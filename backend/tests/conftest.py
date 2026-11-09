from __future__ import annotations

import ipaddress
import subprocess
from pathlib import Path

import httpx
import pytest

from app.services.fetcher import Fetcher


async def fake_resolver(hostname: str):
    host = hostname.lower().rstrip(".")
    if host in {"localhost", "127.0.0.1", "::1", "169.254.169.254", "0.0.0.0"} or host.endswith(".internal"):
        return [ipaddress.ip_address("127.0.0.1")]
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        return [ipaddress.ip_address("93.184.216.34")]


def make_fetcher(handler) -> Fetcher:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, follow_redirects=False, trust_env=False)
    return Fetcher(client, resolver=fake_resolver, own=True)


def build_tone_mp4(path: Path) -> None:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=64x64:d=1",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            str(path),
        ],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace")[-2000:])


@pytest.fixture(scope="session")
def tiny_mp4(tmp_path_factory) -> bytes:
    path = tmp_path_factory.mktemp("media") / "tone.mp4"
    build_tone_mp4(path)
    return path.read_bytes()
