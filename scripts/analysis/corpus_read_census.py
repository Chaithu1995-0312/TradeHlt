"""corpus_read_census.py — PHASE 0 census of every direct corpus read in the repository.

READ-ONLY, deterministic, stdlib-only. Answers one question the repo cannot currently
answer: *which code reads an OHLCV corpus without going through the admission seam?*

`corpus_gate.admit_corpus` declares itself "The single corpus admission seam" and its own
docstring records the failure this census measures — "Every `src/research/` consumer read its
corpus with a bare `pd.read_csv` ... (F-039)". That claim has never been quantified. This
script quantifies it.

WHY A SIBLING OF ohlcv_census.py, NOT AN EXTENSION OF IT
--------------------------------------------------------
`ohlcv_census.py` scans DATA FILES under `data/` and is bound by a byte-determinism
`--check` contract over two dated governance artifacts. This scans SOURCE CODE. Different
object, different output, and folding them would put a new AST pass inside that frozen
determinism gate for no benefit.

CLASSIFICATION IS SEMANTIC, NOT SYNTACTIC
-----------------------------------------
The `feature_math_lint.py` discipline: a `pd.read_csv` is not a violation because of its
name, it is a violation because of WHAT IT READS. Every call site resolves to one of:

  CORPUS   -- the path resolves to an OHLCV corpus  -> must migrate behind the seam
  DERIVED  -- trades / matrices / results / configs -> out of scope, recorded as such
  GATED    -- already flows through admit_corpus / admit_csv_path / CandleLoader
  UNKNOWN  -- the path is not statically resolvable -> BLOCKING, adjudicate by hand

UNKNOWN is deliberately not folded into DERIVED. A census that guesses in the permissive
direction would under-report the migration surface, which is the one number this exists to
produce.

Usage:
    venv/Scripts/python.exe scripts/analysis/corpus_read_census.py
    venv/Scripts/python.exe scripts/analysis/corpus_read_census.py --json out.json
    venv/Scripts/python.exe scripts/analysis/corpus_read_census.py --class CORPUS
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

SCRIPT_VERSION = "1.0.0"

# ── Scan scope ────────────────────────────────────────────────────────────────
# Roots that hold first-party code. `logs/` is excluded deliberately: it contains
# full scratch COPIES of src/ (logs/dual_construction*/scratch_roots/**), which would
# triple-count every finding.
SCAN_ROOTS = ("src", "scripts", "tools", "reports", "tests", "multi_llm")
EXCLUDE_PARTS = frozenset({
    "venv", ".venv", ".git", "__pycache__", "node_modules", "logs",
    ".claude", ".grok", "site-packages", "build", "dist",
})

# ── Reader calls this census cares about ──────────────────────────────────────
# Keyed by the attribute/function name as it appears at the call site.
READER_CALLS = frozenset({
    "read_csv", "read_excel", "read_parquet", "read_table",
    "load_workbook", "reader", "DictReader", "open", "loadtxt", "genfromtxt",
})
# Calls that ARE the seam (or its sanctioned components).
GATED_CALLS = frozenset({
    "admit_corpus", "admit_csv_path", "CandleLoader",
    "guard_xauusd_csv_path", "require_phase1_frozen_candidate",
    "validate_dataset", "corpus_for",
})

# ── Corpus path signals ───────────────────────────────────────────────────────
_TF = r"(?:M1|M5|M15|M30|H1|H4|D1|W1|MN1)"
# `data/mt5/XAUUSD_M15.csv`, `data/BNBUSDT_M15_2year.xlsx`, `XAUUSD_M15.csv`
_CORPUS_NAME_RE = re.compile(rf"[A-Z][A-Z0-9]{{2,11}}_{_TF}(?:_[A-Za-z0-9]+)*\.(?:csv|xlsx|xlsm)$")
_CORPUS_DIR_RE = re.compile(r"(?:^|/)data/(?:mt5/|binance/)?[^/]*$")

# Directories whose contents are derived artifacts, never a corpus.
_DERIVED_DIR_RE = re.compile(
    r"(?:^|/)(?:results|reports|logs|docs|configs|models|multi_llm|context|tests/fixtures)/"
)
# Filename stems that mark a derived artifact even under data/.
_DERIVED_STEM_RE = re.compile(
    r"(?:trades|setups|matrix|registry|checkpoint|manifest|summary|metrics|events|scan|"
    r"census|report|ledger|audit|labels|dataset|features|_second_low|_secondlow|"
    r"predictions|equity|journal)",
    re.IGNORECASE,
)

# Module-level names that are known corpus locators.
CORPUS_CONSTANTS = frozenset({
    "PHASE1_PHYSICAL_PATH", "DEFAULT_XLSX", "DEFAULT_CSV", "CORPUS", "CORPUS_PATH",
    "XAUUSD_CSV", "CANONICAL_CSV", "_CANONICAL",
})
# Callables whose return value is a corpus path.
CORPUS_CALLABLES = frozenset({"corpus_for", "guard_xauusd_csv_path", "_guarded_csv"})

CLASS_CORPUS = "CORPUS"
CLASS_DERIVED = "DERIVED"
CLASS_GATED = "GATED"
CLASS_UNKNOWN = "UNKNOWN"


def _iter_py_files() -> list[Path]:
    out: list[Path] = []
    for root_name in SCAN_ROOTS:
        root = _ROOT / root_name
        if not root.is_dir():
            continue
        for p in root.rglob("*.py"):
            if EXCLUDE_PARTS & set(p.parts):
                continue
            out.append(p)
    for p in sorted(_ROOT.glob("*.py")):
        if p.is_file():
            out.append(p)
    # Deterministic order: repo-relative posix path.
    return sorted(set(out), key=lambda q: q.relative_to(_ROOT).as_posix())


def _call_name(node: ast.Call) -> str:
    """`pd.read_csv(...)` -> 'read_csv'; `open(...)` -> 'open'; `Foo.bar.baz()` -> 'baz'."""
    fn = node.func
    if isinstance(fn, ast.Attribute):
        return fn.attr
    if isinstance(fn, ast.Name):
        return fn.id
    return ""


def _literal_strings(node: ast.AST) -> list[str]:
    """Every string literal reachable inside `node` (covers f-strings and joins)."""
    out: list[str] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            out.append(sub.value)
    return out


def _referenced_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            names.add(sub.id)
        elif isinstance(sub, ast.Attribute):
            names.add(sub.attr)
    return names


def _called_names(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            n = _call_name(sub)
            if n:
                out.add(n)
    return out


def _root_ref(node: ast.AST) -> str | None:
    """Reduce `x`, `self.csv_path`, `guarded.filepath` to a single taint-lookup key.

    `self.csv_path` -> 'self.csv_path' (class-attr key). A bare Name -> its id.
    Anything else (calls, subscripts, joins) -> None; those are handled by
    `_classify_call`'s literal/call-based paths instead.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
        return f"self.{node.attr}"
    if isinstance(node, ast.Attribute):
        # `guarded.filepath` -- taint follows the base object, not the attr name,
        # since admit_csv_path()/admit_corpus() results expose their path via
        # `.filepath`. Look through one `.attr` hop onto the base.
        base = _root_ref(node.value)
        return base
    return None


def _expr_is_gated(node: ast.AST) -> bool:
    """True if a seam/locator call appears anywhere in `node` (e.g. the RHS of
    `csv_path = admit_csv_path(csv_path, symbol_hint).filepath` -- the Call sits
    one `.filepath` Attribute hop below the top of the expression, so a top-level
    `isinstance(node, ast.Call)` check alone misses it)."""
    return bool(_called_names(node) & (GATED_CALLS | CORPUS_CALLABLES))


class _TaintVisitor(ast.NodeVisitor):
    """Scope-aware pass finding reader calls whose argument traces back to a seam call.

    Two propagation rules, matched to how this codebase actually writes the pattern
    (verified against backtest_v2.py, export_xauusd_window.py, build_bar_matrix.py):

      1. Local reassignment within one function, in statement order:
             csv_path = admit_csv_path(csv_path, instrument).filepath   # GATED now
             df = pd.read_csv(csv_path)                                # -> GATED
      2. `self.<attr> = <gated-or-tainted expr>` in ANY method taints `self.<attr>`
         for the whole class (constructor sets it, a later method reads it):
             self.csv_path = csv_path   # already GATED per rule 1
             ...
             raw_df = pd.read_csv(self.csv_path)   # -> GATED

    Conservative on purpose: an attr tainted anywhere in the class is treated as
    tainted everywhere in it. A census under-reporting the migration surface would
    be the wrong failure mode; over-crediting a handful of ambiguous attrs is not.
    """

    def __init__(self, module_consts: dict[str, str], class_self_gated: set[str]):
        self.module_consts = module_consts
        self.class_self_gated = class_self_gated  # names of the form 'self.attr'
        self.local_gated: set[str] = set()
        self.findings: list[tuple[ast.Call, str, str]] = []  # (node, class, evidence)

    def _taint_of(self, node: ast.AST) -> str | None:
        ref = _root_ref(node)
        if ref is None:
            return None
        if ref in self.local_gated or ref in self.class_self_gated:
            return ref
        return None

    def visit_Assign(self, node: ast.Assign) -> None:
        self.generic_visit(node)
        gated = _expr_is_gated(node.value) or self._taint_of(node.value) is not None
        for tgt in node.targets:
            ref = _root_ref(tgt)
            if ref is None:
                continue
            if gated:
                self.local_gated.add(ref)
            else:
                self.local_gated.discard(ref)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node)
        if name in READER_CALLS:
            args = list(node.args) + [kw.value for kw in node.keywords if kw.value]
            if args:
                t = self._taint_of(args[0])
                if t is not None and not (name == "open" and False):
                    self.findings.append((node, CLASS_GATED, f"traced to seam via {t!r}"))
        self.generic_visit(node)


# ── Durable, location-independent finding identity ────────────────────────────
# Same precedent as scripts/analysis/feature_math_lint.py's `_durable_key`/`_enclosing_qualname`/
# `_build_parent_map` (module->class->function path + content hash, not a line number) — required
# for corpus_read_lint.py's ratchet to survive unrelated edits shifting line numbers. Reused by
# name, not forked logic-for-logic, so the two ratchets can never silently drift apart in shape.
def _build_parent_map(tree: ast.AST) -> dict:
    parents: dict = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            parents[c] = n
    return parents


def _enclosing_qualname(node: ast.AST, parents: dict) -> str:
    """module->class->function path enclosing `node` (e.g. 'CandleLoader.stream')."""
    names: list[str] = []
    cur = parents.get(node)
    while cur is not None:
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(cur.name)
        cur = parents.get(cur)
    return ".".join(reversed(names)) or "<module>"


def _durable_key(rel: str, qualname: str, call_name: str, call_node: ast.Call) -> str:
    """Location-independent, content-sensitive finding identity. Editing the call's arguments
    (AST dump) OR moving it to another function/class (qualname) changes the key -> an allowlist
    entry keyed on this goes stale exactly when it should (the site genuinely changed), and never
    goes stale merely because an unrelated line was inserted above it."""
    payload = "\0".join([rel, qualname, call_name, ast.dump(call_node, annotate_fields=False)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _collect_class_self_gated(class_node: ast.ClassDef) -> set[str]:
    """First pass over every method: which `self.<attr>` names are ever assigned
    from a seam call or from something already known to trace to one, within that
    same method's local taint (single pass per method, ignores cross-method locals
    other than `self.*` -- matches the pattern actually used here)."""
    gated: set[str] = set()
    for item in ast.walk(class_node):
        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        local_gated: set[str] = set()
        for stmt in ast.walk(item):
            if not isinstance(stmt, ast.Assign):
                continue
            is_gated = _expr_is_gated(stmt.value)
            if not is_gated:
                ref = _root_ref(stmt.value)
                if ref is not None and (ref in local_gated or ref in gated):
                    is_gated = True
            for tgt in stmt.targets:
                ref = _root_ref(tgt)
                if ref is None:
                    continue
                if ref.startswith("self."):
                    if is_gated:
                        gated.add(ref)
                else:
                    if is_gated:
                        local_gated.add(ref)
                    else:
                        local_gated.discard(ref)
    return gated


def _classify_path_text(text: str) -> str | None:
    """CORPUS / DERIVED for a resolvable path-ish string, else None (undecided)."""
    norm = text.replace("\\", "/")
    stem = norm.rsplit("/", 1)[-1]
    if _DERIVED_DIR_RE.search(norm):
        return CLASS_DERIVED
    if _CORPUS_NAME_RE.search(stem):
        # A corpus-shaped name still loses to a derived stem marker
        # (`XAUUSD_M15_second_low_events.csv` is an events file, not a corpus).
        if _DERIVED_STEM_RE.search(stem):
            return CLASS_DERIVED
        return CLASS_CORPUS
    if norm.startswith("data/") or "/data/" in norm:
        if _DERIVED_STEM_RE.search(stem):
            return CLASS_DERIVED
        if stem.endswith((".csv", ".xlsx", ".xlsm")):
            return CLASS_CORPUS
    if stem.endswith((".json", ".jsonl", ".yaml", ".yml", ".md", ".txt", ".parquet")):
        return CLASS_DERIVED
    return None


def _classify_call(node: ast.Call, module_consts: dict[str, str]) -> tuple[str, str]:
    """Return (classification, evidence)."""
    args: list[ast.AST] = list(node.args) + [kw.value for kw in node.keywords if kw.value]
    if not args:
        return CLASS_UNKNOWN, "no positional/keyword argument to inspect"

    target = args[0]

    # 1. A gated locator anywhere in the argument expression wins outright.
    called = _called_names(target)
    if called & CORPUS_CALLABLES:
        return CLASS_GATED, f"path from gated locator: {sorted(called & CORPUS_CALLABLES)}"
    if called & GATED_CALLS:
        return CLASS_GATED, f"path from seam call: {sorted(called & GATED_CALLS)}"

    # 2. Known corpus constants.
    names = _referenced_names(target)
    hit = names & CORPUS_CONSTANTS
    if hit:
        return CLASS_CORPUS, f"corpus constant: {sorted(hit)}"

    # 3. Literal strings in the expression (covers f-strings and os.path.join).
    lits = _literal_strings(target)
    verdicts = {v for v in (_classify_path_text(s) for s in lits) if v}
    if verdicts == {CLASS_CORPUS}:
        return CLASS_CORPUS, f"literal path: {lits!r}"
    if verdicts == {CLASS_DERIVED}:
        return CLASS_DERIVED, f"literal path: {lits!r}"
    if verdicts:
        return CLASS_UNKNOWN, f"ambiguous literals {sorted(verdicts)}: {lits!r}"

    # 4. Module-level constant assigned a literal path.
    for n in sorted(names):
        if n in module_consts:
            v = _classify_path_text(module_consts[n])
            if v:
                return v, f"module constant {n} = {module_consts[n]!r}"

    return CLASS_UNKNOWN, f"unresolvable path expression (names={sorted(names)[:6]})"


def _module_constants(tree: ast.Module) -> dict[str, str]:
    """Module-level `NAME = "literal"` assignments, for one hop of resolution."""
    out: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            tgt = node.targets[0]
            if isinstance(tgt, ast.Name):
                lits = _literal_strings(node.value)
                if len(lits) == 1:
                    out[tgt.id] = lits[0]
    return out


def _unparseable_key(rel: str, marker: str, evidence: str) -> str:
    """Fallback durable_key for a file this census cannot even parse into an AST (no Call
    node exists to hash). Content-based on the error message itself: a file whose syntax
    error changes (fixed, or changed differently) gets a new key, same staleness semantics
    as the AST-based `_durable_key` -- it just has no AST to hash instead."""
    payload = "\0".join([rel, marker, evidence])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def scan_file(path: Path) -> list[dict]:
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        rel = path.relative_to(_ROOT).as_posix()
        evidence = f"read error: {exc}"
        return [{
            "file": rel, "line": 0, "call": "<unreadable>", "qualname": "<module>",
            "durable_key": _unparseable_key(rel, "<unreadable>", evidence),
            "class": CLASS_UNKNOWN, "evidence": evidence,
        }]
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as exc:
        rel = path.relative_to(_ROOT).as_posix()
        evidence = str(exc)
        return [{
            "file": rel, "line": exc.lineno or 0, "call": "<syntax-error>",
            "qualname": "<module>",
            "durable_key": _unparseable_key(rel, "<syntax-error>", evidence),
            "class": CLASS_UNKNOWN, "evidence": evidence,
        }]

    consts = _module_constants(tree)
    rel = path.relative_to(_ROOT).as_posix()

    # ── Pass 1: taint trace, one fresh scope per function (never shared across
    # functions -- a name tainted in one function must not leak into another's). ──
    # A node classified GATED here is authoritative; it is excluded from pass 2 so
    # the literal/module-constant fallback never overrides a traced-through gate.
    gated_lines: dict[int, str] = {}  # lineno -> evidence (adequate: reader calls
                                       # essentially never share a line in this codebase)

    def _run_scope(node: ast.AST, self_gated: set[str]) -> None:
        tv = _TaintVisitor(consts, self_gated)
        tv.visit(node)
        for call_node, _klass, evidence in tv.findings:
            gated_lines[call_node.lineno] = evidence

    # Direct children of the module only (not ast.walk) -- each top-level def/class
    # gets its own scope; a nested def inside one is picked up by that scope's
    # `generic_visit` recursion (a reasonable approximation: a closure's locals get
    # folded into its enclosing function's taint set rather than isolated, which
    # only ever makes tracing MORE permissive within one already-related function).
    top_level_only = [
        n for n in tree.body
        if not isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    _run_scope(ast.Module(body=top_level_only, type_ignores=[]), set())

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            self_gated = _collect_class_self_gated(node)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    _run_scope(item, self_gated)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _run_scope(node, set())

    # ── Pass 2: every reader call, GATED trace wins, else literal/module-const rules ──
    parents = _build_parent_map(tree)
    findings: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name not in READER_CALLS:
            continue
        if node.lineno in gated_lines:
            klass, evidence = CLASS_GATED, gated_lines[node.lineno]
        else:
            klass, evidence = _classify_call(node, consts)
        # `open()` is overwhelmingly non-corpus; only report it when it resolves to a corpus
        # or is traced GATED (an ungated open() that turns out to read a corpus after admission
        # would be worth seeing, but a GATED open() is not worth reporting as a finding).
        if name == "open" and klass not in (CLASS_CORPUS,):
            continue
        qualname = _enclosing_qualname(node, parents)
        findings.append({
            "file": rel, "line": node.lineno, "call": name,
            "qualname": qualname,
            "durable_key": _durable_key(rel, qualname, name, node),
            "class": klass, "evidence": evidence,
        })

    # Disambiguate genuine content-collisions: two textually-identical reader calls (same
    # qualname + call name + argument AST) in one function hash to the same durable_key --
    # e.g. `DictReader(f)` opened twice in one loop body. Findings are already in ast.walk's
    # (stable, source-order) traversal order, so numbering repeats in that order is stable
    # across runs on an unchanged file. The FIRST occurrence's key is left untouched (only
    # actual duplicates change), so a file with no collisions is byte-identical to before
    # this existed.
    seen: dict[str, int] = {}
    for f in findings:
        base = f["durable_key"]
        idx = seen.get(base, 0)
        seen[base] = idx + 1
        if idx > 0:
            f["durable_key"] = f"{base}-occ{idx}"
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, default=None, help="write the full manifest here")
    ap.add_argument("--class", dest="klass", default=None,
                    choices=[CLASS_CORPUS, CLASS_DERIVED, CLASS_GATED, CLASS_UNKNOWN],
                    help="print only sites of this class")
    args = ap.parse_args(argv)

    files = _iter_py_files()
    findings: list[dict] = []
    for f in files:
        findings.extend(scan_file(f))
    findings.sort(key=lambda r: (r["file"], r["line"], r["call"]))

    counts = {c: 0 for c in (CLASS_CORPUS, CLASS_DERIVED, CLASS_GATED, CLASS_UNKNOWN)}
    for r in findings:
        counts[r["class"]] = counts.get(r["class"], 0) + 1

    manifest = {
        "script_version": SCRIPT_VERSION,
        "files_scanned": len(files),
        "counts": counts,
        "findings": findings,
    }

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    shown = [r for r in findings if args.klass is None or r["class"] == args.klass]
    for r in shown:
        print(f"{r['class']:<8} {r['file']}:{r['line']}  {r['call']}()  -- {r['evidence']}")

    print()
    print(f"files scanned : {len(files)}")
    for c in (CLASS_CORPUS, CLASS_UNKNOWN, CLASS_GATED, CLASS_DERIVED):
        print(f"  {c:<8} {counts[c]}")
    print()
    print(f"MIGRATION SURFACE (CORPUS + UNKNOWN) = {counts[CLASS_CORPUS] + counts[CLASS_UNKNOWN]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
