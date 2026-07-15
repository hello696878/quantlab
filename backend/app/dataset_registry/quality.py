"""
Metadata-driven quality checks.

Checks validate the **declared structural properties** a version recorded
(row counts, schema snapshot, timestamps, statistics summary) — they never
open files, never fetch data, and never prove a dataset is financially or
scientifically correct.  Passing checks means "the recorded metadata is
internally consistent with the declared expectations", nothing more.

Each check returns a result dict; the caller persists it and rolls the
version's overall ``quality_status`` up as worst-of (failed > warning >
passed > skipped/unknown).
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

CHECKER_VERSION = "quality_checks_v1"

Status = str  # passed | warning | failed | skipped | unknown


def _result(
    name: str,
    category: str,
    status: Status,
    severity: str,
    *,
    observed: Any = None,
    expected: Any = None,
    message: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "check_name": name,
        "check_category": category,
        "status": status,
        "severity": severity,
        "observed_value": None if observed is None else str(observed),
        "expected_value": None if expected is None else str(expected),
        "message": message,
        "checker_version": CHECKER_VERSION,
        "details": details or {},
    }


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


# --- individual checks ------------------------------------------------------
# Signature: (version, expectations) -> result dict


def check_row_count_nonzero(version: Dict[str, Any], _: Dict[str, Any]) -> Dict[str, Any]:
    rc = version.get("row_count")
    if rc is None:
        return _result("row_count_nonzero", "structural", "skipped", "info",
                       message="row_count not recorded")
    if rc > 0:
        return _result("row_count_nonzero", "structural", "passed", "info", observed=rc)
    return _result("row_count_nonzero", "structural", "failed", "high",
                   observed=rc, expected="> 0", message="declared row_count is zero")


def check_required_columns_present(version: Dict[str, Any], exp: Dict[str, Any]) -> Dict[str, Any]:
    required = exp.get("required_columns") or []
    fields = {f.get("name") for f in (version.get("schema_snapshot") or {}).get("fields", [])}
    if not required:
        return _result("required_columns_present", "schema", "skipped", "info",
                       message="no required_columns expectation supplied")
    if not fields:
        return _result("required_columns_present", "schema", "unknown", "medium",
                       message="no schema snapshot recorded")
    missing = [c for c in required if c not in fields]
    if missing:
        return _result("required_columns_present", "schema", "failed", "high",
                       observed=sorted(fields), expected=required,
                       message=f"missing required columns: {missing}")
    return _result("required_columns_present", "schema", "passed", "info", expected=required)


def check_schema_matches_expected(version: Dict[str, Any], exp: Dict[str, Any]) -> Dict[str, Any]:
    expected_fp = exp.get("expected_schema_fingerprint")
    actual = version.get("schema_fingerprint")
    if not expected_fp:
        return _result("schema_matches_expected", "schema", "skipped", "info",
                       message="no expected_schema_fingerprint supplied")
    if not actual:
        return _result("schema_matches_expected", "schema", "unknown", "medium",
                       message="version has no schema fingerprint")
    if actual == expected_fp:
        return _result("schema_matches_expected", "schema", "passed", "info", observed=actual[:12])
    return _result("schema_matches_expected", "schema", "failed", "high",
                   observed=actual[:12], expected=str(expected_fp)[:12],
                   message="schema fingerprint differs from the declared expectation")


def check_timestamps_parseable(version: Dict[str, Any], _: Dict[str, Any]) -> Dict[str, Any]:
    raws = {k: version.get(k) for k in ("start_time", "end_time")}
    present = {k: v for k, v in raws.items() if v}
    if not present:
        return _result("timestamps_parseable", "temporal", "skipped", "info",
                       message="no start/end timestamps recorded")
    bad = [k for k, v in present.items() if _parse_ts(v) is None]
    if bad:
        return _result("timestamps_parseable", "temporal", "failed", "medium",
                       observed=bad, message=f"unparseable ISO timestamps: {bad}")
    return _result("timestamps_parseable", "temporal", "passed", "info")


def check_date_range_valid(version: Dict[str, Any], _: Dict[str, Any]) -> Dict[str, Any]:
    start = _parse_ts(version.get("start_time"))
    end = _parse_ts(version.get("end_time"))
    if start is None or end is None:
        return _result("date_range_valid", "temporal", "skipped", "info",
                       message="date range not fully recorded")
    if start <= end:
        return _result("date_range_valid", "temporal", "passed", "info",
                       observed=f"{start.date()} → {end.date()}")
    return _result("date_range_valid", "temporal", "failed", "high",
                   observed=f"{start} > {end}", message="start_time is after end_time")


def check_timezone_known(version: Dict[str, Any], exp: Dict[str, Any]) -> Dict[str, Any]:
    tz = exp.get("timezone") or version.get("provenance", {}).get("timezone")
    if tz:
        return _result("timezone_known", "temporal", "passed", "info", observed=tz)
    return _result("timezone_known", "temporal", "warning", "low",
                   message="no timezone declared for this version")


def check_no_non_finite_values(version: Dict[str, Any], _: Dict[str, Any]) -> Dict[str, Any]:
    stats = version.get("statistics_summary") or {}

    def scan(obj: Any, path: str = "") -> Optional[str]:
        if isinstance(obj, float) and not math.isfinite(obj):
            return path or "<root>"
        if isinstance(obj, dict):
            for k, v in obj.items():
                hit = scan(v, f"{path}.{k}" if path else str(k))
                if hit:
                    return hit
        if isinstance(obj, list):
            for i, v in enumerate(obj):
                hit = scan(v, f"{path}[{i}]")
                if hit:
                    return hit
        return None

    hit = scan(stats)
    if hit:
        return _result("no_non_finite_values", "statistical", "failed", "high",
                       observed=hit, message=f"non-finite value in statistics at {hit}")
    if not stats:
        return _result("no_non_finite_values", "statistical", "skipped", "info",
                       message="no statistics summary recorded")
    return _result("no_non_finite_values", "statistical", "passed", "info")


def check_missing_ratio_within_limit(version: Dict[str, Any], exp: Dict[str, Any]) -> Dict[str, Any]:
    ratio = (version.get("statistics_summary") or {}).get("missing_ratio")
    limit = exp.get("max_missing_ratio", 0.05)
    if ratio is None:
        return _result("missing_ratio_within_limit", "statistical", "skipped", "info",
                       message="missing_ratio not recorded in statistics")
    if not isinstance(ratio, (int, float)) or not math.isfinite(float(ratio)):
        return _result("missing_ratio_within_limit", "statistical", "failed", "medium",
                       observed=ratio, message="missing_ratio is not a finite number")
    if float(ratio) <= float(limit):
        return _result("missing_ratio_within_limit", "statistical", "passed", "info",
                       observed=ratio, expected=f"<= {limit}")
    return _result("missing_ratio_within_limit", "statistical", "warning", "medium",
                   observed=ratio, expected=f"<= {limit}",
                   message="declared missing-value ratio exceeds the limit")


def check_duplicate_ratio_within_limit(version: Dict[str, Any], exp: Dict[str, Any]) -> Dict[str, Any]:
    ratio = (version.get("statistics_summary") or {}).get("duplicate_ratio")
    limit = exp.get("max_duplicate_ratio", 0.01)
    if ratio is None:
        return _result("duplicate_ratio_within_limit", "statistical", "skipped", "info",
                       message="duplicate_ratio not recorded in statistics")
    if not isinstance(ratio, (int, float)) or not math.isfinite(float(ratio)):
        return _result("duplicate_ratio_within_limit", "statistical", "failed", "medium",
                       observed=ratio, message="duplicate_ratio is not a finite number")
    if float(ratio) <= float(limit):
        return _result("duplicate_ratio_within_limit", "statistical", "passed", "info",
                       observed=ratio, expected=f"<= {limit}")
    return _result("duplicate_ratio_within_limit", "statistical", "warning", "medium",
                   observed=ratio, expected=f"<= {limit}",
                   message="declared duplicate ratio exceeds the limit")


def check_content_fingerprint_present(version: Dict[str, Any], _: Dict[str, Any]) -> Dict[str, Any]:
    if version.get("content_fingerprint"):
        return _result("content_fingerprint_present", "provenance", "passed", "info")
    return _result("content_fingerprint_present", "provenance", "warning", "low",
                   message="no content fingerprint recorded (identity is metadata-only)")


def check_source_identity_present(version: Dict[str, Any], _: Dict[str, Any]) -> Dict[str, Any]:
    prov = version.get("provenance") or {}
    if version.get("source_fingerprint") or prov.get("source"):
        return _result("source_identity_present", "provenance", "passed", "info")
    return _result("source_identity_present", "provenance", "warning", "low",
                   message="no source fingerprint or provenance source recorded")


BUILT_IN_CHECKS: Dict[str, Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]] = {
    "row_count_nonzero": check_row_count_nonzero,
    "required_columns_present": check_required_columns_present,
    "schema_matches_expected": check_schema_matches_expected,
    "timestamps_parseable": check_timestamps_parseable,
    "date_range_valid": check_date_range_valid,
    "timezone_known": check_timezone_known,
    "no_non_finite_values": check_no_non_finite_values,
    "missing_ratio_within_limit": check_missing_ratio_within_limit,
    "duplicate_ratio_within_limit": check_duplicate_ratio_within_limit,
    "content_fingerprint_present": check_content_fingerprint_present,
    "source_identity_present": check_source_identity_present,
}

# Rollup order: worst wins.
_ROLLUP_RANK = {"failed": 4, "warning": 3, "passed": 2, "unknown": 1, "skipped": 0}


def run_checks(
    version: Dict[str, Any],
    check_names: List[str],
    expectations: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Run the named built-in checks (all of them when the list is empty)."""
    names = check_names or list(BUILT_IN_CHECKS)
    results: List[Dict[str, Any]] = []
    for name in names:
        fn = BUILT_IN_CHECKS.get(name)
        if fn is None:
            raise ValueError(
                f"unknown quality check {name!r}; available: {sorted(BUILT_IN_CHECKS)}"
            )
        results.append(fn(version, expectations))
    return results


def rollup_status(results: List[Dict[str, Any]]) -> str:
    """Worst-of rollup for the version's quality_status."""
    if not results:
        return "unknown"
    worst = max(results, key=lambda r: _ROLLUP_RANK.get(r["status"], 0))
    status = worst["status"]
    return status if status in ("failed", "warning", "passed") else "unknown"


__all__ = ["BUILT_IN_CHECKS", "CHECKER_VERSION", "run_checks", "rollup_status"]
