#!/usr/bin/env python3
"""Analyze Google Takeout photo/video structure without modifying anything."""

import os
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path("/Volumes/Seldom Seen Smith/Resterampe/Google Photos")

# Extensions considered photo/video
PHOTO_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.heic', '.heif', '.raw', '.cr2', '.nef', '.arw', '.dng'}
VIDEO_EXT = {'.mp4', '.mov', '.avi', '.mkv', '.3gp', '.m4v', '.mpg', '.mpeg', '.wmv', '.webm', '.mts'}
MEDIA_EXT = PHOTO_EXT | VIDEO_EXT

# Date patterns in filenames
DATE_PATTERNS = [
    (r'(\d{4})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})', 'YYYYMMDD_HHMMSS'),
    (r'(\d{4})-(\d{2})-(\d{2})', 'YYYY-MM-DD'),
    (r'(\d{4})(\d{2})(\d{2})', 'YYYYMMDD'),
]

def find_matching_json(media_path):
    """Check if a matching .json sidecar exists for a media file."""
    p = Path(media_path)
    # Google Takeout pattern: file.jpg.json or file.jpg(1).json etc.
    candidates = [
        p.parent / (p.name + ".json"),
        # Truncated name pattern (Takeout truncates long filenames)
    ]
    # Also check for edited variants
    for c in candidates:
        if c.exists():
            return c
    # Glob for partial matches (handles truncation and numbering)
    for f in p.parent.glob(p.stem[:40] + "*.json"):
        return f
    return None

def check_filename_date(filename):
    """Check if filename contains a date pattern."""
    for pattern, label in DATE_PATTERNS:
        if re.search(pattern, filename):
            return label
    return None

def sample_exif(media_files, sample_size=50):
    """Sample files and check for EXIF data availability."""
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
        has_pil = True
    except ImportError:
        has_pil = False

    if not has_pil:
        return None, "PIL/Pillow not installed - skipping EXIF check"

    import random
    photo_files = [f for f in media_files if Path(f).suffix.lower() in PHOTO_EXT]
    sample = random.sample(photo_files, min(sample_size, len(photo_files)))

    results = {'has_exif': 0, 'has_date_exif': 0, 'no_exif': 0, 'error': 0}
    date_tags_found = Counter()

    for fpath in sample:
        try:
            img = Image.open(fpath)
            exif = img._getexif()
            if exif:
                results['has_exif'] += 1
                tag_names = {TAGS.get(k, k): v for k, v in exif.items()}
                for dt in ['DateTimeOriginal', 'DateTimeDigitized', 'DateTime']:
                    if dt in tag_names:
                        results['has_date_exif'] += 1
                        date_tags_found[dt] += 1
                        break
            else:
                results['no_exif'] += 1
            img.close()
        except Exception:
            results['error'] += 1

    return results, date_tags_found

def analyze_json_metadata(json_path):
    """Extract date info from a Google Takeout JSON sidecar."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        dates = {}
        if 'photoTakenTime' in data:
            dates['photoTakenTime'] = data['photoTakenTime'].get('timestamp')
        if 'creationTime' in data:
            dates['creationTime'] = data['creationTime'].get('timestamp')
        return dates
    except Exception:
        return None

def main():
    print("=" * 70)
    print("GOOGLE TAKEOUT ANALYSIS")
    print("=" * 70)

    # Find all Takeout folders
    takeout_dirs = sorted([d for d in BASE.iterdir() if d.is_dir() and d.name.startswith("Takeout")])
    print(f"\nTakeout folders found: {len(takeout_dirs)}")
    for td in takeout_dirs:
        print(f"  {td.name}")

    # Walk all Takeout dirs and collect files
    media_files = []
    json_files = []
    other_files = []
    all_extensions = Counter()
    folder_structure = Counter()  # track album/folder names

    print("\nScanning all files...")
    for td in takeout_dirs:
        for root, dirs, files in os.walk(td):
            rel = Path(root).relative_to(td)
            parts = rel.parts
            # Track the Google Photos subfolder structure
            if len(parts) >= 2 and parts[0] == "Google Photos":
                folder_structure[parts[1]] += len(files)

            for fname in files:
                fpath = os.path.join(root, fname)
                ext = Path(fname).suffix.lower()

                if ext == '.json':
                    json_files.append(fpath)
                elif ext in MEDIA_EXT:
                    media_files.append(fpath)
                    all_extensions[ext] += 1
                else:
                    other_files.append(fpath)
                    all_extensions[ext] += 1

    total_media = len(media_files)
    total_json = len(json_files)
    photos = sum(1 for f in media_files if Path(f).suffix.lower() in PHOTO_EXT)
    videos = sum(1 for f in media_files if Path(f).suffix.lower() in VIDEO_EXT)

    print(f"\n{'─' * 50}")
    print("FILE COUNTS")
    print(f"{'─' * 50}")
    print(f"  Total media files:  {total_media:,}")
    print(f"    Photos:           {photos:,}")
    print(f"    Videos:           {videos:,}")
    print(f"  JSON sidecars:      {total_json:,}")
    print(f"  Other files:        {len(other_files):,}")

    # File type breakdown
    print(f"\n{'─' * 50}")
    print("FILE TYPE DISTRIBUTION")
    print(f"{'─' * 50}")
    for ext, count in all_extensions.most_common(20):
        pct = count / max(total_media + len(other_files), 1) * 100
        bar = '█' * int(pct / 2)
        print(f"  {ext:8s}  {count:>7,}  ({pct:5.1f}%)  {bar}")

    # JSON matching
    print(f"\n{'─' * 50}")
    print("JSON METADATA MATCHING")
    print(f"{'─' * 50}")
    matched = 0
    unmatched_samples = []
    for i, mf in enumerate(media_files):
        jf = find_matching_json(mf)
        if jf:
            matched += 1
        elif len(unmatched_samples) < 10:
            unmatched_samples.append(mf)
        if (i + 1) % 5000 == 0:
            print(f"  ... checked {i+1:,}/{total_media:,}")

    print(f"  Media with JSON:    {matched:,} / {total_media:,} ({matched/max(total_media,1)*100:.1f}%)")
    print(f"  Media without JSON: {total_media - matched:,}")
    if unmatched_samples:
        print(f"\n  Sample unmatched files:")
        for s in unmatched_samples[:5]:
            print(f"    {Path(s).name}")

    # Filename date patterns
    print(f"\n{'─' * 50}")
    print("FILENAME DATE PATTERNS")
    print(f"{'─' * 50}")
    date_pattern_counts = Counter()
    no_date_in_name = 0
    for mf in media_files:
        pat = check_filename_date(Path(mf).name)
        if pat:
            date_pattern_counts[pat] += 1
        else:
            no_date_in_name += 1
    for pat, count in date_pattern_counts.most_common():
        print(f"  {pat:25s}  {count:>7,}  ({count/total_media*100:.1f}%)")
    print(f"  {'No date in filename':25s}  {no_date_in_name:>7,}  ({no_date_in_name/total_media*100:.1f}%)")

    # Sample JSON metadata
    print(f"\n{'─' * 50}")
    print("JSON METADATA ANALYSIS (sample)")
    print(f"{'─' * 50}")
    import random
    json_sample = random.sample(json_files, min(100, len(json_files)))
    json_date_fields = Counter()
    json_ok = 0
    for jf in json_sample:
        dates = analyze_json_metadata(jf)
        if dates:
            json_ok += 1
            for k in dates:
                if dates[k]:
                    json_date_fields[k] += 1

    print(f"  Parseable JSONs (of {len(json_sample)} sampled): {json_ok}")
    print(f"  Date fields found:")
    for field, count in json_date_fields.most_common():
        print(f"    {field:25s}  {count:>4} / {len(json_sample)}")

    # EXIF sampling
    print(f"\n{'─' * 50}")
    print("EXIF DATA ANALYSIS (sample of 50 photos)")
    print(f"{'─' * 50}")
    exif_results, exif_dates = sample_exif(media_files, 50)
    if exif_results is None:
        print(f"  {exif_dates}")
    else:
        total_sampled = sum(exif_results.values())
        print(f"  Has EXIF data:      {exif_results['has_exif']:>4} / {total_sampled}")
        print(f"  Has EXIF date:      {exif_results['has_date_exif']:>4} / {total_sampled}")
        print(f"  No EXIF:            {exif_results['no_exif']:>4} / {total_sampled}")
        print(f"  Errors:             {exif_results['error']:>4} / {total_sampled}")
        if exif_dates:
            print(f"  Date tags found:")
            for tag, count in exif_dates.most_common():
                print(f"    {tag:25s}  {count:>4}")

    # Folder/album structure
    print(f"\n{'─' * 50}")
    print("ALBUM/FOLDER STRUCTURE (top 25)")
    print(f"{'─' * 50}")
    for folder, count in folder_structure.most_common(25):
        print(f"  {folder:50s}  {count:>6} files")

    # Summary
    print(f"\n{'=' * 70}")
    print("SUMMARY & DATE SOURCE PRIORITY")
    print(f"{'=' * 70}")
    print(f"  Best date sources (in likely reliability order):")
    print(f"    1. EXIF DateTimeOriginal - embedded in photo at capture time")
    print(f"    2. JSON photoTakenTime   - Google's recorded take time")
    print(f"    3. Filename date pattern  - often matches capture time")
    print(f"    4. JSON creationTime      - upload/creation time (less reliable)")
    print()

if __name__ == "__main__":
    main()
