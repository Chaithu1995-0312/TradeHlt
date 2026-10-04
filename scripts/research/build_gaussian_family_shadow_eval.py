#!/usr/bin/env python3
"""CLI: Gaussian family shadow_ml agreement + geometry-conditioned economics.

Research-only. Writes under results/zone_maps/ (or --out-dir).
No config edit, no fusion wire, no promotion.

Usage
-----
  python scripts/research/build_gaussian_family_shadow_eval.py
  python scripts/research/build_gaussian_family_shadow_eval.py --instrument BNBUSDT
  python scripts/research/build_gaussian_family_shadow_eval.py --instrument ETHUSDT \\
      --csv data/ETHUSDT_M15.csv --econ-stride 2
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def _default_csv(instrument: str) -> str:
    inst = instrument.upper()
    if inst == "XAUUSD":
        return "data/mt5/XAUUSD_M15.csv"
    return f"data/{inst}_M15.csv"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Gaussian H/ML shadow_ml family measurement (research only)"
    )
    ap.add_argument("--instrument", default="BNBUSDT")
    ap.add_argument("--csv", default="")
    ap.add_argument("--out-dir", default="results/zone_maps")
    ap.add_argument("--stem", default="")
    ap.add_argument(
        "--candidate-mode",
        default="sweep_or_rare_entry",
        choices=(
            "sweep_or_rare_entry",
            "sweep",
            "rare_entry",
            "trade_opened",
            "all_directional",
        ),
    )
    ap.add_argument(
        "--econ-stride",
        type=int,
        default=1,
        help="Subsample candidates for forward_walk (1=all)",
    )
    ap.add_argument(
        "--max-bars",
        type=int,
        default=0,
        help="Cap post-warmup bars (0=all; for smoke tests)",
    )
    ap.add_argument("--progress-every", type=int, default=5000)
    args = ap.parse_args()

    instrument = args.instrument.upper()
    csv_path = args.csv or _default_csv(instrument)
    if instrument == "XAUUSD":
        from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path

        csv_path = str(guard_xauusd_csv_path(csv_path, "XAUUSD"))

    csv_p = Path(csv_path)
    if not csv_p.exists():
        print(f"ERROR: csv not found: {csv_path}", file=sys.stderr)
        return 2

    from research.zone_mapping.gaussian_family_shadow_eval import (
        report_to_markdown,
        run_from_csv,
    )

    stem = args.stem or f"{instrument.lower()}_gaussian_family_shadow"
    print(
        f"Gaussian family shadow_ml eval on {csv_path} ({instrument}) …",
        flush=True,
    )
    rep = run_from_csv(
        str(csv_p),
        instrument=instrument,
        candidate_mode=args.candidate_mode,
        econ_stride=max(1, int(args.econ_stride)),
        max_bars=max(0, int(args.max_bars)),
        progress_every=max(0, int(args.progress_every)),
    )

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    jp = out / f"{stem}.json"
    mp = out / f"{stem}.md"
    jp.write_text(json.dumps(rep, indent=2), encoding="utf-8")
    mp.write_text(
        report_to_markdown(rep, title=f"Gaussian family shadow — {instrument}"),
        encoding="utf-8",
    )
    print(f"wrote {jp}")
    print(f"wrote {mp}")

    o = rep.get("overall") or {}
    print(
        f"OVERALL n={o.get('n')} agree={o.get('agreement_rate')} "
        f"|Δ|={o.get('mean_abs_delta')} ml_fallback={o.get('ml_fallback_rate')}"
    )
    for ctx in ("SWEEP", "RANGE", "RARE_ENTRY", "BOUNDARY", "RARE_ENTRY_SWEEP"):
        p = (rep.get("by_geometry_context") or {}).get(ctx) or {}
        if not p.get("n"):
            continue
        print(
            f"  {ctx:<18} n={p.get('n'):<6} agree={p.get('agreement_rate')} "
            f"|Δ|={p.get('mean_abs_delta')} high={p.get('agree_high_rate')}"
        )
    econ = (rep.get("economic") or {}).get("subsets") or {}
    print("ECONOMIC (candidate base):")
    for name in ("base", "h_pass", "ml_pass", "agree_high", "disagree"):
        s = econ.get(name) or {}
        print(
            f"  {name:<12} n={s.get('n')} E={s.get('expectancy_rr_net')} "
            f"WR={s.get('win_rate')} PF={s.get('profit_factor')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
