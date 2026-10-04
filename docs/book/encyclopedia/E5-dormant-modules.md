# Encyclopedia E5 — Dormant / Archived Surfaces (Group C)

**Phase:** E5  
**Status:** DONE (honest one-line + reopen rules — do not deep-read by default)  
**Date:** 2026-08-07  
**Parent:** [Chapter 24](../24-repository-encyclopedia.md) · [Encyclopedia index](README.md)

## Scope

Group C packages were **intentionally deprioritized** by the architecture book because they are
not on the **active production candle→order story** — scaffold, multi-strategy experiments,
sidecars with zero spine consumption, UAT harnesses, or **archived** parallel rails.

| Package / tree | `.py` files | Default posture |
|---|---:|---|
| `src/strategies/` | 18 | DORMANT scaffold (S01–S10) |
| `src/scanner/` | 6 | DORMANT / ORPHANED vs live single-candle spine |
| `src/journal/` | 6 | DORMANT identity/provenance layers |
| `src/cognitive/` | 2 | DORMANT sidecar bus (F-012) |
| `src/feedback/` | 2 | DORMANT |
| `src/llm_research/` | 5 | DORMANT offline LLM research pipeline |
| `src/data_ingestion/` | 6 | **MIXED** — see §7 (not all dead) |
| `src/uat/` | 4 | DORMANT multi-strategy UAT harness |
| `src/ui/` | 1 | Empty / remnant package |
| `archive/**` | ~19 | **ARCHIVED** — do not import from production |
| **Total** | **~69** | |

**Rule:** DORMANT ≠ delete. Means **do not reopen without explicit intent** and a reopen checklist.

---

## How to use

1. **Default:** skip deep-reading these packages for spine work.  
2. **If reopening:** read the package row + reopen conditions below; run construction protocol; do not silently wire into EngineRunner.  
3. **Archive:** read only for forensics; never re-import as live path without a full design.

---

## 1. `src/strategies/` — S01–S10 multi-strategy scaffold (18)

**Posture:** **DORMANT** — full strategy module framework exists; live production still runs the
**single CRT spine**, not StrategyOrchestrator multi-strategy hot path (see F-013 class).

| File | Purpose (one line) |
|---|---|
| `base_strategy.py` | ABC for S1–S10 |
| `strategy_result.py` | Universal strategy output contract |
| `strategy_intent.py` | Typed hypothesis intent from strategies |
| `intent_builder.py` | StrategyResult → intent adapter |
| `strategy_orchestrator.py` | Run all 10 strategies per candle + aggregate |
| `strategy_package.py` | Strategy package / registry architecture target |
| `strategy_registry.py` | Load/list StrategyPackage versions |
| `s01_crt_wrapper.py` | S1 CRT wrapper (closest to live spine) |
| `s02_mean_reversion.py` … `s10_trap_strategy.py` | S2–S10 alternate strategies (MR, breakout, stat-arb, grid, scalp, news, ML ensemble, pattern, trap) |
| `__init__.py` | Package exports |

**Reopen if:** multi-strategy production is an explicit goal + ValidationReport path + single-spine parity.  
**Do not:** assume S08/S06 etc. are live because files exist.  
**Related:** E3 `multi_strategy_validator` / `strategy_backtest` can exercise them offline.

---

## 2. `src/scanner/` — multi-symbol scan rail (6)

**Posture:** **DORMANT / ORPHANED** relative to live single-candle spine (scan→allocate→loop class, F-013).

| File | Purpose |
|---|---|
| `scanner.py` | Multi-symbol scanner core |
| `universe.py` | Symbol universe definition |
| `ranker.py` | Rank scan hits |
| `signal_pool.py` | Pool of candidate signals |
| `spine_adapter.py` | **Only designed path** scanner → `EngineRunner.run()` |
| `__init__.py` | Package marker |

**Reopen if:** multi-symbol live allocation is authorized and wired end-to-end through Ultron.  
**Do not:** confuse with `archive/inout_legacy/.../scanner.py` (different archived rail).

---

## 3. `src/journal/` — trade identity / provenance (6)

**Posture:** **DORMANT** as a production journal system; contracts exist for future correlation.

| File | Purpose |
|---|---|
| `trade_identity_v1_0.py` | Minimal immutable trade identity (alert → decision link) |
| `trade_provenance_v1_0.py` | Config/model/promotion lineage keyed by trade_id |
| `trade_execution_link_v1_0.py` | Broker/venue correlation layer (disposable Tier 0B) |
| `trade_logger.py` / `schema.py` | Journal logging + schema |
| `__init__.py` | Package marker |

**Note:** Live logging often uses `src/utils/trade_logger.py` (E4) instead.  
**Archive twin:** `archive/dead_code/journal/*` — older copies; ignore for new work.

---

## 4. `src/cognitive/` — cognitive bus (2)

**Posture:** **DORMANT sidecar** — async cognitive processing; **zero spine consumption** (F-012).

| File | Purpose |
|---|---|
| `cognitive_bus.py` | Async cognitive processing bus |
| `__init__.py` | Package marker |

**Reopen if:** explicit cognitive sidecar product goal; never block EngineRunner on bus health.

---

## 5. `src/feedback/` — AI feedback (2)

**Posture:** **DORMANT**.

| File | Purpose |
|---|---|
| `ai_feedback.py` | AI feedback collection/loop (scaffold) |
| `__init__.py` | Package marker |

**Reopen if:** closed-loop learning product is designed with measurement contract + no silent train-in-prod.

---

## 6. `src/llm_research/` — offline LLM research pipeline (5)

**Posture:** **DORMANT** offline pipeline (pattern → policy → forward test). Not live LLM gate.

| File | Purpose |
|---|---|
| `pattern_extractor.py` | Extract patterns via LLM offline |
| `policy_builder.py` | Build policies from extracted patterns |
| `forward_tester.py` | Forward-test generated policies |
| `evaluator.py` | Evaluate LLM research outputs |
| `__init__.py` | Pipeline architecture package |

**Distinct from:** live `llm_inference_client` (E1, fail-open advisory) and multi-LLM ops (E4/Ch.23).

---

## 7. `src/data_ingestion/` — MIXED (6)

**Not pure dormant.** Parts are legacy DB-oriented; parts are **LIVE integrity** used by research/backtest.

| File | Posture | Purpose |
|---|---|---|
| `dataset_integrity.py` | **LIVE-research** | L3 whole-dataset sequence integrity preflight (F-039: limited call sites) |
| `ohlcv_schema.py` | **LIVE-contract** | Historical OHLCV column contract |
| `session_autoderive.py` | RESEARCH | Learn tradable session from data (vs hardcoded calendars) |
| `xauusd_phase1_candidate.py` | RESEARCH freeze | XAUUSD M15 Phase-1 candidate identity verification |
| `historical_fetcher.py` | **LEGACY / convention tension** | Multi-pair OHLCV into **TimescaleDB** (repo doctrine: no DB — prefer `src/inout/*` CSV fetchers) |
| `__init__.py` | — | Package marker |

**Prefer for new data I/O:** `src/inout/*` fetchers (E1/Ch.15).  
**Prefer for integrity:** `dataset_integrity` at backtest/research preflight when required.

---

## 8. `src/uat/` — multi-strategy UAT harness (4)

**Posture:** **DORMANT** relative to single-spine production; useful only if multi-strategy returns.

| File | Purpose |
|---|---|
| `uat_runner.py` | Orchestrates UAT areas for 10-strategy system |
| `monte_carlo.py` | Bootstrap resampling robustness checks |
| `kill_switch.py` | Daily/weekly loss kill-switch state machine |
| `__init__.py` | Package marker |

**Note:** `kill_switch` ideas may overlap live risk concerns — production capital authority remains **UltronRiskGate** (E1/Ch.14).

---

## 9. `src/ui/` — remnant (1)

| File | Purpose |
|---|---|
| `__init__.py` | Empty/remnant UI package |

**Archive:** `archive/ui_legacy/dashboard_ARCHIVED_2026_05_02.py`, `archive/dead_code/ui/dashboard.py`.  
**Live UI surface:** control-plane localhost dashboard (E1/Ch.22), not `src/ui/`.

---

## 10. `archive/**` — ARCHIVED (do not import)

| Path | Why archived |
|---|---|
| `archive/inout_legacy/ARCHIVED_2026_05_02/` | Parallel execution rail (scanner/state_machine/controller/db) — bypassed spine; SQLite violated no-DB (Ch.15) |
| `archive/dead_code/**` | Extracted dead modules (old bitnet smoke, journal, ui, insight_reporter, bitnet_feature_builder) |
| `archive/ui_legacy/` | Old dashboard |
| `archive/scripts/` | Old historical data runner scripts (typo’d names preserved) |
| `archive/zips/` | Zip backups — not code authority |

**Replacement for archived INOUT rail:** `HookedLiveEngine.process` (E1).  
**Replacement for data I/O:** `src/inout/*` CSV fetchers.

---

## Reopen checklist (any Group C package)

1. Explicit user/owner goal (not “file looks interesting”).  
2. Classify against construction protocol / change contracts.  
3. Prove callers (or add them) — no silent hot-path wire.  
4. Measurement: if economic claim → pre-registration + M4-class gate (E2).  
5. If multi-strategy/scanner: address F-013 single-spine reality.  
6. Never re-enable `archive/inout_legacy` as a second spine.  
7. SESSION LOG + docs decision (Ch.17 drift protocol).

---

## Danger flags

| Flag | Meaning |
|---|---|
| **DORMANT** | Present; off active story; deprioritize |
| **ORPHANED** | Built path with no live caller (scanner/portfolio class) |
| **ARCHIVED** | Explicitly retired under `archive/` — forensic only |
| **MIXED** | Package contains both live-adjacent and legacy files |
| **CONVENTION_BREAK** | e.g. TimescaleDB fetcher vs no-DB doctrine |

---

## E5 exit criterion

| Criterion | Status |
|---|---|
| All Group C packages from Ch.24 have one-line map | **Met** |
| Archive trees listed with replacement path | **Met** |
| data_ingestion MIXED called out (not false dormant) | **Met** |
| Reopen checklist | **Met** |
| Full strategy design revival | **Out of scope** |

---

## Next

- **E6** — Remaining scripts outside research/governance/analysis catalogs (operator script matrix residual).

---
**Related:** [Ch.15 INOUT](../15-live-execution-and-inout.md) · [E1 spine](E1-spine-implementation.md) · [E3 multi-strategy validators](E3-governance-tooling.md) · [Ch.24](../24-repository-encyclopedia.md) · F-012 / F-013
