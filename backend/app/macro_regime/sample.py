"""
Deterministic static-sample datasets for the Macro Regime Lab (Phase 31.0).

Six illustrative macro states (goldilocks growth, inflation shock, recession /
credit stress, stagflation, liquidity easing, strong-USD tightening), each with
twelve hand-written indicators (two per category, values placed at chosen
z-scores) and a shared eleven-asset cross-asset assumption set. Identical every
run and every test. Not live macro or market data (no FRED, no yfinance), not
advice.
"""

from __future__ import annotations

from typing import List, Tuple

from app.macro_regime.models import (
    AssetClassInput,
    MacroIndicatorInput,
    MacroRegimeAnalysisRequest,
    MacroRegimeSampleResponse,
)

DISCLAIMER = (
    "Static illustrative sample data. Macro regime and cross-asset allocation "
    "analytics are educational and not investment, trading, asset-allocation, "
    "legal, tax, or risk-management advice."
)

# Indicator library: (name, category, long_run_mean, long_run_std, direction)
# The direction flag is a sign convention that orients each indicator so a
# HIGHER category score means: stronger growth / hotter inflation / tighter
# policy / easier liquidity / more credit stress / stronger USD pressure.
_INDICATORS = [
    ("Composite PMI Sample", "growth", 52.0, 4.0, "higher_is_expansionary"),
    ("Payroll Growth Sample (k)", "growth", 150.0, 80.0, "higher_is_expansionary"),
    ("CPI YoY Sample (%)", "inflation", 2.5, 1.2, "higher_is_expansionary"),
    ("Wage Growth Sample (%)", "inflation", 3.0, 1.0, "higher_is_expansionary"),
    ("Policy Rate vs Neutral Sample (%)", "policy", 0.0, 1.0, "higher_is_expansionary"),
    ("Real Policy Rate Sample (%)", "policy", 0.5, 1.0, "higher_is_expansionary"),
    ("Money Supply Growth Sample (%)", "liquidity", 6.0, 3.0, "higher_is_expansionary"),
    ("Funding Spread Sample (%)", "liquidity", 0.4, 0.25, "higher_is_contractionary"),
    ("HY Spread Sample (%)", "credit", 4.5, 1.5, "higher_is_expansionary"),
    ("Downgrade Ratio Sample", "credit", 1.0, 0.4, "higher_is_expansionary"),
    ("USD Index vs Trend Sample (%)", "fx", 0.0, 3.0, "higher_is_expansionary"),
    ("EM FX Stress Sample", "fx", 1.0, 0.5, "higher_is_expansionary"),
]


def _indicators_for(targets: dict) -> List[MacroIndicatorInput]:
    """Place each indicator's value at the category's target z-score."""
    out: List[MacroIndicatorInput] = []
    for name, cat, mean, std, direction in _INDICATORS:
        t = targets[cat]
        z = t if direction == "higher_is_expansionary" else -t
        out.append(
            MacroIndicatorInput(
                name=name,
                category=cat,
                value=mean + z * std,
                long_run_mean=mean,
                long_run_std=std,
                direction=direction,
                weight=1.0,
            )
        )
    return out


# Shared cross-asset assumption set:
# (id, name, category, μ, σ, liquidity, β_growth, β_inflation, β_rate, β_usd, β_credit)
_ASSETS: List[Tuple] = [
    ("US_EQUITY_SAMPLE", "US Equity Sample", "equity", 0.065, 0.16, 0.95, 0.020, -0.008, -0.010, -0.004, 0.016),
    ("INTL_EQUITY_SAMPLE", "International Equity Sample", "equity", 0.060, 0.17, 0.90, 0.018, -0.006, -0.008, -0.012, 0.014),
    ("LONG_TSY_SAMPLE", "Long Duration Treasury Sample", "duration", 0.045, 0.14, 0.90, -0.008, -0.014, -0.018, 0.002, -0.006),
    ("SHORT_TSY_SAMPLE", "Short Duration Treasury Sample", "duration", 0.042, 0.03, 0.95, -0.002, -0.004, -0.004, 0.001, -0.003),
    ("IG_CREDIT_SAMPLE", "Investment Grade Credit Sample", "credit", 0.050, 0.07, 0.85, 0.004, -0.006, -0.008, 0.000, 0.010),
    ("HY_CREDIT_SAMPLE", "High Yield Credit Sample", "credit", 0.062, 0.10, 0.75, 0.010, -0.004, -0.006, -0.002, 0.020),
    ("GOLD_SAMPLE", "Gold Sample", "commodity", 0.045, 0.15, 0.85, -0.004, 0.012, -0.008, -0.012, -0.008),
    ("COMMODITY_SAMPLE", "Broad Commodity Sample", "commodity", 0.048, 0.18, 0.80, 0.010, 0.014, -0.004, -0.010, 0.006),
    ("REIT_SAMPLE", "REIT Sample", "real_asset", 0.058, 0.18, 0.80, 0.012, 0.002, -0.014, -0.004, 0.012),
    ("USD_CASH_SAMPLE", "USD Cash Sample", "cash", 0.040, 0.005, 1.00, 0.000, 0.002, 0.006, 0.004, 0.000),
    ("CRYPTO_SAMPLE", "Crypto Basket Sample", "crypto", 0.090, 0.60, 0.70, 0.020, 0.004, -0.012, -0.014, 0.012),
]


def _assets() -> List[AssetClassInput]:
    return [
        AssetClassInput(
            asset_id=a[0], asset_name=a[1], category=a[2],
            expected_return=a[3], volatility=a[4], liquidity_score=a[5],
            growth_beta=a[6], inflation_beta=a[7], rate_beta=a[8],
            usd_beta=a[9], credit_beta=a[10],
        )
        for a in _ASSETS
    ]


# Category z-score targets per sample: growth, inflation, policy, liquidity, credit, fx.
_SAMPLE_TARGETS = [
    ("GOLDILOCKS_SAMPLE", "Goldilocks Growth Sample",
     {"growth": 1.0, "inflation": -0.5, "policy": -0.3, "liquidity": 0.7, "credit": -0.5, "fx": -0.2}),
    ("INFLATION_SHOCK_SAMPLE", "Inflation Shock Sample",
     {"growth": 0.2, "inflation": 1.5, "policy": 1.0, "liquidity": -0.5, "credit": 0.3, "fx": 0.4}),
    ("RECESSION_CREDIT_SAMPLE", "Recession Credit Stress Sample",
     {"growth": -1.2, "inflation": -0.3, "policy": -0.5, "liquidity": -0.5, "credit": 1.5, "fx": 0.3}),
    ("STAGFLATION_SAMPLE", "Stagflation Sample",
     {"growth": -1.0, "inflation": 1.2, "policy": 0.4, "liquidity": -0.4, "credit": 0.4, "fx": 0.2}),
    ("LIQUIDITY_EASING_SAMPLE", "Liquidity Easing Sample",
     {"growth": 0.2, "inflation": -0.2, "policy": -0.8, "liquidity": 1.2, "credit": -0.3, "fx": -0.3}),
    ("STRONG_USD_SAMPLE", "Strong USD Tightening Sample",
     {"growth": -0.2, "inflation": 0.3, "policy": 0.8, "liquidity": -0.4, "credit": 0.3, "fx": 1.3}),
]


def sample_requests() -> List[MacroRegimeAnalysisRequest]:
    return [
        MacroRegimeAnalysisRequest(
            sample_id=sid,
            sample_name=name,
            indicators=_indicators_for(targets),
            assets=_assets(),
            risk_aversion_lambda=0.2,
            liquidity_preference_eta=0.01,
        )
        for sid, name, targets in _SAMPLE_TARGETS
    ]


def build_sample_response() -> MacroRegimeSampleResponse:
    return MacroRegimeSampleResponse(
        samples=sample_requests(),
        disclaimer=DISCLAIMER,
        notes=[
            "Six illustrative macro states (goldilocks growth, inflation shock, "
            "recession/credit stress, stagflation, liquidity easing, strong-USD "
            "tightening) with twelve hand-written indicators each and a shared "
            "eleven-asset cross-asset assumption set.",
            "Select / edit a sample in the lab to explore the analytics.",
            "Not live macro or market data (no FRED or yfinance in this lab) — and "
            "not investment, trading, or asset-allocation advice.",
        ],
    )
