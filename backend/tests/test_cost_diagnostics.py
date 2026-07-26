"""
Cost Diagnostics Lab tests (Phase 55.0): trade/period validation, unit
conversions from first principles, commission/spread/slippage/impact models
with hand-computed values, no-look-ahead liquidity inputs with adversarial
future-data mutation, gross-to-net reconciliation invariants, aggregates and
break-even diagnostics, sensitivity-grid bounds, capacity scaling with fixed
versus scalable fees and the integer-contract policy, participation
thresholds, regime integration on stored assignments, fingerprints,
persistence + migration, baselines, integrations, export privacy, demo
idempotence, and API happy/error paths.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta

import numpy as np
import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")
db_module = pytest.importorskip("app.db")
core = pytest.importorskip("app.cost_diagnostics.core")
units = pytest.importorskip("app.cost_diagnostics.units")
comp_mod = pytest.importorskip("app.cost_diagnostics.components")
impact_mod = pytest.importorskip("app.cost_diagnostics.impact")
liq_mod = pytest.importorskip("app.cost_diagnostics.liquidity")
rec_mod = pytest.importorskip("app.cost_diagnostics.reconcile")
agg_mod = pytest.importorskip("app.cost_diagnostics.aggregates")
scen_mod = pytest.importorskip("app.cost_diagnostics.scenarios")
fp_mod = pytest.importorskip("app.cost_diagnostics.fingerprints")
service = pytest.importorskip("app.cost_diagnostics.service")
cd_store = pytest.importorskip("app.cost_diagnostics.store")

BASE = "/cost-diagnostics"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_quantlab.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    yield


@pytest.fixture
def client():
    return TestClient(main_module.app)


def _ts(day, start=datetime(2024, 1, 1)):
    return (start + timedelta(days=day)).isoformat()


def _trade(i=0, *, cid="a", side="long", day=None, hold=2, entry=100.0,
           exit_price=None, qty=10.0, mult=1.0, **extra):
    day = i * 3 if day is None else day
    return {
        "trade_id": f"t{i:02d}", "candidate_id": cid, "side": side,
        "entry_timestamp": _ts(day), "exit_timestamp": _ts(day + hold),
        "entry_price": entry,
        "exit_price": entry * 1.01 if exit_price is None else exit_price,
        "quantity": qty, "contract_multiplier": mult, **extra,
    }


def _trades(n=4, **kw):
    return [_trade(i, **kw) for i in range(n)]


def _payload(**overrides):
    payload = {
        "name": "run", "observation_type": "trade",
        "observations": _trades(4),
        "commission": {"model": "bps_of_notional", "value": 2.0},
        "spread": {"model": "fixed_bps", "value": 2.0, "fraction": 0.5},
        "slippage": {"model": "fixed_bps_per_side", "value": 1.0},
        "impact": {"model": "none"},
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Observation validation
# ---------------------------------------------------------------------------


def test_trade_validation_and_deterministic_ordering():
    with pytest.raises(core.CostInputError, match="duplicate trade_id"):
        core.normalize_trades([_trade(0), _trade(0)])
    with pytest.raises(core.CostInputError, match="must be an object"):
        core.normalize_trades([_trade(0), "not-a-trade"])
    with pytest.raises(core.CostInputError, match="side"):
        core.normalize_trades([_trade(0, side="buy"), _trade(1)])
    with pytest.raises(core.CostInputError, match="before entry"):
        core.normalize_trades([_trade(0, day=5, hold=-3), _trade(1)])
    with pytest.raises(core.CostInputError, match="finite"):
        core.normalize_trades([_trade(0, entry=float("nan")), _trade(1)])
    with pytest.raises(core.CostInputError, match="mixed trade currencies"):
        core.normalize_trades([_trade(0, currency="USD"),
                               _trade(1, currency="EUR")])
    # deterministic ordering by (entry_timestamp, trade_id), multiplier echoed
    trades, currency = core.normalize_trades([_trade(1, day=9), _trade(0, day=3)])
    assert [t["trade_id"] for t in trades] == ["t00", "t01"]
    assert currency == "USD"
    assert trades[0]["contract_multiplier"] == 1.0  # explicit, never hidden

    # gross pnl derived from prices when absent, supplied wins when present
    t = core.normalize_trades([_trade(0, entry=100.0, exit_price=102.0,
                                      qty=5.0), _trade(1)])[0][0]
    assert t["gross_pnl"] == pytest.approx(2.0 * 5.0)
    assert t["gross_pnl_source"] == "derived_from_prices"
    t2 = core.normalize_trades([_trade(0, gross_pnl=7.5), _trade(1)])[0][0]
    assert t2["gross_pnl"] == 7.5 and t2["gross_pnl_source"] == "supplied"
    assert t2["input_warnings"]  # differs from the price-derived value
    # short side: pnl = -(exit-entry)*qty*mult
    s = core.normalize_trades([_trade(0, side="short", entry=100.0,
                                      exit_price=98.0, qty=3.0), _trade(1)])[0][0]
    assert s["gross_pnl"] == pytest.approx(6.0)


def test_timestamp_and_tz_validation():
    with pytest.raises(core.CostInputError, match="ISO-8601"):
        core.normalize_trades([_trade(0, entry_timestamp="not-a-date"),
                               _trade(1)])
    bad = _trade(0)
    bad["entry_timestamp"] = "2024-01-01T00:00:00+00:00"
    with pytest.raises(core.CostInputError, match="timezone"):
        core.normalize_trades([bad, _trade(1)])


def test_period_observation_validation():
    def obs(i, **extra):
        return {"observation_id": f"p{i}", "candidate_id": "a",
                "timestamp": _ts(i), "gross_return": 0.001, **extra}
    with pytest.raises(core.CostInputError, match="duplicate observation_id"):
        core.normalize_period_observations([obs(0), obs(0)])
    with pytest.raises(core.CostInputError, match=">= 0"):
        core.normalize_period_observations([obs(0, turnover=-0.5), obs(1)])
    with pytest.raises(core.CostInputError, match="finite"):
        core.normalize_period_observations(
            [obs(0, gross_return=float("inf")), obs(1)])
    rows = core.normalize_period_observations([obs(1), obs(0)])
    assert [r["observation_id"] for r in rows] == ["p0", "p1"]


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------


def test_unit_conversions_hand_computed():
    # 1 bp = 0.0001 of notional
    r = units.normalize_cost_amount(3.0, "bps_of_notional", notional=50_000.0)
    assert r["amount"] == pytest.approx(3.0 * 0.0001 * 50_000.0)  # 15.0
    r = units.normalize_cost_amount(0.5, "percent_of_notional", notional=10_000.0)
    assert r["amount"] == pytest.approx(50.0)
    r = units.normalize_cost_amount(2.0, "ticks", quantity=4.0,
                                    contract_multiplier=5.0, tick_size=0.25)
    assert r["amount"] == pytest.approx(2.0 * 0.25 * 4.0 * 5.0)  # 10.0
    r = units.normalize_cost_amount(0.05, "price_units", quantity=10.0,
                                    contract_multiplier=2.0)
    assert r["amount"] == pytest.approx(1.0)
    r = units.normalize_cost_amount(1.25, "currency_per_contract", quantity=8.0)
    assert r["amount"] == pytest.approx(10.0)
    r = units.normalize_cost_amount(2.5, "currency_per_order", order_count=3)
    assert r["amount"] == pytest.approx(7.5)
    r = units.normalize_cost_amount(9.0, "currency_per_trade")
    assert r["amount"] == pytest.approx(9.0)
    # missing context is unavailable with a reason — never zero
    r = units.normalize_cost_amount(2.0, "ticks", quantity=4.0,
                                    contract_multiplier=5.0)
    assert r["status"] == "unavailable" and "tick_size" in r["reason"]
    r = units.normalize_cost_amount(1.0, "bps_of_notional")
    assert r["status"] == "unavailable"
    assert units.normalize_cost_amount(1.0, "made_up")["status"] == "unavailable"


def test_spread_to_price_conversions():
    assert units.spread_to_price(0.5, "price")["amount"] == 0.5
    assert units.spread_to_price(2.0, "ticks", tick_size=0.25)["amount"] == 0.5
    assert units.spread_to_price(4.0, "bps", mid_price=100.0)["amount"] == \
        pytest.approx(0.04)
    assert units.spread_to_price(-1.0, "price")["status"] == "unavailable"
    assert units.spread_to_price(2.0, "ticks")["status"] == "unavailable"


# ---------------------------------------------------------------------------
# Commission
# ---------------------------------------------------------------------------


def test_commission_models_hand_computed():
    trades, _ = core.normalize_trades(
        [_trade(0, entry=100.0, exit_price=101.0, qty=10.0, mult=2.0),
         _trade(1)])
    t = trades[0]  # entry notional 2000, exit notional 2020, traded 4020
    cfg = comp_mod.validate_commission_config(
        {"model": "fixed_per_order", "value": 2.5, "entry_orders": 2,
         "exit_orders": 1}, "trade")
    assert comp_mod.compute_commission(t, cfg, "trade")["amount"] == \
        pytest.approx(7.5)
    cfg = comp_mod.validate_commission_config(
        {"model": "fixed_per_trade", "value": 4.0}, "trade")
    assert comp_mod.compute_commission(t, cfg, "trade")["amount"] == 4.0
    # per-contract charges each side: value * qty * 2
    cfg = comp_mod.validate_commission_config(
        {"model": "per_contract", "value": 1.1}, "trade")
    assert comp_mod.compute_commission(t, cfg, "trade")["amount"] == \
        pytest.approx(22.0)
    # bps is a per-side rate on each side's notional == bps on traded notional
    cfg = comp_mod.validate_commission_config(
        {"model": "bps_of_notional", "value": 5.0}, "trade")
    assert comp_mod.compute_commission(t, cfg, "trade")["amount"] == \
        pytest.approx(5.0 * 0.0001 * 4020.0)
    # minimum floor applied first, then maximum cap
    cfg = comp_mod.validate_commission_config(
        {"model": "bps_of_notional", "value": 5.0, "minimum": 10.0,
         "maximum": 12.0}, "trade")
    assert comp_mod.compute_commission(t, cfg, "trade")["amount"] == 10.0
    cfg = comp_mod.validate_commission_config(
        {"model": "bps_of_notional", "value": 500.0, "minimum": 10.0,
         "maximum": 12.0}, "trade")
    assert comp_mod.compute_commission(t, cfg, "trade")["amount"] == 12.0
    with pytest.raises(core.CostInputError, match="maximum must be >= minimum"):
        comp_mod.validate_commission_config(
            {"model": "fixed_per_trade", "value": 1.0, "minimum": 5.0,
             "maximum": 2.0}, "trade")
    with pytest.raises(core.CostInputError, match="negative fees are rejected"):
        comp_mod.validate_commission_config(
            {"model": "fixed_per_trade", "value": -1.0}, "trade")
    # zero is allowed
    cfg = comp_mod.validate_commission_config(
        {"model": "fixed_per_trade", "value": 0.0}, "trade")
    assert comp_mod.compute_commission(t, cfg, "trade")["amount"] == 0.0
    # period runs support only turnover-proportional commission
    with pytest.raises(core.CostInputError, match="period observations"):
        comp_mod.validate_commission_config(
            {"model": "fixed_per_order", "value": 1.0}, "period")


# ---------------------------------------------------------------------------
# Spread
# ---------------------------------------------------------------------------


def test_spread_fraction_explicit_and_sides():
    with pytest.raises(core.CostInputError, match="fraction must be configured"):
        comp_mod.validate_spread_config({"model": "fixed_bps", "value": 2.0},
                                        "trade")
    with pytest.raises(core.CostInputError, match="\\[0, 1\\]"):
        comp_mod.validate_spread_config(
            {"model": "fixed_bps", "value": 2.0, "fraction": 1.5}, "trade")
    trades, _ = core.normalize_trades(
        [_trade(0, entry=100.0, exit_price=102.0, qty=10.0), _trade(1)])
    t = trades[0]
    cfg = comp_mod.validate_spread_config(
        {"model": "fixed_bps", "value": 4.0, "fraction": 0.5}, "trade")
    # per side: 0.5 * (4bp of side price) * qty; entry 100, exit 102
    expected = 0.5 * 4.0 * 0.0001 * 100.0 * 10.0 + \
        0.5 * 4.0 * 0.0001 * 102.0 * 10.0
    assert comp_mod.compute_spread_cost(t, cfg, "trade", None)["amount"] == \
        pytest.approx(expected)
    cfg_entry = comp_mod.validate_spread_config(
        {"model": "fixed_bps", "value": 4.0, "fraction": 0.5,
         "sides": "entry_only"}, "trade")
    assert comp_mod.compute_spread_cost(t, cfg_entry, "trade", None)["amount"] == \
        pytest.approx(0.5 * 4.0 * 0.0001 * 100.0 * 10.0)
    # supplied spread missing stays unavailable — never zero
    cfg_sup = comp_mod.validate_spread_config(
        {"model": "supplied", "fraction": 0.5}, "trade")
    r = comp_mod.compute_spread_cost(t, cfg_sup, "trade", None)
    assert r["status"] == "unavailable" and r["amount"] is None
    # supplied tick spread converts through tick size
    trades2, _ = core.normalize_trades(
        [_trade(0, qty=10.0,
                cost_inputs={"spread": {"value": 2.0, "unit": "ticks",
                                        "basis": "declared"}}),
         _trade(1)])
    r2 = comp_mod.compute_spread_cost(trades2[0], cfg_sup, "trade", 0.25)
    # 0.5 fraction * (2 ticks * 0.25) * qty 10 * mult 1 per side, both sides
    assert r2["amount"] == pytest.approx(0.5 * 0.5 * 10.0 * 2)


# ---------------------------------------------------------------------------
# Slippage
# ---------------------------------------------------------------------------


def test_slippage_models_stress_and_realized():
    trades, _ = core.normalize_trades(
        [_trade(0, entry=100.0, exit_price=101.0, qty=10.0), _trade(1)])
    t = trades[0]  # traded notional 2010
    cfg = comp_mod.validate_slippage_config(
        {"model": "fixed_bps_per_side", "value": 2.0,
         "stress_multiplier": 3.0}, "trade")
    r = comp_mod.compute_slippage(t, cfg, "trade", None)
    assert r["modelled_amount"] == pytest.approx(2.0 * 0.0001 * 2010.0)
    assert r["amount"] == pytest.approx(r["modelled_amount"] * 3.0)
    with pytest.raises(core.CostInputError, match="favourable"):
        comp_mod.validate_slippage_config(
            {"model": "fixed_bps_per_side", "value": 2.0,
             "stress_multiplier": 0.5}, "trade")
    with pytest.raises(core.CostInputError, match=">= 0"):
        comp_mod.validate_slippage_config(
            {"model": "fixed_bps_per_side", "value": -2.0}, "trade")
    # ticks and price units per side (x2 sides)
    cfg_t = comp_mod.validate_slippage_config(
        {"model": "fixed_ticks_per_side", "value": 2.0}, "trade")
    assert comp_mod.compute_slippage(t, cfg_t, "trade", 0.25)["amount"] == \
        pytest.approx(2.0 * 0.25 * 10.0 * 2)
    # supplied realized may be favourable (negative) and ignores stress
    trades2, _ = core.normalize_trades(
        [_trade(0, cost_inputs={"realized_slippage": {"value": -1.25}}),
         _trade(1)])
    cfg_r = comp_mod.validate_slippage_config(
        {"model": "supplied_realized", "stress_multiplier": 5.0}, "trade")
    r2 = comp_mod.compute_slippage(trades2[0], cfg_r, "trade", None)
    assert r2["amount"] == -1.25 and r2["source"] == "supplied_realized"
    # missing realized slippage stays unavailable
    r3 = comp_mod.compute_slippage(trades2[1] if len(trades2) > 1 else t,
                                   cfg_r, "trade", None)
    assert r3["status"] == "unavailable"


# ---------------------------------------------------------------------------
# Impact + participation
# ---------------------------------------------------------------------------


def test_impact_square_root_hand_computed():
    trades, _ = core.normalize_trades(
        [_trade(0, entry=100.0, exit_price=100.0, qty=10.0,
                cost_inputs={"adv": {"value": 4000.0, "unit": "currency",
                                     "basis": "declared"},
                             "volatility": {"value": 0.02,
                                            "basis": "declared"}}),
         _trade(1)])
    t = trades[0]  # each side notional 1000
    cfg = impact_mod.validate_impact_config(
        {"model": "square_root", "coefficient": 0.1,
         "participation_mode": "notional"}, "trade")
    r = impact_mod.compute_impact(t, cfg, "trade", None, None)
    part = 1000.0 / 4000.0
    per_side = 0.1 * 0.02 * math.sqrt(part) * 1000.0
    assert r["amount"] == pytest.approx(2 * per_side)
    assert r["participation"] == pytest.approx(part)
    assert r["amount"] >= 0
    # explicit participation_mode is required
    with pytest.raises(core.CostInputError, match="explicit, no default"):
        impact_mod.validate_impact_config(
            {"model": "square_root", "coefficient": 0.1}, "trade")
    with pytest.raises(core.CostInputError, match="coefficient"):
        impact_mod.validate_impact_config(
            {"model": "square_root", "participation_mode": "notional"},
            "trade")
    # fixed_bps alternative
    cfg_f = impact_mod.validate_impact_config(
        {"model": "fixed_bps", "value": 3.0}, "trade")
    assert impact_mod.compute_impact(t, cfg_f, "trade", None, None)["amount"] \
        == pytest.approx(3.0 * 0.0001 * 2000.0)
    # ADV unit mismatch is unavailable — never silently converted
    cfg_q = impact_mod.validate_impact_config(
        {"model": "square_root", "coefficient": 0.1,
         "participation_mode": "quantity"}, "trade")
    r_mismatch = impact_mod.compute_impact(t, cfg_q, "trade", None, None)
    assert r_mismatch["status"] == "unavailable"
    assert "units" in r_mismatch["reason"]


def test_impact_missing_inputs_and_zero_participation():
    trades, _ = core.normalize_trades(_trades(2))
    cfg = impact_mod.validate_impact_config(
        {"model": "square_root", "coefficient": 0.1,
         "participation_mode": "notional"}, "trade")
    r = impact_mod.compute_impact(trades[0], cfg, "trade", None, None)
    assert r["status"] == "unavailable" and r["amount"] is None
    assert "volatility" in r["reason"]
    r2 = impact_mod.compute_impact(trades[0], cfg, "trade", None, 0.02)
    assert r2["status"] == "unavailable" and "ADV" in r2["reason"]
    # zero participation (period turnover 0) gives zero impact
    obs = core.normalize_period_observations(
        [{"observation_id": "p0", "candidate_id": "a", "timestamp": _ts(0),
          "gross_return": 0.001, "turnover": 0.0, "traded_notional": 0.0},
         {"observation_id": "p1", "candidate_id": "a", "timestamp": _ts(1),
          "gross_return": 0.001, "turnover": 0.5, "traded_notional": 1000.0}])
    cfg_p = impact_mod.validate_impact_config(
        {"model": "square_root", "coefficient": 0.1,
         "participation_mode": "notional"}, "period")
    r0 = impact_mod.compute_impact(obs[0], cfg_p, "period", 5000.0, 0.02)
    assert r0["amount"] == 0.0 and r0["participation"] == 0.0


def test_participation_thresholds_and_warning():
    trades, _ = core.normalize_trades(
        [_trade(0, entry=100.0, exit_price=100.0, qty=10.0), _trade(1)])
    t = trades[0]  # side notional 1000
    rec = impact_mod.participation_record(t, "trade", 2000.0, "notional", 0.25)
    assert rec["participation"] == pytest.approx(0.5)
    assert rec["status"] == "above_configured_threshold"
    assert rec["warning"] is None
    rec2 = impact_mod.participation_record(t, "trade", 800.0, "notional", 0.25)
    assert rec2["participation"] == pytest.approx(1.25)
    assert "100%" in rec2["warning"]  # visible, warning-level, not rejected
    rec3 = impact_mod.participation_record(t, "trade", None, "notional", 0.25)
    assert rec3["status"] == "unavailable"
    assert impact_mod.participation_record(t, "trade", 2000.0, None, 0.25)[
        "status"] == "unavailable"
    with pytest.raises(core.CostInputError):
        impact_mod.validate_participation_threshold(99.0)
    assert impact_mod.validate_participation_threshold(None) == \
        impact_mod.DEFAULT_PARTICIPATION_THRESHOLD


# ---------------------------------------------------------------------------
# No-look-ahead liquidity inputs
# ---------------------------------------------------------------------------


def test_trailing_derivation_no_lookahead_mutation():
    values = [float(v) for v in range(100)]
    derived = liq_mod.derive_trailing(values, lookback=5, lag=2, stat="mean")
    # derived[j] uses values[j-6 .. j-2]; hand-check j=10: mean(4..8) = 6
    assert derived[10] == pytest.approx(6.0)
    assert derived[5] is None and derived[6] is not None  # min history
    # adversarial mutation: change every value after j - lag; derived[j]
    # must not move
    j = 40
    mutated = list(values)
    for k in range(j - 2 + 1, len(mutated)):
        mutated[k] = 1e9
    derived_m = liq_mod.derive_trailing(mutated, lookback=5, lag=2, stat="mean")
    assert derived_m[j] == derived[j]
    # std uses ddof=1 and needs lookback >= 2
    d_std = liq_mod.derive_trailing([1.0, 2.0, 3.0, 4.0, 5.0], 3, 1, "std")
    assert d_std[4] == pytest.approx(float(np.std([2.0, 3.0, 4.0], ddof=1)))
    with pytest.raises(liq_mod.LiquidityInputError):
        liq_mod.derive_trailing(values, lookback=1, lag=1, stat="std")
    with pytest.raises(liq_mod.LiquidityInputError):
        liq_mod.derive_trailing(values, lookback=5, lag=0, stat="mean")
    # exact-match alignment only — unknown timestamps unavailable
    mapped = liq_mod.map_series_to_observations(
        ["a", "b", "c"], [1.0, 2.0, 3.0], ["b", "zz"])
    assert mapped == [2.0, None]


def test_liquidity_provenance_classification():
    c = liq_mod.classify_supplied_input
    assert c({"basis": "supplied_realized"}, dataset_linked=False)[
        "integrity"] == "supplied_realized"
    assert c({"basis": "trailing", "lag": 1, "lookback": 10},
             dataset_linked=False)["integrity"] == "verified_causal_input"
    assert c({"basis": "trailing", "lag": 0, "lookback": 10},
             dataset_linked=False)["integrity"] == "invalid"
    assert c({"basis": "trailing", "lag": -1, "lookback": 10},
             dataset_linked=False)["integrity"] == "invalid"
    assert c({"basis": "declared", "window": "centered"},
             dataset_linked=False)["integrity"] == "invalid"
    r = c({"basis": "dataset_lineage"}, dataset_linked=False)
    assert r["integrity"] == "declared" and r["warnings"]
    assert c({"basis": "dataset_lineage"}, dataset_linked=True)[
        "integrity"] == "verified_from_dataset_lineage"
    fs = c({"basis": "full_sample"}, dataset_linked=False)
    assert fs["integrity"] == "full_sample_descriptive"
    assert any("never" in w for w in fs["warnings"])
    assert c({}, dataset_linked=False)["integrity"] == "unknown"
    # trust order: least trusted wins; empty defaults to declared
    assert liq_mod.least_trusted(
        ["supplied_realized", "declared", "unknown"]) == "unknown"
    assert liq_mod.least_trusted([]) == "declared"


# ---------------------------------------------------------------------------
# Reconciliation + aggregates + break-even
# ---------------------------------------------------------------------------


def test_reconciliation_invariants_and_completeness():
    A = {"status": "available", "amount": 2.0}
    U = {"status": "unavailable", "amount": None, "reason": "missing"}
    N = {"status": "not_configured", "amount": None}
    r = rec_mod.reconcile_observation(10.0, {
        "commission": A, "spread": {"status": "available", "amount": 1.5},
        "slippage": N, "impact": N})
    assert r["total_cost"] == pytest.approx(3.5)
    assert r["net_value"] == pytest.approx(6.5)
    assert r["completeness"] == "complete"
    p = rec_mod.reconcile_observation(10.0, {
        "commission": A, "spread": U, "slippage": N, "impact": N})
    assert p["completeness"] == "partial"
    assert p["unavailable_components"] == ["spread"]
    assert p["net_value"] == pytest.approx(8.0)  # excludes missing, disclosed
    g = rec_mod.reconcile_observation(10.0, {
        "commission": U, "spread": U, "slippage": N, "impact": N})
    assert g["completeness"] == "gross_only" and g["net_value"] is None
    none_cfg = rec_mod.reconcile_observation(10.0, {
        "commission": N, "spread": N, "slippage": N, "impact": N})
    assert none_cfg["completeness"] == "gross_only"
    assert rec_mod.run_completeness(["complete", "complete"]) == "complete"
    assert rec_mod.run_completeness(["complete", "partial"]) == "partial"
    assert rec_mod.run_completeness(["gross_only"]) == "gross_only"
    assert rec_mod.run_completeness(["complete", "invalid"]) == "invalid"
    assert rec_mod.run_completeness([]) == "invalid"


def _obs_result(oid, gross, comps, notional=1000.0):
    values = {n: comps.get(n) for n in ("commission", "spread", "slippage",
                                        "impact")}
    available = {n: v for n, v in values.items() if v is not None}
    total = sum(available.values()) if available else None
    return {
        "observation_id": oid, "candidate_id": "a", "timestamp": _ts(0),
        "gross_value": gross, "component_values": values,
        "total_cost": total,
        "net_value": (gross - total) if total is not None else None,
        "completeness": "complete" if available else "gross_only",
        "unavailable_components": [], "traded_notional": notional,
        "turnover": None, "participation": None,
    }


def test_aggregates_hand_computed():
    rows = [
        _obs_result("a", 10.0, {"commission": 2.0}),
        _obs_result("b", -4.0, {"commission": 1.0}),
        _obs_result("c", 3.0, {"commission": 3.5}),
    ]
    agg = agg_mod.aggregate_results(rows)
    assert agg["gross_total"] == pytest.approx(9.0)
    assert agg["total_cost"] == pytest.approx(6.5)
    assert agg["net_total"] == pytest.approx(2.5)
    # by hand: a net 8.0 (positive), b gross negative, c net -0.5 → count 1
    assert agg["gross_positive_net_nonpositive_count"] == 1
    assert agg["gross_positive_net_nonpositive_count"] == \
        sum(1 for r in rows if r["gross_value"] > 0 and r["net_value"] <= 0)
    assert agg["gross_stats"]["mean"] == pytest.approx(3.0)
    assert agg["gross_stats"]["std"] == pytest.approx(
        float(np.std([10.0, -4.0, 3.0], ddof=1)))
    assert agg["gross_stats"]["sharpe_like"] == pytest.approx(
        3.0 / float(np.std([10.0, -4.0, 3.0], ddof=1)))
    assert agg["cost_fraction_of_gross_magnitude"] == pytest.approx(6.5 / 9.0)
    assert agg["cost_fraction_of_traded_notional"] == pytest.approx(6.5 / 3000.0)
    # zero gross total → fraction unavailable, no division by zero
    zero = agg_mod.aggregate_results(
        [_obs_result("a", 5.0, {"commission": 1.0}),
         _obs_result("b", -5.0, {"commission": 1.0})])
    assert zero["cost_fraction_of_gross_magnitude"] is None


def test_breakeven_diagnostics_hand_computed():
    rows = [_obs_result("a", 10.0, {"commission": 2.0, "spread": 1.0}),
            _obs_result("b", 6.0, {"commission": 2.0, "spread": 1.0})]
    agg = agg_mod.aggregate_results(rows)
    be = agg_mod.breakeven_diagnostics(agg, impact_coefficient=None)
    assert be["status"] == "available"
    # gross 16, notional 2000, bps = 16/2000/0.0001 = 80
    assert be["aggregate_breakeven_bps_of_notional"] == pytest.approx(80.0)
    assert be["mean_breakeven_cost_per_observation"] == pytest.approx(8.0)
    assert be["max_cost_multiplier"] == pytest.approx(16.0 / 6.0)
    m = be["component_breakeven_multipliers"]
    # commission base 4, others 2: (16-2)/4 = 3.5
    assert m["commission"]["multiplier"] == pytest.approx(3.5)
    # spread base 2, others 4: (16-4)/2 = 6.0
    assert m["spread"]["multiplier"] == pytest.approx(6.0)
    assert m["impact"] is None
    # nonpositive gross → unavailable, never a negative break-even
    neg = agg_mod.aggregate_results([_obs_result("a", -1.0, {"commission": 1.0}),
                                     _obs_result("b", 0.5, {"commission": 1.0})])
    assert agg_mod.breakeven_diagnostics(neg, None)["status"] == "unavailable"
    # other components already exceeding gross → honest unavailable
    rows2 = [_obs_result("a", 3.0, {"commission": 1.0, "spread": 5.0})]
    be2 = agg_mod.breakeven_diagnostics(agg_mod.aggregate_results(rows2), None)
    assert be2["component_breakeven_multipliers"]["commission"]["multiplier"] is None


def test_aggregate_reconciles_over_costed_subset_with_gross_only():
    # A gross_only observation contributes gross but neither cost nor net; the
    # published triple net_total == gross_total_costed - total_cost must hold
    # over the COSTED subset, never over the whole-run gross (which would leave
    # net_total unreconcilable against gross_total - total_cost).
    costed = _obs_result("a", 100.0, {"commission": 20.0}, notional=1000.0)
    gross_only = _obs_result("b", 1000.0, {}, notional=5000.0)
    assert gross_only["net_value"] is None  # helper builds a true gross_only row
    agg = agg_mod.aggregate_results([costed, gross_only])
    assert agg["gross_total"] == pytest.approx(1100.0)      # whole run
    assert agg["gross_total_costed"] == pytest.approx(100.0)  # costed subset
    assert agg["total_cost"] == pytest.approx(20.0)
    assert agg["net_total"] == pytest.approx(80.0)
    # the identity reconciles against the costed gross, NOT the whole-run gross
    assert agg["net_total"] == pytest.approx(
        agg["gross_total_costed"] - agg["total_cost"])
    assert agg["net_total"] != pytest.approx(
        agg["gross_total"] - agg["total_cost"])
    # cost ratios pair the costed cost with the costed gross / notional
    assert agg["cost_fraction_of_gross_magnitude"] == pytest.approx(20.0 / 100.0)
    assert agg["cost_fraction_of_traded_notional"] == pytest.approx(20.0 / 1000.0)
    # break-even uses the costed gross and the costed observation count
    be = agg_mod.breakeven_diagnostics(agg, impact_coefficient=None)
    assert be["mean_breakeven_cost_per_observation"] == pytest.approx(100.0)
    assert be["max_cost_multiplier"] == pytest.approx(100.0 / 20.0)
    # when every observation is costed the costed gross equals the whole gross
    full = agg_mod.aggregate_results([costed, _obs_result("c", 40.0,
                                                          {"commission": 5.0})])
    assert full["gross_total_costed"] == pytest.approx(full["gross_total"])


def test_aggregate_identity_period_type_with_gross_only():
    # period runs pair the turnover basis with the costed subset; a gross_only
    # period observation must not leak its gross or turnover into the reconciled
    # net / break-even basis.
    def prow(oid, gross, comps, turnover):
        vals = {n: comps.get(n) for n in ("commission", "spread",
                                          "slippage", "impact")}
        avail = {n: v for n, v in vals.items() if v is not None}
        total = sum(avail.values()) if avail else None
        return {
            "observation_id": oid, "candidate_id": "a", "timestamp": _ts(0),
            "gross_value": gross, "component_values": vals,
            "total_cost": total,
            "net_value": (gross - total) if total is not None else None,
            "completeness": "complete" if avail else "gross_only",
            "unavailable_components": [], "traded_notional": None,
            "turnover": turnover, "participation": None,
        }
    rows = [prow("a", 0.01, {"commission": 0.002}, 0.5),
            prow("b", 0.05, {}, 0.4)]  # b is gross_only
    agg = agg_mod.aggregate_results(rows, observation_type="period")
    assert agg["gross_total"] == pytest.approx(0.06)
    assert agg["gross_total_costed"] == pytest.approx(0.01)
    assert agg["total_cost"] == pytest.approx(0.002)
    assert agg["net_total"] == pytest.approx(0.008)
    assert agg["net_total"] == pytest.approx(
        agg["gross_total_costed"] - agg["total_cost"])
    # basis is the COSTED turnover (0.5), never the gross_only obs's 0.4
    assert agg["notional_basis_total"] == pytest.approx(0.5)
    be = agg_mod.breakeven_diagnostics(agg, impact_coefficient=None)
    assert be["status"] == "available"
    # 0.01 / 0.5 / 0.0001 = 200 bps; mean over the single costed obs = 0.01
    assert be["aggregate_breakeven_bps_of_notional"] == pytest.approx(200.0)
    assert be["mean_breakeven_cost_per_observation"] == pytest.approx(0.01)


def test_aggregate_identity_partial_completeness():
    # a PARTIAL observation (some components unavailable) stays costed; the
    # identity holds over the costed set and break-even's per-component "others"
    # math must handle an unavailable component correctly.
    partial = _obs_result("p", 100.0, {"commission": 10.0})
    partial["unavailable_components"] = ["spread"]
    partial["completeness"] = "partial"
    complete = _obs_result("c", 50.0, {"commission": 5.0, "spread": 2.0})
    agg = agg_mod.aggregate_results([partial, complete])
    assert agg["partial_result_count"] == 1
    assert agg["gross_total_costed"] == pytest.approx(150.0)
    assert agg["total_cost"] == pytest.approx(17.0)  # 10 + 5 + 2
    assert agg["net_total"] == pytest.approx(133.0)
    assert agg["net_total"] == pytest.approx(
        agg["gross_total_costed"] - agg["total_cost"])
    be = agg_mod.breakeven_diagnostics(agg, impact_coefficient=None)
    # commission base 15, others = spread 2: (150 - 2) / 15
    assert be["component_breakeven_multipliers"]["commission"]["multiplier"] \
        == pytest.approx((150.0 - 2.0) / 15.0)


# ---------------------------------------------------------------------------
# Sensitivity + capacity
# ---------------------------------------------------------------------------


def test_sensitivity_grid_bounds_and_evaluation():
    grid = scen_mod.validate_sensitivity_grid(
        {"spread_multipliers": [2.0, 0.5, 1.0, 0.5]})
    assert grid["spread_multipliers"] == [0.5, 1.0, 2.0]  # deduped + sorted
    with pytest.raises(core.CostInputError, match="at most"):
        scen_mod.validate_sensitivity_grid(
            {"spread_multipliers": [1, 2, 3, 4, 5, 6]})
    with pytest.raises(core.CostInputError, match="scenarios"):
        scen_mod.validate_sensitivity_grid(
            {"commission_multipliers": [1, 2, 3, 4],
             "spread_multipliers": [1, 2, 3, 4],
             "slippage_multipliers": [1, 2, 3, 4]})
    scenarios = scen_mod.build_scenarios(scen_mod.validate_sensitivity_grid(
        {"spread_multipliers": [0.5, 2.0]}))
    assert sum(1 for s in scenarios if s["is_base"]) == 1  # base injected
    assert len(scenarios) == 3
    rows = [_obs_result("a", 10.0, {"commission": 2.0, "spread": 1.0}),
            _obs_result("b", 2.0, {"commission": 2.0, "spread": 1.0})]
    hi = scen_mod.evaluate_scenario(rows, {
        "commission_multiplier": 1.0, "spread_multiplier": 2.0,
        "slippage_multiplier": 1.0, "impact_multiplier": 1.0,
        "is_base": False})
    assert hi["total_cost"] == pytest.approx(2 * (2.0 + 2.0))
    assert hi["net_total"] == pytest.approx(12.0 - 8.0)
    assert hi["gross_positive_net_nonpositive_count"] == 1  # b: 2 - 4 <= 0


def test_capacity_scaling_fixed_vs_scalable_fees(client):
    payload = _payload(
        observations=_trades(4, qty=10.0),
        commission={"model": "fixed_per_order", "value": 2.0},
        spread={"model": "fixed_bps", "value": 2.0, "fraction": 0.5},
        slippage={"model": "none"}, impact={"model": "none"},
        capacity_scales=[0.5, 1.0, 2.0])
    run = service.create_run(payload)
    service.execute_run(run["id"])
    cap = cd_store.list_capacity_results(run["id"])
    by_scale = {c["scale"]: c for c in cap}
    # fixed per-order fees do not scale with size
    assert by_scale[0.5]["commission_total"] == by_scale[2.0]["commission_total"]
    assert by_scale[1.0]["commission_total"] == pytest.approx(4 * 2.0 * 2)
    # bps spread cost scales linearly with notional
    assert by_scale[2.0]["spread_total"] == pytest.approx(
        2 * by_scale[1.0]["spread_total"])
    assert by_scale[0.5]["spread_total"] == pytest.approx(
        0.5 * by_scale[1.0]["spread_total"])
    # gross scales with size; base row marked
    assert by_scale[2.0]["gross_total"] == pytest.approx(
        2 * by_scale[1.0]["gross_total"])
    assert by_scale[1.0]["is_base"] is True


def test_impact_superlinear_capacity_and_participation():
    trades = [_trade(i, qty=10.0, entry=100.0, exit_price=101.0,
                     cost_inputs={"adv": {"value": 20_000.0, "unit": "currency",
                                          "basis": "declared"},
                                  "volatility": {"value": 0.02,
                                                 "basis": "declared"}})
              for i in range(3)]
    run = service.create_run(_payload(
        observations=trades,
        commission={"model": "none"}, spread={"model": "none"},
        slippage={"model": "none"},
        impact={"model": "square_root", "coefficient": 0.1,
                "participation_mode": "notional"},
        capacity_scales=[1.0, 4.0]))
    service.execute_run(run["id"])
    cap = {c["scale"]: c for c in cd_store.list_capacity_results(run["id"])}
    # sqrt impact: cost scales as s^1.5 → 4x notional = 8x impact
    assert cap[4.0]["impact_total"] == pytest.approx(
        8.0 * cap[1.0]["impact_total"], rel=1e-9)
    assert cap[4.0]["max_participation"] == pytest.approx(
        4.0 * cap[1.0]["max_participation"], rel=1e-9)


def test_integer_contract_policy():
    trades = [_trade(i, qty=float(1 + i % 2), entry=100.0, exit_price=101.0)
              for i in range(4)]  # quantities 1, 2, 1, 2
    run = service.create_run(_payload(
        observations=trades, integer_contracts=True,
        capacity_scales=[0.25, 0.5, 1.0]))
    service.execute_run(run["id"])
    cap = {c["scale"]: c for c in cd_store.list_capacity_results(run["id"])}
    assert cap[0.25]["excluded_count"] == 4       # all floor to zero
    assert cap[0.5]["excluded_count"] == 2        # the qty-1 trades floor to 0
    assert cap[1.0]["excluded_count"] == 0
    with pytest.raises(service.CostDiagnosticsError, match="trade observations"):
        service.create_run(_payload(
            observation_type="period", integer_contracts=True,
            observations=[{"observation_id": "p0", "candidate_id": "a",
                           "timestamp": _ts(0), "gross_return": 0.001},
                          {"observation_id": "p1", "candidate_id": "a",
                           "timestamp": _ts(1), "gross_return": 0.001}],
            commission={"model": "none"}, spread={"model": "none"},
            slippage={"model": "none"}))


# ---------------------------------------------------------------------------
# Service-level no-look-ahead: future mutation invariance
# ---------------------------------------------------------------------------


def _series(n=60, volume_tail=None):
    rng = np.random.default_rng(7)
    volume = [round(float(v), 4) for v in rng.normal(50_000.0, 1_000.0, n)]
    returns = [round(float(v), 8) for v in rng.normal(0.0, 0.01, n)]
    if volume_tail is not None:
        for k in range(45, n):
            volume[k] = volume_tail
            returns[k] = 0.5
    return {"timestamps": [_ts(i) for i in range(n)],
            "volume": volume, "returns": returns}


def test_future_series_mutation_does_not_change_costs():
    trades = [_trade(i, day=30 + i * 2, qty=10.0) for i in range(5)]
    base_cfg = dict(
        observations=trades,
        commission={"model": "none"}, spread={"model": "none"},
        slippage={"model": "none"},
        impact={"model": "square_root", "coefficient": 0.1,
                "participation_mode": "notional"},
        liquidity={
            "adv_source": {"mode": "trailing_volume", "lookback": 10,
                           "lag": 1, "unit": "currency"},
            "volatility_source": {"mode": "trailing_returns", "lookback": 10,
                                  "lag": 1},
            "series": _series()},
    )
    run_a = service.create_run(_payload(**base_cfg))
    service.execute_run(run_a["id"])
    # mutate the series strictly after every observation's permitted window
    mutated = dict(base_cfg)
    mutated["liquidity"] = {**base_cfg["liquidity"],
                            "series": _series(volume_tail=9e9)}
    run_b = service.create_run(_payload(name="mutated", **mutated))
    service.execute_run(run_b["id"])
    obs_a = cd_store.list_observation_results(run_a["id"], page_size=100)["items"]
    obs_b = cd_store.list_observation_results(run_b["id"], page_size=100)["items"]
    assert len(obs_a) == len(obs_b) == 5
    for a, b in zip(obs_a, obs_b):
        assert a["impact_cost"] == b["impact_cost"]
        assert a["total_cost"] == b["total_cost"]
        assert a["net_value"] == b["net_value"]
    # integrity reflects the causal derivation
    assert service.get_run(run_a["id"])["integrity_status"] == \
        "verified_causal_input"


def test_centered_and_negative_lag_rejected_at_create():
    cfg = dict(
        observations=_trades(4),
        liquidity={"adv_source": {"mode": "trailing_volume", "lookback": 10,
                                  "lag": 1, "unit": "currency",
                                  "window": "centered"},
                   "series": _series()},
        impact={"model": "square_root", "coefficient": 0.1,
                "participation_mode": "notional"})
    with pytest.raises(service.CostDiagnosticsError, match="centered"):
        service.create_run(_payload(**cfg))
    cfg2 = dict(
        observations=_trades(4),
        liquidity={"adv_source": {"mode": "trailing_volume", "lookback": 10,
                                  "lag": -1, "unit": "currency"},
                   "series": _series()},
        impact={"model": "square_root", "coefficient": 0.1,
                "participation_mode": "notional"})
    with pytest.raises(service.CostDiagnosticsError, match="lag"):
        service.create_run(_payload(**cfg2))
    # ADV unit must match the participation mode — no silent conversion
    cfg3 = dict(
        observations=_trades(4),
        liquidity={"adv_source": {"mode": "trailing_volume", "lookback": 10,
                                  "lag": 1, "unit": "units"},
                   "series": _series()},
        impact={"model": "square_root", "coefficient": 0.1,
                "participation_mode": "notional"})
    with pytest.raises(service.CostDiagnosticsError, match="no silent unit"):
        service.create_run(_payload(**cfg3))


# ---------------------------------------------------------------------------
# Fingerprints
# ---------------------------------------------------------------------------


def test_fingerprint_material_changes_and_nan_rejection():
    trades, currency = core.normalize_trades(_trades(3))
    fp1 = fp_mod.observation_universe_fingerprint(trades, "trade", currency, None)
    trades2, _ = core.normalize_trades(_trades(3, entry=101.0))
    fp2 = fp_mod.observation_universe_fingerprint(trades2, "trade", currency, None)
    assert fp1 != fp2
    cm1 = fp_mod.cost_model_fingerprint(
        {"model": "none"}, {"model": "none"}, {"model": "none"},
        {"model": "none"}, {})
    cm2 = fp_mod.cost_model_fingerprint(
        {"model": "bps_of_notional", "value": 1.0}, {"model": "none"},
        {"model": "none"}, {"model": "none"}, {})
    assert cm1 != cm2
    with pytest.raises(fp_mod.FingerprintError):
        fp_mod.cost_model_fingerprint({"v": float("nan")}, {}, {}, {}, {})


def test_fingerprint_covers_ticksize_costinputs_and_liquidity_series():
    # These three inputs change results and feed the baseline scope; two runs
    # that differ only in one of them must NOT collide on a fingerprint.
    none = {"model": "none"}
    # tick_size is a cost-model parameter (prices tick-denominated costs)
    cm_a = fp_mod.cost_model_fingerprint(none, none, none, none, {}, 0.25)
    cm_b = fp_mod.cost_model_fingerprint(none, none, none, none, {}, 0.50)
    assert cm_a != cm_b
    assert cm_a == fp_mod.cost_model_fingerprint(none, none, none, none, {}, 0.25)
    # per-observation supplied execution inputs are hashed into the universe
    trades, currency = core.normalize_trades(_trades(2))
    with_inputs, _ = core.normalize_trades(
        [_trade(0, cost_inputs={"realized_slippage": {"value": -0.5}}),
         _trade(1)])
    base_fp = fp_mod.observation_universe_fingerprint(trades, "trade", currency, None)
    inputs_fp = fp_mod.observation_universe_fingerprint(
        with_inputs, "trade", currency, None)
    assert base_fp != inputs_fp
    # the run-level liquidity series is hashed into the universe as well
    series_fp = fp_mod.observation_universe_fingerprint(
        trades, "trade", currency, None, {"volume": [1.0, 2.0]})
    assert series_fp != base_fp
    assert series_fp != fp_mod.observation_universe_fingerprint(
        trades, "trade", currency, None, {"volume": [1.0, 3.0]})


def test_reexecution_is_deterministic():
    run = service.create_run(_payload())
    first = service.execute_run(run["id"])
    second = service.execute_run(run["id"])
    assert first["result_fingerprint"] == second["result_fingerprint"]
    assert first["result_fingerprint"]
    obs = cd_store.list_observation_results(run["id"])["items"]
    assert len(obs) == 4  # child rows replaced, not duplicated


# ---------------------------------------------------------------------------
# Regime integration
# ---------------------------------------------------------------------------


def test_regime_integration_uses_stored_assignments():
    from app.regime_diagnostics.demo import seed_demo_regime_diagnostics
    from app.regime_diagnostics import store as rd_store
    seed_demo_regime_diagnostics()
    regime_id = rd_store.run_demo_key_id("demo:rd:volatility-trend")
    regime_before = rd_store.get_run(regime_id)
    stamps = regime_before["timestamps"]
    obs = [{"observation_id": f"p{i}", "candidate_id": "a",
            "timestamp": stamps[i], "gross_return": 0.001, "turnover": 0.5}
           for i in range(40, 60)]
    run = service.create_run(_payload(
        observation_type="period", observations=obs,
        commission={"model": "bps_of_notional", "value": 2.0},
        spread={"model": "none"}, slippage={"model": "none"},
        impact={"model": "none"},
        regime_run_id=regime_id, regime_definition_id="vol"))
    result = service.execute_run(run["id"])
    regimes = result["regimes"]
    assert regimes["definition_id"] == "vol"
    assert sum(r["observation_count"] for r in regimes["rows"]) == 20
    # spot-check one label against the stored assignment
    definition = next(d for d in rd_store.list_definitions(regime_id)
                      if d["definition_id"] == "vol")
    label_map = dict(zip(stamps, definition["assignments"]))
    row_obs = cd_store.list_observation_results(run["id"], page_size=100)["items"]
    for o in row_obs:
        expected = label_map.get(o["timestamp"])
        assert o["regime_label"] == (expected if expected is not None
                                     else "unassigned")
    # the regime run itself is untouched
    regime_after = rd_store.get_run(regime_id)
    assert regime_after["result_fingerprint"] == regime_before["result_fingerprint"]
    assert regime_after["updated_at"] == regime_before["updated_at"]
    # unknown definition id fails honestly
    with pytest.raises(service.CostDiagnosticsError, match="not found in run"):
        service.create_run(_payload(
            observation_type="period", observations=obs,
            commission={"model": "bps_of_notional", "value": 2.0},
            spread={"model": "none"}, slippage={"model": "none"},
            impact={"model": "none"},
            regime_run_id=regime_id, regime_definition_id="nope"))


def test_regime_rows_reconcile_over_costed_subset():
    # A regime group containing a gross_only observation must expose
    # gross_total_costed so net_total == gross_total_costed - total_cost, exactly
    # like aggregate_results — the whole-group gross is reported separately.
    from collections import Counter
    from app.regime_diagnostics.demo import seed_demo_regime_diagnostics
    from app.regime_diagnostics import store as rd_store
    seed_demo_regime_diagnostics()
    regime_id = rd_store.run_demo_key_id("demo:rd:volatility-trend")
    rrun = rd_store.get_run(regime_id)
    stamps = rrun["timestamps"]
    definition = next(d for d in rd_store.list_definitions(regime_id)
                      if d["definition_id"] == "vol")
    # a label that appears at least twice, so one group holds a costed AND a
    # gross_only observation
    label = next(lbl for lbl, c in Counter(definition["assignments"]).items()
                 if lbl is not None and c >= 2)
    idxs = [i for i, a in enumerate(definition["assignments"]) if a == label][:2]

    def orow(oid, ts, gross, comps):
        vals = {n: comps.get(n) for n in ("commission", "spread",
                                          "slippage", "impact")}
        avail = {n: v for n, v in vals.items() if v is not None}
        total = sum(avail.values()) if avail else None
        return {
            "observation_id": oid, "candidate_id": "a", "timestamp": ts,
            "gross_value": gross, "component_values": vals,
            "total_cost": total,
            "net_value": (gross - total) if total is not None else None,
            "completeness": "complete" if avail else "gross_only",
            "unavailable_components": [], "participation": None,
        }
    obs_results = [
        orow("c0", stamps[idxs[0]], 100.0, {"commission": 20.0}),
        orow("g0", stamps[idxs[1]], 1000.0, {}),  # gross_only, same regime
    ]
    block = service._regime_join(
        {"regime_run_id": regime_id, "regime_definition_id": "vol"},
        obs_results)
    row = next(r for r in block["rows"] if r["regime_label"] == label)
    assert row["gross_total"] == pytest.approx(1100.0)        # whole group
    assert row["gross_total_costed"] == pytest.approx(100.0)  # costed subset
    assert row["total_cost"] == pytest.approx(20.0)
    assert row["net_total"] == pytest.approx(80.0)
    assert row["net_total"] == pytest.approx(
        row["gross_total_costed"] - row["total_cost"])
    assert row["net_total"] != pytest.approx(
        row["gross_total"] - row["total_cost"])
    # the regime run itself is never mutated by the join
    assert rd_store.get_run(regime_id)["updated_at"] == rrun["updated_at"]


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------


def test_baseline_policy():
    run = service.create_run(_payload())
    with pytest.raises(service.ConflictError, match="completed"):
        service.mark_baseline(run["id"])
    service.execute_run(run["id"])
    marked = service.mark_baseline(run["id"])
    assert marked["is_baseline"] and marked["baseline_scope"]
    # idempotent
    again = service.mark_baseline(run["id"])
    assert again["is_baseline"]
    # same-scope replacement is transactional; unrelated scope preserved
    run2 = service.create_run(_payload())
    service.execute_run(run2["id"])
    service.mark_baseline(run2["id"])
    assert not service.get_run(run["id"])["is_baseline"]
    other = service.create_run(_payload(name="other-universe",
                                        observations=_trades(5)))
    service.execute_run(other["id"])
    service.mark_baseline(other["id"])
    assert service.get_run(run2["id"])["is_baseline"]
    # partial completeness cannot baseline
    partial = service.create_run(_payload(
        spread={"model": "supplied", "fraction": 0.5}))
    service.execute_run(partial["id"])
    with pytest.raises(service.ConflictError, match="complete"):
        service.mark_baseline(partial["id"])
    # invalid integrity cannot baseline
    bad = [_trade(i, cost_inputs={"adv": {"value": 100.0, "unit": "units",
                                          "basis": "trailing", "lag": 0,
                                          "lookback": 5},
                                  "volatility": {"value": 0.01,
                                                 "basis": "declared"}})
           for i in range(3)]
    inv = service.create_run(_payload(
        observations=bad,
        impact={"model": "square_root", "coefficient": 0.1,
                "participation_mode": "quantity"}))
    executed = service.execute_run(inv["id"])
    assert executed["integrity_status"] == "invalid"
    with pytest.raises(service.ConflictError, match="integrity"):
        service.mark_baseline(inv["id"])
    # invalidation clears the baseline flag
    service.invalidate_run(run2["id"], "superseded")
    assert not service.get_run(run2["id"])["is_baseline"]


# ---------------------------------------------------------------------------
# Migration, integrations, export, demo
# ---------------------------------------------------------------------------


def test_migration_idempotent_and_registries_preserved():
    db_module.init_db()
    db_module.init_db()
    with db_module.get_connection() as conn:
        tables = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    for t in ("cost_diagnostic_runs", "cost_models", "cost_observation_results",
              "cost_sensitivity_results", "cost_capacity_results",
              "regime_diagnostic_runs", "overfitting_diagnostic_runs",
              "feature_runs", "meta_label_runs", "validation_runs",
              "datasets", "experiment_registry", "saved_backtests"):
        assert t in tables, t
    run = service.create_run(_payload())
    service.execute_run(run["id"])
    with db_module.get_connection() as conn:
        for t in ("regime_diagnostic_runs", "overfitting_diagnostic_runs",
                  "feature_runs", "validation_runs"):
            n = conn.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"]
            assert n == 0  # cost operations never touch prior registries


def test_integrations_and_experiment_record():
    run = service.create_run(_payload())
    executed = service.execute_run(run["id"], create_experiment=True)
    assert executed["experiment_id"] is not None
    assert executed["experiment_name"].startswith("Cost diagnostics:")
    from app.experiment_registry import store as exp_store
    exp = exp_store.get_experiment(executed["experiment_id"])
    assert exp["module"] == "transaction_cost_diagnostics"
    # re-execution never duplicates the experiment record
    again = service.execute_run(run["id"], create_experiment=True)
    assert again["experiment_id"] == executed["experiment_id"]
    # candidate matrix fingerprints for >= 2 candidates
    two = service.create_run(_payload(observations=(
        _trades(3, cid="a") + [_trade(9, cid="b", day=40)])))
    executed2 = service.execute_run(two["id"])
    agg = executed2["aggregates"]
    assert agg["gross_candidate_matrix_fingerprint"]
    assert agg["net_candidate_matrix_fingerprint"]
    assert agg["gross_candidate_matrix_fingerprint"] != \
        agg["net_candidate_matrix_fingerprint"]


def test_export_privacy_and_no_nonfinite(client):
    run = service.create_run(_payload())
    service.execute_run(run["id"])
    resp = client.get(f"{BASE}/export")
    assert resp.status_code == 200
    blob = resp.text
    assert "NaN" not in blob and "Infinity" not in blob
    assert "C:\\\\" not in blob and "C:/" not in blob
    data = resp.json()
    assert data["schema_version"] == "cost_diagnostics_export_v1"
    assert data["runs"] and data["cost_models"]


def test_demo_idempotent_and_expectations():
    from app.cost_diagnostics.demo import seed_demo_cost_diagnostics
    first = seed_demo_cost_diagnostics()
    assert first["created_runs"] == 6
    second = seed_demo_cost_diagnostics()
    assert second["created_runs"] == 0 and second["skipped_existing"] == 6
    by_key = {k: cd_store.get_run(cd_store.run_demo_key_id(k))
              for k in ("demo:cd:complete-costs", "demo:cd:high-turnover-erosion",
                        "demo:cd:partial-missing-inputs",
                        "demo:cd:fixed-fee-scaling", "demo:cd:regime-linked",
                        "demo:cd:invalid-future-looking")}
    flagship = by_key["demo:cd:complete-costs"]
    assert flagship["status"] == "completed"
    assert flagship["completeness_status"] == "complete"
    assert flagship["is_baseline"]
    assert flagship["participation_warning_count"] >= 1
    # only the flagship creates an experiment record (registry-noise policy)
    assert flagship["experiment_id"] is not None
    assert by_key["demo:cd:high-turnover-erosion"]["experiment_id"] is None
    erosion = by_key["demo:cd:high-turnover-erosion"]
    gp_nn = erosion["aggregates"]["gross_positive_net_nonpositive_count"]
    assert gp_nn >= 10 and erosion["net_total"] < 0 < erosion["gross_total"]
    partial = by_key["demo:cd:partial-missing-inputs"]
    assert partial["completeness_status"] == "partial"
    assert partial["unavailable_input_count"] > 0
    regime_linked = by_key["demo:cd:regime-linked"]
    assert regime_linked["integrity_status"] == "verified_causal_input"
    rows = {r["regime_label"]: r for r in regime_linked["regimes"]["rows"]}
    assert rows["high"]["total_cost"] > rows["low"]["total_cost"]
    invalid = by_key["demo:cd:invalid-future-looking"]
    assert invalid["integrity_status"] == "invalid"
    cap = cd_store.list_capacity_results(
        cd_store.run_demo_key_id("demo:cd:complete-costs"))
    parts = [c["max_participation"] for c in cap]
    assert parts == sorted(parts)


# ---------------------------------------------------------------------------
# Adversarial-review regressions (Phase 55 verification workflow findings)
# ---------------------------------------------------------------------------


def test_units_reject_negative_values_and_bad_order_counts():
    assert units.normalize_cost_amount(-5.0, "bps_of_notional",
                                       notional=1e6)["status"] == "unavailable"
    assert units.normalize_cost_amount(2.5, "currency_per_order",
                                       order_count=-3)["status"] == "unavailable"
    assert units.normalize_cost_amount(2.5, "currency_per_order",
                                       order_count=0)["status"] == "unavailable"
    # per_unit means underlying units: contracts x multiplier
    r = units.normalize_cost_amount(0.1, "currency_per_unit", quantity=3.0,
                                    contract_multiplier=50.0)
    assert r["amount"] == pytest.approx(0.1 * 3.0 * 50.0)
    assert units.normalize_cost_amount(0.1, "currency_per_unit",
                                       quantity=3.0)["status"] == "unavailable"


def test_per_unit_commission_uses_contract_multiplier():
    trades, _ = core.normalize_trades(
        [_trade(0, qty=3.0, mult=50.0), _trade(1)])
    cfg = comp_mod.validate_commission_config(
        {"model": "per_unit", "value": 0.1}, "trade")
    # 0.1 per underlying unit x (3 contracts x 50 multiplier) x 2 sides
    assert comp_mod.compute_commission(trades[0], cfg, "trade")["amount"] == \
        pytest.approx(0.1 * 3.0 * 50.0 * 2)


def test_period_runs_reject_monetary_commission_floors_and_spread_sides():
    with pytest.raises(core.CostInputError, match="minimum"):
        comp_mod.validate_commission_config(
            {"model": "bps_of_notional", "value": 1.0, "minimum": 2.0},
            "period")
    with pytest.raises(core.CostInputError, match="round_trip"):
        comp_mod.validate_spread_config(
            {"model": "fixed_bps", "value": 2.0, "fraction": 0.5,
             "sides": "entry_only"}, "period")


def test_trailing_mode_never_falls_back_to_supplied_inputs():
    # one trade sits OUTSIDE the series coverage and supplies a full-sample
    # ADV/volatility; under a trailing config it must stay unavailable, not
    # silently consume the unclassified supplied input
    trades = [_trade(0, day=30, qty=10.0),
              _trade(1, day=32, qty=10.0),
              _trade(2, day=500, qty=10.0,
                     cost_inputs={"adv": {"value": 100.0, "unit": "currency",
                                          "basis": "full_sample"},
                                  "volatility": {"value": 0.5,
                                                 "basis": "full_sample"}})]
    run = service.create_run(_payload(
        observations=trades,
        commission={"model": "none"}, spread={"model": "none"},
        slippage={"model": "none"},
        impact={"model": "square_root", "coefficient": 0.1,
                "participation_mode": "notional"},
        liquidity={
            "adv_source": {"mode": "trailing_volume", "lookback": 10,
                           "lag": 1, "unit": "currency"},
            "volatility_source": {"mode": "trailing_returns", "lookback": 10,
                                  "lag": 1},
            "series": _series()}))
    executed = service.execute_run(run["id"])
    rows = {o["observation_id"]: o for o in
            cd_store.list_observation_results(run["id"], page_size=100)["items"]}
    assert rows["t02"]["impact_cost"] is None
    # impact is the only configured component, so this observation is
    # honestly gross_only (not zero-costed)
    assert rows["t02"]["completeness"] == "gross_only"
    assert rows["t02"]["total_cost"] is None
    assert rows["t00"]["impact_cost"] is not None
    # integrity is not polluted by the never-consumed full-sample inputs
    assert executed["integrity_status"] == "verified_causal_input"
    assert executed["completeness_status"] == "partial"


def test_period_breakeven_uses_turnover_dimension():
    obs = [{"observation_id": f"p{i}", "candidate_id": "a",
            "timestamp": _ts(i), "gross_return": 0.01, "turnover": 0.5,
            "traded_notional": 1_000_000.0} for i in range(3)]
    run = service.create_run(_payload(
        observation_type="period", observations=obs,
        commission={"model": "bps_of_notional", "value": 10.0},
        spread={"model": "none"}, slippage={"model": "none"},
        impact={"model": "none"}))
    executed = service.execute_run(run["id"])
    rows = cd_store.list_observation_results(run["id"])["items"]
    # gross_return / turnover / 1bp = 0.01 / 0.5 / 0.0001 = 200 bps — never
    # the return-fraction / currency-notional mix
    assert rows[0]["breakeven_bps"] == pytest.approx(200.0)
    be = executed["breakeven"]
    assert be["aggregate_breakeven_bps_of_notional"] == pytest.approx(200.0)
    agg = executed["aggregates"]
    # cost fraction of traded notional = cost_return / turnover
    assert agg["cost_fraction_of_traded_notional"] == pytest.approx(
        (10.0 * 0.0001 * 0.5 * 3) / 1.5)


def test_no_silent_zero_total_cost_when_nothing_configured():
    rows = [_obs_result("a", 10.0, {}), _obs_result("b", 5.0, {})]
    agg = agg_mod.aggregate_results(rows)
    assert agg["total_cost"] is None
    assert agg["cost_fraction_of_gross_magnitude"] is None
    assert agg["component_totals"]["commission"] is None


def test_sensitivity_multiplier_pins_supplied_realized_slippage():
    row = _obs_result("a", 10.0, {"slippage": -2.0})
    row["slippage_source"] = "supplied_realized"
    hi = scen_mod.evaluate_scenario([row], {
        "commission_multiplier": 1.0, "spread_multiplier": 1.0,
        "slippage_multiplier": 5.0, "impact_multiplier": 1.0,
        "is_base": False})
    # realized (favourable) slippage is a historical fact — never scaled
    assert hi["total_cost"] == pytest.approx(-2.0)
    modelled = _obs_result("b", 10.0, {"slippage": 2.0})
    hi2 = scen_mod.evaluate_scenario([modelled], {
        "commission_multiplier": 1.0, "spread_multiplier": 1.0,
        "slippage_multiplier": 5.0, "impact_multiplier": 1.0,
        "is_base": False})
    assert hi2["total_cost"] == pytest.approx(10.0)


def test_series_ordering_is_chronological_not_lexicographic():
    # lexicographically increasing but chronologically disordered offsets
    with pytest.raises(liq_mod.LiquidityInputError, match="increasing in time"):
        liq_mod.validate_series({
            "timestamps": ["2024-01-01T09:00:00+00:00",
                           "2024-01-01T12:00:00+09:00",
                           "2024-01-02T09:00:00+00:00"],
            "volume": [1.0, 2.0, 3.0]})
    with pytest.raises(liq_mod.LiquidityInputError, match="mix timezone"):
        liq_mod.validate_series({
            "timestamps": ["2024-01-01T09:00:00", "2024-01-02T09:00:00+00:00",
                           "2024-01-03T09:00:00"],
            "volume": [1.0, 2.0, 3.0]})


def test_volatility_trailing_claim_needs_lookback_two():
    r = liq_mod.classify_supplied_input(
        {"basis": "trailing", "lag": 1, "lookback": 1},
        dataset_linked=False, input_key="volatility")
    assert r["integrity"] == "invalid"
    # a non-volatility input with lookback 1 remains a valid trailing claim
    r2 = liq_mod.classify_supplied_input(
        {"basis": "trailing", "lag": 1, "lookback": 1},
        dataset_linked=False, input_key="adv")
    assert r2["integrity"] == "verified_causal_input"


def test_integer_contracts_reject_fractional_base_quantities():
    with pytest.raises(service.CostDiagnosticsError, match="whole-number"):
        service.create_run(_payload(
            observations=_trades(4, qty=1.5), integer_contracts=True))


def test_failed_execution_is_recorded_not_stuck_running(monkeypatch):
    run = service.create_run(_payload())
    monkeypatch.setattr(service.agg_mod, "aggregate_results",
                        lambda *a, **k: (_ for _ in ()).throw(
                            RuntimeError("boom")))
    with pytest.raises(service.CostDiagnosticsError, match="execution failed"):
        service.execute_run(run["id"])
    stored = cd_store.get_run(run["id"])
    assert stored["status"] == "failed"
    assert "boom" in stored["error_message"]


def test_failed_reexecution_clears_stale_derived_state(monkeypatch):
    # A previously-successful (and baselined) run that later fails re-execution
    # must not keep its baseline flag, result fingerprint, aggregates or child
    # rows — otherwise a "failed" run would still advertise stale results.
    run = service.create_run(_payload())
    service.execute_run(run["id"])
    service.mark_baseline(run["id"])
    before = cd_store.get_run(run["id"])
    assert before["is_baseline"] and before["result_fingerprint"]
    assert before["aggregates"] and cd_store.list_observation_results(
        run["id"])["items"]
    assert cd_store.list_sensitivity_results(run["id"])
    assert cd_store.list_capacity_results(run["id"])
    assert before["duration_ms"] is not None

    monkeypatch.setattr(service.agg_mod, "aggregate_results",
                        lambda *a, **k: (_ for _ in ()).throw(
                            RuntimeError("boom")))
    with pytest.raises(service.CostDiagnosticsError, match="execution failed"):
        service.execute_run(run["id"])

    after = cd_store.get_run(run["id"])
    assert after["status"] == "failed"
    assert after["is_baseline"] is False
    assert after["baseline_scope"] is None
    assert after["result_fingerprint"] is None
    assert after["duration_ms"] is None  # prior success's elapsed time cleared
    assert not after["aggregates"] and not after["breakeven"]
    # regimes stays an (empty) dict — the Optional[Dict] field must never be
    # cleared to a list, which is the exact shape that trips Pydantic loading
    assert not after["regimes"]
    assert not isinstance(after["regimes"], list)
    assert after["gross_total"] is None and after["net_total"] is None
    # child result rows are cleared, not left stale
    assert cd_store.list_observation_results(run["id"])["items"] == []
    assert cd_store.list_sensitivity_results(run["id"]) == []
    assert cd_store.list_capacity_results(run["id"]) == []


# ---------------------------------------------------------------------------
# API paths
# ---------------------------------------------------------------------------


def test_api_happy_path(client):
    resp = client.post(f"{BASE}/runs", json=_payload())
    assert resp.status_code == 201
    run_id = resp.json()["id"]
    resp = client.post(f"{BASE}/runs/{run_id}/execute",
                       json={"create_experiment": False})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["completeness_status"] == "complete"
    assert client.get(f"{BASE}/summary").json()["runs"] == 1
    obs = client.get(f"{BASE}/runs/{run_id}/observations").json()
    assert obs["total"] == 4
    for o in obs["items"]:
        comps = [v for v in (o["commission_cost"], o["spread_cost"],
                             o["slippage_cost"], o["impact_cost"])
                 if v is not None]
        assert o["total_cost"] == pytest.approx(sum(comps))
        assert o["net_value"] == pytest.approx(o["gross_value"] - o["total_cost"])
    assert client.get(f"{BASE}/runs/{run_id}/sensitivity").json()["items"]
    assert client.get(f"{BASE}/runs/{run_id}/capacity").json()["items"]
    assert client.get(
        f"{BASE}/runs/{run_id}/regimes").json()["regimes"] is None
    resp = client.post(f"{BASE}/runs", json=_payload(name="second"))
    other_id = resp.json()["id"]
    client.post(f"{BASE}/runs/{other_id}/execute",
                json={"create_experiment": False})
    cmp_resp = client.get(f"{BASE}/compare",
                          params={"a": run_id, "b": other_id})
    assert cmp_resp.status_code == 200
    assert cmp_resp.json()["fingerprint_match"]["universe"] is True
    listing = client.get(f"{BASE}/runs", params={"completeness_status":
                                                 "complete"}).json()
    assert listing["total"] == 2


def test_api_error_paths(client):
    assert client.get(f"{BASE}/runs/999").status_code == 404
    assert client.post(f"{BASE}/runs/999/execute",
                       json={"create_experiment": False}).status_code == 404
    # invalid observation type
    assert client.post(f"{BASE}/runs", json=_payload(
        observation_type="fill")).status_code == 422
    # negative fee
    assert client.post(f"{BASE}/runs", json=_payload(
        commission={"model": "fixed_per_trade", "value": -3.0})).status_code == 422
    # spread fraction missing
    assert client.post(f"{BASE}/runs", json=_payload(
        spread={"model": "fixed_bps", "value": 2.0})).status_code == 422
    # tick models require tick_size
    assert client.post(f"{BASE}/runs", json=_payload(
        spread={"model": "fixed_ticks", "value": 2.0,
                "fraction": 0.5})).status_code == 422
    # oversized sensitivity grid
    assert client.post(f"{BASE}/runs", json=_payload(
        sensitivity_grid={"commission_multipliers": [1, 2, 3, 4],
                          "spread_multipliers": [1, 2, 3, 4],
                          "slippage_multipliers": [1, 2, 3, 4]})).status_code == 422
    # unknown linked ids
    assert client.post(f"{BASE}/runs", json=_payload(
        dataset_version_id=12345)).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(
        regime_run_id=12345, regime_definition_id="vol")).status_code == 422
    # raw NaN token in the JSON body is rejected
    raw = json.dumps(_payload()).replace('"entry_price": 100.0',
                                         '"entry_price": NaN')
    resp = client.post(f"{BASE}/runs", content=raw,
                       headers={"content-type": "application/json"})
    assert resp.status_code == 422
    # duplicate invalidation conflicts
    created = client.post(f"{BASE}/runs", json=_payload()).json()
    client.post(f"{BASE}/runs/{created['id']}/invalidate",
                json={"reason": "test"})
    assert client.post(f"{BASE}/runs/{created['id']}/invalidate",
                       json={"reason": "again"}).status_code == 409
    # compare requires two distinct runs
    assert client.get(f"{BASE}/compare",
                      params={"a": created["id"],
                              "b": created["id"]}).status_code == 422
