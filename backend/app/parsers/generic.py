"""普通网页：直接的音频/视频地址，或页面里的 audio / video 标签。"""

from __future__ import annotations

import json
import os
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

from app.errors import AppError
from app.parsers.base import MediaSource, kind_from_content_type, media_kind_from_url
from app.parsers.jsonutil import walk
from app.services.titles import clean_title

name = "generic"


def matches(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")


def title_from_url(url: str) -> str:
    name_part = os.path.basename(urlparse(url).path)
    if "." in name_part:
        name_part = name_part.rsplit(".", 1)[0]
    return name_part


class _Finder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.audio: list[str] = []
        self.video: list[str] = []
        self.title = ""
        self._in_title = False
        self._stack: list[str] = []
        self._jsonld = False
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): (value or "") for key, value in attrs}
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            prop = (attr.get("property") or attr.get("name") or "").lower()
            content = attr.get("content") or ""
            if content and prop in {"og:audio", "og:audio:url"}:
                self.audio.append(content)
            if content and prop in {"og:video", "og:video:url", "og:video:secure_url"}:
                self.video.append(content)
            if content and prop == "og:title" and not self.title:
                self.title = content.strip()
        if tag in {"audio", "video"}:
            self._stack.append(tag)
            src = attr.get("src")
            if src:
                (self.audio if tag == "audio" else self.video).append(src)
        if tag == "source" and self._stack:
            src = attr.get("src")
            if src:
                (self.audio if self._stack[-1] == "audio" else self.video).append(src)
        if tag == "script" and "ld+json" in (attr.get("type") or ""):
            self._jsonld = True
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in {"audio", "video"} and self._stack and self._stack[-1] == tag:
            self._stack.pop()
        if tag == "script" and self._jsonld:
            self._consume_jsonld("".join(self._buf))
            self._jsonld = False
            self._buf = []

    def handle_data(self, data: str) -> None:
        if self._in_title and data.strip() and not self.title:
            self.title = data.strip()
        if self._jsonld:
            self._buf.append(data)

    def _consume_jsonld(self, raw: str) -> None:
        raw = raw.strip()
        if not raw:
            return
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        for node in walk(data):
            if not isinstance(node, dict):
                continue
            kind = _ld_kind(node)
            for key in ("contentUrl", "contenturl", "encodingUrl"):
                value = node.get(key)
                if not isinstance(value, str) or not value.startswith("http"):
                    continue
                target = kind or media_kind_from_url(value)
                if target == "audio":
                    self.audio.append(value)
                elif target == "video":
                    self.video.append(value)


def _ld_kind(node: dict[str, Any]) -> str | None:
    raw = node.get("@type") or ""
    if isinstance(raw, list):
        raw = " ".join(str(item) for item in raw)
    text = str(raw).lower()
    if "audio" in text:
        return "audio"
    if "video" in text:
        return "video"
    return None


def _abs(page_url: str, src: str) -> str | None:
    src = src.strip()
    if not src or src.startswith(("data:", "blob:", "javascript:")):
        return None
    absolute = urljoin(page_url, src)
    if absolute.startswith("http://") or absolute.startswith("https://"):
        return absolute
    return None


def parse_html_media(html: str, page_url: str) -> MediaSource | None:
    finder = _Finder()
    try:
        finder.feed(html)
    except Exception:
        return None
    audio = [item for item in (_abs(page_url, src) for src in finder.audio) if item]
    video = [item for item in (_abs(page_url, src) for src in finder.video) if item]
    headers = {"Referer": page_url}
    title = clean_title(finder.title or title_from_url(page_url))
    if audio:
        return MediaSource(
            title=title,
            media_url=audio[0],
            media_kind="audio",
            platform="web",
            headers=headers,
            fallback_url=video[0] if video else None,
            fallback_kind="video" if video else None,
            fallback_headers=headers if video else None,
        )
    if video:
        return MediaSource(
            title=title,
            media_url=video[0],
            media_kind="video",
            platform="web",
            headers=headers,
        )
    return None


async def resolve(url: str, fetcher) -> MediaSource:
    kind = media_kind_from_url(url)
    if kind:
        return MediaSource(
            title=clean_title(title_from_url(url)),
            media_url=url,
            media_kind=kind,
            platform="direct" if kind == "audio" else "web",
        )
    info = await fetcher.peek(url)
    if info.is_media:
        detected = kind_from_content_type(info.content_type) or media_kind_from_url(info.final_url) or "video"
        final = info.final_url or url
        return MediaSource(
            title=clean_title(title_from_url(final)),
            media_url=final,
            media_kind=detected,
            platform="direct" if detected == "audio" else "web",
        )
    page = info.final_url or url
    html = info.snippet if "<audio" in info.snippet.lower() or "<video" in info.snippet.lower() else ""
    if not html:
        html = await fetcher.get_text(page)
    parsed = parse_html_media(html, page)
    if parsed is None or not parsed.media_url:
        raise AppError("这个页面里没有找到音乐或视频。请换一个链接。", "NO_MEDIA")
    return parsed
