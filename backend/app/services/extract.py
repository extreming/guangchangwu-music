from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import Settings
from app.errors import AppError
from app.parsers.base import MediaSource, is_hls_url
from app.parsers.linktext import extract_urls
from app.parsers.registry import choose_url, resolve_media
from app.services.fetcher import Fetcher
from app.services.ffmpeg_audio import extract_audio_file, looks_like_html_or_json, looks_like_playlist
from app.services.titles import clean_title, filename_for

logger = logging.getLogger(__name__)

LABELS = {
    "douyin": "抖音",
    "kuaishou": "快手",
    "huoshan": "抖音火山版",
    "web": "网页",
    "direct": "链接",
}
_FALLBACK_CODES = {
    "NOT_MEDIA",
    "NO_AUDIO",
    "FETCH_FAILED",
    "UPSTREAM",
    "BAD_RESPONSE",
    "TIMEOUT",
    "HLS",
}


async def extract_from_text(text: str, fetcher: Fetcher, settings: Settings) -> dict:
    urls = extract_urls(text)
    if not urls:
        raise AppError(
            "没有找到链接。请复制完整的分享文字，里面要有 http 开头的地址。",
            "NO_URL",
        )
    url = choose_url(urls)
    expanded = await fetcher.expand(url)
    source = await resolve_media(expanded, fetcher)
    file_id = uuid.uuid4().hex
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    tmp = settings.tmp_dir / f"{file_id}.bin"
    out = settings.data_dir / f"{file_id}.mp3"
    try:
        duration = await _produce(source, tmp, out, settings, fetcher)
    except Exception:
        out.unlink(missing_ok=True)
        raise
    finally:
        tmp.unlink(missing_ok=True)

    title = clean_title(source.title)
    filename = filename_for(title, "mp3")
    created = time.time()
    expires = datetime.now(timezone.utc) + timedelta(seconds=settings.file_ttl_seconds)
    duration_out = None if duration is None else int(round(duration))
    meta = {
        "id": file_id,
        "title": title,
        "filename": filename,
        "platform": source.platform,
        "platform_label": LABELS.get(source.platform, "网页"),
        "format": "mp3",
        "duration": duration_out,
        "size": out.stat().st_size,
        "created_ts": created,
        "expires_at": expires.isoformat(),
    }
    (settings.data_dir / f"{file_id}.json").write_text(
        json.dumps(meta, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(
        "saved id=%s platform=%s bytes=%s",
        file_id,
        source.platform,
        meta["size"],
    )
    return {
        "id": file_id,
        "title": title,
        "filename": filename,
        "platform": source.platform,
        "platform_label": meta["platform_label"],
        "audio_url": f"{settings.public_base_url}/api/files/{file_id}",
        "duration": duration_out,
        "size": meta["size"],
        "format": "mp3",
        "expires_at": meta["expires_at"],
    }


async def _produce(
    source: MediaSource,
    tmp: Path,
    out: Path,
    settings: Settings,
    fetcher: Fetcher,
) -> float | None:
    attempts = [(source.media_url, source.headers)]
    if source.fallback_url:
        attempts.append((source.fallback_url, source.fallback_headers or source.headers))
    last: AppError | None = None
    for index, (url, headers) in enumerate(attempts):
        try:
            tmp.unlink(missing_ok=True)
            out.unlink(missing_ok=True)
            await _download_one(url, headers, tmp, settings, fetcher)
            return await extract_audio_file(tmp, out, settings.max_duration_seconds)
        except AppError as exc:
            last = exc
            if exc.code not in _FALLBACK_CODES or index == len(attempts) - 1:
                raise
            logger.info("media source failed (%s), trying another", exc.code)
    if last is None:
        raise AppError("没有提取到声音，请换一个链接试试。", "NO_AUDIO")
    raise last


async def _download_one(
    url: str,
    headers: dict[str, str] | None,
    tmp: Path,
    settings: Settings,
    fetcher: Fetcher,
) -> None:
    if is_hls_url(url):
        raise AppError("这个链接是分段视频，暂时提取不了。请换一个分享。", "HLS")
    await fetcher.download(url, tmp, headers, settings.max_download_bytes)
    if looks_like_html_or_json(tmp) or looks_like_playlist(tmp):
        tmp.unlink(missing_ok=True)
        raise AppError("下载到的不是音乐。链接可能失效了，请重新分享。", "NOT_MEDIA")
