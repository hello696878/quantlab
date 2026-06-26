"""
Full synthetic Phase 1->5 research pipeline (Phase 6 — commit 2).

``run_es_ml_experiment(config)`` runs the entire flow from synthetic raw ES
futures through training, evaluation, and persistence in the Phase 5 registry:

    generate -> validate -> continuous -> features -> labels -> dataset -> split
    -> train -> evaluate (with no-trade + momentum baselines) -> save.

Synthetic data only; no network; no real-data download; artifacts are written
only under the provided (or resolved) ``ExperimentStore`` base directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.datastore.store import validate_raw_futures
from app.datastore.futures_continuous import (
    build_continuous_futures,
    compute_roll_schedule,
    continuous_config_hash,
)
from app.features import build_feature_matrix
from app.labels import build_label_matrix, build_supervised_dataset
from app.instruments import get_instrument
from app.ml_signal import (
    chronological_holdout_split,
    dataset_config_hash,
    evaluate_ml_signal,
    train_model,
)
from app.experiments import ExperimentStore, best_effort_git_commit, save_experiment_run
from app.research_cli.config import ExperimentConfig, resolve_artifact_base_dir
from app.research_cli.synthetic import generate_synthetic_es_raw


@dataclass(frozen=True)
class ExperimentResult:
    """The outcome of one synthetic experiment run: config, hashes, saved run, and
    compact metrics.  Holds references to the Phase 4/5 objects for inspection."""

    config: ExperimentConfig
    train_run_hash: str
    experiment_run: object          # app.experiments.ExperimentRun
    trained_model: object           # app.ml_signal.TrainedModel
    evaluation_result: object       # app.ml_signal.MlEvaluationResult
    artifact_dir: Path
    continuous_config_hash: str
    feature_config_hash: str
    label_config_hash: str
    dataset_config_hash: str
    model_config_hash: str
    ml_metrics: dict
    backtest_metrics: dict
    baseline_metrics: dict


def run_es_ml_experiment(
    config: ExperimentConfig,
    *,
    store: Optional[ExperimentStore] = None,
) -> ExperimentResult:
    """Run the full synthetic ES ML pipeline and persist it as an experiment run.

    Pass ``store`` to control where artifacts land (tests pass an
    ``ExperimentStore(tmp_path)``); otherwise it is resolved from the config /
    ``QUANTLAB_ARTIFACTS_DIR`` / the default ``artifacts/experiments``."""
    instrument = get_instrument(config.root_symbol)

    # Phase 1: synthetic raw -> validated -> ratio-adjusted continuous.
    raw = generate_synthetic_es_raw(config)
    validate_raw_futures(raw)
    compute_roll_schedule(raw, instrument)  # surfaces off-cycle / unrollable data early
    continuous = build_continuous_futures(raw, instrument, config.adjustment_method)
    ch = continuous_config_hash(raw, instrument, config.adjustment_method)

    # Phase 2 / 3: features -> labels -> supervised dataset (with the hash chain).
    features = build_feature_matrix(continuous, upstream_continuous_hash=ch)
    fh = features["feature_config_hash"].iloc[0]
    labels = build_label_matrix(continuous, feature_df=features, upstream_feature_hash=fh)
    lh = labels["label_config_hash"].iloc[0]
    dataset = build_supervised_dataset(features, labels)

    # Phase 4: split (from config windows) -> train -> evaluate (OOS, with baselines).
    model_spec = config.to_model_spec()
    split = chronological_holdout_split(
        dataset,
        train_start=config.train_start,
        train_end=config.train_end,
        validation_start=config.validation_start,
        validation_end=config.validation_end,
    )
    ds_hash = dataset_config_hash(
        label_config_hash=lh,
        feature_columns=config.feature_columns,
        label_column=config.label_column,
    )
    trained_model = train_model(
        dataset, model_spec, split,
        continuous_config_hash=ch, feature_config_hash=fh, label_config_hash=lh,
        dataset_config_hash_value=ds_hash,
    )
    evaluation = evaluate_ml_signal(
        trained_model, dataset, continuous, instrument,
        start=config.validation_start, end=config.validation_end,
        backtest_kwargs={"transaction_cost_bps": config.transaction_cost_bps},
    )

    # Phase 5: persist.
    if store is None:
        store = ExperimentStore(resolve_artifact_base_dir(config))
    run = save_experiment_run(
        trained_model, evaluation, store=store,
        overwrite=config.overwrite,
        git_commit=best_effort_git_commit(),
        code_version=config.code_version,
        created_at=config.created_at,
    )

    baselines = {
        "no_trade": dict((evaluation.no_trade_baseline or {}).get("backtest_metrics", {})),
        "momentum": dict((evaluation.momentum_baseline or {}).get("backtest_metrics", {})),
    }
    return ExperimentResult(
        config=config,
        train_run_hash=run.train_run_hash,
        experiment_run=run,
        trained_model=trained_model,
        evaluation_result=evaluation,
        artifact_dir=store.run_dir(run.train_run_hash),
        continuous_config_hash=ch,
        feature_config_hash=fh,
        label_config_hash=lh,
        dataset_config_hash=ds_hash,
        model_config_hash=trained_model.model_config_hash,
        ml_metrics=dict(evaluation.classification_metrics or evaluation.regression_metrics or {}),
        backtest_metrics=dict(evaluation.backtest_metrics),
        baseline_metrics=baselines,
    )
