"""Pure bounded vintage comparison and explicit knowledge-time eligibility."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from app.instruments import get_instrument
from app.run_replay.identity import digest
from .calendar import DeclaredCalendar
from .models import Bar, Snapshot, instant

Mode = Literal["declared_source", "local_observed"]


def spec_hash(root: str) -> str:
    return digest({"namespace": "futures_instrument_metadata_v1",
                   "spec": get_instrument(root).model_dump(mode="json")})


def market_content(bar: Bar) -> dict:
    return bar.model_dump(mode="json", exclude={"revision_id", "supersedes", "availability"})


def validate_binding(snapshot: Snapshot, calendar: DeclaredCalendar):
    if (snapshot.calendar_id, snapshot.calendar_version) != (calendar.calendar_id, calendar.version):
        raise ValueError("snapshot/calendar identity mismatch")
    if snapshot.instrument_metadata_hash != spec_hash(snapshot.root_symbol):
        raise ValueError("instrument metadata content changed")
    if calendar.timezone != get_instrument(snapshot.root_symbol).session.timezone:
        raise ValueError("calendar timezone does not match instrument")
    for bar in snapshot.bars:
        session = calendar.lookup(bar.session)
        if not session.open:
            raise ValueError("bar assigned to an explicitly closed session")
        for available in (bar.availability.price, bar.availability.volume, bar.availability.open_interest,
                          bar.availability.local_received_at):
            if available is not None and available < session.interval.end:
                raise ValueError("full daily fields cannot be available before session end")


def envelope_hash(snapshot: Snapshot, calendar: DeclaredCalendar) -> str:
    validate_binding(snapshot, calendar)
    ordered = sorted(snapshot.bars, key=lambda b: (*b.key, b.revision_id))
    material = snapshot.model_dump(mode="json", exclude={"bars", "snapshot_id"})
    return digest({"namespace": "futures_pit_envelope_v1", "declaration": material,
                   "bars": [b.model_dump(mode="json") for b in ordered],
                   "calendar": calendar.model_dump(mode="json"),
                   "instrument": get_instrument(snapshot.root_symbol).model_dump(mode="json")})


def table_hash(bars: tuple[Bar, ...]) -> str:
    if not bars or len({b.key for b in bars}) != len(bars):
        raise ValueError("normalized market hash requires a nonempty selected vintage")
    return digest({"namespace": "futures_market_table_v1",
                   "rows": sorted((market_content(b) for b in bars),
                                  key=lambda b: (b["source"], b["contract_symbol"], b["session"]))})


def compare(original: Snapshot, incoming: Snapshot) -> tuple[dict, ...]:
    if (original.source, original.root_symbol) != (incoming.source, incoming.root_symbol):
        raise ValueError("cannot compare unrelated sources/roots")
    if original.model_dump(mode="json", exclude={"bars", "snapshot_id"}) != incoming.model_dump(mode="json", exclude={"bars", "snapshot_id"}):
        raise ValueError("cannot compare revisions with changed provenance/calendar/spec contexts")
    old = {(*b.key, b.revision_id): b for b in original.bars}
    keys = {b.key for b in original.bars}
    findings = []
    for bar in incoming.bars:
        prior = old.get((*bar.key, bar.revision_id))
        if prior is not None:
            status = "exact_duplicate" if prior == bar else "same_version_contradiction"
        elif bar.key not in keys:
            status = "new_observation" if bar.supersedes is None else "ambiguous_provenance"
        elif bar.supersedes is not None and (*bar.key, bar.supersedes) in old:
            status = "explicit_revision"
        else:
            status = "ambiguous_provenance"
        findings.append({"contract": bar.contract_symbol, "session": bar.session.isoformat(),
                         "revision_id": bar.revision_id, "status": status})
    return tuple(findings)


@dataclass(frozen=True)
class Selection:
    bars: tuple[Bar, ...]
    excluded_unknown: int
    excluded_future: int
    mode: Mode
    cutoff: str


def as_of(snapshots: tuple[Snapshot, ...], cutoff, mode: Mode) -> Selection:
    cutoff = instant(cutoff)
    if mode not in ("declared_source", "local_observed") or not 1 <= len(snapshots) <= 16:
        raise ValueError("explicit as-of mode and 1..16 snapshots required")
    if sum(len(s.bars) for s in snapshots) > 4000:
        raise ValueError("revision corpus exceeds 4000 records")
    contexts = {digest(s.model_dump(mode="json", exclude={"bars", "snapshot_id"})) for s in snapshots}
    if len(contexts) != 1:
        raise ValueError("mixed provenance/calendar/spec contexts require explicit separate selection")
    groups = {}
    for snapshot in snapshots:
        for bar in snapshot.bars:
            revisions = groups.setdefault(bar.key, {})
            prior = revisions.get(bar.revision_id)
            if prior is not None and prior != bar:
                raise ValueError("same-version contradictory content")
            revisions[bar.revision_id] = bar
    selected, unknown, future = [], 0, 0
    for revisions in groups.values():
        children = {}
        roots = []
        for bar in revisions.values():
            if bar.supersedes is None:
                roots.append(bar)
            else:
                parent = revisions.get(bar.supersedes)
                if parent is None:
                    raise ValueError("missing superseded revision provenance")
                if bar.supersedes in children:
                    raise ValueError("ambiguous branched revisions")
                children[bar.supersedes] = bar
        if len(roots) != 1:
            raise ValueError("ambiguous revision roots or cycle")
        chain, current = [], roots[0]
        while current is not None:
            chain.append(current)
            current = children.get(current.revision_id)
            if len(chain) > len(revisions):
                raise ValueError("revision cycle")
        if len(chain) != len(revisions):
            raise ValueError("disconnected revision cycle")
        eligible, previous_time = [], None
        for bar in chain:
            available = bar.availability.source_time() if mode == "declared_source" else bar.availability.local_received_at
            if available is None:
                unknown += 1
            else:
                if previous_time is not None and available <= previous_time:
                    raise ValueError("revision knowledge times must strictly increase; ties refused")
                previous_time = available
                if available <= cutoff:
                    eligible.append(bar)
                else:
                    future += 1
        if eligible:
            selected.append(eligible[-1])
    return Selection(tuple(sorted(selected, key=lambda b: b.key)), unknown, future, mode, cutoff.isoformat())


def legacy_frame(bars: tuple[Bar, ...]) -> pd.DataFrame:
    if not bars or len({b.key for b in bars}) != len(bars):
        raise ValueError("select a nonempty single vintage before legacy normalization")
    rows = []
    for b in bars:
        row = market_content(b)
        row.pop("session")
        row["timestamp"] = pd.Timestamp(b.session, tz="UTC")
        row["expiry"] = pd.Timestamp(b.expiry, tz="UTC")
        row["timezone"] = get_instrument(b.root_symbol).session.timezone
        rows.append(row)
    return pd.DataFrame(rows)


def legacy_status(_frame) -> dict:
    return {"status": "incomplete", "strict_supported": False,
            "limitations": ["Legacy timestamp is a label, not an attested event instant",
                            "No field availability, local receipt, calendar or revision provenance"]}
