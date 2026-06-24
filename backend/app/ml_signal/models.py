"""
Pure numpy/scipy estimators for the ML Signal Lab (Phase 4 — commit 2).

Three deliberately simple, **deterministic** models behind a common interface
(``fit`` / ``predict`` / optional ``predict_proba``).  No scikit-learn, xgboost,
lightgbm, torch, or tensorflow — only numpy + scipy.

* ``DummyBaseline``      — majority class (classification) / train mean (regression).
* ``RidgeRegression``    — closed-form ridge with an unpenalized intercept.
* ``LogisticRegression`` — binary L2-regularized logistic via ``scipy.optimize``.

Classification is **binary**: labels are binarized to *up(+1) vs rest*, so a
direction label in ``{-1, 0, +1}`` is modelled as ``P(label == +1)``.  Labels
outside ``{-1, 0, +1}`` are rejected (no true multiclass in V1).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

from app.ml_signal.spec import ModelSpec, ModelType, MlSignalError, TaskType

_POSITIVE_LABEL = 1.0
_ALLOWED_CLASS_LABELS = frozenset({-1.0, 0.0, 1.0})


def _as_2d(X) -> np.ndarray:
    arr = np.asarray(X, dtype=float)
    if arr.ndim != 2:
        raise MlSignalError("X must be a 2D array of shape (n_samples, n_features)")
    return arr


def _as_1d(y) -> np.ndarray:
    arr = np.asarray(y, dtype=float).ravel()
    return arr


def _check_weights(sample_weight: Optional[np.ndarray], n: int) -> np.ndarray:
    if sample_weight is None:
        return np.ones(n, dtype=float)
    w = np.asarray(sample_weight, dtype=float).ravel()
    if w.size != n:
        raise MlSignalError("sample_weight length must match the number of rows")
    if np.any(w < 0):
        raise MlSignalError("sample_weight must be non-negative")
    return w


class BaseModel(ABC):
    """Common estimator interface.  ``is_classifier`` flags probability support."""

    is_classifier: bool = False

    @abstractmethod
    def fit(self, X, y, sample_weight: Optional[np.ndarray] = None) -> "BaseModel":
        ...

    @abstractmethod
    def predict(self, X) -> np.ndarray:
        ...

    def predict_proba(self, X) -> np.ndarray:
        raise NotImplementedError("predict_proba is only defined for classifiers")

    @property
    def params(self) -> dict:
        raise NotImplementedError


class DummyBaseline(BaseModel):
    """Majority class (classification) or train mean (regression).  Deterministic."""

    def __init__(self, task_type: TaskType):
        self.task_type = task_type
        self.is_classifier = task_type is TaskType.CLASSIFICATION
        self.majority_: Optional[float] = None
        self.mean_: Optional[float] = None
        self.positive_freq_: Optional[float] = None

    def fit(self, X, y, sample_weight: Optional[np.ndarray] = None) -> "DummyBaseline":
        y = _as_1d(y)
        w = _check_weights(sample_weight, y.size)
        if self.is_classifier:
            classes, counts = np.unique(y, return_counts=True)
            # weighted class mass; deterministic argmax (np.unique is sorted, ties -> smaller label)
            mass = np.array([w[y == c].sum() for c in classes])
            self.majority_ = float(classes[int(np.argmax(mass))])
            self.positive_freq_ = float(w[y == _POSITIVE_LABEL].sum() / w.sum())
        else:
            self.mean_ = float(np.average(y, weights=w))
        return self

    def predict(self, X) -> np.ndarray:
        X = _as_2d(X)
        if self.is_classifier:
            if self.majority_ is None:
                raise MlSignalError("model is not fitted")
            return np.full(X.shape[0], self.majority_, dtype=float)
        if self.mean_ is None:
            raise MlSignalError("model is not fitted")
        return np.full(X.shape[0], self.mean_, dtype=float)

    def predict_proba(self, X) -> np.ndarray:
        if not self.is_classifier or self.positive_freq_ is None:
            raise NotImplementedError("predict_proba requires a fitted classifier")
        X = _as_2d(X)
        return np.full(X.shape[0], self.positive_freq_, dtype=float)

    @property
    def params(self) -> dict:
        return {"majority_": self.majority_, "mean_": self.mean_,
                "positive_freq_": self.positive_freq_}


class RidgeRegression(BaseModel):
    """Closed-form ridge: ``beta = (Xb' W Xb + P)^-1 Xb' W y`` with ``P`` zeroing
    the intercept (the intercept is never regularized).  Deterministic."""

    is_classifier = False

    def __init__(self, alpha: float = 1.0, fit_intercept: bool = True):
        if alpha < 0:
            raise MlSignalError("ridge alpha must be non-negative")
        self.alpha = float(alpha)
        self.fit_intercept = bool(fit_intercept)
        self.coef_: Optional[np.ndarray] = None
        self.intercept_: float = 0.0

    def _design(self, X: np.ndarray) -> np.ndarray:
        if self.fit_intercept:
            return np.hstack([np.ones((X.shape[0], 1)), X])
        return X

    def fit(self, X, y, sample_weight: Optional[np.ndarray] = None) -> "RidgeRegression":
        X = _as_2d(X)
        y = _as_1d(y)
        w = _check_weights(sample_weight, y.size)
        Xb = self._design(X)
        d = Xb.shape[1]
        penalty = self.alpha * np.eye(d)
        if self.fit_intercept:
            penalty[0, 0] = 0.0  # do not regularize the intercept
        A = Xb.T @ (Xb * w[:, None]) + penalty
        b = Xb.T @ (w * y)
        beta = np.linalg.solve(A, b)
        if self.fit_intercept:
            self.intercept_ = float(beta[0])
            self.coef_ = beta[1:]
        else:
            self.intercept_ = 0.0
            self.coef_ = beta
        return self

    def predict(self, X) -> np.ndarray:
        if self.coef_ is None:
            raise MlSignalError("model is not fitted")
        X = _as_2d(X)
        return self.intercept_ + X @ self.coef_

    @property
    def params(self) -> dict:
        return {"coef_": self.coef_, "intercept_": self.intercept_, "alpha": self.alpha}


class LogisticRegression(BaseModel):
    """Binary L2-regularized logistic regression via ``scipy.optimize.minimize``
    (L-BFGS-B, analytic gradient, zero init) — deterministic.  ``C`` is the
    inverse regularization strength; the intercept is not penalized.

    Labels are binarized to *up(+1) vs rest*: ``y == +1`` is the positive class.
    Labels outside ``{-1, 0, +1}`` are rejected (no true multiclass in V1).
    """

    is_classifier = True

    def __init__(self, C: float = 1.0, max_iter: int = 200, tol: float = 1e-8,
                 fit_intercept: bool = True):
        if C <= 0:
            raise MlSignalError("logistic C must be positive")
        self.C = float(C)
        self.max_iter = int(max_iter)
        self.tol = float(tol)
        self.fit_intercept = bool(fit_intercept)
        self.coef_: Optional[np.ndarray] = None
        self.intercept_: float = 0.0
        self.converged_: bool = False

    def _design(self, X: np.ndarray) -> np.ndarray:
        if self.fit_intercept:
            return np.hstack([np.ones((X.shape[0], 1)), X])
        return X

    @staticmethod
    def _binarize(y: np.ndarray) -> np.ndarray:
        classes = set(np.unique(y).tolist())
        if not classes <= _ALLOWED_CLASS_LABELS:
            raise MlSignalError(
                f"classification labels must be a subset of {{-1, 0, 1}}; got {sorted(classes)}"
            )
        return (y == _POSITIVE_LABEL).astype(float)

    def fit(self, X, y, sample_weight: Optional[np.ndarray] = None) -> "LogisticRegression":
        X = _as_2d(X)
        y01 = self._binarize(_as_1d(y))
        w = _check_weights(sample_weight, y01.size)
        Xb = self._design(X)
        d = Xb.shape[1]
        lam = 1.0 / self.C
        reg_mask = np.ones(d)
        if self.fit_intercept:
            reg_mask[0] = 0.0  # do not penalize the intercept

        def nll(beta: np.ndarray) -> float:
            z = Xb @ beta
            # weighted negative log-likelihood, numerically stable via logaddexp
            data = np.sum(w * (np.logaddexp(0.0, z) - y01 * z))
            penalty = 0.5 * lam * np.sum((reg_mask * beta) ** 2)
            return float(data + penalty)

        def grad(beta: np.ndarray) -> np.ndarray:
            p = expit(Xb @ beta)
            return Xb.T @ (w * (p - y01)) + lam * (reg_mask * beta)

        res = minimize(
            nll, np.zeros(d), jac=grad, method="L-BFGS-B",
            options={"maxiter": self.max_iter, "ftol": self.tol, "gtol": self.tol},
        )
        self.converged_ = bool(res.success)
        if self.fit_intercept:
            self.intercept_ = float(res.x[0])
            self.coef_ = res.x[1:]
        else:
            self.intercept_ = 0.0
            self.coef_ = res.x
        return self

    def predict_proba(self, X) -> np.ndarray:
        if self.coef_ is None:
            raise MlSignalError("model is not fitted")
        X = _as_2d(X)
        return expit(self.intercept_ + X @ self.coef_)

    def predict(self, X) -> np.ndarray:
        # binary decision: positive (1.0) vs rest (0.0)
        return (self.predict_proba(X) >= 0.5).astype(float)

    @property
    def params(self) -> dict:
        return {"coef_": self.coef_, "intercept_": self.intercept_,
                "C": self.C, "converged_": self.converged_}


def build_model(spec: ModelSpec) -> BaseModel:
    """Instantiate the estimator named by ``spec.model_type`` with its hyperparameters."""
    hp = dict(spec.hyperparameters)
    if spec.model_type is ModelType.DUMMY_BASELINE:
        return DummyBaseline(spec.task_type)
    if spec.model_type is ModelType.RIDGE_REGRESSION:
        return RidgeRegression(
            alpha=float(hp.get("alpha", 1.0)),
            fit_intercept=bool(hp.get("fit_intercept", True)),
        )
    if spec.model_type is ModelType.LOGISTIC_REGRESSION:
        return LogisticRegression(
            C=float(hp.get("C", 1.0)),
            max_iter=int(hp.get("max_iter", 200)),
            tol=float(hp.get("tol", 1e-8)),
            fit_intercept=bool(hp.get("fit_intercept", True)),
        )
    raise MlSignalError(f"unsupported model_type: {spec.model_type!r}")
