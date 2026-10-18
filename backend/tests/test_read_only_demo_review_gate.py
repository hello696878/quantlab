"""Independent early-gate and lifecycle controls; no corpus or database work."""
import asyncio
import logging
import os

import pytest

from app import main
from app.read_only_demo import Admission, DemoApplication, DemoConfig, HEADERS

pytestmark = [pytest.mark.db_free, pytest.mark.usefixtures("isolated_lab_db")]


def forbidden(*args, **kwargs):
    pytest.fail("Refused request or configuration reached ordinary work")


@pytest.mark.parametrize("configuration", [
    {"QUANTLAB_SERVING_MODE": "read_only_demo"},
    {"QUANTLAB_SERVING_MODE": "unknown"},
    {"QUANTLAB_DEMO_CORPUS": "private-never-opened"},
])
def test_cached_local_app_revalidates_before_writable_startup(monkeypatch, configuration):
    for key in list(os.environ):
        if key == "QUANTLAB_SERVING_MODE" or key.startswith("QUANTLAB_DEMO_"):
            monkeypatch.delenv(key)
    for key, value in configuration.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(main, "init_db", forbidden)

    async def start():
        async with main.lifespan(main.app):
            forbidden()

    with pytest.raises(ValueError):
        asyncio.run(start())


@pytest.mark.parametrize("mode", [None, "local"])
def test_ordinary_lifespan_still_initializes_once(monkeypatch, mode):
    for key in list(os.environ):
        if key == "QUANTLAB_SERVING_MODE" or key.startswith("QUANTLAB_DEMO_"):
            monkeypatch.delenv(key)
    if mode is not None:
        monkeypatch.setenv("QUANTLAB_SERVING_MODE", mode)
    calls = []
    monkeypatch.setattr(main, "init_db", lambda: calls.append("init"))

    async def start():
        async with main.lifespan(main.app):
            assert calls == ["init"]

    asyncio.run(start())
    assert calls == ["init"]


def config(tmp_path):
    return DemoConfig(tmp_path / "absent-corpus", "a" * 64, hosts=("testserver",))


def request_scope(*, path="/health", method="GET", headers=None, query=b""):
    return {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "scheme": "http", "path": path, "raw_path": path.encode("ascii"),
            "root_path": "", "query_string": query, "method": method,
            "headers": [(b"host", b"testserver")] if headers is None else headers}


async def invoke(app, scope=None, *, frame=None, receive_error=None):
    messages, reads = [], []

    async def receive():
        reads.append(1)
        if receive_error is not None:
            raise receive_error("controlled secret")
        return {"type": "http.request", "body": b"", "more_body": False} if frame is None else frame

    async def send(message):
        messages.append(message)

    await app(request_scope() if scope is None else scope, receive, send)
    return messages, reads


@pytest.mark.parametrize("headers,status", [
    ([(b"host", b"testserver"), (b"content-length", b"0"), (b"content-length", b"0")], 400),
    ([(b"host", b"testserver"), (b"content-length", b"-1")], 400),
    ([(b"host", b"testserver"), (b"content-length", b"not-a-number")], 400),
    ([(b"host", b"testserver"), (b"content-length", b"99999999999999999999999")], 400),
    ([(b"host", b"testserver"), (b"transfer-encoding", b"chunked")], 400),
    ([(b"host", b"testserver"), (b"host", b"testserver")], 400),
    ([(b"host", b"testserver"), (b"origin", b"https://secret.invalid")], 403),
    ([(b"host", b"testserver")] + [(b"x", b"y")] * 100, 431),
    ([(b"host", b"testserver"), (b"x-secret", b"s" * 8192)], 431),
])
def test_header_rejections_do_not_receive_or_dispatch(tmp_path, headers, status):
    admission = Admission()
    app = DemoApplication(forbidden, config(tmp_path), admission)
    messages, reads = asyncio.run(invoke(app, request_scope(headers=headers)))
    assert messages[0]["status"] == status and reads == []
    assert admission.active == 0 and admission.tokens == admission.burst
    assert b"secret.invalid" not in messages[1]["body"]


@pytest.mark.parametrize("path,method,query", [
    ("/health", "POST", b""),
    ("/capabilities", "OPTIONS", b""),
    ("/saved-backtests/1", "HEAD", b""),
    ("/saved-backtests/new", "GET", b""),
    ("/saved-backtests/1/import", "GET", b""),
    ("/globe/markets", "GET", b""),
    ("/new-unclassified", "GET", b""),
    ("/health", "GET", b"QUANTLAB_SERVING_MODE=local"),
])
def test_route_or_http_mode_inputs_never_authorize_work(tmp_path, path, method, query):
    scope = request_scope(path=path, method=method, query=query)
    scope["headers"] += [(b"cookie", b"QUANTLAB_SERVING_MODE=local"),
                         (b"x-quantlab-serving-mode", b"local")]
    messages, reads = asyncio.run(invoke(DemoApplication(forbidden, config(tmp_path), Admission()), scope))
    assert messages[0]["status"] == (422 if query else 403) and reads == []


@pytest.mark.parametrize("frame", [
    {"type": "http.request", "body": b"", "more_body": True},
    {"type": "http.request", "body": b"secret", "more_body": False},
    {"type": "http.disconnect"},
])
def test_undeclared_stream_or_disconnect_releases_without_dispatch(tmp_path, frame):
    admission = Admission()
    messages, reads = asyncio.run(invoke(DemoApplication(forbidden, config(tmp_path), admission), frame=frame))
    assert messages[0]["status"] == 400 and reads == [1]
    assert admission.active == 0
    assert b"secret" not in messages[1]["body"]


def test_initial_frame_timeout_releases_without_dispatch(tmp_path):
    admission = Admission()
    messages, reads = asyncio.run(invoke(DemoApplication(forbidden, config(tmp_path), admission),
                                       receive_error=asyncio.TimeoutError))
    assert messages[0]["status"] == 408 and reads == [1] and admission.active == 0
    assert b"controlled secret" not in messages[1]["body"]


def test_dispatched_timeout_is_unavailable_not_an_initial_frame_timeout(tmp_path):
    calls = []

    async def broken(scope, receive, send):
        calls.append(scope["path"])
        raise asyncio.TimeoutError("private handler timeout")

    admission = Admission()
    messages, reads = asyncio.run(invoke(DemoApplication(broken, config(tmp_path), admission)))
    assert calls == ["/health"] and reads == [1] and admission.active == 0
    assert messages[0]["status"] == 503
    assert b"before dispatch" not in messages[1]["body"]
    assert b"private handler" not in messages[1]["body"]


def test_cancellation_while_waiting_for_initial_frame_releases_slot(tmp_path):
    async def scenario():
        admission = Admission()
        entered = asyncio.Event()

        async def receive():
            entered.set()
            await asyncio.Future()

        async def send(message):
            forbidden()

        task = asyncio.create_task(DemoApplication(forbidden, config(tmp_path), admission)(request_scope(), receive, send))
        await entered.wait()
        assert admission.active == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert admission.active == 0

    asyncio.run(scenario())


def test_concurrent_rejection_preserves_active_permits_and_never_receives(tmp_path):
    async def scenario():
        entered = asyncio.Queue()
        release = asyncio.Event()
        admission = Admission(concurrency=2)

        async def waiting(scope, receive, send):
            entered.put_nowait(scope["path"])
            await release.wait()
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"{}"})

        app = DemoApplication(waiting, config(tmp_path), admission)
        first = asyncio.create_task(invoke(app))
        second = asyncio.create_task(invoke(app))
        await entered.get()
        await entered.get()
        assert admission.active == 2
        messages, reads = await invoke(app)
        assert messages[0]["status"] == 429 and reads == [] and admission.active == 2
        release.set()
        await asyncio.gather(first, second)
        assert admission.active == 0

    asyncio.run(scenario())


def test_backwards_clock_does_not_refill_until_prior_high_water_mark():
    now = [10.0]
    admission = Admission(lambda: now[0], burst=1, rate=1)
    assert admission.enter()
    admission.leave()
    now[0] = 9.0
    assert not admission.enter()
    now[0] = 10.0
    assert not admission.enter()
    now[0] = 10.5
    assert not admission.enter()
    now[0] = 11.0
    assert admission.enter()
    admission.leave()


def test_safe_response_headers_and_logging_do_not_echo_inner_exception(tmp_path, caplog):
    async def broken(scope, receive, send):
        raise ValueError("private-path credential never-log")

    caplog.set_level(logging.INFO, logger="quantlab.demo")
    app = DemoApplication(broken, config(tmp_path), Admission())
    messages, _ = asyncio.run(invoke(app))
    assert messages[0]["status"] == 503
    actual = dict(messages[0]["headers"])
    assert all(actual[key.lower().encode()] == value.encode() for key, value in HEADERS.items())
    assert b"private-path" not in messages[1]["body"]
    records = [record for record in caplog.records if record.name == "quantlab.demo"]
    assert len(records) == 1 and records[0].getMessage() == "demo_request"
    assert records[0].route_pattern == "/health" and records[0].status_code == 503
    assert "never-log" not in caplog.text
