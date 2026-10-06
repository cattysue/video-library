"""영상자료실 반영: 작업 폴더 → 완성 폴더(원자적 교체), index.json 목록, 재작업 열기."""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from .config import StepError, library_home, lecture_dir, read_json, work_dir, write_json, video_id_arg
from .jobs import STEPS, start_job
from .remote import load_config
from .validate import validate_lecture

INDEX_NAME = "index.json"


def index_entry(doc: dict) -> dict:
    lec = doc["lecture"]
    return {"id": lec["id"], "title": lec["title"], "channel": lec["channel"], "duration": lec["duration"],
            "thumbnail_url": lec["thumbnail_url"], "field": lec["field"], "language": lec["language"],
            "translations": sorted(doc["translations"]), "chapter_count": len(doc["chapters"]),
            "processed_at": lec["processed_at"]}


def _save_index(home: Path, items: list) -> list:
    items = sorted(items, key=lambda e: str(e.get("processed_at", "")), reverse=True)
    write_json(home / INDEX_NAME, items)
    return items


def rebuild_index(home: Path) -> list:
    items = []
    for path in sorted((home / "lectures").glob("*/lecture.json")):
        if "." in path.parent.name:  # <id>.tmp, <id>.old
            continue
        try:
            items.append(index_entry(read_json(path)))
        except (ValueError, KeyError, TypeError):
            continue
    return _save_index(home, items)


def update_index(home: Path, doc: dict) -> list:
    path = home / INDEX_NAME
    try:
        items = read_json(path) if path.exists() else []
        if not isinstance(items, list):
            raise ValueError("index.json 이 배열이 아님")
    except ValueError:
        return rebuild_index(home)  # 깨진 목록은 lectures/ 에서 다시 만든다
    entry = index_entry(doc)
    items = [e for e in items if isinstance(e, dict) and e.get("id") != entry["id"]] + [entry]
    return _save_index(home, items)


_LOCKED = "영상자료실에 반영하지 못했습니다(폴더가 열려 있으면 닫고 다시 시도): {}"


def commit_lecture(home: Path, video_id: str) -> Path:
    work, final = work_dir(home, video_id), lecture_dir(home, video_id)
    backup = final.with_name(f"{video_id}.old")
    if not final.exists() and backup.exists():
        try:
            os.replace(backup, final)  # 지난번 반영이 중간에 멈춰 .old 에만 남은 강의를 되살린다
        except OSError as exc:
            raise StepError(_LOCKED.format(exc)) from exc
    try:
        doc = read_json(work / "lecture.json")
    except (ValueError, FileNotFoundError) as exc:
        raise StepError(f"lecture.json 을 읽지 못했습니다: {exc}") from exc
    errors = validate_lecture(doc)
    if errors:
        raise StepError("lecture.json 검사 불합격 — 영상자료실의 기존 자료는 그대로 둡니다:\n"
                        + "\n".join(f"  - {e}" for e in errors))
    try:
        if backup.exists():
            shutil.rmtree(backup)
        if final.exists():
            os.replace(final, backup)
    except OSError as exc:
        raise StepError(_LOCKED.format(exc)) from exc
    try:
        os.replace(work, final)
    except OSError as exc:
        try:
            if backup.exists() and not final.exists():
                os.replace(backup, final)
        except OSError:
            pass  # .old 에 남은 강의는 다음 반영 때 되살린다
        raise StepError(_LOCKED.format(exc)) from exc
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
    update_index(home, doc)
    return final


def reopen(home: Path, video_id: str, translate_en: bool) -> dict:
    final, work = lecture_dir(home, video_id), work_dir(home, video_id)
    if not (final / "lecture.json").exists():
        raise StepError(f"영상자료실에 이 강의가 없습니다: {video_id}")
    if work.exists():
        raise StepError(f"작업 폴더가 이미 있습니다: {work} — 이전 작업을 이어서 하거나 폴더를 지운 뒤 다시 실행하세요.")
    doc = read_json(final / "lecture.json")
    if translate_en and doc["lecture"]["language"] != "ko":
        raise StepError("영어 번역 요청은 한국어 강의에만 할 수 있습니다.")
    shutil.copytree(final, work)
    steps = {s: "skipped" for s in STEPS}
    steps["assemble"] = "pending"
    if translate_en:
        steps["translate"] = "pending"
    if load_config(home):
        steps["upload"] = "pending"  # Railway 사본도 새 번역으로 바꾼다
    job = start_job(home, video_id, doc["lecture"]["title"], steps)
    req_path = work / "build" / "request.json"
    request = read_json(req_path) if req_path.exists() else {
        "video_id": video_id, "url": doc["lecture"]["source_url"], "translate_en": False, "lang_override": None}
    request["job_id"] = job["job_id"]
    request["translate_en"] = translate_en or request.get("translate_en", False)
    write_json(req_path, request)
    return {"video_id": video_id, "job_id": job["job_id"], "work_dir": str(work)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py reopen", description="영상자료실의 강의를 다시 작업 폴더로 연다(추가 번역용).")
    ap.add_argument("--video", required=True, type=video_id_arg, help="영상 ID")
    ap.add_argument("--translate-en", action="store_true", help="한국어 강의의 전사를 영어로 번역")
    a = ap.parse_args(argv)
    result = reopen(library_home(), a.video, a.translate_en)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
