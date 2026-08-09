#!/usr/bin/env python3
"""CLI: zone-boundary vs center hypothesis for DISPLACEMENT enrichment."""
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
    ap.add_argument("--out-dir", default="results/zone_maps")
    ap.add_argument("--stem", default="xauusd_phase1_boundary_hypothesis")
    ap.add_argument("--no-guard-xauusd", action="store_true")
    args = ap.parse_args()

    csv_path = args.csv
    if not args.no_guard_xauusd and args.instrument.upper() == "XAUUSD":
        from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path

        csv_path = str(guard_xauusd_csv_path(csv_path, "XAUUSD"))

    from research.zone_mapping.boundary_hypothesis_eval import (
        boundary_eval_to_markdown,
        run_from_csv,
    )

    print(f"Boundary hypothesis eval on {csv_path} …", flush=True)
    ev = run_from_csv(csv_path, instrument=args.instrument)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    jp = out / f"{args.stem}.json"
    mp = out / f"{args.stem}.md"
    jp.write_text(json.dumps(ev, indent=2), encoding="utf-8")
    mp.write_text(
        boundary_eval_to_markdown(
            ev, title=f"Boundary hypothesis — {args.instrument}"
        ),
        encoding="utf-8",
    )
    print(f"wrote {jp}")
    print(f"wrote {mp}")
    for ctx, pack in (ev.get("by_context") or {}).items():
        if pack.get("insufficient"):
            continue
        hs = pack.get("hypothesis_support") or {}
        print(
            f"{ctx}: Δmargin(DISP-other)={pack.get('delta_margin_disp_minus_other')} "
            f"Δscore={pack.get('delta_score_disp_minus_other')} "
            f"boundary_ok={hs.get('boundary_hyp_supported_for_state')} "
            f"score_inv={hs.get('score_inverted_for_state')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
