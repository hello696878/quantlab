"""
Deterministic demo validation runs (explicit, idempotent — never at startup).

Seven runs over a shared deterministic 60-sample series (daily prediction
times, 5-day label horizons → deliberately overlapping information intervals,
deterministic labels/predictions/scores/returns):

1. ``standard K-fold (reference)`` — expected leakage; splits audit invalid.
2. ``walk-forward`` — chronological folds, boundary purge, clean.
3. ``purged K-fold`` — purge only.
4. ``purged K-fold + embargo`` — purge + 3-day embargo, clean.
5. ``CPCV`` — N=5, k=2 (10 combinations), purge + embargo, clean.
6. ``invalid configuration`` — folds > samples; executes to ``failed`` honestly.
7. ``baseline candidate`` — purged K-fold + embargo linked to the Dataset
   Lineage KO/PEP-features demo version and an Experiment Registry record,
   marked baseline.

Idempotent via unique ``demo_key``; re-seeding creates nothing and never
touches real records.  The Dataset Lineage and Experiment Registry demo
loaders (both idempotent) are seeded first so links have real targets.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.dataset_registry.demo import seed_demo_lineage
from app.dataset_registry.store import version_demo_key_id
from app.model_validation import service, store

_BASE = datetime(2025, 1, 6)
_N = 60
_HORIZON_DAYS = 5


def demo_samples() -> List[Dict[str, Any]]:
    """60 deterministic samples with overlapping 5-day label horizons."""
    samples = []
    for i in range(_N):
        pred = _BASE + timedelta(days=i)
        label = 1 if (i * 7) % 10 < 5 else 0
        prediction = 1 if (i * 3) % 10 < 5 else 0
        score = round(0.15 + ((i * 13) % 70) / 100.0, 4)
        ret = round(0.012 * (((i * 11) % 9) - 4) / 4, 6)
        samples.append(
            {
                "sample_id": f"demo-{i:03d}",
                "prediction_time": pred.isoformat(),
                "evaluation_time": (pred + timedelta(days=_HORIZON_DAYS)).isoformat(),
                "label": label,
                "prediction": prediction,
                "score": score,
                "ret": ret,
            }
        )
    return samples


_RUNS: List[Dict[str, Any]] = [
    {
        "demo_key": "demo:mv:kfold-reference",
        "name": "Demo — Standard K-fold (leakage reference)",
        "description": "Reference only: shuffled-free K-fold over overlapping 5-day "
        "label horizons. Training labels overlap the test window, so the "
        "leakage audit marks every fold invalid — this is the expected warning.",
        "method": "standard_kfold",
        "configuration": {"n_folds": 5},
    },
    {
        "demo_key": "demo:mv:walk-forward",
        "name": "Demo — Walk-forward (expanding)",
        "description": "Chronological expanding-window folds with boundary purge.",
        "method": "walk_forward",
        "configuration": {"min_train_size": 20, "test_size": 8},
    },
    {
        "demo_key": "demo:mv:purged-kfold",
        "name": "Demo — Purged K-fold",
        "description": "Interval purge removes training samples overlapping the test window.",
        "method": "purged_kfold",
        "configuration": {"n_folds": 5},
    },
    {
        "demo_key": "demo:mv:purged-kfold-embargo",
        "name": "Demo — Purged K-fold + embargo",
        "description": "Purge plus a 3-day embargo window after each test block.",
        "method": "purged_kfold",
        "configuration": {"n_folds": 5, "embargo": {"mode": "duration_days", "value": 3}},
    },
    {
        "demo_key": "demo:mv:cpcv",
        "name": "Demo — CPCV (5 groups, 2 test groups)",
        "description": "All C(5,2)=10 deterministic test-group combinations, purged + embargoed.",
        "method": "cpcv",
        "configuration": {
            "n_groups": 5,
            "test_groups": 2,
            "embargo": {"mode": "fraction", "value": 0.02},
        },
    },
    {
        "demo_key": "demo:mv:invalid-config",
        "name": "Demo — Invalid configuration (folds > samples)",
        "description": "Deliberately invalid: 20 folds cannot exceed... they do not fit "
        "the 12-sample subset. Executing records an honest failed status.",
        "method": "purged_kfold",
        "configuration": {"n_folds": 20},
        "sample_slice": 12,
    },
    {
        "demo_key": "demo:mv:baseline-candidate",
        "name": "Demo — Baseline candidate (purged + embargo, linked)",
        "description": "Leakage-clean purged K-fold + embargo, linked to the Dataset "
        "Lineage KO/PEP-features demo version; marked as the scope baseline.",
        "method": "purged_kfold",
        "configuration": {"n_folds": 4, "embargo": {"mode": "duration_days", "value": 2}},
        "link_dataset_demo_key": "demo:dsv:kopep-features:v1",
        "mark_baseline": True,
        "create_experiment": True,
    },
]


def seed_demo_validation() -> Dict[str, int]:
    """Idempotently create + execute the seven demo runs."""
    created = 0
    skipped = 0

    # Give links real targets (both loaders are idempotent).
    seed_demo_lineage()

    samples = demo_samples()
    for spec in _RUNS:
        if store.run_demo_key_id(spec["demo_key"]) is not None:
            skipped += 1
            continue
        run_samples = samples[: spec["sample_slice"]] if spec.get("sample_slice") else samples
        dataset_version_id: Optional[int] = None
        if spec.get("link_dataset_demo_key"):
            dataset_version_id = version_demo_key_id(spec["link_dataset_demo_key"])
        run = service.create_run(
            {
                "name": spec["name"],
                "description": spec["description"],
                "method": spec["method"],
                "configuration": spec["configuration"],
                "samples": run_samples,
                "dataset_version_id": dataset_version_id,
                "notes": "deterministic demo validation run",
            },
            demo_key=spec["demo_key"],
            # The invalid-configuration demo must exist so its execution can be
            # recorded as an honest failed run; the public API validates eagerly.
            validate_configuration=not spec.get("sample_slice"),
        )
        executed = service.execute_run(
            run["id"], create_experiment=bool(spec.get("create_experiment"))
        )
        if spec.get("mark_baseline") and executed["status"] == "completed":
            service.mark_baseline(run["id"])
        created += 1

    return {"created_runs": created, "skipped_existing": skipped}


__all__ = ["demo_samples", "seed_demo_validation"]
