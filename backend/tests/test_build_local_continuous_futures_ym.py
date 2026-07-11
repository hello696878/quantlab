"""
Phase 1 futures data layer — end-to-end YM continuous-build smoke test.

Verifies the ingest -> continuous-build path is **root-agnostic** by exercising
it on a second equity-index root (YM, E-mini Dow), complementing the existing
ES coverage.  It uses a tiny committed synthetic multi-contract fixture
(``ym_roll.csv``: YMM25 -> YMU25 with a clean volume/OI crossover) and reuses
the Phase 7 ingest helper (``ingest_local_futures_csv``) and the Phase 8
store->continuous adapter (``build_continuous_from_store``) verbatim — no new
production code and no new hash.

Everything is written under ``tmp_path``; no network; nothing is written outside
``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from app.datastore.continuous_build import (
    ContinuousBuildResult,
    build_continuous_from_store,
    read_root_raw_frame,
)
from app.datastore.futures_continuous import continuous_config_hash
from app.datastore.ingest import ingest_local_futures_csv
from app.datastore.store import (
    CONTINUOUS_COLUMNS,
    RawFuturesStore,
    raw_data_version_hash,
)
from app.instruments import get_instrument

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "futures_csv"
YM_ROLL = FIXTURES / "ym_roll.csv"

# The fixture declares source=synthetic (matching esm25.csv / nqm25.csv).
_SOURCE = "synthetic"

# Numeric columns that must survive the continuous store round-trip.
_PRICE_COLUMNS = [
    "open_raw", "high_raw", "low_raw", "close_raw",
    "open_adjusted", "high_adjusted", "low_adjusted", "close_adjusted",
]


def _ingest_ym(tmp_path: Path) -> tuple[RawFuturesStore, Path]:
    """Ingest the committed YM roll fixture into a tmp RawFuturesStore.

    Asserts the ingest itself succeeded (both contracts, one root, all rows),
    then returns ``(store, base_dir)`` for the continuous build.
    """
    base = tmp_path / "store"
    report = ingest_local_futures_csv([YM_ROLL], base_dir=base, prefer_parquet=False)

    assert report.roots == ["YM"]
    assert {(c.root_symbol, c.contract_symbol) for c in report.contracts} == {
        ("YM", "YMM25"),
        ("YM", "YMU25"),
    }
    assert report.rows_written == 8  # 3 YMM25 + 5 YMU25
    return RawFuturesStore(base, prefer_parquet=False), base


def test_ym_end_to_end_ingest_and_continuous_build(tmp_path):
    store, base = _ingest_ym(tmp_path)

    continuous, result = build_continuous_from_store(store, source=_SOURCE, root="YM")

    # (a) the build produced output with the canonical continuous schema.
    assert isinstance(result, ContinuousBuildResult)
    assert list(continuous.columns) == CONTINUOUS_COLUMNS
    assert result.rows == len(continuous) == 5 > 0
    assert result.root_symbol == "YM" and result.source == _SOURCE
    assert result.adjustment_method == "ratio"
    assert result.contracts == ["YMM25", "YMU25"]
    assert result.start == "2025-06-16" and result.end == "2025-06-20"

    # (b) the roll schedule behaves as expected: one YMM25 -> YMU25 crossover.
    assert len(result.roll_events) == 1
    ev = result.roll_events[0]
    assert ev["from_contract"] == "YMM25" and ev["to_contract"] == "YMU25"
    assert ev["rule_used"] == "volume_open_interest"
    assert ev["decision_date"] == "2025-06-18"  # first session next leads on vol AND OI
    assert ev["roll_date"] == "2025-06-19"       # next calendar session after the decision

    # active contract transitions front -> next across the roll seam.
    active = continuous["active_contract"]
    assert active.iloc[0] == "YMM25" and active.iloc[-1] == "YMU25"
    assert set(active) == {"YMM25", "YMU25"}
    assert int(continuous["roll_flag"].sum()) == 1  # exactly one seam flagged

    # (c) continuous_config_hash is deterministic and matches the existing helper;
    #     a rebuild is byte-for-byte identical (no hidden nondeterminism).
    stacked = read_root_raw_frame(store, _SOURCE, "YM")
    spec = get_instrument("YM")
    assert result.continuous_config_hash == continuous_config_hash(stacked, spec, "ratio")
    assert result.raw_data_version_hash == raw_data_version_hash(stacked)
    # per-contract provenance hashes match the stored raw bars.
    for contract in ("YMM25", "YMU25"):
        assert result.contract_version_hashes[contract] == raw_data_version_hash(
            store.read_raw("YM", contract, _SOURCE)
        )

    continuous2, result2 = build_continuous_from_store(store, source=_SOURCE, root="YM")
    pd.testing.assert_frame_equal(continuous, continuous2)
    assert result2.continuous_config_hash == result.continuous_config_hash
    assert result2.raw_data_version_hash == result.raw_data_version_hash

    # (d) stored/read-back continuous data preserves the expected invariants.
    write_path = store.write_continuous(continuous, source=_SOURCE)
    assert write_path.exists() and str(write_path).startswith(str(base))
    read_back = store.read_continuous("YM", _SOURCE, "ratio")

    assert list(read_back.columns) == CONTINUOUS_COLUMNS
    assert len(read_back) == len(continuous) == 5
    # non-float structure preserved exactly across the round-trip.
    assert read_back["active_contract"].tolist() == continuous["active_contract"].tolist()
    assert read_back["active_contract"].iloc[0] == "YMM25"
    assert read_back["active_contract"].iloc[-1] == "YMU25"
    assert read_back["roll_flag"].tolist() == continuous["roll_flag"].tolist()
    assert int(read_back["roll_flag"].sum()) == 1
    # numeric OHLC (raw + adjusted) preserved, all finite and strictly positive.
    assert np.allclose(
        read_back[_PRICE_COLUMNS].to_numpy(), continuous[_PRICE_COLUMNS].to_numpy()
    )
    assert (read_back[_PRICE_COLUMNS].to_numpy() > 0).all()
