"""Disposable adversarial regressions for the Phase 64 test infrastructure."""
from argparse import Namespace
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time

import pytest

from .conftest import isolated_lab_db, lab_schema_template
from .test_backend_test_maintenance import FixtureRequest, SCRIPT, runner

CACHED_CONNECT = sqlite3.connect


def disposable_repo(tmp_path, body="def test_ok(): assert True", ini=""):
    repo = tmp_path / "source-測試"
    (repo / "scripts").mkdir(parents=True)
    (repo / "backend/tests").mkdir(parents=True)
    shutil.copyfile(SCRIPT, repo / "scripts/backend_test_runner.py")
    (repo / "backend/tests/test_probe.py").write_text(body, encoding="utf-8")
    (repo / "backend/pyproject.toml").write_text("[tool.pytest.ini_options]\n" + ini, encoding="utf-8")
    # Git writes are confined to this disposable repository, never the checkout.
    runner.git(repo, "init", "-q", "--template=")
    runner.git(repo, "add", "--", "scripts", "backend")
    runner.git(repo, "-c", "commit.gpgsign=false", "-c", "user.name=Test Fixture", "-c", "user.email=fixture@example.invalid",
               "commit", "-qm", "disposable baseline")
    return repo


def run_disposable(repo, tmp_path, scope="focused"):
    output = tmp_path / "evidence"
    output.mkdir()
    args = Namespace(scope=scope, collect_only=False)
    targets = runner.selection(scope, [] if scope == "full" else ["backend/tests/test_probe.py"])
    code = runner.run_snapshot(repo, args, targets, output)
    return code, json.loads((output / "runner-result.json").read_text(encoding="utf-8")), output


@pytest.mark.parametrize("body,expected", [
    ("def test_ok(): assert True", 0),
    ("def test_failure(): assert False", 1),
    ("raise ImportError('controlled import failure')", 2),
    ("# no tests", 5),
])
def test_outer_status_records_actual_child_and_final_codes(tmp_path, body, expected):
    repo = disposable_repo(tmp_path, body)
    code, result, output = run_disposable(repo, tmp_path)
    assert code == result["outer_runner_exit_code"] == result["pytest_process_exit_code"] == expected
    assert result["status"] == "completed"
    assert all(result[key] for key in ("worktree_bytes_unchanged", "snapshot_bytes_unchanged", "active_db_unchanged"))
    assert json.loads((output / "pytest-result.json").read_text())["exit_code"] == expected


@pytest.mark.parametrize("ini", [
    'addopts = "--ignore=tests/test_hidden.py"\n',
    'python_files = ["test_probe.py"]\n',
])
def test_full_cannot_succeed_when_configuration_hides_tests(tmp_path, ini):
    repo = disposable_repo(tmp_path, ini=ini)
    (repo / "backend/tests/test_hidden.py").write_text("def test_hidden(): assert True", encoding="utf-8")
    code, result, output = run_disposable(repo, tmp_path, "full")
    assert code != 0 and result["outer_runner_exit_code"] == code
    assert "full scope refuses" in (output / "pytest.log").read_text(encoding="utf-8")


def test_full_detects_plugin_ignored_file_before_execution(tmp_path):
    repo = disposable_repo(tmp_path, "def test_ok(): raise AssertionError('must not run')")
    (repo / "backend/tests/test_hidden.py").write_text("def test_hidden(): assert True", encoding="utf-8")
    (repo / "backend/tests/conftest.py").write_text("collect_ignore = ['test_hidden.py']", encoding="utf-8")
    code, result, output = run_disposable(repo, tmp_path, "full")
    assert code != 0
    assert "full scope collection is incomplete" in (output / "pytest.log").read_text(encoding="utf-8")
    assert not (output / "phases.jsonl").read_text()


def test_diff_uses_same_exclusions_and_never_rename_sources(tmp_path):
    repo = disposable_repo(tmp_path)
    files = {".env": "PRIVATE_OLD_SECRET", "backend/data/quantlab.db": "PRIVATE_OLD_DB",
             "artifacts/private.txt": "PRIVATE_OLD_ARTIFACT", ".env.example": "PLACEHOLDER_OLD"}
    for name, content in files.items():
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    runner.git(repo, "add", "--", *files)
    runner.git(repo, "-c", "commit.gpgsign=false", "-c", "user.name=Test Fixture", "-c", "user.email=fixture@example.invalid",
               "commit", "-qm", "disposable exclusions")
    for name in files:
        (repo / name).write_text("PRIVATE_NEW_SECRET" if name != ".env.example" else "PLACEHOLDER_NEW", encoding="utf-8")
    # A safe file replacing a removed secret must not include the old secret via rename detection.
    (repo / ".env").unlink()
    (repo / "safe.txt").write_text("safe replacement", encoding="utf-8")
    runner.git(repo, "add", "--", ".env", "safe.txt")
    diff = runner.safe_worktree_diff(repo, runner.source_inventory(repo))
    assert "PRIVATE_" not in diff
    assert "PLACEHOLDER_OLD" in diff and "PLACEHOLDER_NEW" in diff
    assert "safe replacement" in diff


@pytest.mark.parametrize("path", ["../escape.py", "backend/tests/../../../escape.py", "/absolute.py",
                                 "C:/escape.py", "backend/tests/test.py:stream", "backend//tests/test.py"])
def test_snapshot_rejects_literal_path_escapes(tmp_path, path):
    with pytest.raises(ValueError):
        runner.copy_snapshot(tmp_path / "repo", tmp_path / "snapshot", [path])
    assert not (tmp_path / "snapshot").exists()


def directory_link(link, target):
    if os.name == "nt":
        # Junctions need no Developer Mode; both endpoints remain test-owned.
        command = ["powershell", "-NoProfile", "-Command",
                   f"New-Item -ItemType Junction -Path '{link}' -Target '{target}' | Out-Null"]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
        assert completed.returncode == 0, completed.stderr
    else:
        link.symlink_to(target, target_is_directory=True)


def test_internal_directory_link_is_rejected_without_reading_target(tmp_path):
    repo = tmp_path / "repo"
    (repo / "real").mkdir(parents=True)
    (repo / "real/source.py").write_text("controlled source", encoding="utf-8")
    link = repo / "linked"
    directory_link(link, repo / "real")
    with pytest.raises(ValueError, match="links/junctions"):
        runner.copy_snapshot(repo, tmp_path / "snapshot", ["linked/source.py"])
    assert not (tmp_path / "snapshot").exists()


@pytest.mark.parametrize("linked_side", ["source", "destination", "destination_parent"])
def test_snapshot_refuses_linked_roots_before_copying(tmp_path, linked_side):
    repo, destination, controlled = tmp_path / "repo", tmp_path / "snapshot", tmp_path / "controlled"
    repo.mkdir()
    controlled.mkdir()
    (repo / "source.py").write_text("controlled source", encoding="utf-8")
    if linked_side == "source":
        link = tmp_path / "source-link"
        directory_link(link, repo)
        repo = link
    else:
        directory_link(destination, controlled)
        if linked_side == "destination_parent":
            destination = destination / "nested"
    with pytest.raises(ValueError, match="linked/junction roots"):
        runner.copy_snapshot(repo, destination, ["source.py"])
    assert list(controlled.iterdir()) == []


@pytest.mark.parametrize("addition", ["source", "junction", "excluded_artifact"])
def test_snapshot_inventory_detects_added_source_without_following_links(tmp_path, addition):
    repo, target = tmp_path / "repo", tmp_path / "snapshot"
    repo.mkdir()
    (repo / "source.py").write_text("controlled source", encoding="utf-8")
    manifest, omitted = runner.copy_snapshot(repo, target, ["source.py"])
    if addition == "source":
        (target / "added.py").write_text("new source", encoding="utf-8")
    elif addition == "junction":
        controlled = tmp_path / "controlled"
        controlled.mkdir()
        (controlled / "private.py").write_text("test-owned sentinel", encoding="utf-8")
        directory_link(target / "new_directory", controlled)
    else:
        (target / "artifacts").mkdir()
        (target / "artifacts/runtime.txt").write_text("excluded runtime output", encoding="utf-8")
    assert runner.snapshot_unchanged(target, manifest, omitted) is (addition == "excluded_artifact")


def test_outer_runner_rejects_added_snapshot_source(tmp_path):
    body = ("from pathlib import Path\ndef test_add():\n"
            "    Path(__file__).with_name('added.py').write_text('new source')\n")
    repo = disposable_repo(tmp_path, body)
    code, result, _ = run_disposable(repo, tmp_path)
    assert code == result["outer_runner_exit_code"] == 2
    assert result["pytest_process_exit_code"] == 0
    assert result["snapshot_bytes_unchanged"] is False
    assert result["status"] == "protection_failed"


@pytest.mark.parametrize("mutation", ["source", "snapshot", "missing"])
def test_outer_protection_detects_changed_and_reappearing_source(tmp_path, monkeypatch, mutation):
    repo = disposable_repo(tmp_path)
    if mutation == "missing":
        (repo / "backend/tests/test_probe.py").unlink()

    def mutate(command, snapshot, env, output):
        target = snapshot if mutation == "snapshot" else repo
        (target / "backend/tests/test_probe.py").write_text("changed working bytes", encoding="utf-8")
        return 0

    monkeypatch.setattr(runner, "stream_child", mutate)
    code, result, _ = run_disposable(repo, tmp_path)
    assert code == result["outer_runner_exit_code"] == 2
    assert result["status"] == "protection_failed"
    assert result["pytest_process_exit_code"] == 0


@pytest.mark.parametrize("error,status,expected", [(OSError, "runner_error", 2),
                                                 (KeyboardInterrupt, "interrupted", 130)])
def test_launch_failure_and_interruption_are_explicit(tmp_path, monkeypatch, error, status, expected):
    repo = disposable_repo(tmp_path)

    def fail(*args):
        raise error("controlled failure")

    monkeypatch.setattr(runner, "stream_child", fail)
    code, result, _ = run_disposable(repo, tmp_path)
    assert code == result["outer_runner_exit_code"] == expected
    assert result["status"] == status
    assert result["pytest_process_exit_code"] is None


def test_postprocessing_failure_is_not_green(tmp_path, monkeypatch):
    repo = disposable_repo(tmp_path)
    monkeypatch.setattr(runner, "stream_child", lambda *args: 0)
    real_snapshot = runner.database_snapshot
    calls = []

    def snapshot(path):
        calls.append(path)
        if len(calls) == 2:
            raise OSError("controlled postprocessing failure")
        return real_snapshot(path)

    monkeypatch.setattr(runner, "database_snapshot", snapshot)
    code, result, _ = run_disposable(repo, tmp_path)
    assert code == result["outer_runner_exit_code"] == 2
    assert result["status"] == "postprocessing_error"


@pytest.mark.parametrize("connect", [CACHED_CONNECT, sqlite3.dbapi2.connect])
def test_database_free_guard_catches_cached_and_dbapi2_connections(tmp_path, monkeypatch, connect):
    fixture = isolated_lab_db.__wrapped__(FixtureRequest(db_free=True), tmp_path, monkeypatch)
    path = next(fixture)
    with pytest.raises(AssertionError, match="unauthorized SQLite"):
        connect(path)
    with pytest.raises(AssertionError, match="unauthorized SQLite attempts"):
        next(fixture)
    assert not path.exists()
    # The permanent hook must be inert after teardown.
    with closing(connect(":memory:")) as conn:
        assert conn.execute("SELECT 1").fetchone() == (1,)


def test_fresh_schema_guard_is_installed_before_initialization(tmp_path, monkeypatch):
    from app import db
    outside = tmp_path / "forbidden.db"
    allowed = tmp_path / "fixture"
    allowed.mkdir()

    def initialize():
        try:
            CACHED_CONNECT(outside)
        except AssertionError:
            pass

    monkeypatch.setattr(db, "init_db", initialize)
    fixture = isolated_lab_db.__wrapped__(FixtureRequest(fresh=True), allowed, monkeypatch)
    next(fixture)
    with pytest.raises(AssertionError, match="unauthorized SQLite attempts"):
        next(fixture)
    assert not outside.exists()


def test_conflicting_fixture_markers_fail_before_schema_access(tmp_path, monkeypatch):
    fixture = isolated_lab_db.__wrapped__(FixtureRequest(db_free=True, fresh=True), tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="markers conflict"):
        next(fixture)
    assert not list(tmp_path.iterdir())


def test_template_initialization_is_guarded_and_restores_override(tmp_path, monkeypatch):
    from app import db
    forbidden = tmp_path / "forbidden.db"
    original_override = db._db_path_override

    class Factory:
        def mktemp(self, name):
            path = tmp_path / name
            path.mkdir()
            return path

    monkeypatch.setattr(db, "init_db", lambda: CACHED_CONNECT(forbidden))
    with pytest.raises(AssertionError, match="unauthorized SQLite attempts"):
        lab_schema_template.__wrapped__(Factory())
    assert db._db_path_override == original_override
    assert not forbidden.exists()


def test_basetemp_cannot_be_redirected_by_pytest_configuration(tmp_path):
    outside = tmp_path / "must-stay-absent"
    repo = disposable_repo(tmp_path, ini=f"addopts = {json.dumps('--basetemp=' + str(outside))}\n")
    code, result, output = run_disposable(repo, tmp_path)
    # The outer runner's later explicit basetemp overrides the ini value safely.
    assert code == 0 and not outside.exists()
    config = json.loads((output / "run-config.json").read_text(encoding="utf-8"))
    assert str(output / "pytest-tmp") in config["pytest_args"]


def test_pytest_pythonpath_cannot_import_outside_snapshot(tmp_path):
    outside = tmp_path / "outside-pythonpath"
    outside.mkdir()
    sentinel = tmp_path / "must-not-import.txt"
    (outside / "outside_probe.py").write_text(
        f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('unauthorized import')", encoding="utf-8")
    repo = disposable_repo(tmp_path, "import outside_probe\ndef test_ok(): assert True",
                           ini=f"pythonpath = [{json.dumps(str(outside))}]\n")
    (repo / "backend/tests/conftest.py").write_text("import outside_probe", encoding="utf-8")
    code, result, output = run_disposable(repo, tmp_path)
    assert code != 0 and result["outer_runner_exit_code"] == code
    assert "pythonpath must remain inside" in (output / "pytest.log").read_text(encoding="utf-8")
    assert not sentinel.exists()


@pytest.mark.parametrize("expected", [0, 1, 2])
def test_powershell_propagates_runner_exit_and_launch_failure(tmp_path, expected):
    shell = shutil.which("powershell") or shutil.which("pwsh")
    if shell is None:
        pytest.skip("PowerShell wrapper requires PowerShell")
    repo = disposable_repo(tmp_path, "def test_probe(): assert " + str(expected == 0))
    wrapper = repo / "scripts/run_backend_tests.ps1"
    shutil.copyfile(SCRIPT.with_name("run_backend_tests.ps1"), wrapper)
    temporary = tmp_path / "runner-temp"
    temporary.mkdir()
    env = runner.child_environment(repo, temporary)
    env.update(TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary))
    python = str(tmp_path / "missing-python.exe") if expected == 2 else sys.executable
    completed = subprocess.run([shell, "-NoProfile", "-File", str(wrapper), "-Python", python,
                                "-Scope", "focused", "-Tests", "backend/tests/test_probe.py"],
                               cwd=repo, env=env, capture_output=True, text=True, encoding="utf-8", timeout=45)
    assert completed.returncode == expected, completed.stdout + completed.stderr
    reports = list(temporary.glob("quantlab-backend-*/runner-result.json"))
    if expected != 2:
        assert len(reports) == 1
        assert json.loads(reports[0].read_text(encoding="utf-8"))["outer_runner_exit_code"] == expected
    else:
        assert reports == []


def test_stream_interruption_terminates_child_tree_before_reraising(tmp_path, monkeypatch):
    calls = []

    class BrokenOutput:
        def __iter__(self):
            raise KeyboardInterrupt()

        def close(self):
            calls.append("closed")

    class Process:
        stdout = BrokenOutput()

    process = Process()
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(runner, "stop_process_tree", lambda current: calls.append(current))
    with pytest.raises(KeyboardInterrupt):
        runner.stream_child(["controlled"], tmp_path, {}, tmp_path)
    assert calls == [process, "closed"]


def test_child_records_caught_bytes_database_attempt(tmp_path):
    forbidden = tmp_path / "forbidden.db"
    body = ("import os, sqlite3\ndef test_bytes():\n"
            f"    try: sqlite3.dbapi2.connect(os.fsencode({str(forbidden)!r}))\n"
            "    except Exception: pass\n")
    repo = disposable_repo(tmp_path, body)
    code, result, output = run_disposable(repo, tmp_path)
    assert code == result["outer_runner_exit_code"] == 1
    assert json.loads((output / "sqlite-violations.json").read_text()) == [str(forbidden)]
    assert not forbidden.exists()


def test_zero_exit_before_pytest_finalization_is_incomplete(tmp_path):
    repo = disposable_repo(tmp_path, "import os\ndef test_exit(): os._exit(0)")
    code, result, output = run_disposable(repo, tmp_path)
    assert code == result["outer_runner_exit_code"] == 2
    assert result["pytest_process_exit_code"] == 0
    assert result["child_evidence_complete"] is False
    assert result["status"] == "incomplete"
    assert not (output / "pytest-result.json").exists()


def test_collection_only_has_complete_evidence_without_execution_phases(tmp_path):
    repo = disposable_repo(tmp_path, "def test_never_runs(): assert False")
    output = tmp_path / "evidence"
    output.mkdir()
    code = runner.run_snapshot(repo, Namespace(scope="full", collect_only=True), ["backend/tests"], output)
    result = json.loads((output / "runner-result.json").read_text(encoding="utf-8"))
    assert code == result["outer_runner_exit_code"] == 0
    assert result["child_evidence_complete"] is True
    assert not (output / "phases.jsonl").read_text(encoding="utf-8")


def test_real_interrupted_process_tree_is_terminated(tmp_path, monkeypatch):
    import ctypes
    import signal

    def running(pid):
        if os.name == "nt":
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.restype = ctypes.c_void_p
            kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            handle = kernel.OpenProcess(0x1000, False, pid)
            if not handle:
                return False
            try:
                code = ctypes.c_ulong()
                assert kernel.GetExitCodeProcess(handle, ctypes.byref(code))
                return code.value == 259
            finally:
                kernel.CloseHandle(handle)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        proc_stat = Path(f"/proc/{pid}/stat")
        return not (proc_stat.exists() and proc_stat.read_text().split()[2] == "Z")

    child_program = "import time; print('READY', flush=True); time.sleep(60)"
    parent_program = (
        "import subprocess, sys, time; "
        f"child = subprocess.Popen([sys.executable, '-u', '-c', {child_program!r}], stdout=subprocess.PIPE, text=True); "
        "ready = child.stdout.readline(); print(str(child.pid) + ':' + ready.strip(), flush=True); time.sleep(60)"
    )
    seen = []

    def interrupt_on_ready(line, **kwargs):
        child_pid, ready = line.strip().split(":")
        assert ready == "READY"
        seen.append(int(child_pid))
        assert running(seen[0])
        raise KeyboardInterrupt()

    monkeypatch.setattr(runner, "print", interrupt_on_ready, raising=False)
    try:
        with pytest.raises(KeyboardInterrupt):
            runner.stream_child([sys.executable, "-u", "-c", parent_program], tmp_path,
                                runner.child_environment(tmp_path, tmp_path), tmp_path)
        assert len(seen) == 1
        deadline = time.monotonic() + 5
        while running(seen[0]) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not running(seen[0]), "interrupted runner left its descendant running"
    finally:
        for pid in seen:
            if running(pid):
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=15)
                else:
                    os.kill(pid, signal.SIGKILL)
