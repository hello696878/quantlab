"""
Phase 13 commit 1 — audit models, deterministic finding utilities, and
audit-scoped path / frame contract helpers.

Covers ``app.experiment_audit.models`` only (no engine / renderers / CLI yet).
Parity tests prove the audit-scoped path helpers agree with the **public**
``ExperimentRun`` schema and the audit-scoped frame names agree with the
**public** ``ExperimentStore.write_frame`` — **without importing any private
``ExperimentStore`` symbol**.  Everything runs under ``tmp_path``; no network.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import io
import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from app.experiment_audit import (
    CANONICAL_ARTIFACT_KEYS,
    CANONICAL_FRAME_NAMES,
    IGNORED_OS_FILES,
    AuditCode,
    AuditError,
    AuditFinding,
    AuditLevel,
    AuditOverallStatus,
    AuditRunStatus,
    AuditSeverity,
    ExperimentRunAudit,
    ExperimentStoreAuditResult,
    AUDIT_DISCLAIMERS,
    audit_experiment_run,
    audit_experiment_store,
    export_audit_csv,
    export_audit_json,
    export_audit_markdown,
    finding_sort_key,
    has_parent_traversal,
    is_absolute_artifact_path,
    is_canonical_artifact_filename,
    is_safe_relative_artifact_path,
    overall_status_for,
    severity_at_least,
    severity_rank,
    sort_and_number_findings,
    status_for_findings,
    summarize_audit_result,
)
from app.experiment_audit import audit as audit_module
from app.experiment_audit import models as models_module
from app.experiment_audit import render as render_module
from app.experiments import ExperimentError, ExperimentRun, ExperimentStore
from pydantic import ValidationError

_BACKEND = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _repo_snapshot() -> tuple[bool, bool, bool]:
    return (
        (_REPO_ROOT / "data").exists(),
        (_REPO_ROOT / "artifacts").exists(),
        (_BACKEND / "data").exists(),
    )


def _finding(code=AuditCode.ORPHAN_ARTIFACT, severity=AuditSeverity.WARNING, **kw) -> AuditFinding:
    base = dict(severity=severity, code=code, message="m", run_directory="run_a")
    base.update(kw)
    return AuditFinding(**base)


# --------------------------------------------------------------------------- #
# enums
# --------------------------------------------------------------------------- #


def test_audit_severity_values():
    assert [s.value for s in AuditSeverity] == ["info", "warning", "error", "critical"]


def test_audit_code_values_unique():
    values = [c.value for c in AuditCode]
    assert len(values) == len(set(values))
    assert len(values) == 25  # the documented code set


def test_status_enum_values():
    assert {s.value for s in AuditRunStatus} == {"valid", "warning", "invalid"}
    assert {s.value for s in AuditOverallStatus} == {"ok", "warning", "failed"}


# --------------------------------------------------------------------------- #
# AuditFinding
# --------------------------------------------------------------------------- #


def test_finding_field_order_is_stable():
    assert [f.name for f in dataclasses.fields(AuditFinding)] == [
        "finding_id",
        "severity",
        "code",
        "message",
        "train_run_hash",
        "run_directory",
        "artifact_name",
        "relative_path",
        "expected",
        "actual",
    ]


def test_finding_frozen():
    f = _finding()
    with pytest.raises(dataclasses.FrozenInstanceError):
        f.message = "changed"


def test_finding_to_dict_deterministic_and_json_safe():
    f = _finding(
        code=AuditCode.ABSOLUTE_ARTIFACT_PATH,
        severity=AuditSeverity.ERROR,
        train_run_hash="run_a",
        artifact_name="predictions",
        relative_path=None,
        expected="relative path",
        actual=r"C:\evil\x.csv",  # unsafe raw value lives in 'actual', not a path field
    )
    d = f.to_dict()
    assert d["severity"] == "error" and d["code"] == "ABSOLUTE_ARTIFACT_PATH"
    assert d["actual"] == r"C:\evil\x.csv"
    assert f.to_dict() == d  # deterministic
    text = json.dumps(d, allow_nan=False, sort_keys=True)
    assert json.loads(text)["run_directory"] == "run_a"


def test_finding_accepts_root_directory_dot():
    f = _finding(run_directory=".", code=AuditCode.ROOT_LEVEL_FILE, severity=AuditSeverity.INFO)
    assert f.run_directory == "."


def test_finding_rejects_absolute_run_directory():
    with pytest.raises(AuditError):
        _finding(run_directory=r"C:\abs")


def test_finding_rejects_absolute_relative_path():
    with pytest.raises(AuditError):
        _finding(relative_path="/etc/passwd")


def test_finding_rejects_traversal_relative_path():
    with pytest.raises(AuditError):
        _finding(relative_path="../escape.csv")


def test_finding_rejects_traversal_run_directory():
    with pytest.raises(AuditError):
        _finding(run_directory="../run_a")


# --------------------------------------------------------------------------- #
# ExperimentRunAudit invariants
# --------------------------------------------------------------------------- #


def test_run_audit_valid_status():
    ra = ExperimentRunAudit(
        run_directory="run_a",
        train_run_hash="run_a",
        status=AuditRunStatus.VALID,
        findings=(_finding(code=AuditCode.UNEXPECTED_FILE, severity=AuditSeverity.INFO),),
    )
    assert ra.status == AuditRunStatus.VALID
    assert isinstance(ra.findings, tuple)


def test_run_audit_warning_status():
    ra = ExperimentRunAudit(
        run_directory="run_a",
        train_run_hash="run_a",
        status=AuditRunStatus.WARNING,
        findings=(_finding(severity=AuditSeverity.WARNING),),
    )
    assert ra.status == AuditRunStatus.WARNING


def test_run_audit_invalid_status():
    ra = ExperimentRunAudit(
        run_directory="run_a",
        train_run_hash="run_a",
        status=AuditRunStatus.INVALID,
        findings=(_finding(code=AuditCode.MISSING_REFERENCED_ARTIFACT, severity=AuditSeverity.ERROR),),
    )
    assert ra.status == AuditRunStatus.INVALID


def test_run_audit_valid_with_error_finding_rejected():
    with pytest.raises(AuditError):
        ExperimentRunAudit(
            run_directory="run_a",
            train_run_hash="run_a",
            status=AuditRunStatus.VALID,
            findings=(_finding(severity=AuditSeverity.ERROR),),
        )


def test_run_audit_warning_with_error_finding_rejected():
    with pytest.raises(AuditError):
        ExperimentRunAudit(
            run_directory="run_a",
            train_run_hash="run_a",
            status=AuditRunStatus.WARNING,
            findings=(_finding(severity=AuditSeverity.CRITICAL),),
        )


def test_run_audit_to_dict():
    ra = ExperimentRunAudit(
        run_directory="run_a", train_run_hash="run_a",
        status=AuditRunStatus.WARNING, findings=(_finding(severity=AuditSeverity.WARNING),),
    )
    d = ra.to_dict()
    assert d["status"] == "warning" and d["run_directory"] == "run_a"
    json.dumps(d, allow_nan=False)


# --------------------------------------------------------------------------- #
# ExperimentStoreAuditResult invariants
# --------------------------------------------------------------------------- #


def _result(**overrides) -> ExperimentStoreAuditResult:
    warn = _finding(severity=AuditSeverity.WARNING)
    ra = ExperimentRunAudit(
        run_directory="run_a", train_run_hash="run_a",
        status=AuditRunStatus.WARNING, findings=(warn,),
    )
    base = dict(
        runs_discovered=1,
        runs_valid=0,
        runs_with_warnings=1,
        runs_invalid=0,
        non_run_entries=0,
        findings_total=1,
        findings_by_severity={"warning": 1},
        findings_by_code={"ORPHAN_ARTIFACT": 1},
        audited_run_hashes=("run_a",),
        run_audits=(ra,),
        findings=(warn,),
        overall_status=AuditOverallStatus.WARNING,
    )
    base.update(overrides)
    return ExperimentStoreAuditResult(**base)


def test_store_result_valid_construction_and_to_dict():
    result = _result()
    assert result.overall_status == AuditOverallStatus.WARNING
    d = result.to_dict()
    text = json.dumps(d, allow_nan=False, sort_keys=True)
    assert json.loads(text)["findings_total"] == 1
    assert isinstance(result.run_audits, tuple)


def test_store_result_negative_count_rejected():
    with pytest.raises(AuditError):
        _result(runs_discovered=-1)


def test_store_result_findings_total_mismatch_rejected():
    with pytest.raises(AuditError):
        _result(findings_total=5)


def test_store_result_status_sum_mismatch_rejected():
    with pytest.raises(AuditError):
        _result(runs_valid=3)  # 3 + 1 + 0 != 1


def test_store_result_run_audit_count_mismatch_rejected():
    with pytest.raises(AuditError):
        _result(runs_discovered=2, runs_with_warnings=2)  # len(run_audits)=1


def test_store_result_duplicate_hashes_rejected():
    with pytest.raises(AuditError):
        _result(audited_run_hashes=("run_a", "run_a"))


def test_store_result_by_severity_sum_mismatch_rejected():
    with pytest.raises(AuditError):
        _result(findings_by_severity={"warning": 2})


def test_store_result_overall_status_mismatch_rejected():
    with pytest.raises(AuditError):
        _result(overall_status=AuditOverallStatus.OK)  # a warning finding exists


def test_store_result_empty_store_is_ok():
    result = ExperimentStoreAuditResult(
        runs_discovered=0, runs_valid=0, runs_with_warnings=0, runs_invalid=0,
        non_run_entries=0, findings_total=0, findings_by_severity={}, findings_by_code={},
        audited_run_hashes=(), run_audits=(), findings=(), overall_status=AuditOverallStatus.OK,
    )
    assert result.overall_status == AuditOverallStatus.OK
    json.dumps(result.to_dict(), allow_nan=False)


# --------------------------------------------------------------------------- #
# finding utilities
# --------------------------------------------------------------------------- #


def test_sort_and_number_deterministic():
    findings = (
        _finding(run_directory="run_b", code=AuditCode.ORPHAN_ARTIFACT, message="z"),
        _finding(run_directory="run_a", code=AuditCode.ORPHAN_ARTIFACT, message="a"),
        _finding(run_directory="run_a", code=AuditCode.ABSOLUTE_ARTIFACT_PATH,
                 severity=AuditSeverity.ERROR, message="a"),
    )
    numbered = sort_and_number_findings(findings)
    # ordered by run_directory, then code, then message
    assert [f.run_directory for f in numbered] == ["run_a", "run_a", "run_b"]
    assert [f.code for f in numbered][0] == AuditCode.ABSOLUTE_ARTIFACT_PATH  # sorts before ORPHAN
    assert [f.finding_id for f in numbered] == ["finding_0000", "finding_0001", "finding_0002"]
    # deterministic across calls
    assert [f.to_dict() for f in sort_and_number_findings(findings)] == [
        f.to_dict() for f in numbered
    ]


def test_sort_and_number_does_not_mutate_input():
    original = _finding(message="a")
    assert original.finding_id == ""
    sort_and_number_findings((original,))
    assert original.finding_id == ""  # unchanged


def test_finding_sort_key_handles_none():
    key = finding_sort_key(_finding(artifact_name=None, relative_path=None))
    assert key == ("run_a", "ORPHAN_ARTIFACT", "", "", "m")


def test_severity_rank_order():
    assert (
        severity_rank(AuditSeverity.INFO)
        < severity_rank(AuditSeverity.WARNING)
        < severity_rank(AuditSeverity.ERROR)
        < severity_rank(AuditSeverity.CRITICAL)
    )
    assert severity_rank("warning") == severity_rank(AuditSeverity.WARNING)  # accepts str


def test_severity_at_least():
    assert severity_at_least(AuditSeverity.ERROR, AuditSeverity.WARNING)
    assert severity_at_least(AuditSeverity.WARNING, AuditSeverity.WARNING)
    assert not severity_at_least(AuditSeverity.INFO, AuditSeverity.WARNING)


def test_status_helpers():
    assert status_for_findings(()) == AuditRunStatus.VALID
    assert status_for_findings((_finding(severity=AuditSeverity.INFO),)) == AuditRunStatus.VALID
    assert status_for_findings((_finding(severity=AuditSeverity.WARNING),)) == AuditRunStatus.WARNING
    assert status_for_findings((_finding(severity=AuditSeverity.ERROR),)) == AuditRunStatus.INVALID
    assert overall_status_for(()) == AuditOverallStatus.OK
    assert overall_status_for((_finding(severity=AuditSeverity.CRITICAL),)) == AuditOverallStatus.FAILED


# --------------------------------------------------------------------------- #
# audit-scoped path helpers
# --------------------------------------------------------------------------- #


def test_is_absolute_artifact_path():
    for v in (r"C:\x.csv", "C:/x.csv", "/x.csv", r"\\server\share\x.csv", r"\x.csv"):
        assert is_absolute_artifact_path(v), v
    for v in ("x.csv", "sub/x.csv", ""):
        assert not is_absolute_artifact_path(v), v


def test_has_parent_traversal():
    for v in ("../x.csv", r"..\x.csv", "sub/../x.csv", "a/../../b.csv"):
        assert has_parent_traversal(v), v
    for v in ("x.csv", "sub/x.csv", "..x.csv"):  # '..x' is not a '..' component
        assert not has_parent_traversal(v), v


def test_is_safe_relative_artifact_path():
    assert is_safe_relative_artifact_path("predictions.csv")
    assert is_safe_relative_artifact_path("sub/predictions.csv")  # safe subdir allowed
    assert not is_safe_relative_artifact_path("")
    assert not is_safe_relative_artifact_path("   ")
    assert not is_safe_relative_artifact_path(r"C:\x.csv")
    assert not is_safe_relative_artifact_path("/x.csv")
    assert not is_safe_relative_artifact_path(r"\\server\share\x.csv")
    assert not is_safe_relative_artifact_path("../x.csv")


def test_is_canonical_artifact_filename():
    assert is_canonical_artifact_filename("predictions.csv")
    assert is_canonical_artifact_filename("metadata.json")
    # canonical is stricter: safe subdirs are NOT canonical
    assert not is_canonical_artifact_filename("sub/predictions.csv")
    assert not is_canonical_artifact_filename(r"sub\predictions.csv")
    assert not is_canonical_artifact_filename("/abs.csv")
    assert not is_canonical_artifact_filename("")


def test_constants():
    assert CANONICAL_FRAME_NAMES == ("predictions", "signal", "backtest")
    assert CANONICAL_ARTIFACT_KEYS == (
        "metadata", "model_params", "metrics", "predictions", "signal", "backtest",
    )
    assert IGNORED_OS_FILES == frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})


# --------------------------------------------------------------------------- #
# parity with the PUBLIC persistence contract (no private imports)
# --------------------------------------------------------------------------- #


def _run_kwargs(**overrides) -> dict:
    base = dict(
        train_run_hash="h",
        continuous_config_hash="c",
        feature_config_hash="f",
        label_config_hash="l",
        dataset_config_hash="d",
        model_config_hash="m",
        model_type="ridge_regression",
        feature_columns=("feature__return_20",),
        label_column="label__forward_return_1",
        task_type="regression",
        train_start=date(2024, 4, 1),
        train_end=date(2024, 6, 5),
        validation_start=date(2024, 6, 6),
        validation_end=date(2024, 9, 15),
        created_at="2026-07-13T00:00:00+00:00",
    )
    base.update(overrides)
    return base


def _schema_accepts_artifact_path(value: str) -> bool:
    try:
        ExperimentRun(**_run_kwargs(artifact_paths={"predictions": value}))
        return True
    except ValidationError:
        return False


@pytest.mark.parametrize(
    "value",
    [
        "predictions.csv",
        "model_params.json",
        "sub/predictions.csv",       # safe relative subdir (schema allows)
        r"sub\predictions.csv",
        r"C:\x.csv",
        "C:/x.csv",
        "/x.csv",
        r"\\server\share\x.csv",     # UNC
        r"\x.csv",
        "../x.csv",
        r"..\x.csv",
        "sub/../x.csv",
        "",
    ],
)
def test_path_safety_parity_with_public_schema(value):
    assert is_safe_relative_artifact_path(value) == _schema_accepts_artifact_path(value)


def test_frame_name_parity_with_public_store(tmp_path):
    store = ExperimentStore(tmp_path / "s", prefer_parquet=False)
    df = pd.DataFrame({"a": [1, 2, 3]})
    for name in CANONICAL_FRAME_NAMES:
        store.write_frame("h", name, df)  # public API accepts each canonical frame
    with pytest.raises(ExperimentError):
        store.write_frame("h", "not_a_frame", df)  # and rejects unknown names


# --------------------------------------------------------------------------- #
# boundary / guard rails
# --------------------------------------------------------------------------- #


def test_models_module_no_private_or_forbidden_imports():
    import re as _re

    src = Path(models_module.__file__).read_text(encoding="utf-8")
    # Private ExperimentStore symbols: word-boundary match so legitimate public
    # names (e.g. CANONICAL_FRAME_NAMES) never trip the guard.
    for private in ("_ABSOLUTE_PATH", "_FRAME_NAMES", "_is_relative_path"):
        assert not _re.search(rf"\b{private}\b", src), f"models.py must not reference {private!r}"
    forbidden = [
        "app.local_pipeline",
        "app.batch_experiments",
        "app.reporting",
        "app.experiment_catalog",
        "run_local_futures_ml_experiment",
        "train_model",
        "build_feature_matrix",
        "build_label_matrix",
        "hashlib",
        "sha256",
        "compute_config_hash",
        "import requests",
        "urllib",
        "httpx",
        "aiohttp",
        "socket",
        "yfinance",
        "ibkr",
        "sklearn",
        "xgboost",
        "lightgbm",
        "torch",
        "tensorflow",
    ]
    for token in forbidden:
        assert token not in src, f"models.py must not reference {token!r}"


def test_models_module_does_no_filesystem_writes_or_repair():
    src = Path(models_module.__file__).read_text(encoding="utf-8")
    for token in (
        "open(",
        ".write_text",
        ".write_bytes",
        ".mkdir",
        "to_csv",
        "to_parquet",
        "rmtree",
        ".unlink",
        "os.remove",
        ".rename",
        "shutil",
    ):
        assert token not in src, f"models.py must not reference {token!r}"


def test_models_module_imports_no_app_modules():
    src = Path(models_module.__file__).read_text(encoding="utf-8")
    assert "from app." not in src and "import app." not in src


def test_models_create_no_repo_artifacts():
    before = _repo_snapshot()
    _result()
    sort_and_number_findings((_finding(),))
    assert _repo_snapshot() == before


# --------------------------------------------------------------------------- #
# engine fixtures (hand-built + deliberately tampered stores under tmp_path)
# --------------------------------------------------------------------------- #

import hashlib  # noqa: E402  (test-only, for byte-identical read-only proof)

_ALL_ARTIFACT_PATHS = {
    "metadata": "metadata.json",
    "model_params": "model_params.json",
    "metrics": "metrics.json",
    "predictions": "predictions.csv",
    "signal": "signal.csv",
    "backtest": "backtest.csv",
}


def _write_valid_run(store: ExperimentStore, name: str, *, artifact_paths=None) -> None:
    ap = _ALL_ARTIFACT_PATHS if artifact_paths is None else artifact_paths
    store.write_metadata(ExperimentRun(**_run_kwargs(train_run_hash=name, artifact_paths=ap)))
    store.write_model_params(name, {"a": 1})
    store.write_metrics(name, {"m": 1.0})
    df = pd.DataFrame({"x": [1, 2, 3]})
    for frame in CANONICAL_FRAME_NAMES:
        store.write_frame(name, frame, df)


def _valid_store(tmp_path: Path, names=("run_a", "run_b")) -> ExperimentStore:
    store = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    for name in names:
        _write_valid_run(store, name)
    return store


def _rewrite_metadata(store: ExperimentStore, name: str, mutate) -> None:
    """Load, mutate (a dict), and rewrite one run's metadata.json (test-side)."""
    path = store.base_dir / name / "metadata.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def _codes(result) -> set:
    return {f.code.value for f in result.findings}


def _codes_for(result, run_directory) -> set:
    return {f.code.value for f in result.findings if f.run_directory == run_directory}


def _store_snapshot(base: Path) -> dict:
    snap = {}
    for p in sorted(base.rglob("*")):
        rel = str(p.relative_to(base)).replace("\\", "/")
        snap[rel] = "DIR" if p.is_dir() else hashlib.sha256(p.read_bytes()).hexdigest()
    return snap


def _try_symlink(link: Path, target: Path) -> bool:
    try:
        link.symlink_to(target)
        return True
    except (OSError, NotImplementedError):
        return False


# --------------------------------------------------------------------------- #
# store root + entry classification
# --------------------------------------------------------------------------- #


def test_audit_missing_root_raises(tmp_path):
    store = ExperimentStore(tmp_path / "nope", prefer_parquet=False)
    with pytest.raises(AuditError):
        audit_experiment_store(store)


def test_audit_root_is_file_raises(tmp_path):
    (tmp_path / "afile").write_text("x", encoding="utf-8")
    store = ExperimentStore(tmp_path / "afile", prefer_parquet=False)
    with pytest.raises(AuditError):
        audit_experiment_store(store)


def test_audit_empty_store_ok(tmp_path):
    base = tmp_path / "exp"
    base.mkdir()
    result = audit_experiment_store(ExperimentStore(base, prefer_parquet=False))
    assert result.overall_status == AuditOverallStatus.OK
    assert result.runs_discovered == 0 and result.findings_total == 1
    assert _codes(result) == {"EMPTY_STORE"}


def test_audit_valid_store(tmp_path):
    store = _valid_store(tmp_path, ("run_a", "run_b", "run_c"))
    result = audit_experiment_store(store, level=AuditLevel.DEEP)
    assert result.overall_status == AuditOverallStatus.OK
    assert (result.runs_discovered, result.runs_valid, result.runs_invalid) == (3, 3, 0)
    assert result.findings_total == 0
    assert result.audited_run_hashes == ("run_a", "run_b", "run_c")
    assert [ra.run_directory for ra in result.run_audits] == ["run_a", "run_b", "run_c"]


def test_audit_root_level_file(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    (store.base_dir / "stray.txt").write_text("x", encoding="utf-8")
    result = audit_experiment_store(store)
    assert "ROOT_LEVEL_FILE" in _codes(result)
    assert result.non_run_entries == 1 and result.runs_discovered == 1


def test_audit_ignored_os_file_at_root(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    (store.base_dir / ".DS_Store").write_text("x", encoding="utf-8")
    result = audit_experiment_store(store)
    assert "IGNORED_OS_FILE" in _codes(result)


def test_audit_unrelated_directory(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    unrelated = store.base_dir / "notes"
    unrelated.mkdir()
    (unrelated / "readme.txt").write_text("hi", encoding="utf-8")
    result = audit_experiment_store(store)
    assert "NON_RUN_DIRECTORY" in _codes(result)
    assert result.non_run_entries == 1


def test_audit_empty_directory(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    (store.base_dir / "blank").mkdir()
    result = audit_experiment_store(store)
    assert "EMPTY_DIRECTORY" in _codes(result)


def test_audit_directory_with_artifacts_no_metadata(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    orphan_dir = store.base_dir / "half_run"
    orphan_dir.mkdir()
    (orphan_dir / "metrics.json").write_text("{}", encoding="utf-8")
    result = audit_experiment_store(store)
    assert "MISSING_METADATA" in _codes(result)
    assert result.overall_status == AuditOverallStatus.WARNING


def test_audit_root_symlink_not_followed(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    link = store.base_dir / "linky"
    if not _try_symlink(link, store.base_dir / "run_a"):
        pytest.skip("symlink creation not permitted on this platform")
    result = audit_experiment_store(store)
    assert "SYMLINK_ENTRY" in _codes(result)
    # the symlink is a non-run entry, not audited as a second run
    assert result.runs_discovered == 1


def test_audit_deterministic_entry_order(tmp_path):
    store = _valid_store(tmp_path, ("run_b", "run_a"))
    result = audit_experiment_store(store)
    assert [ra.run_directory for ra in result.run_audits] == ["run_a", "run_b"]  # sorted by name


# --------------------------------------------------------------------------- #
# metadata ladder — tolerant, does not abort other runs
# --------------------------------------------------------------------------- #


def test_audit_malformed_json_does_not_abort(tmp_path):
    store = _valid_store(tmp_path, ("run_a", "run_b"))
    (store.base_dir / "run_a" / "metadata.json").write_text("{ not valid json", encoding="utf-8")
    result = audit_experiment_store(store)
    assert "MALFORMED_METADATA_JSON" in _codes_for(result, "run_a")
    a = next(ra for ra in result.run_audits if ra.run_directory == "run_a")
    b = next(ra for ra in result.run_audits if ra.run_directory == "run_b")
    assert a.status == AuditRunStatus.INVALID and a.train_run_hash is None
    assert b.status == AuditRunStatus.VALID  # the valid run is unaffected
    assert result.overall_status == AuditOverallStatus.FAILED


def test_audit_invalid_schema(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    _rewrite_metadata(store, "run_a", lambda d: d.update(validation_end="2020-01-01"))
    result = audit_experiment_store(store)
    assert "INVALID_EXPERIMENT_RUN_SCHEMA" in _codes_for(result, "run_a")
    a = next(ra for ra in result.run_audits if ra.run_directory == "run_a")
    assert a.status == AuditRunStatus.INVALID and a.train_run_hash is None


def test_audit_directory_hash_mismatch(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    _rewrite_metadata(store, "run_a", lambda d: d.update(train_run_hash="different_hash"))
    result = audit_experiment_store(store)
    f = next(f for f in result.findings if f.code == AuditCode.DIRECTORY_HASH_MISMATCH)
    assert f.expected == "run_a" and f.actual == "different_hash"
    assert "different_hash" in result.audited_run_hashes  # schema-valid, so parseable


def test_audit_raw_unsafe_path_checked_when_schema_invalid(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    _rewrite_metadata(
        store, "run_a",
        lambda d: d["artifact_paths"].__setitem__("predictions", r"C:\evil\x.csv"),
    )
    result = audit_experiment_store(store)
    codes = _codes_for(result, "run_a")
    # both the raw path-safety finding AND the schema-invalid finding appear
    assert "ABSOLUTE_ARTIFACT_PATH" in codes
    assert "INVALID_EXPERIMENT_RUN_SCHEMA" in codes
    # the unsafe raw value lives in 'actual', not relative_path
    f = next(f for f in result.findings if f.code == AuditCode.ABSOLUTE_ARTIFACT_PATH)
    assert f.actual == r"C:\evil\x.csv" and f.relative_path is None


def test_audit_hash_chain_field_missing(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    _rewrite_metadata(store, "run_a", lambda d: d.update(model_config_hash=""))
    result = audit_experiment_store(store)
    assert "HASH_CHAIN_FIELD_MISSING" in _codes_for(result, "run_a")


# --------------------------------------------------------------------------- #
# artifact-path safety (metadata-only level suffices)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "value,expected_code",
    [
        (r"C:\evil.csv", "ABSOLUTE_ARTIFACT_PATH"),
        ("/etc/evil.csv", "ABSOLUTE_ARTIFACT_PATH"),
        (r"\\server\share\evil.csv", "ABSOLUTE_ARTIFACT_PATH"),
        ("../evil.csv", "PATH_TRAVERSAL"),
        (r"..\evil.csv", "PATH_TRAVERSAL"),
        ("", "INVALID_ARTIFACT_PATH"),
    ],
)
def test_audit_unsafe_artifact_paths(tmp_path, value, expected_code):
    store = _valid_store(tmp_path, ("run_a",))
    _rewrite_metadata(
        store, "run_a", lambda d: d["artifact_paths"].__setitem__("predictions", value)
    )
    result = audit_experiment_store(store, level=AuditLevel.METADATA_ONLY)
    assert expected_code in _codes_for(result, "run_a")


def test_audit_duplicate_artifact_reference(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    _rewrite_metadata(
        store, "run_a", lambda d: d["artifact_paths"].__setitem__("model_params", "metrics.json")
    )
    result = audit_experiment_store(store, level=AuditLevel.METADATA_ONLY)
    assert "DUPLICATE_ARTIFACT_REFERENCE" in _codes_for(result, "run_a")


def test_audit_safe_subdir_not_traversal(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    _rewrite_metadata(
        store, "run_a", lambda d: d["artifact_paths"].__setitem__("predictions", "sub/predictions.csv")
    )
    result = audit_experiment_store(store, level=AuditLevel.METADATA_ONLY)
    codes = _codes_for(result, "run_a")
    assert "PATH_TRAVERSAL" not in codes and "ABSOLUTE_ARTIFACT_PATH" not in codes
    # schema-valid (safe subdir allowed): no schema-invalid finding either
    assert "INVALID_EXPERIMENT_RUN_SCHEMA" not in codes


# --------------------------------------------------------------------------- #
# standard-level artifact / layout checks
# --------------------------------------------------------------------------- #


def test_audit_missing_referenced_artifact(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    (store.base_dir / "run_a" / "predictions.csv").unlink()
    result = audit_experiment_store(store, level=AuditLevel.STANDARD)
    f = next(f for f in result.findings if f.code == AuditCode.MISSING_REFERENCED_ARTIFACT)
    assert f.artifact_name == "predictions" and f.relative_path == "predictions.csv"


def test_audit_missing_expected_canonical_key(tmp_path):
    ap = {k: v for k, v in _ALL_ARTIFACT_PATHS.items() if k != "backtest"}
    store = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    _write_valid_run(store, "run_a", artifact_paths=ap)
    (store.base_dir / "run_a" / "backtest.csv").unlink()  # avoid an orphan
    result = audit_experiment_store(store, level=AuditLevel.STANDARD)
    f = next(f for f in result.findings if f.code == AuditCode.MISSING_EXPECTED_ARTIFACT)
    assert f.artifact_name == "backtest"
    assert "MISSING_REFERENCED_ARTIFACT" not in _codes(result)  # not described as referenced


def test_audit_artifact_path_points_to_directory(tmp_path):
    ap = dict(_ALL_ARTIFACT_PATHS, predictions="pred_dir")
    store = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    _write_valid_run(store, "run_a", artifact_paths=ap)
    (store.base_dir / "run_a" / "predictions.csv").unlink()
    (store.base_dir / "run_a" / "pred_dir").mkdir()
    result = audit_experiment_store(store, level=AuditLevel.STANDARD)
    assert "ARTIFACT_NOT_A_FILE" in _codes_for(result, "run_a")


def test_audit_orphan_and_unexpected_and_os_files(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    (store.base_dir / "run_a" / "extra.json").write_text("{}", encoding="utf-8")   # orphan
    (store.base_dir / "run_a" / "notes.txt").write_text("hi", encoding="utf-8")     # unexpected
    (store.base_dir / "run_a" / ".DS_Store").write_text("x", encoding="utf-8")      # ignored
    result = audit_experiment_store(store, level=AuditLevel.STANDARD)
    codes = _codes_for(result, "run_a")
    assert {"ORPHAN_ARTIFACT", "UNEXPECTED_FILE", "IGNORED_OS_FILE"} <= codes


def test_audit_conflicting_frame_format(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    (store.base_dir / "run_a" / "predictions.parquet").write_bytes(b"not a parquet")
    result = audit_experiment_store(store, level=AuditLevel.STANDARD)
    f = next(f for f in result.findings if f.code == AuditCode.CONFLICTING_FRAME_FORMAT)
    assert f.artifact_name == "predictions"


def test_audit_artifact_symlink_not_followed(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    target = store.base_dir / "run_a" / "predictions.csv"
    target.unlink()
    if not _try_symlink(target, store.base_dir / "run_a" / "signal.csv"):
        pytest.skip("symlink creation not permitted on this platform")
    result = audit_experiment_store(store, level=AuditLevel.STANDARD)
    assert "SYMLINK_ENTRY" in _codes_for(result, "run_a")


# --------------------------------------------------------------------------- #
# audit levels
# --------------------------------------------------------------------------- #


def test_metadata_only_skips_existence(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    (store.base_dir / "run_a" / "predictions.csv").unlink()
    result = audit_experiment_store(store, level=AuditLevel.METADATA_ONLY)
    assert "MISSING_REFERENCED_ARTIFACT" not in _codes(result)
    assert result.overall_status == AuditOverallStatus.OK  # existence not checked


def test_standard_checks_existence_but_not_frames(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    (store.base_dir / "run_a" / "predictions.csv").unlink()
    result = audit_experiment_store(store, level=AuditLevel.STANDARD)
    assert "MISSING_REFERENCED_ARTIFACT" in _codes(result)
    assert "INVALID_FRAME_FORMAT" not in _codes(result)


def test_deep_detects_unreadable_frame(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    (store.base_dir / "run_a" / "predictions.parquet").write_bytes(b"garbage-not-parquet")
    result = audit_experiment_store(store, level=AuditLevel.DEEP)
    assert "INVALID_FRAME_FORMAT" in _codes_for(result, "run_a")
    assert result.overall_status == AuditOverallStatus.FAILED


def test_deep_empty_frame_info(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    (store.base_dir / "run_a" / "signal.csv").write_text("x\n", encoding="utf-8")  # header only
    result = audit_experiment_store(store, level=AuditLevel.DEEP)
    assert "FRAME_ROW_COUNT_IMPLAUSIBLE" in _codes_for(result, "run_a")


def test_deep_continues_after_bad_frame(tmp_path):
    store = _valid_store(tmp_path, ("run_a", "run_b"))
    (store.base_dir / "run_a" / "predictions.parquet").write_bytes(b"garbage")
    result = audit_experiment_store(store, level=AuditLevel.DEEP)
    b = next(ra for ra in result.run_audits if ra.run_directory == "run_b")
    assert b.status == AuditRunStatus.VALID  # the other run still audits cleanly
    assert result.runs_discovered == 2


# --------------------------------------------------------------------------- #
# result determinism, counts, summary
# --------------------------------------------------------------------------- #


def test_result_deterministic_finding_ids_and_counts(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    (store.base_dir / "run_a" / "extra.json").write_text("{}", encoding="utf-8")
    (store.base_dir / "run_a" / "predictions.csv").unlink()
    r1 = audit_experiment_store(store, level=AuditLevel.STANDARD)
    r2 = audit_experiment_store(store, level=AuditLevel.STANDARD)
    assert r1.to_dict() == r2.to_dict()  # fully deterministic
    assert [f.finding_id for f in r1.findings] == [
        f"finding_{i:04d}" for i in range(r1.findings_total)
    ]
    assert sum(r1.findings_by_severity.values()) == r1.findings_total
    assert sum(r1.findings_by_code.values()) == r1.findings_total


def test_result_strict_json_safe_and_no_path_leak(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    (store.base_dir / "run_a" / "predictions.csv").unlink()  # error finding, no abs-path tamper
    result = audit_experiment_store(store, level=AuditLevel.STANDARD)
    text = json.dumps(result.to_dict(), allow_nan=False, sort_keys=True)
    assert "NaN" not in text and "Infinity" not in text
    assert tmp_path.name not in text and ":\\" not in text and ":/" not in text


def test_summarize_audit_result(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    result = audit_experiment_store(store, level=AuditLevel.STANDARD)
    summary = summarize_audit_result(result)
    assert summarize_audit_result(result) == summary  # deterministic
    text = json.dumps(summary, allow_nan=False, sort_keys=True)
    assert json.loads(text)["overall_status"] == "ok"
    assert set(summary) == {
        "overall_status", "runs_discovered", "runs_valid", "runs_with_warnings",
        "runs_invalid", "non_run_entries", "findings_total",
        "findings_by_severity", "findings_by_code", "audited_run_hashes",
    }


# --------------------------------------------------------------------------- #
# single-run audit
# --------------------------------------------------------------------------- #


def test_audit_single_valid_run(tmp_path):
    store = _valid_store(tmp_path, ("run_a", "run_b"))
    ra = audit_experiment_run(store, "run_a", level=AuditLevel.DEEP)
    assert ra.run_directory == "run_a" and ra.status == AuditRunStatus.VALID
    assert ra.train_run_hash == "run_a" and ra.findings == ()


def test_audit_single_missing_run_raises(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    with pytest.raises(AuditError):
        audit_experiment_run(store, "does_not_exist")


@pytest.mark.parametrize("bad", ["../run_a", "a/b", r"a\b", r"C:\run_a", "..", ""])
def test_audit_single_unsafe_run_directory_raises(tmp_path, bad):
    store = _valid_store(tmp_path, ("run_a",))
    with pytest.raises(AuditError):
        audit_experiment_run(store, bad)


def test_audit_single_non_run_raises(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    (store.base_dir / "notes").mkdir()
    with pytest.raises(AuditError):
        audit_experiment_run(store, "notes")


# --------------------------------------------------------------------------- #
# read-only proof + engine guard rails
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("level", [AuditLevel.METADATA_ONLY, AuditLevel.STANDARD, AuditLevel.DEEP])
def test_audit_leaves_store_byte_identical(tmp_path, level):
    store = _valid_store(tmp_path, ("run_a", "run_b"))
    # add a bit of variety so more code paths run during the audit
    (store.base_dir / "run_a" / "extra.json").write_text("{}", encoding="utf-8")
    (store.base_dir / "stray.txt").write_text("x", encoding="utf-8")
    before = _store_snapshot(store.base_dir)
    audit_experiment_store(store, level=level)
    assert _store_snapshot(store.base_dir) == before


def test_audit_creates_no_repo_artifacts(tmp_path):
    before = _repo_snapshot()
    store = _valid_store(tmp_path, ("run_a",))
    audit_experiment_store(store, level=AuditLevel.DEEP)
    assert _repo_snapshot() == before


def test_audit_module_no_mutation_calls():
    src = Path(audit_module.__file__).read_text(encoding="utf-8")
    for token in (
        ".write_text",
        ".write_bytes",
        'open(',
        ".mkdir",
        ".touch",
        ".unlink",
        ".rmdir",
        ".rename",
        ".replace(",
        "rmtree",
        "shutil",
        "to_csv",
        "to_parquet",
        "os.remove",
    ):
        assert token not in src, f"audit.py must not contain mutation call {token!r}"


def test_audit_module_no_forbidden_or_private_imports():
    import re as _re

    src = Path(audit_module.__file__).read_text(encoding="utf-8")
    for private in ("_ABSOLUTE_PATH", "_FRAME_NAMES", "_is_relative_path"):
        assert not _re.search(rf"\b{private}\b", src), f"audit.py must not reference {private!r}"
    forbidden = [
        "list_experiments",
        "load_experiment_run",
        "read_metadata",
        "app.local_pipeline",
        "app.batch_experiments",
        "app.reporting",
        "app.experiment_catalog",
        "run_local_futures_ml_experiment",
        "train_model",
        "build_feature_matrix",
        "build_label_matrix",
        "hashlib",
        "sha256",
        "compute_config_hash",
        "urllib",
        "httpx",
        "socket",
        "yfinance",
        "ibkr",
        "sklearn",
        "xgboost",
        "lightgbm",
        "torch",
        "tensorflow",
    ]
    for token in forbidden:
        assert token not in src, f"audit.py must not reference {token!r}"


# --------------------------------------------------------------------------- #
# renderers (hand-built audit results — no store scanning)
# --------------------------------------------------------------------------- #


def _render_result(findings=None) -> ExperimentStoreAuditResult:
    """A hand-built store result with two runs and three findings across
    severities (info/warning/error), all report-safe (no absolute paths)."""
    if findings is None:
        findings = (
            _finding(
                code=AuditCode.UNEXPECTED_FILE, severity=AuditSeverity.INFO,
                run_directory="run_a", relative_path="notes.txt", message="unexpected file",
            ),
            _finding(
                code=AuditCode.ORPHAN_ARTIFACT, severity=AuditSeverity.WARNING,
                run_directory="run_a", relative_path="extra.json", message="orphan artifact",
            ),
            _finding(
                code=AuditCode.MISSING_REFERENCED_ARTIFACT, severity=AuditSeverity.ERROR,
                run_directory="run_b", artifact_name="predictions",
                relative_path="predictions.csv", message="missing referenced artifact",
            ),
        )
    numbered = sort_and_number_findings(findings)
    by_dir = {}
    for f in numbered:
        by_dir.setdefault(f.run_directory, []).append(f)
    run_meta = [("run_a", "run_a"), ("run_b", "run_b")]
    run_audits = tuple(
        ExperimentRunAudit(
            run_directory=name, train_run_hash=h,
            status=status_for_findings(by_dir.get(name, ())),
            findings=tuple(by_dir.get(name, ())),
        )
        for name, h in run_meta
    )
    from collections import Counter

    return ExperimentStoreAuditResult(
        runs_discovered=2,
        runs_valid=sum(1 for ra in run_audits if ra.status == AuditRunStatus.VALID),
        runs_with_warnings=sum(1 for ra in run_audits if ra.status == AuditRunStatus.WARNING),
        runs_invalid=sum(1 for ra in run_audits if ra.status == AuditRunStatus.INVALID),
        non_run_entries=0,
        findings_total=len(numbered),
        findings_by_severity=dict(Counter(f.severity.value for f in numbered)),
        findings_by_code=dict(Counter(f.code.value for f in numbered)),
        audited_run_hashes=("run_a", "run_b"),
        run_audits=run_audits,
        findings=numbered,
        overall_status=overall_status_for(numbered),
    )


def _empty_result() -> ExperimentStoreAuditResult:
    return ExperimentStoreAuditResult(
        runs_discovered=0, runs_valid=0, runs_with_warnings=0, runs_invalid=0,
        non_run_entries=0, findings_total=0, findings_by_severity={}, findings_by_code={},
        audited_run_hashes=(), run_audits=(), findings=(), overall_status=AuditOverallStatus.OK,
    )


_ADVICE_TOKENS = ("buy", "sell", "allocate", "deploy")


# ---- JSON ---- #


def test_export_json_strict_and_deterministic():
    result = _render_result()
    text = export_audit_json(result)
    assert export_audit_json(result) == text  # deterministic
    payload = json.loads(text)  # strict parse
    json.dumps(payload, allow_nan=False)  # strict re-serialization
    assert text.endswith("\n")
    assert "NaN" not in text and "Infinity" not in text


def test_export_json_stable_top_level_keys():
    payload = json.loads(export_audit_json(_render_result()))
    assert set(payload) == {
        "disclaimers", "overall_status", "runs_discovered", "runs_valid",
        "runs_with_warnings", "runs_invalid", "non_run_entries", "findings_total",
        "findings_by_severity", "findings_by_code", "audited_run_hashes",
        "run_audits", "findings", "displayed_findings_total", "findings_filtered",
    }


def test_export_json_unfiltered_view_flags():
    result = _render_result()
    payload = json.loads(export_audit_json(result))  # no override
    assert payload["findings_filtered"] is False
    assert payload["displayed_findings_total"] == payload["findings_total"]
    assert payload["displayed_findings_total"] == len(payload["findings"])
    # an explicit override equal to the canonical findings is still "unfiltered"
    same = json.loads(export_audit_json(result, findings=list(result.findings)))
    assert same["findings_filtered"] is False


def test_export_json_filtered_view_flags():
    result = _render_result()
    errors = [f for f in result.findings if f.severity == AuditSeverity.ERROR]
    assert len(errors) == 1
    payload = json.loads(export_audit_json(result, findings=errors))
    assert payload["findings_filtered"] is True
    assert payload["findings_total"] == 3            # canonical count preserved
    assert payload["displayed_findings_total"] == 1  # == len(exported findings)
    assert payload["displayed_findings_total"] < payload["findings_total"]
    assert len(payload["findings"]) == 1
    # original finding id preserved (not renumbered)
    assert payload["findings"][0]["finding_id"] == errors[0].finding_id


def test_export_json_content_and_order():
    payload = json.loads(export_audit_json(_render_result()))
    assert payload["disclaimers"] == list(AUDIT_DISCLAIMERS)
    assert payload["overall_status"] == "failed"
    assert payload["audited_run_hashes"] == ["run_a", "run_b"]
    assert [f["finding_id"] for f in payload["findings"]] == [
        "finding_0000", "finding_0001", "finding_0002",
    ]
    assert [ra["run_directory"] for ra in payload["run_audits"]] == ["run_a", "run_b"]


def test_export_json_none_becomes_null():
    payload = json.loads(export_audit_json(_render_result()))
    info_finding = next(f for f in payload["findings"] if f["code"] == "UNEXPECTED_FILE")
    assert info_finding["train_run_hash"] is None
    assert info_finding["artifact_name"] is None


def test_export_json_no_paths_or_timestamps():
    import re as _re

    text = export_audit_json(_render_result())
    assert ":\\" not in text and ":/" not in text
    assert _re.search(r"\d{4}-\d{2}-\d{2}T", text) is None  # no ISO timestamp


def test_export_json_empty_result():
    payload = json.loads(export_audit_json(_empty_result()))
    assert payload["findings"] == [] and payload["run_audits"] == []
    assert payload["disclaimers"] == list(AUDIT_DISCLAIMERS)


# ---- CSV ---- #


def test_export_csv_deterministic_and_headers():
    result = _render_result()
    text = export_audit_csv(result)
    assert export_audit_csv(result) == text
    lines = text.splitlines()
    assert lines[0] == (
        "finding_id,severity,code,run_directory,train_run_hash,"
        "artifact_name,relative_path,expected,actual,message"
    )
    assert len(lines) == 1 + result.findings_total  # header + one row per finding


def test_export_csv_none_becomes_empty():
    import csv as _csv

    rows = list(_csv.reader(io.StringIO(export_audit_csv(_render_result()))))
    info_row = next(r for r in rows[1:] if r[2] == "UNEXPECTED_FILE")
    # columns: 0 finding_id,1 severity,2 code,3 run_directory,4 train_run_hash,
    #          5 artifact_name,6 relative_path,7 expected,8 actual,9 message
    assert info_row[4] == "" and info_row[5] == "" and info_row[6] == "notes.txt"


def test_export_csv_header_only_for_zero_findings():
    text = export_audit_csv(_empty_result())
    assert text.strip().splitlines() == [
        "finding_id,severity,code,run_directory,train_run_hash,"
        "artifact_name,relative_path,expected,actual,message"
    ]


def test_export_csv_escapes_special_characters():
    import csv as _csv

    tricky = _finding(
        code=AuditCode.UNEXPECTED_FILE, severity=AuditSeverity.INFO,
        run_directory="run_a", message='has, comma "quote" and\nnewline',
    )
    text = export_audit_csv(_render_result(findings=(tricky,)))
    rows = list(_csv.reader(io.StringIO(text)))
    assert rows[1][-1] == 'has, comma "quote" and\nnewline'  # round-trips exactly


def test_export_csv_no_paths_or_nan():
    text = export_audit_csv(_render_result())
    assert ":\\" not in text and "NaN" not in text and "Infinity" not in text


# ---- Markdown ---- #


def test_export_markdown_deterministic_sections():
    result = _render_result()
    text = export_audit_markdown(result)
    assert export_audit_markdown(result) == text
    for heading in (
        "# ExperimentStore Integrity Audit",
        "**Overall status:** failed",
        "## Summary",
        "## Findings by severity",
        "## Findings by code",
        "## Audited runs",
        "## Findings",
        "## Scope & Safety",
    ):
        assert heading in text


def test_export_markdown_all_disclaimers_present():
    text = export_audit_markdown(_render_result())
    for disclaimer in AUDIT_DISCLAIMERS:
        assert f"- {disclaimer}" in text


def test_export_markdown_shows_both_counts_and_filtered_note():
    result = _render_result()
    # unfiltered: both counts present, no filtered-view note
    full = export_audit_markdown(result)
    assert "| findings_total | 3 |" in full
    assert "| findings_displayed | 3 |" in full
    assert "filtered view" not in full
    # filtered: displayed count differs and the factual note appears
    errors = [f for f in result.findings if f.severity == AuditSeverity.ERROR]
    filtered = export_audit_markdown(result, findings=errors)
    assert "| findings_total | 3 |" in filtered          # canonical preserved
    assert "| findings_displayed | 1 |" in filtered
    assert (
        "The findings table is a filtered view; summary counts describe the "
        "complete audit result." in filtered
    )


def test_export_markdown_zero_findings_renders_all_sections():
    text = export_audit_markdown(_empty_result())
    for heading in (
        "## Summary", "## Findings by severity", "## Findings by code",
        "## Audited runs", "## Findings", "## Scope & Safety",
    ):
        assert heading in text
    for disclaimer in AUDIT_DISCLAIMERS:
        assert f"- {disclaimer}" in text


def test_export_markdown_escapes_pipes_and_newlines():
    tricky = _finding(
        code=AuditCode.UNEXPECTED_FILE, severity=AuditSeverity.INFO,
        run_directory="run_a", message="pipe | here\nand newline",
    )
    text = export_audit_markdown(_render_result(findings=(tricky,)))
    assert "pipe \\| here and newline" in text  # pipe escaped, newline collapsed


def test_export_markdown_no_paths_nan_or_advice():
    text = export_audit_markdown(_render_result()).lower()
    assert ":\\" not in text and "nan" not in text.replace("scan", "") and "infinity" not in text
    for token in _ADVICE_TOKENS:
        assert token not in text, f"advice token {token!r} leaked into markdown"


# ---- render read-only + boundaries ---- #


def test_renderers_do_not_mutate_result():
    result = _render_result()
    before = result.to_dict()
    export_audit_json(result)
    export_audit_csv(result)
    export_audit_markdown(result)
    assert result.to_dict() == before


def test_render_module_no_mutation_or_forbidden_imports():
    import re as _re

    src = Path(render_module.__file__).read_text(encoding="utf-8")
    for token in (
        ".write_text", ".write_bytes", "open(", ".mkdir", ".touch", ".unlink",
        ".rmdir", ".rename", "rmtree", "shutil", "to_csv", "to_parquet", "os.remove",
    ):
        assert token not in src, f"render.py must not contain mutation call {token!r}"
    for private in ("_ABSOLUTE_PATH", "_FRAME_NAMES", "_is_relative_path"):
        assert not _re.search(rf"\b{private}\b", src)
    forbidden = [
        "app.experiments",
        "app.reporting",
        "app.experiment_catalog",
        "app.local_pipeline",
        "app.batch_experiments",
        "run_local_futures_ml_experiment",
        "train_model",
        "build_feature_matrix",
        "build_label_matrix",
        "hashlib",
        "sha256",
        "compute_config_hash",
        "urllib",
        "httpx",
        "socket",
        "yfinance",
        "ibkr",
        "sklearn",
        "xgboost",
        "lightgbm",
        "torch",
        "tensorflow",
    ]
    for token in forbidden:
        assert token not in src, f"render.py must not reference {token!r}"


def test_renderers_create_no_repo_artifacts():
    before = _repo_snapshot()
    result = _render_result()
    export_audit_json(result)
    export_audit_csv(result)
    export_audit_markdown(result)
    assert _repo_snapshot() == before


# --------------------------------------------------------------------------- #
# CLI — scripts/audit_experiment_store.py
# --------------------------------------------------------------------------- #

_AUDIT_CLI_PATH = _REPO_ROOT / "scripts" / "audit_experiment_store.py"


def _load_audit_cli():
    spec = importlib.util.spec_from_file_location("audit_cli", _AUDIT_CLI_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _warning_store(tmp_path) -> ExperimentStore:
    store = _valid_store(tmp_path, ("run_a",))
    (store.base_dir / "run_a" / "extra.json").write_text("{}", encoding="utf-8")  # orphan -> warning
    return store


def _error_store(tmp_path) -> ExperimentStore:
    store = _valid_store(tmp_path, ("run_a",))
    (store.base_dir / "run_a" / "predictions.csv").unlink()  # missing referenced -> error
    return store


def _critical_store(tmp_path) -> ExperimentStore:
    store = _valid_store(tmp_path, ("run_a",))
    _rewrite_metadata(
        store, "run_a", lambda d: d["artifact_paths"].__setitem__("predictions", "../evil.csv")
    )  # path traversal -> critical
    return store


def _cli(store, *extra):
    return [*("--artifacts-dir", str(store.base_dir)), *extra]


# ---- success + status/exit matrix ---- #


def test_cli_clean_store_ok(tmp_path, capsys):
    store = _valid_store(tmp_path, ("run_a", "run_b"))
    code = _load_audit_cli().main(_cli(store, "--no-parquet"))
    out = capsys.readouterr().out
    assert code == 0 and "RESULT: OK" in out
    assert "overall_status=ok runs_discovered=2 runs_valid=2" in out
    assert "findings_total=0" in out


def test_cli_warning_default_fail_on(tmp_path, capsys):
    store = _warning_store(tmp_path)
    code = _load_audit_cli().main(_cli(store, "--no-parquet"))
    out = capsys.readouterr().out
    assert code == 0 and "RESULT: WARNING" in out  # warning-only, default fail-on=error -> exit 0


def test_cli_warning_fail_on_warning(tmp_path, capsys):
    store = _warning_store(tmp_path)
    code = _load_audit_cli().main(_cli(store, "--no-parquet", "--fail-on", "warning"))
    out = capsys.readouterr().out
    assert code == 1 and "RESULT: WARNING" in out  # RESULT reflects status; exit reflects fail-on


def test_cli_error_default_fail_on(tmp_path, capsys):
    store = _error_store(tmp_path)
    code = _load_audit_cli().main(_cli(store, "--no-parquet"))
    out = capsys.readouterr().out
    assert code == 1 and "RESULT: FAIL" in out
    assert "MISSING_REFERENCED_ARTIFACT" in out


@pytest.mark.parametrize("fail_on", ["warning", "error", "critical"])
def test_cli_critical_exits_1_for_all_thresholds(tmp_path, capsys, fail_on):
    store = _critical_store(tmp_path)
    code = _load_audit_cli().main(_cli(store, "--no-parquet", "--fail-on", fail_on))
    out = capsys.readouterr().out
    assert code == 1 and "RESULT: FAIL" in out
    assert "PATH_TRAVERSAL" in out


@pytest.mark.parametrize("level", ["metadata-only", "standard", "deep"])
def test_cli_level_dispatch(tmp_path, capsys, level):
    store = _valid_store(tmp_path, ("run_a",))
    code = _load_audit_cli().main(_cli(store, "--no-parquet", "--level", level))
    assert code == 0 and "RESULT: OK" in capsys.readouterr().out


def test_cli_single_run(tmp_path, capsys):
    store = _valid_store(tmp_path, ("run_a", "run_b"))
    code = _load_audit_cli().main(_cli(store, "--no-parquet", "--run-hash", "run_a"))
    out = capsys.readouterr().out
    assert code == 0 and "RESULT: OK" in out
    assert "runs_discovered=1" in out  # only the one run


# ---- severity filter + non-run behavior ---- #


def test_cli_severity_filters_display_but_not_exit(tmp_path, capsys):
    # store has an info UNEXPECTED_FILE + an error MISSING_REFERENCED_ARTIFACT
    store = _error_store(tmp_path)
    (store.base_dir / "run_a" / "notes.txt").write_text("x", encoding="utf-8")  # info
    code = _load_audit_cli().main(_cli(store, "--no-parquet", "--severity", "error"))
    out = capsys.readouterr().out
    assert code == 1  # error still triggers default fail-on
    assert "MISSING_REFERENCED_ARTIFACT" in out
    assert "UNEXPECTED_FILE" not in out  # info filtered from display
    assert "RESULT: FAIL" in out  # canonical status unaffected by the display filter


def test_cli_filtered_findings_keep_original_ids(tmp_path, capsys):
    store = _error_store(tmp_path)
    (store.base_dir / "run_a" / "notes.txt").write_text("x", encoding="utf-8")
    # unfiltered: capture the id of the error finding
    _load_audit_cli().main(_cli(store, "--no-parquet"))
    full = capsys.readouterr().out
    err_line = next(ln for ln in full.splitlines() if "MISSING_REFERENCED_ARTIFACT" in ln)
    err_id = err_line.split("]")[0].lstrip("[")
    # filtered: the same finding keeps the same id (no renumbering)
    _load_audit_cli().main(_cli(store, "--no-parquet", "--severity", "error"))
    filtered = capsys.readouterr().out
    assert f"[{err_id}]" in filtered


def test_cli_non_run_info_hidden_by_default(tmp_path, capsys):
    store = _valid_store(tmp_path, ("run_a",))
    (store.base_dir / "stray.txt").write_text("x", encoding="utf-8")  # ROOT_LEVEL_FILE (info)
    _load_audit_cli().main(_cli(store, "--no-parquet"))
    default_out = capsys.readouterr().out
    assert "ROOT_LEVEL_FILE" not in default_out  # hidden by default
    _load_audit_cli().main(_cli(store, "--no-parquet", "--include-non-run-entries"))
    included_out = capsys.readouterr().out
    assert "ROOT_LEVEL_FILE" in included_out


def test_cli_console_shows_both_counts(tmp_path, capsys):
    # store with an info UNEXPECTED_FILE (hidden by --severity error) + an error
    store = _error_store(tmp_path)
    (store.base_dir / "run_a" / "notes.txt").write_text("x", encoding="utf-8")
    _load_audit_cli().main(_cli(store, "--no-parquet", "--severity", "error"))
    out = capsys.readouterr().out
    summary = next(ln for ln in out.splitlines() if ln.startswith("overall_status="))
    assert "findings_total=" in summary and "displayed_findings_total=" in summary
    # displayed is filtered below the canonical total (the info finding is hidden)
    total = int(summary.split("findings_total=")[1].split()[0])
    displayed = int(summary.split("displayed_findings_total=")[1].split()[0])
    assert displayed < total


def test_cli_output_json_records_filtered_view(tmp_path, capsys):
    store = _error_store(tmp_path)
    (store.base_dir / "run_a" / "notes.txt").write_text("x", encoding="utf-8")
    out_path = tmp_path / "audit.json"
    _load_audit_cli().main(
        _cli(store, "--no-parquet", "--severity", "error", "--output-json", str(out_path))
    )
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["findings_filtered"] is True
    assert payload["displayed_findings_total"] == len(payload["findings"])
    assert payload["displayed_findings_total"] < payload["findings_total"]


def test_cli_missing_metadata_warning_never_hidden(tmp_path, capsys):
    store = _valid_store(tmp_path, ("run_a",))
    half = store.base_dir / "half_run"
    half.mkdir()
    (half / "metrics.json").write_text("{}", encoding="utf-8")  # MISSING_METADATA (warning)
    _load_audit_cli().main(_cli(store, "--no-parquet"))  # no --include-non-run-entries
    out = capsys.readouterr().out
    assert "MISSING_METADATA" in out  # warnings are never hidden


# ---- output files ---- #


def test_cli_output_json(tmp_path, capsys):
    store = _error_store(tmp_path)
    out_path = tmp_path / "reports" / "audit.json"
    code = _load_audit_cli().main(_cli(store, "--no-parquet", "--output-json", str(out_path)))
    out = capsys.readouterr().out
    assert code == 1 and f"[JSON] path={out_path}" in out
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    json.dumps(payload, allow_nan=False)
    assert payload["overall_status"] == "failed"
    assert [p.name for p in (tmp_path / "reports").iterdir()] == ["audit.json"]


def test_cli_output_csv(tmp_path, capsys):
    store = _error_store(tmp_path)
    out_path = tmp_path / "audit.csv"
    code = _load_audit_cli().main(_cli(store, "--no-parquet", "--output-csv", str(out_path)))
    assert code == 1
    assert out_path.read_text(encoding="utf-8").splitlines()[0].startswith("finding_id,severity,code,")


def test_cli_output_markdown_has_disclaimers(tmp_path, capsys):
    from app.experiment_audit import AUDIT_DISCLAIMERS

    store = _valid_store(tmp_path, ("run_a",))
    out_path = tmp_path / "audit.md"
    _load_audit_cli().main(_cli(store, "--no-parquet", "--output-markdown", str(out_path)))
    text = out_path.read_text(encoding="utf-8")
    assert "## Scope & Safety" in text
    for disclaimer in AUDIT_DISCLAIMERS:
        assert disclaimer in text


def test_cli_multiple_outputs_and_determinism(tmp_path, capsys):
    store = _warning_store(tmp_path)
    j, c, m = tmp_path / "a.json", tmp_path / "a.csv", tmp_path / "a.md"
    _load_audit_cli().main(
        _cli(store, "--no-parquet", "--output-json", str(j), "--output-csv", str(c), "--output-markdown", str(m))
    )
    out = capsys.readouterr().out
    assert all(x in out for x in ("[JSON] path=", "[CSV] path=", "[MARKDOWN] path="))

    def _read3():
        return (
            j.read_text(encoding="utf-8"),
            c.read_text(encoding="utf-8"),
            m.read_text(encoding="utf-8"),
        )

    first = _read3()
    _load_audit_cli().main(
        _cli(store, "--no-parquet", "--output-json", str(j), "--output-csv", str(c), "--output-markdown", str(m))
    )
    assert _read3() == first  # deterministic


def test_cli_no_outputs_writes_nothing_outside_store(tmp_path):
    store = _valid_store(tmp_path, ("run_a",))
    before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    _load_audit_cli().main(_cli(store, "--no-parquet"))
    after = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    assert after == before  # no files created


# ---- runtime failures -> exit 3 (no traceback) ---- #


def test_cli_missing_root_exit_3(tmp_path, capsys):
    code = _load_audit_cli().main(["--artifacts-dir", str(tmp_path / "nope")])
    out = capsys.readouterr().out
    assert code == 3 and "RESULT: FAIL" in out and "Traceback" not in out


def test_cli_root_is_file_exit_3(tmp_path, capsys):
    f = tmp_path / "afile"
    f.write_text("x", encoding="utf-8")
    code = _load_audit_cli().main(["--artifacts-dir", str(f)])
    assert code == 3 and "RESULT: FAIL" in capsys.readouterr().out


@pytest.mark.parametrize("bad", ["../run_a", "a/b", r"C:\run_a"])
def test_cli_unsafe_run_hash_exit_3(tmp_path, capsys, bad):
    store = _valid_store(tmp_path, ("run_a",))
    code = _load_audit_cli().main(_cli(store, "--run-hash", bad))
    assert code == 3 and "RESULT: FAIL" in capsys.readouterr().out


def test_cli_missing_run_hash_exit_3(tmp_path, capsys):
    store = _valid_store(tmp_path, ("run_a",))
    code = _load_audit_cli().main(_cli(store, "--run-hash", "no_such_run"))
    assert code == 3 and "RESULT: FAIL" in capsys.readouterr().out


def test_cli_non_run_run_hash_exit_3(tmp_path, capsys):
    store = _valid_store(tmp_path, ("run_a",))
    (store.base_dir / "notes").mkdir()
    code = _load_audit_cli().main(_cli(store, "--run-hash", "notes"))
    assert code == 3 and "RESULT: FAIL" in capsys.readouterr().out


def test_cli_unwritable_output_exit_3(tmp_path, capsys):
    store = _valid_store(tmp_path, ("run_a",))
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")  # a file where a parent dir is expected
    bad_out = blocker / "sub" / "audit.json"
    code = _load_audit_cli().main(_cli(store, "--no-parquet", "--output-json", str(bad_out)))
    assert code == 3 and "RESULT: FAIL" in capsys.readouterr().out


# ---- argparse usage -> SystemExit 2 ---- #


@pytest.mark.parametrize(
    "argv",
    [
        [],  # missing --artifacts-dir
        ["--artifacts-dir", "x", "--level", "bogus"],
        ["--artifacts-dir", "x", "--severity", "bogus"],
        ["--artifacts-dir", "x", "--fail-on", "bogus"],
    ],
)
def test_cli_argparse_usage_exit_2(argv):
    cli = _load_audit_cli()
    with pytest.raises(SystemExit) as excinfo:
        cli.main(argv)
    assert excinfo.value.code == 2


# ---- read-only + boundaries ---- #


@pytest.mark.parametrize("level", ["metadata-only", "standard", "deep"])
def test_cli_leaves_store_byte_identical(tmp_path, level):
    store = _warning_store(tmp_path)
    before = _store_snapshot(store.base_dir)
    _load_audit_cli().main(
        _cli(store, "--no-parquet", "--level", level, "--output-json", str(tmp_path / "o.json"))
    )
    assert _store_snapshot(store.base_dir) == before  # audited store unchanged


def test_cli_creates_no_repo_artifacts(tmp_path, capsys):
    before = _repo_snapshot()
    store = _valid_store(tmp_path, ("run_a",))
    _load_audit_cli().main(_cli(store, "--no-parquet"))
    assert _repo_snapshot() == before


def test_cli_module_no_forbidden_imports_or_advice():
    import re as _re

    src = Path(_AUDIT_CLI_PATH).read_text(encoding="utf-8")
    for private in ("_ABSOLUTE_PATH", "_FRAME_NAMES", "_is_relative_path"):
        assert not _re.search(rf"\b{private}\b", src)
    forbidden = [
        "app.local_pipeline",
        "app.batch_experiments",
        "app.reporting",
        "app.experiment_catalog",
        "run_local_futures_ml_experiment",
        "train_model",
        "build_feature_matrix",
        "build_label_matrix",
        "hashlib",
        "sha256",
        "compute_config_hash",
        "urllib",
        "httpx",
        "socket",
        "yfinance",
        "ibkr",
        "sklearn",
        "xgboost",
        "lightgbm",
        "torch",
        "tensorflow",
        "rmtree",
        ".unlink",
        "shutil",
    ]
    for token in forbidden:
        assert token not in src, f"CLI must not reference {token!r}"
    lowered = src.lower()
    for token in ("buy", "sell", "allocate", "deploy"):
        assert token not in lowered, f"advice token {token!r} in CLI source"
