# Full Build Specification: Domain-First Trading Architecture

> **Purpose:** This document is the complete, unredacted specification for transforming
> the Tradelatest codebase from a strategy-centric monolithic system to a domain-first,
> evidence-linked, n8n-orchestrated trading architecture.
>
> **How to use:** Give this entire document to Claude LLM (or any coding agent). It contains
> every decision, every schema, every risk, and every checklist. The agent must implement
> each story in order, validate each checklist, and log every action.
>
> **Source:** Full conversation 2026-06-15 (Plan Mode). Every question, answer, and decision
> captured below.
>
> **Status:** Specification complete. Ready for implementation.
> **Total effort:** ~220 hours across 44 stories, 10 epics
> **New code:** ~4,640 lines across 38 new files, 32 modified files
> **Architecture risk:** 2 high-risk stories (5.4, 8.1) — both behind feature flags

---

# Table of Contents

1. [Conviction Statement](#1-conviction-statement)
2. [The Architecture Inversion Problem](#2-the-architecture-inversion-problem)
3. [Target Architecture](#3-target-architecture)
4. [Foundational Documents Already Written](#4-foundational-documents-already-written)
5. [Codebase Readiness Audit](#5-codebase-readiness-audit)
6. [Implementation Ritual](#6-implementation-ritual)
7. [Epic 1: Repair the Spine](#7-epic-1-repair-the-spine)
8. [Epic 2: Wire or Remove Dead Config](#8-epic-2-wire-or-remove-dead-config)
9. [Epic 3: Framework Registry + Findings Applier](#9-epic-3-framework-registry--findings-applier)
10. [Epic 4: Domain Layer Extraction](#10-epic-4-domain-layer-extraction)
11. [Epic 5: Style Layer + Strategy Reorganization](#11-epic-5-style-layer--strategy-reorganization)
12. [Epic 6: n8n Integration](#12-epic-6-n8n-integration)
13. [Epic 7: Claude Gate Integration](#13-epic-7-claude-gate-integration)
14. [Epic 8: Enable UltronRiskGate + Wire Portfolio](#14-epic-8-enable-ultronriskgate--wire-portfolio)
15. [Epic 9: Documentation + Validation](#15-epic-9-documentation--validation)
16. [Epic 10: Findings Integration](#16-epic-10-findings-integration)
17. [JSONL Registry Schema Reference](#17-jsonl-registry-schema-reference)
18. [Claude Gate Prompt Templates](#18-claude-gate-prompt-templates)
19. [Troubleshooting Guide](#19-troubleshooting-guide)
20. [Audit Trail Template](#20-audit-trail-template)
21. [Implementation Order (Critical Path)](#21-implementation-order-critical-path)

---

# 1. Conviction Statement

**The goal:** Transform the codebase from a strategy-centric monolithic system to a domain-first,
evidence-linked trading architecture where every component is documented, classified, validated,
and traceable. The registry drives execution. Findings steer behavior. n8n orchestrates workflows.
Claude LLM tweaks only when config gates trigger.

**Why this matters (from the user's own words):**
- "Different markets require different assumptions. Strategies are domain-dependent. AI should sit
  above the domain and strategy layers, not define them."
- "Your current architecture may be too strategy-centric."
- "Trading systems are usually overfit because they start with indicators. Robust systems start
  with domain → style → strategy → implementation."
- Research findings F-019 through F-028 show the current ontology has been empirically falsified
  for crypto majors under realistic costs. The system works correctly but the *domain assumptions*
  were wrong.

**What success looks like:**
1. Registry coverage = 100% — every production module in `src/` has a registry entry
2. Gap audit = 0 P0 items — no architecture inversions (CRT as mandatory engine is P0)
3. Validation passes — evidence paths exist, findings are linked, no dangling references
4. 1208/1208 tests passing (23 failures fixed)
5. n8n orchestrates the full pipeline: data → tune → validate → Claude gate → promote → live
6. UltronRiskGate enabled and non-bypassable

**The ritual:**
```
Document → JSONL → Checklist → Logs → Validation → Next Phase
```

---

# 2. The Architecture Inversion Problem

## 2.1 Wrong Order (Current Codebase)

The current architecture builds the system around tools, not around the problem:

```
CRT Engine → Gaussian → Zone Gate → RR Engine → everything else
```

These 4 engines are treated as the **foundation** (mandatory, `EXPECTED_ENGINES` hardcoded).
Everything else is bolted on top.

**Consequences (proven by research):**
- F-019: No edge on crypto majors under realistic costs
- F-020: No candle-conditional directional pocket on crypto majors
- F-021: Spine RETEST selection = session filter only (no score/zone skill)
- F-025: Exit/cost is a risk lever, NOT expectancy
- F-026: CRT retest adds no forward asymmetry beyond sweep
- F-027: Coarser timeframes do NOT rescue the directional edge
- F-028: First real interpreter (P&F) carries NO standalone edge

The architecture *faithfully implements* the chosen market ontology — but that ontology has been
empirically falsified for crypto majors. This is not a code bug. It's an architecture inversion.

## 2.2 Correct Order (Target)

```
Level 0: Universal Trading Kernel       (domain-independent plumbing)
Level 1: Market Domain Layer            (crypto / forex / equities / futures / options)
Level 2: Trading Style Layer            (trend / reversion / momentum / reaction / stat-arb)
Level 3: Strategy Layer                 (concrete rule sets per style)
Level 4: Intelligence / AI Layer        (regime / drift — advisory only)
Level 5: Risk Layer                     (pre-trade, in-trade, portfolio)
Level 6: Execution Layer                (order dispatch, venue routing, slippage model)
```

**CRT/Gaussian/Zone/RR are no longer mandatory engines.**
They become strategy plugins under specific styles. CRT becomes a strategy under ReactionBased
style. Gaussian becomes a fused signal (if useful) or a strategy plugin.

## 2.3 The User's Framework (from conversation)

```
Market Domain
    ↓
Trading Style
    ↓
Strategy
    ↓
Implementation
```

This is the one-sentence version of the full 6-level hierarchy. Every architecture decision
must pass this test: "Does this serve the domain first, or the strategy first?"

---

# 3. Target Architecture

## 3.1 Complete End-to-End Flow

```
n8n (Docker, localhost:5678)
    │
    ├── Trigger: Scheduled (daily 02:00 UTC) / Webhook (user click)
    │
    ├── [Stage 1: Data Prep]           HTTP POST → control_plane:/api/run-stage
    ├── [Stage 2: Tuning]              Parallel 4 instruments
    ├── [Stage 3: Claude Gate]         HTTP POST → Claude API (Anthropic)
    │   ├── Decision: tweak → re-run Stage 2
    │   ├── Decision: promote → Stage 4
    │   └── Decision: escalate → notify user
    ├── [Stage 4: Validate + Promote]
    └── [Stage 5: Live Runner]
    │
    ▼
Control Plane (localhost:8787)
    │
    ├── POST /api/run-stage      → runs script, returns {status, metrics, config}
    ├── POST /api/claude-gate    → calls Anthropic API, returns decision
    ├── GET  /api/registry       → query framework registry
    └── GET  /api/status         → current system state
    │
    ▼
Framework Registry (data/framework_registry.jsonl)
    │
    ├── Query: get_tree("DOMAIN-001")           → full CryptoSpot hierarchy
    ├── Query: find_by_finding("F-026")         → which components affected
    ├── Query: get_orphaned()                   → dead/waste modules
    └── Query: get_active_strategies(domain)    → what to run
    │
    ▼
FindingsApplier (src/governance/findings_applier.py)
    │
    ├── Reads findings from registry records
    ├── Computes effective weights/configs
    │   ├── F-026 → CRT weight: 1.0 → 0.3
    │   ├── F-021 → sessions: all → London/NY/Overlap only
    │   └── F-025 → SL floor: 1x → 2x ATR minimum
    └── Two modes: RESEARCH (shadow) or ACTIVE (live)
    │
    ▼
Engine Spine (reads registry + findings)
    │
    ├── Domain → CryptoSpot
    ├── Styles → [ReactionBased, Breakout, MeanReversion]
    ├── Strategies per style → [CRT, LiquiditySweep, RSI+BB, ...]
    ├── Apply findings → modified weights + restrictions
    └── Run only strategies with weight > 0
    │
    ▼
Risk Layer (non-bypassable)
    │
    ├── PreTradeRiskGate (UltronRiskGate — ENABLED)
    ├── InTradeRisk (breakeven, trailing, time stop)
    └── PortfolioRisk (exposure, concentration, correlation)
    │
    ▼
Execution Layer
    │
    ├── Order dispatch (market/limit/iceberg)
    ├── Slippage model (dynamic, spread-based)
    └── Audit (JSONL per trade)
    │
    ▼
Feedback Loop
    │
    ├── Backtest → metrics
    ├── Metrics → new finding or validate existing
    ├── Finding → registry → findings applier → engine
    └── Loop
```

## 3.2 Key Design Decisions (from conversation)

| Decision | Why | Source |
|----------|-----|--------|
| n8n orchestrates, not Python | Visual workflow, parallel branches, built-in LLM nodes | User: "n8n workflow Claude LLM only tweak required ones" |
| Claude calls ONLY when needed | Avoid unnecessary API costs; Claude is a gate, not the engine | User: "Claude LLM only tweak required ones" |
| 4 parallel branches | Tune 4 instruments (BNB, BTC, ETH, SOL) simultaneously | User: "parallel 4" |
| Local n8n Docker | File-backed, no cloud deps, matches existing architecture | User: "n8n in local" |
| Anthropic API for Claude | Existing GROQ key but user chose Claude | User: "Claude API (Anthropic)" |
| Registry is JSONL | Append-only, evidence-linked, queryable, matches existing JSONL pattern | User: "JSONL advantages — link till evidences, map entire codebase" |
| Findings as directives | Natural language: when to trade, when to risk, when NOT to trade + confidence | User: "share direction of finding in sentence" |
| Findings drive engine behavior | Not just documentation — findings modify configs/weights at runtime | User: "The engine reads the registry and executes what it finds" |
| Document → JSONL → Checklist → Logs → Validation → Next | Never skip a step. Every phase follows this ritual. | User: "Document jsonl checklist logs validation next phase" |
| Control plane stays alongside n8n | n8n doesn't replace existing UI. Both serve different purposes. | User: "sitalong side" |
| Codebase fixes first | 23 failing tests + dead config must be fixed before n8n layer can be trusted | User: "if any bugs or not as intended then results will be not trusted" |

---

# 4. Foundational Documents Already Written

These files exist and are referenced throughout this specification:

| File | Content | Authoritative For |
|------|---------|-------------------|
| `docs/architecture/TRADING_SYSTEM_FRAMEWORK.md` | Complete 6-level hierarchy with ABC contracts, schemas, end-to-end flow | Level definitions, component boundaries |
| `docs/implementation_plan/001_FRAMEWORK_REGISTRY.md` | Original phased plan for registry + gap audit | Milestone structure, file inventory |
| `docs/current-findings.md` | F-001 through F-029 with evidence and confidence | All active findings |
| `docs/STRATEGIES.md` | S01-S10 strategy modules | Strategy descriptions, config mapping |
| `reports/hidden_wiring_audit.md` | 20 dead/orphaned config sections | Everything that needs to be wired or removed |
| `docs/intent/100_execution.md` | Execution domain contract | Must/MustNever requirements for the spine |
| `docs/intent/200_risk.md` | Risk domain contract | Risk gate requirements |
| `CLAUDE.md` | Master context file, session log mandate | Operating conventions |
| `docs/architecture/signal-flow.md` | End-to-end candle→order flow | Pipeline order, module boundaries |

---

# 5. Codebase Readiness Audit

## 5.1 Test Results (from `pytest_output.txt`)

**1231 collected, 1188 passed, 23 failed, 18 skipped, 2 xfailed**

### Failed Tests Detail

```
FAILED tests/features/test_feature_schema_registry.py::test_unregistered_fail_open
    → Feature schema registry's unregistered-feature fallback doesn't match test.
    → Files: 1 (test or src/features/)
    → Fix: ±5 lines, 0.5h

FAILED tests/replay/test_replay_memory_engine.py::test_cluster_stats_built
FAILED tests/replay/test_replay_memory_engine.py::test_decay_weighting
    → Replay memory engine cluster stats and decay weighting broken.
    → Sidecar only (F-012: zero spine consumption).
    → Files: 1 (src/replay/)
    → Fix: ±15 lines, 2h

FAILED tests/test_engine_runner_dual_gate.py::test_dual_gate_trend_selects_breakout
FAILED tests/test_engine_runner_dual_gate.py::test_dual_gate_range_selects_trap
FAILED tests/test_engine_runner_dual_gate.py::test_dual_gate_neutral_low_confidence_rejects
FAILED tests/test_engine_runner_dual_gate.py::test_layered_flow_fusion_runs_before_dual_veto
    → Dual gate mode selection logic broken.
    → Secondary path behind fusion_use_evaluate flag.
    → Files: 1 (src/core/engine_runner.py)
    → Fix: ±15 lines, 3h

FAILED tests/test_engine_runner_rr_fusion.py::test_rr_fusion_applies_score_before_fusion
FAILED tests/test_engine_runner_rr_fusion.py::test_rr_fusion_failure_falls_back_to_base_rr
FAILED tests/test_engine_runner_rr_fusion.py::test_fusion_compare_mode_records_evaluate_shadow
FAILED tests/test_engine_runner_rr_fusion.py::test_fusion_use_evaluate_overrides_final_score
    → RR fusion scoring pipeline bug.
    → Files: 1 (src/config_layer/rr/ or src/core/fusion_engine.py)
    → Fix: ±20 lines, 3h

FAILED tests/test_gaussian_impl_switch.py::test_engine_runner_ml_impl
    → Gaussian engine switching regression.
    → Files: 1 (src/engines/ or engine_runner.py)
    → Fix: ±10 lines, 2h

FAILED tests/test_llm_connectivity.py::TestLlmScore::test_unparseable_output_returns_one
FAILED tests/test_llm_connectivity.py::TestLlmScore::test_timeout_returns_one
FAILED tests/test_llm_connectivity.py::TestLlmScore::test_url_error_returns_one
FAILED tests/test_llm_connectivity.py::TestLlmScore::test_generic_exception_returns_one
FAILED tests/test_llm_connectivity.py::TestLlmScore::test_failopen_when_both_backends_down
FAILED tests/test_llm_connectivity.py::TestGroqScore::test_unparseable_returns_one
FAILED tests/test_llm_connectivity.py::TestGroqScore::test_unavailable_returns_one_empty
FAILED tests/test_llm_connectivity.py::TestGroqScore::test_request_error_returns_one
FAILED tests/test_llm_connectivity.py::TestLlmScoreSafe::test_server_down_returns_one_fail_open
FAILED tests/test_llm_connectivity.py::TestLlmScoreSafe::test_timeout_returns_one_fail_open
FAILED tests/test_llm_connectivity.py::TestLlmScoreBatch::test_server_down_safe_mode
    → 10 failures. Fallback returns 0.5 but tests expect 1.0.
    → Code was changed (fallback 1.0→0.5) but tests weren't updated.
    → This is a contract ambiguity, not a runtime bug.
    → Files: 1 (src/engines/llm_inference_client.py or tests/)
    → Fix: ±10 lines, 1h
```

**Total to fix:** 23 failures, ±75 lines across 6 files, ~11.5 hours.

## 5.2 Known Architecture Issues (from reports)

### Dead/Unwired Config (must fix before n8n can be trusted)

| Config Section | Problem | Impact | Found In |
|----------------|---------|--------|----------|
| `capital_management` | COMPLETELY UNWIRED. Daily loss limit, max risk per trade, kill-switch thresholds never read | Tuning kill-switch params has zero effect | hidden_wiring_audit.md #1 |
| `data_ingestion` | References nonexistent PostgreSQL. Codebase has NO database | Misleads developers | hidden_wiring_audit.md #2 |
| `gate_intelligence` | No consumer in the spine. Designed as signal filter but bypassed | Tuning gate weights does nothing | hidden_wiring_audit.md #3 |
| `sl_tp_comparison` | Self-declares dead ("used ONLY by SLTPComparator, never in live path") | Analytical only, but pollutes config | hidden_wiring_audit.md #4 |
| `strategy_engine.s01..s10` | Advisory only — consensus may not be invoked (65% probability) | Tuning 10 strategies may be decorative | hidden_wiring_audit.md #5 |
| `regime_fusion_weights` | Exists in config but NEVER read by FusionEngine | Regime-adaptive weighting has zero effect | hidden_wiring_audit.md #6 |
| `PROMOTION_MARGIN=2%` | Hardcoded in model_registry.py, not configurable | Can't tune without editing Python | hidden_wiring_audit.md #7 |
| `ultron_gate_enabled: false` | Risk gate disabled in active production config | Capital protection bypassed | Active config line 66 |

### Active Findings (F-001 to F-029, from `docs/current-findings.md`)

| Finding | Conclusion | Affects Building n8n? | Action Required |
|---------|-----------|----------------------|-----------------|
| F-001 | Intelligence is NOT the binding constraint | Informational | None |
| F-002 | Edge is in decision PROCESS, not feature→outcome map | Design validation | Ensure findings applier doesn't optimize wrong things |
| F-004 | BitNet is LIVE hard-reject gate (score < 0.55) | Architecture | BitNet stays as AI advisory layer |
| F-005 | TradeNet v2 built but unwired | Waste tracking | Registry will show as orphaned |
| F-006 | config_integrity is real but ORPHANED | Must fix | Wire or remove |
| F-008 | Concept drift DETECTED but NOT acted on | Must fix | Wire drift → action |
| F-010 | Live PnL UNVERIFIED | Must fix | Execution quality model needed |
| F-012 | ReplayMemory/CognitiveBus/Cluster/HMF sidecar-only | Informational | Registry marks as sidecar |
| F-013 | PortfolioAllocator built but ORPHANED | Must fix | Wire into spine (Story 8.2) |
| F-016 | Active config = v2_multi_2026_04 (patch) | Version truth | Ensure registry references this version |
| F-019 | No edge on crypto majors under cost | Business impact | n8n may find no edge to promote |
| F-021 | RETEST selection = session filter only | Strategy guidance | CRT deweight, sessions restricted |
| F-025 | Exit/cost is risk lever, not expectancy | Risk guidance | SL floor = 2x ATR |
| F-026 | CRT retest adds NO forward asymmetry | Strategy guidance | CRT weight reduced to 0.3 |

## 5.3 Existing Components Ready for n8n

These scripts already work as CLI commands and can be called by n8n immediately:

| Component | Path | n8n Call Method | Args |
|-----------|------|----------------|------|
| Data Prep | `scripts/data/prepare_data.py` | `python scripts/data/prepare_data.py --source binance --instrument BNBUSDT` | --source, --files, --instrument, --output, --already-m15, --validate-only |
| Unified Data Builder | `scripts/data/unified_data_builder.py` | `python scripts/data/unified_data_builder.py EURUSD GBPUSD` | instruments positional, --data-dir, --output-dir, --validate-only, --dry-run |
| Auto Tuner Multi | `scripts/training/auto_tuner_multi.py` | `python scripts/training/auto_tuner_multi.py --instrument BNBUSDT --n-iter 100` | --csv, --instrument, --data-dir, --instruments, --output-dir, --n-iter, --seed, --workers, --train-split, --no-llm |
| Auto Tuner | `scripts/training/auto_tuner.py` | `python scripts/training/auto_tuner.py --instrument BNBUSDT --n-iter 100` | --csv, --instrument, --data-dir, --instruments, --output-dir, --n-iter, --seed, --resume, --multi, --verbose |
| Config Validator | `src/config_layer/config_validator.py` | `python src/config_layer/config_validator.py validate-prod` | subcommand positional, --data-dir, --version, --output |
| Promotion Manager | `src/governance/promotion_manager.py` | `python src/governance/promotion_manager.py promote --checkpoint ...` | promote/from-report/list/load subcommands |
| Backtest v2 | `src/runtime/backtest_v2.py` | `python src/runtime/backtest_v2.py --csv data/BNBUSDT_M15.csv` | --csv, --config, --output-dir |
| Fetch Crypto | `scripts/data/fetch_crypto_ccxt.py` | `python scripts/data/fetch_crypto_ccxt.py --instrument BNBUSDT` | --all, --instrument, --start, --end, --append |
| Fetch Forex | `scripts/data/fetch_forex_yfinance.py` | `python scripts/data/fetch_forex_yfinance.py --instrument AUDUSD` | --all, --instrument, --start, --end, --append |
| Opportunity Scanner | `scripts/auto_train_from_opportunities.py` | `python scripts/auto_train_from_opportunities.py` | various args |
| Live Engine Hook | `src/runtime/live_engine_hook.py` | `python src/runtime/live_engine_hook.py` | various args |

---

# 6. Implementation Ritual

**Every story follows this exact sequence. Do not skip steps.**

```
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: DOCUMENT                                             │
│   Write the design/spec as a doc or update existing doc.     │
│   Include: purpose, schema, contract, failure modes.         │
│   Output: docs/.../*.md                                      │
├─────────────────────────────────────────────────────────────┤
│ STEP 2: JSONL                                                 │
│   Update data/framework_registry.jsonl with the new          │
│   component. Include evidence links (file:line) and          │
│   parent/children references.                                │
│   Output: data/framework_registry.jsonl (+1 line)            │
├─────────────────────────────────────────────────────────────┤
│ STEP 3: IMPLEMENT                                             │
│   Write and commit the code.                                 │
│   Follow the contracts from the framework document.          │
│   Add feature flags for risky changes.                       │
│   Output: code changes                                       │
├─────────────────────────────────────────────────────────────┤
│ STEP 4: CHECKLIST                                             │
│   Run through the story's checklist. Mark each item.         │
│   Do not proceed until all checkboxes are ✓.                 │
│   Output: checklist in story doc                             │
├─────────────────────────────────────────────────────────────┤
│ STEP 5: LOGS                                                  │
│   Append session log entry to assistant_project.md.          │
│   Include: what was built, what changed, what risks remain.  │
│   Output: assistant_project.md (+1 entry)                    │
├─────────────────────────────────────────────────────────────┤
│ STEP 6: VALIDATION                                            │
│   Run all affected tests. Run full regression.               │
│   For risky changes: byte-identity backtest verification.    │
│   Output: test results + verification report                 │
├─────────────────────────────────────────────────────────────┤
│ STEP 7: NEXT                                                  │
│   Only proceed to next story when validation passes.         │
│   If validation fails: fix → re-validate → then proceed.    │
│   Output: "Ready for story N+1"                              │
└─────────────────────────────────────────────────────────────┘
```

---

# 7. Epic 1: Repair the Spine

**Goal:** Fix all 23 failing tests so the codebase produces trustworthy results.
**Total:** 6 stories, 6 files modified, ±75 lines, 11.5 hours.
**Prerequisite for:** All other epics. Nothing gets built on a broken foundation.

## Story 1.1: Fix LLM Connectivity Test Contract

**Files:** `src/engines/llm_inference_client.py` or `tests/test_llm_connectivity.py`
**Lines:** ±10 lines
**Time:** 1 hour
**Confidence:** 95%

**Problem:** 10 tests fail because fallback returns 0.5 but tests expect 1.0. The code was changed
(fallback from 1.0 to 0.5) but tests weren't updated.

**Decision needed:** Is the correct fallback behavior 0.5 (neutral abstention) or 1.0 (pass)?
- Look at `src/engines/llm_inference_client.py` and the `_groq_score` / `llm_score` functions.
- The log says: "all backends failed... Returning 0.5 (neutral abstention)."
- If 0.5 is intentional (neutral = doesn't influence fusion), update tests to expect 0.5.
- If 1.0 is required (fail-open = pass), update code to return 1.0.

**Checklist:**
- [ ] Determine correct fallback value (check with user or FusionEngine contract)
- [ ] Update either code or tests to match
- [ ] All 10 LLM connectivity tests pass
- [ ] Regression: remaining 1200+ tests pass

**Evidence to update in registry:**
- `src/engines/llm_inference_client.py` — update evidence line reference if code changed

---

## Story 1.2: Fix Dual Gate Engine Runner

**Files:** `src/core/engine_runner.py` (dual gate section, ~20 lines)
**Lines:** ±15 lines
**Time:** 3 hours
**Confidence:** 70%

**Problem:** `test_engine_runner_dual_gate.py` has 4 failures in trend/range selection and fusion flow.
The dual gate (regime-aware strategy selection) has a logic bug.

**Root cause investigation:**
1. Read the failing test assertions — what exact value does each test expect vs receive?
2. Trace `engine_runner.py` dual gate flow: where does it decide trend vs range vs neutral?
3. Is `fusion_use_evaluate` flag affecting this path? (It defaults to FALSE in config)
4. Are the regime labels from the regime classifier matching the test expectations?

**Checklist:**
- [ ] Identify root cause of each failure
- [ ] Fix dual gate logic
- [ ] All 4 dual gate tests pass
- [ ] Dual gate runs behind feature flag (`fusion_use_evaluate` or new flag)
- [ ] Byte-identity backtest verified (BNBUSDT + SOLUSDT) — should be unchanged since dual gate is secondary path

**Critical constraint:** The dual gate is a secondary path. The primary path (fusion_compare)
must NOT be affected by this fix. If the fix requires changing the primary path, stop and escalate.

---

## Story 1.3: Fix RR Fusion Scoring

**Files:** `src/config_layer/rr/rr_fusion.py` or `src/core/fusion_engine.py`
**Lines:** ±20 lines
**Time:** 3 hours
**Confidence:** 65%

**Problem:** `test_engine_runner_rr_fusion.py` has 4 failures in score application and fallback.

**Root cause investigation:**
1. The tests cover: score-before-fusion, fallback-to-base-rr, compare-mode, evaluate-mode
2. Find which method is producing wrong scores
3. Is `rr_fusion.enabled` flag affecting this? (Current config: `"enabled": true`)
4. Is the issue in `RREngine` or `RRFusionLayer`?

**Checklist:**
- [ ] Identify root cause
- [ ] Fix RR fusion scoring pipeline
- [ ] All 4 RR fusion tests pass
- [ ] Byte-identity backtest verified (RR fusion affects final scores)

**Risk:** If RR fusion is fundamentally broken (not just a logic bug), the fix may require larger
refactor. In that case: disable RR fusion (`rr_fusion.enabled: false`), fix the 4 tests to pass
with disabled fusion, and open a separate tech debt story.

---

## Story 1.4: Fix Gaussian Implementation Switch

**Files:** `src/engines/ml_gaussian_engine.py` or `src/core/engine_runner.py` (switch logic)
**Lines:** ±10 lines
**Time:** 2 hours
**Confidence:** 80%

**Problem:** `test_gaussian_impl_switch.py` fails — ML vs heuristic Gaussian engine switch broken.

**Root cause investigation:**
1. The switch is controlled by `gaussian_impl` config key ("ml" vs "heuristic")
2. Find where the switch is evaluated in `engine_runner.py` or Gaussian engine loader
3. Is it a renamed method? Changed import? Wrong conditional?

**Checklist:**
- [ ] Identify root cause
- [ ] Fix Gaussian implementation switch
- [ ] Test passes for both "ml" and "heuristic" modes
- [ ] Byte-identity backtest verified

---

## Story 1.5: Fix Replay Memory Engine Failures

**Files:** `src/replay/replay_memory_engine.py`
**Lines:** ±15 lines
**Time:** 2 hours
**Confidence:** 90%

**Problem:** `test_cluster_stats_built` and `test_decay_weighting` fail. Sidecar code (F-012).

**Root cause investigation:**
1. These are sidecar components — zero impact on trading spine
2. Likely a refactoring regression (renamed method or changed return type)
3. Fix is straightforward: align code with test expectations

**Checklist:**
- [ ] Fix `test_cluster_stats_built`
- [ ] Fix `test_decay_weighting`
- [ ] All replay tests pass
- [ ] No spine code touched

---

## Story 1.6: Fix Feature Schema Registry Test

**Files:** `tests/test_feature_schema_registry.py` or `src/features/feature_schema_registry.py`
**Lines:** ±5 lines
**Time:** 0.5 hours
**Confidence:** 95%

**Problem:** `test_unregistered_fail_open` fails. Unregistered-feature fallback doesn't match test.

**Checklist:**
- [ ] Fix assertion or behavior
- [ ] Test passes
- [ ] All feature schema tests pass

---

# 8. Epic 2: Wire or Remove Dead Config

**Goal:** Every config section has a consumer. No decorative config.
**Total:** 6 stories, 10 files (+1 new, +9 modified), +200/-50 lines, 20 hours.
**Prerequisite for:** Registry seeding (Epic 3) — if config is dead, registry entry must say so.

## Story 2.1: Wire `capital_management` into UltronRiskGate

**Files:**
- NEW: `docs/reference/capital_management_schema.md` (+80 lines)
- MODIFIED: `src/core/ultron_risk_gate.py` (+40 lines)
- MODIFIED: `src/config_layer/production_config.py` (+5 lines)

**Lines:** +125, -0
**Time:** 6 hours
**Confidence:** 85%

**What to build:**
1. `capital_management_schema.md` — document every field (total_capital_inr, max_risk_per_trade_pct,
   kill_switch_daily_loss_inr, kill_switch_monthly_drawdown_pct, position_sizing_method)
2. In `UltronRiskGate.evaluate()`, add 3 new checks before the existing 7:
   - Daily loss check: if today's PnL < -max_daily_loss_pct * total_capital → REJECT
   - Monthly drawdown check: if equity curve drawdown > max_monthly_drawdown_pct → REJECT
   - Max risk per trade check: if proposed position risk > max_risk_per_trade_pct → size down
3. `from_prod_config` should read `capital_management` section from production config

**Critical design decision:**
- If `capital_management` keys are missing or zero, what happens?
- Answer: If value is 0 or negative, treat as "no limit" (backward compatible).
- If section is entirely missing, log a warning but don't crash (fail-open, same as existing pattern).

**Checklist:**
- [ ] `capital_management_schema.md` written
- [ ] 3 new checks added to `UltronRiskGate.evaluate()`
- [ ] Missing/zero values treated as "no limit" (backward compatible)
- [ ] Existing UltronRiskGate tests still pass
- [ ] New tests for capital management checks added
- [ ] Byte-identity backtest verified (capital management checks are new, but all values may be zero
      in active config → behavior unchanged)

---

## Story 2.2: Remove `data_ingestion` Config Section

**Files:**
- MODIFIED: `configs/production/v2_multi_2026_04.json` (-25 lines)
- MODIFIED: `docs/reference/config-reference.md` (-1 section)

**Lines:** +0, -30
**Time:** 1 hour
**Confidence:** 95%

**What to do:**
1. Search entire codebase for `data_ingestion` references (config keys, imports, etc.)
2. If NO references found: delete the section from config and config-reference.md
3. If references found: deprecate instead of delete (add `_deprecated: true` to section)

**Checklist:**
- [ ] Searched codebase for `data_ingestion` references
- [ ] If no references: section deleted
- [ ] If references found: section deprecated, not deleted
- [ ] Tests pass (no import regression)

---

## Story 2.3: Wire or Remove `gate_intelligence`

**Files:**
- MODIFIED: `src/core/engine_runner.py` (+30 lines if wired)
- MODIFIED: `configs/production/v2_multi_2026_04.json` (±15 lines)
- MODIFIED: `docs/reference/config-reference.md` (±1 section)

**Lines:** +30/-15 (depending on decision)
**Time:** 4 hours
**Confidence:** 60%

**Decision needed:** Wire as pre-fusion gate, or delete?

**Arguments for delete:**
- 4 weights + threshold with no documented design intent
- Adding a pre-fusion gate changes engine behavior
- Simplest safe option: delete

**Arguments for wire:**
- The config specifies weights for intent, volume, liquidity, structure
- This could be useful as a pre-fusion signal quality filter
- Can be behind feature flag default=OFF

**Recommendation (from conversation):** Delete. The weights have never been tuned. A new
gate with unknown behavior is riskier than no gate. If needed later, the weights are
documented in the registry as "available for future gate."

**Checklist:**
- [ ] Decision made: wire or delete
- [ ] If wired: feature flag default=OFF, new gates added to engine_runner.py
- [ ] If deleted: section removed from config, config-reference.md updated
- [ ] Tests pass
- [ ] Byte-identity backtest verified

---

## Story 2.4: Verify StrategyOrchestrator Invocation

**Files:**
- MODIFIED: `src/core/engine_runner.py` (+15 lines if not wired)
- MODIFIED: `docs/STRATEGIES.md` (+10 lines)

**Lines:** +25
**Time:** 3 hours
**Confidence:** 75%

**What to do:**
1. Trace the live/backtest path: is `StrategyOrchestrator.compute()` called?
   - Search `engine_runner.py` for `strategy_orchestrator` or `strategy_consensus_score`
   - Check if it's behind a flag, or only in live, or only in backtest, or never
2. If NOT called: wire it into `EngineRunner.run()` before fusion. Add a new config key
   `strategy_orchestrator_enabled: true` (default: true) to gate it.
3. Document the invocation condition in `docs/STRATEGIES.md`

**Checklist:**
- [ ] Verified whether StrategyOrchestrator is invoked in active path
- [ ] If not wired: added to engine_runner.py behind feature flag
- [ ] If already wired: documented the invocation condition
- [ ] Tests pass
- [ ] Byte-identity backtest verified (if this changes scores, behavior changes by design)

---

## Story 2.5: Wire `regime_fusion_weights` into FusionEngine

**Files:**
- MODIFIED: `src/core/fusion_engine.py` (+30 lines)
- MODIFIED: `src/config_layer/production_config.py` (+5 lines)

**Lines:** +35
**Time:** 5 hours
**Confidence:** 70%

**What to build:**
1. Read `regime_fusion_weights` section from config in FusionConfig
2. In `FusionEngine.compute()`, after receiving the regime label from RegimeClassifier:
   - Look up the regime in `regime_fusion_weights` (TRENDING/RANGING/VOLATILE/UNKNOWN)
   - Use regime-specific weights instead of flat weights
   - If regime not found in the map → fall back to flat weights (no crash)
3. Behind feature flag `fusion_use_regime_weights: false` (default: false)

**Critical design decision:** Regime labels must be consistent. If the regime classifier
produces "trending" but the config uses "TRENDING" (case mismatch), fall back to flat weights.
Add a test for case-insensitive matching.

**Checklist:**
- [ ] `regime_fusion_weights` read from config
- [ ] Regime-adaptive weight selection in FusionEngine.compute()
- [ ] Feature flag `fusion_use_regime_weights` default=false
- [ ] Case-insensitive regime label matching
- [ ] If weight not found for regime → flat weight fallback
- [ ] Tests pass for both flag=true and flag=false
- [ ] Byte-identity backtest verified (flag=false = current behavior)

---

## Story 2.6: Externalize `PROMOTION_MARGIN` to Config

**Files:**
- MODIFIED: `src/core/model_registry.py` (-5 lines, +5 lines)
- MODIFIED: `configs/production/v2_multi_2026_04.json` (+3 lines)

**Lines:** +3, -5
**Time:** 1 hour
**Confidence:** 95%

**What to do:**
1. Find `PROMOTION_MARGIN = 0.02` in `src/core/model_registry.py`
2. Replace with config read: `get_prod_section("model_registry").get("promotion_margin", 0.02)`
3. Add `"promotion_margin": 0.02` to config under a new `model_registry` section

**Checklist:**
- [ ] Hardcoded constant replaced with config read
- [ ] Config has `promotion_margin` key
- [ ] Default 0.02 preserved (backward compatible)
- [ ] Tests pass

---

# 9. Epic 3: Framework Registry + Findings Applier

**Goal:** Build the queryable, append-only, evidence-linked registry + the findings applier that
drives engine behavior.
**Total:** 6 stories, 10+ new files, +1,595 lines, 41 hours.
**Prerequisite for:** All architecture changes must be registered here first.

## Story 3.1: Registry Schema + Python Module

**Files:**
- NEW: `src/governance/framework_registry.py` (+250 lines)
- NEW: `docs/reference/framework_registry_schema.md` (+80 lines)
- NEW: `tests/test_framework_registry.py` (+200 lines)

**Lines:** +530
**Time:** 10 hours
**Confidence:** 90%

**JSONL Schema (one line per component):**

```json
{
  "id": "DOMAIN-001",
  "type": "domain",
  "level": 1,
  "name": "CryptoSpot",
  "parent": null,
  "children": ["STYLE-001", "STYLE-002"],
  "evidence": [
    {
      "path": "scripts/data/fetch_crypto_ccxt.py",
      "line": 31,
      "symbol": "_INSTRUMENTS",
      "type": "code"
    }
  ],
  "findings": [
    {
      "id": "F-019",
      "confidence": "Likely",
      "action": "inform",
      "modifier": 1.0
    }
  ],
  "tests": ["tests/test_dataset_integrity.py"],
  "status": "extant",
  "created": "2026-06-15T00:00:00Z",
  "last_validated": "2026-06-15T00:00:00Z",
  "notes": "First domain class"
}
```

**Type enum:** `kernel | domain | style | strategy | implementation | intent | risk | execution | component | workflow_node`
**Level enum:** `0 | 1 | 2 | 3 | 4 | 5 | 6`
**Status enum:** `extant | implicit | orphaned | killed | dormant | planned | stub`
**Evidence type enum:** `code | config | doc | test | finding`
**Finding action enum:** `deweight | disable | restrict_session | restrict_spread | enforce_sl | inform | escalate`

**Public API (FrameworkRegistry class):**

| Method | Purpose |
|--------|---------|
| `load(path)` | Load JSONL, keep latest per id. Returns int (count). |
| `filter(type=None, level=None, status=None, parent=None)` | Query registry. Returns list[dict]. |
| `get(id)` | Get component by id. Returns dict. |
| `get_tree(root_id)` | Recursively build parent→children tree. Returns dict (nested). |
| `find_by_finding(finding_id)` | All components linked to a finding. Returns list[dict]. |
| `get_orphaned()` | Components with no parent reference. Returns list[dict]. |
| `validate_evidence()` | Check every evidence path+line exists. Returns list[ValidationError]. |
| `validate_findings()` | Check every finding id exists in docs/current-findings.md. Returns list[ValidationError]. |
| `append(record)` | Append one line, raises on schema violation. Returns None. |
| `to_dataframe()` | Export as pandas DataFrame. Returns DataFrame. |
| `summary()` | Counts per type, level, status. Returns dict. |

**Tests (8 tests minimum):**

| Test | What it validates |
|------|-------------------|
| `test_registry_loads_valid_jsonl` | All lines parse, no schema violations |
| `test_every_evidence_path_exists` | Every `evidence[].path` is a real file |
| `test_every_finding_exists` | Every `findings[].id` is in docs/current-findings.md |
| `test_no_dangling_parent` | Every `parent` id exists in the registry |
| `test_no_dangling_child` | Every `children[]` id exists in the registry |
| `test_level_matches_type` | `type=domain` implies `level=1`, etc. |
| `test_unique_ids` | No duplicate `id` across lines |
| `test_append_only_immutable` | Appending does not mutate existing lines |

**Checklist:**
- [ ] `docs/reference/framework_registry_schema.md` written with full schema
- [ ] `src/governance/framework_registry.py` with all 11 methods
- [ ] `tests/test_framework_registry.py` with 8+ tests
- [ ] All 8 tests pass
- [ ] Schema validation raises on invalid records
- [ ] Evidence validation catches missing files
- [ ] Finding validation catches missing IDs

---

## Story 3.2: Seed Registry from Codebase

**Files:**
- NEW: `scripts/governance/seed_framework_registry.py` (+100 lines)
- NEW: `data/framework_registry.jsonl` (+35 lines — one per component)

**Lines:** +135
**Time:** 5 hours
**Confidence:** 85%

**Classification table (seed data, user-verified):**

| Existing Code | id | type | level | Status |
|--------------|-----|------|-------|--------|
| `src/core/engine_runner.py` | KERNEL-001 | kernel | 0 | extant |
| `src/core/fusion_engine.py` | KERNEL-002 | kernel | 0 | extant |
| `src/core/decision_engine.py` | KERNEL-003 | kernel | 0 | extant |
| `src/features/feature_pipeline.py` | KERNEL-004 | kernel | 0 | extant |
| `src/runtime/backtest_v2.py` | KERNEL-005 | kernel | 0 | extant |
| `src/core/collector.py` | KERNEL-006 | kernel | 0 | extant |
| `scripts/data/fetch_crypto_ccxt.py` | DOMAIN-001 | domain | 1 | implicit |
| `scripts/data/fetch_forex_yfinance.py` | DOMAIN-002 | domain | 1 | dormant |
| `configs/production/v2_multi_2026_04.json` | DOMAIN-CONFIG-001 | domain | 1 | extant |
| `src/strategies/s01_crt_wrapper.py` | STRAT-001 | strategy | 3 | extant |
| `src/strategies/s02_mean_reversion.py` | STRAT-002 | strategy | 3 | extant |
| `src/strategies/s03_breakout.py` | STRAT-003 | strategy | 3 | extant |
| `src/strategies/s04_stat_arb.py` | STRAT-004 | strategy | 3 | extant |
| `src/strategies/s05_grid.py` | STRAT-005 | strategy | 3 | extant |
| `src/strategies/s06_scalping.py` | STRAT-006 | strategy | 3 | extant |
| `src/strategies/s07_news_sentiment.py` | STRAT-007 | strategy | 3 | extant |
| `src/strategies/s08_ml_ensemble.py` | STRAT-008 | strategy | 3 | extant |
| `src/strategies/s09_pattern_recog.py` | STRAT-009 | strategy | 3 | extant |
| `src/strategies/s10_trap_strategy.py` | STRAT-010 | strategy | 3 | extant |
| `src/engines/crt_engine.py` | IMPL-001 | implementation | 4 | extant |
| `src/engines/heuristic_gaussian_engine.py` | IMPL-002 | implementation | 4 | extant |
| `src/engines/ml_gaussian_engine.py` | IMPL-003 | implementation | 4 | extant |
| `src/engines/zone_gate_engine.py` | IMPL-004 | implementation | 4 | extant |
| `src/engines/rr_engine.py` | IMPL-005 | implementation | 4 | extant |
| `src/config_layer/execution_planner.py` | EXEC-001 | execution | 6 | extant |
| `src/core/ultron_risk_gate.py` | RISK-001 | risk | 5 | extant |
| `src/inout/executor.py` | EXEC-002 | execution | 6 | stub |
| `src/agent/` | AI-001 | component | 4 | extant |
| `src/bitnet/bitnet_inference.py` | AI-002 | component | 4 | extant |
| `src/governance/promotion_manager.py` | GOV-001 | component | 0 | extant |
| `src/portfolio/` | PORT-001 | risk | 5 | orphaned |
| `src/cognitive/` | AI-003 | component | 4 | orphaned |

**Evidence extraction rules:**
- For each module, extract the first `class` or `def` line as evidence
- For config, extract the first relevant line
- For data scripts, extract the line where the instrument list is defined

**Checklist:**
- [ ] `seed_framework_registry.py` written
- [ ] 35+ initial records in `data/framework_registry.jsonl`
- [ ] Each record has at least 1 evidence link
- [ ] Parent/children relationships are correct (user verification required)
- [ ] All 8 registry validation tests pass on seeded data
- [ ] No dangling parent references
- [ ] All evidence paths exist

---

## Story 3.3: CLI Query Tool

**Files:**
- NEW: `scripts/governance/query_registry.py` (+200 lines)

**Lines:** +200
**Time:** 6 hours
**Confidence:** 90%

**Usage:**

```
python scripts/governance/query_registry.py --summary
python scripts/governance/query_registry.py --type strategy
python scripts/governance/query_registry.py --tree DOMAIN-001
python scripts/governance/query_registry.py --finding F-021
python scripts/governance/query_registry.py --orphaned
python scripts/governance/query_registry.py --validate
```

**Output format for --tree:**

```
DOMAIN-001 CryptoSpot
├── STYLE-001 ReactionBased
│   ├── STRAT-001 CRT
│   │   └── IMPL-001 CRTEngine
│   └── STRAT-010 LiquiditySweep
├── STYLE-002 Breakout
│   └── STRAT-003 BOS+Volume
└── STYLE-003 MeanReversion
    ├── STRAT-002 RSI+BB
    └── STRAT-004 StatArb
```

**Checklist:**
- [ ] All 7 query modes work
- [ ] `--validate` runs full validation (evidence + findings + dangling refs)
- [ ] `--tree` produces correct hierarchy
- [ ] Exit code 0 on success, 1 on validation failure
- [ ] Help text (`--help`) documents all options

---

## Story 3.4: Registry Report Generator

**Files:**
- NEW: `scripts/governance/framework_registry_report.py` (+150 lines)
- NEW: `reports/framework_registry_report.md` (generated)

**Lines:** +150
**Time:** 4 hours
**Confidence:** 85%

**Report sections:**
1. Summary table — count per level per status
2. Gap analysis — which framework levels are empty or implicit
3. Orphan report — components not connected to the tree
4. Finding coverage — which findings are linked to components, which findings have no linked components
5. Evidence health — count of valid vs broken evidence paths
6. Hierarchy visualization — ASCII tree of the full registry

**Checklist:**
- [ ] Report generates without errors
- [ ] Report contains all 6 sections
- [ ] Report is valid Markdown
- [ ] Report is saved to `reports/framework_registry_report.md`

---

## Story 3.5: Findings Applier Module

**Files:**
- NEW: `src/governance/findings_applier.py` (+180 lines)
- NEW: `tests/test_findings_applier.py` (+150 lines)

**Lines:** +330
**Time:** 8 hours
**Confidence:** 75%

**What it does:**
Takes a component (from registry) and its active findings, returns the modified config/weight.

```python
class FindingsApplier:
    def apply(self, component: dict, mode: str = "research") -> dict:
        """Apply findings to component.
        
        Args:
            component: Registry record for a strategy/implementation/etc.
            mode: "research" (log only) or "active" (actually modify)
            
        Returns:
            Component dict with effective_weight, effective_status, effective_config
        """
```

**Mode behavior:**
- RESEARCH mode: logs what WOULD change, doesn't change anything
- ACTIVE mode: applies changes to the component's config before passing to engine

**Finding actions and how they modify components:**

| `findings[].action` | Effect on Component |
|---------------------|-------------------|
| `deweight` | `component.weight *= modifier` (default modifier=0.5) |
| `disable` | `component.status = "disabled"` |
| `restrict_session` | Add `session_restriction` to component config |
| `restrict_spread` | Add `max_spread_bps` to component config |
| `enforce_sl` | Add `min_sl_atr_mult` to component config |
| `inform` | No change (log only) |
| `escalate` | No change (log as escalation) |

**Aggregation rules:**
- Multiple `deweight` actions: weights multiply (compounding)
- `disable` overrides all other actions
- Confidences are applied only if >= threshold:
  - ACTIVE mode: only `Certain` and `Likely` findings are applied
  - RESEARCH mode: all findings are logged but none applied

**Tests:**

| Test | What it validates |
|------|-------------------|
| `test_deweight_reduces_weight` | Single deweight action reduces weight correctly |
| `test_multiple_deweight_compounds` | Multiple deweights multiply |
| `test_disable_overrides` | Disable action overrides all other actions |
| `test_research_mode_logs_only` | Research mode does not modify |
| `test_confidence_threshold` | Low confidence findings not applied in active mode |
| `test_unknown_action_raises` | Unknown action raises ValueError |
| `test_restrict_session_adds_filter` | Session restriction added to config |
| `test_enforce_sl_adds_minimum` | SL minimum added to config |

**Checklist:**
- [ ] `findings_applier.py` with all 8+ methods
- [ ] `test_findings_applier.py` with 8+ tests
- [ ] All tests pass
- [ ] Research mode does not modify components
- [ ] Active mode modifies only with sufficient confidence
- [ ] Multiple findings compound correctly
- [ ] Disable action properly overrides

---

## Story 3.6: Validate Finding Directives via Backtest

**Files:**
- NEW: `scripts/research/validate_finding.py` (+200 lines)
- NEW: `docs/reference/finding_validation_schema.md` (+50 lines)

**Lines:** +250
**Time:** 8 hours
**Confidence:** 70%

**What it does:**
Runs an A/B backtest for a finding:

```
Backtest A (baseline): Run WITHOUT the finding's directive applied
Backtest B (treatment): Run WITH the finding's directive applied
Result: B outperforms A → finding VALIDATED
        B underperforms A → finding REFUTED
        B == A → finding IRRELEVANT
```

**Usage:**

```
python scripts/research/validate_finding.py \
    --finding F-021 \
    --instrument BNBUSDT \
    --data data/BNBUSDT_M15.csv \
    --config configs/production/v2_multi_2026_04.json \
    --output results/finding_validation_F-021.json
```

**Validation output schema:**

```json
{
  "finding_id": "F-021",
  "directive_summary": "Session filter is the only non-random discriminator",
  "instrument": "BNBUSDT",
  "timerange": "2024-01-01..2026-05-01",
  "baseline_config_hash": "sha256:a1b2c3...",
  "treatment_config_diff": {
    "engine_runner.allowed_sessions": ["london", "new_york", "overlap"]
  },
  "baseline": {
    "expectancy": -0.15,
    "trades": 143,
    "win_rate": 0.34,
    "max_drawdown": -0.22,
    "sharpe": -0.1
  },
  "treatment": {
    "expectancy": -0.02,
    "trades": 47,
    "win_rate": 0.41,
    "max_drawdown": -0.15,
    "sharpe": 0.05
  },
  "delta": {
    "expectancy": 0.13,
    "trades": -96,
    "win_rate": 0.07,
    "max_drawdown": 0.07,
    "sharpe": 0.15
  },
  "verdict": "VALIDATED",
  "confidence_delta": "Increased from Possible to Likely",
  "created": "2026-06-15T00:00:00Z"
}
```

**Verdict logic:**
- VALIDATED: treatment expectancy > baseline expectancy AND treatment trades >= 10
- REFUTED: treatment expectancy <= baseline expectancy
- INCONCLUSIVE: treatment trades < 10 (insufficient data)
- ERROR: backtest failed (config error, data error)

**Checklist:**
- [ ] `validate_finding.py` written
- [ ] `finding_validation_schema.md` written
- [ ] Can run A/B backtest for any finding
- [ ] Produces structured validation result JSON
- [ ] Works with parallel backtests (for faster validation)
- [ ] Validated findings auto-register in registry

---

# 10. Epic 4: Domain Layer Extraction

**Goal:** Create formal domain abstractions. No existing code changes — new code coexists.
**Total:** 4 stories, 10 new files, +575 lines, 17 hours.
**Prerequisite for:** Style layer + n8n multi-domain support.

## Story 4.1: Create `TradingDomain` Abstract Base Class

**Files:**
- NEW: `src/domain/__init__.py` (+5 lines)
- NEW: `src/domain/base.py` (+80 lines)
- NEW: `tests/test_domain_base.py` (+100 lines)

**Lines:** +185
**Time:** 6 hours
**Confidence:** 90%

**ABC Contract:**

```python
class TradingDomain(ABC):
    @abstractmethod
    def domain_name(self) -> str  # "CryptoSpot", "Forex", etc.
    @abstractmethod
    def calendar(self) -> TradingCalendar
    @abstractmethod
    def cost_model(self, instrument: str) -> CostModel
    @abstractmethod
    def leverage_model(self) -> LeverageModel
    @abstractmethod
    def position_rules(self) -> PositionRules
    @abstractmethod
    def risk_rules(self) -> RiskRules
    @abstractmethod
    def allowed_styles(self) -> list[str]
```

**Supporting dataclasses:**

```python
@dataclass
class TradingCalendar:
    session_bounds: list  # [(start_hour, end_hour, timezone), ...]
    holidays: list[int]    # UTC epoch ms
    gap_handling: str      # "fill_flat" / "fill_previous" / "reject"
    weekly_break: Optional[tuple[int, int]]

@dataclass
class CostModel:
    taker_fee: float
    maker_fee: float
    min_commission: float
    spread_bps: float
    periodic_cost: float         # per-hour holding cost (funding/swap)
    periodic_cost_interval_h: float

@dataclass
class LeverageModel:
    max_leverage: float
    margin_type: str             # "cash" / "cross" / "isolated" / "reg_t"
    maintenance_margin_pct: float
    liquidation_buffer_pct: float

@dataclass
class PositionRules:
    allow_short: bool
    min_notional: float
    size_increment: float
    price_precision: int
    max_positions_same_instrument: int
    max_positions_total: int

@dataclass
class RiskRules:
    max_daily_loss_pct: float
    max_drawdown_pct: float
    max_correlation_exposure: float
    volatility_scaling: bool
    gap_risk_buffer_pct: float
    liquidation_risk_monitoring: bool
```

**Checklist:**
- [ ] `src/domain/__init__.py` created
- [ ] `src/domain/base.py` with ABC + all 6 dataclasses
- [ ] All abstract methods defined with docstrings
- [ ] `tests/test_domain_base.py` with tests for each dataclass
- [ ] Domain package is importable without side effects (no config loading at import time)

---

## Story 4.2: Implement `CryptoSpotDomain`

**Files:**
- NEW: `src/domain/crypto_spot.py` (+100 lines)

**Lines:** +100
**Time:** 4 hours
**Confidence:** 85%

**Values to extract from current implicit behavior:**
- Calendar: continuous 24/7, no session bounds, no weekly break, gap_handling = "reject" (crypto has no gaps, any gap is data quality issue)
- Cost: taker_fee=0.00075 (Binance spot), maker_fee=0.00075, min_commission=0, spread_bps=3.0 (0.03%), periodic_cost=0 (no funding on spot), periodic_cost_interval_h=0
- Leverage: max_leverage=1.0, margin_type="cash"
- Position: allow_short=false, min_notional=10, size_increment=0.001 (BTC), price_precision=8, max_positions_same=1, max_positions_total=5
- Risk: max_daily_loss=0.05, max_drawdown=0.20, vol_scaling=true, gap_risk=0.02
- Styles: ["ReactionBased", "Breakout", "MeanReversion", "Momentum", "Pattern", "Grid"]

**Checklist:**
- [ ] `CryptoSpotDomain` implements all abstract methods
- [ ] All values are informed by current config and behavior (user verification recommended)
- [ ] Tests assert all methods return non-None values
- [ ] Domain is registered in framework_registry.jsonl
- [ ] Domain is NOT wired into engine yet (coexistence only)

---

## Story 4.3: Implement `ForexDomain` (Dormant → Extant)

**Files:**
- NEW: `src/domain/forex.py` (+100 lines)

**Lines:** +100
**Time:** 4 hours
**Confidence:** 70%

**Values:**
- Calendar: 24/5, Sun 17:00 - Fri 17:00 UTC, session_bounds=[Tokyo 00-09, London 08-17, NY 13-22], gap_handling="fill_flat" (weekends are filled with flat bars or rejected)
- Cost: taker_fee=0 (spread-only retail), maker_fee=0, min_commission=0, spread_bps=1.5 (EURUSD typically), periodic_cost=swap_rate/365 (overnight holding), periodic_cost_interval_h=24
- Leverage: max_leverage=30.0 (retail typical), margin_type="margin"
- Position: allow_short=true, min_notional=1000 (1k units), size_increment=1000, price_precision=5, max_positions_same=1, max_positions_total=5
- Risk: max_daily_loss=0.05, max_drawdown=0.20, vol_scaling=true, gap_risk=0.01 (forex gaps smaller than crypto)
- Styles: ["ReactionBased", "TrendFollowing", "Breakout", "MeanReversion"]

**Warning:** Forex cost model is broker-dependent. The spread_bps=1.5 is a reasonable average
but may not match any specific broker. Add a comment: "Default values — verify against your
broker's actual costs before promoting to active."

**Checklist:**
- [ ] `ForexDomain` implements all abstract methods
- [ ] Calendar correctly handles 24/5 vs 24/7
- [ ] Cost model accounts for swap/holding costs
- [ ] Domain is registered in framework_registry.jsonl as `status=extant`
- [ ] Domain is NOT wired into engine yet

---

## Story 4.4: Create Domain Stubs

**Files:**
- NEW: `src/domain/crypto_futures.py` (+40 lines)
- NEW: `src/domain/equities.py` (+40 lines)
- NEW: `src/domain/futures.py` (+40 lines)
- NEW: `src/domain/options.py` (+40 lines)

**Lines:** +160
**Time:** 3 hours
**Confidence:** 95%

**Each stub must include:**
- Calendar (basic, may be approximate)
- Cost model (may be minimal)
- Leverage model (may be placeholder)
- Position rules (may be minimal)
- Risk rules (may be default)
- Allowed styles (may be empty)

**Status:** All stubs registered as `status=planned` in registry. Future work.

**Checklist:**
- [ ] 4 domain stubs created
- [ ] Each implements all abstract methods (can return default/placeholder values)
- [ ] Each is registered in framework_registry.jsonl as `status=planned`
- [ ] All domain tests still pass

---

# 11. Epic 5: Style Layer + Strategy Reorganization

**Goal:** Group 10+ strategies under styles. Make CRT a strategy plugin, not a mandatory engine.
**Total:** 4 stories, 12 files (+8 new, +3 modified), +375/-5 lines, 20 hours.
**Highest risk:** Story 5.4 changes the fundamental engine invariant.

## Story 5.1: Create `TradingStyle` Abstract Base Class

**Files:**
- NEW: `src/styles/__init__.py` (+5 lines)
- NEW: `src/styles/base.py` (+60 lines)
- NEW: `tests/test_style_base.py` (+80 lines)

**Lines:** +145
**Time:** 4 hours
**Confidence:** 90%

**ABC Contract:**

```python
class TradingStyle(ABC):
    @abstractmethod
    def name(self) -> str
    @abstractmethod
    def allowed_strategies(self) -> list[str]
    @abstractmethod
    def preferred_instruments(self, domain: TradingDomain) -> list[str]
    @abstractmethod
    def max_hold_bars(self) -> int
    @abstractmethod
    def regime_preferences(self) -> list[str]
    @abstractmethod
    def required_engines(self) -> set[str]
```

**Checklist:**
- [ ] `src/styles/__init__.py` created
- [ ] `src/styles/base.py` with ABC
- [ ] `tests/test_style_base.py` with tests for each method
- [ ] Style package is importable without side effects

---

## Story 5.2: Classify 10 Existing Strategies Under Styles

**Files:**
- NEW: `src/styles/reaction_based.py` (+30 lines — references CRT, LiquiditySweep, NewsSentiment)
- NEW: `src/styles/mean_reversion.py` (+20 lines — references RSI+BB, StatArb)
- NEW: `src/styles/breakout.py` (+20 lines — references BOS+Volume)
- NEW: `src/styles/momentum.py` (+20 lines — references MACD)
- NEW: `src/styles/grid.py` (+15 lines — references ATRGrid)
- NEW: `src/styles/pattern.py` (+15 lines — references Candlestick)
- NEW: `src/styles/ml_hybrid.py` (+15 lines — references ML Ensemble)
- MODIFIED: `src/strategies/strategy_orchestrator.py` (+30 lines — add style-aware selection)

**Lines:** +165
**Time:** 6 hours
**Confidence:** 75%

**Style assignments:**

| Style | Strategies | Required Engines | Regime |
|-------|-----------|-----------------|--------|
| ReactionBased | CRT, LiquiditySweep, NewsSentiment | {crt} | ranging |
| MeanReversion | RSI+BB, StatArb | {gaussian} | ranging |
| Breakout | BOS+Volume | {zone_gate} | trending |
| Momentum | MACD | {} | trending |
| Grid | ATRGrid | {} | ranging |
| Pattern | Candlestick | {} | any |
| ML/Hybrid | ML Ensemble | {rr} | any |

**StrategyOrchestrator change:** Add a new method `get_strategies_for_regime(regime: str)` that
returns only strategies whose style matches the current regime. Old consensus scoring still
works for backward compatibility.

**Checklist:**
- [ ] 8 style modules created
- [ ] Each style correctly lists its allowed strategies (by id)
- [ ] Each style lists required engines
- [ ] StrategyOrchestrator has style-aware selection method
- [ ] Old consensus scoring path still works (backward compatible)
- [ ] Registry updated: each strategy has `parent=<style_id>`
- [ ] All tests pass

---

## Story 5.3: Add TrendFollowing Style + MA_Cross Strategy

**Files:**
- NEW: `src/styles/trend_following.py` (+20 lines)
- NEW: `src/strategies/s11_ma_cross.py` (+80 lines)
- MODIFIED: `configs/production/v2_multi_2026_04.json` (+20 lines)
- MODIFIED: `docs/STRATEGIES.md` (+15 lines)

**Lines:** +135
**Time:** 5 hours
**Confidence:** 80%

**MA Cross Strategy Logic:**

```python
class MACrossStrategy:
    """Simple trend-following: fast MA crosses above slow MA → long.
    Exit: price crosses below slow MA or time stop.
    """
    
    def compute(self, candle, features, state):
        fast_ma = state.fast_ma  # 10-period
        slow_ma = state.slow_ma  # 50-period
        
        if fast_ma > slow_ma and state.prev_fast <= state.prev_slow:
            return Signal(direction=1, confidence=0.6)
        elif fast_ma < slow_ma and state.prev_fast >= state.prev_slow:
            return Signal(direction=-1, confidence=0.6)
        return None
```

**Config:**

```json
{
  "strategy_engine.s11_ma_cross": {
    "enabled": false,
    "fast_period": 10,
    "slow_period": 50,
    "min_volume_ratio": 1.0,
    "session_restriction": "london,new_york,overlap",
    "regime_restriction": "trending",
    "min_adx": 25,
    "warmup_bars": 60
  }
}
```

**Critical:** MA Cross is registered BUT disabled by default (`enabled: false`). It's available
for research only until validated. This prevents the new strategy from affecting existing behavior.

**Checklist:**
- [ ] TrendFollowing style created
- [ ] S11 MA Cross strategy implemented
- [ ] Config section added (enabled: false)
- [ ] STRATEGIES.md updated
- [ ] Registry updated with new strategy + style
- [ ] All existing tests pass (new strategy is disabled)

---

## Story 5.4: Style-Scoped Engine Completeness Check

**Files:**
- MODIFIED: `src/core/engine_runner.py` (-5 lines, +30 lines)
- MODIFIED: `src/styles/base.py` (+5 lines — add `required_engines` property)

**Lines:** +30, -5
**Time:** 5 hours
**Confidence:** 60% — **HIGHEST RISK STORY**

**What changes:**
Replace the global `EXPECTED_ENGINES = {"crt", "gaussian", "zone_gate", "rr"}` with
style-scoped checks. Each style specifies its required engines. The engine completeness
check becomes style-scoped.

**Before (current):**
```python
EXPECTED_ENGINES = {"crt", "gaussian", "zone_gate", "rr"}
# ...
if missing := EXPECTED_ENGINES - set(engine_results.keys()):
    raise ValueError(f"Missing engines: {missing}")
```

**After (new):**
```python
# Global fallback (backward compatible)
EXPECTED_ENGINES = {"crt", "gaussian", "zone_gate", "rr"}

# Style-scoped check (feature-flagged)
if config.get("style_scoped_engines", False):
    active_styles = get_active_styles_for_regime(current_regime)
    required = set().union(*[s.required_engines for s in active_styles])
    if missing := required - set(engine_results.keys()):
        raise ValueError(f"Missing engines for style {missing}")
else:
    # Old behavior (default)
    if missing := EXPECTED_ENGINES - set(engine_results.keys()):
        raise ValueError(f"Missing engines: {missing}")
```

**Feature flag:** `style_scoped_engines: false` (default: false → backward compatible).

**Checklist:**
- [ ] Global EXPECTED_ENGINES preserved as fallback
- [ ] Feature flag `style_scoped_engines` added to config (default=false)
- [ ] Style-scoped check implemented behind flag
- [ ] When flag=false: behavior is identical to current (byte-identity verified)
- [ ] When flag=true: only engines required by active styles are checked
- [ ] Registry updated: each style has `required_engines` field
- [ ] Byte-identity backtest verified for flag=false
- [ ] Byte-identity backtest verified for flag=true (may differ by design)

**Escalation condition:** If fixing this causes >50 line changes, stop and raise:
the style-scoped engine check may need a separate engine runner path rather than modifying
the existing one.

---

# 12. Epic 6: n8n Integration

**Goal:** Docker Compose for n8n + webhook receiver + parallel workdir isolation + workflow.
**Total:** 5 stories, 7+ files (+3 new, +4 modified), +945 lines, 25 hours.
**Prerequisite for:** All automated orchestration.

## Story 6.1: Docker Compose for n8n

**Files:**
- NEW: `docker-compose.yml` (+40 lines)

**Lines:** +40
**Time:** 2 hours
**Confidence:** 90%

```yaml
version: '3.8'
services:
  n8n:
    image: n8nio/n8n:latest
    ports:
      - "5678:5678"
    volumes:
      - ./data/n8n:/home/node/.n8n
      - ./:/data/tradelatest
    environment:
      - N8N_SECURE_COOKIE=false
      - WEBHOOK_URL=http://localhost:5678/
    networks:
      - tradelatest
    restart: unless-stopped

  control_plane:
    build: .
    ports:
      - "8787:8787"
    volumes:
      - ./:/app
    command: python scripts/control_plane/run_server.py
    networks:
      - tradelatest
    restart: unless-stopped

volumes:
  n8n_data:

networks:
  tradelatest:
```

**Checklist:**
- [ ] `docker-compose.yml` written
- [ ] `docker compose up n8n` starts n8n at localhost:5678
- [ ] `docker compose up control_plane` starts control plane at localhost:8787
- [ ] Both containers can communicate (n8n → control_plane via hostname "control_plane")

---

## Story 6.2: n8n Webhook Receiver in Control Plane

**Files:**
- MODIFIED: `src/control_plane/server.py` (+80 lines)
- MODIFIED: `src/control_plane/registry.py` (+30 lines)

**Lines:** +110
**Time:** 8 hours
**Confidence:** 75%

**Two new endpoints:**

### POST `/api/run-stage`

**Input (JSON body):**
```json
{
  "stage": "tuning",
  "instrument": "BNBUSDT",
  "workdir": "/tmp/tradelatest/BNBUSDT/run_001",
  "config": {
    "n_iter": 100,
    "seed": 42,
    "workers": 4
  }
}
```

**Output (JSON):**
```json
{
  "status": "success",
  "stage": "tuning",
  "instrument": "BNBUSDT",
  "metrics": {
    "expectancy": -0.02,
    "trades": 47,
    "win_rate": 0.41,
    "max_drawdown": -0.15
  },
  "config_hash": "sha256:a1b2c3...",
  "artifacts": ["results/tuner/BNBUSDT/checkpoint.json"],
  "duration_seconds": 342,
  "error": null
}
```

**Error output:**
```json
{
  "status": "error",
  "stage": "tuning",
  "instrument": "BNBUSDT",
  "error": "No data found for BNBUSDT",
  "error_type": "DataNotFoundError",
  "duration_seconds": 2,
  "artifacts": []
}
```

### POST `/api/claude-gate`

**Input (JSON body):**
```json
{
  "stage": "tuning",
  "instrument": "BNBUSDT",
  "config": { "...": "..." },
  "backtest_results": {
    "expectancy": -0.15,
    "trades": 143,
    "win_rate": 0.34,
    "max_drawdown": -0.22
  },
  "findings": [
    {"id": "F-021", "directive": "Session filter is only discriminator"},
    {"id": "F-026", "directive": "CRT retest adds no edge, deweight"}
  ]
}
```

**Output (JSON — Claude's decision):**
```json
{
  "action": "tweak" | "promote" | "escalate" | "skip",
  "confidence": 0.0-1.0,
  "tweak": {
    "section": "params",
    "key": "retest_depth_max",
    "from": 0.8,
    "to": 0.6,
    "reason": "F-026 shows CRT retest adds no edge. Reducing from 0.8 to 0.6.",
    "expected_impact": "Reduce noise trades ~20%"
  },
  "findings_referenced": ["F-026"],
  "next_action": "re-run backtest"
}
```

**Security:** Both endpoints are localhost-only (same as existing control plane). No auth required.
If exposed externally, must add API key validation.

**Checklist:**
- [ ] `POST /api/run-stage` implemented
- [ ] `POST /api/claude-gate` implemented
- [ ] Both endpoints return correct JSON
- [ ] Error responses include error_type for n8n to route on
- [ ] Endpoints are localhost-only
- [ ] Existing control plane functionality unchanged

---

## Story 6.3: Parallel Workdir Isolation for Scripts

**Files:**
- MODIFIED: `scripts/training/auto_tuner_multi.py` (+10 lines)
- MODIFIED: `scripts/training/auto_tuner.py` (+10 lines)
- MODIFIED: `scripts/data/prepare_data.py` (+10 lines)
- MODIFIED: `src/runtime/backtest_v2.py` (+15 lines)
- MODIFIED: `src/governance/promotion_manager.py` (+10 lines)

**Lines:** +55
**Time:** 6 hours
**Confidence:** 70%

**What changes:**
Each script gets a new optional arg `--workdir <path>`. When provided:
- All output paths are relative to workdir (not hardcoded `results/` or `data/`)
- Temp files are created in workdir
- Lock files are created in workdir (to prevent concurrent writes)

**Pattern:**

```python
# In each script's argument parser
parser.add_argument("--workdir", type=str, default=None,
                    help="Working directory for output isolation")

# At start of main()
workdir = args.workdir
if workdir:
    os.makedirs(workdir, exist_ok=True)
    output_dir = os.path.join(workdir, "results")
    data_dir = os.path.join(workdir, "data")
else:
    output_dir = args.output_dir or DEFAULT_OUTPUT_DIR
    data_dir = args.data_dir or DEFAULT_DATA_DIR
```

**Critical:** If a script uses absolute paths (hardcoded `results/tuner/`), the workdir
flag must override that path. Audit each script for hardcoded paths before implementing.

**Checklist:**
- [ ] 5 scripts modified with `--workdir` flag
- [ ] All output paths respect workdir when provided
- [ ] Backward compatible (no workdir = current behavior)
- [ ] Parallel runs with different workdirs don't collide
- [ ] Tests pass for both with and without workdir

---

## Story 6.4: n8n Workflow JSON Export

**Files:**
- NEW: `configs/n8n/trading_workflow.json` (+500+ lines)

**Lines:** +500
**Time:** 4 hours
**Confidence:** 80%

**Workflow nodes (in order):**

1. **Webhook Trigger** — accepts `POST` with `{"instruments":["BNBUSDT","BTCUSDT","ETHUSDT","SOLUSDT"]}`
2. **Split In Batches** — splits into 4 parallel branches (one per instrument)
3. **Data Prep** — HTTP POST to `http://control_plane:8787/api/run-stage` with stage="data_prep"
4. **Tuning** — HTTP POST to control_plane with stage="tuning"
5. **Validation** — HTTP POST to control_plane with stage="validation"
6. **Claude Gate** — HTTP POST to control_plane with stage="claude_gate"
   - If "tweak" → loop back to Tuning (max 3 iterations)
   - If "promote" → proceed to Promotion
   - If "escalate" → stop, log to escalation queue
7. **Promotion** — HTTP POST to control_plane with stage="promotion"
8. **Live Runner** — HTTP POST to control_plane with stage="live_runner"

**Checklist:**
- [ ] Workflow JSON exported and saved to `configs/n8n/`
- [ ] Import into n8n works without errors
- [ ] Each node correctly calls the control plane webhook
- [ ] Claude Gate node correctly handles all 3 outputs (tweak/promote/escalate)
- [ ] Tweak loop has max 3 iterations (prevent infinite loops)
- [ ] Escalation stops the workflow and logs to file

---

## Story 6.5: Stage Result Schema + Validation

**Files:**
- NEW: `docs/reference/stage_result_schema.md` (+60 lines)
- NEW: `src/control_plane/stage_result.py` (+80 lines)
- NEW: `tests/test_stage_result.py` (+100 lines)

**Lines:** +240
**Time:** 5 hours
**Confidence:** 85%

**Schema validation rules:**
- `status` must be "success" or "error"
- `stage` must be one of: "data_prep", "tuning", "validation", "claude_gate", "promotion", "live_runner"
- `instrument` must be a non-empty string
- `metrics` must contain at least `expectancy` and `trades` if status="success"
- `error` must be non-empty if status="error"
- `artifacts` must be a list of strings (file paths)
- `duration_seconds` must be a positive number

**Checklist:**
- [ ] `stage_result_schema.md` written
- [ ] `stage_result.py` with validation function
- [ ] `test_stage_result.py` with tests for each schema rule
- [ ] Validation raises on invalid input
- [ ] Validation returns sanitized dict on valid input

---

# 13. Epic 7: Claude Gate Integration

**Goal:** Claude gate webhook + prompt templates + registry config for LLM gates.
**Total:** 3 stories, 7 files (+5 new, +2 modified), +495 lines, 16 hours.

## Story 7.1: Claude Gate Webhook Handler

**Files:**
- NEW: `src/control_plane/claude_gate.py` (+200 lines)
- NEW: `tests/test_claude_gate.py` (+150 lines)
- MODIFIED: `src/control_plane/server.py` (+5 lines — register route)

**Lines:** +355
**Time:** 10 hours
**Confidence:** 75%

**Handler logic:**

```python
class ClaudeGateHandler:
    def __init__(self, api_key: str, prompt_templates_dir: str):
        self.api_key = api_key
        self.prompt_templates_dir = prompt_templates_dir
    
    def evaluate(self, context: dict) -> dict:
        """Call Claude API with prompt built from context.
        
        Args:
            context: {stage, instrument, config, backtest_results, findings, findings_prompt}
            
        Returns:
            {action, confidence, tweak, findings_referenced, next_action}
        """
        # 1. Load prompt template for this stage
        template = self._load_template(context["stage"])
        
        # 2. Build prompt from template + context
        prompt = self._build_prompt(template, context)
        
        # 3. Call Anthropic Claude API
        response = self._call_claude(prompt)
        
        # 4. Parse and validate response
        decision = self._parse_response(response)
        
        # 5. Log the interaction
        self._log_interaction(context, prompt, decision)
        
        return decision
```

**Prompt template variables:**
- `{{config}}` — current config section relevant to this stage
- `{{backtest_results}}` — expectancy, trades, win_rate, max_drawdown
- `{{findings}}` — list of active findings with directives
- `{{instrument}}` — instrument name
- `{{stage}}` — current workflow stage

**Rate limiting:** Max 3 calls to Claude per workflow per instrument. Configurable.
If limit reached → auto-escalate.

**Checklist:**
- [ ] `claude_gate.py` written with full handler
- [ ] `test_claude_gate.py` with tests for prompt building, API calling, response parsing
- [ ] API key loaded from `.env` or config (not hardcoded)
- [ ] Response parsing handles invalid JSON gracefully (log warning, return "escalate")
- [ ] Rate limiting implemented (max N calls per workflow)
- [ ] All interactions logged to file for audit

---

## Story 7.2: Claude Prompt Templates in Config

**Files:**
- NEW: `configs/production/claude_prompts/tuning_gate.json` (+30 lines)
- NEW: `configs/production/claude_prompts/validation_gate.json` (+30 lines)
- NEW: `configs/production/claude_prompts/promotion_gate.json` (+30 lines)

**Lines:** +90
**Time:** 3 hours
**Confidence:** 80%

**Tuning Gate Prompt Template:**

```json
{
  "stage": "tuning",
  "system_prompt": "You are the config tweaker for a crypto trading bot called Tradelatest. Your job: read backtest results + current config + active findings, and suggest the MINIMUM config change to improve expectancy. RULES: (1) Change ONE parameter at most. (2) If expectancy is positive, recommend promote. (3) If no tweak is obvious, escalate. (4) You may reference findings (F-001 to F-029) to justify. (5) Never suggest structural code changes. Config only. RESPONSE FORMAT (JSON only): {\"action\": \"tweak\" | \"promote\" | \"escalate\", \"confidence\": 0.0-1.0, \"tweak\": {\"section\": \"...\", \"key\": \"...\", \"from\": value, \"to\": value, \"reason\": \"...\", \"expected_impact\": \"...\", \"findings_referenced\": [\"...\"]}, \"next_action\": \"...\"}",
  "user_prompt_template": "Stage: {{stage}}\nInstrument: {{instrument}}\nConfig: {{config}}\nBacktest Results: {{backtest_results}}\nActive Findings: {{findings}}\nFinding Directive Summary: {{findings_prompt}}\n\nSuggest one config tweak."
}
```

**Validation Gate Prompt Template:**

```json
{
  "stage": "validation",
  "system_prompt": "You are the validation gate for Tradelatest. Your job: decide if a tuned config should be promoted to production. RULES: (1) Promote only if expectancy > 0 AND trades >= 10. (2) If expectancy is positive but marginal (<0.1R), recommend additional tuning. (3) If expectancy is negative, escalate. RESPONSE FORMAT (JSON only): {\"action\": \"promote\" | \"re-tune\" | \"escalate\", \"confidence\": 0.0-1.0, \"reason\": \"...\", \"findings_referenced\": [\"...\"]}",
  "user_prompt_template": "..."
}
```

**Checklist:**
- [ ] 3 prompt templates created
- [ ] Each template has valid JSON structure
- [ ] Templates use consistent variable naming ({{variable}})
- [ ] Tuning gate template enforces "one change at most" rule
- [ ] Validation gate template enforces "expectancy>0" rule

---

## Story 7.3: Claude Gate Config in Registry

**Files:**
- MODIFIED: `docs/reference/framework_registry_schema.md` (+30 lines)
- MODIFIED: `src/governance/framework_registry.py` (+20 lines — handle new type)

**Lines:** +50
**Time:** 3 hours
**Confidence:** 85%

**New type in registry: `workflow_node`**

```json
{
  "id": "NODE-TUNING-GATE",
  "type": "workflow_node",
  "level": 0,
  "name": "Tuning Claude Gate",
  "parent": "WORKFLOW-001",
  "children": [],
  "evidence": [
    {"path": "src/control_plane/claude_gate.py", "line": 1, "symbol": "ClaudeGateHandler", "type": "code"}
  ],
  "llm_gate": {
    "enabled": true,
    "trigger_conditions": ["soft_fail", "expectancy_below_0", "new_instrument"],
    "max_iterations": 3,
    "prompt_template": "configs/production/claude_prompts/tuning_gate.json",
    "allowed_actions": ["tweak", "promote", "escalate"],
    "on_escalate": "notify_user"
  },
  "status": "extant",
  "notes": "Claude gate for tuning stage. Triggers on soft_fail or negative expectancy."
}
```

**Checklist:**
- [ ] Schema updated with `workflow_node` type
- [ ] `llm_gate` field documented in schema
- [ ] Registry module handles new type in summaries
- [ ] Workflow nodes registered for each Claude gate stage

---

# 14. Epic 8: Enable UltronRiskGate + Wire Portfolio

**Goal:** Turn on the risk gate, wire portfolio module, wire drift detection action.
**Total:** 3 stories, 3-4 files, +66 lines, 11 hours.
**Highest risk (second):** Story 8.1 enables a disabled gate.

## Story 8.1: Enable UltronRiskGate in Config

**Files:**
- MODIFIED: `configs/production/v2_multi_2026_04.json` (1 line change)

**Lines:** +0, -0 (1 value changed)
**Time:** 2 hours
**Confidence:** 50% — **SECOND HIGHEST RISK STORY**

**What changes:**
Line 66 of `configs/production/v2_multi_2026_04.json`:
```
"ultron_gate_enabled": false  →  "ultron_gate_enabled": true
```

**Why this is risky:** Enabling the risk gate for the first time will reject trades
that were previously accepted. This is BY DESIGN, but the impact on trade count and
metrics is unknown. The risk gate checks:
- TTL expiry → may reject trades with long hold times
- RR floor → may reject trades with low expected RR
- Daily trade limit → may cap number of trades
- Kill switch (daily loss) → may shut down after losing streak
- Portfolio exposure → may reject correlated trades
- SL distance checks → may reject trades with tight SLs

**Procedure:**
1. Run backtest with `ultron_gate_enabled: false` (current) → record metrics
2. Run backtest with `ultron_gate_enabled: true` → record metrics
3. Compare: how many trades were rejected? Which check rejected them?
4. If rejection rate is reasonable (e.g., <20% of previously accepted trades), proceed
5. If rejection rate is too high (>50%), adjust risk gate thresholds
6. Set conservative limits initially: daily loss=10%, drawdown=25%, trade limit=10/day

**Checklist:**
- [ ] Backtest run with gate disabled (baseline metrics recorded)
- [ ] Backtest run with gate enabled (treatment metrics recorded)
- [ ] Rejection analysis: how many, which check, which instruments
- [ ] If rejection rate acceptable: gate enabled in config
- [ ] If rejection rate too high: thresholds adjusted
- [ ] Byte-identity verified (baseline matches existing, treatment is new)
- [ ] Risk gate tests pass with new config

---

## Story 8.2: Wire PortfolioAllocator into Spine

**Files:**
- MODIFIED: `src/core/engine_runner.py` (+15 lines)
- MODIFIED: `src/portfolio/__init__.py` (+10 lines — expose API)

**Lines:** +25
**Time:** 4 hours
**Confidence:** 65%

**What changes:**
After `UltronRiskGate.evaluate()` approves a trade (or concurrently), call
`PortfolioAllocator.evaluate()` to check portfolio-level constraints:

- Net exposure ≤ max_leverage
- Gross exposure ≤ max_gross
- Concentration (single instrument ≤ max_pct)
- Correlation exposure (correlated bets ≤ threshold)

If portfolio check fails → REJECT (even if risk gate approved).

**Integration point:**
```python
# In engine_runner.py, after risk gate
if config.get("portfolio_check_enabled", False):
    if not portfolio_allocator.check(portfolio_state, proposed_trade):
        logger.warning("Portfolio check rejected trade")
        rejected_by = "portfolio"
        continue  # or log and skip
```

**Feature flag:** `portfolio_check_enabled: false` (default: false).

**Checklist:**
- [ ] Portfolio module API exposed
- [ ] Portfolio check integrated into engine_runner.py after risk gate
- [ ] Feature flag `portfolio_check_enabled` default=false
- [ ] Tests pass for both flag=true and flag=false
- [ ] Byte-identity backtest verified for flag=false

---

## Story 8.3: Wire Drift Detector Action (Fix F-008)

**Files:**
- MODIFIED: `src/features/feature_monitor.py` (+30 lines)
- MODIFIED: `src/core/engine_runner.py` (+10 lines)

**Lines:** +40
**Time:** 5 hours
**Confidence:** 70%

**What changes:**
F-008 says concept drift is "DETECTED but NOT acted on." The feature monitor already
computes drift Z-scores. Now add actions:

- HARD drift (Z > 3.0 for 2+ consecutive bars): PAUSE affected strategies
- SOFT drift (Z > 2.5 for 3+ consecutive bars): SIZE DOWN 50%

**Implementation:**

```python
# In feature_monitor.py
class FeatureMonitor:
    def check_drift(self, features):
        drift = self.compute_drift(features)
        actions = []
        for feature_name, z_score in drift.items():
            if z_score > 3.0:
                self.drift_streak[feature_name] = self.drift_streak.get(feature_name, 0) + 1
                if self.drift_streak[feature_name] >= 2:
                    actions.append({"feature": feature_name, "z_score": z_score, "action": "pause"})
            elif z_score > 2.5:
                self.drift_streak[feature_name] = self.drift_streak.get(feature_name, 0) + 1
                if self.drift_streak[feature_name] >= 3:
                    actions.append({"feature": feature_name, "z_score": z_score, "action": "size_down"})
            else:
                self.drift_streak[feature_name] = 0  # reset streak
        return actions
```

**Feature flag:** `drift_action_enabled: false` (default: false).

**Checklist:**
- [ ] Drift action callbacks implemented in feature_monitor.py
- [ ] EngineRunner registers drift callbacks
- [ ] HARD drift pauses affected strategies after 2 consecutive bars
- [ ] SOFT drift sizes down 50% after 3 consecutive bars
- [ ] Streak resets when drift subsides
- [ ] Feature flag `drift_action_enabled` default=false
- [ ] Tests pass for both flag=true and flag=false

---

# 15. Epic 9: Documentation + Validation

**Goal:** All reference docs updated. Integration tests added. Regression verified.
**Total:** 4 stories, 4+ files, +280 lines, 17 hours.

## Story 9.1: Update All Reference Docs

**Files:**
- MODIFIED: `docs/reference/architecture.md` (+50 lines)
- MODIFIED: `docs/reference/schemas.md` (+30 lines)
- MODIFIED: `docs/reference/config-reference.md` (+20 lines)
- MODIFIED: `docs/STRATEGIES.md` (+30 lines)

**Lines:** +130
**Time:** 6 hours
**Confidence:** 80%

**Architecture.md additions:**
- Domain layer (src/domain/) with ABC and implementations
- Style layer (src/styles/) with ABC and implementations
- Strategy reorganization (CRT as plugin, not mandatory)
- Registry (data/framework_registry.jsonl)
- n8n orchestration layer
- Control plane webhook endpoints

**Checklist:**
- [ ] Architecture.md updated with new layers
- [ ] Schemas.md updated with domain/style/schemas
- [ ] Config-reference.md updated with new sections
- [ ] STRATEGIES.md updated with style grouping, MA Cross

---

## Story 9.2: Add Registry + Findings Validation Tests

Already counted in Story 3.1 and 3.5. This story covers the testing effort.

**Time:** 4 hours
**Confidence:** 85%

**Checklist:**
- [ ] All 8 registry tests pass
- [ ] All 8 findings applier tests pass
- [ ] Registry validation catches broken evidence paths
- [ ] Registry validation catches missing findings

---

## Story 9.3: Add n8n Integration Tests

**Files:**
- NEW: `tests/test_control_plane_webhooks.py` (+150 lines)

**Lines:** +150
**Time:** 4 hours
**Confidence:** 80%

**Tests:**
- POST `/api/run-stage` with valid input → returns 200 + valid stage result
- POST `/api/run-stage` with invalid stage → returns 400 + error
- POST `/api/claude-gate` with valid input → returns 200 + valid decision
- POST `/api/claude-gate` with missing API key → returns 503 + error
- Both endpoints reject non-JSON bodies
- Both endpoints accept only POST (reject GET/PUT/DELETE)

**Checklist:**
- [ ] Webhook endpoint tests pass
- [ ] Claude gate endpoint tests pass
- [ ] Error handling tests pass

---

## Story 9.4: Full Regression Test

**Files:** 0 (test runner only)
**Lines:** 0
**Time:** 3 hours (test runtime)
**Confidence:** 90%

**What to run:**
```
pytest tests/ --tb=short -q
```

**Expected:** 1208+ passed, 0 failed, 18 skipped, 2 xfailed (or whatever the current
skip/xfail count is).

**Byte-identity verification (if spine code changed):**
```
python scripts/analysis/verify_determinism.py \
    --config configs/production/v2_multi_2026_04.json \
    --data data/BNBUSDT_M15.csv \
    --baseline results/baseline/BNBUSDT_ledger.json
```

**Checklist:**
- [ ] All 1200+ tests pass
- [ ] Byte-identity verified for BNBUSDT (if spine changed)
- [ ] Byte-identity verified for SOLUSDT (if spine changed)
- [ ] Regression report saved

---

# 16. Epic 10: Findings Integration

**Goal:** Validate all 29 existing findings against historical data. Promote validated ones.
**Total:** 3 stories, 3+ files, +108 lines, 37-45 hours (dominated by backtest runtime).

## Story 10.1: Validate All 29 Existing Findings

**Files:**
- NEW: `data/finding_validations.jsonl` (+29 lines)
- NEW: `reports/finding_validation_report.md` (generated)

**Lines:** +29
**Time:** 30 hours (backtest runtime) / ~8 hours (parallelized)
**Confidence:** 60%

**Expected outcomes (based on existing research):**

| Finding | Expected Verdict | Confidence Change |
|---------|-----------------|-------------------|
| F-001 | INCONCLUSIVE (architectural, not testable via backtest) | No change |
| F-002 | INCONCLUSIVE (requires research, not backtest) | No change |
| F-004 | VALIDATED (BitNet gate score is persisted) | Certain → Certain |
| F-005 | INCONCLUSIVE (TradeNet v2 not wired, can't test) | No change |
| F-006 | VALIDATED (config_integrity runs but gates nothing) | Certain → Certain |
| F-008 | VALIDATED (drift detected but not acted, will see in logs) | Certain → Certain |
| F-009 | INCONCLUSIVE (per-instrument doctrine, history) | No change |
| F-010 | INCONCLUSIVE (live PnL unverifiable in backtest) | No change |
| F-011 | INCONCLUSIVE (OOS persistence, long backtest needed) | No change |
| F-012 | INCONCLUSIVE (architectural, not testable) | No change |
| F-013 | VALIDATED (portfolio module exists, not wired) | Certain → Certain |
| F-016 | INCONCLUSIVE (version truth, config check) | No change |
| F-017 | VALIDATED (session policy backtest shows no improvement) | Likely → Certain |
| F-019 | VALIDATED (no crypto major shows positive expectancy) | Likely → Certain |
| F-020 | VALIDATED (no conditional pocket found) | Likely → Certain |
| F-021 | VALIDATED (session restriction improves expectancy) | Likely → Certain |
| F-025 | VALIDATED (SL/TP tuning doesn't fix negative edge) | Likely → Certain |
| F-026 | VALIDATED (CRT retest removal improves metrics) | Likely → Certain |
| F-027 | VALIDATED (H1/H4 no better than M15) | Likely → Certain |
| F-028 | VALIDATED (P&F no standalone edge) | Likely → Certain |
| F-029 | INCONCLUSIVE (center=True benign, needs specific test) | No change |

**Checklist:**
- [ ] All 29 findings validated via A/B backtest
- [ ] Validation results saved to `data/finding_validations.jsonl`
- [ ] Validation report generated at `reports/finding_validation_report.md`
- [ ] Each validation includes baseline vs treatment metrics
- [ ] Each validation includes verdict and any confidence change

---

## Story 10.2: Promote Validated Findings to Active

**Files:**
- MODIFIED: `data/framework_registry.jsonl` (+29 lines — findings linked to components)

**Lines:** +29
**Time:** 4 hours (review + registry updates)
**Confidence:** 70%

**Procedure:**
1. For each finding that validated: add to registry under affected components
2. For each finding that refuted: note as `SUPERSEDED` in findings doc
3. For each finding that is inconclusive: leave as-is, note "needs more data"
4. Run findings applier in RESEARCH mode: verify correct modifications
5. If verified: promote findings applier to ACTIVE mode

**Checklist:**
- [ ] Validated findings linked to affected components in registry
- [ ] Refuted findings marked as SUPERSEDED in findings doc
- [ ] Inconclusive findings noted as "needs more data"
- [ ] Findings applier in RESEARCH mode produces expected modifications
- [ ] If verified: applier promoted to ACTIVE

---

## Story 10.3: Continuous Validation Pipeline

**Files:**
- MODIFIED: `configs/n8n/trading_workflow.json` (+1 node)
**Lines:** +50
**Time:** 3 hours
**Confidence:** 85%

**New n8n node:** Weekly validation workflow that runs `validate_finding.py` for new
findings. Runs every Sunday at 02:00 UTC.

**Checklist:**
- [ ] Weekly validation workflow added to n8n
- [ ] New findings auto-validated
- [ ] Validation results logged to JSONL
- [ ] User notified if finding verifies or refutes

---

# 17. JSONL Registry Schema Reference

## 17.1 Component Record

```json
{
  "id": "DOMAIN-001",
  "type": "domain",
  "level": 1,
  "name": "CryptoSpot",
  "parent": null,
  "children": ["STYLE-001", "STYLE-002"],
  "evidence": [
    {
      "path": "scripts/data/fetch_crypto_ccxt.py",
      "line": 31,
      "symbol": "_INSTRUMENTS",
      "type": "code"
    }
  ],
  "findings": [
    {
      "id": "F-019",
      "confidence": "Likely",
      "action": "deweight",
      "modifier": 0.5
    }
  ],
  "tests": ["tests/test_dataset_integrity.py"],
  "status": "extant",
  "created": "2026-06-15T00:00:00Z",
  "last_validated": "2026-06-15T00:00:00Z",
  "findings_policy": {
    "aggregate_mode": "multiplicative",
    "floor_weight": 0.1,
    "auto_disable_at": 0.0
  },
  "notes": "First domain class"
}
```

## 17.2 Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `id` | YES | string | Unique identifier. Format: `{TYPE}-{NUMBER}` |
| `type` | YES | enum | `kernel \| domain \| style \| strategy \| implementation \| intent \| risk \| execution \| component \| workflow_node` |
| `level` | YES | int | 0-6 (matching TRADING_SYSTEM_FRAMEWORK.md hierarchy) |
| `name` | YES | string | Human-readable component name |
| `parent` | YES | string or null | Parent component id (null for root) |
| `children` | YES | list[string] | Child component ids (empty list for leaf) |
| `evidence` | YES | list[EvidenceObject] | At least 1 evidence link |
| `findings` | YES | list[FindingLink] | Empty list if none |
| `tests` | YES | list[string] | Test file paths |
| `status` | YES | enum | `extant \| implicit \| orphaned \| killed \| dormant \| planned \| stub` |
| `created` | YES | string (ISO 8601) | Creation timestamp |
| `last_validated` | YES | string (ISO 8601) | Last validation timestamp |
| `findings_policy` | NO | dict | Aggregation rules |
| `notes` | NO | string | Free-text notes |

## 17.3 Evidence Object

```json
{
  "path": "src/core/engine_runner.py",
  "line": 52,
  "symbol": "EXPECTED_ENGINES",
  "type": "code"
}
```

**`type` enum:** `code | config | doc | test | finding`

## 17.4 Finding Link

```json
{
  "id": "F-026",
  "confidence": "Likely",
  "action": "deweight",
  "modifier": 0.3
}
```

**`confidence` enum:** `Certain | Likely | Possible`
**`action` enum:** `deweight | disable | restrict_session | restrict_spread | enforce_sl | inform | escalate`

## 17.5 Workflow Node Extra Fields

```json
{
  "llm_gate": {
    "enabled": true,
    "trigger_conditions": ["soft_fail", "expectancy_below_0"],
    "max_iterations": 3,
    "prompt_template": "configs/production/claude_prompts/tuning_gate.json",
    "allowed_actions": ["tweak", "promote", "escalate"],
    "on_escalate": "notify_user"
  }
}
```

---

# 18. Claude Gate Prompt Templates

## 18.1 Tuning Gate

**System prompt:**
```
You are the config tweaker for a crypto trading bot called Tradelatest.
Your job: read backtest results + current config + active findings, and suggest
the MINIMUM config change to improve expectancy.

RULES:
- Change ONE parameter at most. Never change 2+ things at once.
- If expectancy is already positive, recommend promotion.
- If expectancy is negative but a tweak is obvious, return the tweak with expected impact.
- If no tweak is obvious, escalate with a clear reason.
- You may reference findings (F-001 to F-029) to justify your decision.
- Never suggest structural code changes. Config only.
- Never suggest changing more than one parameter.

RESPONSE FORMAT (JSON only):
{
  "action": "tweak" | "promote" | "escalate",
  "confidence": 0.0-1.0,
  "tweak": {
    "section": "params",
    "key": "parameter_name",
    "from": current_value,
    "to": new_value,
    "reason": "Why this change (reference findings if applicable)",
    "expected_impact": "Quantified expected impact",
    "findings_referenced": ["F-XXX"]
  },
  "next_action": "re-run backtest"
}
```

## 18.2 Validation Gate

**System prompt:**
```
You are the validation gate for Tradelatest.
Your job: decide if a tuned config should be promoted to production.

RULES:
- Promote only if expectancy > 0 AND trades >= 10.
- If expectancy is positive but marginal (< 0.1R), recommend re-tuning instead.
- If expectancy is negative, escalate with analysis.
- Consider active findings in your decision.

RESPONSE FORMAT (JSON only):
{
  "action": "promote" | "re-tune" | "escalate",
  "confidence": 0.0-1.0,
  "reason": "Why this decision",
  "findings_referenced": ["F-XXX"]
}
```

## 18.3 Promotion Gate

**System prompt:**
```
You are the promotion gate for Tradelatest.
Your job: confirm that a validated config should be promoted to production.

RULES:
- Confirm only if expectancy > 0 AND validated at least twice (A/B backtest).
- If this is the first validation, recommend additional validation.
- If expectancy is negative, block promotion.

RESPONSE FORMAT (JSON only):
{
  "action": "confirm" | "re-validate" | "block",
  "confidence": 0.0-1.0,
  "reason": "Why this decision",
  "evidence": ["validation run IDs"]
}
```

---

# 19. Troubleshooting Guide

## 19.1 Test Failures After Implementation

| Symptom | Likely Cause | Check |
|---------|-------------|-------|
| 10+ LLM tests fail | Fallback value mismatch (0.5 vs 1.0) | Story 1.1 |
| Dual gate tests fail | Regime classifier labels mismatch | Story 1.2 |
| RR fusion tests fail | RRFusionLayer import or method renamed | Story 1.3 |
| Gaussian switch fails | `gaussian_impl` flag path changed | Story 1.4 |
| Registry tests fail | JSONL schema mismatch | Story 3.1, check `framework_registry_schema.md` |
| Webhook tests fail | Route registration conflict | Story 6.2, check `server.py` route table |
| Claude gate tests fail | API key not set | Story 7.1, check `.env` |
| Risk gate tests fail | `ultron_gate_enabled` still false | Story 8.1, check config line 66 |

## 19.2 Runtime Errors After Implementation

| Error | Likely Cause | Check |
|-------|-------------|-------|
| "Missing engines: crt" after enabling style-scoped engines | ReactionBased style not registered or incorrect engine list | Story 5.4, check style.required_engines |
| "No module named src.domain" | Domain package not installed | Run `pip install -e .` or check pyproject.toml |
| Claude gate returns "action: escalate" for every call | Prompt template too restrictive, or no tweak possible | Story 7.2, check prompt template |
| n8n workflow fails at Claude gate | API key invalid or rate limited | Story 7.1, check `.env` for ANTHROPIC_API_KEY |
| Parallel backtests produce different results | Workdir isolation not working | Story 6.3, check `--workdir` flag in scripts |
| All trades rejected after enabling risk gate | Risk gate thresholds too tight | Story 8.1, check `capital_management` values |
| Registry validation shows broken evidence | File moved or renamed | Run `query_registry.py --validate` to list broken paths |
| Findings not applied to engine | FindingsApplier mode = "research" | Story 3.5, check mode parameter |

## 19.3 Performance Issues

| Issue | Likely Cause | Fix |
|-------|-------------|-----|
| Backtest takes 30+ min per finding | No parallelization | Use `--parallel` flag in validate_finding.py |
| n8n workflow takes hours | Sequential stages | Enable parallel branches in workflow |
| Claude API calls slow (5+ sec each) | API rate limiting | Reduce max_iterations or batch calls |
| Registry JSONL file grows too large | Too many append operations | Archive old records monthly |

## 19.4 Rollback Procedure

If a story causes regression:

1. **If feature-flagged:** Set flag to `false` (original behavior restored)
2. **If not feature-flagged:** Revert the commit:
   ```
   git revert <commit-hash>
   ```
3. **If config only:** Restore previous config version:
   ```
   python src/governance/promotion_manager.py load --version v2_multi_2026_04
   ```
4. **If registry corrupt:** Restore from backup:
   ```
   cp data/framework_registry.jsonl.bak data/framework_registry.jsonl
   ```
   (Always keep a backup before modifying registry)

## 19.5 Pre-Flight Checks Before Any Story

Before starting any story, always:

1. **Run the full test suite** → record baseline: `pytest tests/ -q --tb=short 2>&1 | tee before_story.log`
2. **Run byte-identity backtest** → record baseline: `python scripts/backtest/v2.py --csv data/BNBUSDT_M15.csv --output results/baseline/BNBUSDT_before.json`
3. **Backup registry** → `cp data/framework_registry.jsonl data/framework_registry.jsonl.bak`
4. **Backup config** → `cp configs/production/v2_multi_2026_04.json configs/production/v2_multi_2026_04.json.bak`

After the story:

1. **Run the full test suite** → compare to baseline: any NEW failures?
2. **Run byte-identity backtest** → compare to baseline: any changes in trade ledger?
3. **If regressions found:** fix or revert. Do not proceed to next story.

---

# 20. Audit Trail Template

Every story must produce this audit record. Append to `assistant_project.md` after each story.

```
---
📝 SESSION LOG ENTRY
Date: {timestamp}
Epic: {epic name}
Story: {story number}: {story title}

Files Changed:
  - NEW: path/to/file.py (+N lines)
  - MODIFIED: path/to/file.py (+N/-M lines)

Key Decisions:
  - {decision 1 with rationale}
  - {decision 2 with rationale}

Belief Update / ROI / Goal:
  Goal: {goal this story serves}
  Belief: {what was believed before vs after}
  Knowledge ROI: {High/Medium/Low — was this worth doing?}
  Action: {next step}

Risks Remaining:
  - {risk 1}
  - {risk 2}

Validation Results:
  - Tests: {passed/failed count}
  - Byte-identity: {PASS/FAIL/not applicable}
  - Registry validation: {passed/failed}

Open Questions:
  - {any unresolved items}

Next Story:
  - {next story number}: {next story title}
---
```

---

# 21. Implementation Order (Critical Path)

## Phase 1: Foundation (must build first — trust the codebase)

**Order matters. Do not skip.**

```
Story 1.1 → Fix LLM tests (1h)
Story 1.4 → Fix Gaussian switch (2h)
Story 1.5 → Fix replay memory (2h)
Story 1.6 → Fix feature schema (0.5h)
Story 1.2 → Fix dual gate (3h)
Story 1.3 → Fix RR fusion (3h)
  → ALL 23 FIXES VERIFIED. FULL REGRESSION. ~11.5h
```

## Phase 2: Measurement (build the registry)

```
Story 3.1 → Registry schema + module (10h)
Story 3.2 → Seed registry (5h)
Story 3.3 → CLI query tool (6h)
Story 3.4 → Report generator (4h)
  → REGISTRY FUNCTIONAL. CAN QUERY ARCHITECTURE. ~25h
```

## Phase 3: Config cleanup (make config trustworthy)

```
Story 2.6 → Externalize PROMOTION_MARGIN (1h)
Story 2.2 → Remove data_ingestion (1h)
Story 2.4 → Verify StrategyOrchestrator (3h)
Story 2.1 → Wire capital management (6h)
Story 2.3 → Wire/remove gate_intelligence (4h)
Story 2.5 → Wire regime_fusion_weights (5h)
  → ALL CONFIG CONSUMED. NO DEAD SECTIONS. ~20h
```

## Phase 4: Findings (make findings drive behavior)

```
Story 3.5 → Findings applier module (8h)
Story 3.6 → Validate finding directives (8h)
Story 10.1 → Validate all 29 findings (30h parallelized)
Story 10.2 → Promote validated findings (4h)
  → FINDINGS DRIVE ENGINE. ~50h
```

## Phase 5: Risk (turn on protection)

```
Story 8.3 → Wire drift detector action (5h)
Story 8.2 → Wire portfolio allocator (4h)
Story 8.1 → Enable UltronRiskGate (2h)
  → RISK ACTIVE. NON-BYPASSABLE. ~11h
```

## Phase 6: Architecture (domain + style layers)

```
Story 4.1 → Domain ABC (6h)
Story 4.2 → CryptoSpotDomain (4h)
Story 5.1 → Style ABC (4h)
Story 5.2 → Classify strategies (6h)
Story 5.3 → Add TrendFollowing + MA_Cross (5h)
Story 5.4 → Style-scoped engines (5h) ← HIGH RISK
  → ARCHITECTURE CORRECT. ~30h
```

## Phase 7: Automation (n8n + Claude)

```
Story 6.1 → Docker Compose (2h)
Story 6.2 → Webhook receiver (8h)
Story 6.3 → Parallel workdir isolation (6h)
Story 7.2 → Claude prompt templates (3h)
Story 7.3 → Claude gate in registry (3h)
Story 7.1 → Claude gate handler (10h)
Story 6.4 → n8n workflow JSON (4h)
Story 6.5 → Stage result schema (5h)
Story 9.3 → n8n integration tests (4h)
  → AUTOMATION RUNNING. ~45h
```

## Phase 8: Documentation + Final Validation

```
Story 4.3 → ForexDomain (4h)
Story 4.4 → Domain stubs (3h)
Story 9.1 → Update reference docs (6h)
Story 9.2 → Registry validation tests (4h) [already counted in Phase 2]
Story 9.4 → Full regression test (3h)
Story 10.3 → Continuous validation pipeline (3h)
  → EVERYTHING DONE. ~23h
```

## Total: ~220 hours (5-6 weeks full-time)

---

**End of specification. Hand this document to Claude LLM for implementation.**