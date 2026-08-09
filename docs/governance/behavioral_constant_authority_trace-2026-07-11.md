# Behavioral Constant Authority Trace — Closure Pass (2026-07-11)

| Field | Value |
|---|---|
| Schema | `behavioral_constant_authority_trace.v2_closure` |
| Pass | `ACTIVE_CRT_BEHAVIORAL_CONSTANT_CLOSURE_PASS` |
| Status | **COMPLETE** |
| ACTIVE_VERSION | `v2_multi_2026_04` |
| Spine modules | 16 |
| Machine ledger | [`behavioral_constant_authority_trace-2026-07-11.json`](behavioral_constant_authority_trace-2026-07-11.json) |

## Closure gates

- CLOSURE_SCOPE_RESOLVED = **True**
- EVERY_IN_SCOPE_ADJUDICATED = **True**
- PLANS_RECERTIFIED_OR_REVISED = **True**
- UNPROVEN_SCOPE_COUNT = **0**

## Population

- RAW = 1172
- IN_SCOPE = 520
- OUT_OF_SCOPE = 652
- DEEP_TRACED anchors = 13
- FULLY_ADJUDICATED = 520
- SUR008_ANCHORS_FOUND = True

## Spine modules

- `src/config_layer/crt_engine_v2.py`
- `src/engines/crt_engine.py`
- `src/engines/scoring_engine.py`
- `src/config_layer/crt_sweep_taxonomy.py`
- `src/core/engine_runner.py`
- `src/core/fusion_engine.py`
- `src/core/decision_engine.py`
- `src/config_layer/execution_planner.py`
- `src/core/ultron_risk_gate.py`
- `src/core/ultron_risk_gate_wrapper.py`
- `src/config_layer/production_config.py`
- `src/config_layer/config_builder.py`
- `src/config_layer/market_router.py`
- `src/features/candle_math.py`
- `src/features/derived_math.py`
- `src/runtime/live_engine_hook.py`

## Plan re-certification

| Plan | Status | Notes |
|---|---|---|
| PLAN-001 | **IMPLEMENTED** | Closure confirmed min_depth as sole P1 floor hardcode; IMPLEMENTED 2026-07-11 (CH-plan001-retest-min... |
| PLAN-002 | **IMPLEMENTED** | REVISED (dual-path design) then IMPLEMENTED 2026-07-12 as TWO DISTINCT HOW keys (user-approved ident... |
| PLAN-003 | **REVISED** | REVISED scope: batch remaining PROVEN_HOW_CANDIDATE spine residuals (support_count=509) including Ul... |

## Adjudication summary

- PROVEN_HOW_CANDIDATE = 503
- PROVEN_WHAT_FORMULA_COMPONENT = 0
- PROVEN_CODE_INVARIANT = 0
- PROVEN_DUPLICATE_RUNTIME_AUTHORITY = 17
- PROVEN_MISSING_CODE_IMPLEMENTATION = 0
- UNPROVEN = 0

## Top findings

- **FND-CL-001**: Closure resolves spine AST candidates to IN/OUT without residual UNPROVEN on the declared module set (UNPROVEN_SCOPE_COUNT=0).
- **FND-CL-002**: PLAN-001 RECERTIFIED for min_depth→HOW; PLAN-002 REVISED for dual-path weight vector (RiskScore.final + scoring_engine defaults); PLAN-003 REVISED to batch remaining HOW candidates.
- **FND-CL-003**: Weight vector (0.35,0.25,0.20,0.20) has PROVEN_PARTIAL_SEMANTIC_OVERLAP across two CODE runtime paths; conf_weights remains PROVEN_DIFFERENT_SEMANTIC.
- **FND-CL-004**: Every IN_SCOPE candidate (n=520) has authority adjudication; summary={'PROVEN_HOW_CANDIDATE': 503, 'PROVEN_WHAT_FORMULA_COMPONENT': 0, 'PROVEN_CODE_INVARIANT': 0, 'PROVEN_DUPLICATE_RUNTIME_AUTHORITY': 17, 'PROVEN_MISSING_CODE_IMPLEMENTATION': 0, 'UNPROVEN': 0}

## Unresolved gaps

- Deep runtime call-chain proofs limited to anchor set; residual IN_SCOPE use scope-derived DIRECT/CONDITIONAL effect tags (closure policy), not per-site mutation experiments

## Next step

Stop — do not implement PLAN-001..003. Next implementation (if approved) starts with RECERTIFIED PLAN-001 under §6.5 parity, then REVISED PLAN-002 covering both weight-vector CODE sites.
