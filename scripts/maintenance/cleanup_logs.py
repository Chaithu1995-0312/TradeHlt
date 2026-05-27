"""
cleanup_logs.py
Archive flat log files in logs/ that are older than --days days.

Governance files (agent_*.jsonl, expansion_*.jsonl) and backtest_debug.log
are never moved. Run directories (logs/run_*/) are left untouched.

Usage:
    python scripts/maintenance/cleanup_logs.py [--days 7] [--dry-run]
"""
import argparse
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Force UTF-8 output on Windows so arrow/dash characters print cleanly
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Files that must never be archived regardless of age
_PROTECTED = {
    "agent_audit.jsonl",
    "agent_findings.jsonl",
    "agent_intent_log.jsonl",
    "agent_llm_requests.jsonl",
    "expansion_rejected.jsonl",
    "expansion_trace.jsonl",
    "backtest_debug.log",
    "integrity_events.jsonl",
}

_LOG_DIR = Path("logs")


def _archive_dir(file_mtime: datetime) -> Path:
    return _LOG_DIR / "archive" / file_mtime.strftime("%Y%m")


def run(days: int, dry_run: bool) -> None:
    cutoff = datetime.now() - timedelta(days=days)
    moved = skipped = errors = 0

    for f in sorted(_LOG_DIR.iterdir()):
        # Only operate on flat files (not subdirs like run_*/ or archive/)
        if not f.is_file():
            continue
        if f.name in _PROTECTED:
            skipped += 1
            continue

        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if mtime >= cutoff:
            skipped += 1
            continue

        dest_dir = _archive_dir(mtime)
        dest = dest_dir / f.name

        if dry_run:
            print(f"[DRY-RUN] MOVE {f.name}  →  {dest_dir.relative_to(_LOG_DIR)}/")
            moved += 1
            continue

        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(dest))
            moved += 1
        except Exception as exc:
            print(f"[ERROR] {f.name}: {exc}")
            errors += 1

    label = "Would move" if dry_run else "Moved"
    print(f"\n{label}: {moved}  |  Skipped (recent/protected): {skipped}  |  Errors: {errors}")
    if dry_run and moved:
        print("Re-run without --dry-run to apply.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive old flat log files from logs/")
    parser.add_argument("--days", type=int, default=7,
                        help="Files older than this many days are archived (default: 7)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would happen without moving files")
    args = parser.parse_args()

    if not _LOG_DIR.is_dir():
        print(f"[ERROR] logs/ directory not found at {_LOG_DIR.absolute()}")
        return

    print(f"Scanning {_LOG_DIR.absolute()} — archiving files older than {args.days} days"
          + (" [DRY-RUN]" if args.dry_run else ""))
    run(days=args.days, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
