"""영상자료실의 강의(lecture.json)를 내 Railway 서버로 올린다. 설정(config.json)이 없으면 건너뛴다."""
from __future__ import annotations

import argparse
import json

from .config import StepError, lecture_dir, library_home, read_json, video_id_arg
from .jobs import best_effort, finish_job, pending_upload_job, set_step
from .remote import RemoteError, load_config, request

UPLOAD_TIMEOUT_SEC = 60.0


def upload(home, video_id: str, cfg: dict) -> dict:
    path = lecture_dir(home, video_id) / "lecture.json"
    if not path.exists():
        raise StepError(f"영상자료실에 이 강의가 없습니다: {video_id}")
    try:
        doc = read_json(path)
    except ValueError as exc:
        raise StepError(f"영상자료실의 lecture.json 이 깨졌습니다({exc}). 그 강의를 다시 처리한 뒤 올리세요.") from exc
    try:
        status, body = request("PUT", f"{cfg['server']}/api/lectures/{video_id}", cfg["token"], doc,
                               timeout=UPLOAD_TIMEOUT_SEC)
    except RemoteError as exc:
        raise StepError(f"Railway 서버에 연결하지 못했습니다({exc}). PC 결과는 그대로 있습니다 — "
                        f"나중에 'vl.py upload --video {video_id}' 로 다시 올리세요.") from exc
    if status != 200:
        hint = " 토큰이나 서버를 바꿨다면 사용자가 직접 'vl.py connect' 를 다시 실행하세요." if status == 401 else ""
        raise StepError(f"업로드 실패({status}): {body.get('error', '')} — PC 결과는 그대로 있습니다.{hint}")
    return {"uploaded": True, "id": video_id, "public": bool(body.get("public")),
            "url": f"{cfg['server']}/lecture?id={video_id}"}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py upload", description="강의를 내 Railway 서버로 올린다(새 강의는 비공개).")
    ap.add_argument("--video", required=True, type=video_id_arg, help="영상 ID")
    a = ap.parse_args(argv)
    home = library_home()
    job_id = pending_upload_job(home, a.video)
    cfg = load_config(home)
    if not cfg:
        if job_id:
            best_effort(finish_job, home, job_id, {"upload": "skipped"})
        print(json.dumps({"uploaded": False, "reason": "업로드 설정이 없습니다(선택 기능) — 건너뜀"}, ensure_ascii=False))
        return 0
    if job_id:
        best_effort(set_step, home, job_id, "upload", "running")
    try:
        result = upload(home, a.video, cfg)
    except StepError as exc:
        if job_id:
            best_effort(set_step, home, job_id, "upload", "failed", error=str(exc)[:300])
        raise
    if job_id:
        best_effort(finish_job, home, job_id, {"upload": "done"})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
