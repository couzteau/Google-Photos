# Contributing to Degoogle-Photos

Thanks for your interest in making this tool better. Whether you're fixing a bug, adding a feature, or improving documentation, contributions are welcome.

## Quick Start

1. **Fork and clone**
```bash
   git clone https://github.com/YOUR_USERNAME/Degoogle-Photos.git
   cd Degoogle-Photos
```

2. **Set up development environment**
```bash
   pip3 install -e ".[dev]"
```

3. **Run tests**
```bash
   pytest -v
```

4. **Make your changes**

5. **Submit a pull request**

## What to Contribute

### High-priority areas
- **Web UI development** (see ROADMAP.md v1.0.0) - React, Vue, or vanilla JS welcome
- **Windows compatibility fixes** - Path handling, symlink alternatives
- **Performance improvements** - Multi-threading, thumbnail caching
- **Test coverage** - Edge cases, real-world Takeout variations
- **Documentation** - Tutorials, troubleshooting guides, architecture docs

### Feature requests
Check the [ROADMAP.md](ROADMAP.md) first. If your idea isn't there, open an issue to discuss before implementing. Big features benefit from design discussion upfront.

### Bug reports
Include:
- Your OS and Python version
- Full error message and stack trace
- Sample data structure (anonymized) if possible
- What you expected vs. what happened

## Code Guidelines

### Style
- Follow PEP 8 (run `black` for auto-formatting if you want)
- Write docstrings for public functions
- Keep functions focused and testable
- Prefer explicit over clever

### Testing
- Add tests for new features
- Don't break existing tests
- Test edge cases (missing metadata, malformed JSON, unicode filenames)
- Use the fixtures in `tests/conftest.py` for consistency

### Commits
- Use clear, descriptive commit messages
- Reference issue numbers when relevant (`Fix #42: Handle missing geoDataExif field`)
- Keep commits focused - one logical change per commit

## Project Structure
```
degoogle_photos/
  indexing.py      # Scan Takeout dirs, build file index
  dates.py         # Extract best date from EXIF/JSON/filename
  metadata.py      # Rich metadata for tooltips/display
  dedup.py         # MD5 hashing and duplicate detection
  copy.py          # File operations with collision handling
  albums.py        # Symlink creation for albums
  report.py        # HTML report generation
  cli.py           # Command-line interface
tests/
  test_*.py        # Test modules mirror src structure
```

## Privacy & Philosophy

This tool exists because **privacy matters**. When contributing:

- **No telemetry, analytics, or phone-home features** - Users trust us with personal photos
- **Local processing only** - Face recognition and other AI features must run on-device
- **No proprietary lock-in** - Output should be standard files anyone can use
- **Graceful degradation** - Handle missing/malformed data without crashing

If a feature requires cloud APIs or data upload, it doesn't belong in this project.

## Getting Help

- **Questions?** Open a GitHub issue or discussion
- **Stuck on something?** Tag `@couzteau` in an issue
- **Just exploring?** Browse the code, run the tests, see how it works

## Recognition

Contributors will be listed in the README. Significant contributions may warrant co-authorship credit.

## License

By contributing, you agree your code will be released under the MIT License (same as the project).

---

**Most important:** Don't overthink it. If you see something that could be better, try to make it better. We'll figure out the details together.