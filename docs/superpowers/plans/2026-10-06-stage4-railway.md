# video-library 4단계(Railway 공개 서버) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 3단계의 화면·서버를 Railway에 올려, PC에서 만든 강의를 업로드하면 관리자가 [공개]로 바꾼 강의만 누구나 공개 주소에서 보고(목록·검색·강의 화면), 처리 중 진행 상황은 관리자에게 보이게 한다.

**Architecture:** 서버 프로그램은 3단계 `server.py` 한 벌에 **호스팅 모드**를 더한다(`auth`가 있으면 호스팅 모드). 저장은 PostgreSQL이 아니라 **볼륨 `/data`에 PC와 같은 파일 형식**(`lectures/<ID>/lecture.json`·`index.json`·`jobs/`)을 쓰고, 공개 여부는 `visibility.json`에 따로 둔다(재업로드해도 공개 상태 유지). 관리자 비밀번호·업로드 토큰은 **해시만** Railway 변수에 있고, 사용자가 자기 터미널에서 `vl.py connect`로 설정한다. PC 쪽은 `config.json`(서버 주소·토큰)이 있을 때만 진행 보고(3초 제한)와 업로드를 한다.

**Tech Stack:** Python 3.10+ 표준 라이브러리(`http.server`, `hashlib.pbkdf2_hmac`, `hmac`, `secrets`, `http.cookies`, `urllib.request`, `getpass`, `subprocess`), Docker(`python:3.12-slim`), Railway CLI 5.x(`railway up`·`variable set --stdin`·`volume`·`domain`), 바닐라 HTML·CSS·JS, 개발용 pytest.

**Spec:** [docs/superpowers/specs/2026-10-05-video-library-design.md](../specs/2026-10-05-video-library-design.md) — 3장(구조·코드 단위, 10-06 파일 저장 결정 반영), 5.4(API), 6장(12단계 업로드·진행 보고), 7.1(관리자 [공개/비공개]·[삭제]), 8.2·8.3(데이터 보호·보안), 9장 3·4겹, 10장 4단계, 11장 결정 기록. API 약속: [docs/api.md](../../api.md) 4장.

## Global Constraints

- 명령은 `plugin-app/` 폴더에서 실행한다. `SKILL_DIR` = `plugin/video-library/skills/video-library`, `PKG` = `SKILL_DIR/scripts/video_library`, `WEB` = `SKILL_DIR/web`, `TESTS` = `SKILL_DIR/tests`.
- 런타임은 **표준 라이브러리만**(Railway 서버도 추가 패키지 없음), Python 3.10 문법.
- **비밀 값 규칙:** 관리자 비밀번호·업로드 토큰은 채팅·Git·로그·화면 출력·명령줄 인자에 넣지 않는다. Railway 변수에는 해시만(`VL_ADMIN_PASSWORD_HASH` = `pbkdf2_sha256$<반복>$<salt hex>$<hash hex>`, `VL_UPLOAD_TOKEN_HASH` = SHA-256 hex 64자), 값은 `railway variable set <KEY> --stdin`의 표준 입력으로만 넘긴다. AI는 `vl.py connect`를 대신 실행하지 않고 비밀번호·토큰을 묻지 않는다.
- 호스팅 서버는 두 해시 변수가 없거나 형식이 틀리면 **시작하지 않는다**.
- 공개 범위: 로그인하지 않은 사람에게 비공개 강의는 목록·검색·단건·진행 카드 **어디에서도** 보이지 않는다(단건은 404로 존재도 숨김). 새 업로드는 비공개, 재업로드는 공개 상태 유지.
- 관리자 쓰기 요청(로그인·로그아웃·PATCH·DELETE)은 세션 쿠키(로그인 제외) + `X-Requested-With: video-library` 헤더 필수. 세션 쿠키 `vl_session`: `HttpOnly; Secure; SameSite=Strict; Path=/`, 12시간. 로그인 실패 15분에 10번이면 15분 동안 잠금(맞는 비밀번호도 거절).
- 본문 크기: 업로드 20MB, 그 밖 64KB. `Content-Length` 없으면 411, 넘으면 413(본문을 읽지 않음).
- 진행 보고는 **3초 제한·실패해도 조용히 계속**. 업로드 실패해도 PC 결과는 그대로, 같은 명령으로 다시 올린다.
- PC 미니 서버 동작(127.0.0.1·읽기 전용·Host 검사·405)은 바뀌지 않는다.
- 테스트는 인터넷·실제 문서 폴더를 쓰지 않는다. **이번 단계에서 conftest에 인터넷 연결 차단 가드를 넣는다**(127.0.0.1·::1·localhost만 허용).
- Railway 작업(프로젝트·서비스·볼륨·도메인 생성, 배포, 변수 설정, 업로드)은 **단계마다 사용자 승인**. 공개는 사용 허락을 받은 데모 영상(바이브코딩대학 `40JNj2zjnQc`)만.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **로그아웃 상태의 방문자가 비공개 강의를 엿보는 경우**(목록·검색어·`/api/lectures/<ID>` 직접 입력·`/api/jobs`) — 하나도 보이지 않아야 한다. → Task 3 테스트.
2. **토큰 없이·틀린 토큰으로·아주 큰 본문으로 업로드하는 경우** — 401/413, 본문을 읽지 않고 거절, 기존 강의는 그대로. → Task 3 테스트.
3. **처리 중 Railway가 꺼져 있거나 느린 경우** — 진행 보고가 처리 속도를 늦추거나 멈추면 안 된다(3초 제한, 오류 없이 계속). → Task 5 테스트.
4. **`visibility.json`이 깨지거나 사라진 경우** — 모든 강의를 비공개로 본다(실수로 공개되지 않게). 재업로드는 공개 상태를 유지, 삭제하면 공개 목록에서도 빠진다. → Task 1 테스트.
5. **비밀번호를 계속 맞혀 보는 경우·비밀 값이 출력에 섞이는 경우** — 10번 실패 뒤 잠금, `connect` 출력·명령줄에 비밀번호·토큰이 없다. → Task 2·7 테스트.

---

## File Structure

| 파일 | 책임 |
|---|---|
| `PKG/search.py` (수정) | `search(..., allowed=None)` — 볼 수 있는 강의만 검색 |
| `PKG/store_hosted.py` (새) | `HostedStore(FileStore)`: 업로드·공개 상태·삭제·진행 보고 저장, `check_job` |
| `PKG/auth.py` (새) | 비밀번호 해시·확인, 토큰 해시·확인, 세션, 로그인 잠금, 쿠키 문자열 |
| `PKG/server.py` (수정) | 호스팅 모드 라우팅(쓰기·로그인·공개 범위), `hosted_server(env)`, `vl.py serve --hosted` |
| `PKG/remote.py` (새) | `config.json` 읽기·쓰기, 서버 주소 검사, Railway 요청, 진행 보고 |
| `PKG/jobs.py` (수정) | 기록할 때마다 진행 보고, 업로드 대기 중이면 작업을 끝내지 않음, `pending_upload_job` |
| `PKG/upload.py` (새) | `vl.py upload --video <ID>` |
| `PKG/fetch.py` (수정) | `--no-upload`, 설정이 있으면 업로드 단계 `pending` |
| `PKG/connect.py` (새) | `vl.py connect <주소>`: 숨김 입력·토큰 생성·Railway 변수 설정·`config.json` 저장 |
| `SKILL_DIR/scripts/vl.py` (수정) | `upload`·`connect` 명령 등록 |
| `WEB/common.js`·`library.html`·`library.js`·`lecture.js`·`app.css` (수정) | 관리자 로그인·[공개/비공개]·[삭제], 호스팅에서 진행 카드·요청 버튼 숨김 |
| `SKILL_DIR/SKILL.md` (수정) | 12단계 업로드, `--no-upload`, Railway 연결 안내 |
| `docs/api.md` (수정) | 호스팅 API 세부(상태 코드·헤더·`visibility`) |
| `railway/Dockerfile`, `.dockerignore` (새) | Railway 이미지 |
| `TESTS/conftest.py` (수정) | 인터넷 차단 가드 |
| `TESTS/test_store_hosted.py`, `test_auth.py`, `test_server_hosted.py`, `test_remote.py`, `test_upload.py`, `test_connect.py`, `test_deploy_files.py` (새) | 테스트 |

---

### Task 1: 검색 범위 + `store_hosted` — Railway용 파일 저장소

**Files:**
- Modify: `PKG/search.py` (`SearchIndex.search`)
- Create: `PKG/store_hosted.py`
- Test: `TESTS/test_store_hosted.py`

**Interfaces:**
- Consumes: `FileStore(home)`(`list_lectures`, `get_lecture`, `all_lectures`, `list_jobs`, `version`), `validate_lecture(doc) -> list[str]`, `library.update_index(home, doc)`, `library.rebuild_index(home)`, `config.lecture_dir`, `config.write_json`, `config.read_json`, `jobs.STEPS`, `jobs.STEP_STATUSES`.
- Produces:
  - `SearchIndex.search(query, field=None, video=None, limit=20, allowed: set[str] | None = None) -> dict`
  - `class UploadError(ValueError)` — `.errors: list[str]`
  - `check_job(job_id, job) -> list[str]`
  - `class HostedStore(FileStore)`: `public_ids() -> set[str]`, `put_lecture(lecture_id, doc) -> bool`(공개 여부), `set_public(lecture_id, public: bool) -> bool`(없으면 False), `delete_lecture(lecture_id) -> bool`, `put_job(job_id, job) -> None`

- [ ] **Step 1: Write the failing test**

`TESTS/test_store_hosted.py`:

```python
import pytest

from conftest import VIDEO_ID
from test_library import make_doc
from video_library import jobs
from video_library.config import lecture_dir, read_json, write_json
from video_library.search import SearchIndex
from video_library.store_hosted import HostedStore, UploadError, check_job


def test_search_respects_allowed_ids():
    index = SearchIndex([make_doc()])
    assert index.search("기초")["results"]
    assert index.search("기초", allowed=set())["results"] == []
    assert index.search("기초", allowed={VIDEO_ID})["results"][0]["id"] == VIDEO_ID


def test_upload_new_lecture_is_private(home):
    store = HostedStore(home)
    assert store.put_lecture(VIDEO_ID, make_doc()) is False
    assert (lecture_dir(home, VIDEO_ID) / "lecture.json").exists()
    assert [e["id"] for e in store.list_lectures()] == [VIDEO_ID]
    assert store.public_ids() == set()


def test_upload_rejects_bad_documents(home):
    store = HostedStore(home)
    broken = make_doc()
    del broken["segments"]
    with pytest.raises(UploadError) as err:
        store.put_lecture(VIDEO_ID, broken)
    assert err.value.errors
    with pytest.raises(UploadError):
        store.put_lecture("ZZZZZZZZZZZ", make_doc())  # 주소의 ID 와 문서 ID 가 다름
    with pytest.raises(UploadError):
        store.put_lecture("../escape", make_doc())
    assert store.list_lectures() == []


def test_publish_survives_reupload_and_delete_clears_it(home):
    store = HostedStore(home)
    assert store.set_public(VIDEO_ID, True) is False  # 아직 없는 강의
    store.put_lecture(VIDEO_ID, make_doc())
    assert store.set_public(VIDEO_ID, True) is True
    assert store.put_lecture(VIDEO_ID, make_doc(title="고친 제목")) is True
    assert store.public_ids() == {VIDEO_ID}
    assert store.set_public(VIDEO_ID, False) is True and store.public_ids() == set()
    store.set_public(VIDEO_ID, True)
    assert store.delete_lecture(VIDEO_ID) is True
    assert store.get_lecture(VIDEO_ID) is None and store.list_lectures() == []
    assert store.public_ids() == set()
    assert store.delete_lecture(VIDEO_ID) is False


@pytest.mark.parametrize("content", ["{망가진", '{"public": "AbCdEfGhIjK"}', '[1, 2]', '{"public": ["../x", 3]}'])
def test_broken_visibility_means_nothing_public(home, content):
    store = HostedStore(home)
    store.put_lecture(VIDEO_ID, make_doc())
    (home / "visibility.json").write_text(content, encoding="utf-8")
    assert store.public_ids() == set()


def make_job(tmp_path):
    # PC 쪽 영상자료실(다른 폴더)에서 만든 진짜 진행 기록 — 서버 폴더에는 미리 쓰지 않는다
    return jobs.start_job(tmp_path / "pc", VIDEO_ID, "깃 기초", jobs.initial_steps(False, True))


def test_put_job_accepts_real_job(home, tmp_path):
    store = HostedStore(home)
    job = make_job(tmp_path)
    assert not (home / "jobs" / f"{job['job_id']}.json").exists()
    store.put_job(job["job_id"], job)
    assert read_json(home / "jobs" / f"{job['job_id']}.json") == job
    assert check_job(job["job_id"], job) == []


@pytest.mark.parametrize("change", [
    lambda j: j.update(job_id="other"),
    lambda j: j.update(updated_at="2026-10-06T10:00:00"),  # 시간대 없음
    lambda j: j["steps"].update(hack="done"),
    lambda j: j["steps"].update(fetch="exploded"),
    lambda j: j.update(status="paused"),
    lambda j: j.update(extra="x"),
    lambda j: j.update(title="가" * 301),
])
def test_put_job_rejects_bad_jobs(home, tmp_path, change):
    job = make_job(tmp_path)
    job_id = job["job_id"]
    change(job)
    with pytest.raises(UploadError):
        HostedStore(home).put_job(job_id, job)


def test_put_job_rejects_bad_id(home, tmp_path):
    job = make_job(tmp_path)
    with pytest.raises(UploadError):
        HostedStore(home).put_job("../../index", job)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -W error -q plugin/video-library/skills/video-library/tests/test_store_hosted.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'video_library.store_hosted'`

- [ ] **Step 3: Write minimal implementation**

`PKG/search.py` — `search` 시그니처와 반복문 첫 줄만 바꾼다:

```python
    def search(self, query: str, field: str | None = None, video: str | None = None,
               limit: int = MAX_HITS_PER_LECTURE, allowed: set[str] | None = None) -> dict:
        needle = normalize_query(query or "")
        results = []
        if needle:
            for lec, rows in self._docs:
                if (field and lec["field"] != field) or (video and lec["id"] != video):
                    continue
                if allowed is not None and lec["id"] not in allowed:
                    continue
```

(나머지 본문은 그대로.)

`PKG/store_hosted.py`:

```python
"""Railway 서버용 저장소: 영상자료실과 같은 파일 형식을 볼륨(/data)에 쓴다. 업로드·공개 상태·삭제·진행 보고."""
from __future__ import annotations

import re
import shutil
import threading
from datetime import datetime

from .config import VIDEO_ID_RE, lecture_dir, read_json, write_json
from .jobs import STEP_STATUSES, STEPS
from .library import rebuild_index, update_index
from .store_file import FileStore
from .validate import validate_lecture

VISIBILITY = "visibility.json"
JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}-\d{4}-\d{4}$")
JOB_STATUSES = ("running", "done", "failed")
JOB_KEYS = {"job_id", "lecture_id", "title", "status", "started_at", "updated_at", "steps", "detail", "error"}


class UploadError(ValueError):
    """받은 자료가 약속과 다를 때(서버는 400 으로 돌려준다)."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors[:5]))
        self.errors = errors


def _aware(value) -> bool:
    try:
        return datetime.fromisoformat(value).tzinfo is not None
    except (TypeError, ValueError):
        return False


def check_job(job_id, job) -> list[str]:
    if not isinstance(job_id, str) or not JOB_ID_RE.match(job_id):
        return ["job_id 형식이 올바르지 않습니다"]
    if not isinstance(job, dict):
        return ["진행 기록은 객체여야 합니다"]
    errors = []
    if set(job) != JOB_KEYS:
        errors.append(f"키가 약속과 다릅니다: {sorted(set(job) ^ JOB_KEYS)}")
    if job.get("job_id") != job_id:
        errors.append("job_id 가 주소와 다릅니다")
    lid = job.get("lecture_id")
    if not isinstance(lid, str) or not VIDEO_ID_RE.match(lid) or not job_id.startswith(lid + "-"):
        errors.append("lecture_id 가 올바르지 않습니다")
    if not isinstance(job.get("title"), str) or len(job["title"]) > 300:
        errors.append("title 은 300자 이하 글자")
    if job.get("status") not in JOB_STATUSES:
        errors.append("status 가 올바르지 않습니다")
    for key in ("started_at", "updated_at"):
        if not _aware(job.get(key)):
            errors.append(f"{key} 는 시간대가 있는 ISO 시각이어야 합니다")
    steps = job.get("steps")
    if not isinstance(steps, dict) or not set(steps) <= set(STEPS) or \
            any(v not in STEP_STATUSES for v in steps.values()):
        errors.append("steps 가 올바르지 않습니다")
    if not isinstance(job.get("detail"), str) or len(job["detail"]) > 200:
        errors.append("detail 은 200자 이하 글자")
    if job.get("error") is not None and (not isinstance(job["error"], str) or len(job["error"]) > 300):
        errors.append("error 는 300자 이하 글자 또는 null")
    return errors


class HostedStore(FileStore):
    def __init__(self, home):
        super().__init__(home)
        self._write_lock = threading.Lock()  # 동시에 들어온 업로드가 index.json 을 덮어쓰지 않게

    def public_ids(self) -> set[str]:
        try:
            data = read_json(self.home / VISIBILITY)
        except (ValueError, OSError):
            return set()  # 깨지거나 없으면 아무것도 공개하지 않는다
        ids = data.get("public") if isinstance(data, dict) else None
        if not isinstance(ids, list):
            return set()
        return {i for i in ids if isinstance(i, str) and VIDEO_ID_RE.match(i)}

    def _save_public(self, ids: set[str]) -> None:
        write_json(self.home / VISIBILITY, {"public": sorted(ids)})

    def put_lecture(self, lecture_id, doc) -> bool:
        if not isinstance(lecture_id, str) or not VIDEO_ID_RE.match(lecture_id):
            raise UploadError(["주소의 강의 ID 가 올바르지 않습니다"])
        errors = validate_lecture(doc)
        if errors:
            raise UploadError(errors)
        if doc["lecture"]["id"] != lecture_id:
            raise UploadError(["주소의 강의 ID 와 lecture.id 가 다릅니다"])
        with self._write_lock:
            write_json(lecture_dir(self.home, lecture_id) / "lecture.json", doc)
            update_index(self.home, doc)
            return lecture_id in self.public_ids()

    def set_public(self, lecture_id, public: bool) -> bool:
        with self._write_lock:
            if self.get_lecture(lecture_id) is None:
                return False
            ids = self.public_ids()
            if public:
                ids.add(lecture_id)
            else:
                ids.discard(lecture_id)
            self._save_public(ids)
            return True

    def delete_lecture(self, lecture_id) -> bool:
        with self._write_lock:
            if self.get_lecture(lecture_id) is None:
                return False
            shutil.rmtree(lecture_dir(self.home, lecture_id))
            rebuild_index(self.home)
            ids = self.public_ids()
            ids.discard(lecture_id)
            self._save_public(ids)
            return True

    def put_job(self, job_id, job) -> None:
        errors = check_job(job_id, job)
        if errors:
            raise UploadError(errors)
        write_json(self.home / "jobs" / f"{job_id}.json", job)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -W error -q plugin/video-library/skills/video-library/tests/test_store_hosted.py plugin/video-library/skills/video-library/tests/test_search.py`
Expected: PASS (모두)

- [ ] **Step 5: Commit**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/search.py plugin/video-library/skills/video-library/scripts/video_library/store_hosted.py plugin/video-library/skills/video-library/tests/test_store_hosted.py
git commit -m "feat(stage4): hosted file store with visibility, delete and job reports" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `auth` — 비밀번호·토큰 해시, 세션, 로그인 잠금

**Files:**
- Create: `PKG/auth.py`
- Test: `TESTS/test_auth.py`

**Interfaces:**
- Produces:
  - `hash_password(password: str, salt: bytes | None = None, iterations: int = PBKDF2_ITERATIONS) -> str`
  - `verify_password(password: str, stored: str) -> bool`
  - `hash_token(token: str) -> str`
  - `session_cookie(sid: str, expire: bool = False) -> str`
  - `COOKIE = "vl_session"`, `SESSION_TTL_SEC`, `LOGIN_WINDOW_SEC`, `LOGIN_MAX_FAILURES`
  - `class LoginLocked(Exception)`
  - `class Auth(password_hash, token_hash, clock=time.monotonic)`: `check_token(authorization_header) -> bool`, `login(password) -> str | None`(잠금이면 `LoginLocked`), `session_ok(sid) -> bool`, `logout(sid) -> None`. 생성자는 해시 형식이 틀리면 `ValueError`.

- [ ] **Step 1: Write the failing test**

`TESTS/test_auth.py`:

```python
import pytest

from video_library import auth

PW = "시험용-관리자-비번"
TOKEN = "test-upload-token"


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make(clock=None):
    return auth.Auth(auth.hash_password(PW, iterations=1000), auth.hash_token(TOKEN), clock=clock or Clock())


def test_password_hash_roundtrip_and_format():
    stored = auth.hash_password(PW, iterations=1000)
    algo, iters, salt, digest = stored.split("$")
    assert algo == "pbkdf2_sha256" and iters == "1000" and len(salt) == 32 and len(digest) == 64
    assert PW not in stored
    assert auth.verify_password(PW, stored) and not auth.verify_password(PW + "x", stored)
    assert auth.hash_password(PW, iterations=1000) != stored  # salt 가 매번 다르다
    for broken in ("", "md5$1$00$00", "pbkdf2_sha256$x$zz$00", None):
        assert auth.verify_password(PW, broken) is False


def test_default_iterations_are_strong():
    assert auth.PBKDF2_ITERATIONS >= 200_000


def test_token_check():
    a = make()
    assert a.check_token(f"Bearer {TOKEN}")
    for bad in (None, "", TOKEN, "Bearer wrong", f"Basic {TOKEN}"):
        assert not a.check_token(bad)
    assert len(auth.hash_token(TOKEN)) == 64


@pytest.mark.parametrize("pw_hash, token_hash", [
    ("", "a" * 64), ("plain-password", "a" * 64), (None, "a" * 64),
    ("pbkdf2_sha256$1000$00$00", "short"), ("pbkdf2_sha256$1000$00$00", "Z" * 64)])
def test_rejects_bad_hash_settings(pw_hash, token_hash):
    with pytest.raises(ValueError):
        auth.Auth(pw_hash, token_hash)


def test_login_session_and_expiry():
    clock = Clock()
    a = make(clock)
    assert a.login("틀림") is None
    sid = a.login(PW)
    assert sid and a.session_ok(sid) and not a.session_ok("guess") and not a.session_ok(None)
    clock.now += auth.SESSION_TTL_SEC + 1
    assert not a.session_ok(sid)


def test_logout():
    a = make()
    sid = a.login(PW)
    a.logout(sid)
    assert not a.session_ok(sid)
    a.logout(None)  # 오류 없음


def test_lock_after_many_failures_even_for_right_password():
    clock = Clock()
    a = make(clock)
    for _ in range(auth.LOGIN_MAX_FAILURES):
        assert a.login("틀림") is None
    with pytest.raises(auth.LoginLocked):
        a.login(PW)
    clock.now += auth.LOGIN_WINDOW_SEC + 1
    assert a.login(PW)


def test_cookie_flags():
    c = auth.session_cookie("abc")
    assert c.startswith("vl_session=abc;")
    for flag in ("HttpOnly", "Secure", "SameSite=Strict", "Path=/", f"Max-Age={auth.SESSION_TTL_SEC}"):
        assert flag in c
    assert "Max-Age=0" in auth.session_cookie("", expire=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -W error -q plugin/video-library/skills/video-library/tests/test_auth.py`
Expected: FAIL — `ImportError: cannot import name 'auth'`

- [ ] **Step 3: Write minimal implementation**

`PKG/auth.py`:

```python
"""Railway 관리자 로그인과 업로드 토큰 확인. 비밀번호·토큰은 해시로만 다룬다(표준 라이브러리)."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time

PBKDF2_ITERATIONS = 200_000
SESSION_TTL_SEC = 12 * 3600
LOGIN_WINDOW_SEC = 15 * 60
LOGIN_MAX_FAILURES = 10
COOKIE = "vl_session"
_HEX = set("0123456789abcdef")


def hash_password(password: str, salt: bytes | None = None, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, digest_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iters))
    except (ValueError, AttributeError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_cookie(sid: str, expire: bool = False) -> str:
    age = 0 if expire else SESSION_TTL_SEC
    return f"{COOKIE}={sid}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age={age}"


class LoginLocked(Exception):
    """로그인 실패가 많아 잠시 막힌 상태."""


class Auth:
    def __init__(self, password_hash: str, token_hash: str, clock=time.monotonic):
        if not isinstance(password_hash, str) or not password_hash.startswith("pbkdf2_sha256$") \
                or password_hash.count("$") != 3:
            raise ValueError("VL_ADMIN_PASSWORD_HASH 형식이 올바르지 않습니다")
        if not isinstance(token_hash, str) or len(token_hash) != 64 or not set(token_hash) <= _HEX:
            raise ValueError("VL_UPLOAD_TOKEN_HASH 형식이 올바르지 않습니다")
        self._password_hash = password_hash
        self._token_hash = token_hash
        self._clock = clock
        self._sessions: dict[str, float] = {}
        self._failures: list[float] = []
        self._lock = threading.Lock()

    def check_token(self, authorization) -> bool:
        if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
            return False
        return hmac.compare_digest(hash_token(authorization[len("Bearer "):].strip()), self._token_hash)

    def login(self, password: str) -> str | None:
        with self._lock:
            now = self._clock()
            self._failures = [t for t in self._failures if now - t < LOGIN_WINDOW_SEC]
            if len(self._failures) >= LOGIN_MAX_FAILURES:
                raise LoginLocked()
        ok = verify_password(password, self._password_hash)  # 느린 계산은 잠금 밖에서
        with self._lock:
            if not ok:
                self._failures.append(self._clock())
                return None
            sid = secrets.token_urlsafe(32)
            self._sessions[sid] = self._clock() + SESSION_TTL_SEC
            return sid

    def session_ok(self, sid) -> bool:
        if not sid:
            return False
        with self._lock:
            expires = self._sessions.get(sid)
            if expires is None:
                return False
            if expires <= self._clock():
                del self._sessions[sid]
                return False
            return True

    def logout(self, sid) -> None:
        if sid:
            with self._lock:
                self._sessions.pop(sid, None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -W error -q plugin/video-library/skills/video-library/tests/test_auth.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/auth.py plugin/video-library/skills/video-library/tests/test_auth.py
git commit -m "feat(stage4): admin password and upload token hashing, sessions, login lock" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `server` 호스팅 모드 — 공개 범위, 업로드, 관리자 쓰기

**Files:**
- Modify: `PKG/server.py` (`LibraryServer.__init__`, `_Handler` 전체 교체)
- Test: `TESTS/test_server_hosted.py`; 기존 `TESTS/test_server.py`는 그대로 통과해야 한다.

**Interfaces:**
- Consumes: Task 1 `HostedStore`, `UploadError`, `SearchIndex.search(..., allowed=)`; Task 2 `Auth`, `LoginLocked`, `COOKIE`, `session_cookie`.
- Produces:
  - `LibraryServer(addr, store, web_dir, idle_timeout=IDLE_TIMEOUT_SEC, auth: Auth | None = None)` — `.auth`, `.hosted: bool`
  - `GET /api/health` → PC `{"app","mode":"pc","home"}`, 호스팅 `{"app","mode":"hosted","admin"}`
  - 상수 `LECTURE_MAX_BYTES = 20 * 1024 * 1024`, `SMALL_MAX_BYTES = 64 * 1024`, `WRITE_HEADER = ("X-Requested-With", "video-library")`
  - 호스팅 쓰기 경로: `POST /api/login` `{"password"}`, `POST /api/logout`, `POST /api/jobs/<job_id>`(토큰), `PUT /api/lectures/<id>`(토큰), `PATCH /api/lectures/<id>` `{"public": bool}`(관리자), `DELETE /api/lectures/<id>`(관리자)

- [ ] **Step 1: Write the failing test**

`TESTS/test_server_hosted.py`:

```python
import http.client
import json
import threading

import pytest

from conftest import VIDEO_ID
from test_library import make_doc
from test_server import make_web
from video_library import auth, jobs
from video_library.server import LibraryServer
from video_library.store_hosted import HostedStore

TOKEN = "test-upload-token"
PASSWORD = "test-admin-password"
WRITE = {"X-Requested-With": "video-library"}
BEARER = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def hosted(home):
    a = auth.Auth(auth.hash_password(PASSWORD, iterations=1000), auth.hash_token(TOKEN))
    server = LibraryServer(("127.0.0.1", 0), HostedStore(home), make_web(home), auth=a)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def call(server, method, path, body=None, headers=None, raw=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
    data = raw if raw is not None else (json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None)
    conn.request(method, path, body=data, headers=dict(headers or {}))
    resp = conn.getresponse()
    payload = resp.read()
    conn.close()
    return resp, (json.loads(payload.decode("utf-8")) if payload else None)


def login(server):
    resp, _ = call(server, "POST", "/api/login", {"password": PASSWORD}, WRITE)
    assert resp.status == 200
    return {"Cookie": resp.getheader("Set-Cookie").split(";")[0]}


def upload(server, doc=None):
    return call(server, "PUT", f"/api/lectures/{VIDEO_ID}", doc or make_doc(), BEARER)


def test_health_hides_home_and_reports_admin(hosted):
    _, body = call(hosted, "GET", "/api/health")
    assert body == {"app": "video-library", "mode": "hosted", "admin": False}
    _, body = call(hosted, "GET", "/api/health", headers=login(hosted))
    assert body["admin"] is True


def test_public_host_name_is_allowed(hosted):
    resp, _ = call(hosted, "GET", "/api/health", headers={"Host": "video-library.up.railway.app"})
    assert resp.status == 200


def test_upload_needs_right_token(hosted):
    for headers in ({}, {"Authorization": "Bearer wrong"}, {"Authorization": TOKEN}):
        resp, body = call(hosted, "PUT", f"/api/lectures/{VIDEO_ID}", make_doc(), headers)
        assert resp.status == 401 and "토큰" in body["error"]
    resp, body = upload(hosted)
    assert resp.status == 200 and body == {"id": VIDEO_ID, "public": False}


def test_private_lecture_hidden_from_visitors(hosted):
    upload(hosted)
    assert call(hosted, "GET", "/api/lectures")[1] == []
    assert call(hosted, "GET", f"/api/lectures/{VIDEO_ID}")[0].status == 404
    assert call(hosted, "GET", "/api/search?q=기초")[1]["results"] == []
    resp, _ = call(hosted, "GET", "/api/jobs")
    assert resp.status == 401


def test_admin_sees_all_and_publishes(hosted):
    upload(hosted)
    admin = login(hosted)
    items = call(hosted, "GET", "/api/lectures", headers=admin)[1]
    assert [(e["id"], e["public"]) for e in items] == [(VIDEO_ID, False)]
    assert call(hosted, "GET", "/api/search?q=기초", headers=admin)[1]["results"]
    resp, _ = call(hosted, "PATCH", f"/api/lectures/{VIDEO_ID}", {"public": True}, admin)  # 요청 헤더 빠짐
    assert resp.status == 403
    resp, body = call(hosted, "PATCH", f"/api/lectures/{VIDEO_ID}", {"public": True}, {**admin, **WRITE})
    assert resp.status == 200 and body == {"id": VIDEO_ID, "public": True}
    items = call(hosted, "GET", "/api/lectures")[1]
    assert [(e["id"], e["public"]) for e in items] == [(VIDEO_ID, True)]
    assert call(hosted, "GET", f"/api/lectures/{VIDEO_ID}")[0].status == 200
    assert call(hosted, "GET", "/api/search?q=기초")[1]["results"]
    assert upload(hosted)[1]["public"] is True  # 재업로드해도 공개 유지


def test_admin_writes_need_login(hosted):
    upload(hosted)
    for method, body in (("PATCH", {"public": True}), ("DELETE", None)):
        resp, _ = call(hosted, method, f"/api/lectures/{VIDEO_ID}", body, WRITE)
        assert resp.status == 401
    resp, _ = call(hosted, "PATCH", f"/api/lectures/{VIDEO_ID}", {"public": "yes"}, {**login(hosted), **WRITE})
    assert resp.status == 400


def test_delete(hosted):
    upload(hosted)
    admin = {**login(hosted), **WRITE}
    assert call(hosted, "DELETE", f"/api/lectures/{VIDEO_ID}", headers=admin)[0].status == 200
    assert call(hosted, "GET", f"/api/lectures/{VIDEO_ID}", headers=admin)[0].status == 404
    assert call(hosted, "DELETE", f"/api/lectures/{VIDEO_ID}", headers=admin)[0].status == 404


def test_bad_uploads_rejected(hosted):
    broken = make_doc()
    del broken["segments"]
    assert upload(hosted, broken)[0].status == 400
    resp, _ = call(hosted, "PUT", "/api/lectures/ZZZZZZZZZZZ", make_doc(), BEARER)
    assert resp.status == 400
    resp, _ = call(hosted, "PUT", f"/api/lectures/{VIDEO_ID}", headers=BEARER, raw=b"{not json")
    assert resp.status == 400
    assert call(hosted, "GET", "/api/lectures", headers=login(hosted))[1] == []


def test_too_large_upload_rejected_without_reading(hosted):
    conn = http.client.HTTPConnection("127.0.0.1", hosted.port, timeout=10)
    conn.putrequest("PUT", f"/api/lectures/{VIDEO_ID}")
    conn.putheader("Authorization", f"Bearer {TOKEN}")
    conn.putheader("Content-Length", str(21 * 1024 * 1024))
    conn.endheaders()
    resp = conn.getresponse()
    assert resp.status == 413
    conn.close()


def test_login_errors_and_lock(hosted):
    resp, _ = call(hosted, "POST", "/api/login", {"password": PASSWORD})  # 요청 헤더 빠짐
    assert resp.status == 403
    for _ in range(auth.LOGIN_MAX_FAILURES):
        resp, body = call(hosted, "POST", "/api/login", {"password": "틀림"}, WRITE)
        assert resp.status == 401
    resp, body = call(hosted, "POST", "/api/login", {"password": PASSWORD}, WRITE)
    assert resp.status == 429 and "15분" in body["error"]


def test_login_cookie_and_logout(hosted):
    resp, _ = call(hosted, "POST", "/api/login", {"password": PASSWORD}, WRITE)
    cookie = resp.getheader("Set-Cookie")
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=Strict" in cookie
    admin = {"Cookie": cookie.split(";")[0]}
    resp, _ = call(hosted, "POST", "/api/logout", headers={**admin, **WRITE})
    assert resp.status == 200 and "Max-Age=0" in resp.getheader("Set-Cookie")
    assert call(hosted, "GET", "/api/health", headers=admin)[1]["admin"] is False


def test_job_reports(hosted, tmp_path):
    job = jobs.start_job(tmp_path / "pc", VIDEO_ID, "깃 기초", jobs.initial_steps(False, True))  # PC 쪽 기록
    path = f"/api/jobs/{job['job_id']}"
    assert call(hosted, "POST", path, job)[0].status == 401
    resp, body = call(hosted, "POST", path, job, BEARER)
    assert resp.status == 200 and body == {"job_id": job["job_id"]}
    assert call(hosted, "POST", path, {**job, "status": "paused"}, BEARER)[0].status == 400
    listed = call(hosted, "GET", "/api/jobs", headers=login(hosted))[1]
    assert [j["job_id"] for j in listed] == [job["job_id"]]


def test_unknown_write_paths(hosted):
    assert call(hosted, "POST", "/api/nothing", {}, BEARER)[0].status == 404
    assert call(hosted, "PUT", "/api/jobs/x", {}, BEARER)[0].status == 404
```

`TESTS/test_server.py` 의 `test_api_jobs_and_health`에서 health 기대값에 `"mode": "pc"`가 들어가도록 한 줄 고친다(기존 단언이 `home` 키만 본다면 그대로 두고 아래 한 줄을 추가):

```python
    assert get_json(live, "/api/health")[1]["mode"] == "pc"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -W error -q plugin/video-library/skills/video-library/tests/test_server_hosted.py plugin/video-library/skills/video-library/tests/test_server.py`
Expected: FAIL — `TypeError: LibraryServer.__init__() got an unexpected keyword argument 'auth'` (그리고 `mode` 단언 실패)

- [ ] **Step 3: Write minimal implementation**

`PKG/server.py` 위쪽 import에 추가:

```python
from http.cookies import CookieError, SimpleCookie

from .auth import COOKIE, Auth, LoginLocked, session_cookie
from .store_hosted import UploadError
```

상수 추가(`CSP` 아래):

```python
LECTURE_MAX_BYTES = 20 * 1024 * 1024
SMALL_MAX_BYTES = 64 * 1024
WRITE_HEADER = ("X-Requested-With", "video-library")
LECTURES = "/api/lectures/"
JOBS = "/api/jobs/"
```

`LibraryServer.__init__` 시그니처와 두 줄:

```python
    def __init__(self, addr, store: FileStore, web_dir: Path, idle_timeout: float = IDLE_TIMEOUT_SEC,
                 auth: Auth | None = None):
        super().__init__(addr, _Handler)
        self.store = store
        self.auth = auth
        self.hosted = auth is not None  # Railway: 로그인·업로드·공개 범위. PC: 읽기 전용
```

(나머지 속성은 그대로.)

`_Handler` 클래스를 통째로 아래로 바꾼다:

```python
class _HttpError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class _Handler(BaseHTTPRequestHandler):
    server_version = "video-library"

    def log_message(self, fmt, *args):  # 콘솔을 조용히 둔다
        pass

    def do_GET(self):
        self._dispatch(self._get)

    def do_POST(self):
        self._dispatch(self._post)

    def do_PUT(self):
        self._dispatch(self._put)

    def do_PATCH(self):
        self._dispatch(self._patch)

    def do_DELETE(self):
        self._dispatch(self._delete)

    def _dispatch(self, route):
        self.server.touch()
        if not self.server.hosted:
            if not self._host_ok():
                return self._error(403, "허용되지 않은 접근입니다")
            if route != self._get:
                return self._error(405, "읽기 전용 서버입니다")
        parts = urlsplit(self.path)
        try:
            route(parts.path, parse_qs(parts.query))
        except _HttpError as exc:
            self._error(exc.status, exc.message)
        except Exception as exc:  # 한 요청의 오류로 서버가 멈추지 않게
            self._error(500, f"서버 오류: {type(exc).__name__}")

    # ---- 읽기 ----
    def _get(self, path, query):
        store = self.server.store
        if path in PAGES:
            return self._static(PAGES[path])
        if path.startswith("/app/"):
            return self._static(path[len("/app/"):])
        if path == "/api/health":
            if self.server.hosted:
                return self._json(200, {"app": "video-library", "mode": "hosted", "admin": self._is_admin()})
            return self._json(200, {"app": "video-library", "mode": "pc", "home": str(store.home)})
        if path == "/api/lectures":
            return self._json(200, self._visible_list())
        if path.startswith(LECTURES):
            lecture_id = unquote(path[len(LECTURES):])
            doc = store.get_lecture(lecture_id) if self._can_see(lecture_id) else None
            return self._json(200, doc) if doc else self._error(404, "강의를 찾을 수 없습니다")
        if path == "/api/search":
            first = lambda key: (query.get(key) or [None])[0] or None
            allowed = None if self._sees_all() else store.public_ids()
            return self._json(200, self.server.search_index().search(
                first("q") or "", first("field"), first("video"), allowed=allowed))
        if path == "/api/jobs":
            if not self._sees_all():
                raise _HttpError(401, "관리자 로그인이 필요합니다")
            return self._json(200, store.list_jobs())
        raise _HttpError(404, "없는 주소입니다")

    def _visible_list(self) -> list:
        items = self.server.store.list_lectures()
        if not self.server.hosted:
            return items
        public = self.server.store.public_ids()
        if not self._is_admin():
            items = [e for e in items if isinstance(e, dict) and e.get("id") in public]
        return [dict(e, public=e.get("id") in public) for e in items if isinstance(e, dict)]

    # ---- 쓰기(호스팅 모드만) ----
    def _post(self, path, query):
        auth = self.server.auth
        if path == "/api/login":
            self._require_write_header()
            body = self._read_json(SMALL_MAX_BYTES)
            password = body.get("password") if isinstance(body, dict) else None
            if not isinstance(password, str):
                raise _HttpError(400, "비밀번호가 필요합니다")
            try:
                sid = auth.login(password)
            except LoginLocked:
                raise _HttpError(429, "로그인 시도가 너무 많습니다. 15분 뒤 다시 시도하세요")
            if not sid:
                raise _HttpError(401, "비밀번호가 맞지 않습니다")
            return self._json(200, {"admin": True}, {"Set-Cookie": session_cookie(sid)})
        if path == "/api/logout":
            self._require_write_header()
            auth.logout(self._session_id())
            return self._json(200, {"admin": False}, {"Set-Cookie": session_cookie("", expire=True)})
        if path.startswith(JOBS):
            self._require_token()
            job_id = unquote(path[len(JOBS):])
            body = self._read_json(SMALL_MAX_BYTES)
            try:
                self.server.store.put_job(job_id, body)
            except UploadError as exc:
                raise _HttpError(400, str(exc))
            return self._json(200, {"job_id": job_id})
        raise _HttpError(404, "없는 주소입니다")

    def _put(self, path, query):
        lecture_id = self._lecture_id(path)
        self._require_token()
        doc = self._read_json(LECTURE_MAX_BYTES)
        try:
            public = self.server.store.put_lecture(lecture_id, doc)
        except UploadError as exc:
            raise _HttpError(400, str(exc))
        return self._json(200, {"id": lecture_id, "public": public})

    def _patch(self, path, query):
        lecture_id = self._lecture_id(path)
        self._require_admin()
        body = self._read_json(SMALL_MAX_BYTES)
        if not isinstance(body, dict) or not isinstance(body.get("public"), bool):
            raise _HttpError(400, '{"public": true 또는 false} 형식이어야 합니다')
        if not self.server.store.set_public(lecture_id, body["public"]):
            raise _HttpError(404, "강의를 찾을 수 없습니다")
        return self._json(200, {"id": lecture_id, "public": body["public"]})

    def _delete(self, path, query):
        lecture_id = self._lecture_id(path)
        self._require_admin()
        if not self.server.store.delete_lecture(lecture_id):
            raise _HttpError(404, "강의를 찾을 수 없습니다")
        return self._json(200, {"id": lecture_id, "deleted": True})

    # ---- 권한·본문 ----
    def _lecture_id(self, path) -> str:
        if not path.startswith(LECTURES):
            raise _HttpError(404, "없는 주소입니다")
        return unquote(path[len(LECTURES):])

    def _session_id(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except CookieError:
            return None
        morsel = cookie.get(COOKIE)
        return morsel.value if morsel else None

    def _is_admin(self) -> bool:
        return self.server.hosted and self.server.auth.session_ok(self._session_id())

    def _sees_all(self) -> bool:
        return not self.server.hosted or self._is_admin()

    def _can_see(self, lecture_id) -> bool:
        return self._sees_all() or lecture_id in self.server.store.public_ids()

    def _require_write_header(self):
        name, value = WRITE_HEADER
        if self.headers.get(name) != value:
            raise _HttpError(403, "요청 형식이 올바르지 않습니다")

    def _require_admin(self):
        self._require_write_header()
        if not self._is_admin():
            raise _HttpError(401, "관리자 로그인이 필요합니다")

    def _require_token(self):
        if not self.server.auth.check_token(self.headers.get("Authorization")):
            raise _HttpError(401, "업로드 토큰이 맞지 않습니다")

    def _read_json(self, limit: int):
        length = self.headers.get("Content-Length")
        if length is None or not length.isdigit():
            raise _HttpError(411, "본문 길이(Content-Length)가 필요합니다")
        if int(length) > limit:
            raise _HttpError(413, "본문이 너무 큽니다")
        raw = self.rfile.read(int(length))
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise _HttpError(400, "JSON 형식이 아닙니다")

    # ---- 응답 ----
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

    def _json(self, status: int, data, headers: dict | None = None) -> None:
        self._send(status, "application/json; charset=utf-8",
                   json.dumps(data, ensure_ascii=False).encode("utf-8"), headers)

    def _error(self, status: int, message: str) -> None:
        self._json(status, {"error": message})

    def _send(self, status: int, ctype: str, body: bytes, headers: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CSP)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)
```

참고: `BaseHTTPRequestHandler`의 기본 `protocol_version`은 `HTTP/1.0`이라 응답마다 연결을 닫는다 — 413·401로 본문을 읽지 않고 답해도 다음 요청과 섞이지 않는다.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -W error -q plugin/video-library/skills/video-library/tests`
Expected: PASS (기존 테스트 포함 전부)

- [ ] **Step 5: Commit**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/server.py plugin/video-library/skills/video-library/tests/test_server_hosted.py plugin/video-library/skills/video-library/tests/test_server.py
git commit -m "feat(stage4): hosted server mode with visibility, uploads and admin writes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `vl.py serve --hosted` — 환경변수로 Railway 서버 켜기

**Files:**
- Modify: `PKG/server.py` (`hosted_server`, `main`)
- Test: `TESTS/test_server_hosted.py` (추가)

**Interfaces:**
- Consumes: Task 3 `LibraryServer(..., auth=)`, Task 1 `HostedStore`, Task 2 `Auth`.
- Produces:
  - `BUNDLED_WEB = Path(__file__).resolve().parent.parent.parent / "web"` — 스킬 폴더의 `web/`(Docker에서는 `/srv/web`)
  - `hosted_server(env: Mapping[str, str], host: str = "0.0.0.0") -> LibraryServer` — `VL_ADMIN_PASSWORD_HASH`·`VL_UPLOAD_TOKEN_HASH` 필수(없거나 틀리면 `StepError`), `PORT`(기본 8080), `VL_HOME`(기본 `/data`)
  - `vl.py serve --hosted`

- [ ] **Step 1: Write the failing test**

`TESTS/test_server_hosted.py` 끝에 추가:

```python
from video_library.config import StepError
from video_library.server import BUNDLED_WEB, hosted_server


def good_env(tmp_path):
    return {"VL_ADMIN_PASSWORD_HASH": auth.hash_password(PASSWORD, iterations=1000),
            "VL_UPLOAD_TOKEN_HASH": auth.hash_token(TOKEN), "PORT": "0", "VL_HOME": str(tmp_path / "data")}


def test_hosted_server_from_env(tmp_path):
    server = hosted_server(good_env(tmp_path), host="127.0.0.1")
    try:
        assert server.hosted and isinstance(server.store, HostedStore)
        assert server.web_dir == BUNDLED_WEB and (BUNDLED_WEB / "library.html").is_file()
        assert (tmp_path / "data").is_dir()
    finally:
        server.server_close()


@pytest.mark.parametrize("missing", ["VL_ADMIN_PASSWORD_HASH", "VL_UPLOAD_TOKEN_HASH"])
def test_hosted_server_refuses_without_secrets(tmp_path, missing):
    env = good_env(tmp_path)
    del env[missing]
    with pytest.raises(StepError, match=missing):
        hosted_server(env, host="127.0.0.1")


def test_hosted_server_refuses_plain_password(tmp_path):
    env = good_env(tmp_path) | {"VL_ADMIN_PASSWORD_HASH": "my-password"}
    with pytest.raises(StepError, match="형식"):
        hosted_server(env, host="127.0.0.1")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -W error -q plugin/video-library/skills/video-library/tests/test_server_hosted.py`
Expected: FAIL — `ImportError: cannot import name 'BUNDLED_WEB'`

- [ ] **Step 3: Write minimal implementation**

`PKG/server.py` import에 `from collections.abc import Mapping`, `from .store_hosted import HostedStore, UploadError`(Task 3의 줄을 이것으로 바꿈) 추가. 상수 추가:

```python
BUNDLED_WEB = Path(__file__).resolve().parent.parent.parent / "web"  # 스킬의 web/ (Docker: /srv/web)
SECRET_VARS = ("VL_ADMIN_PASSWORD_HASH", "VL_UPLOAD_TOKEN_HASH")
```

`run` 함수 아래에 추가:

```python
def hosted_server(env: Mapping[str, str], host: str = "0.0.0.0") -> LibraryServer:
    """Railway 서버. 비밀번호·토큰 해시가 없으면 켜지 않는다(실수로 열린 서버를 막는다)."""
    for name in SECRET_VARS:
        if not env.get(name):
            raise StepError(f"{name} 환경변수가 없습니다 — 사용자가 'vl.py connect' 로 설정합니다")
    try:
        auth = Auth(env["VL_ADMIN_PASSWORD_HASH"], env["VL_UPLOAD_TOKEN_HASH"])
    except ValueError as exc:
        raise StepError(str(exc)) from exc
    home = ensure_home(Path(env.get("VL_HOME") or "/data"))
    port = int(env.get("PORT") or 8080)
    return LibraryServer((host, port), HostedStore(home), BUNDLED_WEB, auth=auth)
```

`main`을 바꾼다:

```python
def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py serve", description="영상자료실 화면을 보여 주는 서버(PC 전용 미니 서버, 또는 --hosted 로 Railway 서버).")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--idle", type=float, default=IDLE_TIMEOUT_SEC, help="이 시간(초) 동안 요청이 없으면 끈다")
    ap.add_argument("--hosted", action="store_true", help="Railway 서버로 실행(환경변수 PORT·VL_HOME·해시 2개)")
    a = ap.parse_args(argv)
    if a.hosted:
        server = hosted_server(os.environ)
        print(f"video-library Railway 서버: 포트 {server.port}", flush=True)
        try:
            server.serve_forever(poll_interval=0.5)
        finally:
            server.server_close()
        return 0
    home = ensure_home(library_home())
    web = home / "app"
    if not (web / "library.html").exists():
        raise StepError("화면 파일이 없습니다. 'vl.py open' 으로 여세요.")
    server = bind(FileStore(home), web, a.port, a.idle)
    print(f"영상자료실: http://127.0.0.1:{server.port}  (1시간 동안 쓰지 않으면 스스로 꺼집니다)", flush=True)
    run(server, home / SERVER_STATE)
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -W error -q plugin/video-library/skills/video-library/tests/test_server_hosted.py plugin/video-library/skills/video-library/tests/test_server.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/server.py plugin/video-library/skills/video-library/tests/test_server_hosted.py
git commit -m "feat(stage4): vl.py serve --hosted reads secrets from env and refuses without them" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `remote` + 진행 보고 + 인터넷 차단 가드

**Files:**
- Create: `PKG/remote.py`
- Modify: `PKG/jobs.py` (기록할 때마다 `report_job`), `TESTS/conftest.py` (가드)
- Test: `TESTS/test_remote.py`

**Interfaces:**
- Consumes: `config.read_json`, `config.write_json`, `config.StepError`.
- Produces:
  - `CONFIG_NAME = "config.json"`, `REPORT_TIMEOUT_SEC = 3.0`
  - `class RemoteError(Exception)`
  - `normalize_server(url: str) -> str` — `https://…`(끝 `/` 제거). 시험용으로 `http://127.0.0.1:<포트>`·`http://localhost:<포트>`만 허용. 그 밖은 `StepError`
  - `load_config(home) -> dict` — `{"server", "token"}` 또는 `{}`(없거나 깨짐)
  - `save_config(home, server: str, token: str) -> Path`
  - `request(method, url, token, body=None, timeout=30.0) -> tuple[int, dict]` — 연결 실패·시간 초과는 `RemoteError`
  - `report_job(home, job, timeout=REPORT_TIMEOUT_SEC) -> bool` — 설정이 없으면 아무것도 안 함, 실패는 조용히 False
  - 테스트 헬퍼(`test_remote.py`): `FakeRailway` — 받은 요청을 `.calls`에 쌓는 127.0.0.1 서버

- [ ] **Step 1: Write the failing test**

`TESTS/conftest.py`에 추가(맨 아래):

```python
import socket

_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


@pytest.fixture(autouse=True)
def _no_internet(monkeypatch):
    """테스트는 내 PC 안(127.0.0.1)에만 연결한다 — 실제 Railway·유튜브로 나가면 바로 실패."""
    real_connect = socket.socket.connect
    real_getaddrinfo = socket.getaddrinfo

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if host not in _LOCAL_HOSTS:
            raise OSError(f"테스트 중 인터넷 연결 금지: {host}")
        return real_connect(self, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if host not in _LOCAL_HOSTS and host is not None:
            raise OSError(f"테스트 중 인터넷 연결 금지: {host}")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
```

`TESTS/test_remote.py`:

```python
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from conftest import VIDEO_ID
from video_library import jobs, remote
from video_library.config import StepError


class FakeRailway:
    """받은 요청을 기록하고 정해 둔 응답을 돌려주는 시험용 서버(127.0.0.1)."""

    def __init__(self, status=200, reply=None, delay=0.0):
        fake = self
        self.calls = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _any(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"null")
                fake.calls.append((self.command, self.path, self.headers.get("Authorization"), body))
                time.sleep(delay)
                data = json.dumps(reply if reply is not None else {"ok": True}).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = do_PUT = _any

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def fake():
    server = FakeRailway()
    yield server
    server.close()


def test_guard_blocks_internet():
    with pytest.raises(OSError, match="인터넷"):
        socket.create_connection(("example.com", 443), timeout=1)


@pytest.mark.parametrize("url, expected", [
    ("https://video-library.up.railway.app/", "https://video-library.up.railway.app"),
    ("https://example.com", "https://example.com"),
    ("http://127.0.0.1:8790", "http://127.0.0.1:8790"),
])
def test_normalize_server(url, expected):
    assert remote.normalize_server(url) == expected


@pytest.mark.parametrize("url", ["http://example.com", "ftp://x", "example.com", "", "https://", "https://a b"])
def test_normalize_server_rejects(url):
    with pytest.raises(StepError):
        remote.normalize_server(url)


def test_config_roundtrip_and_broken(home):
    assert remote.load_config(home) == {}
    remote.save_config(home, "https://x.up.railway.app", "tok")
    assert remote.load_config(home) == {"server": "https://x.up.railway.app", "token": "tok"}
    (home / "config.json").write_text("{망가짐", encoding="utf-8")
    assert remote.load_config(home) == {}
    (home / "config.json").write_text('{"server": "http://evil.com", "token": "t"}', encoding="utf-8")
    assert remote.load_config(home) == {}


def test_request_sends_token_and_json(fake):
    status, body = remote.request("PUT", f"{fake.url}/api/lectures/{VIDEO_ID}", "tok", {"a": 1})
    assert status == 200 and body == {"ok": True}
    assert fake.calls == [("PUT", f"/api/lectures/{VIDEO_ID}", "Bearer tok", {"a": 1})]


def test_request_error_status_is_returned():
    server = FakeRailway(status=401, reply={"error": "업로드 토큰이 맞지 않습니다"})
    try:
        assert remote.request("PUT", f"{server.url}/x", "t", {}) == (401, {"error": "업로드 토큰이 맞지 않습니다"})
    finally:
        server.close()


def test_request_connection_refused():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()  # 아무도 듣지 않는 포트
    with pytest.raises(remote.RemoteError):
        remote.request("GET", f"http://127.0.0.1:{port}/", "t", timeout=1)


def test_report_job_without_config_does_nothing(home, fake):
    job = jobs.start_job(home, VIDEO_ID, "깃 기초", jobs.initial_steps(False, False))
    assert remote.report_job(home, job) is False
    assert fake.calls == []


def test_jobs_report_every_write(home, fake):
    remote.save_config(home, fake.url, "tok")
    job = jobs.start_job(home, VIDEO_ID, "깃 기초", jobs.initial_steps(False, True))
    jobs.set_step(home, job["job_id"], "preprocess", "done")
    paths = [(m, p, a) for m, p, a, _ in fake.calls]
    assert paths == [("POST", f"/api/jobs/{job['job_id']}", "Bearer tok")] * 2
    assert fake.calls[-1][3]["steps"]["preprocess"] == "done"


def test_slow_railway_does_not_block(home):
    slow = FakeRailway(delay=2.0)
    try:
        remote.save_config(home, slow.url, "tok")
        job = jobs.start_job(home, VIDEO_ID, "깃 기초", jobs.initial_steps(False, True))
        began = time.monotonic()
        assert remote.report_job(home, job, timeout=0.3) is False
        assert time.monotonic() - began < 1.5
    finally:
        slow.close()
```


- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -W error -q plugin/video-library/skills/video-library/tests/test_remote.py`
Expected: FAIL — `ImportError: cannot import name 'remote'` (가드 테스트는 통과)

- [ ] **Step 3: Write minimal implementation**

`PKG/remote.py`:

```python
"""Railway 연결: config.json(서버 주소·업로드 토큰) 읽기·쓰기, 요청 보내기, 진행 보고. 표준 라이브러리만."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from .config import StepError, read_json, write_json

CONFIG_NAME = "config.json"
REPORT_TIMEOUT_SEC = 3.0
_SERVER_RE = re.compile(r"^(https://[A-Za-z0-9.-]+(:\d+)?|http://(127\.0\.0\.1|localhost):\d+)$")
_LOCAL = ("http://127.0.0.1:", "http://localhost:")


class RemoteError(Exception):
    """서버에 닿지 못함(연결 거부·시간 초과·주소 오류)."""


def normalize_server(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if not _SERVER_RE.match(url):
        raise StepError("서버 주소는 https:// 로 시작해야 합니다(예: https://video-library.up.railway.app)")
    return url


def load_config(home) -> dict:
    try:
        data = read_json(Path(home) / CONFIG_NAME)
        server = normalize_server(data["server"])
        token = data["token"]
    except (ValueError, OSError, KeyError, TypeError, AttributeError, StepError):
        return {}
    if not isinstance(token, str) or not token:
        return {}
    return {"server": server, "token": token}


def save_config(home, server: str, token: str) -> Path:
    path = Path(home) / CONFIG_NAME
    write_json(path, {"server": normalize_server(server), "token": token})
    try:
        os.chmod(path, 0o600)  # Mac·Linux: 본인만 읽기. Windows 는 무시된다
    except OSError:
        pass
    return path


def _opener(url: str):
    if url.startswith(_LOCAL):
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 시험용 서버는 프록시를 거치지 않는다
    return urllib.request.build_opener()


def request(method: str, url: str, token: str, body=None, timeout: float = 30.0) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "video-library"})
    try:
        with _opener(url).open(req, timeout=timeout) as resp:
            return resp.status, _json_or_empty(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, _json_or_empty(exc.read())
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise RemoteError(str(getattr(exc, "reason", exc))) from exc


def _json_or_empty(raw: bytes) -> dict:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def report_job(home, job: dict, timeout: float = REPORT_TIMEOUT_SEC) -> bool:
    """진행 상황을 Railway 에도 알린다. 설정이 없거나 실패하면 조용히 넘어간다(처리는 계속)."""
    cfg = load_config(home)
    if not cfg:
        return False
    try:
        status, _ = request("POST", f"{cfg['server']}/api/jobs/{job['job_id']}", cfg["token"], job, timeout)
    except (RemoteError, KeyError, TypeError):
        return False
    return status == 200
```

`PKG/jobs.py`: import에 `from .remote import report_job` 추가하고, 기록 함수 4개(`start_job`, `set_step`, `finish_job`, `abandon_job`)에서 `write_json(job_path(...), job)` 바로 다음 줄에 `report_job(home, job)`을 넣는다. 예(`set_step`):

```python
    job["updated_at"] = (now or now_kst()).isoformat(timespec="seconds")
    write_json(job_path(home, job_id), job)
    report_job(home, job)
    return job
```

(`abandon_job`은 이미 `done`이면 일찍 돌아가는 줄은 그대로 — 보고하지 않는다.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -W error -q plugin/video-library/skills/video-library/tests`
Expected: PASS (전부 — 기존 jobs 테스트는 `config.json`이 없어 보고하지 않는다)

- [ ] **Step 5: Commit**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/remote.py plugin/video-library/skills/video-library/scripts/video_library/jobs.py plugin/video-library/skills/video-library/tests/conftest.py plugin/video-library/skills/video-library/tests/test_remote.py
git commit -m "feat(stage4): railway config, requests and best-effort job reports; block internet in tests" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: `vl.py upload` + 업로드 단계가 있는 작업 흐름

**Files:**
- Create: `PKG/upload.py`
- Modify: `PKG/jobs.py` (`finish_job`, `pending_upload_job`), `PKG/fetch.py` (`upload` 인자·`--no-upload`)
- Test: `TESTS/test_upload.py`, `TESTS/test_fetch.py`(기대값 수정·추가), `TESTS/test_jobs.py`(추가)

**Interfaces:**
- Consumes: Task 5 `load_config`, `request`, `RemoteError`, `save_config`; Task 3·1 서버(`LibraryServer(auth=)`, `HostedStore`)는 통합 테스트에서만.
- Produces:
  - `jobs.finish_job(...)` — 업로드 단계가 `pending`이면 `status`는 `running`, `detail`은 `"업로드 대기"`
  - `jobs.pending_upload_job(home, video_id) -> str | None` — 업로드가 `pending`·`running`·`failed`인 가장 최근 작업
  - `fetch.fetch(url, home, lang=None, translate_en=False, upload=True, ydl_factory=None, now=None)` — 결과에 `"upload": bool`(설정이 있고 `upload`가 참일 때만 True)
  - `upload.upload(home, video_id, cfg) -> dict` `{"uploaded": True, "id", "public", "url"}`
  - `upload.main(argv)` — `vl.py upload --video <ID>`

- [ ] **Step 1: Write the failing test**

`TESTS/test_jobs.py` 끝에 추가:

```python
def test_finish_job_waits_for_upload(home):
    job = jobs.start_job(home, "AbCdEfGhIjK", "깃 기초", jobs.initial_steps(False, True))
    waiting = jobs.finish_job(home, job["job_id"], {"glossary": "done"})
    assert waiting["status"] == "running" and waiting["detail"] == "업로드 대기"
    assert jobs.pending_upload_job(home, "AbCdEfGhIjK") == job["job_id"]
    done = jobs.finish_job(home, job["job_id"], {"upload": "done"})
    assert done["status"] == "done" and done["steps"]["upload"] == "done"
    assert jobs.pending_upload_job(home, "AbCdEfGhIjK") is None
```

`TESTS/test_fetch.py`: `test_fetch_creates_work_folder_and_job`의 `out == {...}` 기대값 끝에 `"upload": False`를 추가하고, 파일 끝에 추가:

```python
def test_upload_step_pending_only_with_config(home):
    from video_library import remote
    remote.save_config(home, "https://video-library.up.railway.app", "tok")
    out = fetch_mod.fetch(URL, home, ydl_factory=factory(info()), now=NOW, upload=False)
    assert out["upload"] is False
    out = fetch_mod.fetch(URL, home, ydl_factory=factory(info()), now=NOW)
    assert out["upload"] is True
    assert read_json(home / "jobs" / f"{out['job_id']}.json")["steps"]["upload"] == "pending"
```

(이 테스트의 `fetch`는 `config.json`이 있어 진행 보고를 시도하지만, 가드가 `video-library.up.railway.app` 연결을 막아 `report_job`이 조용히 False를 돌려준다 — 처리에는 영향 없음.)

`TESTS/test_upload.py`:

```python
import json
import threading

import pytest

from conftest import VIDEO_ID
from test_library import make_doc, stage
from test_server import make_web
from video_library import auth, jobs, library, remote, upload
from video_library.config import StepError
from video_library.server import LibraryServer
from video_library.store_hosted import HostedStore

TOKEN = "test-upload-token"


@pytest.fixture
def railway(tmp_path):
    a = auth.Auth(auth.hash_password("pw-for-tests", iterations=1000), auth.hash_token(TOKEN))
    data = tmp_path / "railway-data"
    server = LibraryServer(("127.0.0.1", 0), HostedStore(data), make_web(data), auth=a)
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    yield server
    server.shutdown()
    server.server_close()


def committed(home):
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)


def test_upload_without_config_skips(home, capsys):
    committed(home)
    job = jobs.start_job(home, VIDEO_ID, "깃 기초", jobs.initial_steps(False, True))
    assert upload.main(["--video", VIDEO_ID]) == 0
    assert json.loads(capsys.readouterr().out)["uploaded"] is False
    saved = jobs.load_job(home, job["job_id"])
    assert saved["steps"]["upload"] == "skipped" and saved["status"] == "done"


def test_upload_to_railway(home, railway, capsys):
    committed(home)
    url = f"http://127.0.0.1:{railway.port}"
    remote.save_config(home, url, TOKEN)
    job = jobs.start_job(home, VIDEO_ID, "깃 기초", jobs.initial_steps(False, True))
    jobs.finish_job(home, job["job_id"], {})
    assert upload.main(["--video", VIDEO_ID]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"uploaded": True, "id": VIDEO_ID, "public": False, "url": f"{url}/lecture?id={VIDEO_ID}"}
    assert railway.store.get_lecture(VIDEO_ID)["lecture"]["id"] == VIDEO_ID
    saved = jobs.load_job(home, job["job_id"])
    assert saved["status"] == "done" and saved["steps"]["upload"] == "done"
    assert TOKEN not in json.dumps(out)


def test_wrong_token_fails_but_keeps_pc_copy(home, railway):
    committed(home)
    remote.save_config(home, f"http://127.0.0.1:{railway.port}", "wrong-token")
    job = jobs.start_job(home, VIDEO_ID, "깃 기초", jobs.initial_steps(False, True))
    with pytest.raises(StepError, match="업로드 실패\\(401\\)"):
        upload.main(["--video", VIDEO_ID])
    assert jobs.load_job(home, job["job_id"])["steps"]["upload"] == "failed"
    assert (home / "lectures" / VIDEO_ID / "lecture.json").exists()


def test_server_down_explains_retry(home):
    committed(home)
    remote.save_config(home, "http://127.0.0.1:9", TOKEN)  # 아무도 듣지 않는 포트
    with pytest.raises(StepError, match="다시 올리세요"):
        upload.main(["--video", VIDEO_ID])


def test_missing_lecture(home, railway):
    remote.save_config(home, f"http://127.0.0.1:{railway.port}", TOKEN)
    with pytest.raises(StepError, match="영상자료실에 이 강의가 없습니다"):
        upload.main(["--video", VIDEO_ID])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -W error -q plugin/video-library/skills/video-library/tests/test_upload.py plugin/video-library/skills/video-library/tests/test_jobs.py plugin/video-library/skills/video-library/tests/test_fetch.py`
Expected: FAIL — `ImportError: cannot import name 'upload'`, `AttributeError: ... 'pending_upload_job'`, fetch 결과에 `upload` 없음

- [ ] **Step 3: Write minimal implementation**

`PKG/jobs.py` — `finish_job`의 상태 줄을 바꾸고 함수 하나를 더한다:

```python
def finish_job(home: Path, job_id: str, outcome: dict[str, str], now=None) -> dict:
    job = load_job(home, job_id)
    for step, status in outcome.items():
        if job["steps"].get(step) in ("pending", "running"):
            job["steps"][step] = status
    waiting = job["steps"].get("upload") == "pending"  # 조립은 끝났고 업로드만 남음
    job["status"] = "running" if waiting else "done"
    job["error"] = None
    job["detail"] = "업로드 대기" if waiting else ""
    job["updated_at"] = (now or now_kst()).isoformat(timespec="seconds")
    write_json(job_path(home, job_id), job)
    report_job(home, job)
    return job


def pending_upload_job(home: Path, video_id: str) -> str | None:
    """업로드가 아직 끝나지 않은 이 영상의 가장 최근 작업(조립 뒤에는 작업 폴더가 없어 jobs/ 에서 찾는다)."""
    best = None
    for path in (Path(home) / "jobs").glob(f"{video_id}-*.json"):
        try:
            job = read_json(path)
        except (ValueError, OSError):
            continue
        if not isinstance(job, dict) or job.get("lecture_id") != video_id:
            continue
        if (job.get("steps") or {}).get("upload") not in ("pending", "running", "failed"):
            continue
        if best is None or str(job.get("updated_at", "")) > str(best.get("updated_at", "")):
            best = job
    return best["job_id"] if best else None
```

`PKG/fetch.py` — import에 `from .remote import load_config`, 시그니처·작업 시작·결과·`main`:

```python
def fetch(url: str, home, lang: str | None = None, translate_en: bool = False, upload: bool = True,
          ydl_factory=None, now=None) -> dict:
```

```python
    translate_needed = meta["language"] != "ko" or translate_en
    upload_enabled = upload and bool(load_config(home))
    job = start_job(home, video_id, meta["title"], initial_steps(translate_needed, upload_enabled), now=now)
```

```python
            "long": meta["duration"] > LONG_VIDEO_SEC, "translate": translate_needed, "upload": upload_enabled}
```

```python
    ap.add_argument("--no-upload", action="store_true", help="Railway 업로드 설정이 있어도 이번에는 올리지 않음")
    a = ap.parse_args(argv)
    result = fetch(a.url, library_home(), lang=a.lang, translate_en=a.translate_en, upload=not a.no_upload,
                   ydl_factory=_default_ydl_factory)
```

`PKG/upload.py`:

```python
"""영상자료실의 강의(lecture.json)를 내 Railway 서버로 올린다. 설정(config.json)이 없으면 건너뛴다."""
from __future__ import annotations

import argparse
import json

from .config import StepError, lecture_dir, library_home, read_json, video_id_arg
from .jobs import best_effort, finish_job, pending_upload_job, set_step
from .remote import RemoteError, load_config, request

UPLOAD_TIMEOUT_SEC = 60.0


def upload(home, video_id: str, cfg: dict) -> dict:
    path = lecture_dir(home, video_id) / "lecture.json"
    if not path.exists():
        raise StepError(f"영상자료실에 이 강의가 없습니다: {video_id}")
    doc = read_json(path)
    try:
        status, body = request("PUT", f"{cfg['server']}/api/lectures/{video_id}", cfg["token"], doc,
                               timeout=UPLOAD_TIMEOUT_SEC)
    except RemoteError as exc:
        raise StepError(f"Railway 서버에 연결하지 못했습니다({exc}). PC 결과는 그대로 있습니다 — "
                        f"나중에 'vl.py upload --video {video_id}' 로 다시 올리세요.") from exc
    if status != 200:
        raise StepError(f"업로드 실패({status}): {body.get('error', '')} — PC 결과는 그대로 있습니다.")
    return {"uploaded": True, "id": video_id, "public": bool(body.get("public")),
            "url": f"{cfg['server']}/lecture?id={video_id}"}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py upload", description="강의를 내 Railway 서버로 올린다(새 강의는 비공개).")
    ap.add_argument("--video", required=True, type=video_id_arg, help="영상 ID")
    a = ap.parse_args(argv)
    home = library_home()
    job_id = pending_upload_job(home, a.video)
    cfg = load_config(home)
    if not cfg:
        if job_id:
            best_effort(finish_job, home, job_id, {"upload": "skipped"})
        print(json.dumps({"uploaded": False, "reason": "업로드 설정이 없습니다(선택 기능) — 건너뜀"}, ensure_ascii=False))
        return 0
    if job_id:
        best_effort(set_step, home, job_id, "upload", "running")
    try:
        result = upload(home, a.video, cfg)
    except StepError as exc:
        if job_id:
            best_effort(set_step, home, job_id, "upload", "failed", error=str(exc)[:300])
        raise
    if job_id:
        best_effort(finish_job, home, job_id, {"upload": "done"})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -W error -q plugin/video-library/skills/video-library/tests`
Expected: PASS (전부)

- [ ] **Step 5: Commit**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/upload.py plugin/video-library/skills/video-library/scripts/video_library/jobs.py plugin/video-library/skills/video-library/scripts/video_library/fetch.py plugin/video-library/skills/video-library/tests/test_upload.py plugin/video-library/skills/video-library/tests/test_jobs.py plugin/video-library/skills/video-library/tests/test_fetch.py
git commit -m "feat(stage4): vl.py upload and upload-aware job flow (--no-upload)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: `vl.py connect` — 사용자 터미널에서 Railway 연결

**Files:**
- Create: `PKG/connect.py`
- Test: `TESTS/test_connect.py`

**Interfaces:**
- Consumes: Task 2 `hash_password`, `hash_token`, `verify_password`; Task 5 `normalize_server`, `save_config`, `load_config`.
- Produces:
  - `MIN_PASSWORD = 10`, `SECRET_VARS = ("VL_ADMIN_PASSWORD_HASH", "VL_UPLOAD_TOKEN_HASH")`
  - `connect(home, server_url, service=None, ask=getpass.getpass, run=subprocess.run, railway=None) -> dict` `{"server", "config"}` — 비밀번호 두 번 숨김 입력, 토큰 생성, `railway variable set <KEY> --stdin [--service S] [--skip-deploys]`(첫 변수만 `--skip-deploys`, 마지막 변수가 재배포), 성공 뒤 `config.json` 저장
  - `main(argv)` — `vl.py connect <주소> [--service 이름]`, 터미널(tty)이 아니면 거부

- [ ] **Step 1: Write the failing test**

`TESTS/test_connect.py`:

```python
import subprocess

import pytest

from video_library import auth, connect, remote
from video_library.config import StepError

PW = "시험용-비밀번호-1234"
URL = "https://video-library.up.railway.app"


class Runner:
    def __init__(self, code=0):
        self.code = code
        self.calls = []

    def __call__(self, cmd, input=None, text=None, capture_output=None, **kw):
        self.calls.append((cmd, input))
        return subprocess.CompletedProcess(cmd, self.code, stdout="", stderr="railway 오류" if self.code else "")


def asker(*answers):
    it = iter(answers)
    return lambda prompt="": next(it)


def test_connect_sets_hashes_by_stdin_and_saves_config(home, capsys):
    run = Runner()
    out = connect.connect(home, URL + "/", service="video-library", ask=asker(PW, PW), run=run, railway="railway")
    assert out == {"server": URL, "config": str(home / "config.json")}
    cfg = remote.load_config(home)
    assert cfg["server"] == URL and len(cfg["token"]) >= 40
    (cmd1, in1), (cmd2, in2) = run.calls
    assert cmd1 == ["railway", "variable", "set", "VL_ADMIN_PASSWORD_HASH", "--stdin", "--service", "video-library", "--skip-deploys"]
    assert cmd2 == ["railway", "variable", "set", "VL_UPLOAD_TOKEN_HASH", "--stdin", "--service", "video-library"]
    assert auth.verify_password(PW, in1) and in2 == auth.hash_token(cfg["token"])
    joined = " ".join(" ".join(c) for c, _ in run.calls) + capsys.readouterr().out
    assert PW not in joined and cfg["token"] not in joined  # 비밀 값은 명령줄·출력 어디에도 없다


@pytest.mark.parametrize("answers, message", [
    ((PW, PW + "x"), "서로 다릅니다"),
    (("short", "short"), "10자"),
])
def test_bad_passwords(home, answers, message):
    run = Runner()
    with pytest.raises(StepError, match=message):
        connect.connect(home, URL, ask=asker(*answers), run=run, railway="railway")
    assert run.calls == [] and remote.load_config(home) == {}


def test_railway_failure_keeps_old_config(home):
    remote.save_config(home, URL, "old-token")
    with pytest.raises(StepError, match="Railway 변수"):
        connect.connect(home, URL, ask=asker(PW, PW), run=Runner(code=1), railway="railway")
    assert remote.load_config(home)["token"] == "old-token"


def test_bad_url(home):
    with pytest.raises(StepError, match="https://"):
        connect.connect(home, "http://example.com", ask=asker(PW, PW), run=Runner(), railway="railway")


def test_main_refuses_without_terminal(home, monkeypatch):
    monkeypatch.setattr(connect.sys.stdin, "isatty", lambda: False, raising=False)
    with pytest.raises(StepError, match="직접"):
        connect.main([URL])


def test_missing_railway_cli(home, monkeypatch):
    monkeypatch.setattr(connect.shutil, "which", lambda name: None)
    with pytest.raises(StepError, match="Railway CLI"):
        connect.connect(home, URL, ask=asker(PW, PW), run=Runner())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -W error -q plugin/video-library/skills/video-library/tests/test_connect.py`
Expected: FAIL — `ImportError: cannot import name 'connect'`

- [ ] **Step 3: Write minimal implementation**

`PKG/connect.py`:

```python
"""Railway 연결(사용자가 자기 터미널에서 직접 실행). 비밀번호는 보이지 않게 입력받고, 토큰은 무작위로 만든다.
Railway 에는 해시만 표준 입력으로 넘기고, 토큰은 내 PC 의 config.json 에만 둔다. 화면에는 비밀 값을 출력하지 않는다."""
from __future__ import annotations

import argparse
import getpass
import json
import secrets
import shutil
import subprocess
import sys

from .auth import hash_password, hash_token
from .config import StepError, ensure_home, library_home
from .remote import CONFIG_NAME, normalize_server, save_config

MIN_PASSWORD = 10
SECRET_VARS = ("VL_ADMIN_PASSWORD_HASH", "VL_UPLOAD_TOKEN_HASH")


def connect(home, server_url: str, service: str | None = None, ask=getpass.getpass, run=subprocess.run,
            railway: str | None = None) -> dict:
    server = normalize_server(server_url)
    railway = railway or shutil.which("railway")
    if not railway:
        raise StepError("Railway CLI 가 없습니다. https://docs.railway.com/cli 에서 설치하고 'railway login' 후 다시 실행하세요.")
    first = ask("Railway 관리자 비밀번호(10자 이상, 화면에 보이지 않음): ")
    second = ask("한 번 더 입력: ")
    if first != second:
        raise StepError("두 비밀번호가 서로 다릅니다. 다시 실행하세요.")
    if len(first) < MIN_PASSWORD:
        raise StepError(f"비밀번호는 {MIN_PASSWORD}자 이상이어야 합니다.")
    token = secrets.token_urlsafe(32)
    values = {SECRET_VARS[0]: hash_password(first), SECRET_VARS[1]: hash_token(token)}
    for i, (key, value) in enumerate(values.items()):
        cmd = [railway, "variable", "set", key, "--stdin"]
        if service:
            cmd += ["--service", service]
        if i < len(values) - 1:
            cmd.append("--skip-deploys")  # 마지막 변수를 넣을 때 한 번만 다시 배포
        proc = run(cmd, input=value, text=True, capture_output=True)
        if proc.returncode != 0:
            raise StepError(f"Railway 변수 {key} 를 넣지 못했습니다. 이 폴더가 'railway link' 로 프로젝트에 "
                            f"연결됐는지 확인하세요. ({(proc.stderr or '').strip()[:300]})")
    path = save_config(ensure_home(home), server, token)
    return {"server": server, "config": str(path)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py connect",
                                 description="내 Railway 서버와 연결한다(사용자가 자기 터미널에서 직접 실행).")
    ap.add_argument("server", help="Railway 서버 주소(예: https://video-library.up.railway.app)")
    ap.add_argument("--service", default=None, help="Railway 서비스 이름")
    a = ap.parse_args(argv)
    if not sys.stdin.isatty():
        raise StepError("이 명령은 비밀번호를 입력받으므로 사용자가 자기 터미널에서 직접 실행해야 합니다.")
    result = connect(library_home(), a.server, service=a.service)
    print(json.dumps(result, ensure_ascii=False))
    print(f"연결 완료: 서버 주소와 업로드 토큰을 {CONFIG_NAME} 에 저장했습니다(토큰은 화면에 표시하지 않음). "
          "Railway 가 새 설정으로 다시 배포됩니다(1~2분).")
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -W error -q plugin/video-library/skills/video-library/tests/test_connect.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugin/video-library/skills/video-library/scripts/video_library/connect.py plugin/video-library/skills/video-library/tests/test_connect.py
git commit -m "feat(stage4): vl.py connect sets railway secret hashes via stdin" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: 화면 — 관리자 로그인·[공개/비공개]·[삭제], 호스팅 화면 정리

**Files:**
- Modify: `WEB/common.js`, `WEB/library.html`, `WEB/library.js`, `WEB/lecture.js`, `WEB/app.css`
- Test: `TESTS/test_web_assets.py` (추가)

**Interfaces:**
- Consumes: Task 3·4 API(`/api/health`의 `mode`·`admin`, 로그인·로그아웃, `PATCH`·`DELETE`, 목록의 `public`).
- Produces (common.js `VL`):
  - `VL.info() -> Promise<{app, mode, admin?}>` — `/api/health`를 한 번만 부름(실패하면 `{mode: "pc"}`)
  - `VL.send(method, path, body) -> Promise<object>` — JSON 본문 + `X-Requested-With: video-library`, 오류면 `Error(message)`(`.status` 포함)

- [ ] **Step 1: Write the failing test**

`TESTS/test_web_assets.py` 끝에 추가:

```python
def test_hosted_admin_ui():
    common, lib, lec, page = read("common.js"), read("library.js"), read("lecture.js"), read("library.html")
    assert '"X-Requested-With": "video-library"' in common and "function info(" in common and "function send(" in common
    for needle in ('"/api/login"', '"/api/logout"', '"PATCH"', '"DELETE"', "confirm(", "아직 공개된 강의가 없습니다."):
        assert needle in lib, needle
    assert 'type="password"' in page and 'autocomplete="current-password"' in page
    assert "hosted" in lec and '$("#ask").hidden' in lec
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -W error -q plugin/video-library/skills/video-library/tests/test_web_assets.py`
Expected: FAIL — `assert '"X-Requested-With": "video-library"' in common`

- [ ] **Step 3: Write minimal implementation**

`WEB/common.js` — `api` 함수 아래에 추가하고 `return`에 `info, send`를 더한다:

```javascript
  let infoPromise = null;
  function info() {
    if (!infoPromise) infoPromise = api("/api/health").catch(() => ({ mode: "pc" }));
    return infoPromise;
  }

  async function send(method, path, body) {
    let resp;
    try {
      resp = await fetch(path, {
        method, cache: "no-store",
        headers: { "Content-Type": "application/json", "X-Requested-With": "video-library" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch (e) {
      serverStatus(false);
      throw new Error("서버에 연결하지 못했습니다");
    }
    serverStatus(true);
    let data = {};
    try { data = await resp.json(); } catch (e) { /* 본문 없음 */ }
    if (!resp.ok) {
      const err = new Error(data.error || resp.statusText);
      err.status = resp.status;
      throw err;
    }
    return data;
  }
```

```javascript
  return { FIELD_LABELS, api, info, send, watchServer, fmtTime, fmtDate, fmtElapsed, el, highlight, toast, copy, langPair };
```

`WEB/library.html` — 머리(`<header class="topbar">`) 안, 검색창 뒤에 추가:

```html
  <button id="admin-btn" class="btn small ghost" type="button" hidden>관리자</button>
  <form id="login" class="login" hidden>
    <input id="password" type="password" autocomplete="current-password" placeholder="관리자 비밀번호" aria-label="관리자 비밀번호" required>
    <button class="btn small" type="submit">로그인</button>
  </form>
```

`WEB/library.js`:
1. `state`에 `hosted: false, admin: false`를 더한다:

```javascript
  const state = { lectures: [], field: "", query: "", dismissed: loadDismissed(), running: new Set(), hosted: false, admin: false };
```

2. `lectureCard`의 마지막 `VL.el("a", { href, class: \`pebble view …\` }, "보기")` 앞에 관리자 버튼을 넣는다 — 함수 끝부분을 다음으로 바꾼다:

```javascript
      VL.el("div", { class: "card-actions" },
        state.admin ? adminButtons(item) : null,
        VL.el("a", { href, class: `pebble view field-${VL.FIELD_LABELS[item.field] ? item.field : "other"}` }, "보기")));
  }

  function adminButtons(item) {
    return [
      VL.el("button", { type: "button", class: "btn small" + (item.public ? " public-on" : ""),
        "aria-pressed": String(!!item.public),
        onclick: () => togglePublic(item) }, item.public ? "공개 중" : "비공개"),
      VL.el("button", { type: "button", class: "btn small ghost danger", onclick: () => removeLecture(item) }, "삭제"),
    ];
  }

  async function togglePublic(item) {
    try {
      await VL.send("PATCH", `/api/lectures/${encodeURIComponent(item.id)}`, { public: !item.public });
      VL.toast(item.public ? "비공개로 바꿨습니다." : "공개했습니다. 로그인하지 않은 사람도 볼 수 있습니다.");
      loadLectures();
    } catch (e) { VL.toast("바꾸지 못했습니다: " + e.message); }
  }

  async function removeLecture(item) {
    if (!confirm(`「${item.title}」을(를) Railway 서버에서 삭제할까요? 내 PC 영상자료실의 원본은 그대로 남습니다.`)) return;
    try {
      await VL.send("DELETE", `/api/lectures/${encodeURIComponent(item.id)}`);
      VL.toast("삭제했습니다.");
      loadLectures();
    } catch (e) { VL.toast("삭제하지 못했습니다: " + e.message); }
  }
```

(원래 `lectureCard`의 마지막 줄 `VL.el("a", { href, class: … }, "보기"));`는 위 `card-actions` 묶음으로 대체된다.)

3. `pollJobs`의 첫 줄에 호스팅 손님이면 건너뛰기:

```javascript
  async function pollJobs() {
    if (state.hosted && !state.admin) return;
```

4. 파일 끝의 시작 코드(`renderFilters(); … $("#search").addEventListener(…)`)를 다음으로 바꾼다:

```javascript
  function setupAdmin() {
    const btn = $("#admin-btn");
    btn.hidden = false;
    btn.textContent = state.admin ? "로그아웃" : "관리자";
    btn.addEventListener("click", async () => {
      if (!state.admin) { $("#login").hidden = !$("#login").hidden; $("#password").focus(); return; }
      try { await VL.send("POST", "/api/logout"); } catch (e) { /* 이미 끝난 세션 */ }
      location.reload();
    });
    $("#login").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        await VL.send("POST", "/api/login", { password: $("#password").value });
        location.reload();
      } catch (e) {
        $("#password").value = "";
        VL.toast(e.status === 429 ? "로그인 시도가 너무 많습니다. 15분 뒤 다시 시도하세요." : "로그인하지 못했습니다: " + e.message);
      }
    });
    if (!state.admin) $("#empty").textContent = "아직 공개된 강의가 없습니다.";
  }

  async function start() {
    const info = await VL.info();
    state.hosted = info.mode === "hosted";
    state.admin = !!info.admin;
    if (state.hosted) setupAdmin();
    renderFilters();
    loadLectures();
    pollJobs();
    setInterval(pollJobs, 2000);
    VL.watchServer();
    $("#search").addEventListener("input", onSearchInput);
  }

  start();
```

`WEB/lecture.js` — `setupButtons`를 다음으로 바꾼다(호스팅 손님에게는 AI 도구용 버튼을 숨김):

```javascript
  async function setupButtons() {
    $("#copy-plain").addEventListener("click", () => copyTranscript(false));
    $("#copy-timed").addEventListener("click", () => copyTranscript(true));
    $("#ask").addEventListener("click", () =>
      VL.copy(`video-library 강의 「${doc.lecture.title}」(${lectureId})에 대해 질문: `, ASK_MESSAGE));
    const needsEnglish = doc.lecture.language === "ko" && !doc.translations.en;
    $("#request-en").hidden = !needsEnglish;
    $("#request-en").addEventListener("click", () => VL.copy(`/video-library 번역 ${lectureId}`, REQUEST_MESSAGE));
    const info = await VL.info();
    const visitor = info.mode === "hosted" && !info.admin; // 공개 서버 손님: AI 도구용 버튼은 의미가 없다
    if (visitor) {
      $("#ask").hidden = true;
      $("#request-en").hidden = true;
    }
  }
```

`WEB/app.css` — 끝에 추가:

```css
/* Railway 관리자 */
.login { display: flex; gap: 6px; align-items: center; }
.login input { width: 160px; padding: 6px 10px; border: 1px solid var(--line); border-radius: 8px;
  background: var(--surface-2); color: var(--text); font: inherit; }
.card-actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; justify-content: flex-end; }
.btn.public-on { border-color: var(--ok); color: var(--ok); background: var(--ok-soft); }
.btn.danger { color: var(--bad); }
```

`.card` 그리드의 마지막 칸이 `auto`라 `card-actions`가 그 칸을 차지한다. 좁은 화면(`@media (max-width: 640px)`)에서는 `.card-actions { justify-content: flex-start; }`를 그 미디어 쿼리 안에 추가한다.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -W error -q plugin/video-library/skills/video-library/tests/test_web_assets.py`
Expected: PASS (`node --check`·요소 id 검사 포함)

- [ ] **Step 5: Commit**

```bash
git add plugin/video-library/skills/video-library/web plugin/video-library/skills/video-library/tests/test_web_assets.py
git commit -m "feat(stage4): admin login, publish toggle and delete on the hosted list page" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: 명령 등록 + `SKILL.md` 12단계·Railway 연결 + API 문서

**Files:**
- Modify: `SKILL_DIR/scripts/vl.py` (`COMMANDS`), `SKILL_DIR/SKILL.md`, `docs/api.md`
- Test: `TESTS/test_skill_doc.py` (추가). 기존 `test_every_command_is_documented`가 새 명령의 문서화를 강제한다.

**Interfaces:**
- Consumes: Task 6 `vl.py upload`, Task 7 `vl.py connect`, Task 6 fetch 출력 `upload`.
- Produces: `vl.py upload`, `vl.py connect` 명령. SKILL.md 12단계·`## 나중 요청: Railway 연결(선택)`·`## 나중 요청: 업로드`.

- [ ] **Step 1: Write the failing test**

`TESTS/test_skill_doc.py` 끝에 추가:

```python
def test_upload_and_connect_documented():
    body = text()
    assert "12. **업로드**" in body and "vl.py upload --video <ID>" in body and "--no-upload" in body
    section = body.split("## 나중 요청: Railway 연결(선택)", 1)[1].split("\n## ", 1)[0]
    assert "vl.py connect" in section and "직접" in section
    assert "대신 실행하지 않는다" in section
```

그리고 `vl.py`에 명령을 등록한다(이 시점에 `test_every_command_is_documented`가 실패해야 정상):

```python
    "upload": ("video_library.upload", "강의를 내 Railway 서버로 올리기(설정이 있을 때만)"),
    "connect": ("video_library.connect", "내 Railway 서버와 연결(사용자가 자기 터미널에서 직접 실행)"),
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -W error -q plugin/video-library/skills/video-library/tests/test_skill_doc.py`
Expected: FAIL — `test_upload_and_connect_documented`, `test_every_command_is_documented`(upload·connect 없음)

- [ ] **Step 3: Write minimal implementation**

`SKILL.md`:

1. `## 규칙`의 옵션 줄을 바꾼다:

```markdown
- 옵션: `--translate-en`(한국어 영상의 전사를 영어로도 번역), `--lang xx`(영상 언어를 직접 지정), `--no-upload`(Railway 업로드 설정이 있어도 이번에는 올리지 않음).
```

2. 1단계 줄을 바꾼다:

```markdown
1. **자막 받기** — `vl.py fetch "<링크>" [--translate-en] [--lang xx] [--no-upload]`. 출력 JSON의 `video_id`, `work_dir`, `language`, `translate`, `long`, `upload`을 기억한다. `long`이 true(1시간 초과)면 처리 시간이 길고 구독 사용량이 많이 든다는 점을 알리고 계속할지 묻는다.
```

3. 11단계 다음 줄에 12단계를 더한다:

```markdown
12. **업로드** — fetch 출력의 `upload`가 true일 때만 `vl.py upload --video <ID>`. 성공하면 출력의 `url`을 알려 주고, **새 강의는 비공개**라 남에게 보이려면 Railway 화면에서 관리자로 로그인해 [비공개]를 눌러 공개로 바꿔야 한다고 안내한다. 실패해도 PC 영상자료실의 결과는 그대로이며, 원인을 고친 뒤 같은 명령으로 다시 올릴 수 있다고 안내한다.
```

4. `## 나중 요청: 한국어 강의 영어 번역` 앞에 두 절을 더한다:

```markdown
## 나중 요청: 업로드
사용자가 `/video-library 업로드 <ID>`(또는 "video-library 업로드 <ID>")를 요청하면 `vl.py upload --video <ID>`를 실행하고 위 12단계처럼 결과를 안내한다. 설정이 없다는 출력이면 아래 "Railway 연결"을 안내한다.

## 나중 요청: Railway 연결(선택)
내 Railway 서버로 결과를 올리고 싶다는 요청이면:
1. Railway 서버가 이미 배포돼 있어야 한다(설치 안내서 README의 Railway 절).
2. 연결은 비밀번호를 입력받으므로 **사용자가 자기 터미널에서 직접** 실행한다. AI는 `vl.py connect`를 대신 실행하지 않는다. 비밀번호·토큰을 묻거나 출력하지 않는다. 아래 명령을 실제 경로로 바꿔 보여 주기만 한다(Railway 프로젝트에 `railway link`된 폴더에서):
   `"$PY" "$SKILL/scripts/vl.py" connect <서버 주소> --service <서비스 이름>`
3. 사용자가 끝났다고 하면 `vl.py upload --video <ID>`로 올릴 수 있다고 안내한다.
```

5. `## 규칙`의 토큰 줄을 바꾼다:

```markdown
- 사용자에게 업로드 토큰·관리자 비밀번호를 묻거나 출력하지 않는다. `vl.py connect`는 사용자가 직접 실행한다. 설치 명령은 사용자 승인 후에만 실행한다.
```

`docs/api.md` 4장 — 표 아래 목록을 다음으로 바꾼다:

```markdown
- PC 미니 서버는 읽기 전용이며 `127.0.0.1`에만 열린다. GET 외 요청은 405, `Host`가 `127.0.0.1:<포트>`·`localhost:<포트>`가 아니면 403. 정적 파일은 `/`(목록)·`/lecture`(강의)·`/app/<파일>`(`영상자료실/app/` 바로 아래 `.html .css .js .svg .png .ico`)만 낸다. 포트는 8765부터 빈 번호, 실행 정보는 `영상자료실/.server.json`.
- `GET /api/health`: PC `{"app":"video-library","mode":"pc","home":…}`, Railway `{"app":"video-library","mode":"hosted","admin":true|false}`(폴더 경로는 내지 않음).
- Railway 서버(`vl.py serve --hosted`)는 볼륨 `/data`에 PC와 같은 파일 형식으로 저장하고, 공개 목록은 `/data/visibility.json` `{"public": [<ID>, …]}`에 둔다(깨지거나 없으면 아무것도 공개하지 않음). 정적 파일은 이미지에 들어 있는 `web/`에서 낸다. `Host` 검사는 하지 않는다.
- 업로드 토큰: `Authorization: Bearer <토큰>` 헤더(`PUT /api/lectures/<id>`, `POST /api/jobs/<job_id>`). 토큰은 `영상자료실/config.json`(공개 금지)에서 읽고, 서버는 `VL_UPLOAD_TOKEN_HASH`(SHA-256)와 비교한다. 틀리면 401.
- 관리자: `POST /api/login` `{"password"}` → 세션 쿠키 `vl_session`(`HttpOnly; Secure; SameSite=Strict`, 12시간). 비밀번호는 `VL_ADMIN_PASSWORD_HASH`(PBKDF2-SHA256)와 비교. 15분에 10번 실패하면 15분 잠금(429). `POST /api/login`·`/api/logout`·`PATCH`·`DELETE`는 `X-Requested-With: video-library` 헤더가 없으면 403, 로그인하지 않았으면 401.
- 본문: JSON. 업로드 최대 20MB, 그 밖 64KB. `Content-Length`가 없으면 411, 넘으면 413, JSON이 아니면 400. 업로드는 서버가 `validate_lecture`로 다시 검사하고 주소의 ID와 `lecture.id`가 같아야 한다(아니면 400). 진행 보고는 `jobs/<job_id>.json` 형식(시간대 있는 시각, 정해진 키만)이어야 한다.
- 응답: 업로드 `{"id","public"}`(새 강의 `false`, 재업로드는 기존 공개 상태 유지), 공개 전환 `{"id","public"}`, 삭제 `{"id","deleted":true}`, 진행 보고 `{"job_id"}`. 로그인하지 않은 사람에게 비공개 강의는 목록·검색에서 빠지고 단건은 404, `GET /api/jobs`는 401.
```

(기존 줄 "관리자 쓰기 요청(`PATCH`·`DELETE`·`logout`)은 … `X-Requested-With: video-library` 헤더가 필요하다."와 "업로드 본문은 …" 줄은 위 목록에 합쳐졌으므로 지운다.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -W error -q plugin/video-library/skills/video-library/tests`
Expected: PASS (전부)

- [ ] **Step 5: Commit**

```bash
git add plugin/video-library/skills/video-library/scripts/vl.py plugin/video-library/skills/video-library/SKILL.md plugin/video-library/skills/video-library/tests/test_skill_doc.py docs/api.md
git commit -m "feat(stage4): register upload/connect, document step 12 and railway connection" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Railway 배포 파일 + 내 PC에서 호스팅 모드 확인

**Files:**
- Create: `railway/Dockerfile`, `.dockerignore`
- Test: `TESTS/test_deploy_files.py`
- 증거: `docs/superpowers/evidence/2026-10-06-stage4-railway.md`(새, 이 Task에서 시작)

**Interfaces:**
- Consumes: Task 4 `vl.py serve --hosted`, Task 7 `connect`(브라우저 확인용 해시 만들기에는 쓰지 않음 — 아래 스크립트로 시험 값만), Task 6 `upload`, Task 8 화면.
- Produces: Docker 이미지 정의(`/srv/scripts`, `/srv/web`, `VL_HOME=/data`, `CMD python scripts/vl.py serve --hosted`).

- [ ] **Step 1: Write the failing test**

`TESTS/test_deploy_files.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]  # tests → video-library → skills → video-library → plugin → plugin-app


def test_dockerfile_runs_hosted_server_with_stdlib_only():
    text = (ROOT / "railway" / "Dockerfile").read_text(encoding="utf-8")
    assert text.startswith("FROM python:3.12-slim")
    assert "COPY plugin/video-library/skills/video-library/scripts ./scripts" in text
    assert "COPY plugin/video-library/skills/video-library/web ./web" in text
    assert "VL_HOME=/data" in text
    assert 'CMD ["python", "scripts/vl.py", "serve", "--hosted"]' in text
    assert "pip install" not in text  # 표준 라이브러리만
    for secret in ("VL_ADMIN_PASSWORD_HASH", "VL_UPLOAD_TOKEN_HASH", "token"):
        assert secret not in text  # 비밀 값은 Railway 변수로만


def test_dockerignore_keeps_image_small_and_clean():
    lines = (ROOT / ".dockerignore").read_text(encoding="utf-8").split()
    for pattern in ("**/__pycache__", "**/tests", "docs", ".superpowers", ".git"):
        assert pattern in lines
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -W error -q plugin/video-library/skills/video-library/tests/test_deploy_files.py`
Expected: FAIL — `FileNotFoundError: …railway/Dockerfile`

- [ ] **Step 3: Write minimal implementation**

`railway/Dockerfile`:

```dockerfile
FROM python:3.12-slim
# video-library Railway 서버: 표준 라이브러리만 쓰므로 설치할 패키지가 없다.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 VL_HOME=/data
WORKDIR /srv
COPY plugin/video-library/skills/video-library/scripts ./scripts
COPY plugin/video-library/skills/video-library/web ./web
EXPOSE 8080
CMD ["python", "scripts/vl.py", "serve", "--hosted"]
```

`.dockerignore`(plugin-app 맨 위):

```
.git
.superpowers
docs
**/__pycache__
**/*.pyc
**/tests
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -W error -q plugin/video-library/skills/video-library/tests/test_deploy_files.py`
Expected: PASS

- [ ] **Step 5: 내 PC에서 호스팅 모드 확인(시험용 폴더, 시험 값)**

시험 값(비밀번호·토큰)은 이 확인에만 쓰는 무작위 값으로, 세션 scratchpad의 파일에만 두고 채팅·Git에 쓰지 않는다. scratchpad에 `hosted_env.py`를 만들어 실행한다:

```python
import json, os, secrets, sys
from pathlib import Path
sys.path.insert(0, "plugin/video-library/skills/video-library/scripts")
from video_library.auth import hash_password, hash_token
scratch = Path(sys.argv[1])
pw, token = secrets.token_urlsafe(12), secrets.token_urlsafe(32)
(scratch / "hosted-test-secrets.json").write_text(json.dumps({"password": pw, "token": token}), encoding="utf-8")
(scratch / "hosted-test.env.json").write_text(json.dumps({
    "VL_ADMIN_PASSWORD_HASH": hash_password(pw), "VL_UPLOAD_TOKEN_HASH": hash_token(token),
    "PORT": "8790", "VL_HOME": str(scratch / "railway-data")}), encoding="utf-8")
print("시험 값 생성 완료(값은 출력하지 않음)")
```

그 다음:
1. 백그라운드로 호스팅 서버 실행: 위 env 파일의 값을 환경변수로 넣고 `python plugin/video-library/skills/video-library/scripts/vl.py serve --hosted`.
2. 시험용 PC 자료실(`VL_HOME`=scratchpad의 `pc-home`)에 3단계 시험 방식대로 샘플 강의를 넣고, `config.json`을 `http://127.0.0.1:8790` + 시험 토큰으로 저장(scratchpad 파이썬 한 줄, 값 출력 없음) → `vl.py upload --video <샘플 ID>` → `uploaded: true, public: false`.
3. 내장 브라우저로 `http://127.0.0.1:8790/` 확인, 결과를 증거 문서 표로:
   - 로그아웃 상태: 빈 안내 "아직 공개된 강의가 없습니다.", [관리자] 버튼, 진행 카드 없음, `/lecture?id=<ID>` → "강의를 불러오지 못했습니다"(404)
   - [관리자] → 시험 비밀번호로 로그인(로컬 개발 서버·시험 값) → 카드에 [비공개]·[삭제], 진행 카드 보임
   - [비공개] 클릭 → "공개 중" → 로그아웃 → 목록에 보이고 강의 화면 재생·검색 동작, [이 강의에 질문하기]·[영어 번역 요청] 숨김
   - [삭제] 확인 창 → 사라짐(PC 원본은 그대로)
   - 콘솔 오류(CSP 포함) 없음, 좁은 화면 확인
4. 서버를 끄고 scratchpad 시험 파일은 그대로 둔다(세션 전용 폴더).

Expected: 위 항목 모두 ✓. Secure 쿠키는 `http://127.0.0.1`에서도 Chrome 계열이 저장한다 — 로그인이 유지되지 않으면 원인을 증거에 적고, Railway(HTTPS)에서 다시 확인한다.

- [ ] **Step 6: Commit**

```bash
git add railway/Dockerfile .dockerignore plugin/video-library/skills/video-library/tests/test_deploy_files.py docs/superpowers/evidence/2026-10-06-stage4-railway.md
git commit -m "feat(stage4): railway Dockerfile; local hosted-mode check recorded" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Railway 배포와 공개 확인 (단계마다 사용자 승인)

**Files:**
- Modify: `docs/superpowers/evidence/2026-10-06-stage4-railway.md`, `docs/handoff.md`

**Interfaces:**
- Consumes: Task 10 이미지, Task 7 `connect`(사용자), Task 6 `upload`, Task 8 화면.

각 번호 앞에서 **무엇을 실행하는지·비용 영향**을 사용자에게 말하고 승인을 받는다. 명령 형식이 CLI 도움말과 다르면 `railway <명령> --help`로 확인해 맞추고 증거에 적는다. 출력에 비밀 값이 나오는 명령(`variable list --kv` 등)은 쓰지 않는다.

- [ ] **Step 1 (승인):** 새 Railway 프로젝트 `video-library` 만들기 + 이 폴더 연결 — `railway init --name video-library` (plugin-app에서). 기존 `aistra-news` 프로젝트에 넣을지 사용자가 다르게 원하면 그쪽으로.
- [ ] **Step 2 (승인):** 서비스·볼륨·도메인 — `railway add --service video-library`, `railway volume add --mount-path /data`(서비스 선택), `railway variable set RAILWAY_DOCKERFILE_PATH=railway/Dockerfile --service video-library --skip-deploys`, `railway domain --service video-library` → 공개 주소(`https://…up.railway.app`) 기록.
- [ ] **Step 3 (사용자 직접):** 사용자가 자기 터미널에서, plugin-app 폴더에서:

```bash
python plugin/video-library/skills/video-library/scripts/vl.py connect https://<공개 주소> --service video-library
```

  (AI는 이 명령을 보여 주기만 한다. 비밀번호는 사용자만 안다.)
- [ ] **Step 4 (승인):** 배포 — `railway up --service video-library --detach` → `railway logs --service video-library`로 "video-library Railway 서버: 포트" 확인 → `https://<주소>/api/health` = `{"app":"video-library","mode":"hosted","admin":false}`.
- [ ] **Step 5 (승인):** 데모 강의 업로드 — `vl.py upload --video 40JNj2zjnQc` → `uploaded: true, public: false`. 다른 3편(남의 영상)은 올리지 않는다.
- [ ] **Step 6 (사용자):** 사용자가 공개 주소에서 [관리자] 로그인 → 데모 강의 [비공개] → "공개 중".
- [ ] **Step 7:** 9장 3·4겹 확인(내장 브라우저, 로그아웃 상태): 목록에 데모 1편, 유튜브 재생·목차 이동·검색→장면 이동·복사·좁은 화면·어두운 모드, AI 도구용 버튼 숨김, `/api/lectures/<올리지 않은 ID>` 404, `/api/jobs` 401, 콘솔 오류 없음. 사용자 승인 후 짧은 영상으로 처리 1회를 돌려 관리자 화면에서 진행 카드가 보이는지(선택).
- [ ] **Step 8:** 증거 문서 마무리(명령·결과 성공/실패/미확인, 공개 주소, 비용 확인 방법: Railway Usage 화면에서 하루 뒤 실측) + `docs/handoff.md` §1·다음 할 일·§3 기록 + 커밋:

```bash
git add docs/superpowers/evidence/2026-10-06-stage4-railway.md docs/handoff.md
git commit -m "docs(stage4): railway deployment and public-scope verification" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
