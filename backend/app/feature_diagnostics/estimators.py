"""
Deterministic in-process estimators (numpy only — no scikit-learn, no model
files, no pickle).  Every fit is a pure function of (X, y, hyperparameters):

* ``logistic_regression`` — L2-regularized logistic regression via
  Newton–Raphson on standardized features (binary classification).
* ``linear_regression`` — ridge regression in closed form on standardized
  features (regression).
* ``decision_tree`` — bounded CART (gini for classification, variance for
  regression) with exhaustive midpoint threshold search and deterministic
  tie-breaking (lowest feature index, then lowest threshold).  Exposes
  impurity-based native importance.

Models are plain JSON-serializable dicts; nothing is ever deserialized from
untrusted bytes.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

MODEL_TYPES = ("logistic_regression", "linear_regression", "decision_tree")

MODEL_TASKS = {
    "logistic_regression": ("binary_classification",),
    "linear_regression": ("regression",),
    "decision_tree": ("binary_classification", "regression"),
}

# Models that natively expose impurity-based importance / coefficients.
NATIVE_IMPORTANCE_MODELS = ("decision_tree",)
COEFFICIENT_MODELS = ("logistic_regression", "linear_regression")

DEFAULT_L2 = 0.01
DEFAULT_MAX_DEPTH = 4
DEFAULT_MIN_LEAF = 5

_MAX_NEWTON_ITER = 100
_NEWTON_TOL = 1e-8


class EstimatorError(ValueError):
    """Model cannot be fitted on the given data (recorded honestly)."""


def _standardize_params(X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    means = X.mean(axis=0)
    stds = X.std(axis=0)
    stds = np.where(stds > 0.0, stds, 1.0)
    return means, stds


def _fit_logistic(X: np.ndarray, y: np.ndarray, l2: float) -> Dict[str, Any]:
    classes = np.unique(y)
    if not np.all(np.isin(classes, (0.0, 1.0))) or len(classes) < 2:
        raise EstimatorError(
            "logistic_regression requires both classes (0 and 1) in training data"
        )
    means, stds = _standardize_params(X)
    Z = (X - means) / stds
    n, p = Z.shape
    A = np.hstack([np.ones((n, 1)), Z])
    w = np.zeros(p + 1)
    reg = np.full(p + 1, l2 * n)
    reg[0] = 0.0  # intercept unregularized
    for _ in range(_MAX_NEWTON_ITER):
        z = np.clip(A @ w, -35.0, 35.0)
        prob = 1.0 / (1.0 + np.exp(-z))
        grad = A.T @ (prob - y) + reg * w
        W = np.maximum(prob * (1.0 - prob), 1e-10)
        H = (A * W[:, None]).T @ A + np.diag(np.maximum(reg, 1e-10))
        H[0, 0] = max(H[0, 0], 1e-10)
        try:
            step = np.linalg.solve(H, grad)
        except np.linalg.LinAlgError:
            raise EstimatorError("logistic_regression Hessian is singular")
        w = w - step
        if float(np.max(np.abs(step))) < _NEWTON_TOL:
            break
    if not np.all(np.isfinite(w)):
        raise EstimatorError("logistic_regression coefficients did not converge")
    return {"kind": "logistic_regression", "task": "binary_classification",
            "means": means.tolist(), "stds": stds.tolist(),
            "weights": w.tolist(), "standardized": True, "l2": l2}


def _fit_linear(X: np.ndarray, y: np.ndarray, l2: float) -> Dict[str, Any]:
    means, stds = _standardize_params(X)
    Z = (X - means) / stds
    n, p = Z.shape
    y_mean = float(y.mean())
    yc = y - y_mean
    G = Z.T @ Z + l2 * n * np.eye(p)
    try:
        coef = np.linalg.solve(G, Z.T @ yc)
    except np.linalg.LinAlgError:
        raise EstimatorError("linear_regression normal equations are singular")
    if not np.all(np.isfinite(coef)):
        raise EstimatorError("linear_regression coefficients are non-finite")
    return {"kind": "linear_regression", "task": "regression",
            "means": means.tolist(), "stds": stds.tolist(),
            "weights": [y_mean, *coef.tolist()], "standardized": True, "l2": l2}


# ---------------------------------------------------------------------------
# Bounded deterministic CART
# ---------------------------------------------------------------------------


def _node_impurity(y: np.ndarray, task: str) -> float:
    if task == "binary_classification":
        p1 = float(y.mean())
        return 1.0 - p1 * p1 - (1.0 - p1) * (1.0 - p1)
    return float(np.var(y))


def _best_split(
    X: np.ndarray, y: np.ndarray, task: str, min_leaf: int
) -> Optional[Tuple[int, float, float]]:
    """(feature_index, threshold, impurity_decrease) or None.

    Deterministic: features scanned in declared order; a candidate replaces the
    best only on a strictly larger decrease, so ties keep the lowest feature
    index and, within a feature, the lowest threshold.
    """
    n = len(y)
    parent = _node_impurity(y, task)
    best: Optional[Tuple[int, float, float]] = None
    for j in range(X.shape[1]):
        order = np.argsort(X[:, j], kind="stable")
        xs, ys = X[order, j], y[order]
        csum = np.cumsum(ys)
        csq = np.cumsum(ys * ys)
        total, total_sq = csum[-1], csq[-1]
        for i in range(min_leaf - 1, n - min_leaf):
            if xs[i] == xs[i + 1]:
                continue
            nl, nr = i + 1, n - i - 1
            if task == "binary_classification":
                pl = csum[i] / nl
                pr = (total - csum[i]) / nr
                gl = 1.0 - pl * pl - (1.0 - pl) * (1.0 - pl)
                gr = 1.0 - pr * pr - (1.0 - pr) * (1.0 - pr)
            else:
                gl = csq[i] / nl - (csum[i] / nl) ** 2
                gr = (total_sq - csq[i]) / nr - ((total - csum[i]) / nr) ** 2
            decrease = parent - (nl * gl + nr * gr) / n
            if decrease > 1e-12 and (best is None or decrease > best[2]):
                threshold = float((xs[i] + xs[i + 1]) / 2.0)
                best = (j, threshold, float(decrease))
    return best


def _grow(
    X: np.ndarray, y: np.ndarray, task: str, depth: int, max_depth: int,
    min_leaf: int, n_total: int, importance: np.ndarray,
) -> Dict[str, Any]:
    leaf_value = float(y.mean())
    if depth >= max_depth or len(y) < 2 * min_leaf \
            or _node_impurity(y, task) <= 1e-12:
        return {"leaf": True, "value": leaf_value, "n": int(len(y))}
    found = _best_split(X, y, task, min_leaf)
    if found is None:
        return {"leaf": True, "value": leaf_value, "n": int(len(y))}
    j, threshold, decrease = found
    importance[j] += decrease * len(y) / n_total
    mask = X[:, j] <= threshold
    return {
        "leaf": False, "feature_index": j, "threshold": threshold,
        "n": int(len(y)),
        "left": _grow(X[mask], y[mask], task, depth + 1, max_depth, min_leaf,
                      n_total, importance),
        "right": _grow(X[~mask], y[~mask], task, depth + 1, max_depth, min_leaf,
                       n_total, importance),
    }


def _fit_tree(
    X: np.ndarray, y: np.ndarray, task: str, max_depth: int, min_leaf: int
) -> Dict[str, Any]:
    if task == "binary_classification" and len(np.unique(y)) < 2:
        raise EstimatorError("decision_tree classification requires both classes")
    importance = np.zeros(X.shape[1])
    root = _grow(X, y, task, 0, max_depth, min_leaf, len(y), importance)
    total = float(importance.sum())
    native = (importance / total).tolist() if total > 0 else importance.tolist()
    return {"kind": "decision_tree", "task": task, "root": root,
            "native_importance": native, "max_depth": max_depth,
            "min_samples_leaf": min_leaf}


def _tree_predict_row(node: Dict[str, Any], row: np.ndarray) -> float:
    while not node["leaf"]:
        node = node["left"] if row[node["feature_index"]] <= node["threshold"] \
            else node["right"]
    return node["value"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fit_estimator(
    model_type: str, X: np.ndarray, y: np.ndarray, target_type: str,
    hyperparameters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    hp = hyperparameters or {}
    if model_type not in MODEL_TYPES:
        raise EstimatorError(f"model_type must be one of {MODEL_TYPES}")
    if target_type not in MODEL_TASKS[model_type]:
        raise EstimatorError(
            f"{model_type} does not support target_type {target_type!r}"
        )
    if model_type == "logistic_regression":
        return _fit_logistic(X, y, float(hp.get("l2", DEFAULT_L2)))
    if model_type == "linear_regression":
        return _fit_linear(X, y, float(hp.get("l2", DEFAULT_L2)))
    return _fit_tree(
        X, y, target_type,
        int(hp.get("max_depth", DEFAULT_MAX_DEPTH)),
        int(hp.get("min_samples_leaf", DEFAULT_MIN_LEAF)),
    )


def predict(model: Dict[str, Any], X: np.ndarray) -> np.ndarray:
    """Probabilities of class 1 (classification) or values (regression)."""
    kind = model["kind"]
    if kind in COEFFICIENT_MODELS:
        means = np.asarray(model["means"])
        stds = np.asarray(model["stds"])
        w = np.asarray(model["weights"])
        Z = (X - means) / stds
        raw = w[0] + Z @ w[1:]
        if kind == "logistic_regression":
            return 1.0 / (1.0 + np.exp(-np.clip(raw, -35.0, 35.0)))
        return raw
    return np.array([_tree_predict_row(model["root"], row) for row in X])


def coefficient_reference(
    model: Dict[str, Any], feature_names: List[str]
) -> Optional[List[Dict[str, Any]]]:
    """Standardized coefficients with signs — a scale-caveated reference only."""
    if model["kind"] not in COEFFICIENT_MODELS:
        return None
    coefs = model["weights"][1:]
    return [
        {"feature_name": name, "coefficient": float(c),
         "abs_coefficient": abs(float(c)),
         "sign": 1 if c > 0 else (-1 if c < 0 else 0),
         "standardized": bool(model.get("standardized", False))}
        for name, c in zip(feature_names, coefs)
    ]


def native_reference(
    model: Dict[str, Any], feature_names: List[str]
) -> Optional[List[Dict[str, Any]]]:
    """Impurity-based native importance — training-data derived, caveated."""
    if model["kind"] not in NATIVE_IMPORTANCE_MODELS:
        return None
    return [
        {"feature_name": name, "native_importance": float(v)}
        for name, v in zip(feature_names, model["native_importance"])
    ]


def validate_hyperparameters(model_type: str, hp: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    l2 = hp.get("l2", DEFAULT_L2)
    if isinstance(l2, bool) or not isinstance(l2, (int, float)) \
            or not math.isfinite(l2) or not (1e-6 <= float(l2) <= 10.0):
        raise EstimatorError("l2 must be a finite number in [1e-6, 10]")
    out["l2"] = float(l2)
    depth = hp.get("max_depth", DEFAULT_MAX_DEPTH)
    if isinstance(depth, bool) or not isinstance(depth, int) or not (1 <= depth <= 8):
        raise EstimatorError("max_depth must be an integer in [1, 8]")
    out["max_depth"] = depth
    leaf = hp.get("min_samples_leaf", DEFAULT_MIN_LEAF)
    if isinstance(leaf, bool) or not isinstance(leaf, int) or not (2 <= leaf <= 50):
        raise EstimatorError("min_samples_leaf must be an integer in [2, 50]")
    out["min_samples_leaf"] = leaf
    return out


__all__ = [
    "MODEL_TYPES", "MODEL_TASKS", "NATIVE_IMPORTANCE_MODELS",
    "COEFFICIENT_MODELS", "EstimatorError", "fit_estimator", "predict",
    "coefficient_reference", "native_reference", "validate_hyperparameters",
]
