"""File copying with collision resolution and sidecar handling."""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional


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
