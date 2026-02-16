"""HTML report generation for migration results."""

import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".heic", ".webp", ".bmp", ".tiff", ".tif"}

HTML_UPDATE_INTERVAL = 200  # write HTML every N files

# Generic album names that Google auto-creates — not real user albums
_GENERIC_ALBUM_RE = re.compile(r'^(Photos from \d{4}|Untitled\(\d+\))$', re.IGNORECASE)


def _html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _slugify(name: str) -> str:
    """Convert an album name to a filesystem/URL-safe slug."""
    s = name.lower().strip()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    return s.strip('_')[:80] or 'unnamed'


class HtmlReport:
    """Generates a multi-page browsable HTML report of the migration."""

    def __init__(self, output_root: Path, dry_run: bool):
        self.output_root = output_root
        self.dry_run = dry_run
        self.report_dir = output_root / "report"
        # files_by_folder["2020/03"] = [{"name": ..., "dest": ..., ...}, ...]
        self.files_by_folder = defaultdict(list)  # type: dict[str, list]
        # files_by_album["My Vacation"] = [{"name": ..., ...}, ...]
        self.files_by_album = defaultdict(list)   # type: dict[str, list]
        self.duplicates = []   # type: list[dict]
        self.errors = []       # type: list[dict]
        self.date_source_counts = defaultdict(int)  # type: dict[str, int]
        self.total = 0
        self.processed = 0
        self._dirty = False
        # Track which folders/albums changed since last write
        self._dirty_folders = set()
        self._dirty_albums = set()

    def add_copied(self, dest_path: Path, source_path: Path, dt: Optional[datetime],
                   date_source: str, album: str, had_json: bool,
                   metadata: Optional[dict] = None):
        folder = f"{dt.year:04d}/{dt.month:02d}" if dt else "needs_review"
        entry = {
            "name": dest_path.name,
            "dest": str(dest_path),
            "source": str(source_path),
            "date": dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "",
            "date_source": date_source,
            "album": album,
            "had_json": had_json,
            "is_image": dest_path.suffix.lower() in IMAGE_EXTENSIONS,
            "metadata": metadata or {},
        }
        self.files_by_folder[folder].append(entry)
        self.date_source_counts[date_source] += 1
        self._dirty = True
        self._dirty_folders.add(folder)
        # Track album membership (skip generic "Photos from YYYY" albums)
        if album and not _GENERIC_ALBUM_RE.match(album):
            self.files_by_album[album].append(entry)
            self._dirty_albums.add(album)

    def add_duplicate(self, source_path: Path, md5: str):
        self.duplicates.append({"source": str(source_path), "md5": md5})
        self._dirty = True

    def add_error(self, source_path: Path, error: str):
        self.errors.append({"source": str(source_path), "error": error})
        self._dirty = True

    def maybe_write(self, current: int):
        """Write HTML if enough files have been processed since last write."""
        if current % HTML_UPDATE_INTERVAL == 0 or current == self.total:
            if self._dirty:
                self._write()
                self._dirty = False

    # ------------------------------------------------------------------
    # Multi-page write
    # ------------------------------------------------------------------

    def _write(self):
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self._write_css()
        self._write_index()
        # Only rewrite pages whose content changed
        for folder in self._dirty_folders:
            self._write_folder_page(folder, self.files_by_folder[folder])
        for album in self._dirty_albums:
            self._write_album_page(album, self.files_by_album[album])
        self._dirty_folders.clear()
        self._dirty_albums.clear()

    def _write_css(self):
        css_path = self.report_dir / "style.css"
        css_path.write_text(_CSS, encoding="utf-8")

    def _page_head(self, title: str, back_link: bool = False) -> str:
        parts = [
            '<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f'<title>{_html_escape(title)}</title>',
            '<link rel="stylesheet" href="style.css">',
            '<script>function copyText(btn,t){navigator.clipboard.writeText(t).then(function(){'
            'var o=btn.textContent;btn.textContent="Copied!";setTimeout(function(){btn.textContent=o},1000)})}</script>',
            '</head><body>',
        ]
        if back_link:
            parts.append('<nav class="back"><a href="index.html">&larr; Back to Dashboard</a></nav>')
        return '\n'.join(parts)

    def _write_index(self):
        total_copied = sum(len(v) for v in self.files_by_folder.values())
        total_dupes = len(self.duplicates)
        total_errors = len(self.errors)

        html = []
        prefix = "[DRY RUN] " if self.dry_run else ""
        html.append(self._page_head(f"{prefix}Degoogle-Photos Report"))

        html.append(f'<header><h1>{prefix}Degoogle-Photos Report</h1>')
        html.append(f'<p class="updated">Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
                     f' &mdash; {self.processed}/{self.total} files processed</p></header>')

        # Stats
        html.append('<section class="summary"><h2>Summary</h2><div class="stat-grid">')
        html.append(f'<div class="stat"><span class="num">{total_copied}</span><span class="label">Copied</span></div>')
        html.append(f'<div class="stat"><span class="num">{total_dupes}</span><span class="label">Duplicates skipped</span></div>')
        html.append(f'<div class="stat"><span class="num">{total_errors}</span><span class="label">Errors</span></div>')
        nr = len(self.files_by_folder.get("needs_review", []))
        html.append(f'<div class="stat"><span class="num">{nr}</span><span class="label">Needs review</span></div>')
        html.append('</div>')

        # Date source breakdown
        html.append('<h3>Date Sources</h3><table class="date-sources"><tr><th>Source</th><th>Count</th></tr>')
        source_labels = {
            "exif": "EXIF DateTimeOriginal",
            "json_taken": "JSON photoTakenTime",
            "filename": "Filename pattern",
            "json_created": "JSON creationTime",
            "mtime": "File modification time",
            "none": "No date found",
        }
        for key in ["exif", "json_taken", "filename", "json_created", "mtime", "none"]:
            cnt = self.date_source_counts.get(key, 0)
            if cnt > 0:
                html.append(f'<tr><td>{source_labels.get(key, key)}</td><td>{cnt}</td></tr>')
        html.append('</table></section>')

        # Album navigation
        if self.files_by_album:
            html.append('<section class="nav-section"><h2>Albums</h2><div class="folder-nav">')
            for album in sorted(self.files_by_album.keys()):
                count = len(self.files_by_album[album])
                slug = _slugify(album)
                html.append(f'<a href="album_{slug}.html">{_html_escape(album)} ({count})</a>')
            html.append('</div></section>')

        # Folder navigation
        html.append('<section class="nav-section"><h2>Browse by Date Folder</h2><div class="folder-nav">')
        for folder in sorted(self.files_by_folder.keys()):
            count = len(self.files_by_folder[folder])
            slug = folder.replace("/", "_")
            css = ' class="review"' if folder == "needs_review" else ""
            html.append(f'<a href="folder_{slug}.html"{css}>{folder} ({count})</a>')
        html.append('</div></section>')

        # Duplicates
        if self.duplicates:
            html.append('<section class="dupes"><h2>Duplicates Skipped</h2>')
            html.append(f'<p>{len(self.duplicates)} duplicate files were skipped.</p>')
            html.append('<details><summary>Show all duplicates</summary><table><tr><th>Source</th><th>MD5</th></tr>')
            for d in self.duplicates:
                html.append(f'<tr><td>{_html_escape(d["source"])}</td><td><code>{d["md5"]}</code></td></tr>')
            html.append('</table></details></section>')

        # Errors
        if self.errors:
            html.append('<section class="errors"><h2>Errors</h2>')
            html.append('<table><tr><th>Source</th><th>Error</th></tr>')
            for e in self.errors:
                html.append(f'<tr><td>{_html_escape(e["source"])}</td><td>{_html_escape(e["error"])}</td></tr>')
            html.append('</table></section>')

        html.append(_FOOTER)
        html.append('</body></html>')
        (self.report_dir / "index.html").write_text("\n".join(html), encoding="utf-8")

    def _write_folder_page(self, folder: str, files: list):
        slug = folder.replace("/", "_")
        html = []
        html.append(self._page_head(f"Folder: {folder}", back_link=True))
        html.append(f'<h1>{folder} <span class="count">({len(files)} files)</span></h1>')
        html.append('<div class="file-grid">')
        for f in files:
            html.append(self._render_card(f))
        html.append('</div>')
        html.append(_FOOTER)
        html.append('</body></html>')
        (self.report_dir / f"folder_{slug}.html").write_text("\n".join(html), encoding="utf-8")

    def _write_album_page(self, album: str, files: list):
        slug = _slugify(album)
        html = []
        html.append(self._page_head(f"Album: {album}", back_link=True))
        html.append(f'<h1>Album: {_html_escape(album)} <span class="count">({len(files)} files)</span></h1>')
        html.append('<div class="file-grid">')
        for f in files:
            html.append(self._render_card(f))
        html.append('</div>')
        html.append(_FOOTER)
        html.append('</body></html>')
        (self.report_dir / f"album_{slug}.html").write_text("\n".join(html), encoding="utf-8")

    # ------------------------------------------------------------------
    # Card rendering
    # ------------------------------------------------------------------

    def _render_card(self, f: dict) -> str:
        meta = f.get("metadata", {})

        # Thumbnail
        if f["is_image"]:
            thumb = (f'<div class="thumb"><img loading="lazy" '
                     f'src="file://{_html_escape(f["dest"])}" '
                     f'alt="{_html_escape(f["name"])}"></div>')
        else:
            ext = Path(f["name"]).suffix.upper()
            thumb = f'<div class="thumb vid-thumb">{ext}</div>'

        # EXIF badge with tooltip
        exif_parts = [v for k, v in meta.items()
                      if k in ("camera", "dimensions", "iso", "focal_length", "aperture", "gps")]
        if exif_parts:
            exif_tip = _html_escape(" | ".join(exif_parts))
            src_badge = (f'<span class="badge badge-{f["date_source"]} has-tooltip" '
                         f'data-tooltip="{exif_tip}">{f["date_source"]}</span>')
        else:
            src_badge = f'<span class="badge badge-{f["date_source"]}">{f["date_source"]}</span>'

        # JSON badge with tooltip
        if f["had_json"]:
            json_parts = []
            for key, label in [("photoTakenTime", "Taken"), ("people", "People"),
                                ("geo", "Geo"), ("description", "Desc"),
                                ("device_type", "Device"), ("google_url", "URL")]:
                val = meta.get(key)
                if val:
                    json_parts.append(f"{label}: {val}")
            if json_parts:
                json_tip = _html_escape(" | ".join(json_parts))
                json_badge = (f'<span class="badge badge-json has-tooltip" '
                              f'data-tooltip="{json_tip}">JSON</span>')
            else:
                json_badge = '<span class="badge badge-json">JSON</span>'
        else:
            json_badge = ""

        # View in Finder button
        parent_dir = str(Path(f["dest"]).parent)
        finder_btn = (f'<a class="finder-btn" href="file://{_html_escape(parent_dir)}/" '
                      f'title="Open folder in Finder">Finder</a>')

        # Copy buttons
        copy_name_btn = (f'<button class="copy-btn" onclick="copyText(this, \'{_html_escape(f["name"])}\')" '
                         f'title="Copy filename">Name</button>')
        copy_path_btn = (f'<button class="copy-btn" onclick="copyText(this, \'{_html_escape(f["dest"])}\')" '
                         f'title="Copy full path">Path</button>')

        return (
            f'<div class="file-card">'
            f'{thumb}'
            f'<div class="file-info">'
            f'<div class="file-name" title="{_html_escape(f["name"])}">{_html_escape(f["name"])}</div>'
            f'<div class="file-date">{f["date"]}</div>'
            f'<div class="file-meta">{src_badge} {json_badge} {finder_btn} {copy_name_btn} {copy_path_btn}</div>'
            f'<div class="file-album" title="{_html_escape(f["album"])}">Album: {_html_escape(f["album"])}</div>'
            f'</div></div>'
        )


_FOOTER = (
    '<footer class="site-footer">'
    'Generated by <a href="https://github.com/couzteau/Degoogle-Photos">Degoogle-Photos</a>'
    '</footer>'
)

# ---------------------------------------------------------------------------
# Shared CSS
# ---------------------------------------------------------------------------

_CSS = """\
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
       background: #0d1117; color: #c9d1d9; padding: 20px; line-height: 1.5; }
header { margin-bottom: 30px; }
h1 { color: #58a6ff; font-size: 1.6em; margin-bottom: 10px; }
h2 { color: #58a6ff; margin: 20px 0 12px; font-size: 1.3em; border-bottom: 1px solid #21262d; padding-bottom: 6px; }
h3 { color: #c9d1d9; margin: 14px 0 8px; font-size: 1.1em; }
.updated { color: #8b949e; font-size: 0.9em; margin-top: 4px; }
.back { margin-bottom: 16px; }
.back a { color: #58a6ff; text-decoration: none; font-size: 0.9em; }
.back a:hover { text-decoration: underline; }
.stat-grid { display: flex; gap: 16px; flex-wrap: wrap; margin: 10px 0; }
.stat { background: #161b22; border: 1px solid #21262d; border-radius: 8px;
        padding: 16px 24px; text-align: center; min-width: 140px; }
.stat .num { display: block; font-size: 2em; font-weight: 700; color: #58a6ff; }
.stat .label { color: #8b949e; font-size: 0.85em; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; }
th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid #21262d; font-size: 0.85em; }
th { color: #8b949e; }
.date-sources { width: auto; }
.nav-section { margin-bottom: 24px; }
.folder-nav { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0 20px; }
.folder-nav a { background: #161b22; border: 1px solid #21262d; border-radius: 6px;
                padding: 4px 10px; color: #58a6ff; text-decoration: none; font-size: 0.85em; }
.folder-nav a:hover { background: #1f2937; }
.folder-nav a.review { color: #f0883e; border-color: #f0883e; }
.count { color: #8b949e; font-weight: 400; font-size: 0.9em; }
.file-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
.file-card { background: #161b22; border: 1px solid #21262d; border-radius: 8px; overflow: hidden; }
.thumb { width: 100%; height: 160px; overflow: hidden; display: flex; align-items: center;
         justify-content: center; background: #0d1117; }
.thumb img { width: 100%; height: 100%; object-fit: cover; }
.vid-thumb { color: #8b949e; font-size: 1.4em; font-weight: 700; }
.file-info { padding: 8px 10px; }
.file-name { font-size: 0.8em; font-weight: 600; color: #c9d1d9; white-space: nowrap;
             overflow: hidden; text-overflow: ellipsis; }
.file-date { font-size: 0.75em; color: #8b949e; margin: 2px 0; }
.file-meta { display: flex; gap: 4px; margin: 4px 0; flex-wrap: wrap; align-items: center; }
.file-album { font-size: 0.7em; color: #6e7681; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.badge { font-size: 0.65em; padding: 1px 6px; border-radius: 10px; font-weight: 600; }
.badge-exif { background: #1f6feb33; color: #58a6ff; }
.badge-json_taken { background: #23863633; color: #3fb950; }
.badge-filename { background: #9e6a03aa; color: #e3b341; }
.badge-json_created { background: #23863633; color: #3fb950; }
.badge-mtime { background: #f0883e33; color: #f0883e; }
.badge-none { background: #f8514933; color: #f85149; }
.badge-json { background: #23863633; color: #3fb950; }
/* Tooltip via data-tooltip + ::after */
.has-tooltip { position: relative; cursor: help; }
.has-tooltip:hover::after {
    content: attr(data-tooltip);
    position: absolute; bottom: 120%; left: 50%; transform: translateX(-50%);
    background: #1c2128; color: #c9d1d9; border: 1px solid #30363d; border-radius: 6px;
    padding: 6px 10px; font-size: 0.75em; font-weight: 400; white-space: pre-wrap;
    max-width: 320px; z-index: 100; pointer-events: none; line-height: 1.4;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
}
/* Finder button */
.finder-btn { font-size: 0.6em; padding: 1px 6px; border-radius: 10px; font-weight: 600;
              background: #30363d; color: #c9d1d9; text-decoration: none; border: 1px solid #484f58; }
.finder-btn:hover { background: #484f58; }
.copy-btn { font-size: 0.6em; padding: 1px 6px; border-radius: 10px; font-weight: 600;
            background: #30363d; color: #c9d1d9; border: 1px solid #484f58; cursor: pointer;
            font-family: inherit; }
.copy-btn:hover { background: #484f58; }
details { margin: 8px 0; }
summary { cursor: pointer; color: #58a6ff; font-size: 0.9em; }
.errors table td { color: #f85149; }
code { font-size: 0.8em; color: #8b949e; }
.site-footer { margin-top: 40px; padding: 16px 0; border-top: 1px solid #21262d;
               text-align: center; font-size: 0.8em; color: #8b949e; }
.site-footer a { color: #58a6ff; text-decoration: none; }
.site-footer a:hover { text-decoration: underline; }
"""
