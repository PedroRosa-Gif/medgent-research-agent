"""Graph assembly — compile the self-correcting research loop into a runnable.

This module is the one place that knows about LangGraph's :class:`StateGraph`: it
wires the node factories from :mod:`medgent.application.graph.nodes` into a state
machine, attaches the conditional routing that drives the bounded self-correction
loop, and compiles the result with a checkpointer.

The loop (see ``docs/architecture.md`` §5)::

    START -> planner -> fetch_evidence -> evaluator -> (route)
                              ^                            |
                              |                            |
                          refine_queries <----- refine ---+
                                                          |
                                             finish ------+-> END

After ``evaluator`` the graph routes on :func:`route_after_evaluator`: when the
evidence is sufficient *or* the iteration ceiling has been reached it goes to the
"finish" branch; otherwise it goes to ``refine_queries``, which reformulates the
queries and loops back into ``fetch_evidence``. The ceiling
(``iteration >= max_iterations``) guarantees termination even if the evidence
never becomes sufficient.

The "finish" branch currently wires straight to ``END``. That is exactly where
the ``synthesizer`` node attaches in a later task — the final report node slots
between the "finish" route and ``END`` without touching the loop.

Dependency rule: this module lives in the application layer and may import
langgraph and the node factories, but it must never import or construct a concrete
adapter (``OllamaAdapter``, ``PubMedAdapter``, ...). It receives the ports as
parameters and injects them into the factories; composing the concrete adapters
happens further out (use case / CLI).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from medgent.application.graph.nodes import (
    make_evaluator_node,
    make_fetch_evidence_node,
    make_planner_node,
    make_refine_queries_node,
)
from medgent.domain.state import AgentState

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph.state import CompiledStateGraph

    from medgent.application.ports.llm_port import LLMPort
    from medgent.application.ports.retrieval_port import EvidenceRetrievalPort


def route_after_evaluator(state: AgentState) -> str:
    """Decide where to go after the evaluator runs.

    Returns ``"finish"`` when the evaluator marked the evidence sufficient *or*
    the iteration counter has reached the ceiling (``max_iterations``, default 3),
    and ``"refine"`` otherwise. Reads only :class:`AgentState` fields so routing
    stays a pure function of state. The ``>=`` comparison on a ceiling the
    evaluator always advances is what guarantees the loop terminates.
    """
    if state.get("is_sufficient") or state.get("iteration", 0) >= state.get("max_iterations", 3):
        return "finish"
    return "refine"


def build_graph(
    llm: LLMPort,
    sources: Sequence[EvidenceRetrievalPort],
    *,
    max_results_per_source: int = 10,
    min_studies: int = 3,
    quality_threshold: float = 0.6,
    heuristic_weight: float = 0.5,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Wire the research nodes into a compiled, checkpointed LangGraph.

    The ports (``llm`` and the retrieval ``sources``) are injected into the node
    factories here; this function never touches a concrete adapter. The tuning
    parameters (``max_results_per_source``, ``min_studies``, ``quality_threshold``,
    ``heuristic_weight``) are forwarded to the ``fetch_evidence`` and ``evaluator``
    factories.

    Topology — ``START -> planner -> fetch_evidence -> evaluator``, then a
    conditional edge on :func:`route_after_evaluator`: ``"finish"`` goes to ``END``
    (where the synthesizer node will later attach) and ``"refine"`` goes to
    ``refine_queries``, which loops back to ``fetch_evidence``. The
    ``iteration >= max_iterations`` ceiling in the router bounds the loop.

    Checkpointing — the graph is compiled with a checkpointer so runs are keyed by
    a ``thread_id`` (passed at invoke time via ``config``), giving step streaming,
    resumable state, and the foundation for future conversational follow-ups. When
    ``checkpointer`` is ``None`` an in-memory :class:`MemorySaver` is used. A formal
    ``CheckpointerPort`` is intentionally not introduced — LangGraph already
    abstracts over Memory/Sqlite savers — and is noted as a future extension.
    """
    if checkpointer is None:
        checkpointer = MemorySaver()

    graph: StateGraph = StateGraph(AgentState)

    graph.add_node("planner", make_planner_node(llm))
    graph.add_node(
        "fetch_evidence",
        make_fetch_evidence_node(sources, max_results_per_source=max_results_per_source),
    )
    graph.add_node(
        "evaluator",
        make_evaluator_node(
            llm,
            min_studies=min_studies,
            quality_threshold=quality_threshold,
            heuristic_weight=heuristic_weight,
        ),
    )
    graph.add_node("refine_queries", make_refine_queries_node(llm))

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "fetch_evidence")
    graph.add_edge("fetch_evidence", "evaluator")
    graph.add_conditional_edges(
        "evaluator",
        route_after_evaluator,
        {"finish": END, "refine": "refine_queries"},
    )
    graph.add_edge("refine_queries", "fetch_evidence")

    return graph.compile(checkpointer=checkpointer)
