"""Tests for the multi-source evidence aggregator — pure, offline.

Uses fake :class:`EvidenceRetrievalPort` implementations (no adapters, no
network) to pin down concatenation, deduplication by exact ``identifier``, and
the documented fault-isolation behavior when a source raises.
"""

from __future__ import annotations

from medgent.application.retrieval import aggregate_evidence
from medgent.domain.schemas import Evidence, EvidenceSource


class FakeSource:
    """A fake ``EvidenceRetrievalPort`` returning a canned list of evidence."""

    def __init__(self, results: list[Evidence]) -> None:
        self._results = results
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, max_results: int = 10) -> list[Evidence]:
        self.calls.append((query, max_results))
        return list(self._results)


class FailingSource:
    """A fake ``EvidenceRetrievalPort`` whose ``search`` always raises."""

    def search(self, query: str, max_results: int = 10) -> list[Evidence]:
        raise RuntimeError("source is down")


def _web(identifier: str, title: str = "t") -> Evidence:
    """Build a minimal web :class:`Evidence` with the given ``identifier``."""
    return Evidence(
        source=EvidenceSource.WEB,
        identifier=identifier,
        title=title,
        url=identifier,
    )


def _pubmed(identifier: str, title: str = "t") -> Evidence:
    """Build a minimal PubMed :class:`Evidence` with the given ``identifier``."""
    return Evidence(source=EvidenceSource.PUBMED, identifier=identifier, title=title)


def test_concatenates_results_from_all_sources() -> None:
    source_a = FakeSource([_pubmed("111"), _pubmed("222")])
    source_b = FakeSource([_web("https://example.com/a")])

    results = aggregate_evidence([source_a, source_b], "topic")

    assert [e.identifier for e in results] == ["111", "222", "https://example.com/a"]


def test_deduplicates_by_identifier_keeping_first_and_order() -> None:
    # "222" appears in both sources; the first occurrence wins, order preserved.
    source_a = FakeSource([_pubmed("111", "first-111"), _pubmed("222", "first-222")])
    source_b = FakeSource([_pubmed("222", "dup-222"), _pubmed("333", "new-333")])

    results = aggregate_evidence([source_a, source_b], "topic")

    assert [e.identifier for e in results] == ["111", "222", "333"]
    # The kept "222" is the first occurrence, not the later duplicate.
    kept = next(e for e in results if e.identifier == "222")
    assert kept.title == "first-222"


def test_failing_source_is_skipped_and_others_still_return() -> None:
    good = FakeSource([_pubmed("111"), _pubmed("222")])

    # A failing source in the middle must not sink the good ones around it.
    results = aggregate_evidence([FailingSource(), good], "topic")

    assert [e.identifier for e in results] == ["111", "222"]


def test_max_results_per_source_is_forwarded() -> None:
    source = FakeSource([_pubmed("111")])

    aggregate_evidence([source], "topic", max_results_per_source=5)

    assert source.calls == [("topic", 5)]


def test_no_sources_returns_empty_list() -> None:
    assert aggregate_evidence([], "topic") == []
