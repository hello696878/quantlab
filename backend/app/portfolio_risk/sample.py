"""
Deterministic static-sample portfolio for the Portfolio Risk Lab (Phase 21.0).

Eight illustrative assets across equities, rates, credit, gold, and cash. The
monthly return series are generated **deterministically** from a fixed seed and a
hand-built correlation structure, so every run — and every test — sees identical
numbers. These values are illustrative only: not live data, not advice.
"""

from __future__ import annotations

from typing import List

import numpy as np

from app.portfolio_risk.models import PortfolioAsset, StressScenario

# Fixed seed → reproducible monthly series (documented so tests stay stable).
SAMPLE_SEED = 20240517
# Three years of illustrative monthly returns per asset.
SAMPLE_MONTHS = 36

DISCLAIMER = (
    "Static illustrative sample data. Portfolio analytics are educational and "
    "not investment advice."
)

# id, name, ticker, asset_class, region, annual expected return, annual vol, weight
_SPECS = [
    ("us_eq", "US Equity", "USEQ", "Equity", "Americas", 0.080, 0.160, 0.25),
    ("tw_eq", "Taiwan Equity", "TWEQ", "Equity", "Asia-Pacific", 0.100, 0.240, 0.08),
    ("jp_eq", "Japan Equity", "JPEQ", "Equity", "Asia-Pacific", 0.060, 0.170, 0.07),
    ("em_eq", "Emerging Market Equity", "EMEQ", "Equity", "Global", 0.090, 0.200, 0.10),
    ("us_treas", "US Treasury", "UST", "Government Bond", "Americas", 0.030, 0.060, 0.20),
    ("ig_credit", "Investment Grade Credit", "IGC", "Credit", "Americas", 0.045, 0.080, 0.15),
    ("gold", "Gold", "GOLD", "Commodity", "Global", 0.040, 0.150, 0.10),
    ("usd_cash", "USD Cash", "CASH", "Cash", "Americas", 0.020, 0.005, 0.05),
]

# Symmetric correlation target (order matches _SPECS). Equities co-move; bonds
# diversify equity risk; gold is a mild diversifier; cash is near-uncorrelated.
_CORR_TARGET = np.array(
    [
        # us_eq  tw_eq  jp_eq  em_eq  ust    igc    gold   cash
        [1.00, 0.75, 0.65, 0.80, -0.25, 0.35, -0.05, 0.00],
        [0.75, 1.00, 0.60, 0.78, -0.20, 0.30, 0.00, 0.00],
        [0.65, 0.60, 1.00, 0.62, -0.15, 0.28, 0.02, 0.00],
        [0.80, 0.78, 0.62, 1.00, -0.22, 0.33, 0.05, 0.00],
        [-0.25, -0.20, -0.15, -0.22, 1.00, 0.55, 0.25, 0.10],
        [0.35, 0.30, 0.28, 0.33, 0.55, 1.00, 0.20, 0.05],
        [-0.05, 0.00, 0.02, 0.05, 0.25, 0.20, 1.00, 0.03],
        [0.00, 0.00, 0.00, 0.00, 0.10, 0.05, 0.03, 1.00],
    ],
    dtype=float,
)


def _monthly_series() -> np.ndarray:
    """Deterministic (SAMPLE_MONTHS, n) matrix of correlated monthly returns."""
    n = len(_SPECS)
    ann_ret = np.array([s[5] for s in _SPECS], dtype=float)
    ann_vol = np.array([s[6] for s in _SPECS], dtype=float)
    monthly_mean = ann_ret / 12.0
    monthly_vol = ann_vol / np.sqrt(12.0)

    # Ridge the correlation target so it is positive-definite for Cholesky.
    corr = 0.85 * _CORR_TARGET + 0.15 * np.eye(n)
    chol = np.linalg.cholesky(corr)

    rng = np.random.default_rng(SAMPLE_SEED)
    z = rng.standard_normal((SAMPLE_MONTHS, n))
    correlated = z @ chol.T  # unit-variance, target correlation
    series = monthly_mean + monthly_vol * correlated  # (months, n)
    return np.round(series, 6)


def sample_assets() -> List[PortfolioAsset]:
    """Build the eight deterministic sample assets."""
    series = _monthly_series()  # (months, n)
    assets: List[PortfolioAsset] = []
    for i, (aid, name, ticker, asset_class, region, exp_ret, vol, weight) in enumerate(
        _SPECS
    ):
        assets.append(
            PortfolioAsset(
                id=aid,
                name=name,
                ticker=ticker,
                asset_class=asset_class,
                region=region,
                weight=weight,
                expected_return=exp_ret,
                volatility=vol,
                sample_return_series=[float(x) for x in series[:, i]],
            )
        )
    return assets


def sample_stress_scenario() -> StressScenario:
    """An illustrative risk-off shock used as the default stress scenario."""
    return StressScenario(
        name="Risk-off shock (illustrative)",
        description=(
            "A hypothetical risk-off month: equities sell off, government bonds "
            "and gold rally. Illustrative only — not a forecast."
        ),
        shocks={
            "us_eq": -0.12,
            "tw_eq": -0.18,
            "jp_eq": -0.11,
            "em_eq": -0.16,
            "us_treas": 0.04,
            "ig_credit": -0.02,
            "gold": 0.06,
            "usd_cash": 0.00,
        },
    )


def build_sample_response():
    """Assemble the GET /portfolio-risk/sample payload."""
    from app.portfolio_risk.models import SamplePortfolioResponse

    return SamplePortfolioResponse(
        assets=sample_assets(),
        risk_free_rate=0.02,
        confidence_level=0.95,
        stress_scenario=sample_stress_scenario(),
        disclaimer=DISCLAIMER,
        notes=[
            "Eight illustrative assets with deterministic monthly return series "
            f"(fixed seed {SAMPLE_SEED}, {SAMPLE_MONTHS} months).",
            "Weights are an illustrative starting allocation; edit them in the lab.",
            "Long-only by default. Not live data and not investment advice.",
        ],
    )
