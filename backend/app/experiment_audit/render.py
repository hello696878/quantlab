"""
Phase 13 (commit 3) — deterministic, string-returning renderers for audit results.

``export_audit_json`` / ``export_audit_csv`` / ``export_audit_markdown`` each take an
``ExperimentStoreAuditResult`` and return a **string** — they perform no filesystem
writes (only the CLI, in a later commit, writes to explicit output paths).  Output
is deterministic and strict-JSON-safe: no ``NaN`` / ``Infinity``, no timestamps, no
audit-root / host paths, and every report carries the read-only, structural-only
scope disclaimers.

This module imports only the stdlib and ``app.experiment_audit.models`` — never the
experiments / reporting / catalog / pipeline packages, and it mints no hashes.
"""

from __future__ import annotations

import csv
import io
import json

from app.experiment_audit.models import AuditSeverity, ExperimentStoreAuditResult

__all__ = [
    "AUDIT_DISCLAIMERS",
    "export_audit_json",
    "export_audit_csv",
    "export_audit_markdown",
]

# Phase-13-specific scope / safety statements (distinct from Phase 10's market
# disclaimers).  Descriptive only — no remediation commands, no trading advice.
AUDIT_DISCLAIMERS: tuple[str, ...] = (
    "This audit is read-only and does not modify, repair, delete, or quarantine the ExperimentStore.",
    "It checks structural integrity only — not data correctness, model correctness, or reproducibility.",
    "A passing audit does not prove the experiments are correct, valid, or reproducible.",
    "A passing audit does not guarantee any investment, live-trading, or performance outcome.",
    "Local or synthetic results are not investment advice.",
)

_CSV_HEADER: tuple[str, ...] = (
    "finding_id",
    "severity",
    "code",
    "run_directory",
    "train_run_hash",
    "artifact_name",
    "relative_path",
    "expected",
    "actual",
    "message",
)

_MD_NA = "n/a"


def export_audit_json(result: ExperimentStoreAuditResult) -> str:
    """Strict, deterministic JSON (sorted keys, 2-space indent, trailing newline).

    Object key order is normalized by ``sort_keys``; list order (``findings`` /
    ``run_audits``) is preserved.  ``None`` becomes ``null``; there are no
    ``NaN`` / ``Infinity`` values, timestamps, or host paths."""
    payload = {"disclaimers": list(AUDIT_DISCLAIMERS), **result.to_dict()}
    return json.dumps(payload, allow_nan=False, sort_keys=True, indent=2) + "\n"


def _csv_cell(value) -> str:
    return "" if value is None else str(value)


def export_audit_csv(result: ExperimentStoreAuditResult) -> str:
    """Deterministic CSV findings table: fixed header + one row per finding.

    ``None`` becomes an empty cell; the stdlib ``csv`` module quotes / escapes
    commas, quotes, and newlines.  Zero findings yields the header row only (no
    summary pseudo-row)."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(_CSV_HEADER)
    for finding in result.findings:
        data = finding.to_dict()
        writer.writerow([_csv_cell(data[column]) for column in _CSV_HEADER])
    return buf.getvalue()


def _md_cell(value) -> str:
    """Markdown table cell: None -> 'n/a'; escape pipes; collapse newlines."""
    if value is None:
        return _MD_NA
    text = str(value)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _md_table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def export_audit_markdown(result: ExperimentStoreAuditResult) -> str:
    """Deterministic, human-readable Markdown report (all sections always present).

    Renders the overall status, a summary table, findings-by-severity and
    findings-by-code tables, an audited-runs table, a findings table, and a
    Scope & Safety section listing every :data:`AUDIT_DISCLAIMERS` entry."""
    lines: list[str] = ["# ExperimentStore Integrity Audit", ""]
    lines.append(f"**Overall status:** {result.overall_status.value}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.extend(
        _md_table(
            ["metric", "value"],
            [
                ["runs_discovered", str(result.runs_discovered)],
                ["runs_valid", str(result.runs_valid)],
                ["runs_with_warnings", str(result.runs_with_warnings)],
                ["runs_invalid", str(result.runs_invalid)],
                ["non_run_entries", str(result.non_run_entries)],
                ["findings_total", str(result.findings_total)],
            ],
        )
    )
    lines.append("")

    lines.append("## Findings by severity")
    lines.append("")
    severity_rows = [
        [severity.value, str(result.findings_by_severity[severity.value])]
        for severity in AuditSeverity
        if severity.value in result.findings_by_severity
    ]
    lines.extend(_md_table(["severity", "count"], severity_rows))
    lines.append("")

    lines.append("## Findings by code")
    lines.append("")
    code_rows = [[code, str(result.findings_by_code[code])] for code in sorted(result.findings_by_code)]
    lines.extend(_md_table(["code", "count"], code_rows))
    lines.append("")

    lines.append("## Audited runs")
    lines.append("")
    run_rows = [
        [_md_cell(ra.run_directory), _md_cell(ra.train_run_hash), _md_cell(ra.status.value)]
        for ra in result.run_audits
    ]
    lines.extend(_md_table(["run_directory", "train_run_hash", "status"], run_rows))
    lines.append("")

    lines.append("## Findings")
    lines.append("")
    finding_header = [
        "finding_id", "severity", "code", "run_directory",
        "artifact_name", "relative_path", "expected", "actual", "message",
    ]
    finding_rows = [
        [
            _md_cell(f.finding_id),
            _md_cell(f.severity.value),
            _md_cell(f.code.value),
            _md_cell(f.run_directory),
            _md_cell(f.artifact_name),
            _md_cell(f.relative_path),
            _md_cell(f.expected),
            _md_cell(f.actual),
            _md_cell(f.message),
        ]
        for f in result.findings
    ]
    lines.extend(_md_table(finding_header, finding_rows))
    lines.append("")

    lines.append("## Scope & Safety")
    lines.append("")
    lines.extend(f"- {disclaimer}" for disclaimer in AUDIT_DISCLAIMERS)

    return "\n".join(lines) + "\n"
