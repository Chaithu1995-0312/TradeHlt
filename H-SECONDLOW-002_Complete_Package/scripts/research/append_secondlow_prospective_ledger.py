#!/usr/bin/env python3
"""Append POST_DISCOVERY independent events to secondlow_prospective_events.jsonl."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from research.secondlow_v1.corpus import CANONICAL_XAUUSD_M15
from research.secondlow_v1.detector import (
    DISCOVERY_END,
    detect_independent_events,
    load_ohlcv,
    sha256_prefix,
)

LEDGER = _REPO / "data/secondlow_prospective_events.jsonl"
HYPOTHESIS_DEFAULT = "H-SECONDLOW-004"
DETECTOR_ID = "secondlow_v1"


def _git_sha_short() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_REPO,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _load_existing_times(path: Path) -> set[pd.Timestamp]:
    if not path.exists():
        return set()
    times: set[pd.Timestamp] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        times.add(pd.Timestamp(row["purge_time"]))
    return times


def main() -> None:
    parser = argparse.ArgumentParser(description="Append POST_DISCOVERY events to prospective ledger")
    parser.add_argument("--csv", type=Path, default=_REPO / CANONICAL_XAUUSD_M15)
    parser.add_argument("--hypothesis-id", default=HYPOTHESIS_DEFAULT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    corpus = args.csv.resolve()
    df = load_ohlcv(corpus)
    corpus_hash = sha256_prefix(corpus)
    collected_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    git_sha = _git_sha_short()

    _, events = detect_independent_events(df, require_post_window=True)
    post_events = [e for e in events if e.purge_time > DISCOVERY_END]

    existing = _load_existing_times(LEDGER)
    new_events = [e for e in post_events if e.purge_time not in existing]

    rows = []
    for e in new_events:
        rows.append(
            {
                "purge_time": e.purge_time.strftime("%Y-%m-%d %H:%M:%S"),
                "corpus_hash_prefix": corpus_hash,
                "detector": DETECTOR_ID,
                "detector_git_sha": git_sha,
                "collected_at": collected_at,
                "hypothesis_id": args.hypothesis_id,
                "post_window_complete": True,
            }
        )

    report = {
        "corpus": str(corpus),
        "corpus_hash_prefix": corpus_hash,
        "corpus_last_bar": str(df.index[-1]),
        "n_post_discovery_independent": len(post_events),
        "n_already_in_ledger": len(post_events) - len(new_events),
        "n_appended": len(rows),
        "appended_times": [r["purge_time"] for r in rows],
        "ledger_path": str(LEDGER),
        "dry_run": args.dry_run,
    }

    if rows and not args.dry_run:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, separators=(",", ": ")) + "\n")

    out_dir = _REPO / "H-SECONDLOW-002_Complete_Package/results/prospective_fetch"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "prospective_ledger_append.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"\nWrote {report_path}")
    if args.dry_run:
        print("(dry-run — ledger not modified)")
    elif rows:
        print(f"Appended {len(rows)} line(s) to {LEDGER}")


if __name__ == "__main__":
    main()