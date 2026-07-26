"""
Service layer for the Portfolio Attribution Lab (v1).

Documented, fingerprinted execution order:

1. validate the linked portfolio run and the explicit attribution policy
2. build the period/asset observation set from STORED weights and returns
3. validate the explicit benchmark definition (never auto-selected)
4. per period: asset contributions → portfolio market return → costs → net
5. per period: benchmark return → active return → Brinson decomposition
6. multi-period linking (arithmetic reference and/or Carino)
7. active-risk, concentration, regime and drawdown views
8. reconciliation status and result fingerprint

Every linked record — Phase 56 weights, Phase 55 cost estimates, Phase 54
regime assignments, Phase 57 drawdown episodes, Model Validation splits,
datasets and experiments — is consumed READ-ONLY.  The lab's only
cross-lab write is an optional NEW Experiment Registry record.
"""

from __future__ import annotations

import json
import logging
import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.dataset_registry import store as dataset_store
from app.experiment_registry import integration as experiment_integration
from app.experiment_registry import store as experiment_store
from app.experiment_registry.provenance import get_app_version, get_git_commit
from app.cost_diagnostics import store as cost_store
from app.model_validation import store as validation_store
from app.portfolio_diagnostics import store as pd_store
from app.portfolio_stress import store as stress_store
from app.regime_diagnostics import store as regime_store
from app.portfolio_attribution import EXPORT_SCHEMA_VERSION
from app.portfolio_attribution import activerisk as risk_mod
from app.portfolio_attribution import benchmarks as bench_mod
from app.portfolio_attribution import brinson as brinson_mod
from app.portfolio_attribution import contribution as contrib_mod
from app.portfolio_attribution import costs as cost_mod
from app.portfolio_attribution import fingerprints as fp_mod
from app.portfolio_attribution import linking as link_mod
from app.portfolio_attribution import observations as obs_mod
from app.portfolio_attribution import store

logger = logging.getLogger(__name__)

ATTRIBUTION_METHODS = ("contribution_only", "brinson")
COST_POLICIES = ("stored_rebalance_costs", "none")
RARE_REGIME_MIN_OBSERVATIONS = 10

EXECUTION_ORDER = [
    "validate_portfolio_and_policy", "build_observations",
    "validate_benchmark", "asset_contributions_and_costs",
    "benchmark_and_brinson", "multi_period_linking",
    "active_risk_regimes_drawdowns", "reconciliation",
]

BASELINE_ACCEPTABLE_INTEGRITY = ("verified_from_stored_rebalance",
                                 "verified_causal_weights")
BASELINE_ACCEPTABLE_COMPLETENESS = ("complete",)
BASELINE_ACCEPTABLE_RECONCILIATION = ("reconciled",)


class AttributionError(ValueError):
    """Invalid input/config (HTTP 422)."""


class NotFoundError(LookupError):
    """Unknown id (HTTP 404)."""


class ConflictError(RuntimeError):
    """State conflict (HTTP 409)."""


class InternalExecutionError(RuntimeError):
    """Unexpected execution failure (HTTP 500, sanitized message)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def _optional_positive_id(value: Any, field: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise AttributionError(f"{field} must be a positive integer")
    return value


def _dataset_identity(version: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "content_fingerprint": version.get("content_fingerprint"),
        "manifest_fingerprint": version.get("manifest_fingerprint"),
        "schema_fingerprint": version.get("schema_fingerprint"),
        "quality_status": version.get("quality_status"),
        "validation_status": version.get("validation_status"),
        "invalidated_at": version.get("invalidated_at"),
    }

def _load_portfolio(portfolio_run_id: Any) -> Dict[str, Any]:
    if isinstance(portfolio_run_id, bool) or not isinstance(portfolio_run_id, int):
        raise AttributionError("portfolio_run_id is required")
    prun = pd_store.get_run(portfolio_run_id)
    if prun is None:
        raise AttributionError(f"portfolio run {portfolio_run_id} not found")
    if prun["status"] != "completed":
        raise AttributionError(
            "attribution requires a completed portfolio run")
    return prun


def _indexed_rebalances(prun: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Stored rebalances with the decision_index the timeline implies."""
    timestamps = prun["universe"]["timestamps"]
    index = {ts: i for i, ts in enumerate(timestamps)}
    rows = pd_store.list_rebalances(prun["id"])
    decisions = [r.get("decision_timestamp") for r in rows]
    if len(set(decisions)) != len(decisions):
        raise AttributionError("linked portfolio has duplicate rebalance decisions")
    unknown = [ts for ts in decisions if ts not in index]
    if unknown:
        raise AttributionError(
            "linked portfolio has rebalance decisions outside its timeline")
    return [{**r, "decision_index": index[r["decision_timestamp"]]}
            for r in rows]


def create_run(payload: Dict[str, Any], *,
               demo_key: Optional[str] = None) -> Dict[str, Any]:
    name = (payload.get("name") or "").strip()
    if not name or len(name) > 200:
        raise AttributionError("name must be 1..200 characters")

    method = payload.get("attribution_method", "brinson")
    if method not in ATTRIBUTION_METHODS:
        raise AttributionError(
            f"attribution_method must be one of {', '.join(ATTRIBUTION_METHODS)}")
    variant = payload.get("brinson_variant", "brinson_fachler")
    if variant not in brinson_mod.BRINSON_VARIANTS:
        raise AttributionError(
            "brinson_variant must be one of "
            + ", ".join(brinson_mod.BRINSON_VARIANTS))
    linking_method = payload.get("linking_method", "arithmetic")
    if linking_method not in link_mod.LINKING_METHODS:
        raise AttributionError(
            f"linking_method must be one of {', '.join(link_mod.LINKING_METHODS)}")
    cost_policy = payload.get("cost_policy", "stored_rebalance_costs")
    if cost_policy not in COST_POLICIES:
        raise AttributionError(
            f"cost_policy must be one of {', '.join(COST_POLICIES)}")

    try:
        policy = obs_mod.validate_policy(payload.get("policy"))
    except obs_mod.ObservationError as exc:
        raise AttributionError(str(exc))

    prun = _load_portfolio(payload.get("portfolio_run_id"))
    rebalances = _indexed_rebalances(prun)

    window = None
    if payload.get("observation_start") or payload.get("observation_end"):
        start = payload.get("observation_start")
        end = payload.get("observation_end")
        if not isinstance(start, str) or not isinstance(end, str):
            raise AttributionError(
                "an observation window needs both start and end timestamps")
        window = (start, end)

    try:
        observations = obs_mod.build_observations(prun, rebalances, policy,
                                                  window=window)
    except obs_mod.ObservationError as exc:
        raise AttributionError(str(exc))

    integrity_block = obs_mod.classify_integrity(prun, policy, rebalances)

    portfolio_returns_by_period = [
        {r["asset_id"]: r["asset_return"] for r in p["rows"]}
        for p in observations["periods"]]
    try:
        benchmark = bench_mod.validate_benchmark(
            payload.get("benchmark"),
            portfolio_asset_ids=observations["asset_ids"],
            portfolio_groups=observations["groups"],
            period_count=observations["period_count"],
            period_starts=[p["period_start"]
                           for p in observations["periods"]])
    except bench_mod.BenchmarkError as exc:
        raise AttributionError(str(exc))
    if benchmark.get("configured"):
        benchmark["frequency"] = policy["return_frequency"]
        benchmark["period_start"] = observations["observation_start"]
        benchmark["period_end"] = observations["observation_end"]
        portfolio_currencies = {asset.get("currency")
                                for asset in prun["universe"]["assets"]
                                if asset.get("currency")}
        benchmark_currency = (benchmark.get("metadata") or {}).get("currency")
        if portfolio_currencies and (
                len(portfolio_currencies) != 1
                or benchmark_currency not in portfolio_currencies):
            raise AttributionError(
                "portfolio and benchmark currencies do not match; currency "
                "conversion is never inferred or performed")
    if method == "brinson" and not benchmark.get("configured"):
        raise AttributionError(
            "Brinson attribution requires an explicit benchmark definition; "
            "a benchmark is never selected automatically")

    # Linked records are read-only and their material identities are pinned.
    linked: Dict[str, Any] = {}
    cost_run_id = _optional_positive_id(
        payload.get("cost_diagnostic_run_id"), "cost_diagnostic_run_id")
    if cost_run_id is not None:
        crun = cost_store.get_run(cost_run_id)
        if crun is None or crun["status"] != "completed":
            raise AttributionError(
                "cost linkage requires a completed cost-diagnostic run")
        linked.update({
            "cost_model_fingerprint": crun["cost_model_fingerprint"],
            "cost_configuration_fingerprint": crun["configuration_fingerprint"],
            "cost_result_fingerprint": crun.get("result_fingerprint"),
        })
    regime_run_id = _optional_positive_id(
        payload.get("regime_run_id"), "regime_run_id")
    regime_definition_id = payload.get("regime_definition_id")
    if regime_run_id is not None:
        rrun = regime_store.get_run(regime_run_id)
        if rrun is None or rrun["status"] != "completed":
            raise AttributionError(
                "regime attribution requires a completed regime run")
        if not regime_definition_id:
            raise AttributionError(
                "regime attribution requires regime_definition_id")
        definition = next((d for d in regime_store.list_definitions(rrun["id"])
                           if d["definition_id"] == regime_definition_id), None)
        if definition is None:
            raise AttributionError(
                f"regime definition {regime_definition_id!r} not found in run "
                f"{rrun['id']}")
        linked.update({
            "regime_configuration_fingerprint": rrun["configuration_fingerprint"],
            "regime_result_fingerprint": rrun.get("result_fingerprint"),
            "regime_definition_fingerprint":
                definition["definition_fingerprint"],
        })
    elif regime_definition_id:
        raise AttributionError("regime_definition_id requires regime_run_id")
    stress_run_id = _optional_positive_id(
        payload.get("stress_run_id"), "stress_run_id")
    if stress_run_id is not None:
        srun = stress_store.get_run(stress_run_id)
        if srun is None or srun["status"] != "completed":
            raise AttributionError(
                "drawdown attribution requires a completed portfolio-stress run")
        if srun["portfolio_run_id"] != prun["id"]:
            raise AttributionError(
                "the linked stress run analyses a different portfolio run; "
                "drawdown episodes are never transplanted between books")
        linked.update({
            "stress_configuration_fingerprint": srun["configuration_fingerprint"],
            "stress_result_fingerprint": srun.get("result_fingerprint"),
        })
    validation_run_id = _optional_positive_id(
        payload.get("validation_run_id"), "validation_run_id")
    if validation_run_id is not None:
        vrun = validation_store.get_run(validation_run_id)
        if vrun is None or vrun["status"] != "completed":
            raise AttributionError(
                "validation linkage requires a completed model-validation run")
        if vrun.get("leakage_clean") is not True \
                or vrun.get("invalid_split_count", 0) != 0:
            raise AttributionError(
                "validation linkage requires a leakage-clean run with no "
                "invalid splits")
        linked.update({
            "validation_configuration_fingerprint":
                vrun.get("configuration_fingerprint"),
            "validation_result_fingerprint": vrun.get("result_fingerprint"),
            "validation_leakage_clean": True,
            "validation_invalid_split_count": 0,
        })
    dataset_version_id = _optional_positive_id(
        payload.get("dataset_version_id"), "dataset_version_id")
    if dataset_version_id is None:
        dataset_version_id = prun.get("dataset_version_id")
    dataset_identity: Dict[str, Any] = {}
    if dataset_version_id is not None:
        version = dataset_store.get_version(dataset_version_id)
        if version is None:
            raise AttributionError(
                f"dataset version {dataset_version_id} not found")
        if version.get("invalidated_at"):
            raise AttributionError(
                "an invalidated dataset version cannot support verified attribution")
        dataset_identity = _dataset_identity(version)
        linked["dataset_identity"] = dataset_identity

    benchmark_dataset_id = benchmark.get("dataset_version_id")
    if benchmark_dataset_id is not None:
        benchmark_version = dataset_store.get_version(benchmark_dataset_id)
        if benchmark_version is None:
            raise AttributionError(
                f"benchmark dataset version {benchmark_dataset_id} not found")
        if benchmark_version.get("invalidated_at"):
            raise AttributionError(
                "an invalidated benchmark dataset cannot support attribution")
        benchmark["dataset_identity"] = _dataset_identity(benchmark_version)
        linked["benchmark_dataset_identity"] = benchmark["dataset_identity"]

    benchmark["fingerprint"] = (
        fp_mod.benchmark_definition_fingerprint(benchmark)
        if benchmark.get("configured") else None)

    observation_fp = fp_mod.observation_universe_fingerprint(
        observations, benchmark, dataset_identity,
        policy["weight_timing_policy"])
    policy_fp = fp_mod.attribution_policy_fingerprint(
        policy, method, variant if method == "brinson" else None,
        linking_method, cost_policy)
    portfolio_identity = {
        "portfolio_configuration_fingerprint": prun["configuration_fingerprint"],
        "portfolio_result_fingerprint": prun.get("result_fingerprint"),
        "method": prun["method"],
    }
    benchmark_identity = {
        "configured": benchmark.get("configured", False),
        "benchmark_id": benchmark.get("benchmark_id"),
        "kind": benchmark.get("kind"),
        "source": benchmark.get("source"),
        "fingerprint": benchmark.get("fingerprint"),
    }
    filters = {"observation_start": observations["observation_start"],
               "observation_end": observations["observation_end"]}
    config_fp = fp_mod.configuration_fingerprint(
        observation_fp, policy_fp, portfolio_identity, benchmark_identity,
        linked, filters)

    configuration = {
        "policy": policy,
        "attribution_method": method,
        "brinson_variant": variant if method == "brinson" else None,
        "linking_method": linking_method,
        "cost_policy": cost_policy,
        "benchmark": benchmark,
        "portfolio_identity": {**portfolio_identity,
                               "portfolio_run_id": prun["id"]},
        "linked": linked,
        "execution_order": EXECUTION_ORDER,
        "integrity_warnings": integrity_block["warnings"],
        "observation_summary": {
            "asset_ids": observations["asset_ids"],
            "groups": observations["groups"],
            "period_count": observations["period_count"],
            "unavailable_periods": observations["unavailable_periods"],
        },
        "factor_attribution": (
            "deferred in v1: no validated exposure and factor-return matrices "
            "exist in this repository, and factors are never inferred from "
            "asset names"),
        "scope_note": (
            "measured contributions and effects under the stated convention; "
            "not evidence of alpha, manager skill, or a preferred portfolio"),
    }

    run = store.insert_run({
        "name": name, "description": payload.get("description", ""),
        "attribution_method": method,
        "brinson_variant": variant if method == "brinson" else None,
        "linking_method": linking_method,
        "return_convention": policy["return_convention"],
        "return_frequency": policy["return_frequency"],
        "weight_timing_policy": policy["weight_timing_policy"],
        "benchmark_timing_policy": policy["benchmark_timing_policy"],
        "observation_start": observations["observation_start"],
        "observation_end": observations["observation_end"],
        "asset_count": len(observations["asset_ids"]),
        "group_count": len(observations["distinct_groups"]),
        "period_count": observations["period_count"],
        "integrity_status": integrity_block["integrity"],
        "configuration": configuration,
        "observation_fingerprint": observation_fp,
        "policy_fingerprint": policy_fp,
        "configuration_fingerprint": config_fp,
        "warnings": integrity_block["warnings"],
        "portfolio_run_id": prun["id"],
        "dataset_version_id": dataset_version_id,
        "cost_diagnostic_run_id": cost_run_id,
        "regime_run_id": regime_run_id,
        "regime_definition_id": regime_definition_id,
        "stress_run_id": stress_run_id,
        "validation_run_id": validation_run_id,
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
        raise NotFoundError(f"portfolio-attribution run {run_id} not found")
    return _hydrate(run)


def _hydrate(run: Dict[str, Any]) -> Dict[str, Any]:
    run["portfolio_run_name"] = run["portfolio_method"] = None
    run["dataset_name"] = run["dataset_version_label"] = None
    run["dataset_invalidated"] = None
    run["dataset_manifest_fingerprint"] = None
    run["dataset_provenance_status"] = run["dataset_quality_status"] = None
    run["cost_run_name"] = run["cost_model_fingerprint"] = None
    run["regime_run_name"] = None
    run["stress_run_name"] = None
    run["validation_run_name"] = run["validation_leakage_clean"] = None
    run["experiment_name"] = None
    run["benchmark_name"] = None
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
            run["dataset_provenance_status"] = (dataset["provenance_status"]
                                                if dataset else None)
            run["dataset_quality_status"] = version["quality_status"]
    if run.get("cost_diagnostic_run_id"):
        crun = cost_store.get_run(run["cost_diagnostic_run_id"])
        if crun:
            run["cost_run_name"] = crun["name"]
            run["cost_model_fingerprint"] = crun["cost_model_fingerprint"]
    if run.get("regime_run_id"):
        rrun = regime_store.get_run(run["regime_run_id"])
        if rrun:
            run["regime_run_name"] = rrun["name"]
    if run.get("stress_run_id"):
        srun = stress_store.get_run(run["stress_run_id"])
        if srun:
            run["stress_run_name"] = srun["name"]
    if run.get("validation_run_id"):
        vrun = validation_store.get_run(run["validation_run_id"])
        if vrun:
            run["validation_run_name"] = vrun["name"]
            run["validation_leakage_clean"] = vrun.get("leakage_clean")
    if run.get("experiment_id"):
        exp = experiment_store.get_experiment(run["experiment_id"])
        run["experiment_name"] = exp["name"] if exp else None
    benchmark = (run.get("configuration") or {}).get("benchmark") or {}
    if benchmark.get("configured"):
        run["benchmark_name"] = benchmark.get("name")
    return run


def list_runs(**kwargs: Any) -> Dict[str, Any]:
    result = store.list_runs(**kwargs)
    result["items"] = [_hydrate(r) for r in result["items"]]
    return result


def lab_summary() -> Dict[str, Any]:
    return store.lab_summary()


# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------


def _assert_pinned(label: str, current: Dict[str, Any],
                   expected: Dict[str, Any], mapping: Dict[str, str]) -> None:
    for expected_key, current_key in mapping.items():
        if expected_key in expected and expected[expected_key] != current.get(current_key):
            raise AttributionError(
                f"the linked {label} changed since this attribution run was "
                "created; create a new attribution run")


def _revalidate_inputs(run: Dict[str, Any]
                       ) -> Tuple[Dict[str, Any], List[Dict[str, Any]],
                                  Dict[str, Any]]:
    """Reload every linked identity and rebuild the observation fingerprint."""
    config = run["configuration"]
    expected = config.get("linked") or {}
    prun = pd_store.get_run(run["portfolio_run_id"])
    if prun is None or prun["status"] != "completed":
        raise AttributionError(
            "the linked portfolio run is no longer available/completed")
    _assert_pinned("portfolio run", prun, config["portfolio_identity"], {
        "portfolio_configuration_fingerprint": "configuration_fingerprint",
        "portfolio_result_fingerprint": "result_fingerprint",
    })
    if run.get("cost_diagnostic_run_id"):
        current = cost_store.get_run(run["cost_diagnostic_run_id"])
        if current is None or current["status"] != "completed":
            raise AttributionError("the linked cost-diagnostic run is unavailable")
        _assert_pinned("cost-diagnostic run", current, expected, {
            "cost_model_fingerprint": "cost_model_fingerprint",
            "cost_configuration_fingerprint": "configuration_fingerprint",
            "cost_result_fingerprint": "result_fingerprint",
        })
    if run.get("regime_run_id"):
        current = regime_store.get_run(run["regime_run_id"])
        if current is None or current["status"] != "completed":
            raise AttributionError("the linked regime run is unavailable")
        _assert_pinned("regime run", current, expected, {
            "regime_configuration_fingerprint": "configuration_fingerprint",
            "regime_result_fingerprint": "result_fingerprint",
        })
        definition = next((d for d in regime_store.list_definitions(current["id"])
                           if d["definition_id"] == run["regime_definition_id"]),
                          None)
        if definition is None:
            raise AttributionError("the linked regime definition is unavailable")
        _assert_pinned("regime definition", definition, expected, {
            "regime_definition_fingerprint": "definition_fingerprint",
        })
    if run.get("stress_run_id"):
        current = stress_store.get_run(run["stress_run_id"])
        if current is None or current["status"] != "completed" \
                or current["portfolio_run_id"] != prun["id"]:
            raise AttributionError("the linked stress run is unavailable or mismatched")
        _assert_pinned("stress run", current, expected, {
            "stress_configuration_fingerprint": "configuration_fingerprint",
            "stress_result_fingerprint": "result_fingerprint",
        })
    if run.get("validation_run_id"):
        current = validation_store.get_run(run["validation_run_id"])
        if current is None or current["status"] != "completed" \
                or current.get("leakage_clean") is not True \
                or current.get("invalid_split_count", 0) != 0:
            raise AttributionError(
                "the linked validation run is unavailable or no longer "
                "leakage-clean")
        _assert_pinned("validation run", current, expected, {
            "validation_configuration_fingerprint": "configuration_fingerprint",
            "validation_result_fingerprint": "result_fingerprint",
            "validation_leakage_clean": "leakage_clean",
            "validation_invalid_split_count": "invalid_split_count",
        })

    dataset_identity: Dict[str, Any] = {}
    if run.get("dataset_version_id"):
        version = dataset_store.get_version(run["dataset_version_id"])
        if version is None or version.get("invalidated_at"):
            raise AttributionError(
                "the linked dataset is missing or has been invalidated")
        dataset_identity = _dataset_identity(version)
        if "dataset_identity" in expected \
                and expected["dataset_identity"] != dataset_identity:
            raise AttributionError("the linked dataset identity changed")
    benchmark = config["benchmark"]
    if benchmark.get("dataset_version_id"):
        version = dataset_store.get_version(benchmark["dataset_version_id"])
        if version is None or version.get("invalidated_at"):
            raise AttributionError(
                "the benchmark dataset is missing or has been invalidated")
        identity = _dataset_identity(version)
        if "benchmark_dataset_identity" in expected \
                and expected["benchmark_dataset_identity"] != identity:
            raise AttributionError("the benchmark dataset identity changed")

    rebalances = _indexed_rebalances(prun)
    policy = config["policy"]
    window = (run["observation_start"], run["observation_end"])
    observations = obs_mod.build_observations(
        prun, rebalances, policy,
        window=(window[0], window[1]) if window[0] and window[1] else None)
    observation_fp = fp_mod.observation_universe_fingerprint(
        observations, benchmark, dataset_identity,
        policy["weight_timing_policy"])
    if observation_fp != run["observation_fingerprint"]:
        raise AttributionError(
            "the attribution observation universe changed since creation")
    return prun, rebalances, observations

def execute_run(run_id: int, *, create_experiment: bool = False) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"portfolio-attribution run {run_id} not found")
    if run["status"] == "invalidated":
        raise ConflictError("run is invalidated; create a new run instead")
    t0 = time.monotonic()
    store.update_run(run_id, {"status": "running", "error_message": None})
    try:
        return _execute_body(run_id, run, t0, create_experiment)
    except (NotFoundError, ConflictError):
        raise
    except AttributionError as exc:
        store.mark_failed(run_id, str(exc), _now())
        raise
    except Exception:
        logger.exception("unexpected portfolio-attribution execution failure")
        store.mark_failed(
            run_id, "internal error during attribution execution", _now())
        raise InternalExecutionError(
            "internal error during attribution execution; the run is marked "
            "failed with the stored error message")


def _execute_body(run_id: int, run: Dict[str, Any], t0: float,
                  create_experiment: bool) -> Dict[str, Any]:
    config = run["configuration"]
    policy = config["policy"]
    tolerance = policy["reconciliation_tolerance"]
    method = config["attribution_method"]
    variant = config.get("brinson_variant")
    warnings: List[str] = list(config.get("integrity_warnings") or [])

    # Steps 1-2: revalidate all linked identities and observations.
    prun, rebalances, observations = _revalidate_inputs(run)
    asset_ids = observations["asset_ids"]
    groups = observations["groups"]
    periods = observations["periods"]
    if observations["unavailable_periods"]:
        warnings.append(
            f"{len(observations['unavailable_periods'])} period(s) have no "
            "stored beginning-of-period weights and are excluded; they are "
            "never back-filled")

    # step 3: benchmark
    benchmark = config["benchmark"]
    portfolio_returns_by_period = [
        {r["asset_id"]: r["asset_return"] for r in p["rows"]} for p in periods]
    bench_returns_by_period: List[Dict[str, float]] = []
    bench_weight_path: List[Optional[Dict[str, float]]] = []
    if benchmark.get("configured"):
        bench_returns_by_period = bench_mod.benchmark_returns_by_period(
            benchmark, portfolio_returns_by_period)
        bench_weight_path = bench_mod.benchmark_weight_path(
            benchmark, bench_returns_by_period)
        if not benchmark.get("weight_sum_is_one"):
            warnings.append(
                f"benchmark weights sum to {benchmark['weight_sum']:.10g}, not "
                "1; they are used as declared and never renormalized")
        if benchmark.get("benchmark_only_assets"):
            warnings.append(
                "benchmark-only assets (not held by the portfolio): "
                + ", ".join(benchmark["benchmark_only_assets"]))
        if benchmark.get("portfolio_only_assets"):
            warnings.append(
                "portfolio-only assets (absent from the benchmark): "
                + ", ".join(benchmark["portfolio_only_assets"]))

    # step 4-5: per-period contributions, costs, benchmark and Brinson
    cost_rows = (cost_mod.period_costs([p["period_id"] for p in periods],
                                       [p["period_start"] for p in periods],
                                       rebalances)
                 if config["cost_policy"] == "stored_rebalance_costs" else [])
    cost_by_period = {r["period_id"]: r for r in cost_rows}

    period_results: List[Dict[str, Any]] = []
    period_rows: List[Dict[str, Any]] = []
    brinson_periods: List[Dict[str, Any]] = []
    market_returns: List[float] = []
    benchmark_returns: List[float] = []

    for idx, period in enumerate(periods):
        contributions = contrib_mod.period_contributions(period["rows"])
        market_return = contributions["portfolio_market_return"]
        market_returns.append(market_return)
        portfolio_groups = contrib_mod.group_aggregate(contributions["rows"])

        cost_row = cost_by_period.get(period["period_id"])
        cost_return = cost_row["total_cost_return"] if cost_row else None
        net_return = (market_return - cost_return
                      if cost_return is not None else None)

        benchmark_return = None
        benchmark_groups: Dict[str, Dict[str, Any]] = {}
        brinson_result = None
        if benchmark.get("configured"):
            bench_weights = bench_weight_path[idx]
            if bench_weights is None:
                warnings.append(
                    f"benchmark weights are unavailable for period "
                    f"{period['period_id']} (its buy-and-hold book was wiped "
                    "out); benchmark-relative results are withheld for it")
            else:
                bench_rows = [{
                    "asset_id": aid,
                    "group_id": benchmark["groups"][aid],
                    "portfolio_beginning_weight": bench_weights[aid],
                    "asset_return": bench_returns_by_period[idx][aid],
                } for aid in benchmark["asset_ids"]]
                bench_contrib = contrib_mod.period_contributions(bench_rows)
                benchmark_return = bench_contrib["portfolio_market_return"]
                benchmark_groups = contrib_mod.group_aggregate(
                    bench_contrib["rows"])
                benchmark_returns.append(benchmark_return)
                if method == "brinson":
                    brinson_result = brinson_mod.brinson_period(
                        portfolio_groups, benchmark_groups,
                        benchmark_total_return=benchmark_return,
                        portfolio_return=market_return,
                        benchmark_return=benchmark_return,
                        variant=variant, tolerance=tolerance)
                    brinson_periods.append(brinson_result)

        active_return = (market_return - benchmark_return
                         if benchmark_return is not None else None)
        period_results.append({
            "period": period,
            "contributions": contributions,
            "portfolio_groups": portfolio_groups,
            "benchmark_groups": benchmark_groups,
            "market_return": market_return,
            "benchmark_return": benchmark_return,
            "active_return": active_return,
            "cost_return": cost_return,
            "net_return": net_return,
            "brinson": brinson_result,
        })
        period_rows.append({
            "period_id": period["period_id"],
            "period_start": period["period_start"],
            "period_end": period["period_end"],
            "information_available_at": period["information_available_at"],
            "portfolio_market_return": market_return,
            "transaction_cost_return": cost_return,
            "cost_state": cost_row["state"] if cost_row else None,
            "portfolio_net_return": net_return,
            "benchmark_return": benchmark_return,
            "active_return": active_return,
            "allocation_effect": (brinson_result or {}).get("allocation_effect"),
            "selection_effect": (brinson_result or {}).get("selection_effect"),
            "interaction_effect": (brinson_result or {}).get("interaction_effect"),
            "residual": (brinson_result or {}).get("residual"),
            "reconciliation_state": (brinson_result or {}).get(
                "reconciliation_state"),
            "cash_weight": contributions["cash_weight"],
            "regime_label": None,
        })

    # step 6: multi-period linking
    linking = None
    if benchmark.get("configured") and len(benchmark_returns) == len(market_returns):
        effects_for_linking = [
            {k: (p["brinson"] or {}).get(k) for k in
             ("allocation_effect", "selection_effect", "interaction_effect",
              "residual")}
            for p in period_results]
        linking = link_mod.link_effects(
            effects_for_linking, market_returns, benchmark_returns,
            config["linking_method"], tolerance)
        if linking.get("available") is False and linking.get("reason"):
            warnings.append(f"multi-period linking unavailable: "
                            f"{linking['reason']}")
        elif linking.get("within_tolerance") is False:
            warnings.append(
                "linked effects do not reconcile with the linking target "
                f"within {tolerance:g}; the residual is reported, not hidden")
    elif benchmark.get("configured"):
        warnings.append(
            "some periods have no benchmark observation, so multi-period "
            "linking is withheld (partial-period linking is never implied)")

    # aggregates
    asset_rows = contrib_mod.aggregate_asset_results(period_results, asset_ids,
                                                     groups)
    asset_linking = link_mod.link_contributions(
        [{row["asset_id"]: row["contribution"]
          for row in result["contributions"]["rows"]}
         for result in period_results],
        market_returns, config["linking_method"])
    linked_values = asset_linking.get("values") or {}
    for row in asset_rows:
        row["linked_contribution"] = linked_values.get(row["asset_id"])
    group_rows = contrib_mod.aggregate_group_results(asset_rows)
    brinson_rows = (brinson_mod.aggregate_brinson(brinson_periods)
                    if brinson_periods else [])
    if linking and linking.get("available") and linking.get("smoothing_factors"):
        _apply_linked_group_effects(brinson_rows, brinson_periods, linking)

    cost_block = (cost_mod.aggregate_costs(
        cost_rows, {p["period_id"]: r["market_return"]
                    for p, r in zip(periods, period_results)})
        if cost_rows else None)
    if cost_block and cost_block["completeness"] == "partial":
        warnings.append(
            "some traded periods have no stored cost estimate; the net figure "
            "covers the costed subset only and states that basis")

    active_risk_block = None
    active_dd = None
    if benchmark.get("configured") and len(benchmark_returns) == len(market_returns):
        active_risk_block = risk_mod.active_risk(
            market_returns, benchmark_returns,
            periods_per_year=obs_mod.periods_per_year(policy["return_frequency"]),
            frequency=policy["return_frequency"])
        if active_risk_block.get("information_ratio_state") == "unavailable":
            warnings.append(
                "information ratio unavailable: "
                + str(active_risk_block.get("information_ratio_reason")))
        active_dd = risk_mod.active_drawdown(
            risk_mod.active_series(market_returns, benchmark_returns))

    concentration_block = risk_mod.concentration(
        [r["arithmetic_contribution"] for r in asset_rows], label="asset")
    group_concentration = risk_mod.concentration(
        [r["arithmetic_contribution"] for r in group_rows], label="group")
    period_concentration = risk_mod.concentration(market_returns,
                                                  label="period")

    # step 7: regime + drawdown views
    regime_rows, regime_note = _regime_rows(run, prun, periods, period_results,
                                            period_rows, warnings)
    drawdown_rows = _drawdown_rows(run, periods, period_results, tolerance)

    # step 8: reconciliation + totals
    total_market = sum(market_returns)
    total_benchmark = (sum(benchmark_returns)
                       if benchmark.get("configured") and benchmark_returns
                       else None)
    total_active = (total_market - total_benchmark
                    if total_benchmark is not None else None)
    total_cost = (cost_block or {}).get("total_cost_return")
    total_net = ((cost_block or {}).get("net_return_costed_periods")
                 if cost_block else None)

    asset_sum = sum(r["arithmetic_contribution"] for r in asset_rows)
    group_sum = sum(r["arithmetic_contribution"] for r in group_rows)
    contribution_reconciled = abs(asset_sum - total_market) <= tolerance
    group_reconciled = abs(group_sum - asset_sum) <= tolerance
    if not contribution_reconciled:
        warnings.append(
            "asset contributions do not sum to the portfolio market return "
            f"within {tolerance:g}; the difference is reported, not hidden")
    if not group_reconciled:
        warnings.append(
            "group totals do not match the asset totals within "
            f"{tolerance:g}; the difference is reported, not hidden")

    brinson_reconciled = all(p.get("within_tolerance", True)
                             for p in brinson_periods)
    if brinson_periods and not brinson_reconciled:
        warnings.append(
            "one or more periods carry a Brinson residual outside "
            f"{tolerance:g}; residuals are reported verbatim and never "
            "redistributed into the three effects")

    reconciliation_status = (
        "reconciled" if contribution_reconciled and group_reconciled
        and brinson_reconciled else "residual")

    completeness = "complete"
    if observations["unavailable_periods"]:
        completeness = "partial"
    if benchmark.get("configured") and len(benchmark_returns) != len(market_returns):
        completeness = "partial"
    if cost_block and cost_block["completeness"] == "partial":
        completeness = "partial"
    if method == "brinson" and any(p.get("unavailable_terms")
                                   for p in brinson_periods):
        completeness = "partial"

    integrity = run["integrity_status"]
    if integrity == "invalid":
        warnings.append(
            "the weight-timing declaration is invalid; these results are "
            "descriptive only and the run can never become a baseline")

    summary = {
        "portfolio_market_return_arithmetic": total_market,
        "benchmark_return_arithmetic": total_benchmark,
        "active_return_arithmetic": total_active,
        "asset_contribution_sum": asset_sum,
        "group_contribution_sum": group_sum,
        "contribution_reconciled": contribution_reconciled,
        "group_reconciled": group_reconciled,
        "brinson_reconciled": brinson_reconciled if brinson_periods else None,
        "tolerance": tolerance,
        "time_weighted_return": link_mod.time_weighted_return(
            market_returns, supports_twr=True),
        "benchmark_time_weighted_return": (
            link_mod.time_weighted_return(benchmark_returns, supports_twr=True)
            if benchmark.get("configured") and benchmark_returns else None),
        "active_drawdown": active_dd,
        "group_concentration": group_concentration,
        "asset_contribution_linking": asset_linking,
        "period_concentration": period_concentration,
        "regime_note": regime_note,
        "execution_order": EXECUTION_ORDER,
    }

    result_fp = fp_mod.result_fingerprint(
        run["configuration_fingerprint"], period_rows, asset_rows, group_rows,
        brinson_rows, linking, cost_block, active_risk_block,
        {"asset": concentration_block, "group": group_concentration,
         "period": period_concentration}, regime_rows, drawdown_rows,
        summary, warnings, integrity, completeness, reconciliation_status)

    benchmark_record = None
    if benchmark.get("configured"):
        benchmark_record = {
            "benchmark_id": benchmark["benchmark_id"],
            "name": benchmark["name"],
            "description": benchmark.get("description", ""),
            "source": benchmark["source"], "kind": benchmark["kind"],
            "return_convention": benchmark["return_convention"],
            "timing_policy": benchmark["timing_policy"],
            "asset_ids": benchmark["asset_ids"],
            "weight_sum": benchmark["weight_sum"],
            "definition": {k: benchmark.get(k) for k in
                           ("asset_ids", "groups", "base_weights", "weights_per_period",
                            "returns", "kind", "source", "weight_sum",
                            "portfolio_only_assets", "benchmark_only_assets",
                            "dataset_version_id", "dataset_identity", "metadata",
                            "period_starts", "information_available_at",
                            "frequency", "period_start", "period_end")},
            "fingerprint": benchmark["fingerprint"],
        }

    store.replace_children(
        run_id, benchmark=benchmark_record, period_rows=period_rows,
        asset_rows=asset_rows, group_rows=group_rows,
        brinson_rows=brinson_rows, regime_rows=regime_rows,
        drawdown_rows=drawdown_rows,
        run_updates={
            "status": "completed",
            "completeness_status": completeness,
            "reconciliation_status": reconciliation_status,
            "period_count": len(periods),
            "group_count": len(group_rows),
            "portfolio_market_return": total_market,
            "portfolio_net_return": total_net,
            "benchmark_return": total_benchmark,
            "active_return": total_active,
            "total_cost_return": total_cost,
            "tracking_error": (active_risk_block or {}).get("tracking_error"),
            "information_ratio": (active_risk_block or {}).get(
                "information_ratio"),
            "result_fingerprint": result_fp,
            "summary_json": json.dumps(summary),
            "linking_json": json.dumps(linking) if linking else None,
            "cost_json": json.dumps(cost_block) if cost_block else None,
            "active_risk_json": (json.dumps(active_risk_block)
                                 if active_risk_block else None),
            "concentration_json": json.dumps(concentration_block),
            "warnings_json": json.dumps(warnings),
            "completed_at": _now(),
            "duration_ms": int((time.monotonic() - t0) * 1000),
            "error_message": None,
        })

    run = store.get_run(run_id)
    assert run is not None
    if create_experiment and not run.get("experiment_id"):
        record = experiment_integration.record_experiment(
            name=f"Portfolio attribution: {run['name']}",
            module="portfolio_performance_attribution",
            experiment_type="portfolio_attribution",
            status="completed",
            parameters={
                "portfolio_run_id": run["portfolio_run_id"],
                "benchmark_id": (benchmark or {}).get("benchmark_id"),
                "attribution_method": run["attribution_method"],
                "linking_method": run["linking_method"],
                "period_count": run["period_count"],
                "integrity_status": integrity,
                "completeness_status": completeness,
                "reconciliation_status": reconciliation_status,
                "configuration_fingerprint": run["configuration_fingerprint"],
                "result_fingerprint": result_fp,
            },
            metrics={
                "portfolio_market_return": total_market,
                "portfolio_net_return": total_net,
                "benchmark_return": total_benchmark,
                "active_return": total_active,
                "tracking_error": (active_risk_block or {}).get("tracking_error"),
                "contribution_herfindahl": concentration_block.get("herfindahl"),
            },
            tags=["portfolio-attribution"],
            source="portfolio_performance_attribution",
        )
        if record is not None:
            store.update_run(run_id, {"experiment_id": record["id"]})
    return get_run(run_id)


def _apply_linked_group_effects(brinson_rows: List[Dict[str, Any]],
                                brinson_periods: List[Dict[str, Any]],
                                linking: Dict[str, Any]) -> None:
    """Per-group linked effects using the same smoothing factors."""
    factors = linking["smoothing_factors"]
    acc: Dict[str, Dict[str, float]] = {}
    for t, period in enumerate(brinson_periods):
        scale = factors[t]
        for row in period["rows"]:
            e = acc.setdefault(row["group_id"], {
                "linked_allocation_effect": 0.0,
                "linked_selection_effect": 0.0,
                "linked_interaction_effect": 0.0})
            e["linked_allocation_effect"] += scale * (row["allocation_effect"] or 0.0)
            e["linked_selection_effect"] += scale * (row["selection_effect"] or 0.0)
            e["linked_interaction_effect"] += scale * (row["interaction_effect"] or 0.0)
    for row in brinson_rows:
        row.update(acc.get(row["group_id"], {}))


def _regime_rows(run: Dict[str, Any], prun: Dict[str, Any],
                 periods: List[Dict[str, Any]],
                 period_results: List[Dict[str, Any]],
                 period_rows: List[Dict[str, Any]],
                 warnings: List[str]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Attribution by STORED Phase 54 regime assignment (never recomputed)."""
    if not run.get("regime_run_id"):
        return [], None
    rrun = regime_store.get_run(run["regime_run_id"])
    if rrun is None:
        return [], None
    definition = next((d for d in regime_store.list_definitions(rrun["id"])
                       if d["definition_id"] == run["regime_definition_id"]),
                      None)
    if definition is None:
        return [], None
    label_by_ts = dict(zip(rrun["timestamps"], definition["assignments"]))
    buckets: Dict[str, List[int]] = {}
    for i, period in enumerate(periods):
        label = label_by_ts.get(period["period_start"])
        key = label if label is not None else "unassigned"
        buckets.setdefault(key, []).append(i)
        period_rows[i]["regime_label"] = key
    rows: List[Dict[str, Any]] = []
    for label in sorted(buckets):
        idx = buckets[label]
        market = [period_results[i]["market_return"] for i in idx]
        bench = [period_results[i]["benchmark_return"] for i in idx
                 if period_results[i]["benchmark_return"] is not None]
        costs = [period_results[i]["cost_return"] for i in idx
                 if period_results[i]["cost_return"] is not None]
        alloc = [period_results[i]["brinson"]["allocation_effect"]
                 for i in idx if period_results[i]["brinson"]]
        sel = [period_results[i]["brinson"]["selection_effect"]
               for i in idx if period_results[i]["brinson"]]
        inter = [period_results[i]["brinson"]["interaction_effect"]
                 for i in idx if period_results[i]["brinson"]]
        full_bench = len(bench) == len(idx)
        active = ([m - b for m, b in zip(market, bench)]
                  if full_bench else [])
        te = None
        if len(active) >= 2:
            mean = sum(active) / len(active)
            te = math.sqrt(sum((a - mean) ** 2 for a in active)
                           / (len(active) - 1))
        conc = risk_mod.concentration(market, label=f"regime:{label}")
        rows.append({
            "regime_label": label,
            "observation_count": len(idx),
            "portfolio_market_return": sum(market),
            "benchmark_return": sum(bench) if full_bench else None,
            "active_return": sum(active) if full_bench else None,
            "cost_return": (sum(costs) if len(costs) == len(idx) else None),
            "net_return": (sum(market) - sum(costs)) if len(costs) == len(idx)
                          else None,
            "allocation_effect": sum(alloc) if alloc else None,
            "selection_effect": sum(sel) if sel else None,
            "interaction_effect": sum(inter) if inter else None,
            "tracking_error": te,
            "contribution_herfindahl": conc.get("herfindahl"),
            "completeness": ("complete" if full_bench and len(costs) == len(idx)
                             else "partial"),
            "rare_regime_warning": len(idx) < RARE_REGIME_MIN_OBSERVATIONS,
        })
    rare = [r["regime_label"] for r in rows if r["rare_regime_warning"]]
    if rare:
        warnings.append(
            "rare regime(s) with fewer than "
            f"{RARE_REGIME_MIN_OBSERVATIONS} observations: "
            + ", ".join(rare) + " — their statistics are not reliable")
    return rows, ("stored effective regime assignments joined by exact "
                  "timestamp; regimes are never recomputed and no regime is "
                  "preferred or recommended")


def _drawdown_rows(run: Dict[str, Any], periods: List[Dict[str, Any]],
                   period_results: List[Dict[str, Any]],
                   tolerance: float) -> List[Dict[str, Any]]:
    """Attribution over STORED Phase 57 drawdown episodes (read-only)."""
    if not run.get("stress_run_id"):
        return []
    episodes = stress_store.list_episodes(run["stress_run_id"])
    if not episodes:
        return []
    start_index = {p["period_start"]: i for i, p in enumerate(periods)}
    rows: List[Dict[str, Any]] = []
    for episode in episodes:
        peak = episode["peak_timestamp"]
        trough = episode["trough_timestamp"]
        if peak not in start_index or trough not in start_index:
            continue
        lo, hi = start_index[peak], start_index[trough]
        if hi < lo:
            continue
        window = period_results[lo:hi + 1]
        market = [w["market_return"] for w in window]
        bench = [w["benchmark_return"] for w in window
                 if w["benchmark_return"] is not None]
        costs = [w["cost_return"] for w in window
                 if w["cost_return"] is not None]
        full_bench = len(bench) == len(window)
        alloc = [w["brinson"]["allocation_effect"] for w in window
                 if w["brinson"]]
        sel = [w["brinson"]["selection_effect"] for w in window if w["brinson"]]
        inter = [w["brinson"]["interaction_effect"] for w in window
                 if w["brinson"]]
        active = (sum(market) - sum(bench)) if full_bench else None
        explained = ((sum(alloc) + sum(sel) + sum(inter))
                     if alloc and full_bench else None)
        residual = (active - explained
                    if active is not None and explained is not None else None)
        contributions: Dict[str, float] = {}
        for w in window:
            for row in w["contributions"]["rows"]:
                contributions[row["asset_id"]] = (
                    contributions.get(row["asset_id"], 0.0) + row["contribution"])
        rows.append({
            "episode_id": episode["episode_id"],
            "peak_timestamp": peak, "trough_timestamp": trough,
            "recovery_timestamp": episode.get("recovery_timestamp"),
            "period_count": len(window),
            "portfolio_market_return": sum(market),
            "benchmark_return": sum(bench) if full_bench else None,
            "active_return": active,
            "cost_return": (sum(costs) if len(costs) == len(window) else None),
            "allocation_effect": sum(alloc) if alloc else None,
            "selection_effect": sum(sel) if sel else None,
            "interaction_effect": sum(inter) if inter else None,
            "residual": residual,
            "reconciliation_state": (
                "reconciled" if residual is not None
                and abs(residual) <= tolerance else
                ("residual" if residual is not None else "unavailable")),
            "contributions": [{"asset_id": a, "contribution": c}
                              for a, c in sorted(contributions.items())],
        })
    return rows


def invalidate_run(run_id: int, reason: str) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"portfolio-attribution run {run_id} not found")
    if run["status"] == "invalidated":
        raise ConflictError("run is already invalidated")
    store.update_run(run_id, {"status": "invalidated", "error_message": reason,
                              "is_baseline": 0})
    return get_run(run_id)


# ---------------------------------------------------------------------------
# Baseline / compare / export
# ---------------------------------------------------------------------------


def _baseline_scope(run: Dict[str, Any]) -> str:
    return "|".join([
        f"prun:{run['portfolio_run_id']}",
        f"obs:{run['observation_fingerprint'][:16]}",
        f"bench:{((run.get('configuration') or {}).get('benchmark') or {}).get('fingerprint', 'none')[:16]}",
        f"pol:{run['policy_fingerprint'][:16]}",
        f"win:{run['observation_start']}..{run['observation_end']}",
        f"freq:{run['return_frequency']}",
    ])


def mark_baseline(run_id: int) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"portfolio-attribution run {run_id} not found")
    if run["status"] != "completed":
        raise ConflictError("baselines require a completed run")
    if run["integrity_status"] not in BASELINE_ACCEPTABLE_INTEGRITY:
        raise ConflictError(
            "baselines require verified weight provenance — this run is "
            f"{run['integrity_status']}")
    if run["completeness_status"] not in BASELINE_ACCEPTABLE_COMPLETENESS:
        raise ConflictError(
            "baselines require a complete result — this run is "
            f"{run['completeness_status']}")
    if run["reconciliation_status"] not in BASELINE_ACCEPTABLE_RECONCILIATION:
        raise ConflictError(
            "baselines require reconciliation within the configured "
            f"tolerance — this run is {run['reconciliation_status']}")
    if not run["result_fingerprint"]:
        raise ConflictError("baselines require a result fingerprint")
    try:
        _revalidate_inputs(run)
    except AttributionError as exc:
        raise ConflictError(str(exc)) from exc
    scope = _baseline_scope(run)
    store.mark_baseline(run_id, scope)
    return get_run(run_id)


def _entry(field: str, a: Any, b: Any) -> Dict[str, Any]:
    if a is None and b is None:
        return {"kind": "unavailable", "field": field, "a": a, "b": b,
                "note": ""}
    if a is None:
        return {"kind": "only_in_b", "field": field, "a": a, "b": b, "note": ""}
    if b is None:
        return {"kind": "only_in_a", "field": field, "a": a, "b": b, "note": ""}
    kind = "same" if a == b else "changed"
    note = ""
    if (kind == "changed" and isinstance(a, (int, float))
            and isinstance(b, (int, float)) and not isinstance(a, bool)
            and not isinstance(b, bool) and math.isfinite(float(a))
            and math.isfinite(float(b))):
        note = f"Δ {round(b - a, 8)}"
    return {"kind": kind, "field": field, "a": a, "b": b, "note": note}


def compare_runs(a_id: int, b_id: int) -> Dict[str, Any]:
    if a_id == b_id:
        raise AttributionError("compare requires two different runs")
    a, b = get_run(a_id), get_run(b_id)
    comparability: List[str] = []
    if a["portfolio_run_id"] != b["portfolio_run_id"]:
        comparability.append("different portfolio runs — not directly comparable")
    if a.get("benchmark_name") != b.get("benchmark_name"):
        comparability.append("different benchmarks")
    if (a["observation_start"], a["observation_end"]) != \
            (b["observation_start"], b["observation_end"]):
        comparability.append("different observation windows")
    if a["return_frequency"] != b["return_frequency"]:
        comparability.append("different return frequencies")
    if a["observation_fingerprint"] != b["observation_fingerprint"]:
        comparability.append("different observation universes "
                             "(assets, groups, weights or returns differ)")
    if a["weight_timing_policy"] != b["weight_timing_policy"]:
        comparability.append("different weight-timing policies")
    if a["linking_method"] != b["linking_method"]:
        comparability.append("different multi-period linking methods")
    if a["attribution_method"] != b["attribution_method"]:
        comparability.append("different attribution methods")
    if a.get("cost_model_fingerprint") != b.get("cost_model_fingerprint"):
        comparability.append("different linked cost models")

    identity = [_entry(f, a.get(f), b.get(f)) for f in (
        "attribution_method", "brinson_variant", "linking_method",
        "return_frequency", "weight_timing_policy", "period_count",
        "asset_count", "group_count", "portfolio_market_return",
        "portfolio_net_return", "benchmark_return", "active_return",
        "total_cost_return", "tracking_error", "information_ratio",
        "integrity_status", "completeness_status", "reconciliation_status",
        "status", "portfolio_run_name", "benchmark_name")]

    a_groups = {r["group_id"]: r for r in store.list_brinson(a_id)}
    b_groups = {r["group_id"]: r for r in store.list_brinson(b_id)}
    brinson_rows = [{
        "group_id": g,
        "availability": ("both" if g in a_groups and g in b_groups
                         else ("only_in_a" if g in a_groups else "only_in_b")),
        "a_allocation": a_groups.get(g, {}).get("allocation_effect"),
        "b_allocation": b_groups.get(g, {}).get("allocation_effect"),
        "a_selection": a_groups.get(g, {}).get("selection_effect"),
        "b_selection": b_groups.get(g, {}).get("selection_effect"),
        "a_interaction": a_groups.get(g, {}).get("interaction_effect"),
        "b_interaction": b_groups.get(g, {}).get("interaction_effect"),
    } for g in sorted(set(a_groups) | set(b_groups))]

    a_assets = {r["asset_id"]: r for r in store.list_assets(a_id)}
    b_assets = {r["asset_id"]: r for r in store.list_assets(b_id)}
    contribution_rows = [{
        "asset_id": aid,
        "availability": ("both" if aid in a_assets and aid in b_assets
                         else ("only_in_a" if aid in a_assets else "only_in_b")),
        "a_contribution": a_assets.get(aid, {}).get("arithmetic_contribution"),
        "b_contribution": b_assets.get(aid, {}).get("arithmetic_contribution"),
    } for aid in sorted(set(a_assets) | set(b_assets))]

    return {
        "a_id": a_id, "b_id": b_id,
        "comparability_warnings": comparability,
        "groups": {"identity": identity},
        "brinson": brinson_rows,
        "contributions": contribution_rows,
        "fingerprint_match": {
            "observation_universe":
                a["observation_fingerprint"] == b["observation_fingerprint"],
            "attribution_policy":
                a["policy_fingerprint"] == b["policy_fingerprint"],
            "configuration":
                a["configuration_fingerprint"] == b["configuration_fingerprint"],
            "result": bool(a.get("result_fingerprint"))
            and a.get("result_fingerprint") == b.get("result_fingerprint"),
        },
        "baseline": {"a": a["is_baseline"], "b": b["is_baseline"]},
        "note": ("differences are reported neutrally; no run is declared "
                 "better, superior or recommended"),
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
        "benchmarks": {}, "periods": {}, "assets": {}, "groups": {},
        "brinson": {}, "regimes": {}, "drawdowns": {},
    }
    for r in runs:
        rid = r["id"]
        payload["benchmarks"][rid] = store.get_benchmark(rid)
        payload["periods"][rid] = store.list_periods(rid)
        payload["assets"][rid] = store.list_assets(rid)
        payload["groups"][rid] = store.list_groups(rid)
        payload["brinson"][rid] = store.list_brinson(rid)
        payload["regimes"][rid] = store.list_regimes(rid)
        payload["drawdowns"][rid] = store.list_drawdowns(rid)
    return payload


__all__ = [
    "ATTRIBUTION_METHODS", "COST_POLICIES", "EXECUTION_ORDER",
    "BASELINE_ACCEPTABLE_INTEGRITY", "BASELINE_ACCEPTABLE_COMPLETENESS",
    "BASELINE_ACCEPTABLE_RECONCILIATION", "AttributionError", "NotFoundError",
    "ConflictError", "InternalExecutionError", "create_run", "get_run",
    "list_runs", "lab_summary", "execute_run", "invalidate_run",
    "mark_baseline", "compare_runs", "export",
]
