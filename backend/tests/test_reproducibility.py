"""
Tests for the reproducible config hash (research v1).

Pure layer: canonicalization determinism, default-normalization equivalences,
sensitivity to every result-changing input, insensitivity to outputs.
API layer: single backtest / comparison / CSV responses carry the hash; same
request → same hash; legacy-vs-explicit-default requests hash identically.

All deterministic / monkeypatched — no live yfinance.
"""

from __future__ import annotations

import math
import re

import pandas as pd
import pytest

from app.reproducibility import (
    build_reproducibility,
    canonical_json,
    compute_config_hash,
    normalize_backtest_config,
)
from app.schemas import BenchmarkConfig, PositionSizing, RiskManagement

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _base_config(**overrides):
    kwargs = dict(
        strategy="sma_crossover",
        ticker="spy",
        start_date="2015-01-01",
        end_date="2023-12-31",
        initial_capital=100_000.0,
        strategy_params={"fast_window": 20, "slow_window": 100},
        effective_cost_bps=10.0,
        position_sizing=None,
        risk_management=None,
        annualization_mode_used="trading_days_252",
        benchmark=None,
        position_mode="long_only",
        data_provider="yfinance",
    )
    kwargs.update(overrides)
    return normalize_backtest_config(**kwargs)


# ---------------------------------------------------------------------------
# Pure canonicalization + hashing
# ---------------------------------------------------------------------------


def test_same_config_same_hash_and_valid_sha256():
    short_a, full_a = compute_config_hash(_base_config())
    short_b, full_b = compute_config_hash(_base_config())
    assert full_a == full_b
    assert short_a == full_a[:12] == short_b
    assert _SHA256_RE.match(full_a)


def test_dict_key_order_does_not_change_hash():
    a = {"b": 2, "a": 1, "nested": {"y": 2, "x": 1}}
    b = {"a": 1, "nested": {"x": 1, "y": 2}, "b": 2}
    assert compute_config_hash(a) == compute_config_hash(b)
    assert canonical_json(a) == canonical_json(b)


def test_whole_floats_normalize_to_ints():
    assert compute_config_hash({"v": 10.0}) == compute_config_hash({"v": 10})
    assert canonical_json({"v": 10.0}) == '{"v":10}'


def test_missing_position_sizing_equals_full_allocation():
    a = _base_config(position_sizing=None)
    b = _base_config(position_sizing=PositionSizing(type="full_allocation"))
    c = _base_config(position_sizing=PositionSizing(type="full"))  # legacy alias
    assert compute_config_hash(a) == compute_config_hash(b) == compute_config_hash(c)


def test_missing_risk_management_equals_none():
    a = _base_config(risk_management=None)
    b = _base_config(risk_management=RiskManagement(type="none"))
    assert compute_config_hash(a) == compute_config_hash(b)


def test_missing_benchmark_equals_buy_and_hold():
    a = _base_config(benchmark=None)
    b = _base_config(benchmark=BenchmarkConfig(mode="buy_and_hold_same_asset"))
    assert compute_config_hash(a) == compute_config_hash(b)


def test_ticker_case_normalized():
    assert compute_config_hash(_base_config(ticker="spy")) == compute_config_hash(
        _base_config(ticker="SPY")
    )


def test_result_changing_inputs_change_hash():
    base = compute_config_hash(_base_config())
    assert compute_config_hash(_base_config(ticker="QQQ")) != base
    assert compute_config_hash(_base_config(start_date="2016-01-01")) != base
    assert compute_config_hash(_base_config(end_date="2022-12-31")) != base
    assert compute_config_hash(_base_config(initial_capital=50_000.0)) != base
    assert (
        compute_config_hash(
            _base_config(strategy_params={"fast_window": 10, "slow_window": 100})
        )
        != base
    )
    assert compute_config_hash(_base_config(effective_cost_bps=25.0)) != base
    assert (
        compute_config_hash(
            _base_config(position_sizing=PositionSizing(type="fixed_fraction", fraction=0.5))
        )
        != base
    )
    assert (
        compute_config_hash(
            _base_config(
                risk_management=RiskManagement(
                    type="fixed_stop_take_profit", stop_loss_pct=0.1
                )
            )
        )
        != base
    )
    assert (
        compute_config_hash(
            _base_config(benchmark=BenchmarkConfig(mode="custom_ticker", ticker="QQQ"))
        )
        != base
    )
    assert compute_config_hash(_base_config(position_mode="long_short")) != base
    assert (
        compute_config_hash(_base_config(annualization_mode_used="crypto_365")) != base
    )


def test_outputs_do_not_affect_hash():
    # The canonical config never contains outputs; adding them to a *copy* of
    # the dict (simulating a buggy caller) is the only way to change the hash.
    config = _base_config()
    _, before = compute_config_hash(config)
    # metrics / curves / ids are simply not part of the normalized inputs:
    assert "metrics" not in canonical_json(config)
    assert "equity_curve" not in canonical_json(config)
    assert "saved" not in canonical_json(config)
    _, after = compute_config_hash(_base_config())
    assert before == after


def test_build_reproducibility_block():
    block = build_reproducibility(_base_config())
    assert block.schema_version == "backtest_config_v1"
    assert block.config_hash == block.config_hash_full[:12]
    assert _SHA256_RE.match(block.config_hash_full)
    assert '"ticker":"SPY"' in block.canonical_config_json


# ---------------------------------------------------------------------------
# API integration
# ---------------------------------------------------------------------------

_DATES = pd.date_range("2015-01-01", periods=400, freq="B")


def _fake_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
    prices = [100.0]
    for i in range(1, len(_DATES)):
        r = 0.012 * math.sin(0.045 * i) + 0.004 * math.cos(0.23 * i)
        prices.append(prices[-1] * (1.0 + r))
    return pd.DataFrame({"Close": prices}, index=_DATES)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main_module, "_fetch", _fake_fetch)
    return TestClient(main_module.app)


def test_api_response_includes_config_hash(client):
    body = client.post("/backtest/sma-crossover", json={}).json()
    rep = body["reproducibility"]
    assert rep["schema_version"] == "backtest_config_v1"
    assert _SHA256_RE.match(rep["config_hash_full"])
    assert rep["config_hash"] == rep["config_hash_full"][:12]
    assert rep["canonical_config_json"].startswith("{")


def test_api_same_request_same_hash_repeatable(client):
    a = client.post("/backtest/sma-crossover", json={}).json()
    b = client.post("/backtest/sma-crossover", json={}).json()
    assert a["reproducibility"]["config_hash_full"] == b["reproducibility"]["config_hash_full"]


def test_api_legacy_defaults_hash_like_explicit_defaults(client):
    legacy = client.post("/backtest/sma-crossover", json={}).json()
    explicit = client.post(
        "/backtest/sma-crossover",
        json={
            "cost_model": {"type": "simple_bps", "transaction_cost_bps": 10},
            "position_sizing": {"type": "full_allocation"},
            "risk_management": {"type": "none"},
            "annualization_mode": "trading_days_252",
            "benchmark": {"mode": "buy_and_hold_same_asset"},
        },
    ).json()
    assert (
        legacy["reproducibility"]["config_hash_full"]
        == explicit["reproducibility"]["config_hash_full"]
    )


def test_api_changed_cost_changes_hash(client):
    a = client.post("/backtest/sma-crossover", json={}).json()
    b = client.post(
        "/backtest/sma-crossover", json={"transaction_cost_bps": 20}
    ).json()
    assert a["reproducibility"]["config_hash"] != b["reproducibility"]["config_hash"]


def test_api_auto_annualization_hashes_as_resolved(client):
    auto = client.post(
        "/backtest/sma-crossover", json={"annualization_mode": "auto"}
    ).json()
    explicit = client.post(
        "/backtest/sma-crossover", json={"annualization_mode": "trading_days_252"}
    ).json()
    # auto on SPY resolves to 252 → identical results → identical hash.
    assert (
        auto["reproducibility"]["config_hash_full"]
        == explicit["reproducibility"]["config_hash_full"]
    )


def test_api_comparison_includes_config_hash(client):
    a = client.post("/research/strategy-comparison", json={}).json()
    b = client.post("/research/strategy-comparison", json={}).json()
    rep = a["reproducibility"]
    assert rep["schema_version"] == "comparison_config_v1"
    assert _SHA256_RE.match(rep["config_hash_full"])
    assert rep["config_hash_full"] == b["reproducibility"]["config_hash_full"]
    c = client.post(
        "/research/strategy-comparison", json={"transaction_cost_bps": 25}
    ).json()
    assert c["reproducibility"]["config_hash_full"] != rep["config_hash_full"]


def test_api_csv_hash_includes_content_fingerprint():
    import io

    def _csv_bytes(base: float) -> bytes:
        rows = "\n".join(
            f"{d.date()},{base + i * 0.5}"
            for i, d in enumerate(pd.date_range("2020-01-01", periods=160, freq="B"))
        )
        return ("Date,Close\n" + rows).encode()

    client = TestClient(main_module.app)

    def _run(content: bytes):
        return client.post(
            "/backtest/csv",
            files={"file": ("prices.csv", io.BytesIO(content), "text/csv")},
            data={"strategy": "sma_crossover", "params": '{"fast_window": 10, "slow_window": 30}'},
        ).json()

    a = _run(_csv_bytes(100.0))
    b = _run(_csv_bytes(100.0))  # same content → same hash
    c = _run(_csv_bytes(200.0))  # different content, same params → different hash
    assert a["reproducibility"]["config_hash_full"] == b["reproducibility"]["config_hash_full"]
    assert a["reproducibility"]["config_hash_full"] != c["reproducibility"]["config_hash_full"]
    assert "dataset_fingerprint" in a["reproducibility"]["canonical_config_json"]
