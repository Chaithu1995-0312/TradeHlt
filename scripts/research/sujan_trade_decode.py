"""Sujan trade decode — candidate levels for his 2026-09-25 XAU chart and live trade (READ-ONLY).

Context: "Trace Sujan docs" left his chart facts UNKNOWN. Drift log Record 7
(docs/research/sujan_identity_drift_log.md:40-61) relays his own words and one live trade:
red lines 4309.273 / 4255.613 called "WEEKLY OPEN"; BUY 0.4 @ 4276.30, SL 4269, TP 4299; chat
2026-09-25 21:02-21:36 (clock of the chat UNKNOWN; IST and UTC are both reported).

This script only lists CANDIDATES with their numeric distance. It picks none. Per
docs/governance/SUJAN_CRT_IDENTITY_EXTRACTION_SYSTEM.md every candidate is an UNVALIDATED proxy
until the human bridge approves it. His prices have 3 decimals and this MT5 feed has 2, so the
brokers differ and an exact match is not expected; a base-rate scan shows how many unrelated bars
also land within tolerance.

AUTHORITY: NONE. No SEM, no MC, no outcome numbers, no backtest.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

CORPUS = "data/mt5/XAUUSD_M15_2026-04-20_to_2026-10-06.csv"
OUT_DIR = REPO_ROOT / "userinvestigation" / "sujan_trade_decode"

# His numbers, as relayed (drift log Record 7 :42-45, :53).
RED_LINES = {"red_line_a": 4309.273, "red_line_b": 4255.613}
TRADE = {"entry": 4276.30, "sl": 4269.0, "tp": 4299.0}
CHAT_WALL = datetime(2026, 9, 25, 21, 29)          # trade screenshot time, clock UNKNOWN
CHAT_CLOCKS = {"IST": timedelta(hours=5, minutes=30), "UTC": timedelta(0)}
TOL = 0.50                                        # $ — broker-difference scale, not a fit
WEEKS = [datetime(2026, 9, 14), datetime(2026, 9, 21)]   # Mondays (calendar dates)


def _load():
    import pandas as pd
    from data_ingestion.corpus_store import load

    # Identity + configured-clock admission only, as the sibling xau_1009_prereg_* scripts do: the
    # full validate_dataset gate REJECTs this file on a filename parse ('XAUUSD_M15_2026-04-20_to'
    # read as the symbol), not on its bars.
    corpus = load(REPO_ROOT / CORPUS, "XAUUSD", sequence_check=False)
    df = corpus.frame()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["source_timestamp"] = pd.to_datetime(df["source_timestamp"])
    return corpus, df.sort_values("timestamp").reset_index(drop=True)


def _first_open_at_or_after(df, col, t):
    row = df[df[col] >= t].head(1)
    if row.empty:
        return None
    r = row.iloc[0]
    return {"bar_utc": str(r["timestamp"]), "bar_source": str(r["source_timestamp"]), "price": float(r["open"])}


def _dist(price):
    return {k: round(price - v, 3) for k, v in RED_LINES.items()}


def weekly_open_candidates(df, cal):
    out = []
    for monday in WEEKS:
        sunday = monday - timedelta(days=1)
        defs = {
            # fx_metals calendar: the week starts at the first wall-Monday 00:00 = Sunday 17:00 New York
            "calendar_week_open (Sun 17:00 NY)": ("timestamp", cal.to_utc(monday)),
            "broker_week_open (first bar of broker Monday)": ("source_timestamp", monday),
            "utc_monday_00:00_open": ("timestamp", monday),
            "utc_sunday_22:00_open": ("timestamp", sunday + timedelta(hours=22)),
        }
        for name, (col, t) in defs.items():
            hit = _first_open_at_or_after(df, col, t)
            if hit:
                out.append({"week_of": monday.date().isoformat(), "candidate": name, **hit,
                            "distance": _dist(hit["price"])})
        # every calendar day open that week (his "daily range acting as a weekly open key level")
        for d in range(5):
            day = monday + timedelta(days=d)
            hit = _first_open_at_or_after(df, "timestamp", cal.to_utc(day))
            if hit:
                out.append({"week_of": monday.date().isoformat(),
                            "candidate": f"calendar_day_open {day.date()}", **hit,
                            "distance": _dist(hit["price"])})
    return out


def daily_ranges(df, cal, start, end):
    w = df[(df["timestamp"] >= start) & (df["timestamp"] < end)].copy()
    w["wall_day"] = cal.wall_series(w["timestamp"]).dt.date
    g = w.groupby("wall_day").agg(open=("open", "first"), high=("high", "max"),
                                  low=("low", "min"), close=("close", "last"))
    return [{"day": str(k), **{c: float(v) for c, v in r.items()}, "distance_high": _dist(r["high"]),
             "distance_low": _dist(r["low"])} for k, r in g.iterrows()]


def base_rate(df, start, end):
    w = df[(df["timestamp"] >= start) & (df["timestamp"] < end)]
    rows = {}
    for k, v in RED_LINES.items():
        m = ((w[["open", "high", "low", "close"]] - v).abs() <= TOL).any(axis=1)
        rows[k] = {"bars_in_window": int(len(w)), "bars_with_any_ohlc_within_tol": int(m.sum()),
                   "examples_utc": [str(t) for t in w.loc[m, "timestamp"].head(8)]}
    return rows


def h1_around_trade(df, chat_utc):
    w = df[(df["timestamp"] >= chat_utc - timedelta(hours=14)) & (df["timestamp"] < chat_utc + timedelta(hours=2))].copy()
    w["h"] = w["timestamp"].dt.floor("h")
    h1 = w.groupby("h").agg(open=("open", "first"), high=("high", "max"),
                            low=("low", "min"), close=("close", "last"))
    bars = [{"h1_utc": str(k), **{c: float(v) for c, v in r.items()},
             "contains_entry": bool(r["low"] <= TRADE["entry"] <= r["high"])} for k, r in h1.iterrows()]
    pairs = []
    for c1, c2 in zip(bars, bars[1:]):
        inside = c1["low"] < c2["close"] < c1["high"]
        sweep = ("low" if c2["low"] < c1["low"] else "") + ("high" if c2["high"] > c1["high"] else "")
        if inside and sweep in ("low", "high"):
            pairs.append({"c1": c1["h1_utc"], "c2": c2["h1_utc"], "c2_swept": sweep,
                          "c1_low": c1["low"], "c1_high": c1["high"], "c2_low": c2["low"], "c2_high": c2["high"],
                          "sl_minus_c2_low": round(TRADE["sl"] - c2["low"], 2),
                          "tp_minus_c1_high": round(TRADE["tp"] - c1["high"], 2)})
    return {"h1_bars": bars, "c2_sweeps_closing_inside_c1": pairs}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(OUT_DIR))
    args = ap.parse_args()

    from features.market_calendar import calendar_for_instrument

    corpus, df = _load()
    cal = calendar_for_instrument("XAUUSD")
    win_start, win_end = datetime(2026, 9, 14), datetime(2026, 9, 27)
    n_win = int(((df["timestamp"] >= win_start) & (df["timestamp"] < win_end)).sum())
    print(f"corpus={corpus.path} identity={corpus.identity} rows={corpus.n_rows} "
          f"clock={corpus.clock.clock_id if corpus.clock else None} window_rows({win_start.date()}..{win_end.date()})={n_win}")

    result = {
        "authority": "NONE — candidates only, UNVALIDATED; human bridge decides",
        "provenance": corpus.provenance(),
        "his_numbers": {"red_lines": RED_LINES, "trade": TRADE, "chat_wall": str(CHAT_WALL)},
        "tolerance_usd": TOL,
        "weekly_open_candidates": weekly_open_candidates(df, cal),
        "calendar_daily_ranges": daily_ranges(df, cal, win_start, win_end),
        "base_rate_any_bar_within_tol": base_rate(df, win_start, win_end),
        "trade_window": {name: {"chat_utc": str(CHAT_WALL - off), **h1_around_trade(df, CHAT_WALL - off)}
                         for name, off in CHAT_CLOCKS.items()},
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "sujan_trade_decode.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("\nWeekly-open candidates (price, distance to red lines A=4309.273 / B=4255.613):")
    for c in result["weekly_open_candidates"]:
        d = c["distance"]
        flag = " <= tol" if min(abs(x) for x in d.values()) <= TOL else ""
        print(f"  {c['week_of']} {c['candidate']:<48} {c['price']:>9.2f}  A {d['red_line_a']:+8.2f}  B {d['red_line_b']:+8.2f}{flag}")
    print("\nBase rate (bars in window with any OHLC within tol):",
          {k: v["bars_with_any_ohlc_within_tol"] for k, v in result["base_rate_any_bar_within_tol"].items()},
          f"of {n_win}")
    for name, tw in result["trade_window"].items():
        print(f"\nChat clock = {name} -> chat at {tw['chat_utc']} UTC")
        for b in tw["h1_bars"]:
            print(f"  {b['h1_utc']}  O {b['open']:.2f} H {b['high']:.2f} L {b['low']:.2f} C {b['close']:.2f}"
                  f"{'  <- contains 4276.30' if b['contains_entry'] else ''}")
        for p in tw["c2_sweeps_closing_inside_c1"]:
            print(f"  C1 {p['c1']} / C2 {p['c2']} swept {p['c2_swept']}: SL-C2low {p['sl_minus_c2_low']:+.2f}, TP-C1high {p['tp_minus_c1_high']:+.2f}")
    print(f"\nwrote {out / 'sujan_trade_decode.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
