"""Pull URLs out of the messy text people copy from a share sheet."""

from __future__ import annotations

import re

_ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\ufeff]")
# Chinese punctuation ends the URL. ASCII punctuation is trimmed afterwards so
# "https://v.douyin.com/abc/。" does not swallow the period-like full stop.
_URL = re.compile(
    r"https?://[^\s<>\"'，。！？、；：（）【】《》\u4e00-\u9fff]+",
    re.IGNORECASE,
)
_TRAIL = ".,;:!?)]}>\"'”’」』"


def extract_urls(text: str) -> list[str]:
    if not text:
        return []
    cleaned = _ZERO_WIDTH.sub("", text)
    found: list[str] = []
    for raw in _URL.findall(cleaned):
        url = raw.rstrip(_TRAIL)
        if url and url not in found:
            found.append(url)
    return found
