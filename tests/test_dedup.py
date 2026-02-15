"""Tests for degoogle_photos.dedup."""

from datetime import datetime
from pathlib import Path

from degoogle_photos.dedup import compute_md5, make_dedup_key


def test_compute_md5(tmp_path):
    f = tmp_path / "test.bin"
    f.write_bytes(b"hello world")
    md5 = compute_md5(f)
    assert md5 == "5eb63bbbe01eeed093cb22bb8f5acdc3"


def test_compute_md5_different_content(tmp_path):
    f1 = tmp_path / "a.bin"
    f2 = tmp_path / "b.bin"
    f1.write_bytes(b"aaa")
    f2.write_bytes(b"bbb")
    assert compute_md5(f1) != compute_md5(f2)


def test_make_dedup_key_with_date():
    dt = datetime(2020, 5, 10, 14, 30, 45)
    key = make_dedup_key("abc123", dt)
    # Seconds should be rounded to 0
    assert key == ("abc123", "2020-05-10T14:30:00")


def test_make_dedup_key_without_date():
    key = make_dedup_key("abc123", None)
    assert key == ("abc123", None)


def test_make_dedup_key_same_minute_different_seconds():
    dt1 = datetime(2020, 5, 10, 14, 30, 10)
    dt2 = datetime(2020, 5, 10, 14, 30, 55)
    assert make_dedup_key("abc", dt1) == make_dedup_key("abc", dt2)
