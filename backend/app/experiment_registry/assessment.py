"""
Conservative reproducibility assessment.

Given a *candidate* record and a *reference* record (usually its parent or the
baseline in the same scope), classify the candidate into one of four states by
comparing fingerprints, dataset identity, random seed, and provenance:

* ``reproducible`` — configuration and result fingerprints match, dataset
  fingerprint matches, and seed matches when applicable.
* ``partially_reproducible`` — configuration matches but the result differs (and
  the dataset could not be confirmed identical), or the dataset identity matches
  while its exact fingerprint is unavailable.
* ``not_reproducible`` — the configuration fingerprint differs, the dataset
  fingerprint/name differs, the required seed differs, or an identical
  configuration+dataset produced a materially different result fingerprint.
* ``unknown`` — insufficient metadata (no reference, or a missing configuration
  fingerprint).

**Honest scope:** this is repository-level *metadata validation only*.  It does
not certify scientific reproducibility, pass an audit, or validate model
correctness.  The rules are intentionally visible (returned in ``checks``) so a
reader can see exactly why a state was assigned.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

REPRODUCIBLE = "reproducible"
PARTIALLY_REPRODUCIBLE = "partially_reproducible"
NOT_REPRODUCIBLE = "not_reproducible"
UNKNOWN = "unknown"

REPRODUCIBILITY_STATUSES = frozenset(
    {REPRODUCIBLE, PARTIALLY_REPRODUCIBLE, NOT_REPRODUCIBLE, UNKNOWN}
)


def _dataset_state(candidate: Dict[str, Any], reference: Dict[str, Any]) -> str:
    dfp_c = candidate.get("dataset_fingerprint")
    dfp_r = reference.get("dataset_fingerprint")
    if dfp_c and dfp_r:
        return "match" if dfp_c == dfp_r else "mismatch"
    dname_c = candidate.get("dataset_name")
    dname_r = reference.get("dataset_name")
    if dname_c and dname_r:
        return "identity_match" if dname_c == dname_r else "mismatch"
    return "unknown"


def _seed_state(candidate: Dict[str, Any], reference: Dict[str, Any]) -> str:
    seed_c = candidate.get("random_seed")
    seed_r = reference.get("random_seed")
    if seed_c is not None and seed_r is not None:
        return "match" if seed_c == seed_r else "mismatch"
    return "unknown"


def _result_state(candidate: Dict[str, Any], reference: Dict[str, Any]) -> str:
    rfp_c = candidate.get("result_fingerprint")
    rfp_r = reference.get("result_fingerprint")
    if rfp_c and rfp_r:
        return "match" if rfp_c == rfp_r else "mismatch"
    return "unknown"


def assess_reproducibility(
    candidate: Dict[str, Any],
    reference: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return a reproducibility assessment for *candidate* vs *reference*."""
    checks: List[Dict[str, str]] = []

    if reference is None:
        return {
            "status": UNKNOWN,
            "reference_id": None,
            "summary": "No reference run to compare against.",
            "checks": checks,
        }

    reference_id = reference.get("id")
    cfg_c = candidate.get("configuration_fingerprint")
    cfg_r = reference.get("configuration_fingerprint")

    if not cfg_c or not cfg_r:
        return {
            "status": UNKNOWN,
            "reference_id": reference_id,
            "summary": "Missing configuration fingerprint on the candidate or reference.",
            "checks": checks,
        }

    config_match = cfg_c == cfg_r
    dataset = _dataset_state(candidate, reference)
    seed = _seed_state(candidate, reference)
    result = _result_state(candidate, reference)

    checks.append(
        {
            "name": "configuration_fingerprint",
            "state": "match" if config_match else "mismatch",
        }
    )
    checks.append({"name": "dataset", "state": dataset})
    checks.append({"name": "random_seed", "state": seed})
    checks.append({"name": "result_fingerprint", "state": result})

    if not config_match:
        status, summary = NOT_REPRODUCIBLE, "Configuration fingerprint differs from the reference."
    elif dataset == "mismatch":
        status, summary = NOT_REPRODUCIBLE, "Dataset identity/fingerprint differs from the reference."
    elif seed == "mismatch":
        status, summary = NOT_REPRODUCIBLE, "Random seed differs from the reference."
    elif result == "mismatch":
        if dataset == "match":
            status = NOT_REPRODUCIBLE
            summary = (
                "Identical configuration and dataset fingerprint produced a "
                "different result fingerprint."
            )
        else:
            status = PARTIALLY_REPRODUCIBLE
            summary = (
                "Configuration matches but the result fingerprint differs; the "
                "dataset fingerprint is unavailable to confirm identical inputs."
            )
    elif result == "match":
        if dataset == "match":
            status = REPRODUCIBLE
            summary = "Configuration, dataset, and result fingerprints all match the reference."
        else:
            status = PARTIALLY_REPRODUCIBLE
            summary = (
                "Configuration and result fingerprints match, but the dataset "
                "fingerprint is unavailable (identity matched by name only)."
            )
    else:  # result == "unknown"
        status = PARTIALLY_REPRODUCIBLE
        summary = (
            "Configuration matches the reference, but a result fingerprint is "
            "unavailable to confirm the outputs."
        )

    return {
        "status": status,
        "reference_id": reference_id,
        "summary": summary,
        "checks": checks,
    }


__all__ = [
    "REPRODUCIBLE",
    "PARTIALLY_REPRODUCIBLE",
    "NOT_REPRODUCIBLE",
    "UNKNOWN",
    "REPRODUCIBILITY_STATUSES",
    "assess_reproducibility",
]
