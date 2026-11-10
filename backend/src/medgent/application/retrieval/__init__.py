"""Retrieval application logic — composition of evidence sources.

Houses the multi-source aggregation that the ``fetch_evidence`` node leans on:
fan a query out across several :class:`EvidenceRetrievalPort` implementations,
concatenate their results, and deduplicate into a single normalized list.

Dependency rule: this package is application logic. It depends only on the
``EvidenceRetrievalPort`` abstraction and the domain :class:`Evidence` model —
never on a concrete adapter (PubMed, web search, ...). That is the whole point:
it composes ports, so swapping or adding a source changes nothing here.
"""

from medgent.application.retrieval.aggregator import aggregate_evidence

__all__ = ["aggregate_evidence"]
