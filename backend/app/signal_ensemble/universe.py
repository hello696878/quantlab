"""
Signal-universe validation (Phase 61, v1).

A signal universe is an explicit list of at least two Phase 60-style signal
definitions with their own observation rows.  Each definition is validated
by the Signal Decay contract (reused, not duplicated): declared type, unit,
frequency, direction (never inferred from a name), availability policy, tie
policy and transformation.  The universe adds:

* deterministic canonical ordering (sorted signal ids);
* a bounded signal count, entity count and total observation count;
* frequency compatibility (one shared stored frequency — nothing is
  resampled to force compatibility);
* an explicit alignment policy and missing policy.

Nothing is unit-converted, sign-flipped, transformed or imputed silently.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.signal_decay import definitions as sd_definitions
from app.signal_decay import observations as sd_observations

MIN_SIGNALS = 2
MAX_SIGNALS = 12
MAX_ENTITIES = 50
MAX_OBSERVATIONS_TOTAL = 40000

ALIGNMENT_POLICIES = ("strict_intersection", "pairwise_complete")
MISSING_POLICIES = ("unavailable",)

ORIENTATIONS = ("as_supplied", "multiply_by_negative_one")


class UniverseError(ValueError):
    """Invalid signal universe (HTTP 422)."""


def validate_universe(raw: Any) -> Dict[str, Any]:
    """Validated universe: definitions, per-signal observations, policies.

    Returns a dict with:
      ``signal_ids``     canonical (sorted) signal ids,
      ``definitions``    {signal_id: validated definition},
      ``observations``   {signal_id: validated observation rows},
      ``entities``       sorted union of entity ids,
      ``alignment_policy`` / ``missing_policy``.
    """
    if not isinstance(raw, dict):
        raise UniverseError("the signal universe must be an object")
    unknown = sorted(set(raw) - {
        "name", "description", "signals", "observations",
        "alignment_policy", "missing_policy", "metadata"})
    if unknown:
        raise UniverseError(f"unknown signal universe keys: {unknown}")

    signals = raw.get("signals")
    if not isinstance(signals, list):
        raise UniverseError("universe.signals must be a list of signal "
                            "definitions")
    if not (MIN_SIGNALS <= len(signals) <= MAX_SIGNALS):
        raise UniverseError(
            f"between {MIN_SIGNALS} and {MAX_SIGNALS} signals are required; "
            f"got {len(signals)}")

    definitions: Dict[str, Dict[str, Any]] = {}
    for item in signals:
        definition = sd_definitions.validate_signal_definition(item)
        signal_id = definition["signal_id"]
        if signal_id in definitions:
            raise UniverseError(f"duplicate signal_id {signal_id}")
        definitions[signal_id] = definition
    signal_ids = sorted(definitions)

    frequencies = sorted({d["frequency"] for d in definitions.values()})
    if len(frequencies) > 1:
        raise UniverseError(
            f"all signals must share one stored frequency; got "
            f"{frequencies} — nothing is resampled to force compatibility")

    observations_raw = raw.get("observations")
    if not isinstance(observations_raw, dict):
        raise UniverseError(
            "universe.observations must map signal_id -> observation rows")
    missing_obs = sorted(set(signal_ids) - set(observations_raw))
    if missing_obs:
        raise UniverseError(
            f"observations are missing for signal(s): {missing_obs}")
    extra_obs = sorted(set(observations_raw) - set(signal_ids))
    if extra_obs:
        raise UniverseError(
            f"observations reference unknown signal(s): {extra_obs}")

    observations: Dict[str, List[Dict[str, Any]]] = {}
    total = 0
    entities: set = set()
    for signal_id in signal_ids:
        rows = sd_observations.validate_signal_observations(
            definitions[signal_id], observations_raw[signal_id])
        observations[signal_id] = rows
        total += len(rows)
        entities.update(r["entity_id"] for r in rows)
    if total > MAX_OBSERVATIONS_TOTAL:
        raise UniverseError(
            f"at most {MAX_OBSERVATIONS_TOTAL} observations are supported "
            f"across all signals; got {total}")
    if len(entities) > MAX_ENTITIES:
        raise UniverseError(
            f"at most {MAX_ENTITIES} entities are supported across the "
            f"universe; got {len(entities)}")

    alignment_policy = raw.get("alignment_policy", "strict_intersection")
    if alignment_policy not in ALIGNMENT_POLICIES:
        raise UniverseError(
            f"alignment_policy must be one of {list(ALIGNMENT_POLICIES)}")
    missing_policy = raw.get("missing_policy", "unavailable")
    if missing_policy not in MISSING_POLICIES:
        raise UniverseError(
            f"missing_policy must be one of {list(MISSING_POLICIES)} — "
            f"missing observations are never imputed")

    name = raw.get("name") or "signal universe"
    if not isinstance(name, str) or not (1 <= len(name) <= 200):
        raise UniverseError("universe name must be 1-200 characters")
    description = raw.get("description", "")
    if not isinstance(description, str) or len(description) > 1000:
        raise UniverseError("universe description must be <= 1000 characters")

    metadata = raw.get("metadata") or {}
    if not isinstance(metadata, dict) or len(str(metadata)) > 2000:
        raise UniverseError("universe metadata must be an object of at most "
                            "2000 rendered characters")

    return {
        "name": name,
        "description": description,
        "signal_ids": signal_ids,
        "definitions": definitions,
        "observations": observations,
        "entities": sorted(entities),
        "frequency": frequencies[0],
        "alignment_policy": alignment_policy,
        "missing_policy": missing_policy,
        "metadata": metadata,
    }


def validate_orientations(raw: Any, signal_ids: List[str]) -> Dict[str, str]:
    """Explicit per-signal orientation; default ``as_supplied``.

    Orientation is a user declaration only — it is never derived from IC,
    bucket returns or any historical performance, and an inverted signal is
    never called corrected or improved.
    """
    orientations = dict(raw or {})
    unknown = sorted(set(orientations) - set(signal_ids))
    if unknown:
        raise UniverseError(f"orientation references unknown signal(s): "
                            f"{unknown}")
    out: Dict[str, str] = {}
    for signal_id in signal_ids:
        orientation = orientations.get(signal_id, "as_supplied")
        if orientation not in ORIENTATIONS:
            raise UniverseError(
                f"orientation for {signal_id} must be one of "
                f"{list(ORIENTATIONS)}")
        out[signal_id] = orientation
    return out


__all__ = [
    "MIN_SIGNALS", "MAX_SIGNALS", "MAX_ENTITIES", "MAX_OBSERVATIONS_TOTAL",
    "ALIGNMENT_POLICIES", "MISSING_POLICIES", "ORIENTATIONS",
    "UniverseError", "validate_universe", "validate_orientations",
]
