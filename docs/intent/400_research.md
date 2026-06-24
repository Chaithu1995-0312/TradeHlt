# Domain Contract: Research

## Purpose
Discover, measure, and qualify market behaviors through an infrastructure that is isolated from the production trading spine. Research produces edge reports and findings — never config changes or live trades.

## Why does this exist?
The user thought: *"I need to experiment freely without any risk to the live trading path."* Research and production have different truth standards and must not share infrastructure.

**Evidence:** assistant_project.md:1902–1904 (isolation lint clean) — Confidence: Certain

## Authority
- **Owns:** Edge Discovery (hypothesis testing, qualification, forensics, process characterization).
- **Decides:** Whether a behavior qualifies (PROMOTE/REJECT/INSUFFICIENT) under the research truth standard.
- **Must NOT:** Import from engine_runner, fusion_engine, decision_engine, execution_planner, promotion_manager, or config_validator.
- **Must NOT:** Write to configs/production/* or modify ACTIVE_VERSION.
- **Must NOT:** Modify the spine, production configs, or promotion path.

## Must (Required Behaviors)
1. Every experiment must use a consistent truth standard (intrabar_fixed exits, flat 12bps cost).
2. Every experiment must produce a deterministic, byte-identical edge report across runs.
3. Every experiment must be reproducible from a config file (research_config.json) + CSV data.
4. M4 QualificationGate must be applied before any behavior is deemed qualified: gate 7 ordered checks (sample → expectancy → PF → beats control → OOS retention → permutation → BH correction).
5. Findings from research must be filed in current-findings.md per the Findings Mandate.

## Must Never (Forbidden Behaviors)
1. Must NEVER import from the forbidden list (engine_runner, promotion_manager, config_validator).
2. Must NEVER write to configs/production/ — research is measurement-only.
3. Must NEVER modify the production spine.
4. Must NEVER override the qualification gate's REJECT/INSUFFICIENT verdict.
5. Must NEVER claim edge without passing M4 (qualification gate) on the unified truth standard.

## Failure Modes
| Failure | Detection | Severity |
|---------|-----------|----------|
| Forbidden import (engine_runner etc.) | Lint check in research isolation test | HIGH |
| Non-reproducible result (wall-clock dependency) | Determinism gate (byte-identical x2) | HIGH |
| Research result from non-standard truth | TRUTH_STANDARD_VERSION not matching | HIGH |
| False discovery (luck + multiple comparisons) | M4 qualification gate + BH correction | MEDIUM (gate catches it) |
| Hypothesis space exhausted without documenting | Not automatically caught | MEDIUM |

## Economic Meaning
The research program produced the most important findings in the repository: that under honest exits + cost, no tested behavior (direction, conditional, selection, exit geometry) produces positive expectancy on the crypto-major M15 universe. These null findings are HIGH knowledge-ROI — they prevent wasted parameter archaeology.

**Evidence:** F-019, F-020, F-021, F-025 — Confidence: Certain

## Unknowns
- Whether the null findings generalize to FX, equities, or other timeframes.
- Whether a genuinely new ontology (volatility targeting, positional trading) would change the result.
- Whether the flat 12bps cost model vs. the seeded-slippage spine model would materially change qualification outcomes.

## Evidence
- assistant_project.md:1902–1904 (isolation) — Confidence: Certain
- assistant_project.md:1936–1937 (determinism) — Confidence: Certain
- assistant_project.md:2014–2018 (B0 reconciliation, multiple truth standards) — Confidence: Certain
- F-019, F-020, F-021, F-025 (the four falsifications) — Confidence: Likely