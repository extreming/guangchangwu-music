"""HTTP fetch with a hard stop on private addresses."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

from app.errors import AppError, FetchError
from app.parsers.base import kind_from_content_type, media_kind_from_url

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept": "*/*",
}

REDIRECTS = {301, 302, 303, 307, 308}
BLOCKED_HOSTS = {"localhost", "metadata.google.internal", "metadata.google"}
BLOCKED_SUFFIXES = (".localhost", ".local", ".internal")

Resolver = Callable[[str], Awaitable[list[ipaddress.IPv4Address | ipaddress.IPv6Address]]]


async def default_resolver(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    def lookup() -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        try:
            infos = socket.getaddrinfo(hostname, None)
        except socket.gaierror as exc:
            raise AppError("这个链接的网站找不到。", "DNS") from exc
        ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
        for info in infos:
            try:
                ips.append(ipaddress.ip_address(info[4][0]))
            except ValueError:
                continue
        return ips

    import asyncio

    return await asyncio.to_thread(lookup)


def _bad_url() -> AppError:
    return AppError("这个链接不能用。请复制视频的分享链接。", "BAD_URL")


def _blocked() -> AppError:
    return AppError("这个链接不能用。请换一个分享链接。", "BLOCKED")


class _OpenResponse:
    def __init__(self, cm, response: httpx.Response, final_url: str):
        self._cm = cm
        self.response = response
        self.final_url = final_url

    @property
    def status_code(self) -> int:
        return self.response.status_code

    @property
    def headers(self) -> httpx.Headers:
        return self.response.headers

    @property
    def content_type(self) -> str:
        return self.response.headers.get("content-type", "")

    def aiter_bytes(self):
        return self.response.aiter_bytes()

    async def __aenter__(self) -> _OpenResponse:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._cm.__aexit__(exc_type, exc, tb)


@dataclass
class Peek:
    final_url: str
    content_type: str
    snippet: str
    is_media: bool


class Fetcher:
    def __init__(self, client: httpx.AsyncClient, resolver: Resolver | None = None, own: bool = False):
        self.client = client
        self.resolver = resolver or default_resolver
        self.own = own

    async def aclose(self) -> None:
        if self.own:
            await self.client.aclose()

    def merge(self, extra: dict[str, str] | None) -> dict[str, str]:
        headers = dict(DEFAULT_HEADERS)
        if extra:
            headers.update(extra)
        return headers

    async def ensure_safe(self, url: str) -> None:
        if len(url) > 2000:
            raise AppError("链接太长了，请重新复制。", "BAD_URL")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
            raise _bad_url()
        host = parsed.hostname
        if not host:
            raise _bad_url()
        try:
            host_ascii = host.encode("idna").decode("ascii").lower().rstrip(".")
        except UnicodeError as exc:
            raise _bad_url() from exc
        if host_ascii in BLOCKED_HOSTS or host_ascii.endswith(BLOCKED_SUFFIXES):
            raise _blocked()
        ips = await self._ips_for(host_ascii)
        if not ips:
            raise AppError("这个链接的网站找不到。", "DNS")
        for ip in ips:
            if not ip.is_global:
                raise _blocked()

    async def _ips_for(self, host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        if host.isdigit():
            try:
                return [ipaddress.ip_address(int(host))]
            except ValueError:
                return []
        try:
            return [ipaddress.ip_address(host)]
        except ValueError:
            pass
        return await self.resolver(host)

    async def open(self, url: str, headers: dict[str, str] | None = None, max_hops: int = 5) -> _OpenResponse:
        current = url
        visited: set[str] = set()
        for hop in range(max_hops + 1):
            if current in visited:
                raise AppError("链接跳转来回转圈，请换一个。", "REDIRECT")
            visited.add(current)
            await self.ensure_safe(current)
            cm = self.client.stream(
                "GET",
                current,
                headers=self.merge(headers),
                follow_redirects=False,
            )
            try:
                response = await cm.__aenter__()
            except httpx.TimeoutException as exc:
                raise FetchError("网站响应太慢，请稍后再试。", "TIMEOUT", 504) from exc
            except httpx.HTTPError as exc:
                raise FetchError("打不开这个链接，请重新复制分享。", "FETCH_FAILED") from exc
            if response.status_code in REDIRECTS and hop < max_hops:
                location = response.headers.get("location")
                await cm.__aexit__(None, None, None)
                if not location:
                    raise FetchError("链接跳转失败，请重新复制分享。", "REDIRECT")
                current = urljoin(str(response.url), location.strip())
                continue
            if response.status_code in REDIRECTS:
                await cm.__aexit__(None, None, None)
                raise AppError("链接转了太多次，没能打开。", "REDIRECT")
            return _OpenResponse(cm, response, str(response.url))
        raise AppError("链接转了太多次，没能打开。", "REDIRECT")

    def _raise_for_status(self, status: int) -> None:
        if status < 400:
            return
        if status == 404:
            raise FetchError("链接已经失效，请重新分享一次。", "UPSTREAM", 502)
        if status in {401, 403, 429}:
            raise FetchError("网站拒绝了访问，请稍后再试。", "UPSTREAM", 502)
        raise FetchError("网站暂时打不开，请稍后再试。", "UPSTREAM", 502)

    async def read_bytes(self, url: str, headers: dict[str, str] | None = None, limit: int = 1_500_000) -> bytes:
        async with await self.open(url, headers) as opened:
            self._raise_for_status(opened.status_code)
            buf = bytearray()
            async for chunk in opened.aiter_bytes():
                buf.extend(chunk)
                if len(buf) > limit:
                    raise AppError("页面太大，没能读完。", "TOO_LARGE", 400)
            return bytes(buf)

    async def get_text(self, url: str, headers: dict[str, str] | None = None, limit: int = 1_500_000) -> str:
        data = await self.read_bytes(url, headers=headers, limit=limit)
        return data.decode("utf-8", "replace")

    async def get_json(self, url: str, headers: dict[str, str] | None = None):
        text = await self.get_text(url, headers=headers, limit=2_000_000)
        import json

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise FetchError("网站返回的内容看不懂。", "BAD_RESPONSE") from exc
        if not isinstance(data, (dict, list)):
            raise FetchError("网站返回的内容看不懂。", "BAD_RESPONSE")
        return data

    async def peek(self, url: str, headers: dict[str, str] | None = None) -> Peek:
        async with await self.open(url, headers) as opened:
            self._raise_for_status(opened.status_code)
            content_type = opened.content_type
            if kind_from_content_type(content_type) or media_kind_from_url(opened.final_url):
                return Peek(opened.final_url, content_type, "", True)
            buf = bytearray()
            async for chunk in opened.aiter_bytes():
                buf.extend(chunk)
                if len(buf) >= 8192:
                    break
            return Peek(opened.final_url, content_type, bytes(buf).decode("utf-8", "replace"), False)

    async def expand(self, url: str, headers: dict[str, str] | None = None) -> str:
        current = url
        for _ in range(6):
            await self.ensure_safe(current)
            if media_kind_from_url(current):
                return current
            info = await self.peek(current, headers)
            if info.is_media:
                return info.final_url or current
            nxt = find_meta_redirect(info.snippet, info.final_url or current)
            if nxt and nxt != current:
                current = nxt
                continue
            return info.final_url or current
        return current

    async def download(self, url: str, dest: Path, headers: dict[str, str] | None, limit: int) -> str:
        async with await self.open(url, headers) as opened:
            self._raise_for_status(opened.status_code)
            dest.parent.mkdir(parents=True, exist_ok=True)
            total = 0
            try:
                with dest.open("wb") as handle:
                    async for chunk in opened.aiter_bytes():
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > limit:
                            raise AppError("文件太大了，请换一个短一点的视频。", "TOO_LARGE", 400)
                        handle.write(chunk)
            except AppError:
                dest.unlink(missing_ok=True)
                raise
            if total == 0:
                dest.unlink(missing_ok=True)
                raise FetchError("没有下载到内容。请重新分享一次。", "FETCH_FAILED")
            return opened.final_url


def find_meta_redirect(html: str, base: str) -> str | None:
    if not html:
        return None
    import re

    patterns = (
        re.compile(
            r"""http-equiv=["']refresh["'][^>]*content=["'][^"']*?url=([^"'>\s]+)""",
            re.IGNORECASE,
        ),
        re.compile(
            r"""content=["'][^"']*?url=([^"'>\s]+)["'][^>]*http-equiv=["']refresh["']""",
            re.IGNORECASE,
        ),
        re.compile(r"""location\.(?:replace|href)\s*(?:=|\()\s*["'](https?://[^"']+)""", re.IGNORECASE),
    )
    for pattern in patterns:
        match = pattern.search(html)
        if match:
            return urljoin(base, match.group(1).strip())
    return None


def default_fetcher_factory() -> Fetcher:
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(60.0, connect=10.0),
        follow_redirects=False,
        trust_env=False,
        headers=DEFAULT_HEADERS,
    )
    return Fetcher(client, own=True)
