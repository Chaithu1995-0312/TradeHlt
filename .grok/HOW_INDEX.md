# How-index — topics × Excel files

Generated 2026-09-03 from `docs/topics/*.md` + the three functionality Excels.
This file is the **How** extract. GROK.md points here. Do not paste this into GROK.md.

Workbooks (file-list, generated 2026-09-03; GCMC is listed ∩ disk — see `.grok/CLOSURE_KPI.md`):

| Workbook | Unique files | Role in How |
|---|---:|---|
| `results/analysis/src_business_functionality.xlsx` | 592 | Does this `src/` file exist as inventoried behavior? |
| `scripts_business_functionality.xlsx` | 408 | Does this `scripts/` helper exist? |
| `docs/analysis/tests_functionality_inventory.xlsx` (`By File`) | 531 | Which test file covers a claim? |

GCMC v1: see `.grok/CLOSURE_KPI.md`. This extract lists topic Ins/Outs; the KPI is file-list intersection.

## How a trader claim uses this file

1. Name the **topic** (meaning).
2. Read **Ins / Outs** (contract: what goes in, what is allowed out).
3. Open the **code files** cited (existence / current behavior).
4. Confirm the file is in the matching Excel (inventory).
5. Only then ask money (`P-GOAL-04`). Ins/outs that forbid TRADE_OPENED cannot mint an edge.

## Needed vs useful

- **NEEDED** — required to validate a money/structure/execution claim.
- **USEFUL** — real topics; sidecar, orphan, search, or not-yet-authoritative.
- **OTHER** — extracted but not classified above.

## Topic extract

### NEEDED — Topic: BitNet Gate

- File: [`docs/topics/bitnet-gate.md`](../docs/topics/bitnet-gate.md)
- Why for How: Hard-reject when enabled; inert on active patch.
- Plain: BitNet is a small neural model that scores a candidate trade's features and, **when enabled**, acts as a **hard-reject gate** (score `< bitnet_main_threshold`, default `0.55` → `RejectReason.LOW_SCORE`). It is **not** a fusion engine and **not** TradeNet.
- **Ins:** the CRT feature dict (BitNet reads a fixed legacy subset); model artifact (`model.json` / export schema) under `models/`; config `get_prod_section("crt_engine")` → `bitnet_main_threshold`.
- **Outs:** a `bitnet_main_score ∈ [0,1]`; a hard ACCEPT/REJECT branch in CRT; the score + decision persisted to the trade record (and CSV export) for later attribution.
- Cited files: `src/bitnet/bitnet_inference.py`, `src/config_layer/crt_engine_v2.py`, `src/runtime/backtest_v2.py`, `tests/test_bitnet_inference.py`, `tests/test_bitnet_parity.py`

### NEEDED — Topic: Config Validation

- File: [`docs/topics/config-validation.md`](../docs/topics/config-validation.md)
- Why for How: What APPROVE on a config actually promises.
- Plain: `ConfigValidator` decides whether a candidate config is fit for production. It runs a per-instrument backtest, computes a fitness score, and applies **hard gates** (must pass) and **soft gates** (warn) — then returns a structured `ValidationReport` with `decision` = `APPROVE` or `REJECT`.
- **Ins:** `params` (CRTConfig-compatible dict), `csv_paths` (`{instrument: path}`), `config_id`; config section `config_validator`.
- **Outs:** `ValidationReport` dict (`:332`): `{decision: APPROVE|REJECT, config_id, validated_at, params, metrics{final_score,mean_score,...}, per_instrument{}, instruments_tested[], hard_failures[], warnings[]}`.
- Cited files: `src/config_layer/config_validator.py`, `src/config_layer/production_config.py`, `src/config_layer/__init__.py`, `src/config_layer/stack_version.py`, `src/utils/config_dumper.py`, `src/utils/isolated_config_root.py`, `src/utils/registry_refresh.py`, `tests/test_fusion_and_validator_regression.py`

### NEEDED — Topic: CRT Spine (candle → order)

- File: [`docs/topics/crt-spine.md`](../docs/topics/crt-spine.md)
- Why for How: Incumbent structure path (Sense A). Candle to order.
- Plain: The "spine" is the straight line every candle walks: score it through four engines, fuse the scores into one decision, plan the trade (entry / stop / target), and let a risk gate approve or reject. The CRT engine is the backbone of that line — it tracks market structure through a fixed 9-state graph (`RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION → RESOLUTION`, plus the `SHADOW_PENDING` and `EXPIRED`…
- **Ins:** an M15 `Candle` stream (see `docs/reference/schemas.md`); production config sections (`crt_engine`, `fusion_engine`, `decision_engine`, `execution_planner`, `ultron_risk_gate`) via `get_prod_section(...)`.
- **Outs:** per-candle decision → optional `ExecutionPlan` (entry/SL/TP/RR/TTL) → terminal APPROVE/REJECT; events streamed to `logs/` JSONL (e.g. `TRADE_OPENED`, `EXPANSION_EXPIRED`).
- Cited files: `src/config_layer/state_identity.py`, `src/config_layer/state_topology.py`, `docs/governance/crt_executable_state_graph.json`, `src/config_layer/crt_engine_v2.py`, `src/runtime/parent_crt_feed.py`, `src/config_layer/htf_state.py`, `src/core/engine_runner.py`, `src/config_layer/crt_config_completeness.py`, `src/config_layer/crt_config_provenance.py`, `src/config_layer/crt_identity_schema.py`, `src/config_layer/crt_sweep_taxonomy.py`, `src/config_layer/state_contract.py`, `src/config_layer/state_contract_loader.py`, `src/config_layer/_crt_state_generated.py`, `src/features/smc/__init__.py`, `src/features/smc/_geometry.py`, `src/features/smc/breaker.py`, `src/features/smc/choch.py`, `src/features/smc/fvg.py`, `src/features/smc/levels.py`, `src/features/smc/mitigation.py`, `src/features/smc/order_block.py`, `src/structure/__init__.py`, `src/structure/predicates.py`

### NEEDED — Topic: Execution Planning

- File: [`docs/topics/execution-planning.md`](../docs/topics/execution-planning.md)
- Why for How: Entry/SL/TP geometry after approval.
- Plain: Once the decision engine says "execute," the **execution planner** turns that decision into a deterministic trade plan: validate the inputs, derive the entry, attach a trade intent, TTL, and position-size hint, and produce a trace. It is intentionally *not* the scorer — it only consumes decision outputs.
- **Ins:** `engine_result` (from `EngineRunner.run()`), canonical `features` dict, `context` (`symbol/signal/score`, optional `account_balance`); config section `execution_planner` (intent-specific TP multipliers, TTLs, `min_rr_ratio`, `default_sl_atr_mult`, `risk_percent`).
- **Outs:** trade plan dict (`execution_id`, `trade_intent`, `entry_price`, gate result, `trace`). SL/TP/RR populated later by the live hook.
- Cited files: `src/config_layer/execution_planner.py`, `src/execution/__init__.py`, `src/execution/execution_intent_v1_0.py`, `tests/test_execution_planner.py`, `tests/test_execution_contract_v1.py`, `tests/test_sl_tp_comparator.py`

### NEEDED — Topic: Feature Schema, Pipeline & Drift

- File: [`docs/topics/feature-schema.md`](../docs/topics/feature-schema.md)
- Why for How: What numbers every engine sees; leakage risk.
- Plain: Every engine scores the same fixed, ordered list of numbers per candle — the **canonical feature vector**. Its order is frozen and hashed so a model trained on one ordering can never be silently fed another.
- **Ins:** raw OHLCV DataFrame (timestamp/open/high/low/close; volume optional → 0.0 for FX). Drift monitor consumes `retest_depth`, `body_ratio`, `disp_strength` per opened trade.
- **Outs:** a 48-float vector in canonical order + enriched df (`FeaturePipeline.run`); `build_features(row)` → 48-key dict; drift severity (`"hard"|"soft"|"none"`) attached to backtest output (`BacktestMetrics.distribution["feature_drift"]`).
- Cited files: `src/features/feature_schema.py`, `src/features/feature_pipeline.py`, `src/features/feature_monitor.py`, `src/features/dataset_validator.py`, `src/core/feature_store.py`, `src/data_ingestion/__init__.py`, `src/data_ingestion/clock_detector.py`, `src/data_ingestion/clock_registry.py`, `src/data_ingestion/session_autoderive.py`, `src/data_ingestion/xauusd_phase1_candidate.py`, `src/features/__init__.py`, `src/features/broker_clock.py`, `src/features/calendar_periods.py`, `src/features/dataset_builder.py`, `src/features/feature_builder.py`, `src/features/feature_identity.py`, `src/features/fm_resolve.py`, `src/features/gaussian_schema_contract.py`, `src/features/magnitude_states.py`, `src/features/market_context.py`, `src/features/market_reality_contract.py`, `src/features/market_shape.py`, `src/features/model_evidence.py`, `src/features/parent_candle.py`

### NEEDED — Topic: Fusion + Decision

- File: [`docs/topics/fusion-decision.md`](../docs/topics/fusion-decision.md)
- Why for How: Who may approve a decision.
- Plain: After the four engines (CRT, Gaussian, Zone Gate, RR) each score a candle, **fusion** combines them into a single `final_score` under regime-aware weights, and the **decision engine** turns that score (plus probability and RR) into APPROVE or a typed REJECT. Fusion is *aggregation only* — it does not decide; the decision engine is the gatekeeper, but it scores against a **dynamic threshold** (the recent score distri…
- **Ins:** `engine_results` dict (`crt/gaussian/zone_gate/rr` scores), optional `weights`/`regime`; config sections `fusion_engine` and `decision_engine` (`score_threshold`, `p_win_threshold`, `weak_link_weight`, `weak_component_threshold`). *DecisionEngine reads no RR knob — `rr_threshold` RETIRED, F-048 resolved 2026-07-24; economic reward:risk is owned by `ultron_risk_gate.min_rr_ratio`, not by the decision surface.*
- **Outs:** fusion → `{final_score, scores{}, normalized_score, missing_engines?, reason?}`; decision → `{decision: APPROVE|REJECT, reject_reason?, threshold, ...}`.
- Cited files: `src/core/fusion_engine.py`, `src/core/decision_engine.py`, `src/core/engine_runner.py`, `src/core/__init__.py`, `src/core/backtest_port.py`, `src/core/dynamic_threshold.py`, `src/core/governance_mode.py`, `src/core/hierarchical_meta_fusion.py`, `src/core/signal_belief_tracker.py`, `src/core/types.py`, `src/runtime/analyze_fusion_shadow.py`, `tests/test_engine_runner_rr_fusion.py`, `tests/test_fusion_and_validator_regression.py`, `tests/test_analyze_fusion_shadow.py`, `tests/test_engine_runner_dual_gate.py`

### NEEDED — Topic: Goal Layer (economic-objective layer)

- File: [`docs/topics/goal-layer.md`](../docs/topics/goal-layer.md)
- Why for How: G001 / earn-money metric ownership.
- Plain: The Goal Layer is the system's single, machine-readable statement of **what success means in business terms** — trades/month, RR, drawdown, expectancy — frozen as goal id **G001** in the active production config. It exists because the codebase was rich in engines and fusion but had no explicit economic objective above them: you could optimize a config to a great fitness score and still drift away from the trading ou…
- **Ins:** the `goal` section of `configs/production/<ACTIVE_VERSION>.json` via `get_prod_section("goal")` (G001: `trades_per_month` {min/target/max}, `avg_rr`, `win_rate`, `max_drawdown_pct`, `risk_per_trade`, `expectancy_r`, `timeframe`, `instruments`, `constraints`, `enforce`); measured metrics dict (`trades_per_month`, `win_rate`, `max_drawdown_pct`, `expectancy_r`; `avg_rr` reports SKIP — no faithful aggregate metric).
- **Outs:** `GoalReport.to_dict()` `{enabled, enforced, goal_id, decision: PASS|FAIL, criteria:[{name, comparator, target, actual, gap, status}]}` — surfaced in `BacktestMetrics.to_dict()["distribution"]["goal_report"]`.
- Cited files: `src/config_layer/goal_schema.py`, `src/config_layer/goal_validator.py`, `src/runtime/backtest_v2.py`, `src/config_layer/config_validator.py`, `tests/test_goal_schema.py`, `tests/test_goal_validator.py`, `tests/test_goal_metrics.py`, `tests/test_resample_completeness.py`

### NEEDED — Topic: Live Execution (live order/data path)

- File: [`docs/topics/live-execution.md`](../docs/topics/live-execution.md)
- Why for How: Whether a live book even exists (F-073).
- Plain: In replay, candles come from CSVs and nothing is ordered. **Live** is the other half: candle fetchers pull fresh OHLCV, a hooked live engine runs the same engines→planner→risk-gate spine, and an approved trade is sent to **MT5** with a **Telegram** alert, behind a **kill-switch** and a human override gate.
- **Ins:** live OHLCV (fetchers) + per-tick features + portfolio state; config `get_prod_section("live_integration")` (mt5/telegram toggles, dry_run) and `get_prod_section("inout")`.
- **Outs:** MT5 orders, Telegram messages, and a per-tick `outcome` dict (incl. `drift_severity`, kill-switch block flags); trade outcomes feed `register_trade_outcome()` → kill-switch accounting.
- Cited files: `src/runtime/live_engine_hook.py`, `src/live/mt5_bridge.py`, `src/live/telegram_bridge.py`, `src/inout/alphavantage_candle_fetcher.py`, `src/inout/hummingbot_candle_fetcher.py`, `src/execution/loop.py`, `src/live/__init__.py`, `src/live/order_manager.py`, `src/inout/live_rail/__init__.py`, `src/inout/live_rail/bar_builder.py`, `src/inout/live_rail/binance_ws_adapter.py`, `src/inout/live_rail/config.py`, `src/inout/live_rail/factory.py`, `src/inout/live_rail/longport_adapter.py`, `src/inout/live_rail/ohlcv_replay_port.py`, `src/inout/live_rail/resilience.py`, `src/inout/live_rail/tickdb_adapter.py`, `src/inout/live_rail/types.py`, `src/runtime/live_rail_feeder.py`, `src/runtime/live_rail_orchestrator.py`, `src/runtime/__init__.py`, `tests/test_live_integration.py`, `tests/test_execution_loop.py`

### NEEDED — Topic: Model Intent & Feature Ownership

- File: [`docs/topics/model-intent-and-feature-ownership.md`](../docs/topics/model-intent-and-feature-ownership.md)
- Why for How: Who owns which market question (MIAR).
- Plain: The system scores each candle through four fused engines (CRT, Gaussian, ZoneGate, RR) plus a BitNet hard-reject gate and a regime/dual-engine layer. A recurring question (raised by `reports/OHLCV_LINEAGE_FORENSICS.md` + `reports/FEATURE_REACHABILITY_AUDIT.md`) is whether the ~20 canonical features only consumed by ZoneGate are "dead." This topic answers the **prior** question instead: *what was each model designed …
- **Ins:** the 38-dim `CANONICAL_FEATURES` vector (`src/features/feature_schema.py:46`); raw `Candle` (OHLCV) for CRT; config sections `engine_runner.*` (incl. `zone_registry_path`, `zone_mode`) and `fusion_engine.*`.
- **Outs:** per-engine scores → `FusionEngine` final score → `DecisionEngine` ACCEPT/REJECT/BLOCK.
- Cited files: `src/config_layer/crt_engine_v2.py`, `src/engines/heuristic_gaussian_engine.py`, `src/engines/rr_engine.py`, `src/engines/zone_gate_engine.py`, `src/engines/live_engine.py`, `src/bitnet/zone_cosine_searcher.py`, `src/bitnet/bitnet_inference.py`, `src/core/engine_runner.py`, `src/core/fusion_engine.py`, `tests/test_topic_docs.py`, `tests/test_current_findings.py`, `src/features/feature_schema.py`

### NEEDED — Topic: Promotion / Governance

- File: [`docs/topics/promotion-governance.md`](../docs/topics/promotion-governance.md)
- Why for How: What may enter production.
- Plain: `PromotionManager` is the gate between a validated config and production. It refuses to promote anything whose `ValidationReport.decision != "APPROVE"`, and — when given the CSVs — **re-runs validation** before promoting so a stale or hand-edited report can't sneak through.
- **Ins:** an approved `ValidationReport` JSON path (or tuner checkpoint), a `version` label (e.g. `v1_multi_2026_03`), `csv_paths` for re-validation; config section `governance`.
- **Outs:** promotion result `{status, paths}`; production registry updated; `promotion_log.jsonl` line appended; archived prior config as `{version}_archived_{ts}.json`.
- Cited files: `src/governance/promotion_manager.py`, `configs/promotion_log.json`, `src/governance/config_integrity.py`, `scripts/maintenance/_promote_v4_bnb_cutover.py`, `tests/test_shadow_promotion_gate.py`, `tests/test_sprint7_governance.py`, `tests/test_meta_governor_executor.py`

### NEEDED — Topic: Research Measurement Contract

- File: [`docs/topics/research-measurement-contract.md`](../docs/topics/research-measurement-contract.md)
- Why for How: How a money claim must be measured.
- Plain: Production config is governed — `ACTIVE_VERSION` + SHA-256 + `promotion_log.jsonl` mean nobody can *infer* what was live. The instrument that judges production — research — had no equivalent: which label definition, cost model, gate mode, or clock basis a result used lived as an untracked `.env` value or a per-script literal.
- **Ins:** the frozen schema's 7 surfaces per experiment; a profile's `surface_defaults` per asset
- **Outs:** a sealed `MC-*` instance (none exist yet); a profile `profile_hash` once `FROZEN` (none
- Cited files: `docs/governance/MEASUREMENT_CONTRACT.md`, `docs/governance/measurement_contract.schema.json`, `docs/governance/e_mt_01_adversarial_mutation_matrix.json`, `docs/governance/research_family_registry.json`, `configs/research/measurement_contracts/crypto_majors.v1.json`, `scripts/research/gate_measurement_m_gate_01.py`, `docs/research/parquet_evidence_layer.md`, `docs/current-findings.md`, `src/identity/__init__.py`, `src/identity/certify.py`, `src/identity/check.py`, `src/identity/hashes.py`, `src/identity/outcome.py`, `src/identity/query.py`, `src/identity/store.py`, `src/identity/tokens.py`, `tests/test_measurement_contract.py`, `tests/test_research_family_registry.py`, `docs/knowledge-map.md`, `tests/test_current_findings.py`, `tests/test_closure_authority_index.py`, `tests/research/test_evidence_layer.py`

### NEEDED — Topic: Scoring Engines (Gaussian · Zone-Gate · RR)

- File: [`docs/topics/scoring-engines.md`](../docs/topics/scoring-engines.md)
- Why for How: What Gaussian/Zone/RR actually score (not p(win)).
- Plain: Every candle is scored by **four independent engines**, then fused. CRT reads market structure; the other three are here: **Gaussian** (a probability score — a fast heuristic kernel or a trained ML model), **Zone-Gate** (a BitNet-backed zone/geometry validator), and **RR** (a candle-polarity / reward-risk quality score).
- **Ins:** a canonical feature dict (see `feature-schema.md`) + `direction`; Gaussian heuristic needs `ema_fast/ema_slow/momentum_score`, RR needs `close/high/low`, Zone-Gate needs the canonical vector + a `model_fn` + optional zone registry. Config: `get_prod_section("engine_runner")` (impl/mode selectors) and `get_prod_section("fusion_engine")` (per-engine weights).
- **Outs:** per-engine `dict{score, reason, meta…}` collected into `engine_results = {crt, gaussian, zone_gate, rr}`, then fused (`FusionEngine.compute`). Fusion weights (v1 config): crt 0.4 / gaussian 0.2 / zone_gate 0.2 / rr 0.2, with regime-aware overrides.
- Cited files: `src/engines/heuristic_gaussian_engine.py`, `src/engines/ml_gaussian_engine.py`, `src/engines/rr_engine.py`, `src/engines/zone_gate_engine.py`, `src/core/engine_runner.py`, `src/engines/__init__.py`, `src/engines/gaussian_engine.py`, `src/engines/tradenet_meta_engine.py`, `src/engines/zone_cluster_score.py`, `tests/test_gaussian_impl_switch.py`, `tests/test_zone_gate.py`, `tests/test_engine_runner_rr_fusion.py`, `tests/test_fusion_and_validator_regression.py`

### NEEDED — Topic: Ultron Risk Gate

- File: [`docs/topics/ultron-risk-gate.md`](../docs/topics/ultron-risk-gate.md)
- Why for How: Final risk/money gate.
- Plain: `UltronRiskGate` is the **sole execution authority** — the final, deterministic gate that consumes the execution plan plus portfolio state and returns approve/reject with the final position size. It runs seven checks in a fixed order and rejects on the first failure, so a trade only passes if *every* risk condition holds.
- **Ins:** `trade` (execution-plan dict: entry/SL/TP/RR/TTL), `portfolio_state` (open exposure, daily P&L, trade count); config section `ultron_risk_gate`.
- **Outs:** `{decision: APPROVE|REJECT, reject_reason?, final_position_size}`; on approve, the trade is sized and released; kill-switch state may be written to disk.
- Cited files: `src/core/ultron_risk_gate.py`, `src/core/ultron_risk_gate_wrapper.py`, `src/runtime/live_engine_hook.py`, `src/core/ultron_live_adapter.py`, `tests/test_ultron_risk_gate.py`, `tests/test_ultron_gate.py`, `tests/test_ultron_wrapper.py`

### USEFUL — Topic: AI Automation Agent

- File: [`docs/topics/ai-automation-agent.md`](../docs/topics/ai-automation-agent.md)
- Why for How: Operator agent; not a strategy.
- Plain: **GrokAgenticAI** lets an operator drive the kitchen in plain English ("Ask GrokAgenticAI …"). It **classifies** the request into an intent, then either: 1.
- **Ins:** NL (`Ask GrokAgenticAI …`); `intent_patterns.json`; config `agent` section; optional `--agent ops_doctor|campaign_runner`.
- **Outs:** goal/linear execution; `logs/agent_audit.jsonl` + intent log; OpsDoctor packs under `results/incidents/`.
- Cited files: `src/agent/grok_agentic.py`, `src/agent/goal.py`, `src/agent/goal_loop.py`, `src/agent/modes/ops_mode.py`, `src/agent/modes/truth_mode.py`, `src/agent/intent_router.py`, `src/agent/plan_compiler.py`, `src/agent/executor.py`, `src/agent/agent_core.py`, `src/agent/cli.py`, `tests/test_grok_agentic_ai.py`, `tests/test_agent_intent_router.py`, `tests/test_agent_plan_compiler.py`, `tests/test_agent_tool_registry.py`, `tests/test_agent_executor_confirm.py`

### USEFUL — Topic: Analytics — SL/TP Comparator

- File: [`docs/topics/analytics-sltp.md`](../docs/topics/analytics-sltp.md)
- Why for How: What-if exits on identical entries.
- Plain: Given a set of trades that already happened, this asks a clean what-if: if we'd placed stops/targets the CRT way vs the legacy ATR way — on the *identical* entries — which would have made more money? It re-simulates exits candle-by-candle for both methods and reports aggregate metrics (win rate, expectancy, drawdown) plus a recommended winner.
- **Ins:** `trade_records` (with entry/SL/TP/features) + `candles`; `cfg` (legacy ATR mults, primary metric). Reads a trades CSV in the backtest wrapper.
- **Outs:** `ComparisonReport` (`.to_dict()` / `.save_json()` / `.print_summary()`) — CRT vs legacy aggregates, winner + delta, recommendation.
- Cited files: `src/analytics/sl_tp_comparator.py`, `src/analytics/clustering.py`, `tests/test_sl_tp_comparator.py`

### USEFUL — Topic: Capital Pressure Ratio (CPR) — Capital Semantics Layer

- File: [`docs/topics/capital-pressure-ratio.md`](../docs/topics/capital-pressure-ratio.md)
- Why for How: Named latent; not validated; no TRADE_OPENED.
- Plain: Markets move because capital seeks opportunities on one side or the other. This topic names that idea carefully: **Capital Pressure Ratio (CPR)** is a *latent* imbalance between buy-seeking and sell-seeking capital.
- **Ins:** - **Ins (proposed latent):** Global capital → Investment pool → BI, SI → CPR = BI/SI (candidate formula; **not validated**). - **Outs (proposed manifestation):** OHLC body/range/ATR/displacement/sweep/retest/continuation — already measured by the existing feature + CRT stack.
- **Outs:** (none extracted)
- Cited files: `configs/formulas/market_ontology.yaml`, `configs/research/measurement_contracts/MC-CPR-L0-XAUUSD-M15-UTC-V1.json`, `docs/research-readiness/mc-cpr-l0-xauusd-m15-preregistration.md`, `tests/test_semantic_registry.py`, `src/core/ultron_risk_gate.py`, `src/config_layer/crt_engine_v2.py`, `src/features/feature_pipeline.py`

### USEFUL — Topic: Context Report

- File: [`docs/topics/context-report.md`](../docs/topics/context-report.md)
- Why for How: Control-plane run explainer.
- Plain: Context Report is the 🧠 button next to a finished run in the control-plane UI. Click it and the system gathers everything about that run — the command line, the last chunk of stdout/stderr, the artifacts it produced, and (the clever part) the **actual Python functions that ran** — and asks Claude to explain, in structured form, *why the run did what it did* and *what to do next*.
- **Ins:** `run` dict (command_id, status, exit_code, args, command_line), `logs` (stdout/stderr), `artifacts` (path/exists/size list), and the derived `code_context` (AST symbol blocks). `ANTHROPIC_API_KEY` from `.env`/env.
- **Outs:** `{"ok": True, "sections": {root_cause, architecture_notes, artifact_analysis, recommendations[]}, "model", "code_context_count"}` — or `{"ok": False, "error": ...}`. Model: `claude-haiku-4-5-20251001`, `max_tokens=1024`, `temperature=0.1`.
- Cited files: `src/control_plane/code_context_extractor.py`, `src/control_plane/context_report.py`, `src/control_plane/server.py`

### USEFUL — Topic: Event Fabric

- File: [`docs/topics/event-fabric.md`](../docs/topics/event-fabric.md)
- Why for How: Telemetry envelope.
- Plain: Whenever any component writes a record meant for another component (telemetry, decision snapshots, drift audits), it wraps it in **one canonical envelope** so every line carries the same metadata: a unique id, a monotonic generation number (for total ordering within a run), the event type, the instrument, an ISO timestamp, a parent id (for causal chains), and a **schema hash**. The rule is "consolidate on the fabric…
- **Ins:** `event_type`, `instrument`, `source`, `payload` (the component's own dict), optional `parent_event_id`. Schema hash is auto-resolved from `features.feature_schema`.
- **Outs:** a JSON-serialisable envelope dict appended to the component's JSONL channel (e.g. `ENGINE_TELEMETRY`, `DECISION_LINEAGE`, `DRIFT_AUDIT`).
- Cited files: `src/events/event_fabric.py`, `tests/events/test_event_fabric.py`

### USEFUL — Topic: Execution Loop (multi-signal tick pipeline)

- File: [`docs/topics/execution-loop.md`](../docs/topics/execution-loop.md)
- Why for How: Multi-signal loop; test/orphan surface (F-013).
- Plain: This is the "trading floor loop" design: every tick, scan instruments for signals, rank them, take the top few, classify regime, size them with the portfolio allocator, pass them through the risk gate, alert the operator, wait for a human y/n/reduce decision (it does **not** auto-execute by default), then place the trade. It's fully built and well-tested — but nothing in the codebase actually calls it yet, so today …
- **Ins:** injected collaborators (scanner, ranker, pool, regime_classifier, config_router, allocator, risk_gate, alert_manager, override_handler, trade_executor) + `tick_seconds`/`top_k`/`max_ticks`.
- **Outs:** a list of executed signal dicts (audit trail); alerts via AlertManager; per-signal enrichment (risk/regime/profile). Each stage can SKIP (allocator REJECT, risk BLOCK, override SKIP).
- Cited files: `src/execution/loop.py`, `src/execution/alert_manager.py`, `src/execution/override_handler.py`, `tests/test_execution_loop.py`

### USEFUL — Topic: Expansion Engine (bounded parameter search)

- File: [`docs/topics/expansion-engine.md`](../docs/topics/expansion-engine.md)
- Why for How: Bounded config search.
- Plain: To improve a config you want to nudge parameters and see if results get better — but unbounded tuning overfits and goes off the rails. This engine asks an LLM **once** (offline) for *which* parameters to move and in which direction, then runs a **deterministic** loop that changes one parameter at a time in small steps, each clipped to hard `PARAM_BOUNDS` and a max drift, re-backtesting and **rejecting** any step tha…
- **Ins:** a base production config + an `ExpansionPlan` (LLM-suggested candidates) + `csv_paths`; bounds from `policy_schema`.
- **Outs:** `ExpansionResult` (baseline + 3 ranked tiers + full step trace); `results/expansion/<config>_<TIER>.json`; audit `logs/expansion_trace.jsonl` (accepted) + `logs/expansion_rejected.jsonl` (rejections with reason).
- Cited files: `src/expansion/expansion_engine.py`, `src/expansion/policy_schema.py`, `src/expansion/evaluator.py`, `src/expansion/config_mutator.py`, `src/expansion/llm_pattern_extractor.py`, `tests/test_expansion_engine.py`, `tests/test_expansion_governance_bridge.py`

### USEFUL — Topic: Interpreter Contract Layer (Level 4)

- File: [`docs/topics/interpreter-contract.md`](../docs/topics/interpreter-contract.md)
- Why for How: Interpreter vs engine authority.
- Plain: The Interpreter Contract is the frozen interface every future market interpreter (P&F, Wyckoff, Market Profile, Order Flow, …) must satisfy *before* it ships — so a new interpreter becomes an **experiment measured against G001**, not a belief. An **Interpreter** is an *event/feature producer*: it observes a window and emits events + confidence/strength that feed **fusion**.
- **Ins:** a `window: Sequence[Candle]` (+ `features`, `ctx{instrument}`); reuses the frozen
- **Outs:** `InterpreterReading` (the pure `observe()` result); via the adapter, research `Signal`s
- Cited files: `src/interpreters/contract.py`, `src/interpreters/adapter.py`, `src/interpreters/reference.py`, `scripts/research/qualify_interpreter.py`, `src/interpreters/point_and_figure.py`, `src/research/contracts.py`, `tests/interpreters/test_interpreter_contract.py`, `tests/interpreters/test_reference_ma_cross.py`, `tests/interpreters/test_reference_interpreter_e2e.py`, `tests/interpreters/test_invariant_guards.py`, `tests/test_metrics_v2.py`

### USEFUL — Topic: Metrics Layer V2 (RR / distribution / concentration / survival / efficiency)

- File: [`docs/topics/metrics-layer.md`](../docs/topics/metrics-layer.md)
- Why for How: Second-order measurement (RR/distribution).
- Plain: The Metrics Layer is the second-order measurement surface that lets us judge *whether a change actually helps the goal* — turning "does P&F look interesting?" into "does it move Δexpectancy / Δfrequency / ΔDD / ΔRR vs baseline?". Before it, the system knew entry / exit / PnL but not *how far price moved, how much was left on the table, how quickly, how efficiently*.
- **Ins:** the closed-trade ledger (`TradeJournal.closed` → `TradeRecord` fields: `pnl_rr_net`,
- **Outs:** `BacktestMetrics.distribution["metrics_v2"]` = `{rr, concentration, distribution,
- Cited files: `src/runtime/backtest_v2.py`, `src/analytics/metrics_oracle.py`, `src/research/measurement/forward_walk.py`, `src/journal/__init__.py`, `src/journal/schema.py`, `src/journal/trade_execution_link_v1_0.py`, `src/journal/trade_identity_v1_0.py`, `src/journal/trade_provenance_v1_0.py`, `tests/test_metrics_v2.py`, `tests/runtime/test_replay_determinism.py`, `tests/research/test_runner_determinism.py`

### USEFUL — Topic: Portfolio Allocation

- File: [`docs/topics/portfolio-allocation.md`](../docs/topics/portfolio-allocation.md)
- Why for How: Built; live path is single-candle (F-013).
- Plain: When you trade several instruments, you can't size each in isolation — total exposure and correlation matter (two correlated longs are really one bigger bet). This package decides **how much capital** a signal gets: it tracks open exposure, estimates correlation to existing positions, and applies a risk policy (base risk, trimmed for high exposure/correlation, boosted for strong signals, hard-capped).
- **Ins:** a signal dict (`symbol`, `confidence`, optional `rr`/`regime`) + current exposure state; config `get_prod_section("portfolio")` (`capital_policy`, `correlation` lookback/cache).
- **Outs:** an allocation decision `{action, risk, reason}`; exposure-tracker mutations on open/close; integrity events when correlation data is missing/stale.
- Cited files: `src/portfolio/allocator.py`, `src/portfolio/exposure_tracker.py`, `src/portfolio/correlation_engine.py`, `src/portfolio/capital_policy.py`, `src/portfolio/__init__.py`, `tests/test_portfolio_allocator.py`

### USEFUL — Topic: Regime Classifier

- File: [`docs/topics/regime-classifier.md`](../docs/topics/regime-classifier.md)
- Why for How: Regime label vs fusion weights.
- Plain: Markets behave differently when trending vs ranging vs wildly volatile. Before scoring a candle, the system classifies the current **regime** (`TRENDING` / `RANGING` / `HIGH_VOLATILITY`) from ATR + trend features, then a **router** picks the matching fusion-weight profile so the four engines are blended differently per regime.
- **Ins:** feature dict (`atr`, `trend_score`, optional `volatility`/`adx`); router loads `configs/production/regime_map.json` (or hardcoded defaults).
- **Outs:** a regime string + a fusion-weight dict injected into the engine context; consumed by `FusionEngine.compute(regime=…)` to select per-regime weights.
- Cited files: `src/regime/regime_classifier.py`, `src/regime/config_router.py`, `src/regime/__init__.py`, `tests/test_regime_classifier.py`, `configs/production/regime_map.json`

### USEFUL — Topic: Replay Memory & the Probability Surface

- File: [`docs/topics/replay-memory.md`](../docs/topics/replay-memory.md)
- Why for How: Sidecar memory; zero spine consumption (F-012).
- Plain: `ReplayMemoryEngine` is the system's **institutional memory**: it loads historical opportunity outcomes (`opportunities.jsonl`), buckets each record into a **zone** (a cluster of similar candle-geometry contexts), and reports cluster-conditioned stats — historical win rate, mean RR, failure modes, trap frequency, staleness. The clusters come from `discover_zones` (research K-Means).
- **Ins:** `opportunities.jsonl` records (`features` dict, `outcome`, `rr_achieved`, `timestamp`); a `zone_v1` registry (`feature_order`, `feature_weights`, `zones[].center`). Config: `cognitive_layer` section (`zone_registry_path`, `opportunities_dir`, `max_replay_records`, decay/staleness).
- **Outs:** `query()` dict (`historical_winrate`, `historical_rr`, `failure_modes`, `replay_density`, `cluster_stability`, …); `REPLAY_QUERY` envelopes appended to `logs/replay_queries.jsonl`. **No** decision/fusion/execution output.
- Cited files: `src/replay/replay_memory_engine.py`, `scripts/research/discover_zones.py`, `scripts/research/feature_region_oos_study.py`, `src/cognitive/cognitive_bus.py`, `tests/replay/test_assign_cluster.py`, `tests/replay/test_replay_memory_engine.py`, `tests/cognitive/test_cognitive_bus.py`

### USEFUL — Topic: Model Training & Calibration

- File: [`docs/topics/training-calibration.md`](../docs/topics/training-calibration.md)
- Why for How: Offline model fit; not a live edge.
- Plain: Some engines use trained models. Training is **offline**: mine paired trade records → fit a model → prove it actually correlates with outcomes (the **Phase-5 gate**: `corr ≥ 0.10`, low calibration error, CV-stable) → register it → promote only if it beats the active model by a margin (GOV-3).
- **Ins:** `*_fusion.jsonl` paired trade logs (the clean training data), a target version label; config `get_prod_section("phase5_calibration")` + `get_prod_section("training")`.
- **Outs:** `models/gaussian_*.json` (+ scaler), an entry in `models/gaussian_registry.json`, and a result dict `{approved, promoted, metrics, verdict, gate_checks}`. Rejected calibration raises (no silent registration).
- Cited files: `src/training/train_pipeline.py`, `src/training/trainer.py`, `src/training/phase5_calibration.py`, `src/core/model_registry.py`, `src/config_layer/rr/__init__.py`, `src/config_layer/rr/rr_dataset_builder.py`, `tests/test_train_pipeline.py`, `tests/test_gaussian_update_pipeline.py`, `tests/test_phase5_calibration.py`, `tests/test_trainer.py`, `tests/test_evaluator.py`

### USEFUL — Topic: Regime Weight Search

- File: [`docs/topics/weight-search.md`](../docs/topics/weight-search.md)
- Why for How: Regime weight search; no authority.
- Plain: The live system blends the four engines with **per-regime weights** (`regime-classifier.md`). Where do those weights come from?
- **Ins:** base config + `csv_paths` + an LLM chat fn + a backtest runner + evaluator; guardrails reused from `expansion.policy_schema` (`MIN_PNL_RATIO`, `MAX_DRAWDOWN_RATIO`, `PARAM_BOUNDS`).
- **Outs:** `List[RegimeSearchResult]` (best candidate + improvement % + insights per regime); audit lines to `logs/regime_search.jsonl`. Final weights are intended for the production `fusion_engine` / `regime_map`.
- Cited files: `src/search/regime_weight_searcher.py`, `tests/test_regime_weight_searcher.py`, `tests/test_regime_classifier.py`

## Excel package rollup (file names tracked)

Counts are unique `.py` rows in the workbooks, not disk (see GROK.md §8).

### src/

| Package | Files |
|---|---:|
| `src/research` | 198 |
| `src/features` | 41 |
| `src/config_layer` | 34 |
| `src/governance` | 29 |
| `src/agent` | 28 |
| `src/bitnet` | 23 |
| `src/core` | 21 |
| `src/utils` | 19 |
| `src/strategies` | 18 |
| `src/runtime` | 15 |
| `src/inout` | 14 |
| `src/engines` | 13 |
| `src/control_plane` | 11 |
| `src/data_ingestion` | 9 |
| `src/retrieval` | 9 |
| `src/identity` | 8 |
| `src/training` | 8 |
| `src/expansion` | 6 |
| `src/interpreters` | 6 |
| `src/journal` | 6 |
| `src/msip` | 6 |
| `src/portfolio` | 6 |
| `src/replay` | 6 |
| `src/scanner` | 6 |
| `src/analytics` | 5 |
| `src/execution` | 5 |
| `src/llm_research` | 5 |
| `src/multi_llm` | 5 |
| `src/charts` | 4 |
| `src/live` | 4 |
| `src/regime` | 4 |
| `src/uat` | 4 |
| `src/validation_access` | 3 |
| `src/cognitive` | 2 |
| `src/events` | 2 |
| `src/feedback` | 2 |
| `src/monitoring` | 2 |
| `src/structure` | 2 |
| `src/__init__.py` | 1 |
| `src/search` | 1 |
| `src/ui` | 1 |

### scripts/

| Package | Files |
|---|---:|
| `scripts/research` | 159 |
| `scripts/analysis` | 127 |
| `scripts/governance` | 37 |
| `scripts/data` | 22 |
| `scripts/maintenance` | 14 |
| `scripts/training` | 13 |
| `scripts/context` | 5 |
| `scripts/misc` | 5 |
| `scripts/evaluation` | 3 |
| `scripts/export` | 3 |
| `scripts/groq_bridge` | 3 |
| `scripts/backtest` | 2 |
| `scripts/__init__.py` | 1 |
| `scripts/_gate5_compliance_pass.py` | 1 |
| `scripts/auto_train_from_opportunities.py` | 1 |
| `scripts/build_consolidated_docs.py` | 1 |
| `scripts/control_plane` | 1 |
| `scripts/export_model_registry.py` | 1 |
| `scripts/extract_folder_structure.py` | 1 |
| `scripts/live` | 1 |
| `scripts/metrics` | 1 |
| `scripts/multi_llm` | 1 |
| `scripts/portfolio` | 1 |
| `scripts/rag_index.py` | 1 |
| `scripts/tmp_cert_worktrees.py` | 1 |
| `scripts/update_config_hash.py` | 1 |
| `scripts/validate_integration.py` | 1 |

### tests/ (folders with ≥2 files; rest are singleton `test_*.py`)

| Package | Files |
|---|---:|
| `tests/research` | 89 |
| `tests/mt5_analytics` | 16 |
| `tests/Grok` | 11 |
| `tests/governance` | 9 |
| `tests/Claude` | 6 |
| `tests/interpreters` | 6 |
| `tests/harness` | 4 |
| `tests/replay` | 4 |
| `tests/analytics` | 3 |
| `tests/data_ingestion` | 3 |
| `tests/journal` | 3 |
| `tests/features` | 2 |
| `tests/helpers` | 2 |
| `tests/inout` | 2 |
| *(root `tests/test_*.py` and singleton folders)* | 371 |

Full file names live in the three xlsx workbooks. Do not copy the 1531 rows here.

## Needed-topic cited files

| File | Topic |
|---|---|
| `src/bitnet/bitnet_inference.py` | bitnet-gate.md |
| `src/config_layer/crt_engine_v2.py` | bitnet-gate.md |
| `src/runtime/backtest_v2.py` | bitnet-gate.md |
| `tests/test_bitnet_inference.py` | bitnet-gate.md |
| `tests/test_bitnet_parity.py` | bitnet-gate.md |
| `src/config_layer/config_validator.py` | config-validation.md |
| `src/config_layer/production_config.py` | config-validation.md |
| `src/config_layer/__init__.py` | config-validation.md |
| `src/config_layer/stack_version.py` | config-validation.md |
| `src/utils/config_dumper.py` | config-validation.md |
| `src/utils/isolated_config_root.py` | config-validation.md |
| `src/utils/registry_refresh.py` | config-validation.md |
| `tests/test_fusion_and_validator_regression.py` | config-validation.md |
| `src/config_layer/state_identity.py` | crt-spine.md |
| `src/config_layer/state_topology.py` | crt-spine.md |
| `docs/governance/crt_executable_state_graph.json` | crt-spine.md |
| `src/config_layer/crt_engine_v2.py` | crt-spine.md |
| `src/runtime/parent_crt_feed.py` | crt-spine.md |
| `src/config_layer/htf_state.py` | crt-spine.md |
| `src/core/engine_runner.py` | crt-spine.md |
| `src/config_layer/crt_config_completeness.py` | crt-spine.md |
| `src/config_layer/crt_config_provenance.py` | crt-spine.md |
| `src/config_layer/crt_identity_schema.py` | crt-spine.md |
| `src/config_layer/crt_sweep_taxonomy.py` | crt-spine.md |
| `src/config_layer/state_contract.py` | crt-spine.md |
| `src/config_layer/state_contract_loader.py` | crt-spine.md |
| `src/config_layer/_crt_state_generated.py` | crt-spine.md |
| `src/features/smc/__init__.py` | crt-spine.md |
| `src/features/smc/_geometry.py` | crt-spine.md |
| `src/features/smc/breaker.py` | crt-spine.md |
| `src/features/smc/choch.py` | crt-spine.md |
| `src/features/smc/fvg.py` | crt-spine.md |
| `src/features/smc/levels.py` | crt-spine.md |
| `src/features/smc/mitigation.py` | crt-spine.md |
| `src/features/smc/order_block.py` | crt-spine.md |
| `src/structure/__init__.py` | crt-spine.md |
| `src/structure/predicates.py` | crt-spine.md |
| `src/config_layer/execution_planner.py` | execution-planning.md |
| `src/execution/__init__.py` | execution-planning.md |
| `src/execution/execution_intent_v1_0.py` | execution-planning.md |
| `tests/test_execution_planner.py` | execution-planning.md |
| `tests/test_execution_contract_v1.py` | execution-planning.md |
| `tests/test_sl_tp_comparator.py` | execution-planning.md |
| `src/features/feature_schema.py` | feature-schema.md |
| `src/features/feature_pipeline.py` | feature-schema.md |
| `src/features/feature_monitor.py` | feature-schema.md |
| `src/features/dataset_validator.py` | feature-schema.md |
| `src/core/feature_store.py` | feature-schema.md |
| `src/data_ingestion/__init__.py` | feature-schema.md |
| `src/data_ingestion/clock_detector.py` | feature-schema.md |
| `src/data_ingestion/clock_registry.py` | feature-schema.md |
| `src/data_ingestion/session_autoderive.py` | feature-schema.md |
| `src/data_ingestion/xauusd_phase1_candidate.py` | feature-schema.md |
| `src/features/__init__.py` | feature-schema.md |
| `src/features/broker_clock.py` | feature-schema.md |
| `src/features/calendar_periods.py` | feature-schema.md |
| `src/features/dataset_builder.py` | feature-schema.md |
| `src/features/feature_builder.py` | feature-schema.md |
| `src/features/feature_identity.py` | feature-schema.md |
| `src/features/fm_resolve.py` | feature-schema.md |
| `src/features/gaussian_schema_contract.py` | feature-schema.md |
| `src/features/magnitude_states.py` | feature-schema.md |
| `src/features/market_context.py` | feature-schema.md |
| `src/features/market_reality_contract.py` | feature-schema.md |
| `src/features/market_shape.py` | feature-schema.md |
| `src/features/model_evidence.py` | feature-schema.md |
| `src/features/parent_candle.py` | feature-schema.md |
| `src/core/fusion_engine.py` | fusion-decision.md |
| `src/core/decision_engine.py` | fusion-decision.md |
| `src/core/engine_runner.py` | fusion-decision.md |
| `src/core/__init__.py` | fusion-decision.md |
| `src/core/backtest_port.py` | fusion-decision.md |
| `src/core/dynamic_threshold.py` | fusion-decision.md |
| `src/core/governance_mode.py` | fusion-decision.md |
| `src/core/hierarchical_meta_fusion.py` | fusion-decision.md |
| `src/core/signal_belief_tracker.py` | fusion-decision.md |
| `src/core/types.py` | fusion-decision.md |
| `src/runtime/analyze_fusion_shadow.py` | fusion-decision.md |
| `tests/test_engine_runner_rr_fusion.py` | fusion-decision.md |
| `tests/test_fusion_and_validator_regression.py` | fusion-decision.md |
| `tests/test_analyze_fusion_shadow.py` | fusion-decision.md |
| `tests/test_engine_runner_dual_gate.py` | fusion-decision.md |
| `src/config_layer/goal_schema.py` | goal-layer.md |
| `src/config_layer/goal_validator.py` | goal-layer.md |
| `src/runtime/backtest_v2.py` | goal-layer.md |
| `src/config_layer/config_validator.py` | goal-layer.md |
| `tests/test_goal_schema.py` | goal-layer.md |
| `tests/test_goal_validator.py` | goal-layer.md |
| `tests/test_goal_metrics.py` | goal-layer.md |
| `tests/test_resample_completeness.py` | goal-layer.md |
| `src/runtime/live_engine_hook.py` | live-execution.md |
| `src/live/mt5_bridge.py` | live-execution.md |
| `src/live/telegram_bridge.py` | live-execution.md |
| `src/inout/alphavantage_candle_fetcher.py` | live-execution.md |
| `src/inout/hummingbot_candle_fetcher.py` | live-execution.md |
| `src/execution/loop.py` | live-execution.md |
| `src/live/__init__.py` | live-execution.md |
| `src/live/order_manager.py` | live-execution.md |
| `src/inout/live_rail/__init__.py` | live-execution.md |
| `src/inout/live_rail/bar_builder.py` | live-execution.md |
| `src/inout/live_rail/binance_ws_adapter.py` | live-execution.md |
| `src/inout/live_rail/config.py` | live-execution.md |
| `src/inout/live_rail/factory.py` | live-execution.md |
| `src/inout/live_rail/longport_adapter.py` | live-execution.md |
| `src/inout/live_rail/ohlcv_replay_port.py` | live-execution.md |
| `src/inout/live_rail/resilience.py` | live-execution.md |
| `src/inout/live_rail/tickdb_adapter.py` | live-execution.md |
| `src/inout/live_rail/types.py` | live-execution.md |
| `src/runtime/live_rail_feeder.py` | live-execution.md |
| `src/runtime/live_rail_orchestrator.py` | live-execution.md |
| `src/runtime/__init__.py` | live-execution.md |
| `tests/test_live_integration.py` | live-execution.md |
| `tests/test_execution_loop.py` | live-execution.md |
| `src/config_layer/crt_engine_v2.py` | model-intent-and-feature-ownership.md |
| `src/engines/heuristic_gaussian_engine.py` | model-intent-and-feature-ownership.md |
| `src/engines/rr_engine.py` | model-intent-and-feature-ownership.md |
| `src/engines/zone_gate_engine.py` | model-intent-and-feature-ownership.md |
| `src/engines/live_engine.py` | model-intent-and-feature-ownership.md |
| `src/bitnet/zone_cosine_searcher.py` | model-intent-and-feature-ownership.md |
| `src/bitnet/bitnet_inference.py` | model-intent-and-feature-ownership.md |
| `src/core/engine_runner.py` | model-intent-and-feature-ownership.md |
| `src/core/fusion_engine.py` | model-intent-and-feature-ownership.md |
| `tests/test_topic_docs.py` | model-intent-and-feature-ownership.md |
| `tests/test_current_findings.py` | model-intent-and-feature-ownership.md |
| `src/features/feature_schema.py` | model-intent-and-feature-ownership.md |
| `src/governance/promotion_manager.py` | promotion-governance.md |
| `configs/promotion_log.json` | promotion-governance.md |
| `src/governance/config_integrity.py` | promotion-governance.md |
| `scripts/maintenance/_promote_v4_bnb_cutover.py` | promotion-governance.md |
| `tests/test_shadow_promotion_gate.py` | promotion-governance.md |
| `tests/test_sprint7_governance.py` | promotion-governance.md |
| `tests/test_meta_governor_executor.py` | promotion-governance.md |
| `docs/governance/MEASUREMENT_CONTRACT.md` | research-measurement-contract.md |
| `docs/governance/measurement_contract.schema.json` | research-measurement-contract.md |
| `docs/governance/e_mt_01_adversarial_mutation_matrix.json` | research-measurement-contract.md |
| `docs/governance/research_family_registry.json` | research-measurement-contract.md |
| `configs/research/measurement_contracts/crypto_majors.v1.json` | research-measurement-contract.md |
| `scripts/research/gate_measurement_m_gate_01.py` | research-measurement-contract.md |
| `docs/research/parquet_evidence_layer.md` | research-measurement-contract.md |
| `docs/current-findings.md` | research-measurement-contract.md |
| `src/identity/__init__.py` | research-measurement-contract.md |
| `src/identity/certify.py` | research-measurement-contract.md |
| `src/identity/check.py` | research-measurement-contract.md |
| `src/identity/hashes.py` | research-measurement-contract.md |
| `src/identity/outcome.py` | research-measurement-contract.md |
| `src/identity/query.py` | research-measurement-contract.md |
| `src/identity/store.py` | research-measurement-contract.md |
| `src/identity/tokens.py` | research-measurement-contract.md |
| `tests/test_measurement_contract.py` | research-measurement-contract.md |
| `tests/test_research_family_registry.py` | research-measurement-contract.md |
| `docs/knowledge-map.md` | research-measurement-contract.md |
| `tests/test_current_findings.py` | research-measurement-contract.md |
| `tests/test_closure_authority_index.py` | research-measurement-contract.md |
| `tests/research/test_evidence_layer.py` | research-measurement-contract.md |
| `src/engines/heuristic_gaussian_engine.py` | scoring-engines.md |
| `src/engines/ml_gaussian_engine.py` | scoring-engines.md |
| `src/engines/rr_engine.py` | scoring-engines.md |
| `src/engines/zone_gate_engine.py` | scoring-engines.md |
| `src/core/engine_runner.py` | scoring-engines.md |
| `src/engines/__init__.py` | scoring-engines.md |
| `src/engines/gaussian_engine.py` | scoring-engines.md |
| `src/engines/tradenet_meta_engine.py` | scoring-engines.md |
| `src/engines/zone_cluster_score.py` | scoring-engines.md |
| `tests/test_gaussian_impl_switch.py` | scoring-engines.md |
| `tests/test_zone_gate.py` | scoring-engines.md |
| `tests/test_engine_runner_rr_fusion.py` | scoring-engines.md |
| `tests/test_fusion_and_validator_regression.py` | scoring-engines.md |
| `src/core/ultron_risk_gate.py` | ultron-risk-gate.md |
| `src/core/ultron_risk_gate_wrapper.py` | ultron-risk-gate.md |
| `src/runtime/live_engine_hook.py` | ultron-risk-gate.md |
| `src/core/ultron_live_adapter.py` | ultron-risk-gate.md |
| `tests/test_ultron_risk_gate.py` | ultron-risk-gate.md |
| `tests/test_ultron_gate.py` | ultron-risk-gate.md |
| `tests/test_ultron_wrapper.py` | ultron-risk-gate.md |

## What this extract is not

- Not economic proof.
- Not a second doctrine.
- Not complete if GCMC v1 is below 100% — leftovers live in `.grok/infra_architecture_link.xlsx` Gaps.
- Topic prose can drift; **source wins**.
