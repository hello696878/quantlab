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
    audit_experiment_run,
    audit_experiment_store,
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
