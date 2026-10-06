import importlib.util
import sys
from pathlib import Path

import pytest

from video_library import config
from video_library.config import (StepError, ensure_home, fmt_time, lecture_dir, library_home,
                                  read_json, work_dir, write_json, write_text)

VL = Path(__file__).resolve().parent.parent / "scripts" / "vl.py"


def _load_vl():
    spec = importlib.util.spec_from_file_location("vl_under_test", VL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_vl_home_env_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("VL_HOME", str(tmp_path / "x"))
    assert library_home() == tmp_path / "x"


def test_default_home_is_documents_library(monkeypatch, tmp_path):
    monkeypatch.delenv("VL_HOME")
    monkeypatch.setattr(config, "documents_dir", lambda: tmp_path / "Docs")
    assert library_home() == tmp_path / "Docs" / "영상자료실"


def test_documents_fallback_on_non_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(config.sys, "platform", "linux")
    monkeypatch.setattr(config.Path, "home", lambda: tmp_path)
    assert config.documents_dir() == tmp_path / "Documents"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows 전용")
def test_windows_documents_folder_found():
    found = config._windows_documents()
    assert found is not None and found.is_dir()


def test_ensure_home_with_korean_and_space_path(home):
    assert (home / "lectures").is_dir() and (home / "jobs").is_dir()
    assert " " in str(home) and "영상자료실" in str(home)


def test_work_and_lecture_dirs(home):
    assert work_dir(home, "AbCdEfGhIjK") == home / "lectures" / "AbCdEfGhIjK.tmp"
    assert lecture_dir(home, "AbCdEfGhIjK") == home / "lectures" / "AbCdEfGhIjK"


def test_write_read_json_roundtrip_is_atomic(tmp_path):
    path = tmp_path / "a" / "b.json"
    write_json(path, {"한글": [1, 2.5]})
    assert read_json(path) == {"한글": [1, 2.5]}
    assert "한글" in path.read_text(encoding="utf-8")
    assert not list(tmp_path.rglob("*.part"))


def test_read_json_accepts_bom(tmp_path):
    path = tmp_path / "bom.json"
    path.write_text('{"a": 1}', encoding="utf-8-sig")
    assert read_json(path) == {"a": 1}


def test_read_json_rejects_nan_and_cp949(tmp_path):
    nan = tmp_path / "nan.json"
    nan.write_text('{"a": NaN}', encoding="utf-8")
    with pytest.raises(ValueError):
        read_json(nan)
    cp = tmp_path / "cp.json"
    cp.write_bytes('{"a": "한글"}'.encode("cp949"))
    with pytest.raises(ValueError):
        read_json(cp)


def test_write_text(tmp_path):
    write_text(tmp_path / "t" / "x.md", "가\n")
    assert (tmp_path / "t" / "x.md").read_text(encoding="utf-8") == "가\n"


def test_fmt_time():
    assert fmt_time(0) == "0:00:00"
    assert fmt_time(3725.9) == "1:02:05"


def test_now_kst_has_korean_offset():
    assert config.now_kst().utcoffset().total_seconds() == 9 * 3600


def test_vl_prints_step_error(tmp_path, monkeypatch, capsys):
    (tmp_path / "boom_cmd.py").write_text(
        "from video_library.config import StepError\n\ndef main(argv):\n    raise StepError('자막이 없습니다')\n",
        encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    vl = _load_vl()
    monkeypatch.setitem(vl.COMMANDS, "boom", ("boom_cmd", "테스트"))
    assert vl.main(["boom"]) == 1
    assert "오류: 자막이 없습니다" in capsys.readouterr().err
