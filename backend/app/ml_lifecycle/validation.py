"""Independent provenance checks, without fitting or executing diagnostics."""

import re

from app.experiments.spec import ExperimentRun
from app.model_validation.engine import audit_split
from app.model_validation.events import normalize_samples

from .identity import canonical, fingerprint, table, timestamp


def _sealed(kind, value):
    excluded = {"hash", "audit"} if kind == "split" else {"hash"}
    if value.get("hash") != fingerprint(kind, {k: v for k, v in value.items() if k not in excluded}):
        raise ValueError(f"{kind} content hash mismatch")


def validate(snapshot, *, allow_demo=False):
    try:
        _validate(snapshot, allow_demo=allow_demo)
    except (KeyError, TypeError, IndexError, AttributeError) as exc:
        raise ValueError("invalid lifecycle artifact structure") from exc


def _validate(snapshot, *, allow_demo=False):
    canonical(snapshot)
    if snapshot.get("schema_version") != 1:
        raise ValueError("unsupported lifecycle schema")
    if snapshot.get("origin") == "experiment_store":
        expected = {"schema_version", "origin", "source", "source_hash", "files", "source_environment",
                    "inspection_environment", "unavailable"}
        if set(snapshot) != expected or snapshot["source_environment"] != {"classification": "unknown"}:
            raise ValueError("legacy import cannot claim historical environment or complete provenance")
        source = snapshot["source"]
        if set(source) != {"metadata", "parameters", "metrics", "tables"}:
            raise ValueError("unsupported ExperimentStore snapshot")
        # Incidental creation time and paths were intentionally removed by importer.
        metadata = ExperimentRun.model_validate({**source["metadata"], "created_at": "2000-01-01T00:00:00Z", "artifact_paths": {}})
        if metadata.schema_version != 1:
            raise ValueError("unsupported source schema")
        if snapshot["source_hash"] != fingerprint("experiment_source", source):
            raise ValueError("source content mismatch")
        if set(source["tables"]) != {"predictions", "signal", "backtest"}:
            raise ValueError("source frames missing")
        for value in source["tables"].values():
            if value.get("keys") != ["timestamp", "root_symbol", "active_contract"] or value != table(**value):
                raise ValueError("source table must be canonical")
        key_sets = []
        for value in source["tables"].values():
            positions = [[c["name"] for c in value["columns"]].index(k) for k in value["keys"]]
            key_sets.append({tuple(row[i] for i in positions) for row in value["rows"]})
        if any(keys != key_sets[0] for keys in key_sets[1:]) or len(key_sets[0]) != metadata.n_oos_rows:
            raise ValueError("source frame alignment/count mismatch")
        if not isinstance(source["parameters"], dict) or not isinstance(source["metrics"], dict):
            raise ValueError("model parameters and metrics must be JSON objects")
        coefficients = source["parameters"].get("coef_")
        if coefficients is not None and (not isinstance(coefficients, list) or len(coefficients) != len(metadata.feature_columns)
                                         or any(type(c) not in (int, float) for c in coefficients)):
            raise ValueError("fitted coefficients must match ordered features")
        if snapshot["unavailable"] != ["feature payload", "exact train/split membership", "verified OOF provenance",
                                       "calibration provenance", "historical training environment"]:
            raise ValueError("legacy provenance gaps cannot be omitted")
        environment = snapshot["inspection_environment"]
        if (set(environment) != {"classification", "python", "libraries", "app_version", "git_commit"}
                or environment["classification"] != "inspection"
                or set(environment["libraries"]) != {"numpy", "scipy", "pandas", "pydantic"}):
            raise ValueError("inspection environment must use the minimal allowlist")
        for name, digest in snapshot["files"].items():
            if not re.fullmatch(r"(?:metadata|model_params|metrics)\.json|(?:predictions|signal|backtest)\.(?:csv|parquet)", name) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                raise ValueError("invalid physical artifact identity")
        return
    if snapshot.get("origin") != "deterministic_demo" or not allow_demo:
        raise ValueError("complete lifecycle registration requires the explicit trusted demo action in v1")
    if snapshot["source"] != table(**snapshot["source"]) or snapshot["source_hash"] != fingerprint("table", snapshot["source"]):
        raise ValueError("source table content mismatch")
    features, samples = snapshot["feature_order"], snapshot["samples"]
    if not features or len(features) != len(set(features)) or not samples:
        raise ValueError("feature order and samples are required")
    normalized = normalize_samples(samples)
    ids = [s["sample_id"] for s in normalized]
    if ids != [s["sample_id"] for s in samples]:
        raise ValueError("samples must be canonically time ordered")
    by_id = dict(zip(ids, samples))
    for sample in samples:
        if not sample.get("features") or len(sample["features"]) != len(features):
            raise ValueError("missing or mismatched feature payload")
        if any(type(v) not in (int, float) for v in sample["features"]):
            raise ValueError("features must be finite numeric values")
        if timestamp(sample["feature_available_at"]) > timestamp(sample["prediction_time"]):
            raise ValueError("features unavailable at decision time")
        if sample["sample_id"] != sample["entity"] + ":" + timestamp(sample["prediction_time"]):
            raise ValueError("sample identity must include exact entity and timestamp")
    splits = {s["hash"]: s for s in snapshot["splits"]}
    models = {m["hash"]: m for m in snapshot["models"]}
    if len(splits) != len(snapshot["splits"]) or len(models) != len(snapshot["models"]):
        raise ValueError("duplicate model/split artifact")
    for split in splits.values():
        _sealed("split", split)
        membership = split["membership"]
        if any(len(v) != len(set(v)) or not set(v) <= set(ids) for v in membership.values()):
            raise ValueError("invalid split sample membership")
        if set(membership) != {"train", "test", "purged", "embargoed"}:
            raise ValueError("split requires retained, test, purged and embargoed membership")
        groups = list(membership.values())
        if any(set(a) & set(b) for i, a in enumerate(groups) for b in groups[i + 1:]):
            raise ValueError("overlapping split membership")
        raw = {k + "_pos": [ids.index(sid) for sid in membership[k]] for k in membership}
        raw.update(split_label=split["role"], purge_reasons={}, embargo_windows=[])
        if not audit_split(normalized, raw, "walk_forward")["valid"]:
            raise ValueError("split fails independent temporal leakage audit")
    for model in models.values():
        _sealed("model", model)
        if model["feature_order"] != features or model["spec"]["feature_columns"] != features:
            raise ValueError("mismatched model feature order")
        split = splits[model["split_hash"]]
        if model["train_ids"] != split["membership"]["train"]:
            raise ValueError("model training membership mismatch")
        if model["training_data_hash"] != fingerprint("training_data", [by_id[s] for s in model["train_ids"]]):
            raise ValueError("training payload mismatch")
        cutoff = max(by_id[s]["evaluation_time"] for s in model["train_ids"])
        if model["training_cutoff"] != cutoff or cutoff >= min(by_id[s]["prediction_time"] for s in split["membership"]["test"]):
            raise ValueError("training outcomes unavailable before predictions")
    seen = set()
    oof, held = set(), set()
    for prediction in snapshot["predictions"]:
        sid = prediction["sample_id"]
        if sid in seen or sid not in by_id:
            raise ValueError("duplicate or unknown prediction sample")
        seen.add(sid)
        model = models[prediction["model_hash"]]
        if sid not in splits[model["split_hash"]]["membership"]["test"]:
            raise ValueError("prediction not generated by its claimed fold")
        if not 0 <= prediction["raw_probability"] <= 1:
            raise ValueError("invalid probability")
        expected_role = "held_out" if model["role"] == "final" else "inner_oof"
        if prediction["role"] != expected_role:
            raise ValueError("false OOF/held-out claim")
        (held if expected_role == "held_out" else oof).add(sid)
    calibration = snapshot["calibration"]
    _sealed("calibration", calibration)
    if set(calibration["fit_ids"]) != oof or not oof or not held or oof & held:
        raise ValueError("calibration must use exactly the eligible inner OOF predictions")
    if max(by_id[s]["evaluation_time"] for s in oof) >= min(by_id[s]["prediction_time"] for s in held):
        raise ValueError("calibration outcomes unavailable before held-out decisions")
    for prediction in snapshot["predictions"]:
        if prediction["role"] == "held_out" and (prediction.get("calibration_hash") != calibration["hash"] or
                                                   not 0 <= prediction.get("calibrated_probability", -1) <= 1):
            raise ValueError("held-out calibration identity mismatch")


def identities(snapshot):
    value = {k: v for k, v in snapshot.items() if k not in ("inspection_environment", "files")}
    result = {"lifecycle": fingerprint("lifecycle", value), "source": snapshot["source_hash"],
              "source_environment": fingerprint("environment", snapshot["source_environment"])}
    for stage in ("specs", "splits", "models", "calibration", "predictions", "evaluation"):
        result[stage] = fingerprint(stage, snapshot[stage]) if stage in snapshot else None
    return result
