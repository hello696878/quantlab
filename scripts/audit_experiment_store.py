"""
Audit a local ExperimentStore for structural integrity (Phase 13 — commit 4).

Thin argparse wrapper around ``app.experiment_audit``: it discovers and classifies
every store entry, validates metadata / ``artifact_paths`` tolerantly, and reports
missing / malformed / orphaned / unsafe content as deterministic findings.  It is
strictly **read-only** — it never modifies, repairs, deletes, quarantines, or
migrates the store, runs nothing, retrains nothing, and mints no hashes.  Reports
are written **only** to the explicit ``--output-*`` paths.

Usage (from the repo root)::

    backend\\venv\\Scripts\\python.exe scripts\\audit_experiment_store.py \\
        --artifacts-dir artifacts\\experiments --level standard \\
        [--run-hash <hash>] [--severity warning] [--fail-on error] \\
        [--output-json reports\\audit.json] [--output-markdown reports\\audit.md]

The ``RESULT:`` line reflects the canonical structural status (OK / WARNING / FAIL).
Exit codes: 0 = ran, nothing met ``--fail-on``; 1 = ran, a finding met ``--fail-on``;
2 = argparse usage error; 3 = the audit could not run (missing / non-directory root,
unsafe / missing ``--run-hash``, unwritable output path, runtime failure).
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

# Make `app.*` importable when run directly from the repo root (mirrors the other
# local-futures scripts and the pytest pythonpath="." setting).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from pydantic import ValidationError  # noqa: E402

from app.experiment_audit import (  # noqa: E402
    AuditError,
    AuditRunStatus,
    AuditSeverity,
    ExperimentRunAudit,
    ExperimentStoreAuditResult,
    audit_experiment_run,
    audit_experiment_store,
    export_audit_csv,
    export_audit_json,
    export_audit_markdown,
    overall_status_for,
    severity_rank,
)
from app.experiments import ExperimentError, ExperimentStore  # noqa: E402

# Piped/redirected stdout on Windows uses the ANSI code page with strict errors;
# degrade non-ASCII to an escape sequence rather than crash mid-report.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="backslashreplace")

_BANNER = (
    "=== EXPERIMENTSTORE INTEGRITY AUDIT — read-only; structural only; "
    "not investment advice ==="
)

_RESULT_WORD = {"ok": "OK", "warning": "WARNING", "failed": "FAIL"}

# Info-level non-run *classification* findings hidden from display/export unless
# --include-non-run-entries.  Warning/error findings (e.g. MISSING_METADATA,
# SYMLINK_ENTRY) are never hidden — only these info codes are.
_NON_RUN_INFO_CODES = frozenset(
    {"EMPTY_STORE", "NON_RUN_DIRECTORY", "ROOT_LEVEL_FILE", "EMPTY_DIRECTORY", "IGNORED_OS_FILE"}
)

# Expected failures that map to a clean nonzero "audit could not run" (exit 3).
_FAIL_ERRORS = (AuditError, ExperimentError, ValidationError, ValueError, OSError)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only structural integrity audit of a local ExperimentStore "
            "(local files only; sequential; no network; no repair)."
        )
    )
    parser.add_argument("--artifacts-dir", required=True, help="ExperimentStore base dir (read)")
    parser.add_argument(
        "--level", choices=("metadata-only", "standard", "deep"), default="standard"
    )
    parser.add_argument("--run-hash", default=None, help="audit a single run directory by name")
    parser.add_argument(
        "--severity",
        choices=("info", "warning", "error", "critical"),
        default="info",
        help="minimum severity of findings to display / export (default: info)",
    )
    parser.add_argument(
        "--fail-on",
        choices=("warning", "error", "critical"),
        default="error",
        help="exit nonzero if any finding reaches this severity (default: error)",
    )
    parser.add_argument(
        "--include-non-run-entries",
        action="store_true",
        help="also show/export info-level non-run classification findings "
        "(EMPTY_STORE / NON_RUN_DIRECTORY / ROOT_LEVEL_FILE / EMPTY_DIRECTORY / IGNORED_OS_FILE); "
        "warning/error findings are always shown",
    )
    parser.add_argument("--output-json", default=None, help="write a strict JSON report here")
    parser.add_argument("--output-csv", default=None, help="write a CSV findings report here")
    parser.add_argument("--output-markdown", default=None, help="write a Markdown report here")
    parser.add_argument(
        "--no-parquet",
        action="store_true",
        help="pass the CSV storage preference to ExperimentStore (audit is read-only; "
        "discovery follows persisted artifact paths / on-disk files regardless)",
    )
    return parser


def _single_run_to_store_result(run_audit: ExperimentRunAudit) -> ExperimentStoreAuditResult:
    """CLI-only adapter: wrap one ``ExperimentRunAudit`` into a consistent
    store-level result for shared rendering.  Adds no findings and changes no
    audit-engine semantics."""
    findings = run_audit.findings
    return ExperimentStoreAuditResult(
        runs_discovered=1,
        runs_valid=1 if run_audit.status == AuditRunStatus.VALID else 0,
        runs_with_warnings=1 if run_audit.status == AuditRunStatus.WARNING else 0,
        runs_invalid=1 if run_audit.status == AuditRunStatus.INVALID else 0,
        non_run_entries=0,
        findings_total=len(findings),
        findings_by_severity=dict(Counter(f.severity.value for f in findings)),
        findings_by_code=dict(Counter(f.code.value for f in findings)),
        audited_run_hashes=(run_audit.train_run_hash,) if run_audit.train_run_hash else (),
        run_audits=(run_audit,),
        findings=findings,
        overall_status=overall_status_for(findings),
    )


def _passes(finding, min_severity: AuditSeverity, include_non_run: bool) -> bool:
    if severity_rank(finding.severity) < severity_rank(min_severity):
        return False
    if not include_non_run and finding.code.value in _NON_RUN_INFO_CODES:
        return False
    return True


def _write(path_str: str, text: str) -> None:
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run(args) -> int:
    store = ExperimentStore(args.artifacts_dir, prefer_parquet=not args.no_parquet)
    if args.run_hash:
        result = _single_run_to_store_result(
            audit_experiment_run(store, args.run_hash, level=args.level)
        )
    else:
        result = audit_experiment_store(store, level=args.level)

    min_severity = AuditSeverity(args.severity)
    displayed = [f for f in result.findings if _passes(f, min_severity, args.include_non_run_entries)]

    # canonical summary (never filtered) + the displayed (filtered) count
    print(
        f"overall_status={result.overall_status.value} "
        f"runs_discovered={result.runs_discovered} "
        f"runs_valid={result.runs_valid} "
        f"runs_with_warnings={result.runs_with_warnings} "
        f"runs_invalid={result.runs_invalid} "
        f"non_run_entries={result.non_run_entries} "
        f"findings_total={result.findings_total} "
        f"displayed_findings_total={len(displayed)}"
    )
    for finding in displayed:
        print(
            f"[{finding.finding_id}] {finding.severity.value} {finding.code.value} "
            f"run={finding.run_directory} artifact={finding.artifact_name or ''} "
            f"path={finding.relative_path or ''}"
        )

    # explicit output paths only (render first, then write — no partial file on a render error)
    if args.output_json:
        _write(args.output_json, export_audit_json(result, findings=displayed))
        print(f"[JSON] path={args.output_json}")
    if args.output_csv:
        _write(args.output_csv, export_audit_csv(result, findings=displayed))
        print(f"[CSV] path={args.output_csv}")
    if args.output_markdown:
        _write(args.output_markdown, export_audit_markdown(result, findings=displayed))
        print(f"[MARKDOWN] path={args.output_markdown}")

    print(f"RESULT: {_RESULT_WORD[result.overall_status.value]}")

    # exit code from --fail-on, evaluated on the FULL (unfiltered) result
    fail_on = AuditSeverity(args.fail_on)
    triggered = any(severity_rank(f.severity) >= severity_rank(fail_on) for f in result.findings)
    return 1 if triggered else 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    print(_BANNER)
    try:
        return _run(args)
    except _FAIL_ERRORS as exc:
        print(f"RESULT: FAIL ({type(exc).__name__}: {exc})")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
