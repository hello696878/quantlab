"""
Tests for the Mortgage & MBS Prepayment Lab (Phase 22.1).

Confirms the static-sample API shape, validation, JSON-safety (no NaN/Inf), and
the analytics' mathematical correctness. Fully deterministic — no network calls.
"""

import math

import pytest
from pydantic import ValidationError

from app.real_estate.mbs import analyze_mbs, cpr_to_smm, psa_cpr
from app.real_estate.models import MortgageMbsRequest
from app.real_estate.sample import sample_mbs_request

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


def _analyze():
    return analyze_mbs(sample_mbs_request())


def _mutate_pool(**fields) -> MortgageMbsRequest:
    base = sample_mbs_request().model_dump()
    base["pool"].update(fields)
    return MortgageMbsRequest(**base)


def _scenario(out, sid):
    return next(s for s in out.scenario_results if s.id == sid)


# --------------------------------------------------------------------------- #
# 1–2. Endpoints
# --------------------------------------------------------------------------- #
def test_mbs_sample_endpoint(client):
    res = client.get("/real-estate/mbs/sample")
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    assert body["request"]["pool"]["current_balance"] == 92_000_000
    assert body["request"]["prepayment"]["psa_speed"] == 100
    assert "not investment" in body["disclaimer"].lower()
    _assert_all_finite(body)


def test_mbs_analyze_endpoint(client):
    req = sample_mbs_request().model_dump()
    res = client.post("/real-estate/mbs/analyze", json=req)
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    assert "not investment" in body["disclaimer"].lower()
    _assert_all_finite(body)


# --------------------------------------------------------------------------- #
# 3–6. Core formulas
# --------------------------------------------------------------------------- #
def test_monthly_payment_formula():
    out = _analyze()
    # First-month scheduled principal = payment − gross interest.
    row = out.cash_flow_schedule[0]
    r_m = 0.055 / 12
    pmt = 92_000_000 * r_m / (1 - (1 + r_m) ** (-330))
    gross_interest = 92_000_000 * r_m
    assert math.isclose(row.scheduled_principal, pmt - gross_interest, rel_tol=1e-6)


def test_zero_coupon_payment_handled():
    base = sample_mbs_request().model_dump()
    base["pool"]["coupon_rate"] = 0.0
    base["pool"]["servicing_fee_rate"] = 0.0
    out = analyze_mbs(MortgageMbsRequest(**base))
    # Zero coupon → scheduled principal = balance / N in month 1 (no prepay at PSA age 31).
    assert math.isfinite(out.cash_flow_schedule[0].scheduled_principal)
    assert out.cash_flow_schedule[0].interest == 0.0


def test_cpr_to_smm_formula():
    assert math.isclose(cpr_to_smm(0.06), 1 - (1 - 0.06) ** (1 / 12), rel_tol=1e-12)
    assert math.isclose(cpr_to_smm(0.0), 0.0, abs_tol=1e-12)


def test_psa_ramp():
    assert math.isclose(psa_cpr(1, 100), 0.002, rel_tol=1e-9)
    assert math.isclose(psa_cpr(30, 100), 0.06, rel_tol=1e-9)
    assert math.isclose(psa_cpr(120, 100), 0.06, rel_tol=1e-9)  # flat after month 30
    assert math.isclose(psa_cpr(30, 200), 0.12, rel_tol=1e-9)  # PSA speed scales


# --------------------------------------------------------------------------- #
# 7–10. Cash flows
# --------------------------------------------------------------------------- #
def test_principal_components_finite():
    out = _analyze()
    for row in out.cash_flow_schedule:
        assert math.isfinite(row.scheduled_principal) and row.scheduled_principal >= 0
        assert math.isfinite(row.prepayment_principal) and row.prepayment_principal >= 0


def test_ending_balance_non_negative():
    out = _analyze()
    for row in out.cash_flow_schedule:
        assert row.ending_balance >= -1e-6


def test_cash_flow_pays_down_balance():
    out = _analyze()
    assert out.cash_flow_summary.final_balance < 1.0  # fully amortised over the term
    # principal repaid ≈ starting balance.
    assert math.isclose(out.cash_flow_summary.total_principal, 92_000_000, rel_tol=1e-4)


# --------------------------------------------------------------------------- #
# 11–15. WAL, prepayment & rate intuition
# --------------------------------------------------------------------------- #
def test_wal_positive_and_finite():
    out = _analyze()
    assert math.isfinite(out.wal) and out.wal > 0


def test_faster_prepayment_lowers_wal():
    out = _analyze()
    assert _scenario(out, "fast_prepayment").wal < _scenario(out, "base_psa").wal


def test_slower_prepayment_raises_wal():
    out = _analyze()
    assert _scenario(out, "slow_prepayment").wal > _scenario(out, "base_psa").wal


def test_rate_up_lowers_price():
    out = _analyze()
    assert _scenario(out, "rate_up_100").price_100 < _scenario(out, "base_psa").price_100


def test_rate_down_raises_price():
    out = _analyze()
    assert _scenario(out, "rate_down_100").price_100 > _scenario(out, "base_psa").price_100


# --------------------------------------------------------------------------- #
# 16–17. Duration / convexity
# --------------------------------------------------------------------------- #
def test_duration_convexity_finite():
    out = _analyze()
    dc = out.duration_convexity
    assert math.isfinite(dc.duration) and dc.duration > 0
    assert math.isfinite(dc.convexity)
    assert dc.price_down >= dc.price_base >= dc.price_up  # monotone in yield


# --------------------------------------------------------------------------- #
# 18–20. Validation
# --------------------------------------------------------------------------- #
def test_reject_negative_balance():
    with pytest.raises(ValidationError):
        _mutate_pool(current_balance=-1.0)


def test_reject_current_above_original():
    with pytest.raises(ValidationError):
        _mutate_pool(current_balance=200_000_000.0)


def test_reject_cpr_above_one():
    base = sample_mbs_request().model_dump()
    base["prepayment"]["cpr"] = 1.5
    with pytest.raises(ValidationError):
        MortgageMbsRequest(**base)


def test_reject_negative_discount_rate():
    base = sample_mbs_request().model_dump()
    base["valuation"]["discount_rate"] = -0.01
    with pytest.raises(ValidationError):
        MortgageMbsRequest(**base)


def test_reject_servicing_above_coupon():
    with pytest.raises(ValidationError):
        _mutate_pool(servicing_fee_rate=0.10)


# --------------------------------------------------------------------------- #
# 21. JSON-safety
# --------------------------------------------------------------------------- #
def test_no_nan_or_infinity(client):
    req = sample_mbs_request().model_dump()
    req["valuation"]["discount_rate"] = 0.09
    req["prepayment"]["psa_speed"] = 300.0
    res = client.post("/real-estate/mbs/analyze", json=req)
    assert res.status_code == 200
    _assert_all_finite(res.json())


def test_constant_cpr_model():
    base = sample_mbs_request().model_dump()
    base["prepayment"] = {"model": "constant_cpr", "cpr": 0.08, "prepayment_lag_months": 0}
    out = analyze_mbs(MortgageMbsRequest(**base))
    # constant-CPR SMM is flat after the (zero) lag.
    smms = {round(p.smm, 10) for p in out.psa_path if p.month > 1}
    assert len(smms) == 1
