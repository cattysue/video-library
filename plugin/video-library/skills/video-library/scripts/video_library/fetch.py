"""1단계: yt-dlp 파이썬 라이브러리로 영상 정보·자막(json3)을 받고 작업을 시작한다. 영상 파일은 받지 않는다."""
from __future__ import annotations

import argparse
import json
import os
import shutil

from .config import StepError, ensure_home, library_home, work_dir, write_json
from .jobs import abandon_job, best_effort, current_job_id, initial_steps, set_step, start_job
from .remote import load_config
from .youtube import check_available, choose_caption, parse_video_id, trim_info

LONG_VIDEO_SEC = 3600


def _default_ydl_factory(opts: dict):
    import yt_dlp  # 이 명령에서만 필요하므로 늦게 import 한다

    return yt_dlp.YoutubeDL(opts)


def base_opts() -> dict:
    opts = {"quiet": True, "no_warnings": True, "noprogress": True, "skip_download": True}
    if shutil.which("deno") is None and shutil.which("node"):
        opts["js_runtimes"] = {"node": {}}  # yt-dlp 는 deno 만 기본으로 켠다
    return opts


def _explain(exc: Exception) -> str:
    msg = str(exc)
    low = msg.lower()
    if isinstance(exc, ModuleNotFoundError):
        return "yt-dlp 라이브러리가 설치되어 있지 않습니다. 'vl.py doctor' 를 실행해 설치 명령을 확인하세요."
    if "403" in msg:
        return ("유튜브가 요청을 막았습니다(HTTP 403). yt-dlp 를 최신으로 업데이트한 뒤 다시 시도하세요"
                "('vl.py doctor' 가 명령을 알려 줍니다).")
    if "private" in low or "sign in" in low or "members" in low:
        return "비공개·회원 전용·로그인이 필요한 영상은 처리할 수 없습니다."
    if "unavailable" in low:
        return "영상을 찾을 수 없거나 볼 수 없는 영상입니다."
    return f"영상 정보를 받지 못했습니다: {msg[:200]}"


def fetch(url: str, home, lang: str | None = None, translate_en: bool = False, upload: bool = True,
          ydl_factory=None, now=None) -> dict:
    factory = ydl_factory or _default_ydl_factory
    video_id = parse_video_id(url)
    ensure_home(home)
    source_url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with factory(base_opts()) as ydl:
            info = ydl.extract_info(source_url, download=False)
    except Exception as exc:
        raise StepError(_explain(exc)) from exc
    check_available(info)
    caption = choose_caption(info, lang)
    meta = trim_info(info, caption)
    if meta["duration"] <= 0:
        raise StepError("영상 길이를 알 수 없습니다. 잠시 뒤 다시 시도하세요.")

    work = work_dir(home, video_id)
    raw, build = work / "raw", work / "build"
    raw.mkdir(parents=True, exist_ok=True)
    old_job = current_job_id(home, video_id)
    if old_job:
        best_effort(abandon_job, home, old_job, "같은 영상의 새 작업으로 대체됨", now=now)
    if build.exists():
        shutil.rmtree(build)  # fetch 는 '처음부터 다시' — 앞 작업의 중간 결과를 섞지 않는다
    build.mkdir(parents=True)
    for old in raw.glob("source*.json3"):
        old.unlink()

    translate_needed = meta["language"] != "ko" or translate_en
    upload_enabled = upload and bool(load_config(home))
    job = start_job(home, video_id, meta["title"], initial_steps(translate_needed, upload_enabled), now=now)
    write_json(build / "request.json", {"video_id": video_id, "url": source_url, "job_id": job["job_id"],
                                        "translate_en": translate_en, "lang_override": lang})
    try:
        _download_caption(factory, source_url, raw, caption)
    except StepError as exc:
        best_effort(set_step, home, job["job_id"], "fetch", "failed", error=str(exc)[:300], now=now)
        raise
    write_json(raw / "info.json", meta)
    set_step(home, job["job_id"], "fetch", "done", now=now)
    return {"video_id": video_id, "job_id": job["job_id"], "work_dir": str(work), "title": meta["title"],
            "duration": meta["duration"], "language": meta["language"], "caption_kind": meta["caption_kind"],
            "long": meta["duration"] > LONG_VIDEO_SEC, "translate": translate_needed, "upload": upload_enabled}


def _download_caption(factory, source_url: str, raw, caption: dict) -> None:
    sub_opts = base_opts() | {
        "writesubtitles": caption["kind"] == "manual",
        "writeautomaticsub": caption["kind"] == "auto",
        "subtitleslangs": [caption["track"]],
        "subtitlesformat": "json3",
        "outtmpl": str(raw / "source.%(ext)s"),
    }
    try:
        with factory(sub_opts) as ydl:
            ydl.download([source_url])
    except Exception as exc:
        raise StepError(_explain(exc)) from exc
    produced = sorted(raw.glob("source.*.json3"))
    if not produced:
        raise StepError("자막 파일을 받지 못했습니다. 잠시 뒤 다시 시도하거나 'vl.py doctor' 로 환경을 확인하세요.")
    os.replace(produced[0], raw / "source.json3")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="vl.py fetch", description="유튜브 영상의 정보와 자막을 받고 작업을 시작한다.")
    ap.add_argument("url", help="유튜브 영상 링크")
    ap.add_argument("--lang", default=None, help="영상 언어를 직접 지정(예: ko, en)")
    ap.add_argument("--translate-en", action="store_true", help="한국어 영상의 전사를 영어로도 번역")
    ap.add_argument("--no-upload", action="store_true", help="Railway 업로드 설정이 있어도 이번에는 올리지 않음")
    a = ap.parse_args(argv)
    result = fetch(a.url, library_home(), lang=a.lang, translate_en=a.translate_en, upload=not a.no_upload,
                   ydl_factory=_default_ydl_factory)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
