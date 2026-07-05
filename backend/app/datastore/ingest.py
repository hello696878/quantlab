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

from dataclasses import dataclass, field

import pandas as pd

from app.datastore.daily_bar import FuturesDailyBar
from app.datastore.store import (
    REQUIRED_COLUMNS,
    raw_data_version_hash,
    validate_raw_futures,
)

# Canonical grouping key for one stored contract file, matching
# ``RawFuturesStore.write_raw``'s ``groupby`` order.
GROUP_KEYS: list[str] = ["source", "root_symbol", "contract_symbol"]

__all__ = [
    "GROUP_KEYS",
    "ContractIngestResult",
    "IngestReport",
    "daily_bars_to_frame",
    "contract_group_key",
    "compute_contract_version_hashes",
    "verify_contract_frame_hash",
]


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
    ingest will assert in a later commit: written content == read-back content.
    """
    return raw_data_version_hash(expected) == raw_data_version_hash(actual)
