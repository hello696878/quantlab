"""Owned real SQLite, actual ASGI policy and no-provider regression coverage."""
import asyncio
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from fastapi import Depends
from fastapi.testclient import TestClient
import pytest

from app import db, demo_corpus as corpus, main, saved_backtests, serving
from app.read_only_demo import Admission, DemoApplication, DemoConfig, POLICY, ROUTES, create_demo_app
from app.run_replay.identity import digest, validate

pytestmark = pytest.mark.usefixtures("isolated_lab_db")


@pytest.mark.db_free
def test_container_context_rules_exclude_private_runtime_material():
    root = Path(__file__).resolve().parents[2]
    backend = set((root / "backend/.dockerignore").read_text().splitlines())
    frontend = set((root / "frontend/.dockerignore").read_text().splitlines())
    assert {".env", ".env.*", "!.env.example", "data/", "*.db", "*.db-*"} <= backend
    assert {".env", ".env.*", "!.env.example", "node_modules/", ".next/"} <= frontend


def prepared(tmp_path):
    path = tmp_path / "public"
    identity = corpus.prepare(path)
    return path, identity, DemoConfig(path, identity, hosts=("testserver",))


def contents(path):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in path.iterdir() if p.is_file()}


def forbid(*args, **kwargs):
    pytest.fail("Demo attempted ordinary initialization, writable storage or provider work")


def test_real_prepare_verify_and_offline_backup_restore(tmp_path):
    path, identity, _ = prepared(tmp_path)
    before = contents(path)
    manifest, record, explanation = corpus.verify(path, identity)
    assert manifest["schema"] == corpus.SCHEMA and manifest["saved_ids"] == [1]
    assert record["ticker"] == "SYNTHETIC" and len(record["equity_curve"]) == 180
    assert record["trades"] and record["metrics"]["num_days"] == 180
    assert explanation["identity"]["trust"] == "legacy_unverified"
    backup, restored = tmp_path / "backup", tmp_path / "restored"
    corpus.copy_stopped(path, backup, identity, stopped=True)
    corpus.copy_stopped(backup, restored, identity, stopped=True)
    assert contents(path) == contents(backup) == contents(restored) == before
    assert db.get_db_path() != path / corpus.DB_NAME


@pytest.mark.parametrize("operation", ["prepare", "copy"])
def test_offline_destination_collision_does_not_overwrite(tmp_path, operation):
    path, identity, _ = prepared(tmp_path)
    before = contents(path)
    with pytest.raises(FileExistsError):
        if operation == "prepare": corpus.prepare(path)
        else: corpus.copy_stopped(path, path, identity, stopped=True)
    assert contents(path) == before


def test_copy_requires_explicit_stopped_confirmation(tmp_path):
    path, identity, _ = prepared(tmp_path)
    with pytest.raises(ValueError): corpus.copy_stopped(path, tmp_path / "copy", identity)
    assert not (tmp_path / "copy").exists()


def test_operator_corpus_link_refused_before_read(tmp_path, monkeypatch):
    from .test_backend_runner_review import directory_link
    path, identity, _ = prepared(tmp_path)
    linked = tmp_path / "linked-public"
    directory_link(linked, path)
    monkeypatch.setattr(corpus.explainer, "_storage_state", forbid)
    with pytest.raises(ValueError, match="Linked corpus paths"):
        corpus.verify(linked, identity)


def test_interrupted_preparation_retains_unservable_owned_destination(tmp_path, monkeypatch):
    path = tmp_path / "partial"
    monkeypatch.setattr(db, "init_db", lambda **kw: (_ for _ in ()).throw(OSError("controlled")))
    with pytest.raises(OSError): corpus.prepare(path)
    assert path.is_dir() and not (path / corpus.MANIFEST).exists()
    with pytest.raises((OSError, ValueError)): corpus.verify(path, "a" * 64)


@pytest.mark.parametrize("mode", ["", "demo", "READ_ONLY_DEMO", " read_only_demo", "false"])
def test_invalid_explicit_mode_fails_closed(monkeypatch, mode):
    monkeypatch.setenv("QUANTLAB_SERVING_MODE", mode)
    with pytest.raises(ValueError, match="configuration"): serving.create_app()


def test_default_local_mode_and_existing_startup(monkeypatch):
    monkeypatch.delenv("QUANTLAB_SERVING_MODE", raising=False)
    assert serving.create_app() is main.app
    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/capabilities").json() == serving.LOCAL_CAPABILITIES
        assert client.get("/saved-backtests").status_code == 200


def test_demo_config_and_wrong_entrypoint_fail_closed(monkeypatch):
    monkeypatch.setenv("QUANTLAB_SERVING_MODE", "read_only_demo")
    monkeypatch.delenv("QUANTLAB_DEMO_CORPUS", raising=False)
    with pytest.raises(ValueError, match="configuration"): serving.create_app()
    with pytest.raises(ValueError, match="factory"): serving.guard_local_entrypoint()


@pytest.mark.parametrize("env", [{"QUANTLAB_DEMO_CORPUS": "private"},
    {"QUANTLAB_SERVING_MODE": "read_only_demo", "QUANTLAB_DEMO_TYPO": "private"}])
def test_partial_or_unknown_operator_configuration_never_falls_back(env):
    with pytest.raises(ValueError): serving.serving_mode(env)


@pytest.mark.parametrize("hosts,origins", [((), ()), (("*",), ()), (("testserver:80",), ()), (("testserver",), ("https://example.test/path",))])
def test_invalid_host_origin_configuration(tmp_path, hosts, origins):
    with pytest.raises(ValueError): DemoConfig(tmp_path, "a" * 64, hosts=hosts, origins=origins)


def test_missing_corpus_never_created_or_falls_back(tmp_path, monkeypatch):
    missing = tmp_path / "missing"
    monkeypatch.setattr(db, "get_db_path", forbid)
    monkeypatch.setattr(db, "init_db", forbid)
    with pytest.raises(ValueError, match="refused at startup"):
        with TestClient(create_demo_app(DemoConfig(missing, "a" * 64))): pass
    assert not missing.exists()


def test_replacement_after_verification_cannot_become_startup_baseline(tmp_path, monkeypatch):
    path, _, config = prepared(tmp_path)
    original = corpus.verify
    def replaced(*args, **kwargs):
        result = original(*args, **kwargs)
        with (path / corpus.DB_NAME).open("ab") as handle: handle.write(b"replacement")
        return result
    monkeypatch.setattr(corpus, "verify", replaced)
    with pytest.raises(ValueError, match="refused at startup"):
        with TestClient(create_demo_app(config)): pass


def test_startup_reads_are_ro_and_requests_never_initialize_or_call_providers(tmp_path, monkeypatch):
    path, identity, config = prepared(tmp_path)
    before = contents(path)
    calls = []
    real = sqlite3.connect
    def connect(database, *args, **kwargs):
        calls.append((database, kwargs))
        return real(database, *args, **kwargs)
    monkeypatch.setattr(sqlite3, "connect", connect)
    import yfinance
    from app import globe_routes
    monkeypatch.setenv("GLOBE_FRED_ENABLED", "true")
    monkeypatch.setenv("FRED_API_KEY", "dummy-never-used")
    monkeypatch.setenv("GLOBE_QUOTES_ENABLED", "true")
    for module, names in [(db, ["get_db_path", "init_db", "get_connection"]),
                          (saved_backtests, ["get_saved_backtest", "list_saved_backtests", "create_saved_backtest"]),
                          (main, ["_fetch", "init_db", "run_backtest"]),
                          (globe_routes, ["build_markets_response", "build_single_market"]), (yfinance, ["download", "Ticker"])]:
        for name in names: monkeypatch.setattr(module, name, forbid)
    app = create_demo_app(config)
    with TestClient(app) as client:
        initial_connections = len(calls)
        assert initial_connections >= 2
        assert all(str(p).endswith("?mode=ro") and kw.get("uri") is True for p, kw in calls)
        for route in ROUTES:
            response = client.get(route.replace("{saved_id}", "1"))
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["x-content-type-options"] == "nosniff"
            assert str(path) not in response.text and "dummy-never-used" not in response.text
        assert client.get("/capabilities").json()["corpus_id"] == identity
        assert len(calls) == initial_connections
        for route in ("/globe/markets", "/globe/markets/us", "/backtest/sma-crossover", "/run-replay/demo", "/saved-reports", "/docs", "/openapi.json"):
            assert client.get(route).status_code == 403
        assert client.post("/backtest/sma-crossover", json={}).status_code == 403
    assert contents(path) == before and set(before) == {corpus.DB_NAME, corpus.MANIFEST}


def test_actual_route_inventory_drift_and_new_routes_deny_before_dependencies(tmp_path):
    _, _, config = prepared(tmp_path)
    wrapped = create_demo_app(config)
    assert len(wrapped.routes) == len(ROUTES)
    assert {(r.path, frozenset(r.methods)) for r in wrapped.routes} == {(p, frozenset({"GET"})) for p in ROUTES}
    @wrapped.app.get("/new-unclassified", dependencies=[Depends(forbid)])
    def unknown(): return forbid()
    wrapped.app.mount("/mounted", wrapped.app.__class__())
    with TestClient(wrapped) as client:
        assert client.get("/new-unclassified").status_code == 403
        assert client.get("/mounted/health").status_code == 403
        for route in main.app.routes:
            for method in getattr(route, "methods", ()):
                sample = route.path
                import re
                sample = re.sub(r"\{[^}]+\}", "1", sample)
                if method == "GET" and sample in ("/health", "/capabilities", "/saved-backtests", "/saved-backtests/1", "/research-explainer/saved-backtests/1"):
                    continue
                assert client.request(method, sample, follow_redirects=False).status_code == 403, (method, sample)


@pytest.mark.parametrize("path,method", [("/saved-backtests/", "GET"), ("/saved-backtests/01", "GET"),
    ("/saved-backtests/2", "GET"), ("/saved-backtests/1/other", "GET"), ("/health", "HEAD"),
    ("/health", "OPTIONS"), ("/saved-backtests", "POST"), ("/saved-backtests/1", "DELETE"),
    ("/saved-backtests/1/replay", "POST")])
def test_path_and_method_variants_are_denied(tmp_path, path, method):
    _, _, config = prepared(tmp_path)
    with TestClient(create_demo_app(config)) as client:
        assert client.request(method, path, follow_redirects=False).status_code == 403


async def asgi_call(app, *, path="/health", raw=None, method="GET", body=b"", more=False, query=b"", headers=None, root_path=""):
    messages, reads = [], []
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "scheme": "http",
             "path": path, "raw_path": raw if raw is not None else path.encode(), "root_path": root_path,
             "query_string": query, "method": method, "headers": headers or [(b"host", b"testserver")], "server": ("testserver", 80)}
    async def receive():
        reads.append(1)
        return {"type": "http.request", "body": body, "more_body": more}
    async def send(message): messages.append(message)
    await app(scope, receive, send)
    return messages, reads


@pytest.mark.parametrize("changes", [{"raw": b"/%68ealth"}, {"path": "/saved-backtests/1", "raw": b"/saved-backtests%2f1"},
    {"root_path": "/mounted"}, {"path": "/health/"}, {"path": "/health", "method": "POST"}])
def test_early_policy_refuses_without_reading_body(tmp_path, changes):
    _, _, config = prepared(tmp_path)
    messages, reads = asyncio.run(asgi_call(create_demo_app(config), body=b"x" * 100000, **changes))
    assert messages[0]["status"] == 403 and reads == []


def test_query_header_host_origin_and_untruthful_body_bounds(tmp_path):
    _, _, config = prepared(tmp_path)
    app = create_demo_app(config)
    with TestClient(app) as client:
        for query in ("x=secret", "expected=a", "expected=" + "a" * 64 + "&expected=" + "b" * 64, "x=" + "z" * 300):
            response = client.get("/research-explainer/saved-backtests/1?" + query)
            assert response.status_code == 422 and "secret" not in response.text
        assert client.get("/health", headers={"Host": "evil.invalid"}).status_code == 400
        assert client.get("/health", headers={"Origin": "https://evil.invalid"}).status_code == 403
        assert client.get("/health", headers={"X-Noise": "z" * 9000}).status_code == 431
    messages, reads = asyncio.run(asgi_call(app, body=b"x" * 100000, headers=[(b"host", b"testserver"), (b"content-length", b"0")]))
    assert messages[0]["status"] == 400 and len(reads) == 1


@pytest.mark.parametrize("change", ["database", "manifest", "sidecar"])
def test_changed_corpus_readiness_refuses_but_liveness_is_not_database_health(tmp_path, change):
    path, _, config = prepared(tmp_path)
    with TestClient(create_demo_app(config)) as client:
        if change == "database":
            with (path / corpus.DB_NAME).open("ab") as handle: handle.write(b"changed")
        elif change == "manifest": (path / corpus.MANIFEST).write_text("private filesystem secret")
        else: (path / (corpus.DB_NAME + "-wal")).write_bytes(b"")
        for route in ("/ready", "/capabilities", "/saved-backtests", "/saved-backtests/1", "/research-explainer/saved-backtests/1"):
            response = client.get(route)
            assert response.status_code == 503 and "secret" not in response.text and str(path) not in response.text
        assert client.get("/health").status_code == 200


@pytest.mark.parametrize("change", ["schema", "identity", "notes", "wal", "missing_manifest"])
def test_incompatible_corrupt_or_private_material_startup_refuses(tmp_path, change):
    path, identity, config = prepared(tmp_path)
    manifest = json.loads((path / corpus.MANIFEST).read_text())
    if change == "schema": manifest["schema"] = "unsupported"
    elif change == "identity": identity = "a" * 64
    elif change == "notes":
        with closing(sqlite3.connect(path / corpus.DB_NAME)) as conn, conn:
            conn.execute("UPDATE saved_backtests SET notes=?", ("private operator path",))
    elif change == "wal": (path / (corpus.DB_NAME + "-journal")).write_bytes(b"")
    else: (path / corpus.MANIFEST).unlink()
    if change == "schema": (path / corpus.MANIFEST).write_text(validate(manifest))
    with pytest.raises(ValueError, match="refused at startup"):
        with TestClient(create_demo_app(DemoConfig(path, identity, hosts=("testserver",)))): pass


def test_pinned_expected_and_two_instances_do_not_leak_state(tmp_path):
    path, identity, config = prepared(tmp_path)
    second = tmp_path / "second"
    second_id = corpus.prepare(second)
    assert second_id != identity
    with TestClient(create_demo_app(config)) as one, TestClient(create_demo_app(DemoConfig(second, second_id, hosts=("testserver",)))) as two:
        assert one.get("/capabilities").json()["corpus_id"] == identity
        assert two.get("/capabilities").json()["corpus_id"] == second_id
        explanation = one.get("/research-explainer/saved-backtests/1").json()
        assert one.get("/research-explainer/saved-backtests/1?expected=" + explanation["fingerprint"]).status_code == 200
        assert one.get("/research-explainer/saved-backtests/1?expected=" + "a" * 64).status_code == 409
        assert db.get_db_path() != path / corpus.DB_NAME


def test_local_and_demo_instances_keep_storage_and_capabilities_separate(tmp_path):
    path, identity, config = prepared(tmp_path)
    override = db._db_path_override
    _, record, _ = corpus.verify(path, identity)
    payload = {key: record[key] for key in ("name", "notes", "ticker", "strategy", "start_date", "end_date", "initial_capital", "transaction_cost_bps", "params", "metrics", "equity_curve", "trades")}
    payload["name"] = "Owned normal-mode result"
    with TestClient(main.app) as normal, TestClient(create_demo_app(config)) as demo:
        assert normal.post("/saved-backtests", json=payload).status_code == 200
        assert normal.get("/capabilities").json()["mode"] == "local"
        assert demo.get("/capabilities").json()["mode"] == "read_only_demo"
        assert normal.get("/saved-backtests").json()[0]["name"] == payload["name"]
        assert demo.get("/saved-backtests").json()[0]["name"] == corpus.TITLE
    assert db._db_path_override == override


def test_demo_corpus_precondition_refuses_stale_or_duplicate_headers_before_dispatch(tmp_path, monkeypatch):
    _, identity, config = prepared(tmp_path)
    second = tmp_path / "replacement"
    second_id = corpus.prepare(second)
    assert second_id != identity
    app = create_demo_app(config)
    with TestClient(app) as client:
        header = {"X-QuantLab-Expected-Corpus": identity}
        for route in ("/saved-backtests", "/saved-backtests/1", "/research-explainer/saved-backtests/1"):
            assert client.get(route, headers=header).status_code == 200
        with monkeypatch.context() as patch:
            patch.setattr(corpus, "observe", forbid)
            for headers in ({"X-QuantLab-Expected-Corpus": second_id},
                            [("X-QuantLab-Expected-Corpus", identity)] * 2):
                assert client.get("/saved-backtests/1", headers=headers).status_code == 409
    with TestClient(create_demo_app(DemoConfig(second, second_id, hosts=("testserver",)))) as client:
        assert client.get("/saved-backtests/1", headers=header).status_code == 409
        assert client.get("/saved-backtests/1", headers={"X-QuantLab-Expected-Corpus": second_id}).status_code == 200


def test_stale_demo_client_cannot_read_normal_saved_data(tmp_path, monkeypatch):
    _, identity, _ = prepared(tmp_path)
    from app.research_explainer import service
    with TestClient(main.app) as client:
        for module, names in ((main, ("db_list", "db_get")),
                              (service, ("acquire",)), (db, ("get_connection",))):
            for name in names:
                monkeypatch.setattr(module, name, forbid)
        for route in ("/saved-backtests", "/saved-backtests/1", "/research-explainer/saved-backtests/1"):
            result = client.get(route, headers={"X-QuantLab-Expected-Corpus": identity})
            assert result.status_code == 409 and result.headers["cache-control"] == "no-store"
            assert "reload" in result.json()["detail"]


def test_even_rehashed_private_trade_fields_cannot_enter_public_projection(tmp_path):
    path, identity, _ = prepared(tmp_path)
    manifest, record, _ = corpus.verify(path, identity)
    record["trades"][0]["private_path"] = "private operator path"
    with closing(sqlite3.connect(path / corpus.DB_NAME)) as conn, conn:
        conn.execute("UPDATE saved_backtests SET trades_json=? WHERE id=?", (json.dumps(record["trades"]), 1))
    manifest["database_sha256"] = hashlib.sha256((path / corpus.DB_NAME).read_bytes()).hexdigest()
    manifest["material_sha256"] = digest(record)
    manifest.pop("corpus_id")
    manifest["corpus_id"] = digest(manifest)
    (path / corpus.MANIFEST).write_text(validate(manifest))
    with pytest.raises(ValueError, match="public trade projection"):
        corpus.verify(path, manifest["corpus_id"])


@pytest.mark.parametrize("table", ["saved_reports", "sqlitexprivate"])
def test_rehashed_private_rows_in_other_tables_are_refused(tmp_path, table):
    path, identity, _ = prepared(tmp_path)
    manifest, _, _ = corpus.verify(path, identity)
    with closing(sqlite3.connect(path / corpus.DB_NAME)) as conn, conn:
        if table == "saved_reports":
            conn.execute("INSERT INTO saved_reports (created_at,updated_at,title,report_type,source_type,markdown_content) VALUES (?,?,?,?,?,?)",
                         ("2026-10-18", "2026-10-18", "Private", "manual", "manual", "private report material"))
        else:
            conn.execute("CREATE TABLE sqlitexprivate (note TEXT)")
            conn.execute("INSERT INTO sqlitexprivate (note) VALUES (?)", ("private material",))
    manifest["database_sha256"] = hashlib.sha256((path / corpus.DB_NAME).read_bytes()).hexdigest()
    manifest.pop("corpus_id")
    manifest["corpus_id"] = digest(manifest)
    (path / corpus.MANIFEST).write_text(validate(manifest))
    with pytest.raises(ValueError, match="Nonpublic table material"):
        corpus.verify(path, manifest["corpus_id"])


def test_global_admission_controlled_clock_and_no_xff_identity():
    now = [1.0]
    admission = Admission(lambda: now[0], burst=2, rate=1, concurrency=1)
    assert admission.enter() and not admission.enter()
    admission.leave()
    assert admission.enter()
    admission.leave()
    assert not admission.enter()
    now[0] += 1
    assert admission.enter()
    admission.leave()
    assert not hasattr(admission, "clients")


def test_http_admission_429_and_success_release_with_controlled_clock(tmp_path):
    _, _, config = prepared(tmp_path)
    now = [1.0]
    admission = Admission(lambda: now[0], burst=1, rate=1)
    with TestClient(create_demo_app(config, admission=admission)) as client:
        assert client.get("/health").status_code == 200
        assert admission.active == 0
        refused = client.get("/health", headers={"X-Forwarded-For": "new-client"})
        assert refused.status_code == 429 and refused.headers["retry-after"] == "1"
        now[0] += 1
        assert client.get("/health").status_code == 200 and admission.active == 0


@pytest.mark.parametrize("failure", [ValueError, asyncio.CancelledError])
def test_admission_releases_on_failure_or_cancellation(tmp_path, failure):
    async def broken(scope, receive, send): raise failure()
    _, _, config = prepared(tmp_path)
    admission = Admission()
    app = DemoApplication(broken, config, admission)
    if failure is asyncio.CancelledError:
        with pytest.raises(asyncio.CancelledError): asyncio.run(asgi_call(app))
    else:
        messages, _ = asyncio.run(asgi_call(app))
        assert messages[0]["status"] == 503
    assert admission.active == 0


def test_websocket_refused_before_accept(tmp_path):
    _, _, config = prepared(tmp_path)
    with TestClient(create_demo_app(config)) as client:
        from starlette.websockets import WebSocketDisconnect
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/health"): pass
        assert exc.value.code == 1008
