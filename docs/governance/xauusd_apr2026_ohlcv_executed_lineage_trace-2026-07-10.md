# XAUUSD April-2026 OHLCV Executed Lineage Trace

| Field | Value |
|---|---|
| Trace id | `XAUUSD-APR2026-OHLCV-EXECUTED-2026-07-10` |
| Binding verify | `require_phase1_frozen_candidate()` → **PASS** |
| Frozen path | `data/mt5/XAUUSD_M15.csv` |
| Frozen SHA-256 | `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56` |
| Frozen rows / range | 47275 / `2024-05-22T01:00:00` → `2026-05-21T23:45:00` |
| Trace window | `2026-04-01T00:00:00` → `2026-04-30T23:59:59` |
| Slice artifact | `results/lineage/xauusd_apr2026_slice.csv` |
| Slice identity | `results/lineage/xauusd_apr2026_slice_identity.json` |
| Stage dump | `results/lineage/xauusd_apr2026_executed_stages.json` |

**Read-only execution. No config/code/formula changes. No promotion. No economic claims.**

---

## 1. One-month slice identity (EXECUTED)

| Field | Value |
|---|---|
| Selected row count | **1929** |
| First timestamp in slice | **2026-04-01T01:45:00** (not 00:00 — no tradable bars earlier on 2026-04-01 under this corpus) |
| Last timestamp in slice | **2026-04-30T23:45:00** |
| Slice content SHA-256 (on-disk file bytes) | `23248ba412955d64064d41ed53a3ba6602ba24c1f248704abeb8fcf738f41a97` |
| Parent corpus SHA-256 | `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56` |

Window request was calendar month; **observed first bar is 01:45** (session/calendar structure of the frozen series).

---

## 2. Executed stages

### E0 — SLICE FILTER

| Field | Value |
|---|---|
| stage_id | `E0_SLICE_IDENTITY` |
| parent | ∅ (from frozen binding) |
| entry | offline extract from frozen CSV |
| branch | FILTER |
| rows_in → out | 47275 → 1929 |
| semantic | month window only |
| evidence | EXECUTED / PROVEN |

### E1 — L1 SCHEMA + VALUE (no mutation)

| Field | Value |
|---|---|
| stage_id | `E1_L1_SCHEMA_VALUE` |
| entry | `ohlcv_schema.require_ohlcv_columns` + `validate_ohlcv_row` + `parse_ohlcv_timestamp` |
| branch | TRANSFORM (validate-only) |
| rows | 1929 / 0 violations |
| semantic | source OHLCV preserved |
| evidence | EXECUTED / PROVEN |

### E2 — L3 DATASET INTEGRITY (full frozen corpus)

| Field | Value |
|---|---|
| stage_id | `E2_L3_DATASET_INTEGRITY_FULL_CORPUS` |
| entry | `validate_dataset(data/mt5/XAUUSD_M15.csv, instrument=XAUUSD)` |
| config | active `v2_multi_2026_04` `dataset_integrity` |
| decision | **WARN** (0 hard_failures; intra-session gaps reported) |
| branch | REPORT |
| semantic | no CSV mutation |
| evidence | EXECUTED / PROVEN |

Note: L3 was run on **full** frozen corpus (gate expects continuous session model), not the isolated April file alone.

### E3 — CandleLoader STREAM (April filter in-process)

| Field | Value |
|---|---|
| stage_id | `E3_CANDLELOADER_STREAM_APRIL` |
| entry | `CandleLoader('data/mt5/XAUUSD_M15.csv','XAUUSD').stream()` |
| guard | path rewritten to absolute frozen path; NOT AUTHORITATIVE log emitted |
| April candles | **1929** (matches slice) |
| first/last | 2026-04-01T01:45:00 → 2026-04-30T23:45:00 |
| branch | TRANSFORM |
| new_fields | `Candle` dataclass |
| L1/L2 | enforced in stream |
| L3 | **not** re-run inside stream |
| evidence | EXECUTED / PROVEN |

### E4 — FeaturePipeline (full corpus warmup → April retain)

| Field | Value |
|---|---|
| stage_id | `E4_FEATURE_PIPELINE` |
| entry | `FeaturePipeline(df).run()` on full frozen CSV via **direct `pd.read_csv`** (bypass CandleLoader L2 stream) |
| rows_before → after finalize | 47275 → **47197** (drop 78 / 0.16% warmup NaNs) |
| April enriched rows | **1929** |
| CANONICAL_FEATURES present | **38 / 38** |
| sample derived | first April `body_ratio` via candle_math = **0.629049…** |
| branch | DERIVE |
| source OHLCV columns | **preserved alongside** derived columns in enriched frame |
| evidence | EXECUTED / PROVEN |

**Boundary note:** first bars of derived state appear here (`candle_body`, `upper_wick`, `ma_*`, `rsi_14`, ATR, etc.) while `open/high/low/close/volume` remain present.

### E5 — candle_math scalar

| Field | Value |
|---|---|
| stage_id | `E5_CANDLE_MATH` |
| entry | `features.candle_math.body_ratio` |
| branch | DERIVE |
| evidence | EXECUTED / PROVEN |

### E6 — SECONDLOW detector (full frozen → April events)

| Field | Value |
|---|---|
| stage_id | `E6_SECONDLOW_DETECTOR` |
| entry | `resolved_canonical_csv` + `load_ohlcv` + `detect_independent_events` |
| loader | **pandas** (`load_ohlcv`) — **no CandleLoader / no L3** |
| independent events (full) | 36 |
| independent events in April window | (see stages JSON; detector ran) |
| branch | DERIVE |
| evidence | EXECUTED / PROVEN |

### E7 — GUARD REWRITE

| Field | Value |
|---|---|
| stage_id | `E7_GUARD_REWRITE` |
| entry | `guard_xauusd_csv_path('data/XAUUSD_M15.csv','XAUUSD')` |
| output | absolute `…/data/mt5/XAUUSD_M15.csv` |
| branch | FILTER |
| evidence | EXECUTED / PROVEN |

### E8 — CRTEngine.process_candle (BLOCKED without spine HTF setup)

| Field | Value |
|---|---|
| stage_id | `E8_CRT_ENGINE` |
| entry | `CRTEngine(ConfigBuilder.build('XAUUSD')).process_candle` |
| result | **BLOCKED**: `active_range` is None (`AttributeError: h_ref`) when called without spine HTF/range initialization |
| static reachability | PROVEN (BacktestRunner spine calls this after range setup) |
| evidence | EXECUTED attempt + STATIC spine wiring / status **BLOCKED** for isolated April call |

Full CRT spine terminal path is therefore **STATIC_AND_EXECUTED partial** — not force-run end-to-end in this trace (would require full BacktestRunner configuration; not required to map terminal consumers statically).

---

## 3. Unexecuted but statically mapped paths

| Path class | Evidence type | Status |
|---|---|---|
| Full BacktestRunner → trades JSONL | STATIC | LATENT for this slice run (not launched) |
| MultiInstrumentRunner / qualify_* | STATIC | LATENT (generic; would hit XAU guard if pointed at XAU) |
| opportunity_scanner | STATIC | LATENT |
| train_bitnet / stage1 | STATIC | LATENT / different input schema |
| live_engine_hook | STATIC | UNREACHABLE for historical CSV |
| rr_dataset_builder | STATIC | LATENT (trade-ledger inputs) |
| resample → data/resampled | STATIC | LATENT (build_resampled_data not run for XAU) |

---

## 4. Validation / integrity coverage (executed)

| Layer | Path | April slice | Full frozen |
|---|---|---|---|
| Phase-1 hash/range | require_phase1_frozen_candidate | N/A | PASS |
| L1 schema/value | ohlcv_schema | PASS 1929/1929 | — |
| L2 order/dup | CandleLoader.stream | PASS (stream) | PASS |
| L3 validate_dataset | dataset_integrity | not slice-alone | WARN (0 hard) |

---

## 5. Executed-path completeness statement

Executed: binding, slice identity, L1, L3 (full), CandleLoader April filter, FeaturePipeline, candle_math, secondlow, path guard.  
CRT isolated call BLOCKED; full spine TERMINAL left STATIC.

```text
EXECUTED_TRACE_STATUS = PARTIAL_BUT_SUFFICIENT_FOR_BOUNDARY_AND_FANOUT
```

Does **not** alone force TRACE_COMPLETE; combined with static census → overall COMPLETE (see return block).
