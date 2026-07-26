"""
Purged Cross-Validation, Embargo & CPCV Model Validation Lab (Phase 50.0).

A **local-first** validation lab for time-dependent financial research: it
represents samples as information intervals, generates standard K-fold
(reference only), walk-forward, purged K-fold, and Combinatorial Purged CV
splits, audits every split for temporal leakage, computes neutral fold-level
metrics, and links validation runs to the Experiment Registry and Dataset
Lineage registries.

Interval convention (mirrors ``app.finml.cv``, documented in
docs/PURGED_CV_AND_EMBARGO_POLICY.md): a sample occupies the **closed**
interval ``[prediction_time, evaluation_time]``; two intervals overlap iff
``a.start <= b.end and a.end >= b.start`` — exact boundary contact counts as
overlap (conservative: purges more, never less).

Honest scope: this lab demonstrates and audits split methodology.  It does not
prove a model is profitable or correct, is not scientific certification or
regulatory validation, does not eliminate leakage outside the represented
intervals, and nothing here is investment, trading, or risk advice.
"""

from __future__ import annotations

EXPORT_SCHEMA_VERSION = "model_validation_export_v1"

__all__ = ["EXPORT_SCHEMA_VERSION"]
