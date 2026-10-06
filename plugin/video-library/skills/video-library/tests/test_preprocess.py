import shutil
from pathlib import Path

import pytest

from video_library import preprocess as pp
from video_library.config import StepError, read_json, work_dir, write_json

VID = "AbCdEfGhIjK"
FIX = Path(__file__).resolve().parent / "fixtures"


def seed_raw(home, fixture, duration=60.0):
    work = work_dir(home, VID)
    (work / "raw").mkdir(parents=True)
    shutil.copy(FIX / fixture, work / "raw" / "source.json3")
    write_json(work / "raw" / "info.json", {"id": VID, "duration": duration})
    return work


def test_auto_caption_words_and_sentences():
    data = read_json(FIX / "auto_ko.json3")
    words = pp.words_from_json3(data)
    assert [w["text"] for w in words] == ["안녕하세요", "오늘은", "깃을", "배워요", "기", "허브를", "씁니다"]
    assert words[0] == {"text": "안녕하세요", "start": 0.5, "end": 1.3}
    assert words[3]["end"] == 4.0
    assert pp.build_sentences(words) == [
        {"idx": 1, "start": 0.5, "end": 4.0, "raw": "안녕하세요 오늘은 깃을 배워요"},
        {"idx": 2, "start": 9.0, "end": 11.5, "raw": "기 허브를 씁니다"},
    ]


def test_manual_caption_lines_split_on_punctuation():
    sents = pp.build_sentences(pp.words_from_json3(read_json(FIX / "manual_en.json3")))
    assert [s["raw"] for s in sents] == ["Hello everyone.", "Today we talk about quantum entanglement."]
    assert (sents[1]["start"], sents[1]["end"]) == (3.0, 7.5)


def test_hard_max_splits_continuous_speech():
    words = [{"text": f"w{i}", "start": float(i), "end": float(i + 1)} for i in range(40)]
    sents = pp.build_sentences(words)
    assert len(sents[0]["raw"].split()) == 30 and sents[1]["start"] == 30.0


def test_soft_max_splits_at_short_pause():
    words = [{"text": f"w{i}", "start": float(i), "end": i + 0.5} for i in range(25)]
    sents = pp.build_sentences(words)
    assert len(sents[0]["raw"].split()) == 21


def test_clamp_to_duration():
    sents = [{"idx": 1, "start": 9.0, "end": 11.5, "raw": "a"}, {"idx": 2, "start": 12.0, "end": 13.0, "raw": "b"}]
    assert pp.clamp_to_duration(sents, 10.0) == [
        {"idx": 1, "start": 9.0, "end": 10.0, "raw": "a"}, {"idx": 2, "start": 10.0, "end": 10.0, "raw": "b"}]


def test_preprocess_writes_files_and_clamps(home):
    work = seed_raw(home, "auto_ko.json3", duration=10.0)
    assert pp.preprocess(home, VID) == {"sentences": 2, "words": 7, "duration": 10.0}
    sents = read_json(work / "build" / "sentences.json")
    assert sents[1]["end"] == 10.0
    transcript = (work / "build" / "transcript.md").read_text(encoding="utf-8")
    assert transcript.startswith("# 전사 — 문장 2개\n")
    assert "[1] [0:00:00] 안녕하세요 오늘은 깃을 배워요" in transcript


def test_sound_tags_only_fails(home):
    work = seed_raw(home, "auto_ko.json3")
    write_json(work / "raw" / "source.json3", {"events": [{"tStartMs": 0, "dDurationMs": 1000, "segs": [{"utf8": "[음악]"}]}]})
    with pytest.raises(StepError, match="문장을 하나도"):
        pp.preprocess(home, VID)


def test_missing_source(home):
    with pytest.raises(StepError, match="fetch"):
        pp.preprocess(home, VID)


def test_main(home, capsys):
    seed_raw(home, "manual_en.json3")
    assert pp.main(["--video", VID]) == 0
    assert '"sentences": 2' in capsys.readouterr().out
