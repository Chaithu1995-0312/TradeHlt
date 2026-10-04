# Plan — Process Characterizer for BNBUSDT M15

## Context

**Thesis to test:** "Volatility has memory; direction mostly does not." If BNBUSDT M15
log-returns are ~random walk (Hurst H≈0.5, fast-decaying autocorrelation) while ATR is
persistent (H>0.5, slow-decaying autocorrelation), then the directional filters in the
spine (`ema_fast`/`ema_slow`/MACD-style alignment) are optimizing for a signal that
statistically does not exist — paying spread/slippage on chop.

**This plan delivers measurement only.** It produces the evidence; it does **not** touch
the spine, the production config, or any directional filter. Gutting/de-weighting
directional gates for BNB is a *downstream* governed decision (deviation flag + Five
Questions per `docs/architecture/goal.md`) that is premature until the numbers exist.
Scope here = build the diagnostic and emit a process manifest.

## What we build

A deterministic, measure-only characterizer that ingests `data/BNBUSDT_M15.csv` (note:
real file is `BNBUSDT_M15.csv`, not `_real`) and emits three measurements:

- **A. Autocorrelation** — sample ACF over lags k∈[1,50] for log-returns `r_t` and for
  `ATR_t` (and `|r_t|` as a second volatility proxy). Decay comparison is the core test.
- **B. Hurst / variance-ratio** — Rescaled-Range (R/S) Hurst exponent for price-returns
  vs. volatility series, plus a Lo-MacKinlay-style variance ratio. Reported per series.
- **C. 6-state Markov transition matrix** — state = {Compression/Normal/Expansion} ×
  {Up/Down}. Volatility axis split at **data-driven terciles** (33rd/66th pct of ATR;
  cut points reported). Direction axis = sign of log-return. Emit the row-normalized
  transition matrix `P_ij` + raw counts, and flag near-uniform exit rows (entropy) as the
  "direction is a coin-flip" signal.

## Structure (Module + thin CLI)

1. **`src/research/process_characterization.py`** — pure, deterministic, no I/O. Functions
   operating on plain lists/arrays:
   - `autocorrelation(series, max_lag) -> list[float]`
   - `hurst_rs(series) -> float` and `variance_ratio(series, q) -> float`
   - `digitize_states(returns, atr_series) -> list[str]` (terciles + sign)
   - `transition_matrix(states) -> (matrix, counts, labels)`
   - `characterize(candles) -> ProcessManifest` (orchestrates A/B/C)
   - `@dataclass(frozen=True) ProcessManifest` with **only deterministic fields** (no
     wall-clock) — mirrors the `edge_report.json` discipline in
     `src/research/runner.py:129` / `provenance.py`.
   - Reuse `compute_atr` from `src/research/indicators.py:12` (already the research-layer
     ATR helper) rather than reimplementing.

2. **`scripts/analysis/process_characterizer.py`** — thin argparse wrapper only (matches
   `scripts/analysis/funnel_diagnosis.py` / `session_cost_audit.py` house style):
   - `--csv data/BNBUSDT_M15.csv --instrument BNBUSDT --max-lag 50 --vr-q 2,4,8,16`
   - Loads candles via `CandleLoader(...).stream()` (`src/runtime/backtest_v2.py:626`).
   - Calls `characterize(...)`, prints a `safe_print` summary table
     (`src/utils/console_safe.py`), and writes `results/analysis/process_manifest_{instrument}.json`
     (deterministic body) alongside a small `*_run_manifest.json` carrying wall-clock /
     git-commit, exactly like `src/research/cli.py:87` splits the two.

## Conventions honored

- **No spine/config edits, no lookahead** — operates on the full historical series offline;
  ACF/Hurst/Markov are whole-series statistics (not streamed features), so no leakage into
  any live decision path.
- **Determinism** — pure functions, sorted iteration, pre-rounded outputs, wall-clock kept
  out of the manifest body (split into run-manifest) per existing research-layer pattern.
- **Numpy only** — used for ACF/R/S/var-ratio (already a de-facto dep across `src/`).
  Avoid `scipy` (Hurst slope via `numpy.polyfit`, not `scipy.linregress`) to add zero new
  dependencies. Pandas only in the CLI if convenient for loading; core math is numpy/stdlib.
- Reuse, don't reinvent: `compute_atr` (`src/research/indicators.py:12`), `Candle`
  (`src/config_layer/crt_engine_v2.py:94`), `CandleLoader`, `console_safe`.

## Tests

`tests/research/test_process_characterization.py` (pure-function coverage, no I/O):
- ACF of i.i.d. noise ≈ 0 at all lags>0; ACF of an AR(1) decays geometrically.
- Hurst of a synthetic random walk ≈ 0.5 (±tol); of a strongly trending/anti-persistent
  series clearly >0.5 / <0.5.
- `transition_matrix` rows sum to 1.0; counts match input length−1; label set is the 6
  expected states.
- `digitize_states` tercile cut points reproduce on a fixed array (determinism).

## Verification (end-to-end)

```
python scripts/analysis/process_characterizer.py --csv data/BNBUSDT_M15.csv --instrument BNBUSDT
pytest tests/research/test_process_characterization.py -q
```
- Confirm `results/analysis/process_manifest_BNBUSDT.json` is written and byte-identical
  across two consecutive runs (determinism check).
- Read the manifest: compare ACF decay (returns vs ATR), the two Hurst exponents, and the
  Markov exit-row entropy. These three numbers either confirm or falsify the thesis.

## Out of scope (explicit)

- Any change to directional filters, `crt_engine_v2.py`, or
  `configs/production/*.json`. If results confirm the thesis, that becomes a **separate**
  governed proposal (deviation flag → Five Questions → config isolation for BNB), planned
  after the numbers are in.

## Per-CLAUDE.md §6

Append the `📝 SESSION LOG ENTRY` block to `assistant_project.md` on implementation.
