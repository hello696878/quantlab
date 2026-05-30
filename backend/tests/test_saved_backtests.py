"""
Tests for the saved-backtests CRUD layer and API endpoints.

Each test function receives a fresh temporary SQLite database via the
``fresh_db`` autouse fixture — no test writes to ``backend/data/quantlab.db``.
"""

from __future__ import annotations

import sqlite3

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")
db_module = pytest.importorskip("app.db")
sb_module = pytest.importorskip("app.saved_backtests")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """
    Redirect all DB operations to a fresh temporary file for each test.

    The monkeypatch reverts ``_db_path_override`` to None after the test,
    so subsequent tests always start clean.
    """
    db_file = tmp_path / "test_quantlab.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    yield


@pytest.fixture
def client():
    """Return a TestClient for the FastAPI app."""
    return TestClient(main_module.app)


# ---------------------------------------------------------------------------
# Sample payloads
# ---------------------------------------------------------------------------

SAMPLE_METRICS = {
    "total_return": 0.25,
    "cagr": 0.08,
    "sharpe_ratio": 1.2,
    "sortino_ratio": 1.5,
    "max_drawdown": -0.15,
    "volatility": 0.12,
    "calmar_ratio": 0.53,
    "win_rate": 0.55,
    "num_days": 504,
}

SAMPLE_EQUITY = [
    {"date": "2020-01-02", "strategy": 100_000.0, "benchmark": 100_000.0},
    {"date": "2020-01-03", "strategy": 100_500.0, "benchmark": 100_200.0},
]

SAMPLE_TRADES = [
    {"date": "2020-01-02", "action": "BUY",  "price": 320.0, "shares": 312.5, "cost": 3.2},
    {"date": "2020-06-01", "action": "SELL", "price": 310.0, "shares": 312.5, "cost": 3.1},
]

BASE_PAYLOAD: dict = {
    "name": "SPY SMA Test",
    "ticker": "SPY",
    "strategy": "sma_crossover",
    "start_date": "2020-01-01",
    "end_date": "2022-12-31",
    "initial_capital": 100_000.0,
    "transaction_cost_bps": 10.0,
    "params": {"fast_window": 50, "slow_window": 200},
    "metrics": SAMPLE_METRICS,
    "equity_curve": SAMPLE_EQUITY,
    "trades": SAMPLE_TRADES,
    "notes": "Test run",
}


# ---------------------------------------------------------------------------
# 1. Database initialisation
# ---------------------------------------------------------------------------


def test_db_initializes(tmp_path, monkeypatch):
    """init_db() creates the file and the saved_backtests table."""
    db_file = tmp_path / "brand_new.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()

    assert db_file.exists(), "Database file was not created."

    conn = sqlite3.connect(str(db_file))
    tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    conn.close()
    assert "saved_backtests" in tables


def test_init_db_is_idempotent(tmp_path, monkeypatch):
    """Calling init_db() twice does not raise or duplicate the table."""
    db_file = tmp_path / "idempotent.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    db_module.init_db()  # second call — must not raise


def test_tests_use_temp_database_not_real_database():
    """The autouse fixture redirects DB access away from backend/data/quantlab.db."""
    active_path = db_module.get_db_path()
    default_path = db_module._DATA_DIR / "quantlab.db"

    assert active_path != default_path
    assert active_path.name == "test_quantlab.db"
    assert active_path.exists()


# ---------------------------------------------------------------------------
# 2. Create
# ---------------------------------------------------------------------------


def test_create_saved_backtest(client):
    """POST /saved-backtests returns 200 with assigned id and correct fields."""
    resp = client.post("/saved-backtests", json=BASE_PAYLOAD)
    assert resp.status_code == 200, resp.text

    data = resp.json()
    assert data["id"] >= 1
    assert data["name"] == "SPY SMA Test"
    assert data["ticker"] == "SPY"
    assert data["strategy"] == "sma_crossover"
    assert data["start_date"] == "2020-01-01"
    assert data["end_date"] == "2022-12-31"
    assert data["initial_capital"] == pytest.approx(100_000.0)
    assert data["transaction_cost_bps"] == pytest.approx(10.0)
    assert data["cagr"] == pytest.approx(0.08, abs=1e-6)
    assert data["sharpe_ratio"] == pytest.approx(1.2, abs=1e-4)
    assert data["max_drawdown"] == pytest.approx(-0.15, abs=1e-6)
    assert "created_at" in data
    assert data["params"] == {"fast_window": 50, "slow_window": 200}
    assert len(data["equity_curve"]) == 2
    assert len(data["trades"]) == 2
    assert data["notes"] == "Test run"


def test_create_empty_notes(client):
    """notes defaults to an empty string when omitted."""
    payload = {k: v for k, v in BASE_PAYLOAD.items() if k != "notes"}
    resp = client.post("/saved-backtests", json=payload)
    assert resp.status_code == 200
    assert resp.json()["notes"] == ""


# ---------------------------------------------------------------------------
# 3. List
# ---------------------------------------------------------------------------


def test_list_empty(client):
    """GET /saved-backtests returns [] when no records exist."""
    resp = client.get("/saved-backtests")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_returns_summaries(client):
    """List endpoint returns summary rows (no equity_curve / params blobs)."""
    client.post("/saved-backtests", json=BASE_PAYLOAD)
    resp = client.get("/saved-backtests")
    assert resp.status_code == 200

    rows = resp.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "SPY SMA Test"
    assert "equity_curve" not in row
    assert "params" not in row
    assert "metrics" not in row
    assert "trades" not in row
    assert row["cagr"] == pytest.approx(0.08, abs=1e-6)


def test_list_ordered_newest_first(client):
    """Multiple records are returned newest-first."""
    client.post("/saved-backtests", json=BASE_PAYLOAD)
    client.post("/saved-backtests", json={**BASE_PAYLOAD, "name": "Second Run"})

    rows = client.get("/saved-backtests").json()
    assert len(rows) == 2
    assert rows[0]["name"] == "Second Run"
    assert rows[1]["name"] == "SPY SMA Test"


# ---------------------------------------------------------------------------
# 4. Get by id
# ---------------------------------------------------------------------------


def test_get_saved_backtest(client):
    """GET /saved-backtests/{id} returns the full record."""
    item_id = client.post("/saved-backtests", json=BASE_PAYLOAD).json()["id"]

    resp = client.get(f"/saved-backtests/{item_id}")
    assert resp.status_code == 200

    data = resp.json()
    assert data["id"] == item_id
    assert data["name"] == "SPY SMA Test"
    assert len(data["equity_curve"]) == 2
    assert len(data["trades"]) == 2
    assert data["params"] == {"fast_window": 50, "slow_window": 200}
    assert data["metrics"]["sharpe_ratio"] == pytest.approx(1.2, abs=1e-4)


def test_get_missing_id_returns_404(client):
    """GET /saved-backtests/999 returns 404 when record does not exist."""
    resp = client.get("/saved-backtests/999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 5. Delete
# ---------------------------------------------------------------------------


def test_delete_saved_backtest(client):
    """DELETE /saved-backtests/{id} removes the record."""
    item_id = client.post("/saved-backtests", json=BASE_PAYLOAD).json()["id"]

    del_resp = client.delete(f"/saved-backtests/{item_id}")
    assert del_resp.status_code == 200
    assert del_resp.json() == {"deleted": True, "id": item_id}

    # Confirm gone
    assert client.get(f"/saved-backtests/{item_id}").status_code == 404


def test_delete_missing_id_returns_404(client):
    """DELETE /saved-backtests/999 returns 404 when record does not exist."""
    resp = client.delete("/saved-backtests/999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 6. Validation (422 cases)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "override,description",
    [
        ({"name": ""},           "empty name"),
        ({"name": "   "},        "blank name"),
        ({"ticker": ""},         "empty ticker"),
        ({"ticker": "   "},      "blank ticker"),
        ({"strategy": ""},       "empty strategy"),
        ({"strategy": "   "},    "blank strategy"),
        ({"initial_capital": 0}, "capital = 0"),
        ({"initial_capital": -1000}, "negative capital"),
        ({"transaction_cost_bps": -1}, "negative cost bps"),
        ({"start_date": "not-a-date"}, "invalid start date"),
        ({"end_date": "not-a-date"}, "invalid end date"),
        ({"start_date": "2025-01-01", "end_date": "2020-01-01"}, "start >= end"),
        ({"start_date": "2020-01-01", "end_date": "2020-01-01"}, "start == end"),
    ],
)
def test_invalid_request_returns_422(client, override, description):
    payload = {**BASE_PAYLOAD, **override}
    resp = client.post("/saved-backtests", json=payload)
    assert resp.status_code == 422, f"Expected 422 for: {description}"


# ---------------------------------------------------------------------------
# 7. JSON round-trip
# ---------------------------------------------------------------------------


def test_json_fields_roundtrip(client):
    """equity_curve and trades survive a write → read cycle exactly."""
    item_id = client.post("/saved-backtests", json=BASE_PAYLOAD).json()["id"]
    data = client.get(f"/saved-backtests/{item_id}").json()

    ec = data["equity_curve"]
    assert ec[0]["date"] == "2020-01-02"
    assert ec[0]["strategy"] == pytest.approx(100_000.0)
    assert ec[1]["strategy"] == pytest.approx(100_500.0)

    tr = data["trades"]
    assert tr[0]["action"] == "BUY"
    assert tr[0]["price"] == pytest.approx(320.0)
    assert tr[1]["action"] == "SELL"


def test_metrics_roundtrip(client):
    """All metrics keys survive the write → read cycle."""
    item_id = client.post("/saved-backtests", json=BASE_PAYLOAD).json()["id"]
    stored = client.get(f"/saved-backtests/{item_id}").json()["metrics"]

    for key, value in SAMPLE_METRICS.items():
        assert stored[key] == pytest.approx(value, abs=1e-6), f"Mismatch on {key}"


def test_params_roundtrip(client):
    """Strategy params survive the write → read cycle."""
    item_id = client.post("/saved-backtests", json=BASE_PAYLOAD).json()["id"]
    assert client.get(f"/saved-backtests/{item_id}").json()["params"] == {
        "fast_window": 50,
        "slow_window": 200,
    }


# ---------------------------------------------------------------------------
# 8. Notes field
# ---------------------------------------------------------------------------


def test_notes_stored_and_returned(client):
    """notes are persisted and appear in both detail and list views."""
    payload = {**BASE_PAYLOAD, "notes": "Great result — consider deploying."}
    item_id = client.post("/saved-backtests", json=payload).json()["id"]

    detail = client.get(f"/saved-backtests/{item_id}").json()
    assert detail["notes"] == "Great result — consider deploying."

    summary = client.get("/saved-backtests").json()[0]
    assert summary["notes"] == "Great result — consider deploying."
