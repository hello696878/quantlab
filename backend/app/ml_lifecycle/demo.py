"""One explicit synthetic lifecycle, existing estimators and numerical engines only."""

from dataclasses import replace
import json

import numpy as np
import pandas as pd

from app.datastore.futures_continuous import build_continuous_futures, continuous_config_hash
from app.features import build_feature_matrix
from app.features.spec import DEFAULT_ES_FEATURES
from app.instruments import get_instrument
from app.labels import build_label_matrix, build_supervised_dataset
from app.labels.spec import DEFAULT_ES_LABELS
from app.meta_labeling.calibration import apply_sigmoid, fit_sigmoid, probability_metrics
from app.ml_signal import (BaseModel, ModelSpec, PredictionSignalConfig, Split, SplitType,
                           evaluate_ml_signal, predict_model, train_model)
from app.model_validation.engine import audit_split, walk_forward
from app.model_validation.events import normalize_samples

from .identity import environment, fingerprint, table, timestamp

FEATURES = ["feature__return_20", "feature__moving_average_gap_10_50"]
LABEL = "label__direction_1"
DEMO_KEY = "phase65-lifecycle-v1"


def frame_table(frame):
    columns = []
    for name in frame.columns:
        kind = ("timestamp" if name == "timestamp" else "boolean" if frame[name].dtype == bool
                else "number" if pd.api.types.is_numeric_dtype(frame[name]) else "string")
        columns.append({"name": name, "type": kind, "nullable": name in ("roll_reason", "open_interest")})
    rows = []
    for values in frame.itertuples(index=False, name=None):
        row = []
        for value, column in zip(values, columns):
            if column["nullable"] and pd.isna(value):
                row.append(None)
            elif column["type"] == "timestamp":
                value = pd.Timestamp(value)
                value = value.tz_localize("UTC") if value.tzinfo is None else value
                row.append(timestamp(value.isoformat()))
            elif hasattr(value, "item"):
                row.append(value.item())
            else:
                row.append(value)
        rows.append(row)
    return table(columns, rows, ["timestamp", "root_symbol", "active_contract"])


def prepare_demo():
    """Causal features, explicit label intervals, then all splits BEFORE any fit."""
    rng = np.random.default_rng(650)
    n = 220
    dates = pd.bdate_range("2022-01-03", periods=n)
    close = 4000 * np.exp(np.cumsum(0.008 * np.sin(np.arange(n) / 5) + rng.normal(0, .004, n)))
    raw = pd.DataFrame({"timestamp": dates, "open": close, "high": close + 2,
                        "low": close - 2, "close": close, "volume": 1000 + np.arange(n),
                        "open_interest": 2000, "root_symbol": "ES", "contract_symbol": "ESZ22",
                        "expiry": pd.Timestamp("2022-12-16"), "source": "synthetic",
                        "timezone": "America/Chicago"})
    instrument = get_instrument("ES")
    cont = build_continuous_futures(raw, instrument, "ratio")
    dates = pd.DatetimeIndex(cont.timestamp)
    ch = continuous_config_hash(raw, instrument, "ratio")
    feature_specs = [s for s in DEFAULT_ES_FEATURES if "feature__" + s.output_name in FEATURES
                     or s.output_name in FEATURES]
    label_specs = [s for s in DEFAULT_ES_LABELS if s.name in ("direction_1", "forward_return_1")]
    features = build_feature_matrix(cont, specs=feature_specs, upstream_continuous_hash=ch)
    fh = features.feature_config_hash.iloc[0]
    labels = build_label_matrix(cont, specs=label_specs, feature_df=features, upstream_feature_hash=fh)
    lh = labels.label_config_hash.iloc[0]
    ds = build_supervised_dataset(features, labels)
    # Availability comes from trailing features, not future label values. The final
    # two decision rows are reserved price context for the declared label horizon.
    ds = ds.loc[(~ds.is_warmup) & (ds.timestamp <= dates[-3])].reset_index(drop=True)
    label_end = {timestamp(pd.Timestamp(d).isoformat()):
                 timestamp(pd.Timestamp(dates[i + 2]).isoformat())
                 for i, d in enumerate(dates[:-2])}
    samples = []
    for row in ds.to_dict("records"):
        stamp = timestamp(pd.Timestamp(row["timestamp"]).isoformat())
        samples.append({"sample_id": f"{row['root_symbol']}:{row['active_contract']}:{stamp}",
                        "prediction_time": stamp, "feature_available_at": stamp,
                        "evaluation_time": label_end[stamp], "entity": f"{row['root_symbol']}:{row['active_contract']}",
                        "features": [float(row[c]) for c in FEATURES], "label": float(row[LABEL]),
                        "outcome": float(row["label__forward_return_1"])})
    outer_config = {"min_train_size": len(samples) - 32, "test_size": 32, "purge": True,
                    "embargo": {"mode": "duration_days", "value": 2}}
    normalized = normalize_samples(samples)
    outer = walk_forward(normalized, outer_config)[0]
    inner_samples = [samples[p] for p in outer["train_pos"]]
    inner_config = {"min_train_size": 60, "test_size": 24, "purge": True,
                    "embargo": {"mode": "duration_days", "value": 2}}
    inner = walk_forward(normalize_samples(inner_samples), inner_config)
    return {"cont": cont, "ds": ds, "samples": samples, "outer": outer, "inner": inner,
            "outer_config": outer_config, "inner_config": inner_config,
            "hashes": {"continuous_config_hash": ch, "feature_config_hash": fh, "label_config_hash": lh},
            "specs": {"features": [s.model_dump(mode="json") for s in feature_specs],
                      "labels": [s.model_dump(mode="json") for s in label_specs]}}


class FrozenCalibration(BaseModel):
    """Runtime-only composition of existing predict/apply functions, never serialized code."""
    is_classifier = True

    def __init__(self, model, parameters):
        self.model, self.parameters = model, parameters

    def predict_proba(self, X):
        return np.asarray(apply_sigmoid(self.parameters, self.model.predict_proba(X)))

    def predict(self, X):
        return (self.predict_proba(X) >= .5).astype(float)

    def fit(self, X, y, sample_weight=None):
        raise ValueError("frozen calibration cannot be fitted")

    @property
    def params(self):
        return self.model.params


def fit_snapshot(prepared):
    ds, samples = prepared["ds"], prepared["samples"]
    outer = prepared["outer"]
    by_id = {s["sample_id"]: i for i, s in enumerate(samples)}
    plans, models, predictions = [], [], []
    inner_samples = [samples[p] for p in outer["train_pos"]]

    def fit(raw_split, population, role):
        normalized = normalize_samples(population)
        audit = audit_split(normalized, raw_split, "walk_forward")
        if not audit["valid"]:
            raise ValueError("demo split failed independent leakage audit")
        membership = {key: [normalized[p]["sample_id"] for p in raw_split[pos]] for key, pos in
                      (("train", "train_pos"), ("test", "test_pos"), ("purged", "purged_pos"), ("embargoed", "embargoed_pos"))}
        plan = {"role": role, "membership": membership, "audit": audit}
        plan["hash"] = fingerprint("split", {"role": role, "membership": membership})
        plans.append(plan)
        train = [by_id[sid] for sid in membership["train"]]
        test = [by_id[sid] for sid in membership["test"]]
        spec = ModelSpec(model_name="phase65-synthetic-logistic", model_type="logistic_regression",
                         task_type="classification", feature_columns=FEATURES, label_column=LABEL,
                         train_start=ds.timestamp.iloc[min(train)].date(), train_end=ds.timestamp.iloc[max(train)].date(),
                         validation_start=ds.timestamp.iloc[min(test)].date(), validation_end=ds.timestamp.iloc[max(test)].date(),
                         prediction_horizon=1, random_seed=650, hyperparameters={"C": 1.0},
                         long_threshold=.5, short_threshold=.5)
        trained = train_model(ds, spec, Split(SplitType.WALK_FORWARD, np.array(train), np.array(test)), **prepared["hashes"])
        params = {k: v.tolist() if isinstance(v, np.ndarray) else v.item() if isinstance(v, np.generic) else v
                  for k, v in trained.fitted_params.items()}
        if params.get("converged_") is False:
            raise ValueError("demo logistic fit did not converge")
        artifact = {"role": role, "split_hash": plan["hash"], "spec": spec.model_dump(mode="json"),
                    "feature_order": FEATURES, "parameters": params, "train_ids": membership["train"],
                    "training_data_hash": fingerprint("training_data", [samples[i] for i in train]),
                    "training_cutoff": max(samples[i]["evaluation_time"] for i in train),
                    "train_run_hash": trained.train_run_hash, "model_config_hash": trained.model_config_hash,
                    "dataset_config_hash": trained.dataset_config_hash}
        artifact["hash"] = fingerprint("model", artifact)
        models.append(artifact)
        prediction = predict_model(trained, ds.iloc[test].copy())
        # Full timestamp + instrument matching, never row matching independently sorted frames.
        keyed = {(pd.Timestamp(r.timestamp).isoformat(), r.root_symbol, r.active_contract): r for r in prediction.itertuples()}
        for i in test:
            r = ds.iloc[i]
            p = keyed[(pd.Timestamp(r.timestamp).isoformat(), r.root_symbol, r.active_contract)]
            predictions.append({"sample_id": samples[i]["sample_id"], "role": "held_out" if role == "final" else "inner_oof",
                                "model_hash": artifact["hash"], "raw_probability": float(p.prediction_proba)})
        return trained

    for split in prepared["inner"]:
        fit(split, inner_samples, split["split_label"])
    calibration_ids = [p["sample_id"] for p in predictions]
    probs = np.array([p["raw_probability"] for p in predictions])
    y = np.array([samples[by_id[sid]]["label"] == 1 for sid in calibration_ids], dtype=float)
    calibration = {"method": "sigmoid", "fit_ids": calibration_ids,
                   "input_hash": fingerprint("calibration_inputs", predictions),
                   "parameters": fit_sigmoid(probs, y), "threshold": .5,
                   "meaning": "P(direction_1 == +1); long primary side, outcome threshold zero",
                   "score_role": "calibration_fit"}
    calibration["hash"] = fingerprint("calibration", calibration)
    final = fit(outer, samples, "final")
    held = [p for p in predictions if p["role"] == "held_out"]
    calibrated = apply_sigmoid(calibration["parameters"], [p["raw_probability"] for p in held])
    for p, probability in zip(held, calibrated):
        p["calibrated_probability"] = float(probability)
        p["calibration_hash"] = calibration["hash"]
    frozen = replace(final, model=FrozenCalibration(final.model, calibration["parameters"]))
    result = evaluate_ml_signal(frozen, ds, prepared["cont"], get_instrument("ES"),
                               start=final.spec.validation_start, end=final.spec.validation_end,
                               prediction_config=PredictionSignalConfig(require_trainable=False),
                               backtest_kwargs={"transaction_cost_bps": 10},
                               include_momentum_baseline=False, include_no_trade_baseline=False)
    evaluation_frame = frame_table(result.ml_backtest.frame)
    held_y = np.array([samples[by_id[p["sample_id"]]]["label"] == 1 for p in held], dtype=float)
    evaluation = {"role": "held_out", "metrics": result.backtest_metrics,
                  "raw_probability_metrics": probability_metrics([p["raw_probability"] for p in held], held_y),
                  "calibrated_probability_metrics": probability_metrics(calibrated, held_y),
                  "periods": evaluation_frame, "signals": frame_table(result.signals),
                  "policy": {"target": "unshifted", "execution_lag": 1, "cost_bps": 10,
                             "label_price_interval": "close[t+1] to close[t+2]",
                             "return_interval": "position[t] * return(close[t-1], close[t])",
                             "note": "Label horizon and one-lag trading evaluation are distinct; no second signal shift."}}
    source_table = frame_table(prepared["cont"])
    snapshot = {"schema_version": 1, "origin": "deterministic_demo", "source": source_table,
                "source_hash": fingerprint("table", source_table), "upstream_hashes": prepared["hashes"],
                "source_environment": environment("source"), "feature_order": FEATURES,
                "specs": prepared["specs"], "samples": samples, "splits": plans, "models": models,
                "calibration": calibration, "predictions": predictions, "evaluation": evaluation,
                "validation_plans": {"outer": prepared["outer_config"], "inner": prepared["inner_config"]},
                "unavailable": []}
    def numeric(value):
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.generic):
            return value.item()
        raise TypeError("unsupported demo artifact scalar")
    return json.loads(json.dumps(snapshot, default=numeric, allow_nan=False))
