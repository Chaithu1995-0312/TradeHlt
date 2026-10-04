#!/usr/bin/env python3
"""CLI: rare-zone entry × CRT context (RANGE vs SWEEP) precision/recall/calibration."""
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
    ap.add_argument("--K", default="1,2,3,5,10")
    ap.add_argument("--out-dir", default="results/zone_maps")
    ap.add_argument("--stem", default="xauusd_phase1_rare_zone_context_filter")
    ap.add_argument("--no-guard-xauusd", action="store_true")
    args = ap.parse_args()

    csv_path = args.csv
    if not args.no_guard_xauusd and args.instrument.upper() == "XAUUSD":
        from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path

        csv_path = str(guard_xauusd_csv_path(csv_path, "XAUUSD"))

    K_values = [int(x.strip()) for x in args.K.split(",") if x.strip()]

    from research.zone_mapping.rare_zone_context_filter_eval import (
        context_eval_to_markdown,
        run_from_csv,
    )

    print(f"Context-filter eval on {csv_path} K={K_values} …", flush=True)
    ev = run_from_csv(csv_path, instrument=args.instrument, K_values=K_values)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    jp = out / f"{args.stem}.json"
    mp = out / f"{args.stem}.md"
    jp.write_text(json.dumps(ev, indent=2), encoding="utf-8")
    mp.write_text(
        context_eval_to_markdown(
            ev,
            title=f"Rare-zone × CRT context — {args.instrument}",
        ),
        encoding="utf-8",
    )
    print(f"wrote {jp}")
    print(f"wrote {mp}")
    print("context counts:", ev.get("signal_counts_by_crt_context"))
    for K in K_values:
        inter = ev["by_K"][str(K)]["interaction_RANGE_vs_SWEEP"]
        print(
            f"K={K}: ΔP(SWEEP-RANGE)={inter.get('precision_SWEEP_minus_RANGE')} "
            f"ratio={inter.get('precision_ratio_SWEEP_over_RANGE')} "
            f"keep_SWEEP P={inter['filter_keep_SWEEP_only'].get('precision')} "
            f"R={inter['filter_keep_SWEEP_only'].get('recall')} "
            f"retain={inter['filter_keep_SWEEP_only'].get('signal_retention')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
