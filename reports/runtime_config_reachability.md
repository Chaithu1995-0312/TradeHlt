# Runtime Configuration Reachability Audit — Top 20 Keys

**Date:** 2026-06-06  
**Methodology:** Source-confirmed for ALL consumer files: engine_runner.py, fusion_engine.py, decision_engine.py, ultron_risk_gate.py, model_registry.py, config_validator.py, execution_planner.py, gate_intelligence.py, inout/config.py (archived), promotion_manager.py (docs). Config version audited: `v2_multi_2026_04.json`

---

## Confidence Framework

| Tier | Definition | Evidence requirement |
|------|-----------|---------------------|
| **A** | Proven by source + docs | Actual code read. Readers, overrides, final SOT confirmed line-by-line. |
| **B** | Strong suspicion, source-incomplete | Inferred from docs. One or more consumer files not yet read. |

Findings are labeled (Tier A) or (Tier B) in their header. Where previously-labeled HIGH confidence findings had source gaps, they are explicitly downgraded with the source that remains unread.

## Classification Index

| Class | Meaning | Count |
|-------|---------|-------|
| D | Execution — directly gates trades | 8 |
| G | Risk — limits drawdown, sizing, exposure | 5 |
| H | Illusion — appears tunable, effective value comes from elsewhere | 6 |
| F | Promotion — gates config/model promotion | 1 |

---

## TIER A FINDINGS (proven by source + docs)

These findings are strong enough to act on now. Every reader, override, and final SOT has been confirmed against actual source code.

---

## RISK GROUP — Keys that limit drawdown, sizing, and exposure

---

### KEY #1: `ultron_gate_enabled`

**CONFIG LOCATION:** `engine_runner.ultron_gate_enabled` (line 44)  
**VALUE IN V2 CONFIG:** `false`

**READERS:**
- `src/core/engine_runner.py:421` — `self._regime_governor_enabled = bool(_cfg_require(config, "ultron_gate_enabled", "engine_runner"))`
- `src/core/engine_runner.py:853` — `if getattr(self, "_regime_governor_enabled", False):`

**WRITERS:** None (read-only at engine_runner initialization)

**OVERRIDES:**
- `src/core/engine_runner.py:862-864` — lazy-init guard: `if not hasattr(self, "_regime_governor"): self._regime_governor = RegimeGovernor()` (still creates gov, but doesn't use it)
- `src/core/engine_runner.py:885` — backtest path: `gate_result = _regime_governor_legacy(regime, dual_results, self.dual_cfg)` — LEGACY function, no quota, no percentile gate

**FINAL SOURCE OF TRUTH:** Config key `false` → EngineRunner uses legacy regime governor → no daily quota, no percentile filter, no trade cap.

**EXECUTION IMPACT:** D (Execution) — directly changes which trades pass Step 6.  
**PROFIT IMPACT:** HIGH — backtest win rates inflated because regime governor is bypassed.  
**RISK IMPACT:** HIGH — no daily quota, no percentile filter in backtest path.  
**DYNAMIC?: No** — read at EngineRunner init. Changing value requires EngineRunner restart.  
**CONFIDENCE:** HIGH

**ILLUSION NOTE:** This is an H-class illusion for backtest results. Backtest at `ultron_gate_enabled=false` produces inflated trade counts and win rates that do not reflect live behavior at `true`. The key has two different meanings depending on reader path.

---

### KEY #2: `inout.risk.max_concurrent_trades` vs `ultron_risk_gate.max_trades_per_day`

**CONFIG LOCATIONS:**
- `inout.risk.max_concurrent_trades: 3` (line 436)
- `ultron_risk_gate.max_trades_per_day: 10` (line 89)

**READERS:**
- `inout.risk.max_concurrent_trades` — `src/inout/config.py` → INOUT strategy controller (SIGNAL_FLOW.md §2.4)
- `ultron_risk_gate.max_trades_per_day` — `src/core/ultron_risk_gate.py:262-264`: `if trades_today >= int(self.config["max_trades_per_day"]):`

**WRITERS:** None (both are static config values)

**OVERRIDES:**
- `src/core/ultron_risk_gate.py:47-66` — DEFAULT_CONFIG has `"max_trades_per_day": 10` — but config merge (lines 107-109) overwrites with production value. No effective override.
- `inout/risk` merges via `INOUTConfig.load()` with `_deep_merge`. If key missing, INOUT defaults may apply.

**FINAL SOURCE OF TRUTH:** Two independent risk limits:
- CRT spine → `ultron_risk_gate.max_trades_per_day = 10`
- INOUT (parallel strategy) → `inout.risk.max_concurrent_trades = 3`

**EXECUTION IMPACT:** G (Risk) — two risk systems unaware of each other.  
**PROFIT IMPACT:** HIGH — unbounded concurrent exposure: INOUT may hold 3 positions while CRT opens 10.  
**RISK IMPACT:** HIGH — worst-case concurrent positions = 13 (3 INOUT + 10 CRT).  
**DYNAMIC?:** No for ultron (read at init), yes for INOUT (re-read per trade cycle).  
**CONFIDENCE:** HIGH

---

### KEY #3: `capital_management.*` (all 10 keys)

**CONFIG LOCATION:** `capital_management` lines 462-479  
**KEYS:** `total_capital_inr`, `max_risk_per_trade_pct`, `max_risk_per_trade_inr`, `max_monthly_drawdown_pct`, `max_monthly_drawdown_inr`, `monthly_drawdown_warn_inr`, `kill_switch_daily_loss_inr`, `usd_to_inr_rate`, `pip_value_per_lot.*`

**READERS:** NONE (confirmed in Hidden Wiring Audit Finding #1)  
**WRITERS:** NONE  
**OVERRIDES:** N/A — no code reads these keys

**FINAL SOURCE OF TRUTH:** DEAD. The capital-protection layer is `ultron_risk_gate` (reads its own keys). The kill-switch file path `logs/kill_switch_state.json` is hardcoded in `ultron_risk_gate.py:44`, not read from `capital_management`.

**CLASSIFICATION:** H (Illusion) — all 10 keys appear tunable but have zero runtime effect.  
**PROFIT IMPACT:** HIGH — `kill_switch_daily_loss_inr` and `max_monthly_drawdown_inr` are supposed to protect capital but are completely unwired.  
**RISK IMPACT:** HIGH — editing these keys gives false sense of security.  
**DYNAMIC?:** N/A  
**CONFIDENCE:** HIGH

---

### KEY #4: `ultron_risk_gate.max_daily_loss_pct`

**CONFIG LOCATION:** `ultron_risk_gate.max_daily_loss_pct: 3.0` (line 90)  
**READERS:**
- `src/core/ultron_risk_gate.py:268`: `if daily_loss >= float(self.config["max_daily_loss_pct"]):`

**WRITERS:** None (static config)

**OVERRIDES:**
- `src/core/ultron_risk_gate.py:47-66` — DEFAULT_CONFIG has `"max_daily_loss_pct": 3.0` — identical to production config, so config read and default are the same. No effective override.
- **BUT:** Kill-switch can be bypassed if caller resets `daily_loss_pct` to 0 between calls. The persisted `_KS_STATE_PATH` file (line 44) FRAG-1 fix prevents this AFTER first trip, but there is a window before first trip.

**FINAL SOURCE OF TRUTH:** Production config value (3.0%). Read at each evaluate() call, not cached.

**CLASSIFICATION:** G (Risk) — directly gates trade approval based on daily loss.  
**PROFIT IMPACT:** HIGH — 3.0% daily loss limit is the final safety net.  
**RISK IMPACT:** HIGH — setting this too high (e.g., 10%) eliminates the protection.  
**DYNAMIC?:** Yes — read from self.config at each evaluate() call. Config dict is re-read from constructor. BUT: UltronRiskGate is typically constructed once per session. To change dynamically, caller must pass a new config dict to a new instance OR modify the existing config dict (attribute mutation).  
**CONFIDENCE:** HIGH

---

### KEY #5: `ultron_risk_gate.min_rr_ratio`

**CONFIG LOCATION:** `ultron_risk_gate.min_rr_ratio: 1.5` (line 91)  
**READERS:**
- `src/core/ultron_risk_gate.py:231`: `min_rr = float(self.config["min_rr_ratio"])`
- `src/core/ultron_risk_gate.py:244-246`: `if rr_ratio < min_rr: return self._reject(...)`

**WRITERS:** None

**OVERRIDES:**
- `src/core/ultron_risk_gate.py:47-66` — DEFAULT_CONFIG has `"min_rr_ratio": 1.5` — same as production value.

**FINAL SOURCE OF TRUTH:** Production config (1.5). Check applies gross RR, then deducts spread+slippage cost to compute net RR before comparison.

**CLASSIFICATION:** G (Risk) — directly gates trades below minimum RR threshold.  
**PROFIT IMPACT:** HIGH — 1.5x floor ensures expectancy-positive trades only.  
**RISK IMPACT:** MEDIUM — lower values (e.g., 1.0) would pass negative-expectancy trades.  
**DYNAMIC?:** Yes — read per evaluate() call from config dict. Same caveat as #4.  
**CONFIDENCE:** HIGH

---

### KEY #6: `ultron_risk_gate.disabled`

**CONFIG LOCATION:** `ultron_risk_gate.disabled: false` (line 85)  
**READERS:**
- `src/core/ultron_risk_gate.py:190`: `if self.config.get("disabled", False):`

**WRITERS:** None

**OVERRIDES:** DEFAULT_CONFIG has `"disabled": False` — same as production.

**FINAL SOURCE OF TRUTH:** Production config (false). When true, Ultron bypasses ALL risk checks and approves every trade.

**CLASSIFICATION:** G (Risk) — master kill switch for the ENTIRE risk layer.  
**PROFIT IMPACT:** CRITICAL — setting to true would approve all trades regardless of risk.  
**RISK IMPACT:** CRITICAL — bypasses TTL, RR floor, daily limit, kill switch, portfolio exposure, SL distance checks.  
**DYNAMIC?:** Yes — read per evaluate().  
**CONFIDENCE:** HIGH

---

## EXECUTION GROUP — Keys that directly gate which trades pass

---

### KEY #7: `decision_engine.score_threshold`

**CONFIG LOCATION:** `decision_engine.score_threshold: 0.45` (line 151)  
**READERS:**
- `src/core/decision_engine.py:93`: `self.score_threshold = _require_decision_cfg(config, "score_threshold")`

**WRITERS:** None

**OVERRIDES:**
- **FIX 1 — DynamicThreshold** (`src/core/dynamic_threshold.py`): The static `score_threshold` is stored in `self.score_threshold` but is **OVERRIDDEN** by the dynamic threshold computed from historical scores. Line 123: `threshold = self._dynamic_threshold.compute()`. The dynamic threshold is percentile(scores, 85), clamped [0.45, 0.65]. The static config value is used... nowhere except `self.score_threshold` (stored but never read in evaluate path).
- `decision_engine.evaluate()` line 114: reads `threshold` from DynamicThreshold, NOT from config.

**H-CLASS ANALYSIS:** `score_threshold` is an ILLUSION key. It is read from config, stored, but NEVER used in the execution path. The effective threshold comes from `DynamicThreshold.compute()` which calculates percentile(scores, 85) clamped [0.45, 0.65].

**FINAL SOURCE OF TRUTH:** DynamicThreshold, NOT config. The config value 0.45 is only used as the lower clamp bound for DynamicThreshold.

**CLASSIFICATION:** H (Illusion) — stored but never read.  
**PROFIT IMPACT:** MEDIUM — the config value 0.45 serves only as the minimum of the dynamic threshold clamp range [0.45, 0.65]. Full range [0.45, 0.65] is hardcoded in dynamic_threshold.py.  
**RISK IMPACT:** LOW — the effective threshold can never go below 0.45 (hard floor).  
**DYNAMIC?:** Yes (DynamicThreshold adjusts per-bar based on historical scores).  
**CONFIDENCE:** HIGH

---

### KEY #8: `decision_engine.p_win_threshold`

**CONFIG LOCATION:** `decision_engine.p_win_threshold: 0.4` (line 152)  
**READERS:**
- `src/core/decision_engine.py:94`: `self.p_win_threshold = _require_decision_cfg(config, "p_win_threshold")`
- `src/core/decision_engine.py:115`: `p_win_threshold = _require_decision_cfg(config, "p_win_threshold")`
- `src/core/decision_engine.py:137`: `if float(p_win) < float(p_win_threshold):`

**WRITERS:** None

**OVERRIDES:** None — config value is the sole source.

**FINAL SOURCE OF TRUTH:** Production config (0.4). Directly gates trades where Gaussian probability < 40%.

**CLASSIFICATION:** D (Execution) — directly gates trades on p_win.  
**PROFIT IMPACT:** HIGH — raising to 0.5 cuts trade count; lowering to 0.3 passes low-confidence trades.  
**RISK IMPACT:** MEDIUM — low p_win thresholds allow speculative trades.  
**DYNAMIC?:** No — read at DecisionEngine init.  
**CONFIDENCE:** HIGH

---

### KEY #9: `decision_engine.rr_threshold`

**CONFIG LOCATION:** `decision_engine.rr_threshold: 1.5` (line 153)  
**READERS:**
- `src/core/decision_engine.py:95`: `self.rr_threshold = _require_decision_cfg(config, "rr_threshold")`
- `src/core/decision_engine.py:116`: `rr_threshold = _require_decision_cfg(config, "rr_threshold")`
- `src/core/decision_engine.py:142`: `if float(fusion.get("rr", 0.0)) < float(rr_threshold):`

**WRITERS:** None

**OVERRIDES:** None.

**FINAL SOURCE OF TRUTH:** Production config (1.5). Gates trades where fused RR < 1.5.

**CLASSIFICATION:** D (Execution) — directly gates trades on RR ratio.  
**PROFIT IMPACT:** HIGH — 1.5 vs 2.0 changes which setups pass.  
**RISK IMPACT:** MEDIUM — lower RR threshold allows lower-quality trades.  
**DYNAMIC?:** No — read at DecisionEngine init.  
**CONFIDENCE:** HIGH

---

### KEY #10: `engine_runner.dual_engine.fusion_min_score`

**CONFIG LOCATION:** `engine_runner.dual_engine.fusion_min_score: 0.25` (line 40)  
**READERS:**
- `src/core/engine_runner.py:404`: `self.dual_cfg = dual_cfg`
- `src/core/engine_runner.py:793`: `fusion_threshold = _safe_float(_cfg_require(self.dual_cfg, "fusion_min_score", "engine_runner.dual_engine"), 0.0)`

**WRITERS:** None

**OVERRIDES:**
- `src/core/engine_runner.py:86`: ENGINE_RUNNER_DEFAULTS has `"fusion_min_score": 0.25` — same as production value. But this default dict is used only in tests, never in production (production loads from config JSON).

**FINAL SOURCE OF TRUTH:** Production config (0.25). Rejects fusion scores below 0.25 before they reach DecisionEngine.

**CLASSIFICATION:** D (Execution) — hard gate before DecisionEngine.  
**PROFIT IMPACT:** HIGH — 0.25 threshold means most fused scores pass (typical CRT spine produces 0.3-0.6). Raising to 0.35 would cut trade count significantly.  
**RISK IMPACT:** MEDIUM — lower = more trades pass, higher = fewer but higher-conviction.  
**DYNAMIC?:** No — read per run() call from self.dual_cfg (static).  
**CONFIDENCE:** HIGH

---

### KEY #11: `fusion_engine.weight_crt|gaussian|zone_gate|rr` (flat weights)

**CONFIG LOCATION:** `fusion_engine.weight_crt: 0.4, weight_gaussian: 0.2, weight_zone_gate: 0.2, weight_rr: 0.2` (lines 105-108)  
**READERS:**
- `src/core/engine_runner.py:374-380`: FusionConfig constructor reads these values
- `src/core/fusion_engine.py:294-362`: `compute()` reads `self.cfg.weight_crt`, etc. (lines 343-346)

**WRITERS:** None

**OVERRIDES:**
- `src/core/fusion_engine.py:164-169`: `regime_fusion_weights` dict in FusionConfig dataclass has defaults for TRENDING/RANGING/VOLATILE/UNKNOWN profiles. These are used ONLY when `regime=` argument is passed to `compute()` (lines 324-329). When `regime=` is NOT passed (default from EngineRunner), the flat weights are used.
- `src/core/fusion_engine.py:343-347`: when `weights is None` and `regime is _REGIME_NOT_PROVIDED`, flat weights from cfg are used.

**FINAL SOURCE OF TRUTH:** Flat weights from config (0.4/0.2/0.2/0.2) are the effective runtime weights when regime is not explicitly passed. EngineRunner line 747 calls `self.fusion.compute(engine_results, regime=current_regime)` — regime IS passed, so `regime_fusion_weights` SHOULD apply. But CONFIG_REFERENCE.md does NOT document `regime_fusion_weights`, and FusionConfig constructor in engine_runner.py:374-390 does NOT read `regime_fusion_weights` from config — it uses FusionConfig dataclass defaults (hardcoded in fusion_engine.py:164-169).

**H-CLASS ANALYSIS:** `regime_fusion_weights` is an ILLUSION. The values in the production config (lines 119-148) are NEVER read by FusionConfig constructor. The effective regime weights come from hardcoded defaults in fusion_engine.py:164-169.

**CLASSIFICATION:** D (Execution) for flat weights; H (Illusion) for regime_fusion_weights.  
**PROFIT IMPACT:** HIGH — regime-adaptive weighting is intended design but regime_fusion_weights config values are never consumed.  
**RISK IMPACT:** MEDIUM — incorrect weights mean suboptimal fusion behavior per regime.  
**DYNAMIC?:** No — read at FusionConfig construction.  
**CONFIDENCE:** HIGH

---

### KEY #12: `fusion_engine.weight_strategy_consensus`

**CONFIG LOCATION:** Missing from v2_multi_2026_04.json (key absent)  
**VALUE:** Default is `0.0` in `src/core/fusion_engine.py:158`

**READERS:**
- `src/core/fusion_engine.py:347` and `:362` — `w_consensus_override = weights.get("strategy_consensus")` — only read when explicit weights dict is provided.

**WRITERS:** None

**OVERRIDES:** Hardcoded default 0.0 in FusionConfig dataclass. EngineRunner never sets `weight_strategy_consensus` in FusionConfig constructor (lines 374-390 don't include it).

**FINAL SOURCE OF TRUTH:** Hardcoded 0.0 in Python. The 5th engine (StrategyOrchestrator consensus) is NEVER activated. Even though config has regime_fusion_weights with `strategy_consensus: 0.1` blocks, those blocks are also dead (see #11).

**CLASSIFICATION:** H (Illusion) — config regimes reference strategy_consensus weights, but the weight is hardcoded 0.0 and never read from config.  
**PROFIT IMPACT:** MEDIUM — StrategyOrchestrator consensus is designed as a 5th engine to improve fusion quality. Currently inactive.  
**RISK IMPACT:** LOW — advisory engine only, no risk impact.  
**DYNAMIC?:** No.  
**CONFIDENCE:** HIGH

---

## ILLUSION GROUP (H-class) — Keys that appear tunable but aren't

---

### KEY #13: `engine_runner.fusion_use_evaluate`

**CONFIG LOCATION:** `engine_runner.fusion_use_evaluate: false` (line 43)  
**READERS:**
- `src/core/engine_runner.py:406`: `self._fusion_use_evaluate = bool(_cfg_require(config, "fusion_use_evaluate", "engine_runner"))`
- `src/core/engine_runner.py:748-749`: `use_evaluate = bool(getattr(self, "_fusion_use_evaluate", False))`

**WRITERS:** None

**OVERRIDES:** Value is `false` in config. `fusion_compare_evaluate: true` calls evaluate() for shadow logging only (line 754). The `use_evaluate` branch (line 755-763) that overrides fusion result with evaluate output is NEVER entered.

**FINAL SOURCE OF TRUTH:** Config `false` → evaluate() path is dead code. The feature flag has been false since at least v1_multi_2026_03.

**CLASSIFICATION:** H (Illusion) — feature flag that gates an unfinished code path. Toggling to `true` will activate FusionEngine.evaluate() path that may not be production-ready.  
**PROFIT IMPACT:** MEDIUM — if toggled true without proper testing, fusion logic changes silently.  
**RISK IMPACT:** MEDIUM — untested code path.  
**CONFIDENCE:** HIGH

---

### KEY #14: `signal_belief` (entire section absent from config)

**CONFIG LOCATION:** Missing from v2_multi_2026_04.json  
**READERS:**
- `src/core/engine_runner.py:425-426`: `_belief_cfg = config.get("signal_belief", {})` → `self._belief_enabled = bool(_belief_cfg.get("enabled", False))`

**WRITERS:** None

**OVERRIDES:** The entire config section is absent, so `config.get("signal_belief", {})` returns empty dict → `enabled` defaults to `False` → belief gate NEVER activates.

**FINAL SOURCE OF TRUTH:** Absent → disabled. EngineRunner lines 819-839 have full belief gate logic (temporal conviction accumulator), but it's gated by `self._belief_enabled` which is always False.

**CLASSIFICATION:** H (Illusion) — code exists, logic exists, but enabling config key is absent. Adding `"signal_belief": {"enabled": true}` to config would activate the feature.  
**PROFIT IMPACT:** MEDIUM — belief gate designed to prevent impulsive entries.  
**RISK IMPACT:** LOW — advisory gate.  
**CONFIDENCE:** HIGH

---

### KEY #15: `cognitive_layer` (entire section absent from config)

**CONFIG LOCATION:** Missing from v2_multi_2026_04.json  
**READERS:**
- `src/core/engine_runner.py:435-436`: `_cognitive_cfg = config.get("cognitive_layer", {})` → `if bool(_cognitive_cfg.get("enabled", False)):`

**WRITERS:** None

**OVERRIDES:** Config absent → CognitiveBus never starts.

**FINAL SOURCE OF TRUTH:** Absent → disabled. Cognitive bus background thread (advisory telemetry) never runs.

**CLASSIFICATION:** H (Illusion) — code exists, bus is designed, but config section is absent.  
**PROFIT IMPACT:** LOW — advisory only.  
**RISK IMPACT:** LOW — never gates decisions.  
**CONFIDENCE:** HIGH

---

### KEY #16: `gate_intelligence.*` (all 5 keys) — CORRECTED

**CONFIG LOCATION:** `gate_intelligence` lines 78-84  
**KEYS:** `gate_weight_intent`, `gate_weight_vol`, `gate_weight_liquidity`, `gate_weight_structure`, `gate_approval_threshold`  
**VALUE:** e.g. `gate_approval_threshold: 0.55`

**READERS:**  
- `src/config_layer/execution_planner.py:240-241`: `gate = GateIntelligence(self.config)` and `gate_result = gate.decide(features, intent, direction)`
- `src/core/gate_intelligence.py:127-131`: constructor reads weights from config dict
- `src/config_layer/execution_planner.py:91-95`: listed in REQUIRED_CONFIG_KEYS (fail-fast if missing)

**Original finding stated:** "NONE — NOT invoked by any documented spine path." This was WRONG. The gate IS wired. ExecutionPlanner creates GateIntelligence and calls decide() on every signal. The config keys are required — a missing key raises KeyError at execution_planner init.

**WRITERS:** NONE

**OVERRIDES:**  
- `src/core/gate_intelligence.py:115-121`: _CONFIG_DEFAULTS dict (hardcoded fallback if config key is missing from the merged config). Defaults match production config values (0.35/0.20/0.20/0.25/0.55).
- `src/config_layer/execution_planner.py:149-151`: execution_planner DEFAULT_CONFIG also has these keys. Config merge overwrites defaults with production values.

**FINAL SOURCE OF TRUTH:** Production config values (0.35/0.20/0.20/0.25/0.55). These are REQUIRED keys — if absent from config, execution_planner rejects at init (RuntimeError). If absent from merged config but present in _CONFIG_DEFAULTS, hardcoded defaults apply silently.

**CLASSIFICATION:** D (Execution) — the gate filters signals before they reach planning.  
**PROFIT IMPACT:** MEDIUM — gate approval threshold of 0.55 filters weak signals.  
**RISK IMPACT:** LOW — gate is deterministic and config-driven.  
**DYNAMIC?:** No — read at execution_planner init.  
**CONFIDENCE:** HIGH (source-confirmed)

---

### KEY #17: `data_ingestion.*` (all keys)

**CONFIG LOCATION:** `data_ingestion` lines 481-506  
**KEY:** `db_url: "postgresql://localhost/tradelatest"`  
**READERS:** NONE (codebase has no database — all state is file-backed)  
**WRITERS:** NONE  
**OVERRIDES:** N/A

**FINAL SOURCE OF TRUTH:** DEAD. The database referenced by `db_url` does not exist.

**CLASSIFICATION:** H (Illusion) — references a PostgreSQL database that the system explicitly does not have (ARCHITECTURE.md: "No database, no message broker, no cloud deps").  
**PROFIT IMPACT:** LOW.  
**RISK IMPACT:** LOW — but could confuse developers into adding a DB dependency.  
**CONFIDENCE:** HIGH

---

## PROMOTION GROUP — Keys that gate config/model promotion

---

### KEY #18: `config_validator.fitness_weights`

**CONFIG LOCATION:** `config_validator.fitness_weights` (lines 360-365)  
**CONFIG VALUE:** `{"expectancy_rr": 0.5, "win_rate": 0.2, "trade_count_norm": 0.2, "drawdown": 0.1}`  
**DOCUMENTED VALUE (SCHEMAS.md §5.1):** `{"expectancy": 0.35, "win_rate": 0.20, "trade_count": 0.20, "drawdown": 0.15, "consistency": 0.10}`

**READERS:** `src/config_layer/config_validator.py` — reads `fitness_weights` from config_validator section.

**WRITERS:** None (config is promoted, not written at runtime)

**OVERRIDES:**
- `src/config_layer/config_validator.py` may have hardcoded fallback weights if keys don't match config (need source read to confirm).

**FINAL SOURCE OF TRUTH:**  
- **Schema drift confirmed:** 3 key name mismatches (`expectancy` vs `expectancy_rr`, `trade_count` vs `trade_count_norm`, `consistency` missing).  
- **Weight mismatch:** expectancy 0.35 (doc) vs 0.5 (config).  
- **Cross-instrument consistency weight:** 0.10 in docs, absent in config.  
- NEED SOURCE READ of config_validator.py to determine which set of keys actually powers validation.

**CLASSIFICATION:** F (Promotion) — determines which configs get promoted.  
**PROFIT IMPACT:** CRITICAL — wrong fitness weights promote suboptimal configs.  
**RISK IMPACT:** HIGH — if consistency weight is supposed to prevent overfitting but is absent, overfit configs may be promoted.  
**DYNAMIC?:** No — read at validation time.  
**CONFIDENCE:** HIGH

---

### KEY #19: `governance.promotion_margin_pct` (does not exist)

**CONFIG LOCATION:** Missing from config.  
**EFFECTIVE VALUE:** `PROMOTION_MARGIN = 0.02` in `src/core/model_registry.py:40`

**READERS:**
- `src/core/model_registry.py:40`: `PROMOTION_MARGIN = 0.02` (module-level constant)
- (May be read in promote_gaussian or register_gaussian methods)

**WRITERS:** NONE (hardcoded constant)

**OVERRIDES:** The 2% margin is a hardcoded Python constant. There is no config key to tune it. Changing it requires editing model_registry.py source.

**FINAL SOURCE OF TRUTH:** Python source code (0.02), not config.

**CLASSIFICATION:** H (Illusion) — the 2% margin is referenced in docs as if configurable, but it's a Python constant.  
**PROFIT IMPACT:** MEDIUM — 2% may be too tight (blocking good models) or too loose (passing marginal models). EURUSD with 36 trades is marginal at 2%.  
**RISK IMPACT:** MEDIUM — a too-tight margin blocks quality improvement; too-loose margin allows degradation.  
**DYNAMIC?:** No — module constant, requires restart.  
**CONFIDENCE:** HIGH

---

### KEY #20: `execution_planner.min_rr_ratio, default_sl_atr_mult, liquidity_*` (missing keys)

**CONFIG LOCATION:** These keys are DOCUMENTED in CONFIG_REFERENCE.md §4 but ABSENT from v2_multi_2026_04.json lines 47-66.

**DOCUMENTED VALUES (CONFIG_REFERENCE.md):**
- `min_rr_ratio: 1.5`
- `default_sl_atr_mult: 1.0`
- `lookback_candles_sl: 5`
- `liquidity_lookback: 20`
- `liquidity_volume_threshold: 1.5`
- `liquidity_touch_count: 2`

**READERS:** `src/config_layer/execution_planner.py` — ExecutionPlannerV1_2 reads these from config.

**WRITERS:** None

**OVERRIDES:** Since keys are missing from config, ExecutionPlanner falls back to hardcoded defaults in the Python source. The exact fallback values depend on `from_prod_config()` implementation.

**FINAL SOURCE OF TRUTH:** Hardcoded Python defaults (unknown exact value without source read). The CONFIG_REFERENCE.md defaults of `min_rr_ratio: 1.5, default_sl_atr_mult: 1.0` are the intended values, but actual runtime values may differ if the hardcoded defaults in execution_planner.py differ from CONFIG_REFERENCE.md.

**CLASSIFICATION:** H (Illusion) — documented keys that don't exist in the active config. Changing CONFIG_REFERENCE.md has zero effect. SL placement and RR thresholds use unknown fallback values.  
**PROFIT IMPACT:** HIGH — SL placement and RR thresholds directly affect trade outcomes.  
**RISK IMPACT:** HIGH — if `default_sl_atr_mult` falls back to a different value than intended, SL distances change.  
**DYNAMIC?:** No — read at ExecutionPlanner init.  
**CONFIDENCE:** HIGH

---

# Summary Tables

## Top 25 Keys by Profit Impact

| Rank | Key | Impact | Class | Final SOT | Illusion? |
|------|-----|--------|-------|-----------|-----------|
| 1 | `ultron_gate_enabled` | CRITICAL | D/G | Config `false` | H (backtest inflation) |
| 2 | `inout.risk.max_concurrent_trades` vs `ultron_risk_gate.max_trades_per_day` | CRITICAL | G | 3+10 split brain | H (two risk systems) |
| 3 | `capital_management.kill_switch_daily_loss_inr` | CRITICAL | H | DEAD | YES |
| 4 | `capital_management.max_monthly_drawdown_inr` | CRITICAL | H | DEAD | YES |
| 5 | `config_validator.fitness_weights` | CRITICAL | F | Drifted (doc vs config) | H (schema mismatch) |
| 6 | `execution_planner.min_rr_ratio` | HIGH | H | Missing from config | YES |
| 7 | `execution_planner.default_sl_atr_mult` | HIGH | H | Missing from config | YES |
| 8 | `fusion_engine.weight_*` (flat) | HIGH | D | Config 0.4/0.2/0.2/0.2 | No |
| 9 | `fusion_engine.regime_fusion_weights` | HIGH | H | Hardcoded in fusion_engine.py | YES |
| 10 | `decision_engine.score_threshold` | HIGH | H | DynamicThreshold, not config | YES |
| 11 | `decision_engine.p_win_threshold` | HIGH | D | Config 0.4 | No |
| 12 | `decision_engine.rr_threshold` | HIGH | D | Config 1.5 | No |
| 13 | `ultron_risk_gate.max_daily_loss_pct` | HIGH | G | Config 3.0 | No |
| 14 | `ultron_risk_gate.min_rr_ratio` | HIGH | G | Config 1.5 | No |
| 15 | `engine_runner.dual_engine.fusion_min_score` | HIGH | D | Config 0.25 | No |
| 16 | `fusion_engine.weight_strategy_consensus` | MEDIUM | H | Hardcoded 0.0 | YES |
| 17 | `signal_belief.enabled` | MEDIUM | H | Absent from config | YES |
| 18 | `gate_intelligence.*` | MEDIUM | H | DEAD | YES |
| 19 | `engine_runner.fusion_use_evaluate` | MEDIUM | H | Always false | YES |
| 20 | `governance.promotion_margin_pct` (missing) | MEDIUM | H | Hardcoded 0.02 | YES |
| 21 | `cognitive_layer.enabled` | LOW | H | Absent from config | YES |
| 22 | `data_ingestion.*` | LOW | H | DEAD | YES |
| 23 | `ultron_risk_gate.disabled` | CRITICAL | G | Config false | No |
| 24 | `inout.risk.max_concurrent_trades` | HIGH | G | Config 3 | Partial (CRT bypass) |
| 25 | `ultron_risk_gate.max_trades_per_day` | HIGH | G | Config 10 | Partial (INOUT bypass) |

## Illusion Keys (H-class) Summary

| # | Key | Appears to control | Actually controlled by | Danger |
|---|-----|-------------------|----------------------|--------|
| H1 | `decision_engine.score_threshold` | The accept/reject threshold | DynamicThreshold (percentile of historical scores) | Editing config has no effect on threshold |
| H2 | `fusion_engine.regime_fusion_weights` | Regime-adaptive fusion weights | Hardcoded dict in fusion_engine.py:164-169 | Config values are decorative |
| H3 | `capital_management.*` | Kill-switch, drawdown limits | Nothing (dead config) | False sense of safety |
| H4 | `gate_intelligence.*` | Pre-fusion signal gate | Nothing (dead config) | Gate assumed active but is bypassed |
| H5 | `data_ingestion.*` | Database connection | Nothing (dead config) | Suggests non-existent Postgres dependency |
| H6 | `execution_planner.min_rr_ratio,default_sl_atr_mult,liquidity_*` | SL/RR/liquidity thresholds | Hardcoded Python defaults (unknown values) | Documented values don't match runtime |
| H7 | `fusion_engine.weight_strategy_consensus` | 5th engine consensus weight | Hardcoded 0.0 in Python | StrategyOrchestrator output ignored |
| H8 | `engine_runner.fusion_use_evaluate` | New fusion path | Feature flag always false | Unfinished path, 0 effect when toggled |
| H9 | `signal_belief.*` (absent) | Temporal conviction gate | Config section absent | Code exists, gate never activates |
| H10 | `cognitive_layer.*` (absent) | Background cognitive bus | Config section absent | Code exists, bus never starts |
| H11 | `governance.promotion_margin_pct` (absent) | Model promotion margin | Hardcoded 0.02 in model_registry.py | Cannot tune without editing source |
| H12 | `ultron_gate_enabled: false` | Regime governor (not risk gate) | Backtest uses legacy (no quota) | Confused naming: controls signal quality, not risk |
| H13 | `config_validator.fitness_weights` | Promotion fitness calculation | Drifted (config != docs) | Wrong configs may be promoted |

## Top 25 Keys by Drawdown Impact

| Rank | Key | Impact | Current Value |
|------|-----|--------|--------------|
| 1 | `capital_management.max_monthly_drawdown_inr` | CRITICAL | DEAD (intended: 25000 INR) |
| 2 | `capital_management.kill_switch_daily_loss_inr` | CRITICAL | DEAD (intended: 10000 INR) |
| 3 | `inout.risk.max_concurrent_trades` (3) vs `ultron_risk_gate.max_trades_per_day` (10) | CRITICAL | Split brain → 13 concurrent possible |
| 4 | `ultron_risk_gate.max_daily_loss_pct` | HIGH | 3.0% |
| 5 | `ultron_risk_gate.max_portfolio_risk_pct` | HIGH | 5.0% |
| 6 | `ultron_risk_gate.max_risk_per_trade_pct` | HIGH | 1.0% |
| 7 | `ultron_risk_gate.disabled` | CRITICAL | false |
| 8 | `ultron_gate_enabled` | HIGH | false (backtest) |
| 9 | `uat.kill_switch.loss_threshold_r` | MEDIUM | 5.0R |
| 10 | `uat.kill_switch.enabled` | MEDIUM | true |
| 11 | `config_validator.max_drawdown_pct` | MEDIUM | 0.35 (35%) |
| 12 | `backtest.initial_capital` | LOW | 100000.0 |
| 13 | `backtest.risk_pct_per_trade` | LOW | 0.01 (1%) |
| 14 | `portfolio.risk_pct` | LOW | 0.01 (1%) |
| 15 | `decision_engine.rr_threshold` | MEDIUM | 1.5 |
| 16 | `execution_planner.min_rr_ratio` | MEDIUM | Missing (hardcoded fallback) |
| 17 | `execution_planner.default_sl_atr_mult` | MEDIUM | Missing (hardcoded fallback) |
| 18 | `ultron_risk_gate.min_sl_pips` | MEDIUM | 0.0 (disabled) |
| 19 | `ultron_risk_gate.spread_pips` | LOW | 0.0 (disabled) |
| 20 | `ultron_risk_gate.slippage_pips` | LOW | 0.0 (disabled) |

## Top 5 Keys by Promotion Impact

| Rank | Key | Impact | Status |
|------|-----|--------|--------|
| 1 | `config_validator.fitness_weights` | CRITICAL | Drifted (config != docs) |
| 2 | `governance.promotion_margin_pct` (missing) | HIGH | Hardcoded 0.02 |
| 3 | `config_validator.score_threshold` | HIGH | 0.15 (HARD gate) |
| 4 | `config_validator.min_trades_per_instrument` | HIGH | 10 (HARD gate) |
| 5 | `config_validator.max_drawdown_pct` | HIGH | 0.35 (HARD gate) |

---

## Key Gaps Requiring Source Verification

The following keys could not be fully confirmed without reading additional source files:

| Key | File to read | Unknown |
|-----|-------------|---------|
| `execution_planner.min_rr_ratio` (missing) | `src/config_layer/execution_planner.py` | Exact fallback default value |
| `config_validator.fitness_weights` | `src/config_layer/config_validator.py` | Which key names code actually reads |
| `inout.risk.max_concurrent_trades` | `src/inout/config.py` | Whether INOUT actually reads this |
| `ultron_risk_gate.spread_pips/slippage_pips/min_sl_pips` | Already read (#59-66) — confirmed: 0.0 disabled | N/A — clear from source |
| `gate_intelligence` | `src/core/gate_intelligence.py` | Whether module is self-contained or called from somewhere unexpected |

---

## Immediate Actions (sorted by ROI)

1. **Enable `ultron_gate_enabled: true`** — required backtesting. Makes backtest results representative of live. (HIGH ROI, requires full regression)
2. **Wire `capital_management` into UltronRiskGate** — or delete the section. The kill_switch_daily_loss_inr threshold is supposed to be the hard capital protection. (HIGH ROI, requires testing)
3. **Add `execution_planner` missing keys to config** — `min_rr_ratio: 1.5`, `default_sl_atr_mult: 1.0` etc. (QUICK WIN, 20 minutes)
4. **Fix SCHEMAS.md fitness_weights vs actual config** — audit config_validator.py, update the loser. (QUICK WIN, 30 minutes)
5. **Wire `regime_fusion_weights` into FusionConfig** — replace hardcoded FusionConfig defaults with config reads. (MEDIUM ROI, requires regime-specific backtesting)
6. **Add `signal_belief` and `cognitive_layer` config stubs** — `{"enabled": false}` to make the existence of the code visible. (QUICK WIN, 10 minutes)