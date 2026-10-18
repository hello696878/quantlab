"""Operator-selected serving entry point; no database/provider work at import."""
import os

SCHEMA = "serving_capabilities_v1"
CORPUS_HEADER = b"x-quantlab-expected-corpus"
LOCAL_CAPABILITIES = {
    "schema": SCHEMA, "mode": "local", "policy": "local_v1",
    "corpus_id": None, "synthetic": False, "capabilities": ["local_research"],
}


class RejectDemoPrecondition:
    """A stale demo client must not fall through to ordinary saved user data."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and any(key.lower() == CORPUS_HEADER for key, value in scope.get("headers", [])):
            from starlette.responses import JSONResponse
            return await JSONResponse({"detail": "Serving mode changed; reload before browsing"}, status_code=409,
                                      headers={"Cache-Control": "no-store"})(scope, receive, send)
        return await self.app(scope, receive, send)


def serving_mode(environ=None):
    env = os.environ if environ is None else environ
    mode = env.get("QUANTLAB_SERVING_MODE", "local")
    if mode not in ("local", "read_only_demo"):
        raise ValueError("Unsupported serving mode configuration")
    demo_keys = {key for key in env if key.startswith("QUANTLAB_DEMO_")}
    if mode == "local" and demo_keys:
        raise ValueError("Demo configuration requires explicit demo mode")
    if demo_keys - {"QUANTLAB_DEMO_CORPUS", "QUANTLAB_DEMO_CORPUS_ID", "QUANTLAB_DEMO_HOSTS", "QUANTLAB_DEMO_ORIGINS"}:
        raise ValueError("Unknown demo configuration")
    return mode


def guard_local_entrypoint():
    if serving_mode() != "local":
        raise ValueError("Use app.serving:create_app --factory for demo serving")


def create_app():
    if serving_mode() == "read_only_demo":
        from app.read_only_demo import create_demo_app, DemoConfig
        return create_demo_app(DemoConfig.from_env())
    from app.main import app
    return app
