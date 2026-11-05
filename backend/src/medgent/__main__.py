"""Package entry point so ``python -m medgent "topic"`` runs the CLI.

Delegates straight to the CLI driving adapter's :func:`main`, propagating its
exit code. Kept trivial on purpose — the real work (argument parsing, composition
root, streaming) lives in :mod:`medgent.adapters.driving.cli`.
"""

from __future__ import annotations

from medgent.adapters.driving.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
