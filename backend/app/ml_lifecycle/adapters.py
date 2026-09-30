"""Explicit, whitelisted existing-lab adapters; no filesystem or dynamic imports."""

from app.model_validation import service as validation_service, store as validation_store
from app.model_validation.models import RunCreate as ValidationCreate
from app.meta_labeling import service as calibration_service, store as calibration_store
from app.meta_labeling.models import RunCreate as CalibrationCreate
from app.feature_diagnostics import service as features_service, store as features_store
from app.feature_diagnostics.models import RunCreate as FeaturesCreate
from app.cost_diagnostics import service as costs_service, store as costs_store
from app.cost_diagnostics.models import RunCreate as CostsCreate
from app.signal_decay import service as decay_service, store as decay_store
from app.signal_decay.models import RunCreate as DecayCreate

from .identity import fingerprint

ADAPTERS = {
    "validation": (validation_service, validation_store, ValidationCreate, "model-validation"),
    "calibration": (calibration_service, calibration_store, CalibrationCreate, "meta-labeling"),
    "features": (features_service, features_store, FeaturesCreate, "feature-diagnostics"),
    "costs": (costs_service, costs_store, CostsCreate, "cost-diagnostics"),
    "decay": (decay_service, decay_store, DecayCreate, "signal-decay"),
}


def records(value):
    names = [c["name"] for c in value["columns"]]
    return [dict(zip(names, row)) for row in value["rows"]]


def content(adapter, run_id):
    service, store, _, _ = ADAPTERS[adapter]
    run = service.get_run(run_id)
    if run["status"] != "completed" or run.get("invalidated_at") or run.get("dataset_invalidated"):
        raise ValueError("linked diagnostic is not completed or was invalidated")
    result = {"run": store.get_run(run_id)}
    if adapter == "validation":
        result["splits"] = service.list_splits(run_id)
    elif adapter == "calibration":
        result["observations"] = store.list_observations(run_id, page_size=2000)
        result["bins"] = store.list_bins(run_id)
    elif adapter == "features":
        result.update(results=store.list_results(run_id), splits=store.list_split_results(run_id),
                      groups=store.list_correlation_groups(run_id), drift=store.list_drift_results(run_id))
    elif adapter == "costs":
        result.update(model=store.get_cost_model(run_id), observations=store.list_observation_results(run_id),
                      sensitivity=store.list_sensitivity_results(run_id), capacity=store.list_capacity_results(run_id))
    else:
        result.update(definition=store.get_definition(run_id), observations=store.list_observations(run_id),
                      horizons=store.list_horizons(run_id), buckets=store.list_buckets(run_id),
                      turnover=store.list_turnover(run_id))

    def scientific(value):
        if isinstance(value, dict):
            return {k: scientific(v) for k, v in value.items() if k not in
                    {"id", "run_id", "created_at", "updated_at", "completed_at", "duration_ms", "demo_key"}}
        if isinstance(value, list):
            return [scientific(v) for v in value]
        return value
    return fingerprint("diagnostic:" + adapter, scientific(result))


def payload(adapter, record, links):
    s = record["snapshot"]
    if s["origin"] != "deterministic_demo":
        raise ValueError("legacy import lacks feature/membership provenance; adapter unavailable")
    common = {"name": "ML lifecycle: " + adapter, "dataset_version_id": record["dataset_version_id"]}
    samples = s["samples"]
    by_id = {r["sample_id"]: r for r in samples}
    final = next(p for p in s["splits"] if p["role"] == "final")
    held = [p for p in s["predictions"] if p["role"] == "held_out"]
    if adapter == "validation":
        return {**common, "method": "walk_forward", "configuration": s["validation_plans"]["outer"],
                "samples": [{"sample_id": r["sample_id"], "prediction_time": r["prediction_time"],
                             "evaluation_time": r["evaluation_time"], "group": r["entity"], "label": r["label"],
                             "ret": r["outcome"]} for r in samples],
                "notes": "Exact outer split. Per-model inner OOF memberships are retained in the lifecycle snapshot."}
    if adapter == "calibration":
        return {**common, "calibration_method": "none", "declared_out_of_fold": False,
                "observations": [{"sample_id": p["sample_id"], "prediction_time": by_id[p["sample_id"]]["prediction_time"],
                                  "evaluation_time": by_id[p["sample_id"]]["evaluation_time"], "primary_side": 1,
                                  "raw_probability": p["calibrated_probability"],
                                  "realized_outcome": by_id[p["sample_id"]]["outcome"]} for p in held],
                "notes": "Held-out diagnostics of already-frozen sigmoid probabilities; no refit. Lab raw_probability means adapter input. Not an OOF claim. Inner calibration artifact is retained in lifecycle."}
    if adapter == "features":
        return {**common, "method": "permutation", "model_type": "logistic_regression", "target_type": "binary_classification",
                "metric": "log_loss", "permutation_repeats": 2, "seed": 650,
                "features": [{"feature_name": name} for name in s["feature_order"]],
                "samples": [{"sample_id": r["sample_id"], "timestamp": r["prediction_time"],
                             "features": dict(zip(s["feature_order"], r["features"])),
                             "target": int(r["label"] == 1)} for r in samples],
                "declared_splits": [{"split_id": "outer-held-out", "train_sample_ids": final["membership"]["train"],
                                     "test_sample_ids": final["membership"]["test"]}],
                "notes": "Separate diagnostic logistic refit using actual X/y and outer membership; NOT the stored estimator or model-selection evidence."}
    if adapter == "costs":
        periods = records(s["evaluation"]["periods"])
        observations, previous = [], 0.0
        for row in periods:
            turnover = abs(row["effective_position"] - previous)
            previous = row["effective_position"]
            observations.append({"observation_id": row["timestamp"], "candidate_id": "held-out-policy",
                                 "timestamp": row["timestamp"], "gross_return": row["strategy_return"],
                                 "turnover": turnover, "traded_notional": turnover * 10000,
                                 "metadata": {"actual_net_return": row["net_strategy_return"],
                                              "actual_return_drag": row["transaction_cost"]}})
        return {**common, "observation_type": "period", "observations": observations,
                "commission": {"model": "bps_of_notional", "value": 10},
                "spread": {"model": "none"}, "slippage": {"model": "none"}, "impact": {"model": "none"},
                "notes": "Gross inputs only. Fixed 10000 reference notional; diagnostic linear fees differ from compounded engine drag. Actual net returns are metadata, never charged twice."}
    if "costs" not in links or links["costs"]["status"] != "completed":
        raise ValueError("Signal Decay requires the completed lifecycle cost adapter first")
    prices = records(s["source"])
    return {**common,
            "signal": {"signal_id": "held-out-calibrated-up-probability", "name": "Frozen held-out up probability",
                       "signal_type": "continuous_score", "source": "ml-lifecycle", "unit": "probability",
                       "frequency": "daily", "direction": "higher_is_higher_score",
                       "availability_policy": "explicit_available_at", "transformation": "none", "tie_policy": "average"},
            "outcome": {"outcome_id": "label-horizon", "name": "Declared label return",
                        "target_type": "forward_return", "price_field": "close", "source": "synthetic ratio continuous"},
            "observations": [{"entity_id": by_id[p["sample_id"]]["entity"],
                              "source_timestamp": by_id[p["sample_id"]]["prediction_time"],
                              "available_at": by_id[p["sample_id"]]["prediction_time"],
                              "value": p["calibrated_probability"]} for p in held],
            "prices": [{"entity_id": r["root_symbol"] + ":" + r["active_contract"], "timestamp": r["timestamp"],
                        "close": r["close_adjusted"]} for r in prices],
            "horizons": {"horizons": [1], "unit": "observations", "entry_lags": [1], "overlap_policy": "overlapping"},
            "buckets": {"bucket_count": 3, "scope": "global", "minimum_per_bucket": 2},
            "policy": {"reference_notional": 10000}, "cost_diagnostic_run_id": links["costs"]["destination_id"],
            "notes": "One entity, fixed label horizon; descriptive time-series diagnostics, not cross-sectional alpha. Linked fee assumptions are reference context, not a second charge to stored returns."}


def create(adapter, record, links, key):
    service, store, model, _ = ADAPTERS[adapter]
    existing = store.run_demo_key_id(key)
    if existing:
        return existing
    request = model.model_validate(payload(adapter, record, links)).model_dump(mode="json")
    return service.create_run(request, demo_key=key)["id"]


def execute(adapter, run_id, record):
    service = ADAPTERS[adapter][0]
    if service.get_run(run_id)["status"] != "completed":
        service.execute_run(run_id, create_experiment=False)
    if adapter == "validation":
        splits = service.list_splits(run_id)
        planned = next(s for s in record["snapshot"]["splits"] if s["role"] == "final")["membership"]
        if len(splits) != 1 or any(splits[0][key + "_ids"] != planned[key] for key in ("train", "test", "purged", "embargoed")):
            raise ValueError("destination validation membership differs from fitted model split")
    return content(adapter, run_id)
