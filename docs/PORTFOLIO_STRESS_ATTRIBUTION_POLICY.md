# Portfolio Stress Attribution Policy (v1)

How a scenario's measured effect is attributed, reconciled and labelled.

## Direct shock attribution

```
contribution_i             = weight_i × shock_i
portfolio_scenario_return  = Σ_i contribution_i
scenario_pnl               = notional × portfolio_scenario_return
```

A static linear approximation on the **fixed stored book** (exact for
one-period simple returns; intra-scenario compounding is not modelled).
Long and short weights flow through signed arithmetic unchanged; nothing is
normalized silently and no leverage is implied. The notional is always
explicit — a P&L is `null` when no notional is configured, never fabricated.

Contributions are **measured under this scenario**; they are never described
as having caused anything.

## Reconciliation (gross → cost → net)

```
net_scenario_return = direct_shock_return − stressed_cost_return
```

Both legs cover the **same basis**. The stored reconciliation block carries:

- `direct_shock_return`, `stressed_cost_return`, `net_scenario_return`;
- `stressed_cost_state` (`not_configured` / `available` / `unavailable`) and
  `stressed_cost_reason` — a configured-but-uncomputable cost leg is
  labelled, never silently equal to gross;
- `stressed_cost_completeness` and `cost_basis_note` (the cost leg is the
  stressed cost of a **reference** one-way move of the whole book —
  turnover `0.5 × Σ|w|` — a reference calculation, not a modelled trade);
- `completeness`: `partial` whenever the shock coverage is partial **or**
  the cost leg is partial/unavailable (a partial cost total under-estimates
  cost, so the triple is labelled partial too).

Under `missing_shock_policy = unavailable`, the total covers only the
shocked subset and the run is `partial`.

**Basis guard.** The cost leg is always a whole-book reference, so it is
never subtracted from a shock leg that covers only a subset: when the
shock coverage is partial *and* a cost leg exists, `net_scenario_return`
and `scenario_pnl` are **withheld** (`null`) with an explicit
`net_basis_note`, and both legs are reported separately. Netting two
different bases would silently misstate the result.

**P&L and risk effects never mix.** Volatility/correlation stress changes
risk *estimates* only and is reported separately.

## Post-shock drifted weights

```
post_value_i = w_i × (1 + r_i)          (r must be ≥ −100%)
cash         = 1 − Σw                   (SIGNED: negative = borrowed)
drifted_i    = post_value_i / (Σ post_value + cash)   = w_i(1+r_i) / (1 + Σ w_i r_i)
```

Cash is carried unshocked with its sign intact, so a zero shock leaves any
book — levered or not — unchanged. A return below −100%, or a non-positive or non-finite denominator
(a wiped-out long-short book) returns unavailable with the reason. **No
automatic rebalancing occurs**: the drifted book is pure arithmetic drift.

## Constraint checks

The stored Phase 56 constraints are re-checked independently on the
**original** and **drifted** books. Breaches are reported per book, and the
warning distinguishes breaches created by the scenario (drifted) from those
already present on the stored book before any shock. Nothing is repaired,
relaxed or rebalanced.

## Liquidity and cost stress

The linked Phase 55 cost model is **deep-copied** and the explicit
multipliers (spread / slippage / impact / ADV / notional scale) are applied
to the copy, which receives its **own new fingerprint**. The stored Phase 55
record and its fingerprint are never modified. Components that need trade
sizes or liquidity inputs this lab does not fabricate (e.g. square-root
impact on weight-space turnover) stay **unavailable with reasons** — never
silently zero. Participation is reported only with an explicit base ADV and
notional.

`cost_volatility_multiplier` is deferred in v1 and rejected explicitly (the
period cost path has no volatility input to stress) — a configured
assumption is never silently dropped.

## Sensitivity probes

The table's first row is the run's **own scenario** on the same net basis as
the run's reconciliation. Every other row is a **self-contained
one-dimension scenario** around the same stored book — not a perturbation of
the configured scenario — and each row says so. Breach counts come from a
real drifted-book check, or `null` when the drifted book is unavailable
(never a silent zero).
