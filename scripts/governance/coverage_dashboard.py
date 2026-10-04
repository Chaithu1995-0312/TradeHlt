#!/usr/bin/env python3
"""coverage_dashboard.py — Repository Semantic Coverage Dashboard.

Answers: \"Is the entire codebase covered?\" with multi-dimensional metrics.

Uses the Semantic OS Object universe (disk enumeration as denominator — never
encyclopedia row count). Extends coverage_report() with Concept / Boundary /
Journey / Contract / Authority / Evidence / Dependency / Attribution / Book dims.

Usage:
    python scripts/governance/coverage_dashboard.py
    python scripts/governance/coverage_dashboard.py --universe all
    python scripts/governance/coverage_dashboard.py --json-out docs/governance/repository_coverage_dashboard.LATEST.json
    python scripts/governance/coverage_dashboard.py --md-out docs/governance/REPOSITORY_COVERAGE_DASHBOARD.md

Authority: advisory / documentation. Grants no production authority (§6.5).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT / "src", _ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from governance.semantic_objects import (  # noqa: E402
    build_objects,
    coverage_report,
)

# Contract-like signals: config keys, script registry, schema-bearing packages
_CONTRACT_PATH_HINTS = (
    "feature_schema",
    "schema_validator",
    "model_contract",
    "validation_contract",
    "execution_intent",
    "trade_identity",
    "state_contract",
    "measurement",
    "qualification",
)

# Authority signals: declared ownership / regime / MIAR-adjacent evidence
_AUTHORITY_REGIMES = {
    "DECISION",
    "TERMINAL",
    "MODEL_LINEAGE",
    "PLATFORM",
    "RESEARCH",
    "SUBSTRATE",
}


def _pct(n: int, d: int) -> float:
    return round(100.0 * n / d, 1) if d else 0.0


def _has_contract(obj: dict) -> bool:
    if obj.get("config_keys") or obj.get("config_keys_heuristic"):
        return True
    if obj.get("script_registry"):
        return True
    path = (obj.get("path") or "").lower()
    return any(h in path for h in _CONTRACT_PATH_HINTS)


def _has_authority(obj: dict) -> bool:
    surface = obj.get("owner_surface")
    if surface and surface != "UNATTRIBUTED":
        return True
    if obj.get("owner_boundary"):
        return True
    regime = obj.get("regime")
    if regime in _AUTHORITY_REGIMES:
        return True
    # encyclopedia relevance that implies intentional authority posture
    rel = obj.get("relevance") or ""
    if rel in {"LIVE", "LIVE_OPS", "LIVE_RESEARCH", "RESEARCH", "DORMANT", "ARCHIVED", "INERT_UNTIL_CONFIG"}:
        return True
    return False


def _has_evidence(obj: dict) -> bool:
    if obj.get("findings_evidence"):
        return True
    if obj.get("framework_evidence"):
        return True
    if obj.get("tests_importing"):
        return True
    if obj.get("doc_citations"):
        return True
    if obj.get("test_text_references"):
        return True
    return False


def _has_dependency_edge(obj: dict) -> bool:
    return bool(obj.get("imports") or obj.get("imported_by"))


def _behavior_coverage() -> dict[str, Any]:
    """Journey steps that resolve concept ∧ boundary (behavior explainability).

    Optional object join is reported but not required for the primary ratio —
    skeleton journeys may cite CN/BD before object globs fill in.
    """
    try:
        from governance.semantic_os import SemanticOSRegistry

        reg = SemanticOSRegistry.load()
    except Exception as exc:  # noqa: BLE001 — dashboard must not crash if YAML thin
        return {
            "metric": "Journey steps with concept ∧ boundary resolved",
            "numerator": 0,
            "denominator": 0,
            "pct": 0.0,
            "status": "RED",
            "note": f"Could not load SemanticOSRegistry: {exc}",
            "steps_total": 0,
            "steps_resolved": 0,
        }

    steps_total = 0
    steps_resolved = 0
    steps_with_objects = 0
    for jn in reg.journeys.values():
        if jn.get("status") not in (None, "ACTIVE", "PROPOSED"):
            continue
        for step in jn.get("steps") or []:
            steps_total += 1
            cn = step.get("concept")
            bd = step.get("boundary")
            cn_ok = bool(cn) and cn in reg.concepts
            bd_ok = bool(bd) and bd in reg.boundaries
            if cn_ok and bd_ok:
                steps_resolved += 1
                # object participation: any OBJ listing this journey step id
                # (filled when objects join journey_steps — measured separately if needed)
                steps_with_objects += 0  # placeholder; object join counted in object dim

    # Inventory completeness floor: a 2-step skeleton can be 100% resolved yet still incomplete.
    # Require a minimum journey depth before GREEN (signal-flow Steps 1–7 ⇒ target ≥7 steps).
    _MIN_STEPS_FOR_GREEN = 7
    ratio = (steps_resolved / steps_total) if steps_total else 0.0
    if steps_total == 0:
        status = "RED"
    elif steps_total < _MIN_STEPS_FOR_GREEN:
        status = "YELLOW" if ratio >= 0.9 else "RED"
    elif ratio >= 0.9:
        status = "GREEN"
    elif ratio >= 0.5:
        status = "YELLOW"
    else:
        status = "RED"

    return {
        "metric": "ACTIVE journey steps with concept ∧ boundary resolved",
        "numerator": steps_resolved,
        "denominator": steps_total,
        "pct": round(100.0 * ratio, 1) if steps_total else 0.0,
        "status": status,
        "note": (
            "Behavior coverage = can every declared journey step be explained by a concept "
            "and boundary? Object participation is journey_coverage on OBJs. "
            f"GREEN also requires ≥{_MIN_STEPS_FOR_GREEN} declared steps (full candle journey depth); "
            f"skeleton with {steps_total} steps stays YELLOW even if fully resolved."
        ),
        "steps_total": steps_total,
        "steps_resolved": steps_resolved,
        "min_steps_for_green": _MIN_STEPS_FOR_GREEN,
        "steps_with_object_join_placeholder": steps_with_objects,
    }


def compute_dashboard(universe: str = "code") -> dict[str, Any]:
    objects = build_objects(universe=universe)
    base = coverage_report(objects)
    total = len(objects)
    if total == 0:
        raise SystemExit("zero objects discovered — abort")

    # Physical / book / encyclopedia
    enc_present = sum(1 for o in objects if "encyclopedia" in (o.get("present_in") or []))
    phase_set = sum(1 for o in objects if o.get("phase"))
    book_status_set = sum(
        1
        for o in objects
        if o.get("book_status") and o.get("book_status") not in {"UNKNOWN", "N/A", None, ""}
    )

    # Semantic OS joins
    with_concept = sum(1 for o in objects if o.get("concepts"))
    with_boundary = sum(1 for o in objects if o.get("owner_boundary"))
    with_journey = sum(1 for o in objects if o.get("journey_steps"))
    with_contract = sum(1 for o in objects if _has_contract(o))
    with_authority = sum(1 for o in objects if _has_authority(o))
    with_evidence = sum(1 for o in objects if _has_evidence(o))
    with_dep = sum(1 for o in objects if _has_dependency_edge(o))
    behavior = _behavior_coverage()

    # Attribution
    src_mods = [o for o in objects if o["kind"] == "module"]
    unattr = sum(
        1
        for o in src_mods
        if (o.get("owner_surface") or "UNATTRIBUTED") == "UNATTRIBUTED"
    )
    attributed = len(src_mods) - unattr

    # Dependency quality
    graph_absent = sum(
        1 for o in objects if o.get("graph_dot_agreement") == "ABSENT_STALE_GRAPH"
    )
    ast_ok = sum(1 for o in objects if not o.get("parse_error"))

    dims = {
        "physical_coverage": {
            "metric": "Objects with encyclopedia enrichment / Objects on disk",
            "numerator": enc_present,
            "denominator": total,
            "pct": _pct(enc_present, total),
            "status": _status(_pct(enc_present, total), green=95, yellow=80),
            "note": "Encyclopedia is enrichment only; disk universe is denominator (848 code files today).",
        },
        "semantic_coverage": {
            "metric": "Objects mapped to ≥1 Concept (CN-*)",
            "numerator": with_concept,
            "denominator": total,
            "pct": _pct(with_concept, total),
            "status": _status(_pct(with_concept, total), green=50, yellow=10),
            "note": (
                "PR-4/PR-5: CN-001..CN-015 + 10 BDs with expanded globs (~93 objects with concept). "
                "YELLOW at ~11%. Further CN (~50 target) and BD waves raise this; object join is "
                "member-driven, not concept-count-driven."
            ),
        },
        "boundary_coverage": {
            "metric": "Objects with owning Boundary (BD-*)",
            "numerator": with_boundary,
            "denominator": total,
            "pct": _pct(with_boundary, total),
            "status": _status(_pct(with_boundary, total), green=50, yellow=10),
            "note": (
                "PR-5: 10 boundaries (BD-001..BD-010) with expanded globs (~94 claimed files). "
                "Spine floor still 11/11. Further seams (~30–40 target) remain for later waves."
            ),
        },
        "journey_coverage": {
            "metric": "Objects participating in ≥1 Journey step",
            "numerator": with_journey,
            "denominator": total,
            "pct": _pct(with_journey, total),
            "status": _status(_pct(with_journey, total), green=30, yellow=5),
            "note": (
                "JN-001 full 7-step candle journey (PR-3/PR-5 BD rewiring). Object participation "
                "follows step member sets; JN-002..005 not yet authored."
            ),
        },
        "contract_coverage": {
            "metric": "Objects with config key / script registry / contract-path hint",
            "numerator": with_contract,
            "denominator": total,
            "pct": _pct(with_contract, total),
            "status": _status(_pct(with_contract, total), green=60, yellow=30),
            "note": "Heuristic contract surface — not formal MC-* seals (still OPEN).",
        },
        "authority_coverage": {
            "metric": "Objects with boundary/regime/relevance authority posture",
            "numerator": with_authority,
            "denominator": total,
            "pct": _pct(with_authority, total),
            "status": _status(_pct(with_authority, total), green=90, yellow=70),
            "note": "owner_surface remains 100% UNATTRIBUTED; authority uses boundary+regime+encyclopedia relevance.",
        },
        "evidence_coverage": {
            "metric": "Objects linked to findings/framework/tests/doc citations",
            "numerator": with_evidence,
            "denominator": total,
            "pct": _pct(with_evidence, total),
            "status": _status(_pct(with_evidence, total), green=60, yellow=30),
            "note": "tests_importing is AST-proven; test_text_references are TEXT_REFERENCE only.",
        },
        "dependency_coverage": {
            "metric": "Objects with ≥1 AST import edge (imports or imported_by)",
            "numerator": with_dep,
            "denominator": total,
            "pct": _pct(with_dep, total),
            "status": _status(_pct(with_dep, total), green=80, yellow=50),
            "note": "AST census covers src+scripts; graph.dot is corroboration only and src-scoped/stale.",
        },
        "attribution_coverage": {
            "metric": "src/ modules with owner_surface ≠ UNATTRIBUTED",
            "numerator": attributed,
            "denominator": len(src_mods),
            "pct": _pct(attributed, len(src_mods)),
            "status": _status(_pct(attributed, len(src_mods)), green=50, yellow=5),
            "note": "Currently ~0% — attribution overlays not authored; use owner_boundary instead.",
        },
        "behavior_coverage": behavior,
        "book_coverage": {
            "metric": "Objects with encyclopedia phase OR book_status enrichment",
            "numerator": max(phase_set, book_status_set, enc_present),
            "denominator": total,
            "pct": _pct(max(phase_set, book_status_set, enc_present), total),
            "status": _status(
                _pct(max(phase_set, book_status_set, enc_present), total),
                green=95,
                yellow=85,
            ),
            "note": "Canonical Book + Encyclopedia documentation layer — strong but ≠ semantic coverage.",
        },
    }

    # Composite: honest "not yet" until semantic dims clear floors
    semantic_dims = (
        "semantic_coverage",
        "boundary_coverage",
        "journey_coverage",
        "behavior_coverage",
        "attribution_coverage",
    )
    all_green = all(dims[d]["status"] == "GREEN" for d in dims)
    semantic_ok = all(dims[d]["status"] != "RED" for d in semantic_dims)
    overall = (
        "YES — multi-dimension floors met"
        if all_green
        else (
            "PARTIAL — documentation strong; semantic OS skeleton only"
            if dims["book_coverage"]["pct"] >= 85 and not semantic_ok
            else "NO — incomplete coverage"
        )
    )

    return {
        "_doc": (
            "Repository Semantic Coverage Dashboard — GENERATED by "
            "scripts/governance/coverage_dashboard.py. Disk universe is the denominator. "
            "Documentation coverage ≠ semantic coverage."
        ),
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "universe": universe,
        "total_objects": total,
        "base_coverage_report": base,
        "dimensions": dims,
        "overall_answer": {
            "is_entire_codebase_covered": overall,
            "verdict": "NOT_YET" if not all_green else "YES",
            "documentation_layer": "STRONG",
            "semantic_layer": "SKELETON" if not semantic_ok else "MATURE",
            "blocking_gaps": [
                d
                for d in dims
                if dims[d]["status"] == "RED"
            ],
            "next_actions": [
                "PR-6: module_attribution overlays (DECISION_SPINE + FEATURE) so owner_surface leaves UNATTRIBUTED",
                "Continue concepts toward ~50 (MeasurementContract, AuthorityLadder, sidecars)",
                "Author JN-002 research / JN-003 governance / JN-004 config / JN-005 agent journeys",
                "PR-7: semantic_impact.py + query \"what breaks\"",
                "PR-8: behavior coverage GREEN_FLOOR hooks",
                "Optional: further BD wave (~20–40 seams) without shrinking spine floor",
            ],
        },
        "counts_snapshot": {
            "with_concept": with_concept,
            "with_boundary": with_boundary,
            "with_journey": with_journey,
            "with_contract": with_contract,
            "with_authority": with_authority,
            "with_evidence": with_evidence,
            "with_dependency_edge": with_dep,
            "encyclopedia_present": enc_present,
            "src_modules": len(src_mods),
            "owner_surface_unattributed": unattr,
            "graph_dot_absent_stale": graph_absent,
            "parse_ok": ast_ok,
        },
    }


def _status(pct: float, green: float, yellow: float) -> str:
    if pct >= green:
        return "GREEN"
    if pct >= yellow:
        return "YELLOW"
    return "RED"


def render_markdown(dash: dict[str, Any]) -> str:
    dims = dash["dimensions"]
    oa = dash["overall_answer"]
    lines = [
        "# Repository Semantic Coverage Dashboard",
        "",
        f"> **GENERATED** `{dash['generated_at_utc']}` by `scripts/governance/coverage_dashboard.py`  ",
        f"> Universe: `{dash['universe']}` · Objects on disk: **{dash['total_objects']}**  ",
        "> Authority: **advisory** — documentation / Semantic OS hygiene only (§6.5).",
        "",
        "## Overall answer",
        "",
        f"**Is the entire codebase covered?** → `{oa['verdict']}`",
        "",
        f"{oa['is_entire_codebase_covered']}",
        "",
        f"| Layer | Assessment |",
        f"|---|---|",
        f"| Documentation (Book + Encyclopedia) | **{oa['documentation_layer']}** |",
        f"| Semantic OS (Concept/Boundary/Journey) | **{oa['semantic_layer']}** |",
        "",
        "### What this dashboard distinguishes",
        "",
        "| You can answer today | You cannot yet answer honestly |",
        "|---|---|",
        "| Is every package indexed in the Encyclopedia? | Is every executable behavior covered? |",
        "| Is every chapter written? | Does every object have Concept + Boundary + Journey + Contract + Authority + Evidence? |",
        "| Physical file documentation | End-to-end semantic coverage |",
        "",
        "## Dimension scores",
        "",
        "| Dimension | Metric | n | N | % | Status |",
        "|---|---|---:|---:|---:|---|",
    ]
    order = [
        "physical_coverage",
        "book_coverage",
        "semantic_coverage",
        "boundary_coverage",
        "journey_coverage",
        "behavior_coverage",
        "contract_coverage",
        "authority_coverage",
        "evidence_coverage",
        "dependency_coverage",
        "attribution_coverage",
    ]
    for key in order:
        d = dims[key]
        lines.append(
            f"| **{key}** | {d['metric']} | {d['numerator']} | {d['denominator']} | "
            f"{d['pct']}% | {d['status']} |"
        )
    lines += [
        "",
        "### Dimension notes",
        "",
    ]
    for key in order:
        d = dims[key]
        lines.append(f"- **{key}** ({d['status']}): {d['note']}")

    base = dash["base_coverage_report"]
    lines += [
        "",
        "## Base Semantic OS coverage_report (raw)",
        "",
        f"- total_objects: {base.get('total_objects')}",
        f"- by_kind: `{json.dumps(base.get('by_kind', {}), sort_keys=True)}`",
        f"- encyclopedia missing: {base.get('encyclopedia', {}).get('missing_count')}",
        f"- module_attribution unattributed_owner_surface: "
        f"{base.get('module_attribution', {}).get('unattributed_owner_surface')}",
        f"- graph_dot absent/stale: {base.get('graph_dot', {}).get('absent_count')}",
        f"- boundary_claimed: {base.get('boundary_claimed')}",
        "",
        "## Blocking gaps (RED)",
        "",
    ]
    reds = oa.get("blocking_gaps") or []
    if not reds:
        lines.append("_None — all dimensions above RED floor._")
    else:
        for g in reds:
            lines.append(f"- `{g}` — {dims[g]['pct']}% ({dims[g]['metric']})")

    lines += [
        "",
        "## Next actions (Semantic OS close-the-gap)",
        "",
    ]
    for a in oa.get("next_actions") or []:
        lines.append(f"1. {a}")

    lines += [
        "",
        "## Related sources",
        "",
        "| Source | Role |",
        "|---|---|",
        "| `src/governance/semantic_objects.py` | Disk universe + Object join + base `coverage_report()` |",
        "| `docs/governance/semantic_os/{concepts,boundaries,journeys}.yaml` | Hand-authored semantic skeleton |",
        "| `docs/book/encyclopedia/` | Documentation encyclopedia E0–E6 + E1b |",
        "| `docs/book/encyclopedia/encyclopedia_rows.jsonl` | Enrichment twin (not denominator) |",
        "| `scripts/governance/seed_semantic_os.py` | Compile YAML → data/semantic_os |",
        "| `graph.dot` | Stale src-only corroboration — do not use as denominator |",
        "",
        "---",
        "",
        "_Regenerate: `python scripts/governance/coverage_dashboard.py`_",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--universe", choices=("code", "all"), default="code")
    ap.add_argument(
        "--json-out",
        type=Path,
        default=_ROOT / "docs" / "governance" / "repository_coverage_dashboard.LATEST.json",
    )
    ap.add_argument(
        "--md-out",
        type=Path,
        default=_ROOT / "docs" / "governance" / "REPOSITORY_COVERAGE_DASHBOARD.md",
    )
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    dash = compute_dashboard(universe=args.universe)
    md = render_markdown(dash)

    print(md[:2500])
    print("\n... [truncated console preview] ...\n")
    oa = dash["overall_answer"]
    print(f"VERDICT: {oa['verdict']}")
    print(f"total_objects={dash['total_objects']}")
    for k, d in dash["dimensions"].items():
        print(f"  {d['status']:6} {k:24} {d['pct']:5}%  ({d['numerator']}/{d['denominator']})")

    if not args.no_write:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(dash, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        args.md_out.write_text(md, encoding="utf-8", newline="\n")
        print(f"\nWROTE {args.json_out}")
        print(f"WROTE {args.md_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
