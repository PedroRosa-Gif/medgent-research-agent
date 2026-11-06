"""FastAPI application factory and routes for the HTTP driving adapter.

:func:`create_app` builds the app, adds CORS for the configured dev origins, and
registers the routes:

- ``GET  /health``          → liveness probe.
- ``POST /research``        → run the loop synchronously, return the final report.
- ``GET  /research/stream`` → Server-Sent Events relay of the reasoning timeline.

The use case is provided through a FastAPI dependency (:func:`get_use_case`) so a
test can override it with one built from fake adapters. This module is the HTTP
composition root: it is allowed to import FastAPI, config, and the concrete
adapters (via the shared :func:`build_use_case`). It holds no business logic —
only HTTP ↔ use-case translation and SSE framing.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import TYPE_CHECKING, Annotated

import anyio
from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from medgent.adapters.driving.api.schemas import (
    ResearchRequest,
    ResearchResponse,
    study_summaries,
)
from medgent.adapters.driving.composition import build_use_case
from medgent.application.use_cases import EventKind, ResearchTopicUseCase
from medgent.config import Settings, get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from medgent.application.use_cases import ResearchEvent

# Sentinel pushed onto the bridge queue by the worker thread to mark the end of
# the sync generator (clean exhaustion). A distinct object so it can never be
# confused with a real ``ResearchEvent``.
_STREAM_DONE = object()


def get_use_case() -> ResearchTopicUseCase:
    """FastAPI dependency returning a use case wired from process settings.

    The default production provider. Tests override this via
    ``app.dependency_overrides[get_use_case]`` to inject a use case built with
    fake adapters, so no route ever touches the network under test.
    """
    return build_use_case(get_settings())


def _step_summary(node: str, update: dict) -> str:
    """Render a concise human-readable summary of one node update.

    Mirrors the CLI's progress lines so both driving adapters describe the loop
    the same way; unknown nodes fall back to listing the keys they changed.
    """
    if node == "planner":
        return f"Planned {len(update.get('queries', []))} queries"
    if node == "refine_queries":
        return f"Refined into {len(update.get('queries', []))} new queries"
    if node == "fetch_evidence":
        return f"Fetched {len(update.get('evidence', []))} papers"
    if node == "evaluator":
        studies = len(update.get("evaluated_studies", []))
        iteration = update.get("iteration", "?")
        sufficient = update.get("is_sufficient", False)
        return f"Evaluated {studies} studies (iteration {iteration}, sufficient={sufficient})"
    if node == "synthesizer":
        return "Report ready"
    return f"{node}: {', '.join(update.keys())}"


def _jsonable(value: object) -> object:
    """Best-effort conversion of a step update into JSON-serializable data.

    Node updates hold Pydantic models (``Evidence``, ``EvaluatedStudy``); dump
    those to plain dicts. Anything already serializable passes through; anything
    else is stringified so an SSE step event can never fail to encode.
    """
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return the configured FastAPI application.

    ``settings`` defaults to :func:`get_settings`; pass an explicit instance to
    control CORS origins and the adapters the default use case is built from. CORS
    is restricted to ``settings.cors_origins`` (the Vite dev server by default).
    """
    settings = settings or get_settings()

    app = FastAPI(
        title="MedGent Research Agent API",
        version="0.1.0",
        summary="HTTP + SSE driving adapter for the clinical research agent.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        """Liveness probe — always ``{"status": "ok"}`` when the app is up."""
        return {"status": "ok"}

    @app.post("/research", response_model=ResearchResponse)
    def research(
        request: ResearchRequest,
        use_case: Annotated[ResearchTopicUseCase, Depends(get_use_case)],
    ) -> ResearchResponse:
        """Run the full research loop synchronously and return the final report.

        Blocks until the loop settles, then returns the report, the number of
        self-correction iterations, and a compact list of evaluated studies.
        """
        state = use_case.run(request.topic, max_iterations=request.max_iterations)
        return ResearchResponse(
            topic=request.topic,
            report=state.get("final_report", ""),
            iterations=state.get("iteration", 0),
            studies=study_summaries(state.get("evaluated_studies", [])),
        )

    @app.get("/research/stream")
    async def research_stream(
        use_case: Annotated[ResearchTopicUseCase, Depends(get_use_case)],
        topic: Annotated[str, Query(min_length=1)],
        max_iterations: Annotated[int | None, Query(ge=1)] = None,
    ) -> EventSourceResponse:
        """Stream the reasoning timeline for ``topic`` over Server-Sent Events.

        Emits ``step`` events (one per node update) and ``token`` events (the
        synthesizer's report, chunk by chunk) as the loop runs, a terminal
        ``done`` event carrying the final report + studies, and an ``error`` event
        if the run raises. The generator is async and yields control between
        events so ``sse-starlette`` can detect client disconnects and send
        heartbeats.
        """
        return EventSourceResponse(
            _event_stream(use_case, topic, max_iterations),
            ping=15,
        )

    return app


async def _aiter_events(
    use_case: ResearchTopicUseCase,
    topic: str,
    max_iterations: int | None,
) -> AsyncIterator[ResearchEvent]:
    """Drive the sync ``stream_events`` generator off-thread, yielding async.

    The use case's :meth:`~ResearchTopicUseCase.stream_events` is a *blocking*
    generator: it pumps LangGraph's synchronous ``graph.stream(...)``, which in
    turn makes blocking LLM/retrieval calls. Iterating it directly inside the
    ``async def`` SSE generator would hold the asyncio event loop for the whole
    run, so ``sse-starlette`` could neither flush events nor send heartbeat pings
    until the run finished — clients time out.

    This bridge runs the sync iteration in a worker thread (via
    :func:`anyio.to_thread.run_sync`, the idiomatic Starlette choice) and hands
    each item to the event loop through an :class:`asyncio.Queue`, pushed with
    ``loop.call_soon_threadsafe`` so the queue is only ever mutated on the loop
    thread. The worker pushes a sentinel on clean exhaustion or the raised
    exception on failure; the async side re-raises that exception so the caller's
    existing ``error`` event path still fires.

    Cancellation/disconnect behavior: if the client disconnects, the async
    generator is closed and this coroutine is cancelled. We cannot forcibly stop a
    sync generator mid-iteration from another thread, so the worker thread is
    allowed to run to completion in the background (its final queue pushes become
    no-ops once no consumer awaits them). Runs are bounded by ``max_iterations``,
    so the thread terminates on its own; this keeps the implementation simple and
    correct without wedging the process.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[object] = asyncio.Queue()

    def _pump() -> None:
        """Run on the worker thread: iterate the sync generator into the queue."""
        try:
            for event in use_case.stream_events(topic, max_iterations=max_iterations):
                loop.call_soon_threadsafe(queue.put_nowait, event)
        except BaseException as exc:  # noqa: BLE001 - forward to the async side
            loop.call_soon_threadsafe(queue.put_nowait, exc)
        else:
            loop.call_soon_threadsafe(queue.put_nowait, _STREAM_DONE)

    worker = asyncio.ensure_future(anyio.to_thread.run_sync(_pump))
    try:
        while True:
            item = await queue.get()
            if item is _STREAM_DONE:
                break
            if isinstance(item, BaseException):
                raise item
            yield item  # type: ignore[misc]  # item is a ResearchEvent here
    finally:
        # Surface a worker failure that happened *after* the loop broke, and make
        # sure the background task is awaited so it does not leak.
        if not worker.done():
            worker.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await worker


async def _event_stream(
    use_case: ResearchTopicUseCase,
    topic: str,
    max_iterations: int | None,
) -> AsyncIterator[dict]:
    """Yield SSE events (``{"event", "data"}`` dicts) for one research run.

    Consumes the :func:`_aiter_events` async bridge, which drives the use case's
    synchronous :meth:`~ResearchTopicUseCase.stream_events` generator on a worker
    thread so the event loop stays free to flush events and send heartbeats.
    ``step`` and ``token`` events are relayed as they arrive; the final synthesizer
    step provides the report and studies for the terminal ``done`` event. Any
    exception is reported as an ``error`` event rather than crashing the
    connection.

    Event contract (``event`` name → JSON ``data``):

    - ``step``  → ``{"node", "summary", "keys", "data"}``
    - ``token`` → ``{"node": "synthesizer", "text"}``
    - ``done``  → ``{"topic", "report", "iterations", "studies"}``
    - ``error`` → ``{"error", "detail"}``
    """
    final_report = ""
    iterations = 0
    studies: list = []
    try:
        async for event in _aiter_events(use_case, topic, max_iterations):
            if event.kind is EventKind.STEP:
                update = event.payload
                if event.node == "synthesizer":
                    final_report = update.get("final_report", final_report)
                if event.node == "evaluator":
                    iterations = update.get("iteration", iterations)
                    studies = update.get("evaluated_studies", studies)
                yield {
                    "event": "step",
                    "data": json.dumps(
                        {
                            "node": event.node,
                            "summary": _step_summary(event.node, update),
                            "keys": list(update.keys()),
                            "data": _jsonable(update),
                        }
                    ),
                }
            else:  # EventKind.TOKEN
                yield {
                    "event": "token",
                    "data": json.dumps({"node": event.node, "text": event.payload}),
                }
    except Exception as exc:  # noqa: BLE001 - surface any failure as an SSE event
        yield {
            "event": "error",
            "data": json.dumps({"error": type(exc).__name__, "detail": str(exc)}),
        }
        return

    yield {
        "event": "done",
        "data": json.dumps(
            {
                "topic": topic,
                "report": final_report,
                "iterations": iterations,
                "studies": [summary.model_dump() for summary in study_summaries(studies)],
            }
        ),
    }
