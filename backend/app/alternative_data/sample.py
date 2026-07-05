"""
Deterministic static-sample event sets for the Alternative Data Lab (Phase 30.0).

Five illustrative samples (mega-cap equity news, crypto sentiment stress,
earnings surprise, macro shock news, supply-chain alternative data), each a
hand-written table of events on a static January-2026 sample timeline with
sentiment / intensity / novelty / reliability / relevance scores, observed
forward-return paths, and publication-lag data. Identical every run and every
test. Not live news, not social scraping, no LLM or provider APIs, not advice.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Tuple

from app.alternative_data.models import (
    AlternativeDataAnalysisRequest,
    AlternativeDataEventInput,
    AlternativeDataSampleResponse,
)

DISCLAIMER = (
    "Static illustrative sample data. Alternative-data, sentiment, event-study, "
    "and signal-quality analytics are educational and not investment, trading, "
    "legal, tax, or risk-management advice."
)

_BASE = datetime(2026, 1, 2, 9, 30)  # static sample timeline anchor (no live clock)


def _ev(
    event_id: str,
    day: int,
    hour: int,
    symbol: str,
    source_type: str,
    headline: str,
    s: float,
    intensity: float,
    novelty: float,
    reliability: float,
    relevance: float,
    lag_min: float,
    r1: float,
    r5: float,
    r20: float,
) -> AlternativeDataEventInput:
    ts = _BASE + timedelta(days=day, hours=hour - 9)
    feat = ts + timedelta(minutes=lag_min)
    return AlternativeDataEventInput(
        event_id=event_id,
        timestamp=ts.strftime("%Y-%m-%dT%H:%M:00Z"),
        symbol=symbol,
        source_type=source_type,
        headline=headline,
        sentiment_score=s,
        event_intensity=intensity,
        novelty_score=novelty,
        source_reliability=reliability,
        relevance_score=relevance,
        observed_return_1d=r1,
        observed_return_5d=r5,
        observed_return_20d=r20,
        publication_lag_minutes=lag_min,
        feature_available_timestamp=feat.strftime("%Y-%m-%dT%H:%M:00Z"),
    )


def _build(sample_id: str, sample_name: str, events: List[AlternativeDataEventInput]) -> AlternativeDataAnalysisRequest:
    return AlternativeDataAnalysisRequest(
        sample_id=sample_id,
        sample_name=sample_name,
        events=events,
        lambda_novelty=0.5,
        gamma_freshness_per_hour=0.1,
    )


def sample_requests() -> List[AlternativeDataAnalysisRequest]:
    return [
        # Mega-cap equity news — clean, well-aligned signal → clean positive.
        _build(
            "MEGACAP_NEWS_SAMPLE", "Mega Cap Equity News Sample",
            [
                _ev("MC-01", 0, 10, "MEGA_A", "product", "Sample: flagship product launch beats expectations", 0.80, 0.70, 0.60, 0.85, 0.90, 25.0, 0.021, 0.034, 0.028),
                _ev("MC-02", 2, 11, "MEGA_A", "regulatory", "Sample: regulator opens inquiry into unit", -0.70, 0.60, 0.50, 0.80, 0.85, 40.0, -0.018, -0.026, -0.015),
                _ev("MC-03", 4, 14, "MEGA_B", "news", "Sample: analyst commentary broadly neutral", 0.05, 0.30, 0.20, 0.75, 0.60, 60.0, 0.002, 0.004, 0.004),
                _ev("MC-04", 6, 16, "MEGA_B", "earnings", "Sample: high-novelty earnings surprise", 0.90, 0.90, 0.90, 0.90, 0.95, 15.0, 0.032, 0.048, 0.036),
                _ev("MC-05", 8, 12, "MEGA_C", "supply_chain", "Sample: component shortage disrupts assembly", -0.50, 0.55, 0.45, 0.70, 0.80, 90.0, -0.012, -0.020, -0.011),
                _ev("MC-06", 10, 13, "MEGA_C", "social", "Sample: social sentiment burst on launch demo", 0.60, 0.50, 0.35, 0.45, 0.70, 10.0, 0.011, 0.016, 0.006),
                _ev("MC-07", 13, 10, "MEGA_A", "news", "Sample: strategic partnership announced", 0.45, 0.40, 0.40, 0.80, 0.75, 35.0, 0.008, 0.012, 0.010),
                _ev("MC-08", 15, 15, "MEGA_B", "social", "Sample: guidance-cut rumor circulates", -0.35, 0.45, 0.30, 0.55, 0.65, 50.0, -0.006, -0.009, -0.002),
            ],
        ),
        # Crypto sentiment — social-heavy, low source reliability → low reliability.
        _build(
            "CRYPTO_SENTIMENT_SAMPLE", "Crypto Sentiment Stress Sample",
            [
                _ev("CS-01", 0, 11, "COIN_A", "social", "Sample: viral thread calls for breakout", 0.90, 0.80, 0.50, 0.35, 0.70, 8.0, 0.030, 0.038, 0.010),
                _ev("CS-02", 2, 15, "COIN_A", "social", "Sample: influencer warns of rug risk", -0.80, 0.75, 0.45, 0.40, 0.65, 12.0, -0.026, -0.031, -0.008),
                _ev("CS-03", 5, 12, "COIN_B", "news", "Sample: exchange listing chatter", 0.70, 0.60, 0.55, 0.30, 0.75, 20.0, 0.018, 0.026, 0.012),
                _ev("CS-04", 7, 17, "COIN_B", "social", "Sample: fee-spike complaints trend", -0.60, 0.55, 0.35, 0.45, 0.60, 15.0, -0.014, -0.018, -0.004),
                _ev("CS-05", 10, 13, "COIN_C", "social", "Sample: airdrop speculation swells", 0.50, 0.65, 0.60, 0.35, 0.55, 6.0, 0.010, 0.015, 0.002),
                _ev("CS-06", 12, 18, "COIN_C", "regulatory", "Sample: offshore regulator comment reposted", -0.40, 0.50, 0.30, 0.40, 0.60, 30.0, -0.008, -0.012, -0.006),
            ],
        ),
        # Earnings surprises — mostly negative but well-aligned → clean negative.
        _build(
            "EARNINGS_SURPRISE_SAMPLE", "Earnings Surprise Sample",
            [
                _ev("ES-01", 0, 16, "EQTY_A", "earnings", "Sample: large EPS miss and weak guide", -0.85, 0.90, 0.80, 0.90, 0.95, 12.0, -0.041, -0.055, -0.038),
                _ev("ES-02", 3, 16, "EQTY_B", "earnings", "Sample: margin compression flagged", -0.60, 0.70, 0.55, 0.85, 0.90, 18.0, -0.022, -0.030, -0.018),
                _ev("ES-03", 6, 16, "EQTY_C", "earnings", "Sample: modest beat on cost control", 0.40, 0.55, 0.45, 0.85, 0.85, 15.0, 0.014, 0.020, 0.012),
                _ev("ES-04", 9, 16, "EQTY_D", "earnings", "Sample: revenue shortfall on churn", -0.70, 0.75, 0.60, 0.90, 0.90, 10.0, -0.028, -0.039, -0.024),
                _ev("ES-05", 12, 16, "EQTY_E", "earnings", "Sample: small beat, cautious tone", 0.30, 0.45, 0.35, 0.80, 0.80, 20.0, 0.008, 0.011, 0.006),
                _ev("ES-06", 15, 16, "EQTY_F", "earnings", "Sample: guidance withdrawn", -0.50, 0.65, 0.50, 0.85, 0.85, 14.0, -0.017, -0.024, -0.014),
            ],
        ),
        # Macro shock headlines — signals poorly aligned with returns → noisy.
        _build(
            "MACRO_SHOCK_SAMPLE", "Macro Shock News Sample",
            [
                _ev("MS-01", 0, 8, "INDEX_X", "macro", "Sample: hot inflation print", 0.60, 0.80, 0.55, 0.85, 0.80, 20.0, -0.004, -0.008, -0.002),
                _ev("MS-02", 3, 8, "INDEX_X", "macro", "Sample: soft jobs report", -0.50, 0.70, 0.50, 0.85, 0.80, 25.0, -0.001, -0.002, -0.001),
                _ev("MS-03", 6, 8, "INDEX_Y", "macro", "Sample: hawkish central-bank remarks", 0.40, 0.65, 0.40, 0.80, 0.75, 30.0, 0.004, 0.007, 0.002),
                _ev("MS-04", 9, 8, "INDEX_Y", "macro", "Sample: surprise PMI rebound", -0.60, 0.75, 0.45, 0.85, 0.80, 22.0, 0.002, 0.003, 0.001),
                _ev("MS-05", 12, 8, "INDEX_Z", "macro", "Sample: trade-talks stall headline", 0.50, 0.60, 0.35, 0.80, 0.70, 28.0, 0.003, 0.006, 0.002),
                _ev("MS-06", 15, 8, "INDEX_Z", "macro", "Sample: energy price spike", -0.40, 0.70, 0.40, 0.85, 0.75, 26.0, -0.004, -0.007, -0.002),
            ],
        ),
        # Supply-chain alt data — slow-arriving datasets → stale signal.
        _build(
            "SUPPLY_CHAIN_SAMPLE", "Supply Chain Alternative Data Sample",
            [
                _ev("SC-01", 0, 12, "SHIP_A", "supply_chain", "Sample: port congestion index jumps", -0.55, 0.65, 0.50, 0.75, 0.80, 720.0, -0.013, -0.019, -0.010),
                _ev("SC-02", 3, 12, "SHIP_A", "supply_chain", "Sample: freight rates roll over", 0.45, 0.55, 0.45, 0.70, 0.75, 960.0, 0.009, 0.014, 0.008),
                _ev("SC-03", 6, 12, "MFG_B", "supply_chain", "Sample: supplier lead times lengthen", -0.50, 0.60, 0.40, 0.75, 0.80, 1440.0, -0.011, -0.016, -0.008),
                _ev("SC-04", 9, 12, "MFG_B", "supply_chain", "Sample: inventory restocking detected", 0.55, 0.60, 0.55, 0.70, 0.80, 1200.0, 0.012, 0.018, 0.009),
                _ev("SC-05", 12, 12, "RETL_C", "supply_chain", "Sample: shipment volumes soften", -0.40, 0.50, 0.35, 0.75, 0.70, 2160.0, -0.007, -0.011, -0.005),
                _ev("SC-06", 15, 12, "RETL_C", "supply_chain", "Sample: air-cargo bookings recover", 0.35, 0.45, 0.40, 0.70, 0.70, 1800.0, 0.006, 0.009, 0.005),
            ],
        ),
    ]


def build_sample_response() -> AlternativeDataSampleResponse:
    return AlternativeDataSampleResponse(
        samples=sample_requests(),
        disclaimer=DISCLAIMER,
        notes=[
            "Five illustrative event sets (mega-cap equity news, crypto sentiment "
            "stress, earnings surprise, macro shock news, supply-chain alternative "
            "data) on a static January-2026 sample timeline with hand-written "
            "sentiment/novelty/reliability scores and observed return paths.",
            "Select / edit a sample in the lab to explore the analytics.",
            "Not live news, social media, or market data; no scraping, LLM, or "
            "provider APIs — and not investment, trading, or signal advice.",
        ],
    )
