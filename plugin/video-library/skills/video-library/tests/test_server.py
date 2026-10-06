import http.client
import json
import socket
import threading
import time

import pytest

from conftest import VIDEO_ID
from test_library import make_doc, stage
from video_library import library
from video_library.config import read_json
from video_library.server import CSP, LibraryServer, bind, run
from video_library.store_file import FileStore

PAGES = {"library.html": "<!doctype html><title>목록</title>", "lecture.html": "<!doctype html><title>강의</title>",
         "app.css": "body{}", "common.js": "var VL={};", "secret.txt": "비밀"}


def make_web(home):
    web = home / "app"
    (web / "runtime").mkdir(parents=True, exist_ok=True)
    for name, body in PAGES.items():
        (web / name).write_text(body, encoding="utf-8")
    (web / "runtime" / "vl.py").write_text("print('runtime')", encoding="utf-8")
    return web


@pytest.fixture
def live(home):
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)
    server = LibraryServer(("127.0.0.1", 0), FileStore(home), make_web(home))
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def get(server, path, method="GET", host=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    headers = {"Host": host} if host else {}
    conn.request(method, path, headers=headers)
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    return resp, body


def get_json(server, path):
    resp, body = get(server, path)
    return resp.status, json.loads(body.decode("utf-8"))


def test_pages_and_security_headers(live):
    resp, body = get(live, "/")
    assert resp.status == 200 and "목록" in body.decode("utf-8")
    assert resp.getheader("Content-Security-Policy") == CSP
    assert resp.getheader("Cache-Control") == "no-store"
    assert resp.getheader("X-Content-Type-Options") == "nosniff"
    resp, body = get(live, f"/lecture?id={VIDEO_ID}&t=10")
    assert resp.status == 200 and "강의" in body.decode("utf-8")
    resp, _ = get(live, "/app/app.css")
    assert resp.status == 200 and resp.getheader("Content-Type").startswith("text/css")


@pytest.mark.parametrize("path", ["/app/..%2Findex.json", "/app/runtime/vl.py", "/app/runtime%2Fvl.py",
                                  "/app/.server.json", "/app/secret.txt", "/app/", "/index.json",
                                  f"/lectures/{VIDEO_ID}/lecture.json"])
def test_files_outside_app_are_not_served(live, path):
    resp, _ = get(live, path)
    assert resp.status == 404


def test_api_lectures(live):
    status, data = get_json(live, "/api/lectures")
    assert status == 200 and [e["id"] for e in data] == [VIDEO_ID]
    status, doc = get_json(live, f"/api/lectures/{VIDEO_ID}")
    assert status == 200 and doc["lecture"]["id"] == VIDEO_ID
    status, err = get_json(live, "/api/lectures/..%2F..%2Fx")
    assert status == 404 and "error" in err
    status, err = get_json(live, "/api/lectures/NoSuchVideo")
    assert status == 404


def test_api_search_and_refresh(live, home):
    status, data = get_json(live, "/api/search?q=%EB%B8%8C%EB%9E%9C%EC%B9%98")  # 브랜치
    assert status == 200 and data["results"][0]["id"] == VIDEO_ID
    stage(home, make_doc("ZzZzZzZzZzZ", "2026-10-06T09:00:00+09:00", title="새 강의 브랜치"))
    library.commit_lecture(home, "ZzZzZzZzZzZ")
    status, data = get_json(live, "/api/search?q=%EB%B8%8C%EB%9E%9C%EC%B9%98")
    assert [r["id"] for r in data["results"]] == ["ZzZzZzZzZzZ", VIDEO_ID]
    status, data = get_json(live, f"/api/search?q=%EB%B8%8C%EB%9E%9C%EC%B9%98&video={VIDEO_ID}")
    assert [r["id"] for r in data["results"]] == [VIDEO_ID]


def test_api_jobs_and_health(live, home):
    status, data = get_json(live, "/api/jobs")
    assert status == 200 and data == []
    status, data = get_json(live, "/api/health")
    assert data == {"app": "video-library", "mode": "pc", "home": str(home)}


def test_write_methods_rejected(live):
    for method in ("POST", "PUT", "DELETE", "PATCH"):
        resp, _ = get(live, "/api/lectures", method=method)
        assert resp.status == 405


def test_foreign_host_rejected(live):
    resp, _ = get(live, "/api/lectures", host="evil.example:80")
    assert resp.status == 403
    resp, _ = get(live, "/api/lectures", host=f"localhost:{live.port}")
    assert resp.status == 200


def test_store_errors_become_500(live, monkeypatch):
    def boom():
        raise RuntimeError("디스크 오류")
    monkeypatch.setattr(live.store, "list_lectures", boom)
    resp, _ = get(live, "/api/lectures")
    assert resp.status == 500
    assert get(live, "/api/jobs")[0].status == 200  # 서버는 계속 동작


def test_bind_skips_busy_port(home):
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", 0))
    busy = blocker.getsockname()[1]
    blocker.listen()
    try:
        server = bind(FileStore(home), make_web(home), port=busy)
        assert server.port != busy and busy < server.port < busy + 20
        server.server_close()
    finally:
        blocker.close()



def test_bind_skips_port_held_on_all_interfaces(home):
    # 다른 프로그램이 0.0.0.0(모든 주소)에서 같은 포트를 쓰면 그 포트를 피한다(Windows는 127.0.0.1 bind가 성공해 버림)
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("0.0.0.0", 0))
    busy = blocker.getsockname()[1]
    blocker.listen()
    try:
        server = bind(FileStore(home), make_web(home), port=busy)
        assert server.port != busy
        server.server_close()
    finally:
        blocker.close()

def test_run_writes_state_and_stops_when_idle(home):
    server = LibraryServer(("127.0.0.1", 0), FileStore(home), make_web(home), idle_timeout=0.3)
    state = home / ".server.json"
    thread = threading.Thread(target=run, args=(server, state), kwargs={"check_every": 0.1}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 3
    while not state.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert read_json(state)["port"] == server.port
    thread.join(timeout=5)
    assert not thread.is_alive() and not state.exists()
