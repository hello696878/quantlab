"""
Signal Ensemble, Redundancy and Combination Diagnostics Lab (Phase 61, v1).

Local-first diagnostics for COMPARING multiple stored signals and evaluating
EXPLICIT, user-configured combination references.  Everything here is
descriptive measurement over supplied, aligned observations:

* pairwise similarity (raw, rank, sign, bucket, tail) with honest
  unavailability for constants, ties and thin overlap;
* matrix-level redundancy (rank, condition number, eigenvalue concentration,
  effective signal count) described as matrix concentration only;
* deterministic combinations (equal weight, user-supplied static weights,
  rank average, majority sign) whose component contributions reconcile
  exactly and whose missing-component handling is an explicit policy;
* evaluation of a combined score through the Phase 60 Signal Decay policies
  (horizons, lags, buckets, turnover, linked Phase 55 costs) side by side
  with its components, plus leave-one-signal-out differences.

It never selects signals, never derives or optimises weights, never picks a
threshold, horizon or lag, never claims a lower correlation proves
independent information, and never provides trading, allocation or
investment advice.  A combination here is a measurement reference, not a
strategy.
"""

EXPORT_SCHEMA_VERSION = "signal_ensemble_export_v1"

__all__ = ["EXPORT_SCHEMA_VERSION"]
