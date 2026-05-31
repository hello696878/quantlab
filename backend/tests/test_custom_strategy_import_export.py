"""
Tests for import / export of custom strategy templates.

Covers GET /custom-strategies/{id}/export and POST /custom-strategies/import.
Uses a fresh temporary SQLite database per test (no network, no real DB).
"""

from __future__ import annotations

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")
db_module = pytest.importorskip("app.db")


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
# Sample data
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


def valid_export(**overrides) -> dict:
    """A well-formed import/export envelope."""
    doc = {
        "schema_version": "1.0",
        "type": "quantlab_custom_strategy_template",
        "name": "Imported Strategy",
        "description": "From file",
        "entry_logic": "AND",
        "exit_logic": "OR",
        "entry_rules": [SMA_RULE],
        "exit_rules": [EXIT_RULE],
        "tags": ["imported"],
    }
    doc.update(overrides)
    return doc


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def test_export_includes_markers(client):
    tid = client.post("/custom-strategies", json=BASE_TEMPLATE).json()["id"]
    resp = client.get(f"/custom-strategies/{tid}/export")
    assert resp.status_code == 200, resp.text
    doc = resp.json()
    assert doc["schema_version"] == "1.0"
    assert doc["type"] == "quantlab_custom_strategy_template"
    assert doc["name"] == "SMA + RSI Trend Filter"
    assert len(doc["entry_rules"]) == 2
    assert len(doc["exit_rules"]) == 1
    assert doc["tags"] == ["trend", "rsi"]


def test_export_excludes_local_fields(client):
    tid = client.post("/custom-strategies", json=BASE_TEMPLATE).json()["id"]
    doc = client.get(f"/custom-strategies/{tid}/export").json()
    assert "id" not in doc
    assert "created_at" not in doc
    assert "updated_at" not in doc


def test_export_missing_returns_404(client):
    assert client.get("/custom-strategies/999/export").status_code == 404


# ---------------------------------------------------------------------------
# Import — happy path
# ---------------------------------------------------------------------------


def test_import_creates_template(client):
    resp = client.post("/custom-strategies/import", json=valid_export())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] >= 1
    assert data["name"] == "Imported Strategy"
    assert data["entry_logic"] == "AND"
    assert len(data["entry_rules"]) == 1
    assert data["tags"] == ["imported"]

    # It now appears in the saved template list.
    rows = client.get("/custom-strategies").json()
    assert any(r["id"] == data["id"] for r in rows)


def test_import_then_run(client, monkeypatch):
    """An imported template can be loaded and run through /backtest/custom."""
    import math
    import pandas as pd

    def fake_df(*_a, **_k):
        vals = [100.0 + 25.0 * math.sin(i / 25.0) + i * 0.1 for i in range(300)]
        idx = pd.date_range("2018-01-01", periods=300, freq="B")
        return pd.DataFrame({"Close": vals}, index=idx)

    monkeypatch.setattr(main_module, "_fetch", fake_df)

    tid = client.post("/custom-strategies/import", json=valid_export()).json()["id"]
    tpl = client.get(f"/custom-strategies/{tid}").json()

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


# ---------------------------------------------------------------------------
# Import — round trip
# ---------------------------------------------------------------------------


def test_export_import_roundtrip(client):
    tid = client.post("/custom-strategies", json=BASE_TEMPLATE).json()["id"]
    exported = client.get(f"/custom-strategies/{tid}/export").json()

    # Re-import the exported document verbatim → a new, equivalent template.
    imported = client.post("/custom-strategies/import", json=exported)
    assert imported.status_code == 200, imported.text
    new = imported.json()

    assert new["id"] != tid  # a distinct record
    assert new["name"] == exported["name"]
    assert new["entry_logic"] == exported["entry_logic"]
    assert new["exit_logic"] == exported["exit_logic"]
    assert len(new["entry_rules"]) == len(exported["entry_rules"])
    assert new["tags"] == exported["tags"]


# ---------------------------------------------------------------------------
# Import — validation / security
# ---------------------------------------------------------------------------


def test_import_rejects_wrong_type(client):
    resp = client.post("/custom-strategies/import", json=valid_export(type="something_else"))
    assert resp.status_code == 422


def test_import_rejects_missing_schema_version(client):
    doc = valid_export()
    doc.pop("schema_version")
    assert client.post("/custom-strategies/import", json=doc).status_code == 422


def test_import_rejects_missing_type(client):
    doc = valid_export()
    doc.pop("type")
    assert client.post("/custom-strategies/import", json=doc).status_code == 422


def test_import_rejects_empty_name(client):
    assert client.post("/custom-strategies/import", json=valid_export(name="")).status_code == 422


def test_import_rejects_invalid_logic(client):
    assert (
        client.post("/custom-strategies/import", json=valid_export(entry_logic="XOR")).status_code
        == 422
    )


def test_import_rejects_unknown_indicator(client):
    bad = valid_export(
        entry_rules=[
            {
                "left": {"type": "indicator", "name": "macd", "params": {"window": 12}},
                "operator": ">",
                "right": {"type": "constant", "value": 0},
            }
        ]
    )
    assert client.post("/custom-strategies/import", json=bad).status_code == 422


def test_import_rejects_invalid_operator(client):
    bad = valid_export(entry_rules=[{**SMA_RULE, "operator": "=="}])
    assert client.post("/custom-strategies/import", json=bad).status_code == 422


def test_import_rejects_too_many_rules(client):
    bad = valid_export(entry_rules=[SMA_RULE for _ in range(11)])
    assert client.post("/custom-strategies/import", json=bad).status_code == 422


def test_import_rejects_string_constant_no_code_execution(client):
    bad = valid_export(
        entry_rules=[
            {
                "left": {"type": "close"},
                "operator": ">",
                "right": {"type": "constant", "value": "__import__('os').system('echo pwned')"},
            }
        ]
    )
    assert client.post("/custom-strategies/import", json=bad).status_code == 422


def test_import_ignores_unknown_envelope_keys(client):
    """Forward-compat: unknown top-level metadata is ignored, not fatal."""
    doc = valid_export(exported_by="someone", future_field={"x": 1})
    resp = client.post("/custom-strategies/import", json=doc)
    assert resp.status_code == 200, resp.text


def test_import_ignores_local_fields_if_present(client):
    """id / timestamps in an uploaded file must not leak into the new record."""
    doc = valid_export(id=999, created_at="2000-01-01T00:00:00Z", updated_at="2000-01-01T00:00:00Z")
    resp = client.post("/custom-strategies/import", json=doc)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] != 999
    assert data["created_at"] != "2000-01-01T00:00:00Z"
