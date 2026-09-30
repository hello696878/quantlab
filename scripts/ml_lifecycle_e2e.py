"""User-started Phase 65 harness, reusing the verified disposable DB factory."""

import hmac

from scripts.strategy_ensemble_e2e import IsolationError, HEADER, create_app as base_app


def create_app():
    from starlette.responses import JSONResponse

    application = base_app()
    from app import db
    identity = application.state.strategy_ensemble_e2e_identity

    @application.middleware("http")
    async def guard_lifecycle(request, call_next):
        if request.url.path.startswith("/ml-lifecycles"):
            if not hmac.compare_digest(request.headers.get(HEADER, ""), identity.token):
                return JSONResponse({"detail": "Disposable lifecycle harness token required"}, status_code=409)
            try:
                identity.verify(db)
            except (IsolationError, OSError, ValueError):
                return JSONResponse({"detail": "Disposable lifecycle database verification failed"}, status_code=409)
        return await call_next(request)

    @application.get("/ml-lifecycles/e2e/isolation", include_in_schema=False)
    def proof():
        return {**identity.verify(db), "kind": "quantlab_ml_lifecycle_disposable_v1"}

    return application
