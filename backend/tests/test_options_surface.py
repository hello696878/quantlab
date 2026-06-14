"""
Tests for the implied-volatility surface + SVI research engine v1.

Deterministic checks: sample-chain generation, IV recovery of synthetic vols,
grid dimensions, per-row moneyness, graceful per-row failure, smile/term/skew
summaries, SVI fit success on clean data and graceful failure on sparse data,
finiteness, and validation.  No live data, no network.
"""

from __future__ import annotations

import math

import pytest

from app.options_surface import (
    MAX_SURFACE_ROWS,
    SurfaceInputError,
    _synthetic_iv,
    build_sample_surface,
    build_surface,
    fit_svi_slice,
    generate_sample_chain,
)

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


def _assert_all_finite(obj):
    """Floats must be finite; None is allowed (invalid cells / failed rows)."""
    if isinstance(obj, dict):
        for v in obj.values():
            _assert_all_finite(v)
    elif isinstance(obj, list):
        for v in obj:
            _assert_all_finite(v)
    elif isinstance(obj, float):
        assert math.isfinite(obj)


# ---------------------------------------------------------------------------
# Sample chain + IV recovery
# ---------------------------------------------------------------------------


def test_sample_chain_returns_rows():
    rows = generate_sample_chain(100.0, 0.05, 0.0)
    assert len(rows) == 45  # 5 expiries × 9 strikes
    for r in rows:
        assert r["option_type"] in ("call", "put")
        assert r["strike"] > 0 and r["time_to_expiry"] > 0 and r["market_price"] > 0


def test_iv_solver_recovers_synthetic_vols():
    res = build_sample_surface(100.0, 0.05, 0.0, base_vol=0.20, skew=0.15, smile=0.30, term=0.02)
    rows = res["surface"]["rows"]
    assert all(r["solver_converged"] for r in rows)
    # Near-ATM options have meaningful vega → IV recovery is tight. Deep-OTM
    # short-dated options have tiny vega, so recovery is necessarily looser
    # (the solver cannot distinguish vols whose prices agree within tolerance).
    checked = 0
    for r in rows:
        expected = _synthetic_iv(r["log_moneyness"], r["time_to_expiry"], 0.20, 0.15, 0.30, 0.02)
        if abs(r["moneyness"] - 1.0) <= 0.1:
            assert r["implied_volatility"] == pytest.approx(expected, abs=0.01)
            checked += 1
        else:
            # wings: still recovered and in a sane band
            assert 0.05 < r["implied_volatility"] < 1.0
    assert checked > 0


def test_rows_include_moneyness_and_log_moneyness():
    res = build_sample_surface()
    for r in res["surface"]["rows"]:
        assert math.isfinite(r["moneyness"]) and r["moneyness"] > 0
        assert math.isfinite(r["log_moneyness"])
        # moneyness is strike / underlying (S = 100)
        assert r["moneyness"] == pytest.approx(r["strike"] / 100.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Grid
# ---------------------------------------------------------------------------


def test_grid_dimensions_match_axes():
    res = build_sample_surface()
    grid = res["surface"]["grid"]
    assert len(grid["surface_matrix"]) == len(grid["expiries"])
    for row in grid["surface_matrix"]:
        assert len(row) == len(grid["moneyness_values"])
    assert len(grid["log_moneyness_values"]) == len(grid["moneyness_values"])
    assert len(grid["expiry_days"]) == len(grid["expiries"])


def test_grid_cells_are_iv_or_null():
    res = build_sample_surface()
    for row in res["surface"]["grid"]["surface_matrix"]:
        for cell in row:
            assert cell is None or (math.isfinite(cell) and cell > 0)


# ---------------------------------------------------------------------------
# Graceful per-row failure
# ---------------------------------------------------------------------------


def test_invalid_row_does_not_crash_surface():
    # One valid row + one impossible quote (call worth more than the underlying).
    res = build_surface(
        100.0,
        0.05,
        0.0,
        [
            {"option_type": "call", "strike": 100.0, "time_to_expiry": 0.5, "market_price": 6.0},
            {"option_type": "call", "strike": 100.0, "time_to_expiry": 0.5, "market_price": 500.0},
        ],
        fit_svi=False,
    )
    summary = res["surface"]["summary"]
    assert summary["valid_row_count"] == 1
    assert summary["failed_row_count"] == 1


def test_failed_row_has_null_iv_and_warning():
    res = build_surface(
        100.0,
        0.05,
        0.0,
        [{"option_type": "call", "strike": 100.0, "time_to_expiry": 0.5, "market_price": 500.0}],
        fit_svi=False,
    )
    row = res["surface"]["rows"][0]
    assert row["implied_volatility"] is None
    assert row["solver_converged"] is False
    assert row["warning"]


# ---------------------------------------------------------------------------
# Smile / term structure / skew
# ---------------------------------------------------------------------------


def test_term_structure_atm_iv_finite():
    res = build_sample_surface()
    term = res["surface"]["term_structure"]
    assert len(term) == 5
    for t in term:
        assert t["atm_iv"] is not None and math.isfinite(t["atm_iv"]) and t["atm_iv"] > 0


def test_smile_points_sorted_by_moneyness():
    res = build_sample_surface()
    for smile in res["surface"]["smiles"]:
        moneyness = [p["moneyness"] for p in smile["points"]]
        assert moneyness == sorted(moneyness)


def test_skew_values_finite_when_data_sufficient():
    res = build_sample_surface()
    for sk in res["surface"]["skew"]:
        assert sk["skew"] is not None and math.isfinite(sk["skew"])
        # Synthetic surface has a put skew → low-moneyness IV exceeds high-moneyness IV.
        assert sk["skew"] > 0


# ---------------------------------------------------------------------------
# SVI
# ---------------------------------------------------------------------------


def test_svi_fits_clean_synthetic_smile():
    res = build_sample_surface()
    fits = res["surface"]["svi_fits"]
    assert res["surface"]["summary"]["svi_fitted_count"] == len(fits)
    for fit in fits:
        assert fit["fitted"] is True
        assert fit["rmse"] is not None and fit["rmse"] < 0.02  # < 2 vol points
        p = fit["params"]
        assert p["b"] >= 0 and -1 < p["rho"] < 1 and p["sigma"] > 0


def test_svi_fails_gracefully_on_insufficient_points():
    fit = fit_svi_slice([0.0, 0.1, -0.1], [0.2, 0.21, 0.22], 0.25)
    assert fit["fitted"] is False
    assert fit["params"] is None
    assert "Insufficient" in fit["warning"]


def test_svi_disabled_produces_no_fits():
    res = build_sample_surface(fit_svi=False)
    assert res["surface"]["summary"]["svi_fitted_count"] == 0
    for fit in res["surface"]["svi_fits"]:
        assert fit["fitted"] is False


# ---------------------------------------------------------------------------
# Finiteness / validation
# ---------------------------------------------------------------------------


def test_no_nan_inf_in_response():
    _assert_all_finite(build_sample_surface())


def test_rows_above_cap_rejected():
    rows = [{"option_type": "call", "strike": 100.0, "time_to_expiry": 0.25, "market_price": 5.0}] * (
        MAX_SURFACE_ROWS + 1
    )
    with pytest.raises(SurfaceInputError):
        build_surface(100.0, 0.05, 0.0, rows)


def test_invalid_underlying_rejected():
    with pytest.raises(SurfaceInputError):
        build_surface(0.0, 0.05, 0.0, [{"option_type": "call", "strike": 100.0, "time_to_expiry": 0.25, "market_price": 5.0}])


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(main_module.app)


def test_api_sample_surface(client):
    body = client.post(
        "/options/surface/sample",
        json={"underlying_price": 100, "risk_free_rate": 0.05, "dividend_yield": 0, "fit_svi": True},
    ).json()
    surface = body["surface"]
    assert surface["summary"]["valid_row_count"] > 0
    assert surface["summary"]["failed_row_count"] == 0
    assert surface["summary"]["svi_fitted_count"] == 5
    assert len(surface["grid"]["surface_matrix"]) == len(surface["grid"]["expiries"])


def test_api_manual_surface(client):
    resp = client.post(
        "/options/surface",
        json={
            "underlying_price": 100,
            "risk_free_rate": 0.05,
            "dividend_yield": 0,
            "fit_svi": True,
            "rows": [
                {"option_type": "put", "strike": 90, "time_to_expiry": 0.25, "market_price": 1.2},
                {"option_type": "call", "strike": 100, "time_to_expiry": 0.25, "market_price": 5.0},
                {"option_type": "call", "strike": 110, "time_to_expiry": 0.25, "market_price": 1.5},
            ],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["surface"]["summary"]["valid_row_count"] == 3


@pytest.mark.parametrize(
    "payload",
    [
        # empty rows
        {"underlying_price": 100, "risk_free_rate": 0.05, "rows": []},
        # negative underlying
        {"underlying_price": -1, "risk_free_rate": 0.05, "rows": [{"option_type": "call", "strike": 100, "time_to_expiry": 0.25, "market_price": 5.0}]},
        # bad strike
        {"underlying_price": 100, "risk_free_rate": 0.05, "rows": [{"option_type": "call", "strike": 0, "time_to_expiry": 0.25, "market_price": 5.0}]},
        # bad market price
        {"underlying_price": 100, "risk_free_rate": 0.05, "rows": [{"option_type": "call", "strike": 100, "time_to_expiry": 0.25, "market_price": 0}]},
    ],
)
def test_api_surface_validation_422(client, payload):
    assert client.post("/options/surface", json=payload).status_code == 422


def test_api_surface_too_many_rows_422(client):
    rows = [{"option_type": "call", "strike": 100, "time_to_expiry": 0.25, "market_price": 5.0}] * 1001
    resp = client.post(
        "/options/surface",
        json={"underlying_price": 100, "risk_free_rate": 0.05, "rows": rows},
    )
    assert resp.status_code == 422
