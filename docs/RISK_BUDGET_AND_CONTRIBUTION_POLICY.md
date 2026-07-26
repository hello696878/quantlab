# Risk Budget & Contribution Policy (v1)

Exact formulas and reconciliation rules
(`backend/app/portfolio_diagnostics/risk.py`).

## Risk contributions

For weights w and covariance Σ (per-period):

```
portfolio_variance   = wᵀΣw
portfolio_volatility = sqrt(portfolio_variance)
MCR_i = (Σw)_i / portfolio_volatility      (marginal)
CCR_i = w_i × MCR_i                        (component)
PCR_i = CCR_i / portfolio_volatility       (percentage)
```

Identities verified within documented numerical tolerance whenever
volatility is positive: `Σ CCR_i = portfolio_volatility` and
`Σ PCR_i = 1` (the CCR check scales relatively with volatility; the PCR
check uses a slightly widened absolute tolerance since it shares the
same relative error). A zero-volatility portfolio returns unavailable
contributions with a visible note. Negative contributions in long-short
portfolios (a hedge whose weight and marginal contribution have opposite
signs) remain visible — never forced to zero. Asset ordering is
preserved everywhere.

## Risk-budget diagnostics

Per asset: configured target budget, measured PCR, absolute / signed /
relative differences (relative is None at a zero target), and a neutral
tolerance state (`within configured tolerance` / `outside configured
tolerance` / `unavailable`). Aggregates: max/mean/RMS absolute
deviation, within-tolerance count, the solver's convergence residual,
and both the target-budget and measured-contribution sums. Targets must
be finite, sum to one, and be positive wherever ERC requires positivity.
Unavailable states stay null; a low deviation is a measurement — never a
superiority claim.

## Concentration & diversification

Weight HHI over |w| shares with effective positions = 1/HHI, maximum
|weight| and top-3 |weight| share; risk-contribution HHI over |PCR|
shares (exactly equal to |CCR| shares — the volatility constant cancels)
with effective risk contributors; average / median / maximum pairwise
correlation over the upper triangle (clipped to [−1,1] so floating-point
noise can never report a correlation above one); and the diversification
ratio `Σ_i |w_i| σ_i / portfolio_volatility` — absolute weights are used
so long-short books are handled explicitly, and a zero denominator makes
it unavailable. All values are descriptive: a higher diversification
ratio or lower concentration never guarantees diversification, risk
reduction, or safety, and none of these measures selects a portfolio.
