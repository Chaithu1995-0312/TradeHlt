"""
weekly_sequence_policy.py
One trade per week of a month, opened at the first bar's OPEN and closed at the last
bar's CLOSE (weekly start -> weekly end). The BUY/SELL sequence follows a policy that
sees only the policy's own previous completed weekly trade (forced-direction mode).

Policies: A reverse after loss, B continue after win, C opposite controls
(reverse after win, retain after loss), D1 always BUY, D2 always SELL, E strict alternation.
A branch a policy does not name keeps the previous direction. First week uses a seed.
Win = net R > 0. Costs reuse backtest_v2 (signed half-spread, SlippageModel).

Usage:
    python scripts/analysis/weekly_sequence_policy.py --csv data/XAUUSD_H1.csv \
        --month 2025-07 --out results/weekly_sequence_2025_07
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics as st
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from config_layer.crt_engine_v2 import Direction  # noqa: E402
from runtime.backtest_v2 import (  # noqa: E402
    BacktestConfig, CandleLoader, SlippageModel, signed_half_spread,
)

RISK_DAYS = 14   # trailing complete days used for the 1R unit (mean daily high-low)
ATR_BARS = 14


def month_weeks(bars: list, month: str) -> list[list]:
    """Group the month's bars by ISO week (Mon-based); a week is bounded by the month."""
    y, m = (int(x) for x in month.split("-"))
    weeks: dict = {}
    for b in bars:
        t = b.timestamp
        if t.year == y and t.month == m:
            weeks.setdefault(t.isocalendar()[:2], []).append(b)
    return [weeks[k] for k in sorted(weeks)]


def next_direction(policy: str, prev_dir: str | None, prev_net: float | None, week_idx: int, seed: str) -> str:
    """BUY/SELL for the next week. prev_* describe the previous completed weekly trade."""
    other = {"BUY": "SELL", "SELL": "BUY"}
    if policy == "D1":
        return "BUY"
    if policy == "D2":
        return "SELL"
    if policy == "E":
        return seed if week_idx % 2 == 0 else other[seed]
    if prev_dir is None:
        return seed
    win = prev_net > 0
    if policy == "A":
        return prev_dir if win else other[prev_dir]
    if policy == "B":
        return prev_dir          # continue after win; unnamed branch (loss) keeps direction
    if policy == "C":
        return other[prev_dir] if win else prev_dir
    raise ValueError(policy)


def atr_before(bars: list, idx: int, n: int = ATR_BARS) -> float:
    lo = max(1, idx - n + 1)
    trs = [max(bars[i].high - bars[i].low, abs(bars[i].high - bars[i - 1].close), abs(bars[i].low - bars[i - 1].close))
           for i in range(lo, idx + 1)]
    return sum(trs) / len(trs) if trs else 0.0


def risk_unit(bars: list, first_idx: int) -> float:
    """Mean daily high-low range of the RISK_DAYS most recent complete days before the week."""
    d0 = bars[first_idx].timestamp.date()
    days: dict = {}
    for b in bars[:first_idx]:
        d = b.timestamp.date()
        if d < d0:
            lo, hi = days.get(d, (b.low, b.high))
            days[d] = (min(lo, b.low), max(hi, b.high))
    recent = [days[d] for d in sorted(days)][-RISK_DAYS:]
    return st.mean(h - l for l, h in recent)


def trade_week(bars: list, week: list, direction: str, cfg, wk: int) -> dict:
    first_idx = bars.index(week[0])
    last_idx = bars.index(week[-1])
    entry_raw, exit_raw = week[0].open, week[-1].close
    atr_e, atr_x = atr_before(bars, first_idx), atr_before(bars, last_idx)
    d = Direction.LONG if direction == "BUY" else Direction.SHORT
    # same slip magnitudes for BUY and SELL in a given week (seed per week), sign by direction
    sl = SlippageModel(cfg.slippage_atr_fraction, seed=cfg.slippage_seed + wk)
    e_slip, x_slip = sl.entry_slip(atr_e, d), sl.exit_slip(atr_x, d)
    sh_e = week[0].open * cfg.simulated_spread_pct / 2
    sh_x = week[-1].close * cfg.simulated_spread_pct / 2
    entry_fill = entry_raw + e_slip + signed_half_spread(d, sh_e)
    exit_fill = exit_raw + x_slip - signed_half_spread(d, sh_x)
    sign = 1.0 if direction == "BUY" else -1.0
    unit = risk_unit(bars, first_idx)
    raw = sign * (exit_raw - entry_raw) / unit
    net = sign * (exit_fill - entry_fill) / unit
    hi, lo = max(b.high for b in week), min(b.low for b in week)
    mae = ((entry_raw - lo) if direction == "BUY" else (hi - entry_raw)) / unit
    return {
        "week": wk + 1, "start": week[0].timestamp.isoformat(), "end": week[-1].timestamp.isoformat(),
        "dir": direction, "entry_raw": round(entry_raw, 2), "exit_raw": round(exit_raw, 2),
        "entry_fill": round(entry_fill, 3), "exit_fill": round(exit_fill, 3), "unit": round(unit, 2),
        "raw_r": round(raw, 4), "net_r": round(net, 4), "cost_r": round(raw - net, 4), "mae_r": round(mae, 3),
    }


def run_sequence(bars: list, weeks: list, cfg, policy: str, seed: str) -> list[dict]:
    out, prev_dir, prev_net = [], None, None
    for i, wk in enumerate(weeks):
        dirn = next_direction(policy, prev_dir, prev_net, i, seed)
        t = trade_week(bars, wk, dirn, cfg, i)
        out.append(t)
        prev_dir, prev_net = dirn, t["net_r"]
    return out


def metrics(trades: list[dict]) -> dict:
    net = [t["net_r"] for t in trades]
    wins, losses = [v for v in net if v > 0], [v for v in net if v <= 0]
    peak = cum = dd = 0.0
    for v in net:
        cum += v
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    return {
        "n": len(net), "total_r": round(sum(net), 3), "exp": round(st.mean(net), 3),
        "pf": ("inf" if wins and not losses else round(sum(wins) / abs(sum(losses)), 2) if wins else 0.0),
        "wr": round(len(wins) / len(net), 2), "dd": round(dd, 2),
        "cost_r": round(st.mean(t["cost_r"] for t in trades), 3),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--month", required=True, help="YYYY-MM")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    bars = list(CandleLoader(a.csv, "XAUUSD").stream())
    weeks = month_weeks(bars, a.month)
    cfg = BacktestConfig.from_prod_config(instrument="XAUUSD", pip_size=0.01)
    runs = [("A", "BUY"), ("A", "SELL"), ("B", "BUY"), ("B", "SELL"), ("C", "BUY"), ("C", "SELL"),
            ("D1", "BUY"), ("D2", "SELL"), ("E", "BUY"), ("E", "SELL")]
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    ledger, summary = [], {}
    for pol, seed in runs:
        label = f"{pol}({seed}-seed)" if pol in ("A", "B", "C", "E") else pol
        tr = run_sequence(bars, weeks, cfg, pol, seed)
        eq = 0.0
        for t in tr:
            eq += t["net_r"]
            ledger.append({"policy": label, **t, "equity_r": round(eq, 4)})
        summary[label] = {"seq": "".join("B" if t["dir"] == "BUY" else "S" for t in tr), **metrics(tr)}
    with open(out / "ledger.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(ledger[0]))
        w.writeheader(); w.writerows(ledger)
    (out / "summary.json").write_text(json.dumps({"weeks": [[w_[0].timestamp.isoformat(), w_[-1].timestamp.isoformat()] for w_ in weeks],
                                                  "summary": summary}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
