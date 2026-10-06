import pytest

from video_library.config import StepError
from video_library.youtube import check_available, choose_caption, normalize_lang, parse_video_id, trim_info

VID = "AbCdEfGhIjK"
J3 = [{"ext": "vtt", "url": "x"}, {"ext": "json3", "url": "y"}]


@pytest.mark.parametrize("url", [
    f"https://www.youtube.com/watch?v={VID}",
    f"https://youtube.com/watch?v={VID}&list=PL123&index=2",
    f"https://youtu.be/{VID}?si=abc",
    f"https://www.youtube.com/shorts/{VID}",
    f"https://www.youtube.com/live/{VID}?feature=share",
    f"https://www.youtube.com/embed/{VID}",
    f"https://m.youtube.com/watch?v={VID}",
    f"https://music.youtube.com/watch?v={VID}",
    f"youtu.be/{VID}",
    VID,
])
def test_parse_video_id(url):
    assert parse_video_id(url) == VID


def test_playlist_only_rejected():
    with pytest.raises(StepError, match="재생목록"):
        parse_video_id("https://www.youtube.com/playlist?list=PL123")


def test_non_youtube_rejected():
    with pytest.raises(StepError, match="유튜브 링크가 아닙니다"):
        parse_video_id("https://vimeo.com/123")


def test_bad_id_rejected():
    with pytest.raises(StepError, match="영상 ID"):
        parse_video_id("https://www.youtube.com/watch?v=short")


@pytest.mark.parametrize("info, word", [
    ({"live_status": "is_live"}, "라이브"),
    ({"live_status": "is_upcoming"}, "라이브"),
    ({"availability": "private"}, "비공개"),
    ({"availability": "needs_auth"}, "비공개"),
    ({"age_limit": 18}, "연령 제한"),
])
def test_unavailable_videos(info, word):
    with pytest.raises(StepError, match=word):
        check_available(info)


def test_available_video_passes():
    check_available({"live_status": "was_live", "availability": "public", "age_limit": 0})


def test_normalize_lang():
    assert normalize_lang("en-US") == "en"
    assert normalize_lang("KO") == "ko"
    assert normalize_lang("fil") is None
    assert normalize_lang(None) is None


def test_manual_caption_preferred():
    info = {"language": "ko", "subtitles": {"ko": J3, "live_chat": J3}, "automatic_captions": {"ko": J3}}
    assert choose_caption(info) == {"lang": "ko", "kind": "manual", "track": "ko"}


def test_auto_caption_prefers_orig_track():
    info = {"language": "en", "automatic_captions": {"en": J3, "en-orig": J3, "ko": J3}}
    assert choose_caption(info) == {"lang": "en", "kind": "auto", "track": "en-orig"}


def test_language_from_single_orig_track():
    info = {"automatic_captions": {"ja-orig": J3, "ko": J3}}
    assert choose_caption(info)["lang"] == "ja"


def test_lang_override():
    info = {"language": "ko", "automatic_captions": {"en": J3}}
    assert choose_caption(info, "EN-us") == {"lang": "en", "kind": "auto", "track": "en"}


def test_bad_lang_override():
    with pytest.raises(StepError, match="두 글자"):
        choose_caption({"language": "ko"}, "english")


def test_unknown_language():
    with pytest.raises(StepError, match="--lang"):
        choose_caption({"automatic_captions": {"en": J3, "ko": J3}})


def test_no_captions():
    with pytest.raises(StepError, match="자막이 없어"):
        choose_caption({"language": "ko", "automatic_captions": {"en": J3}})


def test_tracks_without_json3_ignored():
    with pytest.raises(StepError, match="자막이 없어"):
        choose_caption({"language": "ko", "subtitles": {"ko": [{"ext": "vtt"}]}})


def test_trim_info_keeps_only_needed_keys():
    info = {"id": VID, "title": "제목", "uploader": "업로더", "duration": 600, "formats": [{"url": "secret"}],
            "thumbnail": "https://example.com/t.jpg"}
    meta = trim_info(info, {"lang": "ko", "kind": "auto", "track": "ko"})
    assert meta == {"id": VID, "title": "제목", "channel": "업로더", "duration": 600.0,
                    "thumbnail_url": f"https://i.ytimg.com/vi/{VID}/hqdefault.jpg", "language": "ko",
                    "caption_kind": "auto", "caption_track": "ko",
                    "source_url": f"https://www.youtube.com/watch?v={VID}"}
