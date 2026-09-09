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
    # CH-semantic-os-v2: Semantic OS build 1 (L1 concept/boundary/journey registry).
    {
        "path": "scripts/governance/seed_semantic_os.py",
        "category": "GOVERNANCE",
        "lifecycle": "ACTIVE",
        "implementation_status": "EXTRACTED_TO_SRC",
        "logic_in_script": False,
        "dest_modules": ["src/governance/semantic_os.py"],
        "purpose": (
            "Compile the hand-authored Semantic OS YAMLs (docs/governance/semantic_os/"
            "concepts|boundaries|journeys.yaml — the PRIMARY truth) into the gitignored "
            "data/semantic_os/*.jsonl projection. Validates all 14 graph-integrity "
            "checks first and refuses to write on any error. Pinned timestamps make "
            "reruns byte-identical (pinned by tests/test_semantic_os.py)."
        ),
        "task_refs": ["CH-semantic-os-v2", "SITS"],
        "notes": (
            "Thin wrapper — registry/validator logic lives in src/governance/semantic_os.py "
            "(PR-6 pattern). ADVISORY authority only (CLAUDE.md §6.5): grants no production "
            "authority."
        ),
    },
    {
        "path": "scripts/governance/enrich_workbooks_with_semantic_identity.py",
        "category": "GOVERNANCE",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "logic_in_script": True,
        "purpose": (
            "Append Semantic File Identity columns (Semantic ID / Semantic Name / Filename "
            "Semantic Status / Identity Tier / Identity Provenance) to scripts_business_"
            "functionality.xlsx and results/analysis/src_business_functionality.xlsx, and a "
            "Covers-Semantic-ID coverage pointer (derived from Referred files) to docs/analysis/"
            "tests_functionality_inventory.xlsx. Reads the GENERATED data/semantic_os/"
            "file_identities.jsonl projection (fails loudly if absent). Additive-only: never "
            "renames a file, never touches columns A-C/A-F, idempotent column reuse on rerun."
        ),
        "task_refs": ["CH-semantic-file-identity", "SITS"],
        "notes": (
            "Part of the Semantic File Identity Layer — see docs/governance/"
            "SEMANTIC_FILE_IDENTITY_REPORT.md. ADVISORY authority only (CLAUDE.md §6.5): "
            "grants no rename/promotion/production authority."
        ),
    },
    {
        "path": "scripts/research/crt_resolver_economic_comparison.py",
        "category": "RESEARCH_RUNNER",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "ttl_days": 90,
        "purpose": (
            "One-off economic comparison: CRTStateResolver (EXPANSION-entry, "
            "relaxed trigger, no execution authority) vs BacktestRunner's real "
            "ExecutionEngine.build_trade() trades. Descriptive only — see F-069 "
            "for why resolver EXECUTION-rule trades are structurally impossible; "
            "both arms report INSUFFICIENT (n<15) for any economic conclusion."
        ),
        "task_refs": ["F-069", "SITS"],
        "notes": "wontfix:reason=research economic comparison, no promotion authority, n expected tiny",
    },
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
        "path": "scripts/research/crt_range_rebuild_probe.py",
        "category": "DIAGNOSTIC",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "ttl_days": 90,
        "purpose": (
            "OBSERVATION_ONLY probe: classifies residual SWEEP<->RANGE disagreement after B1 "
            "by comparing an engine-like reconstructed active_range against CRTStateResolver's "
            "range memory. Does not modify production spine or defaults."
        ),
        "task_refs": ["SITS"],
        "notes": (
            "wontfix:reason=pre-existing untracked one-shot probe, incidentally swept in by a "
            "later --write-stubs census; not authored in this session, purpose restated from "
            "its own docstring"
        ),
    },
    {
        "path": "scripts/research/xauusd_mt5_cost_calibration.py",
        "category": "DIAGNOSTIC",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "ttl_days": 90,
        "purpose": (
            "ZONE-X O-1 diagnostic: extracts real spread/commission/slippage/swap for XAUUSD "
            "from a locally running MT5 terminal. READ-ONLY, never places or modifies an order."
        ),
        "task_refs": ["SITS"],
        "notes": (
            "wontfix:reason=pre-existing untracked research diagnostic, incidentally swept in "
            "by a later --write-stubs census; not authored in this session; requires a local "
            "MT5 desktop terminal, not CI-runnable"
        ),
    },
    {
        "path": "scripts/research/xauusd_mt5_cost_seed_stops.py",
        "category": "DIAGNOSTIC",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "ttl_days": 90,
        "purpose": (
            "ZONE-X O-1 DEMO-ONLY helper: places near-market STOP orders on XAUUSD so a "
            "companion script can measure stop-order fill vs requested price. Multi-layer "
            "demo-account safety gate (trade_mode re-check, account-hash pin, lot cap, "
            "symbol allowlist, cleanup of MAGIC-tagged orders/positions)."
        ),
        "task_refs": ["SITS"],
        "notes": (
            "wontfix:reason=pre-existing untracked demo-only helper, incidentally swept in by "
            "a later --write-stubs census; not authored in this session; never runs on real "
            "accounts, not CI-runnable"
        ),
    },
    {
        "path": "scripts/research/zone_x_o4_gap_study.py",
        "category": "RESEARCH_RUNNER",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "ttl_days": 90,
        "purpose": (
            "ZONE-X O-4 DESCRIPTIVE gap-penalty study: on XAUUSD M15, how realized adverse "
            "excursion compares to nominal stop distance when a stop resolves on a bar that "
            "gaps from the prior close. Does not seek region class X, unseal the test year, "
            "or grant production/ontology authority."
        ),
        "task_refs": ["SITS"],
        "notes": (
            "wontfix:reason=pre-existing untracked descriptive study, incidentally swept in "
            "by a later --write-stubs census; not authored in this session, purpose restated "
            "from its own docstring"
        ),
    },
    {
        "path": "scripts/research/gate_measurement_m_gate_01.py",
        "category": "RESEARCH_RUNNER",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "ttl_days": 180,
        "purpose": (
            "M-GATE-01 SCOPE measurement (authority: NONE): two-arm gate-OFF vs gate-ON "
            "re-measurement of the CRT spine via ProductionSpineSource, quantifying the "
            "F-037 (pre-2026-07-23, gate-OFF) vs F-058 (active config, gate-ON) epoch delta "
            "across crypto majors, with a hard non-vacuity guard on EngineRunner.run() call "
            "count and reconciliation against F-037's recorded 13->11 / 7->6 figures."
        ),
        "task_refs": ["F-037", "F-058", "RF-CRT-STRUCTURE", "SITS"],
        "notes": (
            "wontfix:reason=research measurement runner, no extract; reuses "
            "ProductionSpineSource unmodified, writes results/research/"
            "gate_measurement_2026_08_06/summary.json"
        ),
    },
    {
        "path": "scripts/governance/crt_config_construction_census.py",
        "category": "DIAGNOSTIC",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "ttl_days": 180,
        "purpose": (
            "P1 OBSERVE census of CRTConfig construction: static AST scan for "
            "ConfigBuilder.build / load_prod_config_from_registry / CRTConfig( call sites, "
            "plus an optional live three-way SCHEMA / ROUTER_BASE / PRODUCTION_MERGED "
            "fingerprint demonstrating the F-057 programmatic split-brain. Does not "
            "fail-closed. Protocol: docs/governance/CRT_CONFIG_CONSTRUCTION_PROTOCOL.md"
        ),
        "task_refs": ["F-057", "SITS"],
        "notes": (
            "wontfix:reason=pre-existing untracked governance census, appeared on disk "
            "mid-session 2026-08-06 and was incidentally swept in by a --write-stubs run; "
            "NOT authored by that session, purpose restated verbatim from its own docstring"
        ),
    },
    {
        "path": "scripts/governance/validation_access_cli.py",
        "category": "DIAGNOSTIC",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "ttl_days": 180,
        "purpose": (
            "VA-XAUUSD-M15 dual-surface validation access: Surface A human CLI ladder "
            "(stdout + ladder_cli.md), Surface B LLM evidence pack under "
            "results/validation_access/xauusd_m15/<run_id>/, gated in S -> I -> F -> E "
            "sequence. Authority: access/packaging only — no promotion. Design freeze: "
            "docs/governance/VALIDATION_ACCESS_VA_XAUUSD_M15.md"
        ),
        "task_refs": ["SITS"],
        "notes": (
            "wontfix:reason=pre-existing untracked governance access CLI, appeared on disk "
            "mid-session 2026-08-06 and was incidentally swept in by a --write-stubs run; "
            "NOT authored by that session, purpose restated verbatim from its own docstring"
        ),
    },
    {
        "path": "scripts/governance/_build_doc_tracking_index.py",
        "category": "DIAGNOSTIC",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "ttl_days": 180,
        "purpose": (
            "Build DOC_TRACKING_INDEX.xlsx — a metadata-only inventory of docs/ (path, "
            "topic bucket, mtime), explicitly performing no content reads."
        ),
        "task_refs": ["SITS"],
        "notes": (
            "wontfix:reason=pre-existing untracked doc-inventory generator, appeared on disk "
            "mid-session 2026-08-06 and was incidentally swept in by a --write-stubs run; "
            "NOT authored by that session, purpose restated verbatim from its own docstring"
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
        "path": "scripts/analysis/module_census.py",
        "category": "GOVERNANCE",
        "lifecycle": "ACTIVE",
        "implementation_status": "TESTED",
        "logic_in_script": False,
        "purpose": (
            "Module attribution census: enumerate src/**/*.py and report closure-surface "
            "coverage; core in src/governance/module_census.py."
        ),
        "dest_modules": [
            "src/governance/module_census.py",
            "src/governance/module_attribution.py",
        ],
        "tests": ["tests/test_module_attribution.py"],
        "task_refs": ["SITS", "CLOSURE-100"],
        "notes": (
            "Phase 1 of the module attribution ledger. Enumeration is enforced hard; "
            "attribution is a monotonic ratchet (see tests/test_module_attribution.py)."
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
    # -- CH-trace-parquet-duckdb-query: DuckDB over Trace/research Parquet sidecars --
    {
        "path": "scripts/analysis/query_trace.py",
        "category": "DIAGNOSTIC",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "logic_in_script": True,
        "dest_modules": [
            "src/utils/duckdb_query.py",
            "src/utils/parquet_store.py",
            "scripts/maintenance/jsonl_to_parquet.py",
        ],
        "config_keys": [],
        "purpose": (
            "READ-ONLY DuckDB query surface over Trace/research Parquet projections "
            "(crt_construction, crt_telemetry, events, opportunities, clean_labels, "
            "bar_structure) via src/utils/duckdb_query.open_views. JSONL remains system "
            "of record; projections are regenerable sidecars from jsonl_to_parquet. "
            "Accepts --list / --family / --sql. DESCRIPTIVE ONLY; no p-value/verdict/"
            "economic claim. Does not replace query_decision_atlas.py."
        ),
    },

    # -- 2026-09-09 overlay clear: classify census-fresh scripts (purpose ≠ GRANDFATHER_UNCLASSIFIED) --
    {
        "path": "scripts/analysis/analytics_evidence_class_census.py",
        "category": "DIAGNOSTIC",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "logic_in_script": True,
        "purpose": (
            "EC-001 observation-only evidence-class census over analytics lineage rows "
            "(CORPUS_VERIFIED/CODE_VERIFIED/DECLARED_ONLY/UNKNOWN). Does not mutate either "
            "analytics registry."
        ),
        "task_refs": ["EC-001"],
    },
    {
        "path": "scripts/research/jse001_crt_context_join.py",
        "category": "RESEARCH_RUNNER",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "logic_in_script": True,
        "purpose": (
            "JSE-001 measure-only: engine_state_asof vs joint-state membership (BNB-only). "
            "NOT a CRT claim; no L-003 doctrine reopen; no src/ edits."
        ),
        "task_refs": ["JSE-001"],
    },
    {
        "path": "scripts/research/jse002_engine_state_path_geometry.py",
        "category": "RESEARCH_RUNNER",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "logic_in_script": True,
        "purpose": (
            "JSE-002 measure-only: does engine_state_asof predict path geometry (BNB-only). "
            "Same join as JSE-001; not CRT Context; no L-003 doctrine reopen."
        ),
        "task_refs": ["JSE-002"],
    },
    {
        "path": "scripts/research/jse003_engine_context_history_path_geometry.py",
        "category": "RESEARCH_RUNNER",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "logic_in_script": True,
        "purpose": (
            "JSE-003 measure-only: engine_context_history vs path geometry (BNB-only). "
            "Compares asof-only baseline vs history features; not CRT unless declared."
        ),
        "task_refs": ["JSE-003"],
    },
    {
        "path": "scripts/research/l003h_trail_exit_transition_replay.py",
        "category": "RESEARCH_RUNNER",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "logic_in_script": True,
        "purpose": (
            "L-003H measure-only candle replay for trail/exit transition events "
            "(standalone duplicate of scanner/forward_walk hooks). No src/ edits."
        ),
        "task_refs": ["L-003H"],
    },
    {
        "path": "scripts/research/l003i_trail_baseline_inversion.py",
        "category": "RESEARCH_RUNNER",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "logic_in_script": True,
        "purpose": (
            "L-003I measure-only baseline direction / base-rate inversion derived from "
            "L-003H JSON artifact. No src/ edits."
        ),
        "task_refs": ["L-003I"],
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
