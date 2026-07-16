"""
Incremental integration helper for existing QuantLab modules.

A module can record a research run in the registry without being rewritten, by
calling one of these functions.  They are safe to call from synchronous FastAPI
code: no background service, no telemetry, no external network — only local
SQLite writes.

**Failure policy (documented and enforced):** registry recording is
*best-effort*.  Every function catches all exceptions, logs a warning, and
returns ``None`` on failure, so a registry problem can never corrupt, alter, or
block the primary research result the caller is computing.  Because of this, a
module should compute and return its real result first, then record — never gate
its response on a registry write.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.experiment_registry import service
from app.experiment_registry.models import ExperimentCreate

logger = logging.getLogger(__name__)


def record_experiment(
    *,
    name: str,
    module: str,
    experiment_type: str,
    status: str = "completed",
    parameters: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
    description: str = "",
    notes: str = "",
    random_seed: Optional[int] = None,
    dataset_name: Optional[str] = None,
    dataset_version: Optional[str] = None,
    dataset_fingerprint: Optional[str] = None,
    dataset_identity: Optional[Dict[str, Any]] = None,
    parent_experiment_id: Optional[int] = None,
    error_message: Optional[str] = None,
    source: str = "module",
) -> Optional[Dict[str, Any]]:
    """Record a (usually completed) run in one call.  Best-effort; never raises."""
    try:
        payload = ExperimentCreate(
            name=name,
            description=description,
            module=module,
            experiment_type=experiment_type,
            status=status,
            parameters=parameters or {},
            metrics=metrics or {},
            tags=tags or [],
            notes=notes,
            random_seed=random_seed,
            dataset_name=dataset_name,
            dataset_version=dataset_version,
            dataset_fingerprint=dataset_fingerprint,
            dataset_identity=dataset_identity or {},
            parent_experiment_id=parent_experiment_id,
            error_message=error_message,
        ).model_dump()
        return service.create_experiment(payload, source=source)
    except Exception:  # noqa: BLE001 — best-effort recording must never propagate
        logger.warning("experiment_registry: failed to record experiment %r", name, exc_info=True)
        return None


def start_experiment(
    *,
    name: str,
    module: str,
    experiment_type: str,
    parameters: Optional[Dict[str, Any]] = None,
    random_seed: Optional[int] = None,
    dataset_name: Optional[str] = None,
    dataset_version: Optional[str] = None,
    dataset_fingerprint: Optional[str] = None,
    dataset_identity: Optional[Dict[str, Any]] = None,
    started_at: Optional[str] = None,
    source: str = "module",
) -> Optional[int]:
    """Create a ``running`` record and return its id (or ``None`` on failure)."""
    try:
        payload = ExperimentCreate(
            name=name,
            module=module,
            experiment_type=experiment_type,
            status="running",
            parameters=parameters or {},
            random_seed=random_seed,
            dataset_name=dataset_name,
            dataset_version=dataset_version,
            dataset_fingerprint=dataset_fingerprint,
            dataset_identity=dataset_identity or {},
            started_at=started_at,
        ).model_dump()
        record = service.create_experiment(payload, source=source)
        return int(record["id"])
    except Exception:  # noqa: BLE001
        logger.warning("experiment_registry: failed to start experiment %r", name, exc_info=True)
        return None


def complete_experiment(
    experiment_id: int,
    *,
    metrics: Optional[Dict[str, Any]] = None,
    result_metadata: Optional[Dict[str, Any]] = None,
    duration_ms: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Mark a started record completed.  Best-effort; never raises."""
    try:
        return service.complete_experiment(
            experiment_id,
            {
                "metrics": metrics or {},
                "result_metadata": result_metadata or {},
                "duration_ms": duration_ms,
            },
        )
    except Exception:  # noqa: BLE001
        logger.warning("experiment_registry: failed to complete experiment %s", experiment_id, exc_info=True)
        return None


def fail_experiment(experiment_id: int, *, error_message: str) -> Optional[Dict[str, Any]]:
    """Mark a started record failed.  Best-effort; never raises."""
    try:
        return service.fail_experiment(experiment_id, {"error_message": error_message})
    except Exception:  # noqa: BLE001
        logger.warning("experiment_registry: failed to fail experiment %s", experiment_id, exc_info=True)
        return None


def mark_experiment_invalid(experiment_id: int) -> Optional[Dict[str, Any]]:
    """Invalidate a record.  Best-effort; never raises."""
    try:
        return service.invalidate_experiment(experiment_id)
    except Exception:  # noqa: BLE001
        logger.warning("experiment_registry: failed to invalidate experiment %s", experiment_id, exc_info=True)
        return None


__all__ = [
    "record_experiment",
    "start_experiment",
    "complete_experiment",
    "fail_experiment",
    "mark_experiment_invalid",
]
