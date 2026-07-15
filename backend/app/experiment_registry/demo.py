"""
Deterministic demo records for the Research Experiment Registry.

Loaded only through an explicit action (the ``POST /demo-seed`` endpoint or the
frontend "Load deterministic demo registry" button) — never silently populated.
Loading is **idempotent**: each record carries a stable ``demo_key`` (a unique
column), so re-seeding creates nothing new and never overwrites or deletes real
records.

The metrics below are *descriptions of what QuantLab's frozen demos produce*
(Scenario Studio severe stress: severity 100/100, 8/8 modules; KO/PEP Pairs:
119 trades, −23.0% vs +112.7%).  They are illustrative registry metadata — this
module does not re-run or modify any quant logic.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.experiment_registry import service, store

# Fixed fixture timestamps so demo durations are deterministic (created_at is
# still the real insertion time — fingerprints never depend on any timestamp).
_T0 = "2026-01-05T09:00:00.000000Z"
_T1 = "2026-01-05T09:00:04.200000Z"


# Ordered parents-first.  ``parent_key`` links a record to an earlier demo_key.
DEMO_SPECS: List[Dict[str, Any]] = [
    {
        "demo_key": "demo:scenario-studio:severe:baseline",
        "parent_key": None,
        "is_baseline": True,
        "payload": {
            "name": "Scenario Studio — Severe Cross-Asset Stress Combo",
            "description": "Deterministic severe systemic stress scenario across all modules.",
            "module": "scenario_studio",
            "experiment_type": "cross_asset_stress",
            "status": "completed",
            "parameters": {"scenario": "severe_cross_asset_stress_combo", "modules": 8},
            "metrics": {"severity_score": 100.0, "modules_triggered": 8, "modules_total": 8},
            "tags": ["demo", "scenario-studio", "stress"],
            "dataset_name": "scenario_studio_fixtures",
            "dataset_version": "v1",
            "dataset_identity": {"scenario_count": 6, "fixture": "scenario_studio_v1"},
            "started_at": _T0,
            "completed_at": _T1,
            "notes": "Baseline severe systemic stress read.",
        },
    },
    {
        "demo_key": "demo:scenario-studio:severe:rerun",
        "parent_key": "demo:scenario-studio:severe:baseline",
        "is_baseline": False,
        "payload": {
            "name": "Scenario Studio — Severe Stress (reproduction run)",
            "description": "Identical configuration and dataset; expected to reproduce the baseline.",
            "module": "scenario_studio",
            "experiment_type": "cross_asset_stress",
            "status": "completed",
            "parameters": {"scenario": "severe_cross_asset_stress_combo", "modules": 8},
            "metrics": {"severity_score": 100.0, "modules_triggered": 8, "modules_total": 8},
            "tags": ["demo", "scenario-studio", "reproduction"],
            "dataset_name": "scenario_studio_fixtures",
            "dataset_version": "v1",
            "dataset_identity": {"scenario_count": 6, "fixture": "scenario_studio_v1"},
            "started_at": _T0,
            "completed_at": _T1,
            "notes": "Reproduction of the severe-stress baseline.",
        },
    },
    {
        "demo_key": "demo:kopep:pairs:baseline",
        "parent_key": None,
        "is_baseline": True,
        "payload": {
            "name": "KO/PEP Pairs — Frozen Deterministic Backtest",
            "description": "Network-free KO/PEP pairs backtest over the pinned demo window.",
            "module": "pairs_backtest",
            "experiment_type": "pairs_trading",
            "status": "completed",
            "parameters": {
                "asset_a": "KO",
                "asset_b": "PEP",
                "start": "2016-07-11",
                "end": "2026-07-11",
                "entry_z": 2.0,
                "exit_z": 0.5,
                "lookback": 60,
            },
            "metrics": {
                "trades": 119,
                "cumulative_return_a_pct": -23.0,
                "cumulative_return_b_pct": 112.7,
            },
            "tags": ["demo", "pairs", "ko-pep"],
            "dataset_name": "ko_pep_fixture",
            "dataset_version": "v1",
            "dataset_identity": {"rows": 2515, "fixture": "ko_pep_pairs_v1"},
            "random_seed": 7,
            "started_at": _T0,
            "completed_at": _T1,
            "notes": "Frozen KO/PEP demo baseline.",
        },
    },
    {
        "demo_key": "demo:macro-regime:baseline-nofp",
        "parent_key": None,
        "is_baseline": True,
        "payload": {
            "name": "Macro Regime — Risk-Off Classification",
            "description": "Deterministic macro-regime classification (dataset identity by name only).",
            "module": "macro_regime",
            "experiment_type": "regime_scan",
            "status": "completed",
            "parameters": {"window": 252, "assets": ["SPY", "TLT", "GLD", "DXY"]},
            "metrics": {"regime": "risk_off", "confidence": 0.82, "components": 4},
            "tags": ["demo", "macro"],
            "dataset_name": "macro_regime_fixture",
            "dataset_version": "v1",
            "random_seed": 11,
            "started_at": _T0,
            "completed_at": _T1,
            "notes": "Macro-regime baseline (no dataset fingerprint available).",
        },
    },
    {
        "demo_key": "demo:macro-regime:rerun-partial",
        "parent_key": "demo:macro-regime:baseline-nofp",
        "is_baseline": False,
        "payload": {
            "name": "Macro Regime — Risk-Off (partial reproduction)",
            "description": "Same configuration, slightly different confidence; dataset fingerprint unavailable.",
            "module": "macro_regime",
            "experiment_type": "regime_scan",
            "status": "completed",
            "parameters": {"window": 252, "assets": ["SPY", "TLT", "GLD", "DXY"]},
            "metrics": {"regime": "risk_off", "confidence": 0.71, "components": 4},
            "tags": ["demo", "macro", "reproduction"],
            "dataset_name": "macro_regime_fixture",
            "dataset_version": "v1",
            "random_seed": 11,
            "started_at": _T0,
            "completed_at": _T1,
            "notes": "Partial reproduction — result differs, dataset fingerprint unavailable.",
        },
    },
    {
        "demo_key": "demo:alt-data:failed",
        "parent_key": None,
        "is_baseline": False,
        "payload": {
            "name": "Alternative Data — Signal Decay (failed load)",
            "description": "Demonstrates a failed run: the fixture failed a checksum during load.",
            "module": "alternative_data",
            "experiment_type": "signal_decay",
            "status": "failed",
            "parameters": {"signal": "news_sentiment", "half_life_days": 5},
            "tags": ["demo", "alt-data", "failed"],
            "dataset_name": "alt_data_fixture",
            "dataset_version": "v1",
            "error_message": "Fixture checksum mismatch during load; run aborted before analysis.",
            "started_at": _T0,
            "completed_at": _T1,
            "notes": "Intentional failed-run demo record.",
        },
    },
]


def seed_demo_registry(*, source: str = "demo_fixture") -> Dict[str, Any]:
    """Idempotently load the demo records.  Existing demo_keys are skipped.

    Returns ``{created, skipped, total, experiment_ids}``.  Never overwrites or
    deletes any record — real records (``demo_key IS NULL``) are untouched, and
    a demo record that already exists is left exactly as it is.
    """
    created = 0
    skipped = 0
    ids: List[int] = []
    key_to_id: Dict[str, int] = {}

    for spec in DEMO_SPECS:
        demo_key = spec["demo_key"]
        existing_id = store.get_id_by_demo_key(demo_key)
        if existing_id is not None:
            key_to_id[demo_key] = existing_id
            ids.append(existing_id)
            skipped += 1
            continue

        parent_key: Optional[str] = spec.get("parent_key")
        parent_id = key_to_id.get(parent_key) if parent_key else None

        payload = dict(spec["payload"])
        if parent_id is not None:
            payload["parent_experiment_id"] = parent_id

        record = service.create_experiment(payload, source=source, demo_key=demo_key)

        if spec.get("is_baseline") and record["status"] == "completed":
            record = service.mark_baseline(record["id"])

        key_to_id[demo_key] = record["id"]
        ids.append(record["id"])
        created += 1

    return {
        "created": created,
        "skipped": skipped,
        "total": created + skipped,
        "experiment_ids": ids,
    }


__all__ = ["DEMO_SPECS", "seed_demo_registry"]
