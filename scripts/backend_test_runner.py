"""Serial backend verification against current bytes, not git archive HEAD."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
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
        path = target.split("::", 1)[0].replace("\\", "/")
        if not path.startswith("backend/tests/") or ".." in Path(path).parts:
            raise ValueError("test targets must be repository-relative backend/tests paths")
    return tests


def excluded(path):
    parts = Path(path).parts
    name = Path(path).name
    return (name.startswith(".env") and name != ".env.example" or
            any(p in {".git", ".venv", "venv", "node_modules", ".next", "__pycache__"} for p in parts) or
            path.startswith(("backend/data/", "data/", "artifacts/")) and name != ".gitkeep" or
            path == "quantlab.db" or path.startswith("quantlab.db-"))


def copy_snapshot(repo, destination, paths):
    manifest, omitted = {}, []
    for relative in sorted(set(paths)):
        source = repo / relative
        if not source.exists() or excluded(relative):
            omitted.append(relative)
            continue
        if source.is_symlink() or not source.resolve().is_relative_to(repo.resolve()):
            raise ValueError(f"snapshot refuses links/outside paths: {relative}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        content = source.read_bytes()
        target.write_bytes(content)
        manifest[relative] = hashlib.sha256(content).hexdigest()
        if digest(source) != manifest[relative] or digest(target) != manifest[relative]:
            raise RuntimeError(f"source changed during snapshot: {relative}")
    return manifest, omitted


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
    def __init__(self, output):
        self.output = output
        self.started = time.perf_counter()
        self.collected = []
        self.phases = Counter()
        self.outcomes = Counter()
        self.phase_log = (output / "phases.jsonl").open("w", encoding="utf-8")

    def pytest_configure(self, config):
        if config.getoption("numprocesses", default=0) not in (None, 0):
            raise ValueError("this runner requires serial execution")
        write_json(self.output / "pytest-config.json", {
            "args": config.invocation_params.args,
            "ini_addopts": config.getini("addopts"),
            "plugins": [(d.project_name, d.version) for _, d in config.pluginmanager.list_plugin_distinfo()],
            "workers": 1,
        })

    def pytest_itemcollected(self, item):
        self.collected.append(item.nodeid)

    def pytest_collection_finish(self, session):
        selected = [item.nodeid for item in session.items]
        selected_set = set(selected)
        self.collection_seconds = time.perf_counter() - self.started
        write_json(self.output / "collection.json", {
            "collected": self.collected, "selected": selected,
            "deselected": [n for n in self.collected if n not in selected_set],
            "startup_and_collection_seconds": self.collection_seconds,
        })

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
        if event == "sqlite3.connect" and args[0] != ":memory:":
            if str(args[0]).lower().startswith("file:") or not Path(args[0]).resolve().is_relative_to(allowed):
                violations.append(str(args[0]))
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
    evidence = RunEvidence(output)
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


def main(argv=None):
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
    started = time.perf_counter()
    source_paths = git(repo, "ls-files", "--cached", "--others", "--exclude-standard", "-z").split("\0")
    source_paths = [p for p in source_paths if p]
    identity = {"head": git(repo, "rev-parse", "HEAD").strip(),
                "status": git(repo, "status", "--short"), "source": str(repo)}
    (output / "worktree.diff").write_text(git(repo, "diff", "HEAD", "--binary"), encoding="utf-8")
    before_db = database_snapshot(repo)
    snapshot = output / "source"
    manifest, omitted = copy_snapshot(repo, snapshot, source_paths)
    write_json(output / "snapshot-manifest.json", {"identity": identity, "sha256": manifest, "omitted": omitted})
    write_json(output / "active-db-before.json", before_db)
    pytest_args = [*targets, "-q", "-ra", "-p", "no:cacheprovider", "--durations=0", "--durations-min=0",
                   "--basetemp", str(output / "pytest-tmp"), "--junitxml", str(output / "junit.xml")]
    if args.collect_only:
        pytest_args.append("--collect-only")
    config_path = output / "run-config.json"
    write_json(config_path, {"scope": args.scope, "collect_only": args.collect_only, "pytest_args": pytest_args})
    # Prevent an inherited path from importing the original checkout in the child.
    env = child_environment(snapshot, output)
    command = [sys.executable, "-u", str(snapshot / "scripts/backend_test_runner.py"), "--execute", str(config_path)]
    run_started = time.perf_counter()
    with (output / "pytest.log").open("w", encoding="utf-8") as log:
        with subprocess.Popen(command, cwd=snapshot, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace") as process:
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
                log.flush()
            code = process.wait()
    run_wall = time.perf_counter() - run_started
    after_db = database_snapshot(repo)
    unchanged = all((repo / p).is_file() and digest(repo / p) == h for p, h in manifest.items())
    current_paths = git(repo, "ls-files", "--cached", "--others", "--exclude-standard", "-z").split("\0")
    unchanged = unchanged and set(source_paths) == {p for p in current_paths if p}
    snapshot_unchanged = all((snapshot / p).is_file() and digest(snapshot / p) == h for p, h in manifest.items())
    write_json(output / "runner-result.json", {
        "pytest_process_exit_code": code, "test_process_wall_seconds": run_wall,
        "total_wall_seconds": time.perf_counter() - started,
        "snapshot_setup_seconds": run_started - started, "command": command,
        "worktree_bytes_unchanged": unchanged, "snapshot_bytes_unchanged": snapshot_unchanged,
        "active_db_unchanged": before_db == after_db,
    })
    write_json(output / "active-db-after.json", after_db)
    print(f"Evidence retained: {output}", flush=True)
    return code if code else (0 if unchanged and snapshot_unchanged and before_db == after_db else 2)


if __name__ == "__main__":
    raise SystemExit(main())
