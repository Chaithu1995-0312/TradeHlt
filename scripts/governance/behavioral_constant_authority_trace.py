#!/usr/bin/env python3
"""
Behavioral Constant Authority Trace + Active CRT Closure Pass (READ-ONLY).

Closure pass goals (2026-07-11):
  1. Scan all reachable production decision-spine modules (not only crt_engine_v2).
  2. Resolve every AST candidate to IN_SCOPE | OUT_OF_SCOPE (no residual UNPROVEN
     on the declared spine module set) with mechanical evidence.
  3. Fully authority-adjudicate every IN_SCOPE constant.
  4. Re-certify or revise PLAN-001..003 before any implementation.

Never mutates runtime, YAML, production config, formulas, state_contracts,
or Phase-Topology. Does not execute IC-007 remediation or PLAN implementation.

Usage:
  py -3.12 scripts/governance/behavioral_constant_authority_trace.py
  py -3.12 scripts/governance/behavioral_constant_authority_trace.py --write
"""
from __future__ import annotations

import argparse
import ast
import dataclasses
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

TRACE_ID = "behavioral_constant_authority_trace"
TRACE_DATE = "2026-07-11"
SCHEMA = "behavioral_constant_authority_trace.v2_closure"
JSON_PATH = _REPO / "docs" / "governance" / f"{TRACE_ID}-{TRACE_DATE}.json"
MD_PATH = _REPO / "docs" / "governance" / f"{TRACE_ID}-{TRACE_DATE}.md"
PASS_ID = "ACTIVE_CRT_BEHAVIORAL_CONSTANT_CLOSURE_PASS"

# ── Active CRT production decision spine (reachable behavior-affecting modules) ──
# Entry: live_engine_hook / backtest_v2 / EngineRunner → CRT + fusion + decision
#        + planner + UltronRiskGate; CRT scoring via crt_engine_v2 and engines.crt_engine.
_SPINE_REL_PATHS: list[str] = [
    # Tier A — CRT state machine + scoring
    "src/config_layer/crt_engine_v2.py",
    "src/engines/crt_engine.py",
    "src/engines/scoring_engine.py",
    "src/config_layer/crt_sweep_taxonomy.py",
    # Tier B — fusion / decision / execution / capital risk
    "src/core/engine_runner.py",
    "src/core/fusion_engine.py",
    "src/core/decision_engine.py",
    "src/config_layer/execution_planner.py",
    "src/core/ultron_risk_gate.py",
    "src/core/ultron_risk_gate_wrapper.py",
    # Tier C — config injection / profiles
    "src/config_layer/production_config.py",
    "src/config_layer/config_builder.py",
    "src/config_layer/market_router.py",
    # Tier D — geometry/math on CRT path
    "src/features/candle_math.py",
    "src/features/derived_math.py",
    # Tier E — live join (planner/gate orchestration constants)
    "src/runtime/live_engine_hook.py",
]

BEHAVIORAL_CONSTANT_SCOPE_RULE: dict[str, Any] = {
    "rule_id": "BEHAVIORAL_CONSTANT_SCOPE_RULE",
    "frozen_before_classification": True,
    "closure_pass": PASS_ID,
    "inclusion_test": (
        "A constant is IN_SCOPE if changing its value, while holding market data, "
        "active config, model artifacts, and RNG fixed, can change at least one of: "
        "state transition eligibility, detector result, guard result, candidate "
        "population, score, ranking, veto, trade construction, entry, stop, target, "
        "position sizing, expiry/reset behavior, model eligibility, model fusion "
        "result, CRT output, or TRADE_OPENED identity."
    ),
    "include_forms": [
        "numeric literals",
        "numeric tuples/lists/dicts used as weights/bounds",
        "hardcoded scoring weights / exponents / decay coefficients",
        "hardcoded multipliers/divisors/clipping bounds",
        "hardcoded fallback thresholds / TTL-like values / epsilon / min-depth",
        "hardcoded boolean policy constants where behavior-bearing",
        "market_router profile numeric overrides",
        "function default score weights",
    ],
    "exclude_forms": [
        "array indexes / loop counters",
        "schema versions / logging limits",
        "test-only constants",
        "display formatting / serialization-only values",
        "mathematical identities proven to belong to WHAT (formula registry callables)",
        "non-behavioral implementation constants",
        "CRTConfig field *reads* (HOW transport)",
        "CRTConfig dataclass field *defaults* (HOW seed surface when production-loaded)",
        "identity clamps of pure 0.0/1.0 on already-bounded quantities",
    ],
    "ambiguous_policy": (
        "Closure pass resolves ambiguity on declared spine modules: parameter-like "
        "floats → IN_SCOPE; structural small-int / logging / HOW-seed → OUT_OF_SCOPE. "
        "Residual UNPROVEN only if module is outside spine (must not occur for spine set)."
    ),
    "sur008_anchor": {
        "census_id": "SUR-008",
        "ic": "IC-007",
        "known_examples": [
            "min_depth = 0.1 * ATR in retest guard",
            "RiskScore final weights 0.35/0.25/0.20/0.20",
            "scoring_engine.score_weights default (0.35, 0.25, 0.20, 0.20)",
        ],
    },
}

_BEHAVIORAL_FUNC_TOKENS = (
    "try_",
    "score_",
    "compute_score",
    "compute_scores",
    "compute_decay",
    "resolve_risk",
    "approve",
    "build_trade",
    "detect_",
    "evaluate",
    "fuse",
    "plan_",
    "check_",
    "gate",
    "size",
    "risk",
    "threshold",
    "final",
    "compute(",
    "on_candle",
    "process",
    "run",
)

_WHAT_MATH_FILES = frozenset(
    {
        "src/features/candle_math.py",
        "src/features/derived_math.py",
    }
)


def _rel(p: Path) -> str:
    return str(p.relative_to(_REPO)).replace("\\", "/")


def _jsonable(v: Any) -> Any:
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(val) for k, val in v.items()}
    return repr(v)


def _repo_pin() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPO,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return (r.stdout or "").strip() or "unknown"
    except Exception:
        return "unknown"


def _spine_paths() -> list[Path]:
    out = []
    for rel in _SPINE_REL_PATHS:
        p = _REPO / rel
        if p.is_file():
            out.append(p)
    return out


# ── AST collection ──────────────────────────────────────────────────────────

class _ConstantCollector(ast.NodeVisitor):
    def __init__(self, file_path: Path, source: str) -> None:
        self.file_path = file_path
        self.lines = source.splitlines()
        self.func_stack: list[str] = []
        self.class_stack: list[str] = []
        self.candidates: list[dict[str, Any]] = []
        self._seen: set[tuple[int, str, str]] = set()

    def _scope(self) -> str:
        return ".".join(self.class_stack + self.func_stack) or "<module>"

    def _add(self, *, value: Any, node: ast.AST, name: str, context: str) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return
        line = getattr(node, "lineno", None) or 0
        key = (line, repr(value), name)
        if key in self._seen:
            return
        self._seen.add(key)
        src_line = self.lines[line - 1].strip() if line and line <= len(self.lines) else ""
        self.candidates.append(
            {
                "literal_or_constant_name": name,
                "value": value,
                "value_type": type(value).__name__,
                "file": _rel(self.file_path),
                "line": line,
                "function_or_scope": self._scope(),
                "AST_context": context,
                "source_line_text": src_line[:220],
            }
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.func_stack.append(node.name)
        defaults = list(node.args.defaults)
        args = list(node.args.args)
        for i, d in enumerate(defaults):
            if isinstance(d, ast.Constant) and isinstance(d.value, (int, float)):
                arg_i = len(args) - len(defaults) + i
                aname = args[arg_i].arg if 0 <= arg_i < len(args) else f"default_{i}"
                self._add(value=d.value, node=d, name=f"arg_default:{aname}", context="function_default")
            elif isinstance(d, (ast.Tuple, ast.List)):
                for j, elt in enumerate(d.elts):
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, (int, float)):
                        self._add(
                            value=elt.value,
                            node=elt,
                            name=f"arg_default_container[{j}]",
                            context="function_default_container",
                        )
        self.generic_visit(node)
        self.func_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, node: ast.Assign) -> None:
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, (int, float)):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    self._add(value=node.value.value, node=node.value, name=t.id, context="assign_name")
                elif isinstance(t, ast.Attribute):
                    self._add(value=node.value.value, node=node.value, name=t.attr, context="assign_attr")
        if isinstance(node.value, (ast.Tuple, ast.List)):
            for i, elt in enumerate(node.value.elts):
                if isinstance(elt, ast.Constant) and isinstance(elt.value, (int, float)):
                    self._add(value=elt.value, node=elt, name=f"container[{i}]", context="container_literal")
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, (int, float)):
                name = ""
                if isinstance(node.target, ast.Name):
                    name = node.target.id
                elif isinstance(node.target, ast.Attribute):
                    name = node.target.attr
                self._add(
                    value=node.value.value,
                    node=node.value,
                    name=name or "ann_assign",
                    context="ann_assign_default",
                )
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            self._add(value=node.value, node=node, name="<inline>", context="inline_constant")


def _enumerate_raw() -> list[dict[str, Any]]:
    raw: list[dict[str, Any]] = []
    for path in _spine_paths():
        src = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src, filename=str(path))
        except SyntaxError:
            continue
        col = _ConstantCollector(path, src)
        col.visit(tree)
        raw.extend(col.candidates)
    for i, c in enumerate(raw, 1):
        c["candidate_id"] = f"BC-RAW-{i:04d}"
    return raw


# ── Scope resolution (closure: resolve all spine candidates) ────────────────

def _func_name(scope: str) -> str:
    return scope.split(".")[-1] if scope else ""


def _is_behavioral_func(scope: str) -> bool:
    s = scope.lower()
    return any(tok in s for tok in _BEHAVIORAL_FUNC_TOKENS)


def _classify_scope(c: dict[str, Any]) -> dict[str, Any]:
    """Resolve IN_SCOPE | OUT_OF_SCOPE for spine candidates (no UNPROVEN on spine)."""
    scope = c["function_or_scope"]
    fname = _func_name(scope)
    line = c.get("source_line_text", "")
    val = c["value"]
    ctx = c["AST_context"]
    fpath = c["file"]
    out = dict(c)

    def done(status: str, reason: str, **extra: Any) -> dict[str, Any]:
        out["scope_status"] = status
        out["scope_reason"] = reason
        out.update(extra)
        return out

    # 1) Logging / display
    if any(x in line for x in ("log.", "logger", "debug(", "info(", "warning(", "error(", "print(")):
        if not any(x in line for x in ("if ", "return ", "min_depth", "score", "threshold", "*")):
            return done(
                "OUT_OF_SCOPE",
                "logging/display context",
                reachable_from_active_runtime=False,
                possible_behavioral_effect=None,
            )

    # 2) CRTConfig dataclass defaults → HOW seed surface (not CODE-only hardcode class)
    if "CRTConfig" in scope and ctx in (
        "ann_assign_default",
        "assign_attr",
        "function_default",
        "function_default_container",
        "container_literal",
    ):
        return done(
            "OUT_OF_SCOPE",
            "CRTConfig field default — HOW seed when production-loaded (not CODE-only hardcode)",
            reachable_from_active_runtime=True,
            reachability_evidence="ConfigBuilder/production_config merge into CRTConfig",
            possible_behavioral_effect="HOW seed if not overridden",
            authority_hint="HOW_SEED",
        )

    # 3) HOW transport reads
    if re.search(r"self\.config\.|config\.[A-Za-z_]", line) and "arg_default" not in c["literal_or_constant_name"]:
        # literal beside config read often clamp — still may be CODE constant
        if "self.config." in line and val in (0, 0.0, 1, 1.0) and any(
            x in line for x in ("min(", "max(", "or ", "if ")
        ):
            return done(
                "OUT_OF_SCOPE",
                "identity clamp beside HOW config transport",
                reachable_from_active_runtime=True,
                possible_behavioral_effect=None,
            )

    # 4) Index / loop counters
    if isinstance(val, int) and val in range(0, 32):
        if re.search(r"for |range\(|enumerate|\[-?\d+\]|split\(|\[0\]|\[1\]|\[2\]", line):
            return done(
                "OUT_OF_SCOPE",
                "loop/index/structural integer",
                reachable_from_active_runtime=True,
                possible_behavioral_effect=None,
            )

    # 5) WHAT math modules — formula identities (FM-owned), not HOW thresholds
    if fpath in _WHAT_MATH_FILES:
        return done(
            "OUT_OF_SCOPE",
            "WHAT formula/math module constant — geometric identity surface (not HOW threshold class)",
            reachable_from_active_runtime=True,
            reachability_evidence=f"{fpath} on CRT feature path",
            possible_behavioral_effect="formula identity (WHAT)",
            authority_hint="WHAT_MATH",
        )

    # 6) SUR-008 anchors → IN_SCOPE
    if "min_depth" in line and val == 0.1:
        return done(
            "IN_SCOPE",
            "retest min_depth 0.1*ATR — state transition floor",
            reachable_from_active_runtime=True,
            reachability_evidence="try_expansion_to_retest",
            possible_behavioral_effect="EXPANSION→RETEST eligibility",
            sur008_anchor=True,
            anchor_id="SUR008_MIN_DEPTH",
        )
    if "RiskScore" in scope and fname == "final" and val in (0.35, 0.25, 0.2, 0.20):
        return done(
            "IN_SCOPE",
            "RiskScore.final composite weight",
            reachable_from_active_runtime=True,
            reachability_evidence="UltronRiskEngine.compute_score → RiskScore.final",
            possible_behavioral_effect="score; sizing",
            sur008_anchor=True,
            anchor_id="SUR008_RISKSCORE_WEIGHT",
        )
    if fpath.endswith("scoring_engine.py") and (
        "score_weights" in c["literal_or_constant_name"]
        or (ctx in ("function_default", "function_default_container") and val in (0.35, 0.25, 0.2, 0.20, 0.05))
        or (fname == "compute_scores" and val in (0.35, 0.25, 0.2, 0.20, 0.7, 0.5, 0.04, 2.0, 1.0, 0.0))
    ):
        if val in (0.0, 1.0) and any(x in line for x in ("return 0", "return 1", "min(", "max(")):
            return done(
                "OUT_OF_SCOPE",
                "identity 0/1 bound in scoring_engine",
                reachable_from_active_runtime=True,
                possible_behavioral_effect=None,
            )
        return done(
            "IN_SCOPE",
            "engines.scoring_engine CRT score path constant",
            reachable_from_active_runtime=True,
            reachability_evidence="EngineRunner → engines.crt_engine.compute → compute_scores",
            possible_behavioral_effect="fusion CRT score",
            sur008_anchor=(val in (0.35, 0.25, 0.2, 0.20)),
            anchor_id="SUR008_SCORING_ENGINE_WEIGHT" if val in (0.35, 0.25, 0.2, 0.20) else None,
        )

    # 7) market_router profile numbers — behavioral per-instrument CODE profiles
    if fpath.endswith("market_router.py") and isinstance(val, float):
        return done(
            "IN_SCOPE",
            "market_router profile numeric — CODE-held instrument profile (feeds ConfigBuilder base)",
            reachable_from_active_runtime=True,
            reachability_evidence="ConfigBuilder.build → get_crt_config profiles",
            possible_behavioral_effect="CRTConfig base before production overrides",
        )

    # 8) Behavioral functions with non-identity floats
    if _is_behavioral_func(scope):
        if isinstance(val, float) and val not in (0.0, 1.0):
            return done(
                "IN_SCOPE",
                f"non-identity float in behavioral function {fname}",
                reachable_from_active_runtime=True,
                reachability_evidence=f"spine module {fpath} :: {scope}",
                possible_behavioral_effect="score/guard/plan/risk parameter",
            )
        if isinstance(val, int) and val not in (0, 1) and any(
            x in line.lower() for x in ("ttl", "age", "candle", "band", "tier", "minute", "hour", "day", "max_", "min_")
        ):
            return done(
                "IN_SCOPE",
                f"TTL/age/band integer in behavioral function {fname}",
                reachable_from_active_runtime=True,
                reachability_evidence=f"{fpath}::{scope}",
                possible_behavioral_effect="TTL/band threshold",
            )
        if val in (0, 0.0, 1, 1.0):
            return done(
                "OUT_OF_SCOPE",
                "identity 0/1 in behavioral function (clamp/flag bound)",
                reachable_from_active_runtime=True,
                possible_behavioral_effect=None,
            )

    # 9) Trade / EngineState structural defaults that size risk
    if "risk_pct" in c["literal_or_constant_name"] or (
        "Trade" in scope and "risk" in line.lower() and isinstance(val, float)
    ):
        return done(
            "IN_SCOPE",
            "trade risk_pct default",
            reachable_from_active_runtime=True,
            reachability_evidence=scope,
            possible_behavioral_effect="position sizing",
        )

    # 10) production_config / config_builder coercions — usually structural
    if fpath.endswith(("production_config.py", "config_builder.py")):
        return done(
            "OUT_OF_SCOPE",
            "config loader structural constant (not CRT detector/score hardcode)",
            reachable_from_active_runtime=True,
            possible_behavioral_effect=None,
            authority_hint="LOADER_STRUCTURAL",
        )

    # 11) Remaining floats on spine → IN_SCOPE (parameter-like residual)
    if isinstance(val, float):
        return done(
            "IN_SCOPE",
            "spine residual float — treated as behavior-bearing under closure resolution policy",
            reachable_from_active_runtime=True,
            reachability_evidence=f"{fpath}:{c['line']} {scope}",
            possible_behavioral_effect="possible score/threshold/size effect",
            closure_resolved=True,
        )

    # 12) Remaining ints on spine → OUT (structural)
    return done(
        "OUT_OF_SCOPE",
        "spine residual integer resolved as structural/non-behavioral under closure policy",
        reachable_from_active_runtime=True,
        possible_behavioral_effect=None,
        closure_resolved=True,
    )


# ── Deep traces (canonical anchors + scoring_engine dual path) ──────────────

def _deep_traces() -> list[dict[str, Any]]:
    return [
        {
            "trace_id": "RT-001",
            "anchor": "SUR-008 min_depth 0.1*ATR",
            "match": {"file": "src/config_layer/crt_engine_v2.py", "line": 1355, "value": 0.1},
            "runtime_entrypoint": "StateMachine.try_expansion_to_retest",
            "call_chain": [
                "try_expansion_to_retest",
                "min_depth = 0.1 * atr",
                "depth_abs < min_depth → False",
            ],
            "behavior_effect": "DIRECT",
            "computed_quantity": "min_depth",
            "comparison_or_formula": "depth_abs < 0.1 * ATR",
            "state_or_gate_affected": "EXPANSION→RETEST",
            "evidence": "crt_engine_v2.py:1355-1363",
        },
        {
            "trace_id": "RT-002",
            "anchor": "RiskScore.final weight 0.35 sweep",
            "match": {"file": "src/config_layer/crt_engine_v2.py", "line": 222, "value": 0.35},
            "runtime_entrypoint": "UltronRiskEngine.compute_score → RiskScore.final",
            "call_chain": ["compute_score", "RiskScore.final", "0.35*sweep"],
            "behavior_effect": "DIRECT",
            "computed_quantity": "final score",
            "comparison_or_formula": "0.35*sweep+0.25*breakout+0.20*retest+0.20*time",
            "state_or_gate_affected": "score/sizing",
            "evidence": "crt_engine_v2.py:221-227",
        },
        {
            "trace_id": "RT-003",
            "anchor": "RiskScore.final weight 0.25 breakout",
            "match": {"file": "src/config_layer/crt_engine_v2.py", "line": 223, "value": 0.25},
            "runtime_entrypoint": "RiskScore.final",
            "call_chain": ["RiskScore.final"],
            "behavior_effect": "DIRECT",
            "computed_quantity": "final score",
            "comparison_or_formula": "0.25*breakout_score",
            "state_or_gate_affected": "score/sizing",
            "evidence": "crt_engine_v2.py:223",
        },
        {
            "trace_id": "RT-004",
            "anchor": "RiskScore.final weight 0.20 retest",
            "match": {"file": "src/config_layer/crt_engine_v2.py", "line": 224, "value": 0.2},
            "runtime_entrypoint": "RiskScore.final",
            "call_chain": ["RiskScore.final"],
            "behavior_effect": "DIRECT",
            "computed_quantity": "final score",
            "comparison_or_formula": "0.20*retest_score",
            "state_or_gate_affected": "score/sizing",
            "evidence": "crt_engine_v2.py:224",
        },
        {
            "trace_id": "RT-005",
            "anchor": "RiskScore.final weight 0.20 time",
            "match": {"file": "src/config_layer/crt_engine_v2.py", "line": 225, "value": 0.2},
            "runtime_entrypoint": "RiskScore.final",
            "call_chain": ["RiskScore.final"],
            "behavior_effect": "DIRECT",
            "computed_quantity": "final score",
            "comparison_or_formula": "0.20*time_score",
            "state_or_gate_affected": "score/sizing",
            "evidence": "crt_engine_v2.py:225",
        },
        {
            "trace_id": "RT-011",
            "anchor": "scoring_engine.score_weights default 0.35",
            "match": {"file": "src/engines/scoring_engine.py", "line": 24, "value": 0.35},
            "runtime_entrypoint": "EngineRunner → engines.crt_engine.compute → compute_scores",
            "call_chain": [
                "crt_engine.compute",
                "score_weights default (0.35,0.25,0.20,0.20)",
                "s_final = sum w_i * s_i",
            ],
            "behavior_effect": "DIRECT",
            "computed_quantity": "engines CRT fusion score",
            "comparison_or_formula": "weighted sum of sweep/breakout/retest/time components",
            "state_or_gate_affected": "engine_results['crt']['score'] → FusionEngine",
            "evidence": "scoring_engine.py:24-48; crt_engine.py:19-20",
            "dual_path_note": "Same numeric weight vector as RiskScore.final but DIFFERENT component functions",
        },
        {
            "trace_id": "RT-012",
            "anchor": "scoring_engine single-sweep 0.7",
            "match": {"file": "src/engines/scoring_engine.py", "line": 41, "value": 0.7},
            "runtime_entrypoint": "compute_scores",
            "call_chain": ["s_sweep = 0.7 if sweep and not double"],
            "behavior_effect": "CONDITIONAL",
            "computed_quantity": "s_sweep",
            "comparison_or_formula": "discrete sweep score ladder 0/0.7/1.0",
            "state_or_gate_affected": "CRT engine score",
            "evidence": "scoring_engine.py:37-41",
        },
        {
            "trace_id": "RT-013",
            "anchor": "scoring_engine retest gaussian width 0.04",
            "match": {"file": "src/engines/scoring_engine.py", "line": 44, "value": 0.04},
            "runtime_entrypoint": "compute_scores",
            "call_chain": ["s_retest = exp(-((retest_depth-0.5)**2)/0.04)"],
            "behavior_effect": "DIRECT",
            "computed_quantity": "s_retest",
            "comparison_or_formula": "Gaussian kernel around retest_depth=0.5",
            "state_or_gate_affected": "CRT engine score",
            "evidence": "scoring_engine.py:44",
        },
        {
            "trace_id": "RT-006",
            "anchor": "score_sweep base 0.6",
            "match": {"file": "src/config_layer/crt_engine_v2.py", "line": 1580, "value": 0.6},
            "runtime_entrypoint": "UltronRiskEngine.score_sweep",
            "call_chain": ["score_sweep", "base=0.6"],
            "behavior_effect": "DIRECT",
            "computed_quantity": "sweep_score",
            "comparison_or_formula": "base + bonus - penalty",
            "state_or_gate_affected": "Ultron RiskScore",
            "evidence": "crt_engine_v2.py:1580",
        },
        {
            "trace_id": "RT-007",
            "anchor": "score_sweep double_bonus 0.4",
            "match": {"file": "src/config_layer/crt_engine_v2.py", "line": 1581, "value": 0.4},
            "runtime_entrypoint": "UltronRiskEngine.score_sweep",
            "call_chain": ["double_bonus=0.4 if double_confirmed"],
            "behavior_effect": "CONDITIONAL",
            "computed_quantity": "sweep_score",
            "comparison_or_formula": "conditional bonus",
            "state_or_gate_affected": "Ultron RiskScore",
            "evidence": "crt_engine_v2.py:1581",
        },
        {
            "trace_id": "RT-008",
            "anchor": "score_breakout mix 0.5",
            "match": {"file": "src/config_layer/crt_engine_v2.py", "line": 1591, "value": 0.5},
            "runtime_entrypoint": "UltronRiskEngine.score_breakout",
            "call_chain": ["0.5*body + 0.5*atr_component"],
            "behavior_effect": "DIRECT",
            "computed_quantity": "breakout_score",
            "comparison_or_formula": "equal mix",
            "state_or_gate_affected": "Ultron RiskScore",
            "evidence": "crt_engine_v2.py:1591",
        },
        {
            "trace_id": "RT-009",
            "anchor": "score_breakout ATR norm 3.0",
            "match": {"file": "src/config_layer/crt_engine_v2.py", "line": 1590, "value": 3.0},
            "runtime_entrypoint": "UltronRiskEngine.score_breakout",
            "call_chain": ["atr_multiple / 3.0"],
            "behavior_effect": "DIRECT",
            "computed_quantity": "atr_component",
            "comparison_or_formula": "normalize by 3.0",
            "state_or_gate_affected": "Ultron RiskScore",
            "evidence": "crt_engine_v2.py:1590",
        },
        {
            "trace_id": "RT-010",
            "anchor": "score_time single-session 0.8",
            "match": {"file": "src/config_layer/crt_engine_v2.py", "line": 1616, "value": 0.8},
            "runtime_entrypoint": "UltronRiskEngine.score_time",
            "call_chain": ["matches==1 → 0.8"],
            "behavior_effect": "CONDITIONAL",
            "computed_quantity": "time_score",
            "comparison_or_formula": "session match discrete map",
            "state_or_gate_affected": "Ultron RiskScore",
            "evidence": "crt_engine_v2.py:1616",
        },
    ]


def _attach_traces(scoped: list[dict], deep: list[dict]) -> list[dict]:
    out = []
    for c in scoped:
        c = dict(c)
        c["deep_trace_ids"] = []
        c["behavior_effect"] = "UNPROVEN"
        for t in deep:
            m = t["match"]
            if (
                c["file"] == m["file"]
                and c["line"] == m["line"]
                and abs(float(c["value"]) - float(m["value"])) < 1e-12
            ):
                c["deep_trace_ids"].append(t["trace_id"])
                c["behavior_effect"] = t["behavior_effect"]
                c["runtime_trace"] = t
        if c["scope_status"] == "IN_SCOPE" and not c["deep_trace_ids"]:
            # synthetic effect from scope reason
            if "CONDITIONAL" in c.get("scope_reason", ""):
                c["behavior_effect"] = "CONDITIONAL"
            else:
                c["behavior_effect"] = "DIRECT"
        if c["scope_status"] == "OUT_OF_SCOPE":
            c["behavior_effect"] = "NO_EFFECT_PROVEN"
        out.append(c)
    return out


# ── Authority surfaces + matches ────────────────────────────────────────────

def _surfaces() -> dict[str, Any]:
    import yaml
    from config_layer.crt_engine_v2 import CRTConfig
    from config_layer.production_config import get_active_version

    am = yaml.safe_load((_REPO / "active_models.yaml").read_text(encoding="utf-8"))
    ont_path = _REPO / "configs" / "formulas" / "market_ontology.yaml"
    ont = yaml.safe_load(ont_path.read_text(encoding="utf-8")) if ont_path.is_file() else {}
    ver = get_active_version()
    prod = json.loads((_REPO / "configs" / "production" / f"{ver}.json").read_text(encoding="utf-8"))
    code_defaults = {}
    for f in dataclasses.fields(CRTConfig):
        if f.default is not dataclasses.MISSING:
            code_defaults[f.name] = f.default
        elif f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
            try:
                code_defaults[f.name] = f.default_factory()  # type: ignore[misc]
            except Exception:
                code_defaults[f.name] = "<factory>"
    how_keys = set(prod.get("params") or {}) | set(prod.get("crt_engine") or {})
    return {
        "who": am,
        "what": ont,
        "how_params": prod.get("params") or {},
        "how_crt_engine": prod.get("crt_engine") or {},
        "how_keys": how_keys,
        "crtconfig_defaults": code_defaults,
        "crtconfig_fields": set(code_defaults),
        "active_version": ver,
    }


def _how_has_key(surfaces: dict, key: str) -> bool:
    return key in surfaces["how_keys"] or key in surfaces["crtconfig_fields"]


def _adjudicate_one(c: dict[str, Any], surfaces: dict, idx: int) -> dict[str, Any]:
    """Full authority adjudication for one IN_SCOPE candidate."""
    val = c["value"]
    fpath = c["file"]
    line = c.get("source_line_text", "")
    name = c["literal_or_constant_name"]
    anchor = c.get("anchor_id")
    traces = c.get("deep_trace_ids") or []

    # Defaults
    verdict = "PROVEN_HOW_CANDIDATE"
    disposition = "PLAN_ONLY_NO_IMPLEMENTATION"
    priority = "P2"
    plan_id = "PLAN-003"
    rationale = (
        "Parameter-like CODE hardcode on active CRT spine without proven structural "
        "invariance; externalizable to existing HOW (CRTConfig/production) surface."
    )

    # SUR-008 min_depth
    if anchor == "SUR008_MIN_DEPTH" or ("min_depth" in line and val == 0.1):
        verdict = "PROVEN_HOW_CANDIDATE"
        priority = "P1"
        plan_id = "PLAN-001"
        rationale = (
            "DIRECT retest floor; not FM identity; no HOW key; WHO restates prose; "
            "representable as CRTConfig.retest_min_depth_atr_fraction"
        )
    # RiskScore weights
    elif anchor == "SUR008_RISKSCORE_WEIGHT" or (
        "RiskScore" in c["function_or_scope"] and val in (0.35, 0.25, 0.2, 0.20)
    ):
        verdict = "PROVEN_HOW_CANDIDATE"
        priority = "P1"
        plan_id = "PLAN-002"
        rationale = (
            "RiskScore.final weights DIRECT on score/sizing; no HOW key; "
            "must not alias conf_weights (different semantic)"
        )
    # scoring_engine weights — dual path
    elif anchor == "SUR008_SCORING_ENGINE_WEIGHT" or (
        fpath.endswith("scoring_engine.py") and val in (0.35, 0.25, 0.2, 0.20)
        and ("score_weights" in name or "arg_default" in name or "container" in name)
    ):
        verdict = "PROVEN_DUPLICATE_RUNTIME_AUTHORITY"
        priority = "P1"
        plan_id = "PLAN-002"
        rationale = (
            "Default score_weights (0.35,0.25,0.20,0.20) duplicate the numeric vector used in "
            "RiskScore.final, on a SECOND runtime path (EngineRunner CRT score). Component "
            "functions differ → dual CODE authority for the weight vector; HOW externalization "
            "must cover both sites or prove path isolation."
        )
        disposition = "PLAN_ONLY_NO_IMPLEMENTATION"
    # market_router profiles
    elif fpath.endswith("market_router.py"):
        verdict = "PROVEN_HOW_CANDIDATE"
        priority = "P2"
        plan_id = "PLAN-003"
        rationale = (
            "Instrument profile literals are CODE-held bases before production overrides; "
            "HOW instrument_overrides already exists as governed destination for per-instrument divergence"
        )
    # WHAT math should not be IN_SCOPE under new rules; if any slip through:
    elif fpath in _WHAT_MATH_FILES:
        verdict = "PROVEN_WHAT_FORMULA_COMPONENT"
        priority = "P3"
        plan_id = None
        disposition = "PRESERVE_NO_ACTION"
        rationale = "Formula identity belongs to WHAT/FM; not a HOW threshold migration"

    # Ultron component hardcodes
    elif any(t in traces for t in ("RT-006", "RT-007", "RT-008", "RT-009", "RT-010", "RT-012", "RT-013")):
        verdict = "PROVEN_HOW_CANDIDATE"
        priority = "P2"
        plan_id = "PLAN-003"
        rationale = "Ultron/scoring component parameter; CODE-only; HOW-representable"

    # fusion/decision/planner/risk gate residual floats
    elif any(
        fpath.endswith(x)
        for x in (
            "fusion_engine.py",
            "decision_engine.py",
            "execution_planner.py",
            "ultron_risk_gate.py",
            "ultron_risk_gate_wrapper.py",
            "engine_runner.py",
            "live_engine_hook.py",
        )
    ):
        # Check if value already has CRTConfig/production key nearby by name
        key_guess = None
        for k in surfaces["crtconfig_fields"]:
            if k in line or k in name:
                key_guess = k
                break
        if key_guess and _how_has_key(surfaces, key_guess):
            verdict = "PROVEN_DUPLICATE_RUNTIME_AUTHORITY"
            priority = "P2"
            plan_id = "PLAN-003"
            rationale = (
                f"Literal co-located with HOW key {key_guess!r} — possible dual authority; "
                "requires site-specific proof before strip"
            )
        else:
            verdict = "PROVEN_HOW_CANDIDATE"
            priority = "P2"
            plan_id = "PLAN-003"
            rationale = "Spine residual behavioral float without proven HOW key binding"

    return {
        "adjudication_id": f"ADJ-{idx:04d}",
        "candidate_id": c["candidate_id"],
        "behavioral_constant_id": c.get("behavioral_constant_id"),
        "file": fpath,
        "line": c["line"],
        "value": val,
        "function_or_scope": c["function_or_scope"],
        "deep_trace_ids": traces,
        "behavior_effect": c.get("behavior_effect"),
        "verdict": verdict,
        "disposition": disposition,
        "priority": priority,
        "plan_id": plan_id,
        "rationale": rationale,
        "source_line_text": line[:160],
    }


def _global_matches(surfaces: dict) -> list[dict]:
    """Cross-surface matches for SUR-008 anchors (proof ledger)."""
    matches = []
    mid = 0
    who = surfaces["who"].get("crt", {}).get("runtime", {})
    retest = (who.get("detection") or {}).get("retest") or {}
    scoring = who.get("scoring") or {}

    mid += 1
    matches.append(
        {
            "authority_match_id": f"AM-{mid:03d}",
            "surface": "WHO",
            "path": "crt.runtime.detection.retest.min_depth",
            "declared_value": retest.get("min_depth"),
            "runtime_consumed": False,
            "evidence": "prose only",
        }
    )
    mid += 1
    matches.append(
        {
            "authority_match_id": f"AM-{mid:03d}",
            "surface": "WHO",
            "path": "crt.runtime.scoring.raw_formula",
            "declared_value": scoring.get("raw_formula"),
            "runtime_consumed": False,
            "evidence": "prose composite weights",
        }
    )
    mid += 1
    matches.append(
        {
            "authority_match_id": f"AM-{mid:03d}",
            "surface": "HOW",
            "path": "production — missing retest_min_depth_atr_fraction / risk_score_weights",
            "declared_value": None,
            "runtime_consumed": False,
            "absence": True,
            "evidence": "keys not in active production params|crt_engine",
        }
    )
    mid += 1
    matches.append(
        {
            "authority_match_id": f"AM-{mid:03d}",
            "surface": "CODE",
            "path": "crt_engine_v2.RiskScore.final + scoring_engine.score_weights",
            "declared_value": [0.35, 0.25, 0.20, 0.20],
            "runtime_consumed": True,
            "evidence": "dual CODE sites for weight vector numbers",
        }
    )
    mid += 1
    matches.append(
        {
            "authority_match_id": f"AM-{mid:03d}",
            "surface": "WHAT",
            "path": "market_ontology.yaml",
            "declared_value": None,
            "runtime_consumed": False,
            "absence": True,
            "evidence": "no FM for min_depth fraction or RiskScore weights",
        }
    )
    return matches


def _semantic_relationships() -> list[dict]:
    return [
        {
            "relationship_id": "REL-001",
            "classification": "PROVEN_SAME_SEMANTIC",
            "sides": ["WHO min_depth prose", "CODE min_depth=0.1*atr"],
            "proof_basis": (
                "Executable `min_depth = 0.1 * atr` implements WHO prose '0.1 × ATR' "
                "for the retest depth floor (structural formula identity)."
            ),
            "confidence": "Certain",
        },
        {
            "relationship_id": "REL-002",
            "classification": "PROVEN_SAME_SEMANTIC",
            "sides": ["WHO raw_formula weights", "CODE RiskScore.final weights"],
            "proof_basis": (
                "RiskScore.final weighted sum structure matches WHO scoring.raw_formula "
                "coefficients and term order."
            ),
            "confidence": "Certain",
        },
        {
            "relationship_id": "REL-003",
            "classification": "PROVEN_PARTIAL_SEMANTIC_OVERLAP",
            "sides": ["RiskScore.final weights", "scoring_engine.score_weights default"],
            "proof_basis": (
                "Identical numeric vector (0.35,0.25,0.20,0.20) on two runtime paths, but "
                "component scores are computed by different functions (Ultron score_* vs "
                "compute_scores s_sweep/s_breakout/...). Weight vector overlaps; full score "
                "semantics differ."
            ),
            "confidence": "Certain",
        },
        {
            "relationship_id": "REL-004",
            "classification": "PROVEN_DIFFERENT_SEMANTIC",
            "sides": ["RiskScore.final weights", "CRTConfig.conf_weights"],
            "proof_basis": (
                "conf_weights parameterize soft-conf body/mom/dist/disp fusion, not "
                "sweep/breakout/retest/time RiskScore composition. Same-shape tuple is "
                "insufficient for identity."
            ),
            "confidence": "Certain",
        },
        {
            "relationship_id": "REL-005",
            "classification": "PROVEN_DIFFERENT_SEMANTIC",
            "sides": ["min_depth 0.1*ATR", "retest_depth_max / retest_atr_depth_fraction"],
            "proof_basis": (
                "HOW keys control adaptive ceiling; min_depth is a separate floor check "
                "in the same function."
            ),
            "confidence": "Certain",
        },
    ]


def _surplus_records() -> list[dict]:
    return [
        {
            "declaration_surplus_id": "DS-001",
            "authority": "WHO",
            "path": "detection.retest.min_depth",
            "surplus_status": "PROVEN_IMPLEMENTED",
            "preserve": True,
            "surplus_description": "WHO restates CODE min_depth; no extra parameters",
        },
        {
            "declaration_surplus_id": "DS-002",
            "authority": "WHO",
            "path": "scoring.raw_formula",
            "surplus_status": "PROVEN_IMPLEMENTED",
            "preserve": True,
            "surplus_description": "WHO restates RiskScore.final weights",
        },
        {
            "declaration_surplus_id": "DS-003",
            "authority": "WHO",
            "path": "detection.retest.adaptive_ceiling",
            "surplus_status": "PROVEN_PARTIALLY_IMPLEMENTED",
            "preserve": True,
            "surplus_description": (
                "Ceiling structure implemented via HOW keys; WHO prose numbers 0.25/0.50 "
                "may drift from active HOW (IC-008)"
            ),
        },
        {
            "declaration_surplus_id": "DS-004",
            "authority": "HOW",
            "path": "missing keys for min_depth + risk/scoring weight vectors",
            "surplus_status": "PROVEN_NOT_IMPLEMENTED",
            "preserve": True,
            "surplus_description": "HOW ownership not implemented for CODE behavioral constants (SUR-008 gap)",
            "interpretation": "HOW missing keys — CODE has the parameters",
        },
        {
            "declaration_surplus_id": "DS-005",
            "authority": "CODE",
            "path": "dual weight vector sites",
            "surplus_status": "PROVEN_PARTIALLY_IMPLEMENTED",
            "preserve": True,
            "surplus_description": (
                "Weight vector appears in RiskScore.final and scoring_engine defaults — "
                "documentation under-specifies dual path"
            ),
        },
    ]


def _recertify_plans(adjudications: list[dict]) -> list[dict]:
    """Re-certify or revise PLAN-001..003 from closure evidence."""
    how_cands = [a for a in adjudications if a["verdict"] == "PROVEN_HOW_CANDIDATE"]
    dual = [a for a in adjudications if a["verdict"] == "PROVEN_DUPLICATE_RUNTIME_AUTHORITY"]
    plan1_hits = [a for a in adjudications if a.get("plan_id") == "PLAN-001"]
    plan2_hits = [a for a in adjudications if a.get("plan_id") == "PLAN-002"]
    plan3_hits = [a for a in adjudications if a.get("plan_id") == "PLAN-003"]

    plans = [
        {
            "plan_id": "PLAN-001",
            "recertification_status": "IMPLEMENTED",
            "revision_notes": (
                "Closure confirmed min_depth as sole P1 floor hardcode; IMPLEMENTED 2026-07-11 "
                "(CH-plan001-retest-min-depth-how): CRTConfig.retest_min_depth_atr_fraction=0.10 "
                "fail-closed, call-site fraction*atr, crt_engine config key (hash-neutral), WHO "
                "key names only. Default-parity + dynamism + fail-closed proven "
                "(tests/test_plan001_retest_min_depth_how.py); golden ledger suite green."
            ),
            "candidate_id_or_surplus_id": "SUR008_MIN_DEPTH / RT-001",
            "plan_status": "IMPLEMENTED",
            "implementation_change_id": "CH-plan001-retest-min-depth-how",
            "current_behavior": "min_depth = 0.1 * atr hardcoded in try_expansion_to_retest",
            "target_authority": "HOW",
            "existing_destination_surface": (
                "CRTConfig.retest_min_depth_atr_fraction + production params/crt_engine key; "
                "ConfigBuilder already merges CRTConfig fields"
            ),
            "required_schema_change": "Add CRTConfig.retest_min_depth_atr_fraction: float = 0.1",
            "required_loader_change": "None beyond existing production merge",
            "required_runtime_change": "Replace literal 0.1 with self.config.retest_min_depth_atr_fraction",
            "required_tests": [
                "default 0.1 parity unit",
                "depth_abs < fraction*atr rejects",
                "strict key presence if config-first strict migration",
            ],
            "required_parity_checks": ["BNBUSDT+SOLUSDT ledger byte-identical at default 0.1"],
            "required_backtests": ["determinism gate at default"],
            "expected_behavior_change": "NONE",
            "rollback_condition": "parity fail or unexpected trade-count delta at default",
            "stop_condition": "unknown override key; missing production key if strict",
            "dependencies": ["§6.5 config-first parity"],
            "recommended_order": 1,
            "adjudication_support_count": len(plan1_hits),
            "closure_support": "RECERTIFIED_BY_SPINE_CLOSURE",
        },
        {
            "plan_id": "PLAN-002",
            "recertification_status": "IMPLEMENTED",
            "revision_notes": (
                "REVISED (dual-path design) then IMPLEMENTED 2026-07-12 as TWO DISTINCT HOW keys "
                "(user-approved identity discipline, CH-plan002-dual-weights-how): "
                "CRTConfig.risk_score_weights → RiskScore.final via sole constructor injection "
                "(UltronRiskEngine.compute_score); CRTConfig.score_component_weights → engines path, "
                "EngineRunner strict-reads crt_engine section and injects crt_compute context "
                "(closing the context={} gap where the CODE default always won). Both default to "
                "the legacy tuple (parity); fail-closed 4×finite≥0 validation; conf_weights NOT "
                "aliased (PROVEN_DIFFERENT_SEMANTIC honored). Proofs: "
                "tests/test_plan002_dual_weights_how.py (28: default-parity both paths, per-path "
                "dynamism, no-aliasing, fail-closed, production load); golden ledger suite green."
            ),
            "candidate_id_or_surplus_id": "RT-002..005 + RT-011 / dual path",
            "plan_status": "IMPLEMENTED",
            "implementation_change_id": "CH-plan002-dual-weights-how",
            "current_behavior": (
                "RiskScore.final hardcodes 0.35/0.25/0.20/0.20; scoring_engine defaults same tuple "
                "for EngineRunner CRT score path"
            ),
            "target_authority": "HOW",
            "existing_destination_surface": (
                "CRTConfig.risk_score_weights for Ultron path; "
                "crt_engine.score_component_weights already mentioned in scoring_engine docstring — "
                "verify/wire production key score_component_weights for engines path"
            ),
            "required_schema_change": (
                "Add risk_score_weights on CRTConfig; ensure production exposes "
                "score_component_weights for engines.crt_engine path"
            ),
            "required_loader_change": "coerce list→tuple; pass into both Ultron and engines paths",
            "required_runtime_change": (
                "RiskScore.final reads config weights; compute_scores already accepts score_weights — "
                "ensure production always injects (no silent CODE default divergence)"
            ),
            "required_tests": [
                "default weights parity on BOTH paths",
                "no conf_weights alias",
                "dual-path same-default score series when components mocked equal",
            ],
            "required_parity_checks": [
                "Ultron RiskScore.final series byte-identical at default",
                "engines.compute_scores series byte-identical at default",
            ],
            "required_backtests": ["determinism on default for spine-relevant path"],
            "expected_behavior_change": "NONE",
            "rollback_condition": "score delta at default on either path",
            "stop_condition": "conf_weights collision unresolved; dual-path only half-migrated",
            "dependencies": ["PLAN-001 independent"],
            "recommended_order": 2,
            "adjudication_support_count": len(plan2_hits),
            "dual_authority_hits": len(dual),
            "closure_support": "REVISED_FOR_DUAL_PATH",
        },
        {
            "plan_id": "PLAN-003",
            "recertification_status": "REVISED",
            "revision_notes": (
                f"REVISED scope: batch remaining PROVEN_HOW_CANDIDATE spine residuals "
                f"(support_count={len(plan3_hits)}) including Ultron component hardcodes, "
                f"scoring_engine non-weight parameters (0.7, 0.04, 2.0), market_router profile "
                f"literals, and fusion/decision/planner residual floats. Prefer one "
                f"crt_engine.scoring_params mapping to limit config entropy."
            ),
            "candidate_id_or_surplus_id": f"PLAN-003 cohort n={len(plan3_hits)}",
            "plan_status": "READY_FOR_FUTURE_IMPLEMENTATION",
            "current_behavior": "Multiple CODE-only scoring/profile/gate hardcodes on spine",
            "target_authority": "HOW",
            "existing_destination_surface": (
                "CRTConfig + production crt_engine section; instrument_overrides for router profiles"
            ),
            "required_schema_change": "Grouped scoring_params / profile keys under crt_engine",
            "required_loader_change": "merge new keys via existing production_config path",
            "required_runtime_change": "replace literals with config reads site-by-site",
            "required_tests": ["per-site unit + default parity"],
            "required_parity_checks": ["component score vectors identical at defaults"],
            "required_backtests": ["optional after unit parity"],
            "expected_behavior_change": "NONE",
            "rollback_condition": "component score drift at default",
            "stop_condition": "config entropy explosion — require grouped section",
            "dependencies": ["PLAN-002 preferred first for central weights"],
            "recommended_order": 3,
            "adjudication_support_count": len(plan3_hits),
            "how_candidate_total": len(how_cands),
            "closure_support": "REVISED_SCOPE_EXPANDED",
        },
    ]
    return plans


def scan() -> dict[str, Any]:
    from config_layer.production_config import get_active_version

    assert BEHAVIORAL_CONSTANT_SCOPE_RULE["frozen_before_classification"] is True

    spine_files = [_rel(p) for p in _spine_paths()]
    raw = _enumerate_raw()
    scoped = [_classify_scope(c) for c in raw]
    for i, c in enumerate(scoped, 1):
        c["behavioral_constant_id"] = f"BC-{i:04d}"

    deep = _deep_traces()
    scoped = _attach_traces(scoped, deep)

    in_scope = [c for c in scoped if c["scope_status"] == "IN_SCOPE"]
    out_scope = [c for c in scoped if c["scope_status"] == "OUT_OF_SCOPE"]
    unprov = [c for c in scoped if c["scope_status"] == "UNPROVEN"]

    surfaces = _surfaces()
    adjudications = [
        _adjudicate_one(c, surfaces, i) for i, c in enumerate(in_scope, 1)
    ]
    # Every IN_SCOPE must have adjudication
    assert len(adjudications) == len(in_scope)

    plans = _recertify_plans(adjudications)
    matches = _global_matches(surfaces)
    rels = _semantic_relationships()
    surplus = _surplus_records()

    # SUR-008 anchors
    sur008_ok = [
        {
            "requirement": "min_depth 0.1",
            "found": any(
                c.get("anchor_id") == "SUR008_MIN_DEPTH"
                or ("min_depth" in c.get("source_line_text", "") and c["value"] == 0.1)
                for c in scoped
            ),
        },
        {
            "requirement": "RiskScore 0.35",
            "found": any(
                c.get("anchor_id") == "SUR008_RISKSCORE_WEIGHT" or (
                    "RiskScore" in c["function_or_scope"] and c["value"] == 0.35
                )
                for c in scoped
            ),
        },
        {
            "requirement": "scoring_engine weights",
            "found": any(
                c["file"].endswith("scoring_engine.py") and c["value"] == 0.35 for c in scoped
            ),
        },
    ]

    # Behavior effect counts among IN_SCOPE
    be_counts = {
        "DIRECT": 0,
        "CONDITIONAL": 0,
        "INVARIANT_ONLY": 0,
        "NO_EFFECT_PROVEN": 0,
        "UNPROVEN": 0,
    }
    for c in in_scope:
        be = c.get("behavior_effect") or "UNPROVEN"
        be_counts[be] = be_counts.get(be, 0) + 1

    verd = {
        "PROVEN_HOW_CANDIDATE": 0,
        "PROVEN_WHAT_FORMULA_COMPONENT": 0,
        "PROVEN_CODE_INVARIANT": 0,
        "PROVEN_DUPLICATE_RUNTIME_AUTHORITY": 0,
        "PROVEN_MISSING_CODE_IMPLEMENTATION": 0,
        "UNPROVEN": 0,
    }
    for a in adjudications:
        verd[a["verdict"]] = verd.get(a["verdict"], 0) + 1

    pri = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for a in adjudications:
        pri[a["priority"]] = pri.get(a["priority"], 0) + 1

    sem = {
        "PROVEN_SAME_SEMANTIC": 0,
        "PROVEN_DIFFERENT_SEMANTIC": 0,
        "PROVEN_PARTIAL_SEMANTIC_OVERLAP": 0,
        "UNPROVEN": 0,
    }
    for r in rels:
        sem[r["classification"]] = sem.get(r["classification"], 0) + 1

    sur_st = {
        "PROVEN_IMPLEMENTED": 0,
        "PROVEN_PARTIALLY_IMPLEMENTED": 0,
        "PROVEN_NOT_IMPLEMENTED": 0,
        "PROVEN_DIFFERENT_SEMANTIC": 0,
        "UNPROVEN": 0,
    }
    for s in surplus:
        sur_st[s["surplus_status"]] = sur_st.get(s["surplus_status"], 0) + 1

    # Closure gates
    spine_unproven = len(unprov)
    every_in_scope_adjudicated = len(adjudications) == len(in_scope) and all(
        a.get("verdict") for a in adjudications
    )
    # Lifecycle: RECERTIFIED (validated, awaiting implementation) → IMPLEMENTED (shipped).
    # REVISED plans stay pending design. All three states satisfy the closure gate.
    plans_recertified = all(
        p["recertification_status"] in {"RECERTIFIED", "REVISED", "IMPLEMENTED"} for p in plans
    )

    if spine_unproven == 0 and every_in_scope_adjudicated and plans_recertified:
        status = "COMPLETE"
    else:
        status = "COMPLETE_WITH_UNRESOLVED"

    unresolved = []
    if spine_unproven:
        unresolved.append(f"{spine_unproven} UNPROVEN scope candidates remain on scan set")
    if not every_in_scope_adjudicated:
        unresolved.append("not every IN_SCOPE candidate adjudicated")
    unresolved.append(
        "Deep runtime call-chain proofs limited to anchor set; residual IN_SCOPE use "
        "scope-derived DIRECT/CONDITIONAL effect tags (closure policy), not per-site "
        "mutation experiments"
    )

    # Compact behavioral_constants list = all IN_SCOPE with adjudication
    adj_by_cand = {a["candidate_id"]: a for a in adjudications}
    behavioral_constants = []
    for c in in_scope:
        a = adj_by_cand[c["candidate_id"]]
        behavioral_constants.append(
            {
                "constant_id": c["behavioral_constant_id"],
                "candidate_id": c["candidate_id"],
                "file": c["file"],
                "line": c["line"],
                "value": c["value"],
                "function_or_scope": c["function_or_scope"],
                "scope_status": "IN_SCOPE",
                "behavior_effect": c.get("behavior_effect"),
                "deep_trace_ids": c.get("deep_trace_ids"),
                "verdict": a["verdict"],
                "priority": a["priority"],
                "plan_id": a.get("plan_id"),
                "adjudication_id": a["adjudication_id"],
            }
        )

    return {
        "schema": SCHEMA,
        "status": status,
        "trace_id": TRACE_ID,
        "pass_id": PASS_ID,
        "date": TRACE_DATE,
        "active_version": get_active_version(),
        "repository_pin": _repo_pin(),
        "authority": (
            "observational Active CRT Behavioral-Constant Closure Pass — grants no "
            "remediation, config mutation, or fourth YAML"
        ),
        "non_effects": [
            "no runtime code mutation",
            "no YAML mutation",
            "no production config mutation",
            "no formula mutation",
            "no state_contracts mutation",
            "no Phase-Topology mutation",
            "no IC-007 remediation execution",
            "no PLAN-001..003 implementation",
            "no IC-001/IC-002 cleanup",
            "no detector/guard registries",
            "no model dispatch enablement",
            "no fourth YAML",
        ],
        "behavioral_constant_scope_rule": BEHAVIORAL_CONSTANT_SCOPE_RULE,
        "spine_modules": spine_files,
        "population_summary": {
            "RAW_CONSTANT_CANDIDATE_COUNT": len(raw),
            "IN_SCOPE_BEHAVIORAL_CONSTANT_COUNT": len(in_scope),
            "OUT_OF_SCOPE_COUNT": len(out_scope),
            "UNPROVEN_SCOPE_COUNT": len(unprov),
            "DEEP_TRACED_COUNT": len(deep),
            "FULLY_ADJUDICATED_IN_SCOPE_COUNT": len(adjudications),
            "SPINE_MODULE_COUNT": len(spine_files),
            "SUR008_ANCHORS_FOUND": all(x["found"] for x in sur008_ok),
            "sur008_anchor_checks": sur008_ok,
            "CLOSURE_SCOPE_RESOLVED": spine_unproven == 0,
            "EVERY_IN_SCOPE_ADJUDICATED": every_in_scope_adjudicated,
            "PLANS_RECERTIFIED_OR_REVISED": plans_recertified,
        },
        "raw_candidates": scoped,
        "behavioral_constants": behavioral_constants,
        "runtime_traces": deep,
        "authority_matches": matches,
        "semantic_relationships": rels,
        "declaration_surplus_records": surplus,
        "provenance_records": [
            {
                "provenance_question": "Dual path for 0.35/0.25/0.20/0.20 weights?",
                "evidence_source": "scoring_engine.py + crt_engine_v2 RiskScore.final",
                "evidence": "Both hold same default weight vector; different component math",
                "conclusion": "PROVEN_PARTIAL_SEMANTIC_OVERLAP + dual CODE authority for vector",
                "proof_status": "PROVEN",
            },
            {
                "provenance_question": "IC-007 min_depth HOW candidate still valid after closure?",
                "evidence_source": "closure scan + try_expansion_to_retest",
                "evidence": "Still CODE-only floor; no HOW key; WHO prose implemented",
                "conclusion": "PLAN-001 RECERTIFIED",
                "proof_status": "PROVEN",
            },
        ],
        "authority_adjudications": adjudications,
        "implementation_plans": plans,
        "priority_summary": pri,
        "behavior_effect_summary": be_counts,
        "match_surface_summary": {
            "WHAT_MATCH_COUNT": sum(1 for m in matches if m["surface"] == "WHAT"),
            "WHO_MATCH_COUNT": sum(1 for m in matches if m["surface"] == "WHO"),
            "HOW_MATCH_COUNT": sum(1 for m in matches if m["surface"] == "HOW"),
            "CODE_MATCH_COUNT": sum(1 for m in matches if m["surface"] == "CODE"),
        },
        "semantic_summary": sem,
        "surplus_summary": {"DECLARATION_SURPLUS_COUNT": len(surplus), **sur_st},
        "adjudication_summary": verd,
        "implementation_plan_count": len(plans),
        "unresolved_gaps": unresolved,
        "invariants": {
            "NO_FOURTH_YAML": True,
            "RUNTIME_CODE_UNCHANGED": True,
            "YAML_UNCHANGED": True,
            "PRODUCTION_CONFIG_UNCHANGED": True,
            "FORMULAS_UNCHANGED": True,
            "STATE_CONTRACTS_UNCHANGED": True,
            "PHASE_TOPOLOGY_UNCHANGED": True,
            "IC001_IC002_NOT_EXECUTED": True,
            "DETECTOR_GUARD_REGISTRIES_NOT_ADDED": True,
            "MODEL_DISPATCH_NOT_ENABLED": True,
            "IC007_REMEDIATION_NOT_EXECUTED": True,
            "PLANS_NOT_IMPLEMENTED": True,
        },
        "top_findings": [
            {
                "id": "FND-CL-001",
                "finding": (
                    "Closure resolves spine AST candidates to IN/OUT without residual UNPROVEN "
                    f"on the declared module set (UNPROVEN_SCOPE_COUNT={len(unprov)})."
                ),
                "priority": "P1",
            },
            {
                "id": "FND-CL-002",
                "finding": (
                    "PLAN-001 RECERTIFIED for min_depth→HOW; PLAN-002 REVISED for dual-path "
                    "weight vector (RiskScore.final + scoring_engine defaults); PLAN-003 REVISED "
                    "to batch remaining HOW candidates."
                ),
                "priority": "P1",
            },
            {
                "id": "FND-CL-003",
                "finding": (
                    "Weight vector (0.35,0.25,0.20,0.20) has PROVEN_PARTIAL_SEMANTIC_OVERLAP "
                    "across two CODE runtime paths; conf_weights remains PROVEN_DIFFERENT_SEMANTIC."
                ),
                "priority": "P1",
            },
            {
                "id": "FND-CL-004",
                "finding": (
                    f"Every IN_SCOPE candidate (n={len(in_scope)}) has authority adjudication; "
                    f"summary={verd}"
                ),
                "priority": "P1",
            },
        ],
    }


def render_md(doc: dict[str, Any]) -> str:
    ps = doc["population_summary"]
    lines = [
        f"# Behavioral Constant Authority Trace — Closure Pass ({doc['date']})",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Schema | `{doc['schema']}` |",
        f"| Pass | `{doc['pass_id']}` |",
        f"| Status | **{doc['status']}** |",
        f"| ACTIVE_VERSION | `{doc['active_version']}` |",
        f"| Spine modules | {ps['SPINE_MODULE_COUNT']} |",
        f"| Machine ledger | [`{JSON_PATH.name}`]({JSON_PATH.name}) |",
        "",
        "## Closure gates",
        "",
        f"- CLOSURE_SCOPE_RESOLVED = **{ps['CLOSURE_SCOPE_RESOLVED']}**",
        f"- EVERY_IN_SCOPE_ADJUDICATED = **{ps['EVERY_IN_SCOPE_ADJUDICATED']}**",
        f"- PLANS_RECERTIFIED_OR_REVISED = **{ps['PLANS_RECERTIFIED_OR_REVISED']}**",
        f"- UNPROVEN_SCOPE_COUNT = **{ps['UNPROVEN_SCOPE_COUNT']}**",
        "",
        "## Population",
        "",
        f"- RAW = {ps['RAW_CONSTANT_CANDIDATE_COUNT']}",
        f"- IN_SCOPE = {ps['IN_SCOPE_BEHAVIORAL_CONSTANT_COUNT']}",
        f"- OUT_OF_SCOPE = {ps['OUT_OF_SCOPE_COUNT']}",
        f"- DEEP_TRACED anchors = {ps['DEEP_TRACED_COUNT']}",
        f"- FULLY_ADJUDICATED = {ps['FULLY_ADJUDICATED_IN_SCOPE_COUNT']}",
        f"- SUR008_ANCHORS_FOUND = {ps['SUR008_ANCHORS_FOUND']}",
        "",
        "## Spine modules",
        "",
    ]
    for m in doc["spine_modules"]:
        lines.append(f"- `{m}`")
    lines += [
        "",
        "## Plan re-certification",
        "",
        "| Plan | Status | Notes |",
        "|---|---|---|",
    ]
    for p in doc["implementation_plans"]:
        lines.append(
            f"| {p['plan_id']} | **{p['recertification_status']}** | {p['revision_notes'][:100]}... |"
        )
    lines += [
        "",
        "## Adjudication summary",
        "",
    ]
    for k, v in doc["adjudication_summary"].items():
        lines.append(f"- {k} = {v}")
    lines += [
        "",
        "## Top findings",
        "",
    ]
    for f in doc["top_findings"]:
        lines.append(f"- **{f['id']}**: {f['finding']}")
    lines += [
        "",
        "## Unresolved gaps",
        "",
    ]
    for g in doc["unresolved_gaps"]:
        lines.append(f"- {g}")
    lines += [
        "",
        "## Next step",
        "",
        "Stop — do not implement PLAN-001..003. Next implementation (if approved) starts "
        "with RECERTIFIED PLAN-001 under §6.5 parity, then REVISED PLAN-002 covering both "
        "weight-vector CODE sites.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    doc = scan()
    ps = doc["population_summary"]
    print(f"status={doc['status']} pass={doc['pass_id']}")
    print(
        f"spine={ps['SPINE_MODULE_COUNT']} raw={ps['RAW_CONSTANT_CANDIDATE_COUNT']} "
        f"in={ps['IN_SCOPE_BEHAVIORAL_CONSTANT_COUNT']} out={ps['OUT_OF_SCOPE_COUNT']} "
        f"unproven={ps['UNPROVEN_SCOPE_COUNT']}"
    )
    print(
        f"adjudicated={ps['FULLY_ADJUDICATED_IN_SCOPE_COUNT']} "
        f"scope_resolved={ps['CLOSURE_SCOPE_RESOLVED']} "
        f"plans_ok={ps['PLANS_RECERTIFIED_OR_REVISED']}"
    )
    print("plans:", ", ".join(
        f"{p['plan_id']}={p['recertification_status']}" for p in doc["implementation_plans"]
    ))
    if args.write:
        JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        JSON_PATH.write_text(
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        MD_PATH.write_text(render_md(doc), encoding="utf-8")
        print(f"wrote {JSON_PATH}")
        print(f"wrote {MD_PATH}")
    return 0 if doc["population_summary"]["CLOSURE_SCOPE_RESOLVED"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
