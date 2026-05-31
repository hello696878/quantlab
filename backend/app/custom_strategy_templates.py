"""
CRUD operations for saved custom strategy templates.

A template is a *reusable strategy definition* (entry/exit rules + logic +
metadata) — never a backtest result.  Rule arrays and tags are stored as JSON
text and re-validated against the CustomRule schema when read back through the
API layer.  All SQL is parameterised; no string interpolation of user values.
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


def _row_to_summary(row) -> Dict[str, Any]:
    """Convert a DB row to a summary dict (rule counts, not full rules)."""
    entry_rules = json.loads(row["entry_rules_json"])
    exit_rules = json.loads(row["exit_rules_json"])
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "name": row["name"],
        "description": row["description"],
        "entry_logic": row["entry_logic"],
        "exit_logic": row["exit_logic"],
        "num_entry_rules": len(entry_rules),
        "num_exit_rules": len(exit_rules),
        "tags": json.loads(row["tags_json"]),
    }


def _row_to_full(row) -> Dict[str, Any]:
    """Convert a DB row to a full dict including the rule arrays."""
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "name": row["name"],
        "description": row["description"],
        "entry_logic": row["entry_logic"],
        "exit_logic": row["exit_logic"],
        "entry_rules": json.loads(row["entry_rules_json"]),
        "exit_rules": json.loads(row["exit_rules_json"]),
        "tags": json.loads(row["tags_json"]),
    }


def create_template(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Insert a new template.  ``data`` is the dumped Pydantic request
    (rules already validated).  Returns the full stored record.
    """
    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO custom_strategy_templates (
                created_at, updated_at, name, description,
                entry_logic, exit_logic,
                entry_rules_json, exit_rules_json, tags_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now,
                now,
                data["name"],
                data.get("description", ""),
                data["entry_logic"],
                data["exit_logic"],
                json.dumps(data.get("entry_rules", [])),
                json.dumps(data.get("exit_rules", [])),
                json.dumps(data.get("tags", [])),
            ),
        )
        conn.commit()
        new_id: int = cursor.lastrowid  # type: ignore[assignment]

    result = get_template(new_id)
    assert result is not None
    return result


def list_templates() -> List[Dict[str, Any]]:
    """Return all templates as summary dicts, most recently updated first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM custom_strategy_templates "
            "ORDER BY updated_at DESC, id DESC"
        ).fetchall()
    return [_row_to_summary(row) for row in rows]


def get_template(id: int) -> Optional[Dict[str, Any]]:
    """Return the full template for *id*, or ``None`` if not found."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM custom_strategy_templates WHERE id = ?", (id,)
        ).fetchone()
    return _row_to_full(row) if row is not None else None


def update_template(id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Replace the mutable fields of an existing template.

    Preserves ``created_at`` and refreshes ``updated_at``.  Returns the updated
    full record, or ``None`` if the id does not exist.
    """
    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE custom_strategy_templates
               SET updated_at = ?, name = ?, description = ?,
                   entry_logic = ?, exit_logic = ?,
                   entry_rules_json = ?, exit_rules_json = ?, tags_json = ?
             WHERE id = ?
            """,
            (
                now,
                data["name"],
                data.get("description", ""),
                data["entry_logic"],
                data["exit_logic"],
                json.dumps(data.get("entry_rules", [])),
                json.dumps(data.get("exit_rules", [])),
                json.dumps(data.get("tags", [])),
                id,
            ),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None

    return get_template(id)


def delete_template(id: int) -> bool:
    """Delete the template with the given *id*.  Returns True if a row was removed."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM custom_strategy_templates WHERE id = ?", (id,)
        )
        conn.commit()
    return cursor.rowcount > 0
