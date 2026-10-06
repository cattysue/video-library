import json
import sys
import threading

import pytest

from video_library import opener
from video_library.config import StepError, write_json
from video_library.server import LibraryServer, run
from video_library.store_file import FileStore


def start_in_thread(home):
    server = LibraryServer(("127.0.0.1", 0), FileStore(home), home / "app")
    thread = threading.Thread(target=run, args=(server, home / ".server.json"), kwargs={"check_every": 0.1}, daemon=True)
    thread.start()
    return server


def wait_alive(home):
    for _ in range(50):
        url = opener.server_alive(home)
        if url:
            return url
        threading.Event().wait(0.05)
    return None


def test_install_copies_web_and_runtime(home, monkeypatch):
    monkeypatch.setattr(opener.sys, "platform", "win32")
    app = opener.install_app(home)
    assert (app / "library.html").exists()
    assert (app / "runtime" / "vl.py").exists() and (app / "runtime" / "video_library" / "server.py").exists()
    assert not list((app / "runtime").rglob("__pycache__"))
    bat = home / "영상자료실 열기.bat"
    text = bat.read_text(encoding="utf-8")
    assert sys.executable in text and r"app\runtime\vl.py" in text and "open" in text


def test_reinstall_replaces_runtime(home):
    opener.install_app(home)
    stale = home / "app" / "runtime" / "stale.py"
    stale.write_text("old", encoding="utf-8")
    opener.install_app(home)
    assert not stale.exists() and (home / "app" / "runtime" / "vl.py").exists()


def test_install_from_runtime_copy_is_noop(home, monkeypatch):
    opener.install_app(home)
    marker = home / "app" / "library.html"
    marker.write_text("사용자 사본", encoding="utf-8")
    monkeypatch.setattr(opener, "SCRIPTS_DIR", home / "app" / "runtime")
    opener.install_app(home)
    assert marker.read_text(encoding="utf-8") == "사용자 사본"



def test_runtime_copy_uses_its_own_library(home, tmp_path, monkeypatch):
    # 열기 파일은 자기 폴더의 자료실을 연다(VL_HOME·문서 폴더 위치와 무관)
    moved = tmp_path / "옮긴 자료실"
    monkeypatch.setattr(opener, "SCRIPTS_DIR", moved / "app" / "runtime")
    assert opener.runtime_home() == moved
    monkeypatch.setattr(opener, "SCRIPTS_DIR", tmp_path / "plugin" / "scripts")
    assert opener.runtime_home() is None


def test_open_from_runtime_copy_opens_that_library(home, tmp_path, monkeypatch, capsys):
    moved = tmp_path / "옮긴 자료실"
    monkeypatch.setattr(opener, "SCRIPTS_DIR", moved / "app" / "runtime")
    monkeypatch.setattr(opener, "WEB_SRC", moved / "app" / "web")  # 사본 옆에는 web/이 없다
    seen = {}
    monkeypatch.setattr(opener, "ensure_server", lambda h, starter=None: seen.setdefault("home", h) and "http://127.0.0.1:9")
    assert opener.main(["--no-browser"]) == 0
    assert seen["home"] == moved and json.loads(capsys.readouterr().out)["home"] == str(moved)


def test_install_without_web_source_does_not_crash(home, monkeypatch):
    monkeypatch.setattr(opener, "WEB_SRC", home / "없음")
    app = opener.install_app(home)
    assert (app / "runtime" / "vl.py").exists()

def test_mac_launcher(home, monkeypatch):
    monkeypatch.setattr(opener.sys, "platform", "darwin")
    path = opener.write_launcher(home, home / "app" / "runtime")
    assert path.name == "영상자료실 열기.command"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("#!/bin/sh") and "app/runtime/vl.py" in text


def test_server_alive_and_reuse(home):
    opener.install_app(home)
    server = start_in_thread(home)
    try:
        assert wait_alive(home) == f"http://127.0.0.1:{server.port}"
        called = []
        assert opener.ensure_server(home, starter=called.append) == f"http://127.0.0.1:{server.port}"
        assert called == []
    finally:
        server.shutdown()


def test_server_alive_rejects_other_library(home, tmp_path):
    opener.install_app(home)
    server = start_in_thread(home)
    try:
        assert wait_alive(home)
        other = tmp_path / "다른 자료실"
        other.mkdir()
        write_json(other / ".server.json", {"port": server.port, "pid": 1, "home": str(other)})
        assert opener.server_alive(other) is None
    finally:
        server.shutdown()


def test_ensure_server_starts_when_down(home):
    opener.install_app(home)
    started = []

    def starter(h):
        started.append(start_in_thread(h))

    url = opener.ensure_server(home, starter=starter)
    try:
        assert url == f"http://127.0.0.1:{started[0].port}"
    finally:
        started[0].shutdown()


def test_ensure_server_gives_up(home):
    with pytest.raises(StepError, match="미니 서버를 켜지 못했습니다"):
        opener.ensure_server(home, starter=lambda h: None, wait=0.3)


def test_open_command_without_browser(home, monkeypatch, capsys):
    started = []
    monkeypatch.setattr(opener, "start_detached", lambda h: started.append(start_in_thread(h)))
    opened = []
    monkeypatch.setattr(opener.webbrowser, "open", opened.append)
    try:
        assert opener.main(["--no-browser"]) == 0
        out = json.loads(capsys.readouterr().out)
        assert out["url"] == f"http://127.0.0.1:{started[0].port}" and opened == []
    finally:
        started[0].shutdown()
