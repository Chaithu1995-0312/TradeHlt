# -*- coding: utf-8 -*-
"""
path_ambiguity_census.py — Program 10 / Phase 0A (thin CLI).

Measures how often `forward_walk`'s same-bar SL-before-TP tie-break (forward_walk.py:127)
actually fires on F-025's population, and bounds what it could cost.

The entry harvest deliberately MIRRORS scripts/research/phase_d_exit_grid.py::_harvest_universe
(same hypothesis, same warmup/window, same grid, same max_forward) so the census population is
IDENTICAL to F-025's and the per-cell numbers are directly commensurable.

All math lives in research.path.ambiguity_census; this wires config -> harvest -> disk.
Deterministic JSON body (no wall-clock); manifest separate.

Usage: python scripts/research/path_ambiguity_census.py
Pre-registration: docs/research/preregistration-program-10-intrabar-path.md
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
for _p in (str(_ROOT), str(_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research.hypotheses   # noqa: F401,E402  (registers the hypothesis registry)
from research.exit_grid import Entry                                  # noqa: E402
from research.path.ambiguity_census import (                          # noqa: E402
    census_instrument, overlap_census, pool_census, stop_gate,
)
from research.registry import get_hypothesis                          # noqa: E402
from utils.console_safe import safe_print                             # noqa: E402

DEFAULT_CONFIG = "configs/research/research_config_path_crypto.json"


def _load_candles(csv: str, instrument: str) -> list:
    from runtime.backtest_v2 import CandleLoader
    candles = list(CandleLoader(csv, instrument).stream())
    for i, c in enumerate(candles):
        c.index = i
    return candles


def _harvest_universe(hyp, candles, warmup: int, window_size: int) -> list[Entry]:
    """Verbatim mirror of phase_d_exit_grid._harvest_universe — population parity is the point."""
    out: list[Entry] = []
    n = len(candles)
    for i in range(warmup, n):
        lo = max(0, i - window_size + 1)
        window = candles[lo:i + 1]
        for s in hyp.detect(window, {}, {"instrument": "_"}):
            out.append(Entry(entry_index=i, entry=s.entry, direction=s.direction, atr=s.atr))
    return out


def _pool_overlap(per_inst: dict) -> dict:
    """Sum the overlap contingency across instruments (totals, never mean-of-rates)."""
    keys = ("both", "p1_only", "same_bar_conflict_only", "neither")
    tot = {k: sum(v[k] for v in per_inst.values()) for k in keys}
    n_p1 = tot["both"] + tot["p1_only"]
    n_sbc = tot["both"] + tot["same_bar_conflict_only"]
    union = tot["both"] + tot["p1_only"] + tot["same_bar_conflict_only"]
    tot.update({
        "n_p1": n_p1,
        "n_same_bar_conflict": n_sbc,
        "jaccard": round(tot["both"] / union, 6) if union else None,
        "p1_share_of_sbc": round(tot["both"] / n_sbc, 6) if n_sbc else None,
        "sbc_share_of_p1": round(tot["both"] / n_p1, 6) if n_p1 else None,
        "note": ("DISTINCT populations (pre-registration correction 2026-07-19): neither set "
                 "contains the other. F-025's same_bar_conflict is close_only-TP-vs-intrabar-SL; "
                 "P1 is a single-bar wick collision. Never equate the counts."),
    })
    return tot


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(_ROOT), text=True).strip()
    except Exception:
        return "unknown"


def _print_summary(report: dict) -> None:
    g = report["stop_gate"]
    safe_print("\n" + "=" * 74)
    safe_print("PROGRAM 10 / 0A — SAME-BAR SL/TP AMBIGUITY CENSUS")
    safe_print("=" * 74)
    safe_print(f"  population        : {report['population']['n_entries_total']} entries "
               f"across {len(report['population']['per_instrument_n'])} instruments")
    safe_print(f"  incumbent cell    : {g['incumbent_cell']}")
    inc = report["pooled"].get(g["incumbent_cell"], {})
    safe_print(f"    ambiguity_rate  : {inc.get('ambiguity_rate')}  "
               f"(n_p1={inc.get('n_p1')} / n={inc.get('n_signals')})")
    safe_print(f"    mean_r_swing    : {inc.get('mean_r_swing')}")
    safe_print(f"    max_bias_R      : {g['incumbent_max_bias_R']}   "
               f"(UPPER BOUND — every tie-break decided wrongly)")
    safe_print(f"  worst cell        : {g['worst_cell']}  max_bias_R={g['worst_max_bias_R']}")
    safe_print(f"  threshold         : {g['threshold_max_bias_R']}")
    safe_print(f"  VERDICT           : {g['verdict']}")
    dev = report["integrity"]["sl_rr_deviations_total"]
    safe_print(f"  kernel-model check: {dev} deviations from rr_if_sl == -1.0 "
               f"({'OK' if dev == 0 else 'INVESTIGATE — r_swing arithmetic suspect'})")
    ov = report["overlap_vs_f025_same_bar_conflict"]["pooled"]
    safe_print("\n  OVERLAP vs F-025 'same_bar_conflict' (incumbent geometry, DISTINCT sets):")
    safe_print(f"    P1 total            : {ov['n_p1']}")
    safe_print(f"    same_bar_conflict   : {ov['n_same_bar_conflict']}  (F-025 reported 3334)")
    safe_print(f"    both                : {ov['both']}")
    safe_print(f"    P1 only             : {ov['p1_only']}")
    safe_print(f"    same_bar only       : {ov['same_bar_conflict_only']}")
    safe_print(f"    jaccard             : {ov['jaccard']}")
    safe_print("\n  Prior (pre-registered, CORRECTED 2026-07-19): P1's mass is unknown a priori.")
    safe_print("  F-025's 9.11%/9.25% measures a NEIGHBOURING quantity, not P1 — see the overlap")
    safe_print("  table above. max_bias_R is an UPPER BOUND: it can only CLOSE the program;")
    safe_print("  establishing actual harm requires 0B's M5-resolved split.")
    safe_print("=" * 74)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="path_ambiguity_census")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--out", default="results/research/path")
    args = parser.parse_args(argv)

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    instruments = cfg["universe"]["instruments"]
    data_dir = Path(cfg["universe"]["data_dir"])
    sl_grid = list(cfg["grid"]["sl_atr_mults"])
    tp_grid = list(cfg["grid"]["tp_atr_mults"])
    warmup = int(cfg["harness"]["warmup"])
    window = int(cfg["harness"]["window_size"])
    max_forward = int(cfg["forward_walk"]["max_forward"])
    hyp = get_hypothesis(cfg["entry_sources"]["universe_hypothesis"])

    inc_cell = cfg["census"]["incumbent_cell"]
    inc_sl, inc_tp = (float(x) for x in inc_cell.split("x"))

    per_inst: dict[str, dict] = {}
    per_inst_n: dict[str, int] = {}
    per_inst_overlap: dict[str, dict] = {}
    for inst in instruments:
        csv = data_dir / f"{inst}_M15.csv"
        if not csv.exists():
            safe_print(f"  [skip] {inst}: {csv} not found")
            continue
        candles = _load_candles(str(csv), inst)
        safe_print(f"  [{inst}] loaded {len(candles)} candles; harvesting...", flush=True)
        entries = _harvest_universe(hyp, candles, warmup, window)
        per_inst_n[inst] = len(entries)
        safe_print(f"  [{inst}] entries={len(entries)}; census over "
                   f"{len(sl_grid) * len(tp_grid)} cells...", flush=True)
        if not entries:
            continue
        per_inst[inst] = census_instrument(
            entries, candles, sl_grid=sl_grid, tp_grid=tp_grid, max_forward=max_forward)
        # Overlap vs F-025's `same_bar_conflict`, at the incumbent geometry only (the only cell
        # where F-025's own loss decomposition is computed, so the only meaningful comparison).
        per_inst_overlap[inst] = overlap_census(
            entries, candles, inc_sl, inc_tp, max_forward=max_forward)
        safe_print(f"  [{inst}] done: incumbent n_p1="
                   f"{per_inst[inst][inc_cell]['n_p1']} "
                   f"overlap both={per_inst_overlap[inst]['both']}", flush=True)

    pooled = pool_census(per_inst, sl_grid, tp_grid)
    gate = stop_gate(pooled,
                     incumbent_cell=cfg["census"]["incumbent_cell"],
                     threshold=float(cfg["census"]["stop_gate_max_bias_R"]))

    deviations = sum(c["sl_rr_deviations"]
                     for inst in per_inst.values() for c in inst.values())

    report = {
        "program": "10",
        "phase": "0A",
        "truth_standard": {
            "exit_model": cfg["forward_walk"]["exit_model"],
            "max_forward": max_forward,
            "measurement": "GROSS (pre-cost) — matches F-025's e_gross",
        },
        "grid_axes": {"sl_atr_mults": sl_grid, "tp_atr_mults": tp_grid,
                      "incumbent": cfg["census"]["incumbent_cell"]},
        "population": {
            "source": cfg["entry_sources"]["universe_hypothesis"],
            "parity_note": "mirrors phase_d_exit_grid._harvest_universe verbatim",
            "per_instrument_n": per_inst_n,
            "n_entries_total": sum(per_inst_n.values()),
        },
        "per_instrument": per_inst,
        "pooled": pooled,
        "stop_gate": gate,
        "overlap_vs_f025_same_bar_conflict": {
            "per_instrument": per_inst_overlap,
            "pooled": _pool_overlap(per_inst_overlap),
        },
        "integrity": {
            "sl_rr_deviations_total": deviations,
            "note": ("rr_if_sl must be exactly -1.0 in intrabar_fixed (trail_stop never ratchets). "
                     "Non-zero means the census's model of the kernel is wrong and r_swing is "
                     "unreliable."),
        },
        "scope": {
            "p1_only": True,
            "p2_p3": "NOT_MEASURED — OCO/straddle population (Program 9), not F-025's directional set",
            "bound_semantics": ("max_bias_R is an UPPER BOUND (every tie-break wrong), never an "
                                "estimate; it may CLOSE the program but cannot establish harm. "
                                "0B converts it to a measured split."),
        },
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ambiguity_census.json").write_text(
        json.dumps(report, sort_keys=True, indent=2), encoding="utf-8")
    (out_dir / "ambiguity_census_manifest.json").write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                    "git_commit": _git_commit(), "config": args.config},
                   sort_keys=True, indent=2), encoding="utf-8")
    _print_summary(report)
    safe_print(f"\n-> {out_dir / 'ambiguity_census.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
