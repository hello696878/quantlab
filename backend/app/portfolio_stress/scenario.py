"""
Scenario-definition model, units, precedence and integrity (v1).

Scenario types: ``historical_window`` / ``historical_single_period``
(replay of actual stored observations under an explicit timing usage),
``hypothetical_asset_shock`` / ``hypothetical_group_shock``,
``volatility_stress``, ``correlation_stress``,
``liquidity_and_cost_stress``, ``combined_scenario``, and
``user_supplied_descriptive``.

Shock units are explicit and unambiguous: ``return`` (decimal, −0.05 =
−5%), ``percent`` (−5 = −5%), ``bps`` (−500 = −5%).  Absolute price
changes are NOT supported in v1 — stored portfolio universes carry
returns, not reference prices, and the lab never fabricates a price.

``metadata`` is free-form descriptive labelling (bounded, stringified).
It is stored verbatim with the definition but deliberately does NOT enter
the scenario fingerprint: it cannot change any computed result, so two
runs differing only in metadata are the same scenario.

Precedence (documented, deterministic): an asset-specific shock overrides
its group shock; a group shock overrides the global shock; assets covered
by none follow the explicit missing-shock policy (``zero`` — an
explicitly configured "unshocked" assumption — or ``unavailable``, which
withholds the scenario P&L for that asset and marks the run partial).
Overlapping shocks are never combined additively unless every level is
explicitly configured (the precedence chain always selects exactly one).

Integrity states: ``verified_historical_window`` (window of actual stored
observations; an ex-ante claim additionally requires the window to end
strictly before the portfolio decision cutoff — otherwise the scenario is
``invalid``), ``verified_deterministic_rule`` (fully explicit hypothetical
parameters), ``supplied_descriptive`` (user-supplied outcomes — never
called verified), ``full_sample_descriptive`` (a window spanning the whole
sample), ``unknown``, ``invalid``.  ``linked_to_stored_regime`` is
reserved and not used in v1 (documented).  Factor shocks are DEFERRED: no
estimated, run-linked factor-exposure system exists in this repository,
and exposures are never inferred from asset names.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

SCENARIO_TYPES = (
    "historical_window", "historical_single_period",
    "hypothetical_asset_shock", "hypothetical_group_shock",
    "volatility_stress", "correlation_stress", "liquidity_and_cost_stress",
    "combined_scenario", "user_supplied_descriptive",
)
SHOCK_UNITS = ("return", "percent", "bps")
MISSING_SHOCK_POLICIES = ("zero", "unavailable")
HISTORICAL_USAGES = ("ex_ante", "descriptive")
CORRELATION_MODES = ("uniform_multiplier", "additive", "toward_one",
                     "supplied")
VOLATILITY_MODES = ("multiplicative", "additive")
INTEGRITY_STATES = ("verified_historical_window",
                    "verified_deterministic_rule", "supplied_descriptive",
                    "full_sample_descriptive", "unknown", "invalid")

MAX_SHOCK_RETURN = 1.0          # |shock| <= 100% in return space
MAX_VOL_MULTIPLIER = 10.0
MAX_ADDITIVE_VOL = 1.0
MAX_LIQUIDITY_MULTIPLIER = 100.0


class ScenarioError(ValueError):
    """Raised for invalid scenario definitions."""


def shock_to_return(value: float, unit: str) -> float:
    if unit == "return":
        return value
    if unit == "percent":
        return value / 100.0
    return value / 10_000.0  # bps


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScenarioError(f"{field} must be a finite number")
    f = float(value)
    if not math.isfinite(f):
        raise ScenarioError(f"{field} must be a finite number")
    return f


def _shock_entry(raw: Any, field: str) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ScenarioError(f"{field} must be an object with value and unit")
    unit = raw.get("unit")
    if unit not in SHOCK_UNITS:
        raise ScenarioError(
            f"{field}: unit must be one of {', '.join(SHOCK_UNITS)} "
            "(absolute price changes are not supported without reference "
            "prices)")
    value = _finite(raw.get("value"), f"{field}.value")
    as_return = shock_to_return(value, unit)
    if abs(as_return) > MAX_SHOCK_RETURN:
        raise ScenarioError(
            f"{field}: shock exceeds ±100% in return space")
    return {"value": value, "unit": unit, "as_return": as_return}


def _positive_multiplier(raw: Any, field: str, *, lo: float = 0.0,
                         hi: float = MAX_LIQUIDITY_MULTIPLIER) -> float:
    f = _finite(raw, field)
    if not (lo < f <= hi):
        raise ScenarioError(f"{field} must be in ({lo:g}, {hi:g}]")
    return f


def validate_scenario(raw: Any, *, asset_ids: List[str],
                      groups: List[str]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ScenarioError("scenario definition must be an object")
    scenario_type = raw.get("scenario_type")
    if scenario_type not in SCENARIO_TYPES:
        raise ScenarioError(
            f"scenario_type must be one of {', '.join(SCENARIO_TYPES)}")
    if "factor_shocks" in raw:
        raise ScenarioError(
            "factor shocks are deferred in v1: no estimated, run-linked "
            "factor-exposure system exists in this repository, and "
            "exposures are never inferred from asset names")
    known_keys = {"scenario_definition_id", "name", "description",
                  "scenario_type", "source", "missing_shock_policy",
                  "asset_shocks", "group_shocks", "global_shock",
                  "volatility_stress", "correlation_stress",
                  "liquidity_cost_stress", "historical", "metadata"}
    unknown_keys = set(raw) - known_keys
    if unknown_keys:
        raise ScenarioError(
            "unsupported scenario keys (a typo is never silently ignored): "
            + ", ".join(sorted(unknown_keys)))
    out: Dict[str, Any] = {
        "scenario_definition_id": str(raw.get("scenario_definition_id")
                                      or "scenario")[:64],
        "name": str(raw.get("name") or "Scenario")[:200],
        "description": str(raw.get("description") or "")[:2000],
        "scenario_type": scenario_type,
        "source": str(raw.get("source") or "user")[:200],
        "units_note": "return = decimal; percent = value/100; "
                      "bps = value/10000",
        "precedence": "asset shock overrides group shock overrides global "
                      "shock; unspecified assets follow the missing-shock "
                      "policy",
    }
    policy = raw.get("missing_shock_policy", "zero")
    if policy not in MISSING_SHOCK_POLICIES:
        raise ScenarioError(
            "missing_shock_policy must be one of "
            f"{', '.join(MISSING_SHOCK_POLICIES)}")
    out["missing_shock_policy"] = policy

    known_assets = set(asset_ids)
    known_groups = set(groups)

    asset_shocks: Dict[str, Dict[str, Any]] = {}
    for aid, spec in dict(raw.get("asset_shocks") or {}).items():
        if aid not in known_assets:
            raise ScenarioError(f"asset shock references unknown asset {aid!r}")
        asset_shocks[aid] = _shock_entry(spec, f"asset_shocks[{aid}]")
    out["asset_shocks"] = asset_shocks

    group_shocks: Dict[str, Dict[str, Any]] = {}
    for gid, spec in dict(raw.get("group_shocks") or {}).items():
        if gid not in known_groups:
            raise ScenarioError(f"group shock references unknown group {gid!r}")
        group_shocks[gid] = _shock_entry(spec, f"group_shocks[{gid}]")
    out["group_shocks"] = group_shocks

    out["global_shock"] = (_shock_entry(raw["global_shock"], "global_shock")
                           if raw.get("global_shock") is not None else None)

    # volatility stress
    vol = raw.get("volatility_stress")
    if vol is not None:
        if not isinstance(vol, dict):
            raise ScenarioError("volatility_stress must be an object")
        mode = vol.get("mode", "multiplicative")
        if mode not in VOLATILITY_MODES:
            raise ScenarioError(
                f"volatility_stress.mode must be one of "
                f"{', '.join(VOLATILITY_MODES)}")
        entry: Dict[str, Any] = {"mode": mode}
        if mode == "multiplicative":
            uniform = vol.get("multiplier")
            per_asset = dict(vol.get("multipliers") or {})
            if uniform is None and not per_asset:
                raise ScenarioError(
                    "multiplicative volatility stress needs a multiplier or "
                    "per-asset multipliers")
            if uniform is not None:
                entry["multiplier"] = _positive_multiplier(
                    uniform, "volatility multiplier", hi=MAX_VOL_MULTIPLIER)
            mm = {}
            for aid, m in per_asset.items():
                if aid not in known_assets:
                    raise ScenarioError(
                        f"volatility multiplier references unknown asset {aid!r}")
                mm[aid] = _positive_multiplier(
                    m, f"volatility multiplier[{aid}]", hi=MAX_VOL_MULTIPLIER)
            entry["multipliers"] = mm
        else:  # additive, per-period volatility units
            add = _finite(vol.get("value"), "additive volatility value")
            if abs(add) > MAX_ADDITIVE_VOL:
                raise ScenarioError(
                    f"additive volatility must be within ±{MAX_ADDITIVE_VOL:g}")
            entry["value"] = add
            entry["units"] = "per-period volatility (same units as the "\
                             "baseline covariance diagonal square root)"
        out["volatility_stress"] = entry
    else:
        out["volatility_stress"] = None

    # correlation stress
    corr = raw.get("correlation_stress")
    if corr is not None:
        if not isinstance(corr, dict):
            raise ScenarioError("correlation_stress must be an object")
        mode = corr.get("mode")
        if mode not in CORRELATION_MODES:
            raise ScenarioError(
                f"correlation_stress.mode must be one of "
                f"{', '.join(CORRELATION_MODES)}")
        entry = {"mode": mode}
        if mode == "uniform_multiplier":
            entry["value"] = _positive_multiplier(
                corr.get("value"), "correlation multiplier", hi=2.0)
        elif mode == "additive":
            v = _finite(corr.get("value"), "correlation additive value")
            if abs(v) > 2.0:
                raise ScenarioError("additive correlation shock must be within ±2")
            entry["value"] = v
        elif mode == "toward_one":
            alpha = _finite(corr.get("alpha"), "correlation alpha")
            if not (0.0 <= alpha <= 1.0):
                raise ScenarioError("correlation alpha must be in [0, 1]")
            entry["alpha"] = alpha
            entry["formula"] = "rho_stressed = rho + alpha * (1 - rho)"
        else:  # supplied
            matrix = corr.get("matrix")
            n = len(asset_ids)
            if not isinstance(matrix, list) or len(matrix) != n or any(
                    not isinstance(row, list) or len(row) != n
                    for row in matrix):
                raise ScenarioError(
                    "supplied correlation must be an n x n matrix in the "
                    "portfolio's asset order")
            clean = []
            for i, row in enumerate(matrix):
                crow = []
                for j, v in enumerate(row):
                    f = _finite(v, f"correlation[{i}][{j}]")
                    if not (-1.0 <= f <= 1.0):
                        raise ScenarioError(
                            "supplied correlations must lie in [-1, 1]")
                    crow.append(f)
                clean.append(crow)
            for i in range(n):
                if clean[i][i] != 1.0:
                    raise ScenarioError(
                        "supplied correlation diagonal must be exactly 1 "
                        "(it is never silently overwritten)")
                for j in range(i + 1, n):
                    if abs(clean[i][j] - clean[j][i]) > 1e-9:
                        raise ScenarioError(
                            "supplied correlation must be symmetric (it is "
                            "never silently symmetrized)")
            entry["matrix"] = clean
        repair = corr.get("repair", "none")
        if repair not in ("none", "eigenvalue_floor"):
            raise ScenarioError(
                "correlation repair must be 'none' or 'eigenvalue_floor'")
        entry["repair"] = repair
        if repair == "eigenvalue_floor":
            floor = _finite(corr.get("eigenvalue_floor", 1e-10),
                            "eigenvalue_floor")
            if not (0.0 < floor <= 1.0):
                raise ScenarioError("eigenvalue_floor must be in (0, 1]")
            entry["eigenvalue_floor"] = floor
        out["correlation_stress"] = entry
    else:
        out["correlation_stress"] = None

    # liquidity and cost stress
    liq = raw.get("liquidity_cost_stress")
    if liq is not None:
        if not isinstance(liq, dict):
            raise ScenarioError("liquidity_cost_stress must be an object")
        if liq.get("cost_volatility_multiplier") is not None:
            raise ScenarioError(
                "cost_volatility_multiplier is deferred in v1: the period "
                "cost path has no volatility input to stress, and a "
                "configured assumption is never silently dropped")
        entry = {}
        for field in ("spread_multiplier", "slippage_multiplier",
                      "adv_multiplier", "impact_multiplier",
                      "notional_scale"):
            if liq.get(field) is not None:
                entry[field] = _positive_multiplier(liq[field], field)
        base_adv = liq.get("base_adv_notional")
        if base_adv is not None:
            entry["base_adv_notional"] = _positive_multiplier(
                base_adv, "base_adv_notional", hi=1e15)
        threshold = liq.get("participation_threshold")
        if threshold is not None:
            entry["participation_threshold"] = _positive_multiplier(
                threshold, "participation_threshold", hi=10.0)
        if not entry:
            raise ScenarioError(
                "liquidity_cost_stress must configure at least one multiplier")
        out["liquidity_cost_stress"] = entry
    else:
        out["liquidity_cost_stress"] = None

    # historical window
    hist = raw.get("historical")
    if scenario_type in ("historical_window", "historical_single_period"):
        if asset_shocks or group_shocks or out["global_shock"] is not None:
            raise ScenarioError(
                "historical scenarios replay stored observations; explicit "
                "asset/group/global shocks would be silently overridden and "
                "are therefore rejected")
        if not isinstance(hist, dict):
            raise ScenarioError(
                "historical scenarios require a historical block")
        usage = hist.get("usage")
        if usage not in HISTORICAL_USAGES:
            raise ScenarioError(
                f"historical.usage must be one of {', '.join(HISTORICAL_USAGES)}")
        start = hist.get("start_timestamp")
        end = hist.get("end_timestamp")
        if scenario_type == "historical_single_period":
            if end is not None and end != start:
                raise ScenarioError(
                    "historical_single_period replays exactly one stored "
                    "observation; a differing end_timestamp is rejected "
                    "rather than silently widening the window")
            end = start
        if not isinstance(start, str) or not isinstance(end, str):
            raise ScenarioError(
                "historical scenarios require start/end timestamps")
        out["historical"] = {"usage": usage, "start_timestamp": start,
                             "end_timestamp": end}
    else:
        out["historical"] = None

    # type-specific requirements
    if scenario_type in ("hypothetical_asset_shock",) and not asset_shocks \
            and out["global_shock"] is None:
        raise ScenarioError(
            "hypothetical_asset_shock requires asset shocks or a global shock")
    if scenario_type == "hypothetical_group_shock" and not group_shocks:
        raise ScenarioError("hypothetical_group_shock requires group shocks")
    if scenario_type == "volatility_stress" and out["volatility_stress"] is None:
        raise ScenarioError("volatility_stress requires a volatility block")
    if scenario_type == "correlation_stress" and out["correlation_stress"] is None:
        raise ScenarioError("correlation_stress requires a correlation block")
    if scenario_type == "liquidity_and_cost_stress" \
            and out["liquidity_cost_stress"] is None:
        raise ScenarioError(
            "liquidity_and_cost_stress requires a liquidity block")
    metadata = raw.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise ScenarioError("scenario metadata must be an object")
    metadata = dict(metadata or {})
    if len(metadata) > 20:
        raise ScenarioError("scenario metadata supports at most 20 keys")
    out["metadata"] = {str(k)[:64]: (v if isinstance(v, (int, float, bool))
                                     or v is None else str(v)[:500])
                       for k, v in sorted(metadata.items(),
                                          key=lambda kv: str(kv[0]))}
    return out


def classify_integrity(scenario: Dict[str, Any], *,
                       timeline: List[str],
                       decision_timestamp: Optional[str]) -> Dict[str, Any]:
    """Integrity classification (module doc).  Returns state + warnings."""
    warnings: List[str] = []
    stype = scenario["scenario_type"]
    if stype in ("historical_window", "historical_single_period"):
        hist = scenario["historical"]
        index = {ts: i for i, ts in enumerate(timeline)}
        if hist["start_timestamp"] not in index \
                or hist["end_timestamp"] not in index:
            return {"integrity": "invalid",
                    "warnings": ["historical window does not reference "
                                 "actual stored observations"]}
        s, e = index[hist["start_timestamp"]], index[hist["end_timestamp"]]
        if e < s:
            return {"integrity": "invalid",
                    "warnings": ["historical window end precedes its start"]}
        if hist["usage"] == "ex_ante":
            if decision_timestamp is None or decision_timestamp not in index:
                return {"integrity": "invalid",
                        "warnings": ["ex-ante usage requires a portfolio "
                                     "decision timestamp on the timeline"]}
            if e >= index[decision_timestamp]:
                return {"integrity": "invalid",
                        "warnings": [
                            "historical window claimed ex-ante extends to or "
                            "beyond the portfolio decision cutoff — a future "
                            "period is never labelled ex-ante verified"]}
        else:
            warnings.append("descriptive historical usage: realized "
                            "post-decision analysis, not an ex-ante stress")
        if s == 0 and e == len(timeline) - 1:
            warnings.append("the historical window spans the full sample — "
                            "descriptive only")
            return {"integrity": "full_sample_descriptive",
                    "warnings": warnings}
        return {"integrity": "verified_historical_window",
                "warnings": warnings}
    if stype == "user_supplied_descriptive":
        return {"integrity": "supplied_descriptive",
                "warnings": ["user-supplied scenario: descriptive, never "
                             "independently verified"]}
    return {"integrity": "verified_deterministic_rule", "warnings": warnings}
