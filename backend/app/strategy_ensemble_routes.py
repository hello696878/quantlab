"""Local, bounded strategy ensemble API; no external provider or execution."""

from fastapi import APIRouter, HTTPException, Query

from app.strategy_ensemble import service, store
from app.strategy_ensemble.models import RunCreate, ExecuteRequest, InvalidateRequest

router = APIRouter(prefix="/strategy-ensembles", tags=["strategy-ensembles"])


def guard(fn):
    try:
        return fn()
    except service.NotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/runs")
def list_runs(page: int = Query(1, ge=1, le=10000), page_size: int = Query(25, ge=1, le=100)):
    return store.list_runs(page, page_size)


@router.post("/runs", status_code=201)
def create(payload: RunCreate):
    return guard(lambda: service.create_run(payload.model_dump()))


@router.get("/runs/{run_id}")
def get(run_id: int):
    return guard(lambda: service.get_run(run_id))


@router.post("/runs/{run_id}/execute")
def execute(run_id: int, payload: ExecuteRequest = ExecuteRequest()):
    return guard(lambda: service.execute_run(run_id, payload.create_experiment))


@router.post("/runs/{run_id}/invalidate")
def invalidate(run_id: int, payload: InvalidateRequest):
    return guard(lambda: service.invalidate(run_id, payload.reason))


@router.post("/runs/{run_id}/mark-baseline")
def baseline(run_id: int):
    return guard(lambda: service.mark_baseline(run_id))


@router.get("/compare")
def compare(a: int = Query(..., gt=0), b: int = Query(..., gt=0)):
    return guard(lambda: service.compare(a, b))


@router.get("/export")
def export(run_id: int = Query(..., gt=0)):
    return guard(lambda: service.export(run_id))


@router.post("/demo-seed")
def demo_seed():
    from app.strategy_ensemble.demo import seed
    return guard(seed)
