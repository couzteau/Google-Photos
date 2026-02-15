"""Tests for degoogle_photos.copy."""

from datetime import datetime
from pathlib import Path

from degoogle_photos.copy import (
    compute_dest_path,
    resolve_collision,
    is_already_copied,
    copy_with_sidecar,
)


def test_compute_dest_path_with_date(output_dir):
    dt = datetime(2020, 5, 10)
    media = Path("/fake/photo.jpg")
    dest = compute_dest_path(output_dir, media, dt)
    assert dest == output_dir / "2020" / "05" / "photo.jpg"


def test_compute_dest_path_without_date(output_dir):
    media = Path("/fake/photo.jpg")
    dest = compute_dest_path(output_dir, media, None)
    assert dest == output_dir / "needs_review" / "photo.jpg"


def test_resolve_collision_no_conflict(tmp_path):
    dest = tmp_path / "photo.jpg"
    assert resolve_collision(dest) == dest


def test_resolve_collision_appends_counter(tmp_path):
    dest = tmp_path / "photo.jpg"
    dest.write_bytes(b"existing")
    resolved = resolve_collision(dest)
    assert resolved == tmp_path / "photo_2.jpg"


def test_resolve_collision_increments(tmp_path):
    (tmp_path / "photo.jpg").write_bytes(b"x")
    (tmp_path / "photo_2.jpg").write_bytes(b"x")
    resolved = resolve_collision(tmp_path / "photo.jpg")
    assert resolved == tmp_path / "photo_3.jpg"


def test_is_already_copied_same_size(tmp_path):
    src = tmp_path / "source.jpg"
    dst = tmp_path / "dest.jpg"
    content = b"hello world"
    src.write_bytes(content)
    dst.write_bytes(content)
    assert is_already_copied(src, dst) is True


def test_is_already_copied_different_size(tmp_path):
    src = tmp_path / "source.jpg"
    dst = tmp_path / "dest.jpg"
    src.write_bytes(b"hello")
    dst.write_bytes(b"hi")
    assert is_already_copied(src, dst) is False


def test_is_already_copied_no_dest(tmp_path):
    src = tmp_path / "source.jpg"
    src.write_bytes(b"hello")
    assert is_already_copied(src, tmp_path / "nope.jpg") is False


def test_copy_with_sidecar(tmp_path):
    src = tmp_path / "source"
    src.mkdir()
    out = tmp_path / "output" / "2020" / "05"

    media = src / "photo.jpg"
    media.write_bytes(b"jpeg data")
    sidecar = src / "photo.jpg.json"
    sidecar.write_text('{"title":"photo.jpg"}', encoding="utf-8")

    dest = out / "photo.jpg"
    actual = copy_with_sidecar(media, sidecar, dest, dry_run=False)

    assert actual.exists()
    assert actual.read_bytes() == b"jpeg data"
    json_copy = actual.parent / (actual.name + ".json")
    assert json_copy.exists()


def test_copy_with_sidecar_dry_run(tmp_path):
    media = tmp_path / "photo.jpg"
    media.write_bytes(b"data")
    dest = tmp_path / "output" / "photo.jpg"
    actual = copy_with_sidecar(media, None, dest, dry_run=True)
    # Dry run should not create any files
    assert not actual.exists()
