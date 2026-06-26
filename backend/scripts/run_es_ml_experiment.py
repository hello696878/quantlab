"""Thin wrapper for ``python -m app.research_cli.cli run``.

Run from the ``backend/`` directory (or with ``PYTHONPATH=backend``) so ``app``
is importable.
"""

import sys

from app.research_cli.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["run", *sys.argv[1:]]))
