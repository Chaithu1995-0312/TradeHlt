# OHLCV Corpus Census — PHASE 1 (OHLCV Truth Closure) PASS A

| Field | Value |
|---|---|
| Program | Layer-by-layer repository audit (bottom-up) |
| Phase | 1 of 16 — OHLCV Truth |
| Pass | A (Evidence Freeze) |
| Generated (UTC) | 2026-07-10T13:09:06Z |
| Pinned commit | `b48d4d9a7abfb429f2a17c790d4b32083da5dd92` (worktree DIRTY — hashes pin on-disk bytes) |
| Branch | `feature/truth-registry-v2` |
| Machine-readable twin | `docs/governance/ohlcv-corpus-fingerprint-manifest-2026-07-10.json` |
| Generator | `scripts/analysis/ohlcv_census.py` v1.0.0 (deterministic; stdlib) |
| Verdict | (none — PASS A emits evidence only; closure adjudication is PASS B) |

**Scope note.** This census inventories PHYSICAL artifacts and applies the
declared identity rules. Inventorying N files is NOT a claim that logical
corpus authority is closed (C2). Timestamps in every scanned file are
tz-NAIVE; 'UTC' is an assumption to be proven per acquisition path in the
temporal-semantics report, not a census finding. Gap statistics here are
session-BLIND raw inter-bar deltas (the session-aware interpretation is
`dataset_integrity._analyze_gaps`'s job) — a weekend close appears as a
'gap' below and that is expected, not a defect.

## Identity / authority rules applied

| Rule | Effect |
|---|---|
| `RULE-ARCHIVE` | path contains an `_archive` segment -> ARCHIVED (frozen snapshot convention, e.g. data/_archive_5wk/). Confidence HIGH. |
| `RULE-DERIVED-SUFFIX` | filename stem carries a derived-artifact marker (_setups, _purge_scan, _continuation, _reversion, _second_low, _secondlow, _part_, _isolated) -> DERIVED. Parent = the canonical `{SYMBOL}_{TF}` artifact in the same directory when present. Confidence MEDIUM (marker convention; per-file generator not individually traced). |
| `RULE-NON-OHLCV` | header does not resolve the six OHLCV columns via ohlcv_schema.OHLCV_HEADER_ALIASES -> EXCLUDED (non-OHLCV artifact, e.g. data/perp/ funding/basis series). Confidence HIGH. |
| `RULE-PROVIDER-BINANCE` | data/binance/{SYMBOL}_{TF}.csv canonical-pattern -> AUTHORITATIVE_RAW (provider-differentiated corpus written by scripts/data/fetch_and_verify_binance.py DEFAULT_OUT='data/binance', strict-gate verified). Confidence MEDIUM (same caveat as MT5). |
| `RULE-PROVIDER-MT5` | data/mt5/{SYMBOL}_{TF}.csv canonical-pattern -> AUTHORITATIVE_RAW (provider-differentiated corpus written by scripts/data/fetch_and_verify_mt5.py DEFAULT_OUT='data/mt5' via inout.mt5_candle_fetcher.MT5CandleFetcher, strict-gate verified). Confidence MEDIUM (write path proven statically; per-file acquisition session not individually logged). |
| `RULE-PROVIDER-YFINANCE` | data/yfinance/*.csv -> AUTHORITATIVE_RAW candidate (provider dir; scripts/data/fetch_forex_yfinance.py exists) but NO verify-gate wrapper found. Confidence LOW. |
| `RULE-QUARANTINE` | path contains a `_rejected` segment -> QUARANTINED (integrity-gate quarantine convention: fetch_and_verify_mt5.py --quarantine data/mt5/_rejected, fetch_and_verify_binance.py --quarantine data/binance/_rejected). Confidence HIGH. |
| `RULE-RESAMPLED` | under data/resampled/ -> DERIVED from data/{SYMBOL}_M15.csv via scripts/research/build_resampled_data.py (reads --data-dir data, writes --out data/resampled; research.resample causality-invariant aggregator). Confidence HIGH for the pathway, MEDIUM per file (no stored generation log ties each output hash to an input hash). |
| `RULE-ROOT-CANONICAL` | data/{SYMBOL}_{TF}.csv at the data root, canonical pattern -> AUTHORITATIVE_CANONICAL role (the active config's dataset_integrity.canonical_data_roots=['data'] and the historical backtest corpus live here; fetch_and_verify_binance.py:9 calls this the 'legacy data/{SYMBOL}_M15.csv' corpus). SOURCE provenance is NOT established per file -> provenance UNKNOWN, confidence LOW. |
| `RULE-UNMATCHED` | no rule matched -> authority_class UNKNOWN, confidence UNKNOWN. Census never infers unknown provenance (Prompt-2 STEP 2). |

## Family summary

| corpus_family_id | files | OHLCV-schema | rows (sum, scanned) | authority classes |
|---|---|---|---|---|
| `_archive_5wk` | 5 | 5 | 11391 | ARCHIVED |
| `_rejected` | 12 | 12 | 92619 | QUARANTINED |
| `binance` | 28 | 25 | 1831446 | AUTHORITATIVE_RAW, DERIVED, EXCLUDED |
| `data_root` | 45 | 21 | 1252464 | AUTHORITATIVE_CANONICAL, DERIVED, EXCLUDED |
| `mt5` | 96 | 94 | 3605322 | AUTHORITATIVE_RAW, DERIVED, EXCLUDED, QUARANTINED |
| `perp` | 12 | 0 | 433620 | EXCLUDED |
| `repo_root` | 1 | 0 | 1562 | EXCLUDED |
| `resampled` | 8 | 8 | 87592 | DERIVED |
| `yfinance` | 17 | 17 | 515967 | AUTHORITATIVE_RAW, DERIVED |

## Logical-corpus rollup (ACTIVE claimants only)

A logical corpus is AMBIGUOUS when more than one active (non-quarantined,
non-archived, non-derived) physical file claims the same `{SYMBOL}_{TF}`
identity. `same_logical_different_bytes` is the stronger flag: identical
logical name resolving to different data.

| logical_corpus_id | claimants | families | distinct hashes | AMBIGUOUS | different bytes |
|---|---|---|---|---|---|
| `AUDUSD_H1` | 1 | `mt5` | 1 | no | no |
| `AUDUSD_H4` | 1 | `mt5` | 1 | no | no |
| `AUDUSD_M15` | 3 | `data_root`, `mt5`, `yfinance` | 2 | **YES** | **YES** |
| `AUDUSD_M5` | 1 | `mt5` | 1 | no | no |
| `BNBUSDT_H1` | 1 | `binance` | 1 | no | no |
| `BNBUSDT_H4` | 1 | `binance` | 1 | no | no |
| `BNBUSDT_M15` | 3 | `binance`, `data_root`, `yfinance` | 1 | **YES** | no |
| `BNBUSDT_M5` | 1 | `binance` | 1 | no | no |
| `BTCUSDT_H1` | 1 | `binance` | 1 | no | no |
| `BTCUSDT_H4` | 1 | `binance` | 1 | no | no |
| `BTCUSDT_M15` | 3 | `binance`, `data_root`, `yfinance` | 2 | **YES** | **YES** |
| `BTCUSDT_M5` | 1 | `binance` | 1 | no | no |
| `DOGEUSDT_H1` | 1 | `binance` | 1 | no | no |
| `DOGEUSDT_H4` | 1 | `binance` | 1 | no | no |
| `DOGEUSDT_M15` | 3 | `binance`, `data_root`, `yfinance` | 2 | **YES** | **YES** |
| `DOGEUSDT_M5` | 1 | `binance` | 1 | no | no |
| `ETHUSDT_H1` | 1 | `binance` | 1 | no | no |
| `ETHUSDT_H4` | 1 | `binance` | 1 | no | no |
| `ETHUSDT_M15` | 3 | `binance`, `data_root`, `yfinance` | 2 | **YES** | **YES** |
| `ETHUSDT_M5` | 1 | `binance` | 1 | no | no |
| `EURCAD_H1` | 1 | `mt5` | 1 | no | no |
| `EURCAD_H4` | 1 | `mt5` | 1 | no | no |
| `EURCAD_M15` | 3 | `data_root`, `mt5`, `yfinance` | 2 | **YES** | **YES** |
| `EURCAD_M5` | 1 | `mt5` | 1 | no | no |
| `EURUSD_H1` | 1 | `mt5` | 1 | no | no |
| `EURUSD_H4` | 1 | `mt5` | 1 | no | no |
| `EURUSD_M15` | 2 | `data_root`, `mt5` | 1 | **YES** | no |
| `EURUSD_M5` | 1 | `mt5` | 1 | no | no |
| `GBPUSD_H1` | 1 | `mt5` | 1 | no | no |
| `GBPUSD_H4` | 1 | `mt5` | 1 | no | no |
| `GBPUSD_M15` | 3 | `data_root`, `mt5`, `yfinance` | 2 | **YES** | **YES** |
| `GBPUSD_M5` | 1 | `mt5` | 1 | no | no |
| `SOLUSDT_H1` | 1 | `binance` | 1 | no | no |
| `SOLUSDT_H4` | 1 | `binance` | 1 | no | no |
| `SOLUSDT_M15` | 3 | `binance`, `data_root`, `yfinance` | 1 | **YES** | no |
| `SOLUSDT_M5` | 1 | `binance` | 1 | no | no |
| `USDJPY_H1` | 1 | `mt5` | 1 | no | no |
| `USDJPY_H4` | 1 | `mt5` | 1 | no | no |
| `USDJPY_M15` | 3 | `data_root`, `mt5`, `yfinance` | 2 | **YES** | **YES** |
| `USDJPY_M5` | 1 | `mt5` | 1 | no | no |
| `XAUUSD_H1` | 1 | `mt5` | 1 | no | no |
| `XAUUSD_H4` | 1 | `mt5` | 1 | no | no |
| `XAUUSD_M15` | 3 | `data_root`, `mt5`, `yfinance` | 3 | **YES** | **YES** |
| `XAUUSD_M5` | 1 | `mt5` | 1 | no | no |
| `XRPUSDT_H1` | 1 | `binance` | 1 | no | no |
| `XRPUSDT_H4` | 1 | `binance` | 1 | no | no |
| `XRPUSDT_M15` | 3 | `binance`, `data_root`, `yfinance` | 2 | **YES** | **YES** |
| `XRPUSDT_M5` | 1 | `binance` | 1 | no | no |

**48 logical corpora; 12 AMBIGUOUS; 9 with same-logical-different-bytes.**

## Physical artifact census

Full per-artifact detail (all fields incl. per-format timestamp counts and
authority evidence text) lives in the machine twin. `dupTS`/`oOo` = duplicate /
out-of-order timestamp COUNTS (the runtime loader raises on the first; census
counts all). `gaps` = inter-bar deltas > modal (session-blind).

| id | path | class | conf | schema | rows | first ts | last ts | modal(s) | gaps | dupTS | oOo | zeroVol | negV | OHLCviol | dupGrp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PA-898809295e24 | `btc_daily.csv` | EXCLUDED | HIGH | NON_OHLCV | 1562 |  |  |  |  |  |  |  |  |  |  |
| PA-76fe0f3b0165 | `data/AUDUSD_M15.csv` | AUTHORITATIVE_CANONICAL | LOW | OHLCV | 49722 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 109 | 0 | 0 | 0 | 0 | 0 | DUP-027 |
| PA-ef1e65a103bb | `data/BNBUSDT_M15.csv` | AUTHORITATIVE_CANONICAL | LOW | OHLCV | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 | DUP-002 |
| PA-9663efd8b1b7 | `data/BNBUSDT_M15_2year_purge_scan.csv` | DERIVED | MEDIUM | OHLCV_PLUS_EXTRA | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-4b295f05f1e6 | `data/BNBUSDT_M15_2year_setups.csv` | EXCLUDED | HIGH | NON_OHLCV | 277 |  |  |  |  |  |  |  |  |  |  |
| PA-756d9e0ea42a | `data/BNBUSDT_M15_2year_setups_continuation.csv` | EXCLUDED | HIGH | NON_OHLCV | 277 |  |  |  |  |  |  |  |  |  |  |
| PA-c23c46fd61d2 | `data/BNBUSDT_M15_2year_setups_reversion.csv` | EXCLUDED | HIGH | NON_OHLCV | 277 |  |  |  |  |  |  |  |  |  |  |
| PA-9a047c7e32e5 | `data/BTCUSDT_M15.csv` | AUTHORITATIVE_CANONICAL | LOW | OHLCV | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 | DUP-024 |
| PA-eab2769958be | `data/BTCUSDT_M15_2year_purge_scan.csv` | DERIVED | MEDIUM | OHLCV_PLUS_EXTRA | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-8015bc43547d | `data/BTCUSDT_M15_2year_setups.csv` | EXCLUDED | HIGH | NON_OHLCV | 336 |  |  |  |  |  |  |  |  |  |  |
| PA-862981b6454d | `data/BTCUSDT_M15_2year_setups_continuation.csv` | EXCLUDED | HIGH | NON_OHLCV | 336 |  |  |  |  |  |  |  |  |  |  |
| PA-ed35f973f634 | `data/BTCUSDT_M15_2year_setups_reversion.csv` | EXCLUDED | HIGH | NON_OHLCV | 336 |  |  |  |  |  |  |  |  |  |  |
| PA-307cbf3da8b9 | `data/DOGEUSDT_M15.csv` | AUTHORITATIVE_CANONICAL | LOW | OHLCV | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 | DUP-010 |
| PA-635499fb1319 | `data/ETHUSDT_M15.csv` | AUTHORITATIVE_CANONICAL | LOW | OHLCV | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 | DUP-026 |
| PA-0cedc82625cf | `data/ETHUSDT_M15_2year_purge_scan.csv` | DERIVED | MEDIUM | OHLCV_PLUS_EXTRA | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-bb500fd009b9 | `data/ETHUSDT_M15_2year_setups.csv` | EXCLUDED | HIGH | NON_OHLCV | 276 |  |  |  |  |  |  |  |  |  |  |
| PA-1556849d17c8 | `data/ETHUSDT_M15_2year_setups_continuation.csv` | EXCLUDED | HIGH | NON_OHLCV | 276 |  |  |  |  |  |  |  |  |  |  |
| PA-6f77d0b6e897 | `data/ETHUSDT_M15_2year_setups_reversion.csv` | EXCLUDED | HIGH | NON_OHLCV | 276 |  |  |  |  |  |  |  |  |  |  |
| PA-60cb62ca5a9a | `data/EURCAD_M15.csv` | AUTHORITATIVE_CANONICAL | LOW | OHLCV | 49715 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 110 | 0 | 0 | 0 | 0 | 0 | DUP-001 |
| PA-0d01be15958c | `data/EURCAD_M15_purge_scan.csv` | DERIVED | MEDIUM | OHLCV_PLUS_EXTRA | 49715 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 110 | 0 | 0 | 0 | 0 | 0 |  |
| PA-1e9ed0f0b441 | `data/EURUSD_M15.csv` | AUTHORITATIVE_CANONICAL | LOW | OHLCV | 49721 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 109 | 0 | 0 | 5 | 0 | 0 | DUP-009 |
| PA-bce3db648a99 | `data/EURUSD_M15_purge_scan.csv` | DERIVED | MEDIUM | OHLCV_PLUS_EXTRA | 49721 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 109 | 0 | 0 | 5 | 0 | 0 |  |
| PA-03eee4774233 | `data/EURUSD_M15_setups.csv` | EXCLUDED | HIGH | NON_OHLCV | 219 |  |  |  |  |  |  |  |  |  |  |
| PA-ebc45e6ace2b | `data/EURUSD_M15_setups_continuation.csv` | EXCLUDED | HIGH | NON_OHLCV | 219 |  |  |  |  |  |  |  |  |  |  |
| PA-e02b556b0403 | `data/EURUSD_M15_setups_reversion.csv` | EXCLUDED | HIGH | NON_OHLCV | 219 |  |  |  |  |  |  |  |  |  |  |
| PA-141bb5be1aab | `data/GBPUSD_M15.csv` | AUTHORITATIVE_CANONICAL | LOW | OHLCV | 49716 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 110 | 0 | 0 | 0 | 0 | 0 | DUP-019 |
| PA-0d20a7364c70 | `data/GBPUSD_M15_purge_scan.csv` | DERIVED | MEDIUM | OHLCV_PLUS_EXTRA | 49716 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 110 | 0 | 0 | 0 | 0 | 0 |  |
| PA-fc2d20404f27 | `data/GBPUSD_M15_setups.csv` | EXCLUDED | HIGH | NON_OHLCV | 279 |  |  |  |  |  |  |  |  |  |  |
| PA-83b11e040ac0 | `data/GBPUSD_M15_setups_continuation.csv` | EXCLUDED | HIGH | NON_OHLCV | 279 |  |  |  |  |  |  |  |  |  |  |
| PA-8bff862771a0 | `data/GBPUSD_M15_setups_reversion.csv` | EXCLUDED | HIGH | NON_OHLCV | 279 |  |  |  |  |  |  |  |  |  |  |
| PA-e7311207baa5 | `data/SOLUSDT_M15.csv` | AUTHORITATIVE_CANONICAL | LOW | OHLCV | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 | DUP-021 |
| PA-b22fac7beb08 | `data/SOLUSDT_M15_2year_purge_scan.csv` | DERIVED | MEDIUM | OHLCV_PLUS_EXTRA | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-20b8a4a6ac36 | `data/SOLUSDT_M15_2year_setups.csv` | EXCLUDED | HIGH | NON_OHLCV | 352 |  |  |  |  |  |  |  |  |  |  |
| PA-0f2498f64d9c | `data/SOLUSDT_M15_2year_setups_continuation.csv` | EXCLUDED | HIGH | NON_OHLCV | 352 |  |  |  |  |  |  |  |  |  |  |
| PA-22e1d0a072cc | `data/SOLUSDT_M15_2year_setups_reversion.csv` | EXCLUDED | HIGH | NON_OHLCV | 352 |  |  |  |  |  |  |  |  |  |  |
| PA-f3e4cbef4b0e | `data/USDJPY_M15.csv` | AUTHORITATIVE_CANONICAL | LOW | OHLCV | 49716 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 110 | 0 | 0 | 0 | 0 | 0 | DUP-006 |
| PA-6415b2861852 | `data/USDJPY_M15_purge_scan.csv` | DERIVED | MEDIUM | OHLCV_PLUS_EXTRA | 49716 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 110 | 0 | 0 | 0 | 0 | 0 |  |
| PA-c52683aa27c9 | `data/USDJPY_M15_setups.csv` | EXCLUDED | HIGH | NON_OHLCV | 270 |  |  |  |  |  |  |  |  |  |  |
| PA-62698209b07a | `data/USDJPY_M15_setups_continuation.csv` | EXCLUDED | HIGH | NON_OHLCV | 270 |  |  |  |  |  |  |  |  |  |  |
| PA-96de792b0978 | `data/USDJPY_M15_setups_reversion.csv` | EXCLUDED | HIGH | NON_OHLCV | 270 |  |  |  |  |  |  |  |  |  |  |
| PA-487cd36c5d3b | `data/XAUUSD_M15.csv` | AUTHORITATIVE_CANONICAL | LOW | OHLCV | 50169 | 2024-05-22 01:00:00 | 2026-07-06 23:45:00 | 900 | 550 | 0 | 0 | 0 | 0 | 0 | DUP-008 |
| PA-d9ac3226797e | `data/XAUUSD_M15_purge_scan.csv` | DERIVED | MEDIUM | OHLCV_PLUS_EXTRA | 47275 | 2024-05-22 01:00:00 | 2026-05-21 23:45:00 | 900 | 516 | 0 | 0 | 0 | 0 | 0 |  |
| PA-bcaddbbcd55b | `data/XAUUSD_M15_setups.csv` | EXCLUDED | HIGH | NON_OHLCV | 245 |  |  |  |  |  |  |  |  |  |  |
| PA-e800e7642bcf | `data/XAUUSD_M15_setups_continuation.csv` | EXCLUDED | HIGH | NON_OHLCV | 245 |  |  |  |  |  |  |  |  |  |  |
| PA-821209a04caa | `data/XAUUSD_M15_setups_reversion.csv` | EXCLUDED | HIGH | NON_OHLCV | 245 |  |  |  |  |  |  |  |  |  |  |
| PA-e189ccadcb09 | `data/XRPUSDT_M15.csv` | AUTHORITATIVE_CANONICAL | LOW | OHLCV | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 | DUP-029 |
| PA-db9d2a279ac8 | `data/_archive_5wk/AUDUSD_M15.csv` | ARCHIVED | HIGH | OHLCV | 2275 | 2026-04-17 04:00:00 | 2026-05-22 08:45:00 | 900 | 25 | 0 | 0 | 0 | 0 | 0 | DUP-014 |
| PA-f9512038f63b | `data/_archive_5wk/EURCAD_M15.csv` | ARCHIVED | HIGH | OHLCV | 2274 | 2026-04-17 04:00:00 | 2026-05-22 08:45:00 | 900 | 25 | 0 | 0 | 0 | 0 | 0 | DUP-028 |
| PA-a537c58a5d67 | `data/_archive_5wk/GBPUSD_M15.csv` | ARCHIVED | HIGH | OHLCV | 2274 | 2026-04-17 04:00:00 | 2026-05-22 08:45:00 | 900 | 25 | 0 | 0 | 0 | 0 | 0 | DUP-025 |
| PA-a0f3d4d6616d | `data/_archive_5wk/USDJPY_M15.csv` | ARCHIVED | HIGH | OHLCV | 2274 | 2026-04-17 04:00:00 | 2026-05-22 08:45:00 | 900 | 25 | 0 | 0 | 0 | 0 | 0 | DUP-016 |
| PA-ca3d8e0c9e9b | `data/_archive_5wk/XAUUSD_M15.csv` | ARCHIVED | HIGH | OHLCV | 2294 | 2026-04-17 04:00:00 | 2026-05-22 08:45:00 | 900 | 26 | 0 | 0 | 0 | 0 | 0 | DUP-015 |
| PA-a58d2a96e475 | `data/_rejected/AUDUSD_H1.csv` | QUARANTINED | HIGH | OHLCV | 12432 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 108 | 0 | 0 | 0 | 0 | 0 | DUP-012 |
| PA-5651cc34ce09 | `data/_rejected/AUDUSD_H4.csv` | QUARANTINED | HIGH | OHLCV | 3108 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 108 | 0 | 0 | 0 | 0 | 0 | DUP-004 |
| PA-0cf6a44d320e | `data/_rejected/EURCAD_H1.csv` | QUARANTINED | HIGH | OHLCV | 12431 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 109 | 0 | 0 | 0 | 0 | 0 | DUP-023 |
| PA-3f11e080230e | `data/_rejected/EURCAD_H4.csv` | QUARANTINED | HIGH | OHLCV | 3108 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 108 | 0 | 0 | 0 | 0 | 0 | DUP-020 |
| PA-fe84a75d14e7 | `data/_rejected/EURUSD_H1.csv` | QUARANTINED | HIGH | OHLCV | 12431 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 109 | 0 | 0 | 0 | 0 | 0 | DUP-018 |
| PA-3f1b723960c5 | `data/_rejected/EURUSD_H4.csv` | QUARANTINED | HIGH | OHLCV | 3108 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 108 | 0 | 0 | 0 | 0 | 0 | DUP-007 |
| PA-1b4e479f6d76 | `data/_rejected/GBPUSD_H1.csv` | QUARANTINED | HIGH | OHLCV | 12431 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 109 | 0 | 0 | 0 | 0 | 0 | DUP-011 |
| PA-d5ef229042e5 | `data/_rejected/GBPUSD_H4.csv` | QUARANTINED | HIGH | OHLCV | 3108 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 108 | 0 | 0 | 0 | 0 | 0 | DUP-022 |
| PA-33851542e84b | `data/_rejected/USDJPY_H1.csv` | QUARANTINED | HIGH | OHLCV | 12431 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 109 | 0 | 0 | 0 | 0 | 0 | DUP-017 |
| PA-79192c7a3795 | `data/_rejected/USDJPY_H4.csv` | QUARANTINED | HIGH | OHLCV | 3108 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 108 | 0 | 0 | 0 | 0 | 0 | DUP-013 |
| PA-4081b7bf8331 | `data/_rejected/XAUUSD_H1.csv` | QUARANTINED | HIGH | OHLCV | 11828 | 2024-05-22 01:00:00 | 2026-05-21 23:00:00 | 3600 | 515 | 0 | 0 | 0 | 0 | 0 | DUP-003 |
| PA-e624c0d864ba | `data/_rejected/XAUUSD_H4.csv` | QUARANTINED | HIGH | OHLCV | 3095 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 108 | 0 | 0 | 0 | 0 | 0 | DUP-005 |
| PA-f37ff6dfa382 | `data/binance/BNBUSDT_H1.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 17520 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-46a00cad673f | `data/binance/BNBUSDT_H4.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 4380 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-1e057efa77e9 | `data/binance/BNBUSDT_M15.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 | DUP-002 |
| PA-4dce166d5509 | `data/binance/BNBUSDT_M5.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 210240 | 2024-05-22 00:00:00 | 2026-05-21 23:55:00 | 300 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-13709e993566 | `data/binance/BTCUSDT_H1.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 17520 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-ce776b52fa54 | `data/binance/BTCUSDT_H1_purge_scan.csv` | DERIVED | MEDIUM | OHLCV_PLUS_EXTRA | 17520 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-900aa21a4701 | `data/binance/BTCUSDT_H1_setups.csv` | EXCLUDED | HIGH | NON_OHLCV | 202 |  |  |  |  |  |  |  |  |  |  |
| PA-754404b04e9a | `data/binance/BTCUSDT_H1_setups_continuation.csv` | EXCLUDED | HIGH | NON_OHLCV | 202 |  |  |  |  |  |  |  |  |  |  |
| PA-cc7bb2d6d0a0 | `data/binance/BTCUSDT_H1_setups_reversion.csv` | EXCLUDED | HIGH | NON_OHLCV | 202 |  |  |  |  |  |  |  |  |  |  |
| PA-635245527508 | `data/binance/BTCUSDT_H4.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 4380 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-659c10338113 | `data/binance/BTCUSDT_M15.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-85e250001d9d | `data/binance/BTCUSDT_M5.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 210240 | 2024-05-22 00:00:00 | 2026-05-21 23:55:00 | 300 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-de76dab9aca2 | `data/binance/DOGEUSDT_H1.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 17520 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-52b9a93e642b | `data/binance/DOGEUSDT_H4.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 4380 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-d56597c95989 | `data/binance/DOGEUSDT_M15.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-d3aa56373c69 | `data/binance/DOGEUSDT_M5.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 210240 | 2024-05-22 00:00:00 | 2026-05-21 23:55:00 | 300 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-105f678475ba | `data/binance/ETHUSDT_H1.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 17520 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-ad61aca9bdee | `data/binance/ETHUSDT_H4.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 4380 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-8b36d8debc2b | `data/binance/ETHUSDT_M15.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-abf33fe41642 | `data/binance/ETHUSDT_M5.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 210240 | 2024-05-22 00:00:00 | 2026-05-21 23:55:00 | 300 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-db0cd5588057 | `data/binance/SOLUSDT_H1.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 17520 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-c90479bb1b5c | `data/binance/SOLUSDT_H4.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 4380 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-f391f80e364a | `data/binance/SOLUSDT_M15.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 | DUP-021 |
| PA-4605d88fe150 | `data/binance/SOLUSDT_M5.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 210240 | 2024-05-22 00:00:00 | 2026-05-21 23:55:00 | 300 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-404af64dfeb6 | `data/binance/XRPUSDT_H1.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 17520 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-819570e09891 | `data/binance/XRPUSDT_H4.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 4380 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-b4938df7fcf9 | `data/binance/XRPUSDT_M15.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-d55e140361ce | `data/binance/XRPUSDT_M5.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 210240 | 2024-05-22 00:00:00 | 2026-05-21 23:55:00 | 300 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-81ca17a7696a | `data/mt5/AUDUSD_H1.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 12432 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 108 | 0 | 0 | 0 | 0 | 0 | DUP-012 |
| PA-56128ada9cb3 | `data/mt5/AUDUSD_H4.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 3108 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 108 | 0 | 0 | 0 | 0 | 0 | DUP-004 |
| PA-b1ab7ba16382 | `data/mt5/AUDUSD_M15.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 49722 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 109 | 0 | 0 | 0 | 0 | 0 | DUP-027 |
| PA-518746b89641 | `data/mt5/AUDUSD_M5.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 55037 | 2025-10-06 00:00:00 | 2026-07-02 05:25:00 | 300 | 45 | 0 | 0 | 0 | 0 | 0 |  |
| PA-c9c009668041 | `data/mt5/EURCAD_H1.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 12431 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 109 | 0 | 0 | 0 | 0 | 0 | DUP-023 |
| PA-3f55fde7ad35 | `data/mt5/EURCAD_H4.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 3108 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 108 | 0 | 0 | 0 | 0 | 0 | DUP-020 |
| PA-cc101306964e | `data/mt5/EURCAD_M15.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 49715 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 110 | 0 | 0 | 0 | 0 | 0 | DUP-001 |
| PA-3a0430afd2db | `data/mt5/EURCAD_M5.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 54993 | 2025-10-06 00:00:00 | 2026-07-02 05:25:00 | 300 | 50 | 0 | 0 | 0 | 0 | 0 |  |
| PA-36886dfbcd45 | `data/mt5/EURUSD_H1.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 12431 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 109 | 0 | 0 | 0 | 0 | 0 | DUP-018 |
| PA-cb6cbdbad4d0 | `data/mt5/EURUSD_H4.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 3108 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 108 | 0 | 0 | 0 | 0 | 0 | DUP-007 |
| PA-b07b0d304dad | `data/mt5/EURUSD_M15.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 49721 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 109 | 0 | 0 | 5 | 0 | 0 | DUP-009 |
| PA-a404223ea2c1 | `data/mt5/EURUSD_M5.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 55017 | 2025-10-06 00:00:00 | 2026-07-02 05:20:00 | 300 | 48 | 0 | 0 | 18 | 0 | 0 |  |
| PA-9fc770304a39 | `data/mt5/GBPUSD_H1.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 12431 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 109 | 0 | 0 | 0 | 0 | 0 | DUP-011 |
| PA-753aeb9ae1e9 | `data/mt5/GBPUSD_H4.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 3108 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 108 | 0 | 0 | 0 | 0 | 0 | DUP-022 |
| PA-1116495e863c | `data/mt5/GBPUSD_M15.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 49716 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 110 | 0 | 0 | 0 | 0 | 0 | DUP-019 |
| PA-edaabdb82c3f | `data/mt5/GBPUSD_M5.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 54999 | 2025-10-06 00:00:00 | 2026-07-02 05:25:00 | 300 | 49 | 0 | 0 | 0 | 0 | 0 |  |
| PA-9dede99f2529 | `data/mt5/USDJPY_H1.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 12431 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 109 | 0 | 0 | 0 | 0 | 0 | DUP-017 |
| PA-5c533751969e | `data/mt5/USDJPY_H4.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 3108 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 108 | 0 | 0 | 0 | 0 | 0 | DUP-013 |
| PA-ba3ca9778068 | `data/mt5/USDJPY_M15.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 49716 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 110 | 0 | 0 | 0 | 0 | 0 | DUP-006 |
| PA-646952a85964 | `data/mt5/USDJPY_M5.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 55000 | 2025-10-06 00:00:00 | 2026-07-02 05:25:00 | 300 | 49 | 0 | 0 | 0 | 0 | 0 |  |
| PA-98c68c6abc42 | `data/mt5/XAUUSD_H1.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 11828 | 2024-05-22 01:00:00 | 2026-05-21 23:00:00 | 3600 | 515 | 0 | 0 | 0 | 0 | 0 | DUP-003 |
| PA-642ea9bde2aa | `data/mt5/XAUUSD_H4.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 3095 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 108 | 0 | 0 | 0 | 0 | 0 | DUP-005 |
| PA-134568d12172 | `data/mt5/XAUUSD_M15.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 47275 | 2024-05-22 01:00:00 | 2026-05-21 23:45:00 | 900 | 516 | 0 | 0 | 0 | 0 | 0 |  |
| PA-7055c088853d | `data/mt5/XAUUSD_M15_second_low_events.csv` | EXCLUDED | HIGH | NON_OHLCV | 28 |  |  |  |  |  |  |  |  |  |  |
| PA-01f95ed3a1d1 | `data/mt5/XAUUSD_M15_second_low_metrics.csv` | EXCLUDED | HIGH | NON_OHLCV | 28 |  |  |  |  |  |  |  |  |  |  |
| PA-1dd2b46b67b3 | `data/mt5/XAUUSD_M15_second_low_scan.csv` | DERIVED | MEDIUM | OHLCV_PLUS_EXTRA | 47275 | 2024-05-22 01:00:00 | 2026-05-21 23:45:00 | 900 | 516 | 0 | 0 | 0 | 0 | 0 |  |
| PA-40fa1c59a094 | `data/mt5/XAUUSD_M5.csv` | AUTHORITATIVE_RAW | MEDIUM | OHLCV | 52198 | 2025-10-06 01:00:00 | 2026-07-02 05:25:00 | 300 | 198 | 0 | 0 | 0 | 0 | 0 |  |
| PA-0e5c08be8c11 | `data/mt5/_rejected/ADAUSD_H1.csv` | QUARANTINED | HIGH | OHLCV | 17463 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 11 | 0 | 0 | 0 | 0 | 0 |  |
| PA-6ad435edbc42 | `data/mt5/_rejected/ADAUSD_H4.csv` | QUARANTINED | HIGH | OHLCV | 4371 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 4 | 0 | 0 | 0 | 0 | 0 |  |
| PA-ca00f7233600 | `data/mt5/_rejected/ADAUSD_M15.csv` | QUARANTINED | HIGH | OHLCV | 69372 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 175 | 0 | 0 | 0 | 0 | 0 |  |
| PA-3bae3373773c | `data/mt5/_rejected/ADAUSD_M5.csv` | QUARANTINED | HIGH | OHLCV | 76750 | 2025-10-05 05:30:00 | 2026-07-02 05:25:00 | 300 | 178 | 0 | 0 | 0 | 0 | 0 |  |
| PA-59c0066af97e | `data/mt5/_rejected/AVXUSD_H1.csv` | QUARANTINED | HIGH | OHLCV | 17478 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 17 | 0 | 0 | 0 | 0 | 0 |  |
| PA-f079438afc0c | `data/mt5/_rejected/AVXUSD_H4.csv` | QUARANTINED | HIGH | OHLCV | 4376 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 3 | 0 | 0 | 0 | 0 | 0 |  |
| PA-4b459c869581 | `data/mt5/_rejected/AVXUSD_M15.csv` | QUARANTINED | HIGH | OHLCV | 69399 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 188 | 0 | 0 | 0 | 0 | 0 |  |
| PA-b261d96af4a4 | `data/mt5/_rejected/AVXUSD_M5.csv` | QUARANTINED | HIGH | OHLCV | 76829 | 2025-10-05 05:30:00 | 2026-07-02 05:25:00 | 300 | 204 | 0 | 0 | 0 | 0 | 0 |  |
| PA-ccebd28bc328 | `data/mt5/_rejected/BCHUSD_H1.csv` | QUARANTINED | HIGH | OHLCV | 17482 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 21 | 0 | 0 | 0 | 0 | 0 |  |
| PA-a945a9725aa1 | `data/mt5/_rejected/BCHUSD_H4.csv` | QUARANTINED | HIGH | OHLCV | 4377 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 2 | 0 | 0 | 0 | 0 | 0 |  |
| PA-f35e4f938697 | `data/mt5/_rejected/BCHUSD_M15.csv` | QUARANTINED | HIGH | OHLCV | 69628 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 118 | 0 | 0 | 0 | 0 | 0 |  |
| PA-a2edef2d58c3 | `data/mt5/_rejected/BCHUSD_M5.csv` | QUARANTINED | HIGH | OHLCV | 76754 | 2025-10-05 05:30:00 | 2026-07-02 05:25:00 | 300 | 314 | 0 | 0 | 0 | 0 | 0 |  |
| PA-7e7818f959a4 | `data/mt5/_rejected/BNBUSD_H1.csv` | QUARANTINED | HIGH | OHLCV | 17449 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 17 | 0 | 0 | 0 | 0 | 0 |  |
| PA-c117aa84a135 | `data/mt5/_rejected/BNBUSD_H4.csv` | QUARANTINED | HIGH | OHLCV | 4368 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 5 | 0 | 0 | 0 | 0 | 0 |  |
| PA-5157d4eba9c0 | `data/mt5/_rejected/BNBUSD_M15.csv` | QUARANTINED | HIGH | OHLCV | 69247 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 200 | 0 | 0 | 0 | 0 | 0 |  |
| PA-6f36d8a5adc0 | `data/mt5/_rejected/BNBUSD_M5.csv` | QUARANTINED | HIGH | OHLCV | 76616 | 2025-10-05 05:30:00 | 2026-07-02 05:25:00 | 300 | 201 | 0 | 0 | 0 | 0 | 0 |  |
| PA-c75cf9719e5a | `data/mt5/_rejected/BTCUSD_H1.csv` | QUARANTINED | HIGH | OHLCV | 17495 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 8 | 0 | 0 | 0 | 0 | 0 |  |
| PA-4c3b1e446ef7 | `data/mt5/_rejected/BTCUSD_H4.csv` | QUARANTINED | HIGH | OHLCV | 4377 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 2 | 0 | 0 | 0 | 0 | 0 |  |
| PA-f12fdd9594d1 | `data/mt5/_rejected/BTCUSD_M15.csv` | QUARANTINED | HIGH | OHLCV | 69639 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 120 | 0 | 0 | 0 | 0 | 0 |  |
| PA-a7ac984be619 | `data/mt5/_rejected/BTCUSD_M5.csv` | QUARANTINED | HIGH | OHLCV | 75693 | 2025-10-05 05:30:00 | 2026-07-02 05:25:00 | 300 | 146 | 0 | 0 | 0 | 0 | 0 |  |
| PA-bf08a0c8e43e | `data/mt5/_rejected/DOGUSD_H1.csv` | QUARANTINED | HIGH | OHLCV | 17481 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 15 | 0 | 0 | 0 | 0 | 0 |  |
| PA-1b5ef733d091 | `data/mt5/_rejected/DOGUSD_H4.csv` | QUARANTINED | HIGH | OHLCV | 4376 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 3 | 0 | 0 | 0 | 0 | 0 |  |
| PA-382b1a014bc7 | `data/mt5/_rejected/DOGUSD_M15.csv` | QUARANTINED | HIGH | OHLCV | 69435 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 177 | 0 | 0 | 0 | 0 | 0 |  |
| PA-0ec60b04826f | `data/mt5/_rejected/DOGUSD_M5.csv` | QUARANTINED | HIGH | OHLCV | 76883 | 2025-10-05 05:30:00 | 2026-07-02 05:25:00 | 300 | 208 | 0 | 0 | 0 | 0 | 0 |  |
| PA-c063ba3ea4bf | `data/mt5/_rejected/DOTUSD_H1.csv` | QUARANTINED | HIGH | OHLCV | 16958 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 147 | 0 | 0 | 0 | 0 | 0 |  |
| PA-f4189d13ec62 | `data/mt5/_rejected/DOTUSD_H4.csv` | QUARANTINED | HIGH | OHLCV | 4310 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 67 | 0 | 0 | 0 | 0 | 0 |  |
| PA-bb65300c9690 | `data/mt5/_rejected/DOTUSD_M15.csv` | QUARANTINED | HIGH | OHLCV | 67627 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 220 | 0 | 0 | 0 | 0 | 0 |  |
| PA-fb61920832fe | `data/mt5/_rejected/DOTUSD_M5.csv` | QUARANTINED | HIGH | OHLCV | 76742 | 2025-10-05 05:30:00 | 2026-07-02 05:25:00 | 300 | 319 | 0 | 0 | 0 | 0 | 0 |  |
| PA-9819103cb9ee | `data/mt5/_rejected/ETHUSD_H1.csv` | QUARANTINED | HIGH | OHLCV | 17493 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 10 | 0 | 0 | 0 | 0 | 0 |  |
| PA-dfe6edf33d47 | `data/mt5/_rejected/ETHUSD_H4.csv` | QUARANTINED | HIGH | OHLCV | 4377 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 2 | 0 | 0 | 0 | 0 | 0 |  |
| PA-543618314835 | `data/mt5/_rejected/ETHUSD_M15.csv` | QUARANTINED | HIGH | OHLCV | 69626 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 122 | 0 | 0 | 0 | 0 | 0 |  |
| PA-74f3074297b0 | `data/mt5/_rejected/ETHUSD_M5.csv` | QUARANTINED | HIGH | OHLCV | 76865 | 2025-10-05 05:30:00 | 2026-07-02 05:25:00 | 300 | 145 | 0 | 0 | 0 | 0 | 0 |  |
| PA-dfd7e26a5992 | `data/mt5/_rejected/KSMUSD_H1.csv` | QUARANTINED | HIGH | OHLCV | 17482 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 15 | 0 | 0 | 0 | 0 | 0 |  |
| PA-fb8b33ed3bb5 | `data/mt5/_rejected/KSMUSD_H4.csv` | QUARANTINED | HIGH | OHLCV | 4376 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 3 | 0 | 0 | 0 | 0 | 0 |  |
| PA-4df2f77b7d60 | `data/mt5/_rejected/KSMUSD_M15.csv` | QUARANTINED | HIGH | OHLCV | 69410 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 191 | 0 | 0 | 0 | 0 | 0 |  |
| PA-2b1a2f971229 | `data/mt5/_rejected/KSMUSD_M5.csv` | QUARANTINED | HIGH | OHLCV | 76980 | 2025-10-05 05:30:00 | 2026-07-02 05:25:00 | 300 | 88 | 0 | 0 | 0 | 0 | 0 |  |
| PA-63422b5daf6a | `data/mt5/_rejected/LNKUSD_H1.csv` | QUARANTINED | HIGH | OHLCV | 16955 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 144 | 0 | 0 | 0 | 0 | 0 |  |
| PA-4765ce6a89e6 | `data/mt5/_rejected/LNKUSD_H4.csv` | QUARANTINED | HIGH | OHLCV | 4309 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 68 | 0 | 0 | 0 | 0 | 0 |  |
| PA-79322e7951a3 | `data/mt5/_rejected/LNKUSD_M15.csv` | QUARANTINED | HIGH | OHLCV | 67578 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 229 | 0 | 0 | 0 | 0 | 0 |  |
| PA-057e6dfaa944 | `data/mt5/_rejected/LNKUSD_M5.csv` | QUARANTINED | HIGH | OHLCV | 76888 | 2025-10-05 05:30:00 | 2026-07-02 05:30:00 | 300 | 210 | 0 | 0 | 0 | 0 | 0 |  |
| PA-5852b63e78c7 | `data/mt5/_rejected/LTCUSD_H1.csv` | QUARANTINED | HIGH | OHLCV | 17474 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 28 | 0 | 0 | 0 | 0 | 0 |  |
| PA-c2265a27f68b | `data/mt5/_rejected/LTCUSD_H4.csv` | QUARANTINED | HIGH | OHLCV | 4377 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 2 | 0 | 0 | 0 | 0 | 0 |  |
| PA-e00067ab6156 | `data/mt5/_rejected/LTCUSD_M15.csv` | QUARANTINED | HIGH | OHLCV | 69621 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 116 | 0 | 0 | 0 | 0 | 0 |  |
| PA-d72b356f3e90 | `data/mt5/_rejected/LTCUSD_M5.csv` | QUARANTINED | HIGH | OHLCV | 76839 | 2025-10-05 05:30:00 | 2026-07-02 05:30:00 | 300 | 228 | 0 | 0 | 0 | 0 | 0 |  |
| PA-1437ff8d3d6e | `data/mt5/_rejected/POLUSD_H1.csv` | QUARANTINED | HIGH | OHLCV | 17463 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 18 | 0 | 0 | 0 | 0 | 0 |  |
| PA-ab66530fa3ca | `data/mt5/_rejected/POLUSD_H4.csv` | QUARANTINED | HIGH | OHLCV | 4375 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 3 | 0 | 0 | 0 | 0 | 0 |  |
| PA-b8a0492f798a | `data/mt5/_rejected/POLUSD_M15.csv` | QUARANTINED | HIGH | OHLCV | 69302 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 201 | 0 | 0 | 0 | 0 | 0 |  |
| PA-7f1284f8f7b5 | `data/mt5/_rejected/POLUSD_M5.csv` | QUARANTINED | HIGH | OHLCV | 76695 | 2025-10-05 05:35:00 | 2026-07-02 05:30:00 | 300 | 98 | 0 | 0 | 0 | 0 | 0 |  |
| PA-32ffd77b1a8d | `data/mt5/_rejected/SOLUSD_H1.csv` | QUARANTINED | HIGH | OHLCV | 12110 | 2025-01-01 00:00:00 | 2026-05-21 23:00:00 | 3600 | 14 | 0 | 0 | 0 | 0 | 0 |  |
| PA-b50ba0aa0e6c | `data/mt5/_rejected/SOLUSD_H4.csv` | QUARANTINED | HIGH | OHLCV | 3032 | 2025-01-01 00:00:00 | 2026-05-21 20:00:00 | 14400 | 3 | 0 | 0 | 0 | 0 | 0 |  |
| PA-2bf8e67ba027 | `data/mt5/_rejected/SOLUSD_M15.csv` | QUARANTINED | HIGH | OHLCV | 48216 | 2025-01-01 00:00:00 | 2026-05-21 23:45:00 | 900 | 86 | 0 | 0 | 0 | 0 | 0 |  |
| PA-30ed824338ec | `data/mt5/_rejected/SOLUSD_M5.csv` | QUARANTINED | HIGH | OHLCV | 76886 | 2025-10-05 05:35:00 | 2026-07-02 05:30:00 | 300 | 220 | 0 | 0 | 0 | 0 | 0 |  |
| PA-d41e0823d61d | `data/mt5/_rejected/UNIUSD_H1.csv` | QUARANTINED | HIGH | OHLCV | 17437 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 15 | 0 | 0 | 0 | 0 | 0 |  |
| PA-de26b5752881 | `data/mt5/_rejected/UNIUSD_H4.csv` | QUARANTINED | HIGH | OHLCV | 4365 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 4 | 0 | 0 | 0 | 0 | 0 |  |
| PA-4498ba2e96e8 | `data/mt5/_rejected/UNIUSD_M15.csv` | QUARANTINED | HIGH | OHLCV | 69258 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 187 | 0 | 0 | 0 | 0 | 0 |  |
| PA-7ee63f57b93d | `data/mt5/_rejected/UNIUSD_M5.csv` | QUARANTINED | HIGH | OHLCV | 76327 | 2025-10-05 05:35:00 | 2026-07-02 05:30:00 | 300 | 196 | 0 | 0 | 0 | 0 | 0 |  |
| PA-3d949a1fa254 | `data/mt5/_rejected/XAUUSD_M15.csv` | QUARANTINED | HIGH | OHLCV | 50169 | 2024-05-22 01:00:00 | 2026-07-06 23:45:00 | 900 | 550 | 0 | 0 | 0 | 0 | 0 | DUP-008 |
| PA-0eb7fa65b135 | `data/mt5/_rejected/XLMUSD_H1.csv` | QUARANTINED | HIGH | OHLCV | 17225 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 77 | 0 | 0 | 0 | 0 | 0 |  |
| PA-c826feef36a0 | `data/mt5/_rejected/XLMUSD_H4.csv` | QUARANTINED | HIGH | OHLCV | 4343 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 33 | 0 | 0 | 0 | 0 | 0 |  |
| PA-1614b10d7214 | `data/mt5/_rejected/XLMUSD_M15.csv` | QUARANTINED | HIGH | OHLCV | 68502 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 209 | 0 | 0 | 0 | 0 | 0 |  |
| PA-993c53b003d1 | `data/mt5/_rejected/XLMUSD_M5.csv` | QUARANTINED | HIGH | OHLCV | 76682 | 2025-10-05 05:35:00 | 2026-07-02 05:30:00 | 300 | 94 | 0 | 0 | 0 | 0 | 0 |  |
| PA-417c1ee9bed3 | `data/mt5/_rejected/XRPUSD_H1.csv` | QUARANTINED | HIGH | OHLCV | 12116 | 2025-01-01 00:00:00 | 2026-05-21 23:00:00 | 3600 | 11 | 0 | 0 | 0 | 0 | 0 |  |
| PA-5e3068568855 | `data/mt5/_rejected/XRPUSD_H4.csv` | QUARANTINED | HIGH | OHLCV | 3033 | 2025-01-01 00:00:00 | 2026-05-21 20:00:00 | 14400 | 2 | 0 | 0 | 0 | 0 | 0 |  |
| PA-ea6d0d557766 | `data/mt5/_rejected/XRPUSD_M15.csv` | QUARANTINED | HIGH | OHLCV | 48233 | 2025-01-01 00:00:00 | 2026-05-21 23:45:00 | 900 | 83 | 0 | 0 | 0 | 0 | 0 |  |
| PA-096afe64bd32 | `data/mt5/_rejected/XRPUSD_M5.csv` | QUARANTINED | HIGH | OHLCV | 76813 | 2025-10-05 05:35:00 | 2026-07-02 05:30:00 | 300 | 228 | 0 | 0 | 0 | 0 | 0 |  |
| PA-4fdc8b30a107 | `data/mt5/_rejected/XTZUSD_H1.csv` | QUARANTINED | HIGH | OHLCV | 17435 | 2024-05-22 00:00:00 | 2026-05-21 23:00:00 | 3600 | 17 | 0 | 0 | 0 | 0 | 0 |  |
| PA-c821d1a1f29f | `data/mt5/_rejected/XTZUSD_H4.csv` | QUARANTINED | HIGH | OHLCV | 4365 | 2024-05-22 00:00:00 | 2026-05-21 20:00:00 | 14400 | 5 | 0 | 0 | 0 | 0 | 0 |  |
| PA-816bca693df0 | `data/mt5/_rejected/XTZUSD_M15.csv` | QUARANTINED | HIGH | OHLCV | 69190 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 236 | 0 | 0 | 0 | 0 | 0 |  |
| PA-f6c39b8cb57f | `data/mt5/_rejected/XTZUSD_M5.csv` | QUARANTINED | HIGH | OHLCV | 75066 | 2025-10-05 05:35:00 | 2026-07-02 05:30:00 | 300 | 1074 | 0 | 0 | 0 | 0 | 0 |  |
| PA-54bdc6307efa | `data/perp/BNBUSDT_BASIS_M15.csv` | EXCLUDED | HIGH | NON_OHLCV | 70080 |  |  |  |  |  |  |  |  |  |  |
| PA-81d45df7b43d | `data/perp/BNBUSDT_FUNDING_8H.csv` | EXCLUDED | HIGH | NON_OHLCV | 2190 |  |  |  |  |  |  |  |  |  |  |
| PA-38fc1723335b | `data/perp/BTCUSDT_BASIS_M15.csv` | EXCLUDED | HIGH | NON_OHLCV | 70080 |  |  |  |  |  |  |  |  |  |  |
| PA-515dc38f49c3 | `data/perp/BTCUSDT_FUNDING_8H.csv` | EXCLUDED | HIGH | NON_OHLCV | 2190 |  |  |  |  |  |  |  |  |  |  |
| PA-f1a775548873 | `data/perp/DOGEUSDT_BASIS_M15.csv` | EXCLUDED | HIGH | NON_OHLCV | 70080 |  |  |  |  |  |  |  |  |  |  |
| PA-c7692b4b6399 | `data/perp/DOGEUSDT_FUNDING_8H.csv` | EXCLUDED | HIGH | NON_OHLCV | 2190 |  |  |  |  |  |  |  |  |  |  |
| PA-6fd5b01d4c2b | `data/perp/ETHUSDT_BASIS_M15.csv` | EXCLUDED | HIGH | NON_OHLCV | 70080 |  |  |  |  |  |  |  |  |  |  |
| PA-7fdc90a093e0 | `data/perp/ETHUSDT_FUNDING_8H.csv` | EXCLUDED | HIGH | NON_OHLCV | 2190 |  |  |  |  |  |  |  |  |  |  |
| PA-6ed1b858339c | `data/perp/SOLUSDT_BASIS_M15.csv` | EXCLUDED | HIGH | NON_OHLCV | 70080 |  |  |  |  |  |  |  |  |  |  |
| PA-784b79dc2c53 | `data/perp/SOLUSDT_FUNDING_8H.csv` | EXCLUDED | HIGH | NON_OHLCV | 2190 |  |  |  |  |  |  |  |  |  |  |
| PA-9fa5ce030abf | `data/perp/XRPUSDT_BASIS_M15.csv` | EXCLUDED | HIGH | NON_OHLCV | 70080 |  |  |  |  |  |  |  |  |  |  |
| PA-43b3e476416b | `data/perp/XRPUSDT_FUNDING_8H.csv` | EXCLUDED | HIGH | NON_OHLCV | 2190 |  |  |  |  |  |  |  |  |  |  |
| PA-a4815c532b24 | `data/resampled/BNBUSDT_H1.csv` | DERIVED | MEDIUM | OHLCV | 17519 | 2024-05-22 00:00:00 | 2026-05-21 22:00:00 | 3600 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-1f32508a26e0 | `data/resampled/BNBUSDT_H4.csv` | DERIVED | MEDIUM | OHLCV | 4379 | 2024-05-22 00:00:00 | 2026-05-21 16:00:00 | 14400 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-50f4d36f0c2a | `data/resampled/BTCUSDT_H1.csv` | DERIVED | MEDIUM | OHLCV | 17519 | 2024-05-22 00:00:00 | 2026-05-21 22:00:00 | 3600 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-887945f85e65 | `data/resampled/BTCUSDT_H4.csv` | DERIVED | MEDIUM | OHLCV | 4379 | 2024-05-22 00:00:00 | 2026-05-21 16:00:00 | 14400 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-58008954a73d | `data/resampled/ETHUSDT_H1.csv` | DERIVED | MEDIUM | OHLCV | 17519 | 2024-05-22 00:00:00 | 2026-05-21 22:00:00 | 3600 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-72d229a21c61 | `data/resampled/ETHUSDT_H4.csv` | DERIVED | MEDIUM | OHLCV | 4379 | 2024-05-22 00:00:00 | 2026-05-21 16:00:00 | 14400 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-e03b3d0e90de | `data/resampled/SOLUSDT_H1.csv` | DERIVED | MEDIUM | OHLCV | 17519 | 2024-05-22 00:00:00 | 2026-05-21 22:00:00 | 3600 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-57c826af50c1 | `data/resampled/SOLUSDT_H4.csv` | DERIVED | MEDIUM | OHLCV | 4379 | 2024-05-22 00:00:00 | 2026-05-21 16:00:00 | 14400 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-1a7f680cb740 | `data/yfinance/AUDUSD_M15.csv` | AUTHORITATIVE_RAW | LOW | OHLCV | 2275 | 2026-04-17 04:00:00 | 2026-05-22 08:45:00 | 900 | 25 | 0 | 0 | 0 | 0 | 0 | DUP-014 |
| PA-84306c5495ad | `data/yfinance/BNBUSDT_20240522_20260521_Part_1.csv` | DERIVED | MEDIUM | OHLCV | 14016 | 2024-05-22 00:00:00 | 2024-10-14 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-5dc4e6cdf121 | `data/yfinance/BNBUSDT_20240522_20260521_Part_1_Isolated.csv` | DERIVED | MEDIUM | OHLCV | 14016 | 2024-05-22 00:00:00 | 2024-10-14 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-70aeab13ccd7 | `data/yfinance/BNBUSDT_20240522_20260521_Part_2.csv` | DERIVED | MEDIUM | OHLCV | 14016 | 2024-10-15 00:00:00 | 2025-03-09 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-720662793ab9 | `data/yfinance/BNBUSDT_20240522_20260521_Part_3.csv` | DERIVED | MEDIUM | OHLCV | 14016 | 2025-03-10 00:00:00 | 2025-08-02 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-1c547fc81f1e | `data/yfinance/BNBUSDT_20240522_20260521_Part_4.csv` | DERIVED | MEDIUM | OHLCV | 14016 | 2025-08-03 00:00:00 | 2025-12-26 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-f18d0ae58fe7 | `data/yfinance/BNBUSDT_20240522_20260521_Part_5.csv` | DERIVED | MEDIUM | OHLCV | 14016 | 2025-12-27 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| PA-43ba68385abe | `data/yfinance/BNBUSDT_M15.csv` | AUTHORITATIVE_RAW | LOW | OHLCV | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 | DUP-002 |
| PA-1bfd6fc41a0d | `data/yfinance/BTCUSDT_M15.csv` | AUTHORITATIVE_RAW | LOW | OHLCV | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 | DUP-024 |
| PA-6c451292e5b4 | `data/yfinance/DOGEUSDT_M15.csv` | AUTHORITATIVE_RAW | LOW | OHLCV | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 | DUP-010 |
| PA-edf475039377 | `data/yfinance/ETHUSDT_M15.csv` | AUTHORITATIVE_RAW | LOW | OHLCV | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 | DUP-026 |
| PA-94e21ce42681 | `data/yfinance/EURCAD_M15.csv` | AUTHORITATIVE_RAW | LOW | OHLCV | 2274 | 2026-04-17 04:00:00 | 2026-05-22 08:45:00 | 900 | 25 | 0 | 0 | 0 | 0 | 0 | DUP-028 |
| PA-99371d051d80 | `data/yfinance/GBPUSD_M15.csv` | AUTHORITATIVE_RAW | LOW | OHLCV | 2274 | 2026-04-17 04:00:00 | 2026-05-22 08:45:00 | 900 | 25 | 0 | 0 | 0 | 0 | 0 | DUP-025 |
| PA-d5182a4aca1d | `data/yfinance/SOLUSDT_M15.csv` | AUTHORITATIVE_RAW | LOW | OHLCV | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 | DUP-021 |
| PA-4082dcb5552a | `data/yfinance/USDJPY_M15.csv` | AUTHORITATIVE_RAW | LOW | OHLCV | 2274 | 2026-04-17 04:00:00 | 2026-05-22 08:45:00 | 900 | 25 | 0 | 0 | 0 | 0 | 0 | DUP-016 |
| PA-faaf7e23544f | `data/yfinance/XAUUSD_M15.csv` | AUTHORITATIVE_RAW | LOW | OHLCV | 2294 | 2026-04-17 04:00:00 | 2026-05-22 08:45:00 | 900 | 26 | 0 | 0 | 0 | 0 | 0 | DUP-015 |
| PA-c14b338e42c8 | `data/yfinance/XRPUSDT_M15.csv` | AUTHORITATIVE_RAW | LOW | OHLCV | 70080 | 2024-05-22 00:00:00 | 2026-05-21 23:45:00 | 900 | 0 | 0 | 0 | 0 | 0 | 0 | DUP-029 |

## Latent volume-substitution exposure

`FeaturePipeline.compute_volume_features` (src/features/feature_pipeline.py:202-233)
substitutes `high-low` into `volume` when a frame's volume column is ALL-zero.
Artifacts whose ENTIRE volume column is zero (would activate the proxy): **0**

## What this census did NOT do

- No closure verdict, no BLOCKER adjudication (PASS B).
- No session-aware gap gating (that is `dataset_integrity.validate_dataset`).
- No remediation, no file moves, no quarantining.
- No economic claim of any kind.
- Parquet artifacts hashed but not parsed (stdlib constraint) — stats UNKNOWN.

```text
OHLCV_CENSUS_FILES = 224
OHLCV_CENSUS_LOGICAL = 48
OHLCV_CENSUS_AMBIGUOUS_LOGICAL = 12
OHLCV_CENSUS_SAME_LOGICAL_DIFFERENT_BYTES = 9
OHLCV_CENSUS_ALL_ZERO_VOLUME_FILES = 0
OHLCV_CENSUS_STATUS = EVIDENCE_FROZEN
NEXT = PASS-A lineage / temporal / contradiction artifacts; closure = PASS B
```
