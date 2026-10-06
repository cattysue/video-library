"""AI 판단 단계 결과 파일의 검사 관문. 1단계 검사기를 작업 폴더 파일에 연결한다."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from .config import StepError, library_home, read_json, work_dir, video_id_arg
from .validate import (check_context, check_edits, check_faq, check_glossary, check_outline,
                       check_translation_chunk, term_pairs)

OUTPUT_KINDS = ("context", "outline", "glossary", "faq")
_LANG = re.compile(r"^[a-z]{2}$")


def load_json_file(path: Path):
    path = Path(path)
    if not path.exists():
        return None, [f"{path.name}: 파일이 없습니다"]
    try:
        return read_json(path), []
    except ValueError as exc:
        return None, [f"{path.name}: JSON 형식 오류 — {exc}"]


def _must(path: Path, hint: str):
    data, errors = load_json_file(path)
    if errors:
        raise StepError(f"{errors[0]} ({hint})")
    return data


def sentences(work: Path) -> list[dict]:
    return _must(work / "build" / "sentences.json", "먼저 preprocess 를 실행하세요")


def manifest(work: Path) -> dict:
    return _must(work / "build" / "chunks" / "manifest.json", "먼저 chunk 를 실행하세요")


def chunk_range(work: Path, n: int) -> tuple[int, int]:
    for c in manifest(work)["chunks"]:
        if c["n"] == n:
            return c["lo"], c["hi"]
    raise StepError(f"조각 {n}번이 없습니다. manifest.json 의 조각 번호를 확인하세요.")


def _check_lang(lang: str) -> None:
    if not _LANG.match(lang or ""):
        raise StepError("--lang 은 두 글자 언어 코드여야 합니다(예: ko, en).")


def check_chunk_edits(work: Path, n: int) -> list[str]:
    lo, hi = chunk_range(work, n)
    data, errors = load_json_file(work / "build" / "chunks" / f"{n:02d}.edits.json")
    if errors:
        return errors
    originals = {s["idx"]: s["raw"] for s in sentences(work) if lo <= s["idx"] <= hi}  # 정수 키
    return check_edits(originals, data, lo, hi, allowed_pairs=_context_pairs(work))


def _context_pairs(work: Path) -> set:
    """맥락표의 안전한 heard_as → term 쌍. 맥락표가 없거나 틀리면 예외 없이 엄격하게 검사한다."""
    context, errors = load_json_file(work / "build" / "context.json")
    if errors or check_context(context):
        return set()
    return term_pairs(context)


def check_chunk_translation(work: Path, n: int, lang: str) -> list[str]:
    _check_lang(lang)
    lo, hi = chunk_range(work, n)
    data, errors = load_json_file(work / "build" / "chunks" / f"{n:02d}.{lang}.json")
    if errors:
        return errors
    return check_translation_chunk(list(range(lo, hi + 1)), data)


def check_output(work: Path, kind: str) -> list[str]:
    if kind not in OUTPUT_KINDS:
        raise StepError(f"알 수 없는 검사 종류: {kind}")
    data, errors = load_json_file(work / "build" / f"{kind}.json")
    if errors:
        return errors
    n = len(sentences(work))
    duration = float(_must(work / "raw" / "info.json", "먼저 fetch 를 실행하세요")["duration"])
    if kind == "context":
        return check_context(data)
    if kind == "outline":
        return check_outline(data, n, duration)
    if kind == "glossary":
        return ["$: 용어가 하나도 없음"] if data == [] else check_glossary(data, n)
    return check_faq(data, n, require_count=True)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py check", description="AI 판단 단계의 결과 파일을 검사한다.")
    ap.add_argument("--video", required=True, type=video_id_arg, help="영상 ID")
    ap.add_argument("--kind", required=True, choices=("edits", "translation") + OUTPUT_KINDS)
    ap.add_argument("--chunk", type=int, default=None, help="조각 번호(edits·translation)")
    ap.add_argument("--lang", default=None, help="번역 언어(translation)")
    a = ap.parse_args(argv)
    work = work_dir(library_home(), a.video)
    if not work.exists():
        raise StepError(f"작업 폴더가 없습니다: {work} (먼저 fetch 를 실행하세요)")
    if a.kind in ("edits", "translation"):
        if a.chunk is None:
            raise StepError("edits·translation 검사에는 --chunk 조각 번호가 필요합니다.")
        errors = (check_chunk_edits(work, a.chunk) if a.kind == "edits"
                  else check_chunk_translation(work, a.chunk, a.lang or ""))
    else:
        errors = check_output(work, a.kind)
    if errors:
        print(f"불합격 ({len(errors)}건)")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("통과")
    return 0
