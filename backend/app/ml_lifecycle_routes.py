"""Bounded ML lifecycle API. Filesystem import is CLI-only."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.routing import APIRoute

from app.ml_lifecycle import adapters, service
from app.ml_lifecycle.identity import MAX_BYTES, read_json
from app.ml_lifecycle.models import LinkRequest, Registration

class StrictJSONRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def checked(request: Request):
            if request.method == "POST":
                body = await request.body()
                if body:
                    try:
                        if len(body) > MAX_BYTES:
                            raise ValueError("oversized request")
                        read_json(body)
                    except ValueError as exc:
                        raise HTTPException(422, "Lifecycle requests require bounded, unambiguous JSON.") from exc
            return await handler(request)

        return checked


router = APIRouter(prefix="/ml-lifecycles", tags=["ML Research Lifecycle"], route_class=StrictJSONRoute)


def call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except service.NotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, LookupError, RuntimeError) as exc:
        raise HTTPException(422, "Lifecycle validation/action failed. Inspect provenance and adapter state.") from exc


@router.get("")
def listing(page: int = Query(1, ge=1, le=10000), page_size: int = Query(20, ge=1, le=50),
            completeness: Literal["complete", "incomplete"] | None = None,
            integrity: Literal["intact", "changed"] | None = None):
    return call(service.list_runs, page, page_size, completeness, integrity)


@router.post("", status_code=201)
def register(request: Registration):
    return call(service.register, request.model_dump(mode="json"))


@router.post("/demo")
def demo():
    return call(service.demo)


@router.get("/compare")
def compare(a: int = Query(..., gt=0), b: int = Query(..., gt=0)):
    return call(service.compare, a, b)


@router.get("/{run_id}")
def detail(run_id: int):
    return call(service.get_run, run_id)


@router.get("/{run_id}/export")
def export(run_id: int):
    return call(service.export, run_id)


@router.post("/{run_id}/links")
def link(run_id: int, request: LinkRequest):
    return call(service.link, run_id, request.adapter)


@router.get("/{run_id}/links/{adapter}")
def linked_detail(run_id: int, adapter: Literal["validation", "calibration", "features", "costs", "decay"]):
    record = call(service.get_run, run_id)
    link = next((r for r in record["links"] if r["adapter"] == adapter), None)
    if link is None or link["destination_id"] is None:
        raise HTTPException(404, "Diagnostic record unavailable")
    if record["integrity"] != "intact" or link["integrity"] != "intact":
        raise HTTPException(409, "Diagnostic content changed; inspect it in the source lab")
    return {"adapter": adapter, "content_hash": link["content_hash"],
            "record": call(adapters.ADAPTERS[adapter][0].get_run, link["destination_id"])}
