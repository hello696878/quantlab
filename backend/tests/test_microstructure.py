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
# 30. JSON-safety
# --------------------------------------------------------------------------- #
def test_no_nan_or_infinity(client):
    for req in sample_requests():
        res = client.post("/microstructure/analyze", json=req.model_dump())
        assert res.status_code == 200
        _assert_all_finite(res.json())
