"""Adversarial imports use only disposable fixture paths, never user files."""

import json
import os
from pathlib import Path

import pytest

from app.ml_lifecycle import importer
from app.ml_lifecycle.identity import fingerprint
from app.ml_lifecycle.validation import identities, validate

pytestmark = [pytest.mark.usefixtures("isolated_lab_db"), pytest.mark.db_free]


@pytest.fixture
def legacy(tmp_path):
    run = "a" * 64
    directory = tmp_path / run
    directory.mkdir()
    metadata = {"train_run_hash": run, "model_type": "logistic_regression", "task_type": "classification",
                "feature_columns": ["feature__x"], "label_column": "label__direction_1",
                "train_start": "2020-01-01", "train_end": "2020-06-01",
                "validation_start": "2020-07-01", "validation_end": "2020-12-01",
                "metrics": {}, "backtest_metrics": {}, "baseline_metrics": {},
                "created_at": "2021-01-01T00:00:00Z", "artifact_paths": {}, "n_oos_rows": 2, "n_scored_rows": 2}
    for key in ("continuous_config_hash", "feature_config_hash", "label_config_hash", "dataset_config_hash", "model_config_hash"):
        metadata[key] = "b" * 64
    (directory / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (directory / "model_params.json").write_text('{"coef_":[0.5],"intercept_":0}', encoding="utf-8")
    (directory / "metrics.json").write_text('{"accuracy":0.5}', encoding="utf-8")
    for stem in ("predictions", "signal", "backtest"):
        (directory / (stem + ".csv")).write_text(
            "timestamp,root_symbol,active_contract,value\n2020-07-01T12:00:00Z,ES,ESU20,0.5\n2020-07-01T13:00:00Z,ES,ESU20,0.6\n", encoding="utf-8")
    return tmp_path, run, directory


def test_preview_no_writes_and_explicit_legacy_gaps(legacy):
    root, run, directory = legacy
    before = {p: p.read_bytes() for p in directory.iterdir()}
    snapshot = importer.preview(root, run)
    validate(snapshot)
    assert before == {p: p.read_bytes() for p in directory.iterdir()}
    assert len(list(root.iterdir())) == 1
    assert snapshot["source_environment"] == {"classification": "unknown"}
    assert snapshot["inspection_environment"]["classification"] == "inspection"
    assert "feature payload" in snapshot["unavailable"]
    assert identities(snapshot)["models"] is None
    assert snapshot["source"]["metadata"]["train_run_hash"] == run


def test_physical_and_semantic_hashes_are_separate(legacy):
    root, run, directory = legacy
    first = importer.preview(root, run)
    path = directory / "metrics.json"
    path.write_text('{ "accuracy" : 0.5 }', encoding="utf-8")
    second = importer.preview(root, run)
    assert first["source_hash"] == second["source_hash"]
    assert first["files"] != second["files"]
    assert identities(first) == identities(second)
    path.write_text('{"accuracy":0.7}', encoding="utf-8")
    assert importer.preview(root, run)["source_hash"] != first["source_hash"]


@pytest.mark.parametrize("run", ["..", "../private", "C:\\private", "/private", "a:stream", "a" * 63, "A" * 64])
def test_unsafe_run_rejected_before_read(legacy, run, monkeypatch):
    monkeypatch.setattr(importer, "_read", lambda *_: pytest.fail("unsafe run reached file reader"))
    with pytest.raises(ValueError):
        importer.preview(legacy[0], run)


@pytest.mark.parametrize("kind", ["unknown", "alternate", "missing", "duplicate-json", "nan", "bad-csv", "duplicate-sample", "naive-time", "traversal-locator", "future-schema", "oversized", "deep"])
def test_invalid_artifacts_refused(legacy, kind):
    root, run, directory = legacy
    path = directory / "metrics.json"
    if kind == "unknown":
        (directory / "model.pkl").write_bytes(b"not loaded")
    elif kind == "alternate":
        (directory / "predictions.parquet").write_bytes(b"not loaded")
    elif kind == "missing":
        path.unlink()
    elif kind == "duplicate-json":
        path.write_text('{"x":1,"x":2}')
    elif kind == "nan":
        path.write_text('{"x":NaN}')
    elif kind == "deep":
        path.write_text('[' * 30 + '0' + ']' * 30)
    elif kind == "oversized":
        path.write_bytes(b" " * (importer.MAX_BYTES + 1))
    elif kind in ("traversal-locator", "future-schema"):
        path = directory / "metadata.json"
        value = json.loads(path.read_text())
        if kind == "traversal-locator":
            value["artifact_paths"] = {"model": "../outside.json"}
        else:
            value["schema_version"] = 2
        path.write_text(json.dumps(value))
    else:
        path = directory / "predictions.csv"
        value = path.read_text()
        if kind == "bad-csv":
            value += '"unterminated'
        elif kind == "duplicate-sample":
            value += value.splitlines()[1] + "\n"
        else:
            value = value.replace("Z,", ",")
        path.write_text(value)
    with pytest.raises(ValueError):
        importer.preview(root, run)


def test_hardlink_refused(legacy):
    root, run, directory = legacy
    outside = root / "fixture-only.json"
    outside.write_text("{}")
    target = directory / "model_params.json"
    target.unlink()
    os.link(outside, target)
    with pytest.raises(ValueError, match="one link"):
        importer.preview(root, run)


def test_reparse_attribute_refused_without_following(monkeypatch, tmp_path):
    class Info:
        st_mode = 0o040755
        st_file_attributes = 0x400
    monkeypatch.setattr(Path, "lstat", lambda _: Info())
    with pytest.raises(ValueError, match="reparse"):
        importer._safe_path(tmp_path, directory=True)


def test_mutation_between_reads_refused(legacy, monkeypatch):
    root, run, directory = legacy
    original = importer._read
    counts = {}

    def changing(path):
        counts[path.name] = counts.get(path.name, 0) + 1
        if path.name == "metrics.json" and counts[path.name] == 2:
            path.write_text('{"accuracy":0.6}')
        return original(path)

    monkeypatch.setattr(importer, "_read", changing)
    with pytest.raises(ValueError, match="changed"):
        importer.preview(root, run)


def test_tampered_snapshot_refused(legacy):
    snapshot = importer.preview(legacy[0], legacy[1])
    snapshot["source"]["tables"]["predictions"]["rows"][0][-1] = .9
    with pytest.raises(ValueError, match="content mismatch"):
        validate(snapshot)
    snapshot["source_hash"] = fingerprint("experiment_source", snapshot["source"])
    snapshot["source_environment"] = {"classification": "source"}
    with pytest.raises(ValueError, match="historical environment"):
        validate(snapshot)


@pytest.mark.parametrize("parquet", [False, True])
def test_real_experiment_store_frame_roundtrip(legacy, parquet):
    import pandas as pd
    from app.experiments.store import ExperimentStore
    root, run, directory = legacy
    if parquet:
        pytest.importorskip("pyarrow")
    store = ExperimentStore(root, prefer_parquet=parquet)
    metadata_path = directory / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["n_oos_rows"] = 3
    metadata_path.write_text(json.dumps(metadata))
    for stem in ("predictions", "signal", "backtest"):
        (directory / (stem + ".csv")).unlink()
        frame = pd.DataFrame({"timestamp": pd.date_range("2024-01-01", periods=3, tz="UTC"),
                              "root_symbol": "ES", "active_contract": "ESH24", "prediction": [.2, .5, .8]})
        if stem == "signal":
            frame["signal_state"] = ["flat", "long", "long"]
        if stem == "backtest":
            frame["roll_flag"] = [False, False, False]
        store.write_frame(run, stem, frame)
    snapshot = importer.preview(root, run)
    validate(snapshot)
    assert len(snapshot["source"]["tables"]["signal"]["rows"]) == 3


def test_symlink_never_followed(tmp_path):
    outside = tmp_path / "owned-outside"
    outside.mkdir()
    linked = tmp_path / "owned-link"
    try:
        linked.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("OS does not permit fixture symlink creation")
    with pytest.raises(ValueError, match="reparse|symlink"):
        importer._safe_path(linked, directory=True)


def test_frame_alignment_is_exact_not_row_count_only(legacy):
    root, run, directory = legacy
    path = directory / "signal.csv"
    path.write_text(path.read_text().replace("13:00:00", "14:00:00"))
    with pytest.raises(ValueError, match="alignment"):
        importer.preview(root, run)


def test_cli_preview_creates_no_database(legacy, monkeypatch, capsys):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]))
    from scripts.import_ml_lifecycle import main
    before = set(legacy[0].rglob("*"))
    assert main(["--source-root", str(legacy[0]), "--run", legacy[1]]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "preview"
    assert set(legacy[0].rglob("*")) == before


@pytest.mark.parametrize("value", [None, 0.5, float("nan"), float("inf"), float("-inf")])
def test_parquet_scalar_boundary_preserves_null_and_rejects_nonfinite(monkeypatch, value):
    import math
    import sys
    from types import ModuleType, SimpleNamespace

    import pandas as pd

    names = ["timestamp", "root_symbol", "active_contract", "prediction"]
    row = dict(zip(names, ["2024-01-01T00:00:00Z", "ES", "ESH24", value]))
    # Stub only the optional decoder boundary, not canonical scalar validation.
    # The separate ExperimentStore test covers real Parquet when pyarrow exists.
    decoded = SimpleNamespace(column_names=names, to_pylist=lambda: [row],
                              to_pandas=lambda: pd.DataFrame([row]))
    source = SimpleNamespace(metadata=SimpleNamespace(num_rows=1, num_columns=4, num_row_groups=0),
                             schema_arrow=[SimpleNamespace(type="scalar")], read=lambda: decoded)
    arrow = ModuleType("pyarrow")
    arrow.types = SimpleNamespace(is_string=lambda _: True)
    parquet = ModuleType("pyarrow.parquet")
    parquet.ParquetFile = lambda _: source
    arrow.parquet = parquet
    monkeypatch.setitem(sys.modules, "pyarrow", arrow)
    monkeypatch.setitem(sys.modules, "pyarrow.parquet", parquet)

    if value is not None and not math.isfinite(value):
        with pytest.raises(ValueError, match="finite"):
            importer._frame(b"decoder-fixture", ".parquet")
    else:
        assert importer._frame(b"decoder-fixture", ".parquet")["rows"][0][-1] == value
