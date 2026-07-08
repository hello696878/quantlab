"""
Phase 11 (commit 1) — local experiment batch / sweep config + grid expansion.

This module adds the *config layer only*: a frozen ``LocalExperimentBatchConfig``
(a base :class:`LocalExperimentConfig` + a sweep ``grid`` + batch policy) and
``expand_grid``, which turns a base config + grid into a **deterministic** list of
fully-validated ``LocalExperimentConfig`` values.

It is pure and offline: it imports **only** the Phase 9 config — no experiment
runner, and none of the model-training or feature / label builders — does no I/O,
and touches no network / vendor / ML framework.  The optional
``batch_config_hash`` manifest fingerprint (Appendix L §L.6) is **deferred** to
the commit that adds the runner result / manifest, so there is deliberately no
hashing here.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.local_pipeline.config import LocalExperimentConfig

__all__ = [
    "BatchError",
    "LocalExperimentBatchConfig",
    "batch_item_id",
    "expand_grid",
]

_ON_ERROR_VALUES: tuple[str, ...] = ("continue", "stop")


class BatchError(ValueError):
    """Batch-specific spec failure — an empty grid, an unknown grid field, an
    empty value list, or a bad item index.  Kept distinct from Phase 9 /
    ``ExperimentStore`` errors so callers can tell a *batch-spec* problem from a
    *run* problem."""


def batch_item_id(index: int) -> str:
    """Stable, deterministic item id: ``0 -> 'item_0000'``, ``12 -> 'item_0012'``.

    Raises :class:`BatchError` for a negative index (no hashing involved)."""
    if index < 0:
        raise BatchError(f"item index must be non-negative, got {index}")
    return f"item_{index:04d}"


def _validate_grid_spec(field_names: frozenset[str], grid: Mapping[str, Any]) -> None:
    """Raise :class:`BatchError` unless ``grid`` is a well-formed sweep spec:
    non-empty, every key a real ``LocalExperimentConfig`` field, and every value a
    non-empty list / tuple of candidates.

    It deliberately does **not** validate individual candidate *values* — that
    happens when each expanded config is reconstructed, so Phase 9 field / model
    validators (ratio-only, feature/label naming, window ordering) re-run there.
    """
    if not grid:
        raise BatchError("grid must not be empty")

    unknown = sorted(k for k in grid if k not in field_names)
    if unknown:
        raise BatchError(
            f"unknown grid field(s) {unknown}; grid keys must be LocalExperimentConfig fields"
        )

    for key, values in grid.items():
        if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
            raise BatchError(
                f"grid[{key!r}] must be a non-empty list of candidate values"
            )
        if len(values) == 0:
            raise BatchError(f"grid[{key!r}] must have at least one candidate value")


class LocalExperimentBatchConfig(BaseModel):
    """A frozen batch / sweep spec: a base :class:`LocalExperimentConfig`, a
    ``grid`` of ``field -> [candidate values]``, and batch execution policy.

    Validation mirrors Appendix L §L.5 — the grid must be non-empty, every key a
    real ``LocalExperimentConfig`` field, and every value list non-empty;
    ``on_error`` must be ``"continue"`` or ``"stop"``.  Ratio-only and model-type
    rules are **not** relaxed here; they are re-checked per expanded config.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    base: LocalExperimentConfig
    grid: dict[str, list]
    overwrite: bool = False
    on_error: str = "continue"

    @field_validator("on_error")
    @classmethod
    def _validate_on_error(cls, v: str) -> str:
        if v not in _ON_ERROR_VALUES:
            raise ValueError(f"on_error must be one of {_ON_ERROR_VALUES}, got {v!r}")
        return v

    @model_validator(mode="after")
    def _validate_grid(self) -> "LocalExperimentBatchConfig":
        _validate_grid_spec(frozenset(LocalExperimentConfig.model_fields), self.grid)
        return self

    def expand(self) -> list[LocalExperimentConfig]:
        """Expand this spec into a deterministic list of validated configs."""
        return expand_grid(self.base, self.grid)


def expand_grid(
    base: LocalExperimentConfig, grid: Mapping[str, Sequence[Any]]
) -> list[LocalExperimentConfig]:
    """Deterministic cartesian product of ``base`` over ``grid``.

    Ordering is fixed: grid **keys sorted alphabetically**, each key's **values in
    user-provided order** (``itertools.product`` varies the last sorted key
    fastest).  Every combination is reconstructed as a **new**
    ``LocalExperimentConfig`` so all Phase 9 validators re-run — a non-ratio
    ``adjustment_method`` or a bad feature column therefore fails via
    ``LocalExperimentConfig`` validation, not silently.

    Raises :class:`BatchError` for an empty grid, an unknown grid field, or an
    empty value list.  Does not mutate ``base`` or ``grid``; no I/O, no network,
    no hashing.
    """
    _validate_grid_spec(frozenset(LocalExperimentConfig.model_fields), grid)

    keys = sorted(grid)
    value_lists = [list(grid[k]) for k in keys]
    base_fields = base.model_dump()

    configs: list[LocalExperimentConfig] = []
    for combo in itertools.product(*value_lists):
        overrides = dict(zip(keys, combo))
        configs.append(LocalExperimentConfig(**{**base_fields, **overrides}))
    return configs
