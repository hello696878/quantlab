"""
Deterministic demo runs for the Regime Diagnostics Lab (explicit, idempotent).

Five runs cover the eleven spec cases:

1. ``demo:rd:volatility-trend`` — 240 daily periods whose market feature has
   a low→high→low volatility structure and alternating drift: a fixed-
   threshold volatility regime (clear transitions), a trend regime, and a
   combined volatility|trend regime; candidate ``allweather`` measures
   similarly across regimes while ``calm-only`` is concentrated in the
   low-volatility state.  Linked to the KO/PEP features dataset version and
   the Phase 53 persistent-signal demo run; recorded in the Experiment
   Registry.
2. ``demo:rd:rank-reversal`` — ``bull-rider`` and ``bear-hedge`` swap ranks
   between upward and downward trend regimes; the neutral band is rare, so
   its statistics are honestly withheld with a low-sample warning.
3. ``demo:rd:training-verified`` — volatility thresholds fitted only on the
   recorded training membership of the clean purged+embargo validation demo
   run's ``purged-fold-0`` split (``verified_from_validation_split``);
   marked baseline (a comparison reference only).
4. ``demo:rd:full-sample-drawdown`` — a full-sample descriptive volatility
   definition (explicitly warned, never leakage-safe) plus a drawdown-state
   definition built from the trailing peak only.
5. ``demo:rd:invalid-centered`` — a user-supplied categorical definition
   whose provenance admits a centered (future-looking) construction: the
   definition is honestly ``invalid`` and unused while a valid volatility
   definition keeps the run alive.

Idempotent via unique ``demo_key``; the Phase 53 demo loader (which cascades
Feature Diagnostics → Meta-Labeling → Model Validation → Dataset Lineage →
Experiment Registry) is seeded first so links have real targets.
Deterministic; no network, no model files.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

import numpy as np

from app.dataset_registry.store import version_demo_key_id
from app.model_validation.demo import demo_samples
from app.model_validation.store import run_demo_key_id as validation_demo_id
from app.overfitting_diagnostics.demo import seed_demo_overfitting
from app.overfitting_diagnostics.store import run_demo_key_id as overfitting_demo_id
from app.regime_diagnostics import service, store

_BASE = datetime(2024, 1, 1)


def _timestamps(n: int, start: datetime = _BASE) -> List[str]:
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


def _vol_trend_market(t: int = 240) -> List[float]:
    """low vol → high vol → low vol, with drift +0.002 in [30,110) and
    −0.002 in [130,210)."""
    rng = np.random.default_rng(54001)
    values = []
    for i in range(t):
        scale = 0.02 if 80 <= i < 160 else 0.005
        drift = 0.002 if 30 <= i < 110 else (-0.002 if 130 <= i < 210 else 0.0)
        values.append(round(float(rng.normal(drift, scale)), 8))
    return values


def _r1_candidates(t: int = 240) -> List[Dict[str, Any]]:
    rng = np.random.default_rng(54002)
    allweather = [round(float(v), 8) for v in rng.normal(0.0018, 0.005, t)]
    calm_only = [round(float(rng.normal(0.003 if not (80 <= i < 160) else -0.002,
                                        0.004)), 8) for i in range(t)]
    return [
        {"candidate_id": "allweather", "name": "All-weather candidate",
         "description": "similar measured outcomes in every regime of this fixture",
         "outcomes": allweather},
        {"candidate_id": "calm-only", "name": "Calm-market candidate",
         "description": "positive only in the low-volatility state of this fixture",
         "outcomes": calm_only},
    ]


def _r2_market(t: int = 200) -> List[float]:
    rng = np.random.default_rng(54003)
    values = []
    for i in range(t):
        drift = 0.003 if (i // 40) % 2 == 0 else -0.003
        values.append(round(float(rng.normal(drift, 0.004)), 8))
    return values


def _r2_candidates(t: int = 200) -> List[Dict[str, Any]]:
    rng = np.random.default_rng(54004)
    up_phase = [(i // 40) % 2 == 0 for i in range(t)]
    bull = [round(float(rng.normal(0.004 if up else -0.003, 0.003)), 8)
            for up in up_phase]
    bear = [round(float(rng.normal(-0.003 if up else 0.004, 0.003)), 8)
            for up in up_phase]
    steady = [round(float(rng.normal(0.0005, 0.002)), 8) for _ in range(t)]
    return [
        {"candidate_id": "bull-rider", "outcomes": bull},
        {"candidate_id": "bear-hedge", "outcomes": bear},
        {"candidate_id": "steady", "outcomes": steady},
    ]


def _r3_market() -> List[float]:
    rng = np.random.default_rng(54005)
    return [round(float(rng.normal(0.0, 0.006 if i < 30 else 0.014)), 8)
            for i in range(60)]


def _r4_market(t: int = 180) -> List[float]:
    """A deterministic mid-series drawdown: drift up, crash, recover."""
    rng = np.random.default_rng(54006)
    values = []
    for i in range(t):
        if 60 <= i < 90:
            drift = -0.012
        elif i >= 90:
            drift = 0.004
        else:
            drift = 0.002
        values.append(round(float(rng.normal(drift, 0.006)), 8))
    return values


def seed_demo_regime_diagnostics() -> Dict[str, int]:
    created = skipped = 0
    seed_demo_overfitting()  # idempotent; cascades every other registry demo

    if store.run_demo_key_id("demo:rd:volatility-trend") is not None:
        skipped += 1
    else:
        t = 240
        run = service.create_run(
            {
                "name": "Demo — Volatility + trend + combined regimes",
                "description": "A low→high→low volatility market with "
                "alternating drift: the all-weather candidate measures "
                "similarly across regimes while the calm-market candidate is "
                "concentrated in the low-volatility state. Fixed causal "
                "thresholds; visible regime transitions.",
                "frequency": "daily",
                "timestamps": _timestamps(t),
                "candidates": _r1_candidates(t),
                "market_features": {"mkt_return": _vol_trend_market(t)},
                "definitions": [
                    {"definition_id": "vol", "name": "Volatility (fixed)",
                     "dimension": "volatility", "source_feature": "mkt_return",
                     "lookback": 20, "lag": 1, "threshold_mode": "fixed",
                     "thresholds": [0.008, 0.015]},
                    {"definition_id": "trend", "name": "Trend (fixed)",
                     "dimension": "trend", "source_feature": "mkt_return",
                     "lookback": 40, "lag": 1, "threshold_mode": "fixed",
                     "thresholds": [-0.0008, 0.0008]},
                    {"definition_id": "vol-x-trend", "name": "Volatility × trend",
                     "dimension": "combined", "sources": ["vol", "trend"]},
                ],
                "transition_window": 5,
                "dataset_version_id": version_demo_key_id("demo:dsv:kopep-features:v1"),
                "overfitting_run_id": overfitting_demo_id("demo:od:persistent-signal"),
                "notes": "deterministic demo run",
            },
            demo_key="demo:rd:volatility-trend",
        )
        service.execute_run(run["id"], create_experiment=True)
        created += 1

    if store.run_demo_key_id("demo:rd:rank-reversal") is not None:
        skipped += 1
    else:
        t = 200
        run = service.create_run(
            {
                "name": "Demo — Rank reversal across trend regimes",
                "description": "bull-rider and bear-hedge swap ranks between "
                "upward and downward regimes; the neutral band is rare and its "
                "statistics are honestly withheld.",
                "frequency": "daily",
                "timestamps": _timestamps(t, datetime(2024, 9, 2)),
                "candidates": _r2_candidates(t),
                "market_features": {"mkt_return": _r2_market(t)},
                "definitions": [
                    {"definition_id": "trend", "name": "Trend (fixed)",
                     "dimension": "trend", "source_feature": "mkt_return",
                     "lookback": 20, "lag": 1, "threshold_mode": "fixed",
                     "thresholds": [-0.0003, 0.0003], "min_observations": 12},
                ],
                "notes": "deterministic demo run",
            },
            demo_key="demo:rd:rank-reversal",
        )
        service.execute_run(run["id"])
        created += 1

    if store.run_demo_key_id("demo:rd:training-verified") is not None:
        skipped += 1
    else:
        samples = demo_samples()
        run = service.create_run(
            {
                "name": "Demo — Training-only verified thresholds",
                "description": "Volatility thresholds fitted only on the "
                "recorded training membership of the clean purged+embargo "
                "validation run's purged-fold-0 split — "
                "verified_from_validation_split integrity.",
                "frequency": "daily",
                "timestamps": [s["prediction_time"] for s in samples],
                "candidates": [
                    {"candidate_id": "linked-strategy",
                     "outcomes": [round(0.001 * (((i * 7) % 9) - 4), 8)
                                  for i in range(len(samples))]},
                    {"candidate_id": "counter-strategy",
                     "outcomes": [round(0.001 * (4 - ((i * 7) % 9)), 8)
                                  for i in range(len(samples))]},
                ],
                "market_features": {"mkt_return": _r3_market()},
                "sample_ids": [s["sample_id"] for s in samples],
                "definitions": [
                    {"definition_id": "vol-train", "name": "Volatility (training-fitted)",
                     "dimension": "volatility", "source_feature": "mkt_return",
                     "lookback": 10, "lag": 1,
                     "threshold_mode": "training_quantile",
                     "quantiles": [0.33, 0.67],
                     "threshold_split_label": "purged-fold-0",
                     "min_observations": 4},
                ],
                "validation_run_id": validation_demo_id("demo:mv:purged-kfold-embargo"),
                "notes": "deterministic demo run",
            },
            demo_key="demo:rd:training-verified",
        )
        executed = service.execute_run(run["id"])
        if executed["status"] == "completed" \
                and executed["invalid_definition_count"] == 0:
            service.mark_baseline(run["id"])
        created += 1

    if store.run_demo_key_id("demo:rd:full-sample-drawdown") is not None:
        skipped += 1
    else:
        t = 180
        rng = np.random.default_rng(54007)
        run = service.create_run(
            {
                "name": "Demo — Full-sample descriptive + drawdown state",
                "description": "The volatility thresholds here are fitted on "
                "the FULL sample — descriptive only, never leakage-safe (the "
                "warning is the point). The drawdown state uses the trailing "
                "peak only.",
                "frequency": "daily",
                "timestamps": _timestamps(t, datetime(2025, 2, 3)),
                "candidates": [
                    {"candidate_id": "single-strategy",
                     "outcomes": [round(float(v), 8)
                                  for v in rng.normal(0.0006, 0.007, t)]},
                ],
                "market_features": {"mkt_return": _r4_market(t)},
                "definitions": [
                    {"definition_id": "vol-full", "name": "Volatility (full-sample)",
                     "dimension": "volatility", "source_feature": "mkt_return",
                     "lookback": 20, "lag": 1,
                     "threshold_mode": "full_sample_quantile",
                     "quantiles": [0.33, 0.67]},
                    {"definition_id": "dd-state", "name": "Drawdown state",
                     "dimension": "drawdown", "source_feature": "mkt_return",
                     "lag": 1, "thresholds": [0.05, 0.15]},
                ],
                "notes": "deterministic demo run",
            },
            demo_key="demo:rd:full-sample-drawdown",
        )
        service.execute_run(run["id"])
        created += 1

    if store.run_demo_key_id("demo:rd:invalid-centered") is not None:
        skipped += 1
    else:
        t = 60
        rng = np.random.default_rng(54008)
        run = service.create_run(
            {
                "name": "Demo — Invalid future-looking definition (honest state)",
                "description": "The supplied categorical labels declare a "
                "centered (future-looking) construction — the definition is "
                "honestly invalid and unused; a valid causal volatility "
                "definition keeps the run alive for contrast.",
                "frequency": "daily",
                "timestamps": _timestamps(t, datetime(2025, 8, 4)),
                "candidates": [
                    {"candidate_id": "single-strategy",
                     "outcomes": [round(float(v), 8)
                                  for v in rng.normal(0.0, 0.006, t)]},
                ],
                "market_features": {"mkt_return": [
                    round(float(v), 8) for v in rng.normal(0.0, 0.01, t)]},
                "definitions": [
                    {"definition_id": "future-labels",
                     "name": "Centered labels (invalid)",
                     "dimension": "categorical",
                     "labels_supplied": (["calm"] * 30 + ["stressed"] * 30),
                     "provenance": {"source": "demo fixture",
                                    "causality": "centered",
                                    "description": "labels were computed with a "
                                                   "centered window — future data"}},
                    {"definition_id": "vol-ok", "name": "Volatility (causal)",
                     "dimension": "volatility", "source_feature": "mkt_return",
                     "lookback": 10, "lag": 1, "threshold_mode": "fixed",
                     "thresholds": [0.006, 0.012], "min_observations": 4},
                ],
                "notes": "deterministic demo run",
            },
            demo_key="demo:rd:invalid-centered",
        )
        service.execute_run(run["id"])
        created += 1

    return {"created_runs": created, "skipped_existing": skipped}


__all__ = ["seed_demo_regime_diagnostics"]
