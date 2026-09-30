"""Operator-only, bounded ExperimentStore snapshots. Never loads executable models."""

from __future__ import annotations

import csv
from contextlib import ExitStack, contextmanager
import hashlib
import io
import os
import re
import stat
from pathlib import Path, PureWindowsPath

from app.experiments.spec import ExperimentRun

from .identity import MAX_BYTES, MAX_COLUMNS, MAX_ROWS, environment, fingerprint, read_json, table
from .validation import validate, validate_source_metadata

_RUN = re.compile(r"^[a-f0-9]{64}$")
_JSON = ("metadata.json", "model_params.json", "metrics.json")
_FRAMES = ("predictions", "signal", "backtest")


def _safe_path(path: Path, *, directory: bool = False, bounded: bool = True) -> os.stat_result:
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("symlinks and reparse points are not accepted")
    info = path.lstat()
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("source root/run must be directories")
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or bounded and info.st_size > MAX_BYTES:
        raise ValueError("artifact must be a bounded regular file with one link")
    return info


def _windows_directory_fd(path):
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    create.restype = wintypes.HANDLE
    # Request list-directory/read-attributes access with no deletion sharing.
    # Retained handles and named-identity comparisons remain the safety checks;
    # rename prevention is not assumed from a particular Windows filesystem.
    handle = create(str(path), 0x81, 0x3, None, 3, 0x02000000 | 0x00200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle(handle)
        raise


def local_path(path: Path) -> Path:
    windows = PureWindowsPath(str(path))
    if windows.drive.startswith("\\\\") or windows.drive and not windows.root:
        raise ValueError("source/destination must use an explicit local path, not UNC or drive-relative paths")
    return path.absolute()


@contextmanager
def pinned_directory(path: Path):
    """Pin each ancestor; POSIX reads use the final directory descriptor."""
    absolute = local_path(path)
    current = Path(absolute.anchor)
    parent_fd = None
    identities = []
    with ExitStack() as stack:
        for part in (None, *absolute.parts[1:]):
            if part is not None:
                current = current / part
            before = _safe_path(current, directory=True)
            if os.name == "nt":
                fd = _windows_directory_fd(current)
            else:
                flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                fd = os.open(current if parent_fd is None else part, flags, dir_fd=parent_fd)
            stack.callback(os.close, fd)
            opened = os.fstat(fd)
            if (not stat.S_ISDIR(opened.st_mode) or getattr(opened, "st_file_attributes", 0) & 0x400 or
                    (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
                raise ValueError("source/destination directory changed while opening")
            identities.append((current, (opened.st_dev, opened.st_ino)))
            parent_fd = fd
        try:
            yield parent_fd
        finally:
            for current, identity in identities:
                info = _safe_path(current, directory=True)
                if (info.st_dev, info.st_ino) != identity:
                    raise ValueError("source/destination directory changed during access")


def _signature(info):
    # Windows path stat and handle fstat can expose different ctime semantics.
    # Compare identity/size/mtime across APIs; compare handle ctime to itself.
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_nlink


def _read(path: Path, *, parent_fd=None) -> bytes:
    def check_parent():
        if parent_fd is not None:
            named = _safe_path(path.parent, directory=True)
            held = os.fstat(parent_fd)
            if (named.st_dev, named.st_ino) != (held.st_dev, held.st_ino):
                raise ValueError("artifact parent changed during access")

    check_parent()
    before = _safe_path(path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path.name, flags, dir_fd=parent_fd) if parent_fd is not None and os.name != "nt" else os.open(path, flags)
    with os.fdopen(fd, "rb") as source:
        opened = os.fstat(source.fileno())
        if _signature(opened) != _signature(before):
            raise ValueError("artifact changed while opening")
        check_parent()
        data = source.read(MAX_BYTES + 1)
        after = os.fstat(source.fileno())
        if _signature(after) != _signature(opened) or after.st_ctime_ns != opened.st_ctime_ns:
            raise ValueError("artifact changed while reading")
    if len(data) > MAX_BYTES or _signature(_safe_path(path)) != _signature(before):
        raise ValueError("artifact changed while reading")
    check_parent()
    return data


def _frame(data: bytes, extension: str) -> dict:
    # Parse in memory only after size and containment validation. Parquet metadata
    # is bounded before decompression; CSV is canonicalized using explicit roles.
    if len(data) > MAX_BYTES:
        raise ValueError("artifact exceeds 4 MiB")
    if extension == ".parquet":
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
            source = pq.ParquetFile(io.BytesIO(data), thrift_string_size_limit=MAX_BYTES,
                                    thrift_container_size_limit=MAX_ROWS * MAX_COLUMNS)
            meta = source.metadata
            if meta.num_rows > MAX_ROWS or meta.num_columns > MAX_COLUMNS:
                raise ValueError("Parquet exceeds table bounds")
            if sum(meta.row_group(i).total_byte_size for i in range(meta.num_row_groups)) > MAX_BYTES:
                raise ValueError("Parquet decompressed size exceeds bounds")
            if any(not (pa.types.is_string(f.type) or pa.types.is_large_string(f.type) or
                        pa.types.is_integer(f.type) or pa.types.is_floating(f.type) or
                        pa.types.is_boolean(f.type) or pa.types.is_timestamp(f.type)) for f in source.schema_arrow):
                raise ValueError("Parquet must contain scalar columns only")
            names = source.schema_arrow.names
            if len(names) != len(set(names)):
                raise ValueError("duplicate Parquet columns")
            raw = [names]
            decoded_size = 0
            # Dictionary encoding can make expanded strings much larger than
            # stored page sizes. Bound each decoded row before Python expansion.
            for batch in source.iter_batches(batch_size=1, use_threads=False):
                decoded_size += batch.nbytes
                if decoded_size > MAX_BYTES or len(raw) + batch.num_rows - 1 > MAX_ROWS:
                    raise ValueError("Parquet decoded table exceeds bounds")
                raw.extend([[row[name] for name in names] for row in batch.to_pylist()])
        except ImportError as exc:
            raise ValueError("Parquet import requires the existing optional pyarrow dependency") from exc
    elif extension == ".csv":
        raw = []
        for row in csv.reader(io.StringIO(data.decode("utf-8-sig")), strict=True):
            if len(raw) > MAX_ROWS or len(row) > MAX_COLUMNS:
                raise ValueError("CSV exceeds table bounds")
            raw.append(row)
    else:
        raise ValueError("unsupported artifact format")
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
                if type(value) is bool or isinstance(value, str) and value.lower() in ("true", "false"):
                    raise ValueError("boolean values cannot stand for numeric artifact values")
                if (type(value) is int or isinstance(value, str) and re.fullmatch(r"[+-]?\d+", value.strip())) and abs(int(value)) > 2 ** 53:
                    raise ValueError("numeric integer artifact values exceed exact binary64 range")
                row.append(float(value))
            else:
                if column["type"] == "string" and type(value) is not str:
                    raise ValueError("artifact identity/state columns require strings")
                row.append(value.isoformat() if hasattr(value, "isoformat") else str(value))
        rows.append(row)
    return table(columns, rows, keys)


def preview(source_root: Path, run: str) -> dict:
    """Read one explicit run, retain bytes and semantics, create no files/database."""
    if type(run) is not str or not _RUN.fullmatch(run):
        raise ValueError("run must be an existing SHA-256 run directory")
    root = local_path(source_root)
    target = root / run
    try:
        with pinned_directory(target) as parent_fd:
            return _preview_pinned(target, run, parent_fd)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError("source is missing, unsafe, unreadable or malformed; no import performed") from exc


def _inventory(target):
    names = set()
    for entry in target.iterdir():
        names.add(entry.name)
        if len(names) > len(_JSON) + len(_FRAMES):
            raise ValueError("unexpected artifacts in selected run")
    return names


def _preview_pinned(target, run, parent_fd):
    names = _inventory(target)
    selected = list(_JSON)
    for stem in _FRAMES:
        matches = [f"{stem}{ext}" for ext in (".csv", ".parquet") if f"{stem}{ext}" in names]
        if len(matches) != 1:
            raise ValueError("each frame requires exactly one CSV or Parquet artifact")
        selected.extend(matches)
    if names != set(selected):
        raise ValueError("unexpected artifacts in selected run")
    blobs = {}
    total = 0
    for name in selected:
        data = _read(target / name, parent_fd=parent_fd)
        total += len(data)
        if total > MAX_BYTES:
            raise ValueError("combined run exceeds 4 MiB")
        blobs[name] = data
    raw_metadata = read_json(blobs["metadata.json"])
    validate_source_metadata(raw_metadata)
    for key in ("train_run_hash", "continuous_config_hash", "feature_config_hash", "label_config_hash",
                "dataset_config_hash", "model_config_hash", "model_type", "task_type", "label_column"):
        if type(raw_metadata.get(key)) is not str:
            raise ValueError("source identity fields require strings")
    metadata = ExperimentRun.model_validate(raw_metadata)
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
    if _inventory(target) != names or any(_read(target / name, parent_fd=parent_fd) != data for name, data in blobs.items()):
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
