# -*- coding: utf-8 -*-
"""qualify_shape_xauusd.py — Program 11 (B1): the semantic Market-Shape hypothesis through the
unchanged M4 gate on the XAUUSD frozen candidate. Clean-substrate re-derivation of F-023/F-041B.

FROZEN by docs/research/preregistration-program-11-shape-context-edge-xauusd.md (protocol_hash
e5b8232d). Reuses the VERBATIM M4 math (research.qualification) + HypothesisRunner + forward_walk
(intrabar_fixed). Controls (always_long + 2 randoms) operationalize the pre-registered
unconditional-entry twin + random baselines. Runs 12bps and a 0bps sensitivity twin so a null's
direction is cost-robust (F-035). Research-only, NON-PROMOTABLE (§6.5).

Usage: python scripts/research/qualify_shape_xauusd.py [--permutations 2000]
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

import research.controls    # noqa: F401,E402  (register controls)
import research.hypotheses  # noqa: F401,E402  (register market_shape)
from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path  # noqa: E402
from research.config import ResearchConfig                                # noqa: E402
from research.costs import CostModel                                      # noqa: E402
from research.measurement.metrics import EdgeAggregator                   # noqa: E402
from research.qualification import (                                      # noqa: E402
    QualConfig, benjamini_hochberg, evaluate_pre_bh, finalize, _net_rrs)
from research.registry import HYPOTHESIS_REGISTRY                         # noqa: E402
from research.runner import HypothesisRunner                             # noqa: E402

INSTRUMENT = "XAUUSD"
CANDIDATE = "market_shape"
CONFIG = "configs/research/research_config_shape_xauusd.json"


def _csv_map() -> dict[str, str]:
    return {INSTRUMENT: guard_xauusd_csv_path("data/XAUUSD_M15.csv", INSTRUMENT)}


def _winning_control(per, controls, agg, cost):
    win = ("none", [], float("-inf"))
    for name in sorted(controls):
        outs = per[name].get(INSTRUMENT, [])
        rep = agg.aggregate(name, [INSTRUMENT], outs, cost_model=cost)
        if rep.expectancy_rr > win[2]:
            win = (name, _net_rrs(outs, cost), rep.expectancy_rr)
    return win if win[2] != float("-inf") else ("none", [], 0.0)


def _run(bps: float, perms: int | None) -> dict:
    d = json.loads(Path(CONFIG).read_text(encoding="utf-8"))
    d["costs"]["round_trip_bps"] = float(bps)
    cfg = ResearchConfig.from_dict(d)
    runner = HypothesisRunner(cfg)
    cost = CostModel(cfg.round_trip_bps)
    agg = EdgeAggregator()
    qcfg = QualConfig.from_research_config(cfg)
    if perms is not None:
        qcfg = dataclasses.replace(qcfg, n_permutations=perms)

    controls = sorted(n for n, h in HYPOTHESIS_REGISTRY.items() if h.family == "control")
    csv_map = _csv_map()
    per = {name: runner.collect(name, csv_map) for name in [CANDIDATE] + controls}
    win_name, win_rrs, win_exp = _winning_control(per, controls, agg, cost)

    outs = per[CANDIDATE].get(INSTRUMENT, [])
    report = agg.aggregate(CANDIDATE, [INSTRUMENT], outs, cost_model=cost)
    st = evaluate_pre_bh(report, {INSTRUMENT: outs}, win_name, win_rrs, win_exp, qcfg, cost)
    bh = benjamini_hochberg({CANDIDATE: st.p_value} if st.passed_1_to_6 else {},
                            qcfg.significance_alpha)
    final = dataclasses.asdict(finalize(st, bh, qcfg))
    return {"round_trip_bps": cfg.round_trip_bps, "n_permutations": qcfg.n_permutations,
            "winning_control": win_name, "winning_control_exp": round(win_exp, 6),
            "controls": controls, "candidate": final}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="qualify_shape_xauusd")
    ap.add_argument("--permutations", type=int, default=None)
    ap.add_argument("--out", default="results/research/qualify_shape_xauusd.json")
    args = ap.parse_args(argv)

    doc = {"program": "P11_shape_context_edge_xauusd", "instrument": INSTRUMENT,
           "non_promotable": True, "authority": "RESEARCH_ONLY",
           "runs": {"bps_12": _run(12.0, args.permutations),
                    "bps_0_twin": _run(0.0, args.permutations)}}

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, sort_keys=True, indent=2), encoding="utf-8")

    print(f"\nQUALIFY-SHAPE-XAUUSD (Program 11, NON-PROMOTABLE) — intrabar_fixed")
    print(f"| {'run':10s} | {'n':>7s} | {'PF':>8s} | {'E(net)':>9s} | {'p':>8s} | "
          f"{'win_ctrl':16s} | {'verdict':10s} |")
    for label, r in doc["runs"].items():
        c = r["candidate"]
        print(f"| {label:10s} | {c['n']:7d} | {c['profit_factor']:8.3f} | {c['expectancy_rr']:+9.4f} "
              f"| {c['p_value']:8.4f} | {r['winning_control']:16s} | {c['verdict']:10s} |")
        if c["reject_reasons"]:
            print(f"    reject_reasons: {c['reject_reasons']}")
    print(f"\n-> {out}   (research-only; updates F-023/F-041B on clean XAUUSD, no edge claim)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
