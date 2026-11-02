"""抖音火山版。页面结构变了就改这里，不要去改抖音或快手。"""

from __future__ import annotations

import re
from typing import Any

from app.errors import AppError, FetchError
from app.parsers.base import MediaSource, host_is, host_of
from app.parsers.jsonutil import parse_embedded_json, parse_script_json, walk
from app.services.titles import clean_title

PAGE_HEADERS = {"Referer": "https://www.huoshan.com/"}
API_HEADERS = {
    "Referer": "https://share.huoshan.com/",
    "Accept": "application/json, text/plain, */*",
}

_ID_PATH = re.compile(r"(?:item|video|share/video)/(\d{6,22})")
_ID_QUERY = re.compile(r"(?:item_id|itemId|aweme_id)=(\d{6,22})")

name = "huoshan"


def matches(url: str) -> bool:
    host = host_of(url)
    if not host:
        return False
    return "hotsoon" in host or host_is(host, "huoshan.com")


def find_item_id(*parts: str) -> str | None:
    for part in parts:
        if not part:
            continue
        for pattern in (_ID_PATH, _ID_QUERY):
            match = pattern.search(part)
            if match:
                return match.group(1)
    return None


def _http_url(value: Any) -> str | None:
    if isinstance(value, str) and value.startswith("http"):
        return value.replace("\\u0026", "&").replace("\\/", "/")
    return None


def _first_http(values: Any) -> str | None:
    if isinstance(values, str):
        return _http_url(values)
    if isinstance(values, list):
        for item in values:
            found = _http_url(item)
            if found:
                return found
            if isinstance(item, dict):
                found = _http_url(item.get("url")) or _first_http(item.get("url_list"))
                if found:
                    return found
    return None


def _url_from_play(obj: Any) -> str | None:
    found = _http_url(obj)
    if found:
        return found
    if not isinstance(obj, dict):
        return None
    return _first_http(obj.get("url_list") or obj.get("urlList")) or _http_url(obj.get("uri"))


def parse_huoshan_json(data: Any, item_id: str | None = None) -> MediaSource | None:
    best: tuple[str, str | None, str | None] | None = None
    best_score = 0
    for node in walk(data):
        if not isinstance(node, dict):
            continue
        video_obj = node.get("video") if isinstance(node.get("video"), dict) else None
        music_obj = node.get("music") if isinstance(node.get("music"), dict) else None
        desc = ""
        for key in ("description", "desc", "title", "content"):
            raw = node.get(key)
            if isinstance(raw, str) and raw.strip():
                desc = raw.strip()
                break
        audio = _url_from_play(music_obj.get("play_url")) if music_obj else None
        video = None
        if video_obj:
            video = (
                _url_from_play(video_obj.get("play_addr"))
                or _url_from_play(video_obj.get("download_addr"))
                or _first_http(video_obj.get("url_list"))
                or _http_url(video_obj.get("url"))
            )
        if not audio and not video:
            continue
        score = 1
        if desc and (video_obj is not None or audio):
            score += 5
        if audio:
            score += 3
        if video:
            score += 2
        aweme = str(node.get("item_id") or node.get("aweme_id") or node.get("id") or "")
        if item_id and aweme == str(item_id):
            score += 50
        if score > best_score:
            best_score = score
            music_title = ""
            if music_obj and isinstance(music_obj.get("title"), str):
                music_title = music_obj["title"].strip()
            title = desc
            if (not title or title.startswith("#")) and music_title:
                title = music_title
            best = (title or music_title, audio, video)
    if not best:
        return None
    title, audio, video = best
    headers = {"Referer": "https://www.huoshan.com/"}
    if audio:
        return MediaSource(
            title=title,
            media_url=audio,
            media_kind="audio",
            platform="huoshan",
            headers=headers,
            fallback_url=video,
            fallback_kind="video" if video else None,
            fallback_headers=headers if video else None,
        )
    return MediaSource(
        title=title,
        media_url=video or "",
        media_kind="video",
        platform="huoshan",
        headers=headers,
    )


def parse_huoshan_html(html: str, item_id: str | None = None) -> MediaSource | None:
    for script_id in ("RENDER_DATA", "INIT_DATA"):
        payload = parse_script_json(html, script_id)
        if payload is not None:
            parsed = parse_huoshan_json(payload, item_id=item_id)
            if parsed:
                return parsed
    embedded = parse_embedded_json(
        html,
        ("window.__INIT_DATA__ = ", "window._ROUTER_DATA = "),
    )
    if embedded is not None:
        return parse_huoshan_json(embedded, item_id=item_id)
    return None


async def resolve(url: str, fetcher) -> MediaSource:
    item_id = find_item_id(url)
    html: str | None = None
    parsed: MediaSource | None = None
    try:
        html = await fetcher.get_text(url, headers=PAGE_HEADERS)
    except FetchError:
        html = None
    if html and not item_id:
        item_id = find_item_id(html)
    if item_id:
        api = f"https://share.huoshan.com/api/item/info/?item_id={item_id}"
        try:
            data = await fetcher.get_json(api, headers=API_HEADERS)
        except FetchError:
            data = None
        if data is not None:
            parsed = parse_huoshan_json(data, item_id=item_id)
    if parsed is None and html:
        parsed = parse_huoshan_html(html, item_id=item_id)
    if parsed is None or not parsed.media_url:
        raise AppError("没能从火山版链接里找到音乐。请重新复制分享文字后再试。", "PARSE_FAILED")
    parsed.title = clean_title(parsed.title)
    return parsed
