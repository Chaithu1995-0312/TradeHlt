# Opportunity Episode Research Substrate

> **Status:** Architecture audit + pre-freeze design (consolidated). **No code authority.**  
> **Date:** 2026-07-22 → 2026-07-23  
> **Branch context:** research design only; production spine unchanged.  
> **Authority:** NONE (§6.5 Authority Ladder) — infrastructure design for research; grants no promotion, fusion, or live-wiring rights.  
> **Siblings:**  
> - [`opportunity-episode-platform-design.md`](opportunity-episode-platform-design.md) — earlier design freeze draft (rev 2)  
> - [`envelope-layer-design.md`](envelope-layer-design.md) — post-entry operating envelope  
> - [`model-design-intent.md`](model-design-intent.md) — missing-stage context  
> - [`signal-flow.md`](signal-flow.md) — candle→order spine  
> - Governing exit kernel: `src/research/measurement/forward_walk.py`  
> - Clean-label protocol: `src/research/clean_labels/protocol.py`  
> - Path-tensor precedent: `src/research/ic002_entry_evolution/`  
> - Finding **F-022**: `opportunities.jsonl` is a detection stream, not a trade ledger  

This document transports the full multi-round architecture analysis:

1. **Round 1** — Forward-path audit (codebase reconstruction)  
2. **Round 2** — Elevate “forward path” → episode abstraction  
3. **Round 3** — Pre-freeze adjustments (policy-independent timeline, derived events, query layer, offline projector, broader noun)

**Implementation status:** design only. Do not implement without Phase-0 contract freeze + construction protocol.

---

## Table of contents

1. [Problem statement](#1-problem-statement)  
2. [Root abstraction (final)](#2-root-abstraction-final)  
3. [Data-flow reconstruction (current codebase)](#3-data-flow-reconstruction-current-codebase)  
4. [Opportunity lifecycle (current)](#4-opportunity-lifecycle-current)  
5. [Forward-walk ownership (current)](#5-forward-walk-ownership-current)  
6. [Data structures (current)](#6-data-structures-current)  
7. [Feature pipeline impact](#7-feature-pipeline-impact)  
8. [Proposed substrate architecture](#8-proposed-substrate-architecture)  
9. [EpisodeStep layers (Observation / Derived / Annotations)](#9-episodestep-layers)  
10. [Policy independence](#10-policy-independence)  
11. [Events as derived artifacts](#11-events-as-derived-artifacts)  
12. [Provenance](#12-provenance)  
13. [Storage triad](#13-storage-triad)  
14. [Episode Query Engine](#14-episode-query-engine)  
15. [Production isolation (Projector only)](#15-production-isolation-projector-only)  
16. [Research impact (unified consumers)](#16-research-impact-unified-consumers)  
17. [Backward compatibility](#17-backward-compatibility)  
18. [Risks](#18-risks)  
19. [Component impact matrix](#19-component-impact-matrix)  
20. [Files / modules](#20-files--modules)  
21. [Migration roadmap](#21-migration-roadmap)  
22. [Complexity estimates](#22-complexity-estimates)  
23. [Open decisions (pre-freeze)](#23-open-decisions-pre-freeze)  
24. [Non-goals](#24-non-goals)  
25. [Evolution of this audit](#25-evolution-of-this-audit)  
26. [Diagrams](#26-diagrams)

---

## 1. Problem statement

### Current behaviour

Research and training pipelines generally produce **entry + compressed outcome**:

| Field class | Examples |
|-------------|---------|
| Entry | timestamp, price, direction, SL/TP, features@entry |
| Decision | CRT path / scanner dual direction / hypothesis meta |
| Terminal | outcome, exit_reason, rr_achieved, duration |
| Summary path | scalar MFE, MAE, optional time_to_*R |
| Training y | Bernoulli / continuous labels derived from the above |

**The post-entry market evolution is walked then discarded.** Multiple independent walkers re-simulate the same bars and keep only scalars.

### Desired behaviour

A durable **research substrate** that:

1. Preserves (or can always regenerate) the full post-entry **observation timeline**.  
2. Supports **many exit policies, event taxonomies, and models** without rebuilding timelines.  
3. Feeds TradeNet, RR, exit intelligence, replay, RL, and sequence models from **one** store.  
4. Leaves **production runtime** byte-behaviour and latency unchanged.

### What this is *not*

- Not a new live trading object.  
- Not a replacement for `TradeRecord` / journal CSV.  
- Not nested bloat inside `opportunities.jsonl` (F-022).  
- Not authority to re-enable rr_fusion / BitNet / TradeNet in production.

---

## 2. Root abstraction (final)

### Name

| Term | Role |
|------|------|
| **OpportunityEpisode** | Preferred root type |
| MarketEpisode | Optional alias for non-trade structural populations |
| TradeEpisode | **Not** the root noun; may appear as `population=SPINE_TRADE` |

An episode is a **bounded opportunity window with a frozen entry decision context** — not “a filled trade.” Only some episodes execute.

### Populations

```text
population ∈ {
  DETECTION_STREAM,     # opportunity_scanner long/short per bar
  HYPOTHESIS_SIGNAL,    # research.contracts.Signal from Hypothesis.detect
  SPINE_TRADE,          # CRT TRADE_OPENED → accepted ledger trade
  SPINE_REJECTED,       # optional: rejected candidates
  STRUCTURAL_EVENT,     # sweep / BOS / liquidity / regime window
  CUSTOM
}
```

### Conceptual model (canonical vs derived)

```text
OpportunityEpisode                          ← CANONICAL (immutable)
├── episode_id / population / instrument / timeframe
├── entry_snapshot                          ← frozen at decision
├── timeline: EpisodeStep[]                 ← observations (+ optional caches)
└── provenance                              ← multi-hash reproducibility

── derived artifacts (versioned, regenerable) ──
LabelSet        ← PolicyEvaluator(policy_P)
EventSet        ← EventEngine(rulepack_K)
AnnotationSet   ← Annotator / models
Flat step table ← projection for SQL/pandas
Tensors [N,T,D] ← training materializers only
```

**Forward path** is a *view* of the timeline under a chosen geometry/policy — not the system of record.

---

## 3. Data-flow reconstruction (current codebase)

There are **three** relevant pipelines. They must not be conflated (F-022, F-037).

### Pipeline A — CRT spine (accepted trades)

```text
OHLCV CSV (data/*)
  → CandleLoader.stream()                 [L1/L2 integrity; L3 only some entry points]
  → FeaturePipeline.run()                 [batch vectors; schema v4 ≈ 39-dim]
  → CRTEngine.process_candle()
  → (optional) EngineRunner fusion        [BACKTEST_ENGINE_GATE]
  → TRADE_OPENED
  → TradeJournal.on_trade_opened()        [entry freeze + entry features]
  → per-bar: observe_open_bar()           [running MFE/MAE scalars only]
  → engine exits (TP1/TP2/SL/TTL/GAP + partial TP config)
  → on_trade_closed()                     [exit_reason, RR, TradePathStats]
  → *_trades.csv + summary JSON
```

**Key files:** `src/runtime/backtest_v2.py`, `src/config_layer/crt_engine_v2.py`, `src/features/feature_pipeline.py`.

### Pipeline B — Unbiased detection stream (training substrate)

```text
OHLCV
  → FeaturePipeline.run()
  → opportunity_scanner: every bar × {long, short}
  → legacy _simulate (trailing stop)      [NOT governing exit]
  → logs/{inst}/{run_id}/opportunities.jsonl
       {entry, sl, tp, outcome, rr, mfe, mae, features@entry}
  → stage1_dataset_builder / phase5_calibration / zone & RR training
```

**Key files:** `scripts/research/opportunity_scanner.py`, `src/training/stage1_dataset_builder.py`.

**F-022:** stream `outcome`/`rr`/`mfe`/`mae` are **not** reliable realized-trade truth (~36.8% self-consistency historically). Frequency illusion: detections ≫ spine trades.

### Pipeline C — Governing research measurement

```text
OHLCV → CandleLoader
  → Hypothesis.detect() OR geometry from opportunities
  → research.measurement.forward_walk(exit_model=intrabar_fixed)   [GOVERNING]
  → Outcome scalars (+ optional horizon_excursion)
  → EdgeReport / clean_labels / forensics / exit_grid
```

**Key files:**  
`src/research/measurement/forward_walk.py`,  
`src/research/contracts.py` (`Signal`, `Outcome`),  
`src/research/runner.py`,  
`src/research/clean_labels/builder.py`,  
`src/research/forensics.py`,  
`src/research/exit_grid.py`.

### Stage list (today)

| # | Stage | Owner | Output today |
|---|--------|-------|--------------|
| 1 | Candles | `CandleLoader`, `ohlcv_schema` | `Candle` stream |
| 2 | Features | `FeaturePipeline` | full-series matrix in memory |
| 3 | Opportunity gen | scanner / CRT / Hypothesis | rows or trades |
| 4 | Entry freeze | scanner record / `on_trade_opened` | geometry + features@t0 |
| 5 | Exit simulation | `_simulate` / CRT / `forward_walk` | compressed outcome |
| 6 | Labels | clean_labels, rr_dataset_builder, TradeNet extract | scalar y |
| 7 | Artifacts | stage1, train_pipeline, phase5 | JSONL / models |
| 8 | Path summaries | `TradePathStats`, `horizon_excursion`, IC-002 | scalars or 15×N tensors |

**Missing durable stage:** canonical observation timeline + versioned derivation layers.

### Closest existing precedents

| Precedent | Location | What it preserves |
|-----------|----------|-------------------|
| IC-002 trajectories | `src/research/ic002_entry_evolution/` | Path-relative **15** features × N bars as npz (`Z[n,N,D]`) |
| Clean labels | `src/research/clean_labels/` | Re-walk with `intrabar_fixed`; primary y from path, stream diagnostic only |
| TradePathStats | `backtest_v2.TradePathStats` | Within-trade MFE/MAE scalars (observation-only) |
| timing_reconstructor | `src/replay/timing_reconstructor.py` | Additive time_to_*R on legacy simulate |
| structural_asymmetry | `PathMeasure` | Multi-horizon MFE/MAE dicts (still compressed) |

IC-002 is the template for **tensor materialization**, not for canonical episode storage.

---

## 4. Opportunity lifecycle (current)

| Event | Where | What is kept |
|-------|--------|--------------|
| Opportunity created | scanner / `TRADE_OPENED` / `Hypothesis.detect` | Identity + geometry |
| Entry frozen | scanner row; `TradeJournal.on_trade_opened` | price, SL/TP, direction, features@t0 |
| Exits simulated | `_simulate` (trailing); CRT hot-loop; `forward_walk` | Terminal scalars |
| Labels assigned | stream fields (B, contaminated); clean_labels re-walk (C) | y_* |
| MFE/MAE | running max/min inside walkers | final scalars only |
| RR | price move / risk at exit | `rr_achieved`, `pnl_rr_net`, `y_R_net` |

Path state exists **inside** the walk loop and is **thrown away** on return.

---

## 5. Forward-walk ownership (current)

| Responsibility | Module | Notes |
|----------------|--------|-------|
| Governing walk | `research.measurement.forward_walk` | `intrabar_fixed` = truth; SL-before-TP; no-lookahead |
| OCO / straddle | `forward_walk_oco` | Delegates post-fill to `forward_walk` |
| Exit-agnostic envelope | `horizon_excursion` | Full-horizon MFE/MAE; never exits |
| Legacy scanner | `opportunity_scanner._simulate` | Trailing model |
| Timing additive | `timing_reconstructor.simulate_with_timing` | Still compresses |
| Spine path obs | `TradeJournal.observe_open_bar` | MFE/MAE only |
| Spine exits | CRT + `BacktestRunner` | Accepted trades |
| Exit grid | `research.exit_grid` | Re-walks SL×TP cells |
| Feature trajectories | IC-002 `build_trajectories` | Only full sequence store today |
| Forensics | `research.forensics` | Dual-model scalar outcomes |

**Hard rule for the substrate:** one **policy kernel family** (`forward_walk` modes). Do not invent a fourth simulator. PolicyEvaluator wraps the kernel; EpisodeBuilder does **not** own exit policy.

---

## 6. Data structures (current)

| Structure | Location | Stores full path? | Role under substrate |
|-----------|----------|-------------------|----------------------|
| `Signal` | `research/contracts.py` | No | Entry geometry input |
| `Outcome` | same | Scalars | PolicyEvaluator output shape (compat) |
| opportunities JSONL | `logs/**/opportunities.jsonl` | No | Detection population source only |
| Clean-label row | `clean_labels/builder` | Scalar path diagnostics | Future LabelSet consumer |
| `TradeRecord` + `TradePathStats` | `backtest_v2` | Scalars | Ledger; offline SpineProjector input |
| Stage-1 training row | `stage1_dataset_builder` | No | Unchanged default |
| RR training rows | `rr_dataset_builder` | No | Future consumer |
| `ReplayRecord` | `replay_memory_engine` | No | Future join |
| `TrajectoryBatch` | IC-002 | Yes (15×N) | Tensor materializer pattern |

**Natural home:** research-only store under `results/research/episodes/` (or similar), keyed by `episode_id` + provenance — **not** production journal and **not** rewritten opportunities.jsonl as system of record.

---

## 7. Feature pipeline impact

### Capability

`FeaturePipeline` is **batch-first**: one `run()` enriches the full OHLCV frame. Features for every forward bar already exist in the matrix. IC-002:

1. Runs pipeline once  
2. Aligns via `_src_idx`  
3. Slices `entry+1 … entry+N`  
4. Emits path-relative features  

So the challenge is **persistence, layering, and derivation policy** — not inventing a new online feature engine.

### Tiers (recommended)

| Tier | Content | Default |
|------|---------|---------|
| 0 | Observation OHLCV (+ optional ATR under frozen formula) | **Required** |
| 1 | Derived path metrics (MFE/MAE/R/distances) | Recomputable; may cache |
| 2 | Feature subset (e.g. IC-002 15) | Opt-in |
| 3 | Full canonical feature vector (39-dim schema v4) | Opt-in; storage-heavy |
| 4 | Embeddings / model scores | Annotation side-car only |

**Do not force full features on every step in canonical storage.** Prefer join-by-bar-index to the feature matrix when needed.

### Compute sketch

- Detection stream scale (~1e5+ rows historically) × T≤40 × 39 floats → multi-GB raw if naively stored.  
- Spine populations (tens–hundreds trades/instrument) → full features cheap.  
- Batch pipeline once per instrument corpus; slice per episode.

Note: live schema is **39-dim** (`CANONICAL_FEATURE_DIM` in `feature_schema.py`); many docs still say 38. Pin `feature_schema_hash`.

---

## 8. Proposed substrate architecture

### Layered system

```text
EntrySnapshot + Candle window (+ optional feature matrix)
                    │
                    ▼
            EpisodeBuilder / Projectors   (offline)
                    │
                    ▼
         OpportunityEpisode (canonical)
         entry + observation timeline + provenance
                    │
     ┌──────────────┼──────────────────┐
     ▼              ▼                  ▼
PolicyEvaluator  EventEngine      Annotators
 (exit policies) (rule packs)     (models/regime)
     │              │                  │
     ▼              ▼                  ▼
 LabelSet        EventSet         AnnotationSet
                    │
                    ▼
          Episode Query Engine
                    │
     ┌──────┬───────┼───────┬────────┐
     ▼      ▼       ▼       ▼        ▼
 tensors notebooks clean_y replay   RL
```

### Separation of concerns

| Layer | Owns | Does not own |
|-------|------|--------------|
| EpisodeBuilder | Observation timeline from candles + entry | Exit labels, event taxonomy |
| PolicyEvaluator | Labels under exit policy P | Episode existence |
| EventEngine | Sparse semantic milestones | Canonical steps |
| Query Engine | Research predicates / selections | Training authority |
| TensorBuilder | [N,T,D] views | Source of truth |

---

## 9. EpisodeStep layers

Each step (convention: document `t`; recommend entry as `t=0` observation, policy walks use `t≥1` only — **must freeze**):

```text
EpisodeStep
  t: int
  timestamp

  observation: Observation   # IMMUTABLE in canonical store
  derived: Derived | null    # recomputable; optional cache
  annotations: Annotations   # versioned; side-car preferred
```

### Observation (immutable facts)

- OHLC, volume  
- timestamp / bar index  
- spread if measured/simulated and declared  
- ATR only if pinned under `formula_hash` / ontology (else treat ATR as derived)

**Never rewrite** without new `observation_schema_version` + new build.

### Derived (recomputable)

Functions of `entry_snapshot` + observation prefix `0..t` (and declared geometry, not full exit policy):

- floating PnL / floating RR  
- running MFE / MAE / drawdown from peak / recovery  
- distance_to_SL / distance_to_TP under fixed entry geometry  
- bars_held  
- optional path-relative feature deltas  

### Annotations (versioned interpretations)

- regime / vol class  
- CRT structure state snapshots  
- model scores / embeddings  
- human or agent tags  

Stored as **AnnotationSet** side-cars (or clearly non-authoritative caches). Re-annotate without rebuilding episodes.

---

## 10. Policy independence

### Anti-pattern

```text
EpisodeBuilder → forward_walk(intrabar_fixed) → Episode+labels baked in
```

### Correct pattern

```text
Episode = observation timeline (policy-agnostic)
LabelSet_P = PolicyEvaluator(Episode, policy_P)
```

| Policy P | Role |
|----------|------|
| `intrabar_fixed` | Governing economic truth (M4 / clean labels / F-022 re-derive) |
| `trailing` | Scanner-legacy / comparative |
| `close_only` | Forensic optimistic bound |
| `partial_tp_be` | Execution research |
| experimental | Sandbox |

Implementation: PolicyEvaluator **reads** the observation timeline and applies `forward_walk` (or equivalent pure logic) against that path. It does **not** mutate the Episode.

Same Episode → multiple LabelSets without rebuild.

---

## 11. Events as derived artifacts

### Canonical truth

```text
OpportunityEpisode = identity + entry_snapshot + Observation timeline + provenance
```

### Events

```text
EventEngine(rulepack_vK): Episode → EventSet_vK
```

| Why derived | Consequence |
|-------------|-------------|
| New kinds in 5 years (`LIQUIDITY_SWEEP`, `FAKE_BREAKOUT`, …) | New rulepack only |
| Bug in event definition | Regenerate EventSet; Episode untouched |
| Multiple research programs | Multiple EventSets per Episode |

### Seed rulepack v1 (illustrative)

| Kind | Meaning |
|------|---------|
| `ENTRY` | Episode opens |
| `REACHED_R` | First +0.25/0.5/1/1.5/2/3R |
| `NEW_MFE` / `NEW_MAE` | Peak excursion update |
| `BE_ELIGIBLE` | e.g. MFE ≥ 1R (policy-declared) |
| `SL_THREAT` | Within X of stop |
| `TP_TOUCH` | Target geometry |
| `TIMEOUT` / `EXIT` | Terminal under a **linked** policy evaluation (or pure geometry end) |

Example future label without re-walk of candles:

```text
exists BE_ELIGIBLE with t ∈ (0, 5]
```

Existing compressed analogues: `timing_reconstructor` time_to_*R; `Outcome.reached_1r`; clean_labels `y_survives_be` / `y_time_to_1r`.

---

## 12. Provenance

### On canonical Episode

```text
episode_id
episode_version                 # document schema
population
instrument / timeframe

candle_corpus_id | candle_sha256
entry_geometry_hash

observation_schema_version
observation_schema_hash

feature_schema_hash             # if features attached
ontology_hash
canonical_feature_hash          # if vectors present

builder_id
builder_hash
builder_config_hash

# exit_policy_hash does NOT live on Episode —
# it lives on LabelSet
```

### On derived artifacts

```text
LabelSet:   episode_id, exit_policy_id, exit_policy_hash, cost_model_hash,
            evaluator_hash, label_protocol_id

EventSet:   episode_id, event_rulepack_id, event_rulepack_hash, engine_hash

AnnotationSet: episode_id, annotator_id, model_hash | rule_hash
```

**Reproducibility:** same candles + entry geometry + builder hashes → same Episode content hash.  
Same Episode + same policy hash → same LabelSet.

---

## 13. Storage triad

| Role | Form | Purpose |
|------|------|---------|
| **Canonical** | Nested **OpportunityEpisode** (metadata + entry + observation steps) | Immutable research truth (Option A at episode grain) |
| **Analytics** | Flattened `episode_id, t, …` parquet / DuckDB | SQL, filters, notebooks (Option C at step grain) |
| **Training** | On-demand `[N,T,D]` tensors | LSTM/Transformer/path heads — **never** canonical |

Plus separate stores for EventSet / LabelSet / AnnotationSet.

### Rejected as primary store

- Nested paths stuffed into `opportunities.jsonl` (scale + F-022).  
- Tensor-only corpus (opaque, not queryable, not multi-consumer).  
- Production `TradeRecord` field dump.

### Recommended locations (research, gitignored artifacts)

```text
results/research/episodes/{instrument}/          # Tier 1 canonical
results/research/episodes_flat/{instrument}/     # Tier 2
results/research/episode_labels/{policy}/        # LabelSets
results/research/episode_events/{rulepack}/      # EventSets
results/research/episode_tensors/{view}/         # caches
```

Default: **do not** embed full feature vectors in Tier 1; join by bar index when needed.

---

## 14. Episode Query Engine

Insert between store and consumers:

```text
Episode Store + LabelSets + EventSets + AnnotationSets
        │
        ▼
 Episode Query Engine
        │
        ▼
 selections → notebooks / TensorBuilder / reports
```

### v1 capabilities (must)

- Filter by population, instrument, time range  
- Predicates on **derived** timeline (e.g. max MFE_r ≥ 1 within first 6 bars AND min MAE_r > −0.4)  
- Join EventSet version K  
- Join LabelSet policy P  

### v2

- Annotation predicates  
- Sequence pattern DSL  
- Export to tensors with pad/mask policy  

Example research language:

```text
Find every episode that reached 1R before 6 candles
without exceeding 0.4R adverse excursion.
```

Query results are **views**, not new truth. Deterministic queries should be hashable for paper trails.

---

## 15. Production isolation (Projector only)

### Forbidden

```text
TradeJournal / live path → write Episode store
```

Runtime must stay unaware of research storage.

### Required

```text
Production / backtest
  → Ledger (TradeRecord CSV, transitions, logs)   # as today
  → Episode Projector (offline, research package)
  → OpportunityEpisode (population=SPINE_TRADE | …)
```

### Projectors (same schema, different sources)

| Projector | Inputs | Population |
|-----------|--------|------------|
| DetectionProjector | opportunities geometry + candles | `DETECTION_STREAM` |
| HypothesisProjector | Signal stream + candles | `HYPOTHESIS_SIGNAL` |
| SpineProjector | TradeRecord/ledger + candles | `SPINE_TRADE` |
| StructuralProjector | detectors + candles | `STRUCTURAL_EVENT` |

All produce **OpportunityEpisode**; only entry provenance and density differ.

---

## 16. Research impact (unified consumers)

```text
OpportunityEpisode Store
        │
        ├── TradeNet labels          (LabelSet + EventSet)
        ├── RR / envelope targets    (Policy + derived)
        ├── Exit intelligence        (multi-policy LabelSets)
        ├── Replay memory joins      (entry features + outcomes)
        ├── Offline RL               (steps + optional action annotations)
        ├── Sequence / Transformer   (TensorBuilder; IC-002 generalizes)
        ├── Forensics / exit_grid    (multi-policy without re-ingest)
        └── Notebooks                (Query Engine)
```

| Subsystem | Benefit | Today’s substitute |
|-----------|---------|-------------------|
| TradeNet | Path / time-to-event / multi-policy y | Entry vector + re-walk Bernoulli |
| RR Engine | Clean path-conditioned targets | Stream rr (F-022 risk) |
| Exit models | When-to-exit from state trajectory | exit_grid scalars |
| Dynamic SL / trail | Observe threat path | None durable |
| Partial TP / BE | Event predicates | MFE ≥ 1R scalar |
| Sequence models | Full sequences | IC-002 15-dim only |
| Regime path | Annotations over time | Entry regime only |
| Replay Memory | Precedent trajectories | Outcome-only records |
| Offline RL | MDP steps | Absent |
| EnvelopeNet | Running MFE/MAE series | horizon_excursion re-walk |

**Strategic ROI:** one observation build, many policies/events/queries — collapses duplicated simulation across scanner, clean_labels, forensics, exit_grid, IC-002, and ad-hoc scripts.

---

## 17. Backward compatibility

| Surface | Constraint |
|---------|------------|
| Production inference | No change to EngineRunner, fusion, DecisionEngine, live hook |
| Feature schema | No change to live CANONICAL schema for production |
| Live execution | No Episode I/O on hot path |
| TradeRecord / trades CSV | Unchanged default |
| `forward_walk` public return | Stays `Outcome` for EdgeReport byte-compat; path emit is optional/side channel |
| opportunities.jsonl readers | Existing keys still parse; Episode is a new store |
| Stage-1 / phase5 / ReplayMemory | Optional consumers only |
| Active config / promotion | No new authority |

**Invariant:** `PRODUCTION_BEHAVIOR_CHANGED = NO` until explicit authority grant.

---

## 18. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Nested JSON memory blow-up | High | Parquet nested Tier 1; never load full corpus as Python nested dicts blindly |
| Detection-stream size × T × dims | High | Observation-minimal Tier 1; feature join; population choice |
| Second exit kernel drift | **Critical** | PolicyEvaluator only wraps `forward_walk` family |
| F-022 if stream labels treated as truth | High | Labels only from PolicyEvaluator; stream fields diagnostic |
| Events stored-first → rebuild tax | High | Events derived only |
| Exit policy baked into Episode | High | Policy-independent timeline |
| Production coupling | High | Offline Projector; package under `src/research/` |
| Schema / PIT unclean features (F-051) | Medium | Provenance `pit_status`; re-emit features if needed |
| Episode vs backtest scalar mismatch | High | Parity: LabelSet aggregates == journal / Outcome |
| Serialization / versioning | Medium | Multi-hash provenance; additive schema versions |

---

## 19. Component impact matrix

| Component | Role | Impact | Complexity | Touch? |
|-----------|------|--------|------------|--------|
| `forward_walk` | Policy kernel | Used by PolicyEvaluator; Outcome unchanged | Medium | Additive only |
| `contracts.py` | Signal/Outcome | Optional re-export of episode types | Low | Optional |
| New `research/episodes/*` | Substrate | Core new package | Medium–High | **Yes** |
| clean_labels | Labels | Gradual consumer of LabelSet | Medium | Later |
| opportunity_scanner | Detection source | Entry geometry source; prefer offline projector | Low | Prefer no nest |
| backtest_v2 / TradeJournal | Ledger | **No Episode writes** | — | **No** (verify ledger completeness only) |
| FeaturePipeline | Features | Reuse batch | Low | No |
| IC-002 | Tensor precedent | Materializer under Query | Medium | Refactor later |
| stage1 / train_pipeline | Training | Opt-in later | High (phase) | Later |
| Production engines / live | Runtime | None | — | **No** |

---

## 20. Files / modules

### New (proposed)

| Module | Purpose |
|--------|---------|
| `src/research/episodes/schema.py` | OpportunityEpisode, EpisodeStep, Observation, Derived, Annotations, provenance |
| `src/research/episodes/builder.py` | Build observation timeline from candles + entry |
| `src/research/episodes/projectors/*.py` | Detection / Hypothesis / Spine projectors |
| `src/research/episodes/store.py` | Canonical + flat I/O |
| `src/research/episodes/policy.py` | PolicyEvaluator + LabelSet |
| `src/research/episodes/events.py` | EventEngine + EventSet |
| `src/research/episodes/query.py` | Episode Query Engine |
| `src/research/episodes/tensors.py` | TensorBuilder (IC-002 generalization) |
| `scripts/research/build_episodes.py` | Thin CLI |
| Protocol freeze doc + hash | Like clean_labels protocol |

### Modify (when implemented — research only)

- Consumers gradually: clean_labels, forensics adapters, analysis scripts  
- Docs: this file, schemas reference, research-readiness protocol  
- Tests under `tests/research/episodes/`

### Untouched by default

- EngineRunner, Fusion, DecisionEngine, ExecutionPlanner, Ultron  
- Live I/O / MT5  
- Formula registry / ontology (read-only pin via hashes)  
- Promotion manager / production configs behaviour  
- Default opportunities.jsonl contract  

---

## 21. Migration roadmap

| Phase | Deliverable | Production impact |
|-------|-------------|-------------------|
| **P0 Freeze** | OpportunityEpisode contract: Observation schema, t convention, provenance, population enum, non-goals | None |
| **P1 Builder** | EpisodeBuilder + Detection/Hypothesis projectors; observation timeline | None |
| **P2 Policy** | PolicyEvaluator wrapping `forward_walk`; LabelSet store; Outcome parity tests | None |
| **P3 Events** | EventEngine v1 rulepack; EventSet store | None |
| **P4 Query** | Query Engine v1 predicates | None |
| **P5 Projections** | Flat tables + TensorBuilder | None |
| **P6 SpineProjector** | Offline from journal/candles | None |
| **P7 Consumers** | clean_labels / forensics / exit_grid migrate gradually | None |
| **P8 Training** | Opt-in sequence / multi-task heads | None (research models only) |

Phasing preserves: **contract → observation build → multi-policy labels → events → query → tensors → consumers**.

---

## 22. Complexity estimates

| Piece | Complexity | Notes |
|-------|------------|-------|
| Schema + provenance freeze | Low–Medium | Design-heavy, code-light |
| EpisodeBuilder observation timeline | Medium | Candle alignment, no-lookahead |
| PolicyEvaluator multi-exit | Medium | Parity with `forward_walk` is load-bearing |
| EventEngine derived | Medium | Must stay pure |
| Store + flatteners | Medium | Parquet preferred |
| Query Engine | Medium–High | Start library API, not full DSL |
| SpineProjector | Medium | Ledger completeness risk |
| Consumer migration | Medium | Dual-read period |
| Production spine | **None** | Forbidden by default |

Overall program: **Medium** (~20–25 person-days if phased as above; order-of-magnitude, not a schedule commitment).

---

## 23. Open decisions (pre-freeze)

1. **Root name in code:** `OpportunityEpisode` (recommended) vs `MarketEpisode`.  
2. **`t` convention:** entry bar as `t=0` included vs post-entry-only (must align with `forward_walk` future slice).  
3. **ATR placement:** Observation (with formula_hash) vs Derived.  
4. **v1 Observation minimum:** OHLCV + index + timestamp (recommended start).  
5. **v1 Policy set:** at least `intrabar_fixed`; prove multi-policy with `close_only` and/or `trailing`.  
6. **Query v1 surface:** library API first vs declarative JSON predicates.  
7. **First corpus population:** spine (clean, small) vs detection stream (power, F-022 discipline).  
8. **Artifact root path** under `results/research/…`.

---

## 24. Non-goals

1. Live/hot-path Episode construction  
2. TradeJournal writing research store  
3. Nested episodes inside `opportunities.jsonl` as system of record  
4. Events as the only store of path semantics without steps  
5. Single exit policy baked into Episode identity  
6. Training tensors as canonical storage  
7. Authority to promote models from Episode data without §6.5 G001 ladder  
8. Replacing production `TradeRecord` schema  

---

## 25. Evolution of this audit

| Round | Framing | Score / outcome |
|-------|---------|-----------------|
| **1** | “Forward path storage” | Strong codebase map; storage B+C; underspecified long-term |
| **2** | “Trade Episode” = entry + timeline + events + labels | Better substrate; risk of events-as-primary and exit-coupled build |
| **3** | **OpportunityEpisode** + policy-independent timeline + Observation/Derived/Annotations + derived events + Query + offline Projector | Pre-freeze design (~9.8/10 per review) |

### Freezes adopted from review

1. Episode independent of exit policy (PolicyEvaluator).  
2. Observations immutable; interpretations versioned.  
3. Events derived, not canonical.  
4. Episode Query layer first-class.  
5. Offline Episode Projector only (no journal write).  
6. Broader than TradeEpisode → **OpportunityEpisode**.

### Storage freezes

- Canonical = nested Episode (observation timeline).  
- Analytics = flat steps.  
- Training = regenerable tensors.  
- LabelSet / EventSet / AnnotationSet = versioned side-cars.

---

## 26. Diagrams

### 26.1 Current (compressed, multi-walker)

```text
                    ┌─────────────────────┐
                    │   OHLCV M15 CSV     │
                    └──────────┬──────────┘
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
   FeaturePipeline      CandleLoader        (same candles)
           │                   │                   │
           ▼                   ▼                   ▼
 opportunity_scanner      CRTEngine         Hypothesis.detect
 long+short / bar       TRADE_OPENED        research runner
           │                   │                   │
           ▼                   ▼                   ▼
   _simulate TRAILING    engine exits       forward_walk
   → scalar outcome    TradePathStats       INTRABAR_FIXED
           │             scalars            scalars
           ▼                   ▼                   ▼
 opportunities.jsonl    *_trades.csv      Outcome / EdgeReport
           │                                     │
           ▼                                     ▼
  stage1 / phase5 / RR                    clean_labels y_*
           │
           ▼
  models (Gaussian/RR/zones) … F-022 contamination risk on stream y

  IC-002 (side): features@t0..tN (15-dim) → npz   [only full path today]
```

### 26.2 Proposed substrate

```text
  PRODUCTION / BACKTEST (unchanged)
  OHLCV → features → CRT → journal/ledger → trades CSV
                         │
                         │  offline only
                         ▼
              SpineProjector ──┐
  DetectionProjector ──────────┼──► OpportunityEpisode Store (canonical)
  HypothesisProjector ─────────┘         entry + observation steps
                                              │
                         ┌────────────────────┼────────────────────┐
                         ▼                    ▼                    ▼
                  PolicyEvaluator       EventEngine          Annotators
                  LabelSets             EventSets            AnnotationSets
                         │                    │                    │
                         └────────────────────┼────────────────────┘
                                              ▼
                                   Episode Query Engine
                                              │
                    ┌─────────────┬───────────┼───────────┬────────────┐
                    ▼             ▼           ▼           ▼            ▼
                 tensors      notebooks   clean_y     replay        RL
```

### 26.3 Policy vs timeline

```text
  EpisodeBuilder ──► Observation timeline (immutable)
                              │
              PolicyEvaluator(intrabar_fixed) ──► LabelSet_A
              PolicyEvaluator(trailing)       ──► LabelSet_B
              PolicyEvaluator(close_only)     ──► LabelSet_C
              EventEngine(rulepack_v1)        ──► EventSet_v1
              EventEngine(rulepack_v2)        ──► EventSet_v2
```

---

## Appendix A — Original audit deliverable checklist

| # | Deliverable | Location in this doc |
|---|-------------|----------------------|
| 1 | Current architecture diagram | §26.1 |
| 2 | Proposed architecture diagram | §26.2–26.3 |
| 3 | Component impact matrix | §19 |
| 4 | Files requiring modification | §20 |
| 5 | New modules required | §20 |
| 6 | Untouched modules | §20 |
| 7 | Risk assessment | §18 |
| 8 | Migration roadmap | §21 |
| 9 | Storage recommendation | §13 |
| 10 | Complexity estimates | §22 |

---

## Appendix B — Related findings & code anchors

| Anchor | Relevance |
|--------|-----------|
| F-022 | Detection stream ≠ trade ledger; re-derive via governing exit |
| F-037 | Research spine often CRT-only; fusion gate config-dependent |
| F-051 | Centered-swing / PIT unclean stored features — declare pit_status |
| `forward_walk` | Governing kernel for labels |
| `clean_labels/protocol.py` | Label protocol freeze pattern to copy |
| IC-002 | Tensor materialization pattern |
| `TradePathStats` | Spine scalar path metrics; parity target for SpineProjector |

---

## Appendix C — Relationship to platform-design.md

[`opportunity-episode-platform-design.md`](opportunity-episode-platform-design.md) is an earlier design freeze draft (rev 2) with concrete dataclass sketches and phase day estimates.

**This document** is the full multi-round **audit transport**: codebase reconstruction, dual-pipeline map, F-022 discipline, evolution of the abstraction, and the final pre-freeze principles (policy independence, derived events, query layer, projector isolation).

On conflict of narrative: **this file wins for principles and codebase map**; implementation may still follow platform-design module layout once Phase-0 freezes open decisions in §23.

---

*End of consolidated architecture document. No production authority. Implementation requires Phase-0 freeze + construction protocol.*
