"""replay_allocator.py — CLI wrapper for the PortfolioAllocator shadow replay (F-013).

Thin wrapper per conventions (CLAUDE.md §3.3): all logic lives in src/portfolio/replay.py.

Streams a closed-trade ledger (JSONL, one record per line) through PortfolioAllocator and reports
what it WOULD have allocated. Read-only, SHADOW ONLY, earns no authority.

Ledger record (see src/portfolio/replay.py CONTRACT — all required):
    {"trade_id": "...", "symbol": "XAUUSD", "open_index": 0, "close_index": 6,
     "confidence": 0.72, "realized_r": 1.4}   # optional: "rr", "regime"

Usage:
    python scripts/portfolio/replay_allocator.py --ledger results/.../trades.jsonl \
        [--out results/portfolio/allocator_replay.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from src.portfolio.replay import replay_allocator  # noqa: E402


def _load_ledger(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise SystemExit(f"{path}:{ln}: invalid JSON: {e}")
    return records


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ledger", required=True, help="closed-trade ledger JSONL path")
    ap.add_argument("--out", default=None, help="optional JSON output path for the full result")
    args = ap.parse_args()

    ledger = Path(args.ledger)
    if not ledger.exists():
        raise SystemExit(f"ledger not found: {ledger}")

    result = replay_allocator(_load_ledger(ledger))
    d = result.to_dict()

    print(f"records={d['n_records']} allocated={d['n_allocated']} rejected={d['n_rejected']}")
    print(f"reason_histogram={d['reason_histogram']}")
    print(f"allocator_pnl={d['allocator_pnl']:+.5f}  "
          f"take_every_pnl={d['take_every_pnl']:+.5f}  "
          f"(base_risk={d['take_every_base_risk']:.5f})")
    print(f"allocator_config={d['allocator_config']}")
    print("NOTE: SHADOW ONLY - no authority (F-013 allocator is orphaned from the live spine).")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(d, indent=2), encoding="utf-8")
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
