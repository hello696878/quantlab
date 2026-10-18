"""One bounded SQLite read transaction; no registry readers with writable opens."""
import sqlite3
from contextlib import closing
from pathlib import Path

from app import db
from app.run_replay import identity as replay_identity, service as replay
from .contract import FIELDS, render, verify

# Saved SMA fields emitted by SaveBacktestModal.buildParams and replay saves.
# Additional declarations (including per-metric units/status) need an adapter;
# ignoring an unfamiliar spelling could turn an unavailable number into a fact.
SMA_PARAM_KEYS = frozenset({
    "fast_window", "slow_window", "reproducibility", "cost_model", "effective_cost_bps",
    "total_transaction_cost", "cost_drag_return", "position_sizing", "average_exposure",
    "risk_management", "risk_diagnostics", "annualization_mode", "annualization_mode_used",
    "periods_per_year", "annualization_warning", "data_provider", "data_quality",
    "benchmark_analytics", "robustness", "sensitivity", "position_mode",
})


class Missing(LookupError):
    pass


class Unavailable(ValueError):
    pass


class Changed(ValueError):
    pass


def _storage_state(path):
    # mode=ro can create WAL/SHM files or require journal recovery. This adapter
    # supports an observed rollback-mode database with no sidecars only. This
    # preflight is not an atomic lock against a concurrent external mode change.
    if any(Path(str(path) + suffix).exists() or Path(str(path) + suffix).is_symlink()
           for suffix in ("-wal", "-shm", "-journal")):
        raise Unavailable("Stored source journal state is unsupported")
    with path.open("rb") as handle:
        header = handle.read(20)
    if header[:16] != b"SQLite format 3\x00" or header[18:20] != b"\x01\x01":
        raise Unavailable("Stored source storage mode is unsupported")


def _json_preflight(raw, *, limit=replay_identity.MAX_JSON):
    """Bound lexical work before the full decoder allocates nested objects."""
    if type(raw) not in (str, bytes):
        raise ValueError("Stored JSON must be text")
    if len(raw if type(raw) is bytes else raw.encode("utf-8")) > limit:
        raise ValueError("Stored JSON exceeds byte bounds")
    text = raw.decode("utf-8") if type(raw) is bytes else raw
    stack, nodes, index = [], 0, 0
    while index < len(text):
        char = text[index]
        if char in " \t\r\n:,":
            index += 1
            continue
        if char in "]}":
            if not stack or char != stack[-1][0]:
                raise ValueError("Stored JSON has invalid containers")
            stack.pop()
            index += 1
            continue
        nodes += 1  # Includes object keys; deliberately conservative.
        if nodes > 300000:
            raise ValueError("Stored JSON exceeds token bounds")
        if len(stack) > 20:
            raise ValueError("Stored JSON exceeds depth bounds")
        if stack:
            stack[-1][1] += 1
            if stack[-1][1] > 100000:
                raise ValueError("Stored JSON exceeds container bounds")
        if char in "[{":
            stack.append(["]" if char == "[" else "}", 0])
            index += 1
        elif char == '"':
            start = index
            index += 1
            while index < len(text):
                if index - start > 512 * 1024:
                    raise ValueError("Stored JSON exceeds string bounds")
                if text[index] == '"':
                    index += 1
                    break
                if text[index] == "\\":
                    index += 1
                index += 1
            else:
                raise ValueError("Stored JSON has an unfinished string")
        else:
            start = index
            while index < len(text) and text[index] not in " \t\r\n,:[]{}":
                index += 1
                if index - start > 128:
                    raise ValueError("Stored JSON exceeds scalar bounds")
    if stack:
        raise ValueError("Stored JSON has unfinished containers")


def acquire(saved_id, *, path=None):
    replay.positive_id(saved_id)
    path = (db.get_db_path() if path is None else Path(path)).absolute()
    if not path.is_file():
        raise Missing("Stored source is unavailable")
    try:
        _storage_state(path)
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            conn.execute("BEGIN")
            _storage_state(path)
            conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 5 * 1024 * 1024)
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('saved_backtests','run_replay_contexts')")}
            if "saved_backtests" not in tables:
                raise Unavailable("Stored source schema is unavailable")
            # Code-owned columns only. Names/notes/locators are deliberately not read.
            columns = {r[1] for r in conn.execute("PRAGMA table_info(saved_backtests)")}
            if len({"config_hash_full", "config_schema"} & columns) == 1:
                raise Unavailable("Stored index schema is incomplete")
            selected = ["id", "created_at", "ticker", "strategy", "start_date", "end_date", "initial_capital",
                        "transaction_cost_bps", "params_json", "metrics_json", "equity_curve_json", "trades_json"]
            if {"config_hash_full", "config_schema"} <= columns:
                selected += ["config_hash_full", "config_schema"]
            size_sql = " + ".join("length(CAST(COALESCE(" + name + ", '') AS BLOB))" for name in selected)
            sizes = conn.execute("SELECT " + size_sql + " FROM saved_backtests WHERE id=?", (saved_id,)).fetchone()
            if sizes is None:
                raise Missing("Stored source not found")
            if sizes[0] > 4 * 1024 * 1024:
                raise Unavailable("Stored source exceeds supported bounds")
            row = dict(conn.execute("SELECT " + ",".join(selected) + " FROM saved_backtests WHERE id=?", (saved_id,)).fetchone())
            context = None
            if "run_replay_contexts" in tables:
                context_columns = ["id", "saved_backtest_id", "config_hash_full", "config_schema", "snapshot_json", "snapshot_hash"]
                context_size = " + ".join("length(CAST(COALESCE(" + name + ", '') AS BLOB))" for name in context_columns)
                sizes = conn.execute("SELECT " + context_size + " FROM run_replay_contexts WHERE saved_backtest_id=? LIMIT 2", (saved_id,)).fetchall()
                if sizes:
                    if len(sizes) != 1 or sizes[0][0] > 512 * 1024:
                        raise Changed("Recorded replay material exceeds supported bounds")
                    context = dict(conn.execute("SELECT " + ",".join(context_columns) + " FROM run_replay_contexts WHERE saved_backtest_id=?", (saved_id,)).fetchone())
                    try:
                        _json_preflight(context["snapshot_json"], limit=512 * 1024)
                    except ValueError as exc:
                        raise Changed("Recorded replay material exceeds supported bounds") from exc
            for field in ("params", "metrics", "equity_curve", "trades"):
                _json_preflight(row[field + "_json"])
            for field in ("params", "metrics", "equity_curve", "trades"):
                row[field] = replay_identity.loads(row.pop(field + "_json"))
            if any(type(row[k]) is not dict for k in ("params", "metrics")) or any(type(row[k]) is not list for k in ("equity_curve", "trades")):
                raise Unavailable("Stored source structure is unsupported")
            replay_identity.validate(row)
            conn.rollback()
    except (sqlite3.Error, OSError) as exc:
        raise Unavailable("Stored source cannot be read safely") from exc
    except (TypeError, KeyError, ValueError, OverflowError) as exc:
        if isinstance(exc, (Changed, Unavailable)):
            raise
        raise Unavailable("Stored source is invalid or unsupported") from exc
    return row, context


def explain(saved_id, expected=None, *, path=None):
    if expected is not None:
        replay_identity.full_hash(expected)
    saved, context = acquire(saved_id) if path is None else acquire(saved_id, path=path)
    if saved["strategy"] != "sma_crossover":
        raise Unavailable("Only the saved SMA adapter is supported")
    if saved.get("config_schema") not in (None, "backtest_config_v1"):
        raise Unavailable("Stored configuration schema is unsupported")
    metric_keys = {key for key, field in FIELDS.items() if field[0].startswith("/metrics/")}
    if set(saved["metrics"]) - metric_keys or set(saved["params"]) - SMA_PARAM_KEYS:
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
