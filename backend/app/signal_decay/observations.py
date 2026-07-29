"""
Signal observations, outcomes, forecast horizons and alignment (v1).

Timing contract
---------------
For a signal observed at grid index ``i`` of an entity's own stored
timestamp grid, under entry lag ``l`` and horizon ``k`` (both in
**observations** — steps on that grid):

* the decision cutoff and outcome ENTRY are at grid index ``i + l``;
* the outcome EXIT is at grid index ``i + l + k``;
* ``forward_return = exit_price / entry_price - 1`` with both prices read
  by EXACT timestamp on the same grid — nothing is interpolated,
  back-filled or resampled, and a missing price leaves the pair
  unavailable;
* the pair is USED only when the signal was available at or before its
  entry timestamp; a violation marks the whole run ``invalid`` with the
  first offence named.

The outcome interval convention is explicit: the return is earned over
``(entry_ts, exit_ts]`` and, for overlap arithmetic, intervals are compared
as half-open index ranges ``[entry_index, exit_index)`` so two back-to-back
holdings (exit of one = entry of the next) do NOT overlap.

Horizon units
-------------
v1 supports ``observations`` (with ``stored_periods`` as a synonym): steps
on each entity's own stored grid.  Clock units (seconds … days) are
DEFERRED with the reason stated: exact-timestamp arithmetic over an
irregular stored grid would require resampling, which this lab never does.

Overlap
-------
Consecutive signals with ``k > 1`` produce overlapping outcome intervals.
Overlap is measured and disclosed, never hidden: interval count, count of
intervals overlapping at least one other, overlap ratio, the maximum number
of simultaneously open intervals, and a documented descriptive
approximation ``ceil(n / k)`` of the non-overlapping sample count.  The
deterministic non-overlap policy is: walk each entity's usable pairs in
time order, keep the earliest, then keep the next pair whose entry index is
at or after the previously kept pair's exit index.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.signal_decay.definitions import DefinitionError

MIN_OBSERVATIONS = 4
MAX_ENTITIES = 100
MAX_OBSERVATIONS_TOTAL = 20000
MAX_HORIZONS = 12
MAX_LAGS = 6
MAX_HORIZON_VALUE = 250
MAX_LAG_VALUE = 60

HORIZON_UNITS = ("observations", "stored_periods")
DEFERRED_HORIZON_UNITS = {
    "seconds": "clock units are deferred in v1: exact-timestamp arithmetic "
               "over an irregular stored grid would require resampling, "
               "which this lab never does",
    "minutes": "clock units are deferred in v1 (see 'seconds')",
    "hours": "clock units are deferred in v1 (see 'seconds')",
    "days": "clock units are deferred in v1 (see 'seconds')",
}

OVERLAP_POLICIES = ("overlapping", "non_overlapping")

INTEGRITY_STATES = (
    "verified_from_validation_split", "verified_point_in_time",
    "verified_trailing_signal", "supplied_descriptive",
    "full_sample_descriptive", "unknown", "invalid",
)

OVERLAP_STATES = ("non_overlapping", "partially_overlapping", "overlapping",
                  "not_applicable")

_TS_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})?)?$")


class ObservationError(ValueError):
    """Invalid observation, outcome, horizon or alignment input (HTTP 422)."""


def _finite(value: Any) -> bool:
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(float(value)))


def normalise_timestamp(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not _TS_PATTERN.match(value):
        raise ObservationError(
            f"{field} must be an ISO-8601 timestamp (YYYY-MM-DD[THH:MM[:SS]])")
    return value.replace(" ", "T")


# ---------------------------------------------------------------------------
# Signal observations
# ---------------------------------------------------------------------------

def validate_signal_observations(definition: Dict[str, Any],
                                 raw: Any) -> List[Dict[str, Any]]:
    """Validated observation rows in deterministic (entity, timestamp) order."""
    if not isinstance(raw, list) or not raw:
        raise ObservationError("at least one signal observation is required")
    if len(raw) > MAX_OBSERVATIONS_TOTAL:
        raise ObservationError(
            f"at most {MAX_OBSERVATIONS_TOTAL} signal observations are "
            f"supported")

    rows: List[Dict[str, Any]] = []
    seen_ids: set = set()
    seen_pairs: set = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ObservationError("each signal observation must be an object")
        unknown = sorted(set(item) - {
            "observation_id", "entity_id", "source_timestamp", "generated_at",
            "available_at", "value", "universe_membership_id", "metadata"})
        if unknown:
            raise ObservationError(f"unknown observation keys: {unknown}")

        entity_id = item.get("entity_id", "aggregate")
        if not isinstance(entity_id, str) or not (1 <= len(entity_id) <= 64):
            raise ObservationError("entity_id must be 1-64 characters")

        source_timestamp = normalise_timestamp(item.get("source_timestamp"),
                                               field="source_timestamp")
        pair = (entity_id, source_timestamp)
        if pair in seen_pairs:
            raise ObservationError(
                f"duplicate entity/timestamp pair {entity_id} @ "
                f"{source_timestamp}")
        seen_pairs.add(pair)

        observation_id = item.get("observation_id") or \
            f"{entity_id}-{index:05d}"
        if not isinstance(observation_id, str) or len(observation_id) > 80:
            raise ObservationError(
                "observation_id must be a string of at most 80 characters")
        if observation_id in seen_ids:
            raise ObservationError(f"duplicate observation_id {observation_id}")
        seen_ids.add(observation_id)

        generated_at = item.get("generated_at")
        if generated_at is not None:
            generated_at = normalise_timestamp(generated_at,
                                               field="generated_at")

        available_at = item.get("available_at")
        if available_at is not None:
            available_at = normalise_timestamp(available_at,
                                               field="available_at")
        elif definition["availability_policy"] == "explicit_available_at":
            raise ObservationError(
                f"observation {observation_id} has no available_at, but the "
                f"signal declares explicit_available_at; availability is "
                f"never fabricated")
        if generated_at is not None and available_at is not None \
                and available_at < generated_at:
            raise ObservationError(
                f"observation {observation_id}: available_at precedes "
                f"generated_at")

        value = item.get("value")
        if value is not None and not _finite(value):
            raise ObservationError(
                f"observation {observation_id} value must be finite or null")

        metadata = item.get("metadata") or {}
        if not isinstance(metadata, dict) or len(str(metadata)) > 2000:
            raise ObservationError(
                "observation metadata must be an object of at most 2000 "
                "rendered characters")

        rows.append({
            "observation_id": observation_id,
            "entity_id": entity_id,
            "source_timestamp": source_timestamp,
            "generated_at": generated_at,
            "available_at": available_at or source_timestamp,
            "availability_assumed": available_at is None,
            "raw_value": None if value is None else float(value),
            "universe_membership_id": item.get("universe_membership_id"),
            "metadata": metadata,
        })

    rows.sort(key=lambda r: (r["entity_id"], r["source_timestamp"]))
    entities = sorted({r["entity_id"] for r in rows})
    if len(entities) > MAX_ENTITIES:
        raise ObservationError(f"at most {MAX_ENTITIES} entities are supported")

    previous: Dict[str, str] = {}
    for row in rows:
        last = previous.get(row["entity_id"])
        if last is not None and row["source_timestamp"] <= last:
            raise ObservationError(
                f"timestamps must be strictly increasing within entity "
                f"{row['entity_id']}")
        previous[row["entity_id"]] = row["source_timestamp"]
    return rows


# ---------------------------------------------------------------------------
# Prices and supplied outcomes
# ---------------------------------------------------------------------------

def validate_prices(raw: Any, price_field: str) -> Dict[Tuple[str, str], float]:
    """{(entity_id, timestamp): price} — exact-match lookups only."""
    if not isinstance(raw, list) or not raw:
        raise ObservationError(
            "forward_return outcomes require a prices list")
    if len(raw) > MAX_OBSERVATIONS_TOTAL * 2:
        raise ObservationError("too many price rows")
    out: Dict[Tuple[str, str], float] = {}
    for item in raw:
        if not isinstance(item, dict):
            raise ObservationError("each price row must be an object")
        unknown = sorted(set(item) - {"entity_id", "timestamp", price_field,
                                      "provenance"})
        if unknown:
            raise ObservationError(
                f"unknown price keys: {unknown} (the declared price_field is "
                f"'{price_field}')")
        entity_id = item.get("entity_id", "aggregate")
        stamp = normalise_timestamp(item.get("timestamp"), field="timestamp")
        value = item.get(price_field)
        if value is None:
            continue  # an explicit gap: the pair using it stays unavailable
        if not _finite(value) or float(value) <= 0.0:
            raise ObservationError(
                f"price for {entity_id} @ {stamp} must be a finite positive "
                f"number or null")
        key = (entity_id, stamp)
        if key in out:
            raise ObservationError(
                f"duplicate price for {entity_id} @ {stamp}")
        out[key] = float(value)
    return out


def validate_supplied_outcomes(raw: Any) -> List[Dict[str, Any]]:
    """Supplied outcomes keyed to the signal observation they pair with."""
    if not isinstance(raw, list) or not raw:
        raise ObservationError(
            "supplied_outcome runs require an outcomes list")
    if len(raw) > MAX_OBSERVATIONS_TOTAL:
        raise ObservationError("too many outcome rows")
    rows: List[Dict[str, Any]] = []
    seen: set = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ObservationError("each outcome row must be an object")
        unknown = sorted(set(item) - {
            "entity_id", "signal_timestamp", "period_start", "period_end",
            "available_at", "value"})
        if unknown:
            raise ObservationError(f"unknown outcome keys: {unknown}")
        entity_id = item.get("entity_id", "aggregate")
        signal_stamp = normalise_timestamp(item.get("signal_timestamp"),
                                           field="signal_timestamp")
        start = normalise_timestamp(item.get("period_start"),
                                    field="period_start")
        end = normalise_timestamp(item.get("period_end"), field="period_end")
        if end <= start:
            raise ObservationError(
                f"outcome period_end must be after period_start "
                f"({entity_id} @ {signal_stamp})")
        available_at = item.get("available_at")
        available_at = (normalise_timestamp(available_at, field="available_at")
                        if available_at is not None else end)
        value = item.get("value")
        if value is not None and not _finite(value):
            raise ObservationError("outcome value must be finite or null")
        key = (entity_id, signal_stamp)
        if key in seen:
            raise ObservationError(
                f"duplicate supplied outcome for {entity_id} @ {signal_stamp}")
        seen.add(key)
        rows.append({
            "entity_id": entity_id, "signal_timestamp": signal_stamp,
            "period_start": start, "period_end": end,
            "available_at": available_at,
            "value": None if value is None else float(value),
        })
    return rows


# ---------------------------------------------------------------------------
# Horizons and lags
# ---------------------------------------------------------------------------

def validate_horizons(raw: Any, *, supplied_outcomes: bool) -> Dict[str, Any]:
    cfg = dict(raw or {})
    unknown = sorted(set(cfg) - {"horizons", "unit", "entry_lags",
                                 "overlap_policy", "minimum_observations"})
    if unknown:
        raise ObservationError(f"unknown horizon keys: {unknown}")

    unit = cfg.get("unit", "observations")
    if unit in DEFERRED_HORIZON_UNITS:
        raise ObservationError(DEFERRED_HORIZON_UNITS[unit])
    if unit not in HORIZON_UNITS:
        raise ObservationError(
            f"horizon unit must be one of {list(HORIZON_UNITS)}")

    if supplied_outcomes:
        if cfg.get("horizons") not in (None, ["supplied"], ("supplied",)):
            raise ObservationError(
                "supplied outcomes carry their own intervals; the only "
                "horizon is 'supplied' and nothing is reconstructed")
        if cfg.get("entry_lags") not in (None, [0], (0,)):
            raise ObservationError(
                "supplied outcomes cannot be shifted: entry_lags must be [0] "
                "because the lab never reconstructs a supplied interval")
        horizons: List[Any] = ["supplied"]
        lags = [0]
    else:
        horizons = cfg.get("horizons")
        if not isinstance(horizons, list) or not horizons:
            raise ObservationError("at least one horizon is required")
        if len(horizons) > MAX_HORIZONS:
            raise ObservationError(
                f"at most {MAX_HORIZONS} horizons are supported")
        cleaned: List[int] = []
        for h in horizons:
            if isinstance(h, bool) or not isinstance(h, int) \
                    or not (1 <= h <= MAX_HORIZON_VALUE):
                raise ObservationError(
                    f"each horizon must be an integer in "
                    f"[1, {MAX_HORIZON_VALUE}] {unit}")
            cleaned.append(h)
        if len(set(cleaned)) != len(cleaned):
            raise ObservationError("duplicate horizons")
        horizons = sorted(cleaned)

        lags = cfg.get("entry_lags", [0])
        if not isinstance(lags, list) or not lags:
            raise ObservationError("entry_lags must be a non-empty list")
        if len(lags) > MAX_LAGS:
            raise ObservationError(f"at most {MAX_LAGS} entry lags are supported")
        cleaned_lags: List[int] = []
        for lag in lags:
            if isinstance(lag, bool) or not isinstance(lag, int) \
                    or not (0 <= lag <= MAX_LAG_VALUE):
                raise ObservationError(
                    f"each entry lag must be a non-negative integer "
                    f"<= {MAX_LAG_VALUE}; negative lags are rejected")
            cleaned_lags.append(lag)
        if len(set(cleaned_lags)) != len(cleaned_lags):
            raise ObservationError("duplicate entry lags")
        lags = sorted(cleaned_lags)

    policy = cfg.get("overlap_policy", "overlapping")
    if policy not in OVERLAP_POLICIES:
        raise ObservationError(
            f"overlap_policy must be one of {list(OVERLAP_POLICIES)}")

    minimum = cfg.get("minimum_observations", MIN_OBSERVATIONS)
    if isinstance(minimum, bool) or not isinstance(minimum, int) \
            or minimum < 2:
        raise ObservationError("minimum_observations must be an integer >= 2")

    return {"horizons": horizons, "unit": unit, "entry_lags": lags,
            "overlap_policy": policy, "minimum_observations": minimum,
            "interval_convention": (
                "return earned over (entry_ts, exit_ts]; overlap compared on "
                "half-open index ranges [entry_index, exit_index) so "
                "back-to-back holdings do not overlap")}


# ---------------------------------------------------------------------------
# Pair construction
# ---------------------------------------------------------------------------

def build_pairs(observations: List[Dict[str, Any]],
                *, target_type: str,
                prices: Optional[Dict[Tuple[str, str], float]],
                supplied: Optional[List[Dict[str, Any]]],
                horizon: Any, entry_lag: int,
                extreme_loss_policy: str) -> Dict[str, Any]:
    """Signal/outcome pairs for one (horizon, lag) cell.

    Every pair carries its entry/exit identity and availability stamps; a
    pair that cannot be built stays in ``unavailable`` with its reason.
    Timing violations (an outcome beginning before the signal was
    available) are collected — they mark the RUN invalid rather than being
    silently dropped.
    """
    by_entity: Dict[str, List[Dict[str, Any]]] = {}
    for row in observations:
        by_entity.setdefault(row["entity_id"], []).append(row)

    pairs: List[Dict[str, Any]] = []
    unavailable: List[Dict[str, Any]] = []
    violations: List[Dict[str, Any]] = []

    if target_type == "supplied_outcome":
        outcome_by_key = {(o["entity_id"], o["signal_timestamp"]): o
                          for o in (supplied or [])}
        for entity_id, rows in sorted(by_entity.items()):
            for index, row in enumerate(rows):
                outcome = outcome_by_key.get(
                    (entity_id, row["source_timestamp"]))
                if outcome is None or outcome["value"] is None \
                        or row["raw_value"] is None:
                    unavailable.append({
                        "entity_id": entity_id,
                        "signal_timestamp": row["source_timestamp"],
                        "kind": "data",
                        "reason": ("no supplied outcome for this observation"
                                   if outcome is None else
                                   "signal or outcome value is null"),
                    })
                    continue
                if outcome["period_start"] < row["available_at"]:
                    violations.append({
                        "entity_id": entity_id,
                        "signal_timestamp": row["source_timestamp"],
                        "outcome_start": outcome["period_start"],
                        "available_at": row["available_at"],
                    })
                pairs.append({
                    "entity_id": entity_id,
                    "observation_id": row["observation_id"],
                    "signal_timestamp": row["source_timestamp"],
                    "signal_available_at": row["available_at"],
                    "signal_value": row["raw_value"],
                    "entry_timestamp": outcome["period_start"],
                    "exit_timestamp": outcome["period_end"],
                    "entry_index": index,
                    "exit_index": index + 1,
                    "outcome_available_at": outcome["available_at"],
                    "outcome_value": outcome["value"],
                    "outcome_status": "supplied",
                })
        overlap = _overlap_from_intervals(pairs, by_stamp=True)
        return {"pairs": pairs, "unavailable": unavailable,
                "violations": violations, "overlap": overlap}

    k = int(horizon)
    lag = int(entry_lag)
    for entity_id, rows in sorted(by_entity.items()):
        grid = [r["source_timestamp"] for r in rows]
        for index, row in enumerate(rows):
            entry_index = index + lag
            exit_index = index + lag + k
            if exit_index >= len(grid) + 1 and entry_index >= len(grid):
                unavailable.append({
                    "entity_id": entity_id,
                    "signal_timestamp": row["source_timestamp"],
                    "kind": "structural",
                    "reason": f"no stored observation {lag} step(s) ahead for "
                              f"the entry",
                })
                continue
            if entry_index >= len(grid) or exit_index >= len(grid):
                unavailable.append({
                    "entity_id": entity_id,
                    "signal_timestamp": row["source_timestamp"],
                    "kind": "structural",
                    "reason": f"the grid ends before the horizon-{k} exit",
                })
                continue
            entry_ts = grid[entry_index]
            exit_ts = grid[exit_index]
            if row["raw_value"] is None:
                unavailable.append({
                    "entity_id": entity_id,
                    "signal_timestamp": row["source_timestamp"],
                    "kind": "data",
                    "reason": "signal value is null",
                })
                continue
            entry_price = (prices or {}).get((entity_id, entry_ts))
            exit_price = (prices or {}).get((entity_id, exit_ts))
            if entry_price is None or exit_price is None:
                unavailable.append({
                    "entity_id": entity_id,
                    "signal_timestamp": row["source_timestamp"],
                    "kind": "data",
                    "reason": ("missing entry price" if entry_price is None
                               else "missing exit price") +
                              " — never interpolated or back-filled",
                })
                continue
            if row["available_at"] > entry_ts:
                violations.append({
                    "entity_id": entity_id,
                    "signal_timestamp": row["source_timestamp"],
                    "outcome_start": entry_ts,
                    "available_at": row["available_at"],
                })
            value = exit_price / entry_price - 1.0
            if value <= -1.0 and extreme_loss_policy == "mark_unavailable":
                unavailable.append({
                    "entity_id": entity_id,
                    "signal_timestamp": row["source_timestamp"],
                    "reason": "return <= -100% under the declared "
                              "mark_unavailable policy",
                })
                continue
            pairs.append({
                "entity_id": entity_id,
                "observation_id": row["observation_id"],
                "signal_timestamp": row["source_timestamp"],
                "signal_available_at": row["available_at"],
                "signal_value": row["raw_value"],
                "entry_timestamp": entry_ts,
                "exit_timestamp": exit_ts,
                "entry_index": entry_index,
                "exit_index": exit_index,
                "outcome_available_at": exit_ts,
                "outcome_value": float(value),
                "outcome_status": "forward_return",
            })
    overlap = _overlap_from_intervals(pairs, by_stamp=False)
    return {"pairs": pairs, "unavailable": unavailable,
            "violations": violations, "overlap": overlap}


def _overlap_from_intervals(pairs: List[Dict[str, Any]],
                            *, by_stamp: bool) -> Dict[str, Any]:
    """Per-entity interval-overlap diagnostics, aggregated."""
    by_entity: Dict[str, List[Tuple[Any, Any]]] = {}
    for pair in pairs:
        if by_stamp:
            interval = (pair["entry_timestamp"], pair["exit_timestamp"])
        else:
            interval = (pair["entry_index"], pair["exit_index"])
        by_entity.setdefault(pair["entity_id"], []).append(interval)

    total = 0
    overlapping = 0
    max_simultaneous = 0
    for intervals in by_entity.values():
        intervals.sort()
        total += len(intervals)
        for position, (start, end) in enumerate(intervals):
            hit = False
            if position > 0:
                prev_start, prev_end = intervals[position - 1]
                if prev_start < end and start < prev_end:
                    hit = True
            if position + 1 < len(intervals):
                next_start, next_end = intervals[position + 1]
                if start < next_end and next_start < end:
                    hit = True
            if hit:
                overlapping += 1
        events: List[Tuple[Any, int]] = []
        for start, end in intervals:
            events.append((start, 1))
            events.append((end, -1))
        events.sort(key=lambda e: (e[0], e[1]))
        open_count = 0
        for _stamp, delta in events:
            open_count += delta
            max_simultaneous = max(max_simultaneous, open_count)

    ratio = (overlapping / total) if total else None
    state = "not_applicable" if total == 0 else (
        "non_overlapping" if overlapping == 0 else (
            "overlapping" if overlapping == total else
            "partially_overlapping"))
    return {
        "interval_count": total,
        "unique_source_observations": total,
        "overlapping_interval_count": overlapping,
        "overlap_ratio": ratio,
        "max_simultaneous_overlap": max_simultaneous,
        "state": state,
    }


def select_non_overlapping(pairs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deterministic non-overlap selection (documented policy).

    Per entity, in time order: keep the earliest usable pair, then keep the
    next pair whose entry index is at or after the previously kept pair's
    exit index.  No randomisation, no score-based choice.
    """
    by_entity: Dict[str, List[Dict[str, Any]]] = {}
    for pair in pairs:
        by_entity.setdefault(pair["entity_id"], []).append(pair)
    selected: List[Dict[str, Any]] = []
    for entity_id in sorted(by_entity):
        rows = sorted(by_entity[entity_id], key=lambda p: p["entry_index"])
        last_exit: Optional[int] = None
        for row in rows:
            if last_exit is None or row["entry_index"] >= last_exit:
                selected.append(row)
                last_exit = row["exit_index"]
    return selected


def effective_non_overlapping_count(n: int, horizon: Any) -> Optional[int]:
    """Documented DESCRIPTIVE approximation ceil(n / k); never an effective
    sample size for inference."""
    if not isinstance(horizon, int) or horizon <= 0 or n <= 0:
        return None
    return math.ceil(n / horizon)


# ---------------------------------------------------------------------------
# Integrity
# ---------------------------------------------------------------------------

def classify_integrity(*, definition: Dict[str, Any],
                       target_type: str,
                       entry_lags: Sequence[int],
                       violations: int,
                       validation: Optional[Dict[str, Any]],
                       warnings: List[str]) -> str:
    """Timing-based integrity; overlap is a separate, always-visible axis.

    The spec's suggested ``overlapping_descriptive`` state is represented
    here as the COMBINATION of a timing state and the run's
    ``overlap_status`` column, because collapsing the two into one label
    would hide whether the caveat is about information order or about
    interval overlap.  That decision is documented in
    SIGNAL_AND_OUTCOME_TIMING_POLICY.md.
    """
    if violations:
        warnings.append(
            f"INVALID timing: {violations} pair(s) have an outcome that "
            f"begins before the signal was available; the first offence is "
            f"recorded with its timestamps, and this run can never become a "
            f"baseline.")
        return "invalid"

    if definition["transformation"] == "rank_full_sample":
        warnings.append(
            "The signal is ranked over the FULL sample, so every rank uses "
            "future observations; results are descriptive only.")
        return "full_sample_descriptive"

    if validation is not None:
        if validation.get("leakage_clean") is False:
            warnings.append(
                "The linked model-validation run reports leakage; the "
                "verified claim is withheld and results stay descriptive.")
            return "supplied_descriptive"
        return "verified_from_validation_split"

    if target_type == "supplied_outcome":
        warnings.append(
            "Outcomes were supplied directly rather than built from stored "
            "prices, so the outcome values themselves carry supplied "
            "provenance.")
        return "supplied_descriptive"

    if definition["availability_policy"] == "explicit_available_at":
        return "verified_point_in_time"

    if all(lag >= 1 for lag in entry_lags):
        warnings.append(
            "Signal availability is ASSUMED to equal each observation's own "
            "timestamp (same_timestamp policy); the entry lag of at least one "
            "stored step is what separates signal from outcome.")
        return "verified_trailing_signal"

    warnings.append(
        "Signal availability is ASSUMED to equal each observation's own "
        "timestamp AND outcomes begin at that same stamp (lag 0); the "
        "relationship is a contemporaneous descriptive association.")
    return "supplied_descriptive"


__all__ = [
    "MIN_OBSERVATIONS", "MAX_ENTITIES", "MAX_OBSERVATIONS_TOTAL",
    "MAX_HORIZONS", "MAX_LAGS", "MAX_HORIZON_VALUE", "MAX_LAG_VALUE",
    "HORIZON_UNITS", "DEFERRED_HORIZON_UNITS", "OVERLAP_POLICIES",
    "INTEGRITY_STATES", "OVERLAP_STATES", "ObservationError",
    "normalise_timestamp", "validate_signal_observations", "validate_prices",
    "validate_supplied_outcomes", "validate_horizons", "build_pairs",
    "select_non_overlapping", "effective_non_overlapping_count",
    "classify_integrity",
]
