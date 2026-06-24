# Known Config Illusions

> **Operational truth — not narrative.**
> Every key listed below appears tunable but has **zero runtime effect**.
>
> Source: `reports/runtime_config_reachability.md` (Tier A source-confirmed, 2026-06-06)
> and `reports/hidden_wiring_audit.md` (20 findings, 2026-06-06).
>
> Last verified: 2026-06-10

---

## Classification

| Class | Meaning |
|-------|---------|
| **H-Dead** | Config key exists, documented, but has zero consumers in code |
| **H-Split** | Key produces different behavior in backtest vs live (systematic divergence) |
| **H-Shadow** | Effective value comes from hardcoded constant or DynamicThreshold, not config |
| **H-Doc** | Key documented but misunderstood — code follows config, docs are wrong |
| **D-Orphan** | Module exists but is not wired in any production path |

---

## Illusions Register

### #1 — `capital_management.*` (all 10 keys)

| Field | Value |
|-------|-------|
| **Config location** | `v2_multi_2026_04.json:462-479` |
| **Keys** | `total_capital_inr`, `max_risk_per_trade_pct`, `max_risk_per_trade_inr`, `max_monthly_drawdown_pct`, `max_monthly_drawdown_inr`, `monthly_drawdown_warn_inr`, `kill_switch_daily_loss_inr`, `usd_to_inr_rate`, `pip_value_per_lot.*` |
| **Documentation** | CONFIG_REFERENCE.md lists every section's consumer — `capital_management` is absent |
| **Reality** | Zero consumers. The capital-protection layer is `ultron_risk_gate` (reads its own keys). Kill-switch file path is hardcoded in `ultron_risk_gate.py:44`. |
| **Class** | H-Dead |
| **Confidence** | HIGH |
| **Action** | Either wire into UltronRiskGate or delete the section |
| **Risk** | A trader editing kill_switch_daily_loss_inr expects capital protection but gets nothing |

---

### #2 — `data_ingestion.*` (5 keys)

| Field | Value |
|-------|-------|
| **Config location** | `v2_multi_2026_04.json:481-506` |
| **Keys** | `db_url` (points to `postgresql://localhost/tradelatest`), `mt5_enabled: false` |
| **Documentation** | CLAUDE.md §1: "no database, no message broker, no cloud deps" |
| **Reality** | All state is file-backed. No PostgreSQL exists. Signal flow reads from CSV (SIGNAL_FLOW.md §1 Step 1). |
| **Class** | H-Dead |
| **Confidence** | HIGH (90%) |
| **Action** | Delete the section |
| **Risk** | Low — dormant, but misleads new developers about database dependency |

---

### #3 — `gate_intelligence.*` (5 keys)

| Field | Value |
|-------|-------|
| **Config location** | `v2_multi_2026_04.json:78-84` |
| **Keys** | `gate_weight_intent`, `gate_weight_vol`, `gate_weight_liquidity`, `gate_weight_structure`, `gate_approval_threshold: 0.55` |
| **Documentation** | Absent from CONFIG_REFERENCE.md and ARCHITECTURE.md §6.2 |
| **Reality** | No consumer in spine (EngineRunner → FusionEngine → DecisionEngine → ExecutionPlanner → UltronRiskGate). **However:** gate_intelligence module IS wired via ExecutionPlanner delegation (corrected 2026-06-06 from H-Dead to D-Execution for the module itself). These specific keys remain dead. |
| **Class** | H-Dead (keys only — module is active via different path) |
| **Confidence** | HIGH (85%) |
| **Action** | Wire as pre-fusion gate or delete keys |
| **Risk** | Medium — a multi-weight gate with approval threshold 0.55 designed to filter signals is bypassed |

---

### #4 — `sl_tp_comparison.*` (6 keys)

| Field | Value |
|-------|-------|
| **Config location** | `v2_multi_2026_04.json:67-77` |
| **Keys** | `legacy_sl_atr_mult`, `legacy_tp_atr_mult_*`, `primary_metric`, `output_path` |
| **Documentation** | Config's own `_comment` field: "Used ONLY by SLTPComparator, never in live path" |
| **Reality** | Self-declared dead. SLTPComparator is an analytics tool, never in live or backtest trade path. |
| **Class** | H-Dead (self-declared) |
| **Confidence** | 100% |
| **Action** | Move to separate `analytics_config` file or remove from production config |
| **Risk** | Low — analytical tool only. Misleads tuner into thinking these values affect live execution. |

---

### #5 — `signal_belief.*`

| Field | Value |
|-------|-------|
| **Config location** | `v2_multi_2026_04.json` |
| **Keys** | Unconfirmed exact set |
| **Documentation** | Minimal |
| **Reality** | No consumer found in any engine or gate during both audits |
| **Class** | H-Dead |
| **Confidence** | MEDIUM |
| **Action** | Investigate whether module exists. Add `{"enabled": false}` stub or delete. |
| **Risk** | Low |

---

### #6 — `cognitive_layer.*`

| Field | Value |
|-------|-------|
| **Config location** | `v2_multi_2026_04.json` |
| **Keys** | Unconfirmed exact set |
| **Documentation** | Minimal |
| **Reality** | No consumer found. Module may not exist in current codebase. |
| **Class** | H-Dead |
| **Confidence** | MEDIUM |
| **Action** | Investigate whether module exists. Add `{"enabled": false}` stub or delete. |
| **Risk** | Low |

---

### #7 — `phase5_calibration.min_val_samples`

| Field | Value |
|-------|-------|
| **Config location** | `v2_multi_2026_04.json` |
| **Value** | 30 |
| **Reality** | Phase5Calibration now reads from `training` config section, not top-level `phase5_calibration` |
| **Class** | H-Dead |
| **Confidence** | MEDIUM |
| **Action** | Remove from top-level or rewire |

---

### #8 — `decision_engine.score_threshold`

| Field | Value |
|-------|-------|
| **Config location** | `decision_engine.score_threshold: 0.45` (line 151) |
| **Documentation** | CONFIG_REFERENCE.md documents as tunable threshold |
| **Reality** | Read from config (`decision_engine.py:93`), stored in `self.score_threshold`, but **NEVER used in the execution path**. Effective threshold comes from `DynamicThreshold.compute()` → percentile(scores, 85) clamped [0.45, 0.65]. Config value 0.45 only serves as the lower clamp bound for DynamicThreshold. |
| **Class** | H-Shadow |
| **Confidence** | HIGH (source-confirmed) |
| **Action** | Document as clamp minimum, not threshold. Change name to `score_threshold_clamp_min` or similar. |
| **Risk** | Medium — a trader lowering score_threshold expects easier approval but gets no change |

---

### #9 — `fusion_engine.weight_crt / weight_gaussian / weight_zone_gate / weight_rr` (base weights)

| Field | Value |
|-------|-------|
| **Config location** | `v2_multi_2026_04.json:105-108` |
| **Values** | crt=0.4, gaussian=0.2, zone_gate=0.2, rr=0.2 |
| **Reality** | `FusionConfig` constructor in `engine_runner.py:374-390` reads flat weights. BUT `regime_fusion_weights` block exists in config (`:119-148`) specifying per-regime matrices (e.g. TRENDING: 0.38/0.20/0.12/0.20). If FusionEngine does NOT switch to regime-adaptive weights, the per-regime weights are decorative. |
| **Class** | H-Shadow |
| **Confidence** | 70% — regime_fusion_weights block is in config but CONFIG_REFERENCE.md doesn't document it and FusionConfig doesn't read it |
| **Action** | Either wire regime_fusion_weights into FusionEngine.compute() with a feature flag, or remove the unreachable block |
| **Risk** | High — regime-adaptive weighting is a documented design intent; fusion behavior may be regime-blind |

---

### #10 — `ultron_gate_enabled: false`

| Field | Value |
|-------|-------|
| **Config location** | `engine_runner.ultron_gate_enabled: false` (line 44) |
| **Drivers** | `engine_runner.py:421` reads config. `engine_runner.py:853` checks flag. |
| **Reality** | At `false`, EngineRunner uses legacy regime governor function with no daily quota, no percentile filter, no trade cap. This path is **backtest-only**. Live path at `true` has RegimeGovernor with trade caps and filters. **Backtest at false produces inflated trade counts and win rates that do NOT reflect live behavior at true.** |
| **Class** | H-Split (backtest vs live divergence) |
| **Confidence** | HIGH (source-confirmed) |
| **Action** | Enable in production config (`true`) and re-run backtests to get representative results |
| **Risk** | HIGH — every backtest run with current config produces non-representative results |

---

### #11 — `PROMOTION_MARGIN = 2%` (not a config key)

| Field | Value |
|-------|-------|
| **Config location** | NONE — no config key exists |
| **Reality** | `model_registry.py` hardcodes 2% margin gate before model promotion. There is no config key to tune this. |
| **Class** | H-Shadow (hardcoded constant replaces config) |
| **Confidence** | HIGH |
| **Action** | Add `governance.promotion_margin_pct` key to config. Remove magic number from code. |
| **Risk** | Low — 2% is reasonable, but unconfigurable. |

---

### #12 — `execution_planner` missing keys (documentation error)

| Field | Value |
|-------|-------|
| **Config location** | Not in config — documented in CONFIG_REFERENCE.md §4 |
| **Keys** | `min_rr_ratio`, `default_sl_atr_mult`, `liquidity_*` |
| **Reality** | CONFIG_REFERENCE.md documents these as ExecutionPlanner keys. Source read of `execution_planner.py:79-96, 240-241` confirms: **planner does NOT read these keys**. SL/TP/RR is delegated to `gate_intelligence.compute_crt_levels()`. |
| **Class** | H-Doc (documentation error — code follows config, docs are wrong) |
| **Confidence** | HIGH (source-confirmed) |
| **Action** | Update CONFIG_REFERENCE.md to reflect actual planner API. Add keys under gate_intelligence if they belong there. |
| **Risk** | Low — documentation only |

---

## Orphaned Modules

### UltronRiskGateWrapper

| Field | Value |
|-------|-------|
| **Location** | `src/core/ultron_risk_gate_wrapper.py` |
| **Role** | Pre-scales `risk_percent` by regime before delegating to `UltronRiskGate` |
| **Status** | NOT wired in any production path |
| **Class** | D-Orphan |
| **Action** | Wire into live_engine_hook.py or remove |
| **Risk** | Low — dormant, but regime-based pre-scaling is useful |

---

## Summary

| # | Key | Class | Confidence | Action |
|---|-----|-------|------------|--------|
| 1 | `capital_management.*` | H-Dead | HIGH | Wire or delete |
| 2 | `data_ingestion.*` | H-Dead | HIGH | Delete |
| 3 | `gate_intelligence.*` (keys only) | H-Dead | HIGH | Wire or delete keys |
| 4 | `sl_tp_comparison.*` | H-Dead | 100% | Move to analytics config |
| 5 | `signal_belief.*` | H-Dead | MEDIUM | Investigate |
| 6 | `cognitive_layer.*` | H-Dead | MEDIUM | Investigate |
| 7 | `phase5_calibration.min_val_samples` | H-Dead | MEDIUM | Remove or rewire |
| 8 | `decision_engine.score_threshold` | H-Shadow | HIGH | Document as clamp min |
| 9 | `fusion_engine.*` base weights | H-Shadow | 70% | Wire regime weights or remove |
| 10 | `ultron_gate_enabled: false` | H-Split | HIGH | Enable for representative backtests |
| 11 | `PROMOTION_MARGIN` (hardcoded) | H-Shadow | HIGH | Add config key |
| 12 | `execution_planner` docs | H-Doc | HIGH | Update CONFIG_REFERENCE.md |

**8 actionable now** (can be deleted or documented without code changes).
**4 require code changes** to activate.