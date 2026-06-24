# Topic: AI Automation Agent

> **Topic-visibility unit.** The ChatOps overlay: natural language → classified intent → a
> **deterministic** tool plan → confirm-gated execution. Concept narrative; the full tool/intent
> tables live in [`agent-reference.md`](../reference/agent-reference.md).
>
> Created: 2026-06-05 · Updated: 2026-06-05 · Status: living

## In plain language
The agent lets an operator drive the pipeline in plain English ("tune and validate BNB"). It
**classifies** the request into one of 17 intents, then looks up a **fixed, ordered list of tools** for
that intent (the LLM never chooses tools or order — that's the key safety property). Read tools run
freely; **write tools halt for a `y/N` confirm** and are path-guarded. So the agent is advisory
automation, never autonomous execution authority.

## Code covered
- [`src/agent/intent_router.py:51`](../../src/agent/intent_router.py) — `IntentRouter` — `classify()` at :72 (regex fast-path → LLM fallback → `ask_user`).
- [`src/agent/plan_compiler.py:43`](../../src/agent/plan_compiler.py) — `PLAN_REGISTRY` — intent → ordered `ToolStep` list; `PlanCompiler.build()` at :126.
- [`src/agent/tool_registry.py:31`](../../src/agent/tool_registry.py) — `REGISTRY` — the 25 tools; `register_tool` decorator at :34.
- [`src/agent/executor.py:45`](../../src/agent/executor.py) — `Executor` — `dispatch()` at :57 (confirm-gate); `_path_allowed` path-guard at :34.
- [`src/agent/agent_core.py:39`](../../src/agent/agent_core.py) — `AgentCore` — the per-turn loop; `src/agent/cli.py:49 · main` is the REPL.

## Ins / Outs
- **Ins:** NL user input + conversation; `src/agent/prompts/intent_patterns.json`; config `get_prod_section("agent")` (`write_tools_enabled`). 17 intents, 25 tools (pipeline/copilot/governance/cross-mode/log-query).
- **Outs:** an executed (or pending-confirm) ordered plan; audit lines to `logs/agent_audit.jsonl` + `logs/agent_intent_log.jsonl`; tool results.

## Entry points & validations
- **Reached via:** `python -m src.agent.cli` (interactive REPL; `--resume <session>`). Tools may also be invoked by the control plane.
- **Validated by:** deterministic `PLAN_REGISTRY` (no LLM tool-choice); executor allowlist + path-guard (`_WRITE_ROOTS`) + per-call confirm for `write=True`; promotion still requires an APPROVE `ValidationReport`.

## Tests
- [`tests/test_agent_intent_router.py`](../../tests/test_agent_intent_router.py) — regex/LLM classification.
- [`tests/test_agent_plan_compiler.py`](../../tests/test_agent_plan_compiler.py) — PLAN_REGISTRY determinism + skip filtering.
- [`tests/test_agent_tool_registry.py`](../../tests/test_agent_tool_registry.py) — registration + write flags.
- [`tests/test_agent_executor_confirm.py`](../../tests/test_agent_executor_confirm.py) — confirm-gate, path-guard, allowlist.

## Fits in architecture
An async "feeder" beside the spine ([`signal-flow.md`](../architecture/signal-flow.md)): it *invokes*
pipeline/governance tools but holds no execution authority. Governance design:
[`llm-governance-layer.md`](../architecture/llm-governance-layer.md). Full reference:
[`agent-reference.md`](../reference/agent-reference.md).

## Discussion (filled in-session)
- **Risks:** 2026-06-05 — write-tool safety rests on the executor confirm-gate + path-guard + `write_tools_enabled` allowlist; never weaken these to "auto-confirm."
- **Ambiguities:** 2026-06-05 — intent classification falls back to an LLM below the regex confidence floor; the *plan* stays deterministic but the *intent* can be LLM-chosen — keep that boundary clear.
