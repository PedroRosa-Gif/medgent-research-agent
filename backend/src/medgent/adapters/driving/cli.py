"""Command-line driving adapter — the terminal entry point for a research run.

This is a *driving* adapter and the composition root for the CLI: it is the one
place that reads :func:`get_settings`, constructs the concrete adapters
(:class:`OllamaAdapter` via :func:`build_llm`, :class:`PubMedAdapter`,
:class:`WebSearchAdapter`), wires them into :class:`ResearchTopicUseCase`, and
runs it. Nothing in ``application`` or ``domain`` imports from here.

Usage::

    python -m medgent "efficacy of metformin for type 2 diabetes"
    python -m medgent "SGLT2 inhibitors in heart failure" --max-iterations 2
    python -m medgent "topic" --provider ollama --model llama3.2:3b --no-save

It streams node-by-node progress to the terminal as the graph runs, then prints
the final report and (unless ``--no-save``) writes it to
``<output-dir>/<slug>.md``.

Dependency rule: as a driving adapter it may import concrete adapters and the
use case. It stays framework-light — stdlib ``argparse`` only, no web framework.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from medgent.adapters.driven.llm.factory import build_llm
from medgent.adapters.driven.retrieval.pubmed_adapter import PubMedAdapter
from medgent.adapters.driven.retrieval.web_search_adapter import WebSearchAdapter
from medgent.application.use_cases import ResearchTopicUseCase
from medgent.config import get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

_DEFAULT_OUTPUT_DIR = "reports"
_DEFAULT_MAX_ITERATIONS = 3

# Friendly guidance shown when the local model/server cannot be reached, instead
# of a raw traceback for the common "Ollama isn't up" case.
_CONNECTION_HINT = (
    "Could not reach the LLM provider. If you're using the default local Ollama, "
    "make sure it's running and the model is pulled:\n"
    "    docker compose up -d\n"
    "    docker compose logs -f ollama-init   # wait for the model pull to finish\n"
    "See docs/running-locally.md for details."
)


def slugify(topic: str) -> str:
    """Turn a topic into a filesystem-friendly slug for the report filename.

    Lowercases, replaces every run of non-alphanumeric characters with a single
    dash, and trims leading/trailing dashes. Falls back to ``"report"`` when the
    topic has no usable characters (e.g. empty or all punctuation), so a filename
    is always produced.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return slug or "report"


def build_parser() -> argparse.ArgumentParser:
    """Build the ``argparse`` parser for the CLI.

    Kept separate from :func:`main` so argument parsing (and ``--help``) never
    touches settings or constructs an adapter — running ``python -m medgent --help``
    works with no Ollama server and no configuration.
    """
    parser = argparse.ArgumentParser(
        prog="medgent",
        description="Research a clinical topic with the MedGent self-correcting agent.",
    )
    parser.add_argument("topic", help="The clinical research topic to investigate.")
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=_DEFAULT_MAX_ITERATIONS,
        help="Maximum self-correction loop iterations (default: %(default)s).",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help="Override the LLM provider (e.g. ollama, groq, gemini).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the Ollama model (e.g. llama3.2:3b).",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=None,
        help="Max results fetched per source per query (default: 8).",
    )
    parser.add_argument(
        "--max-studies",
        type=int,
        default=None,
        help="Max studies evaluated per iteration (default: 12).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Studies evaluated per LLM call, with one-at-a-time fallback (default: 3).",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Print the report but do not write it to a file.",
    )
    parser.add_argument(
        "--output-dir",
        default=_DEFAULT_OUTPUT_DIR,
        help="Directory to write the report into (default: %(default)s).",
    )
    return parser


def _format_progress(node: str, update: dict) -> str:
    """Render one ``(node, update)`` step into a concise human-readable line.

    Derives the message from the update's keys so each node reports what it
    produced (queries planned, papers fetched, evaluator verdict, report ready).
    Unknown nodes fall back to listing the keys they changed.
    """
    if node == "planner":
        count = len(update.get("queries", []))
        return f"🧠 planner → {count} queries"
    if node == "refine_queries":
        count = len(update.get("queries", []))
        return f"🔁 refine_queries → {count} new queries"
    if node == "fetch_evidence":
        count = len(update.get("evidence", []))
        return f"🔎 fetch_evidence → {count} papers"
    if node == "evaluator":
        studies = len(update.get("evaluated_studies", []))
        iteration = update.get("iteration", "?")
        sufficient = update.get("is_sufficient", False)
        return f"⚖️  evaluator → iteration {iteration}, {studies} studies, sufficient={sufficient}"
    if node == "synthesizer":
        return "✍️  synthesizer → report ready"
    changed = ", ".join(update.keys())
    return f"• {node} → {changed}"


def _write_report(report: str, output_dir: str, topic: str) -> Path:
    """Write ``report`` to ``<output_dir>/<slug>.md``, creating the dir if needed."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{slugify(topic)}.md"
    path.write_text(report, encoding="utf-8")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code (0 = success).

    Parses args first (so ``--help`` and bad arguments never build an adapter),
    then composes the concrete adapters, streams progress, and prints/saves the
    report. The common "provider unreachable" failure is caught and reported as a
    friendly hint (exit code 1) rather than a raw traceback.
    """
    args = build_parser().parse_args(argv)

    settings = get_settings()
    if args.provider:
        settings = settings.model_copy(update={"llm_provider": args.provider})
    if args.model:
        settings = settings.model_copy(update={"ollama_model": args.model})

    llm = build_llm(settings)
    pubmed = PubMedAdapter(api_key=settings.ncbi_api_key)
    web = WebSearchAdapter()
    # Forward the optional tuning flags only when the user set them, so the
    # use case keeps owning the defaults rather than duplicating them here.
    tuning: dict[str, int] = {}
    if args.max_papers is not None:
        tuning["max_results_per_source"] = args.max_papers
    if args.max_studies is not None:
        tuning["max_studies_per_iteration"] = args.max_studies
    if args.batch_size is not None:
        tuning["batch_size"] = args.batch_size
    use_case = ResearchTopicUseCase(
        llm,
        [pubmed, web],
        max_iterations=args.max_iterations,
        **tuning,
    )

    print(f"Researching: {args.topic}\n")
    final_report: str | None = None
    try:
        for node, update in use_case.stream(args.topic):
            print(_format_progress(node, update))
            if node == "synthesizer":
                final_report = update.get("final_report")
    except ConnectionError as exc:
        print(f"\n✗ {_CONNECTION_HINT}\n  ({type(exc).__name__}: {exc})", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - friendly top-level message for the CLI
        print(
            f"\n✗ The research run failed: {type(exc).__name__}: {exc}\n"
            "  See docs/running-locally.md for troubleshooting.",
            file=sys.stderr,
        )
        return 1

    if not final_report:
        print("\n✗ No report was produced.", file=sys.stderr)
        return 1

    print("\n" + "=" * 72)
    print(final_report)
    print("=" * 72)

    if not args.no_save:
        path = _write_report(final_report, args.output_dir, args.topic)
        print(f"\n💾 Report saved to {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
