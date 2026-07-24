"""
Deterministic demo fixture for the Portfolio Diagnostics Lab (idempotent).

Eleven runs cover the fifteen documented demo cases:

1.  ``demo:pd:equal-weight`` — equal-weight reference (case 1).
2.  ``demo:pd:inverse-vol`` — inverse volatility with a visible floor; the
    lowest-volatility asset measurably receives the highest weight (case 2).
3.  ``demo:pd:erc`` — equal risk contribution with near-equal measured
    contributions; valid BASELINE candidate (cases 3, 15).
4.  ``demo:pd:min-variance-caps`` — SLSQP minimum variance under a weight
    cap and group caps, all bounds satisfied (cases 4, 7, 8).
5.  ``demo:pd:high-correlation`` — nearly collinear assets: near-singular
    condition warning and concentration (case 5).
6.  ``demo:pd:singular-honest-failure`` — a duplicated return series with
    repair policy ``none``: honest solver failure, nothing repaired
    silently (case 6).
7.  ``demo:pd:singular-repaired`` — the same universe with an explicit
    eigenvalue floor: visible repair record (case 6, repair branch).
8.  ``demo:pd:turnover-cost`` — every-N rebalances with a turnover cap
    that the independent check flags at one rebalance (cases 9, 14) plus a
    linked Phase 55 cost model where square-root impact stays honestly
    unavailable (case 10).
9.  ``demo:pd:regime-linked`` — portfolio characteristics by stored Phase
    54 regime assignments (case 11).
10. ``demo:pd:full-sample`` + ``demo:pd:future-looking`` — the full-sample
    descriptive warning (case 12) and a user-supplied centered-provenance
    invalid configuration (case 13).

(Structurally infeasible constraints are rejected at create with a 422 —
covered by tests and the API, not a stored run.)  Seeds use the 56xxx
namespace; loading twice creates nothing.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

import numpy as np

from app.cost_diagnostics.demo import seed_demo_cost_diagnostics
from app.cost_diagnostics.store import run_demo_key_id as cost_demo_id
from app.regime_diagnostics.demo import _timestamps as _regime_timestamps
from app.regime_diagnostics.store import run_demo_key_id as regime_demo_id
from app.portfolio_diagnostics import service, store

_BASE = datetime(2024, 1, 1)


def _ts(n: int, start: datetime = _BASE) -> List[str]:
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


def _asset(asset_id: str, returns, *, group=None, name=None,
           asset_type: str = "index") -> Dict[str, Any]:
    return {"asset_id": asset_id, "name": name or asset_id,
            "asset_type": asset_type, "group": group,
            "returns": [round(float(v), 8) for v in returns]}


def _standard_universe(seed: int = 56001, n: int = 160) -> List[Dict[str, Any]]:
    """Six assets with clearly distinct volatilities and mild correlation."""
    rng = np.random.default_rng(seed)
    common = rng.normal(0.0, 0.004, n)
    specs = [("lowvol-a", 0.003, "rates"), ("lowvol-b", 0.005, "rates"),
             ("midvol-a", 0.008, "equity"), ("midvol-b", 0.010, "equity"),
             ("highvol-a", 0.016, "commodity"), ("highvol-b", 0.020, "commodity")]
    assets = []
    for aid, scale, group in specs:
        own = rng.normal(0.0004, scale, n)
        assets.append(_asset(aid, own + 0.3 * common, group=group))
    return assets


def seed_demo_portfolio_diagnostics() -> Dict[str, int]:
    created = skipped = 0
    seed_demo_cost_diagnostics()  # idempotent; cascades every upstream demo

    n = 160
    stamps = _ts(n)
    base_common = {"frequency": "daily", "timestamps": stamps,
                   "estimation": {"mode": "rolling", "lookback": 60, "lag": 1}}

    def seed(key: str, payload: Dict[str, Any], *, baseline: bool = False,
             experiment: bool = False) -> bool:
        nonlocal created, skipped
        if store.run_demo_key_id(key) is not None:
            skipped += 1
            return False
        run = service.create_run(payload, demo_key=key)
        service.execute_run(run["id"], create_experiment=experiment)
        if baseline:
            service.mark_baseline(run["id"])
        created += 1
        return True

    seed("demo:pd:equal-weight", {
        "name": "Equal-weight reference",
        "description": ("1/N over the six-asset universe — the documented "
                        "reference construction; risk contributions show how "
                        "unequal equal weights are in risk terms."),
        "method": "equal_weight", **base_common,
        "assets": _standard_universe(),
    })

    seed("demo:pd:inverse-vol", {
        "name": "Inverse-volatility weighting",
        "description": ("Weights proportional to 1/sigma over the trailing "
                        "window with an explicit visible volatility floor: "
                        "lower-volatility assets measurably receive higher "
                        "weights."),
        "method": "inverse_volatility", **base_common,
        "assets": _standard_universe(),
        "volatility_floor": 0.001,
        "sensitivity": {"volatility_multiplier": [0.5, 1.5]},
    })

    seed("demo:pd:erc", {
        "name": "Equal risk contribution (ERC)",
        "description": ("Long-only risk parity via the log-barrier convex "
                        "formulation: measured percentage risk contributions "
                        "sit near the equal targets within the documented "
                        "tolerance; a valid baseline candidate."),
        "method": "erc", **base_common,
        "assets": _standard_universe(),
        "risk_budgets": {a["asset_id"]: 1.0 / 6.0
                         for a in _standard_universe()},
        "sensitivity": {"shrinkage_alpha": [0.2],
                        "correlation_multiplier": [0.5, 1.5]},
        "covariance": {"method": "fixed_shrinkage", "alpha": 0.1,
                       "target": "diagonal"},
    }, baseline=True, experiment=True)

    seed("demo:pd:min-variance-caps", {
        "name": "Minimum variance with weight and group caps",
        "description": ("SLSQP minimum variance under a 0.30 per-asset cap "
                        "and 0.50 group caps; every bound is re-checked "
                        "independently after the solve."),
        "method": "min_variance", **base_common,
        "assets": _standard_universe(),
        "constraints": {"long_only": True, "max_weight": 0.30,
                        "group_caps": {"rates": 0.50, "equity": 0.50,
                                       "commodity": 0.50}},
        "sensitivity": {"max_weight": [0.25, 0.40]},
    })

    rng_hc = np.random.default_rng(56005)
    base_series = rng_hc.normal(0.0005, 0.01, n)
    seed("demo:pd:high-correlation", {
        "name": "Highly correlated universe",
        "description": ("Four assets sharing one driver: pairwise "
                        "correlations near one, a near-singular condition "
                        "warning, and concentrated risk contributions."),
        "method": "erc", **base_common,
        "assets": [
            _asset("corr-a", base_series + rng_hc.normal(0, 0.0005, n)),
            _asset("corr-b", base_series + rng_hc.normal(0, 0.0005, n)),
            _asset("corr-c", base_series + rng_hc.normal(0, 0.0008, n)),
            _asset("corr-d", base_series * 0.9 + rng_hc.normal(0, 0.0005, n)),
        ],
    })

    rng_sg = np.random.default_rng(56006)
    dup = rng_sg.normal(0.0004, 0.008, n)
    other = rng_sg.normal(0.0004, 0.012, n)
    seed("demo:pd:singular-honest-failure", {
        "name": "Degenerate covariance — honest failure",
        "description": ("A constant return series has zero variance, so the "
                        "covariance is degenerate (singular): the ERC "
                        "log-barrier problem is unbounded and the solve "
                        "fails honestly — nothing is repaired silently and "
                        "no weights are fabricated."),
        "method": "erc", **base_common,
        "assets": [
            _asset("constant", [0.0002] * n),  # zero variance => degenerate
            _asset("dup-a", dup), _asset("other", other),
        ],
        "covariance": {"method": "sample", "repair": "none"},
    })
    seed("demo:pd:singular-repaired", {
        "name": "Singular covariance — explicit eigenvalue floor",
        "description": ("Two identical return series make the covariance "
                        "singular (a zero eigenvalue, condition number "
                        "undefined, warned); an explicit visible eigenvalue "
                        "floor repairs it, with original and repaired "
                        "eigenvalues both recorded."),
        "method": "min_variance", **base_common,
        "assets": [_asset("dup-a", dup), _asset("dup-b", dup),
                   _asset("other", other)],
        "covariance": {"method": "sample", "repair": "eigenvalue_floor",
                       "eigenvalue_floor": 1e-8},
    })

    seed("demo:pd:turnover-cost", {
        "name": "Rebalancing with turnover cap and linked costs",
        "description": ("Inverse-volatility weights re-estimated every 20 "
                        "observations under a tight turnover cap the "
                        "independent check flags, with descriptive rebalance "
                        "costs from the linked Phase 55 cost model — its "
                        "square-root impact stays honestly unavailable for "
                        "weight-space turnover."),
        "method": "inverse_volatility", **base_common,
        "assets": _standard_universe(56008),
        "rebalance": {"kind": "every_n", "every_n": 20,
                      "initial_turnover_policy": "zero_book"},
        "constraints": {"long_only": True, "turnover_cap": 0.05},
        "cost_diagnostic_run_id": cost_demo_id("demo:cd:complete-costs"),
        "cost_notional": 1_000_000.0,
        "sensitivity": {"volatility_multiplier": [0.5, 2.0]},
    })

    regime_run = regime_demo_id("demo:rd:volatility-trend")
    rng_rl = np.random.default_rng(56009)
    r_stamps = _regime_timestamps(240)
    seed("demo:pd:regime-linked", {
        "name": "Regime-conditioned portfolio characteristics",
        "description": ("An equal-weight portfolio on the Phase 54 demo "
                        "timeline: realized portfolio returns, turnover and "
                        "cost completeness summarised by the stored "
                        "volatility-regime assignments — never recomputed."),
        "method": "equal_weight",
        "frequency": "daily", "timestamps": r_stamps,
        "estimation": {"mode": "rolling", "lookback": 40, "lag": 1},
        "assets": [
            _asset("core-a", rng_rl.normal(0.0006, 0.006, 240)),
            _asset("core-b", rng_rl.normal(0.0004, 0.009, 240)),
            _asset("core-c", rng_rl.normal(0.0005, 0.012, 240)),
        ],
        "rebalance": {"kind": "every_n", "every_n": 40,
                      "initial_turnover_policy": "zero_book"},
        "regime_run_id": regime_run,
        "regime_definition_id": "vol",
    })

    seed("demo:pd:full-sample", {
        "name": "Full-sample descriptive estimation",
        "description": ("Covariance estimated on the whole sample — "
                        "descriptive only, prominently warned, and never "
                        "called leakage-safe."),
        "method": "erc",
        "frequency": "daily", "timestamps": stamps,
        "estimation": {"mode": "full_sample", "lag": 1},
        "assets": _standard_universe(56010),
    })

    seed("demo:pd:future-looking", {
        "name": "Invalid future-looking weight provenance",
        "description": ("User-supplied weights claiming a centered "
                        "estimation basis: the integrity state is invalid "
                        "and the run cannot become a baseline."),
        "method": "user_supplied",
        "frequency": "daily", "timestamps": stamps,
        "estimation": {"mode": "rolling", "lookback": 60, "lag": 1},
        "assets": _standard_universe(56011),
        "weights": {"lowvol-a": 0.3, "lowvol-b": 0.2, "midvol-a": 0.2,
                    "midvol-b": 0.1, "highvol-a": 0.1, "highvol-b": 0.1},
        "weight_provenance": {"basis": "centered"},
        "normalization": "sum_to_one",
    })

    return {"created_runs": created, "skipped_existing": skipped}
