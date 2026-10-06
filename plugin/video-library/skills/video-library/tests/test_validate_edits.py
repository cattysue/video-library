from video_library.validate import check_edits, normalize_for_compare

ORIG = {
    4: "작업 내용을 저장소에 기록하는 일을 커밋 이라고 합니다",
    9: "온라인 저장소 서비스로는 기 허브가 널리 쓰입니다",
    20: "그럼 안 되요",
    21: "가나다라마바사아자차",
}
TERM = [{"from": "기 허브", "to": "GitHub", "kind": "term"}]


def has(errors, text):
    return any(text in e for e in errors)


def test_normalize_removes_spaces_and_punctuation():
    assert normalize_for_compare("a b「c」·d! e.") == "abcde"


def test_spacing_and_punctuation_only_passes():
    edits = [{"idx": 4, "text": "작업 내용을 저장소에 기록하는 일을 커밋이라고 합니다.", "changes": []}]
    assert check_edits(ORIG, edits, 1, 10) == []


def test_declared_term_fix_passes():
    edits = [{"idx": 9, "text": "온라인 저장소 서비스로는 GitHub가 널리 쓰입니다.", "changes": TERM}]
    assert check_edits(ORIG, edits, 1, 10) == []


def test_declared_spelling_fix_passes():
    edits = [{"idx": 20, "text": "그럼 안 돼요.", "changes": [{"from": "되요", "to": "돼요", "kind": "spelling"}]}]
    assert check_edits(ORIG, edits, 20, 21) == []


def test_undeclared_content_change_fails():
    edits = [{"idx": 9, "text": "온라인 저장소 서비스로는 GitHub가 가장 널리 쓰입니다.", "changes": TERM}]
    assert has(check_edits(ORIG, edits, 1, 10), "$[0].text: 적어 둔 교정 말고도 내용이 바뀜")


def test_from_not_in_original_fails():
    edits = [{"idx": 9, "text": "온라인 저장소 서비스로는 GitHub가 널리 쓰입니다.",
              "changes": [{"from": "깃 허브", "to": "GitHub", "kind": "term"}]}]
    assert "$[0].changes[0]: 바꾸기 전 표기 '깃 허브'가 원문에 없음" in check_edits(ORIG, edits, 1, 10)


def test_deletion_fails():
    edits = [{"idx": 9, "text": "온라인 저장소 서비스로는 널리 쓰입니다.",
              "changes": [{"from": "기 허브가", "to": ".", "kind": "term"}]}]
    assert "$[0].changes[0]: 삭제는 허용하지 않음(내용 변경)" in check_edits(ORIG, edits, 1, 10)


def test_punctuation_only_change_must_not_be_declared():
    edits = [{"idx": 4, "text": "작업 내용을 저장소에 기록하는 일을 커밋이라고 합니다.",
              "changes": [{"from": ".", "to": "!", "kind": "spelling"}]}]
    assert has(check_edits(ORIG, edits, 1, 10), "띄어쓰기·문장부호만 바꾼 것은 적지 않음")


def test_change_ratio_over_limit_fails():
    edits = [{"idx": 21, "text": "하하하하마바사아자차",
              "changes": [{"from": "가나다라", "to": "하하하하", "kind": "term"}]}]
    assert "$[0]: 바뀐 글자가 40%로 30% 초과 — 내용 변경으로 봄" in check_edits(ORIG, edits, 20, 21)


def test_idx_outside_range_fails():
    edits = [{"idx": 9, "text": "x", "changes": []}]
    assert "$[0].idx: 담당 범위 1~5 밖이거나 없는 문장 번호(9)" in check_edits(ORIG, edits, 1, 5)


def test_duplicate_idx_fails():
    edit = {"idx": 4, "text": "작업 내용을 저장소에 기록하는 일을 커밋이라고 합니다.", "changes": []}
    assert "$[1].idx: 같은 문장(4)을 두 번 고침" in check_edits(ORIG, [edit, dict(edit)], 1, 10)


def test_string_idx_reports_instead_of_crashing():
    edits = [{"idx": "9", "text": "x", "changes": []}]
    assert check_edits(ORIG, edits, 1, 10) == ["$[0].idx: integer 이어야 함"]


def test_not_a_list_reports():
    assert check_edits(ORIG, {"idx": 9}, 1, 10) == ["$: array 이어야 함"]


def test_decimal_point_change_detected():
    orig = {1: "하루 1.5 mg 을 드세요"}
    edits = [{"idx": 1, "text": "하루 15mg을 드세요.", "changes": []}]
    assert has(check_edits(orig, edits, 1, 1), "$[0].text: 적어 둔 교정 말고도 내용이 바뀜")


def test_minus_sign_change_detected():
    orig = {1: "온도가 -5도입니다"}
    edits = [{"idx": 1, "text": "온도가 5도입니다.", "changes": []}]
    assert has(check_edits(orig, edits, 1, 1), "$[0].text: 적어 둔 교정 말고도 내용이 바뀜")


def test_pure_insertion_rejected():
    orig = {1: "이 방법은 쓰면 됩니다"}
    edits = [{"idx": 1, "text": "이 방법은 쓰면 절대로 안 됩니다.",
              "changes": [{"from": "쓰면", "to": "쓰면 절대로 안", "kind": "spelling"}]}]
    assert "$[0].changes[0]: 원래 글자를 그대로 두고 덧붙이기만 한 변경 — 내용 추가로 봄" in         check_edits(orig, edits, 1, 1)


def test_middle_insertion_rejected():
    orig = {1: "이 방법은 쓰면 됩니다"}
    edits = [{"idx": 1, "text": "이 방법은 쓰면 안 됩니다.",
              "changes": [{"from": "쓰면 됩", "to": "쓰면 안 됩", "kind": "term"}]}]
    assert has(check_edits(orig, edits, 1, 1), "덧붙이기만 한 변경")


def test_pure_deletion_rejected():
    orig = {1: "그렇게 하면 안 됩니다"}
    edits = [{"idx": 1, "text": "그렇게 하면 됩니다.",
              "changes": [{"from": "안 됩니다", "to": "됩니다", "kind": "spelling"}]}]
    assert "$[0].changes[0]: 원래 글자 일부를 지우기만 한 변경 — 내용 삭제로 봄" in check_edits(orig, edits, 1, 1)


def test_spacing_only_declared_change_rejected():
    edits = [{"idx": 4, "text": "작업 내용을 저장소에 기록하는 일을 커밋이라고 합니다.",
              "changes": [{"from": "커밋 이라고", "to": "커밋이라고", "kind": "spelling"}]}]
    assert "$[0].changes[0]: 띄어쓰기·문장부호만 바꾼 것은 적지 않음" in check_edits(ORIG, edits, 1, 10)


def test_korean_to_english_term_in_medium_sentence_passes():
    orig = {10: "기 허브 주소는 github.com 입니다"}
    edits = [{"idx": 10, "text": "GitHub 주소는 github.com입니다.", "changes": TERM}]
    assert check_edits(orig, edits, 1, 12) == []


def test_term_fix_in_short_sentence_passes():
    orig = {1: "기 허브 써요"}
    edits = [{"idx": 1, "text": "GitHub 써요.", "changes": TERM}]
    assert check_edits(orig, edits, 1, 1) == []


def test_sample_lecture_edits_all_pass(sample):
    originals = {s["idx"]: s["raw"] for s in sample["segments"]}
    by_idx = {}
    for c in sample["corrections"]:
        by_idx.setdefault(c["idx"], []).append({"from": c["from"], "to": c["to"], "kind": c["kind"]})
    edits = [{"idx": s["idx"], "text": s["text"], "changes": by_idx.get(s["idx"], [])} for s in sample["segments"]]
    assert check_edits(originals, edits, 1, 12) == []
