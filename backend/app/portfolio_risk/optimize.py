"""
Portfolio optimization + Black-Litterman for the Portfolio Risk Lab (Phase 21.2).

Deterministic, long-only, constrained portfolio construction via a **candidate
search** (no heavy optimiser dependency, no unstable randomness), plus a
simplified **educational Black-Litterman** posterior and a **hypothetical**
rebalance / turnover analysis.

Everything is computed from the existing static-sample covariance and stated
expected returns. Nothing is estimated from live data, nothing is a forecast,
and nothing here is investment advice or a trade order.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np

from app.portfolio_risk.models import (
    AssetReturnView,
    BlackLittermanResult,
    BlackLittermanView,
    EffectiveConstraints,
    OptimizationConstraints,
    OptimizationResults,
    OptimizedPortfolio,
    RebalanceAnalysis,
    RebalanceAssetDelta,
)

_MIN_VOL = 1e-12
_CLOUD_SEED = 11
_CLOUD_SAMPLES = 1500
_TOL = 1e-6


# --------------------------------------------------------------------------- #
# Projection & evaluation
# --------------------------------------------------------------------------- #
def project_capped_simplex(v: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """
    Euclidean projection of ``v`` onto {w : sum(w)=1, lo<=w<=hi} via bisection on
    the offset τ so that ``sum(clip(v-τ, lo, hi)) == 1``. Deterministic and
    robust; falls back to clip+renormalise if the box itself is infeasible.
    """
    n = len(v)
    if n * lo > 1.0 + 1e-9 or n * hi < 1.0 - 1e-9:
        w = np.clip(v, lo, hi)
        s = w.sum()
        return w / s if s > _MIN_VOL else np.full(n, 1.0 / n)
    lo_t, hi_t = float(v.min() - hi), float(v.max() - lo)
    tau = 0.0
    for _ in range(80):
        tau = 0.5 * (lo_t + hi_t)
        s = float(np.clip(v - tau, lo, hi).sum())
        if abs(s - 1.0) < 1e-12:
            break
        if s > 1.0:
            lo_t = tau
        else:
            hi_t = tau
    return np.clip(v - tau, lo, hi)


def _vol(w: np.ndarray, cov: np.ndarray) -> float:
    return float(np.sqrt(max(float(w @ cov @ w), 0.0)))


def _turnover(w: np.ndarray, base: np.ndarray) -> float:
    return float(0.5 * np.sum(np.abs(w - base)))


def _is_feasible(w: np.ndarray, lo: float, hi: float) -> bool:
    return bool(
        np.all(w >= lo - 1e-6)
        and np.all(w <= hi + 1e-6)
        and abs(float(w.sum()) - 1.0) < 1e-6
    )


def _portfolio(
    pid: str,
    name: str,
    objective: str,
    w: np.ndarray,
    mu: np.ndarray,
    cov: np.ndarray,
    ids: List[str],
    rf: float,
    current_w: np.ndarray,
    lo: float,
    hi: float,
    notes: Optional[List[str]] = None,
) -> OptimizedPortfolio:
    ret = float(w @ mu)
    vol = _vol(w, cov)
    sharpe = float((ret - rf) / vol) if vol > _MIN_VOL else 0.0
    return OptimizedPortfolio(
        id=pid,
        name=name,
        objective=objective,
        weights={ids[i]: float(w[i]) for i in range(len(ids))},
        expected_return=ret,
        volatility=vol,
        sharpe_ratio=sharpe,
        turnover=_turnover(w, current_w),
        notes=notes or [],
        feasible=_is_feasible(w, lo, hi),
    )


# --------------------------------------------------------------------------- #
# Candidate pool
# --------------------------------------------------------------------------- #
def _candidate_pool(
    mu: np.ndarray,
    cov: np.ndarray,
    current_w: np.ndarray,
    rp_w: np.ndarray,
    lo: float,
    hi: float,
) -> np.ndarray:
    """Deterministic, feasible (box-projected) long-only candidate weights."""
    n = len(current_w)
    eq = np.full(n, 1.0 / n)
    inv_vol = 1.0 / np.sqrt(np.maximum(np.diag(cov), _MIN_VOL))
    inv_vol = inv_vol / inv_vol.sum()
    seeds = [current_w, eq, rp_w, inv_vol]

    # Single-asset-capped tilts.
    for i in range(n):
        w = np.full(n, (1.0 - hi) / max(n - 1, 1))
        w[i] = hi
        seeds.append(w)

    # Blends between the structural seeds.
    base = list(seeds)
    for a in range(len(base)):
        for b in range(a + 1, len(base)):
            for t in (0.25, 0.5, 0.75):
                seeds.append(t * base[a] + (1.0 - t) * base[b])

    # Deterministic Dirichlet cloud.
    rng = np.random.default_rng(_CLOUD_SEED)
    seeds.extend(rng.dirichlet(np.ones(n), size=_CLOUD_SAMPLES))

    projected = np.array([project_capped_simplex(np.asarray(s, float), lo, hi) for s in seeds])
    # De-duplicate (rounded) to keep the count meaningful.
    _, idx = np.unique(np.round(projected, 6), axis=0, return_index=True)
    return projected[np.sort(idx)]


def _best_sharpe(pool: np.ndarray, mu: np.ndarray, cov: np.ndarray, rf: float) -> int:
    rets = pool @ mu
    vols = np.sqrt(np.clip(np.einsum("ij,jk,ik->i", pool, cov, pool), 0.0, None))
    sharpe = np.where(vols > _MIN_VOL, (rets - rf) / np.maximum(vols, _MIN_VOL), -np.inf)
    return int(np.argmax(sharpe))


def build_optimization(
    mu: np.ndarray,
    cov: np.ndarray,
    ids: List[str],
    current_w: np.ndarray,
    rp_w: np.ndarray,
    rf: float,
    constraints: Optional[OptimizationConstraints],
) -> Tuple[OptimizationResults, np.ndarray]:
    """Build the constrained optimization results; also return the candidate pool."""
    c = constraints or OptimizationConstraints()
    lo, hi = float(c.min_weight), float(c.max_weight)
    prev = current_w
    if c.previous_weights:
        raw = np.array([float(c.previous_weights.get(i, 0.0)) for i in ids])
        if raw.sum() > _MIN_VOL:
            prev = raw / raw.sum()

    pool = _candidate_pool(mu, cov, current_w, rp_w, lo, hi)
    rets = pool @ mu
    vols = np.sqrt(np.clip(np.einsum("ij,jk,ik->i", pool, cov, pool), 0.0, None))

    notes = [
        f"Long-only candidate search over {len(pool)} deterministic feasible "
        f"portfolios (weights in [{lo:.2f}, {hi:.2f}], summing to 1).",
        "Turnover is measured against the current portfolio.",
        "Optimised portfolios are an educational construction exercise, not advice.",
    ]

    def mk(pid, name, obj, w, extra=None):
        return _portfolio(pid, name, obj, w, mu, cov, ids, rf, current_w, lo, hi, extra)

    max_sharpe = mk("max_sharpe", "Max Sharpe", "Maximise Sharpe ratio", pool[_best_sharpe(pool, mu, cov, rf)])
    min_var = mk("min_variance", "Minimum variance", "Minimise volatility", pool[int(np.argmin(vols))])

    # Target return: lowest-vol feasible candidate meeting the target return.
    target_return_pf = None
    if c.target_return is not None:
        ok = np.where(rets >= float(c.target_return) - _TOL)[0]
        if ok.size > 0:
            best = ok[int(np.argmin(vols[ok]))]
            target_return_pf = mk(
                "target_return",
                f"Target return ≥ {c.target_return:.1%}",
                "Minimise volatility subject to a return target",
                pool[best],
            )
        else:
            notes.append(
                f"Target return {c.target_return:.1%} is not achievable under the "
                f"constraints (max feasible ≈ {float(rets.max()):.1%}); showing no "
                "target-return portfolio."
            )

    # Target volatility: highest-return feasible candidate within the vol budget.
    target_vol_pf = None
    if c.target_volatility is not None:
        ok = np.where(vols <= float(c.target_volatility) * (1.0 + _TOL))[0]
        if ok.size > 0:
            best = ok[int(np.argmax(rets[ok]))]
            target_vol_pf = mk(
                "target_volatility",
                f"Target volatility ≤ {c.target_volatility:.1%}",
                "Maximise return subject to a volatility budget",
                pool[best],
            )
        else:
            notes.append(
                f"Target volatility {c.target_volatility:.1%} is below the minimum "
                f"achievable (≈ {float(vols.min()):.1%}); showing no target-volatility "
                "portfolio."
            )

    results = OptimizationResults(
        current_portfolio=mk("current", "Current", "As-entered weights", current_w),
        equal_weight_portfolio=mk("equal_weight", "Equal weight", "1/N allocation", project_capped_simplex(np.full(len(ids), 1.0 / len(ids)), lo, hi)),
        max_sharpe_portfolio=max_sharpe,
        min_variance_portfolio=min_var,
        risk_parity_portfolio=mk(
            "risk_parity",
            "Risk parity",
            "Equal risk contribution (preserved)",
            rp_w,
            ["Reuses the risk-parity weights from the risk analysis; may exceed the box cap."]
            if not _is_feasible(rp_w, lo, hi)
            else None,
        ),
        target_return_portfolio=target_return_pf,
        target_volatility_portfolio=target_vol_pf,
        candidate_count=int(len(pool)),
        constraints=EffectiveConstraints(
            min_weight=lo,
            max_weight=hi,
            target_return=c.target_return,
            target_volatility=c.target_volatility,
            turnover_penalty=c.turnover_penalty,
        ),
        notes=notes,
    )
    return results, pool


# --------------------------------------------------------------------------- #
# Black-Litterman
# --------------------------------------------------------------------------- #
def sample_bl_views() -> List[BlackLittermanView]:
    """Three deterministic illustrative views (NOT forecasts)."""
    return [
        BlackLittermanView(
            id="tw_over_jp",
            description="Taiwan equity outperforms Japan equity by 2% annualised (relative view).",
            asset_weights={"tw_eq": 1.0, "jp_eq": -1.0},
            view_return=0.02,
            confidence=0.5,
        ),
        BlackLittermanView(
            id="gold_over_cash",
            description="Gold outperforms USD cash by 1.5% annualised (relative view).",
            asset_weights={"gold": 1.0, "usd_cash": -1.0},
            view_return=0.015,
            confidence=0.5,
        ),
        BlackLittermanView(
            id="ust_absolute",
            description="US Treasury absolute expected return ≈ 2.5% (illustrative absolute view, ~0.5% below its sample prior).",
            asset_weights={"us_treas": 1.0},
            view_return=0.025,
            confidence=0.4,
        ),
    ]


def _safe_inv(mat: np.ndarray) -> np.ndarray:
    try:
        return np.linalg.inv(mat)
    except np.linalg.LinAlgError:
        return np.linalg.pinv(mat)


def build_black_litterman(
    mu_prior: np.ndarray,
    cov: np.ndarray,
    ids: List[str],
    names: dict,
    current_w: np.ndarray,
    rp_w: np.ndarray,
    rf: float,
    risk_aversion: float,
    tau: float,
    views: List[BlackLittermanView],
    constraints: Optional[OptimizationConstraints],
) -> BlackLittermanResult:
    n = len(ids)
    Sigma = cov
    w_mkt = current_w  # market = current sample allocation (illustrative)
    pi = risk_aversion * (Sigma @ w_mkt)  # implied equilibrium returns

    notes = [
        "Implied equilibrium returns π = δ·Σ·w_market (market = current sample weights).",
        "Sample views are illustrative only and are not forecasts.",
    ]

    if views:
        P = np.array([[float(v.asset_weights.get(a, 0.0)) for a in ids] for v in views])
        q = np.array([float(v.view_return) for v in views])
        conf = np.array([float(v.confidence) for v in views])
        tau_sigma = tau * Sigma
        view_var = np.maximum(np.diag(P @ tau_sigma @ P.T), 1e-10)
        # Higher confidence → smaller Omega → view weighted more.
        omega = np.diag(view_var / np.maximum(conf, 1e-6))
        try:
            inv_tau_sigma = _safe_inv(tau_sigma)
            inv_omega = _safe_inv(omega)
            a_mat = inv_tau_sigma + P.T @ inv_omega @ P
            b_vec = inv_tau_sigma @ pi + P.T @ inv_omega @ q
            mu_bl = _safe_inv(a_mat) @ b_vec
            if not np.all(np.isfinite(mu_bl)):
                raise np.linalg.LinAlgError
        except np.linalg.LinAlgError:
            mu_bl = pi.copy()
            notes.append("Posterior solve was singular; falling back to implied returns.")
    else:
        mu_bl = pi.copy()
        notes.append("No views supplied; posterior equals the implied equilibrium returns.")

    returns = [
        AssetReturnView(
            asset_id=ids[i],
            name=names.get(ids[i], ids[i]),
            implied_return=float(pi[i]),
            posterior_return=float(mu_bl[i]),
            prior_return=float(mu_prior[i]),
        )
        for i in range(n)
    ]

    # BL-optimised portfolio = max-Sharpe over the constrained candidate pool,
    # scored with the posterior returns.
    c = constraints or OptimizationConstraints()
    lo, hi = float(c.min_weight), float(c.max_weight)
    pool = _candidate_pool(mu_bl, cov, current_w, rp_w, lo, hi)
    best = pool[_best_sharpe(pool, mu_bl, cov, rf)]
    bl_pf = _portfolio(
        "black_litterman",
        "Black-Litterman max Sharpe",
        "Maximise Sharpe using posterior (Black-Litterman) returns",
        best,
        mu_bl,
        cov,
        ids,
        rf,
        current_w,
        lo,
        hi,
        ["Uses Black-Litterman posterior returns; views are illustrative, not forecasts."],
    )

    return BlackLittermanResult(
        risk_aversion=float(risk_aversion),
        tau=float(tau),
        returns=returns,
        views=views,
        bl_optimized_portfolio=bl_pf,
        notes=notes,
    )


# --------------------------------------------------------------------------- #
# Rebalance / turnover
# --------------------------------------------------------------------------- #
def build_rebalance(
    target: OptimizedPortfolio,
    ids: List[str],
    names: dict,
    current_w: np.ndarray,
    previous_weights: Optional[dict],
) -> RebalanceAnalysis:
    base = current_w
    if previous_weights:
        raw = np.array([float(previous_weights.get(i, 0.0)) for i in ids])
        if raw.sum() > _MIN_VOL:
            base = raw / raw.sum()

    target_w = np.array([float(target.weights.get(i, 0.0)) for i in ids])
    delta = target_w - base
    deltas = [
        RebalanceAssetDelta(
            asset_id=ids[i],
            name=names.get(ids[i], ids[i]),
            current_weight=float(base[i]),
            target_weight=float(target_w[i]),
            delta=float(delta[i]),
        )
        for i in range(len(ids))
    ]
    inc = int(np.argmax(delta))
    dec = int(np.argmin(delta))
    return RebalanceAnalysis(
        target_portfolio_id=target.id,
        asset_deltas=deltas,
        absolute_turnover=float(0.5 * np.sum(np.abs(delta))),
        largest_increase=ids[inc],
        largest_decrease=ids[dec],
        note=(
            "Hypothetical rebalance delta toward the selected portfolio "
            "(target − current). Illustrative only — not a trade order or "
            "buy/sell recommendation."
        ),
    )
