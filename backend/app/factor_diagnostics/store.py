"""SQLite persistence for the Factor Diagnostics Lab (parameterised SQL)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.db import get_connection

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
SORTABLE = frozenset({"created_at", "updated_at", "name", "status",
                      "analysis_mode", "regression_method",
                      "integrity_status", "completeness_status",
                      "rank_status", "observation_count", "factor_count",
                      "r_squared"})

CHILD_TABLES = ("factor_definitions", "factor_observations",
                "factor_coefficients", "factor_period_results",
                "factor_rolling_results", "factor_regime_results",
                "factor_sensitivity_results")

RESULT_TABLES = ("factor_coefficients", "factor_period_results",
                 "factor_rolling_results", "factor_regime_results",
                 "factor_sensitivity_results")

RUN_UPDATE_COLUMNS = frozenset({
    "status", "analysis_mode", "regression_method", "intercept_policy",
    "rank_policy", "timing_policy", "vintage_policy", "target_id",
    "target_type", "target_source", "return_convention", "return_frequency",
    "currency", "observation_start", "observation_end", "factor_count",
    "observation_count", "excluded_period_count", "integrity_status",
    "completeness_status", "rank_status", "reconciliation_status",
    "r_squared", "adjusted_r_squared", "root_mean_squared_error",
    "residual_std", "intercept", "condition_number", "degrees_of_freedom",
    "held_out_r_squared", "configuration", "results", "target_fingerprint",
    "observation_fingerprint", "model_policy_fingerprint",
    "configuration_fingerprint", "result_fingerprint", "dataset_version_id",
    "portfolio_run_id", "attribution_run_id", "validation_run_id",
    "regime_run_id", "stress_run_id", "experiment_id", "is_baseline",
    "baseline_scope", "app_version", "git_commit", "notes", "error_message",
    "started_at", "completed_at",
})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="microseconds").replace("+00:00", "Z")


def _json(value: Optional[str]) -> Any:
    return json.loads(value) if value else None


def _run_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"], "created_at": row["created_at"],
        "updated_at": row["updated_at"], "name": row["name"],
        "description": row["description"], "status": row["status"],
        "analysis_mode": row["analysis_mode"],
        "regression_method": row["regression_method"],
        "intercept_policy": row["intercept_policy"],
        "rank_policy": row["rank_policy"],
        "timing_policy": row["timing_policy"],
        "vintage_policy": row["vintage_policy"],
        "target_id": row["target_id"], "target_type": row["target_type"],
        "target_source": row["target_source"],
        "return_convention": row["return_convention"],
        "return_frequency": row["return_frequency"],
        "currency": row["currency"],
        "observation_start": row["observation_start"],
        "observation_end": row["observation_end"],
        "factor_count": row["factor_count"],
        "observation_count": row["observation_count"],
        "excluded_period_count": row["excluded_period_count"],
        "integrity_status": row["integrity_status"],
        "completeness_status": row["completeness_status"],
        "rank_status": row["rank_status"],
        "reconciliation_status": row["reconciliation_status"],
        "r_squared": row["r_squared"],
        "adjusted_r_squared": row["adjusted_r_squared"],
        "root_mean_squared_error": row["root_mean_squared_error"],
        "residual_std": row["residual_std"],
        "intercept": row["intercept"],
        "condition_number": row["condition_number"],
        "degrees_of_freedom": row["degrees_of_freedom"],
        "held_out_r_squared": row["held_out_r_squared"],
        "configuration": _json(row["configuration"]) or {},
        "results": _json(row["results"]) or {},
        "target_fingerprint": row["target_fingerprint"],
        "observation_fingerprint": row["observation_fingerprint"],
        "model_policy_fingerprint": row["model_policy_fingerprint"],
        "configuration_fingerprint": row["configuration_fingerprint"],
        "result_fingerprint": row["result_fingerprint"],
        "dataset_version_id": row["dataset_version_id"],
        "portfolio_run_id": row["portfolio_run_id"],
        "attribution_run_id": row["attribution_run_id"],
        "validation_run_id": row["validation_run_id"],
        "regime_run_id": row["regime_run_id"],
        "stress_run_id": row["stress_run_id"],
        "experiment_id": row["experiment_id"],
        "is_baseline": bool(row["is_baseline"]),
        "baseline_scope": row["baseline_scope"],
        "app_version": row["app_version"], "git_commit": row["git_commit"],
        "notes": row["notes"], "error_message": row["error_message"],
        "started_at": row["started_at"], "completed_at": row["completed_at"],
    }


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

def insert_run(fields: Dict[str, Any]) -> Dict[str, Any]:
    now = _now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO factor_diagnostic_runs (
                created_at, updated_at, name, description, status,
                analysis_mode, regression_method, intercept_policy,
                rank_policy, timing_policy, vintage_policy, target_id,
                target_type, target_source, return_convention,
                return_frequency, currency, observation_start,
                observation_end, factor_count, observation_count,
                excluded_period_count, integrity_status, completeness_status,
                rank_status, reconciliation_status, configuration,
                target_fingerprint, observation_fingerprint,
                model_policy_fingerprint, configuration_fingerprint,
                dataset_version_id, portfolio_run_id, attribution_run_id,
                validation_run_id, regime_run_id, stress_run_id, app_version,
                git_commit, notes, demo_key
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                      ?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (now, now, fields["name"], fields.get("description", ""),
             fields.get("status", "pending"), fields["analysis_mode"],
             fields.get("regression_method", "ols"),
             fields.get("intercept_policy", "include"),
             fields.get("rank_policy", "fail"), fields["timing_policy"],
             fields["vintage_policy"], fields["target_id"],
             fields["target_type"], fields["target_source"],
             fields.get("return_convention", "simple"),
             fields.get("return_frequency", "daily"),
             fields.get("currency", "USD"), fields.get("observation_start"),
             fields.get("observation_end"), fields.get("factor_count", 0),
             fields.get("observation_count", 0),
             fields.get("excluded_period_count", 0),
             fields.get("integrity_status", "unknown"),
             fields.get("completeness_status", "unavailable"),
             fields.get("rank_status"), fields.get("reconciliation_status"),
             json.dumps(fields.get("configuration") or {}),
             fields["target_fingerprint"], fields["observation_fingerprint"],
             fields["model_policy_fingerprint"],
             fields["configuration_fingerprint"],
             fields.get("dataset_version_id"), fields.get("portfolio_run_id"),
             fields.get("attribution_run_id"), fields.get("validation_run_id"),
             fields.get("regime_run_id"), fields.get("stress_run_id"),
             fields.get("app_version"), fields.get("git_commit"),
             fields.get("notes", ""), fields.get("demo_key")))
        run_id = int(cursor.lastrowid)
        conn.commit()
    return get_run(run_id)  # type: ignore[return-value]


def get_run(run_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM factor_diagnostic_runs WHERE id = ?",
            (run_id,)).fetchone()
    return _run_row(row) if row else None


def run_demo_key_id(demo_key: str) -> Optional[int]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM factor_diagnostic_runs WHERE demo_key = ?",
            (demo_key,)).fetchone()
    return int(row["id"]) if row else None


def update_run(run_id: int, columns: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    unknown = sorted(set(columns) - RUN_UPDATE_COLUMNS)
    if unknown:
        raise ValueError(f"unsupported run columns: {unknown}")
    if not columns:
        return get_run(run_id)
    assignments = ", ".join(f"{name} = ?" for name in columns)
    values = [json.dumps(v) if name in ("configuration", "results") else v
              for name, v in columns.items()]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE factor_diagnostic_runs SET {assignments}, updated_at = ? "
            f"WHERE id = ?", (*values, _now(), run_id))
        conn.commit()
    return get_run(run_id)


def _where(filters: Dict[str, Any]) -> Tuple[str, List[Any]]:
    clauses: List[str] = []
    params: List[Any] = []
    for column in ("status", "analysis_mode", "regression_method",
                   "integrity_status", "completeness_status", "rank_status",
                   "timing_policy", "target_type"):
        value = filters.get(column)
        if value:
            clauses.append(f"{column} = ?")
            params.append(value)
    if filters.get("is_baseline") is not None:
        clauses.append("is_baseline = ?")
        params.append(1 if filters["is_baseline"] else 0)
    query = filters.get("query")
    if query:
        clauses.append("(name LIKE ? OR description LIKE ? OR target_id LIKE ?)")
        like = f"%{query}%"
        params.extend([like, like, like])
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def list_runs(*, filters: Optional[Dict[str, Any]] = None,
              sort_by: str = "created_at", sort_dir: str = "desc",
              page: int = 1, page_size: int = DEFAULT_PAGE_SIZE
              ) -> Dict[str, Any]:
    sort_by = sort_by if sort_by in SORTABLE else "created_at"
    direction = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), MAX_PAGE_SIZE))
    where, params = _where(filters or {})
    with get_connection() as conn:
        total = int(conn.execute(
            f"SELECT COUNT(*) AS c FROM factor_diagnostic_runs{where}",
            params).fetchone()["c"])
        rows = conn.execute(
            f"SELECT * FROM factor_diagnostic_runs{where} "
            f"ORDER BY {sort_by} {direction}, id {direction} LIMIT ? OFFSET ?",
            (*params, page_size, (page - 1) * page_size)).fetchall()
    return {
        "items": [_run_row(r) for r in rows],
        "total": total, "page": page, "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


# ---------------------------------------------------------------------------
# Children
# ---------------------------------------------------------------------------

def replace_children(run_id: int, *,
                     definitions: List[Dict[str, Any]],
                     observations: List[Dict[str, Any]],
                     coefficients: List[Dict[str, Any]],
                     periods: List[Dict[str, Any]],
                     rolling: List[Dict[str, Any]],
                     regimes: List[Dict[str, Any]],
                     sensitivity: List[Dict[str, Any]],
                     run_columns: Dict[str, Any]) -> None:
    """Deterministic child replacement + run update in ONE transaction."""
    unknown = sorted(set(run_columns) - RUN_UPDATE_COLUMNS)
    if unknown:
        raise ValueError(f"unsupported run columns: {unknown}")
    with get_connection() as conn:
        try:
            conn.execute("BEGIN")
            for table in CHILD_TABLES:
                conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))
            for index, d in enumerate(definitions):
                conn.execute(
                    """
                    INSERT INTO factor_definitions (
                        run_id, factor_index, factor_id, name, description,
                        category, source, unit, transformed_unit, frequency,
                        transformation, lag, availability_policy,
                        missing_policy, standardisation_policy,
                        standardisation_window, winsorisation_policy,
                        dataset_version_id, observation_start,
                        observation_end, definition_fingerprint, metadata_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, index, d["factor_id"], d["name"],
                     d.get("description", ""), d["category"], d["source"],
                     d["unit"], d["transformed_unit"], d["frequency"],
                     d["transformation"], d["lag"], d["availability_policy"],
                     d["missing_policy"], d["standardisation_policy"],
                     d.get("standardisation_window"),
                     d["winsorisation_policy"], d.get("dataset_version_id"),
                     d.get("observation_start"), d.get("observation_end"),
                     d["definition_fingerprint"],
                     json.dumps(d.get("metadata") or {})))
            for o in observations:
                conn.execute(
                    """
                    INSERT INTO factor_observations (
                        run_id, factor_id, period_index, observation_id,
                        source_timestamp, available_at, effective_timestamp,
                        knowable_at, release_timestamp, raw_value,
                        transformed_value, unit, quality_state, vintage_state
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, o["factor_id"], o["period_index"],
                     o["observation_id"], o["source_timestamp"],
                     o.get("available_at"), o["effective_timestamp"],
                     o.get("knowable_at"), o.get("release_timestamp"),
                     o.get("raw_value"), o.get("transformed_value"),
                     o["unit"], o["quality_state"], o["vintage_state"]))
            for index, c in enumerate(coefficients):
                conn.execute(
                    """
                    INSERT INTO factor_coefficients (
                        run_id, factor_index, factor_id, coefficient,
                        coefficient_unit, exposure_state, standard_error,
                        t_statistic, p_value, p_bonferroni, p_holm, p_bh,
                        confidence_lower, confidence_upper, contribution_sum,
                        vif, vif_state, warning, unavailable_reason
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, index, c["factor_id"], c.get("coefficient"),
                     c.get("coefficient_unit"), c.get("exposure_state",
                                                      "estimated"),
                     c.get("standard_error"), c.get("t_statistic"),
                     c.get("p_value"), c.get("p_bonferroni"), c.get("p_holm"),
                     c.get("p_bh"), c.get("confidence_lower"),
                     c.get("confidence_upper"), c.get("contribution_sum"),
                     c.get("vif"), c.get("vif_state"), c.get("warning"),
                     c.get("unavailable_reason")))
            for p in periods:
                conn.execute(
                    """
                    INSERT INTO factor_period_results (
                        run_id, period_index, period_start, period_end,
                        information_available_at, measured_return,
                        intercept_contribution, modelled_return, residual,
                        reconciliation_difference, reconciliation_state,
                        exposure_state, regime_label, membership,
                        contributions_json, exposures_json, factor_values_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, p["period_index"], p["period_start"],
                     p.get("period_end"), p.get("information_available_at"),
                     p.get("measured_return"), p.get("intercept_contribution"),
                     p.get("modelled_return"), p.get("residual"),
                     p.get("reconciliation_difference"),
                     p["reconciliation_state"], p["exposure_state"],
                     p.get("regime_label"), p.get("membership"),
                     json.dumps(p.get("factor_contributions") or {}),
                     json.dumps(p.get("exposures") or {}),
                     json.dumps(p.get("factor_values") or {})))
            for r in rolling:
                conn.execute(
                    """
                    INSERT INTO factor_rolling_results (
                        run_id, window_id, window_start, window_end,
                        decision_timestamp, effective_timestamp, observations,
                        intercept, r_squared, condition_number, rank,
                        rank_status, status, reason, fingerprint,
                        coefficients_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, r["window_id"], r["window_start"], r["window_end"],
                     r.get("decision_timestamp"), r.get("effective_timestamp"),
                     r["observations"], r.get("intercept"), r.get("r_squared"),
                     r.get("condition_number"), r.get("rank"),
                     r.get("rank_status"), r["status"], r.get("reason"),
                     r.get("fingerprint"),
                     json.dumps(r.get("coefficients") or {})))
            for g in regimes:
                conn.execute(
                    """
                    INSERT INTO factor_regime_results (
                        run_id, regime_label, definition_id, observations,
                        rare, r_squared, condition_number, rank_status,
                        intercept, residual_mean, residual_std,
                        measured_return_sum, modelled_return_sum, residual_sum,
                        completeness, status, reason, coefficients_json,
                        contributions_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, g["regime_label"], g.get("definition_id"),
                     g.get("observations", 0), 1 if g.get("rare") else 0,
                     g.get("r_squared"), g.get("condition_number"),
                     g.get("rank_status"), g.get("intercept"),
                     g.get("residual_mean"), g.get("residual_std"),
                     g.get("measured_return_sum"), g.get("modelled_return_sum"),
                     g.get("residual_sum"),
                     g.get("completeness", "unavailable"), g["status"],
                     g.get("reason"), json.dumps(g.get("coefficients") or {}),
                     json.dumps(g.get("contributions") or {})))
            for index, s in enumerate(sensitivity):
                conn.execute(
                    """
                    INSERT INTO factor_sensitivity_results (
                        run_id, scenario_index, label, is_base, description,
                        observations, regression_method, intercept, r_squared,
                        adjusted_r_squared, root_mean_squared_error,
                        residual_std, condition_number, rank, rank_status,
                        reconciliation_state, held_out_r_squared, status,
                        reason, fingerprint, coefficients_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, index, s["label"], 1 if s.get("is_base") else 0,
                     s.get("description", ""), s.get("observations"),
                     s.get("regression_method"), s.get("intercept"),
                     s.get("r_squared"), s.get("adjusted_r_squared"),
                     s.get("root_mean_squared_error"), s.get("residual_std"),
                     s.get("condition_number"), s.get("rank"),
                     s.get("rank_status"), s.get("reconciliation_state"),
                     s.get("held_out_r_squared"), s["status"], s.get("reason"),
                     s.get("fingerprint"),
                     json.dumps(s.get("coefficients") or {})))
            if run_columns:
                assignments = ", ".join(f"{name} = ?" for name in run_columns)
                values = [json.dumps(v) if name in ("configuration", "results")
                          else v
                          for name, v in run_columns.items()]
                conn.execute(
                    f"UPDATE factor_diagnostic_runs SET {assignments}, "
                    f"updated_at = ? WHERE id = ?",
                    (*values, _now(), run_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def clear_results(run_id: int) -> None:
    """Drop result rows (definitions and observations survive a failure)."""
    with get_connection() as conn:
        try:
            conn.execute("BEGIN")
            for table in RESULT_TABLES:
                conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def mark_failed(run_id: int, error_message: str, completed_at: str) -> None:
    with get_connection() as conn:
        try:
            conn.execute("BEGIN")
            for table in RESULT_TABLES:
                conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))
            conn.execute(
                """
                UPDATE factor_diagnostic_runs
                   SET status = 'failed', error_message = ?, completed_at = ?,
                       updated_at = ?, result_fingerprint = NULL,
                       results = NULL,
                       r_squared = NULL, adjusted_r_squared = NULL,
                       root_mean_squared_error = NULL, residual_std = NULL,
                       intercept = NULL, condition_number = NULL,
                       degrees_of_freedom = NULL, held_out_r_squared = NULL,
                       rank_status = NULL, reconciliation_status = NULL,
                       completeness_status = 'unavailable', is_baseline = 0,
                       baseline_scope = NULL
                 WHERE id = ?
                """,
                (error_message[:2000], completed_at, _now(), run_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def list_definitions(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM factor_definitions WHERE run_id = ? "
            "ORDER BY factor_index", (run_id,)).fetchall()
    return [{
        "factor_index": r["factor_index"], "factor_id": r["factor_id"],
        "name": r["name"], "description": r["description"],
        "category": r["category"], "source": r["source"], "unit": r["unit"],
        "transformed_unit": r["transformed_unit"], "frequency": r["frequency"],
        "transformation": r["transformation"], "lag": r["lag"],
        "availability_policy": r["availability_policy"],
        "missing_policy": r["missing_policy"],
        "standardisation_policy": r["standardisation_policy"],
        "standardisation_window": r["standardisation_window"],
        "winsorisation_policy": r["winsorisation_policy"],
        "dataset_version_id": r["dataset_version_id"],
        "observation_start": r["observation_start"],
        "observation_end": r["observation_end"],
        "definition_fingerprint": r["definition_fingerprint"],
        "metadata": _json(r["metadata_json"]) or {},
    } for r in rows]


def list_observations(run_id: int, *, factor_id: Optional[str] = None,
                      limit: int = 2000) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit), 24000))
    with get_connection() as conn:
        if factor_id:
            rows = conn.execute(
                "SELECT * FROM factor_observations WHERE run_id = ? AND "
                "factor_id = ? ORDER BY factor_id, period_index LIMIT ?",
                (run_id, factor_id, limit)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM factor_observations WHERE run_id = ? "
                "ORDER BY factor_id, period_index LIMIT ?",
                (run_id, limit)).fetchall()
    return [{
        "factor_id": r["factor_id"], "period_index": r["period_index"],
        "observation_id": r["observation_id"],
        "source_timestamp": r["source_timestamp"],
        "available_at": r["available_at"],
        "effective_timestamp": r["effective_timestamp"],
        "knowable_at": r["knowable_at"],
        "release_timestamp": r["release_timestamp"],
        "raw_value": r["raw_value"], "transformed_value": r["transformed_value"],
        "unit": r["unit"], "quality_state": r["quality_state"],
        "vintage_state": r["vintage_state"],
    } for r in rows]


def list_coefficients(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM factor_coefficients WHERE run_id = ? "
            "ORDER BY factor_index", (run_id,)).fetchall()
    return [{
        "factor_id": r["factor_id"], "coefficient": r["coefficient"],
        "coefficient_unit": r["coefficient_unit"],
        "exposure_state": r["exposure_state"],
        "standard_error": r["standard_error"],
        "t_statistic": r["t_statistic"], "p_value": r["p_value"],
        "p_bonferroni": r["p_bonferroni"], "p_holm": r["p_holm"],
        "p_bh": r["p_bh"], "confidence_lower": r["confidence_lower"],
        "confidence_upper": r["confidence_upper"],
        "contribution_sum": r["contribution_sum"], "vif": r["vif"],
        "vif_state": r["vif_state"], "warning": r["warning"],
        "unavailable_reason": r["unavailable_reason"],
    } for r in rows]


def list_periods(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM factor_period_results WHERE run_id = ? "
            "ORDER BY period_index", (run_id,)).fetchall()
    return [{
        "period_index": r["period_index"], "period_start": r["period_start"],
        "period_end": r["period_end"],
        "information_available_at": r["information_available_at"],
        "measured_return": r["measured_return"],
        "intercept_contribution": r["intercept_contribution"],
        "modelled_return": r["modelled_return"], "residual": r["residual"],
        "reconciliation_difference": r["reconciliation_difference"],
        "reconciliation_state": r["reconciliation_state"],
        "exposure_state": r["exposure_state"],
        "regime_label": r["regime_label"], "membership": r["membership"],
        "factor_contributions": _json(r["contributions_json"]) or {},
        "exposures": _json(r["exposures_json"]) or {},
        "factor_values": _json(r["factor_values_json"]) or {},
    } for r in rows]


def list_rolling(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM factor_rolling_results WHERE run_id = ? "
            "ORDER BY window_id", (run_id,)).fetchall()
    return [{
        "window_id": r["window_id"], "window_start": r["window_start"],
        "window_end": r["window_end"],
        "decision_timestamp": r["decision_timestamp"],
        "effective_timestamp": r["effective_timestamp"],
        "observations": r["observations"], "intercept": r["intercept"],
        "r_squared": r["r_squared"], "condition_number": r["condition_number"],
        "rank": r["rank"], "rank_status": r["rank_status"],
        "status": r["status"], "reason": r["reason"],
        "fingerprint": r["fingerprint"],
        "coefficients": _json(r["coefficients_json"]) or {},
    } for r in rows]


def list_regimes(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM factor_regime_results WHERE run_id = ? "
            "ORDER BY regime_label", (run_id,)).fetchall()
    return [{
        "regime_label": r["regime_label"], "definition_id": r["definition_id"],
        "observations": r["observations"], "rare": bool(r["rare"]),
        "r_squared": r["r_squared"], "condition_number": r["condition_number"],
        "rank_status": r["rank_status"], "intercept": r["intercept"],
        "residual_mean": r["residual_mean"], "residual_std": r["residual_std"],
        "measured_return_sum": r["measured_return_sum"],
        "modelled_return_sum": r["modelled_return_sum"],
        "residual_sum": r["residual_sum"], "completeness": r["completeness"],
        "status": r["status"], "reason": r["reason"],
        "coefficients": _json(r["coefficients_json"]) or {},
        "contributions": _json(r["contributions_json"]) or {},
    } for r in rows]


def list_sensitivity(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM factor_sensitivity_results WHERE run_id = ? "
            "ORDER BY scenario_index", (run_id,)).fetchall()
    return [{
        "scenario_index": r["scenario_index"], "label": r["label"],
        "is_base": bool(r["is_base"]), "description": r["description"],
        "observations": r["observations"],
        "regression_method": r["regression_method"],
        "intercept": r["intercept"], "r_squared": r["r_squared"],
        "adjusted_r_squared": r["adjusted_r_squared"],
        "root_mean_squared_error": r["root_mean_squared_error"],
        "residual_std": r["residual_std"],
        "condition_number": r["condition_number"], "rank": r["rank"],
        "rank_status": r["rank_status"],
        "reconciliation_state": r["reconciliation_state"],
        "held_out_r_squared": r["held_out_r_squared"], "status": r["status"],
        "reason": r["reason"], "fingerprint": r["fingerprint"],
        "coefficients": _json(r["coefficients_json"]) or {},
    } for r in rows]


# ---------------------------------------------------------------------------
# Baselines + summary
# ---------------------------------------------------------------------------

def mark_baseline(run_id: int, scope: str) -> None:
    """Transactional same-scope replacement; other scopes are untouched."""
    with get_connection() as conn:
        try:
            conn.execute("BEGIN")
            conn.execute(
                "UPDATE factor_diagnostic_runs SET is_baseline = 0, "
                "updated_at = ? WHERE baseline_scope = ? AND id != ?",
                (_now(), scope, run_id))
            conn.execute(
                "UPDATE factor_diagnostic_runs SET is_baseline = 1, "
                "baseline_scope = ?, updated_at = ? WHERE id = ?",
                (scope, _now(), run_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def lab_summary() -> Dict[str, Any]:
    with get_connection() as conn:
        runs = int(conn.execute(
            "SELECT COUNT(*) AS c FROM factor_diagnostic_runs"
        ).fetchone()["c"])
        completed = int(conn.execute(
            "SELECT COUNT(*) AS c FROM factor_diagnostic_runs "
            "WHERE status = 'completed'").fetchone()["c"])
        baselines = int(conn.execute(
            "SELECT COUNT(*) AS c FROM factor_diagnostic_runs "
            "WHERE is_baseline = 1").fetchone()["c"])
        factors = int(conn.execute(
            "SELECT COUNT(*) AS c FROM factor_definitions").fetchone()["c"])
        observations = int(conn.execute(
            "SELECT COUNT(*) AS c FROM factor_period_results"
        ).fetchone()["c"])
        verified = int(conn.execute(
            "SELECT COUNT(*) AS c FROM factor_diagnostic_runs "
            "WHERE integrity_status IN ('verified_causal_lag', "
            "'verified_from_validation_split', 'verified_trailing_estimation')"
        ).fetchone()["c"])
        rank_deficient = int(conn.execute(
            "SELECT COUNT(*) AS c FROM factor_diagnostic_runs "
            "WHERE rank_status = 'rank_deficient_descriptive'"
        ).fetchone()["c"])
    return {"runs": runs, "completed": completed, "factors": factors,
            "observations": observations, "verified_runs": verified,
            "rank_deficient_runs": rank_deficient, "baselines": baselines}


__all__ = [
    "DEFAULT_PAGE_SIZE", "MAX_PAGE_SIZE", "SORTABLE", "CHILD_TABLES",
    "RESULT_TABLES", "insert_run", "get_run", "run_demo_key_id", "update_run",
    "list_runs", "replace_children", "clear_results", "mark_failed",
    "list_definitions", "list_observations", "list_coefficients",
    "list_periods", "list_rolling", "list_regimes", "list_sensitivity",
    "mark_baseline", "lab_summary",
]
