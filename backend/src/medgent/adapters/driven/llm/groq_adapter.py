"""Groq LLM adapter — an explicit stub behind :class:`LLMPort`.

Planned provider, not yet implemented. It exists so the factory and the rest of
the app can reference it behind the same port, but both generation methods raise
``NotImplementedError``. No ``langchain-groq`` dependency is pulled in yet.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_NOT_IMPLEMENTED = "Groq provider not yet implemented (planned). Use LLM_PROVIDER=ollama."


class GroqAdapter:
    """Stub ``LLMPort`` for Groq. Construction is allowed; generation is not."""

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self._model = model
        self._api_key = api_key

    def generate(self, prompt: str) -> str:
        """Not implemented — raises :class:`NotImplementedError`."""
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def generate_structured(self, prompt: str, schema: type[T]) -> T:
        """Not implemented — raises :class:`NotImplementedError`."""
        raise NotImplementedError(_NOT_IMPLEMENTED)
