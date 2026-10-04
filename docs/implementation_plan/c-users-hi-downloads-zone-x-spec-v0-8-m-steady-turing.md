# ZONE-X O-1 — MT5 Cost Calibration Script

## Context

The external research programme **ZONE-X** (`ZONE-X-SPEC-v0.8.md`, frozen spec, gold M15
region-discovery, not part of the Tradelatest governed pipeline) has produced a clean null
result on directional/straddle geometry (§6) and has exactly one blocking open item left:
**`O-1`** — the assumed round-trip trading cost (`c = 0.07` ATR/side, i.e. **$0.51/oz/side**
at the test-year median ATR) was **never verified against a real broker**. Halving it to
`c = 0.03` (**$0.22/oz/side**) would cut the required directional edge fourfold (2.1pp →
0.5pp) — no feature/model choice on the table moves the target that far, so this single
number governs whether the programme's next move is "stop" or "continue."

The user has an MT5 terminal already installed locally and wants a script that pulls the
four real numbers the spec asks for — spread by hour, commission, stop-order slippage, swap
— so `c` stops being an estimate. This is explicitly a **standalone research diagnostic**:
it does not touch production config, `ACTIVE_VERSION`, the promotion pipeline, or any
governed engine, and the user has asked to skip the full CLAUDE.md documentation-mandate
ritual for this thread (no SESSION LOG / doc-drift gating) — it follows the lighter
`scripts/research/` convention already used for scripts like `xauusd_price_cost_trace.py`.

Exploration confirmed the repo already has the two hard pieces reusable: `MT5Adapter`
(`mt5_analytics/core/mt5_adapter.py`) solves the MT5 connection lifecycle and — critically —
the broker-server-clock-to-UTC offset correction (the same class of bug F-066 found in
session labeling), and `xau_metals_protocol_v1.json` already carries a **pre-registered
prior of $0.40/oz round-trip (~$0.20/side)** for XAUUSD that this script's output will
directly validate or contradict.

## Design decisions

1. **Don't modify `mt5_adapter.py`.** It's the frozen read-surface of an audited kernel
   (`mt5_analytics/`) with its own migration log. Build a sibling reader
   (`MT5CostReader`) that wraps an already-`__enter__`-ed `MT5Adapter` and reuses its
   public `server_utc_offset` for the two new read calls (`copy_ticks_range`,
   `symbol_info`) this task needs beyond the adapter's existing five. Zero duplication of
   the offset-detection math, zero risk to the audited kernel.
2. **Never fabricate a number.** Every one of the four quantities carries an explicit
   `status ∈ {MEASURED, INSUFFICIENT_DATA, UNKNOWN}`. Commission and stop-slippage need
   real trade history the account may not have yet — those degrade honestly instead of
   defaulting to 0.
3. **Cite the spec's ATR constants, don't recompute.** `ZONE-X-SPEC-v0.8.md §3.2` already
   froze ATR14 test-year median $7.342 (p10 $3.467, p90 $15.489) — the summary converts
   `c_per_side` to ATR units using these cited constants rather than pulling in a new
   feature-pipeline dependency for a throwaway diagnostic.
4. **Stop-order slippage is the target metric, not market-order slippage** — per the spec's
   own reasoning (every ZONE-X barrier is a stop order; 29% of bars gap from the prior
   close), `stop_slippage_median_usd`/`stop_status` are tracked as first-class fields
   distinct from the overall order-type breakdown, and only `stop_status` gates whether
   `c_per_side` can use a real number.
5. **Commission extraction handles both broker forms.** `mt5_analytics/MIGRATIONS.md`
   (2026-06-26 entry) already documents that a real broker (IC Markets Raw) folds
   commission onto each trade leg's own deal record rather than emitting a separate
   zero-volume commission deal — the extractor sums `commission` across all deals per
   `position_id` so it's correct under either form, and records which form was observed.
6. **Never persist account identity/balance.** `account_info()` is read transiently only
   (to check account currency for the swap $-conversion), matching the existing
   `FORBIDDEN_KEYS = ("balance","equity","margin","login","server")` no-persist rule
   enforced by `tests/manual/live_smoke.py:45`.
7. **The script never places or modifies orders** — strictly read-only, same posture as
   `MT5Adapter`. Building up real stop-order fill history (needed for items 2/3) is a
   manual step the user does in the MT5 GUI on a demo account; the plan documents the
   minimal-effort way to do that.

## Files to create

### `src/research/mt5_cost_calibration.py` (new — extraction library)
Style-matches `src/inout/mt5_candle_fetcher.py` (numbered section headers, fail-soft
`import MetaTrader5 as mt5` + fail-fast `RuntimeError`, dataclass config + strict
`_require()`, always `mt5.shutdown()` in `finally` — handled by the `MT5Adapter` context
manager here).

- `Status` enum: `MEASURED | INSUFFICIENT_DATA | UNKNOWN`.
- `CostCalibrationConfig` dataclass: `symbol="XAUUSD"`, `tick_lookback_days=14`,
  `history_lookback_days=90`, `tick_chunk_days=1`, `min_stop_fills_for_confidence=5`
  (reporting hint, never a silent gate), `out_dir`, `server_utc_offset_hours=None`.
- `MT5CostReader` — composition wrapper around an `MT5Adapter` instance; adds
  `copy_ticks_range_chunked()` (chunks `[date_from, date_to)` by `chunk_days`, pulls
  `mt5.COPY_TICKS_ALL`, filters ticks to `bid > 0 and ask > 0 and ask >= bid`, shifts
  timestamps via the adapter's `server_utc_offset`) and `symbol_info()`.
- Result dataclasses, each carrying `status`: `SpreadResult`, `CommissionResult`,
  `SlippageResult` (with a separate `stop_status`), `SwapResult`.
- Four extraction functions:
  - `extract_spread_by_hour(reader, symbol, date_from, date_to, chunk_days)` — groups
    `ask - bid` by `hour_utc` (24 buckets), reports median/p90/mean/n per hour.
  - `extract_commission(mt5a, symbol, date_from, date_to)` — groups
    `history_deals_get()` results by `position_id`, sums `commission` across all deals in
    each position (handles both the folded-per-leg and separate-zero-volume-deal forms),
    normalizes to $/lot/side and $/oz; `status=UNKNOWN` if zero nonzero-commission deals
    exist anywhere in the window.
  - `extract_slippage(mt5a, symbol, date_from, date_to)` — joins `history_orders_get()` to
    `history_deals_get()` on `deal["order"] == order["ticket"]`, classifies by
    `order["type"]` read from live `mt5.ORDER_TYPE_*` constants (MARKET / STOP / LIMIT /
    STOP_LIMIT), computes sign-adjusted adverse slippage `deal.price - order.price_open`
    per side; `stop_status=INSUFFICIENT_DATA` whenever `n_stop_fills == 0`.
  - `extract_swap(reader, symbol)` — reads `symbol_info()` (`swap_long`, `swap_short`,
    `swap_mode`, `trade_contract_size`, `swap_rollover3days`, `point`), converts to
    $/oz/night per the live `swap_mode` enum (POINTS / CURRENCY_SYMBOL handled; percent/
    interest-based modes and non-USD account currency → `UNKNOWN` with raw fields dumped).
- `compute_c_per_side(spread, commission, slippage)` — `spread_median/2 + commission_per_oz
  + stop_slippage_median`; overall status = worst-of-three (`UNKNOWN` > `INSUFFICIENT_DATA`
  > `MEASURED`), never silently substitutes 0 for a missing term.
- Output writers: `write_spread_csv`, `write_commission_json`, `write_slippage_csv`,
  `write_swap_json`, `render_summary_md`.

### `scripts/research/xauusd_mt5_cost_calibration.py` (new — thin CLI entry point)
Style-matches `scripts/research/xauusd_price_cost_trace.py` / `qualify_xauusd.py`
(`RESEARCH_ONLY` header docstring, `sys.stdout.reconfigure(...)` Windows console safety,
argparse wrapper delegating to `src/research/mt5_cost_calibration.py`).

CLI flags: `--symbol` (default `XAUUSD`), `--tick-days` (14), `--history-days` (90),
`--tick-chunk-days` (1), `--server-utc-offset-hours` (None, passthrough to `MT5Adapter`),
`--out-dir` (`results/research/xauusd_mt5_cost_calibration`), `--skip-ticks`,
`--skip-history`, `--min-stop-fills` (5, reporting only).

`main()`: opens `MT5Adapter` as context manager → builds `MT5CostReader` → runs the four
extractors → writes CSV/JSON + timestamped and `_LATEST` variants + an umbrella manifest
JSON (statuses, `c_per_side`, sha256 of each artifact, ZONE-X citation block — no account
identity/balance) → renders `XAUUSD_MT5_COST_CALIBRATION.md` → prints a short console
summary.

## Output artifacts

`results/research/xauusd_mt5_cost_calibration/`:
- `spread_by_hour_{ts}.csv` / `_LATEST.csv` — 24 rows, `hour_utc, n_ticks, median_spread_usd,
  p90_spread_usd, mean_spread_usd`
- `commission_{ts}.json` / `_LATEST.json`
- `slippage_by_order_type_{ts}.csv` / `_LATEST.csv` — one row per {MARKET, STOP, LIMIT,
  STOP_LIMIT}, STOP row is the one that matters
- `swap_{ts}.json` / `_LATEST.json`
- `xauusd_mt5_cost_calibration_manifest_{ts}.json` / `_LATEST.json`
- `XAUUSD_MT5_COST_CALIBRATION.md` — human summary: four-quantity status table,
  `c_per_side` in $/oz and in ATR units (citing `ZONE-X-SPEC-v0.8.md §3.2`), comparison
  against the repo's own `xau_metals_protocol_v1.json` 0.40 prior, comparison against
  ZONE-X §8.1's own thresholds (0.07 vs 0.03 ATR), and an explicit "what's still
  UNKNOWN/INSUFFICIENT_DATA and why" section.

## Known edge cases handled (see exploration for full detail)

- Tick chunking by day to bound IPC/memory cost; tick validity filter on raw bid/ask
  values rather than flag bits (flag-bit filtering would systematically undercount).
- Order-type constants read live from the `mt5` module, never hardcoded ints (broker/build
  sensitive). Unmatched order↔deal joins are counted and excluded, not zero-filled.
- `swap_rollover3days` read from the live enum, not assumed to be Wednesday.
- Thin/fresh account: spread and swap are measurable immediately (no trade history
  needed); commission and stop-slippage need real fills. If the account has none, the
  script reports `UNKNOWN`/`INSUFFICIENT_DATA` and the summary documents the manual path
  (place a spread of small STOP orders on the demo account at varied distances, let a few
  trigger over a few days, re-run with `--skip-ticks` to check accumulation) — the script
  itself never places orders.

## Setup prerequisite (blocking, before first run)

`MetaTrader5` is declared as an optional dependency (`pyproject.toml`
`[project.optional-dependencies].mt5_analytics`) but is **not installed** in either
`venv` or `.venv`. Requires `pip install MetaTrader5` (Windows-only wheel) plus a running,
logged-in MT5 desktop terminal before the script can execute.

## Verification

1. `pip install MetaTrader5` into the project venv; confirm a demo/live MT5 terminal is
   running and logged in.
2. Run `python scripts/research/xauusd_mt5_cost_calibration.py --tick-days 7
   --history-days 30` first as a fast smoke test (small windows) — confirm it connects,
   pulls at least some ticks, and writes all output files without exceptions, even if
   commission/slippage come back `UNKNOWN`/`INSUFFICIENT_DATA` on a fresh account.
3. Inspect `XAUUSD_MT5_COST_CALIBRATION.md` — verify the spread-by-hour table looks
   sane (tighter during London/NY overlap hours, wider in the Asian session per the
   spec's own expectation) as a sanity check on timestamp/offset correctness.
4. Once satisfied, re-run with production-sized windows (`--tick-days 30`,
   `--history-days 180`) for the real O-1 answer, and — if commission/slippage are still
   `UNKNOWN`/`INSUFFICIENT_DATA` — follow the manual stop-order path, then re-run with
   `--skip-ticks` periodically until enough stop fills accumulate.
