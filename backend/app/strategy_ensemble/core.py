"""Pure, deterministic period diagnostics. No providers, selection or execution."""

import math
from itertools import combinations

import numpy as np

from app.experiment_registry.fingerprints import sha256_hex
from app.overfitting_diagnostics.multiple_testing import adjust_p_values
from app.signal_decay.statistics import correlation
from .models import AnalysisPolicy, RunCreate, WeightPolicy


def aligned(request: RunCreate):
    streams = {d.strategy_id: {} for d in request.definitions}
    for row in request.observations:
        streams[row.strategy_id][(row.period_start, row.period_end)] = row
    common = sorted(set.intersection(*(set(s) for s in streams.values())))
    union = set.union(*(set(s) for s in streams.values()))
    coverage = [{"strategy_id": k, "stored_periods": len(s),
                 "missing_periods": len(union - set(s)),
                 "excluded_periods": len(s) - len(common),
                 "coverage_ratio": len(common) / len(s)} for k, s in streams.items()]
    return streams, common, {"strict_intersection_periods": len(common),
                            "union_periods": len(union), "strategies": coverage,
                            "exclusion_reason": "exact period start/end absent from another stream",
                            "gaps": sum(a[1] != b[0] for a, b in zip(common, common[1:]))}


def drawdowns(keys, returns):
    wealth = peak = 1.0
    rows, episodes = [], []
    active = None
    for i, (key, ret) in enumerate(zip(keys, returns)):
        if ret <= -1:
            raise ValueError("ensemble return <= -100% cannot compound")
        wealth *= 1 + ret
        if not math.isfinite(wealth) or wealth <= 0:
            raise ValueError("wealth overflow/underflow; reduce return magnitude or observation window")
        peak = max(peak, wealth)
        dd = wealth / peak - 1
        rows.append({"period_start": key[0], "period_end": key[1],
                     "return_value": float(ret), "wealth": wealth, "running_peak": peak,
                     "drawdown": dd})
        if dd < 0 and active is None:
            active = {"start": key[0], "trough": key[1], "recovery": None,
                      "start_index": i, "end_index": i, "max_drawdown": dd,
                      "duration_periods": 1}
        if active:
            active["end_index"] = i
            active["duration_periods"] = i - active["start_index"] + 1
            if dd < active["max_drawdown"]:
                active.update(trough=key[1], max_drawdown=dd)
            if dd == 0:
                active["recovery"] = key[1]
                episodes.append(active)
                active = None
    if active:
        episodes.append(active)
    return {"periods": rows, "episodes": episodes,
            "max_drawdown": min((r["drawdown"] for r in rows), default=None),
            "compounded_return": wealth - 1 if rows else None}


def weight_details(policy: WeightPolicy, ids: list[str], tolerance: float):
    original = ({k: 1 / len(ids) for k in ids} if policy.mode == "equal_weight"
                else dict(policy.weights))
    if set(original) != set(ids):
        raise ValueError("static weights must contain exactly every strategy ID")
    total = math.fsum(original.values())
    if total <= tolerance:
        raise ValueError("weights must have positive total exposure")
    if policy.normalization == "require_sum_to_one" and abs(total - 1) > tolerance:
        raise ValueError("weights must sum to one under require_sum_to_one")
    divisor = total if policy.normalization in ("normalize_by_sum", "normalize_by_gross") else 1
    effective = {k: original[k] / divisor for k in ids}
    net = math.fsum(effective.values())
    if net > 10 + tolerance:
        raise ValueError("total strategy-return weight is bounded at 10")
    return {"original": original, "effective": effective, "sum": net, "gross": net,
            "net": net, "max_absolute_weight": max(effective.values()),
            "zero_weight_strategies": [k for k, v in effective.items() if v == 0],
            "normalization_residual": net - 1 if policy.normalization != "none" else None}


def pairwise(streams, keys, policy: AnalysisPolicy, histories):
    rows = []
    for a, b in combinations(streams, 2):
        sample = (sorted(set(streams[a]) & set(streams[b]))
                  if policy.pairwise_alignment == "pairwise_complete" else keys)
        x = np.array([streams[a][k].return_value for k in sample])
        y = np.array([streams[b][k].return_value for k in sample])
        n = len(sample)
        valid = n >= policy.minimum_samples
        metrics = {}
        for method in ("pearson", "spearman"):
            c = correlation(x, y, method=method, minimum_observations=policy.minimum_samples,
                            overlapping=False)
            metrics[method] = {"value": c["statistic"], "p_value": c["p_value"], "reason": c["reason"]}
        joint_loss = int(np.sum((x < 0) & (y < 0)))
        joint_gain = int(np.sum((x > 0) & (y > 0)))
        tail = {"state": "unavailable", "reason": "insufficient samples or constant stream"}
        if n >= policy.tail_minimum_samples and np.ptp(x) > 0 and np.ptp(y) > 0:
            qx, qy = float(np.quantile(x, policy.tail_quantile)), float(np.quantile(y, policy.tail_quantile))
            lx, ly = x <= qx, y <= qy
            joint = int(np.sum(lx & ly))
            union = int(np.sum(lx | ly))
            tail = {"state": "available", "reason": None, "quantile": policy.tail_quantile,
                    "ties": policy.tail_ties, "threshold_a": qx, "threshold_b": qy,
                    "joint_count": joint, "jaccard": joint / union if union else None,
                    "b_given_a": joint / int(lx.sum()) if lx.any() else None,
                    "a_given_b": joint / int(ly.sum()) if ly.any() else None,
                    "opposite_tail_rate": float(np.mean(
                        (lx & (y >= np.quantile(y, 1-policy.tail_quantile))) |
                        (ly & (x >= np.quantile(x, 1-policy.tail_quantile)))))}
        da = { (r["period_start"], r["period_end"]): r["drawdown"] for r in histories[a]["periods"]}
        db = { (r["period_start"], r["period_end"]): r["drawdown"] for r in histories[b]["periods"]}
        deepest = []
        for s in (a, b):
            episodes = histories[s]["episodes"]
            e = min(episodes, key=lambda e: e["max_drawdown"]) if episodes else None
            source_keys = sorted(streams[s])
            deepest.append(set(source_keys[e["start_index"]:e["end_index"]+1]) if e else set())
        rows.append({"strategy_a": a, "strategy_b": b, "n": n,
                     "alignment": policy.pairwise_alignment, "correlations": metrics,
                     "covariance": float(np.cov(x, y, ddof=1)[0, 1]) if valid else None,
                     "covariance_units": "decimal_return_squared_per_declared_period",
                     "sign_agreement": float(np.mean(np.sign(x) == np.sign(y))) if valid else None,
                     "simultaneous_loss_count": joint_loss, "simultaneous_gain_count": joint_gain,
                     "positive_agreement": joint_gain / n if valid else None,
                     "negative_agreement": joint_loss / n if valid else None,
                     "opposite_sign_count": int(np.sum(x * y < 0)),
                     "joint_loss_rate": joint_loss / n if valid else None,
                     "mean_absolute_difference": float(np.mean(abs(x-y))) if valid else None,
                     "empirical_lower_tail_overlap": tail,
                     "drawdown_overlap": {
                         "simultaneous_periods": sum(da[k] < 0 and db[k] < 0 for k in sample),
                         "state_agreement": sum((da[k] < 0) == (db[k] < 0) for k in sample) / n if valid else None,
                         "severe_periods": sum(da[k] <= policy.severe_drawdown and db[k] <= policy.severe_drawdown for k in sample),
                         "deepest_episode_overlap": len(deepest[0] & deepest[1] & set(sample)),
                         "loss_period_overlap": joint_loss}})
    return rows


def matrix_diagnostics(streams, keys, policy: AnalysisPolicy):
    ids = list(streams)
    out = {"strategy_ids": ids, "n": len(keys), "method": policy.matrix_method,
           "sample": "strict_intersection", "values": None, "eigenvalues": None,
           "rank": None, "condition": None, "effective_strategy_count": None,
           "mean_absolute_correlation": None, "maximum_absolute_correlation": None,
           "psd_tolerance": policy.tolerance, "state": "unavailable", "reason": None}
    x = np.array([[streams[s][k].return_value for s in ids] for k in keys])
    if len(keys) < policy.minimum_samples or any(np.ptp(x[:, j]) == 0 for j in range(len(ids))):
        out["reason"] = "common sample insufficient or includes a constant strategy; no partial matrix"
        return out
    values = np.eye(len(ids))
    for i, j in combinations(range(len(ids)), 2):
        c = correlation(x[:, i], x[:, j], method=policy.matrix_method,
                        minimum_observations=policy.minimum_samples, overlapping=False)
        if c["statistic"] is None:
            out["reason"] = "non-finite common-sample correlation"
            return out
        values[i, j] = values[j, i] = c["statistic"]
    eigen = np.linalg.eigvalsh(values)
    if eigen.min() < -policy.tolerance:
        out["reason"] = "matrix failed PSD validation; no repair applied"
        return out
    rank = int(np.linalg.matrix_rank(values, tol=policy.tolerance))
    off = abs(values[np.triu_indices(len(ids), 1)])
    out.update(values=values.tolist(), eigenvalues=eigen.tolist(), rank=rank,
               condition=float(np.linalg.cond(values)) if rank == len(ids) else None,
               effective_strategy_count=float(eigen.sum() ** 2 / (eigen ** 2).sum()),
               mean_absolute_correlation=float(off.mean()), maximum_absolute_correlation=float(off.max()),
               state="available", reason="singular condition unavailable" if rank < len(ids) else None)
    return out


def ensemble(streams, keys, policy: WeightPolicy, tolerance: float):
    details = weight_details(policy, list(streams), tolerance)
    weights = details["effective"]
    contribution_rows, returns = [], []
    for start, end in keys:
        contrib = {s: weights[s] * stream[(start, end)].return_value for s, stream in streams.items()}
        ret = math.fsum(contrib.values())
        returns.append(ret)
        contribution_rows.append({"period_start": start, "period_end": end,
                                  "contributions": contrib, "ensemble_return": ret,
                                  "residual": ret - math.fsum(contrib.values())})
    dd = drawdowns(keys, returns)
    total = math.fsum(returns)
    absolute = math.fsum(abs(v) for r in contribution_rows for v in r["contributions"].values())
    summaries = []
    for s in streams:
        values = [r["contributions"][s] for r in contribution_rows]
        arithmetic = math.fsum(values)
        summaries.append({"strategy_id": s, "arithmetic_contribution": arithmetic,
                          "share": arithmetic / total if abs(total) > tolerance else None,
                          "positive_periods": sum(v > 0 for v in values),
                          "negative_periods": sum(v < 0 for v in values),
                          "absolute_share": math.fsum(abs(v) for v in values) / absolute if absolute > tolerance else None})
    for episode in dd["episodes"]:
        sub = contribution_rows[episode["start_index"]:episode["end_index"]+1]
        episode["arithmetic_contributions"] = {s: math.fsum(r["contributions"][s] for r in sub) for s in streams}
    bases = {r.gross_or_net for s, stream in streams.items() if weights[s] != 0 for r in stream.values()}
    basis = next(iter(bases)) if len(bases) == 1 else "mixed"
    source_details = []
    for s, stream in streams.items():
        rows = [stream[k] for k in keys]
        source_details.append({"strategy_id": s, "cost_observations": sum(r.cost_return is not None for r in rows),
                               "turnover_observations": sum(r.turnover is not None for r in rows),
                               "cost_return_sum": math.fsum(r.cost_return for r in rows) if rows and all(r.cost_return is not None for r in rows) else None,
                               "turnover_sum": math.fsum(r.turnover for r in rows) if rows and all(r.turnover is not None for r in rows) else None})
    return {"weights": details, "n": len(keys), "periods": contribution_rows,
            "contribution_summary": summaries,
            "absolute_contribution_concentration": math.fsum(s["absolute_share"] ** 2 for s in summaries) if absolute > tolerance else None,
            "reconciliation_max_residual": max((abs(r["residual"]) for r in contribution_rows), default=0),
            "arithmetic_sum": total, "arithmetic_geometric_gap": dd["compounded_return"] - total if keys else None,
            "mean_return": float(np.mean(returns)) if returns else None,
            "volatility_per_period": float(np.std(returns, ddof=1)) if len(returns) > 1 else None,
            "drawdown": dd,
            "turnover": {"initial_allocation": 0.5 * details["gross"] if policy.initial_build == "zero_prior_weights" else None,
                         "subsequent_target_weight_change": 0.0, "executed_rebalance_turnover": None,
                         "underlying": source_details},
            "costs": {"basis": basis, "completeness": "allocation_costs_not_modeled",
                      "allocation_cost": None, "underlying_cost_deducted_again": False,
                      "gross_ensemble_reference": dd["compounded_return"] if basis == "gross" else None,
                      "net_of_strategy_costs_reference": dd["compounded_return"] if basis == "net_of_strategy_costs" else None,
                      "fully_net_ensemble": None,
                      "reason": "Input returns used verbatim. Underlying costs are read-only; allocation costs unavailable."}}


def analyze(request: RunCreate):
    streams, keys, coverage = aligned(request)
    if len(keys) < 2:
        raise ValueError("at least two strict-intersection periods are required")
    histories = {s: drawdowns(sorted(rows), [rows[k].return_value for k in sorted(rows)]) for s, rows in streams.items()}
    pairs = pairwise(streams, keys, request.analysis, histories)
    matrix = matrix_diagnostics(streams, keys, request.analysis)
    main = ensemble(streams, keys, request.policy, request.analysis.tolerance)
    hypotheses = [{"candidate_id": f"{p['strategy_a']}:{p['strategy_b']}:{method}",
                   "raw_p": p["correlations"][method]["p_value"],
                   "provenance": {"method": f"scipy_{method}", "sample": p["alignment"]}}
                  for p in pairs for method in ("pearson", "spearman")]
    scenarios, seen = [], set()
    for label, policy in [("Base", request.policy), *[(s.label, s.policy) for s in request.scenarios]]:
        values = ensemble(streams, keys, policy, request.analysis.tolerance)
        identity = {"weights": values["weights"]["effective"], "initial_build": policy.initial_build,
                    "cost": policy.allocation_cost_policy, "rebalance": policy.rebalance_policy}
        fp = sha256_hex(identity)
        if fp in seen:
            continue
        seen.add(fp)
        scenarios.append({"label": label, "is_base": not scenarios, "fingerprint": fp,
                          "policy": policy.model_dump(), "weights": values["weights"], "n": values["n"],
                          "mean_return": values["mean_return"], "volatility_per_period": values["volatility_per_period"],
                          "compounded_return": values["drawdown"]["compounded_return"],
                          "max_drawdown": values["drawdown"]["max_drawdown"],
                          "concentration": values["absolute_contribution_concentration"],
                          "mean_absolute_correlation": matrix["mean_absolute_correlation"],
                          "turnover": values["turnover"], "costs": values["costs"]})
    return {"coverage": coverage, "pairwise": pairs, "matrix": matrix,
            "strategy_drawdowns": histories, "ensemble": main, "sensitivity": scenarios,
            "multiple_testing": {"family": "all available Pearson and Spearman pairwise tests in this run",
                                 "correction": "holm", "results": adjust_p_values(hypotheses, request.analysis.alpha),
                                 "limitation": "Classical p-values assume independent observations; serial dependence is not corrected. No alpha or diversification proof."}}
