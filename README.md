# degoogle-photos

Organize Google Takeout photo exports into a clean `YYYY/MM/` folder structure with deduplication, album symlinks, and a browsable HTML report.

## Why this exists

**If you're not paying for the product, you are the product.**

Google Photos is free because Google's business model is advertising and data. Their terms of service grant them a worldwide, royalty-free license to use, reproduce, modify, and distribute anything you upload -- including training AI models and creating derivative works. Your "private" album is private from other users, not from Google.

I decided to leave Google Photos for good, but getting out is harder than getting in. Google Takeout -- the only official export tool -- dumps your collection into dozens of numbered zip files with a chaotic structure: albums split across chunks, JSON metadata sidecars with truncated filenames, duplicates scattered everywhere, and no usable date-based organization. For my ~20,000 photos across 46 archives, it was a mess.

The go-to recommendation is the [Google Photos Takeout Helper](https://github.com/TheLastGimbus/GooglePhotosTakeoutHelper). I tried it. It crashed on a missing `geoDataExif` field in a JSON sidecar. Moved the problem file out, restarted. Crashed again on the next file. Moved the whole album folder. Crashed on a different folder with the same error. Each crash meant starting from scratch -- no resume support. After several rounds of this whack-a-mole I gave up. With 20,000 files and wildly inconsistent metadata across 46 archives, a tool that dies on the first unexpected field is effectively unusable.

So I built this from scratch with [Claude](https://claude.ai)

Sharing it because leaving Google shouldn't require a computer science degree. If the only thing keeping you on Google Photos is "I don't know how to get my photos out," this is how.

## What it does

- Scans multiple `Takeout*/Google Photos/` directories and builds a global index
- Extracts the best date for each file (EXIF > JSON photoTakenTime > filename > JSON creationTime > file mtime)
- Deduplicates by MD5 hash + date (rounded to the minute)
- Copies media files into `YYYY/MM/` folders, preserving JSON sidecars alongside
- Creates `Albums/` folder with relative symlinks for named albums
- Generates a multi-page HTML report with thumbnails, metadata tooltips, and Finder links

## Prerequisites

- Python 3.9+
- [Pillow](https://pypi.org/project/Pillow/) (for EXIF extraction)
- A Google Takeout export with one or more `Takeout*/Google Photos/` directories

## Installation

```bash
pip install -e .
```

Or just run directly without installing:

```bash
python3 migrate_photos.py --source /path/to/takeouts --output /path/to/organized
```

## Usage

```bash
# Preview what would happen (no files copied)
python3 migrate_photos.py --source /path/to/takeouts --output /path/to/organized --dry-run

# Run the migration
python3 migrate_photos.py --source /path/to/takeouts --output /path/to/organized
```

### Options

| Flag | Description |
|------|-------------|
| `--source PATH` | Root directory containing `Takeout*/` folders |
| `--output PATH` | Destination for organized photos |
| `--dry-run` | Report what would be done without copying any files |

## How it works

1. **Index** -- Scan all Takeout directories, index media files and JSON sidecars by album
2. **Match** -- Link each media file to its JSON sidecar via title field or filename stripping
3. **Date extraction** -- Extract the best date using a priority cascade (EXIF > JSON > filename > mtime)
4. **Deduplication** -- Skip files with identical MD5 + date (within the same minute)
5. **Copy** -- Copy to `YYYY/MM/filename` with collision resolution (`_2`, `_3`, etc.)
6. **Albums** -- Create `Albums/<name>/` with relative symlinks to the copied files
7. **Report** -- Generate a browsable HTML report with per-folder and per-album pages

## HTML Report

The report is written to `<output>/report/index.html` and includes:

- Dashboard with copy/duplicate/error counts and date-source breakdown
- Per-folder pages with image thumbnails in a responsive grid
- Per-album pages for named albums (generic "Photos from YYYY" albums are excluded)
- Hover tooltips showing EXIF data (camera, ISO, focal length, GPS) and JSON metadata (people, geo, description)
- "Finder" buttons to open the containing folder in macOS Finder

## Project structure

```
degoogle_photos/
  __init__.py          # Package version
  indexing.py          # Takeout directory scanning and JSON sidecar indexing
  dates.py             # Date extraction (EXIF, JSON, filename, mtime)
  metadata.py          # Rich metadata extraction for report tooltips
  dedup.py             # MD5 hashing and deduplication keys
  copy.py              # File copying with collision resolution
  report.py            # Multi-page HTML report generation
  logging_util.py      # Migration logging and progress reporting
  albums.py            # Album symlink creation
  cli.py               # CLI entry point and orchestration
tests/
  conftest.py          # Shared test fixtures
  test_indexing.py
  test_dates.py
  test_metadata.py
  test_dedup.py
  test_copy.py
  test_report.py
  test_albums.py
migrate_photos.py      # Thin wrapper for backward compatibility
pyproject.toml         # Project metadata and dependencies
```

## Running tests

```bash
pip install -e ".[dev]"
pytest -v
```

## Where to put your photos after

Once your photos are organized, you have options with better privacy terms:

| Service | Terms summary | Cross-platform |
|---------|--------------|----------------|
| **Apple iCloud** | Minimal rights -- just enough to sync and store. No ad business model. | Apple devices + web (non-Apple users can upload via browser to shared albums) |
| **Adobe Lightroom** | Rights limited to operating services. No generative AI training on customer content. | Full cross-platform |
| **Dropbox / OneDrive** | Rights limited to providing the service. No promotional or AI training use. | Full cross-platform |
| **Self-hosted (Immich, PhotoPrism)** | You retain all rights. Requires technical setup. | Web-based, any device |
| **Google Photos** | Worldwide, royalty-free license to use, reproduce, modify, distribute. Can use for AI training, advertising, and derivative works. | Full cross-platform |

## License

MIT
