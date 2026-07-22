"""
Build a local experiment evidence pack (Phase 14 — commit 4).

Thin argparse wrapper around ``app.experiment_review``: it aggregates the evidence
already persisted for the selected ``train_run_hash`` values into one deterministic
review bundle and reports an explicit evidence-completeness result.  It is strictly
**read-only** with respect to the ExperimentStore — it never modifies, mends,
removes, isolates, or upgrades the store, runs nothing, retrains nothing, opens no
database, and mints no hashes.  Reports are written **only** to the explicit
``--output-*`` paths, which may never live inside the audited store.

Usage (from the repo root)::

    backend\\venv\\Scripts\\python.exe scripts\\build_experiment_evidence_pack.py \\
        --artifacts-dir artifacts\\experiments \\
        --run-hash <hash> [--run-hash <hash>] [--run-hashes-file selected.txt] \\
        [--audit-level standard] [--metric sharpe] [--maximize] \\
        [--severity warning] [--fail-on incomplete] \\
        [--output-json out\\pack.json] [--output-markdown out\\pack.md]

The ``RESULT:`` line reflects the canonical evidence completeness
(COMPLETE / WARNING / INCOMPLETE / UNAVAILABLE) and nothing else.
Exit codes: 0 = pack built, completeness does not meet ``--fail-on``; 1 = pack built,
completeness meets ``--fail-on``; 2 = argparse usage error; 3 = the pack could not be
built (missing / non-directory store root, unreadable ``--run-hashes-file``, runtime
input failure, or an explicit output path / write failure).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `app.*` importable when run directly from the repo root (mirrors the other
# local-futures scripts and the pytest pythonpath="." setting).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from pydantic import ValidationError  # noqa: E402

from app.experiment_review import (  # noqa: E402
    EvidenceError,
    collect_experiment_evidence_pack,
    export_evidence_pack_csv,
    export_evidence_pack_json,
    export_evidence_pack_markdown,
)
from app.experiments import ExperimentError, ExperimentStore  # noqa: E402

# Piped/redirected stdout on Windows uses the ANSI code page with strict errors;
# degrade non-ASCII to an escape sequence rather than crash mid-report.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="backslashreplace")

_BANNER = (
    "=== LOCAL EXPERIMENT EVIDENCE PACK - read-only aggregation of existing "
    "evidence; not investment advice ==="
)

_RESULT_WORD = {
    "complete": "COMPLETE",
    "warning": "WARNING",
    "incomplete": "INCOMPLETE",
    "unavailable": "UNAVAILABLE",
}

#: Completeness ordering used by --fail-on (better -> worse).
_COMPLETENESS_ORDER = ("complete", "warning", "incomplete", "unavailable")

#: Finding severity ordering used by --severity (console display only).
_SEVERITY_ORDER = ("info", "warning", "error", "critical")

# Expected failures that map to a clean "could not build the pack" (exit 3).
_FAIL_ERRORS = (EvidenceError, ExperimentError, ValidationError, ValueError, OSError)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a local, read-only evidence pack aggregating the evidence already "
            "persisted for the selected experiment runs (local files only; no network; "
            "no database; nothing is executed or retrained). Evidence completeness "
            "describes which evidence was found - it is not model correctness, not "
            "reproducibility, and not investment advice."
        )
    )
    parser.add_argument("--artifacts-dir", required=True, help="ExperimentStore base dir (read)")
    parser.add_argument(
        "--run-hash",
        action="append",
        default=None,
        dest="run_hash",
        help="select a run by train_run_hash (repeatable; input order preserved)",
    )
    parser.add_argument(
        "--run-hashes-file",
        default=None,
        help="UTF-8 text file of selected hashes, one per line; blank lines and "
        "'#' comment lines are ignored",
    )
    parser.add_argument(
        "--audit-level",
        choices=("metadata-only", "standard", "deep"),
        default="standard",
        help="structural audit depth applied to each selected run (default: standard)",
    )

    catalog = parser.add_mutually_exclusive_group()
    catalog.add_argument(
        "--include-catalog-context",
        dest="include_catalog_context",
        action="store_true",
        help="collect optional catalog compatibility / ranking context (default)",
    )
    catalog.add_argument(
        "--no-catalog-context",
        dest="include_catalog_context",
        action="store_false",
        help="skip the optional catalog context pass",
    )
    parser.set_defaults(include_catalog_context=True)

    parser.add_argument(
        "--metric",
        default=None,
        help="rank each run descriptively within its compatibility group by this "
        "persisted metric; omitting it means no ranking is reported",
    )
    direction = parser.add_mutually_exclusive_group()
    direction.add_argument(
        "--maximize",
        dest="maximize",
        action="store_true",
        help="treat a higher --metric value as rank 1 (default; no effect without --metric)",
    )
    direction.add_argument(
        "--minimize",
        dest="maximize",
        action="store_false",
        help="treat a lower --metric value as rank 1 (no effect without --metric)",
    )
    parser.set_defaults(maximize=True)

    parser.add_argument("--output-json", default=None, help="write a strict JSON pack here")
    parser.add_argument("--output-csv", default=None, help="write a run-summary CSV here")
    parser.add_argument("--output-markdown", default=None, help="write a Markdown report here")
    parser.add_argument(
        "--fail-on",
        choices=("warning", "incomplete"),
        default="incomplete",
        help="exit nonzero if the canonical evidence completeness reaches this level "
        "(default: incomplete)",
    )
    parser.add_argument(
        "--severity",
        choices=_SEVERITY_ORDER,
        default=None,
        help="minimum severity of the detailed console finding lines. Console display "
        "only: it does not change the evidence pack, the JSON / CSV / Markdown "
        "exports, the summary counts, the RESULT line, or the exit code",
    )
    return parser


# --------------------------------------------------------------------------- #
# selection
# --------------------------------------------------------------------------- #


def _read_hashes_file(path_str: str) -> list[str]:
    """Selected hashes from a UTF-8 text file, in file order.

    Blank lines and '#' comment lines are ignored; surrounding whitespace is
    stripped.  Raises ``ValueError`` with a generic, path-free message so no host
    path can reach the console."""
    path = Path(path_str)
    try:
        if path.is_dir():
            raise ValueError("run-hashes file is not a regular file")
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ValueError("run-hashes file could not be read") from None
    except UnicodeDecodeError:
        raise ValueError("run-hashes file is not valid UTF-8 text") from None
    except OSError:
        raise ValueError("run-hashes file could not be read") from None

    entries = []
    for line in text.splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        entries.append(entry)
    return entries


def _selected_hashes(args) -> list[str]:
    """CLI hashes (command-line order) then file hashes (file order), deduplicated
    with the first occurrence preserved.  Never sorted."""
    combined = list(args.run_hash or [])
    if args.run_hashes_file:
        combined.extend(_read_hashes_file(args.run_hashes_file))

    selected: list[str] = []
    for entry in combined:
        if not entry.strip():
            raise _UsageError("selected run hashes must not be blank")
        if entry not in selected:
            selected.append(entry)
    return selected


class _UsageError(Exception):
    """An argument-value problem that argparse should report as a usage error."""


# --------------------------------------------------------------------------- #
# explicit output paths
# --------------------------------------------------------------------------- #


def _resolved(path: Path) -> Path:
    """Resolve for containment comparison only; the result is never printed."""
    try:
        return path.resolve()
    except OSError:
        # containment cannot be established -> fail closed
        raise ValueError("output path could not be validated") from None


def _validate_outputs(args, store_root: Path) -> list[tuple[str, Path]]:
    """Validate every explicit output path *before* anything is rendered or written.

    Rejects an output that is the store root, an existing directory, or inside the
    audited store (following symlinks, so a link into the store is caught), and
    rejects two outputs that resolve to the same destination.  Returns the requested
    ``(format_name, resolved_path)`` pairs in a deterministic order — the *resolved*
    path is what gets written, so the write target is exactly what was validated (a
    lexical parent containing ``..`` could otherwise mkdir inside the store)."""
    requested = [
        (name, value)
        for name, value in (
            ("JSON", args.output_json),
            ("CSV", args.output_csv),
            ("MARKDOWN", args.output_markdown),
        )
        if value
    ]
    resolved_store = _resolved(store_root)
    seen: dict[Path, str] = {}
    validated: list[tuple[str, Path]] = []
    for name, value in requested:
        path = Path(value)
        if path.is_dir():
            raise ValueError(f"{name} output path is an existing directory")
        resolved = _resolved(path)
        if resolved == resolved_store:
            raise ValueError(f"{name} output path is the ExperimentStore root")
        if resolved_store in resolved.parents:
            raise ValueError(f"{name} output path is inside the audited ExperimentStore")
        if resolved in seen:
            raise ValueError(f"{name} output path duplicates the {seen[resolved]} output path")
        seen[resolved] = name
        validated.append((name, resolved))
    return validated


def _write_output(path: Path, text: str) -> None:
    """The CLI's only write path: create the explicit output's parent, then write.

    ``path`` is the already-validated resolved path, so the directory created here is
    guaranteed to be the one containment was checked against."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------- #
# console rendering
# --------------------------------------------------------------------------- #


def _console_text(value) -> str:
    """One-line console value: newlines / tabs collapsed, never a raw path field."""
    if value is None:
        return ""
    return " ".join(str(value).replace("\t", " ").split())


def _passes(severity: str, threshold: str | None) -> bool:
    if threshold is None:
        return True
    try:
        return _SEVERITY_ORDER.index(severity) >= _SEVERITY_ORDER.index(threshold)
    except ValueError:  # an unknown severity is never hidden
        return True


def _print_findings(payload: dict, threshold: str | None) -> tuple[int, int]:
    """Detailed finding lines from the evidence-safe pack mapping only.

    Phase 14 findings first (``evidence_NNNN`` order), then Phase 13 findings grouped
    by run in pack order, each preserving its original serialized order and id.  The
    raw ``actual`` / ``expected`` values are deliberately not printed."""
    phase14 = 0
    for finding in payload["findings"]:
        if not _passes(finding["severity"], threshold):
            continue
        phase14 += 1
        print(
            f"EVIDENCE_FINDING id={finding['finding_id']} "
            f"severity={finding['severity']} code={finding['code']} "
            f"run={_console_text(finding['train_run_hash'])} "
            f"message={_console_text(finding['message'])}"
        )

    phase13 = 0
    for run in payload["runs"]:
        for finding in run["audit_findings"]:
            if not _passes(finding["severity"], threshold):
                continue
            phase13 += 1
            print(
                f"AUDIT_FINDING run={_console_text(run['train_run_hash'])} "
                f"id={finding['finding_id']} severity={finding['severity']} "
                f"code={finding['code']} "
                f"artifact={_console_text(finding.get('artifact_name'))} "
                f"message={_console_text(finding['message'])}"
            )
    return phase14, phase13


# --------------------------------------------------------------------------- #
# main flow
# --------------------------------------------------------------------------- #


def _run(args) -> int:
    root = Path(args.artifacts_dir)
    if not root.exists():
        raise ValueError("--artifacts-dir does not exist")
    if not root.is_dir():
        raise ValueError("--artifacts-dir is not a directory")

    selected = _selected_hashes(args)
    if not selected:
        raise _UsageError("at least one selected run hash is required")

    # validate every explicit output before collecting or rendering anything
    requested_outputs = _validate_outputs(args, root)

    store = ExperimentStore(root)
    pack = collect_experiment_evidence_pack(
        store,
        selected,
        metric=args.metric,
        maximize=args.maximize,
        include_catalog_context=args.include_catalog_context,
        audit_level=args.audit_level,
    )

    summary = pack.evidence_summary
    completeness = summary.completeness.value
    print(f"RESULT: {_RESULT_WORD[completeness]}")
    print(
        f"SUMMARY selected_runs_total={summary.selected_runs_total} "
        f"runs_complete={summary.runs_complete} "
        f"runs_with_warnings={summary.runs_with_warnings} "
        f"runs_incomplete={summary.runs_incomplete} "
        f"runs_unavailable={summary.runs_unavailable} "
        f"phase14_findings_total={summary.phase14_findings_total} "
        f"phase13_findings_total={summary.phase13_findings_total}"
    )

    payload = pack.to_dict()  # evidence-safe projection; the only finding source
    phase14, phase13 = _print_findings(payload, args.severity)
    print(
        f"DISPLAYED phase14_findings={phase14} phase13_findings={phase13} "
        f"severity_threshold={args.severity or 'none'}"
    )

    # render every requested format in memory first, then write
    if requested_outputs:
        renderers = {
            "JSON": export_evidence_pack_json,
            "CSV": export_evidence_pack_csv,
            "MARKDOWN": export_evidence_pack_markdown,
        }
        rendered = [(name, renderers[name](pack), path) for name, path in requested_outputs]
        for name, text, path in rendered:
            try:
                _write_output(path, text)
            except OSError:
                raise ValueError(f"{name} output could not be written") from None
            print(f"WROTE: {name}")

    # exit code from --fail-on, evaluated on the canonical completeness only
    threshold = _COMPLETENESS_ORDER.index(args.fail_on)
    return 1 if _COMPLETENESS_ORDER.index(completeness) >= threshold else 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    print(_BANNER)
    try:
        return _run(args)
    except _UsageError as exc:
        parser.error(str(exc))  # argparse exits 2
    except _FAIL_ERRORS as exc:
        message = str(exc) if isinstance(exc, ValueError) and not isinstance(exc, EvidenceError) else ""
        print(f"ERROR: {message or 'the evidence pack could not be built'}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
