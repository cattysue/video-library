#!/usr/bin/env python3
"""video-library 단일 진입점.

이 파일이 있는 폴더를 import 경로에 넣으므로 어느 위치에서 실행해도 동작한다.

    python3 <이 파일> <명령> [옵션]      (명령 목록은 인자 없이 실행하면 나온다)

결과물은 영상자료실(기본: 문서/영상자료실, 환경변수 VL_HOME 으로 변경)에 쌓인다.
의존성: 파이썬 표준 라이브러리만(자막 받기 fetch 만 yt-dlp 라이브러리를 쓴다).
"""
from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

COMMANDS = {
    "validate": ("video_library.cli_validate", "lecture.json 이 약속(스키마 + 의미 규칙)을 지키는지 검사"),
    "progress": ("video_library.jobs", "AI 판단 단계의 진행 상황 기록"),
    "fetch": ("video_library.fetch", "유튜브 영상 정보·자막 받기, 작업 시작"),
    "preprocess": ("video_library.preprocess", "자막 → 문장 목록·전사"),
    "chunk": ("video_library.chunk", "약 10분 조각으로 나누기"),
    "check": ("video_library.gates", "AI 판단 단계 결과 파일 검사"),
    "merge": ("video_library.merge", "조각별 교정·교열 또는 번역 결과 합치기"),
    "reopen": ("video_library.library", "영상자료실의 강의를 다시 작업 폴더로 열기(추가 번역)"),
    "assemble": ("video_library.assemble", "lecture.json 조립·영상자료실 반영"),
    "doctor": ("video_library.doctor", "실행 환경 점검 + OS별 설치 명령 안내"),
    "search": ("video_library.search", "모든 강의에서 검색(질문 답변용)"),
    "serve": ("video_library.server", "영상자료실 화면용 PC 전용 미니 서버(보통 open 이 켠다)"),
    "open": ("video_library.opener", "영상자료실 화면 열기(필요하면 미니 서버를 켠다)"),
    "upload": ("video_library.upload", "강의를 내 Railway 서버로 올리기(설정이 있을 때만)"),
    "connect": ("video_library.connect", "내 Railway 서버와 연결(사용자가 자기 터미널에서 직접 실행)"),
}


def _utf8_console() -> None:
    """Windows 콘솔(cp949)에서도 한국어 출력이 깨지거나 죽지 않게 한다."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def usage() -> None:
    print(__doc__)
    print("사용 가능한 명령:")
    for name, (_, desc) in COMMANDS.items():
        print(f"  {name:<10} {desc}")


def main(argv: list[str]) -> int:
    _utf8_console()
    if not argv or argv[0] in ("-h", "--help", "help"):
        usage()
        return 0
    if argv[0] not in COMMANDS:
        print(f"알 수 없는 명령: {argv[0]}", file=sys.stderr)
        usage()
        return 2
    from video_library.config import StepError

    module = import_module(COMMANDS[argv[0]][0])
    try:
        return module.main(argv[1:])
    except StepError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
