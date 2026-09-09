"""vcrt_remeasure_v2.py — run a sealed Visual CRT measurement contract.

Thin CLI wrapper (CLAUDE.md section 3.3: no business logic here). All orchestration lives in
``src/research/visual_crt/measure.py``; all parameters live in the sealed contract JSON.

Default target is MC-VCRT-XAUUSD-M15-V2, the re-measurement of the Visual CRT trade object
(SEM-012 v2) under F-082's corrected measurement basis: the SEM-015 measured broker cost model
and the SEM-016 adverse stop-fill model. Pass ``--contract`` to run V1 instead, which is how the
V1 baseline is reproduced.

AUTHORITY: diagnostic only. ``economic_claims_allowed`` is false on every MC-VCRT instance;
mt00/mt01 are UNRUN and 0/27 E-MT-01 probes exist repo-wide. Nothing this script prints is an
economic validation, whatever the sign of the result.

Examples
--------
    python scripts/research/vcrt_remeasure_v2.py
    python scripts/research/vcrt_remeasure_v2.py --contract MC-VCRT-XAUUSD-M15-V1 \
        --out-dir results/visual_crt/_v1_reproduction
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT, _ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from research.visual_crt.measure import run_contract  # noqa: E402

CONTRACT_DIR = _ROOT / "configs" / "research" / "measurement_contracts" / "instances"
DEFAULT_CONTRACT = "MC-VCRT-XAUUSD-M15-V2"


def _default_out_dir(contract_id: str) -> Path:
    return _ROOT / "results" / "visual_crt" / contract_id.lower().replace("-", "_")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--contract", default=DEFAULT_CONTRACT,
                    help=f"MC-* contract id under {CONTRACT_DIR.name}/ (default: {DEFAULT_CONTRACT})")
    ap.add_argument("--out-dir", default=None,
                    help="output directory (default: results/visual_crt/<contract_id lowercased>)")
    args = ap.parse_args(argv)

    contract_path = CONTRACT_DIR / f"{args.contract}.json"
    if not contract_path.is_file():
        ap.error(f"no such contract: {contract_path}")
    out_dir = Path(args.out_dir) if args.out_dir else _default_out_dir(args.contract)

    metrics = run_contract(contract_path, out_dir)

    print(f"contract   : {metrics['contract_id']}")
    print(f"corpus     : {metrics['corpus']['bars']} bars  sha256 {metrics['corpus']['sha256'][:16]}...")
    print(f"authority  : {metrics['authority']}")
    print()
    for arm, b in metrics["arms"].items():
        g, n_ = b["gross"], b["net"]
        print(f"ARM {arm}  n={b['n']}  ({b['entry_rule']})  outcomes={b['outcomes']}")
        print(f"   gross  mean {g['mean_R']:+.6f}R  t={g['t']:+.3f}  "
              f"CI97.5 [{g['ci975'][0]:+.4f}, {g['ci975'][1]:+.4f}]  "
              f"excludes_zero={g['excludes_zero']}")
        print(f"   net    mean {n_['mean_R']:+.6f}R  t={n_['t']:+.3f}  "
              f"CI97.5 [{n_['ci975'][0]:+.4f}, {n_['ci975'][1]:+.4f}]  "
              f"PF={b['profit_factor_net']}")
        print(f"   verdict: {b['verdict']}")
        sp = metrics["splits"].get(arm)
        if sp:
            print(f"   split  IS n={sp['counts']['is']} net {sp['is']['mean_R']:+.6f}R  |  "
                  f"OOS n={sp['counts']['oos']} net {sp['oos']['mean_R']:+.6f}R  "
                  f"(purged {sp['counts']['purged']}, embargoed {sp['counts']['embargoed']})")
        ct = metrics["controls"].get(arm)
        if ct:
            print(f"   control long_only     net {ct['long_only']['net']['mean_R']:+.6f}R  "
                  f"-> arm beats it: {ct['arm_beats_long_only']}")
            print(f"   control random_entry  net {ct['random_entry']['net']['mean_R']:+.6f}R  "
                  f"-> arm beats it: {ct['arm_beats_random_entry']}")
        print()
    print(f"CONCLUSION : {metrics['conclusion']}")
    print(f"artifacts  : {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
