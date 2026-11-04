"""Graph nodes — the plain callables that make up the research loop.

A LangGraph node is a function ``node(state) -> dict`` that returns *only* the
state keys it changed; LangGraph merges that partial update into the running
:class:`AgentState`. Nodes here are built by *factory functions* (closures) that
take the ports they need and return the node callable. Dependency injection via
closure keeps construction (wiring concrete adapters) outside the node and keeps
the node itself trivially unit-testable with fakes.

This module intentionally does not import or build a ``StateGraph`` and does not
depend on langgraph — the nodes are ordinary callables, so they can be tested
without the framework. Wiring them into a graph is a later step.

Dependency rule: nodes live in the application layer and depend *inward only* —
on the domain (:class:`AgentState`, :class:`QueryPlan`, :class:`Evidence`), on
the ports (:class:`LLMPort`, :class:`EvidenceRetrievalPort`), and on the
application-layer aggregator. They must never import a concrete adapter
(``OllamaAdapter``, ``PubMedAdapter``, ...); those are injected from the outside.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from medgent.application.retrieval import aggregate_evidence
from medgent.domain.schemas import EvaluatedStudy, Evidence, QueryPlan
from medgent.domain.scoring import combine_scores, heuristic_score

if TYPE_CHECKING:
    from medgent.application.ports.llm_port import LLMPort
    from medgent.application.ports.retrieval_port import EvidenceRetrievalPort
    from medgent.domain.state import AgentState

_logger = logging.getLogger(__name__)

# Planner prompt template. The LLM decomposes one clinical research topic into a
# small set of focused sub-queries spanning distinct axes (mechanism of action,
# efficacy, adverse effects, ...) phrased with appropriate medical terminology so
# they search well against PubMed/MeSH and the web.
_PLANNER_PROMPT = """You are a clinical research librarian planning a literature search.

Decompose the research topic below into a set of focused, non-overlapping search \
queries suitable for PubMed and general web search. Span distinct clinical axes \
such as mechanism of action, efficacy and clinical outcomes, and adverse effects \
and safety. Use precise medical terminology (including MeSH-style terms where \
appropriate) so each query retrieves relevant studies.

Research topic: {topic}"""


def make_planner_node(llm: LLMPort) -> Callable[[AgentState], dict]:
    """Build the ``planner`` node bound to the given :class:`LLMPort`.

    The returned callable reads ``state["topic"]``, asks the LLM for a structured
    :class:`QueryPlan`, and returns ``{"queries": [...]}``. If the model returns a
    degenerate plan with no usable queries, the node falls back to a single query
    equal to the topic itself, so ``fetch_evidence`` downstream always has at
    least one query to run rather than stalling on an empty list.
    """

    def planner(state: AgentState) -> dict:
        topic = state["topic"]
        prompt = _PLANNER_PROMPT.format(topic=topic)
        plan = llm.generate_structured(prompt, QueryPlan)
        queries = plan.queries or [topic]
        return {"queries": queries}

    return planner


def make_fetch_evidence_node(
    sources: Sequence[EvidenceRetrievalPort],
    max_results_per_source: int = 10,
) -> Callable[[AgentState], dict]:
    """Build the ``fetch_evidence`` node bound to the given retrieval sources.

    The returned callable reads ``state["queries"]`` and, for *each* query, fans
    the search out across all ``sources`` via :func:`aggregate_evidence` (which
    already deduplicates per query and isolates a failing source). The per-query
    results are then concatenated and deduplicated again across queries by exact
    ``identifier`` — first occurrence kept, order preserved — into one pooled
    evidence list returned as ``{"evidence": [...]}``.

    Queries are run independently rather than concatenated into one search, so
    each clinical axis retrieves on its own terms. If ``queries`` is missing or
    empty the node returns ``{"evidence": []}`` without error.
    """

    def fetch_evidence(state: AgentState) -> dict:
        queries = state.get("queries") or []
        pooled: list[Evidence] = []
        seen: set[str] = set()

        for query in queries:
            for evidence in aggregate_evidence(sources, query, max_results_per_source):
                if evidence.identifier in seen:
                    continue
                seen.add(evidence.identifier)
                pooled.append(evidence)

        return {"evidence": pooled}

    return fetch_evidence


# Evaluator prompt template. One study at a time (one abstract per call) keeps
# the structured-extraction task small and reliable for local models. The LLM
# classifies the study and judges its relevance to the research topic; the
# ``identifier`` and final ``quality_score`` are set by the node in code, not by
# the model (see ``make_evaluator_node``).
_EVALUATOR_PROMPT = """You are a clinical evidence analyst extracting a structured \
assessment of a single study.

Read the study title and abstract below and extract:
- study_type: the methodological category (e.g. meta_analysis, systematic_review, \
rct, cohort, case_control, observational, review, other).
- sample_size: the number of participants if stated, otherwise leave it unset.
- key_finding: one concise sentence stating the study's main clinical finding.
- relevance_score: a number in [0.0, 1.0] for how relevant this study is to the \
research topic.

Research topic: {topic}

Study title: {title}

Study abstract: {abstract}"""


def make_evaluator_node(
    llm: LLMPort,
    *,
    min_studies: int = 3,
    quality_threshold: float = 0.6,
    heuristic_weight: float = 0.5,
) -> Callable[[AgentState], dict]:
    """Build the ``evaluator`` node bound to the given :class:`LLMPort`.

    The returned callable implements the hybrid scoring of ``docs/architecture.md``
    §4: for each evidence record it computes a deterministic structural heuristic
    in code (:func:`heuristic_score`), asks the LLM for a structured
    :class:`EvaluatedStudy` (study type, sample size, key finding, relevance to
    ``state["topic"]``) one abstract at a time, then blends the heuristic with the
    model's relevance into a final ``quality_score`` via :func:`combine_scores`.

    Two fields are never trusted to the model and are always set in code: the
    ``identifier`` is copied from the source :class:`Evidence` (not echoed by the
    LLM), and the ``quality_score`` is the combined computation (overriding
    whatever the LLM returned). The LLM-provided ``study_type``, ``sample_size``,
    ``key_finding``, and ``relevance_score`` are kept.

    Sufficiency is a threshold-plus-count rule: the run is sufficient once at
    least ``min_studies`` evaluated studies have ``quality_score`` at or above
    ``quality_threshold``. A per-study LLM failure is logged and skipped so one
    bad extraction cannot abort the whole evaluation. The node always increments
    ``iteration`` (even on empty evidence) so the self-correction loop's ceiling
    advances, and returns only the keys it changed:
    ``{"evaluated_studies": [...], "is_sufficient": bool, "iteration": int}``.
    """

    def evaluator(state: AgentState) -> dict:
        topic = state["topic"]
        evidence_items = state.get("evidence") or []
        iteration = state.get("iteration", 0)

        evaluated_studies: list[EvaluatedStudy] = []
        for evidence in evidence_items:
            heuristic = heuristic_score(evidence)
            prompt = _EVALUATOR_PROMPT.format(
                topic=topic,
                title=evidence.title,
                abstract=evidence.abstract or "",
            )
            try:
                extracted = llm.generate_structured(prompt, EvaluatedStudy)
            except Exception:
                # One bad extraction must not kill the whole evaluation: log it
                # and move on to the next study.
                _logger.exception(
                    "evaluator: structured extraction failed for %s; skipping",
                    evidence.identifier,
                )
                continue

            quality = combine_scores(
                heuristic,
                extracted.relevance_score,
                heuristic_weight=heuristic_weight,
            )
            # Trust the LLM for the semantic fields only; pin the identifier to
            # the source evidence and recompute the quality score in code.
            evaluated_studies.append(
                extracted.model_copy(
                    update={
                        "identifier": evidence.identifier,
                        "quality_score": quality,
                    }
                )
            )

        passing = sum(1 for s in evaluated_studies if s.quality_score >= quality_threshold)
        is_sufficient = passing >= min_studies

        return {
            "evaluated_studies": evaluated_studies,
            "is_sufficient": is_sufficient,
            "iteration": iteration + 1,
        }

    return evaluator
