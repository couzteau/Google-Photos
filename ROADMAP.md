# Roadmap

## Current Version (v0.1.6)

- ✅ Cross-chunk Takeout folder merging
- ✅ Fuzzy JSON metadata matching (handles truncated filenames)
- ✅ Smart date extraction (EXIF > JSON photoTakenTime > filename > creationTime)
- ✅ Content-based deduplication (MD5 + timestamp)
- ✅ Date-based organization (YYYY/MM folders)
- ✅ Album preservation via symlinks
- ✅ Graceful error handling (doesn't crash on missing metadata)
- ✅ Basic HTML report generation with thumbnails and metadata tooltips
- ✅ Dry-run mode
- ✅ Cross-platform support (macOS, Linux, Windows)
- ✅ PyPI package distribution

## v1.0.0

- [ ] **Import non-Takeout photo folders**
  - [ ] Support organizing arbitrary photo directories (not just Google Takeout exports)
  - [ ] `--no-takeout` flag to skip Takeout-specific logic and treat source as a plain photo folder

- [ ] **Bug fixes**
  - [ ] Fix JSON and EXIF badges truncated by card boundary in HTML report

- [ ] **Polish**
  - [ ] Progress indication during migration
  - [ ] Better error messages and recovery
