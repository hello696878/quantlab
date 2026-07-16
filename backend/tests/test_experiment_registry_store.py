"""
Persistence + repository tests for the Research Experiment Registry (Phase 48.0).

Uses a fresh temporary SQLite database per test (never the real
``backend/data/quantlab.db``).  Covers schema creation on fresh + pre-existing
databases, CRUD, pagination, filtering, baseline scope, parent relationships,
demo-fixture idempotence, and delete.
"""

from __future__ import annotations

import sqlite3

import pytest

db_module = pytest.importorskip("app.db")
store = pytest.importorskip("app.experiment_registry.store")
service = pytest.importorskip("app.experiment_registry.service")
demo = pytest.importorskip("app.experiment_registry.demo")


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_quantlab.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    yield


def _make(**over):
    payload = {
        "name": "Run",
        "module": "scenario_studio",
        "experiment_type": "stress",
        "status": "completed",
        "parameters": {"a": 1},
        "metrics": {"sharpe": 1.0},
        "tags": ["demo"],
        "dataset_name": "fx",
    }
    payload.update(over)
    return service.create_experiment(payload, source="test")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def test_fresh_db_creates_registry_table(tmp_path, monkeypatch):
    db_file = tmp_path / "fresh.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    conn = sqlite3.connect(str(db_file))
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='experiment_registry'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None


def test_init_db_is_idempotent_and_preserves_rows():
    rec = _make(name="Persisted")
    # Re-running init_db must not drop or alter existing rows.
    db_module.init_db()
    again = store.get_experiment(rec["id"])
    assert again is not None
    assert again["name"] == "Persisted"


def test_existing_database_upgrade_preserves_saved_reports(tmp_path, monkeypatch):
    # Simulate a pre-existing DB with only the older saved_reports table, then
    # upgrade via init_db and confirm nothing is lost.
    db_file = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        "CREATE TABLE saved_reports (id INTEGER PRIMARY KEY, title TEXT)"
    )
    conn.execute("INSERT INTO saved_reports (title) VALUES ('legacy report')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()  # must not raise, must add the new table

    conn = sqlite3.connect(str(db_file))
    try:
        assert conn.execute("SELECT COUNT(*) FROM saved_reports").fetchone()[0] == 1
        assert (
            conn.execute(
                "SELECT name FROM sqlite_master WHERE name='experiment_registry'"
            ).fetchone()
            is not None
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CRUD + read
# ---------------------------------------------------------------------------


def test_insert_and_get():
    rec = _make(name="Alpha")
    assert rec["id"] >= 1
    fetched = store.get_experiment(rec["id"])
    assert fetched["name"] == "Alpha"
    assert fetched["configuration_fingerprint"]
    assert fetched["result_fingerprint"]  # metrics present -> result fp
    assert fetched["parameters"] == {"a": 1}
    assert fetched["tags"] == ["demo"]


def test_get_missing_returns_none():
    assert store.get_experiment(999) is None


def test_update_mutable_columns():
    rec = _make()
    updated = store.update_columns(rec["id"], {"name": "Renamed", "notes": "hi"})
    assert updated["name"] == "Renamed"
    assert updated["notes"] == "hi"
    assert updated["updated_at"] >= rec["updated_at"]


def test_delete():
    rec = _make()
    assert store.delete_experiment(rec["id"]) is True
    assert store.get_experiment(rec["id"]) is None
    assert store.delete_experiment(rec["id"]) is False


# ---------------------------------------------------------------------------
# Filtering + pagination
# ---------------------------------------------------------------------------


def test_filter_by_module_and_status():
    _make(module="a", status="completed", name="c1")
    _make(module="a", status="failed", error_message="x", metrics={}, name="f1")
    _make(module="b", status="completed", name="c2")
    res = store.list_experiments(filters={"module": "a"})
    assert res["total"] == 2
    res2 = store.list_experiments(filters={"module": "a", "status": "failed"})
    assert res2["total"] == 1
    assert res2["items"][0]["name"] == "f1"


def test_filter_by_tag_and_query():
    _make(name="Alpha find me", tags=["x", "special"])
    _make(name="Beta", tags=["y"])
    by_tag = store.list_experiments(filters={"tag": "special"})
    assert by_tag["total"] == 1
    by_query = store.list_experiments(filters={"query": "find me"})
    assert by_query["total"] == 1


def test_pagination_and_total():
    for i in range(7):
        _make(name=f"R{i}")
    page1 = store.list_experiments(page=1, page_size=3)
    assert page1["total"] == 7
    assert len(page1["items"]) == 3
    assert page1["total_pages"] == 3
    page3 = store.list_experiments(page=3, page_size=3)
    assert len(page3["items"]) == 1


def test_page_size_is_bounded():
    _make()
    res = store.list_experiments(page_size=99999)
    assert res["page_size"] <= store.MAX_PAGE_SIZE


def test_sort_is_stable_and_whitelisted():
    a = _make(name="A")
    b = _make(name="B")
    asc = store.list_experiments(sort_by="name", sort_dir="asc")["items"]
    assert [x["name"] for x in asc[:2]] == ["A", "B"]
    # An unknown sort column falls back to created_at (no SQL error).
    res = store.list_experiments(sort_by="; DROP TABLE experiment_registry;--")
    assert res["total"] >= 2
    assert store.get_experiment(a["id"]) is not None  # table intact
    assert store.get_experiment(b["id"]) is not None


# ---------------------------------------------------------------------------
# Baseline scope
# ---------------------------------------------------------------------------


def test_first_baseline_sets_flag():
    rec = _make()
    updated = store.mark_baseline(rec["id"])
    assert updated["is_baseline"] is True


def test_baseline_replacement_within_same_scope():
    a = _make(module="m", experiment_type="t", dataset_name="d")
    b = _make(module="m", experiment_type="t", dataset_name="d")
    store.mark_baseline(a["id"])
    store.mark_baseline(b["id"])
    assert store.get_experiment(a["id"])["is_baseline"] is False
    assert store.get_experiment(b["id"])["is_baseline"] is True


def test_baseline_in_other_scope_is_unchanged():
    a = _make(module="m", experiment_type="t", dataset_name="d1")
    b = _make(module="m", experiment_type="t", dataset_name="d2")  # different dataset scope
    store.mark_baseline(a["id"])
    store.mark_baseline(b["id"])
    # Different dataset identity => both remain baselines in their own scope.
    assert store.get_experiment(a["id"])["is_baseline"] is True
    assert store.get_experiment(b["id"])["is_baseline"] is True


def test_find_baseline_in_scope():
    a = _make(module="m", experiment_type="t", dataset_name="d")
    store.mark_baseline(a["id"])
    found = store.find_baseline_in_scope(
        module="m", experiment_type="t", dataset_fingerprint=None, dataset_name="d"
    )
    assert found is not None and found["id"] == a["id"]
    none = store.find_baseline_in_scope(
        module="other", experiment_type="t", dataset_fingerprint=None, dataset_name="d"
    )
    assert none is None


# ---------------------------------------------------------------------------
# Summary + facets
# ---------------------------------------------------------------------------


def test_summary_counts_and_facets():
    _make(module="a", status="completed")
    _make(module="b", status="failed", error_message="x", metrics={})
    summary = store.summary_counts()
    assert summary["total"] == 2
    assert summary["by_status"]["completed"] == 1
    assert summary["by_status"]["failed"] == 1
    assert summary["modules_represented"] == 2
    facets = store.distinct_values()
    assert set(facets["modules"]) == {"a", "b"}


# ---------------------------------------------------------------------------
# Demo fixtures
# ---------------------------------------------------------------------------


def test_demo_seed_idempotent():
    first = demo.seed_demo_registry()
    assert first["created"] == len(demo.DEMO_SPECS)
    assert first["skipped"] == 0
    second = demo.seed_demo_registry()
    assert second["created"] == 0
    assert second["skipped"] == len(demo.DEMO_SPECS)
    # Total records equals the number of demo specs — no duplicates.
    assert store.summary_counts()["total"] == len(demo.DEMO_SPECS)


def test_demo_seed_does_not_delete_user_records():
    user = _make(name="User record")
    demo.seed_demo_registry()
    demo.seed_demo_registry()
    assert store.get_experiment(user["id"]) is not None
    # User record has no demo_key, so it is never touched by seeding.
