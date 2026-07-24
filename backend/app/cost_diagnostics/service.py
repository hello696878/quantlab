"""
Service layer for the Cost Diagnostics Lab (v1).

Validation is eager at create time; execution is deterministic from the
stored normalized observations and cost-model configuration.  Linked
registry records (datasets, validation runs, overfitting runs, regime runs,
experiments) are read-only — nothing in this module mutates a prior
registry's rows, fingerprints or memberships.

Run integrity is the least-trusted state across configured cost components:
fixed configured assumptions are ``declared``; components consuming supplied
per-observation execution inputs inherit those inputs' provenance;
trailing-derived inputs are ``verified_causal_input``; a centered window or
non-positive lag makes the run ``invalid``.  Run completeness summarises
per-observation reconciliation states and missing inputs are never treated
as zero.
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.dataset_registry import store as dataset_store
from app.experiment_registry import integration as experiment_integration
from app.experiment_registry import store as experiment_store
from app.experiment_registry.fingerprints import sha256_hex
from app.experiment_registry.provenance import get_app_version, get_git_commit
from app.feature_diagnostics import store as feature_store
from app.meta_labeling import store as meta_store
from app.model_validation import store as validation_store
from app.overfitting_diagnostics import store as overfitting_store
from app.regime_diagnostics import store as regime_store
from app.cost_diagnostics import EXPORT_SCHEMA_VERSION
from app.cost_diagnostics import aggregates as agg_mod
from app.cost_diagnostics import components as comp_mod
from app.cost_diagnostics import fingerprints as fp_mod
from app.cost_diagnostics import impact as impact_mod
from app.cost_diagnostics import liquidity as liq_mod
from app.cost_diagnostics import scenarios as scen_mod
from app.cost_diagnostics.core import (
    OBSERVATION_TYPES,
    CostInputError,
    normalize_period_observations,
    normalize_trades,
)
from app.cost_diagnostics.reconcile import (
    reconcile_observation,
    run_completeness,
)
from app.cost_diagnostics.units import BASIS_POINT


class CostDiagnosticsError(ValueError):
    """Invalid input/config (HTTP 422)."""


class NotFoundError(LookupError):
    """Unknown id (HTTP 404)."""


class ConflictError(RuntimeError):
    """State conflict (HTTP 409)."""


BASELINE_ACCEPTABLE_INTEGRITY = (
    "supplied_realized", "verified_causal_input",
    "verified_from_dataset_lineage", "declared",
)
BASELINE_ACCEPTABLE_COMPLETENESS = ("complete",)
RARE_REGIME_MIN_OBSERVATIONS = 8

ADV_SOURCE_MODES = ("per_observation", "trailing_volume")
VOLATILITY_SOURCE_MODES = ("per_observation", "trailing_returns")

MISSING_INPUT_POLICY = (
    "a missing cost input leaves that component unavailable and the "
    "observation partial; missing costs are never treated as zero"
)
MULTIPLE_COMPARISONS_NOTE = (
    "v1 reports descriptive cost estimates only; no hypothesis tests are "
    "performed and no p-values are produced"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


from app.cost_diagnostics import store  # noqa: E402  (after error classes)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def _validate_liquidity_config(raw: Any, observations: List[Dict[str, Any]]
                               ) -> Dict[str, Any]:
    cfg = dict(raw or {})
    out: Dict[str, Any] = {}
    adv = dict(cfg.get("adv_source") or {"mode": "per_observation"})
    vol = dict(cfg.get("volatility_source") or {"mode": "per_observation"})
    if adv.get("mode") not in ADV_SOURCE_MODES:
        raise CostInputError(
            f"adv_source.mode must be one of {', '.join(ADV_SOURCE_MODES)}")
    if vol.get("mode") not in VOLATILITY_SOURCE_MODES:
        raise CostInputError(
            "volatility_source.mode must be one of "
            f"{', '.join(VOLATILITY_SOURCE_MODES)}")
    for name, src in (("adv_source", adv), ("volatility_source", vol)):
        if src.get("window") == "centered":
            raise CostInputError(
                f"{name}: centered windows on execution inputs are prohibited")
        if src["mode"].startswith("trailing"):
            for field, lo, hi in (("lookback", liq_mod.MIN_LOOKBACK,
                                   liq_mod.MAX_LOOKBACK),
                                  ("lag", liq_mod.MIN_LAG, liq_mod.MAX_LAG)):
                v = src.get(field)
                if isinstance(v, bool) or not isinstance(v, int) or not (lo <= v <= hi):
                    raise CostInputError(
                        f"{name}.{field} must be an integer in [{lo}, {hi}]")
            if name == "volatility_source" and src["lookback"] < 2:
                raise CostInputError(
                    "volatility_source.lookback must be >= 2 for a sample std")
    if adv["mode"] == "trailing_volume":
        if adv.get("unit") not in ("units", "currency"):
            raise CostInputError(
                "adv_source trailing_volume requires an explicit unit "
                "('units' or 'currency') for the liquidity series volume")
    series = None
    if adv["mode"] == "trailing_volume" or vol["mode"] == "trailing_returns":
        if cfg.get("series") is None:
            raise CostInputError(
                "trailing liquidity derivation requires liquidity series data")
        try:
            series = liq_mod.validate_series(cfg["series"])
        except liq_mod.LiquidityInputError as exc:
            raise CostInputError(str(exc))
        if adv["mode"] == "trailing_volume" and "volume" not in series:
            raise CostInputError(
                "adv_source trailing_volume requires liquidity series volume")
        if vol["mode"] == "trailing_returns" and "returns" not in series:
            raise CostInputError(
                "volatility_source trailing_returns requires liquidity "
                "series returns")
    # only validated fields reach the stored, fingerprinted policy: inert
    # lookback/lag/unit keys on per_observation modes are dropped so junk
    # keys can neither contradict the policy text nor perturb fingerprints
    if adv["mode"] == "trailing_volume":
        out["adv_source"] = {k: adv[k]
                            for k in ("mode", "lookback", "lag", "unit")
                            if k in adv}
    else:
        out["adv_source"] = {"mode": adv["mode"]}
    if vol["mode"] == "trailing_returns":
        out["volatility_source"] = {k: vol[k]
                                    for k in ("mode", "lookback", "lag")
                                    if k in vol}
    else:
        out["volatility_source"] = {"mode": vol["mode"]}
    out["series"] = series
    out["alignment"] = ("derived inputs are resolved at each observation's "
                        "timestamp by exact match; no interpolation")
    return out


def _validate_links(payload: Dict[str, Any]) -> Dict[str, Any]:
    links: Dict[str, Any] = {}
    if payload.get("dataset_version_id") is not None:
        version = dataset_store.get_version(payload["dataset_version_id"])
        if version is None:
            raise CostDiagnosticsError(
                f"dataset version {payload['dataset_version_id']} not found")
        links["dataset_version_id"] = version["id"]
        links["dataset_manifest_fingerprint"] = version["manifest_fingerprint"]
    if payload.get("validation_run_id") is not None:
        vrun = validation_store.get_run(payload["validation_run_id"])
        if vrun is None:
            raise CostDiagnosticsError(
                f"validation run {payload['validation_run_id']} not found")
        links["validation_run_id"] = vrun["id"]
    if payload.get("overfitting_run_id") is not None:
        orun = overfitting_store.get_run(payload["overfitting_run_id"])
        if orun is None:
            raise CostDiagnosticsError(
                f"overfitting run {payload['overfitting_run_id']} not found")
        links["overfitting_run_id"] = orun["id"]
    if payload.get("regime_run_id") is not None:
        rrun = regime_store.get_run(payload["regime_run_id"])
        if rrun is None:
            raise CostDiagnosticsError(
                f"regime run {payload['regime_run_id']} not found")
        if rrun["status"] != "completed":
            raise CostDiagnosticsError(
                "regime integration requires a completed regime run")
        definition_id = payload.get("regime_definition_id")
        if not definition_id:
            raise CostDiagnosticsError(
                "regime integration requires regime_definition_id")
        defs = {d["definition_id"] for d in
                regime_store.list_definitions(rrun["id"])}
        if definition_id not in defs:
            raise CostDiagnosticsError(
                f"regime definition {definition_id!r} not found in run "
                f"{rrun['id']}")
        links["regime_run_id"] = rrun["id"]
        links["regime_definition_id"] = definition_id
    elif payload.get("regime_definition_id"):
        raise CostDiagnosticsError(
            "regime_definition_id requires regime_run_id")
    if payload.get("feature_diagnostics_run_id") is not None:
        frun = feature_store.get_run(payload["feature_diagnostics_run_id"])
        if frun is None:
            raise CostDiagnosticsError(
                f"feature run {payload['feature_diagnostics_run_id']} not found")
        links["feature_diagnostics_run_id"] = frun["id"]
    if payload.get("meta_label_run_id") is not None:
        mrun = meta_store.get_run(payload["meta_label_run_id"])
        if mrun is None:
            raise CostDiagnosticsError(
                f"meta-label run {payload['meta_label_run_id']} not found")
        links["meta_label_run_id"] = mrun["id"]
    if payload.get("experiment_id") is not None:
        exp = experiment_store.get_experiment(payload["experiment_id"])
        if exp is None:
            raise CostDiagnosticsError(
                f"experiment {payload['experiment_id']} not found")
        links["experiment_id"] = exp["id"]
    return links


def create_run(payload: Dict[str, Any], *, demo_key: Optional[str] = None) -> Dict[str, Any]:
    name = (payload.get("name") or "").strip()
    if not name or len(name) > 200:
        raise CostDiagnosticsError("name must be 1..200 characters")
    observation_type = payload.get("observation_type")
    if observation_type not in OBSERVATION_TYPES:
        raise CostDiagnosticsError(
            f"observation_type must be one of {', '.join(OBSERVATION_TYPES)}")
    tick_size = payload.get("tick_size")
    if tick_size is not None:
        if isinstance(tick_size, bool) or not isinstance(tick_size, (int, float)) \
                or not math.isfinite(float(tick_size)) or float(tick_size) <= 0:
            raise CostDiagnosticsError("tick_size must be a finite number > 0")
        tick_size = float(tick_size)
    try:
        if observation_type == "trade":
            observations, currency = normalize_trades(payload.get("observations"))
        else:
            observations = normalize_period_observations(payload.get("observations"))
            currency = None
        commission = comp_mod.validate_commission_config(
            payload.get("commission"), observation_type)
        spread = comp_mod.validate_spread_config(
            payload.get("spread"), observation_type)
        slippage = comp_mod.validate_slippage_config(
            payload.get("slippage"), observation_type)
        impact = impact_mod.validate_impact_config(
            payload.get("impact"), observation_type)
        threshold = impact_mod.validate_participation_threshold(
            payload.get("participation_threshold"))
        grid = scen_mod.validate_sensitivity_grid(payload.get("sensitivity_grid"))
        scales = scen_mod.validate_capacity_scales(payload.get("capacity_scales"))
        liquidity = _validate_liquidity_config(payload.get("liquidity"),
                                               observations)
    except CostInputError as exc:
        raise CostDiagnosticsError(str(exc))
    integer_contracts = bool(payload.get("integer_contracts", False))
    if integer_contracts and observation_type != "trade":
        raise CostDiagnosticsError(
            "integer_contracts applies to trade observations only")
    if integer_contracts:
        fractional = [t["trade_id"] for t in observations
                      if t["quantity"] != math.floor(t["quantity"])]
        if fractional:
            raise CostDiagnosticsError(
                "integer_contracts requires whole-number trade quantities; "
                f"fractional quantities on: {', '.join(fractional[:5])}")
    if spread["model"] == "fixed_ticks" and tick_size is None:
        raise CostDiagnosticsError("fixed_ticks spread requires tick_size")
    if slippage["model"] == "fixed_ticks_per_side" and tick_size is None:
        raise CostDiagnosticsError("fixed_ticks_per_side slippage requires tick_size")
    if (impact["model"] == "square_root"
            and liquidity["adv_source"]["mode"] == "trailing_volume"):
        required = "units" if impact["participation_mode"] == "quantity" else "currency"
        if liquidity["adv_source"].get("unit") != required:
            raise CostDiagnosticsError(
                f"impact participation_mode {impact['participation_mode']!r} "
                f"requires the trailing ADV series in {required!r}; the "
                f"declared unit is {liquidity['adv_source'].get('unit')!r} "
                "(no silent unit conversion)")

    links = _validate_links(payload)

    liquidity_policy = {
        "adv_source": liquidity["adv_source"],
        "volatility_source": liquidity["volatility_source"],
        "alignment": liquidity["alignment"],
        "volatility_convention": "per-period return fraction, sample std (ddof=1)",
        "missing_input_policy": MISSING_INPUT_POLICY,
        "no_lookahead_policy": (
            "trailing inputs at an observation use series values through "
            "index i - lag only, with lag >= 1; centered windows and "
            "negative lags are rejected"),
    }
    cost_model_fp = fp_mod.cost_model_fingerprint(
        commission, spread, slippage, impact, liquidity_policy, tick_size)
    universe_fp = fp_mod.observation_universe_fingerprint(
        observations, observation_type, currency,
        {"dataset_version_id": links.get("dataset_version_id"),
         "manifest_fingerprint": links.get("dataset_manifest_fingerprint")},
        liquidity["series"])
    linked_identity = {k: links.get(k) for k in (
        "dataset_version_id", "validation_run_id", "overfitting_run_id",
        "regime_run_id", "regime_definition_id")}
    config_fp = fp_mod.configuration_fingerprint(
        universe_fp, cost_model_fp, grid, scales, integer_contracts,
        threshold, tick_size, linked_identity)

    configuration = {
        "observation_type": observation_type,
        "currency": currency,
        "tick_size": tick_size,
        "commission": commission,
        "spread": spread,
        "slippage": slippage,
        "impact": impact,
        "participation_threshold": threshold,
        "sensitivity_grid": grid,
        "capacity_scales": scales,
        "integer_contracts": integer_contracts,
        "liquidity_policy": liquidity_policy,
        "liquidity_series": liquidity["series"],
        "delay_stress": {
            "supported": False,
            "note": ("delay/adverse-price stress is omitted in v1: stored "
                     "observations carry no per-bar price paths, so a delayed "
                     "fill cannot be derived without fabricating prices"),
        },
        "multiple_comparisons_note": MULTIPLE_COMPARISONS_NOTE,
        "capacity_note": ("capacity results are estimated under configured "
                          "assumptions; no assumption is made that fills "
                          "remain available at scale"),
    }
    run = store.insert_run({
        "name": name, "description": payload.get("description", ""),
        "observation_type": observation_type,
        "candidate_count": len({o["candidate_id"] for o in observations}),
        "observation_count": len(observations),
        "currency": currency,
        "universe_fingerprint": universe_fp,
        "cost_model_fingerprint": cost_model_fp,
        "configuration": configuration,
        "configuration_fingerprint": config_fp,
        "observations": observations,
        "dataset_version_id": links.get("dataset_version_id"),
        "validation_run_id": links.get("validation_run_id"),
        "overfitting_run_id": links.get("overfitting_run_id"),
        "regime_run_id": links.get("regime_run_id"),
        "regime_definition_id": links.get("regime_definition_id"),
        "feature_diagnostics_run_id": links.get("feature_diagnostics_run_id"),
        "meta_label_run_id": links.get("meta_label_run_id"),
        "experiment_id": links.get("experiment_id"),
        "app_version": get_app_version(), "git_commit": get_git_commit(),
        "notes": payload.get("notes", ""), "demo_key": demo_key,
    })
    store.replace_cost_model(run["id"], {
        "commission": commission, "spread": spread, "slippage": slippage,
        "impact": impact, "liquidity_policy": liquidity_policy,
        "fingerprint": cost_model_fp,
    })
    return get_run(run["id"])


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def get_run(run_id: int) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"cost-diagnostic run {run_id} not found")
    return _hydrate(run)


def _hydrate(run: Dict[str, Any]) -> Dict[str, Any]:
    run["dataset_name"] = run["dataset_version_label"] = None
    run["dataset_invalidated"] = None
    run["dataset_manifest_fingerprint"] = None
    run["dataset_provenance_status"] = run["dataset_quality_status"] = None
    run["validation_method"] = run["validation_leakage_clean"] = None
    run["validation_config_fp"] = None
    run["overfitting_name"] = run["overfitting_pbo"] = None
    run["overfitting_psr"] = run["overfitting_dsr"] = None
    run["overfitting_universe_fp"] = None
    run["regime_run_name"] = run["regime_run_integrity"] = None
    run["feature_run_name"] = run["feature_run_integrity"] = None
    run["meta_label_run_name"] = None
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
    if run.get("overfitting_run_id"):
        orun = overfitting_store.get_run(run["overfitting_run_id"])
        if orun:
            run["overfitting_name"] = orun["name"]
            run["overfitting_pbo"] = orun.get("pbo_estimate")
            run["overfitting_psr"] = orun.get("psr")
            run["overfitting_dsr"] = orun.get("dsr")
            run["overfitting_universe_fp"] = orun["universe_fingerprint"]
    if run.get("regime_run_id"):
        rrun = regime_store.get_run(run["regime_run_id"])
        if rrun:
            run["regime_run_name"] = rrun["name"]
            run["regime_run_integrity"] = rrun["integrity_status"]
    if run.get("feature_diagnostics_run_id"):
        frun = feature_store.get_run(run["feature_diagnostics_run_id"])
        if frun:
            run["feature_run_name"] = frun["name"]
            run["feature_run_integrity"] = frun["integrity_status"]
    if run.get("meta_label_run_id"):
        mrun = meta_store.get_run(run["meta_label_run_id"])
        if mrun:
            run["meta_label_run_name"] = mrun["name"]
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


def _resolve_derived_inputs(config: Dict[str, Any],
                            observations: List[Dict[str, Any]]
                            ) -> Tuple[Dict[str, Optional[float]],
                                       Dict[str, Optional[float]],
                                       List[str]]:
    """Derive trailing ADV / volatility per observation id (exact-match)."""
    policy = config["liquidity_policy"]
    series = config.get("liquidity_series")
    adv_by_obs: Dict[str, Optional[float]] = {}
    vol_by_obs: Dict[str, Optional[float]] = {}
    integrities: List[str] = []
    obs_ts = [o["timestamp"] for o in observations]
    if policy["adv_source"]["mode"] == "trailing_volume" and series:
        derived = liq_mod.derive_trailing(
            series["volume"], policy["adv_source"]["lookback"],
            policy["adv_source"]["lag"], "mean")
        mapped = liq_mod.map_series_to_observations(
            series["timestamps"], derived, obs_ts)
        adv_by_obs = {o["observation_id"]: v
                      for o, v in zip(observations, mapped)}
        # the causal-derivation claim holds only if something actually derived
        if any(v is not None for v in mapped):
            integrities.append("verified_causal_input")
    if policy["volatility_source"]["mode"] == "trailing_returns" and series:
        derived = liq_mod.derive_trailing(
            series["returns"], policy["volatility_source"]["lookback"],
            policy["volatility_source"]["lag"], "std")
        mapped = liq_mod.map_series_to_observations(
            series["timestamps"], derived, obs_ts)
        vol_by_obs = {o["observation_id"]: v
                      for o, v in zip(observations, mapped)}
        if any(v is not None for v in mapped):
            integrities.append("verified_causal_input")
    return adv_by_obs, vol_by_obs, integrities


def _compute_observation(obs: Dict[str, Any], config: Dict[str, Any],
                         observation_type: str,
                         resolved_adv: Optional[float],
                         resolved_vol: Optional[float]) -> Dict[str, Any]:
    """All cost components + reconciliation for one (possibly scaled) obs."""
    tick_size = config.get("tick_size")
    commission = comp_mod.compute_commission(obs, config["commission"],
                                             observation_type)
    spread = comp_mod.compute_spread_cost(obs, config["spread"],
                                          observation_type, tick_size)
    slippage = comp_mod.compute_slippage(obs, config["slippage"],
                                         observation_type, tick_size)
    if (slippage.get("source") == "supplied_realized"
            and slippage.get("amount") is not None
            and obs.get("size_ratio") not in (None, 1.0)):
        # historical realized slippage is per-unit; hold the per-unit value
        # constant when size is scaled
        slippage = dict(slippage)
        slippage["amount"] = slippage["amount"] * obs["size_ratio"]
    # a configured trailing derivation never silently falls back to
    # per-observation supplied inputs (their provenance would bypass
    # integrity classification) — unresolved trailing inputs stay unavailable
    allow_adv = (config["liquidity_policy"]["adv_source"]["mode"]
                 != "trailing_volume")
    allow_vol = (config["liquidity_policy"]["volatility_source"]["mode"]
                 != "trailing_returns")
    imp = impact_mod.compute_impact(obs, config["impact"], observation_type,
                                    resolved_adv, resolved_vol,
                                    allow_supplied_adv=allow_adv,
                                    allow_supplied_vol=allow_vol)
    gross_value = (obs["gross_pnl"] if observation_type == "trade"
                   else obs["gross_return"])
    if "gross_value" in obs:
        gross_value = obs["gross_value"]
    rec = reconcile_observation(gross_value, {
        "commission": commission, "spread": spread,
        "slippage": slippage, "impact": imp,
    })
    mode = config["impact"].get("participation_mode")
    part = impact_mod.participation_record(
        obs, observation_type, resolved_adv, mode,
        config["participation_threshold"], allow_supplied_adv=allow_adv)
    # per-observation break-even in bps of traded notional: currency/currency
    # for trades; return-fraction/turnover for periods (identical dimension)
    breakeven_bps = None
    if observation_type == "trade":
        notional = obs.get("traded_notional")
        if gross_value > 0 and notional and notional > 0:
            breakeven_bps = gross_value / notional / BASIS_POINT
    else:
        turnover = obs.get("turnover")
        if gross_value > 0 and turnover and turnover > 0:
            breakeven_bps = gross_value / turnover / BASIS_POINT
    warnings = list(obs.get("input_warnings", []))
    if part.get("warning"):
        warnings.append(part["warning"])
    net_return = None
    if rec["net_value"] is not None:
        if observation_type == "trade":
            net_return = rec["net_value"] / obs["entry_notional"]
        else:
            net_return = rec["net_value"]
    return {
        "observation_id": obs["observation_id"],
        "candidate_id": obs["candidate_id"],
        "timestamp": obs["timestamp"],
        "side": obs.get("side"),
        "quantity": obs.get("quantity"),
        "traded_notional": obs.get("traded_notional"),
        "turnover": obs.get("turnover"),
        "gross_value": gross_value,
        "gross_return": obs.get("gross_return"),
        "component_values": rec["component_values"],
        "component_reasons": rec["component_reasons"],
        "total_cost": rec["total_cost"],
        "net_value": rec["net_value"],
        "net_return": net_return,
        "completeness": rec["completeness"],
        "unavailable_components": rec["unavailable_components"],
        "participation": part["participation"],
        "participation_status": part["status"],
        "breakeven_bps": breakeven_bps,
        "warnings": warnings,
        "impact_participation": imp.get("participation"),
        "slippage_source": slippage.get("source"),
    }


def _component_integrity(config: Dict[str, Any],
                         observations: List[Dict[str, Any]],
                         derived_integrities: List[str],
                         dataset_linked: bool
                         ) -> Tuple[str, List[str]]:
    """Least-trusted integrity across configured components (module doc)."""
    states: List[str] = []
    warnings: List[str] = []

    def classify_present(input_key: str) -> None:
        seen = set()
        for o in observations:
            spec = o.get("cost_inputs", {}).get(input_key)
            if spec is None:
                continue
            result = liq_mod.classify_supplied_input(
                spec, dataset_linked=dataset_linked, input_key=input_key)
            states.append(result["integrity"])
            for w in result["warnings"]:
                if w not in seen:
                    seen.add(w)
                    warnings.append(f"{input_key}: {w}")

    if config["commission"]["model"] != "none":
        states.append("declared")
    spread_model = config["spread"]["model"]
    if spread_model != "none":
        if spread_model == "supplied":
            classify_present("spread")
        else:
            states.append("declared")
    slippage_model = config["slippage"]["model"]
    if slippage_model != "none":
        if slippage_model == "supplied_realized":
            classify_present("realized_slippage")
        else:
            states.append("declared")
    impact_model = config["impact"]["model"]
    if impact_model == "fixed_bps":
        states.append("declared")
    elif impact_model == "square_root":
        if config["liquidity_policy"]["adv_source"]["mode"] == "trailing_volume":
            pass  # covered by derived_integrities
        else:
            classify_present("adv")
            classify_present("volume")
        if config["liquidity_policy"]["volatility_source"]["mode"] == "trailing_returns":
            pass
        else:
            classify_present("volatility")
    states.extend(derived_integrities)
    return liq_mod.least_trusted(states), warnings


def _regime_join(run: Dict[str, Any],
                 obs_results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Join stored regime assignments by exact timestamp; never recompute."""
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
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in obs_results:
        label = label_by_ts.get(r["timestamp"])
        r["regime_label"] = label if label is not None else "unassigned"
        groups.setdefault(r["regime_label"], []).append(r)
    rows = []
    for label in sorted(groups):
        members = groups[label]
        # costed members = those that produced a net; the gross/cost/net triple
        # reconciles over this subset only (net_total == gross_total_costed -
        # total_cost), exactly as in aggregate_results — the whole-group
        # gross_total may include uncosted gross_only members.
        costed = [m for m in members if m["net_value"] is not None]
        nets = [m["net_value"] for m in costed]
        parts = [m["participation"] for m in members
                 if m["participation"] is not None]
        comp_totals = {}
        for name in ("spread", "slippage", "impact"):
            vals = [m["component_values"].get(name) for m in members]
            present = [v for v in vals if v is not None]
            comp_totals[name] = float(sum(present)) if present else None
        rows.append({
            "regime_label": label,
            "observation_count": len(members),
            "gross_total": float(sum(m["gross_value"] for m in members)),
            "gross_total_costed": (float(sum(m["gross_value"] for m in costed))
                                   if costed else None),
            "total_cost": float(sum(m["total_cost"] for m in costed
                                    if m["total_cost"] is not None)),
            "net_total": float(sum(nets)) if nets else None,
            "spread_total": comp_totals["spread"],
            "slippage_total": comp_totals["slippage"],
            "impact_total": comp_totals["impact"],
            "mean_participation": (float(sum(parts) / len(parts))
                                   if parts else None),
            "incomplete_input_count": sum(
                1 for m in members if m["unavailable_components"]),
            "rare_regime_warning": len(members) < RARE_REGIME_MIN_OBSERVATIONS,
        })
    return {
        "regime_run_id": run["regime_run_id"],
        "regime_run_name": rrun["name"],
        "definition_id": run["regime_definition_id"],
        "definition_integrity": definition["integrity_status"],
        "note": ("stored effective regime assignments joined by exact "
                 "timestamp; regimes are not recomputed and comparisons "
                 "are descriptive only"),
        "rows": rows,
    }


def _candidate_matrix_fingerprints(obs_results: List[Dict[str, Any]],
                                   candidate_count: int
                                   ) -> Dict[str, Optional[str]]:
    if candidate_count < 2:
        return {"gross_candidate_matrix_fingerprint": None,
                "net_candidate_matrix_fingerprint": None,
                "note": "candidate matrix fingerprints require >= 2 candidates"}
    by_candidate: Dict[str, List[Dict[str, Any]]] = {}
    for r in obs_results:
        by_candidate.setdefault(r["candidate_id"], []).append(r)
    gross = {cid: [[r["observation_id"], round(r["gross_value"], 12)]
                   for r in rows]
             for cid, rows in sorted(by_candidate.items())}
    net = {cid: [[r["observation_id"],
                  round(r["net_value"], 12) if r["net_value"] is not None
                  else None]
                 for r in rows]
           for cid, rows in sorted(by_candidate.items())}
    return {
        "gross_candidate_matrix_fingerprint": sha256_hex(
            {"kind": "cost_diagnostics_gross_matrix_v1", "matrix": gross}),
        "net_candidate_matrix_fingerprint": sha256_hex(
            {"kind": "cost_diagnostics_net_matrix_v1", "matrix": net}),
        "note": ("a Phase 53 overfitting analysis of net results requires a "
                 "new explicitly executed run on the net matrix; stored PBO "
                 "values are never reused or rewritten for net returns"),
    }


def execute_run(run_id: int, *, create_experiment: bool = False) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"cost-diagnostic run {run_id} not found")
    if run["status"] == "invalidated":
        raise ConflictError("run is invalidated; create a new run instead")
    t0 = time.monotonic()
    store.update_run(run_id, {"status": "running", "error_message": None})
    try:
        return _execute_body(run_id, run, t0, create_experiment)
    except (NotFoundError, ConflictError):
        raise
    except Exception as exc:
        # A failed (re-)execution is recorded honestly AND must not leave the
        # previous successful execution's derived state behind: a failed run
        # must not keep its baseline flag, result fingerprint, aggregates or
        # any observation/sensitivity/capacity child rows — a stale baseline
        # is a state mark_baseline itself would refuse to create.
        store.update_run(run_id, {
            "status": "failed", "error_message": str(exc), "completed_at": _now(),
            "integrity_status": "unknown", "completeness_status": "invalid",
            "result_fingerprint": None,
            "is_baseline": 0, "baseline_scope": None,
            "gross_total": None, "net_total": None, "total_cost": None,
            # duration_ms is a per-execution derived value; a failed re-execution
            # must not keep the prior successful run's elapsed time
            "duration_ms": None,
            "participation_warning_count": 0, "unavailable_input_count": 0,
            # aggregates/breakeven/regimes are Optional[Dict]; warnings is a list
            "aggregates_json": "{}", "breakeven_json": "{}",
            "regimes_json": "{}", "warnings_json": "[]",
        })
        store.replace_observation_results(run_id, [])
        store.replace_sensitivity_results(run_id, [])
        store.replace_capacity_results(run_id, [])
        raise CostDiagnosticsError(f"execution failed: {exc}")


def _execute_body(run_id: int, run: Dict[str, Any], t0: float,
                  create_experiment: bool) -> Dict[str, Any]:
    config = run["configuration"]
    observation_type = run["observation_type"]
    observations = run["observations"]

    adv_by_obs, vol_by_obs, derived_integrities = _resolve_derived_inputs(
        config, observations)

    obs_results = []
    for obs in observations:
        obs_results.append(_compute_observation(
            obs, config, observation_type,
            adv_by_obs.get(obs["observation_id"]),
            vol_by_obs.get(obs["observation_id"])))

    integrity, integrity_warnings = _component_integrity(
        config, observations, derived_integrities,
        dataset_linked=bool(run.get("dataset_version_id")))
    completeness = run_completeness([r["completeness"] for r in obs_results])

    aggregates = agg_mod.aggregate_results(obs_results, observation_type)
    impact_coefficient = config["impact"].get("coefficient")
    breakeven = agg_mod.breakeven_diagnostics(aggregates, impact_coefficient)
    aggregates.update(_candidate_matrix_fingerprints(
        obs_results, run["candidate_count"]))

    scenarios = scen_mod.build_scenarios(config["sensitivity_grid"])
    sensitivity = [scen_mod.evaluate_scenario(obs_results, s)
                   for s in scenarios]

    capacity = []
    for scale in config["capacity_scales"]:
        scaled_results = []
        excluded = 0
        for obs in observations:
            scaled, reason = scen_mod.scale_observation(
                obs, scale, observation_type, config["integer_contracts"])
            if scaled is None:
                excluded += 1
                continue
            if observation_type == "trade":
                scaled["size_ratio"] = scaled["quantity"] / obs["quantity"]
            scaled_results.append(_compute_observation(
                scaled, config, observation_type,
                adv_by_obs.get(obs["observation_id"]),
                vol_by_obs.get(obs["observation_id"])))
        parts = [r["participation"] for r in scaled_results
                 if r["participation"] is not None]
        comp_totals = {}
        for name in ("commission", "spread", "slippage", "impact"):
            present = [r["component_values"].get(name) for r in scaled_results
                       if r["component_values"].get(name) is not None]
            comp_totals[name] = float(sum(present)) if present else None
        nets = [r["net_value"] for r in scaled_results
                if r["net_value"] is not None]
        notionals = [r["traded_notional"] for r in scaled_results
                     if r.get("traded_notional") is not None]
        scale_costs = [r["total_cost"] for r in scaled_results
                       if r["total_cost"] is not None]
        capacity.append({
            "scale": scale, "is_base": scale == 1.0,
            "traded_notional": float(sum(notionals)) if notionals else None,
            "mean_participation": (float(sum(parts) / len(parts))
                                   if parts else None),
            "max_participation": max(parts) if parts else None,
            "above_threshold_count": sum(
                1 for r in scaled_results
                if r["participation_status"] == "above_configured_threshold"),
            "commission_total": comp_totals["commission"],
            "spread_total": comp_totals["spread"],
            "slippage_total": comp_totals["slippage"],
            "impact_total": comp_totals["impact"],
            "total_cost": float(sum(scale_costs)) if scale_costs else None,
            # NOTE: gross_total sums ALL scaled rows while total_cost/net_total
            # cover the costed subset; the two reconcile only when no scaled row
            # is gross_only/partial.  A per-scale gross_total_costed (as added
            # for aggregate and regime rows) would require a new typed column on
            # cost_capacity_results; deferred (see review report) because there
            # is no additive-column migration path and the value is not rendered.
            "gross_total": float(sum(r["gross_value"] for r in scaled_results)),
            "net_total": float(sum(nets)) if nets else None,
            "unavailable_liquidity_count": sum(
                1 for r in scaled_results
                if "impact" in r["unavailable_components"]),
            "excluded_count": excluded,
        })

    regimes = _regime_join(run, obs_results)

    warnings: List[str] = []
    warnings.extend(integrity_warnings)
    if completeness == "partial":
        warnings.append(
            "some observations miss cost inputs; their nets exclude the "
            "unavailable components and are not zero-filled")
    if completeness == "gross_only":
        warnings.append("no cost component could be computed; results are "
                        "gross only")
    if integrity == "full_sample_descriptive":
        warnings.append("full-sample execution inputs are descriptive only "
                        "and never leakage-safe")
    if integrity in ("unknown", "invalid"):
        warnings.append(f"execution-input provenance is {integrity}; cost "
                        "estimates cannot be trusted as causal")
    part_warn_count = sum(
        1 for r in obs_results
        if r["participation_status"] == "above_configured_threshold")
    if part_warn_count:
        warnings.append(
            f"{part_warn_count} observation(s) exceed the configured "
            f"participation threshold of "
            f"{config['participation_threshold']:g}")
    if regimes:
        rare = [r["regime_label"] for r in regimes["rows"]
                if r["rare_regime_warning"]]
        if rare:
            warnings.append(
                "regime groups with fewer than "
                f"{RARE_REGIME_MIN_OBSERVATIONS} observations: "
                + ", ".join(sorted(rare)))

    for s in sensitivity:
        s["fingerprint"] = fp_mod.scenario_fingerprint(
            run["configuration_fingerprint"], s)
    result_fp = fp_mod.result_fingerprint(
        run["configuration_fingerprint"], obs_results, aggregates, breakeven,
        [{k: s[k] for k in ("commission_multiplier", "spread_multiplier",
                            "slippage_multiplier", "impact_multiplier",
                            "total_cost", "net_total")} for s in sensitivity],
        [{k: c[k] for k in ("scale", "total_cost", "net_total",
                            "max_participation")} for c in capacity],
        warnings, completeness, integrity)

    _json = json
    store.replace_observation_results(run_id, obs_results)
    store.replace_sensitivity_results(run_id, sensitivity)
    store.replace_capacity_results(run_id, capacity)
    store.update_run(run_id, {
        "status": "completed",
        "integrity_status": integrity,
        "completeness_status": completeness,
        "gross_total": aggregates["gross_total"],
        "net_total": aggregates["net_total"],
        "total_cost": aggregates["total_cost"],
        "participation_warning_count": part_warn_count,
        "unavailable_input_count": aggregates["unavailable_cost_count"],
        "result_fingerprint": result_fp,
        "aggregates_json": _json.dumps(aggregates),
        "breakeven_json": _json.dumps(breakeven),
        "regimes_json": _json.dumps(regimes) if regimes else None,
        "warnings_json": _json.dumps(warnings),
        "completed_at": _now(),
        "duration_ms": int((time.monotonic() - t0) * 1000),
        "error_message": None,
    })

    run = store.get_run(run_id)
    assert run is not None
    if create_experiment and not run.get("experiment_id"):
        record = experiment_integration.record_experiment(
            name=f"Cost diagnostics: {run['name']}",
            module="transaction_cost_diagnostics",
            experiment_type="execution_cost_diagnostics",
            status="completed",
            parameters={
                "observation_type": observation_type,
                "commission_model": config["commission"]["model"],
                "spread_model": config["spread"]["model"],
                "slippage_model": config["slippage"]["model"],
                "impact_model": config["impact"]["model"],
                "integrity_status": integrity,
                "completeness_status": completeness,
                "configuration_fingerprint": run["configuration_fingerprint"],
                "result_fingerprint": result_fp,
            },
            metrics={
                "observation_count": run["observation_count"],
                "gross_total": aggregates["gross_total"],
                "net_total": aggregates["net_total"],
                "total_cost": aggregates["total_cost"],
                "participation_warnings": part_warn_count,
                "unavailable_input_observations":
                    aggregates["unavailable_cost_count"],
            },
            tags=["cost-diagnostics"],
            source="transaction_cost_diagnostics",
        )
        if record is not None:
            store.update_run(run_id, {"experiment_id": record["id"]})
    return get_run(run_id)


def invalidate_run(run_id: int, reason: str) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"cost-diagnostic run {run_id} not found")
    if run["status"] == "invalidated":
        raise ConflictError("run is already invalidated")
    store.update_run(run_id, {"status": "invalidated", "error_message": reason,
                              "is_baseline": 0})
    return get_run(run_id)


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------


def _baseline_scope(run: Dict[str, Any]) -> str:
    obs = run["observations"]
    window = (f"{obs[0]['timestamp']}..{obs[-1]['timestamp']}"
              if obs else "none")
    return "|".join([
        f"ds:{run['dataset_version_id'] or 'none'}",
        f"uni:{run['universe_fingerprint'][:16]}",
        f"cm:{run['cost_model_fingerprint'][:16]}",
        "scale:1", f"win:{window}",
    ])


def mark_baseline(run_id: int) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise NotFoundError(f"cost-diagnostic run {run_id} not found")
    if run["status"] != "completed":
        raise ConflictError("baselines require a completed run")
    if run["integrity_status"] not in BASELINE_ACCEPTABLE_INTEGRITY:
        raise ConflictError(
            "baselines require supplied, verified or declared execution-input "
            f"integrity — this run is {run['integrity_status']}")
    if run["completeness_status"] not in BASELINE_ACCEPTABLE_COMPLETENESS:
        raise ConflictError(
            "baselines require complete gross-to-net reconciliation — this "
            f"run is {run['completeness_status']}")
    if not run["result_fingerprint"]:
        raise ConflictError("baselines require a result fingerprint")
    scope = _baseline_scope(run)
    store.update_run(run_id, {"baseline_scope": scope})
    store.mark_baseline(run_id, scope)
    return get_run(run_id)


# ---------------------------------------------------------------------------
# Comparison + export
# ---------------------------------------------------------------------------


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
        raise CostDiagnosticsError("compare requires two different runs")
    a, b = get_run(a_id), get_run(b_id)
    comparability: List[str] = []
    if a["observation_type"] != b["observation_type"]:
        comparability.append("observation types differ — monetary and "
                             "return-space results are not comparable")
    if a["universe_fingerprint"] != b["universe_fingerprint"]:
        comparability.append("observation universes differ — cost totals are "
                             "not directly comparable")
    if a["cost_model_fingerprint"] != b["cost_model_fingerprint"]:
        comparability.append("cost-model assumptions differ")
    if (a.get("currency") or None) != (b.get("currency") or None):
        comparability.append("currencies differ; no FX conversion is applied")
    if (a.get("dataset_version_id") or None) != (b.get("dataset_version_id") or None):
        comparability.append("linked dataset versions differ")
    if a["completeness_status"] != b["completeness_status"]:
        comparability.append("completeness states differ — partial nets "
                             "exclude unavailable components")
    if a["integrity_status"] != b["integrity_status"]:
        comparability.append("execution-input integrity states differ")
    identity = [_entry(f, a.get(f), b.get(f)) for f in (
        "observation_type", "candidate_count", "observation_count", "currency",
        "gross_total", "net_total", "total_cost",
        "participation_warning_count", "unavailable_input_count",
        "integrity_status", "completeness_status", "status", "dataset_name")]
    return {
        "a_id": a_id, "b_id": b_id,
        "comparability_warnings": comparability,
        "groups": {"identity": identity},
        "fingerprint_match": {
            "universe": a["universe_fingerprint"] == b["universe_fingerprint"],
            "cost_model": a["cost_model_fingerprint"] == b["cost_model_fingerprint"],
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
    cost_models: Dict[int, Any] = {}
    observations: Dict[int, Any] = {}
    sensitivity: Dict[int, Any] = {}
    capacity: Dict[int, Any] = {}
    for r in runs:
        cost_models[r["id"]] = store.get_cost_model(r["id"])
        rows: List[Dict[str, Any]] = []
        page = 1
        while True:
            chunk = store.list_observation_results(
                r["id"], page=page, page_size=store.MAX_PAGE_SIZE)
            rows.extend(chunk["items"])
            if page >= max(chunk["total_pages"], 1):
                break
            page += 1
        observations[r["id"]] = rows
        sensitivity[r["id"]] = store.list_sensitivity_results(r["id"])
        capacity[r["id"]] = store.list_capacity_results(r["id"])
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "exported_at": _now(),
        "filters": {k: v for k, v in filters.items() if v is not None},
        "runs": runs,
        "cost_models": cost_models,
        "observation_results": observations,
        "sensitivity_results": sensitivity,
        "capacity_results": capacity,
    }


__all__ = [
    "BASELINE_ACCEPTABLE_INTEGRITY", "BASELINE_ACCEPTABLE_COMPLETENESS",
    "CostDiagnosticsError", "NotFoundError", "ConflictError",
    "create_run", "get_run", "list_runs", "lab_summary", "execute_run",
    "invalidate_run", "mark_baseline", "compare_runs", "export",
]
