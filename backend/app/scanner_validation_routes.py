"""Explicit compute only; no list/GET seeding, persistence or active database access."""
from fastapi import APIRouter, HTTPException

from app.scanner.validation import ScannerValidationRequest, ScannerValidationResponse, run_scanner_validation

router = APIRouter(prefix="/scanner", tags=["scanner"])


@router.post("/validate", response_model=ScannerValidationResponse)
def validate_scanner(request: ScannerValidationRequest):
    try:
        return run_scanner_validation(request)
    except (ValueError, ArithmeticError) as exc:
        raise HTTPException(status_code=422, detail="Scanner validation refused: check bounded dates, candidate policies and keyed declarations") from exc
