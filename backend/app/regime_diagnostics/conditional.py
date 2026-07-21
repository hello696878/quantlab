"""
Conditional performance, robustness, rank stability, and concentration.

Conventions (documented, tested):

* Metrics per (candidate, definition, regime label) over the outcome values
  at periods carrying that effective label.  ``sharpe_like`` =
  mean/std(ddof=1), per-period, never annualized (the timeline frequency is
  declared, not assumed).  Compounded return only for ``outcome_kind ==
  'return'``; cumulative sum otherwise.  Maximum drawdown is deliberately
  omitted in v1 — concatenating non-contiguous regime observations has no
  honest drawdown semantics (documented limitation).
* A regime with fewer than the definition's ``min_observations`` reports
  count/coverage only; performance statistics stay null with the reason and
  a low-coverage warning.  Coverage = n / periods that carry any label for
  the definition; the unassigned count is reported alongside.
* Robustness classification (documented thresholds): ``unknown`` with < 2
  defined regimes; ``concentrated`` when the largest regime holds ≥ 60% of
  labeled observations or the absolute-outcome HHI ≥ 0.5; else
  ``broadly_consistent`` when every defined regime's mean shares one sign;
  ``mixed`` when sign consistency ≥ 0.5; ``unstable`` below that.  These are
  measured-consistency descriptions under this configuration — never
  robustness proof.
* Concentration: observation HHI, positive-outcome HHI, largest/top-2 shares
  of Σ|outcome| (absolute magnitude) and — only when every regime sum shares
  one sign — of the signed total; effective regime count = 1/HHI; entropy
  −Σ p·ln p over observation shares.  Empty or zero-total cases are
  unavailable, never zero or NaN.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from scipy import stats as sp_stats

TOP_K = 3
MAX_REGIME_PAIRS = 15

CONCENTRATED_OBS_SHARE = 0.60
CONCENTRATED_HHI = 0.50


def conditional_metrics(
    outcomes: np.ndarray, indices: Sequence[int], labeled_total: int,
    min_observations: int, outcome_kind: str,
) -> Dict[str, Any]:
    values = outcomes[list(indices)] if len(indices) else np.array([])
    n = int(len(values))
    out: Dict[str, Any] = {
        "observation_count": n,
        "coverage": (n / labeled_total) if labeled_total else None,
        "mean": None, "median": None, "std": None, "minimum": None,
        "maximum": None, "positive_rate": None, "negative_rate": None,
        "cumulative": None, "sharpe_like": None, "downside_deviation": None,
        "status": "ok", "note": None,
    }
    if n < min_observations:
        out["status"] = "low_sample"
        out["note"] = (f"only {n} observation(s) — below the minimum of "
                       f"{min_observations}; performance statistics withheld")
        return out
    out["mean"] = float(values.mean())
    out["median"] = float(np.median(values))
    out["std"] = float(values.std(ddof=1)) if n > 1 else None
    out["minimum"] = float(values.min())
    out["maximum"] = float(values.max())
    out["positive_rate"] = float((values > 0).sum() / n)
    out["negative_rate"] = float((values < 0).sum() / n)
    out["cumulative"] = (float(np.prod(1.0 + values) - 1.0)
                         if outcome_kind == "return" else float(values.sum()))
    if out["std"] is not None and out["std"] > 1e-12:
        out["sharpe_like"] = float(values.mean() / values.std(ddof=1))
    else:
        out["note"] = "sharpe_like unavailable: zero outcome dispersion"
    downside = values[values < 0]
    out["downside_deviation"] = (
        float(np.sqrt((downside ** 2).sum() / n)) if len(downside) else 0.0
    )
    return out


def candidate_robustness(
    label_rows: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Per (candidate, definition) robustness from the per-label metric rows."""
    defined = [r for r in label_rows if r["metrics"]["mean"] is not None]
    total_obs = sum(r["metrics"]["observation_count"] for r in label_rows)
    out: Dict[str, Any] = {
        "observed_regimes": len(label_rows),
        "defined_regimes": len(defined),
        "unavailable_regimes": len(label_rows) - len(defined),
        "total_observations": total_obs,
        "dispersion": None, "sign_consistency": None,
        "positive_regime_fraction": None, "negative_regime_fraction": None,
        "lowest_regime_mean": None, "highest_regime_mean": None,
        "largest_regime_share": None,
        "classification": "unknown",
        "classification_note": (
            "measured consistency under this configuration — not robustness proof"
        ),
    }
    if total_obs:
        out["largest_regime_share"] = max(
            r["metrics"]["observation_count"] for r in label_rows) / total_obs
    if len(defined) < 2:
        return out
    means = np.array([r["metrics"]["mean"] for r in defined])
    pos = int((means > 0).sum())
    neg = int((means < 0).sum())
    out["dispersion"] = float(means.std(ddof=1)) if len(means) > 1 else None
    out["positive_regime_fraction"] = pos / len(means)
    out["negative_regime_fraction"] = neg / len(means)
    out["sign_consistency"] = max(pos, neg) / len(means)
    out["lowest_regime_mean"] = float(means.min())
    out["highest_regime_mean"] = float(means.max())
    abs_sums = np.array([abs(r["metrics"]["mean"]) * r["metrics"]["observation_count"]
                         for r in defined])
    # Normalized HHI ((HHI − 1/n)/(1 − 1/n)) is scale-free in the regime
    # count — raw HHI has a floor of 1/n, which would mislabel every
    # two-regime candidate as concentrated.
    hhi_abs = None
    if abs_sums.sum() > 0 and len(abs_sums) > 1:
        raw = float(((abs_sums / abs_sums.sum()) ** 2).sum())
        floor = 1.0 / len(abs_sums)
        hhi_abs = (raw - floor) / (1.0 - floor)
    if (out["largest_regime_share"] is not None
            and out["largest_regime_share"] >= CONCENTRATED_OBS_SHARE) \
            or (hhi_abs is not None and hhi_abs >= CONCENTRATED_HHI):
        out["classification"] = "concentrated"
    elif out["sign_consistency"] == 1.0:
        out["classification"] = "broadly_consistent"
    elif out["sign_consistency"] >= 0.5:
        out["classification"] = "mixed"
    else:
        out["classification"] = "unstable"
    return out


def concentration_diagnostics(
    label_rows: Sequence[Dict[str, Any]], outcomes_by_label: Dict[str, np.ndarray],
) -> Dict[str, Any]:
    counts = {r["regime_label"]: r["metrics"]["observation_count"] for r in label_rows}
    total_n = sum(counts.values())
    out: Dict[str, Any] = {
        "observation_hhi": None, "positive_outcome_hhi": None,
        "largest_abs_share": None, "top2_abs_share": None,
        "largest_signed_share": None, "top2_signed_share": None,
        "signed_share_note": None,
        "effective_regime_count": None, "entropy": None,
        "status": "ok", "note": None,
    }
    if total_n == 0:
        out["status"] = "unavailable"
        out["note"] = "no labeled observations"
        return out
    shares = np.array([n / total_n for n in counts.values() if n > 0])
    out["observation_hhi"] = float((shares ** 2).sum())
    out["effective_regime_count"] = float(1.0 / out["observation_hhi"])
    out["entropy"] = float(-(shares * np.log(shares)).sum()) + 0.0  # avoid -0.0
    pos_sums = np.array([float(v[v > 0].sum()) for v in outcomes_by_label.values()])
    if pos_sums.sum() > 0:
        p = pos_sums / pos_sums.sum()
        p = p[p > 0]
        out["positive_outcome_hhi"] = float((p ** 2).sum())
    abs_sums = np.array([float(np.abs(v).sum()) for v in outcomes_by_label.values()])
    if abs_sums.sum() > 0:
        ordered = np.sort(abs_sums)[::-1] / abs_sums.sum()
        out["largest_abs_share"] = float(ordered[0])
        out["top2_abs_share"] = float(ordered[: 2].sum())
    signed_sums = np.array([float(v.sum()) for v in outcomes_by_label.values()])
    nonzero = signed_sums[signed_sums != 0]
    if len(nonzero) and (np.all(nonzero > 0) or np.all(nonzero < 0)):
        total = signed_sums.sum()
        ordered = np.sort(np.abs(signed_sums))[::-1] / abs(total)
        out["largest_signed_share"] = float(ordered[0])
        out["top2_signed_share"] = float(ordered[: 2].sum())
    else:
        out["signed_share_note"] = (
            "regime outcome sums carry mixed signs — signed contribution shares "
            "are unavailable (absolute-magnitude shares apply instead)"
        )
    return out


def rank_stability(
    candidate_ids: Sequence[str],
    means_by_label: Dict[str, Dict[str, Optional[float]]],
) -> Dict[str, Any]:
    """Candidate ranks per regime label + pairwise Spearman + top-k overlap.

    ``means_by_label[label][candidate_id]`` = defined regime mean or None.
    Ranks ascend with the mean (rank 1 = lowest measured mean — ties get
    average ranks).  Constant vectors are pre-checked; no scipy warning can
    escape.
    """
    labels = sorted(means_by_label)
    if len(candidate_ids) < 2 or len(labels) < 2:
        return {"status": "unavailable",
                "reason": "needs at least 2 candidates and 2 defined regimes",
                "labels": labels, "ranks": {}, "pairs": [],
                "mean_spearman": None, "mean_top_k_overlap": None,
                "per_candidate": []}
    ranks: Dict[str, Dict[str, Optional[float]]] = {}
    for label in labels:
        means = means_by_label[label]
        defined = [(cid, means[cid]) for cid in candidate_ids
                   if means.get(cid) is not None]
        label_ranks: Dict[str, Optional[float]] = {cid: None for cid in candidate_ids}
        if len(defined) >= 2:
            arr = np.array([m for _, m in defined], dtype=np.float64)
            rd = sp_stats.rankdata(arr, method="average")
            for (cid, _), rank in zip(defined, rd):
                label_ranks[cid] = float(rank)
        ranks[label] = label_ranks
    truncated = len(labels) > MAX_REGIME_PAIRS
    used = labels[:MAX_REGIME_PAIRS]
    k = min(TOP_K, len(candidate_ids))
    pairs: List[Dict[str, Any]] = []
    spearmans: List[float] = []
    overlaps: List[float] = []
    for i in range(len(used)):
        for j in range(i + 1, len(used)):
            shared = [cid for cid in candidate_ids
                      if ranks[used[i]][cid] is not None
                      and ranks[used[j]][cid] is not None]
            entry: Dict[str, Any] = {"regime_a": used[i], "regime_b": used[j],
                                     "spearman": None, "top_k_overlap": None,
                                     "note": None}
            if len(shared) >= 3:
                a = np.array([ranks[used[i]][cid] for cid in shared])
                b = np.array([ranks[used[j]][cid] for cid in shared])
                if float(np.std(a)) > 0.0 and float(np.std(b)) > 0.0:
                    value = float(sp_stats.spearmanr(a, b).statistic)
                    if math.isfinite(value):
                        entry["spearman"] = value
                        spearmans.append(value)
                else:
                    entry["note"] = "constant rank vector — correlation undefined"
            else:
                entry["note"] = "fewer than 3 shared defined candidates"
            if shared:
                # Overlap divides by min(k, shared) so identical rankings over a
                # sparse pair still score 1.0.
                k_eff = min(k, len(shared))

                def top(label: str) -> set:
                    scored = sorted(
                        ((cid, ranks[label][cid]) for cid in shared),
                        key=lambda t: (-t[1], t[0]))
                    return {cid for cid, _ in scored[:k_eff]}
                overlap = len(top(used[i]) & top(used[j])) / k_eff if k_eff else None
                entry["top_k_overlap"] = overlap
                if overlap is not None:
                    overlaps.append(overlap)
            pairs.append(entry)
    per_candidate = []
    for cid in candidate_ids:
        rs = [ranks[lb][cid] for lb in used if ranks[lb][cid] is not None]
        per_candidate.append({
            "candidate_id": cid,
            "rank_std": float(np.std(rs, ddof=1)) if len(rs) > 1 else None,
            "rank_range": float(max(rs) - min(rs)) if rs else None,
            "defined_regimes": len(rs),
        })
    return {
        "status": "ok", "labels": used, "truncated": truncated,
        "truncation_note": (f"pairwise matrix limited to {MAX_REGIME_PAIRS} regimes"
                            if truncated else None),
        "rank_convention": "rank 1 = lowest measured regime mean; average ties",
        "top_k": k,
        "ranks": ranks, "pairs": pairs,
        "mean_spearman": float(np.mean(spearmans)) if spearmans else None,
        "mean_top_k_overlap": float(np.mean(overlaps)) if overlaps else None,
        "per_candidate": per_candidate,
    }


__all__ = [
    "TOP_K", "MAX_REGIME_PAIRS", "CONCENTRATED_OBS_SHARE", "CONCENTRATED_HHI",
    "conditional_metrics", "candidate_robustness", "concentration_diagnostics",
    "rank_stability",
]
