import sys

from video_library import doctor


def patch(monkeypatch, ytdlp=True, deno=True, node=False):
    monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda name: object() if (name == "yt_dlp" and ytdlp) else None)
    found = {"deno": "C:/deno.exe" if deno else None, "node": "C:/node.exe" if node else None}
    monkeypatch.setattr(doctor.shutil, "which", lambda name: found.get(name))


def test_all_ok(home, monkeypatch, capsys):
    patch(monkeypatch)
    assert doctor.main([]) == 0
    out = capsys.readouterr().out
    assert "✓ yt-dlp 라이브러리" in out and "영상자료실" in out


def test_missing_yt_dlp_shows_install_command(home, monkeypatch, capsys):
    patch(monkeypatch, ytdlp=False)
    assert doctor.main([]) == 1
    out = capsys.readouterr().out
    assert "✗ yt-dlp 라이브러리" in out
    assert f'"{sys.executable}" -m pip install --user -U "yt-dlp[default]"' in out


def test_missing_js_runtime_is_only_a_warning(home, monkeypatch, capsys):
    patch(monkeypatch, deno=False, node=False)
    assert doctor.main([]) == 0
    out = capsys.readouterr().out
    assert "△ 자바스크립트 실행기" in out and "deno" in out


def test_node_counts_as_runtime(home, monkeypatch):
    patch(monkeypatch, deno=False, node=True)
    runtime = [c for c in doctor.run_checks(home) if c["name"].startswith("자바스크립트")][0]
    assert runtime["ok"] is True


def test_unwritable_library(home, monkeypatch, capsys):
    patch(monkeypatch)

    def deny(path):
        raise PermissionError("접근 거부")

    monkeypatch.setattr(doctor, "ensure_home", deny)
    assert doctor.main([]) == 1
    assert "✗ 영상자료실 폴더 쓰기" in capsys.readouterr().out
