# 1:1 수업 안내서 — video-library 써 보기 (약 30~40분)

조교(또는 수강생) PC에서 플러그인을 설치하고 영상 하나를 처리해 화면으로 보는 데까지 함께 해 보는 순서입니다.

## 수업 전 확인
1. Claude Code 또는 Codex에 로그인되어 있는지
2. **Python 3.10 이상**: 터미널에서 `python --version`(Mac은 `python3 --version`)이 3.10 이상으로 나오는지. 없으면 https://www.python.org/downloads/ 에서 설치한다(Windows는 설치 첫 화면에서 **Add python.exe to PATH**를 체크, Mac은 python.org 설치 파일 사용 — Mac 기본 python3는 3.9라 안 됨). 파이썬이 없으면 플러그인의 환경 점검 자체가 실행되지 않는다.
3. 인터넷 연결
4. 10분 안팎의 **자막이 있는** 한국어 강의 링크 하나(공개 데모와 같은 바이브코딩대학 강의 추천)

## 순서
### 1) 설치 (5분)
- Claude Code: `claude plugin marketplace add cattysue/video-library` → `claude plugin install video-library@video-library`
- Codex: `codex plugin marketplace add cattysue/video-library` → `codex plugin add video-library@video-library` → Codex 다시 시작

### 2) 영상 하나 처리 (10~15분)
- Claude Code: `/video-library:video-library <링크>` / Codex: `$video-library <링크>`
- 첫 단계에서 환경 점검(`doctor`)이 돌아갑니다. yt-dlp나 deno(또는 Node.js)가 없으면 설치 명령이 나오고, **승인하면** 설치합니다.
- Codex는 처음 실행할 때 인터넷 사용·문서 폴더에 파일 쓰기 허락을 물을 수 있습니다. 허락해야 자막을 받고 영상자료실에 저장합니다.
- 목록 화면이 열리면 위쪽 진행 카드에서 자막 받기 → 교정·교열 → 목차 → 용어집 → FAQ 순서로 진행되는 것을 함께 봅니다.

### 3) 화면 둘러보기 (10분)
- 목록: 분야 필터, 모든 강의 검색 → 결과를 누르면 그 장면부터 열림
- 강의: 유튜브 재생, 전사 문장 클릭으로 이동, 목차·노트·용어집·FAQ 탭, 단축키(J/K/L 10초 이동·재생/정지, 1~9 대목차)

### 4) 질문하기 (5분)
- 강의 화면 [이 강의에 질문하기] → 대화창에 붙여 넣고 질문을 이어 씀 → 답의 근거 장면 링크를 눌러 확인

### 5) 공개 데모 보기
- https://video-library-production-8b85.up.railway.app — 같은 화면을 인터넷에 공개한 예(관리자가 [공개]한 강의만 보임)

## 자주 막히는 곳
| 증상 | 해결 |
|---|---|
| 자막 받기 실패(403) | `python -m pip install --user -U "yt-dlp[default]"`로 yt-dlp 업데이트 후 다시 |
| "자막이 없습니다" | 자막이 있는 영상으로 바꿈 |
| 화면이 안 열림 / "미니 서버가 꺼졌습니다" | `문서/영상자료실`의 「영상자료실 열기」 더블클릭 |
| PowerShell에서 한글이 깨짐 | 같은 줄 맨 앞에 `[Console]::OutputEncoding=[Text.UTF8Encoding]::new();` |
| Mac에서 `python`이 없음 | `python3` 사용 |

## 정리
- 처리한 강의는 그 PC의 `문서/영상자료실`에만 남습니다(다른 사람 서버로 가지 않음).
- 플러그인 제거: Claude Code `claude plugin uninstall video-library@video-library` → `claude plugin marketplace remove video-library`, Codex `codex plugin remove video-library@video-library` → `codex plugin marketplace remove video-library`. 제거해도 `문서/영상자료실` 폴더는 남습니다.
