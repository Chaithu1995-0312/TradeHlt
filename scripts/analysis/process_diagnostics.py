"""
process_diagnostics.py
======================
MEASURE-ONLY statistical diagnostics over a raw OHLCV series (BNBUSDT-scoped use).

Formalizes the Phase-1 process fingerprint into significance verdicts: Ljung-Box Q
(linear autocorrelation), ARCH-LM (volatility clustering), mutual information (nonlinear
dependence vs shuffled surrogate), and direction-only conditional entropy (the clean
coin-flip test). Reads only; writes a deterministic JSON manifest to results/analysis/.
Touches NO config, NO spine, NO directional filter. No scipy.

All math lives in src/research/process_diagnostics.py (pure, unit-tested); this is a thin
CLI wrapper mirroring scripts/analysis/process_characterizer.py.

Usage:
  python scripts/analysis/process_diagnostics.py --instrument BNBUSDT
  python scripts/analysis/process_diagnostics.py --instrument BNBUSDT --arch-q 12 --mi-bins 20
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

from research.process_diagnostics import run_diagnostics  # noqa: E402
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


def _sig(flag: bool) -> str:
    return "REJECT" if flag else "ok"


def _print_summary(d) -> None:
    safe_print(f"==== PROCESS DIAGNOSTICS — {d.instrument} "
               f"(N_candles={d.n_candles}, N_returns={d.n_returns}) ====")
    safe_print("  -- Ljung-Box Q (REJECT = autocorrelation present):")
    for series, byh in d.ljung_box.items():
        for h, row in byh.items():
            safe_print(f"     {series:<16} h={h:<3} Q={row['Q']}  "
                       f"5%={_sig(row['reject_at_5pct'])} 1%={_sig(row['reject_at_1pct'])}")
    a = d.arch_lm
    safe_print(f"  -- ARCH-LM (REJECT = vol clustering): LM={a['LM']} df={a['df']} "
               f"R2={a['r2']}  5%={_sig(a['reject_at_5pct'])} 1%={_sig(a['reject_at_1pct'])}")
    safe_print("  -- Mutual information (nats; significant = above shuffled surrogate):")
    for pair, m in d.mutual_information.items():
        safe_print(f"     {pair:<24} MI={m['mi_nats']}  surr_mean={m['surrogate_mean']}  "
                   f"p={m['p_value']}  {'SIGNIF' if m['significant'] else 'ns'}")
    safe_print("  -- Direction-only conditional entropy H(sign r_t+1 | sign r_t), "
               "within vol band (1.0=coin-flip):")
    for b, h in d.direction_entropy_per_band.items():
        safe_print(f"     band {b}: H={h}  (n={d.direction_entropy_counts[b]})")
    safe_print(f"     GLOBAL: H={d.direction_entropy_global}")
    safe_print(f"  -- THESIS FLAGS: {d.thesis_flags}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instrument", required=True)
    ap.add_argument("--csv", type=Path, default=None,
                    help="defaults to data/<INSTRUMENT>_M15.csv")
    ap.add_argument("--atr-period", type=int, default=14)
    ap.add_argument("--ljung-lags", default="10,20",
                    help="comma-separated Ljung-Box lag counts")
    ap.add_argument("--arch-q", type=int, default=12)
    ap.add_argument("--mi-bins", type=int, default=20)
    ap.add_argument("--mi-surrogates", type=int, default=200)
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args(argv)

    csv_path = args.csv or (_ROOT / "data" / f"{args.instrument}_M15.csv")
    if not csv_path.exists():
        safe_print(f"ERROR: csv not found: {csv_path}", file=sys.stderr)
        return 2
    lags = [int(x) for x in str(args.ljung_lags).split(",") if x.strip()]

    candles = list(CandleLoader(str(csv_path), instrument=args.instrument).stream())
    diag = run_diagnostics(
        candles,
        instrument=args.instrument,
        atr_period=args.atr_period,
        ljung_box_lags=lags,
        arch_q=args.arch_q,
        mi_bins=args.mi_bins,
        mi_surrogates=args.mi_surrogates,
    )

    out = args.output or (_ROOT / "results" / "analysis"
                          / f"process_diagnostics_{args.instrument}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(diag.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    run_out = out.with_name(out.stem + "_run_manifest.json")
    run_out.write_text(json.dumps({
        "instrument": args.instrument,
        "csv": str(csv_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "atr_period": args.atr_period,
        "ljung_lags": lags,
        "arch_q": args.arch_q,
        "mi_bins": args.mi_bins,
        "mi_surrogates": args.mi_surrogates,
    }, indent=2, sort_keys=True), encoding="utf-8")

    _print_summary(diag)
    safe_print(f"OUTPUT:process_diagnostics:{out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
