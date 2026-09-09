# Topic: AI Automation Agent

> **Topic-visibility unit.** The ChatOps overlay: natural language → classified intent → a
> **deterministic** tool plan → confirm-gated execution. Product brand: **GrokAgenticAI** with
> multiple specialists. Concept narrative; the full tool/intent tables live in
> [`agent-reference.md`](../reference/agent-reference.md). Design:
> [`implementation_plan/agentic-ai-kitchen-design.md`](../implementation_plan/agentic-ai-kitchen-design.md).
>
> Created: 2026-06-05 · Updated: 2026-08-25 · Status: living

## In plain language
**GrokAgenticAI** lets an operator drive the kitchen in plain English ("Ask GrokAgenticAI …").
It **classifies** the request into an intent, then either:

1. **Specialist GoalLoop**: **OpsDoctor** (diagnose → incident pack), **CampaignRunner**
   (tune → validate → optional promote → backtest), **TruthJanitor** (construction/lint/census/
   citations → `results/hygiene/` pack), or
2. **Legacy linear plan** via `PLAN_REGISTRY` (tune/validate/promote/copilot/governance).

The LLM never chooses arbitrary tools (Mode D forbidden). Read tools run freely; **write tools
halt for a `y/N` confirm** and are path-guarded. Advisory automation — never spine execution authority.

## Code covered
- [`src/agent/grok_agentic.py`](../../src/agent/grok_agentic.py) — product name + specialist registry (`OpsDoctor`, `CampaignRunner`).
- [`src/agent/goal.py`](../../src/agent/goal.py) — `AgentGoal` / criteria eval.
- [`src/agent/goal_loop.py`](../../src/agent/goal_loop.py) — bounded seed + Mode-B branch execution.
- [`src/agent/modes/ops_mode.py`](../../src/agent/modes/ops_mode.py) — OpsDoctor tools (`ops.*`).
- [`src/agent/modes/truth_mode.py`](../../src/agent/modes/truth_mode.py) — TruthJanitor tools (`truth.*`).
- [`src/agent/recipes/`](../../src/agent/recipes/) — ops + campaign + truth recipes.
- [`src/agent/intent_router.py`](../../src/agent/intent_router.py) — `IntentRouter.classify`.
- [`src/agent/plan_compiler.py`](../../src/agent/plan_compiler.py) — `PLAN_REGISTRY` (incl. `ops_diagnose`, `campaign_run`).
- [`src/agent/executor.py`](../../src/agent/executor.py) — confirm-gate + path-guard.
- [`src/agent/agent_core.py`](../../src/agent/agent_core.py) — turn loop; [`src/agent/cli.py`](../../src/agent/cli.py) REPL.

## Ins / Outs
- **Ins:** NL (`Ask GrokAgenticAI …`); `intent_patterns.json`; config `agent` section; optional `--agent ops_doctor|campaign_runner`.
- **Outs:** goal/linear execution; `logs/agent_audit.jsonl` + intent log; OpsDoctor packs under `results/incidents/`.

## Entry points & validations
- **Reached via:** `python -m src.agent.cli` · `--agent` · `-c "…"`.
- **Validated by:** specialist allowlists; `PLAN_REGISTRY` seeds; Executor fences; promotion still APPROVE-only.

## Tests
- [`tests/test_grok_agentic_ai.py`](../../tests/test_grok_agentic_ai.py) — brand, specialists, goals, ops tools, recipes.
- [`tests/test_agent_intent_router.py`](../../tests/test_agent_intent_router.py) — regex/LLM classification.
- [`tests/test_agent_plan_compiler.py`](../../tests/test_agent_plan_compiler.py) — PLAN_REGISTRY determinism.
- [`tests/test_agent_tool_registry.py`](../../tests/test_agent_tool_registry.py) — registration + write flags.
- [`tests/test_agent_executor_confirm.py`](../../tests/test_agent_executor_confirm.py) — confirm-gate, path-guard.

## Fits in architecture
An async "feeder" beside the spine ([`signal-flow.md`](../architecture/signal-flow.md)): it *invokes*
pipeline/governance tools but holds no execution authority. Governance design:
[`llm-governance-layer.md`](../architecture/llm-governance-layer.md). Full reference:
[`agent-reference.md`](../reference/agent-reference.md).

## Discussion (filled in-session)
- **Risks:** 2026-06-05 — write-tool safety rests on the executor confirm-gate + path-guard + `write_tools_enabled` allowlist; never weaken these to "auto-confirm."
- **Ambiguities:** 2026-06-05 — intent classification falls back to an LLM below the regex confidence floor; the *plan* stays deterministic but the *intent* can be LLM-chosen — keep that boundary clear.
- **2026-08-07 — GrokAgenticAI P0:** Product brand + multi-specialist differentiation shipped. OpsDoctor (read-heavy + incident pack) and CampaignRunner (pipeline goal loop with one REJECT→retune). Free tool choice still forbidden. Design doc remains authoritative for Phases 3–6.
- **2026-08-07 — P1 TruthJanitor:** `truth.*` tools wrap construction_protocol check, feature_math_lint, script_census (observe JSON), citation pytest floor, and confirm-gated `results/hygiene/` pack. No auto-edit of docs/findings/production.
- **2026-08-13 — Closed semantic environment:** `truth.ground_claim` + intent `semantic_ground` wrap `SemanticGrounder` (CT-008). Repository nouns/relations/implementation/evidence must come from tool-returned authority; UNKNOWN fails closed. Reasoning/prose stay free. Advisory only.
- **2026-08-19 — live_hook.dry_run rewrite (PR-4d):** Tool now builds `trade_data` via `LiveRailFeeder` (or refuses `feeder_not_ready`) and calls `HookedLiveEngine.process` with `hook_submit_orders=False`. The `LiveEngineHook` / `simulate_one` / `dry_run_ok` path is gone. Still not a production live rail (F-073 OPEN).
- **2026-08-19 — paper TickDB CLI (CH-live-rail-cli):** `scripts/live/run_live_rail.py --paper` is a thin diagnostic wrapper (SCR-399). Not an agent tool. Experimental paper drain: exit=0, 80 closed bars, 0 process_calls, 2× FEATURE_REJECT. F-073 stays OPEN.
- **2026-08-25 — JSONL claim kind + `REFUSED` (CH-jsonl-claim-surface PR-2):** `truth.ground_claim` now accepts `kind=JSONL`, which asks whether a JSONL stream may *close* a claim and requires `relation=CC-*` from `docs/governance/jsonl_claim_catalog.yaml`. Two behaviours matter for agent callers. (1) The tool's success path previously overwrote the grounding verdict — `out["status"] = "ok"` clobbered the value `to_dict()` had just written — so a refusal survived only as `passed: False`, indistinguishable from UNKNOWN. The verdict is now copied to **`grounding_status`** first; the envelope `status`/`passed` contract is unchanged, so existing consumers are unaffected. (2) For `kind=JSONL` the tool passes `token` **as-is** instead of `token or relation`, because an empty token is legal for a join-only call. No new intent — `semantic_ground` already routes here (CN-013: the LLM must not improvise tool graphs). Advisory; grants no authority.
