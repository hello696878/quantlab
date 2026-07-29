"""
Signal Decay Lab service (v1).

Execution order (fixed, bounded, deterministic):

1. validate definitions, observations, outcomes, horizons and policies;
   resolve and PIN every linked record (read-only)
2. apply the declared transformation and orientation
3. per (horizon, entry-lag) cell: build pairs, measure overlap, compute
   correlations / cross-sectional IC / buckets / spread / monotonicity —
   and, under the non-overlapping policy, the same on the deterministic
   non-overlap selection
4. turnover, holding-cohort overlap and the optional Phase 55 cost mapping
5. decay summaries, regime rows, validation train/held-out split,
   factor-residual outcome scope
6. multiple testing (Phase 53, reused), bootstrap (seeded, bounded)
7. fingerprints, persistence, integrity/completeness/overlap states

Every linked lab is READ-ONLY and fingerprint-pinned; execution refuses
when a pinned record changed.  Nothing here recommends, selects, sizes,
executes or monitors anything.
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

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

from app.signal_decay import EXPORT_SCHEMA_VERSION
from app.signal_decay import bootstrap as boot_mod
from app.signal_decay import buckets as bucket_mod
from app.signal_decay import costs as cost_mod
from app.signal_decay import decay as decay_mod
from app.signal_decay import definitions as defs_mod
from app.signal_decay import fingerprints as fp_mod
from app.signal_decay import observations as obs_mod
from app.signal_decay import statistics as stats_mod
from app.signal_decay import store
from app.signal_decay import turnover as turnover_mod

RARE_REGIME_MIN_OBSERVATIONS = 10
MAX_EXPORT_RUNS = 25
MULTIPLE_TESTING_METHODS = ("bonferroni", "holm", "bh")
DEFAULT_MULTIPLE_TESTING_ALPHA = 0.05

EXECUTION_ORDER = (
    "validate_and_pin_links", "transform_and_orient",
    "horizon_lag_cells", "turnover_cohorts_costs",
    "decay_regime_validation_factor", "multiple_testing_bootstrap",
    "fingerprints_persist",
)

BASELINE_ACCEPTABLE_INTEGRITY = frozenset({
    "verified_from_validation_split", "verified_point_in_time",
    "verified_trailing_signal"})
BASELINE_ACCEPTABLE_COMPLETENESS = frozenset({"complete", "partial"})


class SignalDecayError(ValueError):
    """Invalid request (HTTP 422)."""


class NotFoundError(LookupError):
    """Unknown run (HTTP 404)."""


class ConflictError(RuntimeError):
    """Illegal state transition (HTTP 409)."""


class InternalExecutionError(RuntimeError):
    """Unexpected execution failure (HTTP 500)."""


ENGINE_ERRORS = (
    SignalDecayError, defs_mod.DefinitionError, obs_mod.ObservationError,
    stats_mod.StatisticsError, bucket_mod.BucketError, decay_mod.DecayError,
    turnover_mod.TurnoverError, cost_mod.CostError, boot_mod.BootstrapError,
    fp_mod.FingerprintError,
)


def _optional_positive_id(value: Any, field: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SignalDecayError(f"{field} must be a positive integer")
    return int(value)


def _finite_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

def _validate_analysis_policy(raw: Any) -> Dict[str, Any]:
    cfg = dict(raw or {})
    unknown = sorted(set(cfg) - {
        "correlation_methods", "minimum_cross_section_entities", "decay",
        "multiple_testing", "bootstrap", "reference_notional"})
    if unknown:
        raise SignalDecayError(
            f"unsupported policy keys (a typo is never silently ignored): "
            f"{unknown}")
    methods = cfg.get("correlation_methods") or ["pearson", "spearman"]
    if not isinstance(methods, list) or not methods:
        raise SignalDecayError("correlation_methods must be a non-empty list")
    invalid = sorted(set(methods) - set(stats_mod.CORRELATION_METHODS))
    if invalid:
        raise SignalDecayError(
            f"unsupported correlation methods {invalid}; supported: "
            f"{list(stats_mod.CORRELATION_METHODS)}")
    methods = [m for m in stats_mod.CORRELATION_METHODS if m in set(methods)]

    minimum_entities = cfg.get("minimum_cross_section_entities",
                               stats_mod.MIN_CROSS_SECTION_ENTITIES)
    if isinstance(minimum_entities, bool) \
            or not isinstance(minimum_entities, int) or minimum_entities < 2:
        raise SignalDecayError(
            "minimum_cross_section_entities must be an integer >= 2")

    decay = decay_mod.validate_decay_config(cfg.get("decay"))

    mt_block: Optional[Dict[str, Any]] = None
    multiple_testing = cfg.get("multiple_testing")
    if multiple_testing is not None:
        if not isinstance(multiple_testing, dict):
            raise SignalDecayError("multiple_testing must be an object or null")
        unknown_mt = sorted(set(multiple_testing) - {"methods", "alpha",
                                                     "family"})
        if unknown_mt:
            raise SignalDecayError(
                f"unknown multiple_testing keys: {unknown_mt}")
        chosen = multiple_testing.get("methods") or list(
            MULTIPLE_TESTING_METHODS)
        invalid_mt = sorted(set(chosen) - set(MULTIPLE_TESTING_METHODS))
        if invalid_mt:
            raise SignalDecayError(
                f"unsupported multiple-testing methods {invalid_mt}; v1 "
                f"reuses the Phase 53 corrections "
                f"{list(MULTIPLE_TESTING_METHODS)} (Benjamini-Yekutieli is "
                f"not implemented there and is not simulated here)")
        alpha = mt_mod.validate_alpha(
            multiple_testing.get("alpha", DEFAULT_MULTIPLE_TESTING_ALPHA))
        family = multiple_testing.get(
            "family", "Spearman p-values of every evaluated (lag, horizon) "
                      "cell, ordered by lag then horizon")
        if not isinstance(family, str) or not (1 <= len(family) <= 300):
            raise SignalDecayError(
                "multiple_testing.family must be an explicit statement")
        mt_block = {"methods": [m for m in MULTIPLE_TESTING_METHODS
                                if m in set(chosen)],
                    "alpha": alpha, "family": family}

    bootstrap = boot_mod.validate_bootstrap_config(cfg.get("bootstrap"))

    reference_notional = cfg.get("reference_notional")
    if reference_notional is not None:
        reference_notional = cost_mod.validate_reference_notional(
            reference_notional)

    return {
        "correlation_methods": methods,
        "minimum_cross_section_entities": minimum_entities,
        "decay": decay,
        "multiple_testing_methods": (mt_block or {}).get("methods") or [],
        "multiple_testing_alpha": (mt_block or {}).get("alpha"),
        "multiple_testing_family": (mt_block or {}).get("family"),
        "bootstrap": bootstrap,
        "reference_notional": reference_notional,
    }


# ---------------------------------------------------------------------------
# Linked records (read-only, pinned)
# ---------------------------------------------------------------------------

def _dataset_identity(dataset_version_id: Optional[int]) -> Dict[str, Any]:
    if dataset_version_id is None:
        return {}
    version = dataset_store.get_version(dataset_version_id)
    if version is None:
        raise SignalDecayError(f"dataset version {dataset_version_id} not found")
    dataset = dataset_store.get_dataset(version["dataset_id"])
    return {
        "dataset_version_id": dataset_version_id,
        "dataset_name": dataset["name"] if dataset else None,
        "version_label": version["version_label"],
        "schema_fingerprint": version.get("schema_fingerprint"),
        "manifest_fingerprint": version.get("manifest_fingerprint"),
        "content_fingerprint": version.get("content_fingerprint"),
        "quality_status": version.get("quality_status"),
        "invalidated": bool(version.get("invalidated_at")),
    }


def _assert_pinned(label: str, current: Dict[str, Any],
                   expected: Dict[str, Any], mapping: Dict[str, str]) -> None:
    for expected_key, current_key in mapping.items():
        was = expected.get(expected_key)
        now = current.get(current_key)
        if was is not None and now is not None and was != now:
            raise ConflictError(
                f"the linked {label} changed since this run was created "
                f"({current_key}: {was} -> {now}); execution is refused "
                f"rather than silently measuring different inputs")


def _resolve_links(payload: Dict[str, Any]) -> Dict[str, Any]:
    linked: Dict[str, Any] = {"ids": {}}
    dataset_version_id = _optional_positive_id(
        payload.get("dataset_version_id"), "dataset_version_id")
    linked["dataset_identity"] = _dataset_identity(dataset_version_id)
    linked["ids"]["dataset_version_id"] = dataset_version_id

    feature_run_id = _optional_positive_id(payload.get("feature_run_id"),
                                           "feature_run_id")
    if feature_run_id is not None:
        frun = feature_store.get_run(feature_run_id)
        if frun is None or frun.get("status") != "completed":
            raise SignalDecayError(
                "feature_run_id must reference a completed feature "
                "diagnostics run")
        linked["feature_identity"] = {
            "feature_run_id": feature_run_id,
            "feature_run_name": frun["name"],
            "configuration_fingerprint": frun.get("configuration_fingerprint"),
            "result_fingerprint": frun.get("result_fingerprint"),
            "note": ("feature drift/stability metadata is read-only context; "
                     "feature importance is never relabelled signal "
                     "predictability"),
        }
    linked["ids"]["feature_run_id"] = feature_run_id

    meta_label_run_id = _optional_positive_id(payload.get("meta_label_run_id"),
                                              "meta_label_run_id")
    if meta_label_run_id is not None:
        mrun = meta_store.get_run(meta_label_run_id)
        if mrun is None or mrun.get("status") != "completed":
            raise SignalDecayError(
                "meta_label_run_id must reference a completed meta-labeling "
                "run")
        linked["meta_label_identity"] = {
            "meta_label_run_id": meta_label_run_id,
            "meta_label_run_name": mrun["name"],
            "configuration_fingerprint": mrun.get("configuration_fingerprint"),
            "result_fingerprint": mrun.get("result_fingerprint"),
            "note": ("a stored probability analysed here is treated as a "
                     "signal VALUE only; calibration and threshold records "
                     "stay in the meta-labeling lab, and score decay is a "
                     "different question from probability calibration"),
        }
    linked["ids"]["meta_label_run_id"] = meta_label_run_id

    validation_run_id = _optional_positive_id(payload.get("validation_run_id"),
                                              "validation_run_id")
    split_label = payload.get("validation_split_label")
    if validation_run_id is not None:
        vrun = validation_store.get_run(validation_run_id)
        if vrun is None or vrun.get("status") != "completed":
            raise SignalDecayError(
                "validation_run_id must reference a completed model-validation "
                "run")
        splits = validation_store.list_splits(validation_run_id)
        if not splits:
            raise SignalDecayError("the linked validation run has no splits")
        if split_label is None:
            split_label = splits[0]["split_label"]
        chosen = next((s for s in splits if s["split_label"] == split_label),
                      None)
        if chosen is None:
            raise SignalDecayError(
                f"validation split {split_label!r} not found in run "
                f"{validation_run_id}")
        linked["validation_identity"] = {
            "validation_run_id": validation_run_id,
            "validation_run_name": vrun["name"],
            "configuration_fingerprint": vrun.get("configuration_fingerprint"),
            "split_fingerprint": chosen["split_fingerprint"],
            "split_label": split_label,
            "leakage_clean": vrun.get("leakage_clean"),
        }
    elif split_label is not None:
        raise SignalDecayError("validation_split_label requires "
                               "validation_run_id")
    linked["ids"]["validation_run_id"] = validation_run_id

    regime_run_id = _optional_positive_id(payload.get("regime_run_id"),
                                          "regime_run_id")
    regime_definition_id = payload.get("regime_definition_id")
    if regime_run_id is not None:
        rrun = regime_store.get_run(regime_run_id)
        if rrun is None or rrun.get("status") != "completed":
            raise SignalDecayError(
                "regime_run_id must reference a completed regime diagnostics "
                "run")
        if not regime_definition_id:
            raise SignalDecayError(
                "regime linkage requires an explicit regime_definition_id")
        definition = next(
            (d for d in regime_store.list_definitions(rrun["id"])
             if d["definition_id"] == regime_definition_id), None)
        if definition is None:
            raise SignalDecayError(
                f"regime definition {regime_definition_id!r} not found in "
                f"run {regime_run_id}")
        linked["regime_identity"] = {
            "regime_run_id": regime_run_id,
            "regime_run_name": rrun["name"],
            "configuration_fingerprint": rrun.get("configuration_fingerprint"),
            "result_fingerprint": rrun.get("result_fingerprint"),
            "definition_fingerprint": definition.get("definition_fingerprint"),
            "regime_definition_id": regime_definition_id,
        }
    elif regime_definition_id:
        raise SignalDecayError("regime_definition_id requires regime_run_id")
    linked["ids"]["regime_run_id"] = regime_run_id

    cost_run_id = _optional_positive_id(payload.get("cost_diagnostic_run_id"),
                                        "cost_diagnostic_run_id")
    if cost_run_id is not None:
        crun = cost_store.get_run(cost_run_id)
        if crun is None:
            raise SignalDecayError(
                f"cost diagnostics run {cost_run_id} not found")
        model = cost_store.get_cost_model(cost_run_id)
        if model is None:
            raise SignalDecayError(
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
            raise SignalDecayError(
                "factor_run_id must reference a completed factor diagnostics "
                "run")
        linked["factor_identity"] = {
            "factor_run_id": factor_run_id,
            "factor_run_name": farun["name"],
            "configuration_fingerprint":
                farun.get("configuration_fingerprint"),
            "result_fingerprint": farun.get("result_fingerprint"),
            "model_policy_fingerprint":
                farun.get("model_policy_fingerprint"),
            "note": ("residual-outcome diagnostics use the stored Phase 59 "
                     "residuals read-only; a residual association is not "
                     "alpha and no automatic factor neutralisation happens"),
        }
    linked["ids"]["factor_run_id"] = factor_run_id
    return linked


# ---------------------------------------------------------------------------
# Transformation and orientation
# ---------------------------------------------------------------------------

def _apply_transformation(definition: Dict[str, Any],
                          observations: List[Dict[str, Any]]) -> None:
    """Fill ``rank_value`` in place under the declared transformation."""
    transformation = definition["transformation"]
    if transformation == "none":
        for row in observations:
            row["rank_value"] = None
        return
    if transformation == "rank_cross_sectional":
        by_stamp: Dict[str, List[Dict[str, Any]]] = {}
        for row in observations:
            if row["raw_value"] is not None:
                by_stamp.setdefault(row["source_timestamp"], []).append(row)
        for stamp, rows in by_stamp.items():
            _rank_rows(rows, definition["tie_policy"])
        return
    # rank_full_sample — DESCRIPTIVE: uses the whole sample.
    rows = [row for row in observations if row["raw_value"] is not None]
    _rank_rows(rows, definition["tie_policy"])


def _rank_rows(rows: List[Dict[str, Any]], tie_policy: str) -> None:
    ordered = sorted(rows, key=lambda r: (r["raw_value"], r["entity_id"],
                                          r["source_timestamp"]))
    if tie_policy == "first":
        for position, row in enumerate(ordered):
            row["rank_value"] = float(position + 1)
        return
    index = 0
    while index < len(ordered):
        j = index
        while j + 1 < len(ordered) \
                and ordered[j + 1]["raw_value"] == ordered[index]["raw_value"]:
            j += 1
        average_rank = (index + j) / 2.0 + 1.0
        for k in range(index, j + 1):
            ordered[k]["rank_value"] = average_rank
        index = j + 1


def _scores_for(observations: List[Dict[str, Any]],
                definition: Dict[str, Any]) -> Dict[Tuple[str, str], float]:
    """{(entity, timestamp): oriented configured score}."""
    out: Dict[Tuple[str, str], float] = {}
    invert = definition["direction"] == "higher_is_lower_score"
    use_rank = definition["transformation"] != "none"
    for row in observations:
        value = row["rank_value"] if use_rank else row["raw_value"]
        if value is None:
            continue
        out[(row["entity_id"], row["source_timestamp"])] = \
            (-float(value) if invert else float(value))
    return out


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def create_run(payload: Dict[str, Any], *,
               demo_key: Optional[str] = None) -> Dict[str, Any]:
    name = payload.get("name")
    if not isinstance(name, str) or not (1 <= len(name) <= 200):
        raise SignalDecayError("name must be 1-200 characters")

    definition = defs_mod.validate_signal_definition(payload.get("signal"))
    outcome = defs_mod.validate_outcome_definition(payload.get("outcome"))
    observations = obs_mod.validate_signal_observations(
        definition, payload.get("observations"))

    prices: Optional[Dict[Tuple[str, str], float]] = None
    supplied: Optional[List[Dict[str, Any]]] = None
    if outcome["target_type"] == "forward_return":
        prices = obs_mod.validate_prices(payload.get("prices"),
                                         outcome["price_field"])
        if payload.get("supplied_outcomes") is not None:
            raise SignalDecayError(
                "supplied_outcomes are not accepted for a forward_return "
                "outcome")
    else:
        supplied = obs_mod.validate_supplied_outcomes(
            payload.get("supplied_outcomes"))
        if payload.get("prices") is not None:
            raise SignalDecayError(
                "prices are not accepted for a supplied_outcome run; supplied "
                "outcomes are never reconstructed")

    horizons = obs_mod.validate_horizons(
        payload.get("horizons"),
        supplied_outcomes=outcome["target_type"] == "supplied_outcome")
    bucket_config = bucket_mod.validate_bucket_config(payload.get("buckets"))
    turnover_config = turnover_mod.validate_turnover_config(
        payload.get("turnover"))
    analysis = _validate_analysis_policy(payload.get("policy"))
    links = _resolve_links(payload)

    if links["ids"]["cost_diagnostic_run_id"] is not None \
            and analysis["reference_notional"] is None:
        raise SignalDecayError(
            "a linked cost run requires an explicit reference_notional in the "
            "policy; there is no default notional")

    signal_fp = fp_mod.signal_definition_fingerprint(
        definition, links.get("dataset_identity"))
    outcome_fp = fp_mod.outcome_definition_fingerprint(outcome)
    universe_fp = fp_mod.observation_universe_fingerprint(
        observations, prices=prices, supplied=supplied,
        signal_fp=signal_fp, outcome_fp=outcome_fp)
    horizon_fp = fp_mod.horizon_policy_fingerprint(horizons, bucket_config,
                                                   turnover_config)
    analysis_fp = fp_mod.analysis_policy_fingerprint(analysis)
    configuration_fp = fp_mod.configuration_fingerprint(
        universe_fp, horizon_fp, analysis_fp, links)

    entities = sorted({o["entity_id"] for o in observations})
    configuration = {
        "signal": definition,
        "outcome": outcome,
        "observations": observations,
        "prices": ([[e, t, v] for (e, t), v in sorted(prices.items())]
                   if prices is not None else None),
        "supplied_outcomes": supplied,
        "horizons": horizons,
        "buckets": bucket_config,
        "turnover": turnover_config,
        "policy": analysis,
        "links": links,
        "execution_order": list(EXECUTION_ORDER),
    }

    run = store.insert_run({
        "name": name, "description": payload.get("description", ""),
        "signal_id": definition["signal_id"],
        "signal_type": definition["signal_type"],
        "outcome_id": outcome["outcome_id"],
        "outcome_target_type": outcome["target_type"],
        "frequency": definition["frequency"],
        "entity_count": len(entities),
        "observation_count": len(observations),
        "horizon_count": len(horizons["horizons"]),
        "lag_count": len(horizons["entry_lags"]),
        "observation_start": observations[0]["source_timestamp"],
        "observation_end": observations[-1]["source_timestamp"],
        "configuration": configuration,
        "signal_fingerprint": signal_fp,
        "outcome_fingerprint": outcome_fp,
        "universe_fingerprint": universe_fp,
        "horizon_fingerprint": horizon_fp,
        "analysis_fingerprint": analysis_fp,
        "configuration_fingerprint": configuration_fp,
        "dataset_version_id": links["ids"]["dataset_version_id"],
        "feature_run_id": links["ids"]["feature_run_id"],
        "meta_label_run_id": links["ids"]["meta_label_run_id"],
        "validation_run_id": links["ids"]["validation_run_id"],
        "regime_run_id": links["ids"]["regime_run_id"],
        "cost_diagnostic_run_id": links["ids"]["cost_diagnostic_run_id"],
        "factor_run_id": links["ids"]["factor_run_id"],
        "app_version": get_app_version(), "git_commit": get_git_commit(),
        "notes": payload.get("notes", ""), "demo_key": demo_key,
    })
    return _hydrate(run)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def _hydrate(run: Dict[str, Any], *,
             include_configuration: bool = True) -> Dict[str, Any]:
    run = dict(run)
    results = run.pop("results", {}) or {}
    configuration = run.get("configuration") or {}
    links = configuration.get("links") or {}
    run["signal"] = configuration.get("signal")
    run["outcome"] = configuration.get("outcome")
    run["horizon_policy"] = configuration.get("horizons")
    run["bucket_policy"] = configuration.get("buckets")
    run["turnover_policy"] = configuration.get("turnover")
    run["policy"] = configuration.get("policy")
    run["dataset_identity"] = links.get("dataset_identity") or {}
    for key in ("feature_identity", "meta_label_identity",
                "validation_identity", "regime_identity", "cost_identity",
                "factor_identity"):
        run[key] = links.get(key)
    run["decay"] = results.get("decay") or []
    run["overlap"] = results.get("overlap") or []
    run["turnover_summary"] = results.get("turnover_summary")
    run["holding_overlap"] = results.get("holding_overlap")
    run["cost"] = results.get("cost")
    run["held_out"] = results.get("held_out")
    run["factor_residual"] = results.get("factor_residual")
    run["multiple_testing"] = results.get("multiple_testing")
    run["signal_diagnostics"] = results.get("signal_diagnostics")
    run["warnings"] = results.get("warnings") or []
    if not include_configuration:
        run["configuration"] = {
            "signal_id": (configuration.get("signal") or {}).get("signal_id"),
            "omitted": ("the full configuration, including every observation, "
                        "is returned by GET /runs/{id}"),
        }
    return run


def get_run(run_id: int) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"signal decay run {run_id} not found")
    return _hydrate(run)


def list_runs(**kwargs: Any) -> Dict[str, Any]:
    page = store.list_runs(**kwargs)
    page["items"] = [_hydrate(r, include_configuration=False)
                     for r in page["items"]]
    return page


def lab_summary() -> Dict[str, Any]:
    return store.lab_summary()


# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------

def execute_run(run_id: int, *,
                create_experiment: bool = False) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"signal decay run {run_id} not found")
    if run["status"] == "running":
        raise ConflictError("this run is already executing")
    if run["status"] == "invalidated":
        raise ConflictError("an invalidated run cannot be executed")
    store.update_run(run_id, {"status": "running", "started_at": store._now(),
                              "error_message": None})
    try:
        return _execute_body(run_id, run, create_experiment)
    except (*ENGINE_ERRORS, ConflictError) as exc:
        store.mark_failed(run_id, str(exc), store._now())
        raise
    except Exception as exc:  # pragma: no cover - defensive
        store.mark_failed(run_id, f"unexpected execution failure: {exc}",
                          store._now())
        raise InternalExecutionError(str(exc)) from exc


def _cell(pairs: List[Dict[str, Any]], scores: Dict[Tuple[str, str], float],
          *, horizon: Any, entry_lag: int, selection: str,
          outcome_scope: str, overlap: Dict[str, Any],
          unavailable_count: int, analysis: Dict[str, Any],
          bucket_config: Dict[str, Any], minimum_observations: int,
          frozen_thresholds: Optional[List[float]] = None
          ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """One (horizon, lag, selection, scope) result row + its bucket rows."""
    signal_values = [scores.get((p["entity_id"], p["signal_timestamp"]))
                     for p in pairs]
    outcome_values = [p["outcome_value"] for p in pairs]
    usable = [(p, s) for p, s in zip(pairs, signal_values) if s is not None]
    pairs = [p for p, _ in usable]
    signal_values = [s for _, s in usable]
    outcome_values = [p["outcome_value"] for p in pairs]

    overlapping = overlap["state"] in ("overlapping", "partially_overlapping")
    block = stats_mod.correlation_block(
        signal_values, outcome_values,
        methods=analysis["correlation_methods"],
        minimum_observations=minimum_observations,
        overlapping=overlapping and selection == "overlapping")

    row: Dict[str, Any] = {
        "horizon": horizon, "entry_lag": entry_lag, "selection": selection,
        "outcome_scope": outcome_scope,
        "observations": len(pairs),
        "unavailable_count": unavailable_count,
        "data_gap_count": 0,
        "overlap_ratio": overlap["overlap_ratio"],
        "max_simultaneous_overlap": overlap["max_simultaneous_overlap"],
        "effective_non_overlapping": obs_mod.effective_non_overlapping_count(
            len(pairs), horizon),
        "overlap_state": overlap["state"],
        "state": "unavailable", "reason": None, "p_value_note": None,
        "detail": {},
    }
    for method in ("pearson", "spearman", "kendall"):
        result = block.get(method)
        if result is None:
            continue
        row[method] = result["statistic"]
        row[f"{method}_p_value"] = result["p_value"]
        if result.get("p_value_note"):
            row["p_value_note"] = result["p_value_note"]
        if method == "spearman" and result["state"] != "available":
            row["reason"] = result["reason"]
    if any(block[m]["state"] == "available" for m in block):
        row["state"] = "available"
    row["detail"]["correlations"] = block

    scored_pairs = [dict(p, signal_value=s)
                    for p, s in zip(pairs, signal_values)]
    entity_count = len({p["entity_id"] for p in pairs})
    if entity_count >= analysis["minimum_cross_section_entities"]:
        ic = stats_mod.cross_sectional_ic(
            scored_pairs,
            minimum_entities=analysis["minimum_cross_section_entities"],
            overlapping=overlapping)
        row["mean_cross_sectional_ic"] = \
            ic["aggregate"]["mean_spearman_ic"]
        row["ic_ratio"] = ic["aggregate"]["ic_ratio"]
        row["detail"]["cross_sectional_ic"] = ic
    else:
        row["detail"]["cross_sectional_ic"] = {
            "reason": (f"{entity_count} entity(ies) — cross-sectional IC "
                       f"needs at least "
                       f"{analysis['minimum_cross_section_entities']}")}

    bucket_rows: List[Dict[str, Any]] = []
    if scored_pairs:
        assignments, thresholds, boundaries = bucket_mod.assign_buckets(
            scored_pairs, signal_values,
            bucket_count=bucket_config["bucket_count"],
            scope=bucket_config["scope"],
            frozen_thresholds=frozen_thresholds)
        outcomes = bucket_mod.bucket_outcomes(
            scored_pairs, assignments,
            bucket_count=bucket_config["bucket_count"],
            minimum_per_bucket=bucket_config["minimum_per_bucket"])
        boundary_by_bucket = {b["bucket"]: b for b in boundaries}
        for entry in outcomes:
            boundary = boundary_by_bucket.get(entry["bucket"], {})
            bucket_rows.append({
                "horizon": horizon, "entry_lag": entry_lag,
                "outcome_scope": outcome_scope, **entry,
                "score_minimum": boundary.get("score_minimum"),
                "score_maximum": boundary.get("score_maximum"),
            })
        spread = bucket_mod.top_minus_bottom(
            outcomes, bucket_count=bucket_config["bucket_count"])
        mono = bucket_mod.monotonicity(outcomes)
        unique_scores = len(set(signal_values))
        if unique_scores < bucket_config["bucket_count"] \
                and spread["state"] == "available":
            spread = dict(spread, spread=None, state="unavailable",
                          reason=(f"only {unique_scores} unique score "
                                  f"value(s) for "
                                  f"{bucket_config['bucket_count']} buckets: "
                                  f"equal-count buckets would split ties by "
                                  f"the documented deterministic key, so the "
                                  f"spread is conservatively unavailable"))
        row["top_minus_bottom"] = spread["spread"]
        row["monotonicity_spearman"] = mono["spearman_bucket_vs_mean"]
        row["detail"]["spread"] = spread
        row["detail"]["monotonicity"] = mono
        row["detail"]["bucket_thresholds"] = thresholds
        row["detail"]["assignments_available"] = len(scored_pairs)
    return row, bucket_rows


def _execute_body(run_id: int, run: Dict[str, Any],
                  create_experiment: bool) -> Dict[str, Any]:
    configuration = run["configuration"]
    definition = configuration["signal"]
    outcome = configuration["outcome"]
    observations = [dict(o) for o in configuration["observations"]]
    horizons = configuration["horizons"]
    bucket_config = configuration["buckets"]
    turnover_config = configuration["turnover"]
    analysis = configuration["policy"]
    links = configuration.get("links") or {}
    warnings: List[str] = []

    prices = ({(e, t): v for e, t, v in configuration["prices"]}
              if configuration.get("prices") is not None else None)
    supplied = configuration.get("supplied_outcomes")

    # --- step 1: pin linked records -------------------------------------
    _pin_all(run, links)
    dataset_identity = links.get("dataset_identity") or {}
    if dataset_identity.get("invalidated"):
        warnings.append(
            f"the linked dataset version "
            f"{dataset_identity.get('version_label')} is marked invalidated "
            f"in Dataset Lineage; results are reported but their input "
            f"identity is disputed")

    # --- step 2: transformation + orientation ---------------------------
    _apply_transformation(definition, observations)
    scores = _scores_for(observations, definition)
    if definition["direction"] == "higher_is_lower_score":
        warnings.append(
            "the declared direction is higher_is_lower_score: configured "
            "scores are the negated raw values, an explicit declared "
            "inversion (raw values are stored unchanged)")

    validation_identity = links.get("validation_identity")
    membership = _validation_membership(run, validation_identity,
                                        observations)

    # --- step 3: horizon × lag cells ------------------------------------
    horizon_rows: List[Dict[str, Any]] = []
    bucket_rows: List[Dict[str, Any]] = []
    total_violations = 0
    base_cells: Dict[Tuple[Any, int], Dict[str, Any]] = {}
    overlap_summaries: List[Dict[str, Any]] = []
    for entry_lag in horizons["entry_lags"]:
        for horizon in horizons["horizons"]:
            built = obs_mod.build_pairs(
                observations, target_type=outcome["target_type"],
                prices=prices, supplied=supplied, horizon=horizon,
                entry_lag=entry_lag,
                extreme_loss_policy=outcome["extreme_loss_policy"])
            total_violations += len(built["violations"])
            if built["violations"]:
                first = built["violations"][0]
                warnings.append(
                    f"timing violation at horizon {horizon}, lag {entry_lag}: "
                    f"entity {first['entity_id']} signal of "
                    f"{first['signal_timestamp']} was available at "
                    f"{first['available_at']} but its outcome begins at "
                    f"{first['outcome_start']}")
            row, cell_buckets = _cell(
                built["pairs"], scores, horizon=horizon, entry_lag=entry_lag,
                selection="overlapping", outcome_scope="raw",
                overlap=built["overlap"],
                unavailable_count=len(built["unavailable"]),
                analysis=analysis, bucket_config=bucket_config,
                minimum_observations=horizons["minimum_observations"])
            row["data_gap_count"] = sum(
                1 for u in built["unavailable"] if u.get("kind") == "data")
            row["detail"]["unavailable"] = built["unavailable"][:20]
            row["detail"]["unavailable_note"] = (
                "structural entries (the grid simply ends before an exit) "
                "are listed but do not count against completeness; data "
                "gaps (null signals, missing prices, missing supplied "
                "outcomes) do")
            horizon_rows.append(row)
            bucket_rows.extend(cell_buckets)
            base_cells[(horizon, entry_lag)] = {"built": built, "row": row}
            overlap_summaries.append({
                "horizon": horizon, "entry_lag": entry_lag,
                **built["overlap"]})

            if horizons["overlap_policy"] == "non_overlapping":
                selected = obs_mod.select_non_overlapping(built["pairs"])
                overlap_nonsel = {"interval_count": len(selected),
                                  "unique_source_observations": len(selected),
                                  "overlapping_interval_count": 0,
                                  "overlap_ratio": 0.0 if selected else None,
                                  "max_simultaneous_overlap": 1 if selected
                                  else 0,
                                  "state": ("non_overlapping" if selected
                                            else "not_applicable")}
                non_row, non_buckets = _cell(
                    selected, scores, horizon=horizon, entry_lag=entry_lag,
                    selection="non_overlapping", outcome_scope="raw",
                    overlap=overlap_nonsel,
                    unavailable_count=len(built["unavailable"]),
                    analysis=analysis, bucket_config=bucket_config,
                    minimum_observations=horizons["minimum_observations"])
                horizon_rows.append(non_row)

    # --- step 4: turnover, cohorts, costs -------------------------------
    turnover_rows: List[Dict[str, Any]] = []
    turnover_summary: Optional[Dict[str, Any]] = None
    holding = None
    cost_block: Optional[Dict[str, Any]] = None
    first_horizon = horizons["horizons"][0]
    base = base_cells.get((first_horizon, horizons["entry_lags"][0]))
    if base and base["built"]["pairs"]:
        scored = [dict(p, signal_value=scores.get(
            (p["entity_id"], p["signal_timestamp"])))
            for p in base["built"]["pairs"]]
        scored = [p for p in scored if p["signal_value"] is not None]
        values = [p["signal_value"] for p in scored]
        assignments, _th, _b = bucket_mod.assign_buckets(
            scored, values, bucket_count=bucket_config["bucket_count"],
            scope=bucket_config["scope"])
        timeline = turnover_mod.membership_timeline(
            scored, assignments, bucket_count=bucket_config["bucket_count"],
            initial_policy=turnover_config["initial_policy"])
        turnover_summary = timeline["summary"]
        holding = turnover_mod.holding_overlap(
            timeline["summary"]["rebalance_count"], first_horizon,
            cohort_normalisation=turnover_config["cohort_normalisation"])
        if holding.get("warning"):
            warnings.append(holding["warning"])

        cost_identity = links.get("cost_identity")
        if cost_identity is not None:
            model = cost_store.get_cost_model(
                cost_identity["cost_diagnostic_run_id"])
            if model is None:
                raise ConflictError("the linked cost model is unavailable")
            _assert_pinned("cost model", model, cost_identity,
                           {"model_fingerprint": "fingerprint"})
            cost_block = cost_mod.cost_estimate(
                model, turnover_rows=timeline["rows"],
                reference_notional=analysis["reference_notional"])
            if cost_block["completeness"] != "complete":
                parts = []
                if cost_block["unavailable_components"]:
                    parts.append(
                        f"component(s) "
                        f"{cost_block['unavailable_components']} are "
                        f"unavailable")
                if cost_block["skipped_rebalances"]:
                    parts.append(
                        f"{cost_block['skipped_rebalances']} rebalance(s) "
                        f"have no turnover (no prior book)")
                warnings.append(
                    f"cost completeness is {cost_block['completeness']}: "
                    f"{'; '.join(parts)} — missing cost inputs stay "
                    f"unavailable, never zero")
        cost_by_stamp = {r["timestamp"]: r
                         for r in (cost_block or {}).get("rows", [])}
        for entry in timeline["rows"]:
            cost_row = cost_by_stamp.get(entry["timestamp"], {})
            turnover_rows.append({
                "horizon": first_horizon,
                "entry_lag": horizons["entry_lags"][0],
                **{k: v for k, v in entry.items() if k != "top_members"},
                "cost": cost_row.get("cost"),
                "cost_return": cost_row.get("cost_return"),
                "cost_state": cost_row.get("state"),
            })
        mean_cost_return = None
        if cost_block and cost_block["total_cost_return"] is not None \
                and cost_block["costed_rebalances"]:
            mean_cost_return = (cost_block["total_cost_return"]
                                / cost_block["costed_rebalances"])
        for row in horizon_rows:
            if row["outcome_scope"] != "raw" \
                    or row["selection"] != "overlapping":
                continue
            if row.get("top_minus_bottom") is not None \
                    and mean_cost_return is not None:
                row["cost_adjusted_spread"] = float(
                    row["top_minus_bottom"] - mean_cost_return)
        if cost_block:
            cost_block["spread_adjustment_convention"] = (
                "cost-adjusted spread = gross top-minus-bottom spread minus "
                "the MEAN per-rebalance reference cost return; holding "
                "periods and rebalance intervals are different time bases, "
                "which is disclosed rather than rescaled")

    # --- step 5: decay, regimes, validation, factor residuals ------------
    raw_rows = [r for r in horizon_rows
                if r["outcome_scope"] == "raw"
                and r["selection"] == "overlapping"
                and r["entry_lag"] == horizons["entry_lags"][0]]
    decay_rows = [
        decay_mod.decay_summary(raw_rows, statistic_key="spearman",
                                absolute_threshold=analysis["decay"]
                                ["absolute_threshold"]),
        decay_mod.decay_summary(raw_rows, statistic_key="top_minus_bottom",
                                absolute_threshold=None),
    ]

    regime_rows = _regime_rows(run, links, base_cells, scores, analysis,
                               bucket_config, horizons, warnings)

    held_out = _held_out_block(run, links, membership, base_cells, scores,
                               analysis, bucket_config, horizons, warnings)

    factor_block, factor_horizon_rows, factor_bucket_rows = _factor_residuals(
        run, links, base_cells, scores, analysis, bucket_config, horizons,
        warnings)
    horizon_rows.extend(factor_horizon_rows)
    bucket_rows.extend(factor_bucket_rows)

    # --- step 6: multiple testing + bootstrap ----------------------------
    mt_block = _multiple_testing(horizon_rows, analysis)

    bootstrap_rows: List[Dict[str, Any]] = []
    if analysis.get("bootstrap") and base and base["built"]["pairs"]:
        scored = [dict(p, signal_value=scores.get(
            (p["entity_id"], p["signal_timestamp"])))
            for p in base["built"]["pairs"]]
        scored = [p for p in scored if p["signal_value"] is not None]
        result = boot_mod.run_bootstrap(
            scored, analysis["bootstrap"],
            bucket_count=bucket_config["bucket_count"])
        bootstrap_rows.append({
            "horizon": first_horizon, "entry_lag": horizons["entry_lags"][0],
            **result})

    # --- signal-only diagnostics (persistence != prediction) -------------
    signal_diagnostics = _signal_diagnostics(observations, scores)

    # --- states ----------------------------------------------------------
    integrity = obs_mod.classify_integrity(
        definition=definition, target_type=outcome["target_type"],
        entry_lags=horizons["entry_lags"], violations=total_violations,
        validation=validation_identity, warnings=warnings)
    overlap_status = _overlap_status(overlap_summaries)
    if overlap_status in ("overlapping", "partially_overlapping"):
        warnings.append(
            "outcome intervals overlap; overlapping observations are not "
            "independent, every classical p-value carries that limitation, "
            "and the effective non-overlapping count shown is a documented "
            "descriptive approximation — never an inferential sample size")
    completeness = _completeness(horizon_rows, cost_block)

    result_fp = fp_mod.result_fingerprint(
        horizon_rows=[{k: v for k, v in r.items() if k != "detail"}
                      for r in horizon_rows],
        bucket_rows=bucket_rows, turnover=turnover_summary,
        overlap=overlap_summaries, cost=cost_block, regimes=regime_rows,
        held_out=held_out, bootstrap_rows=bootstrap_rows, decay=decay_rows,
        warnings=warnings, integrity_status=integrity,
        completeness_status=completeness, overlap_status=overlap_status)

    first_rank_ic = next(
        (r["spearman"] for r in raw_rows
         if r["horizon"] == first_horizon and r.get("spearman") is not None),
        None)

    results_block = {
        "decay": decay_rows,
        "overlap": overlap_summaries,
        "turnover_summary": turnover_summary,
        "holding_overlap": holding,
        "cost": cost_block,
        "held_out": held_out,
        "factor_residual": factor_block,
        "multiple_testing": mt_block,
        "signal_diagnostics": signal_diagnostics,
        "warnings": warnings,
    }

    store.replace_children(
        run_id,
        definition={**definition,
                    "definition_fingerprint": run["signal_fingerprint"],
                    "outcome": outcome},
        observations=observations,
        horizon_rows=horizon_rows,
        bucket_rows=bucket_rows,
        turnover_rows=turnover_rows,
        regime_rows=regime_rows,
        bootstrap_rows=bootstrap_rows,
        run_columns={
            "status": "completed",
            "integrity_status": integrity,
            "completeness_status": completeness,
            "overlap_status": overlap_status,
            "first_horizon_rank_ic": _finite_or_none(first_rank_ic),
            "mean_one_way_turnover": _finite_or_none(
                (turnover_summary or {}).get("mean_one_way_turnover")),
            "results": results_block,
            "result_fingerprint": result_fp,
            "completed_at": store._now(),
            "error_message": None,
        })

    if create_experiment and not run.get("experiment_id"):
        record = experiment_integration.record_experiment(
            name=f"Signal decay: {run['name']}",
            module="signal_decay_diagnostics",
            experiment_type="diagnostic",
            description=(
                "Descriptive signal-outcome association across explicit "
                "horizons and implementation lags. No predictability, alpha "
                "or persistence claim; no recommended horizon, lag, "
                "threshold or trade."),
            parameters={
                "signal_id": definition["signal_id"],
                "signal_type": definition["signal_type"],
                "outcome_id": outcome["outcome_id"],
                "horizons": [str(h) for h in horizons["horizons"]],
                "entry_lags": horizons["entry_lags"],
                "overlap_policy": horizons["overlap_policy"],
                "bucket_count": bucket_config["bucket_count"],
                "entity_count": run["entity_count"],
                "observation_count": run["observation_count"],
                "configuration_fingerprint": run["configuration_fingerprint"],
            },
            metrics={
                "first_horizon_rank_ic": _finite_or_none(first_rank_ic),
                "mean_one_way_turnover": _finite_or_none(
                    (turnover_summary or {}).get("mean_one_way_turnover")),
                "integrity_status": integrity,
                "overlap_status": overlap_status,
                "cost_completeness": (cost_block or {}).get("completeness"),
                "result_fingerprint": result_fp,
            },
            tags=["signal-decay", definition["signal_type"],
                  horizons["overlap_policy"]],
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

def _pin_all(run: Dict[str, Any], links: Dict[str, Any]) -> None:
    checks = (
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


def _validation_membership(run: Dict[str, Any],
                           validation_identity: Optional[Dict[str, Any]],
                           observations: List[Dict[str, Any]]
                           ) -> Optional[Dict[str, set]]:
    if not validation_identity:
        return None
    vrun = validation_store.get_run(run["validation_run_id"])
    splits = validation_store.list_splits(run["validation_run_id"])
    split = next((s for s in splits
                  if s["split_label"] == validation_identity["split_label"]),
                 None)
    if vrun is None or split is None:
        raise ConflictError("the linked validation split is unavailable")
    _assert_pinned("validation split", split, validation_identity,
                   {"split_fingerprint": "split_fingerprint"})
    time_by_sample = {s["sample_id"]: s.get("prediction_time")
                      for s in vrun["samples"]}
    return {
        "train": {time_by_sample.get(i) for i in split["train_ids"]},
        "test": {time_by_sample.get(i) for i in split["test_ids"]},
        "purged": {time_by_sample.get(i) for i in split["purged_ids"]},
        "embargoed": {time_by_sample.get(i) for i in split["embargoed_ids"]},
    }


def _held_out_block(run, links, membership, base_cells, scores, analysis,
                    bucket_config, horizons, warnings):
    if membership is None:
        return None
    first = horizons["horizons"][0]
    lag = horizons["entry_lags"][0]
    base = base_cells.get((first, lag))
    if base is None:
        return None
    pairs = base["built"]["pairs"]
    train_pairs = [p for p in pairs
                   if p["signal_timestamp"] in membership["train"]]
    test_pairs = [p for p in pairs
                  if p["signal_timestamp"] in membership["test"]]
    purged = sum(1 for p in pairs
                 if p["signal_timestamp"] in membership["purged"])
    embargoed = sum(1 for p in pairs
                    if p["signal_timestamp"] in membership["embargoed"])

    def _stats(subset, label, frozen=None):
        overlap = {"state": base["built"]["overlap"]["state"],
                   "overlap_ratio": base["built"]["overlap"]["overlap_ratio"],
                   "max_simultaneous_overlap":
                       base["built"]["overlap"]["max_simultaneous_overlap"]}
        row, _buckets = _cell(
            subset, scores, horizon=first, entry_lag=lag,
            selection="overlapping", outcome_scope=label, overlap=overlap,
            unavailable_count=0, analysis=analysis,
            bucket_config=bucket_config,
            minimum_observations=max(3, min(
                horizons["minimum_observations"], len(subset))),
            frozen_thresholds=frozen)
        return {k: row.get(k) for k in
                ("observations", "pearson", "spearman", "spearman_p_value",
                 "top_minus_bottom", "monotonicity_spearman", "state",
                 "reason")}

    # Train-derived bucket thresholds, applied FROZEN to held-out pairs.
    frozen_thresholds = None
    train_scored = [dict(p, signal_value=scores.get(
        (p["entity_id"], p["signal_timestamp"]))) for p in train_pairs]
    train_scored = [p for p in train_scored if p["signal_value"] is not None]
    if len(train_scored) >= bucket_config["bucket_count"]:
        _a, frozen_thresholds, _b = bucket_mod.assign_buckets(
            train_scored, [p["signal_value"] for p in train_scored],
            bucket_count=bucket_config["bucket_count"], scope="global")
    leakage_clean = links["validation_identity"].get("leakage_clean")
    if leakage_clean is False:
        warnings.append(
            "the linked validation run reports leakage; held-out figures are "
            "descriptive and the verified claim is withheld")
    return {
        "split_label": links["validation_identity"]["split_label"],
        "leakage_clean": leakage_clean,
        "training_observations": len(train_pairs),
        "held_out_observations": len(test_pairs),
        "purged_observations": purged,
        "embargoed_observations": embargoed,
        "training": _stats(train_pairs, "train"),
        "held_out": _stats(test_pairs, "held_out",
                           frozen=frozen_thresholds),
        "full_sample": _stats(pairs, "full"),
        "frozen_bucket_thresholds": frozen_thresholds,
        "note": ("bucket thresholds are derived from TRAINING observations "
                 "only and applied frozen to held-out observations; nothing "
                 "is refitted on held-out data, and purge/embargo membership "
                 "is used exactly as stored"),
    }


def _regime_rows(run, links, base_cells, scores, analysis, bucket_config,
                 horizons, warnings):
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
    label_by_stamp = dict(zip(rrun["timestamps"], definition["assignments"]))
    rows: List[Dict[str, Any]] = []
    rare_seen = False
    lag = horizons["entry_lags"][0]
    for horizon in horizons["horizons"]:
        base = base_cells.get((horizon, lag))
        if base is None:
            continue
        buckets_by_label: Dict[str, List[Dict[str, Any]]] = {}
        for pair in base["built"]["pairs"]:
            label = label_by_stamp.get(pair["signal_timestamp"])
            key = str(label) if label is not None else "unassigned"
            buckets_by_label.setdefault(key, []).append(pair)
        for label in sorted(buckets_by_label):
            subset = buckets_by_label[label]
            entry: Dict[str, Any] = {
                "regime_label": label, "horizon": horizon, "entry_lag": lag,
                "observations": len(subset),
                "rare": len(subset) < RARE_REGIME_MIN_OBSERVATIONS,
                "pearson": None, "spearman": None, "top_minus_bottom": None,
                "overlap_ratio": base["built"]["overlap"]["overlap_ratio"],
                "state": "unavailable", "reason": None,
            }
            if entry["rare"]:
                rare_seen = True
                entry["state"] = "rare"
                entry["reason"] = (
                    f"only {len(subset)} observation(s) in this regime "
                    f"(below {RARE_REGIME_MIN_OBSERVATIONS}); statistics are "
                    f"withheld")
                rows.append(entry)
                continue
            row, _b = _cell(
                subset, scores, horizon=horizon, entry_lag=lag,
                selection="overlapping", outcome_scope=f"regime:{label}",
                overlap=base["built"]["overlap"], unavailable_count=0,
                analysis=analysis, bucket_config=bucket_config,
                minimum_observations=3)
            entry.update({
                "pearson": row.get("pearson"),
                "spearman": row.get("spearman"),
                "top_minus_bottom": row.get("top_minus_bottom"),
                "state": row["state"], "reason": row.get("reason"),
            })
            rows.append(entry)
    if rare_seen:
        warnings.append(
            f"one or more regimes hold fewer than "
            f"{RARE_REGIME_MIN_OBSERVATIONS} observations; their statistics "
            f"are withheld, and differences between regimes are measurements "
            f"— never permanent properties")
    return rows


def _factor_residuals(run, links, base_cells, scores, analysis,
                      bucket_config, horizons, warnings):
    identity = links.get("factor_identity")
    if not identity:
        return None, [], []
    periods = factor_store.list_periods(run["factor_run_id"])
    residual_by_start = {p["period_start"]: p.get("residual")
                         for p in periods}
    if not residual_by_start:
        warnings.append(
            "the linked factor run stores no period residuals; the "
            "residual-outcome scope is unavailable")
        return {"state": "unavailable",
                "reason": "no stored factor residuals"}, [], []

    factor_starts = sorted(residual_by_start)
    lag = horizons["entry_lags"][0]
    horizon_rows: List[Dict[str, Any]] = []
    bucket_rows: List[Dict[str, Any]] = []
    matched_any = False
    unmatched = 0
    for horizon in horizons["horizons"]:
        base = base_cells.get((horizon, lag))
        if base is None:
            continue
        expected = horizon if isinstance(horizon, int) else None
        residual_pairs: List[Dict[str, Any]] = []
        for pair in base["built"]["pairs"]:
            # residual outcome = sum of the linked factor run's stored
            # per-period residuals whose period_start lies in [entry, exit)
            stamps = [s for s in factor_starts
                      if pair["entry_timestamp"] <= s
                      < pair["exit_timestamp"]]
            values = [residual_by_start.get(s) for s in stamps]
            if not stamps or any(v is None for v in values) \
                    or (expected is not None and len(stamps) != expected):
                unmatched += 1
                continue
            matched_any = True
            residual_pairs.append(
                dict(pair, outcome_value=float(sum(values))))
        if not residual_pairs:
            continue
        row, cell_buckets = _cell(
            residual_pairs, scores, horizon=horizon, entry_lag=lag,
            selection="overlapping", outcome_scope="factor_residual",
            overlap=base["built"]["overlap"],
            unavailable_count=unmatched, analysis=analysis,
            bucket_config=bucket_config,
            minimum_observations=horizons["minimum_observations"])
        horizon_rows.append(row)
        bucket_rows.extend(cell_buckets)

    block: Dict[str, Any] = {
        "factor_run_id": run["factor_run_id"],
        "factor_run_name": identity.get("factor_run_name"),
        "result_fingerprint": identity.get("result_fingerprint"),
        "model_policy_fingerprint": identity.get("model_policy_fingerprint"),
        "state": "available" if matched_any else "unavailable",
        "reason": (None if matched_any else
                   "no outcome interval matched the factor run's stored "
                   "period grid"),
        "unmatched_pairs": unmatched,
        "convention": (
            "the residual outcome of an interval is the ARITHMETIC SUM of "
            "the linked factor run's stored per-period residuals whose "
            "period_start falls inside [entry, exit); raw-outcome and "
            "residual-outcome diagnostics are separate rows, nothing is "
            "neutralised automatically, and a residual association is not "
            "alpha"),
    }
    if not matched_any:
        warnings.append(
            "the linked factor run's period grid does not match this "
            "signal's outcome intervals; the factor models are not directly "
            "comparable and the residual scope is unavailable")
    return block, horizon_rows, bucket_rows


def _multiple_testing(horizon_rows, analysis):
    methods = analysis.get("multiple_testing_methods") or []
    if not methods:
        return None
    family_rows = sorted(
        [r for r in horizon_rows
         if r["outcome_scope"] == "raw" and r["selection"] == "overlapping"],
        key=lambda r: (r["entry_lag"], str(r["horizon"])))
    entries = [{"candidate_id": f"lag{r['entry_lag']}-h{r['horizon']}",
                "raw_p": r.get("spearman_p_value"),
                "provenance": {"test": "Spearman rank correlation",
                               "source": "scipy.stats.spearmanr"}}
               for r in family_rows]
    adjusted = mt_mod.adjust_p_values(entries,
                                      analysis["multiple_testing_alpha"])
    by_id = {row["candidate_id"]: row for row in adjusted}
    for r in family_rows:
        row = by_id.get(f"lag{r['entry_lag']}-h{r['horizon']}")
        if row and "holm" in methods and row["holm"] is not None:
            r["spearman_p_adjusted"] = row["holm"]
        elif row and "bh" in methods and row["bh"] is not None:
            r["spearman_p_adjusted"] = row["bh"]
        elif row and "bonferroni" in methods \
                and row["bonferroni"] is not None:
            r["spearman_p_adjusted"] = row["bonferroni"]
    return {
        "methods": methods,
        "alpha": analysis["multiple_testing_alpha"],
        "family": analysis["multiple_testing_family"],
        "hypotheses": sum(1 for e in entries if e["raw_p"] is not None),
        "rows": adjusted,
        "note": ("raw p-values are preserved next to the adjusted values; "
                 "every evaluated cell is in the family (no unfavourable "
                 "horizon is omitted), and an adjusted p-value below alpha "
                 "still does not mean the signal is predictive"),
    }


def _signal_diagnostics(observations, scores):
    values = [scores.get((o["entity_id"], o["source_timestamp"]))
              for o in observations]
    return {
        "autocorrelation": stats_mod.signal_autocorrelation(values),
        "note": ("signal persistence (association with its own past) is a "
                 "different measurement from any signal-outcome association "
                 "and must not be read as predictive power"),
    }


def _overlap_status(overlap_summaries):
    states = {s["state"] for s in overlap_summaries}
    states.discard("not_applicable")
    if not states:
        return "not_applicable"
    if states == {"non_overlapping"}:
        return "non_overlapping"
    if "overlapping" in states and states <= {"overlapping"}:
        return "overlapping"
    return "partially_overlapping"


def _completeness(horizon_rows, cost_block):
    raw = [r for r in horizon_rows
           if r["outcome_scope"] == "raw" and r["selection"] == "overlapping"]
    if not raw or all(r["state"] != "available" for r in raw):
        return "unavailable"
    if any(r["state"] != "available" for r in raw) \
            or any(r.get("data_gap_count") for r in raw):
        return "partial"
    if cost_block and cost_block["completeness"] != "complete":
        return "partial"
    return "complete"


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def invalidate_run(run_id: int, reason: str) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"signal decay run {run_id} not found")
    if run["status"] == "invalidated":
        raise ConflictError("this run is already invalidated")
    store.update_run(run_id, {
        "status": "invalidated", "is_baseline": 0, "baseline_scope": None,
        "notes": (f"{run['notes']}\ninvalidated: {reason}").strip()[:2000]})
    return get_run(run_id)


def _baseline_scope(run: Dict[str, Any]) -> str:
    return "|".join([
        run["signal_fingerprint"], run["outcome_fingerprint"],
        run["universe_fingerprint"], run["horizon_fingerprint"],
        run["analysis_fingerprint"], run["frequency"],
        run["observation_start"] or "", run["observation_end"] or "",
    ])


def mark_baseline(run_id: int) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"signal decay run {run_id} not found")
    if run["status"] != "completed":
        raise ConflictError("only a completed run can become a baseline")
    if run["integrity_status"] not in BASELINE_ACCEPTABLE_INTEGRITY:
        raise ConflictError(
            f"integrity status '{run['integrity_status']}' cannot become a "
            f"comparison baseline; acceptable states are "
            f"{sorted(BASELINE_ACCEPTABLE_INTEGRITY)}")
    if run["completeness_status"] not in BASELINE_ACCEPTABLE_COMPLETENESS:
        raise ConflictError(
            f"completeness '{run['completeness_status']}' cannot become a "
            f"comparison baseline")
    if not run.get("result_fingerprint"):
        raise ConflictError("a baseline requires a stored result fingerprint")
    store.mark_baseline(run_id, _baseline_scope(run))
    return get_run(run_id)


def compare_runs(a_id: int, b_id: int) -> Dict[str, Any]:
    a = store.get_run(a_id)
    b = store.get_run(b_id)
    if a is None or b is None:
        raise NotFoundError("both runs must exist to be compared")
    warnings: List[str] = []

    def state(field: str) -> str:
        va, vb = a.get(field), b.get(field)
        if va is None and vb is None:
            return "unavailable"
        if va is None:
            return "only_in_b"
        if vb is None:
            return "only_in_a"
        return "same" if va == vb else "changed"

    fields = {
        "signal_fingerprint": state("signal_fingerprint"),
        "outcome_fingerprint": state("outcome_fingerprint"),
        "universe_fingerprint": state("universe_fingerprint"),
        "horizon_fingerprint": state("horizon_fingerprint"),
        "analysis_fingerprint": state("analysis_fingerprint"),
        "frequency": state("frequency"),
        "overlap_status": state("overlap_status"),
        "validation_run_id": state("validation_run_id"),
        "regime_run_id": state("regime_run_id"),
        "cost_diagnostic_run_id": state("cost_diagnostic_run_id"),
        "factor_run_id": state("factor_run_id"),
    }
    if fields["signal_fingerprint"] != "same":
        warnings.append("the two runs analyse DIFFERENT signal definitions")
    if fields["outcome_fingerprint"] != "same":
        warnings.append("the outcome definitions differ")
    if fields["universe_fingerprint"] != "same":
        warnings.append("the observation universes differ")
    if fields["horizon_fingerprint"] != "same":
        warnings.append("the horizon/bucket policies differ")
    if fields["analysis_fingerprint"] != "same":
        warnings.append("the analysis policies differ")
    if a["overlap_status"] != b["overlap_status"]:
        warnings.append(
            f"overlap status differs ({a['overlap_status']} vs "
            f"{b['overlap_status']}): the runs are not directly comparable "
            f"on inferential statistics")

    rows_a = {(str(r["horizon"]), r["entry_lag"]): r
              for r in store.list_horizons(a_id)
              if r["outcome_scope"] == "raw"
              and r["selection"] == "overlapping"}
    rows_b = {(str(r["horizon"]), r["entry_lag"]): r
              for r in store.list_horizons(b_id)
              if r["outcome_scope"] == "raw"
              and r["selection"] == "overlapping"}
    horizon_rows = []
    for key in sorted(set(rows_a) | set(rows_b)):
        ra, rb = rows_a.get(key), rows_b.get(key)
        horizon_rows.append({
            "horizon": key[0], "entry_lag": key[1],
            "a_spearman": (ra or {}).get("spearman"),
            "b_spearman": (rb or {}).get("spearman"),
            "a_spread": (ra or {}).get("top_minus_bottom"),
            "b_spread": (rb or {}).get("top_minus_bottom"),
            "presence": ("same" if ra and rb else
                         ("only_in_a" if ra else "only_in_b")),
        })
    return {
        "a_id": a_id, "b_id": b_id,
        "comparability_warnings": warnings,
        "fields": fields,
        "horizon_rows": horizon_rows,
        "metrics": {
            "first_horizon_rank_ic": {"a": a["first_horizon_rank_ic"],
                                      "b": b["first_horizon_rank_ic"]},
            "mean_one_way_turnover": {"a": a["mean_one_way_turnover"],
                                      "b": b["mean_one_way_turnover"]},
            "observations": {"a": a["observation_count"],
                             "b": b["observation_count"]},
        },
        "baseline": {"a": a["is_baseline"], "b": b["is_baseline"]},
        "note": ("differences are reported neutrally: no run is better, "
                 "no signal is validated, and no winner is declared"),
    }


def export(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    page = store.list_runs(filters=filters or {}, page=1,
                           page_size=MAX_EXPORT_RUNS)
    runs: List[Dict[str, Any]] = []
    for row in page["items"]:
        run = _hydrate(row)
        run_id = run["id"]
        runs.append({
            "run": {k: v for k, v in run.items() if k != "configuration"},
            "configuration": {k: v for k, v in
                              (row.get("configuration") or {}).items()
                              if k not in ("observations", "prices",
                                           "supplied_outcomes")},
            "definition": store.get_definition(run_id),
            "observations": store.list_observations(run_id),
            "horizons": store.list_horizons(run_id),
            "buckets": store.list_buckets(run_id),
            "turnover": store.list_turnover(run_id),
            "regimes": store.list_regimes(run_id),
            "bootstrap": store.list_bootstrap(run_id),
        })
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "exported_at": store._now(),
        "filters": filters or {},
        "run_count": len(runs),
        "runs": runs,
        "limits": {"max_runs": MAX_EXPORT_RUNS},
        "disclaimer": (
            "Descriptive signal-outcome associations under stated timing, "
            "horizon and overlap policies. Nothing here proves "
            "predictability or alpha, guarantees persistence, recommends a "
            "horizon, lag, threshold or trade, or constitutes investment "
            "advice."),
    }


__all__ = [
    "SignalDecayError", "NotFoundError", "ConflictError",
    "InternalExecutionError", "ENGINE_ERRORS", "EXECUTION_ORDER",
    "RARE_REGIME_MIN_OBSERVATIONS", "MULTIPLE_TESTING_METHODS",
    "create_run", "get_run", "list_runs", "lab_summary", "execute_run",
    "invalidate_run", "mark_baseline", "compare_runs", "export",
]
