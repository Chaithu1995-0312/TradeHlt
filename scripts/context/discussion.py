"""
discussion.py (CLI) — rewind / read the multi-LLM discussion (view-only time-travel).

Usage:
  python scripts/context/discussion.py --full
  python scripts/context/discussion.py --rewind t00012_ab12cd34
  python scripts/context/discussion.py --digest
  python scripts/context/discussion.py --verify     # integrity: re-hash stored turns vs ledger
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
try:  # preserve non-ASCII (em-dashes etc.) without crashing a cp1252 console
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from multi_llm import discussion as D  # noqa: E402
from multi_llm.turn_ledger import TurnLedger  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--full", action="store_true", help="whole discussion from start")
    g.add_argument("--rewind", metavar="TURN_ID", help="discussion as it stood up to TURN_ID")
    g.add_argument("--digest", action="store_true", help="compact 'discussion so far'")
    g.add_argument("--verify", action="store_true", help="re-hash stored turns vs the ledger")
    args = ap.parse_args()

    if args.verify:
        problems = TurnLedger().verify()
        if problems:
            print("INTEGRITY PROBLEMS:")
            for p in problems:
                print(f"  - {p}")
            sys.exit(1)
        print("ledger integrity: OK (all verbatim turns match)")
        return

    records = D.load_records()
    if args.full:
        print(D.full(records))
    elif args.rewind:
        print(D.rewind(records, args.rewind))
    else:
        print(D.digest(records))


if __name__ == "__main__":
    main()
