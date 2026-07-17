"""SQLite persistence for the Meta-Labeling Lab (parameterised SQL only)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.db import get_connection

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
SORTABLE = frozenset({"created_at", "updated_at", "name", "status", "calibration_method"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _run_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"], "created_at": row["created_at"], "updated_at": row["updated_at"],
        "name": row["name"], "description": row["description"], "status": row["status"],
        "label_policy": json.loads(row["label_policy_json"]),
        "calibration_method": row["calibration_method"], "oof_status": row["oof_status"],
        "validation_run_id": row["validation_run_id"],
        "dataset_version_id": row["dataset_version_id"],
        "experiment_id": row["experiment_id"],
        "configuration": json.loads(row["configuration_json"]),
        "configuration_fingerprint": row["configuration_fingerprint"],
        "result_fingerprint": row["result_fingerprint"],
        "observation_count": row["observation_count"],
        "labeled_count": row["labeled_count"], "positive_count": row["positive_count"],
        "abstained_count": row["abstained_count"],
        "raw_metrics": json.loads(row["raw_metrics_json"]),
        "calibrated_metrics": json.loads(row["calibrated_metrics_json"]),
        "calibration_params": json.loads(row["calibration_params_json"]),
        "threshold_analysis": json.loads(row["threshold_analysis_json"]),
        "completed_at": row["completed_at"], "duration_ms": row["duration_ms"],
        "app_version": row["app_version"], "git_commit": row["git_commit"],
        "notes": row["notes"], "error_message": row["error_message"],
    }


def insert_run(fields: Dict[str, Any]) -> Dict[str, Any]:
    now = _now()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO meta_label_runs (
                created_at, updated_at, name, description, status,
                label_policy_json, calibration_method, oof_status,
                validation_run_id, dataset_version_id, experiment_id,
                configuration_json, configuration_fingerprint,
                observation_count, app_version, git_commit, notes, demo_key
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                now, now, fields["name"], fields.get("description", ""), "pending",
                json.dumps(fields.get("label_policy", {})),
                fields.get("calibration_method", "none"),
                fields.get("oof_status", "unknown"),
                fields.get("validation_run_id"), fields.get("dataset_version_id"),
                fields.get("experiment_id"),
                json.dumps(fields.get("configuration", {})),
                fields["configuration_fingerprint"],
                fields.get("observation_count", 0),
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
        row = conn.execute("SELECT * FROM meta_label_runs WHERE id = ?", (run_id,)).fetchone()
    return _run_row(row) if row else None


def run_demo_key_id(demo_key: str) -> Optional[int]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM meta_label_runs WHERE demo_key = ?", (demo_key,)
        ).fetchone()
    return int(row["id"]) if row else None


def update_run(run_id: int, columns: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    allowed = {
        "status", "oof_status", "result_fingerprint", "labeled_count",
        "positive_count", "abstained_count", "raw_metrics_json",
        "calibrated_metrics_json", "calibration_params_json",
        "threshold_analysis_json", "completed_at", "duration_ms",
        "experiment_id", "error_message", "notes",
    }
    updates = {k: v for k, v in columns.items() if k in allowed}
    if not updates:
        return get_run(run_id)
    set_clause = ", ".join(f"{c} = ?" for c in updates)
    with get_connection() as conn:
        cur = conn.execute(
            f"UPDATE meta_label_runs SET {set_clause}, updated_at = ? WHERE id = ?",
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
        ("status", "status"), ("calibration_method", "calibration_method"),
        ("oof_status", "oof_status"), ("validation_run_id", "validation_run_id"),
        ("dataset_version_id", "dataset_version_id"),
        ("configuration_fingerprint", "configuration_fingerprint"),
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
            f"SELECT COUNT(*) AS c FROM meta_label_runs{where}", params).fetchone()["c"])
        rows = conn.execute(
            f"SELECT * FROM meta_label_runs{where} ORDER BY {sort_by} {sort_dir.upper()}, "
            f"id {sort_dir.upper()} LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size]).fetchall()
    return {"items": [_run_row(r) for r in rows], "total": total, "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total else 0}


# --- observations ----------------------------------------------------------


def replace_observations(run_id: int, observations: List[Dict[str, Any]]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM meta_label_observations WHERE run_id = ?", (run_id,))
        for o in observations:
            conn.execute(
                """
                INSERT INTO meta_label_observations (
                    run_id, sample_id, prediction_time, evaluation_time,
                    primary_side, primary_score, raw_probability,
                    calibrated_probability, realized_outcome, meta_label,
                    abstained, sample_weight, split_label, metadata_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (run_id, o["sample_id"], o["prediction_time"], o["evaluation_time"],
                 o["primary_side"], o.get("primary_score"), o.get("raw_probability"),
                 o.get("calibrated_probability"), o.get("realized_outcome"),
                 o.get("meta_label"), 1 if o.get("abstained") else 0,
                 o.get("sample_weight"), o.get("split_label"),
                 json.dumps(o.get("metadata", {}))),
            )
        conn.commit()


def list_observations(run_id: int, *, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), 200))
    with get_connection() as conn:
        total = int(conn.execute(
            "SELECT COUNT(*) AS c FROM meta_label_observations WHERE run_id = ?",
            (run_id,)).fetchone()["c"])
        rows = conn.execute(
            "SELECT * FROM meta_label_observations WHERE run_id = ? "
            "ORDER BY prediction_time, sample_id LIMIT ? OFFSET ?",
            (run_id, page_size, (page - 1) * page_size)).fetchall()
    items = [{
        "sample_id": r["sample_id"], "prediction_time": r["prediction_time"],
        "evaluation_time": r["evaluation_time"], "primary_side": r["primary_side"],
        "primary_score": r["primary_score"], "raw_probability": r["raw_probability"],
        "calibrated_probability": r["calibrated_probability"],
        "realized_outcome": r["realized_outcome"], "meta_label": r["meta_label"],
        "abstained": bool(r["abstained"]), "sample_weight": r["sample_weight"],
        "split_label": r["split_label"], "metadata": json.loads(r["metadata_json"]),
    } for r in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total else 0}


def all_observations(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM meta_label_observations WHERE run_id = ? "
            "ORDER BY prediction_time, sample_id", (run_id,)).fetchall()
    return [{
        "sample_id": r["sample_id"], "prediction_time": r["prediction_time"],
        "evaluation_time": r["evaluation_time"], "primary_side": r["primary_side"],
        "primary_score": r["primary_score"], "raw_probability": r["raw_probability"],
        "calibrated_probability": r["calibrated_probability"],
        "realized_outcome": r["realized_outcome"], "meta_label": r["meta_label"],
        "abstained": bool(r["abstained"]), "sample_weight": r["sample_weight"],
        "split_label": r["split_label"], "metadata": json.loads(r["metadata_json"]),
    } for r in rows]


# --- bins ------------------------------------------------------------------


def replace_bins(run_id: int, source: str, bins: List[Dict[str, Any]]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM calibration_bins WHERE run_id = ? AND source = ?",
                     (run_id, source))
        for b in bins:
            conn.execute(
                """
                INSERT INTO calibration_bins (
                    run_id, source, bin_index, lower_bound, upper_bound,
                    sample_count, mean_probability, observed_frequency, calibration_gap
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (run_id, source, b["bin_index"], b["lower_bound"], b["upper_bound"],
                 b["sample_count"], b["mean_probability"], b["observed_frequency"],
                 b["calibration_gap"]),
            )
        conn.commit()


def list_bins(run_id: int) -> Dict[str, List[Dict[str, Any]]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM calibration_bins WHERE run_id = ? ORDER BY source, bin_index",
            (run_id,)).fetchall()
    out: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(r["source"], []).append({
            "bin_index": r["bin_index"], "lower_bound": r["lower_bound"],
            "upper_bound": r["upper_bound"], "sample_count": r["sample_count"],
            "mean_probability": r["mean_probability"],
            "observed_frequency": r["observed_frequency"],
            "calibration_gap": r["calibration_gap"],
        })
    return out


# --- threshold policies ----------------------------------------------------


def _policy_row(r) -> Dict[str, Any]:
    return {
        "id": r["id"], "created_at": r["created_at"], "updated_at": r["updated_at"],
        "run_id": r["run_id"], "name": r["name"], "threshold": r["threshold"],
        "abstention": json.loads(r["abstention_json"]) if r["abstention_json"] else None,
        "configuration_fingerprint": r["configuration_fingerprint"],
        "observed_coverage": r["observed_coverage"],
        "observed_precision": r["observed_precision"],
        "observed_recall": r["observed_recall"], "observed_f1": r["observed_f1"],
        "is_baseline": bool(r["is_baseline"]), "notes": r["notes"],
    }


def insert_policy(fields: Dict[str, Any]) -> Dict[str, Any]:
    now = _now()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO threshold_policies (
                created_at, updated_at, run_id, name, threshold, abstention_json,
                configuration_fingerprint, observed_coverage, observed_precision,
                observed_recall, observed_f1, notes
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (now, now, fields["run_id"], fields["name"], fields["threshold"],
             json.dumps(fields["abstention"]) if fields.get("abstention") else None,
             fields["configuration_fingerprint"], fields.get("observed_coverage"),
             fields.get("observed_precision"), fields.get("observed_recall"),
             fields.get("observed_f1"), fields.get("notes", "")),
        )
        conn.commit()
        new_id = int(cur.lastrowid)  # type: ignore[arg-type]
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM threshold_policies WHERE id = ?", (new_id,)).fetchone()
    return _policy_row(row)


def get_policy(policy_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM threshold_policies WHERE id = ?", (policy_id,)).fetchone()
    return _policy_row(row) if row else None


def list_policies(run_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM threshold_policies WHERE run_id = ? ORDER BY threshold, id",
            (run_id,)).fetchall()
    return [_policy_row(r) for r in rows]


def all_policies() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM threshold_policies ORDER BY id").fetchall()
    return [_policy_row(r) for r in rows]


def mark_policy_baseline(policy_id: int, run_id: int) -> None:
    """One active baseline policy per run (transactional replacement)."""
    now = _now()
    with get_connection() as conn:
        conn.execute(
            "UPDATE threshold_policies SET is_baseline = 0, updated_at = ? "
            "WHERE run_id = ? AND is_baseline = 1 AND id != ?",
            (now, run_id, policy_id))
        conn.execute(
            "UPDATE threshold_policies SET is_baseline = 1, updated_at = ? WHERE id = ?",
            (now, policy_id))
        conn.commit()


def lab_summary() -> Dict[str, Any]:
    with get_connection() as conn:
        runs = int(conn.execute("SELECT COUNT(*) AS c FROM meta_label_runs").fetchone()["c"])
        completed = int(conn.execute(
            "SELECT COUNT(*) AS c FROM meta_label_runs WHERE status='completed'").fetchone()["c"])
        oof = int(conn.execute(
            "SELECT COUNT(*) AS c FROM meta_label_runs WHERE oof_status='verified_from_validation_run'"
        ).fetchone()["c"])
        calibrated = int(conn.execute(
            "SELECT COUNT(*) AS c FROM meta_label_runs WHERE calibration_method != 'none' "
            "AND status='completed'").fetchone()["c"])
        policies = int(conn.execute("SELECT COUNT(*) AS c FROM threshold_policies").fetchone()["c"])
        baselines = int(conn.execute(
            "SELECT COUNT(*) AS c FROM threshold_policies WHERE is_baseline=1").fetchone()["c"])
        methods = conn.execute(
            "SELECT calibration_method AS m, COUNT(*) AS c FROM meta_label_runs "
            "GROUP BY calibration_method").fetchall()
    return {"runs": runs, "completed": completed, "oof_verified": oof,
            "calibrated": calibrated, "threshold_policies": policies,
            "baselines": baselines,
            "methods": {r["m"]: int(r["c"]) for r in methods}}


__all__ = [
    "DEFAULT_PAGE_SIZE", "MAX_PAGE_SIZE", "SORTABLE",
    "insert_run", "get_run", "run_demo_key_id", "update_run", "list_runs",
    "replace_observations", "list_observations", "all_observations",
    "replace_bins", "list_bins", "insert_policy", "get_policy",
    "list_policies", "all_policies", "mark_policy_baseline", "lab_summary",
]
