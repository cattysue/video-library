# video-library 2단계(플러그인 처리) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 유튜브 링크 하나를 받아 자막 받기 → 정리 → 나누기 → (AI) 맥락·교정·교열·목차·용어집·번역·FAQ → 조립까지 처리해, 검사를 통과한 `lecture.json`을 `문서/영상자료실`에 쌓는 플러그인 처리부와 그 절차서(`SKILL.md`)를 만든다.

**Architecture:** 기계 단계는 `vl.py`의 하위 명령(모듈마다 `main(argv) -> int`)이고, 모두 영상자료실 안의 작업 폴더 `lectures/<영상ID>.tmp/`에서 일한다. 판단 단계는 `SKILL.md`의 브리프를 AI가 수행하고 `vl.py check`(1단계 검사기 재사용)를 통과해야 다음으로 간다. 진행 상황은 단계마다 `jobs/<job_id>.json`에 기록하고, 조립이 끝나면 작업 폴더를 원자적으로 `lectures/<영상ID>/`와 바꾸고 `index.json`을 갱신한다. 사용자에게 보일 실패는 `StepError`(한국어 메시지)로 올리고 `vl.py`가 `오류: …`로 출력한다.

**Tech Stack:** Python 3.10+ 표준 라이브러리, `yt-dlp` 파이썬 라이브러리(`fetch`에서만 늦게 import), 개발용 pytest.

**Spec:** [docs/superpowers/specs/2026-10-05-video-library-design.md](../specs/2026-10-05-video-library-design.md) — 4장(영상자료실), 5.1~5.3, 6장(처리 흐름·브리프·검사기·나중 요청), 8.1~8.2, 10장 2단계. 1단계 결과물: [api.md](../../api.md), `validate.py`, `vl.py`.

## Global Constraints

- 명령은 `plugin-app/` 폴더에서 실행한다. 이하 `SKILL_DIR` = `plugin/video-library/skills/video-library`, `PKG` = `SKILL_DIR/scripts/video_library`, `TESTS` = `SKILL_DIR/tests`.
- 런타임은 **표준 라이브러리만** 쓴다. 예외는 `yt_dlp` 하나이며 `fetch.py` 안에서만 늦게 import 한다(다른 명령은 yt-dlp 없이도 동작). Python 3.10 문법만 쓴다.
- 영상자료실 위치: 환경변수 `VL_HOME` → 없으면 Windows는 시스템이 알려주는 실제 "문서" 폴더(OneDrive 이동 포함), 그 밖은 `~/Documents` → 그 아래 `영상자료실`.
- 작업 폴더 = `<영상자료실>/lectures/<영상ID>.tmp/` (`raw/`, `build/`). 완성 폴더 = `<영상자료실>/lectures/<영상ID>/`. 영상 하나에 항목 하나.
- 모든 JSON은 UTF-8로 쓰고(`ensure_ascii=False`), 읽을 때는 BOM을 허용하며 `NaN`·`Infinity`는 거부한다. 파일 쓰기는 `.part` 임시 파일 → `os.replace`로 원자적으로 한다.
- 진행 단계 키(api.md 3절과 같음): `fetch, preprocess, chunk, context, correct, merge, outline, glossary, translate, faq, assemble, upload`. job id = `<영상ID>-<MMDD-HHMM>`(한국 시간). 이번 단계에서 `upload`는 항상 `skipped`(Railway는 4단계).
- 1시간(3600초) 초과 영상은 `fetch` 출력의 `long: true`로 알리고, 진행 여부 확인은 `SKILL.md`가 사용자에게 묻는다.
- 사용자에게 보일 오류는 `config.StepError("한국어 문장")`. `vl.py`가 받아 표준 오류에 `오류: <문장>`, 종료 코드 1.
- 테스트는 **네트워크와 실제 문서 폴더를 절대 쓰지 않는다**: yt-dlp는 가짜 객체로 대신하고, 모든 테스트에서 `VL_HOME`을 한글·공백이 든 임시 경로로 돌린다(autouse).
- 테스트용 자막·강의 데이터는 직접 쓴 샘플만 쓴다(공개 저장소).
- 업로드 토큰·비밀번호는 묻지도 출력하지도 않는다. 설치 명령과 실제 영상 실행은 사용자 승인 후에만.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **영상자료실 경로에 한글·공백이 있는 경우**(예: `D:\내 자료\홍 길동\문서\영상자료실`) — 모든 명령이 그대로 동작해야 한다. → 모든 테스트가 `…/내 문서/영상자료실`을 쓰고, Task 2에 경로 자체를 확인하는 테스트.
2. **같은 영상 재처리 중 검사 실패** — 이미 영상자료실에 있는 강의는 그대로 남아야 한다. → Task 9 테스트.
3. **`index.json`이 깨진 경우**(편집 중 종료, 수동 편집) — 목록을 `lectures/*/lecture.json`에서 다시 만들어야 한다. → Task 9 테스트.
4. **자막 시간이 영상 길이보다 긴 경우** — 문장 시간을 영상 길이로 잘라 1단계 검사(`END_SLACK`)에 걸리지 않아야 한다. → Task 6 테스트.
5. **AI가 쓴 결과 파일이 cp949로 저장됐거나 JSON이 깨진 경우** — `vl.py check`가 예외 대신 "JSON 형식 오류" 메시지를 돌려줘야 재시도 브리프에 붙일 수 있다. → Task 8 테스트.

---

## File Structure

| 파일 | 책임 |
|---|---|
| `PKG/validate.py` (수정) | 교정 검사 보정: 순수 덧붙이기·지우기 거부, 용어 교정 비율 계산, 짧은 문장 분모 하한 |
| `PKG/config.py` | 영상자료실 위치, 작업·완성 폴더 경로, 한국 시간, 원자적 JSON·텍스트 읽기/쓰기, `fmt_time`, `StepError` |
| `PKG/jobs.py` | 진행 기록(`jobs/<job_id>.json`), `track` 문맥 관리자, `vl.py progress` |
| `PKG/youtube.py` | 링크 → 영상ID, 볼 수 있는 영상인지, 자막 트랙 고르기, 정보 요약(네트워크 없음) |
| `PKG/fetch.py` | yt-dlp로 정보·자막 받기, 작업 폴더·요청 기록·job 시작, `vl.py fetch` |
| `PKG/preprocess.py` | json3 → 단어 → 문장, 영상 길이로 자르기, `transcript.md`, `vl.py preprocess` |
| `PKG/chunk.py` | 약 10분 조각 계획·조각 파일·`manifest.json`, `vl.py chunk` |
| `PKG/gates.py` | AI 결과 파일 읽기·검사(조각별 교정·번역, 맥락·목차·용어집·FAQ), `vl.py check` |
| `PKG/merge.py` | 조각별 교정·번역 합치기, `vl.py merge` |
| `PKG/library.py` | 원자적 반영(`commit_lecture`), `index.json` 갱신·재생성, 재작업 열기(`reopen`), `vl.py reopen` |
| `PKG/assemble.py` | 결과물 → `lecture.json`·전사 파일 → 반영 → job 완료, `vl.py assemble` |
| `PKG/doctor.py` | 환경 점검·OS별 설치 명령, `vl.py doctor` |
| `SKILL_DIR/scripts/vl.py` (수정) | 명령 표 확장, `StepError` 출력 |
| `SKILL_DIR/SKILL.md` | 절차서 + AI 브리프 6종 |
| `TESTS/conftest.py` (수정) | autouse 영상자료실 격리, `home` 픽스처, `seed_work` |
| `TESTS/fixtures/auto_ko.json3`, `manual_en.json3` | 직접 쓴 자막 샘플 |

---

### Task 1: 교정 검사 보정 (실제 용어 교정이 통과하도록)

1단계 미룬 사항 처리. 샘플 강의 10번 문장(`기 허브 주소는 github.com 입니다` → `GitHub 주소는 github.com입니다.`)이 현재 규칙에서 33%로 불합격한다(한글 3자 → 영어 6자를 모두 센다). 한→영 용어 교정은 자동자막에서 가장 흔하므로 이대로면 2단계가 동작하지 않는다. 대신 "뜻을 바꾸는 끼워 넣기"는 비율이 아니라 **순수 덧붙이기·지우기 거부** 규칙으로 막는다.

**Files:**
- Modify: `PKG/validate.py` (`MAX_CHANGE_RATIO` 아래 상수 추가, `_changed_len` → `_affix`로 교체, `_check_one_edit` 교체)
- Modify: `TESTS/test_validate_edits.py` (`test_large_insertion_counts_toward_ratio` 교체, 테스트 추가)

**Interfaces:**
- Consumes: 1단계 `normalize_for_compare`, `check_edits(originals: dict[int, str], edits, lo, hi)`
- Produces: 같은 `check_edits` 시그니처. 규칙 변경: (1) 정규화 후 `from == to`이면 "띄어쓰기·문장부호만 바꾼 것은 적지 않음", (2) 앞뒤 공통 글자가 `from` 전체를 덮으면(=덧붙이기만) "원래 글자를 그대로 두고 덧붙이기만 한 변경 — 내용 추가로 봄", `to` 전체를 덮으면(=지우기만) "원래 글자 일부를 지우기만 한 변경 — 내용 삭제로 봄", (3) 비율 비용: `term`은 바뀐 **원래** 글자 수, `spelling`은 지운 쪽·더한 쪽 중 긴 쪽, (4) 분모 = `max(10, 정규화한 원문 길이)`.

- [ ] **Step 1: 실패하는 테스트 작성**

`TESTS/test_validate_edits.py`에서 `test_large_insertion_counts_toward_ratio` 함수 전체를 아래로 바꾸고, 그 아래에 테스트를 추가한다:
```python
def test_pure_insertion_rejected():
    orig = {1: "이 방법은 쓰면 됩니다"}
    edits = [{"idx": 1, "text": "이 방법은 쓰면 절대로 안 됩니다.",
              "changes": [{"from": "쓰면", "to": "쓰면 절대로 안", "kind": "spelling"}]}]
    assert "$[0].changes[0]: 원래 글자를 그대로 두고 덧붙이기만 한 변경 — 내용 추가로 봄" in \
        check_edits(orig, edits, 1, 1)


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
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_validate_edits.py -v`
Expected: FAIL — `test_pure_insertion_rejected`, `test_middle_insertion_rejected`, `test_pure_deletion_rejected`, `test_spacing_only_declared_change_rejected`, `test_korean_to_english_term_in_medium_sentence_passes`, `test_term_fix_in_short_sentence_passes`, `test_sample_lecture_edits_all_pass` 실패(메시지 불일치 또는 30% 초과). 나머지는 통과.

- [ ] **Step 3: 구현**

`PKG/validate.py`에서 `MAX_CHANGE_RATIO = 0.30` 줄 아래에 추가:
```python
MIN_RATIO_BASE = 10  # 아주 짧은 문장은 한 단어만 고쳐도 비율이 커지므로 분모를 최소 10자로 본다
```

`_changed_len` 함수 전체를 아래로 바꾼다:
```python
def _affix(before: str, after: str) -> tuple[int, int]:
    """앞에서부터, 뒤에서부터 같은 글자 수(겹치지 않게)."""
    p = 0
    while p < min(len(before), len(after)) and before[p] == after[p]:
        p += 1
    s = 0
    while s < min(len(before), len(after)) - p and before[-1 - s] == after[-1 - s]:
        s += 1
    return p, s
```

`_check_one_edit` 함수 전체를 아래로 바꾼다:
```python
def _check_one_edit(original: str, edit: dict, p: str) -> list[str]:
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
        if pre + suf >= len(before):
            errors.append(f"{at}: 원래 글자를 그대로 두고 덧붙이기만 한 변경 — 내용 추가로 봄")
            continue
        if pre + suf >= len(after):
            errors.append(f"{at}: 원래 글자 일부를 지우기만 한 변경 — 내용 삭제로 봄")
            continue
        if before not in current:
            errors.append(f"{at}: 바꾸기 전 표기 '{c['from']}'가 원문에 없음")
            continue
        current = current.replace(before, after, 1)
        # 용어 교정(한글 표기 → 영어 이름 등)은 길이가 늘어나는 게 정상이라 바뀐 원래 글자만 센다
        cost = len(before) if c["kind"] == "term" else max(len(before), len(after))
        changed += cost - pre - suf
    if errors:
        return errors
    if current != normalize_for_compare(edit["text"]):
        return [f"{p}.text: 적어 둔 교정 말고도 내용이 바뀜(띄어쓰기·문장부호 외 변경은 changes 에 적어야 함)"]
    if changed / base > MAX_CHANGE_RATIO:
        return [f"{p}: 바뀐 글자가 {changed / base:.0%}로 30% 초과 — 내용 변경으로 봄"]
    return []
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -W error`
Expected: 모두 통과(1단계 90개 − 교체 1 + 새 7 = 96개), 실패 0

- [ ] **Step 5: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/validate.py plugin/video-library/skills/video-library/tests/test_validate_edits.py
git commit -m "fix(contract): accept transliterated term fixes, reject pure insertions and deletions" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `config` — 영상자료실 위치·경로·파일 쓰기·`StepError`

**Files:**
- Create: `PKG/config.py`
- Modify: `SKILL_DIR/scripts/vl.py` (문서 문자열, `StepError` 처리)
- Modify: `TESTS/conftest.py` (autouse 격리, `home` 픽스처)
- Test: `TESTS/test_config.py`

**Interfaces:**
- Produces (`video_library.config`):
  - `class StepError(Exception)`
  - `LIBRARY_NAME = "영상자료실"`, `KST`
  - `documents_dir() -> Path`, `library_home() -> Path`, `ensure_home(home: Path) -> Path`(lectures/·jobs/ 생성 후 home 반환)
  - `work_dir(home, video_id) -> Path` (`lectures/<id>.tmp`), `lecture_dir(home, video_id) -> Path` (`lectures/<id>`)
  - `now_kst() -> datetime`, `fmt_time(sec: float) -> str` (`h:mm:ss`, 초 버림)
  - `read_json(path) -> object` (BOM 허용, NaN 거부, 실패 시 `ValueError` — `UnicodeDecodeError`·`JSONDecodeError` 포함)
  - `write_json(path, data) -> None`, `write_text(path, text: str) -> None` (부모 폴더 생성, 원자적)
- 테스트 픽스처: autouse `_isolated_home`(VL_HOME = `tmp_path/"내 문서"/"영상자료실"`), `home`(ensure_home 된 그 경로)

- [ ] **Step 1: conftest 격리 추가**

`TESTS/conftest.py`의 `sample` 픽스처 아래에 추가:
```python
@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    """모든 테스트에서 영상자료실을 한글·공백이 든 임시 경로로 돌린다 — 실제 문서 폴더를 건드리지 않는다."""
    path = tmp_path / "내 문서" / "영상자료실"
    monkeypatch.setenv("VL_HOME", str(path))
    return path


@pytest.fixture
def home(_isolated_home):
    from video_library.config import ensure_home
    return ensure_home(_isolated_home)
```

- [ ] **Step 2: 실패하는 테스트 작성**

`TESTS/test_config.py`:
```python
import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pytest

from video_library import config
from video_library.config import (StepError, ensure_home, fmt_time, lecture_dir, library_home,
                                  read_json, work_dir, write_json, write_text)

VL = Path(__file__).resolve().parent.parent / "scripts" / "vl.py"


def _load_vl():
    spec = importlib.util.spec_from_file_location("vl_under_test", VL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_vl_home_env_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("VL_HOME", str(tmp_path / "x"))
    assert library_home() == tmp_path / "x"


def test_default_home_is_documents_library(monkeypatch, tmp_path):
    monkeypatch.delenv("VL_HOME")
    monkeypatch.setattr(config, "documents_dir", lambda: tmp_path / "Docs")
    assert library_home() == tmp_path / "Docs" / "영상자료실"


def test_documents_fallback_on_non_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(config.sys, "platform", "linux")
    monkeypatch.setattr(config.Path, "home", lambda: tmp_path)
    assert config.documents_dir() == tmp_path / "Documents"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows 전용")
def test_windows_documents_folder_found():
    found = config._windows_documents()
    assert found is not None and found.is_dir()


def test_ensure_home_with_korean_and_space_path(home):
    assert (home / "lectures").is_dir() and (home / "jobs").is_dir()
    assert " " in str(home) and "영상자료실" in str(home)


def test_work_and_lecture_dirs(home):
    assert work_dir(home, "AbCdEfGhIjK") == home / "lectures" / "AbCdEfGhIjK.tmp"
    assert lecture_dir(home, "AbCdEfGhIjK") == home / "lectures" / "AbCdEfGhIjK"


def test_write_read_json_roundtrip_is_atomic(tmp_path):
    path = tmp_path / "a" / "b.json"
    write_json(path, {"한글": [1, 2.5]})
    assert read_json(path) == {"한글": [1, 2.5]}
    assert "한글" in path.read_text(encoding="utf-8")
    assert not list(tmp_path.rglob("*.part"))


def test_read_json_accepts_bom(tmp_path):
    path = tmp_path / "bom.json"
    path.write_text('{"a": 1}', encoding="utf-8-sig")
    assert read_json(path) == {"a": 1}


def test_read_json_rejects_nan_and_cp949(tmp_path):
    nan = tmp_path / "nan.json"
    nan.write_text('{"a": NaN}', encoding="utf-8")
    with pytest.raises(ValueError):
        read_json(nan)
    cp = tmp_path / "cp.json"
    cp.write_bytes('{"a": "한글"}'.encode("cp949"))
    with pytest.raises(ValueError):
        read_json(cp)


def test_write_text(tmp_path):
    write_text(tmp_path / "t" / "x.md", "가\n")
    assert (tmp_path / "t" / "x.md").read_text(encoding="utf-8") == "가\n"


def test_fmt_time():
    assert fmt_time(0) == "0:00:00"
    assert fmt_time(3725.9) == "1:02:05"


def test_now_kst_has_korean_offset():
    assert config.now_kst().utcoffset().total_seconds() == 9 * 3600


def test_vl_prints_step_error(tmp_path, monkeypatch, capsys):
    (tmp_path / "boom_cmd.py").write_text(
        "from video_library.config import StepError\n\ndef main(argv):\n    raise StepError('자막이 없습니다')\n",
        encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    vl = _load_vl()
    monkeypatch.setitem(vl.COMMANDS, "boom", ("boom_cmd", "테스트"))
    assert vl.main(["boom"]) == 1
    assert "오류: 자막이 없습니다" in capsys.readouterr().err
```

- [ ] **Step 3: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_config.py -v`
Expected: FAIL — `ImportError: cannot import name 'config'`(모듈 없음)

- [ ] **Step 4: 구현**

`PKG/config.py`:
```python
"""영상자료실 위치, 작업 폴더 경로, 한국 시간, 원자적 파일 쓰기. 표준 라이브러리만."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

LIBRARY_NAME = "영상자료실"
KST = timezone(timedelta(hours=9))


class StepError(Exception):
    """사용자에게 그대로 보여줄 한국어 오류. vl.py 가 받아 '오류: …' 로 출력하고 종료 코드 1."""


def _windows_documents() -> Path | None:
    """Windows '문서' 폴더의 실제 위치(OneDrive 로 옮긴 경우 포함). 실패하면 None."""
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

        # FOLDERID_Documents {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
        folder = GUID(0xFDD39AD0, 0x238F, 0x46AF,
                      (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
        out = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(folder), 0, None, ctypes.byref(out)) != 0:
            return None
        try:
            return Path(out.value)
        finally:
            ctypes.windll.ole32.CoTaskMemFree(out)
    except Exception:
        return None


def documents_dir() -> Path:
    if sys.platform == "win32":
        found = _windows_documents()
        if found is not None:
            return found
    return Path.home() / "Documents"


def library_home() -> Path:
    env = os.environ.get("VL_HOME")
    return Path(env) if env else documents_dir() / LIBRARY_NAME


def ensure_home(home: Path) -> Path:
    for sub in ("lectures", "jobs"):
        (home / sub).mkdir(parents=True, exist_ok=True)
    return home


def work_dir(home: Path, video_id: str) -> Path:
    return home / "lectures" / f"{video_id}.tmp"


def lecture_dir(home: Path, video_id: str) -> Path:
    return home / "lectures" / video_id


def now_kst() -> datetime:
    return datetime.now(KST)


def fmt_time(sec: float) -> str:
    s = int(sec)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def _reject_constant(name: str):
    raise ValueError(f"표준 JSON이 아닌 값 {name}")


def read_json(path):
    """UTF-8(BOM 허용) JSON. 형식·인코딩이 틀리면 ValueError."""
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), parse_constant=_reject_constant)


def write_text(path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_text(text, encoding="utf-8")
    os.replace(part, path)


def write_json(path, data) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
```

`SKILL_DIR/scripts/vl.py`의 문서 문자열에서 사용 예 줄을 아래로 바꾼다:
```python
    python3 <이 파일> <명령> [옵션]      (명령 목록은 인자 없이 실행하면 나온다)

결과물은 영상자료실(기본: 문서/영상자료실, 환경변수 VL_HOME 으로 변경)에 쌓인다.
의존성: 파이썬 표준 라이브러리만(자막 받기 fetch 만 yt-dlp 라이브러리를 쓴다).
```
(기존 `    python3 <이 파일> validate <lecture.json>` 줄과 `의존성: …` 줄을 대체)

같은 파일의 `main`에서 마지막 두 줄
```python
    module = import_module(COMMANDS[argv[0]][0])
    return module.main(argv[1:])
```
을 아래로 바꾼다:
```python
    from video_library.config import StepError

    module = import_module(COMMANDS[argv[0]][0])
    try:
        return module.main(argv[1:])
    except StepError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
```

- [ ] **Step 5: 통과 확인**

Run: `python -m pytest -W error`
Expected: 모두 통과(실패 0). Windows가 아니면 `test_windows_documents_folder_found`는 건너뜀.

- [ ] **Step 6: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/config.py plugin/video-library/skills/video-library/scripts/vl.py plugin/video-library/skills/video-library/tests/conftest.py plugin/video-library/skills/video-library/tests/test_config.py
git commit -m "feat(pipeline): add library location, atomic file helpers, and StepError" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `jobs` — 진행 기록 + `vl.py progress`

**Files:**
- Create: `PKG/jobs.py`
- Modify: `SKILL_DIR/scripts/vl.py` (`COMMANDS`에 `progress`)
- Test: `TESTS/test_jobs.py`

**Interfaces:**
- Consumes: `config.StepError, now_kst, read_json, write_json, work_dir, library_home`
- Produces (`video_library.jobs`):
  - `STEPS: tuple[str, ...]`(12개, Global Constraints 순서), `STEP_STATUSES`
  - `initial_steps(translate_needed: bool, upload_enabled: bool) -> dict[str, str]` — 전부 `pending`, `fetch`만 `running`, 필요 없으면 `translate`·`upload`는 `skipped`
  - `start_job(home, lecture_id: str, title: str, steps: dict[str, str], now=None) -> dict`
  - `load_job(home, job_id) -> dict` (없으면 `StepError`)
  - `set_step(home, job_id, step, status, detail="", error=None, now=None) -> dict`
  - `finish_job(home, job_id, outcome: dict[str, str], now=None) -> dict` — `pending`·`running`인 단계만 outcome으로 바꾸고 작업 상태 `done`
  - `current_job_id(home, video_id) -> str | None` — `work_dir/build/request.json`의 `job_id`
  - `track(home, video_id, step)` — 문맥 관리자. 시작 `running`, 정상 종료 `done`, 예외 시 `failed`(+메시지) 후 다시 올림. job이 없으면 아무것도 기록하지 않음. `yield` 값 = job_id 또는 None
  - `main(argv)` = `vl.py progress --video ID --step S [--status running|done|failed|skipped] [--detail D] [--error E]`

- [ ] **Step 1: 실패하는 테스트 작성**

`TESTS/test_jobs.py`:
```python
from datetime import datetime

import pytest

from video_library import jobs
from video_library.config import KST, StepError, read_json, work_dir, write_json

VID = "AbCdEfGhIjK"
NOW = datetime(2026, 10, 5, 14, 3, 7, tzinfo=KST)


def new_job(home, translate=False):
    job = jobs.start_job(home, VID, "샘플", jobs.initial_steps(translate, upload_enabled=False), now=NOW)
    write_json(work_dir(home, VID) / "build" / "request.json", {"video_id": VID, "job_id": job["job_id"]})
    return job


def test_initial_steps():
    steps = jobs.initial_steps(translate_needed=False, upload_enabled=False)
    assert list(steps) == list(jobs.STEPS)
    assert steps["fetch"] == "running" and steps["preprocess"] == "pending"
    assert steps["translate"] == "skipped" and steps["upload"] == "skipped"
    assert jobs.initial_steps(True, True)["translate"] == "pending"


def test_start_job_writes_file(home):
    job = new_job(home)
    assert job["job_id"] == "AbCdEfGhIjK-1005-1403"
    saved = read_json(home / "jobs" / "AbCdEfGhIjK-1005-1403.json")
    assert saved["status"] == "running" and saved["started_at"] == "2026-10-05T14:03:07+09:00"


def test_set_step_and_failure_then_retry(home):
    job = new_job(home)
    jobs.set_step(home, job["job_id"], "correct", "running", detail="3/8")
    assert jobs.load_job(home, job["job_id"])["detail"] == "3/8"
    failed = jobs.set_step(home, job["job_id"], "correct", "failed", error="조각 02 불합격")
    assert failed["status"] == "failed" and failed["error"] == "조각 02 불합격"
    retried = jobs.set_step(home, job["job_id"], "correct", "running")
    assert retried["status"] == "running" and retried["error"] is None


def test_set_step_rejects_unknown(home):
    job = new_job(home)
    with pytest.raises(StepError):
        jobs.set_step(home, job["job_id"], "render", "running")
    with pytest.raises(StepError):
        jobs.set_step(home, job["job_id"], "fetch", "half")


def test_load_missing_job(home):
    with pytest.raises(StepError, match="작업 기록이 없습니다"):
        jobs.load_job(home, "nope")


def test_finish_job_only_overrides_unfinished(home):
    job = new_job(home)
    done = jobs.finish_job(home, job["job_id"], {"fetch": "done", "translate": "done", "glossary": "skipped"})
    assert done["status"] == "done"
    assert done["steps"]["fetch"] == "done"
    assert done["steps"]["translate"] == "skipped"  # 이미 skipped 였으므로 그대로
    assert done["steps"]["glossary"] == "skipped"


def test_track_marks_done(home):
    job = new_job(home)
    with jobs.track(home, VID, "preprocess") as job_id:
        assert job_id == job["job_id"]
        assert jobs.load_job(home, job_id)["steps"]["preprocess"] == "running"
    assert jobs.load_job(home, job["job_id"])["steps"]["preprocess"] == "done"


def test_track_marks_failed_and_reraises(home):
    job = new_job(home)
    with pytest.raises(StepError):
        with jobs.track(home, VID, "chunk"):
            raise StepError("문장이 없습니다")
    saved = jobs.load_job(home, job["job_id"])
    assert saved["steps"]["chunk"] == "failed" and saved["error"] == "문장이 없습니다"


def test_track_without_job_records_nothing(home):
    with jobs.track(home, VID, "chunk") as job_id:
        assert job_id is None
    assert not list((home / "jobs").iterdir())


def test_progress_command(home, capsys):
    job = new_job(home)
    assert jobs.main(["--video", VID, "--step", "correct", "--detail", "2/5"]) == 0
    assert jobs.load_job(home, job["job_id"])["steps"]["correct"] == "running"
    assert "correct: running (2/5)" in capsys.readouterr().out


def test_progress_without_job(home):
    with pytest.raises(StepError, match="진행 중인 작업이 없습니다"):
        jobs.main(["--video", VID, "--step", "correct"])
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_jobs.py -v`
Expected: FAIL — `ImportError: cannot import name 'jobs'`

- [ ] **Step 3: 구현**

`PKG/jobs.py`:
```python
"""작업 진행 기록(영상자료실/jobs/<job_id>.json). 목록 화면의 진행 카드가 이 파일을 읽는다."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path

from .config import StepError, library_home, now_kst, read_json, work_dir, write_json

STEPS = ("fetch", "preprocess", "chunk", "context", "correct", "merge",
         "outline", "glossary", "translate", "faq", "assemble", "upload")
STEP_STATUSES = ("pending", "running", "done", "failed", "skipped")


def job_path(home: Path, job_id: str) -> Path:
    return Path(home) / "jobs" / f"{job_id}.json"


def initial_steps(translate_needed: bool, upload_enabled: bool) -> dict[str, str]:
    steps = {s: "pending" for s in STEPS}
    steps["fetch"] = "running"
    if not translate_needed:
        steps["translate"] = "skipped"
    if not upload_enabled:
        steps["upload"] = "skipped"
    return steps


def start_job(home: Path, lecture_id: str, title: str, steps: dict[str, str], now=None) -> dict:
    now = now or now_kst()
    stamp = now.isoformat(timespec="seconds")
    job = {"job_id": f"{lecture_id}-{now:%m%d-%H%M}", "lecture_id": lecture_id, "title": title,
           "status": "running", "started_at": stamp, "updated_at": stamp,
           "steps": dict(steps), "detail": "", "error": None}
    write_json(job_path(home, job["job_id"]), job)
    return job


def load_job(home: Path, job_id: str) -> dict:
    path = job_path(home, job_id)
    if not path.exists():
        raise StepError(f"작업 기록이 없습니다: {job_id}")
    return read_json(path)


def set_step(home: Path, job_id: str, step: str, status: str, detail: str = "",
             error: str | None = None, now=None) -> dict:
    if step not in STEPS:
        raise StepError(f"알 수 없는 단계: {step}")
    if status not in STEP_STATUSES:
        raise StepError(f"알 수 없는 상태: {status}")
    job = load_job(home, job_id)
    job["steps"][step] = status
    job["detail"] = detail
    if status == "failed":
        job["status"] = "failed"
        job["error"] = error or f"{step} 단계 실패"
    elif job["status"] == "failed" and status in ("running", "done"):
        job["status"] = "running"  # 실패한 단계부터 다시 실행하는 중
        job["error"] = None
    job["updated_at"] = (now or now_kst()).isoformat(timespec="seconds")
    write_json(job_path(home, job_id), job)
    return job


def finish_job(home: Path, job_id: str, outcome: dict[str, str], now=None) -> dict:
    job = load_job(home, job_id)
    for step, status in outcome.items():
        if job["steps"].get(step) in ("pending", "running"):
            job["steps"][step] = status
    job["status"] = "done"
    job["error"] = None
    job["detail"] = ""
    job["updated_at"] = (now or now_kst()).isoformat(timespec="seconds")
    write_json(job_path(home, job_id), job)
    return job


def current_job_id(home: Path, video_id: str) -> str | None:
    path = work_dir(home, video_id) / "build" / "request.json"
    if not path.exists():
        return None
    try:
        return read_json(path).get("job_id")
    except (ValueError, AttributeError):
        return None


@contextmanager
def track(home: Path, video_id: str, step: str):
    """기계 단계 하나를 감싸 running → done/failed 를 기록한다. job 이 없으면 기록하지 않는다."""
    job_id = current_job_id(home, video_id)
    if job_id:
        set_step(home, job_id, step, "running")
    try:
        yield job_id
    except BaseException as exc:
        if job_id:
            msg = str(exc) if isinstance(exc, StepError) else f"{type(exc).__name__}: {exc}"
            set_step(home, job_id, step, "failed", error=msg[:300])
        raise
    if job_id:
        set_step(home, job_id, step, "done")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py progress", description="AI 판단 단계의 진행 상황을 기록한다.")
    ap.add_argument("--video", required=True, help="영상 ID")
    ap.add_argument("--step", required=True, choices=STEPS)
    ap.add_argument("--status", default="running", choices=STEP_STATUSES)
    ap.add_argument("--detail", default="", help='예: "3/8"')
    ap.add_argument("--error", default=None)
    a = ap.parse_args(argv)
    home = library_home()
    job_id = current_job_id(home, a.video)
    if not job_id:
        raise StepError(f"진행 중인 작업이 없습니다: {a.video} (먼저 fetch 를 실행하세요)")
    set_step(home, job_id, a.step, a.status, a.detail, a.error)
    print(f"{a.step}: {a.status}" + (f" ({a.detail})" if a.detail else ""))
    return 0
```

`SKILL_DIR/scripts/vl.py`의 `COMMANDS`에 줄 추가:
```python
    "progress": ("video_library.jobs", "AI 판단 단계의 진행 상황 기록"),
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -W error`
Expected: 모두 통과(실패 0)

- [ ] **Step 5: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/jobs.py plugin/video-library/skills/video-library/scripts/vl.py plugin/video-library/skills/video-library/tests/test_jobs.py
git commit -m "feat(pipeline): add job progress records and progress command" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `youtube` — 링크 해석·영상 상태·자막 트랙 고르기 (네트워크 없음)

**Files:**
- Create: `PKG/youtube.py`
- Test: `TESTS/test_youtube.py`

**Interfaces:**
- Consumes: `config.StepError`
- Produces (`video_library.youtube`):
  - `parse_video_id(url: str) -> str` — `watch?v=`, `youtu.be/`, `/shorts/`, `/live/`, `/embed/`, `m.`·`music.` 도메인, ID만 입력도 허용. 재생목록만 있는 링크·유튜브가 아닌 링크·잘못된 ID는 `StepError`
  - `check_available(info: dict) -> None` — 진행 중·예정 라이브, 비공개·회원 전용·로그인 필요, 연령 제한(18)은 `StepError`
  - `normalize_lang(code: str | None) -> str | None` — `"en-US"`→`"en"`, 두 글자 아니면 None
  - `choose_caption(info: dict, lang_override: str | None = None) -> dict` — `{"lang", "kind": "manual"|"auto", "track"}`. 원문 언어의 사람이 만든 자막 > 자동자막(`<lang>-orig` 먼저). json3 형식이 있는 트랙만.
  - `trim_info(info: dict, caption: dict) -> dict` — `{"id","title","channel","duration","thumbnail_url","language","caption_kind","caption_track","source_url"}`(다른 키는 버림)

- [ ] **Step 1: 실패하는 테스트 작성**

`TESTS/test_youtube.py`:
```python
import pytest

from video_library.config import StepError
from video_library.youtube import check_available, choose_caption, normalize_lang, parse_video_id, trim_info

VID = "AbCdEfGhIjK"
J3 = [{"ext": "vtt", "url": "x"}, {"ext": "json3", "url": "y"}]


@pytest.mark.parametrize("url", [
    f"https://www.youtube.com/watch?v={VID}",
    f"https://youtube.com/watch?v={VID}&list=PL123&index=2",
    f"https://youtu.be/{VID}?si=abc",
    f"https://www.youtube.com/shorts/{VID}",
    f"https://www.youtube.com/live/{VID}?feature=share",
    f"https://www.youtube.com/embed/{VID}",
    f"https://m.youtube.com/watch?v={VID}",
    f"https://music.youtube.com/watch?v={VID}",
    f"youtu.be/{VID}",
    VID,
])
def test_parse_video_id(url):
    assert parse_video_id(url) == VID


def test_playlist_only_rejected():
    with pytest.raises(StepError, match="재생목록"):
        parse_video_id("https://www.youtube.com/playlist?list=PL123")


def test_non_youtube_rejected():
    with pytest.raises(StepError, match="유튜브 링크가 아닙니다"):
        parse_video_id("https://vimeo.com/123")


def test_bad_id_rejected():
    with pytest.raises(StepError, match="영상 ID"):
        parse_video_id("https://www.youtube.com/watch?v=short")


@pytest.mark.parametrize("info, word", [
    ({"live_status": "is_live"}, "라이브"),
    ({"live_status": "is_upcoming"}, "라이브"),
    ({"availability": "private"}, "비공개"),
    ({"availability": "needs_auth"}, "비공개"),
    ({"age_limit": 18}, "연령 제한"),
])
def test_unavailable_videos(info, word):
    with pytest.raises(StepError, match=word):
        check_available(info)


def test_available_video_passes():
    check_available({"live_status": "was_live", "availability": "public", "age_limit": 0})


def test_normalize_lang():
    assert normalize_lang("en-US") == "en"
    assert normalize_lang("KO") == "ko"
    assert normalize_lang("fil") is None
    assert normalize_lang(None) is None


def test_manual_caption_preferred():
    info = {"language": "ko", "subtitles": {"ko": J3, "live_chat": J3}, "automatic_captions": {"ko": J3}}
    assert choose_caption(info) == {"lang": "ko", "kind": "manual", "track": "ko"}


def test_auto_caption_prefers_orig_track():
    info = {"language": "en", "automatic_captions": {"en": J3, "en-orig": J3, "ko": J3}}
    assert choose_caption(info) == {"lang": "en", "kind": "auto", "track": "en-orig"}


def test_language_from_single_orig_track():
    info = {"automatic_captions": {"ja-orig": J3, "ko": J3}}
    assert choose_caption(info)["lang"] == "ja"


def test_lang_override():
    info = {"language": "ko", "automatic_captions": {"en": J3}}
    assert choose_caption(info, "EN-us") == {"lang": "en", "kind": "auto", "track": "en"}


def test_bad_lang_override():
    with pytest.raises(StepError, match="두 글자"):
        choose_caption({"language": "ko"}, "english")


def test_unknown_language():
    with pytest.raises(StepError, match="--lang"):
        choose_caption({"automatic_captions": {"en": J3, "ko": J3}})


def test_no_captions():
    with pytest.raises(StepError, match="자막이 없어"):
        choose_caption({"language": "ko", "automatic_captions": {"en": J3}})


def test_tracks_without_json3_ignored():
    with pytest.raises(StepError, match="자막이 없어"):
        choose_caption({"language": "ko", "subtitles": {"ko": [{"ext": "vtt"}]}})


def test_trim_info_keeps_only_needed_keys():
    info = {"id": VID, "title": "제목", "uploader": "업로더", "duration": 600, "formats": [{"url": "secret"}],
            "thumbnail": "https://example.com/t.jpg"}
    meta = trim_info(info, {"lang": "ko", "kind": "auto", "track": "ko"})
    assert meta == {"id": VID, "title": "제목", "channel": "업로더", "duration": 600.0,
                    "thumbnail_url": f"https://i.ytimg.com/vi/{VID}/hqdefault.jpg", "language": "ko",
                    "caption_kind": "auto", "caption_track": "ko",
                    "source_url": f"https://www.youtube.com/watch?v={VID}"}
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_youtube.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'video_library.youtube'`

- [ ] **Step 3: 구현**

`PKG/youtube.py`:
```python
"""유튜브 링크·영상 정보 해석(네트워크 없음). yt-dlp 가 준 info 딕셔너리만 읽는다."""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from .config import StepError

_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_BLOCKED = ("private", "premium_only", "subscriber_only", "needs_auth")


def parse_video_id(url: str) -> str:
    url = url.strip()
    if _ID.match(url):
        return url
    parts = urlsplit(url if "://" in url else "https://" + url)
    host = (parts.hostname or "").lower()
    for prefix in ("www.", "m."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    if host == "youtu.be":
        candidate = parts.path.lstrip("/").split("/")[0]
    elif host in ("youtube.com", "music.youtube.com"):
        if parts.path == "/watch":
            candidate = (parse_qs(parts.query).get("v") or [""])[0]
        elif parts.path.startswith(("/shorts/", "/live/", "/embed/")):
            candidate = parts.path.split("/")[2]
        elif parts.path == "/playlist":
            raise StepError("재생목록 링크는 지원하지 않습니다. 영상 하나씩 넣어 주세요.")
        else:
            candidate = ""
    else:
        raise StepError(f"유튜브 링크가 아닙니다: {url}")
    if not _ID.match(candidate):
        raise StepError("유튜브 링크에서 영상 ID를 찾지 못했습니다. 영상 주소를 다시 확인해 주세요.")
    return candidate


def check_available(info: dict) -> None:
    if info.get("live_status") in ("is_live", "is_upcoming"):
        raise StepError("진행 중이거나 예정된 라이브 방송은 처리할 수 없습니다. 방송이 끝난 뒤 다시 시도하세요.")
    if info.get("availability") in _BLOCKED:
        raise StepError("비공개·회원 전용·로그인이 필요한 영상은 처리할 수 없습니다.")
    if (info.get("age_limit") or 0) >= 18:
        raise StepError("연령 제한 영상은 처리할 수 없습니다.")


def normalize_lang(code: str | None) -> str | None:
    if not code:
        return None
    head = code.split("-")[0].lower()
    return head if len(head) == 2 and head.isalpha() else None


def _has_json3(formats) -> bool:
    return any(isinstance(f, dict) and f.get("ext") == "json3" for f in formats or [])


def choose_caption(info: dict, lang_override: str | None = None) -> dict:
    subs = {k: v for k, v in (info.get("subtitles") or {}).items() if k != "live_chat"}
    autos = info.get("automatic_captions") or {}
    lang = None
    if lang_override:
        lang = normalize_lang(lang_override)
        if not lang:
            raise StepError("--lang 은 두 글자 언어 코드여야 합니다(예: ko, en).")
    if not lang:
        lang = normalize_lang(info.get("language"))
    if not lang:
        origs = [k for k in autos if k.endswith("-orig")]
        if len(origs) == 1:
            lang = normalize_lang(origs[0][: -len("-orig")])
    if not lang and len(subs) == 1:
        lang = normalize_lang(next(iter(subs)))
    if not lang:
        raise StepError("영상의 원래 언어를 알 수 없습니다. --lang ko 처럼 언어를 지정해 다시 실행하세요.")
    for key in sorted(subs):
        if normalize_lang(key) == lang and _has_json3(subs[key]):
            return {"lang": lang, "kind": "manual", "track": key}
    for key in (f"{lang}-orig", lang):
        if key in autos and _has_json3(autos[key]):
            return {"lang": lang, "kind": "auto", "track": key}
    raise StepError("이 영상에는 사용할 수 있는 자막이 없어 처리할 수 없습니다.")


def trim_info(info: dict, caption: dict) -> dict:
    vid = info["id"]
    return {
        "id": vid,
        "title": info.get("title") or vid,
        "channel": info.get("channel") or info.get("uploader") or "",
        "duration": float(info.get("duration") or 0),
        "thumbnail_url": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
        "language": caption["lang"],
        "caption_kind": caption["kind"],
        "caption_track": caption["track"],
        "source_url": f"https://www.youtube.com/watch?v={vid}",
    }
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -W error`
Expected: 모두 통과(실패 0)

- [ ] **Step 5: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/youtube.py plugin/video-library/skills/video-library/tests/test_youtube.py
git commit -m "feat(pipeline): parse YouTube links and choose caption tracks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `fetch` — yt-dlp로 정보·자막 받기 + 작업 시작

**Files:**
- Create: `PKG/fetch.py`
- Create: `TESTS/fixtures/auto_ko.json3`
- Modify: `SKILL_DIR/scripts/vl.py` (`COMMANDS`에 `fetch`)
- Test: `TESTS/test_fetch.py`

**Interfaces:**
- Consumes: `config.*`, `jobs.initial_steps/start_job/set_step`, `youtube.*`
- Produces (`video_library.fetch`):
  - `LONG_VIDEO_SEC = 3600`
  - `base_opts() -> dict` — 조용히·받기만 안 함. deno가 없고 node가 있으면 `js_runtimes = {"node": {}}`(yt-dlp는 deno만 기본으로 켬)
  - `fetch(url, home, lang=None, translate_en=False, ydl_factory=None, now=None) -> dict` — 반환 `{"video_id","job_id","work_dir","title","duration","language","caption_kind","long","translate"}`. 작업 폴더의 `build/`는 새로 비운다(fetch = 처음부터 다시). 쓰는 파일: `raw/info.json`(trim_info), `raw/source.json3`, `build/request.json`(`{"video_id","url","job_id","translate_en","lang_override"}`), `jobs/<job_id>.json`(fetch `done`)
  - `ydl_factory(opts) -> 문맥 관리자 객체` (`extract_info(url, download=False)`, `download([url])`). 기본은 `yt_dlp.YoutubeDL`
  - `main(argv)` = `vl.py fetch <링크> [--lang xx] [--translate-en]` → 결과 JSON 출력

- [ ] **Step 1: 자막 샘플 작성**

`TESTS/fixtures/auto_ko.json3` (자동자막 형식을 흉내 낸 직접 쓴 샘플):
```json
{"wireMagic": "pb3", "events": [
  {"tStartMs": 0, "dDurationMs": 4000, "id": 1, "wpWinPosId": 1, "wsWinStyleId": 1},
  {"tStartMs": 500, "dDurationMs": 3500, "wWinId": 1, "segs": [{"utf8": "안녕하세요", "acAsrConf": 0}, {"utf8": " 오늘은", "tOffsetMs": 800}, {"utf8": " 깃을", "tOffsetMs": 1500}, {"utf8": " 배워요", "tOffsetMs": 2100}]},
  {"tStartMs": 4000, "dDurationMs": 100, "wWinId": 1, "aAppend": 1, "segs": [{"utf8": "\n"}]},
  {"tStartMs": 5500, "dDurationMs": 3000, "wWinId": 1, "segs": [{"utf8": "[음악]"}]},
  {"tStartMs": 9000, "dDurationMs": 2500, "wWinId": 1, "segs": [{"utf8": "기"}, {"utf8": " 허브를", "tOffsetMs": 400}, {"utf8": " 씁니다", "tOffsetMs": 900}]}
]}
```

- [ ] **Step 2: 실패하는 테스트 작성**

`TESTS/test_fetch.py`:
```python
import json
from datetime import datetime
from pathlib import Path

import pytest

from video_library import fetch as fetch_mod
from video_library.config import KST, StepError, read_json, work_dir, write_json

VID = "AbCdEfGhIjK"
URL = f"https://youtu.be/{VID}"
NOW = datetime(2026, 10, 5, 14, 3, tzinfo=KST)
CAPTION = (Path(__file__).resolve().parent / "fixtures" / "auto_ko.json3").read_text(encoding="utf-8")
J3 = [{"ext": "json3", "url": "y"}]


def info(**over):
    base = {"id": VID, "title": "깃 기초", "channel": "샘플 채널", "duration": 480, "language": "ko",
            "automatic_captions": {"ko": J3}, "live_status": "not_live", "availability": "public"}
    base.update(over)
    return base


class FakeYDL:
    def __init__(self, opts, info, caption, write=True):
        self.opts, self.info, self.caption, self.write = opts, info, caption, write

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=False):
        assert download is False
        return self.info

    def download(self, urls):
        if self.write:
            track = self.opts["subtitleslangs"][0]
            Path(self.opts["outtmpl"].replace("%(ext)s", f"{track}.json3")).write_text(self.caption, encoding="utf-8")
        return 0


def factory(info_dict, write=True, seen=None):
    def make(opts):
        if seen is not None:
            seen.append(opts)
        return FakeYDL(opts, info_dict, CAPTION, write)
    return make


def test_fetch_creates_work_folder_and_job(home):
    out = fetch_mod.fetch(URL, home, ydl_factory=factory(info()), now=NOW)
    work = work_dir(home, VID)
    assert out == {"video_id": VID, "job_id": f"{VID}-1005-1403", "work_dir": str(work), "title": "깃 기초",
                   "duration": 480.0, "language": "ko", "caption_kind": "auto", "long": False, "translate": False}
    assert read_json(work / "raw" / "source.json3")["wireMagic"] == "pb3"
    assert read_json(work / "raw" / "info.json")["caption_track"] == "ko"
    assert read_json(work / "build" / "request.json") == {
        "video_id": VID, "url": f"https://www.youtube.com/watch?v={VID}", "job_id": f"{VID}-1005-1403",
        "translate_en": False, "lang_override": None}
    job = read_json(home / "jobs" / f"{VID}-1005-1403.json")
    assert job["steps"]["fetch"] == "done" and job["steps"]["translate"] == "skipped"


def test_foreign_video_needs_translation(home):
    foreign = info(language="en", automatic_captions={"en-orig": J3})
    out = fetch_mod.fetch(URL, home, ydl_factory=factory(foreign), now=NOW)
    assert out["translate"] is True and out["language"] == "en"
    assert read_json(home / "jobs" / f"{VID}-1005-1403.json")["steps"]["translate"] == "pending"


def test_translate_en_on_korean_video(home):
    out = fetch_mod.fetch(URL, home, translate_en=True, ydl_factory=factory(info()), now=NOW)
    assert out["translate"] is True


def test_refetch_clears_build(home):
    stale = work_dir(home, VID) / "build" / "chunks" / "01.edits.json"
    write_json(stale, [])
    fetch_mod.fetch(URL, home, ydl_factory=factory(info()), now=NOW)
    assert not stale.exists()


def test_long_video_flag(home):
    out = fetch_mod.fetch(URL, home, ydl_factory=factory(info(duration=4000)), now=NOW)
    assert out["long"] is True


def test_missing_subtitle_file(home):
    with pytest.raises(StepError, match="자막 파일을 받지 못했습니다"):
        fetch_mod.fetch(URL, home, ydl_factory=factory(info(), write=False), now=NOW)


def test_private_video_rejected_before_download(home):
    with pytest.raises(StepError, match="비공개"):
        fetch_mod.fetch(URL, home, ydl_factory=factory(info(availability="private")), now=NOW)
    assert not list((home / "jobs").iterdir())


def test_zero_duration_rejected(home):
    with pytest.raises(StepError, match="영상 길이"):
        fetch_mod.fetch(URL, home, ydl_factory=factory(info(duration=None)), now=NOW)


def test_http_403_explained(home):
    def boom(opts):
        raise RuntimeError("ERROR: unable to download: HTTP Error 403: Forbidden")
    with pytest.raises(StepError, match="403"):
        fetch_mod.fetch(URL, home, ydl_factory=boom, now=NOW)


def test_missing_yt_dlp_explained(home):
    def missing(opts):
        raise ModuleNotFoundError("No module named 'yt_dlp'")
    with pytest.raises(StepError, match="vl.py doctor"):
        fetch_mod.fetch(URL, home, ydl_factory=missing, now=NOW)


def test_node_enabled_when_deno_missing(monkeypatch):
    monkeypatch.setattr(fetch_mod.shutil, "which", lambda name: "C:/node.exe" if name == "node" else None)
    assert fetch_mod.base_opts()["js_runtimes"] == {"node": {}}
    monkeypatch.setattr(fetch_mod.shutil, "which", lambda name: "C:/deno.exe")
    assert "js_runtimes" not in fetch_mod.base_opts()


def test_subtitle_download_options(home):
    seen = []
    fetch_mod.fetch(URL, home, ydl_factory=factory(info(), seen=seen), now=NOW)
    sub = seen[1]
    assert sub["skip_download"] is True and sub["writeautomaticsub"] is True and sub["writesubtitles"] is False
    assert sub["subtitleslangs"] == ["ko"] and sub["subtitlesformat"] == "json3"


def test_main_prints_json(home, monkeypatch, capsys):
    monkeypatch.setattr(fetch_mod, "_default_ydl_factory", factory(info()))
    assert fetch_mod.main([URL]) == 0
    assert json.loads(capsys.readouterr().out)["video_id"] == VID
```

- [ ] **Step 3: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_fetch.py -v`
Expected: FAIL — `ImportError: cannot import name 'fetch'`

- [ ] **Step 4: 구현**

`PKG/fetch.py`:
```python
"""1단계: yt-dlp 파이썬 라이브러리로 영상 정보·자막(json3)을 받고 작업을 시작한다. 영상 파일은 받지 않는다."""
from __future__ import annotations

import argparse
import json
import os
import shutil

from .config import StepError, ensure_home, library_home, work_dir, write_json
from .jobs import initial_steps, set_step, start_job
from .youtube import check_available, choose_caption, parse_video_id, trim_info

LONG_VIDEO_SEC = 3600


def _default_ydl_factory(opts: dict):
    import yt_dlp  # 이 명령에서만 필요하므로 늦게 import 한다

    return yt_dlp.YoutubeDL(opts)


def base_opts() -> dict:
    opts = {"quiet": True, "no_warnings": True, "noprogress": True, "skip_download": True}
    if shutil.which("deno") is None and shutil.which("node"):
        opts["js_runtimes"] = {"node": {}}  # yt-dlp 는 deno 만 기본으로 켠다
    return opts


def _explain(exc: Exception) -> str:
    msg = str(exc)
    low = msg.lower()
    if isinstance(exc, ModuleNotFoundError):
        return "yt-dlp 라이브러리가 설치되어 있지 않습니다. 'vl.py doctor' 를 실행해 설치 명령을 확인하세요."
    if "403" in msg:
        return ("유튜브가 요청을 막았습니다(HTTP 403). yt-dlp 를 최신으로 업데이트한 뒤 다시 시도하세요"
                "('vl.py doctor' 가 명령을 알려 줍니다).")
    if "private" in low or "sign in" in low or "members" in low:
        return "비공개·회원 전용·로그인이 필요한 영상은 처리할 수 없습니다."
    if "unavailable" in low:
        return "영상을 찾을 수 없거나 볼 수 없는 영상입니다."
    return f"영상 정보를 받지 못했습니다: {msg[:200]}"


def fetch(url: str, home, lang: str | None = None, translate_en: bool = False,
          ydl_factory=None, now=None) -> dict:
    factory = ydl_factory or _default_ydl_factory
    video_id = parse_video_id(url)
    ensure_home(home)
    source_url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with factory(base_opts()) as ydl:
            info = ydl.extract_info(source_url, download=False)
    except Exception as exc:
        raise StepError(_explain(exc)) from exc
    check_available(info)
    caption = choose_caption(info, lang)
    meta = trim_info(info, caption)
    if meta["duration"] <= 0:
        raise StepError("영상 길이를 알 수 없습니다. 잠시 뒤 다시 시도하세요.")

    work = work_dir(home, video_id)
    raw, build = work / "raw", work / "build"
    raw.mkdir(parents=True, exist_ok=True)
    if build.exists():
        shutil.rmtree(build)  # fetch 는 '처음부터 다시' — 앞 작업의 중간 결과를 섞지 않는다
    build.mkdir(parents=True)
    for old in raw.glob("source*.json3"):
        old.unlink()

    sub_opts = base_opts() | {
        "writesubtitles": caption["kind"] == "manual",
        "writeautomaticsub": caption["kind"] == "auto",
        "subtitleslangs": [caption["track"]],
        "subtitlesformat": "json3",
        "outtmpl": str(raw / "source.%(ext)s"),
    }
    try:
        with factory(sub_opts) as ydl:
            ydl.download([source_url])
    except Exception as exc:
        raise StepError(_explain(exc)) from exc
    produced = sorted(raw.glob("source.*.json3"))
    if not produced:
        raise StepError("자막 파일을 받지 못했습니다. 잠시 뒤 다시 시도하거나 'vl.py doctor' 로 환경을 확인하세요.")
    os.replace(produced[0], raw / "source.json3")
    write_json(raw / "info.json", meta)

    translate_needed = meta["language"] != "ko" or translate_en
    job = start_job(home, video_id, meta["title"], initial_steps(translate_needed, upload_enabled=False), now=now)
    write_json(build / "request.json", {"video_id": video_id, "url": source_url, "job_id": job["job_id"],
                                        "translate_en": translate_en, "lang_override": lang})
    set_step(home, job["job_id"], "fetch", "done", now=now)
    return {"video_id": video_id, "job_id": job["job_id"], "work_dir": str(work), "title": meta["title"],
            "duration": meta["duration"], "language": meta["language"], "caption_kind": meta["caption_kind"],
            "long": meta["duration"] > LONG_VIDEO_SEC, "translate": translate_needed}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py fetch", description="유튜브 영상의 정보와 자막을 받고 작업을 시작한다.")
    ap.add_argument("url", help="유튜브 영상 링크")
    ap.add_argument("--lang", default=None, help="영상 언어를 직접 지정(예: ko, en)")
    ap.add_argument("--translate-en", action="store_true", help="한국어 영상의 전사를 영어로도 번역")
    a = ap.parse_args(argv)
    result = fetch(a.url, library_home(), lang=a.lang, translate_en=a.translate_en,
                   ydl_factory=_default_ydl_factory)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
```

`SKILL_DIR/scripts/vl.py`의 `COMMANDS`에 줄 추가:
```python
    "fetch": ("video_library.fetch", "유튜브 영상 정보·자막 받기, 작업 시작"),
```

- [ ] **Step 5: 통과 확인**

Run: `python -m pytest -W error`
Expected: 모두 통과(실패 0)

- [ ] **Step 6: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/fetch.py plugin/video-library/skills/video-library/scripts/vl.py plugin/video-library/skills/video-library/tests/fixtures/auto_ko.json3 plugin/video-library/skills/video-library/tests/test_fetch.py
git commit -m "feat(pipeline): fetch captions with yt-dlp and start a job" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: `preprocess` — 자막 → 문장

**Files:**
- Create: `PKG/preprocess.py`
- Create: `TESTS/fixtures/manual_en.json3`
- Modify: `SKILL_DIR/scripts/vl.py` (`COMMANDS`에 `preprocess`)
- Test: `TESTS/test_preprocess.py`

**Interfaces:**
- Consumes: `config.*`, `jobs.track`
- Produces (`video_library.preprocess`):
  - `words_from_json3(data) -> list[dict]` — `[{"text","start","end"}]`(초, 소수 3자리). 공백만 있는 조각·`[음악]` 같은 소리 표시는 버림
  - `build_sentences(words) -> list[dict]` — `[{"idx","start","end","raw"}]`. 끊는 기준: 단어가 `. ? ! 。 ？ ！`로 끝남 / 다음 단어까지 1초 이상 쉼 / 20초 이상이고 0.3초 이상 쉼 / 30초 이상
  - `clamp_to_duration(sentences, duration) -> list[dict]`
  - `render_transcript(sentences) -> str` — `# 전사 — 문장 N개` + `[번호] [h:mm:ss] 문장` 줄
  - `preprocess(home, video_id) -> dict` — `build/sentences.json`, `build/transcript.md` 작성, 반환 `{"sentences","words","duration"}`
  - `main(argv)` = `vl.py preprocess --video ID`

- [ ] **Step 1: 자막 샘플 작성**

`TESTS/fixtures/manual_en.json3` (사람이 만든 자막 형식을 흉내 낸 직접 쓴 샘플):
```json
{"events": [
  {"tStartMs": 1000, "dDurationMs": 2000, "segs": [{"utf8": "Hello everyone."}]},
  {"tStartMs": 3000, "dDurationMs": 2500, "segs": [{"utf8": "Today we talk\nabout quantum"}]},
  {"tStartMs": 5500, "dDurationMs": 2000, "segs": [{"utf8": "entanglement."}]}
]}
```

- [ ] **Step 2: 실패하는 테스트 작성**

`TESTS/test_preprocess.py`:
```python
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
```

- [ ] **Step 3: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_preprocess.py -v`
Expected: FAIL — `ImportError: cannot import name 'preprocess'`

- [ ] **Step 4: 구현**

`PKG/preprocess.py`:
```python
"""2단계: 자막(json3) → 단어 → 문장(build/sentences.json) + 전사(build/transcript.md)."""
from __future__ import annotations

import argparse
import json
import re

from .config import StepError, fmt_time, library_home, read_json, work_dir, write_json, write_text
from .jobs import track

GAP_SEC = 1.0        # 이만큼 쉬면 문장을 끊는다
SOFT_MAX_SEC = 20.0  # 이보다 길면 짧은 쉼(SOFT_GAP_SEC)에서도 끊는다
SOFT_GAP_SEC = 0.3
HARD_MAX_SEC = 30.0  # 쉼이 없어도 이 길이에서는 끊는다
END_PUNCT = (".", "?", "!", "。", "？", "！")
_SOUND_TAG = re.compile(r"^\[[^\]]*\]$")  # [음악] [Music] [박수]


def words_from_json3(data) -> list[dict]:
    words = []
    events = data.get("events") if isinstance(data, dict) else None
    for ev in events or []:
        segs = ev.get("segs") if isinstance(ev, dict) else None
        if not segs or "tStartMs" not in ev:
            continue
        t0 = ev["tStartMs"] / 1000
        t_end = t0 + (ev.get("dDurationMs") or 0) / 1000
        pieces = []
        for seg in segs:
            text = " ".join((seg.get("utf8") or "").split())
            if not text or _SOUND_TAG.match(text):
                continue
            pieces.append((t0 + (seg.get("tOffsetMs") or 0) / 1000, text))
        for i, (start, text) in enumerate(pieces):
            end = pieces[i + 1][0] if i + 1 < len(pieces) else t_end
            words.append({"text": text, "start": round(start, 3), "end": round(max(end, start), 3)})
    words.sort(key=lambda w: w["start"])
    return words


def build_sentences(words: list[dict]) -> list[dict]:
    sentences: list[dict] = []
    current: list[dict] = []

    def flush():
        if current:
            sentences.append({"idx": len(sentences) + 1, "start": current[0]["start"],
                              "end": current[-1]["end"], "raw": " ".join(w["text"] for w in current)})
            current.clear()

    for i, w in enumerate(words):
        current.append(w)
        if i + 1 == len(words):
            break
        gap = words[i + 1]["start"] - w["end"]
        length = w["end"] - current[0]["start"]
        if (w["text"].endswith(END_PUNCT) or gap >= GAP_SEC
                or (length >= SOFT_MAX_SEC and gap >= SOFT_GAP_SEC) or length >= HARD_MAX_SEC):
            flush()
    flush()
    return sentences


def clamp_to_duration(sentences: list[dict], duration: float) -> list[dict]:
    """자막 시간이 영상 길이를 넘지 않게 자른다."""
    for s in sentences:
        s["end"] = min(s["end"], duration)
        s["start"] = min(s["start"], s["end"])
    return sentences


def render_transcript(sentences: list[dict]) -> str:
    lines = [f"# 전사 — 문장 {len(sentences)}개", ""]
    lines += [f"[{s['idx']}] [{fmt_time(s['start'])}] {s['raw']}" for s in sentences]
    return "\n".join(lines) + "\n"


def preprocess(home, video_id: str) -> dict:
    work = work_dir(home, video_id)
    src = work / "raw" / "source.json3"
    if not src.exists():
        raise StepError("자막 파일이 없습니다. 먼저 fetch 를 실행하세요.")
    try:
        data = read_json(src)
        info = read_json(work / "raw" / "info.json")
    except (ValueError, FileNotFoundError) as exc:
        raise StepError(f"자막 또는 영상 정보를 읽지 못했습니다: {exc}") from exc
    words = words_from_json3(data)
    sentences = clamp_to_duration(build_sentences(words), float(info["duration"]))
    if not sentences:
        raise StepError("자막에서 문장을 하나도 만들지 못했습니다(소리 표시만 있는 자막일 수 있습니다).")
    write_json(work / "build" / "sentences.json", sentences)
    write_text(work / "build" / "transcript.md", render_transcript(sentences))
    return {"sentences": len(sentences), "words": len(words), "duration": float(info["duration"])}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py preprocess", description="자막을 문장 목록으로 정리한다.")
    ap.add_argument("--video", required=True, help="영상 ID")
    a = ap.parse_args(argv)
    home = library_home()
    with track(home, a.video, "preprocess"):
        result = preprocess(home, a.video)
    print(json.dumps(result, ensure_ascii=False))
    return 0
```

`SKILL_DIR/scripts/vl.py`의 `COMMANDS`에 줄 추가:
```python
    "preprocess": ("video_library.preprocess", "자막 → 문장 목록·전사"),
```

- [ ] **Step 5: 통과 확인**

Run: `python -m pytest -W error`
Expected: 모두 통과(실패 0)

- [ ] **Step 6: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/preprocess.py plugin/video-library/skills/video-library/scripts/vl.py plugin/video-library/skills/video-library/tests/fixtures/manual_en.json3 plugin/video-library/skills/video-library/tests/test_preprocess.py
git commit -m "feat(pipeline): turn json3 captions into timed sentences" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: `chunk` — 약 10분 조각

**Files:**
- Create: `PKG/chunk.py`
- Modify: `TESTS/conftest.py` (`VIDEO_ID`, `sample_doc`, `seed_work` 추가)
- Modify: `SKILL_DIR/scripts/vl.py` (`COMMANDS`에 `chunk`)
- Test: `TESTS/test_chunk.py`

**Interfaces:**
- Consumes: `config.*`, `jobs.track/start_job/initial_steps`
- Produces (`video_library.chunk`):
  - `CHUNK_SEC = 600.0`, `CONTEXT_SENTENCES = 3`
  - `plan_chunks(sentences, chunk_sec=CHUNK_SEC) -> list[tuple[int, int]]` — 문장 번호 범위. 마지막 조각이 `chunk_sec/4`보다 짧으면 앞 조각에 붙임
  - `render_chunk(sentences, lo, hi, n, total) -> str` — 앞 CONTEXT(최대 3문장, 없으면 `(없음)`) / `## EDITABLE RANGE (lo~hi)` / 뒤 CONTEXT. 줄 형식 `[번호] [h:mm:ss] 문장`
  - `chunk(home, video_id, chunk_sec=CHUNK_SEC) -> dict` — `build/chunks/`를 새로 만들고 `NN.md`, `manifest.json`(`{"sentences": N, "chunks": [{"n","file","lo","hi","start","end"}]}`) 작성. 반환 `{"chunks","sentences"}`
  - `main(argv)` = `vl.py chunk --video ID`
- conftest 도우미(이후 Task가 씀): `VIDEO_ID = "AbCdEfGhIjK"`, `sample_doc() -> dict`, `seed_work(home, doc=None, translate_en=False) -> Path` — 샘플 강의로 "preprocess가 끝난 상태"의 작업 폴더(`raw/info.json`, `build/request.json`, `build/sentences.json`, job)를 만든다

- [ ] **Step 1: conftest 도우미 추가**

`TESTS/conftest.py` 맨 아래에 추가:
```python
VIDEO_ID = "AbCdEfGhIjK"


def sample_doc() -> dict:
    return json.loads((FIXTURES / "sample_lecture.json").read_text(encoding="utf-8"))


def seed_work(home, doc=None, translate_en=False):
    """샘플 강의로 'preprocess 가 끝난 상태'의 작업 폴더를 만든다."""
    from video_library import config, jobs

    doc = doc or sample_doc()
    lec = doc["lecture"]
    vid = lec["video_id"]
    work = config.work_dir(home, vid)
    config.write_json(work / "raw" / "info.json", {
        "id": vid, "title": lec["title"], "channel": lec["channel"], "duration": lec["duration"],
        "thumbnail_url": lec["thumbnail_url"], "language": lec["language"],
        "caption_kind": lec["pipeline"]["caption_kind"], "caption_track": lec["language"],
        "source_url": lec["source_url"]})
    translate_needed = lec["language"] != "ko" or translate_en
    job = jobs.start_job(home, vid, lec["title"], jobs.initial_steps(translate_needed, upload_enabled=False))
    config.write_json(work / "build" / "request.json", {
        "video_id": vid, "url": lec["source_url"], "job_id": job["job_id"],
        "translate_en": translate_en, "lang_override": None})
    config.write_json(work / "build" / "sentences.json", [
        {"idx": s["idx"], "start": s["start"], "end": s["end"], "raw": s["raw"]} for s in doc["segments"]])
    return work
```

- [ ] **Step 2: 실패하는 테스트 작성**

`TESTS/test_chunk.py`:
```python
import pytest

from conftest import VIDEO_ID, seed_work
from video_library import chunk as ck
from video_library.config import StepError, read_json, work_dir, write_json
from video_library.jobs import current_job_id, load_job


def make_sents(n, step=60.0):
    return [{"idx": i, "start": (i - 1) * step, "end": i * step - 1, "raw": f"문장 {i}"} for i in range(1, n + 1)]


def test_plan_chunks_regular():
    assert ck.plan_chunks(make_sents(25)) == [(1, 10), (11, 20), (21, 25)]


def test_plan_chunks_merges_short_tail():
    assert ck.plan_chunks(make_sents(22)) == [(1, 10), (11, 22)]


def test_plan_chunks_short_video():
    assert ck.plan_chunks(make_sents(5)) == [(1, 5)]


def test_render_chunk_context_and_range():
    text = ck.render_chunk(make_sents(25), 11, 20, 2, 3)
    assert text.startswith("# 조각 02/03 — 문장 11~20\n")
    assert "## EDITABLE RANGE (11~20)" in text
    assert "[8] [0:07:00] 문장 8" in text and "[10] [0:09:00] 문장 10" in text
    assert "[7] " not in text
    assert "[21] [0:20:00] 문장 21" in text and "[23] " in text and "[24] " not in text


def test_render_first_chunk_has_no_before_context():
    text = ck.render_chunk(make_sents(25), 1, 10, 1, 3)
    before = text.split("## EDITABLE RANGE")[0]
    assert "(없음)" in before


def test_chunk_writes_files_and_marks_job(home):
    work = seed_work(home)
    write_json(work / "build" / "chunks" / "09.edits.json", [])
    assert ck.chunk(home, VIDEO_ID, chunk_sec=200) == {"chunks": 2, "sentences": 12}
    manifest = read_json(work / "build" / "chunks" / "manifest.json")
    assert [(c["lo"], c["hi"]) for c in manifest["chunks"]] == [(1, 6), (7, 12)]
    assert manifest["chunks"][1] == {"n": 2, "file": "02.md", "lo": 7, "hi": 12, "start": 230.0, "end": 478.0}
    assert (work / "build" / "chunks" / "01.md").exists()
    assert not (work / "build" / "chunks" / "09.edits.json").exists()


def test_chunk_main_tracks_step(home):
    seed_work(home)
    assert ck.main(["--video", VIDEO_ID]) == 0
    job = load_job(home, current_job_id(home, VIDEO_ID))
    assert job["steps"]["chunk"] == "done"


def test_chunk_without_sentences(home):
    with pytest.raises(StepError, match="preprocess"):
        ck.chunk(home, VIDEO_ID)
```

- [ ] **Step 3: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_chunk.py -v`
Expected: FAIL — `ImportError: cannot import name 'chunk'`

- [ ] **Step 4: 구현**

`PKG/chunk.py`:
```python
"""3단계: 문장 목록을 약 10분 조각으로 나눈다(문장 경계 유지). AI 교정·번역이 조각 단위로 일한다."""
from __future__ import annotations

import argparse
import json
import shutil

from .config import StepError, fmt_time, library_home, read_json, work_dir, write_json, write_text
from .jobs import track

CHUNK_SEC = 600.0
CONTEXT_SENTENCES = 3


def plan_chunks(sentences: list[dict], chunk_sec: float = CHUNK_SEC) -> list[tuple[int, int]]:
    ranges = []
    lo = sentences[0]["idx"]
    start0 = sentences[0]["start"]
    for s in sentences:
        if s["start"] - start0 >= chunk_sec and s["idx"] > lo:
            ranges.append((lo, s["idx"] - 1))
            lo, start0 = s["idx"], s["start"]
    ranges.append((lo, sentences[-1]["idx"]))
    if len(ranges) > 1 and sentences[-1]["end"] - sentences[ranges[-1][0] - 1]["start"] < chunk_sec / 4:
        last = ranges.pop()
        ranges[-1] = (ranges[-1][0], last[1])
    return ranges


def _line(s: dict) -> str:
    return f"[{s['idx']}] [{fmt_time(s['start'])}] {s['raw']}"


def render_chunk(sentences: list[dict], lo: int, hi: int, n: int, total: int) -> str:
    before = sentences[max(0, lo - 1 - CONTEXT_SENTENCES):lo - 1]
    body = sentences[lo - 1:hi]
    after = sentences[hi:hi + CONTEXT_SENTENCES]
    lines = [f"# 조각 {n:02d}/{total:02d} — 문장 {lo}~{hi}", "",
             "## CONTEXT (읽기 전용 — 고치지 마세요)"]
    lines += [_line(s) for s in before] or ["(없음)"]
    lines += ["", f"## EDITABLE RANGE ({lo}~{hi})"]
    lines += [_line(s) for s in body]
    lines += ["", "## CONTEXT (읽기 전용 — 고치지 마세요)"]
    lines += [_line(s) for s in after] or ["(없음)"]
    return "\n".join(lines) + "\n"


def chunk(home, video_id: str, chunk_sec: float = CHUNK_SEC) -> dict:
    work = work_dir(home, video_id)
    src = work / "build" / "sentences.json"
    if not src.exists():
        raise StepError("문장 목록이 없습니다. 먼저 preprocess 를 실행하세요.")
    sentences = read_json(src)
    cdir = work / "build" / "chunks"
    if cdir.exists():
        shutil.rmtree(cdir)  # 조각이 바뀌면 앞 조각의 AI 결과는 맞지 않으므로 함께 지운다
    ranges = plan_chunks(sentences, chunk_sec)
    entries = []
    for n, (lo, hi) in enumerate(ranges, start=1):
        write_text(cdir / f"{n:02d}.md", render_chunk(sentences, lo, hi, n, len(ranges)))
        entries.append({"n": n, "file": f"{n:02d}.md", "lo": lo, "hi": hi,
                        "start": sentences[lo - 1]["start"], "end": sentences[hi - 1]["end"]})
    write_json(cdir / "manifest.json", {"sentences": len(sentences), "chunks": entries})
    return {"chunks": len(ranges), "sentences": len(sentences)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py chunk", description="문장 목록을 약 10분 조각으로 나눈다.")
    ap.add_argument("--video", required=True, help="영상 ID")
    a = ap.parse_args(argv)
    home = library_home()
    with track(home, a.video, "chunk"):
        result = chunk(home, a.video)
    print(json.dumps(result, ensure_ascii=False))
    return 0
```

`SKILL_DIR/scripts/vl.py`의 `COMMANDS`에 줄 추가:
```python
    "chunk": ("video_library.chunk", "약 10분 조각으로 나누기"),
```

- [ ] **Step 5: 통과 확인**

Run: `python -m pytest -W error`
Expected: 모두 통과(실패 0)

- [ ] **Step 6: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/chunk.py plugin/video-library/skills/video-library/scripts/vl.py plugin/video-library/skills/video-library/tests/conftest.py plugin/video-library/skills/video-library/tests/test_chunk.py
git commit -m "feat(pipeline): split sentences into ten-minute chunks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: `gates`·`merge` — AI 결과 검사와 합치기

**Files:**
- Create: `PKG/gates.py`, `PKG/merge.py`
- Modify: `SKILL_DIR/scripts/vl.py` (`COMMANDS`에 `check`, `merge`)
- Test: `TESTS/test_gates_merge.py`

**Interfaces:**
- Consumes: `config.*`, `jobs.track`, `validate.check_edits/check_translation_chunk/check_context/check_outline/check_glossary/check_faq`
- Produces (`video_library.gates`):
  - `OUTPUT_KINDS = ("context", "outline", "glossary", "faq")`
  - `load_json_file(path) -> tuple[object | None, list[str]]` — 없음 → `["<파일명>: 파일이 없습니다"]`, 형식·인코딩 오류 → `["<파일명>: JSON 형식 오류 — …"]`
  - `sentences(work) -> list[dict]`, `manifest(work) -> dict`, `chunk_range(work, n) -> tuple[int, int]` (없으면 `StepError`)
  - `check_chunk_edits(work, n) -> list[str]` — `originals`는 **정수 키** `{idx: raw}`
  - `check_chunk_translation(work, n, lang) -> list[str]`
  - `check_output(work, kind) -> list[str]` — glossary는 빈 배열이면 `"$: 용어가 하나도 없음"`
  - `main(argv)` = `vl.py check --video ID --kind edits|translation|context|outline|glossary|faq [--chunk N] [--lang L]` → `통과`(0) 또는 `불합격 (k건)`+목록(1)
- Produces (`video_library.merge`):
  - `merge_edits(work) -> dict` — 모든 조각 검사 후 `build/sentences.corrected.json`(`[{idx,start,end,text,raw}]`, 안 고친 문장은 `text = raw`)와 `build/corrections.json` 작성. 불합격 조각이 있으면 `StepError`(조각 번호별 목록). 반환 `{"chunks","edited","corrections"}`
  - `merge_translation(work, lang) -> dict` — `build/translations.<lang>.json` 작성. 반환 `{"lang","sentences"}`
  - `main(argv)` = `vl.py merge --video ID --kind edits|translation [--lang L]` (job 단계: edits → `merge`, translation → `translate`)

- [ ] **Step 1: 실패하는 테스트 작성**

`TESTS/test_gates_merge.py`:
```python
import pytest

from conftest import VIDEO_ID, sample_doc, seed_work
from video_library import chunk as ck
from video_library import gates, merge
from video_library.config import StepError, read_json, write_json
from video_library.jobs import current_job_id, load_job


def prepared(home):
    work = seed_work(home)
    ck.chunk(home, VIDEO_ID, chunk_sec=200)  # 조각 (1~6), (7~12)
    return work


def write_edits(work, doc, n, lo, hi):
    changes = {}
    for c in doc["corrections"]:
        changes.setdefault(c["idx"], []).append({"from": c["from"], "to": c["to"], "kind": c["kind"]})
    edits = [{"idx": s["idx"], "text": s["text"], "changes": changes.get(s["idx"], [])}
             for s in doc["segments"] if lo <= s["idx"] <= hi and s["text"] != s["raw"]]
    write_json(work / "build" / "chunks" / f"{n:02d}.edits.json", edits)


def write_translation(work, doc, n, lo, hi, lang="en"):
    items = [it for it in doc["translations"]["en"] if lo <= it["idx"] <= hi]
    write_json(work / "build" / "chunks" / f"{n:02d}.{lang}.json", items)


def test_check_chunk_edits_pass(home):
    work = prepared(home)
    write_edits(work, sample_doc(), 2, 7, 12)
    assert gates.check_chunk_edits(work, 2) == []


def test_check_chunk_edits_missing_file(home):
    work = prepared(home)
    assert gates.check_chunk_edits(work, 1) == ["01.edits.json: 파일이 없습니다"]


def test_check_chunk_edits_out_of_range(home):
    work = prepared(home)
    write_json(work / "build" / "chunks" / "01.edits.json", [{"idx": 9, "text": "x", "changes": []}])
    assert any("담당 범위 1~6 밖" in e for e in gates.check_chunk_edits(work, 1))


def test_cp949_or_broken_json_reports_not_crashes(home):
    work = prepared(home)
    (work / "build" / "chunks" / "01.edits.json").write_bytes('[{"idx": 1, "text": "한글"}]'.encode("cp949"))
    assert gates.check_chunk_edits(work, 1)[0].startswith("01.edits.json: JSON 형식 오류")
    (work / "build" / "chunks" / "02.edits.json").write_text("[{깨짐", encoding="utf-8")
    assert gates.check_chunk_edits(work, 2)[0].startswith("02.edits.json: JSON 형식 오류")


def test_unknown_chunk(home):
    work = prepared(home)
    with pytest.raises(StepError, match="조각 7번"):
        gates.check_chunk_edits(work, 7)


def test_merge_edits_reproduces_sample(home):
    work = prepared(home)
    doc = sample_doc()
    write_edits(work, doc, 1, 1, 6)
    write_edits(work, doc, 2, 7, 12)
    assert merge.merge_edits(work) == {"chunks": 2, "edited": 12, "corrections": 2}
    corrected = read_json(work / "build" / "sentences.corrected.json")
    assert [s["text"] for s in corrected] == [s["text"] for s in doc["segments"]]
    assert read_json(work / "build" / "corrections.json") == doc["corrections"]


def test_merge_edits_unedited_sentence_keeps_raw(home):
    work = prepared(home)
    write_json(work / "build" / "chunks" / "01.edits.json", [])
    write_json(work / "build" / "chunks" / "02.edits.json", [])
    merge.merge_edits(work)
    corrected = read_json(work / "build" / "sentences.corrected.json")
    assert corrected[0]["text"] == corrected[0]["raw"]


def test_merge_edits_reports_bad_chunks(home):
    work = prepared(home)
    write_edits(work, sample_doc(), 1, 1, 6)
    with pytest.raises(StepError, match="조각 02: 02.edits.json: 파일이 없습니다"):
        merge.merge_edits(work)


def test_translation_check_and_merge(home):
    work = prepared(home)
    doc = sample_doc()
    write_translation(work, doc, 1, 1, 6)
    write_translation(work, doc, 2, 7, 12)
    assert gates.check_chunk_translation(work, 1, "en") == []
    assert merge.merge_translation(work, "en") == {"lang": "en", "sentences": 12}
    assert read_json(work / "build" / "translations.en.json") == doc["translations"]["en"]


def test_translation_bad_lang(home):
    work = prepared(home)
    with pytest.raises(StepError, match="언어 코드"):
        gates.check_chunk_translation(work, 1, "english")


def test_check_outputs(home):
    work = prepared(home)
    doc = sample_doc()
    build = work / "build"
    write_json(build / "context.json", {"field": "dev", "one_liner": doc["lecture"]["one_liner"],
                                        "topic_summary": "요약", "key_terms": [], "proper_nouns": []})
    strip = lambda chs: [{**{k: v for k, v in c.items() if k not in ("start", "end")}, "children": strip(c["children"])} for c in chs]
    write_json(build / "outline.json", {"chapters": strip(doc["chapters"]), "mentions": doc["mentions"]})
    write_json(build / "glossary.json", [])
    write_json(build / "faq.json", doc["faq"])
    assert gates.check_output(work, "context") == []
    assert gates.check_output(work, "outline") == []
    assert gates.check_output(work, "glossary") == ["$: 용어가 하나도 없음"]
    assert gates.check_output(work, "faq") == []


def test_check_command_exit_codes(home, capsys):
    work = prepared(home)
    assert gates.main(["--video", VIDEO_ID, "--kind", "edits", "--chunk", "1"]) == 1
    assert "불합격 (1건)" in capsys.readouterr().out
    write_edits(work, sample_doc(), 1, 1, 6)
    assert gates.main(["--video", VIDEO_ID, "--kind", "edits", "--chunk", "1"]) == 0
    assert "통과" in capsys.readouterr().out


def test_check_command_requires_chunk(home):
    prepared(home)
    with pytest.raises(StepError, match="--chunk"):
        gates.main(["--video", VIDEO_ID, "--kind", "edits"])


def test_merge_command_marks_job(home):
    work = prepared(home)
    doc = sample_doc()
    write_edits(work, doc, 1, 1, 6)
    write_edits(work, doc, 2, 7, 12)
    assert merge.main(["--video", VIDEO_ID, "--kind", "edits"]) == 0
    assert load_job(home, current_job_id(home, VIDEO_ID))["steps"]["merge"] == "done"
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_gates_merge.py -v`
Expected: FAIL — `ImportError: cannot import name 'gates'`

- [ ] **Step 3: 구현**

`PKG/gates.py`:
```python
"""AI 판단 단계 결과 파일의 검사 관문. 1단계 검사기를 작업 폴더 파일에 연결한다."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from .config import StepError, library_home, read_json, work_dir
from .validate import (check_context, check_edits, check_faq, check_glossary, check_outline,
                       check_translation_chunk)

OUTPUT_KINDS = ("context", "outline", "glossary", "faq")
_LANG = re.compile(r"^[a-z]{2}$")


def load_json_file(path: Path):
    path = Path(path)
    if not path.exists():
        return None, [f"{path.name}: 파일이 없습니다"]
    try:
        return read_json(path), []
    except ValueError as exc:
        return None, [f"{path.name}: JSON 형식 오류 — {exc}"]


def _must(path: Path, hint: str):
    data, errors = load_json_file(path)
    if errors:
        raise StepError(f"{errors[0]} ({hint})")
    return data


def sentences(work: Path) -> list[dict]:
    return _must(work / "build" / "sentences.json", "먼저 preprocess 를 실행하세요")


def manifest(work: Path) -> dict:
    return _must(work / "build" / "chunks" / "manifest.json", "먼저 chunk 를 실행하세요")


def chunk_range(work: Path, n: int) -> tuple[int, int]:
    for c in manifest(work)["chunks"]:
        if c["n"] == n:
            return c["lo"], c["hi"]
    raise StepError(f"조각 {n}번이 없습니다. manifest.json 의 조각 번호를 확인하세요.")


def _check_lang(lang: str) -> None:
    if not _LANG.match(lang or ""):
        raise StepError("--lang 은 두 글자 언어 코드여야 합니다(예: ko, en).")


def check_chunk_edits(work: Path, n: int) -> list[str]:
    lo, hi = chunk_range(work, n)
    data, errors = load_json_file(work / "build" / "chunks" / f"{n:02d}.edits.json")
    if errors:
        return errors
    originals = {s["idx"]: s["raw"] for s in sentences(work) if lo <= s["idx"] <= hi}  # 정수 키
    return check_edits(originals, data, lo, hi)


def check_chunk_translation(work: Path, n: int, lang: str) -> list[str]:
    _check_lang(lang)
    lo, hi = chunk_range(work, n)
    data, errors = load_json_file(work / "build" / "chunks" / f"{n:02d}.{lang}.json")
    if errors:
        return errors
    return check_translation_chunk(list(range(lo, hi + 1)), data)


def check_output(work: Path, kind: str) -> list[str]:
    if kind not in OUTPUT_KINDS:
        raise StepError(f"알 수 없는 검사 종류: {kind}")
    data, errors = load_json_file(work / "build" / f"{kind}.json")
    if errors:
        return errors
    n = len(sentences(work))
    duration = float(_must(work / "raw" / "info.json", "먼저 fetch 를 실행하세요")["duration"])
    if kind == "context":
        return check_context(data)
    if kind == "outline":
        return check_outline(data, n, duration)
    if kind == "glossary":
        return ["$: 용어가 하나도 없음"] if data == [] else check_glossary(data, n)
    return check_faq(data, n, require_count=True)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py check", description="AI 판단 단계의 결과 파일을 검사한다.")
    ap.add_argument("--video", required=True, help="영상 ID")
    ap.add_argument("--kind", required=True, choices=("edits", "translation") + OUTPUT_KINDS)
    ap.add_argument("--chunk", type=int, default=None, help="조각 번호(edits·translation)")
    ap.add_argument("--lang", default=None, help="번역 언어(translation)")
    a = ap.parse_args(argv)
    work = work_dir(library_home(), a.video)
    if not work.exists():
        raise StepError(f"작업 폴더가 없습니다: {work} (먼저 fetch 를 실행하세요)")
    if a.kind in ("edits", "translation"):
        if a.chunk is None:
            raise StepError("edits·translation 검사에는 --chunk 조각 번호가 필요합니다.")
        errors = (check_chunk_edits(work, a.chunk) if a.kind == "edits"
                  else check_chunk_translation(work, a.chunk, a.lang or ""))
    else:
        errors = check_output(work, a.kind)
    if errors:
        print(f"불합격 ({len(errors)}건)")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("통과")
    return 0
```

`PKG/merge.py`:
```python
"""조각별 AI 결과(교정·교열, 번역)를 검사한 뒤 하나로 합친다."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import StepError, library_home, read_json, work_dir, write_json
from .gates import _check_lang, check_chunk_edits, check_chunk_translation, manifest, sentences
from .jobs import track


def _all_or_fail(work: Path, checker, label: str) -> list[dict]:
    chunks = manifest(work)["chunks"]
    problems = []
    for c in chunks:
        problems += [f"조각 {c['n']:02d}: {e}" for e in checker(c["n"])]
    if problems:
        raise StepError(f"{label} 결과에 문제가 있습니다. 해당 조각만 다시 실행하세요:\n" + "\n".join(problems))
    return chunks


def merge_edits(work: Path) -> dict:
    chunks = _all_or_fail(work, lambda n: check_chunk_edits(work, n), "교정·교열")
    corrected = [{"idx": s["idx"], "start": s["start"], "end": s["end"], "text": s["raw"], "raw": s["raw"]}
                 for s in sentences(work)]
    corrections = []
    edited = 0
    for c in chunks:
        for e in read_json(work / "build" / "chunks" / f"{c['n']:02d}.edits.json"):
            corrected[e["idx"] - 1]["text"] = e["text"]
            edited += 1
            corrections += [{"idx": e["idx"], "from": ch["from"], "to": ch["to"], "kind": ch["kind"]}
                            for ch in e["changes"]]
    write_json(work / "build" / "sentences.corrected.json", corrected)
    write_json(work / "build" / "corrections.json", corrections)
    return {"chunks": len(chunks), "edited": edited, "corrections": len(corrections)}


def merge_translation(work: Path, lang: str) -> dict:
    _check_lang(lang)
    chunks = _all_or_fail(work, lambda n: check_chunk_translation(work, n, lang), "번역")
    items = []
    for c in chunks:
        items += read_json(work / "build" / "chunks" / f"{c['n']:02d}.{lang}.json")
    write_json(work / "build" / f"translations.{lang}.json", items)
    return {"lang": lang, "sentences": len(items)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py merge", description="조각별 교정·교열 또는 번역 결과를 합친다.")
    ap.add_argument("--video", required=True, help="영상 ID")
    ap.add_argument("--kind", required=True, choices=("edits", "translation"))
    ap.add_argument("--lang", default=None, help="번역 언어(translation)")
    a = ap.parse_args(argv)
    home = library_home()
    work = work_dir(home, a.video)
    if not work.exists():
        raise StepError(f"작업 폴더가 없습니다: {work} (먼저 fetch 를 실행하세요)")
    if a.kind == "edits":
        with track(home, a.video, "merge"):
            result = merge_edits(work)
    else:
        with track(home, a.video, "translate"):
            result = merge_translation(work, a.lang or "")
    print(json.dumps(result, ensure_ascii=False))
    return 0
```

`SKILL_DIR/scripts/vl.py`의 `COMMANDS`에 줄 추가:
```python
    "check": ("video_library.gates", "AI 판단 단계 결과 파일 검사"),
    "merge": ("video_library.merge", "조각별 교정·교열 또는 번역 결과 합치기"),
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -W error`
Expected: 모두 통과(실패 0)

- [ ] **Step 5: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/gates.py plugin/video-library/skills/video-library/scripts/video_library/merge.py plugin/video-library/skills/video-library/scripts/vl.py plugin/video-library/skills/video-library/tests/test_gates_merge.py
git commit -m "feat(pipeline): gate AI outputs and merge chunk results" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: `library` — 영상자료실 반영·목록·재작업

**Files:**
- Create: `PKG/library.py`
- Modify: `SKILL_DIR/scripts/vl.py` (`COMMANDS`에 `reopen`)
- Test: `TESTS/test_library.py`

**Interfaces:**
- Consumes: `config.*`, `jobs.STEPS/start_job`, `validate.validate_lecture`
- Produces (`video_library.library`):
  - `index_entry(doc) -> dict` — api.md 2절 형식 (`translations`는 언어 목록 정렬)
  - `update_index(home, doc) -> list` — 같은 id 교체, `processed_at` 내림차순. 파일이 깨졌거나 배열이 아니면 `rebuild_index`
  - `rebuild_index(home) -> list` — `lectures/*/lecture.json`(이름에 `.` 있는 폴더 제외)에서 다시 만듦
  - `commit_lecture(home, video_id) -> Path` — 작업 폴더의 `lecture.json`이 `validate_lecture`를 통과해야만, 기존 완성 폴더를 `<id>.old`로 옮기고 작업 폴더를 완성 폴더로 바꾼 뒤 `.old` 삭제, `index.json` 갱신. 실패하면 기존 폴더 복원, 작업 폴더 유지
  - `reopen(home, video_id, translate_en: bool) -> dict` — 완성 폴더를 작업 폴더로 복사하고 새 job(`assemble`·필요 시 `translate`만 `pending`, 나머지 `skipped`), `request.json` 갱신. 작업 폴더가 이미 있거나 강의가 없거나 한국어가 아닌 강의에 `--translate-en`이면 `StepError`
  - `main(argv)` = `vl.py reopen --video ID [--translate-en]`

- [ ] **Step 1: 실패하는 테스트 작성**

`TESTS/test_library.py`:
```python
import json

import pytest

from conftest import VIDEO_ID, sample_doc
from video_library import library
from video_library.config import StepError, lecture_dir, read_json, work_dir, write_json
from video_library.jobs import load_job


def make_doc(vid=VIDEO_ID, processed_at="2026-10-05T14:03:00+09:00", title=None):
    doc = sample_doc()
    lec = doc["lecture"]
    lec.update(id=vid, video_id=vid, source_url=f"https://www.youtube.com/watch?v={vid}",
               thumbnail_url=f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg", processed_at=processed_at)
    if title:
        lec["title"] = title
    return doc


def stage(home, doc):
    vid = doc["lecture"]["id"]
    write_json(work_dir(home, vid) / "lecture.json", doc)
    write_json(work_dir(home, vid) / "build" / "request.json", {"video_id": vid, "job_id": "x"})
    return vid


def test_index_entry():
    assert library.index_entry(sample_doc()) == {
        "id": VIDEO_ID, "title": "깃 기초 맛보기 (샘플)", "channel": "샘플 채널", "duration": 480.0,
        "thumbnail_url": f"https://i.ytimg.com/vi/{VIDEO_ID}/hqdefault.jpg", "field": "dev", "language": "ko",
        "translations": ["en"], "chapter_count": 2, "processed_at": "2026-10-05T14:03:00+09:00"}


def test_commit_moves_folder_and_updates_index(home):
    stage(home, make_doc())
    final = library.commit_lecture(home, VIDEO_ID)
    assert final == lecture_dir(home, VIDEO_ID) and (final / "lecture.json").exists()
    assert not work_dir(home, VIDEO_ID).exists()
    assert [e["id"] for e in read_json(home / "index.json")] == [VIDEO_ID]


def test_recommit_replaces_and_orders_newest_first(home):
    other = "ZzZzZzZzZzZ"
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)
    stage(home, make_doc(other, "2026-10-06T09:00:00+09:00"))
    library.commit_lecture(home, other)
    stage(home, make_doc(VIDEO_ID, "2026-10-07T09:00:00+09:00", title="새 제목"))
    library.commit_lecture(home, VIDEO_ID)
    index = read_json(home / "index.json")
    assert [e["id"] for e in index] == [VIDEO_ID, other]
    assert index[0]["title"] == "새 제목"
    assert read_json(lecture_dir(home, VIDEO_ID) / "lecture.json")["lecture"]["title"] == "새 제목"
    assert not (home / "lectures" / f"{VIDEO_ID}.old").exists()


def test_failed_commit_keeps_existing_lecture(home):
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)
    bad = make_doc(title="망가진 재처리")
    del bad["faq"]
    stage(home, bad)
    with pytest.raises(StepError, match="검사 불합격"):
        library.commit_lecture(home, VIDEO_ID)
    assert read_json(lecture_dir(home, VIDEO_ID) / "lecture.json")["lecture"]["title"] == "깃 기초 맛보기 (샘플)"
    assert work_dir(home, VIDEO_ID).exists()


def test_broken_index_is_rebuilt(home):
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)
    (home / "index.json").write_text("{깨짐", encoding="utf-8")
    other = "ZzZzZzZzZzZ"
    stage(home, make_doc(other, "2026-10-06T09:00:00+09:00"))
    library.commit_lecture(home, other)
    assert [e["id"] for e in read_json(home / "index.json")] == [other, VIDEO_ID]


def test_reopen_for_english_translation(home):
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)
    out = library.reopen(home, VIDEO_ID, translate_en=True)
    work = work_dir(home, VIDEO_ID)
    assert out["work_dir"] == str(work) and (work / "lecture.json").exists()
    request = read_json(work / "build" / "request.json")
    assert request["translate_en"] is True and request["job_id"] == out["job_id"]
    steps = load_job(home, out["job_id"])["steps"]
    assert steps["translate"] == "pending" and steps["assemble"] == "pending" and steps["fetch"] == "skipped"


def test_reopen_refuses_existing_work_folder(home):
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)
    work_dir(home, VIDEO_ID).mkdir()
    with pytest.raises(StepError, match="작업 폴더가 이미 있습니다"):
        library.reopen(home, VIDEO_ID, translate_en=True)


def test_reopen_missing_lecture(home):
    with pytest.raises(StepError, match="영상자료실에 이 강의가 없습니다"):
        library.reopen(home, VIDEO_ID, translate_en=True)


def test_reopen_translate_en_only_for_korean(home):
    doc = make_doc()
    doc["lecture"]["language"] = "en"
    doc["translations"] = {"ko": [{"idx": s["idx"], "text": s["text"]} for s in doc["segments"]]}
    stage(home, doc)
    library.commit_lecture(home, VIDEO_ID)
    with pytest.raises(StepError, match="한국어 강의"):
        library.reopen(home, VIDEO_ID, translate_en=True)


def test_reopen_command(home, capsys):
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)
    assert library.main(["--video", VIDEO_ID, "--translate-en"]) == 0
    assert json.loads(capsys.readouterr().out)["video_id"] == VIDEO_ID
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_library.py -v`
Expected: FAIL — `ImportError: cannot import name 'library'`

- [ ] **Step 3: 구현**

`PKG/library.py`:
```python
"""영상자료실 반영: 작업 폴더 → 완성 폴더(원자적 교체), index.json 목록, 재작업 열기."""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from .config import StepError, library_home, lecture_dir, read_json, work_dir, write_json
from .jobs import STEPS, start_job
from .validate import validate_lecture

INDEX_NAME = "index.json"


def index_entry(doc: dict) -> dict:
    lec = doc["lecture"]
    return {"id": lec["id"], "title": lec["title"], "channel": lec["channel"], "duration": lec["duration"],
            "thumbnail_url": lec["thumbnail_url"], "field": lec["field"], "language": lec["language"],
            "translations": sorted(doc["translations"]), "chapter_count": len(doc["chapters"]),
            "processed_at": lec["processed_at"]}


def _save_index(home: Path, items: list) -> list:
    items = sorted(items, key=lambda e: str(e.get("processed_at", "")), reverse=True)
    write_json(home / INDEX_NAME, items)
    return items


def rebuild_index(home: Path) -> list:
    items = []
    for path in sorted((home / "lectures").glob("*/lecture.json")):
        if "." in path.parent.name:  # <id>.tmp, <id>.old
            continue
        try:
            items.append(index_entry(read_json(path)))
        except (ValueError, KeyError, TypeError):
            continue
    return _save_index(home, items)


def update_index(home: Path, doc: dict) -> list:
    path = home / INDEX_NAME
    try:
        items = read_json(path) if path.exists() else []
        if not isinstance(items, list):
            raise ValueError("index.json 이 배열이 아님")
    except ValueError:
        return rebuild_index(home)  # 깨진 목록은 lectures/ 에서 다시 만든다
    entry = index_entry(doc)
    items = [e for e in items if isinstance(e, dict) and e.get("id") != entry["id"]] + [entry]
    return _save_index(home, items)


def commit_lecture(home: Path, video_id: str) -> Path:
    work, final = work_dir(home, video_id), lecture_dir(home, video_id)
    try:
        doc = read_json(work / "lecture.json")
    except (ValueError, FileNotFoundError) as exc:
        raise StepError(f"lecture.json 을 읽지 못했습니다: {exc}") from exc
    errors = validate_lecture(doc)
    if errors:
        raise StepError("lecture.json 검사 불합격 — 영상자료실의 기존 자료는 그대로 둡니다:\n"
                        + "\n".join(f"  - {e}" for e in errors))
    backup = final.with_name(f"{video_id}.old")
    if backup.exists():
        shutil.rmtree(backup)
    if final.exists():
        os.replace(final, backup)
    try:
        os.replace(work, final)
    except OSError as exc:
        if backup.exists():
            os.replace(backup, final)
        raise StepError(f"영상자료실에 반영하지 못했습니다(폴더가 열려 있으면 닫고 다시 시도): {exc}") from exc
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
    update_index(home, doc)
    return final


def reopen(home: Path, video_id: str, translate_en: bool) -> dict:
    final, work = lecture_dir(home, video_id), work_dir(home, video_id)
    if not (final / "lecture.json").exists():
        raise StepError(f"영상자료실에 이 강의가 없습니다: {video_id}")
    if work.exists():
        raise StepError(f"작업 폴더가 이미 있습니다: {work} — 이전 작업을 이어서 하거나 폴더를 지운 뒤 다시 실행하세요.")
    doc = read_json(final / "lecture.json")
    if translate_en and doc["lecture"]["language"] != "ko":
        raise StepError("영어 번역 요청은 한국어 강의에만 할 수 있습니다.")
    shutil.copytree(final, work)
    steps = {s: "skipped" for s in STEPS}
    steps["assemble"] = "pending"
    if translate_en:
        steps["translate"] = "pending"
    job = start_job(home, video_id, doc["lecture"]["title"], steps)
    req_path = work / "build" / "request.json"
    request = read_json(req_path) if req_path.exists() else {
        "video_id": video_id, "url": doc["lecture"]["source_url"], "translate_en": False, "lang_override": None}
    request["job_id"] = job["job_id"]
    request["translate_en"] = translate_en or request.get("translate_en", False)
    write_json(req_path, request)
    return {"video_id": video_id, "job_id": job["job_id"], "work_dir": str(work)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py reopen", description="영상자료실의 강의를 다시 작업 폴더로 연다(추가 번역용).")
    ap.add_argument("--video", required=True, help="영상 ID")
    ap.add_argument("--translate-en", action="store_true", help="한국어 강의의 전사를 영어로 번역")
    a = ap.parse_args(argv)
    result = reopen(library_home(), a.video, a.translate_en)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
```

`SKILL_DIR/scripts/vl.py`의 `COMMANDS`에 줄 추가:
```python
    "reopen": ("video_library.library", "영상자료실의 강의를 다시 작업 폴더로 열기(추가 번역)"),
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -W error`
Expected: 모두 통과(실패 0)

- [ ] **Step 5: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/library.py plugin/video-library/skills/video-library/scripts/vl.py plugin/video-library/skills/video-library/tests/test_library.py
git commit -m "feat(pipeline): commit lectures atomically and maintain index.json" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: `assemble` — `lecture.json` 조립·반영·작업 완료

**Files:**
- Create: `PKG/assemble.py`
- Modify: `SKILL_DIR/scripts/vl.py` (`COMMANDS`에 `assemble`)
- Test: `TESTS/test_assemble.py`

**Interfaces:**
- Consumes: `config.*`, `gates.check_output/load_json_file`, `jobs.track/finish_job`, `library.commit_lecture`, `validate.SCHEMA_VERSION/validate_lecture`, `video_library.__version__`
- Produces (`video_library.assemble`):
  - `needed_translations(language: str, translate_en: bool) -> list[str]` — 원문이 한국어가 아니면 `["ko"]`, 한국어이고 `translate_en`이면 `["en"]`, 아니면 `[]`
  - `build_lecture(work, now=None) -> tuple[dict, dict]` — (lecture 문서, job outcome). 필수: `raw/info.json`, `build/request.json`, `build/context.json`(검사), `build/outline.json`(검사), `build/sentences.corrected.json`. 선택: `corrections.json`, `glossary.json`, `faq.json`, `translations.<언어>.json`(원문 언어 제외, 있는 것 전부). 빠진 선택 단계는 `pipeline.skipped`에 기록. 목차 `start`·`end`는 문장 시간으로 채움
  - `assemble(home, video_id, now=None) -> tuple[dict, dict]` — 작업 폴더에 `lecture.json`, `transcript.<언어>.txt`, `transcript.<언어>.timed.txt`를 쓰고 `commit_lecture`. 반환 (`{"video_id","lecture_dir","skipped","sentences","chapters"}`, outcome)
  - `main(argv)` = `vl.py assemble --video ID` (단계 `assemble` 추적 → `finish_job`)

- [ ] **Step 1: 실패하는 테스트 작성**

`TESTS/test_assemble.py`:
```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_assemble.py -v`
Expected: FAIL — `ImportError: cannot import name 'assemble'`

- [ ] **Step 3: 구현**

`PKG/assemble.py`:
```python
"""11단계: 작업 폴더의 결과물 → lecture.json·전사 파일 → 영상자료실 반영 → 작업 완료."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .config import StepError, fmt_time, library_home, now_kst, work_dir, write_json, write_text
from .gates import check_output, load_json_file
from .jobs import finish_job, track
from .library import commit_lecture
from .validate import SCHEMA_VERSION, validate_lecture


def _required(path: Path):
    data, errors = load_json_file(path)
    if errors:
        raise StepError(f"{errors[0]} — 앞 단계를 먼저 끝내세요.")
    return data


def _optional(path: Path):
    if not path.exists():
        return None
    data, errors = load_json_file(path)
    if errors:
        raise StepError(errors[0])
    return data


def needed_translations(language: str, translate_en: bool) -> list[str]:
    if language != "ko":
        return ["ko"]
    return ["en"] if translate_en else []


def _with_times(chapters: list, segments: list) -> list:
    out = []
    for ch in chapters:
        a, b = ch["segments"]
        out.append({"id": ch["id"], "title": ch["title"], "summary": ch["summary"], "segments": [a, b],
                    "start": segments[a - 1]["start"], "end": segments[b - 1]["end"],
                    "children": _with_times(ch.get("children") or [], segments)})
    return out


def build_lecture(work: Path, now=None) -> tuple[dict, dict]:
    build = work / "build"
    info = _required(work / "raw" / "info.json")
    request = _required(build / "request.json")
    for kind in ("context", "outline"):
        errors = check_output(work, kind)
        if errors:
            raise StepError(f"{kind}.json 검사 불합격:\n" + "\n".join(f"  - {e}" for e in errors))
    context = _required(build / "context.json")
    outline = _required(build / "outline.json")
    segments = _required(build / "sentences.corrected.json")
    corrections = _optional(build / "corrections.json") or []
    glossary = _optional(build / "glossary.json")
    faq = _optional(build / "faq.json")
    language = info["language"]
    translations = {}
    for path in sorted(build.glob("translations.*.json")):
        lang = path.name.split(".")[1]
        if lang != language:
            translations[lang] = _required(path)
    needed = needed_translations(language, bool(request.get("translate_en")))
    skipped = []
    if glossary is None:
        skipped.append("glossary")
    if any(lang not in translations for lang in needed):
        skipped.append("translate")
    if faq is None:
        skipped.append("faq")
    doc = {
        "schema_version": SCHEMA_VERSION,
        "lecture": {
            "id": info["id"], "video_id": info["id"], "source_url": info["source_url"], "title": info["title"],
            "channel": info["channel"], "duration": info["duration"], "thumbnail_url": info["thumbnail_url"],
            "language": language, "field": context["field"], "one_liner": context["one_liner"], "mode": "text",
            "processed_at": (now or now_kst()).isoformat(timespec="seconds"),
            "pipeline": {"version": __version__, "caption_kind": info["caption_kind"], "skipped": skipped},
        },
        "segments": [{"idx": s["idx"], "start": s["start"], "end": s["end"], "text": s["text"], "raw": s["raw"]}
                     for s in segments],
        "translations": translations,
        "corrections": corrections,
        "chapters": _with_times(outline["chapters"], segments),
        "mentions": outline["mentions"],
        "glossary": glossary or [],
        "faq": faq or [],
    }
    errors = validate_lecture(doc)
    if errors:
        raise StepError("lecture.json 검사 불합격:\n" + "\n".join(f"  - {e}" for e in errors))
    outcome = {"context": "done", "correct": "done", "merge": "done", "outline": "done",
               "glossary": "skipped" if glossary is None else "done",
               "translate": "done" if needed and "translate" not in skipped else "skipped",
               "faq": "skipped" if faq is None else "done"}
    return doc, outcome


def _write_transcripts(work: Path, doc: dict) -> None:
    starts = [s["start"] for s in doc["segments"]]
    texts = {doc["lecture"]["language"]: [s["text"] for s in doc["segments"]]}
    for lang, items in doc["translations"].items():
        texts[lang] = [it["text"] for it in items]
    for lang, lines in texts.items():
        write_text(work / f"transcript.{lang}.txt", "\n".join(lines) + "\n")
        write_text(work / f"transcript.{lang}.timed.txt",
                   "\n".join(f"[{fmt_time(t)}] {x}" for t, x in zip(starts, lines)) + "\n")


def assemble(home, video_id: str, now=None) -> tuple[dict, dict]:
    work = work_dir(home, video_id)
    if not work.exists():
        raise StepError(f"작업 폴더가 없습니다: {work}")
    doc, outcome = build_lecture(work, now)
    write_json(work / "lecture.json", doc)
    _write_transcripts(work, doc)
    final = commit_lecture(home, video_id)
    result = {"video_id": video_id, "lecture_dir": str(final), "skipped": doc["lecture"]["pipeline"]["skipped"],
              "sentences": len(doc["segments"]), "chapters": len(doc["chapters"])}
    return result, outcome


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py assemble", description="결과물을 lecture.json 으로 조립해 영상자료실에 반영한다.")
    ap.add_argument("--video", required=True, help="영상 ID")
    a = ap.parse_args(argv)
    home = library_home()
    with track(home, a.video, "assemble") as job_id:
        result, outcome = assemble(home, a.video)
    if job_id:
        finish_job(home, job_id, outcome)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
```

`SKILL_DIR/scripts/vl.py`의 `COMMANDS`에 줄 추가:
```python
    "assemble": ("video_library.assemble", "lecture.json 조립·영상자료실 반영"),
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -W error`
Expected: 모두 통과(실패 0)

- [ ] **Step 5: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/assemble.py plugin/video-library/skills/video-library/scripts/vl.py plugin/video-library/skills/video-library/tests/test_assemble.py
git commit -m "feat(pipeline): assemble lecture.json and publish to the library" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: `doctor` — 환경 점검

**Files:**
- Create: `PKG/doctor.py`
- Modify: `SKILL_DIR/scripts/vl.py` (`COMMANDS`에 `doctor`)
- Test: `TESTS/test_doctor.py`

**Interfaces:**
- Consumes: `config.ensure_home/library_home`
- Produces (`video_library.doctor`):
  - `run_checks(home) -> list[dict]` — 각 `{"name","ok","required","detail","fix"}`: Python 3.10 이상(필수), yt-dlp 라이브러리(필수, 설치 명령 `"<sys.executable>" -m pip install --user -U "yt-dlp[default]"`), 자바스크립트 실행기 deno 또는 node(권장, Windows `winget install --id DenoLand.Deno -e`, macOS `brew install deno`, 그 밖 `curl -fsSL https://deno.land/install.sh | sh`), 영상자료실 쓰기 가능(필수)
  - `main(argv)` = `vl.py doctor` → 항목마다 `✓`(통과)·`✗`(필수 실패)·`△`(권장 없음) + 실패 항목의 설치 명령. 필수가 모두 통과면 0, 아니면 1

- [ ] **Step 1: 실패하는 테스트 작성**

`TESTS/test_doctor.py`:
```python
import sys

from video_library import doctor


def patch(monkeypatch, ytdlp=True, deno=True, node=False):
    monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda name: object() if (name == "yt_dlp" and ytdlp) else None)
    found = {"deno": "C:/deno.exe" if deno else None, "node": "C:/node.exe" if node else None}
    monkeypatch.setattr(doctor.shutil, "which", lambda name: found.get(name))


def test_all_ok(home, monkeypatch, capsys):
    patch(monkeypatch)
    assert doctor.main([]) == 0
    out = capsys.readouterr().out
    assert "✓ yt-dlp 라이브러리" in out and "영상자료실" in out


def test_missing_yt_dlp_shows_install_command(home, monkeypatch, capsys):
    patch(monkeypatch, ytdlp=False)
    assert doctor.main([]) == 1
    out = capsys.readouterr().out
    assert "✗ yt-dlp 라이브러리" in out
    assert f'"{sys.executable}" -m pip install --user -U "yt-dlp[default]"' in out


def test_missing_js_runtime_is_only_a_warning(home, monkeypatch, capsys):
    patch(monkeypatch, deno=False, node=False)
    assert doctor.main([]) == 0
    out = capsys.readouterr().out
    assert "△ 자바스크립트 실행기" in out and "deno" in out


def test_node_counts_as_runtime(home, monkeypatch):
    patch(monkeypatch, deno=False, node=True)
    runtime = [c for c in doctor.run_checks(home) if c["name"].startswith("자바스크립트")][0]
    assert runtime["ok"] is True


def test_unwritable_library(home, monkeypatch, capsys):
    patch(monkeypatch)

    def deny(path):
        raise PermissionError("접근 거부")

    monkeypatch.setattr(doctor, "ensure_home", deny)
    assert doctor.main([]) == 1
    assert "✗ 영상자료실 폴더 쓰기" in capsys.readouterr().out
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_doctor.py -v`
Expected: FAIL — `ImportError: cannot import name 'doctor'`

- [ ] **Step 3: 구현**

`PKG/doctor.py`:
```python
"""0단계: 실행 환경 점검 + OS별 설치 명령 안내. 설치는 하지 않는다(사용자 승인 후 AI 가 실행)."""
from __future__ import annotations

import importlib.metadata
import importlib.util
import platform
import shutil
import sys
from pathlib import Path

from .config import ensure_home, library_home


def _ytdlp_version() -> str:
    try:
        return importlib.metadata.version("yt-dlp")
    except importlib.metadata.PackageNotFoundError:
        return "설치됨"


def _js_fix() -> str:
    if sys.platform == "win32":
        return "winget install --id DenoLand.Deno -e"
    if sys.platform == "darwin":
        return "brew install deno"
    return "curl -fsSL https://deno.land/install.sh | sh"


def _library_check(home: Path) -> dict:
    check = {"name": "영상자료실 폴더 쓰기", "required": True, "detail": str(home),
             "fix": "폴더 권한을 확인하거나 환경변수 VL_HOME 으로 다른 위치를 지정하세요."}
    try:
        ensure_home(home)
        probe = home / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        check["ok"] = True
    except OSError as exc:
        check["ok"] = False
        check["detail"] = f"{home} — {exc}"
    return check


def run_checks(home: Path) -> list[dict]:
    has_ytdlp = importlib.util.find_spec("yt_dlp") is not None
    runtime = shutil.which("deno") or shutil.which("node")
    return [
        {"name": "Python 3.10 이상", "ok": sys.version_info >= (3, 10), "required": True,
         "detail": platform.python_version(),
         "fix": "https://www.python.org/downloads/ 에서 Python 3.12 이상을 설치하세요."},
        {"name": "yt-dlp 라이브러리", "ok": has_ytdlp, "required": True,
         "detail": _ytdlp_version() if has_ytdlp else "없음",
         "fix": f'"{sys.executable}" -m pip install --user -U "yt-dlp[default]"'},
        {"name": "자바스크립트 실행기(deno 또는 node, 권장)", "ok": bool(runtime), "required": False,
         "detail": runtime or "없음", "fix": _js_fix()},
        _library_check(home),
    ]


def main(argv: list[str]) -> int:
    home = library_home()
    checks = run_checks(home)
    print(f"파이썬: {sys.executable}")
    print(f"영상자료실: {home}")
    for c in checks:
        mark = "✓" if c["ok"] else ("✗" if c["required"] else "△")
        print(f"{mark} {c['name']} — {c['detail']}")
    missing = [c for c in checks if not c["ok"]]
    if missing:
        print("\n설치·조치 명령(사용자 승인 후 실행):")
        for c in missing:
            print(f"  [{c['name']}] {c['fix']}")
    return 0 if all(c["ok"] for c in checks if c["required"]) else 1
```

`SKILL_DIR/scripts/vl.py`의 `COMMANDS`에 줄 추가:
```python
    "doctor": ("video_library.doctor", "실행 환경 점검 + OS별 설치 명령 안내"),
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -W error`
Expected: 모두 통과(실패 0)

- [ ] **Step 5: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/doctor.py plugin/video-library/skills/video-library/scripts/vl.py plugin/video-library/skills/video-library/tests/test_doctor.py
git commit -m "feat(pipeline): add environment doctor with install hints" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: `SKILL.md` — 절차서와 AI 브리프

**Files:**
- Create: `SKILL_DIR/SKILL.md`
- Test: `TESTS/test_skill_doc.py`

**Interfaces:**
- Consumes: `vl.py`의 `COMMANDS`(10개: validate, progress, fetch, preprocess, chunk, check, merge, reopen, assemble, doctor)
- Produces: AI가 따르는 절차. 브리프 제목 6개: `[맥락 브리프]`, `[교정 브리프]`, `[목차 브리프]`, `[용어집 브리프]`, `[번역 브리프]`, `[FAQ 브리프]`

- [ ] **Step 1: 실패하는 테스트 작성**

`TESTS/test_skill_doc.py`:
```python
import importlib.util
import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SKILL = SKILL_DIR / "SKILL.md"


def load_commands():
    spec = importlib.util.spec_from_file_location("vl_cmds", SKILL_DIR / "scripts" / "vl.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.COMMANDS


def text():
    return SKILL.read_text(encoding="utf-8")


def test_frontmatter():
    assert text().startswith("---\nname: video-library\ndescription: ")


def test_every_mentioned_command_exists():
    used = set(re.findall(r"vl\.py\"?\s+([a-z]+)", text()))
    assert used and used <= set(load_commands())


def test_every_command_is_documented():
    used = set(re.findall(r"vl\.py\"?\s+([a-z]+)", text()))
    assert set(load_commands()) - {"validate"} <= used


def test_all_briefs_present():
    for title in ("[맥락 브리프]", "[교정 브리프]", "[목차 브리프]", "[용어집 브리프]", "[번역 브리프]", "[FAQ 브리프]"):
        assert f"## {title}" in text()


def test_safety_rules_present():
    body = text()
    assert "토큰" in body and "승인" in body
    assert "말한 내용은 바꾸지 않는다" in body
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_skill_doc.py -v`
Expected: FAIL — `FileNotFoundError`(SKILL.md 없음)

- [ ] **Step 3: 작성**

`SKILL_DIR/SKILL.md`:
````markdown
---
name: video-library
description: 유튜브 영상 링크 하나로 자막을 교정·교열하고 목차·요약·용어집·번역·FAQ를 만들어 내 PC의 영상자료실(문서/영상자료실)에 쌓는다. Claude Code에서는 /video-library <링크>, Codex에서는 $video-library <링크>로 호출한다. "video-library 번역 <영상ID>"(한국어 강의의 영어 번역 추가) 요청도 이 스킬로 처리한다.
---

# video-library

유튜브 영상의 자막을 받아 **기계 단계는 동봉된 파이썬 스크립트(`vl.py`)**, **판단 단계는 이 문서의 브리프**로 처리한다. 판단 결과는 `vl.py check`를 통과해야만 다음 단계로 간다.

## 규칙
- `$SKILL` = 이 SKILL.md가 있는 폴더의 절대경로. `$PY` = 0단계 `doctor`가 출력한 파이썬 경로(보통 Windows는 `python`, 그 밖은 `python3`).
- 모든 명령은 `"$PY" "$SKILL/scripts/vl.py" <명령> …` 형식이다. 이하 `vl.py <명령>`으로 줄여 쓴다.
- 결과물은 영상자료실(기본 `문서/영상자료실`, 환경변수 `VL_HOME`으로 변경)에 쌓인다. `fetch`가 출력한 `work_dir`(= `<영상자료실>/lectures/<ID>.tmp`)을 이하 `<W>`, `video_id`를 `<ID>`라 한다.
- 옵션: `--translate-en`(한국어 영상의 전사를 영어로도 번역), `--lang xx`(영상 언어를 직접 지정).
- 사용자에게 업로드 토큰·비밀번호를 묻거나 출력하지 않는다. 설치 명령은 사용자 승인 후에만 실행한다.
- 판단 단계는 시작할 때 `vl.py progress --video <ID> --step <단계> --status running`, 끝나면 `--status done`을 보낸다(목록 화면의 진행 카드용).
- 브리프를 에이전트에게 줄 때는 `<W>`·`<ID>`·`NN`(조각 번호 두 자리)·`$PY`·`$SKILL`을 실제 값으로 바꿔 그대로 전달한다.
- 검사 불합격이면 오류 메시지를 브리프 끝에 붙여 **1회** 다시 시킨다. 그래도 불합격이면:
  - 핵심 단계(context·correct·outline)는 멈추고 원인을 사용자에게 알린다.
  - 선택 단계(glossary·translate·faq)는 그 결과 파일을 지우고 `--status skipped`로 보고한 뒤 계속한다.
- 기계 단계가 `오류: …`로 실패하면 그 메시지를 사용자에게 그대로 전하고, 원인을 고친 뒤 **그 단계부터** 다시 실행한다.

## 단계
0. **점검** — `vl.py doctor`. `✗`(필수) 항목이 있으면 출력된 설치 명령을 사용자에게 보여주고 승인을 받아 실행한 뒤 다시 점검한다. `△`(권장)는 알리고 진행한다.
1. **자막 받기** — `vl.py fetch "<링크>" [--translate-en] [--lang xx]`. 출력 JSON의 `video_id`, `work_dir`, `language`, `translate`, `long`을 기억한다. `long`이 true(1시간 초과)면 처리 시간이 길고 구독 사용량이 많이 든다는 점을 알리고 계속할지 묻는다.
2. **정리** — `vl.py preprocess --video <ID>`
3. **나누기** — `vl.py chunk --video <ID>` → `<W>/build/chunks/manifest.json`에 조각 목록
4. **맥락 파악(판단)** — `vl.py progress --video <ID> --step context` → [맥락 브리프] 수행(에이전트 1개 또는 직접) → `vl.py check --video <ID> --kind context` → `--status done`
5. **교정·교열(판단)** — `vl.py progress --video <ID> --step correct` → 조각마다 [교정 브리프]. Claude Code에서는 서브에이전트를 최대 8개씩 병렬로 쓴다. Codex에서는 병렬 에이전트를 쓸 수 있으면 최대 8개씩, 아니면 차례로 처리한다. 조각마다 `vl.py check --video <ID> --kind edits --chunk NN`. 묶음이 끝날 때마다 `vl.py progress --video <ID> --step correct --detail "완료/전체"` → 모두 끝나면 `--status done`
6. **합치기** — `vl.py merge --video <ID> --kind edits` (불합격 조각이 있으면 그 조각만 5단계를 다시)
7. **목차·요약(판단)** — `vl.py progress --video <ID> --step outline` → [목차 브리프] → `vl.py check --video <ID> --kind outline` → `--status done`
8. **용어집(판단)** — `vl.py progress --video <ID> --step glossary` → [용어집 브리프] → `vl.py check --video <ID> --kind glossary` → `--status done`
9. **번역(판단)** — fetch 출력의 `translate`가 true일 때만. 대상 언어 L = 원문이 한국어가 아니면 `ko`, `--translate-en`이면 `en`. `vl.py progress --video <ID> --step translate` → 조각마다 [번역 브리프](5단계처럼 병렬) → 조각마다 `vl.py check --video <ID> --kind translation --lang L --chunk NN` → `vl.py merge --video <ID> --kind translation --lang L`
10. **FAQ(판단)** — `vl.py progress --video <ID> --step faq` → [FAQ 브리프] → `vl.py check --video <ID> --kind faq` → `--status done`
11. **조립** — `vl.py assemble --video <ID>` → 영상자료실에 반영된다. 출력의 `lecture_dir`와 `skipped`를 사용자에게 알린다. 빠진 단계가 있으면 나중에 다시 요청할 수 있다고 안내한다.

## 나중 요청: 한국어 강의 영어 번역
사용자가 `/video-library 번역 <ID>`(또는 "video-library 번역 <ID>")를 요청하면:
1. `vl.py reopen --video <ID> --translate-en`
2. 위 9단계(L = `en`)
3. `vl.py assemble --video <ID>`

## [맥락 브리프]
```
너는 유튜브 영상 자막 정리 파이프라인의 "맥락 파악" 단계다. 자동자막을 고치기 전에 영상 전체를 읽고 맥락표를 만든다.

입력: <W>/build/transcript.md — `[번호] [시간] 문장` 줄. 길면 나눠 읽되 끝까지 읽는다.
출력: <W>/build/context.json (UTF-8, JSON만):
{"field": "dev|finance|science|medical|other", "one_liner": "80자 이내 한국어 한 줄 소개", "topic_summary": "한국어 3~5문장 요약", "key_terms": [{"term": "올바른 표기", "heard_as": ["자막에 잘못 적힌 표기"], "note": "짧은 설명"}], "proper_nouns": ["사람·회사·제품·서비스 이름의 올바른 표기"]}

규칙:
1. field: 개발(dev), 금융·경제·투자(finance), 과학기술(science), 의학·보건(medical), 그 밖(other) 중 영상의 중심 주제 하나.
2. key_terms: 영상이 중요하게 다루는 용어와, 자동자막이 그것을 잘못 적은 형태(heard_as). heard_as에는 transcript.md에 실제로 나온 표기만 적는다(추측으로 지어내지 않는다).
3. one_liner·topic_summary는 원문 언어와 상관없이 한국어로, 영상이 말한 것에 충실하게 쓴다.
4. 끝나면 "$PY" "$SKILL/scripts/vl.py" check --video <ID> --kind context 로 확인하고, 불합격이면 고쳐서 다시 확인한다.

끝나면 2줄로 보고: field와 key_terms 개수, 확신이 없던 점.
```

## [교정 브리프]
```
너는 유튜브 자막 정리 파이프라인의 "교정·교열" 단계다. 담당 조각 하나만 처리한다.

입력:
- <W>/build/chunks/NN.md — `[번호] [시간] 문장`. CONTEXT 블록은 읽기 전용이고, EDITABLE RANGE의 문장만 고친다.
- <W>/build/context.json — 맥락표. key_terms의 heard_as → term 이 교정 후보다.
출력: <W>/build/chunks/NN.edits.json — 바꾼 문장만 담은 JSON 배열(바꿀 것이 없으면 []):
[{"idx": 문장번호(정수), "text": "고친 문장 전체", "changes": [{"from": "원래 표기", "to": "고친 표기", "kind": "term 또는 spelling"}]}]

할 일:
1. 교정(kind "term"): 맥락표와 앞뒤 문맥으로 볼 때 명백히 잘못 인식된 용어·고유명사만 고친다(예: 기 허브→GitHub, 출론→추론).
2. 교열: 띄어쓰기·문장부호(마침표·쉼표·물음표)는 자유롭게 고친다. 이것은 changes에 적지 않는다. 맞춤법(kind "spelling", 예: 되요→돼요)은 changes에 적는다.
3. 말한 내용은 바꾸지 않는다. 군더더기(어·음·그) 지우기, 문장 다시 쓰기, 요약, 단어 추가·삭제를 하지 않는다. 숫자·단위·부호(1.5, -5, 10,000)는 그대로 둔다. 확실하지 않으면 고치지 않는다.
4. changes의 from은 원문 문장에 실제로 있는 글자 그대로, to는 바꾼 글자다. from·to는 각 20자 이내. 원래 글자를 그대로 두고 덧붙이기만 하거나 지우기만 하는 변경은 불합격이다.
5. 같은 문장에 같은 단어가 여러 번 나오는데 일부만 고칠 때는 from에 앞뒤 글자를 붙여 어느 것인지 구분한다(검사기는 처음 나오는 것부터 바꾼다).
6. 한 문장에서 바뀐 글자가 30%를 넘으면 불합격이다. 그렇게 많이 고쳐야 한다면 그 문장은 두지 않는다.
7. 끝나면 "$PY" "$SKILL/scripts/vl.py" check --video <ID> --kind edits --chunk NN 으로 확인하고, 불합격이면 고쳐서 다시 확인한다.

끝나면 2줄로 보고: 고친 문장 수와 교정(term) 예시 몇 개, 확신이 없던 점.
```

## [목차 브리프]
```
너는 영상 전사를 2단 목차로 구조화한다.

입력: <W>/build/sentences.corrected.json — [{idx, start, end, text}] (N개, 초 단위). 길면 나눠 읽는다. <W>/build/context.json 도 참고한다.
출력: <W>/build/outline.json (JSON만):
{"chapters": [{"id": "1", "title": "...", "summary": "...", "segments": [첫 문장 번호, 끝 문장 번호], "children": [{"id": "1.1", "title": "...", "summary": "...", "segments": [a, b], "children": []}]}],
 "mentions": [{"kind": "link|book|command|other", "text": "...", "url": "https://...(링크일 때만)", "idx": 문장번호}]}

규칙:
1. 대목차 개수: 영상 10분 미만 2~4개, 60분 미만 4~10개, 그 이상 6~12개. 소목차는 0개 또는 2~6개이고, 10분 이상 영상은 대목차마다 2~6개가 필수다. 3단은 만들지 않는다(소목차의 children은 []).
2. segments는 문장 번호다(시간·단어 번호가 아님). 대목차들이 1..N을 빈틈·겹침 없이 차례로 덮고, 소목차들이 부모 범위를 정확히 덮는다. id는 "1","2",… / "1.1","1.2",… 순서.
3. 제목은 30자 이내 한국어 명사구로, 화자가 쓴 말을 위주로 한다. 대목차 요약은 3~5문장, 소목차 요약은 1~2문장. 말한 내용에 충실하게 쓰고 평가·추가는 하지 않는다. 원문 언어와 상관없이 한국어로 쓴다.
4. mentions: 화자가 언급한 사이트·책·명령어 등. 없으면 [].
5. 끝나면 "$PY" "$SKILL/scripts/vl.py" check --video <ID> --kind outline 으로 확인하고, 불합격이면 고친다.

끝나면 2줄로 보고: 대목차·소목차 수, mentions 수와 확신이 없던 점.
```

## [용어집 브리프]
```
너는 이 영상을 보는 학습자를 위한 용어집을 만든다.

입력: <W>/build/sentences.corrected.json, <W>/build/outline.json, <W>/build/context.json
출력: <W>/build/glossary.json — [{"term": "...", "definition": "...", "analogy": "...", "claim_note": "...", "idx": 문장번호}] (JSON 배열만)

규칙:
1. 영상에서 실제로 설명하거나 다룬 용어만 넣는다(지나가며 이름만 나온 것은 제외). 20분 영상 8~25개, 3시간 영상 20~60개(길이에 비례). 처음 나온 순서로.
2. term: 표준 표기. 필요하면 한글과 영어를 함께 쓴다(예: "리포지토리(Repository)").
3. definition: 1~2문장. 그 분야에서 일반적으로 인정되는 뜻을 비전문가가 이해할 수준으로 쓴다. 영상 문장을 베끼지 않는다.
4. analogy: 핵심 원리를 담은 일상 비유 한 문장. 정직한 비유가 없으면 이 키를 뺀다.
5. claim_note: 금융·투자·의학 등에서 화자가 그 용어에 대해 주장·전망·권유를 했다면 정의와 섞지 말고 "영상에서는 ~라고 설명" 형식으로 여기에 적는다. 없으면 이 키를 뺀다.
6. idx: 그 용어가 처음 설명된 문장 번호.
7. 모두 한국어로 쓴다. 끝나면 "$PY" "$SKILL/scripts/vl.py" check --video <ID> --kind glossary 로 확인한다.

끝나면 2줄로 보고: 용어 수, 비유를 일부러 뺀 용어와 확신이 없던 점.
```

## [번역 브리프]
```
너는 영상 전사의 한 조각을 L 언어로 번역한다(ko = 한국어, en = 영어).

입력: <W>/build/chunks/NN.md(이 조각의 문장 번호 범위 확인용), <W>/build/sentences.corrected.json(번역할 문장 — 교정된 text), <W>/build/context.json(용어 표기)
출력: <W>/build/chunks/NN.L.json — [{"idx": 번호, "text": "번역문"}]. 이 조각의 EDITABLE RANGE 문장 전부를, 번호 순서대로, 문장 하나에 번역 하나씩.

규칙:
1. 문장을 합치거나 나누지 않는다(번호가 1:1이어야 화면에서 장면 이동이 맞는다). 문장이 중간에 끊겨 있으면 끊긴 그대로 자연스럽게 옮긴다.
2. 용어는 맥락표의 표기를 따른다. 고유명사·명령어·코드·숫자는 원문 그대로 둔다.
3. 빈 번역은 안 된다. 끝나면 "$PY" "$SKILL/scripts/vl.py" check --video <ID> --kind translation --lang L --chunk NN 으로 확인한다.

끝나면 1줄로 보고: 번역한 문장 수와 확신이 없던 점.
```

## [FAQ 브리프]
```
너는 학습자가 이 영상에 대해 물을 법한 질문과 답을 만든다.

입력: <W>/build/sentences.corrected.json, <W>/build/outline.json
출력: <W>/build/faq.json — [{"question": "...", "answer": "...", "evidence": [근거 문장 번호, ...]}] 5~10개

규칙:
1. 답은 영상에 근거가 있는 내용만, 한국어 2~4문장으로 쓴다. evidence에 근거 문장 번호를 1개 이상 넣는다.
2. 영상 밖의 투자 조언·진단·처방을 덧붙이지 않는다. 화자의 주장은 "영상에서는 ~라고 설명합니다"처럼 전한다.
3. 핵심 개념·방법·주의점을 고루 다룬다. 끝나면 "$PY" "$SKILL/scripts/vl.py" check --video <ID> --kind faq 로 확인한다.

끝나면 1줄로 보고: 질문 수와 확신이 없던 점.
```
````

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -W error`
Expected: 모두 통과(실패 0)

- [ ] **Step 5: 커밋**

```bash
git add plugin/video-library/skills/video-library/SKILL.md plugin/video-library/skills/video-library/tests/test_skill_doc.py
git commit -m "feat(pipeline): add SKILL.md procedure and AI briefs" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: 실제 영상으로 끝까지 실행 (사용자 승인 필요)

이 Task는 PC에 설치하고 유튜브에 접속하며 Claude 사용량을 쓰므로, **각 단계 전에 사용자 승인**을 받는다. 플러그인 설치(마켓플레이스)는 5단계 몫이므로, 여기서는 이 세션의 AI가 `SKILL.md`를 절차서로 읽고 그대로 수행한다.

**Files:**
- Create: `docs/superpowers/evidence/2026-10-05-stage2-pipeline.md` (실행 기록)
- 영상자료실(`문서/영상자료실`)에 실제 결과물이 생긴다(Git 대상 아님)

- [ ] **Step 1: 환경 점검**

Run: `python plugin/video-library/skills/video-library/scripts/vl.py doctor`
Expected: `✗ yt-dlp 라이브러리`(이 PC에는 아직 없음). 출력된 설치 명령을 사용자에게 보여주고 **승인을 받는다**.

- [ ] **Step 2: (승인 후) 설치 → 재점검**

Run: doctor가 출력한 `"<python 경로>" -m pip install --user -U "yt-dlp[default]"` 실행 후 `vl.py doctor` 다시 실행
Expected: 필수 항목 모두 `✓`, 종료 코드 0. deno·node가 없어 `△`이면 사용자에게 알린다. 설치는 `fetch` 실패 시 승인을 받아 진행한다.

- [ ] **Step 3: 영상 선택**

사용자에게 **바이브코딩대학 한국어 영상 링크**(10~30분 권장)를 받는다. 예상 사용량(교정·목차·용어집·FAQ — 3시간 강의 기준 원작 텍스트 모드보다 적을 것으로 예상, 실측 전)을 알리고 승인을 받는다.

- [ ] **Step 4: SKILL.md 절차대로 실행**

`SKILL.md` 0~11단계를 그대로 수행한다. 각 기계 단계의 출력과 `vl.py check` 결과를 확인한다.
Expected: `vl.py assemble` 출력의 `skipped`가 `[]`이고 `lecture_dir`가 `문서/영상자료실/lectures/<ID>`.

- [ ] **Step 5: 결과 검증**

Run: `python plugin/video-library/skills/video-library/scripts/vl.py validate "<lecture_dir>/lecture.json"`
Expected: `통과`. 추가로 `index.json`에 항목이 있고, `jobs/<job_id>.json`의 `status`가 `done`인지 확인한다. 교정 사례 3~5개(`corrections`)를 사용자에게 보여준다.

- [ ] **Step 6: 실행 기록 작성·커밋**

`docs/superpowers/evidence/2026-10-05-stage2-pipeline.md`에 실제 값으로 기록: 영상 길이·문장 수·조각 수, 단계별 소요 시간, 서브에이전트 사용량(Agent 도구 결과의 토큰 수 합계), 교정 사례, 실패·재시도와 원인, 성공·실패·미확인. 영상 내용(전사 원문)은 기록하지 않는다(공개 저장소).

```bash
git add docs/superpowers/evidence/2026-10-05-stage2-pipeline.md
git commit -m "docs: record first real pipeline run" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: 기록 갱신

**Files:**
- Modify: `docs/handoff.md` (§1 표·다음 할 일, §3 진행 기록)
- Modify: `docs/superpowers/evidence/2026-10-05-stage2-pipeline.md` (자동 테스트 결과 절 추가)

- [ ] **Step 1: 전체 테스트**

Run: `python -m pytest -W error`
Expected: 모두 통과(실패 0)

- [ ] **Step 2: 기록**

증거 문서에 "자동 테스트" 절(실행 명령과 실제 통과 수)과 "1단계 미룬 사항 처리" 절(교정 검사 보정, `originals` 정수 키, 교정 브리프의 `from` 앞뒤 글자 안내)을 추가한다. `docs/handoff.md` §1 표에 `| 2단계 플러그인 처리 | 완료 — … | [증거](…) |`를 넣고, 다음 할 일을 "3단계(화면 + PC 미니 서버) 구현 계획 작성 → 사용자 검토"로 바꾸고, §3에 한 줄 추가한다.

- [ ] **Step 3: 커밋**

```bash
git add docs/handoff.md docs/superpowers/evidence/2026-10-05-stage2-pipeline.md
git commit -m "docs: record stage 2 completion" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
