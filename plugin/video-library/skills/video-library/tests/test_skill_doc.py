import importlib.util
import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SKILL = SKILL_DIR / "SKILL.md"


def load_commands():
    spec = importlib.util.spec_from_file_location("vl_cmds", SKILL_DIR / "scripts" / "vl.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.COMMANDS


def text():
    return SKILL.read_text(encoding="utf-8")


def test_frontmatter():
    assert text().startswith("---\nname: video-library\ndescription: ")


def test_every_mentioned_command_exists():
    used = set(re.findall(r"vl\.py\"?\s+([a-z]+)", text()))
    assert used and used <= set(load_commands())


def test_every_command_is_documented():
    used = set(re.findall(r"vl\.py\"?\s+([a-z]+)", text()))
    assert set(load_commands()) - {"validate"} <= used


def test_all_briefs_present():
    for title in ("[맥락 브리프]", "[교정 브리프]", "[목차 브리프]", "[용어집 브리프]", "[번역 브리프]", "[FAQ 브리프]"):
        assert f"## {title}" in text()


def test_safety_rules_present():
    body = text()
    assert "토큰" in body and "승인" in body
    assert "말한 내용은 바꾸지 않는다" in body


def test_failure_reporting_and_powershell_rules():
    body = text()
    assert "--status failed --error" in body
    assert "PowerShell" in body and "[Console]::OutputEncoding" in body


def test_viewer_and_question_sections():
    body = text()
    assert "## 나중 요청: 영상자료실 열기" in body and "## 질문 답변" in body
    assert "vl.py open" in body and "vl.py search" in body
    assert "/lecture?id=<ID>&t=<초>" in body


def test_description_names_open_and_question_triggers():
    # 스킬이 호출되는지는 description만 보고 정해진다
    description = text().split("\n")[2]
    assert "열기" in description and "질문" in description and "업로드" in description


def test_question_answer_uses_live_url_and_one_keyword_per_search():
    body = text()
    section = body.split("## 질문 답변", 1)[1].split("\n## ", 1)[0]
    assert "vl.py open --no-browser" in section  # 서버가 꺼져 있어도 켜고 실제 주소를 쓴다
    assert "핵심어마다 따로" in section  # 여러 단어를 한 번에 넣으면 이어 붙여 찾아 0건이 된다


def test_glossary_claim_note_is_rare():
    body = text()
    brief = body.split("## [용어집 브리프]", 1)[1].split("\n## ", 1)[0]
    assert "사실 확인이 필요한" in brief and "claim_note가 아니다" in brief
    assert "3분의 1" in brief


def test_upload_and_connect_documented():
    body = text()
    assert "12. **업로드**" in body and "vl.py upload --video <ID>" in body and "--no-upload" in body
    section = body.split("## 나중 요청: Railway 연결(선택)", 1)[1].split("\n## ", 1)[0]
    assert "vl.py connect" in section and "직접" in section
    assert "대신 실행하지 않는다" in section


def test_translation_request_uploads_again():
    section = text().split("## 나중 요청: 한국어 강의 영어 번역", 1)[1].split("\n## ", 1)[0]
    assert "vl.py upload --video <ID>" in section


def test_frontmatter_description_is_valid_yaml_scalar():
    # 설명문에 "질문: …" 같은 '콜론+공백'이 있으면 YAML 이 깨져 설치 후 설명이 통째로 빠진다(claude plugin validate 로 발견)
    line = text().split("\n")[2]
    value = line[len("description: "):]
    assert value.startswith("'") and value.endswith("'"), "설명문은 작은따옴표로 감싼다"
    assert "'" not in value[1:-1].replace("''", ""), "안쪽 작은따옴표는 두 번 써야 한다"


def test_plain_requests_and_plugin_command_names():
    body = text()
    description = body.split("\n")[2]
    assert "/video-library:video-library <링크>" in description and "$video-library <링크>" in description
    assert '"video-library 번역 <ID>"' in description or "video-library 번역 <영상ID>" in description
    assert "`/video-library 번역" not in body and "`/video-library 열기" not in body and "`/video-library 업로드" not in body
