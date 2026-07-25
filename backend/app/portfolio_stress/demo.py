"""
Deterministic, idempotent demo for the Portfolio Stress Lab (16 cases).

Every case stresses a STORED Phase 56 demo portfolio (seeded first,
idempotently — nothing in the Phase 56/55/54 registries is modified).
Demo keys make re-seeding a no-op; only the flagship creates an
Experiment Registry record.  All scenarios are explicit assumptions for
educational demonstration — none is a prediction, a worst case, or a
recommendation.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.cost_diagnostics.store import run_demo_key_id as cost_demo_id
from app.portfolio_diagnostics.demo import seed_demo_portfolio_diagnostics
from app.portfolio_diagnostics.store import run_demo_key_id as pd_demo_id
from app.portfolio_stress import service, store

_BASE = datetime(2024, 1, 1)


def _iso(i: int) -> str:
    """Timestamp of index i on the Phase 56 demo timeline (160 days)."""
    return (_BASE + timedelta(days=i)).isoformat()


# a deliberately non-PSD 6x6 correlation: the (a,b,c) triangle 0.9/0.9/-0.9
def _non_psd_correlation() -> List[List[float]]:
    m = [[1.0 if i == j else 0.0 for j in range(6)] for i in range(6)]
    m[0][1] = m[1][0] = 0.9
    m[0][2] = m[2][0] = 0.9
    m[1][2] = m[2][1] = -0.9
    return m


def seed_demo_portfolio_stress() -> Dict[str, Any]:
    seed_demo_portfolio_diagnostics()  # idempotent; cascades upstream demos

    erc = pd_demo_id("demo:pd:erc")
    equal = pd_demo_id("demo:pd:equal-weight")
    capped = pd_demo_id("demo:pd:min-variance-caps")
    turnover = pd_demo_id("demo:pd:turnover-cost")
    cost_run = cost_demo_id("demo:cd:complete-costs")
    if None in (erc, equal, capped, turnover, cost_run):
        raise service.PortfolioStressError(
            "portfolio-stress demo requires the Phase 56/55 demo runs")

    created = 0
    skipped = 0
    run_ids: List[int] = []
    notes: List[str] = []

    def seed(key: str, payload: Dict[str, Any], *, baseline: bool = False,
             experiment: bool = False, note: str = "") -> None:
        nonlocal created, skipped
        existing = store.run_demo_key_id(key)
        if existing is not None:
            skipped += 1
            run_ids.append(existing)
            return
        run = service.create_run(payload, demo_key=key)
        service.execute_run(run["id"], create_experiment=experiment)
        if baseline:
            service.mark_baseline(run["id"])
        created += 1
        run_ids.append(run["id"])
        if note:
            notes.append(note)

    # 1 — flagship: combined group shock + volatility + correlation stress
    seed("demo:ps:flagship-group-shock", {
        "name": "Flagship combined stress on the ERC book",
        "description": ("Group shocks (equity -12%, commodity -8%, rates "
                        "+50 bps), volatility x1.75 and correlations moved "
                        "toward one (alpha 0.35) on the stored ERC weights: "
                        "the full documented execution order, with P&L and "
                        "risk-estimate effects reported separately."),
        "portfolio_run_id": erc, "notional": 1_000_000.0,
        "scenario": {
            "scenario_type": "combined_scenario",
            "name": "Broad risk-off shock",
            "scenario_definition_id": "flagship-risk-off",
            "group_shocks": {"equity": {"value": -12, "unit": "percent"},
                             "commodity": {"value": -8, "unit": "percent"},
                             "rates": {"value": 50, "unit": "bps"}},
            "volatility_stress": {"mode": "multiplicative",
                                  "multiplier": 1.75},
            "correlation_stress": {"mode": "toward_one", "alpha": 0.35},
            "missing_shock_policy": "zero",
        },
        "sensitivity": {"global_shock": [-0.10, -0.02, 0.05],
                        "volatility_multiplier": [1.25, 2.5]},
    }, baseline=True, experiment=True,
        note="flagship combined scenario (baseline + experiment record)")

    # 2 — single-asset percent shock
    seed("demo:ps:single-asset-percent", {
        "name": "Single-asset shock, others explicitly unshocked",
        "description": ("highvol-a -20% with the 'zero' missing-shock "
                        "policy: every other asset is explicitly assumed "
                        "unshocked (a configured assumption, not silence)."),
        "portfolio_run_id": erc, "notional": 250_000.0,
        "scenario": {
            "scenario_type": "hypothetical_asset_shock",
            "name": "highvol-a -20%",
            "asset_shocks": {"highvol-a": {"value": -20, "unit": "percent"}},
            "missing_shock_policy": "zero",
        },
    })

    # 3 — unit conversions in one scenario
    seed("demo:ps:units-bps", {
        "name": "Shock units side by side (bps / return / percent)",
        "description": ("-250 bps, -0.03 return and -3 percent in one "
                        "scenario: the stored per-asset shocks show the "
                        "documented unit conversions (bps/10000, "
                        "percent/100) with no ambiguity."),
        "portfolio_run_id": equal,
        "scenario": {
            "scenario_type": "hypothetical_asset_shock",
            "name": "Mixed units",
            "asset_shocks": {
                "lowvol-a": {"value": -250, "unit": "bps"},
                "midvol-a": {"value": -0.03, "unit": "return"},
                "highvol-a": {"value": -3, "unit": "percent"}},
            "missing_shock_policy": "zero",
        },
    })

    # 4 — missing-shock policy 'unavailable' => honest partial
    seed("demo:ps:missing-unavailable", {
        "name": "Partial scenario under the 'unavailable' policy",
        "description": ("Only midvol-a is shocked and the missing-shock "
                        "policy is 'unavailable': uncovered assets carry no "
                        "assumed shock, the scenario total covers the "
                        "shocked subset only, and drifted weights are "
                        "honestly unavailable."),
        "portfolio_run_id": equal,
        "scenario": {
            "scenario_type": "hypothetical_asset_shock",
            "name": "Partial coverage",
            "asset_shocks": {"midvol-a": {"value": -10, "unit": "percent"}},
            "missing_shock_policy": "unavailable",
        },
    })

    # 5 — verified ex-ante historical window
    seed("demo:ps:historical-exante", {
        "name": "Historical window replay (verified ex-ante)",
        "description": ("Compounded stored returns over days 20-45, ending "
                        "strictly before the portfolio decision cutoff: "
                        "integrity verified_historical_window."),
        "portfolio_run_id": erc, "notional": 1_000_000.0,
        "scenario": {
            "scenario_type": "historical_window",
            "name": "Stored window replay",
            "historical": {"usage": "ex_ante",
                           "start_timestamp": _iso(20),
                           "end_timestamp": _iso(45)},
        },
    })

    # 6 — single historical period
    seed("demo:ps:historical-single", {
        "name": "Single stored period replay",
        "description": ("One stored observation (day 30) replayed as the "
                        "shock vector — the smallest verifiable historical "
                        "scenario."),
        "portfolio_run_id": erc,
        "scenario": {
            "scenario_type": "historical_single_period",
            "name": "Day-30 replay",
            "historical": {"usage": "ex_ante",
                           "start_timestamp": _iso(30)},
        },
    })

    # 7 — full-sample historical window => descriptive only
    seed("demo:ps:historical-full-sample", {
        "name": "Full-sample window (descriptive only)",
        "description": ("A window spanning the whole stored sample: "
                        "integrity full_sample_descriptive, prominently "
                        "warned, never callable ex-ante."),
        "portfolio_run_id": erc,
        "scenario": {
            "scenario_type": "historical_window",
            "name": "Whole sample",
            "historical": {"usage": "descriptive",
                           "start_timestamp": _iso(0),
                           "end_timestamp": _iso(159)},
        },
    })

    # 8 — future-looking ex-ante claim => invalid
    seed("demo:ps:future-looking-invalid", {
        "name": "Invalid future-looking ex-ante claim",
        "description": ("A window claimed ex-ante that extends beyond the "
                        "portfolio decision cutoff: integrity invalid — a "
                        "future period is never labelled ex-ante verified, "
                        "and the run cannot become a baseline."),
        "portfolio_run_id": erc,
        "scenario": {
            "scenario_type": "historical_window",
            "name": "Future-looking window",
            "historical": {"usage": "ex_ante",
                           "start_timestamp": _iso(40),
                           "end_timestamp": _iso(100)},
        },
    })

    # 9 — pure volatility stress (risk estimate only, zero P&L)
    seed("demo:ps:vol-stress", {
        "name": "Volatility x2.5 (risk estimate only)",
        "description": ("A pure volatility scenario: no price shocks, so "
                        "the scenario RETURN is zero by construction (no "
                        "P&L is reported because no notional is configured "
                        "— never fabricated) while the stressed volatility "
                        "and contributions move — the P&L-vs-risk "
                        "separation made visible."),
        "portfolio_run_id": erc,
        "scenario": {
            "scenario_type": "volatility_stress",
            "name": "Vol x2.5",
            "volatility_stress": {"mode": "multiplicative",
                                  "multiplier": 2.5},
            "missing_shock_policy": "zero",
        },
    })

    # 10 — additive volatility with disclosed negative clamping
    seed("demo:ps:vol-additive-floor", {
        "name": "Additive volatility shock with disclosed flooring",
        "description": ("An additive -0.02 per-period volatility shock "
                        "floors low-volatility assets at zero — the "
                        "clamping is disclosed, never silent."),
        "portfolio_run_id": erc,
        "scenario": {
            "scenario_type": "volatility_stress",
            "name": "Additive vol -0.02",
            "volatility_stress": {"mode": "additive", "value": -0.02},
            "missing_shock_policy": "zero",
        },
    })

    # 11 — correlations toward one
    seed("demo:ps:corr-toward-one", {
        "name": "Correlations moved toward one (alpha 0.7)",
        "description": ("rho + 0.7 x (1 - rho) on the baseline correlation: "
                        "measured diversification collapse under an explicit "
                        "deterministic rule (elementwise blend with the "
                        "all-ones matrix, PSD preserved)."),
        "portfolio_run_id": erc,
        "scenario": {
            "scenario_type": "correlation_stress",
            "name": "Toward-one 0.7",
            "correlation_stress": {"mode": "toward_one", "alpha": 0.7},
            "missing_shock_policy": "zero",
        },
    })

    # 12 — supplied non-PSD correlation, repair 'none' => honest failure
    seed("demo:ps:corr-supplied-nonpsd", {
        "name": "Supplied non-PSD correlation — honest unavailability",
        "description": ("A supplied correlation with an infeasible "
                        "0.9/0.9/-0.9 triangle is not positive semidefinite; "
                        "with repair policy 'none' the stressed covariance "
                        "is unavailable with the exact reason — nothing is "
                        "silently repaired."),
        "portfolio_run_id": equal,
        "scenario": {
            "scenario_type": "correlation_stress",
            "name": "Non-PSD supplied matrix",
            "correlation_stress": {"mode": "supplied",
                                   "matrix": _non_psd_correlation(),
                                   "repair": "none"},
            "missing_shock_policy": "zero",
        },
    })

    # 13 — same matrix with an explicit eigenvalue-floor repair
    seed("demo:ps:corr-supplied-repaired", {
        "name": "Supplied non-PSD correlation — explicit repair",
        "description": ("The same infeasible matrix under an explicit "
                        "eigenvalue floor: original and repaired "
                        "eigenvalues are both recorded and the repair is "
                        "visible in the run."),
        "portfolio_run_id": equal,
        "scenario": {
            "scenario_type": "correlation_stress",
            "name": "Repaired supplied matrix",
            "correlation_stress": {"mode": "supplied",
                                   "matrix": _non_psd_correlation(),
                                   "repair": "eigenvalue_floor",
                                   "eigenvalue_floor": 1e-8},
            "missing_shock_policy": "zero",
        },
    })

    # 14 — liquidity/cost stress over the linked Phase 55 model
    seed("demo:ps:cost-liquidity", {
        "name": "Liquidity and cost stress on the linked cost model",
        "description": ("Spread x3, slippage x2, impact x5 and ADV x0.25 "
                        "on a COPY of the linked Phase 55 model (new "
                        "fingerprint; the stored model is untouched): "
                        "stressed reference costs, participation above the "
                        "explicit threshold, and the square-root impact "
                        "component honestly unavailable for weight-space "
                        "turnover."),
        "portfolio_run_id": turnover, "notional": 1_000_000.0,
        "cost_diagnostic_run_id": cost_run,
        "scenario": {
            "scenario_type": "liquidity_and_cost_stress",
            "name": "Liquidity squeeze",
            "liquidity_cost_stress": {
                "spread_multiplier": 3.0, "slippage_multiplier": 2.0,
                "impact_multiplier": 5.0, "adv_multiplier": 0.25,
                "base_adv_notional": 5_000_000.0,
                "participation_threshold": 0.25},
            "missing_shock_policy": "zero",
        },
        "sensitivity": {"spread_multiplier": [1.5, 5.0]},
    })

    # 15 — constraint breaches on the drifted book
    seed("demo:ps:constraint-breach", {
        "name": "Post-shock constraint breaches (no auto-rebalance)",
        "description": ("Asymmetric shocks drift the capped minimum-variance "
                        "book past its stored per-asset cap: breaches are "
                        "listed for the drifted weights and nothing is "
                        "rebalanced automatically."),
        "portfolio_run_id": capped,
        "scenario": {
            "scenario_type": "hypothetical_group_shock",
            "name": "Asymmetric drift",
            "group_shocks": {"equity": {"value": -40, "unit": "percent"},
                             "commodity": {"value": -40, "unit": "percent"},
                             "rates": {"value": 5, "unit": "percent"}},
            "missing_shock_policy": "zero",
        },
    })

    # 16 — drawdown episodes and deepest-episode attribution
    seed("demo:ps:drawdown-attribution", {
        "name": "Drawdown episodes on the rebalanced book",
        "description": ("The recomputed portfolio-return series of the "
                        "rebalancing demo book: trailing-peak drawdown "
                        "episodes with recovered/unrecovered states and "
                        "per-asset attribution of the deepest episode under "
                        "the labelled static-weight approximation."),
        "portfolio_run_id": turnover, "notional": 500_000.0,
        "scenario": {
            "scenario_type": "hypothetical_asset_shock",
            "name": "Mild broad shock",
            "global_shock": {"value": -1, "unit": "percent"},
            "missing_shock_policy": "zero",
        },
    })

    return {"created": created > 0,
            "created_count": created, "skipped_count": skipped,
            "run_ids": run_ids, "notes": notes}


__all__ = ["seed_demo_portfolio_stress"]
