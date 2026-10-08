# video-library 인계 문서 (Claude Code ↔ Codex)

이 폴더(`plugin-app/`)는 바이브코딩대학 3회차 과제 플러그인 `video-library`의 **독립 Git 저장소**다(바깥 `바코대AX` 저장소는 이 폴더를 무시한다). 도구를 바꿔 이어서 작업할 때 이 문서를 먼저 읽는다. 새로운 사용자 지시가 이 문서보다 우선한다.

## 1. 현재 상태와 다음 할 일

| 영역 | 상태 | 근거 |
|---|---|---|
| 요구사항·설계 | 설계서 **승인**(10-05) | [설계서](superpowers/specs/2026-10-05-video-library-design.md) |
| Codex 영상자료실 열기 | 10-06 설치된 스킬의 `open` 실행 성공, 로컬 화면 HTTP 200 확인. 사용자 화면 표시·개별 강의 재생은 미확인 | [증거](superpowers/evidence/2026-10-06-codex-library-open.md) |
| 1단계 약속 | 완료 — 스키마·검사기·샘플·`vl.py validate`·API 문서 (`main`에 합침) | [증거](superpowers/evidence/2026-10-05-stage1-contract.md), [API](api.md) |
| 2단계 플러그인 처리 | 완료 — config·jobs·fetch(yt-dlp)·preprocess·chunk·check·merge·library·assemble·doctor·SKILL.md, 실제 영상 1편 처리 성공 (`main`에 합침) | [증거](superpowers/evidence/2026-10-05-stage2-pipeline.md) |
| 3단계 화면 + PC 서버 | 완료 — store_file·search·server·opener, 목록·강의 화면, `vl.py open/serve/search`, 실제 영상 4편(개발·과학 EN→KO·금융·의학) 화면 확인 (`main`에 합침), 최종 검토 중요 5건 수정, 분야 단추·[보기] 조약돌 디자인, 테스트 307개 | [증거](superpowers/evidence/2026-10-06-stage3-viewer.md), [API](api.md) |
| 4단계 Railway | 완료 — 공개 서버 모드·로그인·업로드·connect, 최종 검토 수정, Railway 배포(`https://video-library-production-8b85.up.railway.app`, 데모 1편 공개), 테스트 396개 (`main`에 합침) | [계획](superpowers/plans/2026-10-06-stage4-railway.md) |
| 5단계 마켓플레이스 | 완료 — 공개 저장소 https://github.com/cattysue/video-library (MIT), Claude Code·Codex 마켓플레이스 설치 확인(새 대화에서 영상자료실 열림), README·1:1 수업 안내서, Railway 재배포 | [증거](superpowers/evidence/2026-10-06-stage5-marketplace.md) |
| 1.0.2 공개 | `719efe8`에서 R1 수정, `2dedb27`에서 R2·R3 수정과 1.0.2 공개. GitHub·양쪽 도구 설치본·Railway 반영은 사용자 설명과 기존 기록 기준이며 이번 운영 재확인은 없음 | [이전 감수와 처리 기록](superpowers/evidence/2026-10-08-codex-review.md) |
| 최신 Git 상태 | 재감수 시작 HEAD는 `edce55f`(handoff 기록 추가). 로컬 추적 `origin/main`의 `2dedb27`보다 문서 커밋 1개 앞섬. 원격 재조회 없음 | `git log --oneline -10` |
| 10-08 Codex 재감수 | 428개 테스트·JS 문법·공식 검사 통과. R1 해소, R2 재시도와 `check_job` 호환 확인. 중요 N1(배경 탭에서 완료된 강의의 목록 갱신 누락), 사소 N2·N3 확인 | [재감수 증거](superpowers/evidence/2026-10-08-codex-rereview.md) |

**다음에 할 일:**
1. 중요 N1 수정 권장: 숨긴 동안 시작·완료된 강의도 탭 복귀 시 목록에 보이도록 강의 목록 갱신을 추가. 동작 테스트부터 재현한다. [재감수 증거](superpowers/evidence/2026-10-08-codex-rereview.md) 참고.
2. 사소 N2(업로드 경고 1시간 뒤 사라짐)·N3(Railway 최초 업로드 실패 카드의 보기 링크)를 보완한다. Railway 실사용액은 아직 미확인.
3. 수정 배포 방법(단계마다 승인): 버전 올리기(두 `plugin.json`·테스트 기대값) → 테스트·공식 검사 → `main`만 push(`private-history` 절대 금지) → 설치본 `claude plugin marketplace update video-library` + `claude plugin update video-library@video-library`, Codex `codex plugin marketplace upgrade video-library` + `codex plugin add video-library@video-library` → Railway `railway up`.
4. 과제는 기존 10-08 진행 기록상 10-07 코칭에서 통과. 안내서(`docs/ta-guide.md`)와 남은 일(`docs/backlog.md`)을 유지한다. 이번 검토는 로컬 기준이며 운영·설치본을 새로 확인하지 않았다.

## 2. 지켜야 할 것
- Superpowers 절차: 설계 → 사용자 승인 → 계획 → TDD 구현 → 검토 → 검증.
- Railway 배포, 공개 GitHub 저장소 생성, 유료 AI 호출, PC 설정 변경, 패키지 설치는 **단계마다 사용자 승인**.
- 업로드 토큰·관리자 비밀번호는 채팅·Git·문서에 남기지 않는다. AI는 토큰을 묻거나 출력하지 않는다.
- 이 저장소는 공개돼 있다. 남의 영상 내용, 개인 경로·계정 정보를 넣지 않는다.
- 사용자는 비개발자 학습자다. 기술용어는 짧게 설명하고 성공·실패·미확인을 나눠 보고한다.

## 3. 진행 기록 (새 작업은 맨 아래에 추가)

| 날짜 | 도구 | 한 일 | 커밋 | 근거 |
|---|---|---|---|---|
| 10-03 | Claude | `plugin-app` 폴더 생성, 참고 저장소 lecture-pipeline 구조·화면 분석 | — | 대화 기록 |
| 10-05 | Claude | 브레인스토밍으로 요구사항 합의, 설계서 초안 작성, 독립 저장소 초기화 | (이 커밋) | [증거](superpowers/evidence/2026-10-05-design.md) |
| 10-05 | Claude | 설계서 승인 받음, 1단계(약속) 구현 계획 작성 | (이 커밋) | [계획](superpowers/plans/2026-10-05-stage1-contract.md) |
| 10-05 | Claude | 1단계(약속) 구현: 스키마·검사기·샘플·`vl.py validate`·API 문서, 테스트 83개 통과 | 9cc6c5d..8859375 | [증거](superpowers/evidence/2026-10-05-stage1-contract.md) |
| 10-05 | Claude | 1단계 최종 독립 검토: 중요 5건 수정(숫자 기호·끼워 넣기·줄바꿈·NaN·직접 호출 예외), 테스트 90개 통과, 사소 8건은 증거 문서에 기록 | 89365aa, (이 커밋) | [증거](superpowers/evidence/2026-10-05-stage1-contract.md) |
| 10-05 | Claude | 1단계 브랜치를 `main`에 합침(fast-forward), 합친 뒤 테스트 90개 통과 | (이 커밋) | `python -m pytest -W error` |
| 10-05 | Claude | 2단계(플러그인 처리) 구현 계획 작성(14개 Task, Task 13 실제 영상 실행은 승인 필요) | (이 커밋) | [계획](superpowers/plans/2026-10-05-stage2-pipeline.md) |
| 10-05 | Claude | 2단계 구현(Task 1~12, 테스트 219개) + 실제 영상(40JNj2zjnQc, 38분, 영어 번역 포함) 처리 성공, 서브에이전트 약 90만 토큰 | 06f2b64..(이 커밋) | [증거](superpowers/evidence/2026-10-05-stage2-pipeline.md) |
| 10-05 | Claude | 2단계 최종 독립 검토: 중요 6건 수정(맥락표 기반 교정 예외, 잠긴 폴더, 작업 기록 정리·best-effort, --video 검사, SKILL.md 실패·PowerShell 규칙), 테스트 243개 통과, 사소 7건은 증거 문서에 | a943be3, (이 커밋) | [증거](superpowers/evidence/2026-10-05-stage2-pipeline.md) |
| 10-06 | Claude | 2단계 브랜치를 `main`에 합침(fast-forward), 합친 뒤 테스트 243개 통과 | (이 커밋) | `python -m pytest -W error` |
| 10-06 | Claude | 3단계 사전 실험(127.0.0.1 유튜브 삽입 재생 ✓·seek ✓·자동 재생 차단) + 구현 계획 작성(11개 Task) | (이 커밋) | [계획](superpowers/plans/2026-10-06-stage3-viewer.md) |
| 10-06 | Claude | 3단계 구현(Task 1~11): 미니 서버·화면·열기·검색, 브라우저 확인, 영상 3편 추가 처리(에이전트 1개 순차 방식 약 13~15만 토큰/편), 테스트 298개 | 2011f22..(이 커밋) | [증거](superpowers/evidence/2026-10-06-stage3-viewer.md) |
| 10-06 | Claude | 3단계 최종 독립 검토(Opus): 중요 5건(포트 가로채기·스킬 호출 문구·서버 꺼짐 안내·질문 답변 절차·열기 파일 위치) + 용어집 claim_note 기준 수정, 테스트 306개, 사소 26건은 증거 문서에 | (이 커밋) | [증거](superpowers/evidence/2026-10-06-stage3-viewer.md) |
| 10-06 | Claude | 사용자 확인(열기 파일·유튜브 재생 ✓) + 분야 단추·[보기]를 분야별 파스텔 조약돌 디자인으로, 테스트 307개 | (이 커밋) | [증거](superpowers/evidence/2026-10-06-stage3-viewer.md) |
| 10-06 | Claude | 단추 크기 축소·색 진하게(사용자 요청), 3단계 브랜치를 `main`에 합침(fast-forward) | (이 커밋) | `python -m pytest -W error` |
| 10-06 | Claude | Railway 비용 확인(Hobby $5 포함 사용량 공유, 예상 추가 월 $0.5~1.5) → 사용자가 PostgreSQL 대신 **파일 저장** 결정, 설계서 반영, 4단계 구현 계획 작성(11개 Task) | (이 커밋) | [계획](superpowers/plans/2026-10-06-stage4-railway.md) |
| 10-06 | Claude | 4단계 구현(Task 1~10: 공개 서버 모드·로그인·업로드·connect·화면·Dockerfile), 내 PC에서 호스팅 모드 확인, 최종 검토(치명1·중요3+1 수정), 테스트 395개 | 4ff4a5b..(이 커밋) | [증거](superpowers/evidence/2026-10-06-stage4-railway.md) |
| 10-06 | Claude | Railway 배포(Task 11): 프로젝트·서비스·볼륨·주소 생성, 사용자 `connect`(비밀번호 6자 이상으로 변경), `railway up`, 데모 업로드, 사용자 공개 전환, 손님 화면·공개 범위 확인 | 2cd6cd8..(이 커밋) | [증거](superpowers/evidence/2026-10-06-stage4-railway.md) |
| 10-06 | Claude | 4단계 브랜치를 `main`에 합침(fast-forward), 합친 뒤 테스트 396개 통과 | (이 커밋) | `python -m pytest -W error` |
| 10-06 | Claude | 5단계 준비: Claude Code·Codex 공식 플러그인 형식 확인, 공개 전 점검(커밋 작성자 개인 이메일 68개, 문서 속 PC 경로·다른 분 영상 정보), 사용자 결정 4건, 계획 작성 | (이 커밋) | [계획](superpowers/plans/2026-10-06-stage5-marketplace.md) |
| 10-06 | Claude | 스킬 사용: `번역 <영상 C(의학)>`(한국어 의학 강의 266문장 → 영어). reopen → 조각 2개 병렬 번역(서브에이전트 2개, 약 20만 토큰) → check 통과 → merge → assemble(validate 통과) → Railway 사본 갱신(비공개 상태로 올라감). 전사가 깨진 문장 몇 곳(7·8·13·100·246·254·266 등)은 뜻을 추정해 옮김 | (이 커밋) | 대화 기록 |
| 10-06 | Claude | 5단계 Task 1~5 + 공개 전 독립 검토(치명 1: 공개 검사 파일에 남의 영상 정보가 조각으로 남음 → 이 PC 전용 목록으로 이동, 중요 3 수정), 공개용 커밋 다시 만듦. 이 표의 커밋 번호는 공개 전 기록(이 PC의 `private-history`) 기준 | (공개 첫 커밋) | [증거](superpowers/evidence/2026-10-06-stage5-marketplace.md) |
| 10-06 | Claude | GitHub 공개(`cattysue/video-library`, 커밋 1개·noreply·MIT 인식) + Railway 재배포(새 복사 문구 반영, 데모 공개 유지) | (이 커밋) | [증거](superpowers/evidence/2026-10-06-stage5-marketplace.md) |
| 10-06 | Codex | 사용자 요청으로 설치된 `video-library` 스킬 실행, 영상자료실 열기 성공·로컬 HTTP 200 확인 | — | [증거](superpowers/evidence/2026-10-06-codex-library-open.md) |
| 10-06 | Claude | 5단계 완료: 공개 마켓플레이스 설치(Claude Code·Codex) 확인, 사용자가 두 도구 새 대화에서 영상자료실 열림 확인. 사용자 요청으로 단추 한 단계 축소(내 PC 반영) | (이 커밋) | [증거](superpowers/evidence/2026-10-06-stage5-marketplace.md) |
| 10-07 | Claude | 1.0.1 배포(작은 단추): 공개 저장소·Claude Code·Codex 설치본·Railway 모두 반영 | (이 커밋) | [증거](superpowers/evidence/2026-10-06-stage5-marketplace.md) |
| 10-07 | Claude | 노션 학습 노트에 3강 페이지(3~5단계 정리) 추가, 허브 진행표 갱신 | (이 커밋) | 노션(개인 공간) |
| 10-07 | Claude | 노션 학습 노트에 3강 설계·1~2단계 페이지 추가, 3~5단계 페이지·허브와 서로 연결 | (이 커밋) | 노션(개인 공간) |
| 10-07 | Claude | 미뤄 둔 사소한 점 정리: 사용자 영향 큰 것 수정(ID 정규식, CSP, 멈춘 진행 카드, 진행 상세 200자, 업로드 안내 2건, README Mac·Railway·업데이트·제거), 나머지는 `docs/backlog.md`에 우선순위로. 테스트 424개. 공개(1.0.2)는 사용자 결정 대기 | (이 커밋) | `docs/backlog.md` |
| 10-08 | Claude | Codex와의 교차 개발·감수를 위한 `AGENTS.md`(공개용 기술 규칙) 추가. 전체 브리핑은 비공개 바깥 저장소 `docs/plugin-app-briefing.md` | (이 커밋) | `AGENTS.md` |
| 10-08 | Codex | 미공개 2커밋과 현재 구현 감수: 424개 테스트·JS 문법·공식 검사 통과, 기존 중요 1·사소 3 확인. evidence·현재 상태·backlog 갱신, 제품 코드 수정·커밋·외부 배포 없음 | 미커밋 | [감수 증거](superpowers/evidence/2026-10-08-codex-review.md) |
| 10-08 | Claude | Codex 감수 R1(업로드 생략 작업도 진행 정보 전송) 실패 테스트로 재현 → 수정, 테스트 426개. 미공개 커밋 3개(1.0.2 후보) | (이 커밋) | [감수](superpowers/evidence/2026-10-08-codex-review.md) |
| 10-08 | Claude | 감수 R2·R3 수정, 1.0.2 공개(R1·R2·R3·사소한 점 정리·AGENTS.md): GitHub `main` push, Claude Code·Codex 설치본 업데이트, Railway 재배포. 사용자 과제 통과(10-07 코칭) | (이 커밋) | [감수](superpowers/evidence/2026-10-08-codex-review.md) |
| 10-08 | Claude | 노션 3강 페이지에 '6단계 Codex 교차 감수와 1.0.2' 추가, 비공개 브리핑 현재 상태 갱신. 다음: Codex 재감수(`6226c56..2dedb27`) | (이 커밋) | 노션(개인 공간) |
| 10-08 | Codex | `6226c56..2dedb27` 재감수: 428개·JS 문법·공식 검사 통과, R1 해소·업로드 재시도/서버 검사 호환 확인. 중요 N1·사소 N2/N3 기록. evidence·handoff·backlog만 갱신, 코드 수정·커밋·외부 작업 없음 | 미커밋 | [재감수 증거](superpowers/evidence/2026-10-08-codex-rereview.md) |
| 10-08 | Claude | Codex 재감수(N1 중요·N2·N3 사소) 확인 → Node 동작 테스트로 재현 후 모두 수정, 테스트 431개. 1.0.3 공개는 사용자 결정 대기 | (이 커밋) | [재감수](superpowers/evidence/2026-10-08-codex-rereview.md) |
