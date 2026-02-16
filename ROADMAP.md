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

## v1.0.0 - Modern Photo App Experience (In Progress)

The foundation works. Time to make it beautiful.

- [ ] **Modern web-based photo browser**
  - [ ] Clean, responsive grid layout
  - [ ] Lightbox for full-size viewing with keyboard navigation
  - [ ] Timeline view (scroll through years/months)
  - [ ] Map view for geotagged photos
  - [ ] Album browser with cover images
  - [ ] Search and filtering (date ranges, albums, file types)
  - [ ] Light mode support
  - [ ] Mobile/tablet optimized

- [ ] **Enhanced metadata display**
  - [ ] EXIF sidebar (camera, settings, location)
  - [ ] Edit dates/locations/captions
  - [ ] Star/favorite photos
  - [ ] Quick sharing (export selections)

- [ ] **Performance & polish**
  - [ ] Lazy loading for large collections
  - [ ] Thumbnail caching
  - [ ] Progress indication during migration
  - [ ] Better error messages and recovery

**Goal:** Make the post-migration experience feel like a real photo app, not just organized folders. When you browse your degoogled photos, it should feel *better*