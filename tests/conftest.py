"""Shared fixtures for the test suite."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def fake_takeout(tmp_path):
    """
    Create a minimal Takeout directory structure:
      tmp_path/Takeout1/Google Photos/Album1/
        photo.jpg          (1x1 white JPEG)
        photo.jpg.json     (sidecar with title + photoTakenTime)
        video.mp4          (dummy bytes)
        metadata.json      (album metadata — should be skipped)
    """
    album_dir = tmp_path / "Takeout1" / "Google Photos" / "Album1"
    album_dir.mkdir(parents=True)

    # Minimal JPEG (1x1 white pixel, no EXIF)
    # This is a valid minimal JPEG
    jpeg_bytes = (
        b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
        b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
        b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342'
        b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00'
        b'\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b'
        b'\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04'
        b'\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07'
        b'\x22q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16'
        b'\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz'
        b'\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99'
        b'\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7'
        b'\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5'
        b'\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1'
        b'\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa'
        b'\xff\xda\x00\x08\x01\x01\x00\x00?\x00T\xdb\xa8\xa0\x03\xa8\xa0\x02\x80'
        b'\xff\xd9'
    )
    (album_dir / "photo.jpg").write_bytes(jpeg_bytes)

    # JSON sidecar
    sidecar = {
        "title": "photo.jpg",
        "photoTakenTime": {"timestamp": "1589155200"},  # 2020-05-11 00:00:00 UTC
        "creationTime": {"timestamp": "1589241600"},
        "geoData": {"latitude": 48.8566, "longitude": 2.3522},
        "people": [{"name": "Alice"}],
        "description": "A test photo",
    }
    (album_dir / "photo.jpg.json").write_text(json.dumps(sidecar), encoding="utf-8")

    # Dummy video
    (album_dir / "video.mp4").write_bytes(b"\x00" * 100)

    # Album metadata (should be skipped by indexer)
    (album_dir / "metadata.json").write_text('{"title": "Album1"}', encoding="utf-8")

    return tmp_path


@pytest.fixture
def output_dir(tmp_path):
    """Provide a clean output directory."""
    out = tmp_path / "output"
    out.mkdir()
    return out
