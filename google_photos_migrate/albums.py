"""Album symlink creation."""

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .logging_util import MigrationLog

# Generic album names that Google auto-creates — not real user albums
_GENERIC_ALBUM_RE = re.compile(r'^(Photos from \d{4}|Untitled\(\d+\))$', re.IGNORECASE)


def create_album_symlinks(
    output_root: Path,
    album_files: dict,
    dry_run: bool,
    log: 'MigrationLog',
):
    """Create Albums/<album_name>/ folders with symlinks to the actual files."""
    albums_dir = output_root / "Albums"
    real_albums = {name: paths for name, paths in album_files.items()
                   if not _GENERIC_ALBUM_RE.match(name) and len(paths) > 0}

    if not real_albums:
        print("No named albums to link.")
        return

    print(f"\nPhase 5: Creating album symlinks for {len(real_albums)} albums...")
    link_count = 0
    skip_count = 0

    for album_name, dest_paths in sorted(real_albums.items()):
        # Sanitize album name for filesystem
        safe_name = album_name.replace("/", "-").replace(":", "-").strip()
        if not safe_name:
            continue
        album_dir = albums_dir / safe_name

        if not dry_run:
            album_dir.mkdir(parents=True, exist_ok=True)

        for dest_path in dest_paths:
            link_path = album_dir / dest_path.name
            if link_path.exists() or link_path.is_symlink():
                skip_count += 1
                continue
            if not dry_run:
                try:
                    # Use relative symlink so it works if the root is moved
                    rel_target = os.path.relpath(dest_path, album_dir)
                    link_path.symlink_to(rel_target)
                    link_count += 1
                except Exception as e:
                    log.log(f"SYMLINK_ERROR: {link_path} -> {dest_path} -- {e}")
            else:
                link_count += 1

    print(f"  Created {link_count} symlinks across {len(real_albums)} albums"
          f" ({skip_count} already existed)")
    log.log(f"ALBUMS: {link_count} symlinks in {len(real_albums)} albums")
