"""
Build complete consolidated markdown documents by concatenating source files.
Replaces "See source" placeholders with actual verbatim content.
"""
import os

BASE = "d:\\Tradelatest"
OUT = os.path.join(BASE, "docs", "consolidated")

def read_file(path):
    path = os.path.join(BASE, path)
    if not os.path.exists(path):
        return f"\n**ERROR: File not found: {path}**\n"
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def write_consolidated(filename, header, source_sections):
    """Write a consolidated doc with header followed by each source section."""
    lines = [header, ""]
    for section_label, source_path in source_sections:
        content = read_file(source_path)
        lines.append(f"---\n## SOURCE FILE: {source_path}\n")
        lines.append(content)
    full = "\n".join(lines)
    outpath = os.path.join(OUT, filename)
    with open(outpath, "w", encoding="utf-8") as f:
        f.write(full)
    print(f"Written {len(full)} bytes to {outpath}")

def main():
    header_boilerplate = """# Consolidated Document — Full Verbatim Content

> **Purpose:** This document contains raw verbatim content from all source files.
> No content has been summarized or modified. Each source file is clearly separated.
> Created: 2026-06-11

---
"""

    # --- DOC 1: SYSTEM_ARCHITECTURE.md ---
    arch_sources = [
        ("ARCHITECTURE", "docs/ARCHITECTURE.md"),
        ("CONFIG_REFERENCE", "docs/CONFIG_REFERENCE.md"),
        ("SIGNAL_FLOW", "docs/SIGNAL_FLOW.md"),
        ("SCHEMAS", "docs/SCHEMAS.md"),
        ("CODE_MAP", "docs/architecture/code-map.md"),
        ("CODEBASE_STATE_MAP", "docs/architecture/codebase-state-map.md"),
        ("EVENT_TAXONOMY", "docs/architecture/event-taxonomy.md"),
        ("SERVICE_BOUNDARY_MAP", "docs/architecture/service-boundary-map.md"),
        ("ENTRY_EXIT_MAP", "docs/architecture/entry-exit-map.md"),
        ("LLM_GOVERNANCE", "docs/architecture/llm-governance-layer.md"),
        ("GOAL", "docs/architecture/goal.md"),
        ("REPLAY_GOVERNANCE", "docs/architecture/replay-governance.md"),
        ("PIPELINE_LINKAGE", "docs/architecture/pipeline-linkage-spine-as-hypothesis.md"),
        ("CONTROL_PLANE_ARCH", "docs/control_plane/ARCHITECTURE.md"),
        ("CRT_SPINE", "docs/topics/crt-spine.md"),
    ]
    header1 = "# SYSTEM_ARCHITECTURE.md — Full Verbatim Content\n\n" + header_boilerplate
    write_consolidated("SYSTEM_ARCHITECTURE.md", header1, arch_sources)
    
    # --- DOC 2: SYSTEM_OPERATIONS.md ---
    ops_sources = [
        ("CURRENT_STATE", "docs/operations/CURRENT_STATE.md"),
        ("DEPENDENCY_GRAPH", "docs/operations/DEPENDENCY_GRAPH.md"),
        ("KNOWN_ILLUSIONS", "docs/operations/KNOWN_ILLUSIONS.md"),
        ("TRUST_TIER_INDEX", "docs/operations/TRUST_TIER_INDEX.md"),
        ("CONVENTIONS", "docs/CONVENTIONS.md"),
        ("CLI_MATRIX", "docs/CLI_MATRIX.md"),
        ("CURRENT_FINDINGS", "docs/current-findings.md"),
        ("HIDDEN_WIRING_AUDIT", "reports/hidden_wiring_audit.md"),
        ("RUNTIME_CONFIG_REACH", "reports/runtime_config_reachability.md"),
    ]
    header2 = "# SYSTEM_OPERATIONS.md — Full Verbatim Content\n\n" + header_boilerplate
    write_consolidated("SYSTEM_OPERATIONS.md", header2, ops_sources)
    
    # --- DOC 3: EXECUTION_STRATEGIES.md ---
    strategy_sources = [
        ("STRATEGIES", "docs/STRATEGIES.md"),
        ("GOVERNANCE", "docs/GOVERNANCE.md"),
        ("EXECUTION_LOOP", "docs/topics/execution-loop.md"),
        ("FUSION_DECISION", "docs/topics/fusion-decision.md"),
        ("EXECUTION_PLANNING", "docs/topics/execution-planning.md"),
        ("ULTRON_RISK_GATE", "docs/topics/ultron-risk-gate.md"),
        ("LIVE_EXECUTION", "docs/topics/live-execution.md"),
        ("SCORING_ENGINES", "docs/topics/scoring-engines.md"),
        ("REGIME_CLASSIFIER", "docs/topics/regime-classifier.md"),
        ("PORTFOLIO_ALLOCATION", "docs/topics/portfolio-allocation.md"),
        ("PROMOTION_GOVERNANCE", "docs/topics/promotion-governance.md"),
    ]
    header3 = "# EXECUTION_STRATEGIES.md — Full Verbatim Content\n\n" + header_boilerplate
    write_consolidated("EXECUTION_STRATEGIES.md", header3, strategy_sources)
    
    # --- DOC 4: ANALYSIS_AND_FORENSICS.md ---
    analysis_dir = os.path.join(BASE, "docs", "analysis")
    analysis_files = sorted([
        f for f in os.listdir(analysis_dir)
        if f.endswith(".md") and f != "README.md"
    ])
    analysis_sources = []
    for f in analysis_files:
        analysis_sources.append((f.replace(".md","").upper(), f"docs/analysis/{f}"))
    # Add handover and timeline
    analysis_sources.append(("JARVIS_HANDOVER", "docs/handover/JARVIS_CRT_HANDOVER_v3.md"))
    analysis_sources.append(("TIMELINE", "docs/timeline.md"))
    header4 = "# ANALYSIS_AND_FORENSICS.md — Full Verbatim Content\n\n" + header_boilerplate
    write_consolidated("ANALYSIS_AND_FORENSICS.md", header4, analysis_sources)
    
    # --- DOC 5: REFERENCE_AND_GUIDES.md ---
    ref_sources = [
        ("TESTING", "docs/TESTING.md"),
        ("AGENT_REFERENCE", "docs/AGENT_REFERENCE.md"),
        ("CLAUDE", "CLAUDE.md"),
        ("README", "README.md"),
        ("AGENTS", "AGENTS.md"),
        ("ASSISTANT_PROJECT", "assistant_project.md"),
        ("INTENT_ROUTER_PROMPT", "src/agent/prompts/intent_router.md"),
        ("SYSTEM_COPILOT_PROMPT", "src/agent/prompts/system_copilot.md"),
        ("SYSTEM_GOVERNANCE_PROMPT", "src/agent/prompts/system_governance.md"),
        ("SYSTEM_PIPELINE_PROMPT", "src/agent/prompts/system_pipeline.md"),
        ("TOOL_SCHEMA_PROMPT", "src/agent/prompts/tool_schema.md"),
        ("TRAINING_REF", "docs/reference/training.md"),
        ("BASH_CATALOG", "docs/reference/bash-command-catalog.md"),
        ("USER_PROGRESS", "docs/governance/user-progress-registry.md"),
        ("TRAINING_CAL", "docs/topics/training-calibration.md"),
        ("WEIGHT_SEARCH", "docs/topics/weight-search.md"),
        ("FEATURE_SCHEMA", "docs/topics/feature-schema.md"),
    ]
    # Add implementation plans
    impl_dir = os.path.join(BASE, "docs", "implementation_plan")
    if os.path.exists(impl_dir):
        impl_files = sorted([f for f in os.listdir(impl_dir) if f.endswith(".md")])
        for f in impl_files:
            ref_sources.append((f.replace(".md","").upper()[:20], f"docs/implementation_plan/{f}"))
    
    header5 = "# REFERENCE_AND_GUIDES.md — Full Verbatim Content\n\n" + header_boilerplate
    write_consolidated("REFERENCE_AND_GUIDES.md", header5, ref_sources)

if __name__ == "__main__":
    main()