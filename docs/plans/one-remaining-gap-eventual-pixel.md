> Created: 2026-06-01 · Updated: 2026-06-01 · Milestone: M2

# M2 — User Progress Registry

## Context

The just-shipped [M1 — Idea Governance Framework](../../../D:/Tradelatest/docs/architecture/idea-governance-framework.md) names **what governs ideas** (7 pillars, Brick lifecycle, evidence tiers, verification gate). It does *not* yet answer the user's operational question: **"which ideas are actually moving, which are stalled, which are abandoned?"**

Today that state is implicit — scattered across MEMORY entries, `docs/plans/`, commit history, and the user's head. Reconstructing "what's open right now and who owes the next move" requires a multi-file crawl (M1 §3 P5 receipt, idea-governance-framework.md:94).

M1 §11 already flags **Brick schema** and **`framework_review_log.jsonl`** as future extensions. M2 is the *first instantiation* of the Brick schema as a human-readable single-screen view — not the full audit log (that's M4). It closes the gap between "the framework exists" and "the framework is in daily use."

**Scope confirmed with user:**
- Two-axis status: epistemic `state` (M1's `Loose/Forming/Tested/Promoted/Demoted/Killed`) **plus** operational `progress_status` (`ACTIVE/BLOCKED/SHIPPED/ABANDONED/IDLE`). These answer different questions; both are needed.
- Both code-internal ideas (Phase 6c, M2, P-series) **and** user-domain projects with no code footprint yet (`VOICE_JARVIS_001`, etc.).
- Markdown-only for M2; JSONL audit trail deferred to M4 (Replayable Decision Journal).

---

## Deliverable

A single new file: **`docs/governance/user-progress-registry.md`** — markdown, human-edited, single-screen scannable, machine-loadable via its table.

The file is the **current-state view** of every live Brick. It does not duplicate M1 (the rules) or the SESSION LOG (the narrative) — it sits between them.

---

## File structure

The doc mirrors M1's narrative-front / spec-back convention ([idea-governance-framework.md:13-15](../../../D:/Tradelatest/docs/architecture/idea-governance-framework.md)) and is organized as:

1. **Purpose** — one paragraph: what this is, what it is not, why it lives in `docs/governance/`.
2. **How to use** — the daily ritual: when to add a Brick, when to update Last Reviewed, when to mark BLOCKED, when to ABANDONED. Plain prose, ~10 lines.
3. **ID conventions** — explicit naming scheme (see §"ID format" below).
4. **Status vocabulary** — two-axis table: epistemic `state` (with link to M1 §8) + operational `progress_status` (new, defined here).
5. **The registry** — the live table (see §"Registry schema" below). Ordered: ACTIVE first, then BLOCKED, then IDLE/FORMING, then SHIPPED, then ABANDONED at the bottom.
6. **Composition with other artifacts** — short cross-ref table: when does an entry here trigger a new plan / SESSION LOG entry / promotion event.
7. **Cross-references** — same shape as M1 §12.

---

## ID format

Reuses existing repo conventions where they exist; introduces a new one only for user-domain projects.

| Source | ID pattern | Example | When to use |
|---|---|---|---|
| Phase work | `Phase <n><letter?>` | `Phase 6c` | Structural/experimental work in the BNBUSDT-style sequence |
| Migration milestones | `M<n>` | `M2` | The migration sequence (M0–M5 today; this doc itself = `M2`) |
| Optimization priorities | `P<n>` | `P3` | Performance/code-quality priorities (per [assistant_project.md:446-468](../../../D:/Tradelatest/assistant_project.md)) |
| Config versions | `v<N>_<label>_<YYYY_MM>` | `v2_multi_2026_04` | Production config promotions (per [conventions.md:23](../../../D:/Tradelatest/docs/reference/conventions.md)) |
| User-domain projects | `<DOMAIN>_<SLUG>_<NNN>` SCREAMING_SNAKE_CASE | `VOICE_JARVIS_001`, `TRADELATEST_MIGRATION_001` | Broader projects without (yet) a code footprint |

Rule: a Brick's ID never changes once filed. If a user-domain project later spawns code work, file a child Brick with the code-side ID and link via `parent_brick_id` (the field already named in M1 §11:305).

---

## Status vocabulary (the two axes)

### Epistemic `state` — does this idea check out?

Reuse M1 §8 verbatim ([idea-governance-framework.md:209-216](../../../D:/Tradelatest/docs/architecture/idea-governance-framework.md)). TitleCase in prose, SCREAMING_SNAKE_CASE in machine fields. Values: `Loose · Forming · Tested · Promoted · Demoted · Killed`.

Cross-link to M1 §8 instead of redefining.

### Operational `progress_status` — is anyone actually moving it?

New, defined in this doc. SCREAMING_SNAKE_CASE per [conventions.md:20](../../../D:/Tradelatest/docs/reference/conventions.md). Five values:

| Value | Meaning | Last Reviewed window |
|---|---|---|
| `ACTIVE` | Work happened on this within the last 14 days | ≤ 14d |
| `BLOCKED` | Cannot move until `Blocked By` resolves | n/a |
| `IDLE` | Filed, no decision, no recent work | > 14d, < 60d |
| `SHIPPED` | Reached terminal epistemic state (`Promoted` or merged delivery) | terminal |
| `ABANDONED` | Withdrawn by owner (parallels M1 `Killed` but operational) | terminal |

Transitions are not gated — the user edits the table. The point is visibility, not enforcement (enforcement is M3's job).

---

## Registry schema (the table)

| Column | Type | Source |
|---|---|---|
| `Idea ID` | string per §"ID format" | author |
| `Title` | short prose | author |
| `Owner` | name or handle | author |
| `Domain` | one of `Validation / Lifecycle / Governance / Preservation / Code / Product / Research` | per M1 §4 + extension |
| `State` | M1 epistemic state | author |
| `Progress` | `ACTIVE/BLOCKED/IDLE/SHIPPED/ABANDONED` | author |
| `Last Reviewed` | `YYYY-MM-DD` (plan-header format, [CLAUDE.md §12](../../../D:/Tradelatest/CLAUDE.md)) | author |
| `Next Action` | imperative prose, ≤ 80 chars | author |
| `Blocked By` | Idea ID, external ref, or `—` | author |
| `Evidence Link` | path or URL: plan, SESSION LOG entry, MEMORY file, promotion_log line, commit | author |

Table style matches [cli-matrix.md:5-7](../../../D:/Tradelatest/docs/reference/cli-matrix.md) (left-aligned headers, code-literal keys in backticks, `—` for empty fields).

Seed the table at file-creation time with the Bricks already visible in MEMORY + recent SESSION LOG: `M1` (SHIPPED), `M2` (this doc, ACTIVE), `Phase 6c` (next per MEMORY `project_phase6b_funnel_diagnosis.md`), `M3`/`M4`/`M5` (FORMING/IDLE per the user's roadmap). 5–8 rows is the right starting size.

---

## Composition with existing artifacts

A short table at §6 of the new doc, making the registry's place in the workflow explicit:

| Event | Trigger registry update? | Trigger other artifact? |
|---|---|---|
| New idea filed | Add row, `State=Forming`, `Progress=ACTIVE` | New SESSION LOG entry (per [CLAUDE.md §6](../../../D:/Tradelatest/CLAUDE.md)) |
| Plan written for the idea | Update `Evidence Link` → plan path | New `docs/plans/<slug>.md` file |
| Work stalls > 14d | Flip `Progress` ACTIVE → IDLE | (none) |
| External dependency blocks | Flip `Progress` → BLOCKED, fill `Blocked By` | (none) |
| Validation passes, config promoted | Flip `State` → Promoted, `Progress` → SHIPPED | New `PROMOTED` line in [`promotion_log.jsonl`](../../../D:/Tradelatest/configs/promotion_log.jsonl) |
| Idea withdrawn | Flip `State` → Killed, `Progress` → ABANDONED | SESSION LOG entry documenting why |

The registry never *replaces* the other artifacts — it indexes them. Evidence Link is the back-pointer.

---

## Critical files to modify

| File | Change |
|---|---|
| `docs/governance/user-progress-registry.md` | **CREATE** — new file per the structure above. New directory `docs/governance/` is created by this file's existence; no separate `.gitkeep` needed. |
| `docs/architecture/idea-governance-framework.md` | EDIT §10 (existing implementations) — add a row crediting the registry as the first instantiation of the Brick schema (P5). EDIT §11 (future extensions) — strike or annotate the "Brick schema" bullet now that M2 instantiates a markdown view of it. EDIT §12 (cross-references) — add a link to the new registry. |
| `README.md` | EDIT — add `docs/governance/user-progress-registry.md` to the docs map (existing 4-tier docs map referenced from CLAUDE.md §2). |
| `CLAUDE.md` | EDIT §2 (companion documentation table) — add a row for the new registry between the existing governance/reference rows. |
| `assistant_project.md` | APPEND — one SESSION LOG entry per [§6 mandate](../../../D:/Tradelatest/CLAUDE.md) describing the M2 doc creation. |

No code changes. No config changes. No schema rehash needed.

---

## Verification

Doc-only change — verification is shape + cross-link integrity, not code execution.

1. **Self-link check.** Every `file:line` citation in the new doc resolves. Run a quick grep for each cited path; confirm the line still says what the doc claims.
2. **Round-trip check.** Open the new doc → click each Evidence Link in the seeded rows → land on the cited plan / SESSION LOG entry / MEMORY file. Each link must resolve.
3. **M1 alignment check.** Re-read [idea-governance-framework.md §8 (state grid)](../../../D:/Tradelatest/docs/architecture/idea-governance-framework.md) and confirm the new doc's `State` column uses the same vocabulary, no drift.
4. **Discoverability check.** A fresh `Orient` (per [CLAUDE.md §12](../../../D:/Tradelatest/CLAUDE.md)) must surface the registry. Confirm by reading the updated `README.md` docs map + `CLAUDE.md §2` table — the new row is present and the description is enough to know when to load it.
5. **Five Governance Questions** (per [goal.md](../../../D:/Tradelatest/docs/architecture/goal.md) doctrine + [trigger-vocabulary.md](../../../D:/Tradelatest/docs/architecture/trigger-vocabulary.md) §0):
   - Does this change require new write authority? **No** — markdown-only, human-edited.
   - Does this change cross a `_WRITE_ROOTS` boundary? **No.**
   - Does this require a promotion event? **No** — doc-only.
   - Is this replayable? **Yes** — file is git-tracked; status transitions traceable via `git log` until M4 lands the JSONL companion.
   - Does this preserve the invariants (I1 bidirection, I2 replayability)? **Yes** — registry strengthens I1 by making the idea↔code link explicit per row.

---

## Out of scope (explicitly deferred)

- **JSONL audit trail** for status transitions → M4 (Replayable Decision Journal).
- **Schema-enforced checklist** before adding a Brick → M3 (Mandatory Review Checklist).
- **Automated freshness gate** (e.g. "flag any ACTIVE row whose Last Reviewed > 14d") → M5 (Automated Governance Audits).
- **Code-side Brick object** (Python dataclass implementing M1 §11:305) → not in this milestone; M2 is the markdown view that proves the schema is useful before code is written for it.
- **Backfilling all past Phase findings** as Brick rows → seed with 5–8 current rows; backfill incrementally as Bricks come up for review.
