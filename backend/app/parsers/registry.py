"""Pick a platform parser. Order matters: 火山版 before 抖音."""

from __future__ import annotations

from app.errors import AppError
from app.parsers import douyin, generic, huoshan, kuaishou
from app.parsers.base import MediaSource

PARSERS = (huoshan, kuaishou, douyin)
_HARD_STOP = {"TOO_LARGE", "BLOCKED", "BAD_URL", "RATE_LIMIT", "UNAUTHORIZED"}


def for_url(url: str):
    for parser in PARSERS:
        if parser.matches(url):
            return parser
    return None


def choose_url(urls: list[str]) -> str:
    for url in urls:
        if for_url(url) is not None:
            return url
    return urls[0]


async def resolve_media(url: str, fetcher) -> MediaSource:
    parser = for_url(url)
    if parser is None:
        return await generic.resolve(url, fetcher)
    try:
        return await parser.resolve(url, fetcher)
    except AppError as first:
        if first.code in _HARD_STOP:
            raise
        try:
            return await generic.resolve(url, fetcher)
        except AppError:
            raise first
