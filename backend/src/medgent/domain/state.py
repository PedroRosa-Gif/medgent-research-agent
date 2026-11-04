"""Agent state — the typed dictionary that flows through the LangGraph graph.

The state is a plain :class:`typing.TypedDict` (``total=False``) rather than a
Pydantic model: LangGraph merges partial updates between nodes, so not every key
exists at every step. The *items* inside the state (``Evidence``,
``EvaluatedStudy``) are Pydantic models and carry their own validation.

Node → field map (which node populates/updates which key):

- ``planner``        → ``queries``
- ``fetch_evidence`` → ``evidence``
- ``evaluator``      → ``evaluated_studies``, ``is_sufficient``, ``iteration``
- ``synthesizer``    → ``final_report``

``topic``, ``max_iterations`` are seeded up front by :func:`initial_state`.

Dependency rule: center of the hexagon — stdlib + domain schemas only.
"""

from __future__ import annotations

from typing import TypedDict

from medgent.domain.schemas import EvaluatedStudy, Evidence


class AgentState(TypedDict, total=False):
    """Deterministic state passed between graph nodes.

    ``total=False`` because nodes contribute keys incrementally as the research
    loop progresses; early in the run only a subset of keys is present.
    """

    topic: str
    queries: list[str]
    evidence: list[Evidence]
    evaluated_studies: list[EvaluatedStudy]
    iteration: int
    max_iterations: int
    is_sufficient: bool
    final_report: str


def initial_state(topic: str, max_iterations: int = 3) -> AgentState:
    """Build a well-formed starting state for a research run.

    Pure function: given a topic (and optional iteration cap) it returns a fresh
    state with empty collections, ``iteration`` at zero, and ``is_sufficient``
    unset (``False``). Later nodes fill in the remaining keys.
    """
    return AgentState(
        topic=topic,
        queries=[],
        evidence=[],
        evaluated_studies=[],
        iteration=0,
        max_iterations=max_iterations,
        is_sufficient=False,
    )
