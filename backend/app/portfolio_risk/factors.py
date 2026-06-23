"""
Factor-exposure & scenario-stress model for the Portfolio Risk Lab (Phase 21.1).

A simple, **deterministic, educational** linear factor model layered on the
existing static-sample portfolio. Nine illustrative factors with hand-authored
betas per sample asset; factors are treated as **orthogonal (uncorrelated)** in
v1 — a deliberate simplification that keeps the factor covariance diagonal and
positive-definite. Specific (idiosyncratic) variance is the residual of each
asset's stated annual variance over its factor-explained variance, floored at 0.

Nothing here is estimated from live data, and nothing is investment advice.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from app.portfolio_risk.models import (
    FactorDefinition,
    FactorModelSummary,
    PortfolioFactorExposure,
    ScenarioAssetImpact,
    ScenarioDefinition,
    ScenarioFactorImpact,
    ScenarioResult,
    SpecificRiskContribution,
)

_MIN_VOL = 1e-12

# id, name, category, description, annual factor volatility (illustrative)
_FACTOR_SPECS: List[Tuple[str, str, str, str, float]] = [
    ("equity_market", "Equity Market", "Equity", "Broad equity market beta (systematic equity risk).", 0.130),
    ("size", "Size", "Equity Style", "Small-minus-big size tilt.", 0.050),
    ("value", "Value", "Equity Style", "Value-minus-growth tilt.", 0.050),
    ("momentum", "Momentum", "Equity Style", "Cross-sectional momentum tilt.", 0.070),
    ("rates", "Rates", "Macro", "Duration / interest-rate level exposure.", 0.045),
    ("credit", "Credit", "Macro", "Credit-spread / default-risk exposure.", 0.035),
    ("fx_dollar", "FX Dollar", "Macro", "US dollar strength exposure.", 0.060),
    ("commodity", "Commodity", "Macro", "Broad commodity exposure.", 0.150),
    ("volatility", "Volatility", "Risk Premium", "Sensitivity to volatility shocks.", 0.100),
]

FACTOR_IDS: List[str] = [s[0] for s in _FACTOR_SPECS]
_FACTOR_NAME: Dict[str, str] = {s[0]: s[1] for s in _FACTOR_SPECS}
_FACTOR_VOL: Dict[str, float] = {s[0]: s[4] for s in _FACTOR_SPECS}

# Deterministic illustrative betas (asset id -> {factor id -> beta}). Order of the
# inner tuples matches FACTOR_IDS. Hand-authored, NOT estimated from live data.
_BETAS: Dict[str, List[float]] = {
    # eqmkt  size   value  mom    rates  credit fx     comm   vol
    "us_eq": [1.00, 0.20, 0.10, 0.15, -0.20, 0.10, 0.00, 0.05, -0.30],
    "tw_eq": [1.15, 0.35, -0.05, 0.25, -0.15, 0.10, -0.20, 0.10, -0.40],
    "jp_eq": [0.85, 0.10, 0.20, 0.10, -0.10, 0.05, -0.25, 0.00, -0.25],
    "em_eq": [1.10, 0.40, 0.05, 0.10, -0.20, 0.20, -0.45, 0.20, -0.35],
    "us_treas": [-0.15, 0.00, 0.00, 0.00, 1.00, 0.05, 0.00, 0.00, 0.25],
    "ig_credit": [0.20, 0.00, 0.05, 0.00, 0.60, 1.00, 0.00, 0.00, 0.10],
    "gold": [0.10, 0.00, 0.00, 0.05, -0.35, 0.00, -0.45, 0.85, 0.20],
    "usd_cash": [0.00, 0.00, 0.00, 0.00, 0.05, 0.00, 0.10, 0.00, 0.00],
}

# id, name, description, factor_shocks, asset_shocks (illustrative scenarios)
_SCENARIO_SPECS = [
    (
        "equity_selloff",
        "Equity selloff",
        "A broad equity drawdown with a volatility spike and modest credit widening.",
        {"equity_market": -0.08, "volatility": 0.05, "credit": -0.02},
        None,
    ),
    (
        "rates_shock",
        "Rates shock",
        "A sharp rise in rates that pressures equities and credit.",
        {"rates": 0.03, "equity_market": -0.02, "credit": -0.01},
        None,
    ),
    (
        "usd_squeeze",
        "USD squeeze",
        "A strong-dollar move with weaker commodities and an extra EM-equity drag.",
        {"fx_dollar": 0.04, "commodity": -0.02},
        {"em_eq": -0.04},
    ),
    (
        "commodity_rally",
        "Commodity rally",
        "A commodity rally with a small rates rise and a softer dollar.",
        {"commodity": 0.06, "rates": 0.01, "fx_dollar": -0.01},
        None,
    ),
    (
        "credit_stress",
        "Credit stress",
        "Widening credit spreads with falling equities and rising volatility.",
        {"credit": -0.05, "equity_market": -0.04, "volatility": 0.04},
        None,
    ),
]


def factor_definitions() -> List[FactorDefinition]:
    return [
        FactorDefinition(
            id=fid, name=name, category=category, description=desc, volatility=vol
        )
        for fid, name, category, desc, vol in _FACTOR_SPECS
    ]


def scenario_library() -> List[ScenarioDefinition]:
    return [
        ScenarioDefinition(
            id=sid,
            name=name,
            description=desc,
            factor_shocks=dict(factor_shocks),
            asset_shocks=dict(asset_shocks) if asset_shocks else None,
        )
        for sid, name, desc, factor_shocks, asset_shocks in _SCENARIO_SPECS
    ]


def beta_matrix(asset_ids: List[str]) -> np.ndarray:
    """(assets × factors) beta matrix; unknown assets get all-zero betas."""
    k = len(FACTOR_IDS)
    rows = [
        _BETAS.get(aid, [0.0] * k) if len(_BETAS.get(aid, [])) == k else [0.0] * k
        for aid in asset_ids
    ]
    return np.array(rows, dtype=float)


def _factor_covariance() -> np.ndarray:
    """Diagonal factor covariance (orthogonal factors) — PSD by construction."""
    vols = np.array([_FACTOR_VOL[f] for f in FACTOR_IDS], dtype=float)
    return np.diag(vols ** 2)


def compute_factor_block(
    weights: np.ndarray, asset_ids: List[str], asset_vols: np.ndarray
) -> dict:
    """
    Factor-model risk decomposition.

    Returns the typed pieces the response needs: factor definitions, the beta
    matrix, factor covariance/correlation, the portfolio factor exposure (with
    risk contributions), the specific-risk contribution, and the model summary.

    Convention: percent risk contributions use the **variance-share** convention,
    so the factor percentages plus the specific-risk percentage sum to 1.
    """
    B = beta_matrix(asset_ids)  # (n, k)
    F = _factor_covariance()  # (k, k) diagonal
    factor_vols = np.array([_FACTOR_VOL[f] for f in FACTOR_IDS], dtype=float)

    port_beta = B.T @ weights  # (k,)
    fb = F @ port_beta  # (k,)
    factor_variance = float(port_beta @ fb)

    # Specific variance per asset = stated variance − factor-explained variance,
    # floored at 0; portfolio specific variance = wᵀ D w (D diagonal).
    factor_explained = np.einsum("ij,jk,ik->i", B, F, B)  # (n,) b_iᵀ F b_i
    specific_var_asset = np.maximum(asset_vols ** 2 - factor_explained, 0.0)
    specific_variance = float(np.sum((weights ** 2) * specific_var_asset))

    model_variance = max(factor_variance + specific_variance, 0.0)
    model_vol = float(np.sqrt(model_variance))
    safe_vol = model_vol if model_vol > _MIN_VOL else 1.0

    # Per-factor contributions (variance share).
    contrib_var = port_beta * fb  # (k,) sums to factor_variance
    exposures = [
        PortfolioFactorExposure(
            factor_id=FACTOR_IDS[j],
            name=_FACTOR_NAME[FACTOR_IDS[j]],
            exposure=float(port_beta[j]),
            contribution_to_variance=float(contrib_var[j]),
            contribution_to_volatility=float(contrib_var[j] / safe_vol),
            percent_risk_contribution=float(contrib_var[j] / model_variance)
            if model_variance > _MIN_VOL
            else 0.0,
        )
        for j in range(len(FACTOR_IDS))
    ]
    specific = SpecificRiskContribution(
        variance=specific_variance,
        contribution_to_volatility=float(specific_variance / safe_vol),
        percent_risk_contribution=float(specific_variance / model_variance)
        if model_variance > _MIN_VOL
        else 0.0,
    )
    summary = FactorModelSummary(
        factor_variance=factor_variance,
        specific_variance=specific_variance,
        model_variance=model_variance,
        model_volatility=model_vol,
    )
    corr = np.eye(len(FACTOR_IDS))  # orthogonal factors
    return {
        "factors": factor_definitions(),
        "factor_order": list(FACTOR_IDS),
        "factor_exposures": [[float(x) for x in row] for row in B],
        "factor_covariance_matrix": [[float(x) for x in row] for row in F],
        "factor_correlation_matrix": [[float(x) for x in row] for row in corr],
        "portfolio_factor_exposure": exposures,
        "specific_risk_contribution": specific,
        "factor_model": summary,
        "_factor_vols": factor_vols,  # (unused downstream; kept for clarity)
    }


def compute_scenarios(
    weights: np.ndarray,
    asset_ids: List[str],
    asset_names: Dict[str, str],
    scenarios: List[ScenarioDefinition],
) -> List[ScenarioResult]:
    """
    Deterministic scenario stress. For each scenario, asset impact is the sum of
    factor-shock × beta plus any asset-specific shock; the portfolio impact is the
    weighted sum of asset impacts. The per-factor impact (portfolio_beta × shock)
    decomposes the *factor* part of the same portfolio impact (asset-specific
    shocks are reported separately on the assets, so there is no double counting).
    """
    B = beta_matrix(asset_ids)  # (n, k)
    port_beta = B.T @ weights  # (k,)
    results: List[ScenarioResult] = []

    for sc in scenarios:
        shock_vec = np.array(
            [float(sc.factor_shocks.get(f, 0.0)) for f in FACTOR_IDS], dtype=float
        )
        asset_specific = np.array(
            [float((sc.asset_shocks or {}).get(aid, 0.0)) for aid in asset_ids],
            dtype=float,
        )
        asset_impact = B @ shock_vec + asset_specific  # (n,)
        contribution = weights * asset_impact
        portfolio_impact = float(np.sum(contribution))

        factor_impact = [
            ScenarioFactorImpact(
                factor_id=FACTOR_IDS[j],
                name=_FACTOR_NAME[FACTOR_IDS[j]],
                shock=float(shock_vec[j]),
                impact=float(port_beta[j] * shock_vec[j]),
            )
            for j in range(len(FACTOR_IDS))
            if shock_vec[j] != 0.0
        ]
        asset_rows = [
            ScenarioAssetImpact(
                asset_id=asset_ids[i],
                name=asset_names.get(asset_ids[i], asset_ids[i]),
                weight=float(weights[i]),
                impact=float(asset_impact[i]),
                contribution=float(contribution[i]),
            )
            for i in range(len(asset_ids))
        ]
        worst_i = int(np.argmin(asset_impact))
        best_i = int(np.argmax(asset_impact))
        notes = [
            "Illustrative deterministic scenario — not a forecast and not advice.",
            "Asset impact = Σ(beta × factor shock) + asset-specific shock; "
            "portfolio impact = Σ(weight × asset impact).",
        ]
        if sc.asset_shocks:
            notes.append(
                "This scenario includes asset-specific shocks in addition to "
                "factor shocks."
            )
        results.append(
            ScenarioResult(
                scenario_id=sc.id,
                name=sc.name,
                portfolio_return_impact=portfolio_impact,
                factor_impact=factor_impact,
                asset_impact=asset_rows,
                worst_asset=asset_ids[worst_i],
                best_asset=asset_ids[best_i],
                notes=notes,
            )
        )
    return results
