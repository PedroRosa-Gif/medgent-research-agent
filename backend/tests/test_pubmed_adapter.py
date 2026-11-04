"""Tests for the PubMed retrieval adapter — fully offline.

Every HTTP call to NCBI E-utilities is mocked with the ``responses`` library, and
the adapter's sleep callable is replaced by a recording fake so rate limiting and
retry/backoff add no real delay and can be asserted on. No test touches the
network.
"""

from __future__ import annotations

import responses

from medgent.adapters.driven.retrieval.pubmed_adapter import (
    PubMedAdapter,
    PubMedRetrievalError,
)
from medgent.application.ports.retrieval_port import EvidenceRetrievalPort
from medgent.domain.schemas import EvidenceSource

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ESEARCH_URL = f"{BASE_URL}/esearch.fcgi"
EFETCH_URL = f"{BASE_URL}/efetch.fcgi"


class RecordingSleep:
    """Fake ``sleep`` that records its calls instead of waiting."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def _esearch_body(*pmids: str) -> str:
    """Build a minimal esearch JSON payload listing ``pmids``."""
    ids = ", ".join(f'"{pmid}"' for pmid in pmids)
    return (
        '{"esearchresult": {"count": "%d", "idlist": [%s]}}' % (len(pmids), ids)  # noqa: UP031
    )


def _article_xml(
    *,
    pmid: str,
    title: str,
    abstract_segments: list[str] | None = None,
    authors: list[tuple[str, str]] | None = None,
    year: str | None = None,
    medline_date: str | None = None,
) -> str:
    """Build a single ``<PubmedArticle>`` XML fragment from the given parts."""
    abstract = ""
    if abstract_segments is not None:
        parts = "".join(f"<AbstractText>{seg}</AbstractText>" for seg in abstract_segments)
        abstract = f"<Abstract>{parts}</Abstract>"

    author_list = ""
    if authors:
        entries = "".join(
            f"<Author><LastName>{last}</LastName><ForeName>{fore}</ForeName></Author>"
            for last, fore in authors
        )
        author_list = f"<AuthorList>{entries}</AuthorList>"

    pub_date = ""
    if year is not None:
        pub_date = f"<Year>{year}</Year>"
    elif medline_date is not None:
        pub_date = f"<MedlineDate>{medline_date}</MedlineDate>"

    return f"""
    <PubmedArticle>
      <MedlineCitation>
        <PMID>{pmid}</PMID>
        <Article>
          <Journal>
            <JournalIssue>
              <PubDate>{pub_date}</PubDate>
            </JournalIssue>
          </Journal>
          <ArticleTitle>{title}</ArticleTitle>
          {abstract}
          {author_list}
        </Article>
      </MedlineCitation>
    </PubmedArticle>
    """


def _efetch_body(*articles: str) -> str:
    """Wrap article fragments in a ``<PubmedArticleSet>`` root."""
    return f"<?xml version='1.0'?><PubmedArticleSet>{''.join(articles)}</PubmedArticleSet>"


def _make_adapter() -> tuple[PubMedAdapter, RecordingSleep]:
    """Return an adapter wired to a recording fake sleep (no real delays)."""
    sleep = RecordingSleep()
    return PubMedAdapter(sleep=sleep), sleep


@responses.activate
def test_search_happy_path() -> None:
    responses.add(responses.GET, ESEARCH_URL, body=_esearch_body("111", "222"), status=200)
    responses.add(
        responses.GET,
        EFETCH_URL,
        body=_efetch_body(
            _article_xml(
                pmid="111",
                title="Metformin and longevity",
                abstract_segments=["A randomized trial of metformin."],
                authors=[("Doe", "John"), ("Roe", "Jane")],
                year="2021",
            ),
            _article_xml(
                pmid="222",
                title="Aspirin in primary prevention",
                abstract_segments=["Pooled analysis of aspirin use."],
                authors=[("Smith", "Alan")],
                year="2019",
            ),
        ),
        status=200,
        content_type="application/xml",
    )

    adapter, _ = _make_adapter()
    results = adapter.search("metformin", max_results=2)

    assert len(results) == 2
    first, second = results
    assert first.source is EvidenceSource.PUBMED
    assert first.identifier == "111"
    assert first.title == "Metformin and longevity"
    assert first.abstract == "A randomized trial of metformin."
    assert first.authors == ["Doe John", "Roe Jane"]
    assert first.year == 2021
    assert first.url == "https://pubmed.ncbi.nlm.nih.gov/111/"

    assert second.identifier == "222"
    assert second.authors == ["Smith Alan"]
    assert second.year == 2019


@responses.activate
def test_search_empty_results_skips_efetch() -> None:
    responses.add(responses.GET, ESEARCH_URL, body=_esearch_body(), status=200)
    # Deliberately register no efetch mock: calling it would raise.

    adapter, sleep = _make_adapter()
    results = adapter.search("no such topic")

    assert results == []
    # Exactly one HTTP call was made (esearch), and no inter-call sleep happened.
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url.startswith(ESEARCH_URL)
    assert sleep.calls == []


@responses.activate
def test_article_without_abstract_yields_none() -> None:
    responses.add(responses.GET, ESEARCH_URL, body=_esearch_body("333"), status=200)
    responses.add(
        responses.GET,
        EFETCH_URL,
        body=_efetch_body(_article_xml(pmid="333", title="No abstract here", year="2020")),
        status=200,
    )

    adapter, _ = _make_adapter()
    (evidence,) = adapter.search("topic")

    assert evidence.abstract is None
    assert evidence.title == "No abstract here"


@responses.activate
def test_multi_segment_abstract_is_joined() -> None:
    responses.add(responses.GET, ESEARCH_URL, body=_esearch_body("444"), status=200)
    responses.add(
        responses.GET,
        EFETCH_URL,
        body=_efetch_body(
            _article_xml(
                pmid="444",
                title="Structured abstract",
                abstract_segments=["Background text.", "Methods text.", "Results text."],
                year="2022",
            )
        ),
        status=200,
    )

    adapter, _ = _make_adapter()
    (evidence,) = adapter.search("topic")

    assert evidence.abstract == "Background text. Methods text. Results text."


@responses.activate
def test_missing_year_yields_none() -> None:
    responses.add(responses.GET, ESEARCH_URL, body=_esearch_body("555"), status=200)
    responses.add(
        responses.GET,
        EFETCH_URL,
        body=_efetch_body(_article_xml(pmid="555", title="Undated study")),
        status=200,
    )

    adapter, _ = _make_adapter()
    (evidence,) = adapter.search("topic")

    assert evidence.year is None


@responses.activate
def test_medline_date_year_is_parsed() -> None:
    responses.add(responses.GET, ESEARCH_URL, body=_esearch_body("666"), status=200)
    responses.add(
        responses.GET,
        EFETCH_URL,
        body=_efetch_body(
            _article_xml(
                pmid="666",
                title="MedlineDate study",
                medline_date="2018 Jan-Feb",
            )
        ),
        status=200,
    )

    adapter, _ = _make_adapter()
    (evidence,) = adapter.search("topic")

    assert evidence.year == 2018


@responses.activate
def test_retry_on_503_then_succeeds() -> None:
    # esearch: first a transient 503, then a 200 — the adapter should retry.
    responses.add(responses.GET, ESEARCH_URL, status=503)
    responses.add(responses.GET, ESEARCH_URL, body=_esearch_body("777"), status=200)
    responses.add(
        responses.GET,
        EFETCH_URL,
        body=_efetch_body(_article_xml(pmid="777", title="Recovered", year="2023")),
        status=200,
    )

    adapter, sleep = _make_adapter()
    results = adapter.search("topic")

    assert len(results) == 1
    assert results[0].identifier == "777"
    # Backoff slept at least once (the retry) plus the inter-call rate-limit sleep.
    assert len(sleep.calls) >= 2


@responses.activate
def test_persistent_server_error_raises() -> None:
    for _ in range(3):
        responses.add(responses.GET, ESEARCH_URL, status=503)

    adapter, _ = _make_adapter()
    try:
        adapter.search("topic")
    except PubMedRetrievalError:
        pass
    else:  # pragma: no cover - failure path
        raise AssertionError("expected PubMedRetrievalError on persistent 503")


def test_adapter_satisfies_retrieval_port() -> None:
    adapter, _ = _make_adapter()
    assert isinstance(adapter, EvidenceRetrievalPort)
