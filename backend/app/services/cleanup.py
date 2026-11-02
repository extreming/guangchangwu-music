from __future__ import annotations

import json
import time
from pathlib import Path


def cleanup_expired(root: Path, ttl_seconds: int, now: float | None = None) -> int:
    if not root.exists():
        return 0
    moment = time.time() if now is None else now
    removed = 0
    for meta_path in root.glob("*.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            created = float(meta.get("created_ts") or 0)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if moment - created <= ttl_seconds:
            continue
        file_id = str(meta.get("id") or meta_path.stem)
        ext = str(meta.get("format") or "mp3")
        audio = root / f"{file_id}.{ext}"
        audio.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
        removed += 1
    for pattern in ("*.mp3", "*.m4a", "*.bin"):
        for audio in root.glob(pattern):
            meta_path = root / f"{audio.stem}.json"
            if meta_path.exists():
                continue
            try:
                stale = moment - audio.stat().st_mtime > ttl_seconds
            except OSError:
                continue
            if stale:
                audio.unlink(missing_ok=True)
                removed += 1
    tmp = root / "tmp"
    if tmp.exists():
        for leftover in tmp.glob("*"):
            try:
                stale = moment - leftover.stat().st_mtime > ttl_seconds
            except OSError:
                continue
            if stale and leftover.is_file():
                leftover.unlink(missing_ok=True)
                removed += 1
    return removed
