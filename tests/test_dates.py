"""Tests for degoogle_photos.dates."""

import json
from datetime import datetime
from pathlib import Path

from degoogle_photos.dates import (
    extract_date,
    _date_from_filename,
    _date_from_json_field,
    _date_from_mtime,
    _load_json,
    FILENAME_DATE_PATTERNS,
)


def test_date_from_filename_yyyymmdd_hhmmss():
    dt = _date_from_filename("IMG_20200510_204759.jpg")
    assert dt == datetime(2020, 5, 10)


def test_date_from_filename_dashed():
    dt = _date_from_filename("2021-03-15_14-30-00.jpg")
    assert dt == datetime(2021, 3, 15)


def test_date_from_filename_yyyymmdd_only():
    dt = _date_from_filename("photo_20190801.jpg")
    assert dt == datetime(2019, 8, 1)


def test_date_from_filename_no_match():
    assert _date_from_filename("random_photo.jpg") is None


def test_date_from_filename_invalid_date():
    # Month 13 is invalid
    assert _date_from_filename("IMG_20201301_120000.jpg") is None


def test_date_from_json_field_valid():
    data = {"photoTakenTime": {"timestamp": "1589155200"}}
    dt = _date_from_json_field(data, "photoTakenTime")
    assert dt is not None
    assert dt.year == 2020
    assert dt.month == 5


def test_date_from_json_field_missing():
    assert _date_from_json_field({}, "photoTakenTime") is None


def test_date_from_json_field_zero_timestamp():
    data = {"photoTakenTime": {"timestamp": "0"}}
    assert _date_from_json_field(data, "photoTakenTime") is None


def test_date_from_mtime(tmp_path):
    f = tmp_path / "test.jpg"
    f.write_bytes(b"\xff\xd8\xff\xd9")
    dt = _date_from_mtime(f)
    assert dt is not None
    assert dt.year >= 2020


def test_load_json_valid(tmp_path):
    f = tmp_path / "test.json"
    f.write_text('{"title": "photo.jpg"}', encoding="utf-8")
    data = _load_json(f)
    assert data["title"] == "photo.jpg"


def test_load_json_corrupt(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("not json at all", encoding="utf-8")
    assert _load_json(f) is None


def test_load_json_nonexistent(tmp_path):
    assert _load_json(tmp_path / "nope.json") is None


def test_extract_date_json_taken(tmp_path):
    """JSON photoTakenTime should be used when EXIF is unavailable."""
    media = tmp_path / "video.mp4"
    media.write_bytes(b"\x00" * 10)
    json_path = tmp_path / "video.mp4.json"
    json_path.write_text(json.dumps({
        "photoTakenTime": {"timestamp": "1589155200"},
    }), encoding="utf-8")
    dt, source = extract_date(media, json_path)
    assert source == "json_taken"
    assert dt.year == 2020


def test_extract_date_filename_fallback(tmp_path):
    """Filename pattern should be used when no JSON is available."""
    media = tmp_path / "IMG_20200510_204759.mp4"
    media.write_bytes(b"\x00" * 10)
    dt, source = extract_date(media, None)
    assert source == "filename"
    assert dt == datetime(2020, 5, 10)


def test_extract_date_mtime_fallback(tmp_path):
    """File mtime should be the last resort."""
    media = tmp_path / "random_video.mp4"
    media.write_bytes(b"\x00" * 10)
    dt, source = extract_date(media, None)
    assert source == "mtime"
    assert dt is not None
