#!/usr/bin/env python
"""
CLI: Fetch FX/metals OHLCV from MT5 across the native timeframe ladder, then HARD-STOP
strict-verify each file — "can't train on inconsistent data."

For every (symbol x timeframe) it:
  1. fetches via MT5CandleFetcher -> data/{SYMBOL}_{TF}.csv (reuses the proven fetch path), then
  2. runs the STRICT, zero-tolerance, session-aware integrity gate
     (dataset_integrity.validate_dataset with the `strict_fetch` cfg_override): ANY *tradable*
     missing bar (weekends / daily rollover / reviewed holidays excluded) or any OHLCV defect
     (NaN / missing / negative volume / OHLC inconsistency, enforced at L1) is a HARD FAILURE.

On failure the file is QUARANTINED to data/_rejected/ (so it can never be silently trained on),
the exact missing TRADABLE timestamps are printed (so genuine corruption is distinguishable from a
legitimate holiday closure — add real holidays to `dataset_integrity.session_calendar.holidays`
and re-run), and the process exits non-zero.

Requirements
------------
  * pip install MetaTrader5
  * The MetaTrader 5 desktop terminal RUNNING and LOGGED IN (free demo is fine).

Usage
-----
    python scripts/data/fetch_and_verify_mt5.py
    python scripts/data/fetch_and_verify_mt5.py --symbols EURUSD,XAUUSD --timeframes M5,M15
    python scripts/data/fetch_and_verify_mt5.py --symbol-map XAUUSD=GOLD --start 2024-05-22 --end 2026-05-22
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import timedelta
from pathlib import Path

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parent.parent.parent
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from config_layer.production_config import get_prod_section          # noqa: E402
from data_ingestion.dataset_integrity import (                        # noqa: E402
    _TF_MINUTES, _is_tradable, _parse_known_gaps, _stream_candles, classify_market,
    validate_dataset,
)
from data_ingestion.session_autoderive import (                       # noqa: E402
    derive_weekly_mask, is_tradable_by_mask,
)
from inout.mt5_candle_fetcher import MT5CandleFetcher, MT5FetcherConfig  # noqa: E402
from utils.console_safe import safe_print                             # noqa: E402

# FX + metals (user decision). MT5 crypto is a SEPARATE, provider-tagged corpus under data/mt5/
# (kept distinct from the Binance data/{SYMBOL}_M15.csv); discover broker crypto with --discover-crypto.
DEFAULT_SYMBOLS = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "EURCAD", "XAUUSD"]
DEFAULT_TIMEFRAMES = ["M5", "M15", "H1", "H4"]
DEFAULT_OUT = "data/mt5"                 # provider-differentiated MT5 corpus root
# Match the broker's "Crypto\\..." group PATH only — name substrings (BNB/SOL/LTC/XRP) also
# appear in equity tickers (ABNB.NAS, LTC.NYSE), so path-matching is the precise filter.
CRYPTO_SUBSTRINGS = ["CRYPTO"]
RECENT_BARS = 200_000                    # max-recent fallback depth (M5 isn't cached 2yr back)
# Match the existing 2yr on-disk window (CLI-overridable).
DEFAULT_START = "2024-05-22"
DEFAULT_END = "2026-05-22"


def _strict_override(cfg: dict) -> dict:
    """The zero-tolerance thresholds from config (config-first; no literals here)."""
    sf = cfg.get("strict_fetch")
    if not sf:
        raise SystemExit("dataset_integrity.strict_fetch missing from the active config.")
    return {k: v for k, v in sf.items() if k != "_doc"}


def _missing_tradable(path: Path, symbol: str, tf: str, cfg: dict, override: dict,
                      *, limit: int = 50) -> list[str]:
    """The first `limit` missing TRADABLE timestamps in `path` — so a reviewer can tell a real
    hole from a legitimate closure. Uses the SAME tradability model as the gate's verdict: the
    auto-derived weekly mask (when tradability_mode=autoderive) + holidays, else the config
    calendar. (Without this alignment the printout would show session slots the autoderive gate
    does not actually flag.)"""
    holidays = set(cfg.get("session_calendar", {}).get("holidays", []))
    ts_all = [t for _l, t, *_ in _stream_candles(path)]
    bar = _TF_MINUTES.get((tf or "").upper()) or int(cfg.get("default_bar_minutes", 15))
    step = timedelta(minutes=bar)

    known_gaps = _parse_known_gaps(cfg.get("session_calendar", {}).get("known_gaps", []), symbol)

    def _accepted(t):   # reviewed broker-outage window → not "missing"
        return any(lo <= t < hi for lo, hi in known_gaps)

    if override.get("tradability_mode") == "autoderive":
        mask = derive_weekly_mask(ts_all, presence_min=float(override.get("autoderive_presence_min", 0.5)))
        tradable = lambda t: (not _accepted(t)) and is_tradable_by_mask(t, mask, holidays)  # noqa: E731
    else:
        sc = {**cfg.get("session_calendar", {}), "holidays": holidays}
        market = classify_market(symbol, cfg)
        tradable = lambda t: (not _accepted(t)) and _is_tradable(t, market, sc)             # noqa: E731

    out: list[str] = []
    prev = None
    for ts in ts_all:
        if prev is not None and (ts - prev) > step:
            t = prev + step
            while t < ts and len(out) < limit:
                if tradable(t):
                    out.append(t.isoformat())
                t += step
        prev = ts
        if len(out) >= limit:
            break
    return out


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fetch FX/metals from MT5 across timeframes + STRICT zero-tolerance gap gate",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS),
                   help="Comma-separated canonical pairs (default: FX majors + XAUUSD).")
    p.add_argument("--timeframes", default=",".join(DEFAULT_TIMEFRAMES),
                   help="Comma-separated timeframes (default: M5,M15,H1,H4).")
    p.add_argument("--symbol-map", default="",
                   help="Broker-symbol overrides, e.g. 'XAUUSD=GOLD,EURUSD=EURUSD.r'.")
    p.add_argument("--discover-crypto", action="store_true",
                   help="Auto-discover the broker's crypto symbols (by name/group path) and add them.")
    p.add_argument("--recent-bars", type=int, default=RECENT_BARS,
                   help="Max-recent fallback depth when the broker has no 2yr cache (e.g. M5).")
    p.add_argument("--start", default=DEFAULT_START, metavar="YYYY-MM-DD", help="UTC inclusive")
    p.add_argument("--end", default=DEFAULT_END, metavar="YYYY-MM-DD", help="UTC exclusive")
    p.add_argument("--out", default=DEFAULT_OUT, metavar="DIR",
                   help=f"Provider corpus root (default: {DEFAULT_OUT}).")
    p.add_argument("--quarantine", default="data/mt5/_rejected", metavar="DIR")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    timeframes = [t.strip().upper() for t in args.timeframes.split(",") if t.strip()]
    sym_map = dict(kv.split("=", 1) for kv in args.symbol_map.split(",") if "=" in kv)

    cfg = get_prod_section("dataset_integrity")
    override = _strict_override(cfg)
    quarantine = Path(args.quarantine)

    if args.discover_crypto:
        crypto = MT5CandleFetcher.discover_symbols(CRYPTO_SUBSTRINGS)
        safe_print(f"discovered broker crypto symbols ({len(crypto)}): {crypto}")
        symbols = symbols + [c for c in crypto if c not in symbols]

    safe_print(f"STRICT fetch+verify — {symbols} x {timeframes} [{args.start} .. {args.end})")
    safe_print(f"  provider corpus: {args.out} | autoderive session + reviewed holidays\n")

    fetched: list[tuple[str, str, str]] = []   # (pair, tf, decision)
    failures: list[str] = []

    for pair in symbols:
        for tf in timeframes:
            broker = sym_map.get(pair, pair)
            section = {"symbol": broker.upper(), "timeframe": tf, "start_date": args.start,
                       "end_date": args.end, "output_dir": args.out, "out_name": pair}
            try:
                fetcher = MT5CandleFetcher(MT5FetcherConfig.from_section(section))
                try:
                    path = fetcher.fetch()
                except RuntimeError as exc:
                    if "0 candles" in str(exc):
                        safe_print(f"  [range-empty] {pair} {tf}: no 2yr cache; max-recent fallback "
                                   f"(copy_rates_from_pos, {args.recent_bars} bars) ...")
                        path = fetcher.fetch_recent(args.recent_bars)
                    else:
                        raise
            except (KeyError, ValueError, RuntimeError) as exc:
                safe_print(f"  [FETCH-FAIL] {pair} {tf}: {exc}")
                failures.append(f"{pair}_{tf} (fetch: {exc})")
                continue

            # STRICT verify (do not raise here — we want to quarantine + report, then exit non-zero).
            rep = validate_dataset(str(path), instrument=pair, raise_on_fail=False,
                                   cfg_override=override)
            decision = rep.get("decision")
            fetched.append((pair, tf, decision))
            if decision == "REJECT":
                missing = _missing_tradable(Path(path), pair, tf, cfg, override)
                safe_print(f"  [REJECT] {pair} {tf}: {'; '.join(rep.get('hard_failures', []))}")
                if missing:
                    safe_print(f"           first missing tradable bars: {missing[:12]}"
                               f"{' ...' if len(missing) >= 12 else ''}")
                quarantine.mkdir(parents=True, exist_ok=True)
                dest = quarantine / Path(path).name
                shutil.move(str(path), str(dest))
                safe_print(f"           quarantined -> {dest}")
                failures.append(f"{pair}_{tf}")
            else:
                safe_print(f"  [{decision}] {pair} {tf}: {rep.get('rows')} rows OK")

    safe_print(f"\nfetched+verified: {len(fetched)} | failures: {len(failures)}")
    if failures:
        safe_print(f"HARD STOP — inconsistent/failed: {failures}")
        safe_print("Quarantined files are in "
                   f"{quarantine}; review missing timestamps. If they are genuine market "
                   "holidays, add the dates to dataset_integrity.session_calendar.holidays and "
                   "re-run; otherwise the data is corrupt and must not be used.")
        return 1
    safe_print("ALL CLEAN — every timeframe passed the strict gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
