"""
Service layer: run lifecycle, execution, leakage rollup, registry links,
baseline scope, comparison, and export.

Baseline scope (documented): at most one active baseline per
``(method, dataset_version_id)`` — dataset-less runs share the NULL-dataset
scope per method.  Only completed runs whose splits are all valid and whose
leakage audit passed may become baselines.

Experiment-linking idempotency: executing a run creates at most one Experiment
Registry record — once ``experiment_id`` is set on the run, re-execution
reuses it and never creates a duplicate.
"""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.dataset_registry import store as dataset_store
from app.experiment_registry import integration as experiment_integration
from app.experiment_registry import store as experiment_store
from app.experiment_registry.provenance import get_app_version, get_git_commit
from app.model_validation import EXPORT_SCHEMA_VERSION
from app.model_validation import engine, fingerprints, metrics as metrics_mod, store
from app.model_validation.events import EventError, normalize_samples, strip_datetimes


class ValidationError(ValueError):
    """Invalid input/config (HTTP 422)."""


class NotFoundError(LookupError):
    """Unknown id (HTTP 404)."""


class ConflictError(RuntimeError):
    """State conflict (HTTP 409)."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Create / read
# ---------------------------------------------------------------------------


def create_run(
    payload: Dict[str, Any],
    *,
    demo_key: Optional[str] = None,
    validate_configuration: bool = True,
) -> Dict[str, Any]:
    method = payload["method"]
    try:
        samples = normalize_samples(payload["samples"])
    except EventError as exc:
        raise ValidationError(str(exc))

    if payload.get("dataset_version_id") is not None:
        if dataset_store.get_version(payload["dataset_version_id"]) is None:
            raise NotFoundError(f"dataset version {payload['dataset_version_id']} not found")
    if payload.get("experiment_id") is not None:
        if experiment_store.get_experiment(payload["experiment_id"]) is None:
            raise NotFoundError(f"experiment {payload['experiment_id']} not found")

    config = dict(payload.get("configuration") or {})
    if validate_configuration:
        try:
            engine.validate_config(method, samples, config)
        except engine.SplitConfigError as exc:
            raise ValidationError(str(exc))
    config_fp = fingerprints.configuration_fingerprint(
        method=method,
        samples=samples,
        configuration=config,
        random_seed=payload.get("random_seed"),
    )
    fields = {
        "name": payload["name"],
        "description": payload.get("description", ""),
        "method": method,
        "configuration": config,
        "samples": [strip_datetimes(s) for s in samples],
        "configuration_fingerprint": config_fp,
        "sample_count": len(samples),
        "experiment_id": payload.get("experiment_id"),
        "dataset_version_id": payload.get("dataset_version_id"),
        "random_seed": payload.get("random_seed"),
        "app_version": get_app_version(),
        "git_commit": get_git_commit(),
        "notes": payload.get("notes", ""),
        "demo_key": demo_key,
    }
    return store.insert_run(fields)


def get_run(run_id: int) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"validation run {run_id} not found")
    return _hydrate(run)


def _key_metric_preview(aggregate: Dict[str, Any]) -> Optional[str]:
    for name in ("accuracy", "roc_auc", "rmse", "return_mean"):
        agg = aggregate.get(name)
        if isinstance(agg, dict) and agg.get("mean") is not None:
            return f"{name} {agg['mean']}"
    return None


def _hydrate(run: Dict[str, Any]) -> Dict[str, Any]:
    run["key_metric_preview"] = _key_metric_preview(run.get("aggregate_metrics", {}))
    run["dataset_name"] = None
    run["dataset_version_label"] = None
    run["dataset_invalidated"] = None
    run["dataset_manifest_fingerprint"] = None
    run["dataset_provenance_status"] = None
    run["dataset_quality_status"] = None
    run["experiment_name"] = None
    if run.get("dataset_version_id"):
        version = dataset_store.get_version(run["dataset_version_id"])
        if version:
            dataset = dataset_store.get_dataset(version["dataset_id"])
            run["dataset_name"] = dataset["name"] if dataset else None
            run["dataset_version_label"] = version["version_label"]
            run["dataset_invalidated"] = bool(version.get("invalidated_at"))
            run["dataset_manifest_fingerprint"] = version["manifest_fingerprint"]
            run["dataset_provenance_status"] = dataset["provenance_status"] if dataset else None
            run["dataset_quality_status"] = version["quality_status"]
    if run.get("experiment_id"):
        experiment = experiment_store.get_experiment(run["experiment_id"])
        run["experiment_name"] = experiment["name"] if experiment else None
    return run


def list_runs(**kwargs: Any) -> Dict[str, Any]:
    result = store.list_runs(**kwargs)
    result["items"] = [_hydrate(r) for r in result["items"]]
    return result


def lab_summary() -> Dict[str, Any]:
    return store.lab_summary()


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def execute_run(run_id: int, *, create_experiment: bool = False) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"validation run {run_id} not found")
    if run["status"] == "invalidated":
        raise ConflictError("an invalidated run cannot be executed")

    started = _utc_now()
    t0 = time.monotonic()
    try:
        samples = normalize_samples(run["samples"])
        splitter = engine.SPLITTERS.get(run["method"])
        if splitter is None:
            raise ValidationError(f"unknown method {run['method']!r}")
        config = dict(run["configuration"])
        if run.get("random_seed") is not None and "random_seed" not in config:
            config["random_seed"] = run["random_seed"]
        raw_splits = splitter(samples, config)
    except (EventError, engine.SplitConfigError, ValidationError) as exc:
        store.update_run(
            run_id,
            {
                "status": "failed",
                "started_at": started,
                "completed_at": _utc_now(),
                "duration_ms": int((time.monotonic() - t0) * 1000),
                "error_message": str(exc),
                "leakage_clean": None,
            },
        )
        return get_run(run_id)

    split_records: List[Dict[str, Any]] = []
    metric_blocks: List[Dict[str, Any]] = []
    split_fps: List[str] = []
    valid_count = 0
    for index, split in enumerate(raw_splits):
        diagnostics = engine.audit_split(samples, split, run["method"])
        block = metrics_mod.split_metrics(samples, split["test_pos"])
        train_ids = [samples[p]["sample_id"] for p in split["train_pos"]]
        test_ids = [samples[p]["sample_id"] for p in split["test_pos"]]
        purged_ids = [samples[p]["sample_id"] for p in split["purged_pos"]]
        embargoed_ids = [samples[p]["sample_id"] for p in split["embargoed_pos"]]
        fp = fingerprints.split_fingerprint(
            configuration_fp=run["configuration_fingerprint"],
            split_label=split["split_label"],
            train_ids=train_ids,
            test_ids=test_ids,
            purged_ids=purged_ids,
            embargoed_ids=embargoed_ids,
        )
        diagnostics["purge_reasons"] = split.get("purge_reasons", {})
        diagnostics["embargo_windows"] = split.get("embargo_windows", [])
        diagnostics["method_note"] = split.get("method_note", "")
        status = "valid" if diagnostics["valid"] else "invalid"
        if status == "valid":
            valid_count += 1
        split_fps.append(fp)
        metric_blocks.append(block)
        split_records.append(
            {
                "split_index": index,
                "split_label": split["split_label"],
                "split_fingerprint": fp,
                "status": status,
                "train_ids": train_ids,
                "test_ids": test_ids,
                "purged_ids": purged_ids,
                "embargoed_ids": embargoed_ids,
                "diagnostics": diagnostics,
                "metrics": block,
            }
        )

    aggregate = metrics_mod.aggregate_metrics(metric_blocks)
    invalid_count = len(split_records) - valid_count
    leakage_clean = invalid_count == 0
    leakage_summary = {
        "total_splits": len(split_records),
        "valid_splits": valid_count,
        "invalid_splits": invalid_count,
        "total_purged": sum(len(s["purged_ids"]) for s in split_records),
        "total_embargoed": sum(len(s["embargoed_ids"]) for s in split_records),
        "total_remaining_overlap": sum(
            s["diagnostics"]["remaining_overlap_count"] for s in split_records
        ),
        "leakage_clean": leakage_clean,
    }

    dataset_identity = None
    if run.get("dataset_version_id"):
        version = dataset_store.get_version(run["dataset_version_id"])
        dataset_identity = version["manifest_fingerprint"] if version else None

    result_fp = fingerprints.result_fingerprint(
        configuration_fp=run["configuration_fingerprint"],
        split_fps=split_fps,
        aggregate_metrics=aggregate,
        leakage_summary=leakage_summary,
        dataset_identity=dataset_identity,
    )

    import json as _json

    store.replace_splits(run_id, split_records)
    completed = _utc_now()
    store.update_run(
        run_id,
        {
            "status": "completed",
            "started_at": started,
            "completed_at": completed,
            "duration_ms": int((time.monotonic() - t0) * 1000),
            "split_count": len(split_records),
            "valid_split_count": valid_count,
            "invalid_split_count": invalid_count,
            "leakage_clean": 1 if leakage_clean else 0,
            "aggregate_metrics_json": _json.dumps(aggregate),
            "leakage_summary_json": _json.dumps(leakage_summary),
            "result_fingerprint": result_fp,
            "error_message": None,
        },
    )

    # Idempotent experiment creation: only when requested and not already linked.
    if create_experiment and not run.get("experiment_id"):
        record = experiment_integration.record_experiment(
            name=f"Validation: {run['name']}",
            module="model_validation",
            experiment_type=run["method"],
            status="completed",
            parameters={
                "method": run["method"],
                "configuration": run["configuration"],
                "sample_count": run["sample_count"],
            },
            metrics={
                "valid_splits": valid_count,
                "invalid_splits": invalid_count,
                "total_purged": leakage_summary["total_purged"],
                "total_embargoed": leakage_summary["total_embargoed"],
                "leakage_clean": 1 if leakage_clean else 0,
            },
            tags=["model-validation", run["method"]],
            random_seed=run.get("random_seed"),
            dataset_name=None,
            source="model_validation",
        )
        if record is not None:
            store.update_run(run_id, {"experiment_id": record["id"]})

    return get_run(run_id)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def invalidate_run(run_id: int, reason: str) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"validation run {run_id} not found")
    if run["status"] == "invalidated":
        raise ConflictError("run is already invalidated")
    store.update_run(
        run_id,
        {"status": "invalidated", "error_message": reason, "is_baseline": 0},
    )
    return get_run(run_id)


def mark_baseline(run_id: int) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"validation run {run_id} not found")
    if run["status"] != "completed":
        raise ConflictError("only a completed run can be marked as baseline")
    if run["invalid_split_count"] != 0 or run.get("leakage_clean") is not True:
        raise ConflictError(
            "only a leakage-clean run (all splits valid) can be marked as baseline"
        )
    store.mark_baseline(run_id, run["method"], run.get("dataset_version_id"))
    return get_run(run_id)


def list_splits(run_id: int) -> List[Dict[str, Any]]:
    if store.get_run(run_id) is None:
        raise NotFoundError(f"validation run {run_id} not found")
    return store.list_splits(run_id)


def leakage_audit(run_id: int) -> Dict[str, Any]:
    run = get_run(run_id)
    splits = store.list_splits(run_id)
    return {
        "run_id": run_id,
        "leakage_summary": run["leakage_summary"],
        "splits": [
            {
                "split_label": s["split_label"],
                "status": s["status"],
                "remaining_overlap_count": s["diagnostics"].get("remaining_overlap_count"),
                "purged_count": s["diagnostics"].get("purged_count"),
                "embargoed_count": s["diagnostics"].get("embargoed_count"),
                "chronological_violations": s["diagnostics"].get("chronological_violations"),
                "duplicate_assignments": s["diagnostics"].get("duplicate_assignments"),
            }
            for s in splits
        ],
    }


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def _entry(field: str, a: Any, b: Any) -> Dict[str, Any]:
    if a is None and b is not None:
        return {"kind": "only_in_b", "field": field, "a": a, "b": b, "note": ""}
    if b is None and a is not None:
        return {"kind": "only_in_a", "field": field, "a": a, "b": b, "note": ""}
    if a is None and b is None:
        return {"kind": "unavailable", "field": field, "a": a, "b": b, "note": ""}
    kind = "same" if a == b else "changed"
    note = ""
    if (
        kind == "changed"
        and isinstance(a, (int, float)) and isinstance(b, (int, float))
        and not isinstance(a, bool) and not isinstance(b, bool)
        and math.isfinite(float(a)) and math.isfinite(float(b))
    ):
        note = f"Δ {round(b - a, 6)}"
        if a != 0:
            note += f" ({(b - a) / abs(a) * 100.0:+.2f}%)"
    return {"kind": kind, "field": field, "a": a, "b": b, "note": note}


def compare_runs(a_id: int, b_id: int) -> Dict[str, Any]:
    if a_id == b_id:
        raise ValidationError("compare requires two different validation runs")
    a, b = get_run(a_id), get_run(b_id)

    identity = [
        _entry(f, a.get(f), b.get(f))
        for f in ("method", "status", "sample_count", "dataset_name",
                  "dataset_version_label", "experiment_name", "is_baseline",
                  "random_seed")
    ]
    config_keys = sorted(set(a["configuration"]) | set(b["configuration"]))
    configuration = [
        _entry(k, a["configuration"].get(k), b["configuration"].get(k)) for k in config_keys
    ]
    leakage = [
        _entry(f, a["leakage_summary"].get(f), b["leakage_summary"].get(f))
        for f in ("total_splits", "valid_splits", "invalid_splits",
                  "total_purged", "total_embargoed", "total_remaining_overlap",
                  "leakage_clean")
    ]
    metric_names = sorted(set(a["aggregate_metrics"]) | set(b["aggregate_metrics"]))
    metric_entries = []
    for name in metric_names:
        ma = (a["aggregate_metrics"].get(name) or {}).get("mean")
        mb = (b["aggregate_metrics"].get(name) or {}).get("mean")
        if ma is None and mb is None:
            continue
        metric_entries.append(_entry(name, ma, mb))

    return {
        "a_id": a_id,
        "b_id": b_id,
        "groups": {
            "identity": identity,
            "configuration": configuration,
            "leakage": leakage,
            "aggregate_metrics_mean": metric_entries,
        },
        "fingerprint_match": {
            "configuration": a["configuration_fingerprint"] == b["configuration_fingerprint"],
            "result": bool(a.get("result_fingerprint"))
            and a.get("result_fingerprint") == b.get("result_fingerprint"),
        },
    }


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def export(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    filters = filters or {}
    listing = store.list_runs(filters=filters, page=1, page_size=store.MAX_PAGE_SIZE)
    runs = [_hydrate(r) for r in listing["items"]]
    splits: List[Dict[str, Any]] = []
    for r in runs:
        r.pop("samples", None)  # membership lives on the split records
        splits.extend(store.list_splits(r["id"]))
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "exported_at": _utc_now(),
        "filters": {k: v for k, v in filters.items() if v is not None},
        "runs": runs,
        "splits": splits,
    }


__all__ = [
    "ValidationError", "NotFoundError", "ConflictError",
    "create_run", "get_run", "list_runs", "lab_summary", "execute_run",
    "invalidate_run", "mark_baseline", "list_splits", "leakage_audit",
    "compare_runs", "export",
]
