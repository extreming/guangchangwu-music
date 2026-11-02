"""Turn a downloaded video or audio file into an MP3."""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.errors import AppError


def looks_like_html_or_json(path: Path) -> bool:
    with path.open("rb") as handle:
        head = handle.read(256).lstrip(b"\xef\xbb\xbf \t\r\n")
    lowered = head.lower()
    if lowered.startswith((b"<!doctype", b"<html", b"<head", b"<?xml", b"<script")):
        return True
    return head.startswith((b"{", b"["))


def looks_like_playlist(path: Path) -> bool:
    with path.open("rb") as handle:
        head = handle.read(256)
    return b"#EXTM3U" in head


async def _run(args: list[str]) -> tuple[int, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise AppError("转换时间太长，请换一个短一点的视频。", "TIMEOUT", 504)
    return proc.returncode or 0, stderr or stdout


async def probe_duration(path: Path) -> float | None:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()
    if proc.returncode != 0:
        return None
    try:
        value = float(stdout.decode().strip())
    except ValueError:
        return None
    if value < 0:
        return None
    return value


async def has_audio_stream(path: Path) -> bool:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=codec_type",
        "-of",
        "csv=p=0",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()
    return proc.returncode == 0 and b"audio" in stdout


def _too_long(max_duration: int) -> str:
    minutes = max(1, max_duration // 60)
    return f"这首太长了（超过{minutes}分钟）。请换一首短一点的。"


async def extract_audio_file(src: Path, dest: Path, max_duration: int) -> float | None:
    if looks_like_html_or_json(src):
        raise AppError("下载到的不是音乐。链接可能失效了，请重新分享。", "NOT_MEDIA")
    if looks_like_playlist(src):
        raise AppError("这个链接是分段视频，暂时提取不了。请换一个分享。", "HLS")
    duration = await probe_duration(src)
    if duration is not None and duration > max_duration:
        raise AppError(_too_long(max_duration), "TOO_LONG")
    if not await has_audio_stream(src):
        raise AppError("这里面没有声音。请换一个链接。", "NO_AUDIO")
    dest.parent.mkdir(parents=True, exist_ok=True)
    code, err = await _run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(src),
            "-vn",
            "-acodec",
            "libmp3lame",
            "-ar",
            "44100",
            "-b:a",
            "128k",
            "-ac",
            "2",
            str(dest),
        ]
    )
    if code != 0 or not dest.exists() or dest.stat().st_size < 128:
        dest.unlink(missing_ok=True)
        tail = err.decode("utf-8", "replace")[-400:]
        if tail:
            import logging

            logging.getLogger(__name__).warning("ffmpeg failed: %s", tail)
        raise AppError("没有提取到声音，请换一个链接试试。", "NO_AUDIO")
    return await probe_duration(dest)
