from datetime import datetime

import pytest

from video_library import jobs
from video_library.config import KST, StepError, read_json, work_dir, write_json

VID = "AbCdEfGhIjK"
NOW = datetime(2026, 10, 5, 14, 3, 7, tzinfo=KST)


def new_job(home, translate=False):
    job = jobs.start_job(home, VID, "샘플", jobs.initial_steps(translate, upload_enabled=False), now=NOW)
    write_json(work_dir(home, VID) / "build" / "request.json", {"video_id": VID, "job_id": job["job_id"]})
    return job


def test_initial_steps():
    steps = jobs.initial_steps(translate_needed=False, upload_enabled=False)
    assert list(steps) == list(jobs.STEPS)
    assert steps["fetch"] == "running" and steps["preprocess"] == "pending"
    assert steps["translate"] == "skipped" and steps["upload"] == "skipped"
    assert jobs.initial_steps(True, True)["translate"] == "pending"


def test_start_job_writes_file(home):
    job = new_job(home)
    assert job["job_id"] == "AbCdEfGhIjK-1005-1403"
    saved = read_json(home / "jobs" / "AbCdEfGhIjK-1005-1403.json")
    assert saved["status"] == "running" and saved["started_at"] == "2026-10-05T14:03:07+09:00"


def test_set_step_and_failure_then_retry(home):
    job = new_job(home)
    jobs.set_step(home, job["job_id"], "correct", "running", detail="3/8")
    assert jobs.load_job(home, job["job_id"])["detail"] == "3/8"
    failed = jobs.set_step(home, job["job_id"], "correct", "failed", error="조각 02 불합격")
    assert failed["status"] == "failed" and failed["error"] == "조각 02 불합격"
    retried = jobs.set_step(home, job["job_id"], "correct", "running")
    assert retried["status"] == "running" and retried["error"] is None


def test_set_step_rejects_unknown(home):
    job = new_job(home)
    with pytest.raises(StepError):
        jobs.set_step(home, job["job_id"], "render", "running")
    with pytest.raises(StepError):
        jobs.set_step(home, job["job_id"], "fetch", "half")


def test_load_missing_job(home):
    with pytest.raises(StepError, match="작업 기록이 없습니다"):
        jobs.load_job(home, "nope")


def test_finish_job_only_overrides_unfinished(home):
    job = new_job(home)
    done = jobs.finish_job(home, job["job_id"], {"fetch": "done", "translate": "done", "glossary": "skipped"})
    assert done["status"] == "done"
    assert done["steps"]["fetch"] == "done"
    assert done["steps"]["translate"] == "skipped"  # 이미 skipped 였으므로 그대로
    assert done["steps"]["glossary"] == "skipped"


def test_track_marks_done(home):
    job = new_job(home)
    with jobs.track(home, VID, "preprocess") as job_id:
        assert job_id == job["job_id"]
        assert jobs.load_job(home, job_id)["steps"]["preprocess"] == "running"
    assert jobs.load_job(home, job["job_id"])["steps"]["preprocess"] == "done"


def test_track_marks_failed_and_reraises(home):
    job = new_job(home)
    with pytest.raises(StepError):
        with jobs.track(home, VID, "chunk"):
            raise StepError("문장이 없습니다")
    saved = jobs.load_job(home, job["job_id"])
    assert saved["steps"]["chunk"] == "failed" and saved["error"] == "문장이 없습니다"


def test_track_without_job_records_nothing(home):
    with jobs.track(home, VID, "chunk") as job_id:
        assert job_id is None
    assert not list((home / "jobs").iterdir())


def test_progress_command(home, capsys):
    job = new_job(home)
    assert jobs.main(["--video", VID, "--step", "correct", "--detail", "2/5"]) == 0
    assert jobs.load_job(home, job["job_id"])["steps"]["correct"] == "running"
    assert "correct: running (2/5)" in capsys.readouterr().out


def test_progress_without_job(home):
    with pytest.raises(StepError, match="진행 중인 작업이 없습니다"):
        jobs.main(["--video", VID, "--step", "correct"])


def test_finish_job_waits_for_upload(home):
    job = jobs.start_job(home, "AbCdEfGhIjK", "깃 기초", jobs.initial_steps(False, True))
    waiting = jobs.finish_job(home, job["job_id"], {"glossary": "done"})
    assert waiting["status"] == "running" and waiting["detail"] == "업로드 대기"
    assert jobs.pending_upload_job(home, "AbCdEfGhIjK") == job["job_id"]
    done = jobs.finish_job(home, job["job_id"], {"upload": "done"})
    assert done["status"] == "done" and done["steps"]["upload"] == "done"
    assert jobs.pending_upload_job(home, "AbCdEfGhIjK") is None


def test_upload_failure_keeps_pc_result_done(home):
    # 감수 R2: 업로드만 실패하면 작업 전체를 '실패'로 보이지 않는다(PC 저장은 끝남)
    job = jobs.start_job(home, "AbCdEfGhIjK", "깃 기초", jobs.initial_steps(False, True))
    jobs.finish_job(home, job["job_id"], {"assemble": "done"})  # 실제 흐름: 조립 완료 → 업로드 대기
    failed = jobs.set_step(home, job["job_id"], "upload", "failed", error="업로드 실패(401)")
    assert failed["status"] == "done" and failed["steps"]["upload"] == "failed"
    assert failed["error"] == "업로드 실패(401)" and "PC 저장 완료" in failed["detail"]
    assert jobs.pending_upload_job(home, "AbCdEfGhIjK") == job["job_id"]  # 다시 올리기 가능
    retry = jobs.set_step(home, job["job_id"], "upload", "running")
    assert retry["error"] is None and retry["status"] == "running"
