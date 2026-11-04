"""Tests for the agent state helpers."""

from medgent.domain.state import AgentState, initial_state


def test_initial_state_defaults() -> None:
    state = initial_state("effects of metformin on longevity")
    assert state["topic"] == "effects of metformin on longevity"
    assert state["queries"] == []
    assert state["evidence"] == []
    assert state["evaluated_studies"] == []
    assert state["iteration"] == 0
    assert state["max_iterations"] == 3
    assert state["is_sufficient"] is False


def test_initial_state_custom_max_iterations() -> None:
    state = initial_state("topic", max_iterations=5)
    assert state["max_iterations"] == 5


def test_initial_state_types() -> None:
    state = initial_state("topic")
    assert isinstance(state, dict)
    assert isinstance(state["queries"], list)
    assert isinstance(state["evidence"], list)
    assert isinstance(state["evaluated_studies"], list)
    assert isinstance(state["iteration"], int)
    assert isinstance(state["is_sufficient"], bool)


def test_initial_state_is_pure() -> None:
    first = initial_state("topic")
    second = initial_state("topic")
    first["queries"].append("mutated")
    assert second["queries"] == []


def test_agent_state_accepts_partial_keys() -> None:
    # total=False: a partial state with only some keys is valid.
    state: AgentState = {"topic": "x"}
    assert state["topic"] == "x"
