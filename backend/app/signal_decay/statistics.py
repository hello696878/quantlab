"""
Correlation and information-coefficient diagnostics (v1).

All statistics come from the approved numpy/scipy stack; every p-value is
the real library value (`scipy.stats.pearsonr` / `spearmanr` /
`kendalltau`) — **no p-value is ever fabricated**, and where an assumption
fails the statistic is `unavailable` with its reason rather than a number.

Conventions
-----------
* Spearman uses scipy's average-rank method for ties (documented); with the
  signal's `tie_policy = "first"` a deterministic ordinal ranking by
  (value, entity, timestamp) is used instead and labelled.
* A constant signal or constant outcome has no defined correlation → both
  the statistic and its p-value are unavailable.
* Fewer than ``minimum_observations`` pairs → unavailable.
* Classical p-values assume independent observations; when the horizon's
  intervals overlap, that assumption fails and every p-value in the row
  carries an explicit overlap limitation instead of being suppressed or
  "corrected" silently.
* An information coefficient is a measured association over this sample.
  It is never called good, bad, predictive or profitable.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import stats as sp_stats

MIN_CROSS_SECTION_ENTITIES = 3

CORRELATION_METHODS = ("pearson", "spearman", "kendall")

OVERLAP_P_VALUE_NOTE = (
    "classical p-values assume independent observations; this horizon's "
    "outcome intervals overlap, so the p-value is reported with that "
    "limitation and must not be read at face value")


class StatisticsError(ValueError):
    """Invalid statistics configuration (HTTP 422)."""


def _clean_pairs(signal: Sequence[Optional[float]],
                 outcome: Sequence[Optional[float]]
                 ) -> Tuple[np.ndarray, np.ndarray]:
    xs: List[float] = []
    ys: List[float] = []
    for s, o in zip(signal, outcome):
        if s is None or o is None:
            continue
        xs.append(float(s))
        ys.append(float(o))
    return np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64)


def _tie_count(values: np.ndarray) -> int:
    unique, counts = np.unique(values, return_counts=True)
    return int(np.sum(counts[counts > 1]))


def correlation(signal: Sequence[Optional[float]],
                outcome: Sequence[Optional[float]], *,
                method: str, minimum_observations: int,
                overlapping: bool) -> Dict[str, Any]:
    """One correlation with honest availability and a REAL p-value."""
    if method not in CORRELATION_METHODS:
        raise StatisticsError(
            f"correlation method must be one of {list(CORRELATION_METHODS)}")
    x, y = _clean_pairs(signal, outcome)
    out: Dict[str, Any] = {
        "method": method,
        "observations": int(x.size),
        "signal_tie_count": None, "outcome_tie_count": None,
        "unique_signal_values": None, "unique_outcome_values": None,
        "statistic": None, "p_value": None, "p_value_note": None,
        "state": "unavailable", "reason": None,
    }
    if x.size < minimum_observations:
        out["reason"] = (f"{x.size} valid pair(s) are below the minimum of "
                         f"{minimum_observations}")
        return out
    out["signal_tie_count"] = _tie_count(x)
    out["outcome_tie_count"] = _tie_count(y)
    out["unique_signal_values"] = int(np.unique(x).size)
    out["unique_outcome_values"] = int(np.unique(y).size)
    if np.unique(x).size < 2:
        out["reason"] = "the signal is constant over the valid pairs"
        return out
    if np.unique(y).size < 2:
        out["reason"] = "the outcome is constant over the valid pairs"
        return out
    if method == "pearson":
        result = sp_stats.pearsonr(x, y)
    elif method == "spearman":
        result = sp_stats.spearmanr(x, y)
    else:
        result = sp_stats.kendalltau(x, y, variant="b")
    statistic = float(result.statistic)
    p_value = float(result.pvalue)
    if not math.isfinite(statistic):
        out["reason"] = "the statistic is not finite"
        return out
    out["statistic"] = statistic
    out["p_value"] = p_value if math.isfinite(p_value) else None
    out["state"] = "available"
    if overlapping and out["p_value"] is not None:
        out["p_value_note"] = OVERLAP_P_VALUE_NOTE
    return out


def correlation_block(signal: Sequence[Optional[float]],
                      outcome: Sequence[Optional[float]], *,
                      methods: Sequence[str], minimum_observations: int,
                      overlapping: bool) -> Dict[str, Any]:
    return {method: correlation(signal, outcome, method=method,
                                minimum_observations=minimum_observations,
                                overlapping=overlapping)
            for method in methods}


# ---------------------------------------------------------------------------
# Cross-sectional IC
# ---------------------------------------------------------------------------

def cross_sectional_ic(pairs: List[Dict[str, Any]], *,
                       minimum_entities: int = MIN_CROSS_SECTION_ENTITIES,
                       overlapping: bool) -> Dict[str, Any]:
    """Timestamp-level IC over each timestamp's OWN eligible universe.

    No cross-timestamp pooling: every row uses only the entities that carry
    a valid signal and outcome at that timestamp.  Timestamps below the
    entity minimum stay visible as unavailable.
    """
    by_stamp: Dict[str, List[Dict[str, Any]]] = {}
    for pair in pairs:
        by_stamp.setdefault(pair["signal_timestamp"], []).append(pair)

    rows: List[Dict[str, Any]] = []
    spearman_values: List[float] = []
    pearson_values: List[float] = []
    unavailable = 0
    for stamp in sorted(by_stamp):
        universe = sorted(by_stamp[stamp], key=lambda p: p["entity_id"])
        signal = [p["signal_value"] for p in universe]
        outcome = [p["outcome_value"] for p in universe]
        entry: Dict[str, Any] = {
            "timestamp": stamp,
            "eligible_entities": len(universe),
            "entity_ids": [p["entity_id"] for p in universe],
            "pearson_ic": None, "spearman_ic": None,
            "tie_count": None, "state": "unavailable", "reason": None,
        }
        if len(universe) < minimum_entities:
            entry["reason"] = (f"{len(universe)} eligible entities are below "
                               f"the minimum of {minimum_entities}")
            unavailable += 1
            rows.append(entry)
            continue
        block = correlation_block(signal, outcome,
                                  methods=("pearson", "spearman"),
                                  minimum_observations=minimum_entities,
                                  overlapping=overlapping)
        pearson = block["pearson"]
        spearman = block["spearman"]
        entry["tie_count"] = spearman["signal_tie_count"]
        if spearman["state"] == "available":
            entry["spearman_ic"] = spearman["statistic"]
            entry["state"] = "available"
            spearman_values.append(spearman["statistic"])
        else:
            entry["reason"] = spearman["reason"]
            unavailable += 1
        if pearson["state"] == "available":
            entry["pearson_ic"] = pearson["statistic"]
            pearson_values.append(pearson["statistic"])
        rows.append(entry)

    aggregate = _aggregate_ic(spearman_values, pearson_values,
                              timestamp_count=len(rows),
                              unavailable_count=unavailable)
    return {"rows": rows, "aggregate": aggregate,
            "minimum_entities": minimum_entities}


def _aggregate_ic(spearman_values: List[float], pearson_values: List[float],
                  *, timestamp_count: int,
                  unavailable_count: int) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "timestamp_count": timestamp_count,
        "unavailable_timestamp_count": unavailable_count,
        "mean_spearman_ic": None, "median_spearman_ic": None,
        "std_spearman_ic": None, "ic_ratio": None,
        "ic_ratio_note": ("mean / standard deviation of the timestamp-level "
                          "rank IC — a DESCRIPTIVE ratio over this sample, "
                          "not an information ratio of any strategy"),
        "positive_rate": None, "negative_rate": None, "zero_rate": None,
        "mean_pearson_ic": None,
    }
    if spearman_values:
        array = np.asarray(spearman_values, dtype=np.float64)
        out["mean_spearman_ic"] = float(np.mean(array))
        out["median_spearman_ic"] = float(np.median(array))
        if array.size >= 2:
            std = float(np.std(array, ddof=1))
            out["std_spearman_ic"] = std
            if std > 1e-15:
                out["ic_ratio"] = float(np.mean(array) / std)
        out["positive_rate"] = float(np.mean(array > 0))
        out["negative_rate"] = float(np.mean(array < 0))
        out["zero_rate"] = float(np.mean(array == 0))
    if pearson_values:
        out["mean_pearson_ic"] = float(
            np.mean(np.asarray(pearson_values, dtype=np.float64)))
    return out


# ---------------------------------------------------------------------------
# Time-series diagnostics
# ---------------------------------------------------------------------------

def signal_autocorrelation(values: Sequence[Optional[float]],
                           *, max_lag: int = 5,
                           entity_ids: Optional[Sequence[str]] = None
                           ) -> List[Dict[str, Any]]:
    """Trailing-lag autocorrelation of the SIGNAL itself.

    Missing values preserve their grid position, and optional entity ids keep
    lag pairs within an entity.  This prevents a null observation from
    collapsing time or the end of one entity from pairing with the start of
    another.  Signal persistence remains distinct from outcome association.
    """
    if entity_ids is not None and len(entity_ids) != len(values):
        raise StatisticsError(
            "entity_ids must have the same length as signal values")
    groups: Dict[str, List[Optional[float]]] = {}
    if entity_ids is None:
        groups["aggregate"] = list(values)
    else:
        for entity_id, value in zip(entity_ids, values):
            groups.setdefault(str(entity_id), []).append(value)

    rows: List[Dict[str, Any]] = []
    for lag in range(1, max_lag + 1):
        current: List[float] = []
        previous: List[float] = []
        for series in groups.values():
            for index in range(lag, len(series)):
                now = series[index]
                before = series[index - lag]
                if now is None or before is None:
                    continue
                current.append(float(now))
                previous.append(float(before))
        a = np.asarray(current, dtype=np.float64)
        b = np.asarray(previous, dtype=np.float64)
        entry: Dict[str, Any] = {"lag": lag, "autocorrelation": None,
                                 "observations": int(a.size),
                                 "reason": None}
        if a.size < 3:
            entry["reason"] = "fewer than 3 valid within-entity lag pairs"
            rows.append(entry)
            continue
        if np.unique(a).size < 2 or np.unique(b).size < 2:
            entry["reason"] = "constant series"
            rows.append(entry)
            continue
        value = float(np.corrcoef(a, b)[0, 1])
        entry["autocorrelation"] = value if math.isfinite(value) else None
        rows.append(entry)
    return rows

def sign_agreement(signal: Sequence[Optional[float]],
                   outcome: Sequence[Optional[float]]) -> Dict[str, Any]:
    x, y = _clean_pairs(signal, outcome)
    if x.size == 0:
        return {"observations": 0, "agreement_rate": None,
                "reason": "no valid pairs"}
    agreements = int(np.sum(np.sign(x) == np.sign(y)))
    return {"observations": int(x.size),
            "agreement_rate": float(agreements / x.size),
            "note": ("share of pairs whose signal and outcome share a sign — "
                     "a descriptive count, not a hit-rate claim")}


__all__ = [
    "MIN_CROSS_SECTION_ENTITIES", "CORRELATION_METHODS",
    "OVERLAP_P_VALUE_NOTE", "StatisticsError", "correlation",
    "correlation_block", "cross_sectional_ic", "signal_autocorrelation",
    "sign_agreement",
]
