import json

from app.services.cleanup import cleanup_expired


def test_cleanup_removes_expired_and_keeps_fresh(tmp_path):
    old_id = "a" * 32
    new_id = "b" * 32
    (tmp_path / f"{old_id}.json").write_text(
        json.dumps({"id": old_id, "format": "mp3", "created_ts": 0, "filename": "旧.mp3"}),
        encoding="utf-8",
    )
    (tmp_path / f"{old_id}.mp3").write_bytes(b"old")
    (tmp_path / f"{new_id}.json").write_text(
        json.dumps({"id": new_id, "format": "mp3", "created_ts": 1_000, "filename": "新.mp3"}),
        encoding="utf-8",
    )
    (tmp_path / f"{new_id}.mp3").write_bytes(b"new")

    removed = cleanup_expired(tmp_path, ttl_seconds=10, now=100)
    assert removed == 1
    assert not (tmp_path / f"{old_id}.mp3").exists()
    assert (tmp_path / f"{new_id}.mp3").exists()

    kept = cleanup_expired(tmp_path, ttl_seconds=100, now=1050)
    assert kept == 0
    assert (tmp_path / f"{new_id}.mp3").exists()
