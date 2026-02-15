"""Date extraction from EXIF, JSON sidecars, filenames, and file mtimes."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

# Regex patterns for extracting dates from filenames
FILENAME_DATE_PATTERNS = [
    # YYYYMMDD_HHMMSS (most common: IMG_20200510_204759)
    re.compile(r'(\d{4})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])_((?:[01]\d|2[0-3])([0-5]\d)([0-5]\d))'),
    # YYYY-MM-DD_HH-MM-SS or YYYY-MM-DD HH-MM-SS
    re.compile(r'(\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])[_ -]((?:[01]\d|2[0-3])-([0-5]\d)-([0-5]\d))'),
    # YYYYMMDD alone
    re.compile(r'(\d{4})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])'),
]


def extract_date(
    media_path: Path,
    json_path: Optional[Path],
    filename_date_patterns: Optional[List[re.Pattern]] = None,
) -> Tuple[Optional[datetime], str]:
    """
    Extract the best date for a media file using priority cascade.
    Returns (datetime_or_None, source_label).
    """
    patterns = filename_date_patterns if filename_date_patterns is not None else FILENAME_DATE_PATTERNS

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
    dt = _date_from_filename(media_path.name, patterns)
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


def _date_from_filename(
    filename: str,
    patterns: Optional[List[re.Pattern]] = None,
) -> Optional[datetime]:
    """Extract a date from the filename using known patterns."""
    if patterns is None:
        patterns = FILENAME_DATE_PATTERNS
    for pattern in patterns:
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
