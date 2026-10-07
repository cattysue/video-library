# 2026-10-06 5단계(마켓플레이스·설치 안내서·공개 저장소) 구현·확인 기록

계획 [2026-10-06-stage5-marketplace.md](../plans/2026-10-06-stage5-marketplace.md), 실행 방식: 직접 실행(Claude Code).

## 사용자 결정
저장소 `cattysue/video-library`(공개), MIT, 공개 저장소는 새 기록으로 시작(작성자 GitHub noreply), `docs/`는 정리해서 포함, 영어 번역은 요청할 때만, [영어 번역 요청] 복사 문구를 슬래시 없는 `video-library 번역 <ID>`로 변경.

## 공식 형식 확인
- Claude Code: `.claude-plugin/marketplace.json`(name·owner·plugins[name·source]), 플러그인 `.claude-plugin/plugin.json`, 스킬은 플러그인 루트 `skills/<이름>/SKILL.md`. 플러그인 스킬은 이름 앞에 플러그인 이름이 붙는다(`/video-library:video-library`).
- Codex: `.agents/plugins/marketplace.json`(source `{"source":"local","path":"./…"}`, policy), 플러그인 `.codex-plugin/plugin.json`, 스킬은 루트 `skills/`에서 찾음. 설치 `codex plugin marketplace add owner/repo` → `codex plugin add 이름@마켓`.

## 구현 (Task 1~5)
| Task | 내용 | 결과 |
|---|---|---|
| 1 | 마켓플레이스 2개·플러그인 매니페스트 2개 | ✓ `claude plugin validate`(플러그인·마켓플레이스) 모두 `✔ Validation passed`. `claude --plugin-dir … plugin details video-library` → 스킬 1개, 항상 드는 비용 약 340토큰·호출 시 약 8.5k |
| 1 발견 | **SKILL.md 맨 위 설정(YAML) 문법 오류** — 설명문 안의 "질문: …"(콜론+공백) 때문에 설치하면 설명이 통째로 빠져 스킬이 호출되지 않을 수 있었다(공식 검사기가 발견) | 설명문을 작은따옴표로 감싸고 검사 테스트 추가 ✓ |
| 2 | 복사 문구 `video-library 번역 <ID>`, 빈 목록 안내에 설치 후 명령(`/video-library:video-library`·`$video-library`·평문), SKILL 요청 예시 평문화 | ✓ |
| 3 | README(설치·사용·준비물·Mac·선택 Railway), MIT LICENSE, 1:1 수업 안내서 `docs/ta-guide.md`, `.railwayignore` | ✓ (제거 명령 `claude plugin uninstall`·`codex plugin remove` 존재 확인) |
| 4 | 공개 전 정리: PC 경로 2곳, 다른 분 영상 ID·제목·자막 예시(표·검색어·교정 예시), 4단계 계획의 영상 ID, 예시 경로 1곳, 인계 문서의 영상 ID 1곳 → 일반 표현. 자동 검사 `test_public_hygiene.py`(경로·개인 이메일·Railway ID·다른 분 영상 정보·해시 모양) | ✓ |
| 5 | 공개용 새 기록: 기존 기록은 이 PC의 `private-history` 브랜치에 백업, 저장소 작성자 설정을 noreply로, `main`을 커밋 1개로 새로 만듦 | ✓ 작성자·커미터 모두 noreply, 커밋 1개, 백업과 내용 차이 0 |

## 공개 전 독립 검토 (Opus) → 수정
판정: "수정 후 공개". 모든 파일·커밋 정보를 읽고, 공식 검사기와 새로 내려받은 사본에서 테스트까지 확인했다.

| 지적 | 내용 | 수정 |
|---|---|---|
| 치명 | 공개 검사 파일(과 5단계 계획서)에 다른 분 영상 ID·출연자 이름·Railway ID 앞부분이 **조각난 문자열로** 남아 있었다 — 읽으면 그대로 보이고, 플러그인 폴더 안이라 설치하는 모든 PC에도 복사됨 | 공개 파일에는 '모양' 규칙(PC 경로·개인 메일·UUID·해시 모양)만 두고, 구체적인 값은 이 PC 전용 `.superpowers/hygiene-denylist.txt`(Git 제외)로 옮김. 그 목록이 있으면 조각낸 표기까지 잡는 테스트 추가. **공개용 커밋을 처음부터 다시 만들어** 이전 커밋의 문자열이 공개 기록에 남지 않게 함 |
| 중요 | 1:1 안내서가 "파이썬이 없으면 점검이 설치해 준다"고 안내 — 점검 자체가 파이썬 프로그램이라 실행되지 않음, Mac 기본 python3는 3.9 | 수업 전 확인에 `python --version`/`python3 --version`·python.org 설치·PATH 체크 추가, README 준비물에도 |
| 중요 | Codex 설치·실행은 아직 실제로 해 보지 않음 | Task 7에서 확인(공개 안내 전). README·안내서에 "처음 실행할 때 인터넷·파일 쓰기 허락을 물을 수 있음" 추가 |
| 중요 | SKILL 설명문에 `/video-library 열기`(접두사 없는 명령) 하나 남음 | `video-library 열기`로, 사용자 문서·화면 전체에서 접두사 없는 `/video-library`를 막는 테스트 추가 |

사소한 점(나중에): README의 `python …` 명령에 Mac `python3` 표기, Railway 절에 `railway login`·`git clone` 줄, 제거 안내에 마켓플레이스 제거와 영상자료실 폴더가 남는다는 설명, 인계 문서의 일부 공개 정보(다른 분 강의 번역 기록, 비밀번호 최소 길이), 예시 주소 `video-library.up.railway.app`, Codex 매니페스트 표시 이름, 설계서 3장 README 위치.

## 자동 테스트
- 검토 수정 후 `python -m pytest -W error` → `414 passed`. (수정 전 `411 passed`)

## 참고
- 이 대화 밖의 세션이 같은 폴더에서 의학 강의(영상 C) 영어 번역을 실행하고 Railway에 **비공개**로 올렸다(인계 문서 기록). 비공개라 손님 화면에는 보이지 않는다.

## GitHub 공개·Railway 재배포 (Task 6, 사용자 승인)
| 단계 | 결과 |
|---|---|
| 공개 저장소 | `gh repo create cattysue/video-library --public --source . --push` → https://github.com/cattysue/video-library ✓ / 공개 상태 PUBLIC, 기본 브랜치 `main`, 원격 브랜치는 `main` 하나, 커밋 1개(작성자·커미터 noreply) ✓ / GitHub가 라이선스를 MIT로 인식 ✓ / 저장소 첫 화면에 README·폴더 구성 표시 ✓ |
| Railway 재배포 | `railway up --service video-library --detach` → 약 36초 뒤 새 화면 파일(복사 문구 `video-library 번역 <ID>`) 반영 ✓ / `/api/health` 정상, 공개 목록은 데모 1편(공개) 그대로 ✓(볼륨 유지) |

## 실제 설치 확인 (Task 7, 사용자 승인)
| 도구 | 명령·결과 |
|---|---|
| Claude Code 2.1.278 | `claude plugin marketplace add cattysue/video-library` → "Successfully added marketplace: video-library" ✓ / `claude plugin install video-library@video-library` → "Successfully installed plugin (scope: user)" ✓ / `claude plugin list` → enabled, 1.0.0 ✓ / `claude plugin details video-library` → 스킬 1개(video-library), 설명 표시 ✓ |
| Codex 0.155.1 | `codex plugin marketplace add cattysue/video-library` → GitHub에서 받아 추가 ✓ / `codex plugin add video-library@video-library` → 설치 ✓ / `codex plugin list` → "installed, enabled 1.0.0" ✓ / 설치 폴더에 `skills/video-library/SKILL.md`(설명문 정상)·`scripts`·`web` ✓ |
| 새 대화에서 영상자료실 열기 | 사용자 확인 ✓ — Claude Code·Codex 둘 다 새 대화에서 영상자료실 화면이 열림 |

## 설치 뒤 사용자 요청
- 조약돌 단추 한 단계 더 작게(글자 13px, 여백 4px 12px, [보기] 5px 15px, 단추 사이 8px) → 테스트 `test_pebbles_are_compact`, 전체 415개 통과, 내 PC 영상자료실 화면에 반영·스크린샷 확인 ✓. 사용자 승인(10-07)으로 버전 **1.0.1** 배포 — 아래 표.
