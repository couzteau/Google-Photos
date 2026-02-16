# Degoogle-Photos

Unfuck the mess that Google Takeout makes of your photo library. Takes the dozens of chaotic zip archives, deduplicates, extracts dates, and organizes everything into clean `YYYY/MM/` folders with album symlinks and a browsable HTML report.

## Why this exists

**If you're not paying for the product, you are the product.**

Google Photos is free because their business model is advertising and data. Their terms grant them a worldwide, royalty-free license to use, reproduce, modify, and distribute your uploads -- including AI training. Your "private" album is private from other users, not from Google.

I decided to leave. Google Takeout -- the only official export -- dumps your library into dozens of numbered zips: albums split across chunks, JSON metadata with truncated filenames, duplicates everywhere, no usable organization. For my ~20,000 photos across 46 archives, it was unusable.

The popular [Google Photos Takeout Helper](https://github.com/TheLastGimbus/GooglePhotosTakeoutHelper) crashed repeatedly on missing metadata fields with no resume support. After several rounds of whack-a-mole I gave up.

So I built this with Claude. Sharing it because leaving Google shouldn't require a computer science degree.

## Getting your photos out of Google

1. Go to [takeout.google.com](https://takeout.google.com)
2. Click **Deselect all**, then scroll down and select only **Google Photos**
3. Click **Next step**
4. Choose **Export once**, file type **.zip**, and size **2 GB** (or 50 GB if you have fast internet and lots of storage)
5. Click **Create export**
6. Wait -- Google prepares the archive in the background and emails you when it's ready (can take hours or even days for large collections)
7. Download all the zip files and extract them into a single folder

You'll end up with something like `Takeout/`, `Takeout-2/`, `Takeout-3/`, ... each containing a `Google Photos/` subfolder. That's your `--source` directory.

## What it does

- Scans multiple `Takeout*/Google Photos/` directories and builds a global index
- Extracts the best date for each file (EXIF > JSON photoTakenTime > filename > JSON creationTime > file mtime)
- Deduplicates by MD5 hash + date (rounded to the minute)
- Copies media files into `YYYY/MM/` folders, preserving JSON sidecars alongside
- Creates `Albums/` folder with relative symlinks for named albums
- Generates a multi-page HTML report with thumbnails, metadata tooltips, and Finder links

## Prerequisites

- Python 3.9+
- A Google Takeout export (see above)

## Installation

[![PyPI](https://img.shields.io/pypi/v/degoogle-photos)](https://pypi.org/project/degoogle-photos/)

**Windows:**
```bash
pip install degoogle-photos
```

**macOS / Linux:**
```bash
pip3 install degoogle-photos
```

That's it. Pillow (for EXIF extraction) is installed automatically.

> **Why `pip3`?** Many macOS and Linux systems still have Python 2.7 as the default `pip`. If you see "No matching distribution found" or warnings about Python 2.7, that's why. `pip3` ensures you're using Python 3.

### Alternative: run from source

```bash
git clone https://github.com/couzteau/Degoogle-Photos.git
cd Degoogle-Photos
pip3 install -e .
```

## Usage

```bash
# Simplest: cd into the folder with your extrackted Takeout dirs and run
cd /path/to/takeouts
degoogle-photos

# Or specify paths explicitly
degoogle-photos --source /path/to/takeouts --output /path/to/organized

# Preview what would happen (no files copied)
degoogle-photos --dry-run
```

### Options

| Flag | Description |
|------|-------------|
| `--source PATH` | Root directory containing `Takeout*/` folders (default: current directory) |
| `--output PATH` | Destination for organized photos (default: `./DeGoogled Photos`) |
| `--dry-run` | Report what would be done without copying any files |

The script is **safe to stop and restart** at any time. It detects files that have already been copied and skips them, so you'll never end up with duplicates -- even if you run it multiple times or interrupt it halfway through.

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

### Recommended: Immich (self-hosted Google Photos replacement)

[Immich](https://immich.app/) is a free, open-source, self-hosted photo platform with face recognition, map view, timeline browsing, mobile apps, and AI-powered search -- all running on your own hardware. Your photos never leave your network. It's the closest thing to Google Photos without giving up your privacy.

Setup is quick -- it runs locally via [Docker](https://docs.docker.com/get-docker/) and the [install guide](https://immich.app/docs/install/docker-compose) is straightforward. If you get stuck, any AI assistant can walk you through it in minutes. Once running, Immich's smart search (by face, location, object, or scene) fully replaces what you'd need Google Photos for when it comes to finding and sorting your photos.

After running degoogle-photos, create an API key in the Immich web UI (Account Settings > API Keys), then authenticate and upload:

```bash
immich login http://localhost:2283 YOUR-API-KEY
immich upload --recursive /path/to/DeGoogled\ Photos
```

Immich will pick up the dates and folder structure automatically.

### Other options

| Service | Terms summary | Cross-platform | License | Storage |
|---------|--------------|----------------|---------|---------|
| **Apple iCloud** | Minimal rights -- just enough to sync and store. No ad business model. | Apple devices + web (non-Apple users can upload via browser) | Free | Paid |
| **Adobe Lightroom** | Rights limited to operating services. No generative AI training on customer content. | Full cross-platform | Paid | Included |
| **Dropbox / OneDrive** | Rights limited to providing the service. No promotional or AI training use. | Full cross-platform | Free tier available | Paid |
| **Local storage + backup** | Your files, your rights. Use the generated `report/index.html` to browse and review. | Any device with file access | Free | Free |

## Roadmap

See [ROADMAP.md](ROADMAP.md) for planned features.

## License

MIT
