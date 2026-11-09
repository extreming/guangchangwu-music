import json
from pathlib import Path
from urllib.parse import quote

import httpx
import pytest

from app.errors import AppError
from app.parsers.douyin import find_item_id, parse_douyin_html, parse_douyin_json, resolve as resolve_douyin
from app.parsers.generic import parse_html_media, resolve as resolve_generic
from app.parsers.huoshan import parse_huoshan_json, resolve as resolve_huoshan
from app.parsers.kuaishou import parse_kuaishou_html, resolve as resolve_kuaishou
from tests.conftest import make_fetcher

FIXTURES = Path(__file__).parent / "fixtures"


def test_douyin_prefers_music_track_and_matching_id():
    data = {
        "item_list": [
            {
                "aweme_id": "11111111",
                "desc": "别选我",
                "video": {"play_addr": {"url_list": ["https://cdn.example.com/wrong.mp4"]}},
            },
            {
                "aweme_id": "22222222",
                "desc": "夕阳红广场舞 #广场舞",
                "music": {
                    "title": "原曲",
                    "play_url": {"url_list": ["https://cdn.example.com/right.mp3"]},
                },
                "video": {"duration": 180000, "play_addr": {"url_list": ["https://cdn.example.com/right.mp4"]}},
            },
        ]
    }
    parsed = parse_douyin_json(data, item_id="22222222")
    assert parsed is not None
    assert parsed.media_url == "https://cdn.example.com/right.mp3"
    assert parsed.media_kind == "audio"
    assert parsed.fallback_url == "https://cdn.example.com/right.mp4"
    assert parsed.title == "夕阳红广场舞 #广场舞"
    assert parsed.platform == "douyin"


def test_douyin_hashtags_fall_back_to_song_name():
    data = {
        "aweme_id": "33333333",
        "desc": "#广场舞",
        "music": {"title": "幸福舞步", "play_url": {"url_list": ["https://cdn.example.com/a.mp3"]}},
        "video": {"play_addr": {"url_list": ["https://cdn.example.com/a.mp4"]}},
    }
    parsed = parse_douyin_json(data, item_id="33333333")
    assert parsed is not None
    assert parsed.title == "幸福舞步"
    assert parsed.media_url.endswith("a.mp3")


def test_douyin_render_data_html():
    payload = {
        "app": {
            "videoInfoRes": {
                "item_list": [
                    {
                        "aweme_id": "7123456789012345678",
                        "desc": "幸福舞步教学",
                        "video": {"play_addr": {"url_list": ["https://cdn.example.com/from-html.mp4"]}},
                    }
                ]
            }
        }
    }
    encoded = quote(json.dumps(payload, ensure_ascii=False))
    html = f'<html><script id="RENDER_DATA" type="application/json">{encoded}</script></html>'
    parsed = parse_douyin_html(html, item_id="7123456789012345678")
    assert parsed is not None
    assert parsed.media_url == "https://cdn.example.com/from-html.mp4"
    assert find_item_id("https://www.iesdouyin.com/share/video/7123456789012345678/") == "7123456789012345678"


def test_huoshan_item_json():
    data = {
        "data": {
            "item_info": {
                "item_id": "99887766",
                "description": "火山版夕阳红广场舞",
                "video": {"duration": 90, "url_list": ["https://cdn.example.com/sun.mp4"]},
                "music": {"title": "夕阳红", "play_url": {"url_list": ["https://cdn.example.com/sun.m4a"]}},
            }
        }
    }
    parsed = parse_huoshan_json(data, item_id="99887766")
    assert parsed is not None
    assert parsed.platform == "huoshan"
    assert parsed.media_url == "https://cdn.example.com/sun.m4a"
    assert parsed.fallback_url == "https://cdn.example.com/sun.mp4"
    assert parsed.title == "火山版夕阳红广场舞"


def test_kuaishou_fixture_page():
    html = (FIXTURES / "kuaishou_page.html").read_text(encoding="utf-8")
    parsed = parse_kuaishou_html(html)
    assert parsed is not None
    assert parsed.platform == "kuaishou"
    assert parsed.media_url == "https://cdn.example.com/ks.m4a"
    assert parsed.fallback_url == "https://cdn.example.com/ks.mp4"
    assert "夕阳红广场舞" in parsed.title


def test_generic_html_fixtures():
    audio_html = (FIXTURES / "generic_audio.html").read_text(encoding="utf-8")
    audio = parse_html_media(audio_html, "https://music.example/listen")
    assert audio is not None
    assert audio.media_url == "https://cdn.example.com/party.mp3"
    assert audio.media_kind == "audio"
    assert audio.title == "社区晚会舞曲"

    video_html = (FIXTURES / "generic_video.html").read_text(encoding="utf-8")
    video = parse_html_media(video_html, "https://music.example/watch")
    assert video is not None
    assert video.media_kind == "video"
    assert video.media_url == "https://cdn.example.com/show.mp4"

    relative = parse_html_media(
        "<html><head><title>相对</title></head><body><audio src=\"/song.mp3\"></audio></body></html>",
        "https://music.example/listen",
    )
    assert relative is not None
    assert relative.media_url == "https://music.example/song.mp3"

    ld = parse_html_media((FIXTURES / "generic_jsonld.html").read_text(encoding="utf-8"), "https://music.example/")
    assert ld is not None
    assert ld.media_url == "https://cdn.example.com/ld.mp3"


@pytest.mark.asyncio
async def test_douyin_resolve_falls_back_to_html():
    payload = {
        "item_list": [
            {
                "aweme_id": "7123456789012345678",
                "desc": "老街舞步",
                "video": {"play_addr": {"url_list": ["https://cdn.example.com/oldstreet.mp4"]}},
            }
        ]
    }
    html = (
        '<html><script id="RENDER_DATA" type="application/json">'
        + quote(json.dumps(payload, ensure_ascii=False))
        + "</script></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if "iteminfo" in str(request.url):
            return httpx.Response(200, json={"status_code": 0, "item_list": []})
        if "share/video" in str(request.url):
            return httpx.Response(200, text=html, headers={"content-type": "text/html"})
        return httpx.Response(404)

    fetcher = make_fetcher(handler)
    try:
        source = await resolve_douyin(
            "https://www.iesdouyin.com/share/video/7123456789012345678/",
            fetcher,
        )
    finally:
        await fetcher.aclose()
    assert source.media_url == "https://cdn.example.com/oldstreet.mp4"
    assert source.title == "老街舞步"


@pytest.mark.asyncio
async def test_kuaishou_and_huoshan_and_generic_resolve():
    kuaishou_html = (FIXTURES / "kuaishou_page.html").read_text(encoding="utf-8")
    generic_html = (FIXTURES / "generic_video.html").read_text(encoding="utf-8")
    huoshan = {
        "data": {
            "item_info": {
                "item_id": "55667788",
                "description": "火山舞曲",
                "video": {"url_list": ["https://cdn.example.com/h.mp4"]},
            }
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if host == "v.kuaishou.com":
            return httpx.Response(200, text=kuaishou_html, headers={"content-type": "text/html"})
        if "item/info" in str(request.url):
            return httpx.Response(200, json=huoshan)
        if host == "share.huoshan.com":
            return httpx.Response(200, text="<html>no</html>", headers={"content-type": "text/html"})
        if host == "news.example":
            return httpx.Response(200, text=generic_html, headers={"content-type": "text/html"})
        return httpx.Response(404)

    fetcher = make_fetcher(handler)
    try:
        ks = await resolve_kuaishou("https://v.kuaishou.com/abcd12", fetcher)
        hs = await resolve_huoshan("https://share.huoshan.com/item/55667788", fetcher)
        web = await resolve_generic("https://news.example/article", fetcher)
    finally:
        await fetcher.aclose()
    assert ks.media_url.endswith("ks.m4a")
    assert hs.media_url.endswith("h.mp4")
    assert hs.title == "火山舞曲"
    assert web.media_url.endswith("show.mp4")


@pytest.mark.asyncio
async def test_blocks_private_redirect_and_metadata_ip():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host or "")
        if request.url.host == "evil.example":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})
        return httpx.Response(200, text="secret")

    fetcher = make_fetcher(handler)
    try:
        with pytest.raises(AppError) as blocked:
            await fetcher.expand("https://evil.example/go")
        assert blocked.value.code == "BLOCKED"
        with pytest.raises(AppError):
            await fetcher.expand("http://169.254.169.254/latest/meta-data")
    finally:
        await fetcher.aclose()
    assert "127.0.0.1" not in seen


@pytest.mark.asyncio
async def test_expand_meta_refresh():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "short.example":
            html = (
                '<html><meta http-equiv="refresh" '
                'content="0;url=https://www.douyin.com/video/7123456789012345678"></html>'
            )
            return httpx.Response(200, text=html, headers={"content-type": "text/html"})
        if request.url.host == "www.douyin.com":
            return httpx.Response(200, text="<html>video page</html>", headers={"content-type": "text/html"})
        return httpx.Response(404)

    fetcher = make_fetcher(handler)
    try:
        final = await fetcher.expand("https://short.example/s/1")
    finally:
        await fetcher.aclose()
    assert final == "https://www.douyin.com/video/7123456789012345678"
