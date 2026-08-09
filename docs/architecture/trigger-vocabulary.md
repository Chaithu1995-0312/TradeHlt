# trigger-vocabulary.md

> **Purpose (LLM context economy):** The command vocabulary by which an LLM session
> *owns* this codebase. Each trigger word maps to a concrete **action**, the exact
> **docs/prompts it loads**, and an **exit condition**. The architecture docs are the
> context units; these triggers are how the LLM *moves between and acts on* them without
> re-deriving context every turn.
>
> Read this when the user issues a single-word command (`Continue`, `Validate`,
> `Implement`, …) or asks how the trigger vocabulary works. Pairs with `CLAUDE.md §6/§7`
> (the Response Ritual + SESSION LOG mandate) and the Trd-M0–M5 migration index in
> `docs/plans/`.

---

## Cold start (read this first)

If you are a fresh session with **no carried context**, do exactly this before acting on
any trigger:

1. You are already in `CLAUDE.md` — the first file every session loads. It pointed you
   here via §12.
2. Run **Orient** (§2): read, *in this order* —
   a. the **Repository Truths Index** in `CLAUDE.md` + the living [`docs/current-findings.md`](../current-findings.md) — the current validated conclusions / reversals / open questions, so you don't re-run settled work or trust a stale claim (`CLAUDE.md §6.2`);
   b. the newest file in `docs/plans/*.md` — the active plan + the Trd-M0–M5
      status header at its top;
   c. the last 1–2 `📝 SESSION LOG ENTRY` blocks at the **tail** of `assistant_project.md`;
   d. the `MEMORY.md` index.
   Then state, in one screen: **active milestone · what's ✅ done · what's next · open
   questions.**
3. If the user gave a task, run **Map** (§2) to locate the service/seam it touches;
   otherwise stop after Orient and await a trigger.
4. Obey the §0 doctrine on every subsequent trigger (no new authority · end with the
   SESSION LOG · score the Five Questions · triggers compose).

You are now warm. Proceed with the issued trigger.

---

## 0. Doctrine (non-negotiable)

1. **Triggers are advisory orchestration, never new authority.** Each maps to an existing
   ritual, doc, or CLI path. No trigger bypasses the agent write-authority `_WRITE_ROOTS`,
   the path-guard, the `y/N` confirm gate, or the `APPROVE`-`ValidationReport` promotion
   gate (`governance/promotion_manager.py`). A trigger never *grants* permission it does
   not already have.
2. **Every trigger ends with SELF-DOCUMENT** (`CLAUDE.md §6` / `§7.4`): append the
   `📝 SESSION LOG ENTRY` block to `assistant_project.md`. A response is incomplete until
   the block is both shown and persisted.
3. **Every state-changing trigger is scored against the Five Governance Questions**
   before it is considered done:
   1. Does replay remain deterministic?
   2. Does telemetry remain comparable across runs?
   3. Can this state be audited later?
   4. Can an LLM reason about this event?
   5. Is execution authority still isolated?
4. **Triggers compose.** A high-level trigger may fan out into lower-level ones — e.g.
   `Continue` typically runs `Orient → Map → Next step → Validate → Log`. Canonical
   compositions are listed in §3.

---

## 1. Tier 1 — Execution triggers (the primary five)

| Trigger | Action | Loads (docs/prompts) | Exit condition |
|---|---|---|---|
| **Continue** | Resume the active work from where it left off. Find the in-progress milestone/step from the latest plan + recent SESSION LOG and advance the next incomplete action **without re-asking**. | latest `docs/plans/*.md`; recent `assistant_project.md` SESSION LOG entries; `MEMORY.md` | next pending step advanced + SESSION LOG appended |
| **Next step** | Mark the current step done; execute the **next discrete step *within* the current milestone**. Stay inside the milestone's scope. | active plan file; the relevant `services/<svc>.md` or architecture doc for that step | one step done + Five Questions scored + SESSION LOG |
| **Next plan** | Confirm the current milestone passed `Validate`, then **enter the next milestone** in Trd-M0–M5 (or draft a new plan if none remains). | Migration Sequencing index in the plan file; `codebase-state-map.md`; `service-boundary-map.md` | next milestone scoped + entered (or new plan drafted via `Plan`) |
| **Validate** | Run the milestone's verification gate: `pytest` per `docs/reference/testing.md`, the determinism / byte-identical replay check, and doc-citation resolution (`tests/test_doc_citations.py` — every `path:line · Symbol` resolves, §6.3); then score the Five Questions. **Read-only — never edits code.** | `docs/reference/testing.md`; `replay-governance.md`; the plan's Verification section | pass/fail report per gate + SESSION LOG |
| **Implement** | Turn the **approved** plan into code: exit plan mode, make surgical *additive* edits per `CLAUDE.md §3` patterns, honor path-guard / write-authority, then auto-run `Validate`. | `docs/reference/example-service.py`; `docs/reference/conventions.md`; `docs/reference/schemas.md`; target `services/<svc>.md`; the approved plan | code applied + `Validate` run + SESSION LOG |

---

## 2. Tier 2 — Ownership / self-navigation triggers

| Trigger | Action | Loads (docs/prompts) | Exit condition |
|---|---|---|---|
| **Orient** / **Status** | Report current state: active milestone, what's done (✅), what's next, open questions. **Read-only.** | `CLAUDE.md` Repository Truths Index + `docs/current-findings.md`; active plan; `assistant_project.md`; `MEMORY.md` | one-screen status report |
| **Map** | Load architecture context to locate **where a change lands** (which service / seam). **Read-only.** | `codebase-state-map.md`; `service-boundary-map.md`; `event-taxonomy.md`; `docs/architecture/signal-flow.md`; relevant `services/<svc>.md` | the target service/seam identified |
| **Audit** | Re-verify each architecture doc's `file:line` citations + contracts against the actual code; list gaps; apply **additive doc-only** fixes (the doc-alignment ritual). | all `docs/architecture/*.md` + the cited source files | accuracy verdict per doc + additive fixes + SESSION LOG |
| **Sync** | Reconcile the affected `docs/topics/<topic>.md` against the current code: read → surgical edit (**only that topic file** — token-aware), bump `Updated:`, append dated entries to its Discussion block. **Also update any `path:line · Symbol` citations that point at code you moved** (`CLAUDE.md §6.3` Citation Sync Mandate) — use `docs/architecture/citation-map.generated.md` to find them. The `CLAUDE.md §6.4`/§6.3 mandates, named explicitly. Additive doc-only. | the touched `docs/topics/<topic>.md`; the cited source files; `docs/architecture/citation-map.generated.md`; `docs/topics/_template.md` (if promoting a stub) | topic doc + citations match code + dated Discussion + SESSION LOG |
| **Plan** | Enter plan mode; Phase-1 Explore → Phase-2 design → write the plan to `docs/plans/` (persisted by the Workstream-A hook); end with `ExitPlanMode`. Every plan opens with a `> Created: YYYY-MM-DD · Updated: YYYY-MM-DD · Milestone: M<n>` header — dated like the SESSION LOG (`CLAUDE.md §6`). **No code change in plan mode.** | relevant architecture docs; `CLAUDE.md §3` patterns | an approved, dated plan file |
| **Log** | Append the `📝 SESSION LOG ENTRY` block — names the `CLAUDE.md §6` mandate explicitly so it is never skipped. | `assistant_project.md` | block shown + persisted |
| **Register scripts** | Inventory hygiene for new/moved scripts (SITS): run `--write-stubs`, add a **seed overlay** with `purpose ≠ GRANDFATHER_UNCLASSIFIED`, seed + regenerate matrix. Prefer change class `SCRIPT_LIFECYCLE_CHANGE`. Grants **no** promote authority. | `docs/reference/conventions.md` §2.1; `docs/governance/change_contracts.json` (`SCRIPT_LIFECYCLE_CHANGE`); design `script-implementation-traceability-sits-design.md` | stubs + overlay + matrix green (`tests/test_script_registry.py`) + SESSION LOG with SCR-ids |

---

## 3. Canonical compositions

The high-level triggers expand into deterministic sequences. When in doubt, follow these:

```
Continue   = Orient → Map → Next step → Validate → Log
Next step  = (load step doc) → make change → score Five Questions → Log
Next plan  = Validate(current milestone) → Map → enter next M-milestone → Log
Validate   = pytest (docs/reference/testing.md) → determinism/replay check → Five Questions → Log   [read-only]
Implement  = (exit plan mode) → additive edits (CLAUDE.md §3) → Validate → Log
Plan       = Explore → design → write docs/plans/*.md → ExitPlanMode
Audit      = read all docs/architecture/*.md → diff vs code → additive doc fixes → Log
Sync       = read touched code → update only that docs/topics/<topic>.md → bump Updated: → Log
Orient     = read findings + plan + SESSION LOG + MEMORY → one-screen report               [read-only]
Map        = read CODEBASE_STATE_MAP + SERVICE_BOUNDARY_MAP + EVENT_TAXONOMY + SIGNAL_FLOW [read-only]
Log        = append 📝 SESSION LOG ENTRY to assistant_project.md
Register scripts = write-stubs → seed overlay → seed → matrix → Validate(SITS floors) → Log
```

**Read-only triggers** (`Orient`, `Status`, `Map`, `Validate`) never modify code or
config — they only read and report. Everything else is additive and reversible per the
plan's Rollback Strategy.

---

## 4. How to add a new trigger

1. Decide its **tier**: Tier 1 if it advances/changes work, Tier 2 if it navigates/reports.
2. Define the three columns: **action**, **docs/prompts loaded**, **exit condition**.
3. Confirm it obeys all four doctrine rules in §0 — especially that it adds **no new
   authority** and ends with SELF-DOCUMENT.
4. Add a row to the relevant table here, a composition line to §3, and a one-line gloss
   to `CLAUDE.md §12`.
5. If it touches code, it must be scored against the Five Governance Questions.

**Deferred — governance superset.** `Promote`, `Baseline`, `Rehash`, `Rollback` are
intentionally *not* defined here. They already have authoritative docs and CLI entry
points — see `docs/reference/governance.md` (promotion / rollback), `src/runtime/baseline_capture.py`
(`Baseline`), and `scripts/maintenance/_compute_hash.py` (`Rehash`). The vocabulary
*references* them rather than redefining them.

---

## 5. Cross-references

- `CLAUDE.md §6` — Persistent Logging Mandate (the SESSION LOG block every trigger ends with).
- `CLAUDE.md §7` — Response Ritual: ORIENT → PROBE → IMPLEMENT → SELF-DOCUMENT (the
  per-turn skeleton these triggers operate inside).
- `CLAUDE.md §3` — How to Work With This Codebase (the patterns `Implement` must follow).
- `docs/plans/` — the active plan + Trd-M0–M5 migration index (`Continue` /
  `Next step` / `Next plan` read from here).
- `docs/architecture/service-boundary-map.md` + `codebase-state-map.md` — what `Map` loads.
- `docs/reference/testing.md` + `replay-governance.md` — what `Validate` runs against.
- `assistant_project.md` — the SESSION LOG sink + Five-Questions pre-merge checklist.
- `multi_llm/PROMPT_PLAYBOOK.md` — the copy-paste prompt library behind these triggers: its
  **GATHER** phase backs `Orient`/`Map`, **ENHANCE** sharpens the handoff prompt, and **IMPLEMENT**
  backs `Implement` → `Validate` (audit/sign-off = the `Validate` gate, not a model). Relabeled to
  the frozen multi-LLM role map; grants no new authority (CLAUDE.md §13).
