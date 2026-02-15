"""Tests for degoogle_photos.report."""

from datetime import datetime
from pathlib import Path

from degoogle_photos.report import (
    HtmlReport,
    _html_escape,
    _slugify,
    _GENERIC_ALBUM_RE,
)


def test_html_escape():
    assert _html_escape('<script>"alert&') == '&lt;script&gt;&quot;alert&amp;'


def test_slugify_basic():
    assert _slugify("My Vacation 2020") == "my_vacation_2020"


def test_slugify_special_chars():
    assert _slugify("Trip: Paris/London!") == "trip_paris_london"


def test_slugify_empty():
    assert _slugify("") == "unnamed"


def test_slugify_truncates():
    long_name = "a" * 100
    assert len(_slugify(long_name)) <= 80


def test_generic_album_re():
    assert _GENERIC_ALBUM_RE.match("Photos from 2020")
    assert _GENERIC_ALBUM_RE.match("Untitled(1)")
    assert not _GENERIC_ALBUM_RE.match("My Vacation")
    assert not _GENERIC_ALBUM_RE.match("Summer 2020")


def test_add_copied_populates_folder(output_dir):
    report = HtmlReport(output_dir, dry_run=True)
    dest = Path("/out/2020/05/photo.jpg")
    src = Path("/src/photo.jpg")
    dt = datetime(2020, 5, 10, 14, 30)

    report.add_copied(dest, src, dt, "exif", "My Vacation", True, {"camera": "Nikon"})

    assert "2020/05" in report.files_by_folder
    assert len(report.files_by_folder["2020/05"]) == 1
    entry = report.files_by_folder["2020/05"][0]
    assert entry["name"] == "photo.jpg"
    assert entry["date_source"] == "exif"


def test_add_copied_populates_album(output_dir):
    report = HtmlReport(output_dir, dry_run=True)
    dest = Path("/out/2020/05/photo.jpg")
    src = Path("/src/photo.jpg")
    dt = datetime(2020, 5, 10)

    report.add_copied(dest, src, dt, "exif", "My Vacation", True)
    assert "My Vacation" in report.files_by_album
    assert len(report.files_by_album["My Vacation"]) == 1


def test_add_copied_skips_generic_album(output_dir):
    report = HtmlReport(output_dir, dry_run=True)
    dest = Path("/out/2020/05/photo.jpg")
    src = Path("/src/photo.jpg")
    dt = datetime(2020, 5, 10)

    report.add_copied(dest, src, dt, "exif", "Photos from 2020", True)
    assert len(report.files_by_album) == 0


def test_write_creates_files(output_dir):
    report = HtmlReport(output_dir, dry_run=False)
    report.total = 1
    dest = Path("/out/2020/05/photo.jpg")
    report.add_copied(dest, Path("/src/photo.jpg"), datetime(2020, 5, 10), "exif", "Album1", True)
    report._write()

    assert (output_dir / "report" / "index.html").exists()
    assert (output_dir / "report" / "style.css").exists()
    assert (output_dir / "report" / "folder_2020_05.html").exists()


def test_render_card_has_tooltip(output_dir):
    report = HtmlReport(output_dir, dry_run=True)
    entry = {
        "name": "photo.jpg",
        "dest": "/out/photo.jpg",
        "source": "/src/photo.jpg",
        "date": "2020-05-10 14:30:00",
        "date_source": "exif",
        "album": "Vacation",
        "had_json": True,
        "is_image": True,
        "metadata": {"camera": "Nikon D850", "photoTakenTime": "2020-05-10 14:30:00 UTC"},
    }
    html = report._render_card(entry)
    assert "data-tooltip" in html
    assert "Nikon D850" in html
    assert "Finder" in html


def test_render_card_video(output_dir):
    report = HtmlReport(output_dir, dry_run=True)
    entry = {
        "name": "clip.mp4",
        "dest": "/out/clip.mp4",
        "source": "/src/clip.mp4",
        "date": "",
        "date_source": "none",
        "album": "",
        "had_json": False,
        "is_image": False,
        "metadata": {},
    }
    html = report._render_card(entry)
    assert ".MP4" in html
    assert "vid-thumb" in html
