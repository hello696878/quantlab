"""
API tests for the CSV upload backtest endpoint (POST /backtest/csv).

These tests exercise the real parser + strategy + backtest stack on small
synthetic CSVs.  No network calls are made.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


@pytest.fixture
def client():
    return TestClient(main_module.app)


def make_csv_bytes(
    n: int = 300,
    start: str = "2018-01-01",
    date_col: str = "date",
    close_col: str = "close",
    pattern: str = "uptrend",
) -> bytes:
    dates = pd.date_range(start, periods=n, freq="B")
    if pattern == "uptrend":
        closes = [100.0 + i * 0.5 for i in range(n)]
    elif pattern == "vshape":
        half = n // 2
        down = [100.0 * (0.99**i) for i in range(half)]
        up = [down[-1] * (1.01**i) for i in range(n - half)]
        closes = down + up
    else:
        closes = [100.0 for _ in range(n)]
    df = pd.DataFrame({date_col: dates.strftime("%Y-%m-%d"), close_col: closes})
    return df.to_csv(index=False).encode("utf-8")


def post_csv(client, *, strategy, params, csv_bytes=None, filename="prices.csv"):
    if csv_bytes is None:
        csv_bytes = make_csv_bytes()
    return client.post(
        "/backtest/csv",
        files={"file": (filename, csv_bytes, "text/csv")},
        data={"strategy": strategy, "params": json.dumps(params)},
    )


# ---------------------------------------------------------------------------
# Happy paths — one per supported strategy
# ---------------------------------------------------------------------------


def test_csv_sma_crossover(client):
    resp = post_csv(
        client,
        strategy="sma_crossover",
        params={"fast_window": 20, "slow_window": 50, "transaction_cost_bps": 10, "initial_capital": 100000},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["strategy"] == "sma_crossover"
    assert data["fast_window"] == 20
    assert data["slow_window"] == 50
    assert len(data["equity_curve"]) > 0
    assert "strategy_metrics" in data and "benchmark_metrics" in data


def test_csv_rsi(client):
    resp = post_csv(
        client,
        strategy="rsi_mean_reversion",
        params={"rsi_window": 14, "oversold_threshold": 30, "exit_threshold": 50},
        csv_bytes=make_csv_bytes(pattern="vshape"),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["strategy"] == "rsi_mean_reversion"


def test_csv_bollinger(client):
    resp = post_csv(
        client,
        strategy="bollinger_band",
        params={"bb_window": 20, "num_std": 2.0, "exit_band": "middle"},
        csv_bytes=make_csv_bytes(pattern="vshape"),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["strategy"] == "bollinger_band"


def test_csv_momentum(client):
    resp = post_csv(
        client,
        strategy="momentum",
        params={"momentum_window": 60, "entry_threshold": 0.0, "exit_threshold": 0.0},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["strategy"] == "momentum"


def test_csv_volatility_breakout(client):
    resp = post_csv(
        client,
        strategy="volatility_breakout",
        params={"lookback_window": 20, "breakout_multiplier": 1.0, "exit_window": 10},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["strategy"] == "volatility_breakout"


# ---------------------------------------------------------------------------
# Identity / metadata
# ---------------------------------------------------------------------------


def test_csv_label_from_filename(client):
    resp = post_csv(
        client,
        strategy="sma_crossover",
        params={"fast_window": 20, "slow_window": 50},
        filename="MY_SERIES.csv",
    )
    assert resp.status_code == 200
    # _build_response upper-cases the label.
    assert resp.json()["ticker"] == "MY_SERIES"


def test_csv_dates_from_data(client):
    csv_bytes = make_csv_bytes(n=300, start="2019-03-01")
    resp = post_csv(
        client,
        strategy="sma_crossover",
        params={"fast_window": 10, "slow_window": 30},
        csv_bytes=csv_bytes,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["start_date"] == "2019-03-01"
    # end date is derived from the last row, strictly after the start.
    assert data["end_date"] > data["start_date"]


def test_csv_flexible_columns(client):
    csv_bytes = make_csv_bytes(date_col="Timestamp", close_col="Adj Close")
    resp = post_csv(
        client,
        strategy="sma_crossover",
        params={"fast_window": 20, "slow_window": 50},
        csv_bytes=csv_bytes,
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_csv_pairs_rejected(client):
    resp = post_csv(client, strategy="pairs", params={})
    assert resp.status_code == 422
    assert "pairs" in resp.json()["detail"].lower()


def test_csv_unknown_strategy_rejected(client):
    resp = post_csv(client, strategy="banana", params={})
    assert resp.status_code == 422


def test_csv_missing_date_column_rejected(client):
    df = pd.DataFrame({"close": [100.0 + i for i in range(300)]})
    resp = post_csv(
        client,
        strategy="sma_crossover",
        params={"fast_window": 20, "slow_window": 50},
        csv_bytes=df.to_csv(index=False).encode(),
    )
    assert resp.status_code == 422
    assert "date column" in resp.json()["detail"]


def test_csv_missing_close_column_rejected(client):
    df = pd.DataFrame(
        {"date": pd.date_range("2020-01-01", periods=300, freq="B").strftime("%Y-%m-%d")}
    )
    resp = post_csv(
        client,
        strategy="sma_crossover",
        params={"fast_window": 20, "slow_window": 50},
        csv_bytes=df.to_csv(index=False).encode(),
    )
    assert resp.status_code == 422
    assert "close price column" in resp.json()["detail"]


def test_csv_non_numeric_close_rows_are_dropped(client):
    dates = pd.date_range("2020-01-01", periods=300, freq="B").strftime("%Y-%m-%d")
    closes: list[float | str] = [100.0 + i for i in range(300)]
    closes[10] = "oops"
    df = pd.DataFrame({"date": dates, "close": closes})

    resp = post_csv(
        client,
        strategy="sma_crossover",
        params={"fast_window": 20, "slow_window": 50},
        csv_bytes=df.to_csv(index=False).encode(),
    )

    assert resp.status_code == 200, resp.text
    assert len(resp.json()["equity_curve"]) == 299


def test_csv_zero_prices_rejected(client):
    df = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=250, freq="B").strftime("%Y-%m-%d"),
            "close": [100.0 + i for i in range(249)] + [0.0],
        }
    )
    resp = post_csv(
        client,
        strategy="sma_crossover",
        params={"fast_window": 20, "slow_window": 50},
        csv_bytes=df.to_csv(index=False).encode(),
    )
    assert resp.status_code == 422
    assert "positive" in resp.json()["detail"]


def test_csv_invalid_params_fast_ge_slow(client):
    resp = post_csv(
        client,
        strategy="sma_crossover",
        params={"fast_window": 100, "slow_window": 50},
    )
    assert resp.status_code == 422
    assert "fast_window" in resp.json()["detail"]


def test_csv_invalid_rsi_thresholds(client):
    # oversold must be < exit; reversed values trip the model validator.
    resp = post_csv(
        client,
        strategy="rsi_mean_reversion",
        params={"rsi_window": 14, "oversold_threshold": 60, "exit_threshold": 40},
    )
    assert resp.status_code == 422


def test_csv_too_few_rows(client):
    csv_bytes = make_csv_bytes(n=30)  # < slow_window (200) + 2
    resp = post_csv(
        client,
        strategy="sma_crossover",
        params={"fast_window": 50, "slow_window": 200},
        csv_bytes=csv_bytes,
    )
    assert resp.status_code == 422
    assert "rows available" in resp.json()["detail"]


def test_csv_bad_params_json(client):
    csv_bytes = make_csv_bytes()
    resp = client.post(
        "/backtest/csv",
        files={"file": ("prices.csv", csv_bytes, "text/csv")},
        data={"strategy": "sma_crossover", "params": "{not valid json"},
    )
    assert resp.status_code == 422
    assert "JSON" in resp.json()["detail"]


def test_csv_malformed_file_rejected(client):
    resp = post_csv(
        client,
        strategy="sma_crossover",
        params={"fast_window": 20, "slow_window": 50},
        csv_bytes=b'date,close\n"2020-01-01,100\n2020-01-02,101\n',
    )
    assert resp.status_code == 422
    assert "parse CSV" in resp.json()["detail"]


def test_csv_upload_not_written_to_working_directory(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    resp = post_csv(
        client,
        strategy="sma_crossover",
        params={"fast_window": 20, "slow_window": 50},
        filename="uploaded.csv",
    )

    assert resp.status_code == 200, resp.text
    assert not (tmp_path / "uploaded.csv").exists()


def test_csv_negative_prices_rejected(client):
    df = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=250, freq="B").strftime("%Y-%m-%d"),
            "close": [100.0 - i for i in range(250)],  # goes negative
        }
    )
    resp = post_csv(
        client,
        strategy="sma_crossover",
        params={"fast_window": 20, "slow_window": 50},
        csv_bytes=df.to_csv(index=False).encode(),
    )
    assert resp.status_code == 422
    assert "positive" in resp.json()["detail"]


def test_csv_defaults_when_params_empty(client):
    # Empty params → model defaults (SMA 50/200); 300 rows is enough.
    resp = post_csv(client, strategy="sma_crossover", params={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["fast_window"] == 50
    assert data["slow_window"] == 200
