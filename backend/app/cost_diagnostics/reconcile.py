"""
Gross-to-net reconciliation (v1).

For every observation: total cost equals the exact sum of its available,
non-overlapping components, and net equals gross minus total cost.  A missing
component is NEVER silently classified as zero — it is listed by name in
``unavailable_components``, the observation's completeness drops to
``partial`` (or ``gross_only`` when no configured component could be
computed), and the run-level counts stay visible.

Completeness states: ``complete`` (every configured component available),
``partial`` (some configured components unavailable — net excludes them and
is therefore an under-estimate of cost), ``gross_only`` (no configured
component available, or no component configured at all), ``invalid``.
"""

from __future__ import annotations

from typing import Any, Dict, List

COMPLETENESS_STATES = ("complete", "partial", "gross_only", "invalid")
COMPONENT_NAMES = ("commission", "spread", "slippage", "impact")


def reconcile_observation(gross_value: float,
                          components: Dict[str, Dict[str, Any]]
                          ) -> Dict[str, Any]:
    """Reconcile one observation.

    ``components`` maps component name -> record with ``status`` in
    (``available`` / ``unavailable`` / ``not_configured``) and ``amount``.
    ``gross_value`` is monetary PnL for trade observations and a return
    fraction for period observations; the cost amounts share that unit.
    """
    for name in COMPONENT_NAMES:
        status = components.get(name, {"status": "not_configured"}).get("status")
        if status not in ("available", "unavailable", "not_configured"):
            raise ValueError(
                f"component {name!r} has unrecognized status {status!r}")
    configured = [n for n in COMPONENT_NAMES
                  if components.get(n, {}).get("status") != "not_configured"
                  and n in components]
    available = [n for n in configured
                 if components[n]["status"] == "available"]
    unavailable = [n for n in configured
                   if components[n]["status"] == "unavailable"]
    total_cost = float(sum(components[n]["amount"] for n in available))
    if not configured or not available:
        completeness = "gross_only"
        net = None
    elif unavailable:
        completeness = "partial"
        net = gross_value - total_cost
    else:
        completeness = "complete"
        net = gross_value - total_cost
    return {
        "component_values": {
            n: (components.get(n, {}).get("amount")
                if components.get(n, {}).get("status") == "available" else None)
            for n in COMPONENT_NAMES
        },
        "component_reasons": {
            n: components[n].get("reason") for n in unavailable
        },
        "total_cost": total_cost if available else None,
        "net_value": net,
        "completeness": completeness,
        "unavailable_components": unavailable,
    }


def run_completeness(observation_states: List[str]) -> str:
    """Run-level completeness = the honest summary of observation states."""
    states = set(observation_states)
    if not states:
        return "invalid"
    if "invalid" in states:
        return "invalid"
    if states == {"complete"}:
        return "complete"
    if states == {"gross_only"}:
        return "gross_only"
    return "partial"
