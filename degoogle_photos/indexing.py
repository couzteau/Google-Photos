"""Index Takeout directories — find media files and JSON sidecars."""

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


def find_takeout_dirs(source_root: Path) -> List[Path]:
    """
    Find all Takeout*/Google Photos/ directories.

    Handles several common ways users might point --source:
    1. Parent containing Takeout*/ dirs           (intended usage)
    2. A Takeout dir directly (has Google Photos/)
    3. The Google Photos dir itself inside a Takeout
    4. A grandparent containing subdirs that contain Takeout*/ dirs
    """
    dirs = []

    # Case 1: source_root contains Takeout*/ children (standard case)
    for entry in sorted(source_root.iterdir()):
        if entry.is_dir() and entry.name.startswith("Takeout"):
            gp_dir = entry / "Google Photos"
            if gp_dir.is_dir():
                dirs.append(gp_dir)
    if dirs:
        return dirs

    # Case 2: source_root IS a Takeout dir (has Google Photos/ inside)
    gp_dir = source_root / "Google Photos"
    if gp_dir.is_dir():
        print(f"  (Auto-detected: --source points at a Takeout directory)")
        return [gp_dir]

    # Case 3: source_root IS the Google Photos dir (has album subdirs with media)
    if source_root.name == "Google Photos":
        # Verify it looks like a Google Photos dir (has subdirectories)
        has_subdirs = any(p.is_dir() for p in source_root.iterdir())
        if has_subdirs:
            print(f"  (Auto-detected: --source points at a Google Photos directory)")
            return [source_root]

    # Case 4: source_root is a grandparent (e.g. user pointed at "Pictures/google photos")
    # Look one level deeper for dirs containing Takeout*/Google Photos/
    for child in sorted(source_root.iterdir()):
        if not child.is_dir():
            continue
        for grandchild in child.iterdir():
            if grandchild.is_dir() and grandchild.name.startswith("Takeout"):
                gp_dir = grandchild / "Google Photos"
                if gp_dir.is_dir():
                    dirs.append(gp_dir)
    if dirs:
        print(f"  (Auto-detected: found Takeout directories one level deeper)")

    return dirs


def build_index(
    takeout_dirs: List[Path],
    media_extensions: Set[str],
) -> Tuple[List[Tuple[Path, str]], dict]:
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
                    if ext in media_extensions:
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


# Patterns Google uses for sidecar JSON filenames (most specific -> least)
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


def _strip_sidecar_suffix(json_filename: str) -> Optional[str]:
    """Strip known sidecar suffixes to recover the media filename."""
    lower = json_filename.lower()
    for suffix in SIDECAR_SUFFIXES:
        if lower.endswith(suffix):
            return json_filename[: len(json_filename) - len(suffix)]
    return None


def find_json_for_media(
    media_path: Path,
    album_name: str,
    json_index: dict,
) -> Optional[Path]:
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

    # Prefix matching for heavily truncated JSON filenames
    best_match = None
    best_len = 0
    for key, jpath in album_jsons.items():
        if media_name_lower.startswith(key) and len(key) > best_len:
            best_match = jpath
            best_len = len(key)
        elif key.startswith(media_name_lower) and len(media_name_lower) > best_len:
            best_match = jpath
            best_len = len(media_name_lower)

    # Only accept prefix matches of reasonable length to avoid false positives
    if best_match and best_len >= 10:
        return best_match

    return None
