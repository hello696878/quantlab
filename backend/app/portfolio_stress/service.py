"""
Service layer for the Portfolio Stress Lab (v1).

Documented, fingerprinted execution order for every scenario:

1. validate the baseline portfolio and linked inputs
2. apply price-return shocks (direct P&L attribution, drifted weights)
3. apply volatility shocks
4. apply correlation shocks
5. rebuild and validate the stressed covariance (explicit repair only)
6. recalculate risk (baseline vs stressed MCR/CCR/PCR)
7. apply liquidity and cost stress (stressed cost model, new fingerprint)
8. final scenario reconciliation (P&L and risk effects kept separate)

plus trailing-only drawdown analysis and attribution of the deepest
episode.  Stored Phase 56 weights/covariance and Phase 55 cost models are
consumed READ-ONLY — nothing is recomputed into their records and no
linked fingerprint changes.  A Phase 54 regime run may be linked for
provenance only; no regime assignment is consumed in v1
(``linked_to_stored_regime`` integrity is reserved and unused).  The lab
never rebalances, hedges, or trades.
"""

from __future__ import annotations

import copy
import logging
import json
import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from app.dataset_registry import store as dataset_store
from app.experiment_registry import integration as experiment_integration
from app.experiment_registry import store as experiment_store
from app.experiment_registry.provenance import get_app_version, get_git_commit
from app.cost_diagnostics import store as cost_store
from app.regime_diagnostics import store as regime_store
from app.portfolio_diagnostics import store as pd_store
from app.portfolio_diagnostics import constraints as pd_constraints
from app.portfolio_diagnostics import costs as pd_costs
from app.portfolio_diagnostics import rebalance as pd_rebalance
from app.portfolio_diagnostics import risk as pd_risk
from app.portfolio_stress import EXPORT_SCHEMA_VERSION
from app.portfolio_stress import drawdown as dd_mod
from app.portfolio_stress import fingerprints as fp_mod
from app.portfolio_stress import shocks as shocks_mod
from app.portfolio_stress import store
from app.portfolio_stress import stress as stress_mod
from app.portfolio_stress.scenario import (
    ScenarioError,
    classify_integrity,
    shock_to_return,
    validate_scenario,
)

logger = logging.getLogger(__name__)



class PortfolioStressError(ValueError):
    """Invalid input/config (HTTP 422)."""


class NotFoundError(LookupError):
    """Unknown id (HTTP 404)."""


class ConflictError(RuntimeError):
    """State conflict (HTTP 409)."""


class InternalExecutionError(RuntimeError):
    """Unexpected execution failure (HTTP 500, sanitized message)."""


EXECUTION_ORDER = [
    "validate_baseline", "price_shocks", "volatility_shocks",
    "correlation_shocks", "rebuild_validate_covariance", "recalculate_risk",
    "liquidity_cost_stress", "reconciliation",
]
BASELINE_ACCEPTABLE_INTEGRITY = ("verified_historical_window",
                                 "verified_deterministic_rule")
BASELINE_ACCEPTABLE_COMPLETENESS = ("complete",)
ATTRIBUTION_POLICY = ("static stored-target weights between rebalances "
                      "(approximation labelled); linear per-period "
                      "contributions")

SENSITIVITY_DIMENSIONS = ("global_shock", "volatility_multiplier",
                          "correlation_alpha", "spread_multiplier",
                          "adv_multiplier", "impact_multiplier")
_SENS_BOUNDS = {
    "global_shock": (-1.0, 1.0),
    "volatility_multiplier": (1e-6, 10.0),
    "correlation_alpha": (0.0, 1.0),
    "spread_multiplier": (1e-6, 100.0),
    "adv_multiplier": (1e-6, 100.0),
    "impact_multiplier": (1e-6, 100.0),
}
MAX_SENS_VALUES = 5
MAX_SENS_SCENARIOS = 40


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def _validate_sensitivity(raw: Any, *, cost_linked: bool) -> Dict[str, List[float]]:
    cfg = raw or {}
    if not isinstance(cfg, dict):
        raise PortfolioStressError("sensitivity configuration must be an object")
    unknown = set(cfg) - set(SENSITIVITY_DIMENSIONS)
    if unknown:
        raise PortfolioStressError(
            f"unsupported sensitivity dimensions: {', '.join(sorted(unknown))}")
    out: Dict[str, List[float]] = {}
    total = 0
    for dim, values in cfg.items():
        if dim in ("spread_multiplier", "adv_multiplier", "impact_multiplier") \
                and not cost_linked:
            raise PortfolioStressError(
                f"sensitivity dimension {dim!r} requires a linked cost run")
        if not isinstance(values, list) or not values:
            raise PortfolioStressError(f"{dim} must be a non-empty list")
        if len(values) > MAX_SENS_VALUES:
            raise PortfolioStressError(
                f"{dim} supports at most {MAX_SENS_VALUES} values")
        lo, hi = _SENS_BOUNDS[dim]
        clean = []
        for v in values:
            if isinstance(v, bool) or not isinstance(v, (int, float)) \
                    or not math.isfinite(float(v)) or not (lo <= float(v) <= hi):
                raise PortfolioStressError(
                    f"{dim} values must be numbers in [{lo:g}, {hi:g}]")
            clean.append(float(v))
        out[dim] = sorted(set(clean))
        total += len(out[dim])
    if total + 1 > MAX_SENS_SCENARIOS:
        raise PortfolioStressError(
            f"sensitivity produces {total + 1} scenarios; at most "
            f"{MAX_SENS_SCENARIOS} are supported")
    return out


def _load_portfolio(portfolio_run_id: Any) -> Dict[str, Any]:
    if isinstance(portfolio_run_id, bool) or not isinstance(portfolio_run_id, int):
        raise PortfolioStressError("portfolio_run_id is required")
    prun = pd_store.get_run(portfolio_run_id)
    if prun is None:
        raise PortfolioStressError(
            f"portfolio run {portfolio_run_id} not found")
    if prun["status"] != "completed":
        raise PortfolioStressError(
            "stress runs require a completed portfolio run")
    return prun


def _select_rebalance(prun: Dict[str, Any],
                      rebalance_id: Optional[int]) -> Dict[str, Any]:
    rebs = pd_store.list_rebalances(prun["id"])
    candidates = [r for r in rebs if r.get("weights")]
    if not candidates:
        raise PortfolioStressError(
            "the portfolio run has no rebalance with solved weights")
    if rebalance_id is None:
        return candidates[-1]
    match = next((r for r in candidates
                  if r["rebalance_id"] == rebalance_id), None)
    if match is None:
        raise PortfolioStressError(
            f"rebalance {rebalance_id} not found or has no solved weights")
    return match


def create_run(payload: Dict[str, Any], *, demo_key: Optional[str] = None) -> Dict[str, Any]:
    name = (payload.get("name") or "").strip()
    if not name or len(name) > 200:
        raise PortfolioStressError("name must be 1..200 characters")
    prun = _load_portfolio(payload.get("portfolio_run_id"))
    universe = prun["universe"]
    asset_ids = [a["asset_id"] for a in universe["assets"]]
    groups = sorted({a["group"] for a in universe["assets"] if a.get("group")})
    rebalance = _select_rebalance(prun, payload.get("portfolio_rebalance_id"))

    try:
        scenario = validate_scenario(payload.get("scenario"),
                                     asset_ids=asset_ids, groups=groups)
    except ScenarioError as exc:
        raise PortfolioStressError(str(exc))

    # a historical replay is arithmetically undefined off the stored
    # timeline or with a reversed window — reject at create (422); the
    # future-looking ex-ante case stays creatable as an INVALID run
    # because its replay is well-defined and the label carries the honesty
    if scenario["historical"] is not None:
        timeline_index = {ts: i for i, ts in enumerate(universe["timestamps"])}
        h_start = scenario["historical"]["start_timestamp"]
        h_end = scenario["historical"]["end_timestamp"]
        if h_start not in timeline_index or h_end not in timeline_index:
            raise PortfolioStressError(
                "historical window does not reference actual stored "
                "observations of the linked portfolio's timeline")
        if timeline_index[h_end] < timeline_index[h_start]:
            raise PortfolioStressError(
                "historical window end precedes its start; an empty replay "
                "is never silently reported as zero shocks")

    integrity_block = classify_integrity(
        scenario, timeline=universe["timestamps"],
        decision_timestamp=rebalance["decision_timestamp"])
    integrity = integrity_block["integrity"]

    notional = payload.get("notional")
    if notional is not None:
        if isinstance(notional, bool) or not isinstance(notional, (int, float)) \
                or not math.isfinite(float(notional)) or float(notional) <= 0:
            raise PortfolioStressError(
                "notional must be a finite number > 0 (never fabricated)")
        notional = float(notional)
    if scenario["liquidity_cost_stress"] \
            and scenario["liquidity_cost_stress"].get("notional_scale") \
            and notional is None:
        raise PortfolioStressError(
            "notional_scale requires an explicit portfolio notional")

    cost_run_id = payload.get("cost_diagnostic_run_id")
    cost_model = None
    crun = None
    if cost_run_id is not None:
        crun = cost_store.get_run(cost_run_id)
        if crun is None:
            raise PortfolioStressError(
                f"cost-diagnostic run {cost_run_id} not found")
        cost_model = cost_store.get_cost_model(cost_run_id)
        if cost_model is None:
            raise PortfolioStressError(
                "the linked cost-diagnostic run stores no cost model")
    if scenario["liquidity_cost_stress"] and cost_model is None:
        raise PortfolioStressError(
            "liquidity/cost stress requires a linked cost-diagnostic run")

    regime_run_id = payload.get("regime_run_id")
    rrun = None
    if regime_run_id is not None:
        rrun = regime_store.get_run(regime_run_id)
        if rrun is None or rrun["status"] != "completed":
            raise PortfolioStressError(
                "regime context requires a completed regime run")

    # value-based fallback: the API model always emits the key with None,
    # so key-presence defaulting would never inherit the portfolio's dataset
    dataset_version_id = payload.get("dataset_version_id")
    if dataset_version_id is None:
        dataset_version_id = prun.get("dataset_version_id")
    dataset_manifest_fp = None
    if dataset_version_id is not None:
        version = dataset_store.get_version(dataset_version_id)
        if version is None:
            raise PortfolioStressError(
                f"dataset version {dataset_version_id} not found")
        dataset_manifest_fp = version["manifest_fingerprint"]

    sensitivity = _validate_sensitivity(payload.get("sensitivity"),
                                        cost_linked=cost_model is not None)

    scenario_fp = fp_mod.scenario_fingerprint(scenario, integrity)
    timeline = universe["timestamps"]
    returns_matrix = [a["returns"] for a in universe["assets"]]
    timeline_index = {ts: i for i, ts in enumerate(timeline)}
    historical_input_fp = None
    if scenario["historical"] is not None:
        hist = scenario["historical"]
        historical_input_fp = fp_mod.observation_input_fingerprint(
            "portfolio_stress_historical_input_v1", asset_ids, timeline,
            returns_matrix, timeline_index[hist["start_timestamp"]],
            timeline_index[hist["end_timestamp"]])
    drawdown_input_fp = None
    decision_index = timeline_index[rebalance["decision_timestamp"]]
    if integrity == "verified_historical_window" and decision_index > 0:
        drawdown_input_fp = fp_mod.observation_input_fingerprint(
            "portfolio_stress_predecision_drawdown_input_v1", asset_ids,
            timeline, returns_matrix, 0, decision_index - 1)
    portfolio_identity = {
        "portfolio_run_id": prun["id"],
        "portfolio_configuration_fingerprint": prun["configuration_fingerprint"],
        "rebalance_id": rebalance["rebalance_id"],
        "portfolio_universe_fingerprint": prun.get("universe_fingerprint"),
        "constraint_fingerprint": prun.get("constraint_fingerprint"),
        "weight_fingerprint": rebalance.get("weight_fingerprint"),
        "covariance_fingerprint": rebalance.get("covariance_fingerprint"),
        "decision_timestamp": rebalance["decision_timestamp"],
        "effective_timestamp": rebalance.get("effective_timestamp"),
    }
    # fingerprints hash CONTENT-ADDRESSED identity only (no database row
    # ids), so a byte-identical configuration reproduces the same
    # fingerprint in a different database — the ids stay as stored columns
    fp_identity = {
        "portfolio_configuration_fingerprint": (
            None if integrity == "verified_historical_window"
            else prun["configuration_fingerprint"]),
        "portfolio_universe_fingerprint": (
            None if integrity == "verified_historical_window"
            else prun.get("universe_fingerprint")),
        "constraint_fingerprint": prun.get("constraint_fingerprint"),
        "weight_fingerprint": rebalance.get("weight_fingerprint"),
        "covariance_fingerprint": rebalance.get("covariance_fingerprint"),
        "decision_timestamp": rebalance["decision_timestamp"],
        "effective_timestamp": rebalance.get("effective_timestamp"),
        "historical_input_fingerprint": historical_input_fp,
        "predecision_drawdown_input_fingerprint": drawdown_input_fp,
    }
    fp_linked = {
        "dataset_manifest_fingerprint": dataset_manifest_fp,
        "cost_model_fingerprint": (cost_model or {}).get("fingerprint"),
        "cost_configuration_fingerprint": (
            crun.get("configuration_fingerprint") if crun else None),
        "cost_result_fingerprint": (
            crun.get("result_fingerprint") if crun else None),
        "regime_configuration_fingerprint": (
            rrun.get("configuration_fingerprint") if rrun else None),
        "regime_result_fingerprint": (
            rrun.get("result_fingerprint") if rrun else None),
    }
    config_fp = fp_mod.configuration_fingerprint(
        scenario_fp, fp_identity, notional, fp_linked,
        ATTRIBUTION_POLICY, sensitivity, EXECUTION_ORDER)

    configuration = {
        "scenario": scenario,
        "scenario_integrity": integrity,
        "scenario_integrity_warnings": integrity_block["warnings"],
        "portfolio_identity": portfolio_identity,
        "notional": notional,
        "sensitivity": sensitivity,
        "attribution_policy": ATTRIBUTION_POLICY,
        "execution_order": EXECUTION_ORDER,
        "linked_identities": fp_linked,
        "cost_reference_turnover_note": (
            "cost stress is estimated for a reference one-way move of the "
            "whole book (turnover = 0.5 x sum |w|) under the stressed cost "
            "model — a reference calculation, not a modelled trade"),
        "pnl_vs_risk_note": (
            "direct price shocks produce P&L; volatility/correlation stress "
            "changes RISK ESTIMATES only and is never mixed into P&L"),
        "factor_shocks": "deferred in v1 (no estimated exposure model exists)",
        "regime_linkage_note": (
            "a linked regime run is provenance only in v1: no stored regime "
            "assignment is consumed and nothing is conditioned on regimes"),
    }
    run = store.insert_run({
        "name": name, "description": payload.get("description", ""),
        "scenario_type": scenario["scenario_type"],
        "integrity_status": integrity,
        "asset_count": len(asset_ids),
        "scenario_count": 1,
        "configuration": configuration,
        "configuration_fingerprint": config_fp,
        "scenario_fingerprint": scenario_fp,
        "baseline_weight_fingerprint": rebalance.get("weight_fingerprint"),
        "baseline_covariance_fingerprint": rebalance.get("covariance_fingerprint"),
        "portfolio_run_id": prun["id"],
        "portfolio_rebalance_id": rebalance["rebalance_id"],
        "dataset_version_id": dataset_version_id,
        "regime_run_id": regime_run_id,
        "cost_diagnostic_run_id": cost_run_id,
        "experiment_id": None,
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
        raise NotFoundError(f"portfolio-stress run {run_id} not found")
    return _hydrate(run)


def _hydrate(run: Dict[str, Any]) -> Dict[str, Any]:
    run["portfolio_run_name"] = run["portfolio_method"] = None
    run["dataset_name"] = run["dataset_version_label"] = None
    run["dataset_invalidated"] = None
    run["dataset_manifest_fingerprint"] = None
    run["dataset_provenance_status"] = run["dataset_quality_status"] = None
    run["regime_run_name"] = None
    run["cost_run_name"] = run["cost_model_fingerprint"] = None
    run["experiment_name"] = None
    prun = pd_store.get_run(run["portfolio_run_id"])
    if prun:
        run["portfolio_run_name"] = prun["name"]
        run["portfolio_method"] = prun["method"]
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
    if run.get("regime_run_id"):
        rrun = regime_store.get_run(run["regime_run_id"])
        if rrun:
            run["regime_run_name"] = rrun["name"]
    if run.get("cost_diagnostic_run_id"):
        crun = cost_store.get_run(run["cost_diagnostic_run_id"])
        if crun:
            run["cost_run_name"] = crun["name"]
            run["cost_model_fingerprint"] = crun["cost_model_fingerprint"]
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
# Execution helpers
# ---------------------------------------------------------------------------


def _historical_shocks(scenario: Dict[str, Any], universe: Dict[str, Any]
                       ) -> Dict[str, Optional[float]]:
    """Replay a stored window: shock_i = compounded return over [s..e]."""
    hist = scenario["historical"]
    index = {ts: i for i, ts in enumerate(universe["timestamps"])}
    if hist["start_timestamp"] not in index \
            or hist["end_timestamp"] not in index:
        raise PortfolioStressError(
            "historical window does not reference actual stored "
            "observations of the linked portfolio's timeline")
    s, e = index[hist["start_timestamp"]], index[hist["end_timestamp"]]
    if e < s:
        raise PortfolioStressError(
            "historical window end precedes its start; an empty replay is "
            "never silently reported as zero shocks")
    out: Dict[str, Optional[float]] = {}
    for a in universe["assets"]:
        level = 1.0
        for t in range(s, e + 1):
            level *= (1.0 + a["returns"][t])
        out[a["asset_id"]] = level - 1.0
    return out


def _weight_series(prun: Dict[str, Any],
                   rebalances: List[Dict[str, Any]]
                   ) -> List[Optional[Dict[str, float]]]:
    """Static stored-target weights governing each period (labelled
    approximation; None before the first solved rebalance)."""
    timestamps = prun["universe"]["timestamps"]
    index = {ts: i for i, ts in enumerate(timestamps)}
    solved = sorted(
        ((index[r["decision_timestamp"]], r["weights"]) for r in rebalances
         if r.get("weights") and r["decision_timestamp"] in index),
        key=lambda x: x[0])
    series: List[Optional[Dict[str, float]]] = [None] * len(timestamps)
    for j, (start, weights) in enumerate(solved):
        end = solved[j + 1][0] if j + 1 < len(solved) else len(timestamps)
        for t in range(start, end):
            series[t] = weights
    return series


def _stressed_cost_model(cost_model: Dict[str, Any],
                         liq: Dict[str, Any]) -> Dict[str, Any]:
    """A DEEP COPY of the linked Phase 55 model with explicit multipliers
    applied; the base model object is never touched."""
    stressed = copy.deepcopy(cost_model)
    spread = stressed.get("spread") or {}
    if liq.get("spread_multiplier") is not None and "value" in spread:
        spread["value"] = spread["value"] * liq["spread_multiplier"]
    slippage = stressed.get("slippage") or {}
    if liq.get("slippage_multiplier") is not None and "value" in slippage:
        slippage["value"] = slippage["value"] * liq["slippage_multiplier"]
    impact = stressed.get("impact") or {}
    if liq.get("impact_multiplier") is not None:
        for key in ("value", "coefficient"):
            if key in impact:
                impact[key] = impact[key] * liq["impact_multiplier"]
    return stressed


def _cost_block(scenario_liq: Optional[Dict[str, Any]],
                cost_model: Optional[Dict[str, Any]],
                weights: Dict[str, float],
                notional: Optional[float]) -> Optional[Dict[str, Any]]:
    if cost_model is None:
        return None
    reference_turnover = 0.5 * sum(abs(v) for v in weights.values())
    base = pd_costs.estimate_rebalance_cost(reference_turnover, cost_model,
                                            notional)
    block: Dict[str, Any] = {
        "reference_turnover": reference_turnover,
        "reference_note": ("estimated cost of a full one-way book move; a "
                           "reference calculation, not a modelled trade"),
        "base": base,
        "base_model_fingerprint": cost_model.get("fingerprint"),
        "stressed": None,
        "stressed_model_fingerprint": None,
        "participation": None,
    }
    if scenario_liq:
        stressed_model = _stressed_cost_model(cost_model, scenario_liq)
        scale = scenario_liq.get("notional_scale", 1.0)
        stressed = pd_costs.estimate_rebalance_cost(
            reference_turnover, stressed_model,
            notional * scale if notional else None)
        block["stressed"] = stressed
        block["stressed_model_fingerprint"] = \
            fp_mod.stressed_cost_model_fingerprint(
                cost_model.get("fingerprint"), scenario_liq)
        base_adv = scenario_liq.get("base_adv_notional")
        if base_adv and notional:
            adv_mult = scenario_liq.get("adv_multiplier", 1.0)
            stressed_adv = base_adv * adv_mult
            traded_notional = 2.0 * reference_turnover * notional * \
                scenario_liq.get("notional_scale", 1.0)
            participation = traded_notional / stressed_adv
            threshold = scenario_liq.get("participation_threshold", 0.25)
            block["participation"] = {
                "base_adv_notional": base_adv,
                "adv_multiplier": adv_mult,
                "traded_notional": traded_notional,
                "participation": participation,
                "threshold": threshold,
                "above_threshold": participation > threshold,
                "denominator_note": ("participation = traded notional / "
                                     "(base ADV x ADV multiplier)"),
            }
        elif scenario_liq.get("adv_multiplier") is not None:
            block["participation"] = {
                "participation": None,
                "reason": ("participation needs an explicit base ADV "
                           "notional and a portfolio notional — never "
                           "fabricated"),
            }
    return block


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def execute_run(run_id: int, *, create_experiment: bool = False) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"portfolio-stress run {run_id} not found")
    if run["status"] == "invalidated":
        raise ConflictError("run is invalidated; create a new run instead")
    t0 = time.monotonic()
    store.update_run(run_id, {"status": "running", "error_message": None})
    try:
        return _execute_body(run_id, run, t0, create_experiment)
    except (NotFoundError, ConflictError):
        raise
    except PortfolioStressError as exc:
        store.fail_execution(run_id, str(exc), _now())
        raise
    except Exception:
        logger.exception("Unexpected portfolio-stress execution failure")
        store.fail_execution(
            run_id, "Internal execution error; see server logs.", _now())
        raise InternalExecutionError(
            "internal error during stress execution; the run is marked failed")


def _evaluate_scenario_once(scenario: Dict[str, Any], *,
                            universe: Dict[str, Any],
                            asset_ids: List[str],
                            asset_groups: Dict[str, Optional[str]],
                            weights: Dict[str, float],
                            base_cov: Optional[np.ndarray],
                            cost_model: Optional[Dict[str, Any]],
                            notional: Optional[float]) -> Dict[str, Any]:
    """Steps 2–8 of the documented order for one scenario definition."""
    # step 2: price shocks
    if scenario["scenario_type"] in ("historical_window",
                                     "historical_single_period"):
        resolved = {"shocks": _historical_shocks(scenario, universe),
                    "sources": {a: "historical" for a in asset_ids}}
    else:
        resolved = shocks_mod.resolve_shocks(scenario, asset_ids, asset_groups)
    contributions = shocks_mod.direct_contributions(
        weights, resolved["shocks"], asset_ids, asset_groups, notional)
    drifted = shocks_mod.drifted_weights(weights, resolved["shocks"],
                                         asset_ids)

    # steps 3–6: volatility/correlation stress and risk recomputation
    baseline_risk = stressed_risk = None
    cov_stress = None
    if base_cov is not None:
        w_list = [weights.get(a, 0.0) for a in asset_ids]
        baseline_risk = pd_risk.portfolio_risk(w_list, base_cov)
        if scenario["volatility_stress"] or scenario["correlation_stress"]:
            cov_stress = stress_mod.build_stressed_covariance(
                base_cov, asset_ids, scenario["volatility_stress"],
                scenario["correlation_stress"])
            if cov_stress["matrix"] is not None:
                stressed_risk = pd_risk.portfolio_risk(
                    w_list, cov_stress["matrix"])
    # step 7: liquidity/cost stress
    cost_block = _cost_block(scenario["liquidity_cost_stress"], cost_model,
                             weights, notional)
    # step 8: reconciliation — P&L vs risk kept strictly separate.  The
    # cost leg's state/basis travel WITH the triple so net-vs-gross can
    # never be misread: an unavailable configured cost leg is labelled,
    # never silently equal to gross, and a partial cost leg degrades the
    # triple's completeness (a partial total under-estimates cost).
    cost_return = None
    cost_state = "not_configured"
    cost_reason = None
    cost_completeness = None
    if scenario["liquidity_cost_stress"] is not None:
        if cost_block is None:
            cost_state = "unavailable"
            cost_reason = ("the linked cost model is no longer available; "
                           "the configured liquidity/cost stress could not "
                           "be applied")
        else:
            stressed_est = cost_block.get("stressed") or {}
            cost_return = stressed_est.get("total_cost_return")
            cost_state = stressed_est.get("status", "unavailable")
            cost_reason = stressed_est.get("reason")
            cost_completeness = stressed_est.get("completeness")
    direct = contributions["portfolio_scenario_return"]
    # basis guard: the shock leg may cover only the shocked SUBSET while the
    # cost leg is always a whole-book reference — subtracting one from the
    # other would be a basis mismatch, so the net is withheld with a reason
    basis_mismatch = (contributions["completeness"] != "complete"
                      and cost_return is not None)
    if basis_mismatch:
        net = None
        net_basis_note = (
            "net withheld: the shock leg covers only the shocked subset "
            "while the cost leg is a whole-book reference — the two legs "
            "are on different bases and are reported separately")
    else:
        net = (direct - cost_return
               if direct is not None and cost_return is not None else direct)
        net_basis_note = None
    completeness = contributions["completeness"]
    if cost_state not in ("not_configured", "available") \
            or (cost_completeness not in (None, "complete")):
        if completeness == "complete":
            completeness = "partial"
    reconciliation = {
        "baseline_value": 1.0,
        "direct_shock_return": direct,
        "stressed_cost_return": cost_return,
        "stressed_cost_state": cost_state,
        "stressed_cost_reason": cost_reason,
        "stressed_cost_completeness": cost_completeness,
        "cost_basis_note": (
            ("cost leg = stressed cost of a reference one-way move of the "
             f"whole book (reference turnover "
             f"{cost_block['reference_turnover']:.6f}) — a reference "
             "calculation, not a modelled trade")
            if cost_block and scenario["liquidity_cost_stress"] is not None
            else None),
        "net_scenario_return": net,
        "net_basis_note": net_basis_note,
        "scenario_pnl": (net * notional
                         if net is not None and notional else None),
        "risk_effect_note": ("volatility/correlation stress changes risk "
                             "estimates only — reported separately, never "
                             "mixed into P&L"),
        "completeness": completeness,
    }
    return {"resolved": resolved, "contributions": contributions,
            "drifted": drifted, "baseline_risk": baseline_risk,
            "stressed_risk": stressed_risk, "cov_stress": cov_stress,
            "cost_block": cost_block, "reconciliation": reconciliation}


def _execute_body(run_id: int, run: Dict[str, Any], t0: float,
                  create_experiment: bool) -> Dict[str, Any]:
    config = run["configuration"]
    scenario = config["scenario"]
    integrity = config["scenario_integrity"]
    notional = config.get("notional")
    warnings: List[str] = list(config.get("scenario_integrity_warnings") or [])

    # step 1: validate baseline
    prun = pd_store.get_run(run["portfolio_run_id"])
    if prun is None or prun["status"] != "completed":
        raise PortfolioStressError(
            "the linked portfolio run is no longer available/completed")
    universe = prun["universe"]
    asset_ids = [a["asset_id"] for a in universe["assets"]]
    asset_groups = {a["asset_id"]: a.get("group")
                    for a in universe["assets"]}
    rebalances = pd_store.list_rebalances(prun["id"])
    rebalance = next((r for r in rebalances
                      if r["rebalance_id"] == run["portfolio_rebalance_id"]),
                     None)
    if rebalance is None or not rebalance.get("weights"):
        raise PortfolioStressError(
            "the selected rebalance no longer has solved weights")
    weights = rebalance["weights"]
    if rebalance.get("weight_fingerprint") != run["baseline_weight_fingerprint"]:
        raise PortfolioStressError(
            "the stored portfolio weights changed since this stress run was "
            "created; re-create the run against the current record")

    base_cov = None
    needs_risk = bool(scenario["volatility_stress"]
                      or scenario["correlation_stress"])
    cov_block = prun.get("covariance")
    fingerprint_ok = (rebalance.get("covariance_fingerprint")
                      == run["baseline_covariance_fingerprint"])
    is_last_solved = rebalance["rebalance_id"] == max(
        (r["rebalance_id"] for r in rebalances if r.get("weights")),
        default=None)
    if cov_block and fingerprint_ok and is_last_solved:
        base_cov = np.array(cov_block["matrix"], dtype=float)
    risk_unavailable_reason = None
    if base_cov is None:
        if not cov_block:
            risk_unavailable_reason = (
                "the linked portfolio run stores no covariance matrix")
        elif not fingerprint_ok:
            risk_unavailable_reason = (
                "the stored covariance estimate changed since this stress "
                "run was created; risk stress is withheld — re-create the "
                "run against the current record")
        else:
            risk_unavailable_reason = (
                "the selected rebalance's covariance matrix is not stored "
                "(only the last successful rebalance's is); risk stress is "
                "unavailable for this selection")
        # always disclosed, whether or not this scenario stresses risk
        warnings.append(f"risk recomputation unavailable: "
                        f"{risk_unavailable_reason}")

    linked = config.get("linked_identities") or {}
    if run.get("dataset_version_id"):
        version = dataset_store.get_version(run["dataset_version_id"])
        if version is None:
            raise PortfolioStressError("the linked dataset version is unavailable")
        pinned = linked.get("dataset_manifest_fingerprint")
        if pinned and version.get("manifest_fingerprint") != pinned:
            raise PortfolioStressError(
                "the linked dataset manifest changed since this stress run "
                "was created; re-create the run")
        if version.get("invalidated_at"):
            warnings.append(
                "the linked dataset version is now invalidated; the stored "
                "stress run remains historical but should not be promoted")

    if run.get("regime_run_id"):
        rrun = regime_store.get_run(run["regime_run_id"])
        if rrun is None:
            raise PortfolioStressError("the linked regime run is unavailable")
        for key, field in (
                ("regime_configuration_fingerprint", "configuration_fingerprint"),
                ("regime_result_fingerprint", "result_fingerprint")):
            if linked.get(key) and rrun.get(field) != linked[key]:
                raise PortfolioStressError(
                    "the linked regime identity changed since this stress "
                    "run was created; re-create the run")

    cost_model = None
    if run.get("cost_diagnostic_run_id"):
        crun = cost_store.get_run(run["cost_diagnostic_run_id"])
        cost_model = cost_store.get_cost_model(run["cost_diagnostic_run_id"])
        if crun is None or cost_model is None:
            raise PortfolioStressError("the linked cost model is unavailable")
        expected = linked.get("cost_model_fingerprint")
        if expected and cost_model.get("fingerprint") != expected:
            raise PortfolioStressError(
                "the linked cost model changed since this stress run was "
                "created; re-create the run")
        for key, field in (
                ("cost_configuration_fingerprint", "configuration_fingerprint"),
                ("cost_result_fingerprint", "result_fingerprint")):
            if linked.get(key) and crun.get(field) != linked[key]:
                raise PortfolioStressError(
                    "the linked cost-diagnostic identity changed since this "
                    "stress run was created; re-create the run")

    result = _evaluate_scenario_once(
        scenario, universe=universe, asset_ids=asset_ids,
        asset_groups=asset_groups, weights=weights, base_cov=base_cov,
        cost_model=cost_model, notional=notional)

    contributions = result["contributions"]
    drifted = result["drifted"]
    baseline_risk = result["baseline_risk"]
    stressed_risk = result["stressed_risk"]
    cov_stress = result["cov_stress"]
    cost_block = result["cost_block"]
    reconciliation = result["reconciliation"]

    if contributions["completeness"] == "partial":
        warnings.append(
            f"{contributions['unavailable_assets']} asset(s) have no shock "
            "under the 'unavailable' missing-shock policy; the scenario "
            "return excludes them")
    if drifted["weights"] is None and drifted.get("reason"):
        warnings.append(f"drifted weights unavailable: {drifted['reason']}")
    if cost_block:
        for leg in ("base", "stressed"):
            estimate = cost_block.get(leg)
            if estimate and estimate.get("completeness") == "partial":
                warnings.append(
                    "the linked cost estimate is partial: some components "
                    "are honestly unavailable for weight-space turnover "
                    "(reasons recorded per component)")
                break
    if cov_stress is not None and cov_stress["matrix"] is None:
        warnings.append(f"stressed covariance unavailable: "
                        f"{cov_stress['reason']}")
    if cov_stress is not None and (cov_stress.get("corr_result") or {}).get("clamped"):
        warnings.append("stressed correlations were clamped to [-1, 1] "
                        "(disclosed, not silent)")
    if cov_stress is not None and (cov_stress.get("vol_result") or {}).get("clamped"):
        warnings.append(
            "additive volatility stress floored at zero for: "
            + ", ".join(cov_stress["vol_result"]["clamped"]))
    if cov_stress is not None and (cov_stress.get("repair") or {}).get("repaired"):
        warnings.append(
            "the requested stressed covariance had an eigenvalue below the "
            "explicit floor (which can include a singular PSD matrix) and "
            "was repaired under the explicit eigenvalue-floor policy "
            f"(floor={(cov_stress.get('repair') or {}).get('floor')}); the "
            "disclosed stressed vols/correlations describe the repaired "
            "matrix actually used")
    for report_key in ("report", "report_after"):
        for w in ((cov_stress or {}).get(report_key) or {}).get("warnings", []):
            entry = f"stressed covariance: {w}"
            if entry not in warnings:
                warnings.append(entry)

    # risk rows (baseline vs stressed) — the state reflects value PRESENCE,
    # not merely that a computation was attempted (zero-volatility books
    # return None contributions with an explicit note)
    risk_rows: List[Dict[str, Any]] = []
    if stressed_risk is not None and stressed_risk.get("pcr") is None \
            and stressed_risk.get("note"):
        warnings.append(f"stressed risk contributions unavailable: "
                        f"{stressed_risk['note']}")
    if baseline_risk is not None:
        base_pcr = baseline_risk.get("pcr")
        stre_pcr = stressed_risk.get("pcr") if stressed_risk else None
        base_rank = _ranks(base_pcr)
        stre_rank = _ranks(stre_pcr)
        for i, aid in enumerate(asset_ids):
            row = {
                "asset_id": aid,
                "baseline_mcr": _at(baseline_risk.get("mcr"), i),
                "baseline_ccr": _at(baseline_risk.get("ccr"), i),
                "baseline_pcr": _at(base_pcr, i),
                "stressed_mcr": _at(stressed_risk.get("mcr"), i)
                if stressed_risk else None,
                "stressed_ccr": _at(stressed_risk.get("ccr"), i)
                if stressed_risk else None,
                "stressed_pcr": _at(stre_pcr, i),
                "state": ("available"
                          if stressed_risk is not None
                          and stre_pcr is not None else "baseline_only"),
            }
            row["pcr_change"] = (row["stressed_pcr"] - row["baseline_pcr"]
                                 if row["stressed_pcr"] is not None
                                 and row["baseline_pcr"] is not None else None)
            row["rank_change"] = ((stre_rank[i] - base_rank[i])
                                  if base_rank and stre_rank else None)
            risk_rows.append(row)

    risk_summary = None
    if baseline_risk is None:
        risk_summary = {"available": False,
                        "reason": risk_unavailable_reason,
                        "baseline_volatility": None,
                        "stressed_volatility": None,
                        "volatility_change": None,
                        "baseline_identity_ok": None,
                        "stressed_identity_ok": None,
                        "largest_pcr_increase": None,
                        "largest_pcr_decrease": None,
                        "stressed_note": None,
                        "note": ("risk contributions are withheld rather "
                                 "than estimated from a substitute matrix")}
    else:
        risk_summary = {
            "available": True,
            "reason": None,
            "baseline_volatility": baseline_risk["volatility"],
            "stressed_volatility": (stressed_risk["volatility"]
                                    if stressed_risk else None),
            "volatility_change": (stressed_risk["volatility"]
                                  - baseline_risk["volatility"]
                                  if stressed_risk else None),
            "baseline_identity_ok": baseline_risk.get("identity_ok"),
            "stressed_identity_ok": (stressed_risk.get("identity_ok")
                                     if stressed_risk else None),
            "largest_pcr_increase": _extreme(risk_rows, "pcr_change", max),
            "largest_pcr_decrease": _extreme(risk_rows, "pcr_change", min),
            "stressed_note": (stressed_risk.get("note")
                              if stressed_risk else None),
            "note": ("a higher stressed contribution is a measured change "
                     "under these assumptions — not automatically worse"),
        }

    # constraint checks on the ORIGINAL and (when available) DRIFTED books
    constraints_cfg = prun["configuration"]["constraints"]
    assets_for_check = [{"asset_id": a["asset_id"], "group": a.get("group")}
                        for a in universe["assets"]]
    constraint_rows: List[Dict[str, Any]] = []
    for book, w in (("original", weights),
                    ("drifted", drifted.get("weights"))):
        if w is None:
            continue
        for v in pd_constraints.check_weights(w, constraints_cfg,
                                              assets_for_check,
                                              turnover=None):
            constraint_rows.append({"book": book, **v})
    if constraint_rows:
        drifted_breaches = sum(1 for r in constraint_rows
                               if r["book"] == "drifted")
        original_breaches = len(constraint_rows) - drifted_breaches
        parts = []
        if drifted_breaches:
            parts.append(f"{drifted_breaches} constraint check(s) breached "
                         "on the post-shock drifted book under this scenario")
        if original_breaches:
            parts.append(f"{original_breaches} check(s) already breached on "
                         "the stored book before any shock")
        warnings.append("; ".join(parts)
                        + " (no automatic rebalancing is performed)")

    # drawdown analysis on the CANONICAL Phase 56 realized-return series
    # (drifting weights between rebalances, exactly as recorded)
    weight_series = _weight_series(prun, rebalances)
    returns_matrix = [a["returns"] for a in universe["assets"]]
    timeline_index = {ts: i for i, ts in enumerate(universe["timestamps"])}
    indexed_rebalances = [
        {**r, "decision_index": timeline_index[r["decision_timestamp"]]}
        for r in rebalances if r["decision_timestamp"] in timeline_index]
    port_returns = pd_rebalance.portfolio_returns(
        indexed_rebalances, asset_ids, returns_matrix,
        len(universe["timestamps"]))
    analysis_timestamps = universe["timestamps"]
    analysis_weight_series = weight_series
    analysis_returns_matrix = returns_matrix
    analysis_scope = "full stored realized series (descriptive)"
    cutoff_timestamp = None
    if integrity == "verified_historical_window":
        cutoff = timeline_index[rebalance["decision_timestamp"]]
        cutoff_timestamp = rebalance["decision_timestamp"]
        analysis_timestamps = analysis_timestamps[:cutoff]
        analysis_weight_series = analysis_weight_series[:cutoff]
        analysis_returns_matrix = [row[:cutoff] for row in returns_matrix]
        port_returns = port_returns[:cutoff]
        analysis_scope = (
            "strictly pre-decision realized series for verified ex-ante "
            "historical analysis")
    path = dd_mod.drawdown_path(port_returns, analysis_timestamps)
    if not path.get("available") and path.get("reason"):
        warnings.append(f"drawdown analysis unavailable: {path['reason']}")
    if path.get("trailing_unobserved"):
        warnings.append(
            f"the last {path['trailing_unobserved']} period(s) have no "
            "recorded portfolio return (the recorded series ends early); "
            "the drawdown analysis covers the observed span only")
    all_episodes = dd_mod.detect_episodes(path)
    episode_count_total = len(all_episodes)
    if episode_count_total > dd_mod.MAX_EPISODES:
        # persist the DEEPEST episodes (chronological ids preserved) and
        # disclose the truncation — the deepest is never dropped
        episodes = sorted(sorted(all_episodes, key=lambda e: e["depth"])
                          [:dd_mod.MAX_EPISODES],
                          key=lambda e: e["episode_id"])
        warnings.append(
            f"{episode_count_total} drawdown episodes detected; only the "
            f"deepest {dd_mod.MAX_EPISODES} are persisted (disclosed, not "
            "silent) — episode ids stay chronological")
    else:
        episodes = all_episodes
    attribution_rows: List[Dict[str, Any]] = []
    attribution_block = None
    if all_episodes:
        # deepest selected from the FULL list, so attribution always
        # matches the reported max drawdown
        deepest = min(all_episodes, key=lambda e: e["depth"])
        start_offset = path["start_index"]
        # attribute the below-peak interval [episode start .. trough] — the
        # peak-making period's return is NOT part of the decline
        attribution = dd_mod.attribute_interval(
            start_offset + deepest["start_index"],
            start_offset + deepest["trough_index"],
            asset_ids, analysis_weight_series, analysis_returns_matrix, asset_groups,
            static_weights=True)
        if attribution.get("available"):
            attribution_rows = [
                {**r, "episode_id": deepest["episode_id"]}
                for r in attribution["rows"]]
            attribution_block = {
                "episode_id": deepest["episode_id"],
                "group_contributions": attribution["group_contributions"],
                "portfolio_contribution_sum":
                    attribution["portfolio_contribution_sum"],
                "weight_policy": attribution["weight_policy"],
                "reconciliation_note": attribution["reconciliation_note"],
            }
    convention = path.get("convention")
    if convention:
        convention += ("; the return series is the recorded Phase 56 "
                       "realized series (weights drift between rebalances); "
                       "attribution uses static stored-target weights "
                       "(approximation labelled)")
        convention += f"; scope: {analysis_scope}"
    drawdown_block = {
        "available": path.get("available", False),
        "reason": path.get("reason"),
        "convention": convention,
        "analysis_scope": analysis_scope,
        "decision_cutoff_timestamp": cutoff_timestamp,
        "max_drawdown": path.get("max_drawdown"),
        "episode_count": episode_count_total,
        "episodes_truncated": episode_count_total > len(episodes),
        "series": ({"timestamps": path["timestamps"],
                    "wealth": [round(v, 10) for v in path["wealth"]],
                    "drawdowns": [round(v, 10) for v in path["drawdowns"]]}
                   if path.get("available") else None),
        "attribution": attribution_block,
        "cost_attribution": {
            "available": False,
            "reason": ("no timestamp-aligned realized transaction-cost "
                       "series is stored for the selected drawdown interval"),
        },
    }

    # sensitivity (bounded one-at-a-time probes of the same book)
    sensitivity_rows = _sensitivity_rows(run, config, scenario, universe,
                                         asset_ids, asset_groups, weights,
                                         base_cov, cost_model, notional,
                                         result, constraints_cfg,
                                         assets_for_check)

    completeness = reconciliation["completeness"]
    if needs_risk and (cov_stress is None or cov_stress["matrix"] is None):
        completeness = "partial" if completeness == "complete" else completeness
    if reconciliation.get("stressed_cost_state") not in ("not_configured",
                                                         "available"):
        cost_reason_text = (reconciliation.get("stressed_cost_reason")
                            or "no linked component is applicable to "
                               "weight turnover")
        warnings.append(
            "a liquidity/cost stress was configured but the stressed cost "
            f"leg is unavailable ({cost_reason_text}); the net scenario "
            "return equals the gross shock return and is labelled "
            "accordingly")
    if reconciliation.get("net_basis_note"):
        warnings.append(reconciliation["net_basis_note"])
    if integrity == "invalid":
        warnings.append("the scenario definition is invalid (future-looking "
                        "or unverifiable); results are not causal evidence")

    stressed_cov_fp = None
    if cov_stress is not None and cov_stress["matrix"] is not None:
        stressed_cov_fp = fp_mod.matrix_fingerprint(
            "portfolio_stress_covariance_v1",
            [[round(float(v), 12) for v in row]
             for row in cov_stress["matrix"]])

    asset_rows = []
    for r in contributions["rows"]:
        aid = r["asset_id"]
        asset_rows.append({
            "asset_id": aid, "group": r.get("group"),
            "weight": r.get("weight"),
            "shock": r.get("shock"),
            "shock_source": result["resolved"]["sources"].get(aid),
            "contribution": r.get("contribution"),
            "abs_share": r.get("abs_share"),
            "drifted_weight": (drifted["weights"].get(aid)
                               if drifted.get("weights") else None),
            "status": "ok" if r.get("contribution") is not None
                      else "unavailable",
        })

    covariance_stress_block = None
    if cov_stress is not None:
        covariance_stress_block = {
            "available": cov_stress["matrix"] is not None,
            "reason": cov_stress.get("reason"),
            "report": cov_stress.get("report"),
            "report_after_repair": cov_stress.get("report_after"),
            "repair": cov_stress.get("repair"),
            "stressed_vols": cov_stress.get("stressed_vols"),
            "stressed_correlation": cov_stress.get("stressed_correlation"),
            "requested_vols": cov_stress.get("requested_vols"),
            "requested_correlation": cov_stress.get("requested_correlation"),
            "clamped": (cov_stress.get("corr_result") or {}).get("clamped"),
        }

    result_fp = fp_mod.result_fingerprint(
        run["configuration_fingerprint"], {
            "asset_results": asset_rows,
            "contribution_summary": {
                k: v for k, v in contributions.items() if k != "rows"},
            "reconciliation": reconciliation,
            "stressed_covariance_fingerprint": stressed_cov_fp,
            "covariance_stress": covariance_stress_block,
            "risk_summary": risk_summary,
            "risk_results": risk_rows,
            "constraint_results": constraint_rows,
            "cost_stress": cost_block,
            "drifted": drifted,
            "drawdown": drawdown_block,
            "episodes": episodes,
            "attribution_results": attribution_rows,
            "sensitivity_results": sensitivity_rows,
            "warnings": sorted(warnings),
            "completeness": completeness,
            "integrity": integrity,
        })

    store.replace_children(
        run_id,
        scenario={"scenario_definition_id": scenario["scenario_definition_id"],
                  "name": scenario["name"],
                  "description": scenario["description"],
                  "scenario_type": scenario["scenario_type"],
                  "source": scenario["source"],
                  "integrity": integrity,
                  "fingerprint": run["scenario_fingerprint"],
                  "definition": scenario},
        asset_rows=asset_rows,
        risk_rows=risk_rows,
        constraint_rows=constraint_rows,
        episodes=episodes,
        attribution_rows=attribution_rows,
        sensitivity_rows=sensitivity_rows,
        run_updates={
            "status": "completed",
            "integrity_status": integrity,
            "completeness_status": completeness,
            "scenario_count": len(sensitivity_rows),
            "scenario_return": reconciliation["net_scenario_return"],
            "scenario_pnl": reconciliation["scenario_pnl"],
            "stressed_volatility": (risk_summary or {}).get("stressed_volatility"),
            "baseline_volatility": (risk_summary or {}).get("baseline_volatility"),
            "breach_count": len(constraint_rows),
            "episode_count": episode_count_total,
            "max_drawdown": drawdown_block.get("max_drawdown"),
            "result_fingerprint": result_fp,
            "stressed_covariance_fingerprint": stressed_cov_fp,
            "reconciliation_json": json.dumps(reconciliation),
            "risk_summary_json": (json.dumps(risk_summary)
                                  if risk_summary else None),
            "cost_stress_json": (json.dumps(cost_block)
                                 if cost_block else None),
            "drawdown_json": json.dumps(drawdown_block),
            "covariance_stress_json": (json.dumps(covariance_stress_block)
                                       if covariance_stress_block else None),
            "drifted_json": json.dumps({
                "available": drifted.get("weights") is not None,
                "reason": drifted.get("reason"),
                "cash_weight": drifted.get("cash_weight"),
                "note": drifted.get("note"),
            }),
            "warnings_json": json.dumps(warnings),
            "completed_at": _now(),
            "duration_ms": int((time.monotonic() - t0) * 1000),
            "error_message": None,
        })

    run = store.get_run(run_id)
    assert run is not None
    if create_experiment and not run.get("experiment_id"):
        record = experiment_integration.record_experiment(
            name=f"Portfolio stress: {run['name']}",
            module="portfolio_stress_diagnostics",
            experiment_type="portfolio_stress_scenario",
            status="completed",
            parameters={
                "scenario_type": run["scenario_type"],
                "portfolio_run_id": run["portfolio_run_id"],
                "rebalance_id": run["portfolio_rebalance_id"],
                "integrity_status": integrity,
                "completeness_status": completeness,
                "configuration_fingerprint": run["configuration_fingerprint"],
                "result_fingerprint": result_fp,
            },
            metrics={
                "scenario_return": reconciliation["net_scenario_return"],
                "stressed_volatility":
                    (risk_summary or {}).get("stressed_volatility"),
                "breach_count": len(constraint_rows),
                "episode_count": drawdown_block.get("episode_count"),
                "max_drawdown": drawdown_block.get("max_drawdown"),
            },
            tags=["portfolio-stress"],
            source="portfolio_stress_diagnostics",
        )
        if record is not None:
            store.update_run(run_id, {"experiment_id": record["id"]})
    return get_run(run_id)


def _at(values: Optional[List[float]], i: int) -> Optional[float]:
    return values[i] if values is not None else None


def _ranks(values: Optional[List[float]]) -> Optional[List[int]]:
    if values is None:
        return None
    order = sorted(range(len(values)), key=lambda i: -values[i])
    ranks = [0] * len(values)
    for rank, i in enumerate(order, start=1):
        ranks[i] = rank
    return ranks


def _extreme(rows: List[Dict[str, Any]], key: str, fn) -> Optional[Dict[str, Any]]:
    candidates = [r for r in rows if r.get(key) is not None]
    if not candidates:
        return None
    row = fn(candidates, key=lambda r: r[key])
    return {"asset_id": row["asset_id"], key: row[key]}


def _drifted_breach_count(drifted, constraints_cfg,
                          assets_for_check) -> Optional[int]:
    """Drifted-book breach count for one evaluation; None = not evaluable
    (drifted weights unavailable), never a silent zero."""
    if not drifted or drifted.get("weights") is None:
        return None
    return len(pd_constraints.check_weights(
        drifted["weights"], constraints_cfg, assets_for_check, turnover=None))


def _sensitivity_rows(run, config, scenario, universe, asset_ids,
                      asset_groups, weights, base_cov, cost_model,
                      notional, base_result, constraints_cfg,
                      assets_for_check) -> List[Dict[str, Any]]:
    """One base row (the run's OWN scenario, on the same net basis as the
    run's reconciliation) plus one row per probe.  Probes are self-contained
    one-dimension scenarios around the same stored book — NOT perturbations
    of the configured scenario; every row states that basis."""
    rows: List[Dict[str, Any]] = []
    base_reconciliation = base_result["reconciliation"]
    base_row = {
        "dimension": "base", "value": None, "is_base": True,
        "scenario_return": base_reconciliation["net_scenario_return"],
        "stressed_volatility":
            (base_result["stressed_risk"]["volatility"]
             if base_result["stressed_risk"] else None),
        "contribution_hhi":
            base_result["contributions"]["concentration"].get("abs_hhi"),
        "breach_count": _drifted_breach_count(
            base_result["drifted"], constraints_cfg, assets_for_check),
        "cost_return": base_reconciliation["stressed_cost_return"],
        "completeness": base_reconciliation["completeness"],
        "status": "completed",
        "reason": ("the run's own scenario (net basis); breach_count on "
                   "every row counts the DRIFTED book only, unlike the "
                   "run-level breach_count which also counts the stored "
                   "book; probes below are self-contained one-dimension "
                   "scenarios around the same stored book, not "
                   "perturbations of this scenario"),
    }
    base_row["fingerprint"] = fp_mod.sensitivity_fingerprint(
        run["configuration_fingerprint"], base_row)
    rows.append(base_row)
    for dim in sorted(config["sensitivity"]):
        for value in config["sensitivity"][dim]:
            probe = _probe_scenario(dim, value, asset_ids)
            try:
                result = _evaluate_scenario_once(
                    probe, universe=universe, asset_ids=asset_ids,
                    asset_groups=asset_groups, weights=weights,
                    base_cov=base_cov, cost_model=cost_model,
                    notional=notional)
                row = {
                    "dimension": dim, "value": value, "is_base": False,
                    "scenario_return":
                        result["reconciliation"]["net_scenario_return"],
                    "stressed_volatility":
                        (result["stressed_risk"]["volatility"]
                         if result["stressed_risk"] else None),
                    "contribution_hhi":
                        result["contributions"]["concentration"].get("abs_hhi"),
                    "breach_count": _drifted_breach_count(
                        result["drifted"], constraints_cfg, assets_for_check),
                    "cost_return":
                        result["reconciliation"]["stressed_cost_return"],
                    "completeness":
                        result["reconciliation"]["completeness"],
                    "status": "completed", "reason": None,
                }
            except Exception as exc:  # a probe never voids the run
                row = {"dimension": dim, "value": value, "is_base": False,
                       "scenario_return": None, "stressed_volatility": None,
                       "contribution_hhi": None, "breach_count": None,
                       "cost_return": None, "completeness": "unavailable",
                       "status": "failed", "reason": str(exc)}
            row["fingerprint"] = fp_mod.sensitivity_fingerprint(
                run["configuration_fingerprint"], row)
            rows.append(row)
    return rows


def _probe_scenario(dim: str, value: float,
                    asset_ids: List[str]) -> Dict[str, Any]:
    """A self-contained one-dimension probe scenario around the same book."""
    base: Dict[str, Any] = {
        "scenario_definition_id": f"probe-{dim}",
        "name": f"probe {dim}", "description": "", "source": "sensitivity",
        "scenario_type": "combined_scenario",
        "units_note": "", "precedence": "", "metadata": {},
        "missing_shock_policy": "zero",
        "asset_shocks": {}, "group_shocks": {}, "global_shock": None,
        "volatility_stress": None, "correlation_stress": None,
        "liquidity_cost_stress": None, "historical": None,
    }
    if dim == "global_shock":
        base["global_shock"] = {"value": value, "unit": "return",
                                "as_return": value}
    elif dim == "volatility_multiplier":
        base["volatility_stress"] = {"mode": "multiplicative",
                                     "multiplier": value, "multipliers": {}}
    elif dim == "correlation_alpha":
        base["correlation_stress"] = {"mode": "toward_one", "alpha": value,
                                      "repair": "none",
                                      "formula": "rho + alpha * (1 - rho)"}
    elif dim == "spread_multiplier":
        base["liquidity_cost_stress"] = {"spread_multiplier": value}
    elif dim == "adv_multiplier":
        base["liquidity_cost_stress"] = {"adv_multiplier": value}
    else:  # impact_multiplier
        base["liquidity_cost_stress"] = {"impact_multiplier": value}
    return base


def invalidate_run(run_id: int, reason: str) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"portfolio-stress run {run_id} not found")
    if run["status"] == "invalidated":
        raise ConflictError("run is already invalidated")
    store.update_run(run_id, {"status": "invalidated", "error_message": reason,
                              "is_baseline": 0})
    return get_run(run_id)


# ---------------------------------------------------------------------------
# Baselines, comparison, export
# ---------------------------------------------------------------------------


def _baseline_scope(run: Dict[str, Any]) -> str:
    return "|".join([
        f"prun:{run['portfolio_run_id']}",
        f"reb:{run['portfolio_rebalance_id']}",
        f"w:{run['baseline_weight_fingerprint'] or 'none'}",
        f"cov:{run['baseline_covariance_fingerprint'] or 'none'}",
        f"scen:{run['scenario_fingerprint']}",
        f"ntl:{run['configuration'].get('notional') or 'none'}",
        "obs:{start}:{end}".format(
            start=((run["configuration"].get("scenario") or {})
                   .get("historical") or {}).get("start_timestamp", "none"),
            end=((run["configuration"].get("scenario") or {})
                 .get("historical") or {}).get("end_timestamp", "none")),
    ])


def mark_baseline(run_id: int) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"portfolio-stress run {run_id} not found")
    if run["status"] != "completed":
        raise ConflictError("baselines require a completed run")
    if run["integrity_status"] not in BASELINE_ACCEPTABLE_INTEGRITY:
        raise ConflictError(
            "baselines require verified scenario integrity — this run is "
            f"{run['integrity_status']}")
    if run["completeness_status"] not in BASELINE_ACCEPTABLE_COMPLETENESS:
        raise ConflictError(
            "baselines require a complete scenario result — this run is "
            f"{run['completeness_status']}")
    cov_stress = run.get("covariance_stress")
    if cov_stress is not None and not cov_stress.get("available", True):
        raise ConflictError(
            "baselines require a valid stressed covariance where risk "
            "stress is configured")
    if run.get("dataset_version_id"):
        version = dataset_store.get_version(run["dataset_version_id"])
        if version is None or version.get("invalidated_at"):
            raise ConflictError(
                "baselines require a currently valid linked dataset version")
    if not run["result_fingerprint"]:
        raise ConflictError("baselines require a result fingerprint")
    scope = _baseline_scope(run)
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
    return {"kind": kind, "field": field, "a": a, "b": b, "note": note}



def _shock_unit_signature(run: Dict[str, Any]) -> List[str]:
    scenario = run["configuration"].get("scenario") or {}
    entries: List[str] = []
    for prefix in ("asset_shocks", "group_shocks"):
        for key, spec in sorted((scenario.get(prefix) or {}).items()):
            entries.append(f"{prefix}:{key}:{spec.get('unit')}")
    if scenario.get("global_shock"):
        entries.append(f"global:{scenario['global_shock'].get('unit')}")
    if scenario.get("historical"):
        entries.append("historical:stored-simple-returns")
    return entries

def compare_runs(a_id: int, b_id: int) -> Dict[str, Any]:
    if a_id == b_id:
        raise PortfolioStressError("compare requires two different runs")
    a, b = get_run(a_id), get_run(b_id)
    comparability: List[str] = []
    if a["portfolio_run_id"] != b["portfolio_run_id"]:
        comparability.append("different portfolio runs — results are not "
                             "directly comparable")
    if a["baseline_weight_fingerprint"] != b["baseline_weight_fingerprint"]:
        comparability.append("different portfolio weights")
    if a["portfolio_rebalance_id"] != b["portfolio_rebalance_id"]:
        comparability.append("different rebalance identities")
    a_universe = (a["configuration"].get("portfolio_identity") or {}).get(
        "portfolio_universe_fingerprint")
    b_universe = (b["configuration"].get("portfolio_identity") or {}).get(
        "portfolio_universe_fingerprint")
    if a_universe != b_universe:
        comparability.append("different portfolio universes")
    if a["baseline_covariance_fingerprint"] != b["baseline_covariance_fingerprint"]:
        comparability.append("different baseline covariance estimates")
    if (a["configuration"].get("notional") or None) != \
            (b["configuration"].get("notional") or None):
        comparability.append("different notionals")
    if a.get("cost_model_fingerprint") != b.get("cost_model_fingerprint"):
        comparability.append("different linked cost models")
    if a["integrity_status"] != b["integrity_status"]:
        comparability.append("integrity states differ")
    if _shock_unit_signature(a) != _shock_unit_signature(b):
        comparability.append("different shock-unit definitions")
    identity = [_entry(f, a.get(f), b.get(f)) for f in (
        "scenario_type", "asset_count", "scenario_return", "scenario_pnl",
        "baseline_volatility", "stressed_volatility", "breach_count",
        "episode_count", "max_drawdown", "completeness_status",
        "integrity_status", "status", "portfolio_run_name")]
    a_c = {r["asset_id"]: r for r in store.list_asset_results(a_id)}
    b_c = {r["asset_id"]: r for r in store.list_asset_results(b_id)}
    contribution_rows = [{
        "asset_id": aid,
        "availability": ("both" if aid in a_c and aid in b_c
                         else ("only_in_a" if aid in a_c else "only_in_b")),
        "a_contribution": a_c.get(aid, {}).get("contribution"),
        "b_contribution": b_c.get(aid, {}).get("contribution"),
    } for aid in sorted(set(a_c) | set(b_c))]
    return {
        "a_id": a_id, "b_id": b_id,
        "comparability_warnings": comparability,
        "groups": {"identity": identity},
        "contributions": contribution_rows,
        "fingerprint_match": {
            "scenario": a["scenario_fingerprint"] == b["scenario_fingerprint"],
            "configuration": a["configuration_fingerprint"] == b["configuration_fingerprint"],
            "result": bool(a.get("result_fingerprint"))
            and a.get("result_fingerprint") == b.get("result_fingerprint"),
        },
        "baseline": {"a": a["is_baseline"], "b": b["is_baseline"]},
    }


def export(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    filters = filters or {}
    listing = store.list_runs(filters=filters, page=1,
                              page_size=store.MAX_PAGE_SIZE)
    runs = [_hydrate(r) for r in listing["items"]]
    payload: Dict[str, Any] = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "exported_at": _now(),
        "filters": {k: v for k, v in filters.items() if v is not None},
        "total_matching_runs": listing["total"],
        "truncated": listing["total"] > len(runs),
        "runs": runs,
        "scenarios": {}, "asset_results": {}, "risk_results": {},
        "constraint_results": {}, "episodes": {}, "attribution": {},
        "sensitivity": {},
    }
    for r in runs:
        payload["scenarios"][r["id"]] = store.get_scenario(r["id"])
        payload["asset_results"][r["id"]] = store.list_asset_results(r["id"])
        payload["risk_results"][r["id"]] = store.list_risk_results(r["id"])
        payload["constraint_results"][r["id"]] = \
            store.list_constraint_results(r["id"])
        payload["episodes"][r["id"]] = store.list_episodes(r["id"])
        payload["attribution"][r["id"]] = store.list_attribution(r["id"])
        payload["sensitivity"][r["id"]] = \
            store.list_sensitivity_results(r["id"])
    return payload


__all__ = [
    "BASELINE_ACCEPTABLE_INTEGRITY", "BASELINE_ACCEPTABLE_COMPLETENESS",
    "EXECUTION_ORDER", "PortfolioStressError", "NotFoundError",
    "ConflictError", "InternalExecutionError", "create_run", "get_run", "list_runs", "lab_summary",
    "execute_run", "invalidate_run", "mark_baseline", "compare_runs",
    "export",
]
