# QuantLab — Conditional Performance Policy (Phase 54.0)

Metric conventions for every candidate × regime statistic in the Regime
Diagnostics Lab.  Companion:
[`REGIME_DIAGNOSTICS_LAB.md`](REGIME_DIAGNOSTICS_LAB.md).

## 1. Sample-first presentation

Observation count and coverage are always reported and always more
prominent than any performance statistic — a number never outranks its
sample size.  Coverage = regime observations ÷ periods carrying any label
for the definition; the unassigned-period count is shown alongside.

## 2. Metric conventions

Over the outcome values at periods carrying the regime's effective label:

* mean, median, minimum, maximum — plain sample statistics;
* std — **sample** standard deviation (ddof=1), n ≥ 2;
* positive/negative rates — strict `> 0` / `< 0` fractions;
* cumulative — **compounded** `Π(1+x) − 1` when `outcome_kind = "return"`,
  **summed** otherwise (the input semantics decide, never a guess);
* Sharpe-like — per-period `mean/std(ddof=1)`, risk-free 0, **never
  annualized** (the declared frequency is display metadata; no annualization
  happens without it being explicit);
* downside deviation — `sqrt(Σ min(x,0)² / n)` over all n regime
  observations;
* average regime duration and transition counts come from the effective
  label intervals;
* **maximum drawdown is deliberately omitted** — regime observations are
  generally non-contiguous and concatenating them has no honest drawdown
  semantics (documented limitation, not an oversight).

## 3. Minimum samples and honest unavailability

A regime below the definition's `min_observations` (2–100, default 8)
reports its count and coverage only; every performance statistic is null
with the reason, a low-coverage warning lands on the run, and nothing is
ever zero-substituted.  Zero-dispersion regimes make the Sharpe-like ratio
unavailable with a note.  No NaN or Infinity can leave the API, the
persistence layer, the export, or the frontend.

## 4. Neutral wording

Statistics are measured values under one configuration.  The lab never
describes a regime or candidate as profitable, safe, optimal, best, or
recommended; robustness classifications read as broader or narrower
**measured consistency**; transition rows report **measured before/after
differences**, never effects a regime "caused".

## 5. What conditional performance does NOT establish

Conditioning on a regime is stratification, not causal identification: a
regime label can proxy for anything correlated with it, small regimes carry
wide uncertainty (no significance testing exists in v1), and the same
candidate under a different regime rule may stratify entirely differently.
Conditional statistics inform research questions — they never validate a
strategy, predict a regime, or justify switching anything.
