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

from app.ml_signal import (
    BaseModel,
    DummyBaseline,
    LogisticRegression,
    MlSignalError,
    ModelSpec,
    ModelType,
    RidgeRegression,
    SignalMode,
    Split,
    SplitType,
    TaskType,
    ThresholdRule,
    TrainedModel,
    build_model,
    chronological_holdout_split,
    dataset_config_hash,
    model_config_hash,
    purged_kfold_splits,
    select_design_matrix,
    train_model,
    train_run_hash,
    walk_forward_splits,
)


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

    for mod in (spec_mod, splits_mod, models_mod, training_mod):
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
