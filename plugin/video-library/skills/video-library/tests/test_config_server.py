import pytest

from video_library import config
from video_library.config import server_url, write_json, write_text


def test_server_url_default(home):
    assert server_url(home) == "http://127.0.0.1:8765"


def test_server_url_from_state(home):
    write_json(home / ".server.json", {"port": 8771, "pid": 1, "home": str(home)})
    assert server_url(home) == "http://127.0.0.1:8771"


def test_server_url_with_broken_state(home):
    (home / ".server.json").write_text("{깨짐", encoding="utf-8")
    assert server_url(home) == "http://127.0.0.1:8765"


def test_write_text_retries_when_file_is_busy(tmp_path, monkeypatch):
    real = config.os.replace
    calls = {"n": 0}

    def busy_twice(src, dst):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise PermissionError("[WinError 5] 다른 프로세스가 사용 중")
        return real(src, dst)

    monkeypatch.setattr(config.os, "replace", busy_twice)
    monkeypatch.setattr(config.time, "sleep", lambda s: None)
    write_text(tmp_path / "index.json", "[]\n")
    assert (tmp_path / "index.json").read_text(encoding="utf-8") == "[]\n" and calls["n"] == 3


def test_write_text_gives_up_after_retries(tmp_path, monkeypatch):
    def always_busy(src, dst):
        raise PermissionError("busy")

    monkeypatch.setattr(config.os, "replace", always_busy)
    monkeypatch.setattr(config.time, "sleep", lambda s: None)
    with pytest.raises(PermissionError):
        write_text(tmp_path / "x.json", "{}")
