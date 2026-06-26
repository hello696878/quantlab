"""
Tests for the Market Microstructure & Execution Lab (Phase 25.0).

Confirms the static-sample API shape, validation, JSON-safety (no NaN/Inf), and
the analytics' mathematical correctness. Fully deterministic — no network calls.
"""

import math

import pytest
from pydantic import ValidationError

from app.microstructure.models import MarketMicrostructureAnalysisRequest
from app.microstructure.sample import sample_requests
from app.microstructure.service import analyze_microstructure

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


def _assert_all_finite(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            _assert_all_finite(v)
    elif isinstance(obj, list):
        for v in obj:
            _assert_all_finite(v)
    elif isinstance(obj, float):
        assert math.isfinite(obj), f"non-finite float in payload: {obj}"


@pytest.fixture
def client():
    return TestClient(main_module.app)


def _btc():
    return sample_requests()[0]


def _analyze(req=None):
    return analyze_microstructure(req or _btc())


def _scenario(out, sid):
    return next(s for s in out.liquidity_scenarios if s.id == sid)


def _schedule(out, name):
    return next(s for s in out.schedule_comparison if s.schedule_name == name)


# --------------------------------------------------------------------------- #
# 1–2. Endpoints
# --------------------------------------------------------------------------- #
def test_sample_endpoint(client):
    res = client.get("/microstructure/sample")
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    syms = {i["order_book"]["symbol"] for i in body["instruments"]}
    assert syms == {"BTCUSDT_SAMPLE", "SPY_SAMPLE", "CL_SAMPLE", "TSM_SAMPLE"}
    assert "not investment" in body["disclaimer"].lower()
    _assert_all_finite(body)


def test_analyze_endpoint(client):
    res = client.post("/microstructure/analyze", json=_btc().model_dump())
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    assert "order-routing" in body["disclaimer"].lower()
    _assert_all_finite(body)


# --------------------------------------------------------------------------- #
# 3–10. Order book formulas
# --------------------------------------------------------------------------- #
def test_order_book_core_formulas():
    out = _analyze()
    ob = out.order_book_summary
    req = _btc()
    bb = max(b.price for b in req.order_book.bids)
    ba = min(a.price for a in req.order_book.asks)
    assert math.isclose(ob.best_bid, bb, rel_tol=1e-12)
    assert math.isclose(ob.best_ask, ba, rel_tol=1e-12)
    assert math.isclose(ob.mid_price, (bb + ba) / 2, rel_tol=1e-12)
    assert math.isclose(ob.spread, ba - bb, rel_tol=1e-9)
    assert math.isclose(ob.spread_bps, (ba - bb) / ob.mid_price * 10000, rel_tol=1e-9)


def test_top_of_book_imbalance_and_microprice():
    out = _analyze()
    ob = out.order_book_summary
    req = _btc()
    bids = sorted(req.order_book.bids, key=lambda x: x.price, reverse=True)
    asks = sorted(req.order_book.asks, key=lambda x: x.price)
    b1, a1 = bids[0].size, asks[0].size
    assert math.isclose(ob.top_of_book_imbalance, (b1 - a1) / (b1 + a1), rel_tol=1e-9)
    expected_micro = (asks[0].price * b1 + bids[0].price * a1) / (b1 + a1)
    assert math.isclose(ob.microprice, expected_micro, rel_tol=1e-9)
    # Bid-heavy book → microprice above mid.
    assert ob.microprice > ob.mid_price


def test_depth_imbalance():
    out = _analyze()
    req = _btc()
    bids = sorted(req.order_book.bids, key=lambda x: x.price, reverse=True)
    asks = sorted(req.order_book.asks, key=lambda x: x.price)
    sb = sum(b.size for b in bids[:5])
    sa = sum(a.size for a in asks[:5])
    assert math.isclose(out.order_book_summary.depth_imbalance_5, (sb - sa) / (sb + sa), rel_tol=1e-9)
    assert out.depth_table[0].cumulative_bid_size == bids[0].size


# --------------------------------------------------------------------------- #
# 11–13. Trade tape formulas
# --------------------------------------------------------------------------- #
def test_vwap_twap_imbalance():
    out = _analyze()
    req = _btc()
    t = out.trade_tape_summary
    tv = sum(x.size for x in req.trades)
    vwap = sum(x.price * x.size for x in req.trades) / tv
    twap = sum(x.price for x in req.trades) / len(req.trades)
    signed = sum((x.size if x.side == "buy" else -x.size) for x in req.trades)
    assert math.isclose(t.vwap, vwap, rel_tol=1e-9)
    assert math.isclose(t.twap, twap, rel_tol=1e-9)
    assert math.isclose(t.trade_imbalance, signed / tv, rel_tol=1e-9)
    assert math.isclose(t.total_volume, tv, rel_tol=1e-9)
    assert math.isclose(t.buy_volume + t.sell_volume, tv, rel_tol=1e-9)


# --------------------------------------------------------------------------- #
# 14–19. Execution formulas
# --------------------------------------------------------------------------- #
def test_execution_core_formulas():
    out = _analyze()
    req = _btc()
    ex = out.execution_summary
    filled = sum(f.quantity for f in req.fills)
    avg = sum(f.price * f.quantity for f in req.fills) / filled
    assert math.isclose(ex.average_execution_price, avg, rel_tol=1e-9)
    assert math.isclose(ex.filled_quantity, filled, rel_tol=1e-9)
    assert math.isclose(ex.fill_ratio, filled / req.execution_order.quantity, rel_tol=1e-9)
    # Buy fills above arrival → positive shortfall.
    assert ex.shortfall_bps > 0
    assert math.isclose(ex.participation_rate, filled / out.trade_tape_summary.total_volume, rel_tol=1e-9)
    assert ex.market_impact_bps >= 0 and math.isfinite(ex.market_impact_bps)


def test_sell_shortfall_sign():
    out = _analyze(sample_requests()[2])  # CL sample is a sell parent
    assert out.execution_summary.side == "sell"
    # Sell fills below arrival → positive shortfall (cost).
    assert out.execution_summary.shortfall_bps > 0


# --------------------------------------------------------------------------- #
# 20–23. Schedules & scenarios
# --------------------------------------------------------------------------- #
def test_schedule_comparison_present():
    out = _analyze()
    names = {s.schedule_name for s in out.schedule_comparison}
    assert {"Immediate", "TWAP", "VWAP-style", "Participation-of-volume"} == names
    # Immediate front-loads impact → higher shortfall than TWAP.
    assert _schedule(out, "Immediate").expected_shortfall_bps >= _schedule(out, "TWAP").expected_shortfall_bps


def test_liquidity_scenarios_present():
    out = _analyze()
    ids = {s.id for s in out.liquidity_scenarios}
    assert {
        "base", "spread_doubles", "depth_halves", "volatility_spike",
        "volume_drought", "liquidity_shock_combo", "bid_side_pressure", "ask_side_pressure",
    } == ids


def test_spread_doubles_increases_spread_bps():
    out = _analyze()
    base = _scenario(out, "base")
    doubled = _scenario(out, "spread_doubles")
    assert math.isclose(doubled.spread_bps, base.spread_bps * 2.0, rel_tol=1e-9)


def test_depth_halves_lowers_depth():
    out = _analyze()
    base = _scenario(out, "base")
    halved = _scenario(out, "depth_halves")
    assert math.isclose(halved.total_depth, base.total_depth * 0.5, rel_tol=1e-9)
    assert halved.immediate_shortfall_bps > base.immediate_shortfall_bps


# --------------------------------------------------------------------------- #
# 24–28. Validation
# --------------------------------------------------------------------------- #
def test_reject_crossed_book():
    base = _btc().model_dump()
    base["order_book"]["bids"][0]["price"] = base["order_book"]["asks"][0]["price"] + 100
    with pytest.raises(ValidationError):
        MarketMicrostructureAnalysisRequest(**base)


def test_reject_negative_price():
    base = _btc().model_dump()
    base["order_book"]["bids"][0]["price"] = -1.0
    with pytest.raises(ValidationError):
        MarketMicrostructureAnalysisRequest(**base)


def test_reject_negative_size():
    base = _btc().model_dump()
    base["order_book"]["asks"][0]["size"] = -5.0
    with pytest.raises(ValidationError):
        MarketMicrostructureAnalysisRequest(**base)


def test_reject_invalid_side():
    base = _btc().model_dump()
    base["execution_order"]["side"] = "hold"
    with pytest.raises(ValidationError):
        MarketMicrostructureAnalysisRequest(**base)


def test_reject_non_finite():
    base = _btc().model_dump()
    base["volatility_bps"] = float("nan")
    with pytest.raises(ValidationError):
        MarketMicrostructureAnalysisRequest(**base)


def test_microprice_vs_mid_consistency():
    out = _analyze()
    ob = out.order_book_summary
    # microprice_vs_mid_bps must agree with the microprice / mid relationship.
    expected = (ob.microprice - ob.mid_price) / ob.mid_price * 10000.0
    assert math.isclose(ob.microprice_vs_mid_bps, expected, rel_tol=1e-9, abs_tol=1e-9)
    # Bid-heavy BTC sample → microprice rich vs mid.
    assert ob.microprice_vs_mid_bps > 0


def test_slippage_sign_and_finiteness():
    out = _analyze()
    ex = out.execution_summary
    # Buy fills above the VWAP/benchmark → positive (costly) slippage here.
    assert math.isfinite(ex.slippage_bps)
    assert ex.slippage_bps > 0


def test_schedule_completion_and_participation():
    out = _analyze()
    for s in out.schedule_comparison:
        assert 0.0 <= s.completion_rate <= 1.0 + 1e-9
        assert s.participation_rate >= 0.0
        assert math.isfinite(s.expected_avg_price) and s.expected_avg_price > 0
    pov = _schedule(out, "Participation-of-volume")
    btc = _btc()
    assert math.isclose(pov.participation_rate, btc.execution_order.participation_limit or 0.10, rel_tol=1e-9)


def test_ask_side_pressure_pushes_microprice_down():
    out = _analyze()
    bid = _scenario(out, "bid_side_pressure")
    ask = _scenario(out, "ask_side_pressure")
    base = _scenario(out, "base")
    # Bid pressure lifts microprice above base; ask pressure pushes it below.
    assert bid.microprice > base.microprice > ask.microprice
    assert bid.depth_imbalance > 0 > ask.depth_imbalance


def test_volume_drought_raises_impact():
    out = _analyze()
    base = _scenario(out, "base")
    drought = _scenario(out, "volume_drought")
    # Thinner volume → higher immediate shortfall (impact term grows).
    assert drought.immediate_shortfall_bps > base.immediate_shortfall_bps


def test_all_sample_instruments_analyze():
    for req in sample_requests():
        out = analyze_microstructure(req)
        assert out.order_book_summary.best_ask > out.order_book_summary.best_bid
        assert out.execution_summary.fill_ratio > 0
        assert len(out.schedule_comparison) == 4
        assert len(out.liquidity_scenarios) == 8


# --------------------------------------------------------------------------- #
# TCA / execution-cost attribution (Phase 25.1)
# --------------------------------------------------------------------------- #
def test_tca_section_present(client):
    res = client.post("/microstructure/analyze", json=_btc().model_dump())
    assert res.status_code == 200
    tca = res.json()["tca"]
    components = {r["component"] for r in tca["attribution_rows"]}
    assert components == {"Spread cost", "Market impact", "Timing / drift", "Fees", "Residual"}


def test_tca_total_equals_component_sum():
    for req in sample_requests():
        tca = analyze_microstructure(req).tca
        comp_sum = sum(r.cost_bps for r in tca.attribution_rows)
        assert math.isclose(comp_sum, tca.total_cost_bps, abs_tol=1e-9)
        # And the named components reconcile to the same total.
        named = tca.spread_cost_bps + tca.impact_cost_bps + tca.timing_cost_bps + tca.fees_bps
        residual = next(r.cost_bps for r in tca.attribution_rows if r.component == "Residual")
        assert math.isclose(named + residual, tca.total_cost_bps, abs_tol=1e-9)


def test_tca_total_equals_arrival_shortfall():
    out = _analyze()
    assert math.isclose(out.tca.total_cost_bps, out.execution_summary.shortfall_bps, abs_tol=1e-9)
    assert math.isclose(out.tca.benchmark_arrival_bps, out.execution_summary.shortfall_bps, abs_tol=1e-9)


def test_tca_components_finite():
    for req in sample_requests():
        tca = analyze_microstructure(req).tca
        for v in (
            tca.benchmark_arrival_bps, tca.benchmark_vwap_bps, tca.benchmark_twap_bps,
            tca.spread_cost_bps, tca.impact_cost_bps, tca.timing_cost_bps,
            tca.fees_bps, tca.total_cost_bps,
        ):
            assert math.isfinite(v)
        assert tca.spread_cost_bps >= 0.0  # half-spread cost is non-negative
        assert tca.impact_cost_bps >= 0.0  # square-root impact is non-negative
        assert tca.fees_bps >= 0.0
        for r in tca.attribution_rows:
            assert math.isfinite(r.cost_bps) and math.isfinite(r.share)


# --------------------------------------------------------------------------- #
# Order Flow Toxicity & Liquidity Metrics (Phase 25.2)
# --------------------------------------------------------------------------- #
def _tox(out=None):
    return (out or _analyze()).order_flow_toxicity


def _tox_scenario(tox, sid):
    return next(s for s in tox.toxicity_scenarios if s.id == sid)


def test_toxicity_section_present(client):
    res = client.post("/microstructure/analyze", json=_btc().model_dump())
    assert res.status_code == 200
    body = res.json()
    assert "order_flow_toxicity" in body
    tox = body["order_flow_toxicity"]
    assert tox["data_status"] == "static_sample"
    assert "order-routing" in tox["disclaimer"].lower()
    _assert_all_finite(tox)


def test_toxicity_ofi_and_qi_bounded():
    for req in sample_requests():
        tox = _tox(analyze_microstructure(req))
        assert -1.0 <= tox.order_flow_summary.order_flow_imbalance <= 1.0
        assert -1.0 <= tox.order_flow_summary.average_queue_imbalance <= 1.0


def test_toxicity_spread_quality_finite_and_consistent():
    for req in sample_requests():
        sq = _tox(analyze_microstructure(req)).spread_quality
        assert math.isfinite(sq.average_effective_spread_bps)
        assert math.isfinite(sq.average_realized_spread_bps)
        # adverse selection = effective − realized (averages of a linear relation).
        assert math.isclose(
            sq.average_adverse_selection_bps,
            sq.average_effective_spread_bps - sq.average_realized_spread_bps,
            abs_tol=1e-6,
        )
        assert math.isfinite(sq.effective_spread_p95_bps)
        assert math.isfinite(sq.adverse_selection_p95_bps)


def test_toxicity_vpin_bounded_and_buckets_positive():
    for req in sample_requests():
        tm = _tox(analyze_microstructure(req)).toxicity_metrics
        assert 0.0 <= tm.vpin <= 1.0
        assert tm.vpin_bucket_count > 0


def test_toxicity_kyle_lambda_finite_or_null():
    tm = _tox().toxicity_metrics
    assert tm.kyle_lambda is None or math.isfinite(tm.kyle_lambda)


def test_toxicity_kyle_lambda_null_on_zero_variance():
    from app.microstructure.toxicity import _kyle_lambda
    # Identical signed volume on every trade → zero variance → null + note.
    trades = [{"eps": 1.0, "size": 2.0, "m_before": 100.0, "m_after": 100.1}] * 4
    value, note = _kyle_lambda(trades, 50)
    assert value is None and note


def test_toxicity_amihud_finite_non_negative():
    for req in sample_requests():
        tm = _tox(analyze_microstructure(req)).toxicity_metrics
        assert math.isfinite(tm.amihud_illiquidity) and tm.amihud_illiquidity >= 0.0


def test_toxicity_regime_exists():
    reg = _tox().liquidity_regime
    assert reg.regime_id and reg.regime_label and reg.explanation
    assert math.isfinite(reg.score)


def test_toxicity_scenarios_present():
    tox = _tox()
    ids = {s.id for s in tox.toxicity_scenarios}
    assert {
        "base", "buy_pressure_wave", "sell_pressure_wave", "spread_widening",
        "depth_evaporation", "toxic_informed_flow", "volume_drought", "liquidity_recovery",
    } == ids


def test_toxicity_scenario_intuitions():
    for req in sample_requests():
        tox = _tox(analyze_microstructure(req))
        base = _tox_scenario(tox, "base")
        assert _tox_scenario(tox, "buy_pressure_wave").order_flow_imbalance > base.order_flow_imbalance
        assert _tox_scenario(tox, "sell_pressure_wave").order_flow_imbalance < base.order_flow_imbalance
        assert _tox_scenario(tox, "spread_widening").effective_spread_bps > base.effective_spread_bps
        assert _tox_scenario(tox, "toxic_informed_flow").adverse_selection_bps > base.adverse_selection_bps
        assert _tox_scenario(tox, "volume_drought").amihud_illiquidity > base.amihud_illiquidity


def test_toxicity_reject_crossed_quote():
    base = _btc().model_dump()
    q = base["quotes"][0]
    q["bid"] = q["ask"] + 5.0
    with pytest.raises(ValidationError):
        MarketMicrostructureAnalysisRequest(**base)


def test_toxicity_reject_bad_signed_trade():
    base = _btc().model_dump()
    base["signed_trades"][0]["side"] = "hold"
    with pytest.raises(ValidationError):
        MarketMicrostructureAnalysisRequest(**base)


def test_toxicity_reject_negative_trade_price():
    base = _btc().model_dump()
    base["signed_trades"][0]["price"] = -1.0
    with pytest.raises(ValidationError):
        MarketMicrostructureAnalysisRequest(**base)


def test_toxicity_reject_bad_config_thresholds():
    base = _btc().model_dump()
    base["toxicity_config"]["regime_threshold_low"] = 0.6
    base["toxicity_config"]["regime_threshold_high"] = 0.4
    with pytest.raises(ValidationError):
        MarketMicrostructureAnalysisRequest(**base)


def test_toxicity_present_without_optional_inputs():
    # When signed_trades / quotes / config are omitted, the section is still derived.
    base = _btc().model_dump()
    base.pop("signed_trades", None)
    base.pop("quotes", None)
    base.pop("toxicity_config", None)
    req = MarketMicrostructureAnalysisRequest(**base)
    tox = analyze_microstructure(req).order_flow_toxicity
    assert tox.toxicity_metrics.vpin_bucket_count > 0
    assert len(tox.toxicity_scenarios) == 8


# --------------------------------------------------------------------------- #
# JSON-safety
# --------------------------------------------------------------------------- #
def test_no_nan_or_infinity(client):
    for req in sample_requests():
        res = client.post("/microstructure/analyze", json=req.model_dump())
        assert res.status_code == 200
        _assert_all_finite(res.json())
