"""Composition helper shared by the driving adapters.

The driving adapters (CLI, FastAPI) are each a *composition root*: the one place
allowed to read :func:`get_settings`, construct the concrete driven adapters
(:class:`OllamaAdapter` via :func:`build_llm`, :class:`PubMedAdapter`,
:class:`WebSearchAdapter`), and wire them into the :class:`ResearchTopicUseCase`.
Both adapters need the *same* wiring, so it lives here once rather than being
duplicated — the CLI and the API both call :func:`build_use_case`.

Keeping it under ``adapters/driving`` (not in ``application``) honors the
dependency rule: this module imports concrete adapters, which the application and
domain layers must never do. A driving adapter importing another driving module
is fine; crucially the API does **not** import the CLI to get this.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from medgent.adapters.driven.llm.factory import build_llm
from medgent.adapters.driven.retrieval.pubmed_adapter import PubMedAdapter
from medgent.adapters.driven.retrieval.web_search_adapter import WebSearchAdapter
from medgent.application.use_cases import ResearchTopicUseCase

if TYPE_CHECKING:
    from medgent.config import Settings


def build_use_case(
    settings: Settings,
    *,
    max_iterations: int = 3,
    **tuning: int,
) -> ResearchTopicUseCase:
    """Build a :class:`ResearchTopicUseCase` wired from ``settings``.

    Constructs the concrete LLM adapter selected by ``settings.llm_provider`` and
    the PubMed + web-search retrieval sources, then injects them into the use case
    alongside ``max_iterations`` and any extra ``tuning`` keyword arguments
    (``max_results_per_source``, ``max_studies_per_iteration``, ``batch_size``, …)
    the caller chooses to forward. Any ``tuning`` key omitted keeps the use case's
    own default, so the defaults stay owned in one place rather than duplicated
    across the driving adapters.
    """
    llm = build_llm(settings)
    pubmed = PubMedAdapter(api_key=settings.ncbi_api_key)
    web = WebSearchAdapter()
    return ResearchTopicUseCase(
        llm,
        [pubmed, web],
        max_iterations=max_iterations,
        **tuning,
    )
