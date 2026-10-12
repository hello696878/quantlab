"""Read-only v1 acceptance CLI; no files, database, providers or price repair."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.datastore.ingest import preview_futures_source
from app.datastore.futures_continuous import build_continuous_futures, compute_roll_schedule
from app.datastore.store import raw_data_version_hash
from app.futures_pit.adapter import AdapterRequest, Capabilities
from app.futures_pit.calendar import timezone_provenance
from app.futures_pit.diagnostics import derived_identity, validate_continuous
from app.futures_pit.models import instant
from app.futures_pit.revisions import as_of, compare, legacy_frame, table_hash
from app.instruments import get_instrument


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="explicitly select the tiny invented repository corpus")
    parser.add_argument("--provider", choices=("local_file", "external"), default="local_file")
    parser.add_argument("--csv")
    parser.add_argument("--metadata")
    parser.add_argument("--calendar")
    parser.add_argument("--correction-csv")
    parser.add_argument("--correction-metadata")
    parser.add_argument("--as-of", help="explicit aware ISO cutoff; demo defaults to 2025-06-21T12:00:00Z")
    parser.add_argument("--mode", choices=("declared_source", "local_observed"), default="declared_source")
    parser.add_argument("--continuous", action="store_true")
    args = parser.parse_args(argv)
    if args.demo:
        if any((args.csv, args.metadata, args.calendar, args.correction_csv, args.correction_metadata)):
            parser.error("--demo cannot be mixed with explicit input paths")
        corpus = ROOT / "backend/tests/fixtures/futures_pit"
        args.csv, args.metadata, args.calendar = (str(corpus / p) for p in ("bars.csv", "metadata.json", "calendar.json"))
        args.correction_csv, args.correction_metadata = (str(corpus / p) for p in ("correction.csv", "correction-metadata.json"))
        args.continuous = True
        args.as_of = args.as_of or "2025-06-21T12:00:00Z"
    try:
        result = preview_futures_source(AdapterRequest(provider=args.provider, csv_path=args.csv,
                                                       metadata_path=args.metadata, calendar_path=args.calendar))
        if not args.as_of:
            raise ValueError("non-demo input requires an explicit --as-of cutoff")
        snapshots = (result.snapshot,)
        revisions = ()
        if bool(args.correction_csv) != bool(args.correction_metadata):
            raise ValueError("both correction paths are required")
        if args.correction_csv:
            correction = preview_futures_source(AdapterRequest(provider="local_file", csv_path=args.correction_csv,
                                                               metadata_path=args.correction_metadata, calendar_path=args.calendar))
            if correction.calendar != result.calendar:
                raise ValueError("correction calendar material differs")
            revisions = compare(result.snapshot, correction.snapshot)
            snapshots += (correction.snapshot,)
        chosen = as_of(snapshots, args.as_of, args.mode)
        calendar = result.calendar
        summary = {"schema_version": "futures_pit_preview_v1", "status": "pass", "capabilities": asdict(Capabilities()),
                   "physical_hashes": dict(result.physical_hashes), "envelope_hash": result.envelope_hash,
                   "calendar_hash": calendar.fingerprint, "timezone": timezone_provenance(calendar.timezone),
                   "inspected_at": result.inspected_at, "limitations": result.limitations,
                   "coverage": result.coverage, "missing_fields": result.missing_fields,
                   "calendar": {"open_count_inclusive": calendar.count(calendar.coverage_start, calendar.coverage_end),
                                "coverage_start": str(calendar.coverage_start), "coverage_end": str(calendar.coverage_end),
                                "historical_availability": "declared" if calendar.declared_available_at else "unknown"},
                   "as_of": {"mode": chosen.mode, "cutoff": chosen.cutoff, "selected": len(chosen.bars),
                             "unknown": chosen.excluded_unknown, "future": chosen.excluded_future},
                   "revisions": revisions, "findings": []}
        if args.correction_csv:
            summary["correction_physical_hashes"] = dict(correction.physical_hashes)
            summary["correction_envelope_hash"] = correction.envelope_hash
        if (chosen.excluded_unknown or not chosen.bars or result.snapshot.price_basis == "unknown" or
                calendar.declared_available_at is None or calendar.declared_available_at > instant(args.as_of)):
            summary["status"] = "incomplete"
        if chosen.bars:
            raw = legacy_frame(chosen.bars)
            summary.update(normalized_market_hash=table_hash(chosen.bars), legacy_raw_hash=raw_data_version_hash(raw))
            if args.continuous:
                spec = get_instrument(result.snapshot.root_symbol)
                curve = build_continuous_futures(raw, spec, declared_calendar=calendar)
                events = compute_roll_schedule(raw, spec, declared_calendar=calendar)
                summary["rolls"] = [{"from": e.from_contract, "to": e.to_contract, "decision": str(e.decision_date),
                                     "effective": str(e.roll_date), "metadata": e.metadata} for e in events]
                summary["derived_identity"] = derived_identity(
                    {"envelopes": [result.envelope_hash] + ([correction.envelope_hash] if args.correction_csv else []),
                     "mode": chosen.mode, "cutoff": chosen.cutoff,
                     "selected_revisions": [b.model_dump(mode="json") for b in chosen.bars]},
                    calendar, spec, "ratio")
                summary["findings"] = validate_continuous(curve, raw, spec, calendar)
        if args.demo:
            earlier = as_of(snapshots, "2025-06-18T12:00:00Z", args.mode)
            later = as_of(snapshots, "2025-06-21T12:00:00Z", args.mode)
            summary["restatement_demo"] = {"earlier_close": next(b.close for b in earlier.bars if b.contract_symbol == "ESM25" and str(b.session) == "2025-06-12"),
                                           "later_close": next(b.close for b in later.bars if b.contract_symbol == "ESM25" and str(b.session) == "2025-06-12")}
        if any(f["severity"] == "error" for f in summary["findings"]):
            summary["status"] = "invalid"
        elif summary["status"] == "pass" and any(f["severity"] == "warning" for f in summary["findings"]):
            summary["status"] = "warning"
        code = {"pass": 0, "warning": 1, "invalid": 2, "incomplete": 3}[summary["status"]]
    except (ValueError, OSError) as exc:
        summary = {"schema_version": "futures_pit_preview_v1", "status": "invalid",
                   "failure": getattr(exc, "code", "invalid_input"), "message": str(exc)}
        code = 2
    print(json.dumps(summary, sort_keys=True, allow_nan=False, indent=2))
    print("Futures local preview: " + summary["status"] + "; no inputs/artifacts/database written", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")
    raise SystemExit(main())
