# video-library 3단계(화면 + PC 미니 서버) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 영상자료실에 쌓인 강의를 내 PC 전용 미니 서버(`127.0.0.1`)로 띄워 **목록 화면**(분야 필터·통합 검색·실시간 진행 카드)과 **강의 화면**(유튜브 재생·전사·목차·노트·용어집·FAQ·복사·요청 버튼)으로 보여 주고, 더블클릭 열기 파일과 대화창 질문용 검색 명령까지 만든다.

**Architecture:** 서버는 표준 라이브러리 `ThreadingHTTPServer` 하나이고, 저장소(`FileStore`)를 읽기 전용으로 보여 준다(쓰기는 지금처럼 플러그인 명령이 파일로 한다). 화면은 빌드 없는 HTML·CSS·JS 파일이며 4단계 Railway 서버도 같은 파일을 쓴다. `vl.py open`이 화면 파일과 서버 실행 파일 사본을 `영상자료실/app/`에 설치하고, 서버가 꺼져 있으면 백그라운드로 켠 뒤 브라우저를 연다. 통합 검색은 메모리 색인(`SearchIndex`)으로, 서버와 `vl.py search`가 같이 쓴다.

**Tech Stack:** Python 3.10+ 표준 라이브러리(`http.server`, `subprocess`, `webbrowser`, `urllib`), 바닐라 HTML·CSS·JavaScript, YouTube IFrame Player API, 개발용 pytest(+ 있으면 `node --check`로 JS 문법 검사).

**Spec:** [docs/superpowers/specs/2026-10-05-video-library-design.md](../specs/2026-10-05-video-library-design.md) — 3장(구조), 4장(영상자료실·`app/`·열기 파일·`.server.json`), 5.4(API), 6.4(나중 요청·질문), 7장(화면), 8.3(미니 서버 보안), 9장 3겹, 10장 3단계. API 약속: [docs/api.md](../../api.md).

## 사전 실험 결과 (2026-10-06, 계획 작성 전)
`http://127.0.0.1:8765`에서 YouTube IFrame API로 `40JNj2zjnQc`를 삽입한 페이지를 내장 브라우저로 열었다.
- 플레이어 준비 ✓, 오류 없음 ✓, `seekTo(754)` ✓, 재생 중 상태(1)에서 5초 동안 754.8초 → 759.8초 진행 ✓.
- **자동 재생은 막힌다**(사용자 조작 전 상태 -1). → 설계: 자동 재생하지 않는다. 주소의 `t`는 시작 위치로만 쓰고, 재생은 사용자가 누를 때.
- 결론: 설계서 12장의 미확인 위험(`127.0.0.1`에서 유튜브 재생)은 해소. 대안 화면은 필요 없다.

## Global Constraints

- 명령은 `plugin-app/` 폴더에서 실행한다. `SKILL_DIR` = `plugin/video-library/skills/video-library`, `PKG` = `SKILL_DIR/scripts/video_library`, `WEB` = `SKILL_DIR/web`, `TESTS` = `SKILL_DIR/tests`.
- 런타임은 **표준 라이브러리만**, Python 3.10 문법. 화면은 외부 라이브러리·빌드 없이 HTML·CSS·JS만(유튜브 IFrame API 스크립트만 외부에서 받음).
- 미니 서버는 **`127.0.0.1`에만** 열고 **읽기 전용**(GET만, 그 밖은 405). `Host` 헤더가 `127.0.0.1:<포트>`·`localhost:<포트>`가 아니면 403(DNS 리바인딩 차단). 포트는 8765부터 빈 번호(최대 20개). 1시간(3600초) 동안 요청이 없으면 스스로 끈다.
- 정적 파일은 `영상자료실/app/` 바로 아래의 `.html .css .js .svg .png .ico`만 내준다(하위 폴더·`.`으로 시작하는 이름·경로 조작 거부). 데이터는 `/api/...`로만 낸다.
- 응답 헤더: `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, Content-Security-Policy(아래 Task 4 값). 화면 코드는 데이터를 **`textContent`로만** 넣는다(`innerHTML` 금지 — AI가 만든 글이 들어오기 때문).
- `.server.json`(`{"port","pid","home"}`)은 영상자료실 맨 위. 서버가 켜질 때 쓰고 꺼질 때 지운다.
- 진행 카드: 2초마다 `/api/jobs`. 완료된 작업은 `updated_at`에서 60초 뒤 숨김, [×]로 바로 닫기(닫은 job id는 브라우저 `localStorage`에 최대 50개).
- 화면 문구: [영어 번역 요청] → 복사 `/video-library 번역 <ID>` + "요청 문장을 복사했습니다. video-library 플러그인이 설치된 AI 도구의 대화창에 붙여 넣으세요." / [이 강의에 질문하기] → 복사 `video-library 강의 「<제목>」(<ID>)에 대해 질문: ` + "질문 문장을 복사했습니다. video-library 플러그인이 설치된 AI 도구의 대화창에 붙여 넣고 질문을 이어 쓰세요."
- 테스트는 인터넷과 실제 문서 폴더를 쓰지 않는다(autouse `VL_HOME` 격리 유지). 서버 테스트는 같은 프로세스 안의 스레드로 띄우고 끝나면 반드시 끈다.
- 실제 영상 추가 처리(Task 10)는 설치·사용량이 드므로 **사용자 승인 후에만**.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **서버가 파일을 여는 동안 플러그인이 `index.json`·`jobs/*.json`을 바꾸는 경우(Windows)** — `os.replace`가 PermissionError로 실패하면 안 된다(2단계 미룬 사항). → Task 1 테스트.
2. **브라우저 주소로 영상자료실 밖 파일을 요청하는 경우**(`/app/..%2Findex.json`, `/app/runtime/vl.py`, `/api/lectures/..%2F..`) — 전부 404. → Task 4 테스트.
3. **다른 사이트가 내 PC 서버를 부르는 경우**(Host 헤더 위조) — 403. → Task 4 테스트.
4. **서버가 이미 켜져 있거나, 다른 프로그램이 8765를 쓰는 경우** — 켜진 서버는 다시 쓰고, 포트가 막혔으면 다음 번호를 쓴다. → Task 4·5 테스트.
5. **AI가 만든 글에 `<script>` 같은 HTML이 들어 있는 경우** — 화면에 글자 그대로 보여야 한다. → Task 6 테스트(JS에 `innerHTML` 사용 금지 검사) + Task 9 브라우저 확인.

---

## File Structure

| 파일 | 책임 |
|---|---|
| `PKG/config.py` (수정) | `os.replace` 재시도, `DEFAULT_PORT`, `server_url(home)` |
| `PKG/store_file.py` | PC용 읽기 전용 저장소: 목록·강의·진행 작업·변경 표시 |
| `PKG/search.py` | 통합 검색 메모리 색인, `vl.py search` |
| `PKG/server.py` | 미니 서버(라우팅·정적 파일·보안 헤더·유휴 종료·포트 선택), `vl.py serve` |
| `PKG/opener.py` | `app/` 설치(화면 + 서버 실행 파일 사본), 열기 파일, 서버 확인·백그라운드 시작, `vl.py open` |
| `SKILL_DIR/scripts/vl.py` (수정) | 명령 `search`, `serve`, `open` — Task 8에서 한꺼번에 등록(그 전에 등록하면 SKILL.md 문서 검사 테스트가 깨진다) |
| `WEB/app.css` | 디자인 토큰(밝은·어두운), 목록·강의 레이아웃, 좁은 화면 |
| `WEB/common.js` | `VL` 도구: API 호출, 시간·날짜 표시, 안전한 요소 생성, 강조, 복사·알림 |
| `WEB/library.html`, `WEB/library.js` | 목록 화면 |
| `WEB/lecture.html`, `WEB/lecture.js` | 강의 화면 |
| `SKILL_DIR/SKILL.md` (수정) | 0단계 열기, 열기 요청, 질문 답변 절차 |
| `docs/api.md` (수정) | `/api/health`, 진행 작업 범위, 검색 `idx` null, Host 검사 |

---

### Task 1: `config` — 파일 교체 재시도와 서버 주소

**Files:**
- Modify: `PKG/config.py`
- Test: `TESTS/test_config_server.py`

**Interfaces:**
- Produces: `DEFAULT_PORT = 8765`, `SERVER_STATE = ".server.json"`, `server_url(home) -> str` (`.server.json`의 포트, 없거나 깨졌으면 기본 포트로 `http://127.0.0.1:<포트>`), `write_text`가 `os.replace`의 `PermissionError`를 최대 10번(0.05초씩 늘려 가며) 다시 시도

- [ ] **Step 1: 실패하는 테스트 작성**

`TESTS/test_config_server.py`:
```python
import pytest

from video_library import config
from video_library.config import server_url, write_json, write_text


def test_server_url_default(home):
    assert server_url(home) == "http://127.0.0.1:8765"


def test_server_url_from_state(home):
    write_json(home / ".server.json", {"port": 8771, "pid": 1, "home": str(home)})
    assert server_url(home) == "http://127.0.0.1:8771"


def test_server_url_with_broken_state(home):
    (home / ".server.json").write_text("{깨짐", encoding="utf-8")
    assert server_url(home) == "http://127.0.0.1:8765"


def test_write_text_retries_when_file_is_busy(tmp_path, monkeypatch):
    real = config.os.replace
    calls = {"n": 0}

    def busy_twice(src, dst):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise PermissionError("[WinError 5] 다른 프로세스가 사용 중")
        return real(src, dst)

    monkeypatch.setattr(config.os, "replace", busy_twice)
    monkeypatch.setattr(config.time, "sleep", lambda s: None)
    write_text(tmp_path / "index.json", "[]\n")
    assert (tmp_path / "index.json").read_text(encoding="utf-8") == "[]\n" and calls["n"] == 3


def test_write_text_gives_up_after_retries(tmp_path, monkeypatch):
    def always_busy(src, dst):
        raise PermissionError("busy")

    monkeypatch.setattr(config.os, "replace", always_busy)
    monkeypatch.setattr(config.time, "sleep", lambda s: None)
    with pytest.raises(PermissionError):
        write_text(tmp_path / "x.json", "{}")
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_config_server.py -v`
Expected: FAIL — `ImportError: cannot import name 'server_url'`

- [ ] **Step 3: 구현**

`PKG/config.py`: import 목록에 `import time`을 추가하고, `VIDEO_ID_RE = …` 줄 아래에 추가:
```python
DEFAULT_PORT = 8765
SERVER_STATE = ".server.json"
_REPLACE_RETRIES = 10
```
`write_text` 함수 전체를 아래로 바꾸고 그 아래에 `server_url`을 추가:
```python
def _replace(src: Path, dst: Path) -> None:
    """os.replace — Windows 에서 다른 프로세스(미니 서버)가 잠깐 파일을 열고 있으면 몇 번 다시 시도한다."""
    for attempt in range(_REPLACE_RETRIES):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == _REPLACE_RETRIES - 1:
                raise
            time.sleep(0.05 * (attempt + 1))


def write_text(path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_text(text, encoding="utf-8")
    _replace(part, path)
```
(`write_json`은 그대로 `write_text`를 부른다.) 파일 맨 아래에 추가:
```python
def server_url(home: Path) -> str:
    """미니 서버 주소. 켜진 적이 없거나 기록이 깨졌으면 기본 포트."""
    port = DEFAULT_PORT
    try:
        state = read_json(Path(home) / SERVER_STATE)
        if isinstance(state.get("port"), int):
            port = state["port"]
    except (ValueError, OSError, AttributeError):
        pass
    return f"http://127.0.0.1:{port}"
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -W error`
Expected: 모두 통과(실패 0)

- [ ] **Step 5: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/config.py plugin/video-library/skills/video-library/tests/test_config_server.py
git commit -m "feat(viewer): retry busy file replaces and add server_url" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `store_file` — 영상자료실 읽기 전용 저장소

**Files:**
- Create: `PKG/store_file.py`
- Test: `TESTS/test_store_file.py`

**Interfaces:**
- Consumes: `config.VIDEO_ID_RE/lecture_dir/now_kst/read_json`, `library.index_entry`
- Produces (`video_library.store_file.FileStore(home)`):
  - `.home: Path`
  - `list_lectures() -> list[dict]` — `index.json`(배열이 아니거나 깨졌으면 `lectures/*/lecture.json`에서 메모리로 다시 만듦, 파일은 쓰지 않음), 최신이 앞
  - `get_lecture(lecture_id) -> dict | None` — ID 형식이 틀리거나 없거나 깨졌으면 None
  - `all_lectures() -> list[dict]` — 목록 순서대로 `lecture.json` 문서들(못 읽는 것은 건너뜀)
  - `list_jobs(now=None) -> list[dict]` — `running`은 모두, 그 밖은 `updated_at`이 최근 3600초 안인 것. 깨진 파일 건너뜀. `updated_at` 내림차순
  - `version() -> str` — `index.json`의 수정 시각·크기(검색 색인 갱신용), 없으면 `"none"`

- [ ] **Step 1: 실패하는 테스트 작성**

`TESTS/test_store_file.py`:
```python
from datetime import datetime, timedelta

from conftest import VIDEO_ID
from test_library import make_doc, stage
from video_library import library
from video_library.config import KST, write_json
from video_library.store_file import FileStore

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=KST)


def publish(home, vid=VIDEO_ID, processed_at="2026-10-05T14:03:00+09:00"):
    stage(home, make_doc(vid, processed_at))
    library.commit_lecture(home, vid)


def job(home, job_id, status, updated):
    write_json(home / "jobs" / f"{job_id}.json", {"job_id": job_id, "lecture_id": VIDEO_ID, "title": "t",
                                                  "status": status, "started_at": updated.isoformat(),
                                                  "updated_at": updated.isoformat(), "steps": {}, "detail": "",
                                                  "error": None})


def test_list_and_get(home):
    publish(home)
    publish(home, "ZzZzZzZzZzZ", "2026-10-06T09:00:00+09:00")
    store = FileStore(home)
    assert [e["id"] for e in store.list_lectures()] == ["ZzZzZzZzZzZ", VIDEO_ID]
    assert store.get_lecture(VIDEO_ID)["lecture"]["id"] == VIDEO_ID
    assert [d["lecture"]["id"] for d in store.all_lectures()] == ["ZzZzZzZzZzZ", VIDEO_ID]


def test_get_rejects_bad_or_missing_ids(home):
    publish(home)
    store = FileStore(home)
    assert store.get_lecture("../../x") is None
    assert store.get_lecture("NoSuchVideo") is None
    assert store.get_lecture("") is None


def test_broken_index_falls_back_without_writing(home):
    publish(home)
    (home / "index.json").write_text("{깨짐", encoding="utf-8")
    assert [e["id"] for e in FileStore(home).list_lectures()] == [VIDEO_ID]
    assert (home / "index.json").read_text(encoding="utf-8") == "{깨짐"


def test_empty_library(home):
    assert FileStore(home).list_lectures() == [] and FileStore(home).all_lectures() == []


def test_list_jobs_filters_old_finished_jobs(home):
    job(home, "running-old", "running", NOW - timedelta(days=2))
    job(home, "done-recent", "done", NOW - timedelta(minutes=5))
    job(home, "done-old", "done", NOW - timedelta(hours=2))
    job(home, "failed-recent", "failed", NOW - timedelta(minutes=30))
    (home / "jobs" / "broken.json").write_text("{깨짐", encoding="utf-8")
    ids = [j["job_id"] for j in FileStore(home).list_jobs(now=NOW)]
    assert ids == ["done-recent", "failed-recent", "running-old"]


def test_version_changes_when_index_changes(home):
    store = FileStore(home)
    assert store.version() == "none"
    publish(home)
    first = store.version()
    publish(home, "ZzZzZzZzZzZ", "2026-10-06T09:00:00+09:00")
    assert store.version() != first
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_store_file.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'video_library.store_file'`

- [ ] **Step 3: 구현**

`PKG/store_file.py`:
```python
"""PC 미니 서버용 저장소: 영상자료실 폴더를 읽기만 한다(쓰기는 플러그인 명령이 파일로 한다)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .config import VIDEO_ID_RE, lecture_dir, now_kst, read_json
from .library import index_entry

JOB_RECENT_SEC = 3600


class FileStore:
    def __init__(self, home: Path):
        self.home = Path(home)

    def list_lectures(self) -> list[dict]:
        try:
            items = read_json(self.home / "index.json")
            if isinstance(items, list):
                return items
        except (ValueError, OSError):
            pass
        items = []
        for path in sorted((self.home / "lectures").glob("*/lecture.json")):
            if "." in path.parent.name:
                continue
            try:
                items.append(index_entry(read_json(path)))
            except (ValueError, OSError, KeyError, TypeError):
                continue
        return sorted(items, key=lambda e: str(e.get("processed_at", "")), reverse=True)

    def get_lecture(self, lecture_id) -> dict | None:
        if not isinstance(lecture_id, str) or not VIDEO_ID_RE.match(lecture_id):
            return None
        try:
            doc = read_json(lecture_dir(self.home, lecture_id) / "lecture.json")
        except (ValueError, OSError):
            return None
        return doc if isinstance(doc, dict) else None

    def all_lectures(self) -> list[dict]:
        docs = []
        for entry in self.list_lectures():
            doc = self.get_lecture(entry.get("id")) if isinstance(entry, dict) else None
            if doc is not None:
                docs.append(doc)
        return docs

    def list_jobs(self, now=None) -> list[dict]:
        now = now or now_kst()
        jobs = []
        for path in (self.home / "jobs").glob("*.json"):
            try:
                job = read_json(path)
            except (ValueError, OSError):
                continue
            if not isinstance(job, dict):
                continue
            if job.get("status") == "running":
                jobs.append(job)
                continue
            try:
                updated = datetime.fromisoformat(job["updated_at"])
            except (KeyError, TypeError, ValueError):
                continue
            if (now - updated).total_seconds() <= JOB_RECENT_SEC:
                jobs.append(job)
        return sorted(jobs, key=lambda j: str(j.get("updated_at", "")), reverse=True)

    def version(self) -> str:
        try:
            st = (self.home / "index.json").stat()
        except OSError:
            return "none"
        return f"{st.st_mtime_ns}:{st.st_size}"
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -W error`
Expected: 모두 통과(실패 0)

- [ ] **Step 5: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/store_file.py plugin/video-library/skills/video-library/tests/test_store_file.py
git commit -m "feat(viewer): add read-only file store for the library" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `search` — 통합 검색 색인과 `vl.py search`

**Files:**
- Create: `PKG/search.py`
- Test: `TESTS/test_search.py`

**Interfaces:**
- Consumes: `store_file.FileStore`, `config.fmt_time/library_home/server_url/video_id_arg`
- Produces (`video_library.search`):
  - `FIELDS = ("dev", "finance", "science", "medical", "other")`, `MAX_HITS_PER_LECTURE = 20`
  - `normalize_query(text) -> str` — NFC, 소문자(casefold), 공백 제거
  - `SearchIndex(lectures: list[dict])` — `lecture.json` 문서 목록(최신이 앞)
  - `SearchIndex.search(query, field=None, video=None, limit=20) -> dict` — api.md 형식 `{"query","results":[{"id","title","field","hits":[{"where","idx","start","text"[, "lang"]}]}]}`. `where` ∈ title(idx null, start 0)·chapter·glossary·segment·translation. 빈 검색어는 결과 없음
  - `main(argv)` = `vl.py search "<검색어>" [--field F] [--video ID] [--limit N] [--json]` — 사람이 읽는 형식은 강의별로 `[h:mm:ss] (어디) 문장`과 바로 열리는 링크 `<server_url>/lecture?id=<ID>&t=<초>`

- [ ] **Step 1: 실패하는 테스트 작성**

`TESTS/test_search.py`:
```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_search.py -v`
Expected: FAIL — `ImportError: cannot import name 'search'`

- [ ] **Step 3: 구현**

`PKG/search.py`:
```python
"""전체 강의 통합 검색(메모리 색인). 미니 서버와 vl.py search 가 같이 쓴다."""
from __future__ import annotations

import argparse
import json
import unicodedata

from .config import fmt_time, library_home, server_url, video_id_arg
from .store_file import FileStore

FIELDS = ("dev", "finance", "science", "medical", "other")
MAX_HITS_PER_LECTURE = 20
_WHERE_LABELS = {"title": "제목", "chapter": "목차", "glossary": "용어집", "segment": "전사", "translation": "번역"}


def normalize_query(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFC", text).casefold() if not ch.isspace())


def _walk(chapters: list):
    for ch in chapters:
        yield ch
        yield from _walk(ch.get("children") or [])


class SearchIndex:
    def __init__(self, lectures: list[dict]):
        self._docs = []
        for doc in lectures:
            lec = doc["lecture"]
            starts = {s["idx"]: s["start"] for s in doc["segments"]}
            rows = [("title", None, 0.0, lec["title"], None)]
            for ch in _walk(doc["chapters"]):
                rows.append(("chapter", ch["segments"][0], ch["start"], f"{ch['title']} — {ch['summary']}", None))
            for g in doc["glossary"]:
                rows.append(("glossary", g["idx"], starts.get(g["idx"], 0.0), f"{g['term']}: {g['definition']}", None))
            for s in doc["segments"]:
                rows.append(("segment", s["idx"], s["start"], s["text"], lec["language"]))
            for lang, items in doc["translations"].items():
                for it in items:
                    rows.append(("translation", it["idx"], starts.get(it["idx"], 0.0), it["text"], lang))
            self._docs.append((lec, [(w, i, t, text, lang, normalize_query(text)) for w, i, t, text, lang in rows]))

    def search(self, query: str, field: str | None = None, video: str | None = None,
               limit: int = MAX_HITS_PER_LECTURE) -> dict:
        needle = normalize_query(query or "")
        results = []
        if needle:
            for lec, rows in self._docs:
                if (field and lec["field"] != field) or (video and lec["id"] != video):
                    continue
                hits = []
                for where, idx, start, text, lang, normed in rows:
                    if needle in normed:
                        hit = {"where": where, "idx": idx, "start": start, "text": text}
                        if lang:
                            hit["lang"] = lang
                        hits.append(hit)
                        if len(hits) >= limit:
                            break
                if hits:
                    results.append({"id": lec["id"], "title": lec["title"], "field": lec["field"], "hits": hits})
        return {"query": query, "results": results}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py search", description="영상자료실의 모든 강의에서 검색한다(대화창 질문 답변용).")
    ap.add_argument("query", help="검색어")
    ap.add_argument("--field", choices=FIELDS, default=None)
    ap.add_argument("--video", type=video_id_arg, default=None, help="이 강의 안에서만")
    ap.add_argument("--limit", type=int, default=MAX_HITS_PER_LECTURE)
    ap.add_argument("--json", action="store_true", help="JSON 으로 출력")
    a = ap.parse_args(argv)
    home = library_home()
    result = SearchIndex(FileStore(home).all_lectures()).search(a.query, a.field, a.video, a.limit)
    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if not result["results"]:
        print("검색 결과가 없습니다.")
        return 0
    base = server_url(home)
    for r in result["results"]:
        print(f"■ {r['title']} ({r['id']})")
        for h in r["hits"]:
            label = _WHERE_LABELS[h["where"]] + (f" {h['lang'].upper()}" if h.get("lang") else "")
            print(f"  [{fmt_time(h['start'])}] ({label}) {h['text'][:160]}")
            print(f"    {base}/lecture?id={r['id']}&t={int(h['start'])}")
    return 0
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -W error`
Expected: 모두 통과(실패 0)

- [ ] **Step 5: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/search.py plugin/video-library/skills/video-library/tests/test_search.py
git commit -m "feat(viewer): add in-memory search index and search command" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `server` — PC 전용 미니 서버와 `vl.py serve`

**Files:**
- Create: `PKG/server.py`
- Test: `TESTS/test_server.py`

**Interfaces:**
- Consumes: `store_file.FileStore`, `search.SearchIndex`, `config.*`
- Produces (`video_library.server`):
  - `IDLE_TIMEOUT_SEC = 3600`, `PORT_RANGE = 20`, `CSP`(문자열)
  - `LibraryServer(addr, store, web_dir, idle_timeout=IDLE_TIMEOUT_SEC)` — `ThreadingHTTPServer`, `allow_reuse_address = False`, `.port`, `.touch()`, `.idle() -> bool`, `.search_index()`(저장소 `version()`이 바뀌면 다시 만듦)
  - `bind(store, web_dir, port=DEFAULT_PORT, idle_timeout=…) -> LibraryServer` — `port`부터 20개 중 빈 번호. 모두 막히면 `StepError`
  - `run(server, state_path, check_every=30.0) -> None` — `.server.json` 기록 → 요청 처리 → 유휴 시간이 지나면 스스로 끔 → 끝나면 (자기 pid일 때) `.server.json` 삭제
  - 경로: `GET /`(library.html), `GET /lecture`(lecture.html), `GET /app/<파일>`, `GET /api/health`(`{"app":"video-library","home":…}`), `/api/lectures`, `/api/lectures/<id>`, `/api/search?q=&field=&video=`, `/api/jobs`. 그 밖 404, GET 아닌 요청 405, Host 불일치 403, 처리 중 예외 500(서버는 계속)
  - `main(argv)` = `vl.py serve [--port N] [--idle SEC]`

- [ ] **Step 1: 실패하는 테스트 작성**

`TESTS/test_server.py`:
```python
import http.client
import json
import socket
import threading
import time

import pytest

from conftest import VIDEO_ID
from test_library import make_doc, stage
from video_library import library
from video_library.config import read_json
from video_library.server import CSP, LibraryServer, bind, run
from video_library.store_file import FileStore

PAGES = {"library.html": "<!doctype html><title>목록</title>", "lecture.html": "<!doctype html><title>강의</title>",
         "app.css": "body{}", "common.js": "var VL={};", "secret.txt": "비밀"}


def make_web(home):
    web = home / "app"
    (web / "runtime").mkdir(parents=True, exist_ok=True)
    for name, body in PAGES.items():
        (web / name).write_text(body, encoding="utf-8")
    (web / "runtime" / "vl.py").write_text("print('runtime')", encoding="utf-8")
    return web


@pytest.fixture
def live(home):
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)
    server = LibraryServer(("127.0.0.1", 0), FileStore(home), make_web(home))
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def get(server, path, method="GET", host=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    headers = {"Host": host} if host else {}
    conn.request(method, path, headers=headers)
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    return resp, body


def get_json(server, path):
    resp, body = get(server, path)
    return resp.status, json.loads(body.decode("utf-8"))


def test_pages_and_security_headers(live):
    resp, body = get(live, "/")
    assert resp.status == 200 and "목록" in body.decode("utf-8")
    assert resp.getheader("Content-Security-Policy") == CSP
    assert resp.getheader("Cache-Control") == "no-store"
    assert resp.getheader("X-Content-Type-Options") == "nosniff"
    resp, body = get(live, f"/lecture?id={VIDEO_ID}&t=10")
    assert resp.status == 200 and "강의" in body.decode("utf-8")
    resp, _ = get(live, "/app/app.css")
    assert resp.status == 200 and resp.getheader("Content-Type").startswith("text/css")


@pytest.mark.parametrize("path", ["/app/..%2Findex.json", "/app/runtime/vl.py", "/app/runtime%2Fvl.py",
                                  "/app/.server.json", "/app/secret.txt", "/app/", "/index.json",
                                  f"/lectures/{VIDEO_ID}/lecture.json"])
def test_files_outside_app_are_not_served(live, path):
    resp, _ = get(live, path)
    assert resp.status == 404


def test_api_lectures(live):
    status, data = get_json(live, "/api/lectures")
    assert status == 200 and [e["id"] for e in data] == [VIDEO_ID]
    status, doc = get_json(live, f"/api/lectures/{VIDEO_ID}")
    assert status == 200 and doc["lecture"]["id"] == VIDEO_ID
    status, err = get_json(live, "/api/lectures/..%2F..%2Fx")
    assert status == 404 and "error" in err
    status, err = get_json(live, "/api/lectures/NoSuchVideo")
    assert status == 404


def test_api_search_and_refresh(live, home):
    status, data = get_json(live, "/api/search?q=%EB%B8%8C%EB%9E%9C%EC%B9%98")  # 브랜치
    assert status == 200 and data["results"][0]["id"] == VIDEO_ID
    stage(home, make_doc("ZzZzZzZzZzZ", "2026-10-06T09:00:00+09:00", title="새 강의 브랜치"))
    library.commit_lecture(home, "ZzZzZzZzZzZ")
    status, data = get_json(live, "/api/search?q=%EB%B8%8C%EB%9E%9C%EC%B9%98")
    assert [r["id"] for r in data["results"]] == ["ZzZzZzZzZzZ", VIDEO_ID]
    status, data = get_json(live, f"/api/search?q=%EB%B8%8C%EB%9E%9C%EC%B9%98&video={VIDEO_ID}")
    assert [r["id"] for r in data["results"]] == [VIDEO_ID]


def test_api_jobs_and_health(live, home):
    status, data = get_json(live, "/api/jobs")
    assert status == 200 and data == []
    status, data = get_json(live, "/api/health")
    assert data == {"app": "video-library", "home": str(home)}


def test_write_methods_rejected(live):
    for method in ("POST", "PUT", "DELETE", "PATCH"):
        resp, _ = get(live, "/api/lectures", method=method)
        assert resp.status == 405


def test_foreign_host_rejected(live):
    resp, _ = get(live, "/api/lectures", host="evil.example:80")
    assert resp.status == 403
    resp, _ = get(live, "/api/lectures", host=f"localhost:{live.port}")
    assert resp.status == 200


def test_store_errors_become_500(live, monkeypatch):
    def boom():
        raise RuntimeError("디스크 오류")
    monkeypatch.setattr(live.store, "list_lectures", boom)
    resp, _ = get(live, "/api/lectures")
    assert resp.status == 500
    assert get(live, "/api/jobs")[0].status == 200  # 서버는 계속 동작


def test_bind_skips_busy_port(home):
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", 0))
    busy = blocker.getsockname()[1]
    blocker.listen()
    try:
        server = bind(FileStore(home), make_web(home), port=busy)
        assert server.port != busy and busy < server.port < busy + 20
        server.server_close()
    finally:
        blocker.close()


def test_run_writes_state_and_stops_when_idle(home):
    server = LibraryServer(("127.0.0.1", 0), FileStore(home), make_web(home), idle_timeout=0.3)
    state = home / ".server.json"
    thread = threading.Thread(target=run, args=(server, state), kwargs={"check_every": 0.1}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 3
    while not state.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert read_json(state)["port"] == server.port
    thread.join(timeout=5)
    assert not thread.is_alive() and not state.exists()
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_server.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'video_library.server'`

- [ ] **Step 3: 구현**

`PKG/server.py`:
```python
"""PC 전용 미니 서버(127.0.0.1). 영상자료실을 읽기 전용으로 보여 준다. 표준 라이브러리만."""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .config import DEFAULT_PORT, SERVER_STATE, StepError, ensure_home, library_home, read_json, write_json
from .search import SearchIndex
from .store_file import FileStore

IDLE_TIMEOUT_SEC = 3600
PORT_RANGE = 20
PAGES = {"/": "library.html", "/lecture": "lecture.html"}
STATIC_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml",
                ".png": "image/png", ".ico": "image/x-icon"}
CSP = ("default-src 'self'; script-src 'self' https://www.youtube.com https://s.ytimg.com; "
       "frame-src https://www.youtube.com https://www.youtube-nocookie.com; "
       "img-src 'self' https://i.ytimg.com data:; style-src 'self' 'unsafe-inline'; "
       "connect-src 'self'; object-src 'none'; base-uri 'none'")


class LibraryServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False  # Windows 에서 같은 포트를 두 서버가 나눠 쓰지 않게

    def __init__(self, addr, store: FileStore, web_dir: Path, idle_timeout: float = IDLE_TIMEOUT_SEC):
        super().__init__(addr, _Handler)
        self.store = store
        self.web_dir = Path(web_dir)
        self.idle_timeout = idle_timeout
        self.port = self.server_address[1]
        self._last_seen = time.monotonic()
        self._lock = threading.Lock()
        self._index = None
        self._index_version = None

    def touch(self) -> None:
        self._last_seen = time.monotonic()

    def idle(self) -> bool:
        return time.monotonic() - self._last_seen > self.idle_timeout

    def search_index(self) -> SearchIndex:
        with self._lock:
            version = self.store.version()
            if self._index is None or version != self._index_version:
                self._index = SearchIndex(self.store.all_lectures())
                self._index_version = version
            return self._index


class _Handler(BaseHTTPRequestHandler):
    server_version = "video-library"

    def log_message(self, fmt, *args):  # 콘솔을 조용히 둔다
        pass

    def do_GET(self):
        self.server.touch()
        if not self._host_ok():
            return self._error(403, "허용되지 않은 접근입니다")
        parts = urlsplit(self.path)
        path, query = parts.path, parse_qs(parts.query)
        try:
            if path in PAGES:
                return self._static(PAGES[path])
            if path.startswith("/app/"):
                return self._static(path[len("/app/"):])
            if path == "/api/health":
                return self._json(200, {"app": "video-library", "home": str(self.server.store.home)})
            if path == "/api/lectures":
                return self._json(200, self.server.store.list_lectures())
            if path.startswith("/api/lectures/"):
                doc = self.server.store.get_lecture(unquote(path[len("/api/lectures/"):]))
                return self._json(200, doc) if doc else self._error(404, "강의를 찾을 수 없습니다")
            if path == "/api/search":
                first = lambda key: (query.get(key) or [None])[0] or None
                return self._json(200, self.server.search_index().search(first("q") or "", first("field"), first("video")))
            if path == "/api/jobs":
                return self._json(200, self.server.store.list_jobs())
            return self._error(404, "없는 주소입니다")
        except Exception as exc:  # 한 요청의 오류로 서버가 멈추지 않게
            return self._error(500, f"서버 오류: {type(exc).__name__}")

    def _reject_write(self):
        self.server.touch()
        self._error(405, "읽기 전용 서버입니다")

    do_POST = do_PUT = do_DELETE = do_PATCH = _reject_write

    def _host_ok(self) -> bool:
        host = self.headers.get("Host", "")
        return host in (f"127.0.0.1:{self.server.port}", f"localhost:{self.server.port}")

    def _static(self, name: str):
        name = unquote(name)
        if not name or "/" in name or "\\" in name or name.startswith("."):
            return self._error(404, "없는 파일입니다")
        path = self.server.web_dir / name
        ctype = STATIC_TYPES.get(path.suffix.lower())
        if ctype is None or not path.is_file():
            return self._error(404, "없는 파일입니다")
        self._send(200, ctype, path.read_bytes())

    def _json(self, status: int, data) -> None:
        self._send(status, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _error(self, status: int, message: str) -> None:
        self._json(status, {"error": message})

    def _send(self, status: int, ctype: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        self.wfile.write(body)


def bind(store: FileStore, web_dir: Path, port: int = DEFAULT_PORT,
         idle_timeout: float = IDLE_TIMEOUT_SEC) -> LibraryServer:
    last = None
    for candidate in range(port, port + PORT_RANGE):
        try:
            return LibraryServer(("127.0.0.1", candidate), store, web_dir, idle_timeout)
        except OSError as exc:
            last = exc
    raise StepError(f"빈 포트를 찾지 못했습니다({port}~{port + PORT_RANGE - 1}): {last}")


def run(server: LibraryServer, state_path: Path, check_every: float = 30.0) -> None:
    write_json(state_path, {"port": server.port, "pid": os.getpid(), "home": str(server.store.home)})
    stop = threading.Event()

    def watchdog():
        while not stop.wait(check_every):
            if server.idle():
                server.shutdown()
                return

    threading.Thread(target=watchdog, daemon=True).start()
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        stop.set()
        server.server_close()
        try:
            if read_json(state_path).get("pid") == os.getpid():
                state_path.unlink()
        except (ValueError, OSError, AttributeError):
            pass


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py serve", description="영상자료실 화면을 보여 주는 PC 전용 미니 서버(보통 vl.py open 이 켠다).")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--idle", type=float, default=IDLE_TIMEOUT_SEC, help="이 시간(초) 동안 요청이 없으면 끈다")
    a = ap.parse_args(argv)
    home = ensure_home(library_home())
    web = home / "app"
    if not (web / "library.html").exists():
        raise StepError("화면 파일이 없습니다. 'vl.py open' 으로 여세요.")
    server = bind(FileStore(home), web, a.port, a.idle)
    print(f"영상자료실: http://127.0.0.1:{server.port}  (1시간 동안 쓰지 않으면 스스로 꺼집니다)", flush=True)
    run(server, home / SERVER_STATE)
    return 0
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -W error`
Expected: 모두 통과(실패 0)

- [ ] **Step 5: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/server.py plugin/video-library/skills/video-library/tests/test_server.py
git commit -m "feat(viewer): add read-only local server with security checks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `opener` — 화면 설치·열기 파일·`vl.py open`

**Files:**
- Create: `PKG/opener.py`
- Create: `WEB/library.html` (임시 한 줄 — Task 6에서 완성. 설치 테스트에 파일이 필요)
- Test: `TESTS/test_opener.py`

**Interfaces:**
- Consumes: `config.*`, `server.LibraryServer/run`(테스트), `store_file.FileStore`(테스트)
- Produces (`video_library.opener`):
  - `SCRIPTS_DIR`, `WEB_SRC`(플러그인 안의 `scripts/`, `web/`)
  - `install_app(home) -> Path` — `web/`의 파일을 `app/`에 복사, `scripts/`를 `app/runtime/`으로 교체 복사(`__pycache__` 제외), 열기 파일 작성. 이미 `app/runtime`에서 실행 중이면 아무것도 하지 않음. runtime 교체가 OS 사정으로 실패하면 경고만
  - `write_launcher(home, runtime: Path) -> Path` — Windows `영상자료실 열기.bat`, 그 밖 `영상자료실 열기.command`(실행 권한). 내용은 설치할 때의 `sys.executable`로 `app/runtime/vl.py open` 실행
  - `server_alive(home) -> str | None` — `.server.json` 포트로 `/api/health`(1초) → 같은 영상자료실이면 주소
  - `ensure_server(home, starter=None, wait=10.0) -> str` — 살아 있으면 그 주소, 아니면 `starter(home)` 후 기다림, 끝내 안 되면 `StepError`
  - `start_detached(home) -> None` — `app/runtime/vl.py serve`를 백그라운드로(Windows `DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP`, 그 밖 `start_new_session`), 출력은 `app/server.log`, 환경변수 `VL_HOME`·`PYTHONDONTWRITEBYTECODE=1`
  - `open_library(home, browser=True, starter=None) -> str`
  - `main(argv)` = `vl.py open [--no-browser]` → `{"url","home"}` JSON 출력

- [ ] **Step 1: 임시 화면 파일과 실패하는 테스트 작성**

`WEB/library.html` (Task 6에서 전체 내용으로 바꾼다):
```html
<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>영상자료실</title></head><body></body></html>
```

`TESTS/test_opener.py`:
```python
import json
import sys
import threading

import pytest

from video_library import opener
from video_library.config import StepError, write_json
from video_library.server import LibraryServer, run
from video_library.store_file import FileStore


def start_in_thread(home):
    server = LibraryServer(("127.0.0.1", 0), FileStore(home), home / "app")
    thread = threading.Thread(target=run, args=(server, home / ".server.json"), kwargs={"check_every": 0.1}, daemon=True)
    thread.start()
    return server


def wait_alive(home):
    for _ in range(50):
        url = opener.server_alive(home)
        if url:
            return url
        threading.Event().wait(0.05)
    return None


def test_install_copies_web_and_runtime(home, monkeypatch):
    monkeypatch.setattr(opener.sys, "platform", "win32")
    app = opener.install_app(home)
    assert (app / "library.html").exists()
    assert (app / "runtime" / "vl.py").exists() and (app / "runtime" / "video_library" / "server.py").exists()
    assert not list((app / "runtime").rglob("__pycache__"))
    bat = home / "영상자료실 열기.bat"
    text = bat.read_text(encoding="utf-8")
    assert sys.executable in text and r"app\runtime\vl.py" in text and "open" in text


def test_reinstall_replaces_runtime(home):
    opener.install_app(home)
    stale = home / "app" / "runtime" / "stale.py"
    stale.write_text("old", encoding="utf-8")
    opener.install_app(home)
    assert not stale.exists() and (home / "app" / "runtime" / "vl.py").exists()


def test_install_from_runtime_copy_is_noop(home, monkeypatch):
    opener.install_app(home)
    marker = home / "app" / "library.html"
    marker.write_text("사용자 사본", encoding="utf-8")
    monkeypatch.setattr(opener, "SCRIPTS_DIR", home / "app" / "runtime")
    opener.install_app(home)
    assert marker.read_text(encoding="utf-8") == "사용자 사본"


def test_mac_launcher(home, monkeypatch):
    monkeypatch.setattr(opener.sys, "platform", "darwin")
    path = opener.write_launcher(home, home / "app" / "runtime")
    assert path.name == "영상자료실 열기.command"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("#!/bin/sh") and "app/runtime/vl.py" in text


def test_server_alive_and_reuse(home):
    opener.install_app(home)
    server = start_in_thread(home)
    try:
        assert wait_alive(home) == f"http://127.0.0.1:{server.port}"
        called = []
        assert opener.ensure_server(home, starter=called.append) == f"http://127.0.0.1:{server.port}"
        assert called == []
    finally:
        server.shutdown()


def test_server_alive_rejects_other_library(home, tmp_path):
    opener.install_app(home)
    server = start_in_thread(home)
    try:
        assert wait_alive(home)
        other = tmp_path / "다른 자료실"
        other.mkdir()
        write_json(other / ".server.json", {"port": server.port, "pid": 1, "home": str(other)})
        assert opener.server_alive(other) is None
    finally:
        server.shutdown()


def test_ensure_server_starts_when_down(home):
    opener.install_app(home)
    started = []

    def starter(h):
        started.append(start_in_thread(h))

    url = opener.ensure_server(home, starter=starter)
    try:
        assert url == f"http://127.0.0.1:{started[0].port}"
    finally:
        started[0].shutdown()


def test_ensure_server_gives_up(home):
    with pytest.raises(StepError, match="미니 서버를 켜지 못했습니다"):
        opener.ensure_server(home, starter=lambda h: None, wait=0.3)


def test_open_command_without_browser(home, monkeypatch, capsys):
    started = []
    monkeypatch.setattr(opener, "start_detached", lambda h: started.append(start_in_thread(h)))
    opened = []
    monkeypatch.setattr(opener.webbrowser, "open", opened.append)
    try:
        assert opener.main(["--no-browser"]) == 0
        out = json.loads(capsys.readouterr().out)
        assert out["url"] == f"http://127.0.0.1:{started[0].port}" and opened == []
    finally:
        started[0].shutdown()
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_opener.py -v`
Expected: FAIL — `ImportError: cannot import name 'opener'`

- [ ] **Step 3: 구현**

`PKG/opener.py`:
```python
"""영상자료실 열기: 화면·서버 실행 파일 설치(app/), 더블클릭 열기 파일, 미니 서버 확인·시작, 브라우저 열기."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

from .config import SERVER_STATE, StepError, ensure_home, library_home, read_json

SCRIPTS_DIR = Path(__file__).resolve().parent.parent  # 플러그인의 scripts/ (또는 영상자료실 app/runtime/)
WEB_SRC = SCRIPTS_DIR.parent / "web"
LAUNCHER_WIN = "영상자료실 열기.bat"
LAUNCHER_MAC = "영상자료실 열기.command"


def _same(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def write_launcher(home: Path, runtime: Path) -> Path:
    python = sys.executable
    if sys.platform == "win32":
        path = home / LAUNCHER_WIN
        text = ("@echo off\r\nchcp 65001 >nul\r\n"
                f'"{python}" "%~dp0app\\runtime\\vl.py" open\r\n'
                "if errorlevel 1 pause\r\n")
        path.write_text(text, encoding="utf-8", newline="")
    else:
        path = home / LAUNCHER_MAC
        text = f'#!/bin/sh\ncd "$(dirname "$0")"\nexec "{python}" "app/runtime/vl.py" open\n'
        path.write_text(text, encoding="utf-8", newline="\n")
        path.chmod(0o755)
    return path


def install_app(home: Path) -> Path:
    app = home / "app"
    runtime = app / "runtime"
    if _same(SCRIPTS_DIR, runtime):
        return app  # 영상자료실의 사본에서 실행 중 — 자기 자신을 덮어쓰지 않는다
    app.mkdir(parents=True, exist_ok=True)
    for src in WEB_SRC.iterdir():
        if src.is_file():
            shutil.copy2(src, app / src.name)
    fresh, old = app / "runtime.new", app / "runtime.old"
    for leftover in (fresh, old):
        if leftover.exists():
            shutil.rmtree(leftover, ignore_errors=True)
    shutil.copytree(SCRIPTS_DIR, fresh, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    try:
        if runtime.exists():
            os.replace(runtime, old)
        os.replace(fresh, runtime)
        shutil.rmtree(old, ignore_errors=True)
    except OSError as exc:
        print(f"경고: 서버 실행 파일을 새로 바꾸지 못했습니다({exc}) — 이전 사본으로 계속합니다.", file=sys.stderr)
        if not runtime.exists() and old.exists():
            os.replace(old, runtime)
    write_launcher(home, runtime)
    return app


def server_alive(home: Path) -> str | None:
    try:
        state = read_json(home / SERVER_STATE)
        port = int(state["port"])
    except (ValueError, OSError, KeyError, TypeError):
        return None
    url = f"http://127.0.0.1:{port}"
    no_proxy = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 시스템 프록시를 거치지 않는다
    try:
        with no_proxy.open(f"{url}/api/health", timeout=1) as resp:
            info = json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    if info.get("app") == "video-library" and Path(info.get("home", "")) == Path(home):
        return url
    return None


def start_detached(home: Path) -> None:
    runtime_vl = home / "app" / "runtime" / "vl.py"
    env = {**os.environ, "VL_HOME": str(home), "PYTHONDONTWRITEBYTECODE": "1"}
    kwargs = {"stdin": subprocess.DEVNULL, "cwd": str(home), "env": env}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    with open(home / "app" / "server.log", "ab") as log:
        subprocess.Popen([sys.executable, str(runtime_vl), "serve"], stdout=log, stderr=log, **kwargs)


def ensure_server(home: Path, starter=None, wait: float = 10.0) -> str:
    url = server_alive(home)
    if url:
        return url
    (starter or start_detached)(home)
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        time.sleep(0.2)
        url = server_alive(home)
        if url:
            return url
    raise StepError("미니 서버를 켜지 못했습니다. 영상자료실/app/server.log 를 확인하세요.")


def open_library(home: Path, browser: bool = True, starter=None) -> str:
    ensure_home(home)
    install_app(home)
    url = ensure_server(home, starter=starter or start_detached)
    if browser:
        webbrowser.open(url)
    return url


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py open", description="영상자료실 화면을 연다(미니 서버가 꺼져 있으면 켠다).")
    ap.add_argument("--no-browser", action="store_true", help="브라우저는 열지 않고 주소만 출력")
    a = ap.parse_args(argv)
    home = library_home()
    url = open_library(home, browser=not a.no_browser)
    print(json.dumps({"url": url, "home": str(home)}, ensure_ascii=False))
    return 0
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -W error`
Expected: 모두 통과(실패 0)

- [ ] **Step 5: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/opener.py plugin/video-library/skills/video-library/web/library.html plugin/video-library/skills/video-library/tests/test_opener.py
git commit -m "feat(viewer): install app files, launcher, and open command" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: 공통 화면 파일 + 목록 화면

**Files:**
- Create: `WEB/app.css`, `WEB/common.js`, `WEB/library.js`
- Modify: `WEB/library.html` (전체 내용)
- Test: `TESTS/test_web_assets.py`

**Interfaces:**
- Consumes: `/api/lectures`, `/api/search`, `/api/jobs`(api.md)
- Produces: 전역 `VL` 객체(`FIELD_LABELS`, `api(path)`, `fmtTime(sec)`, `fmtDate(iso)`, `fmtElapsed(ms)`, `el(tag, attrs, ...children)`, `highlight(text, query)`, `toast(msg)`, `copy(text, msg)`, `langPair(language, translations)`), `$`(querySelector 줄임). 강의 화면(Task 7)이 그대로 쓴다.
- 화면 요소 id(테스트가 HTML과 JS를 대조): 목록 `search`, `filters`, `jobs`, `results`, `list`, `empty`, `toast`

UI 동작은 Task 9 브라우저 확인으로 검증한다(JS 단위 테스트 도구를 들이지 않음). 여기서 자동 테스트는 **HTML–JS 연결(요소 id), 스크립트 경로, `innerHTML` 금지, JS 문법**을 지킨다.

- [ ] **Step 1: 실패하는 테스트 작성**

`TESTS/test_web_assets.py`:
```python
import re
import shutil
import subprocess
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parent.parent / "web"
PAIRS = [("library.html", "library.js")]


def read(name):
    return (WEB / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("html, js", PAIRS)
def test_every_element_id_used_by_js_exists_in_html(html, js):
    used = set(re.findall(r"\$\(\"#([\w-]+)\"\)", read(js)))
    declared = set(re.findall(r'id="([\w-]+)"', read(html)))
    assert used and used <= declared, used - declared


@pytest.mark.parametrize("html, js", PAIRS)
def test_html_loads_shared_files_from_app(html, js):
    page = read(html)
    assert '<link rel="stylesheet" href="/app/app.css">' in page
    assert '<script src="/app/common.js"></script>' in page and f'<script src="/app/{js}"></script>' in page
    assert '<meta name="viewport"' in page and 'lang="ko"' in page


def test_no_inner_html_anywhere():
    for path in WEB.glob("*.js"):
        assert "innerHTML" not in path.read_text(encoding="utf-8"), path.name
        assert "insertAdjacentHTML" not in path.read_text(encoding="utf-8"), path.name


def test_css_has_dark_mode_and_narrow_layout():
    css = read("app.css")
    assert "prefers-color-scheme: dark" in css and "@media (max-width:" in css


@pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
def test_js_syntax():
    for path in WEB.glob("*.js"):
        proc = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_web_assets.py -v`
Expected: FAIL — `FileNotFoundError`(library.js 없음) 등

- [ ] **Step 3: 화면 파일 작성**

`WEB/app.css`:
```css
:root {
  --bg: #f6f6f4; --surface: #ffffff; --surface-2: #f0f1f3; --text: #1d1f23; --muted: #6b7079;
  --line: #e2e4e8; --accent: #2f5bd3; --accent-soft: #e8eefc; --ok: #1f8a4c; --ok-soft: #e6f4ec;
  --warn: #b25b00; --warn-soft: #fff1e0; --bad: #c62f2f; --bad-soft: #fdeaea; --mark: #fff2a8;
  --radius: 12px; --shadow: 0 1px 2px rgba(0,0,0,.06);
  --font: system-ui, -apple-system, "Segoe UI", "Malgun Gothic", "Apple SD Gothic Neo", sans-serif;
  --mono: ui-monospace, "Cascadia Mono", Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #15171b; --surface: #1d2025; --surface-2: #262a31; --text: #e8eaee; --muted: #9aa1ad;
    --line: #2e333b; --accent: #7aa2ff; --accent-soft: #23304d; --ok: #5cc98a; --ok-soft: #1d3327;
    --warn: #f0a85a; --warn-soft: #3a2a17; --bad: #ff7b7b; --bad-soft: #3d1f22; --mark: #5a4d12;
  }
}
* { box-sizing: border-box; }
html, body { margin: 0; }
body { background: var(--bg); color: var(--text); font: 15px/1.6 var(--font); }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
button { font: inherit; color: inherit; }
[hidden] { display: none !important; }
.muted { color: var(--muted); }
mark { background: var(--mark); color: inherit; border-radius: 3px; }

.topbar { position: sticky; top: 0; z-index: 10; display: flex; align-items: center; gap: 16px;
  padding: 12px 24px; background: var(--surface); border-bottom: 1px solid var(--line); }
.brand { margin: 0; font-size: 20px; }
.topbar input[type=search] { margin-left: auto; width: min(420px, 45vw); padding: 9px 14px;
  border: 1px solid var(--line); border-radius: 10px; background: var(--surface-2); color: var(--text); font: inherit; }
.container { max-width: 1040px; margin: 0 auto; padding: 20px 16px 60px; }

.btn { display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; border: 1px solid var(--line);
  border-radius: 10px; background: var(--surface); cursor: pointer; white-space: nowrap; }
.btn:hover { background: var(--surface-2); text-decoration: none; }
.btn.small { padding: 4px 10px; font-size: 13px; }
.btn.ghost { border-color: transparent; background: transparent; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.chip { padding: 6px 14px; border: 1px solid var(--line); border-radius: 999px; background: var(--surface); cursor: pointer; }
.chip.active { background: var(--accent); border-color: var(--accent); color: #fff; }
.tag { display: inline-block; padding: 1px 8px; border-radius: 6px; background: var(--accent-soft); color: var(--accent); font-size: 12px; }
.tag.lang { background: var(--surface-2); color: var(--muted); }

.job { background: var(--surface); border: 1.5px solid var(--accent); border-radius: var(--radius);
  padding: 14px 16px; margin-bottom: 12px; box-shadow: var(--shadow); }
.job.failed { border-color: var(--bad); }
.job-head { display: flex; align-items: center; gap: 12px; }
.job-title { flex: 1; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.job-status { color: var(--muted); font-size: 14px; }
.steps { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.step { padding: 2px 8px; border-radius: 6px; font-size: 13px; background: var(--surface-2); color: var(--muted); }
.step.done { background: var(--ok-soft); color: var(--ok); }
.step.running { background: var(--accent-soft); color: var(--accent); font-weight: 600; }
.step.failed { background: var(--bad-soft); color: var(--bad); font-weight: 600; }
.step.skipped { opacity: .45; text-decoration: line-through; }
.job-error { margin-top: 8px; color: var(--bad); font-size: 14px; }

.card { display: grid; grid-template-columns: 176px 1fr auto; align-items: center; gap: 18px;
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
  padding: 14px; margin-bottom: 12px; box-shadow: var(--shadow); }
.thumb img { display: block; width: 176px; aspect-ratio: 16 / 9; object-fit: cover; border-radius: 8px; background: var(--surface-2); }
.card-title { display: block; font-size: 17px; font-weight: 600; color: var(--text); margin-bottom: 6px; }
.meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; color: var(--muted); font-size: 14px; }
.empty { padding: 40px 0; text-align: center; color: var(--muted); }

.result { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 14px 16px; margin-bottom: 12px; }
.result-title { margin: 0 0 8px; font-size: 16px; }
.hits { list-style: none; margin: 0; padding: 0; }
.hits li a { display: grid; grid-template-columns: 72px 70px 1fr; gap: 10px; padding: 6px 4px; color: var(--text); border-radius: 6px; }
.hits li a:hover { background: var(--surface-2); text-decoration: none; }
.time { font-family: var(--mono); color: var(--muted); font-size: 13px; }
.where { font-size: 12px; color: var(--accent); }

.toast { position: fixed; left: 50%; bottom: 28px; transform: translateX(-50%); max-width: min(560px, 92vw);
  padding: 12px 18px; border-radius: 10px; background: #222; color: #fff; box-shadow: 0 6px 20px rgba(0,0,0,.25); z-index: 50; }

/* 강의 화면 */
.page-lecture .topbar { gap: 12px; }
.back { white-space: nowrap; color: var(--muted); }
.lecture-title { margin: 0; font-size: 17px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.badges { display: flex; gap: 6px; white-space: nowrap; }
.lecture-layout { display: grid; grid-template-columns: minmax(0, 1fr) 420px; gap: 20px; padding: 20px; max-width: 1500px; margin: 0 auto; }
.panel { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); }
.player-box { padding: 16px; }
.player-wrap { position: relative; aspect-ratio: 16 / 9; background: #000; border-radius: 10px; overflow: hidden; }
.player-wrap iframe, .player-wrap #player { position: absolute; inset: 0; width: 100%; height: 100%; }
.ticks { position: relative; height: 10px; margin: 12px 0 6px; background: var(--surface-2); border-radius: 5px; cursor: pointer; }
.ticks .progress { position: absolute; left: 0; top: 0; bottom: 0; background: var(--accent-soft); border-radius: 5px; }
.ticks .tick { position: absolute; top: -2px; width: 2px; height: 14px; background: var(--muted); }
.controls { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.clock { font-family: var(--mono); }
.speeds { display: inline-flex; gap: 6px; }
.speeds .btn.active { border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }
.shortcuts { margin: 8px 0 0; color: var(--muted); font-size: 13px; }
.transcript-box { margin-top: 16px; display: flex; flex-direction: column; }
.box-head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 12px 16px; border-bottom: 1px solid var(--line); }
.box-head h2 { margin: 0 8px 0 0; font-size: 16px; }
.seg { display: inline-flex; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
.seg button { border: 0; padding: 4px 10px; background: var(--surface); cursor: pointer; font-size: 13px; }
.seg button.active { background: var(--accent); color: #fff; }
.transcript { list-style: none; margin: 0; padding: 6px 0; max-height: 46vh; overflow-y: auto; }
.transcript li { display: grid; grid-template-columns: 76px 1fr; gap: 10px; padding: 6px 16px; cursor: pointer; }
.transcript li:hover { background: var(--surface-2); }
.transcript li.active { background: var(--accent-soft); }
.transcript .tr { display: block; color: var(--muted); }
.actions { display: flex; gap: 8px; padding: 12px 16px; border-top: 1px solid var(--line); }
.right { display: flex; flex-direction: column; max-height: calc(100vh - 100px); position: sticky; top: 80px; }
.tabs { display: grid; grid-template-columns: repeat(4, 1fr); border-bottom: 1px solid var(--line); }
.tabs button { padding: 12px 6px; border: 0; border-bottom: 2px solid transparent; background: none; cursor: pointer; color: var(--muted); }
.tabs button[aria-selected=true] { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
.tab-panel { overflow-y: auto; padding: 12px 16px 20px; }
.toc-item { display: flex; justify-content: space-between; gap: 10px; width: 100%; padding: 10px 8px; border: 0; border-radius: 8px; background: none; text-align: left; cursor: pointer; }
.toc-item:hover { background: var(--surface-2); }
.toc-item .toc-time { color: var(--muted); font-family: var(--mono); font-size: 13px; white-space: nowrap; }
.toc-child { padding-left: 24px; font-size: 14px; }
.note h3 { margin: 16px 0 4px; font-size: 15px; }
.note h4 { margin: 10px 0 2px 12px; font-size: 14px; }
.note p { margin: 0 0 6px; }
.note .child p { margin-left: 12px; color: var(--muted); font-size: 14px; }
.gloss, .faq { border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; margin-bottom: 10px; }
.gloss-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.gloss-term { font-weight: 700; }
.gloss-analogy { margin-top: 6px; padding-left: 10px; border-left: 3px solid var(--line); color: var(--muted); font-size: 14px; }
.gloss-claim { margin-top: 6px; padding: 6px 10px; border-radius: 6px; background: var(--warn-soft); color: var(--warn); font-size: 13px; }
.faq-q { font-weight: 700; margin-bottom: 4px; }
.evidence { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.link-btn { border: 0; background: none; color: var(--accent); cursor: pointer; padding: 0; font-family: var(--mono); font-size: 13px; }
.panel-search { width: 100%; padding: 8px 12px; margin-bottom: 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); color: var(--text); font: inherit; }

@media (max-width: 960px) {
  .lecture-layout { grid-template-columns: 1fr; padding: 12px; }
  .right { position: static; max-height: none; }
  .badges { display: none; }
}
@media (max-width: 640px) {
  .topbar { flex-wrap: wrap; padding: 10px 16px; }
  .topbar input[type=search] { width: 100%; margin-left: 0; }
  .card { grid-template-columns: 1fr; }
  .thumb img { width: 100%; }
  .hits li a { grid-template-columns: 64px 1fr; }
  .hits .where { display: none; }
}
```

`WEB/common.js`:
```javascript
/* 영상자료실 화면 공통 도구. 데이터는 언제나 textContent 로만 넣는다(AI가 만든 글에 HTML 이 섞여도 글자로 보이게). */
"use strict";
const $ = (selector) => document.querySelector(selector);

const VL = (() => {
  const FIELD_LABELS = { dev: "개발", finance: "금융·투자", science: "과학기술", medical: "의학·보건", other: "기타" };

  async function api(path) {
    const resp = await fetch(path, { cache: "no-store" });
    if (!resp.ok) {
      let message = resp.statusText;
      try { message = (await resp.json()).error || message; } catch (e) { /* 본문 없음 */ }
      throw new Error(message);
    }
    return resp.json();
  }

  const pad = (n) => String(n).padStart(2, "0");

  function fmtTime(sec) {
    const s = Math.max(0, Math.floor(Number(sec) || 0));
    return `${Math.floor(s / 3600)}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`;
  }

  function fmtDate(iso) {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    return `${d.getFullYear()}. ${d.getMonth() + 1}. ${d.getDate()}.`;
  }

  function fmtElapsed(ms) {
    const s = Math.max(0, Math.round(ms / 1000));
    return s >= 60 ? `${Math.floor(s / 60)}분 ${s % 60}초` : `${s}초`;
  }

  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value === true ? "" : String(value));
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  function highlight(text, query) {
    const q = (query || "").trim().toLowerCase();
    if (!q) return [text];
    const lower = text.toLowerCase();
    const parts = [];
    let from = 0;
    for (let at = lower.indexOf(q); at !== -1; at = lower.indexOf(q, from)) {
      if (at > from) parts.push(text.slice(from, at));
      parts.push(el("mark", { text: text.slice(at, at + q.length) }));
      from = at + q.length;
    }
    parts.push(text.slice(from));
    return parts;
  }

  let toastTimer = null;
  function toast(message) {
    const box = document.getElementById("toast");
    if (!box) return;
    box.textContent = message;
    box.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { box.hidden = true; }, 4000);
  }

  async function copy(text, message) {
    try {
      await navigator.clipboard.writeText(text);
    } catch (e) {
      const area = el("textarea", { readonly: true });
      area.value = text;
      document.body.append(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    toast(message);
  }

  function langPair(language, translations) {
    const langs = (translations || []).filter((l) => l !== language);
    return langs.length ? `${language.toUpperCase()}→${langs.map((l) => l.toUpperCase()).join("·")}` : "";
  }

  return { FIELD_LABELS, api, fmtTime, fmtDate, fmtElapsed, el, highlight, toast, copy, langPair };
})();
```

`WEB/library.html`:
```html
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>영상자료실</title>
<link rel="stylesheet" href="/app/app.css">
</head>
<body class="page-library">
<header class="topbar">
  <h1 class="brand">영상자료실</h1>
  <input id="search" type="search" placeholder="모든 강의에서 검색" autocomplete="off" aria-label="모든 강의에서 검색">
</header>
<main class="container">
  <nav id="filters" class="chips" aria-label="분야 필터"></nav>
  <section id="jobs" aria-live="polite"></section>
  <section id="results" hidden></section>
  <section id="list"></section>
  <p id="empty" class="empty" hidden>아직 강의가 없습니다. Claude Code에서는 <code>/video-library &lt;유튜브 링크&gt;</code>, Codex에서는 <code>$video-library &lt;유튜브 링크&gt;</code>를 입력하세요.</p>
</main>
<div id="toast" class="toast" role="status" hidden></div>
<script src="/app/common.js"></script>
<script src="/app/library.js"></script>
</body>
</html>
```

`WEB/library.js`:
```javascript
/* 목록 화면: 강의 카드, 분야 필터, 통합 검색, 진행 카드 */
"use strict";
(() => {
  const STEP_LABELS = {
    fetch: "자막 받기", preprocess: "정리", chunk: "나누기", context: "맥락 파악", correct: "교정·교열",
    merge: "합치기", outline: "목차·요약", glossary: "용어집", translate: "번역", faq: "FAQ",
    assemble: "조립", upload: "업로드",
  };
  const STEP_MARKS = { done: "✓", running: "●", failed: "✕", skipped: "–", pending: "○" };
  const STATUS_LABELS = { running: "진행 중", done: "완료", failed: "실패" };
  const WHERE_LABELS = { title: "제목", chapter: "목차", glossary: "용어집", segment: "전사", translation: "번역" };
  const DONE_HIDE_MS = 60000;
  const DISMISS_KEY = "vl.dismissedJobs";

  const state = { lectures: [], field: "", query: "", dismissed: loadDismissed(), running: new Set() };

  function loadDismissed() {
    try { return new Set(JSON.parse(localStorage.getItem(DISMISS_KEY) || "[]")); } catch (e) { return new Set(); }
  }
  function saveDismissed() {
    try { localStorage.setItem(DISMISS_KEY, JSON.stringify([...state.dismissed].slice(-50))); } catch (e) { /* 저장 불가 */ }
  }

  function renderFilters() {
    const options = [["", "전체"], ...Object.entries(VL.FIELD_LABELS)];
    $("#filters").replaceChildren(...options.map(([key, label]) => VL.el("button", {
      type: "button", class: "chip" + (state.field === key ? " active" : ""), "aria-pressed": String(state.field === key),
      onclick: () => { state.field = key; renderFilters(); refresh(); },
    }, label)));
  }

  function lectureCard(item) {
    const href = `/lecture?id=${encodeURIComponent(item.id)}`;
    const pair = VL.langPair(item.language, item.translations);
    return VL.el("article", { class: "card" },
      VL.el("a", { href, class: "thumb", "aria-hidden": "true", tabindex: "-1" },
        VL.el("img", { src: item.thumbnail_url, alt: "", loading: "lazy" })),
      VL.el("div", { class: "card-body" },
        VL.el("a", { href, class: "card-title", text: item.title }),
        VL.el("div", { class: "meta" },
          VL.el("span", { class: "tag", text: VL.FIELD_LABELS[item.field] || item.field }),
          VL.el("span", { text: `${VL.fmtTime(item.duration)} · 챕터 ${item.chapter_count} · ${VL.fmtDate(item.processed_at)}` }),
          pair ? VL.el("span", { class: "tag lang", text: pair }) : null)),
      VL.el("a", { href, class: "btn" }, "보기"));
  }

  function renderList() {
    const items = state.lectures.filter((x) => !state.field || x.field === state.field);
    $("#list").replaceChildren(...items.map(lectureCard));
    $("#empty").hidden = state.lectures.length > 0 || state.query.length > 0;
  }

  async function loadLectures() {
    try { state.lectures = await VL.api("/api/lectures"); } catch (e) { VL.toast("목록을 불러오지 못했습니다: " + e.message); }
    renderList();
  }

  let searchTimer = null;
  function onSearchInput(event) {
    clearTimeout(searchTimer);
    state.query = event.target.value.trim();
    searchTimer = setTimeout(refresh, 250);
  }

  async function refresh() {
    const searching = state.query.length > 0;
    $("#list").hidden = searching;
    $("#results").hidden = !searching;
    if (!searching) { renderList(); return; }
    $("#empty").hidden = true;
    const params = new URLSearchParams({ q: state.query });
    if (state.field) params.set("field", state.field);
    const asked = state.query;
    let data;
    try { data = await VL.api("/api/search?" + params); } catch (e) { VL.toast("검색하지 못했습니다: " + e.message); return; }
    if (asked !== state.query) return; // 늦게 도착한 이전 검색 결과는 버린다
    renderResults(data);
  }

  function renderResults(data) {
    if (!data.results.length) {
      $("#results").replaceChildren(VL.el("p", { class: "empty", text: `"${data.query}" 검색 결과가 없습니다.` }));
      return;
    }
    $("#results").replaceChildren(...data.results.map((r) => VL.el("article", { class: "result" },
      VL.el("h2", { class: "result-title" }, VL.el("a", { href: `/lecture?id=${encodeURIComponent(r.id)}`, text: r.title })),
      VL.el("ul", { class: "hits" }, ...r.hits.map((h) => VL.el("li", {},
        VL.el("a", { href: `/lecture?id=${encodeURIComponent(r.id)}&t=${Math.floor(h.start)}` },
          VL.el("span", { class: "time", text: VL.fmtTime(h.start) }),
          VL.el("span", { class: "where", text: WHERE_LABELS[h.where] + (h.lang ? ` ${h.lang.toUpperCase()}` : "") }),
          VL.el("span", {}, ...VL.highlight(h.text, data.query)))))))));
  }

  function visible(job) {
    if (state.dismissed.has(job.job_id)) return false;
    if (job.status === "done") return Date.now() - Date.parse(job.updated_at) < DONE_HIDE_MS;
    return true;
  }

  function jobCard(job) {
    const end = job.status === "running" ? Date.now() : Date.parse(job.updated_at);
    const elapsed = VL.fmtElapsed(end - Date.parse(job.started_at));
    const status = `${STATUS_LABELS[job.status] || job.status} · ${elapsed}${job.detail ? ` · ${job.detail}` : ""}`;
    const steps = Object.keys(STEP_LABELS).map((key) => {
      const s = (job.steps && job.steps[key]) || "pending";
      return VL.el("span", { class: `step ${s}` }, `${STEP_MARKS[s] || "○"} ${STEP_LABELS[key]}`);
    });
    return VL.el("article", { class: "job" + (job.status === "failed" ? " failed" : "") },
      VL.el("div", { class: "job-head" },
        VL.el("span", { class: "job-title", text: job.title || job.lecture_id }),
        VL.el("span", { class: "job-status", text: status }),
        job.status === "done" ? VL.el("a", { class: "btn small", href: `/lecture?id=${encodeURIComponent(job.lecture_id)}` }, "보기") : null,
        VL.el("button", { class: "btn small ghost", type: "button", "aria-label": "진행 카드 닫기",
          onclick: () => { state.dismissed.add(job.job_id); saveDismissed(); pollJobs(); } }, "×")),
      VL.el("div", { class: "steps" }, ...steps),
      job.status === "failed" ? VL.el("div", { class: "job-error", text: `${job.error || "실패"} — AI 도구 대화창에서 다시 실행하세요.` }) : null);
  }

  async function pollJobs() {
    let jobs = [];
    try { jobs = await VL.api("/api/jobs"); } catch (e) { return; }
    let finished = false;
    for (const job of jobs) {
      if (job.status === "running") state.running.add(job.job_id);
      else if (state.running.delete(job.job_id) && job.status === "done") finished = true;
    }
    $("#jobs").replaceChildren(...jobs.filter(visible).map(jobCard));
    if (finished) loadLectures();
  }

  renderFilters();
  loadLectures();
  pollJobs();
  setInterval(pollJobs, 2000);
  $("#search").addEventListener("input", onSearchInput);
})();
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -W error`
Expected: 모두 통과(실패 0). node가 없으면 `test_js_syntax`는 건너뜀.

- [ ] **Step 5: 커밋**

```bash
git add plugin/video-library/skills/video-library/web plugin/video-library/skills/video-library/tests/test_web_assets.py
git commit -m "feat(viewer): add shared styles, helpers, and library page" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: 강의 화면

**Files:**
- Create: `WEB/lecture.html`, `WEB/lecture.js`
- Modify: `TESTS/test_web_assets.py` (`PAIRS`에 강의 화면 추가, 버튼 문구 테스트)

**Interfaces:**
- Consumes: `VL`(Task 6), `/api/lectures/<id>`, YouTube IFrame API
- 화면 요소 id: `title`, `badges`, `find`, `player`, `ticks`, `clock`, `speeds`, `lang-switch`, `copy-plain`, `copy-timed`, `count`, `transcript`, `ask`, `request-en`, `tab-toc`, `tab-notes`, `tab-glossary`, `tab-faq`, `glossary-find`, `glossary-list`, `toast`
- 동작: 자동 재생 없음(사전 실험), 주소 `t`는 시작 위치. 문장·목차·용어·FAQ 근거·눈금 클릭 → 그 시간으로 이동 후 재생. 250ms마다 현재 문장 강조(재생 중일 때만 전사 목록 자동 스크롤). 단축키는 입력창에 있을 때 무시.

- [ ] **Step 1: 실패하는 테스트 작성**

`TESTS/test_web_assets.py`에서 `PAIRS`를 아래로 바꾸고, 맨 아래에 테스트를 추가:
```python
PAIRS = [("library.html", "library.js"), ("lecture.html", "lecture.js")]
```
```python
def test_lecture_page_buttons_and_messages():
    js = read("lecture.js")
    assert "video-library 강의 「" in js and "에 대해 질문: " in js
    assert "/video-library 번역 " in js
    assert "질문 문장을 복사했습니다. video-library 플러그인이 설치된 AI 도구의 대화창에 붙여 넣고 질문을 이어 쓰세요." in js
    assert "요청 문장을 복사했습니다. video-library 플러그인이 설치된 AI 도구의 대화창에 붙여 넣으세요." in js
    assert "https://www.youtube.com/iframe_api" in js
    assert "autoplay" not in js


def test_lecture_page_has_four_tabs():
    page = read("lecture.html")
    for tab in ("목차", "노트", "용어집", "FAQ"):
        assert f">{tab}</button>" in page
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_web_assets.py -v`
Expected: FAIL — `FileNotFoundError`(lecture.js·lecture.html 없음)

- [ ] **Step 3: 화면 파일 작성**

`WEB/lecture.html`:
```html
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>강의 — 영상자료실</title>
<link rel="stylesheet" href="/app/app.css">
</head>
<body class="page-lecture">
<header class="topbar">
  <a href="/" class="back">← 목록</a>
  <h1 id="title" class="lecture-title">불러오는 중…</h1>
  <span id="badges" class="badges"></span>
  <input id="find" type="search" placeholder="이 강의에서 검색" autocomplete="off" aria-label="이 강의에서 검색">
</header>
<main class="lecture-layout">
  <section class="left">
    <div class="panel player-box">
      <div class="player-wrap"><div id="player"></div></div>
      <div id="ticks" class="ticks" title="눌러서 이동"></div>
      <div class="controls">
        <span id="clock" class="clock">0:00:00 / 0:00:00</span>
        <span class="muted">배속</span>
        <span id="speeds" class="speeds"></span>
      </div>
      <p class="shortcuts">단축키 J/K/L 10초 뒤·재생/정지·10초 앞 · ←/→ 5초 · 1~9 대목차</p>
    </div>
    <div class="panel transcript-box">
      <div class="box-head">
        <h2>전사</h2>
        <span id="lang-switch" class="seg" hidden></span>
        <button id="copy-plain" class="btn small" type="button">텍스트만 복사</button>
        <button id="copy-timed" class="btn small" type="button">시간 포함 복사</button>
        <span id="count" class="muted"></span>
      </div>
      <ol id="transcript" class="transcript"></ol>
      <div class="actions">
        <button id="ask" class="btn" type="button">이 강의에 질문하기</button>
        <button id="request-en" class="btn" type="button" hidden>영어 번역 요청</button>
      </div>
    </div>
  </section>
  <aside class="panel right">
    <div class="tabs" role="tablist">
      <button type="button" role="tab" data-tab="toc" aria-selected="true">목차</button>
      <button type="button" role="tab" data-tab="notes" aria-selected="false">노트</button>
      <button type="button" role="tab" data-tab="glossary" aria-selected="false">용어집</button>
      <button type="button" role="tab" data-tab="faq" aria-selected="false">FAQ</button>
    </div>
    <div id="tab-toc" class="tab-panel" role="tabpanel"></div>
    <div id="tab-notes" class="tab-panel note" role="tabpanel" hidden></div>
    <div id="tab-glossary" class="tab-panel" role="tabpanel" hidden>
      <input id="glossary-find" class="panel-search" type="search" placeholder="용어 검색" autocomplete="off" aria-label="용어 검색">
      <div id="glossary-list"></div>
    </div>
    <div id="tab-faq" class="tab-panel" role="tabpanel" hidden></div>
  </aside>
</main>
<div id="toast" class="toast" role="status" hidden></div>
<script src="/app/common.js"></script>
<script src="/app/lecture.js"></script>
</body>
</html>
```

`WEB/lecture.js`:
```javascript
/* 강의 화면: 유튜브 플레이어, 전사, 목차·노트·용어집·FAQ, 복사·요청 버튼, 단축키 */
"use strict";
(() => {
  const params = new URLSearchParams(location.search);
  const lectureId = params.get("id") || "";
  const startAt = Math.max(0, Number(params.get("t")) || 0);
  const SPEEDS = [1, 1.25, 1.5, 2];
  const ASK_MESSAGE = "질문 문장을 복사했습니다. video-library 플러그인이 설치된 AI 도구의 대화창에 붙여 넣고 질문을 이어 쓰세요.";
  const REQUEST_MESSAGE = "요청 문장을 복사했습니다. video-library 플러그인이 설치된 AI 도구의 대화창에 붙여 넣으세요.";

  let doc = null;
  let player = null;
  let ready = false;
  let view = "orig";
  let active = -1;
  let starts = [];

  const firstTranslation = () => Object.keys(doc.translations)[0] || null;

  async function init() {
    if (!/^[A-Za-z0-9_-]{11}$/.test(lectureId)) return fail("강의 ID가 올바르지 않습니다.");
    try { doc = await VL.api(`/api/lectures/${encodeURIComponent(lectureId)}`); } catch (e) { return fail("강의를 불러오지 못했습니다: " + e.message); }
    starts = doc.segments.map((s) => s.start);
    document.title = `${doc.lecture.title} — 영상자료실`;
    renderHeader();
    renderTicks();
    renderSpeeds();
    renderLangSwitch();
    renderTranscript();
    renderToc();
    renderNotes();
    renderGlossary("");
    renderFaq();
    setupTabs();
    setupButtons();
    setupKeys();
    $("#find").addEventListener("input", (e) => filterTranscript(e.target.value));
    $("#glossary-find").addEventListener("input", (e) => renderGlossary(e.target.value));
    loadPlayer();
    highlightAt(startAt, true);
    setInterval(tick, 250);
  }

  function fail(message) { $("#title").textContent = message; }

  function renderHeader() {
    const lec = doc.lecture;
    $("#title").textContent = lec.title;
    $("#badges").replaceChildren(
      VL.el("span", { class: "tag", text: VL.FIELD_LABELS[lec.field] || lec.field }),
      VL.el("span", { class: "tag lang", text: `${VL.fmtTime(lec.duration)} · 챕터 ${doc.chapters.length}` }));
  }

  /* ---- 플레이어 ---- */
  function loadPlayer() {
    window.onYouTubeIframeAPIReady = () => {
      player = new YT.Player("player", {
        videoId: doc.lecture.video_id,
        playerVars: { playsinline: 1, rel: 0, start: Math.floor(startAt), origin: location.origin },
        events: {
          onReady: () => { ready = true; updateClock(); },
          onError: (e) => VL.toast(`영상을 재생할 수 없습니다(유튜브 오류 ${e.data}).`),
        },
      });
    };
    document.head.append(VL.el("script", { src: "https://www.youtube.com/iframe_api" }));
  }

  const now = () => (ready && player.getCurrentTime ? player.getCurrentTime() : startAt);
  const playing = () => ready && player.getPlayerState && player.getPlayerState() === 1;

  function seek(t, play = true) {
    const target = Math.max(0, Math.min(t, doc.lecture.duration));
    if (ready) {
      player.seekTo(target, true);
      if (play) player.playVideo();
    }
    highlightAt(target, true);
    updateClock(target);
  }

  function tick() {
    if (!ready) return;
    updateClock();
    highlightAt(now(), false);
  }

  function updateClock(at) {
    const t = at === undefined ? now() : at;
    const total = (ready && player.getDuration && player.getDuration()) || doc.lecture.duration;
    $("#clock").textContent = `${VL.fmtTime(t)} / ${VL.fmtTime(total)}`;
    const bar = $("#ticks").querySelector(".progress");
    if (bar) bar.style.width = `${Math.min(100, (t / total) * 100)}%`;
  }

  function renderTicks() {
    const total = doc.lecture.duration;
    const box = $("#ticks");
    box.replaceChildren(VL.el("div", { class: "progress" }),
      ...doc.chapters.slice(1).map((ch) => {
        const tick = VL.el("span", { class: "tick", title: ch.title });
        tick.style.left = `${(ch.start / total) * 100}%`;
        return tick;
      }));
    box.addEventListener("click", (e) => {
      const rect = box.getBoundingClientRect();
      seek(((e.clientX - rect.left) / rect.width) * total);
    });
  }

  function renderSpeeds() {
    $("#speeds").replaceChildren(...SPEEDS.map((rate) => VL.el("button", {
      type: "button", class: "btn small" + (rate === 1 ? " active" : ""),
      onclick: (e) => {
        if (ready) player.setPlaybackRate(rate);
        for (const b of $("#speeds").children) b.classList.toggle("active", b === e.currentTarget);
      },
    }, `${rate}x`)));
  }

  /* ---- 전사 ---- */
  function renderLangSwitch() {
    const tr = firstTranslation();
    if (!tr) return;
    const orig = doc.lecture.language.toUpperCase();
    const options = [["orig", `원문(${orig})`], [tr, `번역(${tr.toUpperCase()})`], ["both", "나란히"]];
    const box = $("#lang-switch");
    box.hidden = false;
    box.replaceChildren(...options.map(([key, label]) => VL.el("button", {
      type: "button", class: key === view ? "active" : "",
      onclick: (e) => {
        view = key;
        for (const b of box.children) b.classList.toggle("active", b === e.currentTarget);
        renderTranscript();
        filterTranscript($("#find").value);
      },
    }, label)));
  }

  function linesFor(key) {
    if (key === "orig" || !doc.translations[key]) return doc.segments.map((s) => s.text);
    return doc.translations[key].map((it) => it.text);
  }

  function renderTranscript() {
    const orig = linesFor("orig");
    const tr = firstTranslation();
    const shown = view === "both" ? orig : linesFor(view);
    const second = view === "both" && tr ? linesFor(tr) : null;
    $("#transcript").replaceChildren(...doc.segments.map((s, i) => VL.el("li", {
      "data-i": i, onclick: () => seek(s.start),
    },
    VL.el("span", { class: "time", text: VL.fmtTime(s.start) }),
    VL.el("span", {}, shown[i], second ? VL.el("span", { class: "tr", text: second[i] }) : null))));
    active = -1;
    highlightAt(now(), true);
    $("#count").textContent = `문장 ${doc.segments.length}개`;
  }

  function indexAt(t) {
    let lo = 0;
    let hi = starts.length - 1;
    let found = 0;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (starts[mid] <= t + 0.01) { found = mid; lo = mid + 1; } else { hi = mid - 1; }
    }
    return found;
  }

  function highlightAt(t, force) {
    const i = indexAt(t);
    if (i === active && !force) return;
    const list = $("#transcript");
    if (active >= 0 && list.children[active]) list.children[active].classList.remove("active");
    active = i;
    const li = list.children[i];
    if (!li) return;
    li.classList.add("active");
    if (force || playing()) list.scrollTop = li.offsetTop - list.offsetTop - list.clientHeight / 3;
  }

  function filterTranscript(query) {
    const q = query.trim().toLowerCase();
    let shown = 0;
    for (const li of $("#transcript").children) {
      const match = !q || li.textContent.toLowerCase().includes(q);
      li.hidden = !match;
      if (match) shown += 1;
    }
    $("#count").textContent = q ? `${shown}개 일치` : `문장 ${doc.segments.length}개`;
  }

  function copyTranscript(timed) {
    const orig = linesFor("orig");
    const tr = firstTranslation();
    const rows = doc.segments.map((s, i) => {
      const parts = view === "both" ? [orig[i], tr ? linesFor(tr)[i] : null].filter(Boolean) : [linesFor(view)[i]];
      const text = parts.join("\n");
      return timed ? `[${VL.fmtTime(s.start)}] ${text}` : text;
    });
    VL.copy(rows.join("\n"), timed ? "시간 포함 전사를 복사했습니다." : "전사를 복사했습니다.");
  }

  /* ---- 오른쪽 탭 ---- */
  function chapterButton(ch, child) {
    const minutes = Math.max(1, Math.round((ch.end - ch.start) / 60));
    return VL.el("button", { type: "button", class: "toc-item" + (child ? " toc-child" : ""), onclick: () => seek(ch.start) },
      VL.el("span", { text: `${ch.id}. ${ch.title}` }),
      VL.el("span", { class: "toc-time", text: `${VL.fmtTime(ch.start)} · ${minutes}분` }));
  }

  function renderToc() {
    $("#tab-toc").replaceChildren(...doc.chapters.flatMap((ch) => [chapterButton(ch, false),
      ...(ch.children || []).map((c) => chapterButton(c, true))]));
  }

  const timeButton = (t) => VL.el("button", { type: "button", class: "link-btn", onclick: () => seek(t) }, VL.fmtTime(t));
  const startOf = (idx) => (doc.segments[idx - 1] ? doc.segments[idx - 1].start : 0);

  function renderNotes() {
    const blocks = [VL.el("h2", { text: "챕터 요약" })];
    for (const ch of doc.chapters) {
      blocks.push(VL.el("h3", {}, `${ch.id}. ${ch.title} `, timeButton(ch.start)), VL.el("p", { text: ch.summary }));
      for (const c of ch.children || []) {
        blocks.push(VL.el("div", { class: "child" }, VL.el("h4", { text: `${c.id} ${c.title}` }), VL.el("p", { text: c.summary })));
      }
    }
    if (doc.mentions.length) {
      blocks.push(VL.el("h2", { text: "영상에서 언급된 자료" }), VL.el("ul", {}, ...doc.mentions.map((m) => VL.el("li", {},
        m.url ? VL.el("a", { href: m.url, target: "_blank", rel: "noopener noreferrer", text: m.text }) : m.text,
        " ", timeButton(startOf(m.idx))))));
    }
    $("#tab-notes").replaceChildren(...blocks);
  }

  function renderGlossary(query) {
    const q = query.trim().toLowerCase();
    const items = doc.glossary.filter((g) => !q || `${g.term} ${g.definition}`.toLowerCase().includes(q));
    $("#glossary-list").replaceChildren(...(items.length ? items.map((g) => VL.el("div", { class: "gloss" },
      VL.el("div", { class: "gloss-head" }, VL.el("span", { class: "gloss-term", text: g.term }), timeButton(startOf(g.idx))),
      VL.el("div", { text: g.definition }),
      g.analogy ? VL.el("div", { class: "gloss-analogy", text: g.analogy }) : null,
      g.claim_note ? VL.el("div", { class: "gloss-claim", text: `영상 속 주장 · ${g.claim_note}` }) : null))
      : [VL.el("p", { class: "muted", text: doc.glossary.length ? "일치하는 용어가 없습니다." : "용어집이 없습니다." })]));
  }

  function renderFaq() {
    $("#tab-faq").replaceChildren(...(doc.faq.length ? doc.faq.map((f) => VL.el("div", { class: "faq" },
      VL.el("div", { class: "faq-q", text: `Q. ${f.question}` }),
      VL.el("div", { text: f.answer }),
      VL.el("div", { class: "evidence" }, ...f.evidence.map((idx) => VL.el("button", {
        type: "button", class: "btn small", onclick: () => seek(startOf(idx)),
      }, `근거 장면 ${VL.fmtTime(startOf(idx))}`)))))
      : [VL.el("p", { class: "muted", text: "FAQ가 없습니다." })]));
  }

  function setupTabs() {
    const buttons = document.querySelectorAll(".tabs [data-tab]");
    for (const button of buttons) {
      button.addEventListener("click", () => {
        for (const b of buttons) {
          const on = b === button;
          b.setAttribute("aria-selected", String(on));
          document.getElementById(`tab-${b.dataset.tab}`).hidden = !on;
        }
      });
    }
  }

  function setupButtons() {
    $("#copy-plain").addEventListener("click", () => copyTranscript(false));
    $("#copy-timed").addEventListener("click", () => copyTranscript(true));
    $("#ask").addEventListener("click", () =>
      VL.copy(`video-library 강의 「${doc.lecture.title}」(${lectureId})에 대해 질문: `, ASK_MESSAGE));
    const needsEnglish = doc.lecture.language === "ko" && !doc.translations.en;
    $("#request-en").hidden = !needsEnglish;
    $("#request-en").addEventListener("click", () => VL.copy(`/video-library 번역 ${lectureId}`, REQUEST_MESSAGE));
  }

  function setupKeys() {
    document.addEventListener("keydown", (e) => {
      if (e.target.closest("input, textarea") || e.ctrlKey || e.metaKey || e.altKey) return;
      const key = e.key.toLowerCase();
      if (key === "j") seek(now() - 10);
      else if (key === "l") seek(now() + 10);
      else if (key === "k") { if (ready) (playing() ? player.pauseVideo() : player.playVideo()); }
      else if (e.key === "ArrowLeft") seek(now() - 5);
      else if (e.key === "ArrowRight") seek(now() + 5);
      else if (/^[1-9]$/.test(e.key) && doc.chapters[Number(e.key) - 1]) seek(doc.chapters[Number(e.key) - 1].start);
      else return;
      e.preventDefault();
    });
  }

  init();
})();
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -W error`
Expected: 모두 통과(실패 0)

- [ ] **Step 5: 커밋**

```bash
git add plugin/video-library/skills/video-library/web plugin/video-library/skills/video-library/tests/test_web_assets.py
git commit -m "feat(viewer): add lecture page with player, transcript, and tabs" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: 명령 등록 + `SKILL.md` — 열기·질문 답변 절차

**Files:**
- Modify: `SKILL_DIR/scripts/vl.py` (`COMMANDS`에 `search`, `serve`, `open`)
- Modify: `SKILL_DIR/SKILL.md`
- Modify: `TESTS/test_skill_doc.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`TESTS/test_skill_doc.py` 맨 아래에 추가:
```python
def test_viewer_and_question_sections():
    body = text()
    assert "## 나중 요청: 영상자료실 열기" in body and "## 질문 답변" in body
    assert "vl.py open" in body and "vl.py search" in body
    assert "/lecture?id=<ID>&t=<초>" in body
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest plugin/video-library/skills/video-library/tests/test_skill_doc.py -v`
Expected: FAIL — `test_viewer_and_question_sections` (섹션 없음)

- [ ] **Step 3: 명령 등록과 SKILL.md 수정**

`SKILL_DIR/scripts/vl.py`의 `COMMANDS` 끝(`doctor` 줄 아래)에 추가:
```python
    "search": ("video_library.search", "모든 강의에서 검색(질문 답변용)"),
    "serve": ("video_library.server", "영상자료실 화면용 PC 전용 미니 서버(보통 open 이 켠다)"),
    "open": ("video_library.opener", "영상자료실 화면 열기(필요하면 미니 서버를 켠다)"),
```

`## 규칙`의 "결과물은 영상자료실…" 항목 바로 아래에 추가:
```markdown
- 화면: `vl.py open`이 영상자료실 화면을 브라우저로 연다. 화면 파일을 `<영상자료실>/app/`에 설치하고, 내 PC 전용 미니 서버(`vl.py serve`)가 꺼져 있으면 백그라운드로 켠다(1시간 쓰지 않으면 스스로 꺼짐). 출력 JSON의 `url`(예: `http://127.0.0.1:8765`)을 이하 `<URL>`이라 한다.
```

`## 단계`의 0단계를 아래로 바꾼다:
```markdown
0. **점검·열기** — `vl.py doctor`. `✗`(필수) 항목이 있으면 출력된 설치 명령을 사용자에게 보여주고 승인을 받아 실행한 뒤 다시 점검한다. `△`(권장)는 알리고 진행한다. 점검을 통과하면 `vl.py open`으로 목록 화면을 열어 둔다(진행 카드로 단계가 보인다).
```

11단계 끝 문장 "빠진 단계가 있으면…" 뒤에 이어 쓴다:
```markdown
 강의 화면 주소 `<URL>/lecture?id=<ID>`도 알려 준다.
```

`## 나중 요청: 한국어 강의 영어 번역` 섹션 위에 추가:
```markdown
## 나중 요청: 영상자료실 열기
사용자가 `/video-library 열기`(또는 "영상자료실 열어줘")를 요청하면 `vl.py open`을 실행하고 `<URL>`을 알려 준다. 영상자료실 폴더의 `영상자료실 열기.bat`(Mac은 `.command`)을 더블클릭해도 된다고 안내한다.

## 질문 답변
사용자가 영상자료실의 강의 내용에 대해 물으면(예: "그 강의에서 ○○ 설명한 부분 찾아줘", "video-library 강의 「제목」(<ID>)에 대해 질문: …"):
1. 질문의 핵심어 2~3개로 `vl.py search "<핵심어>"`를 실행한다. 강의 ID가 주어졌으면 `--video <ID>`, 분야가 분명하면 `--field <분야>`를 붙인다. 결과가 없으면 비슷한 말로 한두 번 더 찾는다.
2. 찾은 장면 앞뒤 문장을 `<영상자료실>/lectures/<ID>/lecture.json`의 `segments`에서 읽어 맥락을 확인한다.
3. **영상에 근거가 있는 내용만** 한국어로 답하고, 근거 장면마다 시간과 바로 열리는 링크 `<URL>/lecture?id=<ID>&t=<초>`(검색 결과에 출력된 링크)를 붙인다. 영상에서 찾지 못했으면 그렇다고 말한다. 영상 밖 투자 조언·진단은 덧붙이지 않는다.
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -W error`
Expected: 모두 통과(실패 0)

- [ ] **Step 5: 커밋**

```bash
git add plugin/video-library/skills/video-library/scripts/vl.py plugin/video-library/skills/video-library/SKILL.md plugin/video-library/skills/video-library/tests/test_skill_doc.py
git commit -m "feat(viewer): register viewer commands and document open and Q&A" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: 브라우저로 화면 확인 (실제 영상자료실 + 시험용 자료실)

서버는 읽기 전용이므로 실제 `문서/영상자료실`을 그대로 연다. 진행 카드·빈 화면은 실제 자료를 건드리지 않도록 **시험용 자료실**(임시 폴더, `VL_HOME`)에서 확인한다. 확인은 내장 브라우저(`mcp__Claude_Browser__*`)로 하고, 결과를 증거 문서에 적는다.

**Files:**
- Create: `docs/superpowers/evidence/2026-10-06-stage3-viewer.md`
- 바깥 `바코대AX/.claude/launch.json`(세션용, Git 대상 아님) — 실행 중인 서버에 붙는 설정

- [ ] **Step 1: 실제 영상자료실 열기**

Run: `python plugin/video-library/skills/video-library/scripts/vl.py open --no-browser`
Expected: `{"url": "http://127.0.0.1:8765", ...}`. `문서/영상자료실/app/`에 화면 파일·`runtime/`, `영상자료실 열기.bat` 생성.

`바코대AX/.claude/launch.json`:
```json
{"version": "0.0.1", "configurations": [
  {"name": "video-library", "url": "http://127.0.0.1:8765"},
  {"name": "video-library-sandbox", "url": "http://127.0.0.1:8766"}
]}
```
`preview_start`(name `video-library`)로 연다.

- [ ] **Step 2: 목록 화면 확인 (실제)**

확인 항목(각각 결과를 기록): 강의 카드(썸네일·제목·분야 태그·길이·챕터 수·날짜·`KO→EN` 표시), 분야 필터(개발 ↔ 과학기술에서 카드가 사라짐), 통합 검색 `꺾쇠` → 강의별 결과·`<mark>` 강조 → 결과 클릭 시 강의 화면이 그 시간으로 열림.

- [ ] **Step 3: 강의 화면 확인 (실제)**

확인 항목: 유튜브 영상 표시·재생(재생 버튼 클릭 후 `getPlayerState()==1`), 주소 `t`로 시작 위치, 챕터 눈금 클릭 이동, 문장 클릭 이동·현재 문장 강조, 배속 1.5x(`getPlaybackRate()==1.5`), 단축키 L(+10초)·숫자 3(대목차 3), [원문|번역|나란히] 전환, [텍스트만 복사]·[시간 포함 복사](클립보드 내용 확인, `navigator.clipboard.readText()` 또는 알림 문구), 목차·노트·용어집(검색 포함)·FAQ(근거 장면 이동) 탭, [이 강의에 질문하기] 알림 문구, [영어 번역 요청]은 이 강의에 영어 번역이 있으므로 숨김, 이 강의에서 검색(일치 개수), 좁은 화면(`resize_window` mobile)에서 세로 배치, 어두운 모드(`colorScheme: dark`), 콘솔 오류 없음(`read_console_messages`, CSP 위반 포함).

- [ ] **Step 4: 시험용 자료실 확인 (진행 카드·빈 화면·HTML 글자 처리)**

임시 폴더에 시험용 자료실을 만든다(실제 자료와 분리). PowerShell 또는 Git Bash에서 `VL_HOME`을 임시 경로로 두고:
1. 같은 `VL_HOME`으로 `vl.py open --no-browser` → 화면 설치와 서버 시작(실제 서버가 8765를 쓰고 있으므로 다음 빈 포트). 출력 `url`의 포트로 `launch.json`의 `video-library-sandbox` 주소를 맞추고 `preview_start` → **빈 화면 안내 문구** 확인.
2. 테스트 픽스처 샘플 강의를 `<VL_HOME>/lectures/AbCdEfGhIjK.tmp/lecture.json`으로 복사하되 제목을 `<script>alert(1)</script> 샘플`로 바꾼 뒤 Python 한 줄로 `library.commit_lecture` 실행 → 목록에서 제목이 **글자 그대로** 보이고 경고창이 뜨지 않는지 확인.
3. `jobs.start_job`으로 작업을 만들고 `vl.py progress`로 단계를 차례로 `running`→`done`으로 바꾸며 **진행 카드가 2초 안에 바뀌는지**, `failed`로 바꾸면 빨간 카드·오류 문구, [×]로 닫기, 마지막에 `jobs.finish_job` → 완료 카드가 **1분 뒤 사라지는지**(시간을 재서 기록) 확인.
4. 확인 후 시험용 서버를 끄고(`<VL_HOME>/.server.json`의 pid를 종료) 임시 폴더를 지운다.

- [ ] **Step 5: 열기 파일 확인**

`문서/영상자료실/영상자료실 열기.bat` 내용 확인(파이썬 경로·`app\runtime\vl.py open`). 서버가 켜진 상태에서 `cmd /c` 로 실행해 같은 주소가 다시 쓰이는지(새 서버를 띄우지 않는지) 확인한다. 브라우저가 열리는 것은 사용자 화면에서 일어나므로 사용자에게 한 번 더블클릭해 보도록 안내하고 결과를 묻는다.

- [ ] **Step 6: 기록·커밋**

`docs/superpowers/evidence/2026-10-06-stage3-viewer.md`에 항목별 성공·실패·미확인과, 실패 시 원인·조치(조치는 TDD로 고친 뒤 커밋)를 적는다.
```bash
git add docs/superpowers/evidence/2026-10-06-stage3-viewer.md
git commit -m "docs: record stage 3 browser verification" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: 실제 영상 2편 추가 처리 (사용자 승인 필요)

설계서 10장 3단계 완료 조건 "번역·FAQ 포함 영상 3편"을 채운다. **영상 선택과 사용량에 대해 사용자 승인을 받는다.**

- [ ] **Step 1: 영상 받기** — 사용자에게 (a) **영어 과학기술 영상**(10~20분, 한국어 번역 흐름 확인), (b) **한국어 금융 또는 의학·보건 영상**(용어집 `claim_note`·FAQ 안전 규칙 확인) 링크를 받는다. 예상 사용량(2단계 실측: 38분 영상 + 영어 번역에 서브에이전트 약 90만 토큰)을 알리고 승인받는다.
- [ ] **Step 2: 처리** — `SKILL.md` 0~11단계대로 처리한다(목록 화면의 진행 카드가 실제로 움직이는지 함께 본다).
- [ ] **Step 3: 화면 확인** — (a) 강의 화면에서 [원문(EN)|번역(KO)|나란히]·한국어 목차·용어집, (b) 용어집의 "영상 속 주장" 표시와 FAQ 근거 장면, 분야 필터(과학기술·금융/의학)로 세 강의가 나뉘는지.
- [ ] **Step 4: 기록·커밋** — 증거 문서에 영상별 길이·문장 수·소요 시간·사용량·검사 재시도·화면 확인 결과를 추가하고 커밋한다(영상 내용·전사 원문은 적지 않는다).

---

### Task 11: API 문서·인계 갱신

**Files:**
- Modify: `docs/api.md`, `docs/handoff.md`, `docs/superpowers/evidence/2026-10-06-stage3-viewer.md`

- [ ] **Step 1: api.md 갱신** — 4절 표에 `GET /api/health`(`{"app":"video-library","home":…}`) 추가, `GET /api/search`에 `video` 인자 추가, `/api/jobs`는 "실행 중인 작업 전부 + 최근 1시간 안에 끝난 작업", 검색 응답의 제목 결과는 `idx: null`, "PC 미니 서버는 `Host`가 `127.0.0.1:<포트>`·`localhost:<포트>`가 아니면 403, GET 외 405" 문장 추가.
- [ ] **Step 2: 전체 테스트** — Run: `python -m pytest -W error` / Expected: 모두 통과(실패 0)
- [ ] **Step 3: 인계 갱신** — `docs/handoff.md` §1에 `| 3단계 화면 + PC 서버 | 완료 — … | [증거](…) |`, 다음 할 일 "4단계(Railway) 구현 계획 작성 → 사용자 검토"로, §3에 한 줄. 증거 문서에 "자동 테스트" 절(실제 통과 수).
- [ ] **Step 4: 커밋**

```bash
git add docs/api.md docs/handoff.md docs/superpowers/evidence/2026-10-06-stage3-viewer.md
git commit -m "docs: update API contract and record stage 3 completion" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
