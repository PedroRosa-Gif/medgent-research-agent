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
from medgent.domain.schemas import (
    EvaluatedStudy,
    Evidence,
    QueryPlan,
    StudyBatchExtraction,
    StudyExtraction,
)
from medgent.domain.scoring import combine_scores, heuristic_score

if TYPE_CHECKING:
    from medgent.application.ports.llm_port import LLMPort
    from medgent.application.ports.retrieval_port import EvidenceRetrievalPort
    from medgent.domain.state import AgentState

_logger = logging.getLogger(__name__)

# Default ceiling on how many queries the planner / refine step may emit. The
# cap is what actually bounds a run's cost: each query fans out across every
# retrieval source (``max_results_per_source`` papers each), so an uncapped plan
# of dozens of queries multiplies into hundreds of papers and a multi-minute run.
# The prompts also *ask* for at most this many, but the code truncation below is
# the guarantee — it holds regardless of what the model actually returns.
_DEFAULT_MAX_QUERIES = 5

# Planner prompt template. The LLM decomposes one clinical research topic into a
# small set of focused sub-queries spanning distinct axes (mechanism of action,
# efficacy, adverse effects, ...) phrased with appropriate medical terminology so
# they search well against PubMed/MeSH and the web. The "at most five" instruction
# reinforces the hard cap applied in code (see ``make_planner_node``).
_PLANNER_PROMPT = """You are a clinical research librarian planning a literature search.

Decompose the research topic below into at most five focused, non-overlapping \
search queries suitable for PubMed and general web search. Span distinct clinical \
axes such as mechanism of action, efficacy and clinical outcomes, and adverse \
effects and safety. Use precise medical terminology (including MeSH-style terms \
where appropriate) so each query retrieves relevant studies. Return no more than \
five queries — prefer fewer, high-signal queries over many overlapping ones.

Research topic: {topic}"""


def make_planner_node(
    llm: LLMPort,
    *,
    max_queries: int = _DEFAULT_MAX_QUERIES,
) -> Callable[[AgentState], dict]:
    """Build the ``planner`` node bound to the given :class:`LLMPort`.

    The returned callable reads ``state["topic"]``, asks the LLM for a structured
    :class:`QueryPlan`, and returns ``{"queries": [...]}``. If the model returns a
    degenerate plan with no usable queries, the node falls back to a single query
    equal to the topic itself, so ``fetch_evidence`` downstream always has at
    least one query to run rather than stalling on an empty list.

    The number of queries is capped at ``max_queries`` by truncating the plan in
    code (``plan.queries[:max_queries]``). The prompt also asks for "at most five"
    queries, but the truncation is the real guarantee: it bounds a run's cost even
    when the model ignores the instruction and returns dozens of queries (each
    query fans out across every retrieval source, so the query count is the
    dominant multiplier on how many papers a run fetches and evaluates).
    """

    def planner(state: AgentState) -> dict:
        topic = state["topic"]
        prompt = _PLANNER_PROMPT.format(topic=topic)
        plan = llm.generate_structured(prompt, QueryPlan)
        queries = (plan.queries or [topic])[:max_queries]
        return {"queries": queries}

    return planner


def make_fetch_evidence_node(
    sources: Sequence[EvidenceRetrievalPort],
    max_results_per_source: int = 8,
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

# Batch evaluator prompt template. Instead of one call per study, the evaluator
# can present several studies at once (numbered 1..N) and ask the model for one
# structured assessment per study, returned in the SAME ORDER and SAME COUNT as
# the inputs so the node can zip them back onto the source evidence positionally.
# As in the single-study path, ``identifier`` and ``quality_score`` are set by the
# node in code, never by the model (see ``make_evaluator_node``).
_EVALUATOR_BATCH_PROMPT = """You are a clinical evidence analyst extracting a \
structured assessment of several studies at once.

For EACH numbered study below, extract:
- study_type: the methodological category (e.g. meta_analysis, systematic_review, \
rct, cohort, case_control, observational, review, other).
- sample_size: the number of participants if stated, otherwise leave it unset.
- key_finding: one concise sentence stating the study's main clinical finding.
- relevance_score: a number in [0.0, 1.0] for how relevant this study is to the \
research topic.

Return exactly one assessment per study, in the SAME ORDER as the studies are \
listed and with the SAME COUNT — do not skip, merge, reorder, or add studies.

Research topic: {topic}

Studies:
{studies}"""


def _format_batch_studies(chunk: Sequence[Evidence]) -> str:
    """Render a chunk of evidence into a numbered (1..N) title+abstract list.

    The numbering makes the one-assessment-per-study, same-order contract explicit
    to the model; the node relies on positional order, not the numbers, to zip the
    returned extractions back onto the source :class:`Evidence`.
    """
    blocks: list[str] = []
    for index, evidence in enumerate(chunk, start=1):
        blocks.append(f"{index}. Title: {evidence.title}\n   Abstract: {evidence.abstract or ''}")
    return "\n\n".join(blocks)


def make_evaluator_node(
    llm: LLMPort,
    *,
    min_studies: int = 3,
    quality_threshold: float = 0.6,
    heuristic_weight: float = 0.5,
    max_studies_per_iteration: int = 12,
    batch_size: int = 3,
) -> Callable[[AgentState], dict]:
    """Build the ``evaluator`` node bound to the given :class:`LLMPort`.

    The returned callable implements the hybrid scoring of ``docs/architecture.md``
    §4: for each evidence record it computes a deterministic structural heuristic
    in code (:func:`heuristic_score`), asks the LLM for the semantic fields of a
    study (study type, sample size, key finding, relevance to ``state["topic"]``),
    then blends the heuristic with the model's relevance into a final
    ``quality_score`` via :func:`combine_scores`.

    To cut the number of LLM round-trips, studies are evaluated in *batches*: the
    top ``max_studies_per_iteration`` evidence records (ranked by
    :func:`heuristic_score`) are split into chunks of ``batch_size``, and each
    chunk is extracted in a single :class:`StudyBatchExtraction` call. A chunk of
    one — or ``batch_size == 1`` — uses the single-study :class:`StudyExtraction`
    path instead. If a batch call raises OR returns the wrong number of
    extractions, the node logs it and FALLS BACK to evaluating that chunk's studies
    one at a time; a single-study failure within the fallback is logged and skipped
    so one bad extraction cannot abort the whole evaluation.

    Two fields are never trusted to the model and are always set in code, in BOTH
    the batch and single paths: the ``identifier`` is copied from the source
    :class:`Evidence` (not echoed by the LLM), and the ``quality_score`` is the
    combined computation (overriding whatever the LLM returned). The LLM-provided
    ``study_type``, ``sample_size``, ``key_finding``, and ``relevance_score`` are
    kept.

    Sufficiency is a threshold-plus-count rule: the run is sufficient once at
    least ``min_studies`` evaluated studies have ``quality_score`` at or above
    ``quality_threshold``. The node always increments ``iteration`` (even on empty
    evidence) so the self-correction loop's ceiling advances, and returns only the
    keys it changed:
    ``{"evaluated_studies": [...], "is_sufficient": bool, "iteration": int}``.
    """

    def _build_study(evidence: Evidence, extracted: StudyExtraction) -> EvaluatedStudy:
        """Combine one source evidence with its LLM extraction into a final study.

        The LLM's semantic fields are kept; the ``identifier`` comes from the
        source evidence and the ``quality_score`` is computed in code, so the model
        never owns those two fields.
        """
        quality = combine_scores(
            heuristic_score(evidence),
            extracted.relevance_score,
            heuristic_weight=heuristic_weight,
        )
        return EvaluatedStudy(
            identifier=evidence.identifier,
            study_type=extracted.study_type,
            sample_size=extracted.sample_size,
            key_finding=extracted.key_finding,
            relevance_score=extracted.relevance_score,
            quality_score=quality,
        )

    def _evaluate_single(evidence: Evidence, topic: str) -> EvaluatedStudy | None:
        """Evaluate one study via the single-study path; ``None`` on failure.

        Asks the LLM only for the semantic fields (:class:`StudyExtraction`) so it
        cannot emit an out-of-range ``quality_score`` and fail validation. A failed
        extraction is logged and skipped (returns ``None``).
        """
        prompt = _EVALUATOR_PROMPT.format(
            topic=topic,
            title=evidence.title,
            abstract=evidence.abstract or "",
        )
        try:
            extracted = llm.generate_structured(prompt, StudyExtraction)
        except Exception:
            # One bad extraction must not kill the whole evaluation: log it and
            # let the caller move on to the next study.
            _logger.exception(
                "evaluator: structured extraction failed for %s; skipping",
                evidence.identifier,
            )
            return None
        return _build_study(evidence, extracted)

    def _evaluate_chunk(chunk: Sequence[Evidence], topic: str) -> list[EvaluatedStudy]:
        """Evaluate one chunk, batching when possible and falling back when not.

        A chunk of one (or ``batch_size == 1``) goes straight to the single-study
        path. Otherwise one :class:`StudyBatchExtraction` call is made; if it
        raises or returns the wrong count, the node logs it and re-evaluates the
        chunk one study at a time.
        """
        if batch_size == 1 or len(chunk) == 1:
            return [
                study
                for evidence in chunk
                if (study := _evaluate_single(evidence, topic)) is not None
            ]

        prompt = _EVALUATOR_BATCH_PROMPT.format(
            topic=topic,
            studies=_format_batch_studies(chunk),
        )
        try:
            batch = llm.generate_structured(prompt, StudyBatchExtraction)
        except Exception:
            _logger.exception(
                "evaluator: batch extraction raised for %d studies; falling back to one-at-a-time",
                len(chunk),
            )
        else:
            if len(batch.studies) == len(chunk):
                return [
                    _build_study(evidence, extracted)
                    for evidence, extracted in zip(chunk, batch.studies, strict=True)
                ]
            _logger.warning(
                "evaluator: batch returned %d extractions for %d studies; "
                "falling back to one-at-a-time",
                len(batch.studies),
                len(chunk),
            )

        # Fallback: the batch call failed or mismatched — evaluate each study on
        # its own, skipping any individual failure as in the single path.
        return [
            study for evidence in chunk if (study := _evaluate_single(evidence, topic)) is not None
        ]

    def evaluator(state: AgentState) -> dict:
        topic = state["topic"]
        evidence_items = state.get("evidence") or []
        iteration = state.get("iteration", 0)

        # Cap how many studies we send to the LLM per iteration: an unbounded
        # evidence pool (easily dozens of papers) makes a local model painfully
        # slow. Prefer the structurally stronger evidence by heuristic, then
        # evaluate the top slice — in batches to cut LLM round-trips.
        ranked = sorted(evidence_items, key=heuristic_score, reverse=True)
        to_evaluate = ranked[:max_studies_per_iteration]

        evaluated_studies: list[EvaluatedStudy] = []
        for start in range(0, len(to_evaluate), batch_size):
            chunk = to_evaluate[start : start + batch_size]
            evaluated_studies.extend(_evaluate_chunk(chunk, topic))

        passing = sum(1 for s in evaluated_studies if s.quality_score >= quality_threshold)
        is_sufficient = passing >= min_studies

        return {
            "evaluated_studies": evaluated_studies,
            "is_sufficient": is_sufficient,
            "iteration": iteration + 1,
        }

    return evaluator


# Refine prompt template. Reached only when the evaluator judged the current
# evidence insufficient and the iteration ceiling has not been hit. The LLM is
# asked for *new* queries that chase the gaps the previous queries missed —
# different clinical angles and terminology — explicitly avoiding repeats of what
# was already tried, so each loop pass searches genuinely new ground.
_REFINE_PROMPT = """You are a clinical research librarian refining a literature search \
that did not yet surface enough strong evidence.

The queries already tried did not return sufficient high-quality studies. Propose \
at most five new search queries that target gaps the previous attempt missed. \
Explore different clinical angles (e.g. mechanism, specific populations or \
subgroups, comparators, long-term or adverse outcomes) and alternative terminology \
or MeSH-style synonyms. Do NOT repeat any of the previously tried queries, and \
avoid merely rephrasing them. Return no more than five queries.

Research topic: {topic}

Previously tried queries:
{tried_queries}

Evidence found so far: {found_summary}"""


def make_refine_queries_node(
    llm: LLMPort,
    *,
    max_queries: int = _DEFAULT_MAX_QUERIES,
) -> Callable[[AgentState], dict]:
    """Build the ``refine_queries`` node bound to the given :class:`LLMPort`.

    Reached on the self-correction loop's "refine" branch, i.e. when the evaluator
    found the evidence insufficient and the iteration ceiling has not been hit.
    The returned callable reads ``state["topic"]``, the previously tried
    ``state["queries"]``, and ``state["evaluated_studies"]`` (used only to tell the
    model, briefly, what was already found), then asks the LLM for a fresh
    :class:`QueryPlan` aimed at the gaps the previous queries missed. It returns
    ``{"queries": plan.queries}``, which overwrites the old queries so the next
    ``fetch_evidence`` pass searches new ground.

    As in the planner, the refined query list is capped at ``max_queries`` by
    truncating in code so each loop pass stays as cheap as the first; the fallback
    list (previous queries or the topic) is truncated the same way. The prompt also
    asks for "at most five" queries, but the truncation is the guarantee.

    Fallback: if the model returns a degenerate plan with no usable queries, the
    node falls back to the previously tried queries (or the topic itself when none
    were recorded) so the loop keeps a non-empty query list rather than stalling.
    """

    def refine_queries(state: AgentState) -> dict:
        topic = state["topic"]
        previous_queries = state.get("queries", [])
        evaluated_studies = state.get("evaluated_studies", [])

        tried_queries = (
            "\n".join(f"- {query}" for query in previous_queries)
            if previous_queries
            else "(none recorded)"
        )
        if evaluated_studies:
            findings = "; ".join(s.key_finding for s in evaluated_studies[:5])
            found_summary = f"{len(evaluated_studies)} study/studies so far — {findings}"
        else:
            found_summary = "no usable studies yet"

        prompt = _REFINE_PROMPT.format(
            topic=topic,
            tried_queries=tried_queries,
            found_summary=found_summary,
        )
        plan = llm.generate_structured(prompt, QueryPlan)
        queries = (plan.queries or previous_queries or [topic])[:max_queries]
        return {"queries": queries}

    return refine_queries


# Synthesizer prompt template. Reached once the loop finishes (evidence sufficient
# or the iteration ceiling hit). The LLM writes the prose report; the studies list
# is formatted in code and interpolated so the model can cite each study by its
# ``identifier`` (a PMID or URL). The disclaimer is appended in code afterwards, so
# the prompt does not ask the model to produce it.
_SYNTHESIZER_PROMPT = """You are a clinical evidence synthesist writing a concise, \
systematic-review-style report for the research topic below, using only the \
evaluated studies provided.

Write the report in Markdown with these sections:
- "## Summary" — a short overview of what the evidence shows.
- "## Key Findings" — the main findings, drawing on the studies.
- "## Limitations" — gaps, biases, or weaknesses in the available evidence.

Cite studies inline using their identifier in square brackets, e.g. [PMID12345678] \
or [https://example.org/article], immediately after the claim they support. Cite \
every study you rely on and do not invent studies or identifiers beyond those listed. \
Be measured and evidence-based; do not overstate certainty.

Research topic: {topic}

Evaluated studies:
{studies}"""

# Appended verbatim to every synthesized report, in code — never left to the LLM.
# Mirrors the disclaimer in docs/architecture.md: a study/research tool, not medical
# advice, diagnosis, or treatment.
_DISCLAIMER = (
    "\n\n---\n\n"
    "> ⚠️ **Disclaimer**: This is a study/research tool. It does **not** provide "
    "medical advice, diagnosis, or treatment recommendations. Always consult a "
    "qualified healthcare professional for medical decisions."
)

# Report emitted when there is no sufficient evidence to synthesize. The disclaimer
# is appended to this too (in code), so every report carries it.
_NO_EVIDENCE_REPORT = (
    "## Summary\n\n"
    "No sufficient evidence was found for **{topic}**. The search did not surface "
    "studies that met the quality and relevance bar needed to draw conclusions.\n\n"
    "## Key Findings\n\n"
    "None. No qualifying studies were available to synthesize.\n\n"
    "## Limitations\n\n"
    "This absence of evidence is not evidence of absence: stronger or more targeted "
    "searches, broader sources, or newer literature may surface relevant studies."
)


def _format_studies(evaluated_studies: Sequence[EvaluatedStudy]) -> str:
    """Render the evaluated studies into a compact bullet list for the prompt.

    Each line carries the fields the synthesizer needs to cite and weigh a study:
    its ``identifier`` (the PMID or URL used for inline citations), ``study_type``,
    ``sample_size`` (``n/a`` when unknown), and the one-sentence ``key_finding``.
    """
    lines: list[str] = []
    for study in evaluated_studies:
        sample = study.sample_size if study.sample_size is not None else "n/a"
        lines.append(
            f"- [{study.identifier}] type={study.study_type.value}, n={sample}: {study.key_finding}"
        )
    return "\n".join(lines)


def make_synthesizer_node(llm: LLMPort) -> Callable[[AgentState], dict]:
    """Build the ``synthesizer`` node bound to the given :class:`LLMPort`.

    Reached once the self-correction loop finishes (the evidence was judged
    sufficient or the iteration ceiling was hit). The returned callable reads
    ``state["topic"]`` and ``state["evaluated_studies"]`` and asks the LLM for a
    free-form, systematic-review-style Markdown report (Summary / Key Findings /
    Limitations) with inline citations keyed to each study's ``identifier``. The
    studies are formatted in code (:func:`_format_studies`) and interpolated into
    the prompt so the model has the identifier, study type, sample size, and key
    finding of each study to cite and weigh.

    Two things are guaranteed in code, never left to the model: the fixed medical
    :data:`_DISCLAIMER` is always appended to the report, and when there are no
    evaluated studies the node short-circuits to an honest "no sufficient evidence"
    report (:data:`_NO_EVIDENCE_REPORT`) instead of calling the LLM. Returns only
    the key it changed: ``{"final_report": report_text}``.
    """

    def synthesizer(state: AgentState) -> dict:
        topic = state["topic"]
        evaluated_studies = state.get("evaluated_studies", [])

        if not evaluated_studies:
            report = _NO_EVIDENCE_REPORT.format(topic=topic)
            return {"final_report": report + _DISCLAIMER}

        prompt = _SYNTHESIZER_PROMPT.format(
            topic=topic,
            studies=_format_studies(evaluated_studies),
        )
        report = llm.generate(prompt)
        return {"final_report": report + _DISCLAIMER}

    return synthesizer
