"""11단계: 작업 폴더의 결과물 → lecture.json·전사 파일 → 영상자료실 반영 → 작업 완료."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .config import StepError, fmt_time, library_home, now_kst, work_dir, write_json, write_text, video_id_arg
from .gates import check_output, load_json_file
from .jobs import best_effort, finish_job, track
from .library import commit_lecture
from .validate import SCHEMA_VERSION, validate_lecture


def _required(path: Path):
    data, errors = load_json_file(path)
    if errors:
        raise StepError(f"{errors[0]} — 앞 단계를 먼저 끝내세요.")
    return data


def _optional(path: Path):
    if not path.exists():
        return None
    data, errors = load_json_file(path)
    if errors:
        raise StepError(errors[0])
    return data


def needed_translations(language: str, translate_en: bool) -> list[str]:
    if language != "ko":
        return ["ko"]
    return ["en"] if translate_en else []


def _with_times(chapters: list, segments: list) -> list:
    out = []
    for ch in chapters:
        a, b = ch["segments"]
        out.append({"id": ch["id"], "title": ch["title"], "summary": ch["summary"], "segments": [a, b],
                    "start": segments[a - 1]["start"], "end": segments[b - 1]["end"],
                    "children": _with_times(ch.get("children") or [], segments)})
    return out


def build_lecture(work: Path, now=None) -> tuple[dict, dict]:
    build = work / "build"
    info = _required(work / "raw" / "info.json")
    request = _required(build / "request.json")
    for kind in ("context", "outline"):
        errors = check_output(work, kind)
        if errors:
            raise StepError(f"{kind}.json 검사 불합격:\n" + "\n".join(f"  - {e}" for e in errors))
    context = _required(build / "context.json")
    outline = _required(build / "outline.json")
    segments = _required(build / "sentences.corrected.json")
    corrections = _optional(build / "corrections.json") or []
    glossary = _optional(build / "glossary.json")
    faq = _optional(build / "faq.json")
    language = info["language"]
    translations = {}
    for path in sorted(build.glob("translations.*.json")):
        lang = path.name.split(".")[1]
        if lang != language:
            translations[lang] = _required(path)
    needed = needed_translations(language, bool(request.get("translate_en")))
    skipped = []
    if glossary is None:
        skipped.append("glossary")
    if any(lang not in translations for lang in needed):
        skipped.append("translate")
    if faq is None:
        skipped.append("faq")
    doc = {
        "schema_version": SCHEMA_VERSION,
        "lecture": {
            "id": info["id"], "video_id": info["id"], "source_url": info["source_url"], "title": info["title"],
            "channel": info["channel"], "duration": info["duration"], "thumbnail_url": info["thumbnail_url"],
            "language": language, "field": context["field"], "one_liner": context["one_liner"], "mode": "text",
            "processed_at": (now or now_kst()).isoformat(timespec="seconds"),
            "pipeline": {"version": __version__, "caption_kind": info["caption_kind"], "skipped": skipped},
        },
        "segments": [{"idx": s["idx"], "start": s["start"], "end": s["end"], "text": s["text"], "raw": s["raw"]}
                     for s in segments],
        "translations": translations,
        "corrections": corrections,
        "chapters": _with_times(outline["chapters"], segments),
        "mentions": outline["mentions"],
        "glossary": glossary or [],
        "faq": faq or [],
    }
    errors = validate_lecture(doc)
    if errors:
        raise StepError("lecture.json 검사 불합격:\n" + "\n".join(f"  - {e}" for e in errors))
    outcome = {"context": "done", "correct": "done", "merge": "done", "outline": "done",
               "glossary": "skipped" if glossary is None else "done",
               "translate": "done" if needed and "translate" not in skipped else "skipped",
               "faq": "skipped" if faq is None else "done"}
    return doc, outcome


def _write_transcripts(work: Path, doc: dict) -> None:
    starts = [s["start"] for s in doc["segments"]]
    texts = {doc["lecture"]["language"]: [s["text"] for s in doc["segments"]]}
    for lang, items in doc["translations"].items():
        texts[lang] = [it["text"] for it in items]
    for lang, lines in texts.items():
        write_text(work / f"transcript.{lang}.txt", "\n".join(lines) + "\n")
        write_text(work / f"transcript.{lang}.timed.txt",
                   "\n".join(f"[{fmt_time(t)}] {x}" for t, x in zip(starts, lines)) + "\n")


def assemble(home, video_id: str, now=None) -> tuple[dict, dict]:
    work = work_dir(home, video_id)
    if not work.exists():
        raise StepError(f"작업 폴더가 없습니다: {work}")
    doc, outcome = build_lecture(work, now)
    write_json(work / "lecture.json", doc)
    _write_transcripts(work, doc)
    final = commit_lecture(home, video_id)
    result = {"video_id": video_id, "lecture_dir": str(final), "skipped": doc["lecture"]["pipeline"]["skipped"],
              "sentences": len(doc["segments"]), "chapters": len(doc["chapters"])}
    return result, outcome


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py assemble", description="결과물을 lecture.json 으로 조립해 영상자료실에 반영한다.")
    ap.add_argument("--video", required=True, type=video_id_arg, help="영상 ID")
    a = ap.parse_args(argv)
    home = library_home()
    with track(home, a.video, "assemble") as job_id:
        result, outcome = assemble(home, a.video)
    if job_id:
        best_effort(finish_job, home, job_id, outcome)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
