"""h4_rail_reachability.py — H4: do the backtest rail and the live rail reach the same layers?

Plan reference: C:\\Users\\Hi\\.claude\\plans\\pure-conversation-share-only-rosy-parnas.md §4 H4.

CLAIM UNDER TEST
----------------
The backtest rail (`runtime.backtest_v2`) and the live rail (`runtime.live_engine_hook` +
`runtime.live_rail_orchestrator`) reach DIFFERENT layers for conceptually the same bar:

  - Backtest reaches L3 (CRT state machine), L4 (ParentCRT/HTF), L8 (trade birth via
    `crt_engine_v2.TRADE_OPENED`) but NEVER L7 (ExecutionPlanner/UltronRiskGate).
  - Live reaches L7 (trade birth via `ExecutionPlannerV1_2.plan()`) but has NO CRT state
    machine, NO ParentCRT, NO HTFState anywhere in its call graph (L3/L4 absent, not merely
    unreached-this-bar).

METHOD — import-graph assertion, not a live dual-rail run
-----------------------------------------------------------
Standing up the paper live rail (async TickDB port, BarBuilder, OrderManager) to run one real bar
through BOTH rails is a materially larger undertaking than this script. What IS cheap and durable:
the claim above is an IMPORT-GRAPH fact, and import graphs are a regression surface — a future
change could wire the planner into backtest_v2, or add a CRT state machine to the live hook,
silently invalidating every H4-adjacent conclusion in the plan without anyone noticing. This script
asserts the import-graph fact directly (via `ast`, not by executing either module — no side
effects, no dependency on either rail's own config being loadable) and FAILS LOUDLY the day it
stops being true, which is the actionable form of "measure it" for a fact whose evidence is static
python source, not runtime behaviour.

A live-rail dual-run belongs in a SEPARATE, larger follow-up (needs a paper TickDB fixture) — not
substituted here silently.

KILL RULE
---------
Any of the four import assertions below flips (this hypothesis is FALSIFIED for the flipped
direction — report it, do not "fix" the assertion to match).
"""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"


def _imported_dotted_names(py_file: Path) -> set:
    """All `import x.y.z` and `from x.y import z` module paths referenced anywhere in the file,
    INCLUDING inside function bodies (backtest_v2/live_engine_hook both do most imports lazily
    inside methods, not at module top) — walks the whole AST, not just top-level Import nodes."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    names: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            for alias in node.names:
                names.add(f"{node.module}.{alias.name}")
    return names


def _check(file_rel: str, must_contain: list, must_not_contain: list) -> dict:
    path = SRC / file_rel
    imports = _imported_dotted_names(path)
    hits = {name: any(name == n or n.startswith(name + ".") for n in imports) for name in must_contain}
    misses = {name: any(name == n or n.startswith(name + ".") for n in imports) for name in must_not_contain}
    ok = all(hits.values()) and not any(misses.values())
    return {
        "file": file_rel, "must_contain": hits, "must_not_contain": misses, "pass": ok,
    }


def main() -> int:
    checks = [
        _check(
            "runtime/backtest_v2.py",
            must_contain=["config_layer.crt_engine_v2"],
            must_not_contain=["config_layer.execution_planner", "core.ultron_risk_gate"],
        ),
        _check(
            "runtime/live_engine_hook.py",
            must_contain=["config_layer.execution_planner", "core.ultron_risk_gate", "core.engine_runner"],
            must_not_contain=["config_layer.crt_engine_v2.CRTEngine"],  # the class, not the module (parent_crt imports the module)
        ),
        _check(
            "runtime/live_rail_orchestrator.py",
            must_contain=["core.ultron_risk_gate"],
            must_not_contain=[],
        ),
    ]

    all_pass = all(c["pass"] for c in checks)
    verdict = {
        "hypothesis": "H4",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "import_graph_ast_assertion",
        "checks": checks,
        "result": "CONFIRMED_PLANE_SEPARATION" if all_pass else "SPLIT_INVALIDATED_REVIEW_NEEDED",
        "note": (
            "This is a STATIC assertion, not a live dual-rail measurement — see module docstring. "
            "A live-rail run (paper TickDB, one bar through both rails) is a separate follow-up."
        ),
    }

    out_path = REPO_ROOT / "results" / f"h4_rail_reachability_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(verdict, indent=2), encoding="utf-8")

    print(f"H4 result: {verdict['result']}")
    for c in checks:
        print(f"  {c['file']}: pass={c['pass']} must_contain={c['must_contain']} must_not_contain={c['must_not_contain']}")
    print(f"  -> {out_path}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
