"""
Signal Decay, Forecast Horizon, Turnover and Implementation Lag
Diagnostics (v1).

Measures how STORED research signals, scores, probabilities or rankings
relate DESCRIPTIVELY to later outcomes across explicit forecast horizons and
implementation delays.  Everything the lab reports is a measurement of a
supplied sample under a declared timing rule: a correlation is an
association over that sample, a bucket spread is an arithmetic difference of
sample means, and a decay curve is a sequence of such measurements — none of
it is evidence that a relationship will persist.

The lab does NOT prove predictability, prove alpha, guarantee signal
persistence, recommend a horizon, a lag, a threshold or a trade, select a
strategy, size a position, monitor anything live, execute anything, provide
investment advice or certify a signal.  No market or alternative data is
ever fetched: every observation is supplied locally.
"""

EXPORT_SCHEMA_VERSION = "signal_decay_export_v1"

__all__ = ["EXPORT_SCHEMA_VERSION"]
