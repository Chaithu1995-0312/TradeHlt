# Chapter 21 — The AI Automation Agent

**Part VIII — Agent Intelligence**
Status of this chapter: Orientation-level

## Why this chapter exists

Everything in Parts II–VII describes a system a human (or a script) drives directly. This chapter
covers the layer that lets natural language drive it instead — a deterministic, auditable agent
built specifically to avoid the failure mode of "the LLM improvised something." Keep this distinct
from [Chapter 23](23-multi-llm-coordination.md): that chapter covers *humans and multiple LLMs
collaborating on developing this repository*; this chapter covers *one in-repo agent operating the
trading system itself* through a fixed set of tools.

## What problem it solves

Explains how a natural-language command becomes a specific, bounded sequence of tool calls against
the trading system — and why that sequence is looked up, not generated fresh, on every request.

## What you need to already know

[Chapter 2](02-invariants-and-happy-flow.md) — the agent is one of the four async kitchen feeders,
and per invariant #3 it can drive the spine (Pipeline mode) but never silently mutate a decision in
flight (Copilot mode is explicitly read-only).

## The idea

### Five modes, each with its own tool surface

`src/agent/modes/` implements five distinct operating modes: **Pipeline** (drives the spine through
a backtest loop — 6 tools), **Copilot** (taps the Fusion/Decision step read-only, cannot mutate — 7
tools, all read-only by construction), **Governance** (interacts with the promotion machinery from
[Chapter 16](16-config-first-and-promotion.md) — 5 tools), **Findings**, and **Log Query**. Two
additional tools are available cross-mode. This mode separation is itself a safety mechanism: a
Copilot-mode session is structurally incapable of triggering a trade or a promotion, regardless of
what it's asked to do, because the tools that could do that simply aren't in its registry.

### Deterministic planning, not generated planning

This is the agent's central design decision, and it's worth dwelling on: when a natural-language
command comes in, an `IntentRouter` classifies it (a regex-first pass, with an LLM fallback for
ambiguous phrasing) into one of a fixed catalogue of intents. A `PlanCompiler` then looks that
intent key up in `PLAN_REGISTRY` — a hardcoded dictionary in `src/agent/plan_compiler.py`, "the
single source of truth for what steps each intent runs." **The LLM never generates the tool-call
sequence itself.** It only helps identify *which* pre-written sequence applies. This is the same
"LLM is advice, never a trigger" invariant from [Chapter 2](02-invariants-and-happy-flow.md), applied
at the level of *what the agent is allowed to do* rather than just *what decision it can influence*.

An `Executor` then runs the compiled plan, gated by a confirm-step and a path-guard (preventing the
agent from writing outside its authorized surface), tracked through `AgentState`.

### Implementation depth sketch (Grok review pass — still orientation, not a full rewrite)

The review asked for more than a brochure on Part VIII. The following is the **load-bearing call
chain** a reader should keep in mind; the complete tool tables remain in
`docs/reference/agent-reference.md`.

```
User natural language
  → IntentRouter.classify()     # regex first, LLM fallback only for ambiguity
  → PlanCompiler.build(intent) # PLAN_REGISTRY[intent] → ordered ToolSteps
  → Executor.run(plan)         # confirm gate + path-guard + AgentState
       → tool_registry handlers (mode-scoped)
  → dual JSONL audit (per-step + session intent summary)
```

**Intents (order-of-magnitude, not a freeze of the catalogue):** pipeline / copilot / governance /
findings / log-query families — roughly a dozen named intents, each mapped to a **fixed** tool
sequence. Adding a capability is a code change to `tool_registry.py` **and** a new or extended
`PLAN_REGISTRY` entry — never "the model decided to call arbitrary tools."

**REPL entry:** `src/agent/cli.py` (and related agent package CLI wiring) is the human-facing loop;
config knobs live under the production config's `agent` section (fail-fast load patterns apply).

**What the agent cannot do by design:** promote a config without the same `ConfigValidator` /
`PromotionManager` path a human uses ([Chapter 16](16-config-first-and-promotion.md)); invent a new
plan graph at runtime; write outside path-guard; run Copilot tools that mutate the spine.

### Everything is logged, twice

Every agent action writes to `logs/agent_audit.jsonl` (a per-step record of exactly what tool ran
with what arguments) and `logs/agent_intent_log.jsonl` (a session-level summary of what was asked
and how it was classified). This gives the same replayability guarantee
([Chapter 2](02-invariants-and-happy-flow.md)'s invariant #1) to agent-driven work that the core
spine already has for candle-driven work.

## Classification

| Concept | Status |
|---|---|
| Five-mode structure (Pipeline/Copilot/Governance/Findings/Log Query) | Production |
| `PLAN_REGISTRY` deterministic lookup | Production — the core safety mechanism |
| `IntentRouter` (regex + LLM fallback) | Production |
| Dual audit logging | Production |

## Authoritative sources

- `docs/reference/agent-reference.md` — the complete reference: all tools per mode, the intent
  catalogue, the full `PLAN_REGISTRY` tables, the `Executor`'s confirm-gate and path-guard, audit log
  field semantics, and the procedure for adding a new tool. This chapter summarizes it; that
  document is the one to read for implementation detail.
- `src/agent/plan_compiler.py` — `PLAN_REGISTRY` (line ~43) and `PlanCompiler.build()`.
- `src/agent/intent_router.py`, `tool_registry.py`, `executor.py`, `state.py`, `audit.py`.
- `src/agent/modes/` — the five mode implementations.
- `docs/topics/ai-automation-agent.md` — the always-synced topic doc.

## Unresolved questions

None for the architecture itself — `agent-reference.md` is a comprehensive, well-structured primary
source. Whether every documented tool in the reference is currently reachable end-to-end (vs.
scaffolded) wasn't independently re-verified this pass.

---
**Previous:** [Chapter 20 — The Research Platform](20-research-platform.md) · **Next:** [Chapter 22 — The Control Plane](22-control-plane.md)
**Related:** [Chapter 23 — Multi-LLM Coordination](23-multi-llm-coordination.md) (a different, human-orchestrated layer — don't conflate the two)
**Memory:** `docs/memory/agent-memory.md`.
