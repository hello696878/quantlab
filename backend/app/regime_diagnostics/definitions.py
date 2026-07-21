"""
Regime definitions and the no-look-ahead labeling engine.

Mechanics (fixed, documented, adversarially tested):

* Every computed statistic at index j uses a **trailing window ending at j**
  (``values[j−lookback+1 … j]``, sample std ddof=1 for volatility, mean for
  trend/liquidity); centered or forward windows do not exist in this module.
* The label **effective at period i uses the statistic at j = i − lag** with
  ``lag ≥ 1`` — an end-of-period statistic can never label its own period.
  Negative or zero lags are rejected.
* Drawdown state uses the **trailing peak only**: ``level[j] = Π(1+v)``,
  ``peak[j] = max(level[0..j])``; no future maximum is ever consulted.
* Threshold-fitting modes carry distinct integrity states and never fall
  back silently:
  - ``fixed``              → ``verified_causal_rule``
  - ``expanding_quantile`` → ``verified_causal_rule`` (thresholds at i use
    only statistics at or before i − lag, with a minimum history; earlier
    periods stay unavailable)
  - ``training_quantile``  → ``verified_from_validation_split`` (thresholds
    fitted on the named split's recorded training membership only)
  - ``full_sample_quantile`` → ``full_sample_descriptive`` — explicitly NOT
    leakage-safe, always warned
  - user-supplied labels   → ``declared`` (or ``invalid`` when their
    provenance admits a centered/future construction)
* Combined regimes take the **least-trusted** source integrity.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from app.experiment_registry.fingerprints import sha256_hex

DIMENSIONS = ("volatility", "trend", "liquidity", "drawdown", "categorical", "combined")
COMPUTED_DIMENSIONS = ("volatility", "trend", "liquidity")
THRESHOLD_MODES = ("fixed", "training_quantile", "expanding_quantile",
                   "full_sample_quantile")
INTEGRITY_STATES = ("verified_from_validation_split", "verified_causal_rule",
                    "declared", "full_sample_descriptive", "unknown", "invalid")
# ascending trust for combined-regime propagation
_TRUST_ORDER = {"invalid": 0, "unknown": 1, "full_sample_descriptive": 2,
                "declared": 3, "verified_from_validation_split": 4,
                "verified_causal_rule": 5}

MAX_DEFINITIONS = 6
MAX_LABELS = 6
MAX_COMBINED_LABELS = 12
MIN_LOOKBACK = 2
MAX_LOOKBACK = 250
MIN_LAG = 1
MAX_LAG = 30
MIN_REGIME_OBSERVATIONS_DEFAULT = 8

DEFAULT_LABELS = {
    "volatility": ["low", "normal", "high"],
    "trend": ["downward", "neutral", "upward"],
    "liquidity": ["thin", "normal", "deep"],
    "drawdown": ["near_peak", "moderate_drawdown", "deep_drawdown"],
}


class RegimeDefinitionError(ValueError):
    """Invalid regime definition (HTTP 422)."""


def _check_int(value: Any, name: str, lo: int, hi: int, default: Optional[int]) -> int:
    if value is None:
        if default is None:
            raise RegimeDefinitionError(f"{name} is required")
        return default
    if isinstance(value, bool) or not isinstance(value, int) or not (lo <= value <= hi):
        raise RegimeDefinitionError(f"{name} must be an integer in [{lo}, {hi}]")
    return value


def _check_labels(labels: Any, dimension: str) -> List[str]:
    if labels is None:
        return list(DEFAULT_LABELS[dimension])
    if not isinstance(labels, (list, tuple)) or len(labels) != 3:
        raise RegimeDefinitionError(
            f"{dimension} labels must list exactly 3 names (low→high order)"
        )
    out = []
    for lb in labels:
        if not isinstance(lb, str) or not lb.strip() or len(lb) > 32:
            raise RegimeDefinitionError("labels must be non-empty strings ≤ 32 chars")
        out.append(lb.strip())
    if len(set(out)) != 3:
        raise RegimeDefinitionError("labels must be distinct")
    return out


def validate_definition(
    d: Dict[str, Any], feature_names: Sequence[str], existing_ids: Sequence[str]
) -> Dict[str, Any]:
    """Validated, normalized definition (combined sources checked by caller)."""
    def_id = d.get("definition_id")
    if not isinstance(def_id, str) or not def_id.strip() or len(def_id) > 64:
        raise RegimeDefinitionError("every definition needs a definition_id ≤ 64 chars")
    def_id = def_id.strip()
    if def_id in existing_ids:
        raise RegimeDefinitionError(f"duplicate definition_id {def_id!r}")
    dimension = d.get("dimension")
    if dimension not in DIMENSIONS:
        raise RegimeDefinitionError(f"dimension must be one of {DIMENSIONS}")
    lag_raw = d.get("lag")
    if isinstance(lag_raw, (int, float)) and not isinstance(lag_raw, bool) and lag_raw < 0:
        raise RegimeDefinitionError("negative lags are prohibited (future information)")
    if d.get("centered") or d.get("window") == "centered":
        raise RegimeDefinitionError(
            "centered windows are prohibited — only trailing windows exist"
        )
    out: Dict[str, Any] = {
        "definition_id": def_id,
        "name": d.get("name") or def_id,
        "description": d.get("description") or "",
        "dimension": dimension,
        "min_observations": _check_int(d.get("min_observations"), "min_observations",
                                       2, 100, MIN_REGIME_OBSERVATIONS_DEFAULT),
    }
    if dimension in COMPUTED_DIMENSIONS or dimension == "drawdown":
        source = d.get("source_feature")
        if not isinstance(source, str) or source not in feature_names:
            raise RegimeDefinitionError(
                f"definition {def_id}: source_feature must name a supplied market "
                f"feature (got {source!r}; available: {sorted(feature_names)})"
            )
        out["source_feature"] = source
        out["lag"] = _check_int(d.get("lag"), "lag", MIN_LAG, MAX_LAG, 1)
    if dimension in COMPUTED_DIMENSIONS:
        out["lookback"] = _check_int(d.get("lookback"), "lookback",
                                     MIN_LOOKBACK, MAX_LOOKBACK, None)
        mode = d.get("threshold_mode", "fixed")
        if mode not in THRESHOLD_MODES:
            raise RegimeDefinitionError(f"threshold_mode must be one of {THRESHOLD_MODES}")
        out["threshold_mode"] = mode
        out["labels"] = _check_labels(d.get("labels"), dimension)
        if mode == "fixed":
            thresholds = d.get("thresholds")
            if (not isinstance(thresholds, (list, tuple)) or len(thresholds) != 2
                    or any(isinstance(t, bool) or not isinstance(t, (int, float))
                           or not math.isfinite(t) for t in thresholds)
                    or not (float(thresholds[0]) < float(thresholds[1]))):
                raise RegimeDefinitionError(
                    f"definition {def_id}: fixed mode needs two finite ascending thresholds"
                )
            out["thresholds"] = [float(thresholds[0]), float(thresholds[1])]
        else:
            quantiles = d.get("quantiles")
            if quantiles is None:
                quantiles = [1 / 3, 2 / 3]
            if (not isinstance(quantiles, (list, tuple)) or len(quantiles) != 2
                    or any(isinstance(q, bool) or not isinstance(q, (int, float))
                           or not math.isfinite(q) for q in quantiles)
                    or not (0.0 < float(quantiles[0]) < float(quantiles[1]) < 1.0)):
                raise RegimeDefinitionError(
                    f"definition {def_id}: quantiles must be two ascending values in (0, 1)"
                )
            out["quantiles"] = [float(quantiles[0]), float(quantiles[1])]
        if mode == "expanding_quantile":
            out["min_history"] = _check_int(
                d.get("min_history"), "min_history",
                out["lookback"] + 5, MAX_PERIOD_HISTORY, out["lookback"] + 10)
        if mode == "training_quantile":
            split_label = d.get("threshold_split_label")
            if not isinstance(split_label, str) or not split_label.strip():
                raise RegimeDefinitionError(
                    f"definition {def_id}: training_quantile requires threshold_split_label"
                )
            out["threshold_split_label"] = split_label.strip()
    elif dimension == "drawdown":
        thresholds = d.get("thresholds")
        if thresholds is None:
            thresholds = [0.05, 0.15]
        if (not isinstance(thresholds, (list, tuple)) or len(thresholds) != 2
                or any(isinstance(t, bool) or not isinstance(t, (int, float))
                       or not math.isfinite(t) or t <= 0 for t in thresholds)
                or not (float(thresholds[0]) < float(thresholds[1]))):
            raise RegimeDefinitionError(
                f"definition {def_id}: drawdown thresholds must be two ascending "
                "positive magnitudes (e.g. [0.05, 0.15])"
            )
        out["thresholds"] = [float(thresholds[0]), float(thresholds[1])]
        out["threshold_mode"] = "fixed"
        out["labels"] = _check_labels(d.get("labels"), "drawdown")
    elif dimension == "categorical":
        labels_supplied = d.get("labels_supplied")
        if not isinstance(labels_supplied, (list, tuple)) or not labels_supplied:
            raise RegimeDefinitionError(
                f"definition {def_id}: categorical requires labels_supplied"
            )
        cleaned: List[Optional[str]] = []
        distinct: set[str] = set()
        for i, lb in enumerate(labels_supplied):
            if lb is None:
                cleaned.append(None)
                continue
            if not isinstance(lb, str) or not lb.strip() or len(lb) > 32 \
                    or any(ch in lb for ch in "<>"):
                raise RegimeDefinitionError(
                    f"definition {def_id}: labels_supplied[{i}] must be a plain "
                    "string ≤ 32 chars (no markup)"
                )
            value = lb.strip()
            distinct.add(value)
            cleaned.append(value)
        if len(distinct) > MAX_LABELS:
            raise RegimeDefinitionError(
                f"definition {def_id}: at most {MAX_LABELS} distinct categorical labels"
            )
        provenance = d.get("provenance") or {}
        if not isinstance(provenance, dict):
            raise RegimeDefinitionError("categorical provenance must be an object")
        causality = provenance.get("causality", "unknown")
        if causality not in ("trailing", "centered", "unknown"):
            raise RegimeDefinitionError(
                "provenance.causality must be 'trailing', 'centered', or 'unknown'"
            )
        out["labels_supplied"] = cleaned
        out["provenance"] = {"source": str(provenance.get("source", ""))[:200],
                             "causality": causality,
                             "description": str(provenance.get("description", ""))[:500]}
    elif dimension == "combined":
        sources = d.get("sources")
        if (not isinstance(sources, (list, tuple)) or len(sources) != 2
                or any(not isinstance(s, str) for s in sources)
                or sources[0] == sources[1]):
            raise RegimeDefinitionError(
                f"definition {def_id}: combined requires exactly 2 distinct source ids"
            )
        out["sources"] = [sources[0], sources[1]]
    return out


MAX_PERIOD_HISTORY = 2000


# ---------------------------------------------------------------------------
# Trailing statistics (the only windows that exist here)
# ---------------------------------------------------------------------------


def trailing_stat(values: np.ndarray, lookback: int, kind: str) -> np.ndarray:
    """stat[j] over values[j−lookback+1 … j]; NaN where undefined (j < lookback−1)."""
    t = len(values)
    out = np.full(t, np.nan)
    for j in range(lookback - 1, t):
        window = values[j - lookback + 1: j + 1]
        if kind == "std":
            out[j] = float(np.std(window, ddof=1))
        else:
            out[j] = float(np.mean(window))
    return out


def drawdown_series(values: np.ndarray) -> np.ndarray:
    """dd[j] ≤ 0 from the trailing peak of the compounded level — never a
    future maximum."""
    level = np.cumprod(1.0 + values)
    peak = np.maximum.accumulate(level)
    return level / peak - 1.0


def _classify(stat: float, t1: float, t2: float, labels: Sequence[str]) -> str:
    if stat < t1:
        return labels[0]
    if stat < t2:
        return labels[1]
    return labels[2]


def _threshold_fingerprint(payload: Dict[str, Any]) -> str:
    return sha256_hex({"fp_version": "regime_threshold_v1", **payload})


def assign_labels(
    definition: Dict[str, Any],
    features: Dict[str, List[float]],
    n_periods: int,
    train_indices: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    """Effective labels per period + integrity state + threshold record.

    ``train_indices`` (recorded training membership of the named validation
    split) is required by ``training_quantile`` and must be resolved by the
    caller from exact split memberships.
    """
    dim = definition["dimension"]
    warnings: List[str] = []
    if dim == "categorical":
        causality = definition["provenance"]["causality"]
        if causality == "centered":
            return {
                "labels": [None] * n_periods,
                "integrity_status": "invalid",
                "status": "invalid",
                "thresholds_used": None, "threshold_fingerprint": None,
                "unavailable_count": n_periods,
                "warnings": ["supplied labels declare a centered (future-looking) "
                             "construction — they are not used"],
            }
        integrity = "declared"
        if causality == "unknown":
            warnings.append("label causality was not stated — treat as declared only")
        labels = list(definition["labels_supplied"])
        if len(labels) < n_periods:
            labels = labels + [None] * (n_periods - len(labels))
        labels = labels[:n_periods]
        return {
            "labels": labels, "integrity_status": integrity, "status": "ok",
            "thresholds_used": None,
            "threshold_fingerprint": _threshold_fingerprint(
                {"mode": "supplied", "causality": causality}),
            "unavailable_count": sum(1 for lb in labels if lb is None),
            "warnings": warnings,
        }

    values = np.asarray(features[definition["source_feature"]], dtype=np.float64)
    lag = definition["lag"]
    if dim == "drawdown":
        stat = drawdown_series(values)
        t1, t2 = definition["thresholds"]
        labels_out: List[Optional[str]] = [None] * n_periods
        for i in range(n_periods):
            j = i - lag
            if j < 0:
                continue
            dd = float(stat[j])
            if dd > -t1:
                labels_out[i] = definition["labels"][0]
            elif dd > -t2:
                labels_out[i] = definition["labels"][1]
            else:
                labels_out[i] = definition["labels"][2]
        return {
            "labels": labels_out, "integrity_status": "verified_causal_rule",
            "status": "ok",
            "thresholds_used": {"mode": "fixed", "values": [t1, t2]},
            "threshold_fingerprint": _threshold_fingerprint(
                {"mode": "fixed", "values": [t1, t2], "dimension": "drawdown",
                 "lag": lag}),
            "unavailable_count": sum(1 for lb in labels_out if lb is None),
            "warnings": [],
        }

    lookback = definition["lookback"]
    stat = trailing_stat(values, lookback, "std" if dim == "volatility" else "mean")
    mode = definition["threshold_mode"]
    labels_cfg = definition["labels"]
    labels_out = [None] * n_periods
    thresholds_used: Optional[Dict[str, Any]] = None
    fp_payload: Dict[str, Any] = {"dimension": dim, "lookback": lookback,
                                  "lag": lag, "mode": mode}

    if mode == "fixed":
        t1, t2 = definition["thresholds"]
        for i in range(n_periods):
            j = i - lag
            if j < lookback - 1:
                continue
            labels_out[i] = _classify(float(stat[j]), t1, t2, labels_cfg)
        integrity = "verified_causal_rule"
        thresholds_used = {"mode": "fixed", "values": [t1, t2]}
        fp_payload["values"] = [round(t1, 12), round(t2, 12)]
    elif mode == "full_sample_quantile":
        q1, q2 = definition["quantiles"]
        defined = stat[~np.isnan(stat)]
        if len(defined) < definition["min_observations"]:
            return _invalid(definition, n_periods,
                            "too few defined statistics to fit full-sample thresholds")
        t1, t2 = float(np.quantile(defined, q1)), float(np.quantile(defined, q2))
        for i in range(n_periods):
            j = i - lag
            if j < lookback - 1:
                continue
            labels_out[i] = _classify(float(stat[j]), t1, t2, labels_cfg)
        integrity = "full_sample_descriptive"
        thresholds_used = {"mode": "full_sample_quantile", "quantiles": [q1, q2],
                           "values": [t1, t2]}
        fp_payload.update({"quantiles": [q1, q2],
                           "values": [round(t1, 12), round(t2, 12)]})
        warnings.append(
            f"definition {definition['definition_id']}: thresholds were fitted on "
            "the FULL sample — descriptive only, not leakage-safe"
        )
    elif mode == "training_quantile":
        if train_indices is None:
            return _invalid(definition, n_periods,
                            "training_quantile requires a resolved validation split "
                            "training membership")
        train_stats = [float(stat[j]) for j in train_indices
                       if 0 <= j < n_periods and not np.isnan(stat[j])]
        if len(train_stats) < definition["min_observations"]:
            return _invalid(definition, n_periods,
                            "too few defined training statistics to fit thresholds")
        q1, q2 = definition["quantiles"]
        t1 = float(np.quantile(np.array(train_stats), q1))
        t2 = float(np.quantile(np.array(train_stats), q2))
        for i in range(n_periods):
            j = i - lag
            if j < lookback - 1:
                continue
            labels_out[i] = _classify(float(stat[j]), t1, t2, labels_cfg)
        integrity = "verified_from_validation_split"
        thresholds_used = {"mode": "training_quantile", "quantiles": [q1, q2],
                           "values": [t1, t2],
                           "split_label": definition["threshold_split_label"],
                           "fitted_on": len(train_stats)}
        fp_payload.update({"quantiles": [q1, q2],
                           "values": [round(t1, 12), round(t2, 12)],
                           "split_label": definition["threshold_split_label"]})
    else:  # expanding_quantile
        q1, q2 = definition["quantiles"]
        min_history = definition["min_history"]
        last_values: Optional[List[float]] = None
        for i in range(n_periods):
            j = i - lag
            if j < lookback - 1:
                continue
            history = stat[: j + 1]
            defined = history[~np.isnan(history)]
            if len(defined) < min_history:
                continue  # honestly unavailable until enough history exists
            t1 = float(np.quantile(defined, q1))
            t2 = float(np.quantile(defined, q2))
            last_values = [t1, t2]
            labels_out[i] = _classify(float(stat[j]), t1, t2, labels_cfg)
        integrity = "verified_causal_rule"
        thresholds_used = {"mode": "expanding_quantile", "quantiles": [q1, q2],
                           "min_history": min_history,
                           "last_values": last_values,
                           "note": "thresholds are re-fitted per period from "
                                   "strictly prior statistics"}
        fp_payload.update({"quantiles": [q1, q2], "min_history": min_history})

    unavailable = sum(1 for lb in labels_out if lb is None)
    if unavailable == n_periods:
        return _invalid(definition, n_periods,
                        "no period ever received a label (insufficient history)")
    return {
        "labels": labels_out, "integrity_status": integrity, "status": "ok",
        "thresholds_used": thresholds_used,
        "threshold_fingerprint": _threshold_fingerprint(fp_payload),
        "unavailable_count": unavailable,
        "warnings": warnings,
    }


def _invalid(definition: Dict[str, Any], n_periods: int, reason: str) -> Dict[str, Any]:
    return {
        "labels": [None] * n_periods, "integrity_status": "invalid",
        "status": "invalid", "thresholds_used": None,
        "threshold_fingerprint": None, "unavailable_count": n_periods,
        "warnings": [f"definition {definition['definition_id']}: {reason}"],
    }


def combine_labels(
    definition: Dict[str, Any],
    source_a: Dict[str, Any], source_b: Dict[str, Any],
    n_periods: int,
) -> Dict[str, Any]:
    """Deterministic pairwise combination; least-trusted source integrity."""
    if source_a["status"] == "invalid" or source_b["status"] == "invalid":
        return _invalid(definition, n_periods, "a source definition is invalid")
    labels_out: List[Optional[str]] = [None] * n_periods
    distinct: set[str] = set()
    for i in range(n_periods):
        a, b = source_a["labels"][i], source_b["labels"][i]
        if a is None or b is None:
            continue
        combo = f"{a}|{b}"
        distinct.add(combo)
        labels_out[i] = combo
    if len(distinct) > MAX_COMBINED_LABELS:
        return _invalid(definition, n_periods,
                        f"{len(distinct)} combined labels exceed the bound of "
                        f"{MAX_COMBINED_LABELS}")
    integrity = min(
        (source_a["integrity_status"], source_b["integrity_status"]),
        key=lambda s: _TRUST_ORDER[s],
    )
    return {
        "labels": labels_out, "integrity_status": integrity, "status": "ok",
        "thresholds_used": {"mode": "combined",
                            "sources": definition["sources"],
                            "note": "no merging of rare combinations (v1 policy)"},
        "threshold_fingerprint": _threshold_fingerprint(
            {"mode": "combined", "sources": definition["sources"],
             "a": source_a["threshold_fingerprint"],
             "b": source_b["threshold_fingerprint"]}),
        "unavailable_count": sum(1 for lb in labels_out if lb is None),
        "warnings": [],
    }


def definition_fingerprint(definition: Dict[str, Any]) -> str:
    payload = {
        "fp_version": "regime_definition_v1",
        **{k: definition.get(k) for k in (
            "definition_id", "dimension", "source_feature", "lookback", "lag",
            "threshold_mode", "thresholds", "quantiles", "min_history",
            "threshold_split_label", "labels", "sources", "min_observations")},
        "labels_supplied": definition.get("labels_supplied"),
        "provenance": definition.get("provenance"),
        "missing_value_policy": "reject",
    }
    return sha256_hex(payload)


__all__ = [
    "DIMENSIONS", "COMPUTED_DIMENSIONS", "THRESHOLD_MODES", "INTEGRITY_STATES",
    "MAX_DEFINITIONS", "MAX_LABELS", "MAX_COMBINED_LABELS", "MIN_LOOKBACK",
    "MAX_LOOKBACK", "MIN_LAG", "MAX_LAG", "MIN_REGIME_OBSERVATIONS_DEFAULT",
    "DEFAULT_LABELS", "RegimeDefinitionError", "validate_definition",
    "trailing_stat", "drawdown_series", "assign_labels", "combine_labels",
    "definition_fingerprint",
]
