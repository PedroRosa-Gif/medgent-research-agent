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

import pytest
from fastapi.testclient import TestClient

from medgent.adapters.driving.api.app import create_app, get_use_case
from medgent.application.use_cases import ResearchTopicUseCase
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
