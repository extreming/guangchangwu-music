"""快手。页面结构变了就改这里。"""

from __future__ import annotations

import json
import re
from typing import Any

from app.errors import AppError, FetchError
from app.parsers.base import MediaSource, host_is, host_of
from app.parsers.jsonutil import json_unescape, parse_embedded_json, walk
from app.services.titles import clean_title

PAGE_HEADERS = {"Referer": "https://www.kuaishou.com/"}
_MARKERS = (
    "window.__APOLLO_STATE__ = ",
    "window.__APOLLO_STATE__=",
    "window.__INITIAL_STATE__ = ",
    "window.__INITIAL_STATE__=",
    "window.INIT_STATE = ",
    "window.INIT_STATE=",
)
_CAPTION = re.compile(r'"caption"\s*:\s*"((?:\\.|[^"\\])*)"')
_PHOTO = re.compile(r'"(?:photoUrl|playUrl)"\s*:\s*"((?:\\.|[^"\\])*)"')
_AUDIO = re.compile(r'"audioUrls"\s*:\s*\[\s*\{\s*"url"\s*:\s*"((?:\\.|[^"\\])*)"')

name = "kuaishou"


def matches(url: str) -> bool:
    host = host_of(url)
    if not host:
        return False
    return (
        host_is(host, "kuaishou.com")
        or host_is(host, "gifshow.com")
        or host_is(host, "chenzhongtech.com")
    )


def _http(value: Any) -> str | None:
    if isinstance(value, str) and value.startswith("http"):
        return value.replace("\\u0026", "&").replace("\\/", "/")
    return None


def parse_kuaishou_json(data: Any) -> MediaSource | None:
    title = ""
    audio = ""
    video = ""
    for node in walk(data):
        if not isinstance(node, dict):
            continue
        if not title:
            for key in ("caption", "photoCaption", "captionTitle"):
                raw = node.get(key)
                if isinstance(raw, str) and raw.strip():
                    title = raw.strip()
                    break
        if not video:
            for key in ("photoUrl", "playUrl", "srcNoMark", "mp4Url"):
                found = _http(node.get(key))
                if found:
                    video = found
                    break
        reps = node.get("representation")
        if not video and isinstance(reps, list):
            for rep in reps:
                if isinstance(rep, dict):
                    found = _http(rep.get("url"))
                    if found:
                        video = found
                        break
        if not audio:
            audios = node.get("audioUrls")
            if isinstance(audios, list):
                for item in audios:
                    if isinstance(item, str):
                        found = _http(item)
                    elif isinstance(item, dict):
                        found = _http(item.get("url") or item.get("cdnUrl"))
                    else:
                        found = None
                    if found:
                        audio = found
                        break
            else:
                found = _http(audios)
                if found:
                    audio = found
        soundtrack = node.get("soundTrack") or node.get("soundtrack")
        if isinstance(soundtrack, dict) and not audio:
            nested = parse_kuaishou_json(soundtrack)
            if nested and nested.media_kind == "audio":
                audio = nested.media_url
            if nested and not title:
                title = nested.title
    if not audio and not video:
        return None
    headers = {"Referer": "https://www.kuaishou.com/"}
    if audio:
        return MediaSource(
            title=title,
            media_url=audio,
            media_kind="audio",
            platform="kuaishou",
            headers=headers,
            fallback_url=video or None,
            fallback_kind="video" if video else None,
            fallback_headers=headers if video else None,
        )
    return MediaSource(
        title=title,
        media_url=video,
        media_kind="video",
        platform="kuaishou",
        headers=headers,
    )


def parse_kuaishou_html(html: str) -> MediaSource | None:
    embedded = parse_embedded_json(html, _MARKERS)
    if embedded is not None:
        parsed = parse_kuaishou_json(embedded)
        if parsed:
            return parsed
    caption = ""
    cap = _CAPTION.search(html)
    if cap:
        caption = json_unescape(cap.group(1))
    audio = ""
    audio_match = _AUDIO.search(html)
    if audio_match:
        audio = json_unescape(audio_match.group(1))
    video = ""
    photo = _PHOTO.search(html)
    if photo:
        video = json_unescape(photo.group(1))
    if not audio and not video:
        return None
    headers = {"Referer": "https://www.kuaishou.com/"}
    if audio:
        return MediaSource(
            title=caption,
            media_url=audio,
            media_kind="audio",
            platform="kuaishou",
            headers=headers,
            fallback_url=video or None,
            fallback_kind="video" if video else None,
            fallback_headers=headers if video else None,
        )
    return MediaSource(
        title=caption,
        media_url=video,
        media_kind="video",
        platform="kuaishou",
        headers=headers,
    )


async def resolve(url: str, fetcher) -> MediaSource:
    try:
        body = await fetcher.get_text(url, headers=PAGE_HEADERS)
    except FetchError as exc:
        raise AppError("没能打开快手链接。请重新复制分享后再试。", "PARSE_FAILED") from exc
    parsed = parse_kuaishou_html(body)
    if parsed is None:
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, (dict, list)):
            parsed = parse_kuaishou_json(data)
    if parsed is None or not parsed.media_url:
        raise AppError("没能从快手链接里找到音乐。请重新复制分享文字后再试。", "PARSE_FAILED")
    parsed.title = clean_title(parsed.title)
    return parsed
