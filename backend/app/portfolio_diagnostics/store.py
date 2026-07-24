"""SQLite persistence for the Portfolio Diagnostics Lab (parameterised SQL only)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.db import get_connection

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
SORTABLE = frozenset({"created_at", "updated_at", "name", "status", "method",
                      "integrity_status", "solver_status"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _run_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"], "created_at": row["created_at"], "updated_at": row["updated_at"],
        "name": row["name"], "description": row["description"], "status": row["status"],
        "method": row["method"], "covariance_method": row["covariance_method"],
        "asset_count": row["asset_count"],
        "observation_count": row["observation_count"],
        "rebalance_count": row["rebalance_count"],
        "integrity_status": row["integrity_status"],
        "solver_status": row["solver_status"],
        "portfolio_volatility": row["portfolio_volatility"],
        "effective_positions": row["effective_positions"],
        "max_budget_deviation": row["max_budget_deviation"],
        "mean_turnover": row["mean_turnover"],
        "constraint_violation_count": row["constraint_violation_count"],
        "universe_fingerprint": row["universe_fingerprint"],
        "constraint_fingerprint": row["constraint_fingerprint"],
        "configuration": json.loads(row["configuration_json"]),
        "configuration_fingerprint": row["configuration_fingerprint"],
        "result_fingerprint": row["result_fingerprint"],
        "universe": json.loads(row["universe_json"]),
        "risk": (json.loads(row["risk_json"]) if row["risk_json"] else None),
        "budget": (json.loads(row["budget_json"]) if row["budget_json"] else None),
        "concentration": (json.loads(row["concentration_json"])
                          if row["concentration_json"] else None),
        "covariance": (json.loads(row["covariance_json"])
                       if row["covariance_json"] else None),
        "regimes": (json.loads(row["regimes_json"]) if row["regimes_json"] else None),
        "warnings": json.loads(row["warnings_json"]),
        "dataset_version_id": row["dataset_version_id"],
        "validation_run_id": row["validation_run_id"],
        "regime_run_id": row["regime_run_id"],
        "regime_definition_id": row["regime_definition_id"],
        "cost_diagnostic_run_id": row["cost_diagnostic_run_id"],
        "overfitting_run_id": row["overfitting_run_id"],
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
            INSERT INTO portfolio_diagnostic_runs (
                created_at, updated_at, name, description, status, method,
                covariance_method, asset_count, observation_count,
                universe_fingerprint, constraint_fingerprint,
                configuration_json, configuration_fingerprint, universe_json,
                warnings_json, dataset_version_id, validation_run_id,
                regime_run_id, regime_definition_id, cost_diagnostic_run_id,
                overfitting_run_id, experiment_id, app_version, git_commit,
                notes, demo_key
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                now, now, fields["name"], fields.get("description", ""),
                "pending", fields["method"], fields["covariance_method"],
                fields.get("asset_count", 0), fields.get("observation_count", 0),
                fields["universe_fingerprint"], fields["constraint_fingerprint"],
                json.dumps(fields.get("configuration", {})),
                fields["configuration_fingerprint"],
                json.dumps(fields.get("universe", {})),
                json.dumps(fields.get("warnings", [])),
                fields.get("dataset_version_id"), fields.get("validation_run_id"),
                fields.get("regime_run_id"), fields.get("regime_definition_id"),
                fields.get("cost_diagnostic_run_id"),
                fields.get("overfitting_run_id"), fields.get("experiment_id"),
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
            "SELECT * FROM portfolio_diagnostic_runs WHERE id = ?", (run_id,)
        ).fetchone()
    return _run_row(row) if row else None


def run_demo_key_id(demo_key: str) -> Optional[int]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM portfolio_diagnostic_runs WHERE demo_key = ?",
            (demo_key,)).fetchone()
    return int(row["id"]) if row else None


RUN_UPDATE_COLUMNS = frozenset({
    "status", "integrity_status", "solver_status", "rebalance_count",
    "portfolio_volatility", "effective_positions", "max_budget_deviation",
    "mean_turnover", "constraint_violation_count", "result_fingerprint",
    "risk_json", "budget_json", "concentration_json", "covariance_json",
    "regimes_json", "warnings_json", "is_baseline", "baseline_scope",
    "completed_at", "duration_ms", "experiment_id", "error_message", "notes",
})


def _update_run_in_connection(conn: Any, run_id: int,
                              columns: Dict[str, Any]) -> int:
    updates = {k: v for k, v in columns.items() if k in RUN_UPDATE_COLUMNS}
    if not updates:
        return 0
    set_clause = ", ".join(f"{column} = ?" for column in updates)
    cur = conn.execute(
        f"UPDATE portfolio_diagnostic_runs SET {set_clause}, updated_at = ? "
        "WHERE id = ?",
        [*updates.values(), _now(), run_id],
    )
    return int(cur.rowcount)


def update_run(run_id: int, columns: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not any(key in RUN_UPDATE_COLUMNS for key in columns):
        return get_run(run_id)
    with get_connection() as conn:
        rowcount = _update_run_in_connection(conn, run_id, columns)
        conn.commit()
    if rowcount == 0:
        return None
    return get_run(run_id)

def _where(filters: Dict[str, Any]) -> Tuple[str, List[Any]]:
    clauses: List[str] = []
    params: List[Any] = []
    for col, key in (
        ("status", "status"), ("integrity_status", "integrity_status"),
        ("solver_status", "solver_status"), ("method", "method"),
        ("covariance_method", "covariance_method"),
        ("dataset_version_id", "dataset_version_id"),
        ("validation_run_id", "validation_run_id"),
        ("regime_run_id", "regime_run_id"),
        ("cost_diagnostic_run_id", "cost_diagnostic_run_id"),
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
            f"SELECT COUNT(*) AS c FROM portfolio_diagnostic_runs{where}",
            params).fetchone()["c"])
        rows = conn.execute(
            f"SELECT * FROM portfolio_diagnostic_runs{where} "
            f"ORDER BY {sort_by} {sort_dir.upper()}, id {sort_dir.upper()} "
            f"LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size]).fetchall()
    return {"items": [_run_row(r) for r in rows], "total": total, "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total else 0}


# --- child rows (deterministic replacement) --------------------------------


def _replace_assets_in_connection(conn: Any, run_id: int,
                                  rows_in: List[Dict[str, Any]]) -> None:
    conn.execute("DELETE FROM portfolio_assets WHERE run_id = ?", (run_id,))
    for i, asset in enumerate(rows_in):
        conn.execute(
            """
            INSERT INTO portfolio_assets (
                run_id, asset_index, asset_id, name, asset_type,
                grp, currency, volatility, metadata_json
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (run_id, i, asset["asset_id"], asset["name"], asset["asset_type"],
             asset.get("group"), asset.get("currency"), asset.get("volatility"),
             json.dumps(asset.get("metadata", {}))),
        )


def replace_assets(run_id: int, rows_in: List[Dict[str, Any]]) -> None:
    with get_connection() as conn:
        _replace_assets_in_connection(conn, run_id, rows_in)
        conn.commit()

def list_assets(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM portfolio_assets WHERE run_id = ? ORDER BY asset_index",
            (run_id,)).fetchall()
    return [{
        "asset_index": r["asset_index"], "asset_id": r["asset_id"],
        "name": r["name"], "asset_type": r["asset_type"], "group": r["grp"],
        "currency": r["currency"], "volatility": r["volatility"],
        "metadata": json.loads(r["metadata_json"]),
    } for r in rows]


def _replace_rebalances_in_connection(conn: Any, run_id: int,
                                      rows_in: List[Dict[str, Any]]) -> None:
    conn.execute("DELETE FROM portfolio_rebalances WHERE run_id = ?", (run_id,))
    for row in rows_in:
        conn.execute(
            """
            INSERT INTO portfolio_rebalances (
                run_id, rebalance_id, decision_timestamp,
                effective_timestamp, window_start, window_end,
                turnover, gross_change, solver_status,
                constraint_violation_count, covariance_fingerprint,
                weight_fingerprint, weights_json, prior_weights_json,
                solver_json, violations_json, cost_json, status, reason
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (run_id, row["rebalance_id"], row["decision_timestamp"],
             row.get("effective_timestamp"), row.get("window_start"),
             row.get("window_end"), row.get("turnover"), row.get("gross_change"),
             row.get("solver", {}).get("status"),
             len(row.get("constraint_violations") or []),
             row.get("covariance_fingerprint"), row.get("weight_fingerprint"),
             json.dumps(row.get("weights")) if row.get("weights") is not None else None,
             json.dumps(row.get("prior_weights")) if row.get("prior_weights") is not None else None,
             json.dumps(row.get("solver", {})),
             json.dumps(row.get("constraint_violations") or []),
             json.dumps(row.get("cost")) if row.get("cost") is not None else None,
             row.get("status", "completed"), row.get("reason")),
        )


def replace_rebalances(run_id: int, rows_in: List[Dict[str, Any]]) -> None:
    with get_connection() as conn:
        _replace_rebalances_in_connection(conn, run_id, rows_in)
        conn.commit()

def list_rebalances(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM portfolio_rebalances WHERE run_id = ? "
            "ORDER BY rebalance_id", (run_id,)).fetchall()
    return [{
        "rebalance_id": r["rebalance_id"],
        "decision_timestamp": r["decision_timestamp"],
        "effective_timestamp": r["effective_timestamp"],
        "window_start": r["window_start"], "window_end": r["window_end"],
        "turnover": r["turnover"], "gross_change": r["gross_change"],
        "solver_status": r["solver_status"],
        "constraint_violation_count": r["constraint_violation_count"],
        "covariance_fingerprint": r["covariance_fingerprint"],
        "weight_fingerprint": r["weight_fingerprint"],
        "weights": json.loads(r["weights_json"]) if r["weights_json"] else None,
        "prior_weights": (json.loads(r["prior_weights_json"])
                          if r["prior_weights_json"] else None),
        "solver": json.loads(r["solver_json"]),
        "constraint_violations": json.loads(r["violations_json"]),
        "cost": json.loads(r["cost_json"]) if r["cost_json"] else None,
        "status": r["status"], "reason": r["reason"],
    } for r in rows]


def _replace_weight_results_in_connection(conn: Any, run_id: int,
                                          rows_in: List[Dict[str, Any]]) -> None:
    conn.execute("DELETE FROM portfolio_weight_results WHERE run_id = ?", (run_id,))
    for i, weight in enumerate(rows_in):
        conn.execute(
            """
            INSERT INTO portfolio_weight_results (
                run_id, asset_index, asset_id, raw_weight, weight,
                lower_bound, upper_bound, grp, constraint_status
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (run_id, i, weight["asset_id"], weight.get("raw_weight"),
             weight.get("weight"), weight.get("lower_bound"),
             weight.get("upper_bound"), weight.get("group"),
             weight.get("constraint_status", "ok")),
        )


def replace_weight_results(run_id: int, rows_in: List[Dict[str, Any]]) -> None:
    with get_connection() as conn:
        _replace_weight_results_in_connection(conn, run_id, rows_in)
        conn.commit()

def list_weight_results(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM portfolio_weight_results WHERE run_id = ? "
            "ORDER BY asset_index", (run_id,)).fetchall()
    return [{
        "asset_id": r["asset_id"], "raw_weight": r["raw_weight"],
        "weight": r["weight"], "lower_bound": r["lower_bound"],
        "upper_bound": r["upper_bound"], "group": r["grp"],
        "constraint_status": r["constraint_status"],
    } for r in rows]


def _replace_risk_contributions_in_connection(
        conn: Any, run_id: int, rows_in: List[Dict[str, Any]]) -> None:
    conn.execute(
        "DELETE FROM portfolio_risk_contributions WHERE run_id = ?", (run_id,))
    for i, contribution in enumerate(rows_in):
        conn.execute(
            """
            INSERT INTO portfolio_risk_contributions (
                run_id, asset_index, asset_id, weight, mcr, ccr, pcr,
                target_budget, abs_difference, signed_difference, state
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (run_id, i, contribution["asset_id"], contribution.get("weight"),
             contribution.get("mcr"), contribution.get("ccr"),
             contribution.get("pcr"), contribution.get("target_budget"),
             contribution.get("abs_difference"),
             contribution.get("signed_difference"),
             contribution.get("state", "unavailable")),
        )


def replace_risk_contributions(run_id: int, rows_in: List[Dict[str, Any]]) -> None:
    with get_connection() as conn:
        _replace_risk_contributions_in_connection(conn, run_id, rows_in)
        conn.commit()

def list_risk_contributions(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM portfolio_risk_contributions WHERE run_id = ? "
            "ORDER BY asset_index", (run_id,)).fetchall()
    return [{
        "asset_id": r["asset_id"], "weight": r["weight"], "mcr": r["mcr"],
        "ccr": r["ccr"], "pcr": r["pcr"], "target_budget": r["target_budget"],
        "abs_difference": r["abs_difference"],
        "signed_difference": r["signed_difference"], "state": r["state"],
    } for r in rows]


def _replace_sensitivity_results_in_connection(
        conn: Any, run_id: int, rows_in: List[Dict[str, Any]]) -> None:
    conn.execute(
        "DELETE FROM portfolio_sensitivity_results WHERE run_id = ?", (run_id,))
    for i, scenario in enumerate(rows_in):
        conn.execute(
            """
            INSERT INTO portfolio_sensitivity_results (
                run_id, scenario_index, dimension, value, is_base,
                portfolio_volatility, effective_positions,
                max_budget_deviation, turnover, solver_status,
                constraint_violation_count, cost_return, status, reason,
                fingerprint
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (run_id, i, scenario["dimension"],
             None if scenario.get("value") is None else float(scenario["value"]),
             1 if scenario.get("is_base") else 0,
             scenario.get("portfolio_volatility"),
             scenario.get("effective_positions"),
             scenario.get("max_budget_deviation"), scenario.get("turnover"),
             scenario.get("solver_status"),
             scenario.get("constraint_violation_count", 0),
             scenario.get("cost_return"), scenario.get("status", "completed"),
             scenario.get("reason"), scenario["fingerprint"]),
        )


def replace_sensitivity_results(run_id: int, rows_in: List[Dict[str, Any]]) -> None:
    with get_connection() as conn:
        _replace_sensitivity_results_in_connection(conn, run_id, rows_in)
        conn.commit()

def list_sensitivity_results(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM portfolio_sensitivity_results WHERE run_id = ? "
            "ORDER BY scenario_index", (run_id,)).fetchall()
    return [{
        "scenario_index": r["scenario_index"], "dimension": r["dimension"],
        "value": r["value"], "is_base": bool(r["is_base"]),
        "portfolio_volatility": r["portfolio_volatility"],
        "effective_positions": r["effective_positions"],
        "max_budget_deviation": r["max_budget_deviation"],
        "turnover": r["turnover"], "solver_status": r["solver_status"],
        "constraint_violation_count": r["constraint_violation_count"],
        "cost_return": r["cost_return"], "status": r["status"],
        "reason": r["reason"], "fingerprint": r["fingerprint"],
    } for r in rows]


def replace_execution_results(
        run_id: int, *, assets: List[Dict[str, Any]],
        rebalances: List[Dict[str, Any]], weights: List[Dict[str, Any]],
        contributions: List[Dict[str, Any]],
        sensitivity: List[Dict[str, Any]],
        run_updates: Dict[str, Any]) -> None:
    """Replace one execution snapshot atomically across parent and children."""
    with get_connection() as conn:
        _replace_assets_in_connection(conn, run_id, assets)
        _replace_rebalances_in_connection(conn, run_id, rebalances)
        _replace_weight_results_in_connection(conn, run_id, weights)
        _replace_risk_contributions_in_connection(conn, run_id, contributions)
        _replace_sensitivity_results_in_connection(conn, run_id, sensitivity)
        if _update_run_in_connection(conn, run_id, run_updates) == 0:
            raise LookupError(f"portfolio-diagnostic run {run_id} not found")
        conn.commit()

# --- baselines + summary ---------------------------------------------------


def mark_baseline(run_id: int, scope: str) -> None:
    now = _now()
    with get_connection() as conn:
        conn.execute(
            "UPDATE portfolio_diagnostic_runs SET is_baseline = 0, updated_at = ? "
            "WHERE baseline_scope = ? AND is_baseline = 1 AND id != ?",
            (now, scope, run_id))
        conn.execute(
            "UPDATE portfolio_diagnostic_runs SET is_baseline = 1, updated_at = ? "
            "WHERE id = ?", (now, run_id))
        conn.commit()


def lab_summary() -> Dict[str, Any]:
    with get_connection() as conn:
        runs = int(conn.execute(
            "SELECT COUNT(*) AS c FROM portfolio_diagnostic_runs").fetchone()["c"])
        completed = int(conn.execute(
            "SELECT COUNT(*) AS c FROM portfolio_diagnostic_runs "
            "WHERE status='completed'").fetchone()["c"])
        assets = int(conn.execute(
            "SELECT COALESCE(SUM(asset_count), 0) AS c "
            "FROM portfolio_diagnostic_runs").fetchone()["c"])
        violations = int(conn.execute(
            "SELECT COALESCE(SUM(constraint_violation_count), 0) AS c "
            "FROM portfolio_diagnostic_runs").fetchone()["c"])
        solver_failures = int(conn.execute(
            "SELECT COUNT(*) AS c FROM portfolio_diagnostic_runs "
            "WHERE solver_status='failed'").fetchone()["c"])
        baselines = int(conn.execute(
            "SELECT COUNT(*) AS c FROM portfolio_diagnostic_runs "
            "WHERE is_baseline=1").fetchone()["c"])
    return {"runs": runs, "completed": completed, "assets": assets,
            "constraint_violations": violations,
            "solver_failures": solver_failures, "baselines": baselines}


__all__ = [
    "DEFAULT_PAGE_SIZE", "MAX_PAGE_SIZE", "SORTABLE",
    "insert_run", "get_run", "run_demo_key_id", "update_run", "list_runs",
    "replace_assets", "list_assets", "replace_rebalances", "list_rebalances",
    "replace_weight_results", "list_weight_results",
    "replace_risk_contributions", "list_risk_contributions",
    "replace_sensitivity_results", "list_sensitivity_results",
    "mark_baseline", "lab_summary",
]
