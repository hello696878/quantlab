"""
Tests for scripts/report_local_futures_csv.py (read-only per-root CSV report).

Runs the script as a subprocess (it is a CLI, not a package module) against
normalized output produced from the synthetic fixtures by
scripts/normalize_local_futures_csv.py, mirroring the real workflow:

    raw fixture CSV -> normalize -> processed CSV -> report summary

Pins: ES and NQ one-contract P&L, tick-based == multiplier-based P&L (tied to
the audited ``long_trade_report`` so the numbers can't silently drift), the
exit-code contract, unknown-root rejection, and that inputs are never mutated.
"""

import subprocess
import sys
from pathlib import Path

from app.datastore import load_futures_bars_csv
from app.reports import long_trade_report

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_SCRIPT = REPO_ROOT / "scripts" / "report_local_futures_csv.py"
NORMALIZE_SCRIPT = REPO_ROOT / "scripts" / "normalize_local_futures_csv.py"
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "futures_csv"


def _run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _normalize_fixtures(out_dir: Path) -> None:
    """Produce ES_daily.csv / NQ_daily.csv under ``out_dir`` from the fixtures."""
    result = _run(
        NORMALIZE_SCRIPT, "--input", str(FIXTURES_DIR), "--output-dir", str(out_dir)
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _expected(fixture_name: str):
    """Expected one-contract report numbers via the audited long_trade_report."""
    return long_trade_report(load_futures_bars_csv(FIXTURES_DIR / fixture_name))


def test_es_report_pnl_correct(tmp_path):
    _normalize_fixtures(tmp_path)
    result = _run(REPORT_SCRIPT, "--input", str(tmp_path / "ES_daily.csv"))
    assert result.returncode == 0, result.stdout + result.stderr
    r = _expected("esm25.csv")
    assert r.pnl_usd == 387.50  # 7.75 pts * $50/pt (guards the fixture itself)
    out = result.stdout
    assert "root_symbol:         ES" in out
    assert "rows:                5" in out
    assert "first_close:         6004.25" in out
    assert "last_close:          6012.00" in out
    assert f"price_move:          {r.price_move:.2f}" in out
    assert f"tick_move:           {r.tick_move:.1f}" in out
    assert f"pnl_usd (1 contract): {r.pnl_usd:.2f}" in out
    assert f"tick_pnl_usd:        {r.tick_pnl_usd:.2f}" in out
    assert "pnl_check (direct == tick-based): OK" in out
    assert "RESULT: OK" in out


def test_nq_report_pnl_correct(tmp_path):
    _normalize_fixtures(tmp_path)
    result = _run(REPORT_SCRIPT, "--input", str(tmp_path / "NQ_daily.csv"))
    assert result.returncode == 0, result.stdout + result.stderr
    r = _expected("nqm25.csv")
    assert r.pnl_usd == 1490.00  # 74.50 pts * $20/pt (guards the fixture itself)
    out = result.stdout
    assert "root_symbol:         NQ" in out
    assert "first_close:         21825.50" in out
    assert "last_close:          21900.00" in out
    assert f"pnl_usd (1 contract): {r.pnl_usd:.2f}" in out
    assert f"tick_pnl_usd:        {r.tick_pnl_usd:.2f}" in out
    assert "pnl_check (direct == tick-based): OK" in out


def test_tick_pnl_matches_multiplier_pnl(tmp_path):
    # The whole normalized folder: every root's direct P&L must equal its
    # tick-based P&L (the spec tick-value invariant, end to end).
    _normalize_fixtures(tmp_path)
    result = _run(REPORT_SCRIPT, "--input", str(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    for fixture in ("esm25.csv", "nqm25.csv"):
        r = _expected(fixture)
        assert r.pnl_matches is True
        assert r.pnl_usd == r.tick_pnl_usd
        assert f"pnl_usd (1 contract): {r.pnl_usd:.2f}" in result.stdout
        assert f"tick_pnl_usd:        {r.tick_pnl_usd:.2f}" in result.stdout
    assert result.stdout.count("pnl_check (direct == tick-based): OK") == 2
    assert "FAIL" not in result.stdout


def test_folder_reports_both_roots(tmp_path):
    _normalize_fixtures(tmp_path)
    result = _run(REPORT_SCRIPT, "--input", str(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "root_symbol:         ES" in result.stdout
    assert "root_symbol:         NQ" in result.stdout
    assert "overall: 2 root(s)" in result.stdout
    assert "RESULT: OK" in result.stdout


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
    result = _run(REPORT_SCRIPT, "--input", str(bad))
    assert result.returncode != 0
    assert "[FAIL]" in result.stdout
    assert "RESULT: FAIL" in result.stdout


def test_multi_contract_root_reports_naive_move_with_note(tmp_path):
    # A normalized per-root file can legitimately merge >1 contract (the
    # normalizer does exactly this). The report must still summarize the root
    # with a naive first-close -> last-close move ACROSS contracts AND flag
    # that it is not roll-adjusted -- the guard that proves the script honors
    # the hard "no continuous-futures stitching" Phase 1 constraint.
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    header = (
        "timestamp,open,high,low,close,volume,open_interest,"
        "root_symbol,contract_symbol,expiry,source,timezone"
    )
    esm = (  # June contract: earliest bar's close (6004.25) is the entry
        "2025-06-09T21:00:00+00:00,5998.00,6006.50,5990.25,6004.25,1200000,1800000,"
        "ES,ESM25,2025-06-20,synthetic,America/Chicago\n"
        "2025-06-10T21:00:00+00:00,6004.25,6012.75,5999.50,6010.50,1150000,1795000,"
        "ES,ESM25,2025-06-20,synthetic,America/Chicago"
    )
    esu = (  # Sep contract: latest bar's close (6130.00) is the exit
        "2025-09-10T21:00:00+00:00,6115.00,6125.00,6110.00,6120.00,900000,,"
        "ES,ESU25,2025-09-19,synthetic,America/Chicago\n"
        "2025-09-11T21:00:00+00:00,6120.00,6135.00,6118.00,6130.00,910000,,"
        "ES,ESU25,2025-09-19,synthetic,America/Chicago"
    )
    (in_dir / "esm.csv").write_text(f"{header}\n{esm}\n", encoding="utf-8")
    (in_dir / "esu.csv").write_text(f"{header}\n{esu}\n", encoding="utf-8")

    # Merge both contracts into one normalized ES_daily.csv via the real pipeline.
    norm = _run(NORMALIZE_SCRIPT, "--input", str(in_dir), "--output-dir", str(out_dir))
    assert norm.returncode == 0, norm.stdout + norm.stderr

    result = _run(REPORT_SCRIPT, "--input", str(out_dir / "ES_daily.csv"))
    assert result.returncode == 0, result.stdout + result.stderr
    out = result.stdout
    assert "contracts:           ESM25, ESU25" in out
    assert "first_close:         6004.25" in out  # earliest bar, ESM25
    assert "last_close:          6130.00" in out  # latest bar, ESU25
    assert "price_move:          125.75" in out   # naive move straight across the roll
    assert "tick_move:           503.0" in out    # 125.75 / 0.25
    assert "pnl_usd (1 contract): 6287.50" in out  # 125.75 * $50/pt
    assert "tick_pnl_usd:        6287.50" in out   # 503 ticks * $12.50/tick
    assert "pnl_check (direct == tick-based): OK" in out
    assert "not roll-adjusted" in out  # the no-continuous-stitching guard


def test_missing_path_exits_nonzero(tmp_path):
    result = _run(REPORT_SCRIPT, "--input", str(tmp_path / "does_not_exist"))
    assert result.returncode != 0
    assert "not found" in result.stdout


def test_folder_without_csv_exits_nonzero(tmp_path):
    result = _run(REPORT_SCRIPT, "--input", str(tmp_path))
    assert result.returncode != 0
    assert "no CSV files" in result.stdout


def test_empty_input_arg_exits_nonzero():
    # Path("") normalizes to "." — must fail cleanly, not scan the cwd.
    result = _run(REPORT_SCRIPT, "--input", "")
    assert result.returncode != 0
    assert "must not be empty" in result.stdout


def test_report_does_not_mutate_inputs(tmp_path):
    _normalize_fixtures(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.glob("*.csv")}
    result = _run(REPORT_SCRIPT, "--input", str(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    after = {p.name: p.read_bytes() for p in tmp_path.glob("*.csv")}
    assert before == after
