# video-library (영상자료실)

유튜브 강의 링크 하나를 주면 자막을 받아 **오전사 교정·교열**을 하고, **목차·요약·용어집·FAQ**와 (외국어 영상이면) **한국어 번역**을 만들어 내 PC의 `문서/영상자료실`에 쌓아 주는 **Claude Code·Codex 플러그인**입니다. 쌓인 강의는 내 PC 전용 화면에서 영상과 함께 보고, 모든 강의를 검색하고, AI에게 강의 내용을 물어볼 수 있습니다.

- 공개 데모(데모 강의 1편, 읽기 전용): https://video-library-production-8b85.up.railway.app
- 1:1 수업 안내서: [docs/ta-guide.md](docs/ta-guide.md)

## 할 수 있는 것
- 자막 받기(yt-dlp 파이썬 라이브러리) → 전체 맥락 파악 → 맥락 기반 오전사 교정 → 띄어쓰기·맞춤법·문장부호 교열. 내용은 바꾸지 않으며, 바꾼 곳은 검사기가 확인합니다.
- 2단 목차와 요약, 언급 자료, 비전문가용 용어집(비유, "영상 속 주장" 구분), 예상 질문 FAQ(근거 장면 포함)
- 외국어 영상은 한국어 번역을 자동으로, 한국어 영상의 영어 번역은 요청할 때만 만듭니다.
- 영상자료실 화면: 썸네일 목록·분야 필터·통합 검색, 유튜브 재생과 전사 따라가기, 장면 이동, 복사, 처리 진행 카드
- 대화창 질문: 영상자료실의 강의를 근거 장면 링크와 함께 답합니다.
- (선택) 내 Railway 서버로 올려 [공개]한 강의만 인터넷에 보여 줍니다.

자막이 없는 영상은 처리하지 않습니다. 영상 파일은 받지 않습니다.

## 준비물
| 항목 | 설명 |
|---|---|
| Claude Code 또는 Codex | 플러그인을 실행할 AI 도구 |
| Python 3.10 이상 | Windows는 `python`, Mac은 `python3`. 없으면 https://www.python.org/downloads/ (Windows는 설치 때 **Add python.exe to PATH** 체크, Mac 기본 python3는 3.9라 python.org 설치 파일 사용) |
| yt-dlp | `python -m pip install --user -U "yt-dlp[default]"` |
| Node.js 또는 deno | 유튜브 자막을 받을 때 yt-dlp가 사용 |

처음 실행하면 플러그인이 `doctor`로 환경을 점검하고, 빠진 것이 있으면 설치 명령을 보여 준 뒤 **승인을 받고** 설치합니다.

## 설치
### Claude Code
```bash
claude plugin marketplace add cattysue/video-library
claude plugin install video-library@video-library
```
대화창 안에서는 `/plugin marketplace add cattysue/video-library`, `/plugin install video-library@video-library`로도 됩니다.

### Codex
```bash
codex plugin marketplace add cattysue/video-library
codex plugin add video-library@video-library
```
Codex 앱에서는 플러그인 목록(`/plugins`)에서도 설치할 수 있습니다. 설치 뒤 Codex를 다시 시작하세요. Codex는 처음 실행할 때 인터넷 사용·문서 폴더에 파일 쓰기 허락을 물을 수 있습니다(허락해야 자막을 받고 저장합니다).

## 사용법
| 하고 싶은 일 | Claude Code | Codex |
|---|---|---|
| 영상 정리 | `/video-library:video-library <유튜브 링크>` | `$video-library <유튜브 링크>` |
| 한국어 영상 + 영어 번역 | 링크 뒤에 "영어 번역도 해줘" | 같음 |
| 영상자료실 열기 | "영상자료실 열어줘" | 같음 |
| 강의에 질문 | 강의 화면 [이 강의에 질문하기]가 복사한 문장 뒤에 질문 | 같음 |
| 나중에 영어 번역 | 강의 화면 [영어 번역 요청]이 복사한 문장(`video-library 번역 <영상ID>`) | 같음 |

명령 대신 "video-library로 이 영상 정리해줘 <링크>"처럼 말해도 됩니다. 처리 중에는 목록 화면 위쪽 진행 카드에 단계가 보입니다. 참고 실측: 22~38분 영상 한 편에 약 6분, 구독 사용량 약 13~15만 토큰(영상마다 다름).

## 결과가 쌓이는 곳
`문서/영상자료실/`(환경변수 `VL_HOME`으로 바꿀 수 있음)
- `영상자료실 열기.bat`(Windows) / `영상자료실 열기.command`(Mac): 더블클릭하면 화면이 열립니다.
- `lectures/<영상ID>/`: 강의 하나(`lecture.json`과 전사 파일)
- `app/`: 화면 파일(실행할 때 자동 갱신)

화면은 내 PC 전용 미니 서버(`127.0.0.1`)로 열리며, 1시간 동안 쓰지 않으면 스스로 꺼집니다. 꺼진 뒤에는 「영상자료실 열기」를 다시 더블클릭하세요.

## (선택) 내 Railway 서버로 공개하기
Railway 계정과 [Railway CLI](https://docs.railway.com/cli)가 필요하고, 사용량만큼 요금이 나옵니다. 이 저장소를 내려받은(`git clone`) 폴더에서:
```bash
railway init --name video-library
railway add --service video-library
railway volume add --mount-path /data
railway variable set RAILWAY_DOCKERFILE_PATH=railway/Dockerfile --service video-library --skip-deploys
railway domain --service video-library
```
Git Bash에서는 `/data`가 Windows 경로로 바뀌지 않게 앞에 `MSYS_NO_PATHCONV=1 `을 붙입니다. 그다음 **PowerShell 또는 Mac 터미널에서 직접** 관리자 비밀번호를 정하고(화면에 보이지 않게 입력), 배포합니다:
```bash
python plugin/video-library/skills/video-library/scripts/vl.py connect https://<내 공개 주소> --service video-library
railway up --service video-library --detach
```
이후 처리하는 강의는 자동으로 올라갑니다(처음에는 비공개). 공개 주소에서 [관리자]로 로그인해 [비공개]를 누르면 공개됩니다. 이미 있는 강의는 `vl.py upload --video <영상ID>`로 올립니다.

## 안전과 저작권
- 관리자 비밀번호와 업로드 토큰은 AI에게 알려 주지 마세요. `vl.py connect`가 보이지 않게 입력받고, Railway에는 해시만 저장합니다.
- 다른 사람의 영상 전사를 공개하지 마세요. Railway에는 [공개]로 바꾼 강의만 보입니다.
- 이 저장소의 테스트 자료는 직접 쓴 샘플입니다.

## 개발
- 테스트: `python -m pip install -r requirements-dev.txt` 후 `python -m pytest -W error`
- 설계·구현 계획·진행 기록: `docs/superpowers/`, API: `docs/api.md`

## 라이선스
MIT. 화면 구성 아이디어는 kuntae802/lecture-pipeline을 참고했고, 코드는 새로 작성했습니다.
