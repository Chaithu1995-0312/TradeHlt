# Research Lane (Multi-LLM HOW) — Initiated

> **Lane R** of the dual-lane architecture.  
> **Lane I** (implementation) stays at [`../MULTI_LLM_PROTOCOL.md`](../MULTI_LLM_PROTOCOL.md).  
> **HOW design:** [`docs/research-readiness/edge-research-platform-mllm-how.md`](../../docs/research-readiness/edge-research-platform-mllm-how.md)

## Why this exists

Stop multi-LLM **echo chamber**. Every research output is one of:

| kind | meaning |
|---|---|
| `PROPOSAL` | Hypothesis or experiment sketch |
| `CRITIQUE` | Attack on design / evidence |
| `EXECUTION_EVIDENCE` | Real tool run + paths |
| `DECISION` | Freeze / retire / next grant / PL rung |

**No voting. No free-form truth. No capital without You.**

## Files

| File | Role |
|---|---|
| `package_schema.json` | HOW contract for packages |
| `research_cycle_ledger.jsonl` | Append-only ledger |
| `RESEARCH_ROLES.md` | Role → model map |
| `scorecard.md` | Marginal value metrics |
| `templates/` | Copy-paste package shells |
| `cycles/` | Optional per-cycle notes |

## Quick start — initiate plan per model

```bash
PYTHONPATH=src python scripts/multi_llm/initiate_plan.py --model grok --cycle RC-001
# .\scripts\multi_llm\grok.ps1  | deepseek.ps1 | gemini.ps1 | claude.ps1 | chatgpt.ps1
```

Writes **model-separated** `proposals/<model>/<cycle>/` with `PROPOSAL.md`, `PROMPT_FOR_*.md`, `CONTEXT_BUNDLE.md`  
(curated ERP docs only — see `context_manifest.json`). Full commands: [`INITIATE_PLAN_COMMANDS.md`](INITIATE_PLAN_COMMANDS.md).

## Manual templates (optional)

1. Open a template under `templates/`.  
2. Fill fields; keep `promise_rung_max_claim` ≤ current PL (now **PL-0**).  
3. Append one JSON object line to `research_cycle_ledger.jsonl`.  
4. Claude only executes after a **DECISION** freeze for RUN work.

## Current state

| Item | Value |
|---|---|
| Initiated | **yes** (RC-000) |
| Current promise rung | **PL-0** |
| Next recommended grant | P0 freeze + **Implement P1** |
| Lane I rewrite | **no** |

## Authority

Reality > tests/findings > repo > You (what to do) > LLMs.  
Claude writes code. Packages do not promote configs.
