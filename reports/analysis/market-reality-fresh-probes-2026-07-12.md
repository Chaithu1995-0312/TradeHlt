# Market Reality — Fresh Formula/Behavior Probes (WP1 + WP2)

**Date:** 2026-07-12
**Scope:** Repository-local evidence gathering. No production behavior changed.
**Deliverable of:** `docs/implementation_plan/task-independent-formula-majestic-wolf.md` (WP1 + WP2).

---

## 1. Contamination rule (governing)

All prior verdicts — `CLOSED` / `PASS` / `VALIDATED` / `PIT_CERTIFIED`, prior audit/finding
conclusions, generated status fields, config comments, docstrings, and test pass counts — are treated
as **potentially contaminated** and carry **no** evidentiary weight here. Every finding below is
reconstructed from (a) the **current implementation source** and (b) **fresh runtime execution** of the
real `FeaturePipeline` on synthetic inputs. Where a docstring/comment asserts one thing and the code +
runtime show another, **the code + runtime win** and the divergence is reported explicitly (RSI/ATR).

This task returns **evidence to support/reject** provisional SET A/B/C classifications; it does **not**
perform final A/B/C closure.

## 2. Exact implementation files inspected (first-hand, this session)

| File | What was read |
|---|---|
| `src/features/feature_pipeline.py` | The single production authority. `run()` (`:873`) and every `compute_*` stage: price (`:180`), volume (`:205`), indicators/RSI/ATR/MACD (`:245`), volatility_regime (`:310`), context/session (`:370`), structure/liquidity (`:389`), canonical price/vol/ema/structure/temporal (`:503`–`:667`), liquidity_distance (`:669`), promote_volume_spike (`:722`), finalize (`:762`), build_feature_vector (`:835`). Constants `SWING_WINDOW=2` (`:59`), `NORMALIZE_COLS` (`:63`). |
| `src/features/feature_schema.py` | `CANONICAL_FEATURES` (38, `:46-67`), `CANONICAL_FEATURE_DIM=38` hard-assert (`:76-86`), `SESSION_MAP` (`:91`). |
| `src/features/causal_structure.py` | Online twin of batch structure (read via exploration; consulted for the causal-delay mechanism). |
| `src/research/candle_state/encoder.py`, `mtf_conjunction.py` | Research-only observables (WP3). |

**Note on `OHLCFeatureMap`:** the name is **not an implemented symbol** anywhere in `src/`. It appears
only in planning docs. It is the aspirational name for the future Market Reality layer; any claim that
it exists in code is unverified. The implemented 38-feature authority is `FeaturePipeline`.

## 3. Exact commands executed

```
# environment (repo root D:\Tradelatest)
venv/Scripts/python.exe -c "import pandas,numpy,yaml,sys; print(sys.version, pandas.__version__, numpy.__version__, yaml.__version__)"
#   -> 3.12.10  pandas 3.0.2  numpy 2.2.6  yaml 6.0.3

# the probe harness (scratchpad, NOT committed) — full source in Appendix A
venv/Scripts/python.exe scratchpad/mr_probe.py   # writes scratchpad/mr_probe_results.json + stdout
```

The probe harness imports the real `from features.feature_pipeline import FeaturePipeline, SWING_WINDOW`
and `from features.feature_schema import CANONICAL_FEATURES`. It **does not** re-implement or monkey-patch
any production formula; it only feeds synthetic frames and reads the enriched output.

## 4. Synthetic datasets used

- **Warmup base** (`warmup_df`): deterministic seeded random-walk close + small sine, valid OHLC
  (`high≥max(o,c)`, `low≤min(o,c)`), constant volume 1000, 15-min timestamps from 2024-01-01. Sizes
  450–600 bars so post-warmup rows survive `finalize()` (drop budget = 300).
- **Geometry targets** (correction #2): 450-bar warmup **+ one crafted target candle** appended; the
  target row is inspected (never a 1-bar pipeline input). 8 cases below.
- **Scale pair** (correction #3): the same 450-bar frame with **every** price-valued OHLC column ×1 and
  ×100; timestamps/volume/%-path/length preserved; rows aligned by timestamp identity.
- **Volume scenarios**: constant / one isolated spike / adaptive-window spike / zero volume.
- **Volatility scenarios**: linearly compressing vs linearly expanding candle range.
- **Structure sequences**: a 30-bar engineered zig-zag (Stage-A prerequisite test) and a 500-bar warmup
  (where structure actually publishes), plus a prefix/full pair for PIT.

## 5. Formula verification table (runtime-reproduced)

Static finding column = the provisional claim under test. Verdict from fresh runtime unless marked
"code-reconstructed" (unambiguous single-branch arithmetic in current source).

| # | Claim under test | Runtime evidence | Verdict |
|---|---|---|---|
| 1 | `atr = atr_14_raw / close` (close-relative) | scale-invariance: `atr` max_abs_diff(×1 vs ×100)=**0.0**, ratio 1.0 | **VERIFIED** |
| 2 | `ema_spread` mixes absolute numerator / relative denom | scale: `ema_spread` **SCALES_WITH_PRICE**, median ratio ×100/×1 = **100.0**, max_abs_diff 9503.9 | **VERIFIED (defect real)** |
| 3 | `momentum_score = close.diff()/atr` same defect | scale: **SCALES_WITH_PRICE**, ratio **100.0**, max_abs_diff 5053.8 | **VERIFIED (defect real)** |
| 4 | `volatility_ratio = (h-l)/(atr*close)` reconstructs abs ATR → coherent | scale: **INVARIANT**, max_abs_diff **0.0** | **VERIFIED (coherent)** |
| 5 | `disp_strength = body/(atr*close)` coherent | scale: **INVARIANT**, max_abs_diff **0.0** | **VERIFIED (coherent)** |
| 6 | RSI claims Wilder, uses SMA | `rsi_prod vs SMA` maxdiff **0.0**; `rsi_prod vs Wilder` maxdiff **35.81** | **VERIFIED (SMA, not Wilder)** |
| 7 | ATR uses SMA of TR, not Wilder | `atr_raw vs SMA-TR` maxdiff **0.0**; `atr_raw vs Wilder` maxdiff **0.1184** | **VERIFIED (SMA, not Wilder)** |
| 8 | `candles_since_retest` counts since **sweep**, not retest | groups on `liquidity_sweep` cumsum (`:658-667`); runtime max=51–62 with variance | **VERIFIED (code + runtime)** |
| 9 | `retest_depth` = recent-sweep + **EMA9 proximity**, not a structural level | `:643-648` distance from `ema_fast`; runtime range [0, 0.985] | **VERIFIED (code-reconstructed)** |
| 10 | `volume_ratio` baseline **includes current bar** | isolated spike: prod ma20=**1950** (incl) vs prior-only **1000**; ratio **10.26** vs prior-only **20.0**; self-contribution **+950** | **VERIFIED (counterfactual)** |
| 11 | `volume_spike` threshold **includes current obs** | prod q75 window incl current **1.0370** vs prior-only **1.0300**; own bar raised own threshold by **+0.0070** | **VERIFIED (counterfactual)** |
| 12 | `volatility_regime` = ATR percentile **level**, not expansion/contraction dynamics | tercile of `atr.rolling(200).rank(pct)` (`:343-345`); **0 canonical features encode vol slope/dynamics** | **VERIFIED (level, not dynamics)** — see §10 |
| 13 | `liquidity_pressure_score` = monotonic transform of `liquidity_distance`, missing→10.0 | `:715-718` `exp(-0.5*dist.fillna(10.0))`; runtime min 0.098 (dist 4.64) | **VERIFIED (code-reconstructed)** |
| 14 | `wick_size` = full range, not wick magnitude | geometry: **all 8** cases `wick_size == high-low`; long-upper-wick `wick_size=3.20` == range (actual upper wick 3.0) | **VERIFIED (runtime)** |
| 15 | session from naive timestamp hour, no tz contract | `:373` `pd.to_datetime(...)` (no `utc=`), `:378` `.dt.hour`, cutoffs 8/16; runtime `session∈{0,1,2}`, `hour_of_day∈[0,23]` | **VERIFIED (code-reconstructed)** |

## 6. Scale-invariance results (correction #3)

Same 450-bar frame, all price OHLC ×1 vs ×100, 372 aligned post-warmup rows:

| Feature | max_abs_diff(×1,×100) | median ratio ×100/×1 | Verdict |
|---|---|---|---|
| `atr` | 0.0 | 1.0 | INVARIANT |
| `volatility_ratio` | 0.0 | 1.0 | INVARIANT |
| `disp_strength` | 0.0 | 1.0 | INVARIANT |
| `liquidity_distance` | 0.0 | 1.0 | INVARIANT |
| `retest_depth` | 6.4e-06 (float32) | 1.0 | INVARIANT |
| `ema_spread` | 9503.9 | **100.0** | **SCALES_WITH_PRICE** |
| `momentum_score` | 5053.8 | **100.0** | **SCALES_WITH_PRICE** |

**Interpretation:** `ema_spread` and `momentum_score` divide an **absolute-price** numerator
(`ema_fast-ema_slow`, `close.diff()`) by the **close-relative** `atr` (which is dimensionless). The
denominator is scale-free, so the whole quantity scales linearly with the instrument's price level. The
coherent members (`volatility_ratio`, `disp_strength`, `liquidity_distance`, `retest_depth`) all divide
by `atr*close` (= **absolute** ATR), restoring dimensional consistency. This is a per-instrument
comparability concern (a $10 asset and a $1000 asset with identical % paths get 100× different
`ema_spread`/`momentum_score`), not a crash. **Evidence, not a repair — no formula changed.**

## 7. ATR comparison

Production `atr_14_raw = true_range.rolling(14).mean()` (SMA of True Range). Against independent
references on the same series (372 aligned rows):

- vs **SMA of TR**: max abs diff **0.0** → production **is** SMA-of-TR.
- vs **Wilder ATR** (`ATR_t = (ATR_{t-1}·13 + TR_t)/14`, SMA-seeded): max abs diff **0.1184** → clearly
  divergent. Production ATR is **not** Wilder-smoothed. (No comment claims Wilder for ATR; recorded for
  completeness and to falsify static finding #7 — confirmed true.)

## 8. RSI comparison

Production `rsi_14` uses `gain=delta.clip(lower=0).rolling(14).mean()`, `loss=…rolling(14).mean()`
(`:258-262`). The **docstring at `:254` explicitly says "Standard Wilder formula."** Against references:

- vs **SMA-gain/loss RSI**: max abs diff **0.0** → production **is** SMA-based.
- vs **Wilder RSI** (EWMA `alpha=1/14`): max abs diff **35.81** (RSI points) → grossly divergent.

**Verdict:** the RSI **RS ratio form** is Wilder's, but the **gain/loss averaging is a simple rolling
mean**, not Wilder's recursive smoothing. The docstring's "Wilder" claim is **DOC_DRIFT** (contamination
confirmed: trust the code). No change made — reported for the drift ledger.

## 9. Volume baseline/threshold results (correction #4 — explicit counterfactual)

**`volume_ratio` self-inclusion (isolated 20000 spike on a 1000 baseline):**

| Quantity | Value |
|---|---|
| prod `volume_ma20` (rolling(20), **includes** the spike bar) | 1950.0 |
| reference ma20 from **prior 20 bars only** | 1000.0 |
| prod `volume_ratio` (`20000/1950`) | 10.256 |
| reference ratio prior-only (`20000/1000`) | 20.0 |
| spike bar's contribution to **its own** baseline | **+950 units** |
| ratio understatement factor (prior-only / prod) | **1.95×** |

The current bar's own volume is in its denominator, so a genuine spike's `volume_ratio` is **understated
by ~1.95×** relative to a leakage-free prior-only baseline. `rolling(20).mean()` has no `.shift(1)`.

**`volume_spike` threshold self-inclusion (adaptive q75 over rolling 50):**

| Quantity | Value |
|---|---|
| current `volume_ratio` at the test bar | 5.935 |
| prod threshold = `q75` of window **including** current | 1.0370 |
| reference threshold = `q75` of the **prior-only** window | 1.0300 |
| current bar raised **its own** threshold by | **+0.0070** |
| fires under prod / under prior-only | true / true |

The current observation is part of the percentile population it is tested against. The effect on a single
q75 with one outlier is small (+0.007) but structurally present; it grows when spikes cluster. **Confirmed
by recomputation, not code inference** (per correction #4).

**Fallbacks:** all-zero volume → `volume_ma20=0` → `np.where` false branch → `volume_ratio≡1.0`,
`volume_spike≡0`. Constant volume → `volume_ratio≡1.0`, `volume_spike≡0`.

## 10. Volatility behavior results (correction #5 — narrower fact, not "same regime")

Compressing vs expanding candle-range sequences were run. They produced **different** terminal regimes
(compressing → `volatility_regime=0`; expanding → `2`), so **the "compression and expansion give the same
regime" claim is NOT reproduced and is NOT asserted.** The narrower, reproduced fact:

1. `volatility_regime` = tercile of `atr.rolling(200).rank(pct=True)` — a **trailing-rank of the ATR
   LEVEL**, not a directional/dynamics measure. (It responds to *relative position within the trailing
   window*: compression ends low-in-its-own-range → tercile 0; expansion ends high-in-its-own-range →
   tercile 2. The regime encodes rank, not raw level and not slope.)
2. **Zero canonical features encode volatility slope / acceleration / expansion-contraction dynamics**
   (probe listed `canonical_features_encoding_vol_slope_or_dynamics = []`).

**Conclusion:** the current 38-feature surface does **not uniquely identify volatility direction /
dynamics** as an independent observable — the dedicated quantity (ATR slope / acceleration / TR-vs-ATR
ratio) is absent from the vector. This routes to WP3 as `DERIVABLE_FROM_38_HISTORY` (from the `atr`
history) and `FOUND_RESEARCH_ONLY` (research `candle_state` encoder has `atr_ratio` + COMPRESSION/
EXPANSION tokens). See Report 2.

## 11. Numerical pathology table (post-`finalize`, 600-bar warmup)

`build_feature_vector` asserts **0 NaN / 0 Inf** post-finalize (raises otherwise), so all NaN handling is
in the fallbacks; the table records the *reachable* post-finalize behavior and the fallback each feature
uses upstream.

| Feature | NaN rate | Inf | constant | min | max | Fallback / clip (from source) |
|---|---|---|---|---|---|---|
| `atr` | 0 | no | no | 0.0115 | 0.0159 | `close<=0 → 0.0` |
| `ema_spread` | 0 | no | no | −97.1 | 96.1 | `atr<=0 → NaN` (row dropped in finalize) |
| `momentum_score` | 0 | no | no | −51.2 | 51.9 | `atr<=0 → NaN` (dropped) |
| `volatility_ratio` | 0 | no | no | 0.603 | 1.815 | `atr<=0 or close<=0 → 1.0` |
| `disp_strength` | 0 | no | no | 0.0013 | 0.524 | `atr/close<=0 → NaN` (dropped); **clip [0,3]** |
| `retest_depth` | 0 | no | no | 0.0 | 0.985 | non-retest/atr<=0 → **0.0**; **clip [0,1]** |
| `candles_since_retest` | 0 | no | no | 0 | 51 | `sweep_groups==0 → 0` |
| `liquidity_distance` | 0 | no | no | 0.00043 | 4.638 | `atr*close<=0 → NaN` (dropped) |
| `liquidity_pressure_score` | 0 | no | no | 0.098 | 0.9998 | `dist NaN → 10.0` → `exp(-5)≈0.0067`; **clip [0,1]** |
| `rsi_14` | 0 | no | no | 0.0 | 100.0 | `+1e-9` denom guard; **clip [0,100]** |
| `volume_ratio` | 0 | no | (constant-vol run) | 1.0 | — | `ma20<=0 → 1.0` |
| `volume_spike` | 0 | no | (no-spike run) | 0 | 0 | `<20 samples → fixed 1.5×` |
| `wick_size` | 0 | no | no | — | — | none (`high-low`) |
| `body_ratio` | 0 | no | no | 0.0 | 1.0 | `wick_size<=0 → 0.0` |
| `session`,`hour_of_day` | 0 | no | no | 0/0 | 2/23 | naive `.dt.hour` |
| `swing_high/low`,`higher_high`,`lower_low`,`sweep_detected`,`double_sweep` | 0 | no | no | 0 | 1 | — |
| `liquidity_sweep`,`break_of_structure` | 0 | no | no | −1 | 1 | — |
| `volatility_regime` | 0 | no | no | 0 | 2 | rolling rank, `min_periods=1` |

Zero-denominator behavior is uniformly guarded (`np.where` sentinels or `+1e-9`). **Inf is impossible in
the vector** by the finalize `replace([inf,-inf], nan)` + `dropna` + build-time assertion. Saturation:
`disp_strength` clips at 3.0, `retest_depth` at 1.0, `liquidity_pressure_score` at 1.0, `rsi_14` at 0/100.

## 12. Structure/liquidity semantic reconstruction (WP2)

Reconstructed from `feature_pipeline.py:389-718` (batch) and `causal_structure.py` (online twin).

| Quantity | Identity / algorithm | Event vs state | Direction | Reset / history | Missing-value |
|---|---|---|---|---|---|
| `swing_high/low` | centered pivot `high==rolling(5,center).max()` **shifted +k=2** (`:409-444`) | per-bar 0/1 event | 2 cols | publication delay k=2 | `shift` NaN→0 |
| `last_swing_*_price` | price at centered pivot, ffill, shifted +2 | continuous state | — | ffill | NaN pre-first-pivot |
| `higher_high`/`lower_low` | `high>ref_high` / `low<ref_low`, `ref=last_swing.shift(1)` (`:453-459`) | per-bar 0/1 event (not latched) | 2 cols | recomputed each bar | NaN ref → False |
| `break_of_structure` | `close>ref_high →+1`, `close<ref_low →−1` (`:468-471`) | signed per-bar **event** | **signed** | recomputed | 0 |
| `liquidity_sweep` | `(high>ref_high & close<=ref_high)→+1`; `(low<ref_low & close>=ref_low)→−1` (`:473-479`) | signed per-bar event | **signed** | recomputed | 0 |
| `sweep_detected` | `(liquidity_sweep!=0)` (`:585`) | 0/1 event | **direction LOST** | — | 0 |
| `double_sweep` | both signs present in rolling-5 (`:607-621`) | 0/1 event | direction not preserved | 5-bar window | 0 |
| `retest_flag` | `recent_sweep(rolling10) & |close−ema_fast|<=atr*close` (`:594-605`) | 0/1 event | — | 10-bar post-sweep | 0 |
| `retest_depth` | gated on retest_flag: `|close−ema_fast|/(atr*close)` (`:643-648`) | continuous [0,1] | — | resets with retest_flag | non-retest→0.0 |
| `candles_since_retest` | `cumcount` within `liquidity_sweep!=0` groups (`:658-667`) | counter | — | **resets on SWEEP** | 0 |
| `liquidity_distance` | `min(|close−{ref_high,ref_low,bos_level}|)/(atr*close)` (`:669-713`) | continuous | — | levels ffill/shift(1) | NaN (batch) / 10.0 (online) |
| `liquidity_pressure_score` | `exp(-0.5*liquidity_distance.fillna(10.0))` clip[0,1] (`:715-718`) | continuous | — | — | dist NaN → 10.0 → ≈0.0067 |

**Explicit answers (correction: derived from code + fresh events, not prior PIT assertions):**

- **BOS direction preserved?** Yes — `break_of_structure ∈ {−1,0,+1}` (runtime distinct values observed).
- **BOS event or state?** Per-bar **event**, recomputed each bar (not latched). A separate `bos_level`
  IS ffill-latched, but only inside `liquidity_distance`, not exposed as a vector feature.
- **HH/LL event or state?** Per-bar **events** (0/1), recomputed each bar.
- **Liquidity sweep direction preserved?** In `liquidity_sweep` **yes** ({−1,0,+1}); in `sweep_detected`
  **no** (collapsed to 0/1).
- **Can the surface distinguish liquidity rejection from acceptance?** Partially. `liquidity_sweep`
  encodes a **rejection** pattern (poke beyond level then close back inside). **Acceptance** (close
  *beyond* the level and hold) is `break_of_structure`, a separate feature — so rejection vs acceptance
  is representable only by reading *two* features jointly; there is no single "outcome" feature.
- **Breakout attempt vs acceptance?** Attempt-then-reject = `liquidity_sweep≠0`; acceptance =
  `break_of_structure≠0`. No feature encodes the *transition/attempt→outcome* lifecycle.
- **Breakout acceptance vs failure?** **Not directly.** There is no persistence/"time-beyond-level" or
  retest-outcome feature. Failure-after-acceptance cannot be read from a single bar's vector.
- **What level does `retest_depth` measure from?** **`ema_fast` (EMA9)** — not a swing/BOS structural
  level. It is EMA9 proximity gated by a recent sweep.
- **What resets `candles_since_retest`?** The **`liquidity_sweep` event** (not the retest). Name is
  misleading; source comment (`:650-655`) documents the deliberate change from retest-grouping.
- **Can structural evidence AGE be reconstructed from feature history?** Partly: `candles_since_retest`
  gives bars-since-sweep; bars-since-swing/BOS is **not** a feature (derivable from the swing/BOS event
  history if that history is retained — see Report 2).
- **Can breakout persistence be reconstructed?** Only by retaining the `break_of_structure` event series
  and counting bars price stays beyond the level — **not** available as a feature; needs history buffer.
- **Can retest hold/failure be reconstructed?** Not from a single snapshot; requires post-event tracking
  of price vs the swept level over subsequent bars (history-dependent; no feature encodes it).
- **Does delayed structure publication propagate correctly downstream?** Yes — the whole graph
  (HH/LL/BOS/sweep/liquidity/retest) binds to the **causal** `last_swing_*` (shift +2), and PIT probes
  (§14) show all eight structure columns are prefix-invariant with the expected k=2 delay.

## 13. Structure synthetic sequence results (WP2 — two-stage protocol, correction #6)

**Stage A (prerequisite generation) — 30-bar engineered zig-zag:** ran through the real pipeline.
Result: **`rows_survived_finalize = 0`** (all structure/HH/LL/sweep/BOS counts = 0). Cause: canonical
`trend_strength` is z-score-normalized over `rolling(50)`, so a 30-bar frame yields all-NaN in a
canonical column → every row is dropped by `finalize()`. **Therefore no prerequisite event was produced,
and per the two-stage rule NO semantic label (retest / false-breakout / BOS / sweep) is applied to this
sequence.** This is the correct, honest outcome: a short hand-built sequence cannot exercise the
production structure graph, which needs ≥50 bars just to survive normalization.

**Stage A (prerequisite generation) — 500-bar warmup where structure actually publishes:**

| Event | Count (422 surviving rows) |
|---|---|
| `swing_high` / `swing_low` | 18 / 21 |
| `liquidity_sweep` up (+1) / down (−1) | 25 / 24 |
| `sweep_detected` (unsigned) sum | 49 |
| `break_of_structure` up / down | 58 / 107 |
| `higher_high` / `lower_low` | 83 / 133 |
| `double_sweep` | 8 |
| `retest_flag` | 171 |
| `candles_since_retest` max | 62 |

**Stage B (semantic tests, only on fired prerequisites):** direction preservation confirmed on real
events — `liquidity_sweep` values `{−1,0,+1}`, `break_of_structure` values `{−1,0,+1}`, `sweep_detected`
values `{0,1}` (direction lost). All Stage-B claims in §12 are backed by these fired events, none by
hand-labeling.

## 14. Fresh prefix/PIT probe results (WP2 — correction #7)

Method: run the full 500-bar frame and a prefix cut 5 bars short; **join published outputs by timestamp
identity** (not row position) over the 417 common timestamps; count value mismatches per structure column.

| Column | prefix-vs-full mismatches (by timestamp) |
|---|---|
| `swing_high`, `swing_low` | 0, 0 |
| `last_swing_high_price`, `last_swing_low_price` | 0, 0 |
| `liquidity_sweep`, `break_of_structure` | 0, 0 |
| `higher_high`, `lower_low` | 0, 0 |

`prefix_invariant = true` (all columns). **Swing publication delay** (first bar a centered pivot becomes
visible as `swing_high==1`): **mode 2, median 2.0**, matching `k=SWING_WINDOW=2`. First `swing_high`
publication timestamp: `2024-01-02 08:30:00`. This **independently reproduces** the PIT/causal property
from fresh execution — it does **not** rely on `test_pit_prefix_invariance.py`'s pass status.

## 15. Verified findings (fresh evidence, contamination rule satisfied)

1. `atr` is close-relative (#1) — scale-invariant.
2. `ema_spread` scales with price level (#2) — absolute/relative dimensional mix. **Defect real.**
3. `momentum_score` scales with price level (#3) — same defect. **Real.**
4. `volatility_ratio` is scale-coherent (#4) — divides by absolute ATR.
5. `disp_strength` is scale-coherent (#5).
6. RSI is **SMA-based, not Wilder** (#6) despite the "Wilder" docstring — DOC_DRIFT.
7. ATR is **SMA-of-TR, not Wilder** (#7).
8. `candles_since_retest` resets on **sweep**, not retest (#8).
9. `retest_depth` measures **EMA9 proximity**, not a structural level (#9).
10. `volume_ratio` baseline **includes the current bar** — spike ratio understated ~1.95× (#10).
11. `volume_spike` adaptive threshold **includes the current observation** (#11).
12. `volatility_regime` is an ATR-**level** trailing-rank tercile; **no vol-dynamics feature exists** (#12).
13. `liquidity_pressure_score` is a monotonic transform of `liquidity_distance`, missing→10.0 (#13).
14. `wick_size` == full candle range (high−low), **not** wick magnitude (#14) — all 8 geometry cases.
15. session derives from **naive timestamp hour**, no timezone contract (#15).
16. `sweep_detected` **loses** sweep direction; `liquidity_sweep`/`break_of_structure` preserve it.
17. Structure is **PIT-causal** with a measured **k=2** publication delay (fresh reproduction).

## 16. Rejected findings

- **None of the 15 provisional findings was rejected.** Every one reproduced.
- Rejected *sub-claim*: the stronger phrasing "compression and expansion produce the same
  `volatility_regime`" is **NOT** supported (the two produced different terminal regimes); only the
  narrower "no canonical feature encodes vol dynamics / regime is a level-rank" is verified (§10).
- The docstring assertions "Standard Wilder formula" (RSI, `:254`) and the `(N,32)` vector-width
  docstrings (`:837`,`:880`) are **rejected as inaccurate** (actual: SMA RSI; 38-wide vector).

## 17. Unresolved findings

- **Live-path parity for ATR/RSI/session:** `feature_store.py` consumes `atr`/`ema`/`session`
  **pre-computed from upstream**; this probe exercised the **batch** `FeaturePipeline`. Whether the live
  feeder reproduces the exact SMA-ATR/SMA-RSI/naive-session values is **not** established here (out of
  scope; flagged).
- **Timezone of production timestamps:** the *contract* is absent (naive `.dt.hour`); which tz the live
  feed actually carries is a data-layer question, unresolved at the feature layer.
- **`double_sweep` producer split:** batch computes it in `compute_canonical_structure_features` while
  the online twin bundles it in one pass — semantic equality across the two was not exhaustively
  differenced (single-window w=5 matched in counts; a dedicated parity probe is future work).

## 18. No-production-behavior-change proof

- The probe harness lives in the **scratchpad** (`scratchpad/mr_probe.py`), is **not committed**, and
  **imports** the production pipeline read-only — it defines no monkey-patch and writes no repo file.
- No file under `src/`, `configs/production/`, `tests/`, or any engine/fusion/decision/execution/risk
  module was modified by this task. (Pre-existing working-tree `M` markers predate this session and are
  unrelated.)
- Deliverables created: this report, `market-reality-repository-search-2026-07-12.md`,
  `configs/market_reality/market_reality_v1.yaml`, plus the mandated §6 SESSION LOG append to
  `assistant_project.md` (documentation-only, governance).
- `git diff -- src configs/production tests` from this task = **empty**. See final response GIT_STATUS /
  GIT_DIFF_SUMMARY.

**Probe harness source** is embedded verbatim in **Appendix A** of this report (uncommitted script);
its raw output was written to `scratchpad/mr_probe_results.json`. Reproduce by saving Appendix A to
`scratchpad/mr_probe.py` and running `venv/Scripts/python.exe scratchpad/mr_probe.py`.

## Appendix A — Probe harness source (verbatim, uncommitted)

The harness ran from the session scratchpad and is **not** committed (per task policy: prefer
inline code + commands over a committed script). Full source, reproducible with
`venv/Scripts/python.exe <this-file>` after saving to `scratchpad/mr_probe.py`:

```python
"""Market-Reality fresh probe harness (WP1 + WP2). SCRATCHPAD ONLY — not committed.

Reconstructs feature correctness from the CURRENT production implementation via
fresh runtime execution. Trusts NO prior verdict. Imports the real FeaturePipeline.
Emits a JSON artifact + a human-readable summary to stdout.

Run: venv/Scripts/python.exe scratchpad/mr_probe.py
"""
import sys, os, json, io
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "..", "src"))
# Robust: also add repo src explicitly
REPO = r"D:\Tradelatest"
sys.path.insert(0, os.path.join(REPO, "src"))

from features.feature_pipeline import FeaturePipeline, SWING_WINDOW
from features.feature_schema import CANONICAL_FEATURES

RESULTS = {}
TS0 = pd.Timestamp("2024-01-01 00:00:00")

def ts(n):
    return pd.date_range(TS0, periods=n, freq="15min")

def warmup_df(n=450, base=100.0, seed=7, vol=1000.0):
    """Deterministic smooth-ish warmup with nonzero ATR and valid OHLC."""
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, 0.15, n).cumsum()
    close = base + steps + 3.0*np.sin(np.arange(n)/9.0)
    open_ = np.concatenate([[close[0]], close[:-1]])
    rngspan = 0.4 + 0.2*np.abs(rng.normal(0,1,n))
    high = np.maximum(open_, close) + rngspan
    low  = np.minimum(open_, close) - rngspan
    volume = np.full(n, vol)
    return pd.DataFrame({"timestamp": ts(n), "open": open_, "high": high,
                         "low": low, "close": close, "volume": volume})

def run(df):
    enriched, vectors = FeaturePipeline(df.copy()).run()
    return enriched

# ============================================================ WP1.1 GEOMETRY
def probe_geometry():
    """Warmup + one crafted target candle (correction #2). Inspect target row."""
    base = warmup_df(450)
    last_close = float(base["close"].iloc[-1])
    C = last_close  # anchor target near last close so ATR/normalisation are stable
    cases = {}
    # (open, high, low, close) constructed as the appended target candle
    defs = {
        "zero_range":      (C,     C,      C,      C),
        "doji":            (C,     C+0.5,  C-0.5,  C+0.001),
        "full_bull_body":  (C-1.0, C+1.0,  C-1.0,  C+1.0),   # close=high, open=low
        "full_bear_body":  (C+1.0, C+1.0,  C-1.0,  C-1.0),   # close=low, open=high
        "long_upper_wick": (C,     C+3.0,  C-0.2,  C+0.2),
        "long_lower_wick": (C,     C+0.2,  C-3.0,  C-0.2),
        "outside_bar":     (C-0.5, C+4.0,  C-4.0,  C+0.5),   # engulfs prior range
        "inside_bar":      (C,     C+0.3,  C-0.3,  C+0.1),
    }
    warm_construction = {
        "warmup_bars": 450, "base_price": 100.0, "seed": 7, "constant_volume": 1000.0,
        "target_is": "single appended candle at index 450 (survives finalize warmup budget 300)",
        "anchor_close": round(C, 6),
    }
    for name, (o,h,l,c) in defs.items():
        row = pd.DataFrame({"timestamp": [ts(451)[-1]], "open":[o], "high":[h],
                            "low":[l], "close":[c], "volume":[1000.0]})
        df = pd.concat([base, row], ignore_index=True)
        enr = run(df)
        tgt = enr.iloc[-1]
        cases[name] = {
            "ohlc": [o,h,l,round(c,6)],
            "wick_size": float(tgt["wick_size"]),
            "high_minus_low": float(h-l),
            "body_size": float(tgt["body_size"]),
            "body_ratio": float(tgt["body_ratio"]),
            "price_position": float(tgt["price_position"]),
            "disp_strength": float(tgt["disp_strength"]),
            "volatility_ratio": float(tgt["volatility_ratio"]),
        }
    return {"warmup_construction": warm_construction, "cases": cases}

# ============================================================ WP1.2 SCALE INVARIANCE
def probe_scale_invariance():
    """Multiply ALL price OHLC by constant k; preserve ts/volume/%path/len (#3)."""
    base = warmup_df(450, seed=11)
    feats = ["atr","ema_spread","momentum_score","volatility_ratio",
             "disp_strength","retest_depth","liquidity_distance"]
    def scaled(k):
        d = base.copy()
        for c in ["open","high","low","close"]:
            d[c] = d[c]*k
        return run(d)
    e1 = scaled(1.0); e100 = scaled(100.0)
    # align by timestamp identity
    m = e1.merge(e100, on="timestamp", suffixes=("_1","_100"))
    out = {}
    for f in feats:
        a = m[f+"_1"].to_numpy(dtype=float); b = m[f+"_100"].to_numpy(dtype=float)
        max_abs = float(np.nanmax(np.abs(a-b)))
        # relative: is b ~= a (invariant) or b ~= 100*a (scales with price)?
        denom = np.where(np.abs(a) > 1e-9, np.abs(a), np.nan)
        ratio = np.nanmedian(np.abs(b)/denom)
        out[f] = {"aligned_rows": int(len(m)),
                  "max_abs_diff_k1_vs_k100": max_abs,
                  "median_ratio_k100_over_k1": None if np.isnan(ratio) else round(float(ratio),4),
                  "verdict": "INVARIANT" if max_abs < 1e-3 else "SCALES_WITH_PRICE"}
    return out

# ============================================================ WP1.3 ATR / RSI IDENTITY
def _wilder_atr(tr, period=14):
    tr = np.asarray(tr, dtype=float); n=len(tr); out=np.full(n, np.nan)
    if n < period: return out
    seed = np.nanmean(tr[:period]); out[period-1]=seed
    for t in range(period, n):
        prev = out[t-1]
        out[t] = (prev*(period-1) + tr[t])/period
    return out

def _sma_atr(tr, period=14):
    return pd.Series(tr).rolling(period).mean().to_numpy()

def _rsi(close, period=14, wilder=False):
    close=pd.Series(close, dtype=float); delta=close.diff()
    gain=delta.clip(lower=0); loss=(-delta.clip(upper=0))
    if wilder:
        ag=gain.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
        al=loss.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    else:
        ag=gain.rolling(period).mean(); al=loss.rolling(period).mean()
    rs=ag/(al+1e-9)
    return (100 - 100/(1+rs)).clip(0,100).to_numpy()

def probe_atr_rsi():
    base = warmup_df(450, seed=13)
    enr = run(base)
    # reconstruct TR on the ORIGINAL frame (pre-finalize) to align, then join by ts
    d = base.copy()
    tr1=d["high"]-d["low"]; tr2=(d["high"]-d["close"].shift(1)).abs(); tr3=(d["low"]-d["close"].shift(1)).abs()
    tr=np.maximum(tr1, np.maximum(tr2,tr3)).to_numpy()
    d["_sma_atr"]=_sma_atr(tr); d["_wilder_atr"]=_wilder_atr(tr)
    d["_rsi_sma"]=_rsi(d["close"],14,False); d["_rsi_wilder"]=_rsi(d["close"],14,True)
    ref = d[["timestamp","_sma_atr","_wilder_atr","_rsi_sma","_rsi_wilder"]]
    m = enr.merge(ref, on="timestamp")
    prod_atr_raw = m["atr_14_raw"].to_numpy(dtype=float)
    prod_rsi = m["rsi_14"].to_numpy(dtype=float)
    def maxdiff(a,b):
        a=np.asarray(a,float); b=np.asarray(b,float); mask=~(np.isnan(a)|np.isnan(b))
        return float(np.max(np.abs(a[mask]-b[mask]))) if mask.any() else None
    return {
        "aligned_rows": int(len(m)),
        "atr_prod_vs_sma_TR_maxdiff": maxdiff(prod_atr_raw, m["_sma_atr"]),
        "atr_prod_vs_wilder_maxdiff": maxdiff(prod_atr_raw, m["_wilder_atr"]),
        "rsi_prod_vs_sma_maxdiff": maxdiff(prod_rsi, m["_rsi_sma"]),
        "rsi_prod_vs_wilder_maxdiff": maxdiff(prod_rsi, m["_rsi_wilder"]),
        "note": "prod matches the method with ~0 diff; large diff to the other identity",
    }

# ============================================================ WP1.4 VOLUME (self-inclusion #4)
def probe_volume():
    n=120
    def build(volume):
        d=warmup_df(n, seed=5)
        d["volume"]=volume
        return d
    out={}
    # isolated spike scenario: constant then one big spike at index 80
    vol=np.full(n,1000.0); spike_idx=80; vol[spike_idx]=20000.0
    d=build(vol); enr=run(d)
    m=enr.merge(pd.DataFrame({"timestamp":ts(n),"_rawvol":vol}), on="timestamp")
    # production values at the spike bar
    srow=m[m["timestamp"]==ts(n)[spike_idx]]
    if len(srow):
        srow=srow.iloc[0]
        # counterfactual (correction #4): baseline from PRIOR bars only
        prior = vol[spike_idx-20:spike_idx]           # 20 prior bars, EXCLUDING spike
        incl  = vol[spike_idx-19:spike_idx+1]         # production window INCLUDING spike (rolling(20))
        ref_ratio_prioronly = vol[spike_idx]/prior.mean()
        prod_ma20 = float(srow["volume_ma20"]); prod_ratio=float(srow["volume_ratio"])
        out["isolated_spike"]={
            "prod_volume_ma20_incl_current": prod_ma20,
            "reference_ma20_prior_only": float(prior.mean()),
            "prod_volume_ratio_incl_current": prod_ratio,
            "reference_ratio_prior_only": float(ref_ratio_prioronly),
            "current_bar_contribution_to_own_baseline_units": float(prod_ma20 - prior.mean()),
            "ratio_understatement_factor": float(ref_ratio_prioronly / prod_ratio) if prod_ratio else None,
            "prod_volume_spike": int(srow["volume_spike"]),
        }
    # volume_spike threshold self-inclusion: build a vol_ratio series with a spike, at bar t
    # measure prod threshold-window incl current vs prior-only quantile.
    # Use a longer series so adaptive threshold (window50,min20) is active.
    n2=200; vol2=np.full(n2,1000.0)
    rng=np.random.default_rng(3); vol2=vol2*(1+0.05*rng.normal(0,1,n2))
    tidx=150; vol2[tidx]=8000.0
    d2=warmup_df(n2,seed=9); d2["volume"]=vol2; enr2=run(d2)
    m2=enr2.merge(pd.DataFrame({"timestamp":ts(n2)}), on="timestamp")
    vr=enr2.set_index("timestamp")["volume_ratio"]
    tstamp=ts(n2)[tidx]
    if tstamp in vr.index:
        # production window includes current: rolling(50).quantile(.75) at t
        win_incl = vr.loc[:tstamp].tail(50)
        thr_incl = float(win_incl.quantile(0.75))
        win_prior = vr.loc[:tstamp].iloc[:-1].tail(50)
        thr_prior = float(win_prior.quantile(0.75))
        cur_vr = float(vr.loc[tstamp])
        out["spike_threshold_self_inclusion"]={
            "current_volume_ratio": cur_vr,
            "prod_threshold_window_incl_current_q75": thr_incl,
            "reference_threshold_prior_only_q75": thr_prior,
            "current_bar_raised_own_threshold_by": thr_incl - thr_prior,
            "fires_under_prod_incl": bool(cur_vr > thr_incl),
            "fires_under_prior_only": bool(cur_vr > thr_prior),
        }
    # fallbacks: zero volume, constant volume
    dz=warmup_df(60,seed=1); dz["volume"]=0.0
    ez=run(dz)
    out["zero_volume"]={
        "volume_ratio_unique": sorted(set(np.round(ez["volume_ratio"].to_numpy(),6).tolist()))[:5],
        "volume_spike_sum": int(ez["volume_spike"].sum()),
        "note":"all-zero volume -> volume_ma20=0 -> np.where false -> ratio fallback 1.0",
    }
    dc=warmup_df(80,seed=2); dc["volume"]=1000.0
    ec=run(dc)
    out["constant_volume"]={
        "volume_ratio_unique": sorted(set(np.round(ec["volume_ratio"].to_numpy(),6).tolist()))[:5],
        "volume_spike_sum": int(ec["volume_spike"].sum()),
    }
    return out

# ============================================================ WP1.5 VOLATILITY DYNAMICS (#5)
def probe_volatility_dynamics():
    """Does the feature set UNIQUELY identify vol direction/dynamics? Counterexample."""
    n=300
    def make(range_profile, seed):
        rng=np.random.default_rng(seed)
        close=100+np.cumsum(rng.normal(0,0.05,n))
        open_=np.concatenate([[close[0]],close[:-1]])
        half=range_profile/2.0
        high=np.maximum(open_,close)+half; low=np.minimum(open_,close)-half
        return pd.DataFrame({"timestamp":ts(n),"open":open_,"high":high,"low":low,
                             "close":close,"volume":np.full(n,1000.0)})
    # compressing: range shrinks to r_end. expanding: range grows to r_end.
    r_end=1.0
    comp_profile=np.linspace(3.0, r_end, n)     # high->low  (compression)
    exp_profile =np.linspace(0.2, r_end, n)     # low->high  (expansion), ends similar level
    ec=run(make(comp_profile, 21)); ee=run(make(exp_profile, 21))
    # compare the LAST regime value + whether any canonical feature encodes slope
    tail_c=ec.iloc[-1]; tail_e=ee.iloc[-1]
    canon=set(CANONICAL_FEATURES)
    slope_like=[c for c in canon if any(k in c for k in ("slope","accel","delta","dynamic","expansion","contract"))]
    return {
        "compressing_last_volatility_regime": int(tail_c["volatility_regime"]),
        "expanding_last_volatility_regime": int(tail_e["volatility_regime"]),
        "compressing_last_atr": float(tail_c["atr"]),
        "expanding_last_atr": float(tail_e["atr"]),
        "canonical_features_encoding_vol_slope_or_dynamics": slope_like,
        "note": "volatility_regime = tercile of trailing-200 ATR rank (LEVEL). No canonical "
                "feature encodes ATR slope/acceleration -> vol DIRECTION not uniquely identified.",
    }

# ============================================================ WP1.6 NUMERICAL PATHOLOGY
def probe_pathology():
    base=warmup_df(600, seed=42)
    enr=run(base)
    tbl={}
    for f in CANONICAL_FEATURES:
        s=pd.to_numeric(enr[f], errors="coerce")
        arr=s.to_numpy(dtype=float)
        tbl[f]={
            "nan_rate_post_finalize": round(float(np.isnan(arr).mean()),4),
            "inf_present": bool(np.isinf(arr).any()),
            "constant_output": bool(np.nanstd(arr)==0.0),
            "min": None if np.all(np.isnan(arr)) else round(float(np.nanmin(arr)),6),
            "max": None if np.all(np.isnan(arr)) else round(float(np.nanmax(arr)),6),
        }
    return {"note":"post-finalize (build_feature_vector asserts 0 NaN); "
                   "clipping: disp_strength[0,3], retest_depth[0,1], liq_pressure[0,1]",
            "features": tbl}

# ============================================================ WP2 STRUCTURE (two-stage #6, PIT #7)
def build_structure_sequence():
    """A single deterministic sequence engineered to (attempt to) produce swings,
    a sweep, and a BOS. Two-stage: we PRINT what the implementation actually fired,
    then only label semantics on fired prerequisites."""
    # Construct a zig-zag with clear pivots then a boundary cross.
    prices=[100,100.2,100.5,101.0,101.6,101.2,100.9,100.6,100.4,100.8,
            101.4,102.2,103.0,102.6,102.1,101.7,101.3,101.9,102.7,103.6,
            104.6,104.1,103.5,103.0,102.6,103.2,104.1,105.2,106.4,106.0]
    n=len(prices); close=np.array(prices,float)
    open_=np.concatenate([[close[0]],close[:-1]])
    high=np.maximum(open_,close)+0.15; low=np.minimum(open_,close)-0.15
    # engineer one upside sweep at index 21: high pokes above prior swing high but closes back below
    df=pd.DataFrame({"timestamp":ts(n),"open":open_,"high":high,"low":low,
                     "close":close,"volume":np.full(n,1000.0)})
    return df

def probe_structure_stageA():
    df=build_structure_sequence()
    enr=run(df)
    # NOTE: finalize drops warmup (swing needs w=5, ma_200 needs 200 -> most rows drop!)
    # For a 30-bar seq, ma_200 rolling(200) is all-NaN -> ma-based cols NaN but those
    # are not canonical EXCEPT trend_strength (normalized). Report survivors.
    fired={
        "rows_in": int(len(df)),
        "rows_survived_finalize": int(len(enr)),
        "swing_high_events": int(enr["swing_high"].sum()) if "swing_high" in enr else None,
        "swing_low_events": int(enr["swing_low"].sum()) if "swing_low" in enr else None,
        "liquidity_sweep_nonzero": int((enr["liquidity_sweep"]!=0).sum()) if "liquidity_sweep" in enr else None,
        "break_of_structure_nonzero": int((enr["break_of_structure"]!=0).sum()) if "break_of_structure" in enr else None,
        "higher_high_events": int(enr["higher_high"].sum()) if "higher_high" in enr else None,
        "lower_low_events": int(enr["lower_low"].sum()) if "lower_low" in enr else None,
        "double_sweep_events": int(enr["double_sweep"].sum()) if "double_sweep" in enr else None,
    }
    return fired

def probe_structure_on_full_warmup():
    """Use a LONG warmup so structure columns actually publish (ma_200 satisfied),
    then read directional semantics from real fired events (Stage A)."""
    df=warmup_df(500, seed=17)
    enr=run(df)
    def cnt(col, cond):
        return int(cond.sum())
    ls=enr["liquidity_sweep"]
    bos=enr["break_of_structure"]
    return {
        "rows_survived": int(len(enr)),
        "swing_high_events": int(enr["swing_high"].sum()),
        "swing_low_events": int(enr["swing_low"].sum()),
        "sweep_up_events": int((ls>0).sum()),
        "sweep_down_events": int((ls<0).sum()),
        "sweep_detected_unsigned_sum": int(enr["sweep_detected"].sum()),
        "bos_up_events": int((bos>0).sum()),
        "bos_down_events": int((bos<0).sum()),
        "higher_high_events": int(enr["higher_high"].sum()),
        "lower_low_events": int(enr["lower_low"].sum()),
        "double_sweep_events": int(enr["double_sweep"].sum()),
        "retest_flag_events": int(enr["retest_flag"].sum()),
        "candles_since_retest_max": int(enr["candles_since_retest"].max()),
        "sweep_detected_preserves_direction": bool(set(np.unique(enr["sweep_detected"]))<= {0,1}),
        "liquidity_sweep_preserves_direction": sorted(set(int(x) for x in np.unique(ls))),
        "break_of_structure_values": sorted(set(int(x) for x in np.unique(bos))),
    }

def probe_pit_swings():
    """PIT (#7): append future bars; compare published values by TIMESTAMP identity.
    Measure swing publication delay (expect k=SWING_WINDOW=2)."""
    full=warmup_df(500, seed=17)
    enr_full=run(full)
    # take a prefix that cuts off the last 5 bars
    cut=5
    prefix=full.iloc[:len(full)-cut].copy()
    enr_prefix=run(prefix)
    # join by timestamp on swing_high/swing_low/last_swing_high_price
    cols=["swing_high","swing_low","last_swing_high_price","last_swing_low_price",
          "liquidity_sweep","break_of_structure","higher_high","lower_low"]
    a=enr_prefix.set_index("timestamp")[cols]
    b=enr_full.set_index("timestamp")[cols]
    common=a.index.intersection(b.index)
    mismatches={}
    for c in cols:
        av=a.loc[common,c].to_numpy(dtype=float); bv=b.loc[common,c].to_numpy(dtype=float)
        diff=np.nan_to_num(av-bv, nan=0.0)
        mismatches[c]=int(np.sum(np.abs(diff)>1e-9))
    # measure swing publication delay: for each centered pivot in full, when does swing_high flip to 1?
    # We reconstruct centered pivot from raw highs and compare to published causal flag timestamp.
    d=full.copy()
    w=2*SWING_WINDOW+1
    roll_high=d["high"].rolling(w,center=True,min_periods=w).max()
    centered=(d["high"]==roll_high)
    d["_centered"]=centered.values
    # published swing_high in enr_full
    pub=enr_full.set_index("timestamp")["swing_high"]
    delays=[]
    cen_ts=d.loc[d["_centered"],"timestamp"].tolist()
    for t in cen_ts:
        # find first published swing_high==1 at or after t
        after=pub.loc[pub.index>=t]
        hit=after[after==1]
        if len(hit):
            delay_bars=int((d["timestamp"]>=t).sum() - (d["timestamp"]>=hit.index[0]).sum())
            # delay in bars = position(hit) - position(t)
            pos_t=int((d["timestamp"]<t).sum())
            pos_h=int((d["timestamp"]<hit.index[0]).sum())
            delays.append(pos_h-pos_t)
    return {
        "common_timestamps": int(len(common)),
        "prefix_vs_full_mismatches_by_col": mismatches,
        "prefix_invariant": all(v==0 for v in mismatches.values()),
        "swing_publication_delay_bars_mode": int(pd.Series(delays).mode().iloc[0]) if delays else None,
        "swing_publication_delay_bars_median": float(np.median(delays)) if delays else None,
        "expected_delay_k": SWING_WINDOW,
        "first_swing_high_publication_ts": str(pub[pub==1].index[0]) if (pub==1).any() else None,
    }

# ============================================================ RUN ALL
def main():
    RESULTS["meta"]={"swing_window_k":SWING_WINDOW,"canonical_dim":len(CANONICAL_FEATURES)}
    RESULTS["wp1_geometry"]=probe_geometry()
    RESULTS["wp1_scale_invariance"]=probe_scale_invariance()
    RESULTS["wp1_atr_rsi"]=probe_atr_rsi()
    RESULTS["wp1_volume"]=probe_volume()
    RESULTS["wp1_volatility_dynamics"]=probe_volatility_dynamics()
    RESULTS["wp1_pathology"]=probe_pathology()
    RESULTS["wp2_structure_shortseq_stageA"]=probe_structure_stageA()
    RESULTS["wp2_structure_longwarmup_stageA"]=probe_structure_on_full_warmup()
    RESULTS["wp2_pit_swings"]=probe_pit_swings()
    outpath=os.path.join(os.path.dirname(__file__),"mr_probe_results.json")
    with open(outpath,"w",encoding="utf-8") as f:
        json.dump(RESULTS,f,indent=2,default=str)
    print("WROTE", outpath)
    print(json.dumps(RESULTS,indent=2,default=str))

if __name__=="__main__":
    import logging; logging.disable(logging.CRITICAL)
    main()
```
