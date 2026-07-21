# QuantLab — Multiple Testing Policy (Phase 53.0)

The exact conventions behind the multiple-testing table in the Overfitting
Diagnostics Lab.  Companion:
[`BACKTEST_OVERFITTING_DIAGNOSTICS_LAB.md`](BACKTEST_OVERFITTING_DIAGNOSTICS_LAB.md).

## 1. Nominal p-values

Optional per candidate, validated at creation (finite, in [0, 1]); at most
64 candidates may carry one.  `m` — the correction denominator — counts
**only the candidates that supplied a valid p-value**; a missing p-value
stays `unavailable` and never changes anyone else's correction.

## 2. Provenance

A p-value arrives with optional provenance metadata (source test name, null
hypothesis, sidedness, statistic, degrees of freedom, sample count,
assumptions, linked experiment/validation run).  Statuses:

* `declared` — a p-value was supplied; the lab records it as a declaration
  and **never calls it independently verified**.
* `unavailable` — no p-value supplied.
* `invalid` — out of range or non-finite (excluded from m; no adjusted
  values are computed for it or from it).
* `verified_from_supported_test` — reserved; v1 runs no hypothesis tests of
  its own, so nothing earns this status yet.  P-values are never fabricated
  from Sharpe ratios.

## 3. Bonferroni

`p_adj = min(1, p · m)` — controls the family-wise error rate (FWER).

## 4. Holm step-down

Sort the m valid p-values ascending (stable on ties); for the j-th (0-based)
value `v_j = min(1, (m − j) · p_(j))`; the adjusted value is the running
maximum of v over the ordering (monotone non-decreasing).  Controls FWER;
uniformly no less powerful than Bonferroni.

## 5. Benjamini–Hochberg

For the j-th (0-based) sorted value `v_j = min(1, m/(j+1) · p_(j))`; the
q-value is the running **minimum from the largest j downward** (reverse
cumulative minimum, enforcing monotonicity).  Controls the false discovery
rate (FDR) under independence / positive regression dependence assumptions.

## 6. FWER versus FDR

Bonferroni and Holm bound the probability of **any** false positive across
the family (FWER).  Benjamini–Hochberg bounds the **expected fraction** of
false positives among the values called small (FDR) — a weaker guarantee.
**BH is never described as controlling family-wise error**, and the UI
prints this distinction next to the table.

## 7. Alpha

One configured alpha per run, validated in [0.001, 0.5] (default 0.05).
Each method's adjusted value is compared to alpha with strict `<`,
producing a neutral state.

## 8. Dependency limitations

The corrections assume the stated dependence structures; strongly correlated
candidates weaken them (BH's FDR guarantee holds under PRDS, Bonferroni/Holm
remain valid but conservative).  The dependence diagnostics exist precisely
so the correlation context is visible next to the corrections.

## 9. Neutral interpretation

Output states are exactly `below_threshold`, `above_threshold`, and
`unavailable`.  The lab never says approved, validated, safe, significant
finding, accepted, or rejected — and it never removes, accepts, or ranks
candidates based on these states.

## 10. No automatic acceptance

Nothing happens as a consequence of a threshold state: no candidate is
promoted, no baseline is set, no experiment is amended.  Reading the table
is the product.
