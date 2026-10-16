"""One bounded SQLite read transaction; no registry readers with writable opens."""
import sqlite3
from contextlib import closing

from app import db
from app.run_replay import identity as replay_identity, service as replay
from .contract import FIELDS, render, verify


class Missing(LookupError):
    pass


class Unavailable(ValueError):
    pass


class Changed(ValueError):
    pass


def acquire(saved_id):
    replay.positive_id(saved_id)
    path = db.get_db_path().absolute()
    if not path.is_file():
        raise Missing("Stored source is unavailable")
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            conn.execute("BEGIN")
            conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 5 * 1024 * 1024)
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('saved_backtests','run_replay_contexts')")}
            if "saved_backtests" not in tables:
                raise Unavailable("Stored source schema is unavailable")
            sizes = conn.execute("""SELECT length(CAST(params_json AS BLOB)) + length(CAST(metrics_json AS BLOB)) +
                length(CAST(equity_curve_json AS BLOB)) + length(CAST(trades_json AS BLOB)) +
                length(CAST(ticker AS BLOB)) + length(CAST(strategy AS BLOB)) + length(CAST(created_at AS BLOB))
                FROM saved_backtests WHERE id=?""", (saved_id,)).fetchone()
            if sizes is None:
                raise Missing("Stored source not found")
            if sizes[0] is None or sizes[0] > 4 * 1024 * 1024:
                raise Unavailable("Stored source exceeds supported bounds")
            # Code-owned columns only. Names/notes/locators are deliberately not read.
            columns = {r[1] for r in conn.execute("PRAGMA table_info(saved_backtests)")}
            if len({"config_hash_full", "config_schema"} & columns) == 1:
                raise Unavailable("Stored index schema is incomplete")
            optional = ", config_hash_full, config_schema" if {"config_hash_full", "config_schema"} <= columns else ""
            row = dict(conn.execute("""SELECT id, created_at, ticker, strategy, start_date, end_date,
                initial_capital, transaction_cost_bps, params_json, metrics_json, equity_curve_json, trades_json"""
                + optional + " FROM saved_backtests WHERE id=?", (saved_id,)).fetchone())
            for field in ("params", "metrics", "equity_curve", "trades"):
                row[field] = replay_identity.loads(row.pop(field + "_json"))
            if any(type(row[k]) is not dict for k in ("params", "metrics")) or any(type(row[k]) is not list for k in ("equity_curve", "trades")):
                raise Unavailable("Stored source structure is unsupported")
            replay_identity.validate(row)
            context = None
            if "run_replay_contexts" in tables:
                size = conn.execute("SELECT length(CAST(snapshot_json AS BLOB)) FROM run_replay_contexts WHERE saved_backtest_id=?", (saved_id,)).fetchone()
                if size is not None:
                    if size[0] is None or size[0] > 512 * 1024:
                        raise Changed("Recorded replay material exceeds supported bounds")
                    context = dict(conn.execute("SELECT * FROM run_replay_contexts WHERE saved_backtest_id=?", (saved_id,)).fetchone())
            conn.rollback()
    except sqlite3.Error as exc:
        raise Unavailable("Stored source cannot be read safely") from exc
    except (TypeError, KeyError, ValueError, OverflowError) as exc:
        if isinstance(exc, (Changed, Unavailable)):
            raise
        raise Unavailable("Stored source is invalid or unsupported") from exc
    return row, context


def explain(saved_id, expected=None):
    if expected is not None:
        replay_identity.full_hash(expected)
    saved, context = acquire(saved_id)
    if saved["strategy"] != "sma_crossover":
        raise Unavailable("Only the saved SMA adapter is supported")
    if saved.get("config_schema") not in (None, "backtest_config_v1"):
        raise Unavailable("Stored configuration schema is unsupported")
    if any(key in saved["metrics"] or key in saved["params"] for key in ("availability", "quality", "metric_availability", "metrics_availability", "metric_quality")):
        raise Unavailable("Stored metric quality flags require a supported adapter")
    result_hash = replay.result_identity(saved)
    repro = saved["params"].get("reproducibility")
    if repro is not None:
        try:
            config = replay_identity.legacy(repro)
            replay._saved_config(saved, config)
            for key in ("fast_window", "slow_window"):
                if key in saved["params"] and saved["params"][key] != config["strategy_params"].get(key):
                    raise Changed("Stored parameters disagree with configuration")
        except (ValueError, KeyError, TypeError) as exc:
            raise Changed("Stored configuration integrity differs") from exc
    pinned = {"saved": {"params": {}, "metrics": {}}}
    for _, (pointer, _, _, _) in FIELDS.items():
        parts = pointer[1:].split("/")
        if len(parts) == 1:
            pinned["saved"][parts[0]] = saved[parts[0]]
        elif parts[1] in saved[parts[0]]:
            pinned["saved"][parts[0]][parts[1]] = saved[parts[0]][parts[1]]
    identity = {"source_kind": "saved_backtest", "source_schema": "saved_backtests_row_v1",
                "saved_backtest_id": saved_id, "created_at": saved["created_at"],
                "material_hash": result_hash, "trust": "legacy_unverified", "context": None}
    if context is not None:
        try:
            snapshot, _ = replay.verified(context, check_parent=False, saved_snapshot=saved)
            for key in ("fast_window", "slow_window"):
                if key in saved["params"] and saved["params"][key] != snapshot["config"]["strategy_params"][key]:
                    raise Changed("Stored parameters disagree with replay context")
            if snapshot["parent_context_id"] is not None:
                raise Unavailable("Parent-linked replay contexts are not supported by this adapter")
            identity["trust"] = "recorded_hashes_match"
            identity["context"] = {"id": context["id"], "schema": "replay_context_v1",
                "snapshot_hash": context["snapshot_hash"], "result_hash": snapshot["result_hash"],
                "input_hash": snapshot["input_hash"], "execution_hash": snapshot["execution_hash"],
                "config_hash_full": context["config_hash_full"]}
            pinned["context"] = {"config": {"strategy_params": {key: snapshot["config"]["strategy_params"][key] for key in ("fast_window", "slow_window")}}}
        except (ValueError, KeyError, TypeError, LookupError) as exc:
            if isinstance(exc, Unavailable):
                raise
            raise Changed("Stored replay integrity differs") from exc
    elif saved.get("config_hash_full") is not None or saved.get("config_schema") is not None:
        raise Changed("Advertised replay context is missing")
    try:
        bundle = verify(render(identity, pinned))
    except (ValueError, TypeError, KeyError) as exc:
        raise Unavailable("Stored fields cannot support this explanation") from exc
    if expected is not None and expected != bundle["fingerprint"]:
        raise Changed("Stored source differs from the pinned explanation")
    return bundle
