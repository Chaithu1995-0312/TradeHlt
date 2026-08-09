# Agent Memory (navigation)

> **Last generation:** 2026-08-07  
> **Code-first:** `src/agent/**` is authoritative on conflict.

## Purpose

Index **GrokAgenticAI** — the natural-language multi-specialist kitchen agent: intent
classification, deterministic/bounded tool plans (OpsDoctor, CampaignRunner + legacy modes),
confirm-gated execution, and audit. Entry: `Ask GrokAgenticAI …` / `python -m src.agent.cli`.

## Responsibilities

- Classify operator NL → `{mode, intent_key}` without choosing tools.  
- Compile intent → ordered tools via `PLAN_REGISTRY` (deterministic).  
- Fill missing required args (optional LLM).  
- Dispatch tools under allowlist, path guard, and y/N write confirm.  
- Persist session + append-only audit.

## Runtime role

**Operator control surface** (async kitchen). Triggers pipeline/governance tools or **taps** the decision spine read-only (copilot). Not inside the per-candle hot path.

## Entry points

| Entry | Symbol / path |
|---|---|
| REPL CLI | `src/agent/cli.py` · `main` |
| Turn loop | `src/agent/agent_core.py` · `AgentCore.turn` |
| Intent | `src/agent/intent_router.py` · `IntentRouter.classify` |
| Plan | `src/agent/plan_compiler.py` · `PlanCompiler.build` / `PLAN_REGISTRY` |
| Dispatch | `src/agent/executor.py` · `Executor.dispatch` |
| Tools registry | `src/agent/tool_registry.py` · `REGISTRY` |
| Mode registration | `src/agent/modes/*.py` (import side-effect) |

## Exit points

| Exit | Artifact / effect |
|---|---|
| Tool handlers | Subprocess scripts, validators, spine reads, promotion, findings |
| Audit | `logs/agent_audit.jsonl`, `logs/agent_intent_log.jsonl` |
| Session | `logs/agent_sessions/<session_id>.json` |
| Findings (write) | `logs/agent_findings.jsonl` (confirm-gated) |

## Important contracts

1. **LLM never chooses tools or order** — only intent (and arg fill).  
2. **Write tools** require `confirmed=True` and paths under `configs/production/`, `logs/`, `results/`.  
3. Modes: pipeline (WRITE-capable), copilot (READ-only), governance, findings, log_query.  
4. Config section: production JSON `agent` (soft defaults if absent in CLI only).  
5. Quality gates inside handlers (e.g. ConfigValidator, PromotionManager) are **not** bypassed by the agent.

## Reading order

1. This file.  
2. `src/agent/cli.py` → `agent_core.py` → `plan_compiler.py` → `executor.py`.  
3. Relevant mode: `modes/pipeline_mode.py` | `copilot_mode.py` | `governance_mode.py`.  
4. Deep: `docs/reference/agent-reference.md`.  
5. If spine touch: [`architecture-memory.md`](architecture-memory.md) then code under `src/core/`.

## Related documents

| Doc | Role |
|---|---|
| [`../reference/agent-reference.md`](../reference/agent-reference.md) | Full intents/tools/API |
| [`../topics/ai-automation-agent.md`](../topics/ai-automation-agent.md) | Topic index |
| [`architecture-memory.md`](architecture-memory.md) | System layers |
| [`governance-memory.md`](governance-memory.md) | Promote/validate tools |
| Deep map §2.1–2.2 | `docs/architecture/architecture-memory.md` |

## Known coverage

| Scope | Status |
|---|---|
| `src/agent/` (~19 files) | Name/path visibility ~100% in deep map |
| PLAN_REGISTRY intents | Indexed via agent-reference + plan_compiler |
| Every tool handler body | Not duplicated here — read mode modules |
| Functionality Excel | `results/analysis/src_business_functionality.xlsx` (agent rows) |

## Last generation timestamp

2026-08-07
