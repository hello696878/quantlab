"""
Deterministic demo runs for the Meta-Labeling Lab (explicit, idempotent).

Cases: (1) uncalibrated overconfident probabilities; (2) sigmoid-calibrated
(fitted on all → not_out_of_fold, disclosed); (3) isotonic-calibrated;
(4) one-class calibration failure recorded honestly; (5) declared-OOF run;
(6) verified-OOF run calibrated per split of the clean purged+embargo Model
Validation demo run; (7) run linked to the invalidated Dataset Lineage demo
version (warning); plus threshold policies on the verified run showing
coverage trade-offs and one baseline policy.

Idempotent via unique ``demo_key``; the Model Validation and Dataset Lineage
demo loaders (both idempotent) are seeded first so links have real targets.
Everything is deterministic; no network, no model files.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.dataset_registry.store import version_demo_key_id
from app.meta_labeling import service, store
from app.model_validation.demo import seed_demo_validation
from app.model_validation.store import run_demo_key_id as validation_demo_id

_BASE = datetime(2025, 3, 3)


def _overconfident_obs(n: int = 200, *, one_class: bool = False) -> List[Dict[str, Any]]:
    """Deterministic overconfident probabilities: raw prob spreads 0.05–0.95,
    true frequency compressed toward 0.5 (classic overconfidence)."""
    obs = []
    for i in range(n):
        raw_p = 0.05 + 0.9 * ((i * 37) % 100) / 99.0
        true_p = 0.5 + (raw_p - 0.5) * 0.45
        hit = ((i * 61) % 100) / 100.0 < true_p
        side = 1 if i % 3 else -1
        outcome = (0.02 if hit else -0.02) * side
        if one_class:
            outcome = 0.02 * side  # always correct → labels all 1
        pred = _BASE + timedelta(days=i % 60)
        obs.append({
            "sample_id": f"ml-{i:03d}",
            "prediction_time": pred.isoformat(),
            "evaluation_time": (pred + timedelta(days=5)).isoformat(),
            "primary_side": side,
            "raw_probability": round(raw_p, 6),
            "realized_outcome": round(outcome, 6),
        })
    return obs


def _validation_linked_obs() -> List[Dict[str, Any]]:
    """Observations whose ids match the Model Validation demo samples."""
    from app.model_validation.demo import demo_samples

    obs = []
    for i, s in enumerate(demo_samples()):
        raw_p = 0.05 + 0.9 * ((i * 41) % 60) / 59.0
        true_p = 0.5 + (raw_p - 0.5) * 0.5
        hit = ((i * 29) % 60) / 60.0 < true_p
        side = 1 if i % 2 else -1
        obs.append({
            "sample_id": s["sample_id"],
            "prediction_time": s["prediction_time"],
            "evaluation_time": s["evaluation_time"],
            "primary_side": side,
            "raw_probability": round(raw_p, 6),
            "realized_outcome": round((0.015 if hit else -0.015) * side, 6),
        })
    return obs


_RUNS: List[Dict[str, Any]] = [
    {"demo_key": "demo:ml:uncalibrated",
     "name": "Demo — Uncalibrated (overconfident probabilities)",
     "description": "Raw probabilities are systematically overconfident; the "
     "reliability curve departs from the diagonal and ECE is high.",
     "calibration_method": "none"},
    {"demo_key": "demo:ml:sigmoid",
     "name": "Demo — Sigmoid (Platt) calibrated",
     "description": "Platt scaling fitted on all observations — disclosed as "
     "not out-of-fold.",
     "calibration_method": "sigmoid"},
    {"demo_key": "demo:ml:isotonic",
     "name": "Demo — Isotonic calibrated",
     "description": "Isotonic (PAV) calibration fitted on all observations — "
     "disclosed as not out-of-fold.",
     "calibration_method": "isotonic"},
    {"demo_key": "demo:ml:one-class-failure",
     "name": "Demo — One-class calibration failure",
     "description": "Every outcome matches its side, so all meta-labels are 1; "
     "calibration honestly fails (one-class data is unavailable).",
     "calibration_method": "sigmoid", "one_class": True},
    {"demo_key": "demo:ml:declared-oof",
     "name": "Demo — Declared out-of-fold (uncalibrated)",
     "description": "Raw probabilities declared already out-of-fold by the "
     "caller — recorded as a declaration, not independently verified.",
     "calibration_method": "none", "declared": True},
    {"demo_key": "demo:ml:verified-oof",
     "name": "Demo — Verified OOF sigmoid (purged validation splits)",
     "description": "Sigmoid calibrators fitted per split on the clean purged+"
     "embargo validation run's train memberships and applied only to held-out "
     "test observations.",
     "calibration_method": "sigmoid", "link_validation": True},
    {"demo_key": "demo:ml:invalidated-dataset",
     "name": "Demo — Linked to an invalidated dataset version",
     "description": "Run bound to the invalidated alt-sentiment v1 demo dataset "
     "version — the detail shows a visible warning.",
     "calibration_method": "none", "link_invalid_dataset": True},
]

_POLICIES = [
    {"threshold": 0.4, "name": "Coverage-leaning (0.40)"},
    {"threshold": 0.6, "name": "Precision-leaning (0.60)", "baseline": True},
    {"threshold": 0.5, "name": "Abstention band example",
     "abstention": {"lower": 0.45, "upper": 0.55}},
]


def seed_demo_meta_labeling() -> Dict[str, int]:
    created = policies_created = skipped = 0
    seed_demo_validation()  # idempotent; also seeds dataset+experiment demos

    for spec in _RUNS:
        if store.run_demo_key_id(spec["demo_key"]) is not None:
            skipped += 1
            continue
        validation_run_id: Optional[int] = None
        dataset_version_id: Optional[int] = None
        if spec.get("link_validation"):
            validation_run_id = validation_demo_id("demo:mv:purged-kfold-embargo")
            observations = _validation_linked_obs()
        else:
            observations = _overconfident_obs(one_class=bool(spec.get("one_class")))
        if spec.get("link_invalid_dataset"):
            dataset_version_id = version_demo_key_id("demo:dsv:alt-sentiment:v1")
        run = service.create_run(
            {
                "name": spec["name"],
                "description": spec["description"],
                "calibration_method": spec["calibration_method"],
                "observations": observations,
                "declared_out_of_fold": bool(spec.get("declared")),
                "validation_run_id": validation_run_id,
                "dataset_version_id": dataset_version_id,
                "threshold_grid": {"start": 0.0, "end": 1.0, "step": 0.05},
                "notes": "deterministic demo run",
            },
            demo_key=spec["demo_key"],
        )
        executed = service.execute_run(run["id"])
        created += 1
        if spec.get("link_validation") and executed["status"] == "completed":
            for p in _POLICIES:
                policy = service.create_policy(run["id"], {
                    "name": p["name"], "threshold": p["threshold"],
                    "abstention": p.get("abstention"),
                    "notes": "demo threshold policy",
                })
                policies_created += 1
                if p.get("baseline"):
                    service.mark_policy_baseline(policy["id"])

    return {"created_runs": created, "created_policies": policies_created,
            "skipped_existing": skipped}


__all__ = ["seed_demo_meta_labeling"]
