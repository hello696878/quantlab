"""
Local continuous futures -> ML pipeline (Phase 9 — commit 1).

``run_local_futures_ml_experiment(store, *, config)`` runs the existing Phase 2-5
ML chain on **already-ingested** local raw futures, using Phase 8's
``build_continuous_from_store`` as the continuous-frame source.  It is the same
flow as ``research_cli.run_es_ml_experiment`` with exactly one difference: the
continuous frame (and its ``continuous_config_hash``) come from the
``RawFuturesStore`` instead of a synthetic generator.  Everything downstream reuses
the existing builders / trainer / evaluator / experiment store verbatim:

    build_continuous_from_store  (Phase 8)
      -> build_feature_matrix        (Phase 2)
      -> build_label_matrix          (Phase 3)
      -> build_supervised_dataset    (Phase 3)
      -> chronological_holdout_split (Phase 4)
      -> train_model                 (Phase 4)
      -> evaluate_ml_signal          (Phase 4)
      -> save_experiment_run         (Phase 5, only if an ExperimentStore is given)

No new ML logic, no new hash, no network, no vendor, no live data.  Nothing is
written unless an ``experiment_store`` is explicitly provided.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.datastore.continuous_build import build_continuous_from_store
from app.datastore.store import RawFuturesStore
from app.experiments import ExperimentStore, best_effort_git_commit, save_experiment_run
from app.features import build_feature_matrix
from app.instruments import get_instrument
from app.labels import build_label_matrix, build_supervised_dataset
from app.ml_signal import (
    chronological_holdout_split,
    dataset_config_hash,
    evaluate_ml_signal,
    train_model,
)
from app.local_pipeline.config import LocalExperimentConfig

__all__ = ["LocalExperimentResult", "run_local_futures_ml_experiment"]


@dataclass(frozen=True)
class LocalExperimentResult:
    """The outcome of one local store-backed experiment: config identity, the full
    raw -> continuous -> feature -> label -> dataset -> model -> train hash chain,
    the Phase 8 provenance, and compact metrics.  ``artifact_dir`` is ``""`` unless
    an ``ExperimentStore`` was provided (then it is the persisted run directory)."""

    root_symbol: str
    source: str
    adjustment_method: str
    train_run_hash: str
    continuous_config_hash: str
    feature_config_hash: str
    label_config_hash: str
    dataset_config_hash: str
    model_config_hash: str
    raw_data_version_hash: str
    contract_version_hashes: dict
    contracts: list
    roll_events: list
    ml_metrics: dict
    backtest_metrics: dict
    baseline_metrics: dict
    artifact_dir: str = ""
    experiment_run: object = None       # app.experiments.ExperimentRun | None
    trained_model: object = None        # app.ml_signal.TrainedModel
    evaluation_result: object = None    # app.ml_signal.MlEvaluationResult


def _run_experiment_from_continuous(
    continuous,
    continuous_config_hash: str,
    instrument,
    cbr,
    *,
    config: LocalExperimentConfig,
    experiment_store: Optional[ExperimentStore],
) -> LocalExperimentResult:
    """The shared continuous -> features -> ... -> save tail (one source of truth).

    ``cbr`` is the Phase 8 ``ContinuousBuildResult`` (for the raw-data provenance).
    Persists a run only when ``experiment_store`` is provided.
    """
    ch = continuous_config_hash

    # Phase 2 / 3: features -> labels -> supervised dataset (with the hash chain).
    features = build_feature_matrix(continuous, upstream_continuous_hash=ch)
    fh = features["feature_config_hash"].iloc[0]
    labels = build_label_matrix(continuous, feature_df=features, upstream_feature_hash=fh)
    lh = labels["label_config_hash"].iloc[0]
    dataset = build_supervised_dataset(features, labels)

    # Phase 4: split (from config windows) -> train -> evaluate (OOS, with baselines).
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
        dataset, config.to_model_spec(), split,
        continuous_config_hash=ch, feature_config_hash=fh, label_config_hash=lh,
        dataset_config_hash_value=ds_hash,
    )
    evaluation = evaluate_ml_signal(
        trained_model, dataset, continuous, instrument,
        start=config.validation_start, end=config.validation_end,
        backtest_kwargs={"transaction_cost_bps": config.transaction_cost_bps},
    )

    # Phase 5: persist only when a store is explicitly provided.
    run = None
    artifact_dir = ""
    if experiment_store is not None:
        run = save_experiment_run(
            trained_model, evaluation, store=experiment_store,
            overwrite=config.overwrite,
            git_commit=best_effort_git_commit(),
            code_version=config.code_version,
            created_at=config.created_at,
        )
        artifact_dir = str(experiment_store.run_dir(run.train_run_hash))

    baselines = {
        "no_trade": dict((evaluation.no_trade_baseline or {}).get("backtest_metrics", {})),
        "momentum": dict((evaluation.momentum_baseline or {}).get("backtest_metrics", {})),
    }
    return LocalExperimentResult(
        root_symbol=config.root_symbol,
        source=config.source,
        adjustment_method=config.adjustment_method,
        train_run_hash=trained_model.train_run_hash,
        continuous_config_hash=ch,
        feature_config_hash=fh,
        label_config_hash=lh,
        dataset_config_hash=ds_hash,
        model_config_hash=trained_model.model_config_hash,
        raw_data_version_hash=cbr.raw_data_version_hash,
        contract_version_hashes=dict(cbr.contract_version_hashes),
        contracts=list(cbr.contracts),
        roll_events=[dict(ev) for ev in cbr.roll_events],
        ml_metrics=dict(evaluation.classification_metrics or evaluation.regression_metrics or {}),
        backtest_metrics=dict(evaluation.backtest_metrics),
        baseline_metrics=baselines,
        artifact_dir=artifact_dir,
        experiment_run=run,
        trained_model=trained_model,
        evaluation_result=evaluation,
    )


def run_local_futures_ml_experiment(
    store: RawFuturesStore | str,
    *,
    config: LocalExperimentConfig,
    experiment_store: Optional[ExperimentStore] = None,
) -> LocalExperimentResult:
    """Run the local store-backed ML pipeline and (optionally) persist one run.

    ``store`` is a ``RawFuturesStore`` (or a base-dir path).  The continuous frame
    is **rebuilt** from the store via Phase 8's ``build_continuous_from_store`` (so
    the ``continuous_config_hash`` is returned directly) — Phase 9 depends only on
    ingested raw data, not on a persisted continuous file.  Nothing is written
    unless ``experiment_store`` is provided.
    """
    if not isinstance(store, RawFuturesStore):
        store = RawFuturesStore(store)

    instrument = get_instrument(config.root_symbol)
    continuous, cbr = build_continuous_from_store(
        store,
        source=config.source,
        root=config.root_symbol,
        adjustment_method=config.adjustment_method,
    )
    return _run_experiment_from_continuous(
        continuous, cbr.continuous_config_hash, instrument, cbr,
        config=config, experiment_store=experiment_store,
    )
