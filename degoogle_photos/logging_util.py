"""Migration logging — file + console progress reporting."""

import time
import webbrowser
from pathlib import Path

from .report import HtmlReport


class MigrationLog:
    """Handles logging to file and console progress."""

    def __init__(self, output_root: Path, dry_run: bool, progress_interval: int = 500):
        self.output_root = output_root
        self.dry_run = dry_run
        self.progress_interval = progress_interval
        self.copied = 0
        self.skipped_dupes = 0
        self.skipped_resume = 0
        self.needs_review = 0
        self.errors = 0
        self.total = 0
        self._log_lines = []
        self._review_lines = []
        self._start_time = time.time()
        self.html = HtmlReport(output_root, dry_run)

    def log(self, msg: str):
        self._log_lines.append(msg)

    def log_review(self, media_path: Path, reason: str):
        self._review_lines.append(f"{media_path}  -- {reason}")

    def progress(self, current: int, total: int):
        self.html.processed = current
        self.html.maybe_write(current)
        if current % self.progress_interval == 0 or current == total:
            elapsed = time.time() - self._start_time
            rate = current / elapsed if elapsed > 0 else 0
            pct = current / total * 100 if total > 0 else 0
            prefix = "[DRY RUN] " if self.dry_run else ""
            print(
                f"\r{prefix}Progress: {current}/{total} ({pct:.1f}%) "
                f"| {rate:.0f} files/sec "
                f"| copied={self.copied} dupes={self.skipped_dupes} "
                f"review={self.needs_review} errors={self.errors}",
                end="", flush=True,
            )

    def write_logs(self):
        prefix = "[DRY RUN] " if self.dry_run else ""
        elapsed = time.time() - self._start_time

        # Final HTML write
        self.html._write()
        print(f"\nHTML report: {self.html.report_dir / 'index.html'}")

        summary = (
            f"\n{'='*60}\n"
            f"{prefix}Migration Summary\n"
            f"{'='*60}\n"
            f"Total media files found:  {self.total}\n"
            f"Copied:                   {self.copied}\n"
            f"Skipped (duplicates):     {self.skipped_dupes}\n"
            f"Skipped (already copied): {self.skipped_resume}\n"
            f"Needs review:             {self.needs_review}\n"
            f"Errors:                   {self.errors}\n"
            f"Time elapsed:             {elapsed:.1f}s\n"
            f"{'='*60}\n"
        )
        print(summary)

        if not self.dry_run:
            self.output_root.mkdir(parents=True, exist_ok=True)
            log_path = self.output_root / "migration_log.txt"
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(summary)
                f.write("\nDetailed Log:\n")
                for line in self._log_lines:
                    f.write(line + "\n")
            print(f"Log written to: {log_path}")

            if self._review_lines:
                review_dir = self.output_root / "needs_review"
                review_dir.mkdir(parents=True, exist_ok=True)
                readme = review_dir / "README.txt"
                with open(readme, "w", encoding="utf-8") as f:
                    f.write("Files placed here could not be assigned a date.\n")
                    f.write("Review manually and move to the correct YYYY/MM/ folder.\n\n")
                    for line in self._review_lines:
                        f.write(line + "\n")
                print(f"Review log written to: {readme}")
        else:
            print("(Dry run — no files written)")

        # Print paths and open report at the very end
        report_index = self.html.report_dir / "index.html"
        print(f"\nOutput folder: {self.output_root.resolve()}")
        print(f"HTML report:   {report_index.resolve()}")
        if report_index.exists():
            webbrowser.open(report_index.resolve().as_uri())
