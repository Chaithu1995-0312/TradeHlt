# Episode Semantic Integration — Phase 2 (locked diagnosis + program)

**Status:** DESIGN / RESEARCH AUTHORITY (advisory — never production §6.5)  
**Date:** 2026-08-09  
**Phase 2A:** **CLOSED / CERTIFIED** (Cliff #1 · VALUE → STATE)  
**Phase 2B:** **CLOSED / SHIPPED** (Cliff #2 · RELATED · typed propositions O11/O12)  
**Phase 2C:** **CLOSED / SHIPPED** (Cliff #3 · AGREED · O14 AGR-v0 fold)  
**Authority:** research/docs only · `PRODUCTION_BEHAVIOR_CHANGED=NO` by default  
**Does not supersede:** Semantic OS L0–L6 (`SEMANTIC_OS_V1_DESIGN.md` / `SEMANTIC_OS_CONTRACT.md`)  
**Evidence base:**  
- `results/research/xauusd_episode_semantic_reconstruction/*`  
- `src/features/magnitude_states.py` · `src/research/episode_propositions.py` · `src/research/episode_agreement.py`  
- Encyclopedia E1b authority model (ontology WHAT → registry HOW → pipeline emit)

**Hard non-goals (still):** do not revisit 2A; do not collapse O11 conflicts into false COHERENT; do not reopen POL-O12; no spine/economic authority from Phase 2 alone.

---

## 0. Locked diagnosis (non-negotiable wording)

> **The repository is not non-semantic. It contains descriptive semantics and declarative semantics, but it does not yet produce integrated semantics for a market episode.**

### 0.1 Post–Phase-2A certification (locked 2026-08-09)

| Property | 2A result | Notes |
|---|---|---|
| O6 body commitment | **COVERED 10/10** | FM-071 · identity bins on scale-safe `body_ratio` |
| O7 ATR magnitude | **COVERED 10/10** | FM-072 · series percentile of relative `atr` |
| O18 momentum magnitude | **COVERED 10/10** | FM-073 · abs series percentile (F-061-safe) |
| STATE layer | **OK 10/10** | Cliff #1 closed on cert corpus |
| New measurements | **None** | interpretation only |
| CRT spine modified | **No** | shadow only |
| Production behavior | **No** | `PRODUCTION_BEHAVIOR_CHANGED=NO` |
| AGREEMENT | **BREAK 10/10 — correctly** | **Do not “fix” 2A by touching Agreement** |

Semantic change (not “three new features”):

```text
BEFORE 2A                         AFTER 2A
body_ratio = 0.5648               body_ratio  → MediumCommitment
atr        = 0.00264              relative ATR → HighAtrMagnitude
momentum   = 923                  |momentum|  → MediumMomentumMagnitude
     │                                   │
     ▼                                   ▼
   VALUE                               STATE
     X
   (no magnitude state)
```

Architecture choice certified: continuous → integer domain → `FeatureStateEncoder`  
(preserves pure integer encoder; no mixed continuous/discrete encoder).

Normalization justification certified:

| Work | Method | Why |
|---|---|---|
| O6 | identity bins | `body_ratio` already scale-safe ∈[0,1]; high edge 0.70 CRT-coherent |
| O7 | series percentiles | avoid absolute ATR thresholds across regimes |
| O18 | abs series percentile | F-061 forbids fixed absolute bands on legacy `momentum_score` |

**Magnitude states are semantic states, not episode explanations.**  
`MediumCommitment + HighAtrMagnitude + … + CRT RETEST SHORT` is a richer substrate — it still does **not** assert *same event*. That is why AGREEMENT must remain BREAK until 2C, and why 2B is proposition-first.

Geometry census / gate2b red on this branch remains a **quarantined residual** (pre-existing derivation drift). It must **not** contaminate the Phase-2A semantic conclusion.

### 0.2 Post–Phase-2B certification (locked 2026-08-09)

| Property | 2B result | Notes |
|---|---|---|
| O11 DIRECTION_ALIGNMENT | **typed 10/10** | CONFLICT **5** · INSUFFICIENT **4** · SAME_EVENT **1** — conflicts **represented**, not erased |
| O12 CHAPTER_VS_STRUCTURE_SCORE | **ORTHOGONAL 10/10** | **POL-O12-SCORE-NOT-CHAPTER** — quality testimony ≠ chapter membership |
| Exit claims per episode | **2/2** | plus diagnostics QUALITY_VS_DIRECTION, MAGNITUDE_SUBSTRATE |
| Propositions without Agreement | **required** | having relations ≠ having episode-level fold |
| AGREEMENT | **BREAK 10/10 — correctly** | O14 not built; **do not treat 2B as Agreement solved** |
| 2A magnitude states | **untouched** | do not revisit |

**What 2B added conceptually:** the hop **RELATED** (typed relationship between surfaces).

```text
PROPOSITION  = typed relationship between semantic surfaces
AGREEMENT    = episode-level conclusion formed by folding those relationships
```

O12 is a **semantic resolution**, not an evasion:

```text
CRT chapter            → "Which structural chapter is the market in?"
structure_rule_score   → "How strong/valid is structure per this model?"
→ ORTHOGONAL (different questions)
```

### 0.3 Post–Phase-2C certification (locked 2026-08-09)

| Property | 2C result | Notes |
|---|---|---|
| O14 Agreement object | **COVERED 10/10** | object present = COVERED (verdict independent) |
| AGR-v0 verdicts | **BREAK 5 · PARTIAL 4 · COHERENT 1** | CONFLICT preserved on 5 O11 episodes |
| AGREEMENT layer | BREAK 5 / PARTIAL 4 / OK 1 | maps from verdict |
| layerwise_describable | **5/10** | no longer 0 — fold exists; residual PARTIAL context/testimony |
| full_coherent | 0/10 | CONTEXT/TESTIMONY still not all OK |
| False agreement | **none** | O11 CONFLICT never COHERENT |

### 0.4 Current ladder status (post-2C + L4/L7 closure 2026-08-12)

```text
VALUE          ████████████  10/10 OK
STATE          ████████████  10/10 OK   ← 2A
CONTEXT        ████████████  10/10 OK   ← L4 structured contract + temporal UNKNOWN causality
SHAPE          █████████░░░  ~9/10
CRT            ████████████  10/10 OK
TESTIMONY      ████████████  10/10 OK   ← L7 question/relationship + CRT story≠score
PROPOSITIONS   ████████████  2B CLOSED  (RELATED)
AGREEMENT      █████░░░░░░░  2C CLOSED  (BREAK 5 / PARTIAL 4 / OK 1 — conflict preserved)
```

Conceptual chain:

```text
MEASURED → INTERPRETED → COMPOSED → NAMED → STRUCTURED → TESTIFIED → RELATED → AGREED
   VALUE      STATE       CONTEXT    SHAPE      CRT        TESTIMONY    2B        2C
```

| Metric | Value | Source |
|---|---|---|
| O14 object | COVERED 10/10 | `coverage_census` |
| AGREEMENT BREAK/PARTIAL/OK | 5 / 4 / 1 | `phase2_chain_coherence` |
| O11 CONFLICT episodes → BREAK | **5/5** | conflict-preservation floor |
| O12 ORTHOGONAL | 10/10 | POL-O12 non-regression |
| O16 temporal causality | COVERED 10/10 | observed session + causality=UNKNOWN |
| O19 CRT story vs testimony | COVERED 10/10 | `crt_story` / `crt_testimony` split |
| CONTEXT / TESTIMONY layers | OK 10/10 | L4/L7 structured contracts |

**L4/L7 closure (2026-08-12, research shadow):** CONTEXT and TESTIMONY carry structured contracts
(`dimension_records` / completeness / temporal; question / availability / relationship_to_story /
CRT story≠score). AGREEMENT is **not** re-opened or re-defined — O11 CONFLICT still BREAK.
Residual non-blockers: O5 participation vs expansion PARTIAL, O15 wick UNREPRESENTED, O11 direction
CONFLICT (represented, not erased).

### 0.5 STATE census of the 39-slot vector (2026-08-12) — CLOSED

Authoritative artifact: [`STATE_SEMANTIC_CENSUS_39.md`](STATE_SEMANTIC_CENSUS_39.md).

| Result | Value |
|---|---|
| 39/39 classified | **YES** |
| A STATE_COVERED | 16 |
| B VALUE_SEMANTIC | 7 |
| C STATE_REQUIRED_EXISTING_VALUE | **0** |
| D (among 39) | 0 |
| E IMPLEMENTATION_INTERMEDIATE | 5 |
| F INTENTIONALLY_UNBANDED | 11 |
| G UNKNOWN | 0 |
| New states implemented | none (C=0) |
| `PRODUCTION_BEHAVIOR_CHANGED` | **NO** |
| STATE_CLOSURE | **CLOSED** |

Locked conclusions (do not reverse without new authority):

- **O5 PARTIAL** is a participation-state ↔ expansion-**context** relationship, not a missing
  Layer-2 participation state (`volume_spike` already NoSpike/VolumeSpike).
- **O15** remains UNREPRESENTED as a *directional absorption* semantic; pursuit class = **D**
  (FM-011/012 research inactive; `price_position` computed-then-discarded with no FM id).
  Do not invent wick states without measurement promotion.
- Continuous `27/39` is a **census remainder**, not an implementation backlog.
- L4 CONTEXT / L7 TESTIMONY / AGR-v0 **not reopened**.

---

## 1. Three independent axes (do not collapse)

### Axis 1 — Where is the statement? (Market episode ladder)

```text
VALUE → STATE → CONTEXT → SHAPE → CRT → TESTIMONY → AGREEMENT
```

### Axis 2 — What kind of statement is it?

| Kind | Question |
|---|---|
| **semantic** | What does it mean / own / guarantee / relate? |
| **descriptive** | Where is it / what exists / what count? |
| **implementation** | How is it coded? |
| **evidence** | What was observed / measured? |
| **governance** | Who decides / what is authoritative? |

### Axis 3 — How complete is the meaning?

| Grade | Name | Example |
|---|---|---|
| **D** | Descriptive semantics | “`feature_states.py` converts values into states” (role only) |
| **L** | Declarative semantics | `HighVolatility` = named state + domain + owner + invariant |
| **I** | Integrated semantics | “This episode is a bearish retest **because** magnitudes, states, context, shape, CRT, and testimony describe the **same** event, with conflicts explicitly resolved.” |

**“Semantic” is not binary.** A statement can be semantic at D-grade and still fail I-grade.

---

## 2. Orthogonal ladders (never merge)

| Ladder | Purpose | Primary artifacts |
|---|---|---|
| **Semantic OS L0–L6** | How an agent understands the **repository** | CN / BD / JN / CT / FileIdentity / OBJ |
| **Market episode reasoning** | How an agent understands a **market episode** | feature values → states → context → shape → CRT → testimony → agreement |

```text
SEMANTIC OS                         MARKET REASONING
L0 Identity                         VALUE
L1 Concept                          STATE
L2 Behavior                         CONTEXT
L3 Relationships                    SHAPE
L4 Evidence                         CRT
L5 Governance                       TESTIMONY
L6 Implementation                   AGREEMENT
```

CN/BD/JN/CT may **name and own** episode-ladder concepts later; they must **not** be asked to substitute for AGREEMENT or continuous STATE bands. That is a different product surface.

---

## 3. VALUE is not “anti-semantic” — the missing hop is VALUE → STATE

Correct wording:

- On the episode ladder, raw `body_ratio = 0.5648` / `ATR = 6.186` are **measurements** (Axis-2: evidence).
- Meaning begins when measurement is **interpreted** into STATE.
- Integration begins when multiple interpreted surfaces compose into one episode proposition.

```text
VALUE (measured)     --exists today--
   │
   X  Cliff 1: no continuous magnitude states (O6/O7/O18)
   ▼
STATE (interpreted)
   │
   X  Cliff 2: layers side-by-side, not same-event (O11/O12)
   ▼
composed proposition
   │
   X  Cliff 3: no typed AGREEMENT object (O14)
   ▼
AGREEMENT (I-grade)
```

**Do not invent new measurements.** The reconstruction already holds continuous snapshots. Phase 2 promotes measured surfaces into semantic states, then connects them.

---

## 4. The three cliffs (precise)

### Cliff 1 — Measurement → Meaning (O6 / O7 / O18)

| Id | Surface already measured | Missing STATE |
|---|---|---|
| **O6** | `body_ratio` (e.g. 0.5648) | body commitment bands |
| **O7** | ATR (event absolute and/or vector relative) | ATR magnitude / intensity bands |
| **O18** | `momentum_score` (and/or scale-safe substitute) | momentum magnitude bands |

Encoder fact (implementation constraint, not a goal change):  
`FeatureStateEncoder` only maps **integer enumerated** ontology `states` (`feature_states.py`). Continuous features currently carry `states: []` and appear in `continuous_features` (27/39 class).  
`volatility_regime` (FM-050) is the golden pattern: **pre-discretize → integer domain → named states**.

**F-061 guard:** do **not** freeze absolute bands on legacy `momentum_score` / `ema_spread` (price-scaled). Prefer percentile/tercile style (like vol regime) and/or corrected ATR-normalized identities (FM-030/031) before banding.

### Cliff 2 — Meaning → Shared episode (O11 / O12)

Independent legitimate statements already exist:

```text
STATE:     BearishBreak + LowerLow + HighVolatility
SHAPE:     BearishBreakoutExpansion
CRT:       RETEST / SHORT
TESTIMONY: gaussian≈0.88 quality; crt structure_rule_score=0.000
```

Missing proposition:

```text
THESE DESCRIBE THE SAME EVENT.   (or: they conflict under contract C…)
```

| Id | Gap |
|---|---|
| **O11** | CRT direction vs context/shape co-description |
| **O12** | CRT chapter vs `structure_rule_score` (score often 0 while story advanced) |

### Cliff 3 — Shared episode → Agreement (O14)

Today `aligned` / `tension` / `silent` exist as **reconstruction report fields** — observation of relationships, not a first-class semantic contract.

```text
CRT says X · Shape says Y · Testimony says Z
                │
                ???   ← missing product
                │
            AGREEMENT
```

**Agreement is not another score.**  
It is the assertion:

> These independent semantic surfaces refer to the **same episode**, and their tensions/silences have an **explicit interpretation**.

---

## 5. Canonical market-reasoning model (freeze)

```text
                 MARKET REALITY
                      │
                      ▼
                    VALUE
               measured quantities
                      │
                      ▼
                    STATE
             semantic magnitudes + flags
                      │
                      ▼
                  CONTEXT
             combined conditions
                      │
                      ▼
                   SHAPE
             named morphology
                      │
                      ▼
                    CRT
            temporal structure
                      │
                      ▼
                 TESTIMONY
           independent questions
                      │
                      ▼
                 AGREEMENT
        same-event interpretation
                      │
                      ▼
            DECISION / CAPITAL
```

Transformation chain (product language):

```text
MEASURED → INTERPRETED → COMPOSED → NAMED → STRUCTURED → TESTIFIED → AGREED
```

Today the repository advances far along this chain. It does **not** yet make the final **AGREED** assertion as a typed, certified object.

---

## 6. Program order (B+C, tightened) — chosen path

Not A (taxonomy-only freeze without program), not C alone (bands without join), not D (hold).

```text
PHASE 2A — Cliff 1
  O6 body_commitment · O7 atr_magnitude · O18 momentum_magnitude
  VALUE → STATE
  no new indicators

        ↓

PHASE 2B — Cliff 2
  O11 CRT dir ↔ context/shape
  O12 CRT chapter ↔ structure_rule_score
  cross-layer propositions (same-event claims)

        ↓

PHASE 2C — Cliff 3
  O14 typed AGREEMENT object
  aligned / tension / silent + resolution policy
  first-class (not report-only)

        ↓

CERTIFICATION
  same 10 episodes (xauusd_episode_semantic_reconstruction)
  recompute phase2_chain_coherence
  target: improve AGREEMENT + STATE/CONTEXT; publish before/after matrix
  do not claim economic authority
```

### Non-goals (all phases)

- New OHLC formulas / new indicators / new CRT states for coverage theater  
- Production spine consumption without a separate §6.5 authority grant  
- Merging episode ladder into Semantic OS entity inventory as a substitute for AGREEMENT  
- Absolute bands on F-061-defective dimensions  
- Treating Gaussian/zone/rr scores as market-IS semantics (they remain testimony)

### Authority

| Layer | Authority |
|---|---|
| Design of states / AGREEMENT | research + ontology WHAT first (§6.6) |
| Runtime spine / fusion / risk | unchanged unless separately authorized |
| Economic promote | **NONE** from Phase 2 alone |
| Certification | episode coherence metrics only |

---

## 7. Phase 2A — design constraints (ready to implement next)

### 7.1 Pattern to copy

`volatility_regime` (FM-050): continuous ATR-derived intensity → rolling rank → integer `{0,1,2}` → states `LowVolatility|NormalVolatility|HighVolatility`. Config-owned cuts; encoder stays integer pure.

### 7.2 Candidate bindings (declare in ontology first)

| Work item | Prefer measured surface | Why | Band style (proposal, not yet frozen numbers) |
|---|---|---|---|
| O6 | `body_ratio` FM-010 ∈[0,1] | Scale-safe, already in continuous snapshot | terciles or fixed body bands (Low/Med/High commitment) |
| O7 | **absolute** ATR path used by vol regime (`atr_14` raw), **not** only close-relative FM-041 alone without naming | Avoid dual-ATR identity confusion (ontology already documents FM-041 vs absolute) | percentile/tercile intensity **or** explicit dual: relative + absolute named states |
| O18 | Prefer **ATR-normalized momentum** (FM-031 path) or **percentile of momentum** | Legacy `momentum_score` FM-023 is F-061-contaminated for fixed cuts | rank bands, not raw 923 → “High” |

Exact cut values: config-owned (strict `_require` when wired), not Python literals. Shadow-only until certified.

### 7.3 Schema options (choose in implement turn)

| Option | Pros | Cons |
|---|---|---|
| **A — Pre-discretize + integer states** (vol-regime pattern) | Matches encoder today; no encoder rewrite | Needs emission of integer codes (pipeline or shadow pre-bin) |
| **B — Extend encoder for continuous range bands** | Direct VALUE→STATE on floats | Schema + validator + parity surface; larger change |

**Default recommendation:** Option A for Phase 2A (minimal architecture risk, copies proven path).

### 7.4 Exit criteria (2A)

- Ontology declares non-empty `states` (or sibling magnitude-state identities) for O6/O7/O18 targets  
- Encoder classifies them without `X_UNMAPPED` on the 10-episode anchors (or documents residual X_ rate)  
- Same continuous **measurements** as reconstruction — no new feature math  
- `continuous_features` shrinks for those slots (or explicit parallel magnitude-state identities if dual-key)  
- Re-run census: O6/O7/O18 leave UNREPRESENTED  
- Still shadow: spine does not consume new states  
- Doc + tests + SESSION LOG same turn

---

## 8. Phase 2B — same-event propositions (SHIPPED · proposition-first)

**Status:** **SHIPPED 2026-08-09** — `src/research/episode_propositions.py`  
**Hard rule still holds:** do **not** build O14 / AGREEMENT in this phase (2C only).

### 8.0 Why 2B is not “more states” and not Agreement

After 2A the remaining problem is:

> **Determine when STATE + CONTEXT + SHAPE + CRT + TESTIMONY are propositions about the same event.**

That is **O11 / O12**, not O6/O7/O18 and not O14.

```text
2A  VALUE → STATE                         ✓ CLOSED
          ↓
2B  STATE / CONTEXT / SHAPE / CRT
    ↕ TESTIMONY
    → typed same-event propositions       ← frontier
          ↓
2C  propositions → AGREEMENT object       (blocked until 2B)
```

**Hard rule:** do not create O14 yet. Agreement is a fold over propositions; without typed propositions, Agreement is only a report heuristic.

### 8.1 Empirical inputs (from the same 10-episode corpus)

| Observation | Role in 2B | Post-2A census signal |
|---|---|---|
| **O11** CRT direction ↔ context/shape direction | directional same-event / conflict | **CONTRADICTORY 5/10**, PARTIAL 4, COVERED 1 — live conflict class |
| **O12** CRT chapter ↔ structure-rule testimony | chapter vs quality-score channels | census class is **field-binding sensitive** — 2B must pin the exact testimony field (`structure_rule_score` vs generic `score`) under contract before claiming ORTHOGONAL vs CONFLICT |

These are not theoretical; they appear on the cert corpus (e.g. LONG + BearishStructuralBreak; advanced CRT chapter vs low structure score in earlier reconstruction notes).

### 8.2 Product: typed Proposition (not free text)

```text
Proposition = {
  proposition_id,          # stable within episode, e.g. P-O11-dir, P-O12-chapter-score
  episode_id,
  claim_kind,              # DIRECTION_ALIGNMENT | CHAPTER_VS_SCORE | …
  surfaces: {
    state?:     [...],     # optional magnitude/discrete states cited
    context?:   [...],
    shape?:     {name, family, dir},
    crt?:       {state, direction, event},
    testimony?: {model_id, semantic, value, question}
  },
  relation: SAME_EVENT | ORTHOGONAL | CONFLICT | SILENT | INSUFFICIENT,
  evidence_refs: [...],    # episode field paths / source anchors
  resolution: null | {
    policy_id,             # e.g. POL-O12-SCORE-NOT-CHAPTER
    meaning                  # one sentence: what the relation is allowed to mean
  },
  authority: research_shadow
}
```

Relation vocabulary (closed):

| Relation | Meaning |
|---|---|
| **SAME_EVENT** | Surfaces are co-describing one market episode under the claim_kind |
| **ORTHOGONAL** | Both true in their domains; **not** required to agree (declared non-join) |
| **CONFLICT** | Claim_kind expects co-description; observed values disagree |
| **SILENT** | A required surface is declared absent / non-participating |
| **INSUFFICIENT** | Missing direction / score / shape — cannot adjudicate |

### 8.3 Minimum claim kinds for 2B exit

| Claim kind | Observation | Surfaces | Default policy sketch (draft until cert) |
|---|---|---|---|
| `DIRECTION_ALIGNMENT` | O11 | CRT.direction × trend_bias × shape dir | mismatch → **CONFLICT** unless one side neutral → **INSUFFICIENT** |
| `CHAPTER_VS_STRUCTURE_SCORE` | O12 | CRT.state × crt structure testimony | pin field; if score answers “structure quality” not “chapter valid” → prefer **ORTHOGONAL** with explicit policy — **do not silently treat score 0 as chapter invalid** without a contract |

Also emit (diagnostic, not exit-blocking):

| Claim kind | Surfaces | Notes |
|---|---|---|
| `QUALITY_VS_DIRECTION` | gaussian/rr quality × CRT.direction | default **ORTHOGONAL** (quality ≠ direction) |
| `MAGNITUDE_SUBSTRATE` | body_commitment × atr_magnitude × momentum_magnitude | **not** a same-event claim alone — substrate only (prevents overclaiming 2A as integration) |

### 8.4 Non-goals (2B)

- O14 Agreement object / verdict fold  
- New measurements / new CRT states  
- Spine consumption of propositions  
- “Fixing” AGREEMENT BREAK by redefining layerwise metrics  
- Treating geometry-census red as a 2B failure  
- Economic authority

### 8.5 Exit criteria (2B)

1. Schema + pure builder for Proposition on the **same 10 episode ids**  
2. Every episode emits typed O11 + O12 propositions (no free-text-only path)  
3. Census cells for O11/O12 re-expressed as proposition relation counts (still report COVERED/CONTRADICTORY for continuity)  
4. Documented policy choice for CHAPTER_VS_STRUCTURE_SCORE (ORTHOGONAL vs CONFLICT) with evidence field pinned  
5. AGREEMENT remains BREAK 10/10 by construction (O14 absent) — **required**, not a failure  
6. Tests: schema exhaustiveness, deterministic rebuild, no spine import  
7. `PRODUCTION_BEHAVIOR_CHANGED=NO`

### 8.6 Implementation sketch (when user says Implement)

| Piece | Location (proposal) |
|---|---|
| Schema / dataclass | `src/features/episode_propositions.py` (shadow) **or** `src/research/episode_propositions.py` |
| Builder input | existing `episodes.json` fields only |
| Wire | reconstruction optional emit `propositions: [...]`; census reads them |
| Tests | `tests/test_episode_propositions.py` |
| Doc | this section + session log |

Prefer **research package** if the surface must never be mistaken for feature-layer spine code; prefer **features** only if it is clearly marked shadow sibling of `model_evidence` / `magnitude_states`.

---

## 9. Phase 2C — AGREEMENT object (CLOSED / SHIPPED)

**Status:** **SHIPPED 2026-08-09** — `src/research/episode_agreement.py` (AGR-v0)  
**Inputs:** 2B `propositions[]` only (plus surface inventory already on the episode).  
**Does not:** discover new relationships, revisit 2A bands, collapse O11 CONFLICT, reinterpret O12 scores as CRT states.

### 9.0 Precise job

```text
Magnitude states (O6/O7/O18)
Context / Shape / CRT / Testimony
        │
        ▼
  PROPOSITIONS[]     ← 2B (already shipped)
        │
        ▼
  AGREEMENT OBJECT   ← 2C (fold only)
```

> **Agreement must preserve conflict; it must not turn conflict into false agreement.**

So an episode with `O11=CONFLICT` + `O12=ORTHOGONAL` must **not** magically become `AGREEMENT=TRUE` / verdict COHERENT without an explicit, documented resolution state that still surfaces the conflict.

### 9.1 Questions the object must answer

```text
What semantic surfaces participated?
Which propositions were SAME_EVENT?
Which were ORTHOGONAL?
Which were CONFLICT?
Which were SILENT?
Which were INSUFFICIENT?
What is the resulting episode-level interpretation?
What conflicts remain unresolved?
```

### 9.2 Schema (freeze · research shadow)

```text
Agreement = {
  episode_id,
  policy_version: "AGR-v0",
  authority: research_shadow,

  # inventory (fold inputs — not re-derived meaning)
  surfaces_participating: {
    magnitude_states?: [...],
    feature_states?: [...],
    context?: [...],
    shape?: {...},
    crt?: {...},
    testimony?: [...]
  },

  # fold of 2B propositions by relation (preserve all — do not drop CONFLICT)
  by_relation: {
    SAME_EVENT:   [Proposition...],
    ORTHOGONAL:   [Proposition...],
    CONFLICT:     [Proposition...],
    SILENT:       [Proposition...],
    INSUFFICIENT: [Proposition...]
  },

  # legacy-shaped views (derived from by_relation; must stay consistent)
  aligned:   [...],   # SAME_EVENT (+ optional ORTHOGONAL-with-policy notes)
  tension:   [...],   # CONFLICT (required if any CONFLICT props)
  silent:    [...],   # SILENT + declared absences
  insufficient: [...],

  unresolved_conflicts: [Proposition...],  # subset of CONFLICT still open
  episode_interpretation: str,             # one paragraph; must mention unresolved conflicts if any

  verdict: COHERENT | PARTIAL | BREAK,
  # COHERENT: no CONFLICT; exit claims present; no blocking INSUFFICIENT on O11/O12
  # PARTIAL:  only ORTHOGONAL/INSUFFICIENT/SILENT issues; or incomplete substrate
  # BREAK:    any unresolved CONFLICT on exit claims (O11/O12), or missing exit propositions
}
```

### 9.3 Verdict policy (AGR-v0 · draft freeze)

| Verdict | When |
|---|---|
| **BREAK** | Any exit-claim proposition with `relation=CONFLICT` remains in `unresolved_conflicts` **or** O11/O12 propositions missing |
| **PARTIAL** | No CONFLICT, but any INSUFFICIENT/SILENT on exit claims, or only ORTHOGONAL joins (no SAME_EVENT) |
| **COHERENT** | Exit claims present; zero CONFLICT; zero blocking INSUFFICIENT on O11; at least one SAME_EVENT **or** explicit policy that all-ORTHOGONAL-with-no-conflict is COHERENT (choose at implement time; default: require no CONFLICT and full exit claims → PARTIAL if zero SAME_EVENT) |

**Default recommendation for first cert:**  
`CONFLICT ⇒ BREAK` always.  
All-ORTHOGONAL (O11 absent direction → INSUFFICIENT, O12 ORTHOGONAL) ⇒ **PARTIAL**, not COHERENT.  
COHERENT only when O11 is SAME_EVENT and O12 is ORTHOGONAL/SAME_EVENT with no CONFLICT.

This guarantees the cert set’s 5 O11 CONFLICT episodes stay **BREAK** — conflict preserved.

### 9.4 Non-goals (2C)

- Re-deriving O11/O12 logic outside `episode_propositions`  
- Score thresholds that reopen POL-O12  
- Forcing 10/10 COHERENT  
- Spine / fusion / risk consumption  
- Economic claims  

### 9.5 Exit criteria (2C)

1. Typed Agreement builder consumes `propositions[]` only for relations  
2. Every cert episode has Agreement object; verdict rules match §9.3  
3. Episodes with O11 CONFLICT → verdict **BREAK** (regression floor)  
4. Census O14 moves from UNREPRESENTED toward COVERED (object present), independent of verdict  
5. `phase2_chain_coherence` AGREEMENT layer reflects verdict (BREAK/PARTIAL/OK mapping)  
6. Tests: conflict preservation, POL-O12 non-regression, deterministic fold  
7. `PRODUCTION_BEHAVIOR_CHANGED=NO`

### 9.6 Implementation sketch

| Piece | Location |
|---|---|
| Builder | `src/research/episode_agreement.py` (sibling of propositions) |
| Wire | reconstruction + census; replace legacy free-text `agreement` dict or nest under `agreement_object` |
| Tests | `tests/test_episode_agreement.py` |
| Policy id | `AGR-v0` |

---

## 10. Certification protocol (all phases)

1. Inputs: fixed `episodes.json` anchors (same 10 ids).  
2. No corpus retarget without recording new baseline.  
3. Metrics: `phase2_chain_coherence` layer counts + coverage_census O* cells.  
4. Claims allowed: **descriptive / structural semantic connectivity** only.  
5. Claims forbidden: expectancy, promote, fusion weight, production enable.  
6. `PRODUCTION_BEHAVIOR_CHANGED=NO` unless a separate behavior-change program is authorized.

---

## 11. What we are not missing

| Not missing | Evidence |
|---|---|
| More documentation volume | Book/encyclopedia strong; dashboard ~92.5% docs vs ~1.3% semantic |
| More CRT states | CRT 10/10 OK on episodes |
| More model scores | O13 testimony present 10/10 |
| New measurement indicators | continuous_snapshot already holds body/ATR/momentum class fields |
| Semantic OS rewrite | OS is repo-meaning framework; episode ladder is separate product |

**Phase-2 missing product:** none (VALUE/STATE/RELATED/AGREED chain closed in research shadow).  
Residual gaps (O5/O15/O16, CONTEXT partial) are **not** Phase-2 cliff reopeners.

---

## 12. Phase 2A delivery record (2026-08-09)

| Item | Delivery |
|---|---|
| FM-071 `body_commitment` | structural_states · identity bins on `body_ratio` · edges `[0.33, 0.70]` |
| FM-072 `atr_magnitude` | series percentile of relative `atr` · edges `[0.33, 0.66]` |
| FM-073 `momentum_magnitude` | abs series percentile of `momentum_score` · F-061-safe |
| Code | `src/features/magnitude_states.py` + reconstruction/census hooks |
| Cert | same 10 episodes: O6/O7/O18 **COVERED 10/10**; STATE **OK 10/10**; AGREEMENT still **BREAK 10/10** |
| Spine | not consumed · production config unchanged |

### Phase 2B delivery record (2026-08-09)

| Item | Delivery |
|---|---|
| Module | `src/research/episode_propositions.py` |
| O11 | `DIRECTION_ALIGNMENT` → SAME_EVENT / CONFLICT / INSUFFICIENT |
| O12 | `CHAPTER_VS_STRUCTURE_SCORE` + **POL-O12-SCORE-NOT-CHAPTER** → ORTHOGONAL when both present |
| Diagnostics | `QUALITY_VS_DIRECTION`, `MAGNITUDE_SUBSTRATE` (both ORTHOGONAL by policy) |
| Wire | reconstruction emits `propositions`; census attaches if missing + relation counts |
| O14 | **NOT built** — AGREEMENT BREAK 10/10 by design |

### Phase 2C delivery record (2026-08-09)

| Item | Delivery |
|---|---|
| Module | `src/research/episode_agreement.py` |
| Policy | **AGR-v0** — CONFLICT⇒BREAK; COHERENT requires O11 SAME_EVENT |
| Wire | reconstruction + census attach; `agreement_object` + legacy `agreement` view |
| Cert | O14 COVERED 10/10; verdicts BREAK 5 / PARTIAL 4 / COHERENT 1 |
| Conflict floor | all 5 O11 CONFLICT episodes → BREAK |

### Immediate next step

Phase 2 cliffs closed. Optional follow-ons (out of Phase-2 cliff scope): CONTEXT/TESTIMONY partial residual, O5/O15/O16 — **not** reopening 2A/2B/2C product contracts.

---

## 13. Document control

| Field | Value |
|---|---|
| Supersedes | Informal session taxonomy only (no prior sealed phase-2 episode program) |
| Related | `SEMANTIC_OS_V1_DESIGN.md`, `SEMANTIC_OS_CONTRACT.md`, E1b encyclopedia, F-061, F-047, F-048 |
| Reopen | New measurements required (would contradict §3) · spine consumption requested · economic claim attempted |
| Owner surface | Feature semantic pipeline (shadow) + ontology WHAT · research certification |

`PRODUCTION_BEHAVIOR_CHANGED=NO`
