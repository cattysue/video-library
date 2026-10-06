import re
import shutil
import subprocess
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parent.parent / "web"
PAIRS = [("library.html", "library.js"), ("lecture.html", "lecture.js")]


def read(name):
    return (WEB / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("html, js", PAIRS)
def test_every_element_id_used_by_js_exists_in_html(html, js):
    used = set(re.findall(r"\$\(\"#([\w-]+)\"\)", read(js)))
    declared = set(re.findall(r'id="([\w-]+)"', read(html)))
    assert used and used <= declared, used - declared


@pytest.mark.parametrize("html, js", PAIRS)
def test_html_loads_shared_files_from_app(html, js):
    page = read(html)
    assert '<link rel="stylesheet" href="/app/app.css">' in page
    assert '<script src="/app/common.js"></script>' in page and f'<script src="/app/{js}"></script>' in page
    assert '<meta name="viewport"' in page and 'lang="ko"' in page


def test_no_inner_html_anywhere():
    for path in WEB.glob("*.js"):
        assert "innerHTML" not in path.read_text(encoding="utf-8"), path.name
        assert "insertAdjacentHTML" not in path.read_text(encoding="utf-8"), path.name


def test_css_has_dark_mode_and_narrow_layout():
    css = read("app.css")
    assert "prefers-color-scheme: dark" in css and "@media (max-width:" in css


@pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
def test_js_syntax():
    for path in WEB.glob("*.js"):
        proc = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr


def test_lecture_page_buttons_and_messages():
    js = read("lecture.js")
    assert "video-library 강의 「" in js and "에 대해 질문: " in js
    assert "`video-library 번역 ${lectureId}`" in js  # 설치한 Claude Code 에서는 /video-library 가 없는 명령이라 평문으로
    assert "/video-library 번역" not in js
    assert "질문 문장을 복사했습니다. video-library 플러그인이 설치된 AI 도구의 대화창에 붙여 넣고 질문을 이어 쓰세요." in js
    assert "요청 문장을 복사했습니다. video-library 플러그인이 설치된 AI 도구의 대화창에 붙여 넣으세요." in js
    assert "https://www.youtube.com/iframe_api" in js
    assert "autoplay" not in js


def test_lecture_page_has_four_tabs():
    page = read("lecture.html")
    for tab in ("목차", "노트", "용어집", "FAQ"):
        assert f">{tab}</button>" in page


def test_server_down_banner_on_every_page():
    # 미니 서버가 꺼지면(1시간 미사용) 화면에 계속 보이는 안내를 띄운다
    common = read("common.js")
    assert "미니 서버가 꺼졌습니다 — 영상자료실 폴더의 「영상자료실 열기」를 더블클릭하세요." in common
    assert "/api/health" in common and "visibilitychange" in common
    assert "VL.watchServer()" in read("lecture.js") and "VL.watchServer()" in read("library.js")
    assert ".server-down" in read("app.css")


def test_pebble_colors_for_every_field_chip_and_view_button():
    # 분야 단추와 강의 카드 [보기]는 분야마다 다른 파스텔 조약돌 색
    css, js, common = read("app.css"), read("library.js"), read("common.js")
    keys = re.findall(r"(\w+): \"[^\"]+\"", common.split("FIELD_LABELS = {", 1)[1].split("}", 1)[0])
    assert keys
    for key in keys + ["all"]:
        assert f".pebble.field-{key}" in css, key
    assert "pebble" in js and "field-" in js


def test_hosted_admin_ui():
    common, lib, lec, page = read("common.js"), read("library.js"), read("lecture.js"), read("library.html")
    assert '"X-Requested-With": "video-library"' in common and "function info(" in common and "function send(" in common
    for needle in ('"/api/login"', '"/api/logout"', '"PATCH"', '"DELETE"', "confirm(", "아직 공개된 강의가 없습니다."):
        assert needle in lib, needle
    assert 'type="password"' in page and 'autocomplete="current-password"' in page
    assert "hosted" in lec and '$("#ask").hidden' in lec


def test_public_visitors_never_get_pc_only_messages():
    # 공개 서버 손님에게 '영상자료실 열기 더블클릭' 같은 PC 안내를 보이지 않는다(검토 재등급)
    common, lib, lec = read("common.js"), read("library.js"), read("lecture.js")
    assert "서버에 연결하지 못했습니다. 잠시 뒤 새로고침하세요." in common
    assert 'mode: "pc"' not in common  # 확인 실패를 PC 로 넘겨짚지 않는다
    assert 'info.mode !== "pc"' in lib and 'info.mode !== "pc"' in lec


def test_empty_library_shows_installed_command_names():
    page = read("library.html")
    assert "/video-library:video-library" in page and "$video-library" in page
