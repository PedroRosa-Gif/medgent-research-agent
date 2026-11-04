"""Multi-source evidence aggregation.

Composes several :class:`EvidenceRetrievalPort` sources into one call: run the
same query against each, concatenate the results, and drop duplicates so the
caller gets a single normalized, deduplicated list of :class:`Evidence`.

Dependency rule: this module depends only on the ``EvidenceRetrievalPort``
abstraction and the domain :class:`Evidence`. It never imports a concrete
adapter — sources are passed in from the outside, which is exactly the port
composition this layer is meant to demonstrate.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

from medgent.domain.schemas import Evidence

if TYPE_CHECKING:
    from medgent.application.ports.retrieval_port import EvidenceRetrievalPort

logger = logging.getLogger(__name__)


def aggregate_evidence(
    sources: Sequence[EvidenceRetrievalPort],
    query: str,
    max_results_per_source: int = 10,
) -> list[Evidence]:
    """Fetch ``query`` from every source and return deduplicated :class:`Evidence`.

    Each source's ``search`` is called with ``max_results_per_source`` and the
    results are concatenated in source order. Duplicates are removed by exact
    ``identifier`` equality (PMID or URL string match): the first occurrence is
    kept and later ones are dropped, preserving overall order.

    Fault isolation: if a single source raises while searching, it is logged and
    skipped so one flaky source cannot sink the whole fetch — the evidence from
    the sources that did succeed is still returned. A source that legitimately
    matched nothing simply contributes no items (it returns ``[]`` and does not
    raise).
    """
    aggregated: list[Evidence] = []
    seen: set[str] = set()

    for source in sources:
        try:
            results = source.search(query, max_results=max_results_per_source)
        except Exception:
            # One source failing must not abort the others; log and move on.
            logger.warning(
                "evidence source %r failed for query %r; skipping it",
                type(source).__name__,
                query,
                exc_info=True,
            )
            continue

        for evidence in results:
            if evidence.identifier in seen:
                continue
            seen.add(evidence.identifier)
            aggregated.append(evidence)

    return aggregated
