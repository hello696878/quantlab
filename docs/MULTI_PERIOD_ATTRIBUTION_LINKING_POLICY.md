# Multi-Period Attribution Linking Policy (v1)

How single-period effects become multi-period effects, and what each method
does and does not reconcile with.

## `arithmetic` — the reference view

Sum the single-period effects. This is a **reference only**: a simple
arithmetic sum of single-period effects does **not** generally reconcile with
the compounded active return, because compounding involves cross-period
products the sum omits.

The lab reports all of it explicitly:

- `arithmetic_active_return` — the summed per-period active return (the
  target this method reconciles with exactly);
- `compounded_portfolio_return`, `compounded_benchmark_return`,
  `geometric_active_return` — the compounded figures;
- `arithmetic_vs_geometric_gap` — the difference, disclosed rather than
  hidden;
- `arithmetic_caveat` — the sentence above, stored with the result.

## `carino` — geometric linking

Carinó (1999) logarithmic smoothing. With `Rp`, `Rb` the compounded returns:

```
k    = (ln(1+Rp) − ln(1+Rb)) / (Rp − Rb)
k_t  = (ln(1+rp_t) − ln(1+rb_t)) / (rp_t − rb_t)
linked_effect = Σ_t (k_t / k) × effect_t
```

Because `Σ_t (k_t/k)(rp_t − rb_t) = Rp − Rb`, the linked effects reconcile
with the **geometric** active return within tolerance.

**Degenerate cases are handled analytically, not with an epsilon fudge.** The
limit of `(ln(1+x) − ln(1+y))/(x − y)` as `y → x` is `1/(1+x)`, and that exact
value is used when `x = y` (tested).

**Undefined cases are withheld, not approximated.** A period (or total)
return of −100% or worse makes the logarithm undefined; the linked effects
are then `null` with a stated reason and the affected periods listed. No
fabricated factor is substituted.

**Closure identity.** The lab reports `linked_total_including_residual =
linked_effects + linked single-period residuals` and its `closure_residual`
against the geometric active return. So when single-period effects already
close, the linking residual is zero; when they do not, the linking residual is
**exactly** the scaled single-period residual — never an unexplained gap.

Per-period `smoothing_factors` and the `total_scaling_factor` are stored and
exportable.

## Group-level linking

When Carinó linking is available, the same per-period factors are applied to
each group's allocation / selection / interaction, giving
`linked_allocation_effect` and friends beside the arithmetic totals so both
views are visible at once.

## Partial windows

If any period lacks a benchmark observation, multi-period linking is
**withheld** entirely with a stated reason rather than linking a subset and
implying it covers the window.

## Time-weighted return

```
TWR = Π_t (1 + r_t) − 1
```

on cash-flow-neutral subperiod **simple** returns. The stored Phase 56 series
is a weight-driven return series with no external cash flows, which is
exactly what TWR requires, so the lab asserts that support explicitly. When
support cannot be asserted the result is **withheld** — a compounded number is
never *labelled* a time-weighted return when the inputs do not support it. A
period return of −100% or worse withholds it too. There is **no
money-weighted / IRR / XIRR figure and no placeholder** — no actual cash flows
exist in the inputs.

## Claims

Neither method is GIPS compliant and neither is claimed to be. Both are
arithmetic restatements of measured single-period effects — not evidence of
skill.
