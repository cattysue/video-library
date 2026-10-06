"""2단계: 자막(json3) → 단어 → 문장(build/sentences.json) + 전사(build/transcript.md)."""
from __future__ import annotations

import argparse
import json
import re

from .config import StepError, fmt_time, library_home, read_json, work_dir, write_json, write_text, video_id_arg
from .jobs import track

GAP_SEC = 1.0        # 이만큼 쉬면 문장을 끊는다
SOFT_MAX_SEC = 20.0  # 이보다 길면 짧은 쉼(SOFT_GAP_SEC)에서도 끊는다
SOFT_GAP_SEC = 0.3
HARD_MAX_SEC = 30.0  # 쉼이 없어도 이 길이에서는 끊는다
END_PUNCT = (".", "?", "!", "。", "？", "！")
_SOUND_TAG = re.compile(r"^\[[^\]]*\]$")  # [음악] [Music] [박수]


def words_from_json3(data) -> list[dict]:
    words = []
    events = data.get("events") if isinstance(data, dict) else None
    for ev in events or []:
        segs = ev.get("segs") if isinstance(ev, dict) else None
        if not segs or "tStartMs" not in ev:
            continue
        t0 = ev["tStartMs"] / 1000
        t_end = t0 + (ev.get("dDurationMs") or 0) / 1000
        pieces = []
        for seg in segs:
            text = " ".join((seg.get("utf8") or "").split())
            if not text or _SOUND_TAG.match(text):
                continue
            pieces.append((t0 + (seg.get("tOffsetMs") or 0) / 1000, text))
        for i, (start, text) in enumerate(pieces):
            end = pieces[i + 1][0] if i + 1 < len(pieces) else t_end
            words.append({"text": text, "start": round(start, 3), "end": round(max(end, start), 3)})
    words.sort(key=lambda w: w["start"])
    return words


def build_sentences(words: list[dict]) -> list[dict]:
    sentences: list[dict] = []
    current: list[dict] = []

    def flush():
        if current:
            sentences.append({"idx": len(sentences) + 1, "start": current[0]["start"],
                              "end": current[-1]["end"], "raw": " ".join(w["text"] for w in current)})
            current.clear()

    for i, w in enumerate(words):
        current.append(w)
        if i + 1 == len(words):
            break
        gap = words[i + 1]["start"] - w["end"]
        length = w["end"] - current[0]["start"]
        if (w["text"].endswith(END_PUNCT) or gap >= GAP_SEC
                or (length >= SOFT_MAX_SEC and gap >= SOFT_GAP_SEC) or length >= HARD_MAX_SEC):
            flush()
    flush()
    return sentences


def clamp_to_duration(sentences: list[dict], duration: float) -> list[dict]:
    """자막 시간이 영상 길이를 넘지 않게 자른다."""
    for s in sentences:
        s["end"] = min(s["end"], duration)
        s["start"] = min(s["start"], s["end"])
    return sentences


def render_transcript(sentences: list[dict]) -> str:
    lines = [f"# 전사 — 문장 {len(sentences)}개", ""]
    lines += [f"[{s['idx']}] [{fmt_time(s['start'])}] {s['raw']}" for s in sentences]
    return "\n".join(lines) + "\n"


def preprocess(home, video_id: str) -> dict:
    work = work_dir(home, video_id)
    src = work / "raw" / "source.json3"
    if not src.exists():
        raise StepError("자막 파일이 없습니다. 먼저 fetch 를 실행하세요.")
    try:
        data = read_json(src)
        info = read_json(work / "raw" / "info.json")
    except (ValueError, FileNotFoundError) as exc:
        raise StepError(f"자막 또는 영상 정보를 읽지 못했습니다: {exc}") from exc
    words = words_from_json3(data)
    sentences = clamp_to_duration(build_sentences(words), float(info["duration"]))
    if not sentences:
        raise StepError("자막에서 문장을 하나도 만들지 못했습니다(소리 표시만 있는 자막일 수 있습니다).")
    write_json(work / "build" / "sentences.json", sentences)
    write_text(work / "build" / "transcript.md", render_transcript(sentences))
    return {"sentences": len(sentences), "words": len(words), "duration": float(info["duration"])}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py preprocess", description="자막을 문장 목록으로 정리한다.")
    ap.add_argument("--video", required=True, type=video_id_arg, help="영상 ID")
    a = ap.parse_args(argv)
    home = library_home()
    with track(home, a.video, "preprocess"):
        result = preprocess(home, a.video)
    print(json.dumps(result, ensure_ascii=False))
    return 0
