"""
Phase 8 commit 1 — store-to-continuous adapter/helpers.

Covers the pure adapter (`list_stored_contracts`, `read_root_raw_frame`,
`build_continuous_from_store`) only — no CLI, no persistence, no report JSON.

The existing fixtures (`esm25.csv`, `nqm25.csv`) are single-contract, different
roots, so they cannot roll.  These tests **generate same-root ES multi-contract
data in `tmp_path`** (ESM25 + ESU25 with correct spec-derived expiries and a
volume/OI crossover), ingest it via the Phase 7 ingest helper, then build.
Everything stays under `tmp_path`; no network; nothing written outside `tmp_path`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

from app.datastore.continuous_build import (
    ContinuousBuildResult,
    ContinuousSourceError,
    build_continuous_from_store,
    list_stored_contracts,
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

_BACKEND = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[2]

_HEADER = (
    "timestamp,open,high,low,close,volume,open_interest,"
    "root_symbol,contract_symbol,expiry,source,timezone"
)


def _es_roll_csvs(dirpath: Path) -> tuple[Path, Path]:
    """Write ESM25 + ESU25 CSVs: 15 business days ending the session before the
    ESM25 expiry (2025-06-20), with ESU25 volume AND OI overtaking ESM25 (a clean
    crossover roll). Expiries are the real spec-derived third Fridays."""
    dates = list(pd.bdate_range("2025-05-30", "2025-06-19"))  # 15 sessions
    n = len(dates)
    front_vol = [10000 - 300 * i for i in range(n)]
    next_vol = [1000 + 700 * i for i in range(n)]
    front_oi = [50000 - 1000 * i for i in range(n)]
    next_oi = [5000 + 5000 * i for i in range(n)]

    def rows(symbol: str, expiry: str, vols: list[int], ois: list[int], base_price: float) -> list[str]:
        out = []
        for i, d in enumerate(dates):
            openp = base_price + i
            closep = openp + 1.0
            high = max(openp, closep) + 1.0
            low = min(openp, closep) - 1.0
            ts = d.strftime("%Y-%m-%dT21:00:00+00:00")
            out.append(
                f"{ts},{openp:.2f},{high:.2f},{low:.2f},{closep:.2f},"
                f"{int(vols[i])},{int(ois[i])},ES,{symbol},{expiry},synthetic,America/Chicago"
            )
        return out

    esm = dirpath / "esm25.csv"
    esu = dirpath / "esu25.csv"
    esm.write_text(
        "\n".join([_HEADER, *rows("ESM25", "2025-06-20", front_vol, front_oi, 5000.0)]) + "\n",
        encoding="utf-8",
    )
    esu.write_text(
        "\n".join([_HEADER, *rows("ESU25", "2025-09-19", next_vol, next_oi, 5100.0)]) + "\n",
        encoding="utf-8",
    )
    return esm, esu


def _ingest_es_roll(tmp_path: Path, source: str = "csv_fixture") -> tuple[RawFuturesStore, Path]:
    """Generate + ingest ES M/U into a tmp RawFuturesStore; return (store, base_dir)."""
    csv_dir = tmp_path / "csv"
    csv_dir.mkdir()
    esm, esu = _es_roll_csvs(csv_dir)
    base = tmp_path / "store"
    ingest_local_futures_csv([esm, esu], base_dir=base, source=source, prefer_parquet=False)
    return RawFuturesStore(base, prefer_parquet=False), base


def _store_files(base: Path) -> set[Path]:
    return {p for p in base.rglob("*") if p.is_file()}


# --------------------------------------------------------------------------- #
# list_stored_contracts / read_root_raw_frame
# --------------------------------------------------------------------------- #


def test_list_stored_contracts_returns_both(tmp_path):
    store, _ = _ingest_es_roll(tmp_path)
    assert list_stored_contracts(store, "csv_fixture", "ES") == ["ESM25", "ESU25"]


def test_list_stored_contracts_empty_when_absent(tmp_path):
    store, _ = _ingest_es_roll(tmp_path)
    assert list_stored_contracts(store, "csv_fixture", "NQ") == []
    assert list_stored_contracts(store, "other_source", "ES") == []


def test_read_root_raw_frame_stacks_and_validates(tmp_path):
    store, _ = _ingest_es_roll(tmp_path)
    frame = read_root_raw_frame(store, "csv_fixture", "ES")
    assert set(frame["contract_symbol"]) == {"ESM25", "ESU25"}
    assert len(frame) == 30  # 15 sessions x 2 contracts
    # already normalized (sorted by contract, timestamp)
    assert frame["contract_symbol"].is_monotonic_increasing


def test_read_root_raw_frame_missing_raises(tmp_path):
    store, _ = _ingest_es_roll(tmp_path)
    with pytest.raises(ContinuousSourceError):
        read_root_raw_frame(store, "csv_fixture", "NQ")


# --------------------------------------------------------------------------- #
# build_continuous_from_store
# --------------------------------------------------------------------------- #


def test_build_returns_frame_and_result(tmp_path):
    store, _ = _ingest_es_roll(tmp_path)
    continuous, result = build_continuous_from_store(store, source="csv_fixture", root="ES")
    assert isinstance(result, ContinuousBuildResult)
    assert result.contracts == ["ESM25", "ESU25"]
    assert result.root_symbol == "ES" and result.source == "csv_fixture"
    assert result.adjustment_method == "ratio"
    assert result.rows == len(continuous) > 0
    assert result.output_path == ""  # no persistence in this commit


def test_continuous_frame_has_expected_columns(tmp_path):
    store, _ = _ingest_es_roll(tmp_path)
    continuous, _ = build_continuous_from_store(store, source="csv_fixture", root="ES")
    assert list(continuous.columns) == CONTINUOUS_COLUMNS


def test_active_contract_transitions_esm_to_esu(tmp_path):
    store, _ = _ingest_es_roll(tmp_path)
    continuous, _ = build_continuous_from_store(store, source="csv_fixture", root="ES")
    active = continuous["active_contract"]
    assert set(active) == {"ESM25", "ESU25"}
    assert active.iloc[0] == "ESM25"
    assert active.iloc[-1] == "ESU25"


def test_roll_events_contain_esm_to_esu(tmp_path):
    store, _ = _ingest_es_roll(tmp_path)
    _, result = build_continuous_from_store(store, source="csv_fixture", root="ES")
    assert len(result.roll_events) == 1
    ev = result.roll_events[0]
    assert ev["from_contract"] == "ESM25" and ev["to_contract"] == "ESU25"
    assert ev["roll_date"] and ev["rule_used"]


def test_start_end_are_set(tmp_path):
    store, _ = _ingest_es_roll(tmp_path)
    _, result = build_continuous_from_store(store, source="csv_fixture", root="ES")
    assert result.start == "2025-05-30"
    assert result.end == "2025-06-19"


def test_continuous_config_hash_matches_existing(tmp_path):
    store, _ = _ingest_es_roll(tmp_path)
    stacked = read_root_raw_frame(store, "csv_fixture", "ES")
    spec = get_instrument("ES")
    _, result = build_continuous_from_store(store, source="csv_fixture", root="ES")
    assert result.continuous_config_hash == continuous_config_hash(stacked, spec, "ratio")


def test_stacked_raw_hash_matches_existing(tmp_path):
    store, _ = _ingest_es_roll(tmp_path)
    stacked = read_root_raw_frame(store, "csv_fixture", "ES")
    _, result = build_continuous_from_store(store, source="csv_fixture", root="ES")
    assert result.raw_data_version_hash == raw_data_version_hash(stacked)


def test_per_contract_hashes_match_stored(tmp_path):
    store, _ = _ingest_es_roll(tmp_path)
    _, result = build_continuous_from_store(store, source="csv_fixture", root="ES")
    for contract in ("ESM25", "ESU25"):
        expected = raw_data_version_hash(store.read_raw("ES", contract, "csv_fixture"))
        assert result.contract_version_hashes[contract] == expected


def test_build_is_deterministic(tmp_path):
    store, _ = _ingest_es_roll(tmp_path)
    frame1, res1 = build_continuous_from_store(store, source="csv_fixture", root="ES")
    frame2, res2 = build_continuous_from_store(store, source="csv_fixture", root="ES")
    pd.testing.assert_frame_equal(frame1, frame2)
    assert res1.continuous_config_hash == res2.continuous_config_hash
    assert res1.raw_data_version_hash == res2.raw_data_version_hash
    assert res1.contract_version_hashes == res2.contract_version_hashes


def test_ratio_vs_panama_differ(tmp_path):
    store, _ = _ingest_es_roll(tmp_path)
    ratio_frame, ratio_res = build_continuous_from_store(
        store, source="csv_fixture", root="ES", adjustment_method="ratio"
    )
    panama_frame, panama_res = build_continuous_from_store(
        store, source="csv_fixture", root="ES", adjustment_method="panama"
    )
    assert ratio_res.continuous_config_hash != panama_res.continuous_config_hash
    assert panama_res.adjustment_method == "panama"
    # adjusted close differs (older segment is back-adjusted differently)
    assert not ratio_frame["close_adjusted"].equals(panama_frame["close_adjusted"])


# --------------------------------------------------------------------------- #
# failure modes
# --------------------------------------------------------------------------- #


def test_missing_source_root_raises(tmp_path):
    store, _ = _ingest_es_roll(tmp_path)
    with pytest.raises(ContinuousSourceError):
        build_continuous_from_store(store, source="nope", root="ES")
    with pytest.raises(ContinuousSourceError):
        build_continuous_from_store(store, source="csv_fixture", root="NQ")


def test_invalid_adjustment_method_fails(tmp_path):
    store, _ = _ingest_es_roll(tmp_path)
    with pytest.raises(ValueError):
        build_continuous_from_store(store, source="csv_fixture", root="ES", adjustment_method="bogus")


def test_non_futures_spec_fails_clearly(tmp_path):
    store, _ = _ingest_es_roll(tmp_path)
    with pytest.raises(ContinuousSourceError):
        build_continuous_from_store(store, source="csv_fixture", root="ES", spec=object())


# --------------------------------------------------------------------------- #
# safety: no writes, no repo artifacts, no forbidden imports, no new hash
# --------------------------------------------------------------------------- #


def test_build_writes_nothing(tmp_path):
    store, base = _ingest_es_roll(tmp_path)
    before = _store_files(base)
    build_continuous_from_store(store, source="csv_fixture", root="ES")
    assert _store_files(base) == before          # build only reads
    assert not (base / "continuous").exists()    # no continuous output written


def test_no_repo_root_data_or_artifacts(tmp_path, monkeypatch):
    before_data = (_REPO_ROOT / "data").exists()
    before_artifacts = (_REPO_ROOT / "artifacts").exists()
    before_backend_data = (_BACKEND / "data").exists()
    monkeypatch.chdir(tmp_path)
    store, base = _ingest_es_roll(tmp_path)
    build_continuous_from_store(store, source="csv_fixture", root="ES")
    assert all(str(p).startswith(str(tmp_path)) for p in _store_files(base))
    assert (_REPO_ROOT / "data").exists() == before_data
    assert (_REPO_ROOT / "artifacts").exists() == before_artifacts
    assert (_BACKEND / "data").exists() == before_backend_data


def test_continuous_build_module_no_network_or_forbidden_imports():
    src = (_BACKEND / "app" / "datastore" / "continuous_build.py").read_text(encoding="utf-8")
    assert not re.search(
        r"(?m)^\s*(from|import)\s+\S*\b(requests|urllib|httpx|socket|aiohttp)\b", src
    )
    assert not re.search(
        r"(?m)^\s*(from|import)\s+\S*"
        r"(features|labels|ml_signal|research_cli)\b",
        src,
    )


def test_continuous_build_module_invents_no_new_hash():
    src = (_BACKEND / "app" / "datastore" / "continuous_build.py").read_text(encoding="utf-8")
    assert "hashlib" not in src and "sha256" not in src
    # reuses the existing hash functions
    assert "raw_data_version_hash" in src and "continuous_config_hash" in src
