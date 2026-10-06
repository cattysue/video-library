"""Railway 관리자 로그인과 업로드 토큰 확인. 비밀번호·토큰은 해시로만 다룬다(표준 라이브러리)."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time

PBKDF2_ITERATIONS = 200_000
SESSION_TTL_SEC = 12 * 3600
LOGIN_WINDOW_SEC = 15 * 60
LOGIN_MAX_FAILURES = 10
COOKIE = "vl_session"
_HEX = set("0123456789abcdef")


def hash_password(password: str, salt: bytes | None = None, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, digest_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iters))
    except (ValueError, AttributeError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_cookie(sid: str, expire: bool = False) -> str:
    age = 0 if expire else SESSION_TTL_SEC
    return f"{COOKIE}={sid}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age={age}"


class LoginLocked(Exception):
    """로그인 실패가 많아 잠시 막힌 상태."""


class Auth:
    def __init__(self, password_hash: str, token_hash: str, clock=time.monotonic):
        if not isinstance(password_hash, str) or not password_hash.startswith("pbkdf2_sha256$") \
                or password_hash.count("$") != 3:
            raise ValueError("VL_ADMIN_PASSWORD_HASH 형식이 올바르지 않습니다")
        if not isinstance(token_hash, str) or len(token_hash) != 64 or not set(token_hash) <= _HEX:
            raise ValueError("VL_UPLOAD_TOKEN_HASH 형식이 올바르지 않습니다")
        self._password_hash = password_hash
        self._token_hash = token_hash
        self._clock = clock
        self._sessions: dict[str, float] = {}
        self._failures: list[float] = []
        self._inflight = 0  # 지금 확인 중인 로그인 수(동시에 보내 잠금을 건너뛰지 못하게)
        self._lock = threading.Lock()
        self._verify_lock = threading.Lock()  # 비밀번호 계산은 한 번에 하나(CPU 보호)

    def check_token(self, authorization) -> bool:
        if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
            return False
        return hmac.compare_digest(hash_token(authorization[len("Bearer "):].strip()), self._token_hash)

    def login(self, password: str) -> str | None:
        with self._lock:
            now = self._clock()
            self._failures = [t for t in self._failures if now - t < LOGIN_WINDOW_SEC]
            if len(self._failures) + self._inflight >= LOGIN_MAX_FAILURES:
                raise LoginLocked()
            self._inflight += 1
        ok = False
        try:
            with self._verify_lock:
                ok = verify_password(password, self._password_hash)
        finally:
            with self._lock:
                self._inflight -= 1
                if not ok:
                    self._failures.append(self._clock())
        if not ok:
            return None
        with self._lock:
            sid = secrets.token_urlsafe(32)
            self._sessions[sid] = self._clock() + SESSION_TTL_SEC
            return sid

    def session_ok(self, sid) -> bool:
        if not sid:
            return False
        with self._lock:
            expires = self._sessions.get(sid)
            if expires is None:
                return False
            if expires <= self._clock():
                del self._sessions[sid]
                return False
            return True

    def logout(self, sid) -> None:
        if sid:
            with self._lock:
                self._sessions.pop(sid, None)
