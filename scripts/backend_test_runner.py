"""Serial backend verification against current bytes, not git archive HEAD."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import platform
import signal
import stat
import subprocess
import sys
import tempfile
import time

FAST_FILES = [f"backend/tests/test_{name}.py" for name in
              ("signal_ensemble", "factor_diagnostics", "strategy_ensemble")]
ENV_KEYS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "PYTEST_ADDOPTS",
            "PYTEST_PLUGINS", "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "PYTHONUTF8", "PYTHONIOENCODING")


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
    return result.stdout.decode("utf-8")


def selection(scope, tests):
    if scope in {"full", "fast"}:
        if tests:
            raise ValueError("full/fast do not accept a narrower --test selection")
        return ["backend/tests"] if scope == "full" else [*FAST_FILES, "-m", "db_free"]
    if not tests:
        raise ValueError("focused/profile require explicit --test files or node IDs")
    for target in tests:
        path = relative_path(target.split("::", 1)[0])
        if not path.startswith("backend/tests/"):
            raise ValueError("test targets must be repository-relative backend/tests paths")
    return tests


def excluded(path):
    path = path.replace("\\", "/").lower()
    parts = PurePosixPath(path).parts
    name = PurePosixPath(path).name
    return (name.startswith(".env") and name != ".env.example" or
            any(p in {".git", ".venv", "venv", "node_modules", ".next", "__pycache__",
                      ".pytest_cache", ".mypy_cache", ".ruff_cache", "test-results", "playwright-report"} for p in parts) or
            path.startswith(("backend/data/", "data/", "artifacts/")) and name != ".gitkeep" or
            name == "quantlab.db" or name.startswith("quantlab.db-"))


def relative_path(value):
    path = value.replace("\\", "/")
    if (not path or PurePosixPath(path).is_absolute() or PureWindowsPath(path).drive or
            any(p in {"", ".", ".."} for p in path.split("/")) or
            ":" in path or "\0" in path):
        raise ValueError("paths must be literal repository-relative paths without traversal")
    return path


def contained_path(root, relative):
    relative = relative_path(relative)
    # Check the root before resolve(), which would erase a root junction/link.
    for parent in (root, *root.parents):
        try:
            info = parent.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError("snapshot refuses linked/junction roots")
    root = root.resolve()
    path = root
    for part in PurePosixPath(relative).parts:
        path = path / part
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError(f"snapshot refuses links/junctions: {relative}")
    if not path.resolve().is_relative_to(root):
        raise ValueError(f"snapshot refuses outside paths: {relative}")
    return path


def source_inventory(repo):
    return [p for p in git(repo, "ls-files", "--cached", "--others", "--exclude-standard", "-z").split("\0") if p]


def safe_worktree_diff(repo, paths):
    # Disable renames so a safe destination cannot disclose an excluded old path.
    # Literal pathspecs also prevent a filename from becoming a Git pattern.
    changed = set(git(repo, "diff", "HEAD", "--name-only", "--no-renames", "-z").split("\0"))
    selected = sorted({relative_path(p) for p in paths if p in changed and not excluded(p)})
    return "".join(git(repo, "diff", "HEAD", "--binary", "--no-renames", "--no-ext-diff", "--no-textconv",
                       "--", *[f":(literal){p}" for p in selected[i:i + 50]])
                   for i in range(0, len(selected), 50))


def copy_snapshot(repo, destination, paths):
    manifest, omitted = {}, []
    for relative in sorted(set(paths)):
        relative = relative_path(relative)
        if excluded(relative):
            omitted.append(relative)
            continue
        source = contained_path(repo, relative)
        if not source.exists():
            omitted.append(relative)
            continue
        if not source.is_file():
            raise ValueError(f"snapshot expects a regular file: {relative}")
        target = contained_path(destination, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        content = source.read_bytes()
        target.write_bytes(content)
        manifest[relative] = hashlib.sha256(content).hexdigest()
        if digest(source) != manifest[relative] or digest(target) != manifest[relative]:
            raise RuntimeError(f"source changed during snapshot: {relative}")
    return manifest, omitted


def manifest_unchanged(root, manifest, missing=()):
    try:
        return (all(contained_path(root, p).is_file() and digest(contained_path(root, p)) == h
                    for p, h in manifest.items()) and
                all(not contained_path(root, p).exists() for p in missing))
    except (OSError, ValueError):
        return False


def snapshot_unchanged(root, manifest, missing=()):
    if not manifest_unchanged(root, manifest, missing):
        return False
    expected = set(manifest)
    observed = set()

    def walk_error(error):
        raise error

    try:
        for directory, directories, files in os.walk(root, topdown=True, followlinks=False, onerror=walk_error):
            for name in list(directories):
                relative = (Path(directory) / name).relative_to(root).as_posix()
                if excluded(relative + "/probe") and not any(p.startswith(relative + "/") for p in expected):
                    directories.remove(name)
                    continue
                # Reject reparse points before os.walk can descend through them.
                contained_path(root, relative)
            for name in files:
                relative = (Path(directory) / name).relative_to(root).as_posix()
                if not excluded(relative):
                    contained_path(root, relative)
                    observed.add(relative)
        return observed == expected
    except (OSError, ValueError):
        return False


def database_snapshot(repo):
    paths = [*repo.glob("quantlab.db*"), *(repo / "backend/data").glob("quantlab.db*")]
    return {str(p.relative_to(repo)): {"sha256": digest(p), "size": p.stat().st_size,
                                     "mtime_ns": p.stat().st_mtime_ns}
            for p in paths if p.is_file()}


def child_environment(snapshot, output):
    env = os.environ.copy()
    # Stdio and default subprocess text decoders must agree on Windows too.
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    env["PYTHONPATH"] = str(snapshot / "backend")
    env["PYTEST_DEBUG_TEMPROOT"] = str(output)
    return env


class RunEvidence:
    def __init__(self, output, scope="focused", expected_files=(), source_root=None):
        self.output = output
        self.started = time.perf_counter()
        self.collected = []
        self.scope = scope
        self.expected_files = set(expected_files)
        self.collected_files = set()
        self.source_root = (source_root or output).resolve()
        self.phases = Counter()
        self.outcomes = Counter()
        self.phase_log = (output / "phases.jsonl").open("w", encoding="utf-8")

    def _validate_pythonpath(self, config):
        if any(not Path(path).resolve().is_relative_to(self.source_root) for path in config.getini("pythonpath")):
            raise ValueError("pytest pythonpath must remain inside the test-owned source snapshot")

    def pytest_load_initial_conftests(self, early_config):
        # Runs before pytest's trylast initial-conftest importer.
        self._validate_pythonpath(early_config)

    def pytest_configure(self, config):
        if config.getoption("numprocesses", default=0) not in (None, 0):
            raise ValueError("this runner requires serial execution")
        basetemp = config.getoption("basetemp")
        if basetemp and Path(basetemp).resolve() != (self.output / "pytest-tmp").resolve():
            raise ValueError("--basetemp must use this run's pytest-tmp directory")
        self._validate_pythonpath(config)
        if self.scope == "full":
            narrowing = {name: config.getoption(name, default=None) for name in
                         ("keyword", "markexpr", "ignore", "ignore_glob", "deselect", "lf", "stepwise", "pyargs")}
            if any(narrowing.values()):
                raise ValueError(f"full scope refuses collection narrowing: {narrowing}")
            for name, expected in (("python_files", ["test_*.py", "*_test.py"]),
                                   ("python_classes", ["Test"]), ("python_functions", ["test"])):
                if config.getini(name) != expected:
                    raise ValueError(f"full scope refuses nondefault {name}")
        write_json(self.output / "pytest-config.json", {
            "args": config.invocation_params.args,
            "ini_addopts": config.getini("addopts"),
            "plugins": [(d.project_name, d.version) for _, d in config.pluginmanager.list_plugin_distinfo()],
            "workers": 1,
        })

    def pytest_itemcollected(self, item):
        self.collected.append(item.nodeid)

    def pytest_collectreport(self, report):
        if report.nodeid:
            self.collected_files.add(report.nodeid.split("::", 1)[0].replace("\\", "/"))

    def pytest_collection_finish(self, session):
        selected = [item.nodeid for item in session.items]
        selected_set = set(selected)
        self.collection_seconds = time.perf_counter() - self.started
        write_json(self.output / "collection.json", {
            "collected": self.collected, "selected": selected,
            "deselected": [n for n in self.collected if n not in selected_set],
            "startup_and_collection_seconds": self.collection_seconds,
            "collected_files": sorted(self.collected_files),
            "expected_files": sorted(self.expected_files),
        })
        if self.scope == "full" and (selected != self.collected or
                not self.expected_files.issubset(self.collected_files)):
            raise ValueError("full scope collection is incomplete or deselected")

    def pytest_runtest_logreport(self, report):
        self.phases[report.when] += report.duration
        self.outcomes[f"{report.when}:{report.outcome}"] += 1
        self.phase_log.write(json.dumps({"nodeid": report.nodeid, "phase": report.when,
                                         "outcome": report.outcome, "seconds": report.duration}) + "\n")
        self.phase_log.flush()

    def pytest_sessionfinish(self, session, exitstatus):
        elapsed = time.perf_counter() - self.started
        write_json(self.output / "pytest-result.json", {
            "exit_code": int(exitstatus), "selected_count": session.testscollected,
            "pytest_wall_seconds": elapsed, "phase_seconds": dict(self.phases),
            "outcomes": dict(self.outcomes),
            "non_phase_seconds": elapsed - sum(self.phases.values()),
        })
        self.phase_log.close()


def execute(config_path):
    config = json.loads(config_path.read_text(encoding="utf-8"))
    output = config_path.parent
    allowed = output.resolve()
    violations = []

    def database_guard(event, args):
        if event == "sqlite3.connect":
            database = os.fsdecode(args[0])
            if database != ":memory:" and (database.lower().startswith("file:") or
                                             not Path(database).resolve().is_relative_to(allowed)):
                violations.append(database)
                raise RuntimeError("SQLite path outside this test-owned run directory")

    sys.addaudithook(database_guard)
    started = time.perf_counter()
    import pytest
    import_seconds = time.perf_counter() - started
    write_json(output / "runtime.json", {
        "python": sys.version, "executable": sys.executable, "platform": platform.platform(),
        "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
        "environment": {key: os.environ.get(key) for key in ENV_KEYS},
        "pytest_import_seconds": import_seconds,
        "workers": 1,
    })
    source_root = Path(config.get("source_root", output)).resolve()
    if not source_root.is_relative_to(allowed):
        raise ValueError("source_root must remain inside this test-owned run directory")
    evidence = RunEvidence(output, config["scope"], config.get("expected_files", []), source_root)
    if config["scope"] == "profile" and not config["collect_only"]:
        import cProfile
        profiler = cProfile.Profile()
        code = profiler.runcall(pytest.main, config["pytest_args"], plugins=[evidence])
        profiler.dump_stats(str(output / "profile.pstats"))
    else:
        code = pytest.main(config["pytest_args"], plugins=[evidence])
    write_json(output / "sqlite-violations.json", violations)
    collection_path = output / "collection.json"
    collection = json.loads(collection_path.read_text()) if collection_path.exists() else None
    complete = (config["scope"] != "full" or collection is not None and
                collection["selected"] == collection["collected"])
    return int(code) if code else (0 if complete and not violations else 1)


def stop_process_tree(process):
    if os.name == "nt":
        result = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                capture_output=True, timeout=15)
        if result.returncode and process.poll() is None:
            raise RuntimeError("could not terminate interrupted test process tree")
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=15)


def stream_child(command, snapshot, env, output):
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    with (output / "pytest.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=snapshot, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding="utf-8", **options)
        try:
            for line in process.stdout:
                log.write(line)
                log.flush()
                print(line, end="", flush=True)
            return process.wait()
        except BaseException:
            stop_process_tree(process)
            raise
        finally:
            process.stdout.close()


def child_evidence_complete(output, *, collect_only):
    """A zero process exit alone is insufficient (for example os._exit(0))."""
    try:
        result = json.loads((output / "pytest-result.json").read_text(encoding="utf-8"))
        collection = json.loads((output / "collection.json").read_text(encoding="utf-8"))
        violations = json.loads((output / "sqlite-violations.json").read_text(encoding="utf-8"))
        selected = collection["selected"]
        count = result["selected_count"]
        if (type(result["exit_code"]) is not int or result["exit_code"] != 0 or type(count) is not int or count <= 0 or
                not isinstance(selected, list) or len(selected) != count or violations != []):
            return False
        collected, deselected = collection["collected"], collection["deselected"]
        if (not all(isinstance(items, list) and all(isinstance(node, str) for node in items)
                    for items in (collected, selected, deselected)) or
                Counter(collected) != Counter(selected) + Counter(deselected)):
            return False
        outcomes = result["outcomes"]
        if not isinstance(outcomes, dict) or any(type(value) is not int or value < 0 for value in outcomes.values()):
            return False
        if collect_only:
            return not outcomes
        setup = sum(outcomes.get(f"setup:{outcome}", 0) for outcome in ("passed", "skipped", "failed"))
        teardown = sum(outcomes.get(f"teardown:{outcome}", 0) for outcome in ("passed", "skipped", "failed"))
        calls = outcomes.get("call:passed", 0) + outcomes.get("call:skipped", 0)
        return (setup == teardown == count and calls == outcomes.get("setup:passed", 0) and
                not any(outcomes.get(f"{phase}:failed", 0) for phase in ("setup", "call", "teardown")))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def run_snapshot(repo, args, targets, output):
    started = time.perf_counter()
    result = {"status": "incomplete", "outer_runner_exit_code": None,
              "pytest_process_exit_code": None, "worktree_bytes_unchanged": None,
              "snapshot_bytes_unchanged": None, "active_db_unchanged": None}
    write_json(output / "runner-result.json", result)
    before_db = None
    manifest = None
    source_paths = None
    missing = []
    run_started = None
    snapshot = output / "source"
    final_code = 2
    try:
        before_db = database_snapshot(repo)
        write_json(output / "active-db-before.json", before_db)
        source_paths = source_inventory(repo)
        identity = {"head": git(repo, "rev-parse", "HEAD").strip(),
                    "status": git(repo, "status", "--short"), "source": str(repo)}
        manifest, omitted = copy_snapshot(repo, snapshot, source_paths)
        missing = [p for p in omitted if not excluded(p)]
        write_json(output / "snapshot-manifest.json", {"identity": identity, "sha256": manifest,
                                                       "omitted": omitted, "missing": missing})
        (output / "worktree.diff").write_text(safe_worktree_diff(repo, source_paths), encoding="utf-8")
        if not manifest_unchanged(repo, manifest, missing):
            raise RuntimeError("source changed before test launch")
        pytest_args = [*targets, "-q", "-ra", "-p", "no:cacheprovider", "--durations=0", "--durations-min=0",
                       "--basetemp", str(output / "pytest-tmp"), "--junitxml", str(output / "junit.xml")]
        if args.collect_only:
            pytest_args.append("--collect-only")
        config_path = output / "run-config.json"
        expected_files = [p.removeprefix("backend/") for p in manifest if p.startswith("backend/tests/") and
                          (Path(p).match("test_*.py") or Path(p).match("*_test.py"))]
        write_json(config_path, {"scope": args.scope, "collect_only": args.collect_only,
                                 "pytest_args": pytest_args, "expected_files": expected_files,
                                 "source_root": str(snapshot)})
        env = child_environment(snapshot, output)
        command = [sys.executable, "-u", str(snapshot / "scripts/backend_test_runner.py"), "--execute", str(config_path)]
        result["command"] = command
        run_started = time.perf_counter()
        result["snapshot_setup_seconds"] = run_started - started
        code = stream_child(command, snapshot, env, output)
        result["pytest_process_exit_code"] = code
        final_code = code
        result["status"] = "completed"
        if code == 0:
            result["child_evidence_complete"] = child_evidence_complete(output, collect_only=args.collect_only)
            if not result["child_evidence_complete"]:
                final_code = 2
                result["status"] = "incomplete"
    except KeyboardInterrupt:
        final_code = 130
        result["status"] = "interrupted"
        result["error_type"] = "KeyboardInterrupt"
    except Exception as error:
        final_code = 2
        result["status"] = "runner_error"
        result["error_type"] = type(error).__name__
        # Do not serialize exception text, which can contain source or secrets.
    finally:
        if run_started is not None:
            result["test_process_wall_seconds"] = time.perf_counter() - run_started
        try:
            if before_db is not None:
                after_db = database_snapshot(repo)
                write_json(output / "active-db-after.json", after_db)
                result["active_db_unchanged"] = before_db == after_db
            if manifest is not None:
                result["worktree_bytes_unchanged"] = (manifest_unchanged(repo, manifest, missing) and
                                                       set(source_paths) == set(source_inventory(repo)))
                result["snapshot_bytes_unchanged"] = snapshot_unchanged(snapshot, manifest, missing)
            if not all(result[key] is True for key in
                       ("active_db_unchanged", "worktree_bytes_unchanged", "snapshot_bytes_unchanged")):
                if final_code == 0:
                    final_code = 2
                if result["status"] in {"completed", "incomplete"}:
                    result["status"] = "protection_failed"
        except Exception as error:
            final_code = final_code or 2
            result.update(status="postprocessing_error", error_type=type(error).__name__)
        result["total_wall_seconds"] = time.perf_counter() - started
        # Printing happens before recording success: a broken output stream is not green.
        try:
            print(f"Evidence retained: {output}", flush=True)
        except (OSError, ValueError):
            final_code = final_code or 2
            result["status"] = "postprocessing_error"
        result["outer_runner_exit_code"] = final_code
        write_json(output / "runner-result.json", result)
    return final_code


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=["focused", "fast", "full", "profile"], default="full")
    parser.add_argument("--test", action="append", default=[])
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument("--execute", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.execute:
        return execute(args.execute)
    targets = selection(args.scope, args.test)
    if os.environ.get("PYTEST_ADDOPTS"):
        raise ValueError("clear PYTEST_ADDOPTS so hidden filters/workers cannot alter this run")
    repo = Path(__file__).resolve().parents[1]
    if Path(tempfile.gettempdir()).resolve().is_relative_to(repo):
        raise ValueError("TEMP must be outside the repository")
    output = Path(tempfile.mkdtemp(prefix=f"quantlab-backend-{args.scope}-"))
    print(f"Evidence: {output}", flush=True)
    return run_snapshot(repo, args, targets, output)


if __name__ == "__main__":
    raise SystemExit(main())
