import pytest

from conftest import VIDEO_ID
from test_library import make_doc
from video_library import jobs
from video_library.config import lecture_dir, read_json, write_json
from video_library.search import SearchIndex
from video_library.store_hosted import HostedStore, UploadError, check_job


def test_search_respects_allowed_ids():
    index = SearchIndex([make_doc()])
    assert index.search("기초")["results"]
    assert index.search("기초", allowed=set())["results"] == []
    assert index.search("기초", allowed={VIDEO_ID})["results"][0]["id"] == VIDEO_ID


def test_upload_new_lecture_is_private(home):
    store = HostedStore(home)
    assert store.put_lecture(VIDEO_ID, make_doc()) is False
    assert (lecture_dir(home, VIDEO_ID) / "lecture.json").exists()
    assert [e["id"] for e in store.list_lectures()] == [VIDEO_ID]
    assert store.public_ids() == set()


def test_upload_rejects_bad_documents(home):
    store = HostedStore(home)
    broken = make_doc()
    del broken["segments"]
    with pytest.raises(UploadError) as err:
        store.put_lecture(VIDEO_ID, broken)
    assert err.value.errors
    with pytest.raises(UploadError):
        store.put_lecture("ZZZZZZZZZZZ", make_doc())  # 주소의 ID 와 문서 ID 가 다름
    with pytest.raises(UploadError):
        store.put_lecture("../escape", make_doc())
    assert store.list_lectures() == []


def test_publish_survives_reupload_and_delete_clears_it(home):
    store = HostedStore(home)
    assert store.set_public(VIDEO_ID, True) is False  # 아직 없는 강의
    store.put_lecture(VIDEO_ID, make_doc())
    assert store.set_public(VIDEO_ID, True) is True
    assert store.put_lecture(VIDEO_ID, make_doc(title="고친 제목")) is True
    assert store.public_ids() == {VIDEO_ID}
    assert store.set_public(VIDEO_ID, False) is True and store.public_ids() == set()
    store.set_public(VIDEO_ID, True)
    assert store.delete_lecture(VIDEO_ID) is True
    assert store.get_lecture(VIDEO_ID) is None and store.list_lectures() == []
    assert store.public_ids() == set()
    assert store.delete_lecture(VIDEO_ID) is False


@pytest.mark.parametrize("content", ["{망가진", '{"public": "AbCdEfGhIjK"}', '[1, 2]', '{"public": ["../x", 3]}'])
def test_broken_visibility_means_nothing_public(home, content):
    store = HostedStore(home)
    store.put_lecture(VIDEO_ID, make_doc())
    (home / "visibility.json").write_text(content, encoding="utf-8")
    assert store.public_ids() == set()


def make_job(tmp_path):
    # PC 쪽 영상자료실(다른 폴더)에서 만든 진짜 진행 기록 — 서버 폴더에는 미리 쓰지 않는다
    return jobs.start_job(tmp_path / "pc", VIDEO_ID, "깃 기초", jobs.initial_steps(False, True))


def test_put_job_accepts_real_job(home, tmp_path):
    store = HostedStore(home)
    job = make_job(tmp_path)
    assert not (home / "jobs" / f"{job['job_id']}.json").exists()
    store.put_job(job["job_id"], job)
    assert read_json(home / "jobs" / f"{job['job_id']}.json") == job
    assert check_job(job["job_id"], job) == []


@pytest.mark.parametrize("change", [
    lambda j: j.update(job_id="other"),
    lambda j: j.update(updated_at="2026-10-06T10:00:00"),  # 시간대 없음
    lambda j: j["steps"].update(hack="done"),
    lambda j: j["steps"].update(fetch="exploded"),
    lambda j: j.update(status="paused"),
    lambda j: j.update(extra="x"),
    lambda j: j.update(title="가" * 301),
])
def test_put_job_rejects_bad_jobs(home, tmp_path, change):
    job = make_job(tmp_path)
    job_id = job["job_id"]
    change(job)
    with pytest.raises(UploadError):
        HostedStore(home).put_job(job_id, job)


def test_put_job_rejects_bad_id(home, tmp_path):
    job = make_job(tmp_path)
    with pytest.raises(UploadError):
        HostedStore(home).put_job("../../index", job)
