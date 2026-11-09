"""Turn a video caption into a filename a person can recognize."""

from __future__ import annotations

import re

_ZERO = re.compile(r"[\u200b\u200c\u200d\ufeff]")
_SHARE_NOISE = (
    re.compile(r"复制打开抖音[，,]?\s*看看"),
    re.compile(r"复制此链接，打开【抖音火山版】[，,]?\s*直接观看视频！?"),
    re.compile(r"【[^】]{0,30}的作品】"),
    re.compile(r"^\d+(?:\.\d+)?\s*[A-Za-z]{2,12}:/?\s*"),
)
_UNSAFE = re.compile(r"[^\u4e00-\u9fffA-Za-z0-9《》「」（）()·\-—、\s]")


def clean_title(raw: str | None) -> str:
    text = raw or ""
    text = _ZERO.sub("", text)
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = re.sub(r"https?://\S+", " ", text)
    text = text.strip()
    for pattern in _SHARE_NOISE:
        text = pattern.sub(" ", text)
        text = text.strip()
    text = text.split("#", 1)[0]
    text = (
        text.replace("\\", " ")
        .replace("/", " ")
        .replace(":", " ")
        .replace("*", " ")
        .replace("?", " ")
        .replace('"', " ")
        .replace("<", " ")
        .replace(">", " ")
        .replace("|", " ")
    )
    text = _UNSAFE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(" .。-_")
    if len(text) > 48:
        text = text[:48].rstrip()
    return text or "未命名音乐"


def filename_for(title: str, ext: str = "mp3") -> str:
    suffix = (ext or "mp3").lstrip(".") or "mp3"
    return f"{clean_title(title)}.{suffix}"
