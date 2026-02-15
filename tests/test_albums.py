"""Tests for google_photos_migrate.albums."""

import os
from pathlib import Path
from unittest.mock import MagicMock

from google_photos_migrate.albums import create_album_symlinks, _GENERIC_ALBUM_RE


def _make_mock_log():
    log = MagicMock()
    log.log = MagicMock()
    return log


def test_create_symlinks(tmp_path):
    output_root = tmp_path / "output"
    output_root.mkdir()

    # Create a real dest file to symlink to
    dest_dir = output_root / "2020" / "05"
    dest_dir.mkdir(parents=True)
    dest_file = dest_dir / "photo.jpg"
    dest_file.write_bytes(b"jpeg")

    album_files = {"My Vacation": [dest_file]}
    log = _make_mock_log()

    create_album_symlinks(output_root, album_files, dry_run=False, log=log)

    link = output_root / "Albums" / "My Vacation" / "photo.jpg"
    assert link.is_symlink()
    assert link.resolve() == dest_file.resolve()


def test_skips_generic_albums(tmp_path):
    output_root = tmp_path / "output"
    output_root.mkdir()

    dest_dir = output_root / "2020" / "05"
    dest_dir.mkdir(parents=True)
    dest_file = dest_dir / "photo.jpg"
    dest_file.write_bytes(b"jpeg")

    album_files = {"Photos from 2020": [dest_file]}
    log = _make_mock_log()

    create_album_symlinks(output_root, album_files, dry_run=False, log=log)
    assert not (output_root / "Albums").exists()


def test_handles_existing_symlinks(tmp_path):
    output_root = tmp_path / "output"
    output_root.mkdir()

    dest_dir = output_root / "2020" / "05"
    dest_dir.mkdir(parents=True)
    dest_file = dest_dir / "photo.jpg"
    dest_file.write_bytes(b"jpeg")

    # Pre-create the symlink
    album_dir = output_root / "Albums" / "Trip"
    album_dir.mkdir(parents=True)
    link = album_dir / "photo.jpg"
    link.symlink_to(os.path.relpath(dest_file, album_dir))

    album_files = {"Trip": [dest_file]}
    log = _make_mock_log()

    # Should not crash — existing symlink is skipped
    create_album_symlinks(output_root, album_files, dry_run=False, log=log)
    assert link.is_symlink()


def test_generic_album_re():
    assert _GENERIC_ALBUM_RE.match("Photos from 2020")
    assert _GENERIC_ALBUM_RE.match("Photos from 2023")
    assert _GENERIC_ALBUM_RE.match("Untitled(1)")
    assert _GENERIC_ALBUM_RE.match("Untitled(42)")
    assert not _GENERIC_ALBUM_RE.match("Summer Vacation")
    assert not _GENERIC_ALBUM_RE.match("Photos from the trip")
