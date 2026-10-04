# Engine Memory (navigation)

> **Last generation:** 2026-08-07  
> **Code-first:** `src/engines/**` + `src/core/engine_runner.py` + `src/config_layer/crt_engine_v2.py` on conflict.

## Purpose

Index independent scoring engines and their orchestration into fused scores for the decision spine.

## Responsibilities

- Hard adapter pre-gate (`TrapValidatorEngine`).  
- Produce per-engine scores: CRT, Gaussian, Zone Gate, RR (mandatory set).  
- Optional channels: ML Gaussian, LLM engine, TradeNet meta, BitNet zone (often inert when disabled).  
- Orchestrate completeness + fusion handoff via `EngineRunner`.  
- CRT **state machine** lives primarily in `config_layer/crt_engine_v2.py` (not only `engines/crt_engine.py` score wrapper).

## Runtime role

**Inference / scoring** on each bar (or setup evaluation). Upstream of DecisionEngine; downstream of features.

## Entry points

| Entry | Symbol / path |
|---|---|
| Orchestrator | `src/core/engine_runner.py` · `EngineRunner.run`, `EXPECTED_ENGINES` |
| CRT score wrapper | `src/engines/crt_engine.py` |
| CRT state machine | `src/config_layer/crt_engine_v2.py` |
| Gaussian | `src/engines/heuristic_gaussian_engine.py` / `ml_gaussian_engine.py` |
| Zone | `src/engines/zone_gate_engine.py`, `zone_cluster_score.py`, `live_engine.get_zone_gate` |
| RR | `src/engines/rr_engine.py`; optional `config_layer/rr/rr_fusion.py` |
| Trap | `src/engines/trap_validator_engine.py` |
| Fusion | `src/core/fusion_engine.py` |

## Exit points

| Exit | Consumer |
|---|---|
| Score map `{crt, gaussian, zone_gate, rr, …}` | FusionEngine → DecisionEngine |
| REJECT (incomplete/adapter/zone) | Collector / harness (no planner) |
| Telemetry | `logs/engine_telemetry.jsonl`, feature snapshots (fail-open) |
| Model files read | `models/zone_registry.json`, `rr_model*.json`, gaussian registries, etc. |

## Important contracts

1. **`EXPECTED_ENGINES = {crt, gaussian, zone_gate, rr}`** — missing any → hard reject before ACCEPT.  
2. **Fusion weights** from production `fusion_engine` / `engine_runner` — strict config read.  
3. **`rr_fusion.enabled`** often false on active lineage (F-038) — base RREngine path.  
4. **`use_bitnet`** false on active patch → BitNet gate inert (F-004).  
5. **TradeNet** fusion neural slot built but largely unwired (F-005).  
6. Gaussian live channel may be information-inert under default params (F-060) — descriptive, not a license to “fix” without authority.

## Reading order

1. This file.  
2. `src/core/engine_runner.py` (pipeline order + completeness).  
3. Engine modules for the task (one engine at a time).  
4. CRT machine: `crt_engine_v2.py` + `state_identity` / `state_topology`.  
5. Topics: `docs/topics/scoring-engines.md`, `crt-spine.md`, `fusion-decision.md`.  
6. Intent authority: `docs/governance/MODEL_INTENT_AUTHORITY_REGISTER.md`.

## Related documents

| Doc | Role |
|---|---|
| [`../topics/scoring-engines.md`](../topics/scoring-engines.md) | Engines topic |
| [`../topics/crt-spine.md`](../topics/crt-spine.md) | CRT topic |
| [`../topics/fusion-decision.md`](../topics/fusion-decision.md) | Fusion topic |
| [`../architecture/services/decision-spine.md`](../architecture/services/decision-spine.md) | Spine exemplar |
| [`feature-memory.md`](feature-memory.md) | Inputs |
| [`runtime-memory.md`](runtime-memory.md) | Callers |
| `active_models.yaml` | Model registry layers |

## Known coverage

| Scope | Status |
|---|---|
| `src/engines/` (~13 files) | ~100% name visibility in deep map |
| EngineRunner + fusion | Covered in architecture deep map |
| BitNet package | Separate tree `src/bitnet/` — package-level unless task is BitNet |
| Per-finding economic claims | `docs/current-findings.md` — not repeated here |

## Last generation timestamp

2026-08-07
