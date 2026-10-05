"""Additive schema; registration participates in the saved-result transaction."""
from contextlib import closing
from app.db import get_connection


def initialize(conn):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(saved_backtests)")}
    for name in ("config_hash_full", "config_schema"):
        if name not in columns:
            conn.execute(f"ALTER TABLE saved_backtests ADD COLUMN {name} TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_saved_config_hash ON saved_backtests(config_hash_full, config_schema)")
    conn.execute("""CREATE TABLE IF NOT EXISTS run_replay_contexts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        saved_backtest_id INTEGER NOT NULL UNIQUE,
        config_hash_full TEXT NOT NULL, config_schema TEXT NOT NULL,
        snapshot_json TEXT NOT NULL, snapshot_hash TEXT NOT NULL,
        FOREIGN KEY(saved_backtest_id) REFERENCES saved_backtests(id)
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_replay_config_hash ON run_replay_contexts(config_hash_full, config_schema)")


def get(context_id):
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT * FROM run_replay_contexts WHERE id=?", (context_id,)).fetchone()
    return dict(row) if row else None


def for_saved(saved_id):
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT * FROM run_replay_contexts WHERE saved_backtest_id=?", (saved_id,)).fetchone()
    return dict(row) if row else None


def contexts(config_hash, offset=0, limit=20):
    with closing(get_connection()) as conn:
        rows = conn.execute("SELECT * FROM run_replay_contexts WHERE config_hash_full=? ORDER BY id LIMIT ? OFFSET ?",
                            (config_hash, limit, offset)).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM run_replay_contexts WHERE config_hash_full=?", (config_hash,)).fetchone()[0]
    return [dict(row) for row in rows], total
