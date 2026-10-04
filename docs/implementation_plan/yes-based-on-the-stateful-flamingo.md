# Plan — Codify the Truth-Maintenance Doctrine + Active-Version Mandate into CLAUDE.md

> Created: 2026-06-11 · Updated: 2026-06-11 · Scope: doc-only (no code, no config writes)

## Context — why this change

Across this session we diagnosed **F-016 (split-brain version truth)** and a broader pattern:
findings, docs, and runtime can disagree, and an agent reading stale history infers the wrong
state. The proposed remedy was a "Repository Truth Maintenance Doctrine."

Exploration reversed two assumptions and reframed the work:

1. **The runtime is already correctly file-driven.** `get_active_version()`
   ([production_config.py:60](src/config_layer/production_config.py)) fail-fasts (`RuntimeError`)
   on a missing/empty `ACTIVE_VERSION`; unknown override keys raise `ValueError`
   ([config_builder.py:190](src/config_layer/config_builder.py)). **F-016's split-brain exists
   only at the agent/LLM reasoning layer** — so the fix is doctrinal (a CLAUDE.md mandate to read
   `ACTIVE_VERSION` first), not code.

2. **The truth-maintenance scaffolding is ~85% built**, but CLAUDE.md is missing the doctrine the
   rest of the repo *already cites*. Four forward-references point at CLAUDE.md mandates that do
   not exist yet:
   - `docs/topics/readme.md:5` → "CLAUDE.md **§6.1** Topic Sync Mandate" (collides — §6.1 is
     Intelligence Compounding)
   - `docs/current-findings.md:17` → "CLAUDE.md **§6.2** Findings Mandate" (absent)
   - `docs/architecture/trigger-vocabulary.md:82` → "CLAUDE.md **§6.3** Citation Sync Mandate"
     (absent)
   - `current-findings.md:8` + `trigger-vocabulary.md:79` → "CLAUDE.md → **Repository Truths
     Index**" (absent)

**Intended outcome:** make those four references real and self-consistent, add the Active-Version
mandate that closes F-016 at the reasoning layer, and wrap them under one "Truth Maintenance
Doctrine" — *without creating new docs* (which is itself the doctrine's Rule 1/Rule 5). Existing
living substrate (`current-findings.md`, `analysis/readme.md`, `knowledge-map.md`,
`test_doc_citations.py`) is referenced, not duplicated.

## Scope (confirmed with user)

- **Doc-only.** No code edits, no config writes.
- **Flag — don't touch — the pointer suffix.** `configs/production/ACTIVE_VERSION` =
  `v2_multi_2026_04 - deepdeektry`; the ` - deepdeektry` suffix is the orphaned F-006 residual.
  Documented as a known finding here; **no write** — defer to a separate governed change that
  verifies the registry key + `promotion_log.jsonl` PROMOTED entry first.

## Numbering reconciliation (the one judgment call)

§6.1 is entrenched as **Intelligence Compounding** (referenced by CLAUDE.md §7.4, `MEMORY.md`, and
`docs/architecture/intelligence-compounding.md`). The docs' cited scheme wants §6.1=Topic Sync,
§6.2=Findings, §6.3=Citation Sync. Resolution that **minimizes total reference churn**:

| Mandate | Target § | Matches existing citation? | Action |
|---|---|---|---|
| Intelligence Compounding | §6.1 (unchanged) | — | leave as-is |
| **Truth Maintenance Doctrine** (umbrella + Repository Truths Index + Findings Mandate) | **§6.2** | ✅ `current-findings.md:17` cites §6.2 Findings | add |
| **Citation Sync Mandate** | **§6.3** | ✅ `trigger-vocabulary.md:82` cites §6.3 | add |
| **Topic Sync Mandate** | **§6.4** | ❌ docs cite §6.1 | add + fix 2 refs |

Net: defining §6.2/§6.3 at the cited numbers validates two references *for free*; only the
Topic-Sync §6.1→§6.4 reference needs editing (2 occurrences).

## Changes

### 1. `CLAUDE.md` — new `§4.0 Active Version Resolution (Mandatory)` (lead-in to §4 Constraints)
Codify the user-authored content:
- **Runtime Truth Precedence (Tier 0–4):** `ACTIVE_VERSION` (Tier 0) > schema physically present
  in code / `CRTConfig`+`ConfigBuilder` (Tier 1) > `promotion_log.jsonl` (Tier 2) >
  `assistant_project.md`/historical findings (Tier 3) > LLM memory (Tier 4). Lower tiers describe
  history; never override higher.
- **`ORIENT_RUNTIME` ritual (A–E):** read `configs/production/ACTIVE_VERSION` → load that config →
  verify schema compat vs `CRTConfig`/`ConfigBuilder` → record `ACTIVE_VERSION=<v>` → only then
  plan/execute. Version truth is **branch-scoped**. If a config carries keys absent from
  `CRTConfig` → conclude "schema/version mismatch," do **not** migrate or execute (cites the real
  `ValueError` at [config_builder.py:190](src/config_layer/config_builder.py)).
- One-line cross-link to §6.2.

### 2. `CLAUDE.md` — new `§6.2 Repository Truth Maintenance Doctrine` (sibling to §6.1)
- **The 7 rules** (condensed): existing-docs-first; detect drift (ALIGNED / DOC_DRIFT[code wins] /
  CODE_DRIFT[doc wins] / AMBIGUOUS[human]); never silently resolve conflicts → emit a
  `TruthConflict` and ask; preserve history via `SUPERSEDED_BY`/`INVALIDATED_BY`/`BRANCH_SPECIFIC`
  (never delete); minimize doc count; mandatory cross-sync; human confirmation on multi-authority
  disagreement.
- **Points at** (does not duplicate) the living substrate: `docs/current-findings.md`,
  `docs/analysis/readme.md` (point-in-time, not living), `docs/knowledge-map.md`,
  `docs/timeline.md`.
- **Findings Mandate** (the §6.2 the docs cite): validate/overturn a conclusion → add/flip a
  finding in the same turn; set `Validated`/`Revalidate-by`, cite `Evidence`, fill `Reversal`;
  never delete. Mirror the rule already stated in `current-findings.md:17–21`.
- **Repository Truths Index (thin, always-loaded):** compact bulleted list of **active** findings
  (id · one-line verdict · confidence) extracted from `current-findings.md`'s non-SUPERSEDED rows,
  with a pointer to the full record. Satisfies `current-findings.md:8` ("the thin always-loaded
  index lives in CLAUDE.md"). Kept fresh by the Findings Mandate; covered by
  `tests/test_current_findings.py`.

### 3. `CLAUDE.md` — new `§6.3 Citation Sync Mandate`
Codify what `trigger-vocabulary.md:82` already references: when code that a `path:line · Symbol`
citation points at moves, update the citation in the same turn; use
`docs/architecture/citation-map.generated.md` to find them; enforced by
`tests/test_doc_citations.py` (±30-line drift window).

### 4. `CLAUDE.md` — new `§6.4 Topic Sync Mandate`
Codify what `docs/topics/readme.md:5` references: when you change code a topic covers, update that
**one** topic doc the same response, bump `Updated:`, append a dated Discussion entry; enforced by
`tests/test_topic_docs.py`. This is the `Sync` Tier-2 trigger's doctrine home.

### 5. Fix the dangling references (the drift this doctrine exists to kill)
- `docs/topics/readme.md:5` — `§6.1 Topic Sync Mandate` → `§6.4 Topic Sync Mandate`.
- `docs/architecture/trigger-vocabulary.md:82` — the `§6.1` in "The CLAUDE.md §6.1/§6.3 mandates"
  → `§6.4` (the `§6.3` Citation Sync reference becomes valid once §6.3 exists — no edit).

## Files to modify
- `CLAUDE.md` — add §4.0, §6.2, §6.3, §6.4 (4 additive sections; Intelligence Compounding §6.1
  untouched).
- `docs/topics/readme.md` — 1 ref fix (§6.1→§6.4).
- `docs/architecture/trigger-vocabulary.md` — 1 ref fix (§6.1→§6.4).

No other files. No `src/`, no `configs/`.

## Verification (read-only / tests)
1. `pytest tests/test_doc_citations.py tests/test_topic_docs.py tests/test_current_findings.py`
   — confirm citation/topic/findings invariants still pass after edits.
2. Grep proof that no dangling CLAUDE.md mandate references remain:
   `rg "§6\.\d Topic Sync|§6\.\d Findings|§6\.\d Citation Sync|Repository Truths Index"` across
   `docs/` → every hit now resolves to a section that exists in `CLAUDE.md`.
3. Confirm §6.1 (Intelligence Compounding) text and its §7.4/`MEMORY.md` references are unchanged
   (no collateral renumbering).
4. Manual read-through: the Tier 0–4 precedence + `ORIENT_RUNTIME` correctly names
   `configs/production/ACTIVE_VERSION` and the real `ValueError` failure path.

## Out of scope (explicit)
- The 8-phase "trustworthy laboratory" audit (reachability / metric-integrity / determinism /
  telemetry / test-gap / readiness reports) — deferred to a follow-up plan.
- Any new trading doctrine (immediate-entry / tiny-SL / reject-first).
- Cleaning the `ACTIVE_VERSION` ` - deepdeektry` suffix (F-006) — flag only.
- No new standalone docs created (doctrine Rule 5).

---
📝 SESSION LOG ENTRY
Date: 2026-06-11
Topic: Plan — codify Truth-Maintenance Doctrine + Active-Version mandate into CLAUDE.md (doc-only)
Decision/Output: Plan written. Runtime already file-driven (get_active_version fail-fast) → F-016 is a reasoning-layer fix. Found 4 forward-refs to non-existent CLAUDE.md mandates (§6.1 Topic Sync collides; §6.2 Findings, §6.3 Citation Sync, Repository Truths Index absent). Resolution: §6.1 stays Intelligence Compounding; add §4.0 Active Version Resolution + §6.2 Truth Maintenance (umbrella + Findings Mandate + Truths Index) + §6.3 Citation Sync + §6.4 Topic Sync; fix 2 §6.1→§6.4 refs. Pointer suffix flagged, not touched.
Belief Update / ROI / Goal: Goal: zero silent truth divergence (intelligence compounding). Belief: the split-brain is documentation entropy, not a runtime bug — and the cure already exists, just uncited. Knowledge ROI: high — defining §6.2/§6.3 at the numbers docs already cite validates 2 refs for free. Action: codify, don't create; defer lab audit.
Open Questions: Should the thin Repository Truths Index list all active F-### inline (maintenance burden) or a tighter top-N? Confirm at execution from current-findings.md active rows.
Next Step: On approval, apply the 6 edits and run the 3 doc tests.
---