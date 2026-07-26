# Brinson Attribution Policy (v1)

The exact single-period decomposition implemented by the Portfolio
Attribution Lab. Both variants are implemented, tested against hand-computed
values, and named in every result.

## Variants and formulas

With `Wp_g` / `Wb_g` the portfolio and benchmark **group weights**, `Rp_g` /
`Rb_g` the group returns and `Rb_total` the total benchmark return:

**Brinson-Fachler (default)**

```
allocation_g  = (Wp_g − Wb_g) × (Rb_g − Rb_total)
selection_g   =  Wb_g         × (Rp_g − Rb_g)
interaction_g = (Wp_g − Wb_g) × (Rp_g − Rb_g)
```

**Brinson-Hood-Beebower**

```
allocation_g  = (Wp_g − Wb_g) ×  Rb_g
selection_g   =  Wb_g         × (Rp_g − Rb_g)
interaction_g = (Wp_g − Wb_g) × (Rp_g − Rb_g)
```

Both decompose the **same** active return. They differ only in how the
allocation term is benchmarked: BF measures a group's over/under-weight
against the benchmark's own average return, so a BF allocation effect is zero
when a group's benchmark return equals the total benchmark return. For books
whose weights each sum to one, `Σ_g (allocation + selection + interaction) =
Rp − Rb` exactly.

Worked example from the demo (balanced book 60/40 vs an equal-weight
benchmark, type-A period):

```
portfolio 0.30(0.02)+0.30(0.04)+0.20(0.01)+0.20(−0.01) = 0.018
benchmark 0.25(0.02)+0.25(0.04)+0.25(0.01)+0.25(−0.01) = 0.015
active                                                  = 0.003
equity  Wp 0.60 Rp 0.030 | Wb 0.50 Rb 0.030
bond    Wp 0.40 Rp 0.000 | Wb 0.50 Rb 0.000
allocation (0.60−0.50)(0.030−0.015) + (0.40−0.50)(0.000−0.015) = 0.003
selection / interaction                                         = 0
```

## Group returns

See `PORTFOLIO_RETURN_CONTRIBUTION_POLICY.md` for the exact formula. In
Brinson terms:

- a group with **zero weight** on a side has no return on that side, so the
  terms that need it are reported **unavailable** rather than fabricated;
- **portfolio-only** groups (`Wb = 0`, no `Rb`) leave `allocation`,
  `selection` and `interaction` unavailable;
- **benchmark-only** groups (`Wp = 0`, no `Rp`) leave `selection` and
  `interaction` unavailable while `allocation` remains computable;
- each row records its `presence` (`both` / `portfolio_only` /
  `benchmark_only`), and the aggregated window row records `mixed` when the
  presence changes across periods rather than silently picking one period's
  label.

## Residual policy

```
residual = active_return − (allocation + selection + interaction)
```

The residual is reported **verbatim**. It is never set to zero and never
redistributed into the three effects. Every residual carries stated reasons,
which may include:

- the portfolio or benchmark group weights not summing to one (the cash or
  leverage residual sits outside the group decomposition — the residual is
  then exactly that un-decomposed term);
- unavailable group returns from one-sided or zero-weight groups (the
  specific unavailable terms are listed).

`reconciliation_state` is `reconciled` when `|residual| ≤ tolerance` and
`residual` otherwise; the run-level `reconciliation_status` aggregates the
contribution identity, the group identity and every period's Brinson closure.

## Long/short

A negative group weight makes the weighted-return ratio sign-unstable. Such
a group is reported with an explicit `negative_weight` state and is not
directly compared with a long group's return; the decomposition is
descriptive in that case and says so.

## Wording

Allocation, selection and interaction are **arithmetic decompositions of a
measured return difference under a stated convention**. They are not proof of
investment skill, not alpha, and not a recommendation.
