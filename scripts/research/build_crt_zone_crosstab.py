#!/usr/bin/env python3
"""CLI: CRT State × Zone cross-tabulation on XAUUSD Phase-1 (or any OHLCV)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    ap = argparse.ArgumentParser(description="CRT × Zone geometry relevance cross-tab")
    ap.add_argument("--csv", default="data/mt5/XAUUSD_M15.csv")
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--out-dir", default="results/zone_maps")
    ap.add_argument("--stem", default="xauusd_phase1_crt_zone_crosstab")
    ap.add_argument("--no-guard-xauusd", action="store_true")
    args = ap.parse_args()

    csv_path = args.csv
    if not args.no_guard_xauusd and args.instrument.upper() == "XAUUSD":
        from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path

        csv_path = str(guard_xauusd_csv_path(csv_path, "XAUUSD"))

    from research.zone_mapping.crt_zone_crosstab import (
        collect_crt_zone_joint_labels,
        compute_crt_zone_crosstab,
        crosstab_to_markdown,
    )
    from research.zone_mapping.historical_zone_mapper import ZoneMapConfig
    from research.zone_mapping.build_corpus_zone_map import _registry_zone_ids

    zcfg = ZoneMapConfig.from_prod_engine_runner()
    print(f"Collecting CRT×Zone joint labels on {csv_path} …", flush=True)
    labels = collect_crt_zone_joint_labels(
        csv_path, instrument=args.instrument, zone_config=zcfg
    )
    print(f"joint bars={len(labels)}", flush=True)
    xt = compute_crt_zone_crosstab(
        labels, registry_zone_ids=_registry_zone_ids(zcfg.registry_path)
    )
    xt["meta"] = {
        "instrument": args.instrument,
        "csv_path": csv_path,
        "registry_path": zcfg.registry_path,
        "zone_cluster_threshold": zcfg.zone_cluster_threshold,
        "n_labels": len(labels),
    }

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    jp = out / f"{args.stem}.json"
    mp = out / f"{args.stem}.md"
    jp.write_text(json.dumps(xt, indent=2), encoding="utf-8")
    mp.write_text(
        crosstab_to_markdown(
            xt, title=f"CRT State × Zone — {args.instrument} Phase-1"
        ),
        encoding="utf-8",
    )
    print(f"wrote {jp}")
    print(f"wrote {mp}")
    print("Top concentrations:")
    for r in (xt.get("concentrations") or [])[:10]:
        print(
            f"  {r['crt_state']:16s} × {r['zone_id']}: "
            f"n={r['count']} lift={r['lift']:.2f} P(z|s)={r['p_zone_given_state']:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
