"""영상자료실 열기: 화면·서버 실행 파일 설치(app/), 더블클릭 열기 파일, 미니 서버 확인·시작, 브라우저 열기."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

from .config import SERVER_STATE, StepError, ensure_home, library_home, read_json

SCRIPTS_DIR = Path(__file__).resolve().parent.parent  # 플러그인의 scripts/ (또는 영상자료실 app/runtime/)
WEB_SRC = SCRIPTS_DIR.parent / "web"
LAUNCHER_WIN = "영상자료실 열기.bat"
LAUNCHER_MAC = "영상자료실 열기.command"


def _same(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def write_launcher(home: Path, runtime: Path) -> Path:
    python = sys.executable
    if sys.platform == "win32":
        path = home / LAUNCHER_WIN
        text = ("@echo off\r\nchcp 65001 >nul\r\n"
                f'"{python}" "%~dp0app\\runtime\\vl.py" open\r\n'
                "if errorlevel 1 pause\r\n")
        path.write_text(text, encoding="utf-8", newline="")
    else:
        path = home / LAUNCHER_MAC
        text = f'#!/bin/sh\ncd "$(dirname "$0")"\nexec "{python}" "app/runtime/vl.py" open\n'
        path.write_text(text, encoding="utf-8", newline="\n")
        path.chmod(0o755)
    return path


def runtime_home() -> Path | None:
    """영상자료실 app/runtime/ 사본에서 실행 중이면 그 자료실 폴더(열기 파일이 있는 곳)."""
    if SCRIPTS_DIR.name == "runtime" and SCRIPTS_DIR.parent.name == "app":
        return SCRIPTS_DIR.parent.parent
    return None


def install_app(home: Path) -> Path:
    app = home / "app"
    runtime = app / "runtime"
    if _same(SCRIPTS_DIR, runtime):
        return app  # 영상자료실의 사본에서 실행 중 — 자기 자신을 덮어쓰지 않는다
    app.mkdir(parents=True, exist_ok=True)
    if WEB_SRC.is_dir():
        for src in WEB_SRC.iterdir():
            if src.is_file():
                shutil.copy2(src, app / src.name)
    fresh, old = app / "runtime.new", app / "runtime.old"
    for leftover in (fresh, old):
        if leftover.exists():
            shutil.rmtree(leftover, ignore_errors=True)
    shutil.copytree(SCRIPTS_DIR, fresh, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    try:
        if runtime.exists():
            os.replace(runtime, old)
        os.replace(fresh, runtime)
        shutil.rmtree(old, ignore_errors=True)
    except OSError as exc:
        print(f"경고: 서버 실행 파일을 새로 바꾸지 못했습니다({exc}) — 이전 사본으로 계속합니다.", file=sys.stderr)
        if not runtime.exists() and old.exists():
            os.replace(old, runtime)
    write_launcher(home, runtime)
    return app


def server_alive(home: Path) -> str | None:
    try:
        state = read_json(home / SERVER_STATE)
        port = int(state["port"])
    except (ValueError, OSError, KeyError, TypeError):
        return None
    url = f"http://127.0.0.1:{port}"
    no_proxy = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 시스템 프록시를 거치지 않는다
    try:
        with no_proxy.open(f"{url}/api/health", timeout=1) as resp:
            info = json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    if info.get("app") == "video-library" and Path(info.get("home", "")) == Path(home):
        return url
    return None


def start_detached(home: Path) -> None:
    runtime_vl = home / "app" / "runtime" / "vl.py"
    env = {**os.environ, "VL_HOME": str(home), "PYTHONDONTWRITEBYTECODE": "1"}
    kwargs = {"stdin": subprocess.DEVNULL, "cwd": str(home), "env": env}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    with open(home / "app" / "server.log", "ab") as log:
        subprocess.Popen([sys.executable, str(runtime_vl), "serve"], stdout=log, stderr=log, **kwargs)


def ensure_server(home: Path, starter=None, wait: float = 10.0) -> str:
    url = server_alive(home)
    if url:
        return url
    (starter or start_detached)(home)
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        time.sleep(0.2)
        url = server_alive(home)
        if url:
            return url
    raise StepError("미니 서버를 켜지 못했습니다. 영상자료실/app/server.log 를 확인하세요.")


def open_library(home: Path, browser: bool = True, starter=None) -> str:
    ensure_home(home)
    install_app(home)
    url = ensure_server(home, starter=starter or start_detached)
    if browser:
        webbrowser.open(url)
    return url


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py open", description="영상자료실 화면을 연다(미니 서버가 꺼져 있으면 켠다).")
    ap.add_argument("--no-browser", action="store_true", help="브라우저는 열지 않고 주소만 출력")
    a = ap.parse_args(argv)
    home = runtime_home() or library_home()
    url = open_library(home, browser=not a.no_browser)
    print(json.dumps({"url": url, "home": str(home)}, ensure_ascii=False))
    return 0
