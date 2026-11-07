"""Tests for the FastAPI driving adapter — fully offline, no network/LLM.

The app is built via :func:`create_app` and its ``get_use_case`` dependency is
overridden with a use case wired to a ``FakeLLM`` + ``FakeSource`` (the same fake
patterns as ``test_research_topic_use_case``), so the real LangGraph loop runs but
no provider SDK or network is touched. Covers ``/health``, ``POST /research``
(success + validation), the ``/research/stream`` SSE contract, and CORS.

Note on token events: the fakes implement :class:`LLMPort` structurally but are
not LangChain chat models, so the synthesizer's ``generate`` returns a whole
string rather than streaming chunks. LangGraph therefore emits no ``messages``
(token) events on the fake path — this is expected. These tests assert the
``step`` + ``done`` contract and that the token-event *plumbing* does not error;
real token streaming requires a streaming LLM (Ollama), exercised manually.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from medgent.adapters.driving.api.app import create_app, get_use_case
from medgent.application.use_cases import EventKind, ResearchEvent, ResearchTopicUseCase
from medgent.config import Settings
from medgent.domain.schemas import (
    Evidence,
    EvidenceSource,
    QueryPlan,
    StudyBatchExtraction,
    StudyExtraction,
    StudyType,
)

_LONG_ABSTRACT = "y" * 400
_DEV_ORIGIN = "http://localhost:5173"


class FakeLLM:
    """``LLMPort`` double: structured per-schema output + canned prose."""

    def __init__(self, *, plan: QueryPlan, study: StudyExtraction) -> None:
        self._plan = plan
        self._study = study

    def generate(self, prompt: str) -> str:
        return "## Summary\n\nSynthesized findings for the topic."

    def generate_structured(self, prompt: str, schema: type) -> object:
        if schema is QueryPlan:
            return self._plan
        if schema is StudyBatchExtraction:
            count = prompt.count(". Title:")
            return StudyBatchExtraction(studies=[self._study for _ in range(count)])
        if schema is StudyExtraction:
            return self._study
        raise AssertionError(f"unexpected schema requested: {schema!r}")


class FakeSource:
    """A fake ``EvidenceRetrievalPort`` returning canned evidence for any query."""

    def __init__(self, evidence: list[Evidence]) -> None:
        self._evidence = evidence

    def search(self, query: str, max_results: int = 10) -> list[Evidence]:
        return list(self._evidence)


def _evidence(identifier: str) -> Evidence:
    return Evidence(
        source=EvidenceSource.PUBMED,
        identifier=identifier,
        title=f"title-{identifier}",
        abstract=_LONG_ABSTRACT,
        year=2023,
    )


def _study(relevance: float = 1.0) -> StudyExtraction:
    return StudyExtraction(
        study_type=StudyType.RCT,
        sample_size=100,
        key_finding="a finding",
        relevance_score=relevance,
    )


def _fake_use_case() -> ResearchTopicUseCase:
    source = FakeSource([_evidence("a"), _evidence("b"), _evidence("c")])
    llm = FakeLLM(plan=QueryPlan(queries=["q1", "q2", "q3"]), study=_study())
    return ResearchTopicUseCase(llm, [source], min_studies=3, quality_threshold=0.6)


@pytest.fixture
def client() -> TestClient:
    """A TestClient whose use case is a fake-wired real graph (offline)."""
    app = create_app(Settings())
    app.dependency_overrides[get_use_case] = _fake_use_case
    return TestClient(app)


# --- /health -----------------------------------------------------------------


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- POST /research ----------------------------------------------------------


def test_research_returns_report_and_studies(client: TestClient) -> None:
    response = client.post("/research", json={"topic": "metformin efficacy"})

    assert response.status_code == 200
    body = response.json()
    assert body["topic"] == "metformin efficacy"
    assert body["report"]
    assert "Disclaimer" in body["report"]
    assert body["iterations"] >= 1
    assert len(body["studies"]) == 3
    study = body["studies"][0]
    assert set(study) == {"identifier", "study_type", "quality_score"}
    assert study["study_type"] == "rct"


def test_research_rejects_missing_topic(client: TestClient) -> None:
    response = client.post("/research", json={})
    assert response.status_code == 422


def test_research_rejects_empty_topic(client: TestClient) -> None:
    response = client.post("/research", json={"topic": ""})
    assert response.status_code == 422


# --- GET /research/stream (SSE) ----------------------------------------------


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    """Parse an SSE body into a list of ``(event_name, data_dict)`` pairs."""
    events: list[tuple[str, dict]] = []
    event_name = "message"
    data_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("event:"):
            event_name = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].strip())
        elif line == "":
            if data_lines:
                events.append((event_name, json.loads("\n".join(data_lines))))
            event_name = "message"
            data_lines = []
    if data_lines:
        events.append((event_name, json.loads("\n".join(data_lines))))
    return events


def test_stream_emits_step_and_done(client: TestClient) -> None:
    response = client.get("/research/stream", params={"topic": "metformin efficacy"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(response.text)
    names = [name for name, _ in events]

    # At least one structured step event and exactly one terminal done event.
    assert "step" in names
    assert names.count("done") == 1

    steps = [data for name, data in events if name == "step"]
    assert any(step["node"] == "planner" for step in steps)
    assert any(step["node"] == "synthesizer" for step in steps)

    # A node_start event precedes each node's work; the planner start must come
    # before the planner step so a UI can show the step as "thinking" while it
    # runs.
    starts = [data for name, data in events if name == "node_start"]
    assert any(start["node"] == "planner" for start in starts)
    planner_start = next(i for i, (name, data) in enumerate(events) if name == "node_start")
    planner_step = next(
        i for i, (name, data) in enumerate(events) if name == "step" and data["node"] == "planner"
    )
    assert planner_start < planner_step

    # Any token events (none on the fake path) must be tagged node=synthesizer.
    tokens = [data for name, data in events if name == "token"]
    assert all(token["node"] == "synthesizer" for token in tokens)

    done = next(data for name, data in events if name == "done")
    assert done["topic"] == "metformin efficacy"
    assert done["report"]
    assert "Disclaimer" in done["report"]
    assert len(done["studies"]) == 3


def test_stream_rejects_empty_topic(client: TestClient) -> None:
    response = client.get("/research/stream", params={"topic": ""})
    assert response.status_code == 422


# --- GET /research/stream: off-thread bridge (scripted fake use case) --------


class ScriptedUseCase:
    """A ``ResearchTopicUseCase`` double exposing only ``stream_events``.

    Its ``stream_events`` is a blocking sync generator (like the real one) that
    replays a scripted list of :class:`ResearchEvent` values, optionally sleeping
    between yields to mimic slow blocking work, and optionally raising partway
    through. It records the thread it iterates on so a test can prove the bridge
    drives it off the request-handler thread. Only the SSE path uses it, so the
    other methods are intentionally absent.
    """

    def __init__(
        self,
        events: list[ResearchEvent],
        *,
        sleep: float = 0.0,
        raise_after: int | None = None,
    ) -> None:
        self._events = events
        self._sleep = sleep
        self._raise_after = raise_after
        self.iter_thread_id: int | None = None

    def stream_events(
        self,
        topic: str,
        *,
        max_iterations: int | None = None,
        thread_id: str | None = None,
    ) -> Iterator[ResearchEvent]:
        self.iter_thread_id = threading.get_ident()
        for index, event in enumerate(self._events):
            if self._raise_after is not None and index == self._raise_after:
                raise RuntimeError("boom")
            if self._sleep:
                time.sleep(self._sleep)
            yield event


def _scripted_events() -> list[ResearchEvent]:
    """A known ordered sequence: planner step, a token, then synthesizer step."""
    return [
        ResearchEvent(EventKind.STEP, "planner", {"queries": ["q1", "q2"]}),
        ResearchEvent(EventKind.TOKEN, "synthesizer", "Hello "),
        ResearchEvent(EventKind.TOKEN, "synthesizer", "world"),
        ResearchEvent(
            EventKind.STEP,
            "synthesizer",
            {"final_report": "## Report\n\nbody"},
        ),
    ]


def _client_for(use_case: object) -> TestClient:
    app = create_app(Settings())
    app.dependency_overrides[get_use_case] = lambda: use_case
    return TestClient(app)


def test_stream_preserves_order_and_ends_with_done() -> None:
    fake = ScriptedUseCase(_scripted_events())
    client = _client_for(fake)

    response = client.get("/research/stream", params={"topic": "t"})
    assert response.status_code == 200

    events = _parse_sse(response.text)
    names = [name for name, _ in events]

    assert names == ["step", "token", "token", "step", "done"]
    assert events[0][1]["node"] == "planner"
    assert events[1][1] == {"node": "synthesizer", "text": "Hello "}
    assert events[2][1] == {"node": "synthesizer", "text": "world"}
    assert events[3][1]["node"] == "synthesizer"

    done = events[-1][1]
    assert done["topic"] == "t"
    assert done["report"] == "## Report\n\nbody"


def test_stream_emits_error_event_on_exception() -> None:
    # Raise after the first event so we see one good event then the error.
    fake = ScriptedUseCase(_scripted_events(), raise_after=1)
    client = _client_for(fake)

    response = client.get("/research/stream", params={"topic": "t"})
    assert response.status_code == 200

    events = _parse_sse(response.text)
    names = [name for name, _ in events]

    assert names[0] == "step"
    assert names[-1] == "error"
    assert "done" not in names
    error = events[-1][1]
    assert error["error"] == "RuntimeError"
    assert error["detail"] == "boom"


def test_stream_drives_slow_sync_generator_without_blocking() -> None:
    # A slow blocking generator: under the old inline-blocking approach this held
    # the event loop; the off-thread bridge delivers every event in order.
    fake = ScriptedUseCase(_scripted_events(), sleep=0.05)
    client = _client_for(fake)

    start = time.monotonic()
    response = client.get("/research/stream", params={"topic": "t"})
    elapsed = time.monotonic() - start

    assert response.status_code == 200
    assert elapsed < 5  # generous ceiling; the real work is ~0.2s of sleeps

    names = [name for name, _ in _parse_sse(response.text)]
    assert names == ["step", "token", "token", "step", "done"]


def test_stream_runs_sync_generator_off_the_request_thread() -> None:
    fake = ScriptedUseCase(_scripted_events())
    client = _client_for(fake)

    response = client.get("/research/stream", params={"topic": "t"})
    assert response.status_code == 200

    # The scripted generator records the thread it iterated on; the bridge must
    # run it in a worker thread, not the current (test) thread.
    assert fake.iter_thread_id is not None
    assert fake.iter_thread_id != threading.get_ident()


# --- CORS --------------------------------------------------------------------


def test_cors_allows_dev_origin(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": _DEV_ORIGIN})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == _DEV_ORIGIN


def test_cors_preflight(client: TestClient) -> None:
    response = client.options(
        "/research",
        headers={
            "Origin": _DEV_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == _DEV_ORIGIN


def test_cors_respects_configured_origins() -> None:
    settings = Settings(cors_origins=["https://app.example.com"])
    app = create_app(settings)
    app.dependency_overrides[get_use_case] = _fake_use_case
    client = TestClient(app)

    allowed = client.get("/health", headers={"Origin": "https://app.example.com"})
    assert allowed.headers.get("access-control-allow-origin") == "https://app.example.com"

    other = client.get("/health", headers={"Origin": _DEV_ORIGIN})
    assert other.headers.get("access-control-allow-origin") != _DEV_ORIGIN
