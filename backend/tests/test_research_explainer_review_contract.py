"""Independent display, logical-source and closed-bundle review regressions."""
import copy
import json
from decimal import Context, ROUND_DOWN, ROUND_UP, getcontext, localcontext

import pandas as pd
import pytest

from app.metrics import compute_metrics
from app.research_explainer import contract as c
from app.run_replay.identity import digest

pytestmark = [pytest.mark.db_free, pytest.mark.usefixtures("isolated_lab_db")]


def source():
    return {"saved": {
        "start_date": "2020-01-01", "end_date": "2020-01-03",
        "initial_capital": 100, "transaction_cost_bps": 7.125,
        "params": {"fast_window": 2, "slow_window": 9},
        "metrics": {"total_return": .012345, "cagr": .012345,
                    "sharpe_ratio": 1.23455, "max_drawdown": -.1,
                    "volatility": 0, "num_days": 3, "win_rate": .5},
    }}


def identity(*, context=False):
    result = {
        "source_kind": "saved_backtest", "source_schema": "saved_backtests_row_v1",
        "saved_backtest_id": 17, "created_at": "2020-02-01T00:00:00Z",
        "material_hash": "a" * 64, "trust": "legacy_unverified", "context": None,
    }
    if context:
        result["trust"] = "recorded_hashes_match"
        result["context"] = {
            "id": 23, "schema": "replay_context_v1", "result_hash": "a" * 64,
            "snapshot_hash": "b" * 64, "input_hash": "c" * 64,
            "execution_hash": "d" * 64, "config_hash_full": "e" * 64,
        }
    return result


def contextual_source():
    result = source()
    result["context"] = {"config": {"strategy_params": {"fast_window": 2, "slow_window": 9}}}
    return result


def rehash(bundle):
    bundle["fingerprint"] = digest({key: value for key, value in bundle.items() if key != "fingerprint"})
    return bundle


@pytest.mark.parametrize("precision,rounding,exponent", [
    (2, ROUND_UP, 2), (3, ROUND_DOWN, 5), (80, ROUND_DOWN, 999),
])
def test_decimal_context_cannot_change_pinned_text_or_fingerprint(precision, rounding, exponent):
    panel = source()
    panel["saved"]["metrics"]["calmar_ratio"] = 5e-324
    panel["saved"]["metrics"]["sortino_ratio"] = -5e-324
    baseline = c.verify(c.render(identity(), panel))
    with localcontext(Context(prec=precision, rounding=rounding, Emin=-exponent, Emax=exponent)):
        before = getcontext().copy()
        bundle = c.verify(c.render(identity(), copy.deepcopy(panel)))
        assert bundle == baseline
        assert getcontext().prec == before.prec
        assert getcontext().rounding == before.rounding
        assert getcontext().flags == before.flags
        assert getcontext().traps == before.traps
        assert c.display(5e-324, "decimal_return", "percent_2") == "5.000000E-322%"
        assert c.display(9007199254740991, "USD", "decimal_2") == "9,007,199,254,740,991.00 USD"
    texts = {statement["template_id"]: statement["text"] for statement in bundle["statements"]}
    assert texts["total_return"] == "The stored total return is 1.23%."
    assert texts["sharpe_ratio"] == "The stored Sharpe ratio is 1.2346."
    assert texts["cost"] == "The stored one-way transaction cost is 7.12 bps."
    assert texts["calmar_ratio"] == "The stored Calmar ratio is 5.000000E-324."
    assert texts["sortino_ratio"] == "The stored Sortino ratio is -5.000000E-324."


@pytest.mark.parametrize("field,value", [
    ("params", []), ("params", None), ("metrics", []), ("metrics", None),
])
def test_missing_object_is_not_an_empty_metric_or_parameter_dictionary(field, value):
    panel = source()
    panel["saved"][field] = value
    # Rendering missing leaves can look coherent; it must not legalize the container.
    bundle = c.render(identity(), panel)
    with pytest.raises(ValueError, match="Unapproved evidence field"):
        c.verify(bundle)


@pytest.mark.parametrize("path,value", [
    (("saved",), []), (("context",), []), (("context", "config"), []),
    (("context", "config", "strategy_params"), ["fast_window", "slow_window"]),
])
def test_rehashed_malformed_projection_containers_are_controlled_refusals(path, value):
    bundle = c.render(identity(context=True), contextual_source())
    target = bundle["evidence"]
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        c.verify(rehash(bundle))


@pytest.mark.parametrize("value", [True, "2", 2.0, 0, -1, None, [], {}])
def test_unused_context_parameter_must_still_be_a_positive_strict_integer(value):
    panel = contextual_source()
    panel["context"]["config"]["strategy_params"]["fast_window"] = value
    # The displayed fact comes from saved.params, leaving this context leaf unused.
    bundle = c.render(identity(context=True), panel)
    assert bundle["facts"][4]["source"] == "saved"
    with pytest.raises(ValueError):
        c.verify(bundle)


@pytest.mark.parametrize("key,value", [("fast_window", 3), ("slow_window", 10)])
def test_coherently_rehashed_context_cannot_disagree_with_saved_parameters(key, value):
    panel = contextual_source()
    panel["context"]["config"]["strategy_params"][key] = value
    with pytest.raises(ValueError, match="disagree"):
        c.verify(c.render(identity(context=True), panel))


def test_context_fallback_preserves_the_exact_logical_source_and_pointer():
    panel = contextual_source()
    del panel["saved"]["params"]["fast_window"]
    bundle = c.verify(c.render(identity(context=True), panel))
    facts = {fact["id"]: fact for fact in bundle["facts"]}
    assert facts["fast"] == {
        "id": "fast", "source": "context", "path": "/config/strategy_params/fast_window",
        "state": "available", "value": 2, "unit": "observations", "rule": "integer", "display": "2",
    }
    assert facts["slow"]["source"] == "saved"
    assert facts["slow"]["path"] == "/params/slow_window"
    assert bundle["identity"]["context"]["result_hash"] == bundle["identity"]["material_hash"]


@pytest.mark.parametrize("extra", [
    {"units": {"total_return": "percent"}}, {"total_return_available": False},
    {"availability": {"volatility": False}}, {"annualization": 365},
])
def test_projected_metric_metadata_cannot_silently_modify_scalar_semantics(extra):
    panel = source()
    panel["saved"]["metrics"].update(extra)
    with pytest.raises(ValueError, match="Unapproved evidence field"):
        c.verify(c.render(identity(), panel))


@pytest.mark.parametrize("path,expected", [
    ("/object/00", (True, "zero-zero")), ("/object/-1", (True, "minus-one")),
    ("/object/0", (True, "zero")), ("/array/0", (True, 7)),
    ("/array/00", (False, None)), ("/array/-1", (False, None)),
    ("/array/+0", (False, None)), ("/array/1", (False, None)),
    ("/array/999999999", (False, None)), ("/array/-", (False, None)),
    ("/", (True, "empty")), ("/~01", (True, "literal-escape")),
    ("/a~1b/~0key", (True, "escaped")), ("/scalar/child", (False, None)),
])
def test_json_pointer_object_keys_and_array_indexes_are_distinct(path, expected):
    panel = {"object": {"00": "zero-zero", "-1": "minus-one", "0": "zero"},
             "array": [7], "": "empty", "~1": "literal-escape",
             "a/b": {"~key": "escaped"}, "scalar": 8}
    assert c.lookup(panel, path) == expected
    assert c.pointer(["a/b", "~key"]) == "/a~1b/~0key"
    assert c.pointer(["~1"]) == "/~01"


@pytest.mark.parametrize("path", ["/missing/~2", "/scalar/~", "/array/1/~x", "/missing/ok/~01~3"])
def test_invalid_pointer_syntax_is_not_hidden_by_an_unresolved_ancestor(path):
    with pytest.raises(ValueError, match="Invalid field reference"):
        c.lookup({"scalar": 3, "array": [1]}, path)


@pytest.mark.parametrize("mutation", [
    "plausible_path", "fact_id", "unit", "rule", "display", "raw_type", "template_id",
    "statement_binding", "policy", "unapproved_prose", "untrusted_source_field",
])
def test_valid_outer_rehash_does_not_legalize_plausible_wrong_bindings(mutation):
    bundle = c.render(identity(), source())
    facts = {fact["id"]: fact for fact in bundle["facts"]}
    statements = {statement["template_id"]: statement for statement in bundle["statements"]}
    if mutation == "plausible_path":
        # CAGR and total return deliberately have the same raw value.
        facts["total_return"]["path"] = "/metrics/cagr"
    elif mutation == "fact_id":
        facts["total_return"]["id"] = "cagr"
    elif mutation == "unit":
        facts["total_return"]["unit"] = "ratio"
    elif mutation == "rule":
        facts["total_return"]["rule"] = "decimal_4"
    elif mutation == "display":
        facts["total_return"]["display"] = "0.01%"
    elif mutation == "raw_type":
        facts["num_days"]["value"] = 3.0
    elif mutation == "template_id":
        statements["total_return"]["template_id"] = "cagr"
    elif mutation == "statement_binding":
        statements["total_return"]["facts"] = ["cagr"]
    elif mutation == "policy":
        statements["legacy"]["text"] = c.LIMITATIONS["replay"]
    elif mutation == "unapproved_prose":
        statements["scope"]["text"] += " B\u200buy now. <script>alert('SECRET')</script>"
    elif mutation == "untrusted_source_field":
        bundle["evidence"]["saved"]["notes"] = "https://secret.invalid/BUY"
    with pytest.raises(ValueError):
        c.verify(rehash(bundle))


def test_negative_volatility_refuses_while_signed_ratios_and_zero_remain_valid():
    panel = source()
    panel["saved"]["metrics"]["sharpe_ratio"] = -1.25
    bundle = c.verify(c.render(identity(), panel))
    facts = {fact["id"]: fact for fact in bundle["facts"]}
    assert facts["volatility"]["display"] == "0.00%"
    assert facts["sharpe_ratio"]["display"] == "-1.2500"
    panel["saved"]["metrics"]["volatility"] = -.1
    with pytest.raises(ValueError, match="volatility sign"):
        c.render(identity(), panel)


def test_stored_metric_words_match_hand_computable_equity_not_trade_counts():
    # Two returns: +10%, -10%; three equity observations; one positive-return day.
    metrics = compute_metrics(pd.Series([100.0, 110.0, 99.0]), periods_per_year=2)
    assert metrics["total_return"] == -.01
    assert metrics["max_drawdown"] == -.1
    assert metrics["win_rate"] == .5
    assert metrics["num_days"] == 3
    assert metrics["volatility"] == .2
    panel = source()
    # SavedBacktest persistence serializes metrics, then acquisition decodes JSON.
    panel["saved"]["metrics"] = json.loads(json.dumps(metrics))
    bundle = c.verify(c.render(identity(), panel))
    texts = {statement["template_id"]: statement["text"] for statement in bundle["statements"]}
    assert texts["total_return"] == "The stored total return is -1.00%."
    assert texts["max_drawdown"] == "The stored maximum drawdown is -10.00%."
    assert texts["win_rate"] == "The stored fraction of positive-return days is 50.00%."
    assert texts["num_days"] == "The stored equity observation count is 3."
    assert texts["volatility"] == "The stored annualized volatility is 20.00%."
    assert texts["trades"] == "No total trade count is inferred from the stored trade list."
    assert texts["annualization"] == "This adapter does not establish the annualization convention or its suitability for crypto."


def test_number_reserialization_can_break_pinned_hash_despite_equal_parsed_values():
    panel = source()
    panel["saved"]["initial_capital"] = 100.0
    panel["saved"]["metrics"]["volatility"] = -0.0
    bundle = c.verify(c.render(identity(), panel))
    original_text = json.dumps(bundle)
    assert c.verify(json.loads(original_text)) == bundle
    # JSON.stringify after JSON.parse emits 100 for 100.0 and 0 for -0.0.
    # Apply only those two known token changes, without changing the fingerprint.
    rewritten = json.loads(original_text.replace(": 100.0", ": 100").replace(": -0.0", ": 0"))
    assert rewritten == bundle  # Ordinary value equality misses both type/sign changes.
    assert type(rewritten["evidence"]["saved"]["initial_capital"]) is int
    assert type(bundle["evidence"]["saved"]["initial_capital"]) is float
    assert digest({key: value for key, value in rewritten.items() if key != "fingerprint"}) != bundle["fingerprint"]
    with pytest.raises(ValueError, match="bindings or content changed"):
        c.verify(rewritten)
