#!/usr/bin/env python
"""RC-003 — are the directional-contract-violation bars a distinct object at all?

Thin CLI wrapper. All logic lives in ``src/research/rc003_distinct_object/driver.py``.
Executes the frozen pre-registration ``docs/research/preregistration-rc003-distinct-object.md``
(sha256 verified at run time; the run aborts if the frozen text changed).

Diagnostic only. PL-0, economic_claims_allowed: false. No ontology, config, predicate,
or F-074 authority at any outcome.

Usage:
  python scripts/research/rc003_distinct_object.py \
      --corpus data/mt5/XAUUSD_M15.csv \
      --out docs/research-readiness/rc003_distinct_object
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from research.rc003_distinct_object import run_rc003  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus", default="data/mt5/XAUUSD_M15.csv")
    p.add_argument("--out", default="docs/research-readiness/rc003_distinct_object")
    p.add_argument("--instrument", default="XAUUSD")
    a = p.parse_args(argv)

    res = run_rc003(a.corpus, a.out, instrument=a.instrument)
    print(json.dumps(res, indent=2))

    if res["insufficient"]:
        print("\nSTOP CONDITION: raw n below the declared floor in at least one group.")
        print("Per pre-registration section 8 this is INSUFFICIENT — no claim is made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
