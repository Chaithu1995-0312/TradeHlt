"""
crt_declare_all_knobs_parity.py
================================
Phase B of the "CRT single source of truth" plan (2026-08-31 session).

Declares 47 of the 53 CRTConfig fields into `params` (the one authority `crt_engine_v2` reads
LAST and therefore actually runs on, per production_config.py's merge order) at their CURRENT
RESOLVED value, and proves the change is decision-neutral -- a byte-identical XAUUSD backtest
ledger before and after. 5 fields (session_windows, sizing_bands, conf_weights,
risk_score_weights, score_component_weights) are excluded because `params` is not type-coerced
the way `crt_engine` is -- see `_EXCLUDED_NONSCALAR_FIELDS`. A 6th field, `allowed_sessions`, is
excluded for a DIFFERENT reason: it is owned by `engine_runner.allowed_sessions`, applied by the
loader AFTER the crt_engine/params merge and unconditionally overwriting anything `params`
supplies -- declaring it here would be an inert write. (Corrected 2026-08-31, Phase E0 / CR-1:
an earlier version of this script DID declare it into params, silently overwritten every time;
caught by code review, not by the parity run, since an inert write produces a byte-identical
ledger either way.)

SAFETY -- never touches the live ACTIVE_VERSION file
------------------------------------------------------
`configs/production/<ACTIVE_VERSION>.json` is read by every concurrent process in this repository
via `production_config.load_prod_config_from_registry`, which hash-verifies `params` on every
load. Editing it in place without an atomic hash update would break that verification for every
other session mid-run. This script NEVER writes to the repo's own `configs/` tree -- it builds two
throwaway isolated roots (`src/utils/isolated_config_root.build_config_root`, the same mechanism
`v3_config_parity.py` uses), each with its OWN private copy of `configs/`, runs a full backtest in
each, and diffs the resulting ledgers. Nothing under the real `configs/production/` is written by
this script, ever -- confirmed by construction, not by convention.

The declaration rule (decided 2026-08-31, see the plan's Phase B section; amended Phase E0)
---------------------------------------------------------------------------
For each of the 53 CRTConfig fields:
    - if externally owned (allowed_sessions): SKIP -- declaring it in params would be inert
    - elif declared in `crt_engine`: keep that raw JSON value (already the correct on-disk shape)
    - elif declared in `params`: keep that raw JSON value
    - else (the 2 genuinely-undeclared fields): write the CRTConfig code default, in the correct
      JSON-native shape for its type (list for tuple, plain literal for scalar)
`market_router.classes` is deliberately NOT folded in -- Phase A measured its FOREX/CRYPTO
differentiation as already fully shadowed by `params` for every instrument, so incorporating it
would encode a differentiation that currently does nothing. `crt_engine` itself is left in place,
now fully redundant (a fact this run proves, not assumes) -- its removal is a separate,
later decision (the plan's Phase D/G), never bundled with this declaration.

Usage
    python scripts/analysis/crt_declare_all_knobs_parity.py [--csv PATH] [--keep]
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from utils.isolated_config_root import build_config_root, run_backtest  # noqa: E402
#: Canonical definitions live in Phase C's src/config_layer/crt_config_completeness.py -- imported
#: here rather than duplicated, so this script and that module can never independently drift on
#: which fields are coercion-sensitive or externally-owned.
from config_layer.crt_config_completeness import (  # noqa: E402
    EXTERNALLY_OWNED_FIELDS,
    NONSCALAR_UNCOERCED_IN_PARAMS_FIELDS as _EXCLUDED_NONSCALAR_FIELDS,
)

ACTIVE_VERSION_FILE = ROOT / "configs" / "production" / "ACTIVE_VERSION"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _undeclared_field_literal(field: str, jsonable_default) -> object:
    """JSON-native literal for a field that has no crt_engine/params entry yet.

    `jsonable_default` is the census's own `_jsonable(bare_CRTConfig_default)` -- already run
    through the same tuple->list / time->isoformat coercion production_config.py's loader expects
    on the way IN (via `_coerce_crt_engine`), so for these 2 fields (neither time-typed) it is
    already the correct on-disk shape. Hand-checked against the known bare defaults below -- do
    not derive this generically; these are the only 2 fields this applies to. (`allowed_sessions`
    was a 3rd entry here before Phase E0 / CR-1 -- removed, it is externally owned, never
    undeclared; see EXTERNALLY_OWNED_FIELDS.)"""
    expected = {
        "displacement_origin_kill_enabled": False,
        "displacement_origin_kill_precedence": "after_resting_fills",
    }
    if field not in expected:
        raise AssertionError(f"unexpected undeclared field {field!r} -- census drifted, re-verify")
    assert jsonable_default == expected[field], (field, jsonable_default, expected[field])
    return jsonable_default


def build_declared_params(active_config: dict, census_report: dict) -> dict:
    """Return the params dict for the 'declare everything (scalar-safe)' arm -- 47 of 53 fields.
    Excluded: the 5 in _EXCLUDED_NONSCALAR_FIELDS (stay declared via crt_engine only) and the 1 in
    EXTERNALLY_OWNED_FIELDS (allowed_sessions -- declaring it here would be an inert write,
    unconditionally overwritten by engine_runner.allowed_sessions after this merge; see module
    docstring, CR-1)."""
    crt_engine = active_config.get("crt_engine", {})
    params = active_config.get("params", {})

    declared: dict = {}
    for row in census_report["rows"]:
        field = row["field"]
        if field in _EXCLUDED_NONSCALAR_FIELDS or field in EXTERNALLY_OWNED_FIELDS:
            continue
        if field in crt_engine:
            declared[field] = crt_engine[field]
        elif field in params:
            declared[field] = params[field]
        else:
            declared[field] = _undeclared_field_literal(field, row["code_default"])
    return declared


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

    version = ACTIVE_VERSION_FILE.read_text(encoding="utf-8").strip()
    print(f"ACTIVE_VERSION (read-only, never written) : {version}")

    census = _load_module(
        "crt_threshold_authority_census",
        ROOT / "scripts" / "analysis" / "crt_threshold_authority_census.py",
    )
    report = census.build_census()
    if report["active_version"] != version:
        raise SystemExit(
            f"census ran against {report['active_version']!r} but ACTIVE_VERSION is now "
            f"{version!r} -- re-run the census before this script."
        )

    active_config_path = ROOT / "configs" / "production" / f"{version}.json"
    active_config = json.loads(active_config_path.read_text(encoding="utf-8"))
    declared_params = build_declared_params(active_config, report)
    print(f"declared params: {len(declared_params)} keys "
          f"(was {len(active_config.get('params', {}))})")

    from config_layer.production_config import _compute_params_hash  # noqa: E402

    def _mutate_declare_all(cfg: dict) -> None:
        cfg["params"] = copy.deepcopy(declared_params)
        cfg["config_hash"] = _compute_params_hash(cfg["params"])

    v3_parity = _load_module(
        "v3_config_parity", ROOT / "scripts" / "analysis" / "v3_config_parity.py"
    )

    tmp = Path(tempfile.mkdtemp(prefix="crt_declare_all_knobs_"))
    print(f"scratch roots: {tmp}")
    print(f"corpus       : {corpus_rel} (via junctioned data/)")
    try:
        baseline_root = build_config_root(ROOT, tmp / "baseline", version)
        declared_root = build_config_root(
            ROOT, tmp / "declared", version, mutate_config=_mutate_declare_all
        )

        print("\nrunning baseline (unmodified active config) ...", flush=True)
        baseline_out = run_backtest(ROOT, baseline_root, corpus_rel, args.instrument)
        print(f"  -> {baseline_out}")

        print("\nrunning declared (all 53 knobs in params) ...", flush=True)
        declared_out = run_backtest(ROOT, declared_root, corpus_rel, args.instrument)
        print(f"  -> {declared_out}")

        ok = v3_parity.compare(
            baseline_out, declared_out, args.instrument,
            "Phase B: baseline params (5 keys) vs declared params (47 keys)",
            expect_version_stamp_differs=False,
        )

        print("\n" + "=" * 68)
        print(f"  PHASE B PARITY: {'PASS' if ok else 'FAIL'}")
        print("=" * 68)
        return 0 if ok else 1
    finally:
        if args.keep:
            print(f"\nscratch roots kept at {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
