# Plan — Backtest a 2-month XAUUSD window + record the corpus-guard finding

## Context

Earlier this session we established the canonical XAUUSD corpus (`data/mt5/XAUUSD_M15.csv`,
sha `4d73f5ce…`, 47,275 rows) and built `scripts/analysis/export_xauusd_window.py`, which
produced a 2-month Excel export (3,949 rows, 2026-03-23 → 2026-05-21).

The user now wants that 2-month window run through `backtest_v2`. Two blockers were found:

1. **The corpus guard silently substitutes the full corpus.** `guard_xauusd_csv_path` is
   called at four sites in `backtest_v2`, and `is_xauusd_m15_request`
   ([xauusd_phase1_candidate.py:200-215](src/data_ingestion/xauusd_phase1_candidate.py:200))
   matches on filename prefix *with no extension check*, **and** on a second branch
   (`instrument == "XAUUSD"` AND `"M15"` in filename). Any such path is rewritten to the
   frozen 47,275-row corpus with only an `INFO` log. A user believing they ran a 2-month
   backtest would actually have run the full 2-year one.
2. **`.xlsx` cannot be read.** Three independent readers parse the input — `CandleLoader.stream`
   ([:723](src/runtime/backtest_v2.py:723), stdlib `csv`), `BacktestRunner.__init__`
   ([:1651](src/runtime/backtest_v2.py:1651), `pd.read_csv`), and the L2 integrity gate
   ([dataset_integrity.py:530](src/data_ingestion/dataset_integrity.py:530), stdlib `csv`).

**User decisions:** export CSV rather than teach three readers `.xlsx` (the L2 gate is the
one net remaining on most paths per F-039 — not where to add a format branch under time
pressure); and **log** the guard defect rather than fix it, in a new timestamped findings file.

Intended outcome: a real backtest over exactly the 2-month window, plus a recorded finding.

## Filename design (the non-obvious part)

The output name must satisfy three constraints simultaneously:

| Constraint | Requirement |
|---|---|
| Dodge guard branch 1 | must NOT start with `XAUUSD_M15` |
| Dodge guard branch 2 | must NOT contain `M15` (fires when `--instrument XAUUSD` is passed) |
| Keep L2 symbol parsing | `_parse_symbol_tf` ([dataset_integrity.py:456](src/data_ingestion/dataset_integrity.py:456)) does `stem.rsplit("_", 1)` — the text before the LAST underscore must be exactly `XAUUSD`. **CORRECTED 2026-07-18:** the reason originally given here — "or the market-class/session calendar is misdetected and the gap gate misfires" — was WRONG for gold. `classify_market` ([:114](src/data_ingestion/dataset_integrity.py:114)) only tests for a crypto quote suffix (USDT/USDC/BUSD), so a garbled XAUUSD symbol still resolves to `WEEKDAY`, identical to the clean one. **Actual** enforcement is `_check_path_consistency` ([:516](src/data_ingestion/dataset_integrity.py:516)): `instrument.upper() != symbol.upper()` is a HARD failure → REJECT. The wrong-calendar failure mode is real but applies only to CRYPTO symbols, where garbling breaks the suffix test. |
| **Canonical data root — MISSED in the first pass** | `_check_path_consistency` ([:506](src/data_ingestion/dataset_integrity.py:506)) requires the file to sit under `roots: ['data']`. The `results/` export **REJECTs** — confirmed by running `validate_dataset` on the shipped file. `backtest_v2` then aborts via `sys.exit(1)` ([:2811](src/runtime/backtest_v2.py:2811)) before streaming a single candle. The earlier "verification" checked guard passthrough but never ran the preflight gate. |

Chosen: **`XAUUSD_W2026-03-23-to-2026-05-21.csv`**
→ `rsplit("_",1)` = `("XAUUSD", "W2026-03-23-to-2026-05-21")` → symbol `XAUUSD` correct;
unparseable TF falls back to `default_bar_minutes: 15`
([v2_multi_2026_04.json:648](configs/production/v2_multi_2026_04.json:648)), which matches
the real modal delta, so the timeframe-consistency check passes. Dates stay in the filename.
`--instrument XAUUSD` still resolves `pip_size = 0.01`
([backtest_v2.py:2608](src/runtime/backtest_v2.py:2608)) — a fake instrument would silently
get the 0.0001 FX default, a 100x error in spread/slippage.

## Implementation

### 1. `scripts/analysis/export_xauusd_window.py` — add CSV output

- New `--format {xlsx,csv,both}`, default `xlsx` (existing behavior unchanged).
- CSV branch writes the guard-safe name above via `df.to_csv(index=False)`; xlsx branch keeps
  the current `XAUUSD_M15_{start}_to_{end}.xlsx` name.
- Reuse the existing `export_window()` slice logic verbatim — only the write step and the
  filename template branch. The source read stays `guard_xauusd_csv_path`-resolved, so the
  export is still provably a slice of the frozen corpus.
- Print the parent lineage (`parent_sha256=4d73f5ce…`, row range) alongside the output path.

### 2. Run the backtest

```
python src/runtime/backtest_v2.py \
  --csv results/XAUUSD/exports/XAUUSD_W2026-03-23-to-2026-05-21.csv \
  --instrument XAUUSD --output results/XAUUSD/backtests
```

Record in the run notes whether `BACKTEST_ENGINE_GATE` was on or off (F-037: `.env` sets `0`
⇒ CRT-only, no 4-engine fusion veto). Do **not** read `.env` — report the effective value from
the run's own config dump / log output.

**Expect a low trade count.** ~3,949 candles minus FeaturePipeline warmup (~254 rows, 6.4%
here vs 0.5% on the full corpus) minus HTF seed. This will land below the `min_trades` gates
in `config_validator`. That is an expected INSUFFICIENT-power result, not a bug — report it
as such and make no edge claim either way (§6.5 Authority Ladder).

### 3. New findings file

`docs/analysis/session-findings-2026-07-18-xauusd-window-backtest.md` — `docs/analysis/` is
the repo's home for point-in-time, non-living documents (§6.2 rule 5), which is what a
session-scoped findings file is. Same table shape as `docs/current-findings.md`
(id · type · conclusion · confidence · evidence · date).

Use **session-scoped IDs (`SF-001…`), not `F-0NN`.** An `F-` id would have to appear in both
`docs/current-findings.md` and the CLAUDE.md Repository Truths Index — `tests/test_current_findings.py`
enforces that correspondence in both directions, so minting one here would break the floor.
Note in the doc that any entry may be promoted to a real `F-` id later.

Entries to record:
- **SF-001 (ARCH):** the guard's extension-blind + instrument-branch substitution, with the
  `.xlsx` worked example and the `INFO`-only log line. Include that this session's export
  deliberately uses a guard-invisible filename, so the bypass is **declared, not silent** —
  with parent sha, row count, and exact time range as the derivation record (the G-10
  "declared synthesis is admissible, undeclared is the defect" rule).
- **SF-002 (ARCH):** `.xlsx` files in `data/` (e.g. `BNBUSDT_M15_2year.xlsx`) fail with an
  obscure `UnicodeDecodeError` rather than a clear "CSV only" error; three readers involved.
- **SF-003 (GOV):** carried-over drift from earlier this session — the stale
  `SECONDLOW_RESEARCH_DATA_POLICY.md:61-62` duplicate claim, and the two guard-bypassing
  scripts (`_enrich_xauusd_corpus.py:35`, `trace_zone_gate_xauusd.py:50`).

## Verification

1. Run the exporter with `--format csv`; confirm stdout reports source sha `4d73f5ce…`.
2. **Prove the guard did not swap the file** — the whole point:
   ```python
   from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path
   p = "results/XAUUSD/exports/XAUUSD_W2026-03-23-to-2026-05-21.csv"
   assert guard_xauusd_csv_path(p, "XAUUSD") == p   # unchanged => reaches the loader intact
   ```
3. Confirm the CSV is an exact row-for-row match to the existing .xlsx (same 3,949 rows).
4. Run the backtest. Confirm from the log that the loaded row count is ~3,949 and **not**
   47,275 — the direct falsification of blocker 1.
5. Inspect `results/XAUUSD/backtests/run_*/XAUUSD_summary.json` for trade count and metrics;
   state the count plainly and flag INSUFFICIENT power rather than reporting an edge.
6. `pytest tests/test_current_findings.py tests/test_session_log.py -q` — confirm the new
   findings file breaks neither floor (it shouldn't; it's a separate doc with non-`F-` ids).
7. Append the §6 SESSION LOG entry to `assistant_project.md`.

## Out of scope

- Fixing the guard (user chose log-only). SF-001 records it.
- `.xlsx` reader support — DEFERRED to future phases, see below.
- The two guard-bypassing research scripts and the stale SECONDLOW policy row (SF-003).
- MT5 integration — parked by the user for future paper-trade/automation phases.

---

## FUTURE PHASES (deferred, not scheduled)

Parked by the user 2026-07-18. Nothing below is started; each needs its own pre-registration
before implementation.

### FP-1 — Native `.xlsx` ingestion for `backtest_v2`

**Why deferred:** the current path is unblocked by exporting CSV instead
(`export_xauusd_window.py --format csv`), so this is a convenience/robustness item, not a
blocker. It touches the L2 integrity gate, which per F-039 is the single remaining net on
most `CandleLoader.stream()` consumers — not a change to make under time pressure.

**Real scope — FOUR readers, not one.** A single-instrument run reads the input file
start-to-finish four times, and every one is CSV-native:

| Pass | Call site | Reader | Purpose |
|---|---|---|---|
| 1 | `main` → `_preflight_dataset` ([backtest_v2.py:2811](../../src/runtime/backtest_v2.py)) | `open()` + `csv.reader` ([dataset_integrity.py:530](../../src/data_ingestion/dataset_integrity.py)) | L2 whole-sequence integrity gate |
| 2 | `BacktestRunner.__init__` ([:1651](../../src/runtime/backtest_v2.py)) | `pd.read_csv` | whole-frame `FeaturePipeline` (rolling windows) |
| 3 | `loader.count()` ([:790](../../src/runtime/backtest_v2.py)) | `open()` + line count | progress-bar row total |
| 4 | `loader.stream()` ([:723](../../src/runtime/backtest_v2.py)) | `open()` + `csv.reader` | sequential candle loop (no-lookahead) |

Passes 2 and 4 cannot be merged — 2 needs the whole frame for vectorized rolling windows,
4 must be sequential to preserve the no-lookahead guarantee. That opposition is why they
join on **timestamp string** rather than row index ([:1672](../../src/runtime/backtest_v2.py)).

**Work required:** a shared suffix-dispatching loader used by all four; the existing
`load_ohlcv` at [src/research/secondlow_v1/detector.py:44](../../src/research/secondlow_v1/detector.py)
is the closest pattern, but it sets `timestamp` as the **index**, which `FeaturePipeline`
rejects (it wants a timestamp *column*) — so it needs adapting, not reusing as-is. Plus
tests across both formats, and a decision on whether the L2 gate's strict row-by-row
validation is reproducible over a pandas-loaded frame.

**Latent bug this would fix (SF-002):** `data/` already contains `.xlsx` files
(`BNBUSDT_M15_2year.xlsx`, `BTCUSDT_M15_2year.xlsx`, `AUDUSD_M15_1year.xlsx`). Passing one
today produces a `UnicodeDecodeError` on ZIP bytes rather than a clear "CSV only" message.
A cheap partial win, independent of full support: an explicit suffix check in
`CandleLoader.__init__` that raises a readable error.

### FP-2 — Redundant-read cleanup (SF-004)

Pass 3 has no justification beyond a cosmetic progress percentage and is a full extra file
scan; `stream()` already knows how many rows it yielded. Also, all four passes independently
re-invoke `guard_xauusd_csv_path`, each re-hashing the full 47,275-row corpus (SHA-256 ×3–4
per run). Both are pure waste, but touching them means touching the hot path — needs a
parity proof (byte-identical ledger) per §6.5, not a casual edit.

### FP-4 — Close the timeframe-consistency gap (SF-005)

**Status: NEEDS TO FIX — deferred until the user's full analysis pass is done, 2026-07-18.**
**Decision made:** option (a) below — move the check into `CandleLoader.stream()`. Not yet
implemented; do not implement until the user says to resume this item.

CONFIRMED real gap, not present-and-missed. The modal-inter-bar-delta check exists and
works ([dataset_integrity.py:378-385](../../src/data_ingestion/dataset_integrity.py)) —
an M5 file mislabeled M15 is caught **when `validate_dataset` runs**. The gap is *reach*:
per F-039, that gate runs on only two call sites (`backtest_v2`'s `_preflight_dataset` /
`validate_universe`). Every other `CandleLoader.stream()` consumer — the entire
`src/research/` pipeline, `config_validator`, `portfolio_validation`,
`unified_replay_harness` — streams with only the **inline** L1/L2 backstop inside
`stream()` ([backtest_v2.py:759-770](../../src/runtime/backtest_v2.py)), which checks
duplicate/out-of-order timestamps but has **no timeframe check at all**. A mislabeled
file sails through those paths silently; every rolling-window feature
(RSI(14)/ATR(14)/MA(200)/the z-score windows) then computes over the wrong time span
with no error, no warning, nothing in the run's own logs to indicate it.

**Chosen fix — move the modal-delta check into `CandleLoader.stream()`'s always-on inline
backstop** ([backtest_v2.py:759-770](../../src/runtime/backtest_v2.py)), alongside the
existing duplicate/out-of-order checks, so it applies to **every** `stream()` caller —
not just the two `backtest_v2` entry points that currently opt into the separate
`validate_dataset` pre-flight. Rejected alternative: auditing + wiring `validate_dataset`
as a pre-flight call at each of the 5+ other consumer sites individually — matches the
existing "L2 is opt-in per caller" design but requires touching every call site instead
of the one shared streamer, and each site could drift again later.

**Implementation shape (for when this is picked up):** the modal-delta computation at
[dataset_integrity.py:378-385](../../src/data_ingestion/dataset_integrity.py) needs the
*whole* delta sequence (`statistics.mode(deltas)`), but `stream()` yields candles one at
a time — so it can't raise on the first bar the way duplicate/order checks do. Likely
shape: accumulate a bounded rolling window of deltas (or the running mode over what's
been seen so far) and raise once a stable modal mismatch is detected, OR require the
expected `bar_minutes` be passed into `CandleLoader.__init__` (already resolvable from
the filename via `_parse_symbol_tf`/`_TF_MINUTES`, or from config) and compare each
inter-candle delta against it directly — the latter is simpler and doesn't need to wait
for a mode to stabilize. Needs a parity check that existing correctly-labeled corpora
(BNB/ETH/BTC/SOL/EURUSD/XAUUSD) still pass unchanged — this touches shared code
(`ohlcv_schema.py` / `CandleLoader`), not a leaf script, so every `stream()` consumer is
in the blast radius.

### FP-5 — Duplicate-timestamp handling: VERIFIED already correct, no action needed

**User asked, 2026-07-18:** should a duplicate timestamp (same bar-time, two different
`close` values) stop execution with an error? **Answer: it already does, on two
independent layers, both verified by reading the enforcement code (not the docstring):**

1. L2 pre-flight ([dataset_integrity.py:341-345](../../src/data_ingestion/dataset_integrity.py))
   — first duplicate seen → `hard.append(...)` → `decision=REJECT` →
   `backtest_v2` `sys.exit(1)` before any candle streams.
2. Inline backstop in `CandleLoader.stream()`
   ([backtest_v2.py:764-767](../../src/runtime/backtest_v2.py)) — raises
   `DatasetIntegrityError` mid-stream on the second occurrence, independent of whether
   the pre-flight gate ran. This is what protects the F-039 non-preflighted consumers.

No implementation item here. Recorded so this doesn't get re-flagged as open work later.

### FP-3 — MT5 live/paper-trade integration

Parked. Read path (candles, deals) is live and load-bearing; write path (`MT5Bridge.send_order`,
[src/live/mt5_bridge.py:212](../../src/live/mt5_bridge.py)) is built but inert behind three
gates: `live_integration.mt5.enabled=false`, `dry_run=true`, and no non-test caller of the
live hook. Relevant when paper trading / automation testing on live data begins. See F-010
(live PnL UNVERIFIED).
