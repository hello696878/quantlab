"""
Tests for scripts/run_local_futures_buyhold_report.py (per-contract report).

Runs the script as a subprocess (it is a CLI, not a package module) against
normalized output produced from the synthetic fixtures by
scripts/normalize_local_futures_csv.py, mirroring the research path:

    normalized CSV -> load bars -> metadata -> buy-and-hold report

Pins: ES and NQ one-contract buy-and-hold P&L, tick-based == multiplier-based
P&L (tied to the audited ``long_trade_report`` so the numbers can't silently
drift), the exit-code contract, and unknown-root rejection.
"""

import shutil
import subprocess
import sys
from pathlib import Path

from app.datastore import load_futures_bars_csv
from app.reports import long_trade_report

REPO_ROOT = Path(__file__).resolve().parents[2]
BUYHOLD_SCRIPT = REPO_ROOT / "scripts" / "run_local_futures_buyhold_report.py"
NORMALIZE_SCRIPT = REPO_ROOT / "scripts" / "normalize_local_futures_csv.py"
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "futures_csv"

# The exact fixtures these ES/NQ pipeline tests are about (staged into an
# isolated dir — the scripts discover CSVs recursively, and the live fixtures
# folder may hold fixtures for other tests, e.g. the YM roll fixture, so
# aggregate assertions must not depend on the developer's working tree).
PIPELINE_FIXTURES = ("esm25.csv", "nqm25.csv")


def _run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _normalize_fixtures(tmp_path: Path) -> Path:
    """Stage the ES/NQ fixtures into ``tmp_path/raw`` and normalize them into
    ``tmp_path/normalized`` (returned as the dir holding ES_daily.csv /
    NQ_daily.csv)."""
    raw_dir = tmp_path / "raw"
    norm_dir = tmp_path / "normalized"
    raw_dir.mkdir()
    for name in PIPELINE_FIXTURES:
        shutil.copy(FIXTURES_DIR / name, raw_dir / name)
    result = _run(
        NORMALIZE_SCRIPT, "--input", str(raw_dir), "--output-dir", str(norm_dir)
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return norm_dir


def _expected(fixture_name: str):
    """Expected one-contract report numbers via the audited long_trade_report."""
    return long_trade_report(load_futures_bars_csv(FIXTURES_DIR / fixture_name))


def test_es_buyhold_pnl_correct(tmp_path):
    norm_dir = _normalize_fixtures(tmp_path)
    result = _run(BUYHOLD_SCRIPT, "--input", str(norm_dir / "ES_daily.csv"))
    assert result.returncode == 0, result.stdout + result.stderr
    r = _expected("esm25.csv")
    assert r.pnl_usd == 387.50  # 7.75 pts * $50/pt (guards the fixture itself)
    out = result.stdout
    assert "ES / ESM25 buy-and-hold 1 contract, 5 bar(s)" in out
    assert "entry_timestamp:     2025-06-09T21:00:00+00:00" in out
    assert "exit_timestamp:      2025-06-13T21:00:00+00:00" in out
    assert "entry_close:         6004.25" in out
    assert "exit_close:          6012.00" in out
    assert f"price_move:          {r.price_move:.2f}" in out
    assert f"tick_move:           {r.tick_move:.1f}" in out
    assert f"pnl_by_multiplier:   {r.pnl_usd:.2f}" in out
    assert f"pnl_by_ticks:        {r.tick_pnl_usd:.2f}" in out
    assert "pnl_check (multiplier == ticks): OK" in out
    assert "RESULT: OK" in out
    # The spec warnings the audited helper carries must be surfaced (the
    # instrument yamls ask for them in every report).
    assert r.warnings
    assert f"warnings ({len(r.warnings)}):" in out
    for w in r.warnings:
        assert w in out


def test_nq_buyhold_pnl_correct(tmp_path):
    norm_dir = _normalize_fixtures(tmp_path)
    result = _run(BUYHOLD_SCRIPT, "--input", str(norm_dir / "NQ_daily.csv"))
    assert result.returncode == 0, result.stdout + result.stderr
    r = _expected("nqm25.csv")
    assert r.pnl_usd == 1490.00  # 74.50 pts * $20/pt (guards the fixture itself)
    out = result.stdout
    assert "NQ / NQM25 buy-and-hold 1 contract, 5 bar(s)" in out
    assert "entry_close:         21825.50" in out
    assert "exit_close:          21900.00" in out
    assert f"pnl_by_multiplier:   {r.pnl_usd:.2f}" in out
    assert f"pnl_by_ticks:        {r.tick_pnl_usd:.2f}" in out
    assert "pnl_check (multiplier == ticks): OK" in out


def test_tick_and_multiplier_pnl_match(tmp_path):
    # The whole normalized folder: every contract's multiplier-based P&L must
    # equal its tick-based P&L (the spec tick-value invariant, end to end).
    norm_dir = _normalize_fixtures(tmp_path)
    result = _run(BUYHOLD_SCRIPT, "--input", str(norm_dir))
    assert result.returncode == 0, result.stdout + result.stderr
    for fixture in ("esm25.csv", "nqm25.csv"):
        r = _expected(fixture)
        assert r.pnl_matches is True
        assert r.pnl_usd == r.tick_pnl_usd
        assert f"pnl_by_multiplier:   {r.pnl_usd:.2f}" in result.stdout
        assert f"pnl_by_ticks:        {r.tick_pnl_usd:.2f}" in result.stdout
    assert result.stdout.count("pnl_check (multiplier == ticks): OK") == 2
    assert "overall: 2 contract(s)" in result.stdout
    assert "FAIL" not in result.stdout


def test_unknown_root_exits_nonzero(tmp_path):
    # A well-formed row whose root has no registry spec must fail validation
    # (and thus the report), not silently report a bogus P&L.
    bad = tmp_path / "xx.csv"
    header = (
        "timestamp,open,high,low,close,volume,open_interest,"
        "root_symbol,contract_symbol,expiry,source,timezone"
    )
    row = (
        "2025-06-09T21:00:00+00:00,100.0,105.0,95.0,102.0,1000,,"
        "XX,XXM25,2025-06-20,synthetic,America/Chicago"
    )
    bad.write_text(f"{header}\n{row}\n", encoding="utf-8")
    result = _run(BUYHOLD_SCRIPT, "--input", str(bad))
    assert result.returncode != 0
    assert "[FAIL]" in result.stdout
    assert "RESULT: FAIL" in result.stdout


def test_missing_path_exits_nonzero(tmp_path):
    result = _run(BUYHOLD_SCRIPT, "--input", str(tmp_path / "does_not_exist"))
    assert result.returncode != 0
    assert "not found" in result.stdout


def test_report_does_not_mutate_inputs(tmp_path):
    norm_dir = _normalize_fixtures(tmp_path)
    before = {p.name: p.read_bytes() for p in norm_dir.glob("*.csv")}
    result = _run(BUYHOLD_SCRIPT, "--input", str(norm_dir))
    assert result.returncode == 0, result.stdout + result.stderr
    after = {p.name: p.read_bytes() for p in norm_dir.glob("*.csv")}
    assert before == after
