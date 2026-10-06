import json
import os
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
VL = TESTS_DIR.parent / "scripts" / "vl.py"
SAMPLE = TESTS_DIR / "fixtures" / "sample_lecture.json"


def run(*args, env_extra=None):
    env = dict(os.environ)
    env.update(env_extra or {})
    proc = subprocess.run([sys.executable, str(VL), *args], capture_output=True, env=env)
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


def test_no_command_prints_usage():
    code, out, _ = run()
    assert code == 0
    assert "validate" in out


def test_unknown_command():
    code, _, err = run("nope")
    assert code == 2
    assert "알 수 없는 명령: nope" in err


def test_validate_sample_passes():
    code, out, _ = run("validate", str(SAMPLE))
    assert code == 0
    assert "통과" in out


def test_validate_broken_file_fails(tmp_path):
    doc = json.loads(SAMPLE.read_text(encoding="utf-8"))
    doc["faq"] = doc["faq"][:2]
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    code, out, _ = run("validate", str(path))
    assert code == 1
    assert "불합격 (1건)" in out
    assert "$.faq: FAQ는 5~10개여야 함(현재 2개)" in out


def test_validate_reads_utf8_bom(tmp_path):
    path = tmp_path / "bom.json"
    path.write_text(SAMPLE.read_text(encoding="utf-8"), encoding="utf-8-sig")
    code, out, _ = run("validate", str(path))
    assert code == 0, out


def test_validate_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{ 깨진", encoding="utf-8")
    code, _, err = run("validate", str(path))
    assert code == 1
    assert "JSON 형식 오류" in err


def test_validate_missing_file(tmp_path):
    code, _, err = run("validate", str(tmp_path / "none.json"))
    assert code == 2
    assert "파일 없음" in err


def test_korean_output_survives_cp949_console(tmp_path):
    doc = json.loads(SAMPLE.read_text(encoding="utf-8"))
    doc["lecture"]["field"] = "cooking"
    path = tmp_path / "x.json"
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    code, out, err = run("validate", str(path), env_extra={"PYTHONIOENCODING": "cp949"})
    assert code == 1, err
    assert "허용 값" in out


def test_validate_rejects_nan_token(tmp_path):
    text = SAMPLE.read_text(encoding="utf-8").replace('"start": 0.0, "end": 35.0', '"start": NaN, "end": 35.0', 1)
    path = tmp_path / "nan.json"
    path.write_text(text, encoding="utf-8")
    code, _, err = run("validate", str(path))
    assert code == 1
    assert "JSON 형식 오류" in err
