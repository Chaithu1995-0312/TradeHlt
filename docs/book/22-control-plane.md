# Chapter 22 — The Control Plane

**Part VIII — Agent Intelligence**
Status of this chapter: Orientation-level

## Why this chapter exists

The repository has no REST API by design ([Chapter 2](02-invariants-and-happy-flow.md)'s invariant
#7 — no database, no broker, no cloud dependency extends to "no network service surface" as a
default posture). But someone still needs a single, discoverable catalogue of every command this
system supports, and a place for a human-facing dashboard to hang off of. That's the control plane.

## What problem it solves

Gives every CLI-invocable command in the system one canonical, machine-readable declaration —
instead of a human needing to grep `scripts/` to discover what's runnable.

## What you need to already know

[Chapter 21](21-ai-automation-agent.md) — the AI Agent's tool registry and the control plane's
command registry are siblings in spirit (both are declarative catalogues), though distinct in scope
(the agent's tools operate the trading system; the control plane catalogues *every* runnable command).

## The idea

### A declarative catalogue, not an execution engine

`src/control_plane/registry.py` defines a `CommandSpec` for every registered command (its
`ArgSpec`s, from `cp_types.py`, and an argv template) — a catalogue, not the execution logic itself.
It also carries a `WORKFLOW_STAGE_ORDER` tuple laying out the canonical operational pipeline in six
stages: **Data Prep → Tuning → Model Training → Validation & Promotion → Replay & Backtest → Live
Runner** — and a mapping from roughly 19 concrete command IDs (`data.prepare_data`,
`tuning.auto_tuner_multi`, `governance.orchestrator`, `promotion.manager`, `backtest.v2`,
`live.inout_runner`, and others) to the stage they belong to, plus a small set of quickstart usage
notes per command. This is effectively the machine-readable backbone behind
`docs/reference/cli-matrix.md`'s human-readable command catalog.

### The localhost dashboard

A small HTTP surface (`server.py`, `dashboard_api.py`, `report_api.py`) exposes this registry to a
browser-based UI at `localhost:8787`, picking up new registered commands automatically via
`ControlPlaneAPI.commands_payload()` — adding a `CommandSpec` is enough to make a command appear in
the UI, with no separate UI-side wiring needed. This surface is explicitly **localhost-only, with no
authentication layer and no TLS** — it is not meant to be exposed beyond the machine it runs on, and
should never be.

### Supporting modules

`code_context_extractor.py`, `context_report.py`, and `dot_graph_context.py` build the contextual
information the AI Agent's Copilot mode ([Chapter 21](21-ai-automation-agent.md)) can surface to an
LLM — dependency-graph context, code excerpts — while `jobs.py` and `monitors.py` handle running and
observing long-lived background operations the control plane kicks off.

## Classification

| Concept | Status |
|---|---|
| `CommandSpec` registry (`registry.py`, `cp_types.py`) | Production |
| Localhost dashboard (`server.py` + UI) | Production, deliberately unauthenticated/local-only |
| Context-extraction support modules | Production, primarily in service of the AI Agent's Copilot mode |

## Authoritative sources

- `src/control_plane/registry.py`, `cp_types.py` — the `CommandSpec` catalogue,
  `WORKFLOW_STAGE_ORDER`, and stage/command mapping.
- `docs/reference/control-plane.md`, `docs/reference/cli-matrix.md` — the full reference and the
  auto-generated command catalog.
- `src/control_plane/server.py`, `dashboard_api.py`, `report_api.py`, `jobs.py`, `monitors.py`.
- `CLAUDE.md` §4 — the localhost-only, no-auth constraint, stated as a hard operational limit.

## Unresolved questions

None for this pass — the control plane's scope (declarative catalogue + localhost dashboard) is
narrow and was confirmed directly against source.

---
**Previous:** [Chapter 21 — The AI Automation Agent](21-ai-automation-agent.md) · **Next:** [Chapter 23 — Multi-LLM Coordination](23-multi-llm-coordination.md)
**Related:** [Chapter 04 — Architecture at a Glance](04-architecture-at-a-glance.md)
**Memory:** none dedicated — see `docs/memory/architecture-memory.md` for cross-package context if needed.
