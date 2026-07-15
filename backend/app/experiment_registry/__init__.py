"""
Research Experiment Registry (Phase 48.0).

A **local-first, single-user** registry that records reproducibility metadata
for QuantLab research runs and presents them in an interactive dashboard.

This package is deliberately separate from :mod:`app.experiments` (the
file-based ML training-run artifact store keyed by ``train_run_hash``).  The
registry here is a broad, SQLite-backed catalogue for *any* module's
deterministic research run — Scenario Studio, KO/PEP Pairs, etc. — and answers:
what was run, with which configuration / dataset / seed / commit, what metrics
came out, did it succeed, and can it be reproduced.

Honest scope: the fingerprints and reproducibility assessment are **integrity
and reproducibility aids only**.  They are not a regulatory audit trail, not
tamper-proof security, and not proof of scientific reproducibility.  Nothing
here is investment, trading, or risk-management advice.
"""

from __future__ import annotations

SCHEMA_VERSION = "experiment_registry_v1"

__all__ = ["SCHEMA_VERSION"]
