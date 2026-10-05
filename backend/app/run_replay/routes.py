"""Small explicit endpoints; local execution is never a GET side effect."""
from fastapi import APIRouter, HTTPException, Path, Query, Request
from fastapi.routing import APIRoute
from . import service
from .identity import loads


async def strict_body(request, limit=256 * 1024):
    chunks = bytearray()
    async for chunk in request.stream():
        chunks.extend(chunk)
        if len(chunks) > limit:
            raise ValueError("Request exceeds JSON size bound")
    request.state.replay_body = bytes(chunks)
    return loads(request.state.replay_body, limit=limit)


async def original_sma_request(request: Request):
    # Preserve raw representation when strict capture is possible. This does
    # not tighten or change the legacy backtest endpoint's accepted requests.
    from .adapter import request_model
    try:
        raw = await strict_body(request, 32768)
        request_model(raw)
        return raw
    except ValueError:
        return None


class ReplayRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def checked(request):
            try:
                return await handler(request)
            except service.Missing as exc:
                raise HTTPException(404, str(exc)) from exc
            except service.Changed as exc:
                raise HTTPException(409, str(exc)) from exc
            except (ValueError, KeyError, TypeError) as exc:
                raise HTTPException(422, str(exc)) from exc
        return checked


class BoundedSaveRoute(ReplayRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def bounded(request):
            try:
                await strict_body(request, 4 * 1024 * 1024)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            body = request.state.replay_body

            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}
            return await handler(Request(request.scope, receive=receive))
        return bounded


saved_router = APIRouter(route_class=BoundedSaveRoute)


router = APIRouter(prefix="/run-replay", tags=["run replay"], route_class=ReplayRoute)


@router.get("/hash/{config_hash}")
def resolve(config_hash: str, page: int = Query(1, ge=1, le=1000), page_size: int = Query(20, ge=1, le=50)):
    return service.resolve_hash(config_hash, page, page_size)


@router.get("/contexts/{context_id}")
def preflight(context_id: int = Path(ge=1, le=2**31 - 1)):
    return service.preflight(context_id)


@router.get("/contexts/{context_id}/export")
def export(context_id: int = Path(ge=1, le=2**31 - 1)):
    return service.export_context(context_id)


@router.post("/register/{saved_id}")
def register(saved_id: int = Path(ge=1, le=2**31 - 1)):
    return service.register_legacy(saved_id)


@router.post("/demo")
def demo():
    return service.demo()


@router.post("/contexts/{context_id}/check-input")
async def check_input(request: Request, context_id: int = Path(ge=1, le=2**31 - 1)):
    raw = await strict_body(request)
    if type(raw) is not dict or set(raw) != {"csv_text"}:
        raise ValueError("Expected only csv_text")
    return service.check_input(context_id, raw["csv_text"])


@router.post("/contexts/{context_id}/execute-local")
async def execute_local(request: Request, context_id: int = Path(ge=1, le=2**31 - 1)):
    raw = await strict_body(request)
    if type(raw) is not dict or set(raw) - {"request", "csv_text"} or "request" not in raw:
        raise ValueError("Expected request and optional csv_text")
    return service.execute_local(context_id, raw["request"], raw.get("csv_text"))
