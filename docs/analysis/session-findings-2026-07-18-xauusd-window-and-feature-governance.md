# Session Findings — 2026-07-18 — XAUUSD window export + feature-pipeline governance

Point-in-time record per CLAUDE.md Section 6.2 rule 5 (`docs/analysis/` = non-living,
session-scoped). Session-local IDs (`SF-00N`), not `F-0NN` — an `F-` id must appear in both
`docs/current-findings.md` and the CLAUDE.md Repository Truths Index
(`tests/test_current_findings.py` enforces bidirectional correspondence), so minting one here
would break that floor. Any entry below may be promoted to a real `F-` id later by a separate,
deliberate action.

| ID | Type | Conclusion | Confidence |
|---|---|---|---|
| SF-001 | ARCH | XAUUSD corpus guard is extension-blind and instrument-branch based, silently substituting a 12x larger dataset for any filename it matches | Certain |
| SF-002 | ARCH | `.xlsx` files under `data/` fail with an obscure `UnicodeDecodeError` rather than a clear format error; three independent readers involved | Certain |
| SF-003 | GOV | Stale duplicate-corpus claim in SECONDLOW policy doc; two research scripts bypass the XAUUSD guard directly | Likely |
| SF-004 | ARCH | A single-instrument backtest reads its input CSV four separate times (preflight, feature build, count, stream); one pass (`count()`) is pure waste | Certain |
| SF-005 | ARCH | `market_ontology.yaml` `rolling_indicators.lookback` was decorative-only prior to this session — no code path consumed it | Certain (superseded by this session's work for the 4 entries listed in SF-007) |
| SF-006 | ARCH | `finalize()`'s survivorship guard is advisory-only (logs, never raises) and its threshold formula contradicts its own comment (ratio-dominant above ~15k rows, backwards vs. the stated "absolute budget" intent) | Certain |
| SF-007 | ARCH | Feature-pipeline indicator periods migrated from Python literals to config-driven, under a scoped CLAUDE.md Section 6.5 exception | Certain |

---

## SF-001 — XAUUSD corpus guard: extension-blind, instrument-branch substitution

**Evidence:** `is_xauusd_m15_request` (`src/data_ingestion/xauusd_phase1_candidate.py:200-215`)
matches on (a) filename prefix `XAUUSD_M15` with **no extension check**, and (b)
`instrument=="XAUUSD"` AND `"M15"` anywhere in the filename. Either match triggers
`guard_xauusd_csv_path` to silently rewrite the request to the frozen 47,275-row corpus
(`data/mt5/XAUUSD_M15.csv`, sha `4d73f5ce...`), announced only via an `INFO` log line. Verified:
a file named `XAUUSD_M15_2026-03-23_to_2026-05-21.xlsx` resolves to `data/mt5/XAUUSD_M15.csv`
via this guard — the requested 2-month/3,949-row file is discarded, the caller gets the full
2-year/47,275-row corpus instead, with no error and no return-value signal.

**This session's export deliberately uses a guard-invisible filename** so the divergence from
the canonical corpus is **declared, not silent** — the CORPUS_AUTHORITY.md G-10 rule ("declared
synthesis is admissible, undeclared is the defect") is satisfied via: parent corpus sha
`4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56`, exact row range
2026-03-23T01:00 to 2026-05-21T23:45, 3,949 source rows, produced by
`scripts/analysis/export_xauusd_window.py`.

**Status:** logged per user instruction. Not fixed this session.

## SF-002 — `.xlsx` files under `data/` fail obscurely

Three independent readers on the `backtest_v2` path are all `open(..., encoding="utf-8-sig")` +
stdlib `csv` or `pd.read_csv` — none dispatch on file suffix. `data/` already contains real
`.xlsx` files (`BNBUSDT_M15_2year.xlsx`, `BTCUSDT_M15_2year.xlsx`, `AUDUSD_M15_1year.xlsx`).
Passing one produces a `UnicodeDecodeError` on the ZIP container bytes rather than a clear
"unsupported format" message. Deferred to a future phase (see
`docs/implementation_plan/from-claude-md-pick-curried-toast.md` FP-1) — real scope is **four**
reader passes per backtest run, not three (preflight/L2 gate, `pd.read_csv` for
`FeaturePipeline`, `count()`, `stream()`), two of which cannot be merged (whole-frame
vectorization vs. sequential no-lookahead).

## SF-003 — carried-over drift, not yet synchronized

- `H-SECONDLOW-002_Complete_Package/SECONDLOW_RESEARCH_DATA_POLICY.md:61-62` claims
  `data/XAUUSD_M15.csv` is a byte-identical `4d73f5ce` duplicate of the canonical corpus — false
  on disk (`486cf361...`, 50,169 rows vs. 47,275, +2,894 later bars).
- `scripts/research/_enrich_xauusd_corpus.py:35` and `scripts/research/trace_zone_gate_xauusd.py:50`
  `pd.read_csv` the extended root twin directly, bypassing `guard_xauusd_csv_path` entirely.

## SF-004 — redundant reads on the backtest ingestion path

A single-instrument `backtest_v2` run reads its input file **four** times: `_preflight_dataset`
(L2 gate, stdlib `csv`), `BacktestRunner.__init__` (`pd.read_csv`, whole-frame for
`FeaturePipeline`), `CandleLoader.count()` (line-count scan, purely for a progress-bar total),
`CandleLoader.stream()` (sequential candle loop). The first two are separately justified by
different contracts (whole-sequence validation vs. vectorized feature computation) and cannot
be merged with the sequential stream (no-lookahead guarantee). `count()` has no such
justification — `stream()` already knows its own row count on completion. All four passes also
independently re-invoke `guard_xauusd_csv_path` for XAUUSD, each re-hashing the full 47,275-row
corpus. Deferred (FP-2) — touches the hot path, needs a parity proof before any change.

## SF-005 — ontology `lookback` field was decorative-only

Prior to this session, `market_ontology.yaml` `rolling_indicators.*.lookback` (e.g.
`rsi_14.lookback: 14`) documented the period in prose but no code path read it — every actual
period was an independent Python literal in `feature_pipeline.py`. Confirmed via grep: zero call
sites consumed `spec["lookback"]`. Superseded for 4 of 7 `rolling_indicators` entries by SF-007
below (`config_key` now names the live source); the other 3 (`true_range`, `swing_high`,
`swing_low`) remain decorative — their periods are outside this session's Section 6.5 exception
scope (swing window is item 7/PARKED; `true_range` has no independent period, it derives from
`atr`'s).

## SF-006 — `finalize()` survivorship guard is advisory-only, and its formula is backwards

**Evidence** (`src/features/feature_pipeline.py`, `finalize()`): the guard
(`_allowed_drop = max(300, int(n_before * 0.02))`) only `_fp_log.error(...)` on breach — it
never raises, so a truncated feature frame silently proceeds through the rest of the pipeline
and into every downstream consumer (backtest, training, research).

**On XAUUSD specifically:** warmup is **78 rows and dataset-size-independent** — verified
identical (78) at 3,949 / 47,275 / 50,169 input rows. It is structural, not proportional:
`ma_20`(20) -> `.diff()`(1) -> `.rolling(10)`(10) -> `.rolling(50)` z-score(50) => first valid
canonical row is index 78 (driven by `trend_strength`, last-NaN at row 77) and `macd_hist`
(similar stacking, last-NaN at row 48). The guard has **never fired** for XAUUSD at any tested
size (allowed 300-1,003 vs. actual 78).

**Design defect, independent of XAUUSD:** the threshold formula contradicts its own code
comment. The comment states "absolute budget, not survival ratio — ratio permits ~5k silent
loss on 100k datasets," but the implementation is `max(300, 2%)`, which is **ratio-dominant**
for any file over 15,000 rows — on a 100k-row file it permits 2,000 dropped rows, precisely the
failure mode the comment says it exists to prevent. Because real canonical warmup is constant
(78 rows, verified above), the guard becomes *more* permissive as input size grows, which is
backwards relative to its stated intent.

**Correction of two claims made earlier in this same session (E-001):** an unverified
extrapolation from the code's own "warm-up budget ~300 rows" comment was quoted as "254 rows
dropped, 6.4%" for the 2-month XAUUSD export, and it was separately claimed this "slipped
through" the guard. Both were wrong: the real drop is 78 rows / 1.98%, and at
`allowed=max(300,2%)=300` for a 3,949-row file, the guard was never triggered — nothing slipped
through anything. The underlying design defect above is real and independent of this correction.

**`ma_200` — removed 2026-07-18, RESTORED 2026-07-19 by explicit user decision.** The column
feeds **zero** downstream consumers (not canonical, not read by any other `compute_*` method;
confirmed via full-repo grep and empirically). It was removed as dead code on 2026-07-18, then
restored on 2026-07-19 at user instruction to keep the 200-MA available for future features.
Now config-driven as `feature_pipeline.ma_periods[2]`.

**Important correction to the stated rationale (E-001):** restoring `ma_200` does **not** change
the warmup, and the original `_warmup_budget = 300` comment's arithmetic
(`ma_200(200) + z-score(50) + swing edges(4) ~= 300`) was **never load-bearing** — `ma_200` is not
in `CANONICAL_FEATURES`, so its 199-row NaN tail never reached `finalize()`'s
`dropna(subset=CANONICAL_FEATURES)`. Measured canonical warmup is **78 rows both with and
without** `ma_200` present (verified on the 3,949-row export: 3,949 -> 3,871, drop 78, in both
states; 38-dim vector shape and NaN-freedom identical). So the budget was over-sized relative to
reality the whole time, independent of this removal/restore cycle. Both the removal and the
restore are hash-neutral with respect to the canonical feature vector.

**Deferred (not this session, per user instruction):** (a) raise instead of log; (b) replace
`max(300, 2%)` with a fixed structural budget, since the real warmup is provable and constant;
(c) optionally split reported drop into head-warmup (expected) vs. mid-series (always a defect)
for a more actionable message.

**Unverified side-observation, explicitly not a basis for action:** a scan of the other 11
instruments in `data/` found `DOGEUSDT_M15.csv` losing 40,230/70,080 rows (57.5%) and
`XRPUSDT_M15.csv` losing 5,126/70,080 rows (7.4%) to mid-series (not head-warmup) NaN, traced to
`atr==0` from 2-decimal-place price precision (`high==low` on 87.7% of DOGE bars). The user
states this data may be stale; this is recorded as an observation pending a data-freshness
check, not as evidence about the current corpus, and no other instrument outside XAUUSD is in
scope for this session's work.

## SF-007 — feature-pipeline indicator periods: config migration, parity-proven

Implemented this session under the CLAUDE.md Section 6.5 scoped exception (see CLAUDE.md
Section 6.5, dated 2026-07-18, immediately following the STRUCTURAL/BEHAVIORAL/GOAL-SEEKING
table). Full detail in `CLAUDE.md`; summary:

- **New config section** `configs/production/v2_multi_2026_04.json` -> `feature_pipeline`:
  `rsi_period`, `atr_period`, `ma_periods`, `bb_period`/`bb_std`, `macd_fast`/`macd_slow`/
  `macd_signal`, `trend_strength_window`, `ema_fast_span`, `ema_slow_span` — values set equal to
  the prior hardcoded literals byte-for-byte.
- **`FeaturePipeline.__init__`** gained an *optional* `cfg: Optional[dict] = None` parameter
  (not required — blast radius of a required param was measured at 97 construction sites: 9
  `src/`, 38 `scripts/`, 50 `tests/`). `cfg=None` resolves from the active production config via
  a function-local import of `get_prod_section` (established repo convention, avoids a
  module-level `features <-> config_layer` import cycle risk). Resolution is strict — a missing
  section or key raises `KeyError`, never falls back to the old literal.
  `configs/production/v2_multi_2026_04.json:crt_engine.ema_fast/ema_slow` (2/5, a genuinely
  different EMA pair for soft-confirmation logic) is annotated with a disambiguating
  `_comment_ema` rather than renamed, to avoid touching a live-consumed key outside this
  exception's scope.
- **`market_ontology.yaml`** `rolling_indicators` entries `rsi_14`/`atr`/`ema_fast`/`ema_slow`
  (FM-042/041/043/044) gained a `config_key` field naming the live config source.
- **Parity proof:** the config-resolved path and an explicit `cfg` dict holding the exact prior
  literals produce byte-identical 38-dim vectors on the full XAUUSD corpus (47,197 rows
  post-warmup, shape `(47197, 38)`). Separately verified the wiring is genuinely live (not
  coincidental): changing `rsi_period` 14->21 and `ema_fast_span` 9->5 changes the output
  vector. Full `pytest` regression run — see session log for pass/fail summary.
- **Explicitly out of scope of this exception** (per the CLAUDE.md wording): the geometric
  primitives `body_size`/`wick_size`/`body_ratio`/`candle_body`/`upper_wick`/`lower_wick` remain
  STRUCTURAL/immutable — `body_ratio = body/range` has no period to parametrize, and
  `candle_math.py`'s own docstring frames these as fixed mathematical identities, not tunable
  formulas.

## Also noted, out of scope, not touched this session

A pre-existing, unrelated encoding defect was found while verifying this session's own JSON
edits did not introduce mojibake: `configs/production/v2_multi_2026_04.json:207`
(`_known_gaps_doc`) already contains a literal U+FFFD replacement character mid-sentence
("...NOT full-day closures [U+FFFD] so the good bars..."), predating this session (confirmed via
`git diff` — not part of any change made here). Not fixed; flagged for a future documentation
pass since it's inside a config comment field, not load-bearing data.
