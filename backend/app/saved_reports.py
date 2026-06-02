"""
CRUD operations for saved research reports (the Report Gallery).

A saved report stores the **Markdown report text** plus structured metadata
(title, type, source, tickers, strategy, date range, notes) — never a rendered
PDF.  PDF export remains a client-side browser-print operation.

All SQL is parameterised; no string interpolation of user-supplied values.
List/object-shaped fields (tickers, metadata) are stored as JSON text and
deserialised on read.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.db import get_connection


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


# ---------------------------------------------------------------------------
# Row mappers
# ---------------------------------------------------------------------------


def _row_to_summary(row) -> Dict[str, Any]:
    """
    Convert a DB row to a summary dict.

    Omits the large ``markdown_content`` blob so list responses stay light.
    """
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "title": row["title"],
        "report_type": row["report_type"],
        "source_type": row["source_type"],
        "source_id": row["source_id"],
        "tickers": json.loads(row["tickers_json"]),
        "strategy": row["strategy"],
        "date_range_start": row["date_range_start"],
        "date_range_end": row["date_range_end"],
        "notes": row["notes"],
    }


def _row_to_full(row) -> Dict[str, Any]:
    """Convert a DB row to a full dict including markdown_content + metadata."""
    full = _row_to_summary(row)
    full.update(
        {
            "markdown_content": row["markdown_content"],
            "metadata": json.loads(row["metadata_json"]),
        }
    )
    return full


# ---------------------------------------------------------------------------
# Public CRUD
# ---------------------------------------------------------------------------


def create_saved_report(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Insert a new saved report.  ``data`` is the dumped Pydantic request.

    Returns the full stored record (including the assigned ``id`` and
    timestamps).
    """
    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO saved_reports (
                created_at, updated_at, title, report_type, source_type,
                source_id, tickers_json, strategy,
                date_range_start, date_range_end,
                markdown_content, metadata_json, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now,
                now,
                data["title"],
                data["report_type"],
                data["source_type"],
                data.get("source_id"),
                json.dumps(data.get("tickers", [])),
                data.get("strategy"),
                data.get("date_range_start"),
                data.get("date_range_end"),
                data["markdown_content"],
                json.dumps(data.get("metadata", {})),
                data.get("notes", ""),
            ),
        )
        conn.commit()
        new_id: int = cursor.lastrowid  # type: ignore[assignment]

    result = get_saved_report(new_id)
    assert result is not None  # just inserted — must exist
    return result


def list_saved_reports() -> List[Dict[str, Any]]:
    """Return all saved reports as summary dicts, newest first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM saved_reports ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return [_row_to_summary(row) for row in rows]


def get_saved_report(id: int) -> Optional[Dict[str, Any]]:
    """Return the full record for *id*, or ``None`` if not found."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM saved_reports WHERE id = ?", (id,)
        ).fetchone()
    return _row_to_full(row) if row is not None else None


def update_saved_report(id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Update the mutable metadata (title, notes, metadata) of a saved report.

    The immutable Markdown content and source provenance are preserved.
    Refreshes ``updated_at``.  Returns the updated full record, or ``None`` if
    the id does not exist.
    """
    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE saved_reports
               SET updated_at = ?, title = ?, notes = ?, metadata_json = ?
             WHERE id = ?
            """,
            (
                now,
                data["title"],
                data.get("notes", ""),
                json.dumps(data.get("metadata", {})),
                id,
            ),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None

    return get_saved_report(id)


def delete_saved_report(id: int) -> bool:
    """Delete the report with the given *id*.  Returns True if a row was removed."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM saved_reports WHERE id = ?", (id,)
        )
        conn.commit()
    return cursor.rowcount > 0
