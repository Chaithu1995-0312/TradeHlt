#!/usr/bin/env python
"""render_chart.py — CLI for INFRA-CPC-V1 Workstream A0 (own OHLC charts).

THIN WRAPPER ONLY (CLAUDE.md §3.3): every decision lives in `src/charts/`; this file
parses argv, calls the library, and prints. No business logic here.

Examples
--------
    # whole 2-year corpus at D1, CRT-coloured
    python scripts/analysis/render_chart.py --instrument XAUUSD --timeframe D1

    # H4 in quarterly tiles
    python scripts/analysis/render_chart.py --instrument XAUUSD --timeframe H4 \
        --bars-per-tile 390

    # a specific M15 window, bare bars, SVG
    python scripts/analysis/render_chart.py --instrument XAUUSD --timeframe M15 \
        --from 2026-05-01 --to 2026-05-21 --overlay none --format svg

Authority: descriptive only. Grants no economic claim, no G001 claim, no promotion
(INFRA-CPC-V1 §8, CLAUDE.md §6.5).
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from charts import chart_series as cs                            # noqa: E402
from charts import crt_overlay as co                             # noqa: E402
from charts import render as rd                                  # noqa: E402


def _ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"unparseable timestamp: {raw!r}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Render own-corpus OHLC charts (INFRA-CPC-V1 A0).")
    p.add_argument("--instrument", default="XAUUSD")
    p.add_argument("--timeframe", default="D1", choices=list(cs.TIMEFRAMES))
    p.add_argument("--csv", default=None,
                   help="base M15 corpus (default data/mt5/<INSTRUMENT>_M15.csv)")
    p.add_argument("--from", dest="start", type=_ts, default=None)
    p.add_argument("--to", dest="end", type=_ts, default=None)
    p.add_argument("--bars-per-tile", type=int, default=None,
                   help="split into tiles of N bars (default: one tile)")
    p.add_argument("--overlay", choices=("crt", "none"), default="crt")
    p.add_argument("--format", dest="fmt", choices=("png", "svg"), default="png")
    p.add_argument("--no-volume", action="store_true")
    p.add_argument("--out-dir", default=None)
    p.add_argument("--run-id", default=None)
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    inst = args.instrument.upper()
    csv_path = args.csv or f"data/mt5/{inst}_M15.csv"
    run_id = args.run_id or f"run_{datetime.now():%Y%m%d_%H%M%S}"
    out_dir = Path(args.out_dir or f"results/charts/{inst.lower()}_m15/{run_id}")

    print(f"[1/5] loading base M15 corpus: {csv_path}")
    base = cs.load_base_candles(csv_path, inst)
    print(f"      {len(base):,} bars  {base[0].timestamp} -> {base[-1].timestamp}")

    # CRT states are resolved on the M15 BASE (the engine runs on M15), then projected
    # onto the requested timeframe at bucket close.
    if args.overlay == "crt":
        print(f"[2/5] resolving CRT states under ACTIVE_VERSION "
              f"(runs the spine; first call is slow)")
        track = co.resolve_states(inst, csv_path, [b.timestamp for b in base])
        print(f"      {track.source}  transitions={track.transitions} "
              f"offset={track.offset}")
        if not track.resolved:
            print("      NOTE: bars will render uncoloured; the legend records why.")
        base_states, source = track.states, track.source
        base_transitions = track.transitions or None
    else:
        base_states = [cs.CRT_UNAVAILABLE] * len(base)
        source = "NONE"
        base_transitions = None

    print(f"[3/5] aggregating to {args.timeframe}")
    htf = cs.to_timeframe(base, args.timeframe)
    htf_states = cs.downsample_states(base, base_states, htf, args.timeframe)

    # `base_span` must track the SAME window as `htf`, otherwise the aliasing check
    # divides a full-corpus base count by a windowed bucket count and reports nonsense
    # (measured: H1 over a 3-month window claimed 32.3 base bars per bucket, vs 4).
    # BOTH sides of the dwell ratio must cover the same window: base bar count AND the
    # transition count. Windowing only one of them is what produced nonsense figures
    # (H1/3-month: 32.3 base bars per bucket vs the true 4; then a 1.11-bar dwell from a
    # full-corpus transition count over a windowed base).
    base_win = base
    base_states_win = base_states
    if args.start or args.end:
        htf, keep = cs.slice_window(htf, args.start, args.end)
        htf_states = [htf_states[i] for i in keep]
        base_win, keep_b = cs.slice_window(base, args.start, args.end)
        base_states_win = [base_states[i] for i in keep_b]
    base_span = len(base_win)
    if base_transitions is not None:
        base_transitions = sum(
            1 for i in range(1, len(base_states_win))
            if base_states_win[i] != base_states_win[i - 1]
        ) or None
    if not htf:
        print("ERROR: window selected zero bars", file=sys.stderr)
        return 2
    print(f"      {len(htf):,} {args.timeframe} bars")

    series = cs.ChartSeries(
        instrument=inst,
        timeframe=args.timeframe,
        bars=htf,
        crt_state=htf_states,
        crt_state_source=source,
        config_pin=cs.build_config_pin(inst, csv_path),
        # Base-series facts so the export can judge whether this timeframe undersamples
        # the CRT state process (see chart_series.crt_aliasing).
        base_bars=base_span,
        base_transitions=base_transitions,
    )

    print(f"[4/5] rendering ({args.fmt})")
    files = rd.render_tiles(series, out_dir, bars_per_tile=args.bars_per_tile,
                            fmt=args.fmt, show_volume=not args.no_volume)

    print(f"[5/5] writing export pack")
    cs.write_export(series, out_dir, chart_files=files)

    print(f"\nOK  {out_dir}")
    for f in files:
        print(f"    {f}")
    print("    series.csv  legend.json  config_pin.json  INDEX.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
