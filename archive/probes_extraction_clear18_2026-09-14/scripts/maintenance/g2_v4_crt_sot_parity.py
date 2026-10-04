"""g2_v4_crt_sot_parity.py — Phase G2 of the CRT single-source-of-truth plan.

Proves the REAL, COMMITTED v4_crt_sot_2026_08.json (built by G1) is decision-neutral vs the
active config, on the full XAUUSD corpus. This is the "prove it, don't argue it" step every prior
phase in this plan used -- Phase B already proved the 47-field declaration is inert INSIDE A
SCRATCH ROOT; this proves the real file that now exists on disk is too, which is a materially
different and stronger claim (a hand-edit between the scratch proof and the committed write is
exactly the class of defect this step exists to catch).

Uses isolated config roots (src/utils/isolated_config_root.py) for BOTH arms -- neither run ever
touches ACTIVE_VERSION or any concurrent session's view of the repo. Reuses v3_config_parity.py's
compare()/_compare_trades() rather than duplicating the diff logic (same pattern as Phase B's
crt_declare_all_knobs_parity.py).

Usage
    python scripts/maintenance/g2_v4_crt_sot_parity.py [--keep]
"""
from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from utils.isolated_config_root import build_config_root, run_backtest  # noqa: E402

BASELINE_VERSION = "v2_htfcrt_2026_08"
NEW_VERSION = "v4_crt_sot_2026_08"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--csv", default=None,
                     help="corpus path RELATIVE to the repo root; default data/mt5/<INSTRUMENT>_M15.csv")
    ap.add_argument("--keep", action="store_true", help="keep the scratch roots for inspection")
    args = ap.parse_args()

    corpus_rel = args.csv or f"data/mt5/{args.instrument}_M15.csv"
    if not (ROOT / corpus_rel).exists():
        raise SystemExit(f"corpus not found: {ROOT / corpus_rel}")

    for v in (BASELINE_VERSION, NEW_VERSION):
        if not (ROOT / "configs" / "production" / f"{v}.json").exists():
            raise SystemExit(f"missing config: {v}.json -- run g1_build_v4_crt_sot_config.py first"
                              if v == NEW_VERSION else f"missing config: {v}.json")

    v3_parity = _load_module("v3_config_parity", ROOT / "scripts" / "analysis" / "v3_config_parity.py")

    tmp = Path(tempfile.mkdtemp(prefix="g2_v4_crt_sot_parity_"))
    print(f"scratch roots: {tmp}")
    print(f"corpus       : {corpus_rel} (via junctioned data/)")
    try:
        baseline_root = build_config_root(ROOT, tmp / "baseline", BASELINE_VERSION)
        new_root = build_config_root(ROOT, tmp / "v4", NEW_VERSION)

        print(f"\nrunning baseline ({BASELINE_VERSION}) ...", flush=True)
        baseline_out = run_backtest(ROOT, baseline_root, corpus_rel, args.instrument)
        print(f"  -> {baseline_out}")

        print(f"\nrunning v4 ({NEW_VERSION}) ...", flush=True)
        new_out = run_backtest(ROOT, new_root, corpus_rel, args.instrument)
        print(f"  -> {new_out}")

        ok = v3_parity.compare(
            baseline_out, new_out, args.instrument,
            f"Phase G2: {BASELINE_VERSION} (47-key split-brain) vs {NEW_VERSION} (single-source params)",
            expect_version_stamp_differs=True,  # different version names, expected on trades.csv/summary.json
        )

        print("\n" + "=" * 68)
        print(f"  PHASE G2 PARITY: {'PASS' if ok else 'FAIL'}")
        print("=" * 68)
        return 0 if ok else 1
    finally:
        if args.keep:
            print(f"\nscratch roots kept at {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
