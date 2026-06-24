> Created: 2026-05-07 · Updated: 2026-05-07 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Backtest on Existing M15 Data + Agent Strategy Discovery + Live Broker Hook

## Context

User has one M15 Excel file in `data/`. Historical download is out of scope — data is
added manually. The three pieces to build are:

1. **Backtest on real M15 data** — read the Excel file, run `BacktestRunner`, get real metrics.
2. **Agent strategy discovery** — agent intent that triggers the backtest + engine scoring +
   `llm_insight()` narrative so the LLM explains what the system would have done.
3. **Live broker hook** — replace `INOUTRunner._fetch_candles()` stub and `INOUTExecutor`
   Phase 1 stubs with real API calls to Binance or OANDA (controlled by config `broker.provider`).

---

## Constraints From Exploration

- `CandleLoader` (backtest_v2.py:583) reads **CSV only** — Excel must be converted first.
- `pandas` is almost certainly available (quantitative trading system with sklearn/scipy).
- `INOUTRunner._fetch_candles()` (runner.py:197) returns a list of raw dicts — this is the
  live candle entry point to replace.
- `INOUTExecutor` (executor.py:71) Phase 1 stubs are at lines 104–250; `self._dry_run = True`
  always set — controlled by new `broker.dry_run` config key.
- All config keys in `configs/production/v1_multi_2026_03.json`.
- No new packages: stdlib `urllib` + `hmac` for HTTP; `pandas` for Excel read (already present).
- `broker.dry_run` **defaults to `true`** — live execution only activates via `live_hook.enable`.

---

## Critical Files

| File | Action |
|------|--------|
| `configs/production/v1_multi_2026_03.json` | Add `"broker"` section |
| `scripts/maintenance/_compute_hash.py` | Run after config change |
| `src/inout/live_feed.py` | **New** — `BinanceLiveFeed`, `OANDALiveFeed` (candle fetch for live) |
| `src/inout/runner.py` | Replace `_fetch_candles()` stub (line ~197) |
| `src/inout/executor.py` | Replace Phase 1 stubs with real broker calls (lines 104–250) |
| `src/agent/tools/market_mode.py` | **New** — `handle_strategy_discover` agent tool |
| `src/agent/tool_registry.py` | Register `strategy.discover` |
| `src/agent/plan_compiler.py` | Add `strategy_discover` to PLAN_REGISTRY |
| `src/agent/prompts/intent_patterns.json` | Add regex patterns |
| `tests/test_agent_strategy_discover.py` | **New** — unit tests |
| `tests/test_inout_live_feed.py` | **New** — unit tests |

---

## Step 1 — Add `"broker"` config section

```json
"broker": {
  "provider": "binance",
  "dry_run": true,
  "live_candle_count": 50,
  "binance": {
    "api_key_env": "BINANCE_API_KEY",
    "api_secret_env": "BINANCE_API_SECRET",
    "futures_base_url": "https://fapi.binance.com",
    "spot_klines_url": "https://api.binance.com/api/v3/klines",
    "recv_window_ms": 5000,
    "interval_map": {"M1":"1m","M5":"5m","M15":"15m","H1":"1h","H4":"4h","D1":"1d"}
  },
  "oanda": {
    "rest_url": "https://api-fxtrade.oanda.com/v3",
    "account_id_env": "OANDA_ACCOUNT_ID",
    "api_key_env": "OANDA_API_KEY",
    "granularity_map": {"M1":"M1","M5":"M5","M15":"M15","H1":"H1","H4":"H4","D1":"D"}
  }
}
```

Re-hash: `python scripts/maintenance/_compute_hash.py`

---

## Step 2 — Excel-to-CSV converter (inline utility, not a new file)

Add a private helper `_excel_to_csv(xlsx_path: str, out_dir: str) -> str` inside
`src/agent/tools/market_mode.py`:

```python
def _excel_to_csv(xlsx_path: str, out_dir: str) -> str:
    """Read first sheet, normalise columns, write CSV for CandleLoader."""
    import pandas as pd
    df = pd.read_excel(xlsx_path, sheet_name=0)
    # normalise column names to lowercase
    df.columns = [c.strip().lower() for c in df.columns]
    # ensure CandleLoader alias match: timestamp,open,high,low,close,volume
    out_path = os.path.join(out_dir, os.path.basename(xlsx_path).replace(".xlsx", ".csv"))
    df.to_csv(out_path, index=False)
    return out_path
```

Called only when input path ends with `.xlsx`. Existing CSV files pass through unchanged.

---

## Step 3 — Agent tool: `src/agent/tools/market_mode.py` (new)

Single handler — follow `docs/EXAMPLE_SERVICE.py`:

```
handle_strategy_discover(data_path, instrument) → dict

1. _load_bt_cfg()  — fail-fast require backtest section keys
2. If data_path ends .xlsx → _excel_to_csv(data_path, "data/") → csv_path
   Else csv_path = data_path
3. total = CandleLoader(csv_path, instrument).count()
4. bt_config = BacktestConfig.from_prod_config(cfg)
5. runner = BacktestRunner(bt_config, csv_path, skip_features=False)
6. metrics = runner.run(CandleLoader(csv_path, instrument).stream(),
                        total, "results/market_scan/")
7. Sample up to 5 approved trade feature vectors → EngineRunner.run() each
   Collect: engine scores, regime labels
8. summary = {
     win_rate, expectancy_rr, max_drawdown_pct, approved_trades, rejected_trades,
     dominant_regime, avg_crt_score, avg_gaussian_score, avg_rr_score,
     feature_drift (from metrics.distribution)
   }
9. narrative = llm_insight(context=summary, report_type="backtest_summary")
10. return {"status": "ok", "summary": summary, "narrative": narrative}
```

`data_path` defaults to glob of first `.xlsx` or `.csv` found in `data/` if not supplied.

---

## Step 4 — Register tool (tool_registry.py)

```python
ToolSpec(
    name="strategy.discover",
    description="Run backtest on M15 data file, score with engines, return LLM strategy narrative",
    args_schema={
        "data_path":  {"type": "str", "required": False,
                       "desc": "Path to .xlsx or .csv in data/. Auto-detected if omitted."},
        "instrument": {"type": "str", "required": False, "desc": "e.g. BTCUSDT"},
    },
    handler=handle_strategy_discover,
    write=False,
),
```

---

## Step 5 — PLAN_REGISTRY addition (plan_compiler.py)

```python
"strategy_discover": Plan(
    intent_key="strategy_discover",
    mode="market",
    steps=[ToolStep("strategy.discover")],
),
```

---

## Step 6 — Intent pattern (intent_patterns.json)

```json
"strategy_discover": {
  "mode": "market",
  "patterns": [
    "find.*strateg", "discover.*strateg",
    "what.*strateg.*work", "analyse.*m15",
    "analyze.*data.*strateg", "check.*backtest.*strateg",
    "run.*backtest.*find", "which.*setup.*profit"
  ]
}
```

---

## Step 7 — Live candle feed: `src/inout/live_feed.py` (new)

Two classes, both output the dict list `INOUTScanner.scan()` expects.

### `BinanceLiveFeed`

```python
def fetch(self, symbol: str, tf: str, count: int) -> list[dict]:
    """GET api.binance.com/api/v3/klines — no auth required for candles."""
    interval = self._cfg["interval_map"][tf]   # "M15" → "15m"
    url = (f"{self._cfg['spot_klines_url']}?"
           f"symbol={symbol}&interval={interval}&limit={count}")
    resp = _get_json(url, timeout=self._timeout)
    return [
        {"open": float(k[1]), "high": float(k[2]),
         "low": float(k[3]),  "close": float(k[4]),
         "volume": float(k[5])}
        for k in resp
    ]
```

### `OANDALiveFeed`

```python
def fetch(self, instrument: str, granularity: str, count: int) -> list[dict]:
    """GET /v3/instruments/{instrument}/candles — requires Bearer token."""
    g = self._cfg["granularity_map"][granularity]
    url = (f"{self._cfg['rest_url']}/instruments/{instrument}/candles"
           f"?granularity={g}&count={count}&price=M")
    resp = _get_json(url, timeout=self._timeout,
                     bearer=_load_env(self._cfg["api_key_env"]))
    return [
        {"open":   float(c["mid"]["o"]), "high": float(c["mid"]["h"]),
         "low":    float(c["mid"]["l"]), "close": float(c["mid"]["c"]),
         "volume": float(c.get("volume", 0))}
        for c in resp["candles"] if c.get("complete", True)
    ]
```

Public factory: `get_live_feed(cfg) -> BinanceLiveFeed | OANDALiveFeed`
Reads `broker.provider` → returns right class.

---

## Step 8 — Wire `INOUTRunner._fetch_candles()` (runner.py:197)

Replace stub:

```python
def _fetch_candles(self, symbol: str, tf: str, count: int) -> list[dict]:
    feed = get_live_feed(self._broker_cfg)   # from live_feed.py
    return feed.fetch(symbol, tf, count)
```

`self._broker_cfg` loaded in `__init__` via `get_prod_section("broker")`.

---

## Step 9 — Wire `INOUTExecutor` real broker calls (executor.py)

Read `broker.dry_run` in `__init__`. When `False`, replace stubs:

### Binance branch (open_position)

```python
side = "BUY" if direction == "LONG" else "SELL"
params = {
    "symbol": symbol, "side": side, "type": "MARKET",
    "quantity": f"{qty:.6f}", "recvWindow": recv_window_ms,
    "timestamp": int(time.time() * 1000),
}
sig = _hmac_sha256(self._secret, urlencode(params))
params["signature"] = sig
resp = _post_form(f"{futures_base_url}/fapi/v1/order", params, self._api_key)
fill_price = float(resp["avgPrice"])
self._place_sl_tp_orders(symbol, direction, qty, stop_loss, tp1_price, tp2_price)
return FillResult(success=True, order_id=str(resp["orderId"]),
                  fill_price=fill_price, fill_qty=qty, status="filled")
```

`_hmac_sha256` uses stdlib `hmac` + `hashlib`. `_post_form` uses stdlib `urllib`.

### OANDA branch (open_position)

```python
body = json.dumps({"order": {
    "type": "MARKET",
    "instrument": symbol,
    "units": str(qty) if direction == "LONG" else str(-qty),
    "stopLossOnFill": {"price": f"{stop_loss:.5f}"},
    "takeProfitOnFill": {"price": f"{tp1_price:.5f}"},
}})
resp = _post_json(
    f"{oanda_url}/v3/accounts/{account_id}/orders",
    body, bearer=self._api_key
)
fill_price = float(resp["orderFillTransaction"]["price"])
return FillResult(success=True,
                  order_id=resp["orderFillTransaction"]["id"],
                  fill_price=fill_price, fill_qty=qty, status="filled")
```

`exit_full` → market close order; `update_stop_loss` → cancel + replace STOP_LOSS order.
All stubs stay active when `dry_run=true` (default).

---

## Complete Data Flow After Implementation

```
BACKTEST / STRATEGY DISCOVERY
──────────────────────────────
Agent: "find strategies in my M15 data"
    → IntentRouter → "strategy_discover"
    → PlanCompiler → [strategy.discover]
    → handle_strategy_discover(data_path=None, instrument="BTCUSDT")
         → glob data/*.xlsx → data/BTCUSDT_M15.xlsx
         → _excel_to_csv() → data/BTCUSDT_M15.csv
         → BacktestRunner.run(CandleLoader.stream())  ← REAL MARKET NUMBERS
         → EngineRunner.run() × 5 sample bars
         → llm_insight("backtest_summary") → narrative
    → Agent prints: win_rate, expectancy, drawdown, narrative
    → logs/agent_audit.jsonl updated

LIVE TRADING PATH
─────────────────
INOUTRunner._run_cycle()
    → _fetch_candles("BTCUSDT", "M15", 50)
         → BinanceLiveFeed.fetch()  [or OANDALiveFeed]
         → GET api.binance.com/api/v3/klines  ← REAL LIVE CANDLES
    → INOUTScanner.scan(candles) → INOUTSignal
    → INOUTController.on_signal() → UltronRiskGate check
    → INOUTExecutor.open_position()
         dry_run=true  → simulated FillResult  (default, safe)
         dry_run=false → POST fapi.binance.com/fapi/v1/order
                      OR POST api-fxtrade.oanda.com/v3/accounts/.../orders
```

---

## Verification

1. `pytest tests/test_agent_strategy_discover.py -v`
   - Excel → CSV conversion produces correct column names
   - BacktestRunner mock returns metrics → narrative key present in result
   - Auto-detect of first .xlsx in `data/` works

2. `pytest tests/test_inout_live_feed.py -v`
   - Mock `urllib.urlopen` → Binance 5-kline list → 5-item dict list returned
   - OANDA mock response → same shape
   - `get_live_feed()` returns correct class per config

3. **Config hash:** `python scripts/maintenance/_compute_hash.py`

4. **Agent smoke test:**
   ```bash
   python -m src.agent.cli
   > find strategies in my M15 data
   ```
   Expect: backtest runs on Excel file, metrics + narrative printed, no crash.

5. **Regression:** `pytest tests/test_backtest*.py tests/test_inout*.py`
