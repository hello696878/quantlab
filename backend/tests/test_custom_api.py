"""
API tests for the Custom Strategy Builder endpoint (POST /backtest/custom).

The data-fetch layer is monkeypatched, so no network calls are made.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


def make_df(n: int = 300, start: str = "2018-01-01") -> pd.DataFrame:
    vals = [100.0 + 25.0 * math.sin(i / 25.0) + i * 0.1 for i in range(n)]
    idx = pd.date_range(start, periods=n, freq="B")
    return pd.DataFrame({"Close": vals}, index=idx)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main_module, "_fetch", lambda ticker, start, end: make_df())
    return TestClient(main_module.app)


def base_request(**overrides) -> dict:
    req = {
        "ticker": "SPY",
        "start_date": "2018-01-01",
        "end_date": "2020-01-01",
        "transaction_cost_bps": 10,
        "initial_capital": 100000,
        "entry_rules": [
            {
                "left": {"type": "indicator", "name": "sma", "params": {"window": 20}},
                "operator": ">",
                "right": {"type": "indicator", "name": "sma", "params": {"window": 50}},
            }
        ],
        "entry_logic": "all",
        "exit_rules": [
            {
                "left": {"type": "indicator", "name": "sma", "params": {"window": 20}},
                "operator": "<=",
                "right": {"type": "indicator", "name": "sma", "params": {"window": 50}},
            }
        ],
        "exit_logic": "any",
    }
    req.update(overrides)
    return req


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_custom_sma_crossover(client):
    resp = client.post("/backtest/custom", json=base_request())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["strategy"] == "custom"
    assert len(data["equity_curve"]) > 0
    assert "strategy_metrics" in data and "benchmark_metrics" in data


def test_custom_close_vs_constant(client):
    resp = client.post(
        "/backtest/custom",
        json=base_request(
            entry_rules=[
                {
                    "left": {"type": "close"},
                    "operator": ">",
                    "right": {"type": "constant", "value": 0},
                }
            ],
            exit_rules=[],
        ),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["strategy"] == "custom"


def test_custom_rsi_and_bollinger(client):
    resp = client.post(
        "/backtest/custom",
        json=base_request(
            entry_rules=[
                {
                    "left": {"type": "indicator", "name": "rsi", "params": {"window": 14}},
                    "operator": "<",
                    "right": {"type": "constant", "value": 30},
                },
                {
                    "left": {"type": "close"},
                    "operator": "<",
                    "right": {
                        "type": "indicator",
                        "name": "bb_lower",
                        "params": {"window": 20, "num_std": 2.0},
                    },
                },
            ],
            entry_logic="any",
            exit_rules=[
                {
                    "left": {"type": "indicator", "name": "rsi", "params": {"window": 14}},
                    "operator": ">",
                    "right": {"type": "constant", "value": 55},
                }
            ],
        ),
    )
    assert resp.status_code == 200, resp.text


def test_custom_momentum(client):
    resp = client.post(
        "/backtest/custom",
        json=base_request(
            entry_rules=[
                {
                    "left": {"type": "indicator", "name": "momentum", "params": {"window": 60}},
                    "operator": ">",
                    "right": {"type": "constant", "value": 0},
                }
            ],
            exit_rules=[
                {
                    "left": {"type": "indicator", "name": "momentum", "params": {"window": 60}},
                    "operator": "<=",
                    "right": {"type": "constant", "value": 0},
                }
            ],
        ),
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# Validation / error cases
# ---------------------------------------------------------------------------


def test_custom_empty_entry_rules_rejected(client):
    resp = client.post("/backtest/custom", json=base_request(entry_rules=[]))
    assert resp.status_code == 422


def test_custom_invalid_operator_rejected(client):
    bad = base_request()
    bad["entry_rules"][0]["operator"] = "=="
    resp = client.post("/backtest/custom", json=bad)
    assert resp.status_code == 422


def test_custom_unknown_indicator_rejected(client):
    bad = base_request()
    bad["entry_rules"][0]["left"] = {
        "type": "indicator",
        "name": "macd",
        "params": {"window": 12},
    }
    resp = client.post("/backtest/custom", json=bad)
    assert resp.status_code == 422


def test_custom_bb_requires_num_std(client):
    bad = base_request(
        entry_rules=[
            {
                "left": {"type": "close"},
                "operator": ">",
                "right": {"type": "indicator", "name": "bb_upper", "params": {"window": 20}},
            }
        ]
    )
    resp = client.post("/backtest/custom", json=bad)
    assert resp.status_code == 422
    assert "num_std" in resp.text


def test_custom_window_out_of_range_rejected(client):
    bad = base_request()
    bad["entry_rules"][0]["left"]["params"]["window"] = 0  # ge=1
    resp = client.post("/backtest/custom", json=bad)
    assert resp.status_code == 422


def test_custom_window_above_max_rejected(client):
    bad = base_request()
    bad["entry_rules"][0]["left"]["params"]["window"] = 1001
    resp = client.post("/backtest/custom", json=bad)
    assert resp.status_code == 422


def test_custom_rsi_window_one_rejected(client):
    bad = base_request()
    bad["entry_rules"][0]["left"] = {
        "type": "indicator",
        "name": "rsi",
        "params": {"window": 1},
    }
    resp = client.post("/backtest/custom", json=bad)
    assert resp.status_code == 422
    assert "window" in resp.text


def test_custom_too_many_entry_rules_rejected(client):
    one_rule = base_request()["entry_rules"][0]
    resp = client.post(
        "/backtest/custom",
        json=base_request(entry_rules=[one_rule for _ in range(11)]),
    )
    assert resp.status_code == 422


def test_custom_unknown_operand_type_rejected(client):
    bad = base_request()
    bad["entry_rules"][0]["left"] = {"type": "formula", "expr": "close > sma(20)"}
    resp = client.post("/backtest/custom", json=bad)
    assert resp.status_code == 422


def test_custom_extra_indicator_param_rejected(client):
    bad = base_request()
    bad["entry_rules"][0]["left"]["params"]["unsafe"] = "ignored?"
    resp = client.post("/backtest/custom", json=bad)
    assert resp.status_code == 422


def test_custom_extra_top_level_field_rejected(client):
    bad = base_request()
    bad["formula"] = "__import__('os').system('echo unsafe')"
    resp = client.post("/backtest/custom", json=bad)
    assert resp.status_code == 422


def test_custom_too_few_bars(client, monkeypatch):
    # Only 30 rows but the strategy references a 50-day SMA (needs 55).
    monkeypatch.setattr(main_module, "_fetch", lambda *a, **k: make_df(n=30))
    resp = client.post("/backtest/custom", json=base_request())
    assert resp.status_code == 422
    assert "trading days available" in resp.json()["detail"]


def test_custom_no_code_execution_constant_is_data(client):
    """A string where a number is expected is rejected by validation, not run."""
    bad = base_request(
        entry_rules=[
            {
                "left": {"type": "close"},
                "operator": ">",
                "right": {"type": "constant", "value": "__import__('os')"},
            }
        ]
    )
    resp = client.post("/backtest/custom", json=bad)
    assert resp.status_code == 422
