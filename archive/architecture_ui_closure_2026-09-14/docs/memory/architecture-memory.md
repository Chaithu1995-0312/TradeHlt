# Architecture Memory (navigation)

> **Last generation:** 2026-08-07  
> **Code-first:** source under `src/` is authoritative on conflict.

## Purpose

Index the whole-system layer map so a session can locate the correct subsystem, spine path, and deep companions without loading the entire repository.

## Responsibilities

- State the layer hierarchy (surfaces → agent → governance → config → runtime → features → engines → core spine → execution/telemetry).  
- Point to ownership contracts (semantic decision vs capital risk; config Tier-0; agent tool order).  
- Route tasks to the correct subsystem memory document.  
- Link the full reverse-engineered map when a session needs deep file-level contracts.

## Runtime role

**Navigation / cold-start.** Not on the trading hot path. Does not execute code.

## Entry points

| Surface | Location |
|---|---|
| Bootloader | `CLAUDE.md` (policy pointer only) |
| Memory index | `docs/memory/README.md` |
| Full map (deep) | `docs/architecture/architecture-memory.md` |
| Candle→order walk | `docs/architecture/signal-flow.md` |
| I/O catalog | `docs/architecture/entry-exit-map.md` |
| Service seams | `docs/architecture/service-boundary-map.md` |
| Decision spine exemplar | `docs/architecture/services/decision-spine.md` |

## Exit points

- Handoff into a **subsystem memory** doc (`agent` / `runtime` / `feature` / `engine` / `governance`).  
- Handoff into **source files** listed in those docs’ Reading order.  
- No runtime artifacts produced by this document itself.

## Important contracts

1. **Tier-0 config:** `configs/production/ACTIVE_VERSION` → production JSON (hash-verified via `production_config.py`).  
2. **Spine order:** Features → four engines → Fusion → DecisionEngine (semantic) → ExecutionPlanner → UltronRiskGate (capital).  
3. **Expected engines:** `{crt, gaussian, zone_gate, rr}` — incomplete set must not ACCEPT via fusion.  
4. **LLM is advisory** — never capital or tool-order authority.  
5. **Code wins** over this memory and over deep companions.

## Reading order

1. This file (orientation).  
2. Subsystem memory for the task domain (see `README.md`).  
3. If cross-cutting spine: `docs/architecture/signal-flow.md` then `services/decision-spine.md`.  
4. Deep map only if needed: `docs/architecture/architecture-memory.md`.  
5. **Source** at the listed entry points — final authority.

## Related documents

| Doc | Role |
|---|---|
| [`ARCHITECTURE_MEMORY_POLICY.md`](ARCHITECTURE_MEMORY_POLICY.md) | Hierarchy + maintenance rules |
| [`README.md`](README.md) | Task → memory map |
| [`../architecture/architecture-memory.md`](../architecture/architecture-memory.md) | Full reverse-engineered detail |
| [`../architecture/signal-flow.md`](../architecture/signal-flow.md) | Per-candle spine |
| [`../architecture/entry-exit-map.md`](../architecture/entry-exit-map.md) | External I/O |
| [`../architecture/service-boundary-map.md`](../architecture/service-boundary-map.md) | Service seams |
| [`../reference/architecture.md`](../reference/architecture.md) | Stack / tree / patterns |

## Known coverage

| Scope | Status |
|---|---|
| Layer map + contracts | Indexed here |
| Subsystem routing | 6 memory docs |
| Deep file contracts | In `docs/architecture/architecture-memory.md` (~40% of `src/` by name; spine packages high) |
| Full inventory of all 1,220 governed `.py` | **Not** this doc — use functionality Excels |
| `src/research/` (~143 files) | Package-level only in deep map |

## Last generation timestamp

2026-08-07
