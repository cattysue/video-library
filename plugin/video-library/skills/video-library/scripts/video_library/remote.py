"""Railway 연결: config.json(서버 주소·업로드 토큰) 읽기·쓰기, 요청 보내기, 진행 보고. 표준 라이브러리만."""
from __future__ import annotations

import http.client
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from .config import StepError, read_json, write_json

CONFIG_NAME = "config.json"
REPORT_TIMEOUT_SEC = 3.0
_SERVER_RE = re.compile(r"^(https://[A-Za-z0-9.-]+(:\d+)?|http://(127\.0\.0\.1|localhost):\d+)$")
_LOCAL = ("http://127.0.0.1:", "http://localhost:")


class RemoteError(Exception):
    """서버에 닿지 못함(연결 거부·시간 초과·주소 오류)."""


def normalize_server(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if not _SERVER_RE.match(url):
        raise StepError("서버 주소는 https:// 로 시작해야 합니다(예: https://<내 서비스>.up.railway.app)")
    return url


def load_config(home) -> dict:
    try:
        data = read_json(Path(home) / CONFIG_NAME)
        server = normalize_server(data["server"])
        token = data["token"]
    except (ValueError, OSError, KeyError, TypeError, AttributeError, StepError):
        return {}
    if not isinstance(token, str) or not token:
        return {}
    return {"server": server, "token": token}


def save_config(home, server: str, token: str) -> Path:
    path = Path(home) / CONFIG_NAME
    write_json(path, {"server": normalize_server(server), "token": token})
    try:
        os.chmod(path, 0o600)  # Mac·Linux: 본인만 읽기. Windows 는 무시된다
    except OSError:
        pass
    return path


def _opener(url: str):
    if url.startswith(_LOCAL):
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 시험용 서버는 프록시를 거치지 않는다
    return urllib.request.build_opener()


def request(method: str, url: str, token: str, body=None, timeout: float = 30.0) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "video-library"})
    try:
        with _opener(url).open(req, timeout=timeout) as resp:
            return resp.status, _json_or_empty(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, _json_or_empty(exc.read())
        finally:
            exc.close()  # 오류 응답도 연결을 닫는다
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException) as exc:
        raise RemoteError(str(getattr(exc, "reason", exc)) or type(exc).__name__) from exc


def _json_or_empty(raw: bytes) -> dict:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def report_job(home, job: dict, timeout: float = REPORT_TIMEOUT_SEC) -> bool:
    """진행 상황을 Railway 에도 알린다. 설정이 없거나 실패하면 조용히 넘어간다(처리는 계속)."""
    cfg = load_config(home)
    if not cfg:
        return False
    try:
        status, _ = request("POST", f"{cfg['server']}/api/jobs/{job['job_id']}", cfg["token"], job, timeout)
    except Exception:  # 보조 기능 — 어떤 오류도 처리를 멈추게 하지 않는다
        return False
    return status == 200
