"""
SQLite persistence for the Dataset Lineage registry.

Thin, fully parameterised data-access layer over :func:`app.db.get_connection`.
Business rules (immutability, cycle rejection, link validation, provenance
derivation) live in :mod:`.service` / :mod:`.lineage`; this module only reads
and writes rows.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.db import get_connection

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100

SORTABLE_COLUMNS = frozenset(
    {"created_at", "updated_at", "name", "domain", "source_type", "format"}
)


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


# ---------------------------------------------------------------------------
# Row mappers
# ---------------------------------------------------------------------------


def _dataset_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "name": row["name"],
        "description": row["description"],
        "domain": row["domain"],
        "dataset_type": row["dataset_type"],
        "source_type": row["source_type"],
        "provider": row["provider"],
        "source_reference": row["source_reference"],
        "license_name": row["license_name"],
        "license_url": row["license_url"],
        "symbol_scope": row["symbol_scope"],
        "asset_class": row["asset_class"],
        "frequency": row["frequency"],
        "timezone": row["timezone"],
        "format": row["format"],
        "schema_version": row["schema_version"],
        "current_version_id": row["current_version_id"],
        "tags": json.loads(row["tags_json"]),
        "metadata": json.loads(row["metadata_json"]),
        "notes": row["notes"],
        "is_demo": bool(row["is_demo"]),
        "is_active": bool(row["is_active"]),
        "provenance_status": row["provenance_status"],
    }


def _version_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "dataset_id": row["dataset_id"],
        "version_label": row["version_label"],
        "created_at": row["created_at"],
        "effective_from": row["effective_from"],
        "effective_to": row["effective_to"],
        "row_count": row["row_count"],
        "column_count": row["column_count"],
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "content_fingerprint": row["content_fingerprint"],
        "manifest_fingerprint": row["manifest_fingerprint"],
        "schema_fingerprint": row["schema_fingerprint"],
        "source_fingerprint": row["source_fingerprint"],
        "file_size_bytes": row["file_size_bytes"],
        "format": row["format"],
        "compression": row["compression"],
        "storage_locator_type": row["storage_locator_type"],
        "storage_locator": row["storage_locator"],
        "ingestion_method": row["ingestion_method"],
        "deterministic": bool(row["deterministic"]),
        "quality_status": row["quality_status"],
        "validation_status": row["validation_status"],
        "schema_snapshot": json.loads(row["schema_snapshot_json"]),
        "statistics_summary": json.loads(row["statistics_json"]),
        "provenance": json.loads(row["provenance_json"]),
        "invalidated_at": row["invalidated_at"],
        "invalidation_reason": row["invalidation_reason"],
    }


def _edge_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "parent_version_id": row["parent_version_id"],
        "child_version_id": row["child_version_id"],
        "relationship_type": row["relationship_type"],
        "transformation_name": row["transformation_name"],
        "transformation_version": row["transformation_version"],
        "parameters": json.loads(row["parameters_json"]),
        "code_reference": row["code_reference"],
        "git_commit": row["git_commit"],
        "created_at": row["created_at"],
        "notes": row["notes"],
    }


def _quality_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "dataset_version_id": row["dataset_version_id"],
        "check_name": row["check_name"],
        "check_category": row["check_category"],
        "status": row["status"],
        "severity": row["severity"],
        "observed_value": row["observed_value"],
        "expected_value": row["expected_value"],
        "message": row["message"],
        "checked_at": row["checked_at"],
        "checker_version": row["checker_version"],
        "details": json.loads(row["details_json"]),
    }


def _link_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "experiment_id": row["experiment_id"],
        "dataset_version_id": row["dataset_version_id"],
        "role": row["role"],
        "created_at": row["created_at"],
        "notes": row["notes"],
    }


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------


def insert_dataset(fields: Dict[str, Any]) -> Dict[str, Any]:
    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO datasets (
                created_at, updated_at, name, description, domain, dataset_type,
                source_type, provider, source_reference, license_name,
                license_url, symbol_scope, asset_class, frequency, timezone,
                format, schema_version, current_version_id, tags_json,
                metadata_json, notes, is_demo, is_active, provenance_status,
                demo_key
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                now,
                now,
                fields["name"],
                fields.get("description", ""),
                fields["domain"],
                fields["dataset_type"],
                fields.get("source_type", "unknown"),
                fields.get("provider"),
                fields.get("source_reference"),
                fields.get("license_name"),
                fields.get("license_url"),
                fields.get("symbol_scope"),
                fields.get("asset_class"),
                fields.get("frequency"),
                fields.get("timezone"),
                fields.get("format", "csv"),
                fields.get("schema_version"),
                None,
                json.dumps(fields.get("tags", [])),
                json.dumps(fields.get("metadata", {})),
                fields.get("notes", ""),
                1 if fields.get("is_demo") else 0,
                1,
                fields.get("provenance_status", "unknown"),
                fields.get("demo_key"),
            ),
        )
        conn.commit()
        new_id = int(cursor.lastrowid)  # type: ignore[arg-type]
    record = get_dataset(new_id)
    assert record is not None
    return record


def get_dataset(dataset_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
    return _dataset_row(row) if row else None


def get_dataset_by_name(name: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM datasets WHERE name = ?", (name,)).fetchone()
    return _dataset_row(row) if row else None


def dataset_demo_key_id(demo_key: str) -> Optional[int]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM datasets WHERE demo_key = ?", (demo_key,)
        ).fetchone()
    return int(row["id"]) if row else None


def update_dataset_columns(dataset_id: int, columns: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    allowed = {
        "description",
        "notes",
        "tags_json",
        "license_name",
        "license_url",
        "is_active",
        "current_version_id",
        "provenance_status",
        "schema_version",
    }
    updates = {k: v for k, v in columns.items() if k in allowed}
    if not updates:
        return get_dataset(dataset_id)
    set_clause = ", ".join(f"{c} = ?" for c in updates)
    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE datasets SET {set_clause}, updated_at = ? WHERE id = ?",
            [*updates.values(), _utc_now(), dataset_id],
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
    return get_dataset(dataset_id)


def _dataset_where(filters: Dict[str, Any]) -> Tuple[str, List[Any]]:
    clauses: List[str] = []
    params: List[Any] = []

    def eq(column: str, key: str) -> None:
        if filters.get(key) is not None:
            clauses.append(f"d.{column} = ?")
            params.append(filters[key])

    eq("source_type", "source_type")
    eq("domain", "domain")
    eq("asset_class", "asset_class")
    eq("format", "format")
    eq("frequency", "frequency")
    eq("provenance_status", "provenance_status")
    if filters.get("demo") is not None:
        clauses.append("d.is_demo = ?")
        params.append(1 if filters["demo"] else 0)
    if filters.get("active") is not None:
        clauses.append("d.is_active = ?")
        params.append(1 if filters["active"] else 0)
    tag = filters.get("tag")
    if tag:
        clauses.append("d.tags_json LIKE ?")
        params.append(f'%"{tag}"%')
    query = filters.get("query")
    if query:
        clauses.append("(d.name LIKE ? OR d.description LIKE ?)")
        like = f"%{query}%"
        params.extend([like, like])
    quality = filters.get("quality_status")
    if quality:
        clauses.append(
            "EXISTS (SELECT 1 FROM dataset_versions v WHERE v.dataset_id = d.id "
            "AND v.quality_status = ?)"
        )
        params.append(quality)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def list_datasets(
    *,
    filters: Optional[Dict[str, Any]] = None,
    sort_by: str = "updated_at",
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Dict[str, Any]:
    filters = filters or {}
    if sort_by not in SORTABLE_COLUMNS:
        sort_by = "updated_at"
    sort_dir = "asc" if str(sort_dir).lower() == "asc" else "desc"
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), MAX_PAGE_SIZE))
    where, params = _dataset_where(filters)

    with get_connection() as conn:
        total = int(
            conn.execute(
                f"SELECT COUNT(*) AS c FROM datasets d{where}", params
            ).fetchone()["c"]
        )
        rows = conn.execute(
            f"SELECT d.* FROM datasets d{where} "
            f"ORDER BY d.{sort_by} {sort_dir.upper()}, d.id {sort_dir.upper()} "
            "LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()
    items = [_dataset_row(r) for r in rows]
    total_pages = (total + page_size - 1) // page_size if total else 0
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def dataset_enrichment(dataset_ids: List[int]) -> Dict[int, Dict[str, Any]]:
    """Per-dataset derived list info: version count, latest version stats, links."""
    if not dataset_ids:
        return {}
    marks = ",".join("?" for _ in dataset_ids)
    out: Dict[int, Dict[str, Any]] = {
        i: {
            "version_count": 0,
            "latest_quality_status": None,
            "latest_row_count": None,
            "latest_date_range": None,
            "latest_manifest_fingerprint": None,
            "linked_experiment_count": 0,
        }
        for i in dataset_ids
    }
    with get_connection() as conn:
        for r in conn.execute(
            f"SELECT dataset_id, COUNT(*) AS c FROM dataset_versions "
            f"WHERE dataset_id IN ({marks}) GROUP BY dataset_id",
            dataset_ids,
        ).fetchall():
            out[int(r["dataset_id"])]["version_count"] = int(r["c"])
        for r in conn.execute(
            f"""
            SELECT v.* FROM dataset_versions v
            JOIN (SELECT dataset_id, MAX(id) AS mx FROM dataset_versions
                  WHERE dataset_id IN ({marks}) GROUP BY dataset_id) latest
              ON latest.mx = v.id
            """,
            dataset_ids,
        ).fetchall():
            info = out[int(r["dataset_id"])]
            info["latest_quality_status"] = r["quality_status"]
            info["latest_row_count"] = r["row_count"]
            if r["start_time"] or r["end_time"]:
                info["latest_date_range"] = (
                    f"{(r['start_time'] or '?')[:10]} → {(r['end_time'] or '?')[:10]}"
                )
            info["latest_manifest_fingerprint"] = r["manifest_fingerprint"]
        for r in conn.execute(
            f"""
            SELECT v.dataset_id AS did, COUNT(DISTINCT l.experiment_id) AS c
              FROM experiment_dataset_links l
              JOIN dataset_versions v ON v.id = l.dataset_version_id
             WHERE v.dataset_id IN ({marks})
             GROUP BY v.dataset_id
            """,
            dataset_ids,
        ).fetchall():
            out[int(r["did"])]["linked_experiment_count"] = int(r["c"])
    return out


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


def insert_version(fields: Dict[str, Any]) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO dataset_versions (
                dataset_id, version_label, created_at, effective_from,
                effective_to, row_count, column_count, start_time, end_time,
                content_fingerprint, manifest_fingerprint, schema_fingerprint,
                source_fingerprint, file_size_bytes, format, compression,
                storage_locator_type, storage_locator, ingestion_method,
                deterministic, quality_status, validation_status,
                schema_snapshot_json, statistics_json, provenance_json,
                invalidated_at, invalidation_reason, demo_key
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                fields["dataset_id"],
                fields["version_label"],
                _utc_now(),
                fields.get("effective_from"),
                fields.get("effective_to"),
                fields.get("row_count"),
                fields.get("column_count"),
                fields.get("start_time"),
                fields.get("end_time"),
                fields.get("content_fingerprint"),
                fields["manifest_fingerprint"],
                fields.get("schema_fingerprint"),
                fields.get("source_fingerprint"),
                fields.get("file_size_bytes"),
                fields.get("format", "csv"),
                fields.get("compression"),
                fields["storage_locator_type"],
                fields["storage_locator"],
                fields.get("ingestion_method", "manual"),
                1 if fields.get("deterministic") else 0,
                fields.get("quality_status", "unknown"),
                fields.get("validation_status", "unknown"),
                json.dumps(fields.get("schema_snapshot", {})),
                json.dumps(fields.get("statistics_summary", {})),
                json.dumps(fields.get("provenance", {})),
                None,
                None,
                fields.get("demo_key"),
            ),
        )
        conn.commit()
        new_id = int(cursor.lastrowid)  # type: ignore[arg-type]
    record = get_version(new_id)
    assert record is not None
    return record


def get_version(version_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM dataset_versions WHERE id = ?", (version_id,)
        ).fetchone()
    return _version_row(row) if row else None


def version_demo_key_id(demo_key: str) -> Optional[int]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM dataset_versions WHERE demo_key = ?", (demo_key,)
        ).fetchone()
    return int(row["id"]) if row else None


def list_versions(dataset_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM dataset_versions WHERE dataset_id = ? "
            "ORDER BY created_at DESC, id DESC",
            (dataset_id,),
        ).fetchall()
    return [_version_row(r) for r in rows]


def update_version_columns(version_id: int, columns: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Narrow correction surface: statuses + invalidation only (immutability)."""
    allowed = {
        "quality_status",
        "validation_status",
        "invalidated_at",
        "invalidation_reason",
    }
    updates = {k: v for k, v in columns.items() if k in allowed}
    if not updates:
        return get_version(version_id)
    set_clause = ", ".join(f"{c} = ?" for c in updates)
    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE dataset_versions SET {set_clause} WHERE id = ?",
            [*updates.values(), version_id],
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
    return get_version(version_id)


def count_versions() -> Dict[str, int]:
    with get_connection() as conn:
        total = int(conn.execute("SELECT COUNT(*) AS c FROM dataset_versions").fetchone()["c"])
        derived = int(
            conn.execute(
                "SELECT COUNT(DISTINCT child_version_id) AS c FROM dataset_lineage"
            ).fetchone()["c"]
        )
        failures = int(
            conn.execute(
                "SELECT COUNT(*) AS c FROM dataset_versions WHERE quality_status = 'failed'"
            ).fetchone()["c"]
        )
    return {"versions": total, "derived_versions": derived, "quality_failures": failures}


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------


def insert_edge(fields: Dict[str, Any]) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO dataset_lineage (
                parent_version_id, child_version_id, relationship_type,
                transformation_name, transformation_version, parameters_json,
                code_reference, git_commit, created_at, notes
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                fields["parent_version_id"],
                fields["child_version_id"],
                fields["relationship_type"],
                fields["transformation_name"],
                fields.get("transformation_version"),
                json.dumps(fields.get("parameters", {})),
                fields.get("code_reference"),
                fields.get("git_commit"),
                _utc_now(),
                fields.get("notes", ""),
            ),
        )
        conn.commit()
        new_id = int(cursor.lastrowid)  # type: ignore[arg-type]
    edge = get_edge(new_id)
    assert edge is not None
    return edge


def get_edge(edge_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM dataset_lineage WHERE id = ?", (edge_id,)
        ).fetchone()
    return _edge_row(row) if row else None


def find_identical_edge(fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM dataset_lineage
             WHERE parent_version_id = ? AND child_version_id = ?
               AND relationship_type = ? AND transformation_name = ?
            """,
            (
                fields["parent_version_id"],
                fields["child_version_id"],
                fields["relationship_type"],
                fields["transformation_name"],
            ),
        ).fetchone()
    return _edge_row(row) if row else None


def edges_by_parent(version_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM dataset_lineage WHERE parent_version_id = ? ORDER BY id",
            (version_id,),
        ).fetchall()
    return [_edge_row(r) for r in rows]


def edges_by_child(version_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM dataset_lineage WHERE child_version_id = ? ORDER BY id",
            (version_id,),
        ).fetchall()
    return [_edge_row(r) for r in rows]


def all_edges() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM dataset_lineage ORDER BY id").fetchall()
    return [_edge_row(r) for r in rows]


# ---------------------------------------------------------------------------
# Quality results
# ---------------------------------------------------------------------------


def insert_quality_result(fields: Dict[str, Any]) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO dataset_quality_results (
                dataset_version_id, check_name, check_category, status,
                severity, observed_value, expected_value, message, checked_at,
                checker_version, details_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                fields["dataset_version_id"],
                fields["check_name"],
                fields.get("check_category", "structural"),
                fields["status"],
                fields.get("severity", "info"),
                fields.get("observed_value"),
                fields.get("expected_value"),
                fields.get("message", ""),
                _utc_now(),
                fields.get("checker_version", "v1"),
                json.dumps(fields.get("details", {})),
            ),
        )
        conn.commit()
        new_id = int(cursor.lastrowid)  # type: ignore[arg-type]
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM dataset_quality_results WHERE id = ?", (new_id,)
        ).fetchone()
    return _quality_row(row)


def list_quality_results(version_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM dataset_quality_results WHERE dataset_version_id = ? "
            "ORDER BY checked_at DESC, id DESC",
            (version_id,),
        ).fetchall()
    return [_quality_row(r) for r in rows]


# ---------------------------------------------------------------------------
# Experiment links
# ---------------------------------------------------------------------------


def insert_link(fields: Dict[str, Any]) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO experiment_dataset_links (
                experiment_id, dataset_version_id, role, created_at, notes
            ) VALUES (?,?,?,?,?)
            """,
            (
                fields["experiment_id"],
                fields["dataset_version_id"],
                fields["role"],
                _utc_now(),
                fields.get("notes", ""),
            ),
        )
        conn.commit()
        new_id = int(cursor.lastrowid)  # type: ignore[arg-type]
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM experiment_dataset_links WHERE id = ?", (new_id,)
        ).fetchone()
    return _link_row(row)


def find_link(experiment_id: int, dataset_version_id: int, role: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM experiment_dataset_links "
            "WHERE experiment_id = ? AND dataset_version_id = ? AND role = ?",
            (experiment_id, dataset_version_id, role),
        ).fetchone()
    return _link_row(row) if row else None


def links_for_version(version_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM experiment_dataset_links WHERE dataset_version_id = ? ORDER BY id",
            (version_id,),
        ).fetchall()
    return [_link_row(r) for r in rows]


def links_for_experiment(experiment_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM experiment_dataset_links WHERE experiment_id = ? ORDER BY id",
            (experiment_id,),
        ).fetchall()
    return [_link_row(r) for r in rows]


def all_links() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM experiment_dataset_links ORDER BY id").fetchall()
    return [_link_row(r) for r in rows]


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def registry_summary() -> Dict[str, Any]:
    with get_connection() as conn:
        datasets = int(conn.execute("SELECT COUNT(*) AS c FROM datasets").fetchone()["c"])
        unknown_prov = int(
            conn.execute(
                "SELECT COUNT(*) AS c FROM datasets WHERE provenance_status IN ('unknown','partial')"
            ).fetchone()["c"]
        )
        linked = int(
            conn.execute(
                "SELECT COUNT(DISTINCT experiment_id) AS c FROM experiment_dataset_links"
            ).fetchone()["c"]
        )
        source_rows = conn.execute(
            "SELECT source_type, COUNT(*) AS c FROM datasets GROUP BY source_type"
        ).fetchall()
        domains = [
            r["domain"]
            for r in conn.execute("SELECT DISTINCT domain FROM datasets ORDER BY domain").fetchall()
        ]
        formats = [
            r["format"]
            for r in conn.execute("SELECT DISTINCT format FROM datasets ORDER BY format").fetchall()
        ]
        tag_rows = conn.execute("SELECT tags_json FROM datasets").fetchall()
    tags: set[str] = set()
    for r in tag_rows:
        try:
            for t in json.loads(r["tags_json"]):
                if isinstance(t, str):
                    tags.add(t)
        except (ValueError, TypeError):
            continue
    counts = count_versions()
    return {
        "datasets": datasets,
        **counts,
        "unknown_provenance": unknown_prov,
        "linked_experiments": linked,
        "source_types": {r["source_type"]: int(r["c"]) for r in source_rows},
        "domains": domains,
        "formats": formats,
        "tags": sorted(tags),
    }


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "SORTABLE_COLUMNS",
    "insert_dataset",
    "get_dataset",
    "get_dataset_by_name",
    "dataset_demo_key_id",
    "update_dataset_columns",
    "list_datasets",
    "dataset_enrichment",
    "insert_version",
    "get_version",
    "version_demo_key_id",
    "list_versions",
    "update_version_columns",
    "count_versions",
    "insert_edge",
    "get_edge",
    "find_identical_edge",
    "edges_by_parent",
    "edges_by_child",
    "all_edges",
    "insert_quality_result",
    "list_quality_results",
    "insert_link",
    "find_link",
    "links_for_version",
    "links_for_experiment",
    "all_links",
    "registry_summary",
]
