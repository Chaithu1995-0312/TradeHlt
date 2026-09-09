# DECISION (v1 — composed WITHOUT packages 1–3)

```yaml
schema_version: "1.0"
package_id: RC-002-DEC-CHATGPT-001
kind: DECISION
cycle_id: RC-002
created_at: 2026-09-04T00:00:00Z
author_role: architect
author_model: chatgpt
claim_type: process
related_package_ids: []
status: PROPOSED
promise_rung_max_claim: PL-0
```

> **PRESERVED, NOT DISCARDED.** This draft was composed from the dossier alone — the three upstream
> packages were not in its bundle, and it said so rather than inventing them. Retained under §6.2
> rule 4. The re-run with all three packages lands in `DECISION.md`.

## Decision type

**NONE-OF-THE-ABOVE.** This cycle does not establish a repair target, retirement target, ontology
change, contract violation, or implementation defect. The unresolved question is semantic identity
and representability of a measured population whose identity remains UNKNOWN. Any further action
would require a separately authorized future turn.

## Evidence cited (by package_id)

- **EVIDENCE_DOSSIER** — 32/32 directional-contract rejection stands; 88/88 attribution stands;
  CHoCH timing-lag explanation falsified; original same-bar trend-bias-flip mechanism falsified;
  both Phase 4g base-rate statistics rendered vacuous; population identity remains UNKNOWN.
- **RC-002-CRIT-DEEPSEEK-001** — referenced in the dossier as the critique that identified the
  missing conditional base-rate control. **Full package not supplied in this review bundle**;
  conclusions beyond dossier references are UNKNOWN.
- **Grok PROPOSAL** — **NOT PROVIDED. UNKNOWN.**
- **Gemini CRITIQUE** — **NOT PROVIDED. UNKNOWN.**

## Semantic review closure

**VERDICT: `USER AUTHORIZATION REQUIRED`**

**Contract named:** no violated semantic contract has been established. F-074 remains intact and
continues to reject counter-directional SWEEP → DISPLACEMENT transitions. The dossier does not
establish that F-074 violates domain semantics, nor that the ontology requires a missing
representable construct. The measured population's identity is UNKNOWN. Therefore no
`CONFIRMED DEFECT`, `TEST / CONTRACT GAP`, `DOCUMENTATION GAP`, or other defect-class verdict is
established. The unresolved question is semantic meaning.

**CURRENT** — the repository implements a directional contract for DISPLACEMENT entry that rejects
candles moving opposite the founding sweep direction. The 32 bars are rejected deterministically.
No evidence in this cycle demonstrates the implementation violates its stated contract.

**INTENDED** — `UNKNOWN`. The cycle does not establish whether repository semantics intend
(A) no representable construct for this population, (B) a representable construct distinct from
DISPLACEMENT, or (C) some other interpretation.

**RECOMMENDED** — do not alter code, configuration, ontology, predicates, tests, or F-074 based on
RC-002. If the Principal wishes to pursue representability, authorize a separate semantic-definition
turn whose first task is to establish the population's identity before discussing representation.

## Position B disposition

**`INSUFFICIENT EVIDENCE`.** Position B originally rested on a mechanism that has been retracted.
The replacement "trend resumption" interpretation was also retracted after conditional base-rate
controls rendered its supporting statistics vacuous. Neither "reversal" nor "resumption" is
established and the population identity is UNKNOWN. Position B is neither confirmed nor disproved
by the evidence presently available.

## Input-package reconciliation

**Unable to determine.** Only the dossier's references to the three upstream packages are available.
Source A: UNKNOWN. Source B: UNKNOWN. Evidence: INSUFFICIENT PACKAGE CONTENT. Cross-model agreement
or conflict cannot be evaluated. **No winner is selected.** If package reconciliation is required,
review the actual package contents rather than dossier summaries.

## Principal decision request

Decide whether the repository should continue treating this population as an unidentified phenomenon
with no established semantic identity, or authorize a future semantic-definition review to determine
whether it represents a distinct market concept.

**Next actor:** Principal. **Next grant:** either CLOSE RC-002 with no semantic change, or AUTHORIZE
a new semantic-definition cycle focused solely on population identity. No implementation authority
requested.

---

## Executor adjudication (Claude, 2026-09-04)

### The bundle failure is the executor's, not the bridge's

The cycle README told the bridge to paste packages 1–3 alongside this prompt, and the generated
prompt repeated it — but the **bundle did not contain them**, so the instruction was a manual step
that could silently not happen. It didn't. **Fixed at the mechanism, not the instruction:** a new
`context_manifest_rc002_chatgpt.json` bakes all three package files into the composing turn's
`CONTEXT_BUNDLE.md` (now 10 docs, all `OK`), so this turn can no longer be run without them.

### Is the verdict robust to what it did not see?

Checked rather than assumed, package by package:

| Missing package | Its position | Would it move the verdict? |
|---|---|---|
| DeepSeek `CRITIQUE` | REPAIR the retraction | **No** — already executed; its substance is *in* the corrected dossier §5, which credits it by id |
| Grok `PROPOSAL` | `UNKNOWN_SWEEP_CHILD_MEMBERSHIP` is the honest default | **No** — converges on the same UNKNOWN |
| Gemini `CRITIQUE` | REPAIR: run a powered test before any identity claim | **No** — also refuses an identity claim now |

**All three independently land on "do not claim identity yet."** The verdict
(`USER AUTHORIZATION REQUIRED`) and the Position B disposition (`INSUFFICIENT EVIDENCE`) are
therefore **robust** to the missing content, and the draft's refusal to fabricate cross-model
agreement was correct behaviour.

### What IS impoverished: the Next Grant

The two grants offered — *close* or *authorize a new cycle to establish identity* — are the grants
available to someone who has not seen that **the identity work is already done and a runnable test
already exists**. With packages 2 and 3 present, a materially more concrete third grant exists:

> **Authorize the specific pre-registered test, on a named corpus, against a named candidate set** —
> Grok's five candidates with `UNKNOWN` as default, Grok's geometric falsifier (same-side extension
> past the swept extreme), Gemini's duration test and its 5-point pre-registration minimum, on the
> frozen Phase-1 admitted corpus.

That is not "a new cycle to establish identity"; it is the execution grant this cycle was built to
produce. The re-run should be able to offer it.

### One open item the re-run must not treat as settled

The **referent question** — which of `range_h_ref`/`range_l_ref`, the founding candle's own extreme,
or engine `SWEEP.price` Grok's falsifier should use — was asked of Gemini and **not answered**. Only
referent (2) is recoverable without a new resolver run, and under the active `htf_range` mode the
semantically correct referent is arguably (1), the unrecoverable one.
