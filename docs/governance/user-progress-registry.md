# user-progress-registry.md

> **Purpose:** Single-screen view of every Brick (idea, milestone, project) that is
> currently *live* in Tradelatest — what state it's in, who owns it, what the next move
> is, what is blocking it, where its evidence lives. The framework that *governs* ideas
> is [`idea-governance-framework.md`](../architecture/idea-governance-framework.md)
> (Gov-M1, the rules). This file is the *operational* view: which ideas are actually
> moving, which are stalled, which are abandoned.
>
> Anchored to `v2_multi_2026_04` — the active production config on the `patch` branch (per
> `configs/production/ACTIVE_VERSION` + `docs/current-findings.md` **F-016**, which supersedes the
> earlier F-007 "v4 active" claim: `v4_multi_2026_06` was promoted on a separate post-TP3 code line
> and is **not loadable on `patch`**. Version truth is branch-scoped).
> Markdown-only; the append-only event log is deferred
> to **Gov-M4 — Replayable Decision Journal** ([§7](#7-cross-references)).

---

## 1. What this is, what it is not

This is the operational index. It instantiates a subset of the Brick schema flagged in
[`idea-governance-framework.md §11`](../architecture/idea-governance-framework.md) as
the *first* human-readable view of live work. It is **the current-state table** — open
it to answer "what's open right now, who owes the next move, what's stuck."

It is **not**:
- The framework itself — that's Gov-M1, the rules ([`idea-governance-framework.md`](../architecture/idea-governance-framework.md)).
- The narrative — that's the SESSION LOG ([`assistant_project.md`](../../assistant_project.md), per [CLAUDE.md §6](../../CLAUDE.md)).
- The audit trail — that's the future `governance/framework_review_log.jsonl` (Gov-M4, [`idea-governance-framework.md §11`](../architecture/idea-governance-framework.md)).
- The plan store — that's [`docs/plans/`](../plans/).

It sits *between* Gov-M1 and the SESSION LOG: Gov-M1 says what's allowed; SESSION LOG records
what happened; this file says **what is happening now**.

---

## 2. How to use it (the ritual)

- **File a Brick** when an idea is named in conversation or a plan is drafted. Status starts at `State=Forming`, `Progress=ACTIVE`.
- **Update `Last Reviewed`** every time you act on the row (touch the plan, run an experiment, write a SESSION LOG entry citing it). Use `YYYY-MM-DD`.
- **Flip to `BLOCKED`** the moment progress stops on an external dependency. Fill `Blocked By`.
- **Flip to `IDLE`** when 14+ days pass with no movement and no blocker. Visible signal that the Brick is forgotten, not blocked.
- **Flip to `SHIPPED`** only when the epistemic `State` reaches `Promoted` (or the deliverable is merged). Keep the row — terminal rows stay for replay.
- **Flip to `ABANDONED`** when the owner withdraws the idea. Add a SESSION LOG entry documenting *why* (per Gov-M1 §7 demote/kill rationale).
- **Never delete rows.** The registry is append-discipline — terminal rows move to the bottom but stay readable for `Orient` and rationale replay.

---

## 3. ID format

Reuses existing repo conventions where they exist; one new pattern for user-domain
projects.

| Source | ID pattern | Example | When to use |
|---|---|---|---|
| Phase work | `Phase <n><letter?>` | `Phase 6c` | Structural / experimental work in the BNBUSDT sequence |
| Governance milestones | `Gov-M<n>` | `Gov-M2` | Idea-governance sequence (Gov-M1 framework → Gov-M5 audits; this file = `Gov-M2`) |
| Trading-arch milestones | `Trd-M<n>` | `Trd-M3` | Engine migration sequence (Trd-M0 doctrine → Trd-M6 scenario-aware; see [`roadmap.md`](../architecture/roadmap.md)) |
| Optimization priorities | `P<n>` | `P3` | Performance / code-quality priorities (per [`assistant_project.md`](../../assistant_project.md)) |
| Config versions | `v<N>_<label>_<YYYY_MM>` | `v2_multi_2026_04` | Production config promotions (per [`conventions.md`](../reference/conventions.md)) |
| User-domain projects | `<DOMAIN>_<SLUG>_<NNN>` SCREAMING_SNAKE_CASE | `VOICE_JARVIS_001` | Broader projects without (yet) a code footprint |

**Rule:** a Brick's ID never changes once filed. If a user-domain project later spawns
code work, file a child Brick with the code-side ID and reference the parent in
`Blocked By` (or `Title`) until the schema-level `parent_brick_id` field arrives with
Gov-M3+Gov-M4.

**Documented supersession (2026-06-01).** The registry's milestone IDs were renamed
`M1..M5 → Gov-M1..Gov-M5` (and the trading-arch milestones to `Trd-M0..Trd-M6`) to remove
the cross-track `M<n>` ambiguity. Per the "ID never changes once filed" rule this is recorded
as a **supersession**, not a silent mutation — the same continuity discipline as the
telemetry "no field removed without a documented superseding field" rule. The new
`Gov-`/`Trd-` IDs are canonical going forward; the bare `M<n>` forms are their superseded
aliases. The rule above (a Brick's ID never changes once filed) holds from this point.

---

## 4. Status vocabulary (two axes)

A Brick has **two** statuses. They answer different questions; both are needed.

### 4.1 Epistemic `State` — does this idea check out?

Reused verbatim from [`idea-governance-framework.md §8`](../architecture/idea-governance-framework.md). TitleCase in the registry table; SCREAMING_SNAKE_CASE in any
future machine field. Values: `Loose · Forming · Tested · Promoted · Demoted · Killed`.

Do **not** redefine these here. Gov-M1 §8 is the only definition. If a value needs
revising, edit Gov-M1 §8 first; this file follows.

### 4.2 Operational `Progress` — is anyone actually moving it?

Defined here. SCREAMING_SNAKE_CASE per [`conventions.md`](../reference/conventions.md).

| Value | Meaning | `Last Reviewed` window |
|---|---|---|
| `ACTIVE` | Work happened on this within the last 14 days | ≤ 14d |
| `BLOCKED` | Cannot move until `Blocked By` resolves | n/a |
| `IDLE` | Filed, no decision, no recent work | > 14d, < 60d |
| `SHIPPED` | Reached terminal epistemic state (`Promoted` or merged delivery) | terminal |
| `ABANDONED` | Withdrawn by owner (parallels Gov-M1 `Killed` but operational) | terminal |

Transitions are **not gated** at this milestone — the owner edits the table. The point
is visibility, not enforcement. Enforcement is Gov-M3 (Mandatory Review Checklist).

The two axes can drift apart, and that drift is *informative*:
- `Promoted` + `IDLE` → shipped Brick that nobody extends → stale or done well.
- `Forming` + `BLOCKED` → idea waiting on you; nudge the blocker.
- `Tested` + `IDLE` → measurement done, no decision filed → governance debt.

---

## 5. The registry

Ordered: `ACTIVE` → `BLOCKED` → `IDLE` → `SHIPPED` → `ABANDONED`. Terminal rows live at
the bottom but stay for `Orient` and rationale replay.

| `Idea ID` | Title | Owner | Domain | `State` | `Progress` | `Last Reviewed` | Next Action | `Blocked By` | Evidence Link |
|---|---|---|---|---|---|---|---|---|---|
| `Gov-M2` | User Progress Registry | user | Governance | Forming | ACTIVE | 2026-06-01 | Commit this doc + wire Gov-M1/README/CLAUDE.md cross-links | — | [plan](../plans/one-remaining-gap-eventual-pixel.md) |
| `Phase 5a` | Decision-threshold sweep | user | Validation | Forming | ACTIVE | 2026-05-30 | Run `tier_2_threshold ∈ [0.44..0.60]` sweep; find minimum where approval_rate < 95% | — | [MEMORY: project_phase5a_plan.md](../../C%3A%5CUsers%5CHi%5C.claude%5Cprojects%5CD--Tradelatest%5Cmemory%5Cproject_phase5a_plan.md) |
| `Phase 6c` | Session-config ROI sweep | user | Validation | Forming | ACTIVE | 2026-06-02 | Sweep done (BNBUSDT 15→35 @ PF 2.54). Next: instrument-scoped promotion via new `allowed_sessions_overrides` mechanism → ConfigValidator → PromotionManager | — | [MEMORY: project_phase6b_funnel_diagnosis.md](../../C%3A%5CUsers%5CHi%5C.claude%5Cprojects%5CD--Tradelatest%5Cmemory%5Cproject_phase6b_funnel_diagnosis.md) |
| `Gov-M3` | Mandatory Review Checklist | user | Governance | Forming | IDLE | 2026-06-01 | Design schema-enforced checklist fields for Brick admission (per Gov-M1 §3 P4 gap) | `Gov-M2` | [Gov-M1 §3 P4](../architecture/idea-governance-framework.md) |
| `Gov-M4` | Replayable Decision Journal | user | Preservation | Forming | IDLE | 2026-06-01 | Design `governance/framework_review_log.jsonl` schema + status-transition log for this registry | `Gov-M3` | [Gov-M1 §11](../architecture/idea-governance-framework.md) |
| `Gov-M5` | Automated Governance Audits | user | Governance | Forming | IDLE | 2026-06-01 | Spec the freshness check (e.g. flag ACTIVE rows where `Last Reviewed > 14d`) + I1 bidirection audit (per Gov-M1 §11) | `Gov-M4` | [Gov-M1 §11](../architecture/idea-governance-framework.md) |
| `VOICE_JARVIS_001` | Voice-driven Jarvis interface | user | Product | Loose | IDLE | 2026-06-01 | Architecture review; pick voice stack | Voice stack selection | — |
| `Trd-M6` | Scenario-Aware Decisioning | user | Trading-arch | Forming | BLOCKED | 2026-06-02 | Operator: cut over V3 (validated-ready); then upstream detection/RETEST-supply for ≥40 throughput — Trd-M6 stays downstream (re-eval #7 2026-06-02) | operator V3 cutover (ACTIVE_VERSION flip); upstream detection supply (session ceiling=35<40); per-instrument edge (ETH/BTC) — none are Trd-M6 | [roadmap §3](../architecture/roadmap.md) |
| `Gov-M1` | Idea Governance Framework | user | Governance | Promoted | SHIPPED | 2026-06-01 | (terminal — extend only via Verification Gate cycle per Gov-M1 §9) | — | [doc](../architecture/idea-governance-framework.md) |
| `v2_multi_2026_04` | Production config (**active on `patch`**) | user | Lifecycle | Promoted | SHIPPED | 2026-04-30 | (active on `patch`; `v4_multi_2026_06` was promoted on a separate post-TP3 line, not loadable here — F-016 supersedes F-007) | — | [ACTIVE_VERSION](../../configs/production/ACTIVE_VERSION) · [promotion log](../../configs/promotion_log.jsonl) |
| `v4_multi_2026_06` | Production config (post-TP3 line only — NOT active on `patch`) | user | Lifecycle | Promoted | SHIPPED | 2026-06-02 | (promoted on a newer post-TP3 code line; needs TP3 schema absent from `patch`, so not loadable here — F-016; row kept for replay per §6.2) | — | [promotion log](../../configs/promotion_log.jsonl) |

Seed size is intentionally small (10 rows). Backfill prior Phase findings (0, 1, 2b, 3b,
4b, 6) on demand — when one comes up for review, add the row, not before.

---

## 6. Composition with other artifacts

The registry never *replaces* the other artifacts — it indexes them. Evidence Link is
the back-pointer.

| Event | Registry update | Other artifact |
|---|---|---|
| New idea filed | Add row, `State=Forming`, `Progress=ACTIVE` | New SESSION LOG entry (per [CLAUDE.md §6](../../CLAUDE.md)) |
| Plan written for the idea | Update `Evidence Link` → plan path | New `docs/plans/<slug>.md` |
| Work stalls > 14d | Flip `Progress` ACTIVE → IDLE | (none) |
| External dependency blocks | Flip `Progress` → BLOCKED; fill `Blocked By` | (none — name the blocker inline) |
| Validation passes, config promoted | Flip `State` → Promoted, `Progress` → SHIPPED | New `PROMOTED` line in [`promotion_log.jsonl`](../../configs/promotion_log.jsonl) |
| Idea withdrawn | Flip `State` → Killed, `Progress` → ABANDONED | SESSION LOG entry documenting *why* (Gov-M1 §7) |

**Five Governance Questions for any registry edit** (per [`goal.md`](../architecture/goal.md) + [`trigger-vocabulary.md §0`](../architecture/trigger-vocabulary.md)):
edits are doc-only, never cross `_WRITE_ROOTS`, never auto-promote a config, are
git-replayable, and strengthen I1 (the idea↔code link is now explicit per row).

---

## 7. Cross-references

- [`docs/architecture/idea-governance-framework.md`](../architecture/idea-governance-framework.md) — **the framework this registry instantiates** (Gov-M1; the rules, the 7 pillars, the Brick state grid §8).
- [`docs/architecture/goal.md`](../architecture/goal.md) — north-star priority order; the registry inherits it.
- [`docs/architecture/trigger-vocabulary.md`](../architecture/trigger-vocabulary.md) — `Orient` loads this file alongside the SESSION LOG and MEMORY index.
- [`docs/architecture/llm-governance-layer.md`](../architecture/llm-governance-layer.md) — write-authority boundary; the registry is human-edited at this milestone.
- [`docs/architecture/replay-governance.md`](../architecture/replay-governance.md) — run-level replay; rationale-level replay extends through this file + Gov-M4.
- [`docs/reference/governance.md`](../reference/governance.md) — config-promotion implementation of Gov-M1 P3 (the existing promotion path); SHIPPED rows here cite its `promotion_log.jsonl`.
- [`docs/reference/conventions.md`](../reference/conventions.md) — naming + casing the ID format honors.
- [`docs/current-findings.md`](../current-findings.md) — the **living Repository Truths** (validated conclusions / reversals / open questions). Distinct axis from this registry: findings record *what we now know*, this registry records *what is in flight*. A `SHIPPED`/`Promoted` Brick often produces a finding; a finding may set a Brick's `Next Action`. (Note: finding `F-016` — superseding `F-007` — confirms this registry's `v2_multi_2026_04` anchor is **correct** on `patch`; `v4_multi_2026_06` applies only to the post-TP3 code line.)
- [`assistant_project.md`](../../assistant_project.md) — the SESSION LOG; every registry edit is accompanied by an entry there.
- [`configs/promotion_log.jsonl`](../../configs/promotion_log.jsonl) — the existing audit trail SHIPPED rows back-reference.
- [`CLAUDE.md §2`](../../CLAUDE.md) — companion documentation table that surfaces this file when a task touches progress / governance.
