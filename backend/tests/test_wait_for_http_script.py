"""
Tests for scripts/wait_for_http.py (the CI service-readiness helper).

Runs the script as a subprocess (it is a CLI, not a package module),
mirroring how .github/workflows/browser-e2e.yml invokes it. Everything is
deterministic and strictly local: the success case uses an in-process
ephemeral-port HTTP server that is shut down within the test, and the
timeout case polls a deliberately closed local port. No external network.
"""

import http.server
import socket
import subprocess
import sys
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "wait_for_http.py"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=30,
    )


def _free_local_port() -> int:
    """Reserve then release an ephemeral port (nothing listens afterwards)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _OkHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 — http.server API name
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *_args):  # keep test output quiet
        pass


def test_malformed_url_rejected():
    result = _run("not-a-url")
    assert result.returncode == 2
    assert "scheme" in result.stderr or "malformed" in result.stderr


def test_non_http_scheme_rejected():
    result = _run("ftp://127.0.0.1/thing")
    assert result.returncode == 2
    assert "scheme" in result.stderr


def test_non_local_host_rejected():
    # The helper must never become a generic network prober.
    result = _run("http://example.com/health")
    assert result.returncode == 2
    assert "non-local" in result.stderr


def test_negative_timeout_rejected():
    result = _run("http://127.0.0.1:1/", "--timeout", "-5")
    assert result.returncode == 2
    assert "--timeout" in result.stderr


def test_bad_allow_status_rejected():
    result = _run("http://127.0.0.1:1/", "--allow-status", "abc")
    assert result.returncode == 2
    assert "--allow-status" in result.stderr


def test_ready_against_ephemeral_local_server():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _OkHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = _run(f"http://127.0.0.1:{port}/", "--timeout", "10", "--interval", "0.2")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "READY" in result.stdout
        assert "HTTP 200" in result.stdout
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_timeout_against_closed_local_port():
    port = _free_local_port()  # reserved then released — nothing listens
    result = _run(
        f"http://127.0.0.1:{port}/", "--timeout", "1.5", "--interval", "0.2"
    )
    assert result.returncode == 1
    assert "TIMEOUT" in result.stderr
    assert "no response" in result.stderr
