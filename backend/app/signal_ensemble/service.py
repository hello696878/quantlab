"""
Signal Ensemble Lab service (v1).

Execution order (fixed, bounded, deterministic):

1. validate the universe, policies and links; PIN every linked record
2. align on explicit (entity, timestamp) keys; missingness summary
3. orient and normalise each signal (point-in-time safe by construction)
4. pairwise similarity (strict intersection, plus pair-specific overlap
   under the pairwise_complete policy) + rank/bucket/tail agreement
5. strict-intersection correlation matrix -> distance -> eigenvalue /
   effective-count diagnostics -> optional hierarchical clustering
6. explicit combination + per-observation contribution reconciliation
7. combined-score (and per-component) evaluation through the Phase 60
   policies: horizons x lags, buckets, turnover, linked Phase 55 costs
8. leave-one-signal-out, regimes, validation split, factor residual
   outcomes, multiple testing, bootstrap, sensitivity scenarios
9. fingerprints, persistence, integrity/completeness states

Every linked lab is READ-ONLY and fingerprint-pinned.  Nothing selects a
signal, derives a weight, picks a horizon/lag/threshold, or recommends,
sizes, executes or monitors anything.
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np

from app.dataset_registry import store as dataset_store
from app.experiment_registry import integration as experiment_integration
from app.experiment_registry.provenance import get_app_version, get_git_commit
from app.factor_diagnostics import store as factor_store
from app.feature_diagnostics import store as feature_store
from app.meta_labeling import store as meta_store
from app.model_validation import store as validation_store
from app.overfitting_diagnostics import multiple_testing as mt_mod
from app.regime_diagnostics import store as regime_store
from app.cost_diagnostics import store as cost_store

from app.signal_decay import buckets as bucket_mod
from app.signal_decay import costs as cost_mod
from app.signal_decay import observations as sd_obs
from app.signal_decay import statistics as stats_mod
from app.signal_decay import store as sd_store
from app.signal_decay import turnover as turnover_mod
from app.signal_decay.fingerprints import signal_definition_fingerprint

from app.signal_ensemble import EXPORT_SCHEMA_VERSION
from app.signal_ensemble import alignment as align_mod
from app.signal_ensemble import combination as combo_mod
from app.signal_ensemble import fingerprints as fp_mod
from app.signal_ensemble import normalisation as norm_mod
from app.signal_ensemble import pairwise as pair_mod
from app.signal_ensemble import redundancy as red_mod
from app.signal_ensemble import store
from app.signal_ensemble import universe as universe_mod

Key = Tuple[str, str]

MAX_ALIGNED_KEYS = 10000
MAX_HORIZONS = 6
MAX_LAGS = 3
CONTRIBUTION_ROW_LIMIT = 3000
MAX_SENSITIVITY_SCENARIOS = 24
MAX_BOOTSTRAP_RESAMPLES = 2000
MIN_BOOTSTRAP_RESAMPLES = 50
MAX_EXPORT_RUNS = 25
RARE_REGIME_MIN_OBSERVATIONS = 10
MULTIPLE_TESTING_METHODS = ("bonferroni", "holm", "bh")
DEFAULT_MULTIPLE_TESTING_ALPHA = 0.05
BOOTSTRAP_METHODS = ("timestamp", "moving_block")
BOOTSTRAP_STATISTICS = ("mean_absolute_correlation",
                        "effective_signal_count", "combination_spearman")

EXECUTION_ORDER = (
    "validate_and_pin_links", "align_and_summarise_missingness",
    "orient_and_normalise", "pairwise_similarity",
    "matrix_distance_clustering", "combine_and_reconcile",
    "horizons_turnover_costs", "loo_regimes_validation_factor_mt_bootstrap",
    "fingerprints_persist",
)

INTEGRITY_STATES = (
    "verified_from_validation_split", "verified_point_in_time",
    "verified_trailing_transformation", "supplied_descriptive",
    "contemporaneous_descriptive", "full_sample_descriptive", "unknown",
    "invalid")

BASELINE_ACCEPTABLE_INTEGRITY = frozenset({
    "verified_from_validation_split", "verified_point_in_time",
    "verified_trailing_transformation"})
BASELINE_ACCEPTABLE_COMPLETENESS = frozenset({"complete", "partial"})


class SignalEnsembleError(ValueError):
    """Invalid request (HTTP 422)."""


class NotFoundError(LookupError):
    """Unknown run (HTTP 404)."""


class ConflictError(RuntimeError):
    """Illegal state transition (HTTP 409)."""


class InternalExecutionError(RuntimeError):
    """Unexpected execution failure (HTTP 500)."""


ENGINE_ERRORS = (
    SignalEnsembleError, universe_mod.UniverseError,
    norm_mod.NormalisationError, pair_mod.PairwiseError,
    red_mod.RedundancyError, combo_mod.CombinationError,
    align_mod.AlignmentError, sd_obs.ObservationError,
    stats_mod.StatisticsError, bucket_mod.BucketError,
    turnover_mod.TurnoverError, cost_mod.CostError, fp_mod.FingerprintError,
)


def _optional_positive_id(value: Any, field: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SignalEnsembleError(f"{field} must be a positive integer")
    return int(value)


def _finite_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _common_value_keys(keys: Sequence[Key],
                       values: Dict[str, Dict[Key, Optional[float]]],
                       signal_ids: Sequence[str]) -> List[Key]:
    """Keys where every selected post-transformation value is available."""
    return [key for key in keys
            if all(values[signal_id].get(key) is not None
                   for signal_id in signal_ids)]


def _combined_provenance(observation: Dict[str, Any],
                         signal_ids: Sequence[str],
                         grid: Dict[str, Any]) -> Dict[str, Any]:
    """Latest input availability and unambiguous validation sample id."""
    key = (observation["entity_id"], observation["timestamp"])
    present = [signal_id for signal_id in signal_ids
               if signal_id not in observation["missing_signal_ids"]]
    if not present:
        return {
            "available_at": observation["timestamp"],
            "availability_assumed": True,
            "universe_membership_id": None,
        }
    membership_ids = {
        grid["membership_id"][signal_id].get(key)
        for signal_id in present
        if grid["membership_id"][signal_id].get(key) is not None
    }
    if len(membership_ids) > 1:
        raise SignalEnsembleError(
            f"components reference different validation samples at "
            f"{key[0]} / {key[1]}")
    return {
        "available_at": max(
            grid["available_at"][signal_id][key] for signal_id in present),
        "availability_assumed": any(
            grid["assumed"][signal_id].get(key, True)
            for signal_id in present),
        "universe_membership_id": (
            next(iter(membership_ids)) if membership_ids else None),
    }


def _synthetic_combination_rows(
        observations: Sequence[Dict[str, Any]], *,
        signal_ids: Sequence[str], grid: Dict[str, Any],
        prefix: str) -> List[Dict[str, Any]]:
    """Phase 60 rows without compressing unavailable timestamps.

    Null rows remain on the per-entity grid so an h-step outcome is always
    measured over h stored grid observations, not h available scores.
    """
    out: List[Dict[str, Any]] = []
    for index, observation in enumerate(observations):
        available = observation["state"] == "available"
        provenance = (_combined_provenance(observation, signal_ids, grid)
                      if available else {
                          "available_at": observation["timestamp"],
                          "availability_assumed": True,
                          "universe_membership_id": None,
                      })
        out.append({
            "observation_id": f"{prefix}-{index:05d}",
            "entity_id": observation["entity_id"],
            "source_timestamp": observation["timestamp"],
            "generated_at": None,
            "available_at": provenance["available_at"],
            "availability_assumed": provenance["availability_assumed"],
            "raw_value": (
                observation["combined_score"] if available else None),
            "universe_membership_id":
                provenance["universe_membership_id"],
            "metadata": {},
        })
    out.sort(key=lambda row: (row["entity_id"], row["source_timestamp"]))
    return out


def _matrix_rows(signal_ids: Sequence[str], keys: Sequence[Key],
                 values: Dict[str, Dict[Key, Optional[float]]], *,
                 method: str, minimum: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for signal_a, signal_b in pair_mod.pair_order(signal_ids):
        correlation = stats_mod.correlation(
            [values[signal_a][key] for key in keys],
            [values[signal_b][key] for key in keys],
            method=method, minimum_observations=minimum,
            overlapping=False)
        rows.append({
            "signal_a": signal_a, "signal_b": signal_b,
            "correlations": {method: correlation}})
    return rows

# Analysis policy
# ---------------------------------------------------------------------------

def _validate_analysis_policy(raw: Any, *, has_prices: bool,
                              cost_linked: bool) -> Dict[str, Any]:
    cfg = dict(raw or {})
    unknown = sorted(set(cfg) - {
        "horizons", "entry_lags", "bucket", "turnover", "outcome",
        "reference_notional", "multiple_testing", "bootstrap",
        "sensitivity", "leave_one_out"})
    if unknown:
        raise SignalEnsembleError(f"unknown analysis policy keys: {unknown}")

    horizons = cfg.get("horizons") or []
    if not isinstance(horizons, list) or len(horizons) > MAX_HORIZONS:
        raise SignalEnsembleError(
            f"horizons must be a list of at most {MAX_HORIZONS} integers")
    seen: Set[int] = set()
    parsed_horizons: List[int] = []
    for h in horizons:
        if isinstance(h, bool) or not isinstance(h, int) \
                or not (1 <= h <= 250):
            raise SignalEnsembleError(
                "each horizon must be an integer in [1, 250] "
                "(observations on the stored grid; clock units are "
                "deferred because they would require resampling)")
        if h in seen:
            raise SignalEnsembleError(f"duplicate horizon {h}")
        seen.add(h)
        parsed_horizons.append(h)
    if parsed_horizons and not has_prices:
        raise SignalEnsembleError(
            "horizon evaluation requires prices; none were supplied")

    lags = cfg.get("entry_lags") or [0]
    if not isinstance(lags, list) or not lags or len(lags) > MAX_LAGS:
        raise SignalEnsembleError(
            f"entry_lags must be a non-empty list of at most {MAX_LAGS} "
            f"integers")
    parsed_lags: List[int] = []
    for lag in lags:
        if isinstance(lag, bool) or not isinstance(lag, int) \
                or not (0 <= lag <= 60):
            raise SignalEnsembleError(
                "each entry lag must be an integer in [0, 60]")
        if lag in parsed_lags:
            raise SignalEnsembleError(f"duplicate entry lag {lag}")
        parsed_lags.append(lag)

    bucket = bucket_mod.validate_bucket_config(cfg.get("bucket") or {
        "bucket_count": 3, "scope": "per_timestamp",
        "minimum_per_bucket": 2})
    turnover = turnover_mod.validate_turnover_config(cfg.get("turnover"))

    outcome = dict(cfg.get("outcome") or {})
    bad = sorted(set(outcome) - {"price_field", "extreme_loss_policy"})
    if bad:
        raise SignalEnsembleError(f"unknown outcome keys: {bad}")
    price_field = outcome.get("price_field", "close")
    if not isinstance(price_field, str) or not (1 <= len(price_field) <= 40):
        raise SignalEnsembleError("outcome.price_field must be 1-40 chars")
    extreme = outcome.get("extreme_loss_policy", "report_verbatim")
    if extreme not in ("report_verbatim", "mark_unavailable"):
        raise SignalEnsembleError(
            "outcome.extreme_loss_policy must be report_verbatim or "
            "mark_unavailable")

    reference_notional = cfg.get("reference_notional")
    if cost_linked:
        if reference_notional is None:
            raise SignalEnsembleError(
                "a linked cost run requires an explicit reference_notional")
        reference_notional = cost_mod.validate_reference_notional(
            reference_notional)
    elif reference_notional is not None:
        raise SignalEnsembleError(
            "reference_notional requires a linked cost run")

    mt = cfg.get("multiple_testing")
    if mt is not None:
        if not isinstance(mt, dict):
            raise SignalEnsembleError("multiple_testing must be an object")
        bad = sorted(set(mt) - {"methods", "alpha", "family"})
        if bad:
            raise SignalEnsembleError(
                f"unknown multiple_testing keys: {bad}")
        methods = mt.get("methods") or []
        if not methods or not set(methods) <= set(MULTIPLE_TESTING_METHODS):
            raise SignalEnsembleError(
                f"multiple_testing.methods must be a non-empty subset of "
                f"{list(MULTIPLE_TESTING_METHODS)}")
        alpha = mt.get("alpha", DEFAULT_MULTIPLE_TESTING_ALPHA)
        if isinstance(alpha, bool) or not isinstance(alpha, (int, float)) \
                or not (0 < float(alpha) < 1):
            raise SignalEnsembleError(
                "multiple_testing.alpha must lie in (0, 1)")
        family = mt.get("family") or (
            "Spearman p-values of the canonical strict-intersection signal "
            "pairs")
        mt = {"methods": list(methods), "alpha": float(alpha),
              "family": str(family)}

    bootstrap = cfg.get("bootstrap")
    if bootstrap is not None:
        if not isinstance(bootstrap, dict):
            raise SignalEnsembleError("bootstrap must be an object")
        bad = sorted(set(bootstrap) - {"method", "statistics", "seed",
                                       "resamples", "block_length"})
        if bad:
            raise SignalEnsembleError(f"unknown bootstrap keys: {bad}")
        method = bootstrap.get("method")
        if method not in BOOTSTRAP_METHODS:
            raise SignalEnsembleError(
                f"bootstrap.method must be one of {list(BOOTSTRAP_METHODS)} "
                f"— timestamp resampling keeps whole cross-sections intact")
        statistics = bootstrap.get("statistics") or []
        if not statistics or not set(statistics) <= set(BOOTSTRAP_STATISTICS):
            raise SignalEnsembleError(
                f"bootstrap.statistics must be a non-empty subset of "
                f"{list(BOOTSTRAP_STATISTICS)}")
        seed = bootstrap.get("seed")
        if isinstance(seed, bool) or not isinstance(seed, int) \
                or not (0 <= seed <= 2 ** 31 - 1):
            raise SignalEnsembleError(
                "bootstrap.seed must be an integer in [0, 2^31-1]")
        resamples = bootstrap.get("resamples")
        if isinstance(resamples, bool) or not isinstance(resamples, int) \
                or not (MIN_BOOTSTRAP_RESAMPLES <= resamples
                        <= MAX_BOOTSTRAP_RESAMPLES):
            raise SignalEnsembleError(
                f"bootstrap.resamples must be an integer in "
                f"[{MIN_BOOTSTRAP_RESAMPLES}, {MAX_BOOTSTRAP_RESAMPLES}]")
        block_length = bootstrap.get("block_length")
        if method == "moving_block":
            if isinstance(block_length, bool) \
                    or not isinstance(block_length, int) \
                    or not (2 <= block_length <= 250):
                raise SignalEnsembleError(
                    "moving_block requires an integer block_length in "
                    "[2, 250]")
        elif block_length is not None:
            raise SignalEnsembleError(
                "block_length is only valid for moving_block")
        bootstrap = {"method": method, "statistics": list(statistics),
                     "seed": seed, "resamples": resamples,
                     "block_length": block_length}

    sensitivity = cfg.get("sensitivity")
    if sensitivity is not None:
        if not isinstance(sensitivity, dict):
            raise SignalEnsembleError("sensitivity must be an object")
        bad = sorted(set(sensitivity) - {"scenarios"})
        if bad:
            raise SignalEnsembleError(f"unknown sensitivity keys: {bad}")
        scenarios = sensitivity.get("scenarios")
        if not isinstance(scenarios, list) or not scenarios \
                or len(scenarios) > MAX_SENSITIVITY_SCENARIOS - 1:
            raise SignalEnsembleError(
                f"sensitivity.scenarios must be a list of 1 to "
                f"{MAX_SENSITIVITY_SCENARIOS - 1} scenario overrides")
        allowed = {"label", "normalisation", "orientations", "weights",
                   "weight_normalisation", "missing_component_policy",
                   "minimum_component_count", "matrix_method",
                   "bucket_count", "horizon", "entry_lag"}
        for scenario in scenarios:
            if not isinstance(scenario, dict):
                raise SignalEnsembleError(
                    "each sensitivity scenario must be an object")
            bad = sorted(set(scenario) - allowed)
            if bad:
                raise SignalEnsembleError(
                    f"unknown sensitivity scenario keys: {bad}")
            if not scenario.get("label") \
                    or not isinstance(scenario["label"], str):
                raise SignalEnsembleError(
                    "each sensitivity scenario needs a string label")
            if len(scenario["label"].strip()) > 100:
                raise SignalEnsembleError(
                    "sensitivity scenario labels must be at most 100 chars")
            matrix_method = scenario.get("matrix_method")
            if (matrix_method is not None
                    and matrix_method not in ("pearson", "spearman")):
                raise SignalEnsembleError(
                    "scenario matrix_method must be pearson or spearman")
            bucket_count = scenario.get("bucket_count")
            if bucket_count is not None and (
                    isinstance(bucket_count, bool)
                    or not isinstance(bucket_count, int)
                    or not (2 <= bucket_count <= 10)):
                raise SignalEnsembleError(
                    "scenario bucket_count must be an integer in [2, 10]")
            horizon = scenario.get("horizon")
            if horizon is not None and (
                    isinstance(horizon, bool) or not isinstance(horizon, int)
                    or not (1 <= horizon <= 250)):
                raise SignalEnsembleError(
                    "scenario horizon must be an integer in [1, 250]")
            if horizon is not None and not has_prices:
                raise SignalEnsembleError(
                    "scenario horizon evaluation requires supplied prices")
            entry_lag = scenario.get("entry_lag")
            if entry_lag is not None and (
                    isinstance(entry_lag, bool)
                    or not isinstance(entry_lag, int)
                    or not (0 <= entry_lag <= 60)):
                raise SignalEnsembleError(
                    "scenario entry_lag must be an integer in [0, 60]")
        sensitivity = {"scenarios": scenarios}

    leave_one_out = cfg.get("leave_one_out", True)
    if not isinstance(leave_one_out, bool):
        raise SignalEnsembleError("leave_one_out must be a boolean")

    return {
        "horizons": parsed_horizons,
        "entry_lags": parsed_lags,
        "bucket": bucket,
        "turnover": turnover,
        "outcome": {"price_field": price_field,
                    "extreme_loss_policy": extreme},
        "reference_notional": reference_notional,
        "multiple_testing": mt,
        "bootstrap": bootstrap,
        "sensitivity": sensitivity,
        "leave_one_out": leave_one_out,
        "reconciliation_tolerance": combo_mod.RECONCILIATION_TOLERANCE,
    }


# ---------------------------------------------------------------------------
# Link resolution (create-time) and pinning (execute-time)
# ---------------------------------------------------------------------------

def _resolve_links(payload: Dict[str, Any]) -> Dict[str, Any]:
    linked: Dict[str, Any] = {"ids": {}}

    dataset_version_id = _optional_positive_id(
        payload.get("dataset_version_id"), "dataset_version_id")
    if dataset_version_id is not None:
        version = dataset_store.get_version(dataset_version_id)
        if version is None:
            raise SignalEnsembleError(
                f"dataset version {dataset_version_id} not found")
        linked["dataset_identity"] = {
            "dataset_version_id": dataset_version_id,
            "dataset_name": version.get("dataset_name"),
            "version_label": version.get("version_label"),
            "schema_fingerprint": version.get("schema_fingerprint"),
            "manifest_fingerprint": version.get("manifest_fingerprint"),
            "invalidated": bool(version.get("invalidated")),
        }
    linked["ids"]["dataset_version_id"] = dataset_version_id

    sd_run_id = _optional_positive_id(payload.get("signal_decay_run_id"),
                                      "signal_decay_run_id")
    if sd_run_id is not None:
        srun = sd_store.get_run(sd_run_id)
        if srun is None or srun.get("status") != "completed":
            raise SignalEnsembleError(
                "signal_decay_run_id must reference a completed signal "
                "decay run")
        linked["signal_decay_identity"] = {
            "signal_decay_run_id": sd_run_id,
            "signal_decay_run_name": srun["name"],
            "configuration_fingerprint":
                srun.get("configuration_fingerprint"),
            "result_fingerprint": srun.get("result_fingerprint"),
            "note": ("read-only context: stored per-signal decay results "
                     "are never recomputed or mutated here"),
        }
    linked["ids"]["signal_decay_run_id"] = sd_run_id

    feature_run_id = _optional_positive_id(payload.get("feature_run_id"),
                                           "feature_run_id")
    if feature_run_id is not None:
        frun = feature_store.get_run(feature_run_id)
        if frun is None or frun.get("status") != "completed":
            raise SignalEnsembleError(
                "feature_run_id must reference a completed feature "
                "diagnostics run")
        linked["feature_identity"] = {
            "feature_run_id": feature_run_id,
            "feature_run_name": frun["name"],
            "configuration_fingerprint":
                frun.get("configuration_fingerprint"),
            "result_fingerprint": frun.get("result_fingerprint"),
            "note": "identity pinning only in v1; no importance number "
                    "flows into this lab",
        }
    linked["ids"]["feature_run_id"] = feature_run_id

    meta_label_run_id = _optional_positive_id(
        payload.get("meta_label_run_id"), "meta_label_run_id")
    if meta_label_run_id is not None:
        mrun = meta_store.get_run(meta_label_run_id)
        if mrun is None or mrun.get("status") != "completed":
            raise SignalEnsembleError(
                "meta_label_run_id must reference a completed meta-labeling "
                "run")
        linked["meta_label_identity"] = {
            "meta_label_run_id": meta_label_run_id,
            "meta_label_run_name": mrun["name"],
            "configuration_fingerprint":
                mrun.get("configuration_fingerprint"),
            "result_fingerprint": mrun.get("result_fingerprint"),
            "note": "identity pinning only in v1; a stored probability is "
                    "treated as a descriptive score",
        }
    linked["ids"]["meta_label_run_id"] = meta_label_run_id

    validation_run_id = _optional_positive_id(
        payload.get("validation_run_id"), "validation_run_id")
    split_label = payload.get("validation_split_label")
    if validation_run_id is not None:
        vrun = validation_store.get_run(validation_run_id)
        if vrun is None or vrun.get("status") != "completed":
            raise SignalEnsembleError(
                "validation_run_id must reference a completed "
                "model-validation run")
        splits = validation_store.list_splits(validation_run_id)
        if not splits:
            raise SignalEnsembleError(
                "the linked validation run has no splits")
        if split_label is None:
            split_label = splits[0]["split_label"]
        chosen = next((s for s in splits
                       if s["split_label"] == split_label), None)
        if chosen is None:
            raise SignalEnsembleError(
                f"validation split {split_label!r} not found in run "
                f"{validation_run_id}")
        linked["validation_identity"] = {
            "validation_run_id": validation_run_id,
            "validation_run_name": vrun["name"],
            "configuration_fingerprint":
                vrun.get("configuration_fingerprint"),
            "split_fingerprint": chosen["split_fingerprint"],
            "split_label": split_label,
            "leakage_clean": vrun.get("leakage_clean"),
        }
    elif split_label is not None:
        raise SignalEnsembleError(
            "validation_split_label requires validation_run_id")
    linked["ids"]["validation_run_id"] = validation_run_id

    regime_run_id = _optional_positive_id(payload.get("regime_run_id"),
                                          "regime_run_id")
    regime_definition_id = payload.get("regime_definition_id")
    if regime_run_id is not None:
        rrun = regime_store.get_run(regime_run_id)
        if rrun is None or rrun.get("status") != "completed":
            raise SignalEnsembleError(
                "regime_run_id must reference a completed regime "
                "diagnostics run")
        if not regime_definition_id:
            raise SignalEnsembleError(
                "regime linkage requires an explicit regime_definition_id")
        definition = next(
            (d for d in regime_store.list_definitions(rrun["id"])
             if d["definition_id"] == regime_definition_id), None)
        if definition is None:
            raise SignalEnsembleError(
                f"regime definition {regime_definition_id!r} not found in "
                f"run {regime_run_id}")
        linked["regime_identity"] = {
            "regime_run_id": regime_run_id,
            "regime_run_name": rrun["name"],
            "configuration_fingerprint":
                rrun.get("configuration_fingerprint"),
            "result_fingerprint": rrun.get("result_fingerprint"),
            "definition_fingerprint":
                definition.get("definition_fingerprint"),
            "regime_definition_id": regime_definition_id,
        }
    elif regime_definition_id:
        raise SignalEnsembleError(
            "regime_definition_id requires regime_run_id")
    linked["ids"]["regime_run_id"] = regime_run_id

    cost_run_id = _optional_positive_id(
        payload.get("cost_diagnostic_run_id"), "cost_diagnostic_run_id")
    if cost_run_id is not None:
        crun = cost_store.get_run(cost_run_id)
        if crun is None:
            raise SignalEnsembleError(
                f"cost diagnostics run {cost_run_id} not found")
        model = cost_store.get_cost_model(cost_run_id)
        if model is None:
            raise SignalEnsembleError(
                "the linked cost diagnostics run stores no cost model")
        linked["cost_identity"] = {
            "cost_diagnostic_run_id": cost_run_id,
            "cost_run_name": crun["name"],
            "model_fingerprint": model.get("fingerprint"),
        }
    linked["ids"]["cost_diagnostic_run_id"] = cost_run_id

    factor_run_id = _optional_positive_id(payload.get("factor_run_id"),
                                          "factor_run_id")
    if factor_run_id is not None:
        farun = factor_store.get_run(factor_run_id)
        if farun is None or farun.get("status") != "completed":
            raise SignalEnsembleError(
                "factor_run_id must reference a completed factor "
                "diagnostics run")
        linked["factor_identity"] = {
            "factor_run_id": factor_run_id,
            "factor_run_name": farun["name"],
            "configuration_fingerprint":
                farun.get("configuration_fingerprint"),
            "result_fingerprint": farun.get("result_fingerprint"),
            "note": ("the combined score's OUTCOMES can be compared against "
                     "the factor run's stored residuals (read-only); no "
                     "stored factor-residualised SIGNAL series exists in "
                     "this repository, and automatic residualisation of "
                     "signal values is prohibited, so signal-value "
                     "residual redundancy is deferred with this reason"),
        }
    linked["ids"]["factor_run_id"] = factor_run_id
    return linked


def _assert_pinned(label: str, current: Dict[str, Any],
                   identity: Dict[str, Any],
                   fields: Dict[str, str]) -> None:
    for current_field, identity_field in fields.items():
        pinned = identity.get(identity_field)
        if pinned is None:
            continue
        if current.get(current_field) != pinned:
            raise ConflictError(
                f"the linked {label}'s {current_field} changed since this "
                f"run pinned it; results would not be reproducible, so "
                f"execution is refused")


def _pin_all(run: Dict[str, Any], links: Dict[str, Any]) -> None:
    checks = (
        ("signal decay run", sd_store.get_run, "signal_decay_run_id",
         links.get("signal_decay_identity")),
        ("feature run", feature_store.get_run, "feature_run_id",
         links.get("feature_identity")),
        ("meta-labeling run", meta_store.get_run, "meta_label_run_id",
         links.get("meta_label_identity")),
        ("validation run", validation_store.get_run, "validation_run_id",
         links.get("validation_identity")),
        ("factor run", factor_store.get_run, "factor_run_id",
         links.get("factor_identity")),
    )
    for label, getter, id_field, identity in checks:
        if not identity:
            continue
        current = getter(run[id_field])
        if current is None:
            raise ConflictError(f"the linked {label} is unavailable")
        _assert_pinned(label, current, identity, {
            "configuration_fingerprint": "configuration_fingerprint",
            "result_fingerprint": "result_fingerprint"})
    regime_identity = links.get("regime_identity")
    if regime_identity:
        rrun = regime_store.get_run(run["regime_run_id"])
        if rrun is None:
            raise ConflictError("the linked regime run is unavailable")
        _assert_pinned("regime run", rrun, regime_identity, {
            "configuration_fingerprint": "configuration_fingerprint",
            "result_fingerprint": "result_fingerprint"})
    cost_identity = links.get("cost_identity")
    if cost_identity:
        model = cost_store.get_cost_model(run["cost_diagnostic_run_id"])
        if model is None:
            raise ConflictError("the linked cost model is unavailable")
        _assert_pinned("cost model", model, cost_identity,
                       {"fingerprint": "model_fingerprint"})


# ---------------------------------------------------------------------------
# Run creation
# ---------------------------------------------------------------------------

def create_run(payload: Dict[str, Any], *,
               demo_key: Optional[str] = None) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise SignalEnsembleError("the request body must be an object")

    name = payload.get("name")
    if not isinstance(name, str) or not (1 <= len(name) <= 200):
        raise SignalEnsembleError("run name must be 1-200 characters")
    description = payload.get("description", "")
    if not isinstance(description, str) or len(description) > 2000:
        raise SignalEnsembleError("description must be <= 2000 characters")

    uni = universe_mod.validate_universe(payload.get("universe"))
    orientations = universe_mod.validate_orientations(
        payload.get("orientations"), uni["signal_ids"])
    normalisation = norm_mod.validate_normalisation(
        payload.get("normalisation"), uni["signal_ids"])
    combination = combo_mod.validate_combination_policy(
        payload.get("combination") or {"mode": "equal_weight"},
        uni["signal_ids"])
    similarity = pair_mod.validate_similarity_policy(
        payload.get("similarity"))
    similarity["clustering"] = red_mod.validate_clustering(
        similarity.get("clustering"))

    prices_raw = payload.get("prices")
    links = _resolve_links(payload)
    analysis = _validate_analysis_policy(
        payload.get("analysis"), has_prices=prices_raw is not None,
        cost_linked=links.get("cost_identity") is not None)
    if prices_raw is not None:
        sd_obs.validate_prices(prices_raw,
                               analysis["outcome"]["price_field"])
        if not analysis["horizons"]:
            raise SignalEnsembleError(
                "prices were supplied but no horizons are configured")

    grid = align_mod.build_grid(uni["observations"])
    if len(grid["keys"]) > MAX_ALIGNED_KEYS:
        raise SignalEnsembleError(
            f"the aligned universe holds {len(grid['keys'])} "
            f"(entity, timestamp) keys; at most {MAX_ALIGNED_KEYS} are "
            f"supported")
    strict_keys = align_mod.strict_intersection(grid, uni["signal_ids"])

    definition_fps = {
        signal_id: signal_definition_fingerprint(
            uni["definitions"][signal_id],
            links.get("dataset_identity"))
        for signal_id in uni["signal_ids"]}
    universe_fp = fp_mod.universe_fingerprint(
        uni, definition_fps, links.get("dataset_identity"))
    combination_fp = fp_mod.combination_policy_fingerprint(
        combination, orientations, normalisation)
    similarity_fp = fp_mod.similarity_policy_fingerprint(
        similarity, uni["alignment_policy"])
    analysis_fp = fp_mod.analysis_policy_fingerprint(analysis)
    configuration_fp = fp_mod.configuration_fingerprint(
        universe_fp, combination_fp, similarity_fp, analysis_fp, links)

    stamps = grid["timestamps"]
    run = store.insert_run({
        "name": name, "description": description,
        "combination_mode": combination["mode"],
        "alignment_policy": uni["alignment_policy"],
        "frequency": uni["frequency"],
        "signal_count": len(uni["signal_ids"]),
        "entity_count": len(grid["entities"]),
        "observation_count": sum(
            len(rows) for rows in uni["observations"].values()),
        "strict_intersection_count": len(strict_keys),
        "observation_start": stamps[0] if stamps else None,
        "observation_end": stamps[-1] if stamps else None,
        "configuration": {
            "universe": payload.get("universe"),
            "orientations": orientations,
            "normalisation": normalisation,
            "combination": {key: value for key, value
                            in (payload.get("combination")
                                or {"mode": "equal_weight"}).items()},
            "similarity": payload.get("similarity") or {},
            "analysis": payload.get("analysis") or {},
            "prices": prices_raw,
            "links": links,
        },
        "universe_fingerprint": universe_fp,
        "combination_fingerprint": combination_fp,
        "similarity_fingerprint": similarity_fp,
        "analysis_fingerprint": analysis_fp,
        "configuration_fingerprint": configuration_fp,
        "dataset_version_id": links["ids"]["dataset_version_id"],
        "signal_decay_run_id": links["ids"]["signal_decay_run_id"],
        "feature_run_id": links["ids"]["feature_run_id"],
        "meta_label_run_id": links["ids"]["meta_label_run_id"],
        "validation_run_id": links["ids"]["validation_run_id"],
        "regime_run_id": links["ids"]["regime_run_id"],
        "cost_diagnostic_run_id": links["ids"]["cost_diagnostic_run_id"],
        "factor_run_id": links["ids"]["factor_run_id"],
        "app_version": get_app_version(), "git_commit": get_git_commit(),
        "notes": payload.get("notes"), "demo_key": demo_key,
    })
    return run


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def execute_run(run_id: int, *,
                create_experiment: bool = False) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"signal ensemble run {run_id} not found")
    if run["status"] == "running":
        raise ConflictError("the run is already executing")
    if run["status"] == "invalidated":
        raise ConflictError("an invalidated run cannot be re-executed")
    started = store._now()
    store.update_run(run_id, {"status": "running", "started_at": started,
                              "error_message": None})
    try:
        return _execute_body(run_id, create_experiment)
    except ENGINE_ERRORS as exc:
        store.mark_failed(run_id, str(exc), store._now())
        raise
    except ConflictError:
        store.update_run(run_id, {"status": run["status"]})
        raise
    except Exception as exc:  # noqa: BLE001 — honest failure state
        store.mark_failed(run_id, f"internal execution error: {exc}",
                          store._now())
        raise InternalExecutionError(str(exc)) from exc


def _execute_body(run_id: int, create_experiment: bool) -> Dict[str, Any]:
    run = store.get_run(run_id)
    configuration = run["configuration"]
    links = configuration.get("links") or {}
    warnings: List[str] = []

    uni = universe_mod.validate_universe(configuration.get("universe"))
    orientations = universe_mod.validate_orientations(
        configuration.get("orientations"), uni["signal_ids"])
    normalisation = norm_mod.validate_normalisation(
        configuration.get("normalisation"), uni["signal_ids"])
    combination_policy = combo_mod.validate_combination_policy(
        configuration.get("combination") or {"mode": "equal_weight"},
        uni["signal_ids"])
    similarity = pair_mod.validate_similarity_policy(
        configuration.get("similarity"))
    similarity["clustering"] = red_mod.validate_clustering(
        similarity.get("clustering"))
    analysis = _validate_analysis_policy(
        configuration.get("analysis"),
        has_prices=configuration.get("prices") is not None,
        cost_linked=links.get("cost_identity") is not None)
    prices = (sd_obs.validate_prices(configuration["prices"],
                                     analysis["outcome"]["price_field"])
              if configuration.get("prices") is not None else None)

    _pin_all(run, links)
    dataset_identity = links.get("dataset_identity") or {}
    if dataset_identity.get("invalidated"):
        warnings.append(
            f"the linked dataset version "
            f"{dataset_identity.get('version_label')} is marked invalidated "
            f"in Dataset Lineage; results are reported but their input "
            f"identity is disputed")

    signal_ids = uni["signal_ids"]
    grid = align_mod.build_grid(uni["observations"])
    strict_keys = align_mod.strict_intersection(grid, signal_ids)
    missingness = align_mod.missingness_summary(grid, signal_ids,
                                                strict_keys)

    # --- orientation + normalisation -----------------------------------
    oriented = norm_mod.orient_values(grid["values"], orientations)
    for signal_id in signal_ids:
        if orientations[signal_id] == "multiply_by_negative_one":
            warnings.append(
                f"signal {signal_id} is used with an explicit user-declared "
                f"inversion (multiply_by_negative_one); raw stored values "
                f"are unchanged and the inversion is never called a "
                f"correction")

    stored_keys = {signal_id: [(r["entity_id"], r["source_timestamp"])
                               for r in uni["observations"][signal_id]]
                   for signal_id in signal_ids}
    normalised: Dict[str, Dict[Key, Optional[float]]] = {}
    normalisation_reasons: Dict[str, Dict[str, int]] = {}
    for signal_id in signal_ids:
        result = norm_mod.normalise_signal(
            oriented=oriented[signal_id],
            stored_keys=stored_keys[signal_id],
            config=normalisation[signal_id],
            tie_policy=uni["definitions"][signal_id]["tie_policy"])
        normalised[signal_id] = result["values"]
        normalisation_reasons[signal_id] = result["reasons"]

    # rank_average combines rank percentiles regardless of the per-signal
    # similarity normalisation — an explicit property of the mode.
    if combination_policy["mode"] == "rank_average":
        combination_inputs: Dict[str, Dict[Key, Optional[float]]] = {}
        for signal_id in signal_ids:
            result = norm_mod.normalise_signal(
                oriented=oriented[signal_id],
                stored_keys=stored_keys[signal_id],
                config={"mode": "cross_sectional_rank_percentile",
                        "ddof": 1, "minimum_observations":
                            normalisation[signal_id]
                            ["minimum_observations"],
                        "window": None, "include_current": False},
                tie_policy=uni["definitions"][signal_id]["tie_policy"])
            combination_inputs[signal_id] = result["values"]
    else:
        combination_inputs = normalised

    matrix_keys = _common_value_keys(strict_keys, normalised, signal_ids)
    missingness["post_normalisation_intersection_keys"] = len(matrix_keys)
    if len(matrix_keys) < len(strict_keys):
        warnings.append(
            f"{len(strict_keys) - len(matrix_keys)} stored strict-"
            f"intersection key(s) are unavailable after the configured "
            f"normalisation; every matrix cell uses the remaining common "
            f"post-normalisation intersection of {len(matrix_keys)} keys")

    # --- pairwise similarity -------------------------------------------
    pairs = pair_mod.pair_order(signal_ids)
    pairwise_rows: List[Dict[str, Any]] = []

    def _comparable(a: str, b: str) -> bool:
        mode_a = normalisation[a]["mode"]
        mode_b = normalisation[b]["mode"]
        if mode_a != mode_b:
            return False
        if mode_a == "none":
            return uni["definitions"][a]["unit"] \
                == uni["definitions"][b]["unit"]
        return True

    outcome_by_key: Optional[Dict[Key, float]] = None
    if prices is not None and analysis["horizons"] and matrix_keys:
        tail_source = [{
            "observation_id": f"tail-{index:05d}",
            "entity_id": key[0],
            "source_timestamp": key[1],
            "generated_at": None,
            "available_at": max(
                grid["available_at"][signal_id][key]
                for signal_id in signal_ids),
            "availability_assumed": any(
                grid["assumed"][signal_id].get(key, True)
                for signal_id in signal_ids),
            "raw_value": 0.0,
            "universe_membership_id": None,
            "metadata": {},
        } for index, key in enumerate(matrix_keys)]
        tail_built = sd_obs.build_pairs(
            tail_source, target_type="forward_return", prices=prices,
            supplied=None, horizon=analysis["horizons"][0],
            entry_lag=analysis["entry_lags"][0],
            extreme_loss_policy=analysis["outcome"]
            ["extreme_loss_policy"])
        outcome_by_key = {
            (pair["entity_id"], pair["signal_timestamp"]):
                pair["outcome_value"]
            for pair in tail_built["pairs"]}

    def _flatten(row: Dict[str, Any]) -> Dict[str, Any]:
        correlations = row["correlations"]
        pearson = correlations.get("pearson") or {}
        spearman = correlations.get("spearman") or {}
        kendall = correlations.get("kendall") or {}
        row["pearson"] = pearson.get("statistic")
        row["pearson_p"] = pearson.get("p_value")
        row["spearman"] = spearman.get("statistic")
        row["spearman_p"] = spearman.get("p_value")
        row["kendall"] = kendall.get("statistic")
        row["kendall_p"] = kendall.get("p_value")
        return row

    for signal_a, signal_b in pairs:
        row = _flatten(pair_mod.pair_row(
            signal_a, signal_b,
            values_a=normalised[signal_a], values_b=normalised[signal_b],
            keys=matrix_keys,
            stored_a=len(stored_keys[signal_a]),
            stored_b=len(stored_keys[signal_b]),
            policy=similarity, alignment_mode="strict_intersection",
            comparable_scale=_comparable(signal_a, signal_b)))
        row["agreement"] = pair_mod.bucket_agreement(
            signal_a, signal_b,
            values_a=normalised[signal_a], values_b=normalised[signal_b],
            keys=matrix_keys,
            bucket_count=similarity["agreement_bucket_count"])
        row["tails"] = pair_mod.tail_cooccurrence(
            signal_a, signal_b,
            values_a=normalised[signal_a], values_b=normalised[signal_b],
            keys=matrix_keys, quantile=similarity["tail_quantile"],
            outcomes=outcome_by_key)
        pairwise_rows.append(row)
        if uni["alignment_policy"] == "pairwise_complete":
            overlap_keys = align_mod.pairwise_overlap(grid, signal_a,
                                                      signal_b)
            pairwise_rows.append(_flatten(pair_mod.pair_row(
                signal_a, signal_b,
                values_a=normalised[signal_a],
                values_b=normalised[signal_b],
                keys=overlap_keys,
                stored_a=len(stored_keys[signal_a]),
                stored_b=len(stored_keys[signal_b]),
                policy=similarity, alignment_mode="pairwise_complete",
                comparable_scale=_comparable(signal_a, signal_b))))
    if uni["alignment_policy"] == "pairwise_complete":
        warnings.append(
            "pairwise_complete rows use pair-specific overlaps with "
            "pair-specific sample counts; matrix-level diagnostics still "
            "use the strict intersection so no matrix mixes universes")

    strict_rows = [r for r in pairwise_rows
                   if r["alignment_mode"] == "strict_intersection"]

    # --- multiple testing over pairwise Spearman p-values ---------------
    mt_block = None
    if analysis["multiple_testing"]:
        entries = [{"candidate_id": f"{r['signal_a']}|{r['signal_b']}",
                    "raw_p": r.get("spearman_p"), "provenance": None}
                   for r in strict_rows]
        adjusted = mt_mod.adjust_p_values(
            entries, analysis["multiple_testing"]["alpha"])
        methods = analysis["multiple_testing"]["methods"]
        preferred = next((m for m in ("holm", "bh", "bonferroni")
                          if m in methods), None)
        by_id = {a["candidate_id"]: a for a in adjusted}
        for r in strict_rows:
            entry = by_id.get(f"{r['signal_a']}|{r['signal_b']}")
            if entry and preferred:
                r["spearman_p_adjusted"] = entry.get(preferred)
        mt_block = {
            "family": analysis["multiple_testing"]["family"],
            "alpha": analysis["multiple_testing"]["alpha"],
            "methods": methods,
            "preferred_method": preferred,
            "hypotheses": adjusted,
            "note": ("raw p-values stay next to adjusted values; adjusted "
                     "significance is never proof of independence or "
                     "predictability"),
        }

    # --- matrix, distance, diagnostics, clustering, redundancy ----------
    matrix = red_mod.correlation_matrix(strict_rows, signal_ids,
                                        method=similarity["matrix_method"])
    distance = red_mod.distance_matrix(matrix)
    diagnostics = red_mod.matrix_diagnostics(matrix)
    warnings.extend(diagnostics.get("warnings") or [])
    clustering = None
    if similarity["clustering"]:
        clustering = red_mod.cluster(distance, similarity["clustering"])
    redundancy = red_mod.redundancy_summary(
        strict_rows, [r["agreement"] for r in strict_rows],
        method=similarity["matrix_method"], signal_ids=signal_ids)

    # --- combination ----------------------------------------------------
    combined = combo_mod.combine(
        keys=grid["keys"], component_values=combination_inputs,
        policy=combination_policy, signal_ids=signal_ids)
    if combined["reconciliation"]["state"] == "failed":
        raise SignalEnsembleError(
            f"component contributions failed to reconcile on "
            f"{combined['reconciliation']['failures']} observation(s) "
            f"within tolerance "
            f"{combined['reconciliation']['tolerance']:g}")

    availability_violations = 0
    combined_rows: List[Dict[str, Any]] = []
    for observation in combined["observations"]:
        key = (observation["entity_id"], observation["timestamp"])
        if observation["state"] == "available":
            provenance = _combined_provenance(
                observation, signal_ids, grid)
            if provenance["available_at"] > key[1]:
                availability_violations += 1
            observation = dict(observation, **provenance)
        else:
            observation = dict(
                observation, available_at=None,
                availability_assumed=True,
                universe_membership_id=None)
        combined_rows.append(observation)
    if availability_violations:
        warnings.append(
            f"{availability_violations} combined observation(s) use a "
            f"component that was only available AFTER the observation "
            f"timestamp; the run is INVALID")

    # --- synthetic combined signal for Phase 60-style evaluation --------
    combination_observations = _synthetic_combination_rows(
        combined_rows, signal_ids=signal_ids, grid=grid, prefix="cmb")

    def _component_rows_for(signal_id: str) -> List[Dict[str, Any]]:
        out = []
        for i, key in enumerate(stored_keys[signal_id]):
            value = combination_inputs[signal_id].get(key)
            out.append({
                "observation_id": f"{signal_id}-{i:05d}",
                "entity_id": key[0], "source_timestamp": key[1],
                "generated_at": None,
                "available_at": grid["available_at"][signal_id][key],
                "availability_assumed":
                    grid["assumed"][signal_id].get(key, False),
                "raw_value": value,
                "universe_membership_id":
                    grid["membership_id"][signal_id].get(key), "metadata": {},
            })
        return out

    horizon_rows: List[Dict[str, Any]] = []
    turnover_summary = None
    holding = None
    cost_block = None
    combination_pairs_first: List[Dict[str, Any]] = []
    pair_violations = 0

    def _evaluate(rows: List[Dict[str, Any]], *, scope: str,
                  subject_id: Optional[str], horizon: int, lag: int,
                  bucket_count: int) -> Tuple[Dict[str, Any],
                                              List[Dict[str, Any]]]:
        built = sd_obs.build_pairs(
            rows, target_type="forward_return", prices=prices,
            supplied=None, horizon=horizon, entry_lag=lag,
            extreme_loss_policy=analysis["outcome"]["extreme_loss_policy"])
        pair_list = built["pairs"]
        overlap = built["overlap"]
        overlapping = overlap.get("overlap_ratio") not in (None, 0, 0.0)
        signal_values = [p["signal_value"] for p in pair_list]
        outcome_values = [p["outcome_value"] for p in pair_list]
        block = stats_mod.correlation_block(
            signal_values, outcome_values,
            methods=("pearson", "spearman"), minimum_observations=4,
            overlapping=overlapping)
        cs = stats_mod.cross_sectional_ic(pair_list, overlapping=overlapping)
        spread = None
        if len(pair_list) >= bucket_count:
            unique = len(set(signal_values))
            if unique >= bucket_count:
                assignments, _thresholds, _bounds = \
                    bucket_mod.assign_buckets(
                        pair_list, signal_values,
                        bucket_count=bucket_count,
                        scope=analysis["bucket"]["scope"])
                bucket_rows = bucket_mod.bucket_outcomes(
                    pair_list, assignments, bucket_count=bucket_count,
                    minimum_per_bucket=analysis["bucket"]
                    ["minimum_per_bucket"])
                spread = bucket_mod.top_minus_bottom(
                    bucket_rows, bucket_count=bucket_count)
            else:
                spread = {"state": "unavailable",
                          "reason": (f"only {unique} unique score(s) for "
                                     f"{bucket_count} buckets — assignment "
                                     f"would be arbitrary tie-splitting"),
                          "spread": None}
        pearson = block["pearson"]
        spearman = block["spearman"]
        row = {
            "scope": scope, "subject_id": subject_id,
            "horizon": horizon, "entry_lag": lag, "outcome_scope": "raw",
            "observations": len(pair_list),
            "pearson": pearson.get("statistic"),
            "spearman": spearman.get("statistic"),
            "spearman_p": spearman.get("p_value"),
            "spearman_p_adjusted": None,
            "mean_cross_sectional_ic":
                cs["aggregate"].get("mean_spearman_ic"),
            "top_minus_bottom": (spread or {}).get("spread"),
            "cost_adjusted_spread": None,
            "overlap_ratio": overlap.get("overlap_ratio"),
            "mean_one_way_turnover": None,
            "state": ("available" if spearman["state"] == "available"
                      else "unavailable"),
            "reason": spearman.get("reason"),
            "detail": {
                "correlations": block,
                "cross_sectional_aggregate": cs["aggregate"],
                "spread": spread,
                "overlap": overlap,
                "p_value_note": spearman.get("p_value_note"),
                "unavailable_pairs": len(built["unavailable"]),
            },
        }
        return row, pair_list, built["violations"]

    if analysis["horizons"] and prices is not None:
        first_horizon = analysis["horizons"][0]
        first_lag = analysis["entry_lags"][0]
        bucket_count = analysis["bucket"]["bucket_count"]
        for lag in analysis["entry_lags"]:
            for horizon in analysis["horizons"]:
                row, pair_list, violations = _evaluate(
                    combination_observations, scope="combination",
                    subject_id=None, horizon=horizon, lag=lag,
                    bucket_count=bucket_count)
                pair_violations += len(violations)
                horizon_rows.append(row)
                if horizon == first_horizon and lag == first_lag:
                    combination_pairs_first = pair_list
        for signal_id in signal_ids:
            row, _pairs, violations = _evaluate(
                _component_rows_for(signal_id), scope="component",
                subject_id=signal_id, horizon=first_horizon,
                lag=first_lag, bucket_count=bucket_count)
            pair_violations += len(violations)
            horizon_rows.append(row)
        if pair_violations:
            warnings.append(
                f"{pair_violations} timing violation(s): a signal value "
                f"was available only after its outcome began; the run is "
                f"INVALID")

        # turnover + costs on the combination reference
        if combination_pairs_first:
            unique_scores = len({p["signal_value"]
                                 for p in combination_pairs_first})
            if unique_scores >= bucket_count:
                assignments, _t, _b = bucket_mod.assign_buckets(
                    combination_pairs_first,
                    [p["signal_value"] for p in combination_pairs_first],
                    bucket_count=bucket_count,
                    scope="per_timestamp")
                timeline = turnover_mod.membership_timeline(
                    combination_pairs_first, assignments,
                    bucket_count=bucket_count,
                    initial_policy=analysis["turnover"]["initial_policy"])
                turnover_summary = timeline["summary"]
                holding = turnover_mod.holding_overlap(
                    turnover_summary["rebalance_count"], first_horizon,
                    cohort_normalisation=analysis["turnover"]
                    ["cohort_normalisation"])
                if holding.get("warning"):
                    warnings.append(holding["warning"])
                for row in horizon_rows:
                    if row["scope"] == "combination" \
                            and row["horizon"] == first_horizon \
                            and row["entry_lag"] == first_lag:
                        row["mean_one_way_turnover"] = \
                            turnover_summary["mean_one_way_turnover"]
                cost_identity = links.get("cost_identity")
                if cost_identity is not None:
                    model = cost_store.get_cost_model(
                        run["cost_diagnostic_run_id"])
                    cost_block = cost_mod.cost_estimate(
                        model, turnover_rows=timeline["rows"],
                        reference_notional=analysis["reference_notional"])
                    if cost_block["completeness"] != "complete":
                        parts = []
                        if cost_block["unavailable_components"]:
                            parts.append(
                                f"component(s) "
                                f"{cost_block['unavailable_components']} "
                                f"are unavailable")
                        if cost_block["skipped_rebalances"]:
                            parts.append(
                                f"{cost_block['skipped_rebalances']} "
                                f"rebalance(s) have no turnover "
                                f"(no prior book)")
                        warnings.append(
                            f"cost completeness is "
                            f"{cost_block['completeness']}: "
                            f"{'; '.join(parts)} — missing cost inputs "
                            f"stay unavailable, never zero")
                    mean_cost_return = None
                    if cost_block["total_cost_return"] is not None \
                            and cost_block["costed_rebalances"]:
                        mean_cost_return = (
                            cost_block["total_cost_return"]
                            / cost_block["costed_rebalances"])
                    for row in horizon_rows:
                        if row["scope"] == "combination" \
                                and row["top_minus_bottom"] is not None \
                                and mean_cost_return is not None:
                            row["cost_adjusted_spread"] = float(
                                row["top_minus_bottom"] - mean_cost_return)

    # --- per-component turnover means (summary context) -----------------
    component_turnover: Dict[str, Optional[float]] = {}
    if analysis["horizons"] and prices is not None:
        bucket_count = analysis["bucket"]["bucket_count"]
        for signal_id in signal_ids:
            rows = _component_rows_for(signal_id)
            built = sd_obs.build_pairs(
                rows, target_type="forward_return", prices=prices,
                supplied=None, horizon=analysis["horizons"][0],
                entry_lag=analysis["entry_lags"][0],
                extreme_loss_policy=analysis["outcome"]
                ["extreme_loss_policy"])
            pair_list = built["pairs"]
            unique_scores = len({p["signal_value"] for p in pair_list})
            if len(pair_list) >= bucket_count \
                    and unique_scores >= bucket_count:
                assignments, _t, _b = bucket_mod.assign_buckets(
                    pair_list, [p["signal_value"] for p in pair_list],
                    bucket_count=bucket_count, scope="per_timestamp")
                timeline = turnover_mod.membership_timeline(
                    pair_list, assignments, bucket_count=bucket_count,
                    initial_policy=analysis["turnover"]["initial_policy"])
                component_turnover[signal_id] = \
                    timeline["summary"]["mean_one_way_turnover"]
                for row in horizon_rows:
                    if row["scope"] == "component" \
                            and row["subject_id"] == signal_id:
                        row["mean_one_way_turnover"] = \
                            component_turnover[signal_id]
            else:
                component_turnover[signal_id] = None

    # --- leave-one-signal-out -------------------------------------------
    loo_rows: List[Dict[str, Any]] = []
    if analysis["leave_one_out"] and len(signal_ids) >= 3:
        loo_rows = _leave_one_out(
            signal_ids=signal_ids, grid=grid,
            combination_inputs=combination_inputs,
            similarity_values=normalised,
            configuration=configuration,
            similarity=similarity, analysis=analysis, prices=prices,
            full_metrics={
                "coverage": combined["coverage"],
                "mean_absolute_correlation":
                    redundancy["mean_absolute_correlation"],
                "effective_signal_count":
                    diagnostics.get("effective_signal_count"),
                "first_horizon_spearman": next(
                    (r["spearman"] for r in horizon_rows
                     if r["scope"] == "combination"), None),
                "first_horizon_spread": next(
                    (r["top_minus_bottom"] for r in horizon_rows
                     if r["scope"] == "combination"), None),
                "mean_one_way_turnover":
                    (turnover_summary or {}).get("mean_one_way_turnover"),
            })

    # --- regimes ---------------------------------------------------------
    regime_rows = _regime_rows(
        run, links, strict_keys=matrix_keys, normalised=normalised,
        signal_ids=signal_ids, similarity=similarity,
        combination_pairs=combination_pairs_first, warnings=warnings)

    # --- validation split ------------------------------------------------
    held_out = _held_out_block(
        run, links, combination_pairs=combination_pairs_first,
        combination_observations=combination_observations,
        strict_keys=matrix_keys, normalised=normalised,
        similarity=similarity, analysis=analysis, warnings=warnings)

    # --- factor residual outcomes ---------------------------------------
    factor_block, factor_rows = _factor_residuals(
        run, links, combination_pairs=combination_pairs_first,
        analysis=analysis, warnings=warnings)
    horizon_rows.extend(factor_rows)

    # --- bootstrap -------------------------------------------------------
    bootstrap_rows: List[Dict[str, Any]] = []
    if analysis["bootstrap"]:
        bootstrap_rows = _run_bootstrap(
            analysis["bootstrap"], strict_keys=matrix_keys,
            normalised=normalised, signal_ids=signal_ids,
            similarity=similarity,
            combination_pairs=combination_pairs_first)

    # --- sensitivity -----------------------------------------------------
    sensitivity_rows: List[Dict[str, Any]] = []
    if analysis["sensitivity"]:
        sensitivity_rows = _sensitivity(
            configuration, uni, analysis, similarity,
            base_metrics={
                "coverage": combined["coverage"],
                "component_count": len(signal_ids),
                "mean_absolute_correlation":
                    redundancy["mean_absolute_correlation"],
                "effective_signal_count":
                    diagnostics.get("effective_signal_count"),
                "first_horizon_spearman": next(
                    (r["spearman"] for r in horizon_rows
                     if r["scope"] == "combination"), None),
                "first_horizon_spread": next(
                    (r["top_minus_bottom"] for r in horizon_rows
                     if r["scope"] == "combination"), None),
                "mean_one_way_turnover":
                    (turnover_summary or {}).get("mean_one_way_turnover"),
                "cost_completeness": (cost_block or {}).get("completeness"),
            },
            prices=prices, links=links, run=run)

    # --- integrity + completeness ---------------------------------------
    integrity = _classify_integrity(
        uni=uni, normalisation=normalisation, analysis=analysis,
        violations=availability_violations + pair_violations,
        validation_evaluated=(
            held_out is not None and held_out.get("leakage_clean") is True))
    completeness = _classify_completeness(
        combined=combined, matrix=matrix, cost_block=cost_block)

    # --- contribution persistence sample --------------------------------
    contributions = combined["contributions"]
    contribution_sample = sorted(
        contributions,
        key=lambda c: (c["timestamp"], c["entity_id"], c["signal_id"]))
    stored_contributions = contribution_sample[:CONTRIBUTION_ROW_LIMIT]
    raw_by_key = grid["values"]
    for entry in stored_contributions:
        key = (entry["entity_id"], entry["timestamp"])
        entry["raw_value"] = raw_by_key[entry["signal_id"]].get(key)
        entry["oriented_value"] = oriented[entry["signal_id"]].get(key)
    if len(contributions) > CONTRIBUTION_ROW_LIMIT:
        warnings.append(
            f"component-contribution rows are stored for the first "
            f"{CONTRIBUTION_ROW_LIMIT} of {len(contributions)} "
            f"observations (deterministic timestamp/entity/signal order); "
            f"reconciliation was verified over ALL observations before "
            f"sampling")

    # --- fingerprints + persistence --------------------------------------
    results_blob = {
        "missingness": missingness,
        "normalisation_reasons": normalisation_reasons,
        "matrix": matrix, "distance": distance,
        "matrix_diagnostics": diagnostics,
        "clustering": clustering,
        "redundancy": redundancy,
        "reconciliation": combined["reconciliation"],
        "combination_coverage": combined["coverage"],
        "turnover_summary": turnover_summary,
        "holding_overlap": holding,
        "cost": cost_block,
        "component_turnover": component_turnover,
        "multiple_testing": mt_block,
        "held_out": held_out,
        "factor_residual": factor_block,
        "contribution_rows_total": len(contributions),
        "contribution_rows_stored": len(stored_contributions),
        "warnings": warnings,
    }
    result_fp = fp_mod.result_fingerprint(
        aligned_keys=[list(k) for k in matrix_keys],
        pairwise_rows=pairwise_rows,
        distance=distance, clustering=clustering,
        matrix_diagnostics=diagnostics, redundancy=redundancy,
        combined_observations=[{k: v for k, v in o.items()}
                               for o in combined_rows],
        component_rows=stored_contributions,
        horizon_rows=[{k: v for k, v in r.items() if k != "detail"}
                      for r in horizon_rows],
        leave_one_out=loo_rows, turnover=turnover_summary,
        cost=cost_block, regimes=regime_rows, held_out=held_out,
        bootstrap_rows=bootstrap_rows, sensitivity_rows=sensitivity_rows,
        warnings=warnings, integrity_status=integrity,
        completeness_status=completeness)

    definition_fps = {
        signal_id: signal_definition_fingerprint(
            uni["definitions"][signal_id], links.get("dataset_identity"))
        for signal_id in signal_ids}
    definition_rows = [{
        "signal_id": signal_id,
        "name": uni["definitions"][signal_id]["name"],
        "definition": uni["definitions"][signal_id],
        "definition_fingerprint": definition_fps[signal_id],
        "orientation": orientations[signal_id],
        "normalisation": normalisation[signal_id],
        "stored_observations": len(stored_keys[signal_id]),
        "coverage": next(
            (s["coverage"] for s in missingness["per_signal"]
             if s["signal_id"] == signal_id), None),
    } for signal_id in signal_ids]

    store.replace_children(
        run_id,
        definitions=definition_rows,
        pairwise=pairwise_rows,
        observations=combined_rows,
        components=stored_contributions,
        horizons=horizon_rows,
        leave_one_out=loo_rows,
        regimes=regime_rows,
        bootstrap=bootstrap_rows,
        sensitivity=sensitivity_rows)

    completed = store._now()
    store.update_run(run_id, {
        "status": "completed",
        "combined_available_count": combined["available_count"],
        "mean_absolute_correlation":
            _finite_or_none(redundancy["mean_absolute_correlation"]),
        "effective_signal_count":
            _finite_or_none(diagnostics.get("effective_signal_count")),
        "integrity_status": integrity,
        "completeness_status": completeness,
        "results": results_blob,
        "result_fingerprint": result_fp,
        "completed_at": completed,
        "error_message": None,
    })

    if create_experiment and not run.get("experiment_id"):
        record = experiment_integration.record_experiment(
            name=f"Signal ensemble: {run['name']}",
            module="signal_ensemble_diagnostics",
            experiment_type="diagnostic",
            description=(
                "Descriptive multi-signal redundancy and explicit "
                "combination diagnostics. No signal selection, no derived "
                "weights, no independence or diversification claim, and "
                "nothing here recommends or certifies an ensemble."),
            parameters={
                "signal_ids": signal_ids,
                "combination_mode": run["combination_mode"],
                "alignment_policy": run["alignment_policy"],
                "signal_count": run["signal_count"],
                "observation_count": run["observation_count"],
                "configuration_fingerprint":
                    run["configuration_fingerprint"],
            },
            metrics={
                "mean_absolute_correlation": _finite_or_none(
                    redundancy["mean_absolute_correlation"]),
                "effective_signal_count": _finite_or_none(
                    diagnostics.get("effective_signal_count")),
                "combination_coverage": _finite_or_none(
                    combined["coverage"]),
                "mean_one_way_turnover": _finite_or_none(
                    (turnover_summary or {}).get("mean_one_way_turnover")),
                "integrity_status": integrity,
                "cost_completeness": (cost_block or {}).get("completeness"),
                "result_fingerprint": result_fp,
            },
            tags=["signal-ensemble", run["combination_mode"],
                  run["alignment_policy"]],
            dataset_name=dataset_identity.get("dataset_name"),
            dataset_version=dataset_identity.get("version_label"),
            dataset_fingerprint=dataset_identity.get("manifest_fingerprint"),
            dataset_identity=dataset_identity or None,
        )
        if record:
            store.update_run(run_id, {"experiment_id": record["id"]})

    return get_run(run_id)


# ---------------------------------------------------------------------------
# Execution helpers
# ---------------------------------------------------------------------------

def _classify_integrity(*, uni: Dict[str, Any],
                        normalisation: Dict[str, Dict[str, Any]],
                        analysis: Dict[str, Any], violations: int,
                        validation_evaluated: bool) -> str:
    if violations > 0:
        return "invalid"
    if any(uni["definitions"][s]["transformation"] == "rank_full_sample"
           for s in uni["signal_ids"]):
        return "full_sample_descriptive"
    policies = {uni["definitions"][s]["availability_policy"]
                for s in uni["signal_ids"]}
    if policies == {"explicit_available_at"}:
        if validation_evaluated:
            return "verified_from_validation_split"
        return "verified_point_in_time"
    # at least one same_timestamp component: values are only ASSUMED
    # knowable at their own stamp
    lags = analysis.get("entry_lags") or []
    if analysis.get("horizons") and lags and min(lags) >= 1:
        return "verified_trailing_transformation"
    return "contemporaneous_descriptive"


def _classify_completeness(*, combined: Dict[str, Any],
                           matrix: Dict[str, Any],
                           cost_block: Optional[Dict[str, Any]]) -> str:
    coverage = combined["coverage"]
    if coverage is None or combined["available_count"] == 0:
        return "unavailable"
    complete = (coverage >= 1.0 and matrix["complete"]
                and (cost_block is None
                     or cost_block.get("completeness") == "complete"))
    return "complete" if complete else "partial"


def _leave_one_out(*, signal_ids: List[str], grid: Dict[str, Any],
                   combination_inputs: Dict[str, Dict[Key, Optional[float]]],
                   similarity_values: Dict[str, Dict[Key, Optional[float]]],
                   configuration: Dict[str, Any],
                   similarity: Dict[str, Any], analysis: Dict[str, Any],
                   prices: Optional[Dict[Tuple[str, str], float]],
                   full_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for omitted in signal_ids:
        remaining = [s for s in signal_ids if s != omitted]
        raw_combo = dict(configuration.get("combination")
                         or {"mode": "equal_weight"})
        if raw_combo.get("weights"):
            raw_combo["weights"] = {k: v for k, v
                                    in raw_combo["weights"].items()
                                    if k != omitted}
        if raw_combo.get("minimum_component_count"):
            raw_combo["minimum_component_count"] = min(
                raw_combo["minimum_component_count"], len(remaining))
        entry: Dict[str, Any] = {
            "omitted_signal_id": omitted,
            "metrics": {}, "state": "unavailable", "reason": None,
        }
        try:
            policy = combo_mod.validate_combination_policy(
                raw_combo, remaining)
        except combo_mod.CombinationError as exc:
            entry["reason"] = (f"the configured policy cannot be applied "
                               f"to the remaining signals: {exc}")
            rows.append(entry)
            continue
        combined = combo_mod.combine(
            keys=grid["keys"], component_values=combination_inputs,
            policy=policy, signal_ids=remaining)
        remaining_raw_keys = align_mod.strict_intersection(grid, remaining)
        remaining_keys = _common_value_keys(
            remaining_raw_keys, similarity_values, remaining)
        subset = _matrix_rows(
            remaining, remaining_keys, similarity_values,
            method=similarity["matrix_method"],
            minimum=similarity["minimum_pair_overlap"])
        absolutes = [
            abs(row["correlations"][similarity["matrix_method"]]["statistic"])
            for row in subset
            if row["correlations"][similarity["matrix_method"]]["state"]
            == "available"]
        mean_abs = (float(np.mean(absolutes)) if absolutes else None)
        reduced_matrix = red_mod.correlation_matrix(
            subset, remaining, method=similarity["matrix_method"])
        effective = red_mod.matrix_diagnostics(
            reduced_matrix).get("effective_signal_count")
        spearman = spread = turnover_mean = None
        if analysis["horizons"] and prices is not None:
            synthetic = _synthetic_combination_rows(
                combined["observations"], signal_ids=remaining, grid=grid,
                prefix=f"loo-{omitted}")
            if synthetic:
                built = sd_obs.build_pairs(
                    synthetic, target_type="forward_return",
                    prices=prices, supplied=None,
                    horizon=analysis["horizons"][0],
                    entry_lag=analysis["entry_lags"][0],
                    extreme_loss_policy=analysis["outcome"]
                    ["extreme_loss_policy"])
                pair_list = built["pairs"]
                signal_values = [p["signal_value"] for p in pair_list]
                outcome_values = [p["outcome_value"] for p in pair_list]
                block = stats_mod.correlation_block(
                    signal_values, outcome_values, methods=("spearman",),
                    minimum_observations=4,
                    overlapping=bool(built["overlap"]
                                     .get("overlap_ratio")))
                spearman = block["spearman"].get("statistic")
                bucket_count = analysis["bucket"]["bucket_count"]
                if len(pair_list) >= bucket_count \
                        and len(set(signal_values)) >= bucket_count:
                    assignments, _t, _b = bucket_mod.assign_buckets(
                        pair_list, signal_values,
                        bucket_count=bucket_count, scope="per_timestamp")
                    bucket_rows = bucket_mod.bucket_outcomes(
                        pair_list, assignments,
                        bucket_count=bucket_count,
                        minimum_per_bucket=analysis["bucket"]
                        ["minimum_per_bucket"])
                    spread = bucket_mod.top_minus_bottom(
                        bucket_rows,
                        bucket_count=bucket_count).get("spread")
                    timeline = turnover_mod.membership_timeline(
                        pair_list, assignments,
                        bucket_count=bucket_count,
                        initial_policy=analysis["turnover"]
                        ["initial_policy"])
                    turnover_mean = timeline["summary"][
                        "mean_one_way_turnover"]

        def _delta(now: Optional[float],
                   before: Optional[float]) -> Optional[float]:
            if now is None or before is None:
                return None
            return float(now - before)

        entry["metrics"] = {
            "coverage": combined["coverage"],
            "similarity_observations": len(remaining_keys),
            "coverage_delta": _delta(combined["coverage"],
                                     full_metrics["coverage"]),
            "mean_absolute_correlation": mean_abs,
            "mean_absolute_correlation_delta": _delta(
                mean_abs, full_metrics["mean_absolute_correlation"]),
            "effective_signal_count": effective,
            "effective_signal_count_delta": _delta(
                effective, full_metrics["effective_signal_count"]),
            "first_horizon_spearman": spearman,
            "first_horizon_spearman_delta": _delta(
                spearman, full_metrics["first_horizon_spearman"]),
            "first_horizon_spread": spread,
            "first_horizon_spread_delta": _delta(
                spread, full_metrics["first_horizon_spread"]),
            "mean_one_way_turnover": turnover_mean,
            "mean_one_way_turnover_delta": _delta(
                turnover_mean, full_metrics["mean_one_way_turnover"]),
            "note": ("descriptive differences under the configured "
                     "omission policy; never an exclusion recommendation "
                     "and never a 'harmful signal' label"),
        }
        entry["state"] = "available"
        rows.append(entry)
    return rows


def _regime_rows(run, links, *, strict_keys: List[Key],
                 normalised: Dict[str, Dict[Key, Optional[float]]],
                 signal_ids: List[str], similarity: Dict[str, Any],
                 combination_pairs: List[Dict[str, Any]],
                 warnings: List[str]) -> List[Dict[str, Any]]:
    identity = links.get("regime_identity")
    if not identity:
        return []
    rrun = regime_store.get_run(run["regime_run_id"])
    definition = next(
        (d for d in regime_store.list_definitions(rrun["id"])
         if d["definition_id"] == identity["regime_definition_id"]), None)
    if definition is None:
        warnings.append("the linked regime definition is unavailable")
        return []
    label_by_stamp = dict(zip(rrun["timestamps"],
                              definition["assignments"]))
    keys_by_label: Dict[str, List[Key]] = {}
    for key in strict_keys:
        label = label_by_stamp.get(key[1])
        keys_by_label.setdefault(
            str(label) if label is not None else "unassigned",
            []).append(key)
    pairs_by_label: Dict[str, List[Dict[str, Any]]] = {}
    for pair in combination_pairs:
        label = label_by_stamp.get(pair["signal_timestamp"])
        pairs_by_label.setdefault(
            str(label) if label is not None else "unassigned",
            []).append(pair)

    rows: List[Dict[str, Any]] = []
    rare_seen = False
    ordered_pairs = pair_mod.pair_order(signal_ids)
    for label in sorted(set(keys_by_label) | set(pairs_by_label)):
        keys = keys_by_label.get(label, [])
        entry: Dict[str, Any] = {
            "regime_label": label, "observations": len(keys),
            "rare": len(keys) < RARE_REGIME_MIN_OBSERVATIONS,
            "mean_absolute_correlation": None,
            "effective_signal_count": None,
            "combined_spearman": None, "top_minus_bottom": None,
            "coverage": (len(keys) / len(strict_keys)
                         if strict_keys else None),
            "state": "unavailable", "reason": None, "detail": None,
        }
        if entry["rare"]:
            rare_seen = True
            entry["state"] = "rare"
            entry["reason"] = (
                f"only {len(keys)} strict-intersection observation(s) in "
                f"this regime (below {RARE_REGIME_MIN_OBSERVATIONS}); "
                f"statistics are withheld")
            rows.append(entry)
            continue
        regime_rows_pairwise: List[Dict[str, Any]] = []
        for signal_a, signal_b in ordered_pairs:
            xs = [normalised[signal_a][k] for k in keys
                  if normalised[signal_a].get(k) is not None
                  and normalised[signal_b].get(k) is not None]
            ys = [normalised[signal_b][k] for k in keys
                  if normalised[signal_a].get(k) is not None
                  and normalised[signal_b].get(k) is not None]
            correlation = stats_mod.correlation(
                xs, ys, method=similarity["matrix_method"],
                minimum_observations=similarity["minimum_pair_overlap"],
                overlapping=False)
            regime_rows_pairwise.append({
                "signal_a": signal_a, "signal_b": signal_b,
                "correlations": {similarity["matrix_method"]: correlation},
            })
        matrix = red_mod.correlation_matrix(
            regime_rows_pairwise, signal_ids,
            method=similarity["matrix_method"])
        diagnostics = red_mod.matrix_diagnostics(matrix)
        absolutes = [abs(c["correlations"][similarity["matrix_method"]]
                         ["statistic"])
                     for c in regime_rows_pairwise
                     if c["correlations"][similarity["matrix_method"]]
                     ["state"] == "available"]
        entry["mean_absolute_correlation"] = (
            float(np.mean(absolutes)) if absolutes else None)
        entry["effective_signal_count"] = \
            diagnostics.get("effective_signal_count")
        subset = pairs_by_label.get(label, [])
        if subset:
            block = stats_mod.correlation_block(
                [p["signal_value"] for p in subset],
                [p["outcome_value"] for p in subset],
                methods=("spearman",), minimum_observations=4,
                overlapping=False)
            entry["combined_spearman"] = \
                block["spearman"].get("statistic")
        entry["state"] = "available"
        entry["detail"] = {"matrix_state": diagnostics["state"],
                           "matrix_reason": diagnostics.get("reason")}
        rows.append(entry)
    if rare_seen:
        warnings.append(
            f"one or more regimes hold fewer than "
            f"{RARE_REGIME_MIN_OBSERVATIONS} strict-intersection "
            f"observations; their statistics are withheld, and regime "
            f"differences are measurements — never permanent properties")
    return rows


def _validation_membership(
        run: Dict[str, Any], identity: Dict[str, Any],
        observations: Sequence[Dict[str, Any]]) -> Dict[str, Set[Key]]:
    """Resolve stored split membership by explicit id or unique timestamp."""
    vrun = validation_store.get_run(run["validation_run_id"])
    splits = validation_store.list_splits(run["validation_run_id"])
    split = next((item for item in splits
                  if item["split_label"] == identity["split_label"]), None)
    if vrun is None or split is None:
        raise ConflictError("the linked validation split is unavailable")
    _assert_pinned("validation split", split, identity,
                   {"split_fingerprint": "split_fingerprint"})

    samples_by_id = {sample["sample_id"]: sample
                     for sample in vrun["samples"]}
    ids_by_time: Dict[str, List[str]] = {}
    for sample_id, sample in samples_by_id.items():
        ids_by_time.setdefault(
            sample.get("prediction_time"), []).append(sample_id)
    member_ids = {
        "train": set(split["train_ids"]),
        "test": set(split["test_ids"]),
        "purged": set(split["purged_ids"]),
        "embargoed": set(split["embargoed_ids"]),
    }
    resolved: Dict[str, Set[Key]] = {
        label: set() for label in member_ids}
    for observation in observations:
        if observation.get("raw_value") is None:
            continue
        source = observation["source_timestamp"]
        sample_id = observation.get("universe_membership_id")
        if sample_id is not None:
            sample = samples_by_id.get(sample_id)
            if sample is None:
                raise ConflictError(
                    f"combined observation references unknown validation "
                    f"sample {sample_id!r}")
            if sample.get("prediction_time") != source:
                raise ConflictError(
                    f"validation sample {sample_id!r} has prediction_time "
                    f"{sample.get('prediction_time')!r}, not signal "
                    f"timestamp {source!r}")
        else:
            candidates = ids_by_time.get(source, [])
            if len(candidates) > 1:
                raise ConflictError(
                    f"validation membership is ambiguous at {source}; "
                    f"supply one consistent universe_membership_id on "
                    f"each component observation")
            sample_id = candidates[0] if candidates else None
        if sample_id is None:
            continue
        key = (observation["entity_id"], source)
        for label, ids in member_ids.items():
            if sample_id in ids:
                resolved[label].add(key)
    return resolved


def _held_out_block(run, links, *, combination_pairs: List[Dict[str, Any]],
                    combination_observations: List[Dict[str, Any]],
                    strict_keys: List[Key],
                    normalised: Dict[str, Dict[Key, Optional[float]]],
                    similarity: Dict[str, Any], analysis: Dict[str, Any],
                    warnings: List[str]) -> Optional[Dict[str, Any]]:
    identity = links.get("validation_identity")
    if not identity:
        return None
    memberships = _validation_membership(
        run, identity, combination_observations)

    def _stats(pairs: List[Dict[str, Any]]) -> Dict[str, Any]:
        block = stats_mod.correlation_block(
            [p["signal_value"] for p in pairs],
            [p["outcome_value"] for p in pairs],
            methods=("spearman",), minimum_observations=4,
            overlapping=False)
        return {"observations": len(pairs),
                "spearman": block["spearman"].get("statistic"),
                "reason": block["spearman"].get("reason")}

    def _pair_key(pair: Dict[str, Any]) -> Key:
        return pair["entity_id"], pair["signal_timestamp"]

    train_pairs = [p for p in combination_pairs
                   if _pair_key(p) in memberships["train"]]
    test_pairs = [p for p in combination_pairs
                  if _pair_key(p) in memberships["test"]]
    purged = sum(1 for p in combination_pairs
                 if _pair_key(p) in memberships["purged"])
    embargoed = sum(1 for p in combination_pairs
                    if _pair_key(p) in memberships["embargoed"])

    def _redundancy_over(bucket: str) -> Optional[float]:
        keys = [key for key in strict_keys
                if key in memberships[bucket]]
        if len(keys) < similarity["minimum_pair_overlap"]:
            return None
        rows = _matrix_rows(
            sorted(normalised), keys, normalised,
            method=similarity["matrix_method"],
            minimum=similarity["minimum_pair_overlap"])
        absolutes = [
            abs(row["correlations"][similarity["matrix_method"]]["statistic"])
            for row in rows
            if row["correlations"][similarity["matrix_method"]]["state"]
            == "available"]
        return float(np.mean(absolutes)) if absolutes else None

    leakage_clean = identity.get("leakage_clean")
    if leakage_clean is False:
        warnings.append(
            "the linked validation run reports leakage; held-out figures "
            "are descriptive and the verified claim is withheld")
    return {
        "split_label": identity["split_label"],
        "leakage_clean": leakage_clean,
        "training_observations": len(train_pairs),
        "held_out_observations": len(test_pairs),
        "purged_observations": purged,
        "embargoed_observations": embargoed,
        "training": _stats(train_pairs),
        "held_out": _stats(test_pairs),
        "full_sample": _stats(combination_pairs),
        "training_mean_absolute_correlation": _redundancy_over("train"),
        "note": ("supplied weights stay fixed; per-timestamp and trailing "
                 "transformations fit no persistent parameter, so nothing "
                 "is refitted on held-out data; purge and embargo "
                 "membership is used exactly as stored"),
    }


def _factor_residuals(run, links, *,
                      combination_pairs: List[Dict[str, Any]],
                      analysis: Dict[str, Any],
                      warnings: List[str]
                      ) -> Tuple[Optional[Dict[str, Any]],
                                 List[Dict[str, Any]]]:
    identity = links.get("factor_identity")
    if not identity:
        return None, []
    periods = factor_store.list_periods(run["factor_run_id"])
    residual_by_start = {p["period_start"]: p.get("residual")
                         for p in periods}
    ordered_starts = sorted(residual_by_start)
    matched: List[Dict[str, Any]] = []
    unmatched = 0
    horizon = analysis["horizons"][0] if analysis["horizons"] else None
    for pair in combination_pairs:
        starts = [s for s in ordered_starts
                  if pair["entry_timestamp"] <= s < pair["exit_timestamp"]]
        values = [residual_by_start[s] for s in starts]
        if horizon is None or len(starts) != horizon \
                or any(v is None for v in values):
            unmatched += 1
            continue
        matched.append(dict(pair, outcome_value=float(sum(values))))
    block = {
        "factor_run_name": identity.get("factor_run_name"),
        "result_fingerprint": identity.get("result_fingerprint"),
        "matched_pairs": len(matched), "unmatched_pairs": unmatched,
        "signal_value_residualisation": {
            "state": "deferred",
            "reason": ("no stored factor-residualised SIGNAL series exists "
                       "in this repository and automatic residualisation "
                       "is prohibited; only combined-score OUTCOMES are "
                       "compared against stored residuals"),
        },
        "convention": ("the residual outcome of a holding is the "
                       "ARITHMETIC SUM of the linked factor run's stored "
                       "per-period residuals whose period_start falls in "
                       "[entry, exit), required to cover exactly the "
                       "horizon; raw and residual scopes are separate "
                       "rows, a residual association is not called alpha, "
                       "and nothing is neutralised automatically"),
    }
    rows: List[Dict[str, Any]] = []
    if matched:
        stats_block = stats_mod.correlation_block(
            [p["signal_value"] for p in matched],
            [p["outcome_value"] for p in matched],
            methods=("pearson", "spearman"), minimum_observations=4,
            overlapping=False)
        spearman = stats_block["spearman"]
        rows.append({
            "scope": "combination", "subject_id": None,
            "horizon": horizon, "entry_lag": analysis["entry_lags"][0],
            "outcome_scope": "factor_residual",
            "observations": len(matched),
            "pearson": stats_block["pearson"].get("statistic"),
            "spearman": spearman.get("statistic"),
            "spearman_p": spearman.get("p_value"),
            "spearman_p_adjusted": None,
            "mean_cross_sectional_ic": None,
            "top_minus_bottom": None, "cost_adjusted_spread": None,
            "overlap_ratio": None, "mean_one_way_turnover": None,
            "state": ("available" if spearman["state"] == "available"
                      else "unavailable"),
            "reason": spearman.get("reason"),
            "detail": {"correlations": stats_block},
        })
    elif unmatched:
        warnings.append(
            f"{unmatched} combined pair(s) could not be matched to stored "
            f"factor residual periods with exact horizon coverage; "
            f"residual-outcome diagnostics are unavailable for them")
    return block, rows


def _run_bootstrap(config: Dict[str, Any], *, strict_keys: List[Key],
                   normalised: Dict[str, Dict[Key, Optional[float]]],
                   signal_ids: List[str], similarity: Dict[str, Any],
                   combination_pairs: List[Dict[str, Any]]
                   ) -> List[Dict[str, Any]]:
    stamps = sorted({k[1] for k in strict_keys})
    if not stamps:
        return [{
            "statistic": statistic, "method": config["method"],
            "seed": config["seed"], "resamples": config["resamples"],
            "block_length": config.get("block_length"),
            "quantiles": None,
            "unavailable_resamples": config["resamples"],
            "state": "unavailable",
            "reason": "no common post-normalisation timestamps to resample",
        } for statistic in config["statistics"]]
    keys_by_stamp: Dict[str, List[Key]] = {}
    for key in strict_keys:
        keys_by_stamp.setdefault(key[1], []).append(key)
    pairs_by_stamp: Dict[str, List[Dict[str, Any]]] = {}
    for pair in combination_pairs:
        pairs_by_stamp.setdefault(pair["signal_timestamp"],
                                  []).append(pair)
    rng = np.random.default_rng(config["seed"])
    ordered_pairs = pair_mod.pair_order(signal_ids)
    method = similarity["matrix_method"]
    rows: List[Dict[str, Any]] = []
    for statistic in config["statistics"]:
        samples: List[float] = []
        unavailable = 0
        for _ in range(config["resamples"]):
            if config["method"] == "timestamp":
                chosen = [stamps[i] for i in
                          rng.integers(0, len(stamps), len(stamps))]
            else:  # moving_block over chronologically ordered stamps
                block_length = min(config["block_length"], len(stamps))
                blocks_needed = math.ceil(len(stamps) / block_length)
                chosen = []
                starts = rng.integers(
                    0, max(1, len(stamps) - block_length + 1),
                    blocks_needed)
                for start in starts:
                    chosen.extend(
                        stamps[int(start):int(start) + block_length])
                chosen = chosen[:len(stamps)]
            value = _bootstrap_statistic(
                statistic, chosen, keys_by_stamp=keys_by_stamp,
                pairs_by_stamp=pairs_by_stamp, normalised=normalised,
                signal_ids=signal_ids, ordered_pairs=ordered_pairs,
                method=method,
                minimum=similarity["minimum_pair_overlap"])
            if value is None:
                unavailable += 1
            else:
                samples.append(value)
        entry: Dict[str, Any] = {
            "statistic": statistic, "method": config["method"],
            "seed": config["seed"], "resamples": config["resamples"],
            "block_length": config.get("block_length"),
            "quantiles": None, "unavailable_resamples": unavailable,
            "state": "unavailable", "reason": None,
        }
        if len(samples) < max(10, config["resamples"] // 10):
            entry["reason"] = (
                f"only {len(samples)} of {config['resamples']} resamples "
                f"produced the statistic; quantiles are withheld")
        else:
            array = np.asarray(samples, dtype=np.float64)
            entry["quantiles"] = {
                "q025": float(np.quantile(array, 0.025)),
                "q500": float(np.quantile(array, 0.5)),
                "q975": float(np.quantile(array, 0.975)),
                "note": ("resampling quantiles over whole timestamp "
                         "cross-sections — descriptive stability only, "
                         "not a p-value and not scientific validation"),
            }
            entry["state"] = "available"
        rows.append(entry)
    return rows


def _bootstrap_statistic(statistic: str, chosen_stamps: List[str], *,
                         keys_by_stamp: Dict[str, List[Key]],
                         pairs_by_stamp: Dict[str, List[Dict[str, Any]]],
                         normalised: Dict[str, Dict[Key, Optional[float]]],
                         signal_ids: List[str],
                         ordered_pairs: List[Tuple[str, str]],
                         method: str, minimum: int) -> Optional[float]:
    if statistic == "combination_spearman":
        pooled = [p for stamp in chosen_stamps
                  for p in pairs_by_stamp.get(stamp, [])]
        if len(pooled) < minimum:
            return None
        block = stats_mod.correlation_block(
            [p["signal_value"] for p in pooled],
            [p["outcome_value"] for p in pooled],
            methods=("spearman",), minimum_observations=minimum,
            overlapping=True)
        return block["spearman"].get("statistic")
    keys = [k for stamp in chosen_stamps
            for k in keys_by_stamp.get(stamp, [])]
    if len(keys) < minimum:
        return None
    resampled_rows: List[Dict[str, Any]] = []
    for signal_a, signal_b in ordered_pairs:
        xs = [normalised[signal_a][k] for k in keys]
        ys = [normalised[signal_b][k] for k in keys]
        correlation = stats_mod.correlation(
            xs, ys, method=method, minimum_observations=minimum,
            overlapping=False)
        resampled_rows.append({
            "signal_a": signal_a, "signal_b": signal_b,
            "correlations": {method: correlation}})
    if statistic == "mean_absolute_correlation":
        absolutes = [abs(r["correlations"][method]["statistic"])
                     for r in resampled_rows
                     if r["correlations"][method]["state"] == "available"]
        return float(np.mean(absolutes)) if absolutes else None
    # effective_signal_count
    matrix = red_mod.correlation_matrix(resampled_rows, signal_ids,
                                        method=method)
    diagnostics = red_mod.matrix_diagnostics(matrix)
    return diagnostics.get("effective_signal_count")


def _sensitivity(configuration, uni, analysis, similarity, *,
                 base_metrics: Dict[str, Any],
                 prices, links, run) -> List[Dict[str, Any]]:
    from app.experiment_registry.fingerprints import sha256_hex
    from app.signal_decay.fingerprints import _clean

    rows: List[Dict[str, Any]] = []
    seen_fps: Set[str] = set()

    base_scenario = {"label": "base"}
    base_fp = sha256_hex(_clean({"kind": "ensemble_scenario_v1",
                                 "overrides": {}}))
    seen_fps.add(base_fp)
    rows.append({
        "scenario_index": 0, "is_base": True, "label": "base",
        "scenario": base_scenario, "scenario_fingerprint": base_fp,
        "metrics": base_metrics, "warnings": [], "state": "available",
        "reason": None,
    })

    index = 1
    for scenario in analysis["sensitivity"]["scenarios"]:
        overrides = {k: v for k, v in scenario.items() if k != "label"}
        fp = sha256_hex(_clean({"kind": "ensemble_scenario_v1",
                                "overrides": overrides}))
        if fp in seen_fps:
            continue  # duplicate scenarios collapse deterministically
        seen_fps.add(fp)
        entry: Dict[str, Any] = {
            "scenario_index": index, "is_base": False,
            "label": scenario["label"], "scenario": scenario,
            "scenario_fingerprint": fp, "metrics": {}, "warnings": [],
            "state": "unavailable", "reason": None,
        }
        index += 1
        try:
            entry["metrics"] = _scenario_metrics(
                overrides, configuration, uni, analysis, similarity,
                prices=prices)
            entry["state"] = "available"
        except ENGINE_ERRORS as exc:
            entry["reason"] = str(exc)
        rows.append(entry)
    return rows


def _scenario_metrics(overrides, configuration, uni, analysis, similarity,
                      *, prices) -> Dict[str, Any]:
    signal_ids = uni["signal_ids"]
    orientations = universe_mod.validate_orientations(
        overrides.get("orientations",
                      configuration.get("orientations")), signal_ids)
    normalisation = norm_mod.validate_normalisation(
        overrides.get("normalisation",
                      configuration.get("normalisation")), signal_ids)
    raw_combo = dict(configuration.get("combination")
                     or {"mode": "equal_weight"})
    for field in ("weights", "weight_normalisation",
                  "missing_component_policy", "minimum_component_count"):
        if field in overrides:
            raw_combo[field] = overrides[field]
    combination_policy = combo_mod.validate_combination_policy(
        raw_combo, signal_ids)
    matrix_method = overrides.get("matrix_method",
                                  similarity["matrix_method"])
    if matrix_method not in ("pearson", "spearman"):
        raise SignalEnsembleError(
            "scenario matrix_method must be 'pearson' or 'spearman'")
    bucket_count = overrides.get("bucket_count",
                                 analysis["bucket"]["bucket_count"])
    if not isinstance(bucket_count, int) or isinstance(bucket_count, bool) \
            or not (2 <= bucket_count <= 10):
        raise SignalEnsembleError(
            "scenario bucket_count must be an integer in [2, 10]")
    horizon = overrides.get(
        "horizon",
        analysis["horizons"][0] if analysis["horizons"] else None)
    entry_lag = overrides.get("entry_lag", analysis["entry_lags"][0])
    if horizon is not None and (
            isinstance(horizon, bool) or not isinstance(horizon, int)
            or not (1 <= horizon <= 250)):
        raise SignalEnsembleError(
            "scenario horizon must be an integer in [1, 250]")
    if horizon is not None and prices is None:
        raise SignalEnsembleError(
            "scenario horizon evaluation requires supplied prices")
    if isinstance(entry_lag, bool) or not isinstance(entry_lag, int) \
            or not (0 <= entry_lag <= 60):
        raise SignalEnsembleError(
            "scenario entry_lag must be an integer in [0, 60]")


    grid = align_mod.build_grid(uni["observations"])
    stored_keys = {signal_id: [(r["entity_id"], r["source_timestamp"])
                               for r in uni["observations"][signal_id]]
                   for signal_id in signal_ids}
    oriented = norm_mod.orient_values(grid["values"], orientations)
    normalised: Dict[str, Dict[Key, Optional[float]]] = {}
    for signal_id in signal_ids:
        result = norm_mod.normalise_signal(
            oriented=oriented[signal_id],
            stored_keys=stored_keys[signal_id],
            config=normalisation[signal_id],
            tie_policy=uni["definitions"][signal_id]["tie_policy"])
        normalised[signal_id] = result["values"]
    strict_raw_keys = align_mod.strict_intersection(grid, signal_ids)
    matrix_keys = _common_value_keys(
        strict_raw_keys, normalised, signal_ids)
    resampled_rows = _matrix_rows(
        signal_ids, matrix_keys, normalised, method=matrix_method,
        minimum=similarity["minimum_pair_overlap"])
    absolutes = [abs(r["correlations"][matrix_method]["statistic"])
                 for r in resampled_rows
                 if r["correlations"][matrix_method]["state"]
                 == "available"]
    matrix = red_mod.correlation_matrix(resampled_rows, signal_ids,
                                        method=matrix_method)
    diagnostics = red_mod.matrix_diagnostics(matrix)
    if combination_policy["mode"] == "rank_average":
        combination_values: Dict[str, Dict[Key, Optional[float]]] = {}
        for signal_id in signal_ids:
            result = norm_mod.normalise_signal(
                oriented=oriented[signal_id],
                stored_keys=stored_keys[signal_id],
                config={"mode": "cross_sectional_rank_percentile",
                        "ddof": 1, "minimum_observations":
                            normalisation[signal_id]
                            ["minimum_observations"],
                        "window": None, "include_current": False},
                tie_policy=uni["definitions"][signal_id]["tie_policy"])
            combination_values[signal_id] = result["values"]
    else:
        combination_values = normalised

    combined = combo_mod.combine(
        keys=grid["keys"], component_values=combination_values,
        policy=combination_policy, signal_ids=signal_ids)
    spearman = spread = turnover_mean = None
    if horizon is not None and prices is not None:
        synthetic = _synthetic_combination_rows(
            combined["observations"], signal_ids=signal_ids, grid=grid,
            prefix="sc")
        if synthetic:
            built = sd_obs.build_pairs(
                synthetic, target_type="forward_return", prices=prices,
                supplied=None, horizon=horizon, entry_lag=entry_lag,
                extreme_loss_policy=analysis["outcome"]
                ["extreme_loss_policy"])
            pair_list = built["pairs"]
            signal_values = [p["signal_value"] for p in pair_list]
            block = stats_mod.correlation_block(
                signal_values, [p["outcome_value"] for p in pair_list],
                methods=("spearman",), minimum_observations=4,
                overlapping=bool(built["overlap"].get("overlap_ratio")))
            spearman = block["spearman"].get("statistic")
            if len(pair_list) >= bucket_count \
                    and len(set(signal_values)) >= bucket_count:
                assignments, _t, _b = bucket_mod.assign_buckets(
                    pair_list, signal_values, bucket_count=bucket_count,
                    scope="per_timestamp")
                bucket_rows = bucket_mod.bucket_outcomes(
                    pair_list, assignments, bucket_count=bucket_count,
                    minimum_per_bucket=analysis["bucket"]
                    ["minimum_per_bucket"])
                spread = bucket_mod.top_minus_bottom(
                    bucket_rows, bucket_count=bucket_count).get("spread")
                timeline = turnover_mod.membership_timeline(
                    pair_list, assignments, bucket_count=bucket_count,
                    initial_policy=analysis["turnover"]["initial_policy"])
                turnover_mean = \
                    timeline["summary"]["mean_one_way_turnover"]
    return {
        "coverage": combined["coverage"],
        "component_count": len(signal_ids),
        "mean_absolute_correlation": (
            float(np.mean(absolutes)) if absolutes else None),
        "effective_signal_count":
            diagnostics.get("effective_signal_count"),
        "first_horizon_spearman": spearman,
        "first_horizon_spread": spread,
        "mean_one_way_turnover": turnover_mean,
        "cost_completeness": None,
    }


# ---------------------------------------------------------------------------
# Reads, baseline, comparison, invalidation, export
# ---------------------------------------------------------------------------

def get_run(run_id: int, *,
            include_configuration: bool = True) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"signal ensemble run {run_id} not found")
    results = run.pop("results", {}) or {}
    run.update({
        "missingness": results.get("missingness"),
        "matrix": results.get("matrix"),
        "distance": results.get("distance"),
        "matrix_diagnostics": results.get("matrix_diagnostics"),
        "clustering": results.get("clustering"),
        "redundancy": results.get("redundancy"),
        "reconciliation": results.get("reconciliation"),
        "combination_coverage": results.get("combination_coverage"),
        "turnover_summary": results.get("turnover_summary"),
        "holding_overlap": results.get("holding_overlap"),
        "cost": results.get("cost"),
        "component_turnover": results.get("component_turnover"),
        "multiple_testing": results.get("multiple_testing"),
        "held_out": results.get("held_out"),
        "factor_residual": results.get("factor_residual"),
        "contribution_rows_total": results.get("contribution_rows_total"),
        "contribution_rows_stored":
            results.get("contribution_rows_stored"),
        "warnings": results.get("warnings") or [],
        "normalisation_reasons": results.get("normalisation_reasons"),
    })
    run["definitions"] = store.list_definitions(run_id)
    run["leave_one_out"] = store.list_leave_one_out(run_id)
    if not include_configuration:
        run.pop("configuration", None)
    else:
        configuration = dict(run.get("configuration") or {})
        configuration.pop("universe", None)
        configuration.pop("prices", None)
        run["configuration"] = configuration
    return run


def list_runs(**kwargs) -> Dict[str, Any]:
    listing = store.list_runs(**kwargs)
    for item in listing["items"]:
        item.pop("configuration", None)
        item.pop("results", None)
    return listing


def invalidate_run(run_id: int, reason: str) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"signal ensemble run {run_id} not found")
    if not reason or not isinstance(reason, str) or len(reason) > 1000:
        raise SignalEnsembleError(
            "an invalidation reason of 1-1000 characters is required")
    if run["status"] == "invalidated":
        raise ConflictError("the run is already invalidated")
    note = (run.get("notes") or "") + \
        f"\n[invalidated] {reason}".strip()
    store.update_run(run_id, {"status": "invalidated", "is_baseline": 0,
                              "baseline_scope": None, "notes": note})
    return get_run(run_id)


def _baseline_scope(run: Dict[str, Any]) -> str:
    return "|".join([
        run.get("universe_fingerprint") or "-",
        run.get("combination_fingerprint") or "-",
        run.get("similarity_fingerprint") or "-",
        run.get("analysis_fingerprint") or "-",
        run.get("observation_start") or "-",
        run.get("observation_end") or "-",
        run.get("frequency") or "-",
    ])


def mark_baseline(run_id: int) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"signal ensemble run {run_id} not found")
    if run["status"] != "completed":
        raise ConflictError(
            "only a completed run can become a comparison baseline")
    if run["integrity_status"] not in BASELINE_ACCEPTABLE_INTEGRITY:
        raise ConflictError(
            f"integrity {run['integrity_status']!r} is not accepted for a "
            f"baseline; verified timing is required — a baseline is never "
            f"chosen by IC, spread, cost, effective signal count or "
            f"turnover")
    if run["completeness_status"] not in BASELINE_ACCEPTABLE_COMPLETENESS:
        raise ConflictError(
            f"completeness {run['completeness_status']!r} is not accepted "
            f"for a baseline")
    reconciliation = (run.get("results") or {}).get("reconciliation") or {}
    if reconciliation.get("state") == "failed":
        raise ConflictError(
            "a run whose component contributions failed reconciliation "
            "cannot become a baseline")
    if not run.get("result_fingerprint"):
        raise ConflictError("the run has no result fingerprint")
    store.mark_baseline(run_id, _baseline_scope(run))
    return get_run(run_id)


_COMPARE_FIELDS = (
    "universe_fingerprint", "combination_fingerprint",
    "similarity_fingerprint", "analysis_fingerprint",
    "alignment_policy", "combination_mode", "frequency",
    "observation_start", "observation_end",
)


def compare_runs(run_a: int, run_b: int) -> Dict[str, Any]:
    a = store.get_run(run_a)
    b = store.get_run(run_b)
    if a is None or b is None:
        raise NotFoundError("both runs must exist")
    warnings: List[str] = []
    if a["universe_fingerprint"] != b["universe_fingerprint"]:
        warnings.append("the two runs analyse DIFFERENT signal universes")
    if a["combination_fingerprint"] != b["combination_fingerprint"]:
        warnings.append("the combination policies differ")
    if a["similarity_fingerprint"] != b["similarity_fingerprint"]:
        warnings.append("the similarity policies differ")
    if a["analysis_fingerprint"] != b["analysis_fingerprint"]:
        warnings.append("the analysis policies differ")
    if a["status"] != "completed" or b["status"] != "completed":
        warnings.append("at least one run is not completed; its fields "
                        "are unavailable")

    def _field_state(field: str) -> Dict[str, Any]:
        left = a.get(field)
        right = b.get(field)
        if left is None and right is None:
            state = "unavailable"
        elif left is None:
            state = "only_in_b"
        elif right is None:
            state = "only_in_a"
        elif left == right:
            state = "same"
        else:
            state = "changed"
        return {"field": field, "a": left, "b": right, "state": state}

    fields = [_field_state(f) for f in _COMPARE_FIELDS]
    metrics = {}
    for metric in ("mean_absolute_correlation", "effective_signal_count",
                   "combined_available_count",
                   "strict_intersection_count"):
        metrics[metric] = {"a": a.get(metric), "b": b.get(metric)}
    comparable = (a["universe_fingerprint"] == b["universe_fingerprint"])
    return {
        "run_a": {"id": a["id"], "name": a["name"],
                  "status": a["status"]},
        "run_b": {"id": b["id"], "name": b["name"],
                  "status": b["status"]},
        "fields": fields, "metrics": metrics,
        "directly_comparable": comparable,
        "warnings": warnings,
        "note": ("differences are reported neutrally: no run is better, "
                 "no winner is declared, and nothing here selects an "
                 "ensemble"),
    }


def export(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    listing = store.list_runs(filters=filters, page=1,
                              page_size=MAX_EXPORT_RUNS)
    runs = []
    for item in listing["items"]:
        run = get_run(item["id"])
        run.pop("configuration", None)
        run["pairwise"] = store.list_pairwise(item["id"])
        run["observations"] = store.list_observations(item["id"],
                                                      limit=500)
        run["components"] = store.list_components(item["id"], limit=500)
        run["horizons"] = store.list_horizons(item["id"])
        run["regimes"] = store.list_regimes(item["id"])
        run["bootstrap"] = store.list_bootstrap(item["id"])
        run["sensitivity"] = store.list_sensitivity(item["id"])
        runs.append(run)
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "exported_at": store._now(),
        "filters": filters or {},
        "run_count": len(runs),
        "runs": runs,
        "disclaimer": (
            "Descriptive multi-signal similarity, redundancy and explicit "
            "combination measurements under stated alignment, timing and "
            "missing-data policies. Nothing here proves signal "
            "independence, diversification, predictability or alpha, "
            "recommends or selects a signal, weight, threshold, horizon "
            "or ensemble, or constitutes investment advice."),
    }


def lab_summary() -> Dict[str, Any]:
    return store.lab_summary()
