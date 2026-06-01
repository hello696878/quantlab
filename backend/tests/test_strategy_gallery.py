"""
Tests for the built-in Strategy Template Gallery.

Covers GET /custom-strategy-gallery and GET /custom-strategy-gallery/{id},
plus structural / security guarantees for every built-in template.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")
db_module = pytest.importorskip("app.db")
gallery_module = pytest.importorskip("app.strategy_gallery")
schemas = pytest.importorskip("app.schemas")
custom_strategy = pytest.importorskip("app.custom_strategy")


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_quantlab.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    yield


@pytest.fixture
def client():
    return TestClient(main_module.app)


EXPECTED_TEMPLATES = [
    ("sma-trend-filter", "SMA Trend Filter"),
    ("rsi-mean-reversion", "RSI Mean Reversion"),
    ("momentum-trend", "Momentum + Trend"),
    ("bollinger-mean-reversion", "Bollinger Mean Reversion"),
    ("defensive-trend", "Defensive Trend Strategy"),
]
EXPECTED_IDS = {template_id for template_id, _name in EXPECTED_TEMPLATES}


# ---------------------------------------------------------------------------
# List endpoint
# ---------------------------------------------------------------------------


def test_gallery_list_returns_templates(client):
    resp = client.get("/custom-strategy-gallery")
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert [(r["id"], r["name"]) for r in rows] == EXPECTED_TEMPLATES


def test_gallery_items_have_all_fields(client):
    rows = client.get("/custom-strategy-gallery").json()
    required = {
        "id", "name", "description", "entry_logic", "exit_logic",
        "entry_rules", "exit_rules", "tags", "difficulty", "category",
    }
    for r in rows:
        assert required.issubset(r.keys()), r["id"]
        assert r["difficulty"] in {"beginner", "intermediate", "advanced"}
        assert r["category"] in {"trend", "mean_reversion", "momentum"}


def test_every_template_has_entry_and_exit_rules(client):
    for r in client.get("/custom-strategy-gallery").json():
        assert len(r["entry_rules"]) >= 1, r["id"]
        assert len(r["exit_rules"]) >= 1, r["id"]


def test_gallery_accessors_return_defensive_copies():
    first = gallery_module.list_gallery()[0]
    first.name = "Mutated"
    first.entry_rules.clear()

    fresh = gallery_module.get_gallery_template("sma-trend-filter")
    assert fresh is not None
    assert fresh.name == "SMA Trend Filter"
    assert len(fresh.entry_rules) == 1


# ---------------------------------------------------------------------------
# Single-template endpoint
# ---------------------------------------------------------------------------


def test_gallery_get_one(client):
    resp = client.get("/custom-strategy-gallery/sma-trend-filter")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == "sma-trend-filter"
    assert data["entry_rules"][0]["left"]["name"] == "sma"
    assert data["category"] == "trend"


def test_gallery_get_missing_returns_404(client):
    assert client.get("/custom-strategy-gallery/does-not-exist").status_code == 404


# ---------------------------------------------------------------------------
# Validation / security
# ---------------------------------------------------------------------------


def test_every_template_validates_under_builder_schema():
    """Each gallery template's rules validate under the live CustomRule schema."""
    for tpl in gallery_module.list_gallery():
        # Constructing CustomStrategyRequest re-validates the rules with the
        # exact same whitelisted schema used by POST /backtest/custom.
        schemas.CustomStrategyRequest(
            ticker="SPY",
            start_date="2015-01-01",
            end_date="2023-12-31",
            entry_rules=[r.model_dump() for r in tpl.entry_rules],
            entry_logic="all" if tpl.entry_logic == "AND" else "any",
            exit_rules=[r.model_dump() for r in tpl.exit_rules],
            exit_logic="all" if tpl.exit_logic == "AND" else "any",
        )


def test_every_template_generates_signals_on_deterministic_data():
    """Each template produces a valid 0/1 position series on synthetic prices."""
    vals = [100.0 + 25.0 * math.sin(i / 25.0) + i * 0.1 for i in range(400)]
    close = pd.Series(
        vals, index=pd.date_range("2018-01-01", periods=400, freq="B"), name="Close"
    )
    for tpl in gallery_module.list_gallery():
        pos = custom_strategy.custom_strategy_signals(
            close,
            entry_rules=tpl.entry_rules,
            entry_logic="all" if tpl.entry_logic == "AND" else "any",
            exit_rules=tpl.exit_rules,
            exit_logic="all" if tpl.exit_logic == "AND" else "any",
        )
        assert len(pos) == len(close)
        assert set(pos.unique()).issubset({0, 1}), tpl.id
        assert pos.iloc[0] == 0  # one-bar shift → no lookahead


# ---------------------------------------------------------------------------
# Loadable shape == saved template shape
# ---------------------------------------------------------------------------


def test_gallery_template_is_savable(client):
    """Every gallery template's fields are accepted by POST /custom-strategies."""
    for g in client.get("/custom-strategy-gallery").json():
        payload = {
            "name": g["name"],
            "description": g["description"],
            "entry_logic": g["entry_logic"],
            "exit_logic": g["exit_logic"],
            "entry_rules": g["entry_rules"],
            "exit_rules": g["exit_rules"],
            "tags": g["tags"],
        }
        resp = client.post("/custom-strategies", json=payload)
        assert resp.status_code == 200, resp.text
        saved = resp.json()
        assert saved["name"] == g["name"]
        assert len(saved["entry_rules"]) == len(g["entry_rules"])


def test_gallery_template_runs_via_backtest(client, monkeypatch):
    """Every gallery template can run end-to-end through /backtest/custom."""

    def fake_df(*_a, **_k):
        vals = [100.0 + 25.0 * math.sin(i / 25.0) + i * 0.1 for i in range(400)]
        return pd.DataFrame(
            {"Close": vals},
            index=pd.date_range("2018-01-01", periods=400, freq="B"),
        )

    monkeypatch.setattr(main_module, "_fetch", fake_df)

    for g in client.get("/custom-strategy-gallery").json():
        run_req = {
            "ticker": "SPY",
            "start_date": "2018-01-01",
            "end_date": "2021-01-01",
            "transaction_cost_bps": 10,
            "initial_capital": 100000,
            "entry_rules": g["entry_rules"],
            "entry_logic": "all" if g["entry_logic"] == "AND" else "any",
            "exit_rules": g["exit_rules"],
            "exit_logic": "all" if g["exit_logic"] == "AND" else "any",
        }
        resp = client.post("/backtest/custom", json=run_req)
        assert resp.status_code == 200, f"{g['id']}: {resp.text}"
        assert resp.json()["strategy"] == "custom"
