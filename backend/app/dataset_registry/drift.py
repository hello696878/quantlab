"""
Schema drift: neutral comparison between two dataset versions.

Detects added/removed columns, type changes, nullable changes, meaningful
ordering changes, and range/frequency/timezone changes, then classifies the
whole diff conservatively.  Drift descriptions are factual — drift is not
automatically "bad", and no version is recommended over another.

Classification rules (documented, conservative):

* ``none``                — schema fingerprints match and no field diffs.
* ``compatible``          — only additions, or nullable loosening
                            (NOT NULL → nullable), or ordering changes when
                            ordering is not significant.
* ``potentially_breaking``— nullable tightening, type changes between
                            plausibly-coercible types (int↔float),
                            frequency/timezone/date-range changes, or ordering
                            changes when ordering IS significant.
* ``breaking``            — removed columns, or type changes between
                            incompatible types.
* ``unknown``             — either side lacks a schema snapshot.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.dataset_registry.fingerprints import normalize_field_type

# Type pairs considered plausibly coercible (order-insensitive).
_COERCIBLE = {
    frozenset({"integer", "float"}),
    frozenset({"date", "datetime"}),
    frozenset({"string", "datetime"}),
    frozenset({"string", "date"}),
}


def _fields(snapshot: Optional[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    if not snapshot:
        return None
    fields = snapshot.get("fields")
    if not isinstance(fields, list) or not fields:
        return None
    return [
        {
            "name": str(f.get("name", "")),
            "type": normalize_field_type(f.get("type", "unknown")),
            "nullable": bool(f.get("nullable", True)),
        }
        for f in fields
        if str(f.get("name", "")).strip()
    ]


def compare_schemas(
    snapshot_a: Optional[Dict[str, Any]],
    snapshot_b: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return ``{"entries": [...], "drift_class": str}`` for A → B."""
    fields_a = _fields(snapshot_a)
    fields_b = _fields(snapshot_b)
    if fields_a is None or fields_b is None:
        return {
            "entries": [
                {
                    "kind": "schema_unavailable",
                    "field": None,
                    "a": bool(fields_a),
                    "b": bool(fields_b),
                    "note": "one or both versions have no schema snapshot",
                }
            ],
            "drift_class": "unknown",
        }

    by_a = {f["name"]: f for f in fields_a}
    by_b = {f["name"]: f for f in fields_b}
    entries: List[Dict[str, Any]] = []
    severity = 0  # 0 none, 1 compatible, 2 potentially_breaking, 3 breaking

    def bump(level: int) -> None:
        nonlocal severity
        severity = max(severity, level)

    for name in sorted(set(by_b) - set(by_a)):
        entries.append(
            {"kind": "column_added", "field": name, "a": None, "b": by_b[name]["type"], "note": ""}
        )
        bump(1)
    for name in sorted(set(by_a) - set(by_b)):
        entries.append(
            {"kind": "column_removed", "field": name, "a": by_a[name]["type"], "b": None, "note": ""}
        )
        bump(3)
    for name in sorted(set(by_a) & set(by_b)):
        fa, fb = by_a[name], by_b[name]
        if fa["type"] != fb["type"]:
            coercible = frozenset({fa["type"], fb["type"]}) in _COERCIBLE
            entries.append(
                {
                    "kind": "type_changed",
                    "field": name,
                    "a": fa["type"],
                    "b": fb["type"],
                    "note": "plausibly coercible" if coercible else "incompatible types",
                }
            )
            bump(2 if coercible else 3)
        if fa["nullable"] != fb["nullable"]:
            tightened = fa["nullable"] and not fb["nullable"]
            entries.append(
                {
                    "kind": "nullable_changed",
                    "field": name,
                    "a": fa["nullable"],
                    "b": fb["nullable"],
                    "note": "tightened (nullable → NOT NULL)" if tightened else "loosened",
                }
            )
            bump(2 if tightened else 1)

    # Ordering: meaningful only when either snapshot declares it significant.
    ordering_significant = bool(
        (snapshot_a or {}).get("ordering_significant")
        or (snapshot_b or {}).get("ordering_significant")
    )
    names_a = [f["name"] for f in fields_a]
    names_b = [f["name"] for f in fields_b]
    shared = [n for n in names_a if n in by_b]
    shared_b = [n for n in names_b if n in by_a]
    if shared != shared_b:
        entries.append(
            {
                "kind": "ordering_changed",
                "field": None,
                "a": shared,
                "b": shared_b,
                "note": "ordering declared significant" if ordering_significant else "ordering not significant",
            }
        )
        bump(2 if ordering_significant else 1)

    drift_class = ("none", "compatible", "potentially_breaking", "breaking")[severity]
    return {"entries": entries, "drift_class": drift_class}


def compare_context(version_a: Dict[str, Any], version_b: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Date-range / frequency-adjacent context diffs (neutral wording)."""
    entries: List[Dict[str, Any]] = []
    for field in ("start_time", "end_time", "format", "compression", "ingestion_method"):
        a, b = version_a.get(field), version_b.get(field)
        if a != b:
            entries.append({"kind": f"{field}_changed", "field": field, "a": a, "b": b, "note": ""})
    return entries


__all__ = ["compare_schemas", "compare_context"]
