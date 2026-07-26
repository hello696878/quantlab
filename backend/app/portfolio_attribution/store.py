"""SQLite persistence for the Portfolio Attribution Lab (parameterised SQL)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.db import get_connection

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
SORTABLE = frozenset({"created_at", "updated_at", "name", "status",
                      "attribution_method", "integrity_status",
                      "completeness_status", "reconciliation_status",
                      "period_count"})

CHILD_TABLES = ("attribution_benchmarks", "attribution_period_results",
                "attribution_asset_results", "attribution_group_results",
                "attribution_brinson_results", "attribution_regime_results",
                "attribution_drawdown_results")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _json(value: Optional[str]) -> Any:
    return json.loads(value) if value else None


def _run_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"], "created_at": row["created_at"],
        "updated_at": row["updated_at"], "name": row["name"],
        "description": row["description"], "status": row["status"],
        "attribution_method": row["attribution_method"],
        "brinson_variant": row["brinson_variant"],
        "linking_method": row["linking_method"],
        "return_convention": row["return_convention"],
        "return_frequency": row["return_frequency"],
        "weight_timing_policy": row["weight_timing_policy"],
        "benchmark_timing_policy": row["benchmark_timing_policy"],
        "observation_start": row["observation_start"],
        "observation_end": row["observation_end"],
        "asset_count": row["asset_count"], "group_count": row["group_count"],
        "period_count": row["period_count"],
        "integrity_status": row["integrity_status"],
        "completeness_status": row["completeness_status"],
        "reconciliation_status": row["reconciliation_status"],
        "portfolio_market_return": row["portfolio_market_return"],
        "portfolio_net_return": row["portfolio_net_return"],
        "benchmark_return": row["benchmark_return"],
        "active_return": row["active_return"],
        "total_cost_return": row["total_cost_return"],
        "tracking_error": row["tracking_error"],
        "information_ratio": row["information_ratio"],
        "configuration": json.loads(row["configuration_json"]),
        "observation_fingerprint": row["observation_fingerprint"],
        "policy_fingerprint": row["policy_fingerprint"],
        "configuration_fingerprint": row["configuration_fingerprint"],
        "result_fingerprint": row["result_fingerprint"],
        "summary": _json(row["summary_json"]),
        "linking": _json(row["linking_json"]),
        "cost": _json(row["cost_json"]),
        "active_risk": _json(row["active_risk_json"]),
        "concentration": _json(row["concentration_json"]),
        "warnings": json.loads(row["warnings_json"]),
        "portfolio_run_id": row["portfolio_run_id"],
        "dataset_version_id": row["dataset_version_id"],
        "cost_diagnostic_run_id": row["cost_diagnostic_run_id"],
        "regime_run_id": row["regime_run_id"],
        "regime_definition_id": row["regime_definition_id"],
        "stress_run_id": row["stress_run_id"],
        "validation_run_id": row["validation_run_id"],
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
            INSERT INTO portfolio_attribution_runs (
                created_at, updated_at, name, description, status,
                attribution_method, brinson_variant, linking_method,
                return_convention, return_frequency, weight_timing_policy,
                benchmark_timing_policy, observation_start, observation_end,
                asset_count, group_count, period_count, integrity_status,
                configuration_json, observation_fingerprint,
                policy_fingerprint, configuration_fingerprint, warnings_json,
                portfolio_run_id, dataset_version_id, cost_diagnostic_run_id,
                regime_run_id, regime_definition_id, stress_run_id,
                validation_run_id, experiment_id, app_version, git_commit,
                notes, demo_key
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                now, now, fields["name"], fields.get("description", ""),
                "pending", fields["attribution_method"],
                fields.get("brinson_variant"), fields["linking_method"],
                fields["return_convention"], fields["return_frequency"],
                fields["weight_timing_policy"],
                fields["benchmark_timing_policy"],
                fields.get("observation_start"), fields.get("observation_end"),
                fields.get("asset_count", 0), fields.get("group_count", 0),
                fields.get("period_count", 0),
                fields.get("integrity_status", "unknown"),
                json.dumps(fields.get("configuration", {})),
                fields["observation_fingerprint"],
                fields["policy_fingerprint"],
                fields["configuration_fingerprint"],
                json.dumps(fields.get("warnings", [])),
                fields["portfolio_run_id"], fields.get("dataset_version_id"),
                fields.get("cost_diagnostic_run_id"),
                fields.get("regime_run_id"), fields.get("regime_definition_id"),
                fields.get("stress_run_id"), fields.get("validation_run_id"),
                fields.get("experiment_id"), fields.get("app_version"),
                fields.get("git_commit"), fields.get("notes", ""),
                fields.get("demo_key"),
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
            "SELECT * FROM portfolio_attribution_runs WHERE id = ?",
            (run_id,)).fetchone()
    return _run_row(row) if row else None


def run_demo_key_id(demo_key: str) -> Optional[int]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM portfolio_attribution_runs WHERE demo_key = ?",
            (demo_key,)).fetchone()
    return int(row["id"]) if row else None


RUN_UPDATE_COLUMNS = {
    "status", "integrity_status", "completeness_status",
    "reconciliation_status", "observation_start", "observation_end",
    "asset_count", "group_count", "period_count",
    "portfolio_market_return", "portfolio_net_return", "benchmark_return",
    "active_return", "total_cost_return", "tracking_error",
    "information_ratio", "result_fingerprint", "summary_json",
    "linking_json", "cost_json", "active_risk_json", "concentration_json",
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
            f"UPDATE portfolio_attribution_runs SET {set_clause}, "
            "updated_at = ? WHERE id = ?",
            [*updates.values(), _now(), run_id])
        conn.commit()
        if cur.rowcount == 0:
            return None
    return get_run(run_id)


def _where(filters: Dict[str, Any]) -> Tuple[str, List[Any]]:
    clauses: List[str] = []
    params: List[Any] = []
    for col in ("status", "integrity_status", "completeness_status",
                "reconciliation_status", "attribution_method",
                "linking_method", "portfolio_run_id", "dataset_version_id",
                "regime_run_id", "cost_diagnostic_run_id",
                "configuration_fingerprint", "is_baseline"):
        if filters.get(col) is not None:
            clauses.append(f"{col} = ?")
            params.append(filters[col])
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
            f"SELECT COUNT(*) AS c FROM portfolio_attribution_runs{where}",
            params).fetchone()["c"])
        rows = conn.execute(
            f"SELECT * FROM portfolio_attribution_runs{where} "
            f"ORDER BY {sort_by} {sort_dir.upper()}, id {sort_dir.upper()} "
            "LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size]).fetchall()
    return {"items": [_run_row(r) for r in rows], "total": total, "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total else 0}


def replace_children(run_id: int, *, benchmark: Optional[Dict[str, Any]],
                     period_rows: List[Dict[str, Any]],
                     asset_rows: List[Dict[str, Any]],
                     group_rows: List[Dict[str, Any]],
                     brinson_rows: List[Dict[str, Any]],
                     regime_rows: List[Dict[str, Any]],
                     drawdown_rows: List[Dict[str, Any]],
                     run_updates: Dict[str, Any]) -> None:
    """Atomic replacement of every child table plus the parent columns."""
    updates = {k: v for k, v in run_updates.items() if k in RUN_UPDATE_COLUMNS}
    set_clause = ", ".join(f"{c} = ?" for c in updates)
    with get_connection() as conn:
        try:
            conn.execute("BEGIN")
            for table in CHILD_TABLES:
                conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))
            if benchmark is not None:
                conn.execute(
                    """
                    INSERT INTO attribution_benchmarks (
                        run_id, benchmark_id, name, description, source, kind,
                        return_convention, timing_policy, asset_count,
                        weight_sum, definition_json, fingerprint
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, benchmark["benchmark_id"], benchmark["name"],
                     benchmark.get("description", ""), benchmark["source"],
                     benchmark["kind"], benchmark["return_convention"],
                     benchmark["timing_policy"],
                     len(benchmark.get("asset_ids") or []),
                     benchmark.get("weight_sum"),
                     json.dumps(benchmark.get("definition", {})),
                     benchmark["fingerprint"]))
            for r in period_rows:
                conn.execute(
                    """
                    INSERT INTO attribution_period_results (
                        run_id, period_id, period_start, period_end,
                        information_available_at, portfolio_market_return,
                        transaction_cost_return, cost_state,
                        portfolio_net_return, benchmark_return, active_return,
                        allocation_effect, selection_effect,
                        interaction_effect, residual, reconciliation_state,
                        cash_weight, regime_label
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, r["period_id"], r["period_start"], r["period_end"],
                     r["information_available_at"],
                     r.get("portfolio_market_return"),
                     r.get("transaction_cost_return"), r.get("cost_state"),
                     r.get("portfolio_net_return"), r.get("benchmark_return"),
                     r.get("active_return"), r.get("allocation_effect"),
                     r.get("selection_effect"), r.get("interaction_effect"),
                     r.get("residual"), r.get("reconciliation_state"),
                     r.get("cash_weight"), r.get("regime_label")))
            for i, r in enumerate(asset_rows):
                conn.execute(
                    """
                    INSERT INTO attribution_asset_results (
                        run_id, asset_index, asset_id, group_id,
                        average_weight, arithmetic_contribution,
                        linked_contribution, positive_contribution,
                        negative_contribution, absolute_contribution,
                        absolute_share, observation_count
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, i, r["asset_id"], r.get("group_id"),
                     r.get("average_weight"), r.get("arithmetic_contribution"),
                     r.get("linked_contribution"),
                     r.get("positive_contribution"),
                     r.get("negative_contribution"),
                     r.get("absolute_contribution"), r.get("absolute_share"),
                     r.get("observation_count", 0)))
            for i, r in enumerate(group_rows):
                conn.execute(
                    """
                    INSERT INTO attribution_group_results (
                        run_id, group_index, group_id, asset_count,
                        average_weight, arithmetic_contribution,
                        positive_contribution, negative_contribution,
                        absolute_contribution, absolute_share
                    ) VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, i, r["group_id"], r.get("asset_count", 0),
                     r.get("average_weight"), r.get("arithmetic_contribution"),
                     r.get("positive_contribution"),
                     r.get("negative_contribution"),
                     r.get("absolute_contribution"), r.get("absolute_share")))
            for i, r in enumerate(brinson_rows):
                conn.execute(
                    """
                    INSERT INTO attribution_brinson_results (
                        run_id, group_index, group_id, presence,
                        average_portfolio_weight, average_benchmark_weight,
                        allocation_effect, selection_effect,
                        interaction_effect, total_effect,
                        linked_allocation_effect, linked_selection_effect,
                        linked_interaction_effect, unavailable_periods
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, i, r["group_id"], r.get("presence"),
                     r.get("average_portfolio_weight"),
                     r.get("average_benchmark_weight"),
                     r.get("allocation_effect"), r.get("selection_effect"),
                     r.get("interaction_effect"), r.get("total_effect"),
                     r.get("linked_allocation_effect"),
                     r.get("linked_selection_effect"),
                     r.get("linked_interaction_effect"),
                     r.get("unavailable_periods", 0)))
            for i, r in enumerate(regime_rows):
                conn.execute(
                    """
                    INSERT INTO attribution_regime_results (
                        run_id, row_index, regime_label, observation_count,
                        portfolio_market_return, benchmark_return,
                        active_return, cost_return, net_return,
                        allocation_effect, selection_effect,
                        interaction_effect, tracking_error,
                        contribution_herfindahl, completeness,
                        rare_regime_warning
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, i, r["regime_label"],
                     r.get("observation_count", 0),
                     r.get("portfolio_market_return"),
                     r.get("benchmark_return"), r.get("active_return"),
                     r.get("cost_return"), r.get("net_return"),
                     r.get("allocation_effect"), r.get("selection_effect"),
                     r.get("interaction_effect"), r.get("tracking_error"),
                     r.get("contribution_herfindahl"), r.get("completeness"),
                     1 if r.get("rare_regime_warning") else 0))
            for r in drawdown_rows:
                conn.execute(
                    """
                    INSERT INTO attribution_drawdown_results (
                        run_id, episode_id, peak_timestamp, trough_timestamp,
                        recovery_timestamp, period_count,
                        portfolio_market_return, benchmark_return,
                        active_return, cost_return, allocation_effect,
                        selection_effect, interaction_effect, residual,
                        reconciliation_state, contributions_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, r["episode_id"], r.get("peak_timestamp"),
                     r.get("trough_timestamp"), r.get("recovery_timestamp"),
                     r.get("period_count", 0),
                     r.get("portfolio_market_return"),
                     r.get("benchmark_return"), r.get("active_return"),
                     r.get("cost_return"), r.get("allocation_effect"),
                     r.get("selection_effect"), r.get("interaction_effect"),
                     r.get("residual"), r.get("reconciliation_state"),
                     json.dumps(r.get("contributions", []))))
            if updates:
                conn.execute(
                    f"UPDATE portfolio_attribution_runs SET {set_clause}, "
                    "updated_at = ? WHERE id = ?",
                    [*updates.values(), _now(), run_id])
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def clear_results(run_id: int) -> None:
    """Remove every derived result (used when execution fails, so a failed
    run never exposes stale numbers from a prior execution)."""
    with get_connection() as conn:
        try:
            conn.execute("BEGIN")
            for table in CHILD_TABLES:
                conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))
            conn.execute(
                """
                UPDATE portfolio_attribution_runs SET
                    completeness_status = 'unavailable',
                    reconciliation_status = 'unknown',
                    portfolio_market_return = NULL, portfolio_net_return = NULL,
                    benchmark_return = NULL, active_return = NULL,
                    total_cost_return = NULL, tracking_error = NULL,
                    information_ratio = NULL, result_fingerprint = NULL,
                    summary_json = NULL, linking_json = NULL, cost_json = NULL,
                    active_risk_json = NULL, concentration_json = NULL,
                    warnings_json = '[]', period_count = 0, group_count = 0,
                    updated_at = ?
                WHERE id = ?
                """, (_now(), run_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def get_benchmark(run_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM attribution_benchmarks WHERE run_id = ?",
            (run_id,)).fetchone()
    if not row:
        return None
    return {"benchmark_id": row["benchmark_id"], "name": row["name"],
            "description": row["description"], "source": row["source"],
            "kind": row["kind"],
            "return_convention": row["return_convention"],
            "timing_policy": row["timing_policy"],
            "asset_count": row["asset_count"], "weight_sum": row["weight_sum"],
            "definition": json.loads(row["definition_json"]),
            "fingerprint": row["fingerprint"]}


def list_periods(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM attribution_period_results WHERE run_id = ? "
            "ORDER BY period_id", (run_id,)).fetchall()
    return [{"period_id": r["period_id"], "period_start": r["period_start"],
             "period_end": r["period_end"],
             "information_available_at": r["information_available_at"],
             "portfolio_market_return": r["portfolio_market_return"],
             "transaction_cost_return": r["transaction_cost_return"],
             "cost_state": r["cost_state"],
             "portfolio_net_return": r["portfolio_net_return"],
             "benchmark_return": r["benchmark_return"],
             "active_return": r["active_return"],
             "allocation_effect": r["allocation_effect"],
             "selection_effect": r["selection_effect"],
             "interaction_effect": r["interaction_effect"],
             "residual": r["residual"],
             "reconciliation_state": r["reconciliation_state"],
             "cash_weight": r["cash_weight"],
             "regime_label": r["regime_label"]} for r in rows]


def list_assets(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM attribution_asset_results WHERE run_id = ? "
            "ORDER BY asset_index", (run_id,)).fetchall()
    return [{"asset_id": r["asset_id"], "group_id": r["group_id"],
             "average_weight": r["average_weight"],
             "arithmetic_contribution": r["arithmetic_contribution"],
             "linked_contribution": r["linked_contribution"],
             "positive_contribution": r["positive_contribution"],
             "negative_contribution": r["negative_contribution"],
             "absolute_contribution": r["absolute_contribution"],
             "absolute_share": r["absolute_share"],
             "observation_count": r["observation_count"]} for r in rows]


def list_groups(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM attribution_group_results WHERE run_id = ? "
            "ORDER BY group_index", (run_id,)).fetchall()
    return [{"group_id": r["group_id"], "asset_count": r["asset_count"],
             "average_weight": r["average_weight"],
             "arithmetic_contribution": r["arithmetic_contribution"],
             "positive_contribution": r["positive_contribution"],
             "negative_contribution": r["negative_contribution"],
             "absolute_contribution": r["absolute_contribution"],
             "absolute_share": r["absolute_share"]} for r in rows]


def list_brinson(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM attribution_brinson_results WHERE run_id = ? "
            "ORDER BY group_index", (run_id,)).fetchall()
    return [{"group_id": r["group_id"], "presence": r["presence"],
             "average_portfolio_weight": r["average_portfolio_weight"],
             "average_benchmark_weight": r["average_benchmark_weight"],
             "allocation_effect": r["allocation_effect"],
             "selection_effect": r["selection_effect"],
             "interaction_effect": r["interaction_effect"],
             "total_effect": r["total_effect"],
             "linked_allocation_effect": r["linked_allocation_effect"],
             "linked_selection_effect": r["linked_selection_effect"],
             "linked_interaction_effect": r["linked_interaction_effect"],
             "unavailable_periods": r["unavailable_periods"]} for r in rows]


def list_regimes(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM attribution_regime_results WHERE run_id = ? "
            "ORDER BY row_index", (run_id,)).fetchall()
    return [{"regime_label": r["regime_label"],
             "observation_count": r["observation_count"],
             "portfolio_market_return": r["portfolio_market_return"],
             "benchmark_return": r["benchmark_return"],
             "active_return": r["active_return"],
             "cost_return": r["cost_return"], "net_return": r["net_return"],
             "allocation_effect": r["allocation_effect"],
             "selection_effect": r["selection_effect"],
             "interaction_effect": r["interaction_effect"],
             "tracking_error": r["tracking_error"],
             "contribution_herfindahl": r["contribution_herfindahl"],
             "completeness": r["completeness"],
             "rare_regime_warning": bool(r["rare_regime_warning"])}
            for r in rows]


def list_drawdowns(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM attribution_drawdown_results WHERE run_id = ? "
            "ORDER BY episode_id", (run_id,)).fetchall()
    return [{"episode_id": r["episode_id"],
             "peak_timestamp": r["peak_timestamp"],
             "trough_timestamp": r["trough_timestamp"],
             "recovery_timestamp": r["recovery_timestamp"],
             "period_count": r["period_count"],
             "portfolio_market_return": r["portfolio_market_return"],
             "benchmark_return": r["benchmark_return"],
             "active_return": r["active_return"],
             "cost_return": r["cost_return"],
             "allocation_effect": r["allocation_effect"],
             "selection_effect": r["selection_effect"],
             "interaction_effect": r["interaction_effect"],
             "residual": r["residual"],
             "reconciliation_state": r["reconciliation_state"],
             "contributions": json.loads(r["contributions_json"] or "[]")}
            for r in rows]


def mark_baseline(run_id: int, scope: str) -> None:
    now = _now()
    with get_connection() as conn:
        try:
            conn.execute("BEGIN")
            conn.execute(
                "UPDATE portfolio_attribution_runs SET is_baseline = 0, "
                "updated_at = ? WHERE baseline_scope = ? AND is_baseline = 1 "
                "AND id != ?", (now, scope, run_id))
            conn.execute(
                "UPDATE portfolio_attribution_runs SET is_baseline = 1, "
                "updated_at = ? WHERE id = ?", (now, run_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def lab_summary() -> Dict[str, Any]:
    with get_connection() as conn:
        runs = int(conn.execute(
            "SELECT COUNT(*) AS c FROM portfolio_attribution_runs"
        ).fetchone()["c"])
        completed = int(conn.execute(
            "SELECT COUNT(*) AS c FROM portfolio_attribution_runs "
            "WHERE status='completed'").fetchone()["c"])
        periods = int(conn.execute(
            "SELECT COALESCE(SUM(period_count), 0) AS c "
            "FROM portfolio_attribution_runs").fetchone()["c"])
        benchmarked = int(conn.execute(
            "SELECT COUNT(*) AS c FROM attribution_benchmarks").fetchone()["c"])
        reconciled = int(conn.execute(
            "SELECT COUNT(*) AS c FROM portfolio_attribution_runs "
            "WHERE reconciliation_status='reconciled'").fetchone()["c"])
        baselines = int(conn.execute(
            "SELECT COUNT(*) AS c FROM portfolio_attribution_runs "
            "WHERE is_baseline=1").fetchone()["c"])
    return {"runs": runs, "completed": completed, "periods": periods,
            "benchmarked_runs": benchmarked, "reconciled_runs": reconciled,
            "baselines": baselines}


__all__ = [
    "DEFAULT_PAGE_SIZE", "MAX_PAGE_SIZE", "SORTABLE", "RUN_UPDATE_COLUMNS",
    "CHILD_TABLES", "insert_run", "get_run", "run_demo_key_id", "update_run",
    "list_runs", "replace_children", "clear_results", "get_benchmark",
    "list_periods", "list_assets", "list_groups", "list_brinson",
    "list_regimes", "list_drawdowns", "mark_baseline", "lab_summary",
]
