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
    # CH-trade-chart-tab: offline precompute for the dashboard's Trade Chart tab.
    {
        "path": "scripts/analysis/build_resolver_overlay.py",
        "category": "DATA",
        "lifecycle": "ACTIVE",
        "implementation_status": "EXTRACTED_TO_SRC",
        "logic_in_script": False,
        "dest_modules": ["src/charts/resolver_overlay.py"],
        "purpose": (
            "Precompute the CRTStateResolver per-bar track over a full M15 corpus "
            "(FeaturePipeline + CRTStateResolver, multi-minute pass) and cache it under "
            "results/charts/_resolver_cache/<INSTR>__<corpus_sha8>__<variant>/. "
            "src/control_plane/server.py's /api/chart_series endpoint (charts.chart_api."
            "chart_payload) reads this cache to render the dashboard's Trade Chart tab "
            "resolver ribbon; it NEVER computes the track in-request. The cache is keyed "
            "on the corpus's sha256, so re-run this after the corpus file changes."
        ),
        "task_refs": ["CH-trade-chart-tab", "F-069", "SITS"],
        "notes": (
            "Thin wrapper — all logic lives in src/charts/resolver_overlay.py (PR-6 "
            "pattern). Descriptive only, no economic claim, no G001, no promotion "
            "(CLAUDE.md §6.5). The resolver track is a DIFFERENT CONSTRUCTION from the "
            "engine (spine) track the same tab also shows — F-069 measured only 88.16% "
            "agreement / 10.77% EXPANSION recall between the two; never merge them."
        ),
    },
    # Semantic OS v2 meaning plane: integration run (engine observed bar by bar vs concept contracts).
    {
        "path": "scripts/governance/semantic_os_integration.py",
        "category": "GOVERNANCE",
        "lifecycle": "ACTIVE",
        "implementation_status": "EXTRACTED_TO_SRC",
        "logic_in_script": False,
        "dest_modules": [
            "src/semantics/integration/observe.py",
            "src/semantics/integration/checks.py",
            "src/semantics/integration/report.py",
        ],
        "purpose": (
            "Semantic OS integration run: runs the real backtest twice on one XAUUSD corpus "
            "(default the one-month slice), refuses to judge unless the observed and plain "
            "event streams are identical, then compares every observed bar with the v2 concept "
            "contracts (AGREE / EXPECTED_DIVERGENCE / UNEXPLAINED / NOT_CHECKABLE) and writes "
            "results/semantic_os_integration/<stamp>/ with a D-level table per concept."
        ),
        "task_refs": ["SEMANTIC_OS_V2_MEANING_PLANE", "SITS"],
        "notes": (
            "Thin wrapper — logic lives in src/semantics/integration/. Observation only: the "
            "engine is wrapped per instance, never edited. Not a performance run: no P&L, "
            "expectancy or win rate. Meaning authority only (CLAUDE.md §6.5/§6.6)."
        ),
    },
    # Semantic OS v2 R1-C: deterministic trade-exercising corpus window for the integration run.
    {
        "path": "scripts/governance/semantic_os_trade_window.py",
        "category": "GOVERNANCE",
        "lifecycle": "ACTIVE",
        "implementation_status": "EXTRACTED_TO_SRC",
        "logic_in_script": False,
        "dest_modules": ["src/semantics/integration/select_window.py"],
        "purpose": (
            "R1-C: from a plain full-corpus XAUUSD backtest (engine trades CSV + events.jsonl only, "
            "never a Semantic OS verdict) pick the smallest contiguous window with the widest trade "
            "lifecycle coverage (trade, LONG, SHORT, stop exit, TP1, TP2, >=2 trades), cut it "
            "verbatim to data/mt5/XAUUSD_W<start>-to-<end>.csv, verify the engine reproduces the "
            "same trades on the slice, and write results/semantic_os_integration/r1c_scan/selection.json."
        ),
        "task_refs": ["SEMANTIC_OS_V2_MEANING_PLANE", "R1-C", "SITS"],
        "notes": (
            "Thin wrapper — logic lives in src/semantics/integration/select_window.py. Selection "
            "provenance is engine output only, so the integration experiment is not contaminated "
            "by its own verdicts. No P&L is read or reported."
        ),
    },
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
    # EPIC-84 F2: census of every silent default / fallback in src/ (no-defaults rule 2026-09-28).
    {
        "path": "scripts/analysis/config_fallback_census.py",
        "category": "DIAGNOSTIC",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "ttl_days": 90,
        "purpose": (
            "AST census of every site in src/ where a value can come from a code literal instead "
            "of a loaded config (.get/getattr defaults, DEFAULT_* merges, `or` literals, "
            "config-dataclass field defaults, env defaults), classified CONFIG/PARAM_DEFAULT/ENV/"
            "DATA/UNCLASSIFIED. Writes docs/research-readiness/config-fallback-census.{json,md}; "
            "the EPIC-84 lane work list and (Wave 2) the blocking ratchet input."
        ),
        "task_refs": ["EPIC-84", "SITS"],
        "notes": "wontfix:reason=read-only census, no economic claim, no promotion authority",
    },
    # EPIC-83 STORY-83.6 (WP-F): five-way parity of the v5 shadow config vs the active config.
    {
        "path": "scripts/research/parity_v5.py",
        "category": "RESEARCH_RUNNER",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "ttl_days": 90,
        "purpose": (
            "Five-way XAUUSD parity of configs/production/v5_htfcrt_sot_dual_k23_2026_09 vs the "
            "active v2_htfcrt_2026_08: trade ledger, engine events/telemetry, resolver states.csv, "
            "layer_trace, oracle labels. Each arm runs in its own isolated_config_root (own "
            "ACTIVE_VERSION copy); reuses v3_config_parity.compare. Declared/volatile fields: "
            "config_hash, run_id, artifact_timestamp, resolver meta built_at/corpus_path, "
            "execution_intent_id (uuid minted per trade)."
        ),
        "task_refs": ["STORY-83.6", "EPIC-83", "SITS"],
        "notes": "wontfix:reason=parity instrument only, no economic claim, no promotion authority",
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

    # -- 2026-09-14 research-framework consolidation Phase 0: archive ledger verifier --
    {
        "path": "scripts/maintenance/verify_archive_manifests.py",
        "category": "GOVERNANCE",
        "lifecycle": "ACTIVE",
        "implementation_status": "EXTRACTED_TO_SRC",
        "logic_in_script": False,
        "dest_modules": ["src/governance/archive_manifest.py"],
        "config_keys": [],
        "tests": ["tests/governance/test_archive_manifests.py"],
        "purpose": (
            "Archive ledger verifier (zero-loss promise of the research-framework consolidation): "
            "every file under archive/ must be named by a SHA-256-matching archive-copy manifest row, "
            "no live original may disappear, every batch dir must be in archive/ARCHIVE_INDEX.md. "
            "`backfill [--apply]` appends rows for archived files that have none (append-only). "
            "Thin CLI; logic in src/governance/archive_manifest.py. Grants no authority."
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
    {
        "path": "scripts/analysis/corpus_read_census.py",
        "category": "DIAGNOSTIC",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "logic_in_script": True,
        "purpose": (
            "PHASE 0 census (single-corpus-read-seam program): AST scan of src/scripts/"
            "tools/tests for direct OHLCV-corpus reads (read_csv/read_excel/load_workbook/"
            "csv.reader/open), classified CORPUS/DERIVED/GATED/UNKNOWN via literal-path "
            "rules plus intra-function/self-attr taint tracing back to corpus_gate."
            "admit_corpus / dataset_registry.admit_csv_path. Read-only; writes only its "
            "own JSON manifest under docs/governance/build_manifests/. No src/ edits, no "
            "corpus mutation, no migration performed."
        ),
        "task_refs": ["CORPUS-READ-SEAM-P0"],
    },
    {
        "path": "scripts/analysis/corpus_read_lint.py",
        "category": "GOVERNANCE",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "logic_in_script": True,
        "purpose": (
            "PHASE 3 enforcement (single-corpus-read-seam program): shrink-only ratchet "
            "over corpus_read_census.py's CORPUS/UNKNOWN findings against the frozen "
            "docs/governance/corpus_read_allowlist.json snapshot, matched by durable_key "
            "(AST-content hash, not line number). Fails only on a genuinely NEW direct "
            "corpus read; a migrated/reclassified site is reported SHRUNK, never a "
            "failure. --regenerate re-snapshots the allowlist after a real migration. "
            "Wired into scripts/maintenance/check_governance_invariants.py GREEN_FLOOR."
        ),
        "task_refs": ["CORPUS-READ-SEAM-P3"],
    },
    {
        "path": "scripts/research/derive_opportunity_rr_bands.py",
        "category": "RESEARCH_RUNNER",
        "lifecycle": "ACTIVE",
        "implementation_status": "EXTRACTED_TO_SRC",
        "logic_in_script": False,
        "dest_modules": ["src/research/opportunity_bands.py", "src/research/band_tables.py"],
        "purpose": (
            "Phase 1 of the layered-outcome-ontology plan: a READ-ONLY arithmetic deriver "
            "over an existing opportunity_scanner.py (SEM-037) run. Writes the sidecar "
            "opportunities_rr_bands.jsonl (registered STR-OPP-RR-BAND-SIDECAR, "
            "docs/governance/jsonl_claim_catalog.yaml) carrying exit_mechanism/trail_state/"
            "risk_distance/mfe_r/mae_r/exit_bounded_capture/capture_state/rr_band, every "
            "field CC-OPP-BAND-RESTATEMENT admissible and CC-OPP-BAND-NOT-ECONOMIC refuses "
            "any economic reading of. Does not re-simulate the kernel; does not touch the "
            "source file (verified: source sha256 unchanged, matches run_linkage_registry.json "
            "A1). Fails closed on an unknown outcome literal, a non-positive risk_distance, "
            "or an SL_HIT row with rr_achieved < -1.0 (adverse fill outside the documented "
            "arming identity) rather than silently mislabeling it."
        ),
        "task_refs": ["SEM-037", "SEM-020", "CC-OPP-BAND-RESTATEMENT", "SITS"],
        "notes": (
            "Thin wrapper — all classification logic lives in src/research/opportunity_bands.py "
            "and src/research/band_tables.py (PR-6 pattern). Descriptive only, no economic "
            "claim, no G001, no promotion (CLAUDE.md 6.5). economic_claims_allowed stays false "
            "on AN-PIPEB-STRAT-XAUUSD-M15-V1; this script does not change that."
        ),
    },

    # STORY-12.3: asset-coverage census + PRIMARY seed (P0, no src/ edit).
    {
        "path": "scripts/analysis/asset_writer_census.py",
        "category": "DIAGNOSTIC",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "logic_in_script": True,
        "dest_modules": [],
        "purpose": (
            "AST census of write-shaped calls in src/ and scripts/ "
            "(open in write mode, write_text, write_bytes, dump, to_csv, to_parquet, writelines). "
            "Emits the writer-symbol set the asset-coverage UNREGISTERED pin is checked against. "
            "Observation only. Does not register coverage rows and does not edit src/."
        ),
        "task_refs": ["STORY-12.3"],
        "tests": ["tests/test_asset_coverage.py"],
        "notes": (
            "P0 of docs/implementation_plan/run-trace-coverage-schema-2026-09-17.md. "
            "Stdout is JSONL. The count comment goes to stderr."
        ),
    },
    {
        "path": "scripts/governance/seed_asset_coverage.py",
        "category": "GOVERNANCE",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "logic_in_script": True,
        "dest_modules": [],
        "purpose": (
            "PRIMARY seed for asset_coverage_v1. Writes the eight hand rows RTC-001..RTC-008 "
            "(backtest writers plus the paper-rail audit writer) and fills evidence lines from the AST. "
            "data/asset_coverage.jsonl is generated. Do not hand-edit it."
        ),
        "task_refs": ["STORY-12.3"],
        "tests": ["tests/test_asset_coverage.py"],
        "notes": (
            "Register this script and scripts/analysis/asset_writer_census.py the same turn "
            "or the SITS disk-coverage floor fails."
        ),
    },
    # Market-language census: deterministic vocabulary extractor (S1..S8) for the
    # Run/Trace identity design — no new engineering words, every row is cited to an authority.
    {
        "path": "scripts/analysis/market_language_census.py",
        "category": "DIAGNOSTIC",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "logic_in_script": True,
        "dest_modules": [],
        "purpose": (
            "Deterministic read-only census of the EXISTING market-language vocabulary across "
            "the five authority files (market_ontology.yaml, market_crt_states.yaml, "
            "crt_state_identity.yaml, market_shapes.yaml, feature_schema.py) plus the trade "
            "sources (src/journal/schema.py, execution_planner.py, crt_engine_v2.py). Emits "
            "S1 feature schema, S2 four DISTINCT state vocabularies (crt_machine / "
            "feature_enum / smc_choch / trade_execution), S3 hierarchy, S4 trade schema, S5 "
            "traceable ontology, S6 exact + concept-token overlaps (e.g. the sweep 3+ way "
            "overlap), S7 orphans, S8 canonical vocabulary table to "
            "docs/research-readiness/market_language_census_report.json(.md). Never invents "
            "or normalises a word; used to fix the Run/Trace identity vocabulary."
        ),
        "task_refs": ["RUN-TRACE-IDENTITY", "MARKET-LANGUAGE-CENSUS"],
        "tests": [],
        "notes": (
            "Volatile (opinionated analysis report) surface — census output is not a governed "
            "schema, only a citation-backed inventory. No G001, no promotion, no production "
            "behaviour. See docs/governance/REPOSITORY_CONSTRUCTION_PROTOCOL.md."
        ),
    },
    # CH-identity-chain-closure-v1: Phase 3 closed identity chain, 7-invariant checker CLI.
    {
        "path": "scripts/governance/identity_chain_check.py",
        "category": "GOVERNANCE",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "logic_in_script": False,
        "dest_modules": ["src/governance/identity_chain.py", "src/governance/identity_spine.py"],
        "purpose": (
            "Thin CLI wrapper (report-only authority) over governance.identity_chain.check_run: "
            "verifies the 7 closed-identity-chain invariants (telemetry envelope uniformity, "
            "ACCEPTED lifecycle completeness, bar-clock monotonicity, trades<->lifecycle "
            "bidirectional closure, strict ACCEPTED.trade_id resolution across trades.csv AND "
            "L8 on the same bar_open_ts, L8 set closure, label provenance) across the Spine "
            "journal, Oracle labeler, layer-trace, and engine telemetry streams, joined only "
            "through the canonical bar-clock bridge (bar_identity.jsonl). --require-all treats "
            "every SKIP (an invariant whose input was not supplied) as a violation; without it, "
            "a partially-wired run can still exit 0, and the printed summary discloses that "
            "partiality explicitly (\"PARTIAL\") so the exit code is never misread alone."
        ),
        "task_refs": ["CH-identity-chain-closure-v1"],
        "tests": ["tests/test_identity_chain.py"],
        "notes": (
            "Grants nothing and changes nothing — verifies identity joins only, no market "
            "quantity. production_behavior_changed: NO."
        ),
    },
    {
        "path": "scripts/data/mt5_history_probe.py",
        "category": "DATA",
        "lifecycle": "ACTIVE",
        "implementation_status": "LOGIC_IN_SCRIPT",
        "purpose": (
            "Program 12 Step 2a: read-only MT5 history-availability probe. Per symbol x "
            "timeframe: resolved broker symbol, earliest/latest bar (broker-server time), bar "
            "count, Max-bars truncation flag, gap histogram; per symbol: digits, point, spread, "
            "contract size, recent tick count, broker clock offset. Writes a JSON report only."
        ),
        "task_refs": ["Program-12"],
        "notes": (
            "wontfix:reason=one-shot external-data probe; runs only on Windows with a "
            "MetaTrader 5 terminal. Writes no market data. production_behavior_changed: NO."
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
