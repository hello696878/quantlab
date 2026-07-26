"""SQLite persistence for the Feature Diagnostics Lab (parameterised SQL only)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.db import get_connection

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
SORTABLE = frozenset({"created_at", "updated_at", "name", "status", "method", "metric"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _run_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"], "created_at": row["created_at"], "updated_at": row["updated_at"],
        "name": row["name"], "description": row["description"], "status": row["status"],
        "method": row["method"], "model_type": row["model_type"],
        "target_type": row["target_type"], "metric": row["metric"],
        "metric_direction": row["metric_direction"],
        "split_source": row["split_source"],
        "integrity_status": row["integrity_status"],
        "validation_run_id": row["validation_run_id"],
        "dataset_version_id": row["dataset_version_id"],
        "experiment_id": row["experiment_id"],
        "meta_label_run_id": row["meta_label_run_id"],
        "configuration": json.loads(row["configuration_json"]),
        "configuration_fingerprint": row["configuration_fingerprint"],
        "result_fingerprint": row["result_fingerprint"],
        "baseline_fingerprint": row["baseline_fingerprint"],
        "sample_count": row["sample_count"], "feature_count": row["feature_count"],
        "split_count": row["split_count"],
        "valid_split_count": row["valid_split_count"],
        "invalid_split_count": row["invalid_split_count"],
        "splits": json.loads(row["splits_json"]),
        "stability_summary": json.loads(row["stability_summary_json"]),
        "importance_drift": json.loads(row["importance_drift_json"]),
        "references": json.loads(row["references_json"]),
        "drift_context": json.loads(row["drift_context_json"]),
        "warnings": json.loads(row["warnings_json"]),
        "is_baseline": bool(row["is_baseline"]),
        "baseline_scope": row["baseline_scope"],
        "completed_at": row["completed_at"], "duration_ms": row["duration_ms"],
        "app_version": row["app_version"], "git_commit": row["git_commit"],
        "notes": row["notes"], "error_message": row["error_message"],
    }


def insert_run(fields: Dict[str, Any]) -> Dict[str, Any]:
    now = _now()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO feature_runs (
                created_at, updated_at, name, description, status,
                method, model_type, target_type, metric, metric_direction,
                split_source, integrity_status, validation_run_id,
                dataset_version_id, experiment_id, meta_label_run_id,
                configuration_json, configuration_fingerprint, sample_count,
                feature_count, baseline_scope, app_version, git_commit,
                notes, demo_key
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                now, now, fields["name"], fields.get("description", ""), "pending",
                fields["method"], fields["model_type"], fields["target_type"],
                fields["metric"], fields["metric_direction"],
                fields["split_source"], fields.get("integrity_status", "unknown"),
                fields.get("validation_run_id"), fields.get("dataset_version_id"),
                fields.get("experiment_id"), fields.get("meta_label_run_id"),
                json.dumps(fields.get("configuration", {})),
                fields["configuration_fingerprint"],
                fields.get("sample_count", 0), fields.get("feature_count", 0),
                fields.get("baseline_scope"),
                fields.get("app_version"), fields.get("git_commit"),
                fields.get("notes", ""), fields.get("demo_key"),
            ),
        )
        conn.commit()
        new_id = int(cur.lastrowid)  # type: ignore[arg-type]
    run = get_run(new_id)
    assert run is not None
    return run


def get_run(run_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM feature_runs WHERE id = ?", (run_id,)).fetchone()
    return _run_row(row) if row else None


def run_demo_key_id(demo_key: str) -> Optional[int]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM feature_runs WHERE demo_key = ?", (demo_key,)
        ).fetchone()
    return int(row["id"]) if row else None


def update_run(run_id: int, columns: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    allowed = {
        "status", "integrity_status", "result_fingerprint", "baseline_fingerprint",
        "split_count", "valid_split_count", "invalid_split_count", "splits_json",
        "stability_summary_json", "importance_drift_json", "references_json",
        "drift_context_json", "warnings_json", "is_baseline", "baseline_scope",
        "completed_at", "duration_ms", "experiment_id", "error_message", "notes",
    }
    updates = {k: v for k, v in columns.items() if k in allowed}
    if not updates:
        return get_run(run_id)
    set_clause = ", ".join(f"{c} = ?" for c in updates)
    with get_connection() as conn:
        cur = conn.execute(
            f"UPDATE feature_runs SET {set_clause}, updated_at = ? WHERE id = ?",
            [*updates.values(), _now(), run_id],
        )
        conn.commit()
        if cur.rowcount == 0:
            return None
    return get_run(run_id)


def _where(filters: Dict[str, Any]) -> Tuple[str, List[Any]]:
    clauses: List[str] = []
    params: List[Any] = []
    for col, key in (
        ("status", "status"), ("method", "method"), ("metric", "metric"),
        ("integrity_status", "integrity_status"),
        ("validation_run_id", "validation_run_id"),
        ("dataset_version_id", "dataset_version_id"),
        ("configuration_fingerprint", "configuration_fingerprint"),
        ("is_baseline", "is_baseline"),
    ):
        if filters.get(key) is not None:
            clauses.append(f"{col} = ?")
            params.append(filters[key])
    if filters.get("query"):
        clauses.append("(name LIKE ? OR description LIKE ?)")
        like = f"%{filters['query']}%"
        params.extend([like, like])
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def list_runs(*, filters=None, sort_by="created_at", sort_dir="desc",
              page=1, page_size=DEFAULT_PAGE_SIZE) -> Dict[str, Any]:
    filters = filters or {}
    if sort_by not in SORTABLE:
        sort_by = "created_at"
    sort_dir = "asc" if str(sort_dir).lower() == "asc" else "desc"
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), MAX_PAGE_SIZE))
    where, params = _where(filters)
    with get_connection() as conn:
        total = int(conn.execute(
            f"SELECT COUNT(*) AS c FROM feature_runs{where}", params).fetchone()["c"])
        rows = conn.execute(
            f"SELECT * FROM feature_runs{where} ORDER BY {sort_by} {sort_dir.upper()}, "
            f"id {sort_dir.upper()} LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size]).fetchall()
    return {"items": [_run_row(r) for r in rows], "total": total, "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total else 0}


# --- samples ---------------------------------------------------------------


def replace_samples(run_id: int, samples: List[Dict[str, Any]]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM feature_samples WHERE run_id = ?", (run_id,))
        for s in samples:
            conn.execute(
                "INSERT INTO feature_samples (run_id, sample_id, timestamp, target, "
                "features_json) VALUES (?,?,?,?,?)",
                (run_id, s["sample_id"], s["timestamp"], s["target"],
                 json.dumps(s["features"])),
            )
        conn.commit()


def all_samples(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM feature_samples WHERE run_id = ? ORDER BY timestamp, sample_id",
            (run_id,)).fetchall()
    return [{"sample_id": r["sample_id"], "timestamp": r["timestamp"],
             "target": r["target"], "features": json.loads(r["features_json"])}
            for r in rows]


# --- aggregate feature results --------------------------------------------


def replace_results(run_id: int, results: List[Dict[str, Any]]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM feature_results WHERE run_id = ?", (run_id,))
        for r in results:
            conn.execute(
                """
                INSERT INTO feature_results (
                    run_id, feature_name, definition_json, rank, mean_importance,
                    median_importance, std_importance, min_importance,
                    max_importance, quantile_json, mean_rank, median_rank,
                    rank_std, rank_range, positive_split_fraction,
                    negative_split_fraction, valid_split_count, stability_score,
                    stability_classification, sign_consistency, sign_changed,
                    warning
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (run_id, r["feature_name"], json.dumps(r.get("definition", {})),
                 r.get("rank"), r.get("mean_importance"),
                 r.get("median_importance"), r.get("std_importance"),
                 r.get("min_importance"), r.get("max_importance"),
                 json.dumps(r["quantile_interval"]) if r.get("quantile_interval") else None,
                 r.get("mean_rank"), r.get("median_rank"), r.get("rank_std"),
                 r.get("rank_range"), r.get("positive_split_fraction"),
                 r.get("negative_split_fraction"), r.get("valid_split_count", 0),
                 r.get("stability_score"),
                 r.get("stability_classification", "unknown"),
                 r.get("sign_consistency"),
                 1 if r.get("sign_changed_across_splits") else 0,
                 r.get("warning")),
            )
        conn.commit()


def list_results(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM feature_results WHERE run_id = ? "
            "ORDER BY (rank IS NULL), rank, feature_name", (run_id,)).fetchall()
    return [{
        "feature_name": r["feature_name"],
        "definition": json.loads(r["definition_json"]),
        "rank": r["rank"], "mean_importance": r["mean_importance"],
        "median_importance": r["median_importance"],
        "std_importance": r["std_importance"],
        "min_importance": r["min_importance"], "max_importance": r["max_importance"],
        "quantile_interval": json.loads(r["quantile_json"]) if r["quantile_json"] else None,
        "mean_rank": r["mean_rank"], "median_rank": r["median_rank"],
        "rank_std": r["rank_std"], "rank_range": r["rank_range"],
        "positive_split_fraction": r["positive_split_fraction"],
        "negative_split_fraction": r["negative_split_fraction"],
        "valid_split_count": r["valid_split_count"],
        "stability_score": r["stability_score"],
        "stability_classification": r["stability_classification"],
        "sign_consistency": r["sign_consistency"],
        "sign_changed_across_splits": bool(r["sign_changed"]),
        "warning": r["warning"],
    } for r in rows]


# --- split-level results ---------------------------------------------------


def replace_split_results(run_id: int, rows_in: List[Dict[str, Any]]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM feature_split_results WHERE run_id = ?", (run_id,))
        for r in rows_in:
            conn.execute(
                """
                INSERT INTO feature_split_results (
                    run_id, split_id, split_index, feature_name, baseline_score,
                    mean_importance, median_importance, std_importance,
                    min_importance, max_importance, positive_repeats,
                    negative_repeats, valid_repeats, permutation_repeats,
                    rank, status, warning
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (run_id, r["split_id"], r["split_index"], r["feature_name"],
                 r.get("baseline_score"), r.get("mean_importance"),
                 r.get("median_importance"), r.get("std_importance"),
                 r.get("min_importance"), r.get("max_importance"),
                 r.get("positive_repeats", 0), r.get("negative_repeats", 0),
                 r.get("valid_repeats", 0), r.get("permutation_repeats", 0),
                 r.get("rank"), r.get("status", "ok"), r.get("warning")),
            )
        conn.commit()


def list_split_results(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM feature_split_results WHERE run_id = ? "
            "ORDER BY split_index, feature_name", (run_id,)).fetchall()
    return [{
        "split_id": r["split_id"], "split_index": r["split_index"],
        "feature_name": r["feature_name"], "baseline_score": r["baseline_score"],
        "mean_importance": r["mean_importance"],
        "median_importance": r["median_importance"],
        "std_importance": r["std_importance"],
        "min_importance": r["min_importance"], "max_importance": r["max_importance"],
        "positive_repeats": r["positive_repeats"],
        "negative_repeats": r["negative_repeats"],
        "valid_repeats": r["valid_repeats"],
        "permutation_repeats": r["permutation_repeats"],
        "rank": r["rank"], "status": r["status"], "warning": r["warning"],
    } for r in rows]


# --- correlation groups ----------------------------------------------------


def replace_correlation_groups(run_id: int, groups: List[Dict[str, Any]]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM feature_correlation_groups WHERE run_id = ?", (run_id,))
        for g in groups:
            conn.execute(
                "INSERT INTO feature_correlation_groups (run_id, group_id, size, "
                "max_abs_correlation, members_json, pairs_json, "
                "combined_mean_importance) VALUES (?,?,?,?,?,?,?)",
                (run_id, g["group_id"], g["size"], g.get("max_abs_correlation"),
                 json.dumps(g["features"]), json.dumps(g["pairs"]),
                 g.get("combined_mean_importance")),
            )
        conn.commit()


def list_correlation_groups(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM feature_correlation_groups WHERE run_id = ? ORDER BY group_id",
            (run_id,)).fetchall()
    return [{
        "group_id": r["group_id"], "size": r["size"],
        "max_abs_correlation": r["max_abs_correlation"],
        "features": json.loads(r["members_json"]),
        "pairs": json.loads(r["pairs_json"]),
        "combined_mean_importance": r["combined_mean_importance"],
    } for r in rows]


# --- drift results ---------------------------------------------------------


def replace_drift_results(run_id: int, rows_in: List[Dict[str, Any]]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM feature_drift_results WHERE run_id = ?", (run_id,))
        for r in rows_in:
            conn.execute(
                "INSERT INTO feature_drift_results (run_id, feature_name, kind, "
                "classification, psi, ks_statistic, detail_json) VALUES (?,?,?,?,?,?,?)",
                (run_id, r["feature_name"], r["kind"],
                 r.get("classification", "unknown"), r.get("psi"),
                 r.get("ks_statistic"), json.dumps(r.get("detail", {}))),
            )
        conn.commit()


def list_drift_results(run_id: int, kind: Optional[str] = None) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM feature_drift_results WHERE run_id = ?"
    params: List[Any] = [run_id]
    if kind is not None:
        sql += " AND kind = ?"
        params.append(kind)
    sql += " ORDER BY kind, feature_name"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [{
        "feature_name": r["feature_name"], "kind": r["kind"],
        "classification": r["classification"], "psi": r["psi"],
        "ks_statistic": r["ks_statistic"],
        "detail": json.loads(r["detail_json"]),
    } for r in rows]


# --- baselines -------------------------------------------------------------


def mark_baseline(run_id: int, scope: str, baseline_fp: str) -> None:
    """One active baseline per scope (transactional replacement)."""
    now = _now()
    with get_connection() as conn:
        conn.execute(
            "UPDATE feature_runs SET is_baseline = 0, baseline_fingerprint = NULL, "
            "updated_at = ? WHERE baseline_scope = ? AND is_baseline = 1 AND id != ?",
            (now, scope, run_id))
        conn.execute(
            "UPDATE feature_runs SET is_baseline = 1, baseline_fingerprint = ?, "
            "updated_at = ? WHERE id = ?",
            (baseline_fp, now, run_id))
        conn.commit()


def lab_summary() -> Dict[str, Any]:
    with get_connection() as conn:
        runs = int(conn.execute("SELECT COUNT(*) AS c FROM feature_runs").fetchone()["c"])
        completed = int(conn.execute(
            "SELECT COUNT(*) AS c FROM feature_runs WHERE status='completed'").fetchone()["c"])
        verified = int(conn.execute(
            "SELECT COUNT(*) AS c FROM feature_runs WHERE integrity_status='verified_held_out'"
        ).fetchone()["c"])
        baselines = int(conn.execute(
            "SELECT COUNT(*) AS c FROM feature_runs WHERE is_baseline=1").fetchone()["c"])
        stable = int(conn.execute(
            "SELECT COUNT(*) AS c FROM feature_results WHERE stability_classification='stable'"
        ).fetchone()["c"])
        drift_flags = int(conn.execute(
            "SELECT COUNT(*) AS c FROM feature_drift_results "
            "WHERE kind='distribution' AND classification IN ('moderate','high')"
        ).fetchone()["c"])
        methods = conn.execute(
            "SELECT method AS m, COUNT(*) AS c FROM feature_runs GROUP BY method"
        ).fetchall()
    return {"runs": runs, "completed": completed, "held_out_verified": verified,
            "stable_features": stable, "drift_flags": drift_flags,
            "baselines": baselines,
            "methods": {r["m"]: int(r["c"]) for r in methods}}


__all__ = [
    "DEFAULT_PAGE_SIZE", "MAX_PAGE_SIZE", "SORTABLE",
    "insert_run", "get_run", "run_demo_key_id", "update_run", "list_runs",
    "replace_samples", "all_samples", "replace_results", "list_results",
    "replace_split_results", "list_split_results",
    "replace_correlation_groups", "list_correlation_groups",
    "replace_drift_results", "list_drift_results", "mark_baseline",
    "lab_summary",
]
