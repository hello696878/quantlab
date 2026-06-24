"""
Supervised dataset assembly (Phase 3 — commit 2).

Joins the Phase 2 feature matrix with the Phase 3 label matrix into a single
supervised dataset with **disjoint** ``feature__`` / ``label__`` namespaces,
carried provenance hashes, and explicit trainable-row flags.

Alignment is **positional by key only** — features and labels are joined on
``(timestamp, root_symbol, active_contract)`` and **never shifted** here.  The
label may carry future information by definition (it is a target); signal/backtest
timing (the ``t+1`` execution shift) is handled later, not in this module.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

KEY_COLUMNS = ["timestamp", "root_symbol", "active_contract"]
_FEATURE_META = ["is_warmup", "source_adjustment_method", "feature_config_hash"]
_LABEL_META = ["label_config_hash"]
_CONT_HASH = "continuous_config_hash"


class DatasetError(ValueError):
    """Raised on invalid or mismatched supervised-dataset inputs."""


def _require_columns(df: pd.DataFrame, columns: list[str], which: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise DatasetError(f"{which} is missing required columns: {missing}")


def build_supervised_dataset(
    feature_df: pd.DataFrame,
    label_df: pd.DataFrame,
    *,
    feature_columns: Optional[list[str]] = None,
    label_columns: Optional[list[str]] = None,
    drop_untrainable: bool = False,
) -> pd.DataFrame:
    """Join features + labels into a leakage-safe supervised dataset.

    Returns one row per session keyed on ``(timestamp, root_symbol,
    active_contract)`` with namespaced ``feature__*`` / ``label__*`` columns,
    the ``is_warmup`` / ``is_label_valid`` / ``is_trainable`` flags, and the
    provenance hashes.  Neither input is mutated; row order is deterministic
    (sorted by timestamp).
    """
    if not isinstance(feature_df, pd.DataFrame) or not isinstance(label_df, pd.DataFrame):
        raise DatasetError("feature_df and label_df must be pandas DataFrames")

    _require_columns(feature_df, KEY_COLUMNS + _FEATURE_META, "feature_df")
    _require_columns(label_df, KEY_COLUMNS + _LABEL_META, "label_df")

    # Resolve feature/label column sets (exclude keys + metadata + provenance).
    reserved_feature = set(KEY_COLUMNS) | set(_FEATURE_META) | {_CONT_HASH}
    reserved_label = set(KEY_COLUMNS) | set(_LABEL_META) | {_CONT_HASH}
    if feature_columns is None:
        feature_columns = [c for c in feature_df.columns if c not in reserved_feature]
    else:
        _require_columns(feature_df, feature_columns, "feature_df (feature_columns)")
    if label_columns is None:
        label_columns = [c for c in label_df.columns if c not in reserved_label]
    else:
        _require_columns(label_df, label_columns, "label_df (label_columns)")

    # Keys must describe exactly the same rows on both sides — no silent drops.
    feat_keys = set(map(tuple, feature_df[KEY_COLUMNS].itertuples(index=False, name=None)))
    label_keys = set(map(tuple, label_df[KEY_COLUMNS].itertuples(index=False, name=None)))
    if feat_keys != label_keys:
        only_feat = len(feat_keys - label_keys)
        only_label = len(label_keys - feat_keys)
        raise DatasetError(
            f"feature/label key mismatch: {only_feat} key(s) only in feature_df, "
            f"{only_label} only in label_df"
        )

    # continuous_config_hash is carried only if actually present (never invented),
    # preferring feature_df to avoid a duplicate column after the merge.
    cont_in_feat = _CONT_HASH in feature_df.columns
    cont_in_label = _CONT_HASH in label_df.columns
    feat_meta = list(_FEATURE_META) + ([_CONT_HASH] if cont_in_feat else [])
    label_meta = list(_LABEL_META) + ([_CONT_HASH] if cont_in_label and not cont_in_feat else [])

    feat_sel = feature_df[KEY_COLUMNS + feature_columns + feat_meta].copy()
    feat_sel = feat_sel.rename(columns={c: f"feature__{c}" for c in feature_columns})
    label_sel = label_df[KEY_COLUMNS + label_columns + label_meta].copy()
    label_sel = label_sel.rename(columns={c: f"label__{c}" for c in label_columns})

    merged = feat_sel.merge(label_sel, on=KEY_COLUMNS, how="inner", validate="one_to_one")

    feature_ns = [f"feature__{c}" for c in feature_columns]
    label_ns = [f"label__{c}" for c in label_columns]

    is_warmup = merged["is_warmup"].astype(bool)
    is_label_valid = merged[label_ns].notna().all(axis=1) if label_ns else pd.Series(True, index=merged.index)
    merged["is_label_valid"] = is_label_valid
    merged["is_trainable"] = (~is_warmup) & is_label_valid

    provenance = [c for c in ("source_adjustment_method", "feature_config_hash",
                              "label_config_hash", _CONT_HASH) if c in merged.columns]
    ordered = (
        KEY_COLUMNS
        + feature_ns
        + label_ns
        + ["is_warmup", "is_label_valid", "is_trainable"]
        + provenance
    )
    merged = merged[ordered].sort_values("timestamp", kind="stable").reset_index(drop=True)

    if drop_untrainable:
        merged = merged[merged["is_trainable"]].reset_index(drop=True)
    return merged
