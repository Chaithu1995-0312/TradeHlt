"""
geometry_census.py — F-049 GATE 1A–1F: reproducible, durable geometry-derivation census.

Purpose (read-only/additive): enumerate EVERY repository occurrence of the governed candlestick-
geometry quantities (F1–F9 of the frozen spec + the `wick_size` alias) via THREE INDEPENDENT
discovery methods, reconcile them, and freeze a machine-readable census artifact. This is the
prerequisite for GATE 2 semantic adjudication — no classification of intent happens here.

  OCCURRENCE  = any repository occurrence of a governed geometry name OR an equivalent geometry
                expression (reads, writes, dict keys, kwargs, string refs in calls).
  DERIVATION  = an occurrence whose RHS mathematically ORIGINATES/recomputes a quantity.
                Transport / serialization / reads / test expectations are occurrences, not
                necessarily derivations.

Discovery methods (independent by construction):
  NAME       — AST usage of a governed name (Name / Attribute / Subscript key / kwarg /
               dict-literal key / string literal passed to a call).
  EXPRESSION — normalized-AST pattern match of the geometry FORMULAS themselves (abs(close-open),
               high-low, high-max(open,close), ratios, epsilon/clip/np.where variants,
               single-level alias + helper-return resolution) — catches derivations that do NOT
               use governed names.
  SINK       — writes into governed feature sinks (Name/Attribute/Subscript targets, DataFrame
               columns, dict.update / DataFrame.assign / dict-literal keys, tuple unpacking).

Universe (GATE 1A): git-tracked *.py files (primary) ∪ untracked repository-local *.py under the
execution-capable roots (secondary, tagged) — excluding vendor/venv, alternate worktrees
(.claude/), caches, archives, generated dirs. Policies are emitted in the manifest.

IDs are content-based (file + qualname + target + normalized RHS), stable under line movement.

Usage:
  python scripts/analysis/geometry_census.py            # writes artifact + summary
Outputs:
  docs/governance/geometry_census.jsonl                 # one line per OCCURRENCE
  docs/governance/geometry_census_summary.json          # manifest + counts + reconciliation
"""
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[2]

# ── GATE 1A: repository-universe policies ────────────────────────────────────
GOVERNED = {
    "body_size", "candle_range", "upper_wick", "lower_wick", "total_wick",
    "body_ratio", "upper_wick_ratio", "lower_wick_ratio", "wick_ratio", "wick_size",
}
EXCLUDED_ROOTS = (
    ".claude", "venv", ".venv", "node_modules", "__pycache__", "archive",
    "context", "data", "logs", "results", "bundles", "flow_graphs",
)
EXEC_ROOTS = ("src", "scripts", "tests", "tools", "mt5_analytics", "exec_telemetry",
              "H-SECONDLOW-002_Complete_Package")  # census-v2: sole-copy research package admitted
# v3 (P0-calibration fixes): MD-1 bare-name alias RHS = transport(alias_of_derivation), not a new
# derivation; MD-2 coercion-helper allowlist (_to_float etc.); MD-3 config-driven registry executors
# admitted explicitly as role=executor_dispatch (previously invisible to static matching).
CENSUS_VERSION = 3

# MD-3: config-driven executors — the math is selected by ontology config at runtime; these sites
# cannot be discovered by static expression matching and are ADMITTED explicitly. Parity evidence:
# tests/test_formula_registry.py (composition battery == candle_math) + tests/test_derived_math.py.
ADMITTED_EXECUTORS = (
    {"file": "src/features/registry/composition_registry.py", "qualname": "compute_composition",
     "symbol": "val", "note": "num/den selected by ontology feature_compositions; bounds clamp; den<=0 -> 0.0"},
    {"file": "src/features/registry/derived_registry.py", "qualname": "compute_derived",
     "symbol": "<dispatch>", "note": "signature dispatch to derived_math.* impls; NO local arithmetic"},
)

UNIVERSE_POLICIES = {
    "primary_universe": "git-tracked *.py files (git ls-files)",
    "secondary_universe": f"untracked repo-local *.py under execution-capable roots {EXEC_ROOTS} "
                          "(git ls-files --others --exclude-standard)",
    "excluded_roots": list(EXCLUDED_ROOTS),
    "excluded_file_types": "everything except *.py (YAML ontology handled by test_formula_registry; "
                           "no governed *.ipynb present)",
    "generated_code_policy": "generated dirs (context/, flow_graphs/, data/, results/, logs/) excluded",
    "vendor_dependency_policy": "venv/.venv/node_modules excluded",
    "notebook_policy": "no repository-governed notebooks found; none scanned",
    "test_policy": "tests/ INCLUDED (occurrences tagged test context; independent impls = TEST_ORACLE candidates)",
    "symlink_policy": "not followed (none expected on Windows checkout)",
    "gitignored_policy": "gitignored files excluded from both universes",
    "worktree_policy": ".claude/worktrees are COPIES of this repo — excluded to avoid census inflation",
    "archive_policy": "archive/ = historical copies — excluded, disclosed here",
}

# ── price-token + quantity-name alias tables (expression discovery) ──────────
_PRICE = {
    "open": {"open", "open_", "opn", "o"},
    "high": {"high", "hi", "h"},
    "low": {"low", "lo", "l"},
    "close": {"close", "cls", "c"},
}
_PRICE_LOOKUP = {alias: canon for canon, s in _PRICE.items() for alias in s}
_WEAK_TOKENS = {"o", "h", "l", "c"}  # accepted only inside a matched pattern shape

# name-mediated quantity sets (division operands referenced by name, recorded explicitly)
_QTY_NAMES = {
    "BODY":   {"body_size", "body", "candle_body", "bodysize", "_body"},
    "RANGE":  {"candle_range", "full_range", "rng", "price_range", "candle_rng", "_rng", "_rng2",
               "range_", "bar_range"},
    "TOTALW": {"total_wick", "tw", "total_wick_size"},
    "UPPER":  {"upper_wick", "uw"},
    "LOWER":  {"lower_wick", "lw"},
    "WICKSZ": {"wick_size"},   # ambiguous alias — kept distinct for adjudication
}
_QTY_LOOKUP = {n: q for q, s in _QTY_NAMES.items() for n in s}

_FORM_CANON = {
    ("BODY", "RANGE"): "F6_BODY_RATIO",
    ("UPPER", "RANGE"): "F7_UPPER_RATIO",
    ("LOWER", "RANGE"): "F8_LOWER_RATIO",
    ("TOTALW", "RANGE"): "F9_WICK_RATIO",
    ("BODY", "TOTALW"): "NC_BODY_OVER_TOTALW",   # the GD-001 non-canonical form
    ("BODY", "WICKSZ"): "NC_BODY_OVER_WICKSZ",   # name-mediated: semantics depend on wick_size site
}
_DIV_CALLS = {"divide", "div", "true_divide", "safe_divide", "safe_div"}
# MD-2: coercion helpers — numeric conversion of an existing value is TRANSPORT, not mathematics.
_COERCION_LEAVES = {"float", "int", "bool", "str", "round",
                    "_to_float", "to_float", "_to_int", "to_int", "as_float",
                    "_safe_float", "safe_float", "_safe_int", "safe_int"}


def _sha(s: str, n: int = 12) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:n]


# ── expression normalization ────────────────────────────────────────────────
def _unwrap(node):
    """float(x) / x.clip(lower=eps) / np.where guard unwrap for denominator analysis."""
    while True:
        if isinstance(node, ast.Call):
            f = node.func
            leaf = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
            if leaf in ("float", "int") and node.args:
                node = node.args[0]; continue
            if leaf == "clip" and isinstance(f, ast.Attribute):
                node = f.value; continue
        return node


def _price_tok(node, env):
    """(canonical_token, weak, base) — `base` identifies the OWNING candle/object (same-candle
    guard: `retest.close - disp.open` must NOT match F1). Bare names share base ''."""
    node = _unwrap(node)
    if isinstance(node, ast.Name):
        e = env.get(node.id)
        if e and e[0] == "price":
            return e[1], False, (e[2] if len(e) > 2 else "")
        canon = _PRICE_LOOKUP.get(node.id.lower())
        if canon:
            return canon, node.id.lower() in _WEAK_TOKENS, ""
    if isinstance(node, ast.Attribute) and node.attr in _PRICE:
        return node.attr, False, ast.dump(node.value, annotate_fields=False)[:80]
    if isinstance(node, ast.Subscript):
        k = node.slice
        if isinstance(k, ast.Constant) and isinstance(k.value, str) and k.value in _PRICE:
            return k.value, False, ast.dump(node.value, annotate_fields=False)[:80]
    return None, False, None


def _small_const(node) -> bool:
    node = _unwrap(node)
    return isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and 0 <= node.value <= 0.01


class _Form:
    __slots__ = ("form", "flags", "weak")
    def __init__(self, form, flags=(), weak=False):
        self.form, self.flags, self.weak = form, set(flags), weak


def _qty_of(node, env, funcmap):
    """Resolve a node to a quantity: a canonical form, or a name-mediated ('NAME', symbol)."""
    f = _resolve_form(node, env, funcmap)
    if f:
        return f
    node = _unwrap(node)
    if isinstance(node, ast.Name):
        e = env.get(node.id)
        if e and e[0] == "form":
            return _Form(e[1])
        q = _QTY_LOOKUP.get(node.id.lstrip("_").lower())
        if q:
            return _Form(q, {"name_mediated"})
    if isinstance(node, ast.Attribute) and node.attr in GOVERNED | set(_QTY_LOOKUP):
        q = _QTY_LOOKUP.get(node.attr)
        return _Form(q or f"NAME:{node.attr}", {"name_mediated"})
    if isinstance(node, ast.Subscript):
        k = node.slice
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            q = _QTY_LOOKUP.get(k.value)
            if q:
                return _Form(q, {"name_mediated"})
    return None


def _resolve_form(node, env, funcmap):  # noqa: C901  (pattern matcher — deliberately explicit)
    """Return _Form for a geometry expression, else None. Single-level alias + helper resolution."""
    node = _unwrap(node)

    if isinstance(node, ast.Name):
        e = env.get(node.id)
        if e and e[0] == "form":
            return _Form(e[1], {"alias_resolved"})
        return None

    if isinstance(node, ast.Call):
        f = node.func
        leaf = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
        # abs(close - open) — same-candle only
        if leaf == "abs" and node.args:
            a = _unwrap(node.args[0])
            if isinstance(a, ast.BinOp) and isinstance(a.op, ast.Sub):
                t1, w1, b1 = _price_tok(a.left, env); t2, w2, b2 = _price_tok(a.right, env)
                if {t1, t2} == {"open", "close"} and b1 == b2:
                    return _Form("F1_BODY", weak=w1 or w2)
        # max(...) — eps floor / clip-at-zero / max(upper,lower) is NOT geometry
        if leaf in ("max", "maximum") and len(node.args) == 2:
            a, b = node.args
            if _small_const(b):
                inner = _resolve_form(a, env, funcmap) or _qty_of(a, env, funcmap)
                if inner:
                    inner.flags.add("eps_floor" if (_unwrap(b).value or 0) > 0 else "clip0")
                    return inner
            if _small_const(a):
                inner = _resolve_form(b, env, funcmap) or _qty_of(b, env, funcmap)
                if inner:
                    inner.flags.add("eps_floor" if (_unwrap(a).value or 0) > 0 else "clip0")
                    return inner
        # np.where(cond, A, B) → guarded form
        if leaf == "where" and len(node.args) == 3:
            for br in node.args[1:]:
                inner = _resolve_form(br, env, funcmap)
                if inner:
                    inner.flags.add("guarded")
                    return inner
        # np.divide / Series.div / safe_divide → division semantics
        if leaf in _DIV_CALLS:
            args = list(node.args)
            if isinstance(f, ast.Attribute) and len(args) == 1:   # series.divide(den)
                args = [f.value, args[0]]
            if len(args) >= 2:
                return _div_form(args[0], args[1], env, funcmap)
        # helper-return resolution (single-level, same module)
        if isinstance(f, ast.Name) and f.id in funcmap:
            return _Form(funcmap[f.id], {"helper_resolved"})

    # ternary guard: X if cond else fallback → guarded form (e.g. body/tw if tw > 1e-8 else 0.0)
    if isinstance(node, ast.IfExp):
        for br in (node.body, node.orelse):
            inner = _resolve_form(br, env, funcmap)
            if inner:
                inner.flags.add("guarded")
                return inner

    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Sub):
            lt, lw, lb = _price_tok(node.left, env); rt, rw, rb = _price_tok(node.right, env)
            if lt == "high" and rt == "low" and lb == rb:
                return _Form("F2_RANGE", weak=lw or rw)
            # high - max(open, close) — same candle across all three tokens
            r = _unwrap(node.right)
            if lt == "high" and isinstance(r, ast.Call):
                rf = r.func
                rleaf = rf.attr if isinstance(rf, ast.Attribute) else (rf.id if isinstance(rf, ast.Name) else "")
                if rleaf in ("max", "maximum") and len(r.args) == 2:
                    (t1, _w1, b1), (t2, _w2, b2) = _price_tok(r.args[0], env), _price_tok(r.args[1], env)
                    if {t1, t2} == {"open", "close"} and b1 == b2 == lb:
                        return _Form("F3_UPPER")
            # min(open, close) - low — same candle across all three tokens
            lnode = _unwrap(node.left)
            if rt == "low" and isinstance(lnode, ast.Call):
                lf = lnode.func
                lleaf = lf.attr if isinstance(lf, ast.Attribute) else (lf.id if isinstance(lf, ast.Name) else "")
                if lleaf in ("min", "minimum") and len(lnode.args) == 2:
                    (t1, _w1, b1), (t2, _w2, b2) = _price_tok(lnode.args[0], env), _price_tok(lnode.args[1], env)
                    if {t1, t2} == {"open", "close"} and b1 == b2 == rb:
                        return _Form("F4_LOWER")
            # RANGE - BODY  → total_wick
            lq = _qty_of(node.left, env, funcmap); rq = _qty_of(node.right, env, funcmap)
            if lq and rq and lq.form in ("F2_RANGE", "RANGE", "WICKSZ") and rq.form in ("F1_BODY", "BODY"):
                return _Form("F5_TOTALW", lq.flags | rq.flags)
        if isinstance(node.op, ast.Add):
            lq = _qty_of(node.left, env, funcmap); rq = _qty_of(node.right, env, funcmap)
            if lq and rq and {lq.form, rq.form} in ({"F3_UPPER", "F4_LOWER"}, {"UPPER", "LOWER"}):
                return _Form("F5_TOTALW", lq.flags | rq.flags)
        if isinstance(node.op, ast.Div):
            return _div_form(node.left, node.right, env, funcmap)
    return None


def _div_form(num, den, env, funcmap):
    nq = _qty_of(num, env, funcmap)
    dq = _qty_of(den, env, funcmap)
    if not (nq or dq):
        return None
    def base(q):
        return {"F1_BODY": "BODY", "F2_RANGE": "RANGE", "F3_UPPER": "UPPER", "F4_LOWER": "LOWER",
                "F5_TOTALW": "TOTALW"}.get(q, q)
    nb = base(nq.form) if nq else "?"
    db = base(dq.form) if dq else "?"
    flags = (nq.flags if nq else set()) | (dq.flags if dq else set())
    if nq and dq:
        return _Form(_FORM_CANON.get((nb, db), f"DIV({nb},{db})"), flags)
    # one-sided resolution: a division that CONSUMES a geometry quantity is still a derivation
    flags.add("partial_div")
    return _Form(f"DIV({nb},{db})", flags)


# ── per-file scan ────────────────────────────────────────────────────────────
def _qualname_map(tree):
    parents = {}
    for n in ast.walk(tree):
        for ch in ast.iter_child_nodes(n):
            parents[ch] = n
    def qual(node):
        names = []
        cur = parents.get(node)
        while cur is not None:
            if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.append(cur.name)
            cur = parents.get(cur)
        return ".".join(reversed(names)) or "<module>"
    return qual


def _build_env(fn_body, funcmap):
    """Single-level alias map: name -> ('price', tok, base) | ('form', F). Two passes for chains."""
    env: dict = {}
    for _ in (0, 1):
        for st in fn_body:
            if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
                nm = st.targets[0].id
                tok, _w, base = _price_tok(st.value, env)
                if tok:
                    env[nm] = ("price", tok, base); continue
                f = _resolve_form(st.value, env, funcmap)
                if f:
                    env[nm] = ("form", f.form)
    return env


def _funcmap(tree):
    """module funcs whose single return is a geometry form → name -> form."""
    out = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef):
            rets = [s for s in ast.walk(n) if isinstance(s, ast.Return) and s.value is not None]
            if len(rets) == 1:
                env = _build_env(n.body, {})
                f = _resolve_form(rets[0].value, env, {})
                if f:
                    out[n.name] = f.form
    return out


def _sink_targets(stmt):
    """Yield (kind, symbol, value_node) for every write in an Assign/AnnAssign/AugAssign + calls."""
    def tgt(t, v):
        if isinstance(t, ast.Name):
            yield ("name", t.id, v)
        elif isinstance(t, ast.Attribute):
            yield ("attribute", t.attr, v)
        elif isinstance(t, ast.Subscript):
            k = t.slice
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                yield ("subscript", k.value, v)
        elif isinstance(t, (ast.Tuple, ast.List)):
            vals = v.elts if isinstance(v, (ast.Tuple, ast.List)) and len(v.elts) == len(t.elts) else [None] * len(t.elts)
            for el, ev in zip(t.elts, vals):
                yield from tgt(el, ev)
    if isinstance(stmt, ast.Assign):
        for t in stmt.targets:
            yield from tgt(t, stmt.value)
    elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
        yield from tgt(stmt.target, stmt.value)
    elif isinstance(stmt, ast.AugAssign):
        yield from tgt(stmt.target, stmt.value)


def _transportish(node) -> bool:
    node = _unwrap(node)
    if isinstance(node, ast.Call):
        f = node.func
        leaf = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
        if leaf in ("get", "pop", "setdefault", "getattr") or leaf in _COERCION_LEAVES:
            return True
        return False
    return isinstance(node, (ast.Subscript, ast.Attribute, ast.Name, ast.Constant))


def _subforms(val, env, funcmap):
    """Geometry forms appearing as SUB-expressions of an unresolved RHS (e.g. (high-low) inside
    pd.concat for a true-range calc). Only consulted when the top level does not resolve, so a
    resolved F6 never double-reports its own F1/F2 operands."""
    found: dict = {}
    for sub in ast.walk(val):
        if sub is val:
            continue
        f = _resolve_form(sub, env, funcmap)
        if f:
            found.setdefault(f.form, f)
    return found


def _role_for(vnode, env, funcmap):
    """(role, _Form|None) for a governed-sink RHS — one rule for ALL sink kinds."""
    ff = _resolve_form(vnode, env, funcmap)
    # MD-1: a bare name/attribute/subscript READ whose form comes only from alias resolution
    # TRANSPORTS an upstream derivation — it does not create new mathematics.
    if ff and isinstance(_unwrap(vnode), (ast.Name, ast.Attribute, ast.Subscript)):
        return "transport", _Form(ff.form, ff.flags | {"alias_of_derivation"})
    if ff:
        return "derivation", ff
    if _transportish(vnode):
        return "transport", None
    v = _unwrap(vnode)
    # literal data provision (test fixtures, alias tables): not a derivation
    if isinstance(v, (ast.List, ast.Tuple, ast.Dict, ast.Set)) and all(
        isinstance(e, ast.Constant) for e in getattr(v, "elts", []) or []
    ):
        return "transport", None
    # ternary of transport branches (guarded read/None fallback): transport
    if isinstance(v, ast.IfExp) and _transportish(v.body) and _transportish(v.orelse):
        return "transport", None
    if isinstance(v, (ast.BinOp, ast.UnaryOp, ast.Call, ast.IfExp)):
        return "derivation", _Form("UNKNOWN_FORM")
    return "unknown_write", None


def scan_source(src: str, rel: str) -> list[dict]:
    """Scan one file's source. Returns occurrence dicts (GATE 1B/1C/1D combined, methods tagged)."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    qual = _qualname_map(tree)
    funcmap = _funcmap(tree)
    is_test = rel.startswith("tests/") or "/tests/" in rel
    occ: list[dict] = []
    seen: set = set()
    _ordinals: dict = {}

    def add(node, method, role, kind, symbol, form=None, flags=(), value=None):
        key = (getattr(node, "lineno", 0), kind, symbol, role, form)
        rec_key = (method, *key)
        if rec_key in seen:
            return
        # merge methods into an existing occurrence at the same site
        for r in occ:
            if (r["line_start"], r["target_kind"], r["target_symbol"], r["role"]) == key[:1] + key[1:4] and r.get("feature_candidate") == form:
                if method not in r["discovery_methods"]:
                    r["discovery_methods"].append(method)
                seen.add(rec_key)
                return
        norm = ast.dump(value, annotate_fields=False)[:400] if value is not None else ""
        q = qual(node)
        # ordinal disambiguates repeated identical sites within one qualname (e.g. multiple reads
        # of the same name) — order-of-appearance is stable under unrelated line movement.
        base_key = f"{rel}|{q}|{kind}|{symbol}|{role}|{form}|{norm}"
        _ordinals[base_key] = _ordinals.get(base_key, 0) + 1
        rec = {
            "occurrence_id": "GEO-O-" + _sha(f"{base_key}#{_ordinals[base_key]}"),
            "derivation_id_or_null": None,
            "discovery_methods": [method],
            "file": rel,
            "enclosing_qualname": q,
            "line_span": [getattr(node, "lineno", 0), getattr(node, "end_lineno", getattr(node, "lineno", 0))],
            "line_start": getattr(node, "lineno", 0),
            "statement_kind": type(node).__name__,
            "target_kind": kind,
            "target_symbol": symbol,
            "normalized_rhs_ast": norm,
            "rhs_fingerprint": _sha(norm) if norm else "",
            "feature_candidate": form,
            "role": role,
            "flags": sorted(flags),
            "classification_status": "UNKNOWN" if role in ("derivation", "unknown_write") else "MECHANICAL",
            "is_test": is_test,
        }
        if role == "derivation":
            rec["derivation_id_or_null"] = "GEO-D-" + _sha(f"{base_key}#{_ordinals[base_key]}", 10)
        occ.append(rec)
        seen.add(rec_key)

    # SINGLE-PASS scope resolution (census-v2 fix): each node is visited exactly once and analyzed
    # under its ENCLOSING function's env. (v1 walked module+function scopes separately → statements
    # inside functions were visited twice, and differing env resolution produced duplicate
    # DERIVATION_IDs for one implementation, e.g. crt_gaussian_scorer:190.)
    parents = {}
    for n in ast.walk(tree):
        for ch in ast.iter_child_nodes(n):
            parents[ch] = n
    env_by_fn = {id(tree): _build_env(tree.body, funcmap)}
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            env_by_fn[id(n)] = _build_env(n.body, funcmap)

    def _env_for(node):
        cur = parents.get(node)
        while cur is not None:
            if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return env_by_fn[id(cur)]
            cur = parents.get(cur)
        return env_by_fn[id(tree)]

    if True:  # keep original loop indentation
        for st in ast.walk(tree):
            env = _env_for(st)
            # -- writes (SINK + EXPRESSION on RHS) --
            if isinstance(st, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                for kind, symbol, val in _sink_targets(st):
                    canon = symbol.lstrip("_").lower()
                    governed_sink = canon in GOVERNED
                    if val is None:
                        if governed_sink:
                            add(st, "sink", "unknown_write", kind, symbol)
                            add(st, "name", "unknown_write", kind, symbol)
                        continue
                    role, ff = _role_for(val, env, funcmap)
                    form = ff.form if ff else None
                    flags = set(ff.flags) if ff else set()
                    # UNKNOWN_FORM (bare arithmetic/helper) is a derivation ONLY at a governed sink;
                    # at a non-governed sink it is ordinary program arithmetic, not geometry.
                    if form == "UNKNOWN_FORM" and not governed_sink:
                        role, form = "irrelevant", None
                    # sub-expression discovery: hidden geometry inside an unresolved larger RHS
                    # (strong-token matches only — weak single-letter operands are too noisy here)
                    if role != "transport" and (form is None or form == "UNKNOWN_FORM"):
                        subs = {k: v for k, v in _subforms(val, env, funcmap).items() if not v.weak}
                        if subs:
                            fm = next(iter(subs.values()))
                            role, form = "derivation", fm.form
                            flags = fm.flags | {"subexpression"}
                    if role == "derivation" and form and form != "UNKNOWN_FORM":
                        add(st, "expression", role, kind, symbol, form, flags, val)
                    if governed_sink:
                        add(st, "sink", role if role != "irrelevant" else "unknown_write",
                            kind, symbol, form, flags, val)
                        add(st, "name", role if role != "irrelevant" else "unknown_write",
                            kind, symbol, form, flags, val)
            # -- calls: assign()/update()/dict-literal keys/kwargs (SINK) + reads of governed strings (NAME) --
            if isinstance(st, ast.Call):
                f = st.func
                leaf = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
                if leaf in ("assign",):
                    for kw in st.keywords or []:
                        if kw.arg and kw.arg.lstrip("_").lower() in GOVERNED:
                            role, ff = _role_for(kw.value, env, funcmap)
                            add(st, "sink", role, "assign_kwarg", kw.arg, ff.form if ff else None,
                                ff.flags if ff else set(), kw.value)
                if leaf == "update" and st.args and isinstance(st.args[0], ast.Dict):
                    for k, v in zip(st.args[0].keys, st.args[0].values):
                        if isinstance(k, ast.Constant) and isinstance(k.value, str) and k.value.lstrip("_").lower() in GOVERNED:
                            role, ff = _role_for(v, env, funcmap)
                            add(st, "sink", role, "dict_update_key", k.value, ff.form if ff else None,
                                ff.flags if ff else set(), v)
                for a in st.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value in GOVERNED:
                        add(st, "name", "consumer_read", "string_arg", a.value)
            if isinstance(st, ast.Dict):
                for k, v in zip(st.keys, st.values):
                    if isinstance(k, ast.Constant) and isinstance(k.value, str) and k.value.lstrip("_").lower() in GOVERNED:
                        role, ff = _role_for(v, env, funcmap)
                        add(st, "sink", role, "dict_literal_key", k.value, ff.form if ff else None,
                            ff.flags if ff else set(), v)
            # -- pure reads (NAME) --
            if isinstance(st, ast.Name) and isinstance(st.ctx, ast.Load) and st.id.lstrip("_").lower() in GOVERNED:
                add(st, "name", "consumer_read", "name", st.id)
            if isinstance(st, ast.Attribute) and isinstance(st.ctx, ast.Load) and st.attr in GOVERNED:
                add(st, "name", "consumer_read", "attribute", st.attr)
            if isinstance(st, ast.Subscript) and isinstance(st.ctx, ast.Load):
                k = st.slice
                if isinstance(k, ast.Constant) and isinstance(k.value, str) and k.value in GOVERNED:
                    add(st, "name", "consumer_read", "subscript", k.value)
            # -- bare expression derivations not assigned to governed sink (EXPRESSION) --
            if isinstance(st, ast.Return) and st.value is not None:
                # MD-1 guard: `return alias_name` transports, it does not derive.
                if not isinstance(_unwrap(st.value), (ast.Name, ast.Attribute, ast.Subscript)):
                    ff = _resolve_form(st.value, env, funcmap)
                    if ff:
                        add(st, "expression", "derivation", "return", "<return>", ff.form, ff.flags, st.value)

    # test-context roles
    for r in occ:
        if r["is_test"] and r["role"] == "derivation":
            r["role"] = "test_oracle"
            r["classification_status"] = "MECHANICAL"
    return occ


# ── universe + main ──────────────────────────────────────────────────────────
def _git_lines(args):
    try:
        out = subprocess.run(["git"] + args, cwd=_ROOT, capture_output=True, text=True, timeout=60)
        return [l.strip() for l in out.stdout.splitlines() if l.strip()]
    except Exception:
        return []


def build_universe():
    tracked = [f for f in _git_lines(["ls-files", "*.py"])]
    untracked = [f for f in _git_lines(["ls-files", "--others", "--exclude-standard", "*.py"])]
    def ok(f):
        p = f.replace("\\", "/")
        return not any(p.startswith(x + "/") or p == x for x in EXCLUDED_ROOTS)
    tracked = sorted(f for f in tracked if ok(f))
    def _exec_capable(f):
        p = f.replace("\\", "/")
        return p.split("/")[0] in EXEC_ROOTS or "/" not in p  # census-v2: root-level *.py admitted
    untracked_exec = sorted(f for f in untracked if ok(f) and _exec_capable(f))
    untracked_other = sorted(f for f in untracked if ok(f) and f not in untracked_exec)
    return tracked, untracked_exec, untracked_other


def build_census():
    tracked, untracked_exec, untracked_other = build_universe()
    occ_all: list[dict] = []
    for universe, files in (("tracked", tracked), ("untracked_local", untracked_exec)):
        for rel in files:
            p = _ROOT / rel
            try:
                src = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            blob = _sha(src, 12)
            for r in scan_source(src, rel.replace("\\", "/")):
                r["universe"] = universe
                r["git_blob_hash"] = blob
                r["source_inputs"] = "OHLC" if r.get("feature_candidate") else ""
                r["downstream_sink"] = r["target_kind"] if r["role"] != "consumer_read" else ""
                r["evidence"] = f'{r["file"]}:{r["line_start"]}'
                r["uncertainty"] = "weak_token_match" if "weak" in r.get("flags", []) else ""
                occ_all.append(r)

    # MD-3: explicit admission of the config-driven registry executors (invisible to static matching)
    for ex in ADMITTED_EXECUTORS:
        base_key = f'{ex["file"]}|{ex["qualname"]}|manual|{ex["symbol"]}|executor_dispatch'
        occ_all.append({
            "occurrence_id": "GEO-O-" + _sha(base_key),
            "derivation_id_or_null": "GEO-D-" + _sha(base_key, 10),
            "discovery_methods": ["manual_admission"],
            "file": ex["file"], "enclosing_qualname": ex["qualname"],
            "line_span": [0, 0], "line_start": 0, "statement_kind": "ManualAdmission",
            "target_kind": "executor", "target_symbol": ex["symbol"],
            "normalized_rhs_ast": "", "rhs_fingerprint": "",
            "feature_candidate": "CONFIG_DRIVEN", "role": "executor_dispatch",
            "flags": ["config_driven"], "classification_status": "UNKNOWN",
            "is_test": False, "universe": "tracked", "git_blob_hash": "",
            "source_inputs": "ontology-config", "downstream_sink": "return",
            "evidence": ex["note"], "uncertainty": "",
        })

    # reconciliation (static methods only; manual admissions reported separately)
    methods = lambda r: set(r["discovery_methods"])
    recon = {
        "NAME_ONLY": 0, "EXPRESSION_ONLY": 0, "SINK_ONLY": 0,
        "NAME_AND_EXPRESSION": 0, "NAME_AND_SINK": 0, "EXPRESSION_AND_SINK": 0, "ALL_THREE": 0,
    }
    for r in occ_all:
        m = methods(r)
        if m == {"manual_admission"}:
            continue
        key = ("ALL_THREE" if m == {"name", "expression", "sink"} else
               "NAME_AND_EXPRESSION" if m == {"name", "expression"} else
               "NAME_AND_SINK" if m == {"name", "sink"} else
               "EXPRESSION_AND_SINK" if m == {"expression", "sink"} else
               "NAME_ONLY" if m == {"name"} else
               "EXPRESSION_ONLY" if m == {"expression"} else "SINK_ONLY")
        recon[key] += 1

    roles = {}
    for r in occ_all:
        roles[r["role"]] = roles.get(r["role"], 0) + 1
    deriv = [r for r in occ_all if r["derivation_id_or_null"]]
    summary = {
        "census_version": CENSUS_VERSION,
        "universe_manifest": {
            **UNIVERSE_POLICIES,
            "tracked_py_files": len(tracked),
            "untracked_exec_py_files": len(untracked_exec),
            "untracked_other_py_files_disclosed_not_scanned": len(untracked_other),
        },
        "counts": {
            "TOTAL_OCCURRENCES": len(occ_all),
            "TOTAL_DERIVATIONS": len({r["derivation_id_or_null"] for r in deriv}),
            "TOTAL_PRODUCERS": len({r["derivation_id_or_null"] for r in deriv if not r["is_test"]}),
            "TOTAL_TRANSPORT_SITES": roles.get("transport", 0),
            "TOTAL_CONSUMERS": roles.get("consumer_read", 0),
            "TOTAL_TEST_ORACLES": roles.get("test_oracle", 0),
            "TOTAL_UNKNOWN": roles.get("unknown_write", 0),
            "MANUALLY_ADMITTED_EXECUTORS": roles.get("executor_dispatch", 0),
        },
        "role_histogram": roles,
        "reconciliation": recon,
    }
    return occ_all, summary, untracked_other


def main() -> int:
    occ, summary, untracked_other = build_census()
    out_dir = _ROOT / "docs" / "governance"
    out_dir.mkdir(parents=True, exist_ok=True)
    art = out_dir / "geometry_census.jsonl"
    with art.open("w", encoding="utf-8") as fh:
        for r in sorted(occ, key=lambda r: (r["file"], r["line_start"], r["occurrence_id"])):
            r2 = dict(r); r2.pop("line_start", None); r2.pop("is_test", None)
            fh.write(json.dumps(r2, ensure_ascii=False) + "\n")
    (out_dir / "geometry_census_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print("artifact:", art.relative_to(_ROOT))
    print(json.dumps(summary["counts"], indent=2))
    print("reconciliation:", json.dumps(summary["reconciliation"]))
    print("universe: tracked", summary["universe_manifest"]["tracked_py_files"],
          "| untracked-exec", summary["universe_manifest"]["untracked_exec_py_files"],
          "| untracked-other (disclosed, unscanned)", len(untracked_other))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
