"""
SQLite database layer for QuantLab.

Design notes
------------
* Uses only the Python standard-library ``sqlite3`` module — no ORM required.
* ``get_db_path()`` honours a module-level override (``_db_path_override``) so
  tests can redirect all queries to a temporary file without touching the real
  database.
* ``init_db()`` is idempotent: ``CREATE TABLE IF NOT EXISTS`` makes it safe to
  call on every startup or in test fixtures.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Default database lives at  backend/data/quantlab.db
_DATA_DIR: Path = Path(__file__).parent.parent / "data"

# Set by tests (via monkeypatch) to redirect all queries to a temp file.
_db_path_override: Optional[Path] = None


def get_db_path() -> Path:
    """Return the active database path (override if set, else default)."""
    if _db_path_override is not None:
        return _db_path_override
    return _DATA_DIR / "quantlab.db"


# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------


def get_connection() -> sqlite3.Connection:
    """
    Open and return a new SQLite connection.

    The parent directory of the database file is created automatically when it
    does not exist (covers the default ``backend/data/`` directory and any
    temporary directory used by tests).
    """
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------


def init_db() -> None:
    """
    Create the application tables if they do not already exist.

    Safe to call multiple times (idempotent).  Called once at application
    startup and once per test via the ``fresh_db`` fixture.
    """
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_backtests (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at          TEXT    NOT NULL,
                name                TEXT    NOT NULL,
                ticker              TEXT    NOT NULL,
                strategy            TEXT    NOT NULL,
                start_date          TEXT    NOT NULL,
                end_date            TEXT    NOT NULL,
                initial_capital     REAL    NOT NULL,
                transaction_cost_bps REAL   NOT NULL,
                params_json         TEXT    NOT NULL DEFAULT '{}',
                metrics_json        TEXT    NOT NULL DEFAULT '{}',
                equity_curve_json   TEXT    NOT NULL DEFAULT '[]',
                trades_json         TEXT    NOT NULL DEFAULT '[]',
                notes               TEXT    NOT NULL DEFAULT ''
            )
            """
        )
        # Reusable Custom Strategy Builder definitions (NOT backtest results).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_strategy_templates (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at        TEXT NOT NULL,
                updated_at        TEXT NOT NULL,
                name              TEXT NOT NULL,
                description       TEXT NOT NULL DEFAULT '',
                entry_logic       TEXT NOT NULL,
                exit_logic        TEXT NOT NULL,
                entry_rules_json  TEXT NOT NULL DEFAULT '[]',
                exit_rules_json   TEXT NOT NULL DEFAULT '[]',
                tags_json         TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        # Saved research reports (Report Gallery).  Stores the Markdown report
        # text + structured metadata only — never PDF binaries.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_reports (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at        TEXT NOT NULL,
                updated_at        TEXT NOT NULL,
                title             TEXT NOT NULL,
                report_type       TEXT NOT NULL,
                source_type       TEXT NOT NULL,
                source_id         INTEGER,
                tickers_json      TEXT NOT NULL DEFAULT '[]',
                strategy          TEXT,
                date_range_start  TEXT,
                date_range_end    TEXT,
                markdown_content  TEXT NOT NULL,
                metadata_json     TEXT NOT NULL DEFAULT '{}',
                notes             TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.commit()
    finally:
        conn.close()
