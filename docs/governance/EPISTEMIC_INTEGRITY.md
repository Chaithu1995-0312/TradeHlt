# Program E-001 — Epistemic Integrity Sweep & Invariantization

> **Created:** 2026-06-17
> **Status:** ACTIVE
> **Mandate:** Every conclusion must be traceable to the evidence that supports it.
> No layer may possess greater certainty than the layer beneath it.

---

## 1. Why this exists

The F-030 incident revealed a systematic vulnerability:

```
Evidence:
  all spine cells = INSUFFICIENT (n < 30)

     ↓ hidden inference

  negative sign counts in rollup

     ↓ presentation

  REGIME_HARMFUL
```

Nothing crashed. Tests passed. Yet the semantic meaning became stronger than the evidence.

That is **epistemic corruption** — worse than a bug.

A manual correction followed (regime_conditioning v1.1→v1.2), but **no invariant guaranteed recurrence prevention**. This program formalizes the missing invariants.

---

## 2. The Invariant

**No layer may claim greater certainty than its supporting evidence — unless an explicit,
documented precedence policy exists.**

(Prose form generalized to an evidence *graph* — relations are often a DAG, not a tree.
"Layer beneath it" was the original tree-shaped phrasing; this is the durable generalization.)

Formally, in the default (tree) case:

```
certainty(parent) ≤ min(certainty(children))
```

Equivalently: a verdict cannot be stronger than the weakest cell that supports it.

**The program's objective, stated permanently:**

> **E-001 creates shorter correction loops, not total prevention.**

No governance system eliminates error. E-001 governs the *speed of correction* (error lifetime),
not the *frequency of mistakes*. The F-030→F-031 chain (governance caught an overclaim → the
governance *tests* later overclaimed → the tests audited themselves → behavioral enforcement was
added) is the loop working as intended, not a failure.

### Sanctioned precedence rules

The invariant's "unless" clause is real, and the difference is load-bearing:

- **Undocumented** precedence looks like inflation (an E-001E bug).
- **Documented** precedence is *policy*.

First sanctioned precedence rule: the **scope-level** rollup in
[`src/research/regime_conditioning.py`](../../src/research/regime_conditioning.py) (`scope_verdict`)
lets an *informative* consumer dominate an *underpowered* (INSUFFICIENT) consumer in the same
scope — so a real signal from one consumer is not masked by another's noise. This is intentional
cross-consumer precedence, not parent-over-children inflation, and is therefore exempt from the
E-001E invariant. The per-consumer rollup (the F-030 site) is **not** exempt and is enforced
behaviorally (see §6).

---

## 3. Failure Classes

### E-001A — Overclaim
Conclusion stronger than evidence supports.

Example:
```
INSUFFICIENT → HARMFUL
```
Pattern: `if sign < 0: verdict = REGIME_HARMFUL` missing `if n < minimum: verdict = INSUFFICIENT`

---

### E-001B — Statistical ≠ Economic
p-value significance interpreted as economic edge.

Example:
```
if p < 0.05:
    useful = True
```
without `expectancy > 0`. Authority-Ladder violation: Level 1 (statistical) masquerading as Level 2 (economic).

---

### E-001C — Prose Registration
Finding registered from narrative instead of artifact.

Example: a finding that cites a conversation summary instead of a file:line with reproducibility information.

---

### E-001D — Silent Default
Unmeasured fallback masquerading as truth.

Example:
```
value = x.get("threshold", 0.5)
```
where `0.5` was invented, not measured.

---

### E-001E — Rollup Inflation
Aggregate verdict exceeds the support of its components.

Example:
```
children:
  INSUFFICIENT
  INSUFFICIENT
  INSUFFICIENT

parent:
  HARMFUL
```

Parent confidence cannot exceed child confidence.

---

### E-001F — Decorative Wiring
Configuration or metadata presented as active while ignored.

Example: a config key documented as controlling X, but the code path for X has no consumer of that key (H-Dead / H-Shadow pattern from `KNOWN_ILLUSIONS.md`).

---

## 4. Mandatory Phrase

Whenever any E-001 failure class is discovered:

> **"Caught me overclaiming; I owe you a correction."**

A correction that occurs **before registration** is evidence the governance system succeeded — not a failure.

---

## 5. The Pre-Registration Ritual

Before every finding registration, ask:

1. **What artifact supports this?** (file:line required)
2. **Could INSUFFICIENT explain the observation?**
3. **Am I upgrading sign noise into meaning?**
4. **Is this statistical or economic?** (Authority-Ladder check)
5. **Is the parent stronger than the children?**
6. **Would I phrase this differently after seeing raw counts?**

If any answer exposes uncertainty, confidence must be downgraded or status set to HYPOTHESIS.

---

## 6. CI-Enforced Invariants (Track B)

The following are checked by `tests/governance/test_epistemic_invariants.py`. Two distinct
strengths — and the table says which honestly (per R2: a test that cannot fail is **not**
enforcement and must not be presented as such):

| Invariant | Rule | Strength |
|-----------|------|----------|
| E-001A | An all-underpowered (all-INSUFFICIENT) population must roll up to INSUFFICIENT, never HARMFUL | **ENFORCED (behavioral)** — drives the pure `_consumer_verdict` rollup with synthetic inputs and asserts the output; a logically-broken guard goes red (proven by the red→green test) |
| E-001E | A consumer verdict may not be stronger than its weakest child cell | **ENFORCED (behavioral)** — same helper; `test_red_green_guard_proof` permanently encodes the guard's load-bearing difference |
| Evidence-link | Every confident (Likely/Certain) finding in `docs/current-findings.md` resolves to a real artifact (file exists; line exists when cited) | **ENFORCED** — parses the live findings file and fails on unresolvable evidence |
| E-001B | Statistical ≠ Economic: a p-value line should carry economic context | **ADVISORY (does not fail)** — surfaces candidates via skip for human review; cannot be mechanized without semantics (future E-002). Honestly *not* an assertion |
| Possible-evidence | Possible-confidence findings get a lower evidence bar | **ADVISORY (does not fail)** |

The **behavioral** rows mean the claim *"the F-030 bug pattern is now a test failure"* is literal:
removing the `all_insufficient` guard turns the suite red (demonstrated, then restored). The
**advisory** rows are documentation-as-tooling and are labeled as such — they do not enforce.

These tests must pass for any PR that touches affected files.

---

## 7. Relationship to Existing Governance

| Existing | E-001 Relationship |
|----------|-------------------|
| M4 Qualification Gate (7-gate pipeline) | Correct — the F-030 overclaim was NOT in the qualification gate; it was in the *presentation/rollup* layer. E-001 complements, does not replace. |
| `KNOWN_ILLUSIONS.md` | Covers E-001F (decorative wiring). E-001 extends to the *epistemic* layer (E-001A–E). |
| `docs/current-findings.md` schema | Confidence / Evidence / Reversal fields provide structure. E-001 adds the pre-registration ritual and CI assertions. |
| Pre-registration discipline (Programs 1–4) | Culturally exists but was not formalized. E-001 enshrines it. |
| `CONVENTIONS.md`, `TRIGGER_VOCABULARY.md` | E-001's mandatory phrase is a new trigger: "Caught me overclaiming; I owe you a correction." |

---

## 8. Scope Boundaries

E-001 does **not** modify:

- CRT spine (`src/config_layer/crt_engine_v2.py`)
- M4 Qualification gate (`src/research/qualification.py`)
- Production configs (`configs/production/`)

The bug lives in the **presentation/aggregation** layer — not in the underlying statistics.

---

## 9. Known Violations Discovered

- **F-030 rollup** (regime_conditioning v1.1): spine cells all INSUFFICIENT → rollup printed REGIME_HARMFUL. Corrected in v1.2 (`all_insufficient` guard). Root cause: missing E-001E invariant. Now enforced behaviorally (§6).
- **E-001 self-audit (2026-06-18):** the *first* generation of E-001's own invariant tests overclaimed — E-001A/E-001E were substring-grep (not behavioral), and E-001B + the possible-evidence test could never fail yet were tabled as "Test asserts." Per the program's own classification this is E-001A (overclaim) + E-001F (decorative wiring). Corrected: the per-consumer rollup was extracted to the pure `_consumer_verdict` helper and the A/E tests rewritten to be behavioral with a permanent red→green proof; the advisory tests were relabeled honestly. **This is the recursive loop the program is designed to produce — E-001 became subject to E-001.** Memorialized as F-031.

---

## 10. Program Status

**The program is OPEN, not "finished."** The most likely failure mode is declaring E-001 complete
and never re-subjecting it to its own standard — the self-audit in §9 is the counter-practice.

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 1 | `EPISTEMIC_INTEGRITY.md` (this file) | ✅ DONE |
| 2a | Expand `CLAUDE.md` §6 with Epistemic Integrity ritual | ✅ DONE |
| 2b | Sweep `docs/current-findings.md` | ✅ DONE |
| 2c | Sweep `src/research/` harnesses | ✅ DONE |
| 2d | Re-verify `KNOWN_ILLUSIONS.md` | ✅ DONE |
| 3 | `tests/governance/test_epistemic_invariants.py` | ✅ DONE |
| 3b | Fix violations found (incl. the E-001 self-audit, §9) | ✅ DONE |
| 4 | Register F-031 | ✅ DONE |
| — | Behavioral-invariantization remediation (R1–R5, 2026-06-18) | ✅ DONE; program remains OPEN/recursive |