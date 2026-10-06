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
