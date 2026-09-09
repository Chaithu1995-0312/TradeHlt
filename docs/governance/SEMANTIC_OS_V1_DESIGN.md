# Repository Semantic Operating System — Design (Semantic OS v1)

**Status:** DESIGN AUTHORITY (v1)  
**Date:** 2026-08-08  
**Authority:** advisory — never overrides code, config, or §4.0 runtime truth  
**Implements / extends:** walking skeleton under `docs/governance/semantic_os/` + `src/governance/semantic_*.py`  
**Scoreboard:** [`REPOSITORY_COVERAGE_DASHBOARD.md`](REPOSITORY_COVERAGE_DASHBOARD.md)  
**Charter twin:** [`SEMANTIC_OS_CONTRACT.md`](SEMANTIC_OS_CONTRACT.md)

---

## 0. Problem statement

### What the repository already answers

| Record system | Answers |
|---|---|
| Canonical Knowledge Book | Architecture, spine, doctrine |
| Repository Encyclopedia + JSONL twin | File purpose, package, phase, group |
| Governance ledgers / findings / research registries | Evidence and falsification history |
| Market ontology + formula registry | Feature mathematics (WHAT) |
| Production YAML / configs | Tunable HOW behavior |

These answer: *what files exist, what modules do, where things live.*

### What they do not answer

| Question |
|---|
| What **concepts** exist, independent of folders? |
| What **boundaries** own behavior? |
| What **journeys** describe executable execution? |
| Which **executable behavior** is covered? |
| Which **concept** justifies an implementation? |

**Documentation coverage is strong (~92.5%). Semantic coverage is weak (~1.3%).**  
**Documentation ≠ Semantic Understanding.**

The Coverage Dashboard is the **scoreboard**.  
The Semantic OS is the **mechanism** for improving those scores.

---

## 1. Fundamental principle (non-negotiable)

### Do NOT design the Semantic OS around the codebase.

### Design it around how modern foundation models organize knowledge.  
### Then map the repository into that structure.

```text
WRONG                         RIGHT
─────                         ─────
Code                          Foundation-model semantic structure
  ↓                             ↓
Semantic Layer                Repository mapping
                                ↓
                              Implementation (last hop)
```

### Interface role

```text
Repository
    ↓
Semantic OS          ← identity, concept, behavior, relationships, evidence, governance
    ↓
LLM latent reasoning
    ↓
Natural-language understanding
    ↓
Implementation lookup   ← last step, never first
```

Optimize for: **machine reasoning, human understanding, semantic completeness** — not more documentation volume.

---

## 2. Semantic stack (design first — L0…L6)

Design and validate this stack **before** growing CN/BD/JN inventories. Layers are **knowledge organization**, not folder layout.

| Layer | Name | Question | Primary entity / view | Human or machine |
|---|---|---|---|---|
| **L0** | Identity | What is this? | Identity kinds (Candle, Feature, Trade, Engine, Program, Finding, Config, Module, …) | Machine-enumerable + thin hand catalog |
| **L1** | Concept | Why does it exist? | **CN-*** | **HUMAN** |
| **L2** | Behavior | What happens? | **JN-*** (journeys) | **HUMAN** |
| **L3** | Relationships | How does it interact? | **BD-*** (boundaries), contracts, deps/consumers | BD human; deps **MACHINE** |
| **L4** | Evidence | Why believe this? | Findings, tests, research, measurements | Join **MACHINE**; claims human |
| **L5** | Governance | Who decides? | Authority ladder, promotion, config policy, ownership | Doctrine human; surfaces joined |
| **L6** | Implementation | Where is the code? | **OBJ:\<path\>** (Python, YAML, JSON, registries) | **100% MACHINE** |

**Rule:** Implementation (L6) is always the **final mapping layer**, never the starting vocabulary.

### Orthogonal ladder — market episode reasoning (do not merge with L0–L6)

```text
VALUE → STATE → CONTEXT → SHAPE → CRT → TESTIMONY → AGREEMENT
```

- **Semantic OS L0–L6** = repository meaning.  
- **Episode ladder** = market-event meaning.  
- Integrated episode semantics (same-event AGREEMENT) is a **separate product**.  
Program lock: [`EPISODE_SEMANTIC_INTEGRATION_PHASE2.md`](EPISODE_SEMANTIC_INTEGRATION_PHASE2.md).

### Identity catalog (L0 — minimal, not a parallel ontology)

L0 kinds are **labels for reasoning**, not file types:

| Identity kind | Examples in this repo |
|---|---|
| MarketStructure | CRT state, sweep, displacement, weekly range |
| NumericSurface | Canonical feature vector, FM-* |
| DecisionAct | Fusion score, ACCEPT/REJECT, risk approve |
| OrderGeometry | Entry/SL/TP plan |
| ConfigIdentity | ACTIVE_VERSION, CRTConfig, feature_pipeline section |
| EvidenceUnit | Finding F-*, hypothesis H-*, ValidationReport |
| ResearchProgram | Program 1…9 |
| RuntimeModule | Any OBJ path under src/scripts |
| AgentAct | Intent, PLAN_REGISTRY plan, control-plane command |

L0 is a **closed enum** in the Semantic OS schema (extensible only via design revision + validator update). Objects and concepts carry `identity_kind` when known; never invent mid-query.

**Do not confuse `identity_kind` (this L0 table) with the FileIdentity *record kind* (§3).**
`identity_kind` classifies the TYPE of a concept/object's meaning (MarketStructure, NumericSurface,
…) — a property. FileIdentity (v1.1, `kind: file_identity`) is a sixth first-class *record* that
maps one physical Python module to a rename-stable `semantic_id -> semantic_name -> physical_path`,
distinct from any object's `identity_kind`. The word "identity" is doing two different jobs on
purpose; both are kept because renaming either would break more references than it clarifies. See
`docs/governance/SEMANTIC_FILE_IDENTITY_REPORT.md`.

---

## 3. First-class entities (minimal set)

Six first-class entity kinds (v1.1 — FileIdentity added, see §3.1). Everything else is a
**generated view**.

| Id prefix | Entity | Authored? | Role |
|---|---|---|---|
| **CN-** | Concept | HAND | Stable meaning; why it exists; non-goals; invariants |
| **BD-** | Boundary | HAND | Architectural seam + protected invariant + member globs |
| **JN-** | Journey | HAND | Ordered semantic path (behavior) across concepts/boundaries |
| **CT-** | Contract | HAND (or sealed join) | Constraints: inputs/outputs/guarantees/non-guarantees/tests |
| dotted slug | FileIdentity | HAND (Tier 1/2) + GENERATED (Tier 3) | `semantic_id -> semantic_name -> physical_path` + filename_semantic_status classification for ONE module |
| **OBJ:** | Object | **GENERATED** | Every code unit on disk (module/script) — zero hand maintenance |

### 3.1 FileIdentity (v1.1) — why a sixth kind, not a seam on OBJ

A Concept (CN-*) is coarse — 15 records today, several backing more than one physical file
(`CN-003`/`CN-015` both cite `src/runtime/backtest_v2.py`). An Object (`OBJ:<path>`) is
path-*keyed* and fully machine-generated, so it cannot survive a rename and carries no reviewed
classification of whether the filename still matches the module's behavior. Neither gives a
module a name that (a) is stable across a future rename and (b) can say a filename is
*misleading* rather than merely unexplained. FileIdentity fills exactly that gap:

- **Id = a dotted lowercase slug** (`crt.state_machine`, `engines.candle_polarity_scorer`), not a
  numbered prefix — chosen so Tier-3 (machine-derived) ids can be a pure function of the path
  with zero counter state, and so the slug IS the thing an agent says out loud.
- **Tiered, not uniformly hand-authored**: Tier 1 (HIGH, hand-verified from source) and Tier 2
  (MEDIUM, boundary-claimed but not independently source-read) are hand-authored in
  `docs/governance/semantic_os/file_identities.yaml`; Tier 3 (LOW, `filename_semantic_status:
  UNKNOWN`) is **generated at seed time** by `governance.semantic_identity.derive_tier3_identities`
  for every remaining code-universe path, never materialized in the YAML (would violate the
  hand-author rule at the volume of ~700+ rows — see the report §3).
- **`filename_semantic_status`** (ALIGNED/HISTORICAL/MISLEADING/COMPATIBILITY/SPLIT/UNKNOWN) is
  the field this kind exists to carry — e.g. `src/engines/rr_engine.py` is classified MISLEADING
  because it computes a candle-polarity index bounded [0.5, 1.0], not economic reward:risk.
- Does **not** duplicate CN/BD/JN/CT/OBJ: `concept_ids` and `owner_boundary`-style joins stay
  read-only pointers (owner_boundary is DERIVED, never hand-written on a FileIdentity record —
  see `_IDENTITY_ONLY_FORBIDDEN_FIELDS` in `semantic_os.py`), and OBJ gains five derived fields
  (`semantic_id`, `semantic_name`, `filename_semantic_status`, `identity_tier`,
  `identity_provenance`) from an in-process join rather than owning the meaning itself.
- Grants **no rename or production authority** — `authority: advisory` is pinned, identical to
  every other kind in this file (§6.5).

### Preferred generated views (not independent ontologies)

| View | Derived from |
|---|---|
| Knowledge Graph | CN ↔ BD ↔ JN ↔ CT ↔ OBJ joins |
| Journey Graph | JN steps + next edges |
| Impact Graph | OBJ imports + config consumers + FM lineage + findings (L6 impact engine) |
| Intent Graph | Agent intents / PLAN_REGISTRY ↔ CN/JN (projection) |
| Coverage scores | OBJ universe ⋉ all entities (Coverage Dashboard) |

**Do not** invent parallel registries for “knowledge graph nodes” that duplicate CN/BD/JN/CT/OBJ/FileIdentity.

### Contract entity (CT-*) — new in v1 design vs skeleton

Today, contracts are **embedded** in Boundary YAML (`contract:` blocks) and scattered schema docs. v1 design **elevates CT-*** as first-class:

| CT field (hand) | Content |
|---|---|
| `id` | `CT-NNN` |
| `name` | Human label |
| `governs_concepts` | CN-* list |
| `governs_boundaries` | BD-* list (optional) |
| `inputs` / `outputs` | Semantic I/O |
| `guarantees` / `non_guarantees` | Explicit |
| `enforced_by_tests` | test paths (FK) |
| `authority_layer` | WHAT / HOW / WHO / RESEARCH |
| `findings` | F-* that constrain or falsify |

Boundaries may **reference** CT-* rather than inline large contract prose (migration: Phase B).

---

## 4. Repository mapping into the stack

| Repository surface | Maps to |
|---|---|
| Market ontology (`market_ontology.yaml`) | L1 Concepts (cite FM/SEM) + L6 formula implementations |
| CRT state machine | L2 Behavior (journeys) + L0 MarketStructure identity |
| Feature pipeline | L6 Objects + L1 CN Canonical Feature Vector + BD Feature Production |
| Findings / research registry | L4 Evidence |
| Promotion / ACTIVE_VERSION / Ultron | L5 Governance + L2 governance journeys |
| Python / YAML / JSON / registries | L6 Objects |
| Encyclopedia / Book | **Documentation views** — not Semantic OS entities |
| Coverage Dashboard | Measurement of L1–L6 join completeness |

### CRT design philosophy (structural language, not a strategy)

**CRT is the structural language of the market**, not a proprietary strategy brand.

| Good | Bad |
|---|---|
| Same market structure for a candle | Different CRT interpretation of the same candle |
| Different consumer decisions (fusion / research / LLM / analytics) | Consumer-specific redefinition of sweep/disp/retest |
| Structural config (ranges, transitions, TTL) | Consumer thresholds mixed into structural truth |

**Separate:**

- **Structural configuration** — what the market narrative *is* (CRT geometry, states, ontology).  
- **Consumer configuration** — how a consumer *reacts* (fusion weights, session filters, BitNet gate, research M4 bar).

Multiple systems (Fusion, Research, Execution, LLM, Analytics) **consume the same structure**. Consumer tuning is OK. Changing structural interpretation without a new concept/journey/evidence is not.

### YAML philosophy (semantics vs mechanics)

| Put in ontology / YAML / formula registry | Keep in Python |
|---|---|
| Market semantics (what a quantity means) | Execution mechanics (loops, I/O, orchestration) |
| Declared FM identities, states, shapes | Hot-path efficiency, fail-fast loaders |
| Structural CRT thresholds that *define* narrative | Consumer scoring glue |

**Do not** blindly migrate Python into YAML. Every CRT line should eventually be classified:

- **Market Semantics** → ontology / structural config, or  
- **Execution Mechanics** → remain in `crt_engine_v2` / runtime.

---

## 5. Human vs machine authorship

### Humans write (meaning)

- Intent and “why”
- Concepts (CN)
- Boundaries (BD) and their invariants
- Journeys (JN) and failure modes (must cite concept-declared modes)
- Contracts (CT)
- FileIdentity Tier 1/2 (`semantic_id`/`semantic_name`/`filename_semantic_status` for one module)
- Explicit unknowns / fail-closed notes

### Machines derive (never hand-write)

- Imports, dependents, package, bytes, sha256  
- Reachability / present_in  
- Call/import graph  
- Test importers (AST)  
- Config-key consumers (where joinable)  
- Object inventory from **disk enumeration**  
- Coverage scores  

**Validation fails closed** if humans author derived fields (`_FORBIDDEN_HAND_FIELDS` pattern already in `semantic_os.py`).

### Fail closed on unknowns

Do not fabricate:

- Concept inventory completeness  
- Boundary ownership  
- Journey participation  
- Owner attribution  
- Behavior coverage  
- Object denominator  

Emit `UNKNOWN` / `UNATTRIBUTED` / empty join / `AMBIGUOUS` — never invent CN/BD/JN ids at query time.

---

## 6. Query model (LLM + human interface)

The Semantic OS must answer, for any identity:

| Question | Resolution path |
|---|---|
| Why does this object exist? | OBJ → purpose (encyclopedia/docstring) + CN.why |
| Which Concept owns it? | OBJ → concepts[] / BD.concepts |
| Which Boundary governs it? | OBJ → owner_boundary |
| Which Journey uses it? | OBJ → journey_steps |
| Which Contracts constrain it? | OBJ → CT via BD/CN |
| Which Evidence supports it? | OBJ → findings_evidence / tests / framework |
| Where is it implemented? | OBJ.path (L6) |
| How does changing it affect behavior? | Impact view: imports + journeys + consumers + FM lineage |

**Anti-pattern:** folder browse → open Python first.

**Canonical path:** Concept/Journey question → Semantic OS join → code last.

Existing L5 surface: `src/governance/semantic_query.py` (extend, do not replace).  
Closed-environment companion: `src/governance/semantic_grounding.py` (`SemanticGrounder`) —
four claim kinds (NOUN / RELATIONSHIP / IMPLEMENTATION / EVIDENCE) fail closed to
GROUNDED / UNKNOWN / AMBIGUOUS / UNANSWERABLE. CLI: `scripts/governance/query_semantic_os.py`.
Contract: CT-008. This grounds *repository claims*; it does not execute market semantics.
L6 impact: `semantic_impact.py` (complete if missing) for blast radius + draft BUILD_IMPACT_MANIFEST.

---

## 7. Coverage philosophy (measure understanding)

### Documentation layers (already strong)

| Layer | Role |
|---|---|
| Book | Explains **architecture** |
| Encyclopedia | Explains **implementation** |
| Semantic OS | Explains **meaning** |
| Coverage Dashboard | Measures **understanding** |

### Dimensions (v1 dashboard — already partially live)

| Dimension | Meaning |
|---|---|
| Physical | Objects enriched / objects on disk |
| Book | Book/encyclopedia documentation enrichment |
| Concept | Objects mapped to ≥1 CN-* |
| Boundary | Objects with owner BD-* |
| Journey | Objects on ≥1 JN step |
| Contract | Objects under CT / config-contract heuristics (migrate to CT-*) |
| Evidence | Findings / tests / framework links |
| Authority | Boundary / regime / relevance posture (not production authority) |
| Dependency | AST import edges present |
| Attribution | owner_surface ≠ UNATTRIBUTED |
| **Behavior** (**add**) | Executable journeys fully expandable to objects with concept+boundary |

### Behavior Coverage (new dimension)

```text
Behavior Coverage =
  | journey steps that resolve to (concept ∧ boundary ∧ ≥1 object) |
  / | journey steps declared in ACTIVE journeys |
```

Optional stricter form: every RUNTIME journey terminal outcome has a test or finding evidence edge.

**Physical/book GREEN does not imply Behavior Coverage GREEN.**

Regenerate: `python scripts/governance/coverage_dashboard.py`

---

## 8. Authority and precedence (invariants)

| Rank | Authority | Semantic OS may |
|---|---|---|
| 0 | Runtime code + ACTIVE_VERSION config | Only **describe** |
| 1 | Market ontology (meaning of market math) | Cite FM/SEM only |
| 2 | Findings / sealed evidence | Join as L4 |
| 3 | Semantic OS (CN/BD/JN/CT) | Navigate, explain, impact-draft |
| 4 | Book / Encyclopedia | Document |

- Semantic OS **never** overrides code.  
- Book **never** overrides code.  
- Every CN/BD/JN/CT claim is **traceable** to implementation and/or finding.  
- `authority: "advisory"` pinned on all Semantic OS records (§6.5).  
- Production authority remains: measured G001 + promotion path only.

---

## 9. Current state vs target

| Item | Now (skeleton) | v1 target |
|---|---|---|
| Concepts | ~2 (CN-001, CN-002) | ~40–60 ACTIVE covering spine + research families |
| Boundaries | 2 (BD-001, BD-002) | ~30–40 seams; spine 100% claimed; single ownership |
| Journeys | JN-001 (2 steps) | Full candle journey (7 steps) + research + promotion + agent |
| Contracts | Inline in BD | CT-* first-class + BD references |
| Objects | GENERATED ~849 | GENERATED; denominator always disk |
| owner_surface | 100% UNATTRIBUTED | Overlays for DECISION_SPINE + key surfaces |
| semantic_impact | Missing file | Implemented blast-radius + draft manifest |
| Coverage verdict | NOT_YET | Still may be NOT_YET until inventories grow — honest |

### Explicit unknowns (do not paper over)

1. Concept inventory incomplete  
2. Boundary inventory incomplete  
3. Journey inventory incomplete  
4. Owner attribution incomplete  
5. Behavior coverage incomplete  
6. Repository semantic coverage incomplete  
7. Object denominator still evolves with the tree  

---

## 10. Seed concept inventory (target set — Phase 3 fill)

Not all exist yet; this is the **ordered growth list** for humans to author (meaning only).

### Market & structure
CN-004 CRT Market Structure **(exists PR-3)** · CN-008 Session and Broker Clock **(exists PR-4)** · CN-SweepDisplacementRetest · CN-VolatilityRegime  

### Numeric surface
CN-001 Canonical Feature Vector **(exists)** · CN-007 Market Ontology Authority **(exists PR-4)** · CN-015 No-Lookahead Integrity **(exists PR-4)** · CN-FormulaRegistry (fold into CN-007) · CN-PITContract (fold into CN-015)  

### Decision & risk
CN-002 Trade Approval **(exists)** · CN-005 Four Engine Scoring **(exists PR-3)** · CN-006 Fusion Decision and Geometry **(exists PR-3)** · CN-UltronCapitalGate (alias of CN-002)  

### Runtime
CN-003 Candle Ingest **(exists PR-3)** · CN-009 Config-First Active Version **(exists PR-4)** · CN-BacktestReplay · CN-LiveTickPath  

### Research
CN-011 Research Falsification Gate **(exists PR-4)** · CN-MeasurementContract · CN-ProgramFamily  

### Governance
CN-010 Promotion Gate **(exists PR-4)** · CN-012 Findings and Epistemic Integrity **(exists PR-4)** · CN-AuthorityLadder · CN-ConstructionProtocol  

### Agent / ops
CN-013 Deterministic Agent Plans **(exists PR-4)** · CN-014 Control Plane Catalog **(exists PR-4)** · CN-MultiLLMCoordination  

### Sidecar / dormant (explicit concepts so “dormant” is semantic, not forgotten)
CN-SidecarNonSpine · CN-DormantMultiStrategy  

**PR-4 inventory (2026-08-08):** CN-001..CN-015 ACTIVE. Journey membership still only JN-001 (CN-001..006); CN-007..015 carry `orphan_justification` where not on a journey step.

**PR-5 inventory (2026-08-08):** 10 ACTIVE boundaries (BD-001..BD-010; IDs not renumbered — BD-002 narrowed to Capital Risk Gate). Member globs claim ~94 files (was 11); all 11 `SPINE_FILES` still claimed. JN-001 steps rewired to refined BDs. Contracts CT-001..CT-007. `graph.dot` regenerated so strict graph-staleness stays green.

Each new CN must include: why, non-goals, invariants, pre/postconditions, assumptions with HOLDS/FALSIFIED, owner_boundary, evidence FKs, failure_modes (for journeys).

---

## 11. Seed journey inventory (target)

| Id | Kind | Scope |
|---|---|---|
| JN-001 | RUNTIME | One candle → order (expand to Steps 1–7 + kitchen feeders) |
| JN-002 | RESEARCH | Pre-register → run → gate → finding |
| JN-003 | GOVERNANCE | Config change → validate → promote / reject |
| JN-004 | CONFIG | ACTIVE_VERSION load → CRTConfig resolution (include F-057 failure) |
| JN-005 | AGENT | NL intent → PLAN_REGISTRY → tools → audit |
| JN-006 | RUNTIME | Live tick only (HookedLiveEngine) vs backtest delta |

---

## 12. Architecture of software components

```text
docs/governance/semantic_os/
  concepts.yaml      (PRIMARY hand)
  boundaries.yaml    (PRIMARY hand)
  journeys.yaml      (PRIMARY hand)
  contracts.yaml     (PRIMARY hand — NEW)

src/governance/
  semantic_os.py         # validate CN/BD/JN/CT, registry load
  semantic_objects.py    # GENERATED OBJ universe + joins
  semantic_query.py      # L5 ask interface
  semantic_impact.py     # L6 blast radius + draft manifest (complete)
  module_attribution.py  # overlays for owner_surface

scripts/governance/
  seed_semantic_os.py           # YAML → data/semantic_os/*.jsonl
  coverage_dashboard.py         # multi-dimension scoreboard
  build_encyclopedia_jsonl.py   # doc twin (not semantic denominator)

data/semantic_os/               # GENERATED, gitignored projection
docs/governance/REPOSITORY_COVERAGE_DASHBOARD.md  # GENERATED scores
```

### Validation rules (extend existing 14)

1. No hand-authored derived fields on CN/BD/JN/CT.  
2. Every BD.members glob matches ≥1 file; no dual ownership.  
3. Every JN step.concept exists; failure_mode ∈ concept.failure_modes.  
4. Every JN step.boundary exists.  
5. CT tests paths resolve when claimed.  
6. FK to F-*, FM-*, MIAR, closure surfaces validate or UNKNOWN.  
7. Spine modules remain boundary-covered (monotonic floor).  
8. `authority` never `production`.  
9. Append-only retire (SUPERSEDED/RETIRED).  
10. Object denominator = `discover_universe()`, never encyclopedia row count.

---

## 13. Phased delivery (implementation plan)

| Phase | Deliverable | Coverage effect |
|---|---|---|
| **A — Contract freeze** | This design + SEMANTIC_OS_CONTRACT.md + CT schema stub | Align team language |
| **B — Entity complete skeleton** | contracts.yaml + CT validation; expand JN-001 to 7 steps | Journey RED → YELLOW |
| **C — Concept inventory** | ~25 spine CN + research CN | Semantic RED → YELLOW |
| **D — Boundary refinement** | ~20 BDs; spine 100%; package globs | Boundary RED → YELLOW |
| **E — Attribution overlays** | owner_surface for DECISION_SPINE + FEATURE + GOVERNANCE | Attribution 0% → partial |
| **F — Impact engine** | semantic_impact.py + query “what breaks” | Implementation completeness |
| **G — Behavior coverage** | Dashboard dimension + tests | New score visible |
| **H — Continuous seed** | GREEN_FLOOR: seed --check + dashboard thresholds | Prevents silent decay |

No phase rewrites CRT math or production fusion without separate BEHAVIOR_CHANGE_AUTHORIZED work.

---

## 14. Key decisions

| # | Decision | Rationale |
|---|---|---|
| K1 | FM-first stack, not code-first | Matches LLM reasoning; reduces semantic entropy |
| K2 | Five entities only (CN/BD/JN/CT/OBJ) | Avoid duplicate graphs as ontologies |
| K3 | OBJ 100% generated from disk | Stale encyclopedia cannot be denominator |
| K4 | CT first-class (not only inline BD contracts) | Contracts constrain multiple boundaries; measurable |
| K5 | CRT = structural language, not strategy | One narrative, many consumers |
| K6 | Structural config ≠ consumer config | Prevents interpretation forks |
| K7 | Advisory authority forever unless G001 | §6.5 ladder |
| K8 | Fail closed on unknowns | Epistemic integrity |
| K9 | Coverage measures understanding | Stops “docs done ⇒ covered” overclaim |
| K10 | Behavior Coverage is first-class dimension | Executable journeys must be explainable |

---

## 15. Alternatives considered

| Alternative | Why rejected |
|---|---|
| Expand encyclopedia only | Improves documentation, not semantic joins |
| Code-comments-as-ontology | Not queryable; no FKs; high entropy |
| Full knowledge graph product | Over-architecture; views over five entities suffice |
| Make Semantic OS production gate | Violates §6.5 without G001 proof |
| Migrate all CRT thresholds to YAML immediately | Blind migration; classify semantics vs mechanics first |

---

## 16. Success criteria

The Semantic OS v1 is successful when:

1. An LLM (or human) can answer the eight questions in §6 for any spine OBJ without opening random folders first.  
2. Coverage Dashboard reports **Concept / Boundary / Journey / Behavior** with clear numerators and disk denominators.  
3. Changing a concept’s invariant surfaces impacted journeys and objects via impact view.  
4. No hand-authored derived field can pass validation.  
5. CRT structure remains one language across fusion, research, execution, and analytics.  
6. Documentation systems remain maps; Semantic OS remains meaning; code remains authority.

**Not success:** more markdown files without CN/BD/JN/CT growth or dashboard movement.

---

## 17. Open questions (for owner)

1. **CT storage:** **RESOLVED PR-2** — `contracts.yaml` shipped with CT-001/CT-002; BD keeps inline `contract:` + `contract_ids` dual form for migration.  
2. **Attribution target:** is `owner_surface` worth overlay investment, or is `owner_boundary` sufficient permanently?  
3. **Behavior Coverage strictness:** step-resolve-only vs require test/finding evidence per step?  
4. **Universe default for dashboard:** `code` (src+scripts) vs `all` (+tests)?  

---

## 18. PR Plan

| PR | Title | Scope | Depends |
|---|---|---|---|
| **PR-1** | Semantic OS v1 design + contract | This doc + `SEMANTIC_OS_CONTRACT.md` + dashboard Behavior dim + doc pointers | — |
| **PR-2** | CT schema + contracts.yaml skeleton + validators | `semantic_os.py` KIND_ENUM, tests | PR-1 · **SHIPPED 2026-08-08** |
| **PR-3** | Expand JN-001 to full candle journey (7 steps) | journeys.yaml + CN-003..006 | PR-1 · **SHIPPED 2026-08-08** |
| **PR-4** | Concept inventory wave 1 (spine ~15 CN) | concepts.yaml | PR-1 · **SHIPPED 2026-08-08** |
| **PR-5** | Boundary refinement wave 1 (~10 BD) | boundaries.yaml; keep spine floor | PR-4 · **SHIPPED 2026-08-08** |
| **PR-6** | Attribution overlays for DECISION_SPINE + FEATURE | module_attribution overlays | PR-5 |
| **PR-7** | semantic_impact.py + query “what breaks” | L6 impact | PR-2 |
| **PR-8** | Behavior coverage + GREEN_FLOOR hooks | coverage_dashboard + tests | PR-3 |

Each PR: advisory only; no production behavior change; regenerate dashboard; SESSION LOG.

---

## 19. Related artifacts

| Path | Role |
|---|---|
| `docs/governance/semantic_os/*.yaml` | PRIMARY hand registries |
| `src/governance/semantic_os.py` | Hand registry validation |
| `src/governance/semantic_objects.py` | GENERATED objects + base coverage_report |
| `src/governance/semantic_query.py` | L5 query |
| `scripts/governance/seed_semantic_os.py` | Seed projection |
| `scripts/governance/coverage_dashboard.py` | Scoreboard |
| `docs/book/` + encyclopedia | Documentation layer |
| `configs/formulas/market_ontology.yaml` | Market meaning #1 |
| `docs/architecture/signal-flow.md` | Journey prose source |

---

_End of Semantic OS v1 design. Implementation follows PR Plan; code remains supreme on conflict._
