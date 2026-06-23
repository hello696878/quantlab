"""
Tests for the raw futures schema + storage layer (Commit 2).

Covers validation (valid frame, missing column, negative price, OHLC
incoherence, negative volume, negative/nullable open_interest, duplicates),
write/read round-trip, raw-vs-continuous path separation, and the data-version
hash (stable for unsorted-equivalent input, changes when data changes).
"""

import pandas as pd
import pytest

from app.datastore import (
    REQUIRED_COLUMNS,
    RawFuturesStore,
    RawSchemaError,
    raw_data_version_hash,
    validate_raw_futures,
)


def make_raw_df(contract: str = "ESZ24", n: int = 5, source: str = "test") -> pd.DataFrame:
    """Build a small, valid raw single-contract frame (naive timestamps)."""
    idx = pd.date_range("2024-11-01", periods=n, freq="B")  # naive -> normalized to UTC
    rows = []
    for i, ts in enumerate(idx):
        open_ = 4500.0 + i
        close = open_ + 0.5
        high = max(open_, close) + 1.0
        low = min(open_, close) - 1.0
        rows.append(
            {
                "timestamp": ts,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1000 + i,
                "open_interest": 2000 + i,
                "root_symbol": "ES",
                "contract_symbol": contract,
                "expiry": "2024-12-20",
                "source": source,
                "timezone": "America/Chicago",
            }
        )
    return pd.DataFrame(rows)


# --- validation ---


def test_valid_raw_dataframe_passes():
    norm = validate_raw_futures(make_raw_df())
    assert list(norm.columns) == REQUIRED_COLUMNS
    assert len(norm) == 5
    assert norm["timestamp"].dt.tz is not None  # normalized to tz-aware (UTC)
    assert norm["volume"].dtype == "int64"


def test_missing_required_column_fails():
    df = make_raw_df().drop(columns=["close"])
    with pytest.raises(RawSchemaError):
        validate_raw_futures(df)


def test_negative_price_fails():
    df = make_raw_df()
    df.loc[2, "open"] = -1.0
    with pytest.raises(RawSchemaError):
        validate_raw_futures(df)


def test_ohlc_incoherence_fails():
    df = make_raw_df()
    df.loc[1, "high"] = df.loc[1, "open"] - 50.0  # high below open, still positive
    with pytest.raises(RawSchemaError):
        validate_raw_futures(df)


def test_negative_volume_fails():
    df = make_raw_df()
    df.loc[0, "volume"] = -5
    with pytest.raises(RawSchemaError):
        validate_raw_futures(df)


def test_negative_open_interest_when_present_fails():
    df = make_raw_df()
    df.loc[0, "open_interest"] = -1
    with pytest.raises(RawSchemaError):
        validate_raw_futures(df)


def test_nullable_open_interest_is_allowed():
    # whole column missing
    df_all = make_raw_df()
    df_all["open_interest"] = None
    norm_all = validate_raw_futures(df_all)
    assert norm_all["open_interest"].isna().all()

    # partially missing
    df_part = make_raw_df()
    df_part.loc[1, "open_interest"] = None
    norm_part = validate_raw_futures(df_part)
    assert norm_part["open_interest"].isna().sum() == 1


def test_duplicate_contract_timestamp_fails():
    df = make_raw_df()
    dup = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    with pytest.raises(RawSchemaError):
        validate_raw_futures(dup)


# --- storage ---


def test_write_and_read_back(tmp_path):
    df = make_raw_df()
    store = RawFuturesStore(tmp_path)
    paths = store.write_raw(df)
    assert len(paths) == 1
    assert paths[0].exists()

    back = store.read_raw("ES", "ESZ24", "test")
    pd.testing.assert_frame_equal(back, validate_raw_futures(df))


def test_raw_path_separate_from_continuous(tmp_path):
    store = RawFuturesStore(tmp_path)
    rp = store.raw_path("ES", "ESZ24", "test")
    assert "raw" in rp.parts
    assert "continuous" not in rp.parts
    assert store.raw_root() != store.continuous_root()
    assert store.continuous_root() not in rp.parents


def test_storage_format_is_explicit(tmp_path):
    store = RawFuturesStore(tmp_path)
    assert store.storage_format in ("parquet", "csv")
    # raw file lives under the raw namespace with the active extension
    rp = store.raw_path("ES", "ESZ24", "test")
    assert rp.suffix == f".{store.storage_format}"


# --- data version hash ---


def test_hash_stable_for_sorted_and_unsorted_inputs():
    df = make_raw_df()
    shuffled = df.sample(frac=1, random_state=7).reset_index(drop=True)
    assert raw_data_version_hash(df) == raw_data_version_hash(shuffled)


def test_hash_changes_when_data_changes():
    df = make_raw_df()
    changed = make_raw_df()
    changed.loc[0, "volume"] = changed.loc[0, "volume"] + 1  # value change, stays coherent
    assert raw_data_version_hash(df) != raw_data_version_hash(changed)
