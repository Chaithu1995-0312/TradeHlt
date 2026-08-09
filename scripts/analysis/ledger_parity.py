"""
ledger_parity.py
=================
F-057 acceptance gate (target-strategy-architecture.md sec13 item4 / sec14.A last item).

Runs the SAME corpus through two BacktestRunner construction styles and asserts the
resulting metrics ledgers are identical:

  ARM "governed"   — crt_config explicitly loaded via load_prod_config_from_registry(),
                     mirroring what the backtest_v2 CLI does.
  ARM "programmatic" — crt_config left None on BacktestConfig, so BacktestRunner.__init__'s
                     internal fallback resolves it. Before the F-057 fix (2026-07-29) this
                     fallback called the bare, router-only ConfigBuilder.build() and silently
                     diverged from the CLI on 5 CRTConfig fields for every instrument
                     (body_ratio_min, atr_multiplier_min, retest_depth_max,
                     expansion_atr_min_distance, retest_atr_depth_fraction — all overridden
                     by the active config's `params` section on the governed path only).

A run is a PASS iff both arms' BacktestMetrics.to_dict() are byte-identical (JSON-equal)
after stripping run-id/wall-clock-only fields. There are none in BacktestMetrics today, so
no stripping is actually needed — kept as an explicit no-op list for future-proofing.

Usage
    python scripts/analysis/ledger_parity.py --csv data/XAUUSD_W2026-03-23-to-2026-05-21.csv --instrument XAUUSD
    python scripts/analysis/ledger_parity.py --csv data/XAUUSD_W2026-03-23-to-2026-05-21.csv --instrument XAUUSD --check
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Fields that are legitimately allowed to differ between the two arms (none today —
# both arms use the same CRTConfig, same corpus, same seeded slippage). Kept explicit
# so a future genuinely-arm-specific field doesn't silently fail this gate without a
# human deciding to add it here.
_IGNORE_KEYS: set[str] = set()


def _run_arm(csv_path: str, instrument: str, pip_size: float, explicit_crt_config: bool) -> dict:
    from config_layer.production_config import load_prod_config_from_registry, PROD_VERSION
    from runtime.backtest_v2 import BacktestConfig, BacktestRunner, CandleLoader

    crt_cfg = load_prod_config_from_registry(PROD_VERSION, instrument) if explicit_crt_config else None
    cfg = BacktestConfig.from_prod_config(
        instrument=instrument, pip_size=pip_size, crt_config=crt_cfg,
    )
    loader = CandleLoader(csv_path, instrument)
    runner = BacktestRunner(cfg, csv_path=csv_path)
    metrics = runner.run(loader.stream(), loader.count(), output_dir=str(_ROOT / "results" / "_ledger_parity_tmp"))
    return metrics.to_dict() if hasattr(metrics, "to_dict") else metrics


def run_parity_check(csv_path: str, instrument: str, pip_size: float = 0.01) -> tuple[bool, dict]:
    governed = _run_arm(csv_path, instrument, pip_size, explicit_crt_config=True)
    programmatic = _run_arm(csv_path, instrument, pip_size, explicit_crt_config=False)

    for k in _IGNORE_KEYS:
        governed.pop(k, None)
        programmatic.pop(k, None)

    ok = governed == programmatic
    diff = {}
    if not ok:
        keys = set(governed) | set(programmatic)
        for k in sorted(keys):
            gv, pv = governed.get(k, "<missing>"), programmatic.get(k, "<missing>")
            if gv != pv:
                diff[k] = {"governed": gv, "programmatic": pv}
    return ok, diff


def main() -> int:
    ap = argparse.ArgumentParser(description="F-057 ledger parity gate: CLI-equivalent vs programmatic BacktestRunner")
    ap.add_argument("--csv", required=True)
    ap.add_argument("--instrument", required=True)
    ap.add_argument("--pip-size", type=float, default=0.01)
    ap.add_argument("--check", action="store_true", help="exit 1 on divergence (CI mode)")
    args = ap.parse_args()

    ok, diff = run_parity_check(args.csv, args.instrument, args.pip_size)
    if ok:
        print(f"PASS — {args.instrument}: governed and programmatic ledgers are identical.")
        return 0

    print(f"FAIL — {args.instrument}: ledgers diverge on {len(diff)} field(s):")
    print(json.dumps(diff, indent=2, default=str))
    return 1 if args.check else 0


if __name__ == "__main__":
    raise SystemExit(main())
