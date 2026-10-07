"""작업 진행 기록(영상자료실/jobs/<job_id>.json). 목록 화면의 진행 카드가 이 파일을 읽는다."""
from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager
from pathlib import Path

from .config import StepError, library_home, now_kst, read_json, video_id_arg, work_dir, write_json
from .remote import report_job

STEPS = ("fetch", "preprocess", "chunk", "context", "correct", "merge",
         "outline", "glossary", "translate", "faq", "assemble", "upload")
STEP_STATUSES = ("pending", "running", "done", "failed", "skipped")


def job_path(home: Path, job_id: str) -> Path:
    return Path(home) / "jobs" / f"{job_id}.json"


def initial_steps(translate_needed: bool, upload_enabled: bool) -> dict[str, str]:
    steps = {s: "pending" for s in STEPS}
    steps["fetch"] = "running"
    if not translate_needed:
        steps["translate"] = "skipped"
    if not upload_enabled:
        steps["upload"] = "skipped"
    return steps


def start_job(home: Path, lecture_id: str, title: str, steps: dict[str, str], now=None) -> dict:
    now = now or now_kst()
    stamp = now.isoformat(timespec="seconds")
    job = {"job_id": f"{lecture_id}-{now:%m%d-%H%M}", "lecture_id": lecture_id, "title": title,
           "status": "running", "started_at": stamp, "updated_at": stamp,
           "steps": dict(steps), "detail": "", "error": None}
    write_json(job_path(home, job["job_id"]), job)
    report_job(home, job)
    return job


def load_job(home: Path, job_id: str) -> dict:
    path = job_path(home, job_id)
    if not path.exists():
        raise StepError(f"작업 기록이 없습니다: {job_id}")
    try:
        return read_json(path)
    except ValueError as exc:
        raise StepError(f"진행 기록 파일이 깨졌습니다: {path.name} ({exc})") from exc


def set_step(home: Path, job_id: str, step: str, status: str, detail: str = "",
             error: str | None = None, now=None) -> dict:
    if step not in STEPS:
        raise StepError(f"알 수 없는 단계: {step}")
    if status not in STEP_STATUSES:
        raise StepError(f"알 수 없는 상태: {status}")
    job = load_job(home, job_id)
    job["steps"][step] = status
    job["detail"] = (detail or "")[:200]
    if status == "failed":
        job["status"] = "failed"
        job["error"] = error or f"{step} 단계 실패"
    elif job["status"] == "failed" and status in ("running", "done"):
        job["status"] = "running"  # 실패한 단계부터 다시 실행하는 중
        job["error"] = None
    job["updated_at"] = (now or now_kst()).isoformat(timespec="seconds")
    write_json(job_path(home, job_id), job)
    report_job(home, job)
    return job


def finish_job(home: Path, job_id: str, outcome: dict[str, str], now=None) -> dict:
    job = load_job(home, job_id)
    for step, status in outcome.items():
        if job["steps"].get(step) in ("pending", "running"):
            job["steps"][step] = status
    waiting = job["steps"].get("upload") == "pending"  # 조립은 끝났고 업로드만 남음
    job["status"] = "running" if waiting else "done"
    job["error"] = None
    job["detail"] = "업로드 대기" if waiting else ""
    job["updated_at"] = (now or now_kst()).isoformat(timespec="seconds")
    write_json(job_path(home, job_id), job)
    report_job(home, job)
    return job


def pending_upload_job(home: Path, video_id: str) -> str | None:
    """업로드가 아직 끝나지 않은 이 영상의 가장 최근 작업(조립 뒤에는 작업 폴더가 없어 jobs/ 에서 찾는다)."""
    best = None
    for path in (Path(home) / "jobs").glob(f"{video_id}-*.json"):
        try:
            job = read_json(path)
        except (ValueError, OSError):
            continue
        if not isinstance(job, dict) or job.get("lecture_id") != video_id:
            continue
        if (job.get("steps") or {}).get("upload") not in ("pending", "running", "failed"):
            continue
        if best is None or str(job.get("updated_at", "")) > str(best.get("updated_at", "")):
            best = job
    return best["job_id"] if best else None


def abandon_job(home: Path, job_id: str, reason: str, now=None) -> dict:
    """끝나지 않은 작업을 실패로 닫는다(같은 영상을 처음부터 다시 시작할 때)."""
    job = load_job(home, job_id)
    if job["status"] == "done":
        return job
    for step, status in job["steps"].items():
        if status == "running":
            job["steps"][step] = "failed"
    job["status"] = "failed"
    job["error"] = reason
    job["updated_at"] = (now or now_kst()).isoformat(timespec="seconds")
    write_json(job_path(home, job_id), job)
    report_job(home, job)
    return job


def best_effort(fn, *args, **kwargs):
    """진행 기록은 보조 정보라, 실패해도 경고만 하고 실제 작업은 계속한다."""
    try:
        return fn(*args, **kwargs)
    except (StepError, ValueError, OSError, KeyError, TypeError) as exc:
        print(f"경고: 진행 기록을 남기지 못했습니다({exc}) — 작업은 계속합니다.", file=sys.stderr)
        return None


def current_job_id(home: Path, video_id: str) -> str | None:
    path = work_dir(home, video_id) / "build" / "request.json"
    if not path.exists():
        return None
    try:
        return read_json(path).get("job_id")
    except (ValueError, AttributeError):
        return None


@contextmanager
def track(home: Path, video_id: str, step: str):
    """기계 단계 하나를 감싸 running → done/failed 를 기록한다. job 이 없으면 기록하지 않는다."""
    job_id = current_job_id(home, video_id)
    if job_id:
        best_effort(set_step, home, job_id, step, "running")
    try:
        yield job_id
    except BaseException as exc:
        if job_id:
            msg = str(exc) if isinstance(exc, StepError) else f"{type(exc).__name__}: {exc}"
            best_effort(set_step, home, job_id, step, "failed", error=msg[:300])
        raise
    if job_id:
        best_effort(set_step, home, job_id, step, "done")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py progress", description="AI 판단 단계의 진행 상황을 기록한다.")
    ap.add_argument("--video", required=True, type=video_id_arg, help="영상 ID")
    ap.add_argument("--step", required=True, choices=STEPS)
    ap.add_argument("--status", default="running", choices=STEP_STATUSES)
    ap.add_argument("--detail", default="", help='예: "3/8"')
    ap.add_argument("--error", default=None)
    a = ap.parse_args(argv)
    home = library_home()
    job_id = current_job_id(home, a.video)
    if not job_id:
        raise StepError(f"진행 중인 작업이 없습니다: {a.video} (먼저 fetch 를 실행하세요)")
    set_step(home, job_id, a.step, a.status, a.detail, a.error)
    print(f"{a.step}: {a.status}" + (f" ({a.detail})" if a.detail else ""))
    return 0
