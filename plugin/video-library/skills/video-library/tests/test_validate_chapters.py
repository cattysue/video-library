from video_library.validate import chapter_count_range, check_chapters, validate_lecture


def has(errors, text):
    return any(text in e for e in errors)


def flat(ranges, prefix=None):
    """[(a, b), ...] → 소목차 없는 목차 목록(시간 없음)."""
    out = []
    for k, (a, b) in enumerate(ranges, start=1):
        cid = str(k) if prefix is None else f"{prefix}.{k}"
        out.append({"id": cid, "title": f"장 {cid}", "summary": "요약", "segments": [a, b], "children": []})
    return out


def test_count_range_boundaries():
    assert chapter_count_range(599) == (2, 4)
    assert chapter_count_range(600) == (4, 10)
    assert chapter_count_range(3599) == (4, 10)
    assert chapter_count_range(3600) == (6, 12)


def test_sample_chapters_pass(sample):
    assert check_chapters(sample["chapters"], 12, 480.0, sample["segments"]) == []


def test_gap_detected(sample):
    sample["chapters"][1]["segments"] = [7, 12]
    assert has(validate_lecture(sample), "$.chapters[1].segments: 빈틈 또는 겹침")


def test_overlap_detected(sample):
    sample["chapters"][1]["segments"] = [5, 12]
    assert has(validate_lecture(sample), "$.chapters[1].segments: 빈틈 또는 겹침")


def test_must_reach_last_sentence():
    errs = check_chapters(flat([(1, 5), (6, 11)]), 12, 480.0)
    assert "$: 마지막 문장 12번까지 덮어야 함(현재 11번)" in errs


def test_top_level_count_follows_duration():
    errs = check_chapters(flat([(1, 2), (3, 4), (5, 6), (7, 8), (9, 12)]), 12, 480.0)
    assert "$: 영상 길이 480초에는 대목차 2~4개여야 함(현재 5개)" in errs


def test_children_must_cover_parent(sample):
    sample["chapters"][0]["children"][1]["segments"] = [4, 4]
    assert has(validate_lecture(sample), "$.chapters[0].children: 마지막 문장 5번까지 덮어야 함")


def test_single_child_rejected(sample):
    sample["chapters"][0]["children"] = sample["chapters"][0]["children"][:1]
    assert has(validate_lecture(sample), "$.chapters[0].children: 소목차는 0개 또는 2~6개여야 함")


def test_third_level_rejected(sample):
    # 3단 id("1.1.1")는 스키마 형식에서 먼저 걸리므로, 형식이 맞는 id 로 의미 검사(2단 제한)만 확인한다
    chapters = sample["chapters"]
    chapters[0]["children"][0]["children"] = flat([(1, 1), (2, 3)])
    assert has(check_chapters(chapters, 12, 480.0), "$[0].children[0]: 목차는 2단까지만 허용")


def test_long_video_needs_children():
    errs = check_chapters(flat([(1, 10), (11, 20), (21, 30), (31, 40)]), 40, 1200.0)
    assert "$[0].children: 10분 이상 영상은 대목차마다 소목차 2~6개가 필요함" in errs


def test_ids_must_be_sequential(sample):
    sample["chapters"][1]["id"] = "3"
    assert "$.chapters[1].id: '2' 이어야 함" in validate_lecture(sample)


def test_child_ids_follow_parent(sample):
    sample["chapters"][1]["children"][0]["id"] = "1.3"
    assert "$.chapters[1].children[0].id: '2.1' 이어야 함" in validate_lecture(sample)


def test_chapter_times_must_match_sentences(sample):
    sample["chapters"][0]["end"] = 189.0
    assert "$.chapters[0].end: 문장 시간 190.0과 같아야 함(현재 189.0)" in validate_lecture(sample)


def test_chapter_times_required_in_lecture(sample):
    del sample["chapters"][0]["children"][0]["start"]
    assert "$.chapters[0].children[0].start: 문장 시간 0.0과 같아야 함(현재 없음)" in validate_lecture(sample)


def test_float_rounding_tolerated(sample):
    sample["segments"][4]["end"] = 0.1 + 0.2 + 189.7  # 190.00000000000003
    sample["segments"][5]["start"] = 190.0
    assert validate_lecture(sample) == []


def test_direct_call_with_malformed_input_reports_instead_of_raising(sample):
    assert check_chapters([{"id": "1", "title": "t", "summary": "s", "segments": [1, 12], "children": 5}], 12, 480.0) \
        == ["$[0].children: array 이어야 함"]
    assert check_chapters([1, 2], 12, 480.0, sample["segments"]) == \
        ["$[0]: object 이어야 함", "$[1]: object 이어야 함"]
