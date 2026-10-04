# Documentation Drift Protocol + F-038 live reconciliation

## Context

**Why this change.** A repository governance discussion identified a missing invariant:
> *Every code/config/runtime-truth change must trigger a documentation-truth decision.*

The motivating example is **F-038** (the rr_fusion "fix"). Investigation this turn proved the
example is not hypothetical — it is a **live, in-flight split-brain right now**:

| Source | Says | rr_fusion deployed? |
|---|---|---|
| `current-findings.md:517,531` (F-038 header/body) | "FIX SHIPPED — disabled in `v2_multi_2026_04.json` (the file ACTIVE_VERSION points to)" | claims YES |
| **committed HEAD** `configs/production/ACTIVE_VERSION` | `v2_multi_2026_04 - deepdeektry` → loads `…- deepdeektry.json:50` `enabled: true` | **NO** |
| **working-tree** `ACTIVE_VERSION` (uncommitted `M`) | `v2_multi_2026_04` → loads `v2_multi_2026_04.json:34` `enabled: false` | YES (only once committed) |
| `docs/governance/finding_dependency_audit.md:94` (untracked, today) | "Fix NOT deployed to prod config" ⚠FLAG | NO (correct vs HEAD) |

The resolver is `src/config_layer/production_config.py:60` (`get_active_version`) → `:116`
(`Path(registry_dir)/f"{version}.json"`). The fix-edit landed on `v2_multi_2026_04.json`, but at
HEAD that file was **not** the active one (the deepdeektry variant was). So the finding's
parenthetical "(the file ACTIVE_VERSION points to)" was **false at HEAD** — a documentation claim
diverged from deployed reality, exactly the failure the protocol must prevent.

**Intended outcome.** (1) Encode the missing invariant as durable doctrine; (2) use F-038's live
drift as its worked first application — reconcile the truth so docs match deployed reality.

**Key constraint discovered — most of this already exists.** CLAUDE.md §6.2 (Repository Truth
Maintenance Doctrine) already covers ~80% of the proposed protocol: drift classification
(`ALIGNED`/`DOC_DRIFT`/`CODE_DRIFT`/`AMBIGUOUS` = rule 2), `TruthConflict` surfacing + "never
silently resolve, ask the user" (rule 3), Sync mandates (rule 6 + §6.3 citation + §6.4 topic +
Findings Mandate = Step 4), and CORRECTED/SUPERSEDED-not-delete + audit logs (rule 4, E-001 "fix the
SOURCE" = Step 5). The protocol must **extend**, not duplicate, these — per §6.2 rule 1
(existing-doc-first) and rule 5 (minimize doc count).

## User decisions (locked)

- **Placement:** thin rule inside CLAUDE.md §6.2 → long-form `docs/governance/` doc (mirrors the
  §6.1↔`intelligence-compounding.md`, §6.5↔`config-first-doctrine.md` pattern).
- **Approval-gate strength:** auto-fix clear `DOC_DRIFT` (code wins); **require user approval only
  for AMBIGUOUS/split-brain conflicts or conclusion downgrade/reversal**. Matches existing §6.2
  rules 2–3; avoids friction on routine doc fixes.
- **F-038:** reconcile now as the worked first application.

## Part A — Doctrine

### A1. Long-form doc: `docs/governance/DOCUMENTATION_DRIFT_PROTOCOL.md` (new)

Self-contained long-form, written as the expansion of the §6.2 thin rule (NOT a re-statement of
§6.2). Sections:

- **The invariant.** "Every code/config/runtime-truth change triggers a documentation-truth
  decision." Reporting a discrepancy is necessary but **not sufficient** — the turn is incomplete
  until the doc decision is made and recorded.
- **The 5-step process**, each cross-linking the §6.2 rule it operationalizes rather than redefining
  it: (1) Classify drift [§6.2 rule 2] → (2) Present impact: believed vs true, artifacts affected,
  whether a conclusion downgrades [§6.2 rule 3 `TruthConflict` shape] → (3) **Gate** [see A3] →
  (4) Synchronize all affected artifacts [§6.2 rule 6 + §6.3 + §6.4 + Findings Mandate] →
  (5) Audit-trail entry [§6.2 rule 4 + E-001 "fix the SOURCE not just chat"].
- **Audit-trail format**, aligned to the existing `finding_dependency_audit.md` Audit Log table:
  `Date · Cause of drift · Previous belief · New verified reality · Verification method
  (static / runtime / economic replay)`.
- **Completion criterion** (the genuinely new floor): a task touching governed code/config/runtime
  is not complete until — code done · tests pass · runtime verified · **doc-impact assessed** ·
  required (gated) doc updates approved · **audit entry recorded**. Extends the §7.4 SESSION LOG
  close, does not replace it.
- **Worked example:** the corrected F-038 story (from Part B) as the canonical illustration.
- **Authority note:** grants NO new authority — never bypasses §6 SESSION LOG, write-authority /
  path-guard, `y/N`, or the `APPROVE` promotion gate (consistent with every other §6.x doctrine).
  Ties to §6.5 Authority Ladder and E-001.

### A2. Thin rule in `CLAUDE.md` §6.2 (edit)

Insert a short **"Documentation Drift Protocol"** subsection within §6.2 (after the seven rules,
before the Findings Mandate), 4–8 lines: state the invariant + the gate + completion-criterion in
one paragraph, then point to the long-form doc. Add the doc to the §2 companion-docs table and to
the §6.2 record-systems pointer line. No renumbering of other sections.

### A3. The approval gate (the one true delta)

State the calibrated rule explicitly so it does not contradict §6.2 rule 2's auto-fix:
- **Auto-fix (no gate):** unambiguous `DOC_DRIFT` where code/config/runtime is plainly authoritative
  and no conclusion changes (e.g. a stale path, a corrected scope sentence).
- **Gate (user approval required):** `AMBIGUOUS`/split-brain (two authorities disagree, winner
  unclear) **or** any change that downgrades/reverses a registered finding's status/confidence, or
  edits an active config / `ACTIVE_VERSION`.

### A4. Enforcement (recommended, consistent with `project_doctrine_test_enforcement`)

This repo turns prose mandates into test floors. Add a lightweight `tests/governance/` test
asserting: (a) `docs/governance/DOCUMENTATION_DRIFT_PROTOCOL.md` exists and contains the invariant
sentence + the 5 step headers; (b) the §6.2 thin-rule pointer to it exists in `CLAUDE.md`. Mirror
the existing `tests/test_current_findings.py` / `test_session_log.py` style (string/section
presence, not behavioral). Keep it minimal — the gate and completion-criterion are process, not
unit-testable.

## Part B — F-038 live reconciliation (the worked first run of the protocol)

Apply the protocol to its own example. Classification = **AMBIGUOUS → resolved by §4.0 Tier-0**
(deployed runtime truth wins): the intended active config is `v2_multi_2026_04` (per F-016 doctrine
and the working-tree `ACTIVE_VERSION`), which deploys `enabled: false`.

1. **Establish canonical truth.** Confirm `ACTIVE_VERSION = v2_multi_2026_04` (working-tree value)
   is the intended Tier-0 truth → resolves to `v2_multi_2026_04.json` (`rr_fusion.enabled: false`).
   The HEAD value (`…- deepdeektry`, `enabled: true`) is the stale state the fix supersedes.
2. **Correct F-038 finding** (`docs/current-findings.md` ~`:531`): append a `CORRECTED:` note to the
   "Fix B SHIPPED" paragraph — at committed HEAD `ACTIVE_VERSION` pointed to
   `v2_multi_2026_04 - deepdeektry` (`enabled: true`), so the parenthetical "(the file ACTIVE_VERSION
   points to)" was false at HEAD; deployment is real only with `ACTIVE_VERSION=v2_multi_2026_04`
   committed. **Preserve history — do not delete** (§6.2 rule 4).
3. **Resolve the audit FLAG** (`docs/governance/finding_dependency_audit.md`): flip F-038 ⚠FLAG →
   RESOLVED, refresh the F-016 row note (`ACTIVE_VERSION` working-tree flip), and add a dated
   **Audit Log** row in the protocol's format. (File is untracked — also note it should be committed.)
4. **Surface the residual TruthConflict (gate, do NOT auto-resolve):** two config files now disagree
   — `v2_multi_2026_04.json` (`enabled: false`, `gaussian_impl: heuristic`) vs
   `v2_multi_2026_04 - deepdeektry.json` (`enabled: true`, `gaussian_impl: ml`). Per the user's
   gate, present this as a `TruthConflict` and **ask the user** whether the deepdeektry variant
   should be archived/removed or kept. Do not delete it unprompted.
5. **Memory:** update the F-038 memory file (`project_zone_gate_topk_config.md`, which carries the
   F-038 record) with the deploy-state correction; add the protocol as a new doctrine memory +
   `MEMORY.md` index line.

## Critical files

- **New:** `docs/governance/DOCUMENTATION_DRIFT_PROTOCOL.md`; `tests/governance/test_documentation_drift_protocol.py`
- **Edit:** `CLAUDE.md` (§6.2 thin rule + §2 table row); `docs/current-findings.md` (F-038 CORRECTED note);
  `docs/governance/finding_dependency_audit.md` (FLAG→RESOLVED + audit row + F-016 note)
- **Reference (read, do not duplicate):** `docs/governance/EPISTEMIC_INTEGRITY.md`,
  `docs/architecture/intelligence-compounding.md` (long-form pattern),
  `docs/research-readiness/config-first-doctrine.md` (long-form pattern)
- **Config decision (gated, no edit without approval):** `configs/production/ACTIVE_VERSION`,
  `configs/production/v2_multi_2026_04 - deepdeektry.json`
- **SESSION LOG:** append the §7.4 block to `assistant_project.md` (governed-doc change → codebase log).

## Verification

1. `pytest tests/governance/test_documentation_drift_protocol.py tests/test_current_findings.py -q`
   — new floor green; findings-index invariant (every non-terminal F-id ↔ table) still green.
2. `pytest tests/test_doc_citations.py tests/test_topic_docs.py -q` — no citation/topic drift from
   the edits.
3. Manual truth re-check: `git show HEAD:configs/production/ACTIVE_VERSION` vs working tree, and
   confirm `current-findings.md` F-038 + `finding_dependency_audit.md` now agree with the working-tree
   deployed reality (no remaining contradiction between the three sources in the Context table).
4. Confirm the SESSION LOG block is both shown and persisted to `assistant_project.md` (§6 mandate).
