"""
feature_math_lint.py
====================
FEATURE-MATH OWNERSHIP LINT (read-only): enforce that governed feature quantities may only
ORIGINATE from registered implementations. The enforcement sibling of behavior_census.py
(config literals) and config_reachability.py (config keys); this audits feature-math ownership.

Authority model (CLAUDE.md §6.5): the ontology (configs/formulas/market_ontology.yaml) declares
the governed feature set; the registry (src/features/registry/) is the sole authoritative
implementation. A registered quantity must not be RE-DERIVED anywhere else.

Method (purely static, AST — SEMANTICS not syntax)
    For every src/ module NOT in the allowlist of authoritative math sources: find assignments
    whose TARGET NAME is a registered feature (leading underscores stripped; column aliases
    included, e.g. wick_size == candle_range), and classify the right-hand side:

      registry-call  (OK)  a call into candle_math / derived_math / the registry (or `.body_ratio(`).
      transport      (OK)  data movement, not derivation: Subscript (record["body_ratio"]),
                           Attribute read (candle.body_ratio), bare Name, or a literal (init).
      derivation  (VIOLATION)  the RHS COMPUTES the value — arithmetic (BinOp/UnaryOp), a
                           conditional over a computation, or a call to a NON-registry function
                           (np.divide, a bare helper()). Regardless of syntax.

    This is *ownership of the name* (who may derive it), stable as implementation styles change —
    not an arithmetic-pattern matcher. tests/ is fully exempt (fixtures/serialization are transport).

Pre-existing divergences are pinned in _KNOWN_DIVERGENCES (grandfathered debt, tracked to a
finding). The floor is GREEN over that pinned set today and FAILS on any NEW re-derivation.

Second check (added 2026-08-09, F-072): DIMENSIONAL-UNIT MISMATCH at known price-unit call
sites. Ownership (above) asks "who may derive this name"; this asks "does a close-relative
ratio reach a parameter that needs a price-unit value" for a small, explicit watch-list of
call sites — currently just `compute_crt_levels`'s `atr` parameter (FM-041 `atr` is
atr_14_raw/close; the function needs the FM-074 `atr_absolute` form). This is a NAMING-
CONVENTION heuristic, not true dimensional analysis: an argument expression is judged SAFE if
its unparsed source contains `_abs` or a `*`-multiplication naming `close`, else UNSAFE. It
scans ALL of src/ (not just _SCAN_DIRS) because the ownership lint's live-spine scoping is
exactly what let 2 of this defect's 3 real sites go unpoliced (research/model_runners/ is
outside _SCAN_DIRS). Pre-existing/intentionally-unfixed sites are pinned in
_KNOWN_DIMENSIONAL_MISMATCHES the same shrink-only way _KNOWN_DIVERGENCES works above — a pin
matches by (file, line, unparsed arg text); editing that line makes the pin stale and the site
resurfaces as NEW, forcing a conscious decision rather than silent continued exemption.

Usage
    python scripts/analysis/feature_math_lint.py            # writes JSON + MD report
    python scripts/analysis/feature_math_lint.py --check     # exit 1 on any NEW (unpinned) violation
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
sys.path.insert(0, str(_SRC))  # for `features.registry` (single source of the registered-name set)

from features.registry import load_ontology  # noqa: E402

# Live-surface packages where feature-math ownership is load-bearing: the feature pipeline, the
# scoring/decision spine, and the live hook. Dormant sidecars (strategies/ F-013-orphaned,
# regime/ + analytics/ sidecars F-012, research/) are EXCLUDED — reviving one brings it under the
# lint (mirrors behavior_census's live-spine scoping). Widen this set to expand coverage.
#
# UNIVERSE DELTA vs geometry_census.py (declared, 2026-07-11): the geometry census scans the
# WHOLE repository (tracked + untracked execution-capable *.py incl. scripts/ and tests/) for
# the F1–F9 geometry quantities; this lint scans only the live-spine src/ dirs below for ALL
# ontology-registered names. "No new unauthorized re-derivation" is therefore a live-spine
# guarantee here; repo-wide, the geometry census + its Gate-2B adjudication closure cover the
# geometry subset, and tests/test_feature_math_lint.py::test_universe_reconciliation_with_census
# mechanically enforces that no ontology-registered geometry derivation outside this lint's
# universe escapes census adjudication.
_SCAN_DIRS = ("features", "core", "config_layer", "engines", "runtime")

# ── Authoritative math sources (exempt): they DEFINE the math or are parity-bound to it. ──
_ALLOWLISTED_FILES = {
    "features/candle_math.py",
    "features/derived_math.py",
    "features/formula_registry.py",
    "features/feature_pipeline.py",   # vectorized authority — lint-exempt but PARITY-bound by tests
    # Phase 2A (2026-07-24): the LIVE-path mirror of feature_pipeline's structure block. Exempt on
    # the same basis as the pipeline itself: tests/test_fc1a_swing_causal.py asserts EXACT int8
    # equality against the pipeline for swing/HH/LL/BOS/sweep/double_sweep, and T-7 unified its
    # double_sweep_window lookup through resolve_double_sweep_window(). Surfaced only when the
    # structural_states registration put `double_sweep` under enforcement (line 152).
    "features/causal_structure.py",
}
_ALLOWLISTED_PREFIXES = ("features/registry/",)

# Column aliases: the feature vector / code names differ from the ontology name in one case.
_NAME_ALIASES: dict[str, tuple[str, ...]] = {
    "candle_range": ("wick_size",),
}

# Attribute roots / aliases that denote a registry/impl call source.
# (2026-07-11 hardening) The old static alias set (_MATH_MODULE_ROOTS) and leaf-name
# set (_REGISTRY_FUNCS) are RETIRED: registry authority is now provenance-verified
# per-module from actual imports (_registry_import_ctx / _REGISTRY_MODULE_PREFIXES
# below). `evil_module.body_ratio(...)` is no longer authoritative; any import alias
# of a real registry module is.

# Transport calls — data movement, NOT derivation: dict/attribute reads.
# T-16 (2026-07-23): +`_require`. The repo's strict accessors (`_require`, `_require_cfg`,
# `_require_bt_cfg`, `_require_fp_cfg`) return `d[key]` and raise when absent — the SAME data
# movement as `.get`, minus the fabricated default. Classifying them as derivation would create a
# perverse incentive: `x.get("ema_fast", 0.0)` would pass the ownership floor while the strictly
# safer `_require(x, "ema_fast", ...)` would fail it, pushing new code back toward silent defaults
# (CLAUDE.md §6.5 forbids exactly that). Detection power is unchanged: only the CALL is whitelisted,
# so a BinOp/UnaryOp/Compare inside still recurses to `derivation` — `features["macd_hist_raw"] =
# features["macd_line"] - features["macd_signal"]` still trips the floor (verified this session).
_TRANSPORT_CALLS = {"get", "pop", "setdefault", "getattr",
                    "_require", "_require_cfg", "_require_bt_cfg", "_require_fp_cfg"}
# Coercion wrappers — carry their argument's class through (float(x.get(...)) is transport if the
# arg is transport). Deliberately EXCLUDES abs/sum/exp (those COMPUTE → derivation).
# T-16 (2026-07-19): +asarray/array/astype/asfarray — numpy dtype coercion of an ALREADY-COMPUTED
# value carries its argument's class exactly like float()/int(). `np.asarray(atr, dtype=float)`
# where `atr` is a parameter is TRANSPORT, not a re-derivation; `np.asarray(high * low)` still
# recurses to a BinOp -> derivation, so detection power is preserved.
_COERCION_CALLS = {"float", "int", "bool", "str", "_safe_float", "_safe_int", "round",
                   "asarray", "array", "astype", "asfarray"}
# Bounding wrappers — clamp a consumed value: transport if ALL args are transport/const, else
# derivation (a clamp of a real computation stays a derivation, e.g. max(a/b, 0.0)).
_BOUND_CALLS = {"max", "min", "clip", "clamp"}

# ── Grandfather ledger (GD-001…GD-010). Durable, adjudicated, monotonically-shrinking debt. ──
# A pin matches a violation by `durable_key` (file+enclosing_qualname+target+kind+RHS-AST). Editing a
# site's formula OR moving it to another method makes the pin STALE → the site resurfaces as NEW. The
# floor stays green over the pins; any new re-derivation is a hard failure. Retirement is via the
# append-only manifest (docs/governance/feature-math-grandfather-retirements.json), never a source edit.
# Adjudication frozen in Matrix v1: docs/analysis/feature-math-divergence-adjudication.md (2026-07-07).
_KNOWN_DIVERGENCES: list[dict] = [
    # GD-001 / GD-002 / GD-003 RETIRED 2026-07-10 (Phase-1 identity closure):
    # live_engine_hook routes body_size / total_wick / body_to_total_wick_ratio through
    # candle_math; durable_keys gone from scan. See feature-math-grandfather-retirements.json.
    # GD-004 / GD-005 RETIRED 2026-07-11 (disp_strength identity closure): scoring_engine routes
    # through derived_math.disp_strength_atr_rescale (NEW FM-029); crt_engine_v2 [PATCH 7] routes
    # through derived_math.displacement_atr_ratio (FM-028). Bare `disp_strength` derivation is now
    # fully prohibited (no pinned exceptions). See feature-math-grandfather-retirements.json.
    # GD-006 / GD-007 RETIRED 2026-07-20 (T-15): RangeDetector.detect_sweep locals renamed
    # upper_wick/lower_wick -> sweep_uw_frac/sweep_lw_frac (diagnostic fractions; deliberately
    # NOT the registered FM-011/FM-012 names). durable_keys gone from scan. See retirements manifest.
    # GD-008 / GD-009 RETIRED 2026-07-20 (T-15): candle_geometry locals renamed the same way
    # (return-dict keys kept for API stability). durable_keys gone from scan.
    {
        "id": "GD-010", "feature_id": "FM-002", "file": "engines/rr_engine.py",
        "enclosing_qualname": "RREngine.compute", "target_symbol": "candle_range",
        "statement_kind": "Assign", "durable_key": "c090bd49a8872a77",
        "semantic_class": "same_quantity", "formula_equivalence": "byte_identical",
        "execution_reachability": "conditional", "decision_reachability": "conditional",
        "observed_value_drift": "zero", "observed_score_drift": "zero",
        "observed_decision_flips": "zero", "owner": "claude", "opened": "2026-07-07",
        "evidence": "candle_range = high-low == candle_math.candle_range (byte-identical). RREngine.compute "
                    "called at EngineRunner.run:683 (conditional on BACKTEST_ENGINE_GATE=1 in backtest; "
                    "unconditional live); candle_range denominator feeds polarity→fusion:787.",
        "review_trigger": "route through candle_math.candle_range (Phase-B, parity-neutral/determinism-gated)",
    },
]

# Immutable original baseline (the 10 grandfathered ids). New ids may NEVER appear; retirement is
# permanent (recorded in the manifest). Enforced by tests/test_feature_math_lint.py.
_ORIGINAL_BASELINE_IDS = frozenset(f"GD-{i:03d}" for i in range(1, 11))
_RETIREMENT_MANIFEST = _ROOT / "docs" / "governance" / "feature-math-grandfather-retirements.json"

# ── Dimensional-unit mismatch watch-list (F-072, 2026-08-09) ──────────────────────────────────
# Small, explicit set of (call name, price-unit param name) pairs known to have caused a
# close-relative-vs-absolute unit mismatch. Widen only when a NEW instance of this exact class
# is found — this is not a general unit-inference system (see module docstring).
_DIMENSIONAL_WATCHLIST: tuple[tuple[str, str], ...] = (
    ("compute_crt_levels", "atr"),
)

# Sites deliberately left unfixed this pass, pinned by (file, line, unparsed-arg-text) so an
# edit to the line invalidates the pin instead of silently continuing to exempt it.
# live_engine_hook.py:916 — F-073 (no live rail: HookedLiveEngine is never instantiated) is
# parked; fixing this site is scoped together with that decision, not this ontology-closure pass.
_KNOWN_DIMENSIONAL_MISMATCHES: tuple[dict, ...] = (
    {
        "id": "DM-001", "file": "runtime/live_engine_hook.py", "line": 916,
        "call": "compute_crt_levels", "param": "atr", "arg_text": "float(engine_input['atr'])",
        "finding": "F-072", "reason": "dead code per F-073 (HookedLiveEngine never instantiated); "
                                        "fix is scoped with the live-rail repair/retire decision, not here",
    },
)


def load_retirements() -> list[dict]:
    """Append-only retirement records. Missing manifest == nothing retired yet."""
    if not _RETIREMENT_MANIFEST.exists():
        return []
    return json.loads(_RETIREMENT_MANIFEST.read_text(encoding="utf-8")).get("retirements", [])


def _pinned_keys() -> set[str]:
    return {p["durable_key"] for p in _KNOWN_DIVERGENCES}


def _rel(path: Path) -> str:
    try:
        return path.relative_to(_SRC).as_posix()
    except ValueError:
        # out-of-tree module (e.g. a test snippet driving _scan_module directly)
        return path.name


def _is_allowlisted(rel: str) -> bool:
    return rel in _ALLOWLISTED_FILES or any(rel.startswith(p) for p in _ALLOWLISTED_PREFIXES)


def _registered_names(ont: dict | None = None) -> set[str]:
    """The governed feature set (ontology names) plus code/column aliases."""
    ont = ont or load_ontology()
    names: set[str] = set()
    # T-16 (2026-07-19): `rolling_indicators` added. Windowed identities (FM-040..050: atr, rsi_14,
    # ema_fast, ema_slow, true_range, swing_high, swing_low, macd_*, volatility_regime) were
    # first-class registered from 2026-07-12 but were NEVER policed here — un-flaggable by
    # construction, so the F-054 promotion conferred identity/lineage but no enforcement.
    # Item-2 (2026-07-19): +temporal_context (FM-051/052 hour_of_day/session). `session` has a
    # documented 4-way collision (pipeline 8/16 vs scanner 7/17 vs dataset_integrity calendar vs
    # M16-WU-SESSION-ENCODING); policing the name is the whole reason it was registered.
    # Phase 2A (2026-07-24): DERIVED from the registry's own section tuple, never re-declared.
    # The two notes above record this same bug happening twice — a section was registered in the
    # ontology but stayed absent from this hand-written list, so its names were "un-flaggable by
    # construction" and the promotion conferred identity without enforcement. It happened a THIRD
    # time with `structural_states` (registered 40 names when the ontology held 49). A literal here
    # is a silent enforcement hole by design; deriving it makes a new section policed on arrival.
    from features.registry import _ITERATED_SECTIONS

    for section in _ITERATED_SECTIONS:
        names |= set((ont.get(section) or {}).keys())
    for canon, aliases in _NAME_ALIASES.items():
        if canon in names:
            names |= set(aliases)
    return names


def _attr_root_leaf(func: ast.AST) -> tuple[str | None, str | None]:
    if isinstance(func, ast.Name):
        return func.id, func.id
    if isinstance(func, ast.Attribute):
        leaf = func.attr
        node: ast.AST = func
        while isinstance(node, ast.Attribute):
            node = node.value
        root = node.id if isinstance(node, ast.Name) else None
        return root, leaf
    return None, None


# Registry authority is PROVENANCE-VERIFIED (2026-07-11 hardening): a call counts as a
# registry call only when THIS module's imports prove the callee originates from one of
# these modules. A bare leaf-name match (`evil_module.body_ratio(...)`) is NOT authority.
_REGISTRY_MODULE_PREFIXES = (
    "features.candle_math",
    "features.derived_math",
    "features.formula_registry",
    "features.registry",
    # Phase-2 FM resolution layer (2026-07-11): binds FM ids -> registry callables via the
    # ontology + FORMULA_REGISTRY; fail-closed, never invents math (fm_resolve charter).
    "features.fm_resolve",
)


def _is_registry_module(dotted: str) -> bool:
    return any(dotted == p or dotted.startswith(p + ".") for p in _REGISTRY_MODULE_PREFIXES)


def _registry_import_ctx(tree: ast.AST) -> dict:
    """Per-module provenance: {module_aliases: {alias -> dotted module}, func_names: set,
    dispatch_maps: set}. dispatch_maps are module-level names bound from a provenance-verified
    registry call (e.g. `_FM_CRT = bind_phase2_crt_callables()`), so `_FM_CRT["FM-028"](...)`
    is registry authority — the map's contents come from the registry, not local math."""
    mod_aliases: dict[str, str] = {}
    func_names: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if _is_registry_module(a.name):
                    if a.asname:
                        mod_aliases[a.asname] = a.name
                    else:
                        # `import features.candle_math` → usable as features.candle_math.f()
                        mod_aliases[a.name.split(".")[0]] = a.name.split(".")[0]
        elif isinstance(n, ast.ImportFrom):
            base = n.module or ""
            for a in n.names:
                full = f"{base}.{a.name}" if base else a.name
                bound = a.asname or a.name
                if _is_registry_module(base):
                    # `from features.candle_math import body_ratio as br` → br is a
                    # registry FUNC (base itself is the registry module). Checked FIRST:
                    # `from features.registry.composition_registry import compute_composition`
                    # must land here, not in mod_aliases. The bound name may also be a
                    # SUBMODULE (`from features.registry import derived_registry`) — record
                    # it as a module alias too so `derived_registry.compute_derived(...)`
                    # resolves; both maps are provenance-verified either way.
                    func_names.add(bound)
                    mod_aliases[bound] = full
                elif _is_registry_module(full):
                    # `from features import candle_math as _cm` → _cm is a registry MODULE
                    mod_aliases[bound] = full

    # Second pass (needs the import maps above): module-level dispatch maps bound from a
    # provenance-verified registry call, e.g. `_FM_CRT = bind_phase2_crt_callables()`.
    partial_ctx = {"mod_aliases": mod_aliases, "func_names": func_names, "dispatch_maps": set()}
    dispatch_maps: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            targets, value = n.targets, n.value
        elif isinstance(n, ast.AnnAssign):     # `_FM_CRT: dict = bind_phase2_crt_callables()`
            targets, value = [n.target], n.value
        else:
            continue
        if not isinstance(value, ast.Call) or not _call_is_registry(value.func, set(), partial_ctx):
            continue
        for t in targets:
            if isinstance(t, ast.Name):
                dispatch_maps.add(t.id)
    return {"mod_aliases": mod_aliases, "func_names": func_names, "dispatch_maps": dispatch_maps}


def _dotted_module_of(func: ast.AST, mod_aliases: dict[str, str]) -> str | None:
    """Resolve the module part of an Attribute call to a dotted path via this file's imports."""
    if not isinstance(func, ast.Attribute):
        return None
    parts: list[str] = []
    node: ast.AST = func.value
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    root = node.id
    if root not in mod_aliases:
        return None
    resolved = mod_aliases[root]
    parts.reverse()
    return ".".join([resolved, *parts]) if parts else resolved


def _call_is_registry(func: ast.AST, registered: set[str], import_ctx: dict | None = None) -> bool:
    ctx = import_ctx or {"mod_aliases": {}, "func_names": set(), "dispatch_maps": set()}
    if isinstance(func, ast.Name):
        # bare call is authority only if imported FROM a registry module in this file
        return func.id in ctx["func_names"]
    if isinstance(func, ast.Subscript):
        # dispatch-map call: `_FM_CRT["FM-028"](...)` where the map was bound from a
        # provenance-verified registry call at module level (see _registry_import_ctx)
        return (isinstance(func.value, ast.Name)
                and func.value.id in ctx.get("dispatch_maps", set()))
    dotted = _dotted_module_of(func, ctx["mod_aliases"])
    if dotted is not None and _is_registry_module(dotted):
        return True
    return False


def _classify_rhs(node: ast.AST, registered: set[str], import_ctx: dict | None = None) -> str:
    """registry_call | transport | derivation (round-3: distinguish derivation from transport)."""
    if isinstance(node, ast.Call):
        if _call_is_registry(node.func, registered, import_ctx):
            return "registry_call"
        _root, leaf = _attr_root_leaf(node.func)
        if leaf in _TRANSPORT_CALLS:                 # x.get("body_ratio", 0.0), getattr(o, "x")
            return "transport"
        if leaf in _COERCION_CALLS:                   # float(features.get(...)) carries arg's class
            return _classify_rhs(node.args[0], registered, import_ctx) if node.args else "transport"
        if leaf in _BOUND_CALLS:                       # max/min/clip: clamp of a consumed value
            kinds = [_classify_rhs(a, registered, import_ctx) for a in node.args]
            return "derivation" if "derivation" in kinds else "transport"
        return "derivation"                           # np.divide(...), a bare helper() that computes
    if isinstance(node, (ast.BinOp, ast.UnaryOp, ast.Compare)):
        return "derivation"
    if isinstance(node, ast.BoolOp):
        # T-16 (2026-07-19): `x or 0.0` is null-coalescing DEFAULTING, not arithmetic. Classify like
        # IfExp / _BOUND_CALLS — derivation only if an operand actually computes. `a > b or c > d`
        # still resolves to derivation via its Compare operands, so detection power is preserved.
        kinds = [_classify_rhs(v, registered, import_ctx) for v in node.values]
        return "derivation" if "derivation" in kinds else "transport"
    if isinstance(node, ast.IfExp):
        # `<expr> if <cond> else <expr>` — derivation if either value branch computes.
        b = _classify_rhs(node.body, registered, import_ctx)
        o = _classify_rhs(node.orelse, registered, import_ctx)
        return "derivation" if "derivation" in (b, o) else "transport"
    if isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
        # comprehension producing values — derivation if its element expression computes
        return _classify_rhs(node.elt, registered, import_ctx)
    # Subscript / Attribute / Name / Constant / everything else = data movement, not derivation.
    return "transport"


def _target_names(target: ast.AST):
    """Yield governed-name candidates from ANY assignment target form (2026-07-11
    hardening): bare names, tuple/list destructuring incl. Starred, attribute targets
    (obj.body_ratio = ...) and constant-string subscript SINKS (df["body_ratio"] = ...)."""
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, ast.Starred):
        yield from _target_names(target.value)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for el in target.elts:
            yield from _target_names(el)
    elif isinstance(target, ast.Attribute):
        yield target.attr
    elif isinstance(target, ast.Subscript):
        sl = target.slice
        if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
            yield sl.value


def _build_parent_map(tree: ast.AST) -> dict:
    parents: dict = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            parents[c] = n
    return parents


def _enclosing_qualname(node: ast.AST, parents: dict) -> str:
    """module→class→function path enclosing `node` (e.g. 'EngineRunner.run')."""
    names: list[str] = []
    cur = parents.get(node)
    while cur is not None:
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(cur.name)
        cur = parents.get(cur)
    return ".".join(reversed(names)) or "<module>"


def _durable_key(rel: str, qualname: str, target: str, kind: str, rhs: ast.AST) -> str:
    """Location-independent, content-sensitive site identity. Editing the formula (rhs dump) OR
    moving it to another method (qualname) OR renaming the target changes the key → pin goes stale."""
    payload = "\0".join([rel, qualname, target, kind, ast.dump(rhs, annotate_fields=False)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _scan_module(path: Path, registered: set[str]) -> list[dict]:
    rel = _rel(path)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []
    parents = _build_parent_map(tree)
    import_ctx = _registry_import_ctx(tree)
    violations: list[dict] = []

    def _record(anode: ast.AST, raw: str, kind: str, value: ast.AST, forced: bool = False) -> None:
        canon = raw.lstrip("_")
        if canon not in registered:
            return
        if forced or _classify_rhs(value, registered, import_ctx) == "derivation":
            qualname = _enclosing_qualname(anode, parents)
            violations.append({
                "module": rel, "line": anode.lineno, "name": canon, "target": raw,
                "enclosing_qualname": qualname, "statement_kind": kind,
                "durable_key": _durable_key(rel, qualname, raw, kind, value),
                "key": f"{rel}::{canon}",  # legacy advisory label
            })

    # 2026-07-11 hardening: cover EVERY binding form a governed quantity can be
    # re-derived through — not just Assign/AnnAssign.
    for anode in ast.walk(tree):
        if isinstance(anode, ast.Assign):
            for t in anode.targets:
                for raw in _target_names(t):
                    _record(anode, raw, "Assign", anode.value)
        elif isinstance(anode, ast.AnnAssign):
            if anode.value is None:
                continue
            for raw in _target_names(anode.target):
                _record(anode, raw, "AnnAssign", anode.value)
        elif isinstance(anode, ast.AugAssign):
            # `x += expr` COMPUTES on the governed value by definition
            for raw in _target_names(anode.target):
                _record(anode, raw, "AugAssign", anode.value, forced=True)
        elif isinstance(anode, ast.NamedExpr):
            for raw in _target_names(anode.target):
                _record(anode, raw, "NamedExpr", anode.value)
        elif isinstance(anode, ast.For):
            # loop binding from a computing iterable (genexp/comprehension of math)
            for raw in _target_names(anode.target):
                _record(anode, raw, "ForTarget", anode.iter)
        elif isinstance(anode, ast.With):
            for item in anode.items:
                if item.optional_vars is not None:
                    for raw in _target_names(item.optional_vars):
                        _record(anode, raw, "WithTarget", item.context_expr)
        elif isinstance(anode, ast.Call):
            # dict/DataFrame sink: d.update({"governed": <expr>, ...})
            _root, leaf = _attr_root_leaf(anode.func)
            if leaf == "update":
                for arg in anode.args:
                    if isinstance(arg, ast.Dict):
                        for k, v in zip(arg.keys, arg.values):
                            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                                _record(anode, k.value, "DictUpdateSink", v)
    return violations


def _dim_pinned_keys() -> set[tuple[str, int, str]]:
    return {(p["file"], p["line"], p["arg_text"]) for p in _KNOWN_DIMENSIONAL_MISMATCHES}


def _find_calls(tree: ast.AST, name: str):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fname = None
            if isinstance(node.func, ast.Name):
                fname = node.func.id
            elif isinstance(node.func, ast.Attribute):
                fname = node.func.attr
            if fname == name:
                yield node


def _is_safe_price_unit_arg(text: str) -> bool:
    """Naming-convention heuristic (see module docstring) — not true unit inference."""
    if "_abs" in text:
        return True
    if "*" in text and "close" in text:
        return True
    return False


def _scan_dimensional_mismatches(src_root: Path) -> list[dict]:
    violations: list[dict] = []
    for path in sorted(src_root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = _rel(path)
        for call_name, param in _DIMENSIONAL_WATCHLIST:
            for call in _find_calls(tree, call_name):
                arg_node = None
                for kw in call.keywords:
                    if kw.arg == param:
                        arg_node = kw.value
                        break
                if arg_node is None:
                    continue  # positional-only call sites are not currently in the watch-list's usage
                text = ast.unparse(arg_node)
                if _is_safe_price_unit_arg(text):
                    continue
                violations.append({
                    "module": rel, "line": arg_node.lineno, "call": call_name,
                    "param": param, "arg_text": text,
                })
    return violations


def check_dimensional_violations(dim_violations: list[dict]) -> tuple[list[str], list[str]]:
    """Returns (new-problem messages, stale-pin messages). Empty both = clean."""
    pinned = _dim_pinned_keys()
    live_keys = {(v["module"], v["line"], v["arg_text"]) for v in dim_violations}
    new = [v for v in dim_violations if (v["module"], v["line"], v["arg_text"]) not in pinned]
    stale = [p for p in _KNOWN_DIMENSIONAL_MISMATCHES
             if (p["file"], p["line"], p["arg_text"]) not in live_keys]
    problems = [
        f"{v['module']}:{v['line']} — {v['call']}({v['param']}={v['arg_text']}) looks close-relative, "
        f"not price-unit (naming heuristic: expected '_abs' or a '* close' multiplication)"
        for v in new
    ]
    stale_msgs = [
        f"stale dimensional pin '{p['id']}' ({p['file']}:{p['line']}) — the line no longer matches; "
        f"re-adjudicate (fixed? re-pin the new text; moved? update line)"
        for p in stale
    ]
    return problems, stale_msgs


def build_report() -> dict:
    ont = load_ontology()
    registered = _registered_names(ont)
    all_violations: list[dict] = []
    scanned = 0
    scan_roots = [_SRC / d for d in _SCAN_DIRS]
    for path in sorted(_SRC.rglob("*.py")):
        rel = _rel(path)
        if not any(str(path).startswith(str(r)) for r in scan_roots):
            continue
        if _is_allowlisted(rel) or path.name == "__init__.py":
            continue
        scanned += 1
        all_violations.extend(_scan_module(path, registered))

    pinned = _pinned_keys()
    live_keys = {v["durable_key"] for v in all_violations}
    new_violations = [v for v in all_violations if v["durable_key"] not in pinned]
    known_present = sorted(pinned & live_keys)
    stale_pins = sorted(p["id"] for p in _KNOWN_DIVERGENCES if p["durable_key"] not in live_keys)

    retired = load_retirements()
    retired_ids = {r.get("gd_id") for r in retired}
    current_ids = {p["id"] for p in _KNOWN_DIVERGENCES}

    dim_violations = _scan_dimensional_mismatches(_SRC)
    dim_problems, dim_stale_msgs = check_dimensional_violations(dim_violations)
    dim_pinned = _dim_pinned_keys()
    dim_live_keys = {(v["module"], v["line"], v["arg_text"]) for v in dim_violations}
    dim_known_present = sorted(
        p["id"] for p in _KNOWN_DIMENSIONAL_MISMATCHES
        if (p["file"], p["line"], p["arg_text"]) in dim_pinned & dim_live_keys
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "modules_scanned": scanned,
            "total_derivations": len(all_violations),
            "new_violations": len(new_violations),
            "known_present": len(known_present),
            "stale_pins": len(stale_pins),
            "current_pins": len(current_ids),
            "retired": len(retired_ids),
            "registered_count": len(registered),
            "dimensional_new_violations": len(dim_problems),
            "dimensional_stale_pins": len(dim_stale_msgs),
            "dimensional_current_pins": len(_KNOWN_DIMENSIONAL_MISMATCHES),
        },
        "registered_names": sorted(registered),
        "new_violations": sorted(new_violations, key=lambda v: (v["module"], v["line"])),
        "known_present": known_present,
        "stale_pins": stale_pins,
        "pins": _KNOWN_DIVERGENCES,
        "ledger": {
            "original_baseline_ids": sorted(_ORIGINAL_BASELINE_IDS),
            "current_ids": sorted(current_ids),
            "retired_ids": sorted(i for i in retired_ids if i),
        },
        "dimensional": {
            "watchlist": [{"call": c, "param": p} for c, p in _DIMENSIONAL_WATCHLIST],
            "new_violations": sorted(
                [v for v in dim_violations
                 if (v["module"], v["line"], v["arg_text"]) not in dim_pinned],
                key=lambda v: (v["module"], v["line"]),
            ),
            "known_present": dim_known_present,
            "stale_pins": sorted(
                p["id"] for p in _KNOWN_DIMENSIONAL_MISMATCHES
                if (p["file"], p["line"], p["arg_text"]) not in dim_live_keys
            ),
            "pins": list(_KNOWN_DIMENSIONAL_MISMATCHES),
        },
    }


def check_violations(report: dict) -> list[str]:
    """Regression floor: messages for NEW (unpinned) re-derivations + stale pins. Empty = clean."""
    problems: list[str] = []
    for v in report["new_violations"]:
        problems.append(
            f"{v['module']}:{v['line']} — '{v['target']}' re-derives registered feature "
            f"'{v['name']}' outside the registry (route through candle_math/derived_math/registry)"
        )
    for gid in report["stale_pins"]:
        problems.append(
            f"stale pin '{gid}' — its site's durable_key no longer matches (formula edited / moved). "
            f"Re-adjudicate: retire it via the manifest if resolved, or re-pin the new site."
        )
    dim = report.get("dimensional", {})
    for v in dim.get("new_violations", []):
        problems.append(
            f"{v['module']}:{v['line']} — {v['call']}({v['param']}={v['arg_text']}) looks "
            f"close-relative, not price-unit (naming heuristic: expected '_abs' or a '* close' "
            f"multiplication) — see F-072"
        )
    for gid in dim.get("stale_pins", []):
        problems.append(
            f"stale dimensional pin '{gid}' — its site's line/text no longer matches. "
            f"Re-adjudicate: fixed → drop the pin; moved → update file/line/arg_text."
        )
    return problems


def _to_markdown(report: dict) -> str:
    s = report["summary"]
    lines = [
        "# Feature-Math Ownership Lint",
        "",
        f"_Generated {report['generated_at']} by `scripts/analysis/feature_math_lint.py` (read-only)._",
        "",
        f"**Modules scanned** {s['modules_scanned']} · **registered features** {s['registered_count']} · "
        f"**derivations found** {s['total_derivations']} "
        f"(NEW {s['new_violations']} · pins {s['current_pins']} · retired {s['retired']} · "
        f"stale-pins {s['stale_pins']})",
        "",
        "## NEW violations (must be empty — fix by routing through the registry)",
        "",
    ]
    nv = report["new_violations"]
    lines += ([f"- `{v['module']}:{v['line']}` — `{v['target']}` re-derives `{v['name']}`" for v in nv]
              if nv else ["_none — floor is green_"])
    lines += ["", "## Grandfather ledger (GD-0NN → Matrix v1 adjudication)", "",
              "| GD | site | semantic | formula_equiv | exec_reach | decision_reach |",
              "|---|---|---|---|---|---|"]
    present = set(report["known_present"])
    for p in report["pins"]:
        stale = "" if p["durable_key"] in present else " ⚠STALE"
        lines.append(
            f"| {p['id']}{stale} | `{p['file']}` {p['enclosing_qualname']}::{p['target_symbol']} | "
            f"{p['semantic_class']} | {p['formula_equivalence']} | {p['execution_reachability']} | "
            f"{p['decision_reachability']} |")
    led = report["ledger"]
    lines += ["", f"_Ledger: baseline {len(led['original_baseline_ids'])} · current "
              f"{len(led['current_ids'])} · retired {len(led['retired_ids'])}. Full evidence + call-chains: "
              "`docs/analysis/feature-math-divergence-adjudication.md`._"]

    dim = report.get("dimensional", {})
    lines += [
        "",
        "## Dimensional-unit mismatches (F-072, naming-convention heuristic — see module docstring)",
        "",
        f"**Watch-list** {', '.join(w['call'] + '(' + w['param'] + ')' for w in dim.get('watchlist', []))} · "
        f"**NEW** {s.get('dimensional_new_violations', 0)} · "
        f"**pinned** {s.get('dimensional_current_pins', 0)} · "
        f"**stale-pins** {s.get('dimensional_stale_pins', 0)}",
        "",
    ]
    dnv = dim.get("new_violations", [])
    lines += (
        [f"- `{v['module']}:{v['line']}` — `{v['call']}({v['param']}={v['arg_text']})`" for v in dnv]
        if dnv else ["_none — floor is green_"]
    )
    if dim.get("pins"):
        lines += ["", "| pin | site | reason |", "|---|---|---|"]
        dim_present = set(dim.get("known_present", []))
        for p in dim["pins"]:
            stale = "" if p["id"] in dim_present else " ⚠STALE"
            lines.append(f"| {p['id']}{stale} | `{p['file']}:{p['line']}` | {p['reason']} |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Feature-math ownership lint (read-only).")
    ap.add_argument("--check", action="store_true", help="exit 1 on any NEW (unpinned) violation")
    args = ap.parse_args()

    report = build_report()
    problems = check_violations(report)

    if args.check:
        if problems:
            print("FEATURE-MATH LINT VIOLATION (ownership and/or dimensional-unit):")
            for p in problems:
                print(f"  - {p}")
            return 1
        print("feature-math ownership lint: clean (floor green over pinned divergences)")
        return 0

    out_dir = _ROOT / "docs" / "research-readiness"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "feature-math-lint-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    (out_dir / "feature-math-lint-report.md").write_text(_to_markdown(report), encoding="utf-8")
    s = report["summary"]
    print("feature-math lint written → docs/research-readiness/feature-math-lint-report.{json,md}")
    print(f"  scanned {s['modules_scanned']} · registered {s['registered_count']} · "
          f"NEW {s['new_violations']} · pins {s['current_pins']} · retired {s['retired']} · "
          f"stale {s['stale_pins']}")
    for p in problems:
        print(f"  WARNING — {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
