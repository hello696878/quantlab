"""
Deterministic demo runs for the Overfitting Diagnostics Lab (explicit,
idempotent).

Four runs cover the ten spec cases:

1. ``demo:od:noise-selection`` — 14 pure-noise candidates (fixed-seed
   deterministic generator, no true edge) over 240 periods, S = 8 (70 CSCV
   combinations): the in-sample winner frequently ranks poorly out of sample
   (high estimated PBO); includes a strongly cross-correlated candidate pair,
   nominal p-values where three look small before correction but none survive
   Bonferroni/Holm/BH at alpha = 0.05, and a many-trial DSR deflation of the
   highest observed Sharpe.  Linked to the Feature Diagnostics demo run.
2. ``demo:od:persistent-signal`` — one candidate carries a deterministic
   drift among 7 noise candidates: lower estimated PBO with a more stable OOS
   ranking (never called robust), linked to the KO/PEP features dataset
   version and the clean purged+embargo validation demo run, recorded in the
   Experiment Registry, and marked baseline (a comparison reference only).
3. ``demo:od:constant-short`` — a 28-observation short track record (below
   the 30-observation small-sample threshold, so the warnings are visible),
   a constant-return candidate whose Sharpe
   diagnostics are honestly unavailable, and a manual one-trial policy so DSR
   is unavailable with the one-trial note while PSR stands alone.
4. ``demo:od:invalid-config`` — every candidate constant under
   ``sharpe_like``: every CSCV split is invalid and execution fails honestly.

Idempotent via unique ``demo_key``; the Feature Diagnostics demo loader
(which cascades Meta-Labeling → Model Validation → Dataset Lineage →
Experiment Registry, all idempotent) is seeded first so links have real
targets.  Deterministic; no network, no model files.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np

from app.dataset_registry.store import version_demo_key_id
from app.feature_diagnostics.demo import seed_demo_feature_diagnostics
from app.feature_diagnostics.store import run_demo_key_id as feature_demo_id
from app.model_validation.store import run_demo_key_id as validation_demo_id
from app.overfitting_diagnostics import service, store

_BASE = datetime(2024, 1, 1)


def _timestamps(n: int, start: datetime = _BASE) -> List[str]:
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


def _noise_universe() -> List[Dict[str, Any]]:
    rng = np.random.default_rng(53001)
    t = 240
    candidates: List[Dict[str, Any]] = []
    base = rng.normal(0.0, 0.01, t)
    p_values = {"noise-01": 0.02, "noise-02": 0.03, "noise-03": 0.04,
                "noise-04": 0.30, "noise-05": 0.60, "noise-06": 0.90}
    for i in range(12):
        cid = f"noise-{i + 1:02d}"
        returns = rng.normal(0.0, 0.01, t)
        candidates.append({
            "candidate_id": cid, "name": f"Noise candidate {i + 1}",
            "returns": [round(float(v), 8) for v in returns],
            "nominal_p_value": p_values.get(cid),
            "p_value_provenance": (
                {"source_test": "illustrative declared t-test", "sidedness": "two-sided",
                 "null_hypothesis": "mean daily return equals zero",
                 "sample_count": t,
                 "assumptions": "declared by the demo fixture, not verified"}
                if cid in p_values else None),
        })
    # Strongly cross-correlated pair built from the shared base series.
    wiggle = rng.normal(0.0, 0.003, t)
    candidates.append({"candidate_id": "corr-a", "name": "Correlated pair A",
                       "returns": [round(float(v), 8) for v in base]})
    candidates.append({"candidate_id": "corr-b", "name": "Correlated pair B",
                       "returns": [round(float(v), 8) for v in 0.95 * base + wiggle]})
    return candidates


def _signal_universe() -> List[Dict[str, Any]]:
    rng = np.random.default_rng(53002)
    t = 240
    candidates: List[Dict[str, Any]] = [{
        "candidate_id": "signal-anchor",
        "name": "Persistent drift candidate",
        "description": "deterministic +0.0015/period drift plus noise — the "
                       "one candidate with a built-in edge in this fixture",
        "returns": [round(float(v), 8) for v in rng.normal(0.0015, 0.008, t)],
    }]
    for i in range(7):
        candidates.append({
            "candidate_id": f"drift-noise-{i + 1:02d}",
            "name": f"No-edge candidate {i + 1}",
            "returns": [round(float(v), 8) for v in rng.normal(0.0, 0.008, t)],
        })
    return candidates


def _constant_short_universe() -> List[Dict[str, Any]]:
    rng = np.random.default_rng(53003)
    t = 28  # below the 30-observation small-sample floor → visible warnings
    return [
        {"candidate_id": "flat-fee", "name": "Constant-return candidate",
         "description": "identical return every period — Sharpe diagnostics "
                        "are honestly unavailable",
         "returns": [0.0005] * t},
        {"candidate_id": "short-a", "name": "Short-record candidate A",
         "returns": [round(float(v), 8) for v in rng.normal(0.001, 0.012, t)]},
        {"candidate_id": "short-b", "name": "Short-record candidate B",
         "returns": [round(float(v), 8) for v in rng.normal(0.0, 0.012, t)]},
        {"candidate_id": "short-c", "name": "Short-record candidate C",
         "returns": [round(float(v), 8) for v in rng.normal(-0.0005, 0.012, t)]},
    ]


def seed_demo_overfitting() -> Dict[str, int]:
    created = skipped = 0
    seed_demo_feature_diagnostics()  # idempotent; cascades every other registry demo

    if store.run_demo_key_id("demo:od:noise-selection") is not None:
        skipped += 1
    else:
        run = service.create_run(
            {
                "name": "Demo — 14 noise candidates (selection bias visible)",
                "description": "Every candidate is deterministic noise with no "
                "edge; picking the in-sample winner per CSCV combination shows "
                "how often it lands in the bottom half out of sample. Nominal "
                "p-values look small for three candidates before correction — "
                "none stay below alpha after Bonferroni, Holm, or BH.",
                "metric": "sharpe_like",
                "block_count": 8,
                "timestamps": _timestamps(240),
                "candidates": _noise_universe(),
                "alpha": 0.05,
                "confidence": 0.95,
                "periods_per_year": 252,
                "feature_diagnostics_run_id": feature_demo_id("demo:fd:heldout-permutation"),
                "notes": "deterministic demo run",
            },
            demo_key="demo:od:noise-selection",
        )
        service.execute_run(run["id"])
        created += 1

    if store.run_demo_key_id("demo:od:persistent-signal") is not None:
        skipped += 1
    else:
        run = service.create_run(
            {
                "name": "Demo — One persistent drift among noise (lower PBO)",
                "description": "A single candidate carries a deterministic "
                "drift; the in-sample selection lands on it often and its OOS "
                "rank is more stable, so the estimated selection-overfitting "
                "frequency is lower under this configuration — which is a "
                "property of this fixture, not robustness evidence.",
                "metric": "sharpe_like",
                "block_count": 8,
                "timestamps": _timestamps(240),
                "candidates": _signal_universe(),
                "alpha": 0.05,
                "confidence": 0.95,
                "periods_per_year": 252,
                "dataset_version_id": version_demo_key_id("demo:dsv:kopep-features:v1"),
                "validation_run_id": validation_demo_id("demo:mv:purged-kfold-embargo"),
                "notes": "deterministic demo run",
            },
            demo_key="demo:od:persistent-signal",
        )
        executed = service.execute_run(run["id"], create_experiment=True)
        if executed["status"] == "completed" and executed["invalid_split_count"] == 0:
            service.mark_baseline(run["id"])
        created += 1

    if store.run_demo_key_id("demo:od:constant-short") is not None:
        skipped += 1
    else:
        run = service.create_run(
            {
                "name": "Demo — Short record, constant candidate, one trial",
                "description": "28 observations (small-sample warnings), a "
                "constant-return candidate with honestly unavailable Sharpe "
                "diagnostics, and a manual one-trial policy: DSR is undefined "
                "with a note while PSR stands on its own assumptions.",
                "metric": "mean_return",
                "block_count": 4,
                "timestamps": _timestamps(28, datetime(2025, 6, 2)),
                "candidates": _constant_short_universe(),
                "trial_count_policy": {"mode": "manual", "manual_value": 1},
                "notes": "deterministic demo run",
            },
            demo_key="demo:od:constant-short",
        )
        service.execute_run(run["id"])
        created += 1

    if store.run_demo_key_id("demo:od:invalid-config") is not None:
        skipped += 1
    else:
        t = 48
        run = service.create_run(
            {
                "name": "Demo — Invalid configuration (honest failure)",
                "description": "Every candidate is constant under sharpe_like, "
                "so every CSCV split has undefined metrics — execution refuses "
                "to produce a PBO and records the failure.",
                "metric": "sharpe_like",
                "block_count": 4,
                "timestamps": _timestamps(t, datetime(2025, 9, 1)),
                "candidates": [
                    {"candidate_id": "const-a", "name": "Constant A",
                     "returns": [0.001] * t},
                    {"candidate_id": "const-b", "name": "Constant B",
                     "returns": [0.002] * t},
                ],
                "notes": "deterministic demo run",
            },
            demo_key="demo:od:invalid-config",
        )
        service.execute_run(run["id"])
        created += 1

    return {"created_runs": created, "skipped_existing": skipped}


__all__ = ["seed_demo_overfitting"]
