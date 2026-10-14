"""Explicit compute only; no list/GET seeding, persistence or active database access."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute

from app.run_replay.identity import loads
from app.scanner.validation import ScannerValidationRequest, ScannerValidationResponse, run_scanner_validation

MAX_REQUEST_BYTES = 4 * 1024 * 1024
REFUSAL = "Scanner validation refused: check bounded dates, candidate policies and keyed declarations"


class _ValidationRoute(APIRoute):
    """Bound and sanitize this route before FastAPI's typed body validation."""
    def get_route_handler(self):
        original = super().get_route_handler()

        async def guarded(request: Request):
            raw = bytearray()
            async for chunk in request.stream():
                if len(raw) + len(chunk) > MAX_REQUEST_BYTES:
                    raise HTTPException(status_code=422, detail="Scanner validation request exceeds the 4 MiB bound")
                raw.extend(chunk)
            try:
                # Reject duplicate keys, nonfinite values, excessive depth/nodes
                # before typed coercion can discard ambiguous request material.
                loads(bytes(raw), limit=MAX_REQUEST_BYTES)
                request._body = bytes(raw)
                return await original(request)
            except (RequestValidationError, ValueError, ArithmeticError) as exc:
                raise HTTPException(status_code=422, detail=REFUSAL) from exc

        return guarded


router = APIRouter(prefix="/scanner", tags=["scanner"], route_class=_ValidationRoute)


@router.post("/validate", response_model=ScannerValidationResponse)
def validate_scanner(request: ScannerValidationRequest):
    try:
        return run_scanner_validation(request)
    except (ValueError, ArithmeticError) as exc:
        raise HTTPException(status_code=422, detail=REFUSAL) from exc
