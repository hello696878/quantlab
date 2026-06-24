"""
Feature input + spec validation (Phase 2 — commit 1).

Read-only validation helpers shared by the (later) feature builder and the tests.
No feature math, no mutation of inputs.
"""

from __future__ import annotations

import pandas as pd

from app.datastore.store import CONTINUOUS_COLUMNS
from app.features.spec import FeatureError, FeatureSpec


def validate_continuous_input(df: pd.DataFrame) -> None:
    """Validate that ``df`` is a Phase 1 continuous frame the feature layer can read.

    Checks every required continuous column is present (timestamp, root_symbol,
    active_contract, adjustment_method, raw + adjusted price columns, roll_flag,
    …).  Read-only — never mutates ``df``.  Raises :class:`FeatureError`.
    """
    if not isinstance(df, pd.DataFrame):
        raise FeatureError(f"expected a pandas DataFrame, got {type(df).__name__}")
    missing = [c for c in CONTINUOUS_COLUMNS if c not in df.columns]
    if missing:
        raise FeatureError(f"continuous frame missing required columns: {missing}")


def validate_feature_specs(specs: list[FeatureSpec]) -> None:
    """Validate a feature spec *set*: unique names, unique output names, types.

    Each :class:`FeatureSpec` is already self-validated at construction; this
    enforces set-level invariants.  Raises :class:`FeatureError`.
    """
    if not isinstance(specs, (list, tuple)) or not specs:
        raise FeatureError("specs must be a non-empty list of FeatureSpec")

    bad = [s for s in specs if not isinstance(s, FeatureSpec)]
    if bad:
        raise FeatureError("all entries must be FeatureSpec instances")

    names = [s.name for s in specs]
    dup_names = sorted({n for n in names if names.count(n) > 1})
    if dup_names:
        raise FeatureError(f"duplicate feature names: {dup_names}")

    output_names = [s.output_name for s in specs]
    dup_outputs = sorted({n for n in output_names if output_names.count(n) > 1})
    if dup_outputs:
        raise FeatureError(f"duplicate output_names: {dup_outputs}")

    for spec in specs:
        if any(w <= 0 for w in spec.windows):  # defensive; already enforced per-spec
            raise FeatureError(f"feature {spec.name!r} has a non-positive window")
