"""Web search retrieval adapter — a real :class:`EvidenceRetrievalPort` over DuckDuckGo.

Runs an open-web text search through the ``ddgs`` package (the renamed successor of
``duckduckgo-search``) and normalizes each hit into domain :class:`Evidence`. Where
PubMed yields structured article metadata, the web gives only a title, a result URL,
and a short snippet — so ``identifier`` and ``url`` are both the result URL, the
snippet lands in ``abstract``, and ``authors``/``year`` stay empty.

Resilience mirrors the PubMed adapter: transient failures (rate limits, timeouts)
are retried with exponential backoff before giving up with a :class:`WebSearchError`.
The ``ddgs`` client factory and the sleep function are injectable so tests run fully
offline and without real delays. The ``ddgs`` import is lazy so merely importing this
module never hard-fails when the optional package is absent, and no network I/O ever
happens at import time.

Dependency rule: this adapter implements the ``EvidenceRetrievalPort`` and may import
``ddgs``. The core never imports from here.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from medgent.domain.schemas import Evidence, EvidenceSource

if TYPE_CHECKING:
    from ddgs import DDGS

# Retry policy for transient failures. Three attempts with a doubling base delay
# (0.5s, 1.0s, ...) is enough to ride out brief rate limits without hanging.
_MAX_ATTEMPTS = 3
_BACKOFF_BASE_SECONDS = 0.5

# Sensible defaults for the DuckDuckGo text search.
_DEFAULT_REGION = "us-en"
_DEFAULT_SAFESEARCH = "moderate"

_INSTALL_HINT = (
    "ddgs is required for the web search provider. "
    "Install it with `uv add ddgs` (or `pip install ddgs`)."
)


class WebSearchError(RuntimeError):
    """Raised when the web search backend cannot be reached or keeps failing.

    Signals an *unexpected* failure (rate limiting, timeouts, or any other
    backend error that persists past the retry budget) as distinct from the
    expected "no results" case, which is reported as an empty list instead.
    """


def _import_ddgs() -> type[DDGS]:
    """Import ``DDGS`` lazily, raising a clear hint if the dependency is missing."""
    try:
        from ddgs import DDGS
    except ImportError as exc:  # pragma: no cover - exercised only without the dep
        raise ImportError(_INSTALL_HINT) from exc
    return DDGS


def _is_no_results_error(exc: Exception) -> bool:
    """Tell apart ddgs's "nothing matched" signal from a real backend failure.

    ``ddgs`` raises ``DDGSException("No results found.")`` for an empty result set
    rather than returning ``[]``. That is a normal outcome, not a transient error,
    so it should map to an empty list without burning retries.
    """
    return "no results found" in str(exc).casefold()


class WebSearchAdapter:
    """``EvidenceRetrievalPort`` backed by a DuckDuckGo text search (via ``ddgs``).

    The client factory and the sleep callable are injectable so the retry/backoff
    logic can be exercised offline and instantly in tests — pass a factory that
    returns a fake client exposing ``text(query, **kwargs)``. Constructing an
    adapter performs no network I/O.

    ``ddgs`` ``.text()`` returns a list of dicts shaped roughly like
    ``{"title": str, "href": str, "body": str}`` (observed with ddgs 9.16.1), where
    ``href`` is the result URL and ``body`` is the snippet. Results missing a URL
    are skipped, since the URL is both the identifier and the link.
    """

    def __init__(
        self,
        *,
        region: str = _DEFAULT_REGION,
        safesearch: str = _DEFAULT_SAFESEARCH,
        client_factory: Callable[[], Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._region = region
        self._safesearch = safesearch
        # Default to the real DDGS class, imported lazily so a missing optional
        # dependency surfaces a clear hint only when a client is actually built.
        self._client_factory = client_factory if client_factory is not None else _import_ddgs()
        self._sleep = sleep

    def search(self, query: str, max_results: int = 10) -> list[Evidence]:
        """Search the web for ``query`` and return normalized :class:`Evidence`.

        Returns ``[]`` when the search matches nothing. Raises
        :class:`WebSearchError` on backend failures that persist past the retry
        budget (rate limits, timeouts, or any other ``ddgs`` error).
        """
        raw_results = self._text_search(query, max_results)
        return [
            evidence
            for result in raw_results
            if (evidence := self._parse_result(result)) is not None
        ]

    def _text_search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        """Run the DuckDuckGo text search with retry/backoff on transient errors.

        Builds a fresh client per attempt and retries any backend exception up to
        ``_MAX_ATTEMPTS`` times with exponential backoff (using the injected
        sleep). Raises :class:`WebSearchError` once the budget is exhausted. A
        successful call returning no hits yields an empty list (not an error).
        """
        last_error: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                client = self._client_factory()
                results = client.text(
                    query,
                    region=self._region,
                    safesearch=self._safesearch,
                    max_results=max_results,
                )
            except Exception as exc:  # noqa: BLE001 - normalized into WebSearchError
                # ddgs raises instead of returning an empty list when a query
                # simply matches nothing. That is an expected "no results" case,
                # not a transient backend failure — don't retry, just return [].
                if _is_no_results_error(exc):
                    return []
                last_error = exc
            else:
                return list(results) if results else []

            # Back off before the next attempt, but never after the final one.
            if attempt < _MAX_ATTEMPTS - 1:
                self._sleep(_BACKOFF_BASE_SECONDS * (2**attempt))

        raise WebSearchError(
            f"web search for {query!r} failed after {_MAX_ATTEMPTS} attempts"
        ) from last_error

    @staticmethod
    def _parse_result(result: dict[str, Any]) -> Evidence | None:
        """Normalize one ``ddgs`` text-result dict into an :class:`Evidence`.

        Returns ``None`` when the result carries no URL (``href``), since the URL
        is both the identifier and the link and cannot be synthesized. A missing
        snippet (``body``) maps to ``abstract=None``; a missing title falls back to
        the URL so the required ``title`` field is always populated.
        """
        url = (result.get("href") or "").strip()
        if not url:
            return None

        snippet = (result.get("body") or "").strip()
        title = (result.get("title") or "").strip() or url

        return Evidence(
            source=EvidenceSource.WEB,
            identifier=url,
            title=title,
            abstract=snippet or None,
            authors=[],
            year=None,
            url=url,
        )
