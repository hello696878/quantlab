"""Canonical JSON and typed table identity, separate from physical file hashes."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_BYTES = 4 * 1024 * 1024
MAX_ROWS = 2000
MAX_COLUMNS = 80


def canonical(value: Any) -> str:
    def check(item: Any, depth: int = 0) -> None:
        if depth > 16:
            raise ValueError("artifact nesting exceeds 16")
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is float and math.isfinite(item):
            return
        if type(item) is list:
            if len(item) > 10000:
                raise ValueError("artifact array exceeds 10000 elements")
            for child in item:
                check(child, depth + 1)
            return
        if type(item) is dict and all(type(k) is str for k in item):
            if len(item) > 200:
                raise ValueError("artifact object exceeds 200 fields")
            for child in item.values():
                check(child, depth + 1)
            return
        raise ValueError("artifacts require finite, plain JSON values")

    check(value)
    result = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                        allow_nan=False)
    if len(result.encode()) > MAX_BYTES:
        raise ValueError("artifact exceeds 4 MiB")
    return result


def fingerprint(kind: str, value: Any) -> str:
    return hashlib.sha256(canonical({"schema_version": 1, "kind": kind, "value": value}).encode()).hexdigest()


def read_json(data: bytes) -> Any:
    if len(data) > MAX_BYTES:
        raise ValueError("artifact exceeds 4 MiB")

    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("duplicate JSON key")
            out[key] = value
        return out

    try:
        value = json.loads(data.decode("utf-8-sig"), object_pairs_hook=pairs)
        canonical(value)
        return value
    except (UnicodeError, RecursionError, json.JSONDecodeError) as exc:
        raise ValueError("invalid bounded JSON artifact") from exc


def timestamp(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("timestamps require an explicit UTC offset")
        return dt.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    except (TypeError, AttributeError, ValueError) as exc:
        raise ValueError("timestamps require ISO 8601 with an explicit UTC offset") from exc


def table(columns: list[dict], rows: list[list], keys: list[str]) -> dict:
    """Rows sort by typed keys; column order, nulls and scalar types are material."""
    if not columns or len(columns) > MAX_COLUMNS or len(rows) > MAX_ROWS:
        raise ValueError("table exceeds column/row bounds")
    names = [c["name"] for c in columns]
    if len(names) != len(set(names)) or not keys or not set(keys) <= set(names):
        raise ValueError("table columns and keys must be unique and present")
    positions = [names.index(k) for k in keys]
    normalized = []
    seen = set()
    for row in rows:
        if len(row) != len(columns):
            raise ValueError("table row width mismatch")
        row = list(row)
        for i, (value, column) in enumerate(zip(row, columns)):
            kind = column["type"]
            if kind not in ("number", "string", "boolean", "timestamp"):
                raise ValueError("unsupported table scalar type")
            if value is None:
                if not column.get("nullable", False) or i in positions:
                    raise ValueError("unexpected table null")
            elif kind == "number":
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError("table numbers must be finite")
                row[i] = float(value)
            elif kind == "boolean" and type(value) is not bool:
                raise ValueError("invalid table boolean")
            elif kind in ("string", "timestamp"):
                if type(value) is not str:
                    raise ValueError("invalid table string")
                if kind == "timestamp":
                    row[i] = timestamp(value)
        key = canonical([row[p] for p in positions])
        if key in seen:
            raise ValueError("duplicate sample key")
        seen.add(key)
        normalized.append(row)
    normalized.sort(key=lambda row: tuple(row[p] for p in positions))
    result = {"columns": columns, "keys": keys, "rows": normalized}
    canonical(result)
    return result


def environment(classification: str) -> dict:
    from app.experiments.spec import best_effort_git_commit

    versions = {}
    for name in ("numpy", "scipy", "pandas", "pydantic"):
        versions[name] = importlib.metadata.version(name)
    return {"classification": classification, "python": platform.python_version(),
            "libraries": versions,
            "app_version": (Path(__file__).resolve().parents[3] / "VERSION").read_text().strip()
            if (Path(__file__).resolve().parents[3] / "VERSION").is_file() else "unavailable",
            "git_commit": best_effort_git_commit()}
