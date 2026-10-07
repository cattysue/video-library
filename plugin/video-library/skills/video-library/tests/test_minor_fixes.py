"""미뤄 둔 사소한 점 정리(10-07)."""
import json
from datetime import timedelta
from pathlib import Path

import pytest

from conftest import VIDEO_ID
from test_library import make_doc, stage
from video_library import jobs, library, remote, upload
from video_library.config import StepError, now_kst, video_id_arg, write_json
from video_library.server import CSP
from video_library.store_file import FileStore
from video_library.store_hosted import check_job

ROOT = Path(__file__).resolve().parents[5]


def test_ids_reject_trailing_newline():
    with pytest.raises(Exception):
        video_id_arg(VIDEO_ID + "\n")
    assert FileStore(Path(".")).get_lecture(VIDEO_ID + "\n") is None
    assert check_job(f"{VIDEO_ID}-1007-1200\n", {}) != []


def test_csp_forbids_framing():
    assert "frame-ancestors 'none'" in CSP


def test_stale_running_job_is_hidden(home):
    job = jobs.start_job(home, VIDEO_ID, "깃 기초", jobs.initial_steps(False, False))
    old = (now_kst() - timedelta(hours=7)).isoformat(timespec="seconds")
    job["updated_at"] = old
    write_json(jobs.job_path(home, job["job_id"]), job)
    assert FileStore(home).list_jobs() == []


def test_progress_detail_is_capped(home):
    job = jobs.start_job(home, VIDEO_ID, "깃 기초", jobs.initial_steps(False, False))
    saved = jobs.set_step(home, job["job_id"], "correct", "running", detail="가" * 500)
    assert len(saved["detail"]) <= 200


def test_upload_broken_lecture_file_is_explained(home):
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)
    (home / "lectures" / VIDEO_ID / "lecture.json").write_text("{망가짐", encoding="utf-8")
    with pytest.raises(StepError, match="lecture.json"):
        upload.upload(home, VIDEO_ID, {"server": "http://127.0.0.1:9", "token": "t"})


def test_upload_401_suggests_reconnect(home, monkeypatch):
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)
    monkeypatch.setattr(upload, "request", lambda *a, **k: (401, {"error": "업로드 토큰이 맞지 않습니다"}))
    with pytest.raises(StepError, match="vl.py connect"):
        upload.upload(home, VIDEO_ID, {"server": "http://127.0.0.1:9", "token": "t"})


def test_example_host_is_a_placeholder():
    for name in ("remote.py", "connect.py"):
        text = (ROOT / "plugin/video-library/skills/video-library/scripts/video_library" / name).read_text(encoding="utf-8")
        assert "https://video-library.up.railway.app" not in text, name


def test_readme_mac_railway_login_and_uninstall():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for needle in ("python3 -m pip", "railway login", "git clone https://github.com/cattysue/video-library",
                   "claude plugin marketplace remove video-library", "codex plugin marketplace remove video-library",
                   "영상자료실` 폴더는 지워지지 않"):
        assert needle in text, needle


def test_backlog_document_exists():
    text = (ROOT / "docs/backlog.md").read_text(encoding="utf-8")
    assert "우선순위" in text and "## 높음" in text and "## 낮음" in text
