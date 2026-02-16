"""CLI entry point — orchestrates the full migration pipeline."""

import argparse
from collections import defaultdict
from pathlib import Path

from .indexing import find_takeout_dirs, build_index, find_json_for_media
from .dates import extract_date
from .metadata import extract_metadata
from .dedup import compute_md5, make_dedup_key
from .copy import compute_dest_path, is_already_copied, copy_with_sidecar
from .albums import create_album_symlinks
from .logging_util import MigrationLog

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".heic", ".webp", ".bmp", ".tiff", ".tif",
    ".mp4", ".mov", ".avi", ".mkv", ".m4v", ".3gp", ".wmv", ".mpg", ".mpeg",
}

PROGRESS_INTERVAL = 500


def main():
    parser = argparse.ArgumentParser(description="Migrate Google Takeout photos to YYYY/MM/ structure")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be done without copying")
    parser.add_argument("--source", type=Path, default=Path.cwd(),
                        help="Source root containing Takeout dirs (default: current directory)")
    parser.add_argument("--output", type=Path, default=Path.cwd() / "DeGoogled Photos",
                        help="Output root for organized photos (default: ./DeGoogled Photos)")
    args = parser.parse_args()

    source_root = args.source
    output_root = args.output
    dry_run = args.dry_run

    log = MigrationLog(output_root, dry_run, progress_interval=PROGRESS_INTERVAL)

    # Phase 1: Build global index
    print("Phase 1: Scanning Takeout directories...")
    takeout_dirs = find_takeout_dirs(source_root)
    print(f"  Found {len(takeout_dirs)} Takeout/Google Photos directories")

    media_files, json_index = build_index(takeout_dirs, MEDIA_EXTENSIONS)
    total_jsons = sum(len(v) for v in json_index.values())
    print(f"  Found {len(media_files)} media files")
    print(f"  Indexed {total_jsons} JSON sidecars across {len(json_index)} albums")

    log.total = len(media_files)
    log.html.total = len(media_files)

    # Album tracking: album_name -> [dest_path, ...]
    album_files = defaultdict(list)  # type: dict[str, list[Path]]

    # Phase 2-4: Process each media file
    print(f"\nPhase 2-4: Processing files{' (dry run)' if dry_run else ''}...")
    seen_dedup_keys = set()

    for i, (media_path, album_name) in enumerate(media_files, 1):
        try:
            # Find matching JSON
            json_path = find_json_for_media(media_path, album_name, json_index)

            # Extract date
            dt, date_source = extract_date(media_path, json_path)

            # Extract rich metadata for report tooltips
            metadata = extract_metadata(media_path, json_path)

            # Compute destination
            dest_path = compute_dest_path(output_root, media_path, dt)

            # Check resumability
            if is_already_copied(media_path, dest_path):
                log.skipped_resume += 1
                log.log(f"SKIP_RESUME: {media_path} -> {dest_path}")
                log.html.add_copied(dest_path, media_path, dt, date_source,
                                    album_name, json_path is not None, metadata)
                album_files[album_name].append(dest_path)
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
                                        album_name, json_path is not None, metadata)
                    album_files[album_name].append(actual_dest)
                else:
                    log.log(f"REVIEW: {media_path} -> {dest_path}")
                    log.html.add_copied(dest_path, media_path, dt, date_source,
                                        album_name, json_path is not None, metadata)
                    album_files[album_name].append(dest_path)
            else:
                # Normal copy
                if not dry_run:
                    actual_dest = copy_with_sidecar(media_path, json_path, dest_path, dry_run)
                    log.log(f"COPY: {media_path} -> {actual_dest} (date={dt})")
                    log.html.add_copied(actual_dest, media_path, dt, date_source,
                                        album_name, json_path is not None, metadata)
                    album_files[album_name].append(actual_dest)
                else:
                    log.log(f"COPY: {media_path} -> {dest_path} (date={dt})")
                    log.html.add_copied(dest_path, media_path, dt, date_source,
                                        album_name, json_path is not None, metadata)
                    album_files[album_name].append(dest_path)
                log.copied += 1

        except Exception as e:
            log.errors += 1
            log.log(f"ERROR: {media_path} -- {type(e).__name__}: {e}")
            log.html.add_error(media_path, f"{type(e).__name__}: {e}")

        log.progress(i, log.total)

    # Phase 5: Create album symlinks
    print()  # newline after progress bar
    create_album_symlinks(output_root, album_files, dry_run, log)

    # Phase 6: Write reports
    log.write_logs()


if __name__ == "__main__":
    main()
