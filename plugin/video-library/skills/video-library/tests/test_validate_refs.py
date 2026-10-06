from video_library.validate import check_faq, check_translation_chunk, validate_lecture


def has(errors, text):
    return any(text in e for e in errors)


def test_translation_count_mismatch(sample):
    sample["translations"]["en"].pop()
    assert has(validate_lecture(sample), "$.translations.en: 번역 문장 번호가 원문과 1:1이 아님")


def test_translation_blank_text(sample):
    sample["translations"]["en"][3]["text"] = "   "
    assert "$.translations.en[3].text: 빈 번역" in validate_lecture(sample)


def test_translation_key_must_be_language_code(sample):
    sample["translations"]["english"] = sample["translations"].pop("en")
    assert "$.translations.english: 언어 코드(두 글자 소문자)여야 함" in validate_lecture(sample)


def test_original_language_not_allowed_in_translations(sample):
    sample["translations"]["ko"] = [{"idx": s["idx"], "text": s["text"]} for s in sample["segments"]]
    assert "$.translations.ko: 원문 언어는 번역에 넣지 않음" in validate_lecture(sample)


def test_foreign_video_needs_korean_translation(sample):
    sample["lecture"]["language"] = "en"
    sample["translations"] = {}
    assert has(validate_lecture(sample), "$.translations: 외국어 영상은 한국어 번역(ko)이 필요함")


def test_foreign_video_translation_skipped_is_ok(sample):
    sample["lecture"]["language"] = "en"
    sample["translations"] = {}
    sample["lecture"]["pipeline"]["skipped"] = ["translate"]
    assert validate_lecture(sample) == []


def test_glossary_idx_out_of_range(sample):
    sample["glossary"][0]["idx"] = 99
    assert "$.glossary[0].idx: 없는 문장 번호(99)" in validate_lecture(sample)


def test_faq_evidence_out_of_range(sample):
    sample["faq"][2]["evidence"] = [5, 13]
    assert "$.faq[2].evidence[1]: 없는 문장 번호(13)" in validate_lecture(sample)


def test_mention_idx_out_of_range(sample):
    sample["mentions"][1]["idx"] = 0
    assert has(validate_lecture(sample), "$.mentions[1].idx")


def test_correction_idx_out_of_range(sample):
    sample["corrections"][0]["idx"] = 40
    assert "$.corrections[0].idx: 없는 문장 번호(40)" in validate_lecture(sample)


def test_faq_count(sample):
    sample["faq"] = sample["faq"][:4]
    assert "$.faq: FAQ는 5~10개여야 함(현재 4개)" in validate_lecture(sample)


def test_faq_skipped_must_be_empty(sample):
    sample["lecture"]["pipeline"]["skipped"] = ["faq"]
    assert "$.faq: 건너뛴 단계(faq)인데 내용이 있음" in validate_lecture(sample)


def test_faq_skipped_and_empty_is_ok(sample):
    sample["lecture"]["pipeline"]["skipped"] = ["faq"]
    sample["faq"] = []
    assert validate_lecture(sample) == []


def test_glossary_empty_without_skip(sample):
    sample["glossary"] = []
    assert "$.glossary: 비어 있음(실패했다면 pipeline.skipped 에 glossary 를 적음)" in validate_lecture(sample)


def test_translation_chunk_partial_range():
    items = [{"idx": 5, "text": "a"}, {"idx": 6, "text": "b"}, {"idx": 7, "text": "c"}]
    assert check_translation_chunk([5, 6, 7], items) == []
    assert has(check_translation_chunk([5, 6, 7], items[::-1]), "1:1이 아님")


def test_check_faq_without_count_requirement():
    items = [{"question": "q", "answer": "a", "evidence": [1]}]
    assert check_faq(items, 3, require_count=False) == []
