# Portfolio Return Contribution Policy (v1)

How weights, timing and contributions are defined in the Portfolio
Attribution Lab. Every rule here is enforced in code and tested.

## Return convention

**Simple returns only** in v1. Log-return attribution is deferred with a
stated reason: contributions are not additive under log returns without a
documented conversion, and the lab will not present a non-additive
decomposition as if it were additive. A benchmark whose convention differs
is rejected — conventions are never mixed.

## Period convention

Period `t` spans `timestamps[t] → timestamps[t+1]`. Its return is the stored
`returns[t]`; its weights are those known at `timestamps[t]`
(`information_available_at`). Periods are strictly increasing and
non-overlapping by construction, and every asset shares the identical period
grid (strict alignment in v1).

## Beginning-of-period weights and no look-ahead

```
contribution_i,t          = w_i,t × r_i,t
portfolio_market_return_t = Σ_i contribution_i,t
portfolio_net_return_t    = portfolio_market_return_t − cost_return_t
```

`w_i,t` is the **beginning-of-period** weight:

- a stored rebalance with decision index `i` supplies the weights that govern
  period `i` onward. The Phase 56 estimation contract already guarantees
  those weights used data only through `i − lag` with `lag ≥ 1`, so a period
  never informs its own weights;
- between rebalances the book **drifts** by the identical recursion Phase 56
  uses for its realized return series, so `w_i,t` is a pure function of
  periods strictly before `t`. A test asserts the implied per-period return
  reproduces `portfolio_diagnostics.rebalance.portfolio_returns` exactly —
  the reuse is verified, not duplicated;
- **`end_of_period` weight timing is accepted only as an explicitly INVALID
  descriptive declaration.** A weight formed at the end of a period already
  embeds that period's return; it is never silently used as a
  beginning-of-period weight, and such a run can never become a baseline;
- negative lags and centered windows are rejected upstream by Phase 56 and,
  where declared, produce an `invalid` integrity state here.

**Adversarial invariants (tested):** a later rebalance cannot change an
earlier period's weights, and a later return cannot change an earlier
contribution.

## Cash, leverage and long/short

Cash is the explicit residual `1 − Σ w_i` and earns zero in v1. It is
reported per period (`cash_weight`), so a book that is partly in cash or
levered is visibly so; weights are never renormalized to hide it. Long and
short weights flow through signed arithmetic unchanged.

## Supplied-return reconciliation

When an independently supplied portfolio return is available it is compared
with the reconstructed one and the residual plus its tolerance status are
recorded. **The supplied value is never adjusted to match the
reconstruction** — a disagreement stays visible.

## Group contribution

Groups come from the linked portfolio's **explicit stored labels** (Phase 56
validates them); unlabelled assets fall into a visible `unclassified` group.
Groups never overlap in v1 — each asset belongs to exactly one — so group
totals sum to the asset totals with no double counting, and that identity is
checked against the configured tolerance. Groups are **never inferred from
ticker or asset names**.

Group return, only where the group weight is non-zero:

```
R_g = Σ_{i∈g} contribution_i / W_g          with W_g = Σ_{i∈g} w_i
```

- a **zero group weight** leaves the group return unavailable
  (`zero_weight`): a group with no capital has no weighted return, and one is
  never fabricated from its constituents' returns;
- a **negative group weight** (short exposure) makes the ratio sign-unstable,
  so it is reported with an explicit `negative_weight` state and is not
  directly comparable with a long group's return;
- there is no division by zero anywhere.

## Aggregation

Per asset the lab reports the arithmetic sum, the positive part, the negative
part, the absolute part, the absolute share and the observation count.
Signed and absolute quantities are always kept separate — a signed total near
zero does not mean nothing happened.

## Wording

Outputs are described as **measured contributions under this attribution
convention**. No contribution "caused" a result, and no contribution is
evidence of skill.
