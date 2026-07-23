"""SQLite persistence for the Cost Diagnostics Lab (parameterised SQL only)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.db import get_connection

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
SORTABLE = frozenset({"created_at", "updated_at", "name", "status",
                      "integrity_status", "completeness_status"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _run_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"], "created_at": row["created_at"], "updated_at": row["updated_at"],
        "name": row["name"], "description": row["description"], "status": row["status"],
        "observation_type": row["observation_type"],
        "candidate_count": row["candidate_count"],
        "observation_count": row["observation_count"],
        "currency": row["currency"],
        "integrity_status": row["integrity_status"],
        "completeness_status": row["completeness_status"],
        "gross_total": row["gross_total"], "net_total": row["net_total"],
        "total_cost": row["total_cost"],
        "participation_warning_count": row["participation_warning_count"],
        "unavailable_input_count": row["unavailable_input_count"],
        "universe_fingerprint": row["universe_fingerprint"],
        "cost_model_fingerprint": row["cost_model_fingerprint"],
        "configuration": json.loads(row["configuration_json"]),
        "configuration_fingerprint": row["configuration_fingerprint"],
        "result_fingerprint": row["result_fingerprint"],
        "observations": json.loads(row["observations_json"]),
        "aggregates": (json.loads(row["aggregates_json"])
                       if row["aggregates_json"] else None),
        "breakeven": (json.loads(row["breakeven_json"])
                      if row["breakeven_json"] else None),
        "regimes": (json.loads(row["regimes_json"])
                    if row["regimes_json"] else None),
        "warnings": json.loads(row["warnings_json"]),
        "dataset_version_id": row["dataset_version_id"],
        "validation_run_id": row["validation_run_id"],
        "overfitting_run_id": row["overfitting_run_id"],
        "regime_run_id": row["regime_run_id"],
        "regime_definition_id": row["regime_definition_id"],
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
            INSERT INTO cost_diagnostic_runs (
                created_at, updated_at, name, description, status,
                observation_type, candidate_count, observation_count, currency,
                universe_fingerprint, cost_model_fingerprint,
                configuration_json, configuration_fingerprint,
                observations_json, warnings_json,
                dataset_version_id, validation_run_id, overfitting_run_id,
                regime_run_id, regime_definition_id,
                feature_diagnostics_run_id, meta_label_run_id, experiment_id,
                app_version, git_commit, notes, demo_key
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                now, now, fields["name"], fields.get("description", ""), "pending",
                fields["observation_type"],
                fields.get("candidate_count", 0), fields.get("observation_count", 0),
                fields.get("currency"),
                fields["universe_fingerprint"], fields["cost_model_fingerprint"],
                json.dumps(fields.get("configuration", {})),
                fields["configuration_fingerprint"],
                json.dumps(fields.get("observations", [])),
                json.dumps(fields.get("warnings", [])),
                fields.get("dataset_version_id"), fields.get("validation_run_id"),
                fields.get("overfitting_run_id"), fields.get("regime_run_id"),
                fields.get("regime_definition_id"),
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
            "SELECT * FROM cost_diagnostic_runs WHERE id = ?", (run_id,)
        ).fetchone()
    return _run_row(row) if row else None


def run_demo_key_id(demo_key: str) -> Optional[int]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM cost_diagnostic_runs WHERE demo_key = ?", (demo_key,)
        ).fetchone()
    return int(row["id"]) if row else None


def update_run(run_id: int, columns: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    allowed = {
        "status", "integrity_status", "completeness_status",
        "gross_total", "net_total", "total_cost",
        "participation_warning_count", "unavailable_input_count",
        "result_fingerprint", "aggregates_json", "breakeven_json",
        "regimes_json", "warnings_json",
        "is_baseline", "baseline_scope", "completed_at", "duration_ms",
        "experiment_id", "error_message", "notes",
    }
    updates = {k: v for k, v in columns.items() if k in allowed}
    if not updates:
        return get_run(run_id)
    set_clause = ", ".join(f"{c} = ?" for c in updates)
    with get_connection() as conn:
        cur = conn.execute(
            f"UPDATE cost_diagnostic_runs SET {set_clause}, updated_at = ? WHERE id = ?",
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
        ("observation_type", "observation_type"),
        ("dataset_version_id", "dataset_version_id"),
        ("validation_run_id", "validation_run_id"),
        ("overfitting_run_id", "overfitting_run_id"),
        ("regime_run_id", "regime_run_id"),
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
            f"SELECT COUNT(*) AS c FROM cost_diagnostic_runs{where}",
            params).fetchone()["c"])
        rows = conn.execute(
            f"SELECT * FROM cost_diagnostic_runs{where} "
            f"ORDER BY {sort_by} {sort_dir.upper()}, id {sort_dir.upper()} "
            f"LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size]).fetchall()
    return {"items": [_run_row(r) for r in rows], "total": total, "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total else 0}


# --- cost model (one row per run) ------------------------------------------


def replace_cost_model(run_id: int, model: Dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM cost_models WHERE run_id = ?", (run_id,))
        conn.execute(
            """
            INSERT INTO cost_models (
                run_id, commission_json, spread_json, slippage_json,
                impact_json, liquidity_policy_json, fingerprint, created_at
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (run_id, json.dumps(model["commission"]), json.dumps(model["spread"]),
             json.dumps(model["slippage"]), json.dumps(model["impact"]),
             json.dumps(model["liquidity_policy"]), model["fingerprint"], _now()),
        )
        conn.commit()


def get_cost_model(run_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM cost_models WHERE run_id = ?", (run_id,)).fetchone()
    if not row:
        return None
    return {
        "commission": json.loads(row["commission_json"]),
        "spread": json.loads(row["spread_json"]),
        "slippage": json.loads(row["slippage_json"]),
        "impact": json.loads(row["impact_json"]),
        "liquidity_policy": json.loads(row["liquidity_policy_json"]),
        "fingerprint": row["fingerprint"],
    }


# --- per-observation results -----------------------------------------------


def _observation_row(r) -> Dict[str, Any]:
    return {
        "observation_id": r["observation_id"], "candidate_id": r["candidate_id"],
        "timestamp": r["timestamp"], "side": r["side"],
        "quantity": r["quantity"], "traded_notional": r["traded_notional"],
        "turnover": r["turnover"],
        "gross_value": r["gross_value"], "gross_return": r["gross_return"],
        "commission_cost": r["commission_cost"], "spread_cost": r["spread_cost"],
        "slippage_cost": r["slippage_cost"], "impact_cost": r["impact_cost"],
        "total_cost": r["total_cost"], "net_value": r["net_value"],
        "net_return": r["net_return"], "completeness": r["completeness"],
        "participation": r["participation"],
        "participation_status": r["participation_status"],
        "breakeven_bps": r["breakeven_bps"],
        "regime_label": r["regime_label"],
        "unavailable_components": json.loads(r["unavailable_json"]),
        "warnings": json.loads(r["warnings_json"]),
    }


def replace_observation_results(run_id: int, rows_in: List[Dict[str, Any]]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM cost_observation_results WHERE run_id = ?", (run_id,))
        for r in rows_in:
            comp = r["component_values"]
            conn.execute(
                """
                INSERT INTO cost_observation_results (
                    run_id, observation_id, candidate_id, timestamp, side,
                    quantity, traded_notional, turnover, gross_value,
                    gross_return, commission_cost, spread_cost, slippage_cost,
                    impact_cost, total_cost, net_value, net_return,
                    completeness, participation, participation_status,
                    breakeven_bps, regime_label, unavailable_json, warnings_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (run_id, r["observation_id"], r["candidate_id"], r["timestamp"],
                 r.get("side"), r.get("quantity"), r.get("traded_notional"),
                 r.get("turnover"), r["gross_value"], r.get("gross_return"),
                 comp.get("commission"), comp.get("spread"),
                 comp.get("slippage"), comp.get("impact"),
                 r["total_cost"], r["net_value"], r.get("net_return"),
                 r["completeness"], r.get("participation"),
                 r.get("participation_status"), r.get("breakeven_bps"),
                 r.get("regime_label"),
                 json.dumps(r.get("unavailable_components", [])),
                 json.dumps(r.get("warnings", []))),
            )
        conn.commit()


def list_observation_results(
    run_id: int, *, candidate_id: Optional[str] = None,
    completeness: Optional[str] = None,
    page: int = 1, page_size: int = DEFAULT_PAGE_SIZE,
) -> Dict[str, Any]:
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), MAX_PAGE_SIZE))
    sql = "FROM cost_observation_results WHERE run_id = ?"
    params: List[Any] = [run_id]
    if candidate_id is not None:
        sql += " AND candidate_id = ?"
        params.append(candidate_id)
    if completeness is not None:
        sql += " AND completeness = ?"
        params.append(completeness)
    with get_connection() as conn:
        total = int(conn.execute(
            f"SELECT COUNT(*) AS c {sql}", params).fetchone()["c"])
        rows = conn.execute(
            f"SELECT * {sql} ORDER BY timestamp, observation_id LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size]).fetchall()
    return {"items": [_observation_row(r) for r in rows], "total": total,
            "page": page, "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total else 0}


# --- sensitivity + capacity results ----------------------------------------


def replace_sensitivity_results(run_id: int, rows_in: List[Dict[str, Any]]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM cost_sensitivity_results WHERE run_id = ?", (run_id,))
        for i, r in enumerate(rows_in):
            conn.execute(
                """
                INSERT INTO cost_sensitivity_results (
                    run_id, scenario_index, is_base, commission_multiplier,
                    spread_multiplier, slippage_multiplier, impact_multiplier,
                    total_cost, net_total, net_positive_rate,
                    gross_positive_net_nonpositive_count,
                    unavailable_cost_count, fingerprint
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (run_id, i, 1 if r["is_base"] else 0,
                 r["commission_multiplier"], r["spread_multiplier"],
                 r["slippage_multiplier"], r["impact_multiplier"],
                 r["total_cost"], r["net_total"], r["net_positive_rate"],
                 r["gross_positive_net_nonpositive_count"],
                 r["unavailable_cost_count"], r["fingerprint"]),
            )
        conn.commit()


def list_sensitivity_results(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM cost_sensitivity_results WHERE run_id = ? "
            "ORDER BY scenario_index", (run_id,)).fetchall()
    return [{
        "scenario_index": r["scenario_index"], "is_base": bool(r["is_base"]),
        "commission_multiplier": r["commission_multiplier"],
        "spread_multiplier": r["spread_multiplier"],
        "slippage_multiplier": r["slippage_multiplier"],
        "impact_multiplier": r["impact_multiplier"],
        "total_cost": r["total_cost"], "net_total": r["net_total"],
        "net_positive_rate": r["net_positive_rate"],
        "gross_positive_net_nonpositive_count":
            r["gross_positive_net_nonpositive_count"],
        "unavailable_cost_count": r["unavailable_cost_count"],
        "fingerprint": r["fingerprint"],
    } for r in rows]


def replace_capacity_results(run_id: int, rows_in: List[Dict[str, Any]]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM cost_capacity_results WHERE run_id = ?", (run_id,))
        for r in rows_in:
            conn.execute(
                """
                INSERT INTO cost_capacity_results (
                    run_id, scale, is_base, traded_notional,
                    mean_participation, max_participation,
                    above_threshold_count, commission_total, spread_total,
                    slippage_total, impact_total, total_cost, gross_total,
                    net_total, unavailable_liquidity_count, excluded_count
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (run_id, r["scale"], 1 if r["is_base"] else 0,
                 r["traded_notional"], r["mean_participation"],
                 r["max_participation"], r["above_threshold_count"],
                 r["commission_total"], r["spread_total"], r["slippage_total"],
                 r["impact_total"], r["total_cost"], r["gross_total"],
                 r["net_total"], r["unavailable_liquidity_count"],
                 r["excluded_count"]),
            )
        conn.commit()


def list_capacity_results(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM cost_capacity_results WHERE run_id = ? "
            "ORDER BY scale", (run_id,)).fetchall()
    return [{
        "scale": r["scale"], "is_base": bool(r["is_base"]),
        "traded_notional": r["traded_notional"],
        "mean_participation": r["mean_participation"],
        "max_participation": r["max_participation"],
        "above_threshold_count": r["above_threshold_count"],
        "commission_total": r["commission_total"],
        "spread_total": r["spread_total"],
        "slippage_total": r["slippage_total"],
        "impact_total": r["impact_total"],
        "total_cost": r["total_cost"], "gross_total": r["gross_total"],
        "net_total": r["net_total"],
        "unavailable_liquidity_count": r["unavailable_liquidity_count"],
        "excluded_count": r["excluded_count"],
    } for r in rows]


# --- baselines + summary ---------------------------------------------------


def mark_baseline(run_id: int, scope: str) -> None:
    now = _now()
    with get_connection() as conn:
        conn.execute(
            "UPDATE cost_diagnostic_runs SET is_baseline = 0, updated_at = ? "
            "WHERE baseline_scope = ? AND is_baseline = 1 AND id != ?",
            (now, scope, run_id))
        conn.execute(
            "UPDATE cost_diagnostic_runs SET is_baseline = 1, updated_at = ? "
            "WHERE id = ?", (now, run_id))
        conn.commit()


def lab_summary() -> Dict[str, Any]:
    with get_connection() as conn:
        runs = int(conn.execute(
            "SELECT COUNT(*) AS c FROM cost_diagnostic_runs").fetchone()["c"])
        completed = int(conn.execute(
            "SELECT COUNT(*) AS c FROM cost_diagnostic_runs "
            "WHERE status='completed'").fetchone()["c"])
        observations = int(conn.execute(
            "SELECT COALESCE(SUM(observation_count), 0) AS c "
            "FROM cost_diagnostic_runs").fetchone()["c"])
        participation_warnings = int(conn.execute(
            "SELECT COALESCE(SUM(participation_warning_count), 0) AS c "
            "FROM cost_diagnostic_runs").fetchone()["c"])
        incomplete = int(conn.execute(
            "SELECT COALESCE(SUM(unavailable_input_count), 0) AS c "
            "FROM cost_diagnostic_runs").fetchone()["c"])
        baselines = int(conn.execute(
            "SELECT COUNT(*) AS c FROM cost_diagnostic_runs "
            "WHERE is_baseline=1").fetchone()["c"])
    return {"runs": runs, "completed": completed,
            "observations": observations,
            "participation_warnings": participation_warnings,
            "incomplete_input_observations": incomplete,
            "baselines": baselines}


__all__ = [
    "DEFAULT_PAGE_SIZE", "MAX_PAGE_SIZE", "SORTABLE",
    "insert_run", "get_run", "run_demo_key_id", "update_run", "list_runs",
    "replace_cost_model", "get_cost_model",
    "replace_observation_results", "list_observation_results",
    "replace_sensitivity_results", "list_sensitivity_results",
    "replace_capacity_results", "list_capacity_results",
    "mark_baseline", "lab_summary",
]
