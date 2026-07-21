"""
Phase 14 (commit 3) — deterministic, string-returning renderers for evidence packs.

``export_evidence_pack_json`` / ``export_evidence_pack_csv`` /
``export_evidence_pack_markdown`` each take an ``ExperimentEvidencePack`` and return
a **string** — they perform no filesystem access whatsoever (only the CLI, in a later
commit, writes to explicit output paths).  Rendering is a pure mapping-to-string
transform, so there is nothing to read, stat, or resolve.

Every nested value is taken from the pack's own evidence-safe ``to_dict()``.  That
mapping already applies the model-layer host-absolute-path redaction to the nested
Phase 13 findings, so this module never touches a raw structural-finding object and
never re-derives an unsafe value — the model layer remains the single source of path
safety for rendered output.

Output is deterministic and strict-JSON-safe: no ``NaN`` / ``Infinity``, no generated
timestamps, no host / user / machine / store-root information, and every report
carries the Phase 14 scope disclaimers.  Descriptive only: rankings are reported as
observed order, never as a recommendation.

This module imports only the stdlib and ``app.experiment_review.models`` — never the
audit / experiments / reporting / catalog / registry / pipeline packages — and it
mints no hashes.
"""

from __future__ import annotations

import csv
import io
import json

from app.experiment_review.models import ExperimentEvidencePack

__all__ = [
    "EVIDENCE_DISCLAIMERS",
    "export_evidence_pack_json",
    "export_evidence_pack_csv",
    "export_evidence_pack_markdown",
]

# Phase-14-specific scope / safety statements (distinct from Phase 13's structural
# disclaimers and Phase 10's market disclaimers).  Descriptive only — no remediation
# commands, no recommendation, and no claim that Phase 14 produced new evidence.
EVIDENCE_DISCLAIMERS: tuple[str, ...] = (
    "This evidence pack is a read-only aggregation of already-persisted evidence and creates no new evidence.",
    "Evidence completeness describes which evidence was found; it does not prove the underlying data is correct.",
    "Evidence completeness does not prove model correctness or reproducibility.",
    "Structural integrity is not statistical validity and is not a measure of model quality.",
    "Any ranking shown is descriptive ordering only and is not a recommendation.",
    "This pack does not approve deployment or live trading.",
    "Local or synthetic results are not investment advice.",
    "A complete evidence pack does not guarantee any investment or trading performance.",
)

#: Fixed run-summary schema (Appendix O.13) — stable regardless of metric keys.
_CSV_HEADER: tuple[str, ...] = (
    "train_run_hash",
    "load_status",
    "audit_status",
    "completeness",
    "model_type",
    "task_type",
    "train_start",
    "train_end",
    "validation_start",
    "validation_end",
    "catalog_group",
    "catalog_rank",
    "requested_metric",
    "requested_metric_value",
    "metrics_json",
    "baseline_metrics_json",
    "missing_evidence",
)

_MISSING_EVIDENCE_DELIMITER = ";"
_MD_NA = "not recorded"
_MD_NONE_SECTION = "_None._"

_STRUCTURAL_FINDING_COLUMNS: tuple[str, ...] = (
    "finding_id",
    "severity",
    "code",
    "artifact_name",
    "relative_path",
    "expected",
    "actual",
    "message",
)


def _payload(pack: ExperimentEvidencePack) -> dict:
    """The pack's evidence-safe mapping with the Phase 14 disclaimers applied.

    Nested runs / structural findings are used **only** as they appear here."""
    payload = pack.to_dict()
    payload["disclaimers"] = list(EVIDENCE_DISCLAIMERS)
    return payload


# --------------------------------------------------------------------------- #
# JSON
# --------------------------------------------------------------------------- #


def export_evidence_pack_json(pack: ExperimentEvidencePack) -> str:
    """Strict, deterministic JSON (sorted keys, 2-space indent, trailing newline).

    Object key order is normalized by ``sort_keys``; list order
    (``selected_run_hashes`` / ``runs`` / ``findings``) is preserved, so the caller's
    selection order survives.  Phase 13 ``finding_NNNN`` ids and Phase 14
    ``evidence_NNNN`` ids are carried through unchanged and never renumbered.
    ``None`` becomes ``null``; there are no ``NaN`` / ``Infinity`` values, timestamps,
    or host paths."""
    return json.dumps(_payload(pack), allow_nan=False, sort_keys=True, indent=2) + "\n"


# --------------------------------------------------------------------------- #
# CSV
# --------------------------------------------------------------------------- #


def _csv_cell(value) -> str:
    return "" if value is None else str(value)


def _compact_json(value) -> str:
    """Deterministic compact strict JSON for an embedded cell (``None`` -> empty)."""
    if value is None:
        return ""
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))


def _csv_row(run: dict) -> list[str]:
    catalog = run.get("catalog_context") or {}
    return [
        _csv_cell(run["train_run_hash"]),
        _csv_cell(run["load_status"]),
        _csv_cell(run["audit_status"]),
        _csv_cell(run["completeness"]),
        _csv_cell(run["model_type"]),
        _csv_cell(run["task_type"]),
        _csv_cell(run["train_start"]),
        _csv_cell(run["train_end"]),
        _csv_cell(run["validation_start"]),
        _csv_cell(run["validation_end"]),
        _csv_cell(catalog.get("compatibility_group")),
        _csv_cell(catalog.get("rank")),
        _csv_cell(catalog.get("requested_metric")),
        _csv_cell(catalog.get("requested_metric_value")),
        _compact_json(run["metrics"]),
        _compact_json(run["baseline_metrics"]),
        _MISSING_EVIDENCE_DELIMITER.join(run["missing_evidence"]),
    ]


def export_evidence_pack_csv(pack: ExperimentEvidencePack) -> str:
    """Deterministic run-summary CSV: fixed header + one row per selected run.

    The header never varies with the metric keys present — per-run metrics travel in
    the ``metrics_json`` / ``baseline_metrics_json`` cells as compact deterministic
    JSON, so there are no dynamic metric columns.  ``catalog_rank`` /
    ``requested_metric`` / ``requested_metric_value`` come from the run's own catalog
    context (empty when no metric was requested); nothing is calculated here and the
    rank is descriptive only.  ``None`` becomes an empty cell, ``missing_evidence``
    is ``;``-joined, and the stdlib ``csv`` module quotes / escapes commas, quotes,
    and newlines.  Structural and aggregation findings are deliberately **not**
    flattened into this table, and it carries no summary pseudo-row and no
    disclaimers."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(_CSV_HEADER)
    for run in _payload(pack)["runs"]:
        writer.writerow(_csv_row(run))
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# Markdown
# --------------------------------------------------------------------------- #


def _md_cell(value) -> str:
    """Markdown table cell: ``None`` -> 'not recorded'; escape pipes; collapse newlines."""
    if value is None:
        return _MD_NA
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    if not text:
        return _MD_NA
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _md_table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def _md_join(values) -> str:
    return ", ".join(_md_cell(v) for v in values) if values else _MD_NA


def _validation_window(run: dict) -> str:
    start, end = run.get("validation_start"), run.get("validation_end")
    if start is None and end is None:
        return _MD_NA
    return f"{_md_cell(start)} to {_md_cell(end)}"


def _summary_section(payload: dict) -> list[str]:
    summary = payload["evidence_summary"]
    rows = [
        [key, str(summary[key])]
        for key in (
            "completeness",
            "selected_runs_total",
            "runs_complete",
            "runs_with_warnings",
            "runs_incomplete",
            "runs_unavailable",
            "phase14_findings_total",
            "phase13_findings_total",
        )
    ]
    return _md_table(["metric", "value"], rows)


def _selected_runs_section(payload: dict) -> list[str]:
    header = [
        "train_run_hash", "load_status", "audit_status", "completeness",
        "model_type", "task_type", "validation_window", "catalog_group", "rank",
    ]
    rows = []
    for run in payload["runs"]:
        catalog = run.get("catalog_context") or {}
        rows.append(
            [
                _md_cell(run["train_run_hash"]),
                _md_cell(run["load_status"]),
                _md_cell(run["audit_status"]),
                _md_cell(run["completeness"]),
                _md_cell(run["model_type"]),
                _md_cell(run["task_type"]),
                _validation_window(run),
                _md_cell(catalog.get("compatibility_group")),
                _md_cell(catalog.get("rank")),
            ]
        )
    return _md_table(header, rows)


def _structural_section(payload: dict) -> list[str]:
    """Phase 13 findings per selected run, rendered from the safe projection only."""
    lines: list[str] = [
        "Structural findings below are produced by the Phase 13 integrity audit and "
        "keep their original `finding_NNNN` identifiers, codes, and severities.",
        "",
    ]
    for run in payload["runs"]:
        # escaped like any other cell: a newline here would inject a spurious heading
        lines.append(f"### {_md_cell(run['train_run_hash'])}")
        lines.append("")
        findings = run["audit_findings"]
        if not findings:
            lines.append("No structural findings were recorded for this run.")
            lines.append("")
            continue
        rows = [[_md_cell(f.get(column)) for column in _STRUCTURAL_FINDING_COLUMNS] for f in findings]
        lines.extend(_md_table(list(_STRUCTURAL_FINDING_COLUMNS), rows))
        lines.append("")
    return lines


def _comparison_section(payload: dict) -> list[str]:
    comparison = payload["comparison"]
    status = comparison["status"]
    lines = [f"**Status:** {status}", ""]

    if status == "not_applicable":
        lines.append(
            "A comparison covers two or more runs, so it does not apply to a single "
            "selected run."
        )
        lines.append("")
        return lines

    if status == "unavailable":
        lines.append(f"Reason: {_md_cell(comparison['unavailable_reason'])}")
        lines.append("")
        return lines

    rows = comparison["rows"]
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key != "metrics" and key not in columns:
                columns.append(key)
    metric_keys: list[str] = []
    for row in rows:
        for key in (row.get("metrics") or {}):
            if key not in metric_keys:
                metric_keys.append(key)
    metric_keys.sort()

    table_rows = [
        [_md_cell(row.get(column)) for column in columns]
        + [_md_cell((row.get("metrics") or {}).get(key)) for key in metric_keys]
        for row in rows
    ]
    # the only data-derived table header in the module, so it needs cell escaping too
    lines.extend(_md_table([_md_cell(c) for c in columns + metric_keys], table_rows))
    lines.append("")
    if comparison["disclaimers"]:
        lines.append("Inherited comparison disclaimers:")
        lines.append("")
        lines.extend(f"- {d}" for d in comparison["disclaimers"])
        lines.append("")
    return lines


def _catalog_section(payload: dict) -> list[str]:
    lines = [f"**Status:** {payload['catalog_context_status']}", ""]
    header = [
        "train_run_hash", "status", "compatibility_group", "group_size",
        "peers", "requested_metric", "requested_metric_value", "rank",
    ]
    rows = []
    for run in payload["runs"]:
        catalog = run.get("catalog_context") or {}
        rows.append(
            [
                _md_cell(run["train_run_hash"]),
                _md_cell(catalog.get("status")),
                _md_cell(catalog.get("compatibility_group")),
                _md_cell(catalog.get("group_size")),
                _md_join(catalog.get("peer_train_run_hashes") or ()),
                _md_cell(catalog.get("requested_metric")),
                _md_cell(catalog.get("requested_metric_value")),
                _md_cell(catalog.get("rank")),
            ]
        )
    lines.extend(_md_table(header, rows))
    lines.append("")
    lines.append("Rank is descriptive ordering within a compatibility group only.")
    lines.append("")
    return lines


def _missing_evidence_section(payload: dict) -> list[str]:
    rows = [
        [_md_cell(run["train_run_hash"]), _md_cell(run["completeness"]), _md_join(run["missing_evidence"])]
        for run in payload["runs"]
    ]
    lines = _md_table(["train_run_hash", "completeness", "missing_or_unavailable"], rows)
    lines.append("")
    return lines


def _registry_section(payload: dict) -> list[str]:
    return [
        f"**Registry context:** {payload['registry_context_status']}",
        "",
        f"**Dataset-lineage context:** {payload['dataset_lineage_context_status']}",
        "",
        "This context is neutral and was not queried: no registry or dataset-lineage "
        "source was consulted while building this pack. It is therefore not missing "
        "evidence, and no database was opened.",
        "",
    ]


def _phase14_findings_section(payload: dict) -> list[str]:
    lines = [
        "Aggregation findings below are produced by Phase 14 and use the "
        "`evidence_NNNN` namespace, kept separate from the Phase 13 `finding_NNNN` "
        "identifiers shown under Structural integrity.",
        "",
    ]
    findings = payload["findings"]
    if not findings:
        lines.append(_MD_NONE_SECTION)
        lines.append("")
        return lines
    rows = [
        [
            _md_cell(f["finding_id"]),
            _md_cell(f["severity"]),
            _md_cell(f["code"]),
            _md_cell(f["train_run_hash"]),
            _md_cell(f["message"]),
            _md_cell(None if f["context"] is None else _compact_json(f["context"])),
        ]
        for f in findings
    ]
    lines.extend(_md_table(
        ["finding_id", "severity", "code", "train_run_hash", "message", "context"], rows
    ))
    lines.append("")
    return lines


def export_evidence_pack_markdown(pack: ExperimentEvidencePack) -> str:
    """Deterministic, human-readable Markdown report (all sections always present).

    Sections appear in a fixed order: title, evidence completeness result, evidence
    summary, selected runs, structural integrity, comparison, catalog context,
    missing or unavailable evidence, registry and dataset-lineage context, Phase 14
    aggregation findings, and Scope & Safety.  Structural findings are rendered from
    the pack's evidence-safe mapping, so their identifiers are preserved and no raw
    structural-finding object is read.  There is no generated timestamp and no host
    or store-root information."""
    payload = _payload(pack)
    lines: list[str] = ["# Local Experiment Evidence Pack", ""]

    lines.append(f"**Evidence completeness:** {payload['evidence_summary']['completeness']}")
    lines.append("")

    lines.append("## Evidence summary")
    lines.append("")
    lines.extend(_summary_section(payload))
    lines.append("")

    lines.append("## Selected runs")
    lines.append("")
    lines.extend(_selected_runs_section(payload))
    lines.append("")

    lines.append("## Structural integrity")
    lines.append("")
    lines.extend(_structural_section(payload))

    lines.append("## Comparison")
    lines.append("")
    lines.extend(_comparison_section(payload))

    lines.append("## Catalog context")
    lines.append("")
    lines.extend(_catalog_section(payload))

    lines.append("## Missing or unavailable evidence")
    lines.append("")
    lines.extend(_missing_evidence_section(payload))

    lines.append("## Registry and dataset-lineage context")
    lines.append("")
    lines.extend(_registry_section(payload))

    lines.append("## Phase 14 aggregation findings")
    lines.append("")
    lines.extend(_phase14_findings_section(payload))

    lines.append("## Scope & Safety")
    lines.append("")
    lines.extend(f"- {disclaimer}" for disclaimer in EVIDENCE_DISCLAIMERS)

    return "\n".join(lines) + "\n"
