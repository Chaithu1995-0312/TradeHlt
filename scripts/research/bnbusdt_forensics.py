# -*- coding: utf-8 -*-
"""
bnbusdt_forensics.py — Layer-6 forensic root-cause analysis (thin CLI).

Runs BOTH shipped behaviors (expansion_breakout, mean_reversion) on BNBUSDT only, replays
every signal under intrabar_fixed (governing) and close_only (measure-only optimistic bound),
persists per-trade JSONL, and writes the aggregated forensic report.

EXPLANATION ONLY — no optimization, no new hypotheses, no promotion.

Usage:
    python scripts/research/bnbusdt_forensics.py
    python scripts/research/bnbusdt_forensics.py --behaviors expansion_breakout
"""

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import research.controls   # noqa: F401  (register controls)
import research.hypotheses  # noqa: F401  (register hypotheses)
from research.config import DEFAULT_CONFIG_PATH, ResearchConfig  # noqa: E402
from research.forensics import build_report, collect_records     # noqa: E402
from utils.console_safe import safe_print                        # noqa: E402

_SIGNAL_KEYS = ("trade_id", "timestamp", "hour", "dow", "month", "direction", "entry", "atr")


def _write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="BNBUSDT Layer-6 forensics")
    ap.add_argument("--behaviors", default="expansion_breakout,mean_reversion")
    ap.add_argument("--instrument", default="BNBUSDT")
    ap.add_argument("--csv", default=None)
    ap.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    ap.add_argument("--out", default=str(_ROOT / "results" / "research"))
    args = ap.parse_args()

    # Pin the spine source to the SAME config (so spine.prod_version follows --config).
    import os
    os.environ["RESEARCH_SPINE_CONFIG"] = str(args.config)
    cfg = ResearchConfig.from_file(args.config)
    csv_path = args.csv or str(_ROOT / "data" / f"{args.instrument}_M15.csv")
    out_root = Path(args.out)
    behaviors = [b.strip() for b in args.behaviors.split(",") if b.strip()]

    per_behavior_records = {}
    all_records = []
    for behavior in behaviors:
        recs = collect_records(behavior, csv_path, args.instrument, cfg)
        per_behavior_records[behavior] = recs
        all_records.extend(recs)
        bdir = out_root / "bnbusdt" / behavior
        _write_jsonl(bdir / "signals.jsonl", ({k: r[k] for k in _SIGNAL_KEYS} for r in recs))
        _write_jsonl(bdir / "trades.jsonl", recs)
        safe_print(f"  {behavior}: {len(recs)} signals -> {bdir}")

    report = build_report(per_behavior_records, cfg)
    (out_root / "bnbusdt_forensics.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    _write_jsonl(out_root / "bnbusdt_forensics.jsonl", all_records)

    safe_print("")
    for behavior in behaviors:
        agg = report["behaviors"][behavior]
        ed = agg["expectancy_decomposition"]
        lm = agg["loss_mechanisms"]
        top = lm[0] if lm else {"name": "n/a", "r_lost_pct": 0.0}
        safe_print(f"  [{behavior}] n={ed.get('n', 0)} E_net={ed.get('expectancy_net', 0):+.4f} "
                   f"WR={ed.get('win_rate', 0):.3f}  top_destroyer={top['name']} "
                   f"({top.get('r_lost_pct', 0)}% of R lost)")
    safe_print(f"\n  report -> {out_root / 'bnbusdt_forensics.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
