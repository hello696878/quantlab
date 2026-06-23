"""
Tests for the Portfolio Risk Lab (Phase 21.0).

Confirms the static-sample API shape, validation, JSON-safety (no NaN/Inf), and
the analytics' mathematical consistency. Fully deterministic — no network calls.
"""

import math

import pytest
from pydantic import ValidationError

from app.portfolio_risk.models import PortfolioAnalysisRequest
from app.portfolio_risk.sample import sample_assets, sample_stress_scenario
from app.portfolio_risk.service import analyze_portfolio

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


def _request(**overrides) -> PortfolioAnalysisRequest:
    payload = {
        "assets": [a.model_dump() for a in sample_assets()],
        "risk_free_rate": 0.02,
        "confidence_level": 0.95,
        "stress_scenario": sample_stress_scenario().model_dump(),
    }
    payload.update(overrides)
    return PortfolioAnalysisRequest(**payload)


def _analyze(**overrides):
    return analyze_portfolio(_request(**overrides))


# --------------------------------------------------------------------------- #
# 1–2. Endpoints
# --------------------------------------------------------------------------- #
def test_sample_endpoint_returns_assets(client):
    res = client.get("/portfolio-risk/sample")
    assert res.status_code == 200
    body = res.json()
    assert len(body["assets"]) == 8
    assert body["data_status"] == "static_sample"
    assert "not investment advice" in body["disclaimer"].lower()
    _assert_all_finite(body)


def test_analyze_endpoint_accepts_sample(client):
    sample = client.get("/portfolio-risk/sample").json()
    res = client.post(
        "/portfolio-risk/analyze",
        json={
            "assets": sample["assets"],
            "risk_free_rate": sample["risk_free_rate"],
            "confidence_level": sample["confidence_level"],
            "stress_scenario": sample["stress_scenario"],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    assert "not investment advice" in body["disclaimer"].lower()
    _assert_all_finite(body)


# --------------------------------------------------------------------------- #
# 3. Normalisation
# --------------------------------------------------------------------------- #
def test_weights_normalize():
    assets = [a.model_dump() for a in sample_assets()]
    for a in assets:
        a["weight"] = a["weight"] * 10.0  # sum = 10, not 1
    out = analyze_portfolio(PortfolioAnalysisRequest(assets=assets))
    assert math.isclose(sum(out.normalized_weights.values()), 1.0, abs_tol=1e-9)


# --------------------------------------------------------------------------- #
# 4–7. Validation rejections
# --------------------------------------------------------------------------- #
def test_reject_empty_portfolio():
    with pytest.raises(ValidationError):
        PortfolioAnalysisRequest(assets=[])


def test_reject_negative_weight_long_only():
    assets = [a.model_dump() for a in sample_assets()]
    assets[0]["weight"] = -0.2
    with pytest.raises(ValidationError):
        PortfolioAnalysisRequest(assets=assets)


def test_allow_short_permits_negative_weight():
    assets = [a.model_dump() for a in sample_assets()]
    assets[0]["weight"] = -0.1
    req = PortfolioAnalysisRequest(assets=assets, allow_short=True)
    assert req.assets[0].weight == -0.1


def test_reject_non_finite_expected_return():
    assets = [a.model_dump() for a in sample_assets()]
    assets[0]["expected_return"] = float("nan")
    with pytest.raises(ValidationError):
        PortfolioAnalysisRequest(assets=assets)


def test_reject_non_positive_volatility():
    assets = [a.model_dump() for a in sample_assets()]
    assets[0]["volatility"] = 0.0
    with pytest.raises(ValidationError):
        PortfolioAnalysisRequest(assets=assets)


def test_reject_confidence_out_of_range():
    with pytest.raises(ValidationError):
        _request(confidence_level=0.4)
    with pytest.raises(ValidationError):
        _request(confidence_level=1.5)


# --------------------------------------------------------------------------- #
# 8–10. Matrices
# --------------------------------------------------------------------------- #
def test_covariance_square_and_symmetric():
    out = _analyze()
    n = len(out.asset_order)
    cov = out.covariance_matrix
    assert len(cov) == n and all(len(row) == n for row in cov)
    for i in range(n):
        for j in range(n):
            assert math.isclose(cov[i][j], cov[j][i], abs_tol=1e-12)


def test_correlation_diagonal_is_one():
    out = _analyze()
    corr = out.correlation_matrix
    for i in range(len(corr)):
        assert math.isclose(corr[i][i], 1.0, abs_tol=1e-9)
        for j in range(len(corr)):
            assert -1.0001 <= corr[i][j] <= 1.0001


# --------------------------------------------------------------------------- #
# 11–14. Core metrics
# --------------------------------------------------------------------------- #
def test_volatility_non_negative_and_sharpe_finite():
    out = _analyze()
    assert out.volatility >= 0.0
    assert math.isfinite(out.sharpe_ratio)


def test_var_non_negative_and_cvar_ge_var():
    out = _analyze()
    assert out.historical_var >= 0.0
    assert out.historical_cvar >= out.historical_var - 1e-9


# --------------------------------------------------------------------------- #
# 15. Risk contributions
# --------------------------------------------------------------------------- #
def test_risk_contributions_sum_to_one():
    out = _analyze()
    total = sum(c.percent_contribution for c in out.asset_risk_contributions)
    assert math.isclose(total, 1.0, abs_tol=1e-6)


# --------------------------------------------------------------------------- #
# 16–18. Frontier / min-variance / risk parity
# --------------------------------------------------------------------------- #
def test_frontier_stable_and_deterministic():
    a, b = _analyze(), _analyze()
    assert len(a.efficient_frontier) >= 5
    assert [p.volatility for p in a.efficient_frontier] == [
        p.volatility for p in b.efficient_frontier
    ]


def test_min_variance_has_lowest_volatility_among_candidates():
    out = _analyze()
    lowest = min(p.volatility for p in out.efficient_frontier)
    assert math.isclose(out.min_variance_portfolio.volatility, lowest, abs_tol=1e-12)


def test_risk_parity_weights_valid():
    out = _analyze()
    w = out.risk_parity_portfolio.weights
    assert math.isclose(sum(w.values()), 1.0, abs_tol=1e-6)
    assert all(v >= -1e-9 for v in w.values())


def test_risk_parity_contributions_roughly_equal():
    """Risk-parity percent contributions should be close to 1/n."""
    import numpy as np

    out = _analyze()
    ids = out.asset_order
    n = len(ids)
    w = np.array([out.risk_parity_portfolio.weights[i] for i in ids])
    cov = np.array(out.covariance_matrix)
    rc = w * (cov @ w)
    pct = rc / rc.sum()
    assert np.max(np.abs(pct - 1.0 / n)) < 0.05


# --------------------------------------------------------------------------- #
# 19. Stress
# --------------------------------------------------------------------------- #
def test_stress_equals_weighted_scenario_returns():
    out = _analyze()
    assert out.stress_result is not None
    expected = sum(out.stress_result.asset_pnl.values())
    assert math.isclose(out.stress_result.portfolio_pnl, expected, abs_tol=1e-12)
    # each asset pnl = normalized weight * shock
    scenario = sample_stress_scenario()
    for aid, pnl in out.stress_result.asset_pnl.items():
        expect = out.normalized_weights[aid] * scenario.shocks[aid]
        assert math.isclose(pnl, expect, abs_tol=1e-12)


# --------------------------------------------------------------------------- #
# 20. JSON-safety
# --------------------------------------------------------------------------- #
def test_no_nan_or_infinity_in_response(client):
    sample = client.get("/portfolio-risk/sample").json()
    res = client.post(
        "/portfolio-risk/analyze",
        json={
            "assets": sample["assets"],
            "risk_free_rate": 0.03,
            "confidence_level": 0.99,
            "stress_scenario": sample["stress_scenario"],
        },
    )
    assert res.status_code == 200
    _assert_all_finite(res.json())


def test_analyze_without_stress_scenario():
    out = _analyze(stress_scenario=None)
    assert out.stress_result is None
