#!/usr/bin/env python3
"""Wait until a LOCAL http(s) URL answers — CI service-readiness helper.

Used by .github/workflows/browser-e2e.yml to wait for the backend
(http://127.0.0.1:8000/health) and the production frontend
(http://127.0.0.1:3100/) before running the Playwright suite.

Deliberately tiny and safe:

* Python standard library only (urllib) — no dependencies.
* **Local URLs only** — anything whose host is not localhost/127.0.0.1/::1
  is rejected up front (exit 2). This tool must never become a generic
  network prober.
* Polls until an accepted HTTP status (default: 200) or the timeout elapses.
* Exit codes: 0 = ready · 1 = timed out · 2 = invalid arguments.
* Prints elapsed time and final status; never logs secrets (it only knows
  the URL it was given), never deletes files, never follows off-host URLs.

Examples:
    python scripts/wait_for_http.py http://127.0.0.1:8000/health --timeout 90
    python scripts/wait_for_http.py http://127.0.0.1:3100/ --timeout 120
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="wait_for_http.py",
        description="Poll a LOCAL http(s) URL until it responds (CI readiness).",
    )
    parser.add_argument("url", help="Local URL to poll, e.g. http://127.0.0.1:8000/health")
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Total seconds to wait before giving up (default: 60).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between polls (default: 1.0).",
    )
    parser.add_argument(
        "--allow-status",
        default="200",
        help="Comma-separated accepted HTTP status codes (default: 200).",
    )
    args = parser.parse_args(argv)

    parsed = urlparse(args.url)
    if parsed.scheme not in ("http", "https"):
        parser.error(f"unsupported URL scheme {parsed.scheme!r} — use http or https")
    if not parsed.hostname:
        parser.error(f"malformed URL: {args.url!r}")
    if parsed.hostname.lower() not in LOCAL_HOSTS:
        parser.error(
            f"refusing non-local host {parsed.hostname!r} — this helper only "
            "polls localhost/127.0.0.1/::1"
        )
    if args.timeout <= 0:
        parser.error("--timeout must be > 0")
    if args.interval <= 0:
        parser.error("--interval must be > 0")
    try:
        args.accepted = {int(s) for s in str(args.allow_status).split(",") if s.strip()}
    except ValueError:
        parser.error(f"--allow-status must be comma-separated integers, got {args.allow_status!r}")
    if not args.accepted:
        parser.error("--allow-status resolved to an empty set")
    return args


def probe_status(url: str, per_request_timeout: float) -> int | None:
    """One poll. Returns the HTTP status, or None if the service isn't up yet."""
    try:
        with urllib.request.urlopen(url, timeout=per_request_timeout) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:  # server answered with a non-2xx
        return int(exc.code)
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
        return None  # not listening / not ready yet


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    per_request_timeout = min(max(args.interval * 2.0, 1.0), 5.0)
    started = time.monotonic()
    deadline = started + args.timeout
    last_status: int | None = None

    while time.monotonic() < deadline:
        last_status = probe_status(args.url, per_request_timeout)
        elapsed = time.monotonic() - started
        if last_status in args.accepted:
            print(f"READY: {args.url} answered HTTP {last_status} after {elapsed:.1f}s")
            return 0
        time.sleep(args.interval)

    elapsed = time.monotonic() - started
    detail = f"last status HTTP {last_status}" if last_status is not None else "no response (connection refused/unreachable)"
    print(
        f"TIMEOUT: {args.url} not ready after {elapsed:.1f}s ({detail}; "
        f"accepted: {sorted(args.accepted)})",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
