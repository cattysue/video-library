import json

from conftest import VIDEO_ID, sample_doc
from test_library import make_doc, stage
from video_library import library, search
from video_library.search import SearchIndex, normalize_query


def other_doc():
    doc = make_doc("ZzZzZzZzZzZ", "2026-10-06T09:00:00+09:00", title="양자 얽힘 입문")
    doc["lecture"]["field"] = "science"
    return doc


def test_normalize_query():
    assert normalize_query("  Git Hub  ") == "github"


def test_hits_in_every_place():
    result = SearchIndex([sample_doc()]).search("브랜치")
    hits = result["results"][0]["hits"]
    wheres = {h["where"] for h in hits}
    assert {"chapter", "glossary", "segment"} <= wheres
    seg = [h for h in hits if h["where"] == "segment"][0]
    assert seg == {"where": "segment", "idx": 6, "start": 190.0, "text": "다음으로 브랜치를 알아보겠습니다.", "lang": "ko"}


def test_title_and_translation_hits():
    result = SearchIndex([sample_doc()]).search("branches")  # 용어집의 "브랜치(Branch)"와 겹치지 않는 말
    hits = result["results"][0]["hits"]
    assert hits and all(h["where"] == "translation" and h["lang"] == "en" for h in hits)
    title = SearchIndex([sample_doc()]).search("맛보기")["results"][0]["hits"][0]
    assert title == {"where": "title", "idx": None, "start": 0.0, "text": "깃 기초 맛보기 (샘플)"}


def test_space_and_case_insensitive():
    assert SearchIndex([sample_doc()]).search("GIT STATUS")["results"]


def test_field_and_video_filters():
    index = SearchIndex([other_doc(), sample_doc()])
    assert [r["id"] for r in index.search("브랜치")["results"]] == ["ZzZzZzZzZzZ", VIDEO_ID]
    assert [r["id"] for r in index.search("브랜치", field="dev")["results"]] == [VIDEO_ID]
    assert [r["id"] for r in index.search("브랜치", video="ZzZzZzZzZzZ")["results"]] == ["ZzZzZzZzZzZ"]


def test_limit_and_empty_query():
    index = SearchIndex([sample_doc()])
    assert len(index.search("니다", limit=3)["results"][0]["hits"]) == 3
    assert index.search("   ")["results"] == []
    assert index.search("없는말쓰")["results"] == []


def test_search_command_prints_links(home, capsys):
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)
    assert search.main(["브랜치"]) == 0
    out = capsys.readouterr().out
    assert "깃 기초 맛보기 (샘플)" in out
    assert f"http://127.0.0.1:8765/lecture?id={VIDEO_ID}&t=190" in out


def test_search_command_json_and_no_results(home, capsys):
    assert search.main(["브랜치", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"query": "브랜치", "results": []}
    assert search.main(["브랜치"]) == 0
    assert "검색 결과가 없습니다" in capsys.readouterr().out
