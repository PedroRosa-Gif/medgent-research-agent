"""Tests for the domain Pydantic schemas."""

from datetime import date

import pytest
from pydantic import ValidationError

from medgent.domain.schemas import (
    EvaluatedStudy,
    Evidence,
    EvidenceSource,
    QueryPlan,
    StudyType,
)


def test_evidence_valid_construction() -> None:
    evidence = Evidence(
        source=EvidenceSource.PUBMED,
        identifier="12345678",
        title="Effect of drug X on condition Y",
        abstract="A randomized trial...",
        authors=["Doe J", "Roe R"],
        year=2021,
        url="https://pubmed.ncbi.nlm.nih.gov/12345678/",
    )
    assert evidence.source is EvidenceSource.PUBMED
    assert evidence.identifier == "12345678"
    assert evidence.authors == ["Doe J", "Roe R"]


def test_evidence_defaults_are_optional() -> None:
    evidence = Evidence(
        source=EvidenceSource.WEB,
        identifier="https://example.org/article",
        title="A web snippet",
    )
    assert evidence.abstract is None
    assert evidence.authors == []
    assert evidence.year is None
    assert evidence.url is None


def test_evidence_accepts_next_year() -> None:
    next_year = date.today().year + 1
    evidence = Evidence(
        source=EvidenceSource.PUBMED,
        identifier="999",
        title="In press",
        year=next_year,
    )
    assert evidence.year == next_year


@pytest.mark.parametrize("bad_year", [1799, 1000, date.today().year + 2, 3000])
def test_evidence_rejects_out_of_range_year(bad_year: int) -> None:
    with pytest.raises(ValidationError):
        Evidence(
            source=EvidenceSource.PUBMED,
            identifier="1",
            title="Bad year",
            year=bad_year,
        )


def test_evaluated_study_valid_construction() -> None:
    study = EvaluatedStudy(
        identifier="12345678",
        study_type=StudyType.RCT,
        sample_size=240,
        key_finding="Drug X reduced symptoms by 30%.",
        relevance_score=0.9,
        quality_score=0.8,
    )
    assert study.study_type is StudyType.RCT
    assert study.sample_size == 240


def test_evaluated_study_sample_size_optional() -> None:
    study = EvaluatedStudy(
        identifier="1",
        study_type=StudyType.REVIEW,
        key_finding="Narrative overview.",
        relevance_score=0.5,
        quality_score=0.5,
    )
    assert study.sample_size is None


@pytest.mark.parametrize("bad_score", [-0.1, 1.1, 2.0])
def test_evaluated_study_rejects_relevance_score_out_of_range(bad_score: float) -> None:
    with pytest.raises(ValidationError):
        EvaluatedStudy(
            identifier="1",
            study_type=StudyType.RCT,
            key_finding="x",
            relevance_score=bad_score,
            quality_score=0.5,
        )


@pytest.mark.parametrize("bad_score", [-0.1, 1.1])
def test_evaluated_study_rejects_quality_score_out_of_range(bad_score: float) -> None:
    with pytest.raises(ValidationError):
        EvaluatedStudy(
            identifier="1",
            study_type=StudyType.RCT,
            key_finding="x",
            relevance_score=0.5,
            quality_score=bad_score,
        )


def test_evaluated_study_rejects_negative_sample_size() -> None:
    with pytest.raises(ValidationError):
        EvaluatedStudy(
            identifier="1",
            study_type=StudyType.COHORT,
            sample_size=-5,
            key_finding="x",
            relevance_score=0.5,
            quality_score=0.5,
        )


def test_evaluated_study_rejects_invalid_study_type() -> None:
    with pytest.raises(ValidationError):
        EvaluatedStudy(
            identifier="1",
            study_type="not_a_real_type",
            key_finding="x",
            relevance_score=0.5,
            quality_score=0.5,
        )


def test_query_plan_valid_construction() -> None:
    plan = QueryPlan(
        queries=["metformin mechanism of action", "metformin adverse effects"],
        rationale="Cover mechanism and safety.",
    )
    assert plan.queries == [
        "metformin mechanism of action",
        "metformin adverse effects",
    ]
    assert plan.rationale == "Cover mechanism and safety."


def test_query_plan_strips_and_drops_blank_queries() -> None:
    plan = QueryPlan(queries=["  spaced query  ", "", "   ", "second"])
    assert plan.queries == ["spaced query", "second"]


def test_query_plan_rejects_empty_queries_list() -> None:
    with pytest.raises(ValidationError):
        QueryPlan(queries=[])


def test_query_plan_rejects_all_blank_queries() -> None:
    with pytest.raises(ValidationError):
        QueryPlan(queries=["", "   "])


def test_evidence_round_trip() -> None:
    evidence = Evidence(
        source=EvidenceSource.WEB,
        identifier="https://example.org/a",
        title="Round trip",
        abstract="snippet",
        authors=["A B"],
        year=2020,
        url="https://example.org/a",
    )
    assert Evidence.model_validate(evidence.model_dump()) == evidence


def test_evaluated_study_round_trip() -> None:
    study = EvaluatedStudy(
        identifier="42",
        study_type=StudyType.META_ANALYSIS,
        sample_size=1000,
        key_finding="Pooled effect is significant.",
        relevance_score=0.95,
        quality_score=0.88,
    )
    assert EvaluatedStudy.model_validate(study.model_dump()) == study
