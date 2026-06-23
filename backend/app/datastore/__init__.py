"""Local storage + schema validation for raw market data (Phase 1).

Named ``datastore`` (not ``data``) to avoid colliding with the existing
``app.data`` provider module; a later refactor can consolidate them.
"""

from app.datastore.store import (
    CONTINUOUS_SUBDIR,
    RAW_SUBDIR,
    REQUIRED_COLUMNS,
    RawFuturesStore,
    RawSchemaError,
    raw_data_version_hash,
    validate_raw_futures,
)

__all__ = [
    "REQUIRED_COLUMNS",
    "RAW_SUBDIR",
    "CONTINUOUS_SUBDIR",
    "RawSchemaError",
    "RawFuturesStore",
    "validate_raw_futures",
    "raw_data_version_hash",
]
