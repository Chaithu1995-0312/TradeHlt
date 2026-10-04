# Plan — Market Reality: Independent Formula Probes + Config Contract

## Context

We are moving `OHLCFeatureMap` toward a layered Market Reality architecture (Raw OHLCV → verified
canonical feature math → 38-feature observation surface → `MarketRealityHistoryBuffer` → configured
causal temporal derivations → configured Market Reality dimensions → `MarketRealitySnapshot` →
evidence consumers). The Market Reality layer must launch **observe-only, zero decision authority**.

This task is **evidence-gathering + a config contract only**. It produces three deliverables and
changes **no production code or behavior**. Per the governing contamination rule, every prior verdict
(CLOSED / PASS / PIT_CERTIFIED / finding conclusions / config comments / test pass counts) is treated
as *potentially contaminated* and must be independently reconstructed from current implementation and
fresh execution probes. ChatGPT is separately doing the SET A/B/C static classification; **this task
returns evidence to support/reject provisional classifications, not final A/B/C closure.**

## Deliverables (the ONLY files created)

1. `reports/analysis/market-reality-fresh-probes-2026-07-12.md` (Report 1 — WP1 + WP2)
2. `reports/analysis/market-reality-repository-search-2026-07-12.md` (Report 2 — WP3)
3. `configs/market_reality/market_reality_v1.yaml` (WP4 — config contract, no formulas)

Temp probe scripts go in the scratchpad (not committed) unless repo policy requires committed
reproducibility; exact commands + inline probe code are recorded in Report 1.

## Hard constraints (from the task)

- Do NOT modify production formulas, CRT, EngineRunner, Fusion, DecisionEngine, ExecutionPlanner,
  risk controls. Do NOT retrain models. Do NOT add canonical features. Do NOT implement the Market
  Reality runtime. Do NOT claim SET A/B/C closure.
- YAML must NOT contain executable formulas / Python expressions / hidden fallbacks / decision authority.
- Config must fail closed: `enabled: false`, `mode: observe_only`, all `authority.*: false`.

<!-- Exploration findings and detailed work-package steps appended below after agent results. -->
