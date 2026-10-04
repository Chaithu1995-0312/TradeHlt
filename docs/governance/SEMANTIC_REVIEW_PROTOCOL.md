# Adversarial Semantic Review Protocol

**Status:** ACTIVE charter (adopted 2026-08-13)
**Long-form of:** CLAUDE.md §6.8 (thin rule of the same name)
**Enforcement (floor):** `tests/governance/test_semantic_review_protocol.py`
**Authority:** review discipline only — grants **no** production, promotion, economic, or
ontology-edit authority (§6.5).
**Code wins** on conflict with this document.

> **Non-duplication clause.** This charter **does not restate** the doctrines it composes.
> Each rule below points at its existing owner:
>
> | Primitive | Owner (authoritative) |
> |---|---|
> | Fail-closed on unknown meaning | [`SEMANTIC_OS_CONTRACT.md`](SEMANTIC_OS_CONTRACT.md) rule 4 · CLAUDE.md §6.5 (no silent config defaults) |
> | Never silently resolve a conflict → `TruthConflict` | CLAUDE.md §6.2 rules 3 / 4 · the `CORRECTED: <old> -> <new>` ritual |
> | User-authorization gate calibration | [`DOCUMENTATION_DRIFT_PROTOCOL.md`](DOCUMENTATION_DRIFT_PROTOCOL.md) Step 3 |
> | Grounding a repository claim | CLAUDE.md §6.7 · `scripts/governance/query_semantic_os.py --ground` |
> | Behavior-preservation obligations of the turn | [`TASK_CLASSIFICATION_BEHAVIOR_POLICY.md`](TASK_CLASSIFICATION_BEHAVIOR_POLICY.md) |
> | Overclaim classes + pre-registration ritual | [`EPISTEMIC_INTEGRITY.md`](EPISTEMIC_INTEGRITY.md) (Program E-001) |
> | Meaning of market concepts | [`MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md`](MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md) |
> | Which model owns which market question | [`MODEL_INTENT_AUTHORITY_REGISTER.md`](MODEL_INTENT_AUTHORITY_REGISTER.md) (MIAR) |
> | Change lifecycle once a fix is authorized | [`REPOSITORY_CONSTRUCTION_PROTOCOL.md`](REPOSITORY_CONSTRUCTION_PROTOCOL.md) |
| Sujan CRT identity during extraction | [`SUJAN_CRT_IDENTITY_EXTRACTION_SYSTEM.md`](SUJAN_CRT_IDENTITY_EXTRACTION_SYSTEM.md) — Sujan-scoped overlay; load before any Sujan implementation / contract / ontology / backtest. Does not recertify CRT. |

---

## 1. Purpose

A semantic review determines whether repository behavior **means** what it claims — not merely
what it does. It exists because the repository's expensive failures have been *meaning*
failures, in both directions:

- **False negatives** — real semantic defects that survived because each layer looked
  internally consistent (F-060's Gaussian kernel degenerating to a near-constant; F-061/F-064's
  dimensional mix saturating four consumers; F-066's broker-clock session mislabel).
- **False positives** — differences reported as defects that were architecture working as
  designed (F-037's gate-OFF research spine, USER-CLASSIFIED INTENDED; F-036's zone knobs,
  tunable-but-inert by redundancy, whose first mechanism claim was itself an overclaim).

Both classes cost the same review budget. This protocol makes the reviewer carry the burden of
semantic analysis and end in an explicit classification, rather than in an edit.

**The user is not assumed to be a trading-domain expert.** Do not ask the user to resolve
domain semantics that standard market knowledge, repository contracts, architecture, config,
naming, lifecycle semantics, or existing evidence can establish. Ask only where the repository
genuinely does not establish which *policy* is intended (§16).

---

## 2. The five review questions

Every semantic investigation answers these, in order:

1. What does the behavior **currently mean**?
2. What **should** it mean, per domain semantics?
3. Has the repository **established** that meaning?
4. Does the implementation **violate** it?
5. Is a change **authorized**?

A review that answers 1 and 4 but skips 2, 3, or 5 is incomplete, not fast.

---

## 3. Two authority ladders — and their reconciliation

The repository already carries authority orderings (CLAUDE.md §4.0 Runtime Truth Precedence,
§6.5 Authority Ladder and precedence hierarchy, MIAR §0, the ontology contract). **This charter
adds none.** It states the one distinction a reviewer needs, so that answering question 1 and
answering question 2 do not use the same list.

### 3.1 The CURRENT-truth ladder — *what does the system do today?*

| Rung | Source |
|---:|---|
| 1 | Executable source code and observed runtime behavior |
| 2 | Active production configuration (`configs/production/ACTIVE_VERSION` → §4.0 Tier 0) |
| 3 | State topology and lifecycle definitions |
| 4 | Tests that encode intentional contracts |
| 5 | Governance records / findings / certified evidence |
| 6 | Architecture documentation and knowledge artifacts |
| 7 | Historical analysis (`docs/analysis/` — point-in-time, not living) |
| 8 | LLM inference or convention |

Documentation explains intent; it does not establish what the code does. Semantic OS,
encyclopedia, and knowledge-book artifacts are advisory and are never production authority.

### 3.2 The MEANING ladder — *what is this concept?*

**Unchanged and cited, not restated:** the market ontology is authority #1 for meaning with
literal supersession (`MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md`), followed by the feature
pipeline, MIAR (model intent), implementations, then research (`MODEL_INTENT_AUTHORITY_REGISTER.md`
§0 ranks 1–5).

### 3.3 Reconciliation clause (non-optional)

The two ladders answer **different questions** and neither supersedes the other:

- The **CURRENT** ladder never grants meaning. That the code computes X does not make X the
  correct definition of the concept it is named for.
- The **MEANING** ladder never asserts runtime state. That the ontology defines X does not
  make X what the active configuration executes. `configs/production/ACTIVE_VERSION` remains
  Tier 0 for runtime truth (§4.0); "ontology first" governs the **origin and requirement** of a
  change, not automatic unvalidated runtime mutation (`MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md`,
  mechanical constraint 2).

**Divergence between the two ladders is the finding.** Report it as a §6.2 `TruthConflict`
(source A, source B, evidence, impact, recommendation). A reviewer does not pick a winner.

### 3.4 Evidence-quality bands

A **banding of the CURRENT ladder**, not a new scale:

| Band | Rungs | Examples |
|---|---|---|
| **HIGH** | 1–4 | executable source behavior, active config, authoritative ontology node, explicit contract, deterministic test contract, independently reproduced runtime trace |
| **MEDIUM** | 5–7 | architecture documentation, canonical knowledge book, repository encyclopedia, governance descriptions |
| **LOW** | 8 | comments, names, historical notes, previous LLM interpretations, assumptions |

LOW evidence is never promoted into a production semantic claim without corroboration.

**Distinct from claim strength.** `HIGH/MEDIUM/LOW` grades *the source*. `Certain · Likely ·
Possible` grades *the claim* (§6.2 Findings Mandate). Do not merge the vocabularies: a HIGH
source can support a `Possible` claim, and a `Certain` claim always requires HIGH evidence.

---

## 4. The primary rule

**Never conclude "defect" from difference alone.** Six rules, all load-bearing:

- **Different ≠ wrong.** Two layers using different vocabularies may be answering different questions.
- **Unreachable ≠ bug.** A branch not reached under the active configuration may be dormant-but-valid.
- **Configured ≠ must be reachable.** A config token is not a promise that every consumer can emit it.
- **Validated ≠ fully valid.** A validator's PASS promises only what that validator owns.
- **Absent ≠ defective.** An unused value, unexercised branch, or unobserved state violates nothing unless a contract says so.
- **Current ≠ correct.** "The code does X, therefore X is right" is not an argument. State: *the code does X; the domain meaning is Y; the architecture indicates Z; therefore X is / is not consistent with the intended contract.*

None of the following is, by itself, evidence of a defect: two configs with different
vocabularies · one layer producing a value another cannot · a validator accepting what another
rejects · similar names · a token unused by one consumer · a branch unreachable under the active
config · a check present in one implementation and not another · a test expecting what feels
intuitive · another model calling it a bug · behavior that looks inconsistent in isolation.

### Candidate explanations (consider before concluding)

**A** real semantic defect · **B** intentional architectural separation · **C** compatibility
boundary · **D** derived vocabulary · **E** policy vocabulary · **F** lifecycle-specific
vocabulary · **G** dormant but legitimate capability · **H** stale / legacy vocabulary ·
**I** defense in depth · **J** incomplete contract · **K** genuinely unresolved design decision.

---

## 5. CURRENT / INTENDED / RECOMMENDED — never collapsed

Three tiers that must stay textually separate in every review:

| Tier | Question | Existing repository anchor |
|---|---|---|
| **CURRENT** | What do code, config, and tests do today? | §3.1 ladder · `active_models.yaml` `runtime` / `evidence` layers |
| **INTENDED** | What should this mean in the domain? | Ontology (meaning) · MIAR (model intent; an implementation contradicting MIAR is *Semantic Drift*, not a silent redefinition) · `active_models.yaml` `intent` layer |
| **RECOMMENDED** | What should the repository ideally do? | Non-binding. CLAUDE.md §13.8 — advice is everyone's; **no model's advice, including Claude's own, is authority.** |

Collapsing CURRENT into INTENDED produces "the code is correct because it is the code."
Collapsing RECOMMENDED into INTENDED smuggles a preference in as a contract.

---

## 6. Domain-first reasoning

Establish domain meaning **before** implementation terminology. Assume the reader is not a
trading expert; explain the concept in plain language first.

Concepts whose domain meaning must be established before reviewing code that claims them:
candles · OHLC geometry · sessions · market structure · liquidity · displacement · sweep ·
range · expansion · retest · execution · direction · entry · stop loss · take profit · ATR ·
volatility · timeframe · clock and session boundaries · risk · reward:risk · data integrity ·
validation · chronology · causal ordering.

Separate four levels, and never let one impersonate another:

1. **Universal market/domain semantics** — use the standard meaning.
2. **Repository-specific CRT semantics** — trace the repository (`state_identity.py`
   `VALID_TRANSITIONS`, `state_topology.py`, `docs/architecture/event-taxonomy.md`).
3. **Repository-specific strategy policy** — a choice, not a fact.
4. **Implementation detail** — never a source of meaning.

Do not invent proprietary strategy semantics. If none of the four establishes the meaning with
sufficient confidence: **USER AUTHORIZATION REQUIRED** (§16).

---

## 7. Semantic ownership analysis

When two layers appear inconsistent, identify **what question each layer answers**.

For models and engines the ownership answer **already exists** — reuse it, do not rebuild it:
MIAR §4 market-question ownership matrix (exactly one Owner per question),
`docs/topics/model-intent-and-feature-ownership.md` (feature × model matrices), and
`WHAT_HOW_WHO_EXECUTABLE_BOUNDARY_MAP_V1.md`.

This section governs the concepts those do **not** cover — session, ATR units, validation,
direction, timeframe, timestamps, configuration tokens, state labels, identifiers, model
scores. Build the table:

| Layer | Question answered | Input vocabulary | Output vocabulary | Authority | Consumer |
|---|---|---|---|---|---|

Worked shape — "session" legitimately means five different things:

| Layer | Question answered |
|---|---|
| Feature classification | What market/session label does this timestamp belong to? |
| Execution filter | Is execution permitted at this time? |
| CRT structural window | Is this timestamp inside the lifecycle's permitted window? |
| Scoring | How favorable is this time? |
| Adapter / gate | Does this feature label pass this consumer's policy? |

Then ask the only question that matters: **must these vocabularies be identical?** Never unify
two layers merely because they share a word. F-066 is the worked precedent — the session
*feature* was a mislabel and was fixed; the session *filter* was empirically tuned on broker
time and was deliberately left untouched, because relabeling it is an economic decision, not a
bug fix.

---

## 8. Vocabulary reachability

When a configuration carries a token one runtime path cannot emit, do not classify it as a
defect. Answer all twelve:

1. Who owns the vocabulary? 2. Who consumes the configuration? 3. Are there multiple consumers?
4. Does each consumer use the same semantic vocabulary? 5. Is the value derived rather than
configured? 6. Is it adapter vocabulary? 7. Is it compatibility vocabulary? 8. Is it dormant but
intentionally retained? 9. Is it legacy/stale? 10. Would making it reachable change domain
semantics or execution policy? 11. Would removing it break another consumer? 12. Does an
existing test incorrectly assume vocabulary identity?

**Exit rule.** Declare a reachability defect **only** where the architecture establishes that
producer and consumer are supposed to share a vocabulary. Where that relationship is not
established: **USER AUTHORIZATION REQUIRED**.

---

## 9. Validation ownership

Not every validator must validate everything. For each validation layer determine: what it
owns · what it can observe · what another layer can observe that it cannot · its scope (row /
file / sequence / dataset / runtime / execution) · whether it is a hard safety gate or an
informational pre-flight · what PASS actually promises · which layer is the final gate.

A validation split is **valid** when ownership is explicit and the final invariant is still
fail-closed before harmful downstream use. It becomes **unsafe** when a consumer mistakes
partial validation for complete validation, a downstream safety gate can be bypassed, a
research path bypasses the canonical validation rail, a validator's *name* promises more than
its contract, or an accepted artifact can reach an economic consumer with the missing invariant
never enforced anywhere.

**The load-bearing distinction:**

> "validator does not check X"  **is not**  "system permits X to reach the trading engine."

F-039 is the worked precedent: the L3 dataset-integrity pre-flight runs at only two call sites,
every other consumer streams with the always-on inline L1/L2 backstop. The correct verdict was
a *single-layer fragility* plus a corrected overclaim in a docstring — explicitly **not** an
invalidation of the research built on those streams, because the backstop did enforce schema
and chronology. L3 adds confidence, not validity.

---

## 10. Contamination analysis

For every suspected validation or semantic gap, determine whether invalid meaning propagates:

```text
INPUT → VALIDATION → NORMALIZATION → FEATURES → STATE → CONTEXT → SHAPE → CRT
      → MODEL TESTIMONY → DECISION → EXECUTION GEOMETRY → RISK → ORDER
```

Ask: can the invalid object survive? which derived quantities become contaminated? can it reach
ATR, structure, direction, SL/TP, RR, model scores, research conclusions, production execution?

**Severity rule:** a gap is materially more serious the more boundaries an invalid semantic
object crosses before rejection. A gap that is contained at the next boundary is a
defense-in-depth observation; a gap that reaches EXECUTION GEOMETRY or RISK is a defect.

---

## 11. Lifecycle and naming semantics

**Lifecycle.** Never reason about a state or value from its name alone. Trace
`CREATED → TRANSFORMED → CLASSIFIED → CONSUMED → REPLACED → EXPIRED → RESOLVED`. For state
machines: legal transitions, reset transitions, implicit transitions, shadow states,
expiration, rollback, terminal states, event ordering, timestamp ordering, causal ordering.

Keep these five distinct — they are routinely conflated:
**STATE TRANSITION** · **RESET** · **EVENT** · **OBSERVATION** · **DERIVED LABEL**.
A graph edge, a log event, and the runtime mutation are three different objects. F-068 is the
worked precedent: a `[DEADLOCK FIX]` fall-through meant a *reset* path delivered a shadow into
the same candle's TTL countdown, so a configured TTL of N yielded N−1 usable bars.

**Naming.** Names are **evidence, not authority**. When name and behavior disagree: identify
what the implementation computes · what the name claims · callers · consumers · contracts · then
whether the name is correct, historical, misleading, compatibility-preserved, a split identity,
or genuinely wrong. **Do not rename anything during review.** A misleading name is not
automatically a production bug (F-046: three apparent definitions of `body_ratio` were one
canonical definition plus one dead outlier with zero call sites).

---

## 12. Configuration semantics

Trace every relevant value: `DECLARATION → LOAD → NORMALIZATION → RUNTIME OBJECT → CONSUMER →
EFFECT`. Determine active version, source section, defaults, overrides, fallback, merge,
normalization, canonicalization, downstream consumers.

Two config keys with similar names need not share a semantic owner. A configuration discrepancy
is a defect **only** where the architecture establishes the values should be identical.

**Presence is not governance.** A key that is declared and strictly read but whose value never
reaches behavior is a *config illusion* (F-056: `partial_tp_fraction` was strict-read then
discarded against a hardcoded blend at three sites). Follow the value to the behavior, not to
the read.

---

## 13. Test semantics

Tests are **evidence of contracts**, not proof the contract is correct. When a test conflicts
with domain semantics, identify the test's intended contract, the domain meaning, and
repository ownership; then classify the test as correct, stale, over-constrained,
under-specified, characterization-only, or encoding an accidental implementation detail.

**Never** modify a test merely to make the current implementation green.
**Never** delete an xfail because it is inconvenient, and never invert one.
**Never** convert an unresolved semantic question into a passing test without resolving the
underlying meaning. An xfail that represents an unresolved semantic decision is **kept**.

---

## 14. The adversarial method

When a suspected defect is reported, reproduce the claim independently. Do **not** begin by
agreeing or disagreeing.

1. **Reproduce** — the exact configuration, code path, input, timestamp, state, consumer, test.
2. **Trace** — upstream and downstream.
3. **Identify the semantic owner** (§7).
4. **Establish domain meaning** (§6) — outside the implementation.
5. **Compare** — CURRENT implementation vs domain semantics vs architectural contract (§5).
6. **Classify** (§15).
7. **Assess risk** — production, research, data contamination, execution, replay, governance.
8. **Recommend** the smallest semantically correct action.
9. **Authorization gate** — if the repository does not establish the intended behavior, stop at
   the recommendation (§16).

### 14.1 External claims are hypotheses (non-optional)

A claim that "X is a bug" arriving from another model, an audit report, a generated document,
or a previous analysis is a **hypothesis**, never evidence. Reproduce it against source before
repeating it. Ask: what domain principle supports it? what repository contract? what consumer
depends on it? what alternative interpretation exists? what breaks if it is wrong — and if it is
right?

Two worked precedents where an external trace was source-verified and found **wrong**:

- **F-067** — a received bug-trace called the double `update_emas` call `EMA(EMA(close))` making
  momentum "overly sensitive." Source-verified **backwards**: double application gives effective
  α = 2α − α², which *compresses* the trend spread and makes approval harder.
- **F-068** — a bug-trace claimed the off-by-one was "documented in the code with the comment
  'same bar burns 1'." That comment **did not exist in source**; it existed only in a prior
  session log. The claim was `CORRECTED`, and the comment was then added for real.

This is CLAUDE.md §13.8 applied to review: other models *propose*; the reviewer verifies.

---

## 15. Required review output

For every unresolved semantic question, produce exactly this structure:

```text
# [QUESTION]
## RECOMMENDATION            KEEP CURRENT ARCHITECTURE | CHANGE REQUIRED | DOCUMENTATION ONLY
                             | TEST CONTRACT ONLY | INVESTIGATE FURTHER | USER AUTHORIZATION REQUIRED
## CONFIDENCE                HIGH | MEDIUM | LOW — and why
## DOMAIN REASONING          plain language first; no implementation terms until the concept is clear
## CURRENT BEHAVIOR          files, symbols, line ranges, active config, consumers, tests, runtime path
## INTENDED SEMANTICS        universal domain / repository-specific / strategy policy, separated
## CODEBASE EVIDENCE         concrete, ranked by §3.4 band
## SEMANTIC OWNERSHIP        the §7 table when multiple layers are involved
## ALTERNATIVE INTERPRETATION  the strongest reasonable alternative — never a strawman — plus the
                             evidence that would make it correct
## FAILURE / CONTAMINATION RISK   what goes wrong if the behavior is misunderstood or bypassed (§10)
## WHAT SHOULD BE TESTED     semantic contracts, not implementation details
## WHAT SHOULD NOT YET BE CHANGED   explicit list: code, config, tests, contracts, xfails
## USER AUTHORIZATION REQUIRED     the decision, as a small number of plain-language choices
```

Do not cite a file because its name sounds relevant. Repository nouns, joins, symbols, and
evidence ids in **CODEBASE EVIDENCE** are subject to §6.7 grounding — if
`query_semantic_os.py --ground` does not return `GROUNDED`, state the status and do not
introduce the token.

---

## 16. Final decision discipline

Every review closes with **exactly one**:

`CONFIRMED DEFECT` · `INTENTIONAL SEMANTIC SEPARATION` · `STALE / LEGACY ARTIFACT` ·
`COMPATIBILITY ARTIFACT` · `DEFENSE-IN-DEPTH OPPORTUNITY` · `TEST / CONTRACT GAP` ·
`DOCUMENTATION GAP` · `DORMANT BUT VALID` · `INSUFFICIENT EVIDENCE` ·
`USER AUTHORIZATION REQUIRED`.

**Do not use the word "bug" unless you can name the violated semantic contract.**

### When authorization is required

The user is not expected to decide semantics that standard domain knowledge or repository
evidence can establish. The user **must** authorize changes to: trading session policy · what a
state means · execution eligibility · risk semantics · the meaning of a configuration field ·
validation ownership · a lifecycle transition · a canonical vocabulary · removal of a
compatibility token · converting an xfail into a passing contract · a production invariant.

Present a small number of understandable choices — for example: **A.** preserve the current
semantic separation · **B.** unify the two concepts · **C.** introduce a new explicit policy.
Do not require implementation knowledge to choose. Then **stop at the recommendation.**

---

## 17. No silent remediation

During review, do **not**: edit production code · edit active configuration · modify or delete
production tests · delete or invert xfails · rename modules · change contracts · change the
ontology · change session windows · change risk rules · change execution rules · or "fix" a
semantic issue because it looks obviously wrong.

Review is for understanding and recommendation. **Implementation is a separate authorized
turn**, and once authorized it runs through `REPOSITORY_CONSTRUCTION_PROTOCOL.md`, not directly
from the review.

Prefer preserving explicit architectural boundaries over unifying concepts for aesthetic
consistency. Do not create duplicate validation, vocabularies, ownership, calculations, state
machines, session calendars, or semantic registries unless the additional layer has an explicit
contract and safety purpose. "Defense in depth" is valid only when its ownership and PASS
semantics are clear.

---

## 18. High-risk trading surfaces

Treat these as high-risk: OHLC geometry · timestamp basis · timezone / broker clock · session
windows · timeframe aggregation · ATR units · price units vs normalized units · direction ·
entry price · stop-loss geometry · take-profit geometry · reward:risk · intrabar vs close-only
exits · lookahead · state transition ordering · reset ordering · causal feature construction ·
future data leakage · execution eligibility · capital and risk gates.

Each of these has already produced a real finding here:

| Surface | Finding |
|---|---|
| Broker clock / session basis | F-066 — MT5 server time labeled UTC; 53.36% of XAUUSD bars mis-labeled |
| ATR units (price vs relative) | F-072 — canonical ATR is close-relative but SL/TP geometry required price units |
| Normalization basis | F-061 / F-064 — `legacy ≡ corrected × close`; four consumers saturated on crypto |
| Lookahead / PIT | F-051 — centered-swing binding leaks future bars into 10 of 38 canonical dims |
| Exit model | F-025 — close-only vs intrabar changes the sign of the conclusion |
| Reset ordering | F-068 — reset fall-through consumed one bar of a configured TTL |

**A mistake in these areas produces a system that is internally consistent while being
economically or causally wrong.** Semantic consistency alone is therefore not sufficient. Always
ask: *does this behavior represent the market concept it claims to represent?*

---

## 19. Enforcement

| Mechanism | Path | Enforces |
|---|---|---|
| Structure floor | `tests/governance/test_semantic_review_protocol.py` | this charter's required sections, the 10 classifications, the required output headings, the §3.3 reconciliation clause, and the CLAUDE.md §6.8 thin rule |
| Green floor | `scripts/maintenance/check_governance_invariants.py` | `docs/governance/` and `tests/governance/` are governed prefixes — a change here runs the curated floor |
| Grounding | `scripts/governance/query_semantic_os.py --ground` · `tests/test_semantic_grounding.py` | CODEBASE EVIDENCE tokens (§15) |
| Session log | `tests/test_session_log.py` | the §6 mandate every review turn closes with |

**Honest residuals (disclosed, not hidden):**

1. The floor is a **presence/structure** check, like `test_documentation_drift_protocol.py`. It
   cannot detect a review that follows the headings while reasoning badly.
2. Nothing mechanically prevents a session from performing remediation *without* first
   declaring a review. §17 binds a turn that has entered review, not every turn.
3. The §3.4 evidence bands are applied by judgment; there is no machine grader.
4. The §7 ownership tables for non-model concepts are built per-review and are not yet
   accumulated into a durable registry. If that recurs, the correct move is to extend the
   existing ownership artifacts, not to start a parallel one (§17).

---

## Authority

This protocol grants **no new authority**. It never bypasses the §6 SESSION LOG,
write-authority / path-guard, the `y/N` confirm, the `APPROVE` promotion gate, or user approval
for irreversible or outward-facing actions. It changes no §4.0 precedence, adds no rung to the
§6.5 Authority Ladder, and does not alter the ontology's meaning-authority under §6.6 or MIAR §0.

A completed review earns *documentation and recommendation* standing only. Production authority
is still earned solely by demonstrated G001 improvement (§6.5) — a correct semantic analysis is
not a licence to change behavior.
