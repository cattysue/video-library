from video_library.validate import check_context, check_outline

CONTEXT = {
    "field": "dev",
    "one_liner": "깃의 기본 개념을 훑는 입문 강의",
    "topic_summary": "깃의 저장소, 커밋, 브랜치, 병합과 GitHub를 소개한다.",
    "key_terms": [{"term": "GitHub", "heard_as": ["기 허브", "기트허브"], "note": "서비스 이름"}],
    "proper_nouns": ["GitHub"],
}


def strip_times(chapters):
    out = []
    for ch in chapters:
        ch = {k: v for k, v in ch.items() if k not in ("start", "end")}
        ch["children"] = strip_times(ch["children"])
        out.append(ch)
    return out


def has(errors, text):
    return any(text in e for e in errors)


def test_context_passes():
    assert check_context(CONTEXT) == []


def test_context_missing_key():
    bad = dict(CONTEXT)
    del bad["key_terms"]
    assert check_context(bad) == ["$: 필수 항목 'key_terms' 없음"]


def test_context_unknown_field():
    assert has(check_context(dict(CONTEXT, field="cooking")), "$.field: 허용 값")


def test_outline_passes(sample):
    outline = {"chapters": strip_times(sample["chapters"]), "mentions": sample["mentions"]}
    assert check_outline(outline, 12, 480.0) == []


def test_outline_coverage_error_has_chapters_path(sample):
    chapters = strip_times(sample["chapters"])
    chapters[1]["segments"] = [7, 12]
    errs = check_outline({"chapters": chapters, "mentions": []}, 12, 480.0)
    assert has(errs, "$.chapters[1].segments: 빈틈 또는 겹침")


def test_outline_mention_out_of_range(sample):
    outline = {"chapters": strip_times(sample["chapters"]),
               "mentions": [{"kind": "other", "text": "책", "idx": 30}]}
    assert "$.mentions[0].idx: 없는 문장 번호(30)" in check_outline(outline, 12, 480.0)


def test_outline_wrong_shape():
    assert check_outline([], 12, 480.0) == ["$: object 이어야 함"]
