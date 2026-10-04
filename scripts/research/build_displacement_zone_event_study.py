#!/usr/bin/env python3
"""CLI: DISPLACEMENT lead/lag vs rare zone entries (1/4/5/6)."""
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
    ap.add_argument("--half-window", type=int, default=10)
    ap.add_argument("--out-dir", default="results/zone_maps")
    ap.add_argument("--stem", default="xauusd_phase1_displacement_zone_event_study")
    ap.add_argument("--no-guard-xauusd", action="store_true")
    args = ap.parse_args()

    csv_path = args.csv
    if not args.no_guard_xauusd and args.instrument.upper() == "XAUUSD":
        from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path

        csv_path = str(guard_xauusd_csv_path(csv_path, "XAUUSD"))

    from research.zone_mapping.displacement_zone_event_study import (
        event_study_to_markdown,
        run_study_from_csv,
    )

    print(f"Running DISPLACEMENT×zone event study on {csv_path} …", flush=True)
    es, _labels = run_study_from_csv(
        csv_path, instrument=args.instrument, half_window=args.half_window
    )
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    jp = out / f"{args.stem}.json"
    mp = out / f"{args.stem}.md"
    # Drop bulky first_entry_lags lists from MD-facing copy? keep full in JSON
    jp.write_text(json.dumps(es, indent=2), encoding="utf-8")
    mp.write_text(
        event_study_to_markdown(
            es,
            title=f"DISPLACEMENT lead/lag × rare zones — {args.instrument}",
        ),
        encoding="utf-8",
    )
    print(f"n_displacement_starts={es['n_displacement_starts']}")
    print(f"baseline_rare_rate={es['baseline_rare_zone_rate']:.4f}")
    any_r = es["rare_entry_timing"]["any_rare"]
    print(
        f"any_rare first-entry: n={any_r.get('n')} mean_lag={any_r.get('mean_lag')} "
        f"P(before)={any_r.get('frac_before')} P(0)={any_r.get('frac_at_0')} P(after)={any_r.get('frac_after')}"
    )
    print(f"wrote {jp}")
    print(f"wrote {mp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
