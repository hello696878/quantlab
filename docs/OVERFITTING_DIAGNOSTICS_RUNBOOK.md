# QuantLab — Overfitting Diagnostics Runbook (Phase 53.0)

How to drive the Backtest Overfitting / PBO / Deflated Sharpe / Multiple
Testing Diagnostics Lab.  Companions:
[`BACKTEST_OVERFITTING_DIAGNOSTICS_LAB.md`](BACKTEST_OVERFITTING_DIAGNOSTICS_LAB.md) ·
[`PBO_AND_CSCV_POLICY.md`](PBO_AND_CSCV_POLICY.md) ·
[`SHARPE_DEFLATION_POLICY.md`](SHARPE_DEFLATION_POLICY.md) ·
[`MULTIPLE_TESTING_POLICY.md`](MULTIPLE_TESTING_POLICY.md).

## 1. Start the app

```powershell
cd C:\quantlab\backend; venv\Scripts\uvicorn app.main:app --reload --port 8000
cd C:\quantlab\frontend; npm run dev   # http://localhost:3000
```

Open **Overfitting Diagnostics** in the sidebar (Product Workflow, after
Feature Diagnostics) or via the command palette (Ctrl+K → "Overfitting
Diagnostics").

## 2. Load the deterministic demo

Click **Load demo runs** (or `POST /overfitting-diagnostics/demo-seed`).
Four runs appear; loading again reports "nothing duplicated".  The seed
cascades every other registry's idempotent demo loader — real user records
are never modified.

## 3. Create a candidate universe (API)

`POST /overfitting-diagnostics/runs` with name, `metric` (`sharpe_like` |
`mean_return` | `median_return`), `block_count` (even, 4–12),
`timestamps` (24–2000 strictly-increasing ISO-8601, one tz convention), and
2–24 `candidates` — each `{candidate_id, returns[...aligned...],
optional nominal_p_value + p_value_provenance, optional experiment/
validation/dataset links}`.  Optional: `benchmark_sharpe`, `confidence`,
`alpha`, `trial_count_policy` (`{"mode": "raw"|"manual"|
"dependence_adjusted", "manual_value": …}`), `dependence`
(`{"threshold": …}`), `periods_per_year`, run-level links.  Then
`POST /runs/{id}/execute` (optionally `{"create_experiment": true}`).

## 4. Select metric and configure CSCV

All ranking metrics are per-period and higher-is-better; `sharpe_like`
needs non-constant returns.  Block count trades resolution against
combinations: S=8 → 70 splits, S=10 → 252, S=12 → 924 (the cap).  Bad
configurations (odd S, too few observations, over-cap combinations) are
422s at creation.

## 5. Inspect PBO

Detail → **PBO**: the estimate with its note, valid/invalid split counts,
λ statistics, the λ histogram (orange = below zero, red dashed line at
λ = 0), IS↔OOS correlation, OOS-loss fraction, and tie counts.  Read the
rank convention printed under the cards — PBO is the fraction of valid
splits with λ < 0, nothing else.

## 6. Inspect rank degradation and selection frequency

The **CSCV splits** table lists every combination: IS blocks, selected
candidate, IS/OOS metric, OOS rank (of N defined), ω, λ, degradation, tie
flags and status.  **Candidate selection frequency** shows who won
in-sample how often and how those selections ranked out of sample — the top
row is "highest measured selection frequency", never a winner.

## 7. Inspect PSR / DSR

**Sharpe diagnostics** shows the focus candidate (highest observed Sharpe —
the value selection bias applies to), observed Sharpe, T, skewness,
non-excess kurtosis, benchmark SR\*, PSR, raw/effective trials with the
policy, E[maxSR], DSR and MinTRL, plus small-sample warnings and every
unavailable-reason.  DSR < PSR is the deflation at work.

## 8. Inspect multiple testing

The table lists nominal p, Bonferroni, Holm, and BH q-values with neutral
threshold states at the configured alpha, provenance status per candidate,
and the FWER-vs-FDR explanation.  Nothing is accepted or rejected for you.

## 9. Compare runs

Select two runs' checkboxes → **Compare selected**.  Comparability warnings
fire when universes/metrics/blocks/windows/annualization/trial assumptions
differ; identity and diagnostic groups show A/B/Δ; selection frequencies
are listed side by side.  No better run is declared.

## 10. Mark a baseline

Detail → **Mark as scope baseline** (completed + zero invalid splits
required; one baseline per dataset/universe/metric/blocks/window scope,
transactionally replaced).  A failed run has no baseline action and the API
answers 409.

## 11. Export

**Export JSON** downloads the filtered runs with candidates, blocks,
splits, aggregates, Sharpe diagnostics, multiple testing, dependence and
fingerprints — no paths, credentials, or serialized models.

## 12. Troubleshooting

* **"no valid CSCV splits"** — every combination had undefined metrics
  (typically all-constant candidates under `sharpe_like`); check the split
  warnings.
* **DSR unavailable, "one effective trial"** — the trial policy resolved to
  K < 2; use `raw` or supply a manual value ≥ 2.
* **PSR unavailable, "variance expansion"** — extreme skew/kurtosis with a
  large Sharpe violates the expansion; the statistic honestly refuses.
* **422 on creation** — read the detail: alignment, block count, bounds and
  p-value ranges are all validated eagerly.
* **Backend offline banner** — start uvicorn on port 8000.

## 13. Safe demo/test reset

Demo records carry unique `demo_key`s (`demo:od:*`) plus the cascaded demo
keys of the other registries; they can be deleted from a dev database by
key without touching real records.  The Playwright suite only writes these
idempotent seeds.  Never delete from a database you care about without a
backup.

## Ground rules (unchanged by this doc)

Deterministic educational sample data; no live data; PBO/PSR/DSR are
research statistics — not profitability, robustness, or safety evidence; no
strategy selection or capital allocation; not investment advice; not
production trading, risk, or compliance infrastructure.
