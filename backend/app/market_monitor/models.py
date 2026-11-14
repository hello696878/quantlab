from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Instrument(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    kind: str
    region: str
    unit: str
    currency: str | None = None
    source: str
    symbol: str
    source_url: str
    note: str


class Observation(BaseModel):
    instrument_id: str
    value: float = Field(allow_inf_nan=False)
    observation_date: date
    unit: str
    change: float | None = Field(default=None, allow_inf_nan=False)
    change_unit: str | None = None
    previous_date: date | None = None
    timezone: str | None = None
    session_complete: bool | None = None


class NewsItem(BaseModel):
    id: str
    title: str
    url: str
    published_at: datetime | None = None


class Filing(BaseModel):
    accession: str
    form: str
    filing_date: date
    accepted_at: datetime | None = None
    url: str


class CalendarEvent(BaseModel):
    id: str
    title: str
    start_date: date
    end_date: date
    url: str


class SourceData(BaseModel):
    observations: list[Observation] = Field(default_factory=list)
    items: list[NewsItem] = Field(default_factory=list)
    filings: list[Filing] = Field(default_factory=list)
    events: list[CalendarEvent] = Field(default_factory=list)
    message: str | None = None


class SourceBlock(SourceData):
    id: str
    label: str
    category: str
    cadence: str
    source_url: str
    status: Literal["ready", "stale", "unavailable", "not_configured"]
    retrieved_at: datetime | None = None
    checked_at: datetime | None = None


class Snapshot(BaseModel):
    generated_at: datetime
    sources: list[SourceBlock]
    company_id: str | None
    eia_schedule_url: str = "https://www.eia.gov/petroleum/supply/weekly/schedule.php"
