"""
Tests for the instrument spec layer (ES, plus the NQ/YM/RTY config-only
additions).

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


@pytest.mark.parametrize("blank", ["", "   "])
@pytest.mark.parametrize("field", ["exchange", "currency", "name", "price_quotation"])
def test_blank_identity_field_fails_validation(field, blank):
    data = _es_dict()
    data[field] = blank
    with pytest.raises(ValidationError):
        FuturesSpec(**data)


def test_identity_field_whitespace_is_stripped():
    data = _es_dict()
    data["currency"] = "  USD  "
    es = FuturesSpec(**data)
    assert es.currency == "USD"


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


# --- NQ (second instrument; config-only addition) ---


def test_nq_spec_loads_correctly():
    nq = get_instrument("NQ")
    assert isinstance(nq, FuturesSpec)
    assert nq.root_symbol == "NQ"
    assert nq.exchange == "CME"
    assert nq.currency == "USD"
    assert nq.contract_multiplier == 20
    assert nq.tick_size == 0.25
    assert nq.contract_months == ["H", "M", "U", "Z"]
    assert "NQ" in list_instruments()


def test_nq_tick_value_invariant():
    nq = get_instrument("NQ")
    assert nq.tick_value == pytest.approx(nq.contract_multiplier * nq.tick_size)
    assert nq.tick_value == pytest.approx(5.0)


def test_nq_expiry_is_third_friday():
    nq = get_instrument("NQ")
    assert nq.build_contract_symbol("Z", 2025) == "NQZ25"
    assert nq.expiry_for_symbol("NQZ25") == datetime.date(2025, 12, 19)


# --- YM (third instrument; config-only addition) ---


def test_ym_spec_loads_correctly():
    ym = get_instrument("YM")
    assert isinstance(ym, FuturesSpec)
    assert ym.root_symbol == "YM"
    assert ym.exchange == "CBOT"
    assert ym.currency == "USD"
    assert ym.contract_multiplier == 5
    assert ym.tick_size == 1.0
    assert ym.contract_months == ["H", "M", "U", "Z"]
    assert "YM" in list_instruments()


def test_ym_tick_value_invariant():
    ym = get_instrument("YM")
    assert ym.tick_value == pytest.approx(ym.contract_multiplier * ym.tick_size)
    assert ym.tick_value == pytest.approx(5.0)


def test_ym_expiry_is_third_friday():
    ym = get_instrument("YM")
    assert ym.build_contract_symbol("Z", 2025) == "YMZ25"
    assert ym.expiry_for_symbol("YMZ25") == datetime.date(2025, 12, 19)


# --- RTY (fourth instrument; config-only addition) ---


def test_rty_spec_loads_correctly():
    rty = get_instrument("RTY")
    assert isinstance(rty, FuturesSpec)
    assert rty.root_symbol == "RTY"
    assert rty.exchange == "CME"
    assert rty.currency == "USD"
    assert rty.contract_multiplier == 50
    assert rty.tick_size == 0.1
    assert rty.contract_months == ["H", "M", "U", "Z"]
    assert "RTY" in list_instruments()


def test_rty_tick_value_invariant():
    rty = get_instrument("RTY")
    assert rty.tick_value == pytest.approx(rty.contract_multiplier * rty.tick_size)
    assert rty.tick_value == pytest.approx(5.0)


def test_rty_expiry_is_third_friday():
    rty = get_instrument("RTY")
    assert rty.build_contract_symbol("Z", 2025) == "RTYZ25"
    assert rty.expiry_for_symbol("RTYZ25") == datetime.date(2025, 12, 19)
