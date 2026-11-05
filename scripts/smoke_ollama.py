#!/usr/bin/env python3
"""Manual smoke test for the Ollama LLM stack. NOT a pytest test; NOT run in CI.

This is a hands-on sanity check that the containerized Ollama server is up and the
model is pulled. It builds an ``OllamaAdapter`` straight from ``Settings`` and
exercises both the free-form ``generate`` and the structured ``generate_structured``
paths (using the domain ``QueryPlan`` schema).

Prerequisites
-------------
1. The Ollama container is running and the model is pulled::

       docker compose up -d                 # from the repo root
       docker compose logs -f ollama-init   # watch the model download finish

2. The backend deps are installed (``uv sync`` in ``backend/``).

How to run
----------
The ``medgent`` package lives in ``backend/src`` and is reachable through the
backend's virtualenv. Run this from the ``backend/`` directory so ``uv`` uses that
environment (the script adds ``backend/src`` to ``sys.path`` itself, so no install
or ``PYTHONPATH`` fiddling is needed)::

    cd backend
    uv run python ../scripts/smoke_ollama.py

To point at a different model/host, set the same env vars the app reads
(``OLLAMA_MODEL`` for compose; ``OLLAMA_BASE_URL`` / ``OLLAMA_MODEL`` for the app),
e.g.::

    cd backend
    OLLAMA_MODEL=llama3.2:3b uv run python ../scripts/smoke_ollama.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the `medgent` package importable without installing it: it lives in
# backend/src, two levels up from this file (scripts/ -> repo root -> backend/src).
_BACKEND_SRC = Path(__file__).resolve().parent.parent / "backend" / "src"
if _BACKEND_SRC.is_dir():
    sys.path.insert(0, str(_BACKEND_SRC))

from medgent.adapters.driven.llm.ollama_adapter import OllamaAdapter  # noqa: E402
from medgent.config import get_settings  # noqa: E402
from medgent.domain.schemas import QueryPlan  # noqa: E402


def main() -> int:
    """Run the smoke test, returning a process exit code (0 = success)."""
    settings = get_settings()
    print(f"→ Using model '{settings.ollama_model}' at {settings.ollama_base_url}\n")

    adapter = OllamaAdapter(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
    )

    try:
        print("[1/2] generate() — expecting roughly 'pong':")
        reply = adapter.generate("Reply with the single word: pong")
        print(f"      {reply!r}\n")

        print("[2/2] generate_structured() — planning queries for a tiny topic:")
        plan = adapter.generate_structured(
            "Create 2 to 3 PubMed search queries to research the efficacy of "
            "metformin for type 2 diabetes. Respond using the required schema.",
            QueryPlan,
        )
        print(f"      queries: {plan.queries}")
        if plan.rationale:
            print(f"      rationale: {plan.rationale}")
    except Exception as exc:  # noqa: BLE001 - friendly top-level message for a manual tool
        print(
            "\n✗ Could not reach Ollama or run the model.\n"
            f"  Error: {type(exc).__name__}: {exc}\n\n"
            "  Is the server up and the model pulled? Try:\n"
            "    docker compose up -d\n"
            "    docker compose logs -f ollama-init   # wait for the pull to finish\n"
            f"  Expected server at: {settings.ollama_base_url}",
            file=sys.stderr,
        )
        return 1

    print("\n✓ Ollama smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
