# -*- coding: utf-8 -*-
"""qualify_transitions.py — Stage-2 economic gate for the Program-4b transition consumer (thin CLI).

Runs the NEW `compression_breakout` hypothesis through the UNCHANGED M4 QualificationGate
(evaluate_pre_bh / benjamini_hochberg / finalize), exactly as qualify_majors does for the toy
pool — same intrabar_fixed exit, same 12bps, same beats-control + OOS + permutation + BH gates.
Promotion stays expectancy-first; this script adds NO statistics.

Additive reporting (NEVER gates): per (scope) win-rate, max losing streak, rolling-10 and a
PF>=1.3 flag are attached from research.candle_state.reporting on the NET-R trade sequence.

Per the Authority Ladder, compression_breakout earns authority only if the gate PROMOTEs it.
MEASURE-ONLY: no spine/config edits, no promotion. Deterministic body (no wall-clock).

Usage:
    python scripts/research/qualify_transitions.py
    python scripts/research/qualify_transitions.py --out results/research/candle_state
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import research.controls    # noqa: F401,E402  (register controls)
import research.hypotheses  # noqa: F401,E402  (register hypotheses, incl. compression_breakout)
from research.candle_state import reporting                         # noqa: E402
from research.config import ResearchConfig                          # noqa: E402
from research.costs import CostModel                                # noqa: E402
from research.measurement.metrics import EdgeAggregator             # noqa: E402
from research.provenance import provenance_block                    # noqa: E402
from research.qualification import (                                # noqa: E402
    BH_METHOD_VERSION, PERMUTATION_METHOD_VERSION, QUALIFICATION_VERSION,
    QualConfig, benjamini_hochberg, evaluate_pre_bh, finalize, _net_rrs,
)
from research.registry import HYPOTHESIS_REGISTRY                   # noqa: E402
from research.runner import HypothesisRunner                       # noqa: E402
from utils.console_safe import safe_print                          # noqa: E402

CANDIDATE = "compression_breakout"
GROUPS = {
    "crypto": ("configs/research/research_config_majors.json",
               ["BNBUSDT", "ETHUSDT", "BTCUSDT", "SOLUSDT"]),
    "fx": ("configs/research/research_config_fx_metals.json",
           ["EURUSD", "AUDUSD", "EURCAD", "GBPUSD", "USDJPY"]),
}


def _csv_map(cfg: ResearchConfig, instruments: list[str]) -> dict[str, str]:
    keep = set(instruments)
    out: dict[str, str] = {}
    for p in sorted(Path(cfg.data_dir).glob(cfg.pattern)):
        inst = p.stem.split("_")[0]
        if inst in keep:
            out[inst] = str(p)
    return out


def _winning_control(per_by_hyp, control_names, scope_instruments, agg, cost):
    win_name, win_rrs, win_exp = "none", [], float("-inf")
    for name in sorted(control_names):
        per = {i: per_by_hyp[name][i] for i in scope_instruments}
        rrs: list[float] = []
        for outs in per.values():
            rrs.extend(_net_rrs(outs, cost))
        rep = agg.aggregate(name, sorted(scope_instruments),
                            [o for outs in per.values() for o in outs], cost_model=cost)
        if rep.expectancy_rr > win_exp:
            win_name, win_rrs, win_exp = name, rrs, rep.expectancy_rr
    if win_exp == float("-inf"):
        win_name, win_rrs, win_exp = "none", [], 0.0
    return win_name, win_rrs, win_exp


def _run_group(cfg_path: str, instruments: list[str]) -> tuple[ResearchConfig, dict]:
    cfg = ResearchConfig.from_file(cfg_path)
    runner = HypothesisRunner(cfg)
    cost = CostModel(cfg.round_trip_bps)
    agg = EdgeAggregator()
    qcfg = QualConfig.from_research_config(cfg)

    csv_map = _csv_map(cfg, instruments)
    if not csv_map:
        raise SystemExit(f"No CSVs matched {cfg.pattern} in {cfg.data_dir} for {instruments}")
    control_names = sorted(n for n, h in HYPOTHESIS_REGISTRY.items() if h.family == "control")

    per_by_hyp: dict[str, dict] = {}
    for name in [CANDIDATE] + control_names:
        per_by_hyp[name] = runner.collect(name, csv_map)

    present = [i for i in instruments if i in csv_map]
    scopes = present + ["POOLED"]
    result: dict[str, dict] = {}
    for scope in scopes:
        scope_instruments = present if scope == "POOLED" else [scope]
        win_name, win_rrs, win_exp = _winning_control(
            per_by_hyp, control_names, scope_instruments, agg, cost)
        per = {i: per_by_hyp[CANDIDATE][i] for i in scope_instruments}
        outs = [o for o in (o for lst in per.values() for o in lst)]
        report = agg.aggregate(CANDIDATE, sorted(scope_instruments), outs, cost_model=cost)
        state = evaluate_pre_bh(report, per, win_name, win_rrs, win_exp, qcfg, cost)
        bh_survivors = benjamini_hochberg(
            {CANDIDATE: state.p_value} if state.passed_1_to_6 else {}, qcfg.significance_alpha)
        final = finalize(state, bh_survivors, qcfg)

        net = _net_rrs(outs, cost)            # reporting-only metrics on the NET-R sequence
        result[scope] = {
            "verdict": dataclasses.asdict(final),
            "winning_control": win_name,
            "reporting": {
                **reporting.report(net),
                "profit_factor": round(final.profit_factor, 6),
                "pf_ge_1_3": bool(final.profit_factor >= 1.3),   # reporting flag only
            },
        }
    return cfg, result


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="qualify_transitions",
                                 description="Stage-2 economic gate for compression_breakout")
    ap.add_argument("--out", default="results/research/candle_state")
    args = ap.parse_args(argv)

    groups: dict[str, dict] = {}
    cfg_ref = None
    for gname, (cfg_path, instruments) in GROUPS.items():
        cfg, res = _run_group(cfg_path, instruments)
        cfg_ref = cfg_ref or cfg
        groups[gname] = {"config_path": cfg_path, "config_sha256": cfg.sha256(), "scopes": res}

    body = {
        "candidate": CANDIDATE,
        "qualification_version": QUALIFICATION_VERSION,
        "permutation_method_version": PERMUTATION_METHOD_VERSION,
        "bh_method_version": BH_METHOD_VERSION,
        **provenance_block(cfg_ref.exit_model, cfg_ref.round_trip_bps),
        "groups": groups,
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "qualify_transitions.json").write_text(
        json.dumps(body, sort_keys=True, indent=2), encoding="utf-8")
    (out_dir / "qualify_transitions_manifest.json").write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                    "git_commit": _git_commit()}, sort_keys=True, indent=2), encoding="utf-8")

    safe_print("\nSTAGE-2 ECONOMIC GATE — compression_breakout (intrabar_fixed, 12bps; expectancy-first)\n")
    safe_print(f"| {'group':6s} | {'scope':10s} | {'n':>6s} | {'PF':>7s} | {'E(net)':>9s} | "
               f"{'WR':>6s} | {'maxLoseStreak':>13s} | {'verdict':12s} |")
    promoted = []
    for gname, g in groups.items():
        for scope, r in g["scopes"].items():
            v = r["verdict"]
            rep = r["reporting"]
            safe_print(f"| {gname:6s} | {scope:10s} | {v['n']:6d} | {v['profit_factor']:7.3f} | "
                       f"{v['expectancy_rr']:+9.4f} | {rep['win_rate']:6.3f} | "
                       f"{rep['max_losing_streak']:13d} | {v['verdict']:12s} |")
            if v["verdict"] == "PROMOTE":
                promoted.append(f"{gname}:{scope}")
    safe_print(f"\nPROMOTE: {promoted or 'none'}")
    safe_print(f"-> {out_dir / 'qualify_transitions.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
