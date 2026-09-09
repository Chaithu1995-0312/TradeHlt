# Feature → State → Geometry → Outcome Lineage Census

**Date:** 2026-08-23
**Type:** Repository observability & persistence audit (point-in-time, `docs/analysis/` — not a living doc)
**Authority:** Research / governance observation only. No G001. Grants no authority (§6.5). No new F-id registered.
**Classification (§6.8):** `TEST / CONTRACT GAP` for the fold-completeness defect in §5.2; everything else `DORMANT BUT VALID` or `INSUFFICIENT EVIDENCE`.
**Scope:** what exists **today**. No architecture proposed, no schema proposed, no persistence added, no experiment run.

**Successor (identity, not storage):** 2026-08-23 Phase 1 froze *what a thing is* for these six layers in [`docs/governance/CANONICAL_LAYER_IDENTITY_CONTRACT.md`](../governance/CANONICAL_LAYER_IDENTITY_CONTRACT.md) (v1.0.0). This census remains the authority for *what exists on disk*. The identity contract is the authority for equality, lineage, immutability, versioning, and archive. Persistence is still not designed.

---

## 0. Repository decision in force

> **Feature Schema v5.0, canonical dimension 48, is the sole active canonical feature surface.**
> All prior feature dimensions (38, 39, and intermediate variants) are **legacy archives**.
> — User decision, 2026-08-23.

This census inventories legacy dimensions **for provenance only**. It does not describe, imply, or
leave room for multi-schema coexistence. A 38- or 39-dim corpus is archived historical evidence: it
can attest to what was measured then; it **cannot** be joined to the active 48-dim surface as if it
were current. That bound is load-bearing for §11 Q2 and Q5.

Not yet enforced in code: `feature_schema.py` still ships `SCHEMA_V3_FEATURE_DIM = 38` and
`SCHEMA_V4_FEATURE_DIM = 39` as compatibility sentinels. Those describe *archive compatibility*,
not active policy. Binding this decision into a tracked governance surface is a repository
modification requiring its own authorized turn (§3.3b) — **flagged, not done here.**

---

## 1. Method, and one caveat that governs the whole document

Verified by reading tracked source, and by inspecting artifacts on this machine's disk. Persistence
was **not assumed anywhere** — every "YES" below was confirmed against a real file.

### 1.1 The caveat: the entire lineage is untracked

```
git ls-files data    -> 0
git ls-files logs    -> 0
git ls-files results -> 0
```

`.gitignore` ignores `data`, `logs`, `results`, and `models/`. **Every artifact carrying any layer
of this lineage exists only on this machine.** From a clean clone, zero historical feature value,
feature state, CRT state, geometry, or outcome is recoverable.

This is the same class as F-071 (the committed repository was not the running system) and the
residue noted in F-083 (evidence citing `models/`/`results/` paths does not resolve). Every disk
observation in this document is therefore marked **[UNTRACKED]** and is **not reproducible from
another clone**. Where a claim rests on tracked source it is cited `path:line` and is reproducible.

### 1.2 Layer numbering

`L0 OHLC → L1 Feature Values → L2 Feature States → L3 CRT States → L4 Geometry → L5 Outcome`.

---

## 2. Census table

| Layer | Produced By | Persisted? | Storage Location | Authoritative? | Reconstructable? |
|---|---|---|---|---|---|
| **L0 OHLC** | MT5 fetch / vendor CSV | **YES** [UNTRACKED] | `data/mt5/{INST}_{TF}.csv`, `data/{INST}_M15.csv` | **YES** — root source of truth | n/a (root) |
| **L1 Feature Values** | `FeaturePipeline` (`src/features/feature_pipeline.py`) — **writes nothing**, pure transform | **PARTIAL** [UNTRACKED] | active v5.0/48: `logs/feature_snapshots.jsonl`, `results/research/bar_matrix/XAUUSD_M15/bar_matrix.csv`. Archive: `clean_labels.jsonl` (38), `opportunities.jsonl` (39) | NO — derived | **YES**, deterministically, *by the current code only* |
| **L2 Feature States** | `FeatureStateEncoder` (`src/features/feature_states.py`) | **PARTIAL** [UNTRACKED] | **one file**: `bar_matrix.csv` `state__*` (19 families, XAUUSD M15, single build 2026-08-20) | NO — derived, shadow-only | **YES**, from L1 + ontology |
| **L3 CRT States** | `CRTEngine._transition` (`src/config_layer/crt_engine_v2.py:1022`) | **PARTIAL** [UNTRACKED] | run-scoped `{INST}_events.jsonl` (fold-complete); global `logs/crt_transitions.jsonl` (**not** fold-complete) | **YES** — engine is execution authority | **YES** from a run-scoped event log; **NO** from the global stream alone |
| **L4 Geometry** | `Trade` (`crt_engine_v2.py:202`), `ExecutionPlannerV1_2`, oracle geometries | **PARTIAL** [UNTRACKED] | `{INST}_trades.csv`, `oracle_labels/labels.csv`, `clean_labels.jsonl`, episode `EntrySnapshot` | **YES** where written (the realized levels) | **PARTIAL** — levels yes; trail/BE/partial trajectory **NO** |
| **L5 Outcome** | `forward_walk` / `multi_tp_walk` / backtest ledger | **YES** [UNTRACKED] | `{INST}_trades.csv`, `labels.csv`, `clean_labels.jsonl`, `opportunities.jsonl` | **YES** for ledger + walk kernels; **NO** for `opportunities.jsonl` (F-022) | **YES**, from L0 + L4 |

**Read the PARTIALs precisely.** They do not mean "some rows are missing". They mean *the layer is
persisted for one instrument, or one program, or one run family, and nowhere else* — detailed per
layer below.

---

## 3. Feature Value Audit (L1)

### 3.1 Active canonical surface

| Question | Answer |
|---|---|
| Canonical vector location | `CANONICAL_FEATURES` / `CANONICAL_FEATURE_ORDER`, `src/features/feature_schema.py` |
| Schema authority | `market_ontology.yaml` for *meaning* (§6.6); `feature_schema.py` for *order and dimension* |
| Active dimension | **48** (`CANONICAL_FEATURE_DIM`, schema v5.0) |
| Serialization path | none in the producer — `FeaturePipeline` returns a DataFrame and **writes no file** (grep for `to_csv` / `to_parquet` / `open(...,'w')` / `append_jsonl` in `feature_pipeline.py` returns nothing). Every persisted copy is written by a *consumer*. |

Persisted copies of the **active** surface, both [UNTRACKED]:

| Artifact | Rows | Carries | Provenance stamp |
|---|---|---|---|
| `logs/feature_snapshots.jsonl` (1.20 GB, 824,471 lines) | one per **scored decision**, not per bar | 48 canonical + `timestamp` + `_data_integrity` (50 keys observed on the tail record) | envelope `schema_hash` only; `instrument` is `""`; no `run_id` |
| `results/research/bar_matrix/XAUUSD_M15/bar_matrix.csv` (57.6 MB) | 47,197 (one per bar) | 48 canonical + pipeline intermediates + L2 + L3, 124 columns | **full manifest** — see §3.3 |

### 3.2 Legacy archive (provenance only — no coexistence)

| Artifact | Dim | Self-declaring? | Notes |
|---|---|---|---|
| `results/clean_labels/XAUUSD/20260723T083443Z/clean_labels.jsonl` (299 MB, 94,332 rows) | **38** | **YES** — `provenance.feature_dim: 38` on every record | ARCHIVE. Also self-declares `pit_status: PIT_UNCLEAN_STORED_FEATURES` |
| `logs/XAUUSD/xauusd_phase1_20260723/opportunities.jsonl` (127 MB) | **39** | **NO** | ARCHIVE. Dim recoverable only by counting keys |

The `opportunities.jsonl` case is the worst shape an archive can take. `opportunity_scanner.py:210`
writes `features = {col: float(row[col]) for col in CANONICAL_FEATURES}` — i.e. whatever
`CANONICAL_FEATURES` happened to be at scan time — and its `run_header`
(`opportunity_scanner.py:187-194`) is `{type, run_id, instrument, started_at}` only. Nothing in the
file records which schema produced it. **A non-self-declaring archive can be silently mistaken for
the active surface**, which is precisely the failure the §0 decision exists to prevent.

### 3.3 The one artifact with real provenance

`bar_matrix/manifest.json` pins: `corpus_sha256`, `schema_version: "5.0"`, `schema_hash`,
`feature_order_hash`, `canonical_dim: 48`, `magnitude_window`, `htf_candles_per_range`,
`breakout_disp_threshold`, `normalization_basis: atr_relative`,
`session_timestamp_basis: broker_local`, `parent_crt_enabled: true` — plus an explicit
`known_contaminated_inputs` block naming the F-066 session-basis mislabel and the F-061 FM-022/023
saturation. This is the only artifact found that declares its own contamination.

### 3.4 Can every historical feature value be recovered exactly?

**NO.** Three distinct loss points:

1. **Coverage.** The active surface is persisted for exactly one instrument at bar granularity
   (XAUUSD M15, one build). `feature_snapshots.jsonl` is decision-cadence, not bar-cadence, so it
   cannot reconstruct a per-bar series for any instrument.
2. **Attribution.** `feature_snapshots.jsonl` carries `instrument: ""` and no `run_id`, so a row
   cannot be attributed to an instrument or a run. Its only usable stamp is the envelope
   `schema_hash`, which is a *passive* drift detector no runtime path checks
   (`src/events/event_fabric.py`, invariant 4) — observed drifting mid-file from
   `235553310100a340` (head) to `160c96c52b198a16` (tail).
3. **Schema identity on archives.** Per §3.2, the 39-dim corpus does not record its own schema.

**Recovery by recompute is possible but is not recovery.** `FeaturePipeline` is deterministic given
the same OHLC and config, so today's code can regenerate an L1 surface. That reproduces *today's*
definitions, not the ones that existed when a historical finding was drawn — the exact substitution
this census was commissioned to detect. F-046, F-050, F-061, F-063, F-066 and F-072 each changed a
feature identity or its normalization, so recompute is known to be non-identity across epochs.

---

## 4. Feature State Audit (L2)

`FeatureStateEncoder` interprets values into ontology-declared states. Its own module docstring is
decisive on placement: *"NOT on the decision path. Shadow-only: nothing on the spine consumes this
output."*

**Declared coverage (enumerated from the live encoder):** 19 stateful families — **13 vector-bound**,
6 not bound to a canonical slot. **35 of the 48 active canonical slots have no declared state at
all** (`continuous_features`). So the L2 layer, even when fully computed, interprets 13/48 of the
active vector.

| Feature State | Persisted? | Recomputed? | Storage Location |
|---|---|---|---|
| `double_sweep` *(vector-bound)* | PARTIAL | YES | `bar_matrix.csv` `state__double_sweep` |
| `trend_bias` *(vector-bound)* | PARTIAL | YES | `bar_matrix.csv` `state__trend_bias` |
| `sweep_detected` *(vector-bound)* | PARTIAL | YES | `bar_matrix.csv` `state__sweep_detected` |
| `liquidity_sweep` *(vector-bound)* | PARTIAL | YES | `bar_matrix.csv` `state__liquidity_sweep` |
| `break_of_structure` *(vector-bound)* | PARTIAL | YES | `bar_matrix.csv` `state__break_of_structure` |
| `swing_high` *(vector-bound)* | PARTIAL | YES | `bar_matrix.csv` `state__swing_high` |
| `swing_low` *(vector-bound)* | PARTIAL | YES | `bar_matrix.csv` `state__swing_low` |
| `higher_high` *(vector-bound)* | PARTIAL | YES | `bar_matrix.csv` `state__higher_high` |
| `lower_low` *(vector-bound)* | PARTIAL | YES | `bar_matrix.csv` `state__lower_low` |
| `volatility_regime` *(vector-bound)* | PARTIAL | YES | `bar_matrix.csv` `state__volatility_regime` |
| `session` *(vector-bound)* | PARTIAL | YES | `bar_matrix.csv` `state__session` — manifest declares this input contaminated (F-066) |
| `volume_spike` *(vector-bound)* | PARTIAL | YES | `bar_matrix.csv` `state__volume_spike` — see F-065: declared twice, consumed by neither |
| `change_of_character` *(vector-bound)* | PARTIAL | YES | `bar_matrix.csv` `state__change_of_character` |
| `rsi_state` *(non-vector)* | PARTIAL | YES | `bar_matrix.csv` `state__rsi_state` |
| `displacement_flag` *(non-vector)* | PARTIAL | YES | `bar_matrix.csv` `state__displacement_flag` |
| `retest_flag` *(non-vector)* | PARTIAL | YES | `bar_matrix.csv` `state__retest_flag` |
| `atr_magnitude` *(magnitude band)* | PARTIAL | YES | `bar_matrix.csv` `state__atr_magnitude` |
| `body_commitment` *(magnitude band)* | PARTIAL | YES | `bar_matrix.csv` `state__body_commitment` |
| `momentum_magnitude` *(magnitude band)* | PARTIAL | YES | `bar_matrix.csv` `state__momentum_magnitude` |

Every row reads PARTIAL for the same reason: **one file, one instrument, one timeframe, one build.**
No other artifact in the repository persists a feature state.

### 4.1 Can historical feature-state identity be recovered without replay?

**NO, except for XAUUSD M15 at the 2026-08-20 build.** Everywhere else the layer is **ephemeral** —
it is computed in memory by a research script and discarded.

Two further constraints even where it *is* persisted:

- The magnitude families (`atr_magnitude`, `body_commitment`, `momentum_magnitude`) are ranked by
  `MagnitudeStateEncoder` against a **trailing window** (`magnitude_window: 200`). The state is
  therefore a function of the window, and re-deriving with a different window silently yields
  different states. The window is recorded in the manifest — which is why that manifest matters.
- Re-deriving states requires the ontology *as it was*. The ontology is tracked and versioned, so
  this is recoverable in principle via git — the only layer in this census for which that is true.

---

## 5. CRT State Audit (L3)

`CRTState` declares **12** members: `RANGE, SHADOW_PENDING, SWEEP, DISPLACEMENT, EXPANSION, EXPIRED,
RETEST, EXECUTION, RESOLUTION` (the M15 machine) plus `RANGE_C1, MANIPULATION_C2, DISTRIBUTION_C3`
(the F-075 parent-CRT disjoint sub-graph, carried on `parent_state`, not the M15 machine).

State is assigned at **exactly one site** — `crt_engine_v2.py:1022`, inside `_transition()` — and
the event is recorded immediately before the assignment (`:1000-1019`). That single funnel is what
makes the layer auditable at all.

### 5.1 Per-state persistence

Observed on `results/research/_spine_entries/XAUUSD__v2_multi_2026_04/run_20260822_162108_XAUUSD`
[UNTRACKED]. `state_to` counts folded from `XAUUSD_events.jsonl` match the independent
`TRANSITION_COUNTER` telemetry record **exactly** — an independent cross-check that the run-scoped
event stream is complete for state entry.

| CRT State | Persisted? | Recomputed? | Storage Location | Observed count |
|---|---|---|---|---|
| `RANGE` | YES (run-scoped) | YES | `{INST}_events.jsonl` (`RESET` + `STATE_TRANSITION`) | 2,887 |
| `SWEEP` | YES (run-scoped) | YES | `{INST}_events.jsonl` | 1,798 |
| `DISPLACEMENT` | YES (run-scoped) | YES | `{INST}_events.jsonl` | 399 |
| `EXPANSION` | YES (run-scoped) | YES | `{INST}_events.jsonl` | 148 |
| `RETEST` | YES (run-scoped) | YES | `{INST}_events.jsonl` | 24 |
| `EXECUTION` | YES (run-scoped) | YES | `{INST}_events.jsonl` | 4 |
| `SHADOW_PENDING` | YES (run-scoped) | YES | `{INST}_events.jsonl` | 6 |
| `RESOLUTION` | YES (run-scoped) | YES | `{INST}_events.jsonl` | 3 |
| `EXPIRED` | YES *(mechanism)* | YES | `{INST}_events.jsonl` | **0 in this run** — TTL branch not exercised |
| `RANGE_C1` / `MANIPULATION_C2` / `DISTRIBUTION_C3` | **NO** | YES | not emitted to the M15 event stream — parent dimension (F-075/F-089) | n/a |

### 5.2 The two CRT streams are not equivalent — and one is wrong

This is the sharpest defect the census found.

**Run-scoped `results/**/{INST}_events.jsonl` is fold-complete.** It carries both `STATE_TRANSITION`
(`crt_engine_v2.py:1000`) and `RESET` (`reset_to_range`, `crt_engine_v2.py:1871-1877`), each with
`state_from` and `state_to`. Folding the ordered stream reconstructs the per-bar state series
**without replaying the engine**.

**Global `logs/crt_transitions.jsonl` is not.** At 2.59 GB / 4,741,789 lines it is by far the
largest CRT artifact, and it is unusable for state reconstruction:

- `_emit_enveloped` (`crt_engine_v2.py:347-366`) returns early unless
  `ev.event == "STATE_TRANSITION"`. **Every RESET is dropped.**
- Verified empirically on a 200,000-row sample: 100% `STATE_TRANSITION`, **0 `RESET`**.
- Resets dominate. In the `B_baseline` run [UNTRACKED] the event log holds **11,024 RESET** against
  3,914 `STATE_TRANSITION`; in the spine run above, 2,887 against 2,382. Folding transitions alone
  therefore yields a **wrong** state series, not a partial one — the machine appears never to
  return to `RANGE`.
- It is also **unattributable**: the emit hardcodes `instrument=""` (observed `""` on
  200,000/200,000 rows), and carries no `run_id`, no `config_version`. Every run since 2026-05-29 is
  interleaved into one file with no separator.

**Both emits are conditional and fail-open.** `_transition` records only `if ev_logger and candle`
(`:1000`); `_emit_enveloped` swallows all exceptions (`:365-366`). An unlogged transition is
indistinguishable from no transition — the same silent-gap class as F-056, F-079, F-083 and F-085.

### 5.3 The resolver is a different object — do not treat it as recovered engine state

`bar_matrix.csv` carries a `crt_state_resolved` column, produced by `CRTStateResolver`
(`src/features/crt_state_resolver.py`), which resolves states declaratively from feature states. It
is **not** the engine. Its own header says so: *"the CRT engine remains the execution authority."*
It has **no consumer in `src/`** — only `scripts/research/`.

F-069 measured agreement at **88.16%** and found the residual to be a divergent construction
(Category C, 96.1% of mismatched bars), not a mistuned threshold. The `bar_matrix` manifest's
`crt_state_distribution` confirms the gap concretely: **only 5 states appear** — `RANGE 21745`,
`SWEEP 15186`, `DISPLACEMENT 3127`, `SHADOW_PENDING 47`, `EXPANSION 7092` — with **no `RETEST`, no
`EXECUTION`, no `RESOLUTION`, no `EXPIRED`**. The resolver's `EXECUTION` branch is structurally
unreachable on real data.

**Consequence:** the only artifact that carries L1+L2+L3 on one aligned surface carries a *resolver*
L3, so joining an outcome to `crt_state_resolved` is not joining it to the state the engine was in.

### 5.4 Can historical CRT state identity be recovered without replay?

**PARTIAL — and only where a run-scoped event log survives on this disk.**

- **YES** for any run whose `{INST}_events.jsonl` still exists: fold `STATE_TRANSITION` + `RESET`.
- **NO** from `logs/crt_transitions.jsonl`, for the reasons in §5.2.
- **NO** for any run whose output directory has been deleted — nothing else records it.
- **NO** for the live path: there is no production live rail (F-073), and `logs/live_rail.jsonl`
  shows the paper caller rejecting bars (`FEATURE_REJECT`, 29 canonical keys missing) consistent
  with F-085.

---

## 6. Geometry Audit (L4)

| Geometry Component | Persisted? | Reconstructable? | Where |
|---|---|---|---|
| Entry | **YES** | YES | `{INST}_trades.csv` `entry_raw` + `entry_fill`; `labels.csv` `entry`; `clean_labels` `entry`; `EntrySnapshot.entry_price` |
| SL | **YES** | YES | `trades.csv` `sl`; `labels.csv` `sl`; `clean_labels` `sl`; `EntrySnapshot.sl_price` |
| TP1 | **YES** | YES | `trades.csv` `tp1`; `labels.csv` `tp1`; `clean_labels` `tp1` |
| TP2 | **PARTIAL** | YES | `trades.csv` `tp2`; `labels.csv` `tp2`; `clean_labels` `tp2` (**observed `null`** on the sampled row — policy `STRETCH_3R_BEFORE_SL` defers it). Episode `EntrySnapshot` carries a **single** `tp_price`, so the two-target shape is lost there |
| RR | **PARTIAL** | YES | not a stored column on `trades.csv`; `Trade.risk_reward_tp1` is a computed property (`crt_engine_v2.py:226`). `clean_labels` stores `tp1_reward_mult`; `labels.csv` stores `tp1_mult` |
| Risk distance | **PARTIAL** | YES (`abs(entry - sl)`) | stored explicitly on `labels.csv` and `clean_labels`; **not** a column on `trades.csv` |
| Partial exits | **NO** | PARTIAL | no per-trade partial ledger anywhere. `Trade.partial_pnl` is in-memory only; the 50% TP1 close is a **parameter**, not a record |
| Trail logic | **NO** | PARTIAL | no per-trade trail trace. The half-way stop reassignment lives in `ExecutionEngine.update_trade` and is replayed, never stored |
| BE moves | **NO** | PARTIAL | no BE event stream. Note the naming trap retained by F-088: `partial_tp_breakeven_enabled` **does not do breakeven** |

### 6.1 Can the exact geometry used for a historical trade be recovered?

**The levels, YES. The trajectory, NO.**

`{INST}_trades.csv` is the richest single row in the repository: identity, direction, `entry_raw`,
`entry_fill`, `sl`, `tp1`, `tp2`, `exit_fill`, `exit_reason`, timestamps, PnL in pips and R (raw and
net), slippage, spread, capital before/after, position size, risk score, session/day/hour, `htf_id`,
`candle_idx`, the flattened canonical feature dict, live audit columns (`live_atr`, `live_ema_*`,
`cached_*`), BitNet audit columns, and — crucially — **`config_version`**. It is the only lineage
artifact that stamps the governing config on every row.

What it does not record is what happened *between* entry and exit: whether TP1 filled and when, where
the stop was reassigned to, how the trail moved. Those are reconstructed by re-running a walk kernel
against L0 — which is exactly F-088's finding, that `forward_walk` had been silently walking a
*simpler trade object* (one TP, no partial, no trail) than production trades, closed only by
`multi_tp_walk` (SEM-017).

Two further gaps:

- **`ExecutionPlannerV1_2` persists nothing.** It returns a plan dict (`execution_planner.py:287`)
  with `execution_id`, `entry_price`, TTL and a `trace`, and no code path writes it. Live planned
  geometry is entirely ephemeral — moot today only because there is no production live rail (F-073).
- **`logs/trade_journal.jsonl` does not exist on disk.** `TradeLogger` targets it, but the
  `TradeRecord` it would write (`src/journal/schema.py`) carries **no geometry at all** — no entry,
  no SL, no TP — only `result`, `pnl`, `duration_candles`. The journal layer is coded but unwritten,
  and would not close this gap if it were.

---

## 7. Outcome Audit (L5)

| Field | Storage | Authoritative source |
|---|---|---|
| `outcome` | `trades.csv` `exit_reason`; `labels.csv` `outcome`/`exit_kind`; `clean_labels` `path_outcome`; `opportunities.jsonl` `outcome` | walk kernel or ledger — **never** `opportunities.jsonl` (F-022) |
| `mfe` / `mae` | `labels.csv`, `clean_labels` (`y_mfe_r`, `y_mae_r_heat`, `path_*`), `opportunities.jsonl` | `TradePathStats` (`backtest_v2.py:253`) in the ledger; `forward_walk` is its verifying oracle |
| `rr` | `trades.csv` `pnl_rr_raw`/`pnl_rr_net`; `labels.csv` `y_R_gross`/`y_R_net`; `clean_labels` `y_R_net` | ledger / walk kernel |
| `pnl` | `trades.csv` `pnl_pips_raw`/`pnl_pips_net`, `capital_before`/`capital_after` | ledger only |
| `duration` | all four corpora (`duration_candles` / `y_holding_bars`) | ledger / walk kernel |
| `time_to_tp` | `labels.csv` `bars_to_tp1`; `clean_labels` `path_time_to_tp`, `y_time_to_1r` | walk kernel |
| `time_to_sl` | **NO dedicated field.** `clean_labels` `path_time_to_failure` is the nearest | walk kernel |

**Authoritative source overall:** the walk kernels (`forward_walk`, `multi_tp_walk`) and the backtest
ledger. `opportunities.jsonl`'s `outcome`/`rr_achieved` are **not** authoritative — F-022 measured
only 36.8% self-consistency, and `opportunity_scanner.py` states outright that *"CRT is intentionally
NOT consulted"*: it is a synthetic every-bar toy-trade stream with its own fixed ATR-multiple
geometry and a 0.5R trailing stop, not a record of any trade the system took.

### 7.1 The three join questions

**Can outcomes be linked back to geometry? — YES.** Every outcome-bearing corpus carries its own
geometry on the same row. This is the strongest edge in the whole lineage.

**Can outcomes be linked back to states? — NO (feature states); PARTIAL and indirect (CRT states).**
No corpus carries a feature state and an outcome on the same row. `bar_matrix.csv` (states) and
`labels.csv` (outcomes) do join on `_pos`, for XAUUSD M15 only — but that gives the **resolver's**
L3 (§5.3), not the engine's. For engine CRT state the only path is timestamp-matching a
`{INST}_trades.csv` row against the same run's `{INST}_events.jsonl`, which works **only when both
files from the same run still exist on this disk.**

**Can outcomes be linked back to feature values? — YES, within a corpus; NO across the active
surface.** `trades.csv` flattens the feature dict onto the trade row; `clean_labels` carries
`feature_vector` beside its labels; `bar_matrix`↔`labels.csv` join on `_pos`. But the two corpora
that pair outcomes with features at scale (`clean_labels` 38-dim, `opportunities` 39-dim) are
**legacy archives** under §0. They attest to what was measured then; they cannot be joined to the
active 48-dim surface as if current.

---

## 8. Lineage graph (as it actually is)

```
                    L0  OHLC  [data/mt5/*.csv - UNTRACKED]
                          |
                          |  DIRECT        (FeaturePipeline, deterministic, writes nothing)
                          v
                    L1  Feature Values
                          |
                          |  DIRECT        (bar_matrix.csv only: 1 instrument, 1 build)
                          |  RECONSTRUCTED (everywhere else - recompute, not recovery)
                          v
                    L2  Feature States
                          |
                          |  MISSING       <-- the engine does NOT consume feature states
                          x
                    L3  CRT States
                          ^
                          |  DIRECT        (engine reads OHLC + its own internals, not L2)
                          |
                    L0 ---+  ......................... the real edge

    L3 --> L4   DIRECT        (run-scoped events; IMPLICIT via the global stream - see 5.2)
    L4 --> L5   DIRECT        (same row in trades.csv / labels.csv / clean_labels)
    L1 --> L4   IMPLICIT      (trades.csv flattens features onto the trade row)
    L2 --> L5   MISSING       (no artifact pairs a feature state with an outcome)
    L3 --> L5   RECONSTRUCTED (timestamp-match trades.csv against same-run events.jsonl)
```

| Edge | Mark | Justification |
|---|---|---|
| L0 → L1 | **DIRECT** | `FeaturePipeline` is deterministic given OHLC + config; the CSV is the declared input |
| L1 → L2 | **DIRECT** for XAUUSD M15 / **RECONSTRUCTED** elsewhere | one persisted artifact; every other path recomputes in memory |
| **L2 → L3** | **MISSING** | **The declared chain does not exist.** The engine does not consume feature states. `CRTStateResolver` is the only code that does, and it is research-only, has no `src/` consumer, and diverges from the engine (F-069) |
| L0 → L3 | **DIRECT** | the real edge — the engine reads candles and its own internal geometry |
| L3 → L4 | **DIRECT** (run-scoped) / **IMPLICIT** (global) | `TRADE_OPENED` and the trade row share a run; the global stream cannot attribute a run at all |
| L4 → L5 | **DIRECT** | same row, every outcome corpus |
| L1 → L4 | **IMPLICIT** | features are copied onto the trade row at build time (`Trade.cached_features`), not linked by key |
| L2 → L5 | **MISSING** | no artifact carries both |
| L3 → L5 | **RECONSTRUCTED** | requires two surviving files from the same run and a timestamp match |

**The headline of this section:** the `L2 → L3` edge in the requested lineage **does not exist in
this repository.** Feature States are a shadow layer that nothing downstream reads. CRT states are
derived from OHLC and engine-internal geometry directly.

---

## 9. Persistence risk assessment

| Layer | Risk | Justification |
|---|---|---|
| **L0 OHLC** | 🟡 **YELLOW** | Content is stable and content-addressable (`corpus_sha256` in one manifest), but **untracked** — not recoverable from a clean clone, and no repository-level pin ties a finding to a corpus hash |
| **L1 Feature Values** | 🟡 **YELLOW** | Deterministically reconstructable *by current code*, but that is recompute, not recovery: F-046/050/061/063/066/072 each changed a feature identity, so a re-derived vector is not the historical one. Active surface persisted for one instrument, one build. Untracked |
| **L2 Feature States** | 🔴 **RED** | **Ephemeral.** One file, one instrument, one timeframe, one build, untracked. Everywhere else the layer is computed in memory and discarded. Magnitude bands additionally depend on a trailing window, so a re-derivation with a different window silently differs. Mitigation: the ontology is tracked, so the *rules* are recoverable even where the values are not |
| **L3 CRT States** | 🔴 **RED** | Historical identity survives **only** in gitignored per-run directories. The one global, always-on stream is fold-incomplete (drops every RESET, §5.2) and unattributable (`instrument: ""`, no run_id). Both emits are conditional and fail-open. Delete a run directory and that run's state history is gone with no second copy |
| **L4 Geometry** | 🟡 **YELLOW** | Realized levels are well persisted and `trades.csv` even stamps `config_version`. But partial/trail/BE **trajectory** is never stored — it is replayed, which is exactly the substitution F-088 caught. Planner output is never persisted at all. Untracked |
| **L5 Outcome** | 🟡 **YELLOW** | Well persisted across four corpora with the geometry that produced it. Downgraded from GREEN only because (a) untracked, and (b) the largest outcome corpus (`opportunities.jsonl`) is not authoritative (F-022) and does not say so in-band |

**No layer is GREEN.** Under §1.1 no layer can be — GREEN requires preserved historical identity, and
nothing in this lineage is tracked. Even setting tracking aside, L2 and L3 would remain RED on their
own merits.

---

## 10. Parquet: what it is today

`src/utils/parquet_store.py` is unambiguous in its own docstring: **JSONL is the system of record;
a Parquet projection is a derived, regenerable sidecar.** `iter_records` falls back to JSONL
whenever the projection is `STALE`, `ABSENT` or `UNAVAILABLE`, so a projection *can never serve data
its source does not contain*. The manifest pins source size/mtime/sha256 to enforce that.

Projections that exist on disk — **four**, all XAUUSD, all [UNTRACKED]:

| Projection | Source |
|---|---|
| `logs/XAUUSD/xauusd_phase1_20260723/opportunities.parquet` | `opportunities.jsonl` (legacy 39-dim archive) |
| `results/clean_labels/XAUUSD/20260723T083443Z/clean_labels.parquet` | `clean_labels.jsonl` (legacy 38-dim archive) |
| `.../run_20260822_162108_XAUUSD/XAUUSD_crt_telemetry.parquet` | telemetry, partitioned by `kind` |
| `.../run_20260822_162108_XAUUSD/XAUUSD_events.parquet` | run CRT events, partitioned by `event` |

`pyarrow 25.0.1` is installed now, but the `bar_matrix` build (2026-08-20) recorded
`parquet_skipped_reason: "Unable to find a usable engine"` — so which artifacts have projections is
a function of which interpreter happened to run, not of any policy.

---

## 11. Final questions — answered explicitly

### Q1. Is Parquet currently a Feature Store or a Semantic Replay Store?

**Neither. It is a compression-and-column-pruning sidecar over four JSONL files.**

It is not a Feature Store: it holds no feature registry, serves no point lookups, has no online/
offline symmetry, and two of its four projections are legacy-archive corpora. It is not a Semantic
Replay Store: it stores no state layer, no lineage keys, and no cross-layer joins — `XAUUSD_events`
is the closest, and that is one run's CRT event log partitioned by event type. By construction it
can only ever be a *projection* of a JSONL source, never an authority.

### Q2. Can a historical outcome be traced all the way back to the exact feature-state surface that existed when it was generated?

**NO.** The chain breaks in three independent places, any one of which is sufficient:

1. **No artifact pairs a feature state with an outcome** (§7.1). The `L2 → L5` edge is MISSING.
2. **Feature states were never persisted** for any run that produced a historical finding (§4.1) —
   `bar_matrix.csv` is a single XAUUSD build from 2026-08-20 and post-dates essentially every
   registered finding.
3. **Nothing is tracked** (§1.1), so "the surface that existed when it was generated" has no
   repository-level referent at all.

Under §0 there is a fourth, decisive bound: the two corpora that *do* pair features with outcomes at
scale are 38- and 39-dim **legacy archives**. They record what was measured then; they cannot be
joined to the active 48-dim surface as if current.

The closest attainable trace today is: outcome → geometry → run → *engine* CRT state (by timestamp
match, if both run files survive) → **recomputed** feature values. That is replay, not recovery.

### Q3. Which semantic layers are ephemeral?

- **Feature States (L2) — fully ephemeral** outside one XAUUSD build. The declared layer exists in
  code, is shadow-only by its own docstring, and is discarded on every other path.
- **Geometry *trajectory* (partial fills / trail / BE) — fully ephemeral.** Only endpoints survive.
- **Planned geometry (`ExecutionPlannerV1_2` output) — fully ephemeral.** Never written.
- **CRT States (L3) — conditionally ephemeral.** Durable while a run directory survives; the global
  fallback stream cannot substitute (§5.2). Both emit paths are fail-open, so a write failure is
  invisible.
- **Feature Values (L1) — ephemeral at bar granularity** for every instrument except XAUUSD M15.

### Q4. What is the largest observability gap?

**That a skipped or dropped write is indistinguishable from an absent one — now demonstrated on the
CRT state layer itself.**

`logs/crt_transitions.jsonl` is the system's only always-on, global CRT stream. At 2.59 GB and 4.7M
rows it *looks* like the authoritative state history. It is not: it drops every RESET, so a fold
over it reports a machine that never returns to RANGE (11,024 dropped resets against 3,914
transitions in one measured run). It additionally cannot name its own instrument, run, or config.
Nothing anywhere compares it to the run-scoped log that *is* complete.

This is the same failure class the repository has now caught five times — F-056 (a strict-read
constant then discarded), F-079 (an absent key instead of a status), F-083 (a sealed contract
declaring a measurement the run never executed), F-085 (a fail-closed guard made unreachable by a
missing `global`), F-088 (a kernel walking a simpler trade object than its name implied). This is
the sixth instance, and the first on the state layer.

**Runner-up:** the `L2 → L3` edge does not exist (§8). The lineage this census was asked to inventory
assumes CRT states are derived from feature states. In this repository they are not — the engine
reads OHLC directly, and the only code that resolves states from feature states is research-only and
diverges from the engine by ~12% (F-069).

### Q5. What minimum persistence additions are required to support future finding revalidation?

Per the constraints, **this is stated as a gap list, not a design.** No schema, no storage layout, no
architecture is proposed. Ordered by how much revalidation each unblocks:

1. **Tracked provenance for any corpus a finding cites.** Not the corpus — a corpus identity. Today
   a finding's evidence path resolves on one machine and nowhere else (§1.1). Until an evidence
   citation can be resolved from a clean clone, no revalidation is verifiable by anyone else.
2. **Fold-completeness for the global CRT stream** (or an explicit contract that it is transitions-
   only, plus a guard that fails when someone folds it as if complete). Today the defect is silent.
3. **Run attribution on the always-on streams.** `instrument`, `run_id`, `config_version` are all
   available at the emit sites and all currently discarded (`instrument=""`).
4. **A schema stamp on every persisted feature surface.** `clean_labels` shows the pattern already
   works; `opportunities.jsonl` shows what its absence costs (§3.2). Under §0 this is what keeps an
   archive filed as an archive.
5. **Geometry trajectory, if and only if a finding depends on it.** F-088 shows the cost of not
   having it. It is listed last deliberately — the trajectory is currently *reconstructable*, so
   this is the only item here that is an optimization rather than a correctness gap.

Items 1–4 are correctness gaps: without them, a revalidation cannot establish that it measured the
same thing the original finding measured.

---

## 12. What this census does **not** establish

- It does **not** assert any of these artifacts is *correct* — only whether it exists and what it
  carries. `AUDITED != CLOSED`.
- It does **not** re-open, confirm, or overturn any finding. No `Validated` / `Revalidate-by` field
  was touched; no F-id was registered.
- It does **not** grant activation, promotion, or fusion authority to anything (§6.5).
- It does **not** claim completeness of disk coverage: `results/` alone holds hundreds of run
  directories, and the artifacts inventoried here are representative, not exhaustive.
- Counts and file sizes are **as observed on 2026-08-23 on this machine**, and are not reproducible
  elsewhere.
