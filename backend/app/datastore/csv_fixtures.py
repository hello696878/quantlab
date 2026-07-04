"""
Synthetic CSV fixture loader for futures daily bars (ingestion phase I1).

Reads a **local** CSV whose header contains the canonical 12 raw-bar columns
(:data:`app.datastore.store.REQUIRED_COLUMNS`) and returns one validated
:class:`~app.datastore.daily_bar.FuturesDailyBar` per row.  This is the
first, smallest CSV entry path from docs/FUTURES_DATA_INGESTION_PLAN.md
(§9, I1): local files only, synthetic data only, no network, no writes —
the input file is opened read-only and never modified.

File-level rules on top of what ``FuturesDailyBar`` already enforces per
record (positive prices, OHLC envelope, registry link, root/contract match):

* the header must contain every required column (extra columns are ignored,
  mirroring ``validate_raw_futures``; a UTF-8 BOM on the header is tolerated);
* rows with more cells than the header are rejected (a shifted row must
  never load with mislabeled fields);
* ``timestamp`` / ``expiry`` cells must be ISO format (parsed explicitly, so
  a digit-only cell can never be misread as Unix epoch seconds);
* a blank ``open_interest`` cell maps to ``None`` (missing OI is allowed);
* duplicate ``(contract_symbol, timestamp)`` pairs are rejected;
* a file with no data rows is rejected.

Registry cross-checks per row (plan §6 obligations 2–4 — the checks
``FuturesDailyBar`` deliberately does not enforce):

* the contract month must be in the instrument's ``contract_months`` cycle;
* ``expiry`` must equal the spec-derived expiry for the contract symbol;
* ``timezone`` must equal the spec's session timezone.

All failures raise :class:`FixtureFormatError` naming the file (and row).
"""

from __future__ import annotations

import csv
import datetime
from pathlib import Path

from pydantic import ValidationError

from app.datastore.daily_bar import FuturesDailyBar
from app.datastore.store import REQUIRED_COLUMNS
from app.instruments import get_instrument, parse_contract_symbol


class FixtureFormatError(ValueError):
    """Raised when a fixture CSV cannot be loaded as valid futures daily bars."""


def _parse_iso(cell: object, field: str, kind: type, path: Path, line_num: int):
    """Parse a timestamp/expiry cell strictly as ISO format, failing loudly."""
    try:
        return kind.fromisoformat(str(cell).strip())
    except ValueError as exc:
        raise FixtureFormatError(
            f"{path.name} line {line_num}: invalid {field} {cell!r} "
            f"(expected ISO format)"
        ) from exc


def _check_against_spec(bar: FuturesDailyBar, path: Path, line_num: int) -> None:
    """Registry cross-checks beyond the model's own rules (plan §6)."""
    spec = get_instrument(bar.root_symbol)
    month_code = parse_contract_symbol(bar.contract_symbol).month_code
    if not spec.is_cycle_month(month_code):
        raise FixtureFormatError(
            f"{path.name} line {line_num}: {bar.contract_symbol!r} month "
            f"{month_code!r} is not in the {bar.root_symbol} cycle "
            f"{spec.contract_months}"
        )
    spec_expiry = spec.expiry_for_symbol(bar.contract_symbol)
    if bar.expiry != spec_expiry:
        raise FixtureFormatError(
            f"{path.name} line {line_num}: expiry {bar.expiry} != spec-derived "
            f"expiry {spec_expiry} for {bar.contract_symbol}"
        )
    if bar.timezone != spec.session.timezone:
        raise FixtureFormatError(
            f"{path.name} line {line_num}: timezone {bar.timezone!r} != spec "
            f"session timezone {spec.session.timezone!r}"
        )


def load_futures_bars_csv(path: str | Path) -> list[FuturesDailyBar]:
    """Load one local fixture CSV into a list of validated daily bars."""
    path = Path(path)
    if not path.is_file():
        raise FixtureFormatError(f"fixture CSV not found: {path}")

    # utf-8-sig strips a leading BOM (Excel's "CSV UTF-8") and is a no-op
    # for plain UTF-8, so the header check never sees an invisible prefix.
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise FixtureFormatError(f"{path.name}: missing required columns: {missing}")

        bars: list[FuturesDailyBar] = []
        seen: set[tuple[str, str]] = set()
        for line_num, row in enumerate(reader, start=2):
            if None in row:  # DictReader parks overflow cells under None
                raise FixtureFormatError(
                    f"{path.name} line {line_num}: row has more cells than header"
                )
            fields = {c: row[c] for c in REQUIRED_COLUMNS}
            fields["timestamp"] = _parse_iso(
                fields["timestamp"], "timestamp", datetime.datetime, path, line_num
            )
            fields["expiry"] = _parse_iso(
                fields["expiry"], "expiry", datetime.date, path, line_num
            )
            if (fields["open_interest"] or "").strip() == "":
                fields["open_interest"] = None
            try:
                bar = FuturesDailyBar(**fields)
            except ValidationError as exc:
                raise FixtureFormatError(f"{path.name} line {line_num}: {exc}") from exc
            _check_against_spec(bar, path, line_num)
            key = (bar.contract_symbol, bar.timestamp.isoformat())
            if key in seen:
                raise FixtureFormatError(
                    f"{path.name} line {line_num}: duplicate bar for "
                    f"(contract_symbol, timestamp) = {key}"
                )
            seen.add(key)
            bars.append(bar)

    if not bars:
        raise FixtureFormatError(f"{path.name}: no data rows")
    return bars
