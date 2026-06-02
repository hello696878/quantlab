"""
Tests for the saved-reports CRUD layer and API endpoints (Report Gallery).

Each test receives a fresh temporary SQLite database via the ``fresh_db``
autouse fixture — no test writes to ``backend/data/quantlab.db``.
"""

from __future__ import annotations

import sqlite3

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")
db_module = pytest.importorskip("app.db")
sr_module = pytest.importorskip("app.saved_reports")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Redirect all DB operations to a fresh temporary file for each test."""
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

MARKDOWN = (
    "# QuantLab Research Report\n\n"
    "## Metadata\n\n"
    "| Field | Value |\n| --- | --- |\n| Ticker | BTC-USD |\n\n"
    "## Risk / Caveats\n\n- Historical backtest only.\n"
)

BASE_PAYLOAD: dict = {
    "title": "BTC Momentum Report",
    "report_type": "markdown",
    "source_type": "backtest",
    "source_id": None,
    "tickers": ["BTC-USD"],
    "strategy": "momentum",
    "date_range_start": "2015-01-01",
    "date_range_end": "2023-12-31",
    "markdown_content": MARKDOWN,
    "metadata": {"total_return": 1.23, "sharpe_ratio": 0.95, "nested": {"a": [1, 2]}},
    "notes": "First saved report",
}


# ---------------------------------------------------------------------------
# 1. Database initialisation
# ---------------------------------------------------------------------------


def test_db_initializes_saved_reports_table(tmp_path, monkeypatch):
    """init_db() creates the saved_reports table."""
    db_file = tmp_path / "brand_new.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()

    assert db_file.exists()
    conn = sqlite3.connect(str(db_file))
    tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    conn.close()
    assert "saved_reports" in tables


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


def test_create_saved_report(client):
    resp = client.post("/saved-reports", json=BASE_PAYLOAD)
    assert resp.status_code == 200, resp.text

    data = resp.json()
    assert data["id"] >= 1
    assert data["title"] == "BTC Momentum Report"
    assert data["report_type"] == "markdown"
    assert data["source_type"] == "backtest"
    assert data["source_id"] is None
    assert data["tickers"] == ["BTC-USD"]
    assert data["strategy"] == "momentum"
    assert data["date_range_start"] == "2015-01-01"
    assert data["date_range_end"] == "2023-12-31"
    assert data["markdown_content"] == MARKDOWN
    assert data["notes"] == "First saved report"
    assert "created_at" in data and "updated_at" in data
    assert data["created_at"] == data["updated_at"]


def test_create_defaults_optional_fields(client):
    """Optional fields default cleanly when omitted."""
    payload = {
        "title": "Minimal",
        "report_type": "markdown",
        "source_type": "manual",
        "markdown_content": "# Hello\n",
    }
    resp = client.post("/saved-reports", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["tickers"] == []
    assert data["strategy"] is None
    assert data["date_range_start"] is None
    assert data["date_range_end"] is None
    assert data["metadata"] == {}
    assert data["notes"] == ""


# ---------------------------------------------------------------------------
# 3. List
# ---------------------------------------------------------------------------


def test_list_empty(client):
    resp = client.get("/saved-reports")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_returns_summaries_without_markdown(client):
    client.post("/saved-reports", json=BASE_PAYLOAD)
    resp = client.get("/saved-reports")
    assert resp.status_code == 200

    rows = resp.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["title"] == "BTC Momentum Report"
    assert row["tickers"] == ["BTC-USD"]
    # Summary rows omit the large content blob + metadata.
    assert "markdown_content" not in row
    assert "metadata" not in row


def test_list_ordered_newest_first(client):
    client.post("/saved-reports", json=BASE_PAYLOAD)
    client.post("/saved-reports", json={**BASE_PAYLOAD, "title": "Second Report"})

    rows = client.get("/saved-reports").json()
    assert len(rows) == 2
    assert rows[0]["title"] == "Second Report"
    assert rows[1]["title"] == "BTC Momentum Report"


# ---------------------------------------------------------------------------
# 4. Get by id
# ---------------------------------------------------------------------------


def test_get_saved_report(client):
    item_id = client.post("/saved-reports", json=BASE_PAYLOAD).json()["id"]
    resp = client.get(f"/saved-reports/{item_id}")
    assert resp.status_code == 200

    data = resp.json()
    assert data["id"] == item_id
    assert data["markdown_content"] == MARKDOWN
    assert data["metadata"]["total_return"] == pytest.approx(1.23)


def test_get_missing_id_returns_404(client):
    assert client.get("/saved-reports/999").status_code == 404


# ---------------------------------------------------------------------------
# 5. Update
# ---------------------------------------------------------------------------


def test_update_saved_report(client):
    item_id = client.post("/saved-reports", json=BASE_PAYLOAD).json()["id"]

    resp = client.put(
        f"/saved-reports/{item_id}",
        json={
            "title": "Renamed Report",
            "notes": "Reviewed and approved",
            "metadata": {"reviewed": True},
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["title"] == "Renamed Report"
    assert data["notes"] == "Reviewed and approved"
    assert data["metadata"] == {"reviewed": True}
    # Immutable fields preserved; content untouched.
    assert data["markdown_content"] == MARKDOWN
    assert data["source_type"] == "backtest"
    # updated_at advances past created_at.
    assert data["updated_at"] >= data["created_at"]


def test_update_missing_id_returns_404(client):
    resp = client.put(
        "/saved-reports/999",
        json={"title": "Nope", "notes": "", "metadata": {}},
    )
    assert resp.status_code == 404


def test_update_blank_title_rejected(client):
    item_id = client.post("/saved-reports", json=BASE_PAYLOAD).json()["id"]
    resp = client.put(
        f"/saved-reports/{item_id}",
        json={"title": "   ", "notes": "", "metadata": {}},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 6. Delete
# ---------------------------------------------------------------------------


def test_delete_saved_report(client):
    item_id = client.post("/saved-reports", json=BASE_PAYLOAD).json()["id"]

    del_resp = client.delete(f"/saved-reports/{item_id}")
    assert del_resp.status_code == 200
    assert del_resp.json() == {"deleted": True, "id": item_id}

    assert client.get(f"/saved-reports/{item_id}").status_code == 404


def test_delete_missing_id_returns_404(client):
    assert client.delete("/saved-reports/999").status_code == 404


# ---------------------------------------------------------------------------
# 7. Validation (422 cases)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "override,description",
    [
        ({"title": ""}, "empty title"),
        ({"title": "   "}, "blank title"),
        ({"report_type": ""}, "empty report_type"),
        ({"report_type": "   "}, "blank report_type"),
        ({"markdown_content": ""}, "empty markdown_content"),
        ({"markdown_content": "   \n  "}, "blank markdown_content"),
        ({"source_type": "not_a_real_source"}, "invalid source_type"),
        ({"date_range_start": "not-a-date"}, "invalid start date"),
        ({"date_range_end": "not-a-date"}, "invalid end date"),
        (
            {"date_range_start": "2023-01-01", "date_range_end": "2015-01-01"},
            "start >= end",
        ),
        (
            {"date_range_start": "2020-01-01", "date_range_end": "2020-01-01"},
            "start == end",
        ),
    ],
)
def test_invalid_request_returns_422(client, override, description):
    payload = {**BASE_PAYLOAD, **override}
    resp = client.post("/saved-reports", json=payload)
    assert resp.status_code == 422, f"Expected 422 for: {description}"


def test_one_sided_date_is_allowed(client):
    """A single date (start OR end) is permitted; only ordering is checked."""
    payload = {**BASE_PAYLOAD, "date_range_start": "2015-01-01", "date_range_end": None}
    resp = client.post("/saved-reports", json=payload)
    assert resp.status_code == 200, resp.text
    assert resp.json()["date_range_end"] is None


# ---------------------------------------------------------------------------
# 8. JSON round-trips
# ---------------------------------------------------------------------------


def test_metadata_roundtrip(client):
    """Nested metadata survives the write → read cycle exactly."""
    item_id = client.post("/saved-reports", json=BASE_PAYLOAD).json()["id"]
    stored = client.get(f"/saved-reports/{item_id}").json()["metadata"]
    assert stored == BASE_PAYLOAD["metadata"]
    assert stored["nested"] == {"a": [1, 2]}


def test_tickers_roundtrip(client):
    payload = {**BASE_PAYLOAD, "tickers": ["SPY", "QQQ", "GLD", "TLT"]}
    item_id = client.post("/saved-reports", json=payload).json()["id"]
    assert client.get(f"/saved-reports/{item_id}").json()["tickers"] == [
        "SPY",
        "QQQ",
        "GLD",
        "TLT",
    ]


def test_markdown_content_preserved_with_whitespace(client):
    """Leading/internal whitespace inside (non-blank) markdown is preserved."""
    md = "# Title\n\n   indented line\n\n## Section\n"
    payload = {**BASE_PAYLOAD, "markdown_content": md}
    item_id = client.post("/saved-reports", json=payload).json()["id"]
    assert client.get(f"/saved-reports/{item_id}").json()["markdown_content"] == md


# ---------------------------------------------------------------------------
# 9. Direct CRUD module (no HTTP layer)
# ---------------------------------------------------------------------------


def test_crud_module_create_and_get():
    created = sr_module.create_saved_report(BASE_PAYLOAD)
    fetched = sr_module.get_saved_report(created["id"])
    assert fetched is not None
    assert fetched["title"] == "BTC Momentum Report"
    assert fetched["markdown_content"] == MARKDOWN


def test_crud_module_update_returns_none_for_missing():
    assert sr_module.update_saved_report(
        12345, {"title": "x", "notes": "", "metadata": {}}
    ) is None


def test_crud_module_delete_returns_false_for_missing():
    assert sr_module.delete_saved_report(12345) is False
