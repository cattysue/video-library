import json

import pytest

from conftest import VIDEO_ID, sample_doc
from video_library import library
from video_library.config import StepError, lecture_dir, read_json, work_dir, write_json
from video_library.jobs import load_job


def make_doc(vid=VIDEO_ID, processed_at="2026-10-05T14:03:00+09:00", title=None):
    doc = sample_doc()
    lec = doc["lecture"]
    lec.update(id=vid, video_id=vid, source_url=f"https://www.youtube.com/watch?v={vid}",
               thumbnail_url=f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg", processed_at=processed_at)
    if title:
        lec["title"] = title
    return doc


def stage(home, doc):
    vid = doc["lecture"]["id"]
    write_json(work_dir(home, vid) / "lecture.json", doc)
    write_json(work_dir(home, vid) / "build" / "request.json", {"video_id": vid, "job_id": "x"})
    return vid


def test_index_entry():
    assert library.index_entry(sample_doc()) == {
        "id": VIDEO_ID, "title": "깃 기초 맛보기 (샘플)", "channel": "샘플 채널", "duration": 480.0,
        "thumbnail_url": f"https://i.ytimg.com/vi/{VIDEO_ID}/hqdefault.jpg", "field": "dev", "language": "ko",
        "translations": ["en"], "chapter_count": 2, "processed_at": "2026-10-05T14:03:00+09:00"}


def test_commit_moves_folder_and_updates_index(home):
    stage(home, make_doc())
    final = library.commit_lecture(home, VIDEO_ID)
    assert final == lecture_dir(home, VIDEO_ID) and (final / "lecture.json").exists()
    assert not work_dir(home, VIDEO_ID).exists()
    assert [e["id"] for e in read_json(home / "index.json")] == [VIDEO_ID]


def test_recommit_replaces_and_orders_newest_first(home):
    other = "ZzZzZzZzZzZ"
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)
    stage(home, make_doc(other, "2026-10-06T09:00:00+09:00"))
    library.commit_lecture(home, other)
    stage(home, make_doc(VIDEO_ID, "2026-10-07T09:00:00+09:00", title="새 제목"))
    library.commit_lecture(home, VIDEO_ID)
    index = read_json(home / "index.json")
    assert [e["id"] for e in index] == [VIDEO_ID, other]
    assert index[0]["title"] == "새 제목"
    assert read_json(lecture_dir(home, VIDEO_ID) / "lecture.json")["lecture"]["title"] == "새 제목"
    assert not (home / "lectures" / f"{VIDEO_ID}.old").exists()


def test_failed_commit_keeps_existing_lecture(home):
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)
    bad = make_doc(title="망가진 재처리")
    del bad["faq"]
    stage(home, bad)
    with pytest.raises(StepError, match="검사 불합격"):
        library.commit_lecture(home, VIDEO_ID)
    assert read_json(lecture_dir(home, VIDEO_ID) / "lecture.json")["lecture"]["title"] == "깃 기초 맛보기 (샘플)"
    assert work_dir(home, VIDEO_ID).exists()


def test_broken_index_is_rebuilt(home):
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)
    (home / "index.json").write_text("{깨짐", encoding="utf-8")
    other = "ZzZzZzZzZzZ"
    stage(home, make_doc(other, "2026-10-06T09:00:00+09:00"))
    library.commit_lecture(home, other)
    assert [e["id"] for e in read_json(home / "index.json")] == [other, VIDEO_ID]


def test_reopen_for_english_translation(home):
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)
    out = library.reopen(home, VIDEO_ID, translate_en=True)
    work = work_dir(home, VIDEO_ID)
    assert out["work_dir"] == str(work) and (work / "lecture.json").exists()
    request = read_json(work / "build" / "request.json")
    assert request["translate_en"] is True and request["job_id"] == out["job_id"]
    steps = load_job(home, out["job_id"])["steps"]
    assert steps["translate"] == "pending" and steps["assemble"] == "pending" and steps["fetch"] == "skipped"


def test_reopen_refuses_existing_work_folder(home):
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)
    work_dir(home, VIDEO_ID).mkdir()
    with pytest.raises(StepError, match="작업 폴더가 이미 있습니다"):
        library.reopen(home, VIDEO_ID, translate_en=True)


def test_reopen_missing_lecture(home):
    with pytest.raises(StepError, match="영상자료실에 이 강의가 없습니다"):
        library.reopen(home, VIDEO_ID, translate_en=True)


def test_reopen_translate_en_only_for_korean(home):
    doc = make_doc()
    doc["lecture"]["language"] = "en"
    doc["translations"] = {"ko": [{"idx": s["idx"], "text": s["text"]} for s in doc["segments"]]}
    stage(home, doc)
    library.commit_lecture(home, VIDEO_ID)
    with pytest.raises(StepError, match="한국어 강의"):
        library.reopen(home, VIDEO_ID, translate_en=True)


def test_reopen_command(home, capsys):
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)
    assert library.main(["--video", VIDEO_ID, "--translate-en"]) == 0
    assert json.loads(capsys.readouterr().out)["video_id"] == VIDEO_ID


def test_reopen_uploads_again_when_railway_is_set(home):
    # 나중에 영어 번역을 더하면 Railway 사본도 다시 올린다(검토 I3)
    from video_library import remote
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)
    out = library.reopen(home, VIDEO_ID, translate_en=True)
    assert load_job(home, out["job_id"])["steps"]["upload"] == "skipped"  # 설정 없음
    work_dir(home, VIDEO_ID).rename(home / "lectures" / "old-work")
    remote.save_config(home, "https://video-library.up.railway.app", "tok")
    out = library.reopen(home, VIDEO_ID, translate_en=True)
    assert load_job(home, out["job_id"])["steps"]["upload"] == "pending"
