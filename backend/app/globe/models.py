"""
Typed Pydantic models for the Global Markets Globe data layer (Phase 20.2).

These describe a country / market **dossier**. Every payload is **static
illustrative sample data** — there is no live market data, FX, macro, or news.
The `is_sample` flags and `source_status` make that explicit and machine-readable
so a future phase can flip individual sources to live without changing the shape.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Region = Literal["Americas", "Europe", "Asia-Pacific"]
Sentiment = Literal["Bullish", "Bearish", "Neutral"]
SourceState = Literal["static_sample", "live", "delayed", "planned"]


class MarketIndex(BaseModel):
    name: str
    ticker: str
    level: float
    change_pct: float  # percent (0.42 == +0.42%)
    sparkline: List[float]
    is_sample: bool = True


class MarketMacro(BaseModel):
    gdp_growth: float
    inflation: float
    unemployment: float
    policy_rate: float
    debt_to_gdp: float
    is_sample: bool = True


class MarketFx(BaseModel):
    pair: str
    rate: float
    change_pct: float  # percent
    is_sample: bool = True


class MarketRates(BaseModel):
    policy_rate: float
    ten_year_yield: Optional[float] = None
    is_sample: bool = True


class MarketStructure(BaseModel):
    market_cap: str
    listed_companies: str
    settlement: str
    notes: str
    is_sample: bool = True


class MarketHeadline(BaseModel):
    title: str
    sentiment: Sentiment
    is_sample: bool = True


class MarketLink(BaseModel):
    label: str
    href: str


class SourceStatus(BaseModel):
    macro: SourceState = "static_sample"
    indices: SourceState = "static_sample"
    fx: SourceState = "static_sample"
    news: SourceState = "static_sample"


class MarketDossier(BaseModel):
    id: str
    country: str
    region: Region
    subregion: str
    flag: str
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    currency: str
    exchange: str
    trading_hours: str
    timezone: str
    static_data_notice: str
    indices: List[MarketIndex]
    macro: MarketMacro
    fx: List[MarketFx]
    rates: MarketRates
    market_structure: MarketStructure
    headlines: List[MarketHeadline]
    links: List[MarketLink]
    source_status: SourceStatus


class MarketsResponse(BaseModel):
    markets: List[MarketDossier]
    count: int
    data_status: str
    notice: str


class RegionCount(BaseModel):
    region: Region
    count: int


class RegionsResponse(BaseModel):
    regions: List[RegionCount]
    data_status: str
    notice: str
