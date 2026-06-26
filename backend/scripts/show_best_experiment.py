"""Thin wrapper for ``app.research_cli.cli best`` (runnable directly or via -m)."""

import sys
from pathlib import Path

_BACKEND_ROOT = str(Path(__file__).resolve().parent.parent)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.research_cli.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["best", *sys.argv[1:]]))
