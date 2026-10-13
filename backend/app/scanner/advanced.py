"""Current cross-sectional transformations, not time-series return residual signals."""
from datetime import datetime, timezone
import math

import numpy as np

from app.factor_diagnostics.regression import RegressionError, ols_fit
from app.run_replay.identity import digest
from app.scanner.neutralize import dollar_neutral_weights
from app.scanner.policies import NeutralisationPolicy, ScannerInputs

TOLERANCE = 1e-9
RCOND = 1e-12
MAX_ADVANCED_ASSETS = 50
MAX_ADVANCED_DATES = 1000


def cutoff(period):
    return datetime.fromisoformat(period).replace(tzinfo=timezone.utc)


def keyed_panel(universe, scores, inputs=None):
    """Join declarations by (session, asset), never by submitted row order."""
    dates, assets = universe["dates"], universe["tickers"]
    n, m = len(dates), len(assets)
    if n > MAX_ADVANCED_DATES or m > MAX_ADVANCED_ASSETS or n * m * m > 2500000:
        raise ValueError("advanced scanner supports at most 50 assets, 1000 dates and 2500000 date-asset-squared units")
    if len(set(dates)) != n or dates != sorted(dates) or len(set(assets)) != m:
        raise ValueError("duplicate or unordered panel identities")
    prices, returns = np.asarray(universe["prices"]), np.asarray(universe["returns"])
    if prices.shape != (n, m) or returns.shape != (n, m) or scores.shape != (n, m):
        raise ValueError("panel dimensions do not match actual session/asset keys")
    if not np.isfinite(prices).all() or not np.isfinite(returns).all() or (prices <= 0).any():
        raise ValueError("analytical prices/returns must be finite and prices positive")
    if np.isinf(scores).any():
        raise ValueError("infinite analytical scores are not unavailable warmup values")
    if not np.allclose(returns[1:], prices[1:] / prices[:-1] - 1, rtol=1e-12, atol=1e-14):
        raise ValueError("return intervals do not match close-to-close prices")
    if not np.isfinite(universe["liquidity"]).all() or len(universe["sectors"]) != m:
        raise ValueError("invalid synthetic declarations")
    declarations = ScannerInputs.model_validate(inputs or {})
    rows, factors = {}, {}
    for row in declarations.exposures or []:
        key = (row.period, row.asset_id)
        if row.period not in dates or row.asset_id not in assets or key in rows:
            raise ValueError("duplicate or unknown exposure session/asset key")
        rows[key] = row
    for row in declarations.factor_returns or []:
        if row.period not in dates or row.period in factors:
            raise ValueError("duplicate or unknown factor session key")
        factors[row.period] = row
    material = {"schema_version": "scanner_panel_v1", "asset_ids": assets, "sessions": dates,
                "sector_provenance": "static_supplied_synthetic" if declarations.exposures is None else "time_varying_declared",
                "default_beta_reference": "synthetic_equal_weight_returns" if declarations.factor_returns is None else "declared_factor_returns",
                "information_policy": "synthetic session t UTC midnight cutoff; returns[t] ends at t; holdings[t] earn returns[t+1]",
                "prices": prices.tolist(), "returns": returns.tolist(),
                "scores": [[float(v) if np.isfinite(v) else None for v in row] for row in scores],
                "sectors": dict(zip(assets, universe["sectors"])),
                "liquidity": dict(zip(assets, map(float, universe["liquidity"]))),
                "declarations": declarations.model_dump(mode="json")}
    return {"universe": universe, "scores": scores, "rows": rows, "factors": factors,
            "declarations": declarations, "material": material, "fingerprint": digest(material)}


def exposure(weights, sectors, betas):
    known = sorted({s for s in sectors if s is not None})
    held = np.abs(weights) > 0
    beta = float(weights[held] @ betas[held]) if np.isfinite(betas[held]).all() else None
    if not held.any():
        beta = 0.0
    return {"net": float(weights.sum()), "gross": float(np.abs(weights).sum()),
            "sectors": {s: float(sum(weights[i] for i, label in enumerate(sectors) if label == s)) for s in known},
            "beta": beta}


def _inputs_at(panel, t, policy, min_liquidity):
    uni = panel["universe"]
    dates, assets = uni["dates"], uni["tickers"]
    sectors = list(uni["sectors"])
    betas = np.full(len(assets), np.nan)
    eligible = np.isfinite(panel["scores"][t])
    exclusions = []
    custom = panel["declarations"].exposures is not None
    end = cutoff(dates[t])
    if policy.mode == "beta" and not custom:
        indices = list(range(max(1, t - policy.beta_window + 1), t + 1))
        factor = []
        for i in indices:
            if panel["declarations"].factor_returns is None:
                factor.append(float(np.mean(uni["returns"][i])))
            else:
                row = panel["factors"].get(dates[i])
                factor.append(row.value if row and datetime.fromisoformat(row.available_at) <= end else math.nan)
        if len(indices) >= policy.beta_min_observations and np.isfinite(factor).all():
            x = np.asarray(factor)
            centred = x - x.mean()
            variance = float(centred @ centred)
            if variance > 1e-20:
                y = uni["returns"][indices]
                betas = centred @ (y - y.mean(axis=0)) / variance
    for j, asset in enumerate(assets):
        reason = None
        if custom:
            row = panel["rows"].get((dates[t], asset))
            sectors[j] = row.sector if row else None
            betas[j] = row.beta if row and row.beta is not None else math.nan
            if not row:
                reason = "missing_declaration"
            elif datetime.fromisoformat(row.available_at) > end:
                reason = "not_available_at_cutoff"
            elif not row.eligible:
                reason = "declared_ineligible"
            elif row.liquidity < min_liquidity:
                reason = "liquidity_filter"
        elif uni["liquidity"][j] < min_liquidity:
            reason = "liquidity_filter"
        if reason is None and policy.mode == "sector" and not sectors[j]:
            reason = "unknown_sector"
        if reason is None and policy.mode == "beta" and (not np.isfinite(betas[j]) or abs(betas[j]) > 20):
            reason = "unavailable_beta"
        if reason or not eligible[j]:
            eligible[j] = False
            exclusions.append({"asset_id": asset, "reason": reason or "score_warmup"})
    return sectors, betas, eligible, exclusions


def neutralise(row, eligible, sectors, betas, policy, long_quantile, short_quantile, gross):
    """Project only selected support; signs may change, unselected names never enter."""
    n = len(row)
    zero = np.zeros(n)
    indices = np.flatnonzero(eligible)
    raw, _, _, _ = dollar_neutral_weights(row, eligible, long_quantile, short_quantile, gross)
    transformed = np.full(n, np.nan)
    report = {"rank": None, "columns": None, "condition_number": None, "reconstruction_error": None,
              "support_rank": None, "raw": exposure(raw, sectors, betas),
              "transformed": exposure(zero, sectors, betas)}
    if len(indices) < 3:
        return zero, transformed, report, "infeasible", "fewer than three eligible assets"
    labels = sorted({sectors[i] for i in indices}) if policy.mode == "sector" else []
    # Intercept + K-1 dummies encodes all sector nets without structural redundancy.
    columns = ([np.asarray([float(sectors[i] == s) for i in indices]) for s in labels[1:]]
               if policy.mode == "sector" else [betas[indices]] if policy.mode == "beta" else [])
    factors = np.column_stack(columns) if columns else np.empty((len(indices), 0))
    try:
        fit = ols_fit(row[indices].tolist(), factors.tolist(),
                      [f"exposure_{i}" for i in range(len(columns))], intercept=True, rank_policy="fail")
    except (RegressionError, np.linalg.LinAlgError):
        return zero, transformed, report, "rank_failure", "cross-sectional design is unidentified or too small"
    design = np.column_stack([np.ones(len(indices)), factors])
    singular = np.linalg.svd(design, compute_uv=False)
    design_condition = float(singular[0] / singular[-1]) if singular[-1] > 0 else math.inf
    condition = max(design_condition, fit["condition_number"] or 0.0)
    report.update(rank=fit["rank"], columns=1 + len(columns),
                  condition_number=condition if math.isfinite(condition) else None)
    if not math.isfinite(condition) or condition > 1e8:
        return zero, transformed, report, "rank_failure", "cross-sectional design is ill-conditioned"
    residual = np.asarray(fit["residuals"])
    transformed[indices] = residual
    report["reconstruction_error"] = float(np.max(np.abs(row[indices] - np.asarray(fit["fitted"]) - residual)))
    if np.linalg.norm(residual) <= RCOND * max(1.0, float(np.linalg.norm(row[indices]))):
        return zero, transformed, report, "no_signal", "scores are explained by the declared exposures"
    selected, _, _, ok = dollar_neutral_weights(transformed, eligible, long_quantile, short_quantile, gross)
    report["transformed"] = exposure(selected, sectors, betas)
    if not ok:
        return zero, transformed, report, "no_signal", "no transformed score spread"
    support = np.flatnonzero(selected)
    support_design = design[np.isin(indices, support)]
    # The same explicit SVD tolerance controls rank and the minimum-norm projection.
    coefficients, _, rank, _ = np.linalg.lstsq(support_design, selected[support], rcond=RCOND)
    direction = selected[support] - support_design @ coefficients
    report["support_rank"] = int(rank)
    if rank >= len(support):
        return zero, transformed, report, "infeasible", "selected support has no nonzero constraint nullspace"
    if np.linalg.norm(direction) <= RCOND * max(1.0, float(np.linalg.norm(selected[support]))):
        return zero, transformed, report, "infeasible", "selected support has no nonzero neutral direction"
    final = zero.copy()
    final[support] = direction * gross / np.sum(np.abs(direction))
    return final, transformed, report, "ok", None


def _constraint_error(weights, sectors, betas, mode):
    report = exposure(weights, sectors, betas)
    error = abs(report["net"])
    if not np.any(weights):
        return error
    if mode == "sector":
        error = max([error, *map(abs, report["sectors"].values())])
    elif mode == "beta":
        if report["beta"] is None:
            return math.inf
        error = max(error, abs(report["beta"]) / max(1.0, float(np.nanmax(np.abs(betas)))))
    return error


def advanced_weights(panel, rebalance_indices, policy, *, long_quantile, short_quantile, gross, min_liquidity):
    policy = NeutralisationPolicy.model_validate(policy)
    uni, scores = panel["universe"], panel["scores"]
    weights = np.zeros_like(scores)
    previous = np.zeros(scores.shape[1])
    diagnostics, used, latest = [], [], []
    for t in range(len(scores)):
        if t in rebalance_indices:
            sectors, betas, eligible, excluded = _inputs_at(panel, t, policy, min_liquidity)
            w, transformed, report, status, reason = neutralise(scores[t], eligible, sectors, betas, policy,
                                                               long_quantile, short_quantile, gross)
            if policy.missing == "refuse" and any(r["reason"] not in {"score_warmup", "liquidity_filter", "declared_ineligible"} for r in excluded):
                w = np.zeros_like(w)
                status, reason = "missing_input", "required declarations unavailable; entire rebalance goes to cash"
            neutral = exposure(w, sectors, betas)
            estimate, scale, achieved = None, None, None
            cap_binding = False
            if status == "ok":
                scale = min(1.0, policy.gross_cap / gross)
                if policy.volatility:
                    reference = policy.volatility
                    history = uni["returns"][max(1, t - reference.window + 1):t + 1]
                    if len(history) < reference.min_observations:
                        status, reason = "volatility_unavailable", "insufficient trailing volatility observations"
                    else:
                        estimate = float(np.std(history @ w, ddof=1) * math.sqrt(reference.periods_per_year))
                        if estimate <= 1e-12 or not math.isfinite(estimate):
                            status, reason = "volatility_unavailable", "zero or unknown fixed-weight variance"
                        else:
                            desired = reference.target / estimate
                            scale = min(desired, policy.gross_cap / gross)
                            cap_binding = scale < desired
                            achieved = estimate * scale
                else:
                    cap_binding = gross > policy.gross_cap
                w = w * scale if status == "ok" else np.zeros_like(w)
            error = _constraint_error(w, sectors, betas, policy.mode)
            if not np.isfinite(w).all() or error > TOLERANCE * max(1.0, float(np.abs(w).sum())):
                w = np.zeros_like(w)
                status, reason = "constraint_failure", "final scaled constraints failed; rebalance goes to cash"
                error = 0.0
            if status != "ok":
                scale = 0.0
                achieved = 0.0 if estimate is not None else None
            previous = w
            if status == "ok":
                used.append(t)
            diagnostics.append({"date": uni["dates"][t], "status": status, "reason": reason,
                                "eligible_count": int(eligible.sum()), "excluded": excluded, **report,
                                "neutral": neutral, "final": exposure(w, sectors, betas),
                                "volatility_estimate": estimate,
                                "volatility_target": policy.volatility.target if policy.volatility else None,
                                "volatility_scale": scale, "achieved_ex_ante": achieved,
                                "cap_binding": cap_binding, "constraint_error": error})
            latest = [{"asset_id": a, "raw_score": float(scores[t, j]) if np.isfinite(scores[t, j]) else None,
                       "transformed_score": float(transformed[j]) if np.isfinite(transformed[j]) else None,
                       "weight": float(w[j]), "sector": sectors[j],
                       "beta": float(betas[j]) if np.isfinite(betas[j]) else None} for j, a in enumerate(uni["tickers"])]
        weights[t] = previous
    return {"weights": weights, "used": used, "diagnostics": diagnostics, "latest_scores": latest,
            "panel": panel, "policy": policy}


def public_advanced(internal, pnl):
    policy, panel = internal["policy"], internal["panel"]
    net_returns = pnl["net"]
    dates = panel["universe"]["dates"]
    by_date = {day: i for i, day in enumerate(dates)}
    rows = []
    for diagnostic in internal["diagnostics"][-100:]:
        t = by_date[diagnostic["date"]]
        rows.append({**diagnostic, "outcome_date": dates[t + 1], "turnover": float(pnl["turnover"][t]),
                     "cost": float(pnl["cost"][t]), "gross_return": float(pnl["gross"][t + 1]),
                     "net_return": float(pnl["net"][t + 1])})
    return {"policy": policy.model_dump(mode="json"), "input_fingerprint": panel["fingerprint"],
            "exposure_provenance": "time_varying_declared" if panel["declarations"].exposures is not None else "static_supplied_synthetic_sectors; beta is trailing estimated, never generator truth",
            "factor_provenance": "declared_single_factor_returns" if panel["declarations"].factor_returns is not None else "synthetic_equal_weight_return_reference (endogenous proxy, not latent market factor)",
            "timing": "session t synthetic UTC cutoff -> weights[t] -> return[t+1]; cost from turnover[t] deducted once at t+1",
            "support_policy": "rank transformed scores; SVD projection on selected names only; signs may change; no new names",
            "failed_rebalance": "cash, including exit turnover; legacy carry is not used",
            "diagnostics": rows, "total_rebalances": len(internal["diagnostics"]),
            "diagnostics_truncated": len(internal["diagnostics"]) > 100, "latest_scores": internal["latest_scores"],
            "realized_net_volatility": float(np.std(net_returns[1:], ddof=1) * math.sqrt(252)) if len(net_returns) > 2 else 0.0,
            "caveats": ["Synthetic universe includes disclosed reversal; no market alpha claim or historical classification certification.",
                        "Current cross-sectional OLS is descriptive; its inferential coefficients/p-values are not exposed.",
                        "Fixed-weight trailing sample volatility, ddof=1, 252/year; no covariance inverse. Realized volatility need not equal target.",
                        "No borrow, impact, capacity or real fills. No terminal liquidation beyond the existing scanner convention.",
                        "Full precision internally; public chart previews remain rounded/downsampled. Constraint tolerance 1e-9 times max(1,gross); beta additionally exposure-scaled."]}
