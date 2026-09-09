"""
crt_threshold_authority_census.py
==================================
READ-ONLY census of every source that can supply a CRTConfig field's value, and what the real
production resolver actually resolves it to. v3 (2026-08-31, Phase E0 / CR-1): corrects a v2
defect that still missed a FIFTH authority for one specific field.

The six sources (five value-supplying layers + the resolver's separate authority)
    CODE      -- the CRTConfig dataclass default (src/config_layer/state_identity.py:136).
                 Fallback of last resort; a field reaching this un-declared anywhere is the real
                 silent-default risk.
    ROUTER    -- configs/production/<ACTIVE_VERSION>.json:market_router.classes[FOREX|CRYPTO].
                 Per-instrument-CLASS base, applied by market_router.get_crt_config() BEFORE
                 crt_engine/params. Declares only 5 keys today.
    ENGINE    -- configs/production/<ACTIVE_VERSION>.json:crt_engine. Applied via
                 dataclasses.replace on top of ROUTER (production_config.py: "params section wins
                 over crt_engine defaults").
    PARAMS    -- configs/production/<ACTIVE_VERSION>.json:params. Wins over ENGINE
                 unconditionally, for every instrument -- see Finding below.
    EXTERNAL  -- a config section OUTSIDE the crt_engine/params pair, applied by the loader AFTER
                 that merge. Only field with this shape today: `allowed_sessions`, owned by
                 `engine_runner.allowed_sessions` (config_layer.crt_config_completeness.
                 EXTERNALLY_OWNED_FIELDS -- imported, not re-declared here, so the two modules
                 cannot drift on which fields these are).
    YAML      -- configs/formulas/market_crt_states.yaml:thresholds. A SEPARATE authority read
                 only by CRTStateResolver (src/features/crt_state_resolver.py), never by
                 crt_engine_v2 / CRTConfig. Comparing YAML to RESOLVED answers "does the resolver
                 disagree with the engine", which is the question this migration exists to answer.

RESOLVED is not reimplemented here -- it is the actual production CRTConfig, built by calling
config_layer.production_config.load_prod_config_from_registry() for a reference instrument
(XAUUSD, this repo's primary corpus). This is deliberate: the precedence chain has FIVE layers
(ROUTER -> ENGINE -> PARAMS -> EXTERNAL(engine_runner) -> instrument_overrides) and hand-merging
them a second time here would just be a second place for that logic to drift from the real one.
Calling the real function means RESOLVED is provably correct by construction, not by
re-derivation.

Finding embedded in this script (verified, not assumed): on the active config, ROUTER's FOREX vs
CRYPTO differentiation is INERT for the 5 keys it declares -- PARAMS unconditionally overrides all
5 for every instrument, so load_prod_config_from_registry(..., "XAUUSD") and
load_prod_config_from_registry(..., "BTCUSDT") resolve identically on those 5 fields despite
ROUTER declaring different FOREX/CRYPTO values. Reported as router_class_differentiation_inert.

Per-field classification
    UNDECLARED       -- absent from ROUTER, ENGINE, PARAMS, and (for the 1 EXTERNAL field) its
                         real owning section. RESOLVED falls through to the bare CODE default with
                         zero declaration anywhere. The real risk class.
    DECLARED_DEFAULT  -- declared somewhere, and RESOLVED == CODE default (coincidence, not risk;
                         the value is committed, it just happens to match the fallback).
    DECLARED_TUNED    -- declared somewhere, and RESOLVED != CODE default (expected -- production
                         tuning away from the raw default).

YAML/RESOLVED verdict (only for the keys market_crt_states.yaml:thresholds also names):
    agree     -- YAML == RESOLVED
    diverged  -- YAML != RESOLVED (CRTStateResolver and crt_engine_v2 see different numbers)

Non-scalar fields (session_windows, sizing_bands, conf_weights, risk_score_weights,
score_component_weights) are compared via the SAME coercion production_config.py applies
(_coerce_crt_engine), not a raw JSON-vs-Python-type diff -- v1 mis-flagged 2 of these as
"differs" purely because JSON has no tuple type.

History
    v1 (2026-08-31) compared CODE / YAML / PARAMS only -- 3 of what turned out to be 6 sources.
    v2 (2026-08-31, same day) added ROUTER + ENGINE, correcting v1's "48 of 53 fields run on CODE
    defaults" to the real picture: only 3 fields genuinely undeclared anywhere (RESOLVED falls
    through to CODE with zero declaration); the other 45 "48-of-53" fields are explicitly declared
    in ENGINE (40 of them just happen to equal CODE default). v2's 3-field undeclared set was
    ITSELF wrong, caught starting Phase E's code review: `allowed_sessions` is declared, just in a
    SIXTH place v2 never checked (`engine_runner.allowed_sessions`, applied by the loader AFTER
    the crt_engine/params merge) -- the exact same class of miss as v1->v2 (a missed authority),
    recurring on one field. Corrected here to 2 (later 1, see below): allowed_sessions moves from
    UNDECLARED to DECLARED_DEFAULT (declared_where now includes "engine_runner"). The
    YAML-vs-RESOLVED divergence set (retest_depth_max, retest_atr_depth_fraction) was UNCHANGED
    by this correction -- allowed_sessions was never part of that set.

    Phase E1 (2026-08-31, same day): retest_depth_max measured non-pivotal for the resolver at
    0.08/0.15/0.25 (scripts/research/e1_retest_depth_max_probe.py -- byte-identical agreement and
    RETEST recall across all three), then aligned in market_crt_states.yaml 0.08 -> 0.15 to match
    production. `_PINNED_YAML_DIVERGED_KEYS` is now 1 key (retest_atr_depth_fraction only), a dead
    duplicate the resolver never reads (Phase D), retained per Phase E2 rather than adjudicated as
    a live value conflict.

Usage
    python scripts/analysis/crt_threshold_authority_census.py            # prints + writes JSON
    python scripts/analysis/crt_threshold_authority_census.py --check    # exit 1 if the pinned
                                                                          # instrument changed
"""
from __future__ import annotations

import argparse
import dataclasses
import io
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
CRT_STATES_YAML = ROOT / "configs" / "formulas" / "market_crt_states.yaml"
ACTIVE_VERSION_FILE = ROOT / "configs" / "production" / "ACTIVE_VERSION"
OUT_JSON = ROOT / "data" / "crt_threshold_authority_census.json"

REFERENCE_INSTRUMENT = "XAUUSD"      # this repo's primary corpus (memory: xauusd_only rule)
CROSS_CLASS_INSTRUMENT = "BTCUSDT"   # CRYPTO-class instrument, used only to test ROUTER inertness

sys.path.insert(0, str(SRC))
from config_layer.crt_config_completeness import EXTERNALLY_OWNED_FIELDS  # noqa: E402

# Pinned at authorship time (2026-08-31), ACTIVE_VERSION=v2_htfcrt_2026_08. YAML disagrees with
# RESOLVED on exactly this 1 key (was 2 -- retest_depth_max REMOVED 2026-08-31, Phase E1: measured
# non-pivotal for the resolver at 0.08/0.15/0.25 via
# scripts/research/e1_retest_depth_max_probe.py, then aligned YAML 0.08 -> 0.15 to match
# production, closing the divergence for real). retest_atr_depth_fraction remains diverged
# (0.5 YAML vs 0.3 resolved) but is a DEAD duplicate -- Phase D found the resolver never reads it
# (consumed:false) -- per Phase E2, retained as-is and already honestly marked, not adjudicated
# as a live value conflict. --check fails if this set changes, so a later edit is caught the
# moment it (intentionally or not) moves a declared value.
_PINNED_YAML_DIVERGED_KEYS = frozenset({
    "retest_atr_depth_fraction",
})

# Pinned truly-undeclared set (RESOLVED falls through to bare CODE default via no declaration
# anywhere in ROUTER/ENGINE/PARAMS/EXTERNAL). If Phase C ("CRTConfig becomes defaultless") is
# done right, this set should SHRINK to empty, never grow. `allowed_sessions` is NOT in this set
# -- it is declared via engine_runner.allowed_sessions (EXTERNAL), corrected 2026-08-31 (CR-1).
_PINNED_UNDECLARED_KEYS = frozenset({
    "displacement_origin_kill_enabled",
    "displacement_origin_kill_precedence",
})


def _load_yaml_utf8(path: Path) -> dict:
    # NOTE: yaml.safe_load(open(path)) dies on cp1252 for this file on Windows. Force utf-8.
    with io.open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _as_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _jsonable(v):
    """Render a resolved CRTConfig field value (which may be a tuple, dict-of-time, etc.) into
    something json.dumps can serialize, without lying about the value."""
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (tuple, list)):
        return [_jsonable(x) for x in v]
    if hasattr(v, "isoformat"):  # datetime.time
        return v.isoformat()
    return v


def build_census() -> dict:
    from config_layer.state_identity import CRTConfig
    from config_layer.production_config import load_prod_config_from_registry

    active_version = ACTIVE_VERSION_FILE.read_text(encoding="utf-8").strip()
    prod_json = json.loads(
        (ROOT / "configs" / "production" / f"{active_version}.json").read_text(encoding="utf-8")
    )
    router_classes = (prod_json.get("market_router") or {}).get("classes", {})
    crt_engine_section = prod_json.get("crt_engine", {})
    params_section = prod_json.get("params", {})
    # EXTERNAL: fields whose real declaration site is a section outside crt_engine/params,
    # applied by the loader AFTER that merge (config_layer.production_config's post-merge
    # mutations, e.g. resolve_allowed_sessions). Set imported from crt_config_completeness so
    # this script and that module cannot independently drift on which fields these are.
    external_sections = {
        field: prod_json.get(owner.split(".", 1)[0], {})
        for field, owner in EXTERNALLY_OWNED_FIELDS.items()
    }

    yaml_doc = _load_yaml_utf8(CRT_STATES_YAML)
    yaml_thresholds = {
        k: v for k, v in (yaml_doc.get("thresholds") or {}).items()
        if not isinstance(v, dict)  # skip the nested `lifecycle` block
    }

    bare = CRTConfig()
    resolved_ref = load_prod_config_from_registry(active_version, REFERENCE_INSTRUMENT)
    resolved_cross = load_prod_config_from_registry(active_version, CROSS_CLASS_INSTRUMENT)

    fields = [f.name for f in dataclasses.fields(CRTConfig)]
    rows = []
    undeclared = []
    yaml_diverged = []
    router_inert_keys = []

    for f in fields:
        code_default = getattr(bare, f)
        resolved_value = getattr(resolved_ref, f)
        resolved_cross_value = getattr(resolved_cross, f)

        declared_where = []
        if f in router_classes.get("FOREX", {}) or f in router_classes.get("CRYPTO", {}):
            declared_where.append("router")
        if f in crt_engine_section:
            declared_where.append("crt_engine")
        if f in params_section:
            declared_where.append("params")
        if f in EXTERNALLY_OWNED_FIELDS:
            owner_section, _, owner_key = EXTERNALLY_OWNED_FIELDS[f].partition(".")
            if owner_key in external_sections.get(f, {}):
                declared_where.append(owner_section)

        if not declared_where:
            classification = "UNDECLARED"
            undeclared.append(f)
        elif resolved_value == code_default:
            classification = "DECLARED_DEFAULT"
        else:
            classification = "DECLARED_TUNED"

        router_inert = False
        if "router" in declared_where:
            router_inert = (resolved_value == resolved_cross_value)
            if router_inert:
                router_inert_keys.append(f)

        yaml_value = yaml_thresholds.get(f)
        yaml_verdict = None
        if yaml_value is not None:
            ry, rv = _as_float(yaml_value), _as_float(resolved_value)
            if ry is not None and rv is not None:
                yaml_verdict = "agree" if ry == rv else "diverged"
                if yaml_verdict == "diverged":
                    yaml_diverged.append(f)
            else:
                yaml_verdict = "unparseable"

        rows.append({
            "field": f,
            "code_default": _jsonable(code_default),
            "router_forex": _jsonable(router_classes.get("FOREX", {}).get(f)),
            "router_crypto": _jsonable(router_classes.get("CRYPTO", {}).get(f)),
            "crt_engine": _jsonable(crt_engine_section.get(f)),
            "params": _jsonable(params_section.get(f)),
            "resolved_xauusd": _jsonable(resolved_value),
            "resolved_btcusdt": _jsonable(resolved_cross_value),
            "yaml_threshold": _jsonable(yaml_value),
            "declared_where": declared_where,
            "classification": classification,
            "router_class_differentiation_inert": router_inert,
            "yaml_vs_resolved_verdict": yaml_verdict,
        })

    return {
        "active_version": active_version,
        "reference_instrument": REFERENCE_INSTRUMENT,
        "cross_class_instrument": CROSS_CLASS_INSTRUMENT,
        "field_count": len(fields),
        "router_field_count": len({k for v in router_classes.values() for k in v}),
        "crt_engine_field_count": len(crt_engine_section),
        "params_field_count": len(params_section),
        "yaml_threshold_count": len(yaml_thresholds),
        "undeclared_fields": sorted(undeclared),
        "router_class_differentiation_inert_fields": sorted(router_inert_keys),
        "yaml_diverged_fields": sorted(yaml_diverged),
        "rows": rows,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check", action="store_true",
        help="exit 1 if the pinned undeclared-set or yaml-divergence-set changed",
    )
    args = ap.parse_args(argv)

    report = build_census()

    print(f"ACTIVE_VERSION      : {report['active_version']}")
    print(f"CRTConfig fields    : {report['field_count']}")
    print(f"ROUTER fields       : {report['router_field_count']}  (FOREX/CRYPTO base)")
    print(f"crt_engine fields   : {report['crt_engine_field_count']}")
    print(f"params fields       : {report['params_field_count']}")
    print(f"YAML thresholds     : {report['yaml_threshold_count']}")
    print()
    print(f"UNDECLARED anywhere ({len(report['undeclared_fields'])}): "
          f"{report['undeclared_fields']}")
    print(f"ROUTER differentiation INERT ({len(report['router_class_differentiation_inert_fields'])}): "
          f"{report['router_class_differentiation_inert_fields']}")
    print(f"YAML vs RESOLVED diverged ({len(report['yaml_diverged_fields'])}): "
          f"{report['yaml_diverged_fields']}")
    print()
    header = (f"{'field':36s} {'code':>8s} {'router(F/C)':>14s} {'engine':>8s} "
              f"{'params':>8s} {'resolved':>10s} {'yaml':>8s}   class / yaml-verdict")
    print(header)
    print("-" * len(header))
    for r in report["rows"]:
        rf = r["router_forex"]
        rc = r["router_crypto"]
        rfc = f"{rf}/{rc}" if rf is not None else "--"
        print(
            f"{r['field']:36s} {str(r['code_default']):>8s} {rfc:>14s} "
            f"{str(r['crt_engine']):>8s} {str(r['params']):>8s} "
            f"{str(r['resolved_xauusd']):>10s} {str(r['yaml_threshold']):>8s}   "
            f"{r['classification']} / {r['yaml_vs_resolved_verdict']}"
        )

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {OUT_JSON.relative_to(ROOT)}")

    if args.check:
        ok = True
        actual_undeclared = frozenset(report["undeclared_fields"])
        if actual_undeclared != _PINNED_UNDECLARED_KEYS:
            print(
                f"\nINSTRUMENT DRIFT (undeclared set): "
                f"added={sorted(actual_undeclared - _PINNED_UNDECLARED_KEYS)} "
                f"removed={sorted(_PINNED_UNDECLARED_KEYS - actual_undeclared)}",
                file=sys.stderr,
            )
            ok = False
        actual_diverged = frozenset(report["yaml_diverged_fields"])
        if actual_diverged != _PINNED_YAML_DIVERGED_KEYS:
            print(
                f"\nINSTRUMENT DRIFT (yaml-divergence set): "
                f"added={sorted(actual_diverged - _PINNED_YAML_DIVERGED_KEYS)} "
                f"removed={sorted(_PINNED_YAML_DIVERGED_KEYS - actual_diverged)}",
                file=sys.stderr,
            )
            ok = False
        if not ok:
            return 1
        print("\n--check OK: both pinned sets match the frozen instrument.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
