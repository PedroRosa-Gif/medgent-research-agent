"""Tests for the web search retrieval adapter — fully offline.

No real ``DDGS`` is ever constructed and the network is never touched: a fake
client factory returns canned ``ddgs``-shaped dicts, and the adapter's sleep
callable is replaced by a recording fake so retry/backoff adds no real delay and
can be asserted on.
"""

from __future__ import annotations

from typing import Any

import pytest

from medgent.adapters.driven.retrieval.web_search_adapter import (
    WebSearchAdapter,
    WebSearchError,
)
from medgent.application.ports.retrieval_port import EvidenceRetrievalPort
from medgent.domain.schemas import EvidenceSource


class RecordingSleep:
    """Fake ``sleep`` that records its calls instead of waiting."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


class FakeClient:
    """Stand-in for ``ddgs.DDGS`` exposing a canned ``text`` method.

    ``text`` returns the next scripted outcome: a result list to return, or an
    exception instance to raise (simulating a transient backend failure).
    """

    def __init__(self, outcomes: list[Any]) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []

    def text(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append({"query": query, **kwargs})
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _result(
    *,
    title: str | None = "A title",
    href: str | None = "https://example.com/a",
    body: str | None = "A snippet.",
) -> dict[str, Any]:
    """Build a single ``ddgs``-shaped text result, omitting keys set to ``None``."""
    result: dict[str, Any] = {}
    if title is not None:
        result["title"] = title
    if href is not None:
        result["href"] = href
    if body is not None:
        result["body"] = body
    return result


def _make_adapter(
    outcomes: list[Any],
) -> tuple[WebSearchAdapter, FakeClient, RecordingSleep]:
    """Return an adapter wired to a single reused fake client and fake sleep."""
    client = FakeClient(outcomes)
    sleep = RecordingSleep()
    adapter = WebSearchAdapter(client_factory=lambda: client, sleep=sleep)
    return adapter, client, sleep


def test_search_happy_path() -> None:
    results_payload = [
        _result(
            title="Metformin and longevity",
            href="https://example.com/metformin",
            body="A web overview of metformin research.",
        ),
        _result(
            title="Aspirin in prevention",
            href="https://example.com/aspirin",
            body="A web overview of aspirin research.",
        ),
    ]
    adapter, client, sleep = _make_adapter([results_payload])

    results = adapter.search("metformin", max_results=2)

    assert len(results) == 2
    first = results[0]
    assert first.source is EvidenceSource.WEB
    assert first.identifier == "https://example.com/metformin"
    assert first.url == "https://example.com/metformin"
    assert first.title == "Metformin and longevity"
    assert first.abstract == "A web overview of metformin research."
    assert first.authors == []
    assert first.year is None

    # max_results was forwarded to the client, no backoff sleep on success.
    assert client.calls[0]["max_results"] == 2
    assert sleep.calls == []


def test_empty_results_returns_empty_list() -> None:
    adapter, _, _ = _make_adapter([[]])

    assert adapter.search("no such topic") == []


def test_result_missing_url_is_skipped() -> None:
    payload = [
        _result(title="Has url", href="https://example.com/keep", body="kept"),
        _result(title="No url", href=None, body="dropped"),
        _result(title="Blank url", href="   ", body="also dropped"),
    ]
    adapter, _, _ = _make_adapter([payload])

    results = adapter.search("topic")

    assert len(results) == 1
    assert results[0].identifier == "https://example.com/keep"


def test_result_missing_body_yields_none_abstract() -> None:
    adapter, _, _ = _make_adapter([[_result(body=None)]])

    (evidence,) = adapter.search("topic")

    assert evidence.abstract is None
    assert evidence.title == "A title"


def test_result_missing_title_falls_back_to_url() -> None:
    adapter, _, _ = _make_adapter([[_result(title=None, href="https://example.com/x")]])

    (evidence,) = adapter.search("topic")

    assert evidence.title == "https://example.com/x"


def test_retry_on_transient_error_then_succeeds() -> None:
    payload = [_result(href="https://example.com/recovered", title="Recovered")]
    # First attempt raises, second returns results — the adapter should retry.
    adapter, _, sleep = _make_adapter([RuntimeError("transient"), payload])

    results = adapter.search("topic")

    assert len(results) == 1
    assert results[0].identifier == "https://example.com/recovered"
    # Exactly one backoff sleep happened (between the two attempts).
    assert len(sleep.calls) == 1


def test_persistent_failure_raises_web_search_error() -> None:
    outcomes = [RuntimeError("boom"), RuntimeError("boom"), RuntimeError("boom")]
    adapter, _, sleep = _make_adapter(outcomes)

    with pytest.raises(WebSearchError):
        adapter.search("topic")

    # Three attempts means two backoff sleeps (none after the final attempt).
    assert len(sleep.calls) == 2


def test_adapter_satisfies_retrieval_port() -> None:
    adapter, _, _ = _make_adapter([[]])

    assert isinstance(adapter, EvidenceRetrievalPort)
