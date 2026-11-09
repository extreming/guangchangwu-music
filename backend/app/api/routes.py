from __future__ import annotations

import json
import re
import shutil
import time

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from urllib.parse import quote

from app.config import Settings
from app.errors import AppError
from app.services.extract import extract_from_text

_ID = re.compile(r"^[a-f0-9]{32}$")


class ExtractIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


def client_ip(request: Request, settings: Settings) -> str:
    if settings.trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def register_routes(app: FastAPI) -> None:
    @app.get("/")
    async def root() -> dict:
        return {
            "name": "广场舞音乐",
            "hint": "这是小程序的服务器。请用微信开发者工具打开项目。",
            "health": "/api/health",
        }

    @app.get("/api/health")
    async def health() -> dict:
        ready = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
        return {"status": "ok", "ffmpeg": ready}

    @app.post("/api/extract")
    async def extract(request: Request, payload: ExtractIn) -> dict:
        settings: Settings = request.app.state.settings
        if settings.api_token and request.headers.get("x-api-token", "") != settings.api_token:
            raise AppError("服务器拒绝了请求。请让家人检查小程序里的口令。", "UNAUTHORIZED", 401)
        await request.app.state.limiter.hit(client_ip(request, settings))
        text = payload.text.strip()
        if not text:
            raise AppError("请先粘贴分享链接。", "NO_URL")
        fetcher = request.app.state.fetcher_factory()
        try:
            return await extract_from_text(text, fetcher, settings)
        finally:
            await fetcher.aclose()

    @app.get("/api/files/{file_id}")
    async def download_file(file_id: str, request: Request):
        if not _ID.fullmatch(file_id):
            raise AppError("找不到这个音乐。", "NOT_FOUND", 404)
        settings: Settings = request.app.state.settings
        meta_path = settings.data_dir / f"{file_id}.json"
        audio_path = settings.data_dir / f"{file_id}.mp3"
        if not meta_path.is_file() or not audio_path.is_file():
            raise AppError("音乐已过期，请重新提取。", "NOT_FOUND", 404)
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            created = float(meta.get("created_ts") or 0)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise AppError("音乐已过期，请重新提取。", "NOT_FOUND", 404) from exc
        if time.time() - created > settings.file_ttl_seconds:
            audio_path.unlink(missing_ok=True)
            meta_path.unlink(missing_ok=True)
            raise AppError("音乐已过期，请重新提取。", "NOT_FOUND", 404)
        filename = str(meta.get("filename") or "音乐.mp3")
        disposition = "attachment; filename=\"audio.mp3\"; filename*=UTF-8''" + quote(filename)
        return FileResponse(
            audio_path,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": disposition,
                "Cache-Control": "private, max-age=600",
            },
        )
