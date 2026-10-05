# -*- coding: utf-8 -*-
"""
mt5_history_probe.py — Program 12 Step 2a: how much history does the broker serve?

Read-only availability probe. For each logical symbol x timeframe it prints one row:
resolved broker symbol, earliest / latest bar, bar count, whether the count hit the
terminal's "Max bars in chart" cap (truncation), and a gap histogram. Per symbol it also
records the contract facts a cost model needs (digits, point, current spread, contract
size), recent tick availability, and the broker clock offset.

Writes no market data. Output: a printed table plus a JSON report (--out).

TIMESTAMPS: MT5 bar times are BROKER-SERVER time, not UTC (F-066). They are reported here
as server time. `server_minus_utc_h` estimates the offset from the latest tick, and is
only meaningful while the market is open (a stale tick reads as a larger offset).

Requires Windows, the MetaTrader5 Python package, and a running, logged-in terminal.

Usage:
    python scripts/data/mt5_history_probe.py
    python scripts/data/mt5_history_probe.py --symbols XAUUSD EURUSD --tf H4 D1
    python scripts/data/mt5_history_probe.py --out results/mt5_probe/mt5_history_probe.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from utils.console_safe import safe_print  # noqa: E402

# Logical symbol -> broker names to try, in order. Brokers suffix or rename symbols
# (XAUUSD.m, XAUUSDm, GOLD, USTEC ...); exact match wins, then prefix match.
CANDIDATES: dict[str, list[str]] = {
    "XAUUSD": ["XAUUSD", "GOLD"],
    "XAGUSD": ["XAGUSD", "SILVER"],
    "BTCUSD": ["BTCUSD", "BTCUSDT"],
    "EURUSD": ["EURUSD"],
    "GBPUSD": ["GBPUSD"],
    "USDJPY": ["USDJPY"],
    "AUDUSD": ["AUDUSD"],
    "US500": ["US500", "SPX500", "SP500", "USA500", "US500Cash"],
    "NAS100": ["NAS100", "USTEC", "US100", "NDX100", "USTECH"],
}

TF_SECONDS = {"M15": 900, "H1": 3600, "H4": 14400, "D1": 86400}
GAP_BUCKETS = (("1", 1, 1), ("2-4", 2, 4), ("5-24", 5, 24), (">24", 25, None))


def resolve_symbol(logical: str, broker_names: set[str]) -> tuple[str | None, list[str]]:
    """First exact candidate present; else, for the first candidate (in order) that prefixes
    any broker name, the shortest such name. Returns (chosen, every prefix match seen)."""
    cands = CANDIDATES.get(logical, [logical])
    upper = {n.upper(): n for n in broker_names}
    for cand in cands:
        if cand.upper() in upper:
            return upper[cand.upper()], []
    all_matches: list[str] = []
    chosen = None
    for cand in cands:
        hits = sorted((n for n in broker_names if n.upper().startswith(cand.upper())),
                      key=lambda n: (len(n), n))
        all_matches += [h for h in hits if h not in all_matches]
        if hits and chosen is None:
            chosen = hits[0]
    return chosen, all_matches


def _is_weekend_gap(t0: int, t1: int, step: int) -> bool:
    """True when every missing bar between t0 and t1 falls on Saturday/Sunday (server time)."""
    t = t0 + step
    while t < t1:
        if dt.datetime.fromtimestamp(t, tz=dt.timezone.utc).weekday() < 5:
            return False
        t += step
    return True


def gap_profile(times: list[int], step: int) -> dict:
    """Histogram of missing-bar runs; weekend runs counted separately. Top-5 largest others."""
    buckets = {name: 0 for name, _, _ in GAP_BUCKETS}
    weekend = 0
    largest: list[tuple[int, int, int]] = []
    for a, b in zip(times, times[1:]):
        missing = (b - a) // step - 1
        if missing < 1:
            continue
        if _is_weekend_gap(a, b, step):
            weekend += 1
            continue
        for name, lo, hi in GAP_BUCKETS:
            if missing >= lo and (hi is None or missing <= hi):
                buckets[name] += 1
                break
        largest.append((missing, a, b))
    largest.sort(reverse=True)

    def _ts(x: int) -> str:
        return dt.datetime.fromtimestamp(x, tz=dt.timezone.utc).strftime("%Y-%m-%d %H:%M")

    return {
        "weekend_gaps": weekend,
        "non_weekend_gaps_by_missing_bars": buckets,
        "largest_non_weekend": [
            {"missing_bars": m, "from_server": _ts(a), "to_server": _ts(b)} for m, a, b in largest[:5]
        ],
    }


def probe_series(mt5, symbol: str, tf: str, start: dt.datetime, now: dt.datetime, maxbars: int) -> dict:
    tf_const = getattr(mt5, f"TIMEFRAME_{tf}")
    rates = mt5.copy_rates_range(symbol, tf_const, start, now)
    source = "copy_rates_range"
    if rates is None or len(rates) == 0:
        err = mt5.last_error()
        rates = mt5.copy_rates_from_pos(symbol, tf_const, 0, maxbars)
        source = "copy_rates_from_pos"
        if rates is None or len(rates) == 0:
            return {"tf": tf, "bars": 0, "error": str(err), "source": source}
    times = [int(t) for t in rates["time"]]
    first = dt.datetime.fromtimestamp(times[0], tz=dt.timezone.utc)
    last = dt.datetime.fromtimestamp(times[-1], tz=dt.timezone.utc)
    return {
        "tf": tf,
        "bars": len(times),
        "source": source,
        "earliest_server": first.strftime("%Y-%m-%d %H:%M"),
        "latest_server": last.strftime("%Y-%m-%d %H:%M"),
        "years": round((times[-1] - times[0]) / (365.25 * 86400), 2),
        "hit_maxbars_cap": len(times) >= maxbars,
        "duplicate_times": len(times) - len(set(times)),
        "gaps": gap_profile(times, TF_SECONDS[tf]),
    }


def symbol_facts(mt5, symbol: str, now: dt.datetime) -> dict:
    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    ticks = mt5.copy_ticks_range(symbol, now - dt.timedelta(days=3), now, mt5.COPY_TICKS_ALL)
    facts = {
        "digits": getattr(info, "digits", None),
        "point": getattr(info, "point", None),
        "spread_points_now": getattr(info, "spread", None),
        "spread_float": getattr(info, "spread_float", None),
        "contract_size": getattr(info, "trade_contract_size", None),
        "currency_profit": getattr(info, "currency_profit", None),
        "ticks_last_3d": 0 if ticks is None else len(ticks),
        "server_minus_utc_h": None,
    }
    if tick is not None and getattr(tick, "time", 0):
        facts["server_minus_utc_h"] = round((tick.time - now.timestamp()) / 3600 * 2) / 2
    return facts


def _print_table(rows: list[dict]) -> None:
    head = (f"{'symbol':<8} {'broker':<12} {'tf':<4} {'bars':>8} {'years':>6} "
            f"{'earliest(server)':<17} {'latest(server)':<17} {'cap':<4} "
            f"{'gaps 1':>6} {'2-4':>5} {'5-24':>5} {'>24':>5} {'wknd':>5}")
    safe_print(head)
    safe_print("-" * len(head))
    for r in rows:
        if r.get("bars", 0) == 0:
            safe_print(f"{r['logical']:<8} {str(r.get('broker')):<12} {r.get('tf', '-'):<4} "
                       f"{0:>8}  NOT AVAILABLE  {r.get('error', '')}")
            continue
        g = r["gaps"]["non_weekend_gaps_by_missing_bars"]
        safe_print(
            f"{r['logical']:<8} {r['broker']:<12} {r['tf']:<4} {r['bars']:>8} {r['years']:>6} "
            f"{r['earliest_server']:<17} {r['latest_server']:<17} "
            f"{'YES' if r['hit_maxbars_cap'] else 'no':<4} "
            f"{g['1']:>6} {g['2-4']:>5} {g['5-24']:>5} {g['>24']:>5} {r['gaps']['weekend_gaps']:>5}"
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--symbols", nargs="+", default=list(CANDIDATES))
    ap.add_argument("--tf", nargs="+", default=["H1", "H4", "D1"], choices=sorted(TF_SECONDS))
    ap.add_argument("--start", default="1990-01-01", help="earliest date to request (YYYY-MM-DD)")
    ap.add_argument("--out", default="results/mt5_probe/mt5_history_probe.json")
    args = ap.parse_args(argv)

    try:
        import MetaTrader5 as mt5  # noqa: N813
    except ImportError:
        safe_print("MetaTrader5 package not installed. Run on the Windows machine: pip install MetaTrader5")
        return 2
    if not mt5.initialize():
        safe_print(f"MT5 initialize() failed: {mt5.last_error()}. Is the terminal running and logged in?")
        return 2

    try:
        term = mt5.terminal_info()
        acct = mt5.account_info()
        maxbars = int(getattr(term, "maxbars", 0) or 0)
        now = dt.datetime.now(tz=dt.timezone.utc).replace(microsecond=0)
        start = dt.datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
        broker_names = {s.name for s in (mt5.symbols_get() or [])}

        rows: list[dict] = []
        facts: dict[str, dict] = {}
        for logical in args.symbols:
            broker, alternatives = resolve_symbol(logical, broker_names)
            if broker is None:
                rows.append({"logical": logical, "broker": None, "tf": "-", "bars": 0,
                             "error": "symbol not offered by this broker"})
                continue
            mt5.symbol_select(broker, True)
            facts[logical] = {"broker": broker, "other_matches": alternatives,
                              **symbol_facts(mt5, broker, now)}
            for tf in args.tf:
                rows.append({"logical": logical, "broker": broker,
                             **probe_series(mt5, broker, tf, start, now, maxbars)})

        report = {
            "probe": "mt5_history_probe/1",
            "probed_at_utc": now.isoformat(),
            "terminal": {"company": getattr(term, "company", None), "name": getattr(term, "name", None),
                         "maxbars": maxbars, "build": getattr(term, "build", None)},
            "account_server": getattr(acct, "server", None),
            "timestamp_basis": "broker_server_time (F-066); not UTC",
            "requested_start": args.start,
            "symbols": facts,
            "series": rows,
        }
    finally:
        mt5.shutdown()

    _print_table(rows)
    safe_print(f"\nterminal maxbars = {maxbars}  (cap=YES means the count was truncated by this setting;"
               " raise Tools > Options > Charts > Max bars in chart and re-run)")
    for logical, f in facts.items():
        safe_print(f"{logical:<8} broker={f['broker']} spread_now={f['spread_points_now']}pt "
                   f"digits={f['digits']} ticks_3d={f['ticks_last_3d']} "
                   f"server-utc={f['server_minus_utc_h']}h")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    safe_print(f"\nreport -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
