"""LLM port — the abstract contract for language-model providers.

Defines the boundary the research agent uses to talk to any chat/completions
model (Ollama, Groq, Gemini, ...). The planner and evaluator nodes need
structured output constrained to a Pydantic schema; the synthesizer needs
free-form text. Both needs are expressed here as a single structural contract.

Dependency rule: this module is a core abstraction. It imports only ``typing``
and ``pydantic.BaseModel`` — never langchain, ollama, or any concrete SDK.
Concrete adapters in ``adapters/driven/llm`` implement this port; the port never
imports them.
"""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

# A Pydantic model type the structured-output method is parametrized over, so
# ``generate_structured(prompt, QueryPlan)`` is typed as returning ``QueryPlan``.
T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class LLMPort(Protocol):
    """Structural contract every LLM provider adapter must satisfy.

    Implemented structurally (via :class:`typing.Protocol`): any object exposing
    ``generate`` and ``generate_structured`` with compatible signatures is an
    ``LLMPort``, without needing to inherit from it. ``runtime_checkable`` allows
    ``isinstance(obj, LLMPort)`` to confirm the methods exist (it does not check
    signatures).
    """

    def generate(self, prompt: str) -> str:
        """Return the model's free-form text completion for ``prompt``.

        Used by the synthesizer node, which needs unconstrained prose rather than
        a schema-validated object.
        """
        ...

    def generate_structured(self, prompt: str, schema: type[T]) -> T:
        """Return a validated instance of ``schema`` for ``prompt``.

        Constrains the model's output to the given Pydantic model and returns the
        parsed, validated instance. Used by the planner (``QueryPlan``) and the
        evaluator (``EvaluatedStudy``). Implementations should raise if the model
        output cannot be coerced into ``schema``.
        """
        ...
