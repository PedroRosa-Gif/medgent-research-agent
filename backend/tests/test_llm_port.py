"""Tests for the LLM port contract.

Proves the contract end-to-end with a ``FakeLLM`` test double — no provider SDK,
no network, no Ollama required.
"""

import pytest

from medgent.adapters.driven.llm.gemini_adapter import GeminiAdapter
from medgent.adapters.driven.llm.groq_adapter import GroqAdapter
from medgent.application.ports.llm_port import LLMPort
from medgent.domain.schemas import QueryPlan


class FakeLLM:
    """In-memory ``LLMPort`` double returning canned, schema-valid output."""

    def generate(self, prompt: str) -> str:
        return f"echo: {prompt}"

    def generate_structured(self, prompt: str, schema: type) -> object:
        return schema(queries=[prompt], rationale="fake plan")


def test_fake_llm_satisfies_port_structurally() -> None:
    fake = FakeLLM()
    assert isinstance(fake, LLMPort)


def test_fake_llm_generate_returns_text() -> None:
    fake = FakeLLM()
    assert fake.generate("hello") == "echo: hello"


def test_fake_llm_generate_structured_returns_validated_model() -> None:
    fake = FakeLLM()
    plan = fake.generate_structured("metformin safety", QueryPlan)
    assert isinstance(plan, QueryPlan)
    assert plan.queries == ["metformin safety"]
    assert plan.rationale == "fake plan"


def test_stub_adapters_report_port_shape() -> None:
    # Stubs expose the methods, so they satisfy the structural port even though
    # calling them raises.
    assert isinstance(GroqAdapter(), LLMPort)
    assert isinstance(GeminiAdapter(), LLMPort)


def test_groq_stub_raises_not_implemented() -> None:
    adapter = GroqAdapter()
    with pytest.raises(NotImplementedError):
        adapter.generate("anything")
    with pytest.raises(NotImplementedError):
        adapter.generate_structured("anything", QueryPlan)


def test_gemini_stub_raises_not_implemented() -> None:
    adapter = GeminiAdapter()
    with pytest.raises(NotImplementedError):
        adapter.generate("anything")
    with pytest.raises(NotImplementedError):
        adapter.generate_structured("anything", QueryPlan)
