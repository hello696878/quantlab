#!/usr/bin/env python3
"""Verify the release SHA-256 checksum manifest — read-only integrity check.

Usage:
    python scripts/verify_release_checksums.py docs/RELEASE_CHECKSUMS_v4.64.sha256
    python scripts/verify_release_checksums.py <manifest> --base-dir <repo root>

Manifest format (sha256sum-compatible): one entry per line —
``<64 hex chars>  <repository-relative path>`` (an optional ``*`` binary
marker before the path is accepted). Blank lines and ``#`` comments are
ignored.

Safety properties:
* Read-only — never modifies, deletes, or downloads anything.
* Paths must be repository-relative with forward slashes; absolute paths,
  drive letters, and ``..`` traversal are rejected (exit 2).
* Exit codes: 0 = all files verified · 1 = any missing file, malformed
  line, or hash mismatch · 2 = bad invocation/manifest unreadable.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path, PurePosixPath

_LINE_RE = re.compile(r"^(?P<hash>[0-9a-fA-F]{64})\s+\*?(?P<path>\S.*)$")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="verify_release_checksums.py",
        description="Verify SHA-256 hashes listed in a release checksum manifest.",
    )
    parser.add_argument("manifest", help="Path to the .sha256 manifest file.")
    parser.add_argument(
        "--base-dir",
        default=".",
        help="Directory the manifest's relative paths resolve against "
        "(default: current working directory — run from the repo root).",
    )
    return parser.parse_args(argv)


def validate_rel_path(raw: str) -> PurePosixPath | None:
    """Return the path if it is a safe repository-relative path, else None."""
    if "\\" in raw:
        return None  # manifest uses forward slashes only
    p = PurePosixPath(raw)
    if p.is_absolute():
        return None
    if re.match(r"^[A-Za-z]:", raw):  # windows drive letter
        return None
    if ".." in p.parts or not p.parts:
        return None
    return p


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    manifest = Path(args.manifest)
    base_dir = Path(args.base_dir)

    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print(f"ERROR: cannot read manifest {manifest}: {exc}", file=sys.stderr)
        return 2

    entries: list[tuple[str, PurePosixPath]] = []
    failed = False
    for lineno, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _LINE_RE.match(line)
        if not match:
            print(f"FAIL  line {lineno}: malformed entry: {line!r}", file=sys.stderr)
            failed = True
            continue
        rel = validate_rel_path(match.group("path"))
        if rel is None:
            print(
                f"FAIL  line {lineno}: unsafe path (absolute/traversal/backslash): "
                f"{match.group('path')!r}",
                file=sys.stderr,
            )
            failed = True
            continue
        entries.append((match.group("hash").lower(), rel))

    if not entries and not failed:
        print("ERROR: manifest contains no entries", file=sys.stderr)
        return 1

    for expected, rel in entries:
        target = base_dir / Path(*rel.parts)
        if not target.is_file():
            print(f"FAIL  {rel}: file not found", file=sys.stderr)
            failed = True
            continue
        actual = sha256_of(target)
        if actual != expected:
            print(
                f"FAIL  {rel}: hash mismatch (expected {expected[:12]}…, got {actual[:12]}…)",
                file=sys.stderr,
            )
            failed = True
        else:
            print(f"OK    {rel}")

    if failed:
        print("RESULT: FAIL — one or more files did not verify", file=sys.stderr)
        return 1
    print(f"RESULT: OK — {len(entries)} file(s) verified")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
