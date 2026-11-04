"""Domain schemas — source-agnostic data models for the research agent.

These Pydantic v2 models are the structured values that flow through the agent
graph: normalized ``Evidence`` retrieved from any source, the ``EvaluatedStudy``
produced by the evaluator node, and the ``QueryPlan`` emitted by the planner.

Dependency rule: this module lives at the center of the hexagon. It imports only
Pydantic and the standard library — no frameworks, no I/O, no network. Pydantic
is permitted here because it is data modeling/validation, not I/O.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

# Lowest plausible publication year; anything earlier is almost certainly a typo.
_MIN_PUBLICATION_YEAR = 1800


class EvidenceSource(StrEnum):
    """Where a piece of evidence was retrieved from."""

    PUBMED = "pubmed"
    WEB = "web"


class StudyType(StrEnum):
    """Methodological category of a study, ordered loosely by evidence strength."""

    META_ANALYSIS = "meta_analysis"
    SYSTEMATIC_REVIEW = "systematic_review"
    RCT = "rct"
    COHORT = "cohort"
    CASE_CONTROL = "case_control"
    OBSERVATIONAL = "observational"
    REVIEW = "review"
    OTHER = "other"


class Evidence(BaseModel):
    """A normalized, source-agnostic piece of retrieved evidence.

    A single record whether it came from PubMed or a web search. ``identifier``
    is the stable id for the record (a PMID for PubMed, a URL for the web), and
    ``abstract`` holds the abstract for PubMed results or the snippet for web
    results.
    """

    source: EvidenceSource
    identifier: str
    title: str
    abstract: str | None = None
    authors: list[str] = []
    year: int | None = None
    url: str | None = None

    @field_validator("year")
    @classmethod
    def _year_within_sane_range(cls, value: int | None) -> int | None:
        """Reject obviously wrong years while allowing next year's in-press work."""
        if value is None:
            return value
        max_year = date.today().year + 1
        if not _MIN_PUBLICATION_YEAR <= value <= max_year:
            raise ValueError(
                f"year must be between {_MIN_PUBLICATION_YEAR} and {max_year}, got {value}"
            )
        return value


class EvaluatedStudy(BaseModel):
    """The structured assessment produced by the evaluator node.

    Each instance is derived from a single :class:`Evidence` record, linked back
    to it via ``identifier``. The two scores capture different things:

    - ``relevance_score``: how relevant the study is to the research topic, as
      judged by the LLM.
    - ``quality_score``: a combined heuristic (study type, sample size, etc.)
      blended with relevance — the overall usefulness of the study.
    """

    identifier: str
    study_type: StudyType
    sample_size: int | None = Field(default=None, ge=0)
    key_finding: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    quality_score: float = Field(ge=0.0, le=1.0)


class QueryPlan(BaseModel):
    """The structured output of the planner node.

    Passed to the LLM via ``with_structured_output``. ``queries`` is the list of
    search strings to run; ``rationale`` is optional short reasoning for the plan.
    """

    queries: list[str]
    rationale: str | None = None

    @field_validator("queries")
    @classmethod
    def _non_empty_queries(cls, value: list[str]) -> list[str]:
        """Strip whitespace, drop blank entries, and require at least one query."""
        cleaned = [query.strip() for query in value if query and query.strip()]
        if not cleaned:
            raise ValueError("queries must contain at least one non-blank string")
        return cleaned
