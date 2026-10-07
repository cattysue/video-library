"""PC 미니 서버용 저장소: 영상자료실 폴더를 읽기만 한다(쓰기는 플러그인 명령이 파일로 한다)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .config import VIDEO_ID_RE, lecture_dir, now_kst, read_json
from .library import index_entry

JOB_RECENT_SEC = 3600
JOB_STALE_SEC = 6 * 3600  # 이만큼 갱신이 없으면 멈춘 작업으로 보고 숨긴다


class FileStore:
    def __init__(self, home: Path):
        self.home = Path(home)

    def list_lectures(self) -> list[dict]:
        try:
            items = read_json(self.home / "index.json")
            if isinstance(items, list):
                return items
        except (ValueError, OSError):
            pass
        items = []
        for path in sorted((self.home / "lectures").glob("*/lecture.json")):
            if "." in path.parent.name:
                continue
            try:
                items.append(index_entry(read_json(path)))
            except (ValueError, OSError, KeyError, TypeError):
                continue
        return sorted(items, key=lambda e: str(e.get("processed_at", "")), reverse=True)

    def get_lecture(self, lecture_id) -> dict | None:
        if not isinstance(lecture_id, str) or not VIDEO_ID_RE.fullmatch(lecture_id):
            return None
        try:
            doc = read_json(lecture_dir(self.home, lecture_id) / "lecture.json")
        except (ValueError, OSError):
            return None
        return doc if isinstance(doc, dict) else None

    def all_lectures(self) -> list[dict]:
        docs = []
        for entry in self.list_lectures():
            doc = self.get_lecture(entry.get("id")) if isinstance(entry, dict) else None
            if doc is not None:
                docs.append(doc)
        return docs

    def list_jobs(self, now=None) -> list[dict]:
        now = now or now_kst()
        jobs = []
        for path in (self.home / "jobs").glob("*.json"):
            try:
                job = read_json(path)
            except (ValueError, OSError):
                continue
            if not isinstance(job, dict):
                continue
            try:
                updated = datetime.fromisoformat(job["updated_at"])
                age = (now - updated).total_seconds()
            except (KeyError, TypeError, ValueError):
                continue
            limit = JOB_STALE_SEC if job.get("status") == "running" else JOB_RECENT_SEC
            if age <= limit:
                jobs.append(job)
        return sorted(jobs, key=lambda j: str(j.get("updated_at", "")), reverse=True)

    def version(self) -> str:
        try:
            st = (self.home / "index.json").stat()
        except OSError:
            return "none"
        return f"{st.st_mtime_ns}:{st.st_size}"
