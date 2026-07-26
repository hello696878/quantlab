"""
Service layer for the Portfolio Diagnostics Lab (v1).

Eager validation at create; deterministic execution from the stored
universe and configuration; read-only links to prior registries (nothing
mutates their rows, memberships or fingerprints); failed executions are
recorded — never left running; generated weights are never applied
anywhere outside this research record.

Integrity states: ``verified_from_validation_split`` (training-only
estimation on a leakage-clean validation split's recorded membership),
``verified_causal_rolling`` (rolling/expanding estimation with lag >= 1),
``declared`` (user-supplied weights with declared provenance),
``full_sample_descriptive`` (whole-sample estimation — descriptive only,
never leakage-safe), ``unknown``, ``invalid`` (a future-looking
provenance claim).  Structural constraint infeasibility is rejected at
create (422); solve-time failures and post-solve violations are stored
honestly and block baselines.
"""

from __future__ import annotations

import json
import logging
import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.dataset_registry import store as dataset_store
from app.experiment_registry import integration as experiment_integration
from app.experiment_registry import store as experiment_store
from app.experiment_registry.provenance import get_app_version, get_git_commit
from app.model_validation import store as validation_store
from app.overfitting_diagnostics import store as overfitting_store
from app.regime_diagnostics import store as regime_store
from app.cost_diagnostics import store as cost_store
from app.portfolio_diagnostics import EXPORT_SCHEMA_VERSION
from app.portfolio_diagnostics import constraints as cons_mod
from app.portfolio_diagnostics import costs as costs_mod
from app.portfolio_diagnostics import covariance as cov_mod
from app.portfolio_diagnostics import fingerprints as fp_mod
from app.portfolio_diagnostics import methods as methods_mod
from app.portfolio_diagnostics import rebalance as reb_mod
from app.portfolio_diagnostics import risk as risk_mod
from app.portfolio_diagnostics import sensitivity as sens_mod
from app.portfolio_diagnostics.core import (
    PortfolioInputError,
    normalize_assets,
    normalize_benchmark,
    normalize_prior_weights,
    normalize_timeline,
)


logger = logging.getLogger(__name__)


class PortfolioDiagnosticsError(ValueError):
    """Invalid input/config (HTTP 422)."""


class InternalExecutionError(RuntimeError):
    """Sanitized unexpected execution failure (HTTP 500)."""


class NotFoundError(LookupError):
    """Unknown id (HTTP 404)."""


class ConflictError(RuntimeError):
    """State conflict (HTTP 409)."""


BASELINE_ACCEPTABLE_INTEGRITY = (
    "verified_from_validation_split", "verified_causal_rolling", "declared",
)
BASELINE_ACCEPTABLE_SOLVER = ("closed_form", "converged", "converged_loose")
RARE_REGIME_MIN_OBSERVATIONS = 8
USER_PROVENANCE_BASES = ("causal_rolling", "declared", "full_sample",
                         "centered", "unknown")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


from app.portfolio_diagnostics import store  # noqa: E402


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def _validate_budgets(raw: Any, assets: List[Dict[str, Any]],
                      method: str) -> Optional[Dict[str, float]]:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise PortfolioInputError("risk_budgets must be an object")
    known = [a["asset_id"] for a in assets]
    out: Dict[str, float] = {}
    for k, v in raw.items():
        if k not in known:
            raise PortfolioInputError(f"risk budget references unknown asset {k!r}")
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise PortfolioInputError("risk budgets must be numbers")
        f = float(v)
        if not math.isfinite(f):
            raise PortfolioInputError("risk budgets must be finite")
        if f < 0:
            raise PortfolioInputError("risk budgets must be non-negative")
        out[k] = f
    total = sum(out.values())
    if abs(total - 1.0) > 1e-6:
        raise PortfolioInputError("risk budgets must sum to one")
    if method == "erc":
        if any(v <= 0 for v in out.values()):
            raise PortfolioInputError("ERC risk budgets must be positive")
        missing = [a for a in known if a not in out]
        if missing:
            raise PortfolioInputError(
                "ERC risk budgets must cover every asset; missing: "
                + ", ".join(missing[:5]))
    return {a: out.get(a, 0.0) for a in known}


def _validate_solver_config(raw: Any) -> Dict[str, Any]:
    if raw is None:
        cfg: Dict[str, Any] = {}
    elif not isinstance(raw, dict):
        raise PortfolioInputError("solver configuration must be an object")
    else:
        cfg = dict(raw)
    tol = cfg.get("tolerance", methods_mod.ERC_DEFAULT_TOLERANCE)
    try:
        tol = float(tol)
    except (TypeError, ValueError):
        raise PortfolioInputError("solver tolerance must be a number")
    if not math.isfinite(tol) or not (1e-10 <= tol <= 0.1):
        raise PortfolioInputError("solver tolerance must be in [1e-10, 0.1]")
    max_iter = cfg.get("max_iterations", methods_mod.ERC_MAX_ITERATIONS)
    if isinstance(max_iter, bool) or not isinstance(max_iter, int) or not (
            10 <= max_iter <= 10_000):
        raise PortfolioInputError(
            "solver max_iterations must be an integer in [10, 10000]")
    return {"tolerance": tol, "max_iterations": max_iter}


def _validate_links(payload: Dict[str, Any]) -> Dict[str, Any]:
    links: Dict[str, Any] = {}
    if payload.get("dataset_version_id") is not None:
        version = dataset_store.get_version(payload["dataset_version_id"])
        if version is None:
            raise PortfolioDiagnosticsError(
                f"dataset version {payload['dataset_version_id']} not found")
        links["dataset_version_id"] = version["id"]
        links["dataset_manifest_fingerprint"] = version["manifest_fingerprint"]
    if payload.get("validation_run_id") is not None:
        vrun = validation_store.get_run(payload["validation_run_id"])
        if vrun is None:
            raise PortfolioDiagnosticsError(
                f"validation run {payload['validation_run_id']} not found")
        links["validation_run_id"] = vrun["id"]
        links["validation_configuration_fingerprint"] = \
            vrun["configuration_fingerprint"]
        links["validation_result_fingerprint"] = vrun.get("result_fingerprint")
        split_label = payload.get("validation_split_label")
        if split_label is not None:
            if vrun["status"] != "completed" \
                    or vrun.get("leakage_clean") is not True:
                raise PortfolioDiagnosticsError(
                    "training-only estimation requires a completed, "
                    "leakage-clean validation run")
            split = next(
                (s for s in validation_store.list_splits(vrun["id"])
                 if s["split_label"] == split_label), None)
            if split is None or split["status"] != "valid":
                raise PortfolioDiagnosticsError(
                    f"validation split {split_label!r} not found or not valid")
            links["validation_split_fingerprint"] = split["split_fingerprint"]
    if payload.get("regime_run_id") is not None:
        rrun = regime_store.get_run(payload["regime_run_id"])
        if rrun is None:
            raise PortfolioDiagnosticsError(
                f"regime run {payload['regime_run_id']} not found")
        if rrun["status"] != "completed":
            raise PortfolioDiagnosticsError(
                "regime integration requires a completed regime run")
        definition_id = payload.get("regime_definition_id")
        if not definition_id:
            raise PortfolioDiagnosticsError(
                "regime integration requires regime_definition_id")
        definition = next(
            (d for d in regime_store.list_definitions(rrun["id"])
             if d["definition_id"] == definition_id), None)
        if definition is None:
            raise PortfolioDiagnosticsError(
                f"regime definition {definition_id!r} not found in run "
                f"{rrun['id']}")
        links["regime_run_id"] = rrun["id"]
        links["regime_definition_id"] = definition_id
        links["regime_configuration_fingerprint"] = \
            rrun["configuration_fingerprint"]
        links["regime_result_fingerprint"] = rrun.get("result_fingerprint")
        links["regime_definition_fingerprint"] = \
            definition["definition_fingerprint"]
    elif payload.get("regime_definition_id"):
        raise PortfolioDiagnosticsError(
            "regime_definition_id requires regime_run_id")
    if payload.get("cost_diagnostic_run_id") is not None:
        crun = cost_store.get_run(payload["cost_diagnostic_run_id"])
        if crun is None:
            raise PortfolioDiagnosticsError(
                f"cost-diagnostic run {payload['cost_diagnostic_run_id']} "
                "not found")
        if cost_store.get_cost_model(crun["id"]) is None:
            raise PortfolioDiagnosticsError(
                "the linked cost-diagnostic run stores no cost model")
        links["cost_diagnostic_run_id"] = crun["id"]
        links["cost_model_fingerprint"] = crun["cost_model_fingerprint"]
        links["cost_configuration_fingerprint"] = \
            crun["configuration_fingerprint"]
        links["cost_result_fingerprint"] = crun.get("result_fingerprint")
    if payload.get("overfitting_run_id") is not None:
        orun = overfitting_store.get_run(payload["overfitting_run_id"])
        if orun is None:
            raise PortfolioDiagnosticsError(
                f"overfitting run {payload['overfitting_run_id']} not found")
        links["overfitting_run_id"] = orun["id"]
        links["overfitting_universe_fingerprint"] = orun["universe_fingerprint"]
        links["overfitting_configuration_fingerprint"] = \
            orun["configuration_fingerprint"]
        links["overfitting_result_fingerprint"] = orun.get("result_fingerprint")
    if payload.get("experiment_id") is not None:
        exp = experiment_store.get_experiment(payload["experiment_id"])
        if exp is None:
            raise PortfolioDiagnosticsError(
                f"experiment {payload['experiment_id']} not found")
        links["experiment_id"] = exp["id"]
    return links


def create_run(payload: Dict[str, Any], *, demo_key: Optional[str] = None) -> Dict[str, Any]:
    name = (payload.get("name") or "").strip()
    if not name or len(name) > 200:
        raise PortfolioDiagnosticsError("name must be 1..200 characters")
    method = payload.get("method")
    if method in methods_mod.DEFERRED_METHODS:
        raise PortfolioDiagnosticsError(
            f"method {method!r} is {methods_mod.DEFERRED_METHODS[method]}")
    if method not in methods_mod.METHODS:
        raise PortfolioDiagnosticsError(
            f"method must be one of {', '.join(methods_mod.METHODS)}")
    try:
        timeline = normalize_timeline(payload.get("timestamps"),
                                      payload.get("frequency"))
        n_periods = len(timeline["timestamps"])
        assets = normalize_assets(payload.get("assets"), n_periods)
        benchmark = normalize_benchmark(payload.get("benchmark_returns"),
                                        n_periods)
        prior_weights = normalize_prior_weights(payload.get("prior_weights"),
                                                assets)
        estimation = reb_mod.validate_estimation_config(payload.get("estimation"))
        cov_config = cov_mod.validate_covariance_config(payload.get("covariance"))
        constraints = cons_mod.validate_constraints(payload.get("constraints"),
                                                    assets)
        rebalance_policy = reb_mod.validate_rebalance_policy(
            payload.get("rebalance"), timeline["timestamps"])
        budgets = _validate_budgets(payload.get("risk_budgets"), assets, method)
        solver_config = _validate_solver_config(payload.get("solver"))
        sensitivity_config = sens_mod.validate_sensitivity_config(
            payload.get("sensitivity"))
    except (PortfolioInputError, cov_mod.CovarianceError,
            cons_mod.ConstraintError, methods_mod.MethodError) as exc:
        raise PortfolioDiagnosticsError(str(exc))

    if constraints["frozen_weights"] and method not in ("user_supplied",
                                                        "min_variance"):
        raise PortfolioDiagnosticsError(
            "frozen weights are supported only for user_supplied and "
            "min_variance in v1 (documented)")
    if method == "erc":
        if not constraints["long_only"]:
            raise PortfolioDiagnosticsError(
                "ERC is supported for long-only portfolios in v1")
        # the v1 ERC solver is constraint-free beyond long-only/sum-1, so
        # configurations it is structurally guaranteed to violate are
        # rejected eagerly rather than failing post-solve every time
        if constraints["excluded_assets"]:
            raise PortfolioDiagnosticsError(
                "ERC assigns positive weight to every asset in v1; "
                "excluded_assets are structurally incompatible — remove the "
                "assets from the universe instead")
        if constraints["net_exposure_target"] not in (None, 1.0):
            raise PortfolioDiagnosticsError(
                "ERC always normalizes to a net exposure of 1 in v1")
        if constraints["min_weight"] > 0:
            raise PortfolioDiagnosticsError(
                "ERC does not enforce a positive min_weight in v1; the "
                "independent check would flag it on every rebalance")

    user_weights = None
    user_provenance = None
    normalization = payload.get("normalization") or "sum_to_one"
    if normalization not in methods_mod.NORMALIZATION_POLICIES:
        raise PortfolioDiagnosticsError(
            "normalization must be one of "
            f"{', '.join(methods_mod.NORMALIZATION_POLICIES)}")
    if method == "user_supplied":
        raw_w = payload.get("weights")
        if not isinstance(raw_w, dict) or not raw_w:
            raise PortfolioDiagnosticsError(
                "user_supplied requires a weights object")
        known = {a["asset_id"] for a in assets}
        user_weights = {}
        for k, v in raw_w.items():
            if k not in known:
                raise PortfolioDiagnosticsError(
                    f"weights reference unknown asset {k!r}")
            if isinstance(v, bool) or not isinstance(v, (int, float)) \
                    or not math.isfinite(float(v)):
                raise PortfolioDiagnosticsError("weights must be finite numbers")
            user_weights[k] = float(v)
        raw_provenance = payload.get("weight_provenance")
        if raw_provenance is None:
            provenance: Dict[str, Any] = {}
        elif not isinstance(raw_provenance, dict):
            raise PortfolioDiagnosticsError(
                "weight_provenance must be an object")
        else:
            provenance = dict(raw_provenance)
        basis = provenance.get("basis", "unknown")
        if basis not in USER_PROVENANCE_BASES:
            raise PortfolioDiagnosticsError(
                "weight_provenance.basis must be one of "
                f"{', '.join(USER_PROVENANCE_BASES)}")
        lag_claim = provenance.get("lag")
        if lag_claim is not None and (isinstance(lag_claim, bool)
                                      or not isinstance(lag_claim, int)):
            raise PortfolioDiagnosticsError(
                "weight_provenance.lag must be an integer")
        user_provenance = {"basis": basis, "lag": lag_claim}
        if normalization not in methods_mod.NORMALIZATION_POLICIES:
            raise PortfolioDiagnosticsError(
                "normalization must be one of "
                f"{', '.join(methods_mod.NORMALIZATION_POLICIES)}")

    # training-only estimation via a validation split needs sample ids
    split_label = payload.get("validation_split_label")
    sample_ids = payload.get("sample_ids")
    if split_label is not None:
        if payload.get("validation_run_id") is None:
            raise PortfolioDiagnosticsError(
                "validation_split_label requires validation_run_id")
        if not isinstance(sample_ids, list) or len(sample_ids) != n_periods:
            raise PortfolioDiagnosticsError(
                "training-only estimation requires sample_ids aligned to "
                "the timeline")
        if estimation["mode"] == "full_sample":
            raise PortfolioDiagnosticsError(
                "training-only estimation cannot use full_sample mode — a "
                "whole-sample window would let traded periods inform their "
                "own weights; use rolling or expanding estimation")
    if sample_ids is not None:
        if not isinstance(sample_ids, list) or len(sample_ids) != n_periods:
            raise PortfolioDiagnosticsError(
                "sample_ids must be a list aligned to the timeline")
        if any(not isinstance(sample_id, str) or not sample_id.strip()
               for sample_id in sample_ids):
            raise PortfolioDiagnosticsError(
                "sample_ids must contain non-empty strings")
        sample_ids = [sample_id.strip() for sample_id in sample_ids]
        if len(set(sample_ids)) != len(sample_ids):
            raise PortfolioDiagnosticsError("sample_ids must be unique")
    # cross-checks the eager-validation contract requires
    if rebalance_policy["initial_turnover_policy"] == "supplied" \
            and prior_weights is None:
        raise PortfolioDiagnosticsError(
            "initial_turnover_policy 'supplied' requires prior_weights")
    try:
        reb_mod.rebalance_indices(rebalance_policy, estimation, n_periods)
    except PortfolioInputError as exc:
        raise PortfolioDiagnosticsError(str(exc))
    for cap in sensitivity_config.get("max_weight", []):
        if cap < constraints["min_weight"]:
            raise PortfolioDiagnosticsError(
                f"sensitivity max_weight value {cap:g} is below the "
                f"configured min_weight {constraints['min_weight']:g}")
        for fw in constraints["frozen_weights"].values():
            if fw > cap:
                raise PortfolioDiagnosticsError(
                    f"sensitivity max_weight value {cap:g} conflicts with a "
                    "frozen weight above it")
    if sensitivity_config.get("lookback") and estimation["mode"] != "rolling":
        raise PortfolioDiagnosticsError(
            "sensitivity lookback applies only to rolling estimation — the "
            f"configured mode is {estimation['mode']!r}")
    if sensitivity_config.get("shrinkage_alpha") \
            and cov_config["method"] != "fixed_shrinkage":
        raise PortfolioDiagnosticsError(
            "sensitivity shrinkage_alpha applies only to fixed_shrinkage "
            f"covariance — the configured method is {cov_config['method']!r}")
    links = _validate_links(payload)

    volatility_floor = payload.get("volatility_floor")
    if volatility_floor is not None:
        try:
            volatility_floor = float(volatility_floor)
        except (TypeError, ValueError):
            raise PortfolioDiagnosticsError("volatility_floor must be a number")
        if not math.isfinite(volatility_floor) or not (
                0 < volatility_floor <= 1):
            raise PortfolioDiagnosticsError(
                "volatility_floor must be in (0, 1]")
    notional = payload.get("cost_notional")
    if notional is not None:
        try:
            notional = float(notional)
        except (TypeError, ValueError):
            raise PortfolioDiagnosticsError("cost_notional must be a number")
        if not math.isfinite(notional) or notional <= 0:
            raise PortfolioDiagnosticsError("cost_notional must be > 0")

    universe = {
        "timestamps": timeline["timestamps"],
        "frequency": timeline["frequency"],
        "assets": assets,
        "benchmark_returns": benchmark,
        "prior_weights": prior_weights,
        "sample_ids": sample_ids,
    }
    universe_fp = fp_mod.universe_fingerprint(
        assets, timeline["timestamps"], timeline["frequency"], benchmark,
        {"dataset_version_id": links.get("dataset_version_id"),
         "manifest_fingerprint": links.get("dataset_manifest_fingerprint")},
        candidate_fingerprints=(
            [links["overfitting_universe_fingerprint"]]
            if links.get("overfitting_universe_fingerprint") else None),
        sample_ids=universe["sample_ids"], prior_weights=prior_weights)
    constraint_fp = fp_mod.constraint_fingerprint(constraints)
    linked_identity = {
        k: v for k, v in links.items() if k != "experiment_id"
    }
    configuration = {
        "method": method,
        "covariance": cov_config,
        "estimation": estimation,
        "constraints": constraints,
        "normalization": normalization,
        "risk_budgets": budgets,
        "rebalance": rebalance_policy,
        "solver": solver_config,
        "sensitivity": sensitivity_config,
        "volatility_floor": volatility_floor,
        "cost_notional": notional,
        "validation_split_label": split_label,
        "user_weights": user_weights,
        "user_provenance": user_provenance,
        "deferred_methods": methods_mod.DEFERRED_METHODS,
        "linked_fingerprints": linked_identity,
        "turnover_convention": "one_way_turnover = 0.5 x sum |w_new - w_old|",
        "no_lookahead_policy": (
            "weights effective for period i use returns through i - lag "
            "only (lag >= 1); centered windows and negative lags rejected; "
            "full-sample estimation is descriptive and never leakage-safe"),
    }
    config_fp = fp_mod.configuration_fingerprint(
        universe_fp, method, cov_config, estimation, constraint_fp, budgets,
        rebalance_policy, solver_config, sensitivity_config, linked_identity,
        execution_inputs={
            "normalization": normalization,
            "volatility_floor": volatility_floor,
            "cost_notional": notional,
            "validation_split_label": split_label,
            "user_weights": user_weights,
            "user_provenance": user_provenance,
        })

    run = store.insert_run({
        "name": name, "description": payload.get("description", ""),
        "method": method, "covariance_method": cov_config["method"],
        "asset_count": len(assets), "observation_count": n_periods,
        "universe_fingerprint": universe_fp,
        "constraint_fingerprint": constraint_fp,
        "configuration": configuration,
        "configuration_fingerprint": config_fp,
        "universe": universe,
        "dataset_version_id": links.get("dataset_version_id"),
        "validation_run_id": links.get("validation_run_id"),
        "regime_run_id": links.get("regime_run_id"),
        "regime_definition_id": links.get("regime_definition_id"),
        "cost_diagnostic_run_id": links.get("cost_diagnostic_run_id"),
        "overfitting_run_id": links.get("overfitting_run_id"),
        "experiment_id": links.get("experiment_id"),
        "app_version": get_app_version(), "git_commit": get_git_commit(),
        "notes": payload.get("notes", ""), "demo_key": demo_key,
    })
    return get_run(run["id"])


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def get_run(run_id: int) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"portfolio-diagnostic run {run_id} not found")
    return _hydrate(run)


def _hydrate(run: Dict[str, Any]) -> Dict[str, Any]:
    run["dataset_name"] = run["dataset_version_label"] = None
    run["dataset_invalidated"] = None
    run["dataset_manifest_fingerprint"] = None
    run["dataset_provenance_status"] = run["dataset_quality_status"] = None
    run["validation_method"] = run["validation_leakage_clean"] = None
    run["validation_config_fp"] = None
    run["regime_run_name"] = run["regime_run_integrity"] = None
    run["cost_run_name"] = run["cost_model_fingerprint"] = None
    run["overfitting_name"] = run["overfitting_pbo"] = None
    run["overfitting_universe_fp"] = None
    run["experiment_name"] = None
    if run.get("dataset_version_id"):
        version = dataset_store.get_version(run["dataset_version_id"])
        if version:
            dataset = dataset_store.get_dataset(version["dataset_id"])
            run["dataset_name"] = dataset["name"] if dataset else None
            run["dataset_version_label"] = version["version_label"]
            run["dataset_invalidated"] = bool(version.get("invalidated_at"))
            run["dataset_manifest_fingerprint"] = version["manifest_fingerprint"]
            run["dataset_provenance_status"] = dataset["provenance_status"] if dataset else None
            run["dataset_quality_status"] = version["quality_status"]
    if run.get("validation_run_id"):
        vrun = validation_store.get_run(run["validation_run_id"])
        if vrun:
            run["validation_method"] = vrun["method"]
            run["validation_leakage_clean"] = vrun.get("leakage_clean")
            run["validation_config_fp"] = vrun["configuration_fingerprint"]
    if run.get("regime_run_id"):
        rrun = regime_store.get_run(run["regime_run_id"])
        if rrun:
            run["regime_run_name"] = rrun["name"]
            run["regime_run_integrity"] = rrun["integrity_status"]
    if run.get("cost_diagnostic_run_id"):
        crun = cost_store.get_run(run["cost_diagnostic_run_id"])
        if crun:
            run["cost_run_name"] = crun["name"]
            run["cost_model_fingerprint"] = crun["cost_model_fingerprint"]
    if run.get("overfitting_run_id"):
        orun = overfitting_store.get_run(run["overfitting_run_id"])
        if orun:
            run["overfitting_name"] = orun["name"]
            run["overfitting_pbo"] = orun.get("pbo_estimate")
            run["overfitting_universe_fp"] = orun["universe_fingerprint"]
    if run.get("experiment_id"):
        exp = experiment_store.get_experiment(run["experiment_id"])
        run["experiment_name"] = exp["name"] if exp else None
    return run


def list_runs(**kwargs: Any) -> Dict[str, Any]:
    result = store.list_runs(**kwargs)
    result["items"] = [_hydrate(r) for r in result["items"]]
    return result


def lab_summary() -> Dict[str, Any]:
    return store.lab_summary()


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def _resolve_train_indices(run: Dict[str, Any]) -> Optional[set]:
    """Training-only membership (exact; mirrors the Phase 54 gates)."""
    config = run["configuration"]
    split_label = config.get("validation_split_label")
    if split_label is None:
        return None
    vrun = validation_store.get_run(run["validation_run_id"])
    if vrun is None or vrun["status"] != "completed" \
            or vrun.get("leakage_clean") is not True:
        raise PortfolioDiagnosticsError(
            "training-only estimation requires a completed, leakage-clean "
            "validation run")
    splits = validation_store.list_splits(run["validation_run_id"])
    split = next((s for s in splits if s["split_label"] == split_label), None)
    if split is None or split["status"] != "valid":
        raise PortfolioDiagnosticsError(
            f"validation split {split_label!r} not found or not valid")
    known = set()
    for s in splits:
        known.update(s["train_ids"])
        known.update(s["test_ids"])
        known.update(s["purged_ids"])
        known.update(s["embargoed_ids"])
    sample_ids = run["universe"]["sample_ids"]
    unknown = [sid for sid in sample_ids if sid not in known]
    if unknown:
        raise PortfolioDiagnosticsError(
            f"{len(unknown)} sample id(s) have no recorded split membership")
    train = set(split["train_ids"])
    return {i for i, sid in enumerate(sample_ids) if sid in train}


def _construct_at(run: Dict[str, Any], decision_index: int,
                  matrix: np.ndarray, asset_ids: List[str],
                  assets: List[Dict[str, Any]],
                  train_indices: Optional[set],
                  overrides: Optional[Dict[str, Any]] = None
                  ) -> Dict[str, Any]:
    """One weight construction at a decision index (used by rebalances and
    sensitivity scenarios).  Returns a record with weights/solver/cov info
    or an unavailable status with a reason."""
    config = run["configuration"]
    overrides = overrides or {}
    estimation = dict(config["estimation"])
    if "lookback" in overrides and estimation["mode"] == "rolling":
        estimation["lookback"] = overrides["lookback"]
    cov_config = dict(config["covariance"])
    if "shrinkage_alpha" in overrides and cov_config["method"] == "fixed_shrinkage":
        cov_config["alpha"] = overrides["shrinkage_alpha"]
    constraints = dict(config["constraints"])
    if "max_weight" in overrides:
        constraints = dict(constraints)
        constraints["max_weight"] = overrides["max_weight"]

    n_periods = matrix.shape[1]
    window = reb_mod.estimation_window(decision_index, estimation, n_periods)
    if window is None:
        return {"status": "unavailable",
                "reason": "insufficient history for the estimation window",
                "weights": None, "solver": {"status": "unavailable"}}
    start, end = window
    indices = list(range(start, end + 1))
    if train_indices is not None:
        indices = [i for i in indices if i in train_indices]
        if len(indices) < cov_mod.MIN_COVARIANCE_SAMPLES:
            return {"status": "unavailable",
                    "reason": "too few training-member observations in the "
                              "permitted window",
                    "weights": None, "solver": {"status": "unavailable"}}
    window_data = matrix[:, indices].T  # obs x assets
    estimation_input_fp = fp_mod.estimation_input_fingerprint(
        asset_ids, run["universe"]["timestamps"], indices,
        matrix.tolist())


    try:
        cov = cov_mod.estimate_covariance(window_data, cov_config)
    except cov_mod.CovarianceError as exc:
        return {"status": "failed", "reason": str(exc), "weights": None,
                "solver": {"status": "failed", "reason": str(exc)}}
    if overrides.get("correlation_multiplier") is not None \
            or overrides.get("volatility_multiplier") is not None:
        vol_mults = None
        if overrides.get("volatility_multiplier") is not None:
            vol_mults = [overrides["volatility_multiplier"]] * len(asset_ids)
        stressed = cov_mod.stress_covariance(
            cov, correlation_multiplier=overrides.get("correlation_multiplier"),
            volatility_multipliers=vol_mults)
        if stressed["matrix"] is None:
            return {"status": "unavailable", "reason": stressed["note"],
                    "weights": None, "solver": {"status": "unavailable"}}
        cov = stressed["matrix"]

    report = cov_mod.validate_matrix(cov)
    repair = cov_mod.repair_matrix(cov, cov_config)
    if repair["repaired"]:
        cov = repair["matrix"]
        report_after = cov_mod.validate_matrix(cov)
    else:
        report_after = report
    if not report_after.get("psd", False):
        return {"status": "failed",
                "reason": "covariance is not positive semidefinite and the "
                          "repair policy is "
                          f"{cov_config.get('repair', 'none')!r} — no silent "
                          "repair",
                "weights": None, "covariance_report": report,
                "repair": repair,
                "solver": {"status": "failed",
                           "reason": "invalid covariance"}}

    method = config["method"]
    excluded = constraints["excluded_assets"]
    target = constraints.get("net_exposure_target")
    if target is None:
        target = 1.0
    if method == "equal_weight":
        result = methods_mod.equal_weight(asset_ids, excluded,
                                          target_sum=target)
    elif method == "inverse_volatility":
        vols = {a: float(np.std(window_data[:, i], ddof=1))
                for i, a in enumerate(asset_ids)}
        result = methods_mod.inverse_volatility(
            asset_ids, vols, excluded,
            volatility_floor=config.get("volatility_floor"),
            target_sum=target)
    elif method == "erc":
        result = methods_mod.erc(
            cov, asset_ids, config.get("risk_budgets"),
            tolerance=config["solver"]["tolerance"],
            max_iterations=config["solver"]["max_iterations"])
    elif method == "min_variance":
        groups = {a["asset_id"]: a.get("group") for a in assets}
        result = methods_mod.min_variance(
            cov, asset_ids, constraints, asset_groups=groups,
            max_iterations=config["solver"]["max_iterations"])
    else:  # user_supplied
        norm = methods_mod.normalize_weights(
            config["user_weights"], config["normalization"],
            net_target=target)
        if norm["status"] != "available":
            result = {"weights": None,
                      "solver": {"status": "failed", "reason": norm["reason"]}}
        else:
            result = {"weights": {a: norm["weights"].get(a, 0.0)
                                  for a in asset_ids},
                      "raw_weights": norm["raw_weights"],
                      "normalization_residual": norm["residual"],
                      "solver": {"status": "closed_form", "iterations": 0,
                                 "residual": 0.0, "reason": None}}
    record: Dict[str, Any] = {
        "status": "completed" if result.get("weights") is not None else "failed",
        "reason": result.get("solver", {}).get("reason"),
        "weights": result.get("weights"),
        "raw_weights": result.get("raw_weights"),
        "solver": result.get("solver", {}),
        "covariance": cov,
        "covariance_report": report,
        "covariance_report_after_repair": report_after,
        "repair": repair,
        "window": [start, end],
        "window_indices_used": len(indices),
        "estimation_input_fingerprint": estimation_input_fp,
        "constraints_used": constraints,
        "unavailable_assets": result.get("unavailable_assets"),
        "floored_assets": result.get("floored_assets"),
    }
    return record


def execute_run(run_id: int, *, create_experiment: bool = False) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"portfolio-diagnostic run {run_id} not found")
    if run["status"] == "invalidated":
        raise ConflictError("run is invalidated; create a new run instead")
    t0 = time.monotonic()
    store.update_run(run_id, {"status": "running", "error_message": None})
    try:
        return _execute_body(run_id, run, t0, create_experiment)
    except (NotFoundError, ConflictError):
        raise
    except (PortfolioDiagnosticsError, PortfolioInputError,
            cov_mod.CovarianceError, cons_mod.ConstraintError,
            methods_mod.MethodError, fp_mod.FingerprintError) as exc:
        # A failed re-execution can no longer satisfy the baseline gates.
        store.update_run(run_id, {"status": "failed",
                                  "error_message": str(exc),
                                  "is_baseline": 0,
                                  "completed_at": _now()})
        raise PortfolioDiagnosticsError(f"execution failed: {exc}") from exc
    except Exception as exc:
        logger.exception("unexpected portfolio-diagnostics execution failure")
        message = "execution failed due to an internal computation or persistence error"
        try:
            store.update_run(run_id, {"status": "failed",
                                      "error_message": message,
                                      "is_baseline": 0,
                                      "completed_at": _now()})
        except Exception:
            logger.exception("could not persist portfolio-diagnostics failure state")
        raise InternalExecutionError(message) from exc

def _execute_body(run_id: int, run: Dict[str, Any], t0: float,
                  create_experiment: bool) -> Dict[str, Any]:
    config = run["configuration"]
    universe = run["universe"]
    assets = universe["assets"]
    asset_ids = [a["asset_id"] for a in assets]
    timestamps = universe["timestamps"]
    n_periods = len(timestamps)
    matrix = np.array([a["returns"] for a in assets], dtype=float)
    train_indices = _resolve_train_indices(run)

    warnings: List[str] = []
    integrity = _integrity_state(config, train_indices)
    if integrity == "full_sample_descriptive":
        warnings.append("full-sample estimation is descriptive only and "
                        "never leakage-safe")
    if integrity == "invalid":
        warnings.append("user-supplied weights claim a centered or "
                        "future-looking estimation basis; the run is invalid "
                        "as causal evidence")

    cost_model = None
    if run.get("cost_diagnostic_run_id"):
        cost_model = cost_store.get_cost_model(run["cost_diagnostic_run_id"])

    indices = reb_mod.rebalance_indices(config["rebalance"],
                                        config["estimation"], n_periods)
    rebalances: List[Dict[str, Any]] = []
    prior = universe.get("prior_weights") \
        if config["rebalance"]["initial_turnover_policy"] == "supplied" else None
    prev_weights: Optional[Dict[str, float]] = prior
    prev_effective_index: Optional[int] = None
    last_success: Optional[Dict[str, Any]] = None
    for rb_id, i in enumerate(indices):
        record = _construct_at(run, i, matrix, asset_ids, assets,
                               train_indices)
        for key, label in (("floored_assets", "volatility floor applied to"),
                           ("unavailable_assets", "volatility unavailable for")):
            entries = record.get(key)
            if entries:
                ids = [e["asset_id"] if isinstance(e, dict) else e
                       for e in entries]
                note = (f"rebalance {rb_id}: {label} "
                        + ", ".join(sorted(ids)))
                if note not in warnings:
                    warnings.append(note)
        turnover = None
        violations: List[Dict[str, Any]] = []
        cost = None
        pre_trade_weights = prev_weights
        if prev_weights is not None and prev_effective_index is not None:
            pre_trade_weights = reb_mod.drift_weights(
                prev_weights, asset_ids, matrix, prev_effective_index, i)
            if pre_trade_weights is None:
                warnings.append(
                    f"rebalance {rb_id}: pre-trade weights are unavailable "
                    "because the prior book reached a non-positive or "
                    "non-finite value; turnover and cost remain unavailable")
        if record.get("weights") is not None:
            if pre_trade_weights is not None or prev_weights is None:
                turnover = reb_mod.one_way_turnover(
                    pre_trade_weights, record["weights"],
                    config["rebalance"]["initial_turnover_policy"])
            violations = cons_mod.check_weights(
                record["weights"], config["constraints"], assets,
                turnover=turnover)
            if cost_model is not None:
                cost = costs_mod.estimate_rebalance_cost(
                    turnover, cost_model, config.get("cost_notional"))
        rb = {
            "rebalance_id": rb_id,
            "decision_index": i,
            "decision_timestamp": timestamps[i],
            "effective_timestamp": timestamps[i],
            "window_start": record.get("window", [None, None])[0],
            "window_end": record.get("window", [None, None])[1],
            "weights": record.get("weights"),
            "prior_weights": pre_trade_weights,
            "turnover": turnover,
            "gross_change": (2.0 * turnover if turnover is not None else None),
            "solver": record.get("solver", {}),
            "constraint_violations": violations,
            "covariance_fingerprint": (fp_mod.covariance_fingerprint(
                run["universe_fingerprint"], config["estimation"],
                config["covariance"], record.get("window"),
                [[round(float(v), 12) for v in row]
                 for row in record["covariance"]],
                record.get("estimation_input_fingerprint"))
                if record.get("covariance") is not None else None),
            "weight_fingerprint": (fp_mod.weight_fingerprint(record["weights"])
                                   if record.get("weights") else None),
            "cost": cost,
            "status": record["status"],
            "reason": record.get("reason"),
        }
        # persisted inside solver_json so the floor clamp and per-asset
        # unavailability stay visible in storage and export
        rb["solver"] = {
            **rb["solver"],
            "floored_assets": [e["asset_id"] if isinstance(e, dict) else e
                               for e in (record.get("floored_assets") or [])],
            "unavailable_assets": record.get("unavailable_assets") or [],
        }
        rebalances.append(rb)
        if record.get("weights") is not None:
            prev_weights = record["weights"]
            last_success = {**record, "rebalance": rb}
            prev_effective_index = i

    solver_status = (last_success["solver"].get("status")
                     if last_success else "failed")
    violation_count = sum(len(r["constraint_violations"]) for r in rebalances)
    if violation_count:
        warnings.append(f"{violation_count} constraint violation(s) detected "
                        "by the independent post-solve check")

    risk = budget = concentration = None
    covariance_block = None
    weight_rows: List[Dict[str, Any]] = []
    contribution_rows: List[Dict[str, Any]] = []
    if last_success is not None:
        weights = last_success["weights"]
        cov = last_success["covariance"]
        w_list = [weights.get(a, 0.0) for a in asset_ids]
        risk = risk_mod.portfolio_risk(w_list, cov)
        budget = risk_mod.budget_diagnostics(
            asset_ids, risk.get("pcr"), config.get("risk_budgets"))
        concentration = risk_mod.concentration_diagnostics(
            asset_ids, w_list, risk.get("pcr"), cov)
        corr = cov_mod.correlation_from_covariance(cov)
        covariance_block = {
            "matrix": [[round(float(v), 12) for v in row] for row in cov],
            "correlation": ([[round(float(v), 10) for v in row]
                             for row in corr] if corr is not None else None),
            "report": last_success["covariance_report"],
            "report_after_repair":
                last_success["covariance_report_after_repair"],
            "repair": {k: v for k, v in last_success["repair"].items()
                       if k != "matrix"},
            "window": last_success["window"],
        }
        for w in last_success["covariance_report"].get("warnings", []):
            warnings.append(f"covariance: {w}")
        cons = last_success["constraints_used"]
        raw = last_success.get("raw_weights") or {}
        for a in assets:
            aid = a["asset_id"]
            weight_rows.append({
                "asset_id": aid,
                "raw_weight": raw.get(aid),
                "weight": weights.get(aid, 0.0),
                "lower_bound": (0.0 if aid in cons["excluded_assets"]
                                else cons["min_weight"]),
                "upper_bound": (0.0 if aid in cons["excluded_assets"]
                                else cons["max_weight"]),
                "group": a.get("group"),
                "constraint_status": ("violated" if any(
                    v.get("asset_id") == aid for v in
                    (last_success["rebalance"]["constraint_violations"] or []))
                    else "ok"),
            })
        for i, a in enumerate(asset_ids):
            row = (budget["rows"][i] if budget and i < len(budget["rows"])
                   else {})
            contribution_rows.append({
                "asset_id": a,
                "weight": w_list[i],
                "mcr": risk["mcr"][i] if risk.get("mcr") else None,
                "ccr": risk["ccr"][i] if risk.get("ccr") else None,
                "pcr": risk["pcr"][i] if risk.get("pcr") else None,
                "target_budget": row.get("target_budget"),
                "abs_difference": row.get("abs_difference"),
                "signed_difference": row.get("signed_difference"),
                "state": row.get("state", "unavailable"),
            })
    else:
        warnings.append("no rebalance produced weights; portfolio risk "
                        "diagnostics are unavailable")

    # sensitivity (around the final decision index)
    sensitivity_rows: List[Dict[str, Any]] = []
    if last_success is not None and indices:
        base_weights = last_success["weights"]
        final_index = last_success["rebalance"]["decision_index"]
        for scenario in sens_mod.build_scenarios(config["sensitivity"]):
            if scenario["is_base"]:
                srec = last_success
            else:
                overrides = {scenario["dimension"]: scenario["value"]}
                try:
                    srec = _construct_at(run, final_index, matrix,
                                         asset_ids, assets,
                                         train_indices, overrides)
                except Exception as exc:  # a scenario never voids the run
                    srec = {"status": "failed", "reason": str(exc),
                            "weights": None,
                            "solver": {"status": "failed",
                                       "reason": str(exc)}}
            row: Dict[str, Any] = {
                "dimension": scenario["dimension"],
                "value": scenario["value"],
                "is_base": scenario["is_base"],
                "status": srec.get("status", "completed"),
                "reason": srec.get("reason"),
                "solver_status": srec.get("solver", {}).get("status"),
                "constraint_violation_count": 0,
                "portfolio_volatility": None, "effective_positions": None,
                "max_budget_deviation": None, "turnover": None,
                "cost_return": None,
            }
            if srec.get("weights") is not None:
                sw = [srec["weights"].get(a, 0.0) for a in asset_ids]
                srisk = risk_mod.portfolio_risk(sw, srec["covariance"])
                sconc = risk_mod.concentration_diagnostics(
                    asset_ids, sw, srisk.get("pcr"), srec["covariance"])
                sbud = risk_mod.budget_diagnostics(
                    asset_ids, srisk.get("pcr"), config.get("risk_budgets"))
                # the BASE row reports the final rebalance's actual turnover;
                # variation rows report the shift from the base book
                sturn = (last_success["rebalance"]["turnover"]
                         if scenario["is_base"] else
                         reb_mod.one_way_turnover(base_weights,
                                                  srec["weights"],
                                                  "zero_book"))
                sviol = cons_mod.check_weights(
                    srec["weights"],
                    srec.get("constraints_used", config["constraints"]),
                    assets, turnover=None)
                row.update({
                    "portfolio_volatility": srisk["volatility"],
                    "effective_positions": sconc.get("effective_positions"),
                    "max_budget_deviation": sbud.get("max_abs_deviation"),
                    "turnover": sturn,
                    "constraint_violation_count": len(sviol),
                })
                if cost_model is not None:
                    # base row: the final rebalance's actual turnover;
                    # variation rows: the shift from the base book — the
                    # same turnover the row's turnover column reports
                    cost = costs_mod.estimate_rebalance_cost(
                        sturn, cost_model, config.get("cost_notional"))
                    row["cost_return"] = cost.get("total_cost_return")
            row["fingerprint"] = fp_mod.scenario_fingerprint(
                run["configuration_fingerprint"], scenario)
            sensitivity_rows.append(row)

    regimes = _regime_join(run, rebalances, asset_ids, matrix, timestamps,
                           budget)

    mean_turn_vals = [r["turnover"] for r in rebalances
                      if r["turnover"] is not None]
    aggregates = {
        "portfolio_volatility": risk["volatility"] if risk else None,
        "effective_positions": (concentration or {}).get("effective_positions"),
        "max_budget_deviation": (budget or {}).get("max_abs_deviation"),
        "mean_turnover": (float(np.mean(mean_turn_vals))
                          if mean_turn_vals else None),
    }
    result_fp = fp_mod.result_fingerprint(
        run["configuration_fingerprint"], rebalances,
        risk or {}, budget or {}, concentration or {}, sensitivity_rows,
        [{"rebalance_id": r["rebalance_id"],
          "violations": r["constraint_violations"]} for r in rebalances],
        warnings, integrity, solver_status or "failed",
        covariance=covariance_block, regimes=regimes)

    asset_rows = [
        {**asset, "volatility": (float(np.std(matrix[i], ddof=1))
                                  if n_periods >= 2 else None),
         "metadata": asset.get("metadata", {})}
        for i, asset in enumerate(assets)
    ]
    store.replace_execution_results(
        run_id,
        assets=asset_rows,
        rebalances=rebalances,
        weights=weight_rows,
        contributions=contribution_rows,
        sensitivity=sensitivity_rows,
        run_updates={
            "status": "completed",
            "integrity_status": integrity,
            "solver_status": solver_status or "failed",
            "rebalance_count": len(rebalances),
            "portfolio_volatility": aggregates["portfolio_volatility"],
            "effective_positions": aggregates["effective_positions"],
            "max_budget_deviation": aggregates["max_budget_deviation"],
            "mean_turnover": aggregates["mean_turnover"],
            "constraint_violation_count": violation_count,
            "result_fingerprint": result_fp,
            "risk_json": json.dumps(risk) if risk else None,
            "budget_json": json.dumps(budget) if budget else None,
            "concentration_json": (json.dumps(concentration)
                                   if concentration else None),
            "covariance_json": (json.dumps(covariance_block)
                                 if covariance_block else None),
            "regimes_json": json.dumps(regimes) if regimes else None,
            "warnings_json": json.dumps(warnings),
            "completed_at": _now(),
            "duration_ms": int((time.monotonic() - t0) * 1000),
            "error_message": None,
        },
    )
    run = store.get_run(run_id)
    assert run is not None
    if create_experiment and not run.get("experiment_id"):
        record = experiment_integration.record_experiment(
            name=f"Portfolio diagnostics: {run['name']}",
            module="portfolio_diagnostics",
            experiment_type="portfolio_construction_diagnostics",
            status="completed",
            parameters={
                "method": run["method"],
                "covariance_method": run["covariance_method"],
                "integrity_status": integrity,
                "solver_status": solver_status,
                "configuration_fingerprint": run["configuration_fingerprint"],
                "result_fingerprint": result_fp,
            },
            metrics={
                "asset_count": run["asset_count"],
                "portfolio_volatility": aggregates["portfolio_volatility"],
                "effective_positions": aggregates["effective_positions"],
                "max_budget_deviation": aggregates["max_budget_deviation"],
                "mean_turnover": aggregates["mean_turnover"],
                "constraint_violations": violation_count,
            },
            tags=["portfolio-diagnostics"],
            source="portfolio_diagnostics",
        )
        if record is not None:
            store.update_run(run_id, {"experiment_id": record["id"]})
    return get_run(run_id)


def _integrity_state(config: Dict[str, Any],
                     train_indices: Optional[set]) -> str:
    # full-sample estimation is NEVER promoted, even when a validation
    # split is linked (that combination is also rejected at create)
    if config["method"] != "user_supplied" \
            and config["estimation"]["mode"] == "full_sample":
        return "full_sample_descriptive"
    if config["method"] == "user_supplied":
        basis = (config.get("user_provenance") or {}).get("basis", "unknown")
        lag = (config.get("user_provenance") or {}).get("lag")
        if basis == "centered" or (lag is not None and lag < 1):
            return "invalid"
        if basis == "causal_rolling":
            return "verified_causal_rolling" if (lag or 0) >= 1 else "invalid"
        if basis == "declared":
            return "declared"
        if basis == "full_sample":
            return "full_sample_descriptive"
        return "unknown"
    if train_indices is not None:
        return "verified_from_validation_split"
    return "verified_causal_rolling"


def _regime_join(run: Dict[str, Any], rebalances: List[Dict[str, Any]],
                 asset_ids: List[str], matrix: np.ndarray,
                 timestamps: List[str],
                 budget: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Portfolio characteristics by STORED regime assignment (no recompute)."""
    if not run.get("regime_run_id"):
        return None
    rrun = regime_store.get_run(run["regime_run_id"])
    if rrun is None:
        return None
    definition = next((d for d in regime_store.list_definitions(rrun["id"])
                       if d["definition_id"] == run["regime_definition_id"]),
                      None)
    if definition is None:
        return None
    label_by_ts = dict(zip(rrun["timestamps"], definition["assignments"]))
    returns_list = matrix.tolist()
    port_returns = reb_mod.portfolio_returns(
        rebalances, asset_ids, returns_list, len(timestamps))
    groups: Dict[str, List[int]] = {}
    for t, ts in enumerate(timestamps):
        if port_returns[t] is None:
            continue
        label = label_by_ts.get(ts)
        groups.setdefault(label if label is not None else "unassigned",
                          []).append(t)
    reb_by_ts = {r["decision_timestamp"]: r for r in rebalances}
    rows = []
    for label in sorted(groups):
        idx = groups[label]
        vals = np.array([port_returns[t] for t in idx], dtype=float)
        rebs = [reb_by_ts[timestamps[t]] for t in idx
                if timestamps[t] in reb_by_ts]
        turns = [r["turnover"] for r in rebs if r["turnover"] is not None]
        cost_states = [r["cost"]["completeness"] for r in rebs
                       if r.get("cost")]
        rows.append({
            "regime_label": label,
            "observation_count": len(idx),
            "mean_return": float(vals.mean()),
            "return_std": (float(vals.std(ddof=1)) if len(vals) >= 2 else None),
            "cumulative_return": float(np.prod(1.0 + vals) - 1.0),
            "rebalance_count": len(rebs),
            "mean_turnover": (float(np.mean(turns)) if turns else None),
            "cost_completeness": (sorted(set(cost_states))
                                  if cost_states else None),
            "rare_regime_warning": len(idx) < RARE_REGIME_MIN_OBSERVATIONS,
        })
    return {
        "regime_run_id": run["regime_run_id"],
        "regime_run_name": rrun["name"],
        "definition_id": run["regime_definition_id"],
        "definition_integrity": definition["integrity_status"],
        # a whole-run property — NOT a regime-conditional measurement
        "run_max_budget_deviation": (budget or {}).get("max_abs_deviation"),
        "note": ("stored effective regime assignments joined by exact "
                 "timestamp; regimes are never recomputed and no regime is "
                 "preferred or recommended"),
        "rows": rows,
    }


def invalidate_run(run_id: int, reason: str) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"portfolio-diagnostic run {run_id} not found")
    if run["status"] == "invalidated":
        raise ConflictError("run is already invalidated")
    store.update_run(run_id, {"status": "invalidated", "error_message": reason,
                              "is_baseline": 0})
    return get_run(run_id)


# ---------------------------------------------------------------------------
# Baselines, comparison, export
# ---------------------------------------------------------------------------


def _baseline_scope(run: Dict[str, Any]) -> str:
    ts = run["universe"]["timestamps"]
    window = f"{ts[0]}..{ts[-1]}" if ts else "none"
    from app.experiment_registry.fingerprints import sha256_hex
    cov_hash = sha256_hex({"cov": run["configuration"]["covariance"],
                           "reb": run["configuration"]["rebalance"]})[:16]
    return "|".join([
        f"uni:{run['universe_fingerprint'][:16]}",
        f"ds:{run['dataset_version_id'] or 'none'}",
        f"m:{run['method']}", f"cov:{cov_hash}",
        f"cons:{run['constraint_fingerprint'][:16]}", f"win:{window}",
    ])


def mark_baseline(run_id: int) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"portfolio-diagnostic run {run_id} not found")
    if run["status"] != "completed":
        raise ConflictError("baselines require a completed run")
    if run["integrity_status"] not in BASELINE_ACCEPTABLE_INTEGRITY:
        raise ConflictError(
            "baselines require verified or declared estimation integrity — "
            f"this run is {run['integrity_status']}")
    if run["solver_status"] not in BASELINE_ACCEPTABLE_SOLVER:
        raise ConflictError(
            f"baselines require a successful solve — this run is "
            f"{run['solver_status']}")
    if run["constraint_violation_count"] > 0:
        raise ConflictError(
            "baselines require every configured constraint satisfied")
    rebs = store.list_rebalances(run_id)
    if any(r["status"] != "completed" for r in rebs):
        raise ConflictError(
            "baselines require every scheduled rebalance to have solved — "
            "this run has failed or unavailable rebalances in its history")
    if not run["result_fingerprint"]:
        raise ConflictError("baselines require a result fingerprint")
    scope = _baseline_scope(run)
    store.update_run(run_id, {"baseline_scope": scope})
    store.mark_baseline(run_id, scope)
    return get_run(run_id)


def _entry(field: str, a: Any, b: Any) -> Dict[str, Any]:
    if a is None and b is None:
        return {"kind": "unavailable", "field": field, "a": a, "b": b, "note": ""}
    if a is None:
        return {"kind": "only_in_b", "field": field, "a": a, "b": b, "note": ""}
    if b is None:
        return {"kind": "only_in_a", "field": field, "a": a, "b": b, "note": ""}
    kind = "same" if a == b else "changed"
    note = ""
    if (kind == "changed" and isinstance(a, (int, float)) and isinstance(b, (int, float))
            and not isinstance(a, bool) and not isinstance(b, bool)
            and math.isfinite(float(a)) and math.isfinite(float(b))):
        note = f"Δ {round(b - a, 6)}"
        if a != 0:
            note += f" ({(b - a) / abs(a) * 100.0:+.2f}%)"
    return {"kind": kind, "field": field, "a": a, "b": b, "note": note}


def compare_runs(a_id: int, b_id: int) -> Dict[str, Any]:
    if a_id == b_id:
        raise PortfolioDiagnosticsError("compare requires two different runs")
    a, b = get_run(a_id), get_run(b_id)
    comparability: List[str] = []
    if a["universe_fingerprint"] != b["universe_fingerprint"]:
        comparability.append("portfolio universes differ — weights and risk "
                             "figures are not directly comparable")
    if (a.get("dataset_version_id") or None) != (b.get("dataset_version_id") or None):
        comparability.append("linked dataset versions differ")
    if a["universe"]["frequency"] != b["universe"]["frequency"]:
        comparability.append("return frequencies differ")
    if a["method"] != b["method"]:
        comparability.append("construction methods differ")
    if a["covariance_method"] != b["covariance_method"]:
        comparability.append("covariance methods differ")
    if a["constraint_fingerprint"] != b["constraint_fingerprint"]:
        comparability.append("constraint configurations differ")
    if (a["configuration"].get("risk_budgets") or None) != \
            (b["configuration"].get("risk_budgets") or None):
        comparability.append("risk budgets differ")
    if a["universe"]["timestamps"][:1] != b["universe"]["timestamps"][:1] or \
            a["universe"]["timestamps"][-1:] != b["universe"]["timestamps"][-1:]:
        comparability.append("observation windows differ")
    if a["integrity_status"] != b["integrity_status"]:
        comparability.append("integrity states differ")
    identity = [_entry(f, a.get(f), b.get(f)) for f in (
        "method", "covariance_method", "asset_count", "observation_count",
        "rebalance_count", "portfolio_volatility", "effective_positions",
        "max_budget_deviation", "mean_turnover",
        "constraint_violation_count", "solver_status", "integrity_status",
        "status", "dataset_name")]
    a_w = {w["asset_id"]: w["weight"] for w in store.list_weight_results(a_id)}
    b_w = {w["asset_id"]: w["weight"] for w in store.list_weight_results(b_id)}
    weight_rows = [{
        "asset_id": aid,
        "availability": ("both" if aid in a_w and aid in b_w
                         else ("only_in_a" if aid in a_w else "only_in_b")),
        "a_weight": a_w.get(aid), "b_weight": b_w.get(aid),
        # b - a, matching the identity group's delta convention
        "difference": (b_w[aid] - a_w[aid]
                       if aid in a_w and aid in b_w
                       and a_w[aid] is not None and b_w[aid] is not None
                       else None),
    } for aid in sorted(set(a_w) | set(b_w))]
    return {
        "a_id": a_id, "b_id": b_id,
        "comparability_warnings": comparability,
        "groups": {"identity": identity},
        "weights": weight_rows,
        "fingerprint_match": {
            "universe": a["universe_fingerprint"] == b["universe_fingerprint"],
            "constraints": a["constraint_fingerprint"] == b["constraint_fingerprint"],
            "configuration": a["configuration_fingerprint"] == b["configuration_fingerprint"],
            "result": bool(a.get("result_fingerprint"))
            and a.get("result_fingerprint") == b.get("result_fingerprint"),
        },
        "baseline": {"a": a["is_baseline"], "b": b["is_baseline"]},
    }


def export(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    filters = filters or {}
    listing = store.list_runs(filters=filters, page=1, page_size=store.MAX_PAGE_SIZE)
    runs = [_hydrate(r) for r in listing["items"]]
    payload: Dict[str, Any] = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "exported_at": _now(),
        "filters": {k: v for k, v in filters.items() if v is not None},
        "total_matching_runs": listing["total"],
        "truncated": listing["total"] > len(runs),
        "runs": runs,
        "assets": {}, "weights": {}, "risk_contributions": {},
        "rebalances": {}, "sensitivity": {},
    }
    for r in runs:
        payload["assets"][r["id"]] = store.list_assets(r["id"])
        payload["weights"][r["id"]] = store.list_weight_results(r["id"])
        payload["risk_contributions"][r["id"]] = \
            store.list_risk_contributions(r["id"])
        payload["rebalances"][r["id"]] = store.list_rebalances(r["id"])
        payload["sensitivity"][r["id"]] = \
            store.list_sensitivity_results(r["id"])
    return payload


__all__ = [
    "BASELINE_ACCEPTABLE_INTEGRITY", "BASELINE_ACCEPTABLE_SOLVER",
    "PortfolioDiagnosticsError", "InternalExecutionError", "NotFoundError", "ConflictError",
    "create_run", "get_run", "list_runs", "lab_summary", "execute_run",
    "invalidate_run", "mark_baseline", "compare_runs", "export",
]
