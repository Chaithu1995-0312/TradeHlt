# Plan — OHLCV clock-provenance gate (fail-closed)

## Context

Mining the CRT episode trace `results/crt_episode_trace/20260813T124158Z/` and tracing the A3 arm
to source established that **four independent surfaces answer "what session is it?"** and they
disagree at the same instant:

| # | Surface | Site | Reads `ts_basis` | SHORT terminal bar |
|---|---|---|---|---|
| 1 | `RiskScore.time_score` | `crt_engine_v2.py:1837-1844` | **NO** — raw `timestamp.time()` | `0.0` → `0.8` under A3 |
| 2 | Session **gate** | `crt_engine_v2.py:3106-3116` | yes | `OFF_SESSION` → in-session |
| 3 | FM-052 `session` feature | `feature_pipeline.py:716` | yes | `2` in **both** arms |
| 4 | `active_range.session` | default `:116`; reset path `:2656-2658` passes no arg | n/a | `UNKNOWN` |

Root cause upstream of all four: `mt5_candle_fetcher.py:186` labels MT5 **broker-server** time as
UTC, so every `data/mt5/*` corpus carries a mislabeled clock (F-066). Surface #1 cannot be fixed by
`feature_pipeline.session_timestamp_basis` because it never reads that key.

**The fix is not to convert at ingestion.** `broker_clock.py:80-82` is explicit that the conversion
is "for deriving session/hour-of-day semantics only, never for re-labeling the corpus's own
timestamp column," and F-066 parked the session *filter* on broker time because it was empirically
tuned there. Relabeling at ingestion would silently move a tuned trading filter.

Instead: **refuse to run on any corpus whose clock is not declared and human-reviewed.** No
conversion, no change to tuned behaviour — it turns an ambient assumption into a gated fact.

---

## Implementation status (written under the previously-approved plan)

| File | State |
|---|---|
| `src/data_ingestion/clock_registry.py` | **complete** — `ClockRecord`, SHA-pinned lookup, `require_reviewed_clock`, `require_basis_compatible` |
| `src/data_ingestion/ohlcv_schema.py` | **complete** — `ClockProvenanceError`, 3-phase docstring, `require_reviewed_clock` façade (lazy import, no cycle) |
| `configs/data_provenance/ohlcv_clock_registry.json` | **complete** — empty seed, `schema_version 1.0.0` |
| `src/data_ingestion/clock_detector.py` | **INCONSISTENT — must be finished first.** Docstring describes the corrected T1/T4; the code below still implements the defective T1 |

**No loader is wired yet**, so nothing is gated and no existing behaviour has changed.

---

## Detector defect found by running it (design correction)

The first T1 compared the modal daily-open time across DST regimes *within one file* and read a
zero step as "fixed offset". Measured:

```
data/mt5/XAUUSD_M15.csv    modal open | NY-DST on: 01:00 | off: 01:00   -> step 0
data/binance/BTCUSDT_M15.csv                     00:00 |      00:00    -> step 0
```

XAUUSD is a DST-observing broker feed, and T1 returned `LOOKS_FIXED_OFFSET_NON_UTC`. The cause is
structural, not a tuning miss: **the broker's day boundary is defined in the broker's own clock**
(01:00 server year-round — the exact invariant `broker_clock.py`'s docstring reports), so the
seasonal shift is absorbed and is invisible from the series alone. DST is only observable against
an external absolute reference.

This matters beyond the bug: a detector that emits confident wrong verdicts would corrupt the
review it exists to inform.

**Corrected test suite** (all reuse `broker_clock._ny_is_dst_on_date`):

- **T2 — reference cross-correlation.** Intraday realized-range profile vs a corpus already
  declared `UTC`; best circular shift = offset in hours. Foundational; T1 and T4 are restrictions
  of it.
- **T1 — seasonal step.** T2 over NY-DST-on vs NY-DST-off dates separately. ~1h difference ⇒
  observes DST; ~0 ⇒ fixed offset. **Requires a reference; reports `INSUFFICIENT` without one.**
- **T4 — NY vs EU calendar.** T2 restricted to the ~5 weeks/year the US and EU DST calendars
  disagree; whichever regime's offset it matches is the calendar the server follows. Small-N and
  noisy — reported as evidence, caps confidence, never decides alone.
- **T3 — daily boundary.** 00:00 open is *consistent with* UTC; 01:00 indicates a non-UTC server
  day. Cannot distinguish fixed-offset from DST-observing on its own.

**Bootstrap:** an empty registry has no declared-UTC reference. Review a Binance corpus first —
Binance klines are UTC epoch by API contract and T3 corroborates (00:00 open) — then every MT5
corpus is measurable against it.

---

## Remaining work

1. **Finish `clock_detector.py`** — replace `_t1_dst_step` with the reference-based T1, add T4,
   make `_t2_reference_xcorr` reusable over a date mask, rewrite `_verdict` so that **no reference
   ⇒ `INCONCLUSIVE`/low** rather than a fixed-offset claim. Re-run on XAUUSD + BTCUSDT and confirm
   XAUUSD reads as `LOOKS_MT5_SERVER_NY_DST` with the ~−3h/−2h seasonal split.
2. **Wire the Phase-3 gate** at file-opening readers. *Correction to the earlier plan:*
   `require_ohlcv_columns` is also called on in-memory frames (`feature_pipeline.py:462`,
   `story_builder.py:167`, `certify_xauusd_corpus.py:58`) that have no source file, so a mandatory
   `source_path` there would be wrong. Gate the **file-backed** sites instead:
   `backtest_v2.py:756` (`CandleLoader.stream`) and `:1818` · `dataset_integrity.py:538-548` ·
   `historical_fetcher.py:511` · `sl_tp_comparator.py:493` · `timing_reconstructor.py:189`.
   Pass the resolved basis on the spine path so the double-conversion guard runs.
3. **Review CLI** `scripts/governance/review_ohlcv_clocks.py` — `--scan` / `--list --unreviewed` /
   `--review <path>` / `--reference <path>` (bootstrap). SITS-register the same turn:
   `script_census.py --write-stubs` → `seed_script_registry.py` → `generate_script_matrix.py`.
4. **Tests** `tests/test_ohlcv_clock_provenance.py` — no record raises · SHA drift raises ·
   reviewed+match passes · `UTC` corpus under `utc_corrected` raises · `user_reviewed:true` without
   `reviewed_by` raises · detector deterministic · detector returns `INCONCLUSIVE` with no
   reference (the regression for the defect above) · a mechanical test asserting every file-backed
   OHLCV reader is gated, so a new reader cannot skip Phase 3.
5. **Byte-identity verification** — the gate admits or refuses, it never alters values:
   XAUUSD vector SHA / `SCHEMA_HASH` / `FEATURE_ORDER_HASH` / backtest ledger unchanged, and
   re-running `crt_episode_number_trace.py` reproduces run `20260813T124158Z` byte-for-byte.
6. **Report + log** — write the six-section mining report + A3 mechanism trace to
   `results/crt_episode_trace/20260813T124158Z/trade_mining_report.md`, including the three items
   the source trace closed (`score_override` is the soft-conf score set at `:3094` *before* the
   session filter and returned by `RiskScore.final:199-200` · `decay_factor` is equal because
   `candles_elapsed = 73−72 = 387−386 = 1`, bars-since-RETEST not bars-since-shadow-sweep ·
   `EXECUTION` precedes `build_trade`, `:3152` then `:3153`). Append the SESSION LOG entry to
   `assistant_project.md` (CLAUDE.md §6).

## Out of scope

- No timestamp conversion or relabeling at ingestion (`broker_clock.py:80-82`).
- No change to `crt_engine.session_windows` or to surface #1's broker-time basis. Making
  `score_time` read the basis is a separate authorized change; this work only makes its input clock
  a declared fact.
- No `F-0NN` registered — a finding is earned after shipping and measurement, not from design.

## Day-one cost (accepted)

Scope is every OHLCV read, fail-closed with no env escape hatch, so reads halt until the queue is
cleared. 258 candidate files exist under `data/`, most of them derived intermediates; `--scan`
reports which are actually reachable through the gate so the real review set is one sitting.
