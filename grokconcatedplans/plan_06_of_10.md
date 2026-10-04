# Concatenated session plans — part 6 of 10

Source directory: `docs/plans/`
Files in this part: 7

## Contents

1. `list-every-numeric-literal-mighty-wave.md` (4264 bytes)
2. `one-remaining-gap-eventual-pixel.md` (11022 bytes)
3. `open-defect-recovery-parsed-marble.md` (7996 bytes)
4. `probability-surface-advisory.md` (4040 bytes)
5. `readme.md` (13933 bytes)
6. `refer-the-pure-docs-sunny-lagoon.md` (11253 bytes)
7. `regime-aware-fusion-closed-marking-glistening-river.md` (20269 bytes)


================================================================================
SOURCE_FILE: docs/plans/list-every-numeric-literal-mighty-wave.md
SOURCE_BYTES: 4264
PART: 6/10 FILE 1/7
================================================================================

> Created: 2026-06-06 · Updated: 2026-06-06 · Milestone: Trd-M5 / Gov-M2

# Plan: Externalize High-Leverage Hard-Coded Literals

## Context

Audit confirmed ~75% of runtime parameters are already config-driven. Only ~20 literals remain hard-coded with material outcome impact. This plan converts the top 5 highest-leverage items only. Blanket externalization has poor ROI; backtest sensitivity must be measured before touching others.

Aligns with F-003 (throughput is the bottleneck) — fusion consensus rules directly control trade frequency and selection quality.

---

## Scope: 5 Items Only

| Priority | Literal | File:Line | Current Value | Config Key to Add | Config Section |
|----------|---------|-----------|---------------|-------------------|----------------|
| 1 | `min_signals` (consensus) | `src/core/fusion_engine.py:731` | `2` | `min_consensus_signals` | `fusion_engine` |
| 2 | `min_agreement` (consensus) | `src/core/fusion_engine.py:741` | `0.60` | `min_consensus_agreement` | `fusion_engine` |
| 3 | Score component weights | `src/engines/scoring_engine.py:44` | `0.35/0.25/0.20/0.20` | `score_component_weights` | `crt_engine` |
| 4 | `_FALLBACK_TOP_N` | `src/core/decision_engine.py:38` | `3` | `fallback_top_n` | `decision_engine` |
| 5 | `PROMOTION_MARGIN` | `src/core/model_registry.py:40` | `0.02` | `model_promotion_margin` | `governance` |

**Do NOT touch:** normalizer window (1000), threshold window (1000), dataset sample gates — these require deeper impact analysis first.

---

## Implementation Steps

### Step 1 — Add config keys to active production config (`configs/production/v4_multi_2026_06.json`)

For each of the 5 literals, add a key to the appropriate section. Also add to `v1_multi_2026_03.json` (baseline) with same values to keep configs in sync.

New keys:
```json
// fusion_engine section
"min_consensus_signals": 2,
"min_consensus_agreement": 0.60,

// crt_engine section
"score_component_weights": [0.35, 0.25, 0.20, 0.20],

// decision_engine section
"fallback_top_n": 3,

// governance section
"model_promotion_margin": 0.02
```

### Step 2 — Wire each literal to read from config

**fusion_engine.py:731** — replace `min_signals=2` with `min_signals=self._cfg.get("min_consensus_signals", 2)`  
**fusion_engine.py:741** — replace `min_agreement=0.60` with `min_agreement=self._cfg.get("min_consensus_agreement", 0.60)`  
**scoring_engine.py:44** — replace tuple literal with `self._weights = cfg.get("score_component_weights", [0.35, 0.25, 0.20, 0.20])`  
**decision_engine.py:38** — replace `_FALLBACK_TOP_N = 3` with value loaded from config at init  
**model_registry.py:40** — replace `PROMOTION_MARGIN = 0.02` with value loaded from governance config section  

Follow `_require()` / `get_prod_section()` pattern per `docs/reference/example-service.py`. No magic numbers remain in Python.

### Step 3 — Re-hash the config

```
python scripts/maintenance/_compute_hash.py
```

### Step 4 — Run regression suite

```
pytest tests/ -x -q
```

Confirm: no test failures, no drift in existing backtest metrics.

### Step 5 — Backtest sensitivity (before any value changes)

Run a baseline backtest with values held at current defaults, then vary each new config key ±1 step to measure impact on trade count and PF. Record in SESSION LOG. Only then tune values.

---

## What NOT to Convert (Frozen by Doctrine)

`0.0/1.0` clamp bounds · EMA `2.0/(period+1)` formula · weight-sum tolerance `0.01` · direction midpoint `0.5` · Fibonacci `1.618` reset · `1e-9` epsilon · confidence mapping `abs(s-0.5)*2.0`

---

## Verification

1. `pytest tests/ -x -q` — all green
2. Spot-check: run a single backtest and confirm `score_component_weights` from config is used (add a debug log or assert in test)
3. Confirm `promotion_manager.py` reads `model_promotion_margin` from config instead of the constant
4. Config hash updated — `python scripts/maintenance/_compute_hash.py` exits 0

---

## Citation Sync (§6.3)

After editing `model_registry.py` and `scoring_engine.py`, check `docs/architecture/citation-map.generated.md` for any `path:line · Symbol` citations that reference these files and update line numbers.

After changes, append SESSION LOG to `assistant_project.md`.


================================================================================
SOURCE_FILE: docs/plans/one-remaining-gap-eventual-pixel.md
SOURCE_BYTES: 11022
PART: 6/10 FILE 2/7
================================================================================

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


================================================================================
SOURCE_FILE: docs/plans/open-defect-recovery-parsed-marble.md
SOURCE_BYTES: 7996
PART: 6/10 FILE 3/7
================================================================================

# EXECUTION PLAN — R2 (measure) → R1 (drift gate) → G1 (integrity gate)

> Created: 2026-06-03 · Updated: 2026-06-03 · Milestone: R2 measurement → governance/execution wiring (FUNDED)
> Mode: **execution, not analysis.** No new ledgers. No redesign. No KILLED/FROZEN orphan work
> (TradeNet V2 / Probability Surface / Liquidity V2 / ReplayMemory). No new feature/cluster intelligence.

## Context
Repository archaeology is complete (Repository Truths → Open Defect Ledger → Profit Impact Ledger →
Implementation Packets). The bottleneck is now execution. The next meaningful information comes only
from **running R2**. Order: measure first, then fix verified defects, then re-rank with measured PF.

---

## R2 COVERAGE PROOF (the gate the user required before coding R2)

*"Show every code path where ExecutionPlannerV1_2 and UltronRiskGate can affect live outcomes, and
prove the replay harness covers 100% of them."* Verified by code read:

### Live entry points (where these components affect outcomes)
| Surface | Path / contract | In R2 scope? |
|---|---|---|
| **Primary (v4 prod)** | `live_engine_hook.py:768-872` — `planner.plan()` → `compute_crt_levels` → `UltronRiskGate`+`UltronRiskGateWrapper.evaluate()` | **YES — 100% target** |
| `execution/loop.py` | generic injected `risk_gate: Callable(signal)->{allow:bool}` (`:60,163`) — abstract, different contract; not the v4 evaluate path | NO (acknowledged; not the prod path) |
| `portfolio/allocator.py:23` | **comment-only** ref to non-existent `UltronRiskGate.check_trade` — no real call | NO (no consumer) |
| `core/types.py:120` | `MT5Bridge.place_order` guard requires prior Ultron APPROVE — downstream of evaluate | covered via primary |
| `llm_research/forward_tester.py:119` | research forward-test, not live trading | NO (research) |

→ The **single production decision path is the primary one**; R2 covers it fully. The others are
explicitly out of scope and named so we never claim false 100%.

### Outcome levers the harness MUST reproduce (each = a way live ≠ replay if missed)
**ExecutionPlannerV1_2.plan()** (`execution_planner.py`): reject_invalid/engine/unknown_intent (:193-229),
**GateIntelligence** accept/reject (:251), **intent classification**, **intent-specific TTL** →
`validity_ttl_sec` (`_TTL_MAP` :71-104, :259-288), entry price.
**UltronRiskGate.evaluate()** (`ultron_risk_gate.py`): gate_disabled passthrough (:203), **Ch0 persisted
kill-switch** (:214), **Ch1 TTL** (:226), **Ch2 RR floor + spread/slippage tax** (:241), **Ch2.5
per-symbol duplicate** (:260), **Ch3 daily trade limit** (:273), **Ch4 daily-loss kill switch (stateful,
persisted)** (:278), **Ch5 portfolio exposure cap + per-trade risk cap** (:298), **Ch6/6b SL distance
floor** (:309), **Ch7 final sizing** = `min(hint, risk_usd/risk_per_unit)` (:334).
**UltronRiskGateWrapper**: regime pre-scale of `risk_percent` (:110-114).

### The decisive coverage requirement (the real failure mode)
**Ch0/Ch2.5/Ch3/Ch4/Ch5 are path-dependent.** A per-trade replay with fixed `portfolio_state` would
silently skip them and **measure the wrong thing**. The harness therefore **threads evolving portfolio
state trade-to-trade**: `account_balance, total_open_risk_pct, trades_today, daily_loss_pct,
open_positions`, with daily reset (`_daily_reset_tracker`) and kill-switch persistence honored. This is
the explicit coverage contract; the trust gate (below) fails the run if it isn't met.

---

## PACKET R2 · live-path validation (BUILD + RUN FIRST — measure-only)
**Deliverable:** `scripts/research/live_path_replay.py` (writes ONLY `results/live_path_replay/`).
**Build** (mirror `live_engine_hook.py:768-872`; reuse `execution_planner_replay.py:66-86` faithful
config load):
1. Faithful backtest on ACTIVE v4 → accepted trades + `RETEST_REPLAY` telemetry.
2. Per accepted trade, run the **real** `ExecutionPlannerV1_2.plan()` → `compute_crt_levels` →
   `UltronRiskGate`+`UltronRiskGateWrapper.evaluate()`, **threading evolving portfolio_state** (coverage
   contract above).
3. Forward-sim exits with `analytics.sl_tp_comparator.simulate_exit`, now with planner TTL/intent +
   Ultron sizing applied.
4. Aggregate position-sized PnL/PF; diff vs backtest spine headline.
**Trust gate (hard):** a no-Ultron/full-risk cell must reproduce the backtest expectancy bit-for-bit AND
selected==backtest trade count, else the harness is UNTRUSTED (exit non-zero).
**One-page conclusion** (the only narrative output): `Backtest PF · Live-path PF · Gap · Root-cause
attribution {execution_planner_ttl_intent, ultron_sizing}`.
**Effort** M. **Production risk** none.

## PACKET R1 · drift detected but not acted on (AFTER R2, only if trust gate passed)
- Config: add `"drift_action": {"hard":"block","hard_factor":0.0,"soft_factor":0.5}` under the
  `ultron_risk_gate` section of `v4_multi_2026_06.json` (NOT `params` — preserves the freshness
  fingerprint G1 enforces); re-hash via `scripts/maintenance/_compute_hash.py`.
- `live_engine_hook.py` before `:872`: soft → `risk_percent *= soft_factor`; hard+block → reject
  mirroring `MISSING_SL_TP` (`:828-834`), `risk_reason="DRIFT_HARD"`, size 0.0, skip wrapper (pre-gate,
  SR-1 intact); hard+scale → `hard_factor`.
- **Parity** (`backtest_v2.py` sizing `:791` using `_sev` from `:1858`): same factors → drift-handling
  symmetric across paths (the broader sizing-engine divergence is owned by R2, not R1).
- Tests: soft scales, hard+block rejects (gate NOT called), hard+scale scales, no-drift byte-identical
  (both paths). Rollback: revert 2 files + remove key + re-hash (inert without key).
- Self-review: key under `ultron_risk_gate` not `params`; G1 audit still exits 0; SR-1 intact; no magic
  numbers; `pytest` green; §6 LOG + §6.1 topic doc.
**Effort** S.

## PACKET G1 · enforce config_integrity (AFTER R1)
- `config_integrity.py`: add `ConfigIntegrityError` + `enforce(registry_dir, *, require_fresh=True)`
  (reuses the two existing guards; raises).
- Call at: `live_engine_hook` session init (primary), `promotion_manager` pre-promote, `backtest_v2`
  prod-registry path **behind a skip flag** (tuner must not re-check — perf). Toggle
  `governance.enforce_config_integrity` (default true).
- Pre-verified safe: v4 has `params_fingerprint` (`v4:193=c2568b6a…`) + a `PROMOTED` entry → passes today.
- Tests: governed+fresh passes; ungoverned/stale raises; toggle off skips; tuner skip-flag no-call.
  Rollback: toggle false (instant). Self-review: v4 audit exits 0 before/after; tuner unaffected.
**Effort** S.

## AFTER R2 — re-rank, don't pre-build
Recompute the **Funding Ledger** + **Profit Impact Ledger** using **measured** PF. Then, only if the
live edge survives: **S2** (throughput sweep `tier_2_threshold∈[0.44..0.60]`; ~35-trade ceiling →
diminishing), then **F3** (consume `context["fusion_weights"]` in `fusion_engine.compute()` behind a
flag; shadowed by F-001). If PF collapses: re-prioritize around the live execution layer; drop S2/F3.

## Execution order & stop conditions
1. **R2** → `results/live_path_replay/bnbusdt.json` + one-page conclusion. **STOP** if trust gate fails
   (fix harness fidelity before trusting any number).
2. **R1** (live + backtest parity) — only if R2 trust gate passed.
3. **G1**.
4. **Re-rank** with measured PF → decide S2/F3.
- Forbidden this cycle: Probability Surface, ReplayMemory, TradeNet revival, new feature/cluster
  intelligence, new architecture proposals.

## Validation
- `python scripts/research/live_path_replay.py --instrument BNBUSDT` → report; trust gate exits 0.
- `pytest tests/` green incl. new R1/G1 tests; no-drift + governed paths byte-identical.
- `python -m governance.config_integrity configs/production` exits 0 (v4 governed + fresh).
- §6 SESSION LOG per change; §6.1 topic docs (drift-handling, governance-enforcement); if measured PF
  materially differs from +20.59%, file/flip a finding in `docs/current-findings.md` per §6.2.


================================================================================
SOURCE_FILE: docs/plans/probability-surface-advisory.md
SOURCE_BYTES: 4040
PART: 6/10 FILE 4/7
================================================================================

# Plan: Probability-Surface Advisory (deterministic, weight-0.0, measured-additively)

> Created: 2026-06-02 · Updated: 2026-06-04 · Milestone: Trd-M (Probability-Surface→Fusion advisory)
> Spawned by backlog #6 DECISION = YES (see [`docs/topics/replay-memory.md`](../topics/replay-memory.md) Discussion).
> **Status: KILLED (2026-06-03) — superseded by the Funding Ledger in [`docs/current-findings.md`](../current-findings.md) (Probability Surface V2 = KILLED; evidence F-001, F-012).** This plan is the implementing initiative for Probability-Surface→Fusion; it is retained for replay, **not** active work. Do **not** resume without meeting the ledger's Reopen Conditions (Phase-0 economic-edge gate clears **and** ReplayMemory path-stats show AUC lift beyond static zone features) **and** filing a SESSION LOG entry per `CLAUDE.md §6.2`.
> *(Historical) Status: SCOPED — not yet implemented.*

## Context

The #6 decision granted ReplayMemory **advisory status** (preconditions met: 4-instrument OOS
persistence + schema/weighting repair + 4 per-instrument `zone_v1` registries). The binding
governance constraint (invariant #1, determinism) is that the signal is currently computed in the
**async fire-and-forget `CognitiveBus` worker** — replay-incomparable, so it cannot influence a
decision as-is. This plan re-homes the computation to the **synchronous deterministic path** and
introduces it as a **weight-0.0, measured-additively** advisory (the Phase-6 ROI pattern), never a
gate. Outcome: a reviewed, reversible advisory branch that can earn a non-zero weight only after its
decision-value is measured.

## Constraints (non-negotiable)
- **Determinism (inv #1):** advisory computed inline on the candle→decision path, seeded, no lookahead, candle-time keyed.
- **All-four-engines (inv #2):** advisory is *additional*, never replaces an engine; absence ⇒ neutral, not partial fusion.
- **Authority isolation (inv #5):** advisory adjusts a fusion *score* within bounds; it can never approve/trigger. Weight 0.0 = inert by default.
- **Telemetry additive (inv #5/#5):** new fields only; old telemetry preserved.

## Steps
1. **Synchronous per-instrument lookup.** Add a deterministic `ProbabilitySurface` reader that, given the current bar's features + instrument, loads `models/replay/zone_registry_<INST>.json`, calls `ReplayMemoryEngine._assign_cluster` + cluster stats, and returns a bounded advisory scalar. Reuse the repaired assignment; load synchronously (cache per instrument). Per-instrument selection = option (a) from the topic doc.
2. **Fusion consumption at weight 0.0.** In `core/fusion_engine.py`, add a config-gated advisory term (`probability_surface.weight`, default `0.0`) that nudges the fused score within a clamp. At 0.0 it is a no-op → output identical to today (regression-provable).
3. **Config.** Add a `probability_surface` section (weight 0.0, per-instrument `registry_paths`, enabled flag) to the source-of-truth config; document in `config-reference.md`.
4. **Measure additively.** Emit the would-be advisory delta as telemetry on every decision (additive field) so its decision-value is measurable *before* any non-zero weight — the gate for ever raising the weight.
5. **Tests.** Determinism/replay parity (weight 0.0 ⇒ byte-identical decisions vs baseline); per-instrument registry selection; neutral-on-missing-registry; authority-isolation (advisory cannot flip a REJECT to APPROVE on its own); bounded clamp.

## Verification
- `pytest -q` green; a replay-parity test proves weight-0.0 ⇒ identical decision stream vs current.
- Determinism: same inputs → same advisory value across two runs.
- Invariant re-check: engines still all-or-nothing; LLM/advisory never trigger; telemetry additive.
- Only after measured decision-value justifies it: a separate, validated promotion raises the weight (governance gate).

## Out of scope
- Any non-zero default weight (requires measured-value review first).
- Learned probabilistic path-trees / Monte-Carlo (later milestone).


================================================================================
SOURCE_FILE: docs/plans/readme.md
SOURCE_BYTES: 13933
PART: 6/10 FILE 5/7
================================================================================

# Plans Index — `docs/plans/`

> The **navigable face** over the plan files in this folder. Each plan is a point-in-time design
> record written in plan mode (filenames are auto-generated from the first prompt, so they are
> opaque — use this index, not the filename, to find a plan). Newest first.
>
> **See also:** [`../knowledge-map.md`](../knowledge-map.md) — how all the record systems connect + traversal recipes.
>
> **This is the chronological lens on _what was planned_.** Pair it with:
> - [`../timeline.md`](../timeline.md) — the unified "what changed when" (plan ↔ SESSION LOG ↔ findings).
> - [`../analysis/readme.md`](../analysis/readme.md) — the studies/audits some of these plans produced.
> - [`../../assistant_project.md`](../../assistant_project.md) — the append-only SESSION LOG (what was actually done).
> - [`../current-findings.md`](../current-findings.md) — validated conclusions (incl. the Funding Ledger that `KILLED`/`FROZEN` some of these plans).

**Conventions**
- **Date** = the plan's `> Created:` header date. A `~` prefix means **inferred from file mtime**
  (the plan predates the dated-header convention; `docs/plans/` is not git-tracked, so mtime is the
  best available signal — treat as approximate).
- **Milestone** = the plan's `Milestone:` header field; `—` = none recorded, `n/a` = explicitly exploratory.
- **Status** = `KILLED` when the plan's own header / the Funding Ledger marks it dead. Blank = not terminal (shipped work is recorded in the SESSION LOG, not here).
- New plans must open with `> Created: YYYY-MM-DD · Updated: YYYY-MM-DD · Milestone: <M>` (per `CLAUDE.md §12` / the `Plan` trigger).

---

| Date | Milestone | Title | File |
| --- | --- | --- | --- |
| 2026-06-05 | Gov (docs-alignment / cold-start visibility) | CLAUDE.md Preparation — Doc↔Code Alignment + Durable Mapping + Chronological Reference | [`lets-work-on-claude-goofy-scott.md`](./lets-work-on-claude-goofy-scott.md) |
| 2026-06-04 | cross-cutting (governance + Trd-track) | Architecture Truth Audit & Synchronization — Tradelatest **KILLED** | [`system-mandate-architecture-tender-hoare.md`](./system-mandate-architecture-tender-hoare.md) |
| ~2026-06-04 | — | BitNet Adaptive Threshold | [`bitnet-is-the-active-adaptive-ritchie.md`](./bitnet-is-the-active-adaptive-ritchie.md) |
| ~2026-06-04 | — | TradeNet v2 — 3-Head Survival Classifier **KILLED** | [`context-current-tradenet-is-jazzy-lemur.md`](./context-current-tradenet-is-jazzy-lemur.md) |
| 2026-06-03 | Gov (knowledge-governance) | Repository Truths Layer v2 — Types, Durable Tier, Funding Ledger **KILLED** | [`assume-the-architecture-is-joyful-naur.md`](./assume-the-architecture-is-joyful-naur.md) |
| 2026-06-03 | research / measure-first | Plan: Selection-Edge studies — Accepted-Trade Attribution + Gate Contribution Audit | [`i-remember-we-are-golden-yeti.md`](./i-remember-we-are-golden-yeti.md) |
| 2026-06-03 | R2 measurement → governance/execution wiring (FUNDED) | EXECUTION PLAN — R2 (measure) → R1 (drift gate) → G1 (integrity gate) **KILLED** | [`open-defect-recovery-parsed-marble.md`](./open-defect-recovery-parsed-marble.md) |
| 2026-06-03 | Trd (governance/execution track) | Execution Plan — Per-Instrument Session Optimization (the pivot's first lever) | [`the-strongest-assumption-that-glistening-clarke.md`](./the-strongest-assumption-that-glistening-clarke.md) |
| 2026-06-03 | cross-cutting (Trd track / analysis) | Plan: Repository Evolution Audit — Liquidity-State Intelligence Thesis | [`yes-after-inspecting-the-proud-summit.md`](./yes-after-inspecting-the-proud-summit.md) |
| ~2026-06-03 | — | Plan — Execution-Planner Replay: split the EXECUTION edge into Selection vs SL/TP structure | [`search-all-plans-reports-merry-sunbeam.md`](./search-all-plans-reports-merry-sunbeam.md) |
| 2026-06-02 | Production-governance integrity (backlog P1) | Plan: Reconcile the v1/v2 config-lineage divergence (governance trust) | [`claude-go-thrugh-docs-twinkling-finch.md`](./claude-go-thrugh-docs-twinkling-finch.md) |
| 2026-06-02 | — | Plan: Persist the Intelligence-Layer Audit | [`goal-produce-a-complete-fluffy-grove.md`](./goal-produce-a-complete-fluffy-grove.md) |
| 2026-06-02 | Trd-M (Probability-Surface→Fusion advisory) | Plan: Probability-Surface Advisory (deterministic, weight-0.0, measured-additively) **KILLED** | [`probability-surface-advisory.md`](./probability-surface-advisory.md) |
| 2026-06-02 | Production-governance integrity + capability re-activation (P1) | Plan: Reconcile lineage onto v1 canonical + enable rich sections (Option B) | [`yes-based-on-the-eventual-sunrise.md`](./yes-based-on-the-eventual-sunrise.md) |
| 2026-06-01 | Pre-existing failure audit + contract audit | Context (Pre-existing failures + execution-contract audit) | [`22-pre-existing-failures-check-splendid-biscuit.md`](./22-pre-existing-failures-check-splendid-biscuit.md) |
| 2026-06-01 | doc/naming convention (cross-track) | Adopt Gov-/Trd- Milestone Prefixes Across Living Docs + Code Comments | [`frolicking-foraging-hearth.md`](./frolicking-foraging-hearth.md) |
| 2026-06-01 | M2 | M2 — User Progress Registry | [`one-remaining-gap-eventual-pixel.md`](./one-remaining-gap-eventual-pixel.md) |
| 2026-06-01 | M (new doc-governance layer, foundation phase) | Topic Visibility & Docs↔Code Sync — Foundation | [`refer-the-pure-docs-sunny-lagoon.md`](./refer-the-pure-docs-sunny-lagoon.md) |
| 2026-06-01 | M1 | Plan: Intent Governance Framework Doc **KILLED** | [`this-is-a-valuable-pure-flurry.md`](./this-is-a-valuable-pure-flurry.md) |
| 2026-06-01 | Trd-M3..M5 | Trd-M3 → M4 → M5 — Complete the Trading-Architecture Infrastructure Track | [`trd-m0-m5-tender-bentley.md`](./trd-m0-m5-tender-bentley.md) |
| 2026-06-01 | Trd-M6 (entry-gate / pre-work) | Trd-M6 stays downstream — BNBUSDT instrument-scoped session promotion | [`trd-m6-stays-downstream-plan-crystalline-pascal.md`](./trd-m6-stays-downstream-plan-crystalline-pascal.md) |
| ~2026-06-01 | — | Plan: Agent-Readable Execution Memory Layer | [`you-are-lead-runtime-typed-snowglobe.md`](./you-are-lead-runtime-typed-snowglobe.md) |
| 2026-05-30 | — | Plan — Analyse `assistant_project.md` & Trace User Intention "of Tool" | [`analyse-assistant-project-d-giggly-flask.md`](./analyse-assistant-project-d-giggly-flask.md) |
| 2026-05-29 | optimization track (Phase 6b — ROI gaps) | ROI Increase Plan — Gap Analysis & Implementation (BNBUSDT M15) | [`from-docs-gather-the-foamy-swan.md`](./from-docs-gather-the-foamy-swan.md) |
| 2026-05-29 | n/a | Collaboration Workflow — Tracking & Replay Setup | [`how-claude-is-refeering-soft-waterfall.md`](./how-claude-is-refeering-soft-waterfall.md) |
| 2026-05-29 | n/a | Plan — Semantic docs reorg (full reshuffle, kebab-case) | [`kind-dazzling-frost.md`](./kind-dazzling-frost.md) |
| 2026-05-28 | Trd-M0 | Architecture Migration — Event-Driven, LLM-Context-Economy Governance | [`claude-architecture-migration-eager-wreath.md`](./claude-architecture-migration-eager-wreath.md) |
| ~2026-05-28 | — | Plan: Phase 4 — Shadow Governance | [`d-tradelatest-trade-discovery-trace-md-serene-zebra.md`](./d-tradelatest-trade-discovery-trace-md-serene-zebra.md) |
| ~2026-05-28 | — | Plan: Expose webhook via ngrok + wire up TradingView | [`generate-claude-md-for-current-eventual-sketch.md`](./generate-claude-md-for-current-eventual-sketch.md) |
| ~2026-05-27 | — | Sprint 1 — Phase A+B: Activate _transition_path Injection (READY TO IMPLEMENT) | [`d-tradelatest-logs-logsrepo-tree-txt-d-tidy-gem.md`](./d-tradelatest-logs-logsrepo-tree-txt-d-tidy-gem.md) |
| ~2026-05-23 | — | Fix: Session Label Missing from TRADE_OPENED Event Metadata | [`analyse-the-accuracy-of-robust-kay.md`](./analyse-the-accuracy-of-robust-kay.md) |
| ~2026-05-22 | — | Current Status (2026-05-22) | [`analyze-only-this-runtime-wondrous-shell.md`](./analyze-only-this-runtime-wondrous-shell.md) |
| ~2026-05-22 | — | ROI-First Refinement: Phases P6.1 → P6.4 (Gaussian → Regime → TradeNet → Joint, plus ZoneGate / RR / BitNet) | [`yes-reverse-order-indexed-cookie.md`](./yes-reverse-order-indexed-cookie.md) |
| ~2026-05-22 | — | Stage-1 Recovery Phase — Implementation Plan | [`you-are-implementing-stage-1-polished-token.md`](./you-are-implementing-stage-1-polished-token.md) |
| ~2026-05-21 | — | Correlation Engine v2 — Rolling Pearson with TTL Cache & Static Fallback | [`here-is-the-complete-tingly-finch.md`](./here-is-the-complete-tingly-finch.md) |
| ~2026-05-21 | — | Plan — Gaussian Versioning Per Instrument | [`regime-aware-fusion-closed-marking-glistening-river.md`](./regime-aware-fusion-closed-marking-glistening-river.md) |
| ~2026-05-21 | — | Plan — Regime-Aware Fusion Weights | [`start-with-regime-aware-fusion-rosy-waterfall.md`](./start-with-regime-aware-fusion-rosy-waterfall.md) |
| ~2026-05-20 | — | CANONICAL EXECUTION COGNITION GRAPH — Tradelatest | [`claude-you-have-full-fuzzy-bonbon.md`](./claude-you-have-full-fuzzy-bonbon.md) |
| ~2026-05-20 | — | Validation Report — Architectural Assessment | [`good-enough-context-let-humming-knuth.md`](./good-enough-context-let-humming-knuth.md) |
| ~2026-05-20 | — | Plan: Per-Instrument Versioned Model Registries | [`knowledge-transfer-document-temporal-bird.md`](./knowledge-transfer-document-temporal-bird.md) |
| ~2026-05-20 | — | Feedback Loop Audit — Plan | [`let-me-read-every-velvety-gosling.md`](./let-me-read-every-velvety-gosling.md) |
| ~2026-05-20 | — | Phase-Integrity Hardening — Implementation Plan | [`you-are-implementing-phase-integrity-inherited-tulip.md`](./you-are-implementing-phase-integrity-inherited-tulip.md) |
| ~2026-05-19 | — | Plan: Configurable UI Poll Interval (default 3 min) | [`crt-127-0-0-1-get-runs-q-cheeky-blum.md`](./crt-127-0-0-1-get-runs-q-cheeky-blum.md) |
| ~2026-05-19 | — | Add Date Fields + Config Clarification for Fetch Commands | [`e4081377-is-failed-but-fluffy-wreath.md`](./e4081377-is-failed-but-fluffy-wreath.md) |
| ~2026-05-19 | — | Feature Explorer Audit + Model Registry Tree & Groq Explain | [`gaussain-zonegate-tradenet-rrminer-ethereal-dove.md`](./gaussain-zonegate-tradenet-rrminer-ethereal-dove.md) |
| ~2026-05-19 | — | Fix: Post-Training Verification Path Inconsistency | [`validation-of-expectations-vivid-peacock.md`](./validation-of-expectations-vivid-peacock.md) |
| ~2026-05-18 | — | Fix Dynamic Catalog Loading in React UI (ComboBox "0 options") | [`yes-this-is-now-eager-pixel.md`](./yes-this-is-now-eager-pixel.md) |
| ~2026-05-16 | — | Feature Pipeline Bug-Fix Plan | [`d-tradelatest-models-tradenet-registry-robust-neumann.md`](./d-tradelatest-models-tradenet-registry-robust-neumann.md) |
| ~2026-05-16 | — | Plan: Fetch AUDUSD M15 Candles via Alpha Vantage (New Fetcher) | [`hummingbot-candle-fetcher-need-command-t-tingly-candle.md`](./hummingbot-candle-fetcher-need-command-t-tingly-candle.md) |
| ~2026-05-16 | — | RR Model Training Audit | [`you-are-auditing-a-goofy-prism.md`](./you-are-auditing-a-goofy-prism.md) |
| ~2026-05-13 | — | Plan: Restrict Control Plane UI to Valid Inputs | [`in-ui-to-follow-purring-honey.md`](./in-ui-to-follow-purring-honey.md) |
| ~2026-05-12 | — | Plan: Timing Instrumentation for `opportunity_scanner.py` | [`time-estimate-calculation-compressed-biscuit.md`](./time-estimate-calculation-compressed-biscuit.md) |
| ~2026-05-10 | — | Plan: Config Version Single Source of Truth Refactor | [`below-is-a-prompt-mighty-riddle.md`](./below-is-a-prompt-mighty-riddle.md) |
| ~2026-05-10 | — | Plan: Fix backtest_v2.py ignoring CRT parameters from production config JSON | [`the-root-cause-fancy-marble.md`](./the-root-cause-fancy-marble.md) |
| ~2026-05-09 | — | CRT Engine Log Empty — Root Cause & Fix Plan | [`crt-engine-20260509-005424-is-empty-chec-parsed-yeti.md`](./crt-engine-20260509-005424-is-empty-chec-parsed-yeti.md) |
| ~2026-05-09 | — | Zone Registry Fix — Per-Instrument Registry with Underpowered Auto-Bypass | [`dont-read-logs-will-streamed-trinket.md`](./dont-read-logs-will-streamed-trinket.md) |
| ~2026-05-07 | — | Plan: Backtest on Existing M15 Data + Agent Strategy Discovery + Live Broker Hook | [`based-on-your-screenshot-precious-scott.md`](./based-on-your-screenshot-precious-scott.md) |
| ~2026-05-07 | — | Plan: Add JSONL Audit Trail for Strategy Orchestrator | [`i-remember-we-implemented-flickering-pie.md`](./i-remember-we-implemented-flickering-pie.md) |
| ~2026-05-07 | — | Plan: Groq-Powered Post-Trade Retrospective & ROI Enhancement | [`study-the-code-base-linear-alpaca.md`](./study-the-code-base-linear-alpaca.md) |
| ~2026-05-07 | — | Plan: Hummingbot Historical Data Ingestion for Tradelatest Backtest | [`stusy-readme-of-https-github-com-humming-unified-flamingo.md`](./stusy-readme-of-https-github-com-humming-unified-flamingo.md) |
| ~2026-05-07 | — | Plan: Relax Phase-5 gates to unblock Gaussian training on small dev dataset | [`venv-ps-d-tradelatest-python-compiled-orbit.md`](./venv-ps-d-tradelatest-python-compiled-orbit.md) |
| ~2026-05-07 | — | Plan: Fix fusion log pairing failure → recover valid training records | [`venv-ps-d-tradelatest-python-sleepy-squirrel.md`](./venv-ps-d-tradelatest-python-sleepy-squirrel.md) |
| ~2026-05-07 | — | Plan: Make `--version` Optional in `from-report` CLI Subcommand | [`venv-ps-d-tradelatest-python-zazzy-simon.md`](./venv-ps-d-tradelatest-python-zazzy-simon.md) |
| ~2026-05-07 | — | Command Audit Report — Tradelatest Quantitative Trading System | [`you-are-an-expert-ancient-pebble.md`](./you-are-an-expert-ancient-pebble.md) |

---

_64 plans indexed. Regenerate the metadata with the extraction approach in the SESSION LOG entry that
created this file (dates from `> Created:` headers; `~` dates from file mtime). When you add a plan,
add its row here in the same turn._


================================================================================
SOURCE_FILE: docs/plans/refer-the-pure-docs-sunny-lagoon.md
SOURCE_BYTES: 11253
PART: 6/10 FILE 6/7
================================================================================

# Topic Visibility & Docs↔Code Sync — Foundation

> Created: 2026-06-01 · Updated: 2026-06-01 · Milestone: M (new doc-governance layer, foundation phase)

## Context (why we're doing this)

The repo already has a **Context Report** button in the control plane — click 🧠 on a finished run and it runs `extract_code_context()` (pure-stdlib AST extraction of executed symbols from the script path + traceback lines, [`code_context_extractor.py`](src/control_plane/code_context_extractor.py)) → `ContextReportAPI.context_analysis()` ([`context_report.py`](src/control_plane/context_report.py)) → Claude Haiku → structured JSON (`root_cause` / `architecture_notes` / `artifact_analysis` / `recommendations`). It gives operational visibility into **one run**.

The user wants the same *shape of visibility* but keyed on a **topic / concept** instead of a run: for a topic, narrate in human language **what code it covers, its tests, its ins/outs, and its validations traced through application entry points** — and keep that narration **in sync with the code on every working response**, so docs never drift. The doc references in `CLAUDE.md` should become a navigable **tree path** (today the §2 table is flat — the "soft waterfall"), and each topic should carry a standing **discussion block** (risks / challenges / blockers / ambiguities / enhancements / need-more-info) filled during sessions.

This phase builds the **docs + sync foundation only** — no new UI button, server route, or LLM code. The LLM-powered "Topic Report" button (the technical mirror of Context Report) is the explicit **next phase**, unlocked once the structure and topic set exist. This is doc-only, fully reversible, no `src/` or runtime change.

**Why it helps Claude (the durable payoff):** today every session re-derives "what is the CRT spine / where does governance live / what tests cover fusion" by re-reading source. A maintained `docs/topics/` layer gives a session **one grounded, human-language file per concept** — code covered (with `file:line` citations), entry points, tests, validations, and known risks/blockers — so orientation is a single read instead of a fan-out, ambiguities are tracked across sessions instead of rediscovered, and the per-response sync mandate keeps that file true as code changes. Less token spend, faster `Orient`, no stale context. This is the same logic as the §6 SESSION LOG mandate, extended from "what I did" to "what each topic *is*."

## What already exists (reuse, do not reinvent)

| Concern | Existing asset |
|---|---|
| AST code extraction (for later report phase) | [`code_context_extractor.py`](src/control_plane/code_context_extractor.py) `extract_code_context()` |
| LLM structured-JSON pattern (for later report phase) | [`context_report.py`](src/control_plane/context_report.py) `ContextReportAPI` (4-key JSON, Haiku, optional-import guard, `.env` key load) |
| Human-language narration format | [`docs/human-language-analysis/`](docs/human-language-analysis/) — 20 package-grouped files (purpose / runtime role / invocation / I-O / failure modes / determinism / trust) |
| Per-module structured analysis | [`docs/analysis/codebase-analysis.md`](docs/analysis/codebase-analysis.md) — ✅Overview 📊Architecture 🚧Gates 🔗Integration ⚠️Constraints 🎯Operation per module |
| Entry-point catalog | [`src/control_plane/registry.py`](src/control_plane/registry.py) `CommandSpec` list → [`docs/reference/cli-matrix.md`](docs/reference/cli-matrix.md) (auto-generated) |
| Session threads / open questions | [`assistant_project.md`](assistant_project.md) SESSION LOG blocks |
| Dependency/code mapping | [`scripts/analysis/gen_code_map.py`](scripts/analysis/gen_code_map.py), `graph.dot`, [`code-map.generated.md`](docs/architecture/code-map.generated.md) |
| Per-response mandate precedent | `CLAUDE.md` §6 SESSION LOG (mandatory append every response) |
| Doc-alignment test pattern | [`tests/test_control_plane_doc_alignment.py`](tests/test_control_plane_doc_alignment.py) |
| Tree/index doc precedent | [`README.md`](README.md) docs map · [`docs/governance/user-progress-registry.md`](docs/governance/user-progress-registry.md) |

## Recommended approach

### 1. New `docs/topics/` layer (the topic-visibility home)

- **`docs/topics/readme.md`** — the **topic index** and tree root. A single-screen table:
  `Topic | Domain | Source files | Entry points | Tests | Status | Doc`.
  Seeded by mining the existing assets (not invented): each [`human-language-analysis/`](docs/human-language-analysis/) grouping → candidate topic rows; cross-reference [`assistant_project.md`](assistant_project.md) threads (e.g. Phase 0–6 BNBUSDT funnel work) for live concepts; map `Entry points` to `registry.py` `CommandSpec` ids / `cli-matrix.md`; map `Source files`/coverage to [`codebase-analysis.md`](docs/analysis/codebase-analysis.md) modules.
- **`docs/topics/_template.md`** — the per-topic template (mirrors `docs/architecture/services/_template.md` placement convention). Sections:
  1. **Header** — `> Created · Updated · Status` (dated like §6 / plans).
  2. **In plain language** — what this topic *is* and why it exists (human narration, lifted style from `human-language-analysis/`).
  3. **Code covered** — modules/classes/functions with `file:line` citations (cross-ref `codebase-analysis.md`).
  4. **Ins / Outs** — inputs consumed, outputs produced, config sections, JSONL lines.
  5. **Entry points & validations** — how it's reached (CLI / control-plane command / agent tool, cited to `registry.py`) and what validates it end-to-end.
  6. **Tests** — covering `tests/` files (the coverage view).
  7. **Fits in architecture** — where it sits in `signal-flow.md` / `code-map`; links up the tree.
  8. **Discussion (filled in-session)** — `Risks · Challenges · Blockers · Ambiguities · Enhancements · Need-more-info`, each entry dated. This is the standing parallel-discussion surface; template, no API calls this phase.
- **Seed 1–2 example topic docs** to prove the format end-to-end — e.g. `context-report.md` (the feature we just studied; self-documenting) and `crt-spine.md` (the candle→order spine, the system's core concept). The rest are listed as rows in `readme.md` with `Status: stub`.

### 2. Restructure `CLAUDE.md` doc references into a tree path

- Add a **`§2.0 Doc Reference Tree`** block above the existing flat §2 table — an indented tree showing the navigation hierarchy (root → tier → leaf), e.g.:
  ```
  CLAUDE.md  (operating manual, root)
  ├─ README.md  (front door + docs map)
  ├─ docs/architecture/   (why / where / flow)
  │   ├─ goal.md · signal-flow.md · event-taxonomy.md · code-map.md …
  ├─ docs/reference/      (what — stack, schemas, conventions, configs, tests)
  ├─ docs/topics/         (TOPIC VISIBILITY — concept↔code↔tests↔validations)   ← NEW
  │   ├─ readme.md  (topic index = tree of topics)
  │   └─ <topic>.md
  ├─ docs/governance/ · docs/architecture/idea-governance-framework.md
  └─ docs/analysis/       (historical, non-living)
  ```
  Keep the existing §2 task→doc table (it stays authoritative for "which doc covers X"); the tree is the *navigation* view the user asked for. Add one `docs/topics/readme.md` row to the §2 table and a §3.4 "Key files" bullet so it's discoverable in the soft waterfall.

### 3. Per-response docs↔code sync mandate (the "automatic on every response" ask)

- Add **`§6.1 Topic Sync Mandate`** to `CLAUDE.md`, modeled on the §6 SESSION LOG rule:
  > On every response that changes code or the understanding of a topic, update that topic's `docs/topics/<topic>.md` in the same turn — **only the affected topic file(s)** (token-aware; never rewrite unrelated docs), bump its `Updated:` date, and note the change. Purely conversational responses touch only the SESSION LOG.
- This makes docs↔code sync **automatic per response** (the user's explicit request) without a generator or CI gate, reusing the proven §6 discipline. Token control is honored by the "only touched files" rule (§8).
- Add a **`Sync`** trigger to [`docs/architecture/trigger-vocabulary.md`](docs/architecture/trigger-vocabulary.md) Tier-2 (action: reconcile a topic doc against current code; read-then-surgical-edit; ends with SESSION LOG) and reference it from `CLAUDE.md` §12.

### 4. Discoverability + light enforcement

- `README.md` docs map: add `docs/topics/` under Tier 3.
- Extend [`tests/test_control_plane_doc_alignment.py`](tests/test_control_plane_doc_alignment.py) (or sibling `tests/test_topic_docs.py`) with a read-and-assert test: every `docs/topics/*.md` (except `readme.md`/`_template.md`) has a `Created:`/`Updated:` date header and the required section headings — the enforceable analogue of the §6 / plan-timestamp pattern. Mechanical only; does **not** verify code-sync content.

## Files to create / modify

- **Create:** `docs/topics/readme.md`, `docs/topics/_template.md`, `docs/topics/context-report.md`, `docs/topics/crt-spine.md`
- **Modify:** `CLAUDE.md` (§2.0 tree block, §2 table row, §3.4 bullet, §6.1 sync mandate, §12 `Sync` trigger)
- **Modify:** `README.md` (docs-map Tier-3 entry)
- **Modify:** `docs/architecture/trigger-vocabulary.md` (`Sync` Tier-2 trigger)
- **Create/Modify:** `tests/test_topic_docs.py` (or extend `test_control_plane_doc_alignment.py`) — header/section assertion

## Next phase (explicitly out of scope here)

The **LLM-powered "Topic Report" button** — control-plane button → topic resolver (registry + dependency graph) → AST topic extractor (generalize `extract_code_context()` from run→topic) → Claude structured JSON (risks/challenges/blockers/enhancements, the parallel-discussion lenses) → auto-written `docs/topics/<topic>.md`. Foundation here makes that a thin wrapper later. **No UI/server/LLM code this phase.**

## Verification (end-to-end)

1. **Read test:** open `docs/topics/readme.md` — is the topic index a scannable one-screen table with the tree visible? Open `docs/topics/context-report.md` — does it narrate the feature in plain language with `file:line` citations, ins/outs, entry points, tests, and a dated Discussion block?
2. **Tree path:** `CLAUDE.md` §2.0 renders the doc references as an indented tree including `docs/topics/`.
3. **Sync mandate:** `CLAUDE.md` §6.1 + the `Sync` trigger in `trigger-vocabulary.md` are present and consistent with the §6 pattern.
4. **Discoverability:** `docs/topics/readme.md` is linked from `CLAUDE.md` §2/§3.4 and `README.md`.
5. **Tests:** `python -m pytest tests/test_topic_docs.py -q` (or the extended alignment test) → pass.
6. **Sync dry-run:** make a trivial edit to one cited symbol, confirm the mandate's loop (update only that topic's doc, bump `Updated:`) is followable in one turn without touching unrelated docs.

## Out of scope

- No `src/`, engine, runtime, control-plane, or UI change.
- No LLM API calls / new automation beyond the one doc-alignment test.
- Not regenerating `human-language-analysis/` or `codebase-analysis.md` — they are *sources* to mine, left intact.
- Not building the Topic Report button (next phase).


================================================================================
SOURCE_FILE: docs/plans/regime-aware-fusion-closed-marking-glistening-river.md
SOURCE_BYTES: 20269
PART: 6/10 FILE 7/7
================================================================================

> Created: 2026-05-21 · Updated: 2026-05-21 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan — Gaussian Versioning Per Instrument

## Context

`gaussian_registry.json` currently uses a flat `{version_id: entry}` shape where each entry carries `active: bool`. A single `active: True` flag is the system's only active-version pointer, so **any instrument promotion overwrites the active flag for every other instrument** — promoting a new EURUSD model also flips XAUUSD off. There is no rollback path. Separately, `trainer.load_gaussian_model` reads `bundle["scaler"]` without auditing missing-scaler cases, so the loud `KeyError` it raises today never lands in `logs/integrity_events.jsonl` and is invisible to forensics.

This patch isolates the active-version pointer per instrument, adds a per-instrument rollback path, and audits the missing-scaler failure mode — without rewriting the registry schema or breaking existing callers.

## Decisions (locked from user feedback)

| Question | Decision |
| --- | --- |
| Registry shape | **Hybrid:** keep `{version_id: entry}` flat. Add one top-level `__active__: {instrument: version}` map. The `__` prefix signals "registry metadata, not a version entry" so any iterator can skip it cleanly. |
| `promote_gaussian` signature | Add `*, instrument: Optional[str] = None` (keyword-only) to the method **and** the module-level wrapper. When `instrument is None`, derive from `reg[version].get("instrument")` and emit `GAUSSIAN_PROMOTE_INSTRUMENT_INFERRED` info event. |
| `trainer.py` scaler guard | Add explicit `bundle.get("scaler") is None` check that emits `GAUSSIAN_MISSING_SCALER` ERROR event. **Preserve** original exception type — `KeyError` for missing key, `RuntimeError` for explicit `None`. |
| Engine instrument source | `__init__(self, config, *, instrument: Optional[str] = None, preload_registry: bool = False)`. Body: `self._instrument = instrument or config.get("instrument", "EURUSD")`. |

## Files To Modify

### 1. `src/core/model_registry.py`

**Lines 86–95** (`_save_atomic`) — unchanged. Atomic write mechanism is correct.

**Lines 98–108** (`_assert_single_active`) — unchanged. Stays generic for non-gaussian registries (tradenet, zone, RR still use the legacy single-active invariant).

**Line 350–353** (`GaussianModelRegistry._save`) — **stop calling** `_assert_single_active(reg, active_key="active")`. The gaussian registry now allows multiple entries with `active: True` (one per instrument during transition). Replace with a new assertion `_assert_single_active_per_instrument(reg)` defined below.

**New helpers** (place above `class GaussianModelRegistry` at line 320):

```python
_ACTIVE_MAP_KEY = "__active__"   # double-underscore => not a version entry

def _is_meta_key(k: str) -> bool:
    return k.startswith("__")

def _assert_single_active_per_instrument(reg: dict) -> None:
    """At most one entry per instrument may have active=True."""
    by_inst: dict[str, list[str]] = {}
    for k, v in reg.items():
        if _is_meta_key(k) or not isinstance(v, dict):
            continue
        if v.get("active", False):
            inst = v.get("instrument", "_unknown")
            by_inst.setdefault(inst, []).append(k)
    for inst, versions in by_inst.items():
        if len(versions) > 1:
            raise RuntimeError(
                f"GOV-3 violation: instrument {inst!r} has multiple "
                f"active versions {versions}. Write aborted."
            )

def _migrate_gaussian_registry(reg: dict) -> dict:
    """One-time migration: if __active__ map is absent, populate it from
    existing entry-level active flags. Idempotent — safe to call on every load."""
    if _ACTIVE_MAP_KEY in reg:
        return reg
    active_map: dict[str, str] = {}
    for k, v in reg.items():
        if _is_meta_key(k) or not isinstance(v, dict):
            continue
        if v.get("active", False):
            inst = v.get("instrument")
            if inst:
                active_map[inst] = k
            else:
                log.warning(
                    "Gaussian migration: version %s is active but has no "
                    "instrument field — skipping in __active__ map", k
                )
    reg[_ACTIVE_MAP_KEY] = active_map
    try:
        from src.utils.integrity_events import emit_integrity_event
        emit_integrity_event(
            "GAUSSIAN_REGISTRY_MIGRATED", "INFO", "model_registry",
            {"active_map": active_map, "n_versions": len([
                k for k in reg if not _is_meta_key(k)
            ])}
        )
    except Exception:
        pass   # don't block migration on telemetry
    return reg
```

**`_load` (line 341–348)** — wrap the parsed dict in `_migrate_gaussian_registry()`:

```python
def _load(self) -> dict:
    if not self.reg_path.exists():
        return {}
    try:
        raw = json.loads(self.reg_path.read_text(encoding="utf-8"))
        return _migrate_gaussian_registry(raw)
    except Exception as e:
        log.warning(f"Gaussian registry load failed: {e}")
        return {}
```

**`promote_gaussian` (lines 400–498)** — change signature to keyword-only `instrument`:

```python
def promote_gaussian(
    self,
    version: str,
    *,
    instrument: Optional[str] = None,
    force: bool = False,
    max_regression: float = 0.01,
) -> tuple[bool, str]:
```

Inside the lock body, after the existing schema-version and GAP-3 checks succeed but **before** the "Derive current_active from registry scan" block (line 454):

```python
# Resolve instrument target for this promotion
if instrument is None:
    instrument = reg[version].get("instrument")
    if instrument:
        try:
            from src.utils.integrity_events import emit_integrity_event
            emit_integrity_event(
                "GAUSSIAN_PROMOTE_INSTRUMENT_INFERRED", "INFO", "model_registry",
                {"version": version, "instrument": instrument}
            )
        except Exception:
            pass
if not instrument:
    return False, (
        f"Gaussian promotion BLOCKED: cannot determine instrument for "
        f"{version}. Pass instrument= explicitly or re-register the entry "
        f"with an 'instrument' field."
    )
```

Replace `active_versions = [k for k, v in reg.items() if v.get("active", False)]` with an instrument-scoped scan:

```python
active_map = reg.setdefault(_ACTIVE_MAP_KEY, {})
current_active = active_map.get(instrument)   # may be None for first deploy

# Belt-and-braces: also scan for legacy entry-level active flag in case the
# active map is stale (e.g., manual edit). Map takes priority.
if current_active is None:
    for k, v in reg.items():
        if _is_meta_key(k) or not isinstance(v, dict):
            continue
        if v.get("active") and v.get("instrument") == instrument:
            current_active = k
            break
```

In all three "promote" branches (first deploy, current not found, success path), update the **write logic** to:

```python
# Deactivate any current active for THIS instrument only
if current_active and current_active in reg:
    reg[current_active]["active"] = False
reg[version]["active"] = True
active_map[instrument] = version   # __active__ map is source of truth
reg[_ACTIVE_MAP_KEY] = active_map
self._save(reg)
```

The cross-instrument entries with `active: True` are untouched. `_assert_single_active_per_instrument` (called from `_save`) enforces the new invariant.

**`get_active_gaussian` (lines 500–505)** — keep the no-arg signature for backward compatibility, add a new method:

```python
def get_active_gaussian(self) -> Optional[str]:
    """Legacy: returns active version for default instrument (EURUSD)."""
    return self.get_active_version("EURUSD")

def get_active_version(self, instrument: str) -> Optional[str]:
    reg = self._load()
    active_map = reg.get(_ACTIVE_MAP_KEY, {})
    return active_map.get(instrument)

def rollback_gaussian(self, instrument: str) -> tuple[bool, str]:
    """Promote the previous (by trained_at desc) version for the instrument."""
    reg = self._load()
    active_map = reg.get(_ACTIVE_MAP_KEY, {})
    current = active_map.get(instrument)
    if not current:
        return False, f"No active version for instrument {instrument!r}"
    # All entries for this instrument, sorted newest-first
    candidates = sorted(
        [k for k, v in reg.items()
         if not _is_meta_key(k) and isinstance(v, dict)
         and v.get("instrument") == instrument and k != current],
        key=lambda k: reg[k].get("trained_at", ""),
        reverse=True,
    )
    if not candidates:
        return False, "no_history"
    previous = candidates[0]
    return self.promote_gaussian(previous, instrument=instrument, force=True)
```

**Module-level wrappers (lines 1032–1048)** — propagate the kw-only arg:

```python
def promote_gaussian(version: str, *, instrument: Optional[str] = None,
                     force: bool = False, max_regression: float = 0.01) -> tuple[bool, str]:
    return _gaussian_registry.promote_gaussian(
        version, instrument=instrument, force=force, max_regression=max_regression
    )

def get_active_gaussian() -> Optional[str]:
    return _gaussian_registry.get_active_gaussian()

def get_active_version(instrument: str) -> Optional[str]:
    return _gaussian_registry.get_active_version(instrument)

def rollback_gaussian(instrument: str) -> tuple[bool, str]:
    return _gaussian_registry.rollback_gaussian(instrument)
```

### 2. `src/engines/heuristic_gaussian_engine.py`

**`__init__` (line 175)** — add kw-only `instrument` parameter:

```python
def __init__(self, config: dict, *, instrument: Optional[str] = None,
             preload_registry: bool = False):
    self.config = config
    self._instrument = instrument or config.get("instrument", "EURUSD")
    self._registry: Optional[GaussianRegistry] = None
    self._loaded_version: Optional[str] = None
    # ... rest unchanged
```

**`_load_registry` (lines 197–213)** — pass instrument to the loader and record loaded version:

```python
def _load_registry(self) -> None:
    registry_path = self.config.get("gaussian_registry_path", GAUSSIAN_REGISTRY_PATH)
    try:
        self._registry = GaussianRegistry(
            registry_path, instrument=self._instrument
        ).load()
        self._loaded_version = self._registry.active_version
        logger.info(
            "HeuristicGaussianEngine[%s]: loaded registry — active '%s'",
            self._instrument, self._loaded_version,
        )
    except (FileNotFoundError, RuntimeError) as exc:
        try:
            from src.utils.integrity_events import emit_integrity_event
            emit_integrity_event(
                "GAUSSIAN_NO_MODEL", "WARNING", "heuristic_gaussian_engine",
                {"instrument": self._instrument, "error": str(exc)}
            )
        except Exception:
            pass
        logger.warning(
            "HeuristicGaussianEngine[%s]: registry load failed (%s). "
            "Using config/default mu=%.2f, sigma=%.2f.",
            self._instrument, exc,
            self._mu_override or 0.0, self._sigma_override or 1.0,
        )
        self._registry = None
        self._loaded_version = None
```

**`GaussianRegistry` class (line 60)** — accept `instrument` and read from `__active__` map with legacy fallback:

```python
def __init__(self, registry_path: str = GAUSSIAN_REGISTRY_PATH,
             models_dir: str = GAUSSIAN_MODELS_DIR,
             instrument: str = "EURUSD"):
    self.registry_path = registry_path
    self.models_dir = models_dir
    self.instrument = instrument
    self._entries: dict = {}
    self._active_version: Optional[str] = None
```

In `load()` (line 70), filter meta keys when normalizing, then prefer `__active__[instrument]`:

```python
self._entries = {
    v: _normalize_registry_entry(v, entry)
    for v, entry in raw.items()
    if not v.startswith("__") and isinstance(entry, dict)
}

active_map = raw.get("__active__", {})
requested_version = active_map.get(self.instrument)

if requested_version is None:
    # Legacy fallback: scan entry-level active flag scoped by instrument
    matches = [
        v for v, e in self._entries.items()
        if e.get("active") and e.get("instrument") == self.instrument
    ]
    if matches:
        requested_version = matches[0]

if requested_version is None:
    raise RuntimeError(
        f"GaussianRegistry: no active version for instrument "
        f"{self.instrument!r} in {self.registry_path}"
    )

self._active_version = self._resolve_with_fallback(requested_version)
return self
```

**`compute` reload guard (lines 245–255)** — version-stamp compare:

```python
if self._registry is None and self._mu_override is None:
    self._load_registry()
    self._watcher.mark_loaded()
elif self._registry is not None and self._watcher.needs_reload():
    prev = self._loaded_version
    self._registry = None
    self._load_registry()
    self._watcher.mark_loaded()
    if self._loaded_version != prev:
        logger.info(
            "HeuristicGaussianEngine[%s]: reloaded — '%s' -> '%s'",
            self._instrument, prev, self._loaded_version,
        )
```

### 3. `src/training/trainer.py`

**`load_gaussian_model` (lines 406–453)** — add scaler audit before the existing read at line 438:

```python
# Audit missing-scaler failures so they show up in logs/integrity_events.jsonl
# rather than crashing silently. Preserves original exception types.
if bundle.get("scaler") is None:
    try:
        from src.utils.integrity_events import emit_integrity_event
        emit_integrity_event(
            "GAUSSIAN_MISSING_SCALER", "ERROR", "trainer",
            {"model_path": str(path), "model_name": name,
             "note": "re-train with current trainer to produce a scaler"}
        )
    except Exception:
        pass
    if "scaler" not in bundle:
        raise KeyError("scaler")   # preserve missing-key semantics
    raise RuntimeError(
        f"Gaussian model '{name}' has scaler=None. "
        f"Re-train with the current trainer to produce a calibrated scaler. "
        f"Refusing to load uncalibrated model."
    )
```

Note: `load_gaussian_model` takes `name: str`, not `(path, instrument=...)` as the prompt suggested. Instrument context isn't available at this call site — the integrity event uses `model_name` instead.

### 4. `scripts/auto_train_from_opportunities.py`

**`_maybe_promote` (line 151)** — add `instrument` parameter, thread to `promote_gaussian`:

```python
def _maybe_promote(version: str, instrument: str) -> None:
    # ... existing import-guard block
    ok, reason = promote_gaussian(version, instrument=instrument)
    # ... existing event emission
```

**Call site in `_train_instrument`** — already has `instrument`, pass it through: `_maybe_promote(version, instrument)`.

### 5. `scripts/training/phase5_calibration.py`

**Line 1618** — pass `instrument` argument:

```python
if get_active_gaussian() is None:
    promoted, reason = promote_gaussian(version, instrument=args.instrument or "EURUSD")
```

The `--instrument` argparse already exists (line 1347) so no new arg is needed.

### 6. `models/gaussian_registry.json`

No manual edit. `_migrate_gaussian_registry()` populates `__active__` lazily on first read.

## What is OUT of scope

- `_save_atomic`, `_PROMOTE_LOCK`, `_file_lock` — unchanged
- `_assert_single_active` (the generic helper at line 98) — unchanged; still used by tradenet/zone/RR registries
- `register_gaussian` — unchanged; entries already carry `instrument` field
- `list_gaussian`, `print_gaussian_leaderboard` — touched only to skip `__active__` meta key via `_is_meta_key(k)` filter inside their iteration
- PATCH-v3 schema check, GAP-3 corr floor, FIX-3 regression guard — all unchanged
- `RegistryWatcher` — unchanged; the version-stamp compare runs after `_load_registry()` re-reads the file
- The on-disk `gaussian_registry.json` is NOT pre-edited; migration runs lazily

## Verification

Run from repo root after implementation. The prompt's verification snippets need three fixes (signatures and free-function call sites) — corrected versions:

```powershell
# 1 — migration: legacy registry layout migrates cleanly on first read
python -c "
from src.core.model_registry import _migrate_gaussian_registry
old = {
    'gaussian_EURUSD_v1': {'active': True, 'instrument': 'EURUSD', 'trained_at': '2026-05-01'},
    'gaussian_XAUUSD_v1': {'active': True, 'instrument': 'XAUUSD', 'trained_at': '2026-05-01'},
}
migrated = _migrate_gaussian_registry(old)
assert migrated['__active__'] == {'EURUSD': 'gaussian_EURUSD_v1', 'XAUUSD': 'gaussian_XAUUSD_v1'}
print('PASS — migration:', migrated['__active__'])
"

# 2 — instrument isolation: EURUSD promotion does not touch XAUUSD
python -c "
import json, tempfile, pathlib
from src.core.model_registry import GaussianModelRegistry
d = pathlib.Path(tempfile.mkdtemp())
reg = GaussianModelRegistry(models_dir=d)
# seed (need register + promote; metrics dict must satisfy schema gate)
reg.register_gaussian('gaussian_EURUSD_v1', 'x.json', [], {'corr_expected_rr': 0.1}, instrument='EURUSD')
reg.register_gaussian('gaussian_XAUUSD_v1', 'y.json', [], {'corr_expected_rr': 0.1}, instrument='XAUUSD')
reg.register_gaussian('gaussian_EURUSD_v2', 'z.json', [], {'corr_expected_rr': 0.1}, instrument='EURUSD')
reg.promote_gaussian('gaussian_EURUSD_v1', force=True)
reg.promote_gaussian('gaussian_XAUUSD_v1', force=True)
reg.promote_gaussian('gaussian_EURUSD_v2', force=True)
assert reg.get_active_version('XAUUSD') == 'gaussian_XAUUSD_v1'
assert reg.get_active_version('EURUSD') == 'gaussian_EURUSD_v2'
print('PASS — XAUUSD untouched after EURUSD re-promote')
"

# 3 — rollback restores the previous EURUSD version
python -c "
import tempfile, pathlib
from src.core.model_registry import GaussianModelRegistry
d = pathlib.Path(tempfile.mkdtemp())
reg = GaussianModelRegistry(models_dir=d)
reg.register_gaussian('gaussian_EURUSD_v1', 'a.json', [], {'corr_expected_rr': 0.1, 'trained_at': '2026-05-01T00:00:00Z'}, instrument='EURUSD')
reg.register_gaussian('gaussian_EURUSD_v2', 'b.json', [], {'corr_expected_rr': 0.1, 'trained_at': '2026-05-15T00:00:00Z'}, instrument='EURUSD')
reg.promote_gaussian('gaussian_EURUSD_v1', force=True)
reg.promote_gaussian('gaussian_EURUSD_v2', force=True)
ok, ver = reg.rollback_gaussian('EURUSD')
assert ok and 'gaussian_EURUSD_v1' in ver
print('PASS — rolled back to:', ver)
"

# 4 — scaler=None guard raises RuntimeError, scaler missing key raises KeyError
python -c "
import json, tempfile, pathlib
from src.training.trainer import load_gaussian_model, MODELS_DIR
# Case A: scaler=None
p1 = MODELS_DIR / 'tmp_scaler_none.json'
p1.write_text(json.dumps({'model': {}, 'scaler': None}))
try:
    load_gaussian_model('tmp_scaler_none.json')
    print('FAIL A')
except RuntimeError as e:
    print('PASS A — RuntimeError:', e)
finally:
    p1.unlink(missing_ok=True)
# Case B: scaler key absent
p2 = MODELS_DIR / 'tmp_scaler_missing.json'
p2.write_text(json.dumps({'model': {}}))
try:
    load_gaussian_model('tmp_scaler_missing.json')
    print('FAIL B')
except KeyError as e:
    print('PASS B — KeyError:', e)
finally:
    p2.unlink(missing_ok=True)
"

# 5 — quick backtest, confirm no regression in active path
python scripts/backtest/run_backtest.py --instrument EURUSD --bars 500

# 6 — confirm integrity events landed
python -c "
import json, pathlib
events = [json.loads(l) for l in pathlib.Path('logs/integrity_events.jsonl').read_text().splitlines()[-50:]]
kinds = [e.get('event_type') for e in events]
print('Recent integrity events:', set(kinds))
assert 'GAUSSIAN_REGISTRY_MIGRATED' in kinds, 'migration event not logged'
"
```

### Success criteria

- Migration runs lazily, emits `GAUSSIAN_REGISTRY_MIGRATED` once
- EURUSD re-promotion leaves `__active__["XAUUSD"]` unchanged
- `rollback_gaussian("EURUSD")` returns `(True, "<prev_version>")`
- `scaler: None` raises `RuntimeError`; missing key raises `KeyError`; both emit `GAUSSIAN_MISSING_SCALER`
- Backtest completes clean, zero new errors
- Logs show `GAUSSIAN_REGISTRY_MIGRATED` event
