"""
Factor Diagnostics service (v1).

Execution order (fixed, bounded, deterministic):

1. resolve the target series and pin every linked record's fingerprint
2. align factor observations against the target grid under the timing rule
3. fit the declared estimator (OLS, or the explicit ridge reference)
4. decompose the measured return period by period and reconcile it
5. multicollinearity, residual and multiple-testing diagnostics
6. trailing rolling estimates and exposure stability
7. portfolio-versus-benchmark exposure, stored-regime, stress and
   held-out validation views
8. bounded sensitivity scenarios, fingerprints and persistence

Every linked lab is READ-ONLY: Phase 55/56/57/58 records, Model Validation
memberships, Regime assignments, Dataset Lineage and Experiment Registry
rows are read, pinned by fingerprint and never rewritten.  Nothing in this
lab constructs a factor portfolio, hedges an exposure, allocates capital or
recommends anything.
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.dataset_registry import store as dataset_store
from app.experiment_registry import integration as experiment_integration
from app.experiment_registry import store as experiment_store
from app.experiment_registry.provenance import get_app_version, get_git_commit
from app.model_validation import store as validation_store
from app.overfitting_diagnostics import multiple_testing as mt_mod
from app.portfolio_attribution import observations as pa_observations
from app.portfolio_attribution import service as pa_service
from app.portfolio_attribution import store as attribution_store
from app.portfolio_diagnostics import store as pd_store
from app.portfolio_stress import store as stress_store
from app.regime_diagnostics import store as regime_store

from app.factor_diagnostics import decomposition as decomp_mod
from app.factor_diagnostics import definitions as defs_mod
from app.factor_diagnostics import diagnostics as diag_mod
from app.factor_diagnostics import fingerprints as fp_mod
from app.factor_diagnostics import observations as obs_mod
from app.factor_diagnostics import regression as reg_mod
from app.factor_diagnostics import rolling as rolling_mod
from app.factor_diagnostics import sensitivity as sens_mod
from app.factor_diagnostics import store
from app.factor_diagnostics import targets as target_mod
from app.factor_diagnostics import EXPORT_SCHEMA_VERSION

RARE_REGIME_MIN_OBSERVATIONS = 10
MAX_EXPORT_RUNS = 25
MULTIPLE_TESTING_METHODS = ("bonferroni", "holm", "bh")
#: Which estimate the run PRESENTS as its usable result.  A full-sample
#: window fit describes the whole window; a trailing declaration says the
#: usable estimates are the rolling ones, which is what
#: ``verified_trailing_estimation`` asserts.
ESTIMATION_SCOPES = ("full_sample_window", "rolling_trailing")
DEFAULT_MULTIPLE_TESTING_ALPHA = 0.05

EXECUTION_ORDER = (
    "resolve_target_and_links", "align_observations", "fit_estimator",
    "decompose_and_reconcile", "diagnose_design_and_residuals",
    "rolling_and_stability", "benchmark_regime_stress_validation",
    "sensitivity_fingerprints_persist",
)

BASELINE_ACCEPTABLE_INTEGRITY = frozenset({
    "verified_from_validation_split", "verified_causal_lag",
    "verified_trailing_estimation"})
BASELINE_ACCEPTABLE_COMPLETENESS = frozenset({"complete"})
BASELINE_ACCEPTABLE_RANK = frozenset({"full_rank"})

INTERCEPT_LABEL = (
    "the intercept is the mean return this specification did not explain "
    "over this sample; it is NOT alpha, skill or a forecast")


class FactorError(ValueError):
    """Invalid request (HTTP 422)."""


class NotFoundError(LookupError):
    """Unknown run (HTTP 404)."""


class ConflictError(RuntimeError):
    """Illegal state transition (HTTP 409)."""


class InternalExecutionError(RuntimeError):
    """Unexpected execution failure (HTTP 500)."""


#: Engine-level refusals are VALIDATION outcomes (422), not server errors:
#: an under-identified design or an unavailable factor value is a statement
#: about the inputs, and the run stores it as a failure with that message.
ENGINE_ERRORS = (
    FactorError, reg_mod.RegressionError, obs_mod.ObservationError,
    target_mod.TargetError, defs_mod.DefinitionError,
    decomp_mod.DecompositionError, rolling_mod.RollingError,
    sens_mod.SensitivityError, fp_mod.FingerprintError,
    # a linked lab refusing its own inputs is still a statement about THIS
    # run's inputs, so it is a 422 with that lab's message, not a 500
    pa_observations.ObservationError, pa_service.AttributionError,
)


def _optional_positive_id(value: Any, field: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise FactorError(f"{field} must be a positive integer")
    return int(value)


def _finite_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


# ---------------------------------------------------------------------------
# Policy validation
# ---------------------------------------------------------------------------

def _validate_policy(raw: Any, *, analysis_mode: str) -> Dict[str, Any]:
    cfg = dict(raw or {})
    unknown = sorted(set(cfg) - {
        "regression_method", "intercept_policy", "rank_policy",
        "timing_policy", "vintage_policy", "lead_periods", "confidence_level",
        "ridge_lambda", "ridge_scaling", "reconciliation_tolerance",
        "multiple_testing", "rolling", "estimation_scope"})
    if unknown:
        raise FactorError(
            f"unsupported policy keys (a typo is never silently ignored): "
            f"{unknown}")

    method = cfg.get("regression_method", "ols")
    if method not in reg_mod.REGRESSION_METHODS:
        raise FactorError(
            f"regression_method must be one of "
            f"{list(reg_mod.REGRESSION_METHODS)}")
    intercept_policy = cfg.get("intercept_policy", "include")
    if intercept_policy not in reg_mod.INTERCEPT_POLICIES:
        raise FactorError(
            f"intercept_policy must be one of "
            f"{list(reg_mod.INTERCEPT_POLICIES)}")
    rank_policy = cfg.get("rank_policy", "fail")
    if rank_policy not in reg_mod.RANK_POLICIES:
        raise FactorError(
            f"rank_policy must be one of {list(reg_mod.RANK_POLICIES)}")

    timing_policy = obs_mod.validate_timing_policy(
        cfg.get("timing_policy", "contemporaneous"))
    vintage_policy = obs_mod.validate_vintage_policy(
        cfg.get("vintage_policy", "supplied_vintage"))
    lead_periods = cfg.get("lead_periods", 0)
    if isinstance(lead_periods, bool) or not isinstance(lead_periods, int) \
            or lead_periods < 0:
        raise FactorError("lead_periods must be a non-negative integer")

    confidence = reg_mod.validate_confidence(cfg.get("confidence_level", 0.95))
    ridge_lambda = None
    ridge_scaling = None
    if method == "ridge":
        ridge_lambda = reg_mod.validate_ridge_lambda(cfg.get("ridge_lambda"))
        ridge_scaling = cfg.get("ridge_scaling", "none")
        if ridge_scaling not in reg_mod.RIDGE_SCALINGS:
            raise FactorError(
                f"ridge_scaling must be one of {list(reg_mod.RIDGE_SCALINGS)}")
    elif cfg.get("ridge_lambda") is not None:
        raise FactorError(
            "ridge_lambda is only valid when regression_method is 'ridge'")

    tolerance = decomp_mod.validate_tolerance(
        cfg.get("reconciliation_tolerance", decomp_mod.DEFAULT_TOLERANCE))

    multiple_testing = cfg.get("multiple_testing")
    mt_block: Optional[Dict[str, Any]] = None
    if multiple_testing is not None:
        if method == "ridge":
            raise FactorError(
                "multiple-testing correction requires p-values; ridge "
                "coefficients have none in v1")
        if not isinstance(multiple_testing, dict):
            raise FactorError("multiple_testing must be an object or null")
        unknown_mt = sorted(set(multiple_testing) - {"methods", "alpha",
                                                     "family"})
        if unknown_mt:
            raise FactorError(f"unknown multiple_testing keys: {unknown_mt}")
        methods = multiple_testing.get("methods") or list(
            MULTIPLE_TESTING_METHODS)
        if not isinstance(methods, list) or not methods:
            raise FactorError("multiple_testing.methods must be a non-empty list")
        invalid = sorted(set(methods) - set(MULTIPLE_TESTING_METHODS))
        if invalid:
            raise FactorError(
                f"unsupported multiple-testing methods {invalid}; v1 reuses "
                f"the Phase 53 corrections "
                f"{list(MULTIPLE_TESTING_METHODS)} (Benjamini-Yekutieli is "
                f"not implemented there and is not simulated here)")
        alpha = mt_mod.validate_alpha(
            multiple_testing.get("alpha", DEFAULT_MULTIPLE_TESTING_ALPHA))
        family = multiple_testing.get(
            "family", "coefficients of this run's declared factors")
        if not isinstance(family, str) or not (1 <= len(family) <= 200):
            raise FactorError(
                "multiple_testing.family must be an explicit 1-200 character "
                "statement of the hypothesis family")
        mt_block = {"methods": [m for m in MULTIPLE_TESTING_METHODS
                                if m in set(methods)],
                    "alpha": alpha, "family": family}

    rolling = rolling_mod.validate_rolling(cfg.get("rolling"))
    estimation_scope = cfg.get("estimation_scope", "full_sample_window")
    if estimation_scope not in ESTIMATION_SCOPES:
        raise FactorError(
            f"estimation_scope must be one of {list(ESTIMATION_SCOPES)}")
    if estimation_scope == "rolling_trailing" and rolling is None:
        raise FactorError(
            "estimation_scope 'rolling_trailing' requires a rolling block: "
            "the state claims the usable estimates are the trailing ones")

    if analysis_mode == "supplied_exposure_aggregation" and method == "ridge":
        raise FactorError(
            "supplied_exposure_aggregation uses supplied exposures; no "
            "estimator is fitted, so a ridge method cannot apply")
    if analysis_mode == "supplied_exposure_aggregation":
        if mt_block is not None:
            raise FactorError(
                "multiple-testing correction is unavailable for supplied "
                "exposures because no coefficient estimator is fitted")
        if rolling is not None:
            raise FactorError(
                "rolling coefficient estimation is unavailable for supplied "
                "exposures because exposures already vary by period")
        if estimation_scope != "full_sample_window":
            raise FactorError(
                "estimation_scope does not apply to supplied exposures")

    return {
        "analysis_mode": analysis_mode,
        "regression_method": method,
        "intercept_policy": intercept_policy,
        "rank_policy": rank_policy,
        "timing_policy": timing_policy,
        "vintage_policy": vintage_policy,
        "lead_periods": lead_periods,
        "confidence_level": confidence,
        "ridge_lambda": ridge_lambda,
        "ridge_scaling": ridge_scaling,
        "reconciliation_tolerance": tolerance,
        "standard_error_method": (reg_mod.STANDARD_ERROR_METHOD
                                  if method == "ols" else None),
        "standard_error_assumptions": (reg_mod.STANDARD_ERROR_ASSUMPTIONS
                                       if method == "ols" else None),
        "multiple_testing_methods": (mt_block or {}).get("methods") or [],
        "multiple_testing_alpha": (mt_block or {}).get("alpha"),
        "multiple_testing_family": (mt_block or {}).get("family"),
        "rolling": rolling,
        "estimation_scope": estimation_scope,
        "intercept_label": INTERCEPT_LABEL,
    }


# ---------------------------------------------------------------------------
# Linked-record resolution (read-only, pinned)
# ---------------------------------------------------------------------------

def _dataset_identity(dataset_version_id: Optional[int]) -> Dict[str, Any]:
    if dataset_version_id is None:
        return {}
    version = dataset_store.get_version(dataset_version_id)
    if version is None:
        raise FactorError(f"dataset version {dataset_version_id} not found")
    dataset = dataset_store.get_dataset(version["dataset_id"])
    return {
        "dataset_version_id": dataset_version_id,
        "dataset_name": dataset["name"] if dataset else None,
        "version_label": version["version_label"],
        "schema_fingerprint": version.get("schema_fingerprint"),
        "manifest_fingerprint": version.get("manifest_fingerprint"),
        "content_fingerprint": version.get("content_fingerprint"),
        "quality_status": version.get("quality_status"),
        "provenance_status": (dataset.get("provenance_status")
                              if dataset else None),
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
                f"({current_key}: {was} -> {now}); execution is refused rather "
                f"than silently re-measuring different inputs")


def _resolve_links(payload: Dict[str, Any], *, analysis_mode: str
                   ) -> Dict[str, Any]:
    linked: Dict[str, Any] = {}
    dataset_version_id = _optional_positive_id(payload.get("dataset_version_id"),
                                               "dataset_version_id")
    linked["dataset_identity"] = _dataset_identity(dataset_version_id)

    portfolio_run_id = _optional_positive_id(payload.get("portfolio_run_id"),
                                             "portfolio_run_id")
    if analysis_mode == "supplied_exposure_aggregation" \
            and portfolio_run_id is None:
        raise FactorError(
            "supplied_exposure_aggregation requires portfolio_run_id: the "
            "beginning-of-period weights come from a stored Phase 56 book")
    if portfolio_run_id is not None:
        prun = pd_store.get_run(portfolio_run_id)
        if prun is None or prun.get("status") != "completed":
            raise FactorError(
                "portfolio_run_id must reference a completed portfolio "
                "diagnostics run")
        linked["portfolio_configuration_fingerprint"] = \
            prun.get("configuration_fingerprint")
        linked["portfolio_run_name"] = prun["name"]

    validation_run_id = _optional_positive_id(payload.get("validation_run_id"),
                                              "validation_run_id")
    split_label = payload.get("validation_split_label")
    if validation_run_id is not None:
        vrun = validation_store.get_run(validation_run_id)
        if vrun is None or vrun.get("status") != "completed":
            raise FactorError(
                "validation_run_id must reference a completed model-validation "
                "run")
        splits = validation_store.list_splits(validation_run_id)
        if not splits:
            raise FactorError("the linked validation run has no splits")
        if split_label is None:
            split_label = splits[0]["split_label"]
        chosen = next((s for s in splits
                       if s["split_label"] == split_label), None)
        if chosen is None:
            raise FactorError(
                f"validation split {split_label!r} not found in run "
                f"{validation_run_id}")
        linked["validation_configuration_fingerprint"] = \
            vrun.get("configuration_fingerprint")
        linked["validation_split_fingerprint"] = chosen["split_fingerprint"]
        linked["validation_split_label"] = split_label
        linked["validation_leakage_clean"] = vrun.get("leakage_clean")
        linked["validation_run_name"] = vrun["name"]
    elif split_label is not None:
        raise FactorError("validation_split_label requires validation_run_id")

    regime_run_id = _optional_positive_id(payload.get("regime_run_id"),
                                          "regime_run_id")
    regime_definition_id = payload.get("regime_definition_id")
    if regime_run_id is not None:
        rrun = regime_store.get_run(regime_run_id)
        if rrun is None or rrun.get("status") != "completed":
            raise FactorError(
                "regime_run_id must reference a completed regime diagnostics "
                "run")
        if not regime_definition_id:
            raise FactorError(
                "regime linkage requires an explicit regime_definition_id")
        definition = next(
            (d for d in regime_store.list_definitions(rrun["id"])
             if d["definition_id"] == regime_definition_id), None)
        if definition is None:
            raise FactorError(
                f"regime definition {regime_definition_id!r} not found in run "
                f"{regime_run_id}")
        linked["regime_identity"] = {
            "regime_configuration_fingerprint":
                rrun.get("configuration_fingerprint"),
            "regime_result_fingerprint": rrun.get("result_fingerprint"),
            "regime_definition_fingerprint":
                definition.get("definition_fingerprint"),
            "regime_definition_id": regime_definition_id,
        }
        linked["regime_run_name"] = rrun["name"]
    elif regime_definition_id:
        raise FactorError("regime_definition_id requires regime_run_id")

    stress_run_id = _optional_positive_id(payload.get("stress_run_id"),
                                          "stress_run_id")
    shocks = payload.get("stress_factor_shocks")
    if stress_run_id is not None:
        srun = stress_store.get_run(stress_run_id)
        if srun is None or srun.get("status") != "completed":
            raise FactorError(
                "stress_run_id must reference a completed portfolio stress run")
        if not isinstance(shocks, dict) or not shocks:
            raise FactorError(
                "stress linkage requires an explicit stress_factor_shocks map "
                "{factor_id: shock in the factor's transformed unit}; factor "
                "shocks are never inferred from a scenario's asset shocks")
        linked["stress_identity"] = {
            "stress_configuration_fingerprint":
                srun.get("configuration_fingerprint"),
            "stress_result_fingerprint": srun.get("result_fingerprint"),
            "stress_run_name": srun["name"],
        }
    elif shocks:
        raise FactorError("stress_factor_shocks requires stress_run_id")

    linked["ids"] = {
        "dataset_version_id": dataset_version_id,
        "portfolio_run_id": portfolio_run_id,
        "validation_run_id": validation_run_id,
        "regime_run_id": regime_run_id,
        "stress_run_id": stress_run_id,
        "regime_definition_id": regime_definition_id,
    }
    return linked


def _resolve_target(spec: Dict[str, Any]) -> Dict[str, Any]:
    if spec["source"] == "attribution_run":
        run = attribution_store.get_run(spec["attribution_run_id"])
        if run is None:
            raise FactorError(
                f"attribution run {spec['attribution_run_id']} not found")
        periods = attribution_store.list_periods(run["id"])
        return target_mod.build_attribution_target(spec, run, periods)
    return target_mod.build_supplied_target(spec)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def create_run(payload: Dict[str, Any], *,
               demo_key: Optional[str] = None) -> Dict[str, Any]:
    name = payload.get("name")
    if not isinstance(name, str) or not (1 <= len(name) <= 200):
        raise FactorError("name must be 1-200 characters")
    description = payload.get("description", "")
    notes = payload.get("notes", "")

    analysis_mode = decomp_mod.validate_mode(
        payload.get("analysis_mode", "time_series_regression"))
    policy = _validate_policy(payload.get("policy"), analysis_mode=analysis_mode)

    target_spec = target_mod.validate_target(payload.get("target"))
    target = _resolve_target(target_spec)

    raw_factors = payload.get("factors")
    if not isinstance(raw_factors, list) or not raw_factors:
        raise FactorError("at least one factor definition is required")
    definition_inputs = [{k: v for k, v in f.items() if k != "observations"}
                         for f in raw_factors if isinstance(f, dict)]
    if len(definition_inputs) != len(raw_factors):
        raise FactorError("each factor must be an object")
    definitions = defs_mod.validate_definitions(definition_inputs)
    observations: Dict[str, List[Dict[str, Any]]] = {}
    observation_ids: set[str] = set()
    for definition, raw in zip(definitions, raw_factors):
        if definition["frequency"] != target["frequency"]:
            raise FactorError(
                f"factor '{definition['factor_id']}' frequency "
                f"{definition['frequency']!r} does not match target frequency "
                f"{target['frequency']!r}; mixed-frequency alignment is not "
                f"implemented in v1")
        validated = obs_mod.validate_observations(
            definition, raw.get("observations"))
        duplicates = sorted(
            {row["observation_id"] for row in validated} & observation_ids)
        if duplicates:
            raise FactorError(
                f"observation_id values must be unique across the run; "
                f"duplicates: {duplicates[:5]}")
        observation_ids.update(row["observation_id"] for row in validated)
        observations[definition["factor_id"]] = validated

    links = _resolve_links(payload, analysis_mode=analysis_mode)
    links["factor_dataset_identities"] = {
        d["factor_id"]: _dataset_identity(d.get("dataset_version_id"))
        for d in definitions if d.get("dataset_version_id") is not None}
    if analysis_mode == "supplied_exposure_aggregation":
        if links["ids"]["validation_run_id"] is not None:
            raise FactorError(
                "validation linkage is unavailable for supplied exposures "
                "because no estimator is fitted")
        if links["ids"]["stress_run_id"] is not None:
            raise FactorError(
                "factor stress linkage is unavailable for supplied exposures "
                "because it requires estimated coefficients")
        if payload.get("sensitivity"):
            raise FactorError(
                "coefficient sensitivity scenarios are unavailable for "
                "supplied exposures because no estimator is fitted")


    asset_exposures = None
    if analysis_mode == "supplied_exposure_aggregation":
        asset_exposures = decomp_mod.validate_asset_exposures(
            payload.get("asset_exposures"),
            factor_ids=[d["factor_id"] for d in definitions])
    elif payload.get("asset_exposures") is not None:
        raise FactorError(
            "asset_exposures are only used by supplied_exposure_aggregation")

    benchmark_comparison = bool(payload.get("benchmark_comparison", False))
    if benchmark_comparison and analysis_mode == "supplied_exposure_aggregation":
        raise FactorError(
            "benchmark coefficient comparison is unavailable for supplied "
            "exposures because no estimator is fitted")
    if benchmark_comparison and target["source"] != "attribution_run":
        raise FactorError(
            "benchmark comparison reads the benchmark series of the linked "
            "attribution run, so it requires an attribution-sourced target; a "
            "benchmark is never selected automatically")

    alignment = obs_mod.align(target, definitions, observations,
                              timing_policy=policy["timing_policy"],
                              vintage_policy=policy["vintage_policy"],
                              lead_periods=policy["lead_periods"])

    scenarios = sens_mod.validate_scenarios(
        payload.get("sensitivity"),
        factor_ids=[d["factor_id"] for d in definitions],
        observation_count=alignment["observation_count"])

    definition_fingerprints = {
        d["factor_id"]: fp_mod.factor_definition_fingerprint(
            d, (links["factor_dataset_identities"].get(d["factor_id"])
                or links.get("dataset_identity")))
        for d in definitions}
    target_fp = fp_mod.target_fingerprint(target)
    observation_fp = fp_mod.observation_universe_fingerprint(
        alignment, target, definition_fingerprints)
    policy_fp = fp_mod.model_policy_fingerprint(policy)
    configuration_fp = fp_mod.configuration_fingerprint(
        observation_fp, policy_fp, {
            **links,
            "attribution_configuration_fingerprint":
                (target.get("source_identity") or {}).get(
                    "attribution_configuration_fingerprint"),
        }, scenarios)

    configuration = {
        "target": target_spec,
        # Pinned at CREATE time: the identity of the stored record this run
        # read.  Execution compares the live record against this snapshot and
        # refuses rather than silently measuring different inputs.
        "target_identity": target.get("source_identity") or {},
        "factors": [{**definition,
                     "observations": observations[definition["factor_id"]],
                     "definition_fingerprint":
                         definition_fingerprints[definition["factor_id"]]}
                    for definition in definitions],
        "policy": policy,
        "links": links,
        "asset_exposures": asset_exposures,
        "benchmark_comparison": benchmark_comparison,
        "stress_factor_shocks": payload.get("stress_factor_shocks"),
        "sensitivity": scenarios,
        "execution_order": list(EXECUTION_ORDER),
        "deferred": {
            "analysis_modes": decomp_mod.DEFERRED_MODES,
            "sensitivity_dimensions": sens_mod.DEFERRED_DIMENSIONS,
            "winsorisation": (
                "not implemented in v1; only the explicit 'none' policy is "
                "accepted"),
            "robust_standard_errors": (
                "no tested robust covariance estimator exists in this "
                "repository, so v1 offers classical OLS covariance only and "
                "never labels it robust"),
        },
    }

    run = store.insert_run({
        "name": name, "description": description,
        "analysis_mode": analysis_mode,
        "regression_method": policy["regression_method"],
        "intercept_policy": policy["intercept_policy"],
        "rank_policy": policy["rank_policy"],
        "timing_policy": policy["timing_policy"],
        "vintage_policy": policy["vintage_policy"],
        "target_id": target["target_id"], "target_type": target["target_type"],
        "target_source": target["source"],
        "return_convention": target["return_convention"],
        "return_frequency": target["frequency"],
        "currency": target["currency"],
        "observation_start": target["observation_start"],
        "observation_end": target["observation_end"],
        "factor_count": len(definitions),
        "observation_count": alignment["observation_count"],
        "excluded_period_count": len(alignment["excluded_periods"]),
        "integrity_status": "unknown",
        "completeness_status": "unavailable",
        "configuration": configuration,
        "target_fingerprint": target_fp,
        "observation_fingerprint": observation_fp,
        "model_policy_fingerprint": policy_fp,
        "configuration_fingerprint": configuration_fp,
        "dataset_version_id": links["ids"]["dataset_version_id"],
        "portfolio_run_id": links["ids"]["portfolio_run_id"],
        "attribution_run_id": target.get("attribution_run_id"),
        "validation_run_id": links["ids"]["validation_run_id"],
        "regime_run_id": links["ids"]["regime_run_id"],
        "stress_run_id": links["ids"]["stress_run_id"],
        "app_version": get_app_version(), "git_commit": get_git_commit(),
        "notes": notes, "demo_key": demo_key,
    })
    return _hydrate(run)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def _hydrate(run: Dict[str, Any], *,
             include_configuration: bool = True) -> Dict[str, Any]:
    """Attach the stored blocks a caller needs.

    The stored configuration carries the FULL factor observation payload —
    that is deliberate, because the run's inputs are part of its identity —
    so the list endpoint drops it and keeps only the identity fields. A
    listing must not ship every observation of every run.
    """
    run = dict(run)
    results = run.pop("results", {}) or {}
    configuration = run.get("configuration") or {}
    if not include_configuration:
        # A listing carries identity and the scalar metrics that are already
        # table columns; the result blocks belong to the detail endpoint.
        results = {}
        run["configuration"] = {
            "analysis_mode": (configuration.get("policy") or {}).get(
                "analysis_mode"),
            "factor_ids": [f["factor_id"]
                           for f in configuration.get("factors", [])],
            "omitted": ("the full configuration, including every factor "
                        "observation, is returned by GET /runs/{id}"),
        }
    links = configuration.get("links") or {}
    run["factors"] = [{k: v for k, v in f.items() if k != "observations"}
                      for f in configuration.get("factors", [])]
    run["target"] = configuration.get("target")
    run["policy"] = configuration.get("policy")
    run["deferred"] = configuration.get("deferred")
    run["dataset_identity"] = links.get("dataset_identity") or {}
    run["portfolio_run_name"] = links.get("portfolio_run_name")
    run["validation_run_name"] = links.get("validation_run_name")
    run["validation_split_label"] = links.get("validation_split_label")
    run["validation_leakage_clean"] = links.get("validation_leakage_clean")
    run["regime_run_name"] = links.get("regime_run_name")
    run["stress_run_name"] = (links.get("stress_identity") or {}).get(
        "stress_run_name")
    run["fit"] = results.get("fit")
    run["summary"] = results.get("summary")
    run["multicollinearity"] = results.get("multicollinearity")
    run["residual_diagnostics"] = results.get("residual_diagnostics")
    run["stability"] = results.get("stability") or []
    run["rolling_summary"] = results.get("rolling_summary")
    run["exposure_comparison"] = results.get("exposure_comparison") or []
    run["held_out"] = results.get("held_out")
    run["stress_linkage"] = results.get("stress_linkage")
    run["attribution_linkage"] = results.get("attribution_linkage")
    run["multiple_testing"] = results.get("multiple_testing")
    run["warnings"] = results.get("warnings") or []
    return run


def get_run(run_id: int) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"factor diagnostics run {run_id} not found")
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
        raise NotFoundError(f"factor diagnostics run {run_id} not found")
    if run["status"] == "running":
        raise ConflictError("this run is already executing")
    if run["status"] == "invalidated":
        raise ConflictError("an invalidated run cannot be executed")
    started = time.time()
    store.update_run(run_id, {"status": "running",
                              "started_at": store._now(),
                              "error_message": None})
    try:
        return _execute_body(run_id, run, started, create_experiment)
    except (*ENGINE_ERRORS, ConflictError) as exc:
        store.mark_failed(run_id, str(exc), store._now())
        raise
    except Exception as exc:  # pragma: no cover - defensive
        store.mark_failed(run_id, f"unexpected execution failure: {exc}",
                          store._now())
        raise InternalExecutionError(str(exc)) from exc


def _rebuild(run: Dict[str, Any]) -> Dict[str, Any]:
    """Re-derive every validated object from the STORED configuration."""
    configuration = run["configuration"]
    policy = configuration["policy"]
    definitions = [{k: v for k, v in f.items()
                    if k not in ("observations", "definition_fingerprint")}
                   for f in configuration["factors"]]
    observations = {f["factor_id"]: f["observations"]
                    for f in configuration["factors"]}
    target = _resolve_target(configuration["target"])
    alignment = obs_mod.align(target, definitions, observations,
                              timing_policy=policy["timing_policy"],
                              vintage_policy=policy["vintage_policy"],
                              lead_periods=policy["lead_periods"])
    return {"configuration": configuration, "policy": policy,
            "definitions": definitions, "observations": observations,
            "target": target, "alignment": alignment}


def _fit_design(y: Sequence[float], x: Sequence[Sequence[float]],
                factor_ids: Sequence[str], policy: Dict[str, Any],
                *, intercept_policy: Optional[str] = None,
                method: Optional[str] = None,
                ridge_lambda: Optional[float] = None) -> Dict[str, Any]:
    intercept = (intercept_policy or policy["intercept_policy"]) == "include"
    method = method or policy["regression_method"]
    if method == "ridge":
        return reg_mod.ridge_fit(
            y, x, factor_ids,
            ridge_lambda=(ridge_lambda if ridge_lambda is not None
                          else policy["ridge_lambda"]),
            intercept=intercept,
            scaling=policy.get("ridge_scaling") or "none")
    return reg_mod.ols_fit(y, x, factor_ids, intercept=intercept,
                           rank_policy=policy["rank_policy"],
                           confidence=policy["confidence_level"])


def _supplied_fit(period_rows: Sequence[Dict[str, Any]],
                  factor_ids: Sequence[str]) -> Dict[str, Any]:
    """Descriptive fit-shaped block for supplied exposures; no estimator."""
    available = [row for row in period_rows
                 if row.get("modelled_return") is not None]
    measured = [float(row["measured_return"]) for row in available]
    fitted = [float(row["modelled_return"]) for row in available]
    residuals = [float(row["residual"]) for row in available]
    n = len(available)
    rss = float(sum(value * value for value in residuals))
    mean = float(sum(measured) / n) if n else 0.0
    tss = float(sum((value - mean) ** 2 for value in measured))
    r_squared = (None if tss <= reg_mod.ZERO_VARIANCE_TOLERANCE
                 else float(1.0 - rss / tss))
    residual_mean = float(sum(residuals) / n) if n else None
    residual_std = None
    if n >= 2 and residual_mean is not None:
        residual_std = float(math.sqrt(
            sum((value - residual_mean) ** 2 for value in residuals) / (n - 1)))
    unavailable = (
        "period-varying exposures are supplied and stored on each period; "
        "no constant coefficient is estimated")
    coefficients = [{
        "factor_id": factor_id, "coefficient": None,
        "standard_error": None, "t_statistic": None, "p_value": None,
        "confidence_lower": None, "confidence_upper": None,
        "unavailable_reason": unavailable,
    } for factor_id in factor_ids]
    return {
        "method": "supplied_exposure_aggregation",
        "intercept_policy": "not_applicable",
        "observations": n, "factors": len(factor_ids), "parameters": 0,
        "degrees_of_freedom": None, "intercept": None,
        "coefficients": coefficients, "fitted": fitted,
        "residuals": residuals, "residual_sum_of_squares": rss,
        "total_sum_of_squares": tss, "r_squared": r_squared,
        "adjusted_r_squared": None,
        "r_squared_note": (
            "descriptive goodness-of-fit of supplied period exposures; no "
            "coefficient estimator was fitted"),
        "root_mean_squared_error": (
            float(math.sqrt(rss / n)) if n else None),
        "residual_mean": residual_mean, "residual_std": residual_std,
        "sigma_squared": None, "rank": None, "expected_rank": None,
        "rank_status": "not_applicable",
        "rank_policy": "not_applicable", "standard_error_method": None,
        "standard_error_assumptions": None,
        "standard_error_state": "unavailable",
        "standard_error_note": unavailable, "confidence_level": None,
        "factor_rank": None, "factor_count": len(factor_ids),
        "singular_values": [], "condition_number": None,
        "condition_state": "unavailable",
        "condition_note": (
            "conditioning is not an estimator diagnostic in supplied mode"),
        "constant_columns": [], "duplicate_columns": [],
    }


def _execute_body(run_id: int, run: Dict[str, Any], started: float,
                  create_experiment: bool) -> Dict[str, Any]:
    rebuilt = _rebuild(run)
    configuration = rebuilt["configuration"]
    policy = rebuilt["policy"]
    definitions = rebuilt["definitions"]
    target = rebuilt["target"]
    alignment = rebuilt["alignment"]
    links = configuration.get("links") or {}
    warnings: List[str] = []
    factor_ids = [d["factor_id"] for d in definitions]
    tolerance = policy["reconciliation_tolerance"]

    # --- step 1: pin the linked records --------------------------------
    if run.get("attribution_run_id"):
        current = attribution_store.get_run(run["attribution_run_id"])
        if current is None:
            raise ConflictError("the linked attribution run is unavailable")
        _assert_pinned("attribution run", current,
                       configuration.get("target_identity") or {},
                       {"attribution_configuration_fingerprint":
                        "configuration_fingerprint",
                        "attribution_result_fingerprint":
                        "result_fingerprint"})
    if run.get("portfolio_run_id"):
        prun = pd_store.get_run(run["portfolio_run_id"])
        if prun is None:
            raise ConflictError("the linked portfolio run is unavailable")
        _assert_pinned("portfolio run", prun, links,
                       {"portfolio_configuration_fingerprint":
                        "configuration_fingerprint"})
    if run.get("validation_run_id"):
        vrun = validation_store.get_run(run["validation_run_id"])
        if vrun is None:
            raise ConflictError("the linked validation run is unavailable")
        _assert_pinned("validation run", vrun, links,
                       {"validation_configuration_fingerprint":
                        "configuration_fingerprint"})
    if run.get("regime_run_id"):
        rrun = regime_store.get_run(run["regime_run_id"])
        if rrun is None:
            raise ConflictError("the linked regime run is unavailable")
        _assert_pinned("regime run", rrun, links.get("regime_identity") or {},
                       {"regime_configuration_fingerprint":
                        "configuration_fingerprint",
                        "regime_result_fingerprint": "result_fingerprint"})
    dataset_identity = links.get("dataset_identity") or {}
    if dataset_identity.get("invalidated"):
        warnings.append(
            f"the linked dataset version "
            f"{dataset_identity.get('version_label')} is marked invalidated in "
            f"Dataset Lineage; results are reported but their input identity "
            f"is disputed")

    # --- step 2/3: design + estimator ----------------------------------
    design_rows = alignment["rows"]
    y = [float(r["target_return"]) for r in design_rows]
    x = [[float(v) for v in r["factor_values"]] for r in design_rows]
    if alignment["excluded_periods"]:
        warnings.append(
            f"{len(alignment['excluded_periods'])} target period(s) left the "
            f"estimation sample because a factor value was unavailable; the "
            f"gap is listed and never filled")
    macro_without_release = [
        d["factor_id"] for d in definitions
        if d["category"] == "macro"
        and d["availability_policy"] != "explicit_available_at"]
    if macro_without_release:
        warnings.append(
            f"macro factor(s) {macro_without_release} declare no release "
            f"timestamp, so availability is ASSUMED to equal the observation "
            f"timestamp. That is an assumption about publication timing, not "
            f"a measurement; a real release lag would change which periods "
            f"could have used the value.")

    validation_block = None
    if run.get("validation_run_id"):
        validation_block = {
            "leakage_clean": links.get("validation_leakage_clean"),
            "split_label": links.get("validation_split_label"),
        }
    integrity, integrity_warnings = obs_mod.classify_integrity(
        timing_policy=policy["timing_policy"],
        vintage_policy=policy["vintage_policy"],
        target=target, alignment=alignment, validation=validation_block,
        estimation_scope=policy.get("estimation_scope",
                                    "full_sample_window"))
    warnings.extend(integrity_warnings)

    held_out: Optional[Dict[str, Any]] = None
    membership: Dict[int, str] = {}
    if policy["analysis_mode"] == "supplied_exposure_aggregation":
        period_rows, mode_warnings = _supplied_exposure_rows(
            run, configuration, design_rows, definitions, tolerance)
        warnings.extend(mode_warnings)
        fit = _supplied_fit(period_rows, factor_ids)
    elif validation_block is not None:
        fit, held_out, membership, split_warnings = _fit_with_validation(
            run, design_rows, factor_ids, policy, tolerance)
        warnings.extend(split_warnings)
    else:
        fit = _fit_design(y, x, factor_ids, policy)

    if fit["condition_state"] == "high":
        warnings.append(
            f"the centred factor block has a condition number of "
            f"{fit['condition_number']:.3g}, above the "
            f"{reg_mod.MAX_CONDITION_NUMBER_WARNING:.0e} flag: small input "
            f"changes can move the coefficients materially. This is a neutral "
            f"warning, not a universal rule.")
    if fit["constant_columns"]:
        warnings.append(
            f"constant factor column(s) {fit['constant_columns']}: a constant "
            f"carries no cross-period information and is collinear with the "
            f"intercept; nothing was dropped automatically")
    if fit["duplicate_columns"]:
        pairs = ", ".join(f"{d['factor_a']}={d['factor_b']}"
                          for d in fit["duplicate_columns"])
        warnings.append(
            f"duplicate factor column(s) detected ({pairs}); the design is "
            f"rank deficient and the coefficients are not separately "
            f"identified")
    if fit["method"] in ("ols", "ridge") and fit["rank_status"] != "full_rank":
        warnings.append(
            f"RANK DEFICIENT design (rank {fit['rank']} of "
            f"{fit['expected_rank']}): the reported coefficients are a "
            f"labelled minimum-norm solution and are not identified; no "
            f"standard error, t-statistic or p-value is published for them")

    # --- step 4: decomposition + reconciliation -------------------------
    if policy["analysis_mode"] != "supplied_exposure_aggregation":
        period_rows = decomp_mod.regression_period_rows(
            design_rows, fit, factor_ids, tolerance,
            fit_residuals=fit["residuals"])
    summary = decomp_mod.summarise_periods(period_rows, factor_ids, tolerance)
    if summary["reconciliation_state"] == "mismatch":
        warnings.append(
            f"the period decomposition does not reconcile within "
            f"{tolerance:g}; the difference "
            f"{summary['reconciliation_difference']:.3e} is reported verbatim "
            f"and never redistributed")

    # --- step 5: design + residual diagnostics --------------------------
    correlation = diag_mod.correlation_matrix(x, factor_ids)
    vif_rows = ([] if fit["method"] == "supplied_exposure_aggregation"
                else diag_mod.variance_inflation(x, factor_ids))
    residual_stamps = (
        [row["period_start"] for row in period_rows
         if row.get("residual") is not None]
        if fit["method"] == "supplied_exposure_aggregation"
        else [row["period_start"] for row in design_rows])
    residuals_block = diag_mod.residual_diagnostics(
        fit["residuals"], residual_stamps)
    multicollinearity = {
        "correlation": correlation,
        "vif": vif_rows,
        "rank": fit["rank"],
        "expected_rank": fit["expected_rank"],
        "rank_status": fit["rank_status"],
        "singular_values": fit["singular_values"],
        "condition_number": fit["condition_number"],
        "condition_state": fit["condition_state"],
        "condition_note": fit["condition_note"],
        "constant_columns": fit["constant_columns"],
        "duplicate_columns": fit["duplicate_columns"],
        "note": ("diagnostics only: no factor is removed, reordered or "
                 "selected automatically, and no threshold here is a "
                 "universal rule"),
    }

    multiple_testing_rows, mt_block = _multiple_testing(fit, policy)
    if mt_block and mt_block.get("skipped"):
        warnings.append(mt_block["skipped"])

    # --- step 6: rolling + stability ------------------------------------
    rolling_rows: List[Dict[str, Any]] = []
    rolling_summary_block: Optional[Dict[str, Any]] = None
    stability: List[Dict[str, Any]] = []
    if policy.get("rolling") and policy["regression_method"] == "ols":
        rolling_rows = rolling_mod.rolling_estimates(
            design_rows, factor_ids,
            window=policy["rolling"]["window"],
            step=policy["rolling"]["step"],
            intercept=policy["intercept_policy"] == "include",
            rank_policy="minimum_norm_descriptive",
            confidence=policy["confidence_level"])
        rolling_summary_block = rolling_mod.rolling_summary(rolling_rows)
        stability = diag_mod.stability_metrics(rolling_rows, factor_ids,
                                               len(rolling_rows))
        if rolling_summary_block["rank_deficient"]:
            warnings.append(
                f"{rolling_summary_block['rank_deficient']} rolling window(s) "
                f"are rank deficient; their coefficients stay visible and are "
                f"never interpolated from neighbouring windows")
    elif policy.get("rolling"):
        warnings.append(
            "rolling estimates are produced for OLS only in v1; the ridge "
            "reference has no rolling view")

    # --- step 7: benchmark, regime, stress, held-out ---------------------
    exposure_comparison, benchmark_warnings = _benchmark_comparison(
        run, configuration, design_rows, factor_ids, policy, fit, period_rows,
        membership)
    warnings.extend(benchmark_warnings)

    regime_rows = _regime_rows(run, configuration, design_rows, period_rows,
                               factor_ids, policy, warnings)
    stress_linkage = _stress_linkage(configuration, fit, factor_ids, warnings)
    attribution_linkage = _attribution_linkage(run, target, summary)

    for index, row in enumerate(period_rows):
        row["membership"] = membership.get(row["period_index"])

    # --- step 8: sensitivity, fingerprints, persistence -------------------
    sensitivity_rows = _sensitivity_rows(configuration, rebuilt, policy,
                                         tolerance, membership)

    coefficient_rows = _coefficient_rows(fit, definitions, period_rows,
                                         vif_rows, multiple_testing_rows,
                                         policy, summary)

    completeness = _completeness(alignment, period_rows, fit, summary)
    reconciliation_status = summary["reconciliation_state"]

    result_fp = fp_mod.result_fingerprint(
        coefficients=coefficient_rows, fit=fit, period_rows=period_rows,
        exposure_comparison=exposure_comparison, rolling=rolling_rows,
        stability=stability, multicollinearity=multicollinearity,
        residuals=residuals_block, held_out=held_out, regimes=regime_rows,
        sensitivity_rows=sensitivity_rows, warnings=warnings,
        integrity_status=integrity, completeness_status=completeness,
        rank_status=fit["rank_status"])

    observation_rows = _observation_rows(alignment, definitions)

    results_block = {
        "fit": {k: v for k, v in fit.items()
                if k not in ("fitted", "residuals", "coefficients",
                             "intercept")},
        "fitted": fit["fitted"], "residuals": fit["residuals"],
        "intercept": fit.get("intercept"),
        "summary": summary,
        "multicollinearity": multicollinearity,
        "residual_diagnostics": residuals_block,
        "stability": stability,
        "rolling_summary": rolling_summary_block,
        "exposure_comparison": exposure_comparison,
        "held_out": held_out,
        "stress_linkage": stress_linkage,
        "attribution_linkage": attribution_linkage,
        "multiple_testing": mt_block,
        "excluded_periods": alignment["excluded_periods"],
        "warnings": warnings,
    }

    intercept_value = (float(fit["intercept"]["coefficient"])
                       if fit.get("intercept") else None)
    store.replace_children(
        run_id,
        definitions=[{**d, "definition_fingerprint":
                      next(f["definition_fingerprint"]
                           for f in configuration["factors"]
                           if f["factor_id"] == d["factor_id"]),
                      "observation_start": alignment["rows"][0]["period_start"],
                      "observation_end": alignment["rows"][-1]["period_end"]}
                     for d in definitions],
        observations=observation_rows,
        coefficients=coefficient_rows,
        periods=period_rows,
        rolling=rolling_rows,
        regimes=regime_rows,
        sensitivity=sensitivity_rows,
        run_columns={
            "status": "completed",
            "observation_count": alignment["observation_count"],
            "excluded_period_count": len(alignment["excluded_periods"]),
            "integrity_status": integrity,
            "completeness_status": completeness,
            "rank_status": fit["rank_status"],
            "reconciliation_status": reconciliation_status,
            "r_squared": _finite_or_none(fit["r_squared"]),
            "adjusted_r_squared": _finite_or_none(fit["adjusted_r_squared"]),
            "root_mean_squared_error":
                _finite_or_none(fit["root_mean_squared_error"]),
            "residual_std": _finite_or_none(fit["residual_std"]),
            "intercept": _finite_or_none(intercept_value),
            "condition_number": _finite_or_none(fit["condition_number"]),
            "degrees_of_freedom": fit["degrees_of_freedom"],
            "held_out_r_squared": (None if held_out is None
                                   else _finite_or_none(
                                       held_out.get("r_squared"))),
            "results": results_block,
            "result_fingerprint": result_fp,
            "completed_at": store._now(),
            "error_message": None,
        })

    if create_experiment and not run.get("experiment_id"):
        record = experiment_integration.record_experiment(
            name=f"Factor diagnostics: {run['name']}",
            module="factor_diagnostics",
            experiment_type="diagnostic",
            description=(
                "Measured sensitivities of one declared return series to "
                "supplied factor observations under an explicit timing rule. "
                "No causal, predictive or economic claim."),
            parameters={
                "analysis_mode": policy["analysis_mode"],
                "regression_method": policy["regression_method"],
                "timing_policy": policy["timing_policy"],
                "vintage_policy": policy["vintage_policy"],
                "intercept_policy": policy["intercept_policy"],
                "rank_policy": policy["rank_policy"],
                "factor_ids": factor_ids,
                "target_type": target["target_type"],
                "observation_count": alignment["observation_count"],
                "configuration_fingerprint": run["configuration_fingerprint"],
            },
            metrics={
                "observations": alignment["observation_count"],
                "factors": len(factor_ids),
                "r_squared": _finite_or_none(fit["r_squared"]),
                "adjusted_r_squared":
                    _finite_or_none(fit["adjusted_r_squared"]),
                "residual_std": _finite_or_none(fit["residual_std"]),
                "condition_number": _finite_or_none(fit["condition_number"]),
                "held_out_r_squared": (None if held_out is None
                                       else _finite_or_none(
                                           held_out.get("r_squared"))),
                "integrity_status": integrity,
                "rank_status": fit["rank_status"],
                "result_fingerprint": result_fp,
            },
            tags=["factor-diagnostics", policy["analysis_mode"],
                  policy["timing_policy"]],
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

def _fit_with_validation(run: Dict[str, Any],
                         design_rows: List[Dict[str, Any]],
                         factor_ids: List[str], policy: Dict[str, Any],
                         tolerance: float
                         ) -> Tuple[Dict[str, Any], Dict[str, Any],
                                    Dict[int, str], List[str]]:
    """Fit on TRAINING observations only; evaluate held-out with fixed betas."""
    warnings: List[str] = []
    links = (run["configuration"].get("links") or {})
    vrun = validation_store.get_run(run["validation_run_id"])
    splits = validation_store.list_splits(run["validation_run_id"])
    split = next((s for s in splits
                  if s["split_label"] == links.get("validation_split_label")),
                 None)
    if vrun is None or split is None:
        raise ConflictError("the linked validation split is unavailable")
    _assert_pinned("validation split", split, links,
                   {"validation_split_fingerprint": "split_fingerprint"})

    time_by_sample = {s["sample_id"]: s.get("prediction_time")
                      for s in vrun["samples"]}

    def sample_times(sample_ids: Sequence[str]) -> set[str]:
        stamps: set[str] = set()
        for sample_id in sample_ids:
            stamp = time_by_sample.get(sample_id)
            if stamp is None:
                continue
            try:
                stamps.add(obs_mod.normalise_timestamp(
                    stamp, field="validation prediction_time"))
            except obs_mod.ObservationError as exc:
                raise FactorError(str(exc)) from exc
        return stamps

    train_times = sample_times(split["train_ids"])
    test_times = sample_times(split["test_ids"])
    purged_times = sample_times(split["purged_ids"])
    embargoed_times = sample_times(split["embargoed_ids"])

    membership: Dict[int, str] = {}
    train_index: List[int] = []
    test_index: List[int] = []
    for position, row in enumerate(design_rows):
        stamp = row["period_start"]
        if stamp in train_times:
            membership[row["period_index"]] = "train"
            train_index.append(position)
        elif stamp in test_times:
            membership[row["period_index"]] = "test"
            test_index.append(position)
        elif stamp in purged_times:
            membership[row["period_index"]] = "purged"
        elif stamp in embargoed_times:
            membership[row["period_index"]] = "embargoed"
        else:
            membership[row["period_index"]] = "unassigned"

    parameters = len(factor_ids) + (1 if policy["intercept_policy"] == "include"
                                    else 0)
    if len(train_index) <= parameters:
        raise FactorError(
            f"the linked split leaves only {len(train_index)} training "
            f"observation(s) for {parameters} parameter(s); coefficients are "
            f"never fitted on held-out data to make up the difference")

    train_y = [float(design_rows[i]["target_return"]) for i in train_index]
    train_x = [[float(v) for v in design_rows[i]["factor_values"]]
               for i in train_index]
    fit = _fit_design(train_y, train_x, factor_ids, policy)

    betas = [float(c["coefficient"]) for c in fit["coefficients"]]
    intercept_value = (float(fit["intercept"]["coefficient"])
                       if fit.get("intercept") else None)
    held_out: Dict[str, Any] = {
        "split_label": links.get("validation_split_label"),
        "leakage_clean": vrun.get("leakage_clean"),
        "training_observations": len(train_index),
        "held_out_observations": len(test_index),
        "purged_observations": sum(1 for v in membership.values()
                                   if v == "purged"),
        "embargoed_observations": sum(1 for v in membership.values()
                                      if v == "embargoed"),
        "training_r_squared": fit["r_squared"],
        "training_rmse": fit["root_mean_squared_error"],
        "r_squared": None, "rmse": None, "correlation": None,
        "residual_mean": None, "residual_std": None,
        "r_squared_formula": (
            "1 - SUM (y - yhat)^2 / SUM (y - mean_TRAIN)^2 — the denominator "
            "uses the TRAINING mean so no held-out information enters the "
            "benchmark; a negative value is reported as measured"),
        "note": ("coefficients are fitted on the training observations only "
                 "and applied unchanged to the held-out observations; nothing "
                 "is refitted on held-out data"),
    }
    if vrun.get("leakage_clean") is False:
        warnings.append(
            "the linked validation run reports leakage, so the held-out "
            "metrics are descriptive and the causal claim is withheld")
    if not test_index:
        held_out["reason"] = (
            "no aligned period matches a held-out sample of this split")
        warnings.append(held_out["reason"])
        return fit, held_out, membership, warnings

    test_y = [float(design_rows[i]["target_return"]) for i in test_index]
    test_x = [[float(v) for v in design_rows[i]["factor_values"]]
              for i in test_index]
    predicted = reg_mod.predict(test_x, betas, intercept_value)
    training_mean = sum(train_y) / len(train_y)
    held_out["r_squared"] = reg_mod.out_of_sample_r_squared(
        test_y, predicted, training_mean)
    errors = [a - p for a, p in zip(test_y, predicted)]
    held_out["rmse"] = float(math.sqrt(sum(e * e for e in errors)
                                       / len(errors)))
    held_out["residual_mean"] = float(sum(errors) / len(errors))
    if len(errors) >= 2:
        mean_error = held_out["residual_mean"]
        variance = sum((e - mean_error) ** 2 for e in errors) / (len(errors) - 1)
        held_out["residual_std"] = float(math.sqrt(variance))
        held_out["correlation"] = _correlation(test_y, predicted)
    held_out["predictions"] = [{
        "period_start": design_rows[i]["period_start"],
        "measured": float(design_rows[i]["target_return"]),
        "predicted": float(p),
        "residual": float(design_rows[i]["target_return"] - p),
    } for i, p in zip(test_index, predicted)]
    return fit, held_out, membership, warnings


def _correlation(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    n = len(a)
    if n < 2:
        return None
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    numerator = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    denominator = math.sqrt(sum((x - mean_a) ** 2 for x in a)
                            * sum((y - mean_b) ** 2 for y in b))
    if denominator <= 0:
        return None
    value = numerator / denominator
    return float(min(1.0, max(-1.0, value)))


def _supplied_exposure_rows(run: Dict[str, Any], configuration: Dict[str, Any],
                            design_rows: List[Dict[str, Any]],
                            definitions: List[Dict[str, Any]],
                            tolerance: float
                            ) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Aggregate SUPPLIED asset exposures with stored Phase 56 weights."""
    prun = pd_store.get_run(run["portfolio_run_id"])
    if prun is None:
        raise ConflictError("the linked portfolio run is unavailable")
    # Reuse the Phase 58 helpers rather than re-deriving the decision index
    # or the drift recursion: the weight path a factor exposure aggregates
    # must be the SAME one the portfolio and attribution labs record.
    rebalances = pa_service._indexed_rebalances(prun)
    pa_policy = pa_observations.validate_policy({})
    book = pa_observations.build_observations(prun, rebalances, pa_policy)
    weights_by_stamp: Dict[str, Optional[Dict[str, float]]] = {}
    for period in book["periods"]:
        try:
            stamp = obs_mod.normalise_timestamp(
                period["period_start"], field="portfolio period_start")
        except obs_mod.ObservationError as exc:
            raise ConflictError(
                f"the linked portfolio has an invalid timestamp: {exc}") from exc
        rows = period.get("rows") or []
        if not rows or any(r.get("portfolio_beginning_weight") is None
                           for r in rows):
            weights_by_stamp[stamp] = None
            continue
        weights_by_stamp[stamp] = {
            r["asset_id"]: float(r["portfolio_beginning_weight"])
            for r in rows}
    ordered = [weights_by_stamp.get(r["period_start"]) for r in design_rows]
    exposure_rows = decomp_mod.aggregate_exposures(
        ordered, configuration["asset_exposures"],
        [d["factor_id"] for d in definitions])
    for position, row in enumerate(exposure_rows):
        row["period_index"] = design_rows[position]["period_index"]
    return decomp_mod.supplied_period_rows(design_rows, exposure_rows,
                                           definitions, tolerance)


def _multiple_testing(fit: Dict[str, Any], policy: Dict[str, Any]
                      ) -> Tuple[Dict[str, Dict[str, Any]],
                                 Optional[Dict[str, Any]]]:
    """Reuse the Phase 53 corrections on VALID coefficient p-values only."""
    methods = policy.get("multiple_testing_methods") or []
    if not methods:
        return {}, None
    entries = [{"candidate_id": c["factor_id"], "raw_p": c.get("p_value"),
                "provenance": {"test": "two-sided Student-t on the OLS "
                                       "coefficient", "source": "ols_fit"}}
               for c in fit["coefficients"]]
    valid = [e for e in entries if e["raw_p"] is not None]
    if not valid:
        return {}, {
            "methods": methods, "alpha": policy["multiple_testing_alpha"],
            "family": policy["multiple_testing_family"],
            "hypotheses": 0, "rows": [],
            "skipped": ("no valid coefficient p-value exists, so no "
                        "multiple-testing correction was applied"),
        }
    adjusted = mt_mod.adjust_p_values(entries,
                                      policy["multiple_testing_alpha"])
    by_factor: Dict[str, Dict[str, Any]] = {}
    rows: List[Dict[str, Any]] = []
    for row in adjusted:
        # The Phase 53 helper labels caller-supplied p-values 'declared';
        # here they come from this run's own Student-t test, so the
        # provenance is restated accurately.
        provenance = ("verified_from_ols_t_test" if row["raw_p_value"]
                      is not None else "unavailable")
        entry = {
            "factor_id": row["candidate_id"],
            "raw_p_value": row["raw_p_value"],
            "bonferroni": row["bonferroni"] if "bonferroni" in methods else None,
            "holm": row["holm"] if "holm" in methods else None,
            "bh": row["bh"] if "bh" in methods else None,
            "state_raw": row["state_raw"],
            "state_bonferroni": (row["state_bonferroni"]
                                 if "bonferroni" in methods else "unavailable"),
            "state_holm": (row["state_holm"] if "holm" in methods
                           else "unavailable"),
            "state_bh": row["state_bh"] if "bh" in methods else "unavailable",
            "provenance_status": provenance,
        }
        by_factor[row["candidate_id"]] = entry
        rows.append(entry)
    return by_factor, {
        "methods": methods, "alpha": policy["multiple_testing_alpha"],
        "family": policy["multiple_testing_family"],
        "hypotheses": len(valid), "rows": rows,
        "note": ("raw p-values are preserved alongside the adjusted values; "
                 "an adjusted p-value is still not evidence of causality, and "
                 "no factor was omitted from the family"),
    }


def _coefficient_rows(fit: Dict[str, Any], definitions: List[Dict[str, Any]],
                      period_rows: List[Dict[str, Any]],
                      vif_rows: List[Dict[str, Any]],
                      multiple_testing: Dict[str, Dict[str, Any]],
                      policy: Dict[str, Any],
                      summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    units = {d["factor_id"]: d["transformed_unit"] for d in definitions}
    vif_by_factor = {v["factor_id"]: v for v in vif_rows}
    rows: List[Dict[str, Any]] = []
    exposure_state = ("supplied"
                      if policy["analysis_mode"] ==
                      "supplied_exposure_aggregation" else "estimated")
    for coefficient in fit["coefficients"]:
        factor_id = coefficient["factor_id"]
        adjusted = multiple_testing.get(factor_id) or {}
        vif = vif_by_factor.get(factor_id) or {}
        warning_parts: List[str] = []
        if vif.get("warning"):
            warning_parts.append(
                f"variance inflation {vif['vif']:.2f} above "
                f"{diag_mod.HIGH_VIF_WARNING:g}")
        if factor_id in (fit.get("constant_columns") or []):
            warning_parts.append("constant factor column")
        for duplicate in fit.get("duplicate_columns") or []:
            if factor_id in (duplicate["factor_a"], duplicate["factor_b"]):
                warning_parts.append(
                    f"duplicate of {duplicate['factor_a']}/"
                    f"{duplicate['factor_b']}")
        rows.append({
            "factor_id": factor_id,
            "coefficient": _finite_or_none(coefficient["coefficient"]),
            "coefficient_unit": (
                None if exposure_state == "supplied"
                else f"target return per 1 "
                     f"{units.get(factor_id, 'unit')}"),
            "exposure_state": exposure_state,
            "standard_error": _finite_or_none(coefficient["standard_error"]),
            "t_statistic": _finite_or_none(coefficient["t_statistic"]),
            "p_value": _finite_or_none(coefficient["p_value"]),
            "p_bonferroni": _finite_or_none(adjusted.get("bonferroni")),
            "p_holm": _finite_or_none(adjusted.get("holm")),
            "p_bh": _finite_or_none(adjusted.get("bh")),
            "confidence_lower": _finite_or_none(
                coefficient["confidence_lower"]),
            "confidence_upper": _finite_or_none(
                coefficient["confidence_upper"]),
            "contribution_sum": _finite_or_none(
                (summary["factor_contribution_sums"] or {}).get(factor_id)),
            "vif": _finite_or_none(vif.get("vif")),
            "vif_state": vif.get("state"),
            "warning": "; ".join(warning_parts) or None,
            "unavailable_reason": coefficient.get("unavailable_reason"),
            "adjusted_p_values": {
                "bonferroni": adjusted.get("bonferroni"),
                "holm": adjusted.get("holm"), "bh": adjusted.get("bh"),
            } if adjusted else None,
        })
    return rows


def _observation_rows(alignment: Dict[str, Any],
                      definitions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    units = {d["factor_id"]: d["transformed_unit"] for d in definitions}
    rows: List[Dict[str, Any]] = []
    for design in alignment["rows"]:
        for index, source in enumerate(design["factor_sources"]):
            rows.append({
                "factor_id": source["factor_id"],
                "period_index": design["period_index"],
                "observation_id": source["observation_id"],
                "source_timestamp": source["source_timestamp"],
                "available_at": source["available_at"],
                "effective_timestamp": source["effective_timestamp"],
                "knowable_at": source["knowable_at"],
                "release_timestamp": source["release_timestamp"],
                "raw_value": _finite_or_none(source.get("raw_value")),
                "transformed_value": float(design["factor_values"][index]),
                "unit": units.get(source["factor_id"], "unknown"),
                "quality_state": source["quality_state"],
                "vintage_state": source["vintage_state"],
            })
    return rows


def _benchmark_comparison(run: Dict[str, Any], configuration: Dict[str, Any],
                          design_rows: List[Dict[str, Any]],
                          factor_ids: List[str], policy: Dict[str, Any],
                          fit: Dict[str, Any],
                          period_rows: List[Dict[str, Any]],
                          membership: Dict[int, str]
                          ) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Fit the SAME specification to the linked benchmark return series."""
    if not configuration.get("benchmark_comparison"):
        return [], []
    warnings: List[str] = []
    benchmark = attribution_store.get_benchmark(run["attribution_run_id"])
    if benchmark is None:
        warnings.append(
            "the linked attribution run stores no benchmark, so no exposure "
            "comparison is available")
        return [], warnings
    periods = attribution_store.list_periods(run["attribution_run_id"])
    returns_by_stamp: Dict[str, Optional[float]] = {}
    try:
        for period in periods:
            stamp = obs_mod.normalise_timestamp(
                period["period_start"], field="benchmark period_start")
            returns_by_stamp[stamp] = period.get("benchmark_return")
    except obs_mod.ObservationError as exc:
        warnings.append(
            f"the linked benchmark has an invalid timestamp; comparison is "
            f"unavailable: {exc}")
        return [], warnings
    fit_rows = [row for row in design_rows
                if not membership
                or membership.get(row["period_index"]) == "train"]
    missing = [row["period_start"] for row in fit_rows
               if returns_by_stamp.get(row["period_start"]) is None]
    if missing:
        warnings.append(
            f"the benchmark is missing {len(missing)} of the exact "
            f"{len(fit_rows)} portfolio estimation periods; comparison is "
            f"withheld rather than fitting a different sample")
        return [], warnings
    y: List[float] = []
    x: List[List[float]] = []
    for row in fit_rows:
        value = returns_by_stamp.get(row["period_start"])
        y.append(float(value))
        x.append([float(v) for v in row["factor_values"]])
    parameters = len(factor_ids) + (
        1 if policy["intercept_policy"] == "include" else 0)
    if len(y) <= parameters:
        warnings.append(
            "too few overlapping benchmark observations to fit the same "
            "specification; the exposure comparison is unavailable")
        return [], warnings
    try:
        benchmark_fit = _fit_design(y, x, factor_ids, policy)
    except reg_mod.RegressionError as exc:
        warnings.append(f"the benchmark specification could not be fitted: {exc}")
        return [], warnings

    portfolio_exposures = {c["factor_id"]: float(c["coefficient"])
                           for c in fit["coefficients"]}
    benchmark_exposures = {c["factor_id"]: float(c["coefficient"])
                           for c in benchmark_fit["coefficients"]}
    portfolio_contributions: Dict[str, Optional[float]] = {}
    benchmark_contributions: Dict[str, Optional[float]] = {}
    for index, factor_id in enumerate(factor_ids):
        values = [float(row["factor_values"][index]) for row in fit_rows]
        portfolio_contributions[factor_id] = float(
            portfolio_exposures[factor_id] * sum(values))
        benchmark_contributions[factor_id] = float(
            benchmark_exposures[factor_id] * sum(values))
    rows = decomp_mod.benchmark_comparison(
        portfolio_exposures, benchmark_exposures, factor_ids,
        portfolio_contributions=portfolio_contributions,
        benchmark_contributions=benchmark_contributions)
    for row in rows:
        row["benchmark_identity"] = {
            "benchmark_id": benchmark.get("benchmark_id"),
            "kind": benchmark.get("kind"), "source": benchmark.get("source"),
        }
    return rows, warnings


def _regime_rows(run: Dict[str, Any], configuration: Dict[str, Any],
                 design_rows: List[Dict[str, Any]],
                 period_rows: List[Dict[str, Any]], factor_ids: List[str],
                 policy: Dict[str, Any],
                 warnings: List[str]) -> List[Dict[str, Any]]:
    """Exposures by STORED Phase 54 regime assignment (never recomputed)."""
    if not run.get("regime_run_id"):
        return []
    rrun = regime_store.get_run(run["regime_run_id"])
    if rrun is None:
        return []
    identity = (configuration.get("links") or {}).get("regime_identity") or {}
    definition = next(
        (d for d in regime_store.list_definitions(rrun["id"])
         if d["definition_id"] == identity.get("regime_definition_id")), None)
    if definition is None:
        warnings.append("the linked regime definition is unavailable")
        return []
    try:
        label_by_stamp = {
            obs_mod.normalise_timestamp(stamp, field="regime timestamp"): label
            for stamp, label in zip(
                rrun["timestamps"], definition["assignments"])}
    except obs_mod.ObservationError as exc:
        warnings.append(
            f"the linked regime timestamps are invalid; regime results are unavailable: {exc}")
        return []
    buckets: Dict[str, List[int]] = {}
    for position, row in enumerate(design_rows):
        label = label_by_stamp.get(row["period_start"])
        key = str(label) if label is not None else "unassigned"
        buckets.setdefault(key, []).append(position)
        period_rows[position]["regime_label"] = key

    rows: List[Dict[str, Any]] = []
    for label in sorted(buckets):
        positions = buckets[label]
        observations = len(positions)
        rare = observations < RARE_REGIME_MIN_OBSERVATIONS
        entry: Dict[str, Any] = {
            "regime_label": label,
            "definition_id": identity.get("regime_definition_id"),
            "observations": observations, "rare": rare,
            "r_squared": None, "condition_number": None, "rank_status": None,
            "intercept": None, "residual_mean": None, "residual_std": None,
            "measured_return_sum": float(sum(
                period_rows[p]["measured_return"] for p in positions)),
            "modelled_return_sum": None, "residual_sum": None,
            "completeness": "partial", "status": "descriptive",
            "reason": None, "coefficients": {}, "contributions": {},
        }
        modelled = [period_rows[p]["modelled_return"] for p in positions]
        if all(v is not None for v in modelled):
            entry["modelled_return_sum"] = float(sum(modelled))
            entry["residual_sum"] = float(sum(
                period_rows[p]["residual"] for p in positions))
            entry["completeness"] = "complete"
        contributions: Dict[str, Optional[float]] = {}
        for factor_id in factor_ids:
            values = [period_rows[p]["factor_contributions"].get(factor_id)
                      for p in positions]
            contributions[factor_id] = (float(sum(values))
                                        if all(v is not None for v in values)
                                        else None)
        entry["contributions"] = contributions
        if policy["analysis_mode"] == "supplied_exposure_aggregation":
            entry["status"] = "descriptive"
            entry["reason"] = (
                "regime sums use the stored period-varying supplied exposures; "
                "no conditional coefficient estimator is fitted")
            rows.append(entry)
            continue
        if rare:
            entry["status"] = "rare"
            entry["reason"] = (
                f"only {observations} observation(s) in this regime (below "
                f"{RARE_REGIME_MIN_OBSERVATIONS}); the conditional fit is "
                f"withheld and the sums are descriptive")
            rows.append(entry)
            continue
        parameters = len(factor_ids) + (
            1 if policy["intercept_policy"] == "include" else 0)
        if observations <= parameters:
            entry["status"] = "insufficient_observations"
            entry["reason"] = (
                f"{observations} observation(s) cannot identify {parameters} "
                f"parameter(s) inside this regime")
            rows.append(entry)
            continue
        try:
            fit = reg_mod.ols_fit(
                [float(design_rows[p]["target_return"]) for p in positions],
                [[float(v) for v in design_rows[p]["factor_values"]]
                 for p in positions],
                factor_ids,
                intercept=policy["intercept_policy"] == "include",
                rank_policy="minimum_norm_descriptive",
                confidence=policy["confidence_level"])
        except reg_mod.RegressionError as exc:
            entry["status"] = "failed"
            entry["reason"] = str(exc)
            rows.append(entry)
            continue
        entry.update({
            "r_squared": fit["r_squared"],
            "condition_number": fit["condition_number"],
            "rank_status": fit["rank_status"],
            "intercept": (float(fit["intercept"]["coefficient"])
                          if fit.get("intercept") else None),
            "residual_mean": fit["residual_mean"],
            "residual_std": fit["residual_std"],
            "status": "estimated",
            "coefficients": {c["factor_id"]: float(c["coefficient"])
                             for c in fit["coefficients"]},
        })
        rows.append(entry)
    if any(r["rare"] for r in rows):
        warnings.append(
            "one or more regimes hold fewer than "
            f"{RARE_REGIME_MIN_OBSERVATIONS} observations; their conditional "
            f"fits are withheld and differences between regimes are neither "
            f"structural nor causal")
    return rows


def _stress_linkage(configuration: Dict[str, Any], fit: Dict[str, Any],
                    factor_ids: List[str],
                    warnings: List[str]) -> Optional[Dict[str, Any]]:
    """Exposure-implied contribution of EXPLICITLY supplied factor shocks."""
    shocks = configuration.get("stress_factor_shocks")
    if not shocks:
        return None
    identity = (configuration.get("links") or {}).get("stress_identity") or {}
    unknown = sorted(set(shocks) - set(factor_ids))
    if unknown:
        raise FactorError(
            f"stress_factor_shocks names factors that are not in this run: "
            f"{unknown}")
    betas = {c["factor_id"]: float(c["coefficient"])
             for c in fit["coefficients"]}
    rows: List[Dict[str, Any]] = []
    total = 0.0
    for factor_id in factor_ids:
        shock = shocks.get(factor_id)
        if shock is None:
            rows.append({"factor_id": factor_id, "shock": None,
                         "exposure": betas[factor_id], "contribution": None,
                         "state": "no_shock_supplied"})
            continue
        if isinstance(shock, bool) or not isinstance(shock, (int, float)) \
                or not math.isfinite(float(shock)):
            raise FactorError(
                f"the factor shock for '{factor_id}' must be a finite number")
        contribution = betas[factor_id] * float(shock)
        total += contribution
        rows.append({"factor_id": factor_id, "shock": float(shock),
                     "exposure": betas[factor_id],
                     "contribution": float(contribution), "state": "supplied"})
    warnings.append(
        "the factor-stress view multiplies measured exposures by SUPPLIED "
        "factor shocks; it is not a prediction of realised loss, no hedge or "
        "reallocation follows from it, and it is separate from the Phase 57 "
        "direct asset shocks, which are unchanged")
    return {
        "stress_identity": identity,
        "rows": rows,
        "total_contribution": float(total),
        "residual_component": None,
        "residual_note": (
            "the residual component of a factor-stress scenario is undefined: "
            "the fitted residual is a property of the observed sample, not of "
            "a hypothetical shock, so it is reported as unavailable"),
        "formula": "contribution_k = measured_exposure_k x supplied_shock_k",
        "comparability_warning": (
            "the shocks are expressed in each factor's TRANSFORMED unit; a "
            "shock in another unit would not be comparable"),
    }


def _attribution_linkage(run: Dict[str, Any], target: Dict[str, Any],
                         summary: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not run.get("attribution_run_id"):
        return None
    identity = target.get("source_identity") or {}
    return {
        "attribution_run_id": run["attribution_run_id"],
        "attribution_run_name": identity.get("attribution_run_name"),
        "column": identity.get("column"),
        "measured_return_sum": summary["measured_return_sum"],
        "modelled_return_sum": summary["modelled_return_sum"],
        "residual_sum": summary["residual_sum"],
        "reconciliation_difference": summary["reconciliation_difference"],
        "note": ("a complementary view: the Brinson decomposition explains the "
                 "same measured return by allocation and selection decisions, "
                 "this one by exposure to declared factors. They are not "
                 "interchangeable, neither overwrites the other, and the "
                 "residual here is not alpha"),
        "cost_note": ("transaction cost stays inside the attribution lab's "
                      "cost block and is never folded into a factor "
                      "contribution"),
    }


def _sensitivity_rows(configuration: Dict[str, Any], rebuilt: Dict[str, Any],
                      policy: Dict[str, Any],
                      tolerance: float,
                      membership: Dict[int, str]) -> List[Dict[str, Any]]:
    scenarios = configuration.get("sensitivity") or []
    target = rebuilt["target"]
    definitions = rebuilt["definitions"]
    observations = rebuilt["observations"]
    rows: List[Dict[str, Any]] = []
    for scenario in scenarios:
        entry: Dict[str, Any] = {
            "label": scenario["label"], "is_base": scenario["is_base"],
            "description": sens_mod.scenario_description(scenario),
            "regression_method": (
                "ridge" if scenario.get("ridge_lambda") is not None
                else policy["regression_method"]),
            "status": "computed", "reason": None, "coefficients": {},
        }
        try:
            subset = scenario.get("factor_subset") or [d["factor_id"]
                                                       for d in definitions]
            scenario_definitions = [
                {**d, "lag": d["lag"] + int(scenario.get("lag_delta") or 0)}
                for d in definitions if d["factor_id"] in set(subset)]
            if any(d["lag"] > defs_mod.MAX_LAG for d in scenario_definitions):
                raise defs_mod.DefinitionError(
                    f"sensitivity lag exceeds the supported maximum "
                    f"of {defs_mod.MAX_LAG}")
            alignment = obs_mod.align(
                target, scenario_definitions,
                {k: v for k, v in observations.items() if k in set(subset)},
                timing_policy=policy["timing_policy"],
                vintage_policy=policy["vintage_policy"],
                lead_periods=policy["lead_periods"])
            design_rows = alignment["rows"]
            if membership:
                design_rows = [
                    row for row in design_rows
                    if membership.get(row["period_index"]) == "train"]
            if scenario.get("lookback"):
                design_rows = design_rows[-int(scenario["lookback"]):]
            scale = float(scenario.get("factor_scale") or 1.0)
            y = [float(r["target_return"]) for r in design_rows]
            x = [[float(v) * scale for v in r["factor_values"]]
                 for r in design_rows]
            factor_ids = [d["factor_id"] for d in scenario_definitions]
            fit = _fit_design(
                y, x, factor_ids, policy,
                intercept_policy=scenario.get("intercept_policy"),
                method=entry["regression_method"],
                ridge_lambda=scenario.get("ridge_lambda"))
            period_rows = decomp_mod.regression_period_rows(
                design_rows, fit, factor_ids, tolerance,
                fit_residuals=fit["residuals"])
            summary = decomp_mod.summarise_periods(period_rows, factor_ids,
                                                   tolerance)
            entry.update({
                "observations": fit["observations"],
                "intercept": (float(fit["intercept"]["coefficient"])
                              if fit.get("intercept") else None),
                "r_squared": _finite_or_none(fit["r_squared"]),
                "adjusted_r_squared": _finite_or_none(
                    fit["adjusted_r_squared"]),
                "root_mean_squared_error": _finite_or_none(
                    fit["root_mean_squared_error"]),
                "residual_std": _finite_or_none(fit["residual_std"]),
                "condition_number": _finite_or_none(fit["condition_number"]),
                "rank": fit["rank"], "rank_status": fit["rank_status"],
                "reconciliation_state": summary["reconciliation_state"],
                "coefficients": {c["factor_id"]: float(c["coefficient"])
                                 for c in fit["coefficients"]},
            })
            entry["fingerprint"] = fp_mod.sensitivity_result_fingerprint(
                scenario, design_rows, fit, summary)
        except (reg_mod.RegressionError, obs_mod.ObservationError,
                decomp_mod.DecompositionError, defs_mod.DefinitionError) as exc:
            entry["status"] = "unavailable"
            entry["reason"] = str(exc)
        rows.append(entry)
    return rows


def _completeness(alignment: Dict[str, Any],
                  period_rows: List[Dict[str, Any]], fit: Dict[str, Any],
                  summary: Dict[str, Any]) -> str:
    if not period_rows or summary["periods_decomposed"] == 0:
        return "unavailable"
    if alignment["excluded_periods"] or summary["periods_unavailable"]:
        return "partial"
    if fit["method"] == "supplied_exposure_aggregation":
        return "complete"
    if fit["rank_status"] != "full_rank":
        return "partial"
    if fit["standard_error_state"] != "available" and fit["method"] == "ols":
        return "partial"
    return "complete"


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def invalidate_run(run_id: int, reason: str) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"factor diagnostics run {run_id} not found")
    if run["status"] == "invalidated":
        raise ConflictError("this run is already invalidated")
    store.update_run(run_id, {
        "status": "invalidated", "is_baseline": 0, "baseline_scope": None,
        "notes": (f"{run['notes']}\ninvalidated: {reason}").strip()[:2000]})
    return get_run(run_id)


def _baseline_scope(run: Dict[str, Any]) -> str:
    return "|".join([
        run["target_fingerprint"], run["observation_fingerprint"],
        run["model_policy_fingerprint"], run["return_frequency"],
        run["observation_start"] or "", run["observation_end"] or "",
    ])


def mark_baseline(run_id: int) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"factor diagnostics run {run_id} not found")
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
    if run["rank_status"] not in BASELINE_ACCEPTABLE_RANK:
        raise ConflictError(
            f"rank status '{run['rank_status']}' cannot become a comparison "
            f"baseline: the coefficients are not identified")
    if run["reconciliation_status"] != "reconciled":
        raise ConflictError(
            "the decomposition must reconcile before a run can become a "
            "comparison baseline")
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
    if a["target_fingerprint"] != b["target_fingerprint"]:
        warnings.append(
            "the two runs analyse DIFFERENT target series; coefficients are "
            "not comparable")
    if a["observation_fingerprint"] != b["observation_fingerprint"]:
        warnings.append(
            "the observation universes differ (sample, timing or factor "
            "definitions)")
    if a["model_policy_fingerprint"] != b["model_policy_fingerprint"]:
        warnings.append("the model policies differ (estimator or switches)")
    if a["analysis_mode"] != b["analysis_mode"]:
        warnings.append(
            f"different analysis modes ({a['analysis_mode']} vs "
            f"{b['analysis_mode']})")
    if a["timing_policy"] != b["timing_policy"]:
        warnings.append(
            f"different timing policies ({a['timing_policy']} vs "
            f"{b['timing_policy']}): a descriptive fit and a causal-timing fit "
            f"do not answer the same question")
    if a["return_frequency"] != b["return_frequency"]:
        warnings.append("different return frequencies")

    coefficients_a = {c["factor_id"]: c
                      for c in store.list_coefficients(a_id)}
    coefficients_b = {c["factor_id"]: c
                      for c in store.list_coefficients(b_id)}
    rows: List[Dict[str, Any]] = []
    for factor_id in sorted(set(coefficients_a) | set(coefficients_b)):
        left = coefficients_a.get(factor_id)
        right = coefficients_b.get(factor_id)
        difference = None
        if left and right and left["coefficient"] is not None \
                and right["coefficient"] is not None:
            difference = float(right["coefficient"] - left["coefficient"])
        rows.append({
            "factor_id": factor_id,
            "a_coefficient": (left or {}).get("coefficient"),
            "b_coefficient": (right or {}).get("coefficient"),
            "difference": difference,
            "a_present": left is not None, "b_present": right is not None,
        })
    return {
        "a_id": a_id, "b_id": b_id,
        "comparability_warnings": warnings,
        "coefficients": rows,
        "metrics": {
            "r_squared": {"a": a["r_squared"], "b": b["r_squared"]},
            "adjusted_r_squared": {"a": a["adjusted_r_squared"],
                                   "b": b["adjusted_r_squared"]},
            "root_mean_squared_error": {"a": a["root_mean_squared_error"],
                                        "b": b["root_mean_squared_error"]},
            "residual_std": {"a": a["residual_std"], "b": b["residual_std"]},
            "condition_number": {"a": a["condition_number"],
                                 "b": b["condition_number"]},
            "observations": {"a": a["observation_count"],
                             "b": b["observation_count"]},
            "held_out_r_squared": {"a": a["held_out_r_squared"],
                                   "b": b["held_out_r_squared"]},
        },
        "fingerprint_match": {
            "target": a["target_fingerprint"] == b["target_fingerprint"],
            "observation": (a["observation_fingerprint"]
                            == b["observation_fingerprint"]),
            "model_policy": (a["model_policy_fingerprint"]
                             == b["model_policy_fingerprint"]),
            "configuration": (a["configuration_fingerprint"]
                              == b["configuration_fingerprint"]),
            "result": (a["result_fingerprint"] == b["result_fingerprint"]
                       and a["result_fingerprint"] is not None),
        },
        "baseline": {"a": a["is_baseline"], "b": b["is_baseline"]},
        "note": ("differences are reported neutrally: no run is better, "
                 "superior, preferred or recommended, and no factor set is "
                 "endorsed"),
    }


def export(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    page = store.list_runs(filters=filters or {}, page=1,
                           page_size=MAX_EXPORT_RUNS)
    runs: List[Dict[str, Any]] = []
    for row in page["items"]:
        run = _hydrate(row)
        run_id = run["id"]
        runs.append({
            "run": {k: v for k, v in run.items()
                    if k not in ("configuration",)},
            "configuration": {k: v for k, v in (run.get("configuration") or {}).items()
                              if k != "factors"},
            "factor_definitions": store.list_definitions(run_id),
            "observations": store.list_observations(run_id),
            "coefficients": store.list_coefficients(run_id),
            "periods": store.list_periods(run_id),
            "rolling": store.list_rolling(run_id),
            "regimes": store.list_regimes(run_id),
            "sensitivity": store.list_sensitivity(run_id),
        })
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "exported_at": store._now(),
        "filters": filters or {},
        "run_count": len(runs),
        "runs": runs,
        "limits": {"max_runs": MAX_EXPORT_RUNS},
        "disclaimer": (
            "Measured sensitivities under explicit, stated assumptions. "
            "Nothing here proves causality, proves alpha, predicts returns, "
            "recommends a factor exposure, a macro trade or a portfolio, or "
            "constitutes investment advice."),
    }


__all__ = [
    "FactorError", "NotFoundError", "ConflictError", "InternalExecutionError",
    "EXECUTION_ORDER", "RARE_REGIME_MIN_OBSERVATIONS",
    "MULTIPLE_TESTING_METHODS", "create_run", "get_run", "list_runs",
    "lab_summary", "execute_run", "invalidate_run", "mark_baseline",
    "compare_runs", "export",
]
