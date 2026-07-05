"""
Store-to-continuous adapter (Phase 8 — commit 1).

Bridges the Phase 7 raw store to the already-built continuous-futures machinery:
enumerate the per-contract raw bars stored for one ``(source, root)``, stack them
into a single canonical raw frame, and hand that to the **existing**
``build_continuous_futures`` / ``continuous_config_hash`` / ``compute_roll_schedule``.

This commit ships **helpers only** — no CLI, no writes/persistence, no report
JSON.  It invents **no new continuous-construction algorithm and no new hash**
(per-contract and stacked hashes both reuse
:func:`app.datastore.store.raw_data_version_hash`).  Reads only from the store's
``raw/futures`` namespace; never writes; no network.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.datastore.futures_continuous import (
    build_continuous_futures,
    compute_roll_schedule,
    continuous_config_hash,
)
from app.datastore.store import (
    RawFuturesStore,
    raw_data_version_hash,
    validate_raw_futures,
)
from app.instruments import FuturesSpec, get_instrument

__all__ = [
    "ContinuousSourceError",
    "ContinuousBuildResult",
    "list_stored_contracts",
    "read_root_raw_frame",
    "build_continuous_from_store",
    "serialize_continuous_build_result",
]


class ContinuousSourceError(ValueError):
    """Raised when the store has no processable raw contracts for ``(source, root)``
    (or the resolved spec is not a futures spec)."""


@dataclass(frozen=True)
class ContinuousBuildResult:
    """Provenance + summary of one continuous build (no persistence in this commit).

    ``output_path`` is always ``""`` here — Commit 1 never writes; a later commit's
    persistence flags fill it with a base-relative path.
    """

    root_symbol: str
    source: str
    adjustment_method: str
    contracts: list[str]
    contract_version_hashes: dict[str, str]
    raw_data_version_hash: str
    continuous_config_hash: str
    rows: int
    start: str
    end: str
    roll_events: list[dict]
    output_path: str = ""


def list_stored_contracts(store: RawFuturesStore, source: str, root: str) -> list[str]:
    """Return the sorted, unique contract symbols stored for ``(source, root)``.

    Uses only the store's **public** ``raw_path`` helper to locate the contract
    directory (``<base>/raw/futures/<source>/<root>/``) and globs both storage
    formats.  Returns ``[]`` when nothing is stored.  Reads no bar data, writes
    nothing, no network.  (Contract symbols are uppercase alphanumeric, so the
    on-disk filename stem equals the contract symbol.)
    """
    contract_dir = store.raw_path(root, "__probe__", source).parent
    if not contract_dir.exists():
        return []
    stems: set[str] = set()
    for ext in ("parquet", "csv"):
        for path in contract_dir.glob(f"*.{ext}"):
            if path.is_file():
                stems.add(path.stem)
    return sorted(stems)


def read_root_raw_frame(store: RawFuturesStore, source: str, root: str) -> pd.DataFrame:
    """Read every stored contract for ``(source, root)`` and stack into one
    canonical raw frame (normalized via :func:`validate_raw_futures`).

    Raises :class:`ContinuousSourceError` if no contracts are stored.  No writes.
    """
    contracts = list_stored_contracts(store, source, root)
    if not contracts:
        raise ContinuousSourceError(
            f"no stored raw contracts for source={source!r} root={root!r} under "
            f"{store.raw_root()}"
        )
    frames = [store.read_raw(root, contract, source) for contract in contracts]
    stacked = pd.concat(frames, ignore_index=True)
    return validate_raw_futures(stacked)


def _adjustment_str(method: object) -> str:
    """Canonical string for the adjustment method (enum -> its value)."""
    return str(getattr(method, "value", method))


def build_continuous_from_store(
    store: RawFuturesStore,
    *,
    source: str,
    root: str,
    adjustment_method: str = "ratio",
    spec: FuturesSpec | None = None,
) -> tuple[pd.DataFrame, ContinuousBuildResult]:
    """Build one continuous series for ``(source, root)`` from stored raw bars.

    Reads + stacks the stored contracts, resolves the spec via
    :func:`get_instrument` (unless supplied), then reuses the existing
    ``build_continuous_futures`` / ``continuous_config_hash`` /
    ``compute_roll_schedule``.  Returns the continuous frame and a
    :class:`ContinuousBuildResult` with full raw -> continuous provenance.

    **No writes** — persistence is a later commit.  Raises
    :class:`ContinuousSourceError` (no contracts / non-futures spec),
    ``UnknownInstrumentError`` (unknown root), ``ContinuousBuildError`` /
    ``RollScheduleError`` (unresolvable roll), or ``ValueError`` (invalid
    adjustment method) — all before anything could be written.
    """
    stacked = read_root_raw_frame(store, source, root)
    contracts = sorted(stacked["contract_symbol"].unique().tolist())

    if spec is None:
        spec = get_instrument(root)
    if not isinstance(spec, FuturesSpec):
        raise ContinuousSourceError(
            f"spec for root {root!r} is not a FuturesSpec (got {type(spec).__name__}); "
            f"continuous construction needs a futures spec"
        )

    # Existing machinery only — no new algorithm, no new hash. Invalid adjustment
    # methods raise inside these calls, before the result is assembled.
    continuous = build_continuous_futures(stacked, spec, adjustment_method=adjustment_method)
    cc_hash = continuous_config_hash(stacked, spec, adjustment_method=adjustment_method)
    events = compute_roll_schedule(stacked, spec)

    contract_hashes = {
        contract: raw_data_version_hash(store.read_raw(root, contract, source))
        for contract in contracts
    }
    roll_events = [
        {
            "from_contract": ev.from_contract,
            "to_contract": ev.to_contract,
            "roll_date": ev.roll_date.isoformat(),
            "decision_date": ev.decision_date.isoformat(),
            "roll_reason": ev.roll_reason,
            "rule_used": _adjustment_str(ev.rule_used),
            "metadata": dict(ev.metadata),  # JSON-safe (iso strings / ints / bools)
        }
        for ev in events
    ]

    if len(continuous):
        ts = continuous["timestamp"]
        start = ts.iloc[0].date().isoformat()
        end = ts.iloc[-1].date().isoformat()
    else:
        start = end = ""

    result = ContinuousBuildResult(
        root_symbol=root,
        source=source,
        adjustment_method=_adjustment_str(adjustment_method),
        contracts=contracts,
        contract_version_hashes=contract_hashes,
        raw_data_version_hash=raw_data_version_hash(stacked),
        continuous_config_hash=cc_hash,
        rows=int(len(continuous)),
        start=start,
        end=end,
        roll_events=roll_events,
        output_path="",  # no persistence in this commit
    )
    return continuous, result


def serialize_continuous_build_result(
    result: ContinuousBuildResult, *, output_path: str = "", report_only: bool = True
) -> dict:
    """Return a plain, JSON-safe dict for a strict-JSON provenance report.

    ``output_path`` / ``report_only`` describe what the caller actually did (the
    result itself carries no persistence info), so the CLI passes the base-relative
    (or user) path and whether continuous output was written.  Every value is a
    string / int / bool / list / dict — no floats — so
    ``json.dumps(..., allow_nan=False)`` can never emit ``NaN`` / ``Infinity``.
    """
    return {
        "root_symbol": result.root_symbol,
        "source": result.source,
        "adjustment_method": result.adjustment_method,
        "contracts": list(result.contracts),
        "contract_version_hashes": dict(result.contract_version_hashes),
        "raw_data_version_hash": result.raw_data_version_hash,
        "continuous_config_hash": result.continuous_config_hash,
        "rows": result.rows,
        "start": result.start,
        "end": result.end,
        "roll_events": [dict(ev) for ev in result.roll_events],
        "output_path": output_path,
        "report_only": report_only,
    }
