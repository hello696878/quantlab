"""Fixed allowlisted read endpoint; exports download the pinned client bundle."""
from fastapi import APIRouter, HTTPException, Request, Response
from . import service
from .contract import Explanation

router = APIRouter(prefix="/research-explainer", tags=["research explainer"])


@router.get("/saved-backtests/{saved_id}", response_model=Explanation)
def explain(saved_id: str, request: Request, response: Response, expected: str | None = None):
    # Keep public errors bounded and free of submitted values or server paths.
    try:
        if len(request.url.query) > 256 or set(request.query_params) - {"expected"} or len(request.query_params.getlist("expected")) > 1:
            raise ValueError("Unsupported request fields")
        if not saved_id.isascii() or not saved_id.isdecimal() or saved_id.startswith("0") or len(saved_id) > 10:
            raise ValueError("Invalid ID")
        response.headers["Cache-Control"] = "no-store"
        return service.explain(int(saved_id), expected)
    except service.Missing as exc:
        raise HTTPException(404, "Stored source not found or unavailable") from exc
    except service.Changed as exc:
        raise HTTPException(409, "Stored source changed or failed integrity checks") from exc
    except (service.Unavailable, ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, "Stored source, fields or request are unsupported") from exc
