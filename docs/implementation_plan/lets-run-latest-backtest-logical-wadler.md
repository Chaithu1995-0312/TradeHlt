# FX/metals via MT5 — install, build MT5→CSV fetcher, then resume the qualification

## Context
The FX/metals cross-asset check (the chosen open frontier; F-029 OPEN) is **data-blocked**: the
on-disk FX CSVs are only ~5 weeks. Alpha Vantage free tier was the first attempt but `FX_INTRADAY`
is **premium-only** (proven by a 1-request probe). $50/mo premium was rejected; MT5 chosen as the
**free** source. (The env-var key wiring for the AV fetcher already shipped and stays — it's the
right pattern if a premium key ever appears.)

This plan covers: MT5 setup → a dedicated **MT5→CSV fetcher** (clean UTC M15, no timezone/resample
wrangling) → fetch EURUSD first (user's pick) → validate → then resume the already-approved FX/metals
M4 qualification.

**Why a new fetcher, not `historical_fetcher.py`:** that module has the right MT5 fetch logic
(`_fetch_from_mt5` → `mt5.copy_rates_range` → UTC OHLCV) but is **TimescaleDB-centric** with no
MT5→CSV writer (its CSV path is read-only fallback), and there's no DB here. A thin dedicated
fetcher mirroring `AlphaVantageCandleFetcher` is cleaner and reuses the proven conversion.

## Phase A — MT5 terminal (YOU, on this Windows machine)
1. Install the **MetaTrader 5** terminal (metaquotes.net or any broker).
2. Open a **free demo account** (MetaQuotes demo works) and log in — this grants historical-data
   access.
3. Leave the terminal **running and logged in** (the Python API attaches to the live terminal).
4. In Market Watch, confirm the symbols exist and note the broker's **gold** symbol (often
   `XAUUSD`, sometimes `GOLD`).

## Phase B — MT5 Python package (GATE — I run)
- `pip install MetaTrader5` on the active interpreter (**Python 3.14.3 / win32**).
- **#1 RISK / GATE:** `MetaTrader5` may have **no cp314 wheel** (3.14 is very new). If install fails
  → create a **Python 3.11/3.12 venv used only for the fetch step** (the fetcher emits plain CSV, so
  only this step needs the venv; the entire downstream pipeline runs on 3.14).
- Verify: `python -c "import MetaTrader5 as m; print(m.initialize())"` connects to the running
  terminal (`initialize()` → True).

## Phase C — Build the MT5→CSV fetcher (I build)
- **new** `src/inout/mt5_candle_fetcher.py` — `MT5CandleFetcher` + `MT5FetcherConfig.from_section`,
  mirroring [`AlphaVantageCandleFetcher`](src/inout/alphavantage_candle_fetcher.py). **Reuse the
  proven conversion** from [`historical_fetcher._fetch_from_mt5`](src/data_ingestion/historical_fetcher.py:462)
  (`copy_rates_range` → `datetime.fromtimestamp(r["time"], tz=utc)` → O/H/L/C/`tick_volume`). Writes
  the canonical `timestamp,open,high,low,close,volume` CSV via `ohlcv_schema`. Supports a
  **`--symbol` override** for broker-specific names (gold).
- **new** `scripts/data/fetch_candles_mt5.py` — thin CLI (`--pair`, `--timeframe M15`, `--start`,
  `--end`, `--out data`, `--symbol`), mirroring the AV CLI (thin wrapper; logic in `src/`).
- **config:** add a small hash-neutral `mt5_data` section (sibling to `data_ingestion`) for defaults,
  consumed via `from_section`/`_require` (config-first, no silent defaults).
- **No resampling needed** — MT5 serves native M15 in UTC, so `resample.py` and timezone surgery are
  not involved (the whole reason MT5 beats the free-CSV path).

## Phase D — Fetch EURUSD first, validate, then fan out
- `python scripts/data/fetch_candles_mt5.py --pair EURUSD --timeframe M15 --start 2024-05-01 --end 2026-05-01 --out data`
  (EURUSD isn't on disk → fresh file, no overwrite.)
- `python -m data_ingestion.dataset_integrity scan data` → expect APPROVE/WARN (session-aware FX gate).
- Then `AUDUSD, EURCAD, GBPUSD, USDJPY` + `XAUUSD` (broker symbol via `--symbol`). **Back up the
  existing 5-week files** to `data/_archive_5wk/` before replacing (look-before-overwrite).

## Phase E — Resume FX/metals qualification (already approved)
Build `scripts/research/qualify_fx_metals.py` + `configs/research/research_config_fx_metals.json` +
`research_config_spine_fx_metals.json` (clones of the `*_majors.json` pair, universe re-scoped,
`round_trip_bps=12.0` conservative, spine `prod_version=v2_multi_2026_04`). **Pre-register** (E-001
ritual), run the gate, prove determinism (run twice, byte-compare), register finding **F-035**, and
append the §6 SESSION LOG. Expectation: spine arm likely INSUFFICIENT (F-029); toy family is the
informative arm.

## Critical files
- **Reuse:** `src/data_ingestion/historical_fetcher.py` (`_fetch_from_mt5` conversion),
  `src/inout/alphavantage_candle_fetcher.py` (structure to mirror), `src/data_ingestion/ohlcv_schema.py`,
  `src/data_ingestion/dataset_integrity.py`, `src/research/qualification.py` + `runner.py` + `registry.py`.
- **New:** `src/inout/mt5_candle_fetcher.py`, `scripts/data/fetch_candles_mt5.py`,
  `scripts/research/qualify_fx_metals.py`, `configs/research/research_config_fx_metals.json`,
  `configs/research/research_config_spine_fx_metals.json`.
- **Data:** `data/{EURUSD,AUDUSD,EURCAD,GBPUSD,USDJPY,XAUUSD}_M15.csv` (5-week originals archived).

## Verification
1. `pip install MetaTrader5` succeeds (or venv fallback) **and** `mt5.initialize()` → True.
2. EURUSD fetch writes `data/EURUSD_M15.csv` with ~2yr of M15 bars, UTC, canonical schema.
3. `dataset_integrity scan data` → APPROVE/WARN, 0 REJECT.
4. `qualify_fx_metals` runs; **toy pooled n ≥ 30** (the power check that justified the fetch);
   determinism byte-identical across two runs; **F-035** registered; `tests/test_current_findings.py` green.

## Risks
- **MetaTrader5 no cp314 wheel** → Python 3.11/3.12 venv for the fetch step only.
- **MT5 history depth is broker-dependent** — `copy_rates_range` may need the terminal to download
  history first; demo accounts usually serve ≥2yr M15. If a broker caps M15 history, fetch what's
  available and note the reduced window.
- **Broker symbol naming** (gold especially) → `--symbol` override.
- MT5 Python API requires the terminal **running + logged in on this machine** for every fetch.
- No production-spine/config edits; research layer stays isolated from the live spine.
