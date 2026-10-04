# CRT Contract Freeze + Code-Grounded Audit (MIAR workflow steps 1–3)

## Context

You froze the MIAR stage-family law (understanding-vs-decision separation) and set the
alignment workflow to **start with CRT**, one model at a time:
`1. Freeze contract → 2. Agree → 3. Audit code → 4. Fix drift → 5. Lock`.
This unit of work executes **steps 1–3 for CRT only**. Steps 4 (fix drift) and 5 (lock →
flip `alignment` to `ALIGNED`) are explicitly **out of scope** here.

Standing rules for this work: **ignore the governance ceremony** (no SESSION LOG mandate, no
`docs/current-findings.md` F-registration, no drift-protocol approval gate, no rehash — this is
intent/documentation only, zero production scoring behavior changes); **no defaults, no
fallbacks, no deletion of any intent**; **on any conflict/ambiguity, ask** (already done — see
Decisions).

What the exploration established:
- CRT's intent contract **already exists** as the MIAR `crt` entry (16 fields) +
  `locked_vocabulary`. "Freeze line-by-line" = ratify those clauses verbatim, plus the new
  stage-family row. There is **no** machine-readable freeze slot beyond `alignment`.
- **Two CRT surfaces.** `src/engines/crt_engine.py::compute` (fusion-slot scorer, delegating to
  `scoring_engine.compute_scores`) is **clean** — emits a bounded `score`, never a probability,
  never approves. The runtime **spine** `src/config_layer/crt_engine_v2.py::CRTEngine` (driven by
  `runtime/backtest_v2.py`) **approves + executes + vetoes** trades via the embedded
  `UltronRiskEngine.approve → open_trade → action=TRADE_OPENED`.
- The spine behavior **contradicts** the Stage-1 law ("CRT — may approve a trade? **Never**") and
  the charter's mandatory Stage-1 non-goal "never decide whether to trade" — which CRT's
  `explicit_non_goals` list currently **omits**. This is the core drift the audit surfaces.
- Three JSON↔MD wording mismatches block a byte-consistent freeze: `hypothesis`, `dependencies`,
  `authority_boundary`.

## Decisions (from user)

1. **Deliverable = single `.md`** — one freeze+audit doc; no `.json` twin.
2. **Reconcile now** — additively fix the JSON↔MD mismatches and add the missing mandatory
   Stage-1 non-goal to CRT's entry (additive only, no deletion).
3. **Document + propose fix** — include a step-4 unbundling proposal, clearly marked
   proposal-not-action.

`alignment` **stays `SEMANTIC_DRIFT`** (🟡): the audit finds unresolved drift (spine approval),
so it cannot flip to `ALIGNED` — that is step 5, out of scope.

## Approach

### Deliverable 1 (NEW): `docs/governance/crt_intent_contract.md`

Single doc, sections in this order (header + Verdict + Key-file-map mirror the existing
`*_lineage_audit.md` template so it reads as a repo-native governance artifact):

- **Header block** — `Program:` MIAR CRT freeze steps 1–3 · `Date (UTC):` 2026-07-28 ·
  `Authority:` intent-only, no scoring behavior changed · `Prerequisite:` CRT closure CLOSED
  (`crt_closure_report.md`) + `crt_formula_contract.md` Phase 2 (cite, do not reopen/duplicate).
- **Verdict** (fenced `text` block): `CRT_INTENT_CONTRACT = FROZEN (steps 1–3)`,
  `ALIGNMENT = SEMANTIC_DRIFT (unresolved)`, `PRIMARY_DRIFT = spine approves/executes trades`,
  `STEPS_4_5 = out of scope`.
- **§A — Frozen contract, line by line.** Table: `clause | verbatim text | source file:line |
  agreed`. Clauses = the 16 MIAR `crt` fields + the stage-family row (locked question +
  "may approve a trade? Never") + the four `locked_vocabulary` terms the contract leans on
  (Structure / Score / Probability / Confidence, verbatim from
  `MODEL_INTENT_AUTHORITY_REGISTER.md §0.3` / `miar_registry.json:748-761`) + the mandatory
  Stage-1 non-goal.
- **§B — Reconciliations applied** (additive; before→after, so nothing is silently changed):
  `hypothesis` (JSON "Sweep to retest…" → MD's fuller "Sweep→displacement→expansion→retest…",
  which matches the actual golden path); `dependencies` (MD "ontology geometries" → name
  `market_ontology` as in JSON); `authority_boundary` (JSON bare → MD "; may open structural path
  to risk"); and **added** non-goal `"never decide whether to trade"` (charter §46 mandate).
- **§C — Code audit (step 3).** Two-surface table: each contract clause → code evidence
  (file:line) → `ALIGNED` / `DRIFT`. Fusion-slot scorer = ALIGNED. Spine = DRIFT on
  "never approve" / "never decide whether to trade". Also record the pre-existing dual-math-path
  drift (FSM `RiskScore.final` vs `compute_scores` retest) that is the current 🟡 reason.
- **§D — TruthConflict (primary).** `Source A` (Stage-1 law / added non-goal) vs `Source B`
  (spine code: `crt_engine_v2.py` `UltronRiskEngine.approve` ~2016–2094 /
  `approve_with_soft_conf` ~1930–2012 / `open_trade`+`TRADE_OPENED` ~3096–3121) · evidence ·
  impact · recommendation (→ step 4).
- **§E — Proposed step-4 remediation (PROPOSAL, NOT ACTION).** Unbundle the Stage-1 structure-FSM
  from the embedded Stage-3/4 `UltronRiskEngine` **without deleting any intent** — the approval
  logic is relocated/owned by the correct stage, not removed. Sketch options only; no code.
- **§F — Key file map** (Role / Path table) and **§G — Final return** block
  (`FROZEN` / `STILL_DRIFTED` / `DO_NOT` reopen closure / `NEXT = step 4`).

### Deliverable 2 (EDIT, additive): `docs/governance/miar_registry.json` — `crt` entry (:116-154)

- `hypothesis` (:119) → `"Sweep to displacement to expansion to retest sequences mark actionable structure."`
- `authority_boundary` (:134) → append `; may open structural path to risk` (match MD).
- `explicit_non_goals` (:135-139) → **append** `"never decide whether to trade"` (additive).
- Bump top-level `updated` (:5). Leave `alignment: "SEMANTIC_DRIFT"` unchanged. `dependencies`
  already lists `market_ontology` — no JSON change there.

### Deliverable 3 (EDIT, additive): `docs/governance/MODEL_INTENT_AUTHORITY_REGISTER.md` §3.3 (:239-258)

- `dependencies` (:253) → name `market_ontology` (align to JSON).
- `explicit_non_goals` (:252) → add "**never** decide whether to trade".
- Optionally add a `notes` line pointing to `crt_intent_contract.md` (freeze audit trail).
  Update the §-rollup alignment table only if it currently mis-states CRT (keep 🟡).

## Critical files

- **Create:** `docs/governance/crt_intent_contract.md`
- **Edit (additive):** `docs/governance/miar_registry.json` (crt entry), `docs/governance/MODEL_INTENT_AUTHORITY_REGISTER.md` (§3.3)
- **Cite, do not modify:** `src/config_layer/crt_engine_v2.py` (spine: `UltronRiskEngine.approve`,
  `approve_with_soft_conf`, `open_trade`/`TRADE_OPENED`, `RiskScore.final`),
  `src/engines/crt_engine.py::compute`, `src/engines/scoring_engine.py::compute_scores`
  (weights `(0.35,0.25,0.20,0.20)`), `src/config_layer/state_identity.py` (9 states,
  VALID_TRANSITIONS, the "never alias" weight-identity note), `src/core/engine_runner.py`
  (fusion-slot wiring, DecisionEngine = sole EXECUTE/REJECT authority),
  `docs/governance/crt_closure_report.md`, `docs/governance/crt_formula_contract.md`,
  `docs/topics/crt-spine.md`.

## Verification

- `python -m pytest tests/test_miar_registry.py -q` → **must stay 9 passed** after the additive
  registry edits (adding a non-goal keeps `explicit_non_goals` non-empty; 17-entry order, intent
  uniqueness, single-owner matrix, locked-vocab keys all unaffected).
- Manual: confirm `miar_registry.json` `crt` entry and MD §3.3 are now byte-consistent on
  `hypothesis` / `dependencies` / `authority_boundary` / `explicit_non_goals`.
- Manual: confirm the freeze doc's §A clauses each carry a real `file:line` source and the §C
  audit rows each carry a real code `file:line`; spot-check 3–4 citations against source.
- No code changes → no behavior/parity tests needed (intent-only, per Authority line).

## Out of scope (do not do)

- Step 4 (fix drift) — no edits to `crt_engine_v2.py` / `UltronRiskEngine`; the §E remediation is
  a written proposal only.
- Step 5 (lock) — do **not** flip `alignment` to `ALIGNED`.
- Do not reopen CRT closure phases (`crt_closure_report.md` is frozen).
- No governance ceremony (SESSION LOG, F-registration, rehash) per the standing instruction.
