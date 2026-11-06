"""HTTP request/response models for the API adapter (DTOs, not domain models).

These Pydantic v2 models shape the JSON contract at the HTTP boundary and keep
the domain models (:class:`EvaluatedStudy`, …) from leaking their full shape into
the API. :func:`study_summaries` projects the evaluator's rich studies down to the
compact ``StudySummary`` the API returns.

Dependency rule: this is driving-adapter code, so importing the domain schemas is
allowed; nothing in domain/application imports from here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from collections.abc import Sequence

    from medgent.domain.schemas import EvaluatedStudy

_DEFAULT_MAX_ITERATIONS = 3


class ResearchRequest(BaseModel):
    """Body of ``POST /research``.

    ``topic`` is required and must be non-blank (``min_length=1`` plus a strip);
    ``max_iterations`` optionally overrides the self-correction loop ceiling for
    this run only.
    """

    topic: str = Field(min_length=1, description="The clinical topic to research.")
    max_iterations: int | None = Field(
        default=None,
        ge=1,
        description="Override the self-correction loop ceiling (default: 3).",
    )


class StudySummary(BaseModel):
    """Compact view of one evaluated study returned to API clients."""

    identifier: str
    study_type: str
    quality_score: float


class ResearchResponse(BaseModel):
    """Body of a successful ``POST /research`` response."""

    topic: str
    report: str
    iterations: int
    studies: list[StudySummary]


def study_summaries(studies: Sequence[EvaluatedStudy]) -> list[StudySummary]:
    """Project evaluated studies down to the compact API :class:`StudySummary`."""
    return [
        StudySummary(
            identifier=study.identifier,
            study_type=study.study_type.value,
            quality_score=study.quality_score,
        )
        for study in studies
    ]
