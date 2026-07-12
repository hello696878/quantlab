"""
Tests for scripts/verify_release_checksums.py (release integrity verifier).

Runs the script as a subprocess against temporary directories only — no
repository files are read or modified, and no network is involved.
"""

import hashlib
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "verify_release_checksums.py"


def _run(manifest: Path, base_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(manifest), "--base-dir", str(base_dir)],
        capture_output=True,
        text=True,
        timeout=30,
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make(tmp_path: Path, rel: str, data: bytes) -> str:
    target = tmp_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return _sha256(data)


def test_valid_manifest_verifies(tmp_path):
    h1 = _make(tmp_path, "docs/a.md", b"alpha")
    h2 = _make(tmp_path, "docs/img/b.png", b"beta")
    manifest = tmp_path / "sums.sha256"
    manifest.write_text(
        f"# comment line\n\n{h1}  docs/a.md\n{h2} *docs/img/b.png\n",
        encoding="utf-8",
    )
    result = _run(manifest, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK    docs/a.md" in result.stdout
    assert "RESULT: OK — 2 file(s) verified" in result.stdout


def test_missing_file_fails(tmp_path):
    manifest = tmp_path / "sums.sha256"
    manifest.write_text(f"{'0' * 64}  docs/missing.md\n", encoding="utf-8")
    result = _run(manifest, tmp_path)
    assert result.returncode == 1
    assert "file not found" in result.stderr


def test_malformed_hash_fails(tmp_path):
    _make(tmp_path, "a.md", b"x")
    manifest = tmp_path / "sums.sha256"
    manifest.write_text("nothex  a.md\n", encoding="utf-8")
    result = _run(manifest, tmp_path)
    assert result.returncode == 1
    assert "malformed" in result.stderr


def test_hash_mismatch_fails(tmp_path):
    _make(tmp_path, "a.md", b"real content")
    manifest = tmp_path / "sums.sha256"
    manifest.write_text(f"{_sha256(b'other content')}  a.md\n", encoding="utf-8")
    result = _run(manifest, tmp_path)
    assert result.returncode == 1
    assert "hash mismatch" in result.stderr


def test_path_traversal_rejected(tmp_path):
    outside = tmp_path.parent / "outside_secret.txt"
    manifest = tmp_path / "sums.sha256"
    manifest.write_text(f"{'a' * 64}  ../{outside.name}\n", encoding="utf-8")
    result = _run(manifest, tmp_path)
    assert result.returncode == 1
    assert "unsafe path" in result.stderr


def test_absolute_path_rejected(tmp_path):
    manifest = tmp_path / "sums.sha256"
    manifest.write_text(f"{'a' * 64}  /etc/passwd\n{'b' * 64}  C:/win.ini\n", encoding="utf-8")
    result = _run(manifest, tmp_path)
    assert result.returncode == 1
    assert result.stderr.count("unsafe path") == 2


def test_empty_manifest_fails(tmp_path):
    manifest = tmp_path / "sums.sha256"
    manifest.write_text("# only a comment\n\n", encoding="utf-8")
    result = _run(manifest, tmp_path)
    assert result.returncode == 1
    assert "no entries" in result.stderr


def test_unreadable_manifest_exits_2(tmp_path):
    result = _run(tmp_path / "does_not_exist.sha256", tmp_path)
    assert result.returncode == 2
    assert "cannot read manifest" in result.stderr
