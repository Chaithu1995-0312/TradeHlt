# Plan — Analyse `assistant_project.md` & Trace User Intention "of Tool"

> Created: 2026-05-30 · Updated: 2026-05-30 · Type: analysis (doc-only, additive)

## Context

The user asked to **analyse `assistant_project.md`** (the repo's append-only SESSION LOG,
2472 lines / 37 entries, 2026-04-10 → 2026-05-30) and **trace the user's intention "of tool."**
Clarified scope = **Both**:

1. **Project intent arc** — what the user has been trying to build and *why*, reconstructed
   from the session log (plain-language narrative; user thinks in goals/flows/outcomes).
2. **Agent intent→tool layer** — the literal "user intention → tool" machinery in `src/agent/`
   (`IntentRouter.classify` → `PLAN_REGISTRY` → `Executor` → `tool_registry`), and how the
   project arc maps onto it.

Deliverable = a **new point-in-time doc** under `docs/analysis/` (the repo's convention for
dated, non-living analyses — see `docs/analysis/readme.md`). This is purely additive: one new
file + one index row. No code, no config, no living-doc edits.

## Deliverable

**New file:** `docs/analysis/user-intention-trace-2026-05-30.md`
**Index row added to:** `docs/analysis/readme.md` (the table, top of list).

## Doc structure (sections)

1. **Header + scope note** — point-in-time disclaimer (matches sibling files); source =
   `assistant_project.md` as of 2026-05-30.
2. **The intention arc (5 eras)** — narrative traced from the log's 37 entries:
   - **Era 1 · Foundation & documentation** (2026-04-10 → 04-22): enhancement plan phases 0–5,
     JSON-as-single-source-of-truth, master-context docs suite, architecture diagram, agent
     design docs. Intent: *make the system governable + legible.*
   - **Era 2 · Stabilisation & correctness** (2026-04-25 → 04-30): pytest restored to 0 failures,
     stale-API agent test fixes, dead-code archive, RR data-integrity audit (rr=2.0 contamination),
     canonical naming (UltronRiskGate), feature-zeroing root-causes, signal-flow doc. Intent:
     *trust the numbers before extending.*
   - **Era 3 · Multi-strategy expansion** (2026-04-30 → 05-01): Sprints 1–7 — 10 strategies,
     StrategyOrchestrator, FusionEngine multi-strategy, MonteCarlo, KillSwitch, UAT, live hook,
     Docker, governance. Intent: *scale from CRT-only to a portfolio engine.*
   - **Era 4 · Empirical, telemetry-driven tuning** (2026-05-12 → 05-30): two-layer arch
     (runtime vs research), direction-mirroring, calibration; then the **BNBUSDT Phase 0→6b**
     measure-first loop (shadow displacement, expansion TTL, age-decay verdict=advisory-only,
     threshold sweep, ROI baseline, funnel diagnosis: RETEST→EXECUTION binding constraint =
     session filter). Intent: *let measured data, not hypotheses, drive changes* (memory:
     several hypotheses were invalidated by telemetry).
   - **Era 5 · LLM-context-economy migration** (2026-05-28 → 05-30): M0–M5 event-driven
     migration doctrine, trigger vocabulary, GOAL.md north-star, collaboration workflow,
     code-map generator, semantic docs reorg. Intent: *make the codebase ownable by an LLM
     loading only one service's context.*
3. **The throughline (deep intention)** — synthesis: the user's consistent meta-goal is a
   trading system that is (a) deterministic/replayable, (b) governed (no config to prod without
   APPROVE), (c) empirically validated not guessed, and (d) **LLM-ownable** — the five
   governance questions + context-economy north star are the unifying frame.
4. **The agent intent→tool layer (literal "user intention of tool")** — trace the pipeline:
   `User NL → IntentRouter.classify() (regex fast-path conf 0.85 → LLM fallback conf_floor 0.6
   → degenerate ask_user) → PlanCompiler.build() (deterministic PLAN_REGISTRY, LLM never picks
   tools) → ArgFiller → Executor.run() (confirm-gate on write tools + path-guard) → AuditLogger`.
   Tables: 14 intents (7 pipeline / 3 copilot / 3 governance / 1 cross-mode + ask_user),
   intent→tool-sequence map, write/read split. Cite `src/agent/intent_router.py`,
   `plan_compiler.py`, `tool_registry.py`, `executor.py`.
5. **Where the two meet** — map: the agent's design *embodies* the project intent. Determinism
   (PLAN_REGISTRY) ⇄ replay-correctness invariant; copilot read-only + UltronRiskGate sole
   authority ⇄ "LLMs advisory, never execution"; confirm-gate/path-guard ⇄ governed writes;
   audit JSONL ⇄ auditability question. The trigger vocabulary (Era 5) is the human-facing
   sibling of the agent's intent routing.
6. **Open intentions (from latest `Next Step` fields)** — M3 orchestration de-coupling; Phase 5
   tier_2_threshold sweep; ROI session-window sweep (add Asia); gate-on-ROI vs optimize-for-ROI
   decision still pending with user.

## Sources (already read during planning)

- `assistant_project.md` — full topic/date/next-step arc (37 entries).
- `docs/reference/agent-reference.md` §1–§5 — routing flow, 14 intents, 20 tools, PLAN_REGISTRY.
- `docs/analysis/readme.md` — naming/format convention + index table.
- Memory: `project_phase*` entries (Phase 0/1/2b/3b/4b/5a/6/6b) corroborate the "measure-first,
  hypotheses-invalidated" intention in Era 4.

## Verification

- All `file:line` / module citations in the doc resolve (grep the cited symbols:
  `IntentRouter`, `PLAN_REGISTRY`, `PlanCompiler`, intent keys) — read-only check.
- New file follows sibling format (header + point-in-time disclaimer + dated kebab-case name).
- `docs/analysis/readme.md` table gains exactly one new row, dated 2026-05-30, no other edits.
- Append the mandated `📝 SESSION LOG ENTRY` block to `assistant_project.md` (CLAUDE.md §6).
