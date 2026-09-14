"""User-started, disposable ASGI harness for Phase 64 browser verification.

This module is never imported by the production application. Run a single
worker without reload; retained temporary data belongs only to this harness.
"""
from __future__ import annotations

import hmac
import importlib
import os
from pathlib import Path
import re
import sys
import tempfile

PREFIX = "quantlab-strategy-ensemble-e2e-"
HEADER = "x-quantlab-e2e-token"
IDENTITY_PATH = "/strategy-ensembles/e2e-isolation"


class IsolationError(RuntimeError):
    pass


class DisposableIdentity:
    def __init__(self, root: Path, token: str, checkout: Path):
        self.root = root.resolve(strict=True)
        self.checkout = checkout.resolve(strict=True)
        if self.root.is_relative_to(self.checkout) or not self.root.name.startswith(PREFIX):
            raise IsolationError("E2E storage must be harness-owned and outside the checkout")
        if not re.fullmatch(r"[a-f0-9]{64}", token):
            raise IsolationError("E2E_STRATEGY_ENSEMBLE_TOKEN must be 64 lowercase hex characters")
        self.token = token
        self.database = self.root / "browser.sqlite3"
        self.marker = self.root / "isolation-token.txt"
        # Exclusive creation prevents adopting an existing database or marker.
        with self.database.open("xb"):
            pass
        stat = self.database.stat()
        self.database_file_identity = (stat.st_dev, stat.st_ino)
        with self.marker.open("x", encoding="utf-8") as handle:
            handle.write(token)

    def verify(self, db, *, inspect_connection: bool = True) -> dict:
        if self.root.resolve(strict=True) != self.root or self.root.is_relative_to(self.checkout):
            raise IsolationError("E2E storage identity changed")
        if (self.database.is_symlink() or self.marker.is_symlink()
                or self.database.resolve(strict=True) != self.database
                or self.marker.resolve(strict=True) != self.marker
                or self.database.stat().st_nlink != 1
                or (self.database.stat().st_dev, self.database.stat().st_ino) != self.database_file_identity):
            raise IsolationError("E2E storage must not be linked or redirected")
        if not hmac.compare_digest(self.marker.read_text(encoding="utf-8"), self.token):
            raise IsolationError("E2E ownership marker changed")
        # Check before opening any connection so a changed override is never used.
        if Path(db.get_db_path()).resolve(strict=True) != self.database:
            raise IsolationError("Serving backend database is not the disposable database")
        if inspect_connection:
            conn = db.get_connection()
            try:
                locations = {row[1]: row[2] for row in conn.execute("PRAGMA database_list")}
                if set(locations) != {"main"} or Path(locations["main"]).resolve(strict=True) != self.database:
                    raise IsolationError("Serving connection does not use the disposable database")
            finally:
                conn.close()
        return {"kind": "quantlab_strategy_ensemble_disposable_v1", "token": self.token,
                "database_identity": self.root.name, "database_verified": True}


def create_app():
    """ASGI factory, intentionally called only by a user-owned service command."""
    from fastapi import FastAPI
    from starlette.responses import JSONResponse

    checkout = Path(__file__).resolve().parents[1]
    token = os.environ.get("E2E_STRATEGY_ENSEMBLE_TOKEN", "")
    if not re.fullmatch(r"[a-f0-9]{64}", token):
        raise IsolationError("E2E_STRATEGY_ENSEMBLE_TOKEN must be 64 lowercase hex characters")
    temporary_root = Path(tempfile.gettempdir()).resolve(strict=True)
    if temporary_root.is_relative_to(checkout):
        raise IsolationError("OS temporary directory must be outside the checkout")
    if "app.main" in sys.modules:
        raise IsolationError("Start the E2E factory in a fresh process before importing app.main")
    root = Path(tempfile.mkdtemp(prefix=PREFIX, dir=temporary_root))
    identity = DisposableIdentity(root, token, checkout)
    sys.path.insert(0, str(checkout / "backend"))
    db = importlib.import_module("app.db")
    db._db_path_override = identity.database
    identity.verify(db, inspect_connection=False)
    application: FastAPI = importlib.import_module("app.main").app

    @application.middleware("http")
    async def require_isolation(request, call_next):
        if request.url.path.startswith("/strategy-ensembles"):
            if not hmac.compare_digest(request.headers.get(HEADER, ""), token):
                return JSONResponse({"detail": "E2E isolation token required"}, status_code=409)
            try:
                identity.verify(db)
            except (IsolationError, OSError, ValueError):
                return JSONResponse({"detail": "E2E database isolation verification failed"}, status_code=409)
        return await call_next(request)

    @application.get(IDENTITY_PATH, include_in_schema=False)
    def isolation_identity():
        return identity.verify(db)

    application.state.strategy_ensemble_e2e_identity = identity
    return application
