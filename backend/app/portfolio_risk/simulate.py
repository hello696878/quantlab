"""
Monte Carlo, bootstrap, and robustness for the Portfolio Risk Lab (Phase 21.3).

Deterministic, **fixed-seed** simulation and assumption-sensitivity analysis on
the existing static-sample portfolio. Two simulation methods (parametric Gaussian
and historical bootstrap), terminal-wealth and drawdown distributions, loss and
drawdown-breach probabilities, simulated VaR/CVaR, plus deterministic
assumption-sensitivity and optimization-robustness comparisons.

Simulated outcomes are an **educational illustration, not a forecast**, computed
from illustrative sample data only — no live data and no investment advice.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from app.portfolio_risk.models import (
    MonteCarloFanPoint,
    MonteCarloPathPoint,
    MonteCarloSamplePath,
    MonteCarloSummary,
    OptimizationRobustnessResult,
    PortfolioSimulationConfig,
    SensitivityResult,
)

_MIN_VOL = 1e-12
_TRADING_DAYS = 252
_DAYS_PER_MONTH = 21
_MAX_SAMPLE_PATHS = 20
_MAX_FAN_POINTS = 41


# --------------------------------------------------------------------------- #
# Drawdown utility
# --------------------------------------------------------------------------- #
def max_drawdowns(wealth: np.ndarray) -> np.ndarray:
    """Per-path max drawdown (<= 0): min over t of wealth_t/peak_t − 1."""
    running_peak = np.maximum.accumulate(wealth, axis=1)
    running_peak = np.where(running_peak > _MIN_VOL, running_peak, _MIN_VOL)
    dd = wealth / running_peak - 1.0
    return np.minimum(dd.min(axis=1), 0.0)


def _p(arr: np.ndarray, q: float) -> float:
    return float(np.percentile(arr, q))


# --------------------------------------------------------------------------- #
# Monte Carlo simulation
# --------------------------------------------------------------------------- #
def simulate(
    method: str,
    mu_p_daily: float,
    sigma_p_daily: float,
    daily_pool: np.ndarray,
    config: PortfolioSimulationConfig,
) -> MonteCarloSummary:
    """Run a deterministic fixed-seed wealth-path simulation and summarise it."""
    rng = np.random.default_rng(int(config.seed))
    horizon = int(config.horizon_days)
    paths = int(config.num_paths)
    v0 = float(config.initial_value)

    notes: List[str] = [
        "Deterministic fixed-seed simulation on illustrative sample data — not a forecast.",
    ]
    if method == "historical_bootstrap":
        if daily_pool.size == 0:
            daily_pool = np.array([0.0])
        idx = rng.integers(0, len(daily_pool), size=(paths, horizon))
        rets = daily_pool[idx]
        notes.append(
            "Historical bootstrap resamples daily-equivalent returns derived from "
            f"the {len(daily_pool)}-point monthly sample series (short sample → wide "
            "uncertainty)."
        )
    else:
        method = "parametric_gaussian"
        rets = rng.normal(mu_p_daily, sigma_p_daily, size=(paths, horizon))
        notes.append("Parametric Gaussian draws daily portfolio returns from N(μ_p, σ_p).")

    growth = np.cumprod(1.0 + rets, axis=1)
    wealth = np.concatenate([np.ones((paths, 1)), growth], axis=1) * v0  # (P, H+1)
    terminal = wealth[:, -1]
    total_return = terminal / v0 - 1.0
    dd = max_drawdowns(wealth)

    quantile = float(np.quantile(total_return, 0.05))
    var95 = float(-quantile)
    tail = total_return[total_return <= quantile]
    cvar95 = float(-tail.mean()) if tail.size > 0 else var95

    day_idx = np.unique(np.linspace(0, horizon, min(horizon + 1, _MAX_FAN_POINTS)).astype(int))
    fan = [
        MonteCarloFanPoint(
            day=int(d),
            p05=_p(wealth[:, d], 5),
            p25=_p(wealth[:, d], 25),
            median=_p(wealth[:, d], 50),
            p75=_p(wealth[:, d], 75),
            p95=_p(wealth[:, d], 95),
        )
        for d in day_idx
    ]
    sample_paths = [
        MonteCarloSamplePath(
            path_id=int(i),
            points=[MonteCarloPathPoint(day=int(d), value=float(wealth[i, d])) for d in day_idx],
        )
        for i in range(min(_MAX_SAMPLE_PATHS, paths))
    ]

    return MonteCarloSummary(
        method=method,
        seed=int(config.seed),
        horizon_days=horizon,
        num_paths=paths,
        initial_value=v0,
        terminal_wealth_mean=float(terminal.mean()),
        terminal_wealth_median=float(np.median(terminal)),
        terminal_wealth_p05=_p(terminal, 5),
        terminal_wealth_p95=_p(terminal, 95),
        probability_of_loss=float(np.mean(terminal < v0)),
        probability_drawdown_breach=float(np.mean(dd <= float(config.drawdown_threshold))),
        drawdown_threshold=float(config.drawdown_threshold),
        max_drawdown_mean=float(dd.mean()),
        max_drawdown_p05=_p(dd, 5),
        max_drawdown_p95=_p(dd, 95),
        simulated_var_95=var95,
        simulated_cvar_95=cvar95,
        fan_chart_points=fan,
        sample_paths=sample_paths,
        notes=notes,
    )


def build_simulations(
    w: np.ndarray,
    mu: np.ndarray,
    cov: np.ndarray,
    series: np.ndarray,
    config: PortfolioSimulationConfig,
) -> Tuple[MonteCarloSummary, MonteCarloSummary]:
    """Build the parametric Monte Carlo + the historical-bootstrap summaries."""
    port_ret = float(w @ mu)
    port_var = max(float(w @ cov @ w), 0.0)
    port_vol = float(np.sqrt(port_var))
    mu_p_daily = port_ret / _TRADING_DAYS
    sigma_p_daily = port_vol / np.sqrt(_TRADING_DAYS)

    port_monthly = w @ series  # (T,)
    # Daily-equivalent returns derived from monthly (geometric split).
    daily_pool = np.power(1.0 + port_monthly, 1.0 / _DAYS_PER_MONTH) - 1.0
    daily_pool = daily_pool[np.isfinite(daily_pool)]

    mc = simulate(config.method, mu_p_daily, sigma_p_daily, daily_pool, config)
    boot_cfg = config.model_copy(update={"method": "historical_bootstrap"})
    boot = simulate("historical_bootstrap", mu_p_daily, sigma_p_daily, daily_pool, boot_cfg)
    return mc, boot


# --------------------------------------------------------------------------- #
# Assumption sensitivity & optimization robustness
# --------------------------------------------------------------------------- #
def _apply_corr_shift(corr: np.ndarray, delta: float) -> np.ndarray:
    out = corr + delta
    out = np.clip(out, -0.99, 0.99)
    np.fill_diagonal(out, 1.0)
    return (out + out.T) / 2.0


def assumption_scenarios(
    mu: np.ndarray, cov: np.ndarray, vols: np.ndarray, corr: np.ndarray, rf: float
) -> List[dict]:
    """Eight deterministic, illustrative assumption shifts."""
    def cov_from(corr_m: np.ndarray, vol_v: np.ndarray) -> np.ndarray:
        c = np.outer(vol_v, vol_v) * corr_m
        return (c + c.T) / 2.0

    return [
        {"id": "ret_down_25", "name": "Expected returns −25%", "desc": "All asset expected returns scaled to 75%.", "mu": mu * 0.75, "cov": cov, "rf": rf},
        {"id": "ret_up_25", "name": "Expected returns +25%", "desc": "All asset expected returns scaled to 125%.", "mu": mu * 1.25, "cov": cov, "rf": rf},
        {"id": "vol_up_25", "name": "Volatility +25%", "desc": "All asset volatilities scaled to 125%.", "mu": mu, "cov": cov * (1.25 ** 2), "rf": rf},
        {"id": "vol_down_15", "name": "Volatility −15%", "desc": "All asset volatilities scaled to 85%.", "mu": mu, "cov": cov * (0.85 ** 2), "rf": rf},
        {"id": "corr_up_20", "name": "Correlation +0.20 (stress)", "desc": "Off-diagonal correlations raised by 0.20 (diversification breaks down).", "mu": mu, "cov": cov_from(_apply_corr_shift(corr, 0.20), vols), "rf": rf},
        {"id": "corr_down_20", "name": "Correlation −0.20 (diversification)", "desc": "Off-diagonal correlations lowered by 0.20.", "mu": mu, "cov": cov_from(_apply_corr_shift(corr, -0.20), vols), "rf": rf},
        {"id": "rf_up_1", "name": "Risk-free +1%", "desc": "Risk-free rate raised by 1%.", "mu": mu, "cov": cov, "rf": rf + 0.01},
        {"id": "rf_down_1", "name": "Risk-free −1%", "desc": "Risk-free rate lowered by 1%.", "mu": mu, "cov": cov, "rf": rf - 0.01},
    ]


def _eval(
    w: np.ndarray,
    mu: np.ndarray,
    cov: np.ndarray,
    rf: float,
    base_series: np.ndarray,
    base_ret: float,
    base_vol: float,
    confidence: float,
) -> Tuple[float, float, float, float, float]:
    """Return (ret, vol, sharpe, var, cvar) for weights under given assumptions."""
    ret = float(w @ mu)
    vol = float(np.sqrt(max(float(w @ cov @ w), 0.0)))
    sharpe = float((ret - rf) / vol) if vol > _MIN_VOL else 0.0
    # VaR/CVaR from the base portfolio series transformed to the scenario's
    # mean and spread (vol-scaled, mean-shifted), monthly convention.
    r_p = w @ base_series
    vol_scale = (vol / base_vol) if base_vol > _MIN_VOL else 1.0
    mean_shift = (ret - base_ret) / 12.0
    scenario = (r_p - r_p.mean()) * vol_scale + r_p.mean() + mean_shift
    alpha = 1.0 - confidence
    q = float(np.quantile(scenario, alpha))
    var = float(-q)
    tail = scenario[scenario <= q]
    cvar = float(-tail.mean()) if tail.size > 0 else var
    return ret, vol, sharpe, var, cvar


def build_sensitivity(
    w: np.ndarray,
    mu: np.ndarray,
    cov: np.ndarray,
    vols: np.ndarray,
    corr: np.ndarray,
    rf: float,
    series: np.ndarray,
    confidence: float,
) -> List[SensitivityResult]:
    """Recompute the current portfolio's risk metrics under each assumption shift."""
    base_ret = float(w @ mu)
    base_vol = float(np.sqrt(max(float(w @ cov @ w), 0.0)))
    out: List[SensitivityResult] = []
    for sc in assumption_scenarios(mu, cov, vols, corr, rf):
        ret, vol, sharpe, var, cvar = _eval(
            w, sc["mu"], sc["cov"], sc["rf"], series, base_ret, base_vol, confidence
        )
        out.append(
            SensitivityResult(
                id=sc["id"],
                name=sc["name"],
                description=sc["desc"],
                expected_return=ret,
                volatility=vol,
                sharpe_ratio=sharpe,
                historical_var=var,
                historical_cvar=cvar,
                notes=["Illustrative assumption shift — not a forecast."],
            )
        )
    return out


def build_optimization_robustness(
    portfolios: List[Tuple[str, str, np.ndarray]],
    mu: np.ndarray,
    cov: np.ndarray,
    vols: np.ndarray,
    corr: np.ndarray,
    rf: float,
    series: np.ndarray,
    confidence: float,
) -> List[OptimizationRobustnessResult]:
    """Compare Sharpe stability of named portfolios across the assumption shifts."""
    base_rets = [float(w @ mu) for _, _, w in portfolios]
    base_vols = [float(np.sqrt(max(float(w @ cov @ w), 0.0))) for _, _, w in portfolios]
    scenarios = [{"mu": mu, "cov": cov, "rf": rf}] + assumption_scenarios(mu, cov, vols, corr, rf)

    # sharpe[p][s]
    sharpe = np.zeros((len(portfolios), len(scenarios)))
    for s, sc in enumerate(scenarios):
        for p, (_, _, w) in enumerate(portfolios):
            _, _, sh, _, _ = _eval(
                w, sc["mu"], sc["cov"], sc["rf"], series, base_rets[p], base_vols[p], confidence
            )
            sharpe[p, s] = sh
    # ranks per scenario (1 = best)
    ranks = np.zeros_like(sharpe, dtype=int)
    for s in range(len(scenarios)):
        order = np.argsort(-sharpe[:, s])  # best first
        for rank, p in enumerate(order, start=1):
            ranks[p, s] = rank

    results: List[OptimizationRobustnessResult] = []
    for p, (pid, name, _) in enumerate(portfolios):
        base_rank = ranks[p, 0]
        stability = float(np.mean(ranks[p, 1:] == base_rank)) if len(scenarios) > 1 else 1.0
        results.append(
            OptimizationRobustnessResult(
                portfolio_id=pid,
                name=name,
                base_sharpe=float(sharpe[p, 0]),
                worst_case_sharpe=float(sharpe[p].min()),
                sharpe_range=float(sharpe[p].max() - sharpe[p].min()),
                rank_stability=stability,
                notes=["Sample robustness across illustrative assumption shifts — not advice."],
            )
        )
    return results
