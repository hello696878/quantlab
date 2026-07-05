"""
Local futures ingestion helpers (Phase 7 — commit 1).

Pure, in-memory helpers that bridge validated
:class:`~app.datastore.daily_bar.FuturesDailyBar` records to the canonical
raw-futures frame plus per-contract content hashes.  This commit deliberately
ships **only** the frame builder, result dataclasses, and hash/verify helpers:

* **no file I/O**, **no network**, **no store writes** — the store-backed
  orchestrator, the thin CLI, and the append-only ingestion log land in later
  Phase 7 commits (see ``docs/AI_QUANT_ARCHITECTURE.md`` Appendix H);
* **no new hash function** — per-contract hashing reuses
  :func:`app.datastore.store.raw_data_version_hash`, which hashes the *canonical
  validated* frame (sorted, fixed float format), so it is order-independent and
  value-sensitive.

Grouping order matches :meth:`app.datastore.store.RawFuturesStore.write_raw`
(``source, root_symbol, contract_symbol``) so a later commit can hand the same
groups straight to the store.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from app.datastore.csv_fixtures import load_futures_bars_csv
from app.datastore.daily_bar import FuturesDailyBar
from app.datastore.store import (
    REQUIRED_COLUMNS,
    RawFuturesStore,
    raw_data_version_hash,
    validate_raw_futures,
)

# Canonical grouping key for one stored contract file, matching
# ``RawFuturesStore.write_raw``'s ``groupby`` order.
GROUP_KEYS: list[str] = ["source", "root_symbol", "contract_symbol"]

# Columns the read-back verification compares explicitly (the version hash covers
# every column; these give a clearer message if the round-trip ever diverges).
_VERIFY_KEY_COLUMNS: list[str] = ["timestamp", "root_symbol", "contract_symbol", "close"]

__all__ = [
    "GROUP_KEYS",
    "ContractIngestResult",
    "IngestReport",
    "DuplicateIngestError",
    "IngestVerificationError",
    "daily_bars_to_frame",
    "contract_group_key",
    "compute_contract_version_hashes",
    "verify_contract_frame_hash",
    "ingest_local_futures_csv",
]


class DuplicateIngestError(RuntimeError):
    """Raised when a target contract file already exists and ``overwrite`` is False.

    Raised **before** anything is written, so an existing store file is never
    touched by a rejected duplicate ingest.
    """


class IngestVerificationError(RuntimeError):
    """Raised when store read-back does not match what was written (row count,
    key columns, or content hash) — the round-trip invariant is broken."""


# --------------------------------------------------------------------------- #
# Result dataclasses (populated further by the commit-2 orchestrator)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ContractIngestResult:
    """Per-contract ingestion result.

    ``path`` is left empty by the pure helpers in this module (they perform no
    writes); the store-backed orchestrator fills it with the written store path
    in a later commit.
    """

    root_symbol: str
    contract_symbol: str
    source: str
    rows: int
    version_hash: str
    path: str = ""


@dataclass(frozen=True)
class IngestReport:
    """Summary of one ingest invocation (no log writing in this commit)."""

    input_files: list[str]
    base_dir: str
    roots: list[str]
    contracts: list[ContractIngestResult]
    rows_written: int
    warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Frame builder
# --------------------------------------------------------------------------- #


def daily_bars_to_frame(bars: list[FuturesDailyBar]) -> pd.DataFrame:
    """Build a ``REQUIRED_COLUMNS`` frame from validated daily bars.

    A missing open interest (``bar.open_interest is None``) becomes ``NaN`` — the
    same missing-OI marker :func:`validate_raw_futures` and the store round-trip
    use.  This performs no validation itself; hand the result to
    :func:`validate_raw_futures` / ``RawFuturesStore.write_raw``.
    """
    records = [
        {
            "timestamp": bar.timestamp,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "open_interest": float("nan") if bar.open_interest is None else bar.open_interest,
            "root_symbol": bar.root_symbol,
            "contract_symbol": bar.contract_symbol,
            "expiry": bar.expiry,
            "source": bar.source,
            "timezone": bar.timezone,
        }
        for bar in bars
    ]
    # ``columns=`` pins exact column order even for an empty ``bars`` list.
    return pd.DataFrame(records, columns=REQUIRED_COLUMNS)


# --------------------------------------------------------------------------- #
# Grouping + per-contract hashing (reuse raw_data_version_hash)
# --------------------------------------------------------------------------- #


def contract_group_key(group: pd.DataFrame) -> tuple[str, str, str]:
    """Return ``(source, root_symbol, contract_symbol)`` for a single-contract frame.

    Raises :class:`ValueError` if the frame spans more than one such key, so a
    caller can never silently hash/store two contracts as one.
    """
    keys = group.loc[:, GROUP_KEYS].drop_duplicates()
    if len(keys) != 1:
        found = [tuple(r) for r in keys.to_numpy().tolist()]
        raise ValueError(
            f"expected exactly one (source, root_symbol, contract_symbol) group, "
            f"got {len(keys)}: {found}"
        )
    row = keys.iloc[0]
    return (str(row["source"]), str(row["root_symbol"]), str(row["contract_symbol"]))


def compute_contract_version_hashes(df: pd.DataFrame) -> list[ContractIngestResult]:
    """Validate ``df``, then return one :class:`ContractIngestResult` per contract.

    The frame is normalized once via :func:`validate_raw_futures` (sorting +
    canonical dtypes), grouped by :data:`GROUP_KEYS`, and each group is hashed
    with :func:`raw_data_version_hash`.  No paths, no writes.  Row order in the
    input does not affect the result (validation sorts first).
    """
    norm = validate_raw_futures(df)
    results: list[ContractIngestResult] = []
    for (source, root, contract), group in norm.groupby(GROUP_KEYS, sort=True):
        group = group.reset_index(drop=True)
        results.append(
            ContractIngestResult(
                root_symbol=str(root),
                contract_symbol=str(contract),
                source=str(source),
                rows=int(len(group)),
                version_hash=raw_data_version_hash(group),
            )
        )
    return results


def verify_contract_frame_hash(expected: pd.DataFrame, actual: pd.DataFrame) -> bool:
    """Return ``True`` iff two frames share the same canonical content hash.

    Both frames are hashed via :func:`raw_data_version_hash` (which validates and
    canonicalizes first), so this is the read-back invariant the store-backed
    ingest asserts: written content == read-back content.
    """
    return raw_data_version_hash(expected) == raw_data_version_hash(actual)


# --------------------------------------------------------------------------- #
# Store-backed ingest orchestrator (no ingestion log yet — commit 3)
# --------------------------------------------------------------------------- #


def _contract_file_exists(
    store: RawFuturesStore, root: str, contract: str, source: str
) -> bool:
    """True if a stored file for this contract exists in **either** format.

    ``read_raw`` also probes both formats, so checking both here means a CSV
    file written earlier is still detected as a duplicate by a parquet-mode store.
    """
    return any(
        store.raw_path(root, contract, source, fmt=fmt).exists()
        for fmt in ("parquet", "csv")
    )


def _rel_path(base_dir: Path, path: Path) -> str:
    """Store path relative to ``base_dir`` (POSIX) — never an absolute path in
    the returned report/log."""
    try:
        return path.relative_to(base_dir).as_posix()
    except ValueError:
        return path.name


def ingest_local_futures_csv(
    csv_paths: Sequence[str | Path] | str | Path,
    *,
    base_dir: str | Path,
    source: str | None = None,
    overwrite: bool = False,
    prefer_parquet: bool = True,
) -> IngestReport:
    """Ingest local futures CSV(s) into the ``RawFuturesStore`` raw namespace.

    Fail-first: every input CSV is loaded and validated, and the duplicate guard
    runs, **before** anything is written. On success each contract is written via
    :meth:`RawFuturesStore.write_raw`, read back via
    :meth:`RawFuturesStore.read_raw`, and verified (row count + key columns +
    :func:`raw_data_version_hash`). Local files only; no network; nothing is
    written outside ``base_dir``. No ingestion log is written by this commit.

    :param source: if given, overrides the ``source`` column on every row (the
        store namespace); if ``None``, each file's own ``source`` value is kept.
    :raises FixtureFormatError: an input CSV is invalid / off-cycle / expiry ≠ spec.
    :raises RawSchemaError: the combined frame violates the raw schema.
    :raises DuplicateIngestError: a target contract file already exists and
        ``overwrite`` is False (nothing is written).
    :raises IngestVerificationError: store read-back does not match what was written.
    """
    if isinstance(csv_paths, (str, Path)):
        csv_paths = [csv_paths]
    paths = [Path(p) for p in csv_paths]
    if not paths:
        raise ValueError("ingest_local_futures_csv: no input CSV paths given")
    if source is not None and not str(source).strip():
        raise ValueError("--source must be a non-empty string when provided")

    # 1) Load + validate every input first (loader enforces the §6 cross-checks:
    #    off-cycle month, expiry == spec, timezone == spec). Any failure aborts
    #    before a store is even constructed, so nothing is written.
    bars: list[FuturesDailyBar] = []
    for path in paths:
        bars.extend(load_futures_bars_csv(path))

    # 2) Records -> canonical frame; optional source override; normalize.
    frame = daily_bars_to_frame(bars)
    if source is not None:
        frame = frame.copy()
        frame["source"] = source
    norm = validate_raw_futures(frame)

    base_dir = Path(base_dir)
    store = RawFuturesStore(base_dir, prefer_parquet=prefer_parquet)

    # 3) Group, then run the duplicate guard across ALL groups before any write.
    groups: list[tuple[str, str, str, pd.DataFrame]] = []
    for (grp_source, root, contract), group in norm.groupby(GROUP_KEYS, sort=True):
        groups.append((str(grp_source), str(root), str(contract), group.reset_index(drop=True)))

    if not overwrite:
        existing = [
            f"{s}/{r}/{c}"
            for (s, r, c, _g) in groups
            if _contract_file_exists(store, r, c, s)
        ]
        if existing:
            raise DuplicateIngestError(
                "refusing to overwrite existing contract file(s): "
                f"{', '.join(existing)} (pass overwrite=True / --overwrite)"
            )

    # 4) Write (validates + groups internally), then read back + verify each group.
    store.write_raw(norm)

    contracts: list[ContractIngestResult] = []
    for (grp_source, root, contract, group) in groups:
        read_back = store.read_raw(root, contract, grp_source)
        if len(read_back) != len(group):
            raise IngestVerificationError(
                f"{grp_source}/{root}/{contract}: read-back row count "
                f"{len(read_back)} != written {len(group)}"
            )
        got = read_back.loc[:, _VERIFY_KEY_COLUMNS].reset_index(drop=True)
        want = group.loc[:, _VERIFY_KEY_COLUMNS].reset_index(drop=True)
        if not got.equals(want):
            raise IngestVerificationError(
                f"{grp_source}/{root}/{contract}: read-back key columns differ from written"
            )
        written_hash = raw_data_version_hash(group)
        if raw_data_version_hash(read_back) != written_hash:
            raise IngestVerificationError(
                f"{grp_source}/{root}/{contract}: read-back content hash != written hash"
            )
        contracts.append(
            ContractIngestResult(
                root_symbol=root,
                contract_symbol=contract,
                source=grp_source,
                rows=int(len(group)),
                version_hash=written_hash,
                path=_rel_path(base_dir, store.raw_path(root, contract, grp_source)),
            )
        )

    warnings: list[str] = []
    if store.storage_format == "csv":
        warnings.append("no parquet engine available; wrote CSV fallback")

    return IngestReport(
        input_files=[p.name for p in paths],
        base_dir=str(base_dir),
        roots=sorted({c.root_symbol for c in contracts}),
        contracts=contracts,
        rows_written=sum(c.rows for c in contracts),
        warnings=warnings,
    )
