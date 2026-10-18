"""Independent owned-corpus acquisition and offline lifecycle regressions."""
from contextlib import closing
import hashlib
import math
from pathlib import Path
import sqlite3

import pytest

from app import db, demo_corpus as corpus, saved_backtests
from app.run_replay.identity import digest, loads, validate

pytestmark = pytest.mark.usefixtures("isolated_lab_db")


def inventory(directory):
    return {path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()}


def forbid(*args, **kwargs):
    pytest.fail("Refused material reached a decoder, ordinary storage, or computation")


def rebind_database(directory):
    manifest = loads((directory / corpus.MANIFEST).read_bytes())
    manifest["database_sha256"] = hashlib.sha256((directory / corpus.DB_NAME).read_bytes()).hexdigest()
    manifest.pop("corpus_id")
    manifest["corpus_id"] = digest(manifest)
    (directory / corpus.MANIFEST).write_text(validate(manifest), encoding="utf-8")
    return manifest["corpus_id"]


@pytest.mark.db_free
@pytest.mark.parametrize("field", ["params", "metrics", "equity_curve", "trades"])
def test_all_public_json_preflight_precedes_every_full_decode(monkeypatch, field):
    row = {name + "_json": "{}" if name in ("params", "metrics") else "[]"
           for name in ("params", "metrics", "equity_curve", "trades")}
    row[field + "_json"] = "[" * 24 + "0" + "]" * 24
    monkeypatch.setattr(corpus, "loads", forbid)
    with pytest.raises(ValueError, match="depth bounds"):
        corpus._public_record(row)


@pytest.mark.db_free
@pytest.mark.parametrize("field", ["params", "metrics", "equity_curve", "trades"])
def test_public_json_duplicate_members_are_never_silently_projected(field):
    row = {name + "_json": "{}" if name in ("params", "metrics") else "[]"
           for name in ("params", "metrics", "equity_curve", "trades")}
    duplicate = '{"value":1,"value":2}'
    row[field + "_json"] = duplicate if field in ("params", "metrics") else "[" + duplicate + "]"
    with pytest.raises(ValueError, match="Duplicate JSON keys"):
        corpus._public_record(row)


def test_manifest_depth_refuses_before_decoder_and_without_file_effects(tmp_path, monkeypatch):
    directory = tmp_path / "public"
    identity = corpus.prepare(directory)
    (directory / corpus.MANIFEST).write_bytes(b"[" * 24 + b"0" + b"]" * 24)
    before = inventory(directory)
    monkeypatch.setattr(corpus, "loads", forbid)
    with pytest.raises(ValueError, match="depth bounds"):
        corpus.verify(directory, identity)
    assert inventory(directory) == before


@pytest.mark.parametrize("table", ["saved_backtests", "run_replay_contexts"])
def test_required_views_refuse_before_their_sql_can_execute(tmp_path, monkeypatch, table):
    directory = tmp_path / "public"
    corpus.prepare(directory)
    with closing(sqlite3.connect(directory / corpus.DB_NAME)) as connection, connection:
        connection.execute("DROP TABLE " + table)
        connection.execute("CREATE VIEW " + table + " AS SELECT 1 AS id WHERE review_probe()")
    identity = rebind_database(directory)
    before = inventory(directory)
    real_connect = sqlite3.connect
    calls = []

    def connect(*args, **kwargs):
        connection = real_connect(*args, **kwargs)
        connection.create_function("review_probe", 0, lambda: calls.append(True) or 1)
        return connection

    monkeypatch.setattr(sqlite3, "connect", connect)
    with pytest.raises(ValueError, match="corpus read schema"):
        corpus.verify(directory, identity)
    assert calls == []
    assert inventory(directory) == before


@pytest.mark.parametrize("filename", [corpus.DB_NAME, corpus.MANIFEST])
def test_new_corpus_file_hardlinks_are_refused_without_read_or_write(tmp_path, monkeypatch, filename):
    directory = tmp_path / "public"
    identity = corpus.prepare(directory)
    original = directory / filename
    alias = tmp_path / (filename + ".alias")
    alias.hardlink_to(original)
    assert original.stat().st_nlink == 2
    before = inventory(directory)
    reads = []
    real_bounded = corpus.bounded_file

    def bounded(path, maximum):
        reads.append(Path(path).name)
        return real_bounded(path, maximum)

    monkeypatch.setattr(corpus, "bounded_file", bounded)
    with pytest.raises(ValueError, match="Linked corpus paths"):
        corpus.verify(directory, identity)
    expected_reads = [corpus.DB_NAME] if filename == corpus.DB_NAME else [corpus.DB_NAME, corpus.MANIFEST]
    assert reads == expected_reads
    assert inventory(directory) == before and alias.read_bytes() == before[filename]


def test_real_synthetic_preparation_then_read_only_backup_restore_uses_no_default_storage(tmp_path, monkeypatch):
    import app.backtest as backtest
    import app.metrics as metrics
    import app.strategies as strategies

    original_override = db._db_path_override
    original_engine, original_metrics, original_signals = backtest.run_backtest, metrics.compute_metrics, strategies.sma_crossover_signals
    setup_calls = []

    def signals(close, fast, slow):
        assert (fast, slow) == (5, 20)
        assert len(close) == 180 and str(close.index[0].date()) == "2000-01-03"
        assert list(close) == [100 + index * .12 + 8 * math.sin(index / 9) for index in range(180)]
        setup_calls.append("signals")
        return original_signals(close, fast, slow)

    def engine(close, signal, cost, capital):
        assert (cost, capital) == (10, 100000)
        setup_calls.append("engine")
        return original_engine(close, signal, cost, capital)

    def compute(equity):
        setup_calls.append("metrics")
        return original_metrics(equity)

    monkeypatch.setattr(db, "get_db_path", forbid)
    monkeypatch.setattr(backtest, "run_backtest", engine)
    monkeypatch.setattr(metrics, "compute_metrics", compute)
    monkeypatch.setattr(strategies, "sma_crossover_signals", signals)
    source = tmp_path / "prepared"
    identity = corpus.prepare(source)
    assert setup_calls == ["signals", "engine", "metrics"]
    before = inventory(source)

    for module, names in ((db, ("init_db", "get_connection")),
                          (saved_backtests, ("get_saved_backtest", "create_saved_backtest", "list_saved_backtests")),
                          (backtest, ("run_backtest",)), (metrics, ("compute_metrics",)),
                          (strategies, ("sma_crossover_signals",))):
        for name in names:
            monkeypatch.setattr(module, name, forbid)
    real_connect = sqlite3.connect
    reads = []

    def read_only(database, *args, **kwargs):
        assert str(database).endswith("?mode=ro") and kwargs.get("uri") is True
        reads.append(database)
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", read_only)
    manifest, record, explanation = corpus.verify(source, identity)
    backup, restored = tmp_path / "backup", tmp_path / "restored"
    assert corpus.copy_stopped(source, backup, identity, stopped=True) == identity
    assert corpus.copy_stopped(backup, restored, identity, stopped=True) == identity
    assert corpus.verify(restored, identity) == (manifest, record, explanation)
    assert reads and inventory(source) == inventory(backup) == inventory(restored) == before
    assert set(before) == {corpus.DB_NAME, corpus.MANIFEST}
    assert record["initial_capital"] == 100000 and record["transaction_cost_bps"] == 10
    assert record["params"] == {"fast_window": 5, "slow_window": 20, "periods_per_year": 252}
    assert explanation["identity"]["trust"] == "legacy_unverified"
    assert db._db_path_override == original_override


def test_interrupted_copy_retains_owned_nonserving_partial_and_preserves_source(tmp_path, monkeypatch):
    source, destination = tmp_path / "source", tmp_path / "partial-copy"
    identity = corpus.prepare(source)
    before = inventory(source)
    real_open = Path.open

    def interrupted(path, *args, **kwargs):
        if path == destination / corpus.MANIFEST:
            raise OSError("controlled copy interruption")
        return real_open(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", interrupted)
        with pytest.raises(OSError, match="controlled copy interruption"):
            corpus.copy_stopped(source, destination, identity, stopped=True)
    assert inventory(source) == before
    assert inventory(destination) == {corpus.DB_NAME: before[corpus.DB_NAME]}
    with pytest.raises(ValueError, match="Corpus file is missing"):
        corpus.verify(destination, identity)


@pytest.mark.parametrize("operation", ["prepare", "copy"])
def test_final_verification_failure_cannot_publish_a_serving_manifest(tmp_path, monkeypatch, operation):
    destination = tmp_path / "unpublished"
    source, identity, source_bytes = None, None, None
    if operation == "copy":
        source = tmp_path / "source"
        identity = corpus.prepare(source)
        source_bytes = inventory(source)
    original_explain = corpus.explainer.explain
    interrupted_paths = []

    def interrupted(saved_id, expected=None, *, path=None):
        if path == destination / corpus.DB_NAME:
            assert path.is_file() and not (destination / corpus.MANIFEST).exists()
            interrupted_paths.append(path)
            raise OSError("controlled final verification interruption")
        return original_explain(saved_id, expected, path=path)

    with monkeypatch.context() as patch:
        patch.setattr(corpus.explainer, "explain", interrupted)
        with pytest.raises(OSError, match="controlled final verification interruption"):
            if operation == "prepare":
                corpus.prepare(destination)
            else:
                corpus.copy_stopped(source, destination, identity, stopped=True)
    assert interrupted_paths == [destination / corpus.DB_NAME]
    assert (destination / corpus.DB_NAME).is_file()
    assert not (destination / corpus.MANIFEST).exists()
    if source is not None:
        assert inventory(source) == source_bytes
    with pytest.raises(ValueError, match="Corpus file is missing"):
        corpus.verify(destination, identity or "a" * 64)


@pytest.mark.parametrize("state", ["missing", "closed_wal", "live_rollback_journal"])
def test_offline_copy_refuses_unsupported_source_before_connect_or_destination_creation(tmp_path, monkeypatch, state):
    source, destination = tmp_path / "source", tmp_path / "not-created"
    identity = corpus.prepare(source)
    database = source / corpus.DB_NAME
    writer = None
    try:
        if state == "missing":
            database.rename(source / "retained-original.db")
        else:
            writer = sqlite3.connect(database)
            if state == "closed_wal":
                assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
                writer.close()
                writer = None
                assert not Path(str(database) + "-wal").exists()
            else:
                writer.execute("BEGIN IMMEDIATE")
                writer.execute("UPDATE saved_backtests SET notes='controlled pending write'")
                assert Path(str(database) + "-journal").is_file()
        before = inventory(source)
        with monkeypatch.context() as patch:
            patch.setattr(sqlite3, "connect", forbid)
            with pytest.raises(ValueError, match="missing|storage mode|journal state"):
                corpus.copy_stopped(source, destination, identity, stopped=True)
        assert inventory(source) == before and not destination.exists()
    finally:
        if writer is not None:
            writer.close()
