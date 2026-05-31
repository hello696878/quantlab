"""
Tests for the saved custom strategy templates CRUD layer and API endpoints.

Each test receives a fresh temporary SQLite database via the autouse
``fresh_db`` fixture — no test writes to backend/data/quantlab.db.
"""

from __future__ import annotations

import sqlite3

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")
db_module = pytest.importorskip("app.db")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_quantlab.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    yield


@pytest.fixture
def client():
    return TestClient(main_module.app)


# ---------------------------------------------------------------------------
# Sample payloads
# ---------------------------------------------------------------------------

SMA_RULE = {
    "left": {"type": "indicator", "name": "sma", "params": {"window": 50}},
    "operator": ">",
    "right": {"type": "indicator", "name": "sma", "params": {"window": 200}},
}
RSI_RULE = {
    "left": {"type": "indicator", "name": "rsi", "params": {"window": 14}},
    "operator": "<",
    "right": {"type": "constant", "value": 70},
}
EXIT_RULE = {
    "left": {"type": "indicator", "name": "sma", "params": {"window": 50}},
    "operator": "<=",
    "right": {"type": "indicator", "name": "sma", "params": {"window": 200}},
}

BASE_TEMPLATE: dict = {
    "name": "SMA + RSI Trend Filter",
    "description": "Long when SMA trend is positive and RSI is not overbought.",
    "entry_logic": "AND",
    "exit_logic": "OR",
    "entry_rules": [SMA_RULE, RSI_RULE],
    "exit_rules": [EXIT_RULE],
    "tags": ["trend", "rsi"],
}


# ---------------------------------------------------------------------------
# 1. Database initialisation
# ---------------------------------------------------------------------------


def test_db_initializes_template_table(tmp_path, monkeypatch):
    db_file = tmp_path / "fresh.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()

    conn = sqlite3.connect(str(db_file))
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    conn.close()
    assert "custom_strategy_templates" in tables


# ---------------------------------------------------------------------------
# 2. Create
# ---------------------------------------------------------------------------


def test_create_template(client):
    resp = client.post("/custom-strategies", json=BASE_TEMPLATE)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] >= 1
    assert data["name"] == "SMA + RSI Trend Filter"
    assert data["entry_logic"] == "AND"
    assert data["exit_logic"] == "OR"
    assert len(data["entry_rules"]) == 2
    assert len(data["exit_rules"]) == 1
    assert data["tags"] == ["trend", "rsi"]
    assert data["created_at"] == data["updated_at"]


def test_create_minimal_template(client):
    resp = client.post(
        "/custom-strategies",
        json={"name": "Empty draft"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["entry_rules"] == []
    assert data["exit_rules"] == []
    assert data["tags"] == []
    assert data["entry_logic"] == "AND"  # default
    assert data["exit_logic"] == "OR"  # default


# ---------------------------------------------------------------------------
# 3. List
# ---------------------------------------------------------------------------


def test_list_empty(client):
    resp = client.get("/custom-strategies")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_returns_summaries(client):
    client.post("/custom-strategies", json=BASE_TEMPLATE)
    rows = client.get("/custom-strategies").json()
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "SMA + RSI Trend Filter"
    assert row["num_entry_rules"] == 2
    assert row["num_exit_rules"] == 1
    assert row["tags"] == ["trend", "rsi"]
    # Summaries omit the full rule arrays.
    assert "entry_rules" not in row
    assert "exit_rules" not in row


# ---------------------------------------------------------------------------
# 4. Get by id
# ---------------------------------------------------------------------------


def test_get_template(client):
    tid = client.post("/custom-strategies", json=BASE_TEMPLATE).json()["id"]
    data = client.get(f"/custom-strategies/{tid}").json()
    assert data["id"] == tid
    assert data["entry_rules"][0]["left"]["name"] == "sma"
    assert data["entry_rules"][1]["right"]["value"] == 70


def test_get_missing_returns_404(client):
    assert client.get("/custom-strategies/999").status_code == 404


# ---------------------------------------------------------------------------
# 5. Update
# ---------------------------------------------------------------------------


def test_update_template(client):
    tid = client.post("/custom-strategies", json=BASE_TEMPLATE).json()["id"]

    updated = {
        **BASE_TEMPLATE,
        "name": "Renamed Strategy",
        "entry_logic": "OR",
        "entry_rules": [RSI_RULE],
        "tags": ["updated"],
    }
    resp = client.put(f"/custom-strategies/{tid}", json=updated)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == tid
    assert data["name"] == "Renamed Strategy"
    assert data["entry_logic"] == "OR"
    assert len(data["entry_rules"]) == 1
    assert data["tags"] == ["updated"]
    # updated_at advances; created_at is preserved.
    assert data["updated_at"] >= data["created_at"]


def test_update_missing_returns_404(client):
    assert client.put("/custom-strategies/999", json=BASE_TEMPLATE).status_code == 404


# ---------------------------------------------------------------------------
# 6. Delete
# ---------------------------------------------------------------------------


def test_delete_template(client):
    tid = client.post("/custom-strategies", json=BASE_TEMPLATE).json()["id"]
    resp = client.delete(f"/custom-strategies/{tid}")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True, "id": tid}
    assert client.get(f"/custom-strategies/{tid}").status_code == 404


def test_delete_missing_returns_404(client):
    assert client.delete("/custom-strategies/999").status_code == 404


# ---------------------------------------------------------------------------
# 7. Validation
# ---------------------------------------------------------------------------


def test_empty_name_rejected(client):
    resp = client.post("/custom-strategies", json={**BASE_TEMPLATE, "name": ""})
    assert resp.status_code == 422


def test_invalid_logic_rejected(client):
    resp = client.post(
        "/custom-strategies", json={**BASE_TEMPLATE, "entry_logic": "NAND"}
    )
    assert resp.status_code == 422


def test_invalid_rule_indicator_rejected(client):
    bad = {
        **BASE_TEMPLATE,
        "entry_rules": [
            {
                "left": {"type": "indicator", "name": "macd", "params": {"window": 12}},
                "operator": ">",
                "right": {"type": "constant", "value": 0},
            }
        ],
    }
    assert client.post("/custom-strategies", json=bad).status_code == 422


def test_invalid_operator_rejected(client):
    bad = {
        **BASE_TEMPLATE,
        "entry_rules": [{**SMA_RULE, "operator": "=="}],
    }
    assert client.post("/custom-strategies", json=bad).status_code == 422


def test_too_many_entry_rules_rejected(client):
    bad = {**BASE_TEMPLATE, "entry_rules": [SMA_RULE for _ in range(11)]}
    assert client.post("/custom-strategies", json=bad).status_code == 422


def test_too_many_exit_rules_rejected(client):
    bad = {**BASE_TEMPLATE, "exit_rules": [EXIT_RULE for _ in range(11)]}
    assert client.post("/custom-strategies", json=bad).status_code == 422


def test_bb_rule_requires_num_std(client):
    bad = {
        **BASE_TEMPLATE,
        "entry_rules": [
            {
                "left": {"type": "close"},
                "operator": "<",
                "right": {"type": "indicator", "name": "bb_lower", "params": {"window": 20}},
            }
        ],
    }
    resp = client.post("/custom-strategies", json=bad)
    assert resp.status_code == 422
    assert "num_std" in resp.text


def test_no_code_execution_string_constant_rejected(client):
    """A string where a numeric constant is expected is rejected, never run."""
    bad = {
        **BASE_TEMPLATE,
        "entry_rules": [
            {
                "left": {"type": "close"},
                "operator": ">",
                "right": {"type": "constant", "value": "__import__('os').system('echo hi')"},
            }
        ],
    }
    assert client.post("/custom-strategies", json=bad).status_code == 422


def test_unknown_operand_type_rejected(client):
    bad = {
        **BASE_TEMPLATE,
        "entry_rules": [
            {
                "left": {"type": "formula", "expr": "close > sma(20)"},
                "operator": ">",
                "right": {"type": "constant", "value": 0},
            }
        ],
    }
    assert client.post("/custom-strategies", json=bad).status_code == 422


# ---------------------------------------------------------------------------
# 8. JSON round-trip
# ---------------------------------------------------------------------------


def test_rules_roundtrip(client):
    """
    Rules survive a write→read cycle.  Values are stored in their validated,
    canonical form (e.g. integer constants become floats, indicator params
    gain an explicit num_std=None), so we compare the meaningful structure.
    """
    tid = client.post("/custom-strategies", json=BASE_TEMPLATE).json()["id"]
    data = client.get(f"/custom-strategies/{tid}").json()

    assert len(data["entry_rules"]) == 2
    assert len(data["exit_rules"]) == 1
    assert data["tags"] == ["trend", "rsi"]

    e0 = data["entry_rules"][0]
    assert e0["left"]["name"] == "sma"
    assert e0["left"]["params"]["window"] == 50
    assert e0["operator"] == ">"
    assert e0["right"]["params"]["window"] == 200

    e1 = data["entry_rules"][1]
    assert e1["left"]["name"] == "rsi"
    assert e1["operator"] == "<"
    assert e1["right"]["type"] == "constant"
    assert float(e1["right"]["value"]) == 70.0

    # Re-posting the read-back rules is accepted (stable canonical form).
    reposted = client.post(
        "/custom-strategies",
        json={**BASE_TEMPLATE, "name": "Round-trip copy",
              "entry_rules": data["entry_rules"], "exit_rules": data["exit_rules"]},
    )
    assert reposted.status_code == 200, reposted.text


def test_loaded_template_runs_in_builder(client, monkeypatch):
    """A saved template's rules are accepted verbatim by /backtest/custom."""
    import math
    import pandas as pd

    def fake_df(*_a, **_k):
        vals = [100.0 + 25.0 * math.sin(i / 25.0) + i * 0.1 for i in range(300)]
        idx = pd.date_range("2018-01-01", periods=300, freq="B")
        return pd.DataFrame({"Close": vals}, index=idx)

    monkeypatch.setattr(main_module, "_fetch", fake_df)

    tid = client.post("/custom-strategies", json=BASE_TEMPLATE).json()["id"]
    tpl = client.get(f"/custom-strategies/{tid}").json()

    # Map template AND/OR → builder all/any and run.
    run_req = {
        "ticker": "SPY",
        "start_date": "2018-01-01",
        "end_date": "2020-01-01",
        "transaction_cost_bps": 10,
        "initial_capital": 100000,
        "entry_rules": tpl["entry_rules"],
        "entry_logic": "all" if tpl["entry_logic"] == "AND" else "any",
        "exit_rules": tpl["exit_rules"],
        "exit_logic": "all" if tpl["exit_logic"] == "AND" else "any",
    }
    resp = client.post("/backtest/custom", json=run_req)
    assert resp.status_code == 200, resp.text
    assert resp.json()["strategy"] == "custom"
