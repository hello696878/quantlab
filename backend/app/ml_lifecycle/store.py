"""Additive SQLite storage: immutable input snapshot, mutable diagnostic job links."""

import json
from contextlib import contextmanager
from datetime import datetime, timezone

from app.db import get_connection

from .identity import canonical


@contextmanager
def connection():
    conn = get_connection()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def initialize(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS ml_lifecycles (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, created_at TEXT NOT NULL,
        lifecycle_hash TEXT NOT NULL, dataset_version_id INTEGER NOT NULL,
        dataset_content_hash TEXT NOT NULL, dataset_manifest_hash TEXT NOT NULL,
        snapshot_json TEXT NOT NULL, snapshot_hash TEXT NOT NULL, trusted_demo INTEGER NOT NULL,
        demo_key TEXT UNIQUE, UNIQUE(lifecycle_hash, dataset_version_id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS ml_lifecycle_links (
        lifecycle_id INTEGER NOT NULL REFERENCES ml_lifecycles(id), adapter TEXT NOT NULL,
        status TEXT NOT NULL, destination_id INTEGER, content_hash TEXT, error TEXT,
        PRIMARY KEY(lifecycle_id, adapter))""")


def decode(row):
    if row is None:
        return None
    out = dict(row)
    out["snapshot"] = json.loads(out.pop("snapshot_json"))
    out["trusted_demo"] = bool(out["trusted_demo"])
    return out


def get(run_id):
    with connection() as conn:
        return decode(conn.execute("SELECT * FROM ml_lifecycles WHERE id=?", (run_id,)).fetchone())


def insert(payload, identity, snapshot_hash, manifest, demo_key=None):
    with connection() as conn:
        conn.execute("""INSERT OR IGNORE INTO ml_lifecycles
            (name,created_at,lifecycle_hash,dataset_version_id,dataset_content_hash,dataset_manifest_hash,
             snapshot_json,snapshot_hash,trusted_demo,demo_key) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                     (payload["name"], datetime.now(timezone.utc).isoformat(), identity,
                      payload["dataset_version_id"], payload["dataset_content_hash"], manifest,
                      canonical(payload["snapshot"]), snapshot_hash, int(demo_key is not None), demo_key))
        row = conn.execute("SELECT * FROM ml_lifecycles WHERE lifecycle_hash=? AND dataset_version_id=?",
                           (identity, payload["dataset_version_id"])).fetchone()
        if row is None:
            raise ValueError("demo identity conflict; existing records were not modified")
        return decode(row)


def ids():
    with connection() as conn:
        return [r[0] for r in conn.execute("SELECT id FROM ml_lifecycles ORDER BY id DESC LIMIT 501")]


def demo_id(key):
    with connection() as conn:
        row = conn.execute("SELECT id FROM ml_lifecycles WHERE demo_key=?", (key,)).fetchone()
        return row[0] if row else None


def links(run_id):
    with connection() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM ml_lifecycle_links WHERE lifecycle_id=? ORDER BY adapter", (run_id,))]


def claim(run_id, adapter):
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM ml_lifecycle_links WHERE lifecycle_id=? AND adapter=?", (run_id, adapter)).fetchone()
        if row and row["status"] in ("running", "completed"):
            return False
        conn.execute("""INSERT INTO ml_lifecycle_links(lifecycle_id,adapter,status) VALUES (?,?,'running')
            ON CONFLICT(lifecycle_id,adapter) DO UPDATE SET status='running', error=NULL""", (run_id, adapter))
        return True


def update_link(run_id, adapter, status, destination_id=None, content_hash=None, error=None):
    with connection() as conn:
        conn.execute("""UPDATE ml_lifecycle_links SET status=?,destination_id=COALESCE(?,destination_id),
            content_hash=?,error=? WHERE lifecycle_id=? AND adapter=?""",
                     (status, destination_id, content_hash, error, run_id, adapter))
