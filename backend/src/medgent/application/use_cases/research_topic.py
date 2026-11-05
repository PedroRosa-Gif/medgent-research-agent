"""Research-topic use case — orchestrate one end-to-end research run.

:class:`ResearchTopicUseCase` is the application-level entry point a driving
adapter (CLI today, HTTP later) calls to research a clinical topic. It is
constructed with the ports it needs — an :class:`LLMPort` and a sequence of
:class:`EvidenceRetrievalPort` sources — plus the loop/evaluator tuning
parameters, and it builds the compiled LangGraph internally via
:func:`build_graph`. It exposes two ways to run:

- :meth:`run` executes the whole loop and returns the final :class:`AgentState`
  (with ``final_report`` populated).
- :meth:`stream` yields ``(node_name, update)`` tuples as each node completes, so
  a caller can render live progress.

Dependency rule: this use case depends inward on ``domain``, on the ports, and on
the application-layer :func:`build_graph`. It never imports a concrete adapter
(``OllamaAdapter``, ``PubMedAdapter``, ...); those are injected from the outside
(the CLI is the composition root). ``langgraph`` is allowed here only transitively
through ``build_graph`` — nothing in this module imports it directly.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING

from medgent.application.graph import build_graph
from medgent.domain.state import AgentState, initial_state

if TYPE_CHECKING:
    from medgent.application.ports.llm_port import LLMPort
    from medgent.application.ports.retrieval_port import EvidenceRetrievalPort


class ResearchTopicUseCase:
    """Run the self-correcting research loop for a single clinical topic.

    Construction wires the injected ports into a compiled graph once; each call to
    :meth:`run` / :meth:`stream` then executes that graph against a fresh
    :func:`initial_state`. Runs are isolated by a ``thread_id`` (generated per call
    when not supplied) so the graph's checkpointer keeps their state separate.

    The tuning parameters mirror :func:`build_graph`'s defaults so the use case is
    a thin, faithful wrapper: ``max_iterations`` seeds the loop ceiling in the
    state, while ``max_results_per_source``, ``min_studies``, ``quality_threshold``,
    ``heuristic_weight``, ``max_studies_per_iteration``, and ``batch_size`` are
    forwarded to the graph nodes.
    """

    def __init__(
        self,
        llm: LLMPort,
        sources: Sequence[EvidenceRetrievalPort],
        *,
        max_iterations: int = 3,
        max_results_per_source: int = 8,
        min_studies: int = 3,
        quality_threshold: float = 0.6,
        heuristic_weight: float = 0.5,
        max_studies_per_iteration: int = 12,
        batch_size: int = 3,
    ) -> None:
        self._max_iterations = max_iterations
        self._compiled = build_graph(
            llm,
            sources,
            max_results_per_source=max_results_per_source,
            min_studies=min_studies,
            quality_threshold=quality_threshold,
            heuristic_weight=heuristic_weight,
            max_studies_per_iteration=max_studies_per_iteration,
            batch_size=batch_size,
        )

    def run(
        self,
        topic: str,
        *,
        max_iterations: int | None = None,
        thread_id: str | None = None,
    ) -> AgentState:
        """Execute the full loop for ``topic`` and return the final state.

        Runs every node to completion and returns the terminal :class:`AgentState`,
        whose ``final_report`` holds the synthesized Markdown report. ``thread_id``
        keys the run in the checkpointer (a fresh UUID is used when omitted);
        ``max_iterations`` overrides the loop ceiling for this run only, defaulting
        to the value set at construction.
        """
        state = initial_state(topic, max_iterations=self._resolve_iterations(max_iterations))
        config = {"configurable": {"thread_id": thread_id or uuid.uuid4().hex}}
        return self._compiled.invoke(state, config=config)

    def stream(
        self,
        topic: str,
        *,
        max_iterations: int | None = None,
        thread_id: str | None = None,
    ) -> Iterator[tuple[str, dict]]:
        """Execute the loop for ``topic``, yielding progress as each node finishes.

        Iterates the graph in ``"updates"`` stream mode and yields one
        ``(node_name, update)`` tuple per node completion, where ``update`` is the
        partial state dict that node returned (e.g. ``("planner", {"queries": [...]})``,
        ``("synthesizer", {"final_report": "..."})``). A caller can render these in
        real time; the final report is available from the last ``synthesizer``
        update (or by calling :meth:`run`). ``thread_id`` and ``max_iterations``
        behave as in :meth:`run`.
        """
        state = initial_state(topic, max_iterations=self._resolve_iterations(max_iterations))
        config = {"configurable": {"thread_id": thread_id or uuid.uuid4().hex}}
        for step in self._compiled.stream(state, config=config, stream_mode="updates"):
            # In "updates" mode each streamed step is a single-entry dict keyed by
            # the node name that just ran, mapping to the partial state it returned.
            yield from step.items()

    def _resolve_iterations(self, override: int | None) -> int:
        """Return the per-run iteration ceiling, honoring an optional override."""
        return override if override is not None else self._max_iterations
