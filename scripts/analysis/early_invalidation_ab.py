"""
early_invalidation_ab.py
========================
Signal-level A/B for the timing-based EARLY-INVALIDATION rule (Consumer A).

Decisive artifact (the table that decides Trd-M6): for the ~140k-opportunity
universe per instrument, compare each opportunity's NATURAL outcome against its
TIMING-EXIT outcome and produce:

    Cut trades that were eventual LOSERS  -> Σ RR saved
    Cut trades that were eventual WINNERS -> Σ RR forgone
    Net RR impact = saved - forgone

Plus control-vs-treatment Tier-1/Tier-2 metrics: expectancy, win-rate, winner-set
avg RR, loser-set avg RR, profit factor.

The rule (causal, no-lookahead): a trade that has NOT reached +0.25R favorable by
candle K (and survived to candle K) is exited at that candle's close. Uses only
elapsed candles + the realized path — no future info, no model.

NOTE ON SCOPE: this is the UNIVERSE-level A/B (every candle, both directions), the
population the timing library was measured on — huge N, deterministic. Max-drawdown
is portfolio-level and ill-defined on overlapping universe positions; it is measured
in the confirmatory executed-trade backtest A/B (sequential, non-overlapping), the
follow-up step. This script decisively answers expectancy / winner-RR / Net-RR.

Usage:
  python scripts/analysis/early_invalidation_ab.py --instrument ETHUSDT \
      --opportunities logs/ETHUSDT/oos_ETHUSDT/opportunities.jsonl \
      --csv data/ETHUSDT_M15.csv --k 3
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from replay.timing_reconstructor import (  # noqa: E402
    load_candles, iter_jsonl, simulate_with_timing,
)

logger = logging.getLogger("EarlyInvalidationAB")


def _agg(rrs: list) -> dict:
    n = len(rrs)
    if n == 0:
        return {"n": 0, "expectancy_R": 0.0, "win_rate": 0.0,
                "winner_avg_R": 0.0, "loser_avg_R": 0.0, "profit_factor": 0.0}
    wins = [r for r in rrs if r > 0]
    losses = [r for r in rrs if r <= 0]
    gw = sum(wins)
    gl = abs(sum(losses))
    return {
        "n": n,
        "expectancy_R": round(sum(rrs) / n, 4),
        "win_rate": round(len(wins) / n, 4),
        "winner_avg_R": round(gw / len(wins), 4) if wins else 0.0,
        "loser_avg_R": round(sum(losses) / len(losses), 4) if losses else 0.0,
        "profit_factor": round(gw / gl, 4) if gl > 0 else (999.0 if gw > 0 else 0.0),
    }


def run(opp_path: Path, csv_path: Path, *, k: int, trail_mult: float,
        max_forward_candles: int) -> dict:
    ts, highs, lows, closes = load_candles(csv_path)
    idx = {t: i for i, t in enumerate(ts)}

    control_rr, treat_rr = [], []
    n_cut = 0
    saved = 0.0          # Σ(treat - natural) over cut eventual-losers (>=0 expected)
    forgone = 0.0        # Σ(natural - treat) over cut eventual-winners (>=0 magnitude)
    cut_losers = cut_winners = 0
    n = skipped = 0

    for rec in iter_jsonl(opp_path):
        t = str(rec.get("timestamp", ""))
        i = idx.get(t)
        if i is None:
            skipped += 1
            continue
        entry = float(rec["entry"]); sl = float(rec["sl"]); tp = float(rec["tp"])
        direction = rec["direction"]; rd = abs(entry - sl)
        if rd <= 0:
            skipped += 1
            continue
        end = min(i + 1 + int(max_forward_candles), len(highs))
        bars = [(highs[j], lows[j], closes[j]) for j in range(i + 1, end)]
        nat = simulate_with_timing(direction, entry, sl, tp, bars, rd, trail_mult=trail_mult)
        natural_rr = nat["rr_achieved"]
        dur = nat["duration_candles"]
        reached_by_k = nat["time_to_025R"] is not None and nat["time_to_025R"] <= k

        # Treatment: exit at candle K close iff the trade survived past K AND
        # never reached +0.25R by K. Otherwise the natural outcome stands.
        if dur > k and not reached_by_k:
            exit_idx = i + k
            if exit_idx < len(closes):
                ec = closes[exit_idx]
                treat = ((ec - entry) / rd if direction == "long" else (entry - ec) / rd)
                treat = round(treat, 4)
            else:
                treat = natural_rr
            n_cut += 1
            delta = treat - natural_rr
            if natural_rr > 0:
                cut_winners += 1
                forgone += -delta            # delta negative -> forgone positive
            else:
                cut_losers += 1
                saved += delta               # delta positive -> saved
        else:
            treat = natural_rr

        control_rr.append(natural_rr)
        treat_rr.append(treat)
        n += 1

    net = saved - forgone
    return {
        "schema": "early_invalidation_ab_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(opp_path),
        "params": {"k": k, "trail_mult": trail_mult,
                   "max_forward_candles": max_forward_candles,
                   "rule": "exit at candle K close if not +0.25R by K and survived to K"},
        "counts": {"n": n, "skipped": skipped, "n_cut": n_cut,
                   "cut_losers": cut_losers, "cut_winners": cut_winners},
        "headline_net_rr": {
            "rr_saved_on_cut_losers": round(saved, 2),
            "rr_forgone_on_cut_winners": round(forgone, 2),
            "net_rr_impact": round(net, 2),
        },
        "control": _agg(control_rr),    # natural (rule OFF)
        "treatment": _agg(treat_rr),    # rule ON
    }


def _print_report(inst: str, r: dict):
    c, t, h = r["control"], r["treatment"], r["headline_net_rr"]
    cc = r["counts"]
    print(f"\n================ {inst}  (k={r['params']['k']}, n={cc['n']}) ================")
    print("HEADLINE — Net RR impact:")
    print(f"  Cut eventual LOSERS : {cc['cut_losers']:>6}   RR saved   = {h['rr_saved_on_cut_losers']:>+10.2f}R")
    print(f"  Cut eventual WINNERS: {cc['cut_winners']:>6}   RR forgone = {-h['rr_forgone_on_cut_winners']:>+10.2f}R")
    print(f"  NET RR IMPACT                       = {h['net_rr_impact']:>+10.2f}R   (cut {cc['n_cut']}/{cc['n']})")
    print("Tier-1 / Tier-2 (control -> treatment):")
    print(f"  Expectancy_R   : {c['expectancy_R']:>+7.4f} -> {t['expectancy_R']:>+7.4f}")
    print(f"  Win rate       : {c['win_rate']:>7.3f} -> {t['win_rate']:>7.3f}")
    print(f"  Winner avg RR  : {c['winner_avg_R']:>+7.4f} -> {t['winner_avg_R']:>+7.4f}   (Tier-2 guard)")
    print(f"  Loser avg RR   : {c['loser_avg_R']:>+7.4f} -> {t['loser_avg_R']:>+7.4f}")
    print(f"  Profit factor  : {c['profit_factor']:>7.3f} -> {t['profit_factor']:>7.3f}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instrument", required=True)
    ap.add_argument("--opportunities", type=Path, default=None)
    ap.add_argument("--csv", type=Path, default=None)
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--k", type=int, default=3, help="candles-to-first-move checkpoint")
    ap.add_argument("--trail-mult", type=float, default=0.5)
    ap.add_argument("--max-forward-candles", type=int, default=40)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    opp = args.opportunities
    if opp is None:
        base = Path("logs") / args.instrument
        found = sorted(base.rglob("opportunities.jsonl")) if base.exists() else []
        if not found:
            ap.error(f"No opportunities.jsonl under {base}; pass --opportunities")
        opp = found[0]
    csv_path = args.csv or (Path("data") / f"{args.instrument}_M15.csv")
    out = args.output or (Path("results/analysis") /
                          f"early_invalidation_ab_{args.instrument}.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    r = run(opp, csv_path, k=args.k, trail_mult=args.trail_mult,
            max_forward_candles=args.max_forward_candles)
    out.write_text(json.dumps(r, indent=2), encoding="utf-8")
    _print_report(args.instrument, r)
    print(f"\nOUTPUT:early_invalidation_ab:{out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
