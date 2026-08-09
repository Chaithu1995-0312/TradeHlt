# G001 Consumer Attribution

> Generated: `2026-07-26T08:51:59Z` Â· schema v1
>
> Goal: **G001** Â· see [`goal.md`](../architecture/goal.md)
>
> **This ledger separates semantic correctness from economic contribution.**
> Passing FM parity / resolve_fm / oracle tests does **not** move G001 and does
> **not** grant production authority (CLAUDE.md Â§6.5 Authority Ladder).

## Authority ladder

- **Level 0** â€” `INFORMATION_ONLY`
- **Level 1** â€” `ECONOMIC_USEFULNESS_MEASURED`
- **Level 2** â€” `AUTHORITY_EARNED`
- **Level 3** â€” `ARCHITECTURE_JUSTIFIED`

## Summary

- Consumers: **10**
- Semantic VALIDATED: **4**
- Ladder > 0: **0**
- Economic MEASURED_POSITIVE Î”G001: **0**

## Consumers

| Consumer | Semantic | Economic | Ladder | Prod influence | New auth from parity |
|---|---|---|---|---|---|
| `crt_spine_state_machine` | VALIDATED | MEASURED_NO_STANDALONE_EDGE | 0 | True | False |
| `scoring_engine_crt_composite` | VALIDATED | NOT_ISOLATED | 0 | True | False |
| `engine_runner_fusion` | PARTIAL | MEASURED_NON_PIVOTAL_OR_INERT_CHANNELS | 0 | True | False |
| `zone_gate` | AUDITED | MEASURED_NO_MARGINAL_VALUE | 0 | True | False |
| `bitnet_gate` | AUDITED_CONDITIONAL_SKEW | MEASURED_NO_IMPROVEMENT | 0 | False | False |
| `rr_fusion` | AUDITED_GATE_MISSPEC | DISABLED_NO_AUTHORITY | 0 | False | False |
| `session_filter` | VALIDATED | MEASURED_NOT_PROMOTABLE_BNB | 0 | True | False |
| `ultron_risk_gate` | CONTRACT_DEFINED | LIVE_UNVERIFIED_HEADLINE | 0 | True | False |
| `feature_state_encoder_shadow` | VALIDATED_MAPPING | NOT_ON_TRADING_PATH | 0 | False | False |
| `liquidity_sweep_veto` | VALIDATED | MEASURED_INSUFFICIENT | 0 | False | False |

### Detail

#### `crt_spine_state_machine`

- **Path:** `src/config_layer/crt_engine_v2.py`
- **Description:** CRT state machine â†’ TRADE_OPENED path (primary research spine)
- **Signals:** FM-002, FM-010, FM-027, FM-028, structural states via pipeline
- **Semantic evidence:** tests/test_fm_resolution_phase2.py, tests/test_fc1a_swing_oracle_parity.py, docs/governance/crt_closure_report.md
- **Economic evidence:** F-019, F-021, F-025, F-026, F-027, docs/current-findings.md
- **Notes:** Multiple M4-style studies under realistic exits: entry-information null on crypto majors; spine throughput-starved; not a G001-clearing edge.
- **Scope:** `incumbent_crt_path_only`

#### `scoring_engine_crt_composite`

- **Path:** `src/engines/scoring_engine.py`
- **Description:** CRT composite score (sweep/breakout/retest/time); FM-029 rescale
- **Signals:** FM-029, body_ratio, retest_depth, sweep flags
- **Semantic evidence:** tests/test_gd004_gd005_identity_closure.py, tests/test_fm_resolution_phase3.py
- **Economic evidence:** F-021
- **Notes:** Score/zone selection skill not demonstrated under intrabar+12bps (F-021). No isolated Î”G001 study for FM-029 alone.
- **Scope:** `incumbent_scoring_only`

#### `engine_runner_fusion`

- **Path:** `src/core/engine_runner.py`
- **Description:** Four-engine fusion gate (CRT/Gaussian/Zone/RR)
- **Signals:** engine scores, zone_gate, rr, gaussian
- **Semantic evidence:** F-037, F-038, F-060, docs/governance/gaussian_lineage_audit.md, docs/governance/rr_lineage_audit.md
- **Economic evidence:** F-036, F-037, F-060, F-038
- **Notes:** Zone non-pivotal (F-036); Gaussian near-constant inert (F-060); rr_fusion disabled (F-038). Gate-ON modest N change only (F-037).
- **Scope:** `incumbent_fusion_when_enabled`

#### `zone_gate`

- **Path:** `src/engines/zone_gate_engine.py`
- **Description:** Geometric HARD zone gate
- **Signals:** zone registry geometry, feature vectors for membership
- **Semantic evidence:** docs/governance/zonegate_lineage_audit.md, F-041
- **Economic evidence:** F-036, F-041B
- **Notes:** Non-pivotal; honest labels show no zone with E>0.
- **Scope:** `incumbent_hard_gate_geometry`

#### `bitnet_gate`

- **Path:** `src/bitnet/bitnet_inference.py`
- **Description:** BitNet hard-reject gate when use_bitnet enabled
- **Signals:** 38/39-dim canonical vector
- **Semantic evidence:** docs/governance/bitnet_lineage_audit.md, F-004, F-050, F-055
- **Economic evidence:** F-055
- **Notes:** Shadow A/B: gate-ON does not improve CRT spine; use_bitnet stays false on active.
- **Scope:** `inert_on_active_config`

#### `rr_fusion`

- **Path:** `src/config_layer/rr/rr_fusion.py`
- **Description:** RR fusion confidence gate over RR engine
- **Signals:** rr_model, gaussian fallback historically
- **Semantic evidence:** F-038, F-044, F-045, F-059
- **Economic evidence:** F-038, F-059
- **Notes:** rr_fusion enabled:false on active; clean-label KEEP_CANDIDATE research-only.
- **Scope:** `disabled`

#### `session_filter`

- **Path:** `src/features/session_classifier.py + engine allowed_sessions`
- **Description:** Session FEATURE (FM-052) vs session FILTER policy (distinct)
- **Signals:** FM-051, FM-052
- **Semantic evidence:** tests/test_feature_temporal_context.py, tests/test_session_classifier.py
- **Economic evidence:** F-017, F-021
- **Notes:** Session policy not a promotable BNB lever under realistic exits + OOS.
- **Scope:** `filter_policy_config`

#### `ultron_risk_gate`

- **Path:** `src/core/ultron_risk_gate.py`
- **Description:** Final risk / min_rr economic gate (owns RR economics post F-048)
- **Signals:** execution plan RR, risk params
- **Semantic evidence:** F-048, tests/test_ultron_risk_gate.py
- **Economic evidence:** F-010
- **Notes:** Headline ROI backtest-only; live PnL through ExecutionPlanner+Ultron UNVERIFIED (F-010).
- **Scope:** `incumbent_risk_gate`

#### `feature_state_encoder_shadow`

- **Path:** `src/features/feature_states.py + crt_state_resolver`
- **Description:** Shadow state naming / CRTStateResolver research path
- **Signals:** states blocks for vector-bound FMs
- **Semantic evidence:** tests/test_feature_states.py
- **Economic evidence:** â€”
- **Notes:** Research/shadow only; cannot earn G001 by definition until wired.
- **Scope:** `shadow_only`

#### `liquidity_sweep_veto`

- **Path:** `research/H-G001-001 + research/H-G001-001b (post-entry filter on spine)`
- **Description:** H-G001-001/H-G001-001b: veto production CRT spine entries when FM-058 liquidity_sweep != 0 on entry bar (XAUUSD M15, M4 intrabar+12bps; fusion gate ON and CRT-only lenses measured separately)
- **Signals:** FM-058
- **Semantic evidence:** tests/test_fc1a_swing_oracle_parity.py, tests/test_feature_structural_states_complex.py
- **Economic evidence:** research/H-G001-001/promotion_decision.md, research/H-G001-001/baseline_results.json, research/H-G001-001/treatment_results.json, research/H-G001-001b/promotion_decision.md, research/H-G001-001b/baseline_results.json, research/H-G001-001b/treatment_results.json, F-029, F-035
- **Notes:** 2026-07-26 H-G001-001: production spine on frozen XAUUSD candidate yielded n=1 entry (fusion gate ON); treatment identical (0 vetoes on that entry). REJECT_INSUFFICIENT; no delta_G001 claim. 2026-07-26 H-G001-001b: CRT-only lens also yielded n=1; treatment identical (0 vetoes). REJECT_INSUFFICIENT. Reopen only with a powered entry set (n>=30) or alternate instrument/corpus under a new H-id.
- **Scope:** `research_only_rejected_insufficient`

## How to update

1. Run a pre-registered consumer A/B (shadow) with `goal_report` / Î”G001 metrics.
2. Edit `_CONSUMERS` in `scripts/governance/build_g001_consumer_attribution.py`.
3. Set `economic_status` / evidence / ladder only from measured results.
4. Regenerate: `python scripts/governance/build_g001_consumer_attribution.py`
5. Never set `new_authority_from_parity=true`.

## Related

- Feature ownership: [`fm_ownership_consumer_matrix.md`](fm_ownership_consumer_matrix.md)
- Goal layer topic: [`docs/topics/goal-layer.md`](../topics/goal-layer.md)
