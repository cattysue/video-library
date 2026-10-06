"""조각별 AI 결과(교정·교열, 번역)를 검사한 뒤 하나로 합친다."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import StepError, library_home, read_json, work_dir, write_json, video_id_arg
from .gates import _check_lang, check_chunk_edits, check_chunk_translation, manifest, sentences
from .jobs import track


def _all_or_fail(work: Path, checker, label: str) -> list[dict]:
    chunks = manifest(work)["chunks"]
    problems = []
    for c in chunks:
        problems += [f"조각 {c['n']:02d}: {e}" for e in checker(c["n"])]
    if problems:
        raise StepError(f"{label} 결과에 문제가 있습니다. 해당 조각만 다시 실행하세요:\n" + "\n".join(problems))
    return chunks


def merge_edits(work: Path) -> dict:
    chunks = _all_or_fail(work, lambda n: check_chunk_edits(work, n), "교정·교열")
    corrected = [{"idx": s["idx"], "start": s["start"], "end": s["end"], "text": s["raw"], "raw": s["raw"]}
                 for s in sentences(work)]
    corrections = []
    edited = 0
    for c in chunks:
        for e in read_json(work / "build" / "chunks" / f"{c['n']:02d}.edits.json"):
            corrected[e["idx"] - 1]["text"] = e["text"]
            edited += 1
            corrections += [{"idx": e["idx"], "from": ch["from"], "to": ch["to"], "kind": ch["kind"]}
                            for ch in e["changes"]]
    write_json(work / "build" / "sentences.corrected.json", corrected)
    write_json(work / "build" / "corrections.json", corrections)
    return {"chunks": len(chunks), "edited": edited, "corrections": len(corrections)}


def merge_translation(work: Path, lang: str) -> dict:
    _check_lang(lang)
    chunks = _all_or_fail(work, lambda n: check_chunk_translation(work, n, lang), "번역")
    items = []
    for c in chunks:
        items += read_json(work / "build" / "chunks" / f"{c['n']:02d}.{lang}.json")
    write_json(work / "build" / f"translations.{lang}.json", items)
    return {"lang": lang, "sentences": len(items)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py merge", description="조각별 교정·교열 또는 번역 결과를 합친다.")
    ap.add_argument("--video", required=True, type=video_id_arg, help="영상 ID")
    ap.add_argument("--kind", required=True, choices=("edits", "translation"))
    ap.add_argument("--lang", default=None, help="번역 언어(translation)")
    a = ap.parse_args(argv)
    home = library_home()
    work = work_dir(home, a.video)
    if not work.exists():
        raise StepError(f"작업 폴더가 없습니다: {work} (먼저 fetch 를 실행하세요)")
    if a.kind == "edits":
        with track(home, a.video, "merge"):
            result = merge_edits(work)
    else:
        with track(home, a.video, "translate"):
            result = merge_translation(work, a.lang or "")
    print(json.dumps(result, ensure_ascii=False))
    return 0
