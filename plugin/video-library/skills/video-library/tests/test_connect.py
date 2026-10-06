import subprocess

import pytest

from video_library import auth, connect, remote
from video_library.config import StepError

PW = "시험용-비밀번호-1234"
URL = "https://video-library.up.railway.app"


class Runner:
    def __init__(self, code=0):
        self.code = code
        self.calls = []

    def __call__(self, cmd, input=None, text=None, capture_output=None, **kw):
        self.calls.append((cmd, input))
        return subprocess.CompletedProcess(cmd, self.code, stdout="", stderr="railway 오류" if self.code else "")


def asker(*answers):
    it = iter(answers)
    return lambda prompt="": next(it)


def test_connect_sets_hashes_by_stdin_and_saves_config(home, capsys):
    run = Runner()
    out = connect.connect(home, URL + "/", service="video-library", ask=asker(PW, PW), run=run, railway="railway")
    assert out == {"server": URL, "config": str(home / "config.json")}
    cfg = remote.load_config(home)
    assert cfg["server"] == URL and len(cfg["token"]) >= 40
    (cmd1, in1), (cmd2, in2) = run.calls
    assert cmd1 == ["railway", "variable", "set", "VL_ADMIN_PASSWORD_HASH", "--stdin", "--service", "video-library", "--skip-deploys"]
    assert cmd2 == ["railway", "variable", "set", "VL_UPLOAD_TOKEN_HASH", "--stdin", "--service", "video-library"]
    assert auth.verify_password(PW, in1) and in2 == auth.hash_token(cfg["token"])
    joined = " ".join(" ".join(c) for c, _ in run.calls) + capsys.readouterr().out
    assert PW not in joined and cfg["token"] not in joined  # 비밀 값은 명령줄·출력 어디에도 없다


@pytest.mark.parametrize("answers, message", [
    ((PW, PW + "x"), "서로 다릅니다"),
    (("five5", "five5"), "6자"),
])
def test_bad_passwords(home, answers, message):
    run = Runner()
    with pytest.raises(StepError, match=message):
        connect.connect(home, URL, ask=asker(*answers), run=run, railway="railway")
    assert run.calls == [] and remote.load_config(home) == {}


def test_railway_failure_keeps_old_config(home):
    remote.save_config(home, URL, "old-token")
    with pytest.raises(StepError, match="Railway 변수"):
        connect.connect(home, URL, ask=asker(PW, PW), run=Runner(code=1), railway="railway")
    assert remote.load_config(home)["token"] == "old-token"


def test_bad_url(home):
    with pytest.raises(StepError, match="https://"):
        connect.connect(home, "http://example.com", ask=asker(PW, PW), run=Runner(), railway="railway")


def test_main_refuses_without_terminal(home, monkeypatch):
    monkeypatch.setattr(connect.sys.stdin, "isatty", lambda: False, raising=False)
    with pytest.raises(StepError, match="직접"):
        connect.main([URL])


def test_missing_railway_cli(home, monkeypatch):
    monkeypatch.setattr(connect.shutil, "which", lambda name: None)
    with pytest.raises(StepError, match="Railway CLI"):
        connect.connect(home, URL, ask=asker(PW, PW), run=Runner())


def test_six_character_password_is_enough(home):
    # 사용자 결정(10-06): 관리자 비밀번호는 6자 이상
    run = Runner()
    connect.connect(home, URL, ask=asker("abc123", "abc123"), run=run, railway="railway")
    assert auth.verify_password("abc123", run.calls[0][1])
