"""Tests for the synthesizer graph node — pure, offline, no provider SDK.

Uses a ``SpyLLM`` double whose ``generate`` returns canned prose and records the
prompt it received, so the tests can prove: the node returns
``{"final_report": ...}``; the fixed medical disclaimer is appended in code (it
appears even when the fake prose omits it); an empty ``evaluated_studies`` yields
an honest "no sufficient evidence" report that still carries the disclaimer; and
the study identifiers are interpolated into the synthesizer prompt.
"""

from __future__ import annotations

from medgent.application.graph import make_synthesizer_node
from medgent.application.graph.nodes import _DISCLAIMER
from medgent.domain.schemas import EvaluatedStudy, StudyType
from medgent.domain.state import initial_state


class SpyLLM:
    """``LLMPort`` double: canned ``generate`` prose + recorded prompts."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.generate_prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.generate_prompts.append(prompt)
        return self._response

    def generate_structured(self, prompt: str, schema: type) -> object:
        raise AssertionError("synthesizer must use free-form generate(), not structured")


def _study(identifier: str, *, key_finding: str = "a finding") -> EvaluatedStudy:
    return EvaluatedStudy(
        identifier=identifier,
        study_type=StudyType.RCT,
        sample_size=120,
        key_finding=key_finding,
        relevance_score=0.9,
        quality_score=0.8,
    )


def test_synthesizer_returns_final_report_with_llm_prose() -> None:
    llm = SpyLLM("## Summary\n\nMetformin lowers HbA1c [pmid-1].")
    synthesizer = make_synthesizer_node(llm)

    state = initial_state("metformin efficacy")
    state["evaluated_studies"] = [_study("pmid-1")]
    update = synthesizer(state)

    assert set(update.keys()) == {"final_report"}
    assert update["final_report"].startswith("## Summary")
    assert "Metformin lowers HbA1c [pmid-1]." in update["final_report"]


def test_synthesizer_appends_disclaimer_even_when_llm_omits_it() -> None:
    # The fake prose deliberately contains no disclaimer; the node must add it.
    llm = SpyLLM("Some report body with no disclaimer at all.")
    synthesizer = make_synthesizer_node(llm)

    state = initial_state("topic")
    state["evaluated_studies"] = [_study("pmid-1")]
    update = synthesizer(state)

    assert _DISCLAIMER in update["final_report"]
    assert update["final_report"].endswith(_DISCLAIMER)
    assert "does **not** provide medical" in update["final_report"]


def test_synthesizer_passes_study_identifiers_into_prompt() -> None:
    llm = SpyLLM("report")
    synthesizer = make_synthesizer_node(llm)

    state = initial_state("SGLT2 inhibitors in heart failure")
    state["evaluated_studies"] = [
        _study("pmid-111", key_finding="reduces hospitalization"),
        _study("https://example.org/a", key_finding="improves outcomes"),
    ]
    synthesizer(state)

    [prompt] = llm.generate_prompts
    assert "SGLT2 inhibitors in heart failure" in prompt
    assert "pmid-111" in prompt
    assert "https://example.org/a" in prompt
    # The key findings are carried into the prompt context too.
    assert "reduces hospitalization" in prompt
    assert "improves outcomes" in prompt


def test_synthesizer_empty_studies_produces_honest_report_with_disclaimer() -> None:
    llm = SpyLLM("this prose must NOT be used")
    synthesizer = make_synthesizer_node(llm)

    state = initial_state("obscure topic")  # evaluated_studies is [] from initial_state
    update = synthesizer(state)

    report = update["final_report"]
    # The LLM is not consulted when there is nothing to synthesize.
    assert llm.generate_prompts == []
    assert "this prose must NOT be used" not in report
    assert "No sufficient evidence was found" in report
    assert "obscure topic" in report
    # The disclaimer is appended to the no-evidence report as well.
    assert _DISCLAIMER in report
