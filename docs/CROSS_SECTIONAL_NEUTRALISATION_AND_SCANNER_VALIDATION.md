# Cross-Sectional Neutralisation and Scanner Validation v1

Educational synthetic research only. No real universe, provider, broker, borrow,
impact, capacity, optimizer, new signal, learned-policy search or alpha verdict.
The legacy generator's disclosed reversal component and random draw stream are
unchanged. Phase 67's declared calendars/retrospective rolls are not PIT certification.

## Reuse and Support

| Area | Actual reused contract / v1 support |
| --- | --- |
| Signals / baskets | Existing momentum/reversal generators and dollar-neutral basket selector |
| Simulation | Existing scanner P&L/turnover lifted unchanged into scanner/pnl.py; basic and advanced share it |
| Cross-sectional regression | Phase 59 regression.ols_fit: intercept, SVD rank/conditioning, rank-failure refusal; no time-series return residual reused as a score |
| Purge / embargo | Phase 52 normalize_samples, purged_kfold, audit_split and configuration/split fingerprints |
| Multiple testing | Phase 53 adjust_p_values unchanged: Bonferroni, Holm, BH, valid supplied-p family size |
| Persistence | Full-precision bounded JSON download with inline input/request/outcomes and recomputed integrity hashes; no new DB/registry |
| Replay / restoration | Not registered in Phase 66; no restoration, saved-context lookup or implicit execution |
| Deferred | Combined sector+beta constraints, learned beta/volatility OOS, PBO/DSR adapter, real classifications/universes, Phase 59 cross-sectional decomposition product feature |

## Information and Panel Contract

The existing synthetic price panel supplies explicit ordered session and asset
IDs, prices, close-to-close decimal returns, generated scores, static synthetic
sector declarations and static relative-liquidity declarations. No external
price/score endpoint is added. Public optional `advanced_inputs` admits bounded
time-varying declared sector/beta/eligibility/liquidity and single-factor returns.
Rows join by `(period, asset_id)` or factor period, not request array order.
Unknown/duplicate keys and contradictory dimensions are rejected. Every exposure
row requires explicit eligibility, liquidity and offset-aware `available_at`.
Missing sectors/betas are not zeros or automatically approved Other labels.
Availability timestamps support at most six fractional-second digits; greater
precision and UTC conversions outside the supported datetime range are refused,
not rounded into the information cutoff.

Synthetic session labels use an explicitly assumed UTC-midnight information
cutoff, not an exchange close/calendar. Scores at t use prices through t;
exposure rows used at t must be available by its cutoff. Trailing beta uses
returns through t (at most beta_window, at least beta_min_observations), against
supplied available factor returns or the explicitly endogenous equal-weight
synthetic-universe return reference. It is not generator latent beta. Missing,
late, zero-variance or out-of-bound beta inputs are excluded/refused explicitly.
Full-sample fits, future liquidity and future normalization are never used.

## Opt-In Policies and Final Holdings

Omitting `advanced_policy` retains the original scanner behavior, including
failed-basket carry and equal-weight long/short baskets. Advanced policy schema
is `scanner_neutralisation_v1`, with modes `dollar`, `sector`, `beta`. Unsupported
combined modes/extra options are rejected. All advanced failed rebalances go to
cash; no previous basket is silently labelled newly verified.

1. Regress eligible current scores on an intercept and exposure columns using
   Phase 59 OLS, with rank policy fail. Sector encoding uses K-1 dummies plus
   intercept; beta uses intercept plus one actual supplied/trailing exposure.
2. Refuse unidentified/ill-conditioned designs (condition >1e8); the adapter
   checks the full intercept design as well as Phase 59's centred-factor block
   so a nearly constant single beta cannot hide behind a factor condition of 1.
   Report rank,
   conditioning, exclusions and reconstruction error. Entirely explained scores
   yield no_signal and zero weights, not useful alpha or amplified residual noise.
3. Rank residual scores with the existing basket selector. Those equal-weight
   baskets are not assumed neutral. Project on the selected support's joint
   constraint nullspace using rank-aware least squares (rcond=1e-12), no inverse.
   Adjustments may change signs, but never introduce previously unselected names.
4. A support whose constraint rank exhausts its number of names is infeasible
   before inspecting numerical residuals, even if its selected betas nearly match.
   A direction below 1e-12 times max(1, original direction norm) is zero/infeasible,
   never normalized to force exposure. Known structural redundancies are encoded
   out; support constraints remain jointly enforced even when redundant.
5. Normalize gross, apply declared gross/volatility cap, then check FINAL dollar,
   sector or beta nets. Tolerance is 1e-9 times max(1,gross); beta is additionally
   scaled by max(1, maximum absolute available beta). Any failed check goes to cash.

Per-rebalance diagnostics distinguish raw basket, residual-score basket,
neutral direction and final scaled holdings, including actual achieved exposures,
state/reason, exclusions, rank, support rank and cost/P&L reconciliation.
Neutrality is at rebalance using available declarations/estimates, not a guarantee
that future realized exposures stay zero. Public diagnostics retain the last 100
rebalances and 20 displayed score rows; validation never uses these previews.
For advanced runs the latest ranking refers to the latest attempted rebalance,
including a zero-weight cash fallback and its current declared sectors. The
legacy ranking continues to refer to its latest successful basket.

## Volatility and Shared P&L

Optional `volatility` declares annual decimal target, trailing window/minimum,
and 252 periods/year. Estimate sample volatility (ddof=1) of trailing asset
returns applied to the proposed fixed weights; this needs no covariance inverse
and can be meaningful with a singular asset covariance. Insufficient observations
or zero/unknown variance produce cash, not infinite leverage or a hidden fallback.
Report requested target, pre-scale estimate, actual scale/cap, achieved ex-ante
estimate and later realized NET volatility separately. Target is not a promise.

Exactly one P&L lag: gross[k] = weights[k-1] dot returns[k]. Turnover[t] is
sum(abs(weights[t]-weights[t-1])); cost is turnover[t]*cost_bps/10000, deducted
once from gross[t+1]. Scaling and cash fallback enter the same turnover kernel.
No borrowed/fill/impact model or terminal liquidation is added. Advanced requests
refuse nonfinite/nonpositive wealth paths instead of presentation-sanitizing them.

## Validation and Statistical Provenance

POST `/scanner/validate` explicitly computes a declared family (1-4 candidates).
Analysis unit is one whole decision-date cross-section, with its feature-start /
feature-end metadata and prediction-to-next-session outcome interval. Assets at
one decision are never split. Actual normalized samples, retained/purged/embargoed
IDs, split fingerprints and recomputed overlap/emptiness audits are returned.

Supported held-out policies are fixed DAILY dollar/sector transformations, no
supervised fit. Current test-date features/declarations may transform scores;
outcome labels cannot fit a policy. Beta/volatility and weekly/monthly validation
stay unavailable with reasons rather than precomputing learned full-sample
returns and calling them OOS. Training parameters are an explicit empty list.

Each contiguous test block starts from cash and charges entry turnover once;
no forced terminal liquidation, matching the scanner finite-horizon convention.
Held-out rows retain actual weights, outcomes and costs. No fictional stitched
wealth or independence assertion for nonadjacent folds. Purged K-fold is a
RETROSPECTIVE audit, not deployable chronological walk-forward performance.

All candidates stay visible; no optimizer or winner selection. Raw supplied p
values remain declared (even when linked to this input/family hash). No supported
inferential test is run and no verified-from-supported-test claim is made.
Empty values stay unavailable; malformed/nonfinite/out-of-range API values are
rejected. Corrections use only valid supplied values for m, while reporting total
declared count, included count, missing IDs and invalid-request policy.
The family fingerprint binds the normalized scanner configuration as well as
the panel, candidate declarations, split configuration, cost and threshold;
changing quantiles, gross exposure or liquidity changes the family identity.
The result fingerprint also binds the complete retained request and outcomes.
Hand fixture: raw [.01,.04,.20], Bonferroni [.03,.12,.60], Holm [.03,.08,.20].
BH assumes independence/PRDS; no universal dependence or investment approval.
PBO/DSR remain unavailable without an implemented scanner trial/selection contract.

## Runbook and Bounds

Use existing Scanner: legacy is default. Select a policy, then Run Scanner.
Load validation parameters only prefills a small universe/date range. Load
declared-p fixture only prefills explicitly synthetic caller declarations.
Validate scanner family executes the actual POST; Download validation JSON saves
only real result state with inline pinned material/caveats. Input edits invalidate
old verdicts; stale/unmounted responses are ignored. No navigation/effect/GET
research, demo seed, provider fallback, DB migration or generic registry.

Advanced: <=50 assets, <=1000 generated sessions, <=1400 calendar days and
2,500,000 date*asset^2 units; <=10000 exposure rows, <=1000 factor rows. Validation:
<=30 assets, <=300 sessions/420 calendar days, 1-4 candidates, 2-5 folds, embargo
0-30 calendar days. Numeric declarations are finite/strict; windows <=252.
Canonical JSON additionally bounds bytes/depth/nodes. SHA-256 integrity is not
truth, financial correctness, data licensing or statistical certification.
Validation and opt-in advanced requests reject unknown options and coerced
numeric Boolean/string inputs. Validation request bodies are bounded before
model parsing and reject duplicate JSON keys. Public errors for these new paths
do not echo submitted values; omitted-option legacy request behavior is preserved.

User-run browser acceptance must use the existing disposable-backend harness and
positive identity proof through the frontend proxy. The new spec refuses a
flag-only or ordinary-backend setup. Discovery does not execute that acceptance.
See [review evidence](PHASE_68_REVIEW.md) for verified fixes and current checks;
[implementation evidence](PHASE_68_IMPLEMENTATION.md) remains historical.
User review commit, exact-commit Python 3.11 CI, user production build and actual
isolated browser acceptance remain pending.
