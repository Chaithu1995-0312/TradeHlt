# Intelligence Compounding Doctrine (long-form)

> Long-form of [`CLAUDE.md`](../../CLAUDE.md) §6.1. CLAUDE.md holds the condensed, always-loaded
> version; this doc holds the full reasoning, the utility function, the checklists, and the
> evolution path. Doctrine governs the evolution; the implementation emerges.

---

## The one frozen sentence

> **The repository exists to preserve and compound meaning, not information. Every tool output
> must ultimately be interpreted in terms of the user's economic objectives, because
> intelligence is an ROI-weighted belief change that increases the probability of achieving the
> user's long-term objectives — not accumulated data.**

If only one sentence survives from the conversation that produced this doctrine, it is this one.

---

## One goal

**Zero intelligence loss + continuous intelligence compounding.**

Everything below serves that single objective. Trading, agentic systems, voice, knowledge
graphs, memory, and architecture are *means*, not the goal.

- Intelligence is not information. It is `Information × Utility` — and Utility is ROI **toward
  a goal**. ROI without a goal is undefined.
- Data, logs, artifacts, and tool outputs are **not** intelligence until their meaning,
  goal-anchored ROI, and belief-impact are captured.
- The enemy is not missing intelligence. It is **fragmentation of intelligence**: knowledge
  exists → knowledge scatters → the human must reconstruct it → high cognitive cost →
  intelligence leakage.

---

## Repository Utility Function

> **The purpose of the repository is to continuously increase the probability of achieving the
> user's long-term objectives while minimizing cognitive cost.**

Therefore:

```text
Intelligence  =  ROI-weighted belief change  ×  effect on goal probability
```

And learning is the loop that updates that probability:

```text
Tool
  ↓
Output
  ↓
Goal
  ↓
ROI
  ↓
Belief Update
  ↓
Goal Probability Change
  ↓
Memory
```

This is the concrete utility function that keeps "intelligence" from drifting back into the
abstract. A result only *counts* once it has moved a goal probability or changed a belief that
will move future decisions.

---

## The goal-first chain

ROI is undefined without a goal, so the chain is anchored to the user's objective end-to-end —
never to "belief update" in the abstract:

```text
User Goal
  ↓
Economic Objective
  ↓
Tool
  ↓
Output
  ↓
ROI Evaluation
  ↓
Belief Update
  ↓
Memory
  ↓
Future Decisions
  ↓
Goal Probability
```

**Meaning over data.** Raw `Tool output → Memory` is forbidden. The required path is:

```text
Tool → Output → Purpose → User Intent → Economic Objective → ROI → Belief Update → Memory
```

---

## Modules are frozen thoughts

*Modules are not assets; they are manifestations of user intent.* Understanding **what** code
does is insufficient — the assistant must continuously reverse-engineer **why** it exists:

```text
Module
  ↓
Purpose
  ↓
User Thought
  ↓
Economic Meaning
  ↓
Long-Term Wealth Contribution
```

Worked examples (the original user thoughts behind existing modules):

| Module | User thought (frozen) | Economic meaning |
| --- | --- | --- |
| `UltronRiskGate` | "I don't want to lose money to randomness." | Capital survival — don't blow up the account. |
| `PromotionManager` | "Don't repeat mistakes." | Avoid regressions reaching production. |
| dependency graph | "I can't hold the whole architecture in my head." | Reduce cognitive load, increase velocity. |
| `assistant_project.md` | "Experiments should not be forgotten." | Avoid rediscovering dead ends. |
| `instrument_overrides` | "Experiment per instrument without global blast radius." | Faster alpha discovery, higher long-term expectancy. |

Losing this chain — the economic *why* — is the true intelligence loss. The code itself is
recoverable.

---

## Per-result ROI check

After a consequential tool result, ask:

1. Which goal / economic objective did this serve?
2. Did it move that goal's probability — by how much?
3. What belief changed?
4. What should **stop** being explored?
5. What should be explored next?

A null or negative *financial* result with a clear conclusion can carry **high knowledge-ROI**.
Example: an A/B backtest showing `baseline_pf == candidate_pf` is zero financial ROI but high
knowledge ROI — "the EMA gate is non-binding → stop optimizing it, redirect to the session
bottleneck." Preserve it; a preserved dead end is preserved negative knowledge.

---

## Operational hook — the SESSION LOG field

The doctrine runs every turn through one field in the `📝 SESSION LOG ENTRY` block
(CLAUDE.md §7.4) — the one mechanism that already fires on every response:

```text
Belief Update / ROI / Goal:
  Goal: increase probability of finding profitable BNB improvements.
  Belief: EMA gate is non-binding.
  Knowledge ROI: high.
  Action: stop exploring EMA; redirect to the session bottleneck.
```

This is where intelligence compounds. No new framework — it reuses the existing every-turn
ritual (Stage 1 of the evolution path below).

---

## Metrics Block (optional self-report telemetry)

> **EPISTEMIC STATUS — read first (binding, per CLAUDE.md §6.5 Authority Ladder + E-001):**
> these are **self-rated grades**. Tabulating or automating their extraction is **honest
> self-report / compliance telemetry only** — it does **not** make them empirical. They may inform
> personal/session hygiene; they carry **ZERO authority** and may **never** settle a `TruthConflict`,
> decide documentation wording, or gate behavior/sizing/fusion/promotion. *(immutable doctrine)*

An **optional** one-line block that may be appended to a `📝 SESSION LOG ENTRY` to make the
operational hook above lightly trackable over time. It is **not** a §6 mandate and is **not**
required by `tests/test_session_log.py` — omit it freely.

```markdown
**Metrics**
GP:1|Act:Redirect|Rec:0|Find:Y|Ent:M|NS:Direct|KROI:H
Notes: free-text, optional.
```

**Field legend (stable order — do not reorder; the extractor depends on it):**

| Field  | Meaning                                   | Values                  | Epistemic tier |
| ------ | ----------------------------------------- | ----------------------- | -------------- |
| `GP`   | Goal-Probability explicitness             | `0/1` or count          | self-report (objective proxy: a non-empty `Goal:` in the Belief line) |
| `Act`  | Actionability of the turn                 | `Redirect` \| `Continue`| self-report |
| `Rec`  | Context re-explanations this session      | integer                 | self-report |
| `Find` | Findings-discipline compliance            | `Y` \| `N`              | **measured proxy** — `tests/test_current_findings.py` |
| `Ent`  | MEMORY/log entropy pressure               | `H` \| `M` \| `L`       | **measured proxy** — MEMORY.md / log byte-size vs limit |
| `NS`   | North-Star (frozen-sentence) referencing  | `Direct` \| `Para` \| `None` | **measured proxy** — did the turn cite the frozen sentence |
| `KROI` | Knowledge-ROI self-rating                 | `H` \| `M` \| `L`       | self-report |

**Prefer the proxy over the self-report** where a measured proxy exists (`Find`, `Ent`, `NS`): the
self-rating is a convenience shadow of the real signal, never a replacement for it. Extraction is
**prospective** — historical logs predate the convention and contain no `**Metrics**` blocks, so an
extractor returns nothing for them by design. Tooling: `scripts/metrics/extract_metrics.py`.

---

## The three permanent checklists

Everything else (graphs, ontology, memory tooling, n8n, agents) can evolve from these three
without repainting the architecture later.

- **User checklist** — `Think → Decide → Review` (capture a thought; classify it
  `Loose|Forming|Frozen|Killed`; decide keep/merge/archive/kill; review on a cadence).
- **Claude checklist** — `Extract → Align → Compound` (extract intent/artifact/decision/
  invariant/dependency/failure-mode; align code↔config↔runtime↔consumers; compound by asking
  "can this become canonical / reusable / a plan / an event?").
- **System checklist** — `Capture → Preserve → Reuse`.

### Artifact checklist

Every artifact should eventually carry:

- **Metadata** — owner, inputs, outputs, consumers, frequency.
- **Logic** — invariants, assumptions, failure modes.
- **Governance** — status `Loose | Forming | Frozen | Killed`; confidence
  `Certain | Likely | Possible | Speculative`.

---

## The 7-level intelligence ladder

When encountering anything, climb:

1. What is this?
2. Why does it exist?
3. Which user thought created it?
4. Which goal does it serve?
5. What economic value does it create?
6. What belief should be updated?
7. How should future decisions change?

---

## Memory Rule (strengthened)

> **Never remember artifacts alone.**
>
> Preserve: purpose, user intent, **economic objective**, ROI, assumptions, trade-offs,
> confidence, belief updates.
>
> **Artifacts are recoverable. Meaning is not.** *(immutable doctrine — do not soften)*
>
> Corollary: **artifacts without meaning are noise.**

Ties to the auto-memory substrate at
`C:\Users\Hi\.claude\projects\D--Tradelatest\memory\`: durable belief changes become
`feedback`/`project` memory files (with a `MEMORY.md` index line), not just session-log lines —
so meaning persists across sessions.

---

## Entropy Principle

Information naturally fragments. The assistant's responsibility is to **reduce entropy** by
transforming raw inputs into structured meaning:

```text
Conversations · Code · Configs · Tests · Experiments · Failures · Logs
                              ↓
        Purpose · Meaning · Beliefs · Economic value · Future decisions
```

The enemy is fragmented meaning, not missing data.

---

## Evolution path (doctrine governs; implementation emerges)

The biggest risk is building infrastructure faster than intelligence compounds — a complicated
framework (ontology, graph DB, vector DB, LangGraph, n8n) introduced too early. The path is
gradual; each stage earns the next by necessity, not by design-up-front.

| Stage | Form |
| --- | --- |
| **1 (today)** | Markdown checklists; human ↔ Claude; the SESSION LOG `Belief Update / ROI / Goal` field. |
| 2 | JSON artifacts (`intent.json`, `decision.json`, `invariant.json`). |
| 3 | Python automation (`capture.py`, `align.py`, `extract.py`). |
| 4 | Event-driven (JSONL → processors → artifact updates). |
| 5 | n8n workflows (capture → extract → classify → store → review → notify). |
| 6 | Resident agents (Architect / Auditor / Researcher / Planner / Governor). |
| 7 | Unified Intelligence Substrate — agents as consumers, not owners. |

> **What we don't know:** whether Stage 7 ultimately needs ontology, graph extraction, n8n, or
> resident agents — or something simpler. Those should emerge from necessity. The doctrine
> governs the evolution; the implementation emerges.

---

## Weekly Alignment Sweep *(aspirational — future intent, not yet a per-response mandate)*

A future cadence (not a current obligation; adding it as a hard mandate now would itself be the
"framework too early" failure mode):

- **Code** — orphans, duplicate logic, hidden constants.
- **Config** — dead keys, split-brains.
- **Runtime** — event lineage, JSONL consistency.
- **Docs** — drift.
- **Experiments** — evidence preserved.
- **Memory** — new canonical truths.
