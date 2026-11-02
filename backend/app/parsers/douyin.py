"""抖音。页面或接口改版时，只改这个文件和对应的测试样例。"""

from __future__ import annotations

import re
from typing import Any

from app.errors import AppError, FetchError
from app.parsers.base import MediaSource, host_is, host_of
from app.parsers.jsonutil import parse_embedded_json, parse_script_json, walk
from app.services.titles import clean_title

# 抖音网页接口里 video.duration 的单位是毫秒。
PAGE_HEADERS = {"Referer": "https://www.douyin.com/"}
API_HEADERS = {
    "Referer": "https://www.douyin.com/",
    "Accept": "application/json, text/plain, */*",
}

_ID_PATH = re.compile(r"(?:video|note|share/video|item)/(\d{6,22})")
_ID_QUERY = re.compile(r"(?:modal_id|item_id|aweme_id)=(\d{6,22})")
_ID_TEXT = re.compile(r'(?:aweme_id|itemId|item_id)"?\s*[:=]\s*"?(\d{6,22})')

name = "douyin"


def matches(url: str) -> bool:
    host = host_of(url)
    if not host or "huoshan" in host:
        return False
    return host_is(host, "douyin.com") or host_is(host, "iesdouyin.com")


def find_item_id(*parts: str) -> str | None:
    for part in parts:
        if not part:
            continue
        for pattern in (_ID_PATH, _ID_QUERY, _ID_TEXT):
            match = pattern.search(part)
            if match:
                return match.group(1)
    return None


def _http_url(value: Any) -> str | None:
    if isinstance(value, str) and value.startswith("http"):
        return value.replace("\\u0026", "&").replace("\\/", "/")
    return None


def _url_from_play(obj: Any) -> str | None:
    direct = _http_url(obj)
    if direct:
        return direct
    if not isinstance(obj, dict):
        return None
    urls = obj.get("url_list") or obj.get("urlList") or []
    if isinstance(urls, list):
        for item in urls:
            found = _http_url(item)
            if found:
                return found
    return _http_url(obj.get("uri"))


def _pick_title(desc: str, music_obj: dict | None) -> str:
    title = desc.strip()
    music_title = ""
    if music_obj and isinstance(music_obj.get("title"), str):
        music_title = music_obj["title"].strip()
    if (not title or title.startswith("#")) and music_title:
        return music_title
    return title or music_title


def parse_douyin_json(data: Any, item_id: str | None = None) -> MediaSource | None:
    best: tuple[str, str | None, str | None] | None = None
    best_score = 0
    for node in walk(data):
        if not isinstance(node, dict):
            continue
        video_obj = node.get("video") if isinstance(node.get("video"), dict) else None
        music_obj = node.get("music") if isinstance(node.get("music"), dict) else None
        desc = node.get("desc") if isinstance(node.get("desc"), str) else ""
        audio = _url_from_play(music_obj.get("play_url")) if music_obj else None
        video = None
        if video_obj:
            video = _url_from_play(video_obj.get("play_addr")) or _url_from_play(
                video_obj.get("download_addr")
            )
        if not audio and not video:
            continue
        score = 1
        if desc.strip() and video_obj is not None:
            score += 5
        if audio:
            score += 3
        if video:
            score += 2
        aweme = str(node.get("aweme_id") or node.get("awemeId") or "")
        if item_id and aweme == str(item_id):
            score += 50
        if score > best_score:
            best_score = score
            best = (_pick_title(desc, music_obj), audio, video)
    if not best:
        return None
    title, audio, video = best
    headers = {"Referer": "https://www.douyin.com/"}
    if audio:
        return MediaSource(
            title=title,
            media_url=audio,
            media_kind="audio",
            platform="douyin",
            headers=headers,
            fallback_url=video,
            fallback_kind="video" if video else None,
            fallback_headers=headers if video else None,
        )
    return MediaSource(
        title=title,
        media_url=video or "",
        media_kind="video",
        platform="douyin",
        headers=headers,
    )


def parse_douyin_html(html: str, item_id: str | None = None) -> MediaSource | None:
    rendered = parse_script_json(html, "RENDER_DATA")
    if rendered is not None:
        parsed = parse_douyin_json(rendered, item_id=item_id)
        if parsed:
            return parsed
    embedded = parse_embedded_json(
        html,
        ("window._ROUTER_DATA = ", "window._ROUTER_DATA=", "window.__INIT_DATA__ = "),
    )
    if embedded is not None:
        return parse_douyin_json(embedded, item_id=item_id)
    return None


async def resolve(url: str, fetcher) -> MediaSource:
    item_id = find_item_id(url)
    html: str | None = None
    if not item_id:
        try:
            html = await fetcher.get_text(url, headers=PAGE_HEADERS)
        except FetchError:
            html = None
        if html:
            item_id = find_item_id(html)
    parsed: MediaSource | None = None
    if item_id:
        api = f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={item_id}"
        try:
            data = await fetcher.get_json(api, headers=API_HEADERS)
        except FetchError:
            data = None
        if data is not None:
            parsed = parse_douyin_json(data, item_id=item_id)
    if parsed is None:
        if html is None:
            try:
                html = await fetcher.get_text(url, headers=PAGE_HEADERS)
            except FetchError:
                html = None
        if html:
            if not item_id:
                item_id = find_item_id(html)
            parsed = parse_douyin_html(html, item_id=item_id)
    if parsed is None or not parsed.media_url:
        raise AppError("没能从抖音链接里找到音乐。请重新复制分享文字后再试。", "PARSE_FAILED")
    parsed.title = clean_title(parsed.title)
    return parsed
