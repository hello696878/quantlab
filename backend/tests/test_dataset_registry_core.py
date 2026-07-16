"""
Pure-logic tests for the Dataset Lineage registry (Phase 49.0):
storage locators, schema/manifest fingerprints, schema drift, quality checks.
No database required.
"""

from __future__ import annotations

import pytest

locators = pytest.importorskip("app.dataset_registry.locators")
fp = pytest.importorskip("app.dataset_registry.fingerprints")
drift = pytest.importorskip("app.dataset_registry.drift")
quality = pytest.importorskip("app.dataset_registry.quality")


# ---------------------------------------------------------------------------
# Storage locators
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "locator,expected_type",
    [
        ("fixture://pairs/ko-pep/v1", "fixture"),
        ("generated://features/orderflow-5m/v1", "generated"),
        ("local-file://prices_2025.csv", "local_file"),
        ("provider://fred/CPIAUCSL", "provider"),
    ],
)
def test_valid_locators(locator, expected_type):
    lt, value = locators.validate_locator(locator)
    assert lt == expected_type
    assert value == locator


@pytest.mark.parametrize(
    "bad",
    [
        "C:\\Users\\jim\\data.csv",
        "C:/quantlab/data.csv",
        "/home/user/data.csv",
        "\\\\server\\share\\x.csv",
        "fixture://../../etc/passwd",
        "fixture://a/../b",
        "local-file://dir/name.csv",          # local-file must be basename only
        "provider://user:token@fred/series",  # credentials
        "fixture://a?b=c",                    # query string
        "fixture://a b",                      # whitespace
        "ftp://x/y",                          # unknown scheme
        "no-scheme-at-all",
        "",
        "fixture://a\x00b",                   # control character
        "fixture://C:/abs/inside",            # absolute path inside
    ],
)
def test_invalid_locators_rejected(bad):
    with pytest.raises(locators.LocatorError):
        locators.validate_locator(bad)


def test_sanitize_basename():
    assert locators.sanitize_basename("C:\\Users\\x\\prices.csv") == "prices.csv"
    assert locators.sanitize_basename("/home/x/data.csv") == "data.csv"
    assert locators.sanitize_basename("we?ird@#name.csv") == "weirdname.csv"


# ---------------------------------------------------------------------------
# Fingerprints
# ---------------------------------------------------------------------------

FIELDS = [
    {"name": "date", "type": "date", "nullable": False},
    {"name": "close", "type": "float64", "nullable": True},
]


def test_schema_fingerprint_order_independent_when_not_significant():
    a = fp.schema_fingerprint(FIELDS)
    b = fp.schema_fingerprint(list(reversed(FIELDS)))
    assert a == b


def test_schema_fingerprint_order_matters_when_significant():
    a = fp.schema_fingerprint(FIELDS, ordering_significant=True)
    b = fp.schema_fingerprint(list(reversed(FIELDS)), ordering_significant=True)
    assert a != b


def test_schema_fingerprint_normalizes_types():
    a = fp.schema_fingerprint([{"name": "x", "type": "float64", "nullable": True}])
    b = fp.schema_fingerprint([{"name": "x", "type": "double", "nullable": True}])
    assert a == b
    c = fp.schema_fingerprint([{"name": "x", "type": "string", "nullable": True}])
    assert a != c


def test_schema_fingerprint_nullable_and_version_matter():
    a = fp.schema_fingerprint([{"name": "x", "type": "float", "nullable": True}])
    b = fp.schema_fingerprint([{"name": "x", "type": "float", "nullable": False}])
    assert a != b
    v1 = fp.schema_fingerprint(FIELDS, schema_version="v1")
    v2 = fp.schema_fingerprint(FIELDS, schema_version="v2")
    assert v1 != v2


def _manifest(**over):
    kwargs = dict(
        dataset_name="ds",
        version_label="v1",
        row_count=100,
        column_count=3,
        start_time="2020-01-01T00:00:00Z",
        end_time="2021-01-01T00:00:00Z",
        fmt="csv",
        schema_fp="a" * 64,
        source_fingerprint=None,
        deterministic=True,
    )
    kwargs.update(over)
    return fp.manifest_fingerprint(**kwargs)


def test_manifest_fingerprint_deterministic_and_sensitive():
    assert _manifest() == _manifest()
    assert _manifest(row_count=101) != _manifest()
    assert _manifest(version_label="v2") != _manifest()
    assert _manifest(schema_fp="b" * 64) != _manifest()
    assert _manifest(deterministic=False) != _manifest()


def test_manifest_fingerprint_rejects_non_finite():
    with pytest.raises(fp.FingerprintError):
        _manifest(provenance_inputs={"x": float("nan")})


def test_schema_field_requires_name():
    with pytest.raises(fp.FingerprintError):
        fp.schema_fingerprint([{"name": "  ", "type": "float"}])


# ---------------------------------------------------------------------------
# Schema drift
# ---------------------------------------------------------------------------


def _snap(fields, ordering=False):
    return {"fields": fields, "ordering_significant": ordering}


BASE = [
    {"name": "date", "type": "date", "nullable": False},
    {"name": "close", "type": "float", "nullable": True},
]


def test_drift_none():
    result = drift.compare_schemas(_snap(BASE), _snap(list(BASE)))
    assert result["drift_class"] == "none"
    assert result["entries"] == []


def test_drift_added_column_is_compatible():
    b = BASE + [{"name": "volume", "type": "integer", "nullable": True}]
    result = drift.compare_schemas(_snap(BASE), _snap(b))
    assert result["drift_class"] == "compatible"
    assert any(e["kind"] == "column_added" for e in result["entries"])


def test_drift_removed_column_is_breaking():
    result = drift.compare_schemas(_snap(BASE), _snap(BASE[:1]))
    assert result["drift_class"] == "breaking"


def test_drift_coercible_type_change_potentially_breaking():
    b = [dict(BASE[0]), {"name": "close", "type": "integer", "nullable": True}]
    result = drift.compare_schemas(_snap(BASE), _snap(b))
    assert result["drift_class"] == "potentially_breaking"


def test_drift_incompatible_type_change_breaking():
    b = [dict(BASE[0]), {"name": "close", "type": "string", "nullable": True}]
    result = drift.compare_schemas(_snap(BASE), _snap(b))
    assert result["drift_class"] == "breaking"


def test_drift_nullable_tighten_vs_loosen():
    tightened = [dict(BASE[0]), {"name": "close", "type": "float", "nullable": False}]
    assert drift.compare_schemas(_snap(BASE), _snap(tightened))["drift_class"] == "potentially_breaking"
    loosened = [{"name": "date", "type": "date", "nullable": True}, dict(BASE[1])]
    assert drift.compare_schemas(_snap(BASE), _snap(loosened))["drift_class"] == "compatible"


def test_drift_ordering_only_matters_when_significant():
    swapped = list(reversed(BASE))
    quiet = drift.compare_schemas(_snap(BASE), _snap(swapped))
    assert quiet["drift_class"] == "compatible"
    loud = drift.compare_schemas(_snap(BASE, ordering=True), _snap(swapped, ordering=True))
    assert loud["drift_class"] == "potentially_breaking"


def test_drift_unknown_without_snapshot():
    assert drift.compare_schemas(None, _snap(BASE))["drift_class"] == "unknown"
    assert drift.compare_schemas(_snap([]), _snap(BASE))["drift_class"] == "unknown"


# ---------------------------------------------------------------------------
# Quality checks (pure — version dicts in, results out)
# ---------------------------------------------------------------------------


def _version(**over):
    v = {
        "row_count": 100,
        "schema_snapshot": _snap(BASE),
        "schema_fingerprint": "a" * 64,
        "start_time": "2020-01-01T00:00:00Z",
        "end_time": "2021-01-01T00:00:00Z",
        "statistics_summary": {"missing_ratio": 0.01, "duplicate_ratio": 0.0},
        "content_fingerprint": "b" * 64,
        "source_fingerprint": None,
        "provenance": {"source": "fixture", "timezone": "UTC"},
    }
    v.update(over)
    return v


def test_quality_all_pass_on_good_version():
    results = quality.run_checks(_version(), [], {})
    assert quality.rollup_status(results) == "passed"


def test_quality_zero_rows_fails():
    results = quality.run_checks(_version(row_count=0), ["row_count_nonzero"], {})
    assert results[0]["status"] == "failed"
    assert quality.rollup_status(results) == "failed"


def test_quality_missing_ratio_warning():
    results = quality.run_checks(
        _version(statistics_summary={"missing_ratio": 0.2}),
        ["missing_ratio_within_limit"],
        {},
    )
    assert results[0]["status"] == "warning"


def test_quality_required_columns():
    ok = quality.run_checks(_version(), ["required_columns_present"], {"required_columns": ["date"]})
    assert ok[0]["status"] == "passed"
    bad = quality.run_checks(_version(), ["required_columns_present"], {"required_columns": ["nope"]})
    assert bad[0]["status"] == "failed"


def test_quality_date_range_invalid():
    v = _version(start_time="2022-01-01T00:00:00Z", end_time="2021-01-01T00:00:00Z")
    results = quality.run_checks(v, ["date_range_valid"], {})
    assert results[0]["status"] == "failed"


def test_quality_non_finite_stats_fail():
    v = _version(statistics_summary={"mean": float("inf")})
    results = quality.run_checks(v, ["no_non_finite_values"], {})
    assert results[0]["status"] == "failed"


def test_quality_unknown_check_rejected():
    with pytest.raises(ValueError):
        quality.run_checks(_version(), ["not_a_real_check"], {})


def test_quality_skipped_does_not_dominate_rollup():
    results = quality.run_checks(
        _version(row_count=None), ["row_count_nonzero"], {}
    )
    assert results[0]["status"] == "skipped"
    assert quality.rollup_status(results) == "unknown"
