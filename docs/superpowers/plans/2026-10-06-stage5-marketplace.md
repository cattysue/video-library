# video-library 5단계(마켓플레이스·설치 안내서·공개 저장소) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `plugin-app`을 공개 GitHub 저장소 `cattysue/video-library`로 올려, 누구나 Claude Code·Codex에서 마켓플레이스로 `video-library` 플러그인을 설치하고 README·1:1 수업 안내서만 보고 쓸 수 있게 한다(과제 체크리스트 ①·②, ③은 4단계 Railway 주소).

**Architecture:** 저장소 맨 위가 두 도구의 마켓플레이스다 — Claude Code는 `.claude-plugin/marketplace.json`, Codex는 `.agents/plugins/marketplace.json`이 같은 플러그인 폴더 `./plugin/video-library`를 가리키고, 그 폴더에 도구별 매니페스트(`.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`)와 기존 `skills/video-library/`가 있다. 플러그인으로 설치하면 Claude Code 명령은 `/video-library:video-library`가 되므로, 화면이 복사해 주는 요청 문장은 슬래시 없는 평문(`video-library 번역 <ID>`)으로 바꿔 두 도구 모두에서 스킬 설명으로 호출되게 한다. 공개 전에 개인 정보(경로·이메일)와 다른 사람 영상 정보를 문서에서 지우고 자동 검사로 막은 뒤, 공개 저장소는 GitHub 비공개 이메일(noreply)로 만든 **새 기록 하나**로 시작한다(기존 기록은 이 PC의 백업 브랜치에만).

**Tech Stack:** JSON 매니페스트, Markdown 문서, Python 3.10+ pytest(문서·매니페스트 검사), Claude Code CLI 2.1.x(`claude plugin validate|marketplace add|install|list`), Codex CLI 0.155(`codex plugin marketplace add`, `codex plugin add`), GitHub CLI(`gh repo create`), Railway CLI(재배포).

**Spec:** [docs/superpowers/specs/2026-10-05-video-library-design.md](../specs/2026-10-05-video-library-design.md) — 3장 저장소 구성(마켓플레이스 파일 위치), 8.3·8.4(비밀 값·공개 저장소에 남의 영상 내용 금지), 9장 5겹(설치), 10장 5단계, 12장 미확인(Codex 형식·저장소 이름). 공식 문서 확인(10-06): Claude Code [Create a marketplace](https://code.claude.com/docs/en/plugin-marketplaces)·[Create a plugin](https://code.claude.com/docs/en/plugins/create), Codex [Build plugins](https://developers.openai.com/plugins/build/plugins).

## 사용자 결정 (10-06)
- 저장소 `cattysue/video-library`, 공개. 라이선스 MIT.
- 커밋 기록: 공개 저장소는 **새 기록**으로 시작, 앞으로 커밋 작성자 이메일은 GitHub noreply(`172098846+cattysue@users.noreply.github.com`). 기존 기록(작성자 이메일 포함)은 이 PC의 `private-history` 브랜치에만 둔다.
- `docs/`(설계·계획·기록)는 개인 경로·다른 분 영상 정보를 지우고 포함.
- 영어 번역은 지금처럼 요청할 때만.

## Global Constraints

- 명령은 `plugin-app/` 폴더에서 실행한다. `SKILL_DIR` = `plugin/video-library/skills/video-library`, `TESTS` = `SKILL_DIR/tests`.
- 플러그인 이름·마켓플레이스 이름은 둘 다 `video-library`(설치 id `video-library@video-library`). 마켓플레이스 항목 이름과 각 `plugin.json`의 `name`은 반드시 같다. `source` 경로는 마켓플레이스 루트 기준 `./plugin/video-library`(`..` 금지).
- 버전 `1.0.0`을 Claude·Codex 매니페스트에 같게 둔다.
- 공개 저장소에 들어가면 안 되는 것: 내 PC 경로(사용자 폴더·파이썬 설치 경로), 개인 이메일, Railway 프로젝트·서비스 ID, 다른 분 영상의 ID·제목·자막 문장, 토큰·비밀번호·해시. 사용 허락을 받은 데모 영상(`40JNj2zjnQc`, 바이브코딩대학)과 공개 주소(`https://video-library-production-8b85.up.railway.app`)는 넣어도 된다.
- 화면 복사 문구: [영어 번역 요청] → `video-library 번역 <ID>`(슬래시 없음, **이번 단계에서 바꿈**), 안내 "요청 문장을 복사했습니다. video-library 플러그인이 설치된 AI 도구의 대화창에 붙여 넣으세요."는 그대로. [이 강의에 질문하기]는 그대로.
- 호출 표기: Claude Code `/video-library:video-library <링크>`, Codex `$video-library <링크>`, 두 도구 공통 평문 "video-library로 이 영상 정리해줘 <링크>".
- 공개 저장소 만들기(`gh repo create`·push), Railway 재배포, 사용자 PC의 Claude Code·Codex 설정을 바꾸는 설치(`marketplace add`·`install`)는 **단계마다 사용자 승인**. 로컬 `main` 교체(Task 5)는 백업 브랜치를 먼저 만든다.
- 테스트는 인터넷을 쓰지 않는다(conftest 가드 유지). 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **다른 PC에서 GitHub 마켓플레이스로 설치할 때 경로·이름이 어긋나는 경우** — 항목 이름≠매니페스트 이름이면 "not found", 상대 경로가 틀리면 "Source path does not exist". → Task 1 테스트 + `claude plugin validate` + Task 7 실제 설치.
2. **설치한 사용자가 화면에서 복사한 요청을 붙여 넣는 경우** — 슬래시 명령이 없는 이름이면 Claude Code가 받지 못한다. 평문이 스킬 설명에 걸려 실행돼야 한다. → Task 2 테스트 + Task 7 실제 확인.
3. **공개 저장소·기록에 개인 정보나 남의 영상 내용이 섞이는 경우** — 파일과 커밋 작성자 이메일 모두. → Task 4 검사 테스트 + Task 5 작성자 확인.
4. **파이썬·yt-dlp·node가 없는 새 PC(조교)** — README와 안내서가 준비물과 `doctor` 점검·승인 설치 흐름을 알려야 한다. → Task 3 테스트.
5. **Mac 사용자** — `python3`, `.command` 열기 파일을 안내해야 한다. → Task 3 테스트.

---

## File Structure

| 파일 | 책임 |
|---|---|
| `.claude-plugin/marketplace.json` (새) | Claude Code 마켓플레이스 목록 |
| `.agents/plugins/marketplace.json` (새) | Codex 마켓플레이스 목록 |
| `plugin/video-library/.claude-plugin/plugin.json` (새) | Claude Code 플러그인 매니페스트 |
| `plugin/video-library/.codex-plugin/plugin.json` (새) | Codex 플러그인 매니페스트 |
| `SKILL_DIR/web/lecture.js`, `library.html`, `SKILL_DIR/SKILL.md` (수정) | 슬래시 없는 요청 문장, 설치 후 호출 표기 |
| `README.md`, `LICENSE`, `docs/ta-guide.md`, `.railwayignore` (새) | 설치·사용 안내, MIT, 1:1 수업 안내서, Railway 업로드 제외 |
| `docs/superpowers/evidence/*.md`, `docs/superpowers/plans/2026-10-06-stage4-railway.md`, `docs/superpowers/specs/…design.md` (수정) | 개인 경로·남의 영상 정보 정리, 12장 미확인 해소 |
| `TESTS/test_marketplace.py`, `TESTS/test_public_docs.py`, `TESTS/test_public_hygiene.py` (새), `TESTS/test_web_assets.py`·`test_skill_doc.py` (수정) | 검사 |

---

### Task 1: 마켓플레이스·플러그인 매니페스트

**Files:**
- Create: `.claude-plugin/marketplace.json`, `.agents/plugins/marketplace.json`, `plugin/video-library/.claude-plugin/plugin.json`, `plugin/video-library/.codex-plugin/plugin.json`
- Test: `TESTS/test_marketplace.py`

**Interfaces:**
- Produces: 설치 id `video-library@video-library`(두 도구), 플러그인 루트 `plugin/video-library`, 스킬 `skills/video-library/SKILL.md`.

- [ ] **Step 1: Write the failing test**

`TESTS/test_marketplace.py`:

```python
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]  # plugin-app/
PLUGIN = ROOT / "plugin" / "video-library"


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_claude_marketplace_points_at_plugin():
    m = load(".claude-plugin/marketplace.json")
    assert m["name"] == "video-library" and m["owner"]["name"]
    (entry,) = m["plugins"]
    assert entry["name"] == "video-library" and entry["source"] == "./plugin/video-library"
    assert ".." not in entry["source"] and (ROOT / entry["source"]).is_dir()
    assert entry["description"]


def test_codex_marketplace_points_at_plugin():
    m = load(".agents/plugins/marketplace.json")
    assert m["name"] == "video-library" and m["interface"]["displayName"]
    (entry,) = m["plugins"]
    assert entry["name"] == "video-library"
    assert entry["source"] == {"source": "local", "path": "./plugin/video-library"}
    assert entry["policy"] == {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}


def test_manifests_agree():
    claude = load("plugin/video-library/.claude-plugin/plugin.json")
    codex = load("plugin/video-library/.codex-plugin/plugin.json")
    for manifest in (claude, codex):
        assert manifest["name"] == "video-library"
        assert manifest["version"] == "1.0.0"
        assert manifest["license"] == "MIT"
        assert manifest["repository"] == "https://github.com/cattysue/video-library"
        assert manifest["description"] and manifest["author"]["name"]
    assert claude["description"] == codex["description"]


def test_skill_lives_where_both_tools_look():
    skill = PLUGIN / "skills" / "video-library" / "SKILL.md"
    assert skill.is_file() and skill.read_text(encoding="utf-8").startswith("---\nname: video-library\n")
    assert not (PLUGIN / ".claude-plugin" / "skills").exists()  # skills/ 는 매니페스트 폴더 밖
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -W error plugin/video-library/skills/video-library/tests/test_marketplace.py`
Expected: FAIL — `FileNotFoundError: …\.claude-plugin\marketplace.json`

- [ ] **Step 3: Write minimal implementation**

`.claude-plugin/marketplace.json`:

```json
{
  "name": "video-library",
  "description": "유튜브 강의를 교정·정리해 내 PC의 영상자료실에 쌓는 플러그인",
  "owner": {
    "name": "cattysue",
    "url": "https://github.com/cattysue"
  },
  "plugins": [
    {
      "name": "video-library",
      "source": "./plugin/video-library",
      "description": "유튜브 링크 하나로 자막 오전사 교정·교열, 목차·요약·용어집·FAQ·번역을 만들어 영상자료실(내 PC)에 쌓고 화면으로 본다"
    }
  ]
}
```

`.agents/plugins/marketplace.json`:

```json
{
  "name": "video-library",
  "interface": {
    "displayName": "video-library (영상자료실)"
  },
  "plugins": [
    {
      "name": "video-library",
      "source": {
        "source": "local",
        "path": "./plugin/video-library"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

`plugin/video-library/.claude-plugin/plugin.json`:

```json
{
  "name": "video-library",
  "version": "1.0.0",
  "description": "유튜브 링크 하나로 자막 오전사 교정·교열, 목차·요약·용어집·FAQ·번역을 만들어 영상자료실(내 PC)에 쌓고 화면으로 본다",
  "author": {
    "name": "cattysue",
    "url": "https://github.com/cattysue"
  },
  "homepage": "https://github.com/cattysue/video-library",
  "repository": "https://github.com/cattysue/video-library",
  "license": "MIT",
  "keywords": ["youtube", "lecture", "transcript", "korean", "study"]
}
```

`plugin/video-library/.codex-plugin/plugin.json`:

```json
{
  "name": "video-library",
  "version": "1.0.0",
  "description": "유튜브 링크 하나로 자막 오전사 교정·교열, 목차·요약·용어집·FAQ·번역을 만들어 영상자료실(내 PC)에 쌓고 화면으로 본다",
  "author": {
    "name": "cattysue",
    "url": "https://github.com/cattysue"
  },
  "homepage": "https://github.com/cattysue/video-library",
  "repository": "https://github.com/cattysue/video-library",
  "license": "MIT",
  "keywords": ["youtube", "lecture", "transcript", "korean", "study"]
}
```

- [ ] **Step 4: Run test to verify it passes, then the official validator**

Run: `python -m pytest -W error plugin/video-library/skills/video-library/tests/test_marketplace.py`
Expected: PASS

Run: `claude plugin validate ./plugin/video-library` 그리고 `claude plugin validate .`
Expected: 두 번 모두 마지막 줄 `✔ Validation passed`(경고가 있으면 증거에 적고, 알 수 없는 필드 경고면 그 필드를 뺀다)

Run: `claude --plugin-dir ./plugin/video-library plugin list`
Expected: `video-library` 가 loaded 로 보인다(설정 파일을 바꾸지 않는 한 번짜리 확인). 출력 형식이 다르면 `claude plugin list --help`로 확인해 증거에 적는다.

- [ ] **Step 5: Commit**

```bash
git add .claude-plugin .agents plugin/video-library/.claude-plugin plugin/video-library/.codex-plugin plugin/video-library/skills/video-library/tests/test_marketplace.py
git commit -m "feat(stage5): claude and codex marketplace and plugin manifests" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: 설치 후에도 통하는 요청 문장

**Files:**
- Modify: `SKILL_DIR/web/lecture.js`(번역 요청 복사 문구), `SKILL_DIR/web/library.html`(빈 목록 안내), `SKILL_DIR/SKILL.md`(설명문·나중 요청 절)
- Test: `TESTS/test_web_assets.py`, `TESTS/test_skill_doc.py`

**Interfaces:**
- Produces: 복사 문구 `video-library 번역 <ID>`, SKILL 설명문의 호출 표기 `/video-library:video-library <링크>`·`$video-library <링크>`·평문 요청.

- [ ] **Step 1: Write the failing test**

`TESTS/test_web_assets.py`의 `test_lecture_page_buttons_and_messages`에서 줄 `assert "/video-library 번역 " in js`를 다음 두 줄로 바꾼다:

```python
    assert "`video-library 번역 ${lectureId}`" in js  # 설치한 Claude Code 에서는 /video-library 가 없는 명령이라 평문으로
    assert "/video-library 번역" not in js
```

파일 끝에 추가:

```python
def test_empty_library_shows_installed_command_names():
    page = read("library.html")
    assert "/video-library:video-library" in page and "$video-library" in page
```

`TESTS/test_skill_doc.py` 끝에 추가:

```python
def test_plain_requests_and_plugin_command_names():
    body = text()
    description = body.split("\n")[2]
    assert "/video-library:video-library <링크>" in description and "$video-library <링크>" in description
    assert '"video-library 번역 <ID>"' in description or "video-library 번역 <영상ID>" in description
    assert "`/video-library 번역" not in body and "`/video-library 열기" not in body and "`/video-library 업로드" not in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -W error plugin/video-library/skills/video-library/tests/test_web_assets.py plugin/video-library/skills/video-library/tests/test_skill_doc.py`
Expected: FAIL — 세 테스트(복사 문구, 빈 목록 안내, SKILL 표기)

- [ ] **Step 3: Write minimal implementation**

`SKILL_DIR/web/lecture.js` — 번역 요청 줄:

```javascript
    $("#request-en").addEventListener("click", () => VL.copy(`video-library 번역 ${lectureId}`, REQUEST_MESSAGE));
```

`SKILL_DIR/web/library.html` — `#empty` 문단:

```html
  <p id="empty" class="empty" hidden>아직 강의가 없습니다. Claude Code에서는 <code>/video-library:video-library &lt;유튜브 링크&gt;</code>, Codex에서는 <code>$video-library &lt;유튜브 링크&gt;</code>를 입력하거나, 대화창에 “video-library로 이 영상 정리해줘 &lt;링크&gt;”라고 쓰세요.</p>
```

`SKILL_DIR/SKILL.md`:
1. 설명문(3번째 줄)의 앞부분 `Claude Code에서는 /video-library <링크>, Codex에서는 $video-library <링크>로 호출한다. "video-library 번역 <영상ID>"(한국어 강의의 영어 번역 추가) 요청도 이 스킬로 처리한다.`를 다음으로 바꾼다(뒤의 열기·질문·업로드 문장은 그대로):

```text
Claude Code에서는 /video-library:video-library <링크>, Codex에서는 $video-library <링크>로 호출하고, "video-library로 이 영상 정리해줘 <링크>"처럼 평문으로 요청해도 된다. "video-library 번역 <영상ID>"(한국어 강의의 영어 번역 추가) 요청도 이 스킬로 처리한다.
```

2. 본문의 요청 예시 세 곳을 평문으로 바꾼다:
   - `사용자가 \`/video-library 열기\`(또는 "영상자료실 열어줘")를 요청하면` → `사용자가 "영상자료실 열어줘"(또는 "video-library 열기")를 요청하면`
   - `사용자가 \`/video-library 업로드 <ID>\`(또는 "video-library 업로드 <ID>")를 요청하면` → `사용자가 "video-library 업로드 <ID>"를 요청하면`
   - `사용자가 \`/video-library 번역 <ID>\`(또는 "video-library 번역 <ID>")를 요청하면` → `사용자가 "video-library 번역 <ID>"(강의 화면 [영어 번역 요청]이 복사해 주는 문장)를 요청하면`

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -W error plugin/video-library/skills/video-library/tests`
Expected: PASS (전부)

- [ ] **Step 5: Commit**

```bash
git add plugin/video-library/skills/video-library
git commit -m "feat(stage5): plain-text requests that work after plugin install" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: README·LICENSE·1:1 수업 안내서·Railway 업로드 제외

**Files:**
- Create: `README.md`, `LICENSE`, `docs/ta-guide.md`, `.railwayignore`
- Test: `TESTS/test_public_docs.py`

**Interfaces:**
- Consumes: Task 1 설치 id, Task 2 호출 표기, 4단계 공개 주소.

- [ ] **Step 1: Write the failing test**

`TESTS/test_public_docs.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]  # plugin-app/


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_readme_install_for_both_tools():
    text = read("README.md")
    for needle in ("claude plugin marketplace add cattysue/video-library", "claude plugin install video-library@video-library",
                   "codex plugin marketplace add cattysue/video-library", "codex plugin add video-library@video-library",
                   "/video-library:video-library", "$video-library"):
        assert needle in text, needle


def test_readme_covers_new_pc_and_mac():
    text = read("README.md")
    for needle in ("Python 3.10", "yt-dlp", "Node.js", "deno", "doctor", "승인", "python3", "영상자료실 열기.command"):
        assert needle in text, needle


def test_readme_links_demo_guide_and_license():
    text = read("README.md")
    assert "https://video-library-production-8b85.up.railway.app" in text
    assert "docs/ta-guide.md" in text and "MIT" in text
    assert "vl.py connect" in text and "railway up" in text  # 선택: 내 Railway 서버


def test_license_is_mit():
    text = read("LICENSE")
    assert text.startswith("MIT License") and "cattysue" in text


def test_ta_guide_steps():
    text = read("docs/ta-guide.md")
    for needle in ("설치", "영상 하나 처리", "화면 둘러보기", "질문", "자주 막히는 곳", "제거"):
        assert needle in text, needle


def test_railway_upload_skips_private_workspace():
    lines = read(".railwayignore").split()
    assert ".superpowers" in lines and "docs" in lines
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -W error plugin/video-library/skills/video-library/tests/test_public_docs.py`
Expected: FAIL — `FileNotFoundError: …README.md`

- [ ] **Step 3: Write minimal implementation**

`LICENSE`:

```text
MIT License

Copyright (c) 2026 cattysue

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

`.railwayignore`:

```text
.git
.superpowers
docs
**/__pycache__
**/tests
```

`README.md`:

````markdown
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
| Python 3.10 이상 | Windows는 `python`, Mac은 `python3` |
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
Codex 앱에서는 플러그인 목록(`/plugins`)에서도 설치할 수 있습니다. 설치 뒤 Codex를 다시 시작하세요.

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
````

`docs/ta-guide.md`:

```markdown
# 1:1 수업 안내서 — video-library 써 보기 (약 30~40분)

조교(또는 수강생) PC에서 플러그인을 설치하고 영상 하나를 처리해 화면으로 보는 데까지 함께 해 보는 순서입니다.

## 수업 전 확인
1. Claude Code 또는 Codex에 로그인되어 있는지
2. 인터넷 연결
3. 10분 안팎의 **자막이 있는** 한국어 강의 링크 하나(공개 데모와 같은 바이브코딩대학 강의 추천)

## 순서
### 1) 설치 (5분)
- Claude Code: `claude plugin marketplace add cattysue/video-library` → `claude plugin install video-library@video-library`
- Codex: `codex plugin marketplace add cattysue/video-library` → `codex plugin add video-library@video-library` → Codex 다시 시작

### 2) 영상 하나 처리 (10~15분)
- Claude Code: `/video-library:video-library <링크>` / Codex: `$video-library <링크>`
- 첫 단계에서 환경 점검(`doctor`)이 돌아갑니다. Python·yt-dlp·Node.js가 없으면 설치 명령이 나오고, **승인하면** 설치합니다.
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
- 플러그인 제거: Claude Code `claude plugin uninstall video-library@video-library`, Codex `codex plugin remove video-library@video-library`
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -W error plugin/video-library/skills/video-library/tests/test_public_docs.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md LICENSE docs/ta-guide.md .railwayignore plugin/video-library/skills/video-library/tests/test_public_docs.py
git commit -m "docs(stage5): README, MIT license, 1:1 class guide, railway ignore" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: 공개 전 문서 정리 + 자동 검사

**Files:**
- Modify: `docs/superpowers/evidence/2026-10-05-stage2-pipeline.md`, `docs/superpowers/evidence/2026-10-06-stage3-viewer.md`, `docs/superpowers/evidence/2026-10-06-stage4-railway.md`, `docs/superpowers/plans/2026-10-06-stage4-railway.md`, `docs/superpowers/specs/2026-10-05-video-library-design.md`(12장)
- Test: `TESTS/test_public_hygiene.py`

**Interfaces:**
- Produces: `git ls-files`의 모든 글 파일이 개인 정보·남의 영상 정보 없이 통과.

- [ ] **Step 1: Write the failing test**

`TESTS/test_public_hygiene.py`:

```python
"""공개 저장소에 넣으면 안 되는 것을 막는다.
- 공개 파일에는 '모양' 규칙만 둔다(PC 경로, 개인 메일 주소, UUID 형태의 서비스 ID, 해시 값 모양).
- 구체적인 값(다른 분 영상 ID·이름, 서비스 ID 등)은 이 PC 전용 `.superpowers/hygiene-denylist.txt`에만 두고(공개 안 함),
  있으면 아래 test_local_denylist_even_when_split 가 조각낸 표기까지 확인한다."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]  # plugin-app/
TEXT = {".md", ".py", ".js", ".html", ".css", ".json", ".txt", ".ini", ".toml", "", ".yml", ".yaml",
        ".json3", ".bat", ".sh", ".command"}
FORBIDDEN = [
    r"[A-Za-z]:\\" + r"Users\\", r"/c/" + r"Users/", r"[A-Za-z]:\\" + r"Python\d",  # 내 PC 경로
    r"[\w.+-]+@(naver|gmail|daum|hanmail|kakao)\.(com|net)",  # 개인 메일 주소
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",  # 서비스 ID(UUID)
    r"pbkdf2_sha256\$\d+\$[0-9a-f]{8}",  # 실제 해시 값 모양
]


def tracked_text_files():
    names = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                           check=True).stdout.split("\n")
    for name in filter(None, names):
        path = ROOT / name
        if path.suffix.lower() in TEXT and path.is_file() and path.name != Path(__file__).name:
            yield name, path.read_text(encoding="utf-8", errors="replace")


def test_no_private_or_third_party_content_in_public_files():
    hits = []
    for name, text in tracked_text_files():
        for pattern in FORBIDDEN:
            for m in re.finditer(pattern, text):
                line = text.count("\n", 0, m.start()) + 1
                hits.append(f"{name}:{line}: {pattern}")
    assert not hits, "\n".join(hits)


def test_spec_open_items_resolved():
    spec = (ROOT / "docs/superpowers/specs/2026-10-05-video-library-design.md").read_text(encoding="utf-8")
    assert "공식 문서 확인(10-06)" in spec and "cattysue/video-library" in spec
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -W error plugin/video-library/skills/video-library/tests/test_public_hygiene.py`
Expected: FAIL — 증거·계획 문서의 걸린 줄 목록(PC 경로 2곳, 이 PC 전용 금지 목록에 걸리는 다른 분 영상 정보) + 설계서 12장 단언

- [ ] **Step 3: Write minimal implementation** — 걸린 줄을 **줄 전체** 아래 새 문장으로 바꾼다(지울 원래 문자열을 이 계획서에 다시 적지 않는다)

`docs/superpowers/evidence/2026-10-05-stage2-pipeline.md` 9줄(사용자 승인 후 설치):

```markdown
- 사용자 승인 후 설치: `python -m pip install --user -U "yt-dlp[default]"` → yt-dlp 2026.8.19, yt-dlp-ejs 0.8.0. 자바스크립트 실행기는 이미 있던 node 사용(deno 없음).
```

`docs/superpowers/evidence/2026-10-06-stage3-viewer.md`:
- 47줄(열기 파일 내용):

```markdown
`영상자료실 열기.bat` 내용: `"<파이썬 경로>" "%~dp0app\runtime\vl.py" open` ✓. 더블클릭 실행은 사용자 화면에서 브라우저가 열리는 동작이라 **미확인**(사용자 확인 요청).
```

- 55~57줄(영상 3편 표의 세 행):

```markdown
| 영상 A(영어 과학) | 영어·사람 자막 | 22분 | 164·2 | 10건 | 8/24 | 18(3) | 10 | 영어→한국어 164문장 | 1회(교정 조각02의 from·to 20자 초과) | 127,348 토큰 | 약 6분 |
| 영상 B(한국어 금융) | 한국어·자동 | 27분 | 447·3 | 55건 | 7/31 | 26(23) | 10 | — | 0회 | 145,802 토큰 | 약 6분 |
| 영상 C(한국어 의학) | 한국어·자동 | 22분 | 266·2 | 67건 | 9/25 | 20(18) | 10 | — | 0회 | 136,272 토큰 | 약 6분 |
```

- 61줄(대화창 질문용 검색):

```markdown
- 대화창 질문용 검색: `vl.py search "<핵심어>"`·`vl.py search "<핵심어>" --field science`가 강의별 장면과 바로 열리는 링크를 출력 ✓(실제 검색어는 공개 문서에서 생략).
```

- 65줄(관찰 2):

```markdown
2. **검사기 규칙에 막힌 정당한 교정** — 약어 끝 글자 빠짐, 단어 중간 글자 빠짐, 띄어쓰기로 갈라진 낱말, 영어 단어 끝 덧붙음 등 5건(실제 자막 문장은 공개 문서에서 생략). 순수 덧붙이기·지우기는 맥락표 `heard_as`에 있고 **같은 단어 수·단어 안 1~2글자·숫자/부정어 없음**일 때만 예외로 통과한다(2단계 검토에서 의도적으로 좁힌 규칙). **정정(최종 검토):** 처음에 "heard_as에 넣도록 안내하면 줄어든다"고 적었으나 틀렸다. 3글자 이상을 덧붙이거나 단어 수가 바뀌는 교정은 heard_as에 있어도 여전히 불합격이다. 현재 설계에서는 이런 오류를 고치지 않고 보고하는 것이 맞는 동작이다.
```

`docs/superpowers/evidence/2026-10-06-stage4-railway.md`의 "7 손님 화면 확인" 행:

```markdown
| 7 손님 화면 확인 (내장 브라우저, 로그아웃) | 목록: 데모 1편, 관리자 단추 없음, 진행 카드 없음 ✓ / 올리지 않은 강의 ID 404, `/api/jobs` 401 ✓ / 검색 `꺾쇠` → 데모 15건 ✓ / 강의 화면 `t=113`: 유튜브 플레이어, 1:53 "우선 어 꺾쇠가 등장을 합니다." 강조, 전사 434문장, 목차 32, [원문(KO)·번역(EN)·나란히], [이 강의에 질문하기]·[영어 번역 요청] 숨김, 서버 끊김 안내 없음 ✓ / 콘솔 오류는 제가 확인용으로 부른 404·401 두 건뿐 |
```

`docs/superpowers/plans/2026-10-06-stage4-railway.md` Task 11 Step 7 줄:

```markdown
- [ ] **Step 7:** 9장 3·4겹 확인(내장 브라우저, 로그아웃 상태): 목록에 데모 1편, 유튜브 재생·목차 이동·검색→장면 이동·복사·좁은 화면·어두운 모드, AI 도구용 버튼 숨김, `/api/lectures/<올리지 않은 ID>` 404, `/api/jobs` 401, 콘솔 오류 없음. 사용자 승인 후 짧은 영상으로 처리 1회를 돌려 관리자 화면에서 진행 카드가 보이는지(선택).
```

`docs/superpowers/specs/2026-10-05-video-library-design.md` 12장 표에서 "Codex 마켓플레이스 형식" 행과 "공개 GitHub 계정·저장소 이름" 행을 각각 아래로 바꾼다:

```markdown
| Codex 마켓플레이스 형식(`.agents/plugins/marketplace.json`, `.codex-plugin/plugin.json`) | 공식 문서 확인(10-06): Codex는 `codex plugin marketplace add owner/repo` → `codex plugin add 이름@마켓`, Claude Code는 플러그인 스킬 이름 앞에 플러그인 이름이 붙음(`/video-library:video-library`) | 5단계 실제 설치로 확인 |
| 공개 GitHub 계정·저장소 이름 | 결정(10-06): `cattysue/video-library`, MIT, 새 기록으로 공개(작성자 noreply) | — |
```

검사 테스트가 다른 줄을 더 잡으면, 같은 원칙(영상은 "영상 A/B/C", 경로는 `<파이썬 경로>`·`<영상자료실>`, 자막 문장은 "공개 문서에서 생략")으로 그 줄을 바꾸고 증거에 적는다.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -W error plugin/video-library/skills/video-library/tests`
Expected: PASS (전부)

- [ ] **Step 5: Commit**

```bash
git add docs plugin/video-library/skills/video-library/tests/test_public_hygiene.py
git commit -m "docs(stage5): scrub local paths and third-party video details before publishing" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: 공개용 새 기록 (내 PC에서만, 백업 먼저)

**Files:** 없음(git 작업). 증거: `docs/superpowers/evidence/2026-10-06-stage5-marketplace.md`(새, 이 Task에서 시작)

- [ ] **Step 1: 작업 브랜치를 `main`에 합치고 백업 브랜치를 만든다**

```bash
git checkout main
git merge --ff-only feat/stage5-marketplace
git branch private-history main
```

Expected: `git log -1 --format=%H private-history` 가 `main`과 같다.

- [ ] **Step 2: 이 저장소의 앞으로 커밋 작성자를 GitHub 비공개 이메일로**

```bash
git config user.name cattysue
git config user.email 172098846+cattysue@users.noreply.github.com
```

(저장소 안 설정만 바꾼다 — 다른 저장소·전역 설정은 그대로.)

- [ ] **Step 3: 새 기록 하나로 `main`을 다시 만든다**

```bash
git checkout --orphan public-main
git add -A
git commit -m "video-library 1.0.0: YouTube lecture library plugin for Claude Code and Codex" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git branch -M public-main main
```

Expected: `git log --format=%ae main` 이 `172098846+cattysue@users.noreply.github.com` 한 줄, `git rev-list --count main` = 1, `git diff private-history main --stat` 출력 없음(내용은 같음).

- [ ] **Step 4: 전체 테스트·검사**

Run: `python -m pytest -W error`
Expected: PASS (전부, `test_public_hygiene` 포함)

- [ ] **Step 5: 증거 문서 시작 + 커밋**

`docs/superpowers/evidence/2026-10-06-stage5-marketplace.md`에 Task 1~5 결과(검사기 출력 마지막 줄, `plugin list` 결과, 새 기록 확인 값)를 적고:

```bash
git add docs/superpowers/evidence/2026-10-06-stage5-marketplace.md
git commit -m "docs(stage5): evidence for manifests, docs and public history" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: GitHub 공개 + Railway 재배포 (단계마다 승인)

- [ ] **Step 1 (승인):** 공개 저장소 만들고 올리기

```bash
gh repo create cattysue/video-library --public --source . --remote origin --description "유튜브 강의를 교정·정리해 내 PC의 영상자료실에 쌓는 Claude Code·Codex 플러그인" --push
```

Expected: `gh repo view cattysue/video-library --json visibility,defaultBranchRef` → `PUBLIC`, `main`. 브라우저로 저장소 첫 화면에 README가 보이는지 확인.

- [ ] **Step 2: 공개 저장소에서 다시 검사**

Run: `gh api repos/cattysue/video-library/commits --jq '.[].commit.author.email'`
Expected: noreply 주소만.

- [ ] **Step 3 (승인):** Railway 재배포(화면 문구 변경 반영, `.railwayignore` 적용) — `railway up --service video-library --detach` → `/api/health` 확인 → 공개 목록에 데모 1편 그대로(볼륨 유지).

- [ ] **Step 4:** 증거 기록 + 커밋 + `git push`.

---

### Task 7: 실제 설치 확인 (사용자 PC 설정이 바뀌므로 승인)

- [ ] **Step 1 (승인):** Claude Code

```bash
claude plugin marketplace add cattysue/video-library
claude plugin install video-library@video-library
claude plugin list
```

Expected: `video-library@video-library` 가 enabled.

- [ ] **Step 2 (승인):** Codex

```bash
codex plugin marketplace add cattysue/video-library
codex plugin add video-library@video-library
codex plugin list
```

Expected: `video-library` 설치됨. 명령 형식이 다르면 `--help`로 맞추고 증거에 적는다.

- [ ] **Step 3 (사용자):** 각 도구에서 **새 대화**를 열어 "영상자료실 열어줘"(Claude Code는 `/video-library:video-library 열기`도) → 영상자료실 화면이 열리는지. Codex는 `$video-library 열기`. 강의 화면 [영어 번역 요청]이 복사한 `video-library 번역 <ID>`를 붙여 넣으면 번역 절차를 시작하겠다고 답하는지(실제 번역은 사용량이 드니 시작 확인 뒤 멈춰도 됨).
- [ ] **Step 4:** 증거·`docs/handoff.md`(§1 5단계 완료, 다음 할 일: 과제 제출·1:1 수업, 사소한 점 정리) 갱신, 커밋, `git push`. 바깥 `바코대AX`의 메모리·CLAUDE.md 안내는 필요할 때만.
