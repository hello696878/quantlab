"""Owned-storage adversarial controls for the read-only evidence adapter."""
from contextlib import closing
import copy
import hashlib
import json
import sqlite3

import pytest

from app import db, saved_backtests
from app.research_explainer import service as explainer
from app.run_replay import identity, service as replay, store
from .test_research_explainer_storage import payload, forbid, spies

pytestmark = pytest.mark.usefixtures("isolated_lab_db")


def inventory(path):
    return {p.name: (p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest())
            for p in path.parent.iterdir() if p.is_file()}


@pytest.mark.parametrize("state", ["closed_wal", "committed_wal", "rollback_journal"])
def test_unsupported_journal_state_refused_before_connect_without_file_effects(monkeypatch, state):
    saved = saved_backtests.create_saved_backtest(payload())
    path = db.get_db_path()
    writer = sqlite3.connect(path)
    try:
        if state in {"closed_wal", "committed_wal"}:
            assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
            writer.execute("UPDATE saved_backtests SET metrics_json=? WHERE id=?", ('{"total_return":0.75}', saved["id"]))
            writer.commit()
            if state == "closed_wal":
                writer.close()
                assert not path.with_name(path.name + "-wal").exists()
            else:
                assert path.with_name(path.name + "-wal").stat().st_size > 0
                assert writer.execute("SELECT metrics_json FROM saved_backtests WHERE id=?", (saved["id"],)).fetchone()[0] == '{"total_return":0.75}'
        else:
            writer.execute("BEGIN IMMEDIATE")
            writer.execute("UPDATE saved_backtests SET metrics_json='{}' WHERE id=?", (saved["id"],))
            assert path.with_name(path.name + "-journal").exists()
        before = inventory(path)
        monkeypatch.setattr(sqlite3, "connect", forbid)
        with pytest.raises(explainer.Unavailable, match="storage mode|journal state"):
            explainer.explain(saved["id"])
        assert inventory(path) == before
    finally:
        writer.close()


@pytest.mark.parametrize("extra", [
    {"units": {"total_return": "percent"}}, {"total_return_available": False},
    {"total_return_quality": "invalid"}, {"arbitrary_metric": 12},
])
def test_unsupported_metric_metadata_is_not_silently_discarded(extra):
    data = payload()
    data["metrics"].update(extra)
    saved = saved_backtests.create_saved_backtest(data)
    with pytest.raises(explainer.Unavailable, match="quality flags"):
        explainer.explain(saved["id"])


@pytest.mark.parametrize("extra", [{"total_return_available": False}, {"total_return_units": "percent"}, {"metric_units": {"total_return": "percent"}}])
def test_metric_specific_params_metadata_is_not_silently_discarded(extra):
    data = payload()
    data["params"].update(extra)
    saved = saved_backtests.create_saved_backtest(data)
    with pytest.raises(explainer.Unavailable, match="quality flags"):
        explainer.explain(saved["id"])


def test_existing_saved_sma_cost_annualization_and_provider_metadata_remains_supported():
    data = payload()
    data["params"].update(cost_model={"type": "simple_bps", "effective_bps_per_side": 10}, effective_cost_bps=10,
        total_transaction_cost=12.5, cost_drag_return=.0001, annualization_mode="auto", annualization_mode_used="equity_252",
        periods_per_year=252, annualization_warning=None, data_provider="yfinance", data_quality={"row_count": 252}, position_mode="long_only")
    saved = saved_backtests.create_saved_backtest(data)
    assert explainer.explain(saved["id"])["identity"]["trust"] == "legacy_unverified"


@pytest.mark.parametrize("column", ["start_date", "end_date", "config_schema", "config_hash_full"])
def test_every_selected_text_column_is_bounded_before_full_decode(monkeypatch, column):
    saved = saved_backtests.create_saved_backtest(payload())
    with closing(db.get_connection()) as conn, conn:
        conn.execute("UPDATE saved_backtests SET " + column + "=? WHERE id=?", ("x" * (4 * 1024 * 1024 + 1), saved["id"]))
    monkeypatch.setattr(identity, "loads", forbid)
    with pytest.raises(explainer.Unavailable, match="bounds"):
        explainer.acquire(saved["id"])


@pytest.mark.parametrize("raw", [
    "[" * 22 + "0" + "]" * 22,
    "[" + ",".join("0" for _ in range(100001)) + "]",
    "[" + ",".join("[" + ",".join("0" for _ in range(75000)) + "]" for _ in range(4)) + "]",
], ids=["depth", "array_entries", "total_tokens"])
def test_json_structure_bounds_precede_full_decoder(monkeypatch, raw):
    saved = saved_backtests.create_saved_backtest(payload())
    with closing(db.get_connection()) as conn, conn:
        conn.execute("UPDATE saved_backtests SET equity_curve_json=? WHERE id=?", (raw, saved["id"]))
    monkeypatch.setattr(identity, "loads", forbid)
    with pytest.raises(explainer.Unavailable, match="invalid or unsupported"):
        explainer.acquire(saved["id"])


@pytest.mark.db_free
@pytest.mark.parametrize("raw", ['{"escaped":"\\\"[{}]\\\\", "value":[1,true,null]}', '[]', '{}', '{"x":' + "[" * 19 + "0" + "]" * 19 + '}'])
def test_lexical_preflight_accepts_valid_escaped_and_bounded_json(raw):
    explainer._json_preflight(raw)
    assert identity.loads(raw) == json.loads(raw)


def registered_saved():
    from app.run_replay.adapter import normalize, request_model
    from app.reproducibility import build_reproducibility
    cfg = normalize(request_model({"ticker": "SPY", "start_date": "2020-01-01", "end_date": "2021-01-01"}), "yfinance")
    data = payload()
    data["params"] = {"reproducibility": build_reproducibility(cfg).model_dump(mode="json")}
    saved = saved_backtests.create_saved_backtest(data)
    replay.register_legacy(saved["id"])
    return saved_backtests.get_saved_backtest(saved["id"]), store.for_saved(saved["id"])


def test_supplied_snapshot_cannot_bind_another_id_even_with_coherent_rehashed_execution():
    saved, context = registered_saved()
    alternate = copy.deepcopy(saved)
    alternate["id"] += 1
    snap = identity.loads(context["snapshot_json"])
    # Keep the snapshot/index saved ID unchanged but coherently rehash execution
    # for the supplied different record. Missing direct ID binding accepted this.
    snap["execution_hash"] = identity.digest({"schema_version": "saved_execution_v1", "saved_backtest_id": alternate["id"],
        "created_at": alternate["created_at"], "result_hash": snap["result_hash"], "input_hash": snap["input_hash"],
        "environment_hash": snap["environment_hash"]})
    context.update(snapshot_json=identity.validate(snap), snapshot_hash=identity.digest(snap))
    with pytest.raises(replay.Changed, match="different record"):
        replay.verified(context, check_parent=False, saved_snapshot=alternate)


def test_context_decoder_preflight_and_owned_column_projection(monkeypatch):
    saved, context = registered_saved()
    with closing(db.get_connection()) as conn, conn:
        conn.execute("ALTER TABLE run_replay_contexts ADD COLUMN private_note TEXT")
        conn.execute("UPDATE run_replay_contexts SET private_note=? WHERE id=?", ("SECRET" * 900000, context["id"]))
    spies(monkeypatch)
    # An unselected oversized extension must never be materialized by SELECT *.
    assert explainer.explain(saved["id"])["identity"]["trust"] == "recorded_hashes_match"


def test_context_nested_json_refused_before_any_full_decoder(monkeypatch):
    saved, context = registered_saved()
    with closing(db.get_connection()) as conn, conn:
        conn.execute("UPDATE run_replay_contexts SET snapshot_json=? WHERE id=?", ("[" * 22 + "0" + "]" * 22, context["id"]))
    monkeypatch.setattr(identity, "loads", forbid)
    with pytest.raises(explainer.Changed, match="bounds"):
        explainer.acquire(saved["id"])


def test_reader_keeps_one_transaction_while_competing_writer_cannot_commit(monkeypatch):
    saved = saved_backtests.create_saved_backtest(payload())
    path = db.get_db_path()
    before = inventory(path)
    original_connect = sqlite3.connect
    writer = original_connect(path, timeout=0)
    attempts = []
    blocked = []

    def reader(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        def observe(sql):
            if sql.startswith("SELECT id,created_at,") and not attempts:
                attempts.append(sql)
                writer.execute("UPDATE saved_backtests SET metrics_json='{}' WHERE id=?", (saved["id"],))
                try:
                    writer.commit()
                except sqlite3.OperationalError as exc:
                    blocked.append("locked" in str(exc))
                finally:
                    writer.rollback()
        conn.set_trace_callback(observe)
        return conn

    try:
        monkeypatch.setattr(sqlite3, "connect", reader)
        row, context = explainer.acquire(saved["id"])
        assert attempts and blocked == [True] and row["metrics"]["total_return"] == -.12 and context is None
        assert inventory(path) == before
        # The competing connection can commit after acquisition has closed.
        writer.execute("UPDATE saved_backtests SET metrics_json='{}' WHERE id=?", (saved["id"],))
        writer.commit()
        assert explainer.acquire(saved["id"])[0]["metrics"] == {}
    finally:
        writer.close()
