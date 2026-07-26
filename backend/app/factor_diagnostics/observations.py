"""
Factor observations, vintage selection and strict timestamp alignment (v1).

Every factor observation declares WHEN it refers to (``source_timestamp``)
and WHEN it could have been known (``available_at``).  Alignment against the
target grid is exact: a factor value is matched to a target period by
timestamp equality after the declared integer lag, never by resampling,
nearest-neighbour search, forward fill or interpolation.  A period whose
factor value is missing leaves the estimation sample with a stated reason.

Timing policies
---------------
``lagged_causal``          every factor lag >= 1 AND ``available_at`` of the
                          value used by period p is <= p's information
                          cutoff.  This is the only policy that can reach a
                          verified integrity state.
``contemporaneous``       lag 0 permitted; DESCRIPTIVE only — a
                          contemporaneous association is never called
                          ex-ante or predictive.
``full_sample_descriptive`` explicitly descriptive over the whole sample.
``future_looking_invalid``  uses a factor value from AFTER the target period
                          (``lead_periods`` >= 1).  Accepted only because the
                          caller declared it invalid; the run is always
                          marked ``invalid`` and can never become a baseline.

Vintage policies (macro revisions)
----------------------------------
``supplied_vintage``               use the observation's own declared value.
``first_release``                  earliest release for that period.
``latest_available_as_of_cutoff``  latest release whose ``release_timestamp``
                                   is <= the consuming period's information
                                   cutoff — a later revision can never reach
                                   an earlier fit.
``full_sample_latest_descriptive`` latest release regardless of timing;
                                   forces a descriptive integrity state.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.factor_diagnostics import definitions as defs

MIN_OBSERVATIONS = 4
MAX_OBSERVATIONS = 2000
MAX_LEAD = 12

TIMING_POLICIES = (
    "lagged_causal", "contemporaneous", "full_sample_descriptive",
    "future_looking_invalid",
)

VINTAGE_POLICIES = (
    "supplied_vintage", "first_release", "latest_available_as_of_cutoff",
    "full_sample_latest_descriptive",
)

QUALITY_STATES = ("observed", "revised", "estimated_by_source", "unknown")

INTEGRITY_STATES = (
    "verified_from_validation_split", "verified_causal_lag",
    "verified_trailing_estimation", "supplied_descriptive",
    "contemporaneous_descriptive", "full_sample_descriptive", "unknown",
    "invalid",
)

_TS_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})?)?$")


class ObservationError(ValueError):
    """Invalid factor observation, alignment or timing policy (HTTP 422)."""


def normalise_timestamp(value: Any, *, field: str) -> str:
    """ISO-8601 timestamps only; comparison is lexicographic on this form."""
    if not isinstance(value, str) or not _TS_PATTERN.match(value):
        raise ObservationError(
            f"{field} must be an ISO-8601 timestamp (YYYY-MM-DD[THH:MM[:SS]])")
    return value.replace(" ", "T")


def validate_timing_policy(value: Any) -> str:
    if value not in TIMING_POLICIES:
        raise ObservationError(
            f"timing_policy must be one of {list(TIMING_POLICIES)}")
    return value


def validate_vintage_policy(value: Any) -> str:
    if value not in VINTAGE_POLICIES:
        raise ObservationError(
            f"vintage_policy must be one of {list(VINTAGE_POLICIES)}")
    return value


def validate_observations(definition: Dict[str, Any],
                          raw: Any) -> List[Dict[str, Any]]:
    """Validate one factor's raw observation list (ordered, unique, finite)."""
    if not isinstance(raw, list) or not raw:
        raise ObservationError(
            f"factor '{definition['factor_id']}' requires at least one "
            f"observation")
    if len(raw) > MAX_OBSERVATIONS:
        raise ObservationError(
            f"at most {MAX_OBSERVATIONS} observations per factor are supported")

    rows: List[Dict[str, Any]] = []
    seen_ids: set = set()
    previous_ts: Optional[str] = None
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ObservationError("each factor observation must be an object")
        unknown = sorted(set(item) - {
            "observation_id", "source_timestamp", "available_at", "value",
            "vintages", "quality_state", "source", "metadata"})
        if unknown:
            raise ObservationError(f"unknown observation keys: {unknown}")

        observation_id = item.get("observation_id") or \
            f"{definition['factor_id']}-{index:04d}"
        if not isinstance(observation_id, str) or len(observation_id) > 80:
            raise ObservationError(
                "observation_id must be a string of at most 80 characters")
        if observation_id in seen_ids:
            raise ObservationError(f"duplicate observation_id {observation_id}")
        seen_ids.add(observation_id)

        source_timestamp = normalise_timestamp(item.get("source_timestamp"),
                                               field="source_timestamp")
        if previous_ts is not None and source_timestamp <= previous_ts:
            raise ObservationError(
                f"factor '{definition['factor_id']}' timestamps must be "
                f"strictly increasing (saw {source_timestamp} after "
                f"{previous_ts})")
        previous_ts = source_timestamp

        available_at = item.get("available_at")
        if available_at is not None:
            available_at = normalise_timestamp(available_at,
                                               field="available_at")
            if available_at < source_timestamp:
                raise ObservationError(
                    f"available_at {available_at} precedes the observation it "
                    f"describes ({source_timestamp})")
        elif definition["availability_policy"] == "explicit_available_at":
            raise ObservationError(
                f"factor '{definition['factor_id']}' declares "
                f"explicit_available_at but observation {observation_id} has "
                f"no available_at timestamp")

        value = item.get("value")
        if value is not None and not defs._finite(value):
            raise ObservationError(
                f"observation {observation_id} value must be finite or null")

        vintages = item.get("vintages")
        vintage_rows: List[Dict[str, Any]] = []
        if vintages is not None:
            if not isinstance(vintages, list) or not vintages:
                raise ObservationError(
                    "vintages must be a non-empty list when supplied")
            if len(vintages) > 12:
                raise ObservationError(
                    "at most 12 vintages per observation are supported")
            previous_release: Optional[str] = None
            for v in vintages:
                if not isinstance(v, dict):
                    raise ObservationError("each vintage must be an object")
                unknown_v = sorted(set(v) - {"release_timestamp", "value",
                                             "vintage_label"})
                if unknown_v:
                    raise ObservationError(f"unknown vintage keys: {unknown_v}")
                release = normalise_timestamp(v.get("release_timestamp"),
                                              field="release_timestamp")
                if release < source_timestamp:
                    raise ObservationError(
                        f"vintage release {release} precedes the period it "
                        f"describes ({source_timestamp})")
                if previous_release is not None and release <= previous_release:
                    raise ObservationError(
                        "vintage release timestamps must be strictly "
                        "increasing")
                previous_release = release
                v_value = v.get("value")
                if not defs._finite(v_value):
                    raise ObservationError("vintage value must be finite")
                label = v.get("vintage_label")
                if label is not None and (not isinstance(label, str)
                                          or len(label) > 80):
                    raise ObservationError(
                        "vintage_label must be a string of at most 80 chars")
                vintage_rows.append({"release_timestamp": release,
                                     "value": float(v_value),
                                     "vintage_label": label})

        quality_state = item.get("quality_state", "observed")
        if quality_state not in QUALITY_STATES:
            raise ObservationError(
                f"quality_state must be one of {list(QUALITY_STATES)}")

        source = item.get("source") or definition["source"]
        if not isinstance(source, str) or len(source) > 200:
            raise ObservationError(
                "observation source must be a string of at most 200 chars")

        metadata = item.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise ObservationError("observation metadata must be an object")
        if len(str(metadata)) > defs.MAX_METADATA_CHARS:
            raise ObservationError(
                f"observation metadata is limited to "
                f"{defs.MAX_METADATA_CHARS} characters")

        if value is None and not vintage_rows:
            # An observation with neither a value nor a vintage is explicitly
            # unavailable; it is kept so the gap stays visible.
            pass

        rows.append({
            "factor_id": definition["factor_id"],
            "observation_id": observation_id,
            "observation_index": index,
            "source_timestamp": source_timestamp,
            "available_at": available_at,
            "raw_value": None if value is None else float(value),
            "vintages": vintage_rows,
            "quality_state": quality_state,
            "source": source,
            "metadata": metadata,
        })
    return rows


def select_vintage(row: Dict[str, Any], policy: str,
                   cutoff: Optional[str]) -> Tuple[Optional[float],
                                                   Optional[str], str]:
    """Return (value, release_timestamp, state) under the vintage policy."""
    vintages = row.get("vintages") or []
    if not vintages:
        if row["raw_value"] is None:
            return None, None, "unavailable"
        return row["raw_value"], None, ("unknown_vintage"
                                        if policy != "supplied_vintage"
                                        else "supplied")
    if policy == "supplied_vintage":
        if row["raw_value"] is None:
            return None, None, "unavailable"
        return row["raw_value"], None, "supplied"
    if policy == "first_release":
        first = vintages[0]
        return first["value"], first["release_timestamp"], "first_release"
    if policy == "full_sample_latest_descriptive":
        last = vintages[-1]
        return last["value"], last["release_timestamp"], "latest_descriptive"
    # latest_available_as_of_cutoff
    if cutoff is None:
        return None, None, "unavailable"
    eligible = [v for v in vintages if v["release_timestamp"] <= cutoff]
    if not eligible:
        return None, None, "no_release_before_cutoff"
    chosen = eligible[-1]
    return chosen["value"], chosen["release_timestamp"], "as_of_cutoff"


def _effective_index(observation_index: int, lag: int, lead: int) -> int:
    """The factor observation that feeds a target period.

    Indexing happens in the FACTOR's own observation sequence, not in the
    target grid, so a factor that carries history BEFORE the target window
    can satisfy a lag (or a differencing transform) at the very first target
    period instead of losing it.
    """
    return observation_index - lag + lead


def align(target: Dict[str, Any], definitions: Sequence[Dict[str, Any]],
          observations: Dict[str, List[Dict[str, Any]]], *,
          timing_policy: str, vintage_policy: str,
          lead_periods: int = 0) -> Dict[str, Any]:
    """Build the aligned observation universe for the configured timing rule.

    Returns the ordered design rows (one per usable target period), the
    excluded periods with reasons, and the availability findings that decide
    whether a causal claim is verified.
    """
    periods = target["periods"]
    if len(periods) < MIN_OBSERVATIONS:
        raise ObservationError(
            f"at least {MIN_OBSERVATIONS} target observations are required")
    if len(periods) > MAX_OBSERVATIONS:
        raise ObservationError(
            f"at most {MAX_OBSERVATIONS} target observations are supported")

    lead = int(lead_periods)
    if timing_policy == "future_looking_invalid":
        if not (1 <= lead <= MAX_LEAD):
            raise ObservationError(
                f"future_looking_invalid requires lead_periods between 1 and "
                f"{MAX_LEAD}")
    elif lead != 0:
        raise ObservationError(
            "lead_periods is only valid under the explicitly invalid "
            "future_looking_invalid timing policy")
    if timing_policy == "lagged_causal":
        zero_lag = [d["factor_id"] for d in definitions if d["lag"] < 1]
        if zero_lag:
            raise ObservationError(
                f"lagged_causal requires every factor lag >= 1; factors with "
                f"lag 0: {zero_lag}")

    # Per factor: index observations by timestamp and build the raw series in
    # the target's own order, selecting the vintage with that period's cutoff.
    by_factor: Dict[str, Dict[str, Any]] = {}
    for definition in definitions:
        factor_id = definition["factor_id"]
        rows = observations.get(factor_id) or []
        if not rows:
            raise ObservationError(f"factor '{factor_id}' has no observations")
        stamps = [r["source_timestamp"] for r in rows]
        by_factor[factor_id] = {
            "definition": definition,
            "rows": rows,
            "index_by_timestamp": {ts: i for i, ts in enumerate(stamps)},
        }

    # The factor grid must contain the target grid: each target period start
    # has to exist as a factor observation timestamp (strict alignment).
    grid = [p["period_start"] for p in periods]
    for factor_id, bundle in by_factor.items():
        missing = [ts for ts in grid if ts not in bundle["index_by_timestamp"]]
        if missing:
            raise ObservationError(
                f"factor '{factor_id}' has no observation at target timestamps "
                f"{missing[:3]}{'...' if len(missing) > 3 else ''}; v1 aligns "
                f"by exact timestamp and never resamples or fills")

    # Vintage selection + transformation, in observation order.
    for factor_id, bundle in by_factor.items():
        rows = bundle["rows"]
        cutoffs: List[Optional[str]] = [None] * len(rows)
        definition = bundle["definition"]
        for period_index, period in enumerate(periods):
            anchor = bundle["index_by_timestamp"][grid[period_index]]
            source_index = _effective_index(anchor, definition["lag"], lead)
            if 0 <= source_index < len(rows):
                cutoffs[source_index] = period["information_available_at"]
        raw_series: List[Optional[float]] = []
        vintage_states: List[str] = []
        release_stamps: List[Optional[str]] = []
        for obs_index, row in enumerate(rows):
            value, release, state = select_vintage(row, vintage_policy,
                                                   cutoffs[obs_index])
            raw_series.append(value)
            vintage_states.append(state)
            release_stamps.append(release)
        bundle["raw_series"] = raw_series
        bundle["vintage_states"] = vintage_states
        bundle["release_stamps"] = release_stamps
        bundle["transformed"] = defs.transform_series(raw_series, definition)

    factor_ids = [d["factor_id"] for d in definitions]
    design_rows: List[Dict[str, Any]] = []
    excluded: List[Dict[str, Any]] = []
    availability_failures: List[Dict[str, Any]] = []
    availability_checked = 0

    for period_index, period in enumerate(periods):
        values: List[float] = []
        sources: List[Dict[str, Any]] = []
        reason: Optional[str] = None
        for definition in definitions:
            factor_id = definition["factor_id"]
            bundle = by_factor[factor_id]
            anchor = bundle["index_by_timestamp"][grid[period_index]]
            obs_index = _effective_index(anchor, definition["lag"], lead)
            if obs_index < 0 or obs_index >= len(bundle["rows"]):
                reason = (f"factor '{factor_id}' has no observation "
                          f"{definition['lag']} period(s) before this period")
                break
            value = bundle["transformed"][obs_index]
            row = bundle["rows"][obs_index]
            if value is None:
                reason = (f"factor '{factor_id}' has no transformed value at "
                          f"{row['source_timestamp']} "
                          f"({bundle['vintage_states'][obs_index]})")
                break
            available_at = row["available_at"] or row["source_timestamp"]
            release = bundle["release_stamps"][obs_index]
            knowable_at = max([s for s in (available_at, release) if s])
            if timing_policy == "lagged_causal":
                availability_checked += 1
                if knowable_at > period["information_available_at"]:
                    availability_failures.append({
                        "period_index": period_index,
                        "factor_id": factor_id,
                        "knowable_at": knowable_at,
                        "information_available_at":
                            period["information_available_at"],
                    })
            values.append(float(value))
            sources.append({
                "factor_id": factor_id,
                "observation_id": row["observation_id"],
                "source_timestamp": row["source_timestamp"],
                "effective_timestamp": period["period_start"],
                "available_at": available_at,
                "knowable_at": knowable_at,
                "release_timestamp": release,
                "vintage_state": bundle["vintage_states"][obs_index],
                "quality_state": row["quality_state"],
            })
        if reason is not None:
            excluded.append({"period_index": period_index,
                             "period_start": period["period_start"],
                             "reason": reason})
            continue
        design_rows.append({
            "period_index": period_index,
            "period_start": period["period_start"],
            "period_end": period["period_end"],
            "information_available_at": period["information_available_at"],
            "target_return": period["target_return"],
            "factor_values": values,
            "factor_sources": sources,
        })

    if len(design_rows) < MIN_OBSERVATIONS:
        raise ObservationError(
            f"only {len(design_rows)} aligned observation(s) remain after "
            f"strict alignment; at least {MIN_OBSERVATIONS} are required "
            f"(nothing is filled in to reach the minimum)")

    return {
        "factor_ids": factor_ids,
        "rows": design_rows,
        "excluded_periods": excluded,
        "timing_policy": timing_policy,
        "vintage_policy": vintage_policy,
        "lead_periods": lead,
        "availability_checked": availability_checked,
        "availability_failures": availability_failures,
        "observation_count": len(design_rows),
    }


def classify_integrity(*, timing_policy: str, vintage_policy: str,
                       target: Dict[str, Any], alignment: Dict[str, Any],
                       validation: Optional[Dict[str, Any]],
                       estimation_scope: str) -> Tuple[str, List[str]]:
    """Integrity state + the warnings that justify it."""
    warnings: List[str] = []
    if timing_policy == "future_looking_invalid":
        warnings.append(
            f"INVALID timing: factor values are taken "
            f"{alignment['lead_periods']} period(s) AFTER the target period; "
            f"this run is descriptive of an impossible information set and "
            f"can never become a baseline.")
        return "invalid", warnings
    if alignment["availability_failures"]:
        first = alignment["availability_failures"][0]
        warnings.append(
            f"INVALID timing: factor '{first['factor_id']}' was knowable only "
            f"at {first['knowable_at']}, after the information cutoff "
            f"{first['information_available_at']} of the period it explains "
            f"({len(alignment['availability_failures'])} occurrence(s)).")
        return "invalid", warnings

    if vintage_policy == "full_sample_latest_descriptive":
        warnings.append(
            "Vintage policy full_sample_latest_descriptive uses the latest "
            "revision of every observation, including revisions published "
            "after the periods they describe — descriptive only.")
        return "full_sample_descriptive", warnings

    if timing_policy == "full_sample_descriptive":
        warnings.append(
            "Full-sample descriptive fit: coefficients are estimated over the "
            "whole sample and describe it; they are not an out-of-sample or "
            "ex-ante statement.")
        return "full_sample_descriptive", warnings

    if timing_policy == "contemporaneous":
        warnings.append(
            "Contemporaneous alignment: factor values carry the same period "
            "stamp as the target return, so the relationship is descriptive "
            "association only and is never ex-ante or predictive.")
        return "contemporaneous_descriptive", warnings

    # lagged_causal from here.  The timing claim is about the factor
    # information order, so it is verified independently of where the target
    # series came from; a supplied target still gets its own provenance
    # warning because its values are the caller's, not a stored measurement.
    if target.get("provenance_status") == "supplied_descriptive":
        warnings.append(
            "The target series was supplied directly rather than read from a "
            "stored run: the verified timing statement covers the FACTOR "
            "information order, not the provenance of the target values.")
    if validation is not None:
        if validation.get("leakage_clean") is False:
            warnings.append(
                "Linked model-validation run reports leakage; the causal "
                "timing claim is withheld and the fit stays descriptive.")
            return "supplied_descriptive", warnings
        return "verified_from_validation_split", warnings
    if estimation_scope == "rolling_trailing":
        return "verified_trailing_estimation", warnings
    return "verified_causal_lag", warnings


__all__ = [
    "MIN_OBSERVATIONS", "MAX_OBSERVATIONS", "MAX_LEAD", "TIMING_POLICIES",
    "VINTAGE_POLICIES", "QUALITY_STATES", "INTEGRITY_STATES",
    "ObservationError", "normalise_timestamp", "validate_timing_policy",
    "validate_vintage_policy", "validate_observations", "select_vintage",
    "align", "classify_integrity",
]
