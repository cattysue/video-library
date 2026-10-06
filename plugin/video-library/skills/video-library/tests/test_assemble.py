import json
import os
from datetime import datetime

import pytest

from conftest import VIDEO_ID, sample_doc, seed_work
from video_library import assemble as asm
from video_library.config import KST, StepError, lecture_dir, read_json, work_dir, write_json
from video_library.jobs import load_job
from video_library.validate import validate_lecture

NOW = datetime(2026, 10, 5, 15, 0, tzinfo=KST)


def strip(chapters):
    return [{**{k: v for k, v in c.items() if k not in ("start", "end")}, "children": strip(c["children"])}
            for c in chapters]


def seed_outputs(home, doc=None, translate_en=True, glossary=True, faq=True, translations=True):
    doc = doc or sample_doc()
    work = seed_work(home, doc, translate_en=translate_en)
    build = work / "build"
    write_json(build / "sentences.corrected.json", doc["segments"])
    write_json(build / "corrections.json", doc["corrections"])
    write_json(build / "context.json", {"field": doc["lecture"]["field"], "one_liner": doc["lecture"]["one_liner"],
                                        "topic_summary": "요약", "key_terms": [], "proper_nouns": []})
    write_json(build / "outline.json", {"chapters": strip(doc["chapters"]), "mentions": doc["mentions"]})
    if glossary:
        write_json(build / "glossary.json", doc["glossary"])
    if faq:
        write_json(build / "faq.json", doc["faq"])
    if translations:
        for lang, items in doc["translations"].items():
            write_json(build / f"translations.{lang}.json", items)
    return work


def test_needed_translations():
    assert asm.needed_translations("en", False) == ["ko"]
    assert asm.needed_translations("ko", True) == ["en"]
    assert asm.needed_translations("ko", False) == []


def test_full_assemble_matches_sample(home):
    seed_outputs(home)
    result, outcome = asm.assemble(home, VIDEO_ID, now=NOW)
    final = lecture_dir(home, VIDEO_ID)
    assert result == {"video_id": VIDEO_ID, "lecture_dir": str(final), "skipped": [], "sentences": 12, "chapters": 2}
    doc = read_json(final / "lecture.json")
    sample = sample_doc()
    assert validate_lecture(doc) == []
    assert doc["segments"] == sample["segments"]
    assert doc["chapters"] == sample["chapters"]
    assert doc["translations"] == sample["translations"]
    assert doc["lecture"]["processed_at"] == "2026-10-05T15:00:00+09:00"
    assert doc["lecture"]["pipeline"] == {"version": "0.1.0", "caption_kind": "auto", "skipped": []}
    assert (final / "transcript.ko.txt").read_text(encoding="utf-8").splitlines()[0] == sample["segments"][0]["text"]
    assert (final / "transcript.en.timed.txt").read_text(encoding="utf-8").splitlines()[1].startswith("[0:00:35] Git is")
    assert read_json(home / "index.json")[0]["id"] == VIDEO_ID
    assert outcome["glossary"] == "done" and outcome["translate"] == "done"


def test_missing_optional_steps_recorded_as_skipped(home):
    seed_outputs(home, glossary=False, faq=False, translations=False)
    result, outcome = asm.assemble(home, VIDEO_ID, now=NOW)
    assert result["skipped"] == ["glossary", "translate", "faq"]
    doc = read_json(lecture_dir(home, VIDEO_ID) / "lecture.json")
    assert doc["glossary"] == [] and doc["faq"] == [] and doc["translations"] == {}
    assert outcome["glossary"] == "skipped" and outcome["translate"] == "skipped"


def test_missing_outline_stops(home):
    work = seed_outputs(home)
    os.remove(work / "build" / "outline.json")
    with pytest.raises(StepError, match="outline.json"):
        asm.assemble(home, VIDEO_ID, now=NOW)
    assert work_dir(home, VIDEO_ID).exists() and not lecture_dir(home, VIDEO_ID).exists()


def test_invalid_outline_stops(home):
    work = seed_outputs(home)
    outline = read_json(work / "build" / "outline.json")
    outline["chapters"][1]["segments"] = [7, 12]
    write_json(work / "build" / "outline.json", outline)
    with pytest.raises(StepError, match="빈틈 또는 겹침"):
        asm.assemble(home, VIDEO_ID, now=NOW)


def test_main_finishes_job(home, capsys):
    seed_outputs(home)
    job_id = read_json(work_dir(home, VIDEO_ID) / "build" / "request.json")["job_id"]
    assert asm.main(["--video", VIDEO_ID]) == 0
    assert json.loads(capsys.readouterr().out)["skipped"] == []
    job = load_job(home, job_id)
    assert job["status"] == "done"
    assert job["steps"]["assemble"] == "done" and job["steps"]["outline"] == "done"
    assert job["steps"]["upload"] == "skipped"
