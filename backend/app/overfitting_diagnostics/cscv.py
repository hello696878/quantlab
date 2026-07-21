"""
Combinatorially Symmetric Cross-Validation (CSCV) and the Probability of
Backtest Overfitting (PBO), after Bailey, Borwein, López de Prado & Zhu.

Conventions (fixed, documented, tested — never mixed):

* Blocks: S chronological contiguous subperiods (S even, bounded), sizes
  differing by at most one (``numpy.array_split`` — earlier blocks get the
  extra observation), every observation in exactly one block, boundaries
  recorded.
* Combinations: all C(S, S/2) in-sample block choices in deterministic
  lexicographic order (``itertools.combinations``); the out-of-sample set is
  always the exact complement.  No sampling, no truncation — configurations
  that would exceed MAX_COMBINATIONS are rejected with a 422.
* Rank convention: **ascending out-of-sample ranks with average ties —
  rank 1 = worst measured OOS candidate, rank N = strongest measured OOS
  candidate** (N = candidates with a defined OOS metric in that split).
* Relative rank: ``omega = rank / (N + 1)`` (the +1 keeps omega strictly
  inside (0, 1)); ``lambda = ln(omega / (1 - omega))``.
* PBO: the fraction of **valid** splits with ``lambda < 0``.  ``lambda == 0``
  (selected candidate exactly median, possible with average ties) counts in
  the denominator but NOT as overfit — documented boundary convention.
* Ties: an exact in-sample tie for the top metric selects the
  lexicographically smallest candidate_id (candidates are pre-sorted by id)
  and records the tie; nothing is ever chosen randomly.

Low PBO under one configuration means a lower estimated selection-overfitting
frequency under that configuration — it is never proof of robustness.
"""

from __future__ import annotations

import math
from itertools import combinations
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import stats as sp_stats

from app.overfitting_diagnostics.dependence import is_constant_series
from app.overfitting_diagnostics.metrics import matrix_metrics

S_MIN = 4
S_MAX = 12
MIN_BLOCK_OBSERVATIONS = 4
MAX_COMBINATIONS = 924  # C(12, 6)


class CSCVError(ValueError):
    """Invalid CSCV configuration (HTTP 422)."""


def combination_count(s: int) -> int:
    return math.comb(s, s // 2)


def validate_block_count(s: Any, n_observations: int) -> int:
    if isinstance(s, bool) or not isinstance(s, int):
        raise CSCVError("block_count must be an integer")
    if s % 2 != 0:
        raise CSCVError("block_count must be even")
    if not (S_MIN <= s <= S_MAX):
        raise CSCVError(f"block_count must be between {S_MIN} and {S_MAX}")
    if combination_count(s) > MAX_COMBINATIONS:
        raise CSCVError(
            f"C({s}, {s // 2}) = {combination_count(s)} exceeds the supported "
            f"combination limit of {MAX_COMBINATIONS}"
        )
    if n_observations < s * MIN_BLOCK_OBSERVATIONS:
        raise CSCVError(
            f"{n_observations} observations cannot fill {s} blocks of at least "
            f"{MIN_BLOCK_OBSERVATIONS} observations each"
        )
    return s


def build_blocks(n_observations: int, s: int) -> List[Dict[str, int]]:
    """Chronological contiguous blocks; sizes differ by at most one."""
    pieces = np.array_split(np.arange(n_observations), s)
    blocks = []
    for i, piece in enumerate(pieces):
        blocks.append({"block_id": i, "start": int(piece[0]),
                       "end": int(piece[-1]), "size": int(len(piece))})
    return blocks


def _average_ranks_ascending(values: np.ndarray) -> np.ndarray:
    """Ascending average-tie ranks over defined values (NaN stays NaN)."""
    ranks = np.full(len(values), np.nan)
    defined = ~np.isnan(values)
    if defined.any():
        ranks[defined] = sp_stats.rankdata(values[defined], method="average")
    return ranks


def run_cscv(
    matrix: np.ndarray,
    blocks: Sequence[Dict[str, int]],
    metric: str,
    candidate_ids: Sequence[str],
) -> List[Dict[str, Any]]:
    """One record per C(S, S/2) combination, valid or invalid — never dropped."""
    s = len(blocks)
    block_indices = [np.arange(b["start"], b["end"] + 1) for b in blocks]
    records: List[Dict[str, Any]] = []
    for combo_index, is_blocks in enumerate(combinations(range(s), s // 2)):
        oos_blocks = tuple(b for b in range(s) if b not in is_blocks)
        is_idx = np.concatenate([block_indices[b] for b in is_blocks])
        oos_idx = np.concatenate([block_indices[b] for b in oos_blocks])
        is_values, _ = matrix_metrics(metric, matrix[is_idx])
        oos_values, _ = matrix_metrics(metric, matrix[oos_idx])
        record: Dict[str, Any] = {
            "split_id": f"cscv-{combo_index:04d}",
            "split_index": combo_index,
            "is_block_ids": list(is_blocks),
            "oos_block_ids": list(oos_blocks),
            "status": "valid", "warning": None,
            "selected_candidate_id": None,
            "is_metric": None, "oos_metric": None,
            "oos_rank": None, "oos_defined_count": None,
            "relative_rank": None, "lambda": None,
            "degradation": None, "rank_degradation": None,
            "tie_in_sample": False, "tie_out_of_sample": False,
        }
        if np.isnan(is_values).all():
            record["status"] = "invalid"
            record["warning"] = "every candidate's in-sample metric is undefined"
            records.append(record)
            continue
        best = np.nanmax(is_values)
        tied = np.where(np.isclose(is_values, best, rtol=0.0, atol=0.0)
                        & ~np.isnan(is_values))[0]
        selected = int(tied[0])  # lexicographically smallest id (pre-sorted)
        record["selected_candidate_id"] = candidate_ids[selected]
        record["is_metric"] = float(is_values[selected])
        record["tie_in_sample"] = len(tied) > 1
        if np.isnan(oos_values[selected]):
            record["status"] = "invalid"
            record["warning"] = "selected candidate's out-of-sample metric is undefined"
            records.append(record)
            continue
        oos_ranks = _average_ranks_ascending(oos_values)
        n_defined = int((~np.isnan(oos_values)).sum())
        rank = float(oos_ranks[selected])
        omega = rank / (n_defined + 1)
        record["oos_metric"] = float(oos_values[selected])
        record["oos_rank"] = rank
        record["oos_defined_count"] = n_defined
        record["relative_rank"] = omega
        record["lambda"] = float(math.log(omega / (1.0 - omega)))
        record["degradation"] = record["is_metric"] - record["oos_metric"]
        record["rank_degradation"] = float(n_defined - rank)
        record["tie_out_of_sample"] = bool(
            (np.isclose(oos_values, oos_values[selected], rtol=0.0, atol=0.0)
             & ~np.isnan(oos_values)).sum() > 1
        )
        records.append(record)
    return records


def _safe_corr(a: np.ndarray, b: np.ndarray, kind: str) -> Optional[float]:
    """Pre-checked correlation (no scipy/numpy constant-input warning possible).

    Constancy is tested with the package's shared predicate, which uses an
    exact scale-free range check.  A dispersion test such as
    ``np.std(v) == 0.0`` is NOT safe: a genuinely constant series whose value
    is not exactly representable carries a tiny non-zero float std
    (``np.std([0.1] * 6)`` is ``1.39e-17``), so such a vector would slip past
    the guard into scipy, raise ConstantInputWarning and return NaN.
    """
    if len(a) < 3 or is_constant_series(a) or is_constant_series(b):
        return None
    if kind == "pearson":
        value = float(np.corrcoef(a, b)[0, 1])
    else:
        value = float(sp_stats.spearmanr(a, b).statistic)
    return value if math.isfinite(value) else None


def aggregate_pbo(
    records: Sequence[Dict[str, Any]], candidate_ids: Sequence[str]
) -> Dict[str, Any]:
    valid = [r for r in records if r["status"] == "valid"]
    invalid_count = len(records) - len(valid)
    out: Dict[str, Any] = {
        "combination_count": len(records),
        "valid_split_count": len(valid),
        "invalid_split_count": invalid_count,
        "tie_in_sample_count": sum(1 for r in valid if r["tie_in_sample"]),
        "tie_out_of_sample_count": sum(1 for r in valid if r["tie_out_of_sample"]),
        "lambda_zero_policy": "lambda == 0 counts in the denominator, not as overfit",
        "rank_convention": "rank 1 = worst OOS, rank N = strongest OOS; "
                           "omega = rank/(N+1); lambda = ln(omega/(1-omega))",
    }
    if not valid:
        out.update({"pbo_estimate": None, "pbo_note": "no valid CSCV splits",
                    "lambda_stats": None, "is_oos_correlation": None,
                    "oos_loss_fraction": None, "mean_degradation": None,
                    "median_degradation": None, "mean_rank_degradation": None,
                    "median_rank_degradation": None, "selection": []})
        return out
    lambdas = np.array([r["lambda"] for r in valid])
    out["pbo_estimate"] = float((lambdas < 0).sum() / len(lambdas))
    out["pbo_note"] = (
        "fraction of valid CSCV splits where the in-sample-selected candidate "
        "ranked in the bottom half out of sample (lambda < 0) — an estimated "
        "selection-overfitting frequency under this configuration, not proof "
        "of anything"
    )
    out["lambda_stats"] = {
        "mean": float(lambdas.mean()), "median": float(np.median(lambdas)),
        "std": float(lambdas.std(ddof=1)) if len(lambdas) > 1 else None,
        "min": float(lambdas.min()), "max": float(lambdas.max()),
        "q05": float(np.quantile(lambdas, 0.05)),
        "q25": float(np.quantile(lambdas, 0.25)),
        "q75": float(np.quantile(lambdas, 0.75)),
        "q95": float(np.quantile(lambdas, 0.95)),
        "fraction_below_zero": out["pbo_estimate"],
        "fraction_at_zero": float((lambdas == 0).sum() / len(lambdas)),
    }
    is_vals = np.array([r["is_metric"] for r in valid])
    oos_vals = np.array([r["oos_metric"] for r in valid])
    out["is_oos_correlation"] = {
        "pearson": _safe_corr(is_vals, oos_vals, "pearson"),
        "spearman": _safe_corr(is_vals, oos_vals, "spearman"),
        "note": "selected candidate's IS vs OOS metric across valid splits; "
                "null when either side is constant or fewer than 3 splits",
    }
    out["oos_loss_fraction"] = float((oos_vals < 0).sum() / len(oos_vals))
    out["oos_loss_note"] = (
        "fraction of valid splits where the selected candidate's OOS metric "
        "was negative — meaningful because all v1 ranking metrics are centred "
        "at zero for a no-edge candidate"
    )
    degr = np.array([r["degradation"] for r in valid])
    rank_degr = np.array([r["rank_degradation"] for r in valid])
    out["mean_degradation"] = float(degr.mean())
    out["median_degradation"] = float(np.median(degr))
    out["mean_rank_degradation"] = float(rank_degr.mean())
    out["median_rank_degradation"] = float(np.median(rank_degr))

    selection: List[Dict[str, Any]] = []
    for cid in candidate_ids:
        chosen = [r for r in valid if r["selected_candidate_id"] == cid]
        entry: Dict[str, Any] = {
            "candidate_id": cid,
            "selected_count": len(chosen),
            "selection_frequency": len(chosen) / len(valid),
        }
        if chosen:
            ranks = np.array([r["oos_rank"] for r in chosen])
            lams = np.array([r["lambda"] for r in chosen])
            degs = np.array([r["degradation"] for r in chosen])
            n_med = np.array([(r["oos_defined_count"] + 1) / 2.0 for r in chosen])
            entry.update({
                "mean_oos_rank_when_selected": float(ranks.mean()),
                "median_oos_rank_when_selected": float(np.median(ranks)),
                "mean_lambda_when_selected": float(lams.mean()),
                "median_lambda_when_selected": float(np.median(lams)),
                "mean_degradation_when_selected": float(degs.mean()),
                "below_median_oos_fraction": float((ranks < n_med).sum() / len(ranks)),
                "negative_oos_fraction": float(
                    (np.array([r["oos_metric"] for r in chosen]) < 0).sum() / len(chosen)),
            })
        else:
            entry.update({
                "mean_oos_rank_when_selected": None,
                "median_oos_rank_when_selected": None,
                "mean_lambda_when_selected": None,
                "median_lambda_when_selected": None,
                "mean_degradation_when_selected": None,
                "below_median_oos_fraction": None,
                "negative_oos_fraction": None,
            })
        selection.append(entry)
    out["selection"] = selection
    return out


__all__ = [
    "S_MIN", "S_MAX", "MIN_BLOCK_OBSERVATIONS", "MAX_COMBINATIONS",
    "CSCVError", "combination_count", "validate_block_count", "build_blocks",
    "run_cscv", "aggregate_pbo",
]
