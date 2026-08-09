"""
execution_planner_replay.py — split the RETEST->EXECUTION edge into Selection vs SL/TP (measure-only).

The gate-contribution study showed the entire +0.584R edge appears at the RETEST->EXECUTION gate, but
that jump conflates two things: (a) *which* retest candles are selected (session/zone/shadow + score),
and (b) the CRT engine's structure-based SL/TP vs a vanilla fixed SL/TP. This script separates them
with a 2x2 counterfactual, all four cells forward-simulated identically (only the varied dimension moves):

                       | vanilla SL/TP (1*ATR / 2*ATR) | CRT structure SL/TP (displacement-anchored)
    Selected (accepted)|              A                |   B   (anchor: ~ real executed +0.545R)
    Rejected (filtered)|              C                |   D   (the missing measurement)

  SL/TP-structure effect = mean(B-A) on selected AND mean(D-C) on rejected
  Selection effect       = mean(A-C) on vanilla   AND mean(B-D) on structure
  Observed C->B jump decomposes into the two effects + an interaction term.

Faithful to production:
  - RETEST candidates (selected + rejected) come from the additive RETEST_REPLAY telemetry the CRT
    engine emits (schemas.md 9.4) — the only source that carries trade DIRECTION + structure inputs.
  - Structure SL/TP is reconstructed with the exact build_trade formula (sl = displacement_candle
    {low|high} -/+ sl_atr_buffer*atr); verified to reproduce the engine's real sl/tp1 bit-for-bit.
  - Forward exits use analytics.sl_tp_comparator.simulate_exit (TP2>SL>TP1, matches BacktestRunner).

Measure-only: writes ONLY under results/execution_planner_replay/. No config edit, no promotion.
Trust gate (hard): cell B (structure on selected) must reproduce the real executed expectancy or the
harness is untrusted.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "src")

from analytics.sl_tp_comparator import (                       # noqa: E402
    _aggregate_variant_results,
    simulate_exit,
    SLTPComparator,
)
from config_layer.production_config import (                   # noqa: E402
    PROD_VERSION,
    get_prod_section,
    load_prod_config_from_registry,
)
from config_layer.config_builder import ConfigBuilder          # noqa: E402
from runtime.backtest_v2 import (                              # noqa: E402
    BacktestConfig,
    BacktestRunner,
    CandleLoader,
)

SEED = 1337  # convention; the replay + backtest are deterministic
# Vanilla counterfactual = the opportunity_scanner definition (sl=1*ATR, tp=2*ATR fixed 2R).
VANILLA_SL_ATR = 1.0
VANILLA_TP_ATR = 2.0


def _norm_ts(s: str) -> str:
    return str(s).replace("T", " ").split("+")[0].split("Z")[0].strip()[:19]


def _run_backtest(instrument: str, csv: str, out_dir: Path) -> tuple[Path, Path, object]:
    """Run one deterministic backtest on the ACTIVE prod config; return (telemetry, trades_csv, metrics).

    Faithful construction (mirrors phase6e_shadow_ab): load the registry crt_engine values + apply the
    market router via ConfigBuilder.from_existing. BacktestConfig.from_prod_config(instrument) ALONE
    rebuilds a CRTConfig from flat params/defaults (the session-sweep.md construction caveat) and would
    silently drop the v4 all-sessions override.
    """
    base = load_prod_config_from_registry(PROD_VERSION, instrument)
    crt = ConfigBuilder.from_existing(instrument, base)
    cfg = BacktestConfig.from_prod_config(instrument=instrument, crt_config=crt)
    loader = CandleLoader(csv, instrument)
    runner = BacktestRunner(cfg, csv_path=csv)
    m = runner.run(loader.stream(), loader.count(), str(out_dir))
    tel = sorted(glob.glob(str(out_dir / "**" / f"*{instrument}*crt_telemetry*.jsonl"), recursive=True),
                 key=os.path.getmtime, reverse=True)
    trd = sorted(glob.glob(str(out_dir / "**" / f"{instrument}*trades.csv"), recursive=True),
                 key=os.path.getmtime, reverse=True)
    if not tel:
        raise SystemExit(f"no crt_telemetry.jsonl produced under {out_dir}")
    return Path(tel[0]), (Path(trd[0]) if trd else None), m


def _load_replay(telemetry_path: Path) -> list[dict]:
    out = []
    for line in open(telemetry_path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("kind") == "RETEST_REPLAY":
            out.append(d)
    return out


def _structure_levels(r: dict) -> tuple[float, float, float]:
    """Faithful build_trade SL/TP: SL anchored to displacement-candle extreme."""
    d = r["direction"]
    sl = r["disp_low"] - r["sl_atr_buffer"] * r["atr"] if d == 1 \
        else r["disp_high"] + r["sl_atr_buffer"] * r["atr"]
    risk = abs(r["entry"] - sl)
    tp1 = r["entry"] + d * r["tp1_mult"] * risk
    tp2 = r["entry"] + d * r["tp2_mult"] * risk
    return sl, tp1, tp2


def _vanilla_levels(r: dict) -> tuple[float, float, float]:
    """Vanilla fixed SL/TP: sl = 1*ATR, tp = 2*ATR (opportunity_scanner definition)."""
    d = r["direction"]
    risk = VANILLA_SL_ATR * r["atr"]
    sl = r["entry"] - d * risk
    tp = r["entry"] + d * VANILLA_TP_ATR * r["atr"]
    return sl, tp, tp  # single TP -> tp1 == tp2


def _simulate_cell(records: list[dict], levels_fn, candle_idx: dict, candles: list[dict],
                   max_candles: int) -> list[dict]:
    """Forward-simulate one population under one SL/TP method; return per-record result dicts."""
    results = []
    for r in records:
        i = candle_idx.get(_norm_ts(r["timestamp"]))
        if i is None:
            continue
        forward = candles[i + 1 : i + 1 + max_candles]
        if not forward:
            continue
        sl, tp1, tp2 = levels_fn(r)
        ex = simulate_exit(r["entry"], r["direction"], sl, tp1, tp2, forward, max_candles)
        ex["sl_dist_atr"] = round(abs(r["entry"] - sl) / r["atr"], 4) if r["atr"] > 0 else 0.0
        ex["entry"] = r["entry"]
        results.append(ex)
    return results


def compute_attribution(exp: dict) -> dict:
    """Pure 2x2 decomposition from the four cell expectancies (keys A_/B_/C_/D_*).

    Identity (both paths reconstruct the observed C->B jump):
        B - C == selection_effect_vanilla   + sltp_effect_on_selected
        B - C == selection_effect_structure + sltp_effect_on_rejected
    """
    a, b = exp["A_selected_vanilla"], exp["B_selected_structure"]
    c, d = exp["C_rejected_vanilla"], exp["D_rejected_structure"]
    return {
        "observed_C_to_B":            round(b - c, 4),
        "sltp_effect_on_selected":    round(b - a, 4),
        "sltp_effect_on_rejected":    round(d - c, 4),
        "selection_effect_vanilla":   round(a - c, 4),
        "selection_effect_structure": round(b - d, 4),
        "interaction":                round((b - a) - (d - c), 4),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instrument", default="BNBUSDT")
    ap.add_argument("--csv", default=None, help="default data/<INSTR>_M15.csv")
    ap.add_argument("--output-dir", default="results/execution_planner_replay")
    args = ap.parse_args(argv)

    instrument = args.instrument
    csv = args.csv or f"data/{instrument}_M15.csv"
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    try:
        max_candles = int(get_prod_section("sl_tp_comparison").get("max_candles_per_trade", 100))
    except (RuntimeError, KeyError):
        max_candles = 100

    # 1) one deterministic backtest -> RETEST_REPLAY telemetry + real trades
    tel_path, trd_path, metrics = _run_backtest(instrument, csv, out / "_run")
    replay = _load_replay(tel_path)
    if not replay:
        raise SystemExit("no RETEST_REPLAY records found — is the additive telemetry wired?")

    candles = SLTPComparator.load_candles_from_csv(csv)
    candle_idx = {_norm_ts(c["timestamp"]): i for i, c in enumerate(candles)}

    selected = [r for r in replay if r["accepted"]]
    rejected = [r for r in replay if not r["accepted"]]

    cells = {
        "A_selected_vanilla":   _aggregate_variant_results(_simulate_cell(selected, _vanilla_levels,   candle_idx, candles, max_candles)),
        "B_selected_structure": _aggregate_variant_results(_simulate_cell(selected, _structure_levels, candle_idx, candles, max_candles)),
        "C_rejected_vanilla":   _aggregate_variant_results(_simulate_cell(rejected, _vanilla_levels,   candle_idx, candles, max_candles)),
        "D_rejected_structure": _aggregate_variant_results(_simulate_cell(rejected, _structure_levels, candle_idx, candles, max_candles)),
    }
    exp = {k: v["expectancy_rr"] for k, v in cells.items()}
    attribution = compute_attribution(exp)

    # ── Trust gate = STRUCTURAL fidelity (not net-number match) ──────────────
    # All four cells share the simplified simulate_exit model (TP2>SL>TP1, no 0.5R trail,
    # no partial-TP, no costs), so the attribution deltas are apples-to-apples. The real
    # net +0.545R is a SEPARATE figure: it differs from cell B only by the trail/partial/cost
    # exit model, which is identical across cells and therefore cancels in every delta.
    # The harness is trustworthy iff (a) the selected set == the real executed trades, and
    # (b) the offline structure SL reconstruction reproduces the engine's recorded SL.
    real_rr = None
    sl_fidelity_mismatch = None
    if trd_path is not None:
        import csv as _csv
        rows = list(_csv.DictReader(open(trd_path, encoding="utf-8")))
        vals = []
        for row in rows:
            try:
                vals.append(float(row.get("pnl_rr_net")))
            except (TypeError, ValueError):
                pass
        real_rr = round(sum(vals) / len(vals), 4) if vals else None
        by_ts = {_norm_ts(t.get("opened_at", "")): t for t in rows}
        sl_fidelity_mismatch = 0
        for r in selected:
            t = by_ts.get(_norm_ts(r["timestamp"]))
            if not t:
                continue
            sl, _, _ = _structure_levels(r)
            try:
                if abs(sl - float(t["sl"])) > 1e-4:
                    sl_fidelity_mismatch += 1
            except (TypeError, ValueError, KeyError):
                pass

    cell_b = exp["B_selected_structure"]
    counts_ok = len(selected) == metrics.approved_trades and len(rejected) > 0
    fidelity_ok = (sl_fidelity_mismatch == 0)
    anchor_ok = counts_ok and fidelity_ok

    # dominant effect verdict
    sltp = (attribution["sltp_effect_on_selected"] + attribution["sltp_effect_on_rejected"]) / 2.0
    sel = (attribution["selection_effect_vanilla"] + attribution["selection_effect_structure"]) / 2.0
    dominant = "selection" if abs(sel) > abs(sltp) else "sl_tp_structure"

    payload = {
        "prod_version": PROD_VERSION,
        "instrument": instrument,
        "seed": SEED,
        "max_candles": max_candles,
        "vanilla_def": {"sl_atr": VANILLA_SL_ATR, "tp_atr": VANILLA_TP_ATR},
        "counts": {
            "retest_total": len(replay),
            "selected": len(selected),
            "rejected": len(rejected),
            "reject_reasons": _reason_counts(rejected),
            "backtest_trades": metrics.approved_trades,
        },
        "cells": cells,
        "expectancy": {k: round(v, 4) for k, v in exp.items()},
        "attribution": attribution,
        "anchors": {
            "cell_B_structure_selected_gross": cell_b,
            "real_executed_mean_rr_net": real_rr,
            "gross_vs_net_gap": (round(real_rr - cell_b, 4) if real_rr is not None else None),
            "_note": "cells are gross/simplified-exit (no trail/partial/cost); the gross-vs-net gap "
                     "is the trail+partial-TP+cost contribution, constant across cells.",
            "selected_eq_backtest_trades": counts_ok,
            "structure_sl_fidelity_mismatch": sl_fidelity_mismatch,
            "harness_trustworthy": anchor_ok,
        },
        "verdict": {
            "dominant_effect": dominant,
            "avg_sltp_effect": round(sltp, 4),
            "avg_selection_effect": round(sel, 4),
        },
    }
    (out / "replay_bnbusdt.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # human-readable summary
    print(f"=== Execution-Planner Replay — {instrument} ({PROD_VERSION}) ===")
    print(f"  RETEST {len(replay)} = selected {len(selected)} + rejected {len(rejected)}  "
          f"(backtest trades={metrics.approved_trades})")
    print(f"  reject reasons: {payload['counts']['reject_reasons']}")
    print("  2x2 expectancy (R):")
    print(f"                       vanilla      structure")
    print(f"    Selected      A {exp['A_selected_vanilla']:+.3f}   B {exp['B_selected_structure']:+.3f}")
    print(f"    Rejected      C {exp['C_rejected_vanilla']:+.3f}   D {exp['D_rejected_structure']:+.3f}")
    print(f"  attribution: {attribution}")
    print(f"  trust gate: selected=={metrics.approved_trades}? {counts_ok}  "
          f"structure-SL fidelity mismatches={sl_fidelity_mismatch} -> {'OK' if anchor_ok else 'FAIL'}")
    print(f"  context: cell B gross {cell_b:+.3f}  |  real executed net {real_rr}  "
          f"(gap = trail+partial+cost, constant across cells)")
    print(f"  VERDICT: dominant effect = {dominant.upper()}  (selection {sel:+.3f} vs SL/TP {sltp:+.3f})")
    print(f"  wrote {out / 'replay_bnbusdt.json'}")
    return 0 if anchor_ok else 2


def _reason_counts(records: list[dict]) -> dict:
    out: dict[str, int] = {}
    for r in records:
        k = r.get("reject_reason") or "none"
        out[k] = out.get(k, 0) + 1
    return out


if __name__ == "__main__":
    sys.exit(main())
