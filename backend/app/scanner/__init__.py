"""
Cross-Sectional Scanner Engine v1 — a **second, portfolio-level** backtest engine.

Unlike the single-instrument :mod:`app.backtest` engine (one price series, one
position series), the scanner works on a *universe*:

* a price matrix  (date × asset),
* a signal/score matrix (date × asset),
* a dollar-neutral weight matrix (date × asset),
* and a single portfolio return series.

Each rebalance date it ranks every instrument by a cross-sectional score, forms
equal-weight long/short baskets, dollar-neutralizes them, and runs a vectorized,
**lookahead-safe** portfolio backtest (weights at *t* earn the return from *t* to
*t+1*) net of turnover-based transaction costs.

Educational / research only — **synthetic sample universe**, no live market data,
no real-time scanning, no ML selection, not investment advice.
"""

from app.scanner.cross_sectional import (  # noqa: F401
    STRATEGIES,
    ScannerInputError,
    run_scanner_backtest,
    validate_scanner_inputs,
)
