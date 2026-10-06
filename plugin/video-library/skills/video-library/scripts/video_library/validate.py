"""lecture.json 과 AI 단계 결과물 검사기. 표준 라이브러리만.

구조 규칙은 schema/lecture.schema.json 에, 스키마로 쓰기 어려운 의미 규칙은 여기에 있다.
모든 검사 함수는 "<경로>: <이유>" 문자열 목록을 돌려준다(빈 목록 = 통과). 예외를 던지지 않는다 —
AI 가 만든 엉뚱한 값도 오류 메시지로 바꿔야 재시도 브리프 끝에 그대로 붙일 수 있다.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from .schemacheck import check

SCHEMA_VERSION = "1.0"
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "lecture.schema.json"
TIME_EPS = 1e-6
END_SLACK = 2.0  # 자막 끝 시간이 영상 길이를 살짝 넘는 경우를 허용한다(초)
FAQ_RANGE = (5, 10)
MAX_CHANGE_RATIO = 0.30
MIN_RATIO_BASE = 10  # 아주 짧은 문장은 한 단어만 고쳐도 비율이 커지므로 분모를 최소 10자로 본다


@lru_cache(maxsize=1)
def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def check_def(instance, name: str) -> list[str]:
    """스키마의 $defs/<name> 으로 검사한다."""
    return check(instance, {"$ref": f"#/$defs/{name}"}, root=load_schema())


def _at(errors: list[str], path: str) -> list[str]:
    """'$' 로 시작하는 하위 검사 오류의 경로 앞부분을 path 로 바꾼다."""
    return [path + e[1:] if e.startswith("$") else f"{path}: {e}" for e in errors]


def validate_lecture(doc) -> list[str]:
    errors = check(doc, load_schema())
    if errors:
        return errors  # 구조가 틀리면 의미 검사는 하지 않는다(엉뚱한 오류가 쏟아지지 않게)
    lec, segs = doc["lecture"], doc["segments"]
    errors += _check_lecture(lec)
    if not segs:
        return errors + ["$.segments: 문장이 하나도 없음"]
    errors += _check_segments(segs, lec["duration"])
    errors += _at(check_chapters(doc["chapters"], len(segs), lec["duration"], segs), "$.chapters")
    errors += _check_translations(doc)
    errors += _check_optional_steps(doc)
    errors += _check_refs(doc)
    return errors


def _check_lecture(lec: dict) -> list[str]:
    errors = []
    if lec["id"] != lec["video_id"]:
        errors.append("$.lecture.id: video_id 와 같아야 함")
    if not lec["source_url"].endswith("v=" + lec["video_id"]):
        errors.append("$.lecture.source_url: video_id 와 다름")
    try:
        stamp = datetime.fromisoformat(lec["processed_at"])
    except ValueError:
        errors.append("$.lecture.processed_at: ISO 8601 날짜·시간이어야 함")
    else:
        if stamp.tzinfo is None:
            errors.append("$.lecture.processed_at: 시간대(+09:00 등)가 있어야 함")
    return errors


def _check_segments(segs: list, duration: float) -> list[str]:
    errors = []
    for i, s in enumerate(segs):
        p = f"$.segments[{i}]"
        if s["idx"] != i + 1:
            errors.append(f"{p}.idx: {i + 1} 이어야 함")
        if s["start"] > s["end"] + TIME_EPS:
            errors.append(f"{p}: 시작이 끝보다 늦음")
        if i and s["start"] < segs[i - 1]["start"] - TIME_EPS:
            errors.append(f"{p}.start: 앞 문장보다 이름")
        if s["end"] > duration + END_SLACK:
            errors.append(f"{p}.end: 영상 길이({duration:.0f}초)를 넘음")
    return errors


def chapter_count_range(duration: float) -> tuple[int, int]:
    """영상 길이(초)에 맞는 대목차 개수 범위."""
    if duration < 600:
        return (2, 4)
    if duration < 3600:
        return (4, 10)
    return (6, 12)


def _valid_range(seg) -> bool:
    return (isinstance(seg, list) and len(seg) == 2
            and all(isinstance(v, int) and not isinstance(v, bool) for v in seg)
            and 1 <= seg[0] <= seg[1])


def _check_cover(items: list, first: int, last: int, path: str, parent_id) -> list[str]:
    """items 의 segments 범위가 first..last 를 빈틈·겹침 없이 차례로 덮는지, id 가 차례대로인지."""
    errors = []
    expected = first
    for k, item in enumerate(items):
        p = f"{path}[{k}]"
        if not isinstance(item, dict):
            return errors + [f"{p}: object 이어야 함"]
        want_id = str(k + 1) if parent_id is None else f"{parent_id}.{k + 1}"
        if item.get("id") != want_id:
            errors.append(f"{p}.id: '{want_id}' 이어야 함")
        seg = item.get("segments")
        if not _valid_range(seg):
            return errors + [f"{p}.segments: [시작 번호, 끝 번호] (시작 ≤ 끝) 이어야 함"]
        if seg[0] != expected:
            errors.append(f"{p}.segments: 빈틈 또는 겹침 — {expected}번부터 시작해야 함(현재 {seg[0]}번)")
        expected = seg[1] + 1
    if items and expected != last + 1:
        errors.append(f"{path}: 마지막 문장 {last}번까지 덮어야 함(현재 {expected - 1}번)")
    return errors


def check_chapters(chapters, n_segments: int, duration: float, segments: list | None = None) -> list[str]:
    """목차 규칙. 경로는 목차 배열 기준 '$'. segments 를 주면 start/end 가 문장 시간과 같은지도 본다."""
    errors = check(chapters, _array_of("chapter"), root=load_schema())
    if errors:
        return errors  # 모양이 틀리면 의미 검사를 하지 않는다(직접 호출돼도 예외 없이)
    lo, hi = chapter_count_range(duration)
    if not lo <= len(chapters) <= hi:
        errors.append(f"$: 영상 길이 {duration:.0f}초에는 대목차 {lo}~{hi}개여야 함(현재 {len(chapters)}개)")
    if not chapters:
        return errors
    errors += _check_cover(chapters, 1, n_segments, "$", None)
    for i, ch in enumerate(chapters):
        if not isinstance(ch, dict):
            continue
        p = f"$[{i}]"
        kids = ch.get("children") or []
        if kids:
            if not 2 <= len(kids) <= 6:
                errors.append(f"{p}.children: 소목차는 0개 또는 2~6개여야 함(현재 {len(kids)}개)")
            if _valid_range(ch.get("segments")):
                errors += _check_cover(kids, ch["segments"][0], ch["segments"][1], f"{p}.children", ch.get("id"))
            for j, kid in enumerate(kids):
                if isinstance(kid, dict) and kid.get("children"):
                    errors.append(f"{p}.children[{j}]: 목차는 2단까지만 허용")
        elif duration >= 600:
            errors.append(f"{p}.children: 10분 이상 영상은 대목차마다 소목차 2~6개가 필요함")
    if segments is not None:
        errors += _check_chapter_times(chapters, segments, "$")
    return errors


def _check_chapter_times(chapters: list, segments: list, path: str) -> list[str]:
    errors = []
    for i, ch in enumerate(chapters):
        p = f"{path}[{i}]"
        seg = ch.get("segments")
        if not _valid_range(seg) or seg[1] > len(segments):
            continue
        for key, want in (("start", segments[seg[0] - 1]["start"]), ("end", segments[seg[1] - 1]["end"])):
            got = ch.get(key)
            if not isinstance(got, (int, float)) or isinstance(got, bool):
                errors.append(f"{p}.{key}: 문장 시간 {want:.1f}과 같아야 함(현재 없음)")
            elif abs(got - want) > TIME_EPS:
                errors.append(f"{p}.{key}: 문장 시간 {want:.1f}과 같아야 함(현재 {got})")
        errors += _check_chapter_times(ch.get("children") or [], segments, f"{p}.children")
    return errors


def _array_of(name: str) -> dict:
    return {"type": "array", "items": {"$ref": f"#/$defs/{name}"}}


def _idx_errors(idx, n_segments: int, path: str) -> list[str]:
    return [] if 1 <= idx <= n_segments else [f"{path}: 없는 문장 번호({idx})"]


def check_translation_chunk(source_idxs: list[int], items) -> list[str]:
    """번역 결과가 원문 문장 번호와 1:1인지. 경로는 번역 배열 기준 '$'."""
    errors = check(items, _array_of("translationItem"), root=load_schema())
    if errors:
        return errors
    if [it["idx"] for it in items] != list(source_idxs):
        return [f"$: 번역 문장 번호가 원문과 1:1이 아님(원문 {len(source_idxs)}개, 번역 {len(items)}개)"]
    return [f"$[{i}].text: 빈 번역" for i, it in enumerate(items) if not it["text"].strip()]


def check_glossary(items, n_segments: int) -> list[str]:
    errors = check(items, _array_of("glossaryItem"), root=load_schema())
    if errors:
        return errors
    out = []
    for i, it in enumerate(items):
        out += _idx_errors(it["idx"], n_segments, f"$[{i}].idx")
    return out


def check_faq(items, n_segments: int, require_count: bool = True) -> list[str]:
    errors = check(items, _array_of("faqItem"), root=load_schema())
    if errors:
        return errors
    out = []
    lo, hi = FAQ_RANGE
    if require_count and not lo <= len(items) <= hi:
        out.append(f"$: FAQ는 {lo}~{hi}개여야 함(현재 {len(items)}개)")
    for i, it in enumerate(items):
        for j, idx in enumerate(it["evidence"]):
            out += _idx_errors(idx, n_segments, f"$[{i}].evidence[{j}]")
    return out


def check_mentions(items, n_segments: int) -> list[str]:
    errors = check(items, _array_of("mention"), root=load_schema())
    if errors:
        return errors
    out = []
    for i, it in enumerate(items):
        out += _idx_errors(it["idx"], n_segments, f"$[{i}].idx")
    return out


def _check_translations(doc: dict) -> list[str]:
    lec, segs, tr = doc["lecture"], doc["segments"], doc["translations"]
    errors = []
    source_idxs = [s["idx"] for s in segs]
    for lang, items in tr.items():
        p = f"$.translations.{lang}"
        if not re.fullmatch(r"[a-z]{2}", lang):
            errors.append(f"{p}: 언어 코드(두 글자 소문자)여야 함")
            continue
        if lang == lec["language"]:
            errors.append(f"{p}: 원문 언어는 번역에 넣지 않음")
            continue
        errors += _at(check_translation_chunk(source_idxs, items), p)
    skipped = lec["pipeline"]["skipped"]
    if lec["language"] != "ko" and "ko" not in tr and "translate" not in skipped:
        errors.append("$.translations: 외국어 영상은 한국어 번역(ko)이 필요함"
                      "(실패했다면 pipeline.skipped 에 translate 를 적음)")
    return errors


def _check_optional_steps(doc: dict) -> list[str]:
    n = len(doc["segments"])
    skipped = doc["lecture"]["pipeline"]["skipped"]
    errors = []
    if "glossary" in skipped:
        if doc["glossary"]:
            errors.append("$.glossary: 건너뛴 단계(glossary)인데 내용이 있음")
    elif not doc["glossary"]:
        errors.append("$.glossary: 비어 있음(실패했다면 pipeline.skipped 에 glossary 를 적음)")
    errors += _at(check_glossary(doc["glossary"], n), "$.glossary")
    if "faq" in skipped:
        if doc["faq"]:
            errors.append("$.faq: 건너뛴 단계(faq)인데 내용이 있음")
    else:
        errors += _at(check_faq(doc["faq"], n, require_count=True), "$.faq")
    return errors


def _check_refs(doc: dict) -> list[str]:
    n = len(doc["segments"])
    errors = _at(check_mentions(doc["mentions"], n), "$.mentions")
    for i, c in enumerate(doc["corrections"]):
        errors += _idx_errors(c["idx"], n, f"$.corrections[{i}].idx")
    return errors


_NUMBER_PUNCT = re.compile(r"(?<=\d)[.,:](?=\d)|[-−+](?=\d)")


def normalize_for_compare(text: str) -> str:
    """띄어쓰기·문장부호를 뺀 글자만 남긴다(교열 전후 내용 비교용).

    숫자의 일부인 기호(1.5 의 점, 10,000 의 쉼표, 12:30 의 쌍점, -5 의 부호)는 남긴다 —
    이것이 바뀌면 뜻이 바뀌기 때문이다(예: 1.5mg → 15mg).
    """
    keep = {m.start() for m in _NUMBER_PUNCT.finditer(text)}
    return "".join(ch for i, ch in enumerate(text)
                   if i in keep or not (ch.isspace() or unicodedata.category(ch)[0] in "PZ"))


def _affix(before: str, after: str) -> tuple[int, int]:
    """앞에서부터, 뒤에서부터 같은 글자 수(겹치지 않게)."""
    p = 0
    while p < min(len(before), len(after)) and before[p] == after[p]:
        p += 1
    s = 0
    while s < min(len(before), len(after)) - p and before[-1 - s] == after[-1 - s]:
        s += 1
    return p, s


_NEGATION = ("안", "못", "않", "없", "아니", "not", "no", "n't")


def _safe_pair(heard: str, term: str) -> bool:
    """자동자막이 한두 글자를 빠뜨리거나 더 넣은 것으로 볼 수 있는 안전한 쌍인지.
    단어 수가 같고, 바뀐 부분이 단어 한가운데의 1~2자이며, 숫자·부정어가 아니어야 한다."""
    if len(heard.split()) != len(term.split()):
        return False
    h, t = normalize_for_compare(heard).casefold(), normalize_for_compare(term).casefold()
    if not h or not t or h == t:
        return False
    pre, suf = _affix(h, t)
    if pre + suf < min(len(h), len(t)):  # 순수 덧붙이기·지우기가 아니면 예외가 필요 없다
        return False
    diff = (t if len(t) > len(h) else h)[pre:max(len(h), len(t)) - suf]
    if not 1 <= len(diff) <= 2 or pre < 1 or suf < 1:
        return False
    return not any(ch.isdigit() for ch in diff) and not any(neg in diff for neg in _NEGATION)


def term_pairs(context) -> set[tuple[str, str]]:
    """맥락표 key_terms 의 heard_as → term 쌍 중 안전한 것만(정규화·소문자). 교정 검사 예외에 쓴다."""
    pairs = set()
    terms = context.get("key_terms") if isinstance(context, dict) else None
    for kt in terms or []:
        if not isinstance(kt, dict) or not isinstance(kt.get("term"), str):
            continue
        for heard in kt.get("heard_as") or []:
            if isinstance(heard, str) and _safe_pair(heard, kt["term"]):
                pairs.add((normalize_for_compare(heard).casefold(), normalize_for_compare(kt["term"]).casefold()))
    return pairs


def _is_known_asr_fix(before: str, after: str, allowed_pairs) -> bool:
    b, a = before.casefold(), after.casefold()
    return any(h in b and b.replace(h, t, 1) == a for h, t in allowed_pairs)


def check_edits(originals: dict[int, str], edits, lo: int, hi: int,
                allowed_pairs: frozenset | set = frozenset()) -> list[str]:
    """교정·교열 결과 검사. 띄어쓰기·문장부호 외의 변경은 모두 changes 에 선언돼 있어야 한다."""
    errors = check(edits, _array_of("editItem"), root=load_schema())
    if errors:
        return errors
    seen: set[int] = set()
    for i, e in enumerate(edits):
        p = f"$[{i}]"
        idx = e["idx"]
        if not lo <= idx <= hi or idx not in originals:
            errors.append(f"{p}.idx: 담당 범위 {lo}~{hi} 밖이거나 없는 문장 번호({idx})")
            continue
        if idx in seen:
            errors.append(f"{p}.idx: 같은 문장({idx})을 두 번 고침")
            continue
        seen.add(idx)
        errors += _check_one_edit(originals[idx], e, p, allowed_pairs)
    return errors


def _check_one_edit(original: str, edit: dict, p: str, allowed_pairs=frozenset()) -> list[str]:
    current = normalize_for_compare(original)
    base = max(MIN_RATIO_BASE, len(current))
    changed = 0
    errors = []
    for k, c in enumerate(edit["changes"]):
        at = f"{p}.changes[{k}]"
        before, after = normalize_for_compare(c["from"]), normalize_for_compare(c["to"])
        if before == after:
            errors.append(f"{at}: 띄어쓰기·문장부호만 바꾼 것은 적지 않음")
            continue
        if not after:
            errors.append(f"{at}: 삭제는 허용하지 않음(내용 변경)")
            continue
        pre, suf = _affix(before, after)
        excused = c["kind"] == "term" and _is_known_asr_fix(before, after, allowed_pairs)
        if pre + suf >= len(before) and not excused:
            errors.append(f"{at}: 원래 글자를 그대로 두고 덧붙이기만 한 변경 — 내용 추가로 봄")
            continue
        if pre + suf >= len(after) and not excused:
            errors.append(f"{at}: 원래 글자 일부를 지우기만 한 변경 — 내용 삭제로 봄")
            continue
        if before not in current:
            errors.append(f"{at}: 바꾸기 전 표기 '{c['from']}'가 원문에 없음")
            continue
        current = current.replace(before, after, 1)
        # 용어 교정(한글 표기 → 영어 이름 등)은 길이가 늘어나는 게 정상이라 바뀐 원래 글자만 센다
        cost = len(before) if c["kind"] == "term" and not excused else max(len(before), len(after))
        changed += cost - pre - suf
    if errors:
        return errors
    if current != normalize_for_compare(edit["text"]):
        return [f"{p}.text: 적어 둔 교정 말고도 내용이 바뀜(띄어쓰기·문장부호 외 변경은 changes 에 적어야 함)"]
    if changed / base > MAX_CHANGE_RATIO:
        return [f"{p}: 바뀐 글자가 {changed / base:.0%}로 30% 초과 — 내용 변경으로 봄"]
    return []



def check_context(data) -> list[str]:
    """맥락 파악 단계 결과(build/context.json)."""
    return check_def(data, "context")


def check_outline(data, n_segments: int, duration: float) -> list[str]:
    """목차·요약 단계 결과(build/outline.json). 목차 시간(start/end)은 조립 단계가 채운다."""
    errors = check_def(data, "outline")
    if errors:
        return errors
    errors += _at(check_chapters(data["chapters"], n_segments, duration), "$.chapters")
    errors += _at(check_mentions(data["mentions"], n_segments), "$.mentions")
    return errors
