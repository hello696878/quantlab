"""
Tests for the ES instrument spec layer (Commit 1).

Covers: spec loading, the tick-value invariant, validation failures (invalid
tick value, missing field, bad month code, unknown field, immutability),
contract-symbol parsing/generation, third-Friday expiry, registry lookup, and
the unknown-instrument error.
"""

import datetime

import pytest
import yaml
from pydantic import ValidationError

from app.instruments import (
    FuturesSpec,
    UnknownInstrumentError,
    get_instrument,
    list_instruments,
    parse_contract_symbol,
    third_friday,
)
from app.instruments import registry


def _es_dict() -> dict:
    """Raw dict from the real es.yaml so failure tests mutate a valid baseline."""
    path = registry.default_instruments_dir() / "es.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# --- loading & invariants ---


def test_es_spec_loads_correctly():
    es = get_instrument("ES")
    assert isinstance(es, FuturesSpec)
    assert es.root_symbol == "ES"
    assert es.exchange == "CME"
    assert es.currency == "USD"
    assert es.contract_multiplier == 50
    assert es.tick_size == 0.25
    assert es.contract_months == ["H", "M", "U", "Z"]


def test_tick_value_invariant():
    es = get_instrument("ES")
    assert es.tick_value == pytest.approx(es.contract_multiplier * es.tick_size)
    assert es.tick_value == pytest.approx(12.5)


# --- validation failures ---


def test_invalid_tick_value_fails_validation():
    data = _es_dict()
    data["tick_value"] = 10.0  # != 50 * 0.25
    with pytest.raises(ValidationError):
        FuturesSpec(**data)


def test_missing_required_field_fails_validation():
    data = _es_dict()
    del data["contract_multiplier"]
    with pytest.raises(ValidationError):
        FuturesSpec(**data)


def test_invalid_month_code_fails_validation():
    data = _es_dict()
    data["contract_months"] = ["H", "M", "U", "ZZ"]
    with pytest.raises(ValidationError):
        FuturesSpec(**data)


def test_unknown_field_fails_validation():
    data = _es_dict()
    data["totally_bogus_field"] = 123
    with pytest.raises(ValidationError):
        FuturesSpec(**data)


def test_frozen_spec_is_immutable():
    es = get_instrument("ES")
    with pytest.raises(ValidationError):
        es.tick_size = 0.5


# --- symbol parsing / generation / expiry ---


def test_esz24_parses_correctly():
    cc = parse_contract_symbol("ESZ24")
    assert cc.root == "ES"
    assert cc.month_code == "Z"
    assert cc.year == 2024


def test_esz24_expiry_is_third_friday_dec_2024():
    es = get_instrument("ES")
    assert es.expiry_date("Z", 2024) == datetime.date(2024, 12, 20)
    assert es.expiry_for_symbol("ESZ24") == datetime.date(2024, 12, 20)
    assert third_friday(2024, 12) == datetime.date(2024, 12, 20)


def test_contract_symbol_roundtrips():
    es = get_instrument("ES")
    sym = es.build_contract_symbol("Z", 2024)
    assert sym == "ESZ24"
    cc = parse_contract_symbol(sym)
    assert es.build_contract_symbol(cc.month_code, cc.year) == sym


def test_build_rejects_off_cycle_month():
    es = get_instrument("ES")
    with pytest.raises(ValueError):
        es.build_contract_symbol("F", 2024)  # Jan not in ES quarterly cycle


# --- registry lookup ---


def test_get_instrument_works():
    es = get_instrument("ES")
    assert es.root_symbol == "ES"
    assert "ES" in list_instruments()


def test_unknown_instrument_raises_clear_error():
    with pytest.raises(UnknownInstrumentError) as exc:
        get_instrument("NOPE")
    assert "NOPE" in str(exc.value)
