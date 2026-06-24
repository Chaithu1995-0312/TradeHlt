> Created: 2026-05-07 · Updated: 2026-05-07 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Hummingbot Historical Data Ingestion for Tradelatest Backtest

## Context

The current `BacktestRunner` (`src/runtime/backtest_v2.py`) is limited to CSV files that must be manually sourced and pre-formatted. This creates a friction point: running backtests on new instruments, date ranges, or exchanges requires manual data procurement. Hummingbot provides production-grade REST + WebSocket connectors for 40+ exchanges (Binance, Bybit, OKX, KuCoin, Gate.io, etc.) and a `CandlesBase` abstraction for fetching historical OHLCV data. The goal is to add a **data-extraction script** that uses hummingbot's candle connectors to pull M15 (and other TF) OHLCV history and write CSV files compatible with Tradelatest's existing `CandleLoader`. Zero changes to `BacktestRunner` internals.

---

## Scope

**In scope:**
- New script `scripts/data/fetch_candles_hummingbot.py` — thin CLI wrapper
- New module `src/inout/hummingbot_candle_fetcher.py` — business logic, follows `EXAMPLE_SERVICE.py` pattern
- New config section `"hummingbot_data"` in `configs/production/v1_multi_2026_03.json`
- Dependency entry in `pyproject.toml` (hummingbot as optional dep)

**Out of scope:**
- Changes to `BacktestRunner`, `CandleLoader`, or any scoring engine
- Real-time streaming or live trading integration
- Order book / slippage model changes (deferred)

---

## How Hummingbot Candles Work

Hummingbot's `CandlesBase` (`hummingbot/data_feed/candles_feed/candles_base.py`):
- Configured via `CandlesConfig(connector, trading_pair, interval, max_records)` and `HistoricalCandlesConfig` (adds `start_time`, `end_time`)
- Fetches from REST endpoint with pagination; fills gaps automatically
- Returns a pandas DataFrame with columns: `timestamp, open, high, low, close, volume, quote_asset_volume, n_trades, taker_buy_base_volume, taker_buy_quote_volume`
- Exchange implementations live at `hummingbot/data_feed/candles_feed/{exchange}_spot_candles.py`

Supported intervals include: `1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `1d`.

The Tradelatest `CandleLoader` expects CSV columns: `datetime, open, high, low, close, volume` (standard OHLCV). A simple column rename + timestamp format conversion bridges the two.

---

## Implementation Plan

### Step 1 — Add `"hummingbot_data"` config section

File: `configs/production/v1_multi_2026_03.json`

Add a new top-level key:
```json
"hummingbot_data": {
  "exchange": "binance",
  "trading_pair": "EURUSD",
  "interval": "15m",
  "start_date": "2024-01-01",
  "end_date": "2025-12-31",
  "output_dir": "data/hummingbot",
  "instruments": ["EURUSD", "GBPUSD", "USDJPY"],
  "max_records_per_request": 500
}
```

Re-hash after: `python scripts/maintenance/_compute_hash.py`

### Step 2 — Create `src/inout/hummingbot_candle_fetcher.py`

Follow `docs/EXAMPLE_SERVICE.py` pattern exactly:

```python
# src/inout/hummingbot_candle_fetcher.py

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger("hummingbot_candle_fetcher")

# --- Optional import guard (hummingbot is optional dep) ---
try:
    from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
    from hummingbot.data_feed.candles_feed.data_types import HistoricalCandlesConfig
    _HB_AVAILABLE = True
except ImportError:
    _HB_AVAILABLE = False
    logger.warning("hummingbot not installed — HummingbotCandleFetcher disabled")

# --- Config dataclass ---
@dataclass
class HummingbotFetcherConfig:
    exchange: str
    trading_pair: str
    interval: str
    start_date: str
    end_date: str
    output_dir: Path
    max_records_per_request: int = 500

    @classmethod
    def from_prod_config(cls, cfg: dict) -> "HummingbotFetcherConfig":
        s = _require(cfg, "hummingbot_data")
        return cls(
            exchange=_require(s, "exchange"),
            trading_pair=_require(s, "trading_pair"),
            interval=_require(s, "interval"),
            start_date=_require(s, "start_date"),
            end_date=_require(s, "end_date"),
            output_dir=Path(_require(s, "output_dir")),
            max_records_per_request=s.get("max_records_per_request", 500),
        )

def _require(cfg: dict, key: str):
    if key not in cfg:
        raise KeyError(f"HummingbotCandleFetcher: missing required config key '{key}'")
    return cfg[key]

# --- Main class ---
class HummingbotCandleFetcher:
    """Fetches historical OHLCV candles from any hummingbot-supported exchange
    and writes Tradelatest-compatible CSV files (datetime,open,high,low,close,volume).
    """

    def __init__(self, cfg: HummingbotFetcherConfig):
        if not _HB_AVAILABLE:
            raise RuntimeError("hummingbot package is required: pip install hummingbot")
        self._cfg = cfg
        self._cfg.output_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_prod_config(cls, prod_cfg: dict) -> "HummingbotCandleFetcher":
        return cls(HummingbotFetcherConfig.from_prod_config(prod_cfg))

    async def fetch_async(self, instrument: Optional[str] = None) -> Path:
        """Fetch candles and write CSV. Returns output path."""
        pair = instrument or self._cfg.trading_pair
        cfg = HistoricalCandlesConfig(
            connector_name=self._cfg.exchange,
            trading_pair=pair,
            interval=self._cfg.interval,
            start_time=_parse_ts(self._cfg.start_date),
            end_time=_parse_ts(self._cfg.end_date),
        )
        candles = CandlesFactory.get_candle(cfg)
        await candles.start_network()
        await candles.wait_for_ready()
        df = candles.candles_df
        await candles.stop_network()

        # Rename to Tradelatest-compatible columns
        df = df[["timestamp", "open", "high", "low", "close", "volume"]].copy()
        df["datetime"] = df["timestamp"].apply(
            lambda ts: __import__("datetime").datetime.utcfromtimestamp(ts / 1e3).strftime("%Y.%m.%d %H:%M")
        )
        df = df[["datetime", "open", "high", "low", "close", "volume"]]

        out_path = self._cfg.output_dir / f"{pair.replace('/', '')}_{self._cfg.interval}.csv"
        df.to_csv(out_path, index=False)
        logger.info("Wrote %d candles → %s", len(df), out_path)
        return out_path

    def fetch(self, instrument: Optional[str] = None) -> Path:
        """Synchronous wrapper around fetch_async."""
        import asyncio
        return asyncio.run(self.fetch_async(instrument))


def _parse_ts(date_str: str) -> int:
    """Convert 'YYYY-MM-DD' to millisecond UTC timestamp."""
    import datetime
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    return int(dt.timestamp() * 1e3)
```

### Step 3 — Create `scripts/data/fetch_candles_hummingbot.py`

Thin CLI wrapper, no business logic:

```python
#!/usr/bin/env python
"""CLI: Fetch historical OHLCV candles via hummingbot and write Tradelatest CSVs.

Usage:
    python scripts/data/fetch_candles_hummingbot.py \\
        --exchange binance \\
        --pair BTCUSDT \\
        --interval 15m \\
        --start 2024-01-01 \\
        --end 2025-01-01 \\
        --out data/hummingbot
"""
import argparse
import json
from pathlib import Path
from src.inout.hummingbot_candle_fetcher import HummingbotCandleFetcher, HummingbotFetcherConfig

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exchange", default=None)
    parser.add_argument("--pair", default=None)
    parser.add_argument("--interval", default="15m")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--out", default="data/hummingbot")
    parser.add_argument("--config", default="configs/production/v1_multi_2026_03.json")
    args = parser.parse_args()

    with open(args.config) as f:
        prod_cfg = json.load(f)

    # CLI args override config values
    hb_cfg = prod_cfg.get("hummingbot_data", {})
    if args.exchange: hb_cfg["exchange"] = args.exchange
    if args.pair:     hb_cfg["trading_pair"] = args.pair
    hb_cfg["interval"] = args.interval
    hb_cfg["start_date"] = args.start
    hb_cfg["end_date"] = args.end
    hb_cfg["output_dir"] = args.out

    fetcher = HummingbotCandleFetcher(HummingbotFetcherConfig(**{
        k: hb_cfg[k] for k in HummingbotFetcherConfig.__dataclass_fields__
    }))

    instruments = prod_cfg.get("hummingbot_data", {}).get("instruments", [hb_cfg["trading_pair"]])
    for instr in instruments:
        path = fetcher.fetch(instrument=instr)
        print(f"  {instr} → {path}")

if __name__ == "__main__":
    main()
```

### Step 4 — Add hummingbot as optional dependency

File: `pyproject.toml`

```toml
[project.optional-dependencies]
hummingbot = ["hummingbot>=2.0.0"]
```

Install with: `pip install -e ".[hummingbot]"`

### Step 5 — Re-hash config

```bash
python scripts/maintenance/_compute_hash.py
```

---

## Critical Files

| File | Action |
|------|--------|
| `src/inout/hummingbot_candle_fetcher.py` | **CREATE** — new fetcher module |
| `scripts/data/fetch_candles_hummingbot.py` | **CREATE** — CLI entry point |
| `configs/production/v1_multi_2026_03.json` | **EDIT** — add `"hummingbot_data"` section |
| `pyproject.toml` | **EDIT** — add optional dep |
| `scripts/maintenance/_compute_hash.py` | **RUN** — re-hash config after edit |

---

## Existing Patterns Reused

- Optional-import guard pattern → `docs/EXAMPLE_SERVICE.py` lines 12–18
- `_require()` strict accessor → `docs/EXAMPLE_SERVICE.py` lines 22–26
- `from_prod_config(cls, cfg)` factory → `docs/EXAMPLE_SERVICE.py` lines 45–52
- Named flow logger → `logging.getLogger("hummingbot_candle_fetcher")`
- CLI thin wrapper → mirrors `scripts/data/` existing scripts pattern

---

## Verification

1. **Unit test** — `tests/inout/test_hummingbot_candle_fetcher.py`:
   - Mock `CandlesFactory.get_candle()` to return a synthetic DataFrame
   - Assert output CSV has columns `datetime, open, high, low, close, volume`
   - Assert optional-import path raises `RuntimeError` when `_HB_AVAILABLE = False`

2. **Integration test** (requires hummingbot installed + network):
   ```bash
   python scripts/data/fetch_candles_hummingbot.py \
     --exchange binance --pair BTCUSDT --interval 15m \
     --start 2025-01-01 --end 2025-01-07 --out /tmp/hb_test
   ```
   Verify `/tmp/hb_test/BTCUSDT_15m.csv` exists, has >500 rows, correct columns.

3. **End-to-end backtest** — feed the generated CSV into `BacktestRunner`:
   ```bash
   python scripts/backtest/run_backtest.py \
     --csv /tmp/hb_test/BTCUSDT_15m.csv \
     --instrument BTCUSDT
   ```
   Confirm run completes, `results/` folder has `_summary.json` and `_trades.csv`.

4. **Config hash** — confirm `python scripts/maintenance/_compute_hash.py` exits 0 after JSON edit.
