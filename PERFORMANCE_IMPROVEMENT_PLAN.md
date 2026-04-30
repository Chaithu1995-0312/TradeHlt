# Performance Improvement Plan — Tradelatest Backtest Engine
**Date:** 2026-04-28  
**Scope:** Backtest speed — `BacktestRunner`, `auto_tuner_multi.py`, `FeaturePipeline`, supporting utilities  
**Constraint:** Zero architecture changes. Surgical, file-local edits only.  
**Evidence basis:** Wall-clock observation + code inspection of hot paths

---

## Executive Summary

Eight concrete optimisations are identified, ranked by estimated wall-clock impact. The single biggest win (P1) eliminates redundant `FeaturePipeline` runs in the tuner — it currently re-runs the full pandas feature computation for every parameter combination evaluated, when the pipeline output is identical for the same CSV. Combined, these changes are expected to reduce a typical multi-instrument tuning run from O(N×M) FeaturePipeline executions to O(M), and reduce per-candle overhead by 30–60% on the hot-path.

---

## 1. Profiling Baseline (do this first)

Before touching code, capture a wall-clock profile so each fix can be verified:

```bash
# Single-instrument profile (generates pstats output)
python -m cProfile -o results/perf_baseline.pstats \
  src/runtime/backtest_v2.py --csv data/EURUSD_M15.csv --instrument EURUSD

# Inspect top 20 hotspots
python -c "
import pstats, io
p = pstats.Stats('results/perf_baseline.pstats', stream=(s := io.StringIO()))
p.sort_stats('cumulative').print_stats(20)
print(s.getvalue())
"
```

Re-run this profile after each fix to verify the expected speedup before moving to the next item.

---

## 2. Optimisations (Ranked by Impact)

---

### P1 — Skip FeaturePipeline in Tuner Workers `[CRITICAL]`

**File:** `scripts/training/auto_tuner_multi.py` → `_run_single_instrument()`  
**File:** `src/runtime/backtest_v2.py` → `BacktestRunner.__init__()`

**Problem:**  
`BacktestRunner.__init__` always runs `FeaturePipeline` when `csv_path` is provided. In the tuner, `_run_single_instrument()` creates a new `BacktestRunner(bt_cfg, csv_path=csv_path)` for **every parameter set × instrument**. With a 1800-sample PARAM_SPACE and 4 instruments, that is up to 7200 full `FeaturePipeline` runs — each reading the CSV and computing all 35 indicators — when only 4 runs are ever needed. The tuner's fitness function reads only `approved_trades`, `win_rate`, `expectancy_rr`, `max_drawdown_pct`; it does not consume feature columns.

**Fix — two steps:**

**Step A:** Add an opt-out flag to `BacktestRunner.__init__`:

```python
# src/runtime/backtest_v2.py  — BacktestRunner.__init__ signature
def __init__(self, bt_config: BacktestConfig, csv_path: str = None,
             skip_features: bool = False):        # ← ADD THIS
    ...
    if self.csv_path and not skip_features:       # ← WRAP existing pipeline block
        try:
            ...  # existing FeaturePipeline code unchanged
```

**Step B:** Pass `skip_features=True` in the tuner worker:

```python
# scripts/training/auto_tuner_multi.py  — _run_single_instrument()
runner = BacktestRunner(bt_cfg, csv_path=csv_path, skip_features=True)   # ← ADD
```

**Expected gain:** Eliminates `pd.read_csv` + full indicator computation on every worker call. For a 100k-row CSV, FeaturePipeline takes ~0.5–2s. Across 7200 calls this is **60–240 minutes of pure wasted CPU**, gone with two line changes.

**Risk:** None. `features` field in `TradeRecord` defaults to `{}` (→ all 0.0 in CSV output), which is acceptable for tuner runs. Full-feature runs still work when `skip_features=False` (default).

---

### P2 — Cache Timestamp Format in `CandleLoader` `[HIGH]`

**File:** `src/runtime/backtest_v2.py` → `CandleLoader._parse_timestamp()`

**Problem:**  
For every candle row, `_parse_timestamp` tries up to **8 datetime format strings** in a try/except loop. A 100k-row CSV incurs up to 800k format-parse attempts.

**Fix:**

```python
# CandleLoader.__init__  — add instance variable
def __init__(self, filepath: str, instrument: str = "UNKNOWN"):
    self.filepath   = filepath
    self.instrument = instrument
    self.log        = logging.getLogger("CRT.CandleLoader")
    self._ts_format: Optional[str] = None    # ← ADD: cached after first success

# CandleLoader._parse_timestamp  — detect and cache
def _parse_timestamp(self, raw: str) -> datetime:
    if self._ts_format:                      # ← fast path: use cached format
        try:
            return datetime.strptime(raw.strip(), self._ts_format)
        except ValueError:
            self._ts_format = None           # invalidate on failure (malformed row)

    for fmt in self.DATE_FORMATS:            # ← slow path: format detection
        try:
            result = datetime.strptime(raw.strip(), fmt)
            self._ts_format = fmt            # ← cache for next row
            return result
        except ValueError:
            continue
    raise ValueError(f"Cannot parse timestamp: '{raw}'")
```

**Expected gain:** Reduces timestamp parsing from O(8) try/excepts to O(1) for 99.9% of rows. Noticeable on large CSVs.

**Risk:** None. Graceful fallback if a row has a different format.

---

### P3 — Precompute Feature Index Lookups `[HIGH]`

**File:** `src/runtime/backtest_v2.py` → `BacktestRunner.run()` (approx. lines 1391–1396)

**Problem:**  
Inside the candle loop, at every `TRADE_OPENED` event:

```python
_idx = _feat_names.index(_fn) if _fn in _feat_names else -1
```

`list.index()` is O(N) where N=35. This runs 3 times per `TRADE_OPENED`. While `TRADE_OPENED` events are sparse, it is still unnecessary repeated computation and `_fn in _feat_names` is a second O(N) scan.

**Fix:** Precompute once in `BacktestRunner.__init__`:

```python
# In BacktestRunner.__init__  — add after the FeatureMonitor block
_drift_feature_names = ("retest_depth", "body_ratio", "disp_strength")
self._drift_feat_indices: dict[str, int] = {
    fn: CANONICAL_FEATURES.index(fn)
    for fn in _drift_feature_names
    if fn in CANONICAL_FEATURES
}
```

Then in `run()` replace the 3-call index loop:

```python
# Replace lines ~1390-1397  (the _drift_dict construction block)
_drift_dict = {
    fn: float(_fv[idx]) if idx < len(_fv) else 0.0
    for fn, idx in self._drift_feat_indices.items()
}
```

**Expected gain:** Minor but zero-risk. Eliminates repeated O(35) list scans.

---

### P4 — Session Lookup via Hour Cache `[MEDIUM]`

**File:** `src/runtime/backtest_v2.py` → `BacktestRunner._session()`

**Problem:**  
`_session(ts)` is called on every candle. It iterates over `session_windows.items()` for every call. With M15 data: 96 candles/day × years of data = millions of calls, each doing a dict iteration + `time()` object comparison.

**Fix:** Build a 24-entry hour → session name lookup in `__init__`:

```python
# In BacktestRunner.__init__  — add after crt_cfg line
self._hour_to_session: dict[int, str] = {}
for h in range(24):
    t = time(h, 0)
    matched = next(
        (name for name, (start, end) in self.crt_cfg.session_windows.items()
         if start <= t <= end),
        "OFF_SESSION",
    )
    self._hour_to_session[h] = matched
```

Replace `_session()`:

```python
def _session(self, ts: datetime) -> str:
    return self._hour_to_session.get(ts.hour, "OFF_SESSION")
```

**Expected gain:** Eliminates dict iteration + time comparison on every candle. On a 200k-candle run this is ~200k iterations → 1 lookup each.

**Risk:** Assumes session windows don't span midnight (which is consistent with existing code). If they do, the existing logic already handles it and can be retained.

---

### P5 — Running Max Drawdown in `CapitalCurve` `[MEDIUM]`

**File:** `src/runtime/backtest_v2.py` → `CapitalCurve`

**Problem:**  
`CapitalCurve.max_drawdown_pct` is a `@property` that scans the **entire `equity_curve` list** from the beginning on every access. In `MetricsEngine.compute()` it is called once per backtest — not a hot-path issue for a single run — but it contributes to tuner overhead when thousands of backtests execute back-to-back.

**Fix:** Maintain a running max drawdown as trades are closed:

```python
# In CapitalCurve.__init__  — add
self._max_drawdown_pct: float = 0.0   # maintained incrementally

# In CapitalCurve.apply_trade()  — add after peak_capital update
dd = (self.peak_capital - self.current_capital) / self.peak_capital \
     if self.peak_capital > 0 else 0.0
self._max_drawdown_pct = max(self._max_drawdown_pct, dd)

# Replace max_drawdown_pct property  — O(1) read
@property
def max_drawdown_pct(self) -> float:
    return self._max_drawdown_pct
```

**Expected gain:** Turns `max_drawdown_pct` from O(n_trades) scan to O(1). Additionally removes the need to keep the full `equity_curve` list if memory reduction is later desired.

**Risk:** None — semantically identical. The `equity_curve` list can be kept for `to_dict()` and debugging.

---

### P6 — Skip Report Writing in Tuner Workers `[MEDIUM]`

**File:** `src/runtime/backtest_v2.py` → `BacktestRunner.run()`  
**File:** `scripts/training/auto_tuner_multi.py` → `_run_single_instrument()`

**Problem:**  
Every tuner worker calls `runner.run(stream, candle_cnt, output_dir=output_dir)` which creates a `ReportWriter` and writes **4 files per instrument per param set**: `_summary.json`, `_trades.csv`, `_events.jsonl`, `_report.txt`. For 7200 evaluations × 4 files = **28800 file write operations** that are never read by the tuner.

**Fix A:** Add `write_reports: bool = True` param to `BacktestRunner.run()`:

```python
# BacktestRunner.run() signature
def run(self, candle_source, total_candles, output_dir="results",
        write_reports: bool = True) -> BacktestMetrics:
    ...
    # near the end, wrap writer call:
    if write_reports:
        paths = writer.write_all(m, journal, flushed_events)
        self.log.info("Output:")
        for k, p in paths.items():
            if p: self.log.info(f"  {k:<15} → {p}")
    return m
```

**Fix B:** Pass `write_reports=False` in tuner:

```python
# scripts/training/auto_tuner_multi.py  — _run_single_instrument()
m = runner.run(stream, candle_cnt, output_dir=output_dir, write_reports=False)
```

**Expected gain:** Eliminates ~28800 disk writes per full tuning run. On a spinning HDD or networked drive this compounds significantly. Also frees the overhead of `DistributionAnalyser.analyse()` and `ReportWriter._write_report()` which are called only to populate the report files.

**Risk:** None. Tuner only reads the returned `BacktestMetrics` object.

---

### P7 — O(n²) → O(n) Rolling Win Rate `[LOW-MEDIUM]`

**File:** `src/runtime/backtest_v2.py` → `DistributionAnalyser._rolling_win_rate()`

**Problem:**  
Current implementation:

```python
for i in range(window, len(trades) + 1):
    window_trades = trades[i - window:i]        # slice copies O(window) elements
    wr = sum(1 for t in window_trades if t.is_winner) / window
```

This is O(n × window). For 500 trades with window=10: 5000 iterations.

**Fix:** Sliding window with integer counter:

```python
def _rolling_win_rate(self, trades: list[TradeRecord], window: int) -> list[float]:
    if len(trades) < window:
        return []
    wins_in_window = sum(1 for t in trades[:window] if t.is_winner)
    rates = [round(wins_in_window / window, 3)]
    for i in range(window, len(trades)):
        wins_in_window += trades[i].is_winner
        wins_in_window -= trades[i - window].is_winner
        rates.append(round(wins_in_window / window, 3))
    return rates
```

**Expected gain:** O(n) instead of O(n×window). Minor at typical trade counts but correct by construction and cleaner.

**Risk:** None — output is identical.

---

### P8 — Reduce Log I/O in Tuner Workers `[LOW]`

**File:** `src/runtime/backtest_v2.py` — module-level logger setup

**Problem:**  
The persistent file handler `_bt_fh` on `bt_log` is set to `logging.DEBUG`. Every tuner worker subprocess inherits this handler and writes to `logs/backtest_debug.log` for every candle batch. With thousands of workers writing concurrently, this creates both I/O contention and a very large log file.

**Fix:** Add a config flag in `configs/production/v1_multi_2026_03.json → backtest`:

```json
"backtest_log_level": "WARNING"
```

In `backtest_v2.py` module init:

```python
# After the existing _bt_fh setup
try:
    from config_layer.production_config import get_prod_section as _gps
    _log_level_str = _gps("backtest").get("backtest_log_level", "DEBUG")
    _log_level = getattr(logging, _log_level_str.upper(), logging.DEBUG)
    bt_log.setLevel(_log_level)
    _bt_fh.setLevel(_log_level)
except Exception:
    pass
```

Alternatively, for a zero-config fix, simply raise the file handler level for tuner runs:

```python
# In _run_single_instrument(), before BacktestRunner
logging.getLogger("CRT.Backtest").setLevel(logging.WARNING)
```

**Expected gain:** Eliminates DEBUG log writes during the candle loop. Reduces disk I/O and lock contention between worker processes.

**Risk:** Reduces visibility during debug sessions. Only apply to tuner workers — standalone backtest runs should retain DEBUG.

---

## 3. Implementation Order

| Priority | Fix | Files Touched | Estimated Effort | Expected Gain |
|----------|-----|---------------|-----------------|---------------|
| P1 | Skip FeaturePipeline in tuner | `backtest_v2.py`, `auto_tuner_multi.py` | 15 min | **Very high** |
| P2 | Cache timestamp format | `backtest_v2.py` | 10 min | High |
| P3 | Precompute feature indices | `backtest_v2.py` | 5 min | Medium |
| P4 | Session hour cache | `backtest_v2.py` | 10 min | Medium |
| P5 | Running max drawdown | `backtest_v2.py` | 10 min | Medium |
| P6 | Skip report writing in tuner | `backtest_v2.py`, `auto_tuner_multi.py` | 10 min | Medium |
| P7 | O(n) rolling win rate | `backtest_v2.py` | 5 min | Low |
| P8 | Reduce log level in tuner | `backtest_v2.py`, `auto_tuner_multi.py` | 5 min | Low |

**Total estimated effort:** ~70 minutes of surgical edits.

---

## 4. Verification Protocol

After each fix, verify with:

```bash
# 1. Unit tests must stay green
python -m pytest tests/ -x -q

# 2. Single-instrument sanity check (wall-clock before/after)
time python src/runtime/backtest_v2.py \
  --csv data/EURUSD_M15.csv --instrument EURUSD

# 3. Tuner smoke run (5 iterations, 2 instruments)
python scripts/training/auto_tuner_multi.py \
  --data-dir data/ --instruments EURUSD GBPUSD --max-trials 5

# 4. Confirm metrics are numerically unchanged (compare summary JSON)
diff results/<before>/<inst>_summary.json results/<after>/<inst>_summary.json
```

For P1 specifically: verify that a full-feature run (`skip_features=False`) still produces non-zero feature columns in `_trades.csv`.

---

## 5. Future Work (Out of Scope for This Plan)

These require broader changes and are noted for future consideration:

- **Vectorised candle processing:** Replace the Python `for candle in candle_source` loop with a batch-apply pattern using a pre-loaded numpy array. Requires significant refactoring of `CRTEngine.process_candle` (currently stateful/sequential — inherently loop-bound).
- **Shared memory for tuner workers:** Pre-compute FeaturePipeline results in the parent process and pass via `multiprocessing.shared_memory` to avoid per-worker CSV re-reads. Blocked until `ProcessPoolExecutor` initialiser pattern is established.
- **Numba/Cython for ATR/EMA hot loops:** Would speed up `FeaturePipeline.compute_indicators()` by 5–10×, but adds a compiled dependency (violates the current stdlib-first philosophy unless approved).
- **Incremental FeaturePipeline for live mode:** `live_engine_hook.py` currently re-runs batch features. A streaming feature updater would reduce live-bar latency.

---

## 6. Constraints Respected

All fixes above comply with:
- No new dependencies (stdlib + existing pandas/numpy only)
- No magic numbers in Python (new config keys added to `v1_multi_2026_03.json`)
- No architecture changes (same class hierarchy, same data flow)
- Fail-fast config loading preserved
- No lookahead introduced
- All changes are additive (new optional parameters, not breaking existing callers)

---

*Generated by Claude — Tradelatest session 2026-04-28*
