"""Independent arithmetic and adversarial input checks for the Phase 64 review."""

from copy import deepcopy
import math

import numpy as np
import pytest
from pydantic import ValidationError
from scipy import stats

from app.overfitting_diagnostics.multiple_testing import (
    MultipleTestingError, adjust_p_values,
)
from app.strategy_ensemble import core, demo, service
from app.strategy_ensemble.models import RunCreate, WeightPolicy, timestamp


pytestmark = [pytest.mark.db_free, pytest.mark.usefixtures("isolated_lab_db")]


def analyze(payload):
    return core.analyze(RunCreate.model_validate(payload))


@pytest.mark.parametrize("strategy_count", [9, 12])
def test_entire_supported_pairwise_family_gets_one_holm_correction(strategy_count):
    payload = demo.payload(values={
        f"s{i:02d}": [((i + 2) * (j + 3) % 17 - 8) / 100 for j in range(12)]
        for i in range(strategy_count)
    })
    result = analyze(payload)
    adjusted = result["multiple_testing"]["results"]
    assert len(adjusted) == strategy_count * (strategy_count - 1)
    raw_by_id = {
        f"{pair['strategy_a']}:{pair['strategy_b']}:{method}": metrics["p_value"]
        for pair in result["pairwise"]
        for method, metrics in pair["correlations"].items()
    }
    ordered = sorted(value for value in raw_by_id.values() if value is not None)
    assert len(ordered) == len(adjusted)
    for row in adjusted:
        raw = raw_by_id[row["candidate_id"]]
        expected = min(1.0, max((len(ordered) - i) * p
                                for i, p in enumerate(ordered) if p <= raw))
        assert row["raw_p_value"] == raw
        assert row["holm"] == pytest.approx(expected)


def test_unavailable_tests_do_not_enlarge_holm_family_and_default_cap_remains():
    payload = demo.payload(values={
        "a": [.1, .2, -.1, .05, -.03],
        "b": [.02, -.1, .04, .06, .01],
        **{f"z{i}": [0.] * 5 for i in range(10)},
    })
    result = analyze(payload)
    rows = result["multiple_testing"]["results"]
    assert len(rows) == 132
    available = sorted((row for row in rows if row["raw_p_value"] is not None),
                       key=lambda row: row["raw_p_value"])
    assert len(available) == 2
    expected_first = min(1., 2 * available[0]["raw_p_value"])
    assert [row["holm"] for row in available] == pytest.approx(
        [expected_first, max(expected_first, available[1]["raw_p_value"])])
    assert all(row["holm"] is None for row in rows if row["raw_p_value"] is None)
    entries = [{"candidate_id": str(i), "raw_p": .1} for i in range(65)]
    with pytest.raises(MultipleTestingError, match="at most 64"):
        adjust_p_values(entries, .05)


@pytest.mark.parametrize("normalization", ["normalize_by_sum", "normalize_by_gross"])
def test_small_positive_weights_normalize_without_using_statistical_tolerance(normalization):
    policy = WeightPolicy(mode="user_static", weights={"a": 1e-12, "b": 3e-12},
                          normalization=normalization)
    result = core.weight_details(policy, ["a", "b"], 1e-8)
    assert result["original"] == {"a": 1e-12, "b": 3e-12}
    assert result["effective"] == pytest.approx({"a": .25, "b": .75})
    zero = policy.model_copy(update={"weights": {"a": 0., "b": 0.}})
    with pytest.raises(ValueError, match="positive total"):
        core.weight_details(zero, ["a", "b"], 1e-8)


def test_opposite_sign_count_does_not_multiply_tiny_returns():
    result = analyze(demo.payload(values={
        "a": [1e-200, -1e-200, 2e-200, -2e-200, 0.],
        "b": [-1e-200, 1e-200, -2e-200, 2e-200, 0.],
    }))["pairwise"][0]
    assert result["opposite_sign_count"] == 4
    assert result["sign_agreement"] == pytest.approx(1 / 5)
    assert result["simultaneous_loss_count"] == 0
    assert result["simultaneous_gain_count"] == 0


@pytest.mark.parametrize("value", ["0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-01:00"])
def test_utc_timestamp_range_failure_is_a_validation_error(value):
    payload = demo.payload()
    payload["weights_available_at"] = value
    with pytest.raises(ValidationError, match="supported UTC datetime range"):
        RunCreate.model_validate(payload)


@pytest.mark.parametrize("container,field", [
    ("observation", "return_value"), ("observation", "cost_return"),
    ("observation", "turnover"), ("observation", "gross_exposure"),
    ("observation", "net_exposure"), ("observation", "strategy_id"),
    ("observation", "source_observation_id"), ("definition", "strategy_id"),
    ("definition", "source_run_id"), ("definition", "dataset_version_id"),
    ("definition", "configuration_fingerprint"), ("policy", "weights"),
])
def test_boolean_values_cannot_be_numeric_or_strategy_identities(container, field):
    payload = demo.payload()
    if container == "policy":
        payload["policy"] = {"mode": "user_static", "weights": {"a": True, "b": 0.}}
    else:
        key = "observations" if container == "observation" else "definitions"
        payload[key][0][field] = True
    with pytest.raises(ValidationError):
        RunCreate.model_validate(payload)


def test_intraday_offsets_order_and_future_extension_preserve_causal_prefix():
    payload = demo.payload(values={
        "b": [-.04, .12, -.03, .02, -.1, .3],
        "a": [.1, -.08, .02, -.06, .4, -.2],
    })
    payload["policy"] = {"mode": "user_static", "weights": {"a": .3, "b": .7}}
    prefix = deepcopy(payload)
    cutoff = timestamp("2024-01-05")
    prefix["observations"] = [row for row in prefix["observations"]
                              if timestamp(row["period_end"]) <= cutoff]
    earlier = analyze(prefix)
    later = analyze(payload)
    assert earlier["ensemble"]["weights"] == later["ensemble"]["weights"]
    assert earlier["ensemble"]["periods"] == later["ensemble"]["periods"][:4]
    assert earlier["ensemble"]["drawdown"]["periods"] == later["ensemble"]["drawdown"]["periods"][:4]
    for strategy_id in ("a", "b"):
        assert earlier["strategy_drawdowns"][strategy_id]["periods"] == later["strategy_drawdowns"][strategy_id]["periods"][:4]
    # A later full-sample correlation is deliberately allowed to change.
    assert earlier["pairwise"][0]["correlations"]["pearson"]["value"] != later["pairwise"][0]["correlations"]["pearson"]["value"]
    payload["definitions"].reverse()
    payload["observations"].reverse()
    assert analyze(payload) == later
    assert timestamp("2024-01-01T08:00:00.123456+08:00") == "2024-01-01T00:00:00.123456Z"
    assert timestamp("2024-01-01T00:00:00.123456") == "2024-01-01T00:00:00.123456Z"


def test_fixed_period_return_weights_differ_from_unrebalanced_sleeves():
    result = analyze(demo.payload(values={"a": [.1, -.1], "b": [0., 0.]}))["ensemble"]
    assert [row["ensemble_return"] for row in result["periods"]] == pytest.approx([.05, -.05])
    assert result["drawdown"]["periods"][-1]["wealth"] == pytest.approx(1.05 * .95)
    buy_and_hold_sleeves = .5 * 1.1 * .9 + .5
    assert buy_and_hold_sleeves == pytest.approx(.995)
    assert result["drawdown"]["periods"][-1]["wealth"] != pytest.approx(buy_and_hold_sleeves)
    assert result["turnover"]["subsequent_target_weight_change"] == 0
    assert result["turnover"]["executed_rebalance_turnover"] is None
    assert all(row["share"] is None for row in result["contribution_summary"])
    assert result["arithmetic_sum"] == 0
    assert result["drawdown"]["compounded_return"] == pytest.approx(-.0025)


def test_contributions_signed_shares_and_zero_weights_have_independent_reference():
    payload = demo.payload(values={"c": [.5, -.5], "b": [-.05, -.05], "a": [.1, .1]})
    payload["policy"] = {"mode": "user_static", "weights": {"c": 0., "b": .5, "a": .5}}
    result = analyze(payload)["ensemble"]
    for row in result["periods"]:
        assert row["contributions"] == {"a": .05, "b": -.025, "c": 0.}
        assert sum(row["contributions"].values()) == pytest.approx(.025)
        assert row["ensemble_return"] == pytest.approx(.025)
    summaries = {row["strategy_id"]: row for row in result["contribution_summary"]}
    assert [summaries[s]["share"] for s in ("a", "b", "c")] == pytest.approx([2., -1., 0.])
    assert [summaries[s]["absolute_share"] for s in ("a", "b", "c")] == pytest.approx([2/3, 1/3, 0.])
    assert summaries["a"]["positive_periods"] == summaries["b"]["negative_periods"] == 2
    assert summaries["c"]["positive_periods"] == summaries["c"]["negative_periods"] == 0
    assert result["absolute_contribution_concentration"] == pytest.approx(5 / 9)
    assert result["drawdown"]["compounded_return"] == pytest.approx(1.025 ** 2 - 1)


@pytest.mark.parametrize("returns,message", [
    ([100.] * 200, "overflow/underflow"), ([-.99] * 200, "overflow/underflow"),
    ([-1.], "-100%"), ([-1.1], "-100%"),
])
def test_compounding_rejects_nonrepresentable_wealth_and_total_loss(returns, message):
    with pytest.raises(ValueError, match=message):
        core.drawdowns([(str(i), str(i + 1)) for i in range(len(returns))], returns)


def test_equal_peak_recovery_and_ongoing_episode_boundaries():
    keys = [(str(i), str(i + 1)) for i in range(5)]
    result = core.drawdowns(keys, [-.5, 1., 0., -.25, 0.])
    assert [row["wealth"] for row in result["periods"]] == [.5, 1., 1., .75, .75]
    assert [row["drawdown"] for row in result["periods"]] == [-.5, 0., 0., -.25, -.25]
    first, ongoing = result["episodes"]
    assert (first["start"], first["trough"], first["recovery"], first["duration_periods"]) == ("0", "1", "2", 2)
    assert (ongoing["start"], ongoing["trough"], ongoing["recovery"], ongoing["duration_periods"]) == ("3", "4", None, 2)


def test_pair_drawdown_samples_full_history_without_recomputing_common_path():
    payload = demo.payload(values={"a": [-.5, .1, .1, .1], "b": [-.5, .1, .1, .1], "c": [0.] * 4})
    payload["observations"] = [row for row in payload["observations"]
                               if row["strategy_id"] != "c" or row["source_observation_id"] != "p000"]
    payload["analysis"] = {"minimum_samples": 3}
    result = analyze(payload)
    pair = next(row for row in result["pairwise"] if (row["strategy_a"], row["strategy_b"]) == ("a", "b"))
    assert pair["n"] == pair["drawdown_overlap"]["simultaneous_periods"] == 3
    assert pair["drawdown_overlap"]["deepest_episode_overlap"] == 3
    assert all(row["drawdown"] == 0 for row in result["ensemble"]["drawdown"]["periods"])


def test_pair_statistics_and_tied_spearman_against_independent_references():
    x, y = [.1, .1, -.2, .3, 0.], [.2, -.1, -.1, .4, 0.]
    pair = analyze(demo.payload(values={"a": x, "b": y}))["pairwise"][0]
    mean_x, mean_y = sum(x) / 5, sum(y) / 5
    cross = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
    denominator = math.sqrt(sum((a - mean_x) ** 2 for a in x) * sum((b - mean_y) ** 2 for b in y))
    assert pair["covariance"] == pytest.approx(cross / 4)
    assert pair["correlations"]["pearson"]["value"] == pytest.approx(cross / denominator)
    # Average ranks are enumerated from the inputs, independently of the app helper.
    ranks_x, ranks_y = [3.5, 3.5, 1., 5., 2.], [4., 1.5, 1.5, 5., 3.]
    rank_cross = sum((a - 3) * (b - 3) for a, b in zip(ranks_x, ranks_y))
    rank_denominator = math.sqrt(sum((a - 3) ** 2 for a in ranks_x) * sum((b - 3) ** 2 for b in ranks_y))
    assert pair["correlations"]["spearman"]["value"] == pytest.approx(rank_cross / rank_denominator)
    assert pair["correlations"]["pearson"]["p_value"] == pytest.approx(stats.pearsonr(x, y).pvalue)
    assert pair["correlations"]["spearman"]["p_value"] == pytest.approx(stats.spearmanr(x, y).pvalue)
    assert pair["sign_agreement"] == pytest.approx(4 / 5)
    assert pair["simultaneous_loss_count"] == 1
    assert pair["simultaneous_gain_count"] == 2
    assert pair["opposite_sign_count"] == 1


def test_inclusive_tail_ties_joint_union_conditionals_and_opposite_direction():
    x = [-.1, -.1, -.1, 0., .01, .02, .03, .04, .05, .06]
    y = [-.2, .06, -.2, -.2, .01, .02, .03, .04, .05, 0.]
    payload = demo.payload(values={"a": x, "b": y})
    payload["analysis"] = {"tail_quantile": .2, "tail_minimum_samples": 10}
    tail = analyze(payload)["pairwise"][0]["empirical_lower_tail_overlap"]
    assert tail["threshold_a"] == -.1
    assert tail["threshold_b"] == -.2
    assert tail["joint_count"] == 2
    assert tail["jaccard"] == .5
    assert tail["b_given_a"] == tail["a_given_b"] == pytest.approx(2 / 3)
    assert tail["opposite_tail_rate"] == .1


def test_matrix_spectrum_concentration_and_sample_are_independent_of_pairwise_missingness():
    payload = demo.payload(values={
        "a": [-.1, 0., .1, 0., .2],
        "b": [-.05, math.sqrt(3) * .05, .05, -math.sqrt(3) * .05, -.2],
    })
    payload["observations"] = [row for row in payload["observations"]
                               if row["strategy_id"] != "b" or row["source_observation_id"] != "p004"]
    payload["analysis"] = {"pairwise_alignment": "pairwise_complete"}
    matrix = analyze(payload)["matrix"]
    assert matrix["strategy_ids"] == ["a", "b"]
    assert matrix["sample"] == "strict_intersection" and matrix["n"] == 4
    assert np.asarray(matrix["values"]) == pytest.approx(np.array([[1., .5], [.5, 1.]]))
    assert matrix["eigenvalues"] == pytest.approx([.5, 1.5])
    assert matrix["rank"] == 2 and matrix["condition"] == pytest.approx(3)
    assert matrix["effective_strategy_count"] == pytest.approx(4 / 2.5)


def test_cost_counts_use_common_periods_and_zero_weight_unknown_basis_is_inactive():
    payload = demo.payload(values={"a": [.1, .2, .3, .4], "b": [.1, .2, .3, .4], "c": [0.] * 4}, basis="net_of_strategy_costs")
    payload["policy"] = {"mode": "user_static", "weights": {"a": .5, "b": .5, "c": 0.}, "initial_build": "zero_prior_weights"}
    for definition in payload["definitions"]:
        if definition["strategy_id"] == "c":
            definition["gross_or_net"] = "unknown"
    for row in payload["observations"]:
        row.update(cost_return=.01, turnover=.2)
        if row["strategy_id"] == "c":
            row["gross_or_net"] = "unknown"
        if row["strategy_id"] == "b" and row["source_observation_id"] == "p002":
            row["cost_return"] = None
    payload["observations"] = [row for row in payload["observations"]
                               if row["strategy_id"] != "c" or row["source_observation_id"] != "p000"]
    result = analyze(payload)["ensemble"]
    assert result["n"] == 3
    underlying = {row["strategy_id"]: row for row in result["turnover"]["underlying"]}
    assert underlying["a"]["cost_observations"] == 3
    assert underlying["a"]["cost_return_sum"] == pytest.approx(.03)
    assert underlying["b"]["cost_observations"] == 2
    assert underlying["b"]["cost_return_sum"] is None
    assert underlying["b"]["turnover_sum"] == pytest.approx(.6)
    assert result["costs"]["basis"] == "net_of_strategy_costs"
    assert result["costs"]["fully_net_ensemble"] is None
    assert result["costs"]["underlying_cost_deducted_again"] is False
    assert [row["ensemble_return"] for row in result["periods"]] == [.2, .3, .4]
    assert result["turnover"]["initial_allocation"] == .5


def test_sensitivity_deduplication_is_neutral_and_uses_identical_common_periods():
    payload = demo.payload(values={"a": [.1, -.1, .2, -.2], "b": [.01, .02, -.01, -.02]})
    payload["scenarios"] = [
        {"label": "duplicate", "policy": {"mode": "user_static", "weights": {"a": 2., "b": 2.}, "normalization": "normalize_by_gross"}},
        {"label": "Explicit weights", "policy": {"mode": "user_static", "weights": {"a": .75, "b": .25}}},
    ]
    result = analyze(payload)
    assert [row["label"] for row in result["sensitivity"]] == ["Base", "Explicit weights"]
    assert [row["is_base"] for row in result["sensitivity"]] == [True, False]
    assert all(row["n"] == result["ensemble"]["n"] for row in result["sensitivity"])
    expected = math.prod(1 + .75 * a + .25 * b for a, b in zip([.1, -.1, .2, -.2], [.01, .02, -.01, -.02])) - 1
    assert result["sensitivity"][1]["compounded_return"] == pytest.approx(expected)
    assert "winner" not in result and "selected_scenario" not in result


def test_material_timestamps_and_observations_change_semantic_hashes():
    payload = demo.payload()
    request = RunCreate.model_validate(payload)
    pinned = {"datasets": {d.strategy_id: {"state": "unlinked", "declared_identity": d.dataset_identity}
                           for d in request.definitions}, "regime": None, "validation": None}
    original = service.fingerprints(request, pinned)
    for field in ("information_available_at", "period_start", "period_end"):
        changed = deepcopy(payload)
        target = changed["observations"][0]
        target[field] = ("2024-01-01T00:00:00.000001" if field == "period_start"
                         else "2024-01-01T23:59:59.999999" if field == "period_end"
                         else "2024-01-02T00:00:00.000001")
        assert service.fingerprints(RunCreate.model_validate(changed), pinned)["configuration"] != original["configuration"]
