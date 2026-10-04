# Incorporate the Adversarial Semantic Review Protocol into CLAUDE.md

> Created: 2026-08-13 · Type: governance doctrine (docs + test floor only)

## Context

The user supplied a ~25-section "DOMAIN + CODE SEMANTIC REVIEWER" protocol: a discipline for
auditing whether repository behavior *means* what it claims, without treating every
inconsistency as a bug. It needs to become an operating rule, not a pasted document.

The repository already carries most of the protocol's *primitives* scattered across five
doctrines (§4.0, §6.2, §6.5, §6.6, §6.7, MIAR). What it does **not** have is a named **review
mode** that composes them, plus three genuinely absent pieces:

1. **The `different ≠ wrong` classification discipline.** Nothing today stops a session from
   filing "config token X is unreachable from layer Y" as a defect. The F-036 mechanism
   correction and the F-037 "USER-CLASSIFIED INTENDED" scope-fix were both this failure class,
   caught late and by hand.
2. **A generalized don't-trust-another-LLM verification rule.** Only §13.8 plus two worked
   precedents exist (F-067: a received bug-trace's EMA mechanism was source-verified
   *backwards*; F-068: a bug-trace cited a mitigating code comment that does not exist in
   source). The `feedback_verify_source_not_comments` memory records this as a recurring class.
3. **The CURRENT / INTENDED / RECOMMENDED triad stated as one frame.** The pieces exist
   (MIAR = intended, `active_models.yaml` truth layers, §13.8 advice ≠ authority) but are
   never required to be kept separate in a single analysis.

Intended outcome: a session asked to audit semantics runs a bounded, fail-closed review that
ends in a classification and a recommendation — never a silent edit to production code,
config, tests, or xfails.

## Approach

Follow the repo's established doctrine-shipping pattern (§6.2 → `DOCUMENTATION_DRIFT_PROTOCOL.md`,
§6.6 → `MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md`, §6.7 → `SEMANTIC_OS_CONTRACT.md`):
**thin always-loaded rule in CLAUDE.md + full charter under `docs/governance/` + a
`tests/governance/` presence floor.**

### Deliverable 1 — `docs/governance/SEMANTIC_REVIEW_PROTOCOL.md` (new charter)

Match the observed charter skeleton: H1 → status/authority header block → `---` → purpose →
rules → enforcement table → non-goals/honest residuals → closing `## Authority` disclaimer.

Header block states, in the style of `SEMANTIC_OS_CONTRACT.md:1-8`:
`**Status:** ACTIVE charter` · `**Authority:** review discipline only — grants no production,
promotion, or economic authority (§6.5)` · `**Code wins** on conflict with this document.`

Sections:

1. **Purpose + what this does NOT restate.** Explicit non-duplication clause modeled on
   `DOCUMENTATION_DRIFT_PROTOCOL.md:3-12`, pointing at the owners it composes rather than
   re-deriving: fail-closed → `SEMANTIC_OS_CONTRACT.md` rule 4 + §6.5 no-silent-defaults;
   no-silent-remediation → §6.2 rules 3/4 + the `CORRECTED: <old> -> <new>` ritual;
   user-authorization gate → `DOCUMENTATION_DRIFT_PROTOCOL.md` Step 3 calibration;
   claim grounding → §6.7 / `query_semantic_os.py --ground`; task class →
   `TASK_CLASSIFICATION_BEHAVIOR_POLICY.md`; epistemic pre-registration → `EPISTEMIC_INTEGRITY.md`.

2. **The five review questions** (means today / should mean / repo established it / implementation
   violates it / change authorized) — the mandate.

3. **Two authority ladders + reconciliation.** This is the section that must not create a sixth
   competing list. State plainly:
   - **CURRENT-truth ladder** (what the system *does* today): executable source + runtime
     behavior → active production config → state topology/lifecycle → tests encoding
     intentional contracts → governance records → docs → historical analysis → LLM inference.
   - **MEANING ladder** (what a concept *is*) — unchanged, cited not restated:
     `MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md` (ontology = authority #1, literal supersession)
     and `MODEL_INTENT_AUTHORITY_REGISTER.md` §0 ranks 1–5.
   - **Reconciliation clause:** the ladders answer different questions; neither supersedes
     the other; the CURRENT ladder never grants meaning and the MEANING ladder never asserts
     runtime state. `configs/production/ACTIVE_VERSION` remains Tier 0 for runtime truth per
     §4.0. **Divergence between the two ladders is the finding**, reported as a §6.2
     `TruthConflict` — not resolved by the reviewer.
   - **Evidence-quality bands** are defined as a *banding of the CURRENT ladder*, not a new
     scale: HIGH = source/config/deterministic-test/reproduced trace; MEDIUM = architecture
     and knowledge docs, governance descriptions; LOW = comments, names, historical notes,
     prior LLM interpretations. Explicitly distinguished from `Certain · Likely · Possible`
     (claim strength, §6.2 Findings Mandate) so the two vocabularies do not merge.

4. **Primary rule + classification set.** `Different ≠ wrong` · `Unreachable ≠ bug` ·
   `Configured ≠ must be reachable` · `Validated ≠ fully valid` · `Absent ≠ defective` ·
   `Current ≠ correct`. Followed by the A–K candidate-explanation list (real defect /
   intentional separation / compatibility boundary / derived vocabulary / policy vocabulary /
   lifecycle vocabulary / dormant-but-legitimate / stale-legacy / defense-in-depth /
   incomplete contract / unresolved design decision).

5. **CURRENT / INTENDED / RECOMMENDED — never collapsed.** Cross-reference MIAR as the
   existing *intended* authority for engines, `active_models.yaml`'s four truth layers, and
   §13.8 for why RECOMMENDED carries no authority.

6. **Domain-first reasoning.** The trading-concept list (candles, OHLC geometry, sessions,
   liquidity, sweep/displacement/expansion/retest, ATR, entry/SL/TP, reward:risk, chronology,
   causal ordering …) and the three-way split: universal domain meaning vs repository-specific
   CRT semantics vs strategy policy. Rule: standard domain knowledge is the reviewer's burden,
   not the user's.

7. **Semantic ownership analysis.** The `Layer | Question answered | Input vocabulary | Output
   vocabulary | Authority | Consumer` table format. Scope note: for *models/engines* the
   ownership answer already exists — reuse `MODEL_INTENT_AUTHORITY_REGISTER.md` §4
   market-question ownership matrix, `docs/topics/model-intent-and-feature-ownership.md`
   (feature×model matrices), and `WHAT_HOW_WHO_EXECUTABLE_BOUNDARY_MAP_V1.md`. This section
   governs the concepts those do *not* cover: session, ATR units, validation, direction,
   timeframe, timestamps, config tokens, state labels.

8. **Vocabulary reachability.** The 12-question checklist, ending in the fail-closed exit:
   declare a reachability defect only where the architecture establishes producer and consumer
   share a vocabulary; otherwise `USER AUTHORIZATION REQUIRED`.

9. **Validation ownership.** Per-layer questions (owns / can observe / row vs sequence vs
   dataset vs runtime scope / hard gate vs informational pre-flight / what PASS promises /
   which layer is final). The load-bearing distinction: *"validator does not check X"* is not
   *"system permits X to reach the trading engine."* Cite F-039 as the worked precedent (L3
   dataset-integrity runs at only two call sites; scope guard says L3 adds confidence, not
   validity).

10. **Contamination trace.** INPUT → VALIDATION → NORMALIZATION → FEATURES → STATE → CONTEXT →
    SHAPE → CRT → MODEL TESTIMONY → DECISION → EXECUTION GEOMETRY → RISK → ORDER, with the
    boundary-crossing severity rule.

11. **Lifecycle and naming semantics.** CREATED → … → RESOLVED; distinguish STATE TRANSITION /
    RESET / EVENT / OBSERVATION / DERIVED LABEL (F-068's `reset_to_range` fall-through is the
    worked example). Names are evidence, not authority; do not rename during review.

12. **Test semantics.** Never modify a test to make the implementation green; never delete or
    invert an xfail; an xfail encoding an unresolved semantic decision is preserved.

13. **Adversarial method (9 steps)** — reproduce → trace → identify owner → establish domain
    meaning → compare → classify → assess risk → recommend smallest correct action →
    authorization gate. Includes the **external-claim rule**: any bug claim arriving from
    another model, audit report, or generated doc is a *hypothesis*; reproduce it against
    source before repeating it. Cite F-067 and F-068 as the two precedents where an external
    trace was source-verified and found wrong.

14. **Required review output** — the fixed heading set (RECOMMENDATION / CONFIDENCE / DOMAIN
    REASONING / CURRENT BEHAVIOR / INTENDED SEMANTICS / CODEBASE EVIDENCE / SEMANTIC OWNERSHIP /
    ALTERNATIVE INTERPRETATION / FAILURE-CONTAMINATION RISK / WHAT SHOULD BE TESTED / WHAT
    SHOULD NOT YET BE CHANGED / USER AUTHORIZATION REQUIRED). Note that CODEBASE EVIDENCE
    entries are subject to §6.7 grounding.

15. **Final decision discipline** — exactly one of the 10 classifications: `CONFIRMED DEFECT` ·
    `INTENTIONAL SEMANTIC SEPARATION` · `STALE / LEGACY ARTIFACT` · `COMPATIBILITY ARTIFACT` ·
    `DEFENSE-IN-DEPTH OPPORTUNITY` · `TEST / CONTRACT GAP` · `DOCUMENTATION GAP` · `DORMANT BUT
    VALID` · `INSUFFICIENT EVIDENCE` · `USER AUTHORIZATION REQUIRED`. "Bug" is disallowed
    unless the violated semantic contract is named.

16. **No silent remediation.** Review never edits production code, active config, production
    tests, xfails, contracts, ontology, session windows, risk or execution rules.
    Implementation is a separately authorized turn.

17. **High-risk trading surfaces** — the §22 list (timestamp basis, broker clock, ATR units,
    price vs normalized units, intrabar vs close-only exits, lookahead, reset ordering,
    execution eligibility …), each anchored to the finding that made it real where one exists
    (F-066 broker clock, F-072/F-064 ATR and dimensional units, F-051 PIT/lookahead, F-025
    exit model).

18. **Enforcement** (mechanism → path → test table), **Non-goals / honest residuals**, and a
    closing **`## Authority`** section stating the protocol grants no production, promotion,
    economic, or ontology-edit authority.

Citation style note: cite files by path and symbol. Avoid the `path:line · Symbol` dual form
unless the line is verified, since `tests/test_doc_citations.py` resolves that form with a
±30-line window.

### Deliverable 2 — CLAUDE.md `## 6.8` (thin, ~30 lines)

Insert between the `---` separator at `CLAUDE.md:638` and `## 7.` at `CLAUDE.md:640`. Use `##`
(§6.1–§6.7 are all top-level `##`, not `###`). Blockquote header pointing at the charter and
the test floor, matching §6.7's shape.

Content, compressed to the always-loaded essentials:
- The five review questions.
- The six `≠` rules (`different ≠ wrong` … `current ≠ correct`).
- Never collapse CURRENT / INTENDED / RECOMMENDED.
- The two-ladder pointer with the one-line reconciliation ("the CURRENT ladder never grants
  meaning; the MEANING ladder (§6.6 / MIAR) never asserts runtime state; divergence is a
  §6.2 `TruthConflict`, not a reviewer's call").
- External bug claims are hypotheses until source-verified (§13.8; F-067/F-068 precedent).
- The 10 final classifications, listed inline as tokens.
- **No silent remediation** — review never edits production code, config, tests, or xfails.
- Closing: grants no new authority (§6.5).

### Deliverable 3 — `tests/governance/test_semantic_review_protocol.py`

Model on `tests/governance/test_documentation_drift_protocol.py` (presence/structure floor,
explicitly not behavioral). `tests/governance/` is already a `GREEN_FLOOR` entry in
`scripts/maintenance/check_governance_invariants.py:70`, so no policy constant changes and no
update to `tests/test_governance_invariant_check.py`.

Assertions:
- Charter file exists and carries the required section headings.
- All 10 final-classification tokens appear in the charter.
- All required review-output headings appear in the charter.
- The reconciliation clause exists and names both `§6.6` (or the ontology contract) and MIAR —
  the guard against the charter silently becoming a sixth authority list.
- The non-duplication clause exists (charter declares what it does not restate).
- `CLAUDE.md` contains `## 6.8`, links `docs/governance/SEMANTIC_REVIEW_PROTOCOL.md`, and
  carries the six `≠` rules plus the no-silent-remediation sentence.
- `## 6.8` appears after `## 6.7` and before `## 7.` (ordering guard).

## Explicitly not doing

Per the user's selection: **no** `§2` companion-table row and **no** `Review` Tier-2 trigger in
§12 / `docs/architecture/trigger-vocabulary.md`. Discoverability rests on `§6.8` being
always-loaded. No production code, config, ontology, or existing test is touched. The two
existing xfails (`tests/test_bitnet_parity.py`, `tests/test_auto_tuner_multi.py`) are unrelated
and stay untouched. No existing authority table (§4.0, §6.5, §6.6, MIAR §0) is edited.

## Verification

```bash
python -m pytest -q tests/governance/test_semantic_review_protocol.py
```

Then the surrounding floors, since `docs/governance/` and `tests/governance/` are governed
prefixes:

```bash
python -m pytest -q tests/governance/ tests/test_doc_citations.py tests/test_current_findings.py tests/test_session_log.py
```

Then the full curated gate the pre-commit hook will run:

```bash
python scripts/maintenance/check_governance_invariants.py --all
```

Expected: the new test passes; `test_doc_citations.py` stays green (charter avoids unverified
`path:line · Symbol` citations); GREEN_FLOOR result unchanged from its pre-change baseline —
capture that baseline first so any red is attributable.

Manual check: re-read `## 6.8` against `## 6.6` and `## 6.7` for tone and length parity, and
confirm the charter's non-duplication clause names every doctrine it composes.

## Closing obligations

- Append the `📝 SESSION LOG ENTRY` block to `assistant_project.md` (§6) — this is a governed
  change and the commit-linkage guard expects a same-day well-formed entry.
- No `docs/current-findings.md` entry: this ships a review discipline, not a validated or
  overturned conclusion, so the Findings Mandate does not fire.
- No `docs/topics/` sync: no code a topic covers changes.
