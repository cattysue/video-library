"""3단계: 문장 목록을 약 10분 조각으로 나눈다(문장 경계 유지). AI 교정·번역이 조각 단위로 일한다."""
from __future__ import annotations

import argparse
import json
import shutil

from .config import StepError, fmt_time, library_home, read_json, work_dir, write_json, write_text, video_id_arg
from .jobs import track

CHUNK_SEC = 600.0
CONTEXT_SENTENCES = 3


def plan_chunks(sentences: list[dict], chunk_sec: float = CHUNK_SEC) -> list[tuple[int, int]]:
    ranges = []
    lo = sentences[0]["idx"]
    start0 = sentences[0]["start"]
    for s in sentences:
        if s["start"] - start0 >= chunk_sec and s["idx"] > lo:
            ranges.append((lo, s["idx"] - 1))
            lo, start0 = s["idx"], s["start"]
    ranges.append((lo, sentences[-1]["idx"]))
    if len(ranges) > 1 and sentences[-1]["end"] - sentences[ranges[-1][0] - 1]["start"] < chunk_sec / 4:
        last = ranges.pop()
        ranges[-1] = (ranges[-1][0], last[1])
    return ranges


def _line(s: dict) -> str:
    return f"[{s['idx']}] [{fmt_time(s['start'])}] {s['raw']}"


def render_chunk(sentences: list[dict], lo: int, hi: int, n: int, total: int) -> str:
    before = sentences[max(0, lo - 1 - CONTEXT_SENTENCES):lo - 1]
    body = sentences[lo - 1:hi]
    after = sentences[hi:hi + CONTEXT_SENTENCES]
    lines = [f"# 조각 {n:02d}/{total:02d} — 문장 {lo}~{hi}", "",
             "## CONTEXT (읽기 전용 — 고치지 마세요)"]
    lines += [_line(s) for s in before] or ["(없음)"]
    lines += ["", f"## EDITABLE RANGE ({lo}~{hi})"]
    lines += [_line(s) for s in body]
    lines += ["", "## CONTEXT (읽기 전용 — 고치지 마세요)"]
    lines += [_line(s) for s in after] or ["(없음)"]
    return "\n".join(lines) + "\n"


def chunk(home, video_id: str, chunk_sec: float = CHUNK_SEC) -> dict:
    work = work_dir(home, video_id)
    src = work / "build" / "sentences.json"
    if not src.exists():
        raise StepError("문장 목록이 없습니다. 먼저 preprocess 를 실행하세요.")
    sentences = read_json(src)
    cdir = work / "build" / "chunks"
    if cdir.exists():
        shutil.rmtree(cdir)  # 조각이 바뀌면 앞 조각의 AI 결과는 맞지 않으므로 함께 지운다
    ranges = plan_chunks(sentences, chunk_sec)
    entries = []
    for n, (lo, hi) in enumerate(ranges, start=1):
        write_text(cdir / f"{n:02d}.md", render_chunk(sentences, lo, hi, n, len(ranges)))
        entries.append({"n": n, "file": f"{n:02d}.md", "lo": lo, "hi": hi,
                        "start": sentences[lo - 1]["start"], "end": sentences[hi - 1]["end"]})
    write_json(cdir / "manifest.json", {"sentences": len(sentences), "chunks": entries})
    return {"chunks": len(ranges), "sentences": len(sentences)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py chunk", description="문장 목록을 약 10분 조각으로 나눈다.")
    ap.add_argument("--video", required=True, type=video_id_arg, help="영상 ID")
    a = ap.parse_args(argv)
    home = library_home()
    with track(home, a.video, "chunk"):
        result = chunk(home, a.video)
    print(json.dumps(result, ensure_ascii=False))
    return 0
