# Plan — BNBUSDT "In-Spine Null" Synthesis Ledger + Findings Flip

## Context

Before stopping single-knob BNBUSDT sweeps and redirecting, the user wants a **synthesis**:
across every module/lever invoked in reaching the "no in-spine BNBUSDT edge under
`intrabar_touch`" conclusion, capture **what was BUILT · what was EXECUTED · what was MISSED** —
sourced **purely from docs/data already written** (no new backtests).

Exploration of the existing record (12 `docs/analysis/` docs + `current-findings.md` F-001–F-016)
surfaced three things that shape this deliverable:

1. **The conclusion is partly an overclaim.** Only *some* in-spine levers were actually tested
   (EMA gate, detection tier-2, consensus gate, shadow/TTL, session filter, exit-model). Three
   engines that run on **every candle — Gaussian, Zone Gate, RR — were never isolated** on
   BNBUSDT. The honest ledger must separate *tested-and-null* from *never-tested*.
2. **Existing ledgers are finding/edge-centric, not module-centric.** `current-findings.md`
   (F-001–F-016) and `alpha-ledger-recovery-2026-06-03.md` already record the conclusions; the
   user's "across modules" view is genuinely new → additive, not duplicative.
3. **This session overturned F-003** ("session policy is the proven lever," VALIDATED on the
   in-sample +20.59%). Per the §6.2 Findings Mandate, that flip must be recorded in the same turn.

**Goal:** a durable, module-centric map of the in-spine search — so the redirect decision is made
against an honest "what's actually been ruled out vs merely assumed-ruled-out" picture, and the
living ledger stays truthful. **Source-only-from-docs; no new runs; no source/config/ACTIVE_VERSION
change.**

## Deliverable 1 — Module-centric synthesis doc

New point-in-time doc `docs/analysis/bnbusdt-in-spine-ledger-2026-06-11.md` (per the
`docs/analysis/` convention — history, not living truth; links out to `current-findings.md` for
current verdicts). Organized **by module**, with a Built / Executed / Missed column each. Five
sections:

- **A. Production-spine levers TESTED → null / non-binding.** EMA gate (`crt_engine_v2.py:1405,
  1605`, byte-identical no-op), detection tier-2 (`:395,1707`, non-binding), consensus gate
  (`fusion_engine.py:158,733`, dormant weight=0.0), shadow/TTL (`:374,2076`, advisory-only Phase
  4b), session filter (`:2604`, OOS-falsified this session), exit-model swap (`:353`, governing —
  PF 0.94→0.46). Each row cites its evidence doc + headline number.
- **B. Production-spine modules NEVER ISOLATED (the honest gap).** Gaussian engine
  (`heuristic_gaussian_engine.py` — note `NoOpScorer` active per run logs), Zone Gate
  (`zone_gate_engine.py`), RR engine (`rr_engine.py`), regime weights/RegimeGovernor, dynamic
  threshold, belief gate (dormant), conflict-resolution policy, UltronRiskGate (live-only, not in
  backtest spine), TrapValidator. Cross-ref existing findings F-005, F-012, F-013, F-006 (already
  document several as built-but-orphaned/sidecar) so this isn't re-derived.
- **C. Research-pipeline measurements (SEPARATE context).** Forensics World-A
  (`bnbusdt-forensics-2026-06-10.md`, gross E[R]≈0), conditional-edge (130 tests / 0 BH survivors),
  M4 qualification (`edge-discovery-m4-intrabar-2026-06-10.md`, PROMOTE: none), process
  characterization (direction entropy 0.999 = coin-flip), spine-as-hypothesis (PF 0.805). **Carry
  the pipeline-disambiguation caveat** (`bnbusdt_execution_forensics.md`): research forward_walk
  (fixed SL/TP, flat 12bps) ≠ production CRT engine — their "no edge" verdicts are different
  measurement contexts and not interchangeable.
- **D. Coherence gaps / unresolved contradictions** (the most valuable "missed").
  (i) Funnel binding-constraint **drift**: 64 session rejects (`roi-funnel-diagnosis-2026-05-30`)
  vs 29 zone rejects + DISP→EXPANSION 5% binding (`funnel-diagnosis-2026-06-06`) — config/code
  drift between measurements, unreconciled. (ii) **Config-version drift** across the evidence base
  (some runs v2, gate-contribution on v4) → not all numbers are same-config comparable.
  (iii) Stale `_BASELINE` constant (already spawned as a fix task). (iv) The overclaim correction
  from §1.
- **E. Net conclusion + what it licenses.** What is genuinely ruled out (the 6 tested levers +
  research behaviors) vs what is merely *assumed* ruled out (the 3 un-isolated engines). Frame the
  redirect options (other instruments / research M4 / spine-or-exit re-examination) — but leave the
  **redirect decision to the user** (next turn).

## Deliverable 2 — Governed findings-ledger flip (`docs/current-findings.md`)

Per §6.2 append-discipline (never delete a finding; refine/supersede with dated note + evidence):

- **Add F-017** · "Session policy is NOT a promotable BNBUSDT lever under realistic exits + OOS"
  — Type ECONOMIC, VALIDATED 2026-06-11, Evidence
  `docs/analysis/session-sweep-bnbusdt-2026-06-11.md` (KEEP_INCUMBENT; V3 +0.21%/mo IS → +0.07%/mo
  OOS PF 1.09; V2 flips negative) + the new synthesis doc. `Reversal:` the in-sample +20.59% was
  regime overfitting; `Supersedes:` refines F-003.
- **Refine F-003** (do not delete): add a dated Note that its in-sample evidence is OOS-falsified
  under `intrabar_touch` by F-017, and that the published +4.91%/PF1.79 baseline is stale
  (true governing-exit V0 = 15 / PF1.03 / +0.12%). Status flip toward SUPERSEDED-by-F-017 (mirror
  the F-007→F-016 pattern already in the file).
- Note (do not fix here): `tests/test_current_findings.py::test_index_and_doc_agree_on_nonterminal_ids`
  is **already RED on `patch`** (the CLAUDE.md "Repository Truths Index" was dropped on this branch).
  Adding F-017 does not newly break it; rebuilding that index is a separate scoped change.

## Sourcing (read-only inputs — no new runs)

All from existing docs already in the repo: the 12 `docs/analysis/` BNBUSDT docs inventoried
(roi-baseline 05-29, roi-funnel-diagnosis 05-30, session-sweep 06-01 & 06-11, gate-contribution
06-03, funnel-diagnosis 06-06, exit-model-adoption 06-10, bnbusdt-forensics 06-10,
bnbusdt-conditional-edge 06-10, edge-discovery-m4 06-10, bnbusdt_execution_forensics,
bnbusdt_process_analysis), `current-findings.md` F-001–F-016, and `assistant_project.md` /
`MEMORY.md`. Module file:line anchors already gathered in this session's exploration. **No
`results/*` regeneration** — cite the existing JSON artifacts as-is.

## Critical files

- **Create:** `docs/analysis/bnbusdt-in-spine-ledger-2026-06-11.md` (Deliverable 1).
- **Edit (governed, append-discipline):** `docs/current-findings.md` (F-017 add + F-003 refine).
- **Read-only evidence:** the 12 analysis docs above; `current-findings.md`; module anchors in
  `src/config_layer/crt_engine_v2.py`, `src/core/fusion_engine.py`, `src/core/engine_runner.py`.
- **Optionally update** `docs/analysis/README.md` index with the new doc's one-line row (matches
  the existing pattern there).

## Verification

- **Doc-only, no system change:** `git status` shows only the two `docs/` files (+ optional README
  row); no `src/`, `configs/`, or `ACTIVE_VERSION` diff.
- **Link/ID integrity:** every `docs/analysis/...` and `file:line` citation in the new doc resolves;
  every `F-0NN` referenced exists in `current-findings.md`.
- **Findings freshness:** F-017 has non-empty Evidence + Validated/Revalidate-by dates (schema in
  `current-findings.md` §Schema). Run `pytest tests/test_current_findings.py` to see its state —
  expect the **pre-existing** index-agreement failure (note it, do not mask it); confirm no *new*
  failure is introduced by F-017's schema.
- **Faithfulness:** spot-check that each headline number in the synthesis matches its source doc
  (e.g. PF 0.94→0.46 vs `exit-model-adoption`; 130 tests/0 survivors vs `bnbusdt-conditional-edge`;
  KEEP_INCUMBENT vs `session-sweep-...06-11`). No number originates outside the docs.
