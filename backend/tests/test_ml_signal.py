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
    MlSignalError,
    ModelSpec,
    ModelType,
    SignalMode,
    SplitType,
    TaskType,
    ThresholdRule,
    chronological_holdout_split,
    dataset_config_hash,
    model_config_hash,
    purged_kfold_splits,
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

    for mod in (spec_mod, splits_mod):
        src = inspect.getsource(mod)
        # no network client imports, and no ML-framework imports (the words may
        # appear in prose saying we deliberately avoid them, so match imports only)
        assert not re.search(r"\bimport (requests|urllib|http|socket|aiohttp|httpx)\b", src)
        assert not re.search(r"\b(import|from)\s+sklearn\b", src)
        assert not re.search(r"\b(import|from)\s+(xgboost|lightgbm|torch|tensorflow)\b", src)
