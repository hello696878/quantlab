"""
Deterministic demo runs for the Feature Diagnostics Lab (explicit, idempotent).

Cases (spec §24, covered across four runs):

1. ``demo:fd:heldout-permutation`` — verified held-out permutation importance
   per split of the clean purged+embargo Model Validation demo run, linked to
   the KO/PEP features Dataset Lineage version and an Experiment Registry
   record; contains a stable dominant feature, a correlated pair that splits
   importance, a sign/rank-unstable noise feature, and a feature whose
   distribution drifts between the early and late halves.  Marked baseline
   (a comparison reference — never "recommended").
2. ``demo:fd:importance-drift`` — declared held-out splits over two regimes:
   the ``fade_signal`` feature predicts the target only in the earlier
   period, so importance drifts sharply while its distribution stays put.
   Linked to the verified-OOF Meta-Labeling demo run for context.
3. ``demo:fd:native-tree`` — model-native impurity importance reference
   (decision tree, fitted on all samples — disclosed as not held-out).
4. ``demo:fd:leakage-failed`` — linked to the leakage-failed standard K-fold
   validation demo run; execution fails honestly.

Idempotent via unique ``demo_key``; the Meta-Labeling demo loader (which
cascades Model Validation, Dataset Lineage and Experiment Registry demos, all
idempotent) is seeded first so links have real targets.  Everything is
deterministic; no network, no model files.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from app.dataset_registry.store import version_demo_key_id
from app.feature_diagnostics import service, store
from app.meta_labeling.demo import seed_demo_meta_labeling
from app.meta_labeling.store import run_demo_key_id as meta_demo_id
from app.model_validation.demo import demo_samples
from app.model_validation.store import run_demo_key_id as validation_demo_id

_BASE_R2 = datetime(2025, 2, 3)


def _validation_features() -> List[Dict[str, Any]]:
    """Samples matching the Model Validation demo ids with six deterministic
    features and a target driven by mom_signal (dominant) + the correlated
    pair base value."""
    out = []
    for i, s in enumerate(demo_samples()):
        mom = ((i * 17) % 21 - 10) / 10.0
        base = ((i * 7) % 13 - 6) / 6.0
        corr_a = round(base, 6)
        corr_b = round(base * 0.9 + ((i % 5) - 2) / 40.0, 6)
        flip = ((i * 29) % 17 - 8) / 8.0
        drift = round((((i * 11) % 10) / 10.0) + (0.5 if i >= 30 else 0.0), 6)
        steady = ((i * 5) % 11 - 5) / 5.0
        logit = 2.2 * mom + 1.0 * base + (((i * 31) % 7) - 3) / 10.0
        out.append({
            "sample_id": s["sample_id"],
            "timestamp": s["prediction_time"],
            "features": {
                "mom_signal": round(mom, 6),
                "corr_pair_a": corr_a,
                "corr_pair_b": corr_b,
                "flip_noise": round(flip, 6),
                "drift_feature": drift,
                "steady_noise": round(steady, 6),
            },
            "target": 1 if logit > 0 else 0,
        })
    return out


_R1_DEFS = [
    {"feature_name": "mom_signal", "display_name": "Momentum signal",
     "feature_group": "signal", "source_column": "zscore",
     "description": "dominant deterministic driver in this demo"},
    {"feature_name": "corr_pair_a", "display_name": "Correlated pair A",
     "feature_group": "pair", "source_column": "spread"},
    {"feature_name": "corr_pair_b", "display_name": "Correlated pair B",
     "feature_group": "pair",
     "description": "near-duplicate of corr_pair_a — importance splits"},
    {"feature_name": "flip_noise", "display_name": "Flip noise",
     "feature_group": "noise",
     "description": "unrelated noise — rank and sign are unstable"},
    {"feature_name": "drift_feature", "display_name": "Drifting feature",
     "feature_group": "drift", "source_column": "sentiment_score",
     "description": "level shifts +0.5 in the later half (distribution drift)"},
    {"feature_name": "steady_noise", "display_name": "Steady noise",
     "feature_group": "noise"},
]


def _r2_samples() -> List[Dict[str, Any]]:
    """200 samples in two regimes: fade_signal drives the target only for
    i < 100; filler_a takes over afterwards.  Feature distributions are the
    same generators in both halves (importance drift WITHOUT data drift)."""
    out = []
    for i in range(200):
        fade = ((i * 13) % 19 - 9) / 9.0
        filler_a = ((i * 7) % 11 - 5) / 5.0
        filler_b = ((i * 23) % 15 - 7) / 7.0
        driver = fade if i < 100 else filler_a
        target = 1 if driver > 0 else 0
        if (i * 37) % 17 == 0:  # deterministic label dither
            target = 1 - target
        out.append({
            "sample_id": f"fd2-{i:03d}",
            "timestamp": (_BASE_R2 + timedelta(days=i)).isoformat(),
            "features": {
                "fade_signal": round(fade, 6),
                "filler_a": round(filler_a, 6),
                "filler_b": round(filler_b, 6),
            },
            "target": target,
        })
    return out


_R2_SPLITS = [
    {"split_id": "early-1", "train_sample_ids": [f"fd2-{i:03d}" for i in range(0, 80)],
     "test_sample_ids": [f"fd2-{i:03d}" for i in range(80, 100)]},
    {"split_id": "early-2", "train_sample_ids": [f"fd2-{i:03d}" for i in range(20, 100)],
     "test_sample_ids": [f"fd2-{i:03d}" for i in range(0, 20)]},
    {"split_id": "late-1", "train_sample_ids": [f"fd2-{i:03d}" for i in range(100, 180)],
     "test_sample_ids": [f"fd2-{i:03d}" for i in range(180, 200)]},
    {"split_id": "late-2", "train_sample_ids": [f"fd2-{i:03d}" for i in range(120, 200)],
     "test_sample_ids": [f"fd2-{i:03d}" for i in range(100, 120)]},
]


def _r3_samples() -> List[Dict[str, Any]]:
    out = []
    base = datetime(2025, 4, 7)
    for i in range(120):
        alpha = ((i * 19) % 23 - 11) / 11.0
        beta = ((i * 11) % 13 - 6) / 6.0
        gamma = ((i * 3) % 7 - 3) / 3.0
        target = 1 if (1.8 * alpha + 0.5 * beta + (((i * 41) % 9) - 4) / 12.0) > 0 else 0
        out.append({
            "sample_id": f"fd3-{i:03d}",
            "timestamp": (base + timedelta(days=i)).isoformat(),
            "features": {"x_alpha": round(alpha, 6), "x_beta": round(beta, 6),
                         "x_gamma": round(gamma, 6)},
            "target": target,
        })
    return out


def _r4_samples() -> List[Dict[str, Any]]:
    out = []
    for i, s in enumerate(demo_samples()):
        a = ((i * 17) % 21 - 10) / 10.0
        b = ((i * 5) % 11 - 5) / 5.0
        out.append({
            "sample_id": s["sample_id"],
            "timestamp": s["prediction_time"],
            "features": {"feat_a": round(a, 6), "feat_b": round(b, 6)},
            "target": 1 if a + (((i * 31) % 7) - 3) / 10.0 > 0 else 0,
        })
    return out


def seed_demo_feature_diagnostics() -> Dict[str, int]:
    created = skipped = 0
    seed_demo_meta_labeling()  # idempotent; cascades validation+dataset+experiment demos

    # 1. Verified held-out permutation run (flagship, becomes baseline).
    if store.run_demo_key_id("demo:fd:heldout-permutation") is not None:
        skipped += 1
    else:
        run = service.create_run(
            {
                "name": "Demo — Held-out permutation importance (verified splits)",
                "description": "Permutation importance measured only on the "
                "held-out test members of the clean purged+embargo validation "
                "demo run: a dominant stable feature, a correlated pair that "
                "splits importance, an unstable noise feature, and a feature "
                "whose distribution drifts in the later half.",
                "method": "permutation",
                "model_type": "logistic_regression",
                "target_type": "binary_classification",
                "metric": "log_loss",
                "features": _R1_DEFS,
                "samples": _validation_features(),
                "permutation_repeats": 5,
                "seed": 11,
                "correlation": {"method": "pearson", "threshold": 0.8},
                "drift": {"mode": "early_vs_late", "psi_bins": 8},
                "validation_run_id": validation_demo_id("demo:mv:purged-kfold-embargo"),
                "dataset_version_id": version_demo_key_id("demo:dsv:kopep-features:v1"),
                "notes": "deterministic demo run",
            },
            demo_key="demo:fd:heldout-permutation",
        )
        executed = service.execute_run(run["id"], create_experiment=True)
        if executed["status"] == "completed":
            service.mark_baseline(run["id"])
        created += 1

    # 2. Importance drift without distribution drift (declared splits).
    if store.run_demo_key_id("demo:fd:importance-drift") is not None:
        skipped += 1
    else:
        run = service.create_run(
            {
                "name": "Demo — Importance drift without data drift",
                "description": "fade_signal predicts the target only in the "
                "earlier declared splits; its importance collapses later while "
                "its distribution stays unchanged.",
                "method": "permutation",
                "model_type": "logistic_regression",
                "target_type": "binary_classification",
                "metric": "log_loss",
                "features": [
                    {"feature_name": "fade_signal", "display_name": "Fading signal"},
                    {"feature_name": "filler_a"},
                    {"feature_name": "filler_b"},
                ],
                "samples": _r2_samples(),
                "permutation_repeats": 5,
                "seed": 23,
                "declared_splits": _R2_SPLITS,
                "drift": {"mode": "early_vs_late", "psi_bins": 8},
                "meta_label_run_id": meta_demo_id("demo:ml:verified-oof"),
                "notes": "deterministic demo run",
            },
            demo_key="demo:fd:importance-drift",
        )
        service.execute_run(run["id"])
        created += 1

    # 3. Model-native impurity reference (disclosed as not held-out).
    if store.run_demo_key_id("demo:fd:native-tree") is not None:
        skipped += 1
    else:
        run = service.create_run(
            {
                "name": "Demo — Model-native impurity reference (tree)",
                "description": "Decision-tree impurity importance fitted on all "
                "samples — training-data derived, shown with its caveats and "
                "disclosed as not held-out.",
                "method": "native_impurity",
                "model_type": "decision_tree",
                "target_type": "binary_classification",
                "metric": "log_loss",
                "features": [
                    {"feature_name": "x_alpha"}, {"feature_name": "x_beta"},
                    {"feature_name": "x_gamma"},
                ],
                "samples": _r3_samples(),
                "notes": "deterministic demo run",
            },
            demo_key="demo:fd:native-tree",
        )
        service.execute_run(run["id"])
        created += 1

    # 4. Leakage-failed linked validation run — honest failure.
    if store.run_demo_key_id("demo:fd:leakage-failed") is not None:
        skipped += 1
    else:
        run = service.create_run(
            {
                "name": "Demo — Leakage-failed validation link (honest failure)",
                "description": "Linked to the standard K-fold reference demo "
                "run whose leakage audit failed — execution refuses to produce "
                "held-out importance and records the failure.",
                "method": "permutation",
                "model_type": "logistic_regression",
                "target_type": "binary_classification",
                "metric": "log_loss",
                "features": [{"feature_name": "feat_a"}, {"feature_name": "feat_b"}],
                "samples": _r4_samples(),
                "validation_run_id": validation_demo_id("demo:mv:kfold-reference"),
                "notes": "deterministic demo run",
            },
            demo_key="demo:fd:leakage-failed",
        )
        service.execute_run(run["id"])
        created += 1

    return {"created_runs": created, "skipped_existing": skipped}


__all__ = ["seed_demo_feature_diagnostics"]
