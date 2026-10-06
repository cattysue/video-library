"""2단계 최종 검토에서 나온 문제의 재현 테스트."""
import os
from datetime import datetime

import pytest

from conftest import VIDEO_ID, sample_doc, seed_work
from test_fetch import CAPTION, URL, FakeYDL, info
from test_library import make_doc, stage
from video_library import assemble as asm
from video_library import chunk as ck
from video_library import fetch as fetch_mod
from video_library import gates, jobs, library
from video_library.config import KST, StepError, lecture_dir, read_json, work_dir, write_json
from video_library.validate import check_edits, term_pairs

PAIRS = {("브라저", "브라우저"), ("바이코딩", "바이브코딩"), ("어트리뷰b트", "어트리뷰트")}
CONTEXT = {"field": "dev", "one_liner": "한 줄", "topic_summary": "요약", "proper_nouns": [],
           "key_terms": [{"term": "브라우저", "heard_as": ["브라저"]},
                         {"term": "바이브코딩", "heard_as": ["바이오코딩", "바이코딩"]},
                         {"term": "어트리뷰트", "heard_as": ["어트리뷰b트"]},
                         {"term": "안 됩니다", "heard_as": ["됩니다"]},
                         {"term": "안됩니다", "heard_as": ["됩니다"]},
                         {"term": "100만", "heard_as": ["10만"]}]}


def edit(orig, text, frm, to, kind="term"):
    return check_edits({1: orig}, [{"idx": 1, "text": text, "changes": [{"from": frm, "to": to, "kind": kind}]}],
                       1, 1, allowed_pairs=term_pairs(CONTEXT))


# 1. 맥락표에 있는 자동자막 음절 누락·추가 교정은 통과, 뜻을 바꾸는 끼워 넣기는 계속 막는다
def test_term_pairs_keep_only_safe_pairs():
    # 바이오코딩→바이브코딩 은 글자를 바꾸는 교정이라 원래 허용되므로 예외 쌍에 넣지 않는다
    assert term_pairs(CONTEXT) == PAIRS


@pytest.mark.parametrize("orig, text, frm, to", [
    ("요즘 브라저 이렇게 생겼잖아요", "요즘 브라우저 이렇게 생겼잖아요.", "브라저", "브라우저"),
    ("바이코딩 잘하기 위함이잖아요", "바이브코딩 잘하기 위함이잖아요.", "바이코딩", "바이브코딩"),
    ("이걸 어트리뷰b트라고 하거든요", "이걸 어트리뷰트라고 하거든요.", "어트리뷰b트", "어트리뷰트"),
    ("요즘 브라저 이렇게", "요즘 브라우저 이렇게", "요즘 브라저", "요즘 브라우저"),
])
def test_context_backed_asr_fixes_pass(orig, text, frm, to):
    assert edit(orig, text, frm, to) == []


@pytest.mark.parametrize("orig, text, frm, to", [
    ("쓰면 됩니다", "쓰면 안 됩니다", "됩니다", "안 됩니다"),
    ("쓰면 됩니다", "쓰면 안됩니다", "됩니다", "안됩니다"),
    ("가격은 10만 원", "가격은 100만 원", "10만", "100만"),
    ("요즘 브라저 이렇게", "요즘 브라우우저 이렇게", "브라저", "브라우우저"),
])
def test_meaning_changing_insertions_still_blocked(orig, text, frm, to):
    assert any("덧붙이기만" in e for e in edit(orig, text, frm, to))


def test_spelling_kind_gets_no_exception():
    assert any("덧붙이기만" in e for e in edit("바이코딩 잘하기", "바이브코딩 잘하기", "바이코딩", "바이브코딩", "spelling"))


def test_gates_uses_context_pairs(home):
    work = seed_work(home)
    ck.chunk(home, VIDEO_ID)
    sents = read_json(work / "build" / "sentences.json")
    sents[0]["raw"] = "요즘 브라저 이렇게 생겼잖아요"
    write_json(work / "build" / "sentences.json", sents)
    write_json(work / "build" / "chunks" / "01.edits.json", [{"idx": 1, "text": "요즘 브라우저 이렇게 생겼잖아요.",
                                                              "changes": [{"from": "브라저", "to": "브라우저", "kind": "term"}]}])
    assert any("덧붙이기만" in e for e in gates.check_chunk_edits(work, 1))  # 맥락표가 없으면 예전처럼 엄격
    write_json(work / "build" / "context.json", CONTEXT)
    assert gates.check_chunk_edits(work, 1) == []


# 2. 잠긴 폴더(Windows)에서도 파이썬 오류 화면 대신 안내, .old 는 다음 반영 때 복원
def test_locked_final_folder_reports_step_error(home, monkeypatch):
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)
    stage(home, make_doc(title="새 제목"))
    real = library.os.replace

    def locked(src, dst):
        if str(src).endswith(VIDEO_ID):
            raise PermissionError("[WinError 5] 액세스가 거부되었습니다")
        return real(src, dst)

    monkeypatch.setattr(library.os, "replace", locked)
    with pytest.raises(StepError, match="폴더가 열려 있으면"):
        library.commit_lecture(home, VIDEO_ID)
    assert read_json(lecture_dir(home, VIDEO_ID) / "lecture.json")["lecture"]["title"] == "깃 기초 맛보기 (샘플)"


def test_leftover_old_folder_is_restored(home):
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)
    os.replace(lecture_dir(home, VIDEO_ID), lecture_dir(home, VIDEO_ID).with_name(f"{VIDEO_ID}.old"))
    bad = make_doc()
    del bad["faq"]
    stage(home, bad)
    with pytest.raises(StepError):
        library.commit_lecture(home, VIDEO_ID)
    assert (lecture_dir(home, VIDEO_ID) / "lecture.json").exists()


# 3. 작업 기록이 'running' 으로 영영 남지 않게
def test_refetch_closes_previous_job(home):
    first = fetch_mod.fetch(URL, home, ydl_factory=lambda o: FakeYDL(o, info(), CAPTION),
                            now=datetime(2026, 10, 5, 10, 0, tzinfo=KST))
    jobs.set_step(home, first["job_id"], "correct", "running")
    fetch_mod.fetch(URL, home, ydl_factory=lambda o: FakeYDL(o, info(), CAPTION),
                    now=datetime(2026, 10, 5, 11, 0, tzinfo=KST))
    old = jobs.load_job(home, first["job_id"])
    assert old["status"] == "failed" and "새 작업" in old["error"]


def test_subtitle_failure_recorded_in_job(home):
    with pytest.raises(StepError):
        fetch_mod.fetch(URL, home, ydl_factory=lambda o: FakeYDL(o, info(), CAPTION, write=False),
                        now=datetime(2026, 10, 5, 12, 0, tzinfo=KST))
    job = jobs.load_job(home, f"{VIDEO_ID}-1005-1200")
    assert job["status"] == "failed" and job["steps"]["fetch"] == "failed"


# 4. 진행 기록이 망가져도 실제 작업은 계속된다
def test_missing_job_file_does_not_block_assemble(home, capsys):
    from test_assemble import seed_outputs
    seed_outputs(home)
    job_id = read_json(work_dir(home, VIDEO_ID) / "build" / "request.json")["job_id"]
    os.remove(home / "jobs" / f"{job_id}.json")
    assert asm.main(["--video", VIDEO_ID]) == 0
    assert (lecture_dir(home, VIDEO_ID) / "lecture.json").exists()
    assert "진행 기록" in capsys.readouterr().err


def test_corrupt_job_file_does_not_crash_track(home):
    seed_work(home)
    job_id = read_json(work_dir(home, VIDEO_ID) / "build" / "request.json")["job_id"]
    (home / "jobs" / f"{job_id}.json").write_text("{깨짐", encoding="utf-8")
    assert ck.main(["--video", VIDEO_ID]) == 0


def test_progress_command_reports_corrupt_job(home):
    seed_work(home)
    job_id = read_json(work_dir(home, VIDEO_ID) / "build" / "request.json")["job_id"]
    (home / "jobs" / f"{job_id}.json").write_text("{깨짐", encoding="utf-8")
    with pytest.raises(StepError, match="진행 기록"):
        jobs.main(["--video", VIDEO_ID, "--step", "correct"])


# 6. --video 는 11자 영상 ID만 받는다(영상자료실 밖 경로 차단)
@pytest.mark.parametrize("module", [asm, ck, gates, library, jobs])
def test_video_argument_rejects_paths(module):
    argv = ["--video", "../../x"] + (["--kind", "context"] if module is gates else []) \
        + (["--step", "correct"] if module is jobs else [])
    with pytest.raises(SystemExit):
        module.main(argv)
