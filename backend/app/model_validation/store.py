"""
SQLite persistence for the Model Validation Lab (parameterised SQL only).
Business rules live in :mod:`.service`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.db import get_connection

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
SORTABLE = frozenset({"created_at", "updated_at", "name", "method", "status"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _run_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "name": row["name"],
        "description": row["description"],
        "method": row["method"],
        "status": row["status"],
        "configuration": json.loads(row["configuration_json"]),
        "samples": json.loads(row["samples_json"]),
        "configuration_fingerprint": row["configuration_fingerprint"],
        "result_fingerprint": row["result_fingerprint"],
        "sample_count": row["sample_count"],
        "split_count": row["split_count"],
        "valid_split_count": row["valid_split_count"],
        "invalid_split_count": row["invalid_split_count"],
        "leakage_clean": None if row["leakage_clean"] is None else bool(row["leakage_clean"]),
        "aggregate_metrics": json.loads(row["aggregate_metrics_json"]),
        "leakage_summary": json.loads(row["leakage_summary_json"]),
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "duration_ms": row["duration_ms"],
        "experiment_id": row["experiment_id"],
        "dataset_version_id": row["dataset_version_id"],
        "random_seed": row["random_seed"],
        "app_version": row["app_version"],
        "git_commit": row["git_commit"],
        "is_baseline": bool(row["is_baseline"]),
        "notes": row["notes"],
        "error_message": row["error_message"],
    }


def _split_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "validation_run_id": row["validation_run_id"],
        "split_index": row["split_index"],
        "split_label": row["split_label"],
        "split_fingerprint": row["split_fingerprint"],
        "status": row["status"],
        "train_ids": json.loads(row["train_ids_json"]),
        "test_ids": json.loads(row["test_ids_json"]),
        "purged_ids": json.loads(row["purged_ids_json"]),
        "embargoed_ids": json.loads(row["embargoed_ids_json"]),
        "diagnostics": json.loads(row["diagnostics_json"]),
        "metrics": json.loads(row["metrics_json"]),
    }


def insert_run(fields: Dict[str, Any]) -> Dict[str, Any]:
    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO validation_runs (
                created_at, updated_at, name, description, method, status,
                configuration_json, samples_json, configuration_fingerprint,
                sample_count, experiment_id, dataset_version_id, random_seed,
                app_version, git_commit, notes, demo_key
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                now, now,
                fields["name"],
                fields.get("description", ""),
                fields["method"],
                "pending",
                json.dumps(fields.get("configuration", {})),
                json.dumps(fields.get("samples", [])),
                fields["configuration_fingerprint"],
                fields.get("sample_count", 0),
                fields.get("experiment_id"),
                fields.get("dataset_version_id"),
                fields.get("random_seed"),
                fields.get("app_version"),
                fields.get("git_commit"),
                fields.get("notes", ""),
                fields.get("demo_key"),
            ),
        )
        conn.commit()
        new_id = int(cursor.lastrowid)  # type: ignore[arg-type]
    run = get_run(new_id)
    assert run is not None
    return run


def get_run(run_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM validation_runs WHERE id = ?", (run_id,)).fetchone()
    return _run_row(row) if row else None


def run_demo_key_id(demo_key: str) -> Optional[int]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM validation_runs WHERE demo_key = ?", (demo_key,)
        ).fetchone()
    return int(row["id"]) if row else None


def update_run(run_id: int, columns: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    allowed = {
        "status", "result_fingerprint", "split_count", "valid_split_count",
        "invalid_split_count", "leakage_clean", "aggregate_metrics_json",
        "leakage_summary_json", "started_at", "completed_at", "duration_ms",
        "experiment_id", "is_baseline", "error_message", "notes",
    }
    updates = {k: v for k, v in columns.items() if k in allowed}
    if not updates:
        return get_run(run_id)
    set_clause = ", ".join(f"{c} = ?" for c in updates)
    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE validation_runs SET {set_clause}, updated_at = ? WHERE id = ?",
            [*updates.values(), _utc_now(), run_id],
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
    return get_run(run_id)


def _where(filters: Dict[str, Any]) -> Tuple[str, List[Any]]:
    clauses: List[str] = []
    params: List[Any] = []
    for column, key in (
        ("method", "method"), ("status", "status"),
        ("dataset_version_id", "dataset_version_id"),
        ("experiment_id", "experiment_id"),
        ("configuration_fingerprint", "configuration_fingerprint"),
    ):
        if filters.get(key) is not None:
            clauses.append(f"{column} = ?")
            params.append(filters[key])
    if filters.get("baseline") is not None:
        clauses.append("is_baseline = ?")
        params.append(1 if filters["baseline"] else 0)
    if filters.get("leakage_clean") is not None:
        clauses.append("leakage_clean = ?")
        params.append(1 if filters["leakage_clean"] else 0)
    if filters.get("created_from"):
        clauses.append("created_at >= ?")
        params.append(filters["created_from"])
    if filters.get("created_to"):
        clauses.append("created_at <= ?")
        params.append(filters["created_to"])
    if filters.get("query"):
        clauses.append("(name LIKE ? OR description LIKE ?)")
        like = f"%{filters['query']}%"
        params.extend([like, like])
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def list_runs(
    *, filters: Optional[Dict[str, Any]] = None, sort_by: str = "created_at",
    sort_dir: str = "desc", page: int = 1, page_size: int = DEFAULT_PAGE_SIZE,
) -> Dict[str, Any]:
    filters = filters or {}
    if sort_by not in SORTABLE:
        sort_by = "created_at"
    sort_dir = "asc" if str(sort_dir).lower() == "asc" else "desc"
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), MAX_PAGE_SIZE))
    where, params = _where(filters)
    with get_connection() as conn:
        total = int(conn.execute(
            f"SELECT COUNT(*) AS c FROM validation_runs{where}", params
        ).fetchone()["c"])
        rows = conn.execute(
            f"SELECT * FROM validation_runs{where} "
            f"ORDER BY {sort_by} {sort_dir.upper()}, id {sort_dir.upper()} LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()
    total_pages = (total + page_size - 1) // page_size if total else 0
    return {
        "items": [_run_row(r) for r in rows],
        "total": total, "page": page, "page_size": page_size, "total_pages": total_pages,
    }


def replace_splits(run_id: int, splits: List[Dict[str, Any]]) -> None:
    """Idempotent re-execute support: replace this run's split records."""
    with get_connection() as conn:
        conn.execute("DELETE FROM validation_splits WHERE validation_run_id = ?", (run_id,))
        for s in splits:
            conn.execute(
                """
                INSERT INTO validation_splits (
                    validation_run_id, split_index, split_label, split_fingerprint,
                    status, train_ids_json, test_ids_json, purged_ids_json,
                    embargoed_ids_json, diagnostics_json, metrics_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    run_id, s["split_index"], s["split_label"], s["split_fingerprint"],
                    s["status"], json.dumps(s["train_ids"]), json.dumps(s["test_ids"]),
                    json.dumps(s["purged_ids"]), json.dumps(s["embargoed_ids"]),
                    json.dumps(s["diagnostics"]), json.dumps(s["metrics"]),
                ),
            )
        conn.commit()


def list_splits(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM validation_splits WHERE validation_run_id = ? ORDER BY split_index",
            (run_id,),
        ).fetchall()
    return [_split_row(r) for r in rows]


def find_baseline_in_scope(
    *, method: str, dataset_version_id: Optional[int], exclude_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    params: List[Any] = [method]
    dataset_clause = "dataset_version_id IS NULL" if dataset_version_id is None else "dataset_version_id = ?"
    if dataset_version_id is not None:
        params.append(dataset_version_id)
    exclude = ""
    if exclude_id is not None:
        exclude = " AND id != ?"
        params.append(exclude_id)
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT * FROM validation_runs WHERE is_baseline = 1 AND method = ? "
            f"AND {dataset_clause}{exclude} ORDER BY updated_at DESC LIMIT 1",
            params,
        ).fetchone()
    return _run_row(row) if row else None


def mark_baseline(run_id: int, method: str, dataset_version_id: Optional[int]) -> None:
    """Transactionally unmark same-scope baselines, then mark run_id."""
    now = _utc_now()
    with get_connection() as conn:
        if dataset_version_id is None:
            conn.execute(
                "UPDATE validation_runs SET is_baseline = 0, updated_at = ? "
                "WHERE is_baseline = 1 AND method = ? AND dataset_version_id IS NULL AND id != ?",
                (now, method, run_id),
            )
        else:
            conn.execute(
                "UPDATE validation_runs SET is_baseline = 0, updated_at = ? "
                "WHERE is_baseline = 1 AND method = ? AND dataset_version_id = ? AND id != ?",
                (now, method, dataset_version_id, run_id),
            )
        conn.execute(
            "UPDATE validation_runs SET is_baseline = 1, updated_at = ? WHERE id = ?",
            (now, run_id),
        )
        conn.commit()


def lab_summary() -> Dict[str, Any]:
    with get_connection() as conn:
        runs = int(conn.execute("SELECT COUNT(*) AS c FROM validation_runs").fetchone()["c"])
        completed = int(conn.execute(
            "SELECT COUNT(*) AS c FROM validation_runs WHERE status = 'completed'"
        ).fetchone()["c"])
        clean = int(conn.execute(
            "SELECT COUNT(*) AS c FROM validation_runs WHERE leakage_clean = 1"
        ).fetchone()["c"])
        invalid_splits = int(conn.execute(
            "SELECT COALESCE(SUM(invalid_split_count), 0) AS c FROM validation_runs"
        ).fetchone()["c"])
        baselines = int(conn.execute(
            "SELECT COUNT(*) AS c FROM validation_runs WHERE is_baseline = 1"
        ).fetchone()["c"])
        linked = int(conn.execute(
            "SELECT COUNT(DISTINCT dataset_version_id) AS c FROM validation_runs "
            "WHERE dataset_version_id IS NOT NULL"
        ).fetchone()["c"])
        method_rows = conn.execute(
            "SELECT method, COUNT(*) AS c FROM validation_runs GROUP BY method"
        ).fetchall()
    return {
        "runs": runs, "completed": completed, "leakage_clean": clean,
        "invalid_splits": invalid_splits, "baselines": baselines,
        "linked_datasets": linked,
        "methods": {r["method"]: int(r["c"]) for r in method_rows},
    }


__all__ = [
    "DEFAULT_PAGE_SIZE", "MAX_PAGE_SIZE", "SORTABLE",
    "insert_run", "get_run", "run_demo_key_id", "update_run", "list_runs",
    "replace_splits", "list_splits", "find_baseline_in_scope", "mark_baseline",
    "lab_summary",
]
