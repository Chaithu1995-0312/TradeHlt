# Documentation Drift Protocol

> **Long-form of the CLAUDE.md §6.2 thin rule of the same name.** §6.2 (Repository Truth
> Maintenance Doctrine) already owns drift *classification*, `TruthConflict` *surfacing*, the *Sync*
> mandates, and *CORRECTED-not-delete*. This doc adds the one missing invariant that ties them into a
> required completion step, and calibrates the user-approval gate. It **does not** restate §6.2 —
> each step below points to the §6.2 rule it operationalizes.
>
> **See also:** [`../current-findings.md`](../current-findings.md) (the conclusions) ·
> [`EPISTEMIC_INTEGRITY.md`](EPISTEMIC_INTEGRITY.md) (Program E-001) ·
> [`finding_dependency_audit.md`](finding_dependency_audit.md) (replay program + Audit Log) ·
> CLAUDE.md §4.0 (runtime truth precedence), §6.5 (Authority Ladder).

---

## The invariant

> **Every code / config / runtime-truth change triggers a documentation-truth decision.**

Discovering and *reporting* a discrepancy is necessary but **not sufficient**. The historical
failures in this repo (the F-007/F-016 version split-brain, feature-dim drift, "config illusion"
findings, and the F-038 "fix shipped" example below) were not code errors — they were moments where
reality moved and a recorded document was left asserting the old truth, which then **re-propagated to
future sessions**. A turn that finds drift is **incomplete** until the documentation-truth decision
is made and recorded.

The forbidden shape:

```
Reality changes  →  Documentation unchanged
```

The required shape:

```
Find drift → Classify → Present impact → [Gate] → Synchronize docs → Audit-trail entry
```

---

## The 5-step process

Each step is the §6.2 rule it enforces — follow the cross-reference, do not re-derive.

### Step 1 — Classify the drift  *(§6.2 rule 2)*
Compare code vs config vs runtime vs docs vs findings vs tests and label exactly one:
`ALIGNED` (no-op) · `DOC_DRIFT` (code/config/runtime wins → fix the doc) · `CODE_DRIFT` (doc wins →
fix the code) · `AMBIGUOUS` (authorities disagree, winner unclear → Step 3 gate). Runtime/config
authority follows the §4.0 precedence ladder (Tier 0 = `ACTIVE_VERSION`).

### Step 2 — Present impact  *(§6.2 rule 3 `TruthConflict` shape)*
State, explicitly: **what was believed**, **what is actually true**, **which artifacts are
affected** (findings / audits / topics / architecture / governance docs / memory), and **whether a
prior conclusion must be downgraded or reversed**. This is the `TruthConflict` tuple — *source A,
source B, evidence, impact, recommendation*.

### Step 3 — The approval gate  *(see "Gate calibration" below)*
- **Auto-fix (NO gate):** unambiguous `DOC_DRIFT`/`CODE_DRIFT` where the authoritative side is plain
  and **no registered conclusion changes** — e.g. a stale path, a corrected scope sentence, a
  citation move. Proceed and record (Steps 4–5).
- **Gate (user approval REQUIRED):** `AMBIGUOUS`/split-brain **or** any change that **downgrades or
  reverses a registered finding's status/confidence**, **or** edits an active config /
  `ACTIVE_VERSION`. Do **not** edit either side or invent a third answer — surface the `TruthConflict`
  and ask.

### Step 4 — Synchronize all affected artifacts  *(§6.2 rule 6 + §6.3 + §6.4 + Findings Mandate)*
A change is never made in isolation. After the source of truth is fixed, propagate the **same turn**:
findings ([Findings Mandate](../current-findings.md)), citations (§6.3 / `tests/test_doc_citations.py`),
topics (§6.4 / `tests/test_topic_docs.py`), the Repository Truths Index (CLAUDE.md §6.2), and any
memory file carrying the claim. **Never delete** — mark `CORRECTED` / `SUPERSEDED` / `INVALIDATED_BY`
and keep the row (§6.2 rule 4).

### Step 5 — Record an audit-trail entry  *(§6.2 rule 4 + E-001 "fix the SOURCE, not just chat")*
A correction that lives only in the chat reply is incomplete — the false claim stays recorded. Fix
every recorded instance, then log one Audit-Log row (format below) and state **how** the true fact
was verified (command / `file:line`), not just that the old one was wrong.

---

## Audit-trail format

Aligned to the existing **Audit Log** table in
[`finding_dependency_audit.md`](finding_dependency_audit.md). Every drift correction records:

| Field | Meaning |
|---|---|
| **Date** | when the correction landed |
| **Cause of drift** | why reality and the doc diverged (edit on wrong file, stale analysis, in-flight commit, …) |
| **Previous belief** | the recorded claim being corrected (quote it) |
| **New verified reality** | the corrected claim |
| **Verification method** | `static` (code/`file:line`) · `runtime` (executed / config-resolved) · `economic replay` (re-measured) |

---

## Completion criterion (the new floor)

This extends — does not replace — the §7.4 SESSION LOG close. A task that touches governed
code / config / runtime is **not complete** until:

1. Code changes finished
2. Tests pass
3. Runtime behavior verified
4. **Documentation impact assessed** (Steps 1–2 above)
5. Required (gated) doc updates **approved** (Step 3)
6. **Audit-trail entry recorded** (Step 5) and the §6 SESSION LOG appended

---

## Worked example — F-038 (the example that produced this protocol)

A real, in-flight split-brain caught while auditing this very protocol's premise.

- **Believed** (`docs/current-findings.md` F-038 body): *"Fix B SHIPPED — flipped
  `engine_runner.rr_fusion.enabled` to `false` in `configs/production/v2_multi_2026_04.json` (the
  file `ACTIVE_VERSION` points to)."*
- **Actually true at committed HEAD `1a8a260`:** `ACTIVE_VERSION` = `v2_multi_2026_04 - deepdeektry`,
  which the resolver (`src/config_layer/production_config.py:60` → `:116`,
  `Path(registry_dir)/f"{version}.json"`) loads as `v2_multi_2026_04 - deepdeektry.json`, where
  `rr_fusion.enabled: true`. **The fix-edit landed on a file that was not the active one** — the
  parenthetical "(the file `ACTIVE_VERSION` points to)" was *false* at HEAD.
- **Classification:** `AMBIGUOUS` (finding vs audit vs two config files disagreed) → resolved by §4.0
  Tier-0: the intended active config is `v2_multi_2026_04` (per F-016 + the working-tree
  `ACTIVE_VERSION`), which deploys `enabled: false`. The deploy becomes real only once that
  `ACTIVE_VERSION` flip is committed.
- **Verification method:** `static` + `runtime` — `git show HEAD:configs/production/ACTIVE_VERSION`
  vs working tree; resolver path traced; `enabled` read at `v2_multi_2026_04.json:34`
  (`false`) vs `v2_multi_2026_04 - deepdeektry.json:50` (`true`).
- **Audit row:** see [`finding_dependency_audit.md`](finding_dependency_audit.md) Audit Log
  (F-038 ⚠FLAG → RESOLVED) and the `CORRECTED:` note appended to the F-038 finding.
- **Residual (gated, NOT auto-resolved):** two config files still disagree
  (`…_04.json` `enabled:false`/`gaussian_impl:heuristic` vs `… - deepdeektry.json`
  `enabled:true`/`gaussian_impl:ml`) — surfaced as a `TruthConflict` for the user, per Step 3.

Lesson, in one line: **a code fix is not a deployed fix until the active-version pointer resolves to
it** — and the document asserting "shipped" must be verified against that resolution, not the edit.

---

## Authority

This protocol grants **no new authority**. It never bypasses the §6 SESSION LOG, write-authority /
path-guard, the `y/N` confirm, or the `APPROVE` promotion gate, and it changes no §4.0 precedence.
It is the procedural completion of §6.2's existing rules, tied to §6.5's Authority Ladder
(a corrected document earns no production authority — only documentation correctness) and to
Program E-001 (a pre-registration correction is evidence governance *succeeded*).
