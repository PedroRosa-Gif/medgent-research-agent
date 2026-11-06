"""Research-topic use case — orchestrate one end-to-end research run.

:class:`ResearchTopicUseCase` is the application-level entry point a driving
adapter (the CLI and the FastAPI SSE API) calls to research a clinical topic. It is
constructed with the ports it needs — an :class:`LLMPort` and a sequence of
:class:`EvidenceRetrievalPort` sources — plus the loop/evaluator tuning
parameters, and it builds the compiled LangGraph internally via
:func:`build_graph`. It exposes three ways to run:

- :meth:`run` executes the whole loop and returns the final :class:`AgentState`
  (with ``final_report`` populated).
- :meth:`stream` yields ``(node_name, update)`` tuples as each node completes, so
  a caller can render live progress.
- :meth:`stream_events` yields normalized :class:`ResearchEvent` values — one
  ``"step"`` event per node update plus ``"token"`` events for the synthesizer
  node's report as it is written — so a streaming transport (the SSE API adapter)
  can relay both structured progress and token-by-token report text.

Dependency rule: this use case depends inward on ``domain``, on the ports, and on
the application-layer :func:`build_graph`. It never imports a concrete adapter
(``OllamaAdapter``, ``PubMedAdapter``, ...); those are injected from the outside
(the CLI is the composition root). ``langgraph`` is allowed here only transitively
through ``build_graph`` — nothing in this module imports it directly.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Sequence
from enum import StrEnum
from typing import TYPE_CHECKING, NamedTuple

from medgent.application.graph import build_graph
from medgent.domain.state import AgentState, initial_state

if TYPE_CHECKING:
    from medgent.application.ports.llm_port import LLMPort
    from medgent.application.ports.retrieval_port import EvidenceRetrievalPort

# The LangGraph node whose free-form report we stream token-by-token. Every other
# node's output is structured JSON, surfaced as a single ``"step"`` event instead.
_SYNTHESIZER_NODE = "synthesizer"


class EventKind(StrEnum):
    """The kind of a normalized :class:`ResearchEvent`.

    ``STEP`` marks one node-update event (the partial state a node returned);
    ``TOKEN`` marks a chunk of the synthesizer's report streamed as it is written.
    """

    STEP = "step"
    TOKEN = "token"


class ResearchEvent(NamedTuple):
    """One normalized event emitted by :meth:`ResearchTopicUseCase.stream_events`.

    - ``kind`` is :class:`EventKind` (``STEP`` or ``TOKEN``).
    - ``node`` is the graph node the event came from (always ``"synthesizer"`` for
      token events).
    - ``payload`` is the partial state dict for a step event, or the text chunk
      (a ``str``) for a token event.
    """

    kind: EventKind
    node: str
    payload: dict | str


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

    def stream_events(
        self,
        topic: str,
        *,
        max_iterations: int | None = None,
        thread_id: str | None = None,
    ) -> Iterator[ResearchEvent]:
        """Execute the loop for ``topic``, yielding normalized streaming events.

        Runs the compiled graph with LangGraph's combined
        ``stream_mode=["updates", "messages"]`` so a single pass produces both:

        - **step events** — one per node completion (``"updates"`` mode), carrying
          the partial state the node returned, yielded as
          ``ResearchEvent(EventKind.STEP, node, update_dict)``; and
        - **token events** — the LLM message chunks produced *inside* the
          synthesizer node (``"messages"`` mode), yielded as
          ``ResearchEvent(EventKind.TOKEN, "synthesizer", text_chunk)``.

        Token events are filtered to the synthesizer node only: the planner,
        evaluator, and refine nodes drive the LLM for structured JSON output, which
        is uninteresting as a token stream and is already surfaced by their step
        events. Filtering uses the ``langgraph_node`` key LangGraph puts in each
        message chunk's metadata; chunks from any other node (or carrying no text)
        are dropped. ``thread_id`` and ``max_iterations`` behave as in :meth:`run`.

        This keeps the use case framework-light: it depends on langgraph's stream
        contract (already an application-layer dependency via :func:`build_graph`)
        but on no HTTP/SSE framework. ``run`` and ``stream`` are left untouched.
        """
        state = initial_state(topic, max_iterations=self._resolve_iterations(max_iterations))
        config = {"configurable": {"thread_id": thread_id or uuid.uuid4().hex}}
        for mode, chunk in self._compiled.stream(
            state, config=config, stream_mode=["updates", "messages"]
        ):
            if mode == "updates":
                # One single-entry dict per node completion: {node: partial_update}.
                for node, update in chunk.items():
                    yield ResearchEvent(EventKind.STEP, node, update)
            elif mode == "messages":
                # (message_chunk, metadata); keep only the synthesizer's text.
                message, metadata = chunk
                if metadata.get("langgraph_node") != _SYNTHESIZER_NODE:
                    continue
                text = _message_text(message)
                if text:
                    yield ResearchEvent(EventKind.TOKEN, _SYNTHESIZER_NODE, text)

    def _resolve_iterations(self, override: int | None) -> int:
        """Return the per-run iteration ceiling, honoring an optional override."""
        return override if override is not None else self._max_iterations


def _message_text(message: object) -> str:
    """Extract plain text from a LangGraph ``"messages"`` chunk.

    A chunk is normally a LangChain ``BaseMessage``/``AIMessageChunk`` whose
    ``content`` is either a ``str`` or a list of content blocks (dicts with a
    ``"text"`` field, as newer multimodal messages use). Returns the concatenated
    text, or an empty string when the chunk carries none, so the caller can simply
    skip empty chunks.
    """
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "".join(parts)
    return ""
