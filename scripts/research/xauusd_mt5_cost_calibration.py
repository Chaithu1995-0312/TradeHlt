#!/usr/bin/env python3
"""
xauusd_mt5_cost_calibration.py
===============================
ZONE-X O-1 diagnostic: extract real spread/commission/slippage/swap for
XAUUSD from a locally running MT5 terminal. READ-ONLY -- never places or
modifies an order. Authority: RESEARCH_ONLY.

Requires a running, logged-in MT5 desktop terminal and `pip install
MetaTrader5` (Windows-only). See src/research/mt5_cost_calibration.py for the
extraction logic, the never-fabricate status contract, and the minimal manual
path to populate commission/stop-slippage history on a fresh demo account.

Usage:
  python scripts/research/xauusd_mt5_cost_calibration.py
  python scripts/research/xauusd_mt5_cost_calibration.py --tick-days 30 --history-days 180
  python scripts/research/xauusd_mt5_cost_calibration.py --skip-ticks   # rerun history-only, cheap
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from research.mt5_cost_calibration import (  # noqa: E402
    CostCalibrationConfig,
    MT5CostReader,
    Status,
    compute_c_per_side,
    extract_commission,
    extract_slippage,
    extract_spread_by_hour,
    extract_swap,
    render_summary_md,
    write_commission_json,
    write_slippage_csv,
    write_spread_csv,
    write_swap_json,
)
from mt5_analytics.core.mt5_adapter import MT5Adapter  # noqa: E402


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbol", default="XAUUSD", help="broker symbol name (gold naming varies)")
    p.add_argument("--tick-days", type=int, default=14, help="trailing days of ticks for spread-by-hour")
    p.add_argument("--history-days", type=int, default=90, help="trailing days of deals/orders scanned")
    p.add_argument("--tick-chunk-days", type=int, default=1, help="copy_ticks_range chunk size in days")
    p.add_argument("--server-utc-offset-hours", type=float, default=None,
                    help="manual override for the MT5Adapter server<->UTC offset")
    p.add_argument("--out-dir", default=str(ROOT / "results" / "research" / "xauusd_mt5_cost_calibration"))
    p.add_argument("--skip-ticks", action="store_true", help="skip the slow tick pull (spread stays stale)")
    p.add_argument("--skip-history", action="store_true", help="skip deals/orders scan (commission/slippage stale)")
    p.add_argument("--min-stop-fills", type=int, default=5, help="reporting hint only, never a silent gate")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cfg = CostCalibrationConfig(
        symbol=args.symbol,
        tick_lookback_days=args.tick_days,
        history_lookback_days=args.history_days,
        tick_chunk_days=args.tick_chunk_days,
        min_stop_fills_for_confidence=args.min_stop_fills,
        out_dir=Path(args.out_dir),
        server_utc_offset_hours=args.server_utc_offset_hours,
    )
    cfg.out_dir.mkdir(parents=True, exist_ok=True)

    now = dt.datetime.now(tz=dt.timezone.utc).replace(microsecond=0)
    tick_from = now - dt.timedelta(days=cfg.tick_lookback_days)
    history_from = now - dt.timedelta(days=cfg.history_lookback_days)
    ts = now.strftime("%Y%m%dT%H%M%SZ")

    print(f"--- XAUUSD MT5 COST CALIBRATION (ZONE-X O-1) --- symbol={cfg.symbol}")

    with MT5Adapter(server_utc_offset_hours=cfg.server_utc_offset_hours) as mt5a:
        reader = MT5CostReader(mt5a)

        if args.skip_ticks:
            print("--skip-ticks: spread result will be INSUFFICIENT_DATA (stale, not re-measured)")
            from research.mt5_cost_calibration import SpreadResult
            spread = SpreadResult(
                status=Status.INSUFFICIENT_DATA, hourly=None, overall_median_usd=None,
                overall_p90_usd=None, n_ticks_total=0, window=(tick_from.isoformat(), now.isoformat()),
                note="--skip-ticks passed; spread not re-measured this run.",
            )
        else:
            print(f"Pulling ticks: {tick_from.isoformat()} -> {now.isoformat()} "
                  f"(chunk={cfg.tick_chunk_days}d) ...")
            spread = extract_spread_by_hour(
                reader, cfg.symbol, tick_from, now, chunk_days=cfg.tick_chunk_days
            )
            print(f"  spread: status={spread.status.value} n_ticks={spread.n_ticks_total} "
                  f"median={spread.overall_median_usd}")

        if args.skip_history:
            print("--skip-history: commission/slippage results will be INSUFFICIENT_DATA")
            from research.mt5_cost_calibration import CommissionResult, SlippageResult
            commission = CommissionResult(
                status=Status.INSUFFICIENT_DATA, per_lot_per_side_usd={"n": 0}, per_oz_usd={"n": 0},
                n_positions=0, n_positions_with_commission=0, commission_form_observed=None,
                window=(history_from.isoformat(), now.isoformat()),
                note="--skip-history passed; commission not re-measured this run.",
            )
            slippage = SlippageResult(
                status=Status.INSUFFICIENT_DATA, by_order_type={}, stop_slippage_median_usd=None,
                stop_status=Status.INSUFFICIENT_DATA, window=(history_from.isoformat(), now.isoformat()),
                note="--skip-history passed; slippage not re-measured this run.",
            )
        else:
            print(f"Scanning deals/orders: {history_from.isoformat()} -> {now.isoformat()} ...")
            commission = extract_commission(mt5a, cfg.symbol, history_from, now)
            print(f"  commission: status={commission.status.value} "
                  f"n_positions={commission.n_positions} "
                  f"with_commission={commission.n_positions_with_commission}")
            slippage = extract_slippage(mt5a, cfg.symbol, history_from, now)
            n_stop = slippage.by_order_type.get("STOP", {}).get("n", 0)
            print(f"  slippage: status={slippage.status.value} stop_status={slippage.stop_status.value} "
                  f"n_stop_fills={n_stop}")
            if n_stop < cfg.min_stop_fills_for_confidence:
                print(f"  NOTE: n_stop_fills={n_stop} < --min-stop-fills={cfg.min_stop_fills_for_confidence} "
                      "(reporting hint only -- value still used if MEASURED)")

        print("Reading swap / contract spec ...")
        swap = extract_swap(reader, cfg.symbol, mt5a)
        print(f"  swap: status={swap.status.value} mode={swap.swap_mode_name}")

    c_per_side = compute_c_per_side(spread, commission, slippage)
    print(f"c_per_side: {c_per_side}")

    outputs = {}
    p = write_spread_csv(spread, cfg.out_dir, ts)
    if p:
        outputs["spread_by_hour_csv"] = str(p).replace("\\", "/")
    outputs["commission_json"] = str(write_commission_json(commission, cfg.out_dir, ts)).replace("\\", "/")
    outputs["slippage_by_order_type_csv"] = str(write_slippage_csv(slippage, cfg.out_dir, ts)).replace("\\", "/")
    outputs["swap_json"] = str(write_swap_json(swap, cfg.out_dir, ts)).replace("\\", "/")

    manifest = {
        "title": "XAUUSD MT5 cost calibration -- ZONE-X O-1",
        "generated_utc": now.isoformat(),
        "authority": "RESEARCH_ONLY -- standalone diagnostic, no economic authority, no production touch",
        "symbol": cfg.symbol,
        "tick_window": [tick_from.isoformat(), now.isoformat()],
        "history_window": [history_from.isoformat(), now.isoformat()],
        "statuses": {
            "spread": spread.status.value,
            "commission": commission.status.value,
            "slippage_overall": slippage.status.value,
            "slippage_stop": slippage.stop_status.value,
            "swap": swap.status.value,
        },
        "c_per_side": c_per_side,
        "zone_x_citation": "ZONE-X-SPEC-v0.8.md §3.2/§8.1, frozen",
        "outputs": outputs,
    }
    manifest["outputs"] = {
        **outputs,
        **{f"{k}_sha256": _sha256(Path(v)) for k, v in outputs.items()},
    }

    man_path = cfg.out_dir / f"xauusd_mt5_cost_calibration_manifest_{ts}.json"
    man_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    (cfg.out_dir / "xauusd_mt5_cost_calibration_manifest_LATEST.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )

    md = render_summary_md(spread, commission, slippage, swap, c_per_side, cfg, now.isoformat())
    (cfg.out_dir / "XAUUSD_MT5_COST_CALIBRATION.md").write_text(md, encoding="utf-8")

    print("--- DONE ---")
    print(f"manifest: {man_path}")
    print(f"report:   {cfg.out_dir / 'XAUUSD_MT5_COST_CALIBRATION.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
