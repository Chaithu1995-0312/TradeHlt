# Current State — Rolling Status

> **Append-only snapshot log.**
> Each entry records the state of the system at a point in time.
> When anything changes (production config, active model, blocking issues, active tracks),
> append a new entry. Do not overwrite old entries.
>
> Format: ISO 8601 date, followed by key-value facts.

---

## 2026-06-10

### Production Config

| Field | Value |
|-------|-------|
| **Active config** | `v2_multi_2026_04 - deepdeektry.json` |
| **Config version** | v2 (v1 retired) |
| **Config location** | `configs/production/v2_multi_2026_04 - deepdeektry.json` |
| **Hash** | Last re-hash during Phase 4b (2026-05-28) |
| **Sparse patch** | Retroactively patched 2026-04-29 with full engine sections |

### Active ML Model

| Field | Value |
|-------|-------|
| **Model name** | `v4_mirrored` |
| **Correlation** | +0.2066 |
| **CV stability** | std=0.0072 |
| **Training samples** | 242,000 (both directions, mirrored) |
| **Type** | GaussianScorer (direction-aware) |
| **Direction threading** | Complete end-to-end (scanner → training → inference → live) |
| **Default path** | HeuristicGaussianEngine (direction-agnostic — still default) |

### CRT State Machine

| Field | Value |
|-------|-------|
| **States** | 9 (RANGE, SWEEP, DISPLACEMENT, SHADOW_PENDING, EXPANSION, RETEST, EXECUTION, RESOLVED, CANCELLED) |
| **Shadow protection** | Active (TTL=4 candles, λ=0.35 threshold) |
| **Shadow mode** | `shadow_advisory_only = true` |
| **Telemetry** | 5 event types, passive sidecar |

### Test Suite

| Field | Value |
|-------|-------|
| **Total passing** | ~1000 |
| **Known pre-existing failures** | 47 (TP3, frequency_boost, LLM, promotion areas) |
| **These failures are** | Pre-existing, not introduced by any tracked change |
| **Test domains** | engines, config_layer, core, governance, agent, expansion, external I/O, research |
| **Sprint 7 passing** | 1001 |

### Strategies

| Field | Value |
|-------|-------|
| **Total strategies** | 10 (S1-S10) |
| **Orchestrator** | StrategyOrchestrator (completeness gate=2, consensus gate=0.60) |
| **Consensus mode** | `weight_strategy_consensus=0.0` — fuse_strategy_results is dormant |
| **Live gate uses** | `_decide() → tier_*` in fusion_engine.py:670 |

### Live Trading Infrastructure

| Field | Value |
|-------|-------|
| **Live integration** | NOT CONFIGURED — `live_integration` section missing from config |
| **Telegram bridge** | Exists, fails on from_prod_config() |
| **MT5 bridge** | Exists, fails on from_prod_config() |
| **KillSwitch** | Implemented, JSON-persisted |
| **HealthChecker** | HTTP on port 8788, daemon thread |
| **Go-live blockers** | 3 (see below) |

### Blocking Issues for Go-Live

| # | Issue | Severity | Status |
|---|-------|----------|--------|
| 1 | `live_integration` config section missing (Telegram + MT5 bridges fail) | BLOCKER | Actionable — add section + re-hash |
| 2 | `ultron_gate_enabled: false` inflates backtest results | HIGH | Requires regression after enabling |
| 3 | Direction blindness in default Gaussian path | MEDIUM | ML path exists but not default |

### Active Tracks

| Track | Status | Next Step |
|-------|--------|-----------|
| CRT Pipeline Improvement | Phase 0-4b complete. Phase 5a/5b/5c deferred. | Phase 5a threshold sweep |
| Edge Discovery Program | M0-M3 complete. M4 planned. | M4 QualificationGate |
| Architecture Migration | M0 complete. M1-M5 not started. | M1 envelope trade writers |

### Config Illusions

| Field | Value |
|-------|-------|
| **Known illusions** | 12 (see `docs/operations/KNOWN_ILLUSIONS.md`) |
| **Actionable now** | 8 (can be deleted or documented without code changes) |
| **Require code changes** | 4 (score_threshold, regime_fusion_weights, ultron_gate_enabled, PROMOTION_MARGIN) |

### Governance

| Field | Value |
|-------|-------|
| **Promotion mechanism** | ConfigValidator → PromotionManager → SHA-256 + promotion_log.jsonl |
| **Rollback** | 6-step procedure documented |
| **OOS validation** | session_sweep with --train-split 0.7, G1 threshold |
| **Last OOS verdict** | KEEP_INCUMBENT (2026-06-10) |

### Known Risks

| Risk | Description | Mitigation |
|------|-------------|------------|
| **Backtest→live divergence** | `ultron_gate_enabled: false` makes backtests non-representative | Enable in config and re-run |
| **Config drift** | SCHEMAS.md known to be wrong; CONFIG_REFERENCE.md generated from v1 | Source-confirm before acting |
| **Direction blindness** | Default Gaussian path is direction-agnostic | Switch to MLGaussianEngine default |
| **INOUT archive** | Archived but not verified inactive via alternative path | Verify deployment paths |
| **Orphaned module** | UltronRiskGateWrapper exists but not wired | Wire or delete |

---

## Previous States

(No previous entries — this is the first entry.)

---

*Entry created: 2026-06-10 01:08 UTC+5:30*