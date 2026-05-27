"""
reorganize_results.py
Move stray top-level run_{ts}_{COIN}/ directories in results/ into
results/{COIN}/run_{ts}_{COIN}/ (mirroring the portfolio_raw/ convention).

Dirs NOT touched: results/portfolio_raw/, results/AGENT/, results/LIVE/,
results/DATA/, top-level .json files.

Usage:
    python scripts/maintenance/reorganize_results.py [--dry-run]
"""
import argparse
import re
import shutil
from pathlib import Path

_RESULTS_DIR = Path("results")
_SKIP_NAMES = {"portfolio_raw", "AGENT", "LIVE", "DATA", "PROMOTION"}

_RUN_DIR_RE = re.compile(r"^run_(\d{8}_\d{6})_(.+)$")


def _collect_stray_runs(results_dir: Path) -> list[tuple[Path, str]]:
    """Return (dir_path, coin) for each top-level run_*_COIN dir."""
    stray = []
    for d in sorted(results_dir.iterdir()):
        if not d.is_dir():
            continue
        if d.name in _SKIP_NAMES:
            continue
        m = _RUN_DIR_RE.match(d.name)
        if m:
            coin = m.group(2)
            stray.append((d, coin))
    return stray


def run(dry_run: bool) -> None:
    if not _RESULTS_DIR.is_dir():
        print(f"[ERROR] results/ not found at {_RESULTS_DIR.absolute()}")
        return

    stray = _collect_stray_runs(_RESULTS_DIR)

    if not stray:
        print("Nothing to reorganize — no stray run_*_COIN dirs found at results/ root.")
        return

    print(f"Found {len(stray)} stray run dir(s):" + (" [DRY-RUN]" if dry_run else ""))
    for src, coin in stray:
        dest = _RESULTS_DIR / coin / src.name
        print(f"  {src.name}  →  {coin}/{src.name}")

    if not dry_run:
        confirm = input("\nProceed? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return

    moved = errors = 0
    for src, coin in stray:
        dest_parent = _RESULTS_DIR / coin
        dest = dest_parent / src.name
        if dry_run:
            moved += 1
            continue
        try:
            dest_parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            moved += 1
        except Exception as exc:
            print(f"[ERROR] {src.name}: {exc}")
            errors += 1

    label = "Would move" if dry_run else "Moved"
    print(f"\n{label}: {moved}  |  Errors: {errors}")
    if dry_run and moved:
        print("Re-run without --dry-run to apply.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Move stray results/run_*_COIN/ dirs under results/{COIN}/")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would happen without moving")
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
