from pathlib import Path

import pytest

from app.errors import AppError
from app.services.ffmpeg_audio import extract_audio_file, looks_like_playlist
from tests.conftest import build_tone_mp4


@pytest.mark.asyncio
async def test_extracts_mp3_from_video(tmp_path: Path):
    src = tmp_path / "in.mp4"
    dest = tmp_path / "out.mp3"
    build_tone_mp4(src)
    duration = await extract_audio_file(src, dest, max_duration=20 * 60)
    assert dest.exists()
    assert dest.stat().st_size > 200
    assert duration is not None and duration > 0
    head = dest.read_bytes()[:3]
    assert head == b"ID3" or head[0] == 0xFF


@pytest.mark.asyncio
async def test_rejects_html_and_playlist_and_long_media(tmp_path: Path):
    html = tmp_path / "page.html"
    html.write_text("<!DOCTYPE html><html><body>no</body></html>", encoding="utf-8")
    with pytest.raises(AppError) as no_media:
        await extract_audio_file(html, tmp_path / "a.mp3", max_duration=60)
    assert no_media.value.code == "NOT_MEDIA"

    playlist = tmp_path / "list.m3u8"
    playlist.write_text("#EXTM3U\n#EXTINF:1,\nhttp://cdn.example.com/a.ts\n", encoding="utf-8")
    assert looks_like_playlist(playlist)
    with pytest.raises(AppError) as hls:
        await extract_audio_file(playlist, tmp_path / "b.mp3", max_duration=60)
    assert hls.value.code == "HLS"

    src = tmp_path / "long.mp4"
    build_tone_mp4(src)
    with pytest.raises(AppError) as too_long:
        await extract_audio_file(src, tmp_path / "c.mp3", max_duration=0)
    assert too_long.value.code == "TOO_LONG"
