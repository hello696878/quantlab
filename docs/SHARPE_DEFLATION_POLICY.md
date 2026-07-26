# QuantLab — Sharpe Deflation Policy (Phase 53.0)

The exact conventions behind PSR, DSR and Minimum Track Record Length in the
Overfitting Diagnostics Lab (after Bailey & López de Prado).  Companion:
[`BACKTEST_OVERFITTING_DIAGNOSTICS_LAB.md`](BACKTEST_OVERFITTING_DIAGNOSTICS_LAB.md).

## 1. Sharpe convention

`SR̂ = mean(returns) / std(returns, ddof=1)` — per-period, risk-free rate
assumed 0, **sample** standard deviation, minimum 12 observations, zero
volatility → unavailable.  This matches the registry-era `sharpe_like`
convention used across the validation labs.

## 2. Annualization

None, ever, inside the formulas.  `periods_per_year` is an optional caller
declaration used only for display and for converting MinTRL observations
into approximate calendar years.  Nothing is silently annualized.

## 3. Skewness

Population moment estimator: `γ₃ = m₃ / m₂^1.5` (scipy `skew`,
`bias=True`).

## 4. Kurtosis convention

**Non-excess** kurtosis: `γ₄ = m₄ / m₂²`, normal distribution = 3 (scipy
`kurtosis`, `fisher=False`, `bias=True`).  The PSR variance term uses
`(γ₄ − 1) / 4` — stated everywhere the number appears.

## 5. PSR formula

```
PSR(SR*) = Φ( (SR̂ − SR*) · sqrt(T − 1)
              / sqrt( 1 − γ₃·SR̂ + ((γ₄ − 1)/4)·SR̂² ) )
```

T = observation count behind SR̂; Φ = standard normal CDF.  The variance
expansion under the square root must be **positive**, otherwise PSR is
unavailable with the reason ("the distributional assumptions are not
satisfied"); T < 12 → unavailable; T < 30 → a visible small-sample warning.
Output clamped to [0, 1]; never NaN/Infinity.

## 6. Benchmark Sharpe

`benchmark_sharpe` (SR\*) is a validated caller input in [−10, 10]
(default 0) used by the run-level PSR and MinTRL.  DSR uses its own
benchmark (§7) — the two are displayed separately.

## 7. Expected maximum Sharpe approximation

Under a null of zero true Sharpe across K effectively independent trials
whose estimated Sharpes have cross-trial variance V:

```
E[maxSR] ≈ sqrt(V) · ( (1 − γ)·Φ⁻¹(1 − 1/K) + γ·Φ⁻¹(1 − 1/(K·e)) )
γ = 0.5772156649015329  (Euler–Mascheroni)
```

Requires K ≥ 2 (one trial → honestly unavailable with a note) and K ≤
10 000; V comes from the cross-sectional variance (ddof=1) of the defined
candidate Sharpes (needs ≥ 2); V = 0 (identical Sharpes) → E[maxSR] = 0
with an explanatory note.

## 8. DSR formula

`DSR = PSR(SR* = E[maxSR])`, computed for the candidate with the **highest
observed Sharpe** — the value selection bias applies to; this focus is
descriptive, never a recommendation.  All inputs (K raw, K effective, the
policy that produced K, V, E[maxSR]) are displayed with the number.

## 9. Effective trial count

Three explicit policies, always displayed: `raw` (K = candidate count),
`manual` (caller-supplied, bounded to [1, raw] — correlated trials are never
counted above the raw total), or `dependence_adjusted`
(`K_eff = 1 + (K−1)·(1 − mean|ρ|)` from the dependence diagnostics — a
documented conservative interpolation, **approximate, never exact**).
Correlated trials are never claimed to be independent.

## 10. Minimum Track Record Length

```
MinTRL = 1 + (1 − γ₃·SR̂ + ((γ₄ − 1)/4)·SR̂²) · ( z_conf / (SR̂ − SR*) )²
```

z_conf = Φ⁻¹(confidence), confidence validated in (0.5, 0.999].  Result is
in **observations at the stated return frequency** (approximate years only
when `periods_per_year` is declared); requires SR̂ > SR\* and a positive
variance expansion, else unavailable; always finite and positive when
defined (internal identity, tested: PSR at T = MinTRL equals the confidence
level).  No rounding is applied to the observation count.

## 11. Small-sample limitations

Moment estimators (especially kurtosis) are noisy below ~30 observations —
the lab attaches visible warnings rather than suppressing output, and PSR
values from short records should be read as indicative only.

## 12. What PSR/DSR do NOT prove

PSR is **not** the probability that a strategy will be profitable in the
future — it is the probability, under the stated distributional assumptions
and the observed moments, that the true Sharpe exceeds the benchmark.  DSR
is **not** proof against overfitting — it deflates one observed maximum for
one trial-count assumption.  Neither certifies a strategy, and no track
record length guarantees future performance.
