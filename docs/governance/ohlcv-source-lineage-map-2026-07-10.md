# OHLCV Source Lineage Map — PHASE 1 (OHLCV Truth Closure) PASS A

| Field | Value |
|---|---|
| Program | Layer-by-layer repository audit (bottom-up) |
| Phase | 1 of 16 — OHLCV Truth |
| Pass | A (Evidence Freeze) |
| Generated (UTC) | 2026-07-10T13:09:06Z |
| Pinned commit | `b48d4d9a7abfb429f2a17c790d4b32083da5dd92` (worktree DIRTY) |
| Branch | `feature/truth-registry-v2` |
| Census twin | `docs/governance/ohlcv-corpus-fingerprint-manifest-2026-07-10.json` |
| Verdict | (none — PASS A emits evidence only) |

Edge classification: **PROVEN** (executable/static evidence at cited line) ·
**LIKELY** (strong static evidence, per-instance not individually logged) ·
**LATENT** (code path exists, no current activation evidence) · **DEAD** (no
call sites) · **UNKNOWN** (no evidence; never inferred).

Canonical chain: `EXTERNAL SOURCE → ACQUISITION → RAW ARTIFACT → TRANSFORMATION
→ CANONICAL CORPUS → LOADER → RUNTIME OBJECT → CONSUMERS`.

---

## 1. Family `mt5` (27 files — FX/metals M5/M15/H1/H4)

```text
IC-Markets broker feed (MT5 terminal)                          [UNKNOWN upstream]
  → mt5.copy_rates_range IPC                                   [PROVEN  src/inout/mt5_candle_fetcher.py:170]
  → UTC datetime from bar epoch r["time"]                      [PROVEN  mt5_candle_fetcher.py:186]
  → defensive de-dupe by timestamp, keep-first                 [PROVEN  mt5_candle_fetcher.py:199]
  → CSV write data/mt5/{SYM}_{TF}.csv                          [PROVEN  scripts/data/fetch_and_verify_mt5.py:58 DEFAULT_OUT="data/mt5"]
  → STRICT verify gate (validate_dataset + strict_fetch)       [PROVEN  fetch_and_verify_mt5.py:181; REJECT → quarantine data/mt5/_rejected (:134)]
  → CandleLoader.stream                                        [PROVEN  src/runtime/backtest_v2.py:704]
  → Candle objects → consumers (§8)
```

Per-file classification: **LIKELY** — the write path is proven statically, but no
stored acquisition log ties each on-disk hash to a specific fetch session.
Cross-check: root FX M15 files are byte-identical to `mt5/` files (census
DUP-001/006/009/019/027) → the root FX corpus descends from this chain.

## 2. Family `binance` (28 files — crypto M5/M15/H1/H4)

```text
Binance via ccxt exchange.fetch_ohlcv (paginated 1000/call)    [PROVEN  scripts/data/fetch_and_verify_binance.py:72]
  → dedupe by row[0] keep-first + range filter + sort          [PROVEN  :83-88]
  → ts = fromtimestamp(row[0]/1000, tz=UTC) → "YYYY-MM-DD HH:MM:SS" [PROVEN :95-96]
  → CSV write data/binance/{SYM}_{TF}.csv                      [PROVEN  :51 DEFAULT_OUT="data/binance", :170]
  → STRICT verify gate; REJECT → data/binance/_rejected        [PROVEN  :142, :180]
  → CandleLoader.stream → consumers
```

Per-file: **LIKELY** (same caveat as mt5). `row[0]` is the ccxt unified-OHLCV
timestamp = candle OPEN time in ms (external ccxt API convention — see the
temporal report's evidence-type tagging); the sibling converter
`convert_binance_m1_to_m15.py:15` uses a field literally named `open_time`.

## 3. Family `yfinance` (17 files)

```text
yfinance API (Yahoo)                                           [UNKNOWN upstream quality]
  → fetch_instrument()                                         [PROVEN  scripts/data/fetch_forex_yfinance.py:108]
  → SYNTHETIC CROSS construction for non-USD crosses:
      High = leg1.High / leg2.Low ; Low = leg1.Low / leg2.High
      Volume = leg1.Volume.fillna(0)  (the LEG's volume, not the cross's)
                                                               [PROVEN  :130-135]
  → INVERSION path (1/x, High/Low swapped)                     [PROVEN  :148-149]
  → volume fillna(0) → int cast                                [PROVEN  :157]
  → drop_duplicates(keep="last") + sort_values                 [PROVEN  :170-171]
  → CSV write data/yfinance/                                   [PROVEN  :108 out_dir]
```

**No verify-gate wrapper exists for this family** (contrast §1/§2). The crypto
files under `yfinance/` are byte-identical to root and/or `binance/` copies
(DUP-002/010/021/024/026/029) — whether they were fetched via yfinance or copied
here is **UNKNOWN**. Volume semantics for synthesized crosses are **synthetic by
construction** (leg volume or 0), not the instrument's traded volume.

## 4. Family `data_root` (45 files — the CANONICAL/legacy corpus)

The active config points the integrity gate here
(`dataset_integrity.canonical_data_roots = ["data"]`,
`configs/production/v2_multi_2026_04.json`) and
`scripts/data/fetch_and_verify_binance.py:9` names it "the legacy
`data/{SYMBOL}_M15.csv`". Its SOURCE provenance is **per-file UNKNOWN**, but
content-hash evidence (census duplicate groups) pins descent for 12 of 12
canonical M15 majors:

| Root file | Byte-identical to | Implied source chain |
|---|---|---|
| `EURUSD/USDJPY/AUDUSD/GBPUSD/EURCAD_M15` | `data/mt5/` same name | §1 MT5 chain (**LIKELY**) |
| `XAUUSD_M15` | `data/mt5/_rejected/XAUUSD_M15.csv` | §1 chain but the twin was **QUARANTINED** (DUP-008 — see contradiction CX-OHLCV-004) |
| `BTCUSDT/ETHUSDT/XRPUSDT/DOGEUSDT_M15` | `data/yfinance/` same name (NOT `binance/`) | §3 yfinance chain (**LIKELY**) — the root crypto corpus does NOT descend from the strict-gated Binance fetch |
| `BNBUSDT/SOLUSDT_M15` | both `binance/` and `yfinance/` (3-way identical) | indistinguishable (**UNKNOWN** which fetch produced it) |

Historic builder scripts that COULD have produced root files —
`scripts/data/build_m15_unified.py`, `convert_binance_m1_to_m15.py`,
`prepare_data.py`, `unified_data_builder.py`, `fetch_crypto_ccxt.py` — have no
generation logs; edges from them to specific root files are **UNKNOWN**.
Derived-suffix artifacts in this family (`*_setups*`, `*_purge_scan*`) are
research outputs, classified DERIVED in the census.

## 5. Family `resampled` (8 files — crypto H1/H4)

```text
data/{SYM}_M15.csv  (family §4 — NOT data/binance/)            [PROVEN  scripts/research/build_resampled_data.py:45 --data-dir default "data"]
  → CandleLoader.stream (integrity backstop runs)              [PROVEN  :38]
  → research.resample (calendar buckets, causality invariant)  [PROVEN  src/research/resample.py:105]
  → write_csv canonical schema                                 [PROVEN  resample.py:148]
  → data/resampled/{SYM}_{H1,H4}.csv                           [PROVEN  build_resampled_data.py:46]
```

Pathway **PROVEN**; per-file parent hash linkage **LIKELY** (no stored
input-hash → output-hash generation record).

## 6. Family `perp` (12 files) — EXCLUDED (non-OHLCV)

Binance fapi funding/basis via `src/inout/perp_funding_fetcher.py` (pure
transport, dedup+sort, no fill — :10). Inventoried, excluded from OHLCV closure.

## 7. Quarantine / archive families

- `data/mt5/_rejected/` (69), `data/_rejected/` (12): strict-gate REJECT
  destinations (**PROVEN** write path, §1/§2 scripts). 16 quarantined files are
  byte-identical to ACTIVE `mt5/` files (DUP-003/004/005/007/011/012/013/017/018/020/022/023
  + DUP-008 inverted) — same bytes accepted in one location and rejected in
  another (see contradiction CX-OHLCV-005).
- `data/_archive_5wk/` (5): frozen FX M15 snapshots, byte-identical to
  `yfinance/` copies (DUP-014/015/016/025/028) → the archive IS the yfinance
  corpus of that era (**PROVEN by hash**).
- No ACTIVE runtime path reads from `_rejected/` or `_archive_5wk/` (grep over
  `src/` + `scripts/`: no reference to either directory outside the quarantine
  writers) — reachability **DEAD** for active consumption. The BYTES, however,
  re-enter via identical twins (XAUUSD_M15, CX-OHLCV-004/005).

## 8. Loader → consumers (single funnel)

`CandleLoader` (`src/runtime/backtest_v2.py:673`) is the ONLY OHLCV CSV→runtime
funnel found (grep `CandleLoader(` — ~50 call sites). Consumers: backtest_v2
entry points (**the only two with the L3 pre-flight**, `:2542/:2586` — F-039),
`research/runner.py:70`, `research/resample` consumers, `research/adapters/*`,
`research/cross_sectional.py:118`, `research/forensics.py:40`,
`analytics/sl_tp_comparator.py:599`, `config_layer/config_validator.py:153`,
`governance/portfolio_validation.py:342`, `runtime/exit_model_band.py:58`,
`runtime/unified_replay_harness.py:171`, ~30 `scripts/` (training/research/
analysis). All inherit the inline L1/L2 backstop; none re-read `_rejected/`.

**Dormant DB path**: `src/data_ingestion/historical_fetcher.py:198`
(`HistoricalFetcher`, TimescaleDB-centric, `_DBConnection:170`) — **LATENT**:
lazy-imported by `src/portfolio/correlation_engine.py:77-78` and registered in
`control_plane/registry.py:800`. A second, DB-backed OHLCV ingestion chain that
bypasses `CandleLoader` entirely (see CX-OHLCV-006).

## 9. Negative evidence (preserved)

- **No forward-fill / interpolation of OHLCV rows anywhere in `src/`** — grep
  `ffill|bfill|fillna|interpolate|resample(` over `src/` hits only:
  feature-layer post-load computations (`feature_pipeline.py:207,373-385,637,655`
  — feature columns, not candle rows), `research/resample.py` (fabrication-free
  by design), and a docstring. Acquisition-time fills exist only in the
  yfinance script (§3).
- **No loader sorts or repairs**: `CandleLoader` RAISES on duplicate
  (`backtest_v2.py:746-750`) and out-of-order (`:751-755`) — fail-fast, not
  repair.
- Census: 0/224 files with duplicate/out-of-order/unparseable timestamps, OHLC
  violations, negative volume, or non-finite values; 0 files with all-zero
  volume.

## What this map did NOT do

No remediation; no authority adjudication (PASS B); no economic claims; no
Phase-2 (candle-math) tracing.

```text
OHLCV_LINEAGE_FAMILIES = 8
OHLCV_LINEAGE_UNKNOWN_EDGES = root-corpus per-file generation events; yfinance-vs-copy for crypto; builder-script attribution
OHLCV_LINEAGE_STATUS = EVIDENCE_FROZEN
```
