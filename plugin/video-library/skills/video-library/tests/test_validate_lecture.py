from video_library.validate import validate_lecture


def has(errors, text):
    return any(text in e for e in errors)


def test_sample_passes(sample):
    assert validate_lecture(sample) == []


def test_missing_top_level_key(sample):
    del sample["faq"]
    assert "$: 필수 항목 'faq' 없음" in validate_lecture(sample)


def test_field_must_be_known(sample):
    sample["lecture"]["field"] = "cooking"
    assert has(validate_lecture(sample), "$.lecture.field: 허용 값")


def test_video_id_pattern(sample):
    sample["lecture"]["video_id"] = "short"
    assert has(validate_lecture(sample), "$.lecture.video_id: 형식")


def test_id_must_equal_video_id(sample):
    sample["lecture"]["id"] = "ZZZZZZZZZZZ"
    assert "$.lecture.id: video_id 와 같아야 함" in validate_lecture(sample)


def test_source_url_must_match_video_id(sample):
    sample["lecture"]["source_url"] = "https://www.youtube.com/watch?v=ZZZZZZZZZZZ"
    assert "$.lecture.source_url: video_id 와 다름" in validate_lecture(sample)


def test_processed_at_needs_timezone(sample):
    sample["lecture"]["processed_at"] = "2026-10-05T14:03:00"
    assert "$.lecture.processed_at: 시간대(+09:00 등)가 있어야 함" in validate_lecture(sample)


def test_processed_at_must_be_iso(sample):
    sample["lecture"]["processed_at"] = "어제"
    assert "$.lecture.processed_at: ISO 8601 날짜·시간이어야 함" in validate_lecture(sample)


def test_segment_idx_must_be_continuous(sample):
    sample["segments"][2]["idx"] = 4
    assert "$.segments[2].idx: 3 이어야 함" in validate_lecture(sample)


def test_segment_start_after_end(sample):
    sample["segments"][0]["start"] = 50.0
    errs = validate_lecture(sample)
    assert "$.segments[0]: 시작이 끝보다 늦음" in errs
    assert "$.segments[1].start: 앞 문장보다 이름" in errs


def test_segment_end_beyond_duration(sample):
    sample["segments"][-1]["end"] = 500.0
    assert "$.segments[11].end: 영상 길이(480초)를 넘음" in validate_lecture(sample)


def test_segment_end_within_slack_is_ok(sample):
    sample["segments"][-1]["end"] = 481.5
    sample["chapters"][1]["end"] = 481.5
    sample["chapters"][1]["children"][1]["end"] = 481.5
    assert validate_lecture(sample) == []


def test_empty_segments_reports_without_crash(sample):
    sample["segments"] = []
    assert "$.segments: 문장이 하나도 없음" in validate_lecture(sample)


def test_bool_idx_rejected(sample):
    sample["segments"][0]["idx"] = True
    assert "$.segments[0].idx: integer 이어야 함" in validate_lecture(sample)
