# XAUUSD April-2026 OHLCV Static Lineage Trace

| Field | Value |
|---|---|
| Trace id | `XAUUSD-APR2026-OHLCV-STATIC-2026-07-10` |
| Binding | `data/mt5/XAUUSD_M15.csv` @ `4d73f5cebe33ec91…b26aba56` |
| Status of corpus | `FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION` (not AUTHORITATIVE) |
| Window | `2026-04-01T00:00:00` → `2026-04-30T23:59:59` |
| Method | STATIC import/call-site census + side-path search |
| Companion | `xauusd_apr2026_ohlcv_executed_lineage_trace-2026-07-10.md` |
| Graph | `xauusd_apr2026_ohlcv_lineage_graph-2026-07-10.json` |

**No economic claims. No remediation.**

---

## 1. Input binding (static record)

Mandatory start: `require_phase1_frozen_candidate()` must pass before any slice work
(executed proof in companion + `results/lineage/xauusd_apr2026_slice_identity.json`).

---

## 2. Static consumer census (reachable OHLCV consumers)

### 2.1 Admission / schema (TRANSFORM / FILTER)

| Consumer | Path | Branch | XAU-specific? | Notes |
|---|---|---|---|---|
| Phase-1 guard | `src/data_ingestion/xauusd_phase1_candidate.py` | FILTER | YES | Rewrites all XAUUSD M15 loads to frozen path |
| ohlcv_schema | `src/data_ingestion/ohlcv_schema.py` | FILTER | generic | L1 columns + value integrity |
| CandleLoader | `src/runtime/backtest_v2.py` | TRANSFORM | XAU rewrite | L1+L2 inline; definition of Candle stream |
| validate_dataset L3 | `src/data_ingestion/dataset_integrity.py` | FILTER | generic | Whole-file integrity |
| `_preflight_dataset` | `src/runtime/backtest_v2.py` | FILTER | XAU rewrite | **Only production L3 call site** (F-039) |
| `validate_universe` | same | FILTER | generic | Multi-instrument L3 |

### 2.2 Acquisition / persist (PERSIST — upstream of frozen pin)

| Consumer | Path | Branch | Notes |
|---|---|---|---|
| fetch_and_verify_mt5 | `scripts/data/fetch_and_verify_mt5.py` | PERSIST | Writes `data/mt5/*`; strict gate |
| historical_fetcher | `src/data_ingestion/historical_fetcher.py` | PERSIST | CSV write/verify |
| hummingbot/binance fetchers | `src/inout/*` | PERSIST | Other families — not this pin |

### 2.3 CandleLoader call sites (TRANSFORM → DERIVE/TERMINAL)

Representative (full list >40; graph enumerates classes):

- Research: `src/research/runner.py`, `forensics.py`, `cross_sectional.py`, adapters
- Governance: `config_validator.py`, `portfolio_validation.py`
- Analytics: `sl_tp_comparator.py`, `exit_model_band.py`
- Scripts: `build_resampled_data.py`, `qualify_*.py`, `auto_tuner*.py`, analysis sweeps
- Runtime: `MultiInstrumentRunner`, CLI single, `unified_replay_harness`

### 2.4 Direct CSV readers (bypass CandleLoader / often L3)

| Consumer | Path | Branch | Integrity |
|---|---|---|---|
| BacktestRunner feature prep | `backtest_v2.py` `pd.read_csv` | DERIVE | Path XAU-guarded; **no L2 stream** on this read |
| `run_backtest` simplified | `backtest_v2.py` | TERMINAL | **No CandleLoader** — pd only |
| backtest_bitnet | `src/runtime/backtest_bitnet.py` | TERMINAL | pd.read_csv |
| strategy_backtest | `src/governance/strategy_backtest.py` | TERMINAL | pd + FeaturePipeline |
| secondlow `load_ohlcv` | `src/research/secondlow_v1/detector.py` | DERIVE | **pandas/xlsx; no L3** |
| opportunity_scanner | `scripts/research/opportunity_scanner.py` | DERIVE/PERSIST | pd + FeaturePipeline |
| train_bitnet | `scripts/training/train_bitnet.py` | DERIVE | pd.read_csv |
| purge_delay_scan / purge_slice | `scripts/analysis/*` | DERIVE | generic `--file` |
| misc resample_m1_to_m15 | `scripts/misc/*` | AGGREGATE | pd |
| feature_math probes | `scripts/analysis/feature_math_*` | REPORT | `data/{symbol}_M15.csv` |

### 2.5 Derivation boundaries (DERIVE)

| Consumer | Path | Branch |
|---|---|---|
| candle_math | `src/features/candle_math.py` | DERIVE geometry |
| derived_math / formula_registry | `src/features/*` | DERIVE FM-* |
| FeaturePipeline | `src/features/feature_pipeline.py` | DERIVE 38-dim features |
| CRTEngine.process_candle | `src/config_layer/crt_engine_v2.py` | DERIVE CRT SM |
| engines.crt_engine.compute | `src/engines/crt_engine.py` | DERIVE fusion score (features in) |
| EngineRunner | `src/core/engine_runner.py` | DERIVE fusion stack |
| secondlow detector | `src/research/secondlow_v1/detector.py` | DERIVE purge events |
| research hypotheses | `src/research/hypotheses/*` | DERIVE |
| forward_walk | `src/research/measurement/forward_walk.py` | DERIVE labels/exits |
| rr_dataset_builder | `src/config_layer/rr/*` | DERIVE labels (trade stream) |
| resample | `src/research/resample.py` | AGGREGATE HTF |

### 2.6 Terminal / report / persist

| Consumer | Path | Branch |
|---|---|---|
| BacktestRunner outputs | trades/metrics/jsonl under `results/` | TERMINAL/PERSIST |
| HypothesisRunner / qualify_* | EdgeReport + JSON | REPORT/PERSIST |
| stage1_dataset_builder | training JSONL | PERSIST (from opportunities, not raw OHLCV) |
| zone_registry builders | models/zone_registry.json | PERSIST (from trades/opportunities) |

### 2.7 Live path

| Consumer | Branch | Historical CSV? |
|---|---|---|
| live_engine_hook / LiveEngine | TERMINAL | **No** — live dict bars from MT5 |
| live_path_replay script | REPORT | **Yes** — CandleLoader historical |

### 2.8 LATENT / UNREACHABLE

| Consumer | Status |
|---|---|
| `crt_feature_builder.py` | UNREACHABLE (0 call sites, F-046) |
| CognitiveBus / ReplayMemory / Cluster sidecars | LATENT (F-012) |
| qualify_fx_metals XAU | UNREACHABLE (XAU excluded by gap gate) |

---

## 3. Side-path search results

Searched: `pd.read_csv`, `CandleLoader(`, `validate_dataset(`, `FeaturePipeline(`, `load_ohlcv(`, parquet (none on OHLCV hot path), notebooks (none production), DB readers (portfolio orphan only — F-013).

**Direct-reader bypass class is REAL** (secondlow, opportunity_scanner, train_bitnet, run_backtest simplified, BacktestRunner dual-load).

---

## 4. Static completeness

Every major consumer class above is mapped to a terminal/report/persist sink or marked LATENT/UNREACHABLE with evidence. Machine graph: companion JSON.

```text
STATIC_CENSUS_STATUS = COMPLETE
```
