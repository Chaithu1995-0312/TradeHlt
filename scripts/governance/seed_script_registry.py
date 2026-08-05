"""Thin CLI + PRIMARY overlays for SITS seed (PR-6: merge engine in src/governance/script_seed.py).

Overlay list below is hand-maintained PRIMARY truth. Core merge lives under src/.

    python scripts/governance/seed_script_registry.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from governance.script_registry import ScriptRegistry  # noqa: E402
from governance.script_seed import apply_overlays, build_records  # noqa: E402
from utils.jsonl_writer import read_jsonl  # noqa: E402

DEFAULT_STUBS = _ROOT / "docs" / "governance" / "script_registry_stubs.jsonl"
OUT = _ROOT / "data" / "script_registry.jsonl"

# PRIMARY curated refinements (K11). Match by path or id. Overlay fields win.
OVERLAYS: list[dict[str, Any]] = [
    {
        "path": "scripts/governance/construction_protocol.py",
        "implementation_status": "ACCEPTED_COLOCATED",
        "category": "GOVERNANCE",
        "lifecycle": "ACTIVE",
        "logic_in_script": True,
        "purpose": (
            "Gate-6 construction protocol validator "
            "(accepted colocated governance tooling — not a thin wrapper)."
        ),
        "notes": (
            "Logic intentionally under scripts/governance/; listed in "
            "docs/governance/script_colocated_allowlist.json."
        ),
        "task_refs": ["SITS", "Gate-6"],
    },
    # F-069 program: CRT Semantic Parity (CRTStateResolver vs BacktestRunner, config-only)
    {
        "path": "scripts/research/crt_state_confusion_matrix.py",
        "category": "RESEARCH_RUNNER",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "ttl_days": 90,
        "purpose": (
            "Bar-aligned CRT resolver-vs-engine confusion-matrix instrument. Extended "
            "this session (F-069) with an explicit injection axis (none/reset/state_to/"
            "full — 'none' is config-only, the program's primary metric), a reusable "
            "run_once()/prepare_engine_context() core, and an enriched-frame cache seam "
            "for sweep reuse. Was pre-existing untracked (GRANDFATHER_UNCLASSIFIED stub "
            "SCR-259, created 2026-08-02); reclassified with a real purpose here."
        ),
        "task_refs": ["F-069", "SITS"],
        "notes": "wontfix:reason=research instrument, extended not extracted; no promotion authority",
    },
    {
        "path": "scripts/research/crt_parity_sweep.py",
        "category": "RESEARCH_RUNNER",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "ttl_days": 90,
        "purpose": (
            "Stage A/B sweep driver for CRT semantic parity: coordinate-descent over "
            "resolver-only config (Stage A) and one-way engine-sensitivity diagnostic "
            "(Stage B). Never writes to a tracked config path (F-069)."
        ),
        "task_refs": ["F-069", "SITS"],
        "notes": "wontfix:reason=research sweep driver for F-069, no promotion authority",
    },
    {
        "path": "scripts/research/crt_parity_classifier.py",
        "category": "DIAGNOSTIC",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "ttl_days": 90,
        "purpose": (
            "Pure mismatch classifier (A/B/C/D taxonomy) for CRT semantic parity "
            "confusion-matrix cells; zero I/O, synthetically drivable (F-069)."
        ),
        "task_refs": ["F-069", "SITS"],
        "notes": "wontfix:reason=pure research diagnostic for F-069, reused by Phase-2 vision program",
    },
    {
        "path": "scripts/research/crt_parity_report.py",
        "category": "RESEARCH_RUNNER",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "ttl_days": 90,
        "purpose": (
            "Generates reports/crt_semantic_parity_report.md from the Stage-A sweep "
            "ledger + crt_parity_classifier.py classifications (F-069)."
        ),
        "task_refs": ["F-069", "SITS"],
        "notes": "wontfix:reason=research report generator for F-069",
    },
    # PR-5 curated TTL debt tracking
    {
        "path": "scripts/analysis/rr_confidence_probe.py",
        "category": "DIAGNOSTIC",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "ttl_days": 90,
        "purpose": "In-sample RR Mahalanobis confidence distribution probe (F-044).",
        "task_refs": ["F-044", "SITS"],
        "notes": (
            "wontfix:reason=research diagnostic for F-044 gate mis-scale; "
            "no extract until rr_fusion re-enabled under §6.5"
        ),
    },
    # Pre-existing untracked one-shot inventory tools, swept into scope by this session's
    # full-repo `--write-stubs` regeneration (working tree has known untracked divergence —
    # see project_untracked_tree_divergence memory). Not authored this session; purposes
    # below are restated verbatim from each script's own docstring, not invented.
    {
        "path": "_scripts_functionality_export.py",
        "category": "MAINTENANCE",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "purpose": "One-shot exporter: scripts/**/*.py -> Excel (name, summary, project imports).",
        "task_refs": ["SITS"],
        "notes": "wontfix:reason=repo-root one-shot inventory tool, pre-existing untracked",
    },
    {
        "path": "scripts/analysis/src_business_functionality_inventory.py",
        "category": "MAINTENANCE",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "purpose": "Inventory business functionality of every src/**/*.py file -> xlsx.",
        "task_refs": ["SITS"],
        "notes": "wontfix:reason=one-shot inventory tool, pre-existing untracked",
    },
    {
        "path": "scripts/analysis/test_functionality_excel.py",
        "category": "MAINTENANCE",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "purpose": "Build an Excel inventory of tests/**/*.py business functionality (read-only).",
        "task_refs": ["SITS"],
        "notes": "wontfix:reason=one-shot inventory tool, pre-existing untracked",
    },
    {
        "path": "scripts/analysis/soft_conf_ema_double_update_probe.py",
        "category": "DIAGNOSTIC",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "ttl_days": 90,
        "purpose": (
            "OBSERVATION_ONLY probe (F-067): measures the CRT soft-confirmation double "
            "EngineState.update_emas call — spread-compression magnitude + tier-flip count "
            "on XAUUSD, no src/ edit."
        ),
        "task_refs": ["F-067", "SEM-006", "SITS"],
        "notes": (
            "wontfix:reason=research diagnostic pending a separate BEHAVIOR_CHANGE_AUTHORIZED "
            "decision on whether to remove the duplicate update_emas call; no extract until then"
        ),
    },
    {
        "path": "scripts/analysis/feature_math_lint.py",
        "category": "DIAGNOSTIC",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "ttl_days": 180,
        "purpose": "Ownership lint for feature-math re-derivation (semantics-not-syntax).",
        "task_refs": ["F-047", "SITS"],
        "dest_modules": ["src/features/registry/", "scripts/analysis/feature_math_lint.py"],
        "notes": (
            "Promotion plan: keep as governed analysis CLI; core lint rules already "
            "mirrored under features registry floors — no further extract required."
        ),
    },
    {
        "path": "scripts/analysis/behavior_census.py",
        "category": "DIAGNOSTIC",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "ttl_days": 180,
        "purpose": "AST behavior-census for config-first maturity (HARD_CODED→CONFIG_DRIVEN).",
        "task_refs": ["SITS", "config-first"],
        "dest_modules": ["scripts/analysis/behavior_census.py"],
        "notes": (
            "Promotion plan: analysis entry point stays in scripts/; maturity pins live "
            "in tests/test_behavior_census.py."
        ),
    },
    {
        "path": "scripts/analysis/gate2b_adjudication.py",
        "category": "DIAGNOSTIC",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "ttl_days": 90,
        "purpose": "Gate-2b feature-math divergence adjudication ledger helper.",
        "task_refs": ["F-047", "SITS"],
        "notes": (
            "wontfix:reason=point-in-time adjudication artifact generator; "
            "durable ledger is docs/analysis/feature-math-divergence-adjudication.md"
        ),
    },
    {
        "path": "scripts/analysis/zone_assignment_parity_probe.py",
        "category": "DIAGNOSTIC",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "ttl_days": 90,
        "purpose": "ZoneGate assignment parity probe (F-041 runtime↔label).",
        "task_refs": ["F-041", "SITS"],
        "notes": (
            "wontfix:reason=one-shot parity probe; ZoneGate lineage is AUDITED not CLOSED"
        ),
    },
    # PR-6 extract wave — SITS cores productized under src/governance/
    {
        "path": "scripts/analysis/script_census.py",
        "category": "CANONICAL_CLI",
        "lifecycle": "ACTIVE",
        "implementation_status": "TESTED",
        "logic_in_script": False,
        "control_plane_id": "governance.script_census",
        "purpose": "Thin CLI for SITS census; core in src/governance/script_census.py.",
        "dest_modules": ["src/governance/script_census.py"],
        "tests": ["tests/test_script_registry.py"],
        "task_refs": ["SITS", "PR-6"],
        "notes": (
            "PR-6 extract: discover_paths/write_stubs moved to src/governance/script_census.py; "
            "this file is thin argparse only."
        ),
    },
    {
        "path": "scripts/governance/seed_script_registry.py",
        "category": "CANONICAL_CLI",
        "lifecycle": "ACTIVE",
        "implementation_status": "TESTED",
        "logic_in_script": False,
        "control_plane_id": "governance.seed_script_registry",
        "purpose": "Thin CLI + PRIMARY overlays; merge engine in src/governance/script_seed.py.",
        "dest_modules": ["src/governance/script_seed.py"],
        "tests": ["tests/test_script_registry.py"],
        "task_refs": ["SITS", "PR-6"],
        "notes": (
            "PR-6 extract: apply_overlays/build_records moved to src/governance/script_seed.py; "
            "OVERLAYS list remains PRIMARY here."
        ),
    },
    {
        "path": "scripts/governance/query_scripts.py",
        "category": "CANONICAL_CLI",
        "lifecycle": "ACTIVE",
        "implementation_status": "WIRED",
        "logic_in_script": False,
        "control_plane_id": "governance.query_scripts",
        "purpose": "Thin CLI over ScriptRegistry query/debt/parity APIs.",
        "dest_modules": ["src/governance/script_registry.py"],
        "tests": ["tests/test_script_registry.py"],
        "task_refs": ["SITS", "PR-6"],
        "notes": (
            "PR-6: query surface already library-backed by ScriptRegistry; CLI is argparse only."
        ),
    },
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Seed data/script_registry.jsonl (SITS)")
    ap.add_argument("--stubs", default=str(DEFAULT_STUBS), help="PRIMARY stubs JSONL path")
    ap.add_argument("--out", default=str(OUT), help="Generated registry JSONL path")
    ap.add_argument(
        "--no-control-plane-link",
        action="store_true",
        help="Skip CommandSpec reverse-map (debug / unit isolation)",
    )
    args = ap.parse_args(argv)

    if args.no_control_plane_link:
        stubs = read_jsonl(Path(args.stubs)) if Path(args.stubs).exists() else []
        records = apply_overlays(stubs, OVERLAYS)
    else:
        records = build_records(
            Path(args.stubs),
            OVERLAYS,
            link_control_plane=True,
        )
    n = ScriptRegistry.dump(args.out, records)
    print(f"Seeded {n} script records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
