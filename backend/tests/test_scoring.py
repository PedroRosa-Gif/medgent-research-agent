"""Tests for the domain scoring heuristics — pure, no LLM, no I/O.

Pins down :func:`heuristic_score` (abstract presence, publication recency, and
abstract substance, with [0, 1] clamping) and :func:`combine_scores` (convex
blend weighting, boundary values, and clamping). Everything here is deterministic
so assertions are on relative ordering and exact combined values.
"""

from __future__ import annotations

from datetime import date

import pytest

from medgent.domain.schemas import Evidence, EvidenceSource
from medgent.domain.scoring import combine_scores, heuristic_score

_LONG_ABSTRACT = "x" * 400
_SHORT_ABSTRACT = "short snippet"


def _evidence(
    *,
    abstract: str | None = None,
    year: int | None = None,
) -> Evidence:
    """Build a minimal PubMed :class:`Evidence` for scoring."""
    return Evidence(
        source=EvidenceSource.PUBMED,
        identifier="pmid-1",
        title="a title",
        abstract=abstract,
        year=year,
    )


# --- heuristic_score ---------------------------------------------------------


def test_heuristic_score_is_within_unit_interval() -> None:
    current_year = date.today().year
    cases = [
        _evidence(),
        _evidence(abstract=_LONG_ABSTRACT, year=current_year),
        _evidence(abstract=_SHORT_ABSTRACT, year=1990),
        _evidence(year=current_year + 1),
    ]
    for evidence in cases:
        score = heuristic_score(evidence)
        assert 0.0 <= score <= 1.0


def test_heuristic_score_empty_evidence_is_zero() -> None:
    assert heuristic_score(_evidence()) == 0.0


def test_abstract_presence_beats_absence() -> None:
    with_abstract = heuristic_score(_evidence(abstract=_SHORT_ABSTRACT))
    without_abstract = heuristic_score(_evidence())
    assert with_abstract > without_abstract


def test_blank_abstract_counts_as_absent() -> None:
    assert heuristic_score(_evidence(abstract="   ")) == 0.0


def test_recent_year_beats_old_year() -> None:
    current_year = date.today().year
    recent = heuristic_score(_evidence(abstract=_SHORT_ABSTRACT, year=current_year))
    old = heuristic_score(_evidence(abstract=_SHORT_ABSTRACT, year=current_year - 30))
    assert recent > old


def test_present_year_beats_missing_year() -> None:
    current_year = date.today().year
    dated = heuristic_score(_evidence(abstract=_SHORT_ABSTRACT, year=current_year))
    undated = heuristic_score(_evidence(abstract=_SHORT_ABSTRACT, year=None))
    assert dated > undated


def test_substantial_abstract_beats_snippet() -> None:
    current_year = date.today().year
    long_abs = heuristic_score(_evidence(abstract=_LONG_ABSTRACT, year=current_year))
    short_abs = heuristic_score(_evidence(abstract=_SHORT_ABSTRACT, year=current_year))
    assert long_abs > short_abs


def test_best_case_evidence_scores_one() -> None:
    current_year = date.today().year
    best = heuristic_score(_evidence(abstract=_LONG_ABSTRACT, year=current_year))
    assert best == 1.0


def test_future_in_press_year_is_clamped_to_full_recency() -> None:
    current_year = date.today().year
    this_year = heuristic_score(_evidence(abstract=_LONG_ABSTRACT, year=current_year))
    in_press = heuristic_score(_evidence(abstract=_LONG_ABSTRACT, year=current_year + 1))
    assert in_press == this_year == 1.0


# --- combine_scores ----------------------------------------------------------


def test_combine_scores_default_is_equal_blend() -> None:
    assert combine_scores(0.8, 0.4) == pytest.approx(0.6)


def test_combine_scores_respects_heuristic_weight() -> None:
    # heuristic_weight=0.25 => 0.25*1.0 + 0.75*0.0 = 0.25
    assert combine_scores(1.0, 0.0, heuristic_weight=0.25) == 0.25


def test_combine_scores_full_heuristic_weight_ignores_relevance() -> None:
    assert combine_scores(0.3, 0.9, heuristic_weight=1.0) == 0.3


def test_combine_scores_zero_heuristic_weight_ignores_heuristic() -> None:
    assert combine_scores(0.3, 0.9, heuristic_weight=0.0) == 0.9


def test_combine_scores_boundary_values_stay_in_unit_interval() -> None:
    assert combine_scores(1.0, 1.0) == 1.0
    assert combine_scores(0.0, 0.0) == 0.0


def test_combine_scores_clamps_out_of_range_weight() -> None:
    # Weight above 1.0 is clamped to 1.0 => pure heuristic.
    assert combine_scores(0.4, 0.9, heuristic_weight=5.0) == 0.4
    # Weight below 0.0 is clamped to 0.0 => pure relevance.
    assert combine_scores(0.4, 0.9, heuristic_weight=-5.0) == 0.9
