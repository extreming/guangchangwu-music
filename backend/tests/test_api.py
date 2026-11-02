import subprocess
from urllib.parse import quote

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import make_fetcher

DOUYIN_ID = "7123456789012345678"


def _app(tmp_path, handler=None, **kwargs):
    settings = Settings(data_dir=tmp_path, public_base_url="http://testserver", cleanup_interval_seconds=3600, **kwargs)

    def factory():
        if handler is None:
            return make_fetcher(lambda request: httpx.Response(404))
        return make_fetcher(handler)

    return create_app(settings=settings, fetcher_factory=factory)


def test_health_and_plain_errors(tmp_path):
    app = _app(tmp_path)
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["ffmpeg"] is True
        missing = client.post("/api/extract", json={"text": "今天一起跳舞，没有链接"})
        assert missing.status_code == 400
        assert missing.json()["code"] == "NO_URL"
        assert "没有找到链接" in missing.json()["error"]
        blocked = client.post("/api/extract", json={"text": "http://169.254.169.254/latest/meta-data"})
        assert blocked.status_code == 400
        assert blocked.json()["code"] == "BLOCKED"
        private_audio = client.post("/api/extract", json={"text": "http://10.1.2.3/secret.mp3"})
        assert private_audio.status_code == 400
        assert private_audio.json()["code"] == "BLOCKED"
        bad = client.post("/api/extract", json={})
        assert bad.status_code == 400
        assert bad.json()["code"] == "BAD_REQUEST"
        missing_file = client.get("/api/files/" + "c" * 32)
        assert missing_file.status_code == 404
        weird = client.get("/api/files/not-valid")
        assert weird.status_code == 404


def test_rate_limit(tmp_path):
    app = _app(tmp_path, rate_limit_count=2)
    with TestClient(app) as client:
        assert client.post("/api/extract", json={"text": "没有链接"}).status_code == 400
        assert client.post("/api/extract", json={"text": "没有链接"}).status_code == 400
        limited = client.post("/api/extract", json={"text": "没有链接"})
        assert limited.status_code == 429
        assert "等一分钟" in limited.json()["error"]


def test_api_token(tmp_path):
    app = _app(tmp_path, api_token="family-token")
    with TestClient(app) as client:
        denied = client.post("/api/extract", json={"text": "https://v.douyin.com/abc/"})
        assert denied.status_code == 401
        allowed = client.post(
            "/api/extract",
            json={"text": "今天没有链接"},
            headers={"X-Api-Token": "family-token"},
        )
        assert allowed.status_code == 400
        assert allowed.json()["code"] == "NO_URL"


def test_falls_back_to_video_when_audio_url_is_html(tmp_path, tiny_mp4: bytes):
    payload = {
        "item_list": [
            {
                "aweme_id": DOUYIN_ID,
                "desc": "幸福舞步",
                "music": {"title": "幸福舞步", "play_url": {"url_list": ["https://cdn.example.com/song.mp3"]}},
                "video": {"play_addr": {"url_list": ["https://cdn.example.com/dance.mp4"]}},
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "iteminfo" in url:
            return httpx.Response(200, json=payload)
        if url.endswith("song.mp3"):
            return httpx.Response(200, text="<!DOCTYPE html><html>blocked</html>", headers={"content-type": "text/html"})
        if url.endswith("dance.mp4"):
            return httpx.Response(200, content=tiny_mp4, headers={"content-type": "video/mp4"})
        return httpx.Response(200, text="<html></html>", headers={"content-type": "text/html"})

    app = _app(tmp_path, handler=handler, rate_limit_count=20)
    page = f"https://www.douyin.com/video/{DOUYIN_ID}"
    with TestClient(app) as client:
        response = client.post("/api/extract", json={"text": page})
        assert response.status_code == 200, response.text
        assert response.json()["title"] == "幸福舞步"
        assert response.json()["filename"].endswith(".mp3")


def test_extract_douyin_video_to_mp3(tmp_path, tiny_mp4: bytes):
    payload = {
        "status_code": 0,
        "item_list": [
            {
                "aweme_id": DOUYIN_ID,
                "desc": "夕阳红广场舞 #广场舞",
                "video": {
                    "duration": 180000,
                    "play_addr": {"url_list": ["https://cdn.example.com/dance.mp4"]},
                },
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if host == "v.douyin.com":
            return httpx.Response(
                302,
                headers={"location": f"https://www.iesdouyin.com/share/video/{DOUYIN_ID}/"},
            )
        if "iteminfo" in str(request.url):
            return httpx.Response(200, json=payload)
        if host == "www.iesdouyin.com":
            return httpx.Response(200, text="<html>share</html>", headers={"content-type": "text/html"})
        if host == "cdn.example.com":
            return httpx.Response(200, content=tiny_mp4, headers={"content-type": "video/mp4"})
        return httpx.Response(404, text="missing")

    app = _app(tmp_path, handler=handler, rate_limit_count=20)
    text = f"5.20 复制打开抖音，看看【王阿姨的作品】舞 https://v.douyin.com/dance1/"
    with TestClient(app) as client:
        response = client.post("/api/extract", json={"text": text})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["title"] == "夕阳红广场舞"
        assert body["filename"] == "夕阳红广场舞.mp3"
        assert body["platform"] == "douyin"
        assert body["platform_label"] == "抖音"
        assert body["format"] == "mp3"
        assert body["duration"] >= 1
        audio = client.get(f"/api/files/{body['id']}")
        assert audio.status_code == 200
        assert audio.headers["content-type"].startswith("audio/mpeg")
        disposition = audio.headers["content-disposition"]
        assert quote("夕阳红广场舞.mp3") in disposition
        out = tmp_path / "played.mp3"
        out.write_bytes(audio.content)
        probed = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "csv=p=0",
                str(out),
            ],
            capture_output=True,
            check=True,
        )
        assert probed.stdout.decode().strip() == "mp3"
