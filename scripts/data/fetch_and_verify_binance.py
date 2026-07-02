#!/usr/bin/env python
"""
CLI: Fetch crypto-major OHLCV from Binance (CCXT) across the M5/M15/H1/H4 ladder, then HARD-STOP
strict-verify each — the crypto counterpart of fetch_and_verify_mt5.py.

Chosen over the MT5 crypto CFDs because those have structural gaps up to ~551 bars (late listings,
halts); Binance spot is 24x7 and serves full-depth M5, so the strict zero-tolerance gate is
actually satisfiable. Provider-differentiated corpus: writes data/binance/{SYMBOL}_{TF}.csv
(separate from the MT5 corpus in data/mt5/ and from the legacy data/{SYMBOL}_M15.csv).

Each (symbol x timeframe): paginated CCXT fetch -> canonical CSV -> validate_dataset with the
`strict_fetch` zero-tolerance + autoderive override. On failure: print the exact missing tradable
timestamps, QUARANTINE to data/binance/_rejected/, exit non-zero.

Requirements: pip install ccxt (no API key needed for public OHLCV).

Usage:
    python scripts/data/fetch_and_verify_binance.py
    python scripts/data/fetch_and_verify_binance.py --symbols BTCUSDT,ETHUSDT --timeframes M5,M15
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time as _time
from datetime import datetime, timedelta, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from data_ingestion.dataset_integrity import (                       # noqa: E402
    _TF_MINUTES, _is_tradable, _parse_known_gaps, _stream_candles, classify_market,
    validate_dataset,
)
from data_ingestion.session_autoderive import (                      # noqa: E402
    derive_weekly_mask, is_tradable_by_mask,
)
from config_layer.production_config import get_prod_section           # noqa: E402
from utils.console_safe import safe_print                            # noqa: E402

# crypto majors matching the legacy Binance corpus (BTC/ETH/SOL/BNB majors + XRP/DOGE)
SYMBOLS = {
    "BTCUSDT": "BTC/USDT", "ETHUSDT": "ETH/USDT", "SOLUSDT": "SOL/USDT",
    "BNBUSDT": "BNB/USDT", "XRPUSDT": "XRP/USDT", "DOGEUSDT": "DOGE/USDT",
}
TF_CCXT = {"M5": "5m", "M15": "15m", "H1": "1h", "H4": "4h"}
DEFAULT_OUT = "data/binance"
DEFAULT_START = "2024-05-22"
DEFAULT_END = "2026-05-22"


def _strict_override(cfg: dict) -> dict:
    sf = cfg.get("strict_fetch")
    if not sf:
        raise SystemExit("dataset_integrity.strict_fetch missing from the active config.")
    return {k: v for k, v in sf.items() if k != "_doc"}


def _ms(dt_str: str) -> int:
    return int(datetime.strptime(dt_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)


def _fetch_ccxt(exchange, ccxt_symbol: str, tf: str, start_ms: int, end_ms: int) -> list[list]:
    """Paginated public OHLCV fetch (1000/call), deduped + range-filtered."""
    limit, since, rows, calls = 1000, start_ms, [], 0
    while since < end_ms:
        try:
            batch = exchange.fetch_ohlcv(ccxt_symbol, TF_CCXT[tf], since=since, limit=limit)
        except Exception as exc:                       # transient network / rate limit
            safe_print(f"    ccxt error {ccxt_symbol} {tf} @ {since}: {exc} — retry 5s")
            _time.sleep(5)
            continue
        if not batch:
            break
        rows.extend(batch)
        since = batch[-1][0] + 1
        calls += 1
        _time.sleep(0.05)
    seen, uniq = set(), []
    for r in rows:
        if start_ms <= r[0] < end_ms and r[0] not in seen:
            seen.add(r[0])
            uniq.append(r)
    uniq.sort(key=lambda r: r[0])
    return uniq


def _write_csv(rows: list[list], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["timestamp,open,high,low,close,volume"]
    for ts_ms, o, h, l, c, v in rows:
        ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"{ts},{round(float(o),8)},{round(float(h),8)},{round(float(l),8)},"
                     f"{round(float(c),8)},{round(float(v),8)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(rows)


def _missing_tradable(path: Path, symbol: str, tf: str, cfg: dict, override: dict, *, limit=50):
    holidays = set(cfg.get("session_calendar", {}).get("holidays", []))
    ts_all = [t for _l, t, *_ in _stream_candles(path)]
    step = timedelta(minutes=_TF_MINUTES[tf])
    known = _parse_known_gaps(cfg.get("session_calendar", {}).get("known_gaps", []), symbol)

    def accepted(t):
        return any(lo <= t < hi for lo, hi in known)

    if override.get("tradability_mode") == "autoderive":
        mask = derive_weekly_mask(ts_all, presence_min=float(override.get("autoderive_presence_min", 0.5)))
        tradable = lambda t: (not accepted(t)) and is_tradable_by_mask(t, mask, holidays)  # noqa: E731
    else:
        sc = {**cfg.get("session_calendar", {}), "holidays": holidays}
        market = classify_market(symbol, cfg)
        tradable = lambda t: (not accepted(t)) and _is_tradable(t, market, sc)             # noqa: E731

    out, prev = [], None
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="fetch_and_verify_binance",
                                 description="Fetch Binance crypto (CCXT) + STRICT gap gate")
    ap.add_argument("--symbols", default=",".join(SYMBOLS))
    ap.add_argument("--timeframes", default=",".join(TF_CCXT))
    ap.add_argument("--start", default=DEFAULT_START)
    ap.add_argument("--end", default=DEFAULT_END)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--quarantine", default="data/binance/_rejected")
    args = ap.parse_args(argv)

    import ccxt
    exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "spot"}})

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    timeframes = [t.strip().upper() for t in args.timeframes.split(",") if t.strip()]
    cfg = get_prod_section("dataset_integrity")
    override = _strict_override(cfg)
    quarantine = Path(args.quarantine)
    start_ms, end_ms = _ms(args.start), _ms(args.end)

    safe_print(f"BINANCE STRICT fetch+verify — {symbols} x {timeframes} [{args.start}..{args.end})")
    safe_print(f"  provider corpus: {args.out} | autoderive + reviewed known_gaps\n")

    failures = []
    for sym in symbols:
        if sym not in SYMBOLS:
            safe_print(f"  [SKIP] {sym}: not a known Binance symbol")
            continue
        for tf in timeframes:
            safe_print(f"  fetching {sym} {tf} ...")
            rows = _fetch_ccxt(exchange, SYMBOLS[sym], tf, start_ms, end_ms)
            if not rows:
                safe_print(f"  [FETCH-FAIL] {sym} {tf}: 0 candles")
                failures.append(f"{sym}_{tf} (0 candles)")
                continue
            path = Path(args.out) / f"{sym}_{tf}.csv"
            n = _write_csv(rows, path)
            rep = validate_dataset(str(path), instrument=sym, raise_on_fail=False,
                                   cfg_override=override)
            if rep.get("decision") == "REJECT":
                miss = _missing_tradable(path, sym, tf, cfg, override)
                safe_print(f"  [REJECT] {sym} {tf} (n={n}): "
                           f"{'; '.join(rep.get('hard_failures', []))}")
                if miss:
                    safe_print(f"           first missing: {miss[:8]}")
                quarantine.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(quarantine / path.name))
                failures.append(f"{sym}_{tf}")
            else:
                safe_print(f"  [{rep.get('decision')}] {sym} {tf}: {n} rows OK")

    safe_print(f"\nfailures: {len(failures)}")
    if failures:
        safe_print(f"HARD STOP — {failures}")
        safe_print(f"Quarantined in {quarantine}; review missing timestamps (real Binance outages "
                   "→ known_gaps; else corrupt).")
        return 1
    safe_print("ALL CLEAN — every Binance timeframe passed the strict gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
