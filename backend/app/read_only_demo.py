"""Deny-by-default ASGI policy around a separate, provider-free browsing app."""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse
from starlette.routing import compile_path

from app import demo_corpus as corpus
from app.run_replay.identity import full_hash
from app.serving import CORPUS_HEADER, SCHEMA

POLICY = "read_only_demo_v1"
ROUTES = ("/health", "/ready", "/capabilities", "/saved-backtests",
          "/saved-backtests/{saved_id}", "/research-explainer/saved-backtests/{saved_id}")
MATCHERS = tuple((path, compile_path(path)[0]) for path in ROUTES)
HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
           "Referrer-Policy": "no-referrer", "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'"}
logger = logging.getLogger("quantlab.demo")


@dataclass(frozen=True)
class DemoConfig:
    directory: Path
    expected_id: str
    hosts: tuple[str, ...] = ("localhost", "127.0.0.1")
    origins: tuple[str, ...] = ()

    def __post_init__(self):
        corpus.unlinked(self.directory)
        full_hash(self.expected_id)
        if not self.hosts or len(self.hosts) > 8 or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", h) for h in self.hosts):
            raise ValueError("Invalid demo allowed hosts")
        if len(self.origins) > 8:
            raise ValueError("Too many demo origins")
        for origin in self.origins:
            parsed = urlsplit(origin)
            if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or origin != f"{parsed.scheme}://{parsed.netloc}":
                raise ValueError("Invalid demo origin")

    @classmethod
    def from_env(cls):
        try:
            return cls(Path(os.environ["QUANTLAB_DEMO_CORPUS"]), os.environ["QUANTLAB_DEMO_CORPUS_ID"],
                       tuple(os.environ.get("QUANTLAB_DEMO_HOSTS", "localhost,127.0.0.1").split(",")),
                       tuple(filter(None, os.environ.get("QUANTLAB_DEMO_ORIGINS", "").split(","))))
        except (KeyError, ValueError, OSError):
            raise ValueError("Invalid explicit demo configuration") from None


class Admission:
    """One event-loop/process bucket, no client identifiers; never trusts XFF."""
    def __init__(self, clock=time.monotonic, *, burst=60, rate=1, concurrency=2):
        self.clock, self.burst, self.rate, self.concurrency = clock, burst, rate, concurrency
        self.tokens, self.active, self.last = float(burst), 0, clock()

    def enter(self):
        now = self.clock()
        self.tokens = min(self.burst, self.tokens + max(0, now - self.last) * self.rate)
        self.last = now
        if self.active >= self.concurrency or self.tokens < 1:
            return False
        self.tokens -= 1
        self.active += 1
        return True

    def leave(self):
        self.active -= 1


class DemoApplication:
    def __init__(self, app, config, admission):
        self.app, self.config, self.admission = app, config, admission

    @property
    def routes(self):
        return self.app.routes

    def classify(self, scope):
        path = scope.get("path", "")
        raw = scope.get("raw_path", path.encode("ascii", errors="replace"))
        if scope.get("root_path") or len(raw) > 160 or len(path) > 160 or not path.isascii() or raw != path.encode("ascii"):
            return None
        if "%" in path or "\\" in path or scope.get("method") != "GET":
            return None
        for pattern, matcher in MATCHERS:
            matched = matcher.fullmatch(path)
            if matched:
                saved_id = matched.groupdict().get("saved_id")
                if saved_id is not None and saved_id != "1":
                    return None
                return pattern
        return None

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        if scope["type"] != "http":
            return
        started, status = False, 500

        async def safe_send(message):
            nonlocal started, status
            if message["type"] == "http.response.start":
                started, status = True, message["status"]
                blocked = {name.lower().encode() for name in HEADERS}
                message = dict(message, headers=[(k, v) for k, v in message.get("headers", []) if k.lower() not in blocked]
                               + [(k.lower().encode(), v.encode()) for k, v in HEADERS.items()])
            await send(message)

        async def refuse(code, detail, headers=None):
            await JSONResponse({"detail": detail}, status_code=code, headers=headers)(scope, receive, safe_send)

        pattern = self.classify(scope)
        if pattern is None:
            return await refuse(403, "Operation unavailable in read-only demo")
        headers = scope.get("headers", [])
        if len(headers) > 100 or sum(len(k) + len(v) for k, v in headers) > 8192:
            return await refuse(431, "Request headers exceed demo bounds")
        expected = [v for k, v in headers if k.lower() == CORPUS_HEADER]
        if expected and expected != [self.config.expected_id.encode("ascii")]:
            return await refuse(409, "Prepared corpus changed; reload before browsing")
        hosts = [v for k, v in headers if k.lower() == b"host"]
        origins = [v for k, v in headers if k.lower() == b"origin"]
        if (len(hosts) != 1 or not re.fullmatch(rb"[a-z0-9.-]+(?::[0-9]{1,5})?", hosts[0])
                or hosts[0].decode().split(":")[0] not in self.config.hosts):
            return await refuse(400, "Host is not approved for demo")
        if len(origins) > 1 or (origins and origins[0].decode("ascii", errors="replace") not in self.config.origins):
            return await refuse(403, "Origin is not approved for demo")
        query = scope.get("query_string", b"")
        if len(query) > 256 or (query and not (pattern == ROUTES[-1] and re.fullmatch(rb"expected=[0-9a-f]{64}", query))):
            return await refuse(422, "Unsupported demo query")
        lengths = [v for k, v in headers if k.lower() == b"content-length"]
        if any(k.lower() == b"transfer-encoding" for k, v in headers) or (lengths and lengths != [b"0"]):
            return await refuse(400, "Request bodies are not accepted in demo")
        if not self.admission.enter():
            return await refuse(429, "Demo admission limit reached", {"Retry-After": "1"})
        try:
            # Read at most one ASGI frame, never accumulate or parse an upload.
            frame = await asyncio.wait_for(receive(), timeout=1)
            if frame.get("type") != "http.request" or frame.get("body") or frame.get("more_body"):
                return await refuse(400, "Request bodies are not accepted in demo")
            first = True

            async def replay_receive():
                nonlocal first
                if first:
                    first = False
                    return frame
                return await receive()

            await self.app(scope, replay_receive, safe_send)
        except asyncio.TimeoutError:
            if not started:
                await refuse(408, "Demo request timed out before dispatch")
        except Exception:
            if not started:
                await refuse(503, "Prepared demo content is unavailable")
        finally:
            self.admission.leave()
            logger.info("demo_request", extra={"policy": POLICY, "route_pattern": pattern, "status_code": status})


def create_demo_app(config, *, admission=None):
    @asynccontextmanager
    async def lifespan(app):
        try:
            observation = corpus.observe(config.directory)
            manifest, record, explanation = corpus.verify(config.directory, config.expected_id)
            if corpus.observe(config.directory) != observation:
                raise ValueError("Changed during startup")
        except Exception:
            raise ValueError("Prepared demo corpus refused at startup") from None
        app.state.manifest, app.state.record, app.state.explanation = manifest, record, explanation
        app.state.observation = observation
        yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None, debug=False,
                  redirect_slashes=False)

    def current():
        try:
            if corpus.observe(config.directory) != app.state.observation:
                raise ValueError("Changed")
        except Exception:
            from fastapi import HTTPException
            raise HTTPException(503, "Prepared demo content is unavailable") from None

    @app.get("/health")
    def live():
        return {"status": "ok"}

    @app.get("/ready")
    def ready():
        current()
        return {"status": "ready", "policy": POLICY, "corpus_id": config.expected_id}

    @app.get("/capabilities")
    def capabilities():
        current()
        return {"schema": SCHEMA, "mode": "read_only_demo", "policy": POLICY, "corpus_id": config.expected_id,
                "synthetic": True, "capabilities": ["browse_saved_sma", "explain_saved_sma"]}

    @app.get("/saved-backtests")
    def saved_list():
        current()
        return [{key: app.state.record[key] for key in corpus.SUMMARY}]

    @app.get("/saved-backtests/{saved_id}")
    def detail(saved_id: str):
        current()
        return app.state.record

    @app.get("/research-explainer/saved-backtests/{saved_id}")
    def explanation(saved_id: str, request: Request):
        current()
        expected = request.query_params.get("expected")
        if expected is not None and expected != app.state.explanation["fingerprint"]:
            from fastapi import HTTPException
            raise HTTPException(409, "Stored source changed or failed integrity checks")
        return app.state.explanation

    return DemoApplication(app, config, admission if admission is not None else Admission())
