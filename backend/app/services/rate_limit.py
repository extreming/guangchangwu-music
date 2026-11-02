from __future__ import annotations

import time
from collections import defaultdict, deque

from app.errors import AppError


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def hit(self, key: str) -> None:
        now = time.monotonic()
        bucket = self._hits[key]
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()
        if len(bucket) >= self.limit:
            raise AppError("操作太频繁，请等一分钟再试。", "RATE_LIMIT", 429)
        bucket.append(now)
