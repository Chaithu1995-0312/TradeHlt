# Algorithm Design: Reasoning System from Codebase Patterns

**Date:** 2026-10-06  
**Branch:** semanticos_impl  
**Scope:** Compose an algorithm from existing codebase reasoning primitives to process userinvestigation/ JSONL data  

---

## Context

The codebase contains **six mature reasoning components** (CRT Engine, Decision Engine, Fusion Engine, State Resolver, Scoring Engine, Model Adapters) that form a layered decision-making architecture. The userinvestigation/ folder contains JSONL audit trails of that decision-making:

- **Entry data** (h4_c1c2c3_entry_xauusd.jsonl, second_low_algo/backtest_M15.jsonl)
- **Level monitors** (second_low_monitor.jsonl, pnl_sign_trace_20260803.jsonl)
- **Investigation flows** (flow_20261004.jsonl)

**Goal:** Design an algorithm that:
1. **Reuses** existing codebase reasoning patterns (no new engines)
2. **Processes** userinvestigation JSONL as input
3. **Validates** algorithm inputs against canonical 48-dim schema
4. **Produces** interpretable reasoning chains (state→decision→trade trace)

---

## Algorithm Design: "Reasoning Chain Reconstructor" (RCR)

### Input Specification

**Source 1: Trade Entry JSONL**
```
Fields required: arm, direction, entry_ts, entry, stop, tp1, tp2, 
                 risk, crt_state, net_r, exit_kind, mfe_r, mae_r
Schema: 48-dim canonical (from canonical_features.py / feature_schema.py v5.0)
Validation: SCHEMA_HASH match; XAUUSD M15 corpus
```

**Source 2: Monitor/Level JSONL**
```
Fields required: timestamp, second_low_Xd, fvg_edge, pdl_price, pdh_price, 
                 crt_state, volatility_regime, hour_of_day
Schema: Real-time level snapshot (48-dim subset)
Validation: Chronological ordering; 0 < pdh_price < price < fvg_edge (semantics check)
```

**Source 3: PnL/Sign Trace JSONL**
```
Fields required: entry_ts, sign (±1), close_price, close_ts, 
                 bars_held, mfe_before_exit, mae_before_exit
Schema: Intrabar fill trace (derived from forward_walk kernel)
Validation: Sign matches direction; timestamp alignment with entry/exit
```

### Algorithm: Three-Stage Pipeline

#### **Stage 1: Input Validation & Schema Alignment**
- **Entrypoint:** `validate_reasoning_inputs(trade_jsonl, monitor_jsonl, pnl_trace_jsonl)`
- **Checks:**
  1. **Schema completeness:** every trade has all 48-dim canonical keys (XAUUSD M15 schema v5.0)
  2. **Semantic consistency:** 
     - `stop < entry < tp1 < tp2` (for LONG) or `stop > entry > tp1 > tp2` (for SHORT)
     - `crt_state ∈ VALID_TRANSITIONS` (9-state graph from state_identity.py)
     - `hour_of_day ∈ [0, 23]` and `volatility_regime ∈ ['CALM', 'ELEVATED', 'SPIKE']`
  3. **Temporal alignment:**
     - entry_ts matches monitor snapshot (within ±1 bar window)
     - pnl_trace entries are chronologically ordered post-entry
  4. **Outcome coherence:**
     - If `exit_kind == TP_HIT`, then `close ≤ tp2` (within fill tolerance)
     - If `exit_kind == SL_HIT`, then `close ≥ stop` (adverse fill accounted)
     - If `exit_kind == TIMEOUT`, then `bars_held ≥ ttl_bars` (configured in trade object)
- **Output:** `ValidationReport(passed: bool, errors: List[str], warnings: List[str], canonical_vector: ndarray[48])`
- **Authority:** Fail-closed (any unresolved inconsistency blocks reconstruction)

---

#### **Stage 2: Reasoning Chain Reconstruction**
Compose three codebase engines into a **replay trace:**

**2a. CRT State Resolver** (read-only classification)
- Input: 48-dim canonical vector from entry timestamp
- Pattern: `feature_encoder → predicate evaluator → state name` (cf. crt_state_resolver.py)
- Output: `resolved_crt_state: str` (compare against `crt_state` from JSONL to audit state derivation)
- **Key check:** Does the JSONL `crt_state` match what the resolver produces from features?

**2b. Scoring Engine Replay** (weighted components)
```
s_sweep       = 1.0 if double_sweep else 0.7 if sweep_detected else 0.0
s_breakout    = 0.5*min(body_ratio,1) + 0.5*min(disp_strength/2, 1)
s_retest      = exp(−((retest_depth−0.5)²)/0.04)
s_time        = exp(−λ_decay * max(0, candles_since_sweep))
s_raw         = w_sweep*s_sweep + w_breakout*s_breakout + w_retest*s_retest + w_time*s_time
```
- Input: 48-dim vector + candles_since_sweep counter (from monitor snapshot)
- Weights: (0.35, 0.25, 0.20, 0.20) default (from configs/production/)
- Output: `ScoreDecomposition(s_sweep, s_breakout, s_retest, s_time, s_raw)`
- **Key check:** Does the raw score exceed the entry decision threshold (default 0.55)?

**2c. Decision Engine Gate** (semantic classifier)
```
decision = evaluate(
    fused_score = s_raw,
    p_win = gaussian_score,          // from Gaussian engine (live/research)
    zone_validity = zone_gate_pass,  // from zone_registry (hard gate)
    weak_component = 1 - fusion_final
)
```
- Input: s_raw from 2b + zone validity + Gaussian confidence
- Logic: if s_raw >= threshold → ACCEPT; elif in LLM zone → consult fallback; else → REJECT
- Output: `DecisionResult(verdict: ACCEPT|REJECT, stage: str, reason: str, confidence: float)`
- **Key check:** Decision gate matches the `crt_state == EXECUTION` outcome in JSONL?

---

#### **Stage 3: Outcome Attribution & Causality Trace**
Link the reasoning chain to the actual trade outcome:

**3a. Entry→Exit Path Attribution**
```
entry_trace = {
  resolved_state: str,           // from 2a
  score_components: {...},       // from 2b
  decision_gate: {...},          // from 2c
  decision_ts: timestamp,        // when decision was made (usually bar CLOSE)
  approved_by: str               // which engine (CRT | DecisionEngine)
}

exit_trace = {
  exit_ts: timestamp,
  exit_price: float,
  bars_held: int,
  mfe_r: float,                  // from walk kernel
  mae_r: float,
  exit_kind: str,                // TP_HIT | SL_HIT | STOPPED | TIMEOUT
  reached_tp1: bool,
  pnl_sign: ±1                   // from pnl_trace
}

causality_link = {
  decision_matches_outcome: bool,  // Did ACCEPT lead to EXECUTE? Did REJECT prevent it?
  state_stability: float,          // % bars crt_state unchanged from entry→exit
  score_degradation: float,        // s_final(exit) / s_final(entry)
  exit_within_plan: bool           // exit_price ∈ [stop, tp2]?
}
```

**3b. Anomaly Detection** (four checks)
1. **State jump:** If `crt_state` changes to invalid transition → flag as "structural anomaly"
2. **Score collapse:** If s_raw drops >50% mid-hold → flag "signal decay"
3. **Outcome mismatch:** If decision=ACCEPT but exit=STOPPED → flag "execution risk"
4. **Fill quality:** If exit outside [stop, tp2] (beyond normal slip) → flag "adverse fill"

**3c. Output: Reasoning Ledger JSONL**
```json
{
  "trade_id": "CRT-0001",
  "entry_ts": "2024-05-22T15:45:00",
  "arm": "A",
  "direction": "short",
  "entry": 2412.51,
  "reasoning_chain": {
    "state_resolved": "DISPLACEMENT",
    "score_components": {"s_sweep": 1.0, "s_breakout": 0.65, "s_retest": 0.88, "s_time": 0.92},
    "s_raw": 0.72,
    "decision": "ACCEPT",
    "decision_reason": "score >= threshold and zone valid",
    "decision_confidence": 0.82
  },
  "outcome": {
    "exit_ts": "2024-05-22T21:15:00",
    "exit_price": 2399.44,
    "exit_kind": "TP_HIT",
    "net_r": 0.227,
    "pnl_sign": 1
  },
  "causality": {
    "decision_matches_outcome": true,
    "state_stability": 0.94,
    "score_degradation": 0.18,
    "exit_within_plan": true
  },
  "anomalies": []
}
```

---

## Input Requirements Checklist

| Requirement | Source | Validation | Authority |
|---|---|---|---|
| **48-dim canonical vector** | entry JSONL | SCHEMA_HASH match v5.0 | FeaturePipeline / canonical_features.py |
| **CRT state name** | entry JSONL | ∈ VALID_TRANSITIONS (9 state graph) | state_identity.py:69 |
| **Candle geometry** (body_ratio, disp_strength, candles_since_sweep) | entry JSONL | 0 ≤ body_ratio ≤ 1; 0 < disp_strength; candles ≥ 0 | candle_math.py + feature_pipeline.py |
| **Entry/SL/TP1/TP2** | entry JSONL | LONG: stop < entry < tp1 < tp2; SHORT: reversed | execution_planner.py |
| **Exit outcome** (exit_kind, net_r, mfe_r, mae_r) | entry JSONL | exit_kind ∈ {TP_HIT, SL_HIT, STOPPED, TIMEOUT} | forward_walk.py / multi_tp_walk.py |
| **Level monitor snapshot** | monitor JSONL | Chronological; pdl < entry < pdh; fvg_edge consistent | second_low_monitor.jsonl schema |
| **PnL sign trace** | pnl_trace JSONL | Sign ∈ {-1, +1}; timestamp ≥ entry_ts | pnl_sign_trace.py |
| **Zone validity** | zone_registry.json | Zone ID ∈ stored registry; cluster_id ≤ max_clusters | models/zone_registry.json |
| **Gaussian score** (optional for full fusion) | gaussian_ml artifact | 0 ≤ score ≤ 1 (or ABSENT for CRT-only) | models/gaussian_model.pkl |
| **Config hash** | active_models.yaml | `config_sha256` = current | configs/production/ACTIVE_VERSION |

---

## Implementation Roadmap

### Phase 1: Validation Layer
1. Write `src/analysis/reasoning_chain_validator.py`
   - `validate_schema(trade_jsonl_rows)` → ValidationReport
   - `validate_semantics(trade, monitor_snapshot)` → SemanticCheck
   - `validate_temporal_alignment(entry_ts, monitor_ts, pnl_ts)` → TemporalCheck

2. Add floor: `tests/test_reasoning_chain_validator.py`
   - Positive: valid XAUUSD M15 entries (from committed backtest results)
   - Negative: malformed vectors, invalid states, semantic contradictions

### Phase 2: Reconstruction Engine
3. Write `src/analysis/reasoning_chain_reconstructor.py`
   - `Stage1`: validate_inputs (Phase 1 delegate)
   - `Stage2a`: replay_crt_state_resolver (import CRTStateResolver, forward)
   - `Stage2b`: replay_scoring_engine (import ScoringEngine weights, compute)
   - `Stage2c`: replay_decision_engine (import DecisionEngine, evaluate)
   - `Stage3`: attribute_outcome (build causality_link + anomaly_flags)

4. Add floor: `tests/test_reasoning_chain_reconstructor.py`
   - Replay 10 known-good trades from h4_c1c2c3_entry_xauusd.jsonl
   - Verify s_raw matches decision_engine confidence
   - Verify anomaly detection catches inserted signal breaks

### Phase 3: Output Ledger & Analysis
5. Write `src/analysis/reasoning_ledger_writer.py`
   - Consume reconstructor output → JSONL line per trade
   - Path: `results/reasoning_ledger_{run_id}.jsonl`
   - Include provenance (config_sha256, timestamp, version)

6. Write `scripts/analysis/reasoning_audit.py` (CLI entry point)
   ```bash
   python scripts/analysis/reasoning_audit.py \
     --trades userinvestigation/h4_c1c2c3_entry_xauusd.jsonl \
     --monitor userinvestigation/second_low_monitor.jsonl \
     --pnl-trace userinvestigation/pnl_sign_trace_20260803.jsonl \
     --output results/reasoning_ledger.jsonl
   ```

---

## Verification Plan

1. **Schema alignment:** Run validator on all 3 JSONL sources. Report % passing + rejection reasons.
2. **Reasoning fidelity:** Pick 5 trades. Manually trace decision→outcome. Verify reconstructor chain matches CRT engine state at entry bar.
3. **Causality signal:** For ACCEPTED trades, check exit_within_plan rate (target: >90%). For REJECTED trades in backtest, confirm they weren't executed.
4. **Anomaly detection:** Inject 3 artificial signal breaks (e.g., s_raw drop 80%→20% mid-hold). Verify detector catches all 3.

---

## Open Questions for User Clarification

1. **Scope of "algorithm":** Do you want the RCR to run as a **live audit** (realtime side-by-side trace) or **offline analysis** (replayed on historical JSONL)?
2. **Authority ladder:** Should RCR output carry authority to **gate decisions** (strict mode) or just **explain decisions** (advisory mode)?
3. **Multi-instrument:** Should Phase 1 focus on **XAUUSD M15 only** or generalize to crypto majors?
4. **Fusion depth:** Include Gaussian + LLM layers (full Fusion Engine) or **CRT-only** spine (Stage 2a/2b/2c without fusion)?

