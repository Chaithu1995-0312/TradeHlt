#!/usr/bin/env python3
"""CLI: rare-zone entry as DISPLACEMENT event detector (precision/recall/baselines)."""
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
    ap.add_argument("--K", default="1,2,3,5,10", help="Comma-separated horizons")
    ap.add_argument("--random-trials", type=int, default=50)
    ap.add_argument("--out-dir", default="results/zone_maps")
    ap.add_argument("--stem", default="xauusd_phase1_rare_zone_detection_eval")
    ap.add_argument("--no-guard-xauusd", action="store_true")
    args = ap.parse_args()

    csv_path = args.csv
    if not args.no_guard_xauusd and args.instrument.upper() == "XAUUSD":
        from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path

        csv_path = str(guard_xauusd_csv_path(csv_path, "XAUUSD"))

    K_values = [int(x.strip()) for x in args.K.split(",") if x.strip()]

    from research.zone_mapping.rare_zone_detection_eval import (
        detection_eval_to_markdown,
        run_eval_from_csv,
    )

    print(f"Evaluating rare-zone detection on {csv_path} K={K_values} …", flush=True)
    ev = run_eval_from_csv(
        csv_path,
        instrument=args.instrument,
        K_values=K_values,
        n_random_trials=args.random_trials,
    )
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    jp = out / f"{args.stem}.json"
    mp = out / f"{args.stem}.md"
    jp.write_text(json.dumps(ev, indent=2), encoding="utf-8")
    mp.write_text(
        detection_eval_to_markdown(
            ev,
            title=f"Rare-zone → DISPLACEMENT detection — {args.instrument}",
        ),
        encoding="utf-8",
    )
    print(f"wrote {jp}")
    print(f"wrote {mp}")
    for K in K_values:
        pack = ev["by_K"][str(K)]
        r = pack["rare_zone_entry"]
        rnd = pack["random_timing"]
        p = pack["persistent_zone_entry"]
        print(
            f"K={K}: rare P={r['precision']:.3f} R={r['recall']:.3f} "
            f"| random P={rnd['precision_mean']:.3f} "
            f"| persistent P={p['precision']:.3f} "
            f"| ΔP_rand={pack['precision_delta_vs_random']:+.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
