from fastapi import APIRouter, HTTPException, Query

from app.market_monitor.catalog import BY_ID, CATALOG, DEFAULT_IDS
from app.market_monitor.models import Snapshot
from app.market_monitor.service import MonitorService

router = APIRouter(prefix="/market-monitor", tags=["market-monitor"])
_service = None


def get_service():
    global _service
    if _service is None:
        _service = MonitorService()
    return _service


@router.get("/catalog")
def catalog():
    return {"instruments": CATALOG, "default_ids": DEFAULT_IDS, "max_watchlist": 16, "refresh_seconds": 300}


@router.get("/snapshot", response_model=Snapshot)
async def snapshot(ids: str = Query(default=",".join(DEFAULT_IDS), max_length=300), company: str | None = Query(default=None, max_length=10)):
    selected = [] if ids == "" else ids.split(",")
    try:
        return await get_service().snapshot(selected, company)
    except ValueError:
        raise HTTPException(422, "Use at most 16 unique supported Monitor IDs and a supported company ID.") from None
