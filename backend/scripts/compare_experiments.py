"""Thin wrapper for ``python -m app.research_cli.cli compare``.

Run from the ``backend/`` directory (or with ``PYTHONPATH=backend``).
"""

import sys

from app.research_cli.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["compare", *sys.argv[1:]]))
