# -*- coding: utf-8 -*-
"""qualify_m5_straddle.py — Stage-2 economic gate for the Program-9 straddle (thin CLI).

Runs `compression_box_straddle` — the SOLE permitted Program-9 consumer (pre-reg D7,
docs/research/preregistration-program-9.md) — through the UNCHANGED M4 QualificationGate
(evaluate_pre_bh / benjamini_hochberg / finalize), exactly as qualify_transitions did for
Program 4: same intrabar_fixed exit truth (every filled straddle's exit is delegated to
the unchanged forward_walk), same 12bps, same beats-control + OOS + permutation + BH
gates. Promotion stays expectancy-first; this script adds NO statistics.

Additive reporting (NEVER gates): per-scope win-rate / max losing streak / rolling-10 /
PF>=1.3 flag on the NET-R sequence, PLUS the straddle-specific fill telemetry
(signals emitted vs outcomes measured — D1 reject-bar and D3 TTL cancels are excluded
from n by construction and reported here only).

Per the Authority Ladder, the straddle earns authority only if the gate PROMOTEs it.
Program 9 CLOSES on this verdict (D7 — no consumer variants). MEASURE-ONLY.

Usage:
    python scripts/research/qualify_m5_straddle.py
    python scripts/research/qualify_m5_straddle.py --out results/research/m5_mtf
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
import research.hypotheses  # noqa: F401,E402  (register hypotheses, incl. compression_box_straddle)
from research.candle_state import reporting                         # noqa: E402
from research.config import ResearchConfig                          # noqa: E402
from research.costs import CostModel                                # noqa: E402
from research.measurement.metrics import EdgeAggregator             # noqa: E402
from research.provenance import provenance_block                    # noqa: E402
from research.qualification import (                                # noqa: E402
    BH_METHOD_VERSION, PERMUTATION_METHOD_VERSION, QUALIFICATION_VERSION,
    QualConfig, benjamini_hochberg, evaluate_pre_bh, finalize, _net_rrs,
)
from research.registry import HYPOTHESIS_REGISTRY, get_hypothesis   # noqa: E402
from research.runner import HypothesisRunner                        # noqa: E402
from utils.console_safe import safe_print                           # noqa: E402

CANDIDATE = "compression_box_straddle"
GROUPS = {
    "crypto": ("configs/research/research_config_m5_mtf_crypto.json",
               ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT"]),
    "fx": ("configs/research/research_config_m5_mtf_fx.json",
           ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "EURCAD", "XAUUSD"]),
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


def _fill_telemetry(cfg: ResearchConfig, csv_map: dict[str, str]) -> dict:
    """Reporting-only: straddles ARMED per instrument (detect events) vs outcomes MEASURED.
    The difference = D1 reject-bar + D3 TTL cancels (excluded from n by construction)."""
    import dataclasses as _dc
    hyp = get_hypothesis(CANDIDATE)
    runner = HypothesisRunner(cfg)
    out: dict[str, dict] = {}
    for inst in sorted(csv_map):
        candles = runner._load_candles(csv_map[inst], inst)
        armed = 0
        ctx = {"instrument": inst}
        for i in range(cfg.warmup, len(candles)):
            lo = max(0, i - cfg.window_size + 1)
            armed += len(hyp.detect(candles[lo:i + 1], {}, ctx))
        out[inst] = {"straddles_armed": armed}
    return out


def _run_group(cfg_path: str, instruments: list[str]) -> tuple[ResearchConfig, dict, dict]:
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

    fills = _fill_telemetry(cfg, csv_map)
    for inst in fills:
        measured = len(per_by_hyp[CANDIDATE].get(inst, []))
        fills[inst]["outcomes_measured"] = measured
        armed = fills[inst]["straddles_armed"]
        fills[inst]["cancelled"] = armed - measured
        fills[inst]["fill_rate"] = round(measured / armed, 6) if armed else 0.0

    present = [i for i in instruments if i in csv_map]
    scopes = present + ["POOLED"]
    result: dict[str, dict] = {}
    for scope in scopes:
        scope_instruments = present if scope == "POOLED" else [scope]
        win_name, win_rrs, win_exp = _winning_control(
            per_by_hyp, control_names, scope_instruments, agg, cost)
        per = {i: per_by_hyp[CANDIDATE][i] for i in scope_instruments}
        outs = [o for lst in per.values() for o in lst]
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
    return cfg, result, fills


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="qualify_m5_straddle",
                                 description="Stage-2 economic gate for compression_box_straddle (Program 9)")
    ap.add_argument("--out", default="results/research/m5_mtf")
    args = ap.parse_args(argv)

    groups: dict[str, dict] = {}
    cfg_ref = None
    for gname, (cfg_path, instruments) in GROUPS.items():
        cfg, res, fills = _run_group(cfg_path, instruments)
        cfg_ref = cfg_ref or cfg
        groups[gname] = {"config_path": cfg_path, "config_sha256": cfg.sha256(),
                         "fill_telemetry": fills, "scopes": res}

    body = {
        "candidate": CANDIDATE,
        "preregistration": "docs/research/preregistration-program-9.md",
        "qualification_version": QUALIFICATION_VERSION,
        "permutation_method_version": PERMUTATION_METHOD_VERSION,
        "bh_method_version": BH_METHOD_VERSION,
        **provenance_block(cfg_ref.exit_model, cfg_ref.round_trip_bps),
        "groups": groups,
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "qualify_m5_straddle.json").write_text(
        json.dumps(body, sort_keys=True, indent=2), encoding="utf-8")
    (out_dir / "qualify_m5_straddle_manifest.json").write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                    "git_commit": _git_commit()}, sort_keys=True, indent=2), encoding="utf-8")

    safe_print("\nSTAGE-2 ECONOMIC GATE — compression_box_straddle (OCO, intrabar_fixed, 12bps; expectancy-first)\n")
    safe_print(f"| {'group':6s} | {'scope':10s} | {'n':>6s} | {'PF':>7s} | {'E(net)':>9s} | "
               f"{'WR':>6s} | {'fill%':>6s} | {'verdict':12s} |")
    promoted = []
    for gname, g in groups.items():
        pooled_armed = sum(f["straddles_armed"] for f in g["fill_telemetry"].values())
        pooled_meas = sum(f["outcomes_measured"] for f in g["fill_telemetry"].values())
        for scope, r in g["scopes"].items():
            v = r["verdict"]
            rep = r["reporting"]
            if scope == "POOLED":
                fr = pooled_meas / pooled_armed if pooled_armed else 0.0
            else:
                fr = g["fill_telemetry"].get(scope, {}).get("fill_rate", 0.0)
            safe_print(f"| {gname:6s} | {scope:10s} | {v['n']:6d} | {v['profit_factor']:7.3f} | "
                       f"{v['expectancy_rr']:+9.4f} | {rep['win_rate']:6.3f} | "
                       f"{fr:6.3f} | {v['verdict']:12s} |")
            if v["verdict"] == "PROMOTE":
                promoted.append(f"{gname}:{scope}")
    safe_print(f"\nPROMOTE: {promoted or 'none'}")
    safe_print("Program 9 closes on this verdict (pre-reg D7 — no consumer variants).")
    safe_print(f"-> {out_dir / 'qualify_m5_straddle.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
