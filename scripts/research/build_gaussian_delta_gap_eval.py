#!/usr/bin/env python3
"""CLI: H-GAUSS-DELTA-001 — signed Δ=ML−H calibration-gap study (measure-only).

Prereg: docs/research-readiness/h-gauss-delta-001-preregistration.md

Does NOT build a coordinator, flip gaussian_impl, or write production config.

Usage
-----
  python scripts/research/build_gaussian_delta_gap_eval.py --instrument BNBUSDT
  python scripts/research/build_gaussian_delta_gap_eval.py --instrument ETHUSDT
  python scripts/research/build_gaussian_delta_gap_eval.py --all-majors
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

MAJORS = ("BNBUSDT", "ETHUSDT", "BTCUSDT", "SOLUSDT")


def _default_csv(instrument: str) -> str:
    return f"data/{instrument.upper()}_M15.csv"


def _run_one(
    instrument: str,
    csv_path: str,
    out_dir: Path,
    *,
    max_bars: int,
    progress_every: int,
) -> dict:
    from research.zone_mapping.gaussian_delta_gap_eval import (
        report_to_markdown,
        run_from_csv,
    )

    print(f"=== {instrument} H-GAUSS-DELTA-001 on {csv_path} ===", flush=True)
    if not Path(csv_path).exists():
        rep = {
            "program": "H-GAUSS-DELTA-001",
            "instrument": instrument,
            "skipped": True,
            "skip_reason": f"csv_missing:{csv_path}",
        }
    else:
        rep = run_from_csv(
            csv_path,
            instrument=instrument,
            max_bars=max_bars,
            progress_every=progress_every,
        )
    stem = f"{instrument.lower()}_h_gauss_delta_001"
    out_dir.mkdir(parents=True, exist_ok=True)
    jp = out_dir / f"{stem}.json"
    mp = out_dir / f"{stem}.md"
    jp.write_text(json.dumps(rep, indent=2), encoding="utf-8")
    mp.write_text(report_to_markdown(rep), encoding="utf-8")
    print(f"wrote {jp}", flush=True)
    print(f"wrote {mp}", flush=True)
    if rep.get("skipped"):
        print(f"  SKIP: {rep.get('skip_reason')}", flush=True)
    else:
        gate = rep.get("gate") or {}
        print(f"  verdict={gate.get('program_verdict')}", flush=True)
        for s in rep.get("strata") or []:
            if s.get("primary"):
                print(
                    f"  {s.get('stratum')}: claim={s.get('claim')} n_oos={s.get('n_oos')}",
                    flush=True,
                )
    return rep


def main() -> int:
    ap = argparse.ArgumentParser(
        description="H-GAUSS-DELTA-001 calibration gap study (research only)"
    )
    ap.add_argument("--instrument", default="BNBUSDT")
    ap.add_argument("--csv", default="")
    ap.add_argument("--all-majors", action="store_true")
    ap.add_argument("--out-dir", default="results/zone_maps")
    ap.add_argument("--max-bars", type=int, default=0)
    ap.add_argument("--progress-every", type=int, default=10000)
    args = ap.parse_args()

    out = Path(args.out_dir)
    instruments = list(MAJORS) if args.all_majors else [args.instrument.upper()]
    results = []
    for inst in instruments:
        csv_path = args.csv if (args.csv and not args.all_majors) else _default_csv(inst)
        results.append(
            _run_one(
                inst,
                csv_path,
                out,
                max_bars=max(0, int(args.max_bars)),
                progress_every=max(0, int(args.progress_every)),
            )
        )

    if args.all_majors:
        pooled = {
            "program": "H-GAUSS-DELTA-001",
            "schema_version": "h_gauss_delta_001_pooled_v1",
            "authority": "research_only",
            "instruments": instruments,
            "per_instrument_verdicts": {
                r.get("instrument"): (r.get("gate") or {}).get("program_verdict")
                if not r.get("skipped")
                else f"SKIP:{r.get('skip_reason')}"
                for r in results
            },
            "notes": [
                "Pooled rollup is navigational only; primary claims stay per-instrument cells.",
                "Coordinator / fusion wire remain unauthorized.",
            ],
        }
        pj = out / "pooled_h_gauss_delta_001.json"
        pj.write_text(json.dumps(pooled, indent=2), encoding="utf-8")
        print(f"wrote {pj}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
