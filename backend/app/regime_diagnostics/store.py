"""SQLite persistence for the Regime Diagnostics Lab (parameterised SQL only)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.db import get_connection

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
SORTABLE = frozenset({"created_at", "updated_at", "name", "status",
                      "integrity_status"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _run_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"], "created_at": row["created_at"], "updated_at": row["updated_at"],
        "name": row["name"], "description": row["description"], "status": row["status"],
        "candidate_count": row["candidate_count"],
        "observation_count": row["observation_count"],
        "period_count": row["period_count"], "frequency": row["frequency"],
        "regime_definition_count": row["regime_definition_count"],
        "observed_regime_count": row["observed_regime_count"],
        "invalid_definition_count": row["invalid_definition_count"],
        "low_coverage_warning_count": row["low_coverage_warning_count"],
        "integrity_status": row["integrity_status"],
        "universe_fingerprint": row["universe_fingerprint"],
        "configuration": json.loads(row["configuration_json"]),
        "configuration_fingerprint": row["configuration_fingerprint"],
        "result_fingerprint": row["result_fingerprint"],
        "timestamps": json.loads(row["timestamps_json"]),
        "candidates": json.loads(row["candidates_json"]),
        "market_features": json.loads(row["market_features_json"]),
        "sample_ids": (json.loads(row["sample_ids_json"])
                       if row["sample_ids_json"] else None),
        "coverage": json.loads(row["coverage_json"]),
        "robustness": json.loads(row["robustness_json"]),
        "rank_stability": json.loads(row["rank_stability_json"]),
        "concentration": json.loads(row["concentration_json"]),
        "warnings": json.loads(row["warnings_json"]),
        "dataset_version_id": row["dataset_version_id"],
        "validation_run_id": row["validation_run_id"],
        "overfitting_run_id": row["overfitting_run_id"],
        "feature_diagnostics_run_id": row["feature_diagnostics_run_id"],
        "meta_label_run_id": row["meta_label_run_id"],
        "experiment_id": row["experiment_id"],
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
            INSERT INTO regime_diagnostic_runs (
                created_at, updated_at, name, description, status,
                candidate_count, observation_count, period_count, frequency,
                regime_definition_count, universe_fingerprint,
                configuration_json, configuration_fingerprint, timestamps_json,
                candidates_json, market_features_json, sample_ids_json,
                dataset_version_id, validation_run_id, overfitting_run_id,
                feature_diagnostics_run_id, meta_label_run_id, experiment_id,
                app_version, git_commit, notes, demo_key
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                now, now, fields["name"], fields.get("description", ""), "pending",
                fields.get("candidate_count", 0), fields.get("observation_count", 0),
                fields.get("period_count", 0), fields.get("frequency", ""),
                fields.get("regime_definition_count", 0),
                fields["universe_fingerprint"],
                json.dumps(fields.get("configuration", {})),
                fields["configuration_fingerprint"],
                json.dumps(fields.get("timestamps", [])),
                json.dumps(fields.get("candidates", [])),
                json.dumps(fields.get("market_features", {})),
                (json.dumps(fields["sample_ids"])
                 if fields.get("sample_ids") is not None else None),
                fields.get("dataset_version_id"), fields.get("validation_run_id"),
                fields.get("overfitting_run_id"),
                fields.get("feature_diagnostics_run_id"),
                fields.get("meta_label_run_id"), fields.get("experiment_id"),
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
            "SELECT * FROM regime_diagnostic_runs WHERE id = ?", (run_id,)
        ).fetchone()
    return _run_row(row) if row else None


def run_demo_key_id(demo_key: str) -> Optional[int]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM regime_diagnostic_runs WHERE demo_key = ?", (demo_key,)
        ).fetchone()
    return int(row["id"]) if row else None


def update_run(run_id: int, columns: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    allowed = {
        "status", "integrity_status", "observed_regime_count",
        "invalid_definition_count", "low_coverage_warning_count",
        "result_fingerprint", "coverage_json", "robustness_json",
        "rank_stability_json", "concentration_json", "warnings_json",
        "is_baseline", "baseline_scope", "completed_at", "duration_ms",
        "experiment_id", "error_message", "notes",
    }
    updates = {k: v for k, v in columns.items() if k in allowed}
    if not updates:
        return get_run(run_id)
    set_clause = ", ".join(f"{c} = ?" for c in updates)
    with get_connection() as conn:
        cur = conn.execute(
            f"UPDATE regime_diagnostic_runs SET {set_clause}, updated_at = ? WHERE id = ?",
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
        ("status", "status"), ("integrity_status", "integrity_status"),
        ("dataset_version_id", "dataset_version_id"),
        ("validation_run_id", "validation_run_id"),
        ("overfitting_run_id", "overfitting_run_id"),
        ("configuration_fingerprint", "configuration_fingerprint"),
        ("universe_fingerprint", "universe_fingerprint"),
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
            f"SELECT COUNT(*) AS c FROM regime_diagnostic_runs{where}",
            params).fetchone()["c"])
        rows = conn.execute(
            f"SELECT * FROM regime_diagnostic_runs{where} "
            f"ORDER BY {sort_by} {sort_dir.upper()}, id {sort_dir.upper()} "
            f"LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size]).fetchall()
    return {"items": [_run_row(r) for r in rows], "total": total, "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total else 0}


# --- definitions (carrying assignments + transitions) ----------------------


def _definition_row(r) -> Dict[str, Any]:
    return {
        "definition_id": r["definition_id"], "name": r["name"],
        "description": r["description"], "dimension": r["dimension"],
        "source_feature": r["source_feature"], "lookback": r["lookback"],
        "lag": r["lag"], "threshold_mode": r["threshold_mode"],
        "min_observations": r["min_observations"],
        "integrity_status": r["integrity_status"], "status": r["status"],
        "definition": json.loads(r["definition_json"]),
        "definition_fingerprint": r["definition_fingerprint"],
        "thresholds_used": (json.loads(r["thresholds_used_json"])
                            if r["thresholds_used_json"] else None),
        "threshold_fingerprint": r["threshold_fingerprint"],
        "assignments": json.loads(r["assignments_json"]),
        "unavailable_count": r["unavailable_count"],
        "distinct_label_count": r["distinct_label_count"],
        "interval_summary": json.loads(r["interval_summary_json"]),
        "transitions": json.loads(r["transition_json"]),
        "warnings": json.loads(r["warnings_json"]),
    }


def replace_definitions(run_id: int, definitions: List[Dict[str, Any]]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM regime_definitions WHERE run_id = ?", (run_id,))
        for d in definitions:
            conn.execute(
                """
                INSERT INTO regime_definitions (
                    run_id, definition_id, name, description, dimension,
                    source_feature, lookback, lag, threshold_mode,
                    min_observations, integrity_status, status, definition_json,
                    definition_fingerprint, thresholds_used_json,
                    threshold_fingerprint, assignments_json, unavailable_count,
                    distinct_label_count, interval_summary_json,
                    transition_json, warnings_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (run_id, d["definition_id"], d["name"], d.get("description", ""),
                 d["dimension"], d.get("source_feature"), d.get("lookback"),
                 d.get("lag"), d.get("threshold_mode"),
                 d.get("min_observations", 8),
                 d.get("integrity_status", "unknown"), d.get("status", "pending"),
                 json.dumps(d.get("definition", {})),
                 d["definition_fingerprint"],
                 (json.dumps(d["thresholds_used"])
                  if d.get("thresholds_used") is not None else None),
                 d.get("threshold_fingerprint"),
                 json.dumps(d.get("assignments", [])),
                 d.get("unavailable_count", 0),
                 d.get("distinct_label_count", 0),
                 json.dumps(d.get("interval_summary", {})),
                 json.dumps(d.get("transitions", {})),
                 json.dumps(d.get("warnings", []))),
            )
        conn.commit()


def list_definitions(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM regime_definitions WHERE run_id = ? ORDER BY definition_id",
            (run_id,)).fetchall()
    return [_definition_row(r) for r in rows]


# --- conditional results ---------------------------------------------------


def replace_conditional_results(run_id: int, rows_in: List[Dict[str, Any]]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM regime_conditional_results WHERE run_id = ?", (run_id,))
        for r in rows_in:
            m = r["metrics"]
            conn.execute(
                """
                INSERT INTO regime_conditional_results (
                    run_id, candidate_id, definition_id, regime_label,
                    observation_count, coverage, mean, median, std, minimum,
                    maximum, positive_rate, negative_rate, cumulative,
                    sharpe_like, downside_deviation, status, note
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (run_id, r["candidate_id"], r["definition_id"], r["regime_label"],
                 m["observation_count"], m["coverage"], m["mean"], m["median"],
                 m["std"], m["minimum"], m["maximum"], m["positive_rate"],
                 m["negative_rate"], m["cumulative"], m["sharpe_like"],
                 m["downside_deviation"], m["status"], m["note"]),
            )
        conn.commit()


def list_conditional_results(
    run_id: int, *, candidate_id: Optional[str] = None,
    definition_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM regime_conditional_results WHERE run_id = ?"
    params: List[Any] = [run_id]
    if candidate_id is not None:
        sql += " AND candidate_id = ?"
        params.append(candidate_id)
    if definition_id is not None:
        sql += " AND definition_id = ?"
        params.append(definition_id)
    sql += " ORDER BY definition_id, candidate_id, regime_label"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [{
        "candidate_id": r["candidate_id"], "definition_id": r["definition_id"],
        "regime_label": r["regime_label"],
        "observation_count": r["observation_count"], "coverage": r["coverage"],
        "mean": r["mean"], "median": r["median"], "std": r["std"],
        "minimum": r["minimum"], "maximum": r["maximum"],
        "positive_rate": r["positive_rate"], "negative_rate": r["negative_rate"],
        "cumulative": r["cumulative"], "sharpe_like": r["sharpe_like"],
        "downside_deviation": r["downside_deviation"],
        "status": r["status"], "note": r["note"],
    } for r in rows]


# --- baselines + summary ---------------------------------------------------


def mark_baseline(run_id: int, scope: str) -> None:
    now = _now()
    with get_connection() as conn:
        conn.execute(
            "UPDATE regime_diagnostic_runs SET is_baseline = 0, updated_at = ? "
            "WHERE baseline_scope = ? AND is_baseline = 1 AND id != ?",
            (now, scope, run_id))
        conn.execute(
            "UPDATE regime_diagnostic_runs SET is_baseline = 1, updated_at = ? "
            "WHERE id = ?", (now, run_id))
        conn.commit()


def lab_summary() -> Dict[str, Any]:
    with get_connection() as conn:
        runs = int(conn.execute(
            "SELECT COUNT(*) AS c FROM regime_diagnostic_runs").fetchone()["c"])
        completed = int(conn.execute(
            "SELECT COUNT(*) AS c FROM regime_diagnostic_runs "
            "WHERE status='completed'").fetchone()["c"])
        candidates = int(conn.execute(
            "SELECT COALESCE(SUM(candidate_count), 0) AS c "
            "FROM regime_diagnostic_runs").fetchone()["c"])
        observed = int(conn.execute(
            "SELECT COALESCE(SUM(observed_regime_count), 0) AS c "
            "FROM regime_diagnostic_runs").fetchone()["c"])
        verified = int(conn.execute(
            "SELECT COUNT(*) AS c FROM regime_definitions "
            "WHERE integrity_status IN "
            "('verified_causal_rule', 'verified_from_validation_split')"
        ).fetchone()["c"])
        low_coverage = int(conn.execute(
            "SELECT COALESCE(SUM(low_coverage_warning_count), 0) AS c "
            "FROM regime_diagnostic_runs").fetchone()["c"])
        baselines = int(conn.execute(
            "SELECT COUNT(*) AS c FROM regime_diagnostic_runs "
            "WHERE is_baseline=1").fetchone()["c"])
    return {"runs": runs, "completed": completed, "candidates": candidates,
            "observed_regimes": observed, "verified_definitions": verified,
            "low_coverage_warnings": low_coverage, "baselines": baselines}


__all__ = [
    "DEFAULT_PAGE_SIZE", "MAX_PAGE_SIZE", "SORTABLE",
    "insert_run", "get_run", "run_demo_key_id", "update_run", "list_runs",
    "replace_definitions", "list_definitions",
    "replace_conditional_results", "list_conditional_results",
    "mark_baseline", "lab_summary",
]
