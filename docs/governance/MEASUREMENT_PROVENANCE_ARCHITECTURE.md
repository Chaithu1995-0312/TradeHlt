# Measurement Provenance Architecture (MPA v1) — design freeze

> **Status:** FROZEN v1.0.0, 2026-08-26 · `MEASUREMENT_PROVENANCE_STATUS=OPEN` · **Change contract:** `CH-measurement-provenance-architecture`
> **Authority:** research / governance only. Grants **no** production authority, **no** G001, **no**
> ontology node, **no** config change (CLAUDE.md §6.5). No finding's verdict is altered by this design.
>
> **Machine-readable:** [`../../configs/research/provenance/provenance_record.schema.json`](../../configs/research/provenance/provenance_record.schema.json) ·
> [`measurement_execution.schema.json`](../../configs/research/provenance/measurement_execution.schema.json)
> **Ledger:** `configs/research/provenance_ledger.jsonl` ·
> **Code:** `src/governance/provenance_record.py` · `provenance_resolver.py` · `provenance_derivation.py` ·
> **CLI:** `scripts/governance/provenance_query.py` · **Floor:** `tests/test_provenance_ledger.py` (33 tests)
> **Inputs:** `docs/analysis/research-dag-provenance-2026-08-26.md` · `docs/analysis/Infrastructure Inventory.csv`

---

## 0. The problem, stated once

The 2026-08-26 research-DAG audit measured 1,170 architectural decisions × 4 origin slots and found
**63.25% UNKNOWN**. Two holes are structural rather than incidental:

- `originating_measurement_basis` was **100% UNKNOWN** — 15 contracts on disk, zero with a proven run.
- `DECISION_PROMOTION`, the only surface that changes what production runs, was **96.67% UNKNOWN**,
  because a promotion line carries `event`/`reason`/`timestamp`/`version`/`config_id`/`params`/
  `config_hash`/`score`/`score_std_dev`/`notes` and nothing binding it to the evidence it rests on.

The audit is an *instrument*. It measures the record; it cannot improve it. The repository had no
**place** to record provenance: links lived as free text inside artifacts never designed to carry
them. This document freezes that place.

**It is additive.** The findings architecture is untouched — no new field, no schema change, no
`_FIELDS` edit, no verdict change. The spine *reads* the existing record systems and *writes* to a
new sibling ledger.

---

## A. Architecture

### The claim, and its limit

> A claim-bearing decision is **provenance-complete** when all four slots resolve to a target that
> exists. Provenance completeness is **not** validity, **not** economic value, and **not** authority.

A complete chain says the *origin* of a claim is recoverable. It says nothing about whether the claim
is true. `grants_authority` is `const false` on every record and pinned by a test, mirroring
`economic_claims_allowed` in `measurement_result_log.jsonl`.

### Subjects × slots

```
                  ┌──────────── PROVENANCE RECORD (PV-*) ────────────┐
                  │  subject_type × subject_id  (an EXISTING key)    │
                  └──┬──────────┬──────────┬──────────┬──────────────┘
                     │          │          │          │
                  EVIDENCE  HYPOTHESIS  CONTRACT   EXECUTION
                   (paths)    (H-*)   (MC-*/MP-*)    (MX-*)
                     │          │          │          │
   git-tracked ──────┘          │          │          └── measurement_result_log.jsonl
   artifact paths               │          └── configs/research/measurement_contracts/**
                                └── data/hypothesis_registry.jsonl
```

| `subject_type` | `subject_id` | Source (unmodified) |
|---|---|---|
| `FINDING` | `F-094` | `docs/current-findings.md` |
| `DECISION` | `CH-<slug>` | `docs/governance/build_manifests/*.impact.json` |
| `PROMOTION` | the line's `timestamp` | `configs/promotion_log.jsonl` |
| `CLOSURE` | `surface_id` | `docs/governance/closure_authority_index.json` |

**SESSION LOG entries are deliberately not subjects.** 1,052 of the audit's 1,170 decisions are
session entries and most record no architectural decision; admitting them would rebuild the audit's
denominator problem inside the ledger. They stay narrative, and a record may cite one as evidence.

### The central correction: CONTRACT ≠ EXECUTION

The audit had **one** `originating_measurement_basis` slot, so *naming* a contract and *running* it
were indistinguishable — its `U4_DECLARED_NOT_EXECUTED` rule fired 56 times to compensate. Splitting
the slot makes **declared-but-never-executed** a first-class, queryable state:

```
FINDING F-090
  OK contract   names MC-MRANGE-XAUUSD-M15-V1
  -- execution  MC-MRANGE-XAUUSD-M15-V1 is declared but has NO result line — declared-but-unexecuted (F-083)
```

That is the same silent-gap class as F-056 / F-079 / F-083 / F-085, promoted from footnote to field.

### The four resolution classes

Strongest → weakest. **A slot never silently upgrades.**

| Class | Means | Requires | Backfill may produce |
|---|---|---|---|
| `EXPLICIT` | the subject's own record names the target and it resolves | `witness` = the literal bytes read | **never** |
| `DERIVED` | mechanically reproducible by a named, versioned rule | `rule_id` + `rule_version` + `inputs` | yes |
| `ATTESTED` | a human/agent adjudication | `by` + `utc` + `basis` + `authority`, all non-empty | yes |
| `UNKNOWN` | no link | recorded by **omission** — never asserted as a value | n/a |

`chain_class` is the **weakest** non-UNKNOWN class among bindings that resolve. One `ATTESTED` slot
makes an `ATTESTED` chain however many `EXPLICIT` slots sit beside it. That is deliberate: it is what
stops coverage being inflated by attesting everything.

### Why the backfill cannot contaminate the audit

The audit's cardinal rule is *"GAPS ARE THE RESULT. No edge is backfilled, guessed, or filled from a
sibling artifact"*, enforced by `test_unknown_edges_are_never_silently_populated`. This design honours
it by **separation, not by argument**:

- `scripts/analysis/research_dag_provenance.py` classifies from the **original artifacts** and never
  reads this ledger. Enforced structurally by
  `test_provenance_ledger.py::test_audit_extractor_does_not_read_the_ledger`, which greps the
  extractor's source for any reference to the provenance modules.
- The ledger is a **separate, additive** record of links a named rule or a named person stands behind.
- The audit's payload is asserted to carry no ledger-derived key.

Two instruments, never averaged. The audit's UNKNOWN percentages stay honest forever.

---

## B. New infrastructure components

| Component | Path | Mirrors |
|---|---|---|
| Provenance ledger (append-only, committed) | `configs/research/provenance_ledger.jsonl` | `measurement_result_log.jsonl` |
| Record builder / validator / appender | `src/governance/provenance_record.py` | `measurement_result_log.py` structurally |
| Slot resolver (read-only, EXPLICIT-only) | `src/governance/provenance_resolver.py` | `validation_access/ladder.py` result shape |
| Derivation rules (backfill) | `src/governance/provenance_derivation.py` | the audit's ordered rule table |
| Query / record CLI (**the only write path**) | `scripts/governance/provenance_query.py` | `feature_surface_query.py` |
| Frozen schemas ×2 | `configs/research/provenance/*.schema.json` | `measurement_contract.schema.json` |
| Test floor | `tests/test_provenance_ledger.py` | `test_measurement_result_log.py` |

**`MX-*` is not a new store.** An execution already exists as a `measurement_result_log.jsonl` line;
`MX-<run_id>` is a stable *addressing scheme* over it, read through the existing
`iter_result_lines`. Adding a second store would have created exactly the duplicate-truth problem
§6.2 exists to prevent.

**Placement:** `.gitignore` excludes `data/`, `logs/`, `results/`, `models/`. A committed audit
stream must live under `configs/` — which is why `measurement_result_log.jsonl` does, and why the
ledger sits beside it rather than in `data/`.

---

## C. Data model

```
ProvenanceRecord
├── record_id       PV-<YYYYMMDDTHHMMSS>Z-<SUBJECT_TYPE>-<slug>
├── timestamp       ISO-8601 UTC
├── kind            "PROVENANCE_RECORD"        (const)
├── schema          "provenance_ledger/1"      (const)
├── subject         {type, id, source_path, source_sha256}
├── slots
│   ├── evidence    SlotBinding[]   (0..n — a claim may rest on several artifacts)
│   ├── hypothesis  SlotBinding?
│   ├── contract    SlotBinding?
│   └── execution   SlotBinding?
├── chain_class     EXPLICIT|DERIVED|ATTESTED|UNKNOWN   ← COMPUTED
├── chain_complete  bool                                ← COMPUTED
├── authority       "research"                 (const)
├── grants_authority false                     (const, pinned)
└── notes

SlotBinding
├── target_kind     EVIDENCE_PATH | HYPOTHESIS | CONTRACT | EXECUTION   ← derived from the slot
├── target_id       "docs/analysis/x.md" | "H-002" | "MC-…-V1" | "MX-<run_id>"
├── resolution      EXPLICIT | DERIVED | ATTESTED
├── resolves        bool     (exists AND, for paths, git-tracked)
├── witness         str      (the literal bytes justifying the binding)
├── target_sha256   str?
├── derivation      {rule_id, rule_version, inputs[], caveat?}   required iff DERIVED
└── attestation     {by, utc, basis, authority}                  required iff ATTESTED
```

### Three invariants, each proved by a planted defect

1. `DERIVED` ⟺ a `derivation` naming a **registered** rule at its **registered version**. A rule
   that cannot be named cannot be re-run, and a backfill that cannot be re-run is a guess wearing a
   label.
2. `ATTESTED` ⟺ an `attestation` with all four fields non-empty. An attestation is a claim someone
   stands behind, so it records *who*.
3. `chain_class` / `chain_complete` are **computed, never caller-supplied** — the
   `basis_status`-is-derived pattern from `measurement_result_log.build_result_line`. A supplied
   value that disagrees with its own bindings is rejected.

### Tracked-only resolution

Evidence paths resolve through `git ls-files`, never the filesystem, and `tracked_paths()` **fails
closed** to an empty set: with no git, nothing resolves rather than everything. An untracked path is
still *recorded* with `resolves: false`, so the dangling citation stays visible — 39 of 374 finding
evidence references are untracked today, and this session found `MC-ASYM` and `MC-MRPRIOR` untracked
and therefore invisible to the F-083 gate. That is the F-071 class; it must not recur here.

---

## D. JSON schemas

Both under `configs/research/provenance/`, `additionalProperties: false`, version pinned with a
`const` (the frozen-schema pattern `test_measurement_contract.py` enforces for `MC-*`).

`provenance_record.schema.json` carries conditional `allOf` blocks binding
`resolution: DERIVED` → `derivation` object, `resolution: ATTESTED` → `attestation` object, and
`resolution: EXPLICIT` → **both null** — so a malformed backfill fails validation rather than landing.

`jsonschema` is **not installed** in this environment (it is why
`test_measurement_contract.py::test_mc_instances_validate_schema…` is red). The always-on floor is
therefore the plain-Python validator in `provenance_record._validate_line`; the schema check is an
`importorskip` belt-and-braces. A separate test asserts the schema's rule enum and the code's
`DERIVATION_RULES` registry cannot diverge.

---

## E. Registry design

The ledger is the record; the registry is the derived read-model.

```bash
python scripts/governance/provenance_query.py --subject FINDING:F-092 --derive
python scripts/governance/provenance_query.py --coverage [--by FINDING]
python scripts/governance/provenance_query.py --unresolved
python scripts/governance/provenance_query.py --backfill [--dry-run]
python scripts/governance/provenance_query.py --attest PROMOTION:<ts> --slot evidence \
    --target docs/analysis/x.md --basis "..." --authority "user 2026-08-26" --by claude
```

**Resolution order per slot** — ordered, first-match-wins, `rule_id` on every hit, mirroring the
audit's own classifier design so both instruments agree on what "resolves" means:

| Slot | Order |
|---|---|
| `evidence` | dedicated field (`authoritative_artifact`, `affected_files[]`) → cited path in body → UNKNOWN |
| `hypothesis` | explicit `H-id` cite → `hypothesis_registry.findings[]` (D3) → `RF-*` cell `claims[]` (D4) → UNKNOWN |
| `contract` | `Contract:` id → content-hash (D1) → UNKNOWN |
| `execution` | result-log line for the resolved `contract_id` (D2) → UNKNOWN |

**One distinction the resolver makes and the audit's evidence rule does not.** A path in a *dedicated
field that exists to name the evidence* — a closure surface's `authoritative_artifact` — **is** the
evidence whatever tree it lives in. A manifest's `affected_files[]` is a list of change **targets**
and keeps the `src/`-and-`configs/`-are-not-evidence filter. Applying one rule to both surfaces left
every closure with zero evidence until this was separated.

**Coverage is reported as a class histogram, never as one percentage** — see §H tension 3.

---

## F. Migration strategy

| Phase | Lands | Gate | State |
|---|---|---|---|
| **0 · Freeze** | this doc + 2 schemas + `CC-*` classes + `INV-*` rows + Closure Index row | schema/catalog floors green | **DONE** |
| **1 · Spine** | `provenance_record.py` + ledger + floor | 3 invariants red-then-green under planted defects | **DONE** |
| **2 · Resolver** | `provenance_resolver.py` + CLI, read-only | resolves all 4 subject types without raising | **DONE** |
| **3 · Derivation** | `provenance_derivation.py` + backfill run | second run is a no-op | **DONE** |
| **4 · Dormant gate** | `provenance.enforce` config key, default `false` | CI fails on MALFORMED records only, never on missing ones | **PROPOSED** |

**Phase 4 is deliberately not built.** Precedent: the Goal Layer shipped G001 advisory-first with a
dormant enforce gate, and §6.5 is explicit that a knob becoming config-driven grants *tunability*,
never *authority*. The gate flips per subject type only when that surface's coverage justifies it —
a separate, evidenced decision.

**Recommended first flip (not now):** `PROMOTION`. Only 15 rows, the worst-traced surface, and the
only one that changes what production runs.

---

## G. Backfill strategy

**Rule: backfill writes `DERIVED` or `ATTESTED`. Never `EXPLICIT`, and it never converts a recorded
UNKNOWN into anything.** An unresolvable slot is omitted, and the omission is the result.

| Rule | Slot | Fires when | Fired on this corpus |
|---|---|---|---|
| `D1_CONTRACT_CONTENT_HASH` | contract | a 64-hex `Contract:` matches a sealed instance's file SHA | **0** — see below |
| `D2_EXECUTION_BY_CONTRACT` | execution | a result-log line exists for the resolved contract | 0 (EXPLICIT path already binds all 4) |
| `D3_HYPOTHESIS_BACKLINK` | hypothesis | `hypothesis_registry.findings[]` names the finding | **19** |
| `D4_FAMILY_CLAIM_CELL` | hypothesis | an `RF-*` cell `claims[]` names the finding | **45** |
| `D5_MANIFEST_AFFECTED_FILES` | evidence | `affected_files[]` names a tracked evidence-class path | 0 (EXPLICIT scan already covers it) |
| `D6_FINDING_EVIDENCE_PATHS` | evidence | a finding cites a tracked evidence path | 0 (EXPLICIT scan already covers it) |

**D1 fires zero times and is kept anyway.** Its input no longer exists: the six bare-sha256 `Contract`
fields (F-081, F-090…F-094) were rebound to ids earlier on 2026-08-26 under
`CH-measurement-provenance-boundary`, after all six were shown to resolve **by content, exactly**.
The rule is kept reachable by a synthetic fixture (`test_d1_content_hash_rule_stays_reachable`) so it
cannot rot into dead code — the same treatment the audit gives its own unexercised rule `I4`.

**D3 and D4 are weaker than they look, and say so in the record.** The `H-*` registry begins
2026-07-03 and **18 of its 20 records were authored that single day about work already completed**. A
`DERIVED` hypothesis binding through it is a *reconstruction*, not a contemporaneous link; each such
binding carries that caveat in `derivation.caveat`. D4 is weaker still — a research family poses a
*question* about an object, not a falsifiable hypothesis — and targets `RF-<family>.<layer>`, never
an `H-*`.

**Deliberately not a rule: promotion evidence.** A promotion line carries no field that could bind it
to evidence, so there is nothing to derive *from*. Deriving one by date proximity would be exactly the
`I3_DATE_COLOCATION` inference the audit names as its own weakest — 325 of its 849 INFERRED edges,
and it states that reclassifying them as UNKNOWN would push the overall rate to ~70%. Promotions are
the natural first `ATTESTED` candidates. Enforced, not merely documented: `provenance_derivation.
FORBIDDEN` blocks the evidence rules for `PROMOTION`, and a test asserts no promotion evidence is ever
derived.

### Result of the backfill run (2026-08-26)

**168 records** over 212 subjects; 44 subjects had nothing to bind and are UNKNOWN by omission.

| `chain_class` | count |
|---|---|
| `EXPLICIT` | 70 |
| `DERIVED` | 64 |
| `UNKNOWN` | 34 |

**Provenance-complete chains: 4 — F-091, F-092, F-093, F-094.** Exactly the four contracts that
executed E-MT-00 earlier the same day. Nothing else in the repository's history has all four origin
slots resolving, and that is the honest headline.

---

## H. Governance impacts

| Area | Impact |
|---|---|
| **Findings architecture** | **Untouched.** No field, no schema change, no verdict change. Read-only. |
| **Authority Ladder (§6.5)** | A record is *information*, rung 1. `grants_authority` const false, pinned. |
| **Closure Index** | New surface `MEASUREMENT_PROVENANCE` · **OPEN** · boundary = whether a decision's four origin slots resolve; explicitly **not** whether the claim is true. Non-transitive. |
| **§6.7 Closed Semantic Environment** | New `CC-*` classes for the ledger stream — including a **CANNOT** class forbidding the misreading this architecture most invites. |
| **§6.2 Truth Maintenance** | A new record system, additive. No existing record system is demoted. |
| **§3.3b Construction Protocol** | `CH-measurement-provenance-architecture`; `production_behavior_changed: NO`. |
| **SITS** | `provenance_query.py` registered the same turn it was added. |
| **MEASUREMENT_CONTRACT.md** | `MEASUREMENT_LAYER_STATUS` stays `OPEN`. This records *whether a basis exists*; only `mt00 PASS ∧ mt01 COMPLETE` makes one admissible, and coverage is 0/27. |

### Known tensions, stated not hidden

1. **The ledger's own provenance is unrecorded.** The spine does not record itself; `CH-*` + the
   SESSION LOG remain its provenance. Stated so nobody claims recursion it does not have.
2. **`DERIVED` inherits its rule's weakness.** D3/D4 reconstruct through a registry back-seeded in a
   day. Reproducible is not contemporaneous.
3. **Coverage is gameable by attestation.** Nothing stops an agent attesting every slot. Three
   mitigations, all mechanical: `ATTESTED` is the weakest non-UNKNOWN class; it propagates to
   `chain_class`; and `--coverage` prints a class **histogram**, never a single percentage.
4. **Resolution is not correctness.** A binding proves a target exists and was named. Whether it
   *supports* the claim is a judgement no resolver makes.

---

## Addendum — 2026-08-27: contract resolution is tracked-only

**Defect found the day after the freeze, by acting on it.** v1.0.0 applied the `git ls-files`
instrument to the EVIDENCE slot but resolved CONTRACTS with a filesystem glob. The two instruments
disagreed, and the gap was live: `MC-ASYM-XAUUSD-M15-V1` (F-091) and `MC-MRPRIOR-XAUUSD-M15-V1`
(F-094) were untracked, so **two of the four provenance-complete chains were complete on one disk
only** and would have collapsed to UNKNOWN in any fresh clone. Worse, the resolver could not warn
about it — the one gap it most exists to surface was the one it was blind to.

Fixed additively: `_resolve_contract` now takes the tracked set, an untracked contract yields
`resolves: false` with an explicit `UNTRACKED` blocker, and two floors were added —
`test_contract_resolution_is_tracked_only` (planted defect) and `test_every_cited_contract_is_tracked`
(no finding may cite a contract another clone cannot see). Both contracts were then git-tracked on
user instruction; the F-083 scan universe widened 8 → 10.

**`MC-MRPRIOR`'s `mt00: FAIL` is preserved, not repaired.** The F-083 gate reports it `ok` because
that gate asks whether a non-UNRUN claim is backed by a real result line — not whether it passed. A
sealed V1 whose fingerprint declares `side` where its contract declares `direction` stays registered
in the record carrying its failure; correcting it requires a **new `MC-*` id**, never a deletion or
a silent edit (the `MC-VCRT` V1→V2 precedent). Tracking it is what forces CI and every other clone
to acknowledge the exact state of the evidence, including a legitimate failure.

**Scope note:** `configs/research/measurement_contracts/drafts/MC-SUJAN-XAUUSD-M15-V1.json` remains
untracked and is correctly out of scope — an unsealed draft no finding cites. Its own test floor
looks for it under `instances/`, which is why that floor errors. Reported, not adopted.

### KNOWN OPERATIONAL CAVEAT (v1.0.0): the hypothesis slot is not tracked-uniform

**Two of three resolving slots use the tracked-only instrument; the hypothesis slot does not.**
`evidence` and `contract` resolve through `git ls-files`. `hypothesis` resolves through
`data/hypothesis_registry.jsonl`, which `.gitignore` excludes — so **19 `D3_HYPOTHESIS_BACKLINK`
bindings rest on an artifact no clone has at checkout**.

This is deliberately **not** patched the way the contract slot was, because the two situations are
not the same failure:

| | untracked CONTRACT | untracked HYPOTHESIS REGISTRY |
|---|---|---|
| Nature | hand-authored sealed artifact | GENERATED derived view |
| Rebuild path | none — the bytes are the only copy | `scripts/governance/seed_hypothesis_registry.py`, **tracked** |
| Consequence of loss | **irrecoverable** | **deterministic recovery** |
| Correct `resolves` | `false` | `true`, after a named regeneration step |

Marking a D3 binding `resolves: false` would assert a falsehood: it *does* resolve, once the
documented seed is run. v1.0.0's vocabulary has no state for "resolves after a named regeneration
step", and inventing one the day after a freeze would be the kind of unversioned vocabulary drift
this contract exists to prevent.

**Blast radius, measured not assumed:** all four provenance-complete chains (F-091…F-094) bind
their hypothesis slot via `D4_FAMILY_CLAIM_CELL` → `docs/governance/research_family_registry.json`,
which **is** tracked. **Zero** complete chains depend on D3. The caveat therefore bounds 19 DERIVED
bindings on incomplete chains, and bounds nothing in the completeness guarantee.

**Operator rule while this caveat stands:** on a fresh clone, run
`python scripts/governance/seed_hypothesis_registry.py` before trusting a D3 binding's `resolves`.

### QUEUED RFC — `REGENERABLE` resolution state (v1.1.0 vocabulary turn)

Deferred by explicit decision, 2026-08-27. **Not** part of v1.0.0.

- **Proposal:** a fourth resolution state, or a `regenerable: {generator, tracked}` qualifier on a
  binding, distinguishing "target is absent and lost" from "target is absent and deterministically
  rebuildable from a tracked generator".
- **Why it needs a version turn, not a patch:** `chain_class` ordering is `EXPLICIT > DERIVED >
  ATTESTED`, and every consumer reads the weakest-wins rule. Adding a state changes that lattice
  and the frozen `provenance_record.schema.json` enum simultaneously — a schema `const` bump with a
  migration note, per §7 of the measurement-contract change-control precedent.
- **Must decide:** whether `REGENERABLE` is a *class* (participating in weakest-wins) or an
  *orthogonal qualifier* (leaving `chain_class` alone). The second is likely correct — regenerability
  describes the TARGET's availability, not the strength of the LINK, and conflating the two is what
  produced this caveat's ambiguity in the first place.
- **Prerequisite:** decide whether `data/hypothesis_registry.jsonl` should simply become tracked,
  which would dissolve the RFC entirely. Cheaper than a vocabulary change if the generated-artifact
  doctrine permits it.
