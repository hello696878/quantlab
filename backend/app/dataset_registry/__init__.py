"""
Data Provenance & Dataset Lineage registry (Phase 49.0).

A **local-first, single-user** dataset registry that records dataset identity,
immutable versions, transformation lineage, metadata-driven quality results,
and links to the Experiment Registry — so a research run's data can be
identified, compared, and re-verified later.

Honest scope: provenance records here are metadata the user (or a fixture)
declared, plus deterministic fingerprints over that metadata.  They are
**integrity aids only** — not a regulatory audit trail, not a tamper-proof
ledger, not digital signatures, not proof of authorship or financial
correctness, and not an enterprise data catalog.  Nothing in this package
fetches live data, calls providers, or touches the network.
"""

from __future__ import annotations

EXPORT_SCHEMA_VERSION = "dataset_registry_export_v1"

__all__ = ["EXPORT_SCHEMA_VERSION"]
