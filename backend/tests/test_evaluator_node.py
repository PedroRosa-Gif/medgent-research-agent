"""Tests for the evaluator graph node — pure, offline, no provider SDK.

Uses a ``QueueLLM`` double whose ``generate_structured`` yields canned
:class:`StudyExtraction` objects (one per call, in order) so each study gets a
distinct relevance. The LLM is asked ONLY for the extraction fields; the node
then builds the final :class:`EvaluatedStudy`, setting the ``identifier`` from
the source :class:`Evidence` and computing ``quality_score`` in code. The tests
pin that contract, plus sufficiency by threshold-plus-count, iteration
increment, and skipping a study whose extraction raises.
"""

from __future__ import annotations

from datetime import date

from medgent.application.graph import make_evaluator_node
from medgent.domain.schemas import Evidence, EvidenceSource, StudyExtraction, StudyType
from medgent.domain.scoring import combine_scores, heuristic_score
from medgent.domain.state import initial_state

_LONG_ABSTRACT = "y" * 400


class QueueLLM:
    """``LLMPort`` double returning queued :class:`StudyExtraction` per call.

    Each ``generate_structured`` call pops the next canned extraction from the
    queue. A queued ``RuntimeError`` (rather than an extraction) is raised
    instead, to exercise the node's per-study failure handling.
    """

    def __init__(self, responses: list[StudyExtraction | Exception]) -> None:
        self._responses = list(responses)
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        return f"echo: {prompt}"

    def generate_structured(self, prompt: str, schema: type) -> object:
        self.prompts.append(prompt)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _evidence(identifier: str, *, abstract: str | None = None, year: int | None = None) -> Evidence:
    """Build a minimal PubMed :class:`Evidence`."""
    return Evidence(
        source=EvidenceSource.PUBMED,
        identifier=identifier,
        title=f"title-{identifier}",
        abstract=abstract,
        year=year,
    )


def _extraction(
    *,
    relevance: float,
    study_type: StudyType = StudyType.RCT,
    sample_size: int | None = 100,
    key_finding: str = "a finding",
) -> StudyExtraction:
    """Build a canned LLM-returned :class:`StudyExtraction` (semantic fields only)."""
    return StudyExtraction(
        study_type=study_type,
        sample_size=sample_size,
        key_finding=key_finding,
        relevance_score=relevance,
    )


# --- building the final study ------------------------------------------------


def test_evaluator_sets_identifier_and_computes_quality_score() -> None:
    current_year = date.today().year
    evidence = _evidence("pmid-42", abstract=_LONG_ABSTRACT, year=current_year)
    llm = QueueLLM([_extraction(relevance=0.8)])
    evaluator = make_evaluator_node(llm)

    state = initial_state("metformin safety")
    state["evidence"] = [evidence]
    update = evaluator(state)

    [study] = update["evaluated_studies"]
    # identifier comes from the Evidence (the extraction schema has no identifier).
    assert study.identifier == "pmid-42"
    # quality_score is computed in code from heuristic + relevance.
    expected = combine_scores(heuristic_score(evidence), 0.8, heuristic_weight=0.5)
    assert study.quality_score == expected
    # semantic fields are kept from the LLM.
    assert study.relevance_score == 0.8
    assert study.study_type == StudyType.RCT
    assert study.sample_size == 100


def test_evaluator_prompt_includes_topic_and_study() -> None:
    evidence = _evidence("pmid-1", abstract="abc")
    llm = QueueLLM([_extraction(relevance=0.5)])
    evaluator = make_evaluator_node(llm)

    state = initial_state("SGLT2 inhibitors in heart failure")
    state["evidence"] = [evidence]
    evaluator(state)

    prompt = llm.prompts[0]
    assert "SGLT2 inhibitors in heart failure" in prompt
    assert "title-pmid-1" in prompt
    assert "abc" in prompt


# --- sufficiency -------------------------------------------------------------


def test_evaluator_sufficient_when_enough_studies_pass_threshold() -> None:
    current_year = date.today().year
    evidence = [
        _evidence("a", abstract=_LONG_ABSTRACT, year=current_year),
        _evidence("b", abstract=_LONG_ABSTRACT, year=current_year),
        _evidence("c", abstract=_LONG_ABSTRACT, year=current_year),
    ]
    # Each heuristic is 1.0; relevance 1.0 => quality 1.0 >= 0.6 for all three.
    llm = QueueLLM([_extraction(relevance=1.0) for _ in evidence])
    evaluator = make_evaluator_node(llm, min_studies=3, quality_threshold=0.6)

    state = initial_state("topic")
    state["evidence"] = evidence
    update = evaluator(state)

    assert len(update["evaluated_studies"]) == 3
    assert update["is_sufficient"] is True
    assert update["iteration"] == 1


def test_evaluator_insufficient_when_too_few_pass_threshold() -> None:
    current_year = date.today().year
    evidence = [
        _evidence("a", abstract=_LONG_ABSTRACT, year=current_year),
        _evidence("b", abstract=_LONG_ABSTRACT, year=current_year),
        _evidence("c", abstract=_LONG_ABSTRACT, year=current_year),
    ]
    # Only the first two are relevant enough to clear the threshold.
    llm = QueueLLM(
        [
            _extraction(relevance=1.0),
            _extraction(relevance=1.0),
            _extraction(relevance=0.0),
        ]
    )
    evaluator = make_evaluator_node(llm, min_studies=3, quality_threshold=0.6)

    state = initial_state("topic")
    state["evidence"] = evidence
    update = evaluator(state)

    passing = sum(1 for s in update["evaluated_studies"] if s.quality_score >= 0.6)
    assert passing == 2
    assert update["is_sufficient"] is False
    assert update["iteration"] == 1


def test_evaluator_increments_iteration_from_current() -> None:
    evidence = _evidence("a", abstract=_LONG_ABSTRACT, year=date.today().year)
    llm = QueueLLM([_extraction(relevance=1.0)])
    evaluator = make_evaluator_node(llm)

    state = initial_state("topic")
    state["evidence"] = [evidence]
    state["iteration"] = 2
    update = evaluator(state)

    assert update["iteration"] == 3


# --- empty evidence ----------------------------------------------------------


def test_evaluator_empty_evidence_returns_empty_but_increments() -> None:
    evaluator = make_evaluator_node(QueueLLM([]))

    state = initial_state("topic")  # evidence is [] from initial_state
    update = evaluator(state)

    assert update == {
        "evaluated_studies": [],
        "is_sufficient": False,
        "iteration": 1,
    }


def test_evaluator_missing_evidence_key_does_not_error() -> None:
    evaluator = make_evaluator_node(QueueLLM([]))

    # AgentState is total=False; a state without ``evidence`` must not raise.
    update = evaluator({"topic": "topic"})

    assert update["evaluated_studies"] == []
    assert update["is_sufficient"] is False
    assert update["iteration"] == 1


# --- per-study failure -------------------------------------------------------


def test_evaluator_skips_study_whose_extraction_raises() -> None:
    current_year = date.today().year
    evidence = [
        _evidence("good-1", abstract=_LONG_ABSTRACT, year=current_year),
        _evidence("bad", abstract=_LONG_ABSTRACT, year=current_year),
        _evidence("good-2", abstract=_LONG_ABSTRACT, year=current_year),
    ]
    # The middle call raises; the other two extract normally.
    llm = QueueLLM(
        [
            _extraction(relevance=1.0),
            RuntimeError("model blew up"),
            _extraction(relevance=1.0),
        ]
    )
    evaluator = make_evaluator_node(llm)

    state = initial_state("topic")
    state["evidence"] = evidence
    update = evaluator(state)

    identifiers = [s.identifier for s in update["evaluated_studies"]]
    assert identifiers == ["good-1", "good-2"]
    assert update["iteration"] == 1
