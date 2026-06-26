"""
Local artifact store for experiment runs (Phase 5 — commit 2).

One directory per run, named by ``train_run_hash``, written **only** under a
caller-provided ``base_dir``:

    <base_dir>/<train_run_hash>/
    ├── metadata.json        # ExperimentRun.to_canonical_json()
    ├── model_params.json    # JSON-safe params (no pickle/joblib)
    ├── metrics.json         # deterministic canonical JSON
    ├── predictions.{parquet|csv}
    ├── signal.{parquet|csv}
    └── backtest.{parquet|csv}

Mirrors ``app.datastore.store.RawFuturesStore``: parquet is preferred, with an
explicit CSV fallback (`index=False`, `lineterminator="\n"`) when no parquet
engine is installed.  No network, no pickle, and no writes outside ``base_dir``.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.datastore.store import _parquet_available
from app.reproducibility import canonical_json
from app.experiments.spec import _ABSOLUTE_PATH, ExperimentError, ExperimentRun

logger = logging.getLogger(__name__)

_FRAME_NAMES = ("predictions", "signal", "backtest")


def _json_safe(obj: Any) -> Any:
    """Recursively coerce numpy types to JSON-safe Python so params/metrics
    serialize deterministically (no pickle)."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.generic):
        return obj.item()
    return obj


def _is_relative_path(value: str) -> bool:
    return not _ABSOLUTE_PATH.search(value) and ".." not in re.split(r"[\\/]", value)


class ExperimentStore:
    """File-based artifact store for experiment runs under an explicit ``base_dir``."""

    def __init__(self, base_dir: str | Path, prefer_parquet: bool = True) -> None:
        self.base_dir = Path(base_dir)
        self._use_parquet = bool(prefer_parquet and _parquet_available())
        self.storage_format = "parquet" if self._use_parquet else "csv"
        if not self._use_parquet:
            logger.info("ExperimentStore: no parquet engine available; using CSV fallback.")

    # --- paths ---

    def run_dir(self, train_run_hash: str) -> Path:
        h = str(train_run_hash)
        if not h.strip():
            raise ExperimentError("train_run_hash must be a non-empty string")
        if re.search(r"[\\/]", h) or ".." in h:
            raise ExperimentError(f"invalid train_run_hash for a directory name: {h!r}")
        return self.base_dir / h

    def _ensure_run_dir(self, train_run_hash: str) -> Path:
        d = self.run_dir(train_run_hash)
        d.mkdir(parents=True, exist_ok=True)  # only ever under base_dir
        return d

    # --- metadata ---

    def write_metadata(self, run: ExperimentRun) -> Path:
        path = self._ensure_run_dir(run.train_run_hash) / "metadata.json"
        path.write_text(run.to_canonical_json(), encoding="utf-8")
        return path

    def read_metadata(self, train_run_hash: str) -> ExperimentRun:
        path = self.run_dir(train_run_hash) / "metadata.json"
        if not path.exists():
            raise ExperimentError(f"metadata.json not found for run {train_run_hash!r}: {path}")
        run = ExperimentRun.model_validate_json(path.read_text(encoding="utf-8"))
        if run.train_run_hash != str(train_run_hash):
            raise ExperimentError(
                f"metadata train_run_hash {run.train_run_hash!r} != directory {train_run_hash!r}"
            )
        for key, value in run.artifact_paths.items():
            if not _is_relative_path(value):
                raise ExperimentError(f"metadata artifact path for {key!r} is not relative: {value!r}")
        return run

    # --- JSON artifacts ---

    def write_model_params(self, train_run_hash: str, params: dict) -> Path:
        return self._write_json(train_run_hash, "model_params.json", params)

    def read_model_params(self, train_run_hash: str) -> dict:
        return self._read_json(train_run_hash, "model_params.json")

    def write_metrics(self, train_run_hash: str, metrics: dict) -> Path:
        return self._write_json(train_run_hash, "metrics.json", metrics)

    def read_metrics(self, train_run_hash: str) -> dict:
        return self._read_json(train_run_hash, "metrics.json")

    def _write_json(self, train_run_hash: str, filename: str, obj: Any) -> Path:
        path = self._ensure_run_dir(train_run_hash) / filename
        path.write_text(canonical_json(_json_safe(obj)), encoding="utf-8")
        return path

    def _read_json(self, train_run_hash: str, filename: str) -> Any:
        path = self.run_dir(train_run_hash) / filename
        if not path.exists():
            raise ExperimentError(f"{filename} not found for run {train_run_hash!r}: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    # --- frame artifacts (parquet-if-available, CSV fallback) ---

    def write_frame(self, train_run_hash: str, name: str, df: pd.DataFrame) -> Path:
        if name not in _FRAME_NAMES:
            raise ExperimentError(f"unknown frame name {name!r}; expected one of {_FRAME_NAMES}")
        d = self._ensure_run_dir(train_run_hash)
        if self._use_parquet:
            path = d / f"{name}.parquet"
            try:
                df.to_parquet(path, index=False)
                return path
            except Exception:
                if path.exists():
                    path.unlink()  # drop a partial parquet before falling back
        path = d / f"{name}.csv"
        df.to_csv(path, index=False, lineterminator="\n")
        return path

    def read_frame(self, train_run_hash: str, name: str) -> pd.DataFrame:
        if name not in _FRAME_NAMES:
            raise ExperimentError(f"unknown frame name {name!r}; expected one of {_FRAME_NAMES}")
        d = self.run_dir(train_run_hash)
        parquet_path = d / f"{name}.parquet"
        csv_path = d / f"{name}.csv"
        if parquet_path.exists():
            return pd.read_parquet(parquet_path)
        if csv_path.exists():
            return pd.read_csv(csv_path)
        raise ExperimentError(f"frame {name!r} not found for run {train_run_hash!r} in {d}")
