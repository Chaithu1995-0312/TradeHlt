# Repository Truths Layer v2 — Types, Durable Tier, Funding Ledger

> Created: 2026-06-03 · Updated: 2026-06-03 · Milestone: Gov (knowledge-governance)
> Doc-only + test-only change. No config write, no rehash, no promotion. Extends the layer
> shipped earlier today (`docs/current-findings.md`, `CLAUDE.md` Repository Truths Index,
> `tests/test_current_findings.py`).

## Context

The findings layer works, but three reviewer enhancements make it a sharper roadmap filter:
1. **Type** — findings are currently undifferentiated; tagging them
   `ARCHITECTURE/ECONOMIC/GOVERNANCE/OPERATIONAL/RISK` makes them filterable.
2. **Durable tier** — re-validating stable empirical truths (e.g. *persistence ≠ discrimination*)
   every 90d is busywork that erodes signal. A `DURABLE` status with a **365d** horizon keeps the
   annual sanity check without a true never-expire bucket (the BitNet "dormant→live-gate" reversal
   proves "timeless" truths still decay — so nothing is exempt from re-check, only re-cadenced).
3. **Funding Ledger** — a *finding* is an observation; *funding* is capital allocation, and one
   finding (F-001) kills/funds many initiatives. Keep them adjacent but separate so a fresh session
   can't silently reopen a KILLED initiative. Lives in `current-findings.md`, **not** the progress
   registry (different axis; registry is in-flight ideas, and is itself stale at `v2`).

**Decisions locked (AskUserQuestion):** Q1 = `DURABLE` + annual re-affirm; Q2 = new Funding Ledger
in `current-findings.md` with Reopen Conditions.

## What exists (reuse, don't rebuild)
- `tests/test_current_findings.py` — extend its existing parse helpers (`_parse_findings`,
  `_field`) and status/freshness checks; don't restructure.
- `docs/governance/user-progress-registry.md` — the *in-flight ideas* axis. The Funding Ledger is
  the *capital-allocation* axis; they cross-reference, they don't merge.

---

## Deliverables

### 1. `docs/current-findings.md`
- **Schema block:** add `- Type:` (vocab `ARCHITECTURE|ECONOMIC|GOVERNANCE|OPERATIONAL|RISK`);
  add `DURABLE` to the Status enum; document per-status revalidation windows:
  `VALIDATED/OPEN = 90d · DURABLE = 365d · SUPERSEDED/RETIRED = exempt`.
- **Every finding F-001…F-012:** insert a `- Type:` line. Assignments:
  F-001/002/003/011 ECONOMIC · F-004/005/012 ARCHITECTURE · F-006/007/009 GOVERNANCE ·
  F-008/010 RISK.
- **Promote F-011 to `DURABLE`** (the canonical example: *persistence ≠ discrimination*),
  `Revalidate-by: 2027-06-01`. Others stay `VALIDATED`/`OPEN` (re-cadence on re-affirmation, not now).
- **New `## Funding Ledger` section** — one block per initiative:
  ```
  ### <Initiative> — <FUNDED|FROZEN|KILLED|RESEARCH|UNFUNDED>
  - Date:    YYYY-MM-DD
  - Evidence: F-xxx, F-yyy [, analysis link]
  - Reopen Conditions: <falsifiable trigger(s)>   (required for FROZEN/KILLED)
  ```
  Seed (~8, evidence-linked):
  | Initiative | Status | Evidence | Reopen |
  |---|---|---|---|
  | Liquidity V2 | KILLED | F-001, F-011 (Phase-0 FAIL) | ΔAUC ≥ +0.03 OOS **and** positive expectancy **and** cross-instrument pass |
  | TradeNet V2 | KILLED | F-001, F-005 | same Phase-0 gate |
  | Probability Surface V2 | KILLED | F-001, F-012 | same Phase-0 gate |
  | BitNet V2 (adaptive threshold) | FROZEN | F-004 | `bitnet_score_at_entry` dataset accrued + measured adaptive lift > static 0.55 |
  | Governance/execution wiring (integrity gate + drift→size-down) | FUNDED | F-001, F-006, F-008 | — |
  | Per-instrument session/throughput sweeps | FUNDED | F-003, F-009 | — |
  | ReplayMemory → deterministic advisory path | RESEARCH | F-012, F-008 | weight-0.0 measurement shows AUC lift beyond static features |
  | Execution-planner replay experiment (selection vs SL/TP) | RESEARCH | F-010, F-002 | — |

### 2. `CLAUDE.md`
- **Repository Truths Index:** add a `Type` column (keep ≤20 rows; currently 12). Add a one-line
  pointer beneath the table: *capital-allocation decisions derived from these findings → Funding
  Ledger in `docs/current-findings.md`.*
- **§6.2 Findings Mandate:** document (a) the `Type` tag, (b) `DURABLE` (365d) vs `VALIDATED/OPEN`
  (90d), (c) the Funding Ledger — initiative-level, cites findings, carries Reopen Conditions;
  **never silently revive a `KILLED`/`FROZEN` initiative — its Reopen Conditions must be met and a
  SESSION LOG entry filed.**

### 3. `tests/test_current_findings.py`
- Add `_VALID_TYPE`; assert every finding has `Type ∈ vocab`.
- Add `DURABLE` to `_VALID_STATUS` (it stays **non-terminal** → still freshness-checked at its 365d
  horizon; only `SUPERSEDED/RETIRED` exempt — unchanged).
- **Window-ceiling check** (enforces the tiering, prevents horizon abuse): for `VALIDATED/OPEN`
  assert `Revalidate-by − Validated ≤ 180d`; for `DURABLE` assert `≤ 400d`.
- **Funding Ledger checks:** parse `### <Initiative> — <STATUS>` blocks under `## Funding Ledger`;
  assert `STATUS ∈ {FUNDED,FROZEN,KILLED,RESEARCH,UNFUNDED}`; every `Evidence` `F-id` resolves to a
  finding block (cross-ref integrity); `FROZEN/KILLED` blocks carry a non-empty `Reopen Conditions`.
- Keep `_parse_findings` anchored to the `## Findings` section so Funding blocks (not `F-NNN`) are
  never misparsed as findings.

---

## Governance check (Five Questions)
Doc-only + additive test; no config `_WRITE_ROOTS`; no auto-promotion; git-replayable; strengthens
I1/I2 (conclusions and the capital decisions derived from them are now both explicit, dated,
evidence-linked). Compliant.

## Verification
- `pytest -k current_findings` → green; then (a) set a `VALIDATED` finding's `Revalidate-by` to
  +300d and confirm the window-ceiling check fails; (b) point a Funding-Ledger `Evidence` at a
  non-existent `F-999` and confirm the cross-ref check fails; revert both.
- `pytest tests/test_current_findings.py tests/test_topic_docs.py` → no regression.
- Cold-start dry-run: from `CLAUDE.md` alone, the index now shows Type per row and points to the
  Funding Ledger; the ledger shows KILLED/FUNDED initiatives + Reopen Conditions without opening
  any analysis doc.
- Append the §6 SESSION LOG entry (after exiting plan mode).

## Out of scope
- Migrating funding status into the progress registry (kept separate by design).
- An "axiomatic / never-expire" tier (rejected — `DURABLE` 365d is the floor; engineering
  invariants like *no-lookahead* already live in `goal.md`, not here).
- Auto-deletion (supersede, never delete — unchanged).
