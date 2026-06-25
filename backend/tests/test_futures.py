"""
Tests for the Futures & Commodities Lab (Phase 23.0).

Confirms the static-sample API shape, validation, JSON-safety (no NaN/Inf), and
the analytics' mathematical correctness. Fully deterministic — no network calls.
"""

import math

import pytest
from pydantic import ValidationError

from app.futures.models import FuturesAnalysisRequest
from app.futures.sample import sample_requests
from app.futures.service import analyze_futures

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


def _crude():
    return sample_requests()[0]


def _analyze(req=None):
    return analyze_futures(req or _crude())


def _named(reqs, name):
    return next(r for r in reqs if name in r.contract.commodity_name)


def _scenario(out, sid):
    return next(s for s in out.scenario_results if s.id == sid)


def _mutate(req: FuturesAnalysisRequest, **contract_fields) -> FuturesAnalysisRequest:
    base = req.model_dump()
    base["contract"].update(contract_fields)
    return FuturesAnalysisRequest(**base)


# --------------------------------------------------------------------------- #
# 1–2. Endpoints
# --------------------------------------------------------------------------- #
def test_sample_endpoint(client):
    res = client.get("/futures/sample")
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    names = {c["contract"]["commodity_name"] for c in body["commodities"]}
    assert names == {"Crude Oil Sample", "Gold Sample", "Natural Gas Sample", "Wheat Sample"}
    assert "not investment" in body["disclaimer"].lower()
    _assert_all_finite(body)


def test_analyze_endpoint(client):
    req = _crude().model_dump()
    res = client.post("/futures/analyze", json=req)
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    assert "not investment" in body["disclaimer"].lower()
    _assert_all_finite(body)


# --------------------------------------------------------------------------- #
# 3–7. Core formulas
# --------------------------------------------------------------------------- #
def test_cost_of_carry_price():
    out = _analyze()
    carry = 0.045 + 0.015 - 0.020
    assert math.isclose(out.theoretical_pricing.cost_of_carry_rate, carry, rel_tol=1e-12)
    assert math.isclose(out.theoretical_pricing.model_futures_12m, 75.0 * math.exp(carry * 1.0), rel_tol=1e-9)


def test_implied_convenience_yield():
    out = _analyze()
    pt = next(p for p in out.curve_analysis.points if p.maturity_months == 12)
    t = 1.0
    expected = 0.045 + 0.015 - math.log(pt.observed_futures / 75.0) / t
    assert math.isclose(pt.implied_convenience_yield, expected, rel_tol=1e-9)


def test_basis_formula():
    out = _analyze()
    pt = out.curve_analysis.points[0]
    assert math.isclose(pt.basis, pt.observed_futures - 75.0, rel_tol=1e-9)


def test_annualized_basis_finite():
    out = _analyze()
    for p in out.curve_analysis.points:
        assert math.isfinite(p.annualized_basis)


def test_roll_yield_formula():
    out = _analyze()
    row = out.roll_yield_table[0]
    assert math.isclose(row.roll_yield, (row.near_price - row.next_price) / row.near_price, rel_tol=1e-9)


# --------------------------------------------------------------------------- #
# 8–9. Curve shape classification
# --------------------------------------------------------------------------- #
def test_curve_shape_contango():
    assert _analyze(_named(sample_requests(), "Crude")).curve_analysis.curve_shape == "contango"
    assert _analyze(_named(sample_requests(), "Gold")).curve_analysis.curve_shape == "contango"


def test_curve_shape_backwardation_and_mixed():
    assert _analyze(_named(sample_requests(), "Natural Gas")).curve_analysis.curve_shape == "backwardation"
    assert _analyze(_named(sample_requests(), "Wheat")).curve_analysis.curve_shape == "mixed"


# --------------------------------------------------------------------------- #
# 10–15. Spread, P&L, margin
# --------------------------------------------------------------------------- #
def test_calendar_spread_formula():
    out = _analyze()
    cal = out.calendar_spread_analysis
    assert math.isclose(cal.spread, cal.deferred_price - cal.near_price, rel_tol=1e-9)


def test_long_pnl_formula():
    out = _analyze()  # crude is long 5 @ 75.80 → 77.60, mult 1000
    expected = (77.60 - 75.80) * 1000 * 5
    assert math.isclose(out.position_pnl.pnl, expected, rel_tol=1e-9)


def test_short_pnl_formula():
    out = _analyze(_named(sample_requests(), "Natural Gas"))  # short 3 @ 3.45 → 3.20, mult 10000
    expected = (3.45 - 3.20) * 10000 * 3
    assert math.isclose(out.position_pnl.pnl, expected, rel_tol=1e-9)


def test_notional_formula():
    out = _analyze()
    assert math.isclose(out.position_pnl.notional, 75.80 * 1000 * 5, rel_tol=1e-9)


def test_initial_margin_formula():
    out = _analyze()
    assert math.isclose(out.margin_analysis.initial_margin, out.margin_analysis.notional * 0.10, rel_tol=1e-9)
    assert math.isclose(out.margin_analysis.maintenance_margin, out.margin_analysis.notional * 0.075, rel_tol=1e-9)


def test_return_on_margin_formula():
    out = _analyze()
    expected = out.position_pnl.pnl / out.position_pnl.initial_margin
    assert math.isclose(out.position_pnl.return_on_margin, expected, rel_tol=1e-9)


# --------------------------------------------------------------------------- #
# 16–18. Scenarios
# --------------------------------------------------------------------------- #
def test_scenarios_exist():
    out = _analyze()
    ids = {s.id for s in out.scenario_results}
    assert {
        "base", "spot_rally", "spot_selloff", "contango_steepening",
        "backwardation_shock", "storage_cost_shock", "convenience_yield_shock", "margin_stress",
    } == ids


def test_spot_rally_increases_spot():
    out = _analyze()
    assert _scenario(out, "spot_rally").shocked_spot > 75.0


def test_contango_steepening_increases_far_near_spread():
    out = _analyze()
    # Compare the calendar spread P&L (long near / short deferred) — steepening
    # contango lifts the far leg more, so the near−far spread falls (negative P&L).
    base = _scenario(out, "base")
    steep = _scenario(out, "contango_steepening")
    assert steep.calendar_spread_pnl < base.calendar_spread_pnl + 1e-9


# --------------------------------------------------------------------------- #
# 19–22. Validation
# --------------------------------------------------------------------------- #
def test_reject_negative_spot():
    with pytest.raises(ValidationError):
        _mutate(_crude(), spot_price=-1.0)


def test_reject_invalid_maturity():
    base = _crude().model_dump()
    base["curve"][0]["maturity_months"] = 0
    with pytest.raises(ValidationError):
        FuturesAnalysisRequest(**base)


def test_reject_invalid_margin_rates():
    # initial < maintenance
    with pytest.raises(ValidationError):
        _mutate(_crude(), initial_margin_rate=0.05, maintenance_margin_rate=0.10)
    # margin rate > 1
    with pytest.raises(ValidationError):
        _mutate(_crude(), initial_margin_rate=1.5)


def test_reject_non_finite():
    with pytest.raises(ValidationError):
        _mutate(_crude(), storage_cost_rate=float("nan"))


# --------------------------------------------------------------------------- #
# 23. JSON-safety
# --------------------------------------------------------------------------- #
def test_no_nan_or_infinity(client):
    for req in sample_requests():
        res = client.post("/futures/analyze", json=req.model_dump())
        assert res.status_code == 200
        _assert_all_finite(res.json())
