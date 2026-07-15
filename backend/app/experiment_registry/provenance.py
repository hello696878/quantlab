"""
Provenance helpers: cached Git commit and application version.

Both values are resolved **once** and memoized for the process lifetime, so
recording an experiment never shells out to ``git`` on every request.  Every
lookup is best-effort and local only: it never raises, never touches the
network, and returns ``None`` when the information is unavailable.

Nothing here records absolute local paths, environment variables, usernames, or
secrets — only the short-lived, non-sensitive build identity (commit SHA and the
project ``VERSION`` label).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

# backend/app/experiment_registry/provenance.py -> repo root is parents[3].
_REPO_ROOT = Path(__file__).resolve().parents[3]
_VERSION_FILE = _REPO_ROOT / "VERSION"

# Sentinel distinguishes "not computed yet" from a computed value of ``None``.
_UNSET = object()
_git_commit_cache: Any = _UNSET
_app_version_cache: Any = _UNSET


def _resolve_git_commit() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha or None


def get_git_commit() -> Optional[str]:
    """Return the current commit SHA (memoized, best-effort, local only)."""
    global _git_commit_cache
    if _git_commit_cache is _UNSET:
        _git_commit_cache = _resolve_git_commit()
    return _git_commit_cache


def _resolve_app_version() -> Optional[str]:
    try:
        text = _VERSION_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    return text or None


def get_app_version() -> Optional[str]:
    """Return the project ``VERSION`` label (memoized, best-effort)."""
    global _app_version_cache
    if _app_version_cache is _UNSET:
        _app_version_cache = _resolve_app_version()
    return _app_version_cache


def build_provenance(
    *,
    source: str,
    extra: Optional[Dict[str, Any]] = None,
    include_build: bool = True,
) -> Dict[str, Any]:
    """Assemble a provenance dict for an experiment record.

    ``source`` labels how the record was created (e.g. ``"api"``,
    ``"demo_fixture"``, ``"scenario_studio"``).  ``extra`` is merged in verbatim
    (the caller is responsible for keeping it free of secrets / absolute paths).
    When ``include_build`` is true, the cached git commit and app version are
    added under a ``build`` key.
    """
    provenance: Dict[str, Any] = {"source": source}
    if include_build:
        provenance["build"] = {
            "git_commit": get_git_commit(),
            "app_version": get_app_version(),
        }
    if extra:
        provenance.update(extra)
    return provenance


def reset_caches() -> None:
    """Clear memoized values (test-only; lets a test force re-resolution)."""
    global _git_commit_cache, _app_version_cache
    _git_commit_cache = _UNSET
    _app_version_cache = _UNSET


__all__ = [
    "get_git_commit",
    "get_app_version",
    "build_provenance",
    "reset_caches",
]
