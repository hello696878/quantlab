# Market Impact & Capacity Policy (v1)

The exact market-impact approximation and capacity-scaling semantics of
the Cost Diagnostics Lab (`backend/app/cost_diagnostics/impact.py`,
`scenarios.py`). Nothing here predicts actual market impact, guarantees
capacity, or recommends a size.

## 1. Implemented impact models

`none`, `fixed_bps`, and the bounded research approximation
`square_root`:

```
participation_side  = traded_quantity_or_notional_side / ADV
impact_fraction_side = impact_coefficient × volatility × sqrt(participation_side)
impact_cost          = Σ over executed sides of impact_fraction_side × side_notional
```

- `impact_coefficient` is explicit and bounded (0 ≤ c ≤ 10); no default.
- `volatility` is a per-period return fraction (sample std, ddof=1); the
  convention is recorded in every run's configuration.
- `participation_mode` is explicit: `quantity` divides contract/unit
  quantity by ADV in units; `notional` divides side notional by ADV in
  currency. The ADV input's declared unit must match the mode — a
  mismatch is unavailable, never silently converted (enforced at create
  time for trailing series and per observation for supplied inputs).
- Both sides of a round-trip trade are charged (each with its own side
  notional); the trade side never reverses the sign — impact is a
  non-negative cost estimate by construction, and zero participation
  gives exactly zero impact.
- Missing ADV / volume / volatility produces an unavailable status with a
  reason — never a silent zero fallback.
- Period runs use notional participation
  (`traded_notional / ADV_currency`) and charge
  `impact_fraction × turnover` in return space.
- `fixed_bps` charges `value × 0.0001` on traded notional (trade runs) or
  turnover (period runs).

The square-root form is deliberately consistent with the educational
Microstructure Lab (`impact_bps = coefficient × sqrt(qty/ADV) ×
volatility_bps`); both are research approximations — neither predicts
actual impact, and no complex proprietary model exists in v1.

## 2. Participation diagnostics

Per observation: participation against the configured denominator with a
configured threshold (default 0.25, bounds 0.001–10). Statuses:
`within_configured_threshold`, `above_configured_threshold`,
`unavailable` (missing/non-positive denominator), `invalid`
(non-finite). Participation above 100% stays visible with a warning —
the lab never rejects or resizes anything automatically. Daily volume
and ADV are never mixed silently (units are declared per input).

## 3. Capacity scaling

Bounded scale factors (defaults 0.25 / 0.5 / 1 / 2 / 5×, user-
configurable, ≤ 8 values in (0.001, 100], 1× always included) applied to
observation size — **never to historical prices**. Per scale the lab
recomputes every component from its configuration:

- fixed per-order/per-trade fees remain fixed;
- per-unit / per-contract fees scale with quantity;
- bps-of-notional costs scale with notional;
- spread and modelled slippage scale with quantity/notional per their
  units; supplied realized slippage holds its per-unit value constant;
- square-root impact responds through participation: participation scales
  linearly with size, so impact cost scales as `scale^1.5`;
- gross results scale proportionally under the documented assumption that
  the historical per-unit result is unchanged.

Optional `integer_contracts` policy: scaled quantities are floored to
whole contracts; a floor of zero excludes the observation at that scale
(reported in `excluded_count`, never silently dropped); whole-number base
quantities are required when the policy is enabled so the 1× row always
matches the run aggregates.

Per scale: traded notional, mean/max participation, above-threshold
count, per-component totals, total cost, gross, net, unavailable-
liquidity count, exclusions. Everything is labelled **estimated under
configured assumptions**: no assumption that fills remain available at
scale, no executable-capacity claim, and no automatic maximum-capacity
recommendation.

## 4. Break-even and sensitivity interaction

The break-even impact coefficient uses the model's linearity in its
coefficient (`c* = c × impact break-even multiplier`). Sensitivity
multipliers scale computed base impact amounts, which for the square-root
model is exactly a coefficient multiplier. Break-even values describe the
measured sample under configured assumptions and are not claimed
achievable in markets.
