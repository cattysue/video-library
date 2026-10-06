import pytest

from conftest import VIDEO_ID, seed_work
from video_library import chunk as ck
from video_library.config import StepError, read_json, work_dir, write_json
from video_library.jobs import current_job_id, load_job


def make_sents(n, step=60.0):
    return [{"idx": i, "start": (i - 1) * step, "end": i * step - 1, "raw": f"문장 {i}"} for i in range(1, n + 1)]


def test_plan_chunks_regular():
    assert ck.plan_chunks(make_sents(25)) == [(1, 10), (11, 20), (21, 25)]


def test_plan_chunks_merges_short_tail():
    assert ck.plan_chunks(make_sents(22)) == [(1, 10), (11, 22)]


def test_plan_chunks_short_video():
    assert ck.plan_chunks(make_sents(5)) == [(1, 5)]


def test_render_chunk_context_and_range():
    text = ck.render_chunk(make_sents(25), 11, 20, 2, 3)
    assert text.startswith("# 조각 02/03 — 문장 11~20\n")
    assert "## EDITABLE RANGE (11~20)" in text
    assert "[8] [0:07:00] 문장 8" in text and "[10] [0:09:00] 문장 10" in text
    assert "[7] " not in text
    assert "[21] [0:20:00] 문장 21" in text and "[23] " in text and "[24] " not in text


def test_render_first_chunk_has_no_before_context():
    text = ck.render_chunk(make_sents(25), 1, 10, 1, 3)
    before = text.split("## EDITABLE RANGE")[0]
    assert "(없음)" in before


def test_chunk_writes_files_and_marks_job(home):
    work = seed_work(home)
    write_json(work / "build" / "chunks" / "09.edits.json", [])
    assert ck.chunk(home, VIDEO_ID, chunk_sec=200) == {"chunks": 2, "sentences": 12}
    manifest = read_json(work / "build" / "chunks" / "manifest.json")
    assert [(c["lo"], c["hi"]) for c in manifest["chunks"]] == [(1, 6), (7, 12)]
    assert manifest["chunks"][1] == {"n": 2, "file": "02.md", "lo": 7, "hi": 12, "start": 230.0, "end": 478.0}
    assert (work / "build" / "chunks" / "01.md").exists()
    assert not (work / "build" / "chunks" / "09.edits.json").exists()


def test_chunk_main_tracks_step(home):
    seed_work(home)
    assert ck.main(["--video", VIDEO_ID]) == 0
    job = load_job(home, current_job_id(home, VIDEO_ID))
    assert job["steps"]["chunk"] == "done"


def test_chunk_without_sentences(home):
    with pytest.raises(StepError, match="preprocess"):
        ck.chunk(home, VIDEO_ID)
