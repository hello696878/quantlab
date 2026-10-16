"""Independent expected stored facts and strict closed-template negatives."""
import copy
import json

import pytest

from app.research_explainer import contract as c
from app.run_replay.identity import digest, loads
from .conftest import sqlite_test_path

pytestmark = [pytest.mark.db_free, pytest.mark.usefixtures("isolated_lab_db")]


def material():
    return {"saved": {"start_date": "2020-01-01", "end_date": "2021-01-01", "initial_capital": 100000,
        "transaction_cost_bps": 0, "params": {"fast_window": 5, "slow_window": 20},
        "metrics": {"total_return": -.12, "cagr": 1e-12, "max_drawdown": -.25, "sharpe_ratio": 0,
                    "win_rate": .5, "num_days": 42}}}


def identity():
    return {"source_kind": "saved_backtest", "source_schema": "saved_backtests_row_v1", "saved_backtest_id": 1,
        "created_at": "2020-02-01T00:00:00Z", "material_hash": "a" * 64, "trust": "legacy_unverified", "context": None}


def test_independent_sentences_values_and_projection():
    bundle = c.verify(c.render(identity(), material()))
    texts = {s["template_id"]: s["text"] for s in bundle["statements"]}
    assert texts["total_return"] == "The stored total return is -12.00%."
    assert texts["max_drawdown"] == "The stored maximum drawdown is -25.00%."
    assert texts["capital"] == "The stored initial capital is 100,000.00 USD."
    assert texts["cost"] == "The stored one-way transaction cost is 0.00 bps."
    assert texts["num_days"] == "The stored equity observation count is 42."
    assert texts["cagr"] == "The stored CAGR is 1.000000E-10%."
    assert texts["sortino_ratio"] == "This stored record does not provide sortino_ratio (missing)."
    for fact in bundle["facts"]:
        found, raw = c.lookup(material()[fact["source"]], fact["path"])
        assert found == (fact["state"] != "missing") and raw == fact["value"]
    assert all(s["facts"] or s["policy_id"] == c.POLICY for s in bundle["statements"])
    assert c.render(identity(), material()) == bundle


@pytest.mark.parametrize("raw,unit,rule,expected", [
    (0, "ratio", "decimal_4", "0.0000"), (-1.23456, "ratio", "decimal_4", "-1.2346"),
    (1e-14, "decimal_return", "percent_2", "1.000000E-12%"),
    (-1e-14, "decimal_return", "percent_2", "-1.000000E-12%"),
    (9007199254740991, "USD", "decimal_2", "9,007,199,254,740,991.00 USD"),
])
def test_numeric_presentation(raw, unit, rule, expected):
    assert c.display(raw, unit, rule) == expected


@pytest.mark.parametrize("value", [True, False, "0", float("nan"), float("inf"), 2**53, {}, []])
def test_invalid_metric_never_zero(value):
    panel = material()
    panel["saved"]["metrics"]["total_return"] = value
    with pytest.raises((ValueError, TypeError)):
        c.render(identity(), panel)


def test_absent_null_zero_distinct():
    panel = material()
    panel["saved"]["metrics"]["sortino_ratio"] = None
    facts = {f["id"]: f for f in c.verify(c.render(identity(), panel))["facts"]}
    assert facts["sortino_ratio"]["state"] == "null"
    assert facts["volatility"]["state"] == "missing"
    assert facts["sharpe_ratio"]["value"] == 0 and facts["sharpe_ratio"]["state"] == "available"


@pytest.mark.parametrize("path,found,value", [("/a~1b/~0key/0", True, 7), ("/a~1b/~0key/1", False, None),
    ("/missing", False, None), ("/a~1b/~0key/-1", False, None), ("/a~1b/~0key/00", False, None)])
def test_pointer_escape_and_bounds(path, found, value):
    assert c.pointer(["a/b", "~key", 0]) == "/a~1b/~0key/0"
    assert c.lookup({"a/b": {"~key": [7]}}, path) == (found, value)


@pytest.mark.parametrize("path", ["x", "/x~", "/x~2"])
def test_malformed_pointer(path):
    with pytest.raises(ValueError):
        c.lookup({}, path)


@pytest.mark.parametrize("mutation", ["text", "fact", "binding", "hash", "extra", "policy", "version"])
def test_rehashed_bundle_tampering_refused(mutation):
    bundle = c.render(identity(), material())
    if mutation == "text": bundle["statements"][0]["text"] = "Buy now for good alpha."
    if mutation == "fact": bundle["facts"][0]["value"] = "2025-01-01"
    if mutation == "binding": bundle["facts"][0]["path"] = "/notes"
    if mutation == "hash": bundle["fingerprint"] = "b" * 64
    if mutation == "extra": bundle["evidence"]["saved"]["notes"] = "SECRET"
    if mutation == "policy": bundle["statements"][-1]["policy_id"] = "attested"
    if mutation == "version": bundle["template_version"] = "source-provided"
    if mutation != "hash": bundle["fingerprint"] = digest({k: v for k, v in bundle.items() if k != "fingerprint"})
    with pytest.raises(ValueError): c.verify(bundle)


@pytest.mark.parametrize("text", ["Buy now", "Sell it", "Recommended", "A good strategy", "bad returns", "robust alpha", "will outperform", "skill", "guaranteed"])
def test_banned_claims(text):
    with pytest.raises(ValueError): c.claim_check(text)


def test_code_owned_templates_and_negative_caveats():
    for value in c.LIMITATIONS.values(): c.claim_check(value)
    for _, _, _, prefix in c.FIELDS.values(): c.claim_check(prefix)
    assert "not investment advice" in c.LIMITATIONS["scope"]


@pytest.mark.parametrize("raw", ['{"a":1,"a":2}', '{"x":NaN}', '['*25+'0'+']'*25, '"'+'x'*100+'"'])
def test_bounded_json(raw):
    with pytest.raises(ValueError): loads(raw, limit=50)


def test_guard_read_only_uri_and_no_other_modes(tmp_path):
    target = tmp_path / "test.db"
    assert sqlite_test_path(target.as_uri() + "?mode=ro") == target
    for query in ("mode=rw", "mode=ro&cache=shared", "mode=ro&mode=ro", "mode=memory"):
        with pytest.raises(ValueError): sqlite_test_path(target.as_uri() + "?" + query)
