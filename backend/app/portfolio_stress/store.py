"""SQLite persistence for the Portfolio Stress Lab (parameterised SQL only)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.db import get_connection

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
SORTABLE = frozenset({"created_at", "updated_at", "name", "status",
                      "scenario_type", "integrity_status",
                      "completeness_status"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _run_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"], "created_at": row["created_at"], "updated_at": row["updated_at"],
        "name": row["name"], "description": row["description"], "status": row["status"],
        "scenario_type": row["scenario_type"],
        "asset_count": row["asset_count"],
        "scenario_count": row["scenario_count"],
        "integrity_status": row["integrity_status"],
        "completeness_status": row["completeness_status"],
        "scenario_return": row["scenario_return"],
        "scenario_pnl": row["scenario_pnl"],
        "stressed_volatility": row["stressed_volatility"],
        "baseline_volatility": row["baseline_volatility"],
        "breach_count": row["breach_count"],
        "episode_count": row["episode_count"],
        "max_drawdown": row["max_drawdown"],
        "configuration": json.loads(row["configuration_json"]),
        "configuration_fingerprint": row["configuration_fingerprint"],
        "result_fingerprint": row["result_fingerprint"],
        "scenario_fingerprint": row["scenario_fingerprint"],
        "baseline_weight_fingerprint": row["baseline_weight_fingerprint"],
        "baseline_covariance_fingerprint": row["baseline_covariance_fingerprint"],
        "stressed_covariance_fingerprint": row["stressed_covariance_fingerprint"],
        "reconciliation": (json.loads(row["reconciliation_json"])
                           if row["reconciliation_json"] else None),
        "risk_summary": (json.loads(row["risk_summary_json"])
                         if row["risk_summary_json"] else None),
        "cost_stress": (json.loads(row["cost_stress_json"])
                        if row["cost_stress_json"] else None),
        "drawdown": (json.loads(row["drawdown_json"])
                     if row["drawdown_json"] else None),
        "covariance_stress": (json.loads(row["covariance_stress_json"])
                              if row["covariance_stress_json"] else None),
        "drifted": (json.loads(row["drifted_json"])
                    if row["drifted_json"] else None),
        "warnings": json.loads(row["warnings_json"]),
        "portfolio_run_id": row["portfolio_run_id"],
        "portfolio_rebalance_id": row["portfolio_rebalance_id"],
        "dataset_version_id": row["dataset_version_id"],
        "regime_run_id": row["regime_run_id"],
        "cost_diagnostic_run_id": row["cost_diagnostic_run_id"],
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
            INSERT INTO portfolio_stress_runs (
                created_at, updated_at, name, description, status,
                scenario_type, integrity_status, asset_count, scenario_count,
                configuration_json, configuration_fingerprint,
                scenario_fingerprint, baseline_weight_fingerprint,
                baseline_covariance_fingerprint, warnings_json,
                portfolio_run_id, portfolio_rebalance_id, dataset_version_id,
                regime_run_id, cost_diagnostic_run_id, experiment_id,
                app_version, git_commit, notes, demo_key
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                now, now, fields["name"], fields.get("description", ""),
                "pending", fields["scenario_type"],
                fields.get("integrity_status", "unknown"),
                fields.get("asset_count", 0), fields.get("scenario_count", 0),
                json.dumps(fields.get("configuration", {})),
                fields["configuration_fingerprint"],
                fields["scenario_fingerprint"],
                fields.get("baseline_weight_fingerprint"),
                fields.get("baseline_covariance_fingerprint"),
                json.dumps(fields.get("warnings", [])),
                fields["portfolio_run_id"],
                fields.get("portfolio_rebalance_id"),
                fields.get("dataset_version_id"), fields.get("regime_run_id"),
                fields.get("cost_diagnostic_run_id"),
                fields.get("experiment_id"),
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
            "SELECT * FROM portfolio_stress_runs WHERE id = ?", (run_id,)
        ).fetchone()
    return _run_row(row) if row else None


def run_demo_key_id(demo_key: str) -> Optional[int]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM portfolio_stress_runs WHERE demo_key = ?",
            (demo_key,)).fetchone()
    return int(row["id"]) if row else None


RUN_UPDATE_COLUMNS = {
    "status", "integrity_status", "completeness_status", "scenario_count",
    "scenario_return", "scenario_pnl", "stressed_volatility",
    "baseline_volatility", "breach_count", "episode_count", "max_drawdown",
    "result_fingerprint", "stressed_covariance_fingerprint",
    "reconciliation_json", "risk_summary_json", "cost_stress_json",
    "drawdown_json", "covariance_stress_json", "drifted_json",
    "warnings_json", "is_baseline", "baseline_scope", "completed_at",
    "duration_ms", "experiment_id", "error_message", "notes",
}


def update_run(run_id: int, columns: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    updates = {k: v for k, v in columns.items() if k in RUN_UPDATE_COLUMNS}
    if not updates:
        return get_run(run_id)
    set_clause = ", ".join(f"{c} = ?" for c in updates)
    with get_connection() as conn:
        cur = conn.execute(
            f"UPDATE portfolio_stress_runs SET {set_clause}, updated_at = ? WHERE id = ?",
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
        ("completeness_status", "completeness_status"),
        ("scenario_type", "scenario_type"),
        ("portfolio_run_id", "portfolio_run_id"),
        ("dataset_version_id", "dataset_version_id"),
        ("regime_run_id", "regime_run_id"),
        ("cost_diagnostic_run_id", "cost_diagnostic_run_id"),
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
            f"SELECT COUNT(*) AS c FROM portfolio_stress_runs{where}",
            params).fetchone()["c"])
        rows = conn.execute(
            f"SELECT * FROM portfolio_stress_runs{where} "
            f"ORDER BY {sort_by} {sort_dir.upper()}, id {sort_dir.upper()} "
            f"LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size]).fetchall()
    return {"items": [_run_row(r) for r in rows], "total": total, "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total else 0}


# --- child rows (deterministic replacement, one transaction) ---------------


def replace_children(run_id: int, *, scenario: Dict[str, Any],
                     asset_rows: List[Dict[str, Any]],
                     risk_rows: List[Dict[str, Any]],
                     constraint_rows: List[Dict[str, Any]],
                     episodes: List[Dict[str, Any]],
                     attribution_rows: List[Dict[str, Any]],
                     sensitivity_rows: List[Dict[str, Any]],
                     run_updates: Dict[str, Any]) -> None:
    """Atomic replacement of every child table + the parent columns."""
    updates = {k: v for k, v in run_updates.items() if k in RUN_UPDATE_COLUMNS}
    set_clause = ", ".join(f"{c} = ?" for c in updates)
    with get_connection() as conn:
        try:
            conn.execute("BEGIN")
            for table in ("stress_scenario_definitions", "stress_asset_results",
                          "stress_risk_results", "stress_constraint_results",
                          "drawdown_episodes", "drawdown_attribution_results",
                          "stress_sensitivity_results"):
                conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))
            conn.execute(
                """
                INSERT INTO stress_scenario_definitions (
                    run_id, scenario_definition_id, name, description,
                    scenario_type, source, integrity_status, fingerprint,
                    definition_json
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (run_id, scenario["scenario_definition_id"], scenario["name"],
                 scenario["description"], scenario["scenario_type"],
                 scenario["source"], scenario["integrity"],
                 scenario["fingerprint"], json.dumps(scenario["definition"])))
            for i, r in enumerate(asset_rows):
                conn.execute(
                    """
                    INSERT INTO stress_asset_results (
                        run_id, asset_index, asset_id, grp, weight, shock,
                        shock_source, contribution, abs_share,
                        drifted_weight, status
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, i, r["asset_id"], r.get("group"), r.get("weight"),
                     r.get("shock"), r.get("shock_source"),
                     r.get("contribution"), r.get("abs_share"),
                     r.get("drifted_weight"),
                     r.get("status", "ok")))
            for i, r in enumerate(risk_rows):
                conn.execute(
                    """
                    INSERT INTO stress_risk_results (
                        run_id, asset_index, asset_id, baseline_mcr,
                        baseline_ccr, baseline_pcr, stressed_mcr,
                        stressed_ccr, stressed_pcr, pcr_change,
                        rank_change, state
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, i, r["asset_id"], r.get("baseline_mcr"),
                     r.get("baseline_ccr"), r.get("baseline_pcr"),
                     r.get("stressed_mcr"), r.get("stressed_ccr"),
                     r.get("stressed_pcr"), r.get("pcr_change"),
                     r.get("rank_change"), r.get("state", "available")))
            for i, r in enumerate(constraint_rows):
                conn.execute(
                    """
                    INSERT INTO stress_constraint_results (
                        run_id, row_index, book, constraint_name, detail,
                        amount, asset_id
                    ) VALUES (?,?,?,?,?,?,?)
                    """,
                    (run_id, i, r["book"], r["constraint"], r["detail"],
                     r.get("amount"), r.get("asset_id")))
            for e in episodes:
                conn.execute(
                    """
                    INSERT INTO drawdown_episodes (
                        run_id, episode_id, peak_timestamp,
                        peak_is_initial_capital, trough_timestamp,
                        recovery_timestamp, depth, duration,
                        recovery_duration, status
                    ) VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, e["episode_id"], e["peak_timestamp"],
                     1 if e.get("peak_is_initial_capital") else 0,
                     e["trough_timestamp"], e.get("recovery_timestamp"),
                     e["depth"], e["duration"], e.get("recovery_duration"),
                     e["status"]))
            for i, r in enumerate(attribution_rows):
                conn.execute(
                    """
                    INSERT INTO drawdown_attribution_results (
                        run_id, asset_index, asset_id, grp, episode_id,
                        contribution, average_weight, abs_share
                    ) VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (run_id, i, r["asset_id"], r.get("group"),
                     r.get("episode_id"), r.get("contribution"),
                     r.get("average_weight"), r.get("abs_share")))
            for i, s in enumerate(sensitivity_rows):
                conn.execute(
                    """
                    INSERT INTO stress_sensitivity_results (
                        run_id, scenario_index, dimension, value, is_base,
                        scenario_return, stressed_volatility,
                        contribution_hhi, breach_count, cost_return,
                        completeness, status, reason, fingerprint
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, i, s["dimension"],
                     None if s.get("value") is None else float(s["value"]),
                     1 if s.get("is_base") else 0,
                     s.get("scenario_return"), s.get("stressed_volatility"),
                     s.get("contribution_hhi"), s.get("breach_count"),
                     s.get("cost_return"), s.get("completeness"),
                     s.get("status", "completed"), s.get("reason"),
                     s["fingerprint"]))
            if updates:
                conn.execute(
                    f"UPDATE portfolio_stress_runs SET {set_clause}, "
                    "updated_at = ? WHERE id = ?",
                    [*updates.values(), _now(), run_id])
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def clear_results(run_id: int) -> None:
    """Remove every derived result from a run (used when execution fails,
    so a failed run never exposes stale numbers from a prior execution)."""
    with get_connection() as conn:
        try:
            conn.execute("BEGIN")
            for table in ("stress_scenario_definitions", "stress_asset_results",
                          "stress_risk_results", "stress_constraint_results",
                          "drawdown_episodes", "drawdown_attribution_results",
                          "stress_sensitivity_results"):
                conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))
            conn.execute(
                """
                UPDATE portfolio_stress_runs SET
                    completeness_status = 'unavailable', scenario_return = NULL,
                    scenario_pnl = NULL, stressed_volatility = NULL,
                    baseline_volatility = NULL, breach_count = 0,
                    episode_count = 0, max_drawdown = NULL,
                    scenario_count = 0, warnings_json = '[]',
                    result_fingerprint = NULL,
                    stressed_covariance_fingerprint = NULL,
                    reconciliation_json = NULL, risk_summary_json = NULL,
                    cost_stress_json = NULL, drawdown_json = NULL,
                    covariance_stress_json = NULL, drifted_json = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (_now(), run_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def fail_execution(run_id: int, error_message: str,
                   completed_at: str) -> None:
    """Atomically clear stale children and mark the parent failed."""
    with get_connection() as conn:
        try:
            conn.execute("BEGIN")
            for table in ("stress_scenario_definitions", "stress_asset_results",
                          "stress_risk_results", "stress_constraint_results",
                          "drawdown_episodes", "drawdown_attribution_results",
                          "stress_sensitivity_results"):
                conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))
            conn.execute(
                """
                UPDATE portfolio_stress_runs SET
                    status = 'failed', error_message = ?, is_baseline = 0,
                    completed_at = ?, duration_ms = NULL,
                    completeness_status = 'unavailable', scenario_return = NULL,
                    scenario_pnl = NULL, stressed_volatility = NULL,
                    baseline_volatility = NULL, breach_count = 0,
                    episode_count = 0, max_drawdown = NULL,
                    scenario_count = 0, warnings_json = '[]',
                    result_fingerprint = NULL,
                    stressed_covariance_fingerprint = NULL,
                    reconciliation_json = NULL, risk_summary_json = NULL,
                    cost_stress_json = NULL, drawdown_json = NULL,
                    covariance_stress_json = NULL, drifted_json = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (error_message, completed_at, _now(), run_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def get_scenario(run_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM stress_scenario_definitions WHERE run_id = ?",
            (run_id,)).fetchone()
    if not row:
        return None
    return {"scenario_definition_id": row["scenario_definition_id"],
            "name": row["name"], "description": row["description"],
            "scenario_type": row["scenario_type"], "source": row["source"],
            "integrity_status": row["integrity_status"],
            "fingerprint": row["fingerprint"],
            "definition": json.loads(row["definition_json"])}


def list_asset_results(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM stress_asset_results WHERE run_id = ? "
            "ORDER BY asset_index", (run_id,)).fetchall()
    return [{"asset_id": r["asset_id"], "group": r["grp"],
             "weight": r["weight"], "shock": r["shock"],
             "shock_source": r["shock_source"],
             "contribution": r["contribution"], "abs_share": r["abs_share"],
             "drifted_weight": r["drifted_weight"], "status": r["status"]}
            for r in rows]


def list_risk_results(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM stress_risk_results WHERE run_id = ? "
            "ORDER BY asset_index", (run_id,)).fetchall()
    return [{"asset_id": r["asset_id"],
             "baseline_mcr": r["baseline_mcr"], "baseline_ccr": r["baseline_ccr"],
             "baseline_pcr": r["baseline_pcr"],
             "stressed_mcr": r["stressed_mcr"], "stressed_ccr": r["stressed_ccr"],
             "stressed_pcr": r["stressed_pcr"], "pcr_change": r["pcr_change"],
             "rank_change": r["rank_change"], "state": r["state"]}
            for r in rows]


def list_constraint_results(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM stress_constraint_results WHERE run_id = ? "
            "ORDER BY row_index", (run_id,)).fetchall()
    return [{"book": r["book"], "constraint": r["constraint_name"],
             "detail": r["detail"], "amount": r["amount"],
             "asset_id": r["asset_id"]} for r in rows]


def list_episodes(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM drawdown_episodes WHERE run_id = ? "
            "ORDER BY episode_id", (run_id,)).fetchall()
    return [{"episode_id": r["episode_id"],
             "peak_timestamp": r["peak_timestamp"],
             "peak_is_initial_capital": bool(r["peak_is_initial_capital"]),
             "trough_timestamp": r["trough_timestamp"],
             "recovery_timestamp": r["recovery_timestamp"],
             "depth": r["depth"], "duration": r["duration"],
             "recovery_duration": r["recovery_duration"],
             "status": r["status"]} for r in rows]


def list_attribution(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM drawdown_attribution_results WHERE run_id = ? "
            "ORDER BY asset_index", (run_id,)).fetchall()
    return [{"asset_id": r["asset_id"], "group": r["grp"],
             "episode_id": r["episode_id"], "contribution": r["contribution"],
             "average_weight": r["average_weight"],
             "abs_share": r["abs_share"]} for r in rows]


def list_sensitivity_results(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM stress_sensitivity_results WHERE run_id = ? "
            "ORDER BY scenario_index", (run_id,)).fetchall()
    return [{"scenario_index": r["scenario_index"],
             "dimension": r["dimension"], "value": r["value"],
             "is_base": bool(r["is_base"]),
             "scenario_return": r["scenario_return"],
             "stressed_volatility": r["stressed_volatility"],
             "contribution_hhi": r["contribution_hhi"],
             "breach_count": r["breach_count"],
             "cost_return": r["cost_return"],
             "completeness": r["completeness"], "status": r["status"],
             "reason": r["reason"], "fingerprint": r["fingerprint"]}
            for r in rows]


def mark_baseline(run_id: int, scope: str) -> None:
    now = _now()
    with get_connection() as conn:
        try:
            conn.execute("BEGIN")
            conn.execute(
                "UPDATE portfolio_stress_runs SET is_baseline = 0, updated_at = ? "
                "WHERE baseline_scope = ? AND is_baseline = 1 AND id != ?",
                (now, scope, run_id))
            conn.execute(
                "UPDATE portfolio_stress_runs SET baseline_scope = ?, "
                "is_baseline = 1, updated_at = ? WHERE id = ?",
                (scope, now, run_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def lab_summary() -> Dict[str, Any]:
    with get_connection() as conn:
        runs = int(conn.execute(
            "SELECT COUNT(*) AS c FROM portfolio_stress_runs").fetchone()["c"])
        completed = int(conn.execute(
            "SELECT COUNT(*) AS c FROM portfolio_stress_runs "
            "WHERE status='completed'").fetchone()["c"])
        scenarios = int(conn.execute(
            "SELECT COALESCE(SUM(scenario_count), 0) AS c "
            "FROM portfolio_stress_runs").fetchone()["c"])
        breaches = int(conn.execute(
            "SELECT COALESCE(SUM(breach_count), 0) AS c "
            "FROM portfolio_stress_runs").fetchone()["c"])
        episodes = int(conn.execute(
            "SELECT COALESCE(SUM(episode_count), 0) AS c "
            "FROM portfolio_stress_runs").fetchone()["c"])
        baselines = int(conn.execute(
            "SELECT COUNT(*) AS c FROM portfolio_stress_runs "
            "WHERE is_baseline=1").fetchone()["c"])
    return {"runs": runs, "completed": completed, "scenarios": scenarios,
            "constraint_breaches": breaches, "drawdown_episodes": episodes,
            "baselines": baselines}


__all__ = [
    "DEFAULT_PAGE_SIZE", "MAX_PAGE_SIZE", "SORTABLE", "RUN_UPDATE_COLUMNS",
    "insert_run", "get_run", "run_demo_key_id", "update_run", "list_runs",
    "replace_children", "get_scenario", "list_asset_results",
    "list_risk_results", "list_constraint_results", "list_episodes",
    "list_attribution", "list_sensitivity_results", "fail_execution", "mark_baseline",
    "lab_summary",
]
