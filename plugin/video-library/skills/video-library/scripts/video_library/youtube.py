"""유튜브 링크·영상 정보 해석(네트워크 없음). yt-dlp 가 준 info 딕셔너리만 읽는다."""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from .config import StepError

_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_BLOCKED = ("private", "premium_only", "subscriber_only", "needs_auth")


def parse_video_id(url: str) -> str:
    url = url.strip()
    if _ID.match(url):
        return url
    parts = urlsplit(url if "://" in url else "https://" + url)
    host = (parts.hostname or "").lower()
    for prefix in ("www.", "m."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    if host == "youtu.be":
        candidate = parts.path.lstrip("/").split("/")[0]
    elif host in ("youtube.com", "music.youtube.com"):
        if parts.path == "/watch":
            candidate = (parse_qs(parts.query).get("v") or [""])[0]
        elif parts.path.startswith(("/shorts/", "/live/", "/embed/")):
            candidate = parts.path.split("/")[2]
        elif parts.path == "/playlist":
            raise StepError("재생목록 링크는 지원하지 않습니다. 영상 하나씩 넣어 주세요.")
        else:
            candidate = ""
    else:
        raise StepError(f"유튜브 링크가 아닙니다: {url}")
    if not _ID.match(candidate):
        raise StepError("유튜브 링크에서 영상 ID를 찾지 못했습니다. 영상 주소를 다시 확인해 주세요.")
    return candidate


def check_available(info: dict) -> None:
    if info.get("live_status") in ("is_live", "is_upcoming"):
        raise StepError("진행 중이거나 예정된 라이브 방송은 처리할 수 없습니다. 방송이 끝난 뒤 다시 시도하세요.")
    if info.get("availability") in _BLOCKED:
        raise StepError("비공개·회원 전용·로그인이 필요한 영상은 처리할 수 없습니다.")
    if (info.get("age_limit") or 0) >= 18:
        raise StepError("연령 제한 영상은 처리할 수 없습니다.")


def normalize_lang(code: str | None) -> str | None:
    if not code:
        return None
    head = code.split("-")[0].lower()
    return head if len(head) == 2 and head.isalpha() else None


def _has_json3(formats) -> bool:
    return any(isinstance(f, dict) and f.get("ext") == "json3" for f in formats or [])


def choose_caption(info: dict, lang_override: str | None = None) -> dict:
    subs = {k: v for k, v in (info.get("subtitles") or {}).items() if k != "live_chat"}
    autos = info.get("automatic_captions") or {}
    lang = None
    if lang_override:
        lang = normalize_lang(lang_override)
        if not lang:
            raise StepError("--lang 은 두 글자 언어 코드여야 합니다(예: ko, en).")
    if not lang:
        lang = normalize_lang(info.get("language"))
    if not lang:
        origs = [k for k in autos if k.endswith("-orig")]
        if len(origs) == 1:
            lang = normalize_lang(origs[0][: -len("-orig")])
    if not lang and len(subs) == 1:
        lang = normalize_lang(next(iter(subs)))
    if not lang:
        raise StepError("영상의 원래 언어를 알 수 없습니다. --lang ko 처럼 언어를 지정해 다시 실행하세요.")
    for key in sorted(subs):
        if normalize_lang(key) == lang and _has_json3(subs[key]):
            return {"lang": lang, "kind": "manual", "track": key}
    for key in (f"{lang}-orig", lang):
        if key in autos and _has_json3(autos[key]):
            return {"lang": lang, "kind": "auto", "track": key}
    raise StepError("이 영상에는 사용할 수 있는 자막이 없어 처리할 수 없습니다.")


def trim_info(info: dict, caption: dict) -> dict:
    vid = info["id"]
    return {
        "id": vid,
        "title": info.get("title") or vid,
        "channel": info.get("channel") or info.get("uploader") or "",
        "duration": float(info.get("duration") or 0),
        "thumbnail_url": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
        "language": caption["lang"],
        "caption_kind": caption["kind"],
        "caption_track": caption["track"],
        "source_url": f"https://www.youtube.com/watch?v={vid}",
    }
