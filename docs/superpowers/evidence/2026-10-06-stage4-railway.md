# 2026-10-06 4단계(Railway 공개 서버) 구현·확인 기록

브랜치 `feat/stage4-railway`, 계획 [2026-10-06-stage4-railway.md](../plans/2026-10-06-stage4-railway.md), 실행 방식: 직접 실행(Claude Code).

## 결정 (계획 작성 전)
- Railway 요금(공식 요금표): Hobby 월 $5, 사용량 $5 포함(다른 앱과 공유), 메모리 GB당 월 $10, CPU 1개당 월 $20, 볼륨 GB당 월 $0.15.
- 사용자 결정: PostgreSQL 대신 **볼륨 파일 저장**(예상 추가 월 $0.5~1.5, 어림값). 설계서 3·5.4·8.3·10·11·12장에 반영.

## 구현 (Task 1~9)
| Task | 내용 | 결과 |
|---|---|---|
| 1 | `HostedStore`(업로드·공개 상태 `visibility.json`·삭제·진행 보고 검사), 검색 `allowed` | ✓ |
| 2 | `auth`: PBKDF2 비밀번호 해시, 토큰 SHA-256, 세션 12시간, 15분 10회 실패 잠금 | ✓ |
| 3 | 서버 호스팅 모드: 공개 범위, 업로드(토큰), 로그인·로그아웃, 공개 전환·삭제(관리자 + `X-Requested-With`) | ✓ |
| 4 | `vl.py serve --hosted`: 해시 변수 없으면 시작 거부 | ✓ |
| 5 | `remote`(config.json·요청), 진행 보고(3초·조용히 실패), 테스트 인터넷 차단 가드 | ✓ (계획 코드의 오류 응답 미닫힘을 고침) |
| 6 | `vl.py upload`, `--no-upload`, 업로드 대기 중이면 작업을 끝내지 않음 | ✓ |
| 7 | `vl.py connect`: 숨김 입력, 토큰 생성, 해시를 `railway variable set --stdin`으로 | ✓ |
| 8 | 화면: 관리자 로그인·[공개/비공개]·[삭제], 손님에게 진행 카드·AI 도구용 버튼 숨김 | ✓ |
| 9 | 명령 등록, SKILL.md 12단계·업로드·Railway 연결, API 문서 | ✓ |

**전체 테스트 중 발견·수정:** 토큰이 틀린 업로드를 서버가 본문을 다 받기 전에 401로 거절하면, Windows에서 보내는 쪽이 "401" 대신 연결 끊김(WinError 10053)을 받는 경우가 있었다(간헐). 거절 전에 남은 본문(20MB 이하)을 받아 두도록 고치고, 3MB 본문으로 항상 재현하는 테스트를 추가했다.

## 내 PC에서 호스팅 모드 확인 (Task 10)
시험용 폴더(세션 임시 폴더)에서 `vl.py serve --hosted`(포트 8790)를 켜고, 시험용 PC 자료실에 데모 강의(`40JNj2zjnQc`) 사본을 넣어 `vl.py upload`로 올렸다. 시험 비밀번호·토큰은 무작위로 만들어 파일에만 두었다.

| 항목 | 결과 |
|---|---|
| `/api/health` | `{"app":"video-library","mode":"hosted","admin":false}` ✓ |
| `vl.py upload --video 40JNj2zjnQc` | `uploaded: true, public: false` ✓ |
| 로그아웃 상태, 비공개일 때: 목록 `[]`, 단건 404, `/api/jobs` 401 | ✓ |
| 로그아웃 화면: "아직 공개된 강의가 없습니다.", [관리자] 버튼, 진행 카드 없음 | ✓ |
| 공개로 바꾼 뒤(서버 저장소에 직접 적용): 목록 카드 표시, 단건 200 | ✓ |
| 강의 화면(손님): 전사 434문장, 유튜브 플레이어, 검색 `꺾쇠` 1건, [이 강의에 질문하기]·[영어 번역 요청] 숨김, 콘솔 오류 없음 | ✓ |
| PC 모드 회귀: [관리자] 버튼 숨김, 관리자 버튼 없음, 카드·[보기] 정상 | ✓ |
| 브라우저에서 관리자 로그인 → [비공개]/[공개 중] 전환 → [삭제] | **미확인** — 시험 비밀번호를 AI가 읽는 동작을 안전장치가 막았다(비밀번호는 AI가 다루지 않는 것이 원칙). 같은 동작은 자동 테스트(`test_server_hosted.py`)로 확인했고, 화면은 Railway 배포 후 사용자가 직접 로그인해 확인한다 |

## 최종 독립 검토 (Opus, 배포 전) → 수정
판정: "수정 후 배포". 공개 서버라 배포(Task 11) **전에** 검토했다. 치명 1·중요 3 + 손님 안내 문구(사소 → 중요로 재등급)를 테스트 먼저 작성(실패 확인) → 수정 → 통과로 고쳤다.

| 지적 | 증상 | 수정 | 테스트 |
|---|---|---|---|
| C1 로그인 잠금 우회 | 틀린 비밀번호를 동시에 수십 개 보내면 10번 잠금이 걸리지 않고 전부 확인됨(검토자 실험 60/60) — 비밀번호 대입·CPU 과금 | 확인 중인 시도도 한도에 포함, 비밀번호 계산은 한 번에 하나 | `test_parallel_guesses_cannot_skip_the_lock` |
| I1 거절한 본문으로 메모리·스레드 소모 | 토큰 없이 20MB 본문을 여러 개 보내면 메모리를 한꺼번에 씀, 보내다 멈춘 연결이 스레드를 영원히 잡음 | 연결 시간 제한 30초, 거절한 본문은 64KB씩 읽고 버림 | `test_stalled_upload_is_dropped`(처음엔 테스트가 스스로 시간 제한을 걸어 미리 통과 → 기본값을 확인하도록 고쳐 실패 확인) |
| I2 Railway 이상 응답으로 처리 중단 | 응답이 중간에 끊기면(`IncompleteRead`) 진행 보고 오류가 PC 처리 단계를 멈춤 | 요청 오류를 모두 `RemoteError`로, 진행 보고는 어떤 오류도 삼킴 | `test_broken_reply_does_not_stop_processing` |
| I3 나중 영어 번역이 Railway에 안 올라감 | 공개 강의에 영어 번역을 더해도 Railway 사본은 그대로 | `reopen`이 설정이 있으면 업로드 단계를 대기로, SKILL 번역 절차에 업로드 추가 | `test_reopen_uploads_again_when_railway_is_set`, `test_translation_request_uploads_again` |
| 손님에게 PC 안내 | Railway가 잠깐 안 될 때 손님에게 "영상자료실 열기 더블클릭" 안내, 첫 확인 실패 시 PC 화면처럼 AI 도구 버튼 표시 | 공개 서버용 문구 "서버에 연결하지 못했습니다. 잠시 뒤 새로고침하세요.", 확인 실패를 PC로 넘겨짚지 않음 | `test_public_visitors_never_get_pc_only_messages` |

남은 사소한 점 13건(ID 정규식 끝 줄바꿈, 업로드 대기 카드가 끝나지 않는 경우, 500 응답 본문 미처리, CSP `frame-ancestors`, 깨진 lecture.json 업로드 오류 메시지, 401 안내 문구, 진행 상세 200자 제한, 진행 보고 지연 합계, Git Bash에서 connect 거부, OneDrive 동기화 가능성, 전체 잠금으로 인한 관리자 잠김, README Railway 절 미작성)은 나중에 다룬다.

## 자동 테스트
- 최종 수정 후 `python -m pytest -W error` → `395 passed`. (Task 10 끝 `389 passed`)

## Railway 배포 (Task 11, 단계마다 사용자 승인)
| 단계 | 명령·결과 |
|---|---|
| 1 프로젝트 (승인) | `railway init --name video-library` → 새 프로젝트 `video-library`(환경 production), plugin-app 폴더 연결 ✓ |
| 2 서비스·볼륨·주소 (승인) | `railway add --service video-library` ✓ / `railway volume add --mount-path /data` — Git Bash가 `/data`를 Windows 경로로 바꿔 1차 실패, `MSYS_NO_PATHCONV=1`로 다시 실행 → `video-library-volume`(5GB 한도, Ready, /data) ✓ / `RAILWAY_DOCKERFILE_PATH=railway/Dockerfile` ✓ / 공개 주소 `https://video-library-production-8b85.up.railway.app` ✓ |
| 사용자 요청 | 관리자 비밀번호 최소 길이 10자 → **6자**(`connect.MIN_PASSWORD`). 로그인은 15분 10회 잠금이 그대로라 인터넷으로 맞혀 보기는 여전히 어렵다. 테스트 `test_six_character_password_is_enough`, 전체 396개 통과 |
| 3 연결 (사용자 직접) | 사용자가 PowerShell에서 `vl.py connect … --service video-library` 실행 → "연결 완료". 확인(값은 보지 않음): `config.json`에 서버 주소·토큰 있음, Railway 변수 `VL_ADMIN_PASSWORD_HASH`(pbkdf2 형식)·`VL_UPLOAD_TOKEN_HASH`·`RAILWAY_DOCKERFILE_PATH` 설정됨 ✓ |
| 4 배포 (승인) | `railway up --service video-library --detach` → 약 18초 뒤 공개 주소 응답. 로그: 볼륨 연결, "video-library Railway 서버: 포트 8080" ✓ / `/api/health` = `{"app":"video-library","mode":"hosted","admin":false}` ✓ / `/api/lectures` = `[]` ✓ / `/api/jobs` 401 ✓ / `/` 200 ✓ |
| 5 데모 업로드 (승인) | `vl.py upload --video 40JNj2zjnQc` → `uploaded: true, public: false` ✓ / 로그아웃 상태 목록 `[]`, 단건 404 ✓ (다른 3편은 올리지 않음) |
| 6 공개 (사용자 직접) | 사용자가 공개 주소에서 [관리자] 로그인 → 데모 카드 [비공개] → "공개 중" ✓ (사용자 화면 캡처: "공개 중"·[삭제]·[보기] 표시). Task 10의 **미확인**(브라우저 관리자 화면) 해소 |
| 7 손님 화면 확인 (내장 브라우저, 로그아웃) | 목록: 데모 1편, 관리자 단추 없음, 진행 카드 없음 ✓ / 올리지 않은 강의 ID 404, `/api/jobs` 401 ✓ / 검색 `꺾쇠` → 데모 15건 ✓ / 강의 화면 `t=113`: 유튜브 플레이어, 1:53 "우선 어 꺾쇠가 등장을 합니다." 강조, 전사 434문장, 목차 32, [원문(KO)·번역(EN)·나란히], [이 강의에 질문하기]·[영어 번역 요청] 숨김, 서버 끊김 안내 없음 ✓ / 콘솔 오류는 제가 확인용으로 부른 404·401 두 건뿐 |

공개 주소: **https://video-library-production-8b85.up.railway.app** (데모 강의만 공개).

## 남은 확인
- 비용: 하루쯤 뒤 Railway Usage 화면에서 `video-library` 프로젝트 실사용액 확인(예상 월 $0.5~1.5, **미확인**).
- 처리 중 진행 카드가 Railway 관리자 화면에 보이는지: 다음에 새 영상을 처리할 때 확인(**미확인**, 자동 테스트로는 확인).
- `railway up`은 `.gitignore`만 따르므로 작업 장부 폴더(`.superpowers/`)도 빌드용으로 함께 올라갔을 수 있다(비밀 값 없음, 이미지에는 `.dockerignore`로 들어가지 않음). 다음 배포 전에 `.railwayignore` 추가 검토.

