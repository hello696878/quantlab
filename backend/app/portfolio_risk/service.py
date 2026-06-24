"""
Portfolio Risk Lab analytics (Phase 21.0) — pure, deterministic computation.

Given a typed request, compute portfolio return / volatility / Sharpe, the
covariance & correlation matrices, marginal / component / percent risk
contributions, historical VaR & CVaR, an optional stress P&L, a deterministic
long-only efficient frontier, the minimum-variance portfolio (lowest vol among
the frontier candidates), and a basic risk-parity portfolio.

All outputs are finite by construction (variances are clamped before sqrt and
every division is guarded), so no NaN/Infinity reaches the API layer. Educational
only — not investment advice.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
from scipy.optimize import minimize

from app.portfolio_risk.models import (
    AssetRiskContribution,
    FrontierPoint,
    NamedPortfolio,
    PortfolioAnalysisRequest,
    PortfolioAnalysisResponse,
    PortfolioAsset,
    StressResult,
)
from app.portfolio_risk.factors import (
    compute_factor_block,
    compute_scenarios,
    scenario_library,
)
from app.portfolio_risk.models import PortfolioSimulationConfig
from app.portfolio_risk.optimize import (
    build_black_litterman,
    build_optimization,
    build_rebalance,
    sample_bl_views,
)
from app.portfolio_risk.sample import DISCLAIMER
from app.portfolio_risk.simulate import (
    build_optimization_robustness,
    build_sensitivity,
    build_simulations,
)

_MIN_VOL = 1e-12
# Deterministic candidate cloud for the efficient frontier.
_FRONTIER_SEED = 7
_FRONTIER_SAMPLES = 4000
_FRONTIER_POINTS = 40


def _normalized_weights(assets: List[PortfolioAsset]) -> np.ndarray:
    """Normalise weights to sum to 1 (request validator guarantees sum > 0)."""
    raw = np.array([a.weight for a in assets], dtype=float)
    return raw / raw.sum()


def _covariance(vols: np.ndarray, series: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Sample correlation from the series; covariance tied to stated annual vols."""
    n = len(vols)
    if series.shape[1] >= 2:
        # np.corrcoef collapses a single-asset series to a 0-d scalar; force an
        # (n, n) matrix so fill_diagonal / outer stay well-shaped for n == 1.
        corr = np.asarray(np.corrcoef(series), dtype=float).reshape(n, n)
    else:  # pragma: no cover - request validator enforces >= 12 observations
        corr = np.eye(n)
    corr = np.clip(np.nan_to_num(corr, nan=0.0), -1.0, 1.0)
    np.fill_diagonal(corr, 1.0)
    corr = (corr + corr.T) / 2.0
    cov = np.outer(vols, vols) * corr  # annual covariance
    cov = (cov + cov.T) / 2.0
    return cov, corr


def _vol(weights: np.ndarray, cov: np.ndarray) -> float:
    return float(np.sqrt(max(float(weights @ cov @ weights), 0.0)))


def _sharpe(ret: float, vol: float, rf: float) -> float:
    return float((ret - rf) / vol) if vol > _MIN_VOL else 0.0


def _point(
    weights: np.ndarray, mu: np.ndarray, cov: np.ndarray, ids: List[str], rf: float
) -> FrontierPoint:
    ret = float(weights @ mu)
    vol = _vol(weights, cov)
    return FrontierPoint(
        expected_return=ret,
        volatility=vol,
        sharpe=_sharpe(ret, vol, rf),
        weights={ids[i]: float(weights[i]) for i in range(len(ids))},
    )


def _efficient_frontier(
    mu: np.ndarray, cov: np.ndarray, ids: List[str], rf: float
) -> List[FrontierPoint]:
    """Deterministic long-only frontier: upper envelope of a seeded weight cloud."""
    n = len(ids)
    rng = np.random.default_rng(_FRONTIER_SEED)
    cloud = rng.dirichlet(np.ones(n), size=_FRONTIER_SAMPLES)  # long-only, sum=1
    rets = cloud @ mu
    variances = np.einsum("ij,jk,ik->i", cloud, cov, cloud)
    vols = np.sqrt(np.clip(variances, 0.0, None))

    edges = np.linspace(vols.min(), vols.max(), _FRONTIER_POINTS + 1)
    chosen: Dict[int, None] = {}
    for b in range(_FRONTIER_POINTS):
        lo, hi = edges[b], edges[b + 1]
        mask = (vols >= lo) & (vols <= hi)
        if not mask.any():
            continue
        idxs = np.where(mask)[0]
        chosen[int(idxs[np.argmax(rets[idxs])])] = None  # max-return per vol bin
    chosen[int(np.argmin(vols))] = None  # always include the global-min-variance pt

    points = [_point(cloud[i], mu, cov, ids, rf) for i in chosen]
    points.sort(key=lambda p: (p.volatility, -p.expected_return))
    return points


def _risk_parity(
    mu: np.ndarray, cov: np.ndarray, ids: List[str], rf: float
) -> NamedPortfolio:
    """
    Basic long-only risk parity (equal risk budget). Solves the convex
    log-barrier formulation (Maillard et al.):

        min_{w>0}  ½ wᵀΣw − (1/n) Σ ln(w_i)

    whose stationarity condition ``Σw = (1/n)/w`` gives every component risk
    contribution ``w_i·(Σw)_i`` equal; the result is then normalised to sum to 1.
    The objective is convex (Σ is positive-definite), so this converges reliably
    even with diversifying (negatively-correlated) assets.
    """
    n = len(ids)
    budget = 1.0 / n

    def objective(weights: np.ndarray) -> float:
        return 0.5 * float(weights @ cov @ weights) - budget * float(
            np.sum(np.log(weights))
        )

    def gradient(weights: np.ndarray) -> np.ndarray:
        return cov @ weights - budget / weights

    result = minimize(
        objective,
        np.full(n, 1.0 / n),
        jac=gradient,
        method="L-BFGS-B",
        bounds=[(1e-8, None)] * n,
        options={"maxiter": 2000, "ftol": 1e-15},
    )
    w = np.maximum(result.x, 0.0)
    total = float(w.sum())
    w = w / total if total > _MIN_VOL else np.full(n, 1.0 / n)
    pt = _point(w, mu, cov, ids, rf)
    return NamedPortfolio(
        label="Risk parity (equal risk contribution)",
        weights=pt.weights,
        expected_return=pt.expected_return,
        volatility=pt.volatility,
        sharpe=pt.sharpe,
    )


def analyze_portfolio(req: PortfolioAnalysisRequest) -> PortfolioAnalysisResponse:
    assets = req.assets
    ids = [a.id for a in assets]
    names = {a.id: a.name for a in assets}
    n = len(assets)

    w = _normalized_weights(assets)
    mu = np.array([a.expected_return for a in assets], dtype=float)
    vols = np.array([a.volatility for a in assets], dtype=float)
    series = np.array([a.sample_return_series for a in assets], dtype=float)  # (n, T)

    cov, corr = _covariance(vols, series)

    port_ret = float(w @ mu)
    port_vol = _vol(w, cov)
    rf = float(req.risk_free_rate)
    sharpe = _sharpe(port_ret, port_vol, rf)

    # Marginal / component / percent risk contributions.
    marginal = (cov @ w) / port_vol if port_vol > _MIN_VOL else np.zeros(n)
    component = w * marginal
    pct = component / port_vol if port_vol > _MIN_VOL else np.zeros(n)
    contributions = [
        AssetRiskContribution(
            id=ids[i],
            name=names[ids[i]],
            weight=float(w[i]),
            marginal_contribution=float(marginal[i]),
            component_contribution=float(component[i]),
            percent_contribution=float(pct[i]),
        )
        for i in range(n)
    ]

    # Historical VaR / CVaR from the portfolio's monthly sample return series.
    r_p = w @ series  # (T,)
    alpha = 1.0 - float(req.confidence_level)
    quantile = float(np.quantile(r_p, alpha))
    var = float(-quantile)
    tail = r_p[r_p <= quantile]
    cvar = float(-tail.mean()) if tail.size > 0 else var

    # Optional stress P&L.
    stress_result = None
    if req.stress_scenario:
        shocks = req.stress_scenario.shocks
        asset_pnl = {
            ids[i]: float(w[i] * shocks.get(ids[i], 0.0)) for i in range(n)
        }
        stress_result = StressResult(
            name=req.stress_scenario.name,
            asset_pnl=asset_pnl,
            portfolio_pnl=float(sum(asset_pnl.values())),
        )

    frontier = _efficient_frontier(mu, cov, ids, rf)
    min_var_point = min(frontier, key=lambda p: p.volatility)
    min_variance = NamedPortfolio(
        label="Minimum variance",
        weights=min_var_point.weights,
        expected_return=min_var_point.expected_return,
        volatility=min_var_point.volatility,
        sharpe=min_var_point.sharpe,
    )
    risk_parity = _risk_parity(mu, cov, ids, rf)

    # Factor exposure / risk decomposition + deterministic scenario stress.
    factor_block = compute_factor_block(w, ids, vols)
    scenarios = scenario_library() + list(req.custom_scenarios)
    scenario_results = compute_scenarios(w, ids, names, scenarios)

    # Constrained optimization, Black-Litterman, and hypothetical rebalance.
    rp_w = np.array([risk_parity.weights[i] for i in ids], dtype=float)
    optimization_results, _pool = build_optimization(
        mu, cov, ids, w, rp_w, rf, req.optimization_constraints
    )
    bl_views = req.black_litterman_views if req.black_litterman_views is not None else sample_bl_views()
    black_litterman = build_black_litterman(
        mu, cov, ids, names, w, rp_w, rf,
        float(req.risk_aversion), float(req.tau), bl_views, req.optimization_constraints,
    )
    prev_weights = (
        req.optimization_constraints.previous_weights
        if req.optimization_constraints
        else None
    )
    rebalance_analysis = build_rebalance(
        optimization_results.max_sharpe_portfolio, ids, names, w, prev_weights
    )

    # Monte Carlo simulation, bootstrap robustness, and assumption sensitivity.
    sim_config = req.simulation_config or PortfolioSimulationConfig()
    monte_carlo, bootstrap_robustness = build_simulations(w, mu, cov, series, sim_config)
    confidence = float(req.confidence_level)
    assumption_sensitivity = build_sensitivity(w, mu, cov, vols, corr, rf, series, confidence)

    def _weights(p) -> np.ndarray:
        return np.array([p.weights[i] for i in ids], dtype=float)

    robustness_portfolios = [
        ("current", "Current", w),
        ("max_sharpe", "Max Sharpe", _weights(optimization_results.max_sharpe_portfolio)),
        ("min_variance", "Minimum variance", _weights(optimization_results.min_variance_portfolio)),
        ("risk_parity", "Risk parity", _weights(optimization_results.risk_parity_portfolio)),
        ("black_litterman", "Black-Litterman", _weights(black_litterman.bl_optimized_portfolio)),
    ]
    optimization_robustness = build_optimization_robustness(
        robustness_portfolios, mu, cov, vols, corr, rf, series, confidence
    )

    return PortfolioAnalysisResponse(
        asset_order=ids,
        asset_names=names,
        normalized_weights={ids[i]: float(w[i]) for i in range(n)},
        expected_return=port_ret,
        volatility=port_vol,
        sharpe_ratio=sharpe,
        covariance_matrix=[[float(x) for x in row] for row in cov],
        correlation_matrix=[[float(x) for x in row] for row in corr],
        asset_risk_contributions=contributions,
        historical_var=var,
        historical_cvar=cvar,
        var_horizon="monthly",
        confidence_level=float(req.confidence_level),
        risk_free_rate=rf,
        stress_result=stress_result,
        efficient_frontier=frontier,
        min_variance_portfolio=min_variance,
        risk_parity_portfolio=risk_parity,
        factors=factor_block["factors"],
        factor_order=factor_block["factor_order"],
        factor_exposures=factor_block["factor_exposures"],
        factor_covariance_matrix=factor_block["factor_covariance_matrix"],
        factor_correlation_matrix=factor_block["factor_correlation_matrix"],
        portfolio_factor_exposure=factor_block["portfolio_factor_exposure"],
        specific_risk_contribution=factor_block["specific_risk_contribution"],
        factor_model=factor_block["factor_model"],
        scenario_library=scenarios,
        scenario_results=scenario_results,
        optimization_results=optimization_results,
        black_litterman=black_litterman,
        rebalance_analysis=rebalance_analysis,
        monte_carlo=monte_carlo,
        bootstrap_robustness=bootstrap_robustness,
        assumption_sensitivity=assumption_sensitivity,
        optimization_robustness=optimization_robustness,
        notes=[
            "Weights are normalised to sum to 1 before analysis.",
            "Covariance is annualised: it ties each asset's stated annual "
            "volatility to the sample correlation of the illustrative return series.",
            "Historical VaR and CVaR are computed at a monthly horizon from the "
            "sample monthly return series (loss-positive convention).",
            "The efficient frontier, minimum-variance, and risk-parity portfolios "
            "are long-only and derived from a deterministic candidate set.",
            "Factor betas are deterministic illustrative values (not estimated "
            "from live data); factors are treated as orthogonal in v1.",
            "Factor and specific percent risk contributions use the variance-share "
            "convention and sum to 1.",
            "Scenario shocks are illustrative educational examples — not a forecast.",
            "Optimisation uses a deterministic long-only candidate search under box "
            "constraints — an educational construction exercise, not a production "
            "optimiser and not advice.",
            "Black-Litterman views are illustrative only and are not forecasts; "
            "rebalance deltas are hypothetical, not trade orders.",
            "Monte Carlo and bootstrap paths use a fixed seed on illustrative sample "
            "data — simulated outcomes are educational, not forecasts.",
            "Assumption-sensitivity and optimization-robustness scenarios are "
            "deterministic illustrative shifts, not predictions.",
        ],
        disclaimer=DISCLAIMER,
    )
