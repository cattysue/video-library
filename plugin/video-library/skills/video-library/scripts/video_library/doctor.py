"""0단계: 실행 환경 점검 + OS별 설치 명령 안내. 설치는 하지 않는다(사용자 승인 후 AI 가 실행)."""
from __future__ import annotations

import importlib.metadata
import importlib.util
import platform
import shutil
import sys
from pathlib import Path

from .config import ensure_home, library_home


def _ytdlp_version() -> str:
    try:
        return importlib.metadata.version("yt-dlp")
    except importlib.metadata.PackageNotFoundError:
        return "설치됨"


def _js_fix() -> str:
    if sys.platform == "win32":
        return "winget install --id DenoLand.Deno -e"
    if sys.platform == "darwin":
        return "brew install deno"
    return "curl -fsSL https://deno.land/install.sh | sh"


def _library_check(home: Path) -> dict:
    check = {"name": "영상자료실 폴더 쓰기", "required": True, "detail": str(home),
             "fix": "폴더 권한을 확인하거나 환경변수 VL_HOME 으로 다른 위치를 지정하세요."}
    try:
        ensure_home(home)
        probe = home / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        check["ok"] = True
    except OSError as exc:
        check["ok"] = False
        check["detail"] = f"{home} — {exc}"
    return check


def run_checks(home: Path) -> list[dict]:
    has_ytdlp = importlib.util.find_spec("yt_dlp") is not None
    runtime = shutil.which("deno") or shutil.which("node")
    return [
        {"name": "Python 3.10 이상", "ok": sys.version_info >= (3, 10), "required": True,
         "detail": platform.python_version(),
         "fix": "https://www.python.org/downloads/ 에서 Python 3.12 이상을 설치하세요."},
        {"name": "yt-dlp 라이브러리", "ok": has_ytdlp, "required": True,
         "detail": _ytdlp_version() if has_ytdlp else "없음",
         "fix": f'"{sys.executable}" -m pip install --user -U "yt-dlp[default]"'},
        {"name": "자바스크립트 실행기(deno 또는 node, 권장)", "ok": bool(runtime), "required": False,
         "detail": runtime or "없음", "fix": _js_fix()},
        _library_check(home),
    ]


def main(argv: list[str]) -> int:
    home = library_home()
    checks = run_checks(home)
    print(f"파이썬: {sys.executable}")
    print(f"영상자료실: {home}")
    for c in checks:
        mark = "✓" if c["ok"] else ("✗" if c["required"] else "△")
        print(f"{mark} {c['name']} — {c['detail']}")
    missing = [c for c in checks if not c["ok"]]
    if missing:
        print("\n설치·조치 명령(사용자 승인 후 실행):")
        for c in missing:
            print(f"  [{c['name']}] {c['fix']}")
    return 0 if all(c["ok"] for c in checks if c["required"]) else 1
