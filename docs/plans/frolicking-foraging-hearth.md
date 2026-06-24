# Adopt Gov-/Trd- Milestone Prefixes Across Living Docs + Code Comments

> Created: 2026-06-01 · Updated: 2026-06-01 · Milestone: doc/naming convention (cross-track)

## Context

Two milestone tracks share the labels `M1`–`M5` (governance: Idea Governance Framework
→ Automated Audits; trading: Telemetry → LLM Hardening). A bare "M3" is ambiguous. The
previous session created [`docs/architecture/roadmap.md`](../../D:/Tradelatest/docs/architecture/roadmap.md)
which *states the rule* ("never cross-reference by number alone") but left the underlying
docs/code using bare `Mn`. **Decision (user, 2026-06-01): propagate `Gov-`/`Trd-`
prefixes everywhere it matters, and adopt them as the new canonical IDs.**

A blind find/replace is unsafe — `\bM[0-6]\b` matches **278 occurrences across 22 docs +
11 code files**, of which three distinct classes exist:
- ✅ **Real milestone refs** — get prefixed.
- ⛔ **Timeframe literals** — `historical_fetcher.py "M1": mt5.TIMEFRAME_M1` / `"M15"`,
  `strategy_result.py:59 "M1 / M5 / M15"`, `control_plane/registry.py:230 "raw M1 CSVs"`.
  Renaming these **breaks the candle-timeframe dictionaries**. NEVER touch.
- 📜 **Historical/point-in-time records** — `docs/analysis/*`, superseded plan snapshots,
  the append-only SESSION LOG history in `assistant_project.md`. Rewriting falsifies the
  preservation record (I2/P7 invariant). NEVER touch.

**User decisions applied:** scope = living docs + code *comments/docstrings only*; the
prefixes become **canonical IDs** (registry §3 updated + documented supersession). The
exact M6 validation-floor threshold stays the operator's call (no doc change).

**Intended outcome:** every *living* milestone reference is track-qualified; the registry's
ID convention is updated; timeframe literals and historical records are untouched; no code
logic changes.

## The disambiguation method (applied per occurrence)

For each in-scope match, read surrounding context and classify:
- **Governance** → `Gov-Mn` — only in `idea-governance-framework.md`,
  `user-progress-registry.md`, and the two governance rows of `CLAUDE.md §2`.
- **Trading** → `Trd-Mn` — everywhere else (migration plan, all other architecture docs,
  `assistant_project.md` doctrine block, code comments).
- **Timeframe/Other** → leave untouched.

Track = which roadmap.md section the milestone lives in (§1 = Gov, §2 = Trd).

## Deliverables

### D1 — Trading-track refs → `Trd-Mn`
**Living docs** (milestone refs only): `docs/plans/claude-architecture-migration-eager-wreath.md`
(M0–M6); `docs/architecture/goal.md` (M0–M5, ~L133–135); `docs/architecture/trigger-vocabulary.md`
("M0–M5 migration index/sequence", ~L11/24/68/135); `docs/architecture/service-boundary-map.md`
(M1–M5); `docs/architecture/event-taxonomy.md` (M1/M2); `docs/architecture/replay-governance.md`
(M1); `docs/architecture/llm-governance-layer.md` (M5); `docs/architecture/codebase-state-map.md`
(M1, L118); `docs/architecture/services/decision-spine.md`; `assistant_project.md`
**doctrine block only** (the Migration sequencing index M0–M6 — NOT the SESSION LOG below it).

**Code comments/docstrings only** (never string literals): `src/runtime/backtest_v2.py`,
`src/config_layer/crt_engine_v2.py`, `src/cognitive/cognitive_bus.py`, `src/utils/trade_logger.py`,
`src/utils/sweep_trace_logger.py`, `src/utils/episode_summarizer.py`, `src/core/engine_runner.py`,
`src/events/event_fabric.py` (L66–67). Pattern: `# M1 …` → `# Trd-M1 …`, `"""M2 dual-write …`
→ `"""Trd-M2 dual-write …`.

### D2 — Governance-track refs → `Gov-Mn`
`docs/architecture/idea-governance-framework.md` (self-ref "M1" + refs M2/M3/M4/M5);
`docs/governance/user-progress-registry.md` (prose refs + §5 table — see D3);
`CLAUDE.md §2`: idea-governance row `(M1)`→`(Gov-M1)`, user-progress row `(M2)`→`(Gov-M2)`.

### D3 — Registry ID canonicalization (`user-progress-registry.md`)
- **§3 ID-format table:** split the single ambiguous `Migration milestones | M<n> | M2`
  row into two: `Governance milestones | Gov-M<n> | Gov-M2` and
  `Trading-arch milestones | Trd-M<n> | Trd-M3`. Reword the "M0–M5 today; this file = M2"
  note to "this file = Gov-M2".
- **Immutability note:** under §3, add one line recording the one-time governed rename
  (`M1..M5 → Gov-M1..Gov-M5`) as a *documented supersession* — honoring "a Brick's ID
  never changes once filed" via supersession (parallel to the telemetry-continuity rule),
  not silent mutation.
- **§5 registry table:** `Idea ID` column `M1→Gov-M1 … M5→Gov-M5`; `Blocked By`
  `M2→Gov-M2`, `M3→Gov-M3`. Phase / config-version rows unchanged.

### D4 — roadmap.md tidy (already prefixed this session)
Light pass only: confirm §0 rule wording stays canonical; bare slash-shorthand like
`Gov-M3/M4/M5` is acceptable (track-qualified by the prefix). No structural change.

## Strict exclusions (never touch)
- **Timeframe literals:** `src/data_ingestion/historical_fetcher.py`,
  `src/strategies/strategy_result.py:59`, `src/control_plane/registry.py:230`, and any
  `M15`/`H1`/`H4`/`D1` token.
- **Historical docs:** `docs/analysis/*`; all `docs/plans/*` **except** the active
  migration plan + this plan file; the SESSION LOG history in `assistant_project.md`.
- `docs/reference/conventions.md` — verified to contain **no** milestone refs.
- No code logic, no config edits/rehash/promotion.

## Verification
1. `grep -rn "\bM[0-6]\b"` across in-scope living docs + the 8 code files → every
   remaining *unprefixed* match is a timeframe literal or lives in an excluded file; **zero
   bare milestone refs remain in living docs / code comments.**
2. `git diff -- src/data_ingestion/historical_fetcher.py src/strategies/strategy_result.py src/control_plane/registry.py docs/analysis/` → **empty** (timeframe literals + historical docs untouched).
3. `user-progress-registry.md` §3 shows the two split ID rows + supersession note; §5
   `Idea ID`/`Blocked By` use `Gov-Mn`; Phase/config rows unchanged.
4. `CLAUDE.md §2` idea-gov/registry rows read `Gov-M1`/`Gov-M2`; `roadmap.md §0` rule intact.
5. `pytest tests/test_topic_docs.py` (+ any plan-header test) → still green (rename is
   cosmetic to the doc-structure floor).
6. Append a `📝 SESSION LOG ENTRY` to `assistant_project.md` recording the convention adoption.

## Out of scope
- Timeframe literals, historical/point-in-time docs, SESSION LOG history, `conventions.md`.
- Any engine/decision/config behavior change. This is a naming-convention pass only.
