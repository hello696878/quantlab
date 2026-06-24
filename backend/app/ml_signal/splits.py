"""
Time-series-correct split utilities for the ML Signal Lab (Phase 4 — commit 1).

Three splitters, all deterministic and shuffle-free:

* ``chronological_holdout_split`` — a single train / validation cut by timestamp.
* ``walk_forward_splits`` — ordered expanding/rolling folds, train strictly before
  each test block, with an optional embargo gap.
* ``purged_kfold_splits`` — purged K-fold + embargo delegated to ``app.finml.cv``
  (Lopez de Prado, AFML ch. 7), using each event's forward label window
  ``[t + execution_lag, t + execution_lag + horizon]`` as its leakage interval.

Returned indices are integer positions into the *input frame* (not a sorted copy);
each splitter sorts internally by timestamp, so callers need not pre-sort.
No model training, no shuffling, no randomness.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional, Sequence

import numpy as np
import pandas as pd

from app.finml.cv import make_purged_kfold_splits
from app.finml.orchestrator import FinmlInputError
from app.ml_signal.spec import MlSignalError, SplitType

# A synthetic, strictly-increasing positional bar axis for app.finml.cv, which
# treats ``dates`` as an ordered axis only.  Real timestamps stay on the frame.
_BASE_DATE = date(2000, 1, 1)


@dataclass(frozen=True)
class Split:
    """A single train/test split as integer positions into the input frame."""

    split_type: SplitType
    train_index: np.ndarray
    test_index: np.ndarray


@dataclass(frozen=True)
class PurgedFold:
    """One purged + embargoed K-fold split with leakage diagnostics."""

    fold_id: int
    train_index: np.ndarray
    test_index: np.ndarray
    purged_index: np.ndarray
    embargoed_index: np.ndarray
    diagnostics: dict


def _naive_days(values) -> pd.Series:
    """Timestamps -> tz-naive, date-normalized (midnight) pandas Series."""
    s = pd.to_datetime(pd.Series(list(values)))
    if getattr(s.dt, "tz", None) is not None:
        s = s.dt.tz_convert("UTC").dt.tz_localize(None)
    return s.dt.normalize()


def _time_order(frame: pd.DataFrame, time_col: str) -> np.ndarray:
    """Original positions of ``frame`` rows in stable timestamp order."""
    if time_col not in frame.columns:
        raise MlSignalError(f"frame is missing the time column {time_col!r}")
    if len(frame) == 0:
        raise MlSignalError("frame must contain at least one row")
    ts = pd.to_datetime(frame[time_col]).to_numpy()
    return np.argsort(ts, kind="stable")


def chronological_holdout_split(
    frame: pd.DataFrame,
    *,
    train_start: date,
    train_end: date,
    validation_start: date,
    validation_end: date,
    time_col: str = "timestamp",
    embargo_bars: int = 0,
) -> Split:
    """Single time cut: train on ``[train_start, train_end]``, validate on
    ``[validation_start, validation_end]`` (both inclusive).  ``embargo_bars``
    drops that many of the latest train rows (closest to validation)."""
    if not (train_start <= train_end < validation_start <= validation_end):
        raise MlSignalError(
            "require train_start <= train_end < validation_start <= validation_end"
        )
    if embargo_bars < 0:
        raise MlSignalError("embargo_bars must be non-negative")

    order = _time_order(frame, time_col)
    day_ord = _naive_days(frame[time_col].to_numpy()).to_numpy()[order]

    def _between(lo: date, hi: date) -> np.ndarray:
        return (day_ord >= pd.Timestamp(lo)) & (day_ord <= pd.Timestamp(hi))

    train_sel = order[_between(train_start, train_end)]
    test_sel = order[_between(validation_start, validation_end)]
    if embargo_bars > 0 and train_sel.size > 0:
        train_sel = train_sel[: max(0, train_sel.size - embargo_bars)]
    return Split(SplitType.CHRONOLOGICAL_HOLDOUT, train_sel, test_sel)


def walk_forward_splits(
    frame: pd.DataFrame,
    *,
    n_splits: int,
    train_span: int,
    test_span: int,
    mode: str = "expanding",
    embargo_bars: int = 0,
    time_col: str = "timestamp",
) -> list[Split]:
    """Ordered walk-forward folds (non-overlapping test blocks).  ``mode`` is
    ``"expanding"`` (train = everything before the test) or ``"rolling"`` (train =
    the last ``train_span`` bars).  An ``embargo_bars`` gap separates train and
    test in every fold."""
    if n_splits < 1:
        raise MlSignalError("n_splits must be >= 1")
    if train_span < 1 or test_span < 1:
        raise MlSignalError("train_span and test_span must be >= 1")
    if embargo_bars < 0:
        raise MlSignalError("embargo_bars must be non-negative")
    if mode not in ("expanding", "rolling"):
        raise MlSignalError("mode must be 'expanding' or 'rolling'")

    order = _time_order(frame, time_col)
    m = order.size
    folds: list[Split] = []
    anchor = train_span
    for _ in range(n_splits):
        test_lo = anchor + embargo_bars
        test_hi = test_lo + test_span
        if test_hi > m:
            break
        train_lo = 0 if mode == "expanding" else max(0, anchor - train_span)
        folds.append(
            Split(SplitType.WALK_FORWARD, order[train_lo:anchor], order[test_lo:test_hi])
        )
        anchor = test_hi
    if not folds:
        raise MlSignalError("not enough rows to build a single walk-forward fold")
    return folds


def purged_kfold_splits(
    frame: pd.DataFrame,
    *,
    n_splits: int,
    execution_lag: int,
    horizon: int,
    embargo_bars: int = 0,
    event_mask: Optional[Sequence[bool]] = None,
    time_col: str = "timestamp",
) -> list[PurgedFold]:
    """Purged K-fold + embargo via ``app.finml.cv.make_purged_kfold_splits``.

    Each event row at time-position ``i`` carries the leakage interval
    ``[i + execution_lag, i + execution_lag + horizon]``; training events whose
    interval overlaps a test fold are purged, and events starting within
    ``embargo_bars`` after a test fold are embargoed.  ``event_mask`` (e.g.
    trainable rows only) restricts which rows act as labeled events; rows whose
    label window runs off the end of the data are never events.
    """
    if execution_lag < 0 or horizon < 1:
        raise MlSignalError("require execution_lag >= 0 and horizon >= 1")
    if embargo_bars < 0:
        raise MlSignalError("embargo_bars must be non-negative")

    order = _time_order(frame, time_col)
    n = order.size
    if event_mask is None:
        mask_sorted = np.ones(n, dtype=bool)
    else:
        mask_arr = np.asarray(list(event_mask), dtype=bool)
        if mask_arr.size != n:
            raise MlSignalError("event_mask length must match the number of rows")
        mask_sorted = mask_arr[order]

    # Event bar positions in time order; drop events whose label window overruns.
    event_bars = [
        i for i in range(n) if mask_sorted[i] and (i + execution_lag + horizon) < n
    ]
    if len(event_bars) < n_splits:
        raise MlSignalError("not enough labeled events for the requested n_splits")

    intervals = [
        {"event_id": j, "start": i + execution_lag, "end": i + execution_lag + horizon}
        for j, i in enumerate(event_bars)
    ]
    dates = [(_BASE_DATE + timedelta(days=k)).isoformat() for k in range(n)]
    try:
        raw_folds = make_purged_kfold_splits(intervals, n_splits, embargo_bars, dates)
    except FinmlInputError as exc:  # surface a consistent error type
        raise MlSignalError(str(exc)) from exc

    def _orig(event_ids: Sequence[int]) -> np.ndarray:
        return np.array([order[event_bars[j]] for j in event_ids], dtype=int)

    folds: list[PurgedFold] = []
    for f in raw_folds:
        folds.append(
            PurgedFold(
                fold_id=int(f["fold_id"]),
                train_index=_orig(f["train_event_ids"]),
                test_index=_orig(f["test_event_ids"]),
                purged_index=_orig(f["purged_event_ids"]),
                embargoed_index=_orig(f["embargoed_event_ids"]),
                diagnostics={
                    "train_count_before": f["train_count_before"],
                    "train_count_after": f["train_count_after"],
                    "test_count": f["test_count"],
                    "purged_count": f["purged_count"],
                    "embargoed_count": f["embargoed_count"],
                    "standard_train_overlap_count": f["standard_train_overlap_count"],
                    "purged_overlap_count_after_purge": f["purged_overlap_count_after_purge"],
                    "leakage_reduction": f["leakage_reduction"],
                    "train_fraction_remaining": f["train_fraction_remaining"],
                    "warnings": f["warnings"],
                },
            )
        )
    return folds
