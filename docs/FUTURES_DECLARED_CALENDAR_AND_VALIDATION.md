# Declared Futures Calendar and Local Validation v1

## Finite Calendar

`DeclaredCalendar` is `declared_futures_calendar_v1`, with ID/version, named
timezone, inclusive coverage, optional declared historical availability and
an ordered classification for **every** covered date (maximum 3660).
Outside coverage is unknown, not closed. A missing expected quote is missing
data, not a holiday. Fixtures are synthetic/user-declared, never official CME
holiday schedules. The June 11 closure is deliberately invented.

Open sessions specify UTC start/end, optional ordered interior non-overlapping
breaks and an early-close flag. Daily sessions may cross midnight and end on
their explicit local trading label, within 36 hours; UTC-date grouping is not
used to infer that label. Closed labels have no intervals/breaks/early-close.
Session intervals cannot overlap. Duration subtracts breaks; session count
does not depend on whether DST makes a session 23 or 25 hours long.

Operations:

| Operation | Convention |
| --- | --- |
| `lookup(label)` | Explicit open/closed entry; error outside coverage |
| `between(start,end)`, `count(start,end)` | Both labels inclusive, open sessions only; no uncovered endpoint |
| `previous(label)` / `next(label)` | Strictly before / after; refusal if unavailable in coverage |
| `on_or_before(label)` | Inclusive; closed label resolves to declared prior open session |

`local_to_utc` uses real `ZoneInfo` with round-trip validation. Nonexistent wall
times are rejected. Ambiguous repeated wall times require integer fold 0 or 1;
Boolean/float fold coercion is refused. Named zones never use a hardcoded offset.
The material calendar already stores explicit UTC intervals, so unchanged
calendar hashes do not depend on a silent timezone database update.

Local inspection: Python 3.13.5 (Anaconda-packaged interpreter in the existing
repository `.venv`); `America/Chicago` resolves through installed `tzdata`
2026.2, not an existing TZPATH file. No timezone dependency/runtime installation
or requirements change was needed. Provenance reports actual system TZPATH
or fallback package, source version when available, and `pinned: false`.
Existing CI is Ubuntu/Python 3.11 with declared backend requirements; actual
Phase 67 3.11 timezone execution remains a future exact-commit CI gate, not a
local 3.13 claim. Unavailable named data fails explicitly.

## Explicit Calendar-Aware Rolls

Existing calls without `declared_calendar` still use the legacy observed-overlap
window/observed union-calendar behavior and existing identity. Explicit mode:

- Uses an expiry-anchored lookback of declared expected sessions, with complete
  calendar coverage through the front expiry; refuses truncated lookback.
- Counts missing expected sessions as confirmation breaks. Known closures do
  not break consecutive *sessions*. Missing OI cannot imply crossover.
- Resolves previous/next sessions through the declared calendar, not observed
  quote rows. Requires both contracts on the effective roll label and immediate
  prior seam label; missing quotes fail, never slide execution/seam forward.
- Keeps `fallback_days_before_expiry` in **calendar days**, then chooses the
  declared session on/before that target. No session-unit reinterpretation.
- Retains spec-derived expiry assumptions, calendar identity, decision/end and
  effective session/start, policy and limitations in each `RollEvent`.

This schedule remains **retrospective**, including daily volume/OI scheduling
and back-adjustment. `decision_eligibility` is a bounded audit of required
confirmation fields and declared calendar availability at an explicit decision
cutoff before the effective session starts. It does not implement or certify a
causal scheduling/execution engine, historical instrument knowledge, or the
availability of the new session's closing quote at its opening time.

The corpus intentionally declares June 12 OI at June 13 02:00 UTC, after the
next session starts at June 12 22:00 UTC. That roll cannot receive a PIT badge.
Tests also demonstrate eligible earlier-published full-field declarations and
local receipt differences. Earlier selected input prefixes preserve the same
past decision when future observations/corrections are appended under the same
as-of policy. Back-adjusted *price levels* do not claim a full-history prefix
invariant when future rolls are appended.

## Continuous Quality Findings

The existing `build_continuous_futures` is the sole stitching/adjustment engine.
Diagnostics inspect nonempty bounded outputs without mutation: ordered labels,
duplicates, closed/unknown/missing sessions, active-contract transitions/flags,
required seam/roll quotes, raw/adjusted fields, factors, nonfinite values and
same-contract spikes. Comparison reuses the existing builder under the declared
policy; hand-computable acceptance assertions are independently specified.

For the baseline June 12/13 seam: old close 100, new prior close 110, new roll
close 111. Ratio is 1.1 and Panama gap is 10. Adjusted prior close 110 -> 111
is a new-contract change; raw 100 -> 111 contains an inter-contract spread,
not a tradable 11% return. Correction of old June 12 close to 102 changes that
input vintage and seam factor explicitly. The June 10 missing front bar is a
warning; invented June 11 closure is not missing data. Spike threshold defaults
to absolute 10% same-contract close change and is explicitly configurable in
the library (0,10]; no claims of full microstructure/official validation.
Panama seam diagnostics use point changes, not fractional returns. Valid zero
or negative additive adjusted levels are warnings, not price repairs or engine
inconsistency; they must not be fed into percentage-return interpretations.

## Read-Only CLI

From `C:\quantlab`, using the existing runtime:

```powershell
.\.venv\Scripts\python.exe -B scripts/validate_futures_point_in_time.py --demo
.\.venv\Scripts\python.exe -B scripts/validate_futures_point_in_time.py --provider external
.\.venv\Scripts\python.exe -B scripts/validate_futures_point_in_time.py --csv backend/tests/fixtures/futures_pit/bars.csv --metadata backend/tests/fixtures/futures_pit/metadata.json --calendar backend/tests/fixtures/futures_pit/calendar.json --as-of 2025-06-14T12:00:00Z --mode local_observed
```

`--demo` explicitly selects the tiny invented corpus, adds retained correction
comparison/earlier-versus-later selection and continuous diagnostics. It cannot
be mixed with explicit source paths. Non-demo inputs require explicit CSV,
metadata, calendar and an aware `--as-of`; optional `--correction-csv` and
`--correction-metadata` must be paired. `--continuous` requests retrospective
stitching; selected vintages without required roll quotes fail clearly rather
than obtaining quotes from later/unselected records. No filesystem export exists.

Strict JSON summary goes to stdout; short human status goes to stderr.
Exit 0 = supplied strict checks pass, 1 = valid with diagnostic warnings,
2 = invalid input/disabled provider/required quote refusal,
3 = incomplete (unknown basis/required knowledge/calendar availability,
or no eligible observations). None means attested provenance/PIT certification.
No arguments cannot succeed. Demo normally exits **1**, deliberately preserving
the missing expected bar warning. The invalid subdirectory is separate from the
valid baseline/correction files; it is never recursively scanned.
