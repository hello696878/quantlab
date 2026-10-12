"""Finite user-declared sessions, never an official exchange calendar."""
from __future__ import annotations

import importlib.metadata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import TZPATH, ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, StrictBool, model_validator

from app.run_replay.identity import digest
from .models import Frozen, Id, Instant, Label, label


def zone(name: str) -> ZoneInfo:
    if type(name) is not str or name.startswith(("/", "\\")) or ".." in name.split("/"):
        raise ValueError("use an explicit named timezone")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("declared timezone unavailable; no guessed offset") from exc


def timezone_provenance(name: str) -> dict:
    zone(name)
    system = next((Path(root) / name for root in TZPATH if (Path(root) / name).is_file()), None)
    try:
        package = importlib.metadata.version("tzdata")
    except importlib.metadata.PackageNotFoundError:
        package = None
    version = None
    if system:
        for root in TZPATH:
            zi = Path(root) / "tzdata.zi"
            if zi.is_file():
                with zi.open(encoding="utf-8") as source:
                    first = source.readline(120).strip()
                if first.startswith("# version "):
                    version = first.removeprefix("# version ")
                break
    return {"timezone": name, "source": "system_TZPATH" if system else "tzdata_package",
            "source_version": version if system else package, "installed_tzdata": package,
            "pinned": False}


def local_to_utc(value: datetime, name: str, *, fold: int | None = None) -> datetime:
    if (type(value) is not datetime or value.tzinfo is not None or
            fold is not None and (type(fold) is not int or fold not in (0, 1))):
        raise ValueError("local wall time must be naive with an optional explicit fold 0/1")
    tz = zone(name)
    candidates = {}
    for f in (0, 1):
        aware = value.replace(tzinfo=tz, fold=f)
        utc = aware.astimezone(timezone.utc)
        back = utc.astimezone(tz)
        if back.replace(tzinfo=None) == value and back.fold == f:
            candidates[f] = utc
    if not candidates:
        raise ValueError("nonexistent local time")
    if len(set(candidates.values())) > 1 and fold is None:
        raise ValueError("ambiguous local time requires fold")
    chosen = 0 if fold is None else fold
    if chosen not in candidates:
        raise ValueError("fold is not valid for this local time")
    return candidates[chosen]


class Interval(Frozen):
    start: Instant
    end: Instant

    @model_validator(mode="after")
    def ordered(self):
        if self.start >= self.end:
            raise ValueError("interval start must precede end")
        return self


class Session(Frozen):
    label: Label
    open: StrictBool
    interval: Interval | None
    breaks: tuple[Interval, ...] = Field(default=(), max_length=8)
    early_close: StrictBool = False

    @model_validator(mode="after")
    def boundaries(self):
        if not self.open:
            if self.interval is not None or self.breaks or self.early_close:
                raise ValueError("closed label cannot contain trading intervals")
        elif self.interval is None:
            raise ValueError("open session requires an explicit UTC interval")
        else:
            previous = self.interval.start
            for brk in self.breaks:
                if brk.start < previous or brk.start <= self.interval.start or brk.end >= self.interval.end:
                    raise ValueError("breaks must be ordered, disjoint and inside the session")
                previous = brk.end
        return self

    @property
    def duration_seconds(self):
        if self.interval is None:
            return 0
        return (self.interval.end - self.interval.start).total_seconds() - sum(
            (b.end - b.start).total_seconds() for b in self.breaks)


class DeclaredCalendar(Frozen):
    schema_version: str = Field(pattern=r"^declared_futures_calendar_v1$")
    calendar_id: Id
    version: Id
    timezone: str = Field(min_length=1, max_length=80)
    coverage_start: Label
    coverage_end: Label
    declared_available_at: Instant | None
    sessions: tuple[Session, ...] = Field(min_length=1, max_length=3660)

    @model_validator(mode="after")
    def complete(self):
        zone(self.timezone)
        days = (self.coverage_end - self.coverage_start).days + 1
        if not 1 <= days <= 3660:
            raise ValueError("calendar coverage must be 1..3660 days")
        expected = [self.coverage_start + timedelta(days=i) for i in range(days)]
        if [s.label for s in self.sessions] != expected:
            raise ValueError("every covered label must be classified exactly once in order")
        previous = None
        for session in self.sessions:
            if session.open:
                if (session.interval.end.astimezone(zone(self.timezone)).date() != session.label or
                        session.interval.end - session.interval.start > timedelta(hours=36)):
                    raise ValueError("daily interval must end on its declared local trading label and span <=36h")
                if previous is not None and session.interval.start < previous:
                    raise ValueError("session UTC intervals overlap or are unordered")
                previous = session.interval.end
        return self

    @property
    def fingerprint(self):
        return digest({"namespace": "declared_futures_calendar_v1", "calendar": self.model_dump(mode="json")})

    def lookup(self, day: date) -> Session:
        day = label(day)
        if day < self.coverage_start or day > self.coverage_end:
            raise ValueError("calendar coverage unknown for requested label")
        return self.sessions[(day - self.coverage_start).days]

    def between(self, start: date, end: date) -> tuple[date, ...]:
        start, end = label(start), label(end)
        self.lookup(start)
        self.lookup(end)
        if start > end:
            raise ValueError("reversed session range")
        return tuple(s.label for s in self.sessions if s.open and start <= s.label <= end)

    def count(self, start: date, end: date) -> int:
        return len(self.between(start, end))

    def previous(self, day: date) -> date:
        day = label(day)
        self.lookup(day)
        found = [s.label for s in self.sessions if s.open and s.label < day]
        if not found:
            raise ValueError("previous session outside declared coverage")
        return found[-1]

    def next(self, day: date) -> date:
        day = label(day)
        self.lookup(day)
        found = [s.label for s in self.sessions if s.open and s.label > day]
        if not found:
            raise ValueError("next session outside declared coverage")
        return found[0]

    def on_or_before(self, day: date) -> date:
        day = label(day)
        self.lookup(day)
        return day if self.lookup(day).open else self.previous(day)
