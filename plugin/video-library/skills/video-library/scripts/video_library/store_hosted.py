"""Railway 서버용 저장소: 영상자료실과 같은 파일 형식을 볼륨(/data)에 쓴다. 업로드·공개 상태·삭제·진행 보고."""
from __future__ import annotations

import re
import shutil
import threading
from datetime import datetime

from .config import VIDEO_ID_RE, lecture_dir, read_json, write_json
from .jobs import STEP_STATUSES, STEPS
from .library import rebuild_index, update_index
from .store_file import FileStore
from .validate import validate_lecture

VISIBILITY = "visibility.json"
JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}-\d{4}-\d{4}$")
JOB_STATUSES = ("running", "done", "failed")
JOB_KEYS = {"job_id", "lecture_id", "title", "status", "started_at", "updated_at", "steps", "detail", "error"}


class UploadError(ValueError):
    """받은 자료가 약속과 다를 때(서버는 400 으로 돌려준다)."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors[:5]))
        self.errors = errors


def _aware(value) -> bool:
    try:
        return datetime.fromisoformat(value).tzinfo is not None
    except (TypeError, ValueError):
        return False


def check_job(job_id, job) -> list[str]:
    if not isinstance(job_id, str) or not JOB_ID_RE.fullmatch(job_id):
        return ["job_id 형식이 올바르지 않습니다"]
    if not isinstance(job, dict):
        return ["진행 기록은 객체여야 합니다"]
    errors = []
    if set(job) != JOB_KEYS:
        errors.append(f"키가 약속과 다릅니다: {sorted(set(job) ^ JOB_KEYS)}")
    if job.get("job_id") != job_id:
        errors.append("job_id 가 주소와 다릅니다")
    lid = job.get("lecture_id")
    if not isinstance(lid, str) or not VIDEO_ID_RE.fullmatch(lid) or not job_id.startswith(lid + "-"):
        errors.append("lecture_id 가 올바르지 않습니다")
    if not isinstance(job.get("title"), str) or len(job["title"]) > 300:
        errors.append("title 은 300자 이하 글자")
    if job.get("status") not in JOB_STATUSES:
        errors.append("status 가 올바르지 않습니다")
    for key in ("started_at", "updated_at"):
        if not _aware(job.get(key)):
            errors.append(f"{key} 는 시간대가 있는 ISO 시각이어야 합니다")
    steps = job.get("steps")
    if not isinstance(steps, dict) or not set(steps) <= set(STEPS) or \
            any(v not in STEP_STATUSES for v in steps.values()):
        errors.append("steps 가 올바르지 않습니다")
    if not isinstance(job.get("detail"), str) or len(job["detail"]) > 200:
        errors.append("detail 은 200자 이하 글자")
    if job.get("error") is not None and (not isinstance(job["error"], str) or len(job["error"]) > 300):
        errors.append("error 는 300자 이하 글자 또는 null")
    return errors


class HostedStore(FileStore):
    def __init__(self, home):
        super().__init__(home)
        self._write_lock = threading.Lock()  # 동시에 들어온 업로드가 index.json 을 덮어쓰지 않게

    def public_ids(self) -> set[str]:
        try:
            data = read_json(self.home / VISIBILITY)
        except (ValueError, OSError):
            return set()  # 깨지거나 없으면 아무것도 공개하지 않는다
        ids = data.get("public") if isinstance(data, dict) else None
        if not isinstance(ids, list):
            return set()
        return {i for i in ids if isinstance(i, str) and VIDEO_ID_RE.fullmatch(i)}

    def _save_public(self, ids: set[str]) -> None:
        write_json(self.home / VISIBILITY, {"public": sorted(ids)})

    def put_lecture(self, lecture_id, doc) -> bool:
        if not isinstance(lecture_id, str) or not VIDEO_ID_RE.fullmatch(lecture_id):
            raise UploadError(["주소의 강의 ID 가 올바르지 않습니다"])
        errors = validate_lecture(doc)
        if errors:
            raise UploadError(errors)
        if doc["lecture"]["id"] != lecture_id:
            raise UploadError(["주소의 강의 ID 와 lecture.id 가 다릅니다"])
        with self._write_lock:
            write_json(lecture_dir(self.home, lecture_id) / "lecture.json", doc)
            update_index(self.home, doc)
            return lecture_id in self.public_ids()

    def set_public(self, lecture_id, public: bool) -> bool:
        with self._write_lock:
            if self.get_lecture(lecture_id) is None:
                return False
            ids = self.public_ids()
            if public:
                ids.add(lecture_id)
            else:
                ids.discard(lecture_id)
            self._save_public(ids)
            return True

    def delete_lecture(self, lecture_id) -> bool:
        with self._write_lock:
            if self.get_lecture(lecture_id) is None:
                return False
            shutil.rmtree(lecture_dir(self.home, lecture_id))
            rebuild_index(self.home)
            ids = self.public_ids()
            ids.discard(lecture_id)
            self._save_public(ids)
            return True

    def put_job(self, job_id, job) -> None:
        errors = check_job(job_id, job)
        if errors:
            raise UploadError(errors)
        write_json(self.home / "jobs" / f"{job_id}.json", job)
