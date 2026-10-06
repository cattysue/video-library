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


LOCAL_DENYLIST = ROOT / ".superpowers" / "hygiene-denylist.txt"  # 이 PC 전용(공개 안 함). 없으면 건너뜀


def test_local_denylist_even_when_split():
    # 구체적인 금지 값은 공개 파일에 적지 않는다 — 조각내 적어도(" + ") 잡는다(검토 C1)
    if not LOCAL_DENYLIST.exists():
        import pytest
        pytest.skip("이 PC 전용 금지 목록 없음")
    values = [v.strip() for v in LOCAL_DENYLIST.read_text(encoding="utf-8").splitlines()
              if v.strip() and not v.startswith("#")]
    names = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                           check=True).stdout.split("\n")
    hits = []
    for name in filter(None, names):
        path = ROOT / name
        if not path.is_file():
            continue
        joined = re.sub(r"""["']\s*\+\s*r?["']""", "", path.read_text(encoding="utf-8", errors="replace"))
        hits += [f"{name}: {v[:2]}…" for v in values if v in joined]
    assert not hits, "\n".join(hits)


def test_no_unprefixed_slash_command_in_user_docs():
    # 설치한 Claude Code 에는 /video-library 가 없다(/video-library:video-library 만 있음, 검토 I4)
    for name in ("plugin/video-library/skills/video-library/SKILL.md", "README.md", "docs/ta-guide.md",
                 "plugin/video-library/skills/video-library/web/library.html",
                 "plugin/video-library/skills/video-library/web/lecture.js"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert not re.search(r"(?<![\w/])/video-library(?![:/.\-\w])", text), name  # 저장소 주소 cattysue/video-library 는 제외


def test_ta_guide_checks_python_before_class():
    guide = (ROOT / "docs/ta-guide.md").read_text(encoding="utf-8")
    assert "python --version" in guide and "python3 --version" in guide and "python.org" in guide
    assert "PATH" in guide
    assert "Python·yt-dlp" not in guide  # 파이썬이 없으면 doctor 가 실행되지 않으므로 doctor 가 설치해 준다고 쓰지 않는다
