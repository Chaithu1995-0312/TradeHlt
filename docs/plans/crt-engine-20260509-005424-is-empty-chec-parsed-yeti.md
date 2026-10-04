> Created: 2026-05-09 · Updated: 2026-05-09 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# CRT Engine Log Empty — Root Cause & Fix Plan

## Context

Running `python src/runtime/backtest_v2.py --instrument ETHUSDT --csv data/hummingbot/ETHUSDT_1h.csv` produced `logs/crt_engine_20260509_005424.log` with only 1 line (blank). The user wants to know why.

There are **two independent causes** — one architectural, one config/data mismatch.

---

## Cause 1 — Architectural: Wrong log for backtest path (the direct answer)

**File:** `src/engines/crt_engine.py` lines 14–19

```python
_handler = logging.FileHandler(get_log_path("crt_engine"))   # ← file created at import
_log.addHandler(_handler)
...
def compute(trade_id, features, context):
    ...
    _log.info(json.dumps(...))   # ← only write point
```

The `crt_engine_*.log` is written **only** when `compute()` is called. `compute()` is only invoked by `engine_runner.py` (live/scoring mode). `backtest_v2.py` never calls `engine_runner.py` — it calls `CRTEngine` from `crt_engine_v2.py` directly (the state machine). The file is created at module-import time (when `crt_engine.py` is transitively imported), then never written to.

**Conclusion:** An empty `crt_engine_*.log` is expected in every backtest run. It is not a bug in the log; it is the wrong log to check for backtest diagnostics. The correct logs are:
- `logs/trade_system_20260509_005424.log` — FeaturePipeline, drift, feature health
- `logs/backtest_debug.log` — candle-by-candle state machine trace

---

## Cause 2 — Zero trades: Timeframe × Config mismatch

Active config: `v2_multi_2026_04` — validated **only on EURUSD** M15 data (`validation_summary.instruments: ["EURUSD"]`). Running it against ETHUSDT 1h exposes three compounding problems:

### 2a. HTF window too narrow for 1h data

```
backtest section: htf_candles_per_range = 4
```

On M15 (designed use): 4 candles = 1h HTF — correct.  
On 1h (actual use): 4 candles = 4h HTF — still functional, but every HTF boundary fires every **4 bars**, and the state machine needs RANGE → SWEEP → DISPLACEMENT → EXPANSION before the next boundary (EXPANSION + RETEST are protected from HTF resets; DISPLACEMENT is not).

**Evidence from `should_reset` (`crt_engine_v2.py:1324–1327`):**
```python
if current_htf_id != state.active_range.htf_candle_id:
    if state.current_state in [CRTState.EXPANSION, CRTState.RETEST]:
        return False, ""  # protected
    return True, f"HTF changed: ..."   # DISPLACEMENT → RESET here
```

With a 4-candle window, DISPLACEMENT is frequently blown away before EXPANSION can form.

### 2b. Feature drift on ETHUSDT 1h

From `trade_system_20260509_005424.log`:
```
FeatureMonitor: 258/3548 rows flagged as drift (Z > 2.5 on retest_depth/body_ratio/disp_strength)
FeatureHealth retest_depth | zero_rate=92.22%
```

`retest_depth` is 0 for 92% of candles — the FeaturePipeline's retest feature rarely fires on 1h ETHUSDT data because the state machine was parameterised for M15 EUR volatility.

### 2c. ATR-based gates tuned for M15 EURUSD

```json
"atr_min_displacement": 1.2,     // body must be 1.2× ATR
"expansion_atr_min_distance": 0.3,
"confirmation_body_min": 0.6,
"soft_conf_max_candles": 3       // only 3 hours to confirm on 1h data
```

These thresholds were optimised against EURUSD M15. On 1h ETHUSDT, ATR is ~12× larger in absolute price but structurally similar in percentage terms — so they don't hard-block, but the combination with 2a and 2b means the full 5-stage pipeline never completes.

---

## Proposed Fixes

### Fix A — Quick smoke-test: widen the HTF window

Pass `--htf 16` on the command line. On 1h data, 16 candles = 16h HTF — equivalent to the M15 config's 1h HTF conceptually. No code change required.

```
python src/runtime/backtest_v2.py \
  --instrument ETHUSDT \
  --csv data/hummingbot/ETHUSDT_1h.csv \
  --htf 16
```

`BacktestConfig.from_prod_config` picks this up at `backtest_v2.py:1799`:
```python
if args.htf is not None: cfg.htf_candles_per_range = args.htf
```

### Fix B — Resample to M15 (canonical path)

The system is architected for M15. ETHUSDT 1h data should be resampled to M15 before running the standard backtest. Avoids all parameter-tuning drift.

```
python scripts/data/resample_ohlcv.py \
  --input data/hummingbot/ETHUSDT_1h.csv \
  --output data/hummingbot/ETHUSDT_M15.csv \
  --from 1h --to 15m
```
(If `resample_ohlcv.py` does not exist it needs to be created; no code change to the engine itself.)

### Fix C — Add ETHUSDT to validation instruments and re-tune (medium-term)

To properly support 1h ETHUSDT:
1. Add `"ETHUSDT"` to `configs/production/v2_multi_2026_04.json → validation_summary.instruments`
2. Add a `per_instrument.ETHUSDT` config section with adjusted `atr_min_displacement`, `soft_conf_max_candles`, `htf_candles_per_range`
3. Run `python src/governance/promotion_manager.py promote ...` against ETHUSDT data
4. Re-hash: `python scripts/maintenance/_compute_hash.py`

This is the correct long-term path per `CLAUDE.md §3.1`.

---

## Critical Files

| File | Role |
|---|---|
| `src/engines/crt_engine.py:14–19` | Log file created on import; `compute()` never called from backtest |
| `src/runtime/backtest_v2.py:1344,1432` | Uses `CRTEngine` directly, not `engine_runner` |
| `src/config_layer/crt_engine_v2.py:1324–1327` | HTF reset logic; DISPLACEMENT not protected |
| `configs/production/v2_multi_2026_04.json:303` | `htf_candles_per_range: 4` |
| `logs/trade_system_20260509_005424.log` | Actual diagnostic log (drift warning, feature health) |

---

## Verification

1. **Confirm Cause 1**: `grep -c "" logs/crt_engine_20260509_005424.log` → 1 (blank). Correct; expected.
2. **Test Fix A**: Run with `--htf 16`; check `logs/backtest_debug.log` for `TRADE_OPENED` events.
3. **Confirm Cause 2**: Run with `--htf 16` and check if trade count becomes non-zero. If still zero after HTF fix, the issue is parameter thresholds (Fix C needed).
4. **Check events file**: `results/run_*_ETHUSDT/*_events.jsonl` shows state machine transitions — look for `DISPLACEMENT_CONFIRMED` followed immediately by `RESET` (confirms 2a).
