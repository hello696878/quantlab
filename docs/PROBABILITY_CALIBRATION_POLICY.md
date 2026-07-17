# Probability Calibration Policy (Phase 51.0)

## Raw vs calibrated probability

A **raw probability** is whatever the caller's primary/secondary model
produced — the lab treats it as an opaque score in [0, 1]. A **calibrated
probability** is that score passed through a mapping fitted so that predicted
probabilities better match observed meta-label frequencies *on the fitting
data*. Both are always preserved side by side.

## OOF fitting requirements

A calibrator must never be fitted on the observations it is evaluated on.
Verified mode fits one calibrator per Model Validation split on that split's
recorded training members and applies it only to the split's held-out test
members; the linked run must be completed and leakage-clean, memberships must
match exactly, and train/test overlap fails the run. Without split evidence,
fitting on all observations is permitted but always labeled
`not_out_of_fold` with a visible warning. A caller's claim that raw
probabilities are already OOF is recorded as `declared_out_of_fold` — a
declaration, never displayed as verified.

## Methods

- **Sigmoid (Platt):** `p' = 1/(1 + exp(A·logit(p) + B))`, A and B fitted by
  Newton–Raphson on the regularized log loss with Platt's smoothed targets
  (guards tiny calibration sets), 100-iteration cap, deterministic. Stored:
  the two floats.
- **Isotonic:** pool-adjacent-violators over (raw, label) pairs sorted by
  probability; prediction interpolates linearly between block centers and
  clamps at the ends. Stored: the block center/value arrays.
- scikit-learn is **not** a project dependency; both methods are small
  deterministic local implementations, and no serialized estimators
  (pickle/joblib) are ever stored or loaded.

## Minimum-data and one-class policy

Fitting requires ≥8 labeled observations containing **both** classes.
One-class data makes calibration unavailable — the run fails honestly with
the reason recorded; nothing is coerced.

## Numerical policy

Probabilities are clipped only by the documented epsilon **1e−6** (for
logits/logs and output bounds). No NaN or Infinity anywhere; undefined
metrics are null with recorded reasons.

## Binning, Brier, log loss, ECE, MCE

Reliability bins: 2–30 bins, equal-width over [0,1] or equal-frequency by
sorted probability; empty bins kept with null statistics. Brier = mean
squared (p − y); log loss uses epsilon-clipped probabilities; ROC AUC is the
rank-based Mann–Whitney statistic; PR AUC is average precision.
**ECE** = Σ (binᵢ count / total) · |mean pᵢ − freqᵢ| over non-empty bins
(count-weighted). **MCE** = max |mean pᵢ − freqᵢ| over non-empty bins.

## What calibration does not prove

Calibration measures the agreement between predicted probabilities and
observed label frequencies on this dataset under this label policy. It does
not prove the underlying signal has value, does not imply profitability
(costs, capacity, regime change, and selection bias are all outside its
scope), does not validate the model scientifically, and a lower Brier score
or ECE is never a trading recommendation.
