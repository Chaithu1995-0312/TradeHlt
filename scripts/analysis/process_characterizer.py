"""
process_characterizer.py
========================
MEASURE-ONLY process characterisation of a raw OHLCV series.

Tests the thesis "volatility has memory; direction mostly does not" by emitting a
deterministic process manifest (autocorrelation, Hurst/variance-ratio, 6-state Markov
transition matrix) for an instrument's M15 data. Reads only; writes a JSON manifest to
results/analysis/. Touches NO config, NO spine, NO directional filter.

All math lives in src/research/process_characterization.py (pure, unit-tested); this is
a thin CLI wrapper that loads candles, calls characterize(), prints a summary, and splits
the deterministic body from the wall-clock run-manifest (per the research-layer pattern).

Usage:
  python scripts/analysis/process_characterizer.py --csv data/BNBUSDT_M15.csv --instrument BNBUSDT
  python scripts/analysis/process_characterizer.py --instrument BNBUSDT --max-lag 50 --vr-q 2,4,8,16
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.process_characterization import characterize  # noqa: E402
from runtime.backtest_v2 import CandleLoader  # noqa: E402
from utils.console_safe import safe_print  # noqa: E402


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(_ROOT),
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _print_summary(m) -> None:
    safe_print(f"==== PROCESS CHARACTERIZATION — {m.instrument} "
               f"(N_candles={m.n_candles}, N_returns={m.n_returns}) ====")
    safe_print("  -- Hurst (R/S): 0.5=random walk, >0.5=persistent, <0.5=mean-reverting")
    safe_print(f"     returns      H = {m.hurst_returns}")
    safe_print(f"     |returns|    H = {m.hurst_abs_returns}")
    safe_print(f"     ATR          H = {m.hurst_atr}")
    safe_print("  -- ACF decay (lag1..5): returns vs |returns| vs ATR")
    safe_print(f"     returns   : {m.acf_returns[:5]}")
    safe_print(f"     |returns| : {m.acf_abs_returns[:5]}")
    safe_print(f"     ATR       : {m.acf_atr[:5]}")
    safe_print(f"  -- Variance ratio (returns), q->VR (1.0=random walk): {m.variance_ratio_returns}")
    safe_print(f"  -- Vol terciles (ATR): low<={m.vol_cut_low}  high<={m.vol_cut_high}")
    safe_print(f"  -- Markov states {m.state_labels}  mean_exit_entropy={m.mean_exit_entropy} (1.0=coin-flip)")
    for lab, row in zip(m.state_labels, m.transition_matrix):
        safe_print(f"     {lab} -> {[f'{p:.3f}' for p in row]}  (H={m.row_entropy[lab]})")
    safe_print(f"  -- THESIS FLAGS: {m.thesis_flags}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instrument", required=True)
    ap.add_argument("--csv", type=Path, default=None,
                    help="defaults to data/<INSTRUMENT>_M15.csv")
    ap.add_argument("--atr-period", type=int, default=14)
    ap.add_argument("--max-lag", type=int, default=50)
    ap.add_argument("--vr-q", default="2,4,8,16",
                    help="comma-separated variance-ratio horizons")
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args(argv)

    csv_path = args.csv or (_ROOT / "data" / f"{args.instrument}_M15.csv")
    if not csv_path.exists():
        safe_print(f"ERROR: csv not found: {csv_path}", file=sys.stderr)
        return 2
    vr_qs = [int(x) for x in str(args.vr_q).split(",") if x.strip()]

    candles = list(CandleLoader(str(csv_path), instrument=args.instrument).stream())
    manifest = characterize(
        candles,
        instrument=args.instrument,
        atr_period=args.atr_period,
        max_lag=args.max_lag,
        vr_qs=vr_qs,
    )

    out = args.output or (_ROOT / "results" / "analysis"
                          / f"process_manifest_{args.instrument}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    # Deterministic body — sort_keys so two runs are byte-identical.
    out.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True),
                   encoding="utf-8")
    # Wall-clock provenance kept OUT of the deterministic manifest (research pattern).
    run_out = out.with_name(out.stem + "_run_manifest.json")
    run_out.write_text(json.dumps({
        "instrument": args.instrument,
        "csv": str(csv_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "atr_period": args.atr_period,
        "max_lag": args.max_lag,
        "vr_q": vr_qs,
    }, indent=2, sort_keys=True), encoding="utf-8")

    _print_summary(manifest)
    safe_print(f"OUTPUT:process_manifest:{out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
