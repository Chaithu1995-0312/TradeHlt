# -*- coding: utf-8 -*-
"""
session_sweep.py — Phase 6c empirical-throughput floor (staged session experiment).

Measures the #1 throughput lever identified by the Phase 6b funnel diagnosis: the
post-score SESSION filter. The binding constraint is RETEST->EXECUTION; 64 of 93
FILTER_REJECTED are session rejects (44 OFF_SESSION + 20 ASIA). The score gate is NOT
binding (134/135 retests approved), so this sweeps sessions only.

This is a SCIENTIFIC EXPERIMENT WITH ATTRIBUTION, not a batch sweep:
  V0 baseline (HARD GATE)  -> must reproduce the published baseline or we STOP
  V1 +ASIA        (alone)  -> marginal contribution of ASIA
  V2 +OFF_SESSION (alone)  -> marginal contribution of off-session hours
  V3 +ASIA+OFF             -> do they compose / interact?
  V4 all-sessions          -> frequency CEILING (research only, not a candidate)

The lever is session-NAME membership in CRTConfig.allowed_sessions (the mechanism the
existing p3b_session_relax_diag.py uses) — NOT editing session_windows. Construction
mirrors p3b exactly (load_prod_config_from_registry -> dataclasses.replace) so V0 is
faithful to the baseline that produced 15 trades.

MEASURE-ONLY: writes only results/session_sweep/. No config edit, no re-hash, no
promotion. Deterministic (fixed slippage_seed from the prod 'backtest' section).

Usage:
    python scripts/analysis/session_sweep.py                      # V0 + all variants
    python scripts/analysis/session_sweep.py --variants V1        # V0 + V1 only (staged)
    python scripts/analysis/session_sweep.py --variants V1,V2
    python scripts/analysis/session_sweep.py --instrument BNBUSDT --csv data/BNBUSDT_M15.csv
"""

import sys
import os
import json
import time
import argparse
import dataclasses
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[2]
_SRC  = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
os.chdir(_ROOT)

from runtime.backtest_v2 import (
    BacktestRunner, BacktestConfig, CandleLoader,
    load_prod_config_from_registry, PROD_VERSION, MultiInstrumentRunner,
)

# ── Published baseline (BNBUSDT M15) — the V0 hard-gate reference ──────────────
# Reconciled 2026-06-11 to the GOVERNING intrabar_touch exit model (CRTConfig.exit_model
# default, adopted 2026-06-10; MEMORY project_exit_model_adoption). The legacy 15/1.79/+4.91%
# figures (docs/analysis/roi-baseline-bnbusdt-2026-05-29.md) were captured under the OLD
# close-only exit model and now false-fail this gate. The trade COUNT (15) is exit-model
# invariant and still reproduces exactly; PF/ROI shift because intrabar touch realizes SL/TP
# intrabar. Truth source: docs/analysis/session-sweep-bnbusdt-2026-06-11.md.
_BASELINE = {
    "approved_trades":  15,
    "profit_factor":    1.0286,
    "total_return_pct": 0.001234,   # +0.12%
}
_GATE_PF_TOL  = 0.05    # PF tolerance for the hard gate
_GATE_ROI_TOL = 0.002   # ROI (fraction) tolerance for the hard gate

# ── Variant definitions: session NAMES added to the baseline allowed_sessions ──
# V4 adds the full label universe (LONDON/NEWYORK/ASIA/OFF_SESSION) = frequency ceiling.
VARIANT_ADDS = {
    "V0_baseline":   (),
    "V1_asia":       ("ASIA",),
    "V2_offsession": ("OFF_SESSION",),
    "V3_asia_off":   ("ASIA", "OFF_SESSION"),
    "V4_all":        ("LONDON", "NEWYORK", "ASIA", "OFF_SESSION"),
}

# ── OOS decision rule + Governance Threshold G1 (--train-split mode only) ───────
# Post-Phase-0 funding doctrine: a session change is promoted only if its economics
# (a) hold out-of-sample and (b) beat the incumbent by a MATERIAL margin. Ranking is
# economic (Expected Monthly ROI), not statistical (PF/expectancy alone).
_OOS_RETENTION_MIN = 0.70   # OOS expectancy_rr must be >= 70% of IS expectancy_rr
_G1_REL_MIN        = 0.10   # G1: >= +10% RELATIVE Expected Monthly ROI vs incumbent
_G1_ABS_MIN        = 0.01   # G1: AND >= +1.0 percentage-point ABSOLUTE (fraction)


def _expected_monthly_roi(annualized_return_pct: float) -> float:
    """Compound the runner's span-aware CAGR down to a monthly rate.
    (1+CAGR)**(1/12)-1. Window-span-aware because annualized_return_pct is computed
    from the candle count actually streamed (so IS and OOS are comparable rates)."""
    g = 1.0 + annualized_return_pct
    return (g ** (1.0 / 12.0) - 1.0) if g > 0 else -1.0


def _g1_pass(cand_roi: float, inc_roi: float) -> tuple[bool, float, float]:
    """Governance Threshold G1 — material monthly-ROI gain vs incumbent.
    Requires BOTH >= +10% relative AND >= +1pp absolute. Returns (pass, abs_gain, rel_gain)."""
    abs_gain = cand_roi - inc_roi
    rel_gain = abs_gain / abs(inc_roi) if inc_roi != 0 else float("inf")
    ok = (abs_gain >= _G1_ABS_MIN) and (inc_roi <= 0 or rel_gain >= _G1_REL_MIN)
    return ok, abs_gain, rel_gain


def _run_one(crt_cfg, instrument: str, csv_path: str, output_dir: str, label: str,
             start_idx: int = 0, end_idx: int = 0) -> dict:
    """Run one backtest; return a flat metrics dict. Mirrors p3b construction.

    start_idx/end_idx (0,0 => full window) slice the candle stream for IS/OOS runs,
    mirroring auto_tuner_multi._run_single_instrument so OOS semantics match the tuner.
    annualized_return_pct (and thus Expected Monthly ROI) is span-aware: it is computed
    from the candle count actually streamed, so IS and OOS rates are comparable."""
    cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
    cfg.instrument = instrument
    cfg.pip_size   = MultiInstrumentRunner.INSTRUMENT_PIP.get(instrument, 0.0001)

    loader = CandleLoader(csv_path, instrument)
    runner = BacktestRunner(
        cfg, csv_path=csv_path,
        overrides={"diagnostic": label, "instrument": instrument},
    )
    stream = loader.stream()
    total  = loader.count()
    if start_idx > 0 or end_idx > 0:
        def _slice(stream_in):
            for i, c in enumerate(stream_in):
                if i < start_idx:
                    continue
                if end_idx > 0 and i >= end_idx:
                    break
                yield c
        stream     = _slice(stream)
        candle_cnt = (end_idx if end_idx > 0 else total) - start_idx
    else:
        candle_cnt = total

    t0 = time.time()
    m = runner.run(stream, candle_cnt, output_dir)
    elapsed = time.time() - t0

    fc = m.funnel_counts or {}
    return {
        "label":                 label,
        "allowed_sessions":      list(crt_cfg.allowed_sessions),
        "approved_trades":       int(m.approved_trades),
        "win_rate":              round(float(m.win_rate), 4),
        "expectancy_rr":         round(float(m.avg_rr_net), 4),
        "profit_factor":         round(float(m.profit_factor), 4),
        "total_pnl_rr_net":      round(float(m.total_pnl_rr_net), 4),
        "total_return_pct":      round(float(m.total_return_pct), 6),
        "annualized_return_pct": round(float(m.annualized_return_pct), 6),
        "expected_monthly_roi":  round(_expected_monthly_roi(float(m.annualized_return_pct)), 6),
        "return_to_max_dd":      round(float(m.return_to_max_dd), 4),
        "max_drawdown_pct":      round(float(m.max_drawdown_pct), 6),
        "approval_rate":         round(float(m.approval_rate), 4),
        "funnel_execution":      int(fc.get("EXECUTION", 0)),
        "funnel_retest":         int(fc.get("RETEST", 0)),
        "candles":               candle_cnt,
        "elapsed_s":             round(elapsed, 1),
    }


def _check_v0_gate(v0: dict) -> bool:
    """Hard gate: V0 must reproduce the published baseline (else harness untrustworthy)."""
    trades_ok = v0["approved_trades"] == _BASELINE["approved_trades"]
    pf_ok     = abs(v0["profit_factor"]  - _BASELINE["profit_factor"])  <= _GATE_PF_TOL
    roi_ok    = abs(v0["total_return_pct"] - _BASELINE["total_return_pct"]) <= _GATE_ROI_TOL
    print("\n" + "=" * 72)
    print("V0 BASELINE HARD GATE")
    print("=" * 72)
    print(f"  trades : {v0['approved_trades']:>8}   expected {_BASELINE['approved_trades']}   "
          f"[{'PASS' if trades_ok else 'FAIL'}]")
    print(f"  PF     : {v0['profit_factor']:>8.4f}   expected ~{_BASELINE['profit_factor']}  "
          f"(±{_GATE_PF_TOL})  [{'PASS' if pf_ok else 'FAIL'}]")
    print(f"  ROI    : {v0['total_return_pct']*100:>7.2f}%   expected ~+{_BASELINE['total_return_pct']*100:.2f}% "
          f"(±{_GATE_ROI_TOL*100:.1f}%)  [{'PASS' if roi_ok else 'FAIL'}]")
    return trades_ok and pf_ok and roi_ok


def _run_oos_mode(args, instrument: str, csv_path: str, output_dir: str) -> int:
    """OOS-validated session sweep (--train-split < 1.0).

    Runs the V0..V4 ladder on an IS window and an OOS holdout, ranks by Expected
    Monthly ROI, and applies the OOS decision rule + Governance Threshold G1.

    Construction note: the ladder is built from the GLOBAL allowed_sessions
    (version-stable restrictive base) up to all-sessions — NOT the per-instrument
    resolved set. Against an already-expanded prod (e.g. BNB all-sessions under v4)
    the per-instrument base would collapse the ladder. The current prod-resolved set
    is the G1 INCUMBENT the challengers must beat materially to justify churn.
    """
    from config_layer.production_config import get_prod_metadata, resolve_allowed_sessions

    total      = CandleLoader(csv_path, instrument).count()
    train_end  = int(total * args.train_split)
    if train_end <= 0 or train_end >= total:
        sys.exit(f"[ERROR] --train-split {args.train_split} yields empty IS/OOS window "
                 f"(total={total}, train_end={train_end}).")

    # Global (version-stable) base + current prod-resolved incumbent set.
    meta = get_prod_metadata()
    er   = meta.get("engine_runner") or {}
    global_sessions = resolve_allowed_sessions(er, "__GLOBAL_NO_OVERRIDE__")
    base_cfg        = load_prod_config_from_registry(PROD_VERSION, instrument)
    prod_resolved   = tuple(base_cfg.allowed_sessions)
    if not global_sessions:
        # Defensive fallback: strip the expandable sessions off the resolved set.
        global_sessions = tuple(s for s in prod_resolved if s not in ("ASIA", "OFF_SESSION"))

    print(f"[session_sweep:OOS] instrument={instrument}  prod={PROD_VERSION}")
    print(f"[session_sweep:OOS] candles={total:,}  IS=0->{train_end:,}  OOS={train_end:,}->{total:,}  "
          f"(train_split={args.train_split})")
    print(f"[session_sweep:OOS] ladder base (global) = {global_sessions}")
    print(f"[session_sweep:OOS] G1 incumbent (prod-resolved) = {prod_resolved}\n")

    rows: list[dict] = []
    for key in VARIANT_ADDS:  # full ladder V0..V4 (attribution needs every rung)
        adds    = tuple(s for s in VARIANT_ADDS[key] if s not in global_sessions)
        patched = global_sessions + adds
        crt_cfg = dataclasses.replace(base_cfg, allowed_sessions=patched)
        is_row  = _run_one(crt_cfg, instrument, csv_path, output_dir, f"{key}_IS",
                           start_idx=0, end_idx=train_end)
        oos_row = _run_one(crt_cfg, instrument, csv_path, output_dir, f"{key}_OOS",
                           start_idx=train_end, end_idx=total)
        rows.append({
            "variant":          key,
            "allowed_sessions": list(patched),
            "is_incumbent":     set(patched) == set(prod_resolved),
            "IS":               is_row,
            "OOS":              oos_row,
        })
        print(f"[session_sweep:OOS] {key}: sessions={patched}\n"
              f"    IS : trades={is_row['approved_trades']:>3}  exp={is_row['expectancy_rr']:+.3f}R  "
              f"PF={is_row['profit_factor']:.2f}  ROI/mo={is_row['expected_monthly_roi']*100:+.2f}%\n"
              f"    OOS: trades={oos_row['approved_trades']:>3}  exp={oos_row['expectancy_rr']:+.3f}R  "
              f"PF={oos_row['profit_factor']:.2f}  ROI/mo={oos_row['expected_monthly_roi']*100:+.2f}%\n")

    # Incumbent reference (current prod-resolved set); fall back to V4_all if unmatched.
    incumbent = next((r for r in rows if r["is_incumbent"]), None)
    if incumbent is None:
        incumbent = next(r for r in rows if r["variant"] == "V4_all")
        incumbent["is_incumbent"] = True
    inc_oos_roi = incumbent["OOS"]["expected_monthly_roi"]
    inc_is_roi  = incumbent["IS"]["expected_monthly_roi"]

    # Rank stability: rank by Expected Monthly ROI within each window (1 = best).
    def _ranks(window: str) -> dict:
        order = sorted(rows, key=lambda r: r[window]["expected_monthly_roi"], reverse=True)
        return {r["variant"]: i + 1 for i, r in enumerate(order)}
    is_rank, oos_rank = _ranks("IS"), _ranks("OOS")

    # Per-variant verdict: OOS sign gate + retention + rank stability + G1 (on OOS ROI).
    for r in rows:
        is_exp  = r["IS"]["expectancy_rr"]
        oos_exp = r["OOS"]["expectancy_rr"]
        oos_pf  = r["OOS"]["profit_factor"]
        sign_ok      = oos_exp > 0 and oos_pf > 1.0
        retention    = (oos_exp / is_exp) if is_exp > 0 else 0.0
        retention_ok = is_exp > 0 and retention >= _OOS_RETENTION_MIN
        rank_ok      = is_rank[r["variant"]] <= args.top_k and oos_rank[r["variant"]] <= args.top_k
        g1_ok, g1_abs, g1_rel = _g1_pass(r["OOS"]["expected_monthly_roi"], inc_oos_roi)
        r["decision"] = {
            "is_rank": is_rank[r["variant"]], "oos_rank": oos_rank[r["variant"]],
            "oos_sign_ok": sign_ok, "retention": round(retention, 3), "retention_ok": retention_ok,
            "rank_stable": rank_ok,
            "g1_abs_gain_pp": round(g1_abs * 100, 3), "g1_rel_gain": round(g1_rel, 3), "g1_pass": g1_ok,
            # Incumbent itself is the no-change reference, never a "challenger PASS".
            "verdict": "PASS" if (not r["is_incumbent"] and sign_ok and retention_ok and rank_ok and g1_ok)
                       else ("INCUMBENT" if r["is_incumbent"] else "FAIL"),
        }

    # Recommendation: best-IS-ROI PASS challenger; else keep incumbent (no churn).
    passers = [r for r in rows if r["decision"]["verdict"] == "PASS"]
    if passers:
        winner = max(passers, key=lambda r: r["IS"]["expected_monthly_roi"])
        recommendation = {"action": "PROMOTE", "variant": winner["variant"],
                          "allowed_sessions": winner["allowed_sessions"]}
    else:
        recommendation = {"action": "KEEP_INCUMBENT", "variant": incumbent["variant"],
                          "allowed_sessions": incumbent["allowed_sessions"]}

    # ── Economic table ─────────────────────────────────────────────────────────
    print("\n" + "=" * 108)
    print(f"SESSION SWEEP (OOS) — {instrument}   incumbent={incumbent['variant']}   "
          f"G1: rel>=+{_G1_REL_MIN*100:.0f}% AND abs>=+{_G1_ABS_MIN*100:.0f}pp   retention>={_OOS_RETENTION_MIN:.2f}")
    print("=" * 108)
    hdr = (f"{'variant':<14}{'IS exp':>8}{'OOS exp':>9}{'IS ROI/mo':>11}{'OOS ROI/mo':>12}"
           f"{'reten':>7}{'OOS PF':>8}{'G1':>6}{'verdict':>11}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        d = r["decision"]
        print(f"{r['variant']:<14}{r['IS']['expectancy_rr']:>+8.3f}{r['OOS']['expectancy_rr']:>+9.3f}"
              f"{r['IS']['expected_monthly_roi']*100:>+10.2f}%{r['OOS']['expected_monthly_roi']*100:>+11.2f}%"
              f"{d['retention']:>7.2f}{r['OOS']['profit_factor']:>8.2f}"
              f"{('Y' if d['g1_pass'] else 'n'):>6}{d['verdict']:>11}")
    print(f"\n  Incumbent ({incumbent['variant']}) Expected Monthly ROI: "
          f"IS {inc_is_roi*100:+.2f}%  OOS {inc_oos_roi*100:+.2f}%")
    print(f"  RECOMMENDATION: {recommendation['action']} -> {recommendation['variant']} "
          f"({recommendation['allowed_sessions']})")
    if recommendation["action"] == "KEEP_INCUMBENT":
        print("  No challenger cleared OOS retention + G1 — keeping current prod sessions is the "
              "correct no-churn result (valid PASS-to-no-change).")

    payload = {
        "mode":              "oos",
        "instrument":        instrument,
        "prod_version":      PROD_VERSION,
        "csv_path":          csv_path,
        "train_split":       args.train_split,
        "windows":           {"total": total, "train_end": train_end},
        "ladder_base_global": list(global_sessions),
        "incumbent_sessions": list(prod_resolved),
        "incumbent_variant":  incumbent["variant"],
        "decision_rule":     {"oos_retention_min": _OOS_RETENTION_MIN,
                              "g1_rel_min": _G1_REL_MIN, "g1_abs_min": _G1_ABS_MIN,
                              "top_k": args.top_k, "selection_metric": "is_expected_monthly_roi",
                              "gate_window": "oos"},
        "rows":              rows,
        "recommendation":    recommendation,
    }
    results_json = Path(args.results_json) if args.results_json else (
        _ROOT / "results" / "session_sweep" / f"{instrument.lower()}_oos.json"
    )
    results_json.parent.mkdir(parents=True, exist_ok=True)
    results_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\n[session_sweep:OOS] results -> {results_json}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 6c staged session sweep (+ OOS mode)")
    ap.add_argument("--instrument", default="BNBUSDT")
    ap.add_argument("--csv", default=None, help="Data CSV (default data/<INSTR>_M15.csv)")
    ap.add_argument("--output-dir", default=str(_ROOT / "results" / "session_sweep" / "_runs"))
    ap.add_argument("--variants", default="V1,V2,V3,V4",
                    help="Comma-separated variant keys to run after V0 (V0 always runs first). "
                         "Ignored in --train-split mode (full ladder always runs).")
    ap.add_argument("--floor-trades", type=int, default=40)
    ap.add_argument("--floor-pf", type=float, default=1.5)
    ap.add_argument("--train-split", type=float, default=1.0,
                    help="<1.0 activates OOS mode: IS=[0,split), OOS=[split,end] with "
                         "retention + Governance Threshold G1. Default 1.0 = legacy full-window.")
    ap.add_argument("--top-k", type=int, default=5,
                    help="Rank-stability window: a variant must rank top-K by Expected Monthly ROI "
                         "in BOTH IS and OOS (OOS mode only).")
    ap.add_argument("--results-json", default=None,
                    help="Output JSON (default results/session_sweep/<instr-lower>[_oos].json)")
    args = ap.parse_args()

    instrument = args.instrument
    csv_path = args.csv or str(_ROOT / "data" / f"{instrument}_M15.csv")
    if not Path(csv_path).exists():
        sys.exit(f"[ERROR] data file not found: {csv_path}")
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    # OOS-validated mode (additive; legacy full-window path untouched below).
    if args.train_split < 1.0:
        return _run_oos_mode(args, instrument, csv_path, args.output_dir)

    results_json = Path(args.results_json) if args.results_json else (
        _ROOT / "results" / "session_sweep" / f"{instrument.lower()}.json"
    )
    results_json.parent.mkdir(parents=True, exist_ok=True)

    # Resolve requested variants; V0 always first (gate reference), dedup, keep order.
    requested = [v.strip() for v in args.variants.split(",") if v.strip()]
    short = {k.split("_")[0]: k for k in VARIANT_ADDS}     # "V1" -> "V1_asia"
    run_keys = ["V0_baseline"]
    for r in requested:
        key = r if r in VARIANT_ADDS else short.get(r)
        if key is None:
            sys.exit(f"[ERROR] unknown variant '{r}'. Valid: {list(VARIANT_ADDS)} or V0..V4")
        if key not in run_keys:
            run_keys.append(key)

    base_cfg = load_prod_config_from_registry(PROD_VERSION, instrument)
    base_sessions = tuple(base_cfg.allowed_sessions)
    print(f"[session_sweep] instrument={instrument}  prod={PROD_VERSION}")
    print(f"[session_sweep] baseline allowed_sessions = {base_sessions}")
    print(f"[session_sweep] running: {run_keys}\n")

    rows: list[dict] = []
    for key in run_keys:
        adds = tuple(s for s in VARIANT_ADDS[key] if s not in base_sessions)
        patched = base_sessions + adds
        crt_cfg = dataclasses.replace(base_cfg, allowed_sessions=patched)
        print(f"[session_sweep] {key}: allowed_sessions={patched} (added={adds or '—'}) ...")
        row = _run_one(crt_cfg, instrument, csv_path, args.output_dir, key)
        row["variant"] = key
        row["added_sessions"] = list(adds)
        rows.append(row)
        print(f"             -> trades={row['approved_trades']}  WR={row['win_rate']:.0%}  "
              f"PF={row['profit_factor']:.3f}  ROI={row['total_return_pct']*100:+.2f}%  "
              f"MAR={row['return_to_max_dd']:.2f}  maxDD={row['max_drawdown_pct']*100:.2f}%\n")

    v0 = rows[0]
    # The published-baseline hard gate is BNBUSDT-specific (that is where 15/1.79/4.91 was
    # measured). For other instruments V0 is simply their own per-instrument reference.
    if instrument == "BNBUSDT":
        gate_pass = _check_v0_gate(v0)
    else:
        gate_pass = True
        print(f"\n[session_sweep] (V0 published-baseline gate is BNBUSDT-only; "
              f"{instrument} V0 used as its own reference)")

    # ── Comparison table (deltas vs V0) ───────────────────────────────────────
    print("\n" + "=" * 100)
    print(f"SESSION SWEEP — {instrument}  (deltas vs V0; floor = >={args.floor_trades} trades & PF>={args.floor_pf})")
    print("=" * 100)
    hdr = f"{'variant':<14}{'trades':>7}{'Δtr':>6}{'WR':>7}{'PF':>7}{'ROI%':>8}{'MAR':>6}{'maxDD%':>8}{'appr':>6}{'floor?':>8}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        dtr = r["approved_trades"] - v0["approved_trades"]
        clears = (r["approved_trades"] >= args.floor_trades and r["profit_factor"] >= args.floor_pf)
        flag = "" if r["variant"] == "V0_baseline" else ("CLEARS" if clears else "—")
        print(f"{r['variant']:<14}{r['approved_trades']:>7}{dtr:>+6}{r['win_rate']:>7.0%}"
              f"{r['profit_factor']:>7.2f}{r['total_return_pct']*100:>+8.2f}{r['return_to_max_dd']:>6.2f}"
              f"{r['max_drawdown_pct']*100:>8.2f}{r['approval_rate']:>6.0%}{flag:>8}")

    # ── Post-V1 decision gate ──────────────────────────────────────────────────
    v1 = next((r for r in rows if r["variant"] == "V1_asia"), None)
    if v1 is not None:
        v1_clears = (v1["approved_trades"] >= args.floor_trades and v1["profit_factor"] >= args.floor_pf)
        print("\n-- Post-V1 decision gate --")
        print(f"  V1 (+ASIA): trades {v0['approved_trades']}->{v1['approved_trades']} "
              f"(Δ{v1['approved_trades']-v0['approved_trades']:+}), PF {v0['profit_factor']:.2f}->{v1['profit_factor']:.2f}, "
              f"maxDD {v0['max_drawdown_pct']*100:.2f}%->{v1['max_drawdown_pct']*100:.2f}%")
        if v1_clears:
            print("  => V1 ALONE clears the floor — Trd-M6 throughput gate effectively solved by +ASIA.")
            print("     V2/V3/V4 demote to optimization/attribution (off the critical path).")
        else:
            print("  => V1 alone does NOT clear the floor; widening (V2/V3) needed — continue staged runs.")
            print("     Reminder: 'rejects != profitable trades' — the gate is trades AND PF, not trades alone.")

    payload = {
        "instrument":       instrument,
        "prod_version":     PROD_VERSION,
        "csv_path":         csv_path,
        "baseline_sessions": list(base_sessions),
        "floor": {"min_trades": args.floor_trades, "min_profit_factor": args.floor_pf},
        "v0_gate_pass":     gate_pass,
        "published_baseline": _BASELINE,
        "rows":             rows,
    }
    results_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\n[session_sweep] results -> {results_json}")

    if not gate_pass:
        print("\n[session_sweep] *** V0 HARD GATE FAILED — harness untrustworthy; "
              "do not trust any variant delta. STOP and reconcile against the baseline. ***")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
