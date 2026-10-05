"""Independent Phase 66 identity/environment checks; no database or engine work."""

import copy
import hashlib
import json
from types import SimpleNamespace

import pytest

from app.reproducibility import canonical_json, compute_config_hash
from app.run_replay import adapter, environment, identity

pytestmark = [pytest.mark.db_free, pytest.mark.usefixtures("isolated_lab_db")]


def manifest(classification="execution", **fields):
    return {"schema_version": "environment_manifest_v1", "classification": classification,
            "collection": "backend_local_allowlist",
            "fields": {**dict.fromkeys(environment.FIELDS), **fields}}


@pytest.mark.parametrize("value", [10**400, -(10**400), 2**53, -(2**53)])
def test_oversized_integer_is_a_controlled_validation_error(value):
    with pytest.raises(ValueError, match="safely representable"):
        identity.validate({"integer": value})
    with pytest.raises(ValueError, match="safely representable"):
        identity.loads('{"integer":' + str(value) + '}')


@pytest.mark.parametrize("value", [None, True, 1, {}, []])
def test_json_reader_refuses_non_text_without_attribute_errors(value):
    with pytest.raises(ValueError, match="text or bytes"):
        identity.loads(value)


@pytest.mark.parametrize("value", [None, True, 1, [], "text", {"schema_version": 1}])
def test_legacy_canonical_payload_requires_an_object_and_schema_namespace(value):
    encoded = json.dumps(value, separators=(",", ":"), sort_keys=True)
    full = hashlib.sha256(encoded.encode()).hexdigest()
    record = {"schema_version": "backtest_config_v1", "canonical_config_json": encoded,
              "config_hash": full[:12], "config_hash_full": full}
    with pytest.raises(ValueError, match="object with a schema namespace"):
        identity.legacy(record)


def test_new_identity_distinguishes_executable_types_order_time_and_namespace():
    original = {"schema_version": "replay_input_v1", "module": "sma_v1",
                "columns": ["price", "signal"], "timestamp": "2026-10-05T01:00:00Z", "value": 1}
    base = identity.digest(original)
    assert identity.digest(dict(reversed(list(original.items())))) == base
    for key, value in (("value", True), ("value", 1.0), ("columns", ["signal", "price"]),
                       ("timestamp", "2026-10-05T01:00:01Z"), ("module", "other"),
                       ("schema_version", "replay_input_v2")):
        assert identity.digest({**original, key: value}) != base
    # New exact JSON identities do not rewrite the legacy whole-float/default
    # normalization. This literal golden also preserves significant array order.
    legacy = {"b": [2.0, 1], "none": None, "a": 1.0}
    expected = '{"a":1,"b":[2,1]}'
    full = hashlib.sha256(expected.encode()).hexdigest()
    assert canonical_json(legacy) == expected
    assert compute_config_hash(legacy) == (full[:12], full)
    assert compute_config_hash({"a": 1, "b": [1, 2]})[1] != full
    assert compute_config_hash({"a": True, "b": [2, 1]})[1] != full


@pytest.mark.parametrize("raw", [
    {"fast_window": True}, {"slow_window": 40.0}, {"initial_capital": True},
    {"transaction_cost_bps": False}, {"cost_model": {"commission_bps": True}},
    {"position_sizing": {"type": "volatility_target", "lookback_days": 20.0}},
    {"position_sizing": {"type": "fixed_fraction", "fraction": True}},
    {"risk_management": {"type": "combined", "max_holding_days": True}},
    {"robustness": {"enabled": 1}}, {"robustness": {"seed": True}},
    {"sensitivity": {"x_values": [True, 20]}}, {"sensitivity": {"max_runs": 10.0}},
])
def test_executable_boolean_and_numeric_types_are_not_interchangeable(raw):
    with pytest.raises(ValueError):
        adapter.request_model(raw)


def test_nondefault_request_matches_independent_effective_config():
    request = {"ticker": "btc-usd", "start_date": "2020-01-01", "end_date": "2021-01-01",
               "fast_window": 7, "slow_window": 31, "initial_capital": 125000.5,
               "transaction_cost_bps": 99, "position_mode": "long_short", "annualization_mode": "auto",
               "cost_model": {"type": "commission_slippage", "commission_bps": 1.125,
                              "slippage_bps": 2.25, "spread_bps": .625},
               "position_sizing": {"type": "volatility_target", "target_volatility": .18,
                                   "lookback_days": 37, "max_exposure": .6},
               "risk_management": {"type": "combined", "stop_loss_pct": .075,
                                   "take_profit_pct": .3, "trailing_stop_pct": .04, "max_holding_days": 9},
               "benchmark": {"mode": "custom_ticker", "ticker": " qqq "},
               "robustness": {"enabled": True, "n_simulations": 200, "block_size": 7, "seed": 19},
               "sensitivity": {"enabled": True, "metric": "cagr", "x_values": [7, 11],
                               "y_values": [31, 43], "max_runs": 4}}
    expected = {"schema_version": "backtest_config_v1", "strategy": "sma_crossover", "ticker": "BTC-USD",
                "start_date": "2020-01-01", "end_date": "2021-01-01", "initial_capital": 125000.5,
                "strategy_params": {"fast_window": 7, "slow_window": 31},
                "cost_model": {"effective_cost_bps": 4},
                "position_sizing": {"type": "volatility_target", "target_volatility": .18,
                                    "lookback_days": 37, "max_exposure": .6},
                "risk_management": {"type": "combined", "stop_loss_pct": .075,
                                    "take_profit_pct": .3, "trailing_stop_pct": .04, "max_holding_days": 9},
                "annualization_mode": "crypto_365", "benchmark": {"mode": "custom_ticker", "ticker": "QQQ"},
                "position_mode": "long_short", "data_provider": "yfinance", "dataset_fingerprint": None}
    assert adapter.normalize(adapter.request_model(request), "yfinance") == expected
    restored = adapter.restore(expected, request)
    assert restored["robustness"] == {**request["robustness"], "method": "block_bootstrap_returns"}
    assert restored["sensitivity"] == {**request["sensitivity"], "x_param": "fast_window", "y_param": "slow_window"}
    assert restored["annualization_mode"] == "auto"
    assert restored["transaction_cost_bps"] == 99  # inactive fallback retained separately from effective cost
    assert adapter.normalize(adapter.request_model(restored), "yfinance") == expected
    canonical_only = adapter.restore(expected)
    assert canonical_only["cost_model"] == {"type": "simple_bps", "transaction_cost_bps": 4.0}
    assert canonical_only["annualization_mode"] == "crypto_365"
    assert "robustness" not in canonical_only and "sensitivity" not in canonical_only


def test_actual_frontend_wire_fixture_matches_independent_canonical_contract():
    # Matches the independently exercised stateful form/Run fixture in
    # ReplayBacktestForm.test.tsx, including conflicting inactive cost fallback.
    wire = {"ticker": "BTC-USD", "start_date": "2020-02-03", "end_date": "2021-04-05",
            "fast_window": 7, "slow_window": 31, "initial_capital": 234567, "transaction_cost_bps": 10,
            "cost_model": {"type": "simple_bps", "transaction_cost_bps": 37}, "position_mode": "long_short",
            "position_sizing": {"type": "volatility_target", "target_volatility": .23,
                                "lookback_days": 17, "max_exposure": .73},
            "risk_management": {"type": "combined", "stop_loss_pct": .07, "take_profit_pct": .19,
                                "trailing_stop_pct": .04, "max_holding_days": 13},
            "annualization_mode": "auto", "benchmark": {"mode": "custom_ticker", "ticker": "QQQ"},
            "robustness": {"enabled": True, "method": "block_bootstrap_returns", "n_simulations": 213,
                           "block_size": 7, "seed": 19},
            "sensitivity": {"enabled": True, "metric": "cagr", "x_param": "fast_window", "y_param": "slow_window",
                            "x_values": [3, 7], "y_values": [21, 31], "max_runs": 4}}
    expected = {"schema_version": "backtest_config_v1", "strategy": "sma_crossover", "ticker": "BTC-USD",
                "start_date": "2020-02-03", "end_date": "2021-04-05", "initial_capital": 234567,
                "strategy_params": {"fast_window": 7, "slow_window": 31}, "cost_model": {"effective_cost_bps": 37},
                "position_sizing": {"type": "volatility_target", "target_volatility": .23,
                                    "lookback_days": 17, "max_exposure": .73},
                "risk_management": {"type": "combined", "stop_loss_pct": .07, "take_profit_pct": .19,
                                    "trailing_stop_pct": .04, "max_holding_days": 13},
                "annualization_mode": "crypto_365", "benchmark": {"mode": "custom_ticker", "ticker": "QQQ"},
                "position_mode": "long_short", "data_provider": "yfinance", "dataset_fingerprint": None}
    assert adapter.normalize(adapter.request_model(wire), "yfinance") == expected
    local_wire = {**wire, "benchmark": {"mode": "none"}}
    local_expected = {**expected, "benchmark": {"mode": "none"}, "data_provider": "csv_upload",
                      "dataset_fingerprint": "a" * 64}
    assert adapter.normalize(adapter.request_model(local_wire), "csv_upload", "a" * 64) == local_expected


@pytest.mark.parametrize("key,value", [("start_date", "20200101"), ("start_date", "2020-W01-1"),
                                      ("end_date", "20210101"), ("end_date", "2021-W01-1")])
def test_dates_unrepresentable_by_actual_html_form_are_refused(key, value):
    from app.schemas import BacktestRequest
    raw = {"start_date": "2020-01-01", "end_date": "2021-01-01", key: value}
    # Legacy request semantics and hashes stay unchanged. Only exact form
    # restoration is refused; converting strings would rewrite that identity.
    legacy_request = BacktestRequest.model_validate(raw)
    canonical = adapter.normalize(legacy_request, "yfinance")
    assert canonical[key] == value
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        adapter.restore(canonical, raw)
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        adapter.restore(canonical)


@pytest.mark.parametrize("role", ["execution", "save", "inspection"])
def test_manifest_roles_are_explicit_and_cannot_be_backdated(role):
    value = manifest(role, python="3.13.5")
    assert environment.check(value, classification=role) is value
    if role != "execution":
        with pytest.raises(ValueError, match="classification"):
            environment.check(value)


@pytest.mark.parametrize("value", [None, [], True, "execution"])
def test_manifest_non_object_is_a_controlled_error(value):
    with pytest.raises(ValueError, match="manifest"):
        environment.check(value)


@pytest.mark.parametrize("old_dirty,new_dirty", [(True, True), (False, True), (True, False),
                                                 (None, False), (False, None), (None, None)])
def test_matching_head_does_not_certify_dirty_or_unknown_source(old_dirty, new_dirty):
    old = manifest(python="3.13.5", git_commit="a" * 40, source_dirty=old_dirty)
    current = manifest("inspection", python="3.13.5", git_commit="a" * 40, source_dirty=new_dirty)
    rows = {row["field"]: row for row in environment.compare(old, current)}
    assert rows["git_commit"]["state"] == "unknown"
    assert rows["source_dirty"]["state"] == "unknown"
    assert rows["python"]["state"] == "same"
    assert rows["node"]["state"] == rows["frontend_build"]["state"] == "unknown"


def test_clean_source_and_library_differences_stay_informational():
    old = manifest(python="3.13.5", git_commit="a" * 40, source_dirty=False, numpy="2.4.5")
    current = copy.deepcopy(old)
    current["classification"] = "inspection"
    current["fields"].update(git_commit="b" * 40, numpy="2.4.6")
    rows = {row["field"]: row for row in environment.compare(old, current)}
    assert rows["git_commit"]["state"] == rows["numpy"]["state"] == "different"
    assert rows["source_dirty"]["state"] == rows["python"]["state"] == "same"
    assert all(row["state"] == "unknown" for row in environment.compare(None, current))
    assert all(set(row) == {"field", "recorded", "current", "state"} for row in rows.values())


def test_collector_keeps_git_when_version_file_is_missing_and_does_not_inventory(tmp_path, monkeypatch):
    root = tmp_path / "source"
    module = root / "backend" / "app" / "run_replay" / "environment.py"
    module.parent.mkdir(parents=True)
    (root / ".git").mkdir()
    monkeypatch.setattr(environment, "__file__", str(module))
    monkeypatch.setattr(environment.platform, "python_version", lambda: "3.13.5")
    packages, commands = [], []

    def version(name):
        packages.append(name)
        if name == "scipy":
            raise environment.PackageNotFoundError(name)
        return "1.2.3"

    def command(args, **kwargs):
        commands.append(args)
        assert kwargs == {"cwd": root, "capture_output": True, "text": True, "timeout": 5}
        if args == ["git", "rev-parse", "HEAD"]:
            return SimpleNamespace(returncode=0, stdout="a" * 40 + "\n")
        assert args == ["git", "status", "--porcelain", "--untracked-files=normal"]
        return SimpleNamespace(returncode=0, stdout=" M backend/app/main.py\n")

    monkeypatch.setattr(environment, "version", version)
    monkeypatch.setattr(environment.subprocess, "run", command)
    result = environment.collect("save")
    assert result["classification"] == "save"
    assert result["fields"]["app_version"] is None
    assert result["fields"]["git_commit"] == "a" * 40
    assert result["fields"]["source_dirty"] is True
    assert result["fields"]["scipy"] is None
    assert result["fields"]["node"] is result["fields"]["frontend_build"] is None
    assert set(packages) == {"pandas", "numpy", "fastapi", "pydantic", "scipy"}
    assert len(commands) == 2
    assert set(result["fields"]) == set(environment.FIELDS)
    assert str(tmp_path) not in identity.validate(result)


def test_snapshot_without_git_leaves_source_unknown(tmp_path, monkeypatch):
    root = tmp_path / "snapshot"
    module = root / "backend" / "app" / "run_replay" / "environment.py"
    module.parent.mkdir(parents=True)
    (root / "VERSION").write_text("4.84.0-dev\n", encoding="utf-8")
    monkeypatch.setattr(environment, "__file__", str(module))
    monkeypatch.setattr(environment, "version", lambda _: "1.2.3")
    monkeypatch.setattr(environment.subprocess, "run", lambda *a, **kw: pytest.fail("Snapshot inspected unrelated Git"))
    result = environment.collect("inspection")
    assert result["fields"]["app_version"] == "4.84.0-dev"
    assert result["fields"]["git_commit"] is result["fields"]["source_dirty"] is None
