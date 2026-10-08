# AGENTS.md — video-library 작업 규칙 (Codex · Claude Code 공통)

이 저장소는 Claude Code·Codex 플러그인 `video-library`이자 두 도구의 마켓플레이스다. 두 AI 도구가 번갈아 **개발과 감수(서로 검토)**를 한다.

## 시작할 때
1. `docs/handoff.md` §1(현재 상태·다음 할 일)을 읽고, `git status`·`git log --oneline -10`으로 그 뒤 변경을 확인한다. 문서와 Git이 다르면 Git과 최신 `docs/superpowers/evidence/`를 믿는다.
2. 구조·약속은 설계서 `docs/superpowers/specs/2026-10-05-video-library-design.md`, API는 `docs/api.md`, 남은 일은 `docs/backlog.md`.

## 일하는 방식
- 설계 → 사용자 승인 → 계획 → **TDD**(실패하는 테스트 먼저) → 독립 검토 → 검증. 테스트: `python -m pytest -W error`.
- 감수할 때는 실제로 테스트를 돌려 확인하고, 지적은 "사용자가 겪을 일" 기준 치명·중요·사소로 나눈다. 사소한 것은 `docs/backlog.md`에.
- 사용자에게는 한국어로, 성공·실패·미확인을 나눠 보고한다. 결정이 필요하면 선택지와 추천·이유를 함께 준다.
- 끝낼 때마다 `docs/superpowers/evidence/`에 기록하고 `docs/handoff.md` §1 갱신·§3 표에 한 줄 추가.

## 승인 없이 하지 않는 것
GitHub push, Railway 작업(생성·변수·배포), 사용자 PC의 플러그인 설치·업데이트, 패키지 설치, 실제 영상 처리(사용량이 큼).

## 공개 저장소 규칙
- 이 저장소는 공개다. PC 경로, 개인 이메일, 서비스 ID, 비밀번호·토큰·해시, 데모(`40JNj2zjnQc`) 외 영상의 ID·제목·출연자·자막을 넣지 않는다. `tests/test_public_hygiene.py`가 모양을 검사하고, 구체적 금지 값은 Git 밖의 로컬 목록(`.superpowers/hygiene-denylist.txt`)에만 둔다 — 금지 값을 테스트·문서에 직접 적지 않는다.
- push는 `git push origin main`만. 로컬 전용 브랜치는 올리지 않는다(`--all`·`--mirror` 금지). 커밋 작성자 설정(GitHub noreply)을 바꾸지 않는다.
- 관리자 비밀번호·업로드 토큰은 AI가 묻거나 읽거나 출력하지 않는다. `vl.py connect`는 사용자가 자기 터미널에서 직접 실행한다.

## 자주 걸리는 점
- Claude Code에서 플러그인 스킬은 `/video-library:video-library`(접두사 필수). 사용자 문서·화면에 접두사 없는 `/video-library`를 쓰지 않는다(테스트가 막음). Codex는 `$video-library`, 둘 다 평문 요청 가능.
- `SKILL.md` 설명문은 작은따옴표로 감싼 YAML. 고친 뒤 `claude plugin validate ./plugin/video-library`와 `claude plugin validate .`.
- 설치본에 반영하려면 두 `plugin.json`의 버전을 올린다(`tests/test_marketplace.py`의 기대 버전도). 릴리스 절차는 `docs/handoff.md` §1.
- Windows: PowerShell 한글 출력은 `[Console]::OutputEncoding=[Text.UTF8Encoding]::new();`, Git Bash에서 `/data` 같은 인자는 `MSYS_NO_PATHCONV=1`.
