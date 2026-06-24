"""
Tests for the feature spec + validation layer (Phase 2 — commit 1).

Config and validation only — no feature math. Synthetic data only, no network.
"""

import pandas as pd
import pytest
from pydantic import ValidationError

from app.instruments import AdjustmentMethod
from app.datastore.store import CONTINUOUS_COLUMNS
from app.features import (
    DEFAULT_ES_FEATURES,
    FeatureError,
    FeatureSpec,
    PriceSpace,
    TransformType,
    feature_config_hash,
    validate_continuous_input,
    validate_feature_specs,
)


def _valid_return_spec(name: str = "return_1", window: int = 1) -> FeatureSpec:
    return FeatureSpec(
        name=name,
        transform=TransformType.RETURN,
        input_columns=["close_adjusted"],
        windows=[window],
        price_space=PriceSpace.ADJUSTED,
        required_adjustment=AdjustmentMethod.RATIO,
    )


def _continuous_frame(n: int = 3) -> pd.DataFrame:
    """Minimal valid Phase 1 continuous frame (all CONTINUOUS_COLUMNS)."""
    idx = pd.date_range("2024-01-01", periods=n, freq="B", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": idx,
            "root_symbol": "ES",
            "active_contract": "ESH24",
            "open_raw": 5000.0,
            "high_raw": 5002.0,
            "low_raw": 4999.0,
            "close_raw": 5001.0,
            "volume": 1000,
            "open_interest": 2000.0,
            "adjustment_method": "ratio",
            "adjustment_factor": 1.0,
            "open_adjusted": 5000.0,
            "high_adjusted": 5002.0,
            "low_adjusted": 4999.0,
            "close_adjusted": 5001.0,
            "roll_flag": False,
            "roll_reason": "",
        }
    )
    return df[CONTINUOUS_COLUMNS]


# --- FeatureSpec model ---


def test_valid_featurespec_creation():
    s = _valid_return_spec()
    assert s.name == "return_1"
    assert s.output_name == "return_1"  # defaults to name
    assert s.transform is TransformType.RETURN
    assert s.windows == [1]
    assert s.price_space is PriceSpace.ADJUSTED
    assert s.required_adjustment is AdjustmentMethod.RATIO


def test_invalid_negative_window_fails():
    with pytest.raises(ValidationError):
        FeatureSpec(
            name="x",
            transform=TransformType.RETURN,
            input_columns=["close_adjusted"],
            windows=[-1],
            price_space=PriceSpace.ADJUSTED,
            required_adjustment=AdjustmentMethod.RATIO,
        )


def test_unknown_extra_field_fails():
    with pytest.raises(ValidationError):
        FeatureSpec(
            name="x",
            transform=TransformType.RETURN,
            input_columns=["close_adjusted"],
            windows=[1],
            price_space=PriceSpace.ADJUSTED,
            required_adjustment=AdjustmentMethod.RATIO,
            totally_bogus_field=123,
        )


def test_adjusted_without_required_adjustment_fails():
    with pytest.raises(ValidationError):
        FeatureSpec(
            name="x",
            transform=TransformType.RETURN,
            input_columns=["close_adjusted"],
            windows=[1],
            price_space=PriceSpace.ADJUSTED,
            required_adjustment=None,
        )


def test_none_pricespace_with_required_adjustment_fails():
    with pytest.raises(ValidationError):
        FeatureSpec(
            name="rf",
            transform=TransformType.PASSTHROUGH,
            input_columns=["roll_flag"],
            price_space=PriceSpace.NONE,
            required_adjustment=AdjustmentMethod.RATIO,
        )


# --- default registry ---


def test_default_es_features_names_unique():
    names = [s.name for s in DEFAULT_ES_FEATURES]
    assert len(names) == len(set(names))
    assert len(DEFAULT_ES_FEATURES) == 16


def test_default_es_features_output_names_unique():
    outputs = [s.output_name for s in DEFAULT_ES_FEATURES]
    assert len(outputs) == len(set(outputs))


def test_default_es_features_validate():
    validate_feature_specs(DEFAULT_ES_FEATURES)  # must not raise


# --- feature config hash ---


def test_feature_config_hash_stable_for_same_specs():
    h1 = feature_config_hash(DEFAULT_ES_FEATURES)
    h2 = feature_config_hash(DEFAULT_ES_FEATURES)
    assert h1 == h2
    # order must not matter (specs sorted by name internally)
    assert feature_config_hash(list(reversed(DEFAULT_ES_FEATURES))) == h1


def test_feature_config_hash_changes_when_config_changes():
    base = feature_config_hash(DEFAULT_ES_FEATURES)
    changed = [_valid_return_spec("return_1", window=2)] + DEFAULT_ES_FEATURES[1:]
    assert feature_config_hash(changed) != base


def test_feature_config_hash_changes_when_upstream_continuous_hash_changes():
    a = feature_config_hash(DEFAULT_ES_FEATURES, continuous_config_hash="aaa")
    b = feature_config_hash(DEFAULT_ES_FEATURES, continuous_config_hash="bbb")
    assert a != b
    assert feature_config_hash(DEFAULT_ES_FEATURES) != a  # None vs "aaa"


# --- validation helpers ---


def test_validate_continuous_input_accepts_valid_frame():
    df = _continuous_frame()
    before = df.copy(deep=True)
    validate_continuous_input(df)  # must not raise
    pd.testing.assert_frame_equal(df, before)  # input not modified


def test_validate_continuous_input_rejects_missing_columns():
    df = _continuous_frame().drop(columns=["close_adjusted"])
    with pytest.raises(FeatureError):
        validate_continuous_input(df)


def test_validate_feature_specs_rejects_duplicate_names():
    specs = [_valid_return_spec("dup", window=1), _valid_return_spec("dup", window=5)]
    with pytest.raises(FeatureError):
        validate_feature_specs(specs)


def test_validate_feature_specs_rejects_duplicate_output_names():
    a = FeatureSpec(
        name="a",
        transform=TransformType.RETURN,
        input_columns=["close_adjusted"],
        windows=[1],
        price_space=PriceSpace.ADJUSTED,
        required_adjustment=AdjustmentMethod.RATIO,
        output_name="same",
    )
    b = FeatureSpec(
        name="b",
        transform=TransformType.RETURN,
        input_columns=["close_adjusted"],
        windows=[1],
        price_space=PriceSpace.ADJUSTED,
        required_adjustment=AdjustmentMethod.RATIO,
        output_name="same",
    )
    with pytest.raises(FeatureError):
        validate_feature_specs([a, b])
