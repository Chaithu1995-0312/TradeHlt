# -*- coding: utf-8 -*-
"""Parameterized CRT guard ablation (identical protocol to 6m XAUUSD baseline).

Usage:
  python scripts/analysis/crt_guard_ablation_run.py \\
    --csv data/XAUUSD_W....csv --instrument XAUUSD \\
    --label xau_trend_3m --out-dir results/runtime_benchmarks/guard_ablation_xau_trend_3m

Production code/JSON never modified. In-memory CRTConfig.replace only.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

for name in (
    "CRT_ENGINE_V2",
    "CRT.StateMachine",
    "CRT.Backtest",
    "CRT.Execution",
    "FeaturePipeline",
):
    logging.getLogger(name).setLevel(logging.ERROR)

from config_layer.production_config import (  # noqa: E402
    get_active_version,
    load_prod_config_from_registry,
)
from runtime.backtest_v2 import BacktestConfig, BacktestRunner, CandleLoader  # noqa: E402

# Identical arm list to crt_guard_ablation_6m.py (do not diverge)
ABLATIONS: list[tuple[str, str, dict]] = [
    ("baseline", "All guards at production values", {}),
    (
        "ablate_disp_move",
        "SWEEP→DISPLACEMENT: disable P_DISP_MOVE (atr_min_displacement→0)",
        {"atr_min_displacement": 0.0},
    ),
    (
        "ablate_disp_body",
        "SWEEP→DISPLACEMENT: disable P_DISP_BODY (body_ratio_min→0)",
        {"body_ratio_min": 0.0},
    ),
    (
        "ablate_disp_wick",
        "SWEEP→DISPLACEMENT: disable P_DISP_WICK (atr_multiplier_min→0)",
        {"atr_multiplier_min": 0.0},
    ),
    (
        "ablate_disp_age",
        "SWEEP→DISPLACEMENT: disable P_DISP_AGE (max_sweep_age_candles→10**6)",
        {"max_sweep_age_candles": 1_000_000},
    ),
    (
        "ablate_exp_atr_dist",
        "DISPLACEMENT→EXPANSION: disable P_EXP_ATR_DIST (expansion_atr_min_distance→0)",
        {"expansion_atr_min_distance": 0.0},
    ),
    (
        "ablate_ret_min_depth",
        "EXPANSION→RETEST: disable P_RET_MIN_DEPTH (retest_min_depth_atr_fraction→0)",
        {"retest_min_depth_atr_fraction": 0.0},
    ),
    (
        "ablate_ret_ceiling",
        "EXPANSION→RETEST: disable P_RET_CEILING (depth ceilings → huge)",
        {"retest_depth_max": 100.0, "retest_atr_depth_fraction": 100.0},
    ),
    (
        "ablate_ret_disp_strength",
        "EXPANSION→RETEST: disable P_RET_DISP_STRENGTH (max_displacement_strength→100)",
        {"max_displacement_strength": 100.0},
    ),
]


def count_structure(events_path: Path) -> dict:
    n: Counter = Counter()
    filter_reasons: Counter = Counter()
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        ev = e.get("event") or e.get("kind")
        if ev == "STATE_TRANSITION":
            to, fr = e.get("state_to"), e.get("state_from")
            if fr == "RANGE" and to == "SWEEP":
                n["n_sweep"] += 1
            if fr == "SWEEP" and to == "DISPLACEMENT":
                n["n_displacement"] += 1
            if to == "EXPANSION":
                n["n_expansion"] += 1
            if to == "RETEST":
                n["n_retest"] += 1
            if to == "EXECUTION":
                n["n_execution"] += 1
            if fr == "SHADOW_PENDING" and to == "EXPANSION":
                n["n_shadow_expansion"] += 1
            if fr == "DISPLACEMENT" and to == "EXPANSION":
                n["n_disp_to_expansion"] += 1
        if ev == "FILTER_REJECTED":
            n["n_filter_rejected"] += 1
            filter_reasons[str(e.get("reason"))] += 1
        if ev == "TRADE_OPENED":
            n["n_trade_opened"] += 1
    out = dict(n)
    out["filter_reasons"] = dict(filter_reasons)
    return out


def deltas(baseline: dict, arm: dict) -> dict:
    def d(key, src_b, src_a):
        vb, va = src_b.get(key), src_a.get(key)
        if vb is None or va is None:
            return None
        try:
            return va - vb
        except TypeError:
            return None

    b_t, a_t = baseline["throughput"], arm["throughput"]
    b_e, a_e = baseline["expectancy"], arm["expectancy"]
    b_s, a_s = baseline["structure"], arm["structure"]
    return {
        "delta_n_retest": d("n_retest", b_t, a_t),
        "delta_n_execution": d("n_execution", b_t, a_t),
        "delta_approved_trades": d("approved_trades", b_t, a_t),
        "delta_n_displacement": d("n_displacement", b_s, a_s),
        "delta_n_expansion": d("n_expansion", b_s, a_s),
        "delta_n_sweep": d("n_sweep", b_s, a_s),
        "delta_avg_rr_net": d("avg_rr_net", b_e, a_e),
        "delta_total_pnl_rr_net": d("total_pnl_rr_net", b_e, a_e),
        "delta_win_rate": d("win_rate", b_e, a_e),
        "delta_filter_rejected": d("n_filter_rejected", b_t, a_t),
    }


def run_arm(
    *,
    arm_id: str,
    description: str,
    overrides: dict,
    csv: Path,
    instrument: str,
    out_dir: Path,
) -> dict:
    os.environ["BACKTEST_ENGINE_GATE"] = "0"
    base = load_prod_config_from_registry("v2_multi_2026_04", instrument)
    crt_cfg = replace(base, **overrides) if overrides else base
    bt_cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
    bt_cfg.instrument = instrument

    arm_out = out_dir / arm_id
    arm_out.mkdir(parents=True, exist_ok=True)

    loader = CandleLoader(str(csv), instrument)
    candles = list(loader.stream())
    runner = BacktestRunner(
        bt_cfg,
        csv_path=str(csv),
        overrides={"ablation": arm_id, **{k: str(v) for k, v in overrides.items()}},
    )
    t0 = time.perf_counter()
    runner.run(iter(candles), len(candles), str(arm_out))
    elapsed = time.perf_counter() - t0

    runs = sorted(arm_out.glob("run_*"), key=lambda p: p.stat().st_mtime)
    if not runs:
        raise RuntimeError(f"no run dir for {arm_id}")
    run_dir = runs[-1]
    summary = json.loads(
        (run_dir / f"{instrument}_summary.json").read_text(encoding="utf-8")
    )
    structure = count_structure(run_dir / f"{instrument}_events.jsonl")

    rec = {
        "arm_id": arm_id,
        "description": description,
        "config_overrides": overrides,
        "elapsed_s": round(elapsed, 2),
        "run_dir": run_dir.relative_to(ROOT).as_posix(),
        "structure": structure,
        "throughput": {
            "approved_trades": summary.get("approved_trades"),
            "total_setups": summary.get("total_setups"),
            "n_trade_opened": structure.get("n_trade_opened", 0),
            "n_retest": structure.get("n_retest", 0),
            "n_execution": structure.get("n_execution", 0),
            "n_filter_rejected": structure.get("n_filter_rejected", 0),
        },
        "expectancy": {
            "avg_rr_net": summary.get("avg_rr_net"),
            "total_pnl_rr_net": summary.get("total_pnl_rr_net"),
            "win_rate": summary.get("win_rate"),
            "max_drawdown_pct": summary.get("max_drawdown_pct"),
            "tp1_hits": summary.get("tp1_hits"),
            "tp2_hits": summary.get("tp2_hits"),
            "authority": "DESCRIPTIVE_ONLY_NOT_PROMOTION",
        },
        "summary_snapshot": {
            "total_candles": summary.get("total_candles"),
            "state_distribution": summary.get("state_distribution"),
        },
    }
    print(
        f"[{arm_id}] {elapsed:.1f}s retest={structure.get('n_retest')} "
        f"trades={summary.get('approved_trades')} avgRR={summary.get('avg_rr_net')} "
        f"disp={structure.get('n_displacement')} exp={structure.get('n_expansion')}",
        flush=True,
    )
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, required=True)
    ap.add_argument("--instrument", required=True)
    ap.add_argument("--label", required=True, help="dataset label for reports")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument(
        "--regime-note",
        default="",
        help="human note: trend/range/instrument characterization",
    )
    args = ap.parse_args()

    csv = args.csv if args.csv.is_absolute() else ROOT / args.csv
    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    if not csv.is_file():
        raise SystemExit(f"missing csv: {csv}")
    out_dir.mkdir(parents=True, exist_ok=True)
    os.environ["BACKTEST_ENGINE_GATE"] = "0"

    print(
        f"label={args.label} csv={csv.name} instrument={args.instrument} "
        f"active={get_active_version()} gate=0",
        flush=True,
    )

    results = []
    t_all = time.perf_counter()
    for arm_id, desc, ov in ABLATIONS:
        results.append(
            run_arm(
                arm_id=arm_id,
                description=desc,
                overrides=ov,
                csv=csv,
                instrument=args.instrument,
                out_dir=out_dir,
            )
        )
    total_elapsed = time.perf_counter() - t_all

    baseline = next(r for r in results if r["arm_id"] == "baseline")
    for r in results:
        r["delta_vs_baseline"] = (
            None if r["arm_id"] == "baseline" else deltas(baseline, r)
        )

    ablations = [r for r in results if r["arm_id"] != "baseline"]
    by_retest = sorted(
        ablations,
        key=lambda r: (r["delta_vs_baseline"]["delta_n_retest"] or 0),
        reverse=True,
    )
    by_trades = sorted(
        ablations,
        key=lambda r: (r["delta_vs_baseline"]["delta_approved_trades"] or 0),
        reverse=True,
    )
    by_pnl = sorted(
        ablations,
        key=lambda r: (r["delta_vs_baseline"]["delta_total_pnl_rr_net"] or 0),
        reverse=True,
    )
    by_disp = sorted(
        ablations,
        key=lambda r: (r["delta_vs_baseline"]["delta_n_displacement"] or 0),
        reverse=True,
    )

    report = {
        "scope": (
            "Identical single-predicate ablation protocol as XAUUSD 6m baseline. "
            "Production unchanged."
        ),
        "authority": "DESCRIPTIVE_ONLY_NOT_PROMOTION",
        "label": args.label,
        "regime_note": args.regime_note,
        "window": {
            "csv": csv.relative_to(ROOT).as_posix()
            if csv.is_relative_to(ROOT)
            else str(csv),
            "instrument": args.instrument,
            "gate": "BACKTEST_ENGINE_GATE=0",
            "active_version": get_active_version(),
        },
        "protocol_id": "CRT_GUARD_ABLATION_V1",
        "arms_spec": [
            {"arm_id": a, "description": d, "overrides": o} for a, d, o in ABLATIONS
        ],
        "total_elapsed_s": round(total_elapsed, 2),
        "baseline": baseline,
        "arms": results,
        "ranking": {
            "by_delta_n_displacement": [
                {
                    "arm_id": r["arm_id"],
                    "delta_n_displacement": r["delta_vs_baseline"][
                        "delta_n_displacement"
                    ],
                }
                for r in by_disp
            ],
            "by_delta_retest": [
                {
                    "arm_id": r["arm_id"],
                    "delta_n_retest": r["delta_vs_baseline"]["delta_n_retest"],
                }
                for r in by_retest
            ],
            "by_delta_trades": [
                {
                    "arm_id": r["arm_id"],
                    "delta_approved_trades": r["delta_vs_baseline"][
                        "delta_approved_trades"
                    ],
                }
                for r in by_trades
            ],
            "by_delta_total_pnl_rr": [
                {
                    "arm_id": r["arm_id"],
                    "delta_total_pnl_rr_net": r["delta_vs_baseline"][
                        "delta_total_pnl_rr_net"
                    ],
                }
                for r in by_pnl
            ],
        },
    }

    out_json = out_dir / f"guard_ablation_{args.label}_report.json"
    out_md = out_dir / f"guard_ablation_{args.label}_report.md"
    out_json.write_text(
        json.dumps(report, indent=2, ensure_ascii=True, default=str) + "\n",
        encoding="utf-8",
    )

    lines = [
        f"# Guard Ablation — `{args.label}`",
        "",
        f"**Regime:** {args.regime_note or '(see label)'}",
        f"**CSV:** `{csv.name}` · **Instrument:** `{args.instrument}`",
        f"**Protocol:** CRT_GUARD_ABLATION_V1 · gate OFF · {get_active_version()}",
        f"**Wall:** {total_elapsed:.1f}s · **Authority:** descriptive only",
        "",
        "| Arm | Δ disp | Δ exp | Δ retest | Δ trades | Δ ΣR | retest | trades | avgRR |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        t, e = r["throughput"], r["expectancy"]
        if r["arm_id"] == "baseline":
            lines.append(
                f"| **baseline** | — | — | — | — | — | {t['n_retest']} | "
                f"{t['approved_trades']} | {e['avg_rr_net']} |"
            )
        else:
            d = r["delta_vs_baseline"]
            lines.append(
                f"| `{r['arm_id']}` | {d['delta_n_displacement']} | "
                f"{d['delta_n_expansion']} | {d['delta_n_retest']} | "
                f"{d['delta_approved_trades']} | {d['delta_total_pnl_rr_net']} | "
                f"{t['n_retest']} | {t['approved_trades']} | {e['avg_rr_net']} |"
            )
    lines += ["", "## Rank by Δ displacement", ""]
    for item in report["ranking"]["by_delta_n_displacement"]:
        lines.append(
            f"- `{item['arm_id']}`: Δ disp = **{item['delta_n_displacement']}**"
        )
    lines += ["", "## Rank by Δ retest", ""]
    for item in report["ranking"]["by_delta_retest"]:
        lines.append(f"- `{item['arm_id']}`: Δ retest = **{item['delta_n_retest']}**")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Wrote", out_json, flush=True)
    print("Wrote", out_md, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
