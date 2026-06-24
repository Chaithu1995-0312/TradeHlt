# Plan: Intent Governance Framework Doc

> Created: 2026-06-01 · Updated: 2026-06-01 · Milestone: M1

## Context

A recurring pattern across this repo: ideas (Phase experiments, structural hypotheses, model variants, agent intents) live across MEMORY, `docs/plans/`, code, configs, JSONL events, and commit history with no unified typed object and no named lifecycle. The Phase 0 → 6b sequence shows the system already *does* idea-governance implicitly — it just isn't named, which means future operators (human or LLM) can't load it, audit it, or verify it stays load-bearing.

Concrete failure receipts confirming the gap is real (not theoretical):

- **P3 verified** — `configs/promotion_log.jsonl` contains only `PROMOTED` and `PROMOTION_FAILED` events. There is no `DEMOTED` / `EXPIRED` / `KILLED` line schema. Phase 4b's `shadow_advisory_only = True` was a soft demotion with no audit event.
- **P1, P2** — Phase 0 (`retest_depth_max` hypothesis invalidated by telemetry) and Phase 6b (session-filter funnel diagnosed only via ad-hoc telemetry) per MEMORY findings.
- **P4** — `docs/reference/agent-reference.md` self-describes "17 intents" today. The historical "14 vs 17" drift incident closed without an enforcing checklist; the pattern can recur on any other doc.
- **P5, P6, P7** — preventative pillars; admitted under the stronger evidence threshold (1 Near Miss + 2 Modeled Scenarios), filed in framing discussion.

This plan creates a single architecture-tier doc that names the governance system, establishes admission rules so pillars can't inflate, and embeds a self-applying Verification Gate so the framework can detect its own drift instead of becoming ceremony.

## Recommended approach

Single file. Architecture tier. Narrative front, machine-loadable spec back. No code changes in this plan. Add a 3-line bidirectional cross-link header to existing `docs/reference/governance.md`. Defer stale-MEMORY remediation to the *first execution* of the Verification Gate (post-implementation follow-up, not a precondition).

### Step 1 — Create `docs/architecture/idea-governance-framework.md` (new file)

Single file, 9 sections in this order:

1. **Purpose** (2–3 paras) — the pattern (ideas fragmented across artifacts), what this doc fixes (names the implicit governance system), why it lives in `docs/architecture/` (load-bearing structure, not reference catalog — matches [`goal.md`](docs/architecture/goal.md), [`trigger-vocabulary.md`](docs/architecture/trigger-vocabulary.md), [`signal-flow.md`](docs/architecture/signal-flow.md)).
2. **System invariants (I1, I2)** — enforced across all pillars and domains:
   - **I1 Intent ↔ Code bidirection** — every code element traces to an idea ID; every idea traces to code (or explicit "not implemented").
   - **I2 Replayability** — any past state's *why* reconstructible from append-only logs + MEMORY + plans + promotion log.
3. **The 7 pillars** — table with columns: *Pillar · Question owned · Admission receipt · Evidence tier · Enforcement sites today · Operational domain*. Rows:
   - P1 Structure correctness — *Phase 0 `retest_depth_max` invalidated by telemetry* — Realized — phase findings, telemetry pipeline → Validation
   - P2 Validation ownership — *Phase 6b session-filter ambiguity* — Realized — `ConfigValidator` / `ModelRegistry` / `BacktestRunner` / **[gap: structure]** → Validation
   - P3 Promotion/demotion — *promotion_log.jsonl lacks DEMOTED; Phase 4b silent demote* — Realized (verified) — `configs/promotion_log.jsonl`, `src/governance/promotion_manager.py`, `src/runtime/model_registry.py` → Lifecycle
   - P4 Checklist enforcement — *doc-code drift pattern; closed 14-vs-17 instance* — Observed Pattern + closed instance — plans, SESSION LOG, `ValidationReport` → Governance
   - P5 Brick lifecycle — *idea fragmentation across artifacts* — Near Miss + 2 Modeled — **[gap: no typed object today]** → Lifecycle
   - P6 Write Authority & Delegation — *plan-mode vs SESSION-LOG rule collision* — Near Miss + 2 Modeled — plan mode, [`trigger-vocabulary.md`](docs/architecture/trigger-vocabulary.md), `ValidationReport.APPROVE` gate → Governance
   - P7 Long-term preservation — *stale MEMORY drift (e.g., 14-vs-17 entry)* — Near Miss + 2 Modeled — `assistant_project.md`, MEMORY, `promotion_log.jsonl`, plans → Preservation
4. **The 4 operational domains** — table: *Domain · Pillars · Current implementation · Named gaps*.
   - Validation = P1 + P2
   - Lifecycle = P3 + P5
   - Governance = P4 + P6
   - Preservation = P7 + I2
5. **Evidence model** — 4 tiers defined: Realized Failure / Near Miss / Observed Pattern / Modeled Risk.
6. **Admission rules** — Orthogonality + Receipt + Overlap. Thresholds: post-mortem pillar = 1 Realized Failure; preventative pillar = 1 Near Miss + 2 Modeled Scenarios.
7. **Pipeline narrative (human half)** — one idea's travel: Capture → Measure → Validate → Promote/Demote, with which pillars constrain each stage.
8. **Grid spec (machine half)** — rows × cols lookup table.
   - Rows = Brick states: Loose, Forming, Tested, Promoted, Demoted, Killed.
   - Cols = P1–P7.
   - Cells = required artifacts / allowed actions / write authority.
9. **Verification Gate** — 6 tests, cadence, recursion, storage:
   - T1 Orthogonality · T2 Receipt freshness · T3 Overlap · T4 Enforcement · T5 Drift · T6 Impact (≥1 cited use per review window; 4-review no-catch streak → tier downgrade).
   - Cadence: quarterly + on triggers (new agent type, new write path, model registry GOV change, structural change to CRT state graph, major doc reorg).
   - Recursion: pillars themselves move through P3 (`DEMOTED` after sustained failure); each review is a P4 submission; I1 + I2 apply to pillars.
   - Storage: `governance/framework_review_log.jsonl` (parallel to `configs/promotion_log.jsonl`; same line-schema family).
   - Owner: operator initially; future Framework Verification Agent explicitly forbidden by P6 from promoting/killing pillars (file-only authority).
10. **Existing implementations** (short index) — table of pillar → where it's enforced today: `promotion_log.jsonl`, `ConfigValidator`, `ModelRegistry`, `BacktestRunner`, plan mode, `trigger-vocabulary.md`, `ValidationReport`, MEMORY, `assistant_project.md`.
11. **Future extensions** (flag-list, no scope creep) — structure-validator owner, `DEMOTED`/`EXPIRED`/`KILLED` event classes, Brick schema, `framework_review_log.jsonl`, formal replay protocol.
12. **Cross-references** — [`goal.md`](docs/architecture/goal.md), [`trigger-vocabulary.md`](docs/architecture/trigger-vocabulary.md), [`signal-flow.md`](docs/architecture/signal-flow.md), [`governance.md`](docs/reference/governance.md) (P3 instance), [`conventions.md`](docs/reference/conventions.md).

Follows the [`trigger-vocabulary.md`](docs/architecture/trigger-vocabulary.md) precedent: narrative + spec in one file, so they co-evolve.

### Step 2 — Edit `docs/reference/governance.md` (bidirectional cross-link)

Insert a 3-line note immediately after the title, before any other content. No restructuring, no rewrite of body. Bidirection satisfies I1 at the doc tier:

```markdown
> This document is the **config-promotion implementation** of P3 (Promotion/Demotion)
> from [`docs/architecture/idea-governance-framework.md`](../architecture/idea-governance-framework.md).
> For framework-level governance concepts, see that doc.
```

### Out of scope (explicit, to prevent scope creep)

- **No code changes.** `governance/framework_review_log.jsonl`, the Brick schema, the `DEMOTED` event class, and a structure-validator owner are *named gaps* in the doc, not implementations in this plan.
- **No MEMORY edits.** The stale 14-vs-17 entry stays. It becomes the first artifact discovered by the first FrameworkReview run (T2 + T5), per the user's directive that stale-MEMORY remediation is the framework's first execution, not a precondition.
- **No restructure of `governance.md` body.** Only the 3-line header is added.
- **No new doc tier.** No `docs/governance/` directory created.

## Critical files

- **Create**: `docs/architecture/idea-governance-framework.md`
- **Edit (3-line header only)**: `docs/reference/governance.md`
- **Read before writing** (verification of receipts and citation paths):
  - `configs/promotion_log.jsonl` — P3 receipt (verified: 14 events, all `PROMOTED`/`PROMOTION_FAILED`)
  - `docs/reference/agent-reference.md:4` — P4 receipt (verified current: "17 intents")
  - `src/agent/intent_router.py` — P6 enforcement surface
  - `src/governance/promotion_manager.py` — P3 instance citation
  - `src/runtime/model_registry.py` — P3 model-tier instance citation
  - `src/config_layer/config_validator.py` — P2 surface for config domain
  - `src/runtime/backtest_v2.py` — P2 surface for decision domain
  - `docs/architecture/trigger-vocabulary.md` — P6 doctrine origin
  - [`MEMORY/MEMORY.md`](C:/Users/Hi/.claude/projects/D--Tradelatest/memory/MEMORY.md) — Phase findings cited in receipts
  - [`assistant_project.md`](assistant_project.md) — P7 surface

## Verification

End-to-end test that this plan landed correctly:

1. **Doc lives at architecture tier**: `docs/architecture/idea-governance-framework.md` exists, is a single file, has all 12 numbered sections in order.
2. **All 7 pillars have non-empty admission receipts**: every row in section 3 cites a real artifact (Phase finding, file path, MEMORY entry, JSONL event). No row is "TBD" or "Receipt pending."
3. **Cross-link bidirection works** (I1 at doc tier): framework doc references `governance.md`; `governance.md` header references framework doc. Both directions resolve in rendered markdown.
4. **Verification Gate is concretely actionable**: T1–T6 each have a clear pass/fail criterion and a documented fail action. A future reader can run the gate without re-reading the design discussion.
5. **No code touched**: `git diff --stat src/ configs/ scripts/` shows no modifications. Only `docs/architecture/idea-governance-framework.md` (added) and `docs/reference/governance.md` (3 lines added at top).
6. **All cited paths/symbols resolve**: after writing, run `Grep` on each `file:line` and each symbol cited in the framework doc — every citation lands on real content. (This is itself a T5 dry-run on the new doc.)
7. **First framework review enqueued as follow-up**: a SESSION LOG entry or follow-up note exists for "run first FrameworkReview against MEMORY + governance artifacts (T2 + T5 priority: stale 14-vs-17 entry)." This converts stale-MEMORY remediation from precondition into first use-case.
8. **Trigger-vocabulary alignment**: optionally, [`trigger-vocabulary.md`](docs/architecture/trigger-vocabulary.md) gains a brief reference noting the framework adds `FrameworkReview` and `FrameworkDrift` as future triggers (flagged in section 11, not a Tier 1/2 promotion).

Once these all pass, the framework is born load-bearing with its own self-audit mechanism, and the first run of that mechanism is the next planned action — not a blocker to creating the doc.
