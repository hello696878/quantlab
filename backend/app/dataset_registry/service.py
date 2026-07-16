"""
Service layer for the Dataset Lineage registry.

Owns the rules the thin store must not: fingerprint computation, provenance
derivation, version immutability, invalidation semantics, lineage validation
(self-edge / cycle / duplicate), quality-check execution and rollup, version
comparison, experiment-link validation, and export assembly.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.dataset_registry import EXPORT_SCHEMA_VERSION
from app.dataset_registry import drift as drift_mod
from app.dataset_registry import fingerprints as fp
from app.dataset_registry import lineage as lineage_mod
from app.dataset_registry import quality as quality_mod
from app.dataset_registry import store
from app.dataset_registry.locators import LocatorError, validate_locator
from app.experiment_registry import store as experiment_store
from app.experiment_registry.provenance import get_git_commit


class DatasetError(ValueError):
    """Invalid input or disallowed operation (HTTP 422)."""


class NotFoundError(LookupError):
    """Referenced record does not exist (HTTP 404)."""


class ConflictError(RuntimeError):
    """Operation conflicts with existing state (HTTP 409)."""


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------


def create_dataset(payload: Dict[str, Any], *, demo_key: Optional[str] = None) -> Dict[str, Any]:
    if store.get_dataset_by_name(payload["name"]) is not None:
        raise ConflictError(f"a dataset named {payload['name']!r} already exists")
    fields = dict(payload)
    fields["demo_key"] = demo_key
    fields["provenance_status"] = "unknown"  # derived per-version later
    return store.insert_dataset(fields)


def get_dataset(dataset_id: int) -> Dict[str, Any]:
    record = store.get_dataset(dataset_id)
    if record is None:
        raise NotFoundError(f"dataset {dataset_id} not found")
    return _enrich([record])[0]


def list_datasets(**kwargs: Any) -> Dict[str, Any]:
    result = store.list_datasets(**kwargs)
    result["items"] = _enrich(result["items"])
    return result


def _enrich(datasets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    info = store.dataset_enrichment([d["id"] for d in datasets])
    for d in datasets:
        d.update(info.get(d["id"], {}))
    return datasets


def update_dataset(dataset_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    if store.get_dataset(dataset_id) is None:
        raise NotFoundError(f"dataset {dataset_id} not found")
    columns: Dict[str, Any] = {}
    for key in ("description", "notes", "license_name", "license_url"):
        if payload.get(key) is not None:
            columns[key] = payload[key]
    if payload.get("tags") is not None:
        columns["tags_json"] = json.dumps(payload["tags"])
    if payload.get("is_active") is not None:
        columns["is_active"] = 1 if payload["is_active"] else 0
    updated = store.update_dataset_columns(dataset_id, columns)
    assert updated is not None
    return _enrich([updated])[0]


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


def _derive_provenance_status(version: Dict[str, Any]) -> str:
    """Documented, conservative derivation from the recorded metadata."""
    if version.get("invalidated_at"):
        return "invalidated"
    has_identity = bool(version.get("content_fingerprint") or version.get("source_fingerprint"))
    has_source = bool((version.get("provenance") or {}).get("source"))
    has_schema = bool((version.get("schema_snapshot") or {}).get("fields"))
    signals = sum([has_identity, has_source, has_schema])
    if signals == 3:
        return "complete"
    if signals >= 1:
        return "partial"
    return "unknown"


def create_version(
    dataset_id: int,
    payload: Dict[str, Any],
    *,
    demo_key: Optional[str] = None,
) -> Dict[str, Any]:
    dataset = store.get_dataset(dataset_id)
    if dataset is None:
        raise NotFoundError(f"dataset {dataset_id} not found")

    for existing in store.list_versions(dataset_id):
        if existing["version_label"] == payload["version_label"]:
            raise ConflictError(
                f"version {payload['version_label']!r} already exists for this dataset"
            )

    try:
        locator_type, locator = validate_locator(payload["storage_locator"])
    except LocatorError as exc:
        raise DatasetError(str(exc))

    snapshot = payload.get("schema_snapshot") or {}
    schema_fields = snapshot.get("fields") or []
    schema_fp: Optional[str] = None
    if schema_fields:
        schema_fp = fp.schema_fingerprint(
            schema_fields,
            ordering_significant=bool(snapshot.get("ordering_significant")),
            schema_version=dataset.get("schema_version"),
        )

    manifest_fp = fp.manifest_fingerprint(
        dataset_name=dataset["name"],
        version_label=payload["version_label"],
        row_count=payload.get("row_count"),
        column_count=payload.get("column_count"),
        start_time=payload.get("start_time"),
        end_time=payload.get("end_time"),
        fmt=payload.get("format", "csv"),
        schema_fp=schema_fp,
        source_fingerprint=payload.get("source_fingerprint"),
        deterministic=bool(payload.get("deterministic")),
        provenance_inputs=payload.get("provenance") or {},
    )

    fields = dict(payload)
    fields.update(
        {
            "dataset_id": dataset_id,
            "storage_locator_type": locator_type,
            "storage_locator": locator,
            "schema_fingerprint": schema_fp,
            "manifest_fingerprint": manifest_fp,
            "demo_key": demo_key,
        }
    )
    version = store.insert_version(fields)

    # The newest version becomes current; dataset provenance follows it.
    store.update_dataset_columns(
        dataset_id,
        {
            "current_version_id": version["id"],
            "provenance_status": _derive_provenance_status(version),
        },
    )
    return version


def get_version(version_id: int) -> Dict[str, Any]:
    record = store.get_version(version_id)
    if record is None:
        raise NotFoundError(f"dataset version {version_id} not found")
    return _hydrate_version(record)


def _hydrate_version(version: Dict[str, Any]) -> Dict[str, Any]:
    dataset = store.get_dataset(version["dataset_id"])
    version["dataset_name"] = dataset["name"] if dataset else None
    version["is_current"] = bool(dataset and dataset.get("current_version_id") == version["id"])
    return version


def list_versions(dataset_id: int) -> List[Dict[str, Any]]:
    if store.get_dataset(dataset_id) is None:
        raise NotFoundError(f"dataset {dataset_id} not found")
    return [_hydrate_version(v) for v in store.list_versions(dataset_id)]


def invalidate_version(version_id: int, reason: str) -> Dict[str, Any]:
    version = store.get_version(version_id)
    if version is None:
        raise NotFoundError(f"dataset version {version_id} not found")
    if version.get("invalidated_at"):
        raise ConflictError("dataset version is already invalidated")
    updated = store.update_version_columns(
        version_id,
        {"invalidated_at": _utc_now(), "invalidation_reason": reason},
    )
    assert updated is not None
    # Lineage and experiment links are deliberately preserved.
    dataset = store.get_dataset(version["dataset_id"])
    if dataset and dataset.get("current_version_id") == version_id:
        store.update_dataset_columns(
            version["dataset_id"], {"provenance_status": "invalidated"}
        )
    return _hydrate_version(updated)


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------


def add_lineage(payload: Dict[str, Any]) -> Dict[str, Any]:
    parent_id = payload["parent_version_id"]
    child_id = payload["child_version_id"]
    if parent_id == child_id:
        raise DatasetError("a version cannot be its own lineage parent")
    if store.get_version(parent_id) is None:
        raise NotFoundError(f"parent version {parent_id} not found")
    if store.get_version(child_id) is None:
        raise NotFoundError(f"child version {child_id} not found")

    existing = store.find_identical_edge(payload)
    if existing is not None:
        return existing  # idempotent duplicate

    try:
        if lineage_mod.would_create_cycle(parent_id, child_id):
            raise DatasetError(
                "adding this edge would create a lineage cycle "
                f"({parent_id} → {child_id})"
            )
    except lineage_mod.LineageError as exc:
        raise DatasetError(str(exc))

    fields = dict(payload)
    fields["git_commit"] = get_git_commit()
    return store.insert_edge(fields)


def lineage_graph(
    version_id: int,
    *,
    max_depth: int = lineage_mod.DEFAULT_MAX_DEPTH,
    node_limit: int = lineage_mod.DEFAULT_NODE_LIMIT,
) -> Dict[str, Any]:
    if store.get_version(version_id) is None:
        raise NotFoundError(f"dataset version {version_id} not found")
    hood = lineage_mod.bounded_neighborhood(
        version_id, max_depth=max_depth, node_limit=node_limit
    )
    nodes: List[Dict[str, Any]] = []
    for vid, (depth, direction) in sorted(hood["node_ids"].items()):
        version = store.get_version(vid)
        if version is None:
            continue
        dataset = store.get_dataset(version["dataset_id"])
        nodes.append(
            {
                "version_id": vid,
                "dataset_id": version["dataset_id"],
                "dataset_name": dataset["name"] if dataset else f"dataset {version['dataset_id']}",
                "version_label": version["version_label"],
                "quality_status": version["quality_status"],
                "invalidated": bool(version.get("invalidated_at")),
                "is_demo": bool(dataset and dataset.get("is_demo")),
                "depth": depth,
                "direction": direction,
            }
        )
    return {
        "root_version_id": version_id,
        "nodes": nodes,
        "edges": hood["edges"],
        "truncated": hood["truncated"],
        "max_depth": min(max(1, int(max_depth)), lineage_mod.MAX_MAX_DEPTH),
        "node_limit": min(max(1, int(node_limit)), lineage_mod.MAX_NODE_LIMIT),
    }


# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------


def run_quality_checks(version_id: int, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    version = store.get_version(version_id)
    if version is None:
        raise NotFoundError(f"dataset version {version_id} not found")
    try:
        results = quality_mod.run_checks(
            version, payload.get("checks") or [], payload.get("expectations") or {}
        )
    except ValueError as exc:
        raise DatasetError(str(exc))
    stored = []
    for r in results:
        r["dataset_version_id"] = version_id
        stored.append(store.insert_quality_result(r))
    store.update_version_columns(
        version_id,
        {
            "quality_status": quality_mod.rollup_status(results),
            "validation_status": "checked",
        },
    )
    return stored


def list_quality(version_id: int) -> List[Dict[str, Any]]:
    if store.get_version(version_id) is None:
        raise NotFoundError(f"dataset version {version_id} not found")
    return store.list_quality_results(version_id)


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def _numeric_entry(field: str, a: Any, b: Any) -> Dict[str, Any]:
    entry: Dict[str, Any] = {"kind": "metric", "field": field, "a": a, "b": b, "note": ""}
    if (
        isinstance(a, (int, float))
        and isinstance(b, (int, float))
        and not isinstance(a, bool)
        and not isinstance(b, bool)
        and math.isfinite(float(a))
        and math.isfinite(float(b))
    ):
        entry["note"] = f"Δ {b - a}"
        if a != 0:
            entry["note"] += f" ({(b - a) / abs(a) * 100.0:+.2f}%)"
    return entry


def compare_versions(a_id: int, b_id: int) -> Dict[str, Any]:
    if a_id == b_id:
        raise DatasetError("compare requires two different dataset versions")
    a = store.get_version(a_id)
    b = store.get_version(b_id)
    if a is None:
        raise NotFoundError(f"dataset version {a_id} not found")
    if b is None:
        raise NotFoundError(f"dataset version {b_id} not found")

    identity = []
    ds_a = store.get_dataset(a["dataset_id"])
    ds_b = store.get_dataset(b["dataset_id"])
    for field, va, vb in (
        ("dataset", ds_a["name"] if ds_a else None, ds_b["name"] if ds_b else None),
        ("version_label", a["version_label"], b["version_label"]),
        ("format", a["format"], b["format"]),
        ("frequency", (ds_a or {}).get("frequency"), (ds_b or {}).get("frequency")),
        ("timezone", (ds_a or {}).get("timezone"), (ds_b or {}).get("timezone")),
        ("deterministic", a["deterministic"], b["deterministic"]),
        ("start_time", a["start_time"], b["start_time"]),
        ("end_time", a["end_time"], b["end_time"]),
    ):
        identity.append(
            {
                "kind": "same" if va == vb else "changed",
                "field": field,
                "a": va,
                "b": vb,
                "note": "",
            }
        )

    schema_result = drift_mod.compare_schemas(a.get("schema_snapshot"), b.get("schema_snapshot"))
    schema_entries = schema_result["entries"] + drift_mod.compare_context(a, b)

    metrics = [
        _numeric_entry("row_count", a.get("row_count"), b.get("row_count")),
        _numeric_entry("column_count", a.get("column_count"), b.get("column_count")),
        _numeric_entry("file_size_bytes", a.get("file_size_bytes"), b.get("file_size_bytes")),
    ]

    fingerprints = {
        "schema": bool(a.get("schema_fingerprint"))
        and a.get("schema_fingerprint") == b.get("schema_fingerprint"),
        "manifest": a.get("manifest_fingerprint") == b.get("manifest_fingerprint"),
        "content": bool(a.get("content_fingerprint"))
        and a.get("content_fingerprint") == b.get("content_fingerprint"),
        "source": bool(a.get("source_fingerprint"))
        and a.get("source_fingerprint") == b.get("source_fingerprint"),
    }

    quality = {
        "a": [f"{r['check_name']}: {r['status']}" for r in store.list_quality_results(a_id)[:20]],
        "b": [f"{r['check_name']}: {r['status']}" for r in store.list_quality_results(b_id)[:20]],
    }

    prov_changes = []
    prov_a = _flatten(a.get("provenance") or {})
    prov_b = _flatten(b.get("provenance") or {})
    for key in sorted(set(prov_a) | set(prov_b)):
        va, vb = prov_a.get(key), prov_b.get(key)
        if va != vb:
            prov_changes.append(
                {"kind": "provenance_changed", "field": key, "a": va, "b": vb, "note": ""}
            )

    return {
        "a_id": a_id,
        "b_id": b_id,
        "identity": identity,
        "schema_drift": schema_entries,
        "drift_class": schema_result["drift_class"],
        "metrics": metrics,
        "fingerprints": fingerprints,
        "quality": quality,
        "provenance_changes": prov_changes,
    }


def _flatten(obj: Any, prefix: str = "") -> Dict[str, Any]:
    flat: Dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                flat.update(_flatten(v, key))
            else:
                flat[key] = v
    else:
        flat[prefix or "value"] = obj
    return flat


# ---------------------------------------------------------------------------
# Experiment links
# ---------------------------------------------------------------------------


def create_link(payload: Dict[str, Any]) -> Dict[str, Any]:
    experiment = experiment_store.get_experiment(payload["experiment_id"])
    if experiment is None:
        raise NotFoundError(f"experiment {payload['experiment_id']} not found")
    version = store.get_version(payload["dataset_version_id"])
    if version is None:
        raise NotFoundError(f"dataset version {payload['dataset_version_id']} not found")
    existing = store.find_link(
        payload["experiment_id"], payload["dataset_version_id"], payload["role"]
    )
    if existing is not None:
        return _hydrate_link(existing)  # idempotent
    return _hydrate_link(store.insert_link(payload))


def _hydrate_link(link: Dict[str, Any]) -> Dict[str, Any]:
    experiment = experiment_store.get_experiment(link["experiment_id"])
    version = store.get_version(link["dataset_version_id"])
    link["experiment_name"] = experiment["name"] if experiment else None
    if version:
        dataset = store.get_dataset(version["dataset_id"])
        link["dataset_name"] = dataset["name"] if dataset else None
        link["version_label"] = version["version_label"]
        # Fingerprint compatibility: the experiment's recorded dataset
        # fingerprint (if any) should match one of the version's fingerprints.
        exp_fp = (experiment or {}).get("dataset_fingerprint")
        if exp_fp:
            link["fingerprint_match"] = exp_fp in (
                version.get("content_fingerprint"),
                version.get("source_fingerprint"),
                version.get("manifest_fingerprint"),
            )
        else:
            link["fingerprint_match"] = None
    else:
        link["dataset_name"] = None
        link["version_label"] = None
        link["fingerprint_match"] = None
    return link


def links_for_version(version_id: int) -> List[Dict[str, Any]]:
    if store.get_version(version_id) is None:
        raise NotFoundError(f"dataset version {version_id} not found")
    return [_hydrate_link(l) for l in store.links_for_version(version_id)]


def links_for_experiment(experiment_id: int) -> List[Dict[str, Any]]:
    if experiment_store.get_experiment(experiment_id) is None:
        raise NotFoundError(f"experiment {experiment_id} not found")
    return [_hydrate_link(l) for l in store.links_for_experiment(experiment_id)]


# ---------------------------------------------------------------------------
# Summary + export
# ---------------------------------------------------------------------------


def registry_summary() -> Dict[str, Any]:
    return store.registry_summary()


def export(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    filters = filters or {}
    listing = store.list_datasets(filters=filters, page=1, page_size=store.MAX_PAGE_SIZE)
    datasets = _enrich(listing["items"])
    dataset_ids = {d["id"] for d in datasets}
    versions: List[Dict[str, Any]] = []
    for d in datasets:
        versions.extend(_hydrate_version(v) for v in store.list_versions(d["id"]))
    version_ids = {v["id"] for v in versions}
    edges = [
        e for e in store.all_edges()
        if e["parent_version_id"] in version_ids or e["child_version_id"] in version_ids
    ]
    quality: List[Dict[str, Any]] = []
    for v in versions:
        quality.extend(store.list_quality_results(v["id"]))
    links = [
        _hydrate_link(l) for l in store.all_links() if l["dataset_version_id"] in version_ids
    ]
    applied = {k: v for k, v in filters.items() if v is not None}
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "exported_at": _utc_now(),
        "filters": applied,
        "datasets": datasets,
        "versions": versions,
        "lineage": edges,
        "quality_results": quality,
        "experiment_links": links,
    }


__all__ = [
    "DatasetError",
    "NotFoundError",
    "ConflictError",
    "create_dataset",
    "get_dataset",
    "list_datasets",
    "update_dataset",
    "create_version",
    "get_version",
    "list_versions",
    "invalidate_version",
    "add_lineage",
    "lineage_graph",
    "run_quality_checks",
    "list_quality",
    "compare_versions",
    "create_link",
    "links_for_version",
    "links_for_experiment",
    "registry_summary",
    "export",
]
