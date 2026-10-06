import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from conftest import VIDEO_ID
from video_library import jobs, remote
from video_library.config import StepError


class FakeRailway:
    """받은 요청을 기록하고 정해 둔 응답을 돌려주는 시험용 서버(127.0.0.1)."""

    def __init__(self, status=200, reply=None, delay=0.0):
        fake = self
        self.calls = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _any(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"null")
                fake.calls.append((self.command, self.path, self.headers.get("Authorization"), body))
                time.sleep(delay)
                data = json.dumps(reply if reply is not None else {"ok": True}).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = do_PUT = _any

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def fake():
    server = FakeRailway()
    yield server
    server.close()


def test_guard_blocks_internet():
    with pytest.raises(OSError, match="인터넷"):
        socket.create_connection(("example.com", 443), timeout=1)


@pytest.mark.parametrize("url, expected", [
    ("https://video-library.up.railway.app/", "https://video-library.up.railway.app"),
    ("https://example.com", "https://example.com"),
    ("http://127.0.0.1:8790", "http://127.0.0.1:8790"),
])
def test_normalize_server(url, expected):
    assert remote.normalize_server(url) == expected


@pytest.mark.parametrize("url", ["http://example.com", "ftp://x", "example.com", "", "https://", "https://a b"])
def test_normalize_server_rejects(url):
    with pytest.raises(StepError):
        remote.normalize_server(url)


def test_config_roundtrip_and_broken(home):
    assert remote.load_config(home) == {}
    remote.save_config(home, "https://x.up.railway.app", "tok")
    assert remote.load_config(home) == {"server": "https://x.up.railway.app", "token": "tok"}
    (home / "config.json").write_text("{망가짐", encoding="utf-8")
    assert remote.load_config(home) == {}
    (home / "config.json").write_text('{"server": "http://evil.com", "token": "t"}', encoding="utf-8")
    assert remote.load_config(home) == {}


def test_request_sends_token_and_json(fake):
    status, body = remote.request("PUT", f"{fake.url}/api/lectures/{VIDEO_ID}", "tok", {"a": 1})
    assert status == 200 and body == {"ok": True}
    assert fake.calls == [("PUT", f"/api/lectures/{VIDEO_ID}", "Bearer tok", {"a": 1})]


def test_request_error_status_is_returned():
    server = FakeRailway(status=401, reply={"error": "업로드 토큰이 맞지 않습니다"})
    try:
        assert remote.request("PUT", f"{server.url}/x", "t", {}) == (401, {"error": "업로드 토큰이 맞지 않습니다"})
    finally:
        server.close()


def test_request_connection_refused():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()  # 아무도 듣지 않는 포트
    with pytest.raises(remote.RemoteError):
        remote.request("GET", f"http://127.0.0.1:{port}/", "t", timeout=1)


def test_report_job_without_config_does_nothing(home, fake):
    job = jobs.start_job(home, VIDEO_ID, "깃 기초", jobs.initial_steps(False, False))
    assert remote.report_job(home, job) is False
    assert fake.calls == []


def test_jobs_report_every_write(home, fake):
    remote.save_config(home, fake.url, "tok")
    job = jobs.start_job(home, VIDEO_ID, "깃 기초", jobs.initial_steps(False, True))
    jobs.set_step(home, job["job_id"], "preprocess", "done")
    paths = [(m, p, a) for m, p, a, _ in fake.calls]
    assert paths == [("POST", f"/api/jobs/{job['job_id']}", "Bearer tok")] * 2
    assert fake.calls[-1][3]["steps"]["preprocess"] == "done"


def test_slow_railway_does_not_block(home):
    slow = FakeRailway(delay=2.0)
    try:
        remote.save_config(home, slow.url, "tok")
        job = jobs.start_job(home, VIDEO_ID, "깃 기초", jobs.initial_steps(False, True))
        began = time.monotonic()
        assert remote.report_job(home, job, timeout=0.3) is False
        assert time.monotonic() - began < 1.5
    finally:
        slow.close()


def test_broken_reply_does_not_stop_processing(home):
    # Railway 가 응답을 중간에 끊어도 진행 보고는 조용히 넘어가고, 요청은 RemoteError 로 바뀐다(검토 I2)
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Truncated(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            self.send_response(200)
            self.send_header("Content-Length", "100")
            self.end_headers()
            self.wfile.write(b'{"ok"')  # 100바이트라고 해 놓고 일부만 보낸다

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Truncated)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}"
        remote.save_config(home, url, "tok")
        job = jobs.start_job(home, VIDEO_ID, "깃 기초", jobs.initial_steps(False, True))  # 예외 없이 끝나야 한다
        assert remote.report_job(home, job) is False
        with pytest.raises(remote.RemoteError):
            remote.request("POST", f"{url}/x", "tok", {})
    finally:
        srv.shutdown()
        srv.server_close()
