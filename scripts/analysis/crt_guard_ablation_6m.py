# -*- coding: utf-8 -*-
"""Episode-level one-predicate counterfactual ablations on the 6-month RB1 window.

Disables ONE structural guard at a time via CRTConfig dataclass.replace (in-memory
only — production JSON/code untouched). Full BacktestRunner path for trades + RR.

Metrics per arm:
  structure: n_sweep, n_displacement, n_expansion, n_retest, n_execution
  throughput: approved_trades, filter_rejected
  expectancy: avg_rr_net, total_pnl_rr_net, win_rate (DESCRIPTIVE only)

Gate: BACKTEST_ENGINE_GATE=0 (CRT isolation).
"""
from __future__ import annotations

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

# Quiet noisy loggers
for name in (
    "CRT_ENGINE_V2",
    "CRT.StateMachine",
    "CRT.Backtest",
    "CRT.Execution",
    "FeaturePipeline",
    "FLOW:FEATURE_PIPELINE",
):
    logging.getLogger(name).setLevel(logging.ERROR)

from config_layer.production_config import (  # noqa: E402
    get_active_version,
    load_prod_config_from_registry,
)
from runtime.backtest_v2 import BacktestConfig, BacktestRunner, CandleLoader  # noqa: E402

CSV = ROOT / "data" / "XAUUSD_W2025-11-21-to-2026-05-21.csv"
OUT_DIR = ROOT / "results" / "runtime_benchmarks" / "guard_ablation_6m"
OUT_JSON = OUT_DIR / "guard_ablation_6m_report.json"
OUT_MD = OUT_DIR / "guard_ablation_6m_report.md"
INSTRUMENT = "XAUUSD"


def count_structure(events_path: Path) -> dict:
    n = Counter()
    filter_reasons = Counter()
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        ev = e.get("event") or e.get("kind")
        if ev == "STATE_TRANSITION":
            to = e.get("state_to")
            fr = e.get("state_from")
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
            if fr == "SWEEP" and to == "EXPANSION":
                n["n_sweep_direct_expansion"] += 1
            if fr == "DISPLACEMENT" and to == "EXPANSION":
                n["n_disp_to_expansion"] += 1
        if ev == "FILTER_REJECTED":
            n["n_filter_rejected"] += 1
            filter_reasons[str(e.get("reason"))] += 1
        if ev == "TRADE_OPENED":
            n["n_trade_opened"] += 1
    n["filter_reasons"] = dict(filter_reasons)
    return dict(n)


# One ablation = disable exactly one predicate family (extreme permissive threshold)
ABLATIONS: list[tuple[str, str, dict]] = [
    (
        "baseline",
        "All guards at production values",
        {},
    ),
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


def run_arm(arm_id: str, description: str, overrides: dict) -> dict:
    os.environ["BACKTEST_ENGINE_GATE"] = "0"
    base = load_prod_config_from_registry("v2_multi_2026_04", INSTRUMENT)
    crt_cfg = replace(base, **overrides) if overrides else base
    bt_cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
    bt_cfg.instrument = INSTRUMENT

    out = OUT_DIR / arm_id
    out.mkdir(parents=True, exist_ok=True)

    loader = CandleLoader(str(CSV), INSTRUMENT)
    candles = list(loader.stream())
    runner = BacktestRunner(
        bt_cfg,
        csv_path=str(CSV),
        overrides={"ablation": arm_id, **{k: str(v) for k, v in overrides.items()}},
    )

    t0 = time.perf_counter()
    metrics = runner.run(iter(candles), len(candles), str(out))
    elapsed = time.perf_counter() - t0

    # Find run dir
    runs = sorted(out.glob("run_*"), key=lambda p: p.stat().st_mtime)
    if not runs:
        raise RuntimeError(f"no run dir for {arm_id}")
    run_dir = runs[-1]
    summary = json.loads((run_dir / f"{INSTRUMENT}_summary.json").read_text(encoding="utf-8"))
    structure = count_structure(run_dir / f"{INSTRUMENT}_events.jsonl")

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
        f"trades={summary.get('approved_trades')} "
        f"avgRR={summary.get('avg_rr_net')} "
        f"disp={structure.get('n_displacement')} exp={structure.get('n_expansion')}",
        flush=True,
    )
    return rec


def deltas(baseline: dict, arm: dict) -> dict:
    b_t = baseline["throughput"]
    a_t = arm["throughput"]
    b_e = baseline["expectancy"]
    a_e = arm["expectancy"]
    b_s = baseline["structure"]
    a_s = arm["structure"]

    def d(key, src_b, src_a):
        vb, va = src_b.get(key), src_a.get(key)
        if vb is None or va is None:
            return None
        try:
            return va - vb
        except TypeError:
            return None

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


def main() -> int:
    if not CSV.is_file():
        raise SystemExit(f"missing {CSV}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["BACKTEST_ENGINE_GATE"] = "0"

    print(f"CSV={CSV.name} active={get_active_version()} gate=0", flush=True)
    print(f"Arms: {len(ABLATIONS)} (baseline + {len(ABLATIONS)-1} single-predicate ablations)", flush=True)

    results = []
    t_all = time.perf_counter()
    for arm_id, desc, ov in ABLATIONS:
        results.append(run_arm(arm_id, desc, ov))
    total_elapsed = time.perf_counter() - t_all

    baseline = next(r for r in results if r["arm_id"] == "baseline")
    for r in results:
        if r["arm_id"] == "baseline":
            r["delta_vs_baseline"] = None
        else:
            r["delta_vs_baseline"] = deltas(baseline, r)

    # Rank ablations by throughput (retest, then trades) and by expectancy shift
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

    report = {
        "scope": (
            "Episode-level counterfactual: one CRT structural predicate disabled per arm "
            "via in-memory CRTConfig.replace. Production code/JSON not modified."
        ),
        "authority": "DESCRIPTIVE_ONLY_NOT_PROMOTION — no activation / economic claims",
        "window": {
            "csv": CSV.relative_to(ROOT).as_posix(),
            "instrument": INSTRUMENT,
            "gate": "BACKTEST_ENGINE_GATE=0",
            "active_version": get_active_version(),
        },
        "method": {
            "runner": "BacktestRunner + CandleLoader",
            "ablation_mechanism": "dataclasses.replace(CRTConfig, **single_override_set)",
            "unit": (
                "Full run metrics (transition counts from events = episode transitions, "
                "not bar-level attempts). Expectancy from summary avg_rr_net / total_pnl_rr_net."
            ),
            "controls": "session filter, scorer, risk path unchanged across arms",
        },
        "total_elapsed_s": round(total_elapsed, 2),
        "baseline": baseline,
        "arms": results,
        "ranking": {
            "by_delta_retest": [
                {"arm_id": r["arm_id"], "delta_n_retest": r["delta_vs_baseline"]["delta_n_retest"]}
                for r in by_retest
            ],
            "by_delta_trades": [
                {
                    "arm_id": r["arm_id"],
                    "delta_approved_trades": r["delta_vs_baseline"]["delta_approved_trades"],
                }
                for r in by_trades
            ],
            "by_delta_total_pnl_rr": [
                {
                    "arm_id": r["arm_id"],
                    "delta_total_pnl_rr_net": r["delta_vs_baseline"]["delta_total_pnl_rr_net"],
                }
                for r in by_pnl
            ],
        },
        "interpretation_template": (
            "Positive delta_n_retest/trades = that guard was binding against throughput. "
            "Expectancy deltas on tiny n are noisy; prefer paired structure deltas first."
        ),
    }

    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=True, default=str) + "\n", encoding="utf-8")

    # Markdown
    lines = [
        "# Guard Ablation Report — XAUUSD 6-month RB1",
        "",
        "**Counterfactual, one predicate at a time. Production unchanged.**",
        "",
        f"- CSV: `{CSV.name}`",
        f"- Config base: `{get_active_version()}`",
        f"- Gate: `BACKTEST_ENGINE_GATE=0`",
        f"- Total wall: {total_elapsed:.1f}s",
        f"- Authority: **descriptive only** (no promotion)",
        "",
        "## Method",
        "",
        "Each arm runs full `BacktestRunner` with a single CRTConfig field(s) set to a "
        "permissive value so that one structural guard never rejects. Deltas are vs baseline.",
        "",
        "## Results table",
        "",
        "| Arm | Δ retest | Δ disp | Δ exp | Δ trades | Δ total PnL R | Δ avg RR | retest | trades | avgRR |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        t = r["throughput"]
        e = r["expectancy"]
        s = r["structure"]
        if r["arm_id"] == "baseline":
            lines.append(
                f"| **baseline** | — | — | — | — | — | — | "
                f"{t['n_retest']} | {t['approved_trades']} | {e['avg_rr_net']} |"
            )
        else:
            d = r["delta_vs_baseline"]
            lines.append(
                f"| `{r['arm_id']}` | {d['delta_n_retest']} | {d['delta_n_displacement']} | "
                f"{d['delta_n_expansion']} | {d['delta_approved_trades']} | "
                f"{d['delta_total_pnl_rr_net']} | {d['delta_avg_rr_net']} | "
                f"{t['n_retest']} | {t['approved_trades']} | {e['avg_rr_net']} |"
            )

    lines += [
        "",
        "## Ranking by Δ retest (throughput of structure)",
        "",
    ]
    for item in report["ranking"]["by_delta_retest"]:
        lines.append(f"- `{item['arm_id']}`: Δ retest = **{item['delta_n_retest']}**")

    lines += [
        "",
        "## Ranking by Δ trades",
        "",
    ]
    for item in report["ranking"]["by_delta_trades"]:
        lines.append(
            f"- `{item['arm_id']}`: Δ trades = **{item['delta_approved_trades']}**"
        )

    lines += [
        "",
        "## Ranking by Δ total PnL (R)",
        "",
        "_Noise warning: trade counts are tiny; expectancy ranks are not authority._",
        "",
    ]
    for item in report["ranking"]["by_delta_total_pnl_rr"]:
        lines.append(
            f"- `{item['arm_id']}`: Δ ΣR = **{item['delta_total_pnl_rr_net']}**"
        )

    lines += [
        "",
        "## Arm descriptions",
        "",
    ]
    for arm_id, desc, ov in ABLATIONS:
        lines.append(f"- **`{arm_id}`**: {desc}  ")
        if ov:
            lines.append(f"  overrides: `{ov}`")

    lines += [
        "",
        f"JSON: `{OUT_JSON.relative_to(ROOT).as_posix()}`",
        "",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Wrote", OUT_JSON, flush=True)
    print("Wrote", OUT_MD, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
