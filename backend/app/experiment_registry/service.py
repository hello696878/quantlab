"""
Service layer for the Research Experiment Registry.

Owns the business rules the thin store must not: fingerprint computation,
provenance capture, status-transition validation, baseline eligibility, parent
validation, reproducibility assessment, comparison, and export assembly.

Failure policy: registry writes here are ordinary SQLite operations and either
succeed or raise a typed error the router turns into a clean HTTP status.  The
integration helper (:mod:`.integration`) wraps these so a registry failure can
never corrupt or block the main research result it is recording.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.experiment_registry import assessment as assess_mod
from app.experiment_registry import comparison as compare_mod
from app.experiment_registry import fingerprints as fp
from app.experiment_registry import provenance as prov
from app.experiment_registry import store

# Statuses from which a lifecycle transition is allowed.
_ACTIVE_STATUSES = frozenset({"pending", "running"})


class RegistryError(ValueError):
    """Invalid input or a disallowed operation (maps to HTTP 422)."""


class NotFoundError(LookupError):
    """Referenced experiment does not exist (maps to HTTP 404)."""


class ConflictError(RuntimeError):
    """Operation not allowed in the record's current state (maps to HTTP 409)."""


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _resolve_dataset_fingerprint(
    *,
    supplied: Optional[str],
    dataset_name: Optional[str],
    dataset_version: Optional[str],
    dataset_identity: Dict[str, Any],
) -> Optional[str]:
    """Prefer a supplied verified fingerprint; else derive from fixture identity."""
    if supplied:
        return supplied
    if dataset_name and dataset_identity:
        return fp.dataset_fingerprint_from_identity(
            name=dataset_name, version=dataset_version, identity=dataset_identity
        )
    return None


def create_experiment(
    payload: Dict[str, Any],
    *,
    source: str = "api",
    demo_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a record, computing fingerprints and provenance server-side.

    ``payload`` is the dumped :class:`~app.experiment_registry.models.ExperimentCreate`.
    Raises :class:`RegistryError` on rule violations (e.g. a missing parent, a
    ``failed`` status without an error message).
    """
    status = payload.get("status", "completed")

    if status == "failed" and not payload.get("error_message"):
        raise RegistryError("a failed experiment requires an error_message")

    parent_id = payload.get("parent_experiment_id")
    if parent_id is not None and not store.experiment_exists(parent_id):
        raise RegistryError(f"parent_experiment_id {parent_id} does not exist")

    dataset_fingerprint = _resolve_dataset_fingerprint(
        supplied=payload.get("dataset_fingerprint"),
        dataset_name=payload.get("dataset_name"),
        dataset_version=payload.get("dataset_version"),
        dataset_identity=payload.get("dataset_identity") or {},
    )

    parameters = payload.get("parameters") or {}
    metrics = payload.get("metrics") or {}

    config_fp = fp.configuration_fingerprint(
        module=payload["module"],
        experiment_type=payload["experiment_type"],
        parameters=parameters,
        random_seed=payload.get("random_seed"),
        dataset_name=payload.get("dataset_name"),
        dataset_version=payload.get("dataset_version"),
        dataset_fingerprint=dataset_fingerprint,
    )

    result_fp: Optional[str] = None
    if metrics:
        result_fp = fp.result_fingerprint(metrics=metrics, configuration_fingerprint=config_fp)

    provenance = prov.build_provenance(source=source, extra=payload.get("provenance_extra") or {})

    fields: Dict[str, Any] = {
        "name": payload["name"],
        "description": payload.get("description", ""),
        "module": payload["module"],
        "experiment_type": payload["experiment_type"],
        "status": status,
        "reproducibility_status": "unknown",
        "started_at": payload.get("started_at"),
        "completed_at": payload.get("completed_at"),
        "duration_ms": payload.get("duration_ms"),
        "git_commit": prov.get_git_commit(),
        "app_version": prov.get_app_version(),
        "dataset_name": payload.get("dataset_name"),
        "dataset_version": payload.get("dataset_version"),
        "dataset_fingerprint": dataset_fingerprint,
        "configuration_fingerprint": config_fp,
        "result_fingerprint": result_fp,
        "random_seed": payload.get("random_seed"),
        "parameters": parameters,
        "metrics": metrics,
        "tags": payload.get("tags") or [],
        "provenance": provenance,
        "notes": payload.get("notes", ""),
        "parent_experiment_id": parent_id,
        "is_baseline": False,
        "error_message": payload.get("error_message"),
        "demo_key": demo_key,
    }
    return store.insert_experiment(fields)


def get_experiment(experiment_id: int) -> Dict[str, Any]:
    record = store.get_experiment(experiment_id)
    if record is None:
        raise NotFoundError(f"experiment {experiment_id} not found")
    return record


def list_experiments(**kwargs: Any) -> Dict[str, Any]:
    return store.list_experiments(**kwargs)


def registry_summary() -> Dict[str, Any]:
    counts = store.summary_counts()
    facets = store.distinct_values()
    return {**counts, **facets}


def update_experiment(experiment_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Update mutable descriptive fields (name/description/notes/tags)."""
    _ = get_experiment(experiment_id)  # 404 if missing
    columns: Dict[str, Any] = {}
    if payload.get("name") is not None:
        columns["name"] = payload["name"]
    if payload.get("description") is not None:
        columns["description"] = payload["description"]
    if payload.get("notes") is not None:
        columns["notes"] = payload["notes"]
    if payload.get("tags") is not None:
        import json

        columns["tags_json"] = json.dumps(payload["tags"])
    updated = store.update_columns(experiment_id, columns)
    assert updated is not None
    return updated


def complete_experiment(experiment_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    record = get_experiment(experiment_id)
    if record["status"] not in _ACTIVE_STATUSES:
        raise ConflictError(
            f"cannot complete an experiment in status '{record['status']}'"
        )
    import json

    metrics = payload.get("metrics") or record.get("metrics") or {}
    result_metadata = payload.get("result_metadata") or {}
    result_fp = fp.result_fingerprint(
        metrics=metrics,
        configuration_fingerprint=record["configuration_fingerprint"],
        result_metadata=result_metadata,
    )
    completed_at = payload.get("completed_at") or _utc_now()
    duration_ms = payload.get("duration_ms")
    if duration_ms is None:
        duration_ms = _duration_from(record.get("started_at"), completed_at)

    columns = {
        "status": "completed",
        "completed_at": completed_at,
        "duration_ms": duration_ms,
        "metrics_json": json.dumps(metrics),
        "result_fingerprint": result_fp,
        "error_message": None,
    }
    updated = store.update_columns(experiment_id, columns)
    assert updated is not None
    return updated


def fail_experiment(experiment_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    record = get_experiment(experiment_id)
    if record["status"] not in _ACTIVE_STATUSES:
        raise ConflictError(f"cannot fail an experiment in status '{record['status']}'")
    completed_at = payload.get("completed_at") or _utc_now()
    columns = {
        "status": "failed",
        "completed_at": completed_at,
        "duration_ms": _duration_from(record.get("started_at"), completed_at),
        "error_message": payload["error_message"],
        "is_baseline": 0,
    }
    updated = store.update_columns(experiment_id, columns)
    assert updated is not None
    return updated


def invalidate_experiment(experiment_id: int) -> Dict[str, Any]:
    record = get_experiment(experiment_id)
    if record["status"] == "invalidated":
        raise ConflictError("experiment is already invalidated")
    columns = {"status": "invalidated", "is_baseline": 0}
    updated = store.update_columns(experiment_id, columns)
    assert updated is not None
    return updated


def mark_baseline(experiment_id: int) -> Dict[str, Any]:
    record = get_experiment(experiment_id)
    if record["status"] != "completed":
        raise ConflictError("only a completed experiment can be marked as the baseline")
    updated = store.mark_baseline(experiment_id)
    assert updated is not None
    return updated


def delete_experiment(experiment_id: int) -> bool:
    if not store.delete_experiment(experiment_id):
        raise NotFoundError(f"experiment {experiment_id} not found")
    return True


def find_reference(candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Choose a reference: explicit parent, else baseline in the same scope."""
    parent_id = candidate.get("parent_experiment_id")
    if parent_id is not None:
        return store.get_experiment(parent_id)
    return store.find_baseline_in_scope(
        module=candidate["module"],
        experiment_type=candidate["experiment_type"],
        dataset_fingerprint=candidate.get("dataset_fingerprint"),
        dataset_name=candidate.get("dataset_name"),
        exclude_id=candidate.get("id"),
    )


def assess_experiment(experiment_id: int) -> Dict[str, Any]:
    candidate = get_experiment(experiment_id)
    reference = find_reference(candidate)
    result = assess_mod.assess_reproducibility(candidate, reference)
    # Persist the derived status so list/detail badges stay in sync.
    if result["status"] != candidate.get("reproducibility_status"):
        store.update_columns(experiment_id, {"reproducibility_status": result["status"]})
    return result


def compare(a_id: int, b_id: int) -> Dict[str, Any]:
    if a_id == b_id:
        raise RegistryError("compare requires two different experiments")
    a = get_experiment(a_id)
    b = get_experiment(b_id)
    return compare_mod.compare_experiments(a, b)


def export(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    filters = filters or {}
    records = store.list_full_for_export(filters)
    # Only echo back non-null filters, so the export header is clean.
    applied = {k: v for k, v in filters.items() if v is not None}
    from app.experiment_registry import SCHEMA_VERSION

    return {
        "schema_version": SCHEMA_VERSION,
        "exported_at": _utc_now(),
        "filters": applied,
        "count": len(records),
        "experiments": records,
    }


def _duration_from(started_at: Optional[str], completed_at: str) -> Optional[int]:
    if not started_at:
        return None
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    delta_ms = int((end - start).total_seconds() * 1000)
    return max(delta_ms, 0)


__all__ = [
    "RegistryError",
    "NotFoundError",
    "ConflictError",
    "create_experiment",
    "get_experiment",
    "list_experiments",
    "registry_summary",
    "update_experiment",
    "complete_experiment",
    "fail_experiment",
    "invalidate_experiment",
    "mark_baseline",
    "delete_experiment",
    "assess_experiment",
    "compare",
    "export",
    "find_reference",
]
