from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

AUDIO_EXT = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac", ".opus"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}


@dataclass
class MediaSource:
    title: str
    media_url: str
    media_kind: str  # "audio" or "video"
    platform: str
    headers: dict[str, str] = field(default_factory=dict)
    fallback_url: str | None = None
    fallback_kind: str | None = None
    fallback_headers: dict[str, str] | None = None


def host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def host_is(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def media_kind_from_url(url: str) -> str | None:
    path = urlparse(url).path.lower()
    dot = path.rfind(".")
    ext = path[dot:] if dot >= 0 else ""
    if ext in AUDIO_EXT:
        return "audio"
    if ext in VIDEO_EXT:
        return "video"
    return None


def kind_from_content_type(content_type: str) -> str | None:
    base = content_type.split(";")[0].strip().lower()
    if base.startswith("audio/"):
        return "audio"
    if base.startswith("video/"):
        return "video"
    return None


def is_hls_url(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".m3u8")
