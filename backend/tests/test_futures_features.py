"""
Tests for the feature layer (Phase 2 — commits 1 & 2).

Commit 1: spec + validation. Commit 2: build_feature_matrix with the basic
price/return/volatility/rolling features. Synthetic data only, no network.
"""

import datetime

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from app.instruments import AdjustmentMethod, get_instrument
from app.datastore.store import CONTINUOUS_COLUMNS
from app.datastore.futures_continuous import build_continuous_futures
from app.features import (
    DEFAULT_ES_FEATURES,
    FeatureError,
    FeatureSpec,
    PriceSpace,
    TransformType,
    build_feature_matrix,
    feature_config_hash,
    validate_continuous_input,
    validate_feature_specs,
)

IMPLEMENTED_FEATURES = [
    "return_1",
    "return_5",
    "return_20",
    "realized_vol_20",
    "rolling_high_20",
    "rolling_low_20",
    "close_to_rolling_high_20",
    "close_to_rolling_low_20",
    "moving_average_gap_10_50",
    "RSI_14",
    "ATR_14",
    "ATR_14_pct",
]


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


# --------------------------------------------------------------------------- #
# Commit 2 — build_feature_matrix (basic price/return/vol/rolling features)
# --------------------------------------------------------------------------- #


def _ratio_continuous(n: int = 60) -> pd.DataFrame:
    """Single-contract ratio-adjusted continuous frame (deterministic price path)."""
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
            "volume": 1000,
            "open_interest": 2000.0,
            "adjustment_method": "ratio",
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


def _raw_seam_df() -> pd.DataFrame:
    """Two ES contracts at different levels, OI missing -> fallback roll (2024-03-07)."""
    dates = list(pd.date_range("2024-02-26", "2024-03-15", freq="B"))
    rows = []
    for symbol, base, expiry in [("ESH24", 5000, "2024-03-15"), ("ESM24", 5100, "2024-06-21")]:
        for i, d in enumerate(dates):
            open_ = base + i
            close = open_ + 1.0
            rows.append(
                {
                    "timestamp": pd.Timestamp(d),
                    "open": open_,
                    "high": max(open_, close) + 1.0,
                    "low": min(open_, close) - 1.0,
                    "close": close,
                    "volume": 1000,
                    "open_interest": None,
                    "root_symbol": "ES",
                    "contract_symbol": symbol,
                    "expiry": pd.Timestamp(expiry),
                    "source": "synthetic",
                    "timezone": "America/Chicago",
                }
            )
    return pd.DataFrame(rows)


# --- structure / metadata / determinism ---


def test_build_does_not_mutate_input():
    df = _ratio_continuous(30)
    before = df.copy(deep=True)
    build_feature_matrix(df)
    pd.testing.assert_frame_equal(df, before)


def test_output_has_required_metadata_columns():
    fm = build_feature_matrix(_ratio_continuous(60))
    for col in ["timestamp", "root_symbol", "active_contract",
                "is_warmup", "source_adjustment_method", "feature_config_hash"]:
        assert col in fm.columns
    for col in IMPLEMENTED_FEATURES:
        assert col in fm.columns
    assert (fm["source_adjustment_method"] == "ratio").all()


def test_build_is_deterministic():
    df = _ratio_continuous(40)
    pd.testing.assert_frame_equal(build_feature_matrix(df), build_feature_matrix(df))


def test_ratio_frame_is_accepted():
    fm = build_feature_matrix(_ratio_continuous(30))
    assert "return_1" in fm.columns
    assert len(fm) == 30


# --- manual formula checks ---


def test_returns_match_manual_formula():
    df = _ratio_continuous(60)
    fm = build_feature_matrix(df)
    close = pd.Series(df["close_adjusted"].to_numpy())
    for n, name in [(1, "return_1"), (5, "return_5"), (20, "return_20")]:
        np.testing.assert_allclose(
            fm[name].to_numpy(), close.pct_change(n).to_numpy(), equal_nan=True, rtol=1e-12
        )


def test_realized_vol_uses_trailing_return_1():
    df = _ratio_continuous(60)
    fm = build_feature_matrix(df)
    close = pd.Series(df["close_adjusted"].to_numpy())
    expected = close.pct_change(1).rolling(20).std() * np.sqrt(252)
    np.testing.assert_allclose(
        fm["realized_vol_20"].to_numpy(), expected.to_numpy(), equal_nan=True, rtol=1e-9
    )


def test_rolling_high_low_trailing_only():
    df = _ratio_continuous(60)
    fm = build_feature_matrix(df)
    high = pd.Series(df["high_adjusted"].to_numpy())
    low = pd.Series(df["low_adjusted"].to_numpy())
    np.testing.assert_allclose(
        fm["rolling_high_20"].to_numpy(), high.rolling(20).max().to_numpy(), equal_nan=True
    )
    np.testing.assert_allclose(
        fm["rolling_low_20"].to_numpy(), low.rolling(20).min().to_numpy(), equal_nan=True
    )


def test_close_to_rolling_match_manual_formula():
    df = _ratio_continuous(60)
    fm = build_feature_matrix(df)
    close = pd.Series(df["close_adjusted"].to_numpy())
    high = pd.Series(df["high_adjusted"].to_numpy())
    low = pd.Series(df["low_adjusted"].to_numpy())
    np.testing.assert_allclose(
        fm["close_to_rolling_high_20"].to_numpy(),
        (close / high.rolling(20).max() - 1.0).to_numpy(),
        equal_nan=True,
    )
    np.testing.assert_allclose(
        fm["close_to_rolling_low_20"].to_numpy(),
        (close / low.rolling(20).min() - 1.0).to_numpy(),
        equal_nan=True,
    )


# --- warmup ---


def test_warmup_rows_marked_explicitly():
    fm = build_feature_matrix(_ratio_continuous(60))
    # longest-warmup feature is moving_average_gap_10_50: first valid at index 49.
    assert fm["is_warmup"].iloc[:49].all()
    assert not fm["is_warmup"].iloc[49:].any()


def test_non_warmup_rows_have_no_nans():
    fm = build_feature_matrix(_ratio_continuous(60))
    non_warmup = fm.loc[~fm["is_warmup"], IMPLEMENTED_FEATURES]
    assert not non_warmup.isna().any().any()


def test_feature_config_hash_present_and_stable():
    fm = build_feature_matrix(_ratio_continuous(40))
    assert fm["feature_config_hash"].nunique() == 1
    assert fm["feature_config_hash"].iloc[0] == feature_config_hash(DEFAULT_ES_FEATURES)


# --- adjustment enforcement ---


def test_panama_frame_rejected_for_return_features():
    panama = build_continuous_futures(_raw_seam_df(), get_instrument("ES"), "panama")
    with pytest.raises(FeatureError):
        build_feature_matrix(panama)


# --- leakage: truncation invariance ---


def _equal_or_nan(a, b) -> bool:
    if pd.isna(a) and pd.isna(b):
        return True
    return a == pytest.approx(b, rel=1e-12, abs=1e-12)


def test_truncation_invariance():
    df = _ratio_continuous(60)
    full = build_feature_matrix(df)
    # include the Wilder-indicator seed (14) and the MA-gap region (55).
    for t in (3, 14, 21, 35, 55, 59):
        trunc = build_feature_matrix(df.iloc[: t + 1])
        for col in IMPLEMENTED_FEATURES:
            assert _equal_or_nan(full.loc[t, col], trunc.loc[t, col]), (col, t)


# --- leakage: roll seam uses adjusted, not raw gap ---


def test_seam_return_uses_adjusted_not_raw_gap():
    ratio = build_continuous_futures(_raw_seam_df(), get_instrument("ES"), "ratio")
    fm = build_feature_matrix(ratio)
    by_date = fm.set_index(fm["timestamp"].dt.date)
    roll = datetime.date(2024, 3, 7)
    held_return = 5109 / 5108 - 1.0       # ESM24 own return across the seam
    raw_gap_return = 5109 / 5008 - 1.0    # the WRONG, spiky one
    assert by_date.loc[roll, "return_1"] == pytest.approx(held_return, rel=1e-9)
    assert abs(by_date.loc[roll, "return_1"] - raw_gap_return) > 1e-4


# --------------------------------------------------------------------------- #
# Commit 3 — technical indicators (MA gap, RSI, ATR, ATR%)
# --------------------------------------------------------------------------- #


def _scaled_continuous(n: int = 60, scale: float = 2.0) -> pd.DataFrame:
    """Ratio continuous frame where adjusted prices = ``scale`` x raw prices."""
    idx = pd.date_range("2024-01-01", periods=n, freq="B", tz="UTC")
    raw_close = np.array([4000.0 + i for i in range(n)])
    raw_high = raw_close + 3.0
    raw_low = raw_close - 3.0
    df = pd.DataFrame(
        {
            "timestamp": idx,
            "root_symbol": "ES",
            "active_contract": "ESH24",
            "open_raw": raw_close,
            "high_raw": raw_high,
            "low_raw": raw_low,
            "close_raw": raw_close,
            "volume": 1000,
            "open_interest": 2000.0,
            "adjustment_method": "ratio",
            "adjustment_factor": scale,
            "open_adjusted": raw_close * scale,
            "high_adjusted": raw_high * scale,
            "low_adjusted": raw_low * scale,
            "close_adjusted": raw_close * scale,
            "roll_flag": False,
            "roll_reason": "",
        }
    )
    return df[CONTINUOUS_COLUMNS]


def _ref_rsi(close, period: int = 14):
    c = list(close)
    n = len(c)
    out = [float("nan")] * n
    gains = [0.0] * n
    losses = [0.0] * n
    for i in range(1, n):
        change = c[i] - c[i - 1]
        gains[i] = max(change, 0.0)
        losses[i] = max(-change, 0.0)
    if n <= period:
        return out

    def rsi_val(avg_gain, avg_loss):
        if avg_loss == 0.0:
            return 100.0
        return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)

    ag = sum(gains[1 : period + 1]) / period
    al = sum(losses[1 : period + 1]) / period
    out[period] = rsi_val(ag, al)
    for t in range(period + 1, n):
        ag = (ag * (period - 1) + gains[t]) / period
        al = (al * (period - 1) + losses[t]) / period
        out[t] = rsi_val(ag, al)
    return out


def _ref_atr(high, low, close, period: int = 14, normalize=None):
    import math as _math

    h, l, c = list(high), list(low), list(close)
    n = len(h)
    tr = [float("nan")] * n
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    out = [float("nan")] * n
    if n > period:
        out[period] = sum(tr[1 : period + 1]) / period
        for t in range(period + 1, n):
            out[t] = (out[t - 1] * (period - 1) + tr[t]) / period
    if normalize == "close":
        out = [out[i] / c[i] if not _math.isnan(out[i]) else float("nan") for i in range(n)]
    return out


# --- MA gap ---


def test_ma_gap_matches_manual_formula():
    df = _ratio_continuous(80)
    fm = build_feature_matrix(df)
    close = pd.Series(df["close_adjusted"].to_numpy())
    expected = (close.rolling(10).mean() - close.rolling(50).mean()) / close.rolling(50).mean()
    np.testing.assert_allclose(
        fm["moving_average_gap_10_50"].to_numpy(), expected.to_numpy(), equal_nan=True
    )


def test_ma_gap_warmup_before_ma50():
    fm = build_feature_matrix(_ratio_continuous(80))
    assert fm["moving_average_gap_10_50"].iloc[:49].isna().all()
    assert fm["moving_average_gap_10_50"].iloc[49:].notna().all()


# --- RSI ---


def test_rsi_matches_reference():
    df = _ratio_continuous(60)
    fm = build_feature_matrix(df)
    expected = np.array(_ref_rsi(df["close_adjusted"].to_numpy(), 14), dtype=float)
    np.testing.assert_allclose(fm["RSI_14"].to_numpy(), expected, equal_nan=True, rtol=1e-9)


def test_rsi_all_up_zero_loss_is_100():
    n = 40
    idx = pd.date_range("2024-01-01", periods=n, freq="B", tz="UTC")
    closes = np.array([5000.0 + 10.0 * i for i in range(n)])  # strictly increasing
    df = pd.DataFrame(
        {
            "timestamp": idx, "root_symbol": "ES", "active_contract": "ESH24",
            "open_raw": closes, "high_raw": closes + 5.0, "low_raw": closes - 5.0, "close_raw": closes,
            "volume": 1000, "open_interest": 2000.0,
            "adjustment_method": "ratio", "adjustment_factor": 1.0,
            "open_adjusted": closes, "high_adjusted": closes + 5.0,
            "low_adjusted": closes - 5.0, "close_adjusted": closes,
            "roll_flag": False, "roll_reason": "",
        }
    )[CONTINUOUS_COLUMNS]
    rsi = build_feature_matrix(df)["RSI_14"].dropna()
    assert (rsi == 100.0).all()


# --- ATR ---


def test_atr_matches_reference():
    df = _ratio_continuous(60)
    fm = build_feature_matrix(df)
    expected = np.array(
        _ref_atr(df["high_adjusted"].to_numpy(), df["low_adjusted"].to_numpy(),
                 df["close_adjusted"].to_numpy(), 14),
        dtype=float,
    )
    np.testing.assert_allclose(fm["ATR_14"].to_numpy(), expected, equal_nan=True, rtol=1e-9)


def test_atr_pct_equals_atr_over_close():
    df = _ratio_continuous(60)
    fm = build_feature_matrix(df)
    expected = fm["ATR_14"].to_numpy() / df["close_adjusted"].to_numpy()
    np.testing.assert_allclose(fm["ATR_14_pct"].to_numpy(), expected, equal_nan=True, rtol=1e-12)


def test_atr_uses_adjusted_not_raw_prices():
    df = _scaled_continuous(60, scale=2.0)  # adjusted = 2x raw
    fm = build_feature_matrix(df)
    atr_adj = np.array(
        _ref_atr(df["high_adjusted"].to_numpy(), df["low_adjusted"].to_numpy(),
                 df["close_adjusted"].to_numpy(), 14), dtype=float
    )
    atr_raw = np.array(
        _ref_atr(df["high_raw"].to_numpy(), df["low_raw"].to_numpy(),
                 df["close_raw"].to_numpy(), 14), dtype=float
    )
    np.testing.assert_allclose(fm["ATR_14"].to_numpy(), atr_adj, equal_nan=True, rtol=1e-9)
    assert abs(fm["ATR_14"].iloc[30] - atr_raw[30]) > 1e-6  # not the raw-based ATR


def test_default_emits_indicator_columns():
    fm = build_feature_matrix(_ratio_continuous(60))
    for col in ["moving_average_gap_10_50", "RSI_14", "ATR_14", "ATR_14_pct"]:
        assert col in fm.columns
