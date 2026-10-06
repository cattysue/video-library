"""Railway 연결(사용자가 자기 터미널에서 직접 실행). 비밀번호는 보이지 않게 입력받고, 토큰은 무작위로 만든다.
Railway 에는 해시만 표준 입력으로 넘기고, 토큰은 내 PC 의 config.json 에만 둔다. 화면에는 비밀 값을 출력하지 않는다."""
from __future__ import annotations

import argparse
import getpass
import json
import secrets
import shutil
import subprocess
import sys

from .auth import hash_password, hash_token
from .config import StepError, ensure_home, library_home
from .remote import CONFIG_NAME, normalize_server, save_config

MIN_PASSWORD = 6
SECRET_VARS = ("VL_ADMIN_PASSWORD_HASH", "VL_UPLOAD_TOKEN_HASH")


def connect(home, server_url: str, service: str | None = None, ask=getpass.getpass, run=subprocess.run,
            railway: str | None = None) -> dict:
    server = normalize_server(server_url)
    railway = railway or shutil.which("railway")
    if not railway:
        raise StepError("Railway CLI 가 없습니다. https://docs.railway.com/cli 에서 설치하고 'railway login' 후 다시 실행하세요.")
    first = ask("Railway 관리자 비밀번호(6자 이상, 화면에 보이지 않음): ")
    second = ask("한 번 더 입력: ")
    if first != second:
        raise StepError("두 비밀번호가 서로 다릅니다. 다시 실행하세요.")
    if len(first) < MIN_PASSWORD:
        raise StepError(f"비밀번호는 {MIN_PASSWORD}자 이상이어야 합니다.")
    token = secrets.token_urlsafe(32)
    values = {SECRET_VARS[0]: hash_password(first), SECRET_VARS[1]: hash_token(token)}
    for i, (key, value) in enumerate(values.items()):
        cmd = [railway, "variable", "set", key, "--stdin"]
        if service:
            cmd += ["--service", service]
        if i < len(values) - 1:
            cmd.append("--skip-deploys")  # 마지막 변수를 넣을 때 한 번만 다시 배포
        proc = run(cmd, input=value, text=True, capture_output=True)
        if proc.returncode != 0:
            raise StepError(f"Railway 변수 {key} 를 넣지 못했습니다. 이 폴더가 'railway link' 로 프로젝트에 "
                            f"연결됐는지 확인하세요. ({(proc.stderr or '').strip()[:300]})")
    path = save_config(ensure_home(home), server, token)
    return {"server": server, "config": str(path)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py connect",
                                 description="내 Railway 서버와 연결한다(사용자가 자기 터미널에서 직접 실행).")
    ap.add_argument("server", help="Railway 서버 주소(예: https://video-library.up.railway.app)")
    ap.add_argument("--service", default=None, help="Railway 서비스 이름")
    a = ap.parse_args(argv)
    if not sys.stdin.isatty():
        raise StepError("이 명령은 비밀번호를 입력받으므로 사용자가 자기 터미널에서 직접 실행해야 합니다.")
    result = connect(library_home(), a.server, service=a.service)
    print(json.dumps(result, ensure_ascii=False))
    print(f"연결 완료: 서버 주소와 업로드 토큰을 {CONFIG_NAME} 에 저장했습니다(토큰은 화면에 표시하지 않음). "
          "Railway 가 새 설정으로 다시 배포됩니다(1~2분).")
    return 0
