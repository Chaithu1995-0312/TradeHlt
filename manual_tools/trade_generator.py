#!/usr/bin/env python
"""
trade_generator — DEMO-ONLY tiny-trade generator for broker-semantics validation.

EXECUTION utility, deliberately OUTSIDE `mt5_analytics/` (read-only/fail-closed) AND outside
`tests/` (tests observe; generators act). Its only purpose is to make a real MT5 *demo* account
emit deal records so the analytics kernel can be validated against real broker semantics. This
is **test-fixture generation, not trading** — it does NOT seek profit and needs no trading skill.

LAYERED SAFETY INVARIANTS (code-enforced):
  L1  trade_mode == DEMO — re-checked immediately before EVERY order; fail => abort, 0 orders.
  L2  account-fingerprint pin (--account-hash must match sha256(company|server|login));
      --require-hedging; lot <= 0.10; --max-trades cap; symbol in allowlist.
  L4  _close_all_by_magic() cleanup sweep at the end.
  L5  proof: zero MAGIC-tagged positions remain (else exit FAIL).
  L6  summary: {opened, closed, remaining} — remaining must be 0.

Usage (run it yourself or via the validation playbook):
    python manual_tools/trade_generator.py                       # dry-run, prints fingerprint
    python manual_tools/trade_generator.py --confirm --require-hedging \
        --account-hash <hash-from-dry-run> --symbol EURUSD --lot 0.01 --count 6
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import MetaTrader5 as mt5  # type: ignore
    _MT5 = True
except Exception:
    mt5 = None  # type: ignore
    _MT5 = False

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root (run as a script)
try:  # Execution Quality Observatory (Phase C-op) — optional; generator works without it.
    from exec_telemetry.schemas.execution_event_v1 import ExecutionEvent, retcode_name
    _EXEC_TELEMETRY = True
except Exception:
    _EXEC_TELEMETRY = False

LOT_CAP = 0.10
MAGIC = 520626
SYMBOL_ALLOWLIST = {"EURUSD", "GBPUSD", "USDJPY", "XAUUSD"}
MAX_TRADES_DEFAULT = 12

_counter = {"sent": 0, "opened": 0, "closed": 0}
_MAX_TRADES = MAX_TRADES_DEFAULT
# Execution-telemetry sink (None = off). Set in main() only under --confirm --exec-log.
_EXEC_LOG: "dict | None" = None


def _p(*a):
    try:
        print(*a)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        print(*[str(x).encode(enc, "replace").decode(enc) for x in a])


def _fingerprint(info) -> str:
    return hashlib.sha256(
        f"{info.company}|{info.server}|{info.login}".encode("utf-8")
    ).hexdigest()


def _assert_demo() -> None:
    """L1 — re-verify DEMO before EVERY order. Any deviation aborts the whole run."""
    info = mt5.account_info()
    mode = getattr(info, "trade_mode", None)
    if info is None or mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
        raise RuntimeError(f"L1 DEMO re-check FAILED (trade_mode={mode}) — aborting, no order")


def _filling(symbol):
    """Pick a filling mode the symbol actually supports (avoids retcode 10030)."""
    fm = getattr(mt5.symbol_info(symbol), "filling_mode", 0)
    if fm & getattr(mt5, "SYMBOL_FILLING_FOK", 1):
        return mt5.ORDER_FILLING_FOK
    if fm & getattr(mt5, "SYMBOL_FILLING_IOC", 2):
        return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN


def _fill_name(fill) -> str:
    return {getattr(mt5, "ORDER_FILLING_FOK", 0): "FOK",
            getattr(mt5, "ORDER_FILLING_IOC", 1): "IOC",
            getattr(mt5, "ORDER_FILLING_RETURN", 2): "RETURN"}.get(fill, str(fill))


def _capture_exec_event(symbol, order_type, lot, requested, res, latency_ms, fill_mode):
    """Append one ExecutionEvent to the per-broker telemetry log (no-op unless --exec-log)."""
    if _EXEC_LOG is None or not _EXEC_TELEMETRY:
        return
    point = getattr(mt5.symbol_info(symbol), "point", 0.0) or 0.0
    code = getattr(res, "retcode", None)
    filled = float(getattr(res, "price", 0.0) or 0.0)
    slip = ((filled - requested) / point) if (point and filled) else 0.0
    ev = ExecutionEvent(
        ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        broker_fingerprint=_EXEC_LOG["fingerprint"], company=_EXEC_LOG["company"],
        server=_EXEC_LOG["server"], login=_EXEC_LOG["login"], margin_mode=_EXEC_LOG["margin_mode"],
        symbol=symbol, side="buy" if order_type == mt5.ORDER_TYPE_BUY else "sell",
        requested_price=float(requested), filled_price=filled, slippage_points=round(slip, 6),
        latency_ms=round(latency_ms, 3), retcode=int(code) if code is not None else -1,
        retcode_name=retcode_name(code), filling_mode=_fill_name(fill_mode), volume=float(lot),
    )
    path = _EXEC_LOG["dir"] / "orders.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(ev.to_dict(), sort_keys=True) + "\n")


def _send(symbol, order_type, lot, position=None, deviation=20):
    if _counter["sent"] >= _MAX_TRADES:
        _p(f"    max-trades {_MAX_TRADES} reached; skipping")
        return None
    _assert_demo()  # L1 before EVERY order
    tick = mt5.symbol_info_tick(symbol)
    price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
    fill_mode = _filling(symbol)
    req = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": float(lot),
        "type": order_type, "price": price, "deviation": deviation, "magic": MAGIC,
        "comment": "mt5a_validation", "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": fill_mode,
    }
    if position is not None:
        req["position"] = position
    _t0 = time.perf_counter()
    res = mt5.order_send(req)
    latency_ms = (time.perf_counter() - _t0) * 1000.0
    ok = res is not None and res.retcode == mt5.TRADE_RETCODE_DONE
    _counter["sent"] += 1
    if ok:
        _counter["closed" if position is not None else "opened"] += 1
    _capture_exec_event(symbol, order_type, lot, price, res, latency_ms, fill_mode)
    _p(f"    {'BUY' if order_type == mt5.ORDER_TYPE_BUY else 'SELL'} {lot} {symbol} -> "
       f"retcode={getattr(res, 'retcode', None)} deal={getattr(res, 'deal', None)} "
       f"{'OK' if ok else 'FAIL'}")
    return res if ok else None


def _latest_position(symbol):
    positions = mt5.positions_get(symbol=symbol) or []
    mine = [p for p in positions if p.magic == MAGIC]
    return max(mine, key=lambda p: p.ticket) if mine else None


def _close_position(pos):
    opp = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    _send(pos.symbol, opp, pos.volume, position=pos.ticket)


def _open_and_close(symbol, side, lot, hold):
    if not _send(symbol, mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL, lot):
        return
    time.sleep(hold)
    pos = _latest_position(symbol)
    if pos:
        _close_position(pos)


def _partial_close(symbol, lot, hold):
    if not _send(symbol, mt5.ORDER_TYPE_BUY, lot * 2):
        return
    time.sleep(hold)
    pos = _latest_position(symbol)
    if pos:
        _send(symbol, mt5.ORDER_TYPE_SELL, lot, position=pos.ticket)
    time.sleep(hold)
    pos = _latest_position(symbol)
    if pos:
        _send(symbol, mt5.ORDER_TYPE_SELL, pos.volume, position=pos.ticket)


def _pyramid(symbol, lot, hold):
    _send(symbol, mt5.ORDER_TYPE_BUY, lot)
    time.sleep(hold)
    _send(symbol, mt5.ORDER_TYPE_BUY, lot)
    time.sleep(hold)
    # hedging => two positions; close both tagged with MAGIC
    for pos in [p for p in (mt5.positions_get(symbol=symbol) or []) if p.magic == MAGIC]:
        _close_position(pos)


def _inout(symbol, lot, hold):
    # netting reversal: BUY lot, then SELL 2*lot -> nets to SHORT lot via a single
    # DEAL_ENTRY_INOUT (close long + open short); then close the resulting short.
    if not _send(symbol, mt5.ORDER_TYPE_BUY, lot):
        return
    time.sleep(hold)
    _send(symbol, mt5.ORDER_TYPE_SELL, lot * 2)
    time.sleep(hold)
    for pos in [p for p in (mt5.positions_get(symbol=symbol) or []) if p.magic == MAGIC]:
        _close_position(pos)


def _close_all_by_magic(symbol) -> int:
    """L4 cleanup — close every still-open MAGIC position. Returns remaining count (L5)."""
    for pos in [p for p in (mt5.positions_get(symbol=symbol) or []) if p.magic == MAGIC]:
        _close_position(pos)
        time.sleep(0.5)
    remaining = len([p for p in (mt5.positions_get(symbol=symbol) or []) if p.magic == MAGIC])
    return remaining


_PLAN = {
    "normal": "N x open->close round-trips",
    "partial": "open 2*lot -> close lot -> close lot (partial scale-out)",
    "pyramid": "open lot -> open lot -> close all (scale-in; netting aggregates to one position)",
    "inout": "BUY lot -> SELL 2*lot (netting reversal -> DEAL_ENTRY_INOUT) -> close short",
    "reopen": "open->close, then open->close again (same symbol)",
    "hold": "open ONE lot and LEAVE IT OPEN (overnight swap capture; no cleanup)",
    "close": "close all MAGIC-tagged positions (run after an overnight 'hold')",
}


def main(argv=None) -> int:
    global _MAX_TRADES
    ap = argparse.ArgumentParser(description="DEMO-ONLY MT5 trade generator")
    ap.add_argument("--symbol", default="EURUSD")
    ap.add_argument("--lot", type=float, default=0.01)
    ap.add_argument("--count", type=int, default=6)
    ap.add_argument("--hold-seconds", type=float, default=2.0)
    ap.add_argument("--patterns", default="normal,partial,pyramid,reopen")
    ap.add_argument("--max-trades", type=int, default=MAX_TRADES_DEFAULT)
    ap.add_argument("--account-hash", default=None, help="required with --confirm (L2 pin)")
    ap.add_argument("--require-margin", choices=["hedging", "netting"], default=None,
                    help="abort unless the account's margin mode matches (L2)")
    ap.add_argument("--extra-allow-symbol", action="append", default=[],
                    help="explicitly opt in a symbol outside the base allowlist (e.g. an "
                         "ECN-suffixed EURUSD.r); repeatable or comma-separated. Fails closed: "
                         "only opted-in symbols are added; DEMO/lot-cap/fingerprint gates unchanged")
    ap.add_argument("--exec-log", action="store_true",
                    help="capture execution telemetry (slippage/latency/retcode) per order to "
                         "runtime/exec_telemetry/<broker>/orders.jsonl (Execution Quality Observatory)")
    ap.add_argument("--confirm", action="store_true", help="REQUIRED to place real orders")
    args = ap.parse_args(argv)
    global _EXEC_LOG
    _MAX_TRADES = args.max_trades

    # L2 — static bounds
    if args.lot > LOT_CAP:
        _p(f"REFUSED: --lot {args.lot} exceeds hard cap {LOT_CAP}")
        return 2
    extra = {s.strip() for item in args.extra_allow_symbol
             for s in item.split(",") if s.strip()}
    allowlist = SYMBOL_ALLOWLIST | extra   # base set intact; only explicit opt-ins added
    if args.symbol not in allowlist:
        _p(f"REFUSED: symbol {args.symbol} not in allowlist {sorted(allowlist)} "
           f"(opt in explicitly with: --extra-allow-symbol {args.symbol})")
        return 2
    patterns = [p.strip() for p in args.patterns.split(",") if p.strip()]

    _p("=== MT5 demo trade generator ===")
    _p(f"symbol={args.symbol} lot={args.lot} count={args.count} max_trades={_MAX_TRADES} "
       f"patterns={patterns}")
    for pat in patterns:
        _p(f"  plan[{pat}]: {_PLAN.get(pat, '?')}")

    if not _MT5:
        _p("SKIP: MetaTrader5 not installed.")
        return 0
    if not mt5.initialize():
        _p(f"SKIP: MT5 initialize() failed: {mt5.last_error()}")
        return 0
    try:
        info = mt5.account_info()
        if info is None:
            _p("SKIP: no account_info (terminal not logged in).")
            return 0
        fp = _fingerprint(info)
        # L1
        if info.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
            _p(f"REFUSED (L1): trade_mode={info.trade_mode} is NOT DEMO. No orders.")
            return 2
        _p(f"account: login={info.login} company={info.company!r} server={info.server!r} "
           f"DEMO margin_mode={info.margin_mode}")
        _p(f"account_fingerprint(sha256 company|server|login)= {fp}")

        _margin_name = {0: "netting", 1: "exchange", 2: "hedging"}.get(info.margin_mode, "?")
        if not args.confirm:
            _p("\nDRY-RUN (no --confirm): no orders sent. To trade, re-run with:")
            _p(f"  --confirm --account-hash {fp} --require-margin {_margin_name}")
            return 0

        # L2 — fingerprint pin + margin gate (only when actually trading)
        if args.account_hash != fp:
            _p(f"REFUSED (L2 fingerprint): live={fp} != --account-hash={args.account_hash}")
            return 2
        _want = {"hedging": mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
                 "netting": mt5.ACCOUNT_MARGIN_MODE_RETAIL_NETTING}
        if args.require_margin and info.margin_mode != _want[args.require_margin]:
            _p(f"REFUSED (L2 margin): margin_mode={info.margin_mode} ({_margin_name}) != "
               f"--require-margin {args.require_margin}")
            return 2

        # Execution Quality Observatory: arm the telemetry sink (post-gate, demo-confirmed only).
        if args.exec_log:
            if not _EXEC_TELEMETRY:
                _p("WARN: --exec-log requested but exec_telemetry not importable; skipping telemetry.")
            else:
                key = re.sub(r"[^A-Za-z0-9._-]+", "_",
                             f"{info.company}_{info.server}_mm{info.margin_mode}").strip("_")
                _EXEC_LOG = {"dir": Path("runtime/exec_telemetry") / key, "fingerprint": fp,
                             "company": info.company, "server": info.server,
                             "login": int(info.login), "margin_mode": int(info.margin_mode)}
                _p(f"exec-telemetry: ON -> runtime/exec_telemetry/{key}/orders.jsonl")

        if mt5.symbol_info(args.symbol) is None:
            _p(f"REFUSED: unknown symbol {args.symbol}")
            return 2
        mt5.symbol_select(args.symbol, True)

        for pat in patterns:
            _p(f"\n-- {pat} --")
            if pat == "normal":
                for i in range(args.count):
                    _open_and_close(args.symbol, "buy" if i % 2 == 0 else "sell",
                                    args.lot, args.hold_seconds)
            elif pat == "partial":
                _partial_close(args.symbol, args.lot, args.hold_seconds)
            elif pat == "pyramid":
                _pyramid(args.symbol, args.lot, args.hold_seconds)
            elif pat == "inout":
                _inout(args.symbol, args.lot, args.hold_seconds)
            elif pat == "reopen":
                _open_and_close(args.symbol, "buy", args.lot, args.hold_seconds)
                _open_and_close(args.symbol, "buy", args.lot, args.hold_seconds)
            elif pat == "hold":
                _send(args.symbol, mt5.ORDER_TYPE_BUY, args.lot)   # open & LEAVE OPEN
            elif pat == "close":
                pass   # handled by the cleanup sweep below

        # 'hold' deliberately leaves the position open (overnight swap capture) — skip L4/L5.
        if "hold" in patterns:
            open_pos = [p for p in (mt5.positions_get(symbol=args.symbol) or [])
                        if p.magic == MAGIC]
            _p(f"\nLEFT OPEN {len(open_pos)} position(s): tickets={[p.ticket for p in open_pos]}")
            _p("Swap accrues at the broker's daily rollover. Tomorrow close with --patterns close.")
            return 0

        remaining = _close_all_by_magic(args.symbol)   # L4 + L5
        _p(f"\nopened={_counter['opened']} closed={_counter['closed']} remaining={remaining}")
        if remaining != 0:
            _p("FAIL (L5): positions left open after cleanup.")
            return 1
        _p("Done. Now run: python -m mt5_analytics.core.coverage --from <d> --to <d>")
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    sys.exit(main())
