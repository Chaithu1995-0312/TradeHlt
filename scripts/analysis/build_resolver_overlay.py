#!/usr/bin/env python
"""build_resolver_overlay.py — precompute the CRTStateResolver track for the chart tab.

THIN WRAPPER ONLY (CLAUDE.md §3.3): every decision lives in `src/charts/resolver_overlay.py`;
this file parses argv, calls the library, and prints. No business logic here.

Runs `FeaturePipeline` -> `CRTStateResolver` over a full M15 corpus (multi-minute) and
writes a per-bar cache under `results/charts/_resolver_cache/<INSTR>__<sha8>__<variant>/`.
The dashboard's `/api/chart_series` endpoint reads this cache; it NEVER computes the
resolver track in-request. Re-run this script after the corpus file changes (the cache is
keyed on the corpus's sha256, so a stale cache is reported as `UNAVAILABLE:stale_cache`
rather than silently served).

Examples
--------
    python scripts/analysis/build_resolver_overlay.py --instrument XAUUSD

    python scripts/analysis/build_resolver_overlay.py --instrument XAUUSD \
        --csv data/mt5/XAUUSD_M15.csv --variant default

Authority: descriptive only. Grants no economic claim, no G001 claim, no promotion
(CLAUDE.md §6.5). The resolver track is a DIFFERENT construction from the engine (spine)
track shown in the same tab, not a second measurement of it — see F-069.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from charts import resolver_overlay as ro                        # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Precompute the CRTStateResolver per-bar track for the dashboard's "
                    "Trade Chart tab.")
    p.add_argument("--instrument", default="XAUUSD")
    p.add_argument("--csv", default=None,
                   help="base M15 corpus (default data/mt5/<INSTRUMENT>_M15.csv)")
    p.add_argument("--variant", default=ro.DEFAULT_VARIANT,
                   help="resolver link-set variant id (default: all links off)")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    inst = args.instrument.upper()
    csv_path = args.csv or f"data/mt5/{inst}_M15.csv"

    print(f"[1/2] resolving CRT states over {csv_path} (FeaturePipeline + CRTStateResolver, "
          f"multi-minute pass)")
    out_dir = ro.build_and_cache(inst, csv_path, variant=args.variant)

    print(f"[2/2] cached -> {out_dir}")
    print(f"    states.csv  meta.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
