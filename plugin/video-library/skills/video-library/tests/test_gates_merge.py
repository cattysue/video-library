import pytest

from conftest import VIDEO_ID, sample_doc, seed_work
from video_library import chunk as ck
from video_library import gates, merge
from video_library.config import StepError, read_json, write_json
from video_library.jobs import current_job_id, load_job


def prepared(home):
    work = seed_work(home)
    ck.chunk(home, VIDEO_ID, chunk_sec=200)  # 조각 (1~6), (7~12)
    return work


def write_edits(work, doc, n, lo, hi):
    changes = {}
    for c in doc["corrections"]:
        changes.setdefault(c["idx"], []).append({"from": c["from"], "to": c["to"], "kind": c["kind"]})
    edits = [{"idx": s["idx"], "text": s["text"], "changes": changes.get(s["idx"], [])}
             for s in doc["segments"] if lo <= s["idx"] <= hi and s["text"] != s["raw"]]
    write_json(work / "build" / "chunks" / f"{n:02d}.edits.json", edits)


def write_translation(work, doc, n, lo, hi, lang="en"):
    items = [it for it in doc["translations"]["en"] if lo <= it["idx"] <= hi]
    write_json(work / "build" / "chunks" / f"{n:02d}.{lang}.json", items)


def test_check_chunk_edits_pass(home):
    work = prepared(home)
    write_edits(work, sample_doc(), 2, 7, 12)
    assert gates.check_chunk_edits(work, 2) == []


def test_check_chunk_edits_missing_file(home):
    work = prepared(home)
    assert gates.check_chunk_edits(work, 1) == ["01.edits.json: 파일이 없습니다"]


def test_check_chunk_edits_out_of_range(home):
    work = prepared(home)
    write_json(work / "build" / "chunks" / "01.edits.json", [{"idx": 9, "text": "x", "changes": []}])
    assert any("담당 범위 1~6 밖" in e for e in gates.check_chunk_edits(work, 1))


def test_cp949_or_broken_json_reports_not_crashes(home):
    work = prepared(home)
    (work / "build" / "chunks" / "01.edits.json").write_bytes('[{"idx": 1, "text": "한글"}]'.encode("cp949"))
    assert gates.check_chunk_edits(work, 1)[0].startswith("01.edits.json: JSON 형식 오류")
    (work / "build" / "chunks" / "02.edits.json").write_text("[{깨짐", encoding="utf-8")
    assert gates.check_chunk_edits(work, 2)[0].startswith("02.edits.json: JSON 형식 오류")


def test_unknown_chunk(home):
    work = prepared(home)
    with pytest.raises(StepError, match="조각 7번"):
        gates.check_chunk_edits(work, 7)


def test_merge_edits_reproduces_sample(home):
    work = prepared(home)
    doc = sample_doc()
    write_edits(work, doc, 1, 1, 6)
    write_edits(work, doc, 2, 7, 12)
    assert merge.merge_edits(work) == {"chunks": 2, "edited": 12, "corrections": 2}
    corrected = read_json(work / "build" / "sentences.corrected.json")
    assert [s["text"] for s in corrected] == [s["text"] for s in doc["segments"]]
    assert read_json(work / "build" / "corrections.json") == doc["corrections"]


def test_merge_edits_unedited_sentence_keeps_raw(home):
    work = prepared(home)
    write_json(work / "build" / "chunks" / "01.edits.json", [])
    write_json(work / "build" / "chunks" / "02.edits.json", [])
    merge.merge_edits(work)
    corrected = read_json(work / "build" / "sentences.corrected.json")
    assert corrected[0]["text"] == corrected[0]["raw"]


def test_merge_edits_reports_bad_chunks(home):
    work = prepared(home)
    write_edits(work, sample_doc(), 1, 1, 6)
    with pytest.raises(StepError, match="조각 02: 02.edits.json: 파일이 없습니다"):
        merge.merge_edits(work)


def test_translation_check_and_merge(home):
    work = prepared(home)
    doc = sample_doc()
    write_translation(work, doc, 1, 1, 6)
    write_translation(work, doc, 2, 7, 12)
    assert gates.check_chunk_translation(work, 1, "en") == []
    assert merge.merge_translation(work, "en") == {"lang": "en", "sentences": 12}
    assert read_json(work / "build" / "translations.en.json") == doc["translations"]["en"]


def test_translation_bad_lang(home):
    work = prepared(home)
    with pytest.raises(StepError, match="언어 코드"):
        gates.check_chunk_translation(work, 1, "english")


def test_check_outputs(home):
    work = prepared(home)
    doc = sample_doc()
    build = work / "build"
    write_json(build / "context.json", {"field": "dev", "one_liner": doc["lecture"]["one_liner"],
                                        "topic_summary": "요약", "key_terms": [], "proper_nouns": []})
    strip = lambda chs: [{**{k: v for k, v in c.items() if k not in ("start", "end")}, "children": strip(c["children"])} for c in chs]
    write_json(build / "outline.json", {"chapters": strip(doc["chapters"]), "mentions": doc["mentions"]})
    write_json(build / "glossary.json", [])
    write_json(build / "faq.json", doc["faq"])
    assert gates.check_output(work, "context") == []
    assert gates.check_output(work, "outline") == []
    assert gates.check_output(work, "glossary") == ["$: 용어가 하나도 없음"]
    assert gates.check_output(work, "faq") == []


def test_check_command_exit_codes(home, capsys):
    work = prepared(home)
    assert gates.main(["--video", VIDEO_ID, "--kind", "edits", "--chunk", "1"]) == 1
    assert "불합격 (1건)" in capsys.readouterr().out
    write_edits(work, sample_doc(), 1, 1, 6)
    assert gates.main(["--video", VIDEO_ID, "--kind", "edits", "--chunk", "1"]) == 0
    assert "통과" in capsys.readouterr().out


def test_check_command_requires_chunk(home):
    prepared(home)
    with pytest.raises(StepError, match="--chunk"):
        gates.main(["--video", VIDEO_ID, "--kind", "edits"])


def test_merge_command_marks_job(home):
    work = prepared(home)
    doc = sample_doc()
    write_edits(work, doc, 1, 1, 6)
    write_edits(work, doc, 2, 7, 12)
    assert merge.main(["--video", VIDEO_ID, "--kind", "edits"]) == 0
    assert load_job(home, current_job_id(home, VIDEO_ID))["steps"]["merge"] == "done"
