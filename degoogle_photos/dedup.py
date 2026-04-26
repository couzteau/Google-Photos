"""Deduplication via MD5 hashing and date-rounded keys."""

import hashlib
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple


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


def group_duplicates(
    files: List[Path],
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> List[Tuple[str, List[Path]]]:
    """
    Scan files by MD5 and return duplicate groups.

    Returns a list of (md5, [path, ...]) tuples where each list has 2+ files.
    Within each group the files are sorted shortest-path-first; the first entry
    is the suggested keeper and the rest are the candidates for deletion.

    progress_cb(current, total) is called after each file if provided.
    """
    md5_groups: Dict[str, List[Path]] = defaultdict(list)
    total = len(files)
    for i, fpath in enumerate(files, 1):
        md5 = compute_md5(fpath)
        md5_groups[md5].append(fpath)
        if progress_cb:
            progress_cb(i, total)

    result = []
    for md5, group in md5_groups.items():
        if len(group) > 1:
            group.sort(key=lambda p: (len(str(p)), str(p)))
            result.append((md5, group))

    return result


def make_dedup_key(md5: str, dt: Optional[datetime]) -> tuple:
    """Create deduplication key: (md5, date rounded to minute)."""
    if dt:
        rounded = dt.replace(second=0, microsecond=0)
        return (md5, rounded.isoformat())
    return (md5, None)
