# Design — Vision Semantic Observation Layer (schema only)

> **Status:** DESIGN ONLY. No code, no runtime change, no promotion. Authority: research/docs only
> (CLAUDE.md §6.5). Nothing here grants fusion, sizing, or production authority, and no schema
> below is wired to a decision path.
>
> **Scope:** the record shapes and controls for comparing what the production CRT engine *says*
> about a bar against what a vision model *observes* in a TradingView screenshot of the same bar,
> on XAUUSD. Written 2026-08-31 (CH-vision-semantic-observation-design-v1).

---

## 0. Source grounding — every named concept verified

Requested explicitly: link the design to real sources rather than asserted ones. Every row below
was verified against the repository this session; nothing is cited from memory.

| Concept named in the proposal | Verified source | Status |
|---|---|---|
| `crt_parity_sweep.py` | `scripts/research/crt_parity_sweep.py` (633 lines) | EXISTS |
| `crt_state_confusion_matrix.py` | `scripts/research/crt_state_confusion_matrix.py` (1,221) | EXISTS |
| `crt_state_window_trace.py` | `scripts/research/crt_state_window_trace.py` (346) | EXISTS |
| `crt_resolver_economic_comparison.py` | `scripts/research/crt_resolver_economic_comparison.py` (807) | EXISTS |
| Semantic layers L0–L6 | `docs/governance/SEMANTIC_OS_CONTRACT.md:62-68` | EXISTS — **and already bound** (see §2) |
| Semantic OS artifacts | `docs/governance/semantic_os/{boundaries,concepts,contracts,file_identities,journeys}.yaml` | EXISTS (5 files) |
| Grounding kinds | `src/governance/semantic_grounding.py` — NOUN / RELATIONSHIP / IMPLEMENTATION / EVIDENCE / JSONL | EXISTS |
| TradingView capture | `tools/tv_forensic/` — 16 modules, `capture_tv.py` (756 lines) | EXISTS |
| Captured shots | `tools/tv_forensic/shots/` — **61** sidecar JSONs | EXISTS |
| Per-bar pixel alignment | sidecar `bars[]` keys `{i,t,o,h,l,c,x}`; `plot` price→y calibration | EXISTS |
| Engine↔TV OHLC fidelity | sidecar `engine_vs_tv`; F-080 (2,253 bars, 30 divergent, all at one day-open slot) | EXISTS |
| Blind labelling pre-registration | `docs/research/preregistration-blind-label-descriptive-fidelity.md` | EXISTS |
| Blind label sampler | `scripts/analysis/blind_label_sample.py` (stratified, greedy-spaced, SVG render) | EXISTS |
| Blind label scorer | `scripts/analysis/blind_label_score.py` — `sklearn cohen_kappa_score`, Arms A/B/C | EXISTS |
| F-069 parity baseline | `reports/crt_semantic_parity_report.md`; ledger `results/analysis/crt_parity_sweep/` | EXISTS |

**Conclusion of the grounding pass: the proposal names nothing that does not exist, but it also
proposes building several things that already exist.** See §3.

---

## 1. Measured corrections to the proposal

Recomputed from the raw confusion matrix (`results/analysis/crt_parity_sweep/iters/iter_0001.json`),
not restated from the summary.

| Claim | Measured | Verdict |
|---|---|---|
| Total mismatch 5,590 | 5,590 (47,197 − 41,607) | **correct** |
| EXPANSION-related = 5,223 = 93.4% | **5,432 = 97.2%** | direction right, number off |
| "start with EXPANSION, RETEST" | RETEST-involved mismatches = **17 (0.3%)** | **RETEST is the wrong second target** |
| SWEEP ≈ solved (96.40%) | 96.40% recall | **correct** |
| Engine EXPANSION 4,625 / Resolver 1,803 | confirmed | **correct** |

**C1 — RETEST is statistically empty, not a priority.** Engine RETEST `n=17` on a 47,197-bar
corpus. "0.00% recall" is 0-of-17. It contributes **17 of 5,590** disagreements. Prioritising it
alongside EXPANSION misallocates the whole program.

**C2 — EXPANSION divergence is BIDIRECTIONAL, which is the real finding.** The top mismatch cells:

| engine → resolver | count | share of all disagreement |
|---|---|---|
| `EXPANSION → RANGE` | **3,335** | 59.7% (resolver **under**-fires) |
| `RANGE → EXPANSION` | **1,052** | 18.8% (resolver **over**-fires) |
| `EXPANSION → SWEEP` | 735 | 13.1% |
| `SWEEP → EXPANSION` | 242 | 4.3% |

A mistuned threshold moves error in **one** direction. Simultaneous 3,335 under-fire *and* 1,052
over-fire is the signature of a **different construction**, which is exactly F-069's Category-C
(96.1%) verdict, now visible in the cell decomposition rather than only in the headline.

**C3 — do not redefine L1–L6.** The proposal re-maps them (`L1 Market Ontology`, `L2 Construction`,
`L6 Runtime`). Those labels are already bound and mechanically enforced:

```
L0 Identity   kind labels        L4 Evidence        findings/tests/research joins
L1 Concept    CN-*               L5 Governance      authority doctrine joins
L2 Behavior   JN-*               L6 Implementation  OBJ-*
L3 Relationships  BD-*, CT-*
```

Redefining them collides with `semantic_grounding.py` and every `CN-*`/`JN-*`/`OBJ-*` id in the
Semantic OS. **The vision program slots into these layers; it does not renumber them.**

---

## 2. Where this program sits in the existing layers

| Layer | Existing meaning | What the vision program contributes |
|---|---|---|
| L0 Identity | kind labels | new kind: `VisionObservation` |
| L1 Concept | `CN-*` | reuses existing CRT concepts; mints **no** new market concept |
| L2 Behavior | `JN-*` | one new journey: screenshot → observation → comparison |
| L3 Relationships | `BD-*`, `CT-*` | one boundary: vision layer may **read** engine output, never write to it |
| L4 Evidence | findings/tests | the agreement matrix + κ report land here |
| L5 Governance | authority doctrine | observation-only; no ΔG001; cannot promote |
| L6 Implementation | `OBJ-*` | the adapter/comparator objects, when built |

---

## 3. Reuse map — what NOT to build

The proposal's build list is largely already in the repo. Building it again would repeat the exact
mistake it warns against ("do not build a second interpreter").

| Proposal step | Already exists | Reuse |
|---|---|---|
| "Generate screenshots" | `tools/tv_forensic/capture_tv.py`, 61 sidecars | reuse wholesale |
| Bar↔pixel alignment | sidecar `bars[].x`, `plot` price→y | reuse; **do not re-derive** |
| Clock handling | `capture_tv.py` measured broker↔UTC offset per run | reuse; **never hand-convert** |
| Engine↔TV OHLC fidelity | F-080, sidecar `engine_vs_tv` | already answered; not re-opened |
| "Engine labels every bar" | `crt_state_confusion_matrix.prepare_engine_context` | reuse |
| Sampling design | `blind_label_sample.py` — stratified, greedy-spaced | reuse |
| Scoring | `blind_label_score.py` — Cohen's κ, Arms A/B/C | reuse |
| Pre-registration form | `preregistration-blind-label-descriptive-fidelity.md` | reuse as template |

> **The single most important structural observation of this design:** the vision program is not a
> new experiment. It is `blind_label` **with the human labeler replaced by a vision model**. Every
> control that program already froze (blind labels, chance-correction, per-stratum conditional κ,
> intra-rater repeats) applies unchanged, and inherits its authority ceiling with them.

---

## 4. The schema

Four record types. All append-only JSONL, all research-tier, none read by any decision path.

### 4.1 `SemanticTrace` — what the engine said (one row per bar)

Derived from the production engine; **no new computation**.

```yaml
schema: vision/semantic_trace/v1
instrument: XAUUSD
timeframe: M15
bar_index:        int          # engine-aligned index
timestamp:        str          # broker-local, basis recorded (F-066)
timestamp_basis:  broker_local | utc_corrected
crt_state:        RANGE | SHADOW_PENDING | SWEEP | DISPLACEMENT | EXPANSION | EXPIRED | RETEST | EXECUTION | RESOLUTION
prev_state:       <same enum>
parent_state:     RANGE_C1 | MANIPULATION_C2 | DISTRIBUTION_C3 | null
objective_status: <HTFState vocabulary> | null
transition_fired: str | null   # e.g. try_sweep_to_displacement
guard_rejected:   str | null   # e.g. G_SWEEP_DISP_DIR_NONE
provenance:
  config_version: str          # ACTIVE_VERSION at generation
  engine_run_id:  str
  corpus_sha256:  str
```

### 4.2 `VisionObservation` — what the model saw (one row per screenshot)

**Structures only. No state names, no prices, no direction.** The vocabulary is deliberately
*not* the CRT state enum — asking the model for `EXPANSION` would invite it to guess the label
rather than describe the chart, and would make agreement uninterpretable.

```yaml
schema: vision/observation/v1
shot_id:        str            # joins tools/tv_forensic/shots/<id>.json
model:          str            # e.g. claude-opus-5
prompt_version: str            # frozen prompt id; changing it forks the experiment
replicate:      int            # 1..N — same shot, repeated (Arm C, see 5.3)
observed_structures:           # closed vocabulary, ordered as seen left→right
  - kind: consolidation | impulse_leg | wick_rejection | retrace | continuation_leg | liquidity_pool | gap
    span_bars: [int, int]      # inclusive bar indices, resolved via sidecar bars[].x
    confidence: high | medium | low
notes_free_text: str           # NOT scored; captured for discovery only (see 6.3)
abstained:      bool           # true if the model declined — an abstention is data, not a failure
```

### 4.3 `AgreementRecord` — the join (one row per bar × replicate)

```yaml
schema: vision/agreement/v1
bar_index:       int
shot_id:         str
replicate:       int
engine_state:    <crt state>           # from 4.1
vision_structures: [<kind>, ...]       # from 4.2
mapped_expectation: <crt state> | null # via the frozen map in 5.2 — NOT model output
agreement:       true | false | unmappable
disagreement_class:                    # only when agreement=false
  under_fire | over_fire | wrong_kind | boundary_offset | ambiguous
```

### 4.4 `AgreementReport` — the scored artifact

```yaml
schema: vision/agreement_report/v1
arm_a_population:  {n, kappa, raw_agreement_pct, status}
arm_b_per_stratum: {<stratum>: {n, kappa, status}}   # conditional; NEVER blended
arm_c_intra_model: {n, kappa, status}                # replicate-vs-replicate
confusion_matrix:  {"<engine>|<mapped>": count}
prereg_ref:        docs/research/preregistration-<id>.md
authority:         OBSERVATION_ONLY
```

---

## 5. Controls — the parts that decide whether this is evidence or theatre

### 5.1 Blind annotation is mandatory

The model must **never** see the engine's label, the state vocabulary, or a prior annotation of the
same shot before producing `VisionObservation`. Without this the comparison measures compliance,
not observation. This is the discipline `preregistration-blind-label-descriptive-fidelity.md`
already froze for the human arm; it carries over unchanged.

### 5.2 The structure→state map is frozen *before* any annotation

`mapped_expectation` is produced by a **pre-registered, hand-authored** map from observed
structures to the CRT state they would imply. Freezing it before annotation is what prevents
post-hoc threshold-shopping. The model never sees this map, and never emits a state directly.

### 5.3 Cohen's κ, never raw agreement

Non-negotiable, and the proposal omits it. Engine RANGE is **35,130 / 47,197 = 74.4%** of bars, so
a labeler that answers "consolidation" every time scores ~74% raw agreement while carrying zero
information. `blind_label_score.py` already computes chance-corrected κ with Arms A/B/C — reuse it
exactly, including its rule that **per-stratum κ is never blended into a marginal**.

Arm C (intra-rater) matters more here than for a human: a vision model is **nondeterministic**, so
its self-agreement across replicates is the ceiling on any engine-agreement number it can produce.
**Report Arm C first** — if the model cannot agree with itself, its disagreement with the engine is
uninterpretable.

### 5.4 Sampling must be stratified on the disagreement, not on time

Per §1, EXPANSION carries 97.2% of engine↔resolver divergence. Strata:

| Stratum | Why |
|---|---|
| `EXPANSION` (engine) | the dominant disagreement surface |
| `EXPANSION→RANGE` cells | the 3,335 under-fire population |
| `RANGE→EXPANSION` cells | the 1,052 over-fire population |
| `SWEEP` / `DISPLACEMENT` | high-recall controls — if the model disagrees *here*, the instrument is broken |
| `RANGE` (majority) | base-rate anchor for κ |

Reuse `blind_label_sample._greedy_spaced_sample` so adjacent, autocorrelated bars are not sampled
as if independent.

### 5.5 Scope limits, stated up front

- Descriptive fidelity **only**. Not predictive, not economic. Cannot revise F-019…F-097.
- Cannot re-open F-080 (engine↔TV OHLC fidelity is already settled and is a *different* question).
- Cannot promote anything, adjust any threshold, or enter a decision path.
- One month of XAUUSD M15 ≈ 2,100 bars ≈ **~4 executions** at the measured base rate. Any
  EXECUTION/RETEST-conditioned claim is unpowered by construction and must be declared so, not
  discovered later.

---

## 6. What the model is and is not asked

### 6.1 Never ask for (the engine is authoritative and the model is weak here)
OHLC values · ATR · displacement magnitude · state names · transition decisions · direction ·
anything predictive.

### 6.2 Ask for (the engine cannot do this)
Which visual structures are present, in what left-to-right order, over which bar span.

### 6.3 Discovery channel — quarantined
`notes_free_text` captures recurring motifs the closed vocabulary cannot express. It is **never
scored** and **never** enters an agreement number. Its only legal output is a *candidate
hypothesis*, which must then go through the normal route (hypothesis → contract → experiment →
evidence) before it means anything. This keeps the discovery upside without letting free text leak
into a measured result.

---

## 7. Sequencing

| Step | Output | Gate |
|---|---|---|
| 1 | Pre-registration doc (questions, strata, frozen structure→state map, predictions) | written **before** any annotation |
| 2 | `SemanticTrace` for the 1-month XAUUSD window | reuses engine context; no new math |
| 3 | Shot plan over the §5.4 strata | reuses `capture_tv.py`; broker-time trap respected |
| 4 | `VisionObservation` × N replicates, blind | Arm C computed **first** |
| 5 | `AgreementRecord` join via the frozen map | κ per Arms A/B |
| 6 | `AgreementReport` | registered as evidence only if the pre-registration's own gate is met |

**Stop rule:** if Arm C (model self-agreement) is below the pre-registered floor, the program halts
at step 4 and reports that — no engine-agreement number is computed from an instrument that cannot
reproduce itself.

---

## 8. Relationship to the CRT V3 question

This program does **not** advance the resolver→engine construction gap, and must not be described
as doing so. F-069's 11.84% residual is a question about *engine construction geometry* (887 lines
across 8 `try_*` methods). A vision agreement matrix measures whether the engine's **labels**
describe what is visibly on the chart — a different axis.

Both are worth knowing; conflating them would be the same category error the proposal correctly
warns about elsewhere.
