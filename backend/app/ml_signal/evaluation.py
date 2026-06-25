"""
ML backtest evaluation for the ML Signal Lab (Phase 4 — commit 4).

Connects a trained model to the **existing** Phase 3 backtest and scores it:

* build the ML ``target_position(t)`` via ``prediction_to_signal`` (unshifted),
* backtest it with ``app.futures_backtest.run_futures_backtest`` (which owns the
  ``effective_position = target_position.shift(1)`` execution timing),
* score classification / regression accuracy on valid-label OOS rows,
* compare — **on the identical OOS window** — against a no-trade baseline and the
  Phase 3 ``momentum_baseline_signal``.

No shifting happens here; no PnL is computed from raw prices (the backtest uses
ratio-adjusted ``close_adjusted``).  Inputs are never mutated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from app.futures_backtest import FuturesBacktestResult, run_futures_backtest
from app.signals import BaselineSignalConfig, momentum_baseline_signal
from app.ml_signal.prediction import PredictionSignalConfig, _select_window, prediction_to_signal
from app.ml_signal.spec import MlSignalError, TaskType
from app.ml_signal.training import TrainedModel

_KEY_COLUMNS = ["timestamp", "root_symbol", "active_contract"]


@dataclass
class MlEvaluationResult:
    """Structured ML evaluation: signals, backtests, metrics, and baselines."""

    signals: pd.DataFrame
    ml_backtest: FuturesBacktestResult
    backtest_metrics: dict
    classification_metrics: Optional[dict]
    regression_metrics: Optional[dict]
    no_trade_baseline: Optional[dict]
    momentum_baseline: Optional[dict]
    metadata: dict


# --------------------------------------------------------------------------- #
# Metrics (pure numpy; up(+1)-vs-rest for classification)
# --------------------------------------------------------------------------- #


def classification_metrics(y_true, y_pred) -> dict:
    """Up(+1)-vs-rest metrics.  ``hit_rate`` equals accuracy for this binary task."""
    yt = (np.asarray(y_true, dtype=float) == 1.0)
    yp = (np.asarray(y_pred, dtype=float) >= 0.5)
    n = yt.shape[0]
    if n == 0:
        return {"accuracy": float("nan"), "precision": float("nan"), "recall": float("nan"),
                "f1": float("nan"), "hit_rate": float("nan"), "n_scored": 0}
    tp = float(np.sum(yp & yt))
    fp = float(np.sum(yp & ~yt))
    fn = float(np.sum(~yp & yt))
    accuracy = float(np.mean(yt == yp))
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {"accuracy": accuracy, "precision": precision, "recall": recall,
            "f1": f1, "hit_rate": accuracy, "n_scored": int(n)}


def regression_metrics(y_true, y_pred) -> dict:
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    n = y.shape[0]
    if n == 0:
        return {"mse": float("nan"), "mae": float("nan"), "r2": float("nan"),
                "sign_accuracy": float("nan"), "information_coefficient": float("nan"),
                "n_scored": 0}
    err = p - y
    mse = float(np.mean(err ** 2))
    mae = float(np.mean(np.abs(err)))
    ss_res = float(np.sum(err ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")
    sign_accuracy = float(np.mean(np.sign(p) == np.sign(y)))
    ic = (float(np.corrcoef(p, y)[0, 1])
          if np.std(p) > 0 and np.std(y) > 0 else float("nan"))
    return {"mse": mse, "mae": mae, "r2": r2, "sign_accuracy": sign_accuracy,
            "information_coefficient": ic, "n_scored": int(n)}


def backtest_metrics_from_result(result: FuturesBacktestResult,
                                 periods_per_year: int = 252) -> dict:
    """Backtest metrics from the result frame: reuses the engine's own metrics and
    adds turnover, max_drawdown, and an annualized Sharpe."""
    frame = result.frame
    equity = frame["equity"].to_numpy(dtype=float)
    effective = frame["effective_position"].to_numpy(dtype=float)
    net_return = frame["net_strategy_return"].to_numpy(dtype=float)

    turnover = float(np.abs(np.diff(np.concatenate([[0.0], effective]))).sum())
    running_max = np.maximum.accumulate(equity)
    drawdown = equity / running_max - 1.0
    max_drawdown = float(drawdown.min()) if equity.size else 0.0
    std = float(net_return.std(ddof=0))
    sharpe = float(net_return.mean() / std * np.sqrt(periods_per_year)) if std > 0 else 0.0

    metrics = dict(result.metrics)
    metrics.update({"turnover": turnover, "max_drawdown": max_drawdown, "sharpe": sharpe})
    return metrics


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #


def _no_trade_signal(ml_signal: pd.DataFrame) -> pd.DataFrame:
    out = ml_signal.loc[:, _KEY_COLUMNS].copy()
    out["target_position"] = 0.0
    return out


def _backtest(continuous_df, signal_df, instrument_spec, backtest_kwargs) -> FuturesBacktestResult:
    return run_futures_backtest(continuous_df, signal_df, instrument_spec, **backtest_kwargs)


def _baseline_entry(continuous_df, signal_df, instrument_spec, backtest_kwargs) -> dict:
    result = _backtest(continuous_df, signal_df, instrument_spec, backtest_kwargs)
    return {"signal": signal_df, "result": result,
            "backtest_metrics": backtest_metrics_from_result(result)}


def evaluate_ml_signal(
    trained_model: TrainedModel,
    dataset_df: pd.DataFrame,
    continuous_df: pd.DataFrame,
    instrument_spec,
    *,
    start=None,
    end=None,
    prediction_config: Optional[PredictionSignalConfig] = None,
    backtest_kwargs: Optional[dict] = None,
    momentum_config: Optional[BaselineSignalConfig] = None,
    include_momentum_baseline: bool = True,
    include_no_trade_baseline: bool = True,
) -> MlEvaluationResult:
    """Evaluate a trained model's signal over an out-of-sample window.

    Inputs are never mutated.  ML, no-trade, and momentum baselines are all
    backtested on the **same** windowed continuous frame with the **same**
    backtest settings, so their metrics are directly comparable."""
    for name, df in (("dataset_df", dataset_df), ("continuous_df", continuous_df)):
        missing = [c for c in _KEY_COLUMNS if c not in df.columns]
        if missing:
            raise MlSignalError(f"{name} is missing required columns: {missing}")

    bt_kwargs = dict(backtest_kwargs or {})

    # Same OOS window for everything.
    oos_dataset = _select_window(dataset_df, start, end)
    oos_continuous = _select_window(continuous_df, start, end)

    # ML signal at t (unshifted); the backtest applies the t+1 shift.
    ml_signal = prediction_to_signal(
        trained_model, dataset_df, start=start, end=end, config=prediction_config
    )
    ml_backtest = _backtest(oos_continuous, ml_signal, instrument_spec, bt_kwargs)
    bt_metrics = backtest_metrics_from_result(ml_backtest)

    # Score predictions on valid-label OOS rows only.
    label_col = trained_model.spec.label_column
    score = ml_signal[_KEY_COLUMNS + ["prediction"]].merge(
        oos_dataset[_KEY_COLUMNS + [label_col]
                    + (["is_label_valid"] if "is_label_valid" in oos_dataset.columns else [])],
        on=_KEY_COLUMNS, how="left",
    )
    labels = score[label_col].to_numpy(dtype=float)
    valid = ~np.isnan(labels)
    if "is_label_valid" in score.columns:
        valid &= score["is_label_valid"].astype(bool).to_numpy()
    y_true = labels[valid]
    y_pred = score["prediction"].to_numpy(dtype=float)[valid]

    classification_result = None
    regression_result = None
    if trained_model.spec.task_type is TaskType.CLASSIFICATION:
        classification_result = classification_metrics(y_true, y_pred)
    else:
        regression_result = regression_metrics(y_true, y_pred)

    # Baselines on the identical OOS window / settings.
    no_trade = None
    if include_no_trade_baseline:
        no_trade = _baseline_entry(
            oos_continuous, _no_trade_signal(ml_signal), instrument_spec, bt_kwargs
        )
    momentum = None
    if include_momentum_baseline:
        mom_signal = momentum_baseline_signal(oos_dataset, momentum_config or BaselineSignalConfig())
        momentum = _baseline_entry(oos_continuous, mom_signal, instrument_spec, bt_kwargs)

    metadata = {
        "train_run_hash": trained_model.train_run_hash,
        "model_config_hash": trained_model.model_config_hash,
        "dataset_config_hash": trained_model.dataset_config_hash,
        "task_type": trained_model.spec.task_type.value,
        "label_column": label_col,
        "n_oos_rows": int(len(ml_signal)),
        "n_scored_rows": int(valid.sum()),
        "window_start": None if start is None else str(start),
        "window_end": None if end is None else str(end),
    }
    for key in ("continuous_config_hash", "feature_config_hash", "label_config_hash"):
        if key in trained_model.metadata:
            metadata[key] = trained_model.metadata[key]

    return MlEvaluationResult(
        signals=ml_signal,
        ml_backtest=ml_backtest,
        backtest_metrics=bt_metrics,
        classification_metrics=classification_result,
        regression_metrics=regression_result,
        no_trade_baseline=no_trade,
        momentum_baseline=momentum,
        metadata=metadata,
    )
