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

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from medgent.application.retrieval import aggregate_evidence
from medgent.domain.schemas import Evidence, QueryPlan

if TYPE_CHECKING:
    from medgent.application.ports.llm_port import LLMPort
    from medgent.application.ports.retrieval_port import EvidenceRetrievalPort
    from medgent.domain.state import AgentState

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
