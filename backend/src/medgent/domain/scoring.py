"""Domain scoring — deterministic, explainable structural-quality heuristics.

The evaluator's hybrid scoring (see ``docs/architecture.md`` §4) keeps the cheap,
reliable signals in code rather than delegating everything to the LLM. This
module holds those pure functions: a structural-quality heuristic computed from
``Evidence`` metadata, and a linear combiner that blends that heuristic with the
LLM's relevance judgement into a single ``quality_score``.

Dependency rule: center of the hexagon. Imports only the standard library and
domain schemas — no ports, no adapters, no application code, no I/O, no network.
Every function here is pure and deterministic, so it is trivially unit-testable.
"""

from __future__ import annotations

from datetime import date

from medgent.domain.schemas import Evidence

# --- heuristic weighting (explicit so the score is explainable) --------------
#
# ``heuristic_score`` is a weighted sum of three independent structural signals,
# each normalized to [0, 1], with weights that sum to 1.0:
#
#   - abstract presence (0.50): the strongest cheap signal — a record with a
#     real abstract is far more useful than a bare title.
#   - publication recency (0.35): linearly scaled over a recency window; work
#     published this year scores 1.0, work ``_RECENCY_WINDOW_YEARS`` or more
#     years old (or with no year at all) scores 0.0.
#   - abstract substance (0.15): a small bonus when the abstract is more than a
#     trivial snippet (at least ``_SUBSTANTIAL_ABSTRACT_CHARS`` characters).
#
# The final sum already lies in [0, 1], but it is clamped defensively.
_ABSTRACT_PRESENCE_WEIGHT = 0.50
_RECENCY_WEIGHT = 0.35
_ABSTRACT_SUBSTANCE_WEIGHT = 0.15

# Recency window: a paper this year scores full recency; one this many years old
# (or older, or undated) scores zero. ~15 years keeps a decade-plus of evidence
# contributing something rather than falling off a cliff.
_RECENCY_WINDOW_YEARS = 15

# An abstract at least this long counts as "substantial" rather than a snippet.
_SUBSTANTIAL_ABSTRACT_CHARS = 250


def _clamp01(value: float) -> float:
    """Clamp ``value`` into the closed interval [0.0, 1.0]."""
    return max(0.0, min(1.0, value))


def heuristic_score(evidence: Evidence) -> float:
    """Return a deterministic 0.0-1.0 structural-quality signal for ``evidence``.

    This is a pure function of the record's metadata only — it never inspects
    semantics, calls an LLM, or performs I/O, so the same input always yields the
    same output. It is a weighted sum of three normalized signals (weights are
    module constants, documented there and summing to 1.0):

    - **Abstract presence** (weight ``0.50``): ``1.0`` when ``abstract`` is a
      non-empty, non-whitespace string, else ``0.0``. A record with a real
      abstract is the strongest cheap indicator of a usable study.
    - **Publication recency** (weight ``0.35``): linearly scaled over a
      ``_RECENCY_WINDOW_YEARS``-year window ending at the current year. A paper
      published this year scores ``1.0``; one exactly the window's length old
      scores ``0.0``; anything older is clamped to ``0.0``; a missing year scores
      ``0.0``. Future (in-press) years are clamped to ``1.0``.
    - **Abstract substance** (weight ``0.15``): a small bonus of ``1.0`` when the
      abstract has at least ``_SUBSTANTIAL_ABSTRACT_CHARS`` characters, else
      ``0.0``. Rewards a full abstract over a one-line snippet.

    The weighted sum already lies in [0, 1]; it is clamped defensively before
    being returned.
    """
    abstract = evidence.abstract or ""
    has_abstract = bool(abstract.strip())

    presence_signal = 1.0 if has_abstract else 0.0

    if evidence.year is None:
        recency_signal = 0.0
    else:
        current_year = date.today().year
        age = current_year - evidence.year
        recency_signal = _clamp01((_RECENCY_WINDOW_YEARS - age) / _RECENCY_WINDOW_YEARS)

    substance_signal = 1.0 if len(abstract) >= _SUBSTANTIAL_ABSTRACT_CHARS else 0.0

    score = (
        _ABSTRACT_PRESENCE_WEIGHT * presence_signal
        + _RECENCY_WEIGHT * recency_signal
        + _ABSTRACT_SUBSTANCE_WEIGHT * substance_signal
    )
    return _clamp01(score)


def combine_scores(
    heuristic: float,
    relevance: float,
    *,
    heuristic_weight: float = 0.5,
) -> float:
    """Linearly blend the deterministic ``heuristic`` with the LLM ``relevance``.

    Produces the final ``quality_score`` for an :class:`EvaluatedStudy` as a
    convex combination::

        quality = heuristic_weight * heuristic + (1 - heuristic_weight) * relevance

    ``heuristic_weight`` (default ``0.5``, equal weighting) tunes how much the
    cheap structural signal counts versus the model's relevance judgement; it is
    clamped to [0, 1] so the blend stays convex. Both inputs are expected in
    [0, 1] and the result is clamped to [0, 1] defensively.
    """
    weight = _clamp01(heuristic_weight)
    combined = weight * heuristic + (1.0 - weight) * relevance
    return _clamp01(combined)
