"""Explicit bounded local-file adapter at the datastore ingestion seam."""
from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field

from app.ml_lifecycle.importer import _read, local_path, pinned_directory
from app.run_replay.identity import loads
from .calendar import DeclaredCalendar
from .models import Frozen, Snapshot, finite
from .revisions import envelope_hash, validate_binding

MAX_INPUT_BYTES = 256 * 1024
CSV_COLUMNS = ("source", "root_symbol", "contract_symbol", "session", "expiry", "revision_id", "supersedes",
               "open", "high", "low", "close", "volume", "open_interest", "price_available_at",
               "volume_available_at", "oi_available_at", "local_received_at")


class AdapterFailure(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class AdapterRequest(Frozen):
    provider: Literal["local_file", "external"]
    csv_path: str | None = Field(default=None, max_length=500)
    metadata_path: str | None = Field(default=None, max_length=500)
    calendar_path: str | None = Field(default=None, max_length=500)


@dataclass(frozen=True)
class Capabilities:
    daily_individual_contracts: bool = True
    local_preview: bool = True
    external_fetch: bool = False
    artifact_export: bool = False
    official_calendar: bool = False


@dataclass(frozen=True)
class AdapterResult:
    snapshot: Snapshot
    calendar: DeclaredCalendar
    physical_hashes: tuple[tuple[str, str], ...]
    envelope_hash: str
    inspected_at: str
    coverage: tuple[str, str]
    missing_fields: tuple[str, ...]
    limitations: tuple[str, ...]


def read_input(path: Path) -> bytes:
    if ".." in path.parts:
        raise ValueError("parent traversal is not accepted")
    path = local_path(path)
    with pinned_directory(path.parent) as fd:
        raw = _read(path, parent_fd=fd)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("futures input exceeds 256 KiB")
    return raw


def parse_csv(raw: bytes) -> tuple[dict, ...]:
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("CSV exceeds 256 KiB")
    try:
        reader = csv.reader(io.StringIO(raw.decode("utf-8-sig")), strict=True)
        headers = next(reader, [])
        if tuple(headers) != CSV_COLUMNS:
            raise ValueError("CSV must use the exact unique v1 column layout")
        rows = []
        for cells in reader:
            if len(cells) != len(headers) or len(rows) >= 2000 or any(len(c) > 300 for c in cells):
                raise ValueError("CSV row width/count/cell bound exceeded")
            row = dict(zip(headers, cells))
            for name in ("open", "high", "low", "close", "open_interest"):
                text = row[name]
                if name == "open_interest" and text == "":
                    row[name] = None
                elif not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", text):
                    raise ValueError("CSV number must be explicit finite decimal syntax")
                else:
                    row[name] = finite(float(text))
            if not re.fullmatch(r"\d+", row["volume"]):
                raise ValueError("CSV volume must be an unsigned integer")
            row["volume"] = int(row["volume"])
            row["supersedes"] = row["supersedes"] or None
            row["availability"] = {"price": row.pop("price_available_at") or None,
                                   "volume": row.pop("volume_available_at") or None,
                                   "open_interest": row.pop("oi_available_at") or None,
                                   "local_received_at": row.pop("local_received_at") or None}
            rows.append(row)
        if not rows:
            raise ValueError("CSV contains no observations")
        return tuple(rows)
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("malformed UTF-8 CSV") from exc


def preview(request: AdapterRequest) -> AdapterResult:
    # No configuration/environment switch can activate an absent futures provider.
    if request.provider != "local_file":
        raise AdapterFailure("provider_disabled", "External futures acquisition is not implemented; no network attempted")
    if not all((request.csv_path, request.metadata_path, request.calendar_path)):
        raise AdapterFailure("incomplete", "Explicit CSV, metadata and calendar paths required")
    paths = (Path(request.csv_path), Path(request.metadata_path), Path(request.calendar_path))
    try:
        if tuple(p.suffix.lower() for p in paths) != (".csv", ".json", ".json"):
            raise ValueError("only explicit CSV/JSON files are supported, not archives or provider locators")
        inputs = tuple(read_input(p) for p in paths)
        metadata = loads(inputs[1], limit=MAX_INPUT_BYTES)
        if type(metadata) is not dict or "bars" in metadata:
            raise ValueError("metadata must be a declaration object without inline bars")
        calendar = DeclaredCalendar.model_validate(loads(inputs[2], limit=MAX_INPUT_BYTES))
        snapshot = Snapshot.model_validate({**metadata, "bars": parse_csv(inputs[0])})
        validate_binding(snapshot, calendar)
        # Detect material cross-file mutations after parsing; no atomic snapshot claim.
        if inputs != tuple(read_input(p) for p in paths):
            raise ValueError("source material changed during preview")
        hashes = tuple((role, hashlib.sha256(raw).hexdigest())
                       for role, raw in zip(("csv", "metadata", "calendar"), inputs))
        availability_fields = {"price_available_at": "price", "volume_available_at": "volume",
                               "oi_available_at": "open_interest", "local_received_at": "local_received_at"}
        missing = (["open_interest"] if any(b.open_interest is None for b in snapshot.bars) else [])
        missing += [name for name, field in availability_fields.items()
                    if any(getattr(b.availability, field) is None for b in snapshot.bars)]
        return AdapterResult(snapshot, calendar, hashes, envelope_hash(snapshot, calendar),
                             datetime.now(timezone.utc).isoformat(),
                             (str(min(b.session for b in snapshot.bars)), str(max(b.session for b in snapshot.bars))),
                             tuple(missing),
                             ("Source/license/availability are unverified declarations",
                              "Inspection time is not historical local receipt",
                              "No atomic multi-file/adversarial filesystem snapshot guarantee"))
    except (ValueError, OSError, OverflowError) as exc:
        raise AdapterFailure("invalid_input", str(exc)) from exc
