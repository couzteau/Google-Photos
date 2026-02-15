# Google Photos Migrate

Organize Google Takeout photo exports into a clean `YYYY/MM/` folder structure with deduplication, album symlinks, and a browsable HTML report.

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
python3 migrate_photos.py --dry-run

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
google_photos_migrate/
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

## License

MIT
