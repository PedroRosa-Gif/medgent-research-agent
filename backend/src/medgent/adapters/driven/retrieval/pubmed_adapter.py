"""PubMed retrieval adapter — a real :class:`EvidenceRetrievalPort` over NCBI.

Runs a structured literature search against the NCBI E-utilities API using plain
``requests`` (no BioPython): ``esearch`` resolves a query to a list of PMIDs and
``efetch`` returns the article records, which are parsed from XML with the stdlib
``xml.etree.ElementTree`` and normalized into domain :class:`Evidence`.

Resilience is built in two layers. Rate limiting respects NCBI's published
limits by sleeping between requests (~3 req/s without an API key, ~10 with one),
and transient failures (connection errors, HTTP 429/5xx) are retried with
exponential backoff. Both the HTTP session and the sleep function are injectable
so tests run fully offline and without real delays.

Dependency rule: this adapter implements the ``EvidenceRetrievalPort`` and may
import ``requests`` and stdlib XML parsing. It never performs network I/O at
import time.
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from typing import TYPE_CHECKING

import requests

from medgent.domain.schemas import Evidence, EvidenceSource

if TYPE_CHECKING:
    from requests import Response, Session

# Public NCBI E-utilities base. Individual endpoints (``esearch.fcgi`` /
# ``efetch.fcgi``) hang off this.
_DEFAULT_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# NCBI allows ~3 requests/second without an API key and ~10/second with one.
# Sleeping a touch above the strict minimum keeps us safely under the ceiling.
_INTERVAL_WITHOUT_KEY = 0.34
_INTERVAL_WITH_KEY = 0.11

# Retry policy for transient failures. Three attempts with a doubling base delay
# (0.5s, 1.0s, ...) is enough to ride out brief NCBI hiccups without hanging.
_MAX_ATTEMPTS = 3
_BACKOFF_BASE_SECONDS = 0.5
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

# Identify ourselves to NCBI as recommended; this is informational only.
_TOOL_NAME = "medgent-research-agent"


class PubMedRetrievalError(RuntimeError):
    """Raised when PubMed cannot be reached or returns an unusable response.

    Signals an *unexpected* failure (network error, persistent server error,
    malformed payload) as distinct from the expected "no results" case, which is
    reported as an empty list instead.
    """


class PubMedAdapter:
    """``EvidenceRetrievalPort`` backed by NCBI E-utilities (esearch + efetch).

    The HTTP session and the sleep callable are injectable so the rate limiting
    and retry/backoff logic can be exercised offline and instantly in tests.
    Constructing an adapter performs no network I/O.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout: float = 20.0,
        base_url: str = _DEFAULT_BASE_URL,
        session: Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._base_url = base_url.rstrip("/")
        self._session = session if session is not None else requests.Session()
        self._sleep = sleep
        # With a key NCBI permits a higher request rate, so we wait less.
        self._interval = _INTERVAL_WITH_KEY if api_key else _INTERVAL_WITHOUT_KEY

    def search(self, query: str, max_results: int = 10) -> list[Evidence]:
        """Search PubMed for ``query`` and return normalized :class:`Evidence`.

        Runs ``esearch`` to resolve PMIDs then ``efetch`` to pull and parse the
        records. Returns ``[]`` when the query matches nothing (and skips the
        ``efetch`` call entirely). Raises :class:`PubMedRetrievalError` on network
        or server failures that persist past the retry budget.
        """
        pmids = self._esearch(query, max_results)
        if not pmids:
            return []
        # Rate-limit between the two calls to stay under NCBI's per-second cap.
        self._sleep(self._interval)
        return self._efetch(pmids)

    def _esearch(self, query: str, max_results: int) -> list[str]:
        """Resolve ``query`` to a list of PMIDs via the esearch endpoint (JSON)."""
        params = self._with_common_params(
            {
                "db": "pubmed",
                "term": query,
                "retmax": str(max_results),
                "retmode": "json",
            }
        )
        response = self._get(f"{self._base_url}/esearch.fcgi", params)
        try:
            payload = response.json()
        except ValueError as exc:
            raise PubMedRetrievalError("esearch returned a non-JSON response") from exc
        idlist = payload.get("esearchresult", {}).get("idlist", [])
        return [str(pmid) for pmid in idlist]

    def _efetch(self, pmids: list[str]) -> list[Evidence]:
        """Fetch and parse PubMed records for ``pmids`` via the efetch endpoint."""
        params = self._with_common_params(
            {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "xml",
            }
        )
        response = self._get(f"{self._base_url}/efetch.fcgi", params)
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            raise PubMedRetrievalError("efetch returned malformed XML") from exc
        return [
            evidence
            for article in root.iter("PubmedArticle")
            if (evidence := self._parse_article(article)) is not None
        ]

    def _with_common_params(self, params: dict[str, str]) -> dict[str, str]:
        """Add the API key and tool identifier shared by every request."""
        enriched = {"tool": _TOOL_NAME, **params}
        if self._api_key:
            enriched["api_key"] = self._api_key
        return enriched

    def _get(self, url: str, params: dict[str, str]) -> Response:
        """GET ``url`` with retry/backoff on transient connection/server errors.

        Retries NCBI connection errors and HTTP 429/5xx responses up to
        ``_MAX_ATTEMPTS`` times with exponential backoff (using the injected
        sleep). Raises :class:`PubMedRetrievalError` once the budget is exhausted.
        """
        last_error: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                response = self._session.get(url, params=params, timeout=self._timeout)
            except requests.RequestException as exc:
                last_error = exc
            else:
                if response.status_code not in _RETRYABLE_STATUS:
                    response.raise_for_status()
                    return response
                last_error = PubMedRetrievalError(
                    f"PubMed returned retryable status {response.status_code}"
                )

            # Back off before the next attempt, but never after the final one.
            if attempt < _MAX_ATTEMPTS - 1:
                self._sleep(_BACKOFF_BASE_SECONDS * (2**attempt))

        raise PubMedRetrievalError(
            f"PubMed request to {url} failed after {_MAX_ATTEMPTS} attempts"
        ) from last_error

    @staticmethod
    def _parse_article(article: ET.Element) -> Evidence | None:
        """Normalize one ``<PubmedArticle>`` element into an :class:`Evidence`.

        Returns ``None`` when the record has no PMID or no title, since neither
        can be synthesized and both are required by the domain model. Missing
        abstract, authors, or year are tolerated and left empty/None.
        """
        pmid = article.findtext(".//MedlineCitation/PMID")
        title = article.findtext(".//Article/ArticleTitle")
        if not pmid or not title:
            return None

        return Evidence(
            source=EvidenceSource.PUBMED,
            identifier=pmid,
            title=title.strip(),
            abstract=PubMedAdapter._parse_abstract(article),
            authors=PubMedAdapter._parse_authors(article),
            year=PubMedAdapter._parse_year(article),
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        )

    @staticmethod
    def _parse_abstract(article: ET.Element) -> str | None:
        """Join every ``<AbstractText>`` segment; return ``None`` when absent.

        Structured abstracts split the text across multiple labeled segments
        (Background, Methods, Results, ...), so all are concatenated in order.
        """
        segments = [
            node.text.strip()
            for node in article.findall(".//Abstract/AbstractText")
            if node.text and node.text.strip()
        ]
        return " ".join(segments) if segments else None

    @staticmethod
    def _parse_authors(article: ET.Element) -> list[str]:
        """Build display names from ``<AuthorList>`` (last name + fore name/initials)."""
        authors: list[str] = []
        for author in article.findall(".//AuthorList/Author"):
            last_name = author.findtext("LastName")
            fore_name = author.findtext("ForeName") or author.findtext("Initials")
            if last_name and fore_name:
                authors.append(f"{last_name} {fore_name}")
            elif last_name:
                authors.append(last_name)
            else:
                # Corporate/collective authors carry no personal name fields.
                collective = author.findtext("CollectiveName")
                if collective:
                    authors.append(collective.strip())
        return authors

    @staticmethod
    def _parse_year(article: ET.Element) -> int | None:
        """Extract the publication year, falling back across PubMed's variants.

        Prefers the structured ``<PubDate>/<Year>``; when only a free-text
        ``<MedlineDate>`` is present (e.g. "2019 Jan-Feb"), the leading four-digit
        year is pulled out. Returns ``None`` if no usable year is found.
        """
        year_text = article.findtext(".//Journal/JournalIssue/PubDate/Year")
        if year_text and year_text.strip().isdigit():
            return int(year_text.strip())

        medline_date = article.findtext(".//Journal/JournalIssue/PubDate/MedlineDate")
        if medline_date:
            leading = medline_date.strip()[:4]
            if leading.isdigit():
                return int(leading)

        return None
