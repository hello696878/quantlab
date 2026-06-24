"""
Tests for the futures label layer (Phase 3 — commit 1).

Config + basic return-based labels, leakage-safe t+L alignment. Synthetic data
only, no network.
"""

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from app.instruments import AdjustmentMethod
from app.datastore.store import CONTINUOUS_COLUMNS
from app.features import DEFAULT_ES_FEATURES, build_feature_matrix, feature_config_hash
from app.labels import (
    DEFAULT_ES_LABELS,
    DatasetError,
    LabelError,
    LabelSpec,
    LabelType,
    PriceSpace,
    build_label_matrix,
    build_supervised_dataset,
    label_config_hash,
)

LABEL_COLUMNS = [
    "forward_return_1",
    "forward_return_5",
    "direction_1",
    "direction_5",
    "volatility_adjusted_return_5",
]


def _continuous(n: int = 80, adjustment: str = "ratio") -> pd.DataFrame:
    """Single-contract continuous frame (deterministic price path, varying volume)."""
    idx = pd.date_range("2024-01-01", periods=n, freq="B", tz="UTC")
    closes = np.array([5000.0 + 2.0 * i + ((-1) ** i) * 3.0 for i in range(n)])
    highs = closes + 5.0
    lows = closes - 5.0
    df = pd.DataFrame(
        {
            "timestamp": idx,
            "root_symbol": "ES",
            "active_contract": "ESH24",
            "open_raw": closes,
            "high_raw": highs,
            "low_raw": lows,
            "close_raw": closes,
            "volume": np.array([1000 + 10 * i for i in range(n)]),
            "open_interest": 2000.0,
            "adjustment_method": adjustment,
            "adjustment_factor": 1.0,
            "open_adjusted": closes,
            "high_adjusted": highs,
            "low_adjusted": lows,
            "close_adjusted": closes,
            "roll_flag": False,
            "roll_reason": "",
        }
    )
    return df[CONTINUOUS_COLUMNS]


def _valid_spec(name: str = "forward_return_1", horizon: int = 1) -> LabelSpec:
    return LabelSpec(
        name=name,
        label_type=LabelType.FORWARD_RETURN,
        horizon=horizon,
        input_column="close_adjusted",
        price_space=PriceSpace.ADJUSTED,
        required_adjustment=AdjustmentMethod.RATIO,
    )


# --- LabelSpec model ---


def test_valid_labelspec_creation():
    s = _valid_spec()
    assert s.name == "forward_return_1"
    assert s.output_column == "forward_return_1"  # defaults to name
    assert s.execution_lag == 1
    assert s.horizon == 1
    assert s.price_space is PriceSpace.ADJUSTED


def test_invalid_horizon_fails():
    with pytest.raises(ValidationError):
        _valid_spec(horizon=0)


def test_invalid_execution_lag_fails():
    with pytest.raises(ValidationError):
        LabelSpec(
            name="x",
            label_type=LabelType.FORWARD_RETURN,
            horizon=1,
            input_column="close_adjusted",
            price_space=PriceSpace.ADJUSTED,
            required_adjustment=AdjustmentMethod.RATIO,
            execution_lag=0,
        )


def test_unknown_extra_field_fails():
    with pytest.raises(ValidationError):
        LabelSpec(
            name="x",
            label_type=LabelType.FORWARD_RETURN,
            horizon=1,
            input_column="close_adjusted",
            price_space=PriceSpace.ADJUSTED,
            required_adjustment=AdjustmentMethod.RATIO,
            bogus_field=1,
        )


def test_adjusted_requires_required_adjustment():
    with pytest.raises(ValidationError):
        LabelSpec(
            name="x",
            label_type=LabelType.FORWARD_RETURN,
            horizon=1,
            input_column="close_adjusted",
            price_space=PriceSpace.ADJUSTED,
            required_adjustment=None,
        )


# --- label_config_hash ---


def test_label_config_hash_stable():
    h1 = label_config_hash(DEFAULT_ES_LABELS)
    assert h1 == label_config_hash(DEFAULT_ES_LABELS)
    assert label_config_hash(list(reversed(DEFAULT_ES_LABELS))) == h1  # order-stable


def test_label_config_hash_changes_when_spec_changes():
    base = label_config_hash(DEFAULT_ES_LABELS)
    changed = [_valid_spec("forward_return_1", horizon=2)] + DEFAULT_ES_LABELS[1:]
    assert label_config_hash(changed) != base


def test_label_config_hash_changes_when_upstream_feature_hash_changes():
    base = label_config_hash(DEFAULT_ES_LABELS, upstream_feature_hash="a")
    assert label_config_hash(DEFAULT_ES_LABELS, upstream_feature_hash="b") != base
    assert label_config_hash(DEFAULT_ES_LABELS) != base  # None vs "a"


# --- label formulas (t+L alignment) ---


def test_forward_return_1_matches_manual_t_plus_1_alignment():
    df = _continuous(80)
    lm = build_label_matrix(df, feature_df=build_feature_matrix(df))
    close = pd.Series(df["close_adjusted"].to_numpy())
    expected = close.shift(-2) / close.shift(-1) - 1.0  # L=1, h=1 -> [t+2]/[t+1]-1
    np.testing.assert_allclose(lm["forward_return_1"].to_numpy(), expected.to_numpy(), equal_nan=True)


def test_forward_return_5_matches_manual():
    df = _continuous(80)
    lm = build_label_matrix(df, feature_df=build_feature_matrix(df))
    close = pd.Series(df["close_adjusted"].to_numpy())
    expected = close.shift(-6) / close.shift(-1) - 1.0  # L=1, h=5 -> [t+6]/[t+1]-1
    np.testing.assert_allclose(lm["forward_return_5"].to_numpy(), expected.to_numpy(), equal_nan=True)


def test_direction_matches_threshold_rules():
    df = _continuous(80)
    lm = build_label_matrix(df, feature_df=build_feature_matrix(df))
    close = pd.Series(df["close_adjusted"].to_numpy())
    fr1 = close.shift(-2) / close.shift(-1) - 1.0
    expected = pd.Series(np.where(fr1 > 0, 1.0, np.where(fr1 < 0, -1.0, 0.0)), index=fr1.index)
    expected[fr1.isna()] = np.nan
    np.testing.assert_allclose(lm["direction_1"].to_numpy(), expected.to_numpy(), equal_nan=True)
    # direction_5 sign matches its forward return
    fr5 = close.shift(-6) / close.shift(-1) - 1.0
    assert np.array_equal(
        np.sign(lm["direction_5"].dropna().to_numpy()),
        np.sign(fr5.reindex(lm.index).dropna().to_numpy()),
    )


def test_vol_adjusted_uses_realized_vol_at_t():
    df = _continuous(80)
    feat = build_feature_matrix(df)
    lm = build_label_matrix(df, feature_df=feat)
    close = pd.Series(df["close_adjusted"].to_numpy())
    fr5 = close.shift(-6) / close.shift(-1) - 1.0
    vol = pd.Series(feat["realized_vol_20"].to_numpy())  # trailing feature at t
    expected = fr5 / vol
    np.testing.assert_allclose(
        lm["volatility_adjusted_return_5"].to_numpy(), expected.to_numpy(), equal_nan=True
    )


def test_last_execution_lag_plus_horizon_rows_are_nan():
    df = _continuous(80)
    lm = build_label_matrix(df, feature_df=build_feature_matrix(df))
    # forward_return_1: L+h = 2 trailing NaN; forward_return_5: L+h = 6 trailing NaN
    assert lm["forward_return_1"].iloc[-2:].isna().all()
    assert lm["forward_return_1"].iloc[:-2].notna().all()
    assert lm["forward_return_5"].iloc[-6:].isna().all()
    assert lm["direction_5"].iloc[-6:].isna().all()


# --- provenance + adjustment enforcement ---


def test_label_config_hash_column_present_and_chained():
    df = _continuous(60)
    feat = build_feature_matrix(df)
    fhash = feature_config_hash(DEFAULT_ES_FEATURES)
    lm = build_label_matrix(df, feature_df=feat, upstream_feature_hash=fhash)
    assert lm["label_config_hash"].nunique() == 1
    assert lm["label_config_hash"].iloc[0] == label_config_hash(
        DEFAULT_ES_LABELS, upstream_feature_hash=fhash
    )


def test_panama_frame_rejected_for_return_labels():
    df = _continuous(60, adjustment="panama")
    with pytest.raises(LabelError):
        build_label_matrix(df, feature_df=None)


def test_build_does_not_mutate_inputs():
    df = _continuous(60)
    feat = build_feature_matrix(df)
    df_before = df.copy(deep=True)
    feat_before = feat.copy(deep=True)
    build_label_matrix(df, feature_df=feat)
    pd.testing.assert_frame_equal(df, df_before)
    pd.testing.assert_frame_equal(feat, feat_before)


def test_all_label_columns_emitted():
    df = _continuous(80)
    lm = build_label_matrix(df, feature_df=build_feature_matrix(df))
    for col in LABEL_COLUMNS + ["timestamp", "root_symbol", "active_contract", "label_config_hash"]:
        assert col in lm.columns


# --------------------------------------------------------------------------- #
# Commit 2 — supervised dataset assembly
# --------------------------------------------------------------------------- #


def _feature_label(n: int = 80):
    df = _continuous(n)
    feat = build_feature_matrix(df)
    lab = build_label_matrix(df, feature_df=feat)
    return feat, lab


def test_dataset_joins_on_keys():
    feat, lab = _feature_label()
    ds = build_supervised_dataset(feat, lab)
    assert list(ds.columns[:3]) == ["timestamp", "root_symbol", "active_contract"]
    assert len(ds) == len(feat) == len(lab)
    # keys preserved and aligned
    assert (ds["root_symbol"] == "ES").all()


def test_dataset_has_feature_and_label_namespaces():
    feat, lab = _feature_label()
    ds = build_supervised_dataset(feat, lab)
    assert "feature__return_1" in ds.columns
    assert "feature__realized_vol_20" in ds.columns
    assert "label__forward_return_1" in ds.columns
    assert "label__volatility_adjusted_return_5" in ds.columns


def test_feature_and_label_namespaces_are_disjoint():
    feat, lab = _feature_label()
    ds = build_supervised_dataset(feat, lab)
    feature_cols = {c for c in ds.columns if c.startswith("feature__")}
    label_cols = {c for c in ds.columns if c.startswith("label__")}
    assert feature_cols and label_cols
    assert feature_cols.isdisjoint(label_cols)
    # no label name leaked into the feature namespace and vice versa
    assert "feature__forward_return_1" not in ds.columns
    assert "label__return_1" not in ds.columns


def test_is_label_valid_false_for_nan_label_tail():
    feat, lab = _feature_label(80)
    ds = build_supervised_dataset(feat, lab)
    # last 6 rows have NaN forward_return_5 / vol_adjusted_5 -> not label-valid
    assert not ds["is_label_valid"].iloc[-6:].any()
    assert ds["is_label_valid"].iloc[49:-6].all()  # post-warmup, pre-tail are valid


def test_is_trainable_excludes_warmup_and_nan_labels():
    feat, lab = _feature_label(80)
    ds = build_supervised_dataset(feat, lab)
    # warmup rows (0..48 from MA-gap) are not trainable
    assert not ds["is_trainable"].iloc[:49].any()
    # NaN-label tail (last 6) is not trainable
    assert not ds["is_trainable"].iloc[-6:].any()
    # the middle band is trainable
    assert ds["is_trainable"].iloc[49:-6].all()


def test_days_since_roll_nan_does_not_block_trainable():
    # _continuous has no rolls -> days_since_roll all NaN, but that must not by
    # itself make non-warmup, valid-label rows untrainable.
    feat, lab = _feature_label(80)
    ds = build_supervised_dataset(feat, lab)
    assert ds["feature__days_since_roll"].isna().all()
    assert ds["is_trainable"].any()  # trainable rows still exist


def test_drop_untrainable_removes_warmup_and_nan_label_rows():
    feat, lab = _feature_label(80)
    full = build_supervised_dataset(feat, lab)
    dropped = build_supervised_dataset(feat, lab, drop_untrainable=True)
    assert len(dropped) == int(full["is_trainable"].sum())
    assert dropped["is_trainable"].all()


def test_provenance_hashes_preserved():
    feat, lab = _feature_label()
    ds = build_supervised_dataset(feat, lab)
    assert "feature_config_hash" in ds.columns
    assert "label_config_hash" in ds.columns
    assert ds["feature_config_hash"].iloc[0] == feat["feature_config_hash"].iloc[0]
    assert ds["label_config_hash"].iloc[0] == lab["label_config_hash"].iloc[0]


def test_dataset_does_not_mutate_inputs():
    feat, lab = _feature_label()
    feat_before = feat.copy(deep=True)
    lab_before = lab.copy(deep=True)
    build_supervised_dataset(feat, lab)
    pd.testing.assert_frame_equal(feat, feat_before)
    pd.testing.assert_frame_equal(lab, lab_before)


def test_dataset_deterministic_and_order_invariant():
    feat, lab = _feature_label()
    ds1 = build_supervised_dataset(feat, lab)
    ds2 = build_supervised_dataset(feat, lab)
    pd.testing.assert_frame_equal(ds1, ds2)
    # shuffled input rows produce the same sorted dataset
    feat_s = feat.sample(frac=1, random_state=3).reset_index(drop=True)
    lab_s = lab.sample(frac=1, random_state=9).reset_index(drop=True)
    ds_shuffled = build_supervised_dataset(feat_s, lab_s)
    pd.testing.assert_frame_equal(ds_shuffled, ds1)


def test_dataset_key_mismatch_raises():
    feat, lab = _feature_label()
    with pytest.raises(DatasetError):
        build_supervised_dataset(feat, lab.iloc[:-1])  # label missing the last key


def test_dataset_missing_required_columns_raises():
    feat, lab = _feature_label()
    with pytest.raises(DatasetError):
        build_supervised_dataset(feat.drop(columns=["active_contract"]), lab)
    with pytest.raises(DatasetError):
        build_supervised_dataset(feat, lab.drop(columns=["label_config_hash"]))
