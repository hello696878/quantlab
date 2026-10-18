"""Offline, non-overwriting synthetic corpus operations and bounded RO verification."""
import argparse
from contextlib import closing
from datetime import date, datetime, timezone
import hashlib
from pathlib import Path
import re
import sqlite3
import stat

from app.run_replay.identity import digest, loads, validate, full_hash
from app.research_explainer import service as explainer

SCHEMA = "public_sma_corpus_v1"
TITLE = "Synthetic SMA showcase"
NOTICE = "Synthetic prices and illustrative dates; prepared offline, not market history or execution attestation."
DB_NAME = "demo.db"
MANIFEST = "corpus.json"
MAX_DB = 2 * 1024 * 1024
SUMMARY = ("id", "created_at", "name", "ticker", "strategy", "start_date", "end_date",
           "total_return", "cagr", "sharpe_ratio", "max_drawdown", "notes", "config_hash_full", "config_schema")


def unlinked(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("An absolute operator-owned path is required")
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            info = item.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 1024:
                raise ValueError("Linked corpus paths are unsupported")
    return path


def bounded_file(path, maximum):
    unlinked(path)
    if not path.is_file() or path.stat().st_size > maximum:
        raise ValueError("Corpus file is missing or exceeds bounds")
    with path.open("rb") as handle:
        data = handle.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError("Corpus file exceeds bounds")
    return data


def observe(directory):
    directory = unlinked(directory)
    database = directory / DB_NAME
    content = bounded_file(database, MAX_DB)
    explainer._storage_state(database)
    manifest = bounded_file(directory / MANIFEST, 16384)
    return content, manifest


def verify(directory, expected_id):
    """No mkdir/migration/repair; observations do not defeat hostile file races."""
    full_hash(expected_id)
    directory = unlinked(directory)
    data, raw = observe(directory)
    manifest = loads(raw, limit=16384)
    keys = {"schema", "prepared_at", "provenance", "saved_ids", "database_sha256", "material_sha256", "corpus_id"}
    if type(manifest) is not dict or set(manifest) != keys or manifest["schema"] != SCHEMA:
        raise ValueError("Unsupported corpus schema")
    material = {k: v for k, v in manifest.items() if k != "corpus_id"}
    if digest(material) != expected_id or manifest["corpus_id"] != expected_id:
        raise ValueError("Corpus identity differs")
    if manifest["saved_ids"] != [1] or manifest["provenance"] != NOTICE:
        raise ValueError("Unsupported corpus content")
    prepared = datetime.fromisoformat(manifest["prepared_at"])
    if prepared.utcoffset() is None or prepared.utcoffset().total_seconds() != 0:
        raise ValueError("Unsupported preparation timestamp")
    if hashlib.sha256(data).hexdigest() != manifest["database_sha256"]:
        raise ValueError("Corpus bytes differ")
    from app.saved_backtests import _row_to_full
    from app.schemas import SavedBacktestFull
    with closing(sqlite3.connect((directory / DB_NAME).as_uri() + "?mode=ro", uri=True, timeout=1)) as conn:
        conn.row_factory = sqlite3.Row
        conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_DB)
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Corpus integrity refused")
        if conn.execute("SELECT count(*) FROM saved_backtests").fetchone()[0] != 1:
            raise ValueError("Unsupported saved inventory")
        if conn.execute("SELECT count(*) FROM run_replay_contexts").fetchone()[0] != 0:
            raise ValueError("Replay contexts are not public demo content")
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT GLOB 'sqlite_*' LIMIT 513")]
        if len(tables) > 512 or any(not re.fullmatch(r"[a-z_][a-z0-9_]{0,63}", name) for name in tables):
            raise ValueError("Unsupported corpus table inventory")
        for name in tables:
            # Identifiers are separately bounded/whitelisted above, never submitted SQL.
            if name != "saved_backtests" and conn.execute('SELECT 1 FROM "' + name + '" LIMIT 1').fetchone() is not None:
                raise ValueError("Nonpublic table material is unsupported")
        row = conn.execute("SELECT * FROM saved_backtests WHERE id=?", (1,)).fetchone()
        record = SavedBacktestFull(**_row_to_full(row)).model_dump(mode="json")
    if (record["name"] != TITLE or record["notes"] != NOTICE or record["ticker"] != "SYNTHETIC"
            or record["strategy"] != "sma_crossover" or record["config_hash_full"] is not None
            or record["config_schema"] is not None or set(record["params"]) != {"fast_window", "slow_window", "periods_per_year"}
            or record["params"] != {"fast_window": 5, "slow_window": 20, "periods_per_year": 252}
            or len(record["equity_curve"]) != 180 or len(record["trades"]) > 180):
        raise ValueError("Unsupported public projection")
    created = datetime.fromisoformat(record["created_at"].replace("Z", "+00:00"))
    if created.utcoffset() is None or created.utcoffset().total_seconds() != 0:
        raise ValueError("Unsupported creation timestamp")
    days = []
    for point in record["equity_curve"]:
        if (type(point) is not dict or set(point) != {"date", "strategy", "benchmark"}
                or any(type(point[key]) not in (int, float) or point[key] <= 0 for key in ("strategy", "benchmark"))):
            raise ValueError("Unsupported public equity projection")
        day = date.fromisoformat(point["date"]).isoformat()
        if day != point["date"] or (days and day <= days[-1]):
            raise ValueError("Unsupported public dates")
        days.append(day)
    if days[0] != record["start_date"] or days[-1] != record["end_date"]:
        raise ValueError("Public range differs")
    for trade in record["trades"]:
        if (type(trade) is not dict or set(trade) != {"date", "action", "price", "shares", "cost"}
                or trade["action"] not in ("BUY", "SELL") or trade["date"] not in days
                or any(type(trade[key]) not in (int, float) or trade[key] < 0 for key in ("price", "shares", "cost"))):
            raise ValueError("Unsupported public trade projection")
    if digest(record) != manifest["material_sha256"]:
        raise ValueError("Stored public material differs")
    explanation = explainer.explain(1, path=directory / DB_NAME)
    if observe(directory) != (data, raw):
        raise ValueError("Corpus changed during verification")
    return manifest, record, explanation


def prepare(destination):
    """Explicit offline operation only; partial destinations are retained on error."""
    destination = unlinked(destination)
    destination.mkdir(exist_ok=False)
    from app import db, saved_backtests
    from app.backtest import run_backtest
    from app.metrics import compute_metrics
    from app.strategies import sma_crossover_signals
    from app.schemas import SavedBacktestCreate
    import math
    import pandas as pd
    database = destination / DB_NAME
    db.init_db(path=database)
    close = pd.Series([100 + i * .12 + 8 * math.sin(i / 9) for i in range(180)],
                      index=pd.date_range("2000-01-03", periods=180, freq="B"))
    equity, benchmark, trades = run_backtest(close, sma_crossover_signals(close, 5, 20), 10, 100000)
    # Preparation uses existing engine/metrics/save contracts; serving never runs these.
    payload = SavedBacktestCreate(name=TITLE, notes=NOTICE, ticker="SYNTHETIC", strategy="sma_crossover",
        start_date=str(close.index[0].date()), end_date=str(close.index[-1].date()),
        initial_capital=100000, transaction_cost_bps=10, params={"fast_window": 5, "slow_window": 20, "periods_per_year": 252},
        metrics=compute_metrics(equity), trades=trades,
        equity_curve=[{"date": str(day.date()), "strategy": float(equity.loc[day]), "benchmark": float(benchmark.loc[day])} for day in close.index])
    record = saved_backtests.create_saved_backtest(payload.model_dump(), path=database)
    from app.schemas import SavedBacktestFull
    record = SavedBacktestFull(**record).model_dump(mode="json")
    data = bounded_file(database, MAX_DB)
    manifest = {"schema": SCHEMA, "prepared_at": datetime.now(timezone.utc).isoformat(), "provenance": NOTICE,
                "saved_ids": [1], "database_sha256": hashlib.sha256(data).hexdigest(), "material_sha256": digest(record)}
    manifest["corpus_id"] = digest(manifest)
    with (destination / MANIFEST).open("x", encoding="utf-8") as handle:
        handle.write(validate(manifest) + "\n")
    verify(destination, manifest["corpus_id"])
    return manifest["corpus_id"]


def copy_stopped(source, destination, expected_id, *, stopped=False):
    """Bounded backup/restore of a stopped prepared corpus, never a live WAL copy."""
    if stopped is not True:
        raise ValueError("Stop the demo and explicitly confirm stopped-source copying")
    verify(source, expected_id)
    data, raw = observe(source)
    destination = unlinked(destination)
    destination.mkdir(exist_ok=False)
    with (destination / DB_NAME).open("xb") as handle:
        handle.write(data)
    if observe(source) != (data, raw):
        raise ValueError("Source changed during offline copy")
    with (destination / MANIFEST).open("xb") as handle:
        handle.write(raw)
    verify(destination, expected_id)
    return expected_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "verify", "copy-stopped"))
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--expected-id")
    parser.add_argument("--stopped", action="store_true")
    args = parser.parse_args()
    try:
        if args.operation == "prepare" and args.destination and not args.source and not args.expected_id and not args.stopped:
            result = prepare(args.destination)
        elif args.operation == "verify" and args.source and args.expected_id and not args.destination and not args.stopped:
            result = verify(args.source, args.expected_id)[0]["corpus_id"]
        elif args.operation == "copy-stopped" and args.source and args.destination and args.expected_id:
            result = copy_stopped(args.source, args.destination, args.expected_id, stopped=args.stopped)
        else:
            raise ValueError("Unsupported operator arguments")
    except (ValueError, OSError, sqlite3.Error, LookupError, TypeError, RecursionError):
        parser.exit(2, "Corpus operation refused; check ownership, identity and supported stopped storage.\n")
    print(result)


if __name__ == "__main__":
    main()
