# DECISION — RC-002 (v2, composed WITH all three upstream packages)

```yaml
schema_version: "1.0"
package_id: RC-002-DEC-CHATGPT-002
kind: DECISION
cycle_id: RC-002
created_at: 2026-09-04T02:00:00Z
author_role: architect
author_model: chatgpt
claim_type: process
related_package_ids:
  - RC-002-CRIT-DEEPSEEK-001
  - RC-002-PROP-GROK-001
  - RC-002-CRIT-GEMINI-001
  - RC-002-DEC-CHATGPT-001
status: PROPOSED
promise_rung_max_claim: PL-0
```

> **SUPERSEDES `RC-002-DEC-CHATGPT-001`** (`DECISION_v1_dossier_only.md`, composed without packages
> 1–3, preserved not deleted per §6.2 rule 4). The author reused the id `…-001` in its own yaml; filed
> here as `…-002` to keep the ledger addressable. **The verdict changed between versions.**

## Decision type

**None-of-the-above.** This package does not authorize a REPAIR, RETIRE, implementation change,
ontology change, state addition, predicate addition, or reversal of F-074. The cycle closes as a
semantic-review adjudication draft for the Principal.

## Evidence cited

**Primary:** `EVIDENCE_DOSSIER` · F-074 directional-displacement contract · 32/32 directional-contract
failures · CHoCH omission analysis · Phase 4g base-rate re-analysis · outcome comparison study
(AMBIGUOUS).
**Upstream packages:** `RC-002-CRIT-DEEPSEEK-001` · `RC-002-PROP-GROK-001` · `RC-002-CRIT-GEMINI-001`.
**Governing authority:** `SEMANTIC_REVIEW_PROTOCOL.md` — "never conclude defect from difference
alone"; CURRENT / INTENDED / RECOMMENDED separation; divergence reported as `TruthConflict`, reviewers
do not silently choose winners.

## Verdict

### `INSUFFICIENT EVIDENCE`

**Contract named:** none violated. The cycle does not demonstrate that F-074 is violated. The evidence
shows F-074 **operating exactly as documented** — the 32 bars are rejected because they move opposite
the founding sweep direction, which F-074 explicitly declares illegal for DISPLACEMENT occupancy.
Likewise no ontology contract has been shown to require that this population possess a distinct
semantic identity.

Established facts: all 32 fail the directional contract; the same-bar `trend_bias` flip mechanism is
false; the replacement "trend resumption" interpretation is unsupported after conditional base-rate
correction; economic distinctiveness is unestablished; identity remains UNKNOWN.

**Under the Semantic Review Protocol, absence of a proven identity is not itself evidence of a defect,
missing state, or ontology omission.** The review therefore cannot close as `CONFIRMED DEFECT`,
`TEST / CONTRACT GAP`, `DOCUMENTATION GAP`, or any other defect-class verdict.

## CURRENT / INTENDED / RECOMMENDED

**CURRENT** — the repository treats these events as failures of the directional-displacement contract.
The 32 bars are rejected at Gate 0 because candle direction disagrees with the sweep-implied
direction. Deterministic and documented.

**INTENDED** — F-074 establishes that DISPLACEMENT means directional impulse away from the swept side
and explicitly rejects the opposite-direction population. **No contrary semantic authority has been
established in this cycle.**

**RECOMMENDED** — no semantic identity should be assigned from the evidence currently available. Any
future attempt to classify the population as reversal, trend resumption, same-side continuation,
misparented displacement, or independent impulse requires separately authorized evidence beyond RC-002.

## Position B

**`INSUFFICIENT EVIDENCE`.** Position B asserted that occupancy was missing a representable construct.
The mechanism originally supporting that conclusion has been falsified, and the replacement
interpretation withdrawn after conditional base-rate analysis. The remaining evidence establishes
neither (1) that the population is a distinct market object, nor (2) that any representable construct
is absent. **Position B neither stands nor is disproven** — it remains unresolved for want of evidence.

## Agreement / conflict analysis

**Do the three upstream packages agree? Materially: yes** — all converge on the same limiting
conclusion. DeepSeek: the "trend resumption" interpretation is unsupported because the supporting
statistic is selection-induced and the base rate mis-specified. Gemini: the observed alignment is
structurally contaminated, not evidence of a distinct semantic object. Grok: identity remains unknown
and should not be named without additional evidence.

**These are different arguments, not independent confirmations. Their agreement is not counted as
votes and does not strengthen a claim merely by repetition.** It indicates only that no package
supplied evidence establishing a positive identity.

**TruthConflict: none requiring escalation.** A historical conflict existed — Source A (F-074 and its
implementation reject the population as DISPLACEMENT) vs Source B (Position B claimed a missing
construct). RC-002 does not resolve it in favour of either side. Instead **the evidentiary basis for
Source B has been withdrawn, so the conflict collapses into uncertainty rather than requiring
adjudication between two still-supported truths.**

## Decision text

The cycle successfully falsified a mechanism. The cycle did not establish an alternative identity.
The strongest supportable conclusion is: **the 32 bars are known directional-contract violations with
UNKNOWN semantic identity.** No contract violation established. No missing ontology construct
established. No distinct market object established. No semantic promotion authorized.

## What the Principal is being asked to decide

Does the repository **retain** the status "UNKNOWN semantic identity" for the 32
directional-contract-violation bars, or **authorize a separate future evidence cycle** aimed
specifically at establishing whether they are a distinct market object at all?

## Next actor / next grant

**Next actor:** Principal. **Next grant: none requested by this package.** If the Principal wants
further investigation it should be authorized as a **new evidence cycle**, not treated as continuation
of a settled semantic conclusion. No implementation, ontology, configuration, state-machine,
predicate, or governance change is requested.

---

## Executor adjudication (Claude, 2026-09-04)

### The re-run changed the verdict — the executor's prediction was wrong

Before the re-run I recorded a prediction: the verdict would be **robust** to the missing packages,
and the re-run's value would be a **better-worded Next Grant** offering the concrete execution grant
that packages 2 and 3 support. **Both halves were wrong**, and in opposite directions:

| | v1 (no packages) | v2 (with packages) |
|---|---|---|
| Semantic-review verdict | `USER AUTHORIZATION REQUIRED` | **`INSUFFICIENT EVIDENCE`** |
| Position B | `INSUFFICIENT EVIDENCE` | `INSUFFICIENT EVIDENCE` (unchanged) |
| Next grant | two offered (close / new cycle) | **none requested** |

The robustness check was right about Position B and about the *direction* of every package, and wrong
about the verdict. The distinction v2 draws is real and sharper: `USER AUTHORIZATION REQUIRED` implies
a well-posed choice awaiting authorization, whereas `INSUFFICIENT EVIDENCE` says the evidence does not
yet support posing that choice. Having the actual packages is what let it see the difference.

### The grant was withdrawn, not enriched — and the reasoning is better than mine

I predicted a third grant would appear ("authorize Grok's falsifier + Gemini's test"). v2 requests
**none**, on the grounds that further investigation must be a **new evidence cycle** rather than a
continuation — because treating it as continuation would smuggle in the premise that there is
something there to find. That is a stronger position than the one I proposed, and it is consistent
with Grok's own `NOT_A_DISTINCT_OBJECT` steelman, which v1 never saw.

### Two things v2 does that v1 structurally could not

1. **Applied the no-voting rule explicitly** — it names the material agreement of all three packages
   and then refuses to let that agreement add weight ("different arguments, not independent
   confirmations").
2. **Dissolved the TruthConflict correctly.** A `TruthConflict` (§6.2 rule 3) requires two *supported*
   sources. Source B's support was withdrawn during this cycle, so there is no longer a conflict to
   adjudicate — it collapses into uncertainty. v1 could not reach this because it could not see that
   the withdrawal had been independently confirmed.

### Still open, and not settled by this DECISION

The **referent question** for Grok's falsifier (`range_h_ref`/`range_l_ref` vs founding-candle extreme
vs engine `SWEEP.price`) was asked of Gemini and never answered. v2's RECOMMENDED section makes it
moot *for now* — no classification attempt is authorized — but it becomes live again the moment any
future evidence cycle is opened. Recorded so it is not lost.
