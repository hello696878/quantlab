"""
Phase 4 — commit 1: ModelSpec, provenance hashes, and split utilities.

Synthetic data only; no network; no model training (those land in later commits).
"""

import inspect
import re
from datetime import date

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from app.instruments import get_instrument
from app.ml_signal import (
    BaseModel,
    DummyBaseline,
    LogisticRegression,
    MlEvaluationResult,
    MlSignalError,
    ModelSpec,
    ModelType,
    PredictionSignalConfig,
    RidgeRegression,
    SignalMode,
    Split,
    SplitType,
    TaskType,
    ThresholdRule,
    TrainedModel,
    build_model,
    chronological_holdout_split,
    classification_metrics,
    dataset_config_hash,
    evaluate_ml_signal,
    model_config_hash,
    predict_model,
    prediction_to_signal,
    purged_kfold_splits,
    regression_metrics,
    select_design_matrix,
    train_model,
    train_run_hash,
    walk_forward_splits,
)

ES = get_instrument("ES")


def _spec(**over) -> ModelSpec:
    base = dict(
        model_name="es_dir_logit",
        model_type=ModelType.LOGISTIC_REGRESSION,
        task_type=TaskType.CLASSIFICATION,
        feature_columns=("feature__return_20", "feature__moving_average_gap_10_50"),
        label_column="label__direction_1",
        train_start=date(2024, 1, 1),
        train_end=date(2024, 6, 30),
        validation_start=date(2024, 7, 1),
        validation_end=date(2024, 12, 31),
        prediction_horizon=1,
        random_seed=7,
    )
    base.update(over)
    return ModelSpec(**base)


def _frame(n: int = 120, start: str = "2024-01-01") -> pd.DataFrame:
    ts = pd.date_range(start, periods=n, freq="B")
    return pd.DataFrame({"timestamp": ts, "x": np.arange(n)})


# --------------------------------------------------------------------------- #
# ModelSpec validation
# --------------------------------------------------------------------------- #


def test_valid_model_spec_creation():
    s = _spec()
    assert s.model_type is ModelType.LOGISTIC_REGRESSION
    assert s.task_type is TaskType.CLASSIFICATION
    assert s.feature_columns == ("feature__return_20", "feature__moving_average_gap_10_50")
    assert s.signal_mode is SignalMode.LONG_FLAT          # default
    assert s.threshold_rule is ThresholdRule.PROB_THRESHOLD


def test_feature_columns_reject_label_column():
    with pytest.raises(ValidationError):
        _spec(feature_columns=("feature__return_20", "label__direction_1"))


def test_feature_columns_require_feature_prefix():
    with pytest.raises(ValidationError):
        _spec(feature_columns=("return_20",))


def test_feature_columns_must_be_nonempty():
    with pytest.raises(ValidationError):
        _spec(feature_columns=())


def test_feature_columns_reject_duplicates():
    with pytest.raises(ValidationError):
        _spec(feature_columns=("feature__a", "feature__a"))


def test_label_column_requires_label_prefix():
    with pytest.raises(ValidationError):
        _spec(label_column="direction_1")


def test_invalid_date_ordering_fails():
    # validation_start not after train_end
    with pytest.raises(ValidationError):
        _spec(validation_start=date(2024, 6, 1))
    # train_start not before train_end
    with pytest.raises(ValidationError):
        _spec(train_start=date(2024, 1, 1), train_end=date(2023, 12, 31))


def test_prediction_horizon_must_be_positive():
    with pytest.raises(ValidationError):
        _spec(prediction_horizon=0)


def test_sklearn_model_types_rejected():
    for bad in ("random_forest", "gradient_boosting", "xgboost"):
        with pytest.raises(ValidationError):
            _spec(model_type=bad)


def test_unknown_field_forbidden():
    with pytest.raises(ValidationError):
        _spec(foo=1)


def test_model_spec_is_frozen():
    s = _spec()
    with pytest.raises(ValidationError):
        s.random_seed = 9


# --------------------------------------------------------------------------- #
# Hashes
# --------------------------------------------------------------------------- #


def test_model_config_hash_stable_and_sensitive():
    s = _spec()
    assert model_config_hash(s) == model_config_hash(_spec())          # stable
    assert len(model_config_hash(s)) == 64                              # full sha256 hex
    assert model_config_hash(s) != model_config_hash(_spec(random_seed=8))
    assert model_config_hash(s) != model_config_hash(
        _spec(feature_columns=("feature__return_20",))
    )
    assert model_config_hash(s) != model_config_hash(
        _spec(
            model_type=ModelType.RIDGE_REGRESSION,
            task_type=TaskType.REGRESSION,
            label_column="label__forward_return_1",
        )
    )


def test_dataset_config_hash_stable_and_sensitive():
    base = dict(
        label_config_hash="L",
        feature_columns=("feature__a", "feature__b"),
        label_column="label__direction_1",
    )
    h = dataset_config_hash(**base)
    assert h == dataset_config_hash(**base)                              # stable
    assert len(h) == 64
    # order-insensitive on feature_columns (sorted internally)
    assert h == dataset_config_hash(
        label_config_hash="L",
        feature_columns=("feature__b", "feature__a"),
        label_column="label__direction_1",
    )
    assert h != dataset_config_hash(**{**base, "label_config_hash": "L2"})
    assert h != dataset_config_hash(**{**base, "label_column": "label__direction_5"})
    assert h != dataset_config_hash(**{**base, "drop_warmup": True})


def test_train_run_hash_chains_all_upstream_hashes():
    base = dict(
        continuous_config_hash="C",
        feature_config_hash="F",
        label_config_hash="L",
        dataset_config_hash="D",
        model_config_hash="M",
    )
    h = train_run_hash(**base)
    assert h == train_run_hash(**base)                                   # stable
    assert len(h) == 64
    for key in base:                                                     # sensitive to each link
        assert h != train_run_hash(**{**base, key: base[key] + "x"})


# --------------------------------------------------------------------------- #
# Chronological holdout
# --------------------------------------------------------------------------- #


def test_chronological_holdout_train_before_validation_and_disjoint():
    df = _frame(120, "2024-01-01")
    sp = chronological_holdout_split(
        df,
        train_start=date(2024, 1, 1),
        train_end=date(2024, 3, 31),
        validation_start=date(2024, 4, 1),
        validation_end=date(2024, 6, 30),
    )
    assert sp.split_type is SplitType.CHRONOLOGICAL_HOLDOUT
    assert set(sp.train_index).isdisjoint(set(sp.test_index))
    ts = df["timestamp"].to_numpy()
    assert ts[sp.train_index].max() < ts[sp.test_index].min()           # train strictly before test
    assert sp.train_index.size > 0 and sp.test_index.size > 0


def test_chronological_invalid_ordering_raises():
    df = _frame(50)
    with pytest.raises(MlSignalError):
        chronological_holdout_split(
            df,
            train_start=date(2024, 1, 1),
            train_end=date(2024, 6, 1),
            validation_start=date(2024, 5, 1),   # overlaps train
            validation_end=date(2024, 7, 1),
        )


def test_chronological_embargo_removes_latest_train_rows():
    df = _frame(120, "2024-01-01")
    kw = dict(
        train_start=date(2024, 1, 1),
        train_end=date(2024, 3, 31),
        validation_start=date(2024, 4, 1),
        validation_end=date(2024, 6, 30),
    )
    a = chronological_holdout_split(df, **kw, embargo_bars=0)
    b = chronological_holdout_split(df, **kw, embargo_bars=5)
    assert b.train_index.size == a.train_index.size - 5
    removed = set(a.train_index) - set(b.train_index)
    assert removed == set(a.train_index[-5:])                           # the 5 latest train rows
    assert set(b.train_index).isdisjoint(set(b.test_index))


# --------------------------------------------------------------------------- #
# Walk-forward
# --------------------------------------------------------------------------- #


def test_walk_forward_ordered_and_disjoint():
    df = _frame(100)
    folds = walk_forward_splits(df, n_splits=3, train_span=40, test_span=15, embargo_bars=2)
    assert len(folds) == 3
    ts = df["timestamp"].to_numpy()
    last_test_max_pos = -1
    for f in folds:
        assert f.split_type is SplitType.WALK_FORWARD
        assert set(f.train_index).isdisjoint(set(f.test_index))
        assert ts[f.train_index].max() < ts[f.test_index].min()         # train before test
        assert int(f.test_index.min()) > last_test_max_pos              # test blocks ordered
        last_test_max_pos = int(f.test_index.max())


def test_walk_forward_rolling_uses_fixed_train_span():
    df = _frame(100)
    folds = walk_forward_splits(df, n_splits=2, train_span=30, test_span=15, mode="rolling")
    assert len(folds) == 2
    for f in folds:
        assert f.train_index.size == 30


def test_walk_forward_embargo_gap_between_train_and_test():
    df = _frame(100)
    folds = walk_forward_splits(df, n_splits=2, train_span=40, test_span=15, embargo_bars=4)
    for f in folds:
        # gap of exactly embargo_bars positions between last train and first test
        assert int(f.test_index.min()) - int(f.train_index.max()) == 4 + 1


# --------------------------------------------------------------------------- #
# Purged K-fold + embargo (delegates to app.finml.cv)
# --------------------------------------------------------------------------- #


def test_purged_kfold_disjoint_and_no_overlap_after_purge():
    df = _frame(120)
    folds = purged_kfold_splits(df, n_splits=4, execution_lag=1, horizon=5, embargo_bars=3)
    assert len(folds) == 4
    for f in folds:
        assert set(f.train_index).isdisjoint(set(f.test_index))
        assert f.diagnostics["purged_overlap_count_after_purge"] == 0
    # a standard (unpurged) K-fold would have leaked on at least one fold
    assert any(f.diagnostics["standard_train_overlap_count"] > 0 for f in folds)


def test_purged_kfold_embargo_removes_adjacent_events():
    df = _frame(120)
    no_emb = purged_kfold_splits(df, n_splits=4, execution_lag=1, horizon=3, embargo_bars=0)
    emb = purged_kfold_splits(df, n_splits=4, execution_lag=1, horizon=3, embargo_bars=10)
    assert sum(f.diagnostics["embargoed_count"] for f in no_emb) == 0
    assert sum(f.diagnostics["embargoed_count"] for f in emb) > 0
    for f in emb:
        assert set(f.train_index).isdisjoint(set(f.embargoed_index))


def test_purged_kfold_respects_event_mask():
    df = _frame(120)
    mask = np.ones(120, dtype=bool)
    mask[:20] = False  # e.g. warmup rows are not labeled events
    folds = purged_kfold_splits(
        df, n_splits=4, execution_lag=1, horizon=5, embargo_bars=2, event_mask=mask
    )
    used = set()
    for f in folds:
        used |= set(f.train_index) | set(f.test_index)
        used |= set(f.purged_index) | set(f.embargoed_index)
    assert used.isdisjoint(set(range(20)))             # masked-out rows never used


def test_splits_deterministic():
    df = _frame(120)
    a = purged_kfold_splits(df, n_splits=4, execution_lag=1, horizon=5, embargo_bars=3)
    b = purged_kfold_splits(df, n_splits=4, execution_lag=1, horizon=5, embargo_bars=3)
    for fa, fb in zip(a, b):
        assert np.array_equal(fa.train_index, fb.train_index)
        assert np.array_equal(fa.test_index, fb.test_index)
    wa = walk_forward_splits(df, n_splits=3, train_span=40, test_span=15)
    wb = walk_forward_splits(df, n_splits=3, train_span=40, test_span=15)
    for fa, fb in zip(wa, wb):
        assert np.array_equal(fa.train_index, fb.train_index)
        assert np.array_equal(fa.test_index, fb.test_index)


# --------------------------------------------------------------------------- #
# Hygiene: no network, no sklearn, synthetic only
# --------------------------------------------------------------------------- #


def test_no_network_or_sklearn_imports_in_sources():
    import app.ml_signal.spec as spec_mod
    import app.ml_signal.splits as splits_mod
    import app.ml_signal.models as models_mod
    import app.ml_signal.training as training_mod
    import app.ml_signal.prediction as prediction_mod
    import app.ml_signal.evaluation as evaluation_mod

    for mod in (spec_mod, splits_mod, models_mod, training_mod, prediction_mod, evaluation_mod):
        src = inspect.getsource(mod)
        # no network client imports, and no ML-framework imports (the words may
        # appear in prose saying we deliberately avoid them, so match imports only)
        assert not re.search(r"\bimport (requests|urllib|http|socket|aiohttp|httpx)\b", src)
        assert not re.search(r"\b(import|from)\s+sklearn\b", src)
        assert not re.search(r"\b(import|from)\s+(xgboost|lightgbm|torch|tensorflow)\b", src)


# --------------------------------------------------------------------------- #
# Commit 2 — models + training
# --------------------------------------------------------------------------- #


def _ds(n: int = 200, seed: int = 0) -> pd.DataFrame:
    """Synthetic supervised-dataset-like frame (no pipeline / no network)."""
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2024-01-01", periods=n, freq="B")
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    y_reg = 2.0 * x1 - 1.0 * x2 + 0.5                     # exact linear (ridge target)
    y_dir = np.where(3.0 * x1 - 2.0 * x2 > 0, 1.0, -1.0)  # separable binary (logistic target)
    return pd.DataFrame(
        {
            "timestamp": ts,
            "root_symbol": "ES",
            "active_contract": "ESH24",
            "feature__x1": x1,
            "feature__x2": x2,
            "label__forward_return_1": y_reg,
            "label__direction_1": y_dir,
            "is_warmup": False,
            "is_label_valid": True,
            "is_trainable": True,
        }
    )


def _reg_spec(**over) -> ModelSpec:
    base = dict(
        model_name="ridge_reg",
        model_type=ModelType.RIDGE_REGRESSION,
        task_type=TaskType.REGRESSION,
        feature_columns=("feature__x1", "feature__x2"),
        label_column="label__forward_return_1",
        train_start=date(2024, 1, 1),
        train_end=date(2024, 6, 30),
        validation_start=date(2024, 7, 1),
        validation_end=date(2024, 12, 31),
        prediction_horizon=1,
        random_seed=0,
        hyperparameters={"alpha": 1e-8},
    )
    base.update(over)
    return ModelSpec(**base)


def _clf_spec(**over) -> ModelSpec:
    base = dict(
        model_name="logit_dir",
        model_type=ModelType.LOGISTIC_REGRESSION,
        task_type=TaskType.CLASSIFICATION,
        feature_columns=("feature__x1", "feature__x2"),
        label_column="label__direction_1",
        train_start=date(2024, 1, 1),
        train_end=date(2024, 6, 30),
        validation_start=date(2024, 7, 1),
        validation_end=date(2024, 12, 31),
        prediction_horizon=1,
        random_seed=0,
        hyperparameters={"C": 1.0},
    )
    base.update(over)
    return ModelSpec(**base)


def _holdout(n_train: int, n: int) -> Split:
    return Split(SplitType.CHRONOLOGICAL_HOLDOUT, np.arange(n_train), np.arange(n_train, n))


_HASHES = dict(continuous_config_hash="C", feature_config_hash="F", label_config_hash="L")


# --- models (unit) ---


def test_dummy_classification_predicts_majority_class():
    y = np.array([1.0, 1.0, 1.0, -1.0, -1.0])     # majority +1
    m = DummyBaseline(TaskType.CLASSIFICATION).fit(np.zeros((5, 2)), y)
    assert np.all(m.predict(np.zeros((3, 2))) == 1.0)
    assert isinstance(m, BaseModel)


def test_dummy_regression_predicts_train_mean():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    m = DummyBaseline(TaskType.REGRESSION).fit(np.zeros((4, 1)), y)
    assert np.allclose(m.predict(np.zeros((2, 1))), 2.5)


def test_ridge_recovers_linear_relationship():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(400, 2))
    y = 2.0 * X[:, 0] - 1.0 * X[:, 1] + 0.5
    m = RidgeRegression(alpha=1e-8).fit(X, y)
    assert np.allclose(m.params["coef_"], [2.0, -1.0], atol=1e-3)
    assert np.isclose(m.params["intercept_"], 0.5, atol=1e-3)


def test_ridge_deterministic():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(100, 3))
    y = rng.normal(size=100)
    a = RidgeRegression(alpha=1.0).fit(X, y)
    b = RidgeRegression(alpha=1.0).fit(X, y)
    assert np.allclose(a.params["coef_"], b.params["coef_"])
    assert np.allclose(a.predict(X), b.predict(X))


def test_logistic_fits_separable_binary():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(300, 2))
    y = np.where(3.0 * X[:, 0] - 2.0 * X[:, 1] > 0, 1.0, -1.0)
    m = LogisticRegression(C=1.0).fit(X, y)
    acc = (m.predict(X) == (y == 1.0)).mean()
    assert acc > 0.9
    assert m.params["coef_"][0] > 0 and m.params["coef_"][1] < 0    # sign of [3, -2]


def test_logistic_deterministic():
    rng = np.random.default_rng(3)
    X = rng.normal(size=(120, 2))
    y = (X[:, 0] - X[:, 1] > 0).astype(float)
    a = LogisticRegression(C=0.5).fit(X, y)
    b = LogisticRegression(C=0.5).fit(X, y)
    assert np.allclose(a.params["coef_"], b.params["coef_"])
    assert np.allclose(a.predict_proba(X), b.predict_proba(X))


def test_logistic_predict_proba_in_unit_interval():
    rng = np.random.default_rng(2)
    X = rng.normal(size=(50, 2))
    y = (X[:, 0] > 0).astype(float)
    p = LogisticRegression().fit(X, y).predict_proba(X)
    assert p.shape == (50,)
    assert np.all(p >= 0.0) and np.all(p <= 1.0)


def test_logistic_maps_directional_labels_up_vs_rest():
    rng = np.random.default_rng(4)
    X = rng.normal(size=(200, 2))
    y = np.where(X[:, 0] > 0.3, 1.0, np.where(X[:, 0] < -0.3, -1.0, 0.0))  # {-1, 0, 1}
    m = LogisticRegression().fit(X, y)        # accepted: up(+1) vs rest, no raise
    p = m.predict_proba(X)
    assert np.all((p >= 0.0) & (p <= 1.0))


def test_logistic_rejects_non_directional_labels():
    X = np.zeros((6, 2))
    y = np.array([0.0, 1.0, 2.0, 0.0, 1.0, 2.0])   # contains 2 -> not in {-1, 0, 1}
    with pytest.raises(MlSignalError):
        LogisticRegression().fit(X, y)


def test_build_model_maps_each_type():
    assert isinstance(build_model(_reg_spec()), RidgeRegression)
    assert isinstance(build_model(_clf_spec()), LogisticRegression)
    assert isinstance(
        build_model(_reg_spec(model_type=ModelType.DUMMY_BASELINE)), DummyBaseline
    )


# --- training (integration) ---


def test_select_design_matrix_rejects_label_feature():
    df = _ds(20)
    with pytest.raises(MlSignalError):
        select_design_matrix(df, ("feature__x1", "label__direction_1"), "label__forward_return_1")


def test_train_model_selects_only_feature_columns():
    df = _ds(120)
    df["feature__unused"] = 999.0      # extra columns the spec does not name
    df["label__other"] = 123.0
    tm = train_model(df, _reg_spec(), _holdout(80, 120), **_HASHES)
    assert tm.feature_columns == ("feature__x1", "feature__x2")
    assert tm.metadata["n_features"] == 2
    assert tm.model.params["coef_"].shape == (2,)
    assert isinstance(tm, TrainedModel)


def test_train_model_uses_only_train_split_rows():
    df = _ds(200)
    split = _holdout(150, 200)
    tm1 = train_model(df, _reg_spec(), split, **_HASHES)
    poisoned = df.copy()
    poisoned.loc[150:, "label__forward_return_1"] = 999.0   # rows OUTSIDE the train split
    poisoned.loc[150:, "feature__x1"] = -777.0
    tm2 = train_model(poisoned, _reg_spec(), split, **_HASHES)
    assert np.allclose(tm1.model.params["coef_"], tm2.model.params["coef_"])
    assert np.isclose(tm1.model.params["intercept_"], tm2.model.params["intercept_"])


def test_train_model_rejects_untrainable_train_rows():
    df = _ds(200)
    df.loc[10, "is_trainable"] = False     # an untrainable row inside the train split
    with pytest.raises(MlSignalError):
        train_model(df, _reg_spec(), _holdout(150, 200), **_HASHES)


def test_train_model_rejects_nan_in_training():
    df = _ds(120)
    df.loc[5, "feature__x1"] = np.nan      # NaN in a train row
    with pytest.raises(MlSignalError):
        train_model(df, _reg_spec(), _holdout(80, 120), **_HASHES)


def test_train_model_does_not_mutate_dataset():
    df = _ds(120)
    before = df.copy(deep=True)
    train_model(df, _reg_spec(), _holdout(80, 120), **_HASHES)
    pd.testing.assert_frame_equal(df, before)


def test_train_model_metadata_contains_all_hashes():
    tm = train_model(_ds(120), _reg_spec(), _holdout(80, 120), **_HASHES)
    md = tm.metadata
    for key in (
        "continuous_config_hash", "feature_config_hash", "label_config_hash",
        "dataset_config_hash", "model_config_hash", "train_run_hash",
        "model_type", "random_seed", "train_start", "train_end",
        "n_train_rows", "n_features",
    ):
        assert key in md
    assert md["n_train_rows"] == 80
    assert md["n_features"] == 2
    assert md["model_type"] == "ridge_regression"
    assert tm.train_run_hash == md["train_run_hash"]
    assert tm.model_config_hash == md["model_config_hash"]


def test_train_run_hash_changes_when_upstream_changes():
    df = _ds(120)
    split = _holdout(80, 120)
    a = train_model(df, _reg_spec(), split, **_HASHES)
    b = train_model(df, _reg_spec(), split,
                    continuous_config_hash="C2", feature_config_hash="F", label_config_hash="L")
    assert a.train_run_hash != b.train_run_hash


def test_train_model_deterministic_params_and_predictions():
    df = _ds(160)
    split = _holdout(110, 160)
    for spec in (_reg_spec(), _clf_spec()):
        a = train_model(df, spec, split, **_HASHES)
        b = train_model(df, spec, split, **_HASHES)
        assert a.train_run_hash == b.train_run_hash
        x_test = df.loc[split.test_index, list(spec.feature_columns)].to_numpy(dtype=float)
        assert np.allclose(a.model.predict(x_test), b.model.predict(x_test))
        assert np.allclose(a.fitted_params["coef_"], b.fitted_params["coef_"])


# --------------------------------------------------------------------------- #
# Commit 3 — prediction-to-signal adapter
# --------------------------------------------------------------------------- #


class _StubModel:
    """A model whose predictions are prescribed, for exact threshold-mapping tests."""

    def __init__(self, *, pred, proba=None, is_classifier=False):
        self._pred = np.asarray(pred, dtype=float)
        self._proba = None if proba is None else np.asarray(proba, dtype=float)
        self.is_classifier = is_classifier

    def predict(self, X):
        return self._pred[: len(X)]

    def predict_proba(self, X):
        if self._proba is None:
            raise NotImplementedError
        return self._proba[: len(X)]


def _trained(model, spec: ModelSpec) -> TrainedModel:
    return TrainedModel(
        model=model,
        spec=spec,
        feature_columns=tuple(spec.feature_columns),
        label_column=spec.label_column,
        train_index=np.array([], dtype=int),
        fitted_params={},
        model_config_hash="m",
        dataset_config_hash="d",
        train_run_hash="t",
        metadata={},
    )


def _pred_ds(n: int = 4, start: str = "2024-07-01") -> pd.DataFrame:
    ts = pd.date_range(start, periods=n, freq="B")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "root_symbol": "ES",
            "active_contract": "ESH24",
            "feature__x1": np.zeros(n),
            "feature__x2": np.zeros(n),
            "is_warmup": False,
            "is_trainable": True,
        }
    )


def _all_long_tm(n: int) -> TrainedModel:
    spec = _clf_spec(
        threshold_rule=ThresholdRule.PROB_THRESHOLD,
        long_threshold=0.5,
        signal_mode=SignalMode.LONG_FLAT,
    )
    return _trained(_StubModel(pred=np.ones(n), proba=np.ones(n), is_classifier=True), spec)


# --- threshold rules ---


def test_classification_long_flat_threshold():
    df = _pred_ds(4)
    proba = [0.7, 0.5, 0.9, 0.55]
    spec = _clf_spec(threshold_rule=ThresholdRule.PROB_THRESHOLD,
                     long_threshold=0.6, signal_mode=SignalMode.LONG_FLAT)
    tm = _trained(_StubModel(pred=(np.array(proba) >= 0.5).astype(float),
                             proba=proba, is_classifier=True), spec)
    sig = prediction_to_signal(tm, df)
    assert sig["target_position"].tolist() == [1.0, 0.0, 1.0, 0.0]
    assert sig["signal_state"].tolist() == ["long", "flat", "long", "flat"]
    assert "prediction_proba" in sig.columns


def test_classification_long_short_threshold():
    df = _pred_ds(4)
    proba = [0.7, 0.5, 0.3, 0.6]
    spec = _clf_spec(threshold_rule=ThresholdRule.PROB_THRESHOLD,
                     long_threshold=0.6, short_threshold=0.4, signal_mode=SignalMode.LONG_SHORT)
    tm = _trained(_StubModel(pred=(np.array(proba) >= 0.5).astype(float),
                             proba=proba, is_classifier=True), spec)
    sig = prediction_to_signal(tm, df)
    assert sig["target_position"].tolist() == [1.0, 0.0, -1.0, 1.0]


def test_regression_long_flat_threshold():
    df = _pred_ds(4)
    spec = _reg_spec(threshold_rule=ThresholdRule.RETURN_THRESHOLD,
                     long_threshold=0.5, signal_mode=SignalMode.LONG_FLAT)
    tm = _trained(_StubModel(pred=[0.6, 0.4, 1.0, -0.5], is_classifier=False), spec)
    sig = prediction_to_signal(tm, df)
    assert sig["target_position"].tolist() == [1.0, 0.0, 1.0, 0.0]
    assert "prediction_proba" not in sig.columns


def test_regression_long_short_threshold():
    df = _pred_ds(4)
    spec = _reg_spec(threshold_rule=ThresholdRule.RETURN_THRESHOLD,
                     long_threshold=0.5, short_threshold=0.5, signal_mode=SignalMode.LONG_SHORT)
    tm = _trained(_StubModel(pred=[0.6, -0.6, 0.0, -0.5], is_classifier=False), spec)
    sig = prediction_to_signal(tm, df)
    assert sig["target_position"].tolist() == [1.0, -1.0, 0.0, -1.0]


# --- filters (row-t only) ---


def test_warmup_rows_are_flat():
    df = _pred_ds(4)
    df.loc[1, "is_warmup"] = True
    sig = prediction_to_signal(_all_long_tm(4), df)
    assert sig["target_position"].tolist() == [1.0, 0.0, 1.0, 1.0]
    assert sig.loc[1, "signal_state"] == "warmup"


def test_non_trainable_rows_are_flat():
    df = _pred_ds(4)
    df.loc[2, "is_trainable"] = False
    sig = prediction_to_signal(_all_long_tm(4), df)
    assert sig["target_position"].tolist() == [1.0, 1.0, 0.0, 1.0]
    assert sig.loc[2, "signal_state"] == "not_trainable"


def test_roll_flag_rows_are_flat_when_enabled():
    df = _pred_ds(4)
    df["feature__roll_flag"] = [False, True, False, False]
    df["feature__days_since_roll"] = [10.0, 0.0, 1.0, 2.0]
    cfg = PredictionSignalConfig(enable_roll_filter=True, roll_avoidance_days=0)
    sig = prediction_to_signal(_all_long_tm(4), df, config=cfg)
    assert sig["target_position"].tolist() == [1.0, 0.0, 1.0, 1.0]
    assert sig.loc[1, "signal_state"] == "roll_avoidance"


def test_days_since_roll_window_is_flat_when_enabled():
    df = _pred_ds(5)
    df["feature__roll_flag"] = [False] * 5
    df["feature__days_since_roll"] = [10.0, 1.0, 2.0, 3.0, 8.0]
    cfg = PredictionSignalConfig(enable_roll_filter=True, roll_avoidance_days=2)
    sig = prediction_to_signal(_all_long_tm(5), df, config=cfg)
    assert sig["target_position"].tolist() == [1.0, 0.0, 0.0, 1.0, 1.0]


def test_volatility_filter_blocks_trades():
    df = _pred_ds(4)
    df["feature__realized_vol_20"] = [0.1, 0.5, 0.15, 0.3]
    cfg = PredictionSignalConfig(max_realized_vol=0.2)
    sig = prediction_to_signal(_all_long_tm(4), df, config=cfg)
    assert sig["target_position"].tolist() == [1.0, 0.0, 1.0, 0.0]
    assert sig.loc[1, "signal_state"] == "vol_filter"


def test_vol_filter_requires_column():
    df = _pred_ds(4)  # no realized_vol column
    cfg = PredictionSignalConfig(max_realized_vol=0.2)
    with pytest.raises(MlSignalError):
        prediction_to_signal(_all_long_tm(4), df, config=cfg)


# --- alignment / hygiene ---


def test_predict_model_aligns_with_input_timestamps():
    df = _pred_ds(10)
    tm = _trained(_StubModel(pred=np.arange(10.0), is_classifier=False), _reg_spec())
    out = predict_model(tm, df)
    assert out["timestamp"].tolist() == df["timestamp"].tolist()
    assert out["prediction"].tolist() == list(np.arange(10.0))
    assert out["root_symbol"].tolist() == ["ES"] * 10


def test_predict_model_respects_window():
    df = _pred_ds(10)
    tm = _trained(_StubModel(pred=np.arange(10.0), is_classifier=False), _reg_spec())
    out = predict_model(tm, df, start=date(2024, 7, 3), end=date(2024, 7, 9))
    days = pd.to_datetime(out["timestamp"]).dt.normalize()
    assert (days >= pd.Timestamp("2024-07-03")).all()
    assert (days <= pd.Timestamp("2024-07-09")).all()
    assert len(out) < len(df)


def test_predict_model_missing_feature_raises():
    df = _pred_ds(4).drop(columns=["feature__x2"])
    with pytest.raises(MlSignalError):
        predict_model(_trained(_StubModel(pred=np.ones(4)), _reg_spec()), df)


def test_prediction_to_signal_does_not_mutate_dataset():
    df = _pred_ds(6)
    before = df.copy(deep=True)
    prediction_to_signal(_all_long_tm(6), df)
    pd.testing.assert_frame_equal(df, before)


def test_no_position_shift_applied():
    df = _pred_ds(4)
    spec = _reg_spec(threshold_rule=ThresholdRule.RETURN_THRESHOLD,
                     long_threshold=0.5, signal_mode=SignalMode.LONG_FLAT)
    tm = _trained(_StubModel(pred=[1.0, 0.0, 0.0, 0.0], is_classifier=False), spec)
    sig = prediction_to_signal(tm, df)
    # row 0's prediction (1.0 -> long) maps to row 0's target, not row 1 (no shift)
    assert sig.loc[0, "target_position"] == 1.0
    assert sig.loc[1, "target_position"] == 0.0


def test_no_pnl_or_backtest_columns():
    df = _pred_ds(4)
    sig = prediction_to_signal(_all_long_tm(4), df)
    forbidden = {"equity", "strategy_return", "net_strategy_return",
                 "transaction_cost", "pnl", "benchmark_equity", "effective_position"}
    assert forbidden.isdisjoint(set(sig.columns))
    assert {"timestamp", "root_symbol", "active_contract", "prediction",
            "target_position", "signal_state"}.issubset(sig.columns)


def test_prediction_to_signal_deterministic_real_model():
    df = _ds(160)
    split = _holdout(110, 160)
    spec = _clf_spec(threshold_rule=ThresholdRule.PROB_THRESHOLD,
                     long_threshold=0.55, short_threshold=0.45, signal_mode=SignalMode.LONG_SHORT)
    tm = train_model(df, spec, split, **_HASHES)
    a = prediction_to_signal(tm, df)
    b = prediction_to_signal(tm, df)
    pd.testing.assert_frame_equal(a, b)
    assert ((a["prediction_proba"] >= 0.0) & (a["prediction_proba"] <= 1.0)).all()
    assert set(a["target_position"].unique()).issubset({-1.0, 0.0, 1.0})


# --------------------------------------------------------------------------- #
# Commit 4 — ML backtest evaluation
# --------------------------------------------------------------------------- #


def _eval_ds(n: int = 60, start: str = "2024-07-01", seed: int = 0) -> pd.DataFrame:
    """Synthetic supervised-dataset window with both ML and momentum feature cols."""
    rng = np.random.default_rng(seed)
    ts = pd.date_range(start, periods=n, freq="B")
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    return pd.DataFrame(
        {
            "timestamp": ts,
            "root_symbol": "ES",
            "active_contract": "ESH24",
            "feature__x1": x1,
            "feature__x2": x2,
            "feature__return_20": x1 * 0.01,
            "feature__moving_average_gap_10_50": x2 * 0.01,
            "feature__roll_flag": False,
            "feature__days_since_roll": 50.0,
            "label__direction_1": np.where(3.0 * x1 - 2.0 * x2 > 0, 1.0, -1.0),
            "label__forward_return_1": 2.0 * x1 - 1.0 * x2,
            "is_warmup": False,
            "is_label_valid": True,
            "is_trainable": True,
        }
    )


def _eval_continuous(n: int = 60, start: str = "2024-07-01") -> pd.DataFrame:
    """Minimal ratio continuous frame aligned to the eval dataset timestamps."""
    ts = pd.date_range(start, periods=n, freq="B")
    close = 5000.0 + np.arange(n, dtype=float)
    return pd.DataFrame(
        {
            "timestamp": ts,
            "root_symbol": "ES",
            "active_contract": "ESH24",
            "close_adjusted": close,
            "open_raw": close,
            "close_raw": close,
            "roll_flag": False,
            "adjustment_method": "ratio",
        }
    )


def _trained_clf(**over) -> TrainedModel:
    spec = _clf_spec(signal_mode=SignalMode.LONG_SHORT, threshold_rule=ThresholdRule.PROB_THRESHOLD,
                     long_threshold=0.55, short_threshold=0.45, **over)
    return train_model(_ds(200), spec, _holdout(150, 200), **_HASHES)


def _trained_reg(**over) -> TrainedModel:
    spec = _reg_spec(signal_mode=SignalMode.LONG_SHORT, threshold_rule=ThresholdRule.RETURN_THRESHOLD,
                     long_threshold=0.5, short_threshold=0.5, **over)
    return train_model(_ds(200), spec, _holdout(150, 200), **_HASHES)


# --- metrics (unit) ---


def test_classification_metrics_correct():
    y_true = np.array([1.0, 1.0, -1.0, -1.0, 1.0, -1.0])   # pos = [T,T,F,F,T,F]
    y_pred = np.array([1.0, 0.0, 0.0, 1.0, 1.0, 0.0])      # pos = [T,F,F,T,T,F]
    m = classification_metrics(y_true, y_pred)
    assert m["accuracy"] == pytest.approx(4 / 6)
    assert m["precision"] == pytest.approx(2 / 3)          # TP=2, FP=1
    assert m["recall"] == pytest.approx(2 / 3)             # TP=2, FN=1
    assert m["f1"] == pytest.approx(2 / 3)
    assert m["hit_rate"] == pytest.approx(4 / 6)
    assert m["n_scored"] == 6


def test_regression_metrics_correct_on_perfect_fit():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    m = regression_metrics(y, y)
    assert m["mse"] == 0.0 and m["mae"] == 0.0
    assert m["r2"] == pytest.approx(1.0)
    assert m["sign_accuracy"] == 1.0
    assert m["information_coefficient"] == pytest.approx(1.0)
    assert m["n_scored"] == 4


def test_regression_metrics_with_error():
    y = np.array([1.0, -1.0, 2.0, -2.0])
    p = np.array([0.5, -0.5, 1.0, -1.0])
    m = regression_metrics(y, p)
    assert m["mse"] == pytest.approx(np.mean((p - y) ** 2))
    assert m["mae"] == pytest.approx(np.mean(np.abs(p - y)))
    assert m["sign_accuracy"] == 1.0
    assert m["information_coefficient"] > 0.9


# --- evaluate_ml_signal (integration) ---


def test_evaluate_returns_expected_fields():
    tm = _trained_clf()
    res = evaluate_ml_signal(tm, _eval_ds(60), _eval_continuous(60), ES)
    assert isinstance(res, MlEvaluationResult)
    assert res.classification_metrics is not None
    assert res.regression_metrics is None
    assert {"final_equity", "total_return", "total_transaction_cost", "turnover"}.issubset(
        res.backtest_metrics
    )
    assert res.no_trade_baseline is not None and res.momentum_baseline is not None
    assert res.metadata["train_run_hash"] == tm.train_run_hash
    assert len(res.signals) == 60


def test_evaluate_regression_model_produces_regression_metrics():
    tm = _trained_reg()
    res = evaluate_ml_signal(tm, _eval_ds(60), _eval_continuous(60), ES, include_momentum_baseline=False)
    assert res.regression_metrics is not None
    assert res.classification_metrics is None
    assert res.regression_metrics["n_scored"] == 60


def test_nan_labels_excluded_from_scoring():
    tm = _trained_reg()
    eds = _eval_ds(40)
    eds.loc[0:9, "label__forward_return_1"] = np.nan
    eds.loc[0:9, "is_label_valid"] = False
    res = evaluate_ml_signal(tm, eds, _eval_continuous(40), ES, include_momentum_baseline=False)
    assert res.regression_metrics["n_scored"] == 30
    assert res.metadata["n_scored_rows"] == 30


def test_ml_backtest_uses_t_plus_1_execution():
    tm = _trained_clf()
    res = evaluate_ml_signal(tm, _eval_ds(50), _eval_continuous(50), ES, include_momentum_baseline=False)
    frame = res.ml_backtest.frame
    assert frame["effective_position"].iloc[0] == 0.0
    np.testing.assert_array_equal(
        frame["effective_position"].to_numpy(),
        frame["target_position"].shift(1).fillna(0.0).to_numpy(),
    )


def test_evaluate_does_not_mutate_inputs():
    tm = _trained_clf()
    eds, cont = _eval_ds(50), _eval_continuous(50)
    eds_before, cont_before = eds.copy(deep=True), cont.copy(deep=True)
    evaluate_ml_signal(tm, eds, cont, ES)
    pd.testing.assert_frame_equal(eds, eds_before)
    pd.testing.assert_frame_equal(cont, cont_before)


def test_no_trade_baseline_has_zero_positions_and_no_trades():
    tm = _trained_clf()
    res = evaluate_ml_signal(tm, _eval_ds(50), _eval_continuous(50), ES, include_momentum_baseline=False)
    nt = res.no_trade_baseline
    assert (nt["signal"]["target_position"] == 0.0).all()
    assert nt["backtest_metrics"]["num_trades"] == 0
    assert nt["backtest_metrics"]["turnover"] == pytest.approx(0.0)
    assert nt["backtest_metrics"]["total_transaction_cost"] == pytest.approx(0.0, abs=1e-9)


def test_baselines_use_same_oos_window_and_timestamps():
    tm = _trained_clf()
    res = evaluate_ml_signal(tm, _eval_ds(60), _eval_continuous(60), ES)
    ml_ts = res.signals["timestamp"].tolist()
    nt_ts = res.no_trade_baseline["signal"]["timestamp"].tolist()
    mom_ts = res.momentum_baseline["signal"]["timestamp"].tolist()
    assert ml_ts == nt_ts == mom_ts
    assert (res.ml_backtest.frame["timestamp"].tolist()
            == res.no_trade_baseline["result"].frame["timestamp"].tolist()
            == res.momentum_baseline["result"].frame["timestamp"].tolist())


def test_evaluation_window_restricts_all_three():
    tm = _trained_clf()
    eds, cont = _eval_ds(60, start="2024-07-01"), _eval_continuous(60, start="2024-07-01")
    res = evaluate_ml_signal(tm, eds, cont, ES, start=date(2024, 7, 15), end=date(2024, 8, 15))
    days = pd.to_datetime(res.signals["timestamp"]).dt.normalize()
    assert (days >= pd.Timestamp("2024-07-15")).all()
    assert (days <= pd.Timestamp("2024-08-15")).all()
    assert len(res.signals) < 60
    assert res.momentum_baseline["signal"]["timestamp"].tolist() == res.signals["timestamp"].tolist()
    assert res.ml_backtest.frame["timestamp"].tolist() == res.signals["timestamp"].tolist()


def test_backtest_metrics_include_required_keys():
    tm = _trained_clf()
    res = evaluate_ml_signal(tm, _eval_ds(50), _eval_continuous(50), ES, include_momentum_baseline=False)
    for key in ("final_equity", "total_return", "total_transaction_cost", "turnover",
                "num_trades", "n_position_changes", "max_drawdown", "sharpe"):
        assert key in res.backtest_metrics


def test_no_pnl_from_raw_close_gap():
    n = 40
    cont = _eval_continuous(n)
    cont.loc[20:, "close_raw"] = cont.loc[20:, "close_raw"] + 2000.0  # raw gap, adjusted stays smooth
    spec = _reg_spec(threshold_rule=ThresholdRule.RETURN_THRESHOLD,
                     long_threshold=-1e9, signal_mode=SignalMode.LONG_FLAT)  # always long
    tm = _trained(_StubModel(pred=np.ones(n), is_classifier=False), spec)
    res = evaluate_ml_signal(tm, _eval_ds(n), cont, ES,
                             include_momentum_baseline=False, backtest_kwargs={"transaction_cost_bps": 0})
    frame = res.ml_backtest.frame
    # held long across the raw gap -> return tracks close_adjusted (~1/5000), not the 2000-pt raw jump
    assert abs(frame["strategy_return"].iloc[20]) < 0.01


def test_evaluate_deterministic():
    tm = _trained_clf()
    eds, cont = _eval_ds(50), _eval_continuous(50)
    a = evaluate_ml_signal(tm, eds, cont, ES)
    b = evaluate_ml_signal(tm, eds, cont, ES)
    pd.testing.assert_frame_equal(a.signals, b.signals)
    pd.testing.assert_frame_equal(a.ml_backtest.frame, b.ml_backtest.frame)
    assert a.backtest_metrics == b.backtest_metrics
    assert a.classification_metrics == b.classification_metrics
