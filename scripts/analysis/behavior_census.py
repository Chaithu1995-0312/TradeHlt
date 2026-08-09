"""
behavior_census.py
==================
CONFIG-FIRST AUDIT (read-only): inventory the BEHAVIORAL magic numbers still living as
code literals in the live-spine source, and classify every module/class-level numeric
constant as STRUCTURAL / BEHAVIORAL / GOAL_SEEKING. The config-first sibling of
``config_reachability.py`` (which audits config keys → code; this audits code literals →
config-readiness).

Why
    The config-first doctrine (docs/research-readiness/config-first-doctrine.md, STAGING)
    wants the engine FROZEN and behavior MUTABLE-via-config. A behavioral constant baked
    into Python forces a code edit (and bypasses governance/hash/validation) to tune. This
    tool makes "what behavior is still hardcoded" machine-checkable, and is the evidence
    engine the doctrine rests on. It mutates nothing.

Method (purely static, AST)
    - Scan live-spine packages (src/core, src/engines, src/config_layer); skip dormant /
      sidecar modules (F-012) and __init__ files.
    - Collect module-level + class-level numeric constant assignments (ints/floats and
      tuples/lists/dicts of numerics). Function-signature defaults are NOT collected — a
      canonical default in a constructor signature that the live path always overrides via
      from_prod_config is config-readiness-OK, not a hidden runtime constant.
    - Classify each by NAME heuristic into STRUCTURAL / BEHAVIORAL / GOAL_SEEKING /
      UNCLASSIFIED.
    - Detect per-module config wiring (from_prod_config / get_prod_section / _require / a
      cfg-read), so BEHAVIORAL constants in NON-wired modules surface as the "future config
      opportunities" backlog.

Classification (BEHAVIORAL is the doctrine's target class)
    STRUCTURAL    feature/buffer geometry — periods, dims, window/buffer sizes, precision,
                  schema/seed. Frozen; leave in code.
    BEHAVIORAL    thresholds, percentiles, clamps, penalties, weights, multipliers, rates,
                  ratios, decays, quotas, tier/accept bands. Belongs in config.
    GOAL_SEEKING  search/optimization knobs (tuner/expansion/search modules).
    UNCLASSIFIED  numeric constant whose name did not match — reported for a human.

Usage
    python scripts/analysis/behavior_census.py            # writes JSON + MD report
    python scripts/analysis/behavior_census.py --check     # exit 1 if a migrated module regresses
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"

# Live-spine packages to scan (decision/scoring path). Research + scripts excluded.
# T-10 (2026-07-19): `features` added. The feature layer was previously invisible to this census
# entirely — so the 36 constants migrated to config on 2026-07-18/19, and the ~12 still hardcoded,
# were unmeasurable here. NOTE most feature_pipeline literals live in METHOD BODIES, which the
# module/class-level collector cannot see; `_collect_function_constants` covers that layer and is
# reported separately (see `function_constants`).
_SCAN_DIRS = ("core", "engines", "config_layer", "features",
              # Widened 2026-07-29 (target-strategy-architecture.md sec13 item3 / sec14.B):
              # the original scope never covered the backtest hot loop itself, which is
              # exactly where F-056 found real undeclared trade-affecting constants
              # (partial_tp_fraction, sl_atr_buffer, p_win<0.35). journal/governance added
              # for the same reason — trade-ledger and promotion-path constants belong in
              # the same audit.
              "runtime", "journal", "governance")

# Dormant / sidecar module path fragments (F-012, F-005). Constants here are not live.
_DORMANT_FRAGMENTS = (
    "replay_memory", "cognitive_bus", "cognitivebus", "cluster", "hmf",
    "tradenet", "scanner", "execution_loop", "portfolio_alloc",
)

# ── Name → class heuristics (curated, auditable) ─────────────────────────────
_STRUCTURAL_RE = re.compile(
    r"(_period$|_periods$|_dim$|_dims$|maxlen|_window$|_window_|window_size|"
    r"precision|schema|_seed$|n_features|vector|buffer)", re.IGNORECASE,
)
_BEHAVIORAL_RE = re.compile(
    r"(threshold|percentile|_pct$|_percent|penalty|weight|_min$|_max$|floor|ceil|"
    r"_rate|_ratio|multiplier|_mult$|lambda|decay|alpha|beta|k_sigma|sig_|_step$|"
    r"quota|tier|accept|conf_|margin|band|warmup)", re.IGNORECASE,
)
_GOAL_SEEKING_RE = re.compile(r"(tuner|expansion|optim|search|sweep|candidate)", re.IGNORECASE)

# ── External-injection detection (WI-1: fix the census over-reporting blind spot) ──
# A behavioral constant can be config-driven even when its OWN file never reads config — the
# value is injected by an EXTERNAL constructor. Two signals make this auditable:
#   (a) the constant's field NAME is read as a config key somewhere in the live corpus, or
#   (b) the constant lives on a curated config-schema class built from config elsewhere.
# Curated schema classes (mirrors config_reachability's curated maps; kept explicit + small):
#   CRTConfig   — built by production_config from params + crt_engine (dataclasses.fields, no
#                 string literals, so the corpus scan alone cannot see it).
#   FusionConfig — built by engine_runner from the fusion_engine section via _cfg_require.
_CONFIG_SCHEMA_CLASSES = {"CRTConfig", "FusionConfig"}

# String literal read as a config key: 2nd positional arg of a *require* accessor, or .get("key").
_KEY_READ_RE = re.compile(
    r"""(?:_cfg_require|_require_decision_cfg|_planner_require)\s*\([^,]+,\s*["']([A-Za-z_]\w*)["']"""
    r"""|\.get\(\s*["']([A-Za-z_]\w*)["']""",
)


def _collect_read_keys(files: list[Path]) -> set[str]:
    """Config-key string literals read anywhere in the live corpus (the external-wiring evidence)."""
    keys: set[str] = set()
    for p in files:
        for m in _KEY_READ_RE.finditer(p.read_text(encoding="utf-8")):
            keys.add(m.group(1) or m.group(2))
    return keys

# Modules migrated under the config-first doctrine (Batch A). The regression floor below
# pins their state so behavior cannot silently drift back into code.
#   - dynamic_threshold: must carry ZERO behavioral module/class constants (fully removed).
#   - the rest: must be config-wired (expose from_prod_config / read a config section).
_MIGRATED_NO_CONST = ("core/dynamic_threshold.py",)
_MIGRATED_WIRED = (
    "core/regime_governor.py",
    "core/convergence_controller.py",
    "core/acceptance_controller.py",
)


def _rel(p: Path) -> str:
    return p.relative_to(_SRC).as_posix()


def _iter_live_files() -> list[Path]:
    out: list[Path] = []
    for d in _SCAN_DIRS:
        for p in sorted((_SRC / d).rglob("*.py")):
            if p.name == "__init__.py":
                continue
            rel = _rel(p)
            if any(frag in rel.lower() for frag in _DORMANT_FRAGMENTS):
                continue
            out.append(p)
    return out


def _numeric_repr(node: ast.AST) -> str | None:
    """Return a compact repr if node is a numeric literal / container of numerics, else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return repr(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)) and isinstance(node.operand, ast.Constant):
        if isinstance(node.operand.value, (int, float)) and not isinstance(node.operand.value, bool):
            return ("-" if isinstance(node.op, ast.USub) else "") + repr(node.operand.value)
    if isinstance(node, (ast.Tuple, ast.List)):
        parts = [_numeric_repr(e) for e in node.elts]
        if parts and all(p is not None for p in parts):
            return ("[" + ", ".join(parts) + "]")  # container of numerics
    if isinstance(node, ast.Dict):
        vals = [_numeric_repr(v) for v in node.values]
        if vals and all(v is not None for v in vals):
            return "{...numeric...}"
    return None


# Output/result + runtime-state schema classes — their numeric field defaults are neutral
# placeholders (overwritten at construction / runtime), NOT tunable behavior → STRUCTURAL.
# `*State` is caught by the regex; the curated set covers the runtime record/state dataclasses in
# crt_engine_v2 whose field defaults the actual tunable knobs already govern from config
# (e.g. RiskScore.decay_factor←score_decay_lambda, Trade.risk_pct←sizing_bands,
#  EngineState.soft_conf_candles←soft_conf_max_candles).
_RESULT_SCHEMA_RE = re.compile(r"(Result|Record|Stats|Snapshot|Report|Output|State)$")
_RUNTIME_STATE_CLASSES = {"Trade", "RiskScore", "Candle", "SweepEvent"}


def _classify(name: str, rel: str, scope: str = "<module>") -> str:
    if _GOAL_SEEKING_RE.search(rel) or _GOAL_SEEKING_RE.search(name):
        return "GOAL_SEEKING"
    # Output/state-schema field defaults are placeholders, not behavior.
    if _RESULT_SCHEMA_RE.search(scope) or scope in _RUNTIME_STATE_CLASSES:
        return "STRUCTURAL"
    # Structural takes precedence (a *_window_size is structural even if it contains 'size').
    if _STRUCTURAL_RE.search(name):
        return "STRUCTURAL"
    if _BEHAVIORAL_RE.search(name):
        return "BEHAVIORAL"
    return "UNCLASSIFIED"


def _collect_constants(tree: ast.AST, rel: str) -> list[dict]:
    """Module-level + class-level numeric constant assignments (NOT function-body / signature)."""
    found: list[dict] = []

    def _scan_body(body, scope: str):
        for node in body:
            targets = []
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
                value = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id]
                value = node.value
            else:
                if isinstance(node, ast.ClassDef):
                    _scan_body(node.body, scope=node.name)  # class-level constants
                continue
            if value is None:
                continue
            rep = _numeric_repr(value)
            if rep is None:
                continue
            for nm in targets:
                found.append({
                    "name": nm,
                    "value": rep,
                    "line": node.lineno,
                    "scope": scope,
                    "verdict": _classify(nm, rel, scope),
                })

    _scan_body(tree.body, scope="<module>")
    return found


def _collect_function_constants(tree: ast.AST, rel: str) -> list[dict]:
    """FUNCTION-BODY numeric constants — reported SEPARATELY from `_collect_constants`.

    T-10 (2026-07-19). `_collect_constants` deliberately sees only module/class-level
    assignments, which is the right scope for the config-first maturity ladder (a signature
    default overridden via `from_prod_config` is config-readiness-OK, not hidden debt).

    But that scope MISSES an entire class of hidden runtime constant: a literal assigned inside a
    method body, e.g. ``_ROLL_N = 200`` / ``window = 5`` in `feature_pipeline.compute_*`. Those
    are exactly the numbers the config-first doctrine cares about, and they were invisible.

    Reported under a DISTINCT key rather than merged into `behavioral`/`hardcoded`, on purpose:
    the existing regression floors (e.g. `test_crt_engine_no_genuine_hardcoded`) assert those
    lists are empty. Merging would break them — not because anything regressed, but because the
    measurement definition changed. Keeping this additive preserves the meaning of every existing
    assertion while making the new layer visible.
    """
    found: list[dict] = []

    def _walk(body, cls_scope: str | None):
        for node in body:
            if isinstance(node, ast.ClassDef):
                _walk(node.body, cls_scope=node.name)
                continue
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            fq = f"{cls_scope}.{node.name}" if cls_scope else node.name
            for sub in ast.walk(node):
                targets = []
                if isinstance(sub, ast.Assign):
                    targets = [t.id for t in sub.targets if isinstance(t, ast.Name)]
                    value = sub.value
                elif isinstance(sub, ast.AnnAssign) and isinstance(sub.target, ast.Name):
                    targets = [sub.target.id]
                    value = sub.value
                else:
                    continue
                if value is None:
                    continue
                rep = _numeric_repr(value)
                if rep is None:
                    continue
                for nm in targets:
                    found.append({
                        "name": nm,
                        "value": rep,
                        "line": sub.lineno,
                        "scope": f"def {fq}",
                        "verdict": _classify(nm, rel, fq),
                    })

    _walk(tree.body, cls_scope=None)
    return found


def _is_config_wired(source: str) -> bool:
    return (
        "from_prod_config" in source
        or "get_prod_section" in source
        or "_require_decision_cfg" in source
        or "_cfg_require" in source
        or "_planner_require" in source
    )


def _maturity(behavioral_total: int, hardcoded_count: int, config_wired: bool) -> str:
    """Behavior-ladder maturity (GOAL_SEEKING is orthogonal — see is_goal_seeking marker, never a rung).
        CONFIG_DRIVEN  zero behavioral code constants (fully externalized)
        CONFIG_WIRED   behavioral canonical-defaults remain BUT every one routes through config
                       (in-file from_prod_config OR externally injected by a consumer/schema class)
        HARD_CODED     genuine magic-number debt remains (behavioral consts neither in-file- nor
                       externally-wired)"""
    if behavioral_total == 0:
        return "CONFIG_DRIVEN"
    if hardcoded_count == 0 and config_wired:
        return "CONFIG_WIRED"
    if hardcoded_count == 0:
        # all behavioral consts are externally wired (e.g. FusionConfig built by engine_runner)
        return "CONFIG_WIRED"
    return "HARD_CODED"


def build_report() -> dict:
    modules: dict[str, dict] = {}
    summary = {"STRUCTURAL": 0, "BEHAVIORAL": 0, "GOAL_SEEKING": 0, "UNCLASSIFIED": 0}
    maturity_summary = {"CONFIG_DRIVEN": 0, "CONFIG_WIRED": 0, "HARD_CODED": 0}
    future_opportunities: list[str] = []

    files = _iter_live_files()
    read_keys = _collect_read_keys(files)  # corpus-wide external-wiring evidence (WI-1)

    for p in files:
        rel = _rel(p)
        src = p.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        consts = _collect_constants(tree, rel)
        # T-10: collect function-body constants BEFORE the skip decision. feature_pipeline.py has
        # ZERO module/class-level constants (SWING_WINDOW became a lazy __getattr__), so the old
        # ordering skipped the single most constant-dense module in the feature layer outright —
        # a silent blind spot that would have read as "clean".
        fn_consts = _collect_function_constants(tree, rel)
        # Always include the explicitly-tracked migrated modules even when they carry zero
        # constants (e.g. dynamic_threshold.py after full externalization) so their maturity
        # is reported + assertable, not silently absent.
        if not consts and not fn_consts and rel not in (_MIGRATED_NO_CONST + _MIGRATED_WIRED):
            continue
        wired = _is_config_wired(src)
        bucket = {"behavioral": [], "structural": [], "goal_seeking": [], "unclassified": [],
                  "config_wired": wired, "externally_wired": [], "hardcoded": []}
        hardcoded_count = 0
        for c in consts:
            summary[c["verdict"]] += 1
            key = {"BEHAVIORAL": "behavioral", "STRUCTURAL": "structural",
                   "GOAL_SEEKING": "goal_seeking", "UNCLASSIFIED": "unclassified"}[c["verdict"]]
            label = f"{c['scope']}.{c['name']}={c['value']} (L{c['line']})"
            bucket[key].append(label)
            if c["verdict"] != "BEHAVIORAL":
                continue
            # External-injection: name read as a config key anywhere, OR owned by a schema class.
            ext_wired = (c["name"] in read_keys) or (c["scope"] in _CONFIG_SCHEMA_CLASSES)
            if ext_wired:
                bucket["externally_wired"].append(label)
            if wired or ext_wired:
                continue  # routed through config (in-file or external) — not genuine debt
            # Genuine HARD_CODED debt = future config opportunity.
            hardcoded_count += 1
            bucket["hardcoded"].append(label)
            future_opportunities.append(f"{rel}:{c['line']} {c['name']}={c['value']}")
        # Maturity ladder (behavior) + orthogonal goal-seeking marker (kept separate from the
        # goal_seeking constant LIST so the marker never becomes a maturity rung).
        # T-10: function-body constants, ADDITIVE and non-maturity-affecting (see
        # _collect_function_constants for why they are not merged into `behavioral`/`hardcoded`).
        bucket["function_constants"] = [
            f"{c['scope']}.{c['name']}={c['value']} (L{c['line']})" for c in fn_consts
        ]
        bucket["function_behavioral"] = [
            f"{c['scope']}.{c['name']}={c['value']} (L{c['line']})"
            for c in fn_consts if c["verdict"] == "BEHAVIORAL"
        ]
        bucket["maturity"] = _maturity(len(bucket["behavioral"]), hardcoded_count, wired)
        bucket["is_goal_seeking"] = bool(bucket["goal_seeking"])
        maturity_summary[bucket["maturity"]] += 1
        modules[rel] = bucket

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "maturity_summary": maturity_summary,
        "future_config_opportunities": sorted(future_opportunities),
        "modules": dict(sorted(modules.items())),
    }


def check_migrated(report: dict) -> list[str]:
    """Return regression messages (empty = clean) for the Batch-A migrated modules. Pins the
    maturity ladder so behavior cannot silently drift back into code."""
    problems: list[str] = []
    mods = report["modules"]
    for rel in _MIGRATED_NO_CONST:
        b = mods.get(rel, {})
        if b.get("behavioral"):
            problems.append(f"{rel}: behavioral constants must be fully removed, found {b['behavioral']}")
        if b and b.get("maturity") != "CONFIG_DRIVEN":
            problems.append(f"{rel}: maturity must be CONFIG_DRIVEN, got {b.get('maturity')}")
    for rel in _MIGRATED_WIRED:
        b = mods.get(rel)
        if b is None:
            continue  # no constants at all is fine
        if not b.get("config_wired"):
            problems.append(f"{rel}: migrated module is no longer config-wired (from_prod_config missing)")
        if b.get("maturity") not in ("CONFIG_WIRED", "CONFIG_DRIVEN"):
            problems.append(f"{rel}: maturity regressed to {b.get('maturity')} (expected CONFIG_WIRED/CONFIG_DRIVEN)")
    return problems


def _to_markdown(report: dict) -> str:
    s = report["summary"]
    m = report["maturity_summary"]
    lines = [
        "# Behavior Census — live-spine BEHAVIORAL constant inventory",
        "",
        f"_Generated {report['generated_at']} by `scripts/analysis/behavior_census.py` (read-only)._",
        "",
        f"**Totals** — BEHAVIORAL {s['BEHAVIORAL']} · STRUCTURAL {s['STRUCTURAL']} · "
        f"GOAL_SEEKING {s['GOAL_SEEKING']} · UNCLASSIFIED {s['UNCLASSIFIED']}",
        "",
        f"**Maturity ladder** (behavior) — CONFIG_DRIVEN {m['CONFIG_DRIVEN']} · "
        f"CONFIG_WIRED {m['CONFIG_WIRED']} · HARD_CODED {m['HARD_CODED']}  "
        f"_(GOAL_SEEKING is orthogonal, not a rung)_",
        "",
        "## Maturity by module (behavioral modules)",
        "",
        "_Behavioral = all behavioral literals; Hardcoded = genuine debt (neither in-file- nor "
        "externally-wired); Ext-wired = config-injected by a consumer/schema class._",
        "",
        "| Module | Behavioral | Ext-wired | Hardcoded | Maturity | Goal-seeking |",
        "|---|---|---|---|---|---|",
    ]
    _tracked = _MIGRATED_NO_CONST + _MIGRATED_WIRED
    for rel, b in report["modules"].items():
        # Show behavioral modules, goal-seeking modules, and the tracked migrated exemplars
        # (incl. fully-externalized ones with 0 behavioral consts); skip pure-structural noise.
        if not b["behavioral"] and not b["is_goal_seeking"] and rel not in _tracked:
            continue
        lines.append(
            f"| `{rel}` | {len(b['behavioral'])} | {len(b['externally_wired'])} | "
            f"{len(b['hardcoded'])} | {b['maturity']} | {'yes' if b['is_goal_seeking'] else '-'} |"
        )
    lines += [
        "",
        "## Future config opportunities (GENUINE HARD_CODED debt — excludes externally-wired)",
        "",
    ]
    fo = report["future_config_opportunities"]
    lines += [f"- `{x}`" for x in fo] if fo else ["_none_"]
    lines += ["", "## Per-module", ""]
    for rel, b in report["modules"].items():
        wired = "config-wired" if b["config_wired"] else "NOT config-wired"
        lines.append(f"### `{rel}` — {b['maturity']} · {wired}")
        for label, key in (("BEHAVIORAL", "behavioral"), ("STRUCTURAL", "structural"),
                           ("GOAL_SEEKING", "goal_seeking"), ("UNCLASSIFIED", "unclassified")):
            if b[key]:
                lines.append(f"- **{label}**: " + "; ".join(b[key]))
        if b.get("externally_wired"):
            lines.append(f"- **EXTERNALLY-WIRED** (config-injected, not debt): " + "; ".join(b["externally_wired"]))
        if b.get("hardcoded"):
            lines.append(f"- **GENUINE HARD_CODED**: " + "; ".join(b["hardcoded"]))
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Config-first behavior census (read-only).")
    ap.add_argument("--check", action="store_true", help="exit 1 if a migrated module regressed")
    args = ap.parse_args()

    report = build_report()
    problems = check_migrated(report)

    if args.check:
        if problems:
            print("BEHAVIOR CENSUS REGRESSION:")
            for p in problems:
                print(f"  - {p}")
            return 1
        print("behavior census: migrated modules OK")
        return 0

    out_dir = _ROOT / "docs" / "research-readiness"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "behavior-census-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    (out_dir / "behavior-census-report.md").write_text(_to_markdown(report), encoding="utf-8")
    s = report["summary"]
    mat = report["maturity_summary"]
    print(f"behavior census written → docs/research-readiness/behavior-census-report.{{json,md}}")
    print(f"  BEHAVIORAL {s['BEHAVIORAL']} · STRUCTURAL {s['STRUCTURAL']} · "
          f"GOAL_SEEKING {s['GOAL_SEEKING']} · UNCLASSIFIED {s['UNCLASSIFIED']}")
    print(f"  maturity: CONFIG_DRIVEN {mat['CONFIG_DRIVEN']} · CONFIG_WIRED {mat['CONFIG_WIRED']} · "
          f"HARD_CODED {mat['HARD_CODED']}")
    print(f"  future config opportunities: {len(report['future_config_opportunities'])}")
    if problems:
        print("  WARNING — migrated-module regressions:")
        for p in problems:
            print(f"    - {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
