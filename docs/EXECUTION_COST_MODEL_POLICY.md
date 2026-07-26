# Execution Cost Model Policy (v1)

Exact unit and component semantics for the Cost Diagnostics Lab
(`backend/app/cost_diagnostics/units.py`, `components.py`). Nothing here
recommends broker terms or claims any configured level is achievable.

## 1. Cost units

Every cost input declares its unit; conversion is explicit:

| Unit | Conversion (one execution context) | Requires |
| --- | --- | --- |
| `bps_of_notional` | `value × 0.0001 × notional` (1 bp = 0.0001) | notional |
| `percent_of_notional` | `value × 0.01 × notional` (never ambiguous "percent") | notional |
| `ticks` | `value × tick_size × quantity × multiplier` | tick_size > 0, quantity, multiplier |
| `price_units` | `value × quantity × multiplier` | quantity, multiplier |
| `currency_per_contract` | `value × quantity` | quantity |
| `currency_per_unit` | `value × quantity × multiplier` (underlying units) | quantity, multiplier |
| `currency_per_order` | `value × order_count` | integer order_count ≥ 1 |
| `currency_per_trade` | `value` once per round-trip | — |

Missing or invalid context yields an unavailable record with an explicit
reason — never zero. Negative cost values are rejected (favourable amounts
exist only as supplied realized slippage). Currency amounts require the
run's single result currency; mixed currencies are rejected outright (no
silent FX conversion). Original value + unit are stored beside every
normalized cost.

## 2. Commission and fees

Models: `none`, `fixed_per_order`, `fixed_per_trade`, `per_contract`,
`per_unit`, `bps_of_notional`.

- `fixed_per_order` charges its value once per order with explicit
  `entry_orders` / `exit_orders` counts (each 1–10, default 1).
- `fixed_per_trade` charges once per round-trip trade.
- `per_contract` charges per contract **per side** (entry and exit each
  pay): `value × quantity × 2`.
- `per_unit` charges per underlying unit per side:
  `value × quantity × contract_multiplier × 2`.
- `bps_of_notional` is a **per-side** rate applied to each side's
  notional — equivalently `value × 0.0001 × traded_notional` where
  `traded_notional = entry_notional + exit_notional`. A long↔short
  round trip therefore pays both sides exactly once (no double counting).
- Optional `minimum` (floor, applied first) then `maximum` (cap);
  `maximum ≥ minimum` enforced. Negative fees rejected; zero allowed.
- Period runs support only `none` / `bps_of_notional` on per-period
  turnover (`value × 0.0001 × turnover`); monetary floors/caps and order
  counts are rejected for period runs rather than silently ignored.
- No broker-specific claims, no tier schedules, no hidden exchange or
  regulatory fees. Supplied realized commissions are not modelled in v1.

## 3. Spread cost

Models: `none`, `fixed_bps`, `fixed_price`, `fixed_ticks`, `supplied`.

- The configured `fraction` ∈ [0, 1] of the quoted spread is assumed paid
  per marketable execution. **The fraction must be configured explicitly**
  — there is no silent half-spread or full-spread default; the UI and
  export always display it.
- Per side: `fraction × spread_in_price_units × quantity × multiplier`,
  where bps spreads use the side's own reference price and tick spreads
  require a positive tick size. `sides` is explicit: `round_trip`
  (default, entry + exit), `entry_only`, `exit_only`. Period runs accept
  only `round_trip` (turnover carries no side decomposition) and charge
  `fraction × spread_bps × 0.0001 × turnover`.
- Negative spreads are rejected; a missing supplied spread stays
  unavailable. Timing/lag of supplied spreads follows the no-look-ahead
  policy; no future spread observation may be used.

## 4. Slippage

Models: `none`, `fixed_bps_per_side`, `fixed_ticks_per_side`,
`fixed_price_per_side`, `supplied_realized`.

- Fixed models are deterministic per-side assumptions charged on both
  sides; no random slippage exists in v1.
- The `stress_multiplier` ∈ [1, 10] applies to **modelled** slippage only
  — it can never generate favourable slippage and never touches supplied
  realized values (in the sensitivity grid as well).
- `supplied_realized` uses per-observation realized slippage as-is;
  favourable (negative) values are supported only there and are labelled.
  Under capacity scaling the realized per-unit value is held constant
  (amount scales with the size ratio).
- Modelled slippage is an assumption — it is never claimed to predict
  actual fills.

## 5. Gross-to-net reconciliation

For every observation: gross, commission, spread cost, slippage, impact,
total cost, net. Invariants (tested):

- components are non-overlapping and share the observation's unit;
- `total_cost = Σ available components` exactly;
- `net = gross − total_cost` exactly;
- entry and exit costs are charged once each, never twice;
- an unavailable component is listed by name with a reason and excluded —
  the observation becomes `partial` (net disclosed as excluding the
  missing components) or `gross_only`; missing costs are never zero.

Monetary and return views reconcile for trade runs
(`net_return = net / entry_notional`); period runs are return-native.
