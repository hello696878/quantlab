# QuantLab — Regime Diagnostics Runbook (Phase 54.0)

How to drive the Market Regime Robustness & Conditional Performance Lab.
Companions: [`REGIME_DIAGNOSTICS_LAB.md`](REGIME_DIAGNOSTICS_LAB.md) ·
[`MARKET_REGIME_DEFINITION_POLICY.md`](MARKET_REGIME_DEFINITION_POLICY.md) ·
[`REGIME_NO_LOOKAHEAD_POLICY.md`](REGIME_NO_LOOKAHEAD_POLICY.md) ·
[`CONDITIONAL_PERFORMANCE_POLICY.md`](CONDITIONAL_PERFORMANCE_POLICY.md).

## 1. Start the app

```powershell
cd C:\quantlab\backend; venv\Scripts\uvicorn app.main:app --reload --port 8000
cd C:\quantlab\frontend; npm run dev   # http://localhost:3000
```

Open **Regime Diagnostics** in the sidebar (Product Workflow, after
Overfitting Diagnostics) or via the command palette (Ctrl+K → "Regime
Diagnostics").

## 2. Load the deterministic demo

Click **Load demo runs** (or `POST /regime-diagnostics/demo-seed`).  Five
runs appear; loading again reports "nothing duplicated".  The seed cascades
every other registry's idempotent demo loader — real user records are never
modified.

## 3. Create a run (API)

`POST /regime-diagnostics/runs` with name, `frequency`, 24–2000
`timestamps`, 1–16 `candidates` (`candidate_id`, aligned `outcomes`,
`outcome_kind`), `market_features` (named aligned series), optional
`sample_ids`, and 1–6 `definitions` (see the definition policy for every
dimension/mode).  Optional: `transition_window` (2–20), links
(`dataset_version_id`, `validation_run_id`, `overfitting_run_id`,
`feature_diagnostics_run_id`, `meta_label_run_id`).  Bad definitions
(negative/zero lag, centered windows, unknown features, threshold order,
bad quantiles) 422 at creation; `training_quantile` requires the validation
link and `sample_ids` eagerly.  Then `POST /runs/{id}/execute` (optionally
`{"create_experiment": true}`).

## 4. Inspect integrity and the lag policy

Detail → **Regime definitions**: each row shows dimension, source feature,
lookback, lag, threshold mode, fitted thresholds, and its integrity pill.
The no-look-ahead note under the table restates the contract; full-sample
definitions carry the descriptive warning, and a centered categorical
definition shows the honest `invalid` state with its labels unused.

## 5. Inspect coverage and conditional metrics

**Coverage** lists observations and shares per regime plus unassigned
periods.  **Conditional performance** shows the candidate × regime table
for a selected definition — observation counts stay prominent, rare
regimes carry `low sample` pills with statistics withheld.

## 6. Inspect robustness, ranks, concentration

**Robustness across regimes** classifies measured consistency per
candidate; **Rank stability** shows per-regime candidate ranks (rank 1 =
lowest mean), pairwise Spearman and top-k overlap — the rank-reversal demo
flips bull-rider and bear-hedge between upward and downward; 
**Concentration** shows HHI, effective regime count, entropy, and
absolute/signed contribution shares (signed shares honestly unavailable
under mixed signs).

## 7. Inspect the timeline and transitions

**Regime timeline** draws each definition's effective labels over time
(legend + interval-table alternative).  **Regime transitions** lists each
boundary with per-candidate before/after means and their measured
difference under the configured window — small samples and overlapping
windows are flagged.

## 8. Compare runs

Select two runs' checkboxes → **Compare selected**.  Comparability warnings
fire when universes, datasets, windows, definitions, threshold modes, or
integrity states differ; identity fields and robustness classifications are
listed side by side.  No better run is declared.

## 9. Mark a baseline

Detail → **Mark as scope baseline** (completed + zero invalid definitions +
verified-or-declared integrity required; one baseline per
dataset/universe/definitions/window scope, transactionally replaced).  The
invalid-definition demo run and the full-sample run are rejected with 409s.

## 10. Export

**Export JSON** downloads the filtered runs with definitions, assignments,
thresholds, conditional results, diagnostics and fingerprints — no paths,
credentials, or model binaries.

## 11. Troubleshooting

* **"every regime definition is invalid"** — see the definition warnings;
  typically a centered declaration or unfittable thresholds.
* **"not members of the linked validation run"** — `sample_ids` must
  exactly match the validation run's recorded memberships.
* **"requires a completed, leakage-clean validation run"** — pick a clean
  run (e.g. the purged+embargo demo) for training-only thresholds.
* **Labels all unavailable early on** — the lookback+lag (and expanding
  min_history) consume the first periods by design.
* **Backend offline banner** — start uvicorn on port 8000.

## 12. Safe demo/test reset

Demo records carry unique `demo_key`s (`demo:rd:*`) plus the cascaded demo
keys of every other registry; they can be deleted from a dev database by
key without touching real records.  The Playwright suite only writes these
idempotent seeds (plus one deliberately-rejected baseline attempt that
writes nothing).  Never delete from a database you care about without a
backup.

## Ground rules (unchanged by this doc)

Deterministic educational sample data; no live data; regimes are
descriptive states, never predictions; conditional statistics are never
causality or profitability evidence; no strategy switching or selection;
not investment advice; not production trading, risk, or compliance
infrastructure.
