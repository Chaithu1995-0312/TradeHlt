# Plan — Acquire Binance perp funding + basis data (unblock carry/basis axis)

## Context

Across Programs 1–5 the next-bar-directional and cross-sectional-dispersion axes on **spot** crypto
majors were exhausted (F-019…F-032, all null). The one structural payoff the multi-LLM advisors
rated highest — **carry / basis** (the funding a perp pays + the perp−spot premium) — was never
tested because it is **DATA-BLOCKED**: `data/` holds Binance **spot** OHLCV only (per the F-032 memo
and `docs/implementation_plan/the-largest-risk-you-wondrous-muffin.md:13-17`). The M4 kernel
(`qualification.py` 7-gate sequence) and the cross-sectional panel machinery
(`cross_sectional.py`) are **payoff-agnostic and already able to qualify** a carry/basis interpreter
— they are starved of inputs, not capability.

**This task acquires the inputs, nothing more.** A small additive fetch script pulls Binance
USDⓈ-M perpetual **funding-rate history** (the carry signal) and **premium-index/basis history**
(the basis signal) into `data/`, time-aligned to the existing 2024-05→2026-05 spot window. Building
the carry/basis *interpreter* and running it through M4 is a **separate downstream task** — this
change grants **no research authority** (§6.5 Authority Ladder: data acquisition ≠ a measured ΔG001).

**Data-availability finding (drives the scope):** funding-rate and premium-index have *full* public
history on Binance fapi. **Open interest is the blocked one** — `futures/data/openInterestHist`
retains only ~30 days, so it cannot match the 2-yr window and is deferred (user-confirmed: funding +
basis only, Binance only).

## Scope (user-confirmed)
- **Signals:** funding rate (8h cadence) + basis via premium-index klines (M15 cadence). **No OI.**
- **Exchange:** Binance USDⓈ-M perpetuals (`fapi.binance.com`) — aligns 1:1 with existing Binance
  spot timestamps the panel inner-joins on.
- **6 instruments:** BNBUSDT, BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, DOGEUSDT (the spot panel set).

## Design (mirror the doctrine-compliant fetcher pattern)

Follow `src/inout/alphavantage_candle_fetcher.py` (logic in `src/`, thin `scripts/` wrapper,
`from_prod_config` factory, stdlib `urllib` HTTP — **no new deps**), **not** the self-contained
`fetch_crypto_ccxt.py`. Pure normalize functions are split out so tests are deterministic without
network.

### 1. New module — `src/inout/perp_funding_fetcher.py`
- `@dataclass PerpFetcherConfig` + `from_prod_config(cls, cfg: dict) -> "PerpFetcherConfig"`.
  Fields: `base_url`, `instruments: tuple[str,...]`, `funding_path` (`/fapi/v1/fundingRate`),
  `basis_path` (`/fapi/v1/premiumIndexKlines`), `interval` (`"15m"`), `request_timeout_s`,
  `request_delay_s`, `max_limit` (1000 funding / 1500 klines), `out_dir` (`data/perp`).
  Strict `_require()` reads — **no silent defaults** (§6.5 hard rule).
- `class PerpFundingFetcher`:
  - public `fetch(instrument, start, end) -> dict[str, Path]` and `fetch_all(start, end)`.
  - private `_get_json(url)` — the **only** network call (stdlib `urllib.request.urlopen`,
    `timeout=request_timeout_s`); isolated so tests monkeypatch it.
  - `_paginate_funding(symbol, start_ms, end_ms)` — advance `startTime` past last `fundingTime`,
    `time.sleep(request_delay_s)` between calls, dedup + sort.
  - `_paginate_klines(symbol, start_ms, end_ms)` — same pagination for premium-index klines.
  - **Pure** `_normalize_funding(raw) -> list[(ts_str, rate_float)]` and
    `_normalize_basis(raw) -> list[(ts_str, premium_float)]` — ms→UTC `YYYY-MM-DD HH:MM:SS`,
    dedup, ascending sort. These are the unit-tested seams.
  - `_write_csv(path, fieldnames, rows)` via stdlib `csv.DictWriter` (matches alphavantage writer).
- Module-level `logger` + `safe_print` from `src/utils/console_safe.py` for any non-ASCII.

### 2. New script — `scripts/data/fetch_perp_funding.py` (thin argparse wrapper)
Mirror `scripts/data/fetch_candles_alphavantage.py`: `--instrument`/`--all`, `--start`, `--end`,
`--config` (default active prod), `--signals funding,basis`, `--out`. Load the config section,
apply CLI overrides, construct `PerpFetcherConfig`, call `PerpFundingFetcher.fetch_all`.
`raise SystemExit(main())`; exit code by success count.

### 3. New config section — `perp_funding_data`
Add a top-level `perp_funding_data` section (base_url, instruments, paths, interval, timeouts,
delay, out_dir) to the **active** config `configs/production/v2_multi_2026_04.json` (ACTIVE_VERSION
on `patch`, per §4.0). **New top-level section = hash-neutral — no rehash.** Mirror the same block
into the documented template `configs/production/v1_multi_2026_03.json` for convention parity.

### 4. Output files (land in gitignored `data/perp/`)
- `data/perp/{SYMBOL}_FUNDING.csv` — header `timestamp,funding_rate` (8h settlement times, UTC).
- `data/perp/{SYMBOL}_BASIS_M15.csv` — header `timestamp,premium_index` (M15, aligns to spot panel).

Store **native cadence raw** — the future interpreter forward-fills funding onto M15 / joins basis;
the fetcher does not pre-align (keeps acquisition lossless and the consumer's job explicit).

### 5. Tests — `tests/test_perp_funding_fetcher.py`
Deterministic, no network (monkeypatch `_get_json`), per repo testing conventions:
- `test_normalize_funding_schema` — fixture raw funding list → `[(ts_str, rate_float)]`, ms→UTC,
  sorted, deduped.
- `test_normalize_basis_schema` — fixture premium-index klines → M15 `[(ts_str, premium_float)]`.
- `test_pagination_advances_no_dup` — multi-page fixture; assert no infinite loop / no duplicate
  `fundingTime`, ascending order.
- `test_fetch_byte_identical` — monkeypatched fetch into two `tmp_path` dirs → CSV bytes identical
  (determinism gate).
- `test_from_prod_config` — dict → `PerpFetcherConfig` field assertions; missing key raises.

## Critical files
- **New:** `src/inout/perp_funding_fetcher.py`, `scripts/data/fetch_perp_funding.py`,
  `tests/test_perp_funding_fetcher.py`.
- **Edit (additive, hash-neutral):** `configs/production/v2_multi_2026_04.json` (+ mirror
  `configs/production/v1_multi_2026_03.json`).
- **Reuse / mirror (no edits):** `src/inout/alphavantage_candle_fetcher.py` (fetcher pattern),
  `scripts/data/fetch_candles_alphavantage.py` (script wrapper), `src/utils/console_safe.py`
  (`safe_print`), `src/research/cross_sectional.py:55` (`load_panel` — the future consumer; confirms
  the basis CSV timestamp format must inner-join with spot).

## Verification (end-to-end)
1. **Unit / determinism:** `pytest tests/test_perp_funding_fetcher.py -q` — all green, byte-identical
   re-run.
2. **Live fetch (network):**
   `python scripts/data/fetch_perp_funding.py --all --start 2024-05-22 --end 2026-05-22`
   → writes 6× `*_FUNDING.csv` + 6× `*_BASIS_M15.csv` to `data/perp/`.
3. **Sanity counts:** funding ≈ 3/day × ~730 days ≈ ~2,190 rows/instrument; basis M15 ≈ ~70k
   rows/instrument (≈ spot file length).
4. **Alignment check:** intersect `BNBUSDT_BASIS_M15.csv` timestamps with `data/BNBUSDT_M15.csv`
   (spot) — inner-join must be non-empty and ≈ full overlap (confirms the basis series is
   `load_panel`-ready for the future carry/basis interpreter).
5. **Config load:** confirm `get_prod_section("perp_funding_data")` resolves on the active version
   (no `KeyError`), and config hash unchanged (new top-level section is hash-neutral).

## Out of scope (explicit — separate downstream tasks)
- The carry/basis **interpreter** + its `Panel` extension (`funding`/`basis` fields) and M4
  qualification run. This plan only lands the data.
- **Open interest** (data-blocked; ~30-day retention) and Bybit / cross-venue sourcing.
- On implementation: flip the F-032 "perps DATA-BLOCKED" note to *funding/basis un-blocked, OI still
  blocked* (finding/memory update, same turn) — but **no edge claim** until the interpreter runs.
