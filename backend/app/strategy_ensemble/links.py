"""Read-only, content-pinned links; no inferred source or sample identities."""

from app.dataset_registry import store as datasets
from app.model_validation import store as validation
from app.regime_diagnostics import store as regimes
from .models import RunCreate, timestamp
from .core import aligned, ensemble, matrix_diagnostics, pairwise


def snapshot(request: RunCreate):
    result = {"datasets": {}, "regime": None, "validation": None}
    for d in request.definitions:
        if d.dataset_version_id is None:
            result["datasets"][d.strategy_id] = {"state": "unlinked", "declared_identity": d.dataset_identity}
            continue
        version = datasets.get_version(d.dataset_version_id)
        if version is None or version.get("invalidated_at"):
            raise ValueError("linked dataset version missing or invalidated")
        dataset = datasets.get_dataset(version["dataset_id"])
        result["datasets"][d.strategy_id] = {"state": "linked", "dataset_name": dataset["name"],
                                             **{k: version.get(k) for k in (
            "version_label", "manifest_fingerprint", "content_fingerprint", "schema_fingerprint", "quality_status")}}
    if request.regime:
        run = regimes.get_run(request.regime.run_id)
        if run is None or run["status"] != "completed":
            raise ValueError("regime link requires a completed stored run")
        if run.get("dataset_version_id") and any(d.dataset_version_id != run["dataset_version_id"] for d in request.definitions):
            raise ValueError("regime dataset version must match every linked strategy")
        definition = next((d for d in regimes.list_definitions(run["id"])
                           if d["definition_id"] == request.regime.definition_id), None)
        if definition is None or definition["integrity_status"] == "invalid":
            raise ValueError("regime definition missing or invalid")
        if run["frequency"] != request.definitions[0].frequency:
            raise ValueError("regime frequency differs from return streams")
        if len(run["timestamps"]) != len(definition["assignments"]):
            raise ValueError("regime assignment length mismatch")
        stamps = [timestamp(t) for t in run["timestamps"]]
        if len(set(stamps)) != len(stamps):
            raise ValueError("ambiguous regime timestamps")
        result["regime"] = {"configuration_fingerprint": run["configuration_fingerprint"],
                            "result_fingerprint": run["result_fingerprint"],
                            "definition_fingerprint": definition["definition_fingerprint"],
                            "definition_id": definition["definition_id"],
                            "integrity_status": definition["integrity_status"],
                            "assignments": dict(zip(stamps, definition["assignments"]))}
    if request.validation:
        run = validation.get_run(request.validation.run_id)
        if run is None or run["status"] != "completed" or run["leakage_clean"] is not True:
            raise ValueError("validation link requires a completed leakage-clean run")
        if run.get("dataset_version_id") and any(d.dataset_version_id != run["dataset_version_id"] for d in request.definitions):
            raise ValueError("validation dataset version must match every linked strategy")
        split = next((s for s in validation.list_splits(run["id"])
                      if s["split_label"] == request.validation.split_label), None)
        if split is None or split["status"] != "valid":
            raise ValueError("validation split missing or not valid")
        members = {k: sorted(split[k]) for k in ("train_ids", "test_ids", "purged_ids", "embargoed_ids")}
        groups = list(members.values())
        if any(set(a) & set(b) for i, a in enumerate(groups) for b in groups[i+1:]):
            raise ValueError("validation membership overlaps")
        samples = [{"sample_id": s["sample_id"], "prediction_time": timestamp(s["prediction_time"]),
                    "evaluation_time": timestamp(s["evaluation_time"])} for s in run["samples"]]
        if len({s["prediction_time"] for s in samples}) != len(samples):
            raise ValueError("validation timestamps ambiguous; v1 requires unique prediction times")
        result["validation"] = {"configuration_fingerprint": run["configuration_fingerprint"],
                                "result_fingerprint": run["result_fingerprint"],
                                "split_fingerprint": split["split_fingerprint"],
                                "split_label": split["split_label"], "memberships": members,
                                "samples": sorted(samples, key=lambda s: s["sample_id"])}
    return result


def evaluate(request: RunCreate, links, results):
    streams, keys, _ = aligned(request)
    regime_rows = []
    if links["regime"]:
        assignments = links["regime"]["assignments"]
        labels = {assignments.get(k[0]) for k in keys}
        dd = {(r["period_start"], r["period_end"]): r["drawdown"]
              for r in results["ensemble"]["drawdown"]["periods"]}
        for label in sorted(labels, key=lambda x: str(x)):
            subset = [k for k in keys if assignments.get(k[0]) == label]
            rare = len(subset) < request.analysis.rare_regime_minimum or label is None
            row = {"label": label or "unassigned", "n": len(subset), "rare": rare,
                   "minimum": request.analysis.rare_regime_minimum, "statistics": None,
                   "integrity": links["regime"]["integrity_status"]}
            if not rare:
                values = ensemble(streams, subset, request.policy, request.analysis.tolerance)
                policy = request.analysis.model_copy(update={"pairwise_alignment": "strict_intersection"})
                row["statistics"] = {"mean_return": values["mean_return"],
                                     "volatility_per_period": values["volatility_per_period"],
                                     "contributions": values["contribution_summary"],
                                     "minimum_observed_full_path_drawdown": min(dd[k] for k in subset),
                                     "drawdown_periods": sum(dd[k] < 0 for k in subset),
                                     "pairwise": pairwise(streams, subset, policy, results["strategy_drawdowns"]),
                                     "matrix": matrix_diagnostics(streams, subset, policy)}
            regime_rows.append(row)
    held_out = {"state": "unavailable", "reason": "no stored validation split linked"}
    if links["validation"]:
        link = links["validation"]
        samples = {s["sample_id"]: s for s in link["samples"]}
        by_start = {k[0]: k for k in keys}
        blocks = {}
        for bucket in ("train_ids", "test_ids"):
            subset = []
            for sample_id in link["memberships"][bucket]:
                sample = samples.get(sample_id)
                if sample is None or sample["prediction_time"] not in by_start:
                    raise ValueError("every retained train/test sample must have an exact common return period")
                key = by_start[sample["prediction_time"]]
                if key[1] != sample["evaluation_time"]:
                    raise ValueError("validation evaluation_time must exactly match return period_end")
                if any(stream[key].information_available_at > sample["evaluation_time"] for stream in streams.values()):
                    raise ValueError("validation information interval omits outcome publication delay")
                subset.append(key)
            if not subset:
                raise ValueError("validation train/test membership must be non-empty")
            values = ensemble(streams, sorted(subset), request.policy, request.analysis.tolerance)
            blocks[bucket] = {"sample_ids": link["memberships"][bucket], "n": values["n"],
                              "mean_return": values["mean_return"], "volatility_per_period": values["volatility_per_period"],
                              "drawdown": values["drawdown"], "weights": values["weights"]["effective"]}
        held_out = {"state": "available", "split_label": link["split_label"],
                    "training": blocks["train_ids"], "held_out": blocks["test_ids"],
                    "memberships": link["memberships"], "weights_frozen": True,
                    "full_sample_descriptive": results["ensemble"]["mean_return"],
                    "reason": "Exact stored membership; no fitting, selection or purge/embargo changes."}
    return regime_rows, held_out
