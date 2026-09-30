"""Independent importer review; all files and databases belong to pytest fixtures."""

import io
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.ml_lifecycle import importer
from .test_ml_lifecycle_import import legacy


def _parquet(columns):
    pa = pytest.importorskip("pyarrow", reason="real codec requires optional pyarrow")
    import pyarrow.parquet as pq

    value = columns if isinstance(columns, pa.Table) else pa.table(columns)
    output = io.BytesIO()
    pq.write_table(value, output, use_dictionary=True, compression="snappy")
    return output.getvalue()


def _columns(values):
    return {"timestamp": [f"2024-01-01T00:00:{i:02d}Z" for i in range(len(values))],
            "root_symbol": ["ES"] * len(values), "active_contract": ["ESH24"] * len(values),
            "prediction": values}


@pytest.mark.parametrize("value", [None, 0.5, float("nan"), float("inf"), float("-inf")])
def test_real_parquet_nullable_finite_boundary(value):
    import math

    pa = pytest.importorskip("pyarrow", reason="real codec requires optional pyarrow")
    columns = _columns([value])
    columns["prediction"] = pa.array([value], type=pa.float64())
    data = _parquet(columns)
    if value is not None and not math.isfinite(value):
        with pytest.raises(ValueError, match="finite"):
            importer._frame(data, ".parquet")
    else:
        assert importer._frame(data, ".parquet")["rows"][0][-1] == value


def test_real_parquet_csv_semantics_with_offset_null_and_boolean():
    pa = pytest.importorskip("pyarrow", reason="real codec requires optional pyarrow")
    source_time = datetime(2024, 1, 1, 8, 0, 0, 123456, tzinfo=timezone(timedelta(hours=8)))
    columns = {"timestamp": pa.array([source_time], type=pa.timestamp("us", tz="Asia/Taipei")),
               "root_symbol": ["ES"], "active_contract": ["ESH24"],
               "prediction": pa.array([None], type=pa.float64()), "roll_flag": [False], "signal_state": ["flat"]}
    csv = (b"timestamp,root_symbol,active_contract,prediction,roll_flag,signal_state\n"
           b"2024-01-01T08:00:00.123456+08:00,ES,ESH24,,false,flat\n")
    assert importer._frame(_parquet(columns), ".parquet") == importer._frame(csv, ".csv")


@pytest.mark.parametrize("field,value", [("prediction", True), ("root_symbol", 123),
                                         ("active_contract", False), ("prediction", 2 ** 53 + 1)])
def test_real_parquet_rejects_lossy_role_coercion(field, value):
    columns = _columns([0.5])
    columns[field] = [value]
    with pytest.raises(ValueError, match="boolean|strings|binary64"):
        importer._frame(_parquet(columns), ".parquet")


def test_real_parquet_duplicate_columns_rejected():
    pa = pytest.importorskip("pyarrow", reason="real codec requires optional pyarrow")
    value = pa.Table.from_arrays([pa.array(v) for v in _columns([0.5]).values()],
                                names=["timestamp", "root_symbol", "active_contract", "root_symbol"])
    with pytest.raises(ValueError, match="duplicate"):
        importer._frame(_parquet(value), ".parquet")


@pytest.mark.parametrize("kind", ["rows", "columns", "nested", "truncated"])
def test_real_parquet_metadata_and_format_bounds(kind):
    columns = _columns([0.5])
    if kind == "rows":
        columns = {key: values * (importer.MAX_ROWS + 1) for key, values in columns.items()}
    elif kind == "columns":
        columns.update({f"value_{i}": [0.5] for i in range(importer.MAX_COLUMNS)})
    elif kind == "nested":
        columns["prediction"] = [[0.5]]
    data = _parquet(columns)
    if kind == "truncated":
        data = data[:-8]
    with pytest.raises((ValueError, OSError)):
        importer._frame(data, ".parquet")


def test_real_parquet_dictionary_expansion_is_bounded():
    pytest.importorskip("pyarrow", reason="real codec requires optional pyarrow")
    import pyarrow.parquet as pq

    # The dictionary/page representation is tiny; materializing every repeated
    # string in Python would exceed the advertised decoded bound.
    count = importer.MAX_ROWS
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    columns = {"timestamp": [(start + timedelta(seconds=i)).isoformat() for i in range(count)],
               "root_symbol": ["X" * 3000] * count, "active_contract": ["ESH24"] * count,
               "prediction": [0.5] * count}
    data = _parquet(columns)
    metadata = pq.ParquetFile(io.BytesIO(data)).metadata
    assert len(data) < importer.MAX_BYTES
    assert sum(metadata.row_group(i).total_byte_size for i in range(metadata.num_row_groups)) < importer.MAX_BYTES
    with pytest.raises(ValueError, match="decoded table exceeds bounds"):
        importer._frame(data, ".parquet")


@pytest.mark.parametrize("value", ["true", "false", str(2 ** 53 + 1)])
def test_csv_rejects_lossy_numeric_coercion(value):
    data = f"timestamp,root_symbol,active_contract,value\n2024-01-01T00:00:00Z,ES,ESH24,{value}\n".encode()
    with pytest.raises(ValueError, match="boolean|binary64"):
        importer._frame(data, ".csv")


@pytest.mark.parametrize("field,value", [("schema_version", True), ("schema_version", "1"),
                                         ("n_oos_rows", 2.0), ("n_scored_rows", "2"),
                                         ("feature_columns", ["feature__x", "feature__x"])])
def test_source_metadata_rejected_before_model_coercion(legacy, field, value):
    root, run, directory = legacy
    path = directory / "metadata.json"
    data = json.loads(path.read_text())
    data[field] = value
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        importer.preview(root, run)


@pytest.mark.parametrize("path", [r"\\owned-fixture-host\share\run", r"C:owned-fixture-run"])
def test_nonlocal_or_drive_relative_root_rejected_before_io(monkeypatch, path):
    monkeypatch.setattr(importer, "_safe_path", lambda *_args, **_kwargs: pytest.fail("unsafe root reached filesystem"))
    with pytest.raises(ValueError, match="explicit local path"):
        importer.preview(Path(path), "a" * 64)


def test_parent_replacement_is_blocked_or_detected(legacy, monkeypatch):
    root, run, directory = legacy
    replacement = root / "owned-replacement"
    replacement.mkdir()
    for file in directory.iterdir():
        (replacement / file.name).write_bytes(file.read_bytes())
    (replacement / "metrics.json").write_text('{"accuracy":0.7}')
    parked = root / "owned-original"
    original = importer._read
    attempted = False
    replaced = False

    def replace_parent(path, **kwargs):
        nonlocal attempted, replaced
        if not attempted:
            attempted = True
            try:
                directory.rename(parked)
            except PermissionError:
                assert os.name == "nt"
            else:
                replacement.rename(directory)
                replaced = True
        return original(path, **kwargs)

    monkeypatch.setattr(importer, "_read", replace_parent)
    try:
        snapshot = importer.preview(root, run)
    except ValueError as error:
        assert replaced
        assert "changed" in str(error)
    else:
        assert not replaced
        assert snapshot["source"]["metrics"]["accuracy"] == 0.5
        assert not parked.exists()
    assert attempted


def test_file_replacement_between_check_and_open_rejected(legacy, monkeypatch):
    _, _, directory = legacy
    path = directory / "metrics.json"
    replacement = directory.parent / "owned-other.json"
    replacement.write_text('{"accuracy":0.7}')
    original = importer.os.open
    attempted = False

    def replacing_open(target, flags, *args, **kwargs):
        nonlocal attempted
        if Path(target) == path and not attempted:
            attempted = True
            os.replace(replacement, path)
        return original(target, flags, *args, **kwargs)

    monkeypatch.setattr(importer.os, "open", replacing_open)
    with pytest.raises(ValueError, match="changed while opening"):
        importer._read(path)
    assert attempted


@pytest.mark.skipif(os.name != "nt", reason="Windows junction behavior requires Windows")
def test_actual_junction_never_reaches_artifact_reader(legacy, monkeypatch):
    root, run, _ = legacy
    link = root / "owned-junction"
    # Both literal paths are generated beneath this test's disposable root.
    command = "New-Item -ItemType Junction -Path '" + str(link).replace("'", "''") + "' -Target '" + str(root).replace("'", "''") + "' | Out-Null"
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    try:
        monkeypatch.setattr(importer, "_read", lambda *_args, **_kwargs: pytest.fail("junction reached reader"))
        with pytest.raises(ValueError, match="reparse"):
            importer.preview(link, run)
    finally:
        link.rmdir()


def _cli(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]))
    from scripts.import_ml_lifecycle import main
    return main


def test_cli_write_uses_explicit_path_and_restores_override(legacy, isolated_lab_db, monkeypatch, capsys):
    from app import db
    from app.dataset_registry import service as datasets
    from app.dataset_registry.models import DatasetCreate, VersionCreate
    from app.ml_lifecycle import service

    snapshot = importer.preview(legacy[0], legacy[1])
    dataset = datasets.create_dataset(DatasetCreate(name="Owned legacy import", domain="research",
                                      dataset_type="experiment_snapshot", source_type="local_file").model_dump(mode="json"))
    version = datasets.create_version(dataset["id"], VersionCreate(version_label="v1", format="json",
                     storage_locator="fixture://legacy/snapshot", content_fingerprint=snapshot["source_hash"]).model_dump(mode="json"))
    sentinel = legacy[0] / "owned-previous-override.db"
    monkeypatch.setattr(db, "_db_path_override", sentinel)
    args = ["--source-root", str(legacy[0]), "--run", legacy[1], "--write",
            "--destination-db", str(isolated_lab_db), "--dataset-version-id", str(version["id"])]
    assert _cli(monkeypatch)(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["completeness"] == "incomplete"
    assert result["integrity"] == "intact"
    assert db._db_path_override == sentinel and not sentinel.exists()
    monkeypatch.setattr(db, "_db_path_override", isolated_lab_db)
    assert service.get_run(result["id"])["snapshot"]["source_hash"] == snapshot["source_hash"]


def test_cli_write_failure_restores_override(legacy, isolated_lab_db, monkeypatch):
    from app import db

    sentinel = legacy[0] / "owned-previous-override.db"
    monkeypatch.setattr(db, "_db_path_override", sentinel)
    with pytest.raises(ValueError, match="existing Dataset"):
        _cli(monkeypatch)(["--source-root", str(legacy[0]), "--run", legacy[1], "--write",
                           "--destination-db", str(isolated_lab_db), "--dataset-version-id", "999999"])
    assert db._db_path_override == sentinel and not sentinel.exists()


def test_cli_hardlinked_destination_refused_before_database_access(legacy, monkeypatch):
    from app import db

    destination = legacy[0] / "owned-destination.db"
    destination.write_bytes(b"owned fixture, not a database")
    os.link(destination, legacy[0] / "owned-destination-link.db")
    monkeypatch.setattr(db, "init_db", lambda: pytest.fail("unsafe destination reached database initialization"))
    with pytest.raises(ValueError, match="one link"):
        _cli(monkeypatch)(["--source-root", str(legacy[0]), "--run", legacy[1], "--write",
                           "--destination-db", str(destination), "--dataset-version-id", "1"])


@pytest.mark.parametrize("extra", [[], ["--dataset-version-id", "0"], ["--dataset-version-id", "-1"]])
def test_cli_missing_explicit_write_arguments_fail_before_preview(monkeypatch, tmp_path, extra):
    main = _cli(monkeypatch)
    import scripts.import_ml_lifecycle as cli

    monkeypatch.setattr(cli, "preview", lambda *_: pytest.fail("invalid write request read source"))
    with pytest.raises(SystemExit) as error:
        main(["--source-root", str(tmp_path), "--run", "a" * 64, "--write", *extra])
    assert error.value.code == 2
