from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    public_base_url: str = "http://127.0.0.1:8765"
    max_download_bytes: int = 100 * 1024 * 1024
    max_duration_seconds: int = 20 * 60
    file_ttl_seconds: int = 7200
    rate_limit_count: int = 10
    rate_limit_window_seconds: int = 60
    trust_proxy: bool = False
    api_token: str = ""
    cleanup_interval_seconds: int = 60

    @property
    def tmp_dir(self) -> Path:
        return self.data_dir / "tmp"

    @classmethod
    def from_env(cls) -> Settings:
        root = Path(__file__).resolve().parents[1]
        data = Path(os.environ.get("DATA_DIR", str(root / "data")))
        return cls(
            data_dir=data,
            public_base_url=os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1:8765").rstrip("/"),
            max_download_bytes=int(os.environ.get("MAX_DOWNLOAD_MB", "100")) * 1024 * 1024,
            max_duration_seconds=int(os.environ.get("MAX_DURATION_SECONDS", str(20 * 60))),
            file_ttl_seconds=int(os.environ.get("FILE_TTL_SECONDS", "7200")),
            rate_limit_count=int(os.environ.get("RATE_LIMIT_PER_MINUTE", "10")),
            rate_limit_window_seconds=int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60")),
            trust_proxy=os.environ.get("TRUST_PROXY", "").lower() in {"1", "true", "yes"},
            api_token=os.environ.get("API_TOKEN", ""),
            cleanup_interval_seconds=int(os.environ.get("CLEANUP_INTERVAL_SECONDS", "60")),
        )
