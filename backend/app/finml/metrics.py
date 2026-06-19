"""Summary metrics for the AFML labeling demo."""

from __future__ import annotations

import math
from typing import List

import numpy as np


def label_summary(labels: List[dict], uniqueness: List[float], n_days: int) -> dict:
    n_events = len(labels)
    pos = sum(1 for l in labels if l["label"] == 1)
    neg = sum(1 for l in labels if l["label"] == -1)
    zero = sum(1 for l in labels if l["label"] == 0)
    mean_uniq = float(np.mean(uniqueness)) if uniqueness else 0.0
    avg_hold = float(np.mean([l["holding_period_days"] for l in labels])) if labels else 0.0

    def _f(x: float) -> float:
        return float(x) if math.isfinite(x) else 0.0

    return {
        "n_days": int(n_days),
        "n_events": int(n_events),
        "positive_labels": int(pos),
        "negative_labels": int(neg),
        "zero_labels": int(zero),
        "mean_uniqueness": _f(mean_uniq),
        "average_holding_period": _f(avg_hold),
    }
