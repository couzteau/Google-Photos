"""Tests for google_photos_migrate.metadata."""

import json
from pathlib import Path

from google_photos_migrate.metadata import extract_metadata


def test_extract_metadata_nonexistent_file(tmp_path):
    fake = tmp_path / "nope.jpg"
    meta = extract_metadata(fake, None)
    assert meta == {}


def test_extract_metadata_json_fields(tmp_path):
    media = tmp_path / "video.mp4"
    media.write_bytes(b"\x00" * 10)
    sidecar = tmp_path / "video.mp4.json"
    sidecar.write_text(json.dumps({
        "photoTakenTime": {"timestamp": "1589155200"},
        "creationTime": {"timestamp": "1589241600"},
        "geoData": {"latitude": 48.8566, "longitude": 2.3522},
        "people": [{"name": "Alice"}, {"name": "Bob"}],
        "description": "A lovely day",
    }), encoding="utf-8")
    meta = extract_metadata(media, sidecar)
    assert "photoTakenTime" in meta
    assert "geo" in meta
    assert "Alice" in meta["people"]
    assert "Bob" in meta["people"]
    assert meta["description"] == "A lovely day"


def test_extract_metadata_corrupt_json(tmp_path):
    media = tmp_path / "photo.jpg"
    media.write_bytes(b"\xff\xd8\xff\xd9")
    bad_json = tmp_path / "photo.jpg.json"
    bad_json.write_text("{{not valid json", encoding="utf-8")
    meta = extract_metadata(media, bad_json)
    # Should not crash, just return whatever EXIF extraction found (or empty)
    assert isinstance(meta, dict)
