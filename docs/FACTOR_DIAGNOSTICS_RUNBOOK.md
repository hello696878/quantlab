# Factor Diagnostics Lab Runbook (v1)

Phase 59.0 · module `factor_diagnostics` · API `/factor-diagnostics`

## 1. Start the services

```bash
cd C:\quantlab\backend; .\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

```bash
cd C:\quantlab\frontend; npm run dev
```

Then open `http://localhost:3000` → sidebar **Factor Diagnostics**.

The migration is append-only and idempotent: eight new tables
(`factor_diagnostic_runs`, `factor_definitions`, `factor_observations`,
`factor_coefficients`, `factor_period_results`, `factor_rolling_results`,
`factor_regime_results`, `factor_sensitivity_results`) plus 26 indexes. No
existing table, column or index is altered or dropped, and no demo data is
inserted at startup.

## 2. Load the demo

Click **Load demo runs** (or `POST /factor-diagnostics/demo-seed`). It is
idempotent — loading twice creates nothing new and says so. It cascades the
Regime, Model Validation, Portfolio Attribution and Portfolio Stress demo
loaders first, then reads them **read-only**.

## 3. The twenty demo cases

| # | demo_key | what it demonstrates |
| --- | --- | --- |
| 1 | `exact-single-factor` | `y = 0.60·a` exactly → coefficient **0.600000**, R² 1, standard errors withheld because the residual variance is zero |
| 2 | `exact-two-factor` | `y = 0.002 + 1.50·a − 0.50·b` → **1.500000 / −0.500000**, intercept **0.002** |
| 3 | `intercept-and-residual` | orthogonal residual cycle → intercept **0.001**, `a` **0.800000** with live standard errors, `b` **0** with p = 1; multiple-testing corrections and five sensitivity scenarios |
| 4 | `constant-factor` | a constant column with the intercept excluded: flagged, VIF unavailable, still full rank |
| 5 | `duplicate-factor` | identical columns → rank 2 of 3, labelled minimum-norm, all inference withheld |
| 6 | `rank-deficient-sum` | `c = a + b` exact dependence |
| 7 | `high-condition-number` | 1e-7 perturbation → huge condition number, still full rank |
| 8 | `zero-variance-target` | constant target → R² **unavailable** with a reason |
| 9 | `insufficient-observations` | 4 observations, 4 parameters → the run **fails** with that sentence |
| 10 | `lagged-causal` | lag 1 with explicit availability → `verified_trailing_estimation`, rolling window 12 step 3 |
| 11 | `contemporaneous-descriptive` | same data, lag 0 → `contemporaneous_descriptive` |
| 12 | `future-looking-invalid` | declared invalid, lead 1 → `invalid`, baseline refused |
| 13 | `rolling-beta-change` | 0.50 → 1.50 halfway; trailing windows show the change |
| 14 | `benchmark-active-exposure` | attribution-linked portfolio return + the same fit on its declared benchmark |
| 15 | `attribution-linked-active` | the stored active return decomposed by factor exposure |
| 16 | `regime-linked` | stored Phase 54 volatility assignments; rare regimes withheld |
| 17 | `stress-linked` | measured exposures × explicitly supplied factor shocks |
| 18 | `held-out-validation` | training-only fit on a stored purged/embargoed split |
| 19 | `macro-missing-availability` | basis-point rate change with the availability assumption stated |
| 20 | `baseline-candidate` | causal timing, full rank, complete, reconciled → the only combination accepted as a baseline |

## 4. Manual verification

1. Open **Factor Diagnostics**; confirm the local-first badge and the
   no-causality / no-advice disclaimer.
2. Confirm every filter control uses the dark theme (no white inputs or
   selects) and has a visible label.
3. Confirm every factor and return field shows its unit (source unit,
   transformed unit, and *target return per 1 unit* on each coefficient).
4. Click **Load demo runs** twice; confirm the second load reports nothing
   duplicated and the row count is unchanged.
5. Open *Exact single-factor relationship*; read **0.600000** in the
   coefficient table.
6. Verify by hand: the factor cycle is `0.010, −0.005, 0.020, 0.000,
   −0.010, 0.015` and the target is `0.6 ×` it.
7. In **Per-period decomposition**, confirm measured = intercept + factor
   contribution + residual on every row and the state reads `reconciled`.
8. Open *Two known coefficients*; confirm **1.500000**, **−0.500000** and
   intercept **0.002**.
9. Open *Non-zero intercept and residual*; confirm **0.800000**, a
   standard error, a t-statistic, a confidence interval and raw + adjusted
   p-values, and that `factor_b` reads p ≈ 1.
10. Confirm inferential statistics appear **only** where they are defined:
    the exact-fit case says the residual variance is zero.
11. Open *Constant factor column*; confirm the constant warning and an
    unavailable VIF, with no misleading coefficient claim.
12. Open *Duplicate factor column*; confirm rank 2 of 3, the
    rank-deficient label and withheld standard errors.
13. Open *Near-collinear factors*; inspect the condition number and the
    factor-correlation table (the heatmap and the table carry the same
    numbers; colour is never the only signal).
14. Open *Insufficient observations*; confirm the failure message and that
    no coefficients are shown.
15. Open *Lagged causal alignment*; in **Aligned factor observations**
    confirm each *knowable at* precedes the period it feeds.
16. Open *Contemporaneous alignment*; confirm the descriptive wording and
    that nothing calls it predictive.
17. Open *Future-looking alignment*; confirm the invalid state, then click
    **Mark as comparison baseline** and confirm it is rejected.
18. Open *Rolling exposure change*; confirm the first windows read ≈ 0.50
    and the last ≈ 1.50, and that earlier windows are unchanged by later
    observations (the window fingerprints are stable).
19. Inspect **Exposure stability**: sample counts, availability, sign
    changes and the largest jump, with no stability verdict.
20. Open *Portfolio versus benchmark exposure*; confirm active = portfolio
    − benchmark on every row.
21. Open *Exposure by STORED regime assignment*; confirm the rare-regime
    marker and the withheld conditional fits.
22. Open *Exposure-implied factor shock*; confirm the formula, the supplied
    shocks and the "no hedge or reallocation follows" warning.
23. Open *Active return decomposed by factor exposure*; confirm the
    complementary-to-Brinson wording and the separated cost note.
24. Open *Held-out evaluation*; confirm training / held-out / purged /
    embargoed counts and the TRAINING-mean R² formula.
25. Select two runs, click **Compare selected**; confirm neutral
    comparability warnings and no better/superior/recommended wording.
26. Click **Export JSON**; confirm no paths, credentials or provider data.
27. Resize to 1024 and 768; confirm no table overlap, no page-level
    horizontal overflow and readable charts.
28. Confirm no NaN, no Infinity and no raw stack trace anywhere.
29. Re-open the other research views and confirm no theme or layout
    regression.

## 5. Isolation policy for automated E2E

`frontend/e2e/factor-diagnostics.spec.ts` must run against services
configured with an **isolated test database**. Its only writes are the
idempotent demo seeds (unique `demo_key`, cascading through the Phase
54/56/57/58 loaders) and one deliberately rejected baseline attempt (a 409
that is filtered out of the failed-request assertion). It never clears a
database and performs no external network access.

## 6. Troubleshooting

* **`IndexError: No item with that key` from `factor_diagnostic_runs`** — a
  database created by an early Phase 59 development build. Restart the
  backend once: `init_db()` adds the missing column idempotently.
* **A run is `failed` with "cannot identify N parameter(s)"** — that is the
  intended honest refusal; add observations or remove a factor.
* **A run is `invalid`** — either a factor was knowable only after the
  period it explains, or the caller declared a future-looking alignment.
  The warning names the factor, the timestamp and the count.
* **`no observation at target timestamps [...]`** — v1 aligns by exact
  timestamp; supply factor observations on the target's own grid (plus any
  history the lag or a differencing transform needs).

## 7. Scope reminder

Nothing in this lab proves causality, proves alpha, proves manager skill,
predicts future returns, recommends a factor exposure, a macro trade or a
portfolio, builds a factor portfolio, hedges, allocates, executes trades,
certifies a factor model, or constitutes investment advice. No market or
macroeconomic data is ever downloaded.
