"""SQLite persistence for the Signal Ensemble Lab (parameterised SQL)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.db import get_connection

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
SORTABLE = frozenset({"created_at", "updated_at", "name", "status",
                      "combination_mode", "integrity_status",
                      "completeness_status", "signal_count",
                      "observation_count", "mean_absolute_correlation",
                      "effective_signal_count"})

CHILD_TABLES = ("signal_ensemble_definitions",
                "signal_ensemble_pairwise_results",
                "signal_ensemble_observations",
                "signal_ensemble_component_results",
                "signal_ensemble_horizon_results",
                "signal_ensemble_leave_one_out_results",
                "signal_ensemble_regime_results",
                "signal_ensemble_bootstrap_results",
                "signal_ensemble_sensitivity_results")

RESULT_TABLES = ("signal_ensemble_pairwise_results",
                 "signal_ensemble_observations",
                 "signal_ensemble_component_results",
                 "signal_ensemble_horizon_results",
                 "signal_ensemble_leave_one_out_results",
                 "signal_ensemble_regime_results",
                 "signal_ensemble_bootstrap_results",
                 "signal_ensemble_sensitivity_results")

RUN_UPDATE_COLUMNS = frozenset({
    "status", "combination_mode", "alignment_policy", "frequency",
    "signal_count", "entity_count", "observation_count",
    "strict_intersection_count", "combined_available_count",
    "observation_start", "observation_end", "integrity_status",
    "completeness_status", "mean_absolute_correlation",
    "effective_signal_count", "configuration", "results",
    "universe_fingerprint", "combination_fingerprint",
    "similarity_fingerprint", "analysis_fingerprint",
    "configuration_fingerprint", "result_fingerprint",
    "dataset_version_id", "signal_decay_run_id", "feature_run_id",
    "meta_label_run_id", "validation_run_id", "regime_run_id",
    "cost_diagnostic_run_id", "factor_run_id", "experiment_id",
    "is_baseline", "baseline_scope", "app_version", "git_commit", "notes",
    "error_message", "started_at", "completed_at",
})

_JSON_COLUMNS = ("configuration", "results")


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
        "combination_mode": row["combination_mode"],
        "alignment_policy": row["alignment_policy"],
        "frequency": row["frequency"],
        "signal_count": row["signal_count"],
        "entity_count": row["entity_count"],
        "observation_count": row["observation_count"],
        "strict_intersection_count": row["strict_intersection_count"],
        "combined_available_count": row["combined_available_count"],
        "observation_start": row["observation_start"],
        "observation_end": row["observation_end"],
        "integrity_status": row["integrity_status"],
        "completeness_status": row["completeness_status"],
        "mean_absolute_correlation": row["mean_absolute_correlation"],
        "effective_signal_count": row["effective_signal_count"],
        "configuration": _json(row["configuration"]) or {},
        "results": _json(row["results"]) or {},
        "universe_fingerprint": row["universe_fingerprint"],
        "combination_fingerprint": row["combination_fingerprint"],
        "similarity_fingerprint": row["similarity_fingerprint"],
        "analysis_fingerprint": row["analysis_fingerprint"],
        "configuration_fingerprint": row["configuration_fingerprint"],
        "result_fingerprint": row["result_fingerprint"],
        "dataset_version_id": row["dataset_version_id"],
        "signal_decay_run_id": row["signal_decay_run_id"],
        "feature_run_id": row["feature_run_id"],
        "meta_label_run_id": row["meta_label_run_id"],
        "validation_run_id": row["validation_run_id"],
        "regime_run_id": row["regime_run_id"],
        "cost_diagnostic_run_id": row["cost_diagnostic_run_id"],
        "factor_run_id": row["factor_run_id"],
        "experiment_id": row["experiment_id"],
        "is_baseline": bool(row["is_baseline"]),
        "baseline_scope": row["baseline_scope"],
        "app_version": row["app_version"], "git_commit": row["git_commit"],
        "notes": row["notes"], "error_message": row["error_message"],
        "started_at": row["started_at"], "completed_at": row["completed_at"],
    }


def insert_run(fields: Dict[str, Any]) -> Dict[str, Any]:
    now = _now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO signal_ensemble_runs (
                created_at, updated_at, name, description, status,
                combination_mode, alignment_policy, frequency, signal_count,
                entity_count, observation_count, strict_intersection_count,
                observation_start, observation_end, integrity_status,
                completeness_status, configuration, universe_fingerprint,
                combination_fingerprint, similarity_fingerprint,
                analysis_fingerprint, configuration_fingerprint,
                dataset_version_id, signal_decay_run_id, feature_run_id,
                meta_label_run_id, validation_run_id, regime_run_id,
                cost_diagnostic_run_id, factor_run_id, app_version,
                git_commit, notes, demo_key
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                      ?,?,?,?,?,?,?,?)
            """,
            (now, now, fields["name"], fields.get("description", ""),
             fields.get("status", "pending"), fields["combination_mode"],
             fields["alignment_policy"], fields.get("frequency", "daily"),
             fields.get("signal_count", 0), fields.get("entity_count", 0),
             fields.get("observation_count", 0),
             fields.get("strict_intersection_count", 0),
             fields.get("observation_start"), fields.get("observation_end"),
             fields.get("integrity_status", "unknown"),
             fields.get("completeness_status", "unavailable"),
             json.dumps(fields.get("configuration") or {}),
             fields.get("universe_fingerprint"),
             fields.get("combination_fingerprint"),
             fields.get("similarity_fingerprint"),
             fields.get("analysis_fingerprint"),
             fields.get("configuration_fingerprint"),
             fields.get("dataset_version_id"),
             fields.get("signal_decay_run_id"),
             fields.get("feature_run_id"), fields.get("meta_label_run_id"),
             fields.get("validation_run_id"), fields.get("regime_run_id"),
             fields.get("cost_diagnostic_run_id"),
             fields.get("factor_run_id"), fields.get("app_version"),
             fields.get("git_commit"), fields.get("notes"),
             fields.get("demo_key")))
        run_id = cursor.lastrowid
        row = conn.execute(
            "SELECT * FROM signal_ensemble_runs WHERE id = ?",
            (run_id,)).fetchone()
        return _run_row(row)


def get_run(run_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM signal_ensemble_runs WHERE id = ?",
            (run_id,)).fetchone()
        return _run_row(row) if row else None


def run_demo_key_id(demo_key: str) -> Optional[int]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM signal_ensemble_runs WHERE demo_key = ?",
            (demo_key,)).fetchone()
        return row["id"] if row else None


def update_run(run_id: int,
               columns: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    unknown = sorted(set(columns) - RUN_UPDATE_COLUMNS)
    if unknown:
        raise ValueError(f"non-updatable run columns: {unknown}")
    sets = []
    values: List[Any] = []
    for key, value in columns.items():
        sets.append(f"{key} = ?")
        values.append(json.dumps(value) if key in _JSON_COLUMNS else value)
    sets.append("updated_at = ?")
    values.append(_now())
    values.append(run_id)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE signal_ensemble_runs SET {', '.join(sets)} "
            f"WHERE id = ?", values)
        row = conn.execute(
            "SELECT * FROM signal_ensemble_runs WHERE id = ?",
            (run_id,)).fetchone()
        return _run_row(row) if row else None


def _where(filters: Dict[str, Any]) -> Tuple[str, List[Any]]:
    clauses: List[str] = []
    values: List[Any] = []
    for column in ("status", "combination_mode", "integrity_status",
                   "completeness_status", "alignment_policy"):
        if filters.get(column):
            clauses.append(f"{column} = ?")
            values.append(filters[column])
    if filters.get("is_baseline") is not None:
        clauses.append("is_baseline = ?")
        values.append(1 if filters["is_baseline"] else 0)
    if filters.get("query"):
        clauses.append("(name LIKE ? OR description LIKE ?)")
        needle = f"%{filters['query']}%"
        values.extend([needle, needle])
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", values


def list_runs(*, filters: Optional[Dict[str, Any]] = None,
              sort: str = "created_at", descending: bool = True,
              page: int = 1,
              page_size: int = DEFAULT_PAGE_SIZE) -> Dict[str, Any]:
    if sort not in SORTABLE:
        sort = "created_at"
    page = max(1, int(page))
    page_size = max(1, min(MAX_PAGE_SIZE, int(page_size)))
    where, values = _where(filters or {})
    direction = "DESC" if descending else "ASC"
    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM signal_ensemble_runs{where}",
            values).fetchone()["c"]
        rows = conn.execute(
            f"SELECT * FROM signal_ensemble_runs{where} "
            f"ORDER BY {sort} {direction}, id {direction} LIMIT ? OFFSET ?",
            values + [page_size, (page - 1) * page_size]).fetchall()
    return {"items": [_run_row(r) for r in rows], "total": total,
            "page": page, "page_size": page_size}


def replace_children(run_id: int, *,
                     definitions: List[Dict[str, Any]],
                     pairwise: List[Dict[str, Any]],
                     observations: List[Dict[str, Any]],
                     components: List[Dict[str, Any]],
                     horizons: List[Dict[str, Any]],
                     leave_one_out: List[Dict[str, Any]],
                     regimes: List[Dict[str, Any]],
                     bootstrap: List[Dict[str, Any]],
                     sensitivity: List[Dict[str, Any]]) -> None:
    """Atomically replace every child row of a run."""
    with get_connection() as conn:
        for table in CHILD_TABLES:
            conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))
        conn.executemany(
            """
            INSERT INTO signal_ensemble_definitions (
                run_id, signal_id, name, definition, definition_fingerprint,
                orientation, normalisation, stored_observations, coverage)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            [(run_id, d["signal_id"], d["name"],
              json.dumps(d["definition"]), d["definition_fingerprint"],
              d["orientation"], json.dumps(d["normalisation"]),
              d["stored_observations"], d.get("coverage"))
             for d in definitions])
        conn.executemany(
            """
            INSERT INTO signal_ensemble_pairwise_results (
                run_id, signal_a, signal_b, alignment_mode, overlap_count,
                coverage_a, coverage_b, pearson, pearson_p, spearman,
                spearman_p, spearman_p_adjusted, kendall, kendall_p,
                mean_absolute_difference, sign_agreement_rate,
                zero_sign_count, agreement, tails, correlations, state,
                reason)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [(run_id, p["signal_a"], p["signal_b"], p["alignment_mode"],
              p["overlap_count"], p.get("coverage_a"), p.get("coverage_b"),
              p.get("pearson"), p.get("pearson_p"), p.get("spearman"),
              p.get("spearman_p"), p.get("spearman_p_adjusted"),
              p.get("kendall"), p.get("kendall_p"),
              p.get("mean_absolute_difference"),
              p.get("sign_agreement_rate"), p.get("zero_sign_count"),
              json.dumps(p.get("agreement")), json.dumps(p.get("tails")),
              json.dumps(p.get("correlations")), p["state"], p.get("reason"))
             for p in pairwise])
        conn.executemany(
            """
            INSERT INTO signal_ensemble_observations (
                run_id, entity_id, timestamp, available_at, combined_score,
                component_count, missing_signal_ids, state, reason)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            [(run_id, o["entity_id"], o["timestamp"], o.get("available_at"),
              o.get("combined_score"), o["component_count"],
              json.dumps(o.get("missing_signal_ids") or []),
              o["state"], o.get("reason"))
             for o in observations])
        conn.executemany(
            """
            INSERT INTO signal_ensemble_component_results (
                run_id, entity_id, timestamp, signal_id, raw_value,
                oriented_value, normalised_value, configured_weight,
                effective_weight, contribution, sign_vote, missing)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [(run_id, c["entity_id"], c["timestamp"], c["signal_id"],
              c.get("raw_value"), c.get("oriented_value"),
              c.get("normalised_value"), c.get("configured_weight"),
              c.get("effective_weight"), c.get("contribution"),
              c.get("sign_vote"), 1 if c.get("missing") else 0)
             for c in components])
        conn.executemany(
            """
            INSERT INTO signal_ensemble_horizon_results (
                run_id, scope, subject_id, horizon, entry_lag, outcome_scope,
                observations, pearson, spearman, spearman_p,
                spearman_p_adjusted, mean_cross_sectional_ic,
                top_minus_bottom, cost_adjusted_spread, overlap_ratio,
                mean_one_way_turnover, state, reason, detail)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [(run_id, h["scope"], h.get("subject_id"), str(h["horizon"]),
              h["entry_lag"], h.get("outcome_scope", "raw"),
              h["observations"], h.get("pearson"), h.get("spearman"),
              h.get("spearman_p"), h.get("spearman_p_adjusted"),
              h.get("mean_cross_sectional_ic"), h.get("top_minus_bottom"),
              h.get("cost_adjusted_spread"), h.get("overlap_ratio"),
              h.get("mean_one_way_turnover"), h["state"], h.get("reason"),
              json.dumps(h.get("detail")))
             for h in horizons])
        conn.executemany(
            """
            INSERT INTO signal_ensemble_leave_one_out_results (
                run_id, omitted_signal_id, metrics, state, reason)
            VALUES (?,?,?,?,?)
            """,
            [(run_id, l["omitted_signal_id"], json.dumps(l["metrics"]),
              l["state"], l.get("reason"))
             for l in leave_one_out])
        conn.executemany(
            """
            INSERT INTO signal_ensemble_regime_results (
                run_id, regime_label, observations, rare,
                mean_absolute_correlation, effective_signal_count,
                combined_spearman, top_minus_bottom, coverage, state,
                reason, detail)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [(run_id, g["regime_label"], g["observations"],
              1 if g.get("rare") else 0,
              g.get("mean_absolute_correlation"),
              g.get("effective_signal_count"), g.get("combined_spearman"),
              g.get("top_minus_bottom"), g.get("coverage"), g["state"],
              g.get("reason"), json.dumps(g.get("detail")))
             for g in regimes])
        conn.executemany(
            """
            INSERT INTO signal_ensemble_bootstrap_results (
                run_id, statistic, method, seed, resamples, block_length,
                quantiles, unavailable_resamples, state, reason)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            [(run_id, b["statistic"], b["method"], b["seed"],
              b["resamples"], b.get("block_length"),
              json.dumps(b.get("quantiles")),
              b.get("unavailable_resamples"), b["state"], b.get("reason"))
             for b in bootstrap])
        conn.executemany(
            """
            INSERT INTO signal_ensemble_sensitivity_results (
                run_id, scenario_index, is_base, label, scenario,
                scenario_fingerprint, metrics, warnings, state, reason)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            [(run_id, s["scenario_index"], 1 if s.get("is_base") else 0,
              s["label"], json.dumps(s["scenario"]),
              s["scenario_fingerprint"], json.dumps(s["metrics"]),
              json.dumps(s.get("warnings") or []), s["state"],
              s.get("reason"))
             for s in sensitivity])


def clear_results(run_id: int) -> None:
    with get_connection() as conn:
        for table in RESULT_TABLES:
            conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))


def mark_failed(run_id: int, error_message: str, completed_at: str) -> None:
    clear_results(run_id)
    update_run(run_id, {
        "status": "failed", "error_message": error_message,
        "completed_at": completed_at, "results": {},
        "result_fingerprint": None,
    })


def list_definitions(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signal_ensemble_definitions WHERE run_id = ? "
            "ORDER BY signal_id", (run_id,)).fetchall()
    return [{
        "signal_id": r["signal_id"], "name": r["name"],
        "definition": _json(r["definition"]),
        "definition_fingerprint": r["definition_fingerprint"],
        "orientation": r["orientation"],
        "normalisation": _json(r["normalisation"]),
        "stored_observations": r["stored_observations"],
        "coverage": r["coverage"],
    } for r in rows]


def list_pairwise(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signal_ensemble_pairwise_results "
            "WHERE run_id = ? ORDER BY signal_a, signal_b",
            (run_id,)).fetchall()
    return [{
        "signal_a": r["signal_a"], "signal_b": r["signal_b"],
        "alignment_mode": r["alignment_mode"],
        "overlap_count": r["overlap_count"],
        "coverage_a": r["coverage_a"], "coverage_b": r["coverage_b"],
        "pearson": r["pearson"], "pearson_p": r["pearson_p"],
        "spearman": r["spearman"], "spearman_p": r["spearman_p"],
        "spearman_p_adjusted": r["spearman_p_adjusted"],
        "kendall": r["kendall"], "kendall_p": r["kendall_p"],
        "mean_absolute_difference": r["mean_absolute_difference"],
        "sign_agreement_rate": r["sign_agreement_rate"],
        "zero_sign_count": r["zero_sign_count"],
        "agreement": _json(r["agreement"]),
        "tails": _json(r["tails"]),
        "correlations": _json(r["correlations"]),
        "state": r["state"], "reason": r["reason"],
    } for r in rows]


def list_observations(run_id: int, *,
                      limit: int = 2000) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signal_ensemble_observations WHERE run_id = ? "
            "ORDER BY timestamp, entity_id LIMIT ?",
            (run_id, limit)).fetchall()
    return [{
        "entity_id": r["entity_id"], "timestamp": r["timestamp"],
        "available_at": r["available_at"],
        "combined_score": r["combined_score"],
        "component_count": r["component_count"],
        "missing_signal_ids": _json(r["missing_signal_ids"]) or [],
        "state": r["state"], "reason": r["reason"],
    } for r in rows]


def list_components(run_id: int, *,
                    limit: int = 2000) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signal_ensemble_component_results "
            "WHERE run_id = ? ORDER BY timestamp, entity_id, signal_id "
            "LIMIT ?", (run_id, limit)).fetchall()
    return [{
        "entity_id": r["entity_id"], "timestamp": r["timestamp"],
        "signal_id": r["signal_id"], "raw_value": r["raw_value"],
        "oriented_value": r["oriented_value"],
        "normalised_value": r["normalised_value"],
        "configured_weight": r["configured_weight"],
        "effective_weight": r["effective_weight"],
        "contribution": r["contribution"], "sign_vote": r["sign_vote"],
        "missing": bool(r["missing"]),
    } for r in rows]


def list_horizons(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signal_ensemble_horizon_results "
            "WHERE run_id = ? "
            "ORDER BY scope, subject_id, outcome_scope, entry_lag, "
            "CAST(horizon AS INTEGER), horizon", (run_id,)).fetchall()
    return [{
        "scope": r["scope"], "subject_id": r["subject_id"],
        "horizon": r["horizon"], "entry_lag": r["entry_lag"],
        "outcome_scope": r["outcome_scope"],
        "observations": r["observations"], "pearson": r["pearson"],
        "spearman": r["spearman"], "spearman_p": r["spearman_p"],
        "spearman_p_adjusted": r["spearman_p_adjusted"],
        "mean_cross_sectional_ic": r["mean_cross_sectional_ic"],
        "top_minus_bottom": r["top_minus_bottom"],
        "cost_adjusted_spread": r["cost_adjusted_spread"],
        "overlap_ratio": r["overlap_ratio"],
        "mean_one_way_turnover": r["mean_one_way_turnover"],
        "state": r["state"], "reason": r["reason"],
        "detail": _json(r["detail"]),
    } for r in rows]


def list_leave_one_out(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signal_ensemble_leave_one_out_results "
            "WHERE run_id = ? ORDER BY omitted_signal_id",
            (run_id,)).fetchall()
    return [{
        "omitted_signal_id": r["omitted_signal_id"],
        "metrics": _json(r["metrics"]),
        "state": r["state"], "reason": r["reason"],
    } for r in rows]


def list_regimes(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signal_ensemble_regime_results "
            "WHERE run_id = ? ORDER BY regime_label", (run_id,)).fetchall()
    return [{
        "regime_label": r["regime_label"],
        "observations": r["observations"], "rare": bool(r["rare"]),
        "mean_absolute_correlation": r["mean_absolute_correlation"],
        "effective_signal_count": r["effective_signal_count"],
        "combined_spearman": r["combined_spearman"],
        "top_minus_bottom": r["top_minus_bottom"],
        "coverage": r["coverage"], "state": r["state"],
        "reason": r["reason"], "detail": _json(r["detail"]),
    } for r in rows]


def list_bootstrap(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signal_ensemble_bootstrap_results "
            "WHERE run_id = ? ORDER BY statistic", (run_id,)).fetchall()
    return [{
        "statistic": r["statistic"], "method": r["method"],
        "seed": r["seed"], "resamples": r["resamples"],
        "block_length": r["block_length"],
        "quantiles": _json(r["quantiles"]),
        "unavailable_resamples": r["unavailable_resamples"],
        "state": r["state"], "reason": r["reason"],
    } for r in rows]


def list_sensitivity(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signal_ensemble_sensitivity_results "
            "WHERE run_id = ? ORDER BY scenario_index",
            (run_id,)).fetchall()
    return [{
        "scenario_index": r["scenario_index"],
        "is_base": bool(r["is_base"]), "label": r["label"],
        "scenario": _json(r["scenario"]),
        "scenario_fingerprint": r["scenario_fingerprint"],
        "metrics": _json(r["metrics"]),
        "warnings": _json(r["warnings"]) or [],
        "state": r["state"], "reason": r["reason"],
    } for r in rows]


def mark_baseline(run_id: int, scope: str) -> None:
    """Transactional same-scope replacement; unrelated baselines preserved."""
    now = _now()
    with get_connection() as conn:
        conn.execute(
            "UPDATE signal_ensemble_runs SET is_baseline = 0, "
            "updated_at = ? WHERE baseline_scope = ? AND id != ?",
            (now, scope, run_id))
        conn.execute(
            "UPDATE signal_ensemble_runs SET is_baseline = 1, "
            "baseline_scope = ?, updated_at = ? WHERE id = ?",
            (scope, now, run_id))


def lab_summary() -> Dict[str, Any]:
    with get_connection() as conn:
        runs = conn.execute(
            "SELECT COUNT(*) AS c FROM signal_ensemble_runs").fetchone()["c"]
        completed = conn.execute(
            "SELECT COUNT(*) AS c FROM signal_ensemble_runs "
            "WHERE status = 'completed'").fetchone()["c"]
        signals = conn.execute(
            "SELECT COALESCE(SUM(signal_count), 0) AS c "
            "FROM signal_ensemble_runs").fetchone()["c"]
        observations = conn.execute(
            "SELECT COALESCE(SUM(observation_count), 0) AS c "
            "FROM signal_ensemble_runs").fetchone()["c"]
        pairwise = conn.execute(
            "SELECT COUNT(*) AS c FROM signal_ensemble_pairwise_results"
        ).fetchone()["c"]
        baselines = conn.execute(
            "SELECT COUNT(*) AS c FROM signal_ensemble_runs "
            "WHERE is_baseline = 1").fetchone()["c"]
    return {"runs": runs, "completed": completed, "signals": signals,
            "observations": observations, "pairwise_rows": pairwise,
            "baselines": baselines}


__all__ = [
    "DEFAULT_PAGE_SIZE", "MAX_PAGE_SIZE", "CHILD_TABLES", "RESULT_TABLES",
    "insert_run", "get_run", "run_demo_key_id", "update_run", "list_runs",
    "replace_children", "clear_results", "mark_failed", "list_definitions",
    "list_pairwise", "list_observations", "list_components",
    "list_horizons", "list_leave_one_out", "list_regimes", "list_bootstrap",
    "list_sensitivity", "mark_baseline", "lab_summary",
]
