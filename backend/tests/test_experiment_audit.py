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
    AuditOverallStatus,
    AuditRunStatus,
    AuditSeverity,
    ExperimentRunAudit,
    ExperimentStoreAuditResult,
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
)
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
