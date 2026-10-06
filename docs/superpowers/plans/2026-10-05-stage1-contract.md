# video-library 1단계(약속) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 플러그인과 뷰어 서버(PC·Railway)가 함께 지킬 데이터 약속 — `lecture.schema.json`, 검사기(`validate`), 샘플 `lecture.json`, `vl.py validate` 명령, API 문서 — 를 만든다.

**Architecture:** 구조 규칙은 JSON Schema 파일 한 곳에 적고, 표준 라이브러리만으로 그 부분집합을 검사하는 작은 검사기(`schemacheck`)로 읽는다. 스키마로 표현하기 어려운 의미 규칙(문장 번호 연속, 목차 빈틈·겹침, 번역 1:1, 교열 시 내용 불변 등)은 `validate`가 파이썬으로 검사한다. 모든 검사 함수는 예외 대신 `"<경로>: <이유>"` 문자열 목록을 돌려준다(빈 목록 = 통과) — AI 재시도 브리프에 그대로 붙이기 위해서다.

**Tech Stack:** Python 3.10+ 표준 라이브러리(`json`, `re`, `unicodedata`, `datetime`, `argparse`), 개발용 pytest.

**Spec:** [plugin-app/docs/superpowers/specs/2026-10-05-video-library-design.md](../specs/2026-10-05-video-library-design.md) — 5장(약속), 6.2~6.3(AI 결과 검사), 10장 1단계

## Global Constraints

- 모든 명령은 `plugin-app/` 폴더에서 실행한다. 이하 `SKILL_DIR` = `plugin/video-library/skills/video-library`.
- 런타임 코드는 **파이썬 표준 라이브러리만** 쓴다(pytest는 개발용). 문법은 Python 3.10에서도 동작해야 한다(`from __future__ import annotations` 사용, `match`·3.11+ 전용 기능 금지).
- `schema_version` = `"1.0"`. `lecture.field` ∈ `dev | finance | science | medical | other`. `lecture.mode` = `"text"`. `pipeline.skipped` ∈ `glossary | translate | faq`.
- 대목차 개수: 10분(600초) 미만 2~4개, 60분(3600초) 미만 4~10개, 그 이상 6~12개. 소목차는 0개 또는 2~6개, 10분 이상 영상은 대목차마다 2~6개 필수. 목차는 2단까지.
- 번역 `translations.<언어>`는 `segments`와 번호·개수 1:1, 원문 언어 키 금지. 외국어(`language != "ko"`) 영상은 `translations.ko` 필수(단 `translate`가 skipped면 면제).
- FAQ는 5~10개(단 `faq`가 skipped면 빈 배열이어야 함). 용어집은 1개 이상(단 `glossary`가 skipped면 빈 배열).
- 교열 검사: 원문에 선언한 `changes`를 적용하고 띄어쓰기·문장부호를 뺀 글자가 결과와 같아야 한다. `changes` 한 건은 원문·결과 각 20자 이내, 문장당 바뀐 원문 글자 비율 30% 이하, 삭제(결과가 비는 변경) 금지.
- 오류 메시지는 한국어, 형식은 `"<JSON 경로>: <이유>"`. 경로는 `$`(검사 대상의 맨 위)에서 시작한다.
- 테스트용 데이터는 **직접 쓴 샘플만** 쓴다(남의 영상 내용 금지). 이 저장소는 공개 예정이다.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` 를 붙인다(Codex로 실행하면 해당 도구 규칙을 따른다).

## Review Focus

1. **`True`/`False`가 번호 자리에 들어온 경우** — 파이썬에서 `bool`은 `int`의 하위 타입이라 그냥 두면 `idx: true`가 통과한다. 정수·숫자 자리에서 `bool`은 불합격이어야 한다. → Task 1·2 테스트.
2. **AI가 번호를 문자열로 적은 경우(`"idx": "12"`)** — 예외로 죽지 않고 "integer 이어야 함" 오류로 돌아와야 재시도 브리프에 붙일 수 있다. → Task 5 테스트.
3. **문장이 하나도 없는 `lecture.json`** — 목차·번역 검사에서 인덱스 오류로 죽지 말고 "문장이 하나도 없음" 한 줄로 끝나야 한다. → Task 2 테스트.
4. **메모장 등이 붙인 UTF-8 BOM이 있는 파일** — Windows에서 흔하다. `vl.py validate`가 JSON 오류 없이 읽어야 한다. → Task 7 테스트.
5. **Windows 콘솔(cp949)에서 한국어 오류 출력** — `UnicodeEncodeError`로 죽지 않아야 한다. → Task 7 테스트.

---

## File Structure

| 파일 | 책임 |
|---|---|
| `pytest.ini` | 테스트 위치 지정 |
| `requirements-dev.txt` | 개발용 의존성(pytest) |
| `SKILL_DIR/scripts/vl.py` | 단일 진입점(명령 표 → 모듈 `main(argv)` 호출), 콘솔 UTF-8 설정 |
| `SKILL_DIR/scripts/video_library/__init__.py` | 패키지 표시, `__version__` |
| `SKILL_DIR/scripts/video_library/schemacheck.py` | JSON Schema 부분집합 검사기(범용, 이 프로젝트 지식 없음) |
| `SKILL_DIR/scripts/schema/lecture.schema.json` | 약속의 구조 규칙(`lecture.json` + AI 결과물 `$defs`) |
| `SKILL_DIR/scripts/video_library/validate.py` | 의미 규칙 검사 + 스키마 적용(`validate_lecture`, `check_*`) |
| `SKILL_DIR/scripts/video_library/cli_validate.py` | `vl.py validate <파일>` 명령 |
| `SKILL_DIR/tests/conftest.py` | `scripts/`를 import 경로에 넣기, `sample` 픽스처 |
| `SKILL_DIR/tests/fixtures/sample_lecture.json` | 직접 쓴 8분짜리 가상 강의 |
| `SKILL_DIR/tests/test_*.py` | 작업별 테스트 |
| `docs/api.md` | `index.json`·진행 상황·서버 API 약속 |

---

### Task 1: 뼈대 + JSON Schema 부분집합 검사기

**Files:**
- Create: `pytest.ini`, `requirements-dev.txt`
- Create: `SKILL_DIR/scripts/video_library/__init__.py`
- Create: `SKILL_DIR/scripts/video_library/schemacheck.py`
- Create: `SKILL_DIR/tests/conftest.py`
- Test: `SKILL_DIR/tests/test_schemacheck.py`

**Interfaces:**
- Consumes: 없음
- Produces: `video_library.schemacheck.check(instance, schema: dict, root: dict | None = None, path: str = "$") -> list[str]`. 지원 키워드: `type`(object·array·string·integer·number·boolean), `required`, `properties`, `additionalProperties`(스키마일 때), `items`, `enum`, `minimum`, `minLength`, `maxLength`, `minItems`, `maxItems`, `pattern`, `$ref`(`#/$defs/<이름>`만). 테스트 픽스처 `sample`(Task 2에서 파일 생성).

- [ ] **Step 1: 뼈대 파일 작성**

`pytest.ini`:
```ini
[pytest]
testpaths = plugin/video-library/skills/video-library/tests
addopts = -q
```

`requirements-dev.txt`:
```text
pytest>=8
```

`SKILL_DIR/scripts/video_library/__init__.py`:
```python
"""video-library — 유튜브 영상을 교정·정리해 영상자료실에 쌓는 플러그인의 기계 단계 코드."""

__version__ = "0.1.0"
```

`SKILL_DIR/tests/conftest.py`:
```python
"""테스트가 어디서 실행되든 스킬의 scripts/ 를 import 경로에 넣는다(설치 불요)."""
import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES = TESTS_DIR / "fixtures"
sys.path.insert(0, str(TESTS_DIR.parent / "scripts"))


@pytest.fixture
def sample() -> dict:
    """직접 쓴 샘플 lecture.json. 테스트마다 새로 읽어 서로 영향을 주지 않는다."""
    return json.loads((FIXTURES / "sample_lecture.json").read_text(encoding="utf-8"))
```

- [ ] **Step 2: 실패하는 테스트 작성**

`SKILL_DIR/tests/test_schemacheck.py`:
```python
from video_library.schemacheck import check


def test_valid_instance_returns_empty_list():
    schema = {"type": "object", "required": ["a"], "properties": {"a": {"type": "integer"}}}
    assert check({"a": 1}, schema) == []


def test_type_mismatch_reports_path():
    schema = {"type": "object", "properties": {"a": {"type": "integer"}}}
    assert check({"a": "x"}, schema) == ["$.a: integer 이어야 함"]


def test_bool_is_not_integer_or_number():
    assert check(True, {"type": "integer"}) == ["$: integer 이어야 함"]
    assert check(False, {"type": "number"}) == ["$: number 이어야 함"]
    assert check(1.5, {"type": "number"}) == []


def test_required_missing():
    assert check({}, {"type": "object", "required": ["x"]}) == ["$: 필수 항목 'x' 없음"]


def test_enum_pattern_lengths():
    assert check("z", {"enum": ["a", "b"]}) == ["$: 허용 값 ['a', 'b'] 중 하나여야 함"]
    assert check("abc", {"type": "string", "pattern": "^[a-z]{2}$"}) == ["$: 형식(^[a-z]{2}$)에 맞지 않음"]
    assert check("", {"type": "string", "minLength": 1}) == ["$: 1자 이상이어야 함"]
    assert check("abcd", {"type": "string", "maxLength": 3}) == ["$: 3자 이하여야 함"]


def test_minimum_and_item_counts():
    assert check(-1, {"type": "number", "minimum": 0}) == ["$: 0 이상이어야 함"]
    assert check([1], {"type": "array", "minItems": 2}) == ["$: 항목 2개 이상이어야 함"]
    assert check([1, 2, 3], {"type": "array", "maxItems": 2}) == ["$: 항목 2개 이하여야 함"]


def test_items_and_additional_properties():
    schema = {"type": "object",
              "additionalProperties": {"type": "array", "items": {"type": "integer"}}}
    assert check({"en": [1, "x"]}, schema) == ["$.en[1]: integer 이어야 함"]


def test_additional_properties_skips_declared_properties():
    schema = {"type": "object", "properties": {"a": {"type": "string"}},
              "additionalProperties": {"type": "integer"}}
    assert check({"a": "ok", "b": 2}, schema) == []


def test_ref_resolves_recursively():
    schema = {
        "$defs": {"node": {"type": "object", "required": ["kids"],
                           "properties": {"kids": {"type": "array", "items": {"$ref": "#/$defs/node"}}}}},
        "$ref": "#/$defs/node",
    }
    assert check({"kids": [{"kids": []}, {}]}, schema) == ["$.kids[1]: 필수 항목 'kids' 없음"]


def test_ref_with_explicit_root():
    root = {"$defs": {"n": {"type": "integer"}}}
    assert check("x", {"$ref": "#/$defs/n"}, root=root, path="$[3]") == ["$[3]: integer 이어야 함"]
```

- [ ] **Step 3: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_schemacheck.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'video_library.schemacheck'`

- [ ] **Step 4: 구현**

`SKILL_DIR/scripts/video_library/schemacheck.py`:
```python
"""JSON Schema(2020-12)의 작은 부분집합 검사기. 표준 라이브러리만.

지원 키워드: type, required, properties, additionalProperties(스키마), items, enum,
minimum, minLength, maxLength, minItems, maxItems, pattern, $ref("#/$defs/<이름>").
오류는 "<경로>: <이유>" 문자열 목록으로 돌려준다(빈 목록 = 통과). 예외를 던지지 않는다.
bool 은 integer·number 로 보지 않는다(파이썬에서 bool 은 int 의 하위 타입이라 따로 막는다).
"""
from __future__ import annotations

import re

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
}
_REF_PREFIX = "#/$defs/"


def resolve(root: dict, ref: str) -> dict:
    if not ref.startswith(_REF_PREFIX):
        raise ValueError(f"지원하지 않는 $ref: {ref}")
    return root["$defs"][ref[len(_REF_PREFIX):]]


def check(instance, schema: dict, root: dict | None = None, path: str = "$") -> list[str]:
    root = schema if root is None else root
    if "$ref" in schema:
        return check(instance, resolve(root, schema["$ref"]), root, path)

    t = schema.get("type")
    if t is not None and not _TYPES[t](instance):
        return [f"{path}: {t} 이어야 함"]

    errors: list[str] = []
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: 허용 값 {schema['enum']} 중 하나여야 함")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: {schema['minLength']}자 이상이어야 함")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: {schema['maxLength']}자 이하여야 함")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: 형식({schema['pattern']})에 맞지 않음")

    if _TYPES["number"](instance) and "minimum" in schema and instance < schema["minimum"]:
        errors.append(f"{path}: {schema['minimum']} 이상이어야 함")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: 필수 항목 '{key}' 없음")
        props = schema.get("properties", {})
        for key, sub in props.items():
            if key in instance:
                errors += check(instance[key], sub, root, f"{path}.{key}")
        extra = schema.get("additionalProperties")
        if isinstance(extra, dict):
            for key, value in instance.items():
                if key not in props:
                    errors += check(value, extra, root, f"{path}.{key}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: 항목 {schema['minItems']}개 이상이어야 함")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: 항목 {schema['maxItems']}개 이하여야 함")
        if "items" in schema:
            for i, item in enumerate(instance):
                errors += check(item, schema["items"], root, f"{path}[{i}]")

    return errors
```

- [ ] **Step 5: 통과 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_schemacheck.py -v`
Expected: 10 passed

- [ ] **Step 6: 커밋**

```bash
git add pytest.ini requirements-dev.txt plugin/video-library/skills/video-library/scripts/video_library/__init__.py plugin/video-library/skills/video-library/scripts/video_library/schemacheck.py plugin/video-library/skills/video-library/tests/conftest.py plugin/video-library/skills/video-library/tests/test_schemacheck.py
git commit -m "feat(contract): add stdlib JSON Schema subset checker" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `lecture.schema.json` + 샘플 + `validate_lecture`(구조·강의 정보·문장)

**Files:**
- Create: `SKILL_DIR/scripts/schema/lecture.schema.json`
- Create: `SKILL_DIR/tests/fixtures/sample_lecture.json`
- Create: `SKILL_DIR/scripts/video_library/validate.py`
- Test: `SKILL_DIR/tests/test_validate_lecture.py`

**Interfaces:**
- Consumes: `schemacheck.check`
- Produces (`video_library.validate`):
  - 상수 `SCHEMA_VERSION = "1.0"`, `SCHEMA_PATH`, `TIME_EPS = 1e-6`, `END_SLACK = 2.0`
  - `load_schema() -> dict` (캐시됨 — 호출자는 고치지 않는다)
  - `check_def(instance, name: str) -> list[str]` — 스키마 `$defs/<name>` 으로 검사
  - `validate_lecture(doc) -> list[str]`
  - 내부 도우미 `_at(errors: list[str], path: str) -> list[str]` — 하위 검사 오류의 맨 앞 `$`를 `path`로 바꾼다
- 스키마 `$defs` 이름(이후 Task가 씀): `videoId`, `field`, `lecture`, `segment`, `translationItem`, `correction`, `chapter`, `mention`, `glossaryItem`, `faqItem`, `change`, `editItem`, `context`, `outline`

- [ ] **Step 1: 스키마 작성**

`SKILL_DIR/scripts/schema/lecture.schema.json`:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "urn:video-library:lecture.schema.json",
  "title": "lecture.json",
  "description": "video-library 플러그인과 뷰어 서버(PC·Railway)의 약속. 시간은 초(number). 의미 규칙(번호 연속, 목차 덮기, 번역 1:1, 교열 내용 불변 등)은 validate.py 가 추가로 검사한다. $defs 의 context·editItem·outline 은 AI 단계 결과물 형식이다.",
  "type": "object",
  "required": ["schema_version", "lecture", "segments", "translations", "corrections", "chapters", "mentions", "glossary", "faq"],
  "properties": {
    "schema_version": {"enum": ["1.0"]},
    "lecture": {"$ref": "#/$defs/lecture"},
    "segments": {"type": "array", "items": {"$ref": "#/$defs/segment"}},
    "translations": {"type": "object", "additionalProperties": {"type": "array", "items": {"$ref": "#/$defs/translationItem"}}},
    "corrections": {"type": "array", "items": {"$ref": "#/$defs/correction"}},
    "chapters": {"type": "array", "items": {"$ref": "#/$defs/chapter"}},
    "mentions": {"type": "array", "items": {"$ref": "#/$defs/mention"}},
    "glossary": {"type": "array", "items": {"$ref": "#/$defs/glossaryItem"}},
    "faq": {"type": "array", "items": {"$ref": "#/$defs/faqItem"}}
  },
  "$defs": {
    "videoId": {"type": "string", "pattern": "^[A-Za-z0-9_-]{11}$"},
    "field": {"enum": ["dev", "finance", "science", "medical", "other"]},
    "lecture": {
      "type": "object",
      "required": ["id", "video_id", "source_url", "title", "channel", "duration", "thumbnail_url", "language", "field", "one_liner", "mode", "processed_at", "pipeline"],
      "properties": {
        "id": {"$ref": "#/$defs/videoId"},
        "video_id": {"$ref": "#/$defs/videoId"},
        "source_url": {"type": "string", "pattern": "^https://www\\.youtube\\.com/watch\\?v=[A-Za-z0-9_-]{11}$"},
        "title": {"type": "string", "minLength": 1},
        "channel": {"type": "string"},
        "duration": {"type": "number", "minimum": 1},
        "thumbnail_url": {"type": "string", "pattern": "^https://"},
        "language": {"type": "string", "pattern": "^[a-z]{2}$"},
        "field": {"$ref": "#/$defs/field"},
        "one_liner": {"type": "string", "minLength": 1, "maxLength": 80},
        "mode": {"enum": ["text"]},
        "processed_at": {"type": "string", "minLength": 1},
        "pipeline": {
          "type": "object",
          "required": ["version", "caption_kind", "skipped"],
          "properties": {
            "version": {"type": "string", "minLength": 1},
            "caption_kind": {"enum": ["manual", "auto"]},
            "skipped": {"type": "array", "items": {"enum": ["glossary", "translate", "faq"]}}
          }
        }
      }
    },
    "segment": {
      "type": "object",
      "required": ["idx", "start", "end", "text", "raw"],
      "properties": {
        "idx": {"type": "integer", "minimum": 1},
        "start": {"type": "number", "minimum": 0},
        "end": {"type": "number", "minimum": 0},
        "text": {"type": "string", "minLength": 1},
        "raw": {"type": "string"}
      }
    },
    "translationItem": {
      "type": "object",
      "required": ["idx", "text"],
      "properties": {
        "idx": {"type": "integer", "minimum": 1},
        "text": {"type": "string", "minLength": 1}
      }
    },
    "change": {
      "type": "object",
      "required": ["from", "to", "kind"],
      "properties": {
        "from": {"type": "string", "minLength": 1, "maxLength": 20},
        "to": {"type": "string", "minLength": 1, "maxLength": 20},
        "kind": {"enum": ["term", "spelling"]}
      }
    },
    "correction": {
      "type": "object",
      "required": ["idx", "from", "to", "kind"],
      "properties": {
        "idx": {"type": "integer", "minimum": 1},
        "from": {"type": "string", "minLength": 1, "maxLength": 20},
        "to": {"type": "string", "minLength": 1, "maxLength": 20},
        "kind": {"enum": ["term", "spelling"]}
      }
    },
    "chapter": {
      "type": "object",
      "required": ["id", "title", "summary", "segments", "children"],
      "properties": {
        "id": {"type": "string", "pattern": "^[0-9]+(\\.[0-9]+)?$"},
        "title": {"type": "string", "minLength": 1, "maxLength": 30},
        "summary": {"type": "string", "minLength": 1},
        "segments": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "integer", "minimum": 1}},
        "start": {"type": "number", "minimum": 0},
        "end": {"type": "number", "minimum": 0},
        "children": {"type": "array", "items": {"$ref": "#/$defs/chapter"}}
      }
    },
    "mention": {
      "type": "object",
      "required": ["kind", "text", "idx"],
      "properties": {
        "kind": {"enum": ["link", "book", "command", "other"]},
        "text": {"type": "string", "minLength": 1},
        "url": {"type": "string", "pattern": "^https?://"},
        "idx": {"type": "integer", "minimum": 1}
      }
    },
    "glossaryItem": {
      "type": "object",
      "required": ["term", "definition", "idx"],
      "properties": {
        "term": {"type": "string", "minLength": 1},
        "definition": {"type": "string", "minLength": 1},
        "analogy": {"type": "string", "minLength": 1},
        "claim_note": {"type": "string", "minLength": 1},
        "idx": {"type": "integer", "minimum": 1}
      }
    },
    "faqItem": {
      "type": "object",
      "required": ["question", "answer", "evidence"],
      "properties": {
        "question": {"type": "string", "minLength": 1},
        "answer": {"type": "string", "minLength": 1},
        "evidence": {"type": "array", "minItems": 1, "items": {"type": "integer", "minimum": 1}}
      }
    },
    "editItem": {
      "type": "object",
      "required": ["idx", "text", "changes"],
      "properties": {
        "idx": {"type": "integer", "minimum": 1},
        "text": {"type": "string", "minLength": 1},
        "changes": {"type": "array", "items": {"$ref": "#/$defs/change"}}
      }
    },
    "context": {
      "type": "object",
      "required": ["field", "one_liner", "topic_summary", "key_terms", "proper_nouns"],
      "properties": {
        "field": {"$ref": "#/$defs/field"},
        "one_liner": {"type": "string", "minLength": 1, "maxLength": 80},
        "topic_summary": {"type": "string", "minLength": 1},
        "key_terms": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["term", "heard_as"],
            "properties": {
              "term": {"type": "string", "minLength": 1},
              "heard_as": {"type": "array", "items": {"type": "string", "minLength": 1}},
              "note": {"type": "string"}
            }
          }
        },
        "proper_nouns": {"type": "array", "items": {"type": "string", "minLength": 1}}
      }
    },
    "outline": {
      "type": "object",
      "required": ["chapters", "mentions"],
      "properties": {
        "chapters": {"type": "array", "items": {"$ref": "#/$defs/chapter"}},
        "mentions": {"type": "array", "items": {"$ref": "#/$defs/mention"}}
      }
    }
  }
}
```

- [ ] **Step 2: 샘플 작성 (직접 쓴 가상 강의, 8분)**

`SKILL_DIR/tests/fixtures/sample_lecture.json`:
```json
{
  "schema_version": "1.0",
  "lecture": {
    "id": "AbCdEfGhIjK",
    "video_id": "AbCdEfGhIjK",
    "source_url": "https://www.youtube.com/watch?v=AbCdEfGhIjK",
    "title": "깃 기초 맛보기 (샘플)",
    "channel": "샘플 채널",
    "duration": 480.0,
    "thumbnail_url": "https://i.ytimg.com/vi/AbCdEfGhIjK/hqdefault.jpg",
    "language": "ko",
    "field": "dev",
    "one_liner": "깃의 저장소·커밋·브랜치·병합을 8분 안에 훑는 입문 강의",
    "mode": "text",
    "processed_at": "2026-10-05T14:03:00+09:00",
    "pipeline": {"version": "0.1.0", "caption_kind": "auto", "skipped": []}
  },
  "segments": [
    {"idx": 1, "start": 0.0, "end": 35.0, "text": "안녕하세요. 오늘은 깃의 기본 개념을 짧게 살펴보겠습니다.", "raw": "안녕하세요 오늘은 깃의 기본 개념을 짧게 살펴보겠습니다"},
    {"idx": 2, "start": 35.0, "end": 72.5, "text": "깃은 파일의 변경 이력을 기록하는 도구입니다.", "raw": "깃은 파일의 변경 이력을 기록하는 도구입니다"},
    {"idx": 3, "start": 72.5, "end": 110.0, "text": "변경 이력을 저장하는 공간을 저장소, 영어로 리포지토리라고 부릅니다.", "raw": "변경 이력을 저장하는 공간을 저장소 영어로 리포지 토리라고 부릅니다"},
    {"idx": 4, "start": 110.0, "end": 150.0, "text": "작업 내용을 저장소에 기록하는 일을 커밋이라고 합니다.", "raw": "작업 내용을 저장소에 기록하는 일을 커밋 이라고 합니다"},
    {"idx": 5, "start": 150.0, "end": 190.0, "text": "커밋에는 무엇을 바꿨는지 짧은 메시지를 남깁니다.", "raw": "커밋에는 무엇을 바꿨는지 짧은 메시지를 남깁니다"},
    {"idx": 6, "start": 190.0, "end": 230.0, "text": "다음으로 브랜치를 알아보겠습니다.", "raw": "다음으로 브랜치를 알아보겠습니다"},
    {"idx": 7, "start": 230.0, "end": 270.0, "text": "브랜치는 원본을 건드리지 않고 따로 작업하는 갈래입니다.", "raw": "브랜치는 원본을 건드리지 않고 따로 작업하는 갈래입니다"},
    {"idx": 8, "start": 270.0, "end": 310.0, "text": "작업이 끝나면 브랜치를 원래 줄기에 합치는데, 이것을 병합이라고 합니다.", "raw": "작업이 끝나면 브랜치를 원래 줄기에 합치는데 이것을 병합이라고 합니다"},
    {"idx": 9, "start": 310.0, "end": 350.0, "text": "온라인 저장소 서비스로는 GitHub가 널리 쓰입니다.", "raw": "온라인 저장소 서비스로는 기 허브가 널리 쓰입니다"},
    {"idx": 10, "start": 350.0, "end": 390.0, "text": "GitHub 주소는 github.com입니다.", "raw": "기 허브 주소는 github.com 입니다"},
    {"idx": 11, "start": 390.0, "end": 430.0, "text": "처음에는 git status 명령으로 상태를 확인하는 습관을 들이세요.", "raw": "처음에는 git status 명령으로 상태를 확인하는 습관을 들이세요"},
    {"idx": 12, "start": 430.0, "end": 478.0, "text": "오늘 내용은 여기까지입니다. 감사합니다.", "raw": "오늘 내용은 여기까지입니다 감사합니다"}
  ],
  "translations": {
    "en": [
      {"idx": 1, "text": "Hello. Today we will take a quick look at the basic concepts of Git."},
      {"idx": 2, "text": "Git is a tool that records the change history of files."},
      {"idx": 3, "text": "The place that stores the change history is called a repository."},
      {"idx": 4, "text": "Recording your work into the repository is called a commit."},
      {"idx": 5, "text": "Each commit carries a short message about what you changed."},
      {"idx": 6, "text": "Next, let's look at branches."},
      {"idx": 7, "text": "A branch is a separate line of work that leaves the original untouched."},
      {"idx": 8, "text": "When the work is done, you join the branch back into the main line, which is called a merge."},
      {"idx": 9, "text": "GitHub is a widely used online repository service."},
      {"idx": 10, "text": "GitHub's address is github.com."},
      {"idx": 11, "text": "At first, build the habit of checking the status with the git status command."},
      {"idx": 12, "text": "That's all for today. Thank you."}
    ]
  },
  "corrections": [
    {"idx": 9, "from": "기 허브", "to": "GitHub", "kind": "term"},
    {"idx": 10, "from": "기 허브", "to": "GitHub", "kind": "term"}
  ],
  "chapters": [
    {"id": "1", "title": "깃과 커밋", "summary": "깃이 파일의 변경 이력을 기록하는 도구라고 소개한다. 이력을 저장하는 공간인 저장소와, 작업을 기록하는 커밋을 설명한다. 커밋에는 짧은 메시지를 남긴다고 말한다.",
     "segments": [1, 5], "start": 0.0, "end": 190.0,
     "children": [
       {"id": "1.1", "title": "깃과 저장소", "summary": "깃의 역할과 저장소의 뜻을 설명한다.", "segments": [1, 3], "start": 0.0, "end": 110.0, "children": []},
       {"id": "1.2", "title": "커밋", "summary": "작업을 기록하는 커밋과 커밋 메시지를 설명한다.", "segments": [4, 5], "start": 110.0, "end": 190.0, "children": []}
     ]},
    {"id": "2", "title": "브랜치와 GitHub", "summary": "브랜치를 원본과 따로 작업하는 갈래로 설명하고, 작업 후 합치는 병합을 소개한다. 온라인 저장소 서비스로 GitHub를 언급하고, git status로 상태를 확인하는 습관을 권한다.",
     "segments": [6, 12], "start": 190.0, "end": 478.0,
     "children": [
       {"id": "2.1", "title": "브랜치와 병합", "summary": "브랜치와 병합의 개념을 설명한다.", "segments": [6, 8], "start": 190.0, "end": 310.0, "children": []},
       {"id": "2.2", "title": "GitHub와 첫 습관", "summary": "GitHub를 소개하고 git status 습관을 권한다.", "segments": [9, 12], "start": 310.0, "end": 478.0, "children": []}
     ]}
  ],
  "mentions": [
    {"kind": "link", "text": "GitHub", "url": "https://github.com", "idx": 10},
    {"kind": "command", "text": "git status", "idx": 11}
  ],
  "glossary": [
    {"term": "커밋(Commit)", "definition": "작업한 변경 내용을 저장소에 하나의 기록으로 남기는 일입니다.", "analogy": "문서를 고칠 때마다 날짜와 메모를 붙여 사본을 보관해 두는 것과 비슷합니다.", "idx": 4},
    {"term": "브랜치(Branch)", "definition": "원본에 영향을 주지 않고 따로 작업할 수 있게 나눈 작업 흐름입니다.", "analogy": "원고를 복사해 초안을 따로 고친 뒤 나중에 원본에 반영하는 것과 비슷합니다.", "idx": 7}
  ],
  "faq": [
    {"question": "깃은 무엇을 하는 도구인가요?", "answer": "파일의 변경 이력을 기록하는 도구라고 설명합니다.", "evidence": [2]},
    {"question": "저장소(리포지토리)는 무엇인가요?", "answer": "변경 이력을 저장하는 공간입니다.", "evidence": [3]},
    {"question": "커밋할 때 무엇을 남기나요?", "answer": "무엇을 바꿨는지 짧은 메시지를 남깁니다.", "evidence": [5]},
    {"question": "브랜치는 왜 쓰나요?", "answer": "원본을 건드리지 않고 따로 작업하기 위해서입니다.", "evidence": [7]},
    {"question": "처음에 들이면 좋은 습관은 무엇인가요?", "answer": "git status 명령으로 상태를 확인하는 습관입니다.", "evidence": [11]}
  ]
}
```

- [ ] **Step 3: 실패하는 테스트 작성**

`SKILL_DIR/tests/test_validate_lecture.py`:
```python
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
```

(`test_segment_end_within_slack_is_ok`는 Task 3에서 목차 시간 검사가 붙어도 계속 통과하도록 목차 끝 시간까지 함께 고친다.)

- [ ] **Step 4: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_validate_lecture.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'video_library.validate'`

- [ ] **Step 5: 구현**

`SKILL_DIR/scripts/video_library/validate.py`:
```python
"""lecture.json 과 AI 단계 결과물 검사기. 표준 라이브러리만.

구조 규칙은 schema/lecture.schema.json 에, 스키마로 쓰기 어려운 의미 규칙은 여기에 있다.
모든 검사 함수는 "<경로>: <이유>" 문자열 목록을 돌려준다(빈 목록 = 통과). 예외를 던지지 않는다 —
AI 가 만든 엉뚱한 값도 오류 메시지로 바꿔야 재시도 브리프 끝에 그대로 붙일 수 있다.
"""
from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from .schemacheck import check

SCHEMA_VERSION = "1.0"
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "lecture.schema.json"
TIME_EPS = 1e-6
END_SLACK = 2.0  # 자막 끝 시간이 영상 길이를 살짝 넘는 경우를 허용한다(초)


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
```

- [ ] **Step 6: 통과 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests -v`
Expected: 24 passed (Task 1의 10 + 이번 14)

- [ ] **Step 7: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/schema/lecture.schema.json plugin/video-library/skills/video-library/tests/fixtures/sample_lecture.json plugin/video-library/skills/video-library/scripts/video_library/validate.py plugin/video-library/skills/video-library/tests/test_validate_lecture.py
git commit -m "feat(contract): add lecture.json schema, sample, and lecture/segment checks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: 목차 검사(`check_chapters`)

**Files:**
- Modify: `SKILL_DIR/scripts/video_library/validate.py` (함수 추가, `validate_lecture` 교체)
- Test: `SKILL_DIR/tests/test_validate_chapters.py`

**Interfaces:**
- Consumes: Task 2의 `_at`, `TIME_EPS`, `validate_lecture`
- Produces:
  - `chapter_count_range(duration: float) -> tuple[int, int]`
  - `check_chapters(chapters, n_segments: int, duration: float, segments: list | None = None) -> list[str]` — 경로는 목차 배열 기준 `$`(예: `$[1].segments`). `segments`를 주면 각 목차의 `start`·`end`가 문장 시간과 같은지(필수) 검사한다. Task 6의 `check_outline`이 `segments=None`으로 재사용한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`SKILL_DIR/tests/test_validate_chapters.py`:
```python
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
    # 3단 id("1.1.1")는 스키마 형식에서도 걸리므로, 의미 검사만 보려고 check_chapters 를 직접 부른다
    chapters = sample["chapters"]
    chapters[0]["children"][0]["children"] = flat([(1, 1), (2, 3)], prefix="1.1")
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
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_validate_chapters.py -v`
Expected: FAIL — `ImportError: cannot import name 'chapter_count_range'`

- [ ] **Step 3: 구현 — `validate.py`에 함수 추가**

`validate.py` 맨 아래에 추가:
```python
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
    if not isinstance(chapters, list):
        return ["$: array 이어야 함"]
    errors = []
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
```

- [ ] **Step 4: 구현 — `validate_lecture`에 목차 검사 연결**

`validate.py`의 `validate_lecture`를 아래로 교체:
```python
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
    return errors
```

- [ ] **Step 5: 통과 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests -v`
Expected: 39 passed (24 + 15)

- [ ] **Step 6: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/validate.py plugin/video-library/skills/video-library/tests/test_validate_chapters.py
git commit -m "feat(contract): validate two-level chapter coverage and timing" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: 번역·참조 번호·건너뛴 단계 검사

**Files:**
- Modify: `SKILL_DIR/scripts/video_library/validate.py` (함수 추가, `validate_lecture` 교체)
- Test: `SKILL_DIR/tests/test_validate_refs.py`

**Interfaces:**
- Consumes: Task 2·3의 `check_def`, `_at`, `check_chapters`, `check`, `load_schema`
- Produces:
  - `FAQ_RANGE = (5, 10)`
  - `check_translation_chunk(source_idxs: list[int], items) -> list[str]` — 경로는 번역 배열 기준 `$`
  - `check_glossary(items, n_segments: int) -> list[str]`
  - `check_faq(items, n_segments: int, require_count: bool = True) -> list[str]`
  - `check_mentions(items, n_segments: int) -> list[str]`
  - (Task 6이 AI 결과물 검사에 재사용)

- [ ] **Step 1: 실패하는 테스트 작성**

`SKILL_DIR/tests/test_validate_refs.py`:
```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_validate_refs.py -v`
Expected: FAIL — `ImportError: cannot import name 'check_faq'`

- [ ] **Step 3: 구현 — `validate.py`에 함수 추가**

`validate.py` 위쪽 import에 `import re`를 추가하고, 상수 목록에 `FAQ_RANGE = (5, 10)`를 추가한 뒤 맨 아래에 추가:
```python
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
```

- [ ] **Step 4: 구현 — `validate_lecture` 교체**

```python
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
```

- [ ] **Step 5: 통과 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests -v`
Expected: 55 passed (39 + 16)

- [ ] **Step 6: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/validate.py plugin/video-library/skills/video-library/tests/test_validate_refs.py
git commit -m "feat(contract): validate translations, references, and skipped steps" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: 교정·교열 검사(`check_edits`) — 내용 불변 보장

**Files:**
- Modify: `SKILL_DIR/scripts/video_library/validate.py` (함수 추가)
- Test: `SKILL_DIR/tests/test_validate_edits.py`

**Interfaces:**
- Consumes: `check`, `load_schema`, `_array_of`
- Produces:
  - 상수 `MAX_CHANGE_RATIO = 0.30`
  - `normalize_for_compare(text: str) -> str` — 공백과 유니코드 구두점(P*)·구분자(Z*) 범주 글자를 모두 뺀다
  - `check_edits(originals: dict[int, str], edits, lo: int, hi: int) -> list[str]` — `originals`는 문장 번호 → 원래 자막 문장, `lo..hi`는 이 조각이 고칠 수 있는 범위. 경로는 결과 배열 기준 `$`.

- [ ] **Step 1: 실패하는 테스트 작성**

`SKILL_DIR/tests/test_validate_edits.py`:
```python
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
    assert "$[0]: 바뀐 원문 글자가 40%로 30% 초과 — 내용 변경으로 봄" in check_edits(ORIG, edits, 20, 21)


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
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_validate_edits.py -v`
Expected: FAIL — `ImportError: cannot import name 'check_edits'`

- [ ] **Step 3: 구현**

`validate.py` 위쪽 import에 `import unicodedata`를, 상수 목록에 `MAX_CHANGE_RATIO = 0.30`을 추가하고 맨 아래에 추가:
```python
def normalize_for_compare(text: str) -> str:
    """띄어쓰기·문장부호를 뺀 글자만 남긴다(교열 전후 내용 비교용)."""
    return "".join(ch for ch in text
                   if not (ch.isspace() or unicodedata.category(ch)[0] in "PZ"))


def _changed_len(before: str, after: str) -> int:
    """before 중 실제로 바뀐 글자 수(앞뒤로 같은 글자는 빼고 센다)."""
    p = 0
    while p < min(len(before), len(after)) and before[p] == after[p]:
        p += 1
    s = 0
    while s < min(len(before), len(after)) - p and before[-1 - s] == after[-1 - s]:
        s += 1
    return len(before) - p - s


def check_edits(originals: dict[int, str], edits, lo: int, hi: int) -> list[str]:
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
        errors += _check_one_edit(originals[idx], e, p)
    return errors


def _check_one_edit(original: str, edit: dict, p: str) -> list[str]:
    current = normalize_for_compare(original)
    base = max(1, len(current))
    changed = 0
    errors = []
    for k, c in enumerate(edit["changes"]):
        before, after = normalize_for_compare(c["from"]), normalize_for_compare(c["to"])
        if not before:
            errors.append(f"{p}.changes[{k}]: 띄어쓰기·문장부호만 바꾼 것은 적지 않음")
            continue
        if not after:
            errors.append(f"{p}.changes[{k}]: 삭제는 허용하지 않음(내용 변경)")
            continue
        if before not in current:
            errors.append(f"{p}.changes[{k}]: 바꾸기 전 표기 '{c['from']}'가 원문에 없음")
            continue
        current = current.replace(before, after, 1)
        changed += _changed_len(before, after)
    if errors:
        return errors
    if current != normalize_for_compare(edit["text"]):
        return [f"{p}.text: 적어 둔 교정 말고도 내용이 바뀜(띄어쓰기·문장부호 외 변경은 changes 에 적어야 함)"]
    if changed / base > MAX_CHANGE_RATIO:
        return [f"{p}: 바뀐 원문 글자가 {changed / base:.0%}로 30% 초과 — 내용 변경으로 봄"]
    return []
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests -v`
Expected: 68 passed (55 + 13)

- [ ] **Step 5: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/validate.py plugin/video-library/skills/video-library/tests/test_validate_edits.py
git commit -m "feat(contract): add proofreading checker that forbids undeclared content changes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: AI 단계 결과물 검사(맥락표·목차)

**Files:**
- Modify: `SKILL_DIR/scripts/video_library/validate.py` (함수 추가)
- Test: `SKILL_DIR/tests/test_validate_ai_outputs.py`

**Interfaces:**
- Consumes: `check_def`, `check_chapters`, `check_mentions`, `_at`
- Produces:
  - `check_context(data) -> list[str]` — `build/context.json` 검사
  - `check_outline(data, n_segments: int, duration: float) -> list[str]` — `build/outline.json` 검사(`{"chapters": [...], "mentions": [...]}`, 목차에 start/end 없음)
  - (용어집·FAQ·번역 조각은 Task 4의 `check_glossary`·`check_faq`·`check_translation_chunk`, 교정·교열은 Task 5의 `check_edits`를 쓴다)

- [ ] **Step 1: 실패하는 테스트 작성**

`SKILL_DIR/tests/test_validate_ai_outputs.py`:
```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_validate_ai_outputs.py -v`
Expected: FAIL — `ImportError: cannot import name 'check_context'`

- [ ] **Step 3: 구현**

`validate.py` 맨 아래에 추가:
```python
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
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests -v`
Expected: 75 passed (68 + 7)

- [ ] **Step 5: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/validate.py plugin/video-library/skills/video-library/tests/test_validate_ai_outputs.py
git commit -m "feat(contract): add checkers for context and outline AI outputs" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: `vl.py` 진입점 + `validate` 명령

**Files:**
- Create: `SKILL_DIR/scripts/vl.py`
- Create: `SKILL_DIR/scripts/video_library/cli_validate.py`
- Test: `SKILL_DIR/tests/test_cli.py`

**Interfaces:**
- Consumes: `validate.validate_lecture`
- Produces:
  - `vl.py` 명령 표 `COMMANDS: dict[str, tuple[str, str]]` (이름 → (모듈 경로, 설명)). 각 모듈은 `main(argv: list[str]) -> int` 를 가진다. 이후 단계는 이 표에 한 줄씩 추가한다.
  - 종료 코드: 0 통과/도움말, 1 불합격·JSON 오류, 2 사용법 오류·파일 없음
  - 표준 출력·오류는 실행 시작 시 UTF-8로 재설정한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`SKILL_DIR/tests/test_cli.py`:
```python
import json
import os
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
VL = TESTS_DIR.parent / "scripts" / "vl.py"
SAMPLE = TESTS_DIR / "fixtures" / "sample_lecture.json"


def run(*args, env_extra=None):
    env = dict(os.environ)
    env.update(env_extra or {})
    proc = subprocess.run([sys.executable, str(VL), *args], capture_output=True, env=env)
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


def test_no_command_prints_usage():
    code, out, _ = run()
    assert code == 0
    assert "validate" in out


def test_unknown_command():
    code, _, err = run("nope")
    assert code == 2
    assert "알 수 없는 명령: nope" in err


def test_validate_sample_passes():
    code, out, _ = run("validate", str(SAMPLE))
    assert code == 0
    assert "통과" in out


def test_validate_broken_file_fails(tmp_path):
    doc = json.loads(SAMPLE.read_text(encoding="utf-8"))
    doc["faq"] = doc["faq"][:2]
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    code, out, _ = run("validate", str(path))
    assert code == 1
    assert "불합격 (1건)" in out
    assert "$.faq: FAQ는 5~10개여야 함(현재 2개)" in out


def test_validate_reads_utf8_bom(tmp_path):
    path = tmp_path / "bom.json"
    path.write_text(SAMPLE.read_text(encoding="utf-8"), encoding="utf-8-sig")
    code, out, _ = run("validate", str(path))
    assert code == 0, out


def test_validate_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{ 깨진", encoding="utf-8")
    code, _, err = run("validate", str(path))
    assert code == 1
    assert "JSON 형식 오류" in err


def test_validate_missing_file(tmp_path):
    code, _, err = run("validate", str(tmp_path / "none.json"))
    assert code == 2
    assert "파일 없음" in err


def test_korean_output_survives_cp949_console(tmp_path):
    doc = json.loads(SAMPLE.read_text(encoding="utf-8"))
    doc["lecture"]["field"] = "cooking"
    path = tmp_path / "x.json"
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    code, out, err = run("validate", str(path), env_extra={"PYTHONIOENCODING": "cp949"})
    assert code == 1, err
    assert "허용 값" in out
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_cli.py -v`
Expected: FAIL — 8 failed (vl.py 없음: 종료 코드 2, `can't open file`)

- [ ] **Step 3: 구현**

`SKILL_DIR/scripts/vl.py`:
```python
#!/usr/bin/env python3
"""video-library 단일 진입점.

이 파일이 있는 폴더를 import 경로에 넣으므로 어느 위치에서 실행해도 동작한다.

    python3 <이 파일> validate <lecture.json>

의존성: 파이썬 표준 라이브러리만(이후 단계의 자막 받기만 yt-dlp 라이브러리를 쓴다).
"""
from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

COMMANDS = {
    "validate": ("video_library.cli_validate", "lecture.json 이 약속(스키마 + 의미 규칙)을 지키는지 검사"),
}


def _utf8_console() -> None:
    """Windows 콘솔(cp949)에서도 한국어 출력이 깨지거나 죽지 않게 한다."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def usage() -> None:
    print(__doc__)
    print("사용 가능한 명령:")
    for name, (_, desc) in COMMANDS.items():
        print(f"  {name:<10} {desc}")


def main(argv: list[str]) -> int:
    _utf8_console()
    if not argv or argv[0] in ("-h", "--help", "help"):
        usage()
        return 0
    if argv[0] not in COMMANDS:
        print(f"알 수 없는 명령: {argv[0]}", file=sys.stderr)
        usage()
        return 2
    module = import_module(COMMANDS[argv[0]][0])
    return module.main(argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

`SKILL_DIR/scripts/video_library/cli_validate.py`:
```python
"""vl.py validate — lecture.json 검사 명령."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .validate import validate_lecture


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py validate",
                                 description="lecture.json 이 약속(스키마 + 의미 규칙)을 지키는지 검사한다.")
    ap.add_argument("path", help="검사할 lecture.json 경로")
    args = ap.parse_args(argv)
    try:
        # utf-8-sig: 메모장 등이 붙인 BOM 이 있어도 읽는다
        doc = json.loads(Path(args.path).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        print(f"파일 없음: {args.path}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"JSON 형식 오류: {exc}", file=sys.stderr)
        return 1
    errors = validate_lecture(doc)
    if errors:
        print(f"불합격 ({len(errors)}건)")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("통과")
    return 0
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests -v`
Expected: 83 passed (75 + 8)

- [ ] **Step 5: 손으로 한 번 실행**

Run: `python plugin/video-library/skills/video-library/scripts/vl.py validate plugin/video-library/skills/video-library/tests/fixtures/sample_lecture.json`
Expected: `통과`

- [ ] **Step 6: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/vl.py plugin/video-library/skills/video-library/scripts/video_library/cli_validate.py plugin/video-library/skills/video-library/tests/test_cli.py
git commit -m "feat(contract): add vl.py entry point with validate command" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: API 문서 + 기록 갱신

**Files:**
- Create: `docs/api.md`
- Create: `docs/superpowers/evidence/2026-10-05-stage1-contract.md`
- Modify: `docs/handoff.md` (§1 표·다음 할 일, §3 진행 기록)

**Interfaces:**
- Consumes: 설계서 5.2~5.4, Task 2의 스키마
- Produces: 2·3·4단계 구현자가 읽는 API 약속 문서

- [ ] **Step 1: API 문서 작성**

`docs/api.md`:
````markdown
# video-library 약속 (API·파일 형식)

설계서 5장의 확정본이다. `lecture.json`의 구조는 [`lecture.schema.json`](../plugin/video-library/skills/video-library/scripts/schema/lecture.schema.json), 의미 규칙은 [`validate.py`](../plugin/video-library/skills/video-library/scripts/video_library/validate.py)가 기준이다. 검사: `python plugin/video-library/skills/video-library/scripts/vl.py validate <파일>`.

## 1. `lecture.json` 요약

| 키 | 내용 |
|---|---|
| `schema_version` | `"1.0"` |
| `lecture` | 영상 정보. `id`=`video_id`(유튜브 11자), `field`(dev·finance·science·medical·other), `language`(원문 언어 2자), `mode`=`"text"`, `pipeline.skipped`(glossary·translate·faq 중 실패로 빠진 단계) |
| `segments` | 원문 언어 문장(교정·교열 반영). `idx` 1부터 연속, `start`·`end` 초, `raw` 자막 원문 |
| `translations` | `{언어: [{idx, text}]}` — `segments`와 1:1, 원문 언어 키 없음. 외국어 영상은 `ko` 필수 |
| `corrections` | 교정 기록 `{idx, from, to, kind: term|spelling}` |
| `chapters` | 2단 목차. `segments: [첫 번호, 끝 번호]`, `start`·`end`, `children` |
| `mentions` | 언급 자료 `{kind: link|book|command|other, text, url?, idx}` |
| `glossary` | `{term, definition, analogy?, claim_note?, idx}` |
| `faq` | `{question, answer, evidence: [번호…]}` 5~10개 |

목차·요약·용어집·FAQ·한 줄 소개는 원문 언어와 상관없이 한국어다.

## 2. `index.json` (영상자료실 목록)

최신이 앞인 배열. `lecture.json`에서 자동으로 만든다.

```json
[{"id": "AbCdEfGhIjK", "title": "...", "channel": "...", "duration": 480.0,
  "thumbnail_url": "https://i.ytimg.com/...", "field": "dev", "language": "ko",
  "translations": ["en"], "chapter_count": 2, "processed_at": "2026-10-05T14:03:00+09:00"}]
```

## 3. 진행 상황 (`jobs/<job_id>.json`, Railway `POST /api/jobs/<job_id>` 본문)

```json
{"job_id": "AbCdEfGhIjK-1005-1403", "lecture_id": "AbCdEfGhIjK", "title": "...",
 "status": "running", "started_at": "...", "updated_at": "...",
 "steps": {"fetch": "done", "correct": "running", "translate": "skipped"},
 "detail": "8/19", "error": null}
```

| 단계 키 | 화면 이름 |
|---|---|
| `fetch` | 자막 받기 |
| `preprocess` | 정리 |
| `chunk` | 나누기 |
| `context` | 맥락 파악 |
| `correct` | 교정·교열 |
| `merge` | 합치기 |
| `outline` | 목차·요약 |
| `glossary` | 용어집 |
| `translate` | 번역 |
| `faq` | FAQ |
| `assemble` | 조립 |
| `upload` | 업로드 |

단계 상태: `pending`·`running`·`done`·`failed`·`skipped`. 작업 상태: `running`·`done`·`failed`. 화면은 `done` 작업을 1분 뒤 숨긴다.

## 4. 서버 API (PC 미니 서버와 Railway가 같은 경로)

| 메서드·경로 | 용도 | PC | Railway 권한 |
|---|---|---|---|
| `GET /` | 목록 화면 | ✅ | 누구나 |
| `GET /lecture?id=<id>&t=<초>` | 강의 화면(`t`초부터) | ✅ | 누구나(비공개는 관리자) |
| `GET /api/lectures` | `index.json` 형식 목록 | 전부 | 공개만, 관리자는 전부 + `public` 필드 |
| `GET /api/lectures/<id>` | `lecture.json` | ✅ | 비공개는 관리자만, 아니면 404 |
| `GET /api/search?q=<검색어>&field=<분야>` | 통합 검색 | ✅ | 공개만, 관리자는 전부 |
| `GET /api/jobs` | 진행 중·최근 작업 | ✅ | 관리자 |
| `POST /api/jobs/<job_id>` | 진행 보고 | ❌ | 업로드 토큰 |
| `PUT /api/lectures/<id>` | `lecture.json` 업로드(교체, 공개 상태 유지, 새 강의는 비공개) | ❌ | 업로드 토큰 |
| `PATCH /api/lectures/<id>` | `{"public": true|false}` | ❌ | 관리자 |
| `DELETE /api/lectures/<id>` | 삭제 | ❌ | 관리자 |
| `POST /api/login` · `POST /api/logout` | 관리자 로그인 | ❌ | — |

- PC 미니 서버는 읽기 전용이며 `127.0.0.1`에만 열린다.
- 업로드 토큰: `Authorization: Bearer <토큰>` 헤더. 토큰은 `영상자료실/config.json`(공개 금지)에서 읽는다.
- 관리자 쓰기 요청(`PATCH`·`DELETE`·`logout`)은 세션 쿠키 + `X-Requested-With: video-library` 헤더가 필요하다.
- 업로드 본문은 `application/json`, 최대 20MB. 서버가 `validate_lecture`로 다시 검사한다.

### 검색 응답

```json
{"query": "브랜치", "results": [
  {"id": "AbCdEfGhIjK", "title": "...", "field": "dev",
   "hits": [{"where": "segment", "idx": 7, "start": 230.0, "text": "브랜치는 원본을…", "lang": "ko"},
            {"where": "glossary", "idx": 7, "start": 230.0, "text": "브랜치(Branch)"}]}]}
```

`where` ∈ `title`·`chapter`·`glossary`·`segment`·`translation`. `start`는 해당 문장 시작 시간(제목은 0).

### 오류 응답

모든 오류는 `{"error": "<한국어 이유>", "details": ["<경로>: <이유>", ...]}` (`details`는 검사 실패 때만). 상태 코드: 400 형식·검사 실패, 401 토큰·로그인 없음, 403 권한 없음, 404 없음(비공개 포함), 413 너무 큼, 429 로그인 시도 초과.
````

- [ ] **Step 2: 전체 테스트 실행**

Run: `python -m pytest`
Expected: 83 passed

- [ ] **Step 3: 증거 기록 작성**

`docs/superpowers/evidence/2026-10-05-stage1-contract.md`에 실제로 실행한 명령과 결과(통과 개수, 실패가 있었으면 원인과 조치, 미확인 — 예: Python 3.10 실제 실행은 이 PC에 3.14만 있어 미확인)를 적는다. 형식:
```markdown
# 2026-10-05 1단계(약속) 구현 기록

## 한 일
- (Task별 한 줄)

## 실행한 검증
- `python -m pytest` → (실제 결과 붙여 넣기)
- `python .../vl.py validate .../sample_lecture.json` → (실제 결과)

## 결과
- 성공: …
- 실패: …(없으면 "없음")
- 미확인: Python 3.10에서의 실행(이 PC는 3.14), …
```

- [ ] **Step 4: 인계 문서 갱신**

`docs/handoff.md` §1 표를 아래처럼 고치고 다음 할 일을 바꾼다:
```markdown
| 요구사항·설계 | 설계서 승인(10-05) | [설계서](superpowers/specs/2026-10-05-video-library-design.md) |
| 1단계 약속 | 완료 — 스키마·검사기·샘플·`vl.py validate`·API 문서 | [증거](superpowers/evidence/2026-10-05-stage1-contract.md), [API](api.md) |
| 2단계 이후 | 시작 전 | — |
```
다음 할 일: "2단계(플러그인 처리) 구현 계획 작성 → 사용자 검토". §3 진행 기록 표에 한 줄 추가(날짜·도구·한 일·커밋·근거).

- [ ] **Step 5: 커밋**

```bash
git add docs/api.md docs/superpowers/evidence/2026-10-05-stage1-contract.md docs/handoff.md
git commit -m "docs: add API contract and stage 1 evidence" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
