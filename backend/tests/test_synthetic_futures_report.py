"""
Tests for the synthetic futures mini trade report (synthetic data only).

Covers: ES and NQ long-trade P&L, tick-based == multiplier-based P&L, and
mixed-contract / empty-input rejection.  Root/contract-symbol mismatch is
already covered by test_futures_daily_bar.py (the FuturesDailyBar model
rejects it at construction).
"""

import datetime

import pytest

from app.datastore import FuturesDailyBar
from app.reports import long_trade_report


_JUNE_2025_EXPIRY = datetime.date(2025, 6, 20)  # third Friday


def _bars(root: str, contract: str, expiry: datetime.date, closes: list) -> list:
    return [
        FuturesDailyBar(
            timestamp=datetime.datetime(
                2025, 6, 16 + i, 21, 0, tzinfo=datetime.timezone.utc
            ),
            open=c - 2.0,
            high=c + 3.0,
            low=c - 5.0,
            close=c,
            volume=100_000,
            open_interest=500_000.0,
            root_symbol=root,
            contract_symbol=contract,
            expiry=expiry,
            source="synthetic",
            timezone="America/Chicago",
        )
        for i, c in enumerate(closes)
    ]


def test_es_long_trade_pnl_correct():
    bars = _bars("ES", "ESM25", _JUNE_2025_EXPIRY, [6000.00, 6004.25, 6010.50])
    r = long_trade_report(bars, contracts=1)
    assert r.root_symbol == "ES"
    assert r.contract_symbol == "ESM25"
    assert r.entry_price == 6000.00
    assert r.exit_price == 6010.50
    assert r.price_move == pytest.approx(10.50)
    assert r.tick_move == pytest.approx(42.0)
    assert r.pnl_usd == pytest.approx(525.0)  # 10.50 pts * $50/pt
    assert r.tick_pnl_usd == pytest.approx(525.0)  # 42 ticks * $12.50/tick
    assert len(r.warnings) > 0  # spec warnings surfaced in every report
    # contracts scale linearly
    assert long_trade_report(bars, contracts=2).pnl_usd == pytest.approx(1050.0)


def test_nq_long_trade_pnl_correct():
    bars = _bars("NQ", "NQM25", _JUNE_2025_EXPIRY, [21800.00, 21830.50, 21850.25])
    r = long_trade_report(bars)
    assert r.root_symbol == "NQ"
    assert r.price_move == pytest.approx(50.25)
    assert r.tick_move == pytest.approx(201.0)
    assert r.pnl_usd == pytest.approx(1005.0)  # 50.25 pts * $20/pt
    assert r.tick_pnl_usd == pytest.approx(1005.0)  # 201 ticks * $5/tick


@pytest.mark.parametrize(
    "root,contract,closes",
    [
        ("ES", "ESM25", [6000.00, 6010.50]),
        ("NQ", "NQM25", [21800.00, 21850.25]),
    ],
)
def test_tick_pnl_equals_multiplier_pnl(root, contract, closes):
    r = long_trade_report(_bars(root, contract, _JUNE_2025_EXPIRY, closes))
    assert r.pnl_usd == pytest.approx(r.tick_pnl_usd)
    assert r.pnl_matches is True


def test_mixed_contract_bars_rejected():
    bars = _bars("ES", "ESM25", _JUNE_2025_EXPIRY, [6000.00]) + _bars(
        "ES", "ESU25", datetime.date(2025, 9, 19), [6010.50]
    )
    with pytest.raises(ValueError):
        long_trade_report(bars)


def test_empty_bars_rejected():
    with pytest.raises(ValueError):
        long_trade_report([])


def test_duplicate_timestamps_rejected():
    bar = _bars("ES", "ESM25", _JUNE_2025_EXPIRY, [6000.00])[0]
    with pytest.raises(ValueError):
        long_trade_report([bar, bar])


@pytest.mark.parametrize("contracts", [2.5, 0, -1, True])
def test_invalid_contracts_rejected(contracts):
    bars = _bars("ES", "ESM25", _JUNE_2025_EXPIRY, [6000.00, 6010.50])
    with pytest.raises(ValueError):
        long_trade_report(bars, contracts=contracts)
