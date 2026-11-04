"""Tests for the LLM provider factory.

Asserts the factory maps ``llm_provider`` to the right adapter and rejects
unknown values — all offline. The Ollama case constructs the adapter (which must
not perform I/O) but never calls a generation method.
"""

import pytest

from medgent.adapters.driven.llm.factory import build_llm
from medgent.adapters.driven.llm.gemini_adapter import GeminiAdapter
from medgent.adapters.driven.llm.groq_adapter import GroqAdapter
from medgent.adapters.driven.llm.ollama_adapter import OllamaAdapter
from medgent.config import Settings


def test_factory_builds_ollama_adapter() -> None:
    settings = Settings(
        llm_provider="ollama",
        ollama_model="test-model",
        ollama_base_url="http://example:11434",
    )
    adapter = build_llm(settings)
    assert isinstance(adapter, OllamaAdapter)


def test_factory_passes_ollama_settings_through() -> None:
    settings = Settings(
        llm_provider="ollama",
        ollama_model="test-model",
        ollama_base_url="http://example:11434",
    )
    adapter = build_llm(settings)
    # Construction wires the settings without any network call.
    assert adapter._model == "test-model"
    assert adapter._base_url == "http://example:11434"


def test_factory_builds_groq_stub() -> None:
    settings = Settings(llm_provider="groq")
    assert isinstance(build_llm(settings), GroqAdapter)


def test_factory_builds_gemini_stub() -> None:
    settings = Settings(llm_provider="gemini")
    assert isinstance(build_llm(settings), GeminiAdapter)


def test_factory_is_case_insensitive() -> None:
    settings = Settings(llm_provider="OLLAMA")
    assert isinstance(build_llm(settings), OllamaAdapter)


def test_factory_rejects_unknown_provider() -> None:
    settings = Settings(llm_provider="not-a-provider")
    with pytest.raises(ValueError, match="ollama, groq, gemini"):
        build_llm(settings)
