"""Tests for the planner and fetch_evidence graph nodes — pure, offline.

Uses a ``FakeLLM`` (no provider SDK, no network) and fake
:class:`EvidenceRetrievalPort` sources (no adapters, no network) to pin down the
node contracts: planner emits ``{"queries": [...]}`` with a documented fallback,
and fetch_evidence runs every query across every source and returns a single
cross-query, cross-source deduplicated ``{"evidence": [...]}``.
"""

from __future__ import annotations

from medgent.application.graph import make_fetch_evidence_node, make_planner_node
from medgent.domain.schemas import Evidence, EvidenceSource, QueryPlan
from medgent.domain.state import initial_state


class FakeLLM:
    """In-memory ``LLMPort`` double returning a canned :class:`QueryPlan`."""

    def __init__(self, plan: QueryPlan) -> None:
        self._plan = plan
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        return f"echo: {prompt}"

    def generate_structured(self, prompt: str, schema: type) -> object:
        self.prompts.append(prompt)
        return self._plan


class FakeSource:
    """A fake ``EvidenceRetrievalPort`` keyed by query → canned evidence."""

    def __init__(self, by_query: dict[str, list[Evidence]]) -> None:
        self._by_query = by_query
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, max_results: int = 10) -> list[Evidence]:
        self.calls.append((query, max_results))
        return list(self._by_query.get(query, []))


class FailingSource:
    """A fake ``EvidenceRetrievalPort`` whose ``search`` always raises."""

    def search(self, query: str, max_results: int = 10) -> list[Evidence]:
        raise RuntimeError("source is down")


def _pubmed(identifier: str, title: str = "t") -> Evidence:
    """Build a minimal PubMed :class:`Evidence` with the given ``identifier``."""
    return Evidence(source=EvidenceSource.PUBMED, identifier=identifier, title=title)


def _web(identifier: str, title: str = "t") -> Evidence:
    """Build a minimal web :class:`Evidence` with the given ``identifier``."""
    return Evidence(
        source=EvidenceSource.WEB,
        identifier=identifier,
        title=title,
        url=identifier,
    )


# --- planner -----------------------------------------------------------------


def test_planner_returns_queries_from_plan() -> None:
    plan = QueryPlan(queries=["q1", "q2", "q3"], rationale="why")
    planner = make_planner_node(FakeLLM(plan))

    update = planner(initial_state("metformin safety"))

    assert update == {"queries": ["q1", "q2", "q3"]}


def test_planner_prompt_includes_topic() -> None:
    llm = FakeLLM(QueryPlan(queries=["q1"]))
    planner = make_planner_node(llm)

    planner(initial_state("SGLT2 inhibitors in heart failure"))

    assert "SGLT2 inhibitors in heart failure" in llm.prompts[0]


def test_planner_falls_back_to_topic_on_empty_plan() -> None:
    # QueryPlan forbids an all-blank list, so simulate a degenerate plan with a
    # stand-in object exposing an empty ``queries`` to exercise the fallback.
    class EmptyPlan:
        queries: list[str] = []

    class EmptyPlanLLM:
        def generate(self, prompt: str) -> str:
            return ""

        def generate_structured(self, prompt: str, schema: type) -> object:
            return EmptyPlan()

    planner = make_planner_node(EmptyPlanLLM())

    update = planner(initial_state("aspirin primary prevention"))

    assert update == {"queries": ["aspirin primary prevention"]}


# --- fetch_evidence ----------------------------------------------------------


def test_fetch_evidence_dedupes_across_queries_and_sources() -> None:
    # Two sources, two queries, with identifiers overlapping both across sources
    # (within a query) and across queries. Expected pooled order, first-wins:
    #   q1: source_a -> 111, 222 ; source_b -> 222(dup), 333  => 111, 222, 333
    #   q2: source_a -> 333(dup), 444 ; source_b -> 111(dup) => 444
    # pooled => 111, 222, 333, 444
    source_a = FakeSource(
        {
            "q1": [_pubmed("111"), _pubmed("222")],
            "q2": [_pubmed("333"), _pubmed("444")],
        }
    )
    source_b = FakeSource(
        {
            "q1": [_pubmed("222"), _pubmed("333")],
            "q2": [_pubmed("111")],
        }
    )
    fetch = make_fetch_evidence_node([source_a, source_b])

    state = initial_state("topic")
    state["queries"] = ["q1", "q2"]
    update = fetch(state)

    assert [e.identifier for e in update["evidence"]] == ["111", "222", "333", "444"]


def test_fetch_evidence_keeps_first_occurrence() -> None:
    source_a = FakeSource({"q1": [_pubmed("222", "first-222")]})
    source_b = FakeSource({"q2": [_pubmed("222", "dup-222")]})
    fetch = make_fetch_evidence_node([source_a, source_b])

    state = initial_state("topic")
    state["queries"] = ["q1", "q2"]
    update = fetch(state)

    kept = next(e for e in update["evidence"] if e.identifier == "222")
    assert kept.title == "first-222"


def test_fetch_evidence_forwards_max_results_per_source() -> None:
    source = FakeSource({"q1": [_pubmed("111")]})
    fetch = make_fetch_evidence_node([source], max_results_per_source=5)

    state = initial_state("topic")
    state["queries"] = ["q1"]
    fetch(state)

    assert source.calls == [("q1", 5)]


def test_fetch_evidence_empty_queries_returns_empty() -> None:
    source = FakeSource({"q1": [_pubmed("111")]})
    fetch = make_fetch_evidence_node([source])

    state = initial_state("topic")
    state["queries"] = []
    update = fetch(state)

    assert update == {"evidence": []}
    # No query means the source is never searched.
    assert source.calls == []


def test_fetch_evidence_missing_queries_key_returns_empty() -> None:
    fetch = make_fetch_evidence_node([FakeSource({})])

    # ``AgentState`` is total=False; a state without ``queries`` must not error.
    update = fetch({"topic": "topic"})

    assert update == {"evidence": []}


def test_fetch_evidence_tolerates_failing_source() -> None:
    good = FakeSource({"q1": [_web("https://example.com/a"), _web("https://example.com/b")]})
    fetch = make_fetch_evidence_node([FailingSource(), good])

    state = initial_state("topic")
    state["queries"] = ["q1"]
    update = fetch(state)

    assert [e.identifier for e in update["evidence"]] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
