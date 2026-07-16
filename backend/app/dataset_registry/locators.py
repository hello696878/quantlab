"""
Storage-locator policy: identify data without leaking the user's filesystem.

A locator is a small logical URI, never an absolute path.  Accepted schemes:

* ``fixture://<repo-relative-ish path>``  — tracked deterministic fixtures
* ``generated://<logical path>``          — locally generated datasets
* ``local-file://<basename>``             — a user's local file, basename only
* ``provider://<provider>/<series>``      — an optional provider identifier

These are logical identifiers, **not network-accessible URLs**.  Validation
rejects absolute Windows/POSIX/UNC paths, ``..`` traversal, embedded
credentials, query strings, whitespace/control characters, and drive letters —
so no locator can ever carry ``C:\\Users\\...`` or a token.
"""

from __future__ import annotations

import re
from typing import Tuple

VALID_LOCATOR_TYPES = ("fixture", "generated", "local_file", "provider")

_SCHEME_BY_TYPE = {
    "fixture": "fixture",
    "generated": "generated",
    "local_file": "local-file",
    "provider": "provider",
}

_LOCATOR_RE = re.compile(r"^(?P<scheme>[a-z][a-z0-9-]*)://(?P<rest>.+)$")

# Anything that smells like an absolute/UNC/drive path or traversal.
_ABSOLUTE_WIN = re.compile(r"^[A-Za-z]:[\\/]")
_UNC = re.compile(r"^[\\/]{2}")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")

MAX_LOCATOR_LEN = 300


class LocatorError(ValueError):
    """Raised when a storage locator violates the privacy/safety policy."""


def validate_locator(locator: str) -> Tuple[str, str]:
    """Validate a logical locator string; return ``(locator_type, locator)``.

    Raises :class:`LocatorError` with a specific reason on any violation.
    """
    if not isinstance(locator, str) or not locator.strip():
        raise LocatorError("storage locator must be a non-empty string")
    locator = locator.strip()
    if len(locator) > MAX_LOCATOR_LEN:
        raise LocatorError(f"storage locator exceeds {MAX_LOCATOR_LEN} characters")
    if _CONTROL.search(locator):
        raise LocatorError("storage locator must not contain control characters")

    m = _LOCATOR_RE.match(locator)
    if not m:
        raise LocatorError(
            "storage locator must use a logical scheme like fixture://, "
            "generated://, local-file://, or provider://"
        )
    scheme, rest = m.group("scheme"), m.group("rest")

    scheme_to_type = {v: k for k, v in _SCHEME_BY_TYPE.items()}
    if scheme not in scheme_to_type:
        raise LocatorError(
            f"unknown locator scheme '{scheme}://'; allowed: "
            + ", ".join(f"{s}://" for s in scheme_to_type)
        )
    locator_type = scheme_to_type[scheme]

    if "@" in rest:
        raise LocatorError("storage locator must not embed credentials ('@')")
    if "?" in rest or "#" in rest:
        raise LocatorError("storage locator must not carry a query string or fragment")
    if _ABSOLUTE_WIN.match(rest) or _UNC.match(rest) or rest.startswith("/") or rest.startswith("\\"):
        raise LocatorError("storage locator must not contain an absolute or UNC path")
    if ".." in re.split(r"[\\/]", rest):
        raise LocatorError("storage locator must not contain '..' traversal")
    if "\\" in rest:
        raise LocatorError("storage locator must use forward slashes only")
    if any(ch.isspace() for ch in rest):
        raise LocatorError("storage locator must not contain whitespace")

    if locator_type == "local_file" and "/" in rest:
        raise LocatorError(
            "local-file:// locators must carry a basename only (no directories)"
        )
    return locator_type, locator


def sanitize_basename(filename: str) -> str:
    """Reduce any user-supplied filename to a safe basename for a locator."""
    base = re.split(r"[\\/]", filename.strip())[-1]
    base = _CONTROL.sub("", base).replace("?", "").replace("#", "").replace("@", "")
    return base


__all__ = [
    "VALID_LOCATOR_TYPES",
    "MAX_LOCATOR_LEN",
    "LocatorError",
    "validate_locator",
    "sanitize_basename",
]
