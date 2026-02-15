#!/usr/bin/env python3
"""
Google Takeout Photo Migration Script

Organizes ~20,781 media files from 46+ Takeout chunks into YYYY/MM/ folders
with deduplication, cross-chunk JSON sidecar matching, and date extraction.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCE_ROOT = Path("/Volumes/Seldom Seen Smith/Resterampe/Google Photos")
OUTPUT_ROOT = Path("/Volumes/Seldom Seen Smith/Resterampe/Google Photos Organized")

MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".heic", ".webp", ".bmp", ".tiff", ".tif",
    ".mp4", ".mov", ".avi", ".mkv", ".m4v", ".3gp", ".wmv", ".mpg", ".mpeg",
}

# Patterns Google uses for sidecar JSON filenames (most specific → least)
# e.g. IMG.jpg.supplemental-metadata.json, IMG.jpg.supplemental-metadat.json,
#      IMG.jpg.suppl.json, IMG.jpg.supp.json, IMG.jpg.json
# Also handles heavily truncated names where the JSON filename itself is truncated
SIDECAR_SUFFIXES = [
    ".supplemental-metadata.json",
    ".supplemental-metadat.json",
    ".supplemental-metada.json",
    ".supplemental-metad.json",
    ".supplemental-meta.json",
    ".supplemental-met.json",
    ".supplemental-me.json",
    ".supplemental-.json",
    ".supplemental.json",
    ".suppleme.json",
    ".supplem.json",
    ".supple.json",
    ".suppl.json",
    ".supp.json",
    ".sup.json",
    ".json",
]

# Regex patterns for extracting dates from filenames
FILENAME_DATE_PATTERNS = [
    # YYYYMMDD_HHMMSS (most common: IMG_20200510_204759)
    re.compile(r'(\d{4})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])_((?:[01]\d|2[0-3])([0-5]\d)([0-5]\d))'),
    # YYYY-MM-DD_HH-MM-SS or YYYY-MM-DD HH-MM-SS
    re.compile(r'(\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])[_ -]((?:[01]\d|2[0-3])-([0-5]\d)-([0-5]\d))'),
    # YYYYMMDD alone
    re.compile(r'(\d{4})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])'),
]

# Progress reporting interval
PROGRESS_INTERVAL = 500


# ---------------------------------------------------------------------------
# Phase 1: Build Global Index
# ---------------------------------------------------------------------------

def find_takeout_dirs(source_root: Path) -> List[Path]:
    """Find all Takeout*/Google Photos/ directories."""
    dirs = []
    for entry in sorted(source_root.iterdir()):
        if entry.is_dir() and entry.name.startswith("Takeout"):
            gp_dir = entry / "Google Photos"
            if gp_dir.is_dir():
                dirs.append(gp_dir)
    return dirs


def build_index(takeout_dirs: List[Path]) -> Tuple[List[Tuple[Path, str]], dict]:
    """
    Walk all Takeout dirs. Return:
    - media_files: list of (file_path, album_name) for every media file
    - json_index: dict[album_name_lower][media_title_lower] -> json_path

    The JSON sidecar's "title" field is the authoritative link to the media file.
    We also index by filename-based stripping as a fallback.
    """
    media_files = []
    # json_index[album_lower][title_lower] = json_path
    json_index = defaultdict(dict)
    # Secondary index: json_by_filename_strip[album_lower][stripped_lower] = json_path
    json_by_strip = defaultdict(dict)

    for gp_dir in takeout_dirs:
        for album_dir in sorted(gp_dir.iterdir()):
            if not album_dir.is_dir():
                continue
            album_name = album_dir.name
            album_key = album_name.lower()

            for fpath in album_dir.iterdir():
                if not fpath.is_file():
                    continue

                name = fpath.name
                name_lower = name.lower()

                if name_lower.endswith(".json"):
                    if name_lower == "metadata.json":
                        continue  # album metadata, skip

                    # Try to read the title from the JSON
                    title = _read_json_title(fpath)
                    if title:
                        json_index[album_key][title.lower()] = fpath

                    # Also index by stripping known sidecar suffixes
                    stripped = _strip_sidecar_suffix(name)
                    if stripped:
                        json_by_strip[album_key][stripped.lower()] = fpath
                else:
                    ext = fpath.suffix.lower()
                    if ext in MEDIA_EXTENSIONS:
                        media_files.append((fpath, album_name))

    # Merge json_by_strip into json_index (json_index takes priority since title is authoritative)
    for album_key, entries in json_by_strip.items():
        for media_key, json_path in entries.items():
            if media_key not in json_index[album_key]:
                json_index[album_key][media_key] = json_path

    return media_files, dict(json_index)


def _read_json_title(json_path: Path) -> Optional[str]:
    """Read the 'title' field from a JSON sidecar."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("title")
    except Exception:
        return None


def _strip_sidecar_suffix(json_filename: str) -> Optional[str]:
    """Strip known sidecar suffixes to recover the media filename."""
    lower = json_filename.lower()
    for suffix in SIDECAR_SUFFIXES:
        if lower.endswith(suffix):
            return json_filename[: len(json_filename) - len(suffix)]
    return None


# ---------------------------------------------------------------------------
# Phase 1.5: Match JSON sidecars to media files
# ---------------------------------------------------------------------------

def find_json_for_media(media_path: Path, album_name: str, json_index: dict) -> Optional[Path]:
    """
    Find the JSON sidecar for a media file.
    Strategy:
    1. Look up by exact media filename in the album's index (title-based or strip-based)
    2. For truncated JSON names, check if any indexed title starts with a prefix of the media filename
    """
    album_key = album_name.lower()
    album_jsons = json_index.get(album_key)
    if not album_jsons:
        return None

    media_name_lower = media_path.name.lower()

    # Direct match
    if media_name_lower in album_jsons:
        return album_jsons[media_name_lower]

    # Prefix matching: for heavily truncated JSON filenames where the title inside
    # the JSON is also truncated. Try matching media files whose name starts with
    # a key in the index.
    # This handles cases like JSON title "71782649013__21A33B3D-F3D2-469D-ADED-6DE8363CC6A9.fullsizerender.heic"
    # which might be truncated in the JSON filename itself.
    # We do reverse: check if any key in the album matches our media file.
    # This is O(n) per file but album sizes are small.
    best_match = None
    best_len = 0
    for key, jpath in album_jsons.items():
        # Check if the media filename starts with the key (truncated title)
        if media_name_lower.startswith(key) and len(key) > best_len:
            best_match = jpath
            best_len = len(key)
        # Check if the key starts with the media filename (shouldn't happen often)
        elif key.startswith(media_name_lower) and len(media_name_lower) > best_len:
            best_match = jpath
            best_len = len(media_name_lower)

    # Only accept prefix matches of reasonable length to avoid false positives
    if best_match and best_len >= 10:
        return best_match

    return None


# ---------------------------------------------------------------------------
# Phase 2: Extract Dates
# ---------------------------------------------------------------------------

def extract_date(media_path: Path, json_path: Optional[Path]) -> Tuple[Optional[datetime], str]:
    """
    Extract the best date for a media file using priority cascade.
    Returns (datetime_or_None, source_label).
    """
    # 1. EXIF
    dt = _date_from_exif(media_path)
    if dt:
        return dt, "exif"

    # 2. JSON photoTakenTime
    json_data = _load_json(json_path) if json_path else None
    if json_data:
        dt = _date_from_json_field(json_data, "photoTakenTime")
        if dt:
            return dt, "json_taken"

    # 3. Filename pattern
    dt = _date_from_filename(media_path.name)
    if dt:
        return dt, "filename"

    # 4. JSON creationTime
    if json_data:
        dt = _date_from_json_field(json_data, "creationTime")
        if dt:
            return dt, "json_created"

    # 5. File mtime
    dt = _date_from_mtime(media_path)
    if dt:
        return dt, "mtime"

    return None, "none"


def _date_from_exif(media_path: Path) -> Optional[datetime]:
    """Extract DateTimeOriginal from EXIF data using Pillow."""
    ext = media_path.suffix.lower()
    if ext not in {".jpg", ".jpeg", ".tiff", ".tif", ".png"}:
        return None
    try:
        from PIL import Image
        from PIL.ExifTags import Base as ExifBase
        img = Image.open(media_path)
        exif = img.getexif()
        if not exif:
            return None
        # DateTimeOriginal = 36867, DateTimeDigitized = 36868, DateTime = 306
        for tag_id in (36867, 36868, 306):
            val = exif.get(tag_id)
            if val:
                # Format: "YYYY:MM:DD HH:MM:SS"
                dt = datetime.strptime(val, "%Y:%m:%d %H:%M:%S")
                if dt.year >= 1970:
                    return dt
    except Exception:
        pass
    return None


def _load_json(json_path: Path) -> Optional[dict]:
    """Load a JSON sidecar file."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _date_from_json_field(data: dict, field: str) -> Optional[datetime]:
    """Extract a date from a JSON timestamp field (photoTakenTime or creationTime)."""
    try:
        ts = int(data[field]["timestamp"])
        if ts > 0:
            return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
    except (KeyError, ValueError, TypeError, OSError):
        pass
    return None


def _date_from_filename(filename: str) -> Optional[datetime]:
    """Extract a date from the filename using known patterns."""
    for pattern in FILENAME_DATE_PATTERNS:
        m = pattern.search(filename)
        if m:
            try:
                year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if 1970 <= year <= 2030:
                    return datetime(year, month, day)
            except (ValueError, IndexError):
                continue
    return None


def _date_from_mtime(media_path: Path) -> Optional[datetime]:
    """Get date from file modification time."""
    try:
        mtime = media_path.stat().st_mtime
        dt = datetime.fromtimestamp(mtime)
        if dt.year >= 1970:
            return dt
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Phase 3: Deduplicate
# ---------------------------------------------------------------------------

def compute_md5(file_path: Path) -> str:
    """Compute MD5 hash of a file."""
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)  # 1 MB chunks
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def make_dedup_key(md5: str, dt: Optional[datetime]) -> tuple:
    """Create deduplication key: (md5, date rounded to minute)."""
    if dt:
        rounded = dt.replace(second=0, microsecond=0)
        return (md5, rounded.isoformat())
    return (md5, None)


# ---------------------------------------------------------------------------
# Phase 4: Copy to Output
# ---------------------------------------------------------------------------

def compute_dest_path(output_root: Path, media_path: Path, dt: Optional[datetime]) -> Path:
    """Compute the destination path: output_root/YYYY/MM/filename."""
    if dt:
        folder = output_root / f"{dt.year:04d}" / f"{dt.month:02d}"
    else:
        folder = output_root / "needs_review"
    return folder / media_path.name


def resolve_collision(dest_path: Path) -> Path:
    """If dest_path exists, append _2, _3, etc. before the extension."""
    if not dest_path.exists():
        return dest_path

    stem = dest_path.stem
    ext = dest_path.suffix
    parent = dest_path.parent
    counter = 2
    while True:
        candidate = parent / f"{stem}_{counter}{ext}"
        if not candidate.exists():
            return candidate
        counter += 1


def is_already_copied(source: Path, dest: Path) -> bool:
    """Check if file was already copied (same name + same size = skip for resume)."""
    if not dest.exists():
        return False
    try:
        return source.stat().st_size == dest.stat().st_size
    except OSError:
        return False


def copy_with_sidecar(
    media_path: Path,
    json_path: Optional[Path],
    dest_path: Path,
    dry_run: bool,
) -> Path:
    """Copy media file (and its JSON sidecar) to dest_path. Returns actual dest used."""
    dest_path = resolve_collision(dest_path)

    if not dry_run:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(media_path, dest_path)

        # Copy JSON sidecar alongside, renamed to match the dest filename
        if json_path and json_path.exists():
            json_dest = dest_path.parent / (dest_path.name + ".json")
            shutil.copy2(json_path, json_dest)

    return dest_path


# ---------------------------------------------------------------------------
# Phase 5: Reporting
# ---------------------------------------------------------------------------

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".heic", ".webp", ".bmp", ".tiff", ".tif"}

HTML_UPDATE_INTERVAL = 200  # write HTML every N files


class HtmlReport:
    """Generates a browsable HTML report of the migration, updated incrementally."""

    def __init__(self, output_root: Path, dry_run: bool):
        self.output_root = output_root
        self.dry_run = dry_run
        self.html_path = output_root / "report.html"
        # files_by_folder["2020/03"] = [{"name": ..., "dest": ..., ...}, ...]
        self.files_by_folder = defaultdict(list)  # type: dict[str, list]
        self.duplicates = []   # type: list[dict]
        self.errors = []       # type: list[dict]
        self.date_source_counts = defaultdict(int)  # type: dict[str, int]
        self.total = 0
        self.processed = 0
        self._dirty = False

    def add_copied(self, dest_path: Path, source_path: Path, dt: Optional[datetime],
                   date_source: str, album: str, had_json: bool):
        folder = f"{dt.year:04d}/{dt.month:02d}" if dt else "needs_review"
        self.files_by_folder[folder].append({
            "name": dest_path.name,
            "dest": str(dest_path),
            "source": str(source_path),
            "date": dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "",
            "date_source": date_source,
            "album": album,
            "had_json": had_json,
            "is_image": dest_path.suffix.lower() in IMAGE_EXTENSIONS,
        })
        self.date_source_counts[date_source] += 1
        self._dirty = True

    def add_duplicate(self, source_path: Path, md5: str):
        self.duplicates.append({"source": str(source_path), "md5": md5})
        self._dirty = True

    def add_error(self, source_path: Path, error: str):
        self.errors.append({"source": str(source_path), "error": error})
        self._dirty = True

    def maybe_write(self, current: int):
        """Write HTML if enough files have been processed since last write."""
        if current % HTML_UPDATE_INTERVAL == 0 or current == self.total:
            if self._dirty:
                self._write()
                self._dirty = False

    def _write(self):
        self.output_root.mkdir(parents=True, exist_ok=True)
        total_copied = sum(len(v) for v in self.files_by_folder.values())
        total_dupes = len(self.duplicates)
        total_errors = len(self.errors)

        html = []
        html.append(_HTML_HEAD)

        # Summary
        prefix = "[DRY RUN] " if self.dry_run else ""
        html.append(f'<header><h1>{prefix}Google Photos Migration Report</h1>')
        html.append(f'<p class="updated">Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
                     f' &mdash; {self.processed}/{self.total} files processed</p></header>')

        html.append('<section class="summary"><h2>Summary</h2><div class="stat-grid">')
        html.append(f'<div class="stat"><span class="num">{total_copied}</span><span class="label">Copied</span></div>')
        html.append(f'<div class="stat"><span class="num">{total_dupes}</span><span class="label">Duplicates skipped</span></div>')
        html.append(f'<div class="stat"><span class="num">{total_errors}</span><span class="label">Errors</span></div>')
        nr = len(self.files_by_folder.get("needs_review", []))
        html.append(f'<div class="stat"><span class="num">{nr}</span><span class="label">Needs review</span></div>')
        html.append('</div>')

        # Date source breakdown
        html.append('<h3>Date Sources</h3><table class="date-sources"><tr><th>Source</th><th>Count</th></tr>')
        source_labels = {
            "exif": "EXIF DateTimeOriginal",
            "json_taken": "JSON photoTakenTime",
            "filename": "Filename pattern",
            "json_created": "JSON creationTime",
            "mtime": "File modification time",
            "none": "No date found",
        }
        for key in ["exif", "json_taken", "filename", "json_created", "mtime", "none"]:
            cnt = self.date_source_counts.get(key, 0)
            if cnt > 0:
                html.append(f'<tr><td>{source_labels.get(key, key)}</td><td>{cnt}</td></tr>')
        html.append('</table></section>')

        # Folder browser
        html.append('<section class="browser"><h2>Browse by Folder</h2>')
        html.append('<div class="folder-nav">')
        for folder in sorted(self.files_by_folder.keys()):
            count = len(self.files_by_folder[folder])
            css = ' class="review"' if folder == "needs_review" else ""
            html.append(f'<a href="#folder-{folder.replace("/", "-")}"{css}>{folder} ({count})</a>')
        html.append('</div>')

        for folder in sorted(self.files_by_folder.keys()):
            files = self.files_by_folder[folder]
            anchor = folder.replace("/", "-")
            html.append(f'<div class="folder" id="folder-{anchor}">')
            html.append(f'<h3>{folder} <span class="count">({len(files)} files)</span></h3>')
            html.append('<div class="file-grid">')
            for f in files:
                src_badge = f'<span class="badge badge-{f["date_source"]}">{f["date_source"]}</span>'
                json_badge = '<span class="badge badge-json">JSON</span>' if f["had_json"] else ""
                if f["is_image"]:
                    thumb = f'<div class="thumb"><img loading="lazy" src="file://{_html_escape(f["dest"])}" alt="{_html_escape(f["name"])}"></div>'
                else:
                    ext = Path(f["name"]).suffix.upper()
                    thumb = f'<div class="thumb vid-thumb">{ext}</div>'
                html.append(
                    f'<div class="file-card">'
                    f'{thumb}'
                    f'<div class="file-info">'
                    f'<div class="file-name" title="{_html_escape(f["name"])}">{_html_escape(f["name"])}</div>'
                    f'<div class="file-date">{f["date"]}</div>'
                    f'<div class="file-meta">{src_badge} {json_badge}</div>'
                    f'<div class="file-album" title="{_html_escape(f["album"])}">Album: {_html_escape(f["album"])}</div>'
                    f'</div></div>'
                )
            html.append('</div></div>')

        html.append('</section>')

        # Duplicates
        if self.duplicates:
            html.append('<section class="dupes"><h2>Duplicates Skipped</h2>')
            html.append(f'<p>{len(self.duplicates)} duplicate files were skipped.</p>')
            html.append('<details><summary>Show all duplicates</summary><table><tr><th>Source</th><th>MD5</th></tr>')
            for d in self.duplicates:
                html.append(f'<tr><td>{_html_escape(d["source"])}</td><td><code>{d["md5"]}</code></td></tr>')
            html.append('</table></details></section>')

        # Errors
        if self.errors:
            html.append('<section class="errors"><h2>Errors</h2>')
            html.append('<table><tr><th>Source</th><th>Error</th></tr>')
            for e in self.errors:
                html.append(f'<tr><td>{_html_escape(e["source"])}</td><td>{_html_escape(e["error"])}</td></tr>')
            html.append('</table></section>')

        html.append('</body></html>')
        with open(self.html_path, "w", encoding="utf-8") as f:
            f.write("\n".join(html))


def _html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


_HTML_HEAD = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Google Photos Migration Report</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
       background: #0d1117; color: #c9d1d9; padding: 20px; line-height: 1.5; }
header { margin-bottom: 30px; }
h1 { color: #58a6ff; font-size: 1.6em; }
h2 { color: #58a6ff; margin: 20px 0 12px; font-size: 1.3em; border-bottom: 1px solid #21262d; padding-bottom: 6px; }
h3 { color: #c9d1d9; margin: 14px 0 8px; font-size: 1.1em; }
.updated { color: #8b949e; font-size: 0.9em; margin-top: 4px; }
.stat-grid { display: flex; gap: 16px; flex-wrap: wrap; margin: 10px 0; }
.stat { background: #161b22; border: 1px solid #21262d; border-radius: 8px;
        padding: 16px 24px; text-align: center; min-width: 140px; }
.stat .num { display: block; font-size: 2em; font-weight: 700; color: #58a6ff; }
.stat .label { color: #8b949e; font-size: 0.85em; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; }
th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid #21262d; font-size: 0.85em; }
th { color: #8b949e; }
.date-sources { width: auto; }
.folder-nav { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0 20px; }
.folder-nav a { background: #161b22; border: 1px solid #21262d; border-radius: 6px;
                padding: 4px 10px; color: #58a6ff; text-decoration: none; font-size: 0.85em; }
.folder-nav a:hover { background: #1f2937; }
.folder-nav a.review { color: #f0883e; border-color: #f0883e; }
.folder { margin-bottom: 30px; }
.count { color: #8b949e; font-weight: 400; font-size: 0.9em; }
.file-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
.file-card { background: #161b22; border: 1px solid #21262d; border-radius: 8px; overflow: hidden; }
.thumb { width: 100%; height: 160px; overflow: hidden; display: flex; align-items: center;
         justify-content: center; background: #0d1117; }
.thumb img { width: 100%; height: 100%; object-fit: cover; }
.vid-thumb { color: #8b949e; font-size: 1.4em; font-weight: 700; }
.file-info { padding: 8px 10px; }
.file-name { font-size: 0.8em; font-weight: 600; color: #c9d1d9; white-space: nowrap;
             overflow: hidden; text-overflow: ellipsis; }
.file-date { font-size: 0.75em; color: #8b949e; margin: 2px 0; }
.file-meta { display: flex; gap: 4px; margin: 4px 0; flex-wrap: wrap; }
.file-album { font-size: 0.7em; color: #6e7681; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.badge { font-size: 0.65em; padding: 1px 6px; border-radius: 10px; font-weight: 600; }
.badge-exif { background: #1f6feb33; color: #58a6ff; }
.badge-json_taken { background: #23863633; color: #3fb950; }
.badge-filename { background: #9e6a03aa; color: #e3b341; }
.badge-json_created { background: #23863633; color: #3fb950; }
.badge-mtime { background: #f0883e33; color: #f0883e; }
.badge-none { background: #f8514933; color: #f85149; }
.badge-json { background: #23863633; color: #3fb950; }
details { margin: 8px 0; }
summary { cursor: pointer; color: #58a6ff; font-size: 0.9em; }
.errors table td { color: #f85149; }
code { font-size: 0.8em; color: #8b949e; }
</style></head><body>"""


class MigrationLog:
    """Handles logging to file and console progress."""

    def __init__(self, output_root: Path, dry_run: bool):
        self.output_root = output_root
        self.dry_run = dry_run
        self.copied = 0
        self.skipped_dupes = 0
        self.skipped_resume = 0
        self.needs_review = 0
        self.errors = 0
        self.total = 0
        self._log_lines = []
        self._review_lines = []
        self._start_time = time.time()
        self.html = HtmlReport(output_root, dry_run)

    def log(self, msg: str):
        self._log_lines.append(msg)

    def log_review(self, media_path: Path, reason: str):
        self._review_lines.append(f"{media_path}  -- {reason}")

    def progress(self, current: int, total: int):
        self.html.processed = current
        self.html.maybe_write(current)
        if current % PROGRESS_INTERVAL == 0 or current == total:
            elapsed = time.time() - self._start_time
            rate = current / elapsed if elapsed > 0 else 0
            pct = current / total * 100 if total > 0 else 0
            prefix = "[DRY RUN] " if self.dry_run else ""
            print(
                f"\r{prefix}Progress: {current}/{total} ({pct:.1f}%) "
                f"| {rate:.0f} files/sec "
                f"| copied={self.copied} dupes={self.skipped_dupes} "
                f"review={self.needs_review} errors={self.errors}",
                end="", flush=True,
            )

    def write_logs(self):
        prefix = "[DRY RUN] " if self.dry_run else ""
        elapsed = time.time() - self._start_time

        # Final HTML write
        self.html._write()
        print(f"\nHTML report: {self.html.html_path}")

        summary = (
            f"\n{'='*60}\n"
            f"{prefix}Migration Summary\n"
            f"{'='*60}\n"
            f"Total media files found:  {self.total}\n"
            f"Copied:                   {self.copied}\n"
            f"Skipped (duplicates):     {self.skipped_dupes}\n"
            f"Skipped (already copied): {self.skipped_resume}\n"
            f"Needs review:             {self.needs_review}\n"
            f"Errors:                   {self.errors}\n"
            f"Time elapsed:             {elapsed:.1f}s\n"
            f"{'='*60}\n"
        )
        print(summary)

        if not self.dry_run:
            self.output_root.mkdir(parents=True, exist_ok=True)
            log_path = self.output_root / "migration_log.txt"
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(summary)
                f.write("\nDetailed Log:\n")
                for line in self._log_lines:
                    f.write(line + "\n")
            print(f"Log written to: {log_path}")

            if self._review_lines:
                review_dir = self.output_root / "needs_review"
                review_dir.mkdir(parents=True, exist_ok=True)
                readme = review_dir / "README.txt"
                with open(readme, "w", encoding="utf-8") as f:
                    f.write("Files placed here could not be assigned a date.\n")
                    f.write("Review manually and move to the correct YYYY/MM/ folder.\n\n")
                    for line in self._review_lines:
                        f.write(line + "\n")
                print(f"Review log written to: {readme}")
        else:
            print("(Dry run — no files written)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Migrate Google Takeout photos to YYYY/MM/ structure")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be done without copying")
    parser.add_argument("--source", type=Path, default=SOURCE_ROOT, help="Source root containing Takeout dirs")
    parser.add_argument("--output", type=Path, default=OUTPUT_ROOT, help="Output root for organized photos")
    args = parser.parse_args()

    source_root = args.source
    output_root = args.output
    dry_run = args.dry_run

    log = MigrationLog(output_root, dry_run)

    # Phase 1: Build global index
    print("Phase 1: Scanning Takeout directories...")
    takeout_dirs = find_takeout_dirs(source_root)
    print(f"  Found {len(takeout_dirs)} Takeout/Google Photos directories")

    media_files, json_index = build_index(takeout_dirs)
    total_jsons = sum(len(v) for v in json_index.values())
    print(f"  Found {len(media_files)} media files")
    print(f"  Indexed {total_jsons} JSON sidecars across {len(json_index)} albums")

    log.total = len(media_files)
    log.html.total = len(media_files)

    # Phase 2-4: Process each media file
    print(f"\nPhase 2-4: Processing files{' (dry run)' if dry_run else ''}...")
    seen_dedup_keys = set()

    for i, (media_path, album_name) in enumerate(media_files, 1):
        try:
            # Find matching JSON
            json_path = find_json_for_media(media_path, album_name, json_index)

            # Extract date
            dt, date_source = extract_date(media_path, json_path)

            # Compute destination
            dest_path = compute_dest_path(output_root, media_path, dt)

            # Check resumability
            if is_already_copied(media_path, dest_path):
                log.skipped_resume += 1
                log.log(f"SKIP_RESUME: {media_path} -> {dest_path}")
                log.html.add_copied(dest_path, media_path, dt, date_source,
                                    album_name, json_path is not None)
                log.progress(i, log.total)
                continue

            # Deduplication
            md5 = compute_md5(media_path)
            dedup_key = make_dedup_key(md5, dt)

            if dedup_key in seen_dedup_keys:
                log.skipped_dupes += 1
                log.log(f"SKIP_DUPE: {media_path} (md5={md5})")
                log.html.add_duplicate(media_path, md5)
                log.progress(i, log.total)
                continue
            seen_dedup_keys.add(dedup_key)

            # Handle needs_review
            if dt is None:
                log.needs_review += 1
                log.log_review(media_path, "No date found from any source")
                if not dry_run:
                    actual_dest = copy_with_sidecar(media_path, json_path, dest_path, dry_run)
                    log.log(f"REVIEW: {media_path} -> {actual_dest}")
                    log.html.add_copied(actual_dest, media_path, dt, date_source,
                                        album_name, json_path is not None)
                else:
                    log.log(f"REVIEW: {media_path} -> {dest_path}")
                    log.html.add_copied(dest_path, media_path, dt, date_source,
                                        album_name, json_path is not None)
            else:
                # Normal copy
                if not dry_run:
                    actual_dest = copy_with_sidecar(media_path, json_path, dest_path, dry_run)
                    log.log(f"COPY: {media_path} -> {actual_dest} (date={dt})")
                    log.html.add_copied(actual_dest, media_path, dt, date_source,
                                        album_name, json_path is not None)
                else:
                    log.log(f"COPY: {media_path} -> {dest_path} (date={dt})")
                    log.html.add_copied(dest_path, media_path, dt, date_source,
                                        album_name, json_path is not None)
                log.copied += 1

        except Exception as e:
            log.errors += 1
            log.log(f"ERROR: {media_path} -- {type(e).__name__}: {e}")
            log.html.add_error(media_path, f"{type(e).__name__}: {e}")

        log.progress(i, log.total)

    # Phase 5: Write reports
    print()  # newline after progress bar
    log.write_logs()


if __name__ == "__main__":
    main()
