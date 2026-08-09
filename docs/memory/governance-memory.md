# Governance Memory (navigation)

> **Last generation:** 2026-08-07  
> **Code-first:** `src/governance/**` + `src/config_layer/config_validator.py` + `src/config_layer/production_config.py` on conflict.

## Purpose

Index how research artifacts become (or fail to become) production config/models under audit, and how meta-governance proposes patches under shadow tests.

## Responsibilities

- Validate candidate params via backtest quality gates → `ValidationReport`.  
- Promote only APPROVE’d configs to production registry + `ACTIVE_VERSION` + `promotion_log.jsonl`.  
- Shadow stage/test/promote-if-superior for meta patches.  
- Reflection buffer + BitNet meta-governor loop (`GovernanceOrchestrator`).  
- Model registry promotion (GOV-3 margin), script/hypothesis/framework registries.  
- Portfolio / multi-strategy validation helpers.

## Runtime role

**Governance kitchen** (async). Feeds config and models into runtime; does not sit inside per-candle scoring. Agent pipeline/governance modes trigger these tools.

## Entry points

| Entry | Symbol / path |
|---|---|
| Promotion | `src/governance/promotion_manager.py` · `PromotionManager.promote_*` |
| Validation | `src/config_layer/config_validator.py` · `ConfigValidator.validate` |
| Shadow gate | `src/governance/shadow_promotion_gate.py` |
| Meta loop | `src/governance/orchestrator.py` · `GovernanceOrchestrator.run` |
| Reflection | `src/governance/reflection_buffer_advanced.py` |
| Meta BitNet | `src/governance/bitnet_governance_executor.py` |
| Model registry | `src/core/model_registry.py` |
| Active config load | `src/config_layer/production_config.py` |
| Agent tools | `modes/pipeline_mode.py`, `modes/governance_mode.py` |
| Control-plane | `promotion.manager`, `validation.config_validator`, `governance.orchestrator` |

## Exit points

| Exit | Artifact |
|---|---|
| Production config | `configs/production/{version}.json` |
| Active pointer | `configs/production/ACTIVE_VERSION` |
| Promotion audit | `configs/promotion_log.jsonl` |
| Validation reports | `results/validation/approved|rejected/` |
| Shadow candidates | gate-local candidate files (no silent prod write) |
| Model artifacts | `models/*` via ModelRegistry |
| Governance audit | `logs/governance_audit.jsonl` |

## Important contracts

1. **Only `ValidationReport.decision == "APPROVE"`** may promote (PromotionManager).  
2. **SHA-256** config hash on promoted params; load-time hash verify.  
3. Promoted files merge onto a **full-config base** (sentinel `engine_runner`) — sparse tuner params alone are not ACTIVE.  
4. **Authority Ladder:** evidence ≠ production authority; measured G001 improvement required for new authority.  
5. Construction protocol + GREEN_FLOOR apply to governed changes (`docs/governance/REPOSITORY_CONSTRUCTION_PROTOCOL.md`).  
6. `config_integrity` may exist but be orphaned at runtime (F-006) — do not assume it gates live.

## Reading order

1. This file.  
2. `src/config_layer/production_config.py` (Tier-0).  
3. `config_validator.py` → `promotion_manager.py`.  
4. If meta: `orchestrator.py` → reflection → shadow gate.  
5. Deep: `docs/reference/governance.md`.  
6. Topic: `docs/topics/promotion-governance.md`.

## Related documents

| Doc | Role |
|---|---|
| [`../reference/governance.md`](../reference/governance.md) | Full promotion workflow |
| [`../topics/promotion-governance.md`](../topics/promotion-governance.md) | Topic |
| [`../topics/config-validation.md`](../topics/config-validation.md) | Validator topic |
| [`../governance/REPOSITORY_CONSTRUCTION_PROTOCOL.md`](../governance/REPOSITORY_CONSTRUCTION_PROTOCOL.md) | Change lifecycle |
| [`agent-memory.md`](agent-memory.md) | Agent triggers |
| [`runtime-memory.md`](runtime-memory.md) | Validation backtests |
| [`architecture-memory.md`](architecture-memory.md) | Layer placement |

## Known coverage

| Scope | Status |
|---|---|
| `src/governance/` (~17 files) | High name visibility in deep map |
| Full script registry (SITS) | Separate registry docs/tests — not duplicated |
| Research programs | Findings + measurement contract — not this memory |
| Functionality Excel | src governance rows in `src_business_functionality.xlsx` |

## Last generation timestamp

2026-08-07
