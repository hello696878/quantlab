"""
Phase 14 commit 1 — evidence-pack models, aggregation findings, JSON-safety
helpers, and completeness derivation.

Covers ``app.experiment_review.models`` only (no collector / renderers / CLI yet).
Everything is pure and in-memory: no store, no database, no filesystem access, no
network.  Phase 13 ``AuditFinding`` objects are constructed through their public
API and must be preserved verbatim (ids / codes / severities) — never converted
into the Phase 14 ``evidence_`` namespace.
"""

from __future__ import annotations

import dataclasses
import json
import math
from pathlib import Path

import pytest

from app.experiment_audit import AuditCode, AuditFinding, AuditSeverity
from app.experiment_review import (
    ArtifactInventoryEntry,
    CatalogRunContext,
    ComparisonEvidence,
    EvidenceCode,
    EvidenceCompleteness,
    EvidenceComparisonStatus,
    EvidenceContextStatus,
    EvidenceError,
    EvidenceFinding,
    EvidenceLoadStatus,
    EvidenceSeverity,
    EvidenceSummary,
    ExperimentEvidencePack,
    ExperimentRunEvidence,
    dedupe_preserve_order,
    derive_pack_completeness,
    derive_run_completeness,
    evidence_finding_sort_key,
    evidence_severity_at_least,
    evidence_severity_rank,
    freeze_json_value,
    sanitize_json_value,
    sort_and_number_evidence_findings,
    thaw_json_value,
)
from app.experiment_review import models as models_module
from app.experiment_review.models import (
    EVIDENCE_REDACTED_PATH,
    is_host_absolute_path,
    redact_host_absolute_text,
    safe_audit_finding_dict,
)

_BACKEND = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _repo_snapshot() -> tuple[bool, bool, bool]:
    return (
        (_REPO_ROOT / "data").exists(),
        (_REPO_ROOT / "artifacts").exists(),
        (_REPO_ROOT / "reports").exists(),
    )


def _audit_finding(severity="warning", code=AuditCode.ORPHAN_ARTIFACT, **kw) -> AuditFinding:
    base = dict(severity=severity, code=code, message="m", run_directory="run_a")
    base.update(kw)
    return AuditFinding(**base)


def _ev_finding(code=EvidenceCode.COMPARISON_UNAVAILABLE, severity=EvidenceSeverity.WARNING, **kw):
    base = dict(severity=severity, code=code, message="m")
    base.update(kw)
    return EvidenceFinding(**base)


# --------------------------------------------------------------------------- #
# enums
# --------------------------------------------------------------------------- #


def test_enum_values():
    assert [s.value for s in EvidenceSeverity] == ["info", "warning", "error"]
    assert {c.value for c in EvidenceCode} == {
        "RUN_NOT_FOUND", "RUN_UNLOADABLE", "COMPARISON_UNAVAILABLE",
        "INCOMPATIBLE_SELECTED_RUNS", "REQUESTED_METRIC_MISSING",
        "CATALOG_CONTEXT_UNAVAILABLE", "EVIDENCE_INCOMPLETE",
    }
    assert {s.value for s in EvidenceCompleteness} == {"complete", "warning", "incomplete", "unavailable"}
    assert {s.value for s in EvidenceLoadStatus} == {"loaded", "unloadable", "unavailable"}
    assert {s.value for s in EvidenceContextStatus} == {"collected", "not_collected", "unavailable"}
    assert {s.value for s in EvidenceComparisonStatus} == {"available", "not_applicable", "unavailable"}


def test_enum_values_unique():
    for enum in (EvidenceSeverity, EvidenceCode, EvidenceCompleteness, EvidenceLoadStatus,
                 EvidenceContextStatus, EvidenceComparisonStatus):
        values = [m.value for m in enum]
        assert len(values) == len(set(values))


def test_no_approval_or_deployment_vocabulary():
    all_values = {
        m.value.lower()
        for enum in (EvidenceSeverity, EvidenceCode, EvidenceCompleteness, EvidenceLoadStatus,
                     EvidenceContextStatus, EvidenceComparisonStatus)
        for m in enum
    }
    for forbidden in ("approved", "rejected", "deployable", "production_ready", "profitable",
                      "tradeable", "deploy", "trade"):
        assert not any(forbidden in v for v in all_values)


# --------------------------------------------------------------------------- #
# EvidenceFinding
# --------------------------------------------------------------------------- #


def test_evidence_finding_frozen_and_to_dict():
    f = _ev_finding(train_run_hash="run_a", context={"reason": "single run"})
    with pytest.raises(dataclasses.FrozenInstanceError):
        f.message = "x"
    d = f.to_dict()
    assert d["code"] == "COMPARISON_UNAVAILABLE" and d["severity"] == "warning"
    assert d["context"] == {"reason": "single run"}
    assert f.to_dict() == d  # deterministic
    json.dumps(d, allow_nan=False)


def test_evidence_finding_empty_and_evidence_id_accepted():
    assert _ev_finding().finding_id == ""
    assert _ev_finding(finding_id="evidence_0000").finding_id == "evidence_0000"


def test_evidence_finding_rejects_phase13_namespace():
    with pytest.raises(EvidenceError):
        _ev_finding(finding_id="finding_0000")


def test_evidence_finding_rejects_bad_type_context():
    with pytest.raises(EvidenceError):
        _ev_finding(context=Path("C:/x"))  # no pathlib.Path


def test_evidence_finding_sort_and_number_deterministic():
    findings = (
        _ev_finding(code=EvidenceCode.RUN_NOT_FOUND, train_run_hash="run_b", message="z"),
        _ev_finding(code=EvidenceCode.RUN_NOT_FOUND, train_run_hash="run_a", message="a"),
        _ev_finding(code=EvidenceCode.COMPARISON_UNAVAILABLE, train_run_hash="run_a", message="a"),
    )
    numbered = sort_and_number_evidence_findings(findings)
    assert [f.finding_id for f in numbered] == ["evidence_0000", "evidence_0001", "evidence_0002"]
    # sorted by (train_run_hash, code, context, message): run_a COMPARISON before run_a RUN_NOT_FOUND
    assert [f.train_run_hash for f in numbered] == ["run_a", "run_a", "run_b"]
    assert numbered[0].code == EvidenceCode.COMPARISON_UNAVAILABLE
    assert sort_and_number_evidence_findings(findings) == numbered  # deterministic


def test_sort_and_number_does_not_mutate_input():
    original = _ev_finding()
    assert original.finding_id == ""
    sort_and_number_evidence_findings((original,))
    assert original.finding_id == ""


def test_evidence_severity_helpers():
    assert evidence_severity_rank("info") < evidence_severity_rank("warning") < evidence_severity_rank("error")
    assert evidence_severity_at_least(EvidenceSeverity.ERROR, EvidenceSeverity.WARNING)
    assert not evidence_severity_at_least(EvidenceSeverity.INFO, EvidenceSeverity.WARNING)


# --------------------------------------------------------------------------- #
# JSON-safe helpers
# --------------------------------------------------------------------------- #


def test_freeze_thaw_deterministic_key_order():
    frozen = freeze_json_value({"b": 1, "a": {"y": 2, "x": 3}})
    plain = thaw_json_value(frozen)
    assert list(plain) == ["a", "b"]  # keys sorted
    assert list(plain["a"]) == ["x", "y"]


def test_freeze_does_not_retain_mutable_input():
    src = {"k": [1, 2]}
    frozen = freeze_json_value(src)
    src["k"].append(999)
    src["new"] = "x"
    assert thaw_json_value(frozen) == {"k": [1, 2]}  # unaffected


def test_sanitize_nan_infinity_to_none():
    out = sanitize_json_value({"a": float("nan"), "b": float("inf"), "c": [float("-inf"), 1.5]})
    assert out == {"a": None, "b": None, "c": [None, 1.5]}
    json.dumps(out, allow_nan=False)


def test_freeze_nested_lists_and_maps():
    value = {"rows": [{"m": 1}, {"m": 2}], "n": None, "ok": True, "i": 7}
    assert sanitize_json_value(value) == value


def test_freeze_rejects_non_json_type():
    with pytest.raises(EvidenceError):
        freeze_json_value({"p": Path("C:/x")})


# --------------------------------------------------------------------------- #
# ArtifactInventoryEntry
# --------------------------------------------------------------------------- #


def test_artifact_inventory_tristate():
    e = ArtifactInventoryEntry(artifact_name="predictions", relative_path="predictions.csv",
                               exists=True, regular_file=True, format="csv",
                               audit_finding_codes=("ORPHAN_ARTIFACT",))
    assert e.to_dict()["exists"] is True and e.to_dict()["regular_file"] is True
    # metadata-only unknown state
    u = ArtifactInventoryEntry(artifact_name="signal")
    assert u.exists is None and u.regular_file is None and u.relative_path is None


def test_artifact_inventory_unsafe_path_is_none_not_absolute():
    # collector sets relative_path=None for unsafe paths; an absolute value is rejected
    ok = ArtifactInventoryEntry(artifact_name="predictions", relative_path=None, exists=None)
    assert ok.relative_path is None
    with pytest.raises(EvidenceError):
        ArtifactInventoryEntry(artifact_name="predictions", relative_path=r"C:\evil.csv")
    with pytest.raises(EvidenceError):
        ArtifactInventoryEntry(artifact_name="predictions", relative_path="../escape.csv")


def test_artifact_inventory_bad_tristate_rejected():
    with pytest.raises(EvidenceError):
        ArtifactInventoryEntry(artifact_name="x", exists="yes")


# --------------------------------------------------------------------------- #
# CatalogRunContext
# --------------------------------------------------------------------------- #


def test_catalog_context_neutral_no_metric():
    c = CatalogRunContext(status=EvidenceContextStatus.COLLECTED, compatibility_group="group_0000",
                          group_size=3, peer_train_run_hashes=("run_b", "run_a"))
    assert c.requested_metric is None and c.requested_metric_value is None and c.rank is None
    assert c.peer_train_run_hashes == ("run_a", "run_b")  # deduped + sorted


def test_catalog_context_positive_rank_and_duplicate_peers():
    with pytest.raises(EvidenceError):
        CatalogRunContext(status=EvidenceContextStatus.COLLECTED, requested_metric="sharpe", rank=0)
    c = CatalogRunContext(status=EvidenceContextStatus.COLLECTED,
                          peer_train_run_hashes=("run_a", "run_a", "run_b"))
    assert c.peer_train_run_hashes == ("run_a", "run_b")  # duplicates removed


def test_catalog_context_rank_requires_metric():
    with pytest.raises(EvidenceError):
        CatalogRunContext(status=EvidenceContextStatus.COLLECTED, rank=1)  # rank without metric


def test_catalog_context_no_recommendation_fields():
    field_names = {f.name for f in dataclasses.fields(CatalogRunContext)}
    for forbidden in ("winner", "best", "recommended", "recommendation", "deploy"):
        assert forbidden not in field_names


# --------------------------------------------------------------------------- #
# ComparisonEvidence
# --------------------------------------------------------------------------- #


def test_comparison_not_applicable_single_run():
    c = ComparisonEvidence(status=EvidenceComparisonStatus.NOT_APPLICABLE, selected_run_hashes=("run_a",))
    assert c.rows == () and c.unavailable_reason is None


def test_comparison_available_shape():
    c = ComparisonEvidence(status=EvidenceComparisonStatus.AVAILABLE,
                           selected_run_hashes=("run_a", "run_b"),
                           rows=({"train_run_hash": "run_a", "sharpe": 1.5},),
                           disclaimers=("not investment advice",))
    assert c.to_dict()["rows"] == [{"train_run_hash": "run_a", "sharpe": 1.5}]
    with pytest.raises(EvidenceError):
        ComparisonEvidence(status=EvidenceComparisonStatus.AVAILABLE, selected_run_hashes=("run_a",), rows=({"x": 1},))
    with pytest.raises(EvidenceError):  # available must not carry a reason
        ComparisonEvidence(status=EvidenceComparisonStatus.AVAILABLE, selected_run_hashes=("a", "b"),
                           rows=({"x": 1},), unavailable_reason="nope")


def test_comparison_unavailable_requires_reason():
    with pytest.raises(EvidenceError):
        ComparisonEvidence(status=EvidenceComparisonStatus.UNAVAILABLE, selected_run_hashes=("a", "b"))
    c = ComparisonEvidence(status=EvidenceComparisonStatus.UNAVAILABLE, selected_run_hashes=("a", "b"),
                           unavailable_reason="incompatible windows")
    assert c.rows == ()


def test_comparison_no_winner_field():
    field_names = {f.name for f in dataclasses.fields(ComparisonEvidence)}
    for forbidden in ("winner", "best", "top_run", "recommended"):
        assert forbidden not in field_names


# --------------------------------------------------------------------------- #
# ExperimentRunEvidence + Phase 13 preservation
# --------------------------------------------------------------------------- #


def _loaded_run(hash_="run_a", *, audit_findings=(), completeness=EvidenceCompleteness.COMPLETE,
                audit_status="valid", **kw) -> ExperimentRunEvidence:
    base = dict(
        train_run_hash=hash_, run_directory=hash_, load_status=EvidenceLoadStatus.LOADED,
        completeness=completeness, audit_status=audit_status, audit_findings=audit_findings,
        created_at="2026-07-17T00:00:00+00:00",
        train_start="2024-04-01", train_end="2024-06-05",
        validation_start="2024-06-06", validation_end="2024-09-15",
        feature_columns=("feature__return_20",), label_column="label__forward_return_1",
        model_type="ridge_regression", task_type="regression",
        metrics={"sharpe": 1.5, "weird": float("nan")}, baseline_metrics={"no_trade": {"sharpe": 0.0}},
        hash_chain={"train_run_hash": hash_, "model_config_hash": "m1"},
    )
    base.update(kw)
    return ExperimentRunEvidence(**base)


def test_loaded_run_serialization_json_safe():
    run = _loaded_run()
    d = run.to_dict()
    text = json.dumps(d, allow_nan=False, sort_keys=True)
    assert json.loads(text)["metrics"]["weird"] is None  # NaN sanitized
    assert d["feature_columns"] == ["feature__return_20"]
    assert ":\\" not in text  # no absolute path


def test_run_preserves_phase13_finding_ids_verbatim():
    audit = AuditFinding(finding_id="finding_0002", severity="error",
                         code=AuditCode.MISSING_REFERENCED_ARTIFACT, message="missing",
                         run_directory="run_a", artifact_name="predictions")
    run = _loaded_run(audit_findings=(audit,), completeness=EvidenceCompleteness.INCOMPLETE,
                      audit_status="invalid")
    serialized = run.to_dict()["audit_findings"][0]
    assert serialized["finding_id"] == "finding_0002"  # NOT renumbered to evidence_*
    assert serialized["code"] == "MISSING_REFERENCED_ARTIFACT" and serialized["severity"] == "error"
    # the stored object is the original AuditFinding, unchanged
    assert run.audit_findings[0] is audit


def test_run_immutable_nested_metrics():
    src = {"sharpe": 1.0}
    run = _loaded_run(metrics=src)
    src["sharpe"] = 999.0
    assert run.to_dict()["metrics"] == {"sharpe": 1.0}  # frozen copy unaffected


def test_run_no_invented_provenance_fields():
    field_names = {f.name for f in dataclasses.fields(ExperimentRunEvidence)}
    for absent in ("root_symbol", "source", "raw_data_version_hash"):
        assert absent not in field_names


def test_run_artifact_ordering_deterministic():
    run = _loaded_run(artifact_inventory=(
        ArtifactInventoryEntry(artifact_name="signal", relative_path="signal.csv"),
        ArtifactInventoryEntry(artifact_name="backtest", relative_path="backtest.csv"),
        ArtifactInventoryEntry(artifact_name="metadata", relative_path="metadata.json"),
    ))
    assert [a.artifact_name for a in run.artifact_inventory] == ["backtest", "metadata", "signal"]


def test_unavailable_run_allows_null_metadata():
    run = ExperimentRunEvidence(
        train_run_hash="ghost", run_directory="ghost",
        load_status=EvidenceLoadStatus.UNAVAILABLE, completeness=EvidenceCompleteness.UNAVAILABLE,
        audit_status="unavailable", missing_evidence=("RUN_NOT_FOUND",),
    )
    d = run.to_dict()
    assert d["metrics"] is None and d["feature_columns"] is None and d["model_type"] is None
    assert d["missing_evidence"] == ["RUN_NOT_FOUND"]


def test_run_rejects_absolute_run_directory():
    with pytest.raises(EvidenceError):
        _loaded_run(run_directory=r"C:\evil")


def test_run_rejects_bad_audit_status():
    with pytest.raises(EvidenceError):
        _loaded_run(audit_status="approved")


# --------------------------------------------------------------------------- #
# completeness derivation
# --------------------------------------------------------------------------- #


def test_derive_run_completeness_rules():
    assert derive_run_completeness(load_status="loaded", audit_findings=()) == EvidenceCompleteness.COMPLETE
    assert derive_run_completeness(
        load_status="loaded", audit_findings=(_audit_finding("warning"),)
    ) == EvidenceCompleteness.WARNING
    assert derive_run_completeness(
        load_status="loaded", audit_findings=(_audit_finding("error"),)
    ) == EvidenceCompleteness.INCOMPLETE
    assert derive_run_completeness(
        load_status="loaded", audit_findings=(_audit_finding("critical", code=AuditCode.PATH_TRAVERSAL),)
    ) == EvidenceCompleteness.INCOMPLETE
    assert derive_run_completeness(
        load_status="loaded", audit_findings=(), required_evidence_missing=True
    ) == EvidenceCompleteness.INCOMPLETE
    assert derive_run_completeness(
        load_status="loaded", audit_findings=(), requested_metric_missing=True
    ) == EvidenceCompleteness.INCOMPLETE
    assert derive_run_completeness(load_status="unavailable", audit_findings=()) == EvidenceCompleteness.UNAVAILABLE
    assert derive_run_completeness(load_status="unloadable", audit_findings=()) == EvidenceCompleteness.UNAVAILABLE


def test_derive_pack_completeness_rules():
    C, W, I, U = (EvidenceCompleteness.COMPLETE, EvidenceCompleteness.WARNING,
                  EvidenceCompleteness.INCOMPLETE, EvidenceCompleteness.UNAVAILABLE)
    assert derive_pack_completeness([C, C]) == C
    assert derive_pack_completeness([C, W]) == W
    assert derive_pack_completeness([C, I]) == I
    assert derive_pack_completeness([C, U]) == I           # mix -> incomplete
    assert derive_pack_completeness([U, U]) == U           # all unavailable
    assert derive_pack_completeness([]) == U               # empty -> unavailable
    assert derive_pack_completeness([C], selection_warning=True) == W   # incompatible-comparison warning
    assert derive_pack_completeness([C], selection_incomplete=True) == I
    # single-run not_applicable comparison contributes no selection warning
    assert derive_pack_completeness([C]) == C


# --------------------------------------------------------------------------- #
# ExperimentEvidencePack
# --------------------------------------------------------------------------- #


def _pack(run_hashes=("run_a", "run_b"), **kw) -> ExperimentEvidencePack:
    runs = tuple(_loaded_run(h) for h in run_hashes)
    comparison = ComparisonEvidence(
        status=EvidenceComparisonStatus.AVAILABLE if len(run_hashes) > 1 else EvidenceComparisonStatus.NOT_APPLICABLE,
        selected_run_hashes=tuple(run_hashes),
        rows=({"train_run_hash": run_hashes[0]},) if len(run_hashes) > 1 else (),
    )
    summary = EvidenceSummary(
        completeness=EvidenceCompleteness.COMPLETE, selected_runs_total=len(run_hashes),
        runs_complete=len(run_hashes), runs_with_warnings=0, runs_incomplete=0, runs_unavailable=0,
        phase14_findings_total=0, phase13_findings_total=0,
    )
    base = dict(selected_run_hashes=tuple(run_hashes), runs=runs, comparison=comparison,
                evidence_summary=summary)
    base.update(kw)
    return ExperimentEvidencePack(**base)


def test_pack_requires_selected_hashes():
    with pytest.raises(EvidenceError):
        ExperimentEvidencePack(
            selected_run_hashes=(), runs=(),
            comparison=ComparisonEvidence(status=EvidenceComparisonStatus.NOT_APPLICABLE),
            evidence_summary=EvidenceSummary(
                completeness=EvidenceCompleteness.UNAVAILABLE, selected_runs_total=0,
                runs_complete=0, runs_with_warnings=0, runs_incomplete=0, runs_unavailable=0,
                phase14_findings_total=0, phase13_findings_total=0),
        )


def test_pack_rejects_duplicate_hashes():
    with pytest.raises(EvidenceError):
        _pack(("run_a", "run_a"))


def test_pack_run_order_matches_selection():
    pack = _pack(("run_b", "run_a"))
    assert [r.train_run_hash for r in pack.runs] == ["run_b", "run_a"]  # not sorted


def test_pack_neutral_registry_defaults():
    pack = _pack()
    assert pack.registry_context_status == EvidenceContextStatus.NOT_COLLECTED
    assert pack.dataset_lineage_context_status == EvidenceContextStatus.NOT_COLLECTED
    d = pack.to_dict()
    assert d["registry_context_status"] == "not_collected"
    assert d["dataset_lineage_context_status"] == "not_collected"


def test_pack_deterministic_strict_json():
    pack = _pack()
    text = json.dumps(pack.to_dict(), allow_nan=False, sort_keys=True)
    assert json.dumps(pack.to_dict(), allow_nan=False, sort_keys=True) == text
    assert "NaN" not in text and "Infinity" not in text


def test_pack_phase14_and_phase13_ids_disjoint():
    audit = AuditFinding(finding_id="finding_0000", severity="warning", code=AuditCode.ORPHAN_ARTIFACT,
                         message="m", run_directory="run_a")
    runs = (_loaded_run("run_a", audit_findings=(audit,), completeness=EvidenceCompleteness.WARNING,
                        audit_status="warning"),)
    ev = sort_and_number_evidence_findings((_ev_finding(train_run_hash="run_a"),))
    summary = EvidenceSummary(completeness=EvidenceCompleteness.WARNING, selected_runs_total=1,
                              runs_complete=0, runs_with_warnings=1, runs_incomplete=0, runs_unavailable=0,
                              phase14_findings_total=1, phase13_findings_total=1)
    pack = ExperimentEvidencePack(
        selected_run_hashes=("run_a",), runs=runs,
        comparison=ComparisonEvidence(status=EvidenceComparisonStatus.NOT_APPLICABLE, selected_run_hashes=("run_a",)),
        evidence_summary=summary, findings=ev,
    )
    pack_ids = {f["finding_id"] for f in pack.to_dict()["findings"]}
    audit_ids = {f["finding_id"] for f in pack.to_dict()["runs"][0]["audit_findings"]}
    assert pack_ids == {"evidence_0000"} and audit_ids == {"finding_0000"}
    assert pack_ids.isdisjoint(audit_ids)


def test_pack_rejects_phase13_id_in_pack_findings():
    with pytest.raises(EvidenceError):
        _pack(findings=(dataclasses.replace(_ev_finding(), finding_id="finding_0000"),))


def test_pack_no_timestamp_or_host_fields():
    field_names = {f.name for f in dataclasses.fields(ExperimentEvidencePack)}
    for forbidden in ("timestamp", "generated_at", "created_at", "host", "hostname", "store_root", "base_dir"):
        assert forbidden not in field_names


# --------------------------------------------------------------------------- #
# EvidenceSummary
# --------------------------------------------------------------------------- #


def test_summary_count_consistency():
    with pytest.raises(EvidenceError):
        EvidenceSummary(completeness=EvidenceCompleteness.COMPLETE, selected_runs_total=3,
                        runs_complete=1, runs_with_warnings=0, runs_incomplete=0, runs_unavailable=0,
                        phase14_findings_total=0, phase13_findings_total=0)
    with pytest.raises(EvidenceError):
        EvidenceSummary(completeness=EvidenceCompleteness.COMPLETE, selected_runs_total=1,
                        runs_complete=-1, runs_with_warnings=1, runs_incomplete=1, runs_unavailable=0,
                        phase14_findings_total=0, phase13_findings_total=0)


# --------------------------------------------------------------------------- #
# dedupe_preserve_order
# --------------------------------------------------------------------------- #


def test_dedupe_preserve_order():
    assert dedupe_preserve_order(["run_b", "run_a", "run_b"]) == ("run_b", "run_a")
    assert dedupe_preserve_order(["only"]) == ("only",)
    with pytest.raises(EvidenceError):
        dedupe_preserve_order(["run_a", "  "])  # whitespace hash rejected
    with pytest.raises(EvidenceError):
        dedupe_preserve_order(["run_a", ""])


# --------------------------------------------------------------------------- #
# boundary / guard rails
# --------------------------------------------------------------------------- #


def test_models_module_no_forbidden_imports():
    src = Path(models_module.__file__).read_text(encoding="utf-8")
    forbidden = [
        "app.experiment_registry",
        "app.dataset_registry",
        "app.db",
        "sqlite3",
        "app.local_pipeline",
        "app.batch_experiments",
        "app.reporting",
        "app.experiment_catalog",
        "ExperimentStore",
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


def test_models_module_no_filesystem_or_repair_or_advice():
    src = Path(models_module.__file__).read_text(encoding="utf-8")
    for token in (".write_text", ".write_bytes", "open(", ".mkdir", ".touch", ".unlink",
                  "rmtree", "shutil", "to_csv", "to_parquet", "os.remove", "get_connection",
                  "init_db", "quantlab.db"):
        assert token not in src, f"models.py must not reference {token!r}"
    lowered = src.lower()
    for token in ("approved", "deployable", "buy", "sell", "allocate"):
        assert token not in lowered, f"models.py must not contain {token!r}"


def test_models_create_no_repo_artifacts():
    before = _repo_snapshot()
    _pack()
    sort_and_number_evidence_findings((_ev_finding(),))
    assert _repo_snapshot() == before


# --------------------------------------------------------------------------- #
# collector fixtures (real ExperimentStore under tmp_path)
# --------------------------------------------------------------------------- #

import hashlib  # noqa: E402  (test-only, for the byte-identical read-only proof)
from datetime import date  # noqa: E402

import pandas as pd  # noqa: E402

from app.experiment_audit import AuditLevel  # noqa: E402
from app.experiment_review import collect as collect_module  # noqa: E402
from app.experiment_review import collect_experiment_evidence_pack  # noqa: E402
from app.experiments import ExperimentRun, ExperimentStore  # noqa: E402

_ARTIFACTS = {
    "metadata": "metadata.json",
    "model_params": "model_params.json",
    "metrics": "metrics.json",
    "predictions": "predictions.csv",
    "signal": "signal.csv",
    "backtest": "backtest.csv",
}


def _run_kwargs(name: str, **overrides) -> dict:
    base = dict(
        train_run_hash=name,
        continuous_config_hash=f"cch_{name}",
        feature_config_hash=f"fch_{name}",
        label_config_hash=f"lch_{name}",
        dataset_config_hash="dch_shared",
        model_config_hash=f"mch_{name}",
        model_type="ridge_regression",
        task_type="regression",
        feature_columns=("feature__return_20",),
        label_column="label__forward_return_1",
        train_start=date(2024, 4, 1),
        train_end=date(2024, 6, 5),
        validation_start=date(2024, 6, 6),
        validation_end=date(2024, 9, 15),
        metrics={"mse": 0.1},
        backtest_metrics={"sharpe": 1.0, "total_return": 0.2},
        baseline_metrics={"no_trade": {"sharpe": 0.0}},
        created_at="2026-07-18T00:00:00+00:00",
        artifact_paths=dict(_ARTIFACTS),
    )
    base.update(overrides)
    return base


def _write_run(store: ExperimentStore, name: str, **overrides) -> None:
    store.write_metadata(ExperimentRun(**_run_kwargs(name, **overrides)))
    store.write_model_params(name, {"a": 1})
    store.write_metrics(name, {"m": 1.0})
    df = pd.DataFrame({"x": [1, 2, 3]})
    for frame in ("predictions", "signal", "backtest"):
        store.write_frame(name, frame, df)


def _store(tmp_path, names=("run_a", "run_b"), **overrides) -> ExperimentStore:
    store = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    for name in names:
        _write_run(store, name, **overrides)
    return store


def _snapshot(base: Path) -> dict:
    out = {}
    for p in sorted(base.rglob("*")):
        rel = str(p.relative_to(base)).replace("\\", "/")
        out[rel] = "DIR" if p.is_dir() else hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def _codes(pack) -> set:
    return {f.code.value for f in pack.findings}


def _run_of(pack, hash_):
    return next(r for r in pack.runs if r.train_run_hash == hash_)


# --------------------------------------------------------------------------- #
# selection
# --------------------------------------------------------------------------- #


def test_collect_rejects_empty_selection(tmp_path):
    store = _store(tmp_path, ("run_a",))
    with pytest.raises(EvidenceError):
        collect_experiment_evidence_pack(store, [])


def test_collect_dedupes_and_preserves_order(tmp_path):
    store = _store(tmp_path, ("run_a", "run_b"))
    pack = collect_experiment_evidence_pack(store, ["run_b", "run_a", "run_b"])
    assert pack.selected_run_hashes == ("run_b", "run_a")
    assert [r.train_run_hash for r in pack.runs] == ["run_b", "run_a"]  # not sorted


def test_collect_rejects_invalid_audit_level(tmp_path):
    store = _store(tmp_path, ("run_a",))
    with pytest.raises(EvidenceError):
        collect_experiment_evidence_pack(store, ["run_a"], audit_level="bogus")


# --------------------------------------------------------------------------- #
# single clean run
# --------------------------------------------------------------------------- #


def test_collect_single_clean_run(tmp_path):
    store = _store(tmp_path, ("run_a",))
    pack = collect_experiment_evidence_pack(store, ["run_a"])
    run = pack.runs[0]
    assert run.load_status == EvidenceLoadStatus.LOADED
    assert run.completeness == EvidenceCompleteness.COMPLETE
    assert run.audit_status == "valid"
    assert pack.evidence_summary.completeness == EvidenceCompleteness.COMPLETE
    # single run -> comparison not applicable, and no comparison finding
    assert pack.comparison.status == EvidenceComparisonStatus.NOT_APPLICABLE
    assert pack.comparison.rows == () and pack.comparison.unavailable_reason is None
    assert "COMPARISON_UNAVAILABLE" not in _codes(pack)
    # neutral registry / lineage context
    assert pack.registry_context_status == EvidenceContextStatus.NOT_COLLECTED
    assert pack.dataset_lineage_context_status == EvidenceContextStatus.NOT_COLLECTED


def test_collect_metadata_and_hash_chain_exact(tmp_path):
    store = _store(tmp_path, ("run_a",))
    run = collect_experiment_evidence_pack(store, ["run_a"]).runs[0]
    assert run.created_at == "2026-07-18T00:00:00+00:00"
    assert (run.train_start, run.validation_end) == ("2024-04-01", "2024-09-15")
    assert run.feature_columns == ("feature__return_20",)
    assert run.label_column == "label__forward_return_1"
    assert run.model_type == "ridge_regression" and run.task_type == "regression"
    chain = thaw_json_value(run.hash_chain)
    assert chain == {
        "train_run_hash": "run_a", "continuous_config_hash": "cch_run_a",
        "feature_config_hash": "fch_run_a", "label_config_hash": "lch_run_a",
        "dataset_config_hash": "dch_shared", "model_config_hash": "mch_run_a",
    }


def test_collect_merged_metrics_and_separate_baselines(tmp_path):
    store = _store(tmp_path, ("run_a",))
    run = collect_experiment_evidence_pack(store, ["run_a"]).runs[0]
    metrics = thaw_json_value(run.metrics)
    assert metrics["mse"] == 0.1                      # task metric preserved
    assert metrics["sharpe"] == 1.0                   # backtest metric merged in
    assert thaw_json_value(run.baseline_metrics) == {"no_trade": {"sharpe": 0.0}}  # separate


def test_collect_invents_no_provenance(tmp_path):
    store = _store(tmp_path, ("run_a",))
    d = collect_experiment_evidence_pack(store, ["run_a"]).runs[0].to_dict()
    for absent in ("root_symbol", "source", "raw_data_version_hash"):
        assert absent not in d


# --------------------------------------------------------------------------- #
# missing / unloadable runs
# --------------------------------------------------------------------------- #


def test_collect_missing_run(tmp_path):
    store = _store(tmp_path, ("run_a",))
    pack = collect_experiment_evidence_pack(store, ["ghost"])
    run = pack.runs[0]
    assert run.load_status == EvidenceLoadStatus.UNAVAILABLE
    assert run.completeness == EvidenceCompleteness.UNAVAILABLE
    assert run.audit_status == "unavailable"
    assert run.metrics is None and run.artifact_inventory == ()
    assert "RUN_NOT_FOUND" in _codes(pack)
    assert "run_not_found" in run.missing_evidence
    assert pack.evidence_summary.completeness == EvidenceCompleteness.UNAVAILABLE


def test_collect_missing_plus_valid_is_incomplete(tmp_path):
    store = _store(tmp_path, ("run_a",))
    pack = collect_experiment_evidence_pack(store, ["run_a", "ghost"])
    assert _run_of(pack, "run_a").completeness == EvidenceCompleteness.COMPLETE
    assert _run_of(pack, "ghost").completeness == EvidenceCompleteness.UNAVAILABLE
    assert pack.evidence_summary.completeness == EvidenceCompleteness.INCOMPLETE
    # comparison not attempted with a missing hash
    assert pack.comparison.status == EvidenceComparisonStatus.UNAVAILABLE
    assert "COMPARISON_UNAVAILABLE" in _codes(pack)


def test_collect_all_missing_is_unavailable(tmp_path):
    store = _store(tmp_path, ("run_a",))
    pack = collect_experiment_evidence_pack(store, ["ghost1", "ghost2"])
    assert pack.evidence_summary.completeness == EvidenceCompleteness.UNAVAILABLE


def test_collect_malformed_run_does_not_abort_valid_run(tmp_path):
    store = _store(tmp_path, ("run_a", "run_bad"))
    (store.base_dir / "run_bad" / "metadata.json").write_text("{ not json", encoding="utf-8")
    pack = collect_experiment_evidence_pack(store, ["run_bad", "run_a"])
    bad, good = _run_of(pack, "run_bad"), _run_of(pack, "run_a")
    assert bad.load_status == EvidenceLoadStatus.UNLOADABLE
    assert bad.completeness == EvidenceCompleteness.UNAVAILABLE
    assert bad.metrics is None  # no invented metadata
    assert "RUN_UNLOADABLE" in _codes(pack) and "run_unloadable" in bad.missing_evidence
    # the valid run still produced full evidence
    assert good.load_status == EvidenceLoadStatus.LOADED and good.metrics is not None
    # Phase 13 still audited the malformed run and its findings are preserved
    assert any(f.code.value == "MALFORMED_METADATA_JSON" for f in bad.audit_findings)
    assert bad.audit_status == "invalid"


def test_collect_preserves_phase13_finding_ids(tmp_path):
    store = _store(tmp_path, ("run_a",))
    (store.base_dir / "run_a" / "extra.json").write_text("{}", encoding="utf-8")  # orphan -> warning
    run = collect_experiment_evidence_pack(store, ["run_a"]).runs[0]
    assert run.audit_findings, "expected Phase 13 findings"
    for f in run.audit_findings:
        assert f.finding_id.startswith("finding_")  # never renumbered to evidence_*


# --------------------------------------------------------------------------- #
# audit-driven completeness
# --------------------------------------------------------------------------- #


def test_collect_warning_only_run(tmp_path):
    store = _store(tmp_path, ("run_a",))
    (store.base_dir / "run_a" / "extra.json").write_text("{}", encoding="utf-8")  # ORPHAN warning
    pack = collect_experiment_evidence_pack(store, ["run_a"])
    assert pack.runs[0].completeness == EvidenceCompleteness.WARNING
    assert pack.evidence_summary.completeness == EvidenceCompleteness.WARNING


def test_collect_error_run_is_incomplete(tmp_path):
    store = _store(tmp_path, ("run_a",))
    (store.base_dir / "run_a" / "predictions.csv").unlink()  # MISSING_REFERENCED_ARTIFACT
    pack = collect_experiment_evidence_pack(store, ["run_a"])
    run = pack.runs[0]
    assert run.completeness == EvidenceCompleteness.INCOMPLETE
    assert "required_artifact_missing" in run.missing_evidence
    assert pack.evidence_summary.completeness == EvidenceCompleteness.INCOMPLETE


def test_collect_critical_run_is_incomplete(tmp_path):
    store = _store(tmp_path, ("run_a",))
    path = store.base_dir / "run_a" / "metadata.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["artifact_paths"]["predictions"] = "../evil.csv"  # PATH_TRAVERSAL (critical)
    path.write_text(json.dumps(data), encoding="utf-8")
    pack = collect_experiment_evidence_pack(store, ["run_a"])
    # schema rejects the unsafe path -> unloadable, but Phase 13 evidence is kept
    run = pack.runs[0]
    assert any(f.code.value == "PATH_TRAVERSAL" for f in run.audit_findings)
    assert run.completeness == EvidenceCompleteness.UNAVAILABLE
    assert not (tmp_path / "evil.csv").exists()  # never followed


# --------------------------------------------------------------------------- #
# artifact inventory
# --------------------------------------------------------------------------- #


def test_inventory_standard_all_canonical_present(tmp_path):
    store = _store(tmp_path, ("run_a",))
    run = collect_experiment_evidence_pack(store, ["run_a"]).runs[0]
    names = [a.artifact_name for a in run.artifact_inventory]
    assert names == sorted(names)  # deterministic ordering
    assert set(names) == set(_ARTIFACTS)
    for entry in run.artifact_inventory:
        assert entry.exists is True and entry.regular_file is True
        assert entry.relative_path == _ARTIFACTS[entry.artifact_name]
        assert entry.format in {"json", "csv"}


def test_inventory_metadata_only_is_tristate_none(tmp_path):
    store = _store(tmp_path, ("run_a",))
    run = collect_experiment_evidence_pack(
        store, ["run_a"], audit_level=AuditLevel.METADATA_ONLY
    ).runs[0]
    for entry in run.artifact_inventory:
        assert entry.exists is None and entry.regular_file is None


def test_inventory_missing_referenced_artifact(tmp_path):
    store = _store(tmp_path, ("run_a",))
    (store.base_dir / "run_a" / "predictions.csv").unlink()
    run = collect_experiment_evidence_pack(store, ["run_a"]).runs[0]
    entry = next(a for a in run.artifact_inventory if a.artifact_name == "predictions")
    assert entry.exists is False and entry.regular_file is False
    assert "MISSING_REFERENCED_ARTIFACT" in entry.audit_finding_codes


def test_inventory_artifact_not_a_file(tmp_path):
    store = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    _write_run(store, "run_a", artifact_paths=dict(_ARTIFACTS, predictions="pred_dir"))
    (store.base_dir / "run_a" / "predictions.csv").unlink()
    (store.base_dir / "run_a" / "pred_dir").mkdir()
    run = collect_experiment_evidence_pack(store, ["run_a"]).runs[0]
    entry = next(a for a in run.artifact_inventory if a.artifact_name == "predictions")
    assert entry.exists is True and entry.regular_file is False
    assert "ARTIFACT_NOT_A_FILE" in entry.audit_finding_codes


def test_inventory_orphan_entry_from_phase13(tmp_path):
    store = _store(tmp_path, ("run_a",))
    (store.base_dir / "run_a" / "extra.json").write_text("{}", encoding="utf-8")
    run = collect_experiment_evidence_pack(store, ["run_a"]).runs[0]
    orphan = next(a for a in run.artifact_inventory if a.artifact_name.startswith("orphan:"))
    assert orphan.relative_path == "extra.json"
    assert orphan.exists is True and orphan.regular_file is None  # presence only
    assert orphan.audit_finding_codes == ("ORPHAN_ARTIFACT",)


def test_inventory_never_contains_absolute_or_unsafe_paths(tmp_path):
    store = _store(tmp_path, ("run_a",))
    run = collect_experiment_evidence_pack(store, ["run_a"]).runs[0]
    for entry in run.artifact_inventory:
        assert entry.relative_path is None or not entry.relative_path.startswith(("/", "\\"))
        assert entry.relative_path is None or ":" not in entry.relative_path


# --------------------------------------------------------------------------- #
# catalog context
# --------------------------------------------------------------------------- #


def test_catalog_context_collected(tmp_path):
    store = _store(tmp_path, ("run_a", "run_b"))
    pack = collect_experiment_evidence_pack(store, ["run_a", "run_b"])
    assert pack.catalog_context_status == EvidenceContextStatus.COLLECTED
    ctx = _run_of(pack, "run_a").catalog_context
    assert ctx.status == EvidenceContextStatus.COLLECTED
    assert ctx.compatibility_group == "group_0000"  # deterministic Phase 12 label
    assert ctx.group_size == 2
    assert ctx.peer_train_run_hashes == ("run_a", "run_b")  # sorted, includes self
    assert ctx.requested_metric is None and ctx.rank is None  # no implicit ranking


def test_catalog_single_pass_only(tmp_path, monkeypatch):
    store = _store(tmp_path, ("run_a", "run_b", "run_c"))
    calls = {"n": 0}
    original = collect_module.build_experiment_catalog

    def counting(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(collect_module, "build_experiment_catalog", counting)
    collect_experiment_evidence_pack(store, ["run_a", "run_b", "run_c"])
    assert calls["n"] == 1  # one store-level pass, not one per run


def test_catalog_disabled_is_neutral(tmp_path):
    store = _store(tmp_path, ("run_a",))
    pack = collect_experiment_evidence_pack(store, ["run_a"], include_catalog_context=False)
    assert pack.catalog_context_status == EvidenceContextStatus.NOT_COLLECTED
    assert pack.runs[0].catalog_context.status == EvidenceContextStatus.NOT_COLLECTED
    assert "CATALOG_CONTEXT_UNAVAILABLE" not in _codes(pack)
    assert pack.evidence_summary.completeness == EvidenceCompleteness.COMPLETE  # no downgrade


def test_catalog_unavailable_from_unrelated_malformed_entry(tmp_path):
    store = _store(tmp_path, ("run_a", "run_bad"))
    (store.base_dir / "run_bad" / "metadata.json").write_text("{ not json", encoding="utf-8")
    pack = collect_experiment_evidence_pack(store, ["run_a"])  # run_bad NOT selected
    assert pack.catalog_context_status == EvidenceContextStatus.UNAVAILABLE
    assert "CATALOG_CONTEXT_UNAVAILABLE" in _codes(pack)
    run = _run_of(pack, "run_a")
    # selected-run evidence survives the catalog failure
    assert run.load_status == EvidenceLoadStatus.LOADED and run.metrics is not None
    assert run.catalog_context.status == EvidenceContextStatus.UNAVAILABLE
    assert pack.evidence_summary.completeness == EvidenceCompleteness.WARNING  # not incomplete


def test_catalog_run_absent_from_successful_catalog(tmp_path, monkeypatch):
    store = _store(tmp_path, ("run_a", "run_b"))
    original = collect_module.build_experiment_catalog
    monkeypatch.setattr(
        collect_module, "build_experiment_catalog",
        lambda *a, **k: tuple(r for r in original(*a, **k) if r.train_run_hash != "run_a"),
    )
    pack = collect_experiment_evidence_pack(store, ["run_a"])
    run = pack.runs[0]
    assert run.catalog_context.status == EvidenceContextStatus.UNAVAILABLE
    assert "CATALOG_CONTEXT_UNAVAILABLE" in _codes(pack)
    # optional context, so it is never listed as missing *required* run evidence...
    assert run.missing_evidence == ()
    # ...and a run whose own evidence is intact stays complete, while the pack warns
    assert run.completeness == EvidenceCompleteness.COMPLETE
    assert pack.evidence_summary.completeness == EvidenceCompleteness.WARNING


# --------------------------------------------------------------------------- #
# explicit metric + ranking
# --------------------------------------------------------------------------- #


def test_metric_rank_maximize_and_minimize(tmp_path):
    store = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    _write_run(store, "run_a", backtest_metrics={"sharpe": 2.0})
    _write_run(store, "run_b", backtest_metrics={"sharpe": 1.0})
    top = collect_experiment_evidence_pack(store, ["run_a", "run_b"], metric="sharpe")
    assert _run_of(top, "run_a").catalog_context.rank == 1
    assert _run_of(top, "run_b").catalog_context.rank == 2
    assert _run_of(top, "run_a").catalog_context.requested_metric_value == 2.0
    low = collect_experiment_evidence_pack(store, ["run_a", "run_b"], metric="sharpe", maximize=False)
    assert _run_of(low, "run_a").catalog_context.rank == 2
    assert _run_of(low, "run_b").catalog_context.rank == 1
    # selected order is unaffected by rank
    assert low.selected_run_hashes == ("run_a", "run_b")


def test_metric_missing_makes_incomplete(tmp_path):
    store = _store(tmp_path, ("run_a", "run_b"))  # no "information_coefficient" persisted
    pack = collect_experiment_evidence_pack(store, ["run_a"], metric="information_coefficient")
    run = pack.runs[0]
    assert run.completeness == EvidenceCompleteness.INCOMPLETE
    assert run.catalog_context.requested_metric == "information_coefficient"
    assert run.catalog_context.requested_metric_value is None and run.catalog_context.rank is None
    assert "REQUESTED_METRIC_MISSING" in _codes(pack)
    assert "requested_metric_missing" in run.missing_evidence
    assert pack.evidence_summary.completeness == EvidenceCompleteness.INCOMPLETE


def test_no_metric_means_no_ranking_and_no_finding(tmp_path):
    store = _store(tmp_path, ("run_a",))
    pack = collect_experiment_evidence_pack(store, ["run_a"])
    ctx = pack.runs[0].catalog_context
    assert ctx.requested_metric is None and ctx.requested_metric_value is None and ctx.rank is None
    assert "REQUESTED_METRIC_MISSING" not in _codes(pack)
    assert pack.evidence_summary.completeness == EvidenceCompleteness.COMPLETE


# --------------------------------------------------------------------------- #
# Phase 10 comparison
# --------------------------------------------------------------------------- #


def test_comparison_available_for_compatible_runs(tmp_path):
    store = _store(tmp_path, ("run_a", "run_b"))
    pack = collect_experiment_evidence_pack(store, ["run_a", "run_b"])
    comp = pack.comparison
    assert comp.status == EvidenceComparisonStatus.AVAILABLE
    rows = comp.to_dict()["rows"]
    assert [r["train_run_hash"] for r in rows] == ["run_a", "run_b"]  # Phase 10 order preserved
    assert comp.disclaimers  # Phase 10 disclaimers retained
    assert "COMPARISON_UNAVAILABLE" not in _codes(pack)
    assert "best" not in comp.to_dict() and "winner" not in comp.to_dict()


def test_comparison_incompatible_runs_is_warning(tmp_path):
    store = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    _write_run(store, "run_a")
    _write_run(store, "run_b", validation_end=date(2024, 9, 30))  # different OOS window
    pack = collect_experiment_evidence_pack(store, ["run_a", "run_b"])
    assert pack.comparison.status == EvidenceComparisonStatus.UNAVAILABLE
    assert pack.comparison.unavailable_reason
    assert {"INCOMPATIBLE_SELECTED_RUNS", "COMPARISON_UNAVAILABLE"} <= _codes(pack)
    # per-run evidence intact; incompatibility is a selection warning, not incomplete
    assert all(r.load_status == EvidenceLoadStatus.LOADED for r in pack.runs)
    assert pack.evidence_summary.completeness == EvidenceCompleteness.WARNING


def test_comparison_guard_not_bypassed(tmp_path, monkeypatch):
    store = _store(tmp_path, ("run_a", "run_b"))
    seen = {}

    original = collect_module.compare_experiment_runs

    def spy(hashes, **kwargs):
        seen.update(kwargs)
        return original(hashes, **kwargs)

    monkeypatch.setattr(collect_module, "compare_experiment_runs", spy)
    collect_experiment_evidence_pack(store, ["run_a", "run_b"])
    assert seen.get("allow_different_windows") in (None, False)  # never bypassed


# --------------------------------------------------------------------------- #
# findings, summary, determinism
# --------------------------------------------------------------------------- #


def test_findings_use_evidence_namespace_and_are_disjoint(tmp_path):
    store = _store(tmp_path, ("run_a",))
    (store.base_dir / "run_a" / "extra.json").write_text("{}", encoding="utf-8")
    pack = collect_experiment_evidence_pack(store, ["run_a", "ghost"])
    pack_ids = {f.finding_id for f in pack.findings}
    assert pack_ids and all(i.startswith("evidence_") for i in pack_ids)
    audit_ids = {f.finding_id for r in pack.runs for f in r.audit_findings}
    assert all(i.startswith("finding_") for i in audit_ids)
    assert pack_ids.isdisjoint(audit_ids)


def test_summary_counts_match_runs_and_findings(tmp_path):
    store = _store(tmp_path, ("run_a",))
    pack = collect_experiment_evidence_pack(store, ["run_a", "ghost"])
    s = pack.evidence_summary
    assert s.selected_runs_total == 2
    assert s.runs_complete + s.runs_with_warnings + s.runs_incomplete + s.runs_unavailable == 2
    assert s.phase14_findings_total == len(pack.findings)
    assert s.phase13_findings_total == sum(len(r.audit_findings) for r in pack.runs)


def test_collect_deterministic_and_strict_json(tmp_path):
    store = _store(tmp_path, ("run_a", "run_b"))
    a = collect_experiment_evidence_pack(store, ["run_a", "run_b"], metric="sharpe")
    b = collect_experiment_evidence_pack(store, ["run_a", "run_b"], metric="sharpe")
    assert a.to_dict() == b.to_dict()
    text = json.dumps(a.to_dict(), allow_nan=False, sort_keys=True)
    assert "NaN" not in text and "Infinity" not in text


def test_collect_no_absolute_path_leakage_anywhere_in_serialization(tmp_path):
    """The COMPLETE pack serialization carries no host-absolute path — including
    Phase 13 finding fields, which are preserved verbatim in memory but projected
    through the evidence-safe serialization."""
    store = _store(tmp_path, ("run_a", "run_bad"))
    (store.base_dir / "run_bad" / "metadata.json").write_text("{ not json", encoding="utf-8")
    path = store.base_dir / "run_a" / "metadata.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["artifact_paths"]["predictions"] = "C:\\secret\\predictions.csv"
    path.write_text(json.dumps(data), encoding="utf-8")
    pack = collect_experiment_evidence_pack(store, ["run_a", "run_bad", "ghost"])
    text = json.dumps(pack.to_dict(), allow_nan=False, sort_keys=True)  # nothing popped
    assert tmp_path.name not in text
    assert "C:\\secret" not in text and "C:\\\\secret" not in text
    assert "secret" not in text
    assert ":\\" not in text and ":/" not in text
    assert EVIDENCE_REDACTED_PATH in text


# --------------------------------------------------------------------------- #
# evidence-safe serialization of Phase 13 findings
# --------------------------------------------------------------------------- #

_HOST_ABSOLUTE = [
    "C:\\secret\\x.csv",
    "C:/secret/x.csv",
    "/tmp/secret.csv",
    "\\\\server\\share\\secret.csv",
    "//server/share/secret.csv",
    "\\secret\\x.csv",
]
_STORE_RELATIVE = ["predictions.csv", "nested/frame.csv", "../evil.csv", "a\\b.csv"]


@pytest.mark.parametrize("value", _HOST_ABSOLUTE)
def test_host_absolute_values_are_redacted(value):
    assert is_host_absolute_path(value)
    assert redact_host_absolute_text(value) == EVIDENCE_REDACTED_PATH


@pytest.mark.parametrize("value", _STORE_RELATIVE)
def test_store_relative_values_are_never_redacted(value):
    """Traversal is unsafe for filesystem access but is not a host-path leak, so it
    stays as factual declared evidence."""
    assert not is_host_absolute_path(value)
    assert redact_host_absolute_text(value) == value


@pytest.mark.parametrize("value", _HOST_ABSOLUTE)
def test_host_absolute_paths_embedded_in_messages_are_neutralized(value):
    out = redact_host_absolute_text(f"artifact {value} could not be read")
    assert EVIDENCE_REDACTED_PATH in out
    assert "secret" not in out
    assert out.startswith("artifact ") and out.endswith(" could not be read")


def test_redaction_marker_is_stable_and_adds_no_metadata():
    a = redact_host_absolute_text("/tmp/secret.csv")
    b = redact_host_absolute_text("/tmp/other.csv")
    assert a == b == EVIDENCE_REDACTED_PATH  # identical marker every time
    assert "20" not in EVIDENCE_REDACTED_PATH  # no timestamp / host metadata


def test_safe_projection_preserves_phase13_identity_and_field_order():
    finding = AuditFinding(
        finding_id="finding_0007",
        severity=AuditSeverity.CRITICAL,
        code=AuditCode.ABSOLUTE_ARTIFACT_PATH,
        message="artifact 'predictions' declares C:\\secret\\x.csv",
        train_run_hash="run_a",
        run_directory="run_a",
        artifact_name="predictions",
        relative_path="predictions.csv",
        expected="/tmp/expected.csv",
        actual="C:\\secret\\x.csv",
    )
    raw, safe = finding.to_dict(), safe_audit_finding_dict(finding)
    assert list(safe) == list(raw)  # identical deterministic field ordering
    assert safe["finding_id"] == "finding_0007"
    assert safe["severity"] == raw["severity"] and safe["code"] == raw["code"]
    assert safe["train_run_hash"] == "run_a" and safe["run_directory"] == "run_a"
    assert safe["artifact_name"] == "predictions"
    assert safe["relative_path"] == "predictions.csv"  # safe evidence untouched
    assert safe["actual"] == EVIDENCE_REDACTED_PATH
    assert safe["expected"] == EVIDENCE_REDACTED_PATH
    assert "secret" not in safe["message"] and EVIDENCE_REDACTED_PATH in safe["message"]
    # the source object is untouched
    assert finding.actual == "C:\\secret\\x.csv"
    assert finding.expected == "/tmp/expected.csv"
    assert finding.to_dict() == raw


def test_phase13_findings_unchanged_in_memory_after_pack_serialization(tmp_path):
    """Serialization is a projection, not a mutation: the original public Phase 13
    objects keep their ids, codes, severities and raw values."""
    store = _store(tmp_path, ("run_a",))
    path = store.base_dir / "run_a" / "metadata.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["artifact_paths"]["predictions"] = "C:\\secret\\predictions.csv"
    path.write_text(json.dumps(data), encoding="utf-8")
    pack = collect_experiment_evidence_pack(store, ["run_a"])
    findings = pack.runs[0].audit_findings
    assert findings, "expected Phase 13 findings"
    before = [dataclasses.astuple(f) for f in findings]
    pack.to_dict()
    pack.to_dict()
    assert [dataclasses.astuple(f) for f in findings] == before  # value-equal
    assert all(f.finding_id.startswith("finding_") for f in findings)
    # the raw declared host path is still present on the in-memory object
    assert any(f.actual and "C:\\secret" in f.actual for f in findings)
    # ...but never in the serialization
    assert "C:\\secret" not in json.dumps(pack.to_dict(), allow_nan=False)


def test_redacted_serialization_is_deterministic_and_strict_json(tmp_path):
    store = _store(tmp_path, ("run_a",))
    path = store.base_dir / "run_a" / "metadata.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["artifact_paths"]["predictions"] = "\\\\server\\share\\predictions.csv"
    path.write_text(json.dumps(data), encoding="utf-8")
    pack = collect_experiment_evidence_pack(store, ["run_a"])
    first = json.dumps(pack.to_dict(), allow_nan=False, sort_keys=True)
    second = json.dumps(pack.to_dict(), allow_nan=False, sort_keys=True)
    assert first == second
    assert "server" not in first and EVIDENCE_REDACTED_PATH in first


def test_namespaces_stay_disjoint_after_redaction(tmp_path):
    store = _store(tmp_path, ("run_a",))
    path = store.base_dir / "run_a" / "metadata.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["artifact_paths"]["predictions"] = "/tmp/secret.csv"
    path.write_text(json.dumps(data), encoding="utf-8")
    d = collect_experiment_evidence_pack(store, ["run_a"]).to_dict()
    audit_ids = {f["finding_id"] for r in d["runs"] for f in r["audit_findings"]}
    pack_ids = {f["finding_id"] for f in d["findings"]}
    assert all(i.startswith("finding_") for i in audit_ids)
    assert all(i.startswith("evidence_") for i in pack_ids)
    assert audit_ids.isdisjoint(pack_ids)


def test_redaction_needs_no_renderer(tmp_path):
    """The safety property holds at the model layer: ``to_dict()`` alone is safe, with
    no renderer involved, so every consumer inherits it rather than re-implementing it."""
    store = _store(tmp_path, ("run_a",))
    path = store.base_dir / "run_a" / "metadata.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["artifact_paths"]["predictions"] = "C:/secret/x.csv"
    path.write_text(json.dumps(data), encoding="utf-8")
    run = collect_experiment_evidence_pack(store, ["run_a"]).runs[0]
    assert "secret" not in json.dumps(run.to_dict(), allow_nan=False)


# --------------------------------------------------------------------------- #
# regressions found by adversarial review
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("unsafe", ["../evil", "C:/evil", "/evil", "a/b", "..\\evil"])
def test_unsafe_hash_does_not_abort_the_pack(tmp_path, unsafe):
    """One unsafe selection entry must not destroy every other run's evidence."""
    store = _store(tmp_path, ("run_a",))
    pack = collect_experiment_evidence_pack(store, ["run_a", unsafe])
    assert _run_of(pack, "run_a").completeness == EvidenceCompleteness.COMPLETE
    bad = _run_of(pack, unsafe)
    assert bad.load_status == EvidenceLoadStatus.UNAVAILABLE
    assert bad.run_directory is None  # unsafe value never enters a path field
    assert "RUN_NOT_FOUND" in _codes(pack)
    json.dumps(pack.to_dict(), allow_nan=False, sort_keys=True)  # still serializable


def test_catalog_failure_does_not_fabricate_missing_metric(tmp_path):
    """A store-level catalog failure is not evidence that a run lacks the metric."""
    store = _store(tmp_path, ("run_a", "run_bad"))
    (store.base_dir / "run_bad" / "metadata.json").write_text("{ not json", encoding="utf-8")
    pack = collect_experiment_evidence_pack(store, ["run_a"], metric="sharpe")
    run = pack.runs[0]
    assert pack.catalog_context_status == EvidenceContextStatus.UNAVAILABLE
    # run_a really does persist sharpe, so claiming otherwise would contradict the pack
    assert thaw_json_value(run.metrics)["sharpe"] == 1.0
    assert "REQUESTED_METRIC_MISSING" not in _codes(pack)
    assert "requested_metric_missing" not in run.missing_evidence
    assert run.completeness == EvidenceCompleteness.COMPLETE
    # degraded to a warning, matching the metric=None behaviour for the same store
    assert pack.evidence_summary.completeness == EvidenceCompleteness.WARNING
    assert "CATALOG_CONTEXT_UNAVAILABLE" in _codes(pack)


def test_catalog_failure_is_warning_regardless_of_metric(tmp_path):
    store = _store(tmp_path, ("run_a", "run_bad"))
    (store.base_dir / "run_bad" / "metadata.json").write_text("{ not json", encoding="utf-8")
    without = collect_experiment_evidence_pack(store, ["run_a"])
    with_metric = collect_experiment_evidence_pack(store, ["run_a"], metric="sharpe")
    assert without.evidence_summary.completeness == with_metric.evidence_summary.completeness


@pytest.mark.parametrize("bad_metric", ["", "   ", 123, 1.5, ["sharpe"], {"m": 1}])
def test_invalid_metric_argument_is_rejected_cleanly(tmp_path, bad_metric):
    """An unusable metric argument fails fast as EvidenceError — never as an
    AttributeError/TypeError escaping from a Phase 12 internal."""
    store = _store(tmp_path, ("run_a", "run_b"))
    with pytest.raises(EvidenceError):
        collect_experiment_evidence_pack(store, ["run_a"], metric=bad_metric)


def test_metric_without_catalog_context_is_rejected(tmp_path):
    """A metric request cannot be silently dropped when ranking evidence is disabled."""
    store = _store(tmp_path, ("run_a",))
    with pytest.raises(EvidenceError):
        collect_experiment_evidence_pack(
            store, ["run_a"], metric="sharpe", include_catalog_context=False
        )


def test_comparison_preserved_when_only_training_window_differs(tmp_path):
    """Phase 12 groups on the *training* window too, so it is strictly narrower than
    the Phase 10 guard.  Compatibility must be decided by Phase 10 alone."""
    store = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    _write_run(store, "run_a", train_start=date(2024, 4, 1))
    _write_run(store, "run_b", train_start=date(2024, 5, 1))  # same OOS window/label/dataset
    groups = {
        _run_of(collect_experiment_evidence_pack(store, ["run_a", "run_b"]), h)
        .catalog_context.compatibility_group
        for h in ("run_a", "run_b")
    }
    assert len(groups) == 2, "fixture must span two Phase 12 groups to be meaningful"
    pack = collect_experiment_evidence_pack(store, ["run_a", "run_b"])
    assert pack.comparison.status == EvidenceComparisonStatus.AVAILABLE
    assert "INCOMPATIBLE_SELECTED_RUNS" not in _codes(pack)
    assert pack.evidence_summary.completeness == EvidenceCompleteness.COMPLETE


def test_missing_artifact_is_not_reported_as_incompatibility(tmp_path):
    """Two window-compatible runs stay compatible even if one has a missing artifact —
    the pack must not contradict its own MISSING_REFERENCED_ARTIFACT evidence."""
    store = _store(tmp_path, ("run_a", "run_b"))  # identical OOS window / label / dataset
    (store.base_dir / "run_a" / "predictions.csv").unlink()
    pack = collect_experiment_evidence_pack(store, ["run_a", "run_b"])
    assert "required_artifact_missing" in _run_of(pack, "run_a").missing_evidence
    assert "INCOMPATIBLE_SELECTED_RUNS" not in _codes(pack)
    assert pack.comparison.status == EvidenceComparisonStatus.AVAILABLE


def test_requested_metric_appears_in_comparison_rows(tmp_path):
    store = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    _write_run(store, "run_a", backtest_metrics={"calmar": 1.2})
    _write_run(store, "run_b", backtest_metrics={"calmar": 0.8})
    pack = collect_experiment_evidence_pack(store, ["run_a", "run_b"], metric="calmar")
    assert _run_of(pack, "run_a").catalog_context.rank == 1
    for row in pack.comparison.to_dict()["rows"]:
        assert "calmar" in row["metrics"], "a reported rank must be backed by a comparison row"


def test_unusable_artifact_is_recorded_in_missing_evidence(tmp_path):
    """An INCOMPLETE run must explain itself via missing_evidence, not just via severity."""
    store = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    _write_run(store, "run_a", artifact_paths=dict(_ARTIFACTS, predictions="pred_dir"))
    (store.base_dir / "run_a" / "predictions.csv").unlink()
    (store.base_dir / "run_a" / "pred_dir").mkdir()
    run = collect_experiment_evidence_pack(store, ["run_a"]).runs[0]
    assert run.completeness == EvidenceCompleteness.INCOMPLETE
    assert "required_artifact_missing" in run.missing_evidence


def test_blank_artifact_key_stays_visible(tmp_path):
    """A declared artifact must never vanish from the inventory: Phase 13 validates
    artifact_paths values but not keys, so nothing else would report it."""
    store = _store(tmp_path, ("run_a",))
    path = store.base_dir / "run_a" / "metadata.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["artifact_paths"][""] = "stray.csv"
    path.write_text(json.dumps(data), encoding="utf-8")
    (store.base_dir / "run_a" / "stray.csv").write_text("x\n", encoding="utf-8")
    run = collect_experiment_evidence_pack(store, ["run_a"]).runs[0]
    paths = {a.relative_path for a in run.artifact_inventory}
    assert "stray.csv" in paths
    assert all(a.artifact_name.strip() for a in run.artifact_inventory)


def test_malformed_artifact_key_does_not_abort_the_pack(tmp_path):
    store = _store(tmp_path, ("run_a", "run_odd"))
    path = store.base_dir / "run_odd" / "metadata.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["artifact_paths"][""] = "stray.csv"
    path.write_text(json.dumps(data), encoding="utf-8")
    pack = collect_experiment_evidence_pack(store, ["run_a", "run_odd"])
    assert _run_of(pack, "run_a").completeness == EvidenceCompleteness.COMPLETE
    assert all(a.artifact_name.strip() for a in _run_of(pack, "run_odd").artifact_inventory)


def test_artifact_format_uses_filename_not_dotted_directory(tmp_path):
    store = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    _write_run(store, "run_a", artifact_paths=dict(_ARTIFACTS, predictions="v1.2/predictions.csv"))
    (store.base_dir / "run_a" / "predictions.csv").unlink()
    (store.base_dir / "run_a" / "v1.2").mkdir()
    (store.base_dir / "run_a" / "v1.2" / "predictions.csv").write_text("x\n", encoding="utf-8")
    run = collect_experiment_evidence_pack(store, ["run_a"]).runs[0]
    entry = next(a for a in run.artifact_inventory if a.artifact_name == "predictions")
    assert entry.format == "csv"  # not "2/predictions.csv"


def test_comparison_failure_reason_is_neutral(tmp_path):
    store = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    _write_run(store, "run_a")
    _write_run(store, "run_b", validation_end=date(2024, 9, 30))
    pack = collect_experiment_evidence_pack(store, ["run_a", "run_b"])
    assert "guard" not in (pack.comparison.unavailable_reason or "")


# --------------------------------------------------------------------------- #
# read-only proof + boundaries
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("level", ["metadata-only", "standard", "deep"])
def test_collect_leaves_store_byte_identical(tmp_path, level):
    store = _store(tmp_path, ("run_a", "run_b"))
    (store.base_dir / "run_a" / "extra.json").write_text("{}", encoding="utf-8")
    before = _snapshot(store.base_dir)
    collect_experiment_evidence_pack(store, ["run_a", "run_b", "ghost"], metric="sharpe", audit_level=level)
    assert _snapshot(store.base_dir) == before


def test_collect_creates_no_repo_artifacts_or_db(tmp_path):
    before = _repo_snapshot()
    store = _store(tmp_path, ("run_a",))
    collect_experiment_evidence_pack(store, ["run_a"])
    assert _repo_snapshot() == before
    assert not (_BACKEND / "data" / "quantlab.db").exists()  # no registry DB created


def test_collect_module_no_forbidden_imports():
    src = Path(collect_module.__file__).read_text(encoding="utf-8")
    forbidden = [
        "app.experiment_registry",
        "app.dataset_registry",
        "app.db",
        "sqlite3",
        "get_connection",
        "quantlab.db",
        "app.local_pipeline",
        "app.batch_experiments",
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
        assert token not in src, f"collect.py must not reference {token!r}"


def test_collect_module_no_mutation_or_advice():
    src = Path(collect_module.__file__).read_text(encoding="utf-8")
    for token in (".write_text", ".write_bytes", "open(", ".mkdir", ".touch", ".unlink",
                  ".rmdir", ".rename", "rmtree", "shutil", "to_csv", "to_parquet", "os.remove"):
        assert token not in src, f"collect.py must not contain mutation call {token!r}"
    lowered = src.lower()
    for token in ("approved", "deployable", "buy", "sell", "allocate", "deploy"):
        assert token not in lowered, f"collect.py must not contain {token!r}"


def test_collect_module_uses_no_private_symbols():
    import re as _re

    src = Path(collect_module.__file__).read_text(encoding="utf-8")
    for private in ("_ABSOLUTE_PATH", "_FRAME_NAMES", "_is_relative_path", "_window_key",
                    "_compat_key", "_resolve_run", "_metric_value"):
        assert not _re.search(rf"\b{private}\b", src), f"collect.py must not use {private!r}"


# --------------------------------------------------------------------------- #
# commit 3 — renderers (hand-built model fixtures; no real store is scanned)
# --------------------------------------------------------------------------- #

import csv as _csv  # noqa: E402
import io as _io  # noqa: E402

from app.experiment_review import render as render_module  # noqa: E402
from app.experiment_review import (  # noqa: E402
    EVIDENCE_DISCLAIMERS,
    export_evidence_pack_csv,
    export_evidence_pack_json,
    export_evidence_pack_markdown,
)

_CSV_HEADER = [
    "train_run_hash", "load_status", "audit_status", "completeness", "model_type",
    "task_type", "train_start", "train_end", "validation_start", "validation_end",
    "catalog_group", "catalog_rank", "requested_metric", "requested_metric_value",
    "metrics_json", "baseline_metrics_json", "missing_evidence",
]

_MD_SECTIONS = [
    "# Local Experiment Evidence Pack",
    "## Evidence summary",
    "## Selected runs",
    "## Structural integrity",
    "## Comparison",
    "## Catalog context",
    "## Missing or unavailable evidence",
    "## Registry and dataset-lineage context",
    "## Phase 14 aggregation findings",
    "## Scope & Safety",
]


def _render_audit_finding(**kw):
    base = dict(
        finding_id="finding_0003",
        severity=AuditSeverity.ERROR,
        code=AuditCode.MISSING_REFERENCED_ARTIFACT,
        message="referenced artifact is missing",
        train_run_hash="run_a",
        run_directory="run_a",
        artifact_name="predictions",
        relative_path="predictions.csv",
    )
    base.update(kw)
    return AuditFinding(**base)


def _run_evidence(hash_="run_a", **kw):
    base = dict(
        train_run_hash=hash_,
        run_directory=hash_,
        load_status=EvidenceLoadStatus.LOADED,
        completeness=EvidenceCompleteness.COMPLETE,
        audit_status="valid",
        audit_findings=(),
        created_at="2026-07-18T00:00:00+00:00",
        train_start="2024-04-01",
        train_end="2024-06-05",
        validation_start="2024-06-06",
        validation_end="2024-09-15",
        feature_columns=("feature__x",),
        label_column="label__y",
        model_type="ridge_regression",
        task_type="regression",
        metrics={"sharpe": 1.5, "mse": 0.1},
        baseline_metrics={"no_trade": {"sharpe": 0.0}},
        hash_chain={"train_run_hash": hash_},
        catalog_context=CatalogRunContext(status=EvidenceContextStatus.NOT_COLLECTED),
    )
    base.update(kw)
    return ExperimentRunEvidence(**base)


def _summary(runs, findings=(), completeness=EvidenceCompleteness.COMPLETE):
    def count(c):
        return sum(1 for r in runs if r.completeness == c)

    return EvidenceSummary(
        completeness=completeness,
        selected_runs_total=len(runs),
        runs_complete=count(EvidenceCompleteness.COMPLETE),
        runs_with_warnings=count(EvidenceCompleteness.WARNING),
        runs_incomplete=count(EvidenceCompleteness.INCOMPLETE),
        runs_unavailable=count(EvidenceCompleteness.UNAVAILABLE),
        phase14_findings_total=len(findings),
        phase13_findings_total=sum(len(r.audit_findings) for r in runs),
    )


def _render_pack(runs=None, comparison=None, findings=(), **kw):
    runs = tuple(runs if runs is not None else (_run_evidence(),))
    hashes = tuple(r.train_run_hash for r in runs)
    if comparison is None:
        comparison = ComparisonEvidence(
            status=EvidenceComparisonStatus.NOT_APPLICABLE
            if len(hashes) == 1
            else EvidenceComparisonStatus.AVAILABLE,
            selected_run_hashes=hashes,
            rows=()
            if len(hashes) == 1
            else tuple({"train_run_hash": h, "metrics": {"sharpe": 1.0}} for h in hashes),
            disclaimers=() if len(hashes) == 1 else ("Not investment advice.",),
        )
    base = dict(
        selected_run_hashes=hashes,
        runs=runs,
        comparison=comparison,
        evidence_summary=_summary(runs, findings, kw.pop("completeness", EvidenceCompleteness.COMPLETE)),
        findings=tuple(findings),
    )
    base.update(kw)
    return ExperimentEvidencePack(**base)


def _csv_rows(text):
    return list(_csv.reader(_io.StringIO(text)))


_FORBIDDEN_LANGUAGE = [
    "winner", "best run", "recommended", "approved", "rejected",
    "deploy-ready", "should buy", "should sell", "allocate to",
]


# --- JSON ------------------------------------------------------------------ #


def test_json_is_strict_and_round_trips():
    text = export_evidence_pack_json(_render_pack())
    assert isinstance(text, str) and text.endswith("\n")
    data = json.loads(text)
    assert data["selected_run_hashes"] == ["run_a"]
    assert "NaN" not in text and "Infinity" not in text


def test_json_is_deterministic():
    pack = _render_pack()
    assert export_evidence_pack_json(pack) == export_evidence_pack_json(pack)


def test_json_top_level_keys_are_stable():
    data = json.loads(export_evidence_pack_json(_render_pack()))
    assert set(data) == {
        "disclaimers", "selected_run_hashes", "runs", "comparison",
        "registry_context_status", "dataset_lineage_context_status",
        "catalog_context_status", "evidence_summary", "findings",
    }


def test_json_contains_every_disclaimer():
    data = json.loads(export_evidence_pack_json(_render_pack()))
    assert data["disclaimers"] == list(EVIDENCE_DISCLAIMERS)


def test_json_preserves_selected_run_order():
    runs = (_run_evidence("run_z"), _run_evidence("run_a"))
    data = json.loads(export_evidence_pack_json(_render_pack(runs)))
    assert data["selected_run_hashes"] == ["run_z", "run_a"]  # not sorted
    assert [r["train_run_hash"] for r in data["runs"]] == ["run_z", "run_a"]


def test_json_preserves_both_finding_namespaces_disjointly():
    run = _run_evidence(audit_findings=(_render_audit_finding(),))
    findings = sort_and_number_evidence_findings((_ev_finding(),))
    data = json.loads(export_evidence_pack_json(_render_pack((run,), findings=findings)))
    audit_ids = {f["finding_id"] for r in data["runs"] for f in r["audit_findings"]}
    pack_ids = {f["finding_id"] for f in data["findings"]}
    assert audit_ids == {"finding_0003"}  # not renumbered
    assert all(i.startswith("evidence_") for i in pack_ids)
    assert audit_ids.isdisjoint(pack_ids)


def test_json_none_becomes_null():
    run = _run_evidence("ghost", run_directory=None, model_type=None, metrics=None,
                        load_status=EvidenceLoadStatus.UNAVAILABLE,
                        completeness=EvidenceCompleteness.UNAVAILABLE, audit_status="unavailable")
    text = export_evidence_pack_json(
        _render_pack((run,), completeness=EvidenceCompleteness.UNAVAILABLE))
    data = json.loads(text)
    assert data["runs"][0]["model_type"] is None and data["runs"][0]["metrics"] is None
    assert ": null" in text


def test_json_has_no_timestamp_or_host_metadata():
    text = export_evidence_pack_json(_render_pack())
    for token in ("timestamp", "generated_at", "hostname", "machine",
                  "store_root", "base_dir", "cwd"):
        assert token not in text.lower()


def test_json_registry_and_lineage_remain_not_collected():
    data = json.loads(export_evidence_pack_json(_render_pack()))
    assert data["registry_context_status"] == "not_collected"
    assert data["dataset_lineage_context_status"] == "not_collected"


@pytest.mark.parametrize("unsafe", _HOST_ABSOLUTE)
def test_json_redacts_every_host_absolute_form(unsafe):
    run = _run_evidence(audit_findings=(_render_audit_finding(actual=unsafe, expected=unsafe,
                                                       message="declared " + unsafe),))
    text = export_evidence_pack_json(_render_pack((run,)))
    assert "secret" not in text and "server" not in text
    assert EVIDENCE_REDACTED_PATH in text


def test_json_preserves_safe_and_traversal_evidence():
    run = _run_evidence(audit_findings=(
        _render_audit_finding(relative_path="nested/frame.csv", actual="../evil.csv",
                       message="declares a traversal value"),))
    data = json.loads(export_evidence_pack_json(_render_pack((run,))))
    finding = data["runs"][0]["audit_findings"][0]
    assert finding["relative_path"] == "nested/frame.csv"
    assert finding["actual"] == "../evil.csv"  # factual, not a host-path leak
    assert EVIDENCE_REDACTED_PATH not in json.dumps(finding)


def test_renderers_do_not_mutate_pack_or_raw_findings():
    finding = _render_audit_finding(actual="C:\\secret\\x.csv")
    run = _run_evidence(audit_findings=(finding,))
    pack = _render_pack((run,))
    before_pack, before_finding = pack.to_dict(), dataclasses.astuple(finding)
    export_evidence_pack_json(pack)
    export_evidence_pack_csv(pack)
    export_evidence_pack_markdown(pack)
    assert pack.to_dict() == before_pack
    assert dataclasses.astuple(finding) == before_finding
    assert finding.actual == "C:\\secret\\x.csv"  # raw value intact in memory
    assert pack.disclaimers == ()  # renderer overlay did not leak back into the model


# --- CSV ------------------------------------------------------------------- #


def test_csv_header_is_exact_and_fixed():
    rows = _csv_rows(export_evidence_pack_csv(_render_pack()))
    assert rows[0] == _CSV_HEADER


def test_csv_is_deterministic():
    pack = _render_pack()
    assert export_evidence_pack_csv(pack) == export_evidence_pack_csv(pack)


def test_csv_one_row_per_run_in_selection_order():
    runs = (_run_evidence("run_z"), _run_evidence("run_a"))
    rows = _csv_rows(export_evidence_pack_csv(_render_pack(runs)))
    assert len(rows) == 3
    assert [r[0] for r in rows[1:]] == ["run_z", "run_a"]


def test_csv_has_no_dynamic_metric_columns():
    runs = (_run_evidence("run_a", metrics={"sharpe": 1.0}),
            _run_evidence("run_b", metrics={"calmar": 2.0, "sortino": 3.0}))
    rows = _csv_rows(export_evidence_pack_csv(_render_pack(runs)))
    assert rows[0] == _CSV_HEADER  # unchanged despite differing metric keys
    assert all(len(r) == len(_CSV_HEADER) for r in rows)


def test_csv_metrics_json_is_compact_and_sorted():
    run = _run_evidence(metrics={"sharpe": 1.5, "mse": 0.1},
                        baseline_metrics={"b": 2.0, "a": 1.0})
    rows = _csv_rows(export_evidence_pack_csv(_render_pack((run,))))
    assert rows[1][_CSV_HEADER.index("metrics_json")] == '{"mse":0.1,"sharpe":1.5}'
    assert rows[1][_CSV_HEADER.index("baseline_metrics_json")] == '{"a":1.0,"b":2.0}'


def test_csv_none_becomes_empty_string():
    run = _run_evidence("ghost", run_directory=None, model_type=None, task_type=None,
                        train_start=None, metrics=None, baseline_metrics=None,
                        load_status=EvidenceLoadStatus.UNAVAILABLE,
                        completeness=EvidenceCompleteness.UNAVAILABLE, audit_status="unavailable")
    row = _csv_rows(export_evidence_pack_csv(
        _render_pack((run,), completeness=EvidenceCompleteness.UNAVAILABLE)))[1]
    for column in ("model_type", "task_type", "train_start", "metrics_json", "catalog_rank"):
        assert row[_CSV_HEADER.index(column)] == ""


def test_csv_missing_evidence_is_deterministically_joined():
    run = _run_evidence(missing_evidence=("required_artifact_missing", "run_unloadable"),
                        completeness=EvidenceCompleteness.INCOMPLETE)
    row = _csv_rows(export_evidence_pack_csv(
        _render_pack((run,), completeness=EvidenceCompleteness.INCOMPLETE)))[1]
    assert row[_CSV_HEADER.index("missing_evidence")] == "required_artifact_missing;run_unloadable"


def test_csv_metric_columns_come_from_catalog_context():
    ctx = CatalogRunContext(status=EvidenceContextStatus.COLLECTED, compatibility_group="group_0000",
                            group_size=2, requested_metric="sharpe", requested_metric_value=1.5, rank=1)
    row = _csv_rows(export_evidence_pack_csv(_render_pack((_run_evidence(catalog_context=ctx),))))[1]
    assert row[_CSV_HEADER.index("catalog_group")] == "group_0000"
    assert row[_CSV_HEADER.index("catalog_rank")] == "1"
    assert row[_CSV_HEADER.index("requested_metric")] == "sharpe"
    assert row[_CSV_HEADER.index("requested_metric_value")] == "1.5"


def test_csv_escapes_commas_quotes_and_newlines():
    run = _run_evidence(model_type='ridge,"odd"\nname')
    text = export_evidence_pack_csv(_render_pack((run,)))
    assert _csv_rows(text)[1][_CSV_HEADER.index("model_type")] == 'ridge,"odd"\nname'


def test_csv_contains_no_findings_or_disclaimers():
    run = _run_evidence(audit_findings=(_render_audit_finding(),))
    findings = sort_and_number_evidence_findings((_ev_finding(),))
    text = export_evidence_pack_csv(_render_pack((run,), findings=findings))
    assert "finding_0003" not in text and "evidence_0000" not in text
    assert "MISSING_REFERENCED_ARTIFACT" not in text
    for disclaimer in EVIDENCE_DISCLAIMERS:
        assert disclaimer not in text
    assert len(_csv_rows(text)) == 2  # header + one run row, no pseudo-row


@pytest.mark.parametrize("unsafe", _HOST_ABSOLUTE)
def test_csv_has_no_absolute_paths_or_nonfinite(unsafe):
    run = _run_evidence(audit_findings=(_render_audit_finding(actual=unsafe),))
    text = export_evidence_pack_csv(_render_pack((run,)))
    assert "secret" not in text and "server" not in text
    assert "NaN" not in text and "Infinity" not in text


# --- Markdown -------------------------------------------------------------- #


def test_markdown_is_deterministic_and_returns_str():
    pack = _render_pack()
    text = export_evidence_pack_markdown(pack)
    assert isinstance(text, str)
    assert text == export_evidence_pack_markdown(pack)


def test_markdown_section_order_is_exact():
    text = export_evidence_pack_markdown(_render_pack())
    positions = [text.index(s) for s in _MD_SECTIONS]
    assert positions == sorted(positions)
    assert len(set(positions)) == len(_MD_SECTIONS)


def test_markdown_shows_completeness_and_summary_counts():
    text = export_evidence_pack_markdown(_render_pack())
    assert "**Evidence completeness:** complete" in text
    for key in ("selected_runs_total", "runs_complete", "runs_with_warnings",
                "runs_incomplete", "runs_unavailable",
                "phase14_findings_total", "phase13_findings_total"):
        assert "| " + key + " |" in text


def test_markdown_selected_runs_table():
    text = export_evidence_pack_markdown(_render_pack())
    assert "| train_run_hash | load_status | audit_status | completeness |" in text
    assert "2024-06-06 to 2024-09-15" in text


def test_markdown_structural_section_preserves_phase13_ids():
    run = _run_evidence(audit_findings=(_render_audit_finding(),))
    text = export_evidence_pack_markdown(_render_pack((run,)))
    integrity = text.split("## Structural integrity")[1].split("## Comparison")[0]
    assert "finding_0003" in integrity
    assert "MISSING_REFERENCED_ARTIFACT" in integrity and "error" in integrity


def test_markdown_clean_run_states_no_structural_findings():
    text = export_evidence_pack_markdown(_render_pack())
    integrity = text.split("## Structural integrity")[1].split("## Comparison")[0]
    assert "No structural findings were recorded for this run." in integrity


def test_markdown_namespaces_are_visually_separated():
    run = _run_evidence(audit_findings=(_render_audit_finding(),))
    findings = sort_and_number_evidence_findings((_ev_finding(),))
    text = export_evidence_pack_markdown(_render_pack((run,), findings=findings))
    integrity = text.split("## Structural integrity")[1].split("## Comparison")[0]
    phase14 = text.split("## Phase 14 aggregation findings")[1].split("## Scope & Safety")[0]
    assert "finding_0003" in integrity and "evidence_0000" not in integrity
    assert "evidence_0000" in phase14 and "finding_0003" not in phase14


def test_markdown_comparison_available():
    runs = (_run_evidence("run_a"), _run_evidence("run_b"))
    text = export_evidence_pack_markdown(_render_pack(runs))
    section = text.split("## Comparison")[1].split("## Catalog context")[0]
    assert "**Status:** available" in section
    assert "run_a" in section and "run_b" in section and "sharpe" in section
    assert "Inherited comparison disclaimers:" in section


def test_markdown_comparison_not_applicable_has_no_warning_language():
    section = export_evidence_pack_markdown(_render_pack()).split(
        "## Comparison")[1].split("## Catalog context")[0]
    assert "**Status:** not_applicable" in section
    assert "single selected run" in section
    for word in ("warning", "failed", "rejected", "error"):
        assert word not in section.lower()


def test_markdown_comparison_unavailable_is_factual():
    runs = (_run_evidence("run_a"), _run_evidence("run_b"))
    comparison = ComparisonEvidence(
        status=EvidenceComparisonStatus.UNAVAILABLE,
        selected_run_hashes=("run_a", "run_b"),
        unavailable_reason="one or more selected runs are missing or unloadable",
    )
    section = export_evidence_pack_markdown(_render_pack(runs, comparison=comparison)).split(
        "## Comparison")[1].split("## Catalog context")[0]
    assert "**Status:** unavailable" in section
    assert "one or more selected runs are missing or unloadable" in section
    for word in ("rejected", "failed validation", "invalid"):
        assert word not in section.lower()


def test_markdown_catalog_collected_and_not_collected():
    ctx = CatalogRunContext(status=EvidenceContextStatus.COLLECTED, compatibility_group="group_0000",
                            group_size=2, peer_train_run_hashes=("run_a", "run_b"),
                            requested_metric="sharpe", requested_metric_value=1.5, rank=1)
    collected = export_evidence_pack_markdown(
        _render_pack((_run_evidence(catalog_context=ctx),),
                     catalog_context_status=EvidenceContextStatus.COLLECTED)
    ).split("## Catalog context")[1].split("## Missing")[0]
    assert "**Status:** collected" in collected
    assert "group_0000" in collected and "run_b" in collected and "sharpe" in collected
    assert "descriptive ordering" in collected

    default = export_evidence_pack_markdown(_render_pack()).split(
        "## Catalog context")[1].split("## Missing")[0]
    assert "**Status:** not_collected" in default


def test_markdown_registry_section_is_neutral():
    section = export_evidence_pack_markdown(_render_pack()).split(
        "## Registry and dataset-lineage context")[1].split("## Phase 14")[0]
    assert "**Registry context:** not_collected" in section
    assert "**Dataset-lineage context:** not_collected" in section
    assert "was not queried" in section and "no database was opened" in section
    assert "not missing evidence" in section  # explicitly NOT called missing evidence


def test_markdown_missing_evidence_section():
    run = _run_evidence(missing_evidence=("required_artifact_missing",),
                        completeness=EvidenceCompleteness.INCOMPLETE)
    section = export_evidence_pack_markdown(
        _render_pack((run,), completeness=EvidenceCompleteness.INCOMPLETE)
    ).split("## Missing or unavailable evidence")[1].split("## Registry")[0]
    assert "required_artifact_missing" in section


def test_markdown_contains_every_disclaimer():
    text = export_evidence_pack_markdown(_render_pack())
    scope = text.split("## Scope & Safety")[1]
    for disclaimer in EVIDENCE_DISCLAIMERS:
        assert "- " + disclaimer in scope
    assert "not investment advice" in scope.lower()
    assert "does not approve deployment" in scope


def test_markdown_escapes_pipes_and_collapses_newlines():
    run = _run_evidence(model_type="a|b", task_type="line1\nline2")
    text = export_evidence_pack_markdown(_render_pack((run,)))
    assert "a\\|b" in text
    assert "line1 line2" in text
    for line in text.splitlines():
        if line.startswith("|"):
            assert line.endswith("|")  # no row broken by an embedded newline


@pytest.mark.parametrize("unsafe", _HOST_ABSOLUTE)
def test_markdown_redacts_host_absolute_forms(unsafe):
    run = _run_evidence(audit_findings=(_render_audit_finding(actual=unsafe, expected=unsafe,
                                                       message="declared " + unsafe),))
    text = export_evidence_pack_markdown(_render_pack((run,)))
    assert "secret" not in text and "server" not in text
    assert EVIDENCE_REDACTED_PATH in text


def test_markdown_has_no_timestamp_host_or_nonfinite():
    text = export_evidence_pack_markdown(_render_pack())
    assert "NaN" not in text and "Infinity" not in text
    for token in ("timestamp", "generated at", "hostname", "store_root", "base_dir"):
        assert token not in text.lower()


@pytest.mark.parametrize("phrase", _FORBIDDEN_LANGUAGE)
def test_markdown_uses_no_recommendation_language(phrase):
    ctx = CatalogRunContext(status=EvidenceContextStatus.COLLECTED, compatibility_group="group_0000",
                            group_size=1, requested_metric="sharpe",
                            requested_metric_value=1.5, rank=1)
    runs = (_run_evidence("run_a", catalog_context=ctx), _run_evidence("run_b"))
    text = export_evidence_pack_markdown(_render_pack(runs)).lower()
    assert phrase not in text


def test_markdown_run_heading_is_escaped():
    """A newline in a hash must not inject a heading and break the fixed section set."""
    hostile = "run_a\n## Comparison"
    run = _run_evidence(hostile, run_directory=None,
                        load_status=EvidenceLoadStatus.UNAVAILABLE,
                        completeness=EvidenceCompleteness.UNAVAILABLE,
                        audit_status="unavailable")
    text = export_evidence_pack_markdown(
        _render_pack((run,), completeness=EvidenceCompleteness.UNAVAILABLE))
    assert text.count("\n## Comparison\n") == 1  # exactly the real section
    headings = [ln for ln in text.splitlines() if ln.startswith("#")]
    assert len(headings) == len(_MD_SECTIONS) + 1  # 10 fixed sections + one run heading


def test_markdown_comparison_header_cells_are_escaped():
    """The comparison header is the only data-derived header, so it needs escaping."""
    rows = ({"train_run_hash": "run_a", "metrics": {"pnl|net": 1.0}},
            {"train_run_hash": "run_b", "metrics": {"pnl|net": 2.0}})
    comparison = ComparisonEvidence(
        status=EvidenceComparisonStatus.AVAILABLE,
        selected_run_hashes=("run_a", "run_b"), rows=rows)
    text = export_evidence_pack_markdown(
        _render_pack((_run_evidence("run_a"), _run_evidence("run_b")), comparison=comparison))
    section = text.split("## Comparison")[1].split("## Catalog context")[0]
    table = [ln for ln in section.splitlines() if ln.startswith("|")]
    assert "pnl\\|net" in table[0]
    widths = {len(ln.split(" | ")) for ln in table}
    assert len(widths) == 1, "header, separator, and body rows must have equal cell counts"


def test_disclaimers_are_ascii_and_deterministic():
    """ASCII-only, like the Phase 10 / Phase 13 disclaimers, so a console-bound CLI
    cannot mangle them on a non-UTF-8 code page."""
    assert isinstance(EVIDENCE_DISCLAIMERS, tuple) and len(EVIDENCE_DISCLAIMERS) == 8
    for disclaimer in EVIDENCE_DISCLAIMERS:
        disclaimer.encode("ascii")  # raises if a non-ASCII character sneaks in
        assert disclaimer.endswith(".")


def test_disclaimers_carry_no_advice_or_remediation():
    joined = " ".join(EVIDENCE_DISCLAIMERS).lower()
    for token in ("run ", "rerun", "delete", "repair", "fix ", "you should",
                  "buy", "sell", "allocate", "promote"):
        assert token not in joined
    # "deployment" may appear only in a negative statement
    for disclaimer in EVIDENCE_DISCLAIMERS:
        if "deployment" in disclaimer.lower():
            assert "does not approve" in disclaimer.lower()
    assert not any("creates new evidence" in d.lower() for d in EVIDENCE_DISCLAIMERS)


# --- boundaries ------------------------------------------------------------ #


def test_all_renderers_return_str_and_touch_no_repo_artifacts():
    before = _repo_snapshot()
    pack = _render_pack()
    for renderer in (export_evidence_pack_json, export_evidence_pack_csv,
                     export_evidence_pack_markdown):
        assert isinstance(renderer(pack), str)
    assert _repo_snapshot() == before
    assert not (_BACKEND / "data" / "quantlab.db").exists()


def test_render_module_has_no_forbidden_imports():
    src = Path(render_module.__file__).read_text(encoding="utf-8")
    for token in ("app.experiment_audit", "app.experiments", "app.reporting",
                  "app.experiment_catalog", "app.experiment_registry",
                  "app.dataset_registry", "app.db", "sqlite3", "get_connection",
                  "local_pipeline", "batch_experiments", "hashlib", "sha256",
                  "import requests", "urllib", "httpx", "socket", "yfinance",
                  "sklearn", "xgboost", "lightgbm", "torch", "tensorflow",
                  "ExperimentStore", "AuditFinding", "pandas", "numpy"):
        assert token not in src, "render.py must not reference " + repr(token)


def test_render_module_performs_no_filesystem_access():
    src = Path(render_module.__file__).read_text(encoding="utf-8")
    for token in ("open(", ".write_text", ".write_bytes", ".mkdir", ".touch",
                  ".unlink", ".rmdir", ".rename", "rmtree", "shutil", "to_csv",
                  "to_parquet", "os.remove", "Path(", "pathlib", ".exists()",
                  ".stat(", ".resolve(", ".glob("):
        assert token not in src, "render.py must not contain filesystem call " + repr(token)


def test_render_module_never_bypasses_the_model_projection():
    """Nested output must come from the pack mapping, not raw finding objects."""
    src = Path(render_module.__file__).read_text(encoding="utf-8")
    for token in (".audit_findings", "audit_finding_dict", ".actual", ".expected",
                  "AuditFinding", "redact_host_absolute_text", "is_host_absolute_path"):
        assert token not in src, "render.py must not use " + repr(token) + " directly"
    assert "pack.to_dict()" in src


def test_render_module_has_no_repair_or_advice_language():
    src = Path(render_module.__file__).read_text(encoding="utf-8").lower()
    for token in ("repair", "quarantine", "migrate", "delete the", "buy ", "sell ",
                  "allocate", "uuid"):
        assert token not in src, "render.py must not contain " + repr(token)


# --------------------------------------------------------------------------- #
# commit 4 — CLI (scripts/build_experiment_evidence_pack.py)
# --------------------------------------------------------------------------- #

import importlib.util  # noqa: E402

_REPO_ROOT = _BACKEND.parent
_PACK_CLI_PATH = _REPO_ROOT / "scripts" / "build_experiment_evidence_pack.py"


def _load_pack_cli():
    spec = importlib.util.spec_from_file_location("evidence_pack_cli", _PACK_CLI_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cli_run(capsys, *argv):
    """Run the CLI in-process; returns (exit_code, stdout)."""
    mod = _load_pack_cli()
    try:
        code = mod.main([str(a) for a in argv])
    except SystemExit as exc:  # argparse usage error
        code = exc.code if isinstance(exc.code, int) else 2
    return code, capsys.readouterr().out


def _cli_store(tmp_path, names=("run_a",), **overrides):
    return _store(tmp_path, names, **overrides)


def _warning_pack_store(tmp_path):
    """One valid run plus an orphan artifact -> audit warning -> pack WARNING."""
    store = _store(tmp_path, ("run_a",))
    (store.base_dir / "run_a" / "extra.json").write_text("{}", encoding="utf-8")
    return store


def _incomplete_pack_store(tmp_path):
    """A missing referenced artifact -> audit error -> pack INCOMPLETE."""
    store = _store(tmp_path, ("run_a",))
    (store.base_dir / "run_a" / "predictions.csv").unlink()
    return store


def _out(tmp_path, name):
    return tmp_path / "cli_out" / name


# --- arguments ------------------------------------------------------------- #


def test_cli_help_exits_zero(capsys):
    code, out = _cli_run(capsys, "--help")
    assert code == 0
    assert "read-only" in out and "not investment advice" in out
    for claim in ("approved", "deployment ready", "profitab", "safe to trade"):
        assert claim not in out.lower()


def test_cli_help_marks_severity_console_only(capsys):
    _, out = _cli_run(capsys, "--help")
    assert "Console display only" in out or "console display only" in out.lower()


def test_cli_missing_artifacts_dir_is_usage_error(capsys):
    code, _ = _cli_run(capsys, "--run-hash", "run_a")
    assert code == 2


def test_cli_missing_run_hashes_is_usage_error(capsys, tmp_path):
    store = _cli_store(tmp_path)
    code, _ = _cli_run(capsys, "--artifacts-dir", store.base_dir)
    assert code == 2


@pytest.mark.parametrize(
    "extra",
    [
        ("--audit-level", "bogus"),
        ("--fail-on", "bogus"),
        ("--severity", "bogus"),
        ("--maximize", "--minimize"),
        ("--include-catalog-context", "--no-catalog-context"),
    ],
)
def test_cli_invalid_argument_combinations_exit_two(capsys, tmp_path, extra):
    store = _cli_store(tmp_path)
    code, _ = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a", *extra)
    assert code == 2


def test_cli_rejects_forbidden_v1_arguments(capsys, tmp_path):
    store = _cli_store(tmp_path)
    for flag in ("--include-registry-context", "--database-path", "--allow-different-windows"):
        code, _ = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a", flag)
        assert code == 2, flag + " must not be a v1 argument"


# --- run selection --------------------------------------------------------- #


def test_cli_repeated_run_hash_preserves_order(capsys, tmp_path):
    store = _cli_store(tmp_path, ("run_a", "run_b"))
    out_json = _out(tmp_path, "p.json")
    code, _ = _cli_run(capsys, "--artifacts-dir", store.base_dir,
                       "--run-hash", "run_b", "--run-hash", "run_a",
                       "--output-json", out_json)
    assert code == 0
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["selected_run_hashes"] == ["run_b", "run_a"]  # not sorted


def test_cli_hashes_file_with_comments_and_blanks(capsys, tmp_path):
    store = _cli_store(tmp_path, ("run_a", "run_b"))
    listing = tmp_path / "sel.txt"
    listing.write_text("# a comment\n\n  run_b  \n\t# indented comment\nrun_a\n\n",
                       encoding="utf-8")
    out_json = _out(tmp_path, "p.json")
    code, _ = _cli_run(capsys, "--artifacts-dir", store.base_dir,
                       "--run-hashes-file", listing, "--output-json", out_json)
    assert code == 0
    assert json.loads(out_json.read_text(encoding="utf-8"))["selected_run_hashes"] == ["run_b", "run_a"]


def test_cli_hashes_combine_cli_then_file_with_first_occurrence_kept(capsys, tmp_path):
    store = _cli_store(tmp_path, ("run_a", "run_b", "run_c"))
    listing = tmp_path / "sel.txt"
    listing.write_text("run_a\nrun_c\n", encoding="utf-8")  # run_a duplicates the CLI value
    out_json = _out(tmp_path, "p.json")
    code, _ = _cli_run(capsys, "--artifacts-dir", store.base_dir,
                       "--run-hash", "run_b", "--run-hash", "run_a",
                       "--run-hashes-file", listing, "--output-json", out_json)
    assert code == 0
    assert json.loads(out_json.read_text(encoding="utf-8"))["selected_run_hashes"] == [
        "run_b", "run_a", "run_c"]


def test_cli_whitespace_only_hash_is_usage_error(capsys, tmp_path):
    store = _cli_store(tmp_path)
    code, _ = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "   ")
    assert code == 2


def test_cli_comment_only_hashes_file_is_usage_error(capsys, tmp_path):
    store = _cli_store(tmp_path)
    listing = tmp_path / "sel.txt"
    listing.write_text("# nothing selected\n\n", encoding="utf-8")
    code, _ = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hashes-file", listing)
    assert code == 2


def test_cli_missing_hashes_file_exits_three(capsys, tmp_path):
    store = _cli_store(tmp_path)
    code, out = _cli_run(capsys, "--artifacts-dir", store.base_dir,
                         "--run-hashes-file", tmp_path / "nope.txt")
    assert code == 3
    assert "ERROR:" in out and "Traceback" not in out
    assert tmp_path.name not in out


def test_cli_directory_as_hashes_file_exits_three(capsys, tmp_path):
    store = _cli_store(tmp_path)
    code, out = _cli_run(capsys, "--artifacts-dir", store.base_dir,
                         "--run-hashes-file", tmp_path)
    assert code == 3
    assert "not a regular file" in out and "Traceback" not in out


def test_cli_invalid_utf8_hashes_file_exits_three(capsys, tmp_path):
    store = _cli_store(tmp_path)
    listing = tmp_path / "sel.txt"
    listing.write_bytes(b"run_a\n\xff\xfe\x00invalid\n")
    code, out = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hashes-file", listing)
    assert code == 3
    assert "UTF-8" in out and "Traceback" not in out
    assert tmp_path.name not in out


# --- store root ------------------------------------------------------------ #


def test_cli_missing_store_root_exits_three(capsys, tmp_path):
    code, out = _cli_run(capsys, "--artifacts-dir", tmp_path / "nope", "--run-hash", "run_a")
    assert code == 3
    assert "does not exist" in out and "Traceback" not in out
    assert tmp_path.name not in out


def test_cli_file_as_store_root_exits_three(capsys, tmp_path):
    target = tmp_path / "a_file.txt"
    target.write_text("x", encoding="utf-8")
    code, out = _cli_run(capsys, "--artifacts-dir", target, "--run-hash", "run_a")
    assert code == 3
    assert "not a directory" in out and "Traceback" not in out


def test_cli_does_not_create_the_store_root(capsys, tmp_path):
    missing = tmp_path / "nope"
    _cli_run(capsys, "--artifacts-dir", missing, "--run-hash", "run_a")
    assert not missing.exists()


def test_cli_empty_store_with_missing_hash_is_unavailable(capsys, tmp_path):
    root = tmp_path / "empty_store"
    root.mkdir()
    code, out = _cli_run(capsys, "--artifacts-dir", root, "--run-hash", "ghost")
    assert code == 1  # UNAVAILABLE meets the default --fail-on incomplete
    assert "RESULT: UNAVAILABLE" in out
    assert "Traceback" not in out
    assert str(root) not in out and tmp_path.name not in out


# --- RESULT and thresholds ------------------------------------------------- #


@pytest.mark.parametrize(
    "maker,word,default_code,warning_code",
    [
        (lambda p: _store(p, ("run_a",)), "COMPLETE", 0, 0),
        (_warning_pack_store, "WARNING", 0, 1),
        (_incomplete_pack_store, "INCOMPLETE", 1, 1),
    ],
)
def test_cli_result_and_exit_codes(capsys, tmp_path, maker, word, default_code, warning_code):
    store = maker(tmp_path)
    code, out = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a")
    assert f"RESULT: {word}" in out
    assert code == default_code
    code2, out2 = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a",
                           "--fail-on", "warning")
    assert f"RESULT: {word}" in out2
    assert code2 == warning_code


def test_cli_unavailable_exits_one_under_both_thresholds(capsys, tmp_path):
    store = _cli_store(tmp_path)
    for extra in ((), ("--fail-on", "warning")):
        code, out = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "ghost", *extra)
        assert "RESULT: UNAVAILABLE" in out and code == 1


def test_cli_prints_exactly_one_result_line(capsys, tmp_path):
    store = _warning_pack_store(tmp_path)
    _, out = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a")
    assert len([ln for ln in out.splitlines() if ln.startswith("RESULT: ")]) == 1


def test_cli_never_prints_approval_or_trading_words(capsys, tmp_path):
    store = _warning_pack_store(tmp_path)
    _, out = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a")
    for banned in ("APPROVED", "REJECTED", "DEPLOYABLE", "PRODUCTION READY",
                   "SAFE TO TRADE", "BUY", "SELL"):
        assert banned not in out


# --- console summary ------------------------------------------------------- #


def test_cli_summary_has_every_canonical_count_in_order(capsys, tmp_path):
    store = _cli_store(tmp_path, ("run_a", "run_b"))
    _, out = _cli_run(capsys, "--artifacts-dir", store.base_dir,
                      "--run-hash", "run_a", "--run-hash", "run_b", "--run-hash", "ghost")
    line = next(ln for ln in out.splitlines() if ln.startswith("SUMMARY "))
    assert line == (
        "SUMMARY selected_runs_total=3 runs_complete=2 runs_with_warnings=0 "
        "runs_incomplete=0 runs_unavailable=1 phase14_findings_total=2 "
        "phase13_findings_total=0"
    )


def test_cli_console_has_no_timestamp_host_or_store_path(capsys, tmp_path):
    store = _warning_pack_store(tmp_path)
    _, out = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a")
    assert str(store.base_dir) not in out and tmp_path.name not in out
    assert ":\\" not in out and ":/" not in out
    for token in ("timestamp", "generated at", "hostname", "username"):
        assert token not in out.lower()


# --- detailed findings ----------------------------------------------------- #


def test_cli_detailed_findings_preserve_both_namespaces(capsys, tmp_path):
    store = _warning_pack_store(tmp_path)
    _, out = _cli_run(capsys, "--artifacts-dir", store.base_dir,
                      "--run-hash", "run_a", "--run-hash", "ghost")
    audit_lines = [ln for ln in out.splitlines() if ln.startswith("AUDIT_FINDING ")]
    evidence_lines = [ln for ln in out.splitlines() if ln.startswith("EVIDENCE_FINDING ")]
    assert audit_lines and evidence_lines
    assert all("id=finding_" in ln for ln in audit_lines)
    assert all("id=evidence_" in ln for ln in evidence_lines)
    assert all("id=evidence_" not in ln for ln in audit_lines)


def test_cli_findings_are_deterministic(capsys, tmp_path):
    store = _warning_pack_store(tmp_path)
    _, first = _cli_run(capsys, "--artifacts-dir", store.base_dir,
                        "--run-hash", "run_a", "--run-hash", "ghost")
    _, second = _cli_run(capsys, "--artifacts-dir", store.base_dir,
                         "--run-hash", "run_a", "--run-hash", "ghost")
    assert first == second


def test_cli_finding_lines_hide_raw_paths_and_collapse_newlines(capsys, tmp_path):
    store = _store(tmp_path, ("run_a",))
    path = store.base_dir / "run_a" / "metadata.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["artifact_paths"]["predictions"] = "C:\\secret\\x.csv"
    path.write_text(json.dumps(data), encoding="utf-8")
    _, out = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a")
    assert "secret" not in out
    for line in out.splitlines():
        if line.startswith(("AUDIT_FINDING ", "EVIDENCE_FINDING ")):
            assert "\t" not in line
            assert "actual=" not in line and "expected=" not in line


@pytest.mark.parametrize(
    "threshold,expect_info,expect_warning,expect_error",
    [(None, True, True, True), ("info", True, True, True), ("warning", False, True, True),
     ("error", False, False, True), ("critical", False, False, False)],
)
def test_cli_severity_filters_only_detailed_lines(capsys, tmp_path, threshold,
                                                  expect_info, expect_warning, expect_error):
    store = _warning_pack_store(tmp_path)          # warning-severity audit finding
    (store.base_dir / "run_b").mkdir()             # non-run entry is not selected
    argv = ["--artifacts-dir", store.base_dir, "--run-hash", "run_a", "--run-hash", "ghost"]
    if threshold:
        argv += ["--severity", threshold]
    code, out = _cli_run(capsys, *argv)
    detailed = [ln for ln in out.splitlines()
                if ln.startswith(("AUDIT_FINDING ", "EVIDENCE_FINDING "))]
    assert any("severity=warning" in ln for ln in detailed) is expect_warning
    assert any("severity=error" in ln for ln in detailed) is expect_error
    # canonical output is untouched by the display filter
    assert "RESULT: INCOMPLETE" in out
    assert "phase14_findings_total=2" in out and "phase13_findings_total=1" in out
    assert code == 1


def test_cli_displayed_counts_match_printed_lines(capsys, tmp_path):
    store = _warning_pack_store(tmp_path)
    _, out = _cli_run(capsys, "--artifacts-dir", store.base_dir,
                      "--run-hash", "run_a", "--run-hash", "ghost", "--severity", "error")
    line = next(ln for ln in out.splitlines() if ln.startswith("DISPLAYED "))
    printed14 = len([ln for ln in out.splitlines() if ln.startswith("EVIDENCE_FINDING ")])
    printed13 = len([ln for ln in out.splitlines() if ln.startswith("AUDIT_FINDING ")])
    assert line == (f"DISPLAYED phase14_findings={printed14} "
                    f"phase13_findings={printed13} severity_threshold=error")


def test_cli_severity_does_not_change_result_summary_or_exit_code(capsys, tmp_path):
    store = _warning_pack_store(tmp_path)
    base_code, base_out = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a")
    filt_code, filt_out = _cli_run(capsys, "--artifacts-dir", store.base_dir,
                                   "--run-hash", "run_a", "--severity", "critical")
    assert base_code == filt_code
    def canonical(text):
        return [ln for ln in text.splitlines() if ln.startswith(("RESULT: ", "SUMMARY "))]
    assert canonical(base_out) == canonical(filt_out)


def test_cli_severity_does_not_change_exports(capsys, tmp_path):
    store = _warning_pack_store(tmp_path)
    a, b = _out(tmp_path, "a.json"), _out(tmp_path, "b.json")
    _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a", "--output-json", a)
    _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a",
             "--output-json", b, "--severity", "critical")
    assert a.read_bytes() == b.read_bytes()


# --- collector delegation -------------------------------------------------- #


def test_cli_calls_collector_exactly_once_with_the_right_arguments(capsys, tmp_path, monkeypatch):
    store = _cli_store(tmp_path, ("run_a", "run_b"))
    mod = _load_pack_cli()
    calls = []
    original = mod.collect_experiment_evidence_pack

    def spy(store_arg, hashes, **kwargs):
        calls.append((list(hashes), kwargs))
        return original(store_arg, hashes, **kwargs)

    monkeypatch.setattr(mod, "collect_experiment_evidence_pack", spy)
    out_json, out_csv, out_md = (_out(tmp_path, n) for n in ("p.json", "p.csv", "p.md"))
    code = mod.main([
        "--artifacts-dir", str(store.base_dir), "--run-hash", "run_b", "--run-hash", "run_a",
        "--metric", "sharpe", "--minimize", "--audit-level", "deep",
        "--output-json", str(out_json), "--output-csv", str(out_csv), "--output-markdown", str(out_md),
    ])
    assert code in (0, 1)
    assert len(calls) == 1, "the collector must run once for all three outputs"
    hashes, kwargs = calls[0]
    assert hashes == ["run_b", "run_a"]          # explicit order preserved
    assert kwargs["audit_level"] == "deep"
    assert kwargs["include_catalog_context"] is True
    assert kwargs["maximize"] is False
    assert kwargs["metric"] == "sharpe"

    calls.clear()  # the catalog flag is threaded through too (without a metric)
    assert mod.main(["--artifacts-dir", str(store.base_dir), "--run-hash", "run_a",
                     "--no-catalog-context"]) in (0, 1)
    assert calls[0][1]["include_catalog_context"] is False


def test_cli_renders_each_requested_format_once(capsys, tmp_path, monkeypatch):
    store = _cli_store(tmp_path)
    mod = _load_pack_cli()
    counts = {"json": 0, "csv": 0, "md": 0}
    for key, name in (("json", "export_evidence_pack_json"), ("csv", "export_evidence_pack_csv"),
                      ("md", "export_evidence_pack_markdown")):
        original = getattr(mod, name)

        def counting(pack, _k=key, _o=original):
            counts[_k] += 1
            return _o(pack)

        monkeypatch.setattr(mod, name, counting)
    mod.main(["--artifacts-dir", str(store.base_dir), "--run-hash", "run_a",
              "--output-json", str(_out(tmp_path, "p.json")),
              "--output-csv", str(_out(tmp_path, "p.csv")),
              "--output-markdown", str(_out(tmp_path, "p.md"))])
    assert counts == {"json": 1, "csv": 1, "md": 1}


def test_cli_module_does_not_import_phase_10_12_13_internals():
    src = _PACK_CLI_PATH.read_text(encoding="utf-8")
    for token in ("app.experiment_audit", "app.experiment_catalog", "app.reporting",
                  "app.experiment_registry", "app.dataset_registry", "app.db", "sqlite3",
                  "get_connection", "local_pipeline", "batch_experiments", "hashlib", "sha256",
                  "audit_experiment_run", "audit_experiment_store", "build_experiment_catalog",
                  "rank_experiment_catalog", "compare_experiment_runs",
                  "run_local_futures_ml_experiment", "train_model", "build_feature_matrix",
                  "import requests", "urllib", "httpx", "socket", "yfinance",
                  "sklearn", "xgboost", "lightgbm", "torch", "tensorflow"):
        assert token not in src, "the CLI must not reference " + repr(token)


def test_cli_module_never_reads_raw_audit_findings():
    src = _PACK_CLI_PATH.read_text(encoding="utf-8")
    for token in ("AuditFinding", ".audit_findings", "safe_audit_finding_dict"):
        assert token not in src, "the CLI must not use " + repr(token)
    assert "pack.to_dict()" in src


def test_cli_module_writes_only_in_the_explicit_output_helper():
    src = _PACK_CLI_PATH.read_text(encoding="utf-8")
    assert src.count(".write_text(") == 1 and src.count(".mkdir(") == 1
    body = src.split("def _write_output")[1].split("\ndef ")[0]
    assert ".write_text(" in body and ".mkdir(" in body
    for token in (".write_bytes", ".unlink", ".rmdir", ".rename", "rmtree", "shutil",
                  "to_csv", "to_parquet", "os.remove"):
        assert token not in src, "the CLI must not contain " + repr(token)


def test_cli_module_has_no_repair_or_advice_language():
    src = _PACK_CLI_PATH.read_text(encoding="utf-8").lower()
    for token in ("repair", "quarantine", "migrate", "deploy-ready", "approve the",
                  "promote", "profitab"):
        assert token not in src, "the CLI must not contain " + repr(token)


# --- outputs --------------------------------------------------------------- #


def test_cli_writes_nothing_without_output_flags(capsys, tmp_path):
    store = _cli_store(tmp_path)
    before = _snapshot(store.base_dir)
    entries_before = sorted(p.name for p in tmp_path.iterdir())
    code, out = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a")
    assert code == 0 and "WROTE:" not in out
    assert sorted(p.name for p in tmp_path.iterdir()) == entries_before
    assert _snapshot(store.base_dir) == before


@pytest.mark.parametrize("flag,name,filename", [("--output-json", "JSON", "p.json"),
                                                ("--output-csv", "CSV", "p.csv"),
                                                ("--output-markdown", "MARKDOWN", "p.md")])
def test_cli_writes_only_the_requested_format(capsys, tmp_path, flag, name, filename):
    store = _cli_store(tmp_path)
    target = _out(tmp_path, filename)
    code, out = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a",
                         flag, target)
    assert code == 0
    assert f"WROTE: {name}" in out
    assert sorted(p.name for p in target.parent.iterdir()) == [filename]
    assert str(target) not in out and target.name not in out  # path-neutral message


def test_cli_writes_all_three_outputs(capsys, tmp_path):
    store = _cli_store(tmp_path)
    paths = [_out(tmp_path, n) for n in ("p.json", "p.csv", "p.md")]
    code, out = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a",
                         "--output-json", paths[0], "--output-csv", paths[1],
                         "--output-markdown", paths[2])
    assert code == 0
    assert [ln for ln in out.splitlines() if ln.startswith("WROTE:")] == [
        "WROTE: JSON", "WROTE: CSV", "WROTE: MARKDOWN"]
    assert all(p.exists() for p in paths)


def test_cli_outputs_are_byte_identical_across_runs(capsys, tmp_path):
    store = _warning_pack_store(tmp_path)
    first, second = _out(tmp_path, "a.md"), _out(tmp_path, "b.md")
    _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a",
             "--output-markdown", first)
    _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a",
             "--output-markdown", second)
    assert first.read_bytes() == second.read_bytes()


def test_cli_creates_parent_only_for_the_explicit_output(capsys, tmp_path):
    store = _cli_store(tmp_path)
    target = tmp_path / "deep" / "nested" / "p.json"
    _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a",
             "--output-json", target)
    assert target.exists()
    assert not (tmp_path / "reports").exists()
    assert not (_REPO_ROOT / "reports").exists()


def test_cli_rejects_output_inside_the_store(capsys, tmp_path):
    store = _cli_store(tmp_path)
    target = store.base_dir / "leaked.json"
    code, out = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a",
                         "--output-json", target)
    assert code == 3
    assert "inside the audited ExperimentStore" in out
    assert not target.exists() and "Traceback" not in out


def test_cli_rejects_store_root_as_output(capsys, tmp_path):
    store = _cli_store(tmp_path)
    code, out = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a",
                         "--output-json", store.base_dir)
    assert code == 3
    assert "ExperimentStore root" in out or "existing directory" in out


def test_cli_rejects_directory_as_output(capsys, tmp_path):
    store = _cli_store(tmp_path)
    target = tmp_path / "a_dir"
    target.mkdir()
    code, out = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a",
                         "--output-json", target)
    assert code == 3 and "existing directory" in out


def test_cli_rejects_equivalent_output_destinations(capsys, tmp_path):
    store = _cli_store(tmp_path)
    target = _out(tmp_path, "same.txt")
    equivalent = target.parent / "." / "same.txt"
    code, out = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a",
                         "--output-json", target, "--output-csv", equivalent)
    assert code == 3 and "duplicates" in out
    assert not target.exists()  # nothing written before validation completed


def test_cli_rejects_symlink_output_into_the_store(capsys, tmp_path):
    store = _cli_store(tmp_path)
    link = tmp_path / "link_into_store"
    try:
        link.symlink_to(store.base_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not permitted on this platform")
    code, out = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a",
                         "--output-json", link / "leaked.json")
    assert code == 3
    assert "inside the audited ExperimentStore" in out
    assert not (store.base_dir / "leaked.json").exists()


def test_cli_validates_all_outputs_before_writing_any(capsys, tmp_path):
    store = _cli_store(tmp_path)
    good = _out(tmp_path, "good.json")
    code, out = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a",
                         "--output-json", good, "--output-csv", store.base_dir / "bad.csv")
    assert code == 3
    assert not good.exists(), "no output may be written when another path is invalid"
    assert "WROTE:" not in out


def test_cli_output_write_failure_exits_three(capsys, tmp_path, monkeypatch):
    store = _cli_store(tmp_path)
    mod = _load_pack_cli()

    def boom(path_str, text):
        raise OSError(f"disk error at {path_str}")

    monkeypatch.setattr(mod, "_write_output", boom)
    target = _out(tmp_path, "p.json")
    code = mod.main(["--artifacts-dir", str(store.base_dir), "--run-hash", "run_a",
                     "--output-json", str(target)])
    out = capsys.readouterr().out
    assert code == 3
    assert "could not be written" in out and "WROTE:" not in out
    assert "Traceback" not in out and str(target) not in out


def test_cli_leaves_the_store_byte_identical(capsys, tmp_path):
    store = _warning_pack_store(tmp_path)
    before = _snapshot(store.base_dir)
    _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a",
             "--run-hash", "ghost", "--audit-level", "deep",
             "--output-json", _out(tmp_path, "p.json"),
             "--output-csv", _out(tmp_path, "p.csv"),
             "--output-markdown", _out(tmp_path, "p.md"))
    assert _snapshot(store.base_dir) == before


def test_cli_traversal_output_path_never_mkdirs_inside_the_store(capsys, tmp_path):
    """The write target must be the path containment was validated against.

    A lexical parent containing '..' through a non-existent component would otherwise
    make mkdir(parents=True) recurse and create a directory inside the store."""
    store = _cli_store(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    target = store.base_dir / "x" / ".." / ".." / "outside" / "p.json"
    before = _snapshot(store.base_dir)
    code, out = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a",
                         "--output-json", target)
    assert not (store.base_dir / "x").exists(), "no directory may be created in the store"
    assert _snapshot(store.base_dir) == before
    if code == 0:
        assert (outside / "p.json").exists()  # written to the validated resolved path
        assert "WROTE: JSON" in out
    else:
        assert code == 3 and "Traceback" not in out


def test_cli_output_write_uses_the_validated_resolved_path(capsys, tmp_path, monkeypatch):
    store = _cli_store(tmp_path)
    mod = _load_pack_cli()
    seen = []
    original = mod._write_output

    def spy(path, text):
        seen.append(path)
        return original(path, text)

    monkeypatch.setattr(mod, "_write_output", spy)
    target = tmp_path / "sub" / ".." / "sub2" / "p.json"
    (tmp_path / "sub2").mkdir()
    mod.main(["--artifacts-dir", str(store.base_dir), "--run-hash", "run_a",
              "--output-json", str(target)])
    assert len(seen) == 1
    assert seen[0] == Path(target).resolve()  # resolved, not the raw lexical string
    assert ".." not in seen[0].parts


# --- expected selected-run problems ---------------------------------------- #


def test_cli_malformed_run_produces_a_pack_not_a_runtime_error(capsys, tmp_path):
    store = _store(tmp_path, ("run_a", "run_bad"))
    (store.base_dir / "run_bad" / "metadata.json").write_text("{ not json", encoding="utf-8")
    code, out = _cli_run(capsys, "--artifacts-dir", store.base_dir,
                         "--run-hash", "run_a", "--run-hash", "run_bad")
    assert code == 1 and "RESULT: INCOMPLETE" in out
    assert "ERROR:" not in out and "Traceback" not in out


def test_cli_incompatible_runs_produce_a_warning_result(capsys, tmp_path):
    store = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    _write_run(store, "run_a")
    _write_run(store, "run_b", validation_end=date(2024, 9, 30))
    code, out = _cli_run(capsys, "--artifacts-dir", store.base_dir,
                         "--run-hash", "run_a", "--run-hash", "run_b")
    assert "RESULT: WARNING" in out and code == 0
    assert "INCOMPATIBLE_SELECTED_RUNS" in out and "Traceback" not in out


def test_cli_missing_requested_metric_produces_incomplete(capsys, tmp_path):
    store = _cli_store(tmp_path)
    code, out = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a",
                         "--metric", "information_coefficient")
    assert "RESULT: INCOMPLETE" in out and code == 1
    assert "REQUESTED_METRIC_MISSING" in out and "Traceback" not in out


def test_cli_metric_ranking_is_descriptive_only(capsys, tmp_path):
    store = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    _write_run(store, "run_a", backtest_metrics={"sharpe": 2.0})
    _write_run(store, "run_b", backtest_metrics={"sharpe": 1.0})
    out_md = _out(tmp_path, "p.md")
    code, out = _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a",
                         "--run-hash", "run_b", "--metric", "sharpe", "--output-markdown", out_md)
    assert code == 0 and "RESULT: COMPLETE" in out
    text = out_md.read_text(encoding="utf-8").lower()
    for banned in ("winner", "best run", "recommended", "approved", "deploy-ready"):
        assert banned not in text


def test_cli_creates_no_database_or_repo_artifacts(capsys, tmp_path):
    before = _repo_snapshot()
    store = _cli_store(tmp_path)
    _cli_run(capsys, "--artifacts-dir", store.base_dir, "--run-hash", "run_a",
             "--output-json", _out(tmp_path, "p.json"))
    assert _repo_snapshot() == before
    assert not (_BACKEND / "data" / "quantlab.db").exists()
    assert not (_REPO_ROOT / "quantlab.db").exists()


# --------------------------------------------------------------------------- #
# commit 5 — integrated end-to-end over real Phase 9/11 runs + tampered copies
# --------------------------------------------------------------------------- #


def test_e2e_experiment_evidence_pack_over_real_and_tampered_runs(tmp_path, capsys):
    """Full Phase 14 path: synthetic ES raw -> a real Phase 11 batch of 3 Phase 9 runs
    in a tmp ExperimentStore -> the CLI aggregates the already-persisted Phase 13 /
    Phase 12 / Phase 10 evidence into one deterministic pack -> deliberately tampered
    copies (still under tmp_path) drive the WARNING / INCOMPLETE / UNAVAILABLE and
    incompatible-selection paths without erasing valid-run evidence -> JSON / CSV /
    Markdown export to explicit paths outside every store -> every audited store stays
    byte-identical and no database is ever created."""
    import shutil  # test-only: copy real runs into tampered stores under tmp_path

    from app.batch_experiments import expand_grid, run_local_experiment_batch
    from app.datastore.store import RawFuturesStore
    from app.local_pipeline import LocalExperimentConfig
    from app.research_cli.config import ExperimentConfig
    from app.research_cli.synthetic import generate_synthetic_es_raw

    repo_before = _repo_snapshot()
    cli = _load_pack_cli()
    reports = tmp_path / "reports"  # explicit outputs live outside every store

    def run_cli(store, *args):
        code = cli.main(["--artifacts-dir", str(store.base_dir), *[str(a) for a in args]])
        return code, capsys.readouterr().out

    # --- 1. real runs produced by the existing Phase 9 / Phase 11 path ---------- #
    raw_store = RawFuturesStore(tmp_path / "raw", prefer_parquet=False)
    raw_store.write_raw(generate_synthetic_es_raw(ExperimentConfig()))
    clean = ExperimentStore(tmp_path / "clean_exp", prefer_parquet=False)
    configs = expand_grid(LocalExperimentConfig(source="synthetic"), {"random_seed": [0, 1, 2]})
    batch = run_local_experiment_batch(raw_store, configs, experiment_store=clean)
    assert batch.n_ok == 3
    hashes = sorted(batch.train_run_hashes)
    assert len(set(hashes)) == 3  # three distinct real train_run_hashes

    clean_before = _snapshot(clean.base_dir)
    metadata = clean.read_metadata(hashes[0])
    assert "sharpe" in metadata.backtest_metrics  # the explicit metric used below
    # the real runs share the Phase 10 guard key and the Phase 12 grouping key
    for other in hashes[1:]:
        peer = clean.read_metadata(other)
        assert (peer.validation_start, peer.validation_end, peer.label_column,
                peer.dataset_config_hash) == (
            metadata.validation_start, metadata.validation_end,
            metadata.label_column, metadata.dataset_config_hash)

    # --- 2. COMPLETE: all three real runs, explicit metric, all three exports --- #
    selected = [hashes[2], hashes[0], hashes[1]]  # deliberately NOT sorted order
    out_json, out_csv, out_md = (reports / n for n in ("pack.json", "pack.csv", "pack.md"))
    code, out = run_cli(
        clean,
        "--run-hash", selected[0], "--run-hash", selected[1], "--run-hash", selected[2],
        "--audit-level", "standard", "--metric", "sharpe",
        "--output-json", out_json, "--output-csv", out_csv, "--output-markdown", out_md,
    )
    assert code == 0
    assert len([ln for ln in out.splitlines() if ln.startswith("RESULT: ")]) == 1
    assert "RESULT: COMPLETE" in out
    assert ("SUMMARY selected_runs_total=3 runs_complete=3 runs_with_warnings=0 "
            "runs_incomplete=0 runs_unavailable=0 phase14_findings_total=0 "
            "phase13_findings_total=0") in out
    assert [ln for ln in out.splitlines() if ln.startswith("WROTE:")] == [
        "WROTE: JSON", "WROTE: CSV", "WROTE: MARKDOWN"]
    assert _snapshot(clean.base_dir) == clean_before

    pack = json.loads(out_json.read_text(encoding="utf-8"))
    assert pack["selected_run_hashes"] == selected  # explicit order preserved
    assert [r["train_run_hash"] for r in pack["runs"]] == selected
    assert pack["comparison"]["status"] == "available"
    assert len(pack["comparison"]["rows"]) == 3          # real Phase 10 rows
    assert pack["catalog_context_status"] == "collected"
    assert pack["registry_context_status"] == "not_collected"
    assert pack["dataset_lineage_context_status"] == "not_collected"
    assert pack["evidence_summary"]["completeness"] == "complete"  # neutral, no downgrade
    assert not pack["findings"]
    assert all(not r["audit_findings"] for r in pack["runs"])
    ranks, values = set(), set()
    for run in pack["runs"]:
        ctx = run["catalog_context"]
        assert ctx["status"] == "collected" and ctx["group_size"] == 3
        assert ctx["requested_metric"] == "sharpe"
        assert ctx["requested_metric_value"] is not None
        ranks.add(ctx["rank"])
        values.add(ctx["requested_metric_value"])
    assert ranks == {1, 2, 3}  # descriptive Phase 12 ranking over the real group
    assert len(values) >= 1

    # --- 3. exports validated against the real pack ----------------------------- #
    text = json.dumps(pack, allow_nan=False, sort_keys=True)
    for disclaimer in EVIDENCE_DISCLAIMERS:
        assert disclaimer in pack["disclaimers"]
    assert tmp_path.name not in text and ":\\" not in text and ":/" not in text
    for token in ("timestamp", "hostname", "username", "store_root"):
        assert token not in text.lower()

    csv_rows = _csv_rows(out_csv.read_text(encoding="utf-8"))
    assert csv_rows[0] == _CSV_HEADER                    # exact fixed 17 columns
    assert [r[0] for r in csv_rows[1:]] == selected      # one row per run, in order
    for row in csv_rows[1:]:
        assert json.loads(row[_CSV_HEADER.index("metrics_json")])["sharpe"] is not None
        assert row[_CSV_HEADER.index("requested_metric")] == "sharpe"
    csv_text = out_csv.read_text(encoding="utf-8")
    assert "NaN" not in csv_text and "Infinity" not in csv_text
    assert tmp_path.name not in csv_text

    md = out_md.read_text(encoding="utf-8")
    positions = [md.index(s) for s in _MD_SECTIONS]
    assert positions == sorted(positions)                 # exact fixed section order
    assert "**Evidence completeness:** complete" in md
    assert "**Registry context:** not_collected" in md and "not missing evidence" in md
    for disclaimer in EVIDENCE_DISCLAIMERS:
        assert f"- {disclaimer}" in md
    for banned in ("winner", "best run", "recommended", "approved", "deploy-ready"):
        assert banned not in md.lower()
    assert tmp_path.name not in md

    # deterministic repeated bytes from an equivalent invocation
    again = reports / "again"
    run_cli(clean, "--run-hash", selected[0], "--run-hash", selected[1],
            "--run-hash", selected[2], "--metric", "sharpe",
            "--output-json", again / "pack.json", "--output-csv", again / "pack.csv",
            "--output-markdown", again / "pack.md")
    for name in ("pack.json", "pack.csv", "pack.md"):
        assert (again / name).read_bytes() == (reports / name).read_bytes()
    assert _snapshot(clean.base_dir) == clean_before

    # --- 4. single real run: comparison is not applicable, no ranking ----------- #
    single = reports / "single.json"
    code, out = run_cli(clean, "--run-hash", hashes[0], "--output-json", single)
    assert code == 0 and "RESULT: COMPLETE" in out
    assert "COMPARISON_UNAVAILABLE" not in out
    one = json.loads(single.read_text(encoding="utf-8"))
    assert one["comparison"]["status"] == "not_applicable"
    assert one["comparison"]["unavailable_reason"] is None
    ctx = one["runs"][0]["catalog_context"]
    assert ctx["status"] == "collected"                   # catalog context still collected
    assert ctx["requested_metric"] is None and ctx["rank"] is None  # no metric -> no rank
    assert one["registry_context_status"] == "not_collected"
    assert _snapshot(clean.base_dir) == clean_before

    # --- 5. run-hashes file: CLI hashes first, then file order, first wins ------ #
    listing = tmp_path / "selected_runs.txt"
    listing.write_text(
        "# selected runs\n\n"
        f"  {hashes[0]}  \n"          # duplicate of the CLI hash below
        f"{hashes[2]}\n"
        "\t# indented comment\n"
        f"{hashes[2]}\n"              # duplicate within the file
        f"{hashes[1]}\n\n",
        encoding="utf-8",
    )
    mixed_json, mixed_csv, mixed_md = (reports / f"mixed.{e}" for e in ("json", "csv", "md"))
    code, out = run_cli(clean, "--run-hash", hashes[0], "--run-hashes-file", listing,
                        "--output-json", mixed_json, "--output-csv", mixed_csv,
                        "--output-markdown", mixed_md)
    assert code == 0 and "RESULT: COMPLETE" in out
    expected_order = [hashes[0], hashes[2], hashes[1]]     # CLI first, then file order
    mixed = json.loads(mixed_json.read_text(encoding="utf-8"))
    assert mixed["selected_run_hashes"] == expected_order
    assert [r[0] for r in _csv_rows(mixed_csv.read_text(encoding="utf-8"))[1:]] == expected_order
    mixed_text = mixed_md.read_text(encoding="utf-8")
    assert [mixed_text.index(h) for h in expected_order] == sorted(
        mixed_text.index(h) for h in expected_order)

    # --- 6. WARNING: a tampered copy with an orphan artifact ------------------- #
    warn_dir = tmp_path / "warning_exp"
    shutil.copytree(clean.base_dir, warn_dir)
    warned = ExperimentStore(warn_dir, prefer_parquet=False)
    (warned.base_dir / hashes[0] / "stray_notes.json").write_text("{}", encoding="utf-8")
    warn_before = _snapshot(warned.base_dir)

    code, out = run_cli(warned, "--run-hash", hashes[0])
    assert code == 0 and "RESULT: WARNING" in out          # default --fail-on incomplete
    assert "ORPHAN_ARTIFACT" in out
    code, _ = run_cli(warned, "--run-hash", hashes[0], "--fail-on", "warning")
    assert code == 1                                       # threshold escalates it

    # severity filtering changes only the detailed lines
    warn_a, warn_b = reports / "warn_a.json", reports / "warn_b.json"
    plain_code, plain = run_cli(warned, "--run-hash", hashes[0], "--output-json", warn_a)
    filt_code, filtered = run_cli(warned, "--run-hash", hashes[0], "--severity", "critical",
                                  "--output-json", warn_b)
    canonical = lambda t: [ln for ln in t.splitlines() if ln.startswith(("RESULT: ", "SUMMARY "))]
    assert plain_code == filt_code == 0
    assert canonical(plain) == canonical(filtered)
    assert warn_a.read_bytes() == warn_b.read_bytes()      # exports never filtered
    assert "AUDIT_FINDING" in plain and "AUDIT_FINDING" not in filtered
    assert "DISPLAYED phase14_findings=0 phase13_findings=0 severity_threshold=critical" in filtered
    assert _snapshot(warned.base_dir) == warn_before

    # --- 7. INCOMPLETE: a required referenced artifact removed ----------------- #
    bad_dir = tmp_path / "incomplete_exp"
    shutil.copytree(clean.base_dir, bad_dir)
    broken = ExperimentStore(bad_dir, prefer_parquet=False)
    (broken.base_dir / hashes[1] / "predictions.csv").unlink()
    bad_before = _snapshot(broken.base_dir)

    inc_json = reports / "incomplete.json"
    code, out = run_cli(broken, "--run-hash", hashes[0], "--run-hash", hashes[1],
                        "--output-json", inc_json)
    assert code == 1 and "RESULT: INCOMPLETE" in out and "Traceback" not in out
    inc = json.loads(inc_json.read_text(encoding="utf-8"))
    good, hurt = inc["runs"][0], inc["runs"][1]
    assert good["completeness"] == "complete"              # a peer keeps full evidence
    assert good["metrics"] is not None
    assert hurt["completeness"] == "incomplete"
    assert "required_artifact_missing" in hurt["missing_evidence"]
    finding = next(f for f in hurt["audit_findings"]
                   if f["code"] == "MISSING_REFERENCED_ARTIFACT")
    assert finding["finding_id"].startswith("finding_")     # Phase 13 id preserved
    assert finding["severity"] == "error"
    entry = next(a for a in hurt["artifact_inventory"] if a["artifact_name"] == "predictions")
    assert entry["exists"] is False and entry["regular_file"] is False
    assert "MISSING_REFERENCED_ARTIFACT" in entry["audit_finding_codes"]
    assert _snapshot(broken.base_dir) == bad_before

    # --- 8. UNAVAILABLE: only missing hashes, and a mixed selection ------------- #
    code, out = run_cli(clean, "--run-hash", "ghost_one", "--run-hash", "ghost_two")
    assert code == 1 and "RESULT: UNAVAILABLE" in out       # a pack, not a runtime error
    assert out.count("code=RUN_NOT_FOUND") == 2
    assert "Traceback" not in out and "ERROR:" not in out
    assert tmp_path.name not in out and ":\\" not in out

    mixed_missing = reports / "mixed_missing.json"
    code, out = run_cli(clean, "--run-hash", hashes[0], "--run-hash", "ghost",
                        "--output-json", mixed_missing)
    assert code == 1 and "RESULT: INCOMPLETE" in out
    partial = json.loads(mixed_missing.read_text(encoding="utf-8"))
    assert partial["runs"][0]["completeness"] == "complete"
    assert partial["runs"][1]["completeness"] == "unavailable"
    assert partial["runs"][1]["run_directory"] is None
    assert partial["comparison"]["status"] == "unavailable"
    assert partial["comparison"]["unavailable_reason"]
    assert _snapshot(clean.base_dir) == clean_before

    # --- 9. incompatible selection per Phase 10's real guard -------------------- #
    incompat_dir = tmp_path / "incompatible_exp"
    shutil.copytree(clean.base_dir, incompat_dir)
    incompatible = ExperimentStore(incompat_dir, prefer_parquet=False)
    shifted = incompatible.base_dir / hashes[1] / "metadata.json"
    shifted_data = json.loads(shifted.read_text(encoding="utf-8"))
    shifted_data["validation_end"] = "2024-09-30"           # breaks the Phase 10 guard key
    shifted.write_text(json.dumps(shifted_data), encoding="utf-8")
    incompat_before = _snapshot(incompatible.base_dir)

    incompat_json = reports / "incompatible.json"
    code, out = run_cli(incompatible, "--run-hash", hashes[0], "--run-hash", hashes[1],
                        "--output-json", incompat_json)
    assert code == 0 and "RESULT: WARNING" in out           # selection warning only
    assert "INCOMPATIBLE_SELECTED_RUNS" in out and "COMPARISON_UNAVAILABLE" in out
    incompat = json.loads(incompat_json.read_text(encoding="utf-8"))
    assert incompat["comparison"]["status"] == "unavailable"
    assert all(r["load_status"] == "loaded" for r in incompat["runs"])
    assert all(r["metrics"] is not None for r in incompat["runs"])  # evidence intact
    for banned in ("winner", "best", "recommended", "approved"):
        assert banned not in json.dumps(incompat).lower()
    assert _snapshot(incompatible.base_dir) == incompat_before

    # --- 10. explicitly requested metric that no real run persists -------------- #
    metric_json = reports / "metric_missing.json"
    code, out = run_cli(clean, "--run-hash", hashes[0], "--run-hash", hashes[1],
                        "--metric", "calmar_ratio", "--output-json", metric_json)
    assert code == 1 and "RESULT: INCOMPLETE" in out
    assert "REQUESTED_METRIC_MISSING" in out and "Traceback" not in out
    missing_metric = json.loads(metric_json.read_text(encoding="utf-8"))
    assert missing_metric["selected_run_hashes"] == [hashes[0], hashes[1]]  # order kept
    for run in missing_metric["runs"]:
        ctx = run["catalog_context"]
        assert ctx["requested_metric"] == "calmar_ratio"    # recorded, not substituted
        assert ctx["requested_metric_value"] is None and ctx["rank"] is None
        assert "requested_metric_missing" in run["missing_evidence"]
    assert _snapshot(clean.base_dir) == clean_before

    # --- 11. output containment and explicit-write-only behaviour --------------- #
    quiet_before = sorted(p.name for p in reports.iterdir())
    code, out = run_cli(clean, "--run-hash", hashes[0])
    assert code == 0 and "WROTE:" not in out
    assert sorted(p.name for p in reports.iterdir()) == quiet_before  # nothing new

    for bad_target in (clean.base_dir / "leaked.json", clean.base_dir):
        code, out = run_cli(clean, "--run-hash", hashes[0], "--output-json", bad_target)
        assert code == 3 and "Traceback" not in out
        assert not (clean.base_dir / "leaked.json").exists()
    assert _snapshot(clean.base_dir) == clean_before        # store never written

    same = reports / "dup.json"
    code, out = run_cli(clean, "--run-hash", hashes[0], "--output-json", same,
                        "--output-csv", reports / "." / "dup.json")
    assert code == 3 and "duplicates" in out
    assert not same.exists()                               # validation precedes any write

    link = tmp_path / "link_into_store"
    if _try_symlink_dir(link, clean.base_dir):
        code, out = run_cli(clean, "--run-hash", hashes[0], "--output-json", link / "leak.json")
        assert code == 3 and "inside the audited ExperimentStore" in out
        assert _snapshot(clean.base_dir) == clean_before

    assert not (_REPO_ROOT / "reports").exists()            # no implicit reports dir
    assert not (_REPO_ROOT / "data").exists()
    assert not (_REPO_ROOT / "artifacts").exists()

    # --- 12. registry / database and repository-cleanliness proof --------------- #
    assert not (_BACKEND / "data" / "quantlab.db").exists()
    assert not (_REPO_ROOT / "quantlab.db").exists()
    assert list((_BACKEND / "data").iterdir()) == [_BACKEND / "data" / ".gitkeep"]
    assert not list(tmp_path.rglob("*.db")) and not list(tmp_path.rglob("*.sqlite*"))
    assert _repo_snapshot() == repo_before

    # every audited store survived the whole scenario byte-identical
    assert _snapshot(clean.base_dir) == clean_before
    assert _snapshot(warned.base_dir) == warn_before
    assert _snapshot(broken.base_dir) == bad_before
    assert _snapshot(incompatible.base_dir) == incompat_before


def _try_symlink_dir(link, target) -> bool:
    try:
        link.symlink_to(target, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        return False  # unprivileged Windows: the containment check is covered elsewhere


def test_phase14_package_and_cli_source_boundaries():
    """Every Phase 14 shipped file obeys the phase's architectural boundaries."""
    package = _BACKEND / "app" / "experiment_review"
    sources = {p.name: p.read_text(encoding="utf-8")
               for p in (package / "models.py", package / "collect.py",
                         package / "render.py", package / "__init__.py",
                         _PACK_CLI_PATH)}
    assert set(sources) == {"models.py", "collect.py", "render.py", "__init__.py",
                            "build_experiment_evidence_pack.py"}

    forbidden = ("app.experiment_registry", "app.dataset_registry", "app.db", "sqlite3",
                 "get_connection", "quantlab.db", "app.local_pipeline",
                 "app.batch_experiments", "run_local_futures_ml_experiment",
                 "train_model", "build_feature_matrix", "hashlib", "sha256",
                 "import requests", "urllib", "httpx", "socket", "yfinance", "ibkr",
                 "sklearn", "xgboost", "lightgbm", "torch", "tensorflow", "frontend")
    for name, src in sources.items():
        for token in forbidden:
            assert token not in src, f"{name} must not reference {token!r}"
        lowered = src.lower()
        for token in ("quarantine", "deploy-ready", "approve the", "promote"):
            assert token not in lowered, f"{name} must not contain {token!r}"

    # the production package performs zero filesystem writes; only the CLI writes
    for name in ("models.py", "collect.py", "render.py", "__init__.py"):
        for token in (".write_text", ".write_bytes", ".mkdir", ".touch", ".unlink",
                      "rmtree", "shutil", "to_csv", "to_parquet"):
            assert token not in sources[name], f"{name} must not contain {token!r}"
    cli_src = sources["build_experiment_evidence_pack.py"]
    assert cli_src.count(".write_text(") == 1 and cli_src.count(".mkdir(") == 1
    assert "--database-path" not in cli_src and "--include-registry-context" not in cli_src
    assert "--allow-different-windows" not in cli_src

    import re as _re
    for private in ("_ABSOLUTE_PATH", "_FRAME_NAMES", "_window_key", "_compat_key",
                    "_resolve_run", "_metric_value"):
        for name, src in sources.items():
            assert not _re.search(rf"\b{private}\b", src), f"{name} uses {private!r}"
