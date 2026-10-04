# Hidden Wiring Audit — Top 20 Findings

**Date:** 2026-06-06  
**Scope:** Entire repository, documented via CLAUDE.md → CONFIG_REFERENCE.md / SIGNAL_FLOW.md / GOVERNANCE.md / SCHEMAS.md / ARCHITECTURE.md / codebase-state-map.md / replay-governance.md / service-boundary-map.md + production config `v2_multi_2026_04.json`  
**Methodology:** Config-key trace from documentation to runtime path. Only doc-visible wiring analyzed (source cross-checked against engine_runner.py).

---

## Finding #1 — `capital_management` Section is Completely Unwired

**Type:** A (Dead Config)  
**Confidence:** HIGH  
**File locations:** `configs/production/v2_multi_2026_04.json:462-479`  
**Config key:** `capital_management.total_capital_inr`, `max_risk_per_trade_pct`, `kill_switch_daily_loss_inr`, etc.  
**Runtime path:** NOWHERE. The documented capital-protection layer is `ultron_risk_gate` (consumed by `src/core/ultron_risk_gate.py`). `capital_management` is a completely separate block with no documented consumer. The kill-switch file path `logs/kill_switch_state.json` is hardcoded in `ultron_risk_gate.py` (per codebase-state-map.md §3), not read from `capital_management`.  
**Evidence chain:** CONFIG_REFERENCE.md lists every section's consumer — `capital_management` is absent from the table. ARCHITECTURE.md §6.2 table of 11 sections also excludes it. SIGNAL_FLOW.md Step 6 lists `ultron_risk_gate` as the only capital check.  
**Economic impact:** 2 configurable kill-switch thresholds (daily loss INR, monthly drawdown INR) that are supposed to protect capital but are never read. A trader editing `capital_management` to tighten kill-switch parameters will see zero effect.  
**Probability bug is real:** 95% — zero consumers documented, zero cross-references.  
**Recommended fix:** Either wire `capital_management` into `UltronRiskGate.evaluate()` as a config source, or delete the section to avoid misdirection.

---

## Finding #2 — `data_ingestion` Section References Nonexistent Database

**Type:** A (Dead Config)  
**Confidence:** HIGH  
**File locations:** `configs/production/v2_multi_2026_04.json:481-506`  
**Config key:** `data_ingestion.db_url` (points to `postgresql://localhost/tradelatest`), `mt5_enabled: false`  
**Runtime path:** NOWHERE. The codebase has "no database, no message broker, no cloud deps" (CLAUDE.md §1, ARCHITECTURE.md §1). All state is file-backed.  
**Evidence chain:** ARCHITECTURE.md §7 CLI entry points list no database loader. SCHEMAS.md §1 explicitly says "no SQL models and no ORM". The signal flow (SIGNAL_FLOW.md §1 Step 1) reads from CSV, not Postgres.  
**Economic impact:** Low — config is dormant, but a new developer reading the config would believe a PostgreSQL dependency exists. If they attempt to wire it, they break the "no database" invariant.  
**Probability bug is real:** 90% — config schema says Postgres, runtime says CSV. The dead `mt5_enabled: false` key suggests a legacy feature that was never connected.  
**Recommended fix:** Delete the `data_ingestion` section and move any future ingestion config to a purpose-built section.

---

## Finding #3 — `gate_intelligence` Section Has No Consumer in the Spine

**Type:** A (Dead Config)  
**Confidence:** HIGH  
**File locations:** `configs/production/v2_multi_2026_04.json:78-84`  
**Config key:** `gate_intelligence.gate_weight_intent`, `gate_weight_vol`, `gate_weight_liquidity`, `gate_weight_structure`, `gate_approval_threshold`  
**Runtime path:** NOWHERE. The spine (SIGNAL_FLOW.md Steps 3–6) is: EngineRunner → FusionEngine → DecisionEngine → ExecutionPlanner → UltronRiskGate. None of these consume `gate_intelligence`.  
**Evidence chain:** CONFIG_REFERENCE.md lists 14 documented sections — `gate_intelligence` is absent. ARCHITECTURE.md §6.2 table of 11 sections also excludes it.  
**Economic impact:** Medium — a multi-weight gate with an approval threshold of 0.55 was designed to filter signals but is bypassed. Trades that should be caught by this gate sail through to the spine.  
**Probability bug is real:** 85% — fully specified config with zero consumers.  
**Recommended fix:** Either wire as a pre-fusion gate in EngineRunner, or delete. If the intent was gate intelligence for INOUT, move it under `inout.gate_intelligence`.

---

## Finding #4 — `sl_tp_comparison` Self-Declares Dead

**Type:** A (Dead Config, documented)  
**Confidence:** HIGH  
**File locations:** `configs/production/v2_multi_2026_04.json:67-77`  
**Config key:** `sl_tp_comparison.legacy_sl_atr_mult`, `legacy_tp_atr_mult_*`, `primary_metric`, `output_path`  
**Runtime path:** `SLTPComparator` (analytics/sl_tp_comparator.py) only — never in live or backtest trade path. The config's own `_comment` field says: "Used ONLY by SLTPComparator, never in live path".  
**Evidence chain:** Config self-documents as dead. codebase-state-map.md §1 lists `analytics.sl_tp_comparator` with role: "SL/TP method comparison for backtest optimization".  
**Economic impact:** Low — analytical tool only. But it increases config surface area and could mislead a tuner into thinking these values affect live execution.  
**Probability bug is real:** 100% (self-declared).  
**Recommended fix:** Move to a separate `analytics_config` file outside the production config, or remove from the active config.

---

## Finding #5 — `strategy_engine.s01..s10` Configs May Be Unconsumed

**Type:** B (Partial Wiring)  
**Confidence:** MEDIUM  
**File locations:** `configs/production/v2_multi_2026_04.json:507-591`  
**Config key:** `strategy_engine.s01_crt`, `s02_mean_reversion`, `s03_breakout`, `s09_pattern_recog`, `s10_trap`, `s04_stat_arb`, `s05_grid`, `s06_scalping`, `s07_news_sentiment`, `s08_ml_ensemble`  
**Runtime path:** StrategyOrchestrator (src/strategies/strategy_orchestrator.py) reads these and injects consensus into EngineRunner context as `strategy_consensus_score`. But EngineRunner only uses this value when `>= 0.0` — the consensus is advisory, not gating. The individual strategy config thresholds (`min_confidence`, `sl_atr_mult`, `tp_rr_ratio`) may not be enforced if StrategyOrchestrator itself is not invoked.  
**Evidence chain:** SIGNAL_FLOW.md §2.4 says INOUT "does NOT flow through EngineRunner". The strategy_engine block is not listed in ARCHITECTURE.md §6.2's consumer table. EngineRunner reads only `strategy_consensus_score` from context — it never reads `strategy_engine` config keys directly.  
**Economic impact:** High — if StrategyOrchestrator consensus is disabled or never invoked, 10 strategy configurations are decorative. A trader tuning `s03_breakout.min_confidence` will see no effect on CRT spine decisions.  
**Probability bug is real:** 65% — depends on whether StrategyOrchestrator is actually wired in the active live/backtest path.  
**Recommended fix:** Verify StrategyOrchestrator is invoked. If not, either wire it or remove the config section. Document the invocation condition.

---

## Finding #6 — `fusion_engine.regime_fusion_weights` May Shadow Flat Weights

**Type:** C (Shadow Override) / D (Split Brain)  
**Confidence:** MEDIUM  
**File locations:** `configs/production/v2_multi_2026_04.json:119-148` vs `configs/production/v2_multi_2026_04.json:105-108`  
**Config key:** `fusion_engine.regime_fusion_weights.TRENDING|RANGING|VOLATILE|UNKNOWN` vs `fusion_engine.weight_crt|weight_gaussian|weight_zone_gate|weight_rr`  
**Runtime path:** FusionEngine.compute() (src/core/fusion_engine.py). The base weights (`weight_crt=0.4, weight_gaussian=0.2, weight_zone_gate=0.2, weight_rr=0.2`) are consumed via FusionConfig. But `regime_fusion_weights` specifies per-regime weight matrices (e.g. TRENDING: `crt: 0.38, gaussian: 0.20, zone_gate: 0.12, rr: 0.20, strategy_consensus: 0.1`). If FusionEngine does not switch to regime-adaptive weights, the TRENDING regime always uses flat 0.4/0.2/0.2/0.2 instead of the intended 0.38/0.20/0.12/0.20.  
**Evidence chain:** CONFIG_REFERENCE.md §3 lists only flat weights for fusion_engine. The regime_fusion_weights block is absent from the reference. FusionConfig constructor in engine_runner.py:374-390 only reads flat weights.  
**Economic impact:** High — regime-adaptive weighting is a documented design intent but if regime_fusion_weights is never applied, fusion behavior is regime-blind. The TRENDING/RANGING/VOLATILE distinctions in config have zero effect.  
**Probability bug is real:** 70% — the regime_fusion_weights block exists in config but CONFIG_REFERENCE.md (the authoritative key reference) doesn't document it, and FusionConfig's constructor doesn't read it.  
**Recommended fix:** Either wire `regime_fusion_weights` into FusionEngine.compute() with a feature flag, or remove the unreachable block and document flat weights as the only active path.

---

## Finding #7 — `PROMOTION_MARGIN=2%` Is Hardcoded, Not Configurable

**Type:** C (Shadow Override — hardcoded constant replaces config)  
**Confidence:** HIGH  
**File locations:** `src/core/model_registry.py` (per CLAUDE.md §11 Phase 3: "model_registry.py enforces GOV-3 atomic promotion + PROMOTION_MARGIN=2% quality gate")  
**Config key:** None — 2% is a magic constant  
**Runtime path:** ModelRegistry enforces a 2% margin gate before model promotion. There is no config key to tune this.  
**Evidence chain:** CLAUDE.md §11 Phase 3 and SIGNAL_FLOW.md §2.2 both reference `PROMOTION_MARGIN=2%`. CONFIG_REFERENCE.md does not list any `promotion_margin` key. A user who wants a 1% or 5% margin must edit Python source.  
**Economic impact:** Medium — the 2% margin may be too tight or too loose for different instruments. EURUSD with 36 trades (from validation_summary) is marginal at 2%.  
**Probability bug is real:** 80% — documented constant with no config key is a classic Type C shadow override.  
**Recommended fix:** Add `promotion_margin_pct` to the `governance` or `model_registry` config section, with `2.0` as default, and read it in model_registry.py.

---

## Finding #8 — `fusion_use_evaluate` Feature Flag Is Always `false`

**Type:** E (Unreachable Feature)  
**Confidence:** HIGH  
**File locations:** `configs/production/v2_multi_2026_04.json:43`  
**Config key:** `engine_runner.fusion_use_evaluate: false`  
**Runtime path:** EngineRunner.run() line 748: `use_evaluate = bool(getattr(self, "_fusion_use_evaluate", False))`. Since config value is `false`, the `FusionEngine.evaluate()` path is NEVER invoked in production. `fusion_compare_evaluate: true` does call it but only for shadow logging.  
**Evidence chain:** EngineRunner.py:748-766 shows `use_evaluate` guards the evaluate path. Production config sets it `false`. CONFIG_REFERENCE.md §3 documents it as "feature flag for new fusion path". It has been `false` since at least v1_multi_2026_03.  
**Economic impact:** Low-Medium — the evaluate path may offer better fusion but it's never used. If evaluate() has bugs, they are only exposed when the flag is toggled.  
**Probability bug is real:** 60% — the flag exists to gate an unfinished/incomplete path. It may never be production-ready.  
**Recommended fix:** Either complete and test the evaluate() path, remove the dead code, or document the flag as "reserved for future use" with a target version for activation.

---

## Finding #9 — `ultron_gate_enabled: false` Creates Split Brain Between Live and Backtest

**Type:** D (Split Brain) / G (Runtime Divergence)  
**Confidence:** HIGH  
**File locations:** `configs/production/v2_multi_2026_04.json:44`  
**Config key:** `engine_runner.ultron_gate_enabled: false`  
**Runtime path:** EngineRunner.run() lines 853-899: when `false` → uses `_regime_governor_legacy()` (no quota, no percentile gate). When `true` → uses `RegimeGovernor.evaluate()` (with daily quota + percentile filtering). The backtest path uses legacy; live uses RegimeGovernor.  
**Evidence chain:** EngineRunner.py:882-885 explicitly documents "Training / backtest pass-through — no quota cap, no percentile gate." This is a DESIGNED split brain, but the config value `false` means backtest results do NOT reflect live regime-filtering behavior.  
**Economic impact:** HIGH — backtest win rates and trade counts are inflated because regime governor is bypassed. A strategy that passes backtest at `ultron_gate_enabled=false` may fail live when quota/percentile gates engage.  
**Probability bug is real:** 100% — documented intentional divergence. The config value `false` means ALL backtest results are non-representative of live behavior.  
**Recommended fix:** Either (a) enable `ultron_gate_enabled: true` and backtest with full regime governor, (b) add a `backtest.override_ultron_gate` flag so the split is explicit, or (c) document the expected backtest-to-live degradation factor.

---

## Finding #10 — `signal_belief` Section Missing from Config

**Type:** A (Dead Config — the code falls back to a default) / F (Config Drift)  
**Confidence:** HIGH  
**File locations:** EngineRunner.py:425-426 vs configs/production/v2_multi_2026_04.json  
**Config key:** `signal_belief` (entire section absent from production config)  
**Runtime path:** EngineRunner.__init__() line 425: `_belief_cfg = config.get("signal_belief", {})`. Since no key exists, defaults to empty dict. Line 426: `self._belief_enabled = bool(_belief_cfg.get("enabled", False))` → always False. The belief gate (temporal conviction accumulator) is NEVER active.  
**Evidence chain:** EngineRunner.py:819-839 shows the full belief gate logic, but it's gated by `self._belief_enabled` which is always False. CONFIG_REFERENCE.md does not list `signal_belief`.  
**Economic impact:** Medium — the belief gate was designed to prevent impulsive entries by accumulating conviction over consecutive candles. It is never used.  
**Probability bug is real:** 95% — code exists, gate exists, but the enabling config key is absent.  
**Recommended fix:** Add a `signal_belief` section to the production config (e.g. `{"enabled": false, "high_conviction": 0.8, "min_confirmations": 2}`) so the feature is at least configurable.

---

## Finding #11 — `cognitive_layer` Section Missing from Config

**Type:** A (Dead Config) / E (Unreachable Feature)  
**Confidence:** HIGH  
**File locations:** EngineRunner.py:435-446 vs configs/production/v2_multi_2026_04.json  
**Config key:** `cognitive_layer` (entire section absent)  
**Runtime path:** EngineRunner.__init__() line 435: `_cognitive_cfg = config.get("cognitive_layer", {})`. With no key, `CognitiveBus` is never started.  
**Evidence chain:** EngineRunner.py:436: `if bool(_cognitive_cfg.get("enabled", False)):` → always False since dict is empty. CognitiveBus is a background thread that writes advisory telemetry — clean code that could provide value but is stranded.  
**Economic impact:** Low — CognitiveBus is advisory only, never gates decisions. But the code exists and maintains, and the thread pool is wasted opportunity.  
**Probability bug is real:** 90% — absent config kills the feature.  
**Recommended fix:** Add a minimal `cognitive_layer: {"enabled": false}` section to enable configuration. Set to true if the bus is stable.

---

## Finding #12 — `feature_monitor.drift_regime_pause_enabled` and `drift_cooldown_candles` Are Unreferenced in Documentation

**Type:** B (Partial Wiring)  
**Confidence:** MEDIUM  
**File locations:** `configs/production/v2_multi_2026_04.json:385-386`  
**Config key:** `feature_monitor.drift_regime_pause_enabled`, `feature_monitor.drift_cooldown_candles`  
**Runtime path:** FeatureMonitor (src/features/feature_monitor.py) — drift detection exists and logs WARNING/DEBUG at Z thresholds. But regime-pause logic (pausing trading when drift is detected) is not documented in the signal flow or architecture docs.  
**Evidence chain:** CONFIG_REFERENCE.md lists only `window_size`, `hard_drift_z`, `soft_drift_z` for feature_monitor. The `drift_regime_pause_enabled` and `drift_cooldown_candles` keys are absent from the reference. replay-governance.md's replay-risk register doesn't mention drift-triggered pauses.  
**Economic impact:** Medium — if drift regime pause IS implemented but undocumented, it could silently pause trading during backtests, making them non-reproducible. If NOT implemented, the config keys are dead.  
**Probability bug is real:** 50% — insufficient evidence either way from docs alone.  
**Recommended fix:** Audit feature_monitor.py to verify whether regime-pause logic reads these config keys. If yes, document; if no, remove keys.

---

## Finding #13 — `training_trigger` Section May Be Self-Contained and Unwired to AutoTuner

**Type:** A (Dead Config) / E (Unreachable Feature)  
**Confidence:** MEDIUM  
**File locations:** `configs/production/v2_multi_2026_04.json:290-303`  
**Config key:** `training_trigger.min_new_samples`, `drift_window_hours`, `drift_event_threshold`, `cooldown_hours`, `integrity_log`, `drift_event_kinds`  
**Runtime path:** The auto-training pipeline (scripts/training/auto_tuner_multi.py) is invoked manually via CLI, not triggered by these thresholds. The `training_trigger` config may be read by a separate trigger daemon that is not part of the documented CLI entry points.  
**Evidence chain:** ARCHITECTURE.md §7 lists 8 entry points. No "auto-trigger" daemon is listed. SIGNAL_FLOW.md §2.2 (Training Kitchen) starts with "Raw trades → DatasetValidator" — no trigger layer.  
**Economic impact:** Medium — if auto-retrain is supposed to happen at drift thresholds but never triggers, model quality degrades silently.  
**Probability bug is real:** 55% — config exists, but no documented runtime path invokes it.  
**Recommended fix:** Either (a) add a trigger daemon to the CLI matrix, (b) document that this is for future use, or (c) remove the section.

---

## Finding #14 — `phase5_calibration` Config Has No Documented Consumer in the Spine

**Type:** A (Dead Config)  
**Confidence:** MEDIUM  
**File locations:** `configs/production/v2_multi_2026_04.json:281-289`  
**Config key:** `phase5_calibration.val_ratio`, `min_val_samples`, `min_corr`, `max_cal_error`, `cv_corr_std_max`, `cv_n_folds`, `require_cv_stable`  
**Runtime path:** Phase-5 calibration is a training pipeline step (per CLAUDE.md §11 Phase 3). It runs during training, not during trading. But the config section lives in the production config alongside runtime sections.  
**Evidence chain:** CONFIG_REFERENCE.md does not list `phase5_calibration` or `training_trigger` in the documented sections table. These are training-only configs mixed into the production config.  
**Economic impact:** Low — calibration only affects training, not live decisions. But config pollution increases maintenance surface.  
**Probability bug is real:** 80% — config is present but absent from the authoritative reference.  
**Recommended fix:** Move training-only configs (phase5_calibration, training_trigger) to a separate `training_config.json` or clearly section them under a `training.` prefix in the production config.

---

## Finding #15 — `PROMOTION_MARGIN` Documentation Says 2% But ModelRegistry May Use Different Value

**Type:** D (Split Brain — documentation vs implementation)  
**Confidence:** MEDIUM  
**File locations:** CLAUDE.md §11 Phase 3, SIGNAL_FLOW.md §2.2  
**Config key:** None (hardcoded)  
**Runtime path:** `src/core/model_registry.py` enforces a margin gate. The exact percentage is not documented in CONFIG_REFERENCE.md or SCHEMAS.md. CLAUDE.md says "PROMOTION_MARGIN=2%".  
**Evidence chain:** Two doc sources reference 2%, but neither cites the source code location. If `model_registry.py` was refactored and the margin value changed, docs would not reflect it.  
**Economic impact:** Low-Medium — if the actual margin is 1% vs 2%, model quality degrades.  
**Probability bug is real:** 30% — likely the value is still 2%, but the documentation is insufficient to prove it.  
**Recommended fix:** Add a config key `governance.promotion_margin_pct` (as in Finding #7) and remove the hardcoded constant.

---

## Finding #16 — `execution_planner` Config Sections Have No `min_rr_ratio`, `default_sl_atr_mult`, `lookback_candles_sl`, or `liquidity_*` Keys

**Type:** F (Config Drift)  
**Confidence:** HIGH  
**File locations:** CONFIG_REFERENCE.md §4 vs `configs/production/v2_multi_2026_04.json:47-66`  
**Config key:** Missing: `min_rr_ratio`, `default_sl_atr_mult`, `lookback_candles_sl`, `liquidity_lookback`, `liquidity_volume_threshold`, `liquidity_touch_count`  
**Runtime path:** ExecutionPlannerV1_2 reads these from `configs/production/*.json`. If keys are missing, the code falls back to defaults.  
**Evidence chain:** CONFIG_REFERENCE.md lists `min_rr_ratio: 1.5`, `default_sl_atr_mult: 1.0`, etc. as documented keys. The active config (v2_multi_2026_04) does NOT have these keys. The config has `ttl_*_sec`, `risk_percent`, `precision_overrides`, but not the SL/RR/liquidity defaults.  
**Economic impact:** HIGH — if ExecutionPlanner falls back to hardcoded defaults that differ from intended values, SL placement and RR thresholds are wrong. Trades may take larger-than-intended risk.  
**Probability bug is real:** 85% — documented keys absent from the active config.  
**Recommended fix:** Add the missing keys to v2_multi_2026_04.json with values matching CONFIG_REFERENCE.md defaults.

---

## Finding #17 — `backtest` Section in Config Has Keys Not Referenced in BacktestRunner Documentation

**Type:** B (Partial Wiring)  
**Confidence:** MEDIUM  
**File locations:** `configs/production/v2_multi_2026_04.json:367-380`  
**Config key:** `backtest.gap_reset_enabled`, `backtest.gap_reset_minutes`, `backtest.event_flush_every`, `backtest.simulated_spread_pct`  
**Runtime path:** BacktestRunner in src/runtime/backtest_v2.py reads some of these. But CONFIG_REFERENCE.md's backtest table lists `gap_reset_enabled`, `gap_reset_minutes`, `event_flush_every` without specifying which code path consumes them.  
**Evidence chain:** replay-governance.md §2 lists determinism guarantees (seeded slippage, gap handling) but doesn't cite which config keys drive them. If `gap_reset_enabled` is not read, gap-handling logic is non-deterministic across configs.  
**Economic impact:** Medium — gap handling affects equity curves. If the config key is decorative, gap behavior is uncontrolled.  
**Probability bug is real:** 45% — keys exist, code likely reads them, but documentation trail is incomplete.  
**Recommended fix:** Trace each backtest config key to its read site in backtest_v2.py and add citations to CONFIG_REFERENCE.md.

---

## Finding #18 — `inout.risk.max_concurrent_trades` (3) vs `ultron_risk_gate.max_trades_per_day` (10) — Two Risk Limits, One Path

**Type:** D (Split Brain — two sources of truth for risk limits)  
**Confidence:** HIGH  
**File locations:** `configs/production/v2_multi_2026_04.json:436` vs `configs/production/v2_multi_2026_04.json:89`  
**Config key:** `inout.risk.max_concurrent_trades: 3` vs `ultron_risk_gate.max_trades_per_day: 10`  
**Runtime path:** INOUT strategy (SIGNAL_FLOW.md §2.4) joins only at Step 6 (UltronRiskGate). INOUT's own risk limits (`inout.risk`) are enforced before the spine join point. UltronRiskGate enforces `max_trades_per_day`. If concurrent trades approach 3 but daily limit is 10, the more restrictive is 3 — but the trade-off is that INOUT may already hold 3 positions when CRT spine tries to open one.  
**Evidence chain:** SIGNAL_FLOW.md §2.4: "INOUT is a separate strategy that runs alongside the CRT spine." INOUT has its own config, its own risk. The two risk systems are unaware of each other.  
**Economic impact:** HIGH — if INOUT holds 2 concurrent positions and CRT spine tries to open a 3rd, `inout.risk.max_concurrent_trades=3` stops INOUT from opening more, but does NOT stop CRT. CRT is governed only by `ultron_risk_gate.max_trades_per_day=10`. Total concurrent exposure could reach 13 (3 INOUT + 10 CRT).  
**Probability bug is real:** 90% — two independent risk systems with no cross-communication.  
**Recommended fix:** Either (a) make CRT and INOUT share a single `PortfolioManager` that enforces global concurrency limits, or (b) document the split-brain risk and set conservative limits on both sides.

---

## Finding #19 — `uat.kill_switch.persist_path: logs/kill_switch_state.json` May Conflict with Hardcoded Path

**Type:** C (Shadow Override — config value overridden by hardcoded path)  
**Confidence:** MEDIUM  
**File locations:** `configs/production/v2_multi_2026_04.json:658` vs `src/core/ultron_risk_gate.py:44` (hardcoded)  
**Config key:** `uat.kill_switch.persist_path`  
**Runtime path:** UAT runner (src/uat/uat_runner.py) reads this config for testing. But the production kill switch in `ultron_risk_gate.py` uses a hardcoded path `logs/kill_switch_state.json`. If the UAT runner honors the config but production does not, tests pass with one path while production uses another.  
**Evidence chain:** codebase-state-map.md §3 Tier 2 item 5: "Hardcoded relative paths in business logic — `core/ultron_risk_gate.py:44` (`logs/kill_switch_state.json`)." CONFIG_REFERENCE.md does not mention `uat.kill_switch`.  
**Economic impact:** Medium — if kill-switch state paths diverge, a kill-switch triggered in UAT won't affect production, and vice versa.  
**Probability bug is real:** 60% — hardcoded path in production code vs config-driven path in UAT is a classic split.  
**Recommended fix:** Make `ultron_risk_gate.py` read its persist path from `ultron_risk_gate` config section, with `logs/kill_switch_state.json` as default.

---

## Finding #20 — `ConfigValidator.fitness_weights` Keys Differ Between SCHEMAS.md and Production Config

**Type:** F (Config Drift — documentation schema doesn't match actual config)  
**Confidence:** HIGH  
**File locations:** SCHEMAS.md §5.1 vs `configs/production/v2_multi_2026_04.json:360-365`  
**Config key:** `config_validator.fitness_weights`  
**Runtime path:** ConfigValidator reads `fitness_weights` from `config_validator` section.  
**Evidence chain:** SCHEMAS.md §5.1 documents:
```json
{"expectancy": 0.35, "win_rate": 0.20, "trade_count": 0.20, "drawdown": 0.15, "consistency": 0.10}
```
Actual config v2_multi_2026_04:
```json
{"expectancy_rr": 0.5, "win_rate": 0.2, "trade_count_norm": 0.2, "drawdown": 0.1}
```
3 key name mismatches (`expectancy` vs `expectancy_rr`, `trade_count` vs `trade_count_norm`, `consistency` missing entirely). Weight values differ (expectancy 0.35 vs 0.5, no consistency weight). If ConfigValidator validates against the documented schema, validation will fail or silently use wrong weights.
**Economic impact:** HIGH — fitness calculation determines which configs get promoted. Wrong weights mean wrong configs are promoted. If `expectancy_rr` is weighted 0.5 (config) instead of 0.35 (doc), expectancy dominates the fitness score, potentially at the expense of drawdown and consistency.
**Probability bug is real:** 95% — the documented schema and actual config are provably different. Either ConfigValidator was updated without updating SCHEMAS.md, or vice versa.
**Recommended fix:** (1) Audit ConfigValidator code to determine which key names and weights it actually reads. (2) Update the loser (code or docs) to match. (3) Add a test (`tests/test_config_validator_fitness_weights.py`) that asserts the active config's fitness_weights match the documented defaults.

---

# Summary

## Probability Distribution

| Type | Count | Findings |
|------|-------|----------|
| A (Dead Config) | 7 | #1, #2, #3, #4, #10, #11, #14 |
| B (Partial Wiring) | 2 | #5, #17 |
| C (Shadow Override) | 3 | #6, #7, #19 |
| D (Split Brain) | 3 | #6, #9, #15, #18 |
| E (Unreachable Feature) | 2 | #8, #13 |
| F (Config Drift) | 3 | #10, #16, #20 |
| G (Runtime Divergence) | 1 | #9 |

## Economic Impact Ranking

1. **#9** — ultron_gate_enabled: false makes backtest results non-representative (HIGH)
2. **#18** — Two independent risk systems allow unbounded concurrent exposure (HIGH)
3. **#20** — Fitness weight mismatch promotes wrong configs (HIGH)
4. **#16** — Missing execution_planner keys cause hardcoded-fallback SL/RR (HIGH)
5. **#6** — Regime-adaptive fusion weights never applied (HIGH)
6. **#5** — 10 strategy configs may be decorative (HIGH)
7. **#1** — Capital management thresholds are decorative (2 configurable kill-switch values ignored)
8. **#10** — Belief gate (temporal conviction) never active (MEDIUM)
9. **#12** — Drift regime pause undetermined (MEDIUM)
10. **#13** — Auto-retrain trigger may never fire (MEDIUM)

## Quick Wins (<1 hour fixes)

1. **#20** — Fix SCHEMAS.md §5.1 fitness_weights to match actual config (update docs, 15 min)
2. **#4** — Remove `sl_tp_comparison` from production config (add citation to analytics config, 10 min)
3. **#10** — Add `signal_belief: {"enabled": false}` to production config (5 min)
4. **#11** — Add `cognitive_layer: {"enabled": false}` to production config (5 min)
5. **#7** — Add `promotion_margin_pct: 2.0` to governance section and document in CONFIG_REFERENCE.md (30 min)
6. **#16** — Add missing execution_planner keys to v2_multi_2026_04.json (20 min)

## Dangerous Fixes (require backtesting)

1. **#9** — Enabling `ultron_gate_enabled: true` will change backtest results (requires full regression)
2. **#18** — Unifying INOUT and CRT risk limits changes position sizing (requires portfolio backtest)
3. **#6** — Wiring regime_fusion_weights changes fusion behavior (requires regime-specific backtests)
4. **#1** — Wiring capital_management into UltronRiskGate changes kill-switch behavior (requires UAT)
5. **#5** — Activating StrategyOrchestrator consensus changes entry logic (requires A/B backtest)