"""SQLite persistence for the Signal Decay Lab (parameterised SQL)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.db import get_connection

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
SORTABLE = frozenset({"created_at", "updated_at", "name", "status",
                      "signal_type", "integrity_status",
                      "completeness_status", "overlap_status",
                      "observation_count", "horizon_count",
                      "first_horizon_rank_ic", "mean_one_way_turnover"})

CHILD_TABLES = ("signal_definitions", "signal_observations",
                "signal_horizon_results", "signal_bucket_results",
                "signal_turnover_results", "signal_regime_results",
                "signal_bootstrap_results")

RESULT_TABLES = ("signal_horizon_results", "signal_bucket_results",
                 "signal_turnover_results", "signal_regime_results",
                 "signal_bootstrap_results")

RUN_UPDATE_COLUMNS = frozenset({
    "status", "signal_id", "signal_type", "outcome_id",
    "outcome_target_type", "frequency", "entity_count", "observation_count",
    "horizon_count", "lag_count", "observation_start", "observation_end",
    "integrity_status", "completeness_status", "overlap_status",
    "first_horizon_rank_ic", "mean_one_way_turnover", "configuration",
    "results", "signal_fingerprint", "outcome_fingerprint",
    "universe_fingerprint", "horizon_fingerprint", "analysis_fingerprint",
    "configuration_fingerprint", "result_fingerprint", "dataset_version_id",
    "feature_run_id", "meta_label_run_id", "validation_run_id",
    "regime_run_id", "cost_diagnostic_run_id", "factor_run_id",
    "experiment_id", "is_baseline", "baseline_scope", "app_version",
    "git_commit", "notes", "error_message", "started_at", "completed_at",
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
        "signal_id": row["signal_id"], "signal_type": row["signal_type"],
        "outcome_id": row["outcome_id"],
        "outcome_target_type": row["outcome_target_type"],
        "frequency": row["frequency"],
        "entity_count": row["entity_count"],
        "observation_count": row["observation_count"],
        "horizon_count": row["horizon_count"],
        "lag_count": row["lag_count"],
        "observation_start": row["observation_start"],
        "observation_end": row["observation_end"],
        "integrity_status": row["integrity_status"],
        "completeness_status": row["completeness_status"],
        "overlap_status": row["overlap_status"],
        "first_horizon_rank_ic": row["first_horizon_rank_ic"],
        "mean_one_way_turnover": row["mean_one_way_turnover"],
        "configuration": _json(row["configuration"]) or {},
        "results": _json(row["results"]) or {},
        "signal_fingerprint": row["signal_fingerprint"],
        "outcome_fingerprint": row["outcome_fingerprint"],
        "universe_fingerprint": row["universe_fingerprint"],
        "horizon_fingerprint": row["horizon_fingerprint"],
        "analysis_fingerprint": row["analysis_fingerprint"],
        "configuration_fingerprint": row["configuration_fingerprint"],
        "result_fingerprint": row["result_fingerprint"],
        "dataset_version_id": row["dataset_version_id"],
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
            INSERT INTO signal_decay_runs (
                created_at, updated_at, name, description, status, signal_id,
                signal_type, outcome_id, outcome_target_type, frequency,
                entity_count, observation_count, horizon_count, lag_count,
                observation_start, observation_end, integrity_status,
                completeness_status, overlap_status, configuration,
                signal_fingerprint, outcome_fingerprint,
                universe_fingerprint, horizon_fingerprint,
                analysis_fingerprint, configuration_fingerprint,
                dataset_version_id, feature_run_id, meta_label_run_id,
                validation_run_id, regime_run_id, cost_diagnostic_run_id,
                factor_run_id, app_version, git_commit, notes, demo_key
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                      ?,?,?,?,?,?,?,?,?,?)
            """,
            (now, now, fields["name"], fields.get("description", ""),
             fields.get("status", "pending"), fields["signal_id"],
             fields["signal_type"], fields["outcome_id"],
             fields["outcome_target_type"],
             fields.get("frequency", "daily"),
             fields.get("entity_count", 0),
             fields.get("observation_count", 0),
             fields.get("horizon_count", 0), fields.get("lag_count", 0),
             fields.get("observation_start"), fields.get("observation_end"),
             fields.get("integrity_status", "unknown"),
             fields.get("completeness_status", "unavailable"),
             fields.get("overlap_status"),
             json.dumps(fields.get("configuration") or {}),
             fields["signal_fingerprint"], fields["outcome_fingerprint"],
             fields["universe_fingerprint"], fields["horizon_fingerprint"],
             fields["analysis_fingerprint"],
             fields["configuration_fingerprint"],
             fields.get("dataset_version_id"), fields.get("feature_run_id"),
             fields.get("meta_label_run_id"), fields.get("validation_run_id"),
             fields.get("regime_run_id"),
             fields.get("cost_diagnostic_run_id"),
             fields.get("factor_run_id"), fields.get("app_version"),
             fields.get("git_commit"), fields.get("notes", ""),
             fields.get("demo_key")))
        run_id = int(cursor.lastrowid)
        conn.commit()
    return get_run(run_id)  # type: ignore[return-value]


def get_run(run_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM signal_decay_runs WHERE id = ?",
            (run_id,)).fetchone()
    return _run_row(row) if row else None


def run_demo_key_id(demo_key: str) -> Optional[int]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM signal_decay_runs WHERE demo_key = ?",
            (demo_key,)).fetchone()
    return int(row["id"]) if row else None


def update_run(run_id: int, columns: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    unknown = sorted(set(columns) - RUN_UPDATE_COLUMNS)
    if unknown:
        raise ValueError(f"unsupported run columns: {unknown}")
    if not columns:
        return get_run(run_id)
    assignments = ", ".join(f"{name} = ?" for name in columns)
    values = [json.dumps(v) if name in _JSON_COLUMNS else v
              for name, v in columns.items()]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE signal_decay_runs SET {assignments}, updated_at = ? "
            f"WHERE id = ?", (*values, _now(), run_id))
        conn.commit()
    return get_run(run_id)


def _where(filters: Dict[str, Any]) -> Tuple[str, List[Any]]:
    clauses: List[str] = []
    params: List[Any] = []
    for column in ("status", "signal_type", "outcome_target_type",
                   "integrity_status", "completeness_status",
                   "overlap_status"):
        value = filters.get(column)
        if value:
            clauses.append(f"{column} = ?")
            params.append(value)
    if filters.get("is_baseline") is not None:
        clauses.append("is_baseline = ?")
        params.append(1 if filters["is_baseline"] else 0)
    query = filters.get("query")
    if query:
        clauses.append(
            "(name LIKE ? OR description LIKE ? OR signal_id LIKE ?)")
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
            f"SELECT COUNT(*) AS c FROM signal_decay_runs{where}",
            params).fetchone()["c"])
        rows = conn.execute(
            f"SELECT * FROM signal_decay_runs{where} "
            f"ORDER BY {sort_by} {direction}, id {direction} LIMIT ? OFFSET ?",
            (*params, page_size, (page - 1) * page_size)).fetchall()
    return {"items": [_run_row(r) for r in rows], "total": total,
            "page": page, "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size)}


def replace_children(run_id: int, *,
                     definition: Dict[str, Any],
                     observations: List[Dict[str, Any]],
                     horizon_rows: List[Dict[str, Any]],
                     bucket_rows: List[Dict[str, Any]],
                     turnover_rows: List[Dict[str, Any]],
                     regime_rows: List[Dict[str, Any]],
                     bootstrap_rows: List[Dict[str, Any]],
                     run_columns: Dict[str, Any]) -> None:
    unknown = sorted(set(run_columns) - RUN_UPDATE_COLUMNS)
    if unknown:
        raise ValueError(f"unsupported run columns: {unknown}")
    with get_connection() as conn:
        try:
            conn.execute("BEGIN")
            for table in CHILD_TABLES:
                conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))
            conn.execute(
                """
                INSERT INTO signal_definitions (
                    run_id, signal_id, name, description, signal_type,
                    source, unit, frequency, direction, availability_policy,
                    transformation, missing_policy, tie_policy,
                    dataset_version_id, feature_run_id, meta_label_run_id,
                    factor_run_id, definition_fingerprint, outcome_json,
                    metadata_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (run_id, definition["signal_id"], definition["name"],
                 definition.get("description", ""),
                 definition["signal_type"], definition["source"],
                 definition["unit"], definition["frequency"],
                 definition["direction"], definition["availability_policy"],
                 definition["transformation"], definition["missing_policy"],
                 definition["tie_policy"],
                 definition.get("dataset_version_id"),
                 definition.get("feature_run_id"),
                 definition.get("meta_label_run_id"),
                 definition.get("factor_run_id"),
                 definition["definition_fingerprint"],
                 json.dumps(definition.get("outcome") or {}),
                 json.dumps(definition.get("metadata") or {})))
            for o in observations:
                conn.execute(
                    """
                    INSERT INTO signal_observations (
                        run_id, observation_id, entity_id, source_timestamp,
                        generated_at, available_at, availability_assumed,
                        raw_value, rank_value, universe_membership_id
                    ) VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, o["observation_id"], o["entity_id"],
                     o["source_timestamp"], o.get("generated_at"),
                     o["available_at"],
                     1 if o.get("availability_assumed") else 0,
                     o.get("raw_value"), o.get("rank_value"),
                     o.get("universe_membership_id")))
            for r in horizon_rows:
                conn.execute(
                    """
                    INSERT INTO signal_horizon_results (
                        run_id, horizon, entry_lag, selection, outcome_scope,
                        observations, unavailable_count, pearson,
                        pearson_p_value, spearman, spearman_p_value,
                        spearman_p_adjusted, kendall, kendall_p_value,
                        mean_cross_sectional_ic, ic_ratio, top_minus_bottom,
                        cost_adjusted_spread, monotonicity_spearman,
                        overlap_ratio, max_simultaneous_overlap,
                        effective_non_overlapping, overlap_state,
                        p_value_note, state, reason, detail_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                              ?,?,?,?)
                    """,
                    (run_id, str(r["horizon"]), r["entry_lag"],
                     r.get("selection", "overlapping"),
                     r.get("outcome_scope", "raw"), r["observations"],
                     r.get("unavailable_count", 0), r.get("pearson"),
                     r.get("pearson_p_value"), r.get("spearman"),
                     r.get("spearman_p_value"), r.get("spearman_p_adjusted"),
                     r.get("kendall"), r.get("kendall_p_value"),
                     r.get("mean_cross_sectional_ic"), r.get("ic_ratio"),
                     r.get("top_minus_bottom"), r.get("cost_adjusted_spread"),
                     r.get("monotonicity_spearman"), r.get("overlap_ratio"),
                     r.get("max_simultaneous_overlap"),
                     r.get("effective_non_overlapping"),
                     r.get("overlap_state"), r.get("p_value_note"),
                     r["state"], r.get("reason"),
                     json.dumps(r.get("detail") or {})))
            for b in bucket_rows:
                conn.execute(
                    """
                    INSERT INTO signal_bucket_results (
                        run_id, horizon, entry_lag, outcome_scope, bucket,
                        observations, score_minimum, score_maximum,
                        mean_outcome, median_outcome, std_outcome,
                        positive_rate, state, reason
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, str(b["horizon"]), b["entry_lag"],
                     b.get("outcome_scope", "raw"), b["bucket"],
                     b["observations"], b.get("score_minimum"),
                     b.get("score_maximum"), b.get("mean_outcome"),
                     b.get("median_outcome"), b.get("std_outcome"),
                     b.get("positive_rate"), b["state"], b.get("reason")))
            for t in turnover_rows:
                conn.execute(
                    """
                    INSERT INTO signal_turnover_results (
                        run_id, horizon, entry_lag, timestamp, universe_size,
                        top_size, bottom_size, top_entries, top_exits,
                        bottom_entries, bottom_exits, jaccard_top,
                        one_way_turnover, cost, cost_return, cost_state
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, str(t["horizon"]), t["entry_lag"],
                     t["timestamp"], t["universe_size"], t["top_size"],
                     t["bottom_size"], t["top_entries"], t["top_exits"],
                     t["bottom_entries"], t["bottom_exits"],
                     t.get("jaccard_top"), t.get("one_way_turnover"),
                     t.get("cost"), t.get("cost_return"),
                     t.get("cost_state")))
            for g in regime_rows:
                conn.execute(
                    """
                    INSERT INTO signal_regime_results (
                        run_id, regime_label, horizon, entry_lag,
                        observations, rare, pearson, spearman,
                        top_minus_bottom, overlap_ratio, state, reason
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, g["regime_label"], str(g["horizon"]),
                     g["entry_lag"], g["observations"],
                     1 if g.get("rare") else 0, g.get("pearson"),
                     g.get("spearman"), g.get("top_minus_bottom"),
                     g.get("overlap_ratio"), g["state"], g.get("reason")))
            for b in bootstrap_rows:
                conn.execute(
                    """
                    INSERT INTO signal_bootstrap_results (
                        run_id, horizon, entry_lag, statistic, method, seed,
                        resamples, valid_resamples, observed, quantiles_json,
                        state, reason
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (run_id, str(b["horizon"]), b["entry_lag"],
                     b["statistic"], b["method"], b["seed"], b["resamples"],
                     b.get("valid_resamples", 0), b.get("observed"),
                     json.dumps(b.get("quantiles") or {}), b["state"],
                     b.get("reason")))
            if run_columns:
                assignments = ", ".join(f"{name} = ?" for name in run_columns)
                values = [json.dumps(v) if name in _JSON_COLUMNS else v
                          for name, v in run_columns.items()]
                conn.execute(
                    f"UPDATE signal_decay_runs SET {assignments}, "
                    f"updated_at = ? WHERE id = ?",
                    (*values, _now(), run_id))
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
                UPDATE signal_decay_runs
                   SET status = 'failed', error_message = ?, completed_at = ?,
                       updated_at = ?, result_fingerprint = NULL,
                       results = NULL, first_horizon_rank_ic = NULL,
                       mean_one_way_turnover = NULL,
                       completeness_status = 'unavailable', is_baseline = 0,
                       baseline_scope = NULL
                 WHERE id = ?
                """,
                (error_message[:2000], completed_at, _now(), run_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def get_definition(run_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        r = conn.execute(
            "SELECT * FROM signal_definitions WHERE run_id = ?",
            (run_id,)).fetchone()
    if not r:
        return None
    return {
        "signal_id": r["signal_id"], "name": r["name"],
        "description": r["description"], "signal_type": r["signal_type"],
        "source": r["source"], "unit": r["unit"],
        "frequency": r["frequency"], "direction": r["direction"],
        "availability_policy": r["availability_policy"],
        "transformation": r["transformation"],
        "missing_policy": r["missing_policy"], "tie_policy": r["tie_policy"],
        "dataset_version_id": r["dataset_version_id"],
        "feature_run_id": r["feature_run_id"],
        "meta_label_run_id": r["meta_label_run_id"],
        "factor_run_id": r["factor_run_id"],
        "definition_fingerprint": r["definition_fingerprint"],
        "outcome": _json(r["outcome_json"]) or {},
        "metadata": _json(r["metadata_json"]) or {},
    }


def list_observations(run_id: int, *, limit: int = 2000) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit), 20000))
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signal_observations WHERE run_id = ? "
            "ORDER BY entity_id, source_timestamp LIMIT ?",
            (run_id, limit)).fetchall()
    return [{
        "observation_id": r["observation_id"], "entity_id": r["entity_id"],
        "source_timestamp": r["source_timestamp"],
        "generated_at": r["generated_at"], "available_at": r["available_at"],
        "availability_assumed": bool(r["availability_assumed"]),
        "raw_value": r["raw_value"], "rank_value": r["rank_value"],
        "universe_membership_id": r["universe_membership_id"],
    } for r in rows]


def list_horizons(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signal_horizon_results WHERE run_id = ? "
            "ORDER BY outcome_scope, selection, entry_lag, "
            "LENGTH(horizon), horizon", (run_id,)).fetchall()
    return [{
        "horizon": (int(r["horizon"]) if r["horizon"].isdigit()
                    else r["horizon"]),
        "entry_lag": r["entry_lag"], "selection": r["selection"],
        "outcome_scope": r["outcome_scope"],
        "observations": r["observations"],
        "unavailable_count": r["unavailable_count"],
        "pearson": r["pearson"], "pearson_p_value": r["pearson_p_value"],
        "spearman": r["spearman"],
        "spearman_p_value": r["spearman_p_value"],
        "spearman_p_adjusted": r["spearman_p_adjusted"],
        "kendall": r["kendall"], "kendall_p_value": r["kendall_p_value"],
        "mean_cross_sectional_ic": r["mean_cross_sectional_ic"],
        "ic_ratio": r["ic_ratio"], "top_minus_bottom": r["top_minus_bottom"],
        "cost_adjusted_spread": r["cost_adjusted_spread"],
        "monotonicity_spearman": r["monotonicity_spearman"],
        "overlap_ratio": r["overlap_ratio"],
        "max_simultaneous_overlap": r["max_simultaneous_overlap"],
        "effective_non_overlapping": r["effective_non_overlapping"],
        "overlap_state": r["overlap_state"],
        "p_value_note": r["p_value_note"], "state": r["state"],
        "reason": r["reason"], "detail": _json(r["detail_json"]) or {},
    } for r in rows]


def list_buckets(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signal_bucket_results WHERE run_id = ? "
            "ORDER BY outcome_scope, entry_lag, LENGTH(horizon), horizon, "
            "bucket", (run_id,)).fetchall()
    return [{
        "horizon": (int(r["horizon"]) if r["horizon"].isdigit()
                    else r["horizon"]),
        "entry_lag": r["entry_lag"], "outcome_scope": r["outcome_scope"],
        "bucket": r["bucket"], "observations": r["observations"],
        "score_minimum": r["score_minimum"],
        "score_maximum": r["score_maximum"],
        "mean_outcome": r["mean_outcome"],
        "median_outcome": r["median_outcome"],
        "std_outcome": r["std_outcome"], "positive_rate": r["positive_rate"],
        "state": r["state"], "reason": r["reason"],
    } for r in rows]


def list_turnover(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signal_turnover_results WHERE run_id = ? "
            "ORDER BY entry_lag, LENGTH(horizon), horizon, timestamp",
            (run_id,)).fetchall()
    return [{
        "horizon": (int(r["horizon"]) if r["horizon"].isdigit()
                    else r["horizon"]),
        "entry_lag": r["entry_lag"], "timestamp": r["timestamp"],
        "universe_size": r["universe_size"], "top_size": r["top_size"],
        "bottom_size": r["bottom_size"], "top_entries": r["top_entries"],
        "top_exits": r["top_exits"], "bottom_entries": r["bottom_entries"],
        "bottom_exits": r["bottom_exits"], "jaccard_top": r["jaccard_top"],
        "one_way_turnover": r["one_way_turnover"], "cost": r["cost"],
        "cost_return": r["cost_return"], "cost_state": r["cost_state"],
    } for r in rows]


def list_regimes(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signal_regime_results WHERE run_id = ? "
            "ORDER BY regime_label, LENGTH(horizon), horizon, entry_lag",
            (run_id,)).fetchall()
    return [{
        "regime_label": r["regime_label"],
        "horizon": (int(r["horizon"]) if r["horizon"].isdigit()
                    else r["horizon"]),
        "entry_lag": r["entry_lag"], "observations": r["observations"],
        "rare": bool(r["rare"]), "pearson": r["pearson"],
        "spearman": r["spearman"], "top_minus_bottom": r["top_minus_bottom"],
        "overlap_ratio": r["overlap_ratio"], "state": r["state"],
        "reason": r["reason"],
    } for r in rows]


def list_bootstrap(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signal_bootstrap_results WHERE run_id = ? "
            "ORDER BY LENGTH(horizon), horizon, entry_lag, statistic",
            (run_id,)).fetchall()
    return [{
        "horizon": (int(r["horizon"]) if r["horizon"].isdigit()
                    else r["horizon"]),
        "entry_lag": r["entry_lag"], "statistic": r["statistic"],
        "method": r["method"], "seed": r["seed"], "resamples": r["resamples"],
        "valid_resamples": r["valid_resamples"], "observed": r["observed"],
        "quantiles": _json(r["quantiles_json"]) or {},
        "state": r["state"], "reason": r["reason"],
    } for r in rows]


def mark_baseline(run_id: int, scope: str) -> None:
    with get_connection() as conn:
        try:
            conn.execute("BEGIN")
            conn.execute(
                "UPDATE signal_decay_runs SET is_baseline = 0, "
                "updated_at = ? WHERE baseline_scope = ? AND id != ?",
                (_now(), scope, run_id))
            conn.execute(
                "UPDATE signal_decay_runs SET is_baseline = 1, "
                "baseline_scope = ?, updated_at = ? WHERE id = ?",
                (scope, _now(), run_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def lab_summary() -> Dict[str, Any]:
    with get_connection() as conn:
        runs = int(conn.execute(
            "SELECT COUNT(*) AS c FROM signal_decay_runs").fetchone()["c"])
        completed = int(conn.execute(
            "SELECT COUNT(*) AS c FROM signal_decay_runs "
            "WHERE status = 'completed'").fetchone()["c"])
        signals = int(conn.execute(
            "SELECT COUNT(*) AS c FROM signal_definitions").fetchone()["c"])
        observations = int(conn.execute(
            "SELECT COUNT(*) AS c FROM signal_observations").fetchone()["c"])
        horizons = int(conn.execute(
            "SELECT COUNT(*) AS c FROM signal_horizon_results "
            "WHERE outcome_scope = 'raw' AND selection = 'overlapping'"
        ).fetchone()["c"])
        overlapping = int(conn.execute(
            "SELECT COUNT(*) AS c FROM signal_decay_runs "
            "WHERE overlap_status IN ('overlapping', 'partially_overlapping')"
        ).fetchone()["c"])
        baselines = int(conn.execute(
            "SELECT COUNT(*) AS c FROM signal_decay_runs "
            "WHERE is_baseline = 1").fetchone()["c"])
    return {"runs": runs, "completed": completed, "signals": signals,
            "observations": observations, "horizon_rows": horizons,
            "overlapping_runs": overlapping, "baselines": baselines}


__all__ = [
    "DEFAULT_PAGE_SIZE", "MAX_PAGE_SIZE", "SORTABLE", "CHILD_TABLES",
    "RESULT_TABLES", "insert_run", "get_run", "run_demo_key_id",
    "update_run", "list_runs", "replace_children", "mark_failed",
    "get_definition", "list_observations", "list_horizons", "list_buckets",
    "list_turnover", "list_regimes", "list_bootstrap", "mark_baseline",
    "lab_summary",
]
