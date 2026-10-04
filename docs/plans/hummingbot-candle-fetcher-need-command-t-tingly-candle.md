> Created: 2026-05-16 · Updated: 2026-05-16 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Fetch AUDUSD M15 Candles via Alpha Vantage (New Fetcher)

## Context
BTCUSDT is a native crypto pair fully supported by Binance (the default exchange in the hummingbot_data config). No code changes needed — just run the existing `fetch_candles_hummingbot.py` script with the right flags.

---

## Files to Create / Modify

| File | Action |
|---|---|
| `src/inout/alphavantage_candle_fetcher.py` | **Create** — core fetcher (mirrors `hummingbot_candle_fetcher.py` pattern) |
| `scripts/data/fetch_candles_alphavantage.py` | **Create** — thin CLI wrapper (mirrors `fetch_candles_hummingbot.py` pattern) |
| `configs/production/v1_multi_2026_03.json` | **Modify** — add `alphavantage_data` section (then re-hash) |

---

## 1. `src/inout/alphavantage_candle_fetcher.py` (new)

Follow `docs/EXAMPLE_SERVICE.py` + `hummingbot_candle_fetcher.py` structure exactly.

### Config dataclass — `AlphaVantageFetcherConfig`
```python
@dataclass
class AlphaVantageFetcherConfig:
    api_key: str
    from_symbol: str      # "AUD"
    to_symbol: str        # "USD"
    interval: str         # "15min"  (AV uses "15min" not "15m")
    start_date: str       # "YYYY-MM-DD"
    end_date: str         # "YYYY-MM-DD"
    output_dir: Path
    request_delay_s: float = 1.2  # stay under 25 req/day free tier

    @classmethod
    def from_section(cls, section: dict) -> "AlphaVantageFetcherConfig": ...
```

### Main class — `AlphaVantageCandleFetcher`

```
SUPPORTED_INTERVALS = {"1min", "5min", "15min", "30min", "60min"}
AV_BASE_URL = "https://www.alphavantage.co/query"
```

Public methods:
- `fetch() -> Path` — iterates months, calls `_fetch_month()`, concatenates, calls `_write_csv()`
- `from_prod_config(cls, prod_cfg) -> "AlphaVantageCandleFetcher"` — factory

Private helpers:
- `_fetch_month(year, month) -> list[dict]` — one `urllib.request.urlopen` call to `FX_INTRADAY` with `month=YYYY-MM`; parses JSON `"Time Series FX (15min)"` dict; returns list of `{ts, open, high, low, close}`
- `_months_in_range() -> list[tuple[int,int]]` — generates `(year, month)` pairs from `start_date` to `end_date` exclusive
- `_write_csv(rows: list[dict]) -> Path` — sorts by timestamp, writes CSV with columns: `datetime, timestamp, open, high, low, close, volume` (volume = `0.0` — AV FX endpoint has no volume); `datetime` formatted as `YYYY.MM.DD HH:MM` for CandleLoader; filename = `AUDUSD_15min.csv`

Error handling:
- API error in JSON response → `RuntimeError` with message
- Empty response for a month → `logger.warning`, skip (some months may have gaps)
- No data at all → `RuntimeError`
- Uses same optional-import guard style as `hummingbot_candle_fetcher.py`; `urllib.request` is stdlib so no guard needed

---

## 2. `scripts/data/fetch_candles_alphavantage.py` (new)

Thin argparse wrapper, same structure as `fetch_candles_hummingbot.py`.

Arguments:
```
--pair      AUDUSD           (required; split at pos 3 → from=AUD, to=USD)
--interval  15min            (default 15min)
--start     YYYY-MM-DD       (required)
--end       YYYY-MM-DD       (required)
--api-key   YOUR_KEY         (required; also falls back to AV_API_KEY env var)
--out       DIR              (default: data/alphavantage)
--config    PATH             (default: configs/production/v1_multi_2026_03.json)
```

Logic:
1. Load prod config → build `alphavantage_data` section
2. Apply CLI overrides (same `if args.x: section[...] = args.x` pattern as hummingbot script)
3. Parse `--pair AUDUSD` → `from_symbol=AUD`, `to_symbol=USD` (always len-6 forex pair)
4. Instantiate `AlphaVantageFetcherConfig.from_section()` → `AlphaVantageCandleFetcher`
5. Call `fetcher.fetch()` → print `wrote -> {path}`

---

## 3. Production config addition

Add as a new top-level sibling of `hummingbot_data` (at the end of the JSON, before closing `}`):

```json
"alphavantage_data": {
  "api_key": "demo",
  "from_symbol": "AUD",
  "to_symbol": "USD",
  "interval": "15min",
  "start_date": "2024-01-01",
  "end_date": "2025-01-01",
  "output_dir": "data/alphavantage",
  "request_delay_s": 1.2
}
```

After editing config: `python scripts/maintenance/_compute_hash.py` (re-hash required per CLAUDE.md §3.1).

---

## Run Command (after implementation)

Get a free API key at https://www.alphavantage.co/support/#api-key (instant, no credit card).

```powershell
python scripts/data/fetch_candles_alphavantage.py `
    --pair AUDUSD `
    --interval 15min `
    --start 2024-01-01 `
    --end 2025-01-01 `
    --api-key YOUR_FREE_KEY `
    --out data/alphavantage
```

Expected: fetches 12 monthly batches (~1.2 s apart), writes `data/alphavantage/AUDUSD_15min.csv`.

---

## Verification

1. Run command above with a valid API key → check console for `wrote -> ...`
2. Check `data/alphavantage/AUDUSD_15min.csv`:
   - Column headers: `datetime,timestamp,open,high,low,close,volume`
   - `datetime` format: `2024.01.02 05:00` (CandleLoader-compatible)
   - Row count: ~24,000 (M15 candles for ~252 forex trading days)
   - Volume column: `0.0` throughout (expected — AV FX has no volume)
3. Use `demo` API key with a narrow date range first (one month) to confirm response parsing before running the full year fetch
