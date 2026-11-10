"""Tests for the CLI driving adapter — fully offline, no adapters/network/LLM.

The composition-root pieces (``build_llm``, ``PubMedAdapter``,
``WebSearchAdapter``, ``ResearchTopicUseCase``) are monkeypatched with fakes so
``main`` never constructs a real adapter or touches the network. The tests cover
the slugify helper's edge cases, argument parsing, that ``main`` writes a report
to a tmp dir (via ``--output-dir`` + ``tmp_path``) and prints it, that
``--no-save`` skips the file, and that ``--help`` parses without building adapters.
"""

from __future__ import annotations

import pytest

from medgent.adapters.driving import cli
from medgent.application.graph.nodes import _DISCLAIMER

_FAKE_REPORT = "## Summary\n\nFake synthesized report." + _DISCLAIMER


class FakeUseCase:
    """Stand-in for ResearchTopicUseCase: canned stream, no graph/LLM."""

    last_init: dict | None = None

    def __init__(self, llm: object, sources: object, **kwargs: object) -> None:
        FakeUseCase.last_init = {"llm": llm, "sources": sources, **kwargs}

    def stream(self, topic: str, **kwargs: object):
        yield "planner", {"queries": ["q1", "q2"]}
        yield "fetch_evidence", {"evidence": [object(), object(), object()]}
        yield (
            "evaluator",
            {
                "evaluated_studies": [object()],
                "iteration": 1,
                "is_sufficient": True,
            },
        )
        yield "synthesizer", {"final_report": _FAKE_REPORT}


@pytest.fixture
def patched_cli(monkeypatch: pytest.MonkeyPatch) -> type[FakeUseCase]:
    """Patch the CLI's composition root to use fakes only."""
    FakeUseCase.last_init = None
    monkeypatch.setattr(cli, "build_llm", lambda settings: object())
    monkeypatch.setattr(cli, "PubMedAdapter", lambda **kwargs: object())
    monkeypatch.setattr(cli, "WebSearchAdapter", lambda **kwargs: object())
    monkeypatch.setattr(cli, "ResearchTopicUseCase", FakeUseCase)
    return FakeUseCase


# --- slugify -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("topic", "expected"),
    [
        ("Metformin Efficacy", "metformin-efficacy"),
        ("SGLT2 inhibitors in heart failure!", "sglt2-inhibitors-in-heart-failure"),
        ("  leading/trailing  ", "leading-trailing"),
        ("multiple---dashes &&& here", "multiple-dashes-here"),
        ("", "report"),
        ("!!!", "report"),
        ("ALL CAPS", "all-caps"),
    ],
)
def test_slugify_edge_cases(topic: str, expected: str) -> None:
    assert cli.slugify(topic) == expected


# --- argument parsing --------------------------------------------------------


def test_parser_defaults() -> None:
    args = cli.build_parser().parse_args(["some topic"])
    assert args.topic == "some topic"
    assert args.max_iterations == 3
    assert args.provider is None
    assert args.model is None
    assert args.no_save is False
    assert args.output_dir == "reports"


def test_parser_all_flags() -> None:
    args = cli.build_parser().parse_args(
        [
            "topic",
            "--max-iterations",
            "2",
            "--provider",
            "groq",
            "--model",
            "llama3.2:3b",
            "--no-save",
            "--output-dir",
            "out",
        ]
    )
    assert args.max_iterations == 2
    assert args.provider == "groq"
    assert args.model == "llama3.2:3b"
    assert args.no_save is True
    assert args.output_dir == "out"


def test_help_exits_zero_without_building_adapters(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # --help must work with no settings/adapter construction at all.
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "usage" in out.lower()
    assert "topic" in out


# --- main run ----------------------------------------------------------------


def test_main_writes_report_and_prints_it(
    patched_cli: type[FakeUseCase],
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_dir = tmp_path / "reports"
    code = cli.main(["Metformin Efficacy", "--output-dir", str(output_dir)])

    assert code == 0
    report_file = output_dir / "metformin-efficacy.md"
    assert report_file.exists()
    assert report_file.read_text(encoding="utf-8") == _FAKE_REPORT

    out = capsys.readouterr().out
    # Progress lines and the final report are both printed.
    assert "planner" in out
    assert "synthesizer" in out
    assert "Fake synthesized report." in out
    assert str(report_file) in out


def test_main_no_save_skips_writing(
    patched_cli: type[FakeUseCase],
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_dir = tmp_path / "reports"
    code = cli.main(["Metformin Efficacy", "--no-save", "--output-dir", str(output_dir)])

    assert code == 0
    assert not output_dir.exists()
    out = capsys.readouterr().out
    assert "Fake synthesized report." in out
    assert "saved to" not in out.lower()


def test_main_forwards_max_iterations_to_use_case(
    patched_cli: type[FakeUseCase],
    tmp_path,
) -> None:
    cli.main(
        [
            "topic",
            "--max-iterations",
            "5",
            "--no-save",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert FakeUseCase.last_init is not None
    assert FakeUseCase.last_init["max_iterations"] == 5
