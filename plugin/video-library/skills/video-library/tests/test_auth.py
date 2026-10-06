import pytest

from video_library import auth

PW = "시험용-관리자-비번"
TOKEN = "test-upload-token"


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make(clock=None):
    return auth.Auth(auth.hash_password(PW, iterations=1000), auth.hash_token(TOKEN), clock=clock or Clock())


def test_password_hash_roundtrip_and_format():
    stored = auth.hash_password(PW, iterations=1000)
    algo, iters, salt, digest = stored.split("$")
    assert algo == "pbkdf2_sha256" and iters == "1000" and len(salt) == 32 and len(digest) == 64
    assert PW not in stored
    assert auth.verify_password(PW, stored) and not auth.verify_password(PW + "x", stored)
    assert auth.hash_password(PW, iterations=1000) != stored  # salt 가 매번 다르다
    for broken in ("", "md5$1$00$00", "pbkdf2_sha256$x$zz$00", None):
        assert auth.verify_password(PW, broken) is False


def test_default_iterations_are_strong():
    assert auth.PBKDF2_ITERATIONS >= 200_000


def test_token_check():
    a = make()
    assert a.check_token(f"Bearer {TOKEN}")
    for bad in (None, "", TOKEN, "Bearer wrong", f"Basic {TOKEN}"):
        assert not a.check_token(bad)
    assert len(auth.hash_token(TOKEN)) == 64


@pytest.mark.parametrize("pw_hash, token_hash", [
    ("", "a" * 64), ("plain-password", "a" * 64), (None, "a" * 64),
    ("pbkdf2_sha256$1000$00$00", "short"), ("pbkdf2_sha256$1000$00$00", "Z" * 64)])
def test_rejects_bad_hash_settings(pw_hash, token_hash):
    with pytest.raises(ValueError):
        auth.Auth(pw_hash, token_hash)


def test_login_session_and_expiry():
    clock = Clock()
    a = make(clock)
    assert a.login("틀림") is None
    sid = a.login(PW)
    assert sid and a.session_ok(sid) and not a.session_ok("guess") and not a.session_ok(None)
    clock.now += auth.SESSION_TTL_SEC + 1
    assert not a.session_ok(sid)


def test_logout():
    a = make()
    sid = a.login(PW)
    a.logout(sid)
    assert not a.session_ok(sid)
    a.logout(None)  # 오류 없음


def test_lock_after_many_failures_even_for_right_password():
    clock = Clock()
    a = make(clock)
    for _ in range(auth.LOGIN_MAX_FAILURES):
        assert a.login("틀림") is None
    with pytest.raises(auth.LoginLocked):
        a.login(PW)
    clock.now += auth.LOGIN_WINDOW_SEC + 1
    assert a.login(PW)


def test_cookie_flags():
    c = auth.session_cookie("abc")
    assert c.startswith("vl_session=abc;")
    for flag in ("HttpOnly", "Secure", "SameSite=Strict", "Path=/", f"Max-Age={auth.SESSION_TTL_SEC}"):
        assert flag in c
    assert "Max-Age=0" in auth.session_cookie("", expire=True)


def test_parallel_guesses_cannot_skip_the_lock():
    # 동시에 많이 보내도 잠금 한도(10번)보다 많이 확인하면 안 된다(검토 C1)
    import threading
    a = auth.Auth(auth.hash_password(PW, iterations=20000), auth.hash_token(TOKEN))
    start = threading.Barrier(30)
    results = []

    def guess():
        start.wait()
        try:
            results.append(a.login("틀림"))
        except auth.LoginLocked:
            results.append("locked")

    threads = [threading.Thread(target=guess) for _ in range(30)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(None) <= auth.LOGIN_MAX_FAILURES
    assert results.count("locked") >= 30 - auth.LOGIN_MAX_FAILURES
