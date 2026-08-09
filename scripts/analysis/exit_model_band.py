# -*- coding: utf-8 -*-
"""
exit_model_band.py — [trust-layer F2] dual-bound exit-model report (thin CLI).

Runs the active config's backtest under BOTH exit models (close-only optimistic vs
intrabar-touch conservative/governing) and writes an oracle-verified comparison with
an inflation_ratio. Visibility only — promotion gates run on the conservative metric.

Usage:
    python scripts/analysis/exit_model_band.py                          # BNBUSDT default
    python scripts/analysis/exit_model_band.py --instrument GBPUSD
    python scripts/analysis/exit_model_band.py --csv data/BTCUSDT_M15.csv --instrument BTCUSDT
"""

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from runtime.exit_model_band import compute_exit_model_band  # noqa: E402
from utils.console_safe import safe_print                    # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Dual-bound exit-model band report")
    ap.add_argument("--instrument", default="BNBUSDT")
    ap.add_argument("--csv", default=None, help="OHLCV CSV (default: data/<instrument>_M15.csv)")
    ap.add_argument("--output", default=str(_ROOT / "reports" / "exit_model_band.json"))
    args = ap.parse_args()

    csv_path = args.csv or str(_ROOT / "data" / f"{args.instrument}_M15.csv")
    band = compute_exit_model_band(csv_path, args.instrument)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(band, indent=2, sort_keys=True), encoding="utf-8")

    ir = band.get("inflation_ratio")
    safe_print(f"  {args.instrument}  governing=intrabar_touch")
    safe_print(f"    PF        close_only={band['pf_close_only']:.3f}  "
               f"intrabar={band['pf_intrabar']:.3f}  "
               f"inflation_ratio={ir if ir is not None else band.get('note')}")
    safe_print(f"    expectancy close_only={band['expectancy_close_only']:.4f}  "
               f"intrabar={band['expectancy_intrabar']:.4f}")
    safe_print(f"    win_rate  close_only={band['win_rate_close_only']:.3f}  "
               f"intrabar={band['win_rate_intrabar']:.3f}")
    safe_print(f"    trades    close_only={band['trade_count_close_only']}  "
               f"intrabar={band['trade_count_intrabar']}")
    safe_print(f"    total_ret close_only={band['total_return_close_only']:.4f}  "
               f"intrabar={band['total_return_intrabar']:.4f}")
    safe_print(f"\n  band report -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
