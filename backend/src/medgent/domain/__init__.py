"""Domain layer — pure business logic.

Holds the core entities, value objects, and business rules of the research
agent (e.g. research topics, evidence, study evaluations).

Dependency rule: this layer has ZERO framework imports and depends on nothing
else in the project. It must never import from ``application`` or ``adapters``.
Everything else depends inward on the domain; the domain depends on no one.
"""

from medgent.domain.schemas import (
    EvaluatedStudy,
    Evidence,
    EvidenceSource,
    QueryPlan,
    StudyType,
)
from medgent.domain.state import AgentState, initial_state

__all__ = [
    "AgentState",
    "EvaluatedStudy",
    "Evidence",
    "EvidenceSource",
    "QueryPlan",
    "StudyType",
    "initial_state",
]
