import json
import threading

import pytest

from conftest import VIDEO_ID
from test_library import make_doc, stage
from test_server import make_web
from video_library import auth, jobs, library, remote, upload
from video_library.config import StepError
from video_library.server import LibraryServer
from video_library.store_hosted import HostedStore

TOKEN = "test-upload-token"


@pytest.fixture
def railway(tmp_path):
    a = auth.Auth(auth.hash_password("pw-for-tests", iterations=1000), auth.hash_token(TOKEN))
    data = tmp_path / "railway-data"
    server = LibraryServer(("127.0.0.1", 0), HostedStore(data), make_web(data), auth=a)
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    yield server
    server.shutdown()
    server.server_close()


def committed(home):
    stage(home, make_doc())
    library.commit_lecture(home, VIDEO_ID)


def test_upload_without_config_skips(home, capsys):
    committed(home)
    job = jobs.start_job(home, VIDEO_ID, "깃 기초", jobs.initial_steps(False, True))
    assert upload.main(["--video", VIDEO_ID]) == 0
    assert json.loads(capsys.readouterr().out)["uploaded"] is False
    saved = jobs.load_job(home, job["job_id"])
    assert saved["steps"]["upload"] == "skipped" and saved["status"] == "done"


def test_upload_to_railway(home, railway, capsys):
    committed(home)
    url = f"http://127.0.0.1:{railway.port}"
    remote.save_config(home, url, TOKEN)
    job = jobs.start_job(home, VIDEO_ID, "깃 기초", jobs.initial_steps(False, True))
    jobs.finish_job(home, job["job_id"], {})
    assert upload.main(["--video", VIDEO_ID]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"uploaded": True, "id": VIDEO_ID, "public": False, "url": f"{url}/lecture?id={VIDEO_ID}"}
    assert railway.store.get_lecture(VIDEO_ID)["lecture"]["id"] == VIDEO_ID
    saved = jobs.load_job(home, job["job_id"])
    assert saved["status"] == "done" and saved["steps"]["upload"] == "done"
    assert TOKEN not in json.dumps(out)


def test_wrong_token_fails_but_keeps_pc_copy(home, railway):
    committed(home)
    remote.save_config(home, f"http://127.0.0.1:{railway.port}", "wrong-token")
    job = jobs.start_job(home, VIDEO_ID, "깃 기초", jobs.initial_steps(False, True))
    with pytest.raises(StepError, match="업로드 실패\\(401\\)"):
        upload.main(["--video", VIDEO_ID])
    assert jobs.load_job(home, job["job_id"])["steps"]["upload"] == "failed"
    assert (home / "lectures" / VIDEO_ID / "lecture.json").exists()


def test_server_down_explains_retry(home):
    committed(home)
    remote.save_config(home, "http://127.0.0.1:9", TOKEN)  # 아무도 듣지 않는 포트
    with pytest.raises(StepError, match="다시 올리세요"):
        upload.main(["--video", VIDEO_ID])


def test_missing_lecture(home, railway):
    remote.save_config(home, f"http://127.0.0.1:{railway.port}", TOKEN)
    with pytest.raises(StepError, match="영상자료실에 이 강의가 없습니다"):
        upload.main(["--video", VIDEO_ID])
