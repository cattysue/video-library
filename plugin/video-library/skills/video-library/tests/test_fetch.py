import json
from datetime import datetime
from pathlib import Path

import pytest

from video_library import fetch as fetch_mod
from video_library.config import KST, StepError, read_json, work_dir, write_json

VID = "AbCdEfGhIjK"
URL = f"https://youtu.be/{VID}"
NOW = datetime(2026, 10, 5, 14, 3, tzinfo=KST)
CAPTION = (Path(__file__).resolve().parent / "fixtures" / "auto_ko.json3").read_text(encoding="utf-8")
J3 = [{"ext": "json3", "url": "y"}]


def info(**over):
    base = {"id": VID, "title": "깃 기초", "channel": "샘플 채널", "duration": 480, "language": "ko",
            "automatic_captions": {"ko": J3}, "live_status": "not_live", "availability": "public"}
    base.update(over)
    return base


class FakeYDL:
    def __init__(self, opts, info, caption, write=True):
        self.opts, self.info, self.caption, self.write = opts, info, caption, write

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=False):
        assert download is False
        return self.info

    def download(self, urls):
        if self.write:
            track = self.opts["subtitleslangs"][0]
            Path(self.opts["outtmpl"].replace("%(ext)s", f"{track}.json3")).write_text(self.caption, encoding="utf-8")
        return 0


def factory(info_dict, write=True, seen=None):
    def make(opts):
        if seen is not None:
            seen.append(opts)
        return FakeYDL(opts, info_dict, CAPTION, write)
    return make


def test_fetch_creates_work_folder_and_job(home):
    out = fetch_mod.fetch(URL, home, ydl_factory=factory(info()), now=NOW)
    work = work_dir(home, VID)
    assert out == {"video_id": VID, "job_id": f"{VID}-1005-1403", "work_dir": str(work), "title": "깃 기초",
                   "duration": 480.0, "language": "ko", "caption_kind": "auto", "long": False, "translate": False,
                   "upload": False}
    assert read_json(work / "raw" / "source.json3")["wireMagic"] == "pb3"
    assert read_json(work / "raw" / "info.json")["caption_track"] == "ko"
    assert read_json(work / "build" / "request.json") == {
        "video_id": VID, "url": f"https://www.youtube.com/watch?v={VID}", "job_id": f"{VID}-1005-1403",
        "translate_en": False, "lang_override": None}
    job = read_json(home / "jobs" / f"{VID}-1005-1403.json")
    assert job["steps"]["fetch"] == "done" and job["steps"]["translate"] == "skipped"


def test_foreign_video_needs_translation(home):
    foreign = info(language="en", automatic_captions={"en-orig": J3})
    out = fetch_mod.fetch(URL, home, ydl_factory=factory(foreign), now=NOW)
    assert out["translate"] is True and out["language"] == "en"
    assert read_json(home / "jobs" / f"{VID}-1005-1403.json")["steps"]["translate"] == "pending"


def test_translate_en_on_korean_video(home):
    out = fetch_mod.fetch(URL, home, translate_en=True, ydl_factory=factory(info()), now=NOW)
    assert out["translate"] is True


def test_refetch_clears_build(home):
    stale = work_dir(home, VID) / "build" / "chunks" / "01.edits.json"
    write_json(stale, [])
    fetch_mod.fetch(URL, home, ydl_factory=factory(info()), now=NOW)
    assert not stale.exists()


def test_long_video_flag(home):
    out = fetch_mod.fetch(URL, home, ydl_factory=factory(info(duration=4000)), now=NOW)
    assert out["long"] is True


def test_missing_subtitle_file(home):
    with pytest.raises(StepError, match="자막 파일을 받지 못했습니다"):
        fetch_mod.fetch(URL, home, ydl_factory=factory(info(), write=False), now=NOW)


def test_private_video_rejected_before_download(home):
    with pytest.raises(StepError, match="비공개"):
        fetch_mod.fetch(URL, home, ydl_factory=factory(info(availability="private")), now=NOW)
    assert not list((home / "jobs").iterdir())


def test_zero_duration_rejected(home):
    with pytest.raises(StepError, match="영상 길이"):
        fetch_mod.fetch(URL, home, ydl_factory=factory(info(duration=None)), now=NOW)


def test_http_403_explained(home):
    def boom(opts):
        raise RuntimeError("ERROR: unable to download: HTTP Error 403: Forbidden")
    with pytest.raises(StepError, match="403"):
        fetch_mod.fetch(URL, home, ydl_factory=boom, now=NOW)


def test_missing_yt_dlp_explained(home):
    def missing(opts):
        raise ModuleNotFoundError("No module named 'yt_dlp'")
    with pytest.raises(StepError, match="vl.py doctor"):
        fetch_mod.fetch(URL, home, ydl_factory=missing, now=NOW)


def test_node_enabled_when_deno_missing(monkeypatch):
    monkeypatch.setattr(fetch_mod.shutil, "which", lambda name: "C:/node.exe" if name == "node" else None)
    assert fetch_mod.base_opts()["js_runtimes"] == {"node": {}}
    monkeypatch.setattr(fetch_mod.shutil, "which", lambda name: "C:/deno.exe")
    assert "js_runtimes" not in fetch_mod.base_opts()


def test_subtitle_download_options(home):
    seen = []
    fetch_mod.fetch(URL, home, ydl_factory=factory(info(), seen=seen), now=NOW)
    sub = seen[1]
    assert sub["skip_download"] is True and sub["writeautomaticsub"] is True and sub["writesubtitles"] is False
    assert sub["subtitleslangs"] == ["ko"] and sub["subtitlesformat"] == "json3"


def test_main_prints_json(home, monkeypatch, capsys):
    monkeypatch.setattr(fetch_mod, "_default_ydl_factory", factory(info()))
    assert fetch_mod.main([URL]) == 0
    assert json.loads(capsys.readouterr().out)["video_id"] == VID


def test_upload_step_pending_only_with_config(home):
    from video_library import remote
    remote.save_config(home, "https://video-library.up.railway.app", "tok")
    out = fetch_mod.fetch(URL, home, ydl_factory=factory(info()), now=NOW, upload=False)
    assert out["upload"] is False
    out = fetch_mod.fetch(URL, home, ydl_factory=factory(info()), now=NOW)
    assert out["upload"] is True
    assert read_json(home / "jobs" / f"{out['job_id']}.json")["steps"]["upload"] == "pending"
