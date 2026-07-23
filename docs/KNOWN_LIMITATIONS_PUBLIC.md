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

## 12. Experiment registry reproducibility is metadata-only

The Research Experiment Registry records reproducibility metadata and computes
deterministic SHA-256 fingerprints and a conservative reproducibility status.
This is **repository-level metadata validation** — it compares recorded inputs
and outputs. It is not a re-execution of the experiment, not scientific
reproducibility, not an audit trail, and not tamper-proof security. A
"reproducible" status means the recorded metadata matches, nothing more.

## 13. Dataset provenance is declared metadata, not verified data

The Dataset Lineage registry records dataset identity, versions,
transformations, and quality-check results as **declared metadata** with
deterministic fingerprints over that metadata. It does not open or verify the
underlying data files during normal operation, is not a tamper-proof ledger,
not an enterprise data catalog, and not a regulatory audit trail. Quality
checks validate declared structural properties only — passing checks does not
mean the data is financially or scientifically correct.

## 14. Model validation audits intervals, not everything

The Model Validation Lab's purged K-fold, embargo, and CPCV remove and audit
temporal leakage **through the declared information intervals** of the
supplied samples. The audit cannot see leakage through features computed from
wider windows, preprocessing that spans folds, or repeated hyperparameter
selection on the same data. A "leakage-clean" run is a methodology check —
not proof of model quality or profitability, and the lab never recommends or
ranks models.

## 15. Calibration quality is not profitability

The Meta-Labeling Lab's calibration metrics (Brier, ECE, reliability curves)
measure how well predicted probabilities match observed label frequencies
under a documented research outcome rule. They say nothing about costs,
capacity, or future regimes; meta-label 1 is a research condition, not a
profitable trade; and the lab never selects a best model or recommends a
threshold — saved threshold policies are the user's own research records.

## 16. Feature importance is sensitivity, not causality

The Feature Diagnostics Lab's permutation importance measures how much one
metric degrades when one feature column is shuffled on held-out samples —
under one model, one metric, and the supplied data. It is not causal
evidence, not a profitability signal, and not feature selection: correlated
features can split or mask importance, native/coefficient references are
training-data derived (labelled as such), drift classifications describe
data changes rather than model failure, and the lab never deletes features,
retrains user models, or recommends anything.

## 17. PBO and Sharpe deflation are estimates, not verdicts

The Overfitting Diagnostics Lab estimates how often an in-sample-selected
candidate ranked poorly out of sample (PBO via CSCV) and deflates the
highest observed Sharpe for the number of trials attempted (PSR/DSR). Both
are research statistics under explicit assumptions: PBO depends on the
chosen universe, metric and block count; PSR/DSR inherit distributional
assumptions and small-sample fragility; the effective trial count is an
approximation; and declared p-values are recorded, never verified. A low
PBO is not robustness, a high DSR is not proof against overfitting, and the
lab never selects, recommends, or allocates to any candidate.

## 18. Regime labels are descriptive states, not predictions

The Regime Diagnostics Lab conditions results on regimes formed by explicit
causal rules (trailing windows, lagged effective labels, documented
threshold-fitting subsets). That contract covers the lab's own label
construction — it cannot audit how the supplied market features were
produced upstream. Conditioning is stratification, not causal
identification: a regime can proxy for anything correlated with it, rare
regimes are honestly withheld rather than estimated, full-sample-fitted
thresholds are always flagged as descriptive, and no significance testing
exists in v1. The lab never predicts regimes, never switches strategies,
and never calls a regime profitable or safe.

## 19. Cost estimates are configured assumptions, not fills

The Cost Diagnostics Lab applies explicitly configured commission, spread,
slippage and square-root market-impact assumptions to supplied historical
observations. Every output is an estimate under those assumptions: modelled
slippage predicts no actual fill, the impact model is a bounded research
approximation with a caller-chosen coefficient, and capacity scaling assumes
historical per-unit results scale with size while saying nothing about fill
availability — it is never executable capacity or a size recommendation.
Missing inputs stay honestly unavailable (never zero), full-sample liquidity
averages stay descriptive, break-even levels describe the measured sample
only, and the lab never executes orders, recommends brokers or sizes,
proves profitability, or certifies execution quality.

## 20. Future improvements (openly planned)

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
