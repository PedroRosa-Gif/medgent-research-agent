"""Ollama LLM adapter — a real :class:`LLMPort` backed by LangChain.

Wraps ``langchain_ollama.ChatOllama`` so the agent gets ``with_structured_output``
(for the planner/evaluator) and smooth LangGraph integration for free. The
langchain dependency is imported lazily inside methods/constructor so that merely
importing this module never hard-fails when the optional package is absent and
never performs network I/O at import time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from langchain_ollama import ChatOllama

T = TypeVar("T", bound=BaseModel)

_INSTALL_HINT = (
    "langchain-ollama is required for the Ollama provider. "
    "Install it with `uv add langchain-ollama` (or `pip install langchain-ollama`)."
)


def _import_chat_ollama() -> type[ChatOllama]:
    """Import ``ChatOllama`` lazily, raising a clear hint if the dep is missing."""
    try:
        from langchain_ollama import ChatOllama
    except ImportError as exc:  # pragma: no cover - exercised only without the dep
        raise ImportError(_INSTALL_HINT) from exc
    return ChatOllama


class OllamaAdapter:
    """``LLMPort`` implementation talking to a local/containerized Ollama server.

    The ``ChatOllama`` client is constructed eagerly from ``model`` and
    ``base_url`` but performs no network call until a generation method runs, so
    constructing an adapter is cheap and offline-safe.
    """

    def __init__(self, model: str, base_url: str) -> None:
        chat_ollama = _import_chat_ollama()
        self._model = model
        self._base_url = base_url
        self._client: Any = chat_ollama(model=model, base_url=base_url)

    def generate(self, prompt: str) -> str:
        """Return the model's free-form text completion for ``prompt``."""
        response = self._client.invoke(prompt)
        content = getattr(response, "content", response)
        return content if isinstance(content, str) else str(content)

    def generate_structured(self, prompt: str, schema: type[T]) -> T:
        """Return a validated ``schema`` instance via ``with_structured_output``."""
        structured = self._client.with_structured_output(schema)
        return structured.invoke(prompt)
