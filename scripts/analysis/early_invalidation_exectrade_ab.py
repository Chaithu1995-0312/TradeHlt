"""
early_invalidation_exectrade_ab.py
==================================
Executed-trade A/B for the timing-based early-invalidation rule — OFFLINE
direct-effect method (NO spine change).

>>> STATUS: DIRECTIONAL EVIDENCE, NOT PRODUCTION EVIDENCE. <<<
The executed-trade population is tiny (~35 BNB). At that N the portfolio risk
metrics (MaxDD/Recovery/Ulcer/TUW) are noise-dominated — this run is a MECHANISM
+ DIRECTION check (does the rule behave as designed; does drawdown move the right
way; are winners preserved), not a promotion gate. Do NOT promote Trd-M6 or enable
live on this; freeze "research-complete / production-pending" until executed-trade
throughput is materially higher.

Method (causal, no-lookahead, no engine modification):
  For each executed trade in a backtest trades CSV, re-walk candles from entry.
  If the trade survived past candle K AND never reached +0.25R by K, the rule
  would have exited at candle K's close. We shift that trade's net RR by the
  offline-computed (exit_raw - natural_raw) delta; all other trades unchanged.
  Then rebuild BOTH equity curves (compounding, same risk_pct) and compare.

  Control  = actual backtest net RR per trade (rule OFF).
  Treatment = control + per-trade rule delta (rule ON).
  NOTE: ignores capital-recycling / re-entry sequencing (an early exit can't free
  the engine to take a new trade here) — so treatment is CONSERVATIVE on upside.

Usage:
  python scripts/analysis/early_invalidation_exectrade_ab.py \
      --trades results/ei_ab_fresh/run_.../BNBUSDT_trades.csv \
      --csv data/BNBUSDT_M15.csv --instrument BNBUSDT --k 3
"""
from __future__ import annotations

import argparse
import csv as _csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from replay.timing_reconstructor import load_candles, simulate_with_timing  # noqa: E402


def _equity_curve(rrs: list, risk_pct: float, initial: float = 100_000.0) -> list:
    cap = initial
    curve = [cap]
    for rr in rrs:
        cap *= (1.0 + risk_pct * rr)
        curve.append(cap)
    return curve


def _risk_metrics(curve: list) -> dict:
    initial, final = curve[0], curve[-1]
    peak = curve[0]
    max_dd = 0.0
    dd_sq_sum = 0.0
    under = 0
    longest = cur = 0
    for eq in curve:
        peak = max(peak, eq)
        dd = (peak - eq) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
        dd_sq_sum += (dd * 100.0) ** 2
        if dd > 1e-9:
            under += 1
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    total_return = (final - initial) / initial
    ulcer = math.sqrt(dd_sq_sum / len(curve))
    return {
        "total_return_pct": round(total_return, 4),
        "max_drawdown_pct": round(max_dd, 4),
        "recovery_factor": round(total_return / max_dd, 3) if max_dd > 1e-9 else None,
        "ulcer_index": round(ulcer, 3),
        "time_under_water_frac": round(under / len(curve), 4),
        "longest_underwater_run": longest,
    }


def _return_metrics(rrs: list) -> dict:
    n = len(rrs)
    wins = [r for r in rrs if r > 0]
    losses = [r for r in rrs if r <= 0]
    return {
        "n": n,
        "expectancy_R": round(sum(rrs) / n, 4) if n else 0.0,
        "win_rate": round(len(wins) / n, 4) if n else 0.0,
        "winner_avg_R": round(sum(wins) / len(wins), 4) if wins else 0.0,
        "loser_avg_R": round(sum(losses) / len(losses), 4) if losses else 0.0,
    }


def run(trades_csv: Path, candle_csv: Path, *, k: int, risk_pct: float,
        trail_mult: float, horizon: int) -> dict:
    ts, highs, lows, closes = load_candles(candle_csv)
    idx = {t: i for i, t in enumerate(ts)}
    rows = list(_csv.DictReader(trades_csv.open(encoding="utf-8")))

    control_rr, treat_rr = [], []
    n_cut = cut_winners = cut_losers = ts_miss = 0
    saved = forgone = 0.0

    for r in rows:
        direction = r["direction"].strip().lower()
        entry = float(r["entry_fill"]); sl = float(r["sl"])
        rd = abs(entry - sl)
        natural_net = float(r["pnl_rr_net"])
        dur_actual = int(float(r.get("duration_candles", 0)))
        tp = float(r.get("tp2") or r.get("tp1") or (entry + 2 * rd if direction == "long" else entry - 2 * rd))
        t = r["opened_at"].strip().replace("T", " ")
        i = idx.get(t)
        treat_net = natural_net
        if i is not None and rd > 0:
            end = min(i + 1 + horizon, len(highs))
            bars = [(highs[j], lows[j], closes[j]) for j in range(i + 1, end)]
            nat = simulate_with_timing(direction, entry, sl, tp, bars, rd, trail_mult=trail_mult)
            reached_by_k = nat["time_to_025R"] is not None and nat["time_to_025R"] <= k
            # Rule fires iff the (actual) trade survived past K and never +0.25R by K.
            if dur_actual > k and not reached_by_k:
                ei = i + k
                if ei < len(closes):
                    ec = closes[ei]
                    exit_raw = (ec - entry) / rd if direction == "long" else (entry - ec) / rd
                    delta = exit_raw - nat["rr_achieved"]
                    treat_net = natural_net + delta
                    n_cut += 1
                    if natural_net > 0:
                        cut_winners += 1; forgone += -delta
                    else:
                        cut_losers += 1; saved += delta
        else:
            ts_miss += 1
        control_rr.append(natural_net)
        treat_rr.append(treat_net)

    ctrl_curve = _equity_curve(control_rr, risk_pct)
    treat_curve = _equity_curve(treat_rr, risk_pct)
    return {
        "schema": "early_invalidation_exectrade_ab_v1",
        "status": "DIRECTIONAL EVIDENCE — NOT PRODUCTION EVIDENCE (research-complete / production-pending)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "trades_csv": str(trades_csv), "candle_csv": str(candle_csv),
        "params": {"k": k, "risk_pct": risk_pct, "trail_mult": trail_mult,
                   "horizon": horizon, "method": "offline direct-effect; ignores capital recycling"},
        "counts": {"n_trades": len(rows), "ts_miss": ts_miss, "n_cut": n_cut,
                   "cut_winners": cut_winners, "cut_losers": cut_losers},
        "headline_net_rr": {
            "rr_saved_on_cut_losers": round(saved, 4),
            "rr_forgone_on_cut_winners": round(forgone, 4),
            "net_rr_impact": round(saved - forgone, 4),
        },
        "control": {**_return_metrics(control_rr), **_risk_metrics(ctrl_curve)},
        "treatment": {**_return_metrics(treat_rr), **_risk_metrics(treat_curve)},
    }


def _print(inst: str, d: dict):
    c, t, h, cc = d["control"], d["treatment"], d["headline_net_rr"], d["counts"]
    print(f"\n############ {inst}  EXECUTED-TRADE A/B (k={d['params']['k']}, N={cc['n_trades']}) ############")
    print(f"** {d['status']} **")
    print(f"Cut {cc['n_cut']} trades ({cc['cut_losers']} losers, {cc['cut_winners']} winners) | ts_miss={cc['ts_miss']}")
    print(f"  RR saved on cut losers   = {h['rr_saved_on_cut_losers']:>+8.3f}R")
    print(f"  RR forgone on cut winners= {-h['rr_forgone_on_cut_winners']:>+8.3f}R")
    print(f"  NET RR impact            = {h['net_rr_impact']:>+8.3f}R")
    def line(name, kc, kt, fmt="{:>+9.4f}"):
        cv, tv = c.get(kc), t.get(kt)
        sc = fmt.format(cv) if isinstance(cv, (int, float)) else str(cv)
        st = fmt.format(tv) if isinstance(tv, (int, float)) else str(tv)
        print(f"  {name:<24} {sc} -> {st}")
    print("control -> treatment:")
    line("Expectancy_R", "expectancy_R", "expectancy_R")
    line("Win rate", "win_rate", "win_rate")
    line("Winner avg RR (guard)", "winner_avg_R", "winner_avg_R")
    line("Total return", "total_return_pct", "total_return_pct")
    line("Max drawdown (PRIMARY)", "max_drawdown_pct", "max_drawdown_pct")
    line("Recovery factor", "recovery_factor", "recovery_factor", "{:>9.3f}")
    line("Ulcer index", "ulcer_index", "ulcer_index", "{:>9.3f}")
    line("Time under water", "time_under_water_frac", "time_under_water_frac")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trades", required=True, type=Path)
    ap.add_argument("--csv", required=True, type=Path)
    ap.add_argument("--instrument", required=True)
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--risk-pct", type=float, default=0.01)
    ap.add_argument("--trail-mult", type=float, default=0.5)
    ap.add_argument("--horizon", type=int, default=40)
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args(argv)

    out = args.output or (Path("results/analysis") /
                          f"early_invalidation_exectrade_ab_{args.instrument}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    d = run(args.trades, args.csv, k=args.k, risk_pct=args.risk_pct,
            trail_mult=args.trail_mult, horizon=max(args.horizon, args.k + 1))
    out.write_text(json.dumps(d, indent=2), encoding="utf-8")
    _print(args.instrument, d)
    print(f"\nOUTPUT:exectrade_ab:{out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
