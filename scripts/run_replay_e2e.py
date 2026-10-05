"""User-started Phase 66 harness; every replay/save request checks DB ownership."""
import hmac
from scripts.strategy_ensemble_e2e import HEADER, IsolationError, create_app as base_app


def create_app():
    from starlette.responses import JSONResponse
    application = base_app()
    from app import db
    identity = application.state.strategy_ensemble_e2e_identity

    @application.middleware("http")
    async def guard(request, call_next):
        if request.url.path.startswith(("/run-replay", "/saved-backtests")):
            if not hmac.compare_digest(request.headers.get(HEADER, ""), identity.token):
                return JSONResponse({"detail": "E2E isolation token required"}, status_code=409)
            try:
                identity.verify(db)
            except (IsolationError, OSError, ValueError):
                return JSONResponse({"detail": "E2E disposable database verification failed"}, status_code=409)
        return await call_next(request)

    @application.get("/run-replay/e2e/isolation", include_in_schema=False)
    def proof():
        value = identity.verify(db)
        value["kind"] = "quantlab_run_replay_disposable_v1"
        return value
    return application
