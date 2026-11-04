"""Evidence retrieval port — the abstract contract for evidence sources.

Defines the boundary the research agent uses to pull evidence for a query,
regardless of where it comes from (PubMed structured search today; web search or
embedding-based semantic search later). The ``fetch_evidence`` node depends on
this port, not on any concrete source, so adding a new source is a new driven
adapter and nothing in the core changes.

Dependency rule: this module is a core abstraction. It imports only ``typing``
and the domain :class:`Evidence` model — never ``requests``, an NCBI SDK, or any
concrete adapter. Concrete adapters in ``adapters/driven/retrieval`` implement
this port; the port never imports them.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from medgent.domain.schemas import Evidence


@runtime_checkable
class EvidenceRetrievalPort(Protocol):
    """Structural contract every evidence-source adapter must satisfy.

    Implemented structurally (via :class:`typing.Protocol`): any object exposing
    a compatible ``search`` method is an ``EvidenceRetrievalPort`` without needing
    to inherit from it. ``runtime_checkable`` allows ``isinstance(obj, ...)`` to
    confirm the method exists (it does not check the signature).
    """

    def search(self, query: str, max_results: int = 10) -> list[Evidence]:
        """Return normalized, source-agnostic :class:`Evidence` for ``query``.

        Contract:

        - The result is always a ``list`` of :class:`Evidence` normalized to the
          common domain shape, so callers never branch on the underlying source.
        - An expected "no data" condition (the source matched nothing) returns an
          empty list rather than raising. ``max_results`` is an upper bound, not a
          guarantee; fewer (including zero) may come back.
        - Unexpected failures (network errors, malformed responses from the source)
          may raise. Implementations should not swallow those into an empty list,
          so the caller can tell "no results" apart from "the source is down".
        """
        ...
