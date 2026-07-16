"""
SQLite persistence for the Research Experiment Registry.

Thin data-access layer over :func:`app.db.get_connection` — all SQL is
parameterised (no string interpolation of values), structured fields
(parameters, metrics, tags, provenance) are stored as JSON text, and every
mutation refreshes ``updated_at``.  Business rules (status transitions, baseline
eligibility, fingerprints, provenance) live in :mod:`.service`; this module only
reads and writes rows.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.db import get_connection

# Columns a client may sort by (whitelist — never interpolate raw input).
SORTABLE_COLUMNS = frozenset(
    {
        "created_at",
        "updated_at",
        "name",
        "module",
        "experiment_type",
        "status",
        "duration_ms",
    }
)

# Columns that generic status/lifecycle updates may touch.
_UPDATABLE_COLUMNS = frozenset(
    {
        "name",
        "description",
        "notes",
        "status",
        "reproducibility_status",
        "started_at",
        "completed_at",
        "duration_ms",
        "result_fingerprint",
        "metrics_json",
        "tags_json",
        "error_message",
        "is_baseline",
        "parent_experiment_id",
    }
)

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


# ---------------------------------------------------------------------------
# Row mappers
# ---------------------------------------------------------------------------


def _row_to_summary(row) -> Dict[str, Any]:
    """Lightweight row for list responses (omits large parameters/provenance)."""
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "name": row["name"],
        "module": row["module"],
        "experiment_type": row["experiment_type"],
        "status": row["status"],
        "reproducibility_status": row["reproducibility_status"],
        "duration_ms": row["duration_ms"],
        "dataset_name": row["dataset_name"],
        "dataset_version": row["dataset_version"],
        "dataset_fingerprint": row["dataset_fingerprint"],
        "random_seed": row["random_seed"],
        "configuration_fingerprint": row["configuration_fingerprint"],
        "result_fingerprint": row["result_fingerprint"],
        "is_baseline": bool(row["is_baseline"]),
        "git_commit": row["git_commit"],
        "app_version": row["app_version"],
        "tags": json.loads(row["tags_json"]),
        "metrics": json.loads(row["metrics_json"]),
        "parent_experiment_id": row["parent_experiment_id"],
    }


def _row_to_full(row) -> Dict[str, Any]:
    """Full record including parameters, provenance, notes, and lifecycle stamps."""
    full = _row_to_summary(row)
    full.update(
        {
            "description": row["description"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "parameters": json.loads(row["parameters_json"]),
            "provenance": json.loads(row["provenance_json"]),
            "notes": row["notes"],
            "error_message": row["error_message"],
        }
    )
    return full


# ---------------------------------------------------------------------------
# Create / read
# ---------------------------------------------------------------------------


def insert_experiment(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Insert a fully-formed record.  Sets created_at/updated_at.  Returns full."""
    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO experiment_registry (
                created_at, updated_at, name, description, module,
                experiment_type, status, reproducibility_status,
                started_at, completed_at, duration_ms,
                git_commit, app_version,
                dataset_name, dataset_version, dataset_fingerprint,
                configuration_fingerprint, result_fingerprint, random_seed,
                parameters_json, metrics_json, tags_json, provenance_json,
                notes, parent_experiment_id, is_baseline, error_message, demo_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now,
                now,
                fields["name"],
                fields.get("description", ""),
                fields["module"],
                fields["experiment_type"],
                fields["status"],
                fields.get("reproducibility_status", "unknown"),
                fields.get("started_at"),
                fields.get("completed_at"),
                fields.get("duration_ms"),
                fields.get("git_commit"),
                fields.get("app_version"),
                fields.get("dataset_name"),
                fields.get("dataset_version"),
                fields.get("dataset_fingerprint"),
                fields["configuration_fingerprint"],
                fields.get("result_fingerprint"),
                fields.get("random_seed"),
                json.dumps(fields.get("parameters", {})),
                json.dumps(fields.get("metrics", {})),
                json.dumps(fields.get("tags", [])),
                json.dumps(fields.get("provenance", {})),
                fields.get("notes", ""),
                fields.get("parent_experiment_id"),
                1 if fields.get("is_baseline") else 0,
                fields.get("error_message"),
                fields.get("demo_key"),
            ),
        )
        conn.commit()
        new_id = int(cursor.lastrowid)  # type: ignore[arg-type]
    result = get_experiment(new_id)
    assert result is not None  # just inserted
    return result


def get_experiment(experiment_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM experiment_registry WHERE id = ?", (experiment_id,)
        ).fetchone()
    return _row_to_full(row) if row is not None else None


def experiment_exists(experiment_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM experiment_registry WHERE id = ?", (experiment_id,)
        ).fetchone()
    return row is not None


def demo_key_exists(demo_key: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM experiment_registry WHERE demo_key = ?", (demo_key,)
        ).fetchone()
    return row is not None


def get_id_by_demo_key(demo_key: str) -> Optional[int]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM experiment_registry WHERE demo_key = ?", (demo_key,)
        ).fetchone()
    return int(row["id"]) if row is not None else None


# ---------------------------------------------------------------------------
# Filtering / listing
# ---------------------------------------------------------------------------


def _build_where(filters: Dict[str, Any]) -> Tuple[str, List[Any]]:
    """Build a parameterised WHERE clause from a validated filters dict."""
    clauses: List[str] = []
    params: List[Any] = []

    def eq(column: str, key: str) -> None:
        value = filters.get(key)
        if value is not None:
            clauses.append(f"{column} = ?")
            params.append(value)

    eq("module", "module")
    eq("experiment_type", "experiment_type")
    eq("status", "status")
    eq("reproducibility_status", "reproducibility_status")
    eq("configuration_fingerprint", "configuration_fingerprint")
    eq("dataset_fingerprint", "dataset_fingerprint")

    if filters.get("baseline") is not None:
        clauses.append("is_baseline = ?")
        params.append(1 if filters["baseline"] else 0)

    if filters.get("created_from") is not None:
        clauses.append("created_at >= ?")
        params.append(filters["created_from"])
    if filters.get("created_to") is not None:
        clauses.append("created_at <= ?")
        params.append(filters["created_to"])

    tag = filters.get("tag")
    if tag:
        # tags_json is a JSON array; match the quoted element form.  The pattern
        # is bound as a parameter, so this is not an injection vector.
        clauses.append("tags_json LIKE ?")
        params.append(f'%"{tag}"%')

    query = filters.get("query")
    if query:
        clauses.append("(name LIKE ? OR description LIKE ?)")
        like = f"%{query}%"
        params.extend([like, like])

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def list_experiments(
    *,
    filters: Optional[Dict[str, Any]] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Dict[str, Any]:
    """Paginated, filtered, sorted list.  Returns items + pagination metadata."""
    filters = filters or {}
    if sort_by not in SORTABLE_COLUMNS:
        sort_by = "created_at"
    sort_dir = "asc" if str(sort_dir).lower() == "asc" else "desc"
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), MAX_PAGE_SIZE))

    where, params = _build_where(filters)

    with get_connection() as conn:
        total = int(
            conn.execute(
                f"SELECT COUNT(*) AS c FROM experiment_registry{where}", params
            ).fetchone()["c"]
        )
        offset = (page - 1) * page_size
        # Stable ordering: primary sort column, then id as a deterministic
        # tiebreak in the same direction.
        order = f"ORDER BY {sort_by} {sort_dir.upper()}, id {sort_dir.upper()}"
        rows = conn.execute(
            f"SELECT * FROM experiment_registry{where} {order} LIMIT ? OFFSET ?",
            [*params, page_size, offset],
        ).fetchall()

    items = [_row_to_summary(r) for r in rows]
    total_pages = (total + page_size - 1) // page_size if total else 0
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def list_full_for_export(filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """All matching records as full dicts (no pagination), newest first."""
    filters = filters or {}
    where, params = _build_where(filters)
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM experiment_registry{where} ORDER BY created_at DESC, id DESC",
            params,
        ).fetchall()
    return [_row_to_full(r) for r in rows]


def summary_counts() -> Dict[str, Any]:
    """Aggregate counts for the dashboard summary cards."""
    with get_connection() as conn:
        total = int(conn.execute("SELECT COUNT(*) AS c FROM experiment_registry").fetchone()["c"])
        status_rows = conn.execute(
            "SELECT status, COUNT(*) AS c FROM experiment_registry GROUP BY status"
        ).fetchall()
        repro_rows = conn.execute(
            "SELECT reproducibility_status AS s, COUNT(*) AS c "
            "FROM experiment_registry GROUP BY reproducibility_status"
        ).fetchall()
        baselines = int(
            conn.execute(
                "SELECT COUNT(*) AS c FROM experiment_registry WHERE is_baseline = 1"
            ).fetchone()["c"]
        )
        modules = int(
            conn.execute(
                "SELECT COUNT(DISTINCT module) AS c FROM experiment_registry"
            ).fetchone()["c"]
        )
    return {
        "total": total,
        "by_status": {r["status"]: int(r["c"]) for r in status_rows},
        "by_reproducibility": {r["s"]: int(r["c"]) for r in repro_rows},
        "baselines": baselines,
        "modules_represented": modules,
    }


def distinct_values() -> Dict[str, List[str]]:
    """Distinct modules / experiment_types / tags for filter dropdowns."""
    with get_connection() as conn:
        modules = [
            r["module"]
            for r in conn.execute(
                "SELECT DISTINCT module FROM experiment_registry ORDER BY module"
            ).fetchall()
        ]
        types = [
            r["experiment_type"]
            for r in conn.execute(
                "SELECT DISTINCT experiment_type FROM experiment_registry ORDER BY experiment_type"
            ).fetchall()
        ]
        tag_rows = conn.execute("SELECT tags_json FROM experiment_registry").fetchall()
    tags: set[str] = set()
    for r in tag_rows:
        try:
            for t in json.loads(r["tags_json"]):
                if isinstance(t, str):
                    tags.add(t)
        except (ValueError, TypeError):
            continue
    return {"modules": modules, "experiment_types": types, "tags": sorted(tags)}


# ---------------------------------------------------------------------------
# Updates
# ---------------------------------------------------------------------------


def update_columns(experiment_id: int, columns: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update a whitelist of columns and refresh updated_at.  Returns full/None."""
    updates = {k: v for k, v in columns.items() if k in _UPDATABLE_COLUMNS}
    if not updates:
        return get_experiment(experiment_id)
    set_clause = ", ".join(f"{col} = ?" for col in updates)
    values = list(updates.values())
    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE experiment_registry SET {set_clause}, updated_at = ? WHERE id = ?",
            [*values, _utc_now(), experiment_id],
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
    return get_experiment(experiment_id)


def mark_baseline(experiment_id: int) -> Optional[Dict[str, Any]]:
    """Transactionally make *experiment_id* the sole baseline in its scope.

    Scope = (module, experiment_type, dataset identity) where dataset identity
    is ``COALESCE(dataset_fingerprint, dataset_name, '')``.  Any other baseline
    in the same scope is unmarked in the same transaction; baselines in other
    scopes are untouched.  Returns the updated record, or ``None`` if not found.
    """
    now = _utc_now()
    with get_connection() as conn:
        target = conn.execute(
            "SELECT module, experiment_type, dataset_fingerprint, dataset_name "
            "FROM experiment_registry WHERE id = ?",
            (experiment_id,),
        ).fetchone()
        if target is None:
            return None
        identity = target["dataset_fingerprint"] or target["dataset_name"] or ""
        conn.execute(
            """
            UPDATE experiment_registry
               SET is_baseline = 0, updated_at = ?
             WHERE is_baseline = 1
               AND id != ?
               AND module = ?
               AND experiment_type = ?
               AND COALESCE(dataset_fingerprint, dataset_name, '') = ?
            """,
            (now, experiment_id, target["module"], target["experiment_type"], identity),
        )
        conn.execute(
            "UPDATE experiment_registry SET is_baseline = 1, updated_at = ? WHERE id = ?",
            (now, experiment_id),
        )
        conn.commit()
    return get_experiment(experiment_id)


def delete_experiment(experiment_id: int) -> bool:
    """Hard-delete a single record by id.  Returns True if a row was removed."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM experiment_registry WHERE id = ?", (experiment_id,)
        )
        conn.commit()
    return cursor.rowcount > 0


def find_baseline_in_scope(
    *,
    module: str,
    experiment_type: str,
    dataset_fingerprint: Optional[str],
    dataset_name: Optional[str],
    exclude_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Return the active baseline in a (module, type, dataset identity) scope."""
    identity = dataset_fingerprint or dataset_name or ""
    params: List[Any] = [module, experiment_type, identity]
    exclude = ""
    if exclude_id is not None:
        exclude = " AND id != ?"
        params.append(exclude_id)
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT * FROM experiment_registry
             WHERE is_baseline = 1
               AND module = ?
               AND experiment_type = ?
               AND COALESCE(dataset_fingerprint, dataset_name, '') = ?{exclude}
             ORDER BY updated_at DESC, id DESC
             LIMIT 1
            """,
            params,
        ).fetchone()
    return _row_to_full(row) if row is not None else None


__all__ = [
    "SORTABLE_COLUMNS",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "insert_experiment",
    "get_experiment",
    "experiment_exists",
    "demo_key_exists",
    "get_id_by_demo_key",
    "list_experiments",
    "list_full_for_export",
    "summary_counts",
    "distinct_values",
    "update_columns",
    "mark_baseline",
    "delete_experiment",
    "find_baseline_in_scope",
]
