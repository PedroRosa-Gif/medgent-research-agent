"""Tests for graph assembly — REAL LangGraph, FAKE llm/sources, fully offline.

Compiles the actual graph via :func:`build_graph` and runs it with
``compiled.invoke(...)``, so these exercise the real routing, the real loop
edge, and the real checkpointer — no network, no provider SDK, no Ollama.

The doubles are the only fakes: ``FakeLLM`` branches on the ``schema`` argument
(planner/refine ask for a :class:`QueryPlan`, the evaluator asks for an
:class:`EvaluatedStudy`) and counts refine calls; ``FakeSource`` returns canned
:class:`Evidence`. Three paths are covered: sufficient-on-first-pass (no loop),
insufficient-forever (loops to the ceiling and stops), and checkpointer/thread
persistence via ``get_state``.
"""

from __future__ import annotations

from medgent.application.graph import build_graph
from medgent.domain.schemas import (
    Evidence,
    EvidenceSource,
    QueryPlan,
    StudyExtraction,
    StudyType,
)
from medgent.domain.state import initial_state

_LONG_ABSTRACT = "y" * 400


class FakeLLM:
    """``LLMPort`` double returning canned structured output per schema.

    Planner and refine call ``generate_structured(prompt, QueryPlan)``; the
    evaluator calls it with ``StudyExtraction``. The fake branches on ``schema``
    to return the right canned type, and counts how many times refine (i.e. a
    ``QueryPlan`` request carrying the refine prompt marker) was asked for so tests
    can assert loop behaviour.
    """

    def __init__(
        self,
        *,
        plan: QueryPlan,
        refine_plan: QueryPlan,
        study: StudyExtraction,
    ) -> None:
        self._plan = plan
        self._refine_plan = refine_plan
        self._study = study
        self.planner_calls = 0
        self.refine_calls = 0
        self.evaluator_calls = 0

    def generate(self, prompt: str) -> str:
        return f"echo: {prompt}"

    def generate_structured(self, prompt: str, schema: type) -> object:
        if schema is QueryPlan:
            # The refine prompt is distinguishable from the planner prompt by its
            # "Previously tried queries" section.
            if "Previously tried queries" in prompt:
                self.refine_calls += 1
                return self._refine_plan
            self.planner_calls += 1
            return self._plan
        if schema is StudyExtraction:
            self.evaluator_calls += 1
            return self._study
        raise AssertionError(f"unexpected schema requested: {schema!r}")


class FakeSource:
    """A fake ``EvidenceRetrievalPort`` returning the same evidence for any query."""

    def __init__(self, evidence: list[Evidence]) -> None:
        self._evidence = evidence
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, max_results: int = 10) -> list[Evidence]:
        self.calls.append((query, max_results))
        return list(self._evidence)


def _evidence(identifier: str) -> Evidence:
    """Build a strong PubMed :class:`Evidence` (abstract + recent year)."""
    return Evidence(
        source=EvidenceSource.PUBMED,
        identifier=identifier,
        title=f"title-{identifier}",
        abstract=_LONG_ABSTRACT,
        year=2023,
    )


def _study(relevance: float) -> StudyExtraction:
    """Build a canned evaluator extraction; identifier/quality are set by the node."""
    return StudyExtraction(
        study_type=StudyType.RCT,
        sample_size=100,
        key_finding="a finding",
        relevance_score=relevance,
    )


def _plan(*queries: str) -> QueryPlan:
    return QueryPlan(queries=list(queries))


# --- sufficient path ---------------------------------------------------------


def test_graph_finishes_without_looping_when_sufficient_on_first_pass() -> None:
    # Three strong studies, each relevance 1.0 => quality clears the threshold,
    # so is_sufficient is True after the first evaluation and the router finishes.
    source = FakeSource([_evidence("a"), _evidence("b"), _evidence("c")])
    llm = FakeLLM(
        plan=_plan("q1", "q2", "q3"),
        refine_plan=_plan("r1"),
        study=_study(relevance=1.0),
    )
    compiled = build_graph(llm, [source], min_studies=3, quality_threshold=0.6)

    config = {"configurable": {"thread_id": "t-sufficient"}}
    final = compiled.invoke(initial_state("topic", max_iterations=3), config=config)

    assert final["is_sufficient"] is True
    assert final["iteration"] == 1
    # refine never ran: a single pass through the loop.
    assert llm.refine_calls == 0
    assert llm.planner_calls == 1
    # The synthesizer ran after "finish": the final report is populated and
    # carries the appended disclaimer.
    assert final["final_report"]
    assert "Disclaimer" in final["final_report"]


# --- loop-to-ceiling path ----------------------------------------------------


def test_graph_loops_until_ceiling_then_stops_when_never_sufficient() -> None:
    # Studies are irrelevant (relevance 0.0 => quality below threshold), so the
    # run is never sufficient and must loop until iteration hits max_iterations.
    source = FakeSource([_evidence("a"), _evidence("b"), _evidence("c")])
    llm = FakeLLM(
        plan=_plan("q1", "q2"),
        refine_plan=_plan("r1", "r2"),
        study=_study(relevance=0.0),
    )
    max_iterations = 3
    compiled = build_graph(llm, [source], min_studies=3, quality_threshold=0.6)

    config = {"configurable": {"thread_id": "t-ceiling"}}
    final = compiled.invoke(
        initial_state("topic", max_iterations=max_iterations),
        config=config,
    )

    # Terminates at exactly the ceiling (the test completing at all proves it is
    # not an infinite loop).
    assert final["is_sufficient"] is False
    assert final["iteration"] == max_iterations
    # planner runs once; refine bridges each subsequent fetch. With a ceiling of 3
    # the evaluator runs 3 times and refine runs on the first 2 insufficient
    # verdicts (the 3rd verdict hits the ceiling and finishes instead).
    assert llm.planner_calls == 1
    assert llm.refine_calls == max_iterations - 1
    assert llm.evaluator_calls == max_iterations * 3
    # Even on the ceiling path the run reaches the synthesizer and produces a
    # report (the studies exist, they were just not relevant enough).
    assert final["final_report"]
    assert "Disclaimer" in final["final_report"]


# --- checkpointer / thread persistence ---------------------------------------


def test_checkpointer_persists_final_state_by_thread_id() -> None:
    source = FakeSource([_evidence("a"), _evidence("b"), _evidence("c")])
    llm = FakeLLM(
        plan=_plan("q1", "q2", "q3"),
        refine_plan=_plan("r1"),
        study=_study(relevance=1.0),
    )
    compiled = build_graph(llm, [source], min_studies=3, quality_threshold=0.6)

    config = {"configurable": {"thread_id": "t-persist"}}
    compiled.invoke(initial_state("metformin safety", max_iterations=3), config=config)

    snapshot = compiled.get_state(config)
    values = snapshot.values
    assert values["topic"] == "metformin safety"
    assert values["is_sufficient"] is True
    assert values["iteration"] == 1
    assert len(values["evaluated_studies"]) == 3
    # a fresh thread_id has no persisted state.
    empty = compiled.get_state({"configurable": {"thread_id": "unknown"}})
    assert empty.values == {}
