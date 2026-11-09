from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import register_routes
from app.config import Settings
from app.errors import AppError
from app.services.cleanup import cleanup_expired
from app.services.fetcher import default_fetcher_factory
from app.services.rate_limit import RateLimiter

logger = logging.getLogger(__name__)


async def _cleanup_loop(settings: Settings) -> None:
    try:
        while True:
            await asyncio.sleep(settings.cleanup_interval_seconds)
            cleanup_expired(settings.data_dir, settings.file_ttl_seconds)
    except asyncio.CancelledError:
        return


def create_app(settings: Settings | None = None, fetcher_factory=None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(_cleanup_loop(settings))
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="广场舞音乐", lifespan=lifespan)
    app.state.settings = settings
    app.state.limiter = RateLimiter(settings.rate_limit_count, settings.rate_limit_window_seconds)
    app.state.fetcher_factory = fetcher_factory or default_fetcher_factory
    register_routes(app)

    @app.exception_handler(AppError)
    async def on_app_error(_request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status,
            content={"error": exc.message, "code": exc.code},
        )

    @app.exception_handler(RequestValidationError)
    async def on_validation(_request: Request, _exc: RequestValidationError):
        return JSONResponse(
            status_code=400,
            content={"error": "请粘贴分享文字后再试。", "code": "BAD_REQUEST"},
        )

    @app.exception_handler(Exception)
    async def on_unexpected(_request: Request, exc: Exception):
        logger.exception("extract crashed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": "提取失败，请稍后再试。", "code": "INTERNAL"},
        )

    return app


app = create_app()
