"""
Phase 11 (commit 2) — sequential batch runner over the Phase 9 local ML pipeline.

``run_local_experiment_batch`` executes an ordered list of ``LocalExperimentConfig``
values **one at a time** (no parallelism), each through the existing Phase 9
``run_local_futures_ml_experiment`` — so it adds no new model, no new feature /
label logic, and no new backtest.  Successful runs are persisted through the
caller's ``ExperimentStore`` (Phase 5); each item records its status, the Phase 9
hash chain, a relative artifact directory, or a captured error string.

``batch_config_hash`` is a **batch manifest fingerprint only** — it identifies
"which configs, in which order, run under which policy".  It is deliberately *not*
part of the ML lineage: it never enters and never replaces the Phase 9
raw -> ... -> train_run chain or any ``train_run_hash``.  It reuses the existing
reproducibility helper (``compute_config_hash`` -> canonical JSON + SHA-256), so no
new hashing primitive and no new ML hash chain are introduced.

This module intentionally stays decoupled from the Phase 10 report / compare
export layer (that is wired at the CLI layer, not here).  No network, no vendor,
no live data.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Optional

from app.datastore.store import RawFuturesStore
from app.experiments import ExperimentStore
from app.local_pipeline import LocalExperimentConfig, run_local_futures_ml_experiment
from app.reproducibility import compute_config_hash

from app.batch_experiments.config import BatchError, batch_item_id

__all__ = [
    "LocalExperimentBatchItem",
    "LocalExperimentBatchResult",
    "batch_config_hash",
    "run_local_experiment_batch",
    "summarize_batch_result",
]

_ON_ERROR_VALUES: tuple[str, ...] = ("continue", "stop")

_HASH_CHAIN_FIELDS: tuple[str, ...] = (
    "raw_data_version_hash",
    "continuous_config_hash",
    "feature_config_hash",
    "label_config_hash",
    "dataset_config_hash",
    "model_config_hash",
    "train_run_hash",
)


@dataclass(frozen=True)
class LocalExperimentBatchItem:
    """One item in a batch run.

    ``status`` is ``"ok"`` (ran and, if a store was given, saved — carries
    ``train_run_hash`` + ``hash_chain`` + relative ``artifact_dir``), ``"failed"``
    (carries ``error`` as ``"ExceptionType: message"``), or ``"skipped"`` (dry-run,
    or not reached because the batch stopped after an earlier failure — ``error``
    holds the reason)."""

    item_id: str
    config: LocalExperimentConfig
    status: str
    train_run_hash: Optional[str] = None
    hash_chain: Optional[dict] = None
    artifact_dir: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class LocalExperimentBatchResult:
    """The outcome of a batch run: the ordered ``items``, status counts, the
    successful ``train_run_hashes`` (in execution order), and the
    ``batch_config_hash`` manifest fingerprint (not an ML lineage hash)."""

    items: tuple[LocalExperimentBatchItem, ...]
    n_total: int
    n_ok: int
    n_failed: int
    n_skipped: int
    train_run_hashes: tuple[str, ...]
    batch_config_hash: str


def batch_config_hash(
    configs: Sequence[LocalExperimentConfig],
    *,
    on_error: str,
    dry_run: bool,
) -> str:
    """Deterministic **batch manifest fingerprint** (full SHA-256 hex).

    Hashes only the ordered, JSON-normalized config dumps plus the execution
    policy (``on_error`` / ``dry_run``) via the existing reproducibility helper —
    no timestamps, no absolute paths, no model outputs.  This identifies the
    *batch spec*; it is **not** an ML lineage hash and does **not** replace any
    ``train_run_hash`` (each run keeps the existing Phase 9 hash chain).
    """
    manifest = {
        "configs": [c.model_dump(mode="json") for c in configs],
        "policy": {"on_error": on_error, "dry_run": bool(dry_run)},
    }
    return compute_config_hash(manifest)[1]


def _hash_chain(result: Any) -> dict:
    """Extract the Phase 9 hash chain from a ``LocalExperimentResult``."""
    return {name: getattr(result, name) for name in _HASH_CHAIN_FIELDS}


def _relative_artifact_dir(result: Any, experiment_store: Optional[ExperimentStore]) -> Optional[str]:
    """The persisted run directory as a store-relative, POSIX-style path (safe for
    manifests — no absolute / tmp paths).  ``None`` when nothing was persisted."""
    if experiment_store is None or not getattr(result, "artifact_dir", ""):
        return None
    try:
        rel = os.path.relpath(result.artifact_dir, experiment_store.base_dir)
    except (ValueError, TypeError):
        return None
    return rel.replace(os.sep, "/")


def run_local_experiment_batch(
    raw_store: RawFuturesStore | str,
    configs: Sequence[LocalExperimentConfig],
    *,
    experiment_store: Optional[ExperimentStore],
    on_error: str = "continue",
    dry_run: bool = False,
) -> LocalExperimentBatchResult:
    """Run ``configs`` sequentially through the Phase 9 local ML pipeline.

    ``configs`` is an ordered sequence of ``LocalExperimentConfig`` (e.g. from
    ``expand_grid``).  Execution is strictly sequential with deterministic item ids
    (``item_0000`` ...).  Each successful run is saved through ``experiment_store``
    (duplicate / overwrite behavior follows the existing ``ExperimentStore`` and
    ``config.overwrite``).  Failures are **captured, never masked** as
    ``"ExceptionType: message"``.

    ``dry_run=True`` executes and saves nothing — every item is ``"skipped"``.
    ``on_error="continue"`` records a failure and proceeds; ``on_error="stop"``
    records the failure and marks every remaining item ``"skipped"``.

    Raises :class:`BatchError` for an empty ``configs`` or an invalid ``on_error``.
    """
    configs = list(configs)
    if not configs:
        raise BatchError("configs must be a non-empty sequence of LocalExperimentConfig")
    if on_error not in _ON_ERROR_VALUES:
        raise BatchError(f"on_error must be one of {_ON_ERROR_VALUES}, got {on_error!r}")

    manifest_hash = batch_config_hash(configs, on_error=on_error, dry_run=dry_run)

    items: list[LocalExperimentBatchItem] = []
    stopped = False
    for index, config in enumerate(configs):
        item_id = batch_item_id(index)

        if stopped:
            items.append(
                LocalExperimentBatchItem(
                    item_id=item_id,
                    config=config,
                    status="skipped",
                    error="skipped: batch stopped after an earlier failure (on_error='stop')",
                )
            )
            continue

        if dry_run:
            items.append(
                LocalExperimentBatchItem(
                    item_id=item_id,
                    config=config,
                    status="skipped",
                    error="skipped: dry_run (nothing executed or saved)",
                )
            )
            continue

        try:
            result = run_local_futures_ml_experiment(
                raw_store, config=config, experiment_store=experiment_store
            )
        except Exception as exc:  # noqa: BLE001 — capture any run failure per item
            items.append(
                LocalExperimentBatchItem(
                    item_id=item_id,
                    config=config,
                    status="failed",
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            if on_error == "stop":
                stopped = True
            continue

        items.append(
            LocalExperimentBatchItem(
                item_id=item_id,
                config=config,
                status="ok",
                train_run_hash=result.train_run_hash,
                hash_chain=_hash_chain(result),
                artifact_dir=_relative_artifact_dir(result, experiment_store),
            )
        )

    n_ok = sum(1 for it in items if it.status == "ok")
    n_failed = sum(1 for it in items if it.status == "failed")
    n_skipped = sum(1 for it in items if it.status == "skipped")
    train_run_hashes = tuple(
        it.train_run_hash for it in items if it.status == "ok" and it.train_run_hash
    )

    return LocalExperimentBatchResult(
        items=tuple(items),
        n_total=len(items),
        n_ok=n_ok,
        n_failed=n_failed,
        n_skipped=n_skipped,
        train_run_hashes=train_run_hashes,
        batch_config_hash=manifest_hash,
    )


def summarize_batch_result(result: LocalExperimentBatchResult) -> dict:
    """A compact, deterministic, JSON-safe summary of a batch result.

    Contains only strings / ints / None / nested string dicts — no floats, so no
    ``NaN`` / ``Infinity`` — and no absolute paths (``artifact_dir`` is
    store-relative).  Item order is execution order.
    """
    return {
        "batch_config_hash": result.batch_config_hash,
        "n_total": result.n_total,
        "n_ok": result.n_ok,
        "n_failed": result.n_failed,
        "n_skipped": result.n_skipped,
        "train_run_hashes": list(result.train_run_hashes),
        "items": [
            {
                "item_id": it.item_id,
                "status": it.status,
                "train_run_hash": it.train_run_hash,
                "error": it.error,
                "artifact_dir": it.artifact_dir,
                "hash_chain": dict(it.hash_chain) if it.hash_chain else None,
            }
            for it in result.items
        ],
    }
