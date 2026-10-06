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
