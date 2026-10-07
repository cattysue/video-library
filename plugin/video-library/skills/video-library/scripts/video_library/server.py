"""영상자료실 서버. PC 전용 미니 서버(127.0.0.1, 읽기 전용) 또는 --hosted 로 Railway 서버(로그인·업로드·공개 범위). 표준 라이브러리만."""
from __future__ import annotations

import argparse
import json
import os
import socket
import threading
import time
from collections.abc import Mapping
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .auth import COOKIE, Auth, LoginLocked, session_cookie
from .config import DEFAULT_PORT, SERVER_STATE, StepError, ensure_home, library_home, read_json, write_json
from .search import SearchIndex
from .store_file import FileStore
from .store_hosted import HostedStore, UploadError

IDLE_TIMEOUT_SEC = 3600
PORT_RANGE = 20
PAGES = {"/": "library.html", "/lecture": "lecture.html"}
STATIC_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml",
                ".png": "image/png", ".ico": "image/x-icon"}
CSP = ("default-src 'self'; script-src 'self' https://www.youtube.com https://s.ytimg.com; "
       "frame-src https://www.youtube.com https://www.youtube-nocookie.com; "
       "img-src 'self' https://i.ytimg.com data:; style-src 'self' 'unsafe-inline'; "
       "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
LECTURE_MAX_BYTES = 20 * 1024 * 1024
SMALL_MAX_BYTES = 64 * 1024
WRITE_HEADER = ("X-Requested-With", "video-library")
LECTURES = "/api/lectures/"
JOBS = "/api/jobs/"
BUNDLED_WEB = Path(__file__).resolve().parent.parent.parent / "web"  # 스킬의 web/ (Docker: /srv/web)
SECRET_VARS = ("VL_ADMIN_PASSWORD_HASH", "VL_UPLOAD_TOKEN_HASH")


class LibraryServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False  # Windows 에서 같은 포트를 두 서버가 나눠 쓰지 않게

    def __init__(self, addr, store: FileStore, web_dir: Path, idle_timeout: float = IDLE_TIMEOUT_SEC,
                 auth: Auth | None = None):
        super().__init__(addr, _Handler)
        self.store = store
        self.auth = auth
        self.hosted = auth is not None  # Railway: 로그인·업로드·공개 범위. PC: 읽기 전용
        self.web_dir = Path(web_dir)
        self.idle_timeout = idle_timeout
        self.port = self.server_address[1]
        self._last_seen = time.monotonic()
        self._lock = threading.Lock()
        self._index = None
        self._index_version = None

    def touch(self) -> None:
        self._last_seen = time.monotonic()

    def idle(self) -> bool:
        return time.monotonic() - self._last_seen > self.idle_timeout

    def search_index(self) -> SearchIndex:
        with self._lock:
            version = self.store.version()
            if self._index is None or version != self._index_version:
                self._index = SearchIndex(self.store.all_lectures())
                self._index_version = version
            return self._index


class _HttpError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class _Handler(BaseHTTPRequestHandler):
    server_version = "video-library"
    timeout = 30  # 초. 보내다 멈춘 연결이 스레드를 붙잡지 않게

    def log_message(self, fmt, *args):  # 콘솔을 조용히 둔다
        pass

    def do_GET(self):
        self._dispatch(self._get)

    def do_POST(self):
        self._dispatch(self._post)

    def do_PUT(self):
        self._dispatch(self._put)

    def do_PATCH(self):
        self._dispatch(self._patch)

    def do_DELETE(self):
        self._dispatch(self._delete)

    def _dispatch(self, route):
        self.server.touch()
        if not self.server.hosted:
            if not self._host_ok():
                return self._error(403, "허용되지 않은 접근입니다")
            if route != self._get:
                return self._error(405, "읽기 전용 서버입니다")
        parts = urlsplit(self.path)
        self._body_read = False
        try:
            route(parts.path, parse_qs(parts.query))
        except _HttpError as exc:
            self._drain()
            self._error(exc.status, exc.message)
        except Exception as exc:  # 한 요청의 오류로 서버가 멈추지 않게
            self._error(500, f"서버 오류: {type(exc).__name__}")

    # ---- 읽기 ----
    def _get(self, path, query):
        store = self.server.store
        if path in PAGES:
            return self._static(PAGES[path])
        if path.startswith("/app/"):
            return self._static(path[len("/app/"):])
        if path == "/api/health":
            if self.server.hosted:
                return self._json(200, {"app": "video-library", "mode": "hosted", "admin": self._is_admin()})
            return self._json(200, {"app": "video-library", "mode": "pc", "home": str(store.home)})
        if path == "/api/lectures":
            return self._json(200, self._visible_list())
        if path.startswith(LECTURES):
            lecture_id = unquote(path[len(LECTURES):])
            doc = store.get_lecture(lecture_id) if self._can_see(lecture_id) else None
            return self._json(200, doc) if doc else self._error(404, "강의를 찾을 수 없습니다")
        if path == "/api/search":
            first = lambda key: (query.get(key) or [None])[0] or None
            allowed = None if self._sees_all() else store.public_ids()
            return self._json(200, self.server.search_index().search(
                first("q") or "", first("field"), first("video"), allowed=allowed))
        if path == "/api/jobs":
            if not self._sees_all():
                raise _HttpError(401, "관리자 로그인이 필요합니다")
            return self._json(200, store.list_jobs())
        raise _HttpError(404, "없는 주소입니다")

    def _visible_list(self) -> list:
        items = self.server.store.list_lectures()
        if not self.server.hosted:
            return items
        public = self.server.store.public_ids()
        if not self._is_admin():
            items = [e for e in items if isinstance(e, dict) and e.get("id") in public]
        return [dict(e, public=e.get("id") in public) for e in items if isinstance(e, dict)]

    # ---- 쓰기(호스팅 모드만) ----
    def _post(self, path, query):
        auth = self.server.auth
        if path == "/api/login":
            self._require_write_header()
            body = self._read_json(SMALL_MAX_BYTES)
            password = body.get("password") if isinstance(body, dict) else None
            if not isinstance(password, str):
                raise _HttpError(400, "비밀번호가 필요합니다")
            try:
                sid = auth.login(password)
            except LoginLocked:
                raise _HttpError(429, "로그인 시도가 너무 많습니다. 15분 뒤 다시 시도하세요")
            if not sid:
                raise _HttpError(401, "비밀번호가 맞지 않습니다")
            return self._json(200, {"admin": True}, {"Set-Cookie": session_cookie(sid)})
        if path == "/api/logout":
            self._require_write_header()
            auth.logout(self._session_id())
            return self._json(200, {"admin": False}, {"Set-Cookie": session_cookie("", expire=True)})
        if path.startswith(JOBS):
            self._require_token()
            job_id = unquote(path[len(JOBS):])
            body = self._read_json(SMALL_MAX_BYTES)
            try:
                self.server.store.put_job(job_id, body)
            except UploadError as exc:
                raise _HttpError(400, str(exc))
            return self._json(200, {"job_id": job_id})
        raise _HttpError(404, "없는 주소입니다")

    def _put(self, path, query):
        lecture_id = self._lecture_id(path)
        self._require_token()
        doc = self._read_json(LECTURE_MAX_BYTES)
        try:
            public = self.server.store.put_lecture(lecture_id, doc)
        except UploadError as exc:
            raise _HttpError(400, str(exc))
        return self._json(200, {"id": lecture_id, "public": public})

    def _patch(self, path, query):
        lecture_id = self._lecture_id(path)
        self._require_admin()
        body = self._read_json(SMALL_MAX_BYTES)
        if not isinstance(body, dict) or not isinstance(body.get("public"), bool):
            raise _HttpError(400, '{"public": true 또는 false} 형식이어야 합니다')
        if not self.server.store.set_public(lecture_id, body["public"]):
            raise _HttpError(404, "강의를 찾을 수 없습니다")
        return self._json(200, {"id": lecture_id, "public": body["public"]})

    def _delete(self, path, query):
        lecture_id = self._lecture_id(path)
        self._require_admin()
        if not self.server.store.delete_lecture(lecture_id):
            raise _HttpError(404, "강의를 찾을 수 없습니다")
        return self._json(200, {"id": lecture_id, "deleted": True})

    # ---- 권한·본문 ----
    def _lecture_id(self, path) -> str:
        if not path.startswith(LECTURES):
            raise _HttpError(404, "없는 주소입니다")
        return unquote(path[len(LECTURES):])

    def _session_id(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except CookieError:
            return None
        morsel = cookie.get(COOKIE)
        return morsel.value if morsel else None

    def _is_admin(self) -> bool:
        return self.server.hosted and self.server.auth.session_ok(self._session_id())

    def _sees_all(self) -> bool:
        return not self.server.hosted or self._is_admin()

    def _can_see(self, lecture_id) -> bool:
        return self._sees_all() or lecture_id in self.server.store.public_ids()

    def _require_write_header(self):
        name, value = WRITE_HEADER
        if self.headers.get(name) != value:
            raise _HttpError(403, "요청 형식이 올바르지 않습니다")

    def _require_admin(self):
        self._require_write_header()
        if not self._is_admin():
            raise _HttpError(401, "관리자 로그인이 필요합니다")

    def _require_token(self):
        if not self.server.auth.check_token(self.headers.get("Authorization")):
            raise _HttpError(401, "업로드 토큰이 맞지 않습니다")

    def _read_json(self, limit: int):
        length = self.headers.get("Content-Length")
        if length is None or not length.isdigit():
            raise _HttpError(411, "본문 길이(Content-Length)가 필요합니다")
        if int(length) > limit:
            raise _HttpError(413, "본문이 너무 큽니다")
        raw = self.rfile.read(int(length))
        self._body_read = True
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise _HttpError(400, "JSON 형식이 아닙니다")

    def _drain(self) -> None:
        """거절하기 전에 보내던 본문을 받아 둔다 — 아니면 보내는 쪽(Windows)이 이유 대신 '연결 끊김'을 본다."""
        length = self.headers.get("Content-Length") or ""
        if self._body_read or not length.isdigit() or int(length) > LECTURE_MAX_BYTES:
            return
        self._body_read = True
        left = int(length)
        try:
            while left > 0:  # 조금씩 읽고 버린다(메모리를 쌓지 않음)
                chunk = self.rfile.read(min(left, 64 * 1024))
                if not chunk:
                    break
                left -= len(chunk)
        except OSError:
            self.close_connection = True

    # ---- 응답 ----
    def _host_ok(self) -> bool:
        host = self.headers.get("Host", "")
        return host in (f"127.0.0.1:{self.server.port}", f"localhost:{self.server.port}")

    def _static(self, name: str):
        name = unquote(name)
        if not name or "/" in name or "\\" in name or name.startswith("."):
            return self._error(404, "없는 파일입니다")
        path = self.server.web_dir / name
        ctype = STATIC_TYPES.get(path.suffix.lower())
        if ctype is None or not path.is_file():
            return self._error(404, "없는 파일입니다")
        self._send(200, ctype, path.read_bytes())

    def _json(self, status: int, data, headers: dict | None = None) -> None:
        self._send(status, "application/json; charset=utf-8",
                   json.dumps(data, ensure_ascii=False).encode("utf-8"), headers)

    def _error(self, status: int, message: str) -> None:
        self._json(status, {"error": message})

    def _send(self, status: int, ctype: str, body: bytes, headers: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CSP)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)


def _held_elsewhere(port: int) -> bool:
    """다른 프로그램이 모든 주소(0.0.0.0 / ::)에서 이 포트를 쓰는지 미리 확인한다.
    Windows는 이 경우에도 127.0.0.1 bind를 허용해 요청이 엉뚱한 프로그램으로 갈 수 있다."""
    for family, host in ((socket.AF_INET, "0.0.0.0"), (getattr(socket, "AF_INET6", None), "::")):
        if family is None:
            continue
        try:
            probe = socket.socket(family, socket.SOCK_STREAM)
        except OSError:
            continue  # 이 PC에서 IPv6를 쓰지 않음
        try:
            probe.bind((host, port))
        except OSError:
            return True
        finally:
            probe.close()
    return False


def bind(store: FileStore, web_dir: Path, port: int = DEFAULT_PORT,
         idle_timeout: float = IDLE_TIMEOUT_SEC) -> LibraryServer:
    last = None
    for candidate in range(port, port + PORT_RANGE):
        if _held_elsewhere(candidate):
            last = f"{candidate}번 포트는 다른 프로그램이 사용 중"
            continue
        try:
            return LibraryServer(("127.0.0.1", candidate), store, web_dir, idle_timeout)
        except OSError as exc:
            last = exc
    raise StepError(f"빈 포트를 찾지 못했습니다({port}~{port + PORT_RANGE - 1}): {last}")


def run(server: LibraryServer, state_path: Path, check_every: float = 30.0) -> None:
    write_json(state_path, {"port": server.port, "pid": os.getpid(), "home": str(server.store.home)})
    stop = threading.Event()

    def watchdog():
        while not stop.wait(check_every):
            if server.idle():
                server.shutdown()
                return

    threading.Thread(target=watchdog, daemon=True).start()
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        stop.set()
        server.server_close()
        try:
            if read_json(state_path).get("pid") == os.getpid():
                state_path.unlink()
        except (ValueError, OSError, AttributeError):
            pass


def hosted_server(env: Mapping[str, str], host: str = "0.0.0.0") -> LibraryServer:
    """Railway 서버. 비밀번호·토큰 해시가 없으면 켜지 않는다(실수로 열린 서버를 막는다)."""
    for name in SECRET_VARS:
        if not env.get(name):
            raise StepError(f"{name} 환경변수가 없습니다 — 사용자가 'vl.py connect' 로 설정합니다")
    try:
        auth = Auth(env["VL_ADMIN_PASSWORD_HASH"], env["VL_UPLOAD_TOKEN_HASH"])
    except ValueError as exc:
        raise StepError(str(exc)) from exc
    home = ensure_home(Path(env.get("VL_HOME") or "/data"))
    port = int(env.get("PORT") or 8080)
    return LibraryServer((host, port), HostedStore(home), BUNDLED_WEB, auth=auth)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py serve", description="영상자료실 화면을 보여 주는 서버(PC 전용 미니 서버, 또는 --hosted 로 Railway 서버).")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--idle", type=float, default=IDLE_TIMEOUT_SEC, help="이 시간(초) 동안 요청이 없으면 끈다")
    ap.add_argument("--hosted", action="store_true", help="Railway 서버로 실행(환경변수 PORT·VL_HOME·해시 2개)")
    a = ap.parse_args(argv)
    if a.hosted:
        server = hosted_server(os.environ)
        print(f"video-library Railway 서버: 포트 {server.port}", flush=True)
        try:
            server.serve_forever(poll_interval=0.5)
        finally:
            server.server_close()
        return 0
    home = ensure_home(library_home())
    web = home / "app"
    if not (web / "library.html").exists():
        raise StepError("화면 파일이 없습니다. 'vl.py open' 으로 여세요.")
    server = bind(FileStore(home), web, a.port, a.idle)
    print(f"영상자료실: http://127.0.0.1:{server.port}  (1시간 동안 쓰지 않으면 스스로 꺼집니다)", flush=True)
    run(server, home / SERVER_STATE)
    return 0
