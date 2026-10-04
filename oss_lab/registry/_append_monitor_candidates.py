"""One-shot helper: append OSS monitor scan candidates. Run from repo root."""
from __future__ import annotations

import json
from pathlib import Path

p = Path(__file__).resolve().parent / "oss_capabilities.jsonl"
existing = p.read_text(encoding="utf-8")

new_records = [
    {
        "oss_id": "OSS-CODEBASE-MEMORY",
        "name": "Codebase-Memory MCP",
        "repository": "https://github.com/DeusData/codebase-memory-mcp",
        "version": "UNPINNED",
        "commit_or_tag": "UNKNOWN",
        "license": "MIT",
        "license_obligations": ["retain_copyright_notice", "include_license"],
        "security_status": "ASSESSED_RISK",
        "maintenance_status": "ACTIVE",
        "purpose": (
            "T1 development tool: structural repository graph (call/import/class/route) "
            "for agent/repo intelligence. Feeds STRUCTURAL facts only — never replaces "
            "Semantic OS meaning authority."
        ),
        "capabilities": [
            "tree_sitter_parsing",
            "persistent_code_graph",
            "cross_repo_edges",
            "lsp_style_semantic_resolution",
            "mcp_tool_surface",
            "structural_call_import_queries",
        ],
        "integration_role": "DEV_TOOL",
        "trust_tier": "T1",
        "allowed_surfaces": [
            "oss_lab/adapters/codebase_memory",
            "oss_lab/evidence/repo_intel",
            "results/oss_lab/repo_intel",
        ],
        "forbidden_surfaces": [
            "docs/governance/semantic_os",
            "src/governance/semantic_os.py",
            "configs/formulas/market_ontology.yaml",
            "src/config_layer/crt_engine_v2.py",
            "src/core",
            "configs/production",
            "src/governance/promotion_manager.py",
        ],
        "input_contract": "local_repository_tree",
        "output_contract": "oss_lab/contracts/structural_fact.py#StructuralFactRecord",
        "adapter": "oss_lab/adapters/codebase_memory",
        "tests": [],
        "certification_status": "NOT_STARTED",
        "provenance": {
            "discovered_utc": "2026-08-12T18:00:00Z",
            "discovered_by": "oss_monitor_scan",
            "sources": [
                "https://github.com/DeusData/codebase-memory-mcp",
                "https://arxiv.org/abs/2603.27277",
                "user_oss_monitor_brief",
            ],
        },
        "known_risks": [
            "reads_entire_filesystem_or_repo",
            "writes_agent_configuration_files",
            "published_token_reduction_claims_need_independent_reproduction",
            "must_not_become_semantic_os_authority",
            "supply_chain_binary_trust_requires_slsa_sigstore_verify",
        ],
        "decision": "DISCOVERED",
        "decision_reason": (
            "Strongest repo-intelligence candidate for controlled local benchmark against "
            "existing pyan/graph.dot/Semantic OS tooling. Priority 1 in evaluation queue. "
            "No install until APPROVED_FOR_LAB + pin + security audit."
        ),
        "lifecycle_status": "DISCOVERED",
        "notes": [
            "Architecture: structural facts IN, Semantic OS meaning OUT.",
            "Answers structural call/import questions; Semantic OS answers meaning.",
            "Head-to-head with OSS-INFIGRAPH before dual adoption.",
            "Research claims (token/tool reductions) = PUBLISHED RESULT until reproduced.",
        ],
    },
    {
        "oss_id": "OSS-LEAN",
        "name": "QuantConnect LEAN",
        "repository": "https://github.com/QuantConnect/Lean",
        "version": "UNPINNED",
        "commit_or_tag": "UNKNOWN",
        "license": "Apache-2.0",
        "license_obligations": [
            "retain_copyright_notice",
            "include_license",
            "state_changes",
        ],
        "security_status": "NOT_ASSESSED",
        "maintenance_status": "ACTIVE",
        "purpose": (
            "T3 independent event-driven execution/backtest laboratory alongside Nautilus — "
            "same Tradelatest signal, alternate fill/cost/latency mechanics. Never import "
            "LEAN strategy architecture into Tradelatest spine."
        ),
        "capabilities": [
            "event_driven_backtest",
            "execution_simulation",
            "multi_asset_classes",
            "portfolio_account_management",
            "research_notebooks",
            "optimization",
            "live_trading_hooks",
            "python_and_csharp",
        ],
        "integration_role": "RUNTIME_EXECUTION_ADAPTER",
        "trust_tier": "T3",
        "allowed_surfaces": [
            "oss_lab/adapters/lean",
            "oss_lab/evidence",
            "results/oss_lab",
        ],
        "forbidden_surfaces": [
            "configs/formulas/market_ontology.yaml",
            "src/config_layer/crt_engine_v2.py",
            "src/core/fusion_engine.py",
            "src/core/decision_engine.py",
            "src/config_layer/execution_planner.py",
            "src/core/ultron_risk_gate.py",
            "configs/production",
            "src/governance",
            "src/strategies",
        ],
        "input_contract": "oss_lab/contracts/dataset_manifest.py",
        "output_contract": "oss_lab/contracts/trade_record.py#BenchmarkTradeRecord",
        "adapter": "oss_lab/adapters/lean",
        "tests": [],
        "certification_status": "NOT_STARTED",
        "provenance": {
            "discovered_utc": "2026-08-12T18:00:00Z",
            "discovered_by": "oss_monitor_scan",
            "sources": [
                "https://github.com/QuantConnect/Lean",
                "https://www.lean.io/",
                "user_oss_monitor_brief",
            ],
        },
        "known_risks": [
            "large_complete_platform_temptation_to_replace_architecture",
            "data_feed_divergence_from_phase1_corpus",
            "fill_model_incomparability_vs_tradelatest_and_nautilus",
            "heavy_dependency_and_build_surface_csharp",
            "cloud_platform_features_not_local_evidence",
        ],
        "decision": "DISCOVERED",
        "decision_reason": (
            "Apache-2.0 independent execution benchmark candidate. Add to three-way "
            "execution comparison: Tradelatest | Nautilus | LEAN under identical signal "
            "+ DatasetManifest. Do not import LEAN strategy model."
        ),
        "lifecycle_status": "DISCOVERED",
        "notes": [
            "Preferred role: independent implementation of mechanics, not strategy host.",
            "Same BenchmarkTradeRecord + CanonicalMetrics path as Nautilus.",
            "No install until APPROVED_FOR_LAB + version pin.",
        ],
    },
    {
        "oss_id": "OSS-INFIGRAPH",
        "name": "Infigraph",
        "repository": "https://github.com/intuit/infigraph",
        "version": "UNPINNED",
        "commit_or_tag": "UNKNOWN",
        "license": "Apache-2.0",
        "license_obligations": [
            "retain_copyright_notice",
            "include_license",
            "state_changes",
        ],
        "security_status": "NOT_ASSESSED",
        "maintenance_status": "UNKNOWN",
        "purpose": (
            "T1 local AST + graph + Cypher + hybrid semantic search for structural "
            "repository facts. Complement candidate for Semantic OS machine-derived "
            "relationship layer — head-to-head with Codebase-Memory; do not adopt both "
            "without evidence."
        ),
        "capabilities": [
            "ast_parsing",
            "persistent_knowledge_graph",
            "cypher_queries",
            "hybrid_semantic_search",
            "cross_file_call_resolution",
            "local_first_zero_network",
        ],
        "integration_role": "DEV_TOOL",
        "trust_tier": "T1",
        "allowed_surfaces": [
            "oss_lab/adapters/infigraph",
            "oss_lab/evidence/repo_intel",
            "results/oss_lab/repo_intel",
        ],
        "forbidden_surfaces": [
            "docs/governance/semantic_os",
            "src/governance/semantic_os.py",
            "configs/formulas/market_ontology.yaml",
            "src/config_layer/crt_engine_v2.py",
            "src/core",
            "configs/production",
            "src/governance/promotion_manager.py",
        ],
        "input_contract": "local_repository_tree",
        "output_contract": "oss_lab/contracts/structural_fact.py#StructuralFactRecord",
        "adapter": "oss_lab/adapters/infigraph",
        "tests": [],
        "certification_status": "NOT_STARTED",
        "provenance": {
            "discovered_utc": "2026-08-12T18:00:00Z",
            "discovered_by": "oss_monitor_scan",
            "sources": [
                "https://github.com/intuit/infigraph",
                "user_oss_monitor_brief",
            ],
        },
        "known_risks": [
            "heavy_overlap_with_codebase_memory",
            "dual_adoption_without_head_to_head_is_waste",
            "must_not_replace_semantic_os_meaning_layer",
            "license_file_not_byte_verified_this_turn_reported_apache2",
        ],
        "decision": "DISCOVERED",
        "decision_reason": (
            "Interesting Semantic OS structural complement. Correct next step is "
            "head-to-head benchmark vs OSS-CODEBASE-MEMORY, not dual deploy."
        ),
        "lifecycle_status": "DISCOVERED",
        "notes": [
            "Local-first, no API key claimed — favorable for offline governance posture.",
            "License stated Apache-2.0 in monitor brief; re-verify LICENSE file on pin.",
        ],
    },
    {
        "oss_id": "OSS-VECTORBT",
        "name": "VectorBT",
        "repository": "https://github.com/polakowo/vectorbt",
        "version": "UNPINNED",
        "commit_or_tag": "UNKNOWN",
        "license": "Apache-2.0+Commons-Clause",
        "license_obligations": [
            "LEGAL_REVIEW_REQUIRED",
            "commons_clause_restricts_selling_software_or_service_deriving_substantial_value",
            "do_not_depend_until_use_case_cleared",
        ],
        "security_status": "NOT_ASSESSED",
        "maintenance_status": "UNKNOWN",
        "purpose": (
            "T2 research-only candidate for vectorized performance benchmarking — blocked "
            "from dependency until legal review of Commons Clause for commercial/production "
            "architecture."
        ),
        "capabilities": [
            "vectorized_backtesting",
            "large_scale_parameter_sweeps",
            "numpy_numba_performance",
        ],
        "integration_role": "RESEARCH_ENGINE",
        "trust_tier": "T2",
        "allowed_surfaces": [
            "oss_lab/adapters/vectorbt",
            "oss_lab/evidence",
            "results/oss_lab",
        ],
        "forbidden_surfaces": [
            "configs/production",
            "src/core",
            "src/governance",
            "src/runtime",
        ],
        "input_contract": "oss_lab/contracts/dataset_manifest.py",
        "output_contract": "oss_lab/contracts/trade_record.py#BenchmarkTradeRecord",
        "adapter": "oss_lab/adapters/vectorbt",
        "tests": [],
        "certification_status": "NOT_STARTED",
        "provenance": {
            "discovered_utc": "2026-08-12T18:00:00Z",
            "discovered_by": "oss_monitor_scan",
            "sources": [
                "https://vectorbt.dev/",
                "user_oss_monitor_brief",
            ],
        },
        "known_risks": [
            "commons_clause_commercial_restriction",
            "license_not_simple_oss_assumption",
            "not_a_priority_this_week",
        ],
        "decision": "DEFERRED",
        "decision_reason": (
            "Interesting for raw speed, but Apache-2.0 + Commons Clause requires legal "
            "review before any dependency in commercial/production architecture. Not on "
            "this-week evaluation critical path."
        ),
        "lifecycle_status": "DEFERRED",
        "notes": [
            "Do not pip install into production or lab venv until LEGAL_REVIEW_REQUIRED cleared.",
            "Verify authoritative upstream LICENSE for any pin before use.",
        ],
    },
    {
        "oss_id": "OSS-RIG-METHOD",
        "name": "Repository Intelligence Graph (RIG) methodology",
        "repository": "https://arxiv.org/abs/2601.10112",
        "version": "paper_2026",
        "commit_or_tag": "arXiv:2601.10112",
        "license": "NOT_APPLICABLE_PAPER",
        "license_obligations": [
            "cite_if_reused",
            "reproduce_before_claiming_transfer",
        ],
        "security_status": "NOT_ASSESSED",
        "maintenance_status": "UNKNOWN",
        "purpose": (
            "T0 reference methodology: deterministic evidence-backed repository architecture "
            "graph for LLM assistants. Not a software dependency — architecture input for "
            "Semantic OS + repo-intel benchmarks."
        ),
        "capabilities": [
            "deterministic_repository_graph_methodology",
            "llm_friendly_structural_view",
            "agent_accuracy_latency_benchmark_protocol",
        ],
        "integration_role": "REFERENCE_ONLY",
        "trust_tier": "T0",
        "allowed_surfaces": [
            "oss_lab/governance",
            "docs/governance",
            "oss_lab/scenarios",
        ],
        "forbidden_surfaces": [
            "src/core",
            "configs/production",
            "src/governance/promotion_manager.py",
        ],
        "input_contract": "build_test_package_artifacts",
        "output_contract": "methodology_only_no_runtime_adapter",
        "adapter": "NOT_BUILT",
        "tests": [],
        "certification_status": "NOT_STARTED",
        "provenance": {
            "discovered_utc": "2026-08-12T18:00:00Z",
            "discovered_by": "oss_monitor_scan",
            "sources": [
                "https://arxiv.org/abs/2601.10112",
                "user_oss_monitor_brief",
            ],
        },
        "known_risks": [
            "published_accuracy_and_time_gains_are_not_tradelatest_evidence",
            "transfer_to_this_repo_unproven",
        ],
        "decision": "REFERENCE_ONLY",
        "decision_reason": (
            "Highly aligned research methodology for Semantic OS direction. Use as "
            "benchmark protocol input; do not treat paper numbers as Tradelatest ROI "
            "until reproduced."
        ),
        "lifecycle_status": "REFERENCE_ONLY",
        "notes": [
            "Reproduce agent structural Q&A accuracy/latency on Tradelatest before any finding.",
            "Complements Codebase-Memory/Infigraph evaluation design.",
        ],
    },
]

for rec in new_records:
    if rec["oss_id"] not in existing:
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print("added", rec["oss_id"])
    else:
        print("skip", rec["oss_id"])
