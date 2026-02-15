"""Tests for google_photos_migrate.indexing."""

import json
from pathlib import Path

from google_photos_migrate.indexing import (
    find_takeout_dirs,
    build_index,
    _strip_sidecar_suffix,
    find_json_for_media,
)


MEDIA_EXTENSIONS = {".jpg", ".jpeg", ".png", ".mp4", ".mov"}


def test_find_takeout_dirs(fake_takeout):
    dirs = find_takeout_dirs(fake_takeout)
    assert len(dirs) == 1
    assert dirs[0].name == "Google Photos"


def test_find_takeout_dirs_ignores_non_takeout(tmp_path):
    (tmp_path / "NotTakeout" / "Google Photos").mkdir(parents=True)
    (tmp_path / "Takeout1" / "Google Photos").mkdir(parents=True)
    dirs = find_takeout_dirs(tmp_path)
    assert len(dirs) == 1


def test_build_index(fake_takeout):
    dirs = find_takeout_dirs(fake_takeout)
    media, json_idx = build_index(dirs, MEDIA_EXTENSIONS)
    # Should find photo.jpg and video.mp4
    assert len(media) == 2
    names = {p.name for p, _ in media}
    assert "photo.jpg" in names
    assert "video.mp4" in names
    # JSON index should have photo.jpg via title
    assert "photo.jpg" in json_idx["album1"]


def test_build_index_skips_metadata_json(fake_takeout):
    dirs = find_takeout_dirs(fake_takeout)
    _, json_idx = build_index(dirs, MEDIA_EXTENSIONS)
    # metadata.json's title "Album1" should not appear as a media key
    album_keys = json_idx.get("album1", {})
    assert "metadata.json" not in album_keys


def test_strip_sidecar_suffix():
    assert _strip_sidecar_suffix("photo.jpg.json") == "photo.jpg"
    assert _strip_sidecar_suffix("photo.jpg.supplemental-metadata.json") == "photo.jpg"
    assert _strip_sidecar_suffix("photo.jpg.suppl.json") == "photo.jpg"
    assert _strip_sidecar_suffix("photo.jpg.supp.json") == "photo.jpg"
    assert _strip_sidecar_suffix("photo.jpg.sup.json") == "photo.jpg"
    assert _strip_sidecar_suffix("not_a_sidecar.txt") is None


def test_find_json_for_media_direct_match(fake_takeout):
    dirs = find_takeout_dirs(fake_takeout)
    media, json_idx = build_index(dirs, MEDIA_EXTENSIONS)
    photo = [p for p, _ in media if p.name == "photo.jpg"][0]
    result = find_json_for_media(photo, "Album1", json_idx)
    assert result is not None
    assert result.name == "photo.jpg.json"


def test_find_json_for_media_no_match(fake_takeout):
    dirs = find_takeout_dirs(fake_takeout)
    _, json_idx = build_index(dirs, MEDIA_EXTENSIONS)
    fake_media = fake_takeout / "Takeout1" / "Google Photos" / "Album1" / "nonexistent.jpg"
    result = find_json_for_media(fake_media, "Album1", json_idx)
    assert result is None


def test_find_json_for_media_prefix_match(tmp_path):
    """Test prefix matching for truncated JSON titles."""
    album_dir = tmp_path / "Takeout1" / "Google Photos" / "Album1"
    album_dir.mkdir(parents=True)

    # Long media filename
    long_name = "a" * 20 + "_extra_stuff.jpg"
    (album_dir / long_name).write_bytes(b"\xff\xd8\xff\xd9")

    # JSON with truncated title (only first 20 chars)
    truncated_title = "a" * 20
    sidecar = {"title": truncated_title}
    (album_dir / (truncated_title + ".json")).write_text(
        json.dumps(sidecar), encoding="utf-8"
    )

    dirs = find_takeout_dirs(tmp_path)
    media, json_idx = build_index(dirs, MEDIA_EXTENSIONS)
    media_file = [p for p, _ in media][0]
    result = find_json_for_media(media_file, "Album1", json_idx)
    assert result is not None
