#!/usr/bin/env python3
"""Measure an OHLCV corpus's UTC offset against TradingView's declared-UTC series.

`scripts/governance/review_ohlcv_clocks.py` returns INCONCLUSIVE on MT5 corpora for a
stated reason: "no declared-UTC reference corpus - DST and offset are not measurable
from a single series". This supplies that missing reference. TradingView served in
`Etc/UTC` is the second series; the offset is whichever hour shift makes the two OHLC
streams agree.

Output is EVIDENCE ONLY. It never touches the clock registry and never sets
`user_reviewed` — declaring a clock stays a human act, via review_ohlcv_clocks.py.

Usage:
    python tools/tv_forensic/measure_corpus_clock.py --csv data/mt5/XAUUSD_M15.csv
    python tools/tv_forensic/measure_corpus_clock.py --csv data/mt5/XAUUSD_M15.csv \
        --anchor-date 2026-05-20 --symbol OANDA:XAUUSD
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

import engine_data as ed
import ui_fallback as ui
from tv_bridge import TVBridge

CHART = "https://www.tradingview.com/chart/?symbol={symbol}&interval=15"
PAD = timedelta(hours=14)  # wide enough that the true window is inside for any +/-12h offset


# The anonymous TradingView feed serves ~5,000 bars per resolution, so M15 only
# reaches ~52 days back. Offsets are whole hours, so a coarser resolution resolves
# the same answer and reaches much further: H1 ~208 days, H4 ~833 days.
TF_MINUTES = {"15": 15, "60": 60, "240": 240}
TF_REACH_DAYS = {"15": 45, "60": 190, "240": 750}


def choose_timeframe(anchor: datetime) -> str:
    age_days = (datetime.utcnow() - anchor).days
    for tf in ("15", "60", "240"):
        if age_days <= TF_REACH_DAYS[tf]:
            return tf
    return "240"


def aggregate(bars: dict, minutes: int) -> dict:
    """Roll M15 bars up to `minutes` buckets: first open, max high, min low, last close.

    Bucketing is done on the corpus's own clock. Since a broker offset is a whole
    number of hours, a broker-local hour bucket maps exactly onto a UTC hour bucket,
    so the comparison stays valid without knowing the offset first.
    """
    if minutes == 15:
        return bars
    buckets: dict[datetime, list] = {}
    for ts in sorted(bars):
        b = bars[ts]
        key = ts.replace(minute=(ts.minute // minutes) * minutes if minutes < 60 else 0)
        if minutes >= 60:
            key = ts.replace(minute=0, hour=(ts.hour // (minutes // 60)) * (minutes // 60))
        buckets.setdefault(key, []).append(b)
    out = {}
    for key, group in buckets.items():
        out[key] = ed.Bar(
            key, group[0].o, max(g.h for g in group),
            min(g.l for g in group), group[-1].c,
            sum(g.v for g in group),
        )
    return out


def pick_anchors(bars: dict, around: datetime, count: int, step_min: int) -> list[datetime]:
    """Consecutive bars near `around`, skipping any the corpus does not have."""
    out, cursor = [], around
    for _ in range(count * 60):
        if len(out) >= count:
            break
        if cursor in bars:
            out.append(cursor)
        cursor += timedelta(minutes=step_min)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Measure a corpus's UTC offset against TradingView.")
    p.add_argument("--csv", required=True)
    p.add_argument("--symbol", default="OANDA:XAUUSD")
    p.add_argument("--anchor-date", default=None,
                   help="YYYY-MM-DD inside the corpus. Default: 2 days before its last bar.")
    p.add_argument("--anchors", type=int, default=8)
    p.add_argument("--tf", choices=["15","60","240"], default=None,
                   help="Comparison timeframe. Default: auto by how far back the anchor is.")
    p.add_argument("--headed", action="store_true")
    args = p.parse_args(argv)

    bars = ed.load_engine_bars(args.csv)
    stamps = sorted(bars)
    print(f"corpus   : {args.csv}")
    print(f"bars     : {len(bars)}  ({stamps[0]} .. {stamps[-1]})")

    if args.anchor_date:
        around = datetime.strptime(args.anchor_date, "%Y-%m-%d").replace(hour=12)
    else:
        around = (stamps[-1] - timedelta(days=2)).replace(hour=12, minute=0)

    tf = args.tf or choose_timeframe(around)
    step = TF_MINUTES[tf]
    cmp_bars = aggregate(bars, step)
    print(f"timeframe: {tf}m  ({'native' if tf == '15' else 'corpus rolled up from M15'}) "
          f"- chosen so ~5,000 TradingView bars reach {around:%Y-%m-%d}")

    anchors = pick_anchors(cmp_bars, around, args.anchors, step)
    if len(anchors) < 2:
        print(f"ERROR: fewer than 2 corpus bars near {around}", file=sys.stderr)
        return 2
    print(f"anchors  : {len(anchors)} bars from {anchors[0]} to {anchors[-1]}")
    print(f"reference: {args.symbol} served in Etc/UTC\n")

    lo = int((anchors[0] - PAD).replace(tzinfo=timezone.utc).timestamp())
    hi = int((anchors[-1] + PAD).replace(tzinfo=timezone.utc).timestamp())

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080},
                                  locale="en-US", timezone_id="UTC", device_scale_factor=1)
        page = ctx.new_page()
        page.set_default_timeout(30000)
        page.goto(CHART.format(symbol=args.symbol), wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(3500)
        ui.dismiss_overlays(page)
        ui.wait_for_chart(page, timeout_ms=60000)
        ui.hide_watchlist(page)

        bridge = TVBridge(page)
        if not bridge.available():
            print("ERROR: window.TradingViewApi not exposed", file=sys.stderr)
            return 3

        bridge.setup(args.symbol, tf)
        print("loading TradingView history back to the anchor window "
              "(this is the slow part) ...")
        hist = bridge.load_history(lo, max_pulls=400)
        print(f"  loaded {hist['size']} bars back to "
              f"{datetime.fromtimestamp(hist['first'], tz=timezone.utc):%Y-%m-%d %H:%M} UTC "
              f"in {hist['pulls']} pulls")
        bridge.frame(lo, hi)
        snap = bridge.snapshot()
        browser.close()

    result = ed.resolve_offset(cmp_bars, snap.bars_by_epoch, anchors)
    print()
    print(f"RESOLVED OFFSET : UTC{result.hours:+d}")
    print(f"  mean |err|    : {result.error:.4f}  over {len(result.anchors)} anchors")
    # D-2 (semantic + screenshot layer review, 2026-08-16): runner_up_hours/error
    # are None with only one scored candidate; `:+d`/`:.4f` on None raised
    # TypeError here instead of printing the (accurate) "no runner-up" state.
    if result.runner_up_hours is not None:
        print(f"  runner-up     : UTC{result.runner_up_hours:+d} @ {result.runner_up_error:.4f}")
    else:
        print("  runner-up     : none (only one candidate offset produced any match)")
    print(f"  decisive      : {result.decisive}  "
          f"(needs winner to beat runner-up {ed.DECISIVE_RATIO}x and err <= {ed.MATCH_TOLERANCE})")
    print()
    print("  ranked candidates:")
    for row in result.ranked[:5]:
        print(f"    UTC{row['offset_hours']:+3d}  mean|err| {row['mean_abs_error']:10.4f}  "
              f"anchors {row['anchors_matched']}")
    print()
    print("EVIDENCE ONLY. This wrote nothing. A human declares the clock:")
    print(f"  python scripts/governance/review_ohlcv_clocks.py --review {args.csv} \\")
    print('      --timezone <UTC|MT5_SERVER_NY_DST|IANA zone> --reviewed-by "<you>"')
    print()
    print("NOTE: a single anchor window measures the offset AT THAT DATE only. It cannot")
    print("distinguish a fixed offset from a DST-tracking one — that needs a second window")
    print("in the opposite season, or the standing F-066 finding.")

    Path("results").mkdir(exist_ok=True)
    out = Path("results") / "corpus_clock_evidence.json"
    prior = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    prior[f"{args.csv}@{anchors[0]:%Y-%m-%d}"] = {
        "corpus": args.csv,
        "reference": args.symbol,
        "anchor_window": [str(anchors[0]), str(anchors[-1])],
        "measured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **result.as_dict(),
    }
    out.write_text(json.dumps(prior, indent=2), encoding="utf-8")
    print(f"\nappended evidence -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
