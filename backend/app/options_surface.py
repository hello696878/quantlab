"""
Implied-volatility surface research v1 — build an IV surface from a **manual or
synthetic** option chain, summarise the smile / skew / term structure, and fit a
per-expiry **SVI** smile (research approximation).

Educational / research only.  This is **not** a live options data terminal and
**not** a production volatility-calibration engine:

* No live option chains — the chain is either user-supplied rows or a synthetic
  sample generated from Black-Scholes plus a parametric skew/smile.
* Surface quality depends on the option prices, strike/expiry coverage,
  dividends, rates, and IV-solver stability.  A single bad row never crashes the
  surface — it is kept with ``implied_volatility = null`` and a warning.
* The SVI fit is a least-squares **research approximation**; it enforces the
  basic parameter constraints (b ≥ 0, |rho| < 1, sigma > 0) but does **not**
  guarantee a static-arbitrage-free surface.

Reuses :func:`app.options.black_scholes_price` and the existing
:func:`app.options.implied_volatility` solver — the IV solver is not duplicated.
All outputs are finite and rounded for JSON; invalid cells are ``null``.
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

from app.options import black_scholes_price, implied_volatility

MAX_SURFACE_ROWS = 1000
MIN_SVI_POINTS = 5
_ATM_LOG_MONEYNESS_TOL = math.log(1.02)  # nearest-forward-ATM warning threshold

# Defaults for the synthetic sample chain.
DEFAULT_EXPIRY_DAYS = [30, 60, 90, 180, 365]
DEFAULT_STRIKES = [70.0, 80.0, 90.0, 95.0, 100.0, 105.0, 110.0, 120.0, 130.0]


class SurfaceInputError(ValueError):
    """Raised when surface inputs are structurally invalid (e.g. too many rows)."""


def _clean(value: Optional[float], digits: int = 6) -> Optional[float]:
    if value is None:
        return None
    f = float(value)
    return round(f, digits) if math.isfinite(f) else None


def compute_moneyness(strike: float, underlying: float) -> float:
    return strike / underlying


def compute_log_moneyness(strike: float, forward: float) -> float:
    return math.log(strike / forward)


# ---------------------------------------------------------------------------
# Synthetic sample chain
# ---------------------------------------------------------------------------


def _synthetic_iv(k: float, T: float, base: float, skew: float, smile: float, term: float) -> float:
    """A parametric synthetic IV: ATM level rises with maturity, negative skew
    (lower strikes richer), convex smile in the wings.  Clamped to a sane band."""
    iv = base + term * math.sqrt(T) - skew * k + smile * k * k
    return min(5.0, max(0.01, iv))


def generate_sample_chain(
    underlying_price: float,
    risk_free_rate: float,
    dividend_yield: float,
    base_vol: float = 0.20,
    skew: float = 0.15,
    smile: float = 0.30,
    term: float = 0.02,
    expiry_days: Sequence[float] = DEFAULT_EXPIRY_DAYS,
    strikes: Sequence[float] = DEFAULT_STRIKES,
) -> List[dict]:
    """Build a synthetic OTM option chain priced from Black-Scholes + a smile.

    Out-of-the-money options (puts below the forward, calls above) give the most
    stable IV recovery.  Returns rows shaped like the manual-input rows.
    """
    for name, value in (
        ("underlying_price", underlying_price),
        ("risk_free_rate", risk_free_rate),
        ("dividend_yield", dividend_yield),
        ("base_vol", base_vol),
        ("skew", skew),
        ("smile", smile),
        ("term", term),
    ):
        if not math.isfinite(float(value)):
            raise SurfaceInputError(f"{name} must be finite.")
    if underlying_price <= 0 or base_vol <= 0:
        raise SurfaceInputError("underlying_price and base_vol must be positive.")
    if dividend_yield < 0:
        raise SurfaceInputError("dividend_yield must be non-negative.")
    for days in expiry_days:
        if not math.isfinite(float(days)) or days <= 0:
            raise SurfaceInputError("expiry_days must contain positive finite values.")
    for strike in strikes:
        if not math.isfinite(float(strike)) or strike <= 0:
            raise SurfaceInputError("strikes must contain positive finite values.")

    rows: List[dict] = []
    for days in expiry_days:
        T = days / 365.0
        forward = underlying_price * math.exp((risk_free_rate - dividend_yield) * T)
        for strike in strikes:
            k = math.log(strike / forward)
            iv = _synthetic_iv(k, T, base_vol, skew, smile, term)
            option_type = "put" if strike < forward else "call"
            price = black_scholes_price(
                option_type, underlying_price, strike, T, risk_free_rate, iv, dividend_yield
            )
            rows.append(
                {
                    "option_type": option_type,
                    "strike": float(strike),
                    "time_to_expiry": T,
                    "market_price": round(float(price), 8),
                }
            )
    return rows


# ---------------------------------------------------------------------------
# Per-row implied volatility
# ---------------------------------------------------------------------------


def compute_option_chain_iv(
    rows: Sequence[dict],
    underlying_price: float,
    risk_free_rate: float,
    dividend_yield: float,
) -> List[dict]:
    """Extract implied volatility per row using the existing bisection solver.

    A row that fails to solve is kept with ``implied_volatility = null`` and a
    warning — the surface is never aborted because of one bad quote.
    """
    out: List[dict] = []
    for row in rows:
        option_type = row["option_type"]
        strike = float(row["strike"])
        T = float(row["time_to_expiry"])
        market_price = float(row["market_price"])
        forward = underlying_price * math.exp((risk_free_rate - dividend_yield) * T)
        moneyness = compute_moneyness(strike, underlying_price)
        log_moneyness = compute_log_moneyness(strike, forward)

        iv, converged, _iters, warning = implied_volatility(
            option_type, market_price, underlying_price, strike, T, risk_free_rate, dividend_yield
        )
        valid = converged and iv is not None and math.isfinite(iv)
        out.append(
            {
                "option_type": option_type,
                "strike": _clean(strike),
                "expiry_days": _clean(T * 365.0, 2),
                "time_to_expiry": _clean(T),
                "market_price": _clean(market_price),
                "implied_volatility": _clean(iv) if valid else None,
                "moneyness": _clean(moneyness),
                "log_moneyness": _clean(log_moneyness),
                "solver_converged": bool(valid),
                "warning": None if valid else (warning or "Implied volatility did not converge."),
            }
        )
    return out


# ---------------------------------------------------------------------------
# SVI smile fit (per expiry)
# ---------------------------------------------------------------------------


def evaluate_svi(params: dict, k: float) -> float:
    """SVI total variance ``w(k) = a + b[rho(k−m) + sqrt((k−m)² + sigma²)]``."""
    a, b, rho, m, sig = params["a"], params["b"], params["rho"], params["m"], params["sigma"]
    return a + b * (rho * (k - m) + math.sqrt((k - m) ** 2 + sig * sig))


def fit_svi_slice(
    log_moneyness: Sequence[float],
    ivs: Sequence[Optional[float]],
    T: float,
    min_points: int = MIN_SVI_POINTS,
) -> dict:
    """Least-squares SVI fit on one expiry slice (total variance ``w = iv²·T``).

    Returns ``{fitted, params, rmse, points, warning}``.  Fails gracefully —
    insufficient points or a missing/failed optimizer returns ``fitted = False``
    with a warning rather than raising.
    """
    pts = [
        (float(k), float(v))
        for k, v in zip(log_moneyness, ivs)
        if v is not None and math.isfinite(v)
    ]
    base = {
        "fitted": False,
        "params": None,
        "rmse": None,
        "points": [
            {"log_moneyness": _clean(k), "iv_observed": _clean(v), "iv_svi": None}
            for k, v in pts
        ],
    }
    if len(pts) < min_points:
        base["warning"] = (
            f"Insufficient valid IV points for an SVI fit (have {len(pts)}, need >= {min_points})."
        )
        return base

    try:
        import numpy as np
        from scipy.optimize import least_squares
    except Exception:  # pragma: no cover - scipy is a project dependency
        base["warning"] = "SVI fit requires scipy, which is not available in this environment."
        return base

    k_arr = np.array([p[0] for p in pts], dtype=float)
    iv_arr = np.array([p[1] for p in pts], dtype=float)
    w_arr = iv_arr**2 * T  # total variance

    def residuals(theta):
        a, b, rho, m, sig = theta
        model = a + b * (rho * (k_arr - m) + np.sqrt((k_arr - m) ** 2 + sig * sig))
        return model - w_arr

    w_max = float(w_arr.max())
    x0 = [max(float(w_arr.min()) * 0.5, 1e-6), 0.1, -0.3, 0.0, 0.1]
    lower = [-abs(w_max) - 1.0, 0.0, -0.999, -1.0, 1e-4]
    upper = [abs(w_max) + 1.0, 10.0, 0.999, 1.0, 5.0]
    try:
        sol = least_squares(residuals, x0, bounds=(lower, upper), max_nfev=3000)
    except Exception as exc:  # pragma: no cover - defensive
        base["warning"] = f"SVI optimizer failed: {exc}"
        return base

    a, b, rho, m, sig = (float(v) for v in sol.x)
    params = {
        "a": _clean(a),
        "b": _clean(b),
        "rho": _clean(rho),
        "m": _clean(m),
        "sigma": _clean(sig),
    }
    model_w = a + b * (rho * (k_arr - m) + np.sqrt((k_arr - m) ** 2 + sig * sig))
    model_iv = np.sqrt(np.maximum(model_w, 0.0) / T)
    rmse = float(np.sqrt(np.mean((model_iv - iv_arr) ** 2)))
    points = [
        {
            "log_moneyness": _clean(float(k_arr[i])),
            "iv_observed": _clean(float(iv_arr[i])),
            "iv_svi": _clean(float(model_iv[i])),
        }
        for i in range(len(pts))
    ]
    return {
        "fitted": True,
        "params": params,
        "rmse": _clean(rmse),
        "points": points,
        "warning": None if math.isfinite(rmse) else "SVI RMSE is non-finite.",
    }


# ---------------------------------------------------------------------------
# Grid / smile / term structure / skew
# ---------------------------------------------------------------------------


def build_vol_surface_grid(rows: Sequence[dict]) -> dict:
    """Surface matrix indexed ``[expiry_index][moneyness_index]`` (null when missing).

    The shared x-axis is **moneyness = K/S** (expiry-independent); per-row true
    forward log-moneyness lives on each row instead.
    """
    expiries = sorted({round(r["time_to_expiry"], 6) for r in rows})
    moneyness_values = sorted({round(r["moneyness"], 4) for r in rows})
    exp_index = {e: i for i, e in enumerate(expiries)}
    mon_index = {m: j for j, m in enumerate(moneyness_values)}

    sums = [[0.0] * len(moneyness_values) for _ in expiries]
    counts = [[0] * len(moneyness_values) for _ in expiries]
    for r in rows:
        iv = r["implied_volatility"]
        if iv is None:
            continue
        i = exp_index[round(r["time_to_expiry"], 6)]
        j = mon_index[round(r["moneyness"], 4)]
        sums[i][j] += iv
        counts[i][j] += 1

    matrix = [
        [(_clean(sums[i][j] / counts[i][j]) if counts[i][j] else None) for j in range(len(moneyness_values))]
        for i in range(len(expiries))
    ]
    return {
        "expiries": [_clean(e) for e in expiries],
        "expiry_days": [_clean(e * 365.0, 2) for e in expiries],
        "moneyness_values": [_clean(m, 4) for m in moneyness_values],
        "log_moneyness_values": [_clean(math.log(m)) for m in moneyness_values],
        "surface_matrix": matrix,
    }


def _rows_by_expiry(rows: Sequence[dict]) -> List[Tuple[float, List[dict]]]:
    expiries = sorted({round(r["time_to_expiry"], 6) for r in rows})
    groups: List[Tuple[float, List[dict]]] = []
    for e in expiries:
        slice_rows = sorted(
            (r for r in rows if round(r["time_to_expiry"], 6) == e),
            key=lambda r: r["moneyness"],
        )
        groups.append((e, slice_rows))
    return groups


def _nearest_valid(rows: Sequence[dict], target_moneyness: float) -> Optional[dict]:
    valid = [r for r in rows if r["implied_volatility"] is not None]
    if not valid:
        return None
    return min(valid, key=lambda r: abs(r["moneyness"] - target_moneyness))


def _nearest_forward_atm(rows: Sequence[dict]) -> Optional[dict]:
    valid = [r for r in rows if r["implied_volatility"] is not None]
    if not valid:
        return None
    return min(valid, key=lambda r: abs(r["log_moneyness"]))


def build_smiles(rows: Sequence[dict], svi_fits_by_expiry: dict) -> List[dict]:
    smiles = []
    for expiry, slice_rows in _rows_by_expiry(rows):
        fit = svi_fits_by_expiry.get(expiry)
        points = []
        for r in slice_rows:
            svi_iv = None
            if fit and fit.get("fitted") and fit.get("params") is not None:
                w = evaluate_svi(fit["params"], r["log_moneyness"])
                svi_iv = _clean(math.sqrt(max(w, 0.0) / expiry)) if expiry > 0 else None
            points.append(
                {
                    "strike": r["strike"],
                    "moneyness": r["moneyness"],
                    "log_moneyness": r["log_moneyness"],
                    "implied_volatility": r["implied_volatility"],
                    "option_type": r["option_type"],
                    "fitted_svi_iv": svi_iv,
                }
            )
        smiles.append(
            {"time_to_expiry": _clean(expiry), "expiry_days": _clean(expiry * 365.0, 2), "points": points}
        )
    return smiles


def build_term_structure(rows: Sequence[dict]) -> List[dict]:
    term = []
    for expiry, slice_rows in _rows_by_expiry(rows):
        atm = _nearest_forward_atm(slice_rows)
        warning = None
        if atm is None:
            atm_iv = None
            nearest_strike = None
        else:
            atm_iv = atm["implied_volatility"]
            nearest_strike = atm["strike"]
            if abs(atm["log_moneyness"]) > _ATM_LOG_MONEYNESS_TOL:
                warning = "ATM IV is approximated from the nearest available strike to the forward."
        term.append(
            {
                "expiry_days": _clean(expiry * 365.0, 2),
                "time_to_expiry": _clean(expiry),
                "atm_iv": atm_iv,
                "nearest_atm_strike": nearest_strike,
                "warning": warning,
            }
        )
    return term


def build_skew(rows: Sequence[dict]) -> List[dict]:
    skews = []
    for expiry, slice_rows in _rows_by_expiry(rows):
        low = _nearest_valid(slice_rows, 0.9)
        atm = _nearest_valid(slice_rows, 1.0)
        high = _nearest_valid(slice_rows, 1.1)
        low_iv = low["implied_volatility"] if low else None
        atm_iv = atm["implied_volatility"] if atm else None
        high_iv = high["implied_volatility"] if high else None
        skew = _clean(low_iv - high_iv) if (low_iv is not None and high_iv is not None) else None
        skews.append(
            {
                "expiry_days": _clean(expiry * 365.0, 2),
                "time_to_expiry": _clean(expiry),
                "low_moneyness_iv": low_iv,
                "atm_iv": atm_iv,
                "high_moneyness_iv": high_iv,
                "skew": skew,
            }
        )
    return skews


# ---------------------------------------------------------------------------
# Validation + orchestration
# ---------------------------------------------------------------------------


def validate_surface_inputs(
    underlying_price: float,
    risk_free_rate: float,
    dividend_yield: float,
    rows: Sequence[dict],
) -> None:
    for name, value in (
        ("underlying_price", underlying_price),
        ("risk_free_rate", risk_free_rate),
        ("dividend_yield", dividend_yield),
    ):
        if not math.isfinite(float(value)):
            raise SurfaceInputError(f"{name} must be finite.")
    if underlying_price <= 0:
        raise SurfaceInputError("underlying_price must be positive.")
    if dividend_yield < 0:
        raise SurfaceInputError("dividend_yield must be non-negative.")
    if not rows:
        raise SurfaceInputError("At least one option row is required.")
    if len(rows) > MAX_SURFACE_ROWS:
        raise SurfaceInputError(f"Too many rows ({len(rows)}); the cap is {MAX_SURFACE_ROWS}.")
    for idx, row in enumerate(rows):
        if row.get("option_type") not in {"call", "put"}:
            raise SurfaceInputError(f"row {idx}: option_type must be 'call' or 'put'.")
        for name in ("strike", "time_to_expiry", "market_price"):
            if name not in row:
                raise SurfaceInputError(f"row {idx}: {name} is required.")
            try:
                value = float(row[name])
            except (TypeError, ValueError):
                raise SurfaceInputError(f"row {idx}: {name} must be numeric.") from None
            if not math.isfinite(value) or value <= 0:
                raise SurfaceInputError(f"row {idx}: {name} must be positive and finite.")


def summarize_surface(rows: Sequence[dict], grid: dict, svi_fitted_count: int) -> dict:
    valid = [r for r in rows if r["implied_volatility"] is not None]
    failed = [r for r in rows if r["implied_volatility"] is None]
    ivs = [r["implied_volatility"] for r in valid]
    atm = _nearest_forward_atm(rows)
    return {
        "valid_row_count": len(valid),
        "failed_row_count": len(failed),
        "min_iv": _clean(min(ivs)) if ivs else None,
        "max_iv": _clean(max(ivs)) if ivs else None,
        "atm_iv_nearest": atm["implied_volatility"] if atm else None,
        "expiries_count": len(grid["expiries"]),
        "strikes_count": len(grid["moneyness_values"]),
        "svi_fitted_count": svi_fitted_count,
    }


def build_surface(
    underlying_price: float,
    risk_free_rate: float,
    dividend_yield: float,
    rows: Sequence[dict],
    fit_svi: bool = True,
) -> dict:
    """Full IV-surface pipeline → a JSON-ready ``{"surface": {...}}`` dict."""
    validate_surface_inputs(underlying_price, risk_free_rate, dividend_yield, rows)

    iv_rows = compute_option_chain_iv(rows, underlying_price, risk_free_rate, dividend_yield)
    grid = build_vol_surface_grid(iv_rows)

    svi_fits: List[dict] = []
    svi_fits_by_expiry: dict = {}
    svi_fitted_count = 0
    for expiry, slice_rows in _rows_by_expiry(iv_rows):
        if fit_svi:
            fit = fit_svi_slice(
                [r["log_moneyness"] for r in slice_rows],
                [r["implied_volatility"] for r in slice_rows],
                expiry,
            )
        else:
            fit = {
                "fitted": False,
                "params": None,
                "rmse": None,
                "points": [],
                "warning": "SVI fitting disabled.",
            }
        if fit.get("fitted"):
            svi_fitted_count += 1
        svi_fits_by_expiry[expiry] = fit
        svi_fits.append(
            {
                "time_to_expiry": _clean(expiry),
                "expiry_days": _clean(expiry * 365.0, 2),
                **fit,
            }
        )

    smiles = build_smiles(iv_rows, svi_fits_by_expiry)
    term_structure = build_term_structure(iv_rows)
    skew = build_skew(iv_rows)
    summary = summarize_surface(iv_rows, grid, svi_fitted_count)

    warnings: List[str] = []
    if summary["failed_row_count"]:
        warnings.append(
            f"{summary['failed_row_count']} of {len(iv_rows)} rows did not produce a valid "
            "implied volatility (kept with null IV)."
        )
    if fit_svi and svi_fitted_count == 0:
        warnings.append("No expiry had enough valid IV points for an SVI fit.")
    warnings.append(
        "Research surface from a manual/synthetic chain — not live market data and not an "
        "arbitrage-free calibration."
    )

    return {
        "surface": {
            "rows": iv_rows,
            "grid": grid,
            "smiles": smiles,
            "term_structure": term_structure,
            "skew": skew,
            "svi_fits": svi_fits,
            "summary": summary,
            "warnings": warnings,
        }
    }


def build_sample_surface(
    underlying_price: float = 100.0,
    risk_free_rate: float = 0.05,
    dividend_yield: float = 0.0,
    base_vol: float = 0.20,
    skew: float = 0.15,
    smile: float = 0.30,
    term: float = 0.02,
    fit_svi: bool = True,
) -> dict:
    """Generate a synthetic chain and build its surface (sample endpoint)."""
    rows = generate_sample_chain(
        underlying_price, risk_free_rate, dividend_yield, base_vol, skew, smile, term
    )
    return build_surface(underlying_price, risk_free_rate, dividend_yield, rows, fit_svi)
