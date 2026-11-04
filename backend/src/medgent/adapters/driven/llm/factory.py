"""LLM provider factory — wiring from settings to a concrete :class:`LLMPort`.

Selects and constructs the adapter named by ``settings.llm_provider``. This is
the single place that knows about the concrete providers, so the rest of the app
depends only on the port.
"""

from __future__ import annotations

from medgent.adapters.driven.llm.gemini_adapter import GeminiAdapter
from medgent.adapters.driven.llm.groq_adapter import GroqAdapter
from medgent.adapters.driven.llm.ollama_adapter import OllamaAdapter
from medgent.application.ports.llm_port import LLMPort
from medgent.config import Settings

_VALID_PROVIDERS = ("ollama", "groq", "gemini")


def build_llm(settings: Settings) -> LLMPort:
    """Build the LLM adapter selected by ``settings.llm_provider``.

    - ``"ollama"`` (the default) returns a working :class:`OllamaAdapter` wired to
      ``settings.ollama_model`` / ``settings.ollama_base_url``; it works offline
      and needs no API key, so the app boots with zero configuration.
    - ``"groq"`` / ``"gemini"`` return their respective stub adapters, which
      construct fine but raise ``NotImplementedError`` on use.
    - any other value raises :class:`ValueError` listing the valid providers.
    """
    provider = settings.llm_provider.lower()

    if provider == "ollama":
        return OllamaAdapter(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
        )
    if provider == "groq":
        return GroqAdapter(api_key=settings.groq_api_key)
    if provider == "gemini":
        return GeminiAdapter(api_key=settings.gemini_api_key)

    valid = ", ".join(_VALID_PROVIDERS)
    raise ValueError(f"Unknown llm_provider {settings.llm_provider!r}. Valid providers: {valid}.")
