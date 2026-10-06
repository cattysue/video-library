from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]  # tests → video-library → skills → video-library → plugin → plugin-app


def test_dockerfile_runs_hosted_server_with_stdlib_only():
    text = (ROOT / "railway" / "Dockerfile").read_text(encoding="utf-8")
    assert text.startswith("FROM python:3.12-slim")
    assert "COPY plugin/video-library/skills/video-library/scripts ./scripts" in text
    assert "COPY plugin/video-library/skills/video-library/web ./web" in text
    assert "VL_HOME=/data" in text
    assert 'CMD ["python", "scripts/vl.py", "serve", "--hosted"]' in text
    assert "pip install" not in text  # 표준 라이브러리만
    for secret in ("VL_ADMIN_PASSWORD_HASH", "VL_UPLOAD_TOKEN_HASH", "token"):
        assert secret not in text  # 비밀 값은 Railway 변수로만


def test_dockerignore_keeps_image_small_and_clean():
    lines = (ROOT / ".dockerignore").read_text(encoding="utf-8").split()
    for pattern in ("**/__pycache__", "**/tests", "docs", ".superpowers", ".git"):
        assert pattern in lines
