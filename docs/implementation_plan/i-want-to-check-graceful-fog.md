# Report: OHLCV→feature tracing (both flows) + blast radius of the two XAUUSD warnings

## Context

Follows the XAUUSD run on active config `v2_multi_2026_04` (1 trade, net −0.04R). Two questions:
(1) do the `normalization_basis` / `session_timestamp_basis` warnings explain or cause bugs in
upper layers? (2) trace OHLCV→feature formation in `BacktestRunner` vs `CRTStateResolver`.

Everything below marked ✅ was verified by me against source or by running read-only probes.
Items marked ⚠️ are unverified and flagged as such. Three sub-agent claims were **corrected**
during verification — noted inline.

---

# PART A — OHLCV → feature formation, both flows

## A1. BacktestRunner: TWO independent passes over the same CSV ✅

The single most important structural fact: `backtest_v2` reads the CSV **twice**, by two different
readers, producing two parallel derivations that are only reconciled at trade time.

```
data/mt5/XAUUSD_M15.csv
   │
   ├─ PASS 1 (vectorized, pandas) ─────────────────────────────────────────
   │   backtest_v2.py:1790  raw_df = pd.read_csv(self.csv_path)
   │   :1792                columns → lowercase
   │   :1794-1800           synthesize `timestamp` from date+time if absent
   │   :1803                require_ohlcv_columns(...)
   │   :1804-1805           FeaturePipeline(raw_df).run()
   │        └─ feature_pipeline.py:1316 run() — ordered steps:
   │             :1329 compute_price_features   :1330 compute_volume_features
   │             :1331 compute_indicators       :1332 compute_trend_features
   │             :1333 compute_volatility_regime:1334 compute_context
   │             :1335 compute_structure_liquidity :1336 compute_normalization
   │             :1339 canonical_price :1340 volatility :1341 ema :1342 trend
   │             :1343 structure :1344 temporal :1345 liquidity_distance
   │             :1346 promote_volume_spike :1347 canonical_session
   │             :1350 finalize()  ← WARMUP DROP + INDEX RESET (single stmt, :1198)
   │                                 df.dropna(subset=CANONICAL_FEATURES).reset_index(drop=True)
   │             :1352 build_feature_vector() (:1276) → 39-dim vectors
   │   → enriched_df (47,197 rows) + self.feature_vectors
   │   :1810-1814  feature_ts_to_idx = {ts.strftime("%Y-%m-%d %H:%M:%S"): i}
   │
   └─ PASS 2 (row-by-row, csv.reader) ─────────────────────────────────────
       backtest_v2.py:700   class CandleLoader   (same file)
       :752-754             stream() re-opens the file with csv.reader
       :840-841             yields crt_engine_v2.Candle(..., index=_candle_pos)
       NO warmup skip, NO dropna — every raw row is yielded (47,275)
            └─ Candle geometry is its OWN, ontology-routed:
               crt_engine_v2.py:86/92/97 → _cm.body_size / FM-002 / FM-010
```

**The join** ✅ — `engine.process_candle(candle, ...)` runs for **every** candle (`:2202`), but the
39-dim vector is pulled **only inside** `if "TRADE_OPENED" in action` (`:2224` → `:2235-2236`
lookup → `:2268` `.tolist()`). So on 47,274 of 47,275 candles this run, the pipeline vector was
never consulted at all — the CRT state machine ran purely on its own ontology-routed geometry.

**Consequence worth internalizing:** the pipeline's 39-dim vector does **not** drive trade
*generation*. It drives scoring/fusion/monitoring **after** a setup exists. That bounds how much
damage the saturation defects (Part B) can do in this flow.

## A2. CRTStateResolver flow ✅

```
data/mt5/XAUUSD_M15.csv
   └─ run_crt_state_on_mt5_xauusd.py  (OHLCV_PATH :35 hardcoded)
        └─ FeaturePipeline(...).run()          ← SAME pipeline as pass 1
             └─ per-bar: CRTStateResolver.resolve(feat_dict, timestamp=...)   :118
                  crt_state_resolver.py:194-283 resolve():
                    normalize → encode feature states → candle_index += 1 (:244)
                    → _advance_htf (:247) → _apply_lifecycle_resets (:253)
                    → _tick_shadow_ttl (:268) → _resolve_from_features (:271)
                    → _apply_transition_validity (:274) → _update_memory (:277)
        → state counts / funnel → reports/crt_state_fresh_run_xauusd.md
```

## A3. Why the two funnels disagree — and the correction I had to make ✅

I initially framed this as "stateless resolver vs stateful engine." **That was wrong**, and I'm
flagging it rather than quietly dropping it. Both are **stateful sequential machines running the
identical transition graph** — `state_identity.py:69-79` `VALID_TRANSITIONS` ≡
`market_crt_states.yaml:237-246`; the resolver carries `CRTStateMemory` (:100-128) and enforces
`_apply_transition_validity` (:882-931) exactly as `crt_engine_v2._transition()` (:980-990) does.
Totals match exactly (47,197 both) → pure redistribution.

| State | BacktestRunner | CRTStateResolver | Mechanism |
|---|---|---|---|
| SHADOW_PENDING | 51 | **271** | `_force_range_reset(kind="htf")` (:429-440) arms `pending_displacement_active` on every DISPLACEMENT; `htf_candles_per_range:4` < `max_displacement_age_candles:3`+1 ⇒ ~every DISPLACEMENT dies on an HTF boundary → 1:1 with DISPLACEMENT (271 = 271 exactly). Engine gates shadow on a real confirming sweep → 51. |
| EXECUTION | 5 | **0** | `_continuous_gates_pass` (:690-694) requires `raw["score"\|"risk_score"\|"crt_score"]`; `feature_schema` has none of those ⇒ `score is None` → fail-closed. **Documented as expected** at `market_crt_states.yaml:33-36`. |
| RANGE / EXPANSION | 35,159 / 4,605 | **39,705 / 698** | ⚠️ **Genuine defect in the runner:** `run_crt_state_on_mt5_xauusd.py:118` calls `resolve()` **without `htf_id`**, so the internal HTF counter restarts at 0 on the post-warmup slice and drifts out of phase. `build_htf_id_timeline()` (:1082-1126) exists precisely to prevent this and is never called. Unmatched bars fall to RANGE (:651). |

**Not a production bug** ✅ — `grep -rn crt_state_resolver src/` returns only the module itself.
Consumers: 4 research scripts, 2 tests, docs. No live or backtest decision path consumes it. My
earlier "TruthConflict between two authorities" framing was too strong: this is a fidelity gap in
an intentionally-shadow research tool, plus one fixable runner defect.

## A4. NEW defect found — warmup off-by-one, verified empirically ✅

| | |
|---|---|
| Pipeline | `required_warmup_rows()` = 78 → drops raw rows **0–77**; first enriched ts = `2024-05-22 20:30:00` (raw row 78) |
| Replay loop | `candle_idx` is **1-based** (`=0` at :1990, `+=1` at :2117 *before* use); skips while `candle_idx < 78` (:2140) → drops raw rows **0–76** |
| Result | raw row **77** (`2024-05-22 20:15:00`) enters the CRT state machine with **no feature row**. Probe confirmed: `'2024-05-22 20:15:00' in feature_ts_to_idx` → **False** |
| Guard | `:1828` tests `warmup_candles < _pipeline_warmup` → `78 < 78` → False → **does not fire** |
| Arithmetic | loop drops `W−1` rows vs pipeline's `P` ⇒ alignment needs `W = P+1 = 79`, or the loop needs `<=` |

**Severity: low, fails closed.** A `TRADE_OPENED` on that one bar raises `FeatureAlignmentError`
(:2255-2267) — it can crash a run, never silently corrupt a ledger. Did not fire on this run.

---

# PART B — Do the two warnings cause bugs upstairs?

## B1. `normalization_basis=atr_relative` (F-061/F-064) — YES, kills channels ✅

Live-measured, this run: `momentum_score` = **1155.82** on the single trade (`tanh` = **exactly
1.0**); `ema_spread` = **−474.22**. Corpus: momentum −26,421→+25,226, ema_spread −9,370→+12,110.
`atr` = 0.00093 (correct ratio) — proving these two are the dimensional outliers, not the norm.

| Consumer | Code | Effect at live scale | Reached in **this backtest**? |
|---|---|---|---|
| `engine_runner.py:160-164` `detect_regime` | `ema_spread_abs >= 0.15 and momentum >= 0.3` | **constant `"trend"`** | ✅ YES (gate was ON) |
| `engine_runner.py:176-179` `breakout_engine` | `score = min(1.0,(spread+momentum)/2)`; `if score < 0.3: direction = 0` | **score pinned 1.0**, min-score veto unreachable | ✅ YES |
| `fusion_engine.py:115,164-168` | regime → `_REGIME_NORM["trend"]="TRENDING"` | **TRENDING weight profile permanently selected**; RANGING/VOLATILE unreachable | ✅ YES |
| `heuristic_gaussian_engine.py:358-360` | `tanh(momentum)`; `x=(ema_diff+momentum_norm)/2` | tanh=±1 swamps ema_diff (~1e-3) → gaussian ≈ 2-valued on `sign(momentum)` | ✅ YES |
| `gate_intelligence.py:235-237` REVERSAL | `1.0 - min(1.0, abs(mom))` | **exactly 0.0, always** | ❌ live-only |
| `s08_ml_ensemble.py:207,213` | `w_mom(0.25) × min(abs(mom),1.0)` | constant **+0.25 offset**, not signal | ❌ strategies |
| `s03/s04/s06/s07/s09` thresholds | `>0.3`, `0.6`, `0.5`, `−0.2` | degenerate to **pure sign tests** | ❌ strategies |
| `crt_gaussian_scorer.py` | — | does **not** consume either | n/a |

**Scoping correction I had to make** ✅ — `ExecutionPlannerV1_2` is constructed **only** at
`live_engine_hook.py:877`; `backtest_v2` never builds it (it only reads `execution_planner` config
values for exit simulation). So the whole `GateIntelligence` column is **live-path only** and was
**not** exercised by the run I did. A sub-agent presented these as one undifferentiated blast
radius; they are two different surfaces.

### The REVERSAL knife-edge — a sub-agent claim I corrected ✅

An agent concluded REVERSAL is "systematically rejected," citing max `0.20+0.20+0.25 = 0.65`
against threshold `0.55`. That arithmetic **refutes** its own conclusion (0.65 ≥ 0.55 → *passes*).
Verified weights from config (`gate_intelligence`): intent 0.35 / vol 0.20 / liq 0.20 / struct
0.25, threshold 0.55, `approved = final >= threshold` (:176).

The real result comes from **two defects compounding**:
- F-061 saturation ⇒ `s_i = 0.0` (kills the 0.35 intent weight)
- F-065 ⇒ `vol_score` structurally 0.0 (`volume_ma20` never emitted, :272-284) ⇒ `_liquidity_score
  = 0.5*sweep_score`, **capped at 0.5**

⇒ REVERSAL ceiling `= 0.35(0) + 0.20(1.0) + 0.20(0.5) + 0.25(1.0) = ` **exactly 0.55** = the
threshold. So REVERSAL is not impossible — it is a **measure-zero knife-edge** requiring perfect
vol AND perfect sweep AND perfect structure simultaneously. Neither defect alone does this
(without F-065 the ceiling is 0.65, comfortably passable). **This interaction is in neither
finding** — it is new.

⚠️ **Unverified, potentially decisive:** `_vol_score` (:250-257) computes `r = (high−low)/atr`. If
the live features dict carries `atr` as the **relative** value (0.00093) while `high`/`low` are raw
prices, then `r ≈ 2269` → `score = 1−(r−1)/2` → clamped **0.0**, dropping the REVERSAL ceiling to
0.35 and making it genuinely **impossible**. The trades.csv carries *both* `atr`=0.00093 and
`live_atr`=2.167, so both are plausible. **I did not verify which dict `live_engine_hook` passes.**
This is the same dimensional-mix class as the known SL/TP ATR issue. Resolving it is the single
highest-value follow-up in this report.

## B2. `session_timestamp_basis=broker_local` (F-066) — YES, and the advertised fix is incomplete ✅

**New finding: two different session-window sets exist and disagree** ✅

| Surface | Config key | Windows | Format |
|---|---|---|---|
| **Trade filter** (gating) | `crt_engine.session_windows` | LONDON 07:00–10:00, NEWYORK 13:00–16:00, ASIA 00:00–03:00 | strings |
| **Feature labeler** | `feature_pipeline.session_windows_utc` | ASIA [0,9], LONDON [7,16], NEWYORK [12,21] | int hours |

The labeler's windows **overlap** (LONDON [7,16] ∩ NEWYORK [12,21] = 12–16), so the emitted label
depends on iteration order — a defect independent of any timezone question. The filter
(`crt_engine_v2.py:3095-3098`) also `break`s on first match, same order-sensitivity.

**The decisive point** ✅ — the trade-gating filter at `crt_engine_v2.py:3093` reads
`candle.timestamp.time()`, i.e. the **raw candle timestamp**, *not* the FM-052 `session` feature.
Therefore **flipping `session_timestamp_basis` to `utc_corrected` fixes the feature and leaves the
gating filter untouched.** The warning text advertises `utc_corrected` as "the correction path"
without noting it does not reach the surface that actually blocks trades.

Evidence from this run: the sole trade opened at broker `15:00` 2024-06-17 (June ⇒ EEST ⇒ true UTC
≈ 12:00), labeled `session=3.0`/NEWYORK, and the summary reports `best_hour_utc: 15` — a field
named UTC holding broker time. On the same row `cached_session` = **UNKNOWN** while the pipeline
says NEWYORK — the engine's own cached session never resolved.

⚠️ **Deliberately not claimed:** whether this *mis-gates*. F-066 records that
`crt_engine.session_windows` was **empirically tuned on broker time**, so filter-and-data may be
self-consistent and the defect purely semantic (the window named "NEWYORK" denotes ≈10:00–13:00
UTC, which is London afternoon). Determining whether the windows were fit to broker or UTC time is
an economic question, not a code question — it needs your call, not a grep.

### Verdicts

| Defect | Kills a channel? | Changes which trades are taken? | Reached in this backtest? |
|---|---|---|---|
| F-061/F-064 saturation | **Yes** — regime discrimination, breakout veto, REVERSAL intent, gaussian reduced to sign | **Yes on the live path** (REVERSAL knife-edge); on the backtest path it freezes fusion into the TRENDING profile | ✅ partially (engine_runner/fusion yes; gate_intelligence no) |
| F-066 session basis | Feature is model-contaminating | ⚠️ filter reads raw timestamp — self-consistency undetermined | filter ✅ active; feature ✅ emitted |

### Silent fusion-weight losses ✅
`fusion_engine` weight profile frozen to TRENDING · `gate_intelligence` `w_intent=0.35 × 0.0` for
REVERSAL · `s08` `w_mom=0.25 × 1.0` = constant offset · `_liquidity_score` permanently halved.
Each is a weight applied to a constant — arithmetically a bias term, not a signal.

---

# Recommended next actions (none taken — read-only report)

1. **Resolve the `_vol_score` ATR dimension** (⚠️ above). Decides whether REVERSAL is knife-edge or
   structurally dead. One probe of the live features dict settles it.
2. **Fix the warmup off-by-one** — `:1828` guard `<` → `<=`, or loop `<` → `<=`. One line, testable.
3. **Fix the `htf_id` phase-lock** in `run_crt_state_on_mt5_xauusd.py:118` — call the existing
   `build_htf_id_timeline()`. Makes the research census trustworthy.
4. **Decide the session question** (yours): were `crt_engine.session_windows` fit to broker or UTC
   time? Then either relabel or re-tune. Also de-overlap `session_windows_utc`.
5. **Correct the F-066 warning text** to state that `utc_corrected` does not reach the trade filter.

None of this grants promotion authority (§6.5) — all descriptive.
