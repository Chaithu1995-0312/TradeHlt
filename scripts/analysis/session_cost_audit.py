"""session_cost_audit.py — read-only session-level cost breakdown.

Reads a BNBUSDT_trades.csv produced by backtest_v2.py and prints
per-session gross vs net PnL, cost drag, WR, and avg RR so you can
compare LONDON vs NEWYORK cost load.

Usage:
    python scripts/analysis/session_cost_audit.py \
        results/roi_baseline/run_20260529_161443_BNBUSDT/BNBUSDT_trades.csv

No dependencies beyond stdlib + csv.
"""

import csv
import sys
from collections import defaultdict
from pathlib import Path


def load_trades(path: str) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


# Session windows (UTC hour ranges) — mirror crt_engine session_windows.
# The trades CSV `session` column is numeric/unreliable, so we derive the
# session label from hour_of_day, the same way the engine's _session() does.
_SESSION_WINDOWS = {
    "LONDON":  (7, 10),
    "NEWYORK": (13, 16),
    "ASIA":    (0, 3),
}


def _session_from_hour(hour: int) -> str:
    for name, (start, end) in _SESSION_WINDOWS.items():
        if start <= hour <= end:
            return name
    return "OFF_SESSION"


def analyse(trades: list[dict]) -> dict:
    sessions: dict[str, dict] = defaultdict(lambda: {
        "trades": 0, "wins": 0, "losses": 0,
        "gross_rr": 0.0, "net_rr": 0.0,
        "slippage_pips": 0.0, "spread_pips": 0.0,
    })

    for t in trades:
        try:
            hour = int(float(t.get("hour_of_day", -1)))
        except (TypeError, ValueError):
            hour = -1
        sess = _session_from_hour(hour) if hour >= 0 else "UNKNOWN"
        s = sessions[sess]
        s["trades"] += 1

        net = float(t.get("pnl_rr_net", 0) or 0)
        raw = float(t.get("pnl_rr_raw", 0) or 0)
        slip = float(t.get("slippage_pips", 0) or 0)
        sprd = float(t.get("spread_pips", 0) or 0)

        s["gross_rr"]      += raw
        s["net_rr"]        += net
        s["slippage_pips"] += slip
        s["spread_pips"]   += sprd
        if net > 0:
            s["wins"] += 1
        else:
            s["losses"] += 1

    return dict(sessions)


def print_report(stats: dict, csv_path: str) -> None:
    W = 65
    print("=" * W)
    print(f"  SESSION COST AUDIT  --  {Path(csv_path).name}")
    print("=" * W)
    fmt = (
        "{:<14}  {:>6}  {:>5}  {:>7}  {:>7}  {:>7}  {:>8}  {:>8}"
    )
    print(fmt.format(
        "SESSION", "TRADES", "WR", "GrossR", "NetR",
        "Drag%", "SlipPips", "SprdPips",
    ))
    print("-" * W)
    for sess, s in sorted(stats.items()):
        n   = s["trades"]
        wr  = s["wins"] / n if n else 0
        gross = s["gross_rr"]
        net   = s["net_rr"]
        drag  = (gross - net) / abs(gross) if gross != 0 else 0
        slip  = s["slippage_pips"]
        sprd  = s["spread_pips"]
        print(fmt.format(
            sess, n, f"{wr:.0%}",
            f"{gross:+.3f}R", f"{net:+.3f}R",
            f"{drag:.0%}",
            f"{slip:,.0f}", f"{sprd:,.0f}",
        ))
    print("=" * W)
    # Totals
    all_trades = sum(s["trades"] for s in stats.values())
    all_gross  = sum(s["gross_rr"] for s in stats.values())
    all_net    = sum(s["net_rr"] for s in stats.values())
    all_drag   = (all_gross - all_net) / abs(all_gross) if all_gross != 0 else 0
    all_slip   = sum(s["slippage_pips"] for s in stats.values())
    all_sprd   = sum(s["spread_pips"] for s in stats.values())
    print(fmt.format(
        "TOTAL", all_trades, "",
        f"{all_gross:+.3f}R", f"{all_net:+.3f}R",
        f"{all_drag:.0%}",
        f"{all_slip:,.0f}", f"{all_sprd:,.0f}",
    ))
    print()
    print("Interpretation guide:")
    print("  Drag% > 20% in a session -> spread/slip materially erodes edge there.")
    print("  SlipPips >> SprdPips -> volatile fills; consider tighter ATR fraction.")
    print("  SprdPips >> SlipPips -> illiquid session; consider session filter.")


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <BNBUSDT_trades.csv>")
        sys.exit(1)
    path = sys.argv[1]
    if not Path(path).exists():
        print(f"ERROR: file not found: {path}")
        sys.exit(1)
    trades = load_trades(path)
    stats  = analyse(trades)
    print_report(stats, path)


if __name__ == "__main__":
    main()
