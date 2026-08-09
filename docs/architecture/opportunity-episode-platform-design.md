# Opportunity Episode Platform — Architecture Design

> **Status:** Design freeze draft (architecture audit output, revision 2)  
> **Date:** 2026-07-22  
> **Full audit transport (recommended entry point):**  
> [`opportunity-episode-research-substrate.md`](opportunity-episode-research-substrate.md)  
> — multi-round reconstruction + pre-freeze principles (policy-independent timeline,  
> derived events, query layer, offline projector). On principle conflict, the substrate  
> doc wins; this file retains concrete dataclass/phase sketches.  
> **Authority:** NONE (§6.5) — research infrastructure design, not a production contract.
> **Contract frozen 2026-07-23** as protocol `OE_L1` —
>   [`src/research/episodes/protocol.py`](../../src/research/episodes/protocol.py) +
>   [`docs/research-readiness/opportunity-episode-prereg.md`](../research-readiness/opportunity-episode-prereg.md)
>   (change id `CH-opportunity-episodes`). The prereg resolves substrate §23's eight open
>   decisions and supersedes this file wherever the two differ.
> **Consumes:** [`docs/architecture/model-design-intent.md`](model-design-intent.md) §missing-stage-#6
> **Siblings:** [`envelope-layer-design.md`](envelope-layer-design.md) (post-entry operating envelope)
>   · [`docs/architecture/TRADING_SYSTEM_FRAMEWORK.md`](TRADING_SYSTEM_FRAMEWORK.md) (reference framework)
>   · [`opportunity-episode-research-substrate.md`](opportunity-episode-research-substrate.md) (full audit)

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Design Principles](#2-design-principles)
3. [The Missing Abstraction](#3-the-missing-abstraction)
4. [Opportunity Episode — Conceptual Model](#4-opportunity-episode--conceptual-model)
5. [Data Structures](#5-data-structures)
6. [Three-Tier Storage Architecture](#6-three-tier-storage-architecture)
7. [Current Architecture Diagram](#7-current-architecture-diagram)
8. [Proposed Architecture Diagram](#8-proposed-architecture-diagram)
9. [Component Impact Matrix](#9-component-impact-matrix)
10. [Files Requiring Modification](#10-files-requiring-modification)
11. [New Modules Required](#11-new-modules-required)
12. [Existing Modules That Remain Untouched](#12-existing-modules-that-remain-untouched)
13. [Risk Assessment](#13-risk-assessment)
14. [Migration Roadmap](#14-migration-roadmap)
15. [Storage Model Recommendation](#15-storage-model-recommendation)
16. [Estimated Implementation Complexity](#16-estimated-implementation-complexity)
17. [Research Impact](#17-research-impact)
18. [Backward Compatibility Guarantees](#18-backward-compatibility-guarantees)

---

## 1. Problem Statement

### Current Behaviour

Every historical trade opportunity today is compressed into a single outcome label. The research pipeline produces:

```
Entry timestamp
Entry features (39-dim canonical feature vector — CANONICAL_FEATURE_DIM, feature_schema.py:114)
Entry decision (from CRT state machine + fusion committee)
Final outcome (TP_HIT / SL_HIT / TIMEOUT)
Exit reason
RR achieved
MFE (scalar max), MAE (scalar max)
Duration
Various summary statistics
```

**The entire forward trajectory between entry and exit is discarded.**

Multiple implementations independently simulate the forward walk. Each drifts independently;
none preserves per-candle data.

> **SUPERSEDED 2026-07-23 (audit).** The five-item list previously here was incomplete and one
> item was wrong. The authoritative inventory is
> [`opportunity-episode-research-substrate.md`](opportunity-episode-research-substrate.md) §5,
> which enumerates **ten** walk owners. In particular, **RR label generation does not re-simulate
> forward** — per F-045 it derives `y` from the trade `outcome`/`rr_achieved` field
> (`rr_dataset_builder.py:125-206`), which is precisely why those labels are F-022-contaminated.
> Use substrate §5 as the migration inventory.

### Desired Behaviour

Every opportunity should preserve the complete forward market evolution after entry — an **Opportunity Episode** — enabling per-step recovery of:

- **Observations** (immutable): OHLC, volume, ATR, spread, timestamp
- **Derived** (recomputable): MFE, MAE, floating PnL (raw and R-multiple), distance to SL/TP, drawdown
- **Annotations** (versioned): regime, trend state, structure state, engine scores, model outputs

Additionally, the platform should enable:
- Multiple exit-policy evaluations from a single episode (no re-simulation)
- Semantic event detection from step sequences (reached 1R, break-even eligible, volatility expansion)
- SQL/DSL querying across episodes for research
- Sequence-aware model training (transformers, LSTMs, offline RL)

---

## 2. Design Principles

1. **Research-only.** Zero impact on production runtime, latency, schema, or behavior.
2. **Observations are immutable.** OHLC, volume, ATR never change. Everything else is derived or annotated.
3. **Episode is independent of exit policy.** The episode captures the market+position timeline; labels are computed offline by a Policy Evaluator.
4. **Events are derived, not stored.** Semantic milestones are generated from episodes by a versioned Event Engine. No schema migration needed when new event types are invented.
5. **Production never knows about episodes.** An offline Episode Projector reconstructs episodes from the production ledger.
6. **One source of truth for all downstream models.** TradeNet, RR, Exit, Replay, RL — all derive from episodes.
7. **Perfect reproducibility.** Provenance hashes on every episode make it reproducible years later.

---

## 3. The Missing Abstraction

The codebase currently has three independent representations of a "trade opportunity," all lossy in different ways:

| Representation | Location | Keeps Path? | Purpose |
|---|---|---|---|
| `Trade` (engine dataclass) | `crt_engine_v2.py` | No | Engine-internal live state |
| `TradeRecord` (backtest) | `backtest_v2.py` | No (only MFE/MAE scalars) | Backtest results CSV |
| Opportunity dict (research) | `opportunity_scanner.py` | No | Training data generation |

**An Opportunity Episode is a new first-class architectural concept** that subsumes all three. It is:

1. A **self-contained research artifact** — the complete record of one opportunity from entry to exit (or timeout)
2. A **single source of truth** — every downstream model derives labels from episodes, not from independent simulation
3. A **durable research substrate** — designed to accommodate future concepts (events, RL actions, model predictions) without schema changes to production code
4. **Policy-agnostic** — the same episode can be evaluated with multiple exit policies without re-simulation

### Scope of "Opportunity"

"Opportunity" is broader than "trade executed by the production system." An Opportunity Episode represents *any* moment where an entry decision could have been made:

| Episode Type | Source | Example |
|---|---|---|
| **Scanner opportunity** | `opportunity_scanner.py` | Every candle past warmup, both long and short |
| **Production trade** | CRT engine → backtest | A trade that was actually executed |
| **Rejected signal** | CRT engine (decision said no) | CRT proposed, fusion or risk rejected |
| **Hypothesis episode** | Research query | "What if we entered at this level at this time?" |
| **Liquidity event** | CRT sweep detection | A sweep occurred; was there an opportunity? |
| **Regime transition** | Market state change | Before/after a regime boundary |

All share the same structure: entry event → timeline → outcome. The architecture must not privilege executed trades over other opportunity types.

---

## 4. Opportunity Episode — Conceptual Model

```
OpportunityEpisode
│
├── episode_id                          [UUID :: str]
├── episode_type                        [SCANNER | PRODUCTION | REJECTED |
│                                           HYPOTHESIS | LIQUIDITY_EVENT | REGIME_TRANSITION]
├── instrument                          [str]
├── timeframe                           [str, e.g. "M15"]
│
├── entry                               [OpportunityEntry]
│   ├── entry_index                     [int — global OHLCV index]
│   ├── entry_timestamp                 [datetime]
│   ├── entry_price                     [float]
│   ├── direction                       [LONG | SHORT]
│   ├── sl_price                        [float or None — may not exist for non-trade episodes]
│   ├── tp_price                        [float or None]
│   ├── trail_mult                      [float or None]
│   ├── atr_entry                       [float or None]
│   ├── risk_distance                   [float or None — |entry - sl|]
│   ├── engine_scores                   [dict[str, float] or None]
│   └── generator_config                [dict — full config snapshot for reproducibility]
│
├── steps                               [list[EpisodeStep]]
│   │   (one per forward observation, including exit step)
│   │
│   ├── OBSERVATION (immutable — never changes)
│   │   ├── timestamp                   [datetime]
│   │   ├── step_index                  [int — 1-based offset from entry]
│   │   ├── open, high, low, close      [float]
│   │   ├── volume                      [float]
│   │   └── atr                         [float — ATR at this step]
│   │
│   ├── DERIVED (recomputable from observation prefix + FIXED entry geometry)
│   │   │   NOTE 2026-07-23: `stop` / `tp` REMOVED — a trailing stop is a function of
│   │   │   the exit policy, so storing it makes the canonical step policy-coupled
│   │   │   (the anti-pattern in substrate §10). Current stop/TP live on the LabelSet.
│   │   ├── unrealized_pnl_raw          [float — entry-relative PnL]
│   │   ├── unrealized_pnl_rr           [float — PnL / risk_distance]
│   │   ├── mfe                         [float — max favorable excursion to date]
│   │   ├── mae                         [float — max adverse excursion to date]
│   │   ├── distance_to_sl              [float — (price - stop) in price units]
│   │   ├── distance_to_tp              [float — (tp - price) in price units]
│   │   ├── distance_to_sl_atr          [float — distance_to_sl / atr]
│   │   ├── distance_to_tp_atr          [float — distance_to_tp / atr]
│   │   ├── drawdown_from_peak          [float — peak-to-current PnL drawdown]
│   │   └── is_active                   [bool — episode still running]
│   │
│   └── ANNOTATION (versioned — carries ontology_hash)
│       ├── regime                      [str or None]
│       ├── structure                   [str or None — CRT state snapshot]
│       ├── trend                       [str or None]
│       ├── volatility_class            [str or None]
│       ├── engine_scores               [dict[str, float] or None]
│       ├── feature_vector              [dict[str, float] or None — optional, heavy]
│       └── custom                      [dict[str, Any] or None — extensible]
│
├── provenance                          [EpisodeProvenance]
│   ├── generator_version               [str — episode projector version]
│   ├── schema_version                  [int — episode schema version]
│   ├── feature_schema_hash             [str — SHA-256 of CANONICAL_FEATURES + formula registry]
│   │                                     (39-dim — see CANONICAL_FEATURE_DIM, feature_schema.py:114)
│   │   NOTE 2026-07-23: `exit_policy_hash` REMOVED — it contradicted Principle 3 of
│   │   this document. Per substrate §12 it lives on the LabelSet, never the Episode.
│   ├── builder_hash                    [str — SHA-256 of projector code]
│   ├── ontology_hash                   [str — SHA-256 of annotation ontology definitions]
│   ├── candle_source_hash              [str — SHA-256 of OHLCV data identity (file + row range)]
│   ├── source_run_id                   [str — run identifier from generator]
│   ├── created_at                      [datetime]
│   └── checksum                        [str — SHA-256 of the serialized episode]
│
└── metadata                            [dict — extensible key-value store]
```

### Key Design Decisions

**The episode does NOT contain:**
- Labels (outcome, RR achieved) — these are computed by the Policy Evaluator
- Events (reached_1R, trail activated) — these are computed by the Event Engine
- Exit reason — the episode captures the timeline; the exit is derived

**The episode ONLY contains:**
- Entry definition (what, where, when, with what parameters)
- Step sequence (observations + derivations + annotations at each timestep)
- Provenance (everything needed to reproduce)

**Why:** An episode can be evaluated with multiple exit policies. The same episode can produce intrabar_fixed labels, trailing labels, close-only labels, and experimental labels — all without rebuilding the episode.

---

## 5. Data Structures

### 5.1 Python Dataclasses (in `src/research/episode.py`)

```python
@dataclass
class EpisodeObs:
    timestamp: datetime
    step_index: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    atr: float


@dataclass
class EpisodeDerived:
    # `stop` / `tp` REMOVED 2026-07-23 — policy state, not derived state (see §4 note).
    unrealized_pnl_raw: float = 0.0
    unrealized_pnl_rr: float = 0.0
    mfe: float = 0.0
    mae: float = 0.0
    distance_to_sl: float = 0.0
    distance_to_tp: float = 0.0
    distance_to_sl_atr: float = 0.0
    distance_to_tp_atr: float = 0.0
    drawdown_from_peak: float = 0.0
    is_active: bool = True


@dataclass
class EpisodeAnnotation:
    ontology_version: str = ""
    regime: str | None = None
    structure: str | None = None
    trend: str | None = None
    volatility_class: str | None = None
    engine_scores: dict[str, float] | None = None
    feature_vector: dict[str, float] | None = None
    custom: dict[str, Any] | None = None


@dataclass
class EpisodeStep:
    obs: EpisodeObs
    derived: EpisodeDerived = field(default_factory=EpisodeDerived)
    annotation: EpisodeAnnotation = field(default_factory=EpisodeAnnotation)


@dataclass
class OpportunityEntry:
    entry_index: int
    entry_timestamp: datetime
    entry_price: float
    direction: str                          # "LONG" | "SHORT"
    sl_price: float | None = None
    tp_price: float | None = None
    trail_mult: float | None = None
    atr_entry: float | None = None
    risk_distance: float | None = None
    engine_scores: dict[str, float] | None = None
    generator_config: dict[str, Any] | None = None


@dataclass
class EpisodeProvenance:
    generator_version: str
    schema_version: int
    feature_schema_hash: str
    # `exit_policy_hash` REMOVED 2026-07-23 — belongs on the LabelSet (substrate §12).
    builder_hash: str
    ontology_hash: str
    candle_source_hash: str
    source_run_id: str
    created_at: datetime
    checksum: str


@dataclass
class OpportunityEpisode:
    episode_id: str
    episode_type: str                       # SCANNER | PRODUCTION | REJECTED | HYPOTHESIS | ...
    instrument: str
    timeframe: str
    entry: OpportunityEntry
    steps: list[EpisodeStep]
    provenance: EpisodeProvenance
    metadata: dict[str, Any] = field(default_factory=dict)
```

### 5.2 Event Engine Output (derived artifact)

Events are **not** stored in the episode. They are generated by the Event Engine:

```python
@dataclass
class EpisodeEvent:
    event_id: str
    episode_id: str
    event_type: str                         # REACHED_1R | TRAIL_ACTIVATED | NEW_MFE | ...
    step_index: int                        # which step the event occurred at
    event_version: str                     # which event ontology produced this
    payload: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


class EventEngine:
    """Deterministic, versioned event detection from episode steps."""
    
    def detect(self, episode: OpportunityEpisode, 
               event_set_version: str = "v1") -> list[EpisodeEvent]:
        """Pure function: same steps → same events for a given version."""
        ...
```

Multiple event versions can coexist for the same episode (`events_v1`, `events_v2`, etc.).

### 5.3 Policy Evaluator Output (derived artifact)

Labels are also derived, not stored:

```python
@dataclass
class PolicyLabels:
    policy_id: str                          # "intrabar_fixed" | "trailing_v2" | "close_only" | ...
    policy_hash: str
    outcome: str                            # TP_HIT | SL_HIT | TIMEOUT
    rr_achieved: float
    duration_candles: int
    reached_1r: bool
    reached_2r: bool
    time_to_1r: int
    time_to_tp: int
    time_to_sl: int
    mfe_max: float
    mae_max: float
    mfe_at_exit: float
    capture_ratio: float | None
    giveback: float | None
    time_efficiency: float | None
    adverse_efficiency: float | None


class PolicyEvaluator:
    """Applies a specific exit policy to an episode and computes labels."""
    
    def evaluate(self, episode: OpportunityEpisode,
                 policy_config: dict) -> PolicyLabels:
        """Deterministic: same episode + same policy → same labels."""
        ...
```

### 5.4 Schema Versioning

- `schema_version` in provenance starts at 1.
- Breaking changes (field removal, type change) increment schema_version.
- Additive changes (new optional field in annotation) do not.
- The episode store can carry multiple schema versions; readers consume what they understand.
- Event versions and policy versions are independent of schema_version.

---

## 6. Three-Tier Storage Architecture

### Tier 1: Canonical Episodes (the truth)

```
Location: results/episode_corpus/{instrument}/episodes.parquet
Format:   Nested Parquet (one row per episode)
Schema:   episode_id STRING,
          episode_type STRING,
          instrument STRING,
          timeframe STRING,
          entry STRUCT<...>,
          steps ARRAY<STRUCT<obs STRUCT<...>, derived STRUCT<...>, annotation STRUCT<...>>>,
          provenance STRUCT<...>,
          metadata MAP<STRING, STRING>
Properties:
  - Immutable truth after validation
  - Write once, read many
  - Self-describing (Parquet schema + custom metadata)
  - Partitioned by instrument, optionally by year-month
  - Events and labels are NOT stored here (they are derived)
```

### Tier 2: Flat Timestep View (analytics)

```
Location: results/episode_corpus_flat/{instrument}/
Format:   Flat Parquet (one row per timestep per episode)
Schema:   episode_id, step_index,
          obs.*, derived.*, annotation.*,
          provenance.*
Properties:
  - Generated FROM Tier 1 (idempotent derivation)
  - Columnar — efficient for SQL, DuckDB, pandas
  - Cross-episode queries: "find all timesteps where distance_to_sl_atr < 0.5"
```

### Tier 3: Tensor Store (training)

```
Location: results/episode_corpus_tensors/{instrument}/
Format:   .npy files and metadata.json (or zarr for streaming)
Shape:    [N_episodes, max_timesteps, D_features]
Properties:
  - Generated FROM Tier 1 on demand
  - Configurable feature selection, padding strategy, masking
  - Not stored in version control — regenerated
  - Multiple tensor views can coexist (different feature subsets)
```

### Derived Artifacts (separate from tiers)

```
Location: results/episode_events/{instrument}/{event_set_version}/
Format:   Parquet (one row per event)
Schema:   event_id, episode_id, event_type, step_index, event_version, payload

Location: results/episode_labels/{instrument}/{policy_id}/
Format:   Parquet (one row per episode)
Schema:   episode_id, policy_id, outcome, rr_achieved, duration_candles, ...
```

### Key Property

**Tier 1 is canonical. Tiers 2, 3, events, and labels are always derivable.** This means:
- No migration pain when ML pipelines change — re-derive from episodes
- No duplicated simulation — one forward walk per opportunity
- Events can be regenerated with new detection logic without touching episodes
- Labels can be recomputed with different exit policies without rebuilding episodes

---

## 7. Current Architecture Diagram

```
                    PRODUCTION PIPELINE

  OHLCV ──► FeaturePipeline ──► CRT Engine ──► Fusion ──► Decision
                                        │
                                        ▼
                                   Trade (engine)
                                   {entry, sl, tp, pnl}
                                        │
                                        ▼
                                   TradeJournal
                                   {TradeRecord → CSV}
                                   MFEmax, MAEmax — path DISCARDED


                    RESEARCH PIPELINE

  OHLCV ──► FeaturePipeline ──► OpportunityScanner
                                        │
                                        ▼
                              _simulate() {forward walk}
                                        │
                                        ▼
                              {outcome, rr, mfe, mae, duration}
                              PATH DISCARDED
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
            Phase5 Calibration   Trace Corpus        Zone Discovery
            {features → label}   {entry+outcome}     {entry features}

                    ┌───────────────────┐
                    ▼                   ▼
            TradeNet Labels      RR Labels
            (re-simulated)       (re-simulated)

DUPLICATED SIMULATION:
  - opportunity_scanner._simulate()
  - build_trace_corpus
  - TradeJournal.observe_open_bar()
  - TradeNet label generation
  - RR label generation
  - Exit model data generation
```

---

## 8. Proposed Architecture Diagram

```
                    PRODUCTION PIPELINE (UNCHANGED)

  OHLCV ──► FeaturePipeline ──► CRT Engine ──► Fusion ──► Decision
                                        │
                                        ▼
                              TradeJournal → CSV
                                        │
                                        ▼
                              Ledger (append-only)
                              {candle_index, event, state, scores, ...}
                              (already exists as EngineEvent log +
                               crt_transitions.jsonl)


                    OFFLINE RESEARCH PIPELINE

  ┌── Ledger ─────┐
  │   OHLCV ──────┤───► Episode Projector (offline, deterministic)
  │  Features ────┤        │
  │   Config ─────┘        │
  │                        ▼
  │  ┌─────────────────────────────────────────────────────────┐
  │  │   OpportunityEpisode (immutable)                         │
  │  │                                                         │
  │  │   entry {entry_ts, price, sl, tp, scores, config}       │
  │  │   steps[] {                                             │
  │  │     obs {o, h, l, c, vol, atr}                          │
  │  │     derived {rr, mfe, mae, dist_sl, drawdown}           │
  │  │     annotation {regime, structure, scores}              │
  │  │   }                                                      │
  │  │   provenance {5 hashes, versions, checksum}             │
  │  └──────────────────────┬──────────────────────────────────┘
  │                         │
  │            ┌────────────┼────────────┐
  │            ▼            ▼            ▼
  │      Event Engine   Policy Eval  Query Index
  │      {v1, v2, ...}  {per policy}  {flat + inverted}
  │            │            │            │
  │            ▼            ▼            ▼
  │       events_v1     labels_v1    Tier 2 Query View
  │       events_v2     labels_v2    (flat Parquet)
  │       ...           ...
  │                                      │
  │                                      ▼
  │                               Episode Query Layer
  │                               {filter, group, pattern-match,
  │                                find_similar, conditional_query}
  │                                      │
  │            ┌─────────────────────────┼─────────────────────┐
  │            ▼                         ▼                     ▼
  │       Tier 3 Tensors           Derived Labels         Research API
  │       (.npy for training)      (TradeNet, RR, Exit,   (notebook access,
  │                                 Replay, RL)            SQL interface)
  └────────────────────────────────────────────────────────────────────

  ONE SOURCE OF TRUTH:
  Episode Projector → Episode Store → Everything derived

  NO DUPLICATED SIMULATION:
  The single forward walk happens inside the Projector.
  All downstream consumers read from the episode store.
```

### Episode Projector Detail

```
Inputs:
  - Ledger (append-only event log from production/backtest)
  - OHLCV data (same as runtime consumed)
  - Feature pipeline output (batch, per candle)
  - Generator config (entry parameters, exit policy for derived state)

Process:
  1. Read ledger events for a trade: entry, each candle tick, exit
  2. For each tick between entry and exit:
     a. Look up OHLCV observation from data
     b. Compute derived state (floating PnL, MFE, MAE, distances)
     c. Look up annotation (regime, structure, features) from batch output
     d. Append EpisodeStep to step list
  3. Compute provenance hashes
  4. Validate: checksum, reconstructability
  5. Write to Tier 1 store

Properties:
  - Deterministic: same inputs → same episode (byte-identical)
  - Re-runnable: can regenerate entire corpus with improved projector
  - Offline: no impact on runtime latency or behavior
  - Versioned: projector_version in provenance tracks which code produced it
```

---

## 9. Component Impact Matrix

| Component | Change Type | Complexity | Impact | Phase |
|---|---|---|---|---|
| **`src/research/episode.py`** (new) | Create | Low | Type definitions | 1 |
| **`src/research/episode_projector.py`** (new) | Create | **High** | Reconstructs episodes from ledger | 2 |
| **`src/research/episode_store.py`** (new) | Create | Medium | Parquet I/O, validation | 5 |
| **`src/research/event_engine.py`** (new) | Create | Medium | Deterministic event detection | 7 |
| **`src/research/policy_evaluator.py`** (new) | Create | Medium | Exit-policy-agnostic label computation | 3 |
| **`src/research/query_engine.py`** (new) | Create | Medium | DS/QL query layer over episodes | 8 |
| **`src/research/dataset.py`** (new) | Create | Medium | PyTorch/TF dataset wrappers | 8 |
| **`src/runtime/backtest_v2.py`** | Modify | Low | Ledger already exists; minor enrichment | 2 |
| **Phase5 calibration** | **No change** | — | Reads flat opportunities; unchanged | — |
| **Opportunity scanner** | Modify | Medium | Emit episodes via projector path | 4 |
| **Build trace corpus** | Modify | Low | Redirect to episode projector | 4 |
| **Production EngineRunner** | **No change** | — | Isolated | — |
| **All engine modules** | **No change** | — | Isolated | — |
| **All configs** | **No change** | — | Isolated | — |
| **All existing tests** | **No change** | — | New tests for episode code only | — |
| **`scripts/training/train_from_episodes.py`** (new) | Create | Medium | Sequence model trainer | 9 |

---

## 10. Files Requiring Modification

### Production Code (minimal, additive)

1. **`src/runtime/backtest_v2.py`**
   - No episode writing (the projector handles this offline)
   - Ensure the ledger (EngineEvent log + `crt_transitions.jsonl`) contains all fields the projector needs:
     - Entry: candle_index, timestamp, entry_price, SL, TP, direction, engine scores, CRT state
     - Per-candle: candle_index, OHLC, ATR, regime, state
     - Exit: candle_index, timestamp, exit_price, exit_reason
   - Most of this already exists in `EngineEvent` and `TradeRecord` — verification only

2. **`src/config_layer/crt_engine_v2.py`**
   - No changes needed (Trade dataclass remains as-is)
   - Ledger events already capture everything the projector needs

### Research Code (primary target)

3. **`src/research/episode.py`** (new) — Type definitions
4. **`src/research/episode_projector.py`** (new) — Ledger → Episode reconstruction
5. **`src/research/episode_store.py`** (new) — Tier 1/2/3 I/O
6. **`src/research/event_engine.py`** (new) — Deterministic event detection
7. **`src/research/policy_evaluator.py`** (new) — Exit policy label computation
8. **`src/research/query_engine.py`** (new) — Episode query DSL
9. **`src/research/dataset.py`** (new) — Training datasets
10. **`scripts/research/opportunity_scanner.py`** — Modify to emit episodes via projector path
11. **`scripts/research/build_trace_corpus.py`** — Modify to use episode projector
12. **`scripts/training/train_from_episodes.py`** (new) — Sequence model training

### Documentation

13. **`docs/architecture/opportunity-episode-platform-design.md`** (this document)

---

## 11. New Modules Required

| Module | File | Purpose |
|---|---|---|
| Episode types | `src/research/episode.py` | All dataclass definitions |
| Episode projector | `src/research/episode_projector.py` | Ledger → Episode reconstruction |
| Episode store | `src/research/episode_store.py` | Parquet I/O, validation, tier management |
| Event engine | `src/research/event_engine.py` | Deterministic event detection from steps |
| Policy evaluator | `src/research/policy_evaluator.py` | Exit-policy-agnostic label computation |
| Query engine | `src/research/query_engine.py` | DSL for episode filtering, pattern matching |
| Episode dataset | `src/research/dataset.py` | PyTorch/TF dataset wrappers |
| Training pipeline | `scripts/training/train_from_episodes.py` | Sequence model training |

---

## 12. Existing Modules That Remain Untouched

### Entire Production Spine
- `src/config_layer/crt_engine_v2.py` — Core engine logic (no changes needed)
- `src/engines/` — All engine modules (Fusion, Gaussian, ZoneGate, BitNet, RR, TradeNet)
- `src/strategies/` — Strategy orchestration
- `src/features/` — Feature pipeline (already produces per-candle features)
- `src/control_plane/` — Registry
- `src/runtime/` — Core runtime (backtest ledger already exists)
- `core/engine_runner.py` — Production runner

### Existing Research Scripts
- `scripts/training/phase5_calibration.py` — Continues reading flat opportunities
- `scripts/research/discover_zones.py` — Continues as-is
- All `qualify_*.py` scripts — No changes
- All `scripts/research/` scripts that read trace_corpus directly — No changes (old corpus remains readable)

### Infrastructure
- `configs/` — All configs
- `tests/` — All existing tests (new tests for episode code only)
- `data/` — Data files

---

## 13. Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|
| **Episode corpus is larger than expected** | **High** | High | **CORRECTED 2026-07-23:** the 10K × 30-step budget below assumed the spine population. The first corpus is `DETECTION_STREAM` — ~139,942 detections (F-022) × T=40 ≈ **5.6M steps**, "multi-GB raw if naively stored" (substrate §7). Observation-minimal Tier 1 + join-by-bar-index for features is mandatory, and a measured sizing gate runs on one instrument before the full build. |
| **Canonical episodes diverge from backtest results** | **High** | Medium | Episode projector must reconstruct from the same data the backtest used. Validation step: aggregate MFE/MAE from episode steps == backtest scalar MFE/MAE. Fail on mismatch. |
| **Projector adds no latency risk** | Low | Low | Projector is offline, scheduled. No runtime path impact. |
| **Schema migrations become painful** | Low | Low | Additive changes don't break readers. Breaking changes increment schema_version; old episodes remain readable. |
| **Storage sprawl from events + labels + tiers** | Low | Low | Events and labels are always derivable from Tier 1. Delete and re-derive on demand. |
| **Nested Parquet is slow to read** | Medium | Low | Use Tier 2 (flat) for queries, Tier 3 (tensors) for training. Nested is archival. |
| **Event detection logic diverges from real execution** | Medium | Low | Events are deterministic from steps. They are research labels, not execution signals. Policy Evaluator handles execution semantics. |
| **Ledger format changes** | Medium | Low | Ledger is append-only and backward-compatible. Episode projector reads the ledger schema version and adapts. |

---

## 14. Migration Roadmap

### Phase 1 — Episode Schema & Types [Low]
- Create `src/research/episode.py` with:
  - `OpportunityEpisode`, `EpisodeStep`, `EpisodeObs`, `EpisodeDerived`, `EpisodeAnnotation`
  - `OpportunityEntry`, `EpisodeProvenance`
  - `EpisodeEvent`, `PolicyLabels` (derived artifacts)
- Define all enums: `EpisodeType`, `EventType` (initial set)
- Unit tests: construction, serialization round-trip, checksum computation
- **Deliverable:** `src/research/episode.py` + tests

### Phase 2 — Episode Projector [High]
- Create `src/research/episode_projector.py`
- Read backtest ledger (EngineEvent logs + `crt_transitions.jsonl`)
- For each trade:
  1. Locate entry event → extract entry snapshot
  2. For each candle between entry and exit:
     - Look up OHLCV observation from data
     - Compute derived state (floating PnL, MFE, MAE, distances, drawdown)
     - Look up annotations (regime, structure) from batch feature output
     - Build `EpisodeStep` with `obs` + `derived` + `annotation`
  3. Compute provenance hashes (5 hashes, checksum)
  4. Validate reconstructability: `aggregate_from_steps == backtest_aggregate`
- Run as CLI: `python -m src.research.episode_projector --ledger logs/ --output results/episode_corpus/`
- **Deliverable:** `src/research/episode_projector.py` + validation tests

### Phase 3 — Policy Evaluator [Medium]
- Create `src/research/policy_evaluator.py`
- Implement initial exit policies:
  - `intrabar_fixed`: SL/TP fixed at entry (current default)
  - `trailing_stop`: trailing stop activated after 1R
  - `close_only`: exit only at candle close (no intrabar)
- Each policy is a pure function: `evaluate(episode, config) → PolicyLabels`
- Verify: labels from `intrabar_fixed` policy == existing backtest labels
- **Deliverable:** `src/research/policy_evaluator.py` + cross-validation

### Phase 4 — Scanner & Corpus Migration [Medium]
- Modify `scripts/research/opportunity_scanner.py`:
  - Forward walk currently in `_simulate()` → reuse projector path
  - Write episodes instead of flat records
  - Keep flat output for backward compatibility (controlled by `--episode-output` flag)
- Modify `scripts/research/build_trace_corpus.py`:
  - Redirect to episode projector
  - Write episodes alongside existing corpus
- **Deliverable:** Modified scanner and corpus builder; verified parity

### Phase 5 — Episode Store [Medium]
- Implement `src/research/episode_store.py`
- `EpisodeWriter`: Write episodes as nested Parquet
  - Schema enforced at write time
  - Partitioned by instrument/source/date
  - Compression: zstd
- `EpisodeReader`: Load by episode_id, instrument, date range
  - Supports lazy loading (metadata-only scan without step data)
- `validate_episode_corpus()`:
  - Checksum verification
  - Schema conformance
  - Reconstructability
- **Deliverable:** `src/research/episode_store.py` + tests

### Phase 6 — Derived Views [Medium]
- `FlatEpisodeWriter`: Derive flat Parquet from episodes
- `TensorEpisodeWriter`: Build padded tensors with configurable feature selection
- `EventStore`: Write events to Parquet
- `LabelStore`: Write labels to Parquet
- All readers operate on flat data for speed
- **Deliverable:** I/O layer complete; verified derivations

### Phase 7 — Event Engine [Medium]
- Implement `src/research/event_engine.py`
- One detector function per event type (pure, composable, testable):
  - `detect_reached_1r(steps) → list[int]` (step indices)
  - `detect_trail_activated(steps) → list[int]`
  - `detect_new_mfe(steps) → list[int]`
  - `detect_volatility_expansion(steps, threshold) → list[int]`
  - `detect_break_even_eligible(steps) → list[int]`
  - `detect_structure_break(steps) → list[int]`
- Event engine dispatches by version: `detect(episode, "v1")`
- Verify: events can be regenerated with v2 without touching episodes
- **Deliverable:** `src/research/event_engine.py` + tests

### Phase 8 — Query Engine & Research API [Medium]
- Implement `src/research/query_engine.py`
- DSL methods:
  - `filter(predicate_string)` — Python expression over episode fields
  - `find_similar(episode_id, k)` — k-NN by entry features
  - `group_by(field)` — group episodes by a metadata field
  - `aggregate(function)` — aggregate over filtered episodes
- SQL backend: query Tier 2 directly with DuckDB
- Implement `src/research/dataset.py`:
  - `EpisodeSequenceDataset`: yields `(entry_features, steps_tensor, mask, labels)`
  - `EpisodeFlatDataset`: yields `(episode_id, step_index, features, labels)`
- **Deliverable:** `src/research/query_engine.py`, `src/research/dataset.py` + integration tests

### Phase 9 — Training Integration [Medium]
- Create `scripts/training/train_from_episodes.py`
- Sequence model architectures:
  - Transformer encoder on step sequences
  - LSTM on step sequences
  - TCN on step sequences
- Multi-task header: outcome + MFE at exit + time to exit
- Configurable: which features, which labels, which architecture
- Validation: compare against existing flat-model baselines
- **Deliverable:** Training script + baseline comparison report

### Phase 10 — Consolidation [ongoing]
- Migrate TradeNet label generation → derive from episodes
- Migrate RR label generation → derive from episodes
- Migrate Exit model data generation → derive from episodes
- Remove duplicated forward-walk implementations one by one
- Each migration: run old and new in parallel; verify identical results; then switch
- **Deliverable:** Single forward-walk implementation; all models derive from episodes

---

## 15. Storage Model Recommendation

**All three tiers, with Tier 1 (nested episode Parquet) as the canonical truth.**

| Tier | Format | Purpose | When to use |
|---|---|---|---|
| **1: Canonical Episodes** | Nested Parquet | Immutable research truth | Write once per opportunity; read for all downstream work |
| **2: Flat Timestep View** | Flat Parquet | Analytics, SQL, pandas | Cross-episode queries, filtering, aggregation |
| **3: Tensor Store** | .npy/zarr | Training batches | High-performance model training, sequence models |

**Why not choose just one:**
- Tier 1 alone is slow for cross-episode queries (need to explode nested arrays)
- Tier 2 alone loses the sequence structure (need to group and order by step)
- Tier 3 alone is opaque (can't query episode metadata without another storage layer)
- All three are derivable from Tier 1, so storage overhead is only for the views you actually need

**Events and labels** are stored separately (Parquet), keyed by `(episode_id, version)`.

**Compression estimates (XAUUSD M15, 10K episodes, avg 30 steps):**

| Artifact | Uncompressed | Parquet (zstd) | Notes |
|---|---|---|---|
| Tier 1 (full, with features) | ~250 MB | ~40 MB | Includes 39-dim features per step |
| Tier 1 (no features) | ~80 MB | ~15 MB | obs + derived + annotation (no feature vector) |
| Tier 2 (flat) | ~350 MB | ~55 MB | Denormalized |
| Tier 3 (tensors) | ~200 MB | N/A | .npy direct |
| Events (per version) | ~5 MB | ~1 MB | Sparse — events at ~3 per episode |
| Labels (per policy) | ~1 MB | ~0.2 MB | One row per episode |

**Recommended default:** Tier 1 without per-step features by default. Features are looked up from the original `enriched_df` by global candle index when needed. Each step stores `obs` (OHLC + ATR) which is sufficient for most research, and the step's timestamp can join back to full feature vectors on demand. This saves ~85% storage on Tier 1.

---

## 16. Estimated Implementation Complexity

| Phase | Component | Complexity | Person-Days |
|---|---|---|---|
| 1 | Episode schema & types | Low | 1 |
| 2 | Episode projector | **High** | 4 |
| 3 | Policy evaluator | Medium | 2 |
| 4 | Scanner & corpus migration | Medium | 2 |
| 5 | Episode store | Medium | 2 |
| 6 | Derived views | Medium | 2 |
| 7 | Event engine | Medium | 2 |
| 8 | Query engine & research API | Medium | 3 |
| 9 | Training integration | Medium | 3 |
| 10 | Consolidation & migration | **High** | 3 |
| | **Total** | | **~24 person-days** |

### Complexity Breakdown by Risk

- **Low** (Phase 1): Pure data structures, no execution path changes. Safe to parallelize.
- **Medium** (Phases 3-9): New research code paths with controlled flags. Moderate testing burden.
- **High** (Phases 2, 10): Phase 2 is the critical infrastructure — must correctly reconstruct episodes from ledger. Phase 10 touches every downstream model to remove duplicated simulation.

---

## 17. Research Impact

| Subsystem | How it benefits from Episode Store |
|---|---|
| **TradeNet** | Train on actual MFE/MAE sequences instead of milestone labels. Use Policy Evaluator to generate labels under multiple exit policies without re-simulation. |
| **RR Engine** | Compute realized RR progression curves from episode.derived.unrealized_pnl_rr. Calibrate expected RR decay/acceleration across episode types. |
| **Exit models** | Train sequence-to-decision models: at each step, predict whether exiting now is optimal. Use Policy Evaluator labels as supervision. |
| **Dynamic SL** | Learn SL adjustment policy from episode context (volatility, drift, MFE/MAE asymmetry). SL moves become event types in the Event Engine. |
| **Partial TP** | Learn optimal partial exit timing from path structure. Policy Evaluator can simulate partial-TP policies on existing episodes. |
| **Break-even prediction** | Train classifier on event `BREAK_EVEN_ELIGIBLE`. Target derived from episode steps; no data regeneration needed. |
| **Confidence estimation** | Calibrate entry confidence from path progression. Early-confirming vs. late-confirming episodes have different step patterns. |
| **Sequence models** | **Critical dependency.** Transformers and LSTMs require `(batch, time, features)` tensors. Episodes provide this via Tier 3. |
| **Regime transition** | Study how within-trade regime changes correlate with outcome. Event engine detects `REGIME_TRANSITION` at exact step index. |
| **Replay Memory** | Store episodes indexed by entry feature similarity. Query Engine `find_similar()` retrieves trajectories. |
| **RL policy learning** | Episodes are MDP trajectories: `state (obs+derived) → action (hold/exit/partial) → reward (PnL delta)`. Policy Evaluator supplies reward. |
| **EnvelopeNet** | Episode `derived` contains floating MFE/MAE at every timestep — the exact training data for envelope prediction. |
| **Cross-policy research** | Same episode can be evaluated with intrabar_fixed, trailing, close-only, and experimental policies. Compare label distributions without re-simulation. |

---

## 18. Backward Compatibility Guarantees

### What must never change (production stability)

1. **`BacktestConfig` and all production config schemas** — Unchanged
2. **`CRTConfig` and CRT state machine transitions** — Unchanged
3. **`TradeRecord` CSV serialization (`to_csv_rows()`)** — Must continue producing the identical flat CSV
4. **`EngineRunner`, `FusionEngine`, `UltronRiskGate`, `DecisionEngine`** — Unchanged
5. **Live execution pipeline** — Unchanged (episodes are offline research artifacts)
6. **`CANONICAL_FEATURES` schema** — Unchanged
7. **`FeaturePipeline` output** — Unchanged
8. **Phase5 calibration input format** — Must continue accepting flat opportunities JSONL
9. **Existing backtest CSV consumers** — Unchanged (episode output is an additional format, not a replacement)
10. **All test assertions** — Unchanged (new tests are additive)
11. **Ledger format** — The EngineEvent log and crt_transitions.jsonl must remain stable. Episode projector reads them; any format change must be backward-compatible.

### What can change (research infrastructure)

1. **Episode schema** — Additive changes are non-breaking; breaking changes increment `schema_version`
2. **Event detection rules** — New event types are additive; existing event versions remain stable
3. **Policy evaluators** — New exit policies are additive; existing policies remain stable
4. **Query engine DSL** — Extensible by design
5. **Training pipelines** — `train_from_episodes.py` is new; existing training scripts unchanged
6. **Episode projector** — Improved versions produce different hashes but don't invalidate old episodes

### Contractual guarantee

> No change to the Episode Store, Projector, Event Engine, Policy Evaluator, or any associated code shall alter the behaviour, output, latency, or schema of any production module. Episode Store code lives exclusively in `src/research/` and `scripts/research/` — physically separated from the production spine. Any violation of this boundary is a P0 regression.

> The Episode Projector is an **offline** process. It reads the production ledger (append-only logs) and produces research artifacts. It never writes to production storage. It never runs in the production hot path.

---

*End of design document. See [`CLAUDE.md`](../../CLAUDE.md) for governance, [`model-design-intent.md`](model-design-intent.md) for architectural context, and [`envelope-layer-design.md`](envelope-layer-design.md) for the sibling operating-envelope specification.*