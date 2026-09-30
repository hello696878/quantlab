"""Operator-only, bounded ExperimentStore snapshots. Never loads executable models."""

from __future__ import annotations

import csv
import hashlib
import io
import os
import re
import stat
from pathlib import Path

from app.experiments.spec import ExperimentRun

from .identity import MAX_BYTES, MAX_COLUMNS, MAX_ROWS, environment, fingerprint, read_json, table
from .validation import validate

_RUN = re.compile(r"^[a-f0-9]{64}$")
_JSON = ("metadata.json", "model_params.json", "metrics.json")
_FRAMES = ("predictions", "signal", "backtest")


def _safe_path(path: Path, *, directory: bool = False) -> os.stat_result:
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("symlinks and reparse points are not accepted")
    info = path.lstat()
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("source root/run must be directories")
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_BYTES:
        raise ValueError("artifact must be a bounded regular file with one link")
    return info


def _signature(info):
    # Windows path stat and handle fstat can expose different ctime semantics.
    # Compare identity/size/mtime across APIs; compare handle ctime to itself.
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_nlink


def _read(path: Path) -> bytes:
    before = _safe_path(path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as source:
        opened = os.fstat(source.fileno())
        if _signature(opened) != _signature(before):
            raise ValueError("artifact changed while opening")
        data = source.read(MAX_BYTES + 1)
        after = os.fstat(source.fileno())
        if _signature(after) != _signature(opened) or after.st_ctime_ns != opened.st_ctime_ns:
            raise ValueError("artifact changed while reading")
    if len(data) > MAX_BYTES or _signature(_safe_path(path)) != _signature(before):
        raise ValueError("artifact changed while reading")
    return data


def _frame(data: bytes, extension: str) -> dict:
    # Parse in memory only after size and containment validation. Parquet metadata
    # is bounded before decompression; CSV is canonicalized using explicit roles.
    if extension == ".parquet":
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
            source = pq.ParquetFile(io.BytesIO(data))
            meta = source.metadata
            if meta.num_rows > MAX_ROWS or meta.num_columns > MAX_COLUMNS:
                raise ValueError("Parquet exceeds table bounds")
            if sum(meta.row_group(i).total_byte_size for i in range(meta.num_row_groups)) > MAX_BYTES:
                raise ValueError("Parquet decompressed size exceeds bounds")
            if any(not (pa.types.is_string(f.type) or pa.types.is_large_string(f.type) or
                        pa.types.is_integer(f.type) or pa.types.is_floating(f.type) or
                        pa.types.is_boolean(f.type) or pa.types.is_timestamp(f.type)) for f in source.schema_arrow):
                raise ValueError("Parquet must contain scalar columns only")
            frame = source.read()
            names = frame.column_names
            # Arrow scalars distinguish null from NaN; pandas would merge them.
            raw = [names, *[[row[name] for name in names] for row in frame.to_pylist()]]
        except ImportError as exc:
            raise ValueError("Parquet import requires the existing optional pyarrow dependency") from exc
    else:
        raw = list(csv.reader(io.StringIO(data.decode("utf-8-sig")), strict=True))
    if not raw or len(raw) - 1 > MAX_ROWS or len(raw[0]) > MAX_COLUMNS:
        raise ValueError("empty or oversized table")
    names = raw[0]
    keys = ["timestamp", "root_symbol", "active_contract"]
    if not set(keys) <= set(names):
        raise ValueError("frame lacks full timestamp/instrument keys")
    columns = [{"name": name, "type": "timestamp" if name == "timestamp" else
                "string" if name in ("root_symbol", "active_contract", "signal_state") else
                "boolean" if name == "roll_flag" else "number",
                "nullable": name not in keys} for name in names]
    rows = []
    for raw_row in raw[1:]:
        if len(raw_row) != len(names):
            raise ValueError("CSV row width mismatch")
        row = []
        for value, column in zip(raw_row, columns):
            if value is None or value == "":
                row.append(None)
            elif column["type"] == "boolean":
                if str(value).lower() not in ("true", "false"):
                    raise ValueError("invalid boolean artifact value")
                row.append(str(value).lower() == "true")
            elif column["type"] == "number":
                if isinstance(value, str) and value.lower() in ("true", "false"):
                    row.append(float(value.lower() == "true"))
                else:
                    row.append(float(value))
            else:
                row.append(value.isoformat() if hasattr(value, "isoformat") else str(value))
        rows.append(row)
    return table(columns, rows, keys)


def preview(source_root: Path, run: str) -> dict:
    """Read one explicit run, retain bytes and semantics, create no files/database."""
    if not _RUN.fullmatch(run):
        raise ValueError("run must be an existing SHA-256 run directory")
    root = source_root.absolute()
    target = root / run
    try:
        _safe_path(root, directory=True)
        _safe_path(target, directory=True)
        names = set(p.name for p in target.iterdir())
        selected = list(_JSON)
        for stem in _FRAMES:
            matches = [f"{stem}{ext}" for ext in (".csv", ".parquet") if f"{stem}{ext}" in names]
            if len(matches) != 1:
                raise ValueError("each frame requires exactly one CSV or Parquet artifact")
            selected.extend(matches)
        if names != set(selected):
            raise ValueError("unexpected artifacts in selected run")
        blobs = {name: _read(target / name) for name in selected}
        if sum(map(len, blobs.values())) > MAX_BYTES:
            raise ValueError("combined run exceeds 4 MiB")
        metadata = ExperimentRun.model_validate(read_json(blobs["metadata.json"]))
        if metadata.schema_version != 1 or metadata.train_run_hash != run:
            raise ValueError("unsupported schema or run hash mismatch")
        if any(path not in selected or Path(path).name != path for path in metadata.artifact_paths.values()):
            raise ValueError("artifact locators must identify the selected root-level files")
        parameters = read_json(blobs["model_params.json"])
        metrics = read_json(blobs["metrics.json"])
        frames = {Path(name).stem: _frame(data, Path(name).suffix)
                  for name, data in blobs.items() if Path(name).suffix != ".json"}
        # Metadata timestamps/paths are intentionally not semantic training evidence.
        source = metadata.model_dump(mode="json", exclude={"created_at", "artifact_paths"})
        logical = {"metadata": source, "parameters": parameters, "metrics": metrics, "tables": frames}
        if set(p.name for p in target.iterdir()) != names or any(_read(target / name) != data for name, data in blobs.items()):
            raise ValueError("source changed during validation")
        snapshot = {"schema_version": 1, "origin": "experiment_store", "source": logical,
                "source_hash": fingerprint("experiment_source", logical),
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in blobs.items()},
                "source_environment": {"classification": "unknown"},
                "inspection_environment": environment("inspection"),
                "unavailable": ["feature payload", "exact train/split membership", "verified OOF provenance",
                                "calibration provenance", "historical training environment"]}
        validate(snapshot)
        return snapshot
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError("source is missing, unsafe, unreadable or malformed; no import performed") from exc
