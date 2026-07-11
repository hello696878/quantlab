# QuantLab — Known Limitations (Public) (Phase 42.0)

The public-facing version of the limitations ledger: what a visitor,
recruiter, or interviewer should know before forming an opinion. These are
deliberate design decisions and honest boundaries, stated plainly. The full
internal per-phase ledger is [`LIMITATIONS.md`](LIMITATIONS.md).

## 1. Educational deterministic sample data

Almost every lab runs on hand-written, deterministic sample data (plus
user-entered inputs in the backtest engines). Numbers are educational
illustrations of documented formulas — nothing is calibrated to current
markets, and no output should be read as a market view.

## 2. Not investment advice

Nothing in QuantLab is investment, trading, allocation, legal, tax,
compliance, or risk-management advice. Generated reports enforce this in
wording — and the wording rules are themselves backend tests.

## 3. Not a live trading system

QuantLab places no orders and has no execution path, no order management,
and no market connectivity. This is a research and product-engineering
project, not a trading product.

## 4. Not connected to brokers, exchanges, or wallets

There are no broker, exchange, or wallet integrations of any kind, and none
are planned in the current scope.

## 5. Not a production compliance or risk system

The QA Command Center, Data Reliability Center, and release docs are product
workflow layers for this project — not compliance tooling, and no regulatory
framework is implemented or claimed.

## 6. Not audited

No external security audit, code audit, or model validation has been
performed, and none is claimed. The security posture is "zero secrets by
design plus documented hygiene" ([`SECURITY_AND_SECRETS.md`](SECURITY_AND_SECRETS.md)),
verified by the author, not by a third party.

## 7. External provider caveats

A few modules can *optionally* use external data (yfinance historical
downloads; opt-in FRED macro series; opt-in delayed globe quotes). All are
disabled by default, fail closed to deterministic static data, and are never
relied on in tests. Availability is never guaranteed, and no provider data
is redistributed.

## 8. Local development focus

QuantLab is local-first and single-user: no hosting, no login, no cloud
sync, no telemetry. A hosted read-only demo is a known future step with its
own requirements ([`DEPLOYMENT_READINESS.md`](DEPLOYMENT_READINESS.md)).

## 9. Manual verification required

Route smoke testing is a documented human pass
([`FINAL_SMOKE_TEST_RUNBOOK.md`](FINAL_SMOKE_TEST_RUNBOOK.md)), not an
automated one. In-app readiness scores are documentation-coverage reads —
they never prove that tests were run.

## 10. Frontend build is user-run

`npm run build` is always executed locally by the user; no tooling in this
repo runs it. CI additionally builds the frontend on push, which is separate
from the local flow.

## 11. CI preflight is limited

CI runs the backend test suite and a frontend typecheck + build on push
([`CI.md`](CI.md)). It does not run browser tests (there is no frontend test
framework yet), does not test optional live providers, and a green badge is
a preflight signal — not a certification.

## 12. Future improvements (openly planned)

- A frontend test framework (shared chart/formula primitives first).
- Registry-vs-route drift tests so stale metadata fails CI.
- Screenshot captures for the newer labs from real runs.
- A read-only hosted demo once the deployment gaps are addressed.
- Deeper pre-configured links between the product workflow layers.

---

These limitations are the point, not the fine print: the project
demonstrates how to build and document a research platform honestly —
deterministic data, tested wording contracts, and verification that is
actually run rather than claimed.
