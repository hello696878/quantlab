"""
Tests for the per-record futures daily bar schema (synthetic data only).

Covers: valid ES/NQ bars, OHLC violations, unknown root symbol, and
root/contract mismatch.  Complements test_store.py (frame-level
validate_raw_futures); this model adds the registry-aware rules.
"""

import datetime

import pytest
from pydantic import ValidationError

from app.datastore import FuturesDailyBar
from app.instruments import get_instrument


def _es_bar(**overrides) -> dict:
    """Synthetic but realistic ES daily bar; failure tests mutate this baseline."""
    bar = dict(
        timestamp=datetime.datetime(2025, 6, 17, 21, 0, tzinfo=datetime.timezone.utc),
        open=6000.0,
        high=6010.0,
        low=5990.0,
        close=6005.0,
        volume=1_200_000,
        open_interest=1_800_000.0,
        root_symbol="ES",
        contract_symbol="ESM25",
        expiry=datetime.date(2025, 6, 20),  # third Friday of June 2025
        source="synthetic",
        timezone="America/Chicago",
    )
    bar.update(overrides)
    return bar


# --- valid bars ---


def test_valid_es_bar_passes():
    bar = FuturesDailyBar(**_es_bar())
    assert bar.root_symbol == "ES"
    assert bar.contract_symbol == "ESM25"
    assert bar.high >= max(bar.open, bar.close)
    assert bar.low <= min(bar.open, bar.close)
    assert bar.timestamp.tzinfo is not None


def test_frame_style_expiry_datetime_is_accepted():
    # store.py normalizes expiry to a tz-aware UTC datetime; the model accepts
    # that representation and truncates to the UTC calendar date.
    bar = FuturesDailyBar(
        **_es_bar(
            expiry=datetime.datetime(2025, 6, 20, 15, 0, tzinfo=datetime.timezone.utc)
        )
    )
    assert bar.expiry == datetime.date(2025, 6, 20)


def test_frame_style_missing_open_interest_is_accepted():
    # The frame schema's missing-OI marker is NaN in a float64 column.
    bar = FuturesDailyBar(**_es_bar(open_interest=float("nan")))
    assert bar.open_interest is None


def test_valid_nq_bar_passes():
    bar = FuturesDailyBar(
        **_es_bar(
            root_symbol="NQ",
            contract_symbol="NQM25",
            open=21800.0,
            high=21900.0,
            low=21700.0,
            close=21850.0,
        )
    )
    assert bar.root_symbol == "NQ"
    assert bar.contract_symbol == "NQM25"


# --- OHLC violations ---


@pytest.mark.parametrize(
    "overrides",
    [
        {"high": 6001.0},   # high < max(open, close)
        {"low": 6002.0},    # low > min(open, close)
        {"open": -6000.0},  # non-positive price
        {"close": 0.0},     # non-positive price
    ],
)
def test_invalid_ohlc_fails(overrides):
    with pytest.raises(ValidationError):
        FuturesDailyBar(**_es_bar(**overrides))


# --- metadata linking (bar -> instrument spec) ---


def test_metadata_lookup_links_bar_to_spec():
    bar = FuturesDailyBar(**_es_bar())
    spec = get_instrument(bar.root_symbol)
    assert spec.root_symbol == bar.root_symbol
    assert spec.currency == "USD"
    assert spec.tick_value == pytest.approx(spec.contract_multiplier * spec.tick_size)
    assert bar.expiry == spec.expiry_for_symbol(bar.contract_symbol)


# --- registry-aware rules ---


def test_unknown_root_symbol_fails():
    with pytest.raises(ValidationError) as exc:
        FuturesDailyBar(**_es_bar(root_symbol="XX", contract_symbol="XXM25"))
    assert "XX" in str(exc.value)


def test_mismatched_root_contract_fails():
    with pytest.raises(ValidationError) as exc:
        FuturesDailyBar(**_es_bar(contract_symbol="NQM25"))
    assert "NQM25" in str(exc.value)
