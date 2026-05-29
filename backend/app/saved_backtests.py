"""
CRUD operations for saved backtest records.

All queries use parameterised SQL — no string interpolation of user-supplied
values.  Large fields (equity curve, trades, params, metrics) are stored as
JSON text and deserialised on read.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.db import get_connection


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _row_to_summary(row) -> Dict[str, Any]:
    """
    Convert a DB row to a summary dict.

    Summary rows omit the four large JSON blobs (params, metrics,
    equity_curve, trades) so list responses stay lightweight.  The four
    headline metrics are extracted directly from metrics_json.
    """
    metrics: Dict[str, Any] = json.loads(row["metrics_json"])
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "name": row["name"],
        "ticker": row["ticker"],
        "strategy": row["strategy"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "total_return": metrics.get("total_return"),
        "cagr": metrics.get("cagr"),
        "sharpe_ratio": metrics.get("sharpe_ratio"),
        "max_drawdown": metrics.get("max_drawdown"),
        "notes": row["notes"],
    }


def _row_to_full(row) -> Dict[str, Any]:
    """
    Convert a DB row to a full dict including all JSON blobs.
    """
    full = _row_to_summary(row)
    full.update(
        {
            "initial_capital": row["initial_capital"],
            "transaction_cost_bps": row["transaction_cost_bps"],
            "params": json.loads(row["params_json"]),
            "metrics": json.loads(row["metrics_json"]),
            "equity_curve": json.loads(row["equity_curve_json"]),
            "trades": json.loads(row["trades_json"]),
        }
    )
    return full


# ---------------------------------------------------------------------------
# Public CRUD
# ---------------------------------------------------------------------------


def create_saved_backtest(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Insert a new saved backtest record.

    Returns the full record (including the assigned ``id`` and ``created_at``).
    """
    created_at = (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO saved_backtests (
                created_at, name, ticker, strategy,
                start_date, end_date,
                initial_capital, transaction_cost_bps,
                params_json, metrics_json, equity_curve_json, trades_json,
                notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                data["name"],
                data["ticker"],
                data["strategy"],
                data["start_date"],
                data["end_date"],
                data["initial_capital"],
                data["transaction_cost_bps"],
                json.dumps(data.get("params", {})),
                json.dumps(data.get("metrics", {})),
                json.dumps(data.get("equity_curve", [])),
                json.dumps(data.get("trades", [])),
                data.get("notes", ""),
            ),
        )
        conn.commit()
        new_id: int = cursor.lastrowid  # type: ignore[assignment]

    result = get_saved_backtest(new_id)
    assert result is not None  # just inserted — must exist
    return result


def list_saved_backtests() -> List[Dict[str, Any]]:
    """
    Return all saved backtests as summary dicts, newest first.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM saved_backtests ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return [_row_to_summary(row) for row in rows]


def get_saved_backtest(id: int) -> Optional[Dict[str, Any]]:
    """
    Return the full record for *id*, or ``None`` if not found.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM saved_backtests WHERE id = ?", (id,)
        ).fetchone()
    return _row_to_full(row) if row is not None else None


def delete_saved_backtest(id: int) -> bool:
    """
    Delete the record with the given *id*.

    Returns ``True`` if a row was deleted, ``False`` if the id was not found.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM saved_backtests WHERE id = ?", (id,)
        )
        conn.commit()
    return cursor.rowcount > 0
