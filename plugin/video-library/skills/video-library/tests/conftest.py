"""테스트가 어디서 실행되든 스킬의 scripts/ 를 import 경로에 넣는다(설치 불요)."""
import json
import socket
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES = TESTS_DIR / "fixtures"
sys.path.insert(0, str(TESTS_DIR.parent / "scripts"))


@pytest.fixture
def sample() -> dict:
    """직접 쓴 샘플 lecture.json. 테스트마다 새로 읽어 서로 영향을 주지 않는다."""
    return json.loads((FIXTURES / "sample_lecture.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    """모든 테스트에서 영상자료실을 한글·공백이 든 임시 경로로 돌린다 — 실제 문서 폴더를 건드리지 않는다."""
    path = tmp_path / "내 문서" / "영상자료실"
    monkeypatch.setenv("VL_HOME", str(path))
    return path


@pytest.fixture
def home(_isolated_home):
    from video_library.config import ensure_home
    return ensure_home(_isolated_home)


VIDEO_ID = "AbCdEfGhIjK"


def sample_doc() -> dict:
    return json.loads((FIXTURES / "sample_lecture.json").read_text(encoding="utf-8"))


def seed_work(home, doc=None, translate_en=False):
    """샘플 강의로 'preprocess 가 끝난 상태'의 작업 폴더를 만든다."""
    from video_library import config, jobs

    doc = doc or sample_doc()
    lec = doc["lecture"]
    vid = lec["video_id"]
    work = config.work_dir(home, vid)
    config.write_json(work / "raw" / "info.json", {
        "id": vid, "title": lec["title"], "channel": lec["channel"], "duration": lec["duration"],
        "thumbnail_url": lec["thumbnail_url"], "language": lec["language"],
        "caption_kind": lec["pipeline"]["caption_kind"], "caption_track": lec["language"],
        "source_url": lec["source_url"]})
    translate_needed = lec["language"] != "ko" or translate_en
    job = jobs.start_job(home, vid, lec["title"], jobs.initial_steps(translate_needed, upload_enabled=False))
    config.write_json(work / "build" / "request.json", {
        "video_id": vid, "url": lec["source_url"], "job_id": job["job_id"],
        "translate_en": translate_en, "lang_override": None})
    config.write_json(work / "build" / "sentences.json", [
        {"idx": s["idx"], "start": s["start"], "end": s["end"], "raw": s["raw"]} for s in doc["segments"]])
    return work


_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


@pytest.fixture(autouse=True)
def _no_internet(monkeypatch):
    """테스트는 내 PC 안(127.0.0.1)에만 연결한다 — 실제 Railway·유튜브로 나가면 바로 실패."""
    real_connect = socket.socket.connect
    real_getaddrinfo = socket.getaddrinfo

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if host not in _LOCAL_HOSTS:
            raise OSError(f"테스트 중 인터넷 연결 금지: {host}")
        return real_connect(self, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if host not in _LOCAL_HOSTS and host is not None:
            raise OSError(f"테스트 중 인터넷 연결 금지: {host}")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
