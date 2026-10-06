"""vl.py validate — lecture.json 검사 명령."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .validate import validate_lecture


def _reject_constant(name: str):
    raise ValueError(f"표준 JSON이 아닌 값 {name}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py validate",
                                 description="lecture.json 이 약속(스키마 + 의미 규칙)을 지키는지 검사한다.")
    ap.add_argument("path", help="검사할 lecture.json 경로")
    args = ap.parse_args(argv)
    try:
        # utf-8-sig: 메모장 등이 붙인 BOM 이 있어도 읽는다
        doc = json.loads(Path(args.path).read_text(encoding="utf-8-sig"), parse_constant=_reject_constant)
    except FileNotFoundError:
        print(f"파일 없음: {args.path}", file=sys.stderr)
        return 2
    except ValueError as exc:  # JSONDecodeError 와 NaN·Infinity 거부
        print(f"JSON 형식 오류: {exc}", file=sys.stderr)
        return 1
    errors = validate_lecture(doc)
    if errors:
        print(f"불합격 ({len(errors)}건)")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("통과")
    return 0
