"""
Deterministic demo fixture for the Cost Diagnostics Lab (idempotent).

Six runs cover the twelve documented demo cases:

1. ``demo:cd:complete-costs`` — low-turnover trades with small configured
   costs: bps commission, explicit spread + slippage, square-root impact on
   trailing-derived ADV/volatility, one observation above the participation
   threshold, a capacity curve, and a valid baseline (cases 1, 6, 7, 8, 9, 12).
2. ``demo:cd:high-turnover-erosion`` — basis-point commission example where
   most gross-positive trades become net-nonpositive (cases 2, 5).
3. ``demo:cd:partial-missing-inputs`` — supplied spread/ADV inputs missing on
   part of the sample: partial completeness, unavailable never zero (case 3).
4. ``demo:cd:fixed-fee-scaling`` — fixed per-order commission plus tick-based
   spread/slippage under an integer-contract capacity policy: fixed fees stay
   fixed while per-contract costs scale (case 4).
5. ``demo:cd:regime-linked`` — period observations on the Phase 54 demo
   timeline with higher supplied spreads and trailing volatility in the
   high-volatility regime; costs join stored regime assignments (cases 7, 10).
6. ``demo:cd:invalid-future-looking`` — an ADV input claiming a trailing
   basis with lag 0 (future-looking): integrity ``invalid``, baseline
   blocked (case 11; the negative-fee variant is rejected at creation with
   a 422 and therefore cannot be stored).

Everything is generated in-module from fixed seeds (55xxx namespace); loading
twice creates nothing new.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

import numpy as np

from app.dataset_registry.store import version_demo_key_id
from app.model_validation.store import run_demo_key_id as validation_demo_id
from app.regime_diagnostics.demo import (
    _timestamps as _regime_timestamps,
    _vol_trend_market,
    seed_demo_regime_diagnostics,
)
from app.cost_diagnostics import service, store

_BASE = datetime(2024, 1, 1)


def _ts(n: int, start: datetime = _BASE) -> List[str]:
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


def _trade(trade_id: str, candidate_id: str, side: str, day: int, hold: int,
           entry_price: float, gross_return: float, quantity: float,
           start: datetime = _BASE, multiplier: float = 1.0,
           **extra: Any) -> Dict[str, Any]:
    """Build one deterministic trade whose gross return on entry notional is
    ``gross_return`` (long: exit = entry*(1+r); short: exit = entry*(1-r))."""
    if side == "long":
        exit_price = entry_price * (1.0 + gross_return)
    else:
        exit_price = entry_price * (1.0 - gross_return)
    return {
        "trade_id": trade_id, "candidate_id": candidate_id, "side": side,
        "entry_timestamp": (start + timedelta(days=day)).isoformat(),
        "exit_timestamp": (start + timedelta(days=day + hold)).isoformat(),
        "entry_price": round(entry_price, 6),
        "exit_price": round(exit_price, 6),
        "quantity": quantity, "contract_multiplier": multiplier,
        "currency": "USD", **extra,
    }


def _r1_trades() -> List[Dict[str, Any]]:
    rng = np.random.default_rng(55001)
    trades = []
    for i in range(24):
        cid = "basket-a" if i % 2 == 0 else "basket-b"
        side = "long" if i % 3 != 2 else "short"
        day = 25 + i * 8
        ret = round(float(rng.normal(0.004, 0.01)), 8)
        qty = float(10 + (i % 5) * 5)
        trades.append(_trade(f"t1-{i:02d}", cid, side, day, 2 + (i % 3),
                             100.0 + i * 0.5, ret, qty))
    # one deliberately large trade above the participation threshold (case 9)
    trades.append(_trade("t1-big", "basket-a", "long", 121, 3, 112.0,
                         0.006, 150.0))
    return trades


def _r1_series() -> Dict[str, Any]:
    rng = np.random.default_rng(55002)
    n = 260
    return {
        "timestamps": _ts(n),
        # ADV in currency (matches notional participation mode)
        "volume": [round(float(v), 4) for v in rng.normal(40_000.0, 2_500.0, n)],
        "returns": [round(float(v), 8) for v in rng.normal(0.0, 0.01, n)],
    }


def _r2_trades() -> List[Dict[str, Any]]:
    rng = np.random.default_rng(55003)
    trades = []
    for i in range(40):
        day = 3 + i * 2
        ret = round(float(rng.normal(0.0008, 0.002)), 8)
        trades.append(_trade(f"t2-{i:02d}", "rapid-cycle", "long", day, 1,
                             50.0 + (i % 7), ret, 100.0,
                             start=datetime(2024, 6, 3)))
    return trades


def _r3_trades() -> List[Dict[str, Any]]:
    rng = np.random.default_rng(55004)
    trades = []
    for i in range(20):
        day = 4 + i * 5
        ret = round(float(rng.normal(0.003, 0.006)), 8)
        extra: Dict[str, Any] = {}
        if i % 5 != 3 and i % 5 != 4:  # 60% of trades carry supplied inputs
            extra["cost_inputs"] = {
                "spread": {"value": 2.0 + (i % 3) * 0.5, "unit": "bps",
                           "basis": "declared"},
                "adv": {"value": 500.0, "unit": "units", "basis": "declared"},
                "volatility": {"value": 0.012, "basis": "declared"},
            }
        trades.append(_trade(f"t3-{i:02d}", "patchy-data", "long", day,
                             2, 80.0 + i, ret, 10.0 + (i % 4) * 10,
                             start=datetime(2024, 3, 4), **extra))
    return trades


def _r4_trades() -> List[Dict[str, Any]]:
    rng = np.random.default_rng(55005)
    trades = []
    for i in range(16):
        day = 2 + i * 6
        ret = round(float(rng.normal(0.001, 0.003)), 8)
        trades.append(_trade(f"t4-{i:02d}", "small-account", "long", day, 2,
                             5000.0 + i * 5, ret, float(1 + i % 3),
                             start=datetime(2024, 2, 5), multiplier=5.0))
    return trades


def _r5_observations() -> List[Dict[str, Any]]:
    rng = np.random.default_rng(55006)
    stamps = _regime_timestamps(240)
    obs = []
    for i in range(30, 240):
        high_vol = 80 <= i < 160
        spread_bps = 3.5 if high_vol else 1.8
        turnover = round(float(0.6 + rng.uniform(-0.2, 0.4)), 6)
        obs.append({
            "observation_id": f"p5-{i:03d}",
            "candidate_id": "allweather-costed",
            "timestamp": stamps[i],
            "gross_return": round(float(rng.normal(0.0015, 0.004)), 8),
            "turnover": turnover,
            "traded_notional": round(turnover * 1_000_000.0, 2),
            "cost_inputs": {
                "spread": {"value": spread_bps, "unit": "bps",
                           "basis": "trailing", "lag": 1, "lookback": 20},
            },
        })
    return obs


def _r5_series() -> Dict[str, Any]:
    rng = np.random.default_rng(55007)
    return {
        "timestamps": _regime_timestamps(240),
        # ADV in currency (notional participation mode)
        "volume": [round(float(v), 2) for v in rng.normal(5e6, 2e5, 240)],
        # volatility derives from the same market series the regime run used
        "returns": _vol_trend_market(240),
    }


def _r6_trades() -> List[Dict[str, Any]]:
    rng = np.random.default_rng(55008)
    trades = []
    for i in range(12):
        ret = round(float(rng.normal(0.002, 0.004)), 8)
        trades.append(_trade(f"t6-{i:02d}", "future-peek", "long", 3 + i * 4,
                             1, 50.0, ret, 10.0, start=datetime(2024, 5, 6),
                             cost_inputs={
                                 "adv": {"value": 500.0, "unit": "units",
                                         # trailing claim with lag 0 looks
                                         # through the execution period
                                         "basis": "trailing", "lag": 0,
                                         "lookback": 10},
                                 "volatility": {"value": 0.01,
                                                "basis": "declared"},
                             }))
    return trades


def seed_demo_cost_diagnostics() -> Dict[str, int]:
    created = skipped = 0
    seed_demo_regime_diagnostics()  # idempotent; cascades all upstream demos

    if store.run_demo_key_id("demo:cd:complete-costs") is not None:
        skipped += 1
    else:
        run = service.create_run(
            {
                "name": "Complete gross-to-net (bps costs + sqrt impact)",
                "description": (
                    "Low-turnover trades with small configured costs: 1 bp "
                    "commission, half of a 2 bp spread, 1 bp slippage per "
                    "side and a square-root impact estimate on trailing "
                    "ADV/volatility. One large trade exceeds the "
                    "participation threshold."),
                "observation_type": "trade",
                "observations": _r1_trades(),
                "commission": {"model": "bps_of_notional", "value": 1.0},
                "spread": {"model": "fixed_bps", "value": 2.0, "fraction": 0.5},
                "slippage": {"model": "fixed_bps_per_side", "value": 1.0},
                "impact": {"model": "square_root", "coefficient": 0.1,
                           "participation_mode": "notional"},
                "liquidity": {
                    "adv_source": {"mode": "trailing_volume", "lookback": 20,
                                   "lag": 1, "unit": "currency"},
                    "volatility_source": {"mode": "trailing_returns",
                                          "lookback": 20, "lag": 1},
                    "series": _r1_series(),
                },
                "sensitivity_grid": {
                    "spread_multipliers": [0.5, 1.0, 2.0],
                    "slippage_multipliers": [1.0, 2.0],
                    "impact_multipliers": [1.0, 2.0],
                },
                "capacity_scales": [0.25, 0.5, 1.0, 2.0, 5.0],
                "dataset_version_id": version_demo_key_id(
                    "demo:dsv:kopep-features:v1"),
                "validation_run_id": validation_demo_id(
                    "demo:mv:purged-kfold-embargo"),
            },
            demo_key="demo:cd:complete-costs",
        )
        service.execute_run(run["id"], create_experiment=True)
        service.mark_baseline(run["id"])
        created += 1

    if store.run_demo_key_id("demo:cd:high-turnover-erosion") is not None:
        skipped += 1
    else:
        run = service.create_run(
            {
                "name": "High turnover erosion (bps commission)",
                "description": (
                    "Forty short-hold trades whose small gross edges sit "
                    "below the configured 8 bp commission + spread + "
                    "slippage stack: most gross-positive observations "
                    "become net-nonpositive."),
                "observation_type": "trade",
                "observations": _r2_trades(),
                "commission": {"model": "bps_of_notional", "value": 8.0},
                "spread": {"model": "fixed_bps", "value": 4.0, "fraction": 0.5},
                "slippage": {"model": "fixed_bps_per_side", "value": 2.0},
                "impact": {"model": "none"},
            },
            demo_key="demo:cd:high-turnover-erosion",
        )
        service.execute_run(run["id"])
        created += 1

    if store.run_demo_key_id("demo:cd:partial-missing-inputs") is not None:
        skipped += 1
    else:
        run = service.create_run(
            {
                "name": "Partial inputs (missing spread/ADV)",
                "description": (
                    "Supplied spread and ADV inputs exist for only part of "
                    "the sample: affected observations stay partial with "
                    "the missing components listed — never zero-filled."),
                "observation_type": "trade",
                "observations": _r3_trades(),
                "commission": {"model": "bps_of_notional", "value": 1.0},
                "spread": {"model": "supplied", "fraction": 0.5},
                "slippage": {"model": "none"},
                "impact": {"model": "square_root", "coefficient": 0.1,
                           "participation_mode": "quantity"},
            },
            demo_key="demo:cd:partial-missing-inputs",
        )
        service.execute_run(run["id"])
        created += 1

    if store.run_demo_key_id("demo:cd:fixed-fee-scaling") is not None:
        skipped += 1
    else:
        run = service.create_run(
            {
                "name": "Fixed per-order fee + integer contracts",
                "description": (
                    "Fixed 2.50 per order commission with tick-based spread "
                    "and slippage on a 5x multiplier instrument under an "
                    "integer-contract capacity policy: fixed fees stay "
                    "fixed while per-contract costs scale with quantity."),
                "observation_type": "trade",
                "observations": _r4_trades(),
                "tick_size": 0.25,
                "commission": {"model": "fixed_per_order", "value": 2.50},
                "spread": {"model": "fixed_ticks", "value": 2.0, "fraction": 0.5},
                "slippage": {"model": "fixed_ticks_per_side", "value": 1.0},
                "impact": {"model": "none"},
                "integer_contracts": True,
                "capacity_scales": [0.25, 0.5, 1.0, 2.0, 5.0],
            },
            demo_key="demo:cd:fixed-fee-scaling",
        )
        service.execute_run(run["id"])
        created += 1

    if store.run_demo_key_id("demo:cd:regime-linked") is not None:
        skipped += 1
    else:
        from app.regime_diagnostics.store import run_demo_key_id as regime_demo_id
        regime_run_id = regime_demo_id("demo:rd:volatility-trend")
        run = service.create_run(
            {
                "name": "Regime-linked period costs",
                "description": (
                    "Period observations on the Phase 54 demo timeline: "
                    "supplied spreads and trailing volatility are higher in "
                    "the high-volatility regime, so estimated costs differ "
                    "across the stored regime assignments."),
                "observation_type": "period",
                "observations": _r5_observations(),
                "commission": {"model": "none"},
                "spread": {"model": "supplied", "fraction": 0.5},
                "slippage": {"model": "none"},
                "impact": {"model": "square_root", "coefficient": 0.1,
                           "participation_mode": "notional"},
                "liquidity": {
                    "adv_source": {"mode": "trailing_volume", "lookback": 20,
                                   "lag": 1, "unit": "currency"},
                    "volatility_source": {"mode": "trailing_returns",
                                          "lookback": 20, "lag": 1},
                    "series": _r5_series(),
                },
                "regime_run_id": regime_run_id,
                "regime_definition_id": "vol",
            },
            demo_key="demo:cd:regime-linked",
        )
        service.execute_run(run["id"])
        created += 1

    if store.run_demo_key_id("demo:cd:invalid-future-looking") is not None:
        skipped += 1
    else:
        run = service.create_run(
            {
                "name": "Invalid future-looking ADV input",
                "description": (
                    "The supplied ADV claims a trailing basis with lag 0 — "
                    "a value computed through the execution period looks "
                    "ahead, so execution-input integrity is invalid and the "
                    "run cannot become a baseline."),
                "observation_type": "trade",
                "observations": _r6_trades(),
                "commission": {"model": "bps_of_notional", "value": 1.0},
                "spread": {"model": "none"},
                "slippage": {"model": "none"},
                "impact": {"model": "square_root", "coefficient": 0.2,
                           "participation_mode": "quantity"},
            },
            demo_key="demo:cd:invalid-future-looking",
        )
        service.execute_run(run["id"])
        created += 1

    return {"created_runs": created, "skipped_existing": skipped}
