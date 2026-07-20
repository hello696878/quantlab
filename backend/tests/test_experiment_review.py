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
