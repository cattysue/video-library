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
| `GET /api/search?q=<검색어>&field=<분야>&video=<ID>` | 통합 검색(`field`·`video`는 선택) | ✅ | 공개만, 관리자는 전부 |
| `GET /api/health` | 서버 확인 `{"app":"video-library","home":…}` | ✅ | 누구나(`home`은 PC만) |
| `GET /api/jobs` | 실행 중인 작업 전부 + 최근 1시간 안에 끝난 작업(`updated_at` 내림차순) | ✅ | 관리자 |
| `POST /api/jobs/<job_id>` | 진행 보고 | ❌ | 업로드 토큰 |
| `PUT /api/lectures/<id>` | `lecture.json` 업로드(교체, 공개 상태 유지, 새 강의는 비공개) | ❌ | 업로드 토큰 |
| `PATCH /api/lectures/<id>` | `{"public": true|false}` | ❌ | 관리자 |
| `DELETE /api/lectures/<id>` | 삭제 | ❌ | 관리자 |
| `POST /api/login` · `POST /api/logout` | 관리자 로그인 | ❌ | — |

- PC 미니 서버는 읽기 전용이며 `127.0.0.1`에만 열린다. GET 외 요청은 405, `Host`가 `127.0.0.1:<포트>`·`localhost:<포트>`가 아니면 403. 정적 파일은 `/`(목록)·`/lecture`(강의)·`/app/<파일>`(`영상자료실/app/` 바로 아래 `.html .css .js .svg .png .ico`)만 낸다. 포트는 8765부터 빈 번호, 실행 정보는 `영상자료실/.server.json`.
- `GET /api/health`: PC `{"app":"video-library","mode":"pc","home":…}`, Railway `{"app":"video-library","mode":"hosted","admin":true|false}`(폴더 경로는 내지 않음).
- Railway 서버(`vl.py serve --hosted`)는 볼륨 `/data`에 PC와 같은 파일 형식으로 저장하고, 공개 목록은 `/data/visibility.json` `{"public": [<ID>, …]}`에 둔다(깨지거나 없으면 아무것도 공개하지 않음). 정적 파일은 이미지에 들어 있는 `web/`에서 낸다. `Host` 검사는 하지 않는다.
- 업로드 토큰: `Authorization: Bearer <토큰>` 헤더(`PUT /api/lectures/<id>`, `POST /api/jobs/<job_id>`). 토큰은 `영상자료실/config.json`(공개 금지)에서 읽고, 서버는 `VL_UPLOAD_TOKEN_HASH`(SHA-256)와 비교한다. 틀리면 401.
- 관리자: `POST /api/login` `{"password"}` → 세션 쿠키 `vl_session`(`HttpOnly; Secure; SameSite=Strict`, 12시간). 비밀번호는 `VL_ADMIN_PASSWORD_HASH`(PBKDF2-SHA256)와 비교. 15분에 10번 실패하면 15분 잠금(429). `POST /api/login`·`/api/logout`·`PATCH`·`DELETE`는 `X-Requested-With: video-library` 헤더가 없으면 403, 로그인하지 않았으면 401.
- 본문: JSON. 업로드 최대 20MB, 그 밖 64KB. `Content-Length`가 없으면 411, 넘으면 413, JSON이 아니면 400. 업로드는 서버가 `validate_lecture`로 다시 검사하고 주소의 ID와 `lecture.id`가 같아야 한다(아니면 400). 진행 보고는 `jobs/<job_id>.json` 형식(시간대 있는 시각, 정해진 키만)이어야 한다.
- 응답: 업로드 `{"id","public"}`(새 강의 `false`, 재업로드는 기존 공개 상태 유지), 공개 전환 `{"id","public"}`, 삭제 `{"id","deleted":true}`, 진행 보고 `{"job_id"}`. 로그인하지 않은 사람에게 비공개 강의는 목록·검색에서 빠지고 단건은 404, `GET /api/jobs`는 401.

### 검색 응답

```json
{"query": "브랜치", "results": [
  {"id": "AbCdEfGhIjK", "title": "...", "field": "dev",
   "hits": [{"where": "segment", "idx": 7, "start": 230.0, "text": "브랜치는 원본을…", "lang": "ko"},
            {"where": "glossary", "idx": 7, "start": 230.0, "text": "브랜치(Branch)"}]}]}
```

`where` ∈ `title`·`chapter`·`glossary`·`segment`·`translation`. `start`는 해당 문장 시작 시간(제목은 0, 제목 결과의 `idx`는 `null`). `segment`·`translation` 결과에는 `lang`이 붙는다. 강의마다 최대 20건, 검색어는 대소문자·띄어쓰기를 가리지 않는다.

### 오류 응답

모든 오류는 `{"error": "<한국어 이유>", "details": ["<경로>: <이유>", ...]}` (`details`는 검사 실패 때만). 상태 코드: 400 형식·검사 실패, 401 토큰·로그인 없음, 403 권한 없음, 404 없음(비공개 포함), 413 너무 큼, 429 로그인 시도 초과.
