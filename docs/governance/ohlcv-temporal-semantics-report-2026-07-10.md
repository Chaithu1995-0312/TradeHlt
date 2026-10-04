# OHLCV Temporal Semantics Report — PHASE 1 (OHLCV Truth Closure) PASS A

| Field | Value |
|---|---|
| Program | Layer-by-layer repository audit (bottom-up) |
| Phase | 1 of 16 — OHLCV Truth |
| Pass | A (Evidence Freeze) |
| Generated (UTC) | 2026-07-10T13:09:06Z |
| Pinned commit | `b48d4d9a7abfb429f2a17c790d4b32083da5dd92` (worktree DIRTY) |
| Branch | `feature/truth-registry-v2` |
| Verdict | (none — PASS A emits evidence only) |

**Evidence-type discipline (correction C3).** Every claim carries one tag:
- `EXECUTABLE` — proven by running code in this pass (census run, boundary probe)
- `STATIC` — proven by cited source lines whose behavior is unconditional
- `REPRODUCIBLE` — proven by a stated command anyone can re-run
- `NARRATIVE-ONLY` — rests on external API convention, comments, or docs.
  **NARRATIVE-ONLY claims are flagged as UNPROVEN for PASS-B contract purposes.**

---

## T-SEM-1 — Timestamp representation (all on-disk corpora)

| Claim | Evidence | Tag |
|---|---|---|
| Every scanned OHLCV file stores timestamps as tz-NAIVE strings; the dominant format is `%Y-%m-%d %H:%M:%S` | census `timestamp_formats` per artifact — 100% "canonical" format across all OHLCV-schema files; no offset suffix anywhere | `EXECUTABLE` |
| The runtime accepts 8 formats (`OHLCV_DATE_FORMATS`) and RAISES on anything else | `src/data_ingestion/ohlcv_schema.py:70-87` | `STATIC` |
| Parsed timestamps are naive `datetime`s; **"UTC" is an ASSUMPTION encoded in one comment** ("parsed CSV timestamps are tz-naive, assumed UTC") | `src/data_ingestion/dataset_integrity.py:64-66` (`_utcnow_naive`) | `STATIC` (that the code assumes UTC) — the assumption's TRUTH is per-family, below |

## T-SEM-2 — Timezone truth per acquisition family

| Family | Claim | Evidence | Tag |
|---|---|---|---|
| `mt5` | Wall time IS UTC: bar epoch → `fromtimestamp(..., tz=timezone.utc)` → strftime; no broker-timezone leak in code | `src/inout/mt5_candle_fetcher.py:186` | `STATIC` |
| `mt5` | The bar epoch `r["time"]` itself is UTC-based | MetaTrader5 API convention (bar open time as Unix epoch) | `NARRATIVE-ONLY` → UNPROVEN |
| `binance` | Wall time IS UTC: `fromtimestamp(row[0]/1000, tz=timezone.utc)` | `scripts/data/fetch_and_verify_binance.py:96` | `STATIC` |
| `yfinance` | Timezone of fetched frames | no normalization code found in `fetch_forex_yfinance.py`; yfinance intraday returns exchange-tz-aware indexes by library convention | `NARRATIVE-ONLY` → UNPROVEN |
| `data_root` FX majors | UTC by descent — byte-identical to `mt5/` twins | census DUP-001/006/009/019/027 + DUP-008 | `EXECUTABLE` (hash) chained on the mt5 `STATIC` row |
| `data_root` crypto (BTC/ETH/XRP/DOGE) | tz truth inherits the yfinance family's UNPROVEN status (byte-identical twins) | census DUP-010/024/026/029 | `EXECUTABLE` (hash) chained on UNPROVEN |
| `resampled` | Same tz as input (pure function of input timestamps) | `src/research/resample.py:60-70` (floor arithmetic only) | `STATIC` |

## T-SEM-3 — Open-time vs close-time labeling

| Path | Claim | Evidence | Tag |
|---|---|---|---|
| `research.resample` output (`data/resampled/`) | OPEN-time labeled: emitted candle's `timestamp = bucket start` | `src/research/resample.py:95` (`timestamp=start`) | `STATIC` |
| `convert_binance_m1_to_m15.py` output | OPEN-time labeled: source field literally `open_time`; pandas `resample("15min")` defaults `label="left", closed="left"` | `scripts/data/convert_binance_m1_to_m15.py:15,22` | `STATIC` (field name + pandas default) |
| `binance` family | OPEN-time: ccxt unified OHLCV `row[0]` is the candle open time | ccxt API convention | `NARRATIVE-ONLY` → UNPROVEN |
| `mt5` family | OPEN-time: MT5 `rates["time"]` is the bar open time | MetaTrader5 API convention (mirrored by module docstring `mt5_candle_fetcher.py:8`) | `NARRATIVE-ONLY` → UNPROVEN |
| `yfinance` family | labeling convention | none found in repo | UNKNOWN |
| Cross-check (all families) | first/last timestamps and modal deltas are internally consistent with a uniform grid labeling; census shows no half-bar phase offsets between byte-identical twins | census | `EXECUTABLE` (consistency only — cannot distinguish open vs close labeling by itself) |

**Consequence:** the repository-wide "timestamp = bar open time, interval
`[t, t+Δ)`" convention is PROVEN only for resampler-produced artifacts and the
historic converter; for acquisition families it currently rests on external API
conventions. This feeds PASS-B as an UNPROVEN handoff guarantee (blocker
candidate BC-2).

## T-SEM-4 — Observability (when a row becomes PIT-available)

| Path | Rule | Evidence | Tag |
|---|---|---|---|
| `CandleLoader.stream` consumers (backtest/research) | A yielded row is treated as a COMPLETED bar; consumers advance strictly row-by-row; no forward index access in the loader | `backtest_v2.py:704-769` (sequential generator) | `STATIC` (loader). Whole-pipeline no-lookahead is the L1/L2/L3+generator conjunction (F-039 scope) — NOT re-proven here |
| `research.resample` | An HTF bucket becomes observable only when the FIRST child of the NEXT bucket exists; trailing partial bucket never observable | `resample.py:15-27,126-135` | `STATIC` |
| `HTFBuilder` (spine) | HTF window becomes observable when the Nth buffered candle arrives (count-based) | `backtest_v2.py:797-805` | `STATIC` |
| `validate_dataset` future gate | No bar may be LABELED after `now + 0 min` (`future_ts_tolerance_minutes: 0` active config) | `dataset_integrity.py:322-323,353-359`; config `v2_multi_2026_04.json` | `STATIC` |
| Acquisition-time incomplete-bar exposure | Whether a fetch can capture the currently-FORMING bar (open-time label ≤ now passes the future gate while the bar is still mutating) | fetch window ends are user-supplied dates (`fetch_and_verify_*.py`); range filter `row[0] < end_ms` excludes it only when `end` is in the past; no explicit completed-bar check found | UNKNOWN → matrix seed SEED-OHLCV-08 |

## T-SEM-5 — Interval / grid / session semantics

| Claim | Evidence | Tag |
|---|---|---|
| Modal inter-bar delta must equal the nominal timeframe (M15=900s etc.) — enforced at the L2/L3 gate | `dataset_integrity.py:378-386`; census `modal_delta_seconds` == nominal for every canonical-pattern OHLCV artifact | `STATIC` + `EXECUTABLE` |
| Gap math counts only TRADABLE slots: crypto 24×7; FX Sun 22:00 → Fri 21:00 GMT (or the autoderived weekly mask), reviewed holidays/known-gaps excluded | `dataset_integrity.py:106-122,150-185,389-395`; `session_autoderive.py:35,60` | `STATIC` |
| Census gap counts are session-BLIND raw deltas (weekend closes appear as gaps; expected) | census scope note | `EXECUTABLE` (by construction) |
| No DST handling exists anywhere in the OHLCV layer (all arithmetic on naive UTC-assumed datetimes) | grep: no `pytz/zoneinfo/dst` in `src/data_ingestion/`, `src/inout/mt5_candle_fetcher.py`, `src/research/resample.py` | `REPRODUCIBLE` (`grep -rn "pytz\|zoneinfo\|dst" src/data_ingestion src/inout/mt5_candle_fetcher.py src/research/resample.py`) |

## T-SEM-6 — Joins / alignment / slicing

| Path | Semantics | Evidence | Tag |
|---|---|---|---|
| `research/cross_sectional.py` panel | streams per-symbol candles onto a shared M15 grid (inner-join semantics; non-OHLCV perp series joined downstream) | `cross_sectional.py:118` + module design | `STATIC` (load), join detail deferred to its own layer phase |
| `mtf_conjunction` | HTF context = `resample(trailing M15 window)` — CLOSED buckets only | `research/candle_state/mtf_conjunction.py:63,117` | `STATIC` |
| No asof/nearest-tolerance joins on OHLCV found in `src/` | mutation-verb + `merge_asof` grep: 0 hits | `REPRODUCIBLE` (`grep -rn "merge_asof" src/`) |

## T-SEM-7 — Boundary worked examples

1. **M15 grid, open-time convention (as encoded by T-004/T-007):** a row
   `2026-01-05 09:15:00` covers `[09:15:00, 09:30:00)`; the NEXT row on an
   ungapped grid is `09:30:00`; census modal delta 900s confirms grid spacing
   for every M15 artifact (`EXECUTABLE`).
2. **H4 calendar bucket (T-004):** children `08:00,08:15,…,11:45` aggregate to
   the H4 candle labeled `08:00`; it is EMITTED only when the `12:00` child
   arrives (`resample.py:126-128`). If the day ends at `11:45` (no `12:00` bar
   ever arrives before EOF), the `08:00` bucket is DROPPED (`:133-135`) —
   conservative, never leaky (`STATIC`).
3. **Weekend (FX):** last Friday bar `20:45` (covers to 21:00 GMT close);
   next bar Monday/Sunday session open. `dataset_integrity` counts the closed
   span as NON-tradable (no gap flagged); the census counts it as one raw
   gap event (session-blind) — both behaviors observed and consistent
   (`EXECUTABLE` for census, `STATIC` for the gate).
4. **Count-based HTF divergence (T-005):** after a weekend, `HTFBuilder` with
   `candles_per_htf=16` builds its next "H4" window from the last 16 candles
   REGARDLESS of calendar phase, while T-004's next H4 bucket snaps to
   00/04/08…; the two paths label different aggregates as "the H4 context"
   from the first post-gap bar onward (`STATIC`, both code paths cited above).

## Evidence gaps rolled up (feed PASS-B / contradiction report)

1. Open-time labeling UNPROVEN for `mt5`/`binance`/`yfinance` acquisition
   families (NARRATIVE-ONLY).
2. Timezone truth UNPROVEN for `yfinance` (and by descent, root crypto majors).
3. Acquisition-time incomplete-bar protection UNKNOWN (T-SEM-4 last row).
4. yfinance labeling convention UNKNOWN entirely.

## What this report did NOT do

No closure adjudication; no remediation; no new probes beyond the census run;
no economic claims; no re-proof of the pipeline-wide no-lookahead conjunction.

```text
OHLCV_TEMPORAL_CLAIMS_STATIC_OR_EXECUTABLE = 19
OHLCV_TEMPORAL_CLAIMS_NARRATIVE_ONLY = 4
OHLCV_TEMPORAL_CLAIMS_UNKNOWN = 3
OHLCV_TEMPORAL_STATUS = EVIDENCE_FROZEN
```
