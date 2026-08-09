# -*- coding: utf-8 -*-
"""
phase_b_conditional_entropy.py — Phase B (B1) conditional-entropy map (thin CLI driver).

Answers "where, if anywhere, does next-direction become conditionally predictable on
crypto-major M15?" — paired test, entropy PRIMARY, economics CONFIRMS survivors. Candle-only
(no CRT/spine labels: that is B2). All math lives in src/research/conditional_entropy_grid.py
and the audited primitives it reuses; this only wires config -> grid -> disk.

Stages:
  1. Entropy grid (PRIMARY). For each (instrument, horizon) the partition is
     session x vol-tercile x momentum-regime. Significance is on the PARTITION (its information
     gain vs a label-permutation null), NOT the cell. Two SEPARATE BH families:
        Family A  per-instrument  (4 x 5 = 20 partition tests)
        Family B  pooled majors   (5 partition tests)
  2. Inside BH-significant partitions only, locate candidate cells (powered + directional).
  3. Economics (SEPARATE second-stage family) — sign-following net expectancy of each candidate
     cell vs random_uniform IN THE SAME CELL (forward_walk intrabar_fixed + 12bps, permutation +
     BH + |dE|>floor). A "pocket" must clear BOTH. Doctrine: a survivor is a PRE-REGISTERED OOS
     CANDIDATE, never an edge.

Deterministic JSON body (no wall-clock); run manifest written separately.

Usage: python scripts/research/phase_b_conditional_entropy.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import numpy as np                                                # noqa: E402

from research.conditional_entropy_grid import (                  # noqa: E402
    BarFeatures, bar_features, horizon_pairs, partition_stat, permutation_pvalue,
    candidate_cells, seed_for, PartitionStat,
)
from research.contracts import Signal                            # noqa: E402
from research.costs import CostModel                             # noqa: E402
from research.measurement.forward_walk import forward_walk       # noqa: E402
from research.qualification import benjamini_hochberg, permutation_p_value  # noqa: E402
from utils.console_safe import safe_print                        # noqa: E402

DEFAULT_CONFIG = "configs/research/research_config_phase_b.json"


# ── data ─────────────────────────────────────────────────────────────────────
def _load_candles(csv_path: str, instrument: str) -> list:
    from runtime.backtest_v2 import CandleLoader   # the one proven primitive (like the runner)
    candles = list(CandleLoader(csv_path, instrument).stream())
    for i, c in enumerate(candles):
        c.index = i
    return candles


def _csv_map(cfg: dict) -> dict[str, str]:
    uni = cfg["universe"]
    data_dir = Path(uni["data_dir"])
    keep = set(uni["instruments"])
    out: dict[str, str] = {}
    for p in sorted(data_dir.glob(uni["pattern"])):
        inst = p.stem.split("_")[0]
        if inst in keep:
            out[inst] = str(p)
    return out


# ── serialization ────────────────────────────────────────────────────────────
def _stat_to_dict(stat: PartitionStat, *, p_value: float, significant: bool,
                  candidates: list) -> dict:
    return {
        "n": stat.n,
        "p_up": stat.p_up,
        "h_unconditional": stat.h_unconditional,
        "h_conditional": stat.h_conditional,
        "information_gain": stat.information_gain,
        "p_value": round(p_value, 6),
        "bh_significant": significant,
        "n_cells": len(stat.cells),
        "candidate_cells": [
            {"cell": c.cell, "n": c.n, "p_up": c.p_up, "h_cell": c.h_cell} for c in candidates
        ],
    }


# ── stage 3: economic confirmation of one candidate cell ─────────────────────
def _economic_confirm(candles: list, feats: BarFeatures, horizon: int, cell: str,
                      majority_long: bool, s3: dict, seed: int) -> dict:
    labels, ups, idx = horizon_pairs(feats, horizon)
    cost = CostModel(float(s3["round_trip_bps"]))
    direction = "long" if majority_long else "short"
    mf = int(s3["max_forward"])
    hyp: list[float] = []
    ctrl: list[float] = []
    rng = np.random.default_rng(seed)
    for lab, t in zip(labels, idx.tolist()):
        if lab != cell:
            continue
        atr_t = float(feats.atrs[t])
        if atr_t <= 0.0:
            continue
        future = candles[t + 1: t + 1 + mf]
        if not future:
            continue
        base = dict(instrument="_", timestamp=candles[t].timestamp, entry_index=t,
                    entry=float(feats.closes[t]), sl_atr_mult=float(s3["sl_atr_mult"]),
                    tp_atr_mult=float(s3["tp_atr_mult"]), atr=atr_t)
        sig_h = Signal(direction=direction, **base)
        o_h = forward_walk(sig_h, future, max_forward=mf, exit_model=s3["exit_model"])
        hyp.append(cost.net_rr(o_h.rr_achieved, base["entry"], base["sl_atr_mult"] * atr_t))
        cdir = "long" if int(rng.integers(0, 2)) == 1 else "short"
        sig_c = Signal(direction=cdir, **base)
        o_c = forward_walk(sig_c, future, max_forward=mf, exit_model=s3["exit_model"])
        ctrl.append(cost.net_rr(o_c.rr_achieved, base["entry"], base["sl_atr_mult"] * atr_t))

    eh = float(np.mean(hyp)) if hyp else 0.0
    ec = float(np.mean(ctrl)) if ctrl else 0.0
    delta = eh - ec
    if delta >= 0:
        p_one = permutation_p_value(hyp, ctrl, int(s3["n_permutations"]), seed)
    else:
        p_one = permutation_p_value(ctrl, hyp, int(s3["n_permutations"]), seed)
    return {
        "cell": cell, "direction": direction, "n": len(hyp),
        "expectancy_hypothesis": round(eh, 4), "expectancy_control": round(ec, 4),
        "delta_expectancy": round(delta, 4), "p_raw": round(min(1.0, 2 * p_one), 6),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phase_b_conditional_entropy")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--out", default="results/research/phase_b")
    args = parser.parse_args(argv)

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    grid, sig, s2, s3 = cfg["grid"], cfg["significance"], cfg["stage2"], cfg["stage3"]
    horizons = list(grid["horizons"])
    csv_map = _csv_map(cfg)
    if not csv_map:
        safe_print("No CSVs matched the universe."); return 1
    instruments = sorted(csv_map)

    fkw = dict(session_windows=grid["session_windows"], atr_period=int(grid["atr_period"]),
               mom_lookback=int(grid["momentum_lookback"]), mom_eps=float(grid["momentum_eps"]))

    # Build per-instrument bar features once; cache candles for stage 3.
    candles_by: dict[str, list] = {}
    feats_by: dict[str, BarFeatures] = {}
    for inst in instruments:
        candles_by[inst] = _load_candles(csv_map[inst], inst)
        feats_by[inst] = bar_features(candles_by[inst], **fkw)
        safe_print(f"  loaded {inst}: {len(candles_by[inst])} candles")

    # ---- Stage 1: partition stats + permutation p per (instrument|pooled, horizon) ----
    nperm = int(sig["n_permutations"])
    statA: dict[str, PartitionStat] = {}
    pA: dict[str, float] = {}
    for inst in instruments:
        for h in horizons:
            labels, ups, _ = horizon_pairs(feats_by[inst], h)
            st = partition_stat(labels, ups)
            key = f"{inst}@{h}"
            statA[key] = st
            pA[key] = permutation_pvalue(labels, ups, nperm, seed_for(inst, h))

    statB: dict[str, PartitionStat] = {}
    pB: dict[str, float] = {}
    for h in horizons:
        labels_all: list[str] = []
        ups_all: list[int] = []
        for inst in instruments:
            labels, ups, _ = horizon_pairs(feats_by[inst], h)
            labels_all.extend(labels); ups_all.extend(ups.tolist())
        ups_arr = np.asarray(ups_all, dtype=np.int64)
        st = partition_stat(labels_all, ups_arr)
        key = f"POOLED@{h}"
        statB[key] = st
        pB[key] = permutation_pvalue(labels_all, ups_arr, nperm, seed_for("POOLED", h))

    # ---- BH within each family separately ----
    alpha = float(sig["alpha"])
    sigA = benjamini_hochberg(pA, alpha)
    sigB = benjamini_hochberg(pB, alpha)

    # ---- Stage 2: candidate cells inside significant partitions ----
    minn, floor = int(s2["min_cell_n"]), float(s2["direction_floor"])
    famA = {k: _stat_to_dict(statA[k], p_value=pA[k], significant=(k in sigA),
                             candidates=candidate_cells(statA[k], min_n=minn, dir_floor=floor)
                             if k in sigA else [])
            for k in sorted(statA)}
    famB = {k: _stat_to_dict(statB[k], p_value=pB[k], significant=(k in sigB),
                             candidates=candidate_cells(statB[k], min_n=minn, dir_floor=floor)
                             if k in sigB else [])
            for k in sorted(statB)}

    # ---- Stage 3: economic confirmation (per-instrument candidates only; pooled candidates
    #      flagged for follow-up). Separate multiple-testing family. ----
    s3_tests: list[dict] = []
    s3_min = int(s3["min_cell_n"])
    for key in sorted(sigA):
        inst, h = key.split("@"); h = int(h)
        for c in candidate_cells(statA[key], min_n=s3_min, dir_floor=floor):
            res = _economic_confirm(candles_by[inst], feats_by[inst], h, c.cell,
                                    majority_long=(c.p_up >= 0.5), s3=s3,
                                    seed=seed_for("econ", inst, h, c.cell))
            res.update(instrument=inst, horizon=h)
            s3_tests.append(res)

    pockets: list[dict] = []
    if s3_tests:
        s3p = {f"{t['instrument']}@{t['horizon']}|{t['cell']}|{t['direction']}": t["p_raw"]
               for t in s3_tests}
        s3_surv = benjamini_hochberg(s3p, alpha)
        eff = float(s3["effect_floor_r"])
        for t in s3_tests:
            tkey = f"{t['instrument']}@{t['horizon']}|{t['cell']}|{t['direction']}"
            t["bh_significant"] = tkey in s3_surv
            if t["bh_significant"] and abs(t["delta_expectancy"]) >= eff:
                pockets.append(t)

    report = {
        "phase": "B1",
        "grid": {k: grid[k] for k in ("horizons", "atr_period", "momentum_lookback",
                                      "momentum_eps", "session_windows")},
        "truth_standard": {"exit_model": s3["exit_model"], "round_trip_bps": s3["round_trip_bps"],
                           "significance_permutations": nperm, "alpha": alpha,
                           "stage2_min_cell_n": minn, "stage2_direction_floor": floor},
        "family_A_per_instrument": famA,
        "family_B_pooled": famB,
        "stage3_economic": sorted(s3_tests, key=lambda t: (t["instrument"], t["horizon"], t["cell"])),
        "pockets": pockets,
        "summary": {
            "n_partitions_A": len(statA), "n_significant_A": len(sigA),
            "n_partitions_B": len(statB), "n_significant_B": len(sigB),
            "n_stage3_candidates": len(s3_tests), "n_pockets": len(pockets),
            "verdict": "POCKET_FOUND" if pockets else (
                "ENTROPY_LEAD_NO_ECON" if (sigA or sigB) else "NULL_NO_CONDITIONAL_EDGE"),
            "doctrine": "a survivor is a PRE-REGISTERED OOS CANDIDATE, never an edge",
        },
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "phase_b_conditional_entropy.json").write_text(
        json.dumps(report, sort_keys=True, indent=2), encoding="utf-8")
    manifest = {"generated_at": datetime.now(timezone.utc).isoformat(),
                "git_commit": _git_commit(), "config": args.config, "instruments": instruments}
    (out_dir / "phase_b_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")

    _print(report)
    safe_print(f"\n-> {out_dir / 'phase_b_conditional_entropy.json'}")
    return 0


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def _print(report: dict) -> None:
    safe_print("\nPHASE B1 — conditional-entropy map (lower H = more predictable; "
               "IG>0 + significant = partition carries info)\n")
    hdr = f"| {'Partition':14s} | {'n':>7s} | {'p_up':>6s} | {'H|part':>7s} | {'IG':>8s} | {'perm_p':>7s} | {'BH sig':6s} |"
    sep = "|" + "-" * 16 + "|" + "-" * 9 + "|" + "-" * 8 + "|" + "-" * 9 + "|" + "-" * 10 + "|" + "-" * 9 + "|" + "-" * 8 + "|"
    for fam_name, fam in (("Family A (per-instrument)", report["family_A_per_instrument"]),
                          ("Family B (pooled)", report["family_B_pooled"])):
        safe_print(fam_name); safe_print(hdr); safe_print(sep)
        for k in sorted(fam):
            r = fam[k]
            safe_print(f"| {k:14s} | {r['n']:7d} | {r['p_up']:.4f} | {r['h_conditional']:7.4f} | "
                       f"{r['information_gain']:+8.5f} | {r['p_value']:7.4f} | "
                       f"{('YES' if r['bh_significant'] else '-'):6s} |")
        safe_print(sep)
    s = report["summary"]
    safe_print(f"\nsignificant partitions: A={s['n_significant_A']}/{s['n_partitions_A']}  "
               f"B={s['n_significant_B']}/{s['n_partitions_B']}  "
               f"stage3_candidates={s['n_stage3_candidates']}  pockets={s['n_pockets']}")
    safe_print(f"VERDICT: {s['verdict']}")
    for p in report["pockets"]:
        safe_print(f"  [POCKET] {p['instrument']}@{p['horizon']} {p['cell']} {p['direction']} "
                   f"dE={p['delta_expectancy']:+.3f} (PRE-REGISTERED OOS CANDIDATE, not an edge)")


if __name__ == "__main__":
    raise SystemExit(main())
