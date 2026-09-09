# Feature→State→Geometry→Outcome Lineage Census

## Context

Before any finding revalidation or state-manipulation research begins, we need to know which
semantic layers are **durably persisted** and which are only **reconstructed by re-running current
code**. If Feature States or CRT States are ephemeral, then every historical finding rests on
replaying today's engine against yesterday's question — which is not revalidation, it is
re-derivation under a silently changed code line.

This is a read-only observability audit. It produces one document. It changes no code, no config,
no schema, and adds no persistence.

Two scoping decisions confirmed with the user:
- The pasted "Canonical Semantic Replay Store" design is **context only**. The census is written
  as-is; it neither names, endorses, nor refines that design. Its L0–L5 layering already answers
  the design's implicit question ("does each layer exist yet?") without becoming a document about
  the design.
- The census **does** inventory machine-local artifacts, each explicitly flagged UNTRACKED.

**Deliverable:** `docs/analysis/feature_state_lineage_census.md` (new file — no existing doc in
`docs/analysis/` owns this topic; §6.2 rule 1 checked).

## Verified findings to write up

Exploration is complete. Every claim below was source- or disk-verified this session and should be
carried into the document with its citation. Nothing here needs re-derivation at write time.

### The headline: the entire lineage is untracked

```
git ls-files data   -> 0
git ls-files logs   -> 0
git ls-files results-> 0
```

`.gitignore:1-6` ignores `data`, `logs`, `results`, `models/`. Every artifact carrying any layer of
this lineage — OHLC CSVs, `opportunities.jsonl`, run `*_events.jsonl`, `*_trades.csv`, oracle
`labels.csv`, `bar_matrix.csv` — exists **only on this machine**. From a clean clone, zero
historical state identity is recoverable. Same class as F-071 and F-083's residue.

### Per-layer verified state

| Layer | Producer | Persisted where | Notes |
|---|---|---|---|
| L0 OHLC | MT5 fetch → `data/mt5/*.csv` | CSV, untracked | `bar_matrix` manifest pins `corpus_sha256` — the only content-addressed OHLC reference found |
| L1 Feature Values | [feature_pipeline.py](src/features/feature_pipeline.py) (writes nothing — pure transform) | `opportunities.jsonl` `features{}`, `logs/feature_snapshots.jsonl`, `bar_matrix.csv`, `clean_labels.jsonl` | **Schema-heterogeneous:** 38-dim (clean_labels), 39-dim (opportunities 2026-07), 48-dim v5.0 (feature_snapshots, bar_matrix). Current canonical is 48 ([feature_schema.py:143](src/features/feature_schema.py:143)) |
| L2 Feature States | [feature_states.py](src/features/feature_states.py) | **only** `bar_matrix.csv` `state__*` (19 families), XAUUSD M15, one build | Module docstring: "NOT on the decision path. Shadow-only: nothing on the spine consumes this output" |
| L3 CRT States | [crt_engine_v2.py:1022](src/config_layer/crt_engine_v2.py:1022) `_transition()` — single assignment site | run-scoped `{INST}_events.jsonl`; global `logs/crt_transitions.jsonl` | Two streams, different completeness — see below |
| L4 Geometry | `Trade` ([crt_engine_v2.py:202](src/config_layer/crt_engine_v2.py:202)), `ExecutionPlannerV1_2` | `{INST}_trades.csv` (entry_raw/entry_fill/sl/tp1/tp2/exit_fill), oracle `labels.csv`, `clean_labels.jsonl` | Planner persists **nothing**; `logs/trade_journal.jsonl` does not exist on disk; `TradeRecord` ([journal/schema.py](src/journal/schema.py)) carries no geometry at all |
| L5 Outcome | `forward_walk` / `multi_tp_walk` / backtest ledger | `{INST}_trades.csv`, `labels.csv`, `clean_labels.jsonl`, `opportunities.jsonl` | `opportunities.jsonl` outcome is the F-022 stream — detection, not ledger |

### The two CRT streams are not equivalent — write this precisely

- **Run-scoped** `results/**/{INST}_events.jsonl` is **fold-complete**: it carries both
  `STATE_TRANSITION` and `RESET` (each with `state_from`/`state_to`). Measured on
  `results/analysis/crt_parity_sweep/engine_runs/B_baseline/run_20260805_170904_XAUUSD`:
  `RESET 11024, STATE_TRANSITION 3914, SWEEP 3416, TRADE_OPENED 6`. Folding this stream
  reconstructs the per-bar state series **without replay**.
- **Global** `logs/crt_transitions.jsonl` (2.59 GB, 4,741,789 lines) is **not**. `_emit_enveloped`
  ([crt_engine_v2.py:347-366](src/config_layer/crt_engine_v2.py:347)) returns early unless
  `ev.event == "STATE_TRANSITION"`, so every RESET is dropped. Verified empirically on a
  200,000-row sample: 100% `STATE_TRANSITION`, **0 RESET**. Folding this stream alone yields a
  **wrong** state series. It is also unattributable — `instrument` is `""` on 200,000/200,000 rows
  (the emit hardcodes `instrument=""`), no `run_id`, no `config_version`, all runs since
  2026-05-29 interleaved into one file.
- Both emits are conditional (`if ev_logger and candle`) and fail-open — an unlogged transition is
  indistinguishable from no transition. Same silent-gap class as F-056/F-079/F-083/F-085.

### Provenance is uneven — rank it in the doc

- **Best:** `clean_labels.jsonl` — per-record `provenance{}` with `protocol_id`, `protocol_hash`,
  `schema_hash`, `pit_status: PIT_UNCLEAN_STORED_FEATURES`, `exit_model`, `cost_bps`,
  `feature_dim: 38`, `source_path`, `candle_path`, `label_authority`.
- **Strong:** `bar_matrix/manifest.json` — `corpus_sha256`, `schema_version 5.0`, `schema_hash`,
  `feature_order_hash`, `canonical_dim 48`, `normalization_basis`, `session_timestamp_basis`,
  `parent_crt_enabled`, plus an explicit `known_contaminated_inputs` block (session basis, F-061
  saturation).
- **Envelope-only:** the enveloped streams carry `schema_hash` = `FEATURE_ORDER_HASH` at emission
  ([events/event_fabric.py](src/events/event_fabric.py)) — a passive drift detector no runtime path
  checks. Observed drifting mid-file: head `235553310100a340` → tail `160c96c52b198a16`.
- **None:** `opportunities.jsonl`. Its `run_header` is `{type, run_id, instrument, started_at}`
  only ([opportunity_scanner.py:187-194](scripts/research/opportunity_scanner.py:187)). No schema
  version, no config hash, no code SHA, and critically **none of the geometry parameters**
  (`sl_atr_mult`, `tp_atr_mult`, `trail_mult`, `max_forward_candles`, `warmup_candles`) that
  produced its own `sl`/`tp` columns. Also: "CRT is intentionally NOT consulted" — this stream
  carries no CRT state by construction.

### The one place a full chain exists

For **XAUUSD M15 only**, one program (SEM-018), one build, gitignored:
- `results/research/bar_matrix/XAUUSD_M15/bar_matrix.csv` — 47,197 rows × 124 cols: L0 + L1 (48
  canonical + intermediates) + L2 (19 `state__*`) + L3 (`crt_state_resolved`, `htf_state`,
  `parent_track_state`, `regime_label`), keyed by `_pos`.
- `results/research/oracle_labels/XAUUSD_M15/labels.csv` — 377,256 rows: L4 (entry/sl/tp1/tp2/
  risk_distance) + L5 (outcome/y_R_gross/cost_r/y_R_net/mfe/mae/duration), keyed by `_pos`.

Two caveats the doc must state plainly: (a) `crt_state_resolved` is the **resolver**, not the
engine — F-069 measured 88.16% agreement, and the manifest's `crt_state_distribution` shows only
5 states with **no RETEST/EXECUTION/RESOLUTION/EXPIRED**, matching the resolver's structurally
unreachable EXECUTION branch; (b) the labels' geometry is the oracle's synthetic every-bar
geometry, not a production trade.

### Parquet is a projection, not a store

[parquet_store.py](src/utils/parquet_store.py) is explicit: JSONL is the system of record, Parquet
is a derived regenerable sidecar, and `iter_records` silently falls back to JSONL on STALE/ABSENT.
Only **4** projections exist on disk, all XAUUSD: `opportunities`, `clean_labels`,
`XAUUSD_crt_telemetry`, `XAUUSD_events`. `pyarrow 25.0.1` is available now, but the bar_matrix
build (2026-08-20) recorded `parquet_skipped_reason: "Unable to find a usable engine"` — so
projection coverage is a function of which interpreter happened to run.

## Document structure

Follow the sections the request specifies, in order, so it is directly checkable against the ask:

1. **Scope & method** — what was read, what was verified on disk, the UNTRACKED caveat.
2. **Census table** (the 6-layer YES/PARTIAL/NO grid).
3. **Feature Value Audit** — canonical vector location, schema authority, the three persisted dims,
   loss points.
4. **Feature State Audit** — per-family table across the 19 declared families.
5. **CRT State Audit** — per-state table; the two-stream fold-completeness split.
6. **Geometry Audit** — per-component table; call out that partial exits / trail / BE moves are
   **parameters**, never persisted per-trade (F-088's `multi_tp_walk` reconstructs them).
7. **Outcome Audit** — storage locations, authority, and the three join questions.
8. **Lineage graph** with every edge marked DIRECT / IMPLICIT / RECONSTRUCTED / MISSING.
9. **Persistence risk assessment** — GREEN / YELLOW / RED per layer with justification.
10. **Final questions** — answer all five explicitly.
11. **Authority footer** — research/governance observation only, no G001, grants no authority
    (§6.5), classification per §6.8.

## Files to read at write time

Only these need re-opening; everything else is captured above.

- [src/features/feature_pipeline.py](src/features/feature_pipeline.py) — confirm it writes nothing
  and name its output columns for the L1 row.
- [src/config_layer/crt_engine_v2.py](src/config_layer/crt_engine_v2.py) `EventLogger.record` /
  `_emit_enveloped` / `reset_to_range` — exact line numbers for citations.
- [src/research/episodes/schema.py](src/research/episodes/schema.py) — `EntrySnapshot` fields, for
  the episode-store row (geometry: one `tp_price`, optional `feature_vector`, no CRT state).
- [docs/analysis/feature-identity-state-inventory-2026-08-19.xlsx](docs/analysis/feature-identity-state-inventory-2026-08-19.xlsx)
  — the declared 19 state families, to make the Feature State Audit table exhaustive rather than
  sampled.

## Constraints held

No architecture proposals. No new schemas. No persistence added. No experiments run. Anything the
census cannot establish is written as `UNKNOWN`, never inferred — per §6.6, an undefined behaviour
becomes an explicit unknown, not a TODO.

## Verification

1. `docs/analysis/feature_state_lineage_census.md` exists and every one of the request's named
   sections is present.
2. Every `file:line` citation resolves — spot-check with
   `python scripts/governance/query_semantic_os.py --ground --kind IMPLEMENTATION --token <path> --symbol <Name>`
   for the module-level claims (§6.7).
3. `pytest tests/test_doc_citations.py -q` — the ±30-line citation drift gate (§6.3).
4. `pytest tests/test_current_findings.py -q` — confirms no finding row was disturbed. The census
   registers **no new F-id**: it is an inventory, not a conclusion. If writing it surfaces a
   genuine `TruthConflict`, surface it to the user rather than resolving it in the doc (§6.2 rule 3).
5. Append the `📝 SESSION LOG ENTRY` block to `assistant_project.md` (§6).
