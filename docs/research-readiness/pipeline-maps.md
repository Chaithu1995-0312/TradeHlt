# Pipeline Maps — 8 Pipelines (2026-06-12)

> **Purpose (Phase 2):** for each pipeline, record inputs · outputs · intermediate artifacts ·
> dependencies · duplicate computations · dead paths · hidden assumptions · consumers. Anchored to
> real modules; cross-links [`signal-flow.md`](../architecture/signal-flow.md) (spine) and
> [`code-map.generated.md`](../architecture/code-map.generated.md). Branch `patch`, v2_multi_2026_04.

## 1. Data Pipeline
- **Inputs:** `data/<INSTR>_M15.csv` (OHLCV M15).
- **Outputs:** streamed `Candle` objects; `DatasetDecision` (APPROVE/WARN/REJECT).
- **Intermediate:** FeaturePipeline matrix (N×38); per-row L1 schema check.
- **Modules:** `data_ingestion/dataset_integrity.py` (L2 sequence/gap, session-aware),
  `data_ingestion/ohlcv_schema.py` (L1 row), `runtime/backtest_v2.py::CandleLoader`.
- **Dependencies:** session model (FX week, daily rollover hour 21).
- **Duplicate computations:** none material.
- **Dead paths:** —
- **Hidden assumptions:** **the `dataset_integrity` *config section* is ABSENT from the active
  v2 config (A-1)** — gate thresholds come from code defaults, not governed config. Loader guard is
  skip-not-abort (a REJECT logs + skips, does not halt).
- **Consumers:** every backtest + training run.

## 2. Decision Pipeline (the CRT spine)
- **Inputs:** `Candle` stream + `CRTConfig` (per-instrument, hash-verified).
- **Outputs:** accept/reject decision + `ExecutionPlan` (entry/SL/TP/RR/TTL).
- **Intermediate:** CRT state transitions, 4 engine scores, fused score, intent classification.
- **Flow:** `engine_runner.EngineRunner.run` (`EXPECTED_ENGINES={crt,gaussian,zone_gate,rr}`) →
  `core/fusion_engine.FusionEngine` → `core/decision_engine.DecisionEngine` →
  `config_layer/execution_planner.ExecutionPlannerV1_2` → `core/ultron_risk_gate.UltronRiskGate`.
- **Dependencies:** LLM tie-breaker (`llm_inference_client`, fail-open → neutral 1.0).
- **Duplicate computations:** intent classification shared via `resolve_breakout_disp_threshold`
  so backtest and live never diverge (good — single source).
- **Dead paths:** TradeNet v2 fusion slot is a permanent stub (F-005); BitNet *adaptive* threshold
  dormant (F-004) and the `bitnet_main_threshold` knob is **hardcoded 0.55** (A-2).
- **Hidden assumptions:** 4 engines mandatory (removing one → silent partial fusion); `CRTState`
  transitions restricted to the 9-state legal map.
- **Consumers:** backtest spine, live_engine_hook.

## 3. Analytics Pipeline
- **Inputs:** decisions + closed trades + capital curve.
- **Outputs:** `BacktestMetrics` (PnL, WR, PF, expectancy, DD R/%, total-return, CAGR, MAR),
  `*_summary.json`, `*_report.txt`.
- **Intermediate:** `TradeJournal`, `CapitalCurve`, `*_crt_telemetry.jsonl`, `*_events.jsonl`,
  feature-drift stats.
- **Modules:** `runtime/backtest_v2.py` (`BacktestRunner`/`MetricsEngine`/`BacktestMetrics`),
  `features/feature_monitor.py`, independent `analytics/metrics_oracle.py`.
- **Duplicate computations:** **resolved** — `analytics/sl_tp_comparator.py` unified onto the oracle;
  `performance.py` + `research/measurement/metrics.py` quarantined (domain-specific, never promotion
  path). Sharpe computed independently only in `governance/portfolio_validation.py` (now oracle-parity-checked, A-3).
- **Dead paths:** —
- **Hidden assumptions:** intrabar-touch is the governing exit model; metrics measure-only (never gated).
- **Consumers:** ConfigValidator, sweeps, research, the metrics oracle parity gate.

## 4. Portfolio Pipeline
- **Inputs:** signals + open positions.
- **Outputs:** ALLOCATE/REJECT + position sizing.
- **Modules:** `portfolio/allocator.PortfolioAllocator`, `exposure_tracker`, `correlation_engine`,
  `capital_policy`.
- **Dead paths:** **ORPHANED (F-013)** — built, not wired; live runs the single-candle spine, no
  ExecutionLoop interposes the allocator.
- **Hidden assumptions:** designed to sit AFTER EngineRunner, BEFORE UltronRiskGate (never realized).
- **Consumers:** none in the live/backtest path (sidecar).

## 5. Validation Pipeline
- **Inputs:** candidate params + per-instrument CSVs.
- **Outputs:** `ValidationReport` (APPROVE/REJECT + hard/soft gate results).
- **Modules:** `config_layer/config_validator.ConfigValidator.validate`.
- **Dependencies:** runs `BacktestRunner` per instrument; thresholds from `config_validator` section.
- **Hidden assumptions:** hard gates (min trades 10, max DD 35%, min fitness 0.15); APPROVE is the
  ONLY path to promotion.
- **Consumers:** `promotion_manager` (mandatory pre-promotion gate).

## 6. Optimization Pipeline
- **Inputs:** base config + expansion plan / sweep grid + CSVs.
- **Outputs:** ranked candidate configs (SAFE/BALANCED/AGGRESSIVE); sweep result JSON (measure-only).
- **Modules:** `expansion/expansion_engine.py` (+ `config_mutator`, `evaluator`,
  `llm_pattern_extractor`); `scripts/analysis/{session,detection}_sweep.py`.
- **Intermediate:** `results/tuner/checkpoint_multi.json`, `results/{session,detection}_sweep/`.
- **Dead paths:** no standalone `auto_tuner.py` in `src/` (orchestrated via
  `scripts/auto_train_from_opportunities.py`); `_FREQ_BOOST` tuner mode is post-TP3 (fails on patch).
- **Hidden assumptions:** sweeps are **measure-only** — never auto-promote.
- **Consumers:** human → `promote_v2.py`.

## 7. Governance Pipeline
- **Inputs:** approved `ValidationReport` / tuner checkpoint.
- **Outputs:** new `configs/production/<version>.json` + SHA-256 + `ACTIVE_VERSION` pointer +
  `promotion_log.jsonl` append.
- **Modules:** `governance/promotion_manager.py`, `config_layer/production_config.py`
  (`get_active_version` fail-fast, hash verify), `core/model_registry.py` (atomic, 2% margin).
- **Dependencies:** Tier-0 `ACTIVE_VERSION` truth (§4.0).
- **Dead paths:** `config_integrity` check is real but **ORPHANED — gates nothing at runtime (F-006)**.
- **Hidden assumptions:** one active version at a time; rollback = restore archived + repoint.
- **Consumers:** every config load (`get_prod_config`).

## 8. Research Pipeline
- **Inputs:** CSVs + registered `Hypothesis` + research config.
- **Outputs:** deterministic `EdgeReport` (per-instrument + pooled), `edge_report.json`.
- **Modules:** `research/runner.HypothesisRunner`, `research/cli.py`, `research/registry.py`,
  `research/measurement/{forward_walk,metrics}.py`, `research/process_characterization.py`.
- **Dependencies:** isolated from the live spine (parallel `src/research/`), shares CSV loader.
- **Duplicate computations:** `research/measurement/metrics.py` is a SEPARATE metrics impl
  (quarantined; not the oracle) — intentional isolation.
- **Dead paths:** —
- **Hidden assumptions:** determinism via sorted iteration + rounded numeric fields + pure functions;
  `src/research/` not yet registered in `codebase-state-map.md` (A-6 doc drift).
- **Consumers:** `auto_train_from_opportunities`, edge-attribution studies.

## Cross-pipeline observations
- **Single biggest structural risk:** config↔code split-brain (A-1/F-016) — the active config feeds
  pipelines 1/3/7 with a schema older than HEAD code expects.
- **Orphaned-but-built:** Portfolio (4), multi-signal ExecutionLoop (F-013), `config_integrity` (F-006),
  TradeNet (F-005) — all flagged so research does not assume they run.
- **Determinism:** proven byte-identical end-to-end (pipelines 1→3) for 2 instruments (Phase 5).
