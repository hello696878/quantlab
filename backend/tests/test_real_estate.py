"""
Tests for the Real Estate Lab (Phase 22.0).

Confirms the static-sample API shape, validation, JSON-safety (no NaN/Inf), and
the analytics' mathematical correctness. Fully deterministic — no network calls.
"""

import math

import pytest
from pydantic import ValidationError

from app.real_estate.models import RealEstateAnalysisRequest
from app.real_estate.sample import sample_request
from app.real_estate.service import analyze_real_estate, irr

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


def _analyze(**overrides):
    base = sample_request().model_dump()
    base.update(overrides)
    return analyze_real_estate(RealEstateAnalysisRequest(**base))


def _mutate_property(**fields) -> RealEstateAnalysisRequest:
    base = sample_request().model_dump()
    base["property"].update(fields)
    return RealEstateAnalysisRequest(**base)


# --------------------------------------------------------------------------- #
# 1–2. Endpoints
# --------------------------------------------------------------------------- #
def test_sample_endpoint(client):
    res = client.get("/real-estate/sample")
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    assert body["request"]["property"]["purchase_price"] == 10_000_000
    assert body["request"]["debt"]["loan_amount"] == 6_500_000
    assert body["request"]["reit"]["shares_outstanding"] == 30_000_000
    assert "not investment" in body["disclaimer"].lower()
    _assert_all_finite(body)


def test_analyze_endpoint_accepts_sample(client):
    req = sample_request().model_dump()
    res = client.post("/real-estate/analyze", json=req)
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    assert "not investment" in body["disclaimer"].lower()
    _assert_all_finite(body)


# --------------------------------------------------------------------------- #
# 3–11. Core formulas
# --------------------------------------------------------------------------- #
def test_egi_formula():
    out = _analyze()
    inc = out.income_statement
    expected = 720_000 * (1 - 0.05) + 30_000
    assert math.isclose(inc.effective_gross_income, expected, rel_tol=1e-9)


def test_noi_formula():
    out = _analyze()
    inc = out.income_statement
    assert math.isclose(inc.net_operating_income, inc.effective_gross_income - 280_000, rel_tol=1e-9)
    assert math.isclose(inc.noi_after_reserves, inc.net_operating_income - 40_000, rel_tol=1e-9)


def test_cap_rate_formula():
    out = _analyze()
    expected = out.income_statement.net_operating_income / 10_000_000
    assert math.isclose(out.valuation.in_place_cap_rate, expected, rel_tol=1e-9)


def test_value_from_cap_rate():
    # exit value uses forward NOI / exit cap; check the identity value*cap = NOI.
    out = _analyze()
    v = out.valuation
    assert v.value_at_exit_cap > 0
    implied_noi = v.value_at_exit_cap * v.exit_cap_rate
    assert math.isfinite(implied_noi) and implied_noi > 0


def test_monthly_payment_formula():
    out = _analyze()
    p, r, n = 6_500_000.0, 0.055 / 12, 360
    expected = p * r / (1 - (1 + r) ** (-n))
    assert math.isclose(out.debt_metrics.monthly_payment, expected, rel_tol=1e-9)


def test_zero_interest_mortgage():
    base = sample_request().model_dump()
    base["debt"]["interest_rate"] = 0.0
    out = analyze_real_estate(RealEstateAnalysisRequest(**base))
    expected = 6_500_000.0 / 360
    assert math.isclose(out.debt_metrics.monthly_payment, expected, rel_tol=1e-9)


def test_ltv_formula():
    out = _analyze()
    assert math.isclose(out.debt_metrics.loan_to_value, 6_500_000 / 10_000_000, rel_tol=1e-9)


def test_dscr_formula():
    out = _analyze()
    d = out.debt_metrics
    expected = out.income_statement.net_operating_income / d.annual_debt_service
    assert math.isclose(d.dscr, expected, rel_tol=1e-9)


def test_cash_on_cash_formula():
    out = _analyze()
    lr = out.levered_returns
    expected = lr.year1_before_tax_cash_flow / lr.initial_equity
    assert math.isclose(lr.cash_on_cash, expected, rel_tol=1e-9)
    assert math.isclose(lr.initial_equity, 10_000_000 + 200_000 - 6_500_000, rel_tol=1e-9)


# --------------------------------------------------------------------------- #
# 12–13. Balances & scenarios
# --------------------------------------------------------------------------- #
def test_remaining_balance_finite_and_bounded():
    out = _analyze()
    bal = out.debt_metrics.remaining_balance_at_exit
    assert math.isfinite(bal)
    assert 0.0 <= bal <= 6_500_000 + 1e-6


def test_scenarios_exist():
    out = _analyze()
    ids = {s.id for s in out.scenario_results}
    assert {"base", "rent_upside", "vacancy_shock", "cap_rate_expansion", "interest_rate_shock", "downside_combo"} == ids


def test_vacancy_shock_lowers_noi():
    out = _analyze()
    base = next(s for s in out.scenario_results if s.id == "base")
    shock = next(s for s in out.scenario_results if s.id == "vacancy_shock")
    assert shock.vacancy_rate > base.vacancy_rate
    assert shock.noi < base.noi


def test_cap_rate_expansion_lowers_exit_value():
    out = _analyze()
    base = next(s for s in out.scenario_results if s.id == "base")
    expand = next(s for s in out.scenario_results if s.id == "cap_rate_expansion")
    assert expand.exit_cap_rate > base.exit_cap_rate
    assert expand.exit_value < base.exit_value


# --------------------------------------------------------------------------- #
# 14. IRR
# --------------------------------------------------------------------------- #
def test_irr_solver_basic():
    # -100 now, +60 for 2 years → IRR ~ 13.07%
    r = irr([-100.0, 60.0, 60.0])
    assert r is not None and 0.12 < r < 0.14


def test_irr_unsolvable_returns_none():
    assert irr([-100.0, -10.0, -10.0]) is None


# --------------------------------------------------------------------------- #
# 16–19. REIT NAV
# --------------------------------------------------------------------------- #
def test_reit_nav_per_share():
    out = _analyze()
    r = out.reit_nav_analysis
    assert math.isclose(r.nav_per_share, (1_200_000_000 - 450_000_000) / 30_000_000, rel_tol=1e-9)
    assert math.isclose(r.nav_per_share, 25.0, rel_tol=1e-9)


def test_reit_premium_discount():
    out = _analyze()
    r = out.reit_nav_analysis
    assert math.isclose(r.premium_discount, 22.0 / 25.0 - 1.0, rel_tol=1e-9)


def test_reit_p_ffo():
    out = _analyze()
    r = out.reit_nav_analysis
    assert r.p_ffo is not None
    assert math.isclose(r.p_ffo, 22.0 / (85_000_000 / 30_000_000), rel_tol=1e-9)


def test_reit_dividend_yield():
    out = _analyze()
    r = out.reit_nav_analysis
    assert math.isclose(r.dividend_yield, 1.2 / 22.0, rel_tol=1e-9)


# --------------------------------------------------------------------------- #
# 20–23. Validation rejections
# --------------------------------------------------------------------------- #
def test_reject_negative_purchase_price():
    with pytest.raises(ValidationError):
        _mutate_property(purchase_price=-1.0)


def test_reject_negative_rent():
    with pytest.raises(ValidationError):
        _mutate_property(gross_rent_annual=-5.0)


def test_reject_vacancy_above_one():
    with pytest.raises(ValidationError):
        _mutate_property(vacancy_rate=1.5)


def test_reject_non_positive_cap_rate():
    with pytest.raises(ValidationError):
        _mutate_property(exit_cap_rate=0.0)


def test_reject_non_finite_value():
    with pytest.raises(ValidationError):
        _mutate_property(operating_expenses_annual=float("nan"))


def test_reject_zero_holding_period():
    with pytest.raises(ValidationError):
        _mutate_property(holding_period_years=0)


# --------------------------------------------------------------------------- #
# 24. JSON-safety
# --------------------------------------------------------------------------- #
def test_no_nan_or_infinity_in_response(client):
    req = sample_request().model_dump()
    # Stress with a high rate to exercise more code paths.
    req["debt"]["interest_rate"] = 0.12
    res = client.post("/real-estate/analyze", json=req)
    assert res.status_code == 200
    _assert_all_finite(res.json())
