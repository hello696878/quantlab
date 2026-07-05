"""
Local continuous futures -> ML pipeline (Phase 9).

Wires already-ingested local raw futures (Phase 7 ``RawFuturesStore``) through the
Phase 8 continuous builder into the existing Phase 2-5 feature / label / ML /
experiment chain — synthetic/local data only, no vendor, no network.  The only
thing that differs from ``research_cli.run_es_ml_experiment`` is the source of the
continuous frame (the store instead of a synthetic generator).
"""

from app.local_pipeline.config import LocalExperimentConfig
from app.local_pipeline.pipeline import (
    LocalExperimentResult,
    run_local_futures_ml_experiment,
)

__all__ = [
    "LocalExperimentConfig",
    "LocalExperimentResult",
    "run_local_futures_ml_experiment",
]
