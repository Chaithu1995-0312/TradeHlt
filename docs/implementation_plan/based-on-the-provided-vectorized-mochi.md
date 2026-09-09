# MPA v1 sufficiency evaluation — Observation → Partial Finding → Finding → Decision → Promotion

**Architecture only. No implementation proposed. v1.0.0 stays frozen.**

## Context

MPA v1 was frozen 2026-08-26 to answer one question — *can a claim's measurement basis be
recovered?* — and it answers that well. This evaluates a different question it was never designed
for: whether it can carry a **research lifecycle**, in which a claim is progressively strengthened
through named stages before anything reaches production.

Sources read: `docs/governance/MEASUREMENT_PROVENANCE_ARCHITECTURE.md` (incl. the 2026-08-27
addendum and the v1.0.0 caveat) and `docs/analysis/research-dag-provenance-2026-08-26.md`.

---

## Verdict

**MPA v1 is necessary and structurally insufficient.** Insufficient not because subject types are
missing — that is the easy half — but because of a shape mismatch stated in §0. Adding
`OBSERVATION` and `PARTIAL_FINDING` as subject types to v1 as it stands would produce two more
disconnected islands, not a lifecycle.

---

## §0 The structural finding: MPA v1 is a star schema, not a DAG

Every record has **one subject and four slots**, and every slot's `target_kind` is a **non-subject**:

```
target_kind ∈ { EVIDENCE_PATH , HYPOTHESIS , CONTRACT , EXECUTION }
                 (a file)      (H-*)        (MC-*/MP-*) (MX-*)
```

There is **no edge whose target is another PV subject.** A `DECISION` record cannot point at the
`FINDING` that motivated it; a `PROMOTION` cannot point at the `DECISION` that produced it. The
lifecycle in question is a chain **of subjects**. MPA v1 has subjects and it has slots, and the
arrow it lacks is exactly the one the lifecycle is made of.

**A second, sharper consequence.** Compare slot sets:

| | slot 1 | slot 2 | slot 3 | slot 4 |
|---|---|---|---|---|
| **Audit** (2026-08-26) | hypothesis | **finding** | evidence | measurement_basis |
| **MPA v1** | hypothesis | *(none)* | evidence | **contract** + **execution** |

MPA v1 **traded the `finding` slot for the contract/execution split.** That split was the right call
and remains v1's best contribution — but the edge it spent to buy it was the audit's *only slot that
half-works*: `originating_finding` at **37.04% EXPLICIT**, against 1.36% for hypothesis and 1.27%
for measurement basis. So the repository's strongest existing provenance edge is the one v1 cannot
represent, and `Finding → Decision` — one of the four transitions asked about — is unrepresentable
today for that reason alone.

This is a limitation of the v1 design, not of the record systems it reads.

---

## §1 What provenance problems ARE solved

| # | Problem | How v1 solves it |
|---|---|---|
| 1 | **Declared ≠ executed** | The contract/execution split. The audit needed a whole rule (`U4_DECLARED_NOT_EXECUTED`, 56 firings) to paper over one conflated slot; v1 makes it a queryable field. This is the single most valuable thing v1 does. |
| 2 | **Nowhere to record provenance** | An append-only committed ledger, with the only write path through a CLI. Links stop being free text in artifacts never designed to hold them. |
| 3 | **All links look equally good** | A four-class lattice with **weakest-wins** composition, so one weak binding cannot be hidden behind strong siblings. |
| 4 | **Backfill laundering** | `EXPLICIT` is unreachable by backfill, mechanically. A reconstruction can never impersonate a record. |
| 5 | **Existence ≠ resolution** | `git ls-files`, fail-closed. Proven load-bearing on 2026-08-27: two contracts resolved on one disk and nowhere else. |
| 6 | **Measuring instrument contamination** | The audit never reads the ledger, enforced by a source-level test rather than a promise. Two instruments, never averaged. |
| 7 | **Provenance mistaken for authority** | `grants_authority` const false, pinned, plus a `CANNOT` claim class forbidding the inference. |
| 8 | **Coverage theatre** | Reported as a class histogram, never one number; `ATTESTED` propagates so attesting cannot inflate. |

---

## §2 What provenance problems REMAIN

Ordered by how much they block the lifecycle.

**Blocking the lifecycle outright**

- **R1 · No subject→subject edges** (§0). No transition in the chain can be recorded.
- **R2 · No `finding` slot** (§0). `Finding → Decision` unrepresentable even between existing types.
- **R3 · No pre-finding subjects.** `Observation` and `Partial Finding` have no home. Note the
  substrate for Observation already exists — 1,052 SESSION LOG entries — and v1 *deliberately*
  excluded them to avoid importing the audit's denominator problem. That exclusion was right for a
  measurement ledger and is wrong for a lifecycle; the resolution is selection, not admission of all
  1,052.

**Blocking the promotion question specifically**

- **R4 · Completeness ≠ sufficiency.** `chain_complete` means *four slots resolve* — recoverability.
  It is silent on power (`n_declared_min`), independence (holdout spent or unspent), multiplicity,
  and control comparison. A chain over one underpowered run is "complete". F-094 is the live proof:
  provenance-complete, and its own conclusion is `INSUFFICIENT` at holdout n=9.
- **R5 · No refutation edges.** Slots bind evidence that *supports*. Nothing expresses evidence that
  *contradicts*. A lifecycle without refutation is a ratchet — partial findings could only ever be
  abandoned silently, never killed on the record.
- **R6 · No α / multiplicity accounting.** The concept already exists in prose and nowhere else:
  F-084 records "REPLICATION not independent test (inherits V1's α, spends none)", and F-086's
  236-bar holdout is described as "unspent". Neither is a field anyone can query.

**Correctness residue**

- **R7 · Single hypothesis** (`0..1`). A synthesis finding cannot bind the several hypotheses it
  resolves.
- **R8 · No temporal ordering.** Records carry timestamps but no happens-before edges. The audit's
  fallback, `I3_DATE_COLOCATION`, is 325 of its 849 INFERRED edges and it names date-adjacency as
  its own weakest inference — that weakness is a *symptom* of missing ordering, and a lifecycle
  makes ordering load-bearing.
- **R9 · Hypothesis slot not tracked-uniform** — already documented as the v1.0.0 caveat with the
  `REGENERABLE` RFC queued.
- **R10 · Promotion has nothing to bind to.** 15 lines, no field that could carry an origin.

---

## §3 Do Partial Findings require a new registry?

**Yes — a registry, not a document.** The deciding argument is lifecycle shape, not volume.

A Partial Finding's defining property is that **it may never become a Finding.** Every invariant in
`docs/current-findings.md` is conclusion-shaped and would have to be weakened to admit one:

| Findings-doc invariant | Why a PF breaks it |
|---|---|
| Every non-terminal finding appears in CLAUDE.md's Repository Truths index | A PF is not a repository truth; the index would fill with non-conclusions |
| Terminal findings require `Reversal:` / `Superseded-by:` | A PF that lapses reverses nothing — it was never asserted |
| `Confidence ∈ {Certain, Likely, Possible}` | All three presume a conclusion exists to be confident *about* |
| `Status` vocabulary in use is VALIDATED / OPEN / SUPERSEDED / DURABLE | None of these means "evidence accumulating, conclusion not yet warranted" |

The lifecycle defaults are also **opposite**: a Finding that goes stale must be re-examined
(`Revalidate-by:`); a PF that goes stale should **lapse**. Encoding both in one surface means one of
them is wrong by default.

**Registry, not doc**, for a specific reason: a Finding's content is *prose a human must read*; a
PF's content is *a binding set* — which evidence, which contract, which execution, what is still
missing. That is machine-first data, and the repo already has the right precedent in
`hypothesis_registry.jsonl` rather than in a second narrative markdown file. This also respects
§6.2 rule 5 (minimise doc count): one new registry, no new findings doc.

**The genuine fork, named rather than hidden.** A PF could instead be modelled as a *lifecycle state
of an `H-*`* — "a hypothesis with evidence attached but no verdict". That is defensible and cheaper.
My recommendation is a distinct object, because `H-*` states a **question** and a PF states a
**partial answer**, and collapsing them would make the hypothesis registry mean two things at once —
the exact ambiguity that made `originating_measurement_basis` unusable. But this is the one place in
this evaluation where the alternative is close, and it is a decision worth taking explicitly.

---

## §4 Should Findings aggregate multiple PF-*?

**Yes, many-to-many** — a Finding aggregates several PFs, and one PF may feed several Findings
(the same partial result can bear on more than one conclusion).

Two constraints matter far more than the cardinality:

**4a · Aggregation must never compose confidence upward.** The repository has already been burned
here: F-031 records a rollup that emitted `REGIME_HARMFUL` from cells that were *all*
gate-INSUFFICIENT, caught by human review before registration, and formalised as the **E-001E
invariant — "Is the parent stronger than the children?"**. An aggregation edge must therefore carry
the same weakest-wins lattice MPA already applies to `chain_class`: a Finding aggregating three
`Possible` PFs is at most `Possible`. Aggregation is an *edge*, never an *arithmetic*.

**4b · Corroboration must be distinguishable from repetition.** Independent PFs agreeing is
evidence; the same population re-measured is not. F-084 is the precedent, and it states the
distinction explicitly — a replication "inherits V1's α, spends none". Without this distinction on
the edge itself, aggregation manufactures confidence out of re-runs, which is the most dangerous
thing a lifecycle can automate.

This is also why R6 (α accounting) is not optional if §4 is adopted: aggregation without an
independence field is a confidence pump.

---

## §5 Should Promotion depend on evidence sufficiency rather than finding existence?

**First, the premise needs correcting: today promotion depends on neither.**
`PromotionManager` gates solely on `ValidationReport.decision == "APPROVE"`
(`src/governance/promotion_manager.py:140`), and that report is a **backtest fitness** gate — min
trade count 10, max drawdown 35%, min fitness 0.15. No finding is required. No provenance is
consulted. The 96.67%-UNKNOWN figure is not an oversight in recording; it reflects that the gate
never had an evidence input to record.

**Recommendation: sufficiency — expressed as a conjunction of independently-owned gates, never a
score.**

| Gate | Owner | Asks |
|---|---|---|
| Provenance | MPA | can this be traced? |
| Admissibility | `MEASUREMENT_CONTRACT.md` E4 seal | was it measured under a sealed contract? (`mt00 PASS ∧ mt01 COMPLETE`; **0/27** probes today) |
| Authority | §6.5 Authority Ladder | measured ΔG001 |
| Operational | existing `ValidationReport` | does it run acceptably? |

Each is separately falsifiable; none substitutes for another; all four must hold. Note what this
implies about the present: with mt01 coverage at 0/27, **nothing in the repository is admissible**,
so a sufficiency gate would today block every promotion — which is the honest state, not a defect
of the design.

**The load-bearing negative: "a finding exists" must never itself be a promotion gate.** Making
registration unlock promotion creates an incentive to register findings in order to promote, which
inverts the Authority Ladder — evidence would begin serving the gate instead of the gate testing the
evidence. Sufficiency is a property of the *evidence*; existence is a property of the *paperwork*.

---

## §6 Migration path: MPA v1 → full research DAG provenance

Five stages. Each is independently valuable and independently revertible; the ordering is forced by
dependency, not preference. **Edges before nodes** is the central sequencing rule — adding
`OBSERVATION`/`PARTIAL_FINDING` first would repeat v1's error at larger scale.

| Stage | Version | Adds | Closes | Why here |
|---|---|---|---|---|
| **S1 · Edge typing** | v1.1 | subject→subject edges as a first-class relation, subsuming the dropped `finding` slot | R1, R2, R7 | Prerequisite for every later stage. Nothing in the lifecycle connects without it. Fold the already-queued `REGENERABLE` RFC (R9) into this same schema turn — both touch the frozen schema, and two `const` bumps where one would do is avoidable churn. |
| **S2 · Pre-finding subjects** | v1.2 | `OBSERVATION`, `PARTIAL_FINDING`; the PF registry of §3 | R3 | Nodes are safe to add once edges exist. Observation admission must be **selective** — the reason v1 excluded SESSION LOG stands, and importing all 1,052 would rebuild the denominator problem inside the ledger. |
| **S3 · Sufficiency vocabulary** | v1.3 | `sufficiency` as a dimension **orthogonal** to `completeness`; power / independence / multiplicity / control | R4, R6 | Must precede any gate that consults it. **Source these from the MC-* contract's `metrics` surface; do not re-derive them** — a second definition of "sufficient" is the duplicate-truth failure §6.2 exists to prevent. |
| **S4 · Refutation edges** | v1.4 | `REFUTES` / `WEAKENS` alongside the supporting relations | R5 | A gate that cannot see contradicting evidence is a ratchet. Must land before S5 or the promotion gate is monotonic by construction. |
| **S5 · Promotion binding** | v1.5 | the §5 conjunction consulted at the promotion gate | R10 | **Last, and the only stage touching production authority.** Ship advisory-first behind a dormant enforce flag — the Goal-Layer G001 precedent — and flip per surface on evidence. |

**Two invariants the migration must preserve at every stage:**

1. **Two instruments, never merged.** The audit reads original artifacts; the ledger records
   asserted links. If S1–S5 ever let the audit read the ledger, the one number that is currently
   honest about the repository's record stops being honest. This is the property most at risk as
   the DAG grows, because a richer ledger looks increasingly like a better audit.
2. **Authority stays out.** `grants_authority` remains const false through v1.5. S5 lets the
   promotion gate *consult* provenance; it must never let provenance *confer* anything.

---

## Non-goals

No implementation. No schema edit today. v1.0.0 stays frozen and its caveat stands. No finding's
verdict, confidence, or status changes. No promotion gate is modified. This document proposes no
`CH-*` and requests no authority.

## What would falsify this evaluation

- If a subject→subject edge turns out to be expressible in v1 by convention (e.g. binding a
  finding's own file path into a DECISION's `evidence` slot), then R1/R2 are weaker than stated and
  S1 shrinks to a typing convention. **I do not believe this survives contact with the resolver's
  evidence-prefix filter, but it is the cheapest thing to check first and it would reorder the
  whole migration.**
- If the PF concept collapses cleanly into an `H-*` lifecycle state under real examples, §3 flips to
  "no new registry" and S2 halves.
- If any MC-* instance reaches `mt00 PASS ∧ mt01 COMPLETE`, §5's "nothing is admissible today"
  expires and the sufficiency gate becomes testable against a real case rather than a hypothetical.
