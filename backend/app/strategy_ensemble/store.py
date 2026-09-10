"""One bounded JSON snapshot per run; atomic lifecycle and baseline writes."""

import json
from contextlib import contextmanager
from datetime import datetime, timezone

from app.db import get_connection
from app.experiment_registry.fingerprints import canonical_json


@contextmanager
def connection():
    conn = get_connection()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def initialize(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS strategy_ensemble_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'created', request_json TEXT NOT NULL,
        links_json TEXT NOT NULL, results_json TEXT, fingerprints_json TEXT NOT NULL,
        is_baseline INTEGER NOT NULL DEFAULT 0, baseline_scope TEXT,
        error_message TEXT, experiment_id INTEGER, experiment_requested INTEGER NOT NULL DEFAULT 0,
        demo_key TEXT UNIQUE)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_ensemble_status ON strategy_ensemble_runs(status, id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_ensemble_scope ON strategy_ensemble_runs(baseline_scope, is_baseline)")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def decode(row):
    if row is None:
        return None
    data = dict(row)
    for field in ("request", "links", "results", "fingerprints"):
        value = data.pop(field + "_json")
        data[field] = json.loads(value) if value else None
    data["is_baseline"] = bool(data["is_baseline"])
    return data


def insert(request, links, fingerprints, demo_key=None):
    with connection() as conn:
        stamp = now()
        cursor = conn.execute("""INSERT INTO strategy_ensemble_runs
            (name, created_at, updated_at, request_json, links_json, fingerprints_json, demo_key)
            VALUES (?,?,?,?,?,?,?)""", (request["name"], stamp, stamp, canonical_json(request),
                                       canonical_json(links), canonical_json(fingerprints), demo_key))
        return decode(conn.execute("SELECT * FROM strategy_ensemble_runs WHERE id=?", (cursor.lastrowid,)).fetchone())


def get(run_id, conn=None):
    if conn is not None:
        return decode(conn.execute("SELECT * FROM strategy_ensemble_runs WHERE id=?", (run_id,)).fetchone())
    with connection() as conn:
        return get(run_id, conn)


def list_runs(page=1, page_size=25):
    with connection() as conn:
        rows = conn.execute("""SELECT id,name,status,is_baseline,error_message,created_at
            FROM strategy_ensemble_runs ORDER BY id DESC LIMIT ? OFFSET ?""",
                            (page_size, (page-1)*page_size)).fetchall()
        total = conn.execute("SELECT count(*) FROM strategy_ensemble_runs").fetchone()[0]
        return {"items": [{**dict(r), "is_baseline": bool(r["is_baseline"])} for r in rows],
                "total": total, "page": page, "page_size": page_size}


def demo_id(key):
    with connection() as conn:
        row = conn.execute("SELECT id FROM strategy_ensemble_runs WHERE demo_key=?", (key,)).fetchone()
        return row["id"] if row else None
