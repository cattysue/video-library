import http.client
import json
import threading

import pytest

from conftest import VIDEO_ID
from test_library import make_doc
from test_server import make_web
from video_library import auth, jobs
from video_library.server import LibraryServer
from video_library.store_hosted import HostedStore

TOKEN = "test-upload-token"
PASSWORD = "test-admin-password"
WRITE = {"X-Requested-With": "video-library"}
BEARER = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def hosted(home):
    a = auth.Auth(auth.hash_password(PASSWORD, iterations=1000), auth.hash_token(TOKEN))
    server = LibraryServer(("127.0.0.1", 0), HostedStore(home), make_web(home), auth=a)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def call(server, method, path, body=None, headers=None, raw=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
    data = raw if raw is not None else (json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None)
    conn.request(method, path, body=data, headers=dict(headers or {}))
    resp = conn.getresponse()
    payload = resp.read()
    conn.close()
    return resp, (json.loads(payload.decode("utf-8")) if payload else None)


def login(server):
    resp, _ = call(server, "POST", "/api/login", {"password": PASSWORD}, WRITE)
    assert resp.status == 200
    return {"Cookie": resp.getheader("Set-Cookie").split(";")[0]}


def upload(server, doc=None):
    return call(server, "PUT", f"/api/lectures/{VIDEO_ID}", doc or make_doc(), BEARER)


def test_health_hides_home_and_reports_admin(hosted):
    _, body = call(hosted, "GET", "/api/health")
    assert body == {"app": "video-library", "mode": "hosted", "admin": False}
    _, body = call(hosted, "GET", "/api/health", headers=login(hosted))
    assert body["admin"] is True


def test_public_host_name_is_allowed(hosted):
    resp, _ = call(hosted, "GET", "/api/health", headers={"Host": "video-library.up.railway.app"})
    assert resp.status == 200


def test_upload_needs_right_token(hosted):
    for headers in ({}, {"Authorization": "Bearer wrong"}, {"Authorization": TOKEN}):
        resp, body = call(hosted, "PUT", f"/api/lectures/{VIDEO_ID}", make_doc(), headers)
        assert resp.status == 401 and "토큰" in body["error"]
    resp, body = upload(hosted)
    assert resp.status == 200 and body == {"id": VIDEO_ID, "public": False}


def test_private_lecture_hidden_from_visitors(hosted):
    upload(hosted)
    assert call(hosted, "GET", "/api/lectures")[1] == []
    assert call(hosted, "GET", f"/api/lectures/{VIDEO_ID}")[0].status == 404
    assert call(hosted, "GET", "/api/search?q=%EA%B8%B0%EC%B4%88")[1]["results"] == []
    resp, _ = call(hosted, "GET", "/api/jobs")
    assert resp.status == 401


def test_admin_sees_all_and_publishes(hosted):
    upload(hosted)
    admin = login(hosted)
    items = call(hosted, "GET", "/api/lectures", headers=admin)[1]
    assert [(e["id"], e["public"]) for e in items] == [(VIDEO_ID, False)]
    assert call(hosted, "GET", "/api/search?q=%EA%B8%B0%EC%B4%88", headers=admin)[1]["results"]
    resp, _ = call(hosted, "PATCH", f"/api/lectures/{VIDEO_ID}", {"public": True}, admin)  # 요청 헤더 빠짐
    assert resp.status == 403
    resp, body = call(hosted, "PATCH", f"/api/lectures/{VIDEO_ID}", {"public": True}, {**admin, **WRITE})
    assert resp.status == 200 and body == {"id": VIDEO_ID, "public": True}
    items = call(hosted, "GET", "/api/lectures")[1]
    assert [(e["id"], e["public"]) for e in items] == [(VIDEO_ID, True)]
    assert call(hosted, "GET", f"/api/lectures/{VIDEO_ID}")[0].status == 200
    assert call(hosted, "GET", "/api/search?q=%EA%B8%B0%EC%B4%88")[1]["results"]
    assert upload(hosted)[1]["public"] is True  # 재업로드해도 공개 유지


def test_admin_writes_need_login(hosted):
    upload(hosted)
    for method, body in (("PATCH", {"public": True}), ("DELETE", None)):
        resp, _ = call(hosted, method, f"/api/lectures/{VIDEO_ID}", body, WRITE)
        assert resp.status == 401
    resp, _ = call(hosted, "PATCH", f"/api/lectures/{VIDEO_ID}", {"public": "yes"}, {**login(hosted), **WRITE})
    assert resp.status == 400


def test_delete(hosted):
    upload(hosted)
    admin = {**login(hosted), **WRITE}
    assert call(hosted, "DELETE", f"/api/lectures/{VIDEO_ID}", headers=admin)[0].status == 200
    assert call(hosted, "GET", f"/api/lectures/{VIDEO_ID}", headers=admin)[0].status == 404
    assert call(hosted, "DELETE", f"/api/lectures/{VIDEO_ID}", headers=admin)[0].status == 404


def test_bad_uploads_rejected(hosted):
    broken = make_doc()
    del broken["segments"]
    assert upload(hosted, broken)[0].status == 400
    resp, _ = call(hosted, "PUT", "/api/lectures/ZZZZZZZZZZZ", make_doc(), BEARER)
    assert resp.status == 400
    resp, _ = call(hosted, "PUT", f"/api/lectures/{VIDEO_ID}", headers=BEARER, raw=b"{not json")
    assert resp.status == 400
    assert call(hosted, "GET", "/api/lectures", headers=login(hosted))[1] == []


def test_too_large_upload_rejected_without_reading(hosted):
    conn = http.client.HTTPConnection("127.0.0.1", hosted.port, timeout=10)
    conn.putrequest("PUT", f"/api/lectures/{VIDEO_ID}")
    conn.putheader("Authorization", f"Bearer {TOKEN}")
    conn.putheader("Content-Length", str(21 * 1024 * 1024))
    conn.endheaders()
    resp = conn.getresponse()
    assert resp.status == 413
    conn.close()


def test_login_errors_and_lock(hosted):
    resp, _ = call(hosted, "POST", "/api/login", {"password": PASSWORD})  # 요청 헤더 빠짐
    assert resp.status == 403
    for _ in range(auth.LOGIN_MAX_FAILURES):
        resp, body = call(hosted, "POST", "/api/login", {"password": "틀림"}, WRITE)
        assert resp.status == 401
    resp, body = call(hosted, "POST", "/api/login", {"password": PASSWORD}, WRITE)
    assert resp.status == 429 and "15분" in body["error"]


def test_login_cookie_and_logout(hosted):
    resp, _ = call(hosted, "POST", "/api/login", {"password": PASSWORD}, WRITE)
    cookie = resp.getheader("Set-Cookie")
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=Strict" in cookie
    admin = {"Cookie": cookie.split(";")[0]}
    resp, _ = call(hosted, "POST", "/api/logout", headers={**admin, **WRITE})
    assert resp.status == 200 and "Max-Age=0" in resp.getheader("Set-Cookie")
    assert call(hosted, "GET", "/api/health", headers=admin)[1]["admin"] is False


def test_job_reports(hosted, tmp_path):
    job = jobs.start_job(tmp_path / "pc", VIDEO_ID, "깃 기초", jobs.initial_steps(False, True))  # PC 쪽 기록
    path = f"/api/jobs/{job['job_id']}"
    assert call(hosted, "POST", path, job)[0].status == 401
    resp, body = call(hosted, "POST", path, job, BEARER)
    assert resp.status == 200 and body == {"job_id": job["job_id"]}
    assert call(hosted, "POST", path, {**job, "status": "paused"}, BEARER)[0].status == 400
    listed = call(hosted, "GET", "/api/jobs", headers=login(hosted))[1]
    assert [j["job_id"] for j in listed] == [job["job_id"]]


def test_unknown_write_paths(hosted):
    assert call(hosted, "POST", "/api/nothing", {}, BEARER)[0].status == 404
    assert call(hosted, "PUT", "/api/jobs/x", {}, BEARER)[0].status == 404


from video_library.config import StepError
from video_library.server import BUNDLED_WEB, hosted_server


def good_env(tmp_path):
    return {"VL_ADMIN_PASSWORD_HASH": auth.hash_password(PASSWORD, iterations=1000),
            "VL_UPLOAD_TOKEN_HASH": auth.hash_token(TOKEN), "PORT": "0", "VL_HOME": str(tmp_path / "data")}


def test_hosted_server_from_env(tmp_path):
    server = hosted_server(good_env(tmp_path), host="127.0.0.1")
    try:
        assert server.hosted and isinstance(server.store, HostedStore)
        assert server.web_dir == BUNDLED_WEB and (BUNDLED_WEB / "library.html").is_file()
        assert (tmp_path / "data").is_dir()
    finally:
        server.server_close()


@pytest.mark.parametrize("missing", ["VL_ADMIN_PASSWORD_HASH", "VL_UPLOAD_TOKEN_HASH"])
def test_hosted_server_refuses_without_secrets(tmp_path, missing):
    env = good_env(tmp_path)
    del env[missing]
    with pytest.raises(StepError, match=missing):
        hosted_server(env, host="127.0.0.1")


def test_hosted_server_refuses_plain_password(tmp_path):
    env = good_env(tmp_path) | {"VL_ADMIN_PASSWORD_HASH": "my-password"}
    with pytest.raises(StepError, match="형식"):
        hosted_server(env, host="127.0.0.1")


def test_rejected_upload_still_gets_clear_answer(hosted):
    # 토큰이 틀려도 보내던 본문을 끝까지 받은 뒤 401 로 답해야, 보내는 쪽이 '연결 끊김' 대신 이유를 본다
    big = b'{"pad": "' + b"a" * 3_000_000 + b'"}'
    for _ in range(3):
        resp, body = call(hosted, "PUT", f"/api/lectures/{VIDEO_ID}", headers={"Authorization": "Bearer wrong"}, raw=big)
        assert resp.status == 401 and "토큰" in body["error"]


def test_stalled_upload_is_dropped(hosted, monkeypatch):
    # 본문을 보내다 멈춘 연결이 서버 스레드를 영원히 붙잡지 않는다(검토 I1)
    import socket
    from video_library import server as server_mod
    assert server_mod._Handler.timeout and 0 < server_mod._Handler.timeout <= 60  # 서버 기본값으로 시간 제한이 있다
    monkeypatch.setattr(server_mod._Handler, "timeout", 0.5)  # 테스트에서는 짧게
    sock = socket.create_connection(("127.0.0.1", hosted.port), timeout=5)
    sock.sendall(b"PUT /api/lectures/AbCdEfGhIjK HTTP/1.0\r\nContent-Length: 1000\r\n\r\n{")
    sock.settimeout(5)
    data = sock.recv(4096)  # 서버가 시간 초과로 닫거나 답하면 곧 돌아온다
    sock.close()
    assert data == b"" or data.startswith(b"HTTP/")
