"""
Raw futures data: schema validation + local storage (Phase 1 — commit 2).

Scope is deliberately narrow: **raw individual-contract** futures bars only.
No continuous stitching, no rollover, no ratio/Panama adjustment (those land in
``data/futures_continuous.py`` in a later commit).

Three public pieces:

* :func:`validate_raw_futures` — validate + normalize a raw OHLCV frame.
* :func:`raw_data_version_hash` — deterministic content hash of normalized data.
* :class:`RawFuturesStore` — write/read raw bars under a ``raw/futures`` namespace
  that is structurally separate from the (reserved) ``continuous/futures`` one.

Normalization choices (V1, documented on purpose):

* Timestamps are normalized to **UTC, tz-aware** (naive is assumed UTC; tz-aware
  is converted).  The ``timezone`` column is retained as metadata so the data
  layer can convert back for display.  This keeps hashing/round-trip
  deterministic without depending on the OS time-zone database.
* Only the required columns are kept (extras dropped) so storage and the version
  hash stay schema-stable.
* The store round-trips the *normalized* frame, not a byte-identical copy of the
  caller's input (dtypes are canonicalized).
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Canonical raw-contract schema (order matters: storage + hash use it).
REQUIRED_COLUMNS: list[str] = [
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "open_interest",
    "root_symbol",
    "contract_symbol",
    "expiry",
    "source",
    "timezone",
]

_PRICE_COLUMNS = ["open", "high", "low", "close"]
_STRING_COLUMNS = ["root_symbol", "contract_symbol", "source", "timezone"]

# Canonical continuous-series schema (built by app.datastore.futures_continuous).
CONTINUOUS_COLUMNS: list[str] = [
    "timestamp",
    "root_symbol",
    "active_contract",
    "open_raw",
    "high_raw",
    "low_raw",
    "close_raw",
    "volume",
    "open_interest",
    "adjustment_method",
    "adjustment_factor",
    "open_adjusted",
    "high_adjusted",
    "low_adjusted",
    "close_adjusted",
    "roll_flag",
    "roll_reason",
]

_CONTINUOUS_FLOAT_COLUMNS = [
    "open_raw", "high_raw", "low_raw", "close_raw",
    "open_adjusted", "high_adjusted", "low_adjusted", "close_adjusted",
    "open_interest", "adjustment_factor",
]

# Storage namespace layout (raw kept separate from continuous/adjusted).
RAW_SUBDIR = "raw"
CONTINUOUS_SUBDIR = "continuous"
FUTURES_SUBDIR = "futures"


class RawSchemaError(ValueError):
    """Raised when a raw futures dataframe violates the schema/validation rules."""


# --------------------------------------------------------------------------- #
# Validation / normalization
# --------------------------------------------------------------------------- #


def _to_datetime(series: pd.Series, col: str) -> pd.Series:
    try:
        return pd.to_datetime(series, utc=True, errors="raise")
    except (ValueError, TypeError) as exc:
        raise RawSchemaError(f"column {col!r} is not parseable as datetime: {exc}") from exc


def _to_numeric(series: pd.Series, col: str) -> pd.Series:
    try:
        return pd.to_numeric(series, errors="raise")
    except (ValueError, TypeError) as exc:
        raise RawSchemaError(f"column {col!r} has non-numeric values: {exc}") from exc


def validate_raw_futures(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize a raw individual-contract futures dataframe.

    Returns a new frame with canonical dtypes and column order, sorted by
    ``(contract_symbol, timestamp)``.  Raises :class:`RawSchemaError` on any
    violation.
    """
    if not isinstance(df, pd.DataFrame):
        raise RawSchemaError(f"expected a pandas DataFrame, got {type(df).__name__}")

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise RawSchemaError(f"missing required columns: {missing}")

    out = df.loc[:, REQUIRED_COLUMNS].copy()

    # --- datetimes (normalized to UTC, tz-aware) ---
    out["timestamp"] = _to_datetime(out["timestamp"], "timestamp")
    out["expiry"] = _to_datetime(out["expiry"], "expiry")
    if out["timestamp"].isna().any():
        raise RawSchemaError("timestamp has missing/unparseable values")
    if out["expiry"].isna().any():
        raise RawSchemaError("expiry has missing/unparseable values")

    # --- prices ---
    for col in _PRICE_COLUMNS:
        out[col] = _to_numeric(out[col], col).astype("float64")
    if out[_PRICE_COLUMNS].isna().to_numpy().any():
        raise RawSchemaError("open/high/low/close must not contain missing values")
    if (out[_PRICE_COLUMNS] <= 0).to_numpy().any():
        raise RawSchemaError("open/high/low/close must be strictly positive")

    row_hi = out[["open", "close"]].max(axis=1)
    row_lo = out[["open", "close"]].min(axis=1)
    if (out["high"] < row_hi).any():
        raise RawSchemaError("high must be >= max(open, close) on every row")
    if (out["low"] > row_lo).any():
        raise RawSchemaError("low must be <= min(open, close) on every row")
    if (out["high"] < out["low"]).any():
        raise RawSchemaError("high must be >= low on every row")

    # --- volume (non-negative, integer-valued -> int64) ---
    vol = _to_numeric(out["volume"], "volume")
    if vol.isna().any():
        raise RawSchemaError("volume must not contain missing values")
    if (vol < 0).any():
        raise RawSchemaError("volume must be non-negative")
    if not (vol % 1 == 0).all():
        raise RawSchemaError("volume must be integer-valued")
    out["volume"] = vol.astype("int64")

    # --- open_interest (nullable; if present must be non-negative) ---
    oi = _to_numeric(out["open_interest"], "open_interest")
    present = oi.notna()
    if (oi[present] < 0).any():
        raise RawSchemaError("open_interest must be non-negative where present")
    out["open_interest"] = oi.astype("float64")

    # --- string identity columns (non-empty) ---
    for col in _STRING_COLUMNS:
        s = out[col]
        if s.isna().any():
            raise RawSchemaError(f"{col} has missing values")
        s = s.astype(str).str.strip()
        if (s == "").any():
            raise RawSchemaError(f"{col} must be non-empty")
        out[col] = s

    # --- uniqueness ---
    if out.duplicated(subset=["contract_symbol", "timestamp"]).any():
        raise RawSchemaError("duplicate rows for the same (contract_symbol, timestamp)")

    out = out.sort_values(["contract_symbol", "timestamp"], kind="stable").reset_index(drop=True)
    return out[REQUIRED_COLUMNS]


# --------------------------------------------------------------------------- #
# Deterministic content hash
# --------------------------------------------------------------------------- #


def raw_data_version_hash(df: pd.DataFrame) -> str:
    """Return a sha256 hex digest of the normalized raw data.

    Stable across row order (normalization sorts first); changes when any value,
    any row, or a schema-relevant field changes.
    """
    norm = validate_raw_futures(df)
    canon = pd.DataFrame(index=norm.index)
    canon["timestamp"] = norm["timestamp"].map(lambda t: t.isoformat())
    canon["expiry"] = norm["expiry"].map(lambda t: t.isoformat())
    for col in _PRICE_COLUMNS:
        canon[col] = norm[col].map(lambda v: format(float(v), ".12g"))
    canon["volume"] = norm["volume"].map(lambda v: str(int(v)))
    canon["open_interest"] = norm["open_interest"].map(
        lambda v: "" if pd.isna(v) else format(float(v), ".12g")
    )
    for col in _STRING_COLUMNS:
        canon[col] = norm[col]
    canon = canon[REQUIRED_COLUMNS]
    payload = canon.to_csv(index=False, lineterminator="\n")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Continuous-series normalization
# --------------------------------------------------------------------------- #


def finalize_continuous(df: pd.DataFrame) -> pd.DataFrame:
    """Validate column presence and canonicalize dtypes/order of a continuous frame.

    Used by both the continuous builder and the store reader so a written frame
    round-trips to an identical normalized frame.
    """
    missing = [c for c in CONTINUOUS_COLUMNS if c not in df.columns]
    if missing:
        raise RawSchemaError(f"continuous frame missing required columns: {missing}")
    out = df.loc[:, CONTINUOUS_COLUMNS].copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
    for col in _CONTINUOUS_FLOAT_COLUMNS:
        out[col] = pd.to_numeric(out[col]).astype("float64")
    out["volume"] = pd.to_numeric(out["volume"]).astype("int64")
    roll_flag = out["roll_flag"]
    if roll_flag.dtype == object:
        roll_flag = roll_flag.map(lambda v: str(v).strip().lower() in ("true", "1", "yes"))
    out["roll_flag"] = roll_flag.astype(bool)
    for col in ["root_symbol", "active_contract", "adjustment_method"]:
        out[col] = out[col].astype(str)
    out["roll_reason"] = out["roll_reason"].fillna("").astype(str)
    out = out.sort_values("timestamp", kind="stable").reset_index(drop=True)
    return out[CONTINUOUS_COLUMNS]


# --------------------------------------------------------------------------- #
# Storage
# --------------------------------------------------------------------------- #


def _parquet_available() -> bool:
    return (
        importlib.util.find_spec("pyarrow") is not None
        or importlib.util.find_spec("fastparquet") is not None
    )


def _slug(value: object) -> str:
    """Filesystem-safe slug for path components (no hard-coded paths)."""
    return re.sub(r"[^0-9A-Za-z._-]+", "_", str(value).strip())


class RawFuturesStore:
    """Local store for raw individual-contract futures bars.

    Files are written per ``(source, root_symbol, contract_symbol)`` under a
    ``<base_dir>/raw/futures`` tree, kept structurally separate from the
    reserved ``<base_dir>/continuous/futures`` tree (so raw writes can never
    overwrite continuous/adjusted data).

    Parquet is preferred; if no parquet engine is installed the store falls back
    to CSV and records this explicitly via :attr:`storage_format` (and a log line).
    """

    def __init__(self, base_dir: str | Path, prefer_parquet: bool = True) -> None:
        self.base_dir = Path(base_dir)
        self._use_parquet = bool(prefer_parquet and _parquet_available())
        self.storage_format = "parquet" if self._use_parquet else "csv"
        if not self._use_parquet:
            logger.info(
                "RawFuturesStore: no parquet engine available; using explicit CSV fallback."
            )

    # --- paths ---

    def raw_root(self) -> Path:
        return self.base_dir / RAW_SUBDIR / FUTURES_SUBDIR

    def continuous_root(self) -> Path:
        """Reserved namespace for continuous/adjusted data (not written here)."""
        return self.base_dir / CONTINUOUS_SUBDIR / FUTURES_SUBDIR

    def raw_path(
        self,
        root_symbol: str,
        contract_symbol: str,
        source: str,
        fmt: str | None = None,
    ) -> Path:
        ext = fmt or self.storage_format
        return (
            self.raw_root()
            / _slug(source)
            / _slug(root_symbol)
            / f"{_slug(contract_symbol)}.{ext}"
        )

    # --- write / read ---

    def write_raw(self, df: pd.DataFrame) -> list[Path]:
        """Validate, then write one file per contract. Returns written paths."""
        norm = validate_raw_futures(df)
        written: list[Path] = []
        group_keys = ["source", "root_symbol", "contract_symbol"]
        for (source, root, contract), group in norm.groupby(group_keys, sort=True):
            group = group.reset_index(drop=True)
            path = self.raw_path(root, contract, source)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._write_one(group, path)
            written.append(path)
        return written

    def _write_one(self, group: pd.DataFrame, path: Path) -> None:
        if self.storage_format == "parquet":
            group.to_parquet(path, index=False)
            return
        out = group.copy()
        out["timestamp"] = out["timestamp"].map(lambda t: t.isoformat())
        out["expiry"] = out["expiry"].map(lambda t: t.isoformat())
        out.to_csv(path, index=False, lineterminator="\n")

    def read_raw(self, root_symbol: str, contract_symbol: str, source: str) -> pd.DataFrame:
        """Read one contract back, normalized identically to :func:`validate_raw_futures`."""
        candidates = (self.storage_format, "parquet" if self.storage_format == "csv" else "csv")
        for fmt in candidates:
            path = self.raw_path(root_symbol, contract_symbol, source, fmt=fmt)
            if path.exists():
                raw = pd.read_parquet(path) if fmt == "parquet" else pd.read_csv(path)
                return validate_raw_futures(raw)
        raise FileNotFoundError(
            f"no raw data for root={root_symbol!r} contract={contract_symbol!r} "
            f"source={source!r} under {self.raw_root()}"
        )

    # --- continuous series (separate namespace from raw) ---

    def continuous_path(
        self,
        root_symbol: str,
        source: str,
        adjustment_method: str,
        fmt: str | None = None,
    ) -> Path:
        ext = fmt or self.storage_format
        return (
            self.continuous_root()
            / _slug(source)
            / _slug(root_symbol)
            / f"{_slug(adjustment_method)}.{ext}"
        )

    def write_continuous(self, df: pd.DataFrame, source: str) -> Path:
        """Validate + write one continuous series (single root, single method)."""
        fin = finalize_continuous(df)
        roots = fin["root_symbol"].unique()
        methods = fin["adjustment_method"].unique()
        if len(roots) != 1 or len(methods) != 1:
            raise RawSchemaError(
                "continuous frame must contain exactly one root_symbol and one "
                f"adjustment_method (got roots={list(roots)}, methods={list(methods)})"
            )
        path = self.continuous_path(roots[0], source, methods[0])
        path.parent.mkdir(parents=True, exist_ok=True)
        if self.storage_format == "parquet":
            fin.to_parquet(path, index=False)
        else:
            out = fin.copy()
            out["timestamp"] = out["timestamp"].map(lambda t: t.isoformat())
            out.to_csv(path, index=False, lineterminator="\n")
        return path

    def read_continuous(
        self, root_symbol: str, source: str, adjustment_method: str
    ) -> pd.DataFrame:
        """Read one continuous series back, normalized via :func:`finalize_continuous`."""
        candidates = (self.storage_format, "parquet" if self.storage_format == "csv" else "csv")
        for fmt in candidates:
            path = self.continuous_path(root_symbol, source, adjustment_method, fmt=fmt)
            if path.exists():
                raw = pd.read_parquet(path) if fmt == "parquet" else pd.read_csv(path)
                return finalize_continuous(raw)
        raise FileNotFoundError(
            f"no continuous data for root={root_symbol!r} source={source!r} "
            f"adjustment={adjustment_method!r} under {self.continuous_root()}"
        )
