"""Tests for ResearchTopicUseCase — REAL graph, FAKE llm/sources, offline.

Builds the use case with a ``FakeLLM`` (branches on schema for the structured
planner/evaluator calls, canned prose for the synthesizer's ``generate``) and a
``FakeSource``, then checks both entry points: ``run`` returns a final state with
``final_report`` populated, and ``stream`` yields the expected
``(node, update)`` sequence including planner, fetch_evidence, evaluator, and
synthesizer. No network, no provider SDK.
"""

from __future__ import annotations

import re

from medgent.application.use_cases import ResearchTopicUseCase
from medgent.domain.schemas import (
    Evidence,
    EvidenceSource,
    QueryPlan,
    StudyBatchExtraction,
    StudyExtraction,
    StudyType,
)

_LONG_ABSTRACT = "y" * 400


def _count_numbered_studies(prompt: str) -> int:
    """Count the ``N. Title:`` entries in a batch evaluator prompt."""
    return len(re.findall(r"(?m)^\d+\.\s", prompt))


class FakeLLM:
    """``LLMPort`` double: structured per-schema output + canned prose.

    The evaluator may call with either ``StudyExtraction`` (single path) or
    ``StudyBatchExtraction`` (batch path); for a batch the fake returns the canned
    study repeated to match the number of studies in the prompt.
    """

    def __init__(self, *, plan: QueryPlan, study: StudyExtraction) -> None:
        self._plan = plan
        self._study = study

    def generate(self, prompt: str) -> str:
        return "## Summary\n\nSynthesized findings for the topic."

    def generate_structured(self, prompt: str, schema: type) -> object:
        if schema is QueryPlan:
            return self._plan
        if schema is StudyBatchExtraction:
            count = _count_numbered_studies(prompt)
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


def _use_case() -> ResearchTopicUseCase:
    source = FakeSource([_evidence("a"), _evidence("b"), _evidence("c")])
    llm = FakeLLM(plan=QueryPlan(queries=["q1", "q2", "q3"]), study=_study())
    return ResearchTopicUseCase(llm, [source], min_studies=3, quality_threshold=0.6)


def test_run_returns_state_with_final_report() -> None:
    use_case = _use_case()

    state = use_case.run("metformin efficacy", thread_id="t-run")

    assert state["topic"] == "metformin efficacy"
    assert state["is_sufficient"] is True
    assert state["final_report"]
    assert "Disclaimer" in state["final_report"]


def test_stream_yields_expected_node_sequence() -> None:
    use_case = _use_case()

    steps = list(use_case.stream("metformin efficacy", thread_id="t-stream"))

    nodes = [node for node, _ in steps]
    # Sufficient on the first pass: planner -> fetch -> evaluator -> synthesizer.
    assert nodes == ["planner", "fetch_evidence", "evaluator", "synthesizer"]

    updates = dict(steps)
    assert updates["planner"]["queries"] == ["q1", "q2", "q3"]
    assert len(updates["fetch_evidence"]["evidence"]) == 3
    assert updates["evaluator"]["is_sufficient"] is True
    assert updates["synthesizer"]["final_report"]


def test_runs_are_isolated_by_generated_thread_id() -> None:
    # Two runs without an explicit thread_id must each complete independently
    # (a fresh UUID per call keeps their checkpointed state separate).
    use_case = _use_case()

    first = use_case.run("topic one")
    second = use_case.run("topic two")

    assert first["topic"] == "topic one"
    assert second["topic"] == "topic two"
    assert first["final_report"]
    assert second["final_report"]
