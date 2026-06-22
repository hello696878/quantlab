"""
Typed Pydantic models for the Global Markets Globe data layer (Phase 20.2).

These describe a country / market **dossier**. Every payload is **static
illustrative sample data** — there is no live market data, FX, macro, or news.
The `is_sample` flags and `source_status` make that explicit and machine-readable
so a future phase can flip individual sources to live without changing the shape.
"""

from __future__ import annotations

from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, StringConstraints

Region = Literal["Americas", "Europe", "Asia-Pacific"]
Sentiment = Literal["Bullish", "Bearish", "Neutral"]
SourceState = Literal[
    "static_sample",
    "live",
    "delayed",
    "planned",
    "fred_live",
    "fred_unavailable",
]
DataStatus = Literal["static_sample", "mixed_static_and_fred"]
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Latitude = Annotated[FiniteFloat, Field(ge=-90.0, le=90.0)]
Longitude = Annotated[FiniteFloat, Field(ge=-180.0, le=180.0)]


class GlobeModel(BaseModel):
    """Strict base model for stable, JSON-safe globe API payloads."""

    model_config = ConfigDict(extra="forbid")


class MarketIndex(GlobeModel):
    name: NonEmptyStr
    ticker: NonEmptyStr
    level: FiniteFloat
    change_pct: FiniteFloat  # percent (0.42 == +0.42%)
    sparkline: List[FiniteFloat] = Field(min_length=2)
    is_sample: bool = True


class MarketMacro(GlobeModel):
    gdp_growth: FiniteFloat
    inflation: FiniteFloat
    unemployment: FiniteFloat
    policy_rate: FiniteFloat
    debt_to_gdp: FiniteFloat
    is_sample: bool = True
    # Set when (some) fields are enriched from FRED (e.g. "2024-05-01").
    as_of_date: Optional[NonEmptyStr] = None


class MarketFx(GlobeModel):
    pair: NonEmptyStr
    rate: FiniteFloat
    change_pct: FiniteFloat  # percent
    is_sample: bool = True


class MarketRates(GlobeModel):
    policy_rate: FiniteFloat
    ten_year_yield: Optional[FiniteFloat] = None
    is_sample: bool = True


class MarketStructure(GlobeModel):
    market_cap: NonEmptyStr
    listed_companies: NonEmptyStr
    settlement: NonEmptyStr
    notes: NonEmptyStr
    is_sample: bool = True


class MarketHeadline(GlobeModel):
    title: NonEmptyStr
    sentiment: Sentiment
    is_sample: bool = True


class MarketLink(GlobeModel):
    label: NonEmptyStr
    href: NonEmptyStr


class SourceStatus(GlobeModel):
    macro: SourceState = "static_sample"
    indices: SourceState = "static_sample"
    fx: SourceState = "static_sample"
    news: SourceState = "static_sample"


class MarketDossier(GlobeModel):
    id: NonEmptyStr
    country: NonEmptyStr
    region: Region
    subregion: NonEmptyStr
    flag: NonEmptyStr
    lat: Latitude
    lon: Longitude
    currency: NonEmptyStr
    exchange: NonEmptyStr
    trading_hours: NonEmptyStr
    timezone: NonEmptyStr
    static_data_notice: NonEmptyStr
    indices: List[MarketIndex] = Field(min_length=1)
    macro: MarketMacro
    fx: List[MarketFx] = Field(min_length=1)
    rates: MarketRates
    market_structure: MarketStructure
    headlines: List[MarketHeadline] = Field(min_length=1)
    links: List[MarketLink] = Field(min_length=1)
    source_status: SourceStatus


class MarketsResponse(GlobeModel):
    markets: List[MarketDossier]
    count: int = Field(ge=0)
    data_status: DataStatus
    notice: NonEmptyStr
    warnings: List[NonEmptyStr] = Field(default_factory=list)


class RegionCount(GlobeModel):
    region: Region
    count: int = Field(ge=0)


class RegionsResponse(GlobeModel):
    regions: List[RegionCount]
    data_status: Literal["static_sample"]
    notice: NonEmptyStr
