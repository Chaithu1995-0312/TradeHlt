# Integration Audit — Unified Execution Spine
**Date:** 2026-05-02  
**Auditor:** Senior Systems Architect  
**Scope:** All `src/` modules; 176 Python files across 30+ subpackages  

---

## Audit Method

1. Grepped all `from.*inout`, `MT5Bridge`, `DecisionEngine`, `"execute"` string emissions across `src/`.  
2. Grepped all custom candle loops (`for.*candle`, `iterrows`, `itertuples`) outside `BacktestRunner`.  
3. Read `src/inout/__init__.py`, `src/governance/strategy_backtest.py`, `src/regime/`, `src/journal/trade_logger.py`, `src/core/feature_store.py`.

---

## Section 1 — Bypass Findings (Spine Violations)

### 1.1 `src/inout/` — Parallel Execution Pipeline

| Attribute | Detail |
|-----------|--------|
| Severity | **HIGH** |
| Files | `inout/controller.py`, `state_machine.py`, `executor.py`, `runner.py`, `probability_engine.py` (47KB), `scanner.py`, `db.py`, `config.py` |
| Importers in `src/` | **NONE** — zero production imports |
| Importers in `tests/` | `tests/inout/test_inout-1.py`, `tests/inout/test_probability_engine.py` |
| Violation | `inout/__init__.py` explicitly states "Runs PARALLEL to the main EngineRunner pipeline — zero shared state" and "ExecutionPlannerV1_2 → NOT USED". This is a confirmed alternative execution loop bypassing the canonical spine. |
| Additional violation | `inout/db.py` uses SQLite persistence — violates CLAUDE.md §4 no-DB convention. |
| Action | **ARCHIVE** → `archive/inout_legacy/` before Phase 4. Delete corresponding tests or move to `tests/archive/`. |

### 1.2 `src/governance/strategy_backtest.py` — Custom Forward-Sim Loop

| Attribute | Detail |
|-----------|--------|
| Severity | **MEDIUM** |
| File | `src/governance/strategy_backtest.py` |
| Violation | `StrategyBacktester` builds its own candle loop using `FeaturePipeline` + strategy `.compute()` calls + manual forward-scan for TP/SL. Does NOT call `BacktestRunner`. Governance validation therefore runs a different execution path than production. |
| Called by | `src/governance/multi_strategy_validator.py` — the governance gate depends on this |
| Action | **REWRITE** `StrategyBacktester._run_candle_loop()` → delegate to `BacktestRunner`. TP/SL labeling logic must match `backtest_v2.py` exactly (live engine is the reference for divergences). |

### 1.3 `src/journal/trade_logger.py` — Split Audit Trail

| Attribute | Detail |
|-----------|--------|
| Severity | **LOW** |
| File | `src/journal/trade_logger.py` |
| Violation | `TradeLogger.log()` writes to `logs/trade_journal.jsonl` independently of `core/collector.py`. This creates a second JSONL event sink not visible to governance audits. |
| Current importers | Not found in `src/` scan — appears unused in live path |
| Action | **REWRITE** `TradeLogger.log()` to call `core/collector.Collector.collect()` as backend. Keep `logs/trade_journal.jsonl` path as the write target but route through Collector. |

---

## Section 2 — Missing Wiring (Integration Gaps)

### 2.1 `src/regime/` — Not Injected into EngineRunner Context

| Attribute | Detail |
|-----------|--------|
| Severity | **MEDIUM** |
| Files | `src/regime/regime_classifier.py`, `src/regime/config_router.py` |
| Gap | `RegimeClassifier.classify(features)` → returns `TRENDING | RANGING | HIGH_VOLATILITY`. `ConfigRouter.route(regime)` → returns fusion weight profile. Neither is called from `live_engine_hook.process()` or `BacktestRunner`. The `EngineRunner.run()` context dict never receives `{"regime": ...}` from these classes. |
| Impact | Regime-aware fusion weight selection (`ConfigRouter.DEFAULT_FUSION_WEIGHTS`) is dead code — FusionEngine cannot use regime-specific weights without injection. |
| Action | **INTEGRATE** in Phase 3: call `RegimeClassifier.classify()` in `live_engine_hook.process()` before `EngineRunner.run()`; inject `{"regime": label, "fusion_weights": weights}` into context dict. |

### 2.2 `src/scanner/` — No Path to EngineRunner

| Attribute | Detail |
|-----------|--------|
| Severity | **MEDIUM** |
| Files | `src/scanner/scanner.py`, `ranker.py`, `signal_pool.py`, `universe.py` |
| Gap | `Scanner.scan()` → `Ranker.rank()` → `SignalPool` produces candidate symbol/candle pairs. No `SpineAdapter` exists to route these into `EngineRunner.run()`. Scanner signals bypass the entire decision pipeline. |
| Action | **CREATE** `src/scanner/spine_adapter.py` in Phase 2 wrapping `EngineRunner.run()`; update `Scanner` to call `SpineAdapter.evaluate()` for each candidate. |

### 2.3 `StrategyOrchestrator` — Runs in Parallel to FusionEngine

| Attribute | Detail |
|-----------|--------|
| Severity | **HIGH** |
| File | `src/runtime/live_engine_hook.py` (~line 600+), `src/core/fusion_engine.py` |
| Gap | `live_engine_hook` runs `StrategyOrchestrator.compute()` after `EngineRunner.run()` and merges results into output dict in parallel — not inside FusionEngine. This means 10-strategy consensus is a post-hoc overlay, not a scored input to the canonical fusion computation. Two signals coexist with no priority rule. |
| Decision | **5th engine architecture** (approved): `StrategyOrchestrator` result is injected as a 5th weighted score (`strategy_consensus`) into `FusionEngine.compute()` inside `EngineRunner`. The parallel call in `live_engine_hook` is removed. |
| Action | See Phase 3 task: Wire StrategyOrchestrator as 5th engine. |

---

## Section 3 — Confirmed Clean (No Bypass)

| Area | Finding |
|------|---------|
| `MT5Bridge` usage | Called ONLY from `live_engine_hook.py` (correctly after UltronRiskGate APPROVE) and `health_checker.py` (health probe, no orders placed). No unauthorized bypass. |
| `DecisionEngine` import | Imported ONLY in `src/core/engine_runner.py:28`. No module calls it directly outside the spine. |
| `"execute"` string emission | `src/core/decision_engine.py:172` — sole authority. `execution_planner.py:334,636` emits `"execute"` in its own `trade_plan.decision` domain (different semantic, not engine decision). Acceptable. |
| `src/inout/` → `UltronRiskGate` | `inout/controller.py` imports `UltronRiskGate` READ ONLY (not calling it as a bypass — controller uses it for a pre-check). Risk gate is not bypassed. |

---

## Section 4 — Orphan / Dead Module Map

| Module | Status | Importers in src/ | Action |
|--------|--------|-------------------|--------|
| `src/inout/probability_engine.py` | DEAD — parallel decision engine | 0 | ARCHIVE |
| `src/inout/state_machine.py` | DEAD — parallel orchestration | 0 | ARCHIVE |
| `src/inout/controller.py` | DEAD — parallel loop | 0 | ARCHIVE |
| `src/inout/executor.py` | DEAD — parallel executor | 0 | ARCHIVE |
| `src/inout/runner.py` | DEAD — parallel runner | 0 | ARCHIVE |
| `src/inout/scanner.py` | DEAD — duplicates `src/scanner/` | 0 | ARCHIVE |
| `src/inout/db.py` | DEAD — SQLite, violates no-DB | 0 | ARCHIVE |
| `src/inout/config.py` | DEAD — inout config | 0 | ARCHIVE |
| `src/ui/dashboard.py` | DEAD — stub, superseded by control_plane SPA | 0 | ARCHIVE |
| `src/bitnet/_smoke_test.py` | TEST ARTIFACT | 0 | DELETE → move to tests/ |
| `src/journal/trade_logger.py` | SPLIT AUDIT TRAIL | 0 in live path | REWRITE → delegate to Collector |

---

## Section 5 — Custom Candle Loop Violations

| File | Loop | Violation? |
|------|------|-----------|
| `src/governance/strategy_backtest.py` | Custom forward-sim (max_forward_candles) | **YES** — must use BacktestRunner |
| `src/uat/uat_runner.py:142,177,364` | Test case iteration | NO — UAT test harness, not decision logic |
| `src/features/feature_pipeline.py:618` | `iterrows` for drift stats | NO — feature engineering, not trade decision |
| `src/runtime/backtest_v2.py:1282,1691` | Main backtest loop | NO — this IS BacktestRunner |
| `scripts/backtest/manual_backtest.py:350` | Manual analysis script | NO — in scripts/, not production src/ |
| `src/config_layer/crt_engine_v2.py:417,1390` | CRT pattern detection | NO — engine internal, not a backtest loop |

---

## Section 6 — Phase Readiness Summary

| Phase | Blocker? | Notes |
|-------|----------|-------|
| Phase 2 (Interfaces) | None — additive | Add `src/core/types.py`, `FeatureStore.validate_or_raise()`, `SpineAdapter` |
| Phase 3 (Reroute) | `strategy_backtest.py` rewrite is the critical path | Must not break `MultiStrategyValidator` output schema |
| Phase 4 (Archive) | Audit for inout test deps | `tests/inout/` must be moved or deleted before archiving `src/inout/` |

---

## Appendix — Files Checked

- `src/inout/__init__.py` — docstring confirms parallel architecture
- `src/governance/strategy_backtest.py` — custom loop lines 113–180
- `src/regime/regime_classifier.py` — `RegimeClassifier.classify()` signature
- `src/regime/config_router.py` — `ConfigRouter` + `DEFAULT_FUSION_WEIGHTS`
- `src/journal/trade_logger.py` — `TradeLogger.log()` writes to own JSONL
- `src/core/feature_store.py` — `process()`, `_validate_schema()` (internal only, no public `validate_or_raise`)
- `src/runtime/live_engine_hook.py` — `MT5Bridge` gating, `StrategyOrchestrator` parallel call
- `src/monitoring/health_checker.py` — `MT5Bridge` health probe only (not order placement)
