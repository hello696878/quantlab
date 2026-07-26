"""SQLite persistence for the Overfitting Diagnostics Lab (parameterised SQL only)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.db import get_connection

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
SORTABLE = frozenset({"created_at", "updated_at", "name", "status", "metric",
                      "pbo_estimate"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _run_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"], "created_at": row["created_at"], "updated_at": row["updated_at"],
        "name": row["name"], "description": row["description"], "status": row["status"],
        "metric": row["metric"], "block_count": row["block_count"],
        "candidate_count": row["candidate_count"],
        "observation_count": row["observation_count"],
        "combination_count": row["combination_count"],
        "valid_split_count": row["valid_split_count"],
        "invalid_split_count": row["invalid_split_count"],
        "pbo_estimate": row["pbo_estimate"], "psr": row["psr"], "dsr": row["dsr"],
        "benchmark_sharpe": row["benchmark_sharpe"],
        "effective_trial_count": row["effective_trial_count"],
        "universe_fingerprint": row["universe_fingerprint"],
        "configuration": json.loads(row["configuration_json"]),
        "configuration_fingerprint": row["configuration_fingerprint"],
        "result_fingerprint": row["result_fingerprint"],
        "timestamps": json.loads(row["timestamps_json"]),
        "blocks": json.loads(row["blocks_json"]),
        "pbo_aggregate": json.loads(row["pbo_aggregate_json"]),
        "sharpe_diagnostics": json.loads(row["sharpe_diagnostics_json"]),
        "dependence": json.loads(row["dependence_json"]),
        "warnings": json.loads(row["warnings_json"]),
        "dataset_version_id": row["dataset_version_id"],
        "validation_run_id": row["validation_run_id"],
        "experiment_id": row["experiment_id"],
        "feature_diagnostics_run_id": row["feature_diagnostics_run_id"],
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
            INSERT INTO overfitting_diagnostic_runs (
                created_at, updated_at, name, description, status, metric,
                block_count, candidate_count, observation_count,
                combination_count, universe_fingerprint, configuration_json,
                configuration_fingerprint, timestamps_json,
                dataset_version_id, validation_run_id, experiment_id,
                feature_diagnostics_run_id, app_version, git_commit, notes,
                demo_key
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                now, now, fields["name"], fields.get("description", ""), "pending",
                fields["metric"], fields["block_count"],
                fields.get("candidate_count", 0), fields.get("observation_count", 0),
                fields.get("combination_count", 0),
                fields["universe_fingerprint"],
                json.dumps(fields.get("configuration", {})),
                fields["configuration_fingerprint"],
                json.dumps(fields.get("timestamps", [])),
                fields.get("dataset_version_id"), fields.get("validation_run_id"),
                fields.get("experiment_id"), fields.get("feature_diagnostics_run_id"),
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
        row = conn.execute(
            "SELECT * FROM overfitting_diagnostic_runs WHERE id = ?", (run_id,)
        ).fetchone()
    return _run_row(row) if row else None


def run_demo_key_id(demo_key: str) -> Optional[int]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM overfitting_diagnostic_runs WHERE demo_key = ?", (demo_key,)
        ).fetchone()
    return int(row["id"]) if row else None


def update_run(run_id: int, columns: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    allowed = {
        "status", "valid_split_count", "invalid_split_count", "pbo_estimate",
        "psr", "dsr", "benchmark_sharpe", "effective_trial_count",
        "result_fingerprint", "blocks_json", "pbo_aggregate_json",
        "sharpe_diagnostics_json", "dependence_json", "warnings_json",
        "is_baseline", "baseline_scope", "completed_at", "duration_ms",
        "experiment_id", "error_message", "notes",
    }
    updates = {k: v for k, v in columns.items() if k in allowed}
    if not updates:
        return get_run(run_id)
    set_clause = ", ".join(f"{c} = ?" for c in updates)
    with get_connection() as conn:
        cur = conn.execute(
            f"UPDATE overfitting_diagnostic_runs SET {set_clause}, updated_at = ? WHERE id = ?",
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
        ("status", "status"), ("metric", "metric"),
        ("dataset_version_id", "dataset_version_id"),
        ("validation_run_id", "validation_run_id"),
        ("configuration_fingerprint", "configuration_fingerprint"),
        ("universe_fingerprint", "universe_fingerprint"),
        ("is_baseline", "is_baseline"),
    ):
        if filters.get(key) is not None:
            clauses.append(f"{col} = ?")
            params.append(filters[key])
    if filters.get("max_pbo") is not None:
        clauses.append("pbo_estimate <= ?")
        params.append(filters["max_pbo"])
    if filters.get("min_pbo") is not None:
        clauses.append("pbo_estimate >= ?")
        params.append(filters["min_pbo"])
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
            f"SELECT COUNT(*) AS c FROM overfitting_diagnostic_runs{where}",
            params).fetchone()["c"])
        rows = conn.execute(
            f"SELECT * FROM overfitting_diagnostic_runs{where} "
            f"ORDER BY {sort_by} {sort_dir.upper()}, id {sort_dir.upper()} "
            f"LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size]).fetchall()
    return {"items": [_run_row(r) for r in rows], "total": total, "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total else 0}


# --- candidates ------------------------------------------------------------


def _candidate_row(r) -> Dict[str, Any]:
    return {
        "candidate_id": r["candidate_id"], "name": r["name"],
        "description": r["description"], "candidate_group": r["candidate_group"],
        "experiment_id": r["experiment_id"],
        "validation_run_id": r["validation_run_id"],
        "dataset_version_id": r["dataset_version_id"],
        "configuration_fingerprint": r["configuration_fingerprint"],
        "result_fingerprint": r["result_fingerprint"],
        "returns": json.loads(r["returns_json"]),
        "nominal_p_value": r["nominal_p_value"],
        "p_value_provenance": (json.loads(r["p_value_provenance_json"])
                               if r["p_value_provenance_json"] else None),
        "metadata": json.loads(r["metadata_json"]),
        "raw_sharpe": r["raw_sharpe"], "skewness": r["skewness"],
        "kurtosis": r["kurtosis"], "psr": r["psr"],
        "sharpe_status": r["sharpe_status"], "sharpe_note": r["sharpe_note"],
        "mean_return": r["mean_return"],
        "cumulative_return": r["cumulative_return"],
        "selection_frequency": r["selection_frequency"],
        "mean_oos_rank": r["mean_oos_rank"], "status": r["status"],
    }


def replace_candidates(run_id: int, candidates: List[Dict[str, Any]]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM overfitting_candidates WHERE run_id = ?", (run_id,))
        for c in candidates:
            conn.execute(
                """
                INSERT INTO overfitting_candidates (
                    run_id, candidate_id, name, description, candidate_group,
                    experiment_id, validation_run_id, dataset_version_id,
                    configuration_fingerprint, result_fingerprint, returns_json,
                    nominal_p_value, p_value_provenance_json, metadata_json,
                    raw_sharpe, skewness, kurtosis, psr, sharpe_status,
                    sharpe_note, mean_return, cumulative_return,
                    selection_frequency, mean_oos_rank, status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (run_id, c["candidate_id"], c["name"], c.get("description", ""),
                 c.get("candidate_group"), c.get("experiment_id"),
                 c.get("validation_run_id"), c.get("dataset_version_id"),
                 c.get("configuration_fingerprint"), c.get("result_fingerprint"),
                 json.dumps(c["returns"]), c.get("nominal_p_value"),
                 json.dumps(c["p_value_provenance"]) if c.get("p_value_provenance") else None,
                 json.dumps(c.get("metadata", {})),
                 c.get("raw_sharpe"), c.get("skewness"), c.get("kurtosis"),
                 c.get("psr"), c.get("sharpe_status"), c.get("sharpe_note"),
                 c.get("mean_return"), c.get("cumulative_return"),
                 c.get("selection_frequency"), c.get("mean_oos_rank"),
                 c.get("status", "ok")),
            )
        conn.commit()


def list_candidates(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM overfitting_candidates WHERE run_id = ? ORDER BY candidate_id",
            (run_id,)).fetchall()
    return [_candidate_row(r) for r in rows]


def update_candidate_stats(run_id: int, candidate_id: str,
                           columns: Dict[str, Any]) -> None:
    allowed = {"raw_sharpe", "skewness", "kurtosis", "psr", "sharpe_status",
               "sharpe_note", "mean_return", "cumulative_return",
               "selection_frequency", "mean_oos_rank", "status"}
    updates = {k: v for k, v in columns.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{c} = ?" for c in updates)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE overfitting_candidates SET {set_clause} "
            "WHERE run_id = ? AND candidate_id = ?",
            [*updates.values(), run_id, candidate_id])
        conn.commit()


# --- PBO splits ------------------------------------------------------------


def replace_splits(run_id: int, splits: List[Dict[str, Any]]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM pbo_split_results WHERE run_id = ?", (run_id,))
        for s in splits:
            conn.execute(
                """
                INSERT INTO pbo_split_results (
                    run_id, split_id, split_index, is_block_ids_json,
                    oos_block_ids_json, selected_candidate_id, is_metric,
                    oos_metric, oos_rank, oos_defined_count, relative_rank,
                    lambda, degradation, rank_degradation, tie_in_sample,
                    tie_out_of_sample, status, warning
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (run_id, s["split_id"], s["split_index"],
                 json.dumps(s["is_block_ids"]), json.dumps(s["oos_block_ids"]),
                 s.get("selected_candidate_id"), s.get("is_metric"),
                 s.get("oos_metric"), s.get("oos_rank"),
                 s.get("oos_defined_count"), s.get("relative_rank"),
                 s.get("lambda"), s.get("degradation"),
                 s.get("rank_degradation"),
                 1 if s.get("tie_in_sample") else 0,
                 1 if s.get("tie_out_of_sample") else 0,
                 s.get("status", "valid"), s.get("warning")),
            )
        conn.commit()


def list_splits(run_id: int, *, page: int = 1, page_size: int = 100) -> Dict[str, Any]:
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), 500))
    with get_connection() as conn:
        total = int(conn.execute(
            "SELECT COUNT(*) AS c FROM pbo_split_results WHERE run_id = ?",
            (run_id,)).fetchone()["c"])
        rows = conn.execute(
            "SELECT * FROM pbo_split_results WHERE run_id = ? "
            "ORDER BY split_index LIMIT ? OFFSET ?",
            (run_id, page_size, (page - 1) * page_size)).fetchall()
    items = [{
        "split_id": r["split_id"], "split_index": r["split_index"],
        "is_block_ids": json.loads(r["is_block_ids_json"]),
        "oos_block_ids": json.loads(r["oos_block_ids_json"]),
        "selected_candidate_id": r["selected_candidate_id"],
        "is_metric": r["is_metric"], "oos_metric": r["oos_metric"],
        "oos_rank": r["oos_rank"], "oos_defined_count": r["oos_defined_count"],
        "relative_rank": r["relative_rank"], "lambda": r["lambda"],
        "degradation": r["degradation"],
        "rank_degradation": r["rank_degradation"],
        "tie_in_sample": bool(r["tie_in_sample"]),
        "tie_out_of_sample": bool(r["tie_out_of_sample"]),
        "status": r["status"], "warning": r["warning"],
    } for r in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total else 0}


def all_splits(run_id: int) -> List[Dict[str, Any]]:
    """Every split row (bounded by MAX_COMBINATIONS = 924 per run)."""
    out: List[Dict[str, Any]] = []
    page = 1
    while True:
        chunk = list_splits(run_id, page=page, page_size=500)
        out.extend(chunk["items"])
        if page >= max(1, chunk["total_pages"]):
            return out
        page += 1


# --- multiple testing ------------------------------------------------------


def replace_multiple_testing(run_id: int, rows_in: List[Dict[str, Any]]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM multiple_testing_results WHERE run_id = ?", (run_id,))
        for r in rows_in:
            conn.execute(
                """
                INSERT INTO multiple_testing_results (
                    run_id, candidate_id, raw_p_value, bonferroni, holm, bh,
                    provenance_status, provenance_json, state_raw,
                    state_bonferroni, state_holm, state_bh
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (run_id, r["candidate_id"], r.get("raw_p_value"),
                 r.get("bonferroni"), r.get("holm"), r.get("bh"),
                 r.get("provenance_status", "unavailable"),
                 json.dumps(r["provenance"]) if r.get("provenance") else None,
                 r.get("state_raw", "unavailable"),
                 r.get("state_bonferroni", "unavailable"),
                 r.get("state_holm", "unavailable"),
                 r.get("state_bh", "unavailable")),
            )
        conn.commit()


def list_multiple_testing(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM multiple_testing_results WHERE run_id = ? "
            "ORDER BY candidate_id", (run_id,)).fetchall()
    return [{
        "candidate_id": r["candidate_id"], "raw_p_value": r["raw_p_value"],
        "bonferroni": r["bonferroni"], "holm": r["holm"], "bh": r["bh"],
        "provenance_status": r["provenance_status"],
        "provenance": json.loads(r["provenance_json"]) if r["provenance_json"] else None,
        "state_raw": r["state_raw"], "state_bonferroni": r["state_bonferroni"],
        "state_holm": r["state_holm"], "state_bh": r["state_bh"],
    } for r in rows]


# --- baselines + summary ---------------------------------------------------


def mark_baseline(run_id: int, scope: str) -> None:
    """One active baseline per scope (transactional replacement)."""
    now = _now()
    with get_connection() as conn:
        conn.execute(
            "UPDATE overfitting_diagnostic_runs SET is_baseline = 0, updated_at = ? "
            "WHERE baseline_scope = ? AND is_baseline = 1 AND id != ?",
            (now, scope, run_id))
        conn.execute(
            "UPDATE overfitting_diagnostic_runs SET is_baseline = 1, updated_at = ? "
            "WHERE id = ?", (now, run_id))
        conn.commit()


def lab_summary() -> Dict[str, Any]:
    with get_connection() as conn:
        runs = int(conn.execute(
            "SELECT COUNT(*) AS c FROM overfitting_diagnostic_runs").fetchone()["c"])
        completed = int(conn.execute(
            "SELECT COUNT(*) AS c FROM overfitting_diagnostic_runs "
            "WHERE status='completed'").fetchone()["c"])
        candidates = int(conn.execute(
            "SELECT COUNT(*) AS c FROM overfitting_candidates").fetchone()["c"])
        valid_splits = int(conn.execute(
            "SELECT COALESCE(SUM(valid_split_count), 0) AS c "
            "FROM overfitting_diagnostic_runs").fetchone()["c"])
        baselines = int(conn.execute(
            "SELECT COUNT(*) AS c FROM overfitting_diagnostic_runs "
            "WHERE is_baseline=1").fetchone()["c"])
        adjusted_below = int(conn.execute(
            "SELECT COUNT(*) AS c FROM multiple_testing_results "
            "WHERE state_holm='below_threshold' OR state_bh='below_threshold'"
        ).fetchone()["c"])
        metrics = conn.execute(
            "SELECT metric AS m, COUNT(*) AS c FROM overfitting_diagnostic_runs "
            "GROUP BY metric").fetchall()
    return {"runs": runs, "completed": completed, "candidates": candidates,
            "valid_splits": valid_splits, "baselines": baselines,
            "adjusted_below_threshold": adjusted_below,
            "metrics": {r["m"]: int(r["c"]) for r in metrics}}


__all__ = [
    "DEFAULT_PAGE_SIZE", "MAX_PAGE_SIZE", "SORTABLE",
    "insert_run", "get_run", "run_demo_key_id", "update_run", "list_runs",
    "replace_candidates", "list_candidates", "update_candidate_stats",
    "replace_splits", "list_splits", "all_splits",
    "replace_multiple_testing", "list_multiple_testing",
    "mark_baseline", "lab_summary",
]
