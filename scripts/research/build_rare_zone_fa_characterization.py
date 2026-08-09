#!/usr/bin/env python3
"""CLI: partition rare-zone FAs by zone; label 20-bar CRT evolution; vs TPs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="data/mt5/XAUUSD_M15.csv")
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--K", type=int, default=5)
    ap.add_argument("--follow", type=int, default=20)
    ap.add_argument("--out-dir", default="results/zone_maps")
    ap.add_argument("--stem", default="xauusd_phase1_rare_zone_fa_char")
    ap.add_argument("--no-guard-xauusd", action="store_true")
    args = ap.parse_args()

    csv_path = args.csv
    if not args.no_guard_xauusd and args.instrument.upper() == "XAUUSD":
        from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path

        csv_path = str(guard_xauusd_csv_path(csv_path, "XAUUSD"))

    from research.zone_mapping.rare_zone_fa_characterization import (
        fa_char_to_markdown,
        run_from_csv,
    )

    print(
        f"FA characterization on {csv_path} K={args.K} follow={args.follow} …",
        flush=True,
    )
    rep = run_from_csv(
        csv_path, instrument=args.instrument, K=args.K, follow=args.follow
    )
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    # Drop ultra-verbose path lists from JSON if any — keep samples only
    jp = out / f"{args.stem}.json"
    mp = out / f"{args.stem}.md"
    jp.write_text(json.dumps(rep, indent=2), encoding="utf-8")
    mp.write_text(
        fa_char_to_markdown(
            rep,
            title=f"Rare-zone FA characterization — {args.instrument} (K={args.K})",
        ),
        encoding="utf-8",
    )
    print(f"n_sig={rep['n_signals']} TP={rep['n_tp']} FA={rep['n_fa']}")
    print("FA top evolutions:", list((rep['overall']['FA']['by_primary'] or {}).items())[:6])
    print("TP top evolutions:", list((rep['overall']['TP']['by_primary'] or {}).items())[:6])
    print(f"wrote {jp}")
    print(f"wrote {mp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
