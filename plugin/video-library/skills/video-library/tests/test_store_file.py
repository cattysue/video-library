import json
from datetime import datetime, timedelta

from conftest import VIDEO_ID
from test_library import make_doc, stage
from video_library import library
from video_library.config import KST, write_json
from video_library.store_file import FileStore

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=KST)


def publish(home, vid=VIDEO_ID, processed_at="2026-10-05T14:03:00+09:00"):
    stage(home, make_doc(vid, processed_at))
    library.commit_lecture(home, vid)


def job(home, job_id, status, updated):
    write_json(home / "jobs" / f"{job_id}.json", {"job_id": job_id, "lecture_id": VIDEO_ID, "title": "t",
                                                  "status": status, "started_at": updated.isoformat(),
                                                  "updated_at": updated.isoformat(), "steps": {}, "detail": "",
                                                  "error": None})


def test_list_and_get(home):
    publish(home)
    publish(home, "ZzZzZzZzZzZ", "2026-10-06T09:00:00+09:00")
    store = FileStore(home)
    assert [e["id"] for e in store.list_lectures()] == ["ZzZzZzZzZzZ", VIDEO_ID]
    assert store.get_lecture(VIDEO_ID)["lecture"]["id"] == VIDEO_ID
    assert [d["lecture"]["id"] for d in store.all_lectures()] == ["ZzZzZzZzZzZ", VIDEO_ID]


def test_get_rejects_bad_or_missing_ids(home):
    publish(home)
    store = FileStore(home)
    assert store.get_lecture("../../x") is None
    assert store.get_lecture("NoSuchVideo") is None
    assert store.get_lecture("") is None


def test_broken_index_falls_back_without_writing(home):
    publish(home)
    (home / "index.json").write_text("{깨짐", encoding="utf-8")
    assert [e["id"] for e in FileStore(home).list_lectures()] == [VIDEO_ID]
    assert (home / "index.json").read_text(encoding="utf-8") == "{깨짐"


def test_empty_library(home):
    assert FileStore(home).list_lectures() == [] and FileStore(home).all_lectures() == []


def test_list_jobs_filters_old_finished_jobs(home):
    job(home, "running-old", "running", NOW - timedelta(days=2))  # 멈춘 작업(6시간 넘음) → 숨김(10-07 결정)
    job(home, "running-now", "running", NOW - timedelta(hours=1))
    job(home, "done-recent", "done", NOW - timedelta(minutes=5))
    job(home, "done-old", "done", NOW - timedelta(hours=2))
    job(home, "failed-recent", "failed", NOW - timedelta(minutes=30))
    (home / "jobs" / "broken.json").write_text("{깨짐", encoding="utf-8")
    ids = [j["job_id"] for j in FileStore(home).list_jobs(now=NOW)]
    assert ids == ["done-recent", "failed-recent", "running-now"]


def test_version_changes_when_index_changes(home):
    store = FileStore(home)
    assert store.version() == "none"
    publish(home)
    first = store.version()
    publish(home, "ZzZzZzZzZzZ", "2026-10-06T09:00:00+09:00")
    assert store.version() != first


def test_upload_failed_job_stays_listed_until_dismissed(home):
    # 재감수 N2: 업로드 실패 경고는 1시간이 지나도 목록에 남는다(화면에서 닫을 때까지)
    j = job(home, "upload-failed-old", "done", NOW - timedelta(hours=5))
    path = home / "jobs" / "upload-failed-old.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["steps"]["upload"] = "failed"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert [x["job_id"] for x in FileStore(home).list_jobs(now=NOW)] == ["upload-failed-old"]
