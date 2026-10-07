"""영상자료실 위치, 작업 폴더 경로, 한국 시간, 원자적 파일 쓰기. 표준 라이브러리만."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

LIBRARY_NAME = "영상자료실"
KST = timezone(timedelta(hours=9))
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
DEFAULT_PORT = 8765
SERVER_STATE = ".server.json"
_REPLACE_RETRIES = 10


class StepError(Exception):
    """사용자에게 그대로 보여줄 한국어 오류. vl.py 가 받아 '오류: …' 로 출력하고 종료 코드 1."""


def _windows_documents() -> Path | None:
    """Windows '문서' 폴더의 실제 위치(OneDrive 로 옮긴 경우 포함). 실패하면 None."""
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

        # FOLDERID_Documents {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
        folder = GUID(0xFDD39AD0, 0x238F, 0x46AF,
                      (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
        out = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(folder), 0, None, ctypes.byref(out)) != 0:
            return None
        try:
            return Path(out.value)
        finally:
            ctypes.windll.ole32.CoTaskMemFree(out)
    except Exception:
        return None


def documents_dir() -> Path:
    if sys.platform == "win32":
        found = _windows_documents()
        if found is not None:
            return found
    return Path.home() / "Documents"


def library_home() -> Path:
    env = os.environ.get("VL_HOME")
    return Path(env) if env else documents_dir() / LIBRARY_NAME


def ensure_home(home: Path) -> Path:
    for sub in ("lectures", "jobs"):
        (home / sub).mkdir(parents=True, exist_ok=True)
    return home


def video_id_arg(value: str) -> str:
    """argparse 용: 유튜브 11자 영상 ID만 받는다(영상자료실 밖 경로가 섞이지 않게)."""
    if not VIDEO_ID_RE.fullmatch(value):
        raise argparse.ArgumentTypeError("영상 ID는 유튜브 11자 ID여야 합니다(예: 40JNj2zjnQc)")
    return value


def work_dir(home: Path, video_id: str) -> Path:
    return home / "lectures" / f"{video_id}.tmp"


def lecture_dir(home: Path, video_id: str) -> Path:
    return home / "lectures" / video_id


def now_kst() -> datetime:
    return datetime.now(KST)


def fmt_time(sec: float) -> str:
    s = int(sec)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def _reject_constant(name: str):
    raise ValueError(f"표준 JSON이 아닌 값 {name}")


def read_json(path):
    """UTF-8(BOM 허용) JSON. 형식·인코딩이 틀리면 ValueError."""
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), parse_constant=_reject_constant)


def _replace(src: Path, dst: Path) -> None:
    """os.replace — Windows 에서 다른 프로세스(미니 서버)가 잠깐 파일을 열고 있으면 몇 번 다시 시도한다."""
    for attempt in range(_REPLACE_RETRIES):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == _REPLACE_RETRIES - 1:
                raise
            time.sleep(0.05 * (attempt + 1))


def write_text(path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_text(text, encoding="utf-8")
    _replace(part, path)


def write_json(path, data) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def server_url(home: Path) -> str:
    """미니 서버 주소. 켜진 적이 없거나 기록이 깨졌으면 기본 포트."""
    port = DEFAULT_PORT
    try:
        state = read_json(Path(home) / SERVER_STATE)
        if isinstance(state.get("port"), int):
            port = state["port"]
    except (ValueError, OSError, AttributeError):
        pass
    return f"http://127.0.0.1:{port}"
