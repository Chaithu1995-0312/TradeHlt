#!/usr/bin/env python3
"""
xauusd_mt5_cost_seed_stops.py
=============================
DEMO-ONLY helper for ZONE-X O-1: place near-market STOP orders on XAUUSD so
`extract_slippage` can measure stop-order fill vs requested price.

Uses the same safety model as `manual_tools/trade_generator.py`:
  L1  trade_mode == DEMO re-checked before every order
  L2  --account-hash fingerprint pin + optional margin mode pin
  L3  lot <= 0.10, symbol allowlist, --max-orders cap
  L4  cancel any still-pending MAGIC stops; close any MAGIC positions left

Does NOT modify `mt5_analytics` (read-only). Does NOT run on real accounts.

Usage:
  python scripts/research/xauusd_mt5_cost_seed_stops.py
  python scripts/research/xauusd_mt5_cost_seed_stops.py --confirm --account-hash <fp>
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import MetaTrader5 as mt5  # type: ignore
    _MT5 = True
except Exception:
    mt5 = None  # type: ignore
    _MT5 = False

MAGIC = 520627  # distinct from trade_generator MAGIC=520626
LOT_CAP = 0.10
SYMBOL_ALLOWLIST = {"XAUUSD", "EURUSD", "GBPUSD", "USDJPY"}


def _p(*a):
    print(*a)


def _fingerprint(info) -> str:
    return hashlib.sha256(
        f"{info.company}|{info.server}|{info.login}".encode("utf-8")
    ).hexdigest()


def _assert_demo() -> None:
    info = mt5.account_info()
    mode = getattr(info, "trade_mode", None)
    if info is None or mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
        raise RuntimeError(f"L1 DEMO re-check FAILED (trade_mode={mode}) — abort")


def _filling(symbol: str):
    fm = getattr(mt5.symbol_info(symbol), "filling_mode", 0)
    if fm & getattr(mt5, "SYMBOL_FILLING_FOK", 1):
        return mt5.ORDER_FILLING_FOK
    if fm & getattr(mt5, "SYMBOL_FILLING_IOC", 2):
        return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN


def _digits_price(symbol: str, price: float) -> float:
    info = mt5.symbol_info(symbol)
    digits = int(getattr(info, "digits", 2) or 2)
    return round(float(price), digits)


def _place_stop(symbol: str, order_type: int, price: float, lot: float, deviation: int = 30):
    _assert_demo()
    fill = _filling(symbol)
    req = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": float(lot),
        "type": order_type,
        "price": _digits_price(symbol, price),
        "deviation": deviation,
        "magic": MAGIC,
        "comment": "zonex_o1_stop_seed",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": fill,
    }
    res = mt5.order_send(req)
    ok = res is not None and res.retcode == mt5.TRADE_RETCODE_DONE
    side = "BUY_STOP" if order_type == mt5.ORDER_TYPE_BUY_STOP else "SELL_STOP"
    _p(
        f"  {side} {lot} @ {req['price']} -> retcode={getattr(res, 'retcode', None)} "
        f"order={getattr(res, 'order', None)} {'OK' if ok else 'FAIL'} "
        f"comment={getattr(res, 'comment', '')}"
    )
    return res if ok else None


def _close_position(pos) -> bool:
    _assert_demo()
    tick = mt5.symbol_info_tick(pos.symbol)
    if tick is None:
        return False
    order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": pos.symbol,
        "volume": float(pos.volume),
        "type": order_type,
        "position": pos.ticket,
        "price": price,
        "deviation": 40,
        "magic": MAGIC,
        "comment": "zonex_o1_stop_close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": _filling(pos.symbol),
    }
    res = mt5.order_send(req)
    ok = res is not None and res.retcode == mt5.TRADE_RETCODE_DONE
    _p(f"  close pos={pos.ticket} -> retcode={getattr(res, 'retcode', None)} {'OK' if ok else 'FAIL'}")
    return ok


def _cancel_pending(symbol: str) -> int:
    n = 0
    for o in mt5.orders_get(symbol=symbol) or []:
        if int(getattr(o, "magic", 0)) != MAGIC:
            continue
        _assert_demo()
        res = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
        ok = res is not None and res.retcode == mt5.TRADE_RETCODE_DONE
        _p(f"  cancel pending={o.ticket} -> retcode={getattr(res, 'retcode', None)} {'OK' if ok else 'FAIL'}")
        if ok:
            n += 1
    return n


def _cleanup(symbol: str) -> tuple[int, int]:
    cancelled = _cancel_pending(symbol)
    closed = 0
    for pos in mt5.positions_get(symbol=symbol) or []:
        if int(getattr(pos, "magic", 0)) != MAGIC:
            continue
        if _close_position(pos):
            closed += 1
        time.sleep(0.3)
    remaining_pos = len([p for p in (mt5.positions_get(symbol=symbol) or []) if p.magic == MAGIC])
    remaining_ord = len([o for o in (mt5.orders_get(symbol=symbol) or []) if o.magic == MAGIC])
    return remaining_pos, remaining_ord


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbol", default="XAUUSD")
    p.add_argument("--lot", type=float, default=0.01)
    p.add_argument("--pairs", type=int, default=4, help="number of BUY_STOP+SELL_STOP pairs")
    p.add_argument(
        "--offsets-usd",
        default="0.15,0.25,0.40,0.80",
        help="comma list of USD distances from mid for stop placement",
    )
    p.add_argument("--wait-seconds", type=float, default=90.0, help="max wait for stops to trigger")
    p.add_argument("--poll-seconds", type=float, default=2.0)
    p.add_argument("--account-hash", default=None)
    p.add_argument("--require-margin", choices=["hedging", "netting"], default="hedging")
    p.add_argument("--confirm", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.lot > LOT_CAP:
        _p(f"REFUSED: lot {args.lot} > {LOT_CAP}")
        return 2
    if args.symbol not in SYMBOL_ALLOWLIST:
        _p(f"REFUSED: symbol {args.symbol} not allowlisted")
        return 2
    if not _MT5:
        _p("SKIP: MetaTrader5 not installed")
        return 0
    if not mt5.initialize():
        _p(f"SKIP: initialize failed: {mt5.last_error()}")
        return 0

    try:
        info = mt5.account_info()
        if info is None:
            _p("SKIP: not logged in")
            return 0
        fp = _fingerprint(info)
        if info.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
            _p(f"REFUSED (L1): not DEMO trade_mode={info.trade_mode}")
            return 2
        _margin_name = {0: "netting", 1: "exchange", 2: "hedging"}.get(info.margin_mode, "?")
        _p("=== ZONE-X O-1 STOP seed (DEMO only) ===")
        _p(f"symbol={args.symbol} lot={args.lot} pairs={args.pairs}")
        _p(f"account company={info.company!r} server={info.server!r} DEMO margin={_margin_name}")
        _p(f"account_fingerprint= {fp}")

        if not args.confirm:
            _p("DRY-RUN: no orders. Re-run with:")
            _p(f"  --confirm --account-hash {fp} --require-margin {_margin_name}")
            return 0

        if args.account_hash != fp:
            _p(f"REFUSED (L2): fingerprint mismatch live={fp} got={args.account_hash}")
            return 2
        want = {
            "hedging": mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
            "netting": mt5.ACCOUNT_MARGIN_MODE_RETAIL_NETTING,
        }
        if args.require_margin and info.margin_mode != want[args.require_margin]:
            _p(f"REFUSED (L2 margin): need {args.require_margin}, got {_margin_name}")
            return 2

        if mt5.symbol_info(args.symbol) is None:
            _p(f"REFUSED: unknown symbol {args.symbol}")
            return 2
        mt5.symbol_select(args.symbol, True)

        offsets = [float(x) for x in args.offsets_usd.split(",") if x.strip()]
        if not offsets:
            offsets = [0.25]
        # cycle offsets across pairs
        placed = 0
        for i in range(args.pairs):
            off = offsets[i % len(offsets)]
            tick = mt5.symbol_info_tick(args.symbol)
            if tick is None:
                _p("no tick; abort")
                break
            mid = (tick.bid + tick.ask) / 2.0
            # BUY_STOP above market, SELL_STOP below — near enough to fill soon on gold
            _place_stop(args.symbol, mt5.ORDER_TYPE_BUY_STOP, mid + off, args.lot)
            _place_stop(args.symbol, mt5.ORDER_TYPE_SELL_STOP, mid - off, args.lot)
            placed += 2
            time.sleep(0.4)

        _p(f"placed_pending={placed}; waiting up to {args.wait_seconds}s for triggers...")
        t0 = time.time()
        filled_positions = 0
        while time.time() - t0 < args.wait_seconds:
            pos = [p for p in (mt5.positions_get(symbol=args.symbol) or []) if p.magic == MAGIC]
            pending = [o for o in (mt5.orders_get(symbol=args.symbol) or []) if o.magic == MAGIC]
            filled_positions = len(pos)
            _p(f"  t={time.time()-t0:5.1f}s positions={filled_positions} pending={len(pending)}")
            # close any filled stop positions promptly (we only need the fill record)
            for p_ in pos:
                _close_position(p_)
            if not pending and not pos:
                break
            time.sleep(args.poll_seconds)

        rem_pos, rem_ord = _cleanup(args.symbol)
        _p(f"cleanup remaining_positions={rem_pos} remaining_pending={rem_ord}")
        if rem_pos or rem_ord:
            _p("FAIL: leftover MAGIC stops/positions")
            return 1
        _p("Done. Re-run cost calibration with --skip-ticks to harvest commission/stop slip.")
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
