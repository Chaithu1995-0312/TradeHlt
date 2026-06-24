# User-Intention Trace — Era 6: Self-Governing Legibility

> **Point-in-time snapshot, not a living doc.** Captured 2026-06-01 from the SESSION LOG
> (`assistant_project.md`, through 2026-06-01) and the two milestones that post-date the prior
> trace. **Continues** `user-intention-trace-2026-05-30.md` (Eras 1–5) — read that first for the
> foundation. For current truth use the living docs: operating rules → `CLAUDE.md`; north-star →
> `docs/architecture/goal.md`; topic index → `docs/topics/readme.md`.
>
> **Why this exists:** the prior trace ended at Era 5 (2026-05-30). Two moves since — the
> idea-governance framework (M1) and the topic-visibility layer — add a sixth era that reframes
> the throughline. This snapshot records it.

---

## Part 1 — Era 6: Self-governing legibility (2026-05-31 → 2026-06-01)

The prior trace pinned five eras. Era 6 is the one that closes the loop on the fourth value.

| Era | Window | Underlying question | Produced |
|---|---|---|---|
| 1 · Foundation & legibility | 04-10→04-22 | *Make it governable before growing it* | one config of record, promotion gate, master-context docs |
| 2 · Stabilisation & correctness | 04-25→04-30 | *Trust the numbers first* | 0-failure test net, RR data-integrity audit, all-zero-feature fix |
| 3 · Multi-strategy expansion | 04-30→05-01 | *Scale CRT → governed portfolio* | 10 strategies, orchestrator, kill-switch, UAT |
| 4 · Empirical tuning | 05-12→05-30 | *Let measured data, not hypotheses, drive* | BNBUSDT Phase 0→6b — every leading hypothesis died on contact with telemetry |
| 5 · LLM-context-economy migration | 05-28→05-30 | *Make the codebase ownable by an LLM* | M0–M5 doctrine, Trigger Vocabulary, goal.md, code-map |
| **6 · Self-governing legibility** | **05-31→06-01** | ***Make the system explain and audit itself*** | **idea-governance framework (M1); topic-visibility layer + §6.1 sync mandate** |

Two artifacts define Era 6:

1. **Idea-governance framework (M1)** — `docs/architecture/idea-governance-framework.md` (SESSION LOG 2026-06-01 00:43; plan `docs/plans/this-is-a-valuable-pure-flurry.md`). Named the implicit system: ideas (Phase experiments, hypotheses, model variants, agent intents) lived scattered across MEMORY / plans / code / configs / JSONL / commits with **no typed object and no named lifecycle**. The framework gives drift a name (7 pillars, Brick lifecycle, evidence tiers) and a self-applying Verification Gate so it detects its own drift instead of becoming ceremony.

2. **Topic-visibility layer (foundation)** — `docs/topics/` (readme index + `_template.md` + seed docs `context-report.md`, `crt-spine.md`) + `CLAUDE.md §2.0 Doc Reference Tree`, **§6.1 Topic Sync Mandate**, §12 `Sync` trigger, `tests/test_topic_docs.py`. One human-language file per *concept* (code covered ↔ tests ↔ validations ↔ standing discussion), kept in sync with code **every working response** by §6.1 (touch only the affected file — token-aware). Modeled on the existing **Context Report** button (control-plane 🧠 → AST `extract_code_context()` → Claude Haiku → structured JSON), but keyed on a *topic* instead of a *run*.

---

## Part 2 — How the throughline matured

The prior trace named four constants — **deterministic/replayable · governed · empirically-validated · LLM-ownable** — unified by the five governance questions. Era 6 adds no fifth value; it **closes the loop on the fourth**:

- Eras 1–5 made the system *operable* by an LLM from curated context.
- Era 6 makes that curated context **keep itself true** — docs that can't go stale, the same way a config can't reach production without an audit trail.

So the meta-intention evolved:

```
Era 1  "document the system"
   ↓
Era 5  "make an LLM able to own it from minimal context"
   ↓
Era 6  "make the documentation self-maintaining, so ownership can't decay"
```

The signal in the recent requests is not *more docs* — it is **docs with a mechanism that prevents drift** (automatic on every response, backed by a test), exactly parallel to the §6 SESSION LOG mandate and the promotion APPROVE gate.

---

## Part 3 — The repeating fingerprint

Three habits recur identically across every era (tuning a session filter or restructuring CLAUDE.md):

1. **Name the implicit before extending it.** Phase 0 named the real bottleneck before touching params; the framework named idea-governance; topics name concepts. No building on the unnamed.
2. **Measure / verify first, accept the verdict.** retest-depth, score-inversion, age-decay — all invalidated and dropped. On 06-01 the user required confirmation that a failing test was *pre-existing*, not hand-waved.
3. **Mechanism over discipline.** Not "we'll remember to update docs" but **automatic on every response** (§6.1) + a test — like §6 SESSION LOG and the APPROVE gate.

---

## Part 4 — Open intentions (current)

Carried from the prior trace's Part 5 + Era-6 additions:

- **ROI: governance gate vs optimisation target** (latter needs a documented deviation flag).
- **ROI session-window sweep** — add `asia` to `allowed_sessions` (Phase 6b: session filter = #1 ROI lever).
- **Phase 5a** — `tier_2_threshold` selectivity sweep `[0.44..0.60]`.
- **M3** — kill `live_engine_hook` singletons → injection.
- **First FrameworkReview** — run the idea-governance framework on itself (its first execution).
- **Topic Report button (next phase)** — generalize `extract_code_context()` (run→topic) to auto-write `docs/topics/<topic>.md`.
- **Topics ↔ Bricks reconciliation** — the framework (Bricks) and the topics layer (concepts) are two implementations of the same idea (governed, auditable legibility) at different grain. Decide: keep parallel, or make a topic a *kind of* Brick so there's one lifecycle. *(Unresolved — surfaced 2026-06-01.)*

---

## Sources

- `assistant_project.md` SESSION LOG (entries through 2026-06-01, incl. 06-01 00:43 framework + 06-01 topic-visibility entries).
- `docs/analysis/user-intention-trace-2026-05-30.md` (Eras 1–5, the foundation this continues).
- `docs/architecture/idea-governance-framework.md`; `docs/plans/this-is-a-valuable-pure-flurry.md` (M1).
- `docs/topics/readme.md`, `_template.md`, `context-report.md`, `crt-spine.md`; `CLAUDE.md §2.0 / §6.1 / §12`; `tests/test_topic_docs.py`.
- Corroborating memory: `project_topics_visibility_layer`, `project_phase{0..6b}_findings`.
