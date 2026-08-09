# Topic: Model Intent & Feature Ownership

> **Topic-visibility unit.** One concept, narrated in human language, kept in sync with the
> code on every working response (`CLAUDE.md §6.1`). Read this to understand *which model owns
> which of the 38 canonical features and why* — **without loading the rest of the codebase**.
> This is the **canonical authority** the feature-expansion program (plan
> `d-tradelatest-reports-ohlcv-lineage…`) defers to. Link, don't inline.
>
> Created: 2026-06-27 · Updated: 2026-07-28 · Status: living
>
> **Intent authority (higher than this topic for *why* engines exist):**  
> [`docs/governance/MODEL_INTENT_AUTHORITY_REGISTER.md`](../governance/MODEL_INTENT_AUTHORITY_REGISTER.md)
> (MIAR) + [`miar_registry.json`](../governance/miar_registry.json). Hierarchy: Ontology →
> Feature Pipeline → **MIAR** → Implementations → Backtest/Research. This topic remains the
> **feature×model ownership matrix** authority; on pure intent conflict, MIAR wins.
>
> **Related (architecture design, not ownership matrix):** EnvelopeNet —
> [`docs/architecture/envelope-layer-design.md`](../architecture/envelope-layer-design.md) —
> last pre-Fusion predictive layer (operating bounds). Owns none of the 38 features exclusively
> at design freeze; planned v1 inputs = full canonical vector + CRT/context metadata.

## In plain language

The system scores each candle through four fused engines (CRT, Gaussian, ZoneGate, RR) plus a
BitNet hard-reject gate and a regime/dual-engine layer. A recurring question (raised by
`reports/OHLCV_LINEAGE_FORENSICS.md` + `reports/FEATURE_REACHABILITY_AUDIT.md`) is whether the
~20 canonical features only consumed by ZoneGate are "dead." This topic answers the **prior**
question instead: *what was each model designed to own, and why does it deliberately ignore the
rest?* The governing principle is **three separate questions** — (A) intended ownership, (B)
marginal value to an individual model, (C) ensemble-uniqueness value — and the rule that
**specialization is diversification capital**: a model legitimately ignores a feature when it
serves a different horizon, an independent vote, ensemble diversity, or a structural filter
rather than prediction. No feature is deleted; reclassification is documentation only.

## Code covered

- [`src/config_layer/crt_engine_v2.py`](../../src/config_layer/crt_engine_v2.py) — `UltronRiskEngine.compute_score` (~:1604), `compute_soft_confirmation` (~:1639) — structural state machine; raw Candle + internal EMA(2,5) (~:292) + internal ATR(14) (~:1002).
- [`src/engines/heuristic_gaussian_engine.py:305`](../../src/engines/heuristic_gaussian_engine.py) — `HeuristicGaussianEngine.compute` — directional-momentum Gaussian on 3 features.
- [`src/engines/rr_engine.py:45`](../../src/engines/rr_engine.py) — `RREngine` — candle-polarity index on close/high/low; `min_rr` retained-but-unused (:43).
- [`src/engines/zone_gate_engine.py:163`](../../src/engines/zone_gate_engine.py) — `filter_canonical_inputs` / `_extract_vector` — requires all 38 canonical keys; fail-open to 0.5/pass on registry error (:230).
- [`src/engines/live_engine.py:202`](../../src/engines/live_engine.py) — `BitNetZoneGate.check` — per-zone weighted-Gaussian over the 38-vector.
- [`src/bitnet/zone_cosine_searcher.py:222`](../../src/bitnet/zone_cosine_searcher.py) — `compute_gaussian_score` — `score = Σ w_k·exp(-½((x_k-µ_k)/σ_k)²) / Σ w_k`.
- [`src/bitnet/bitnet_inference.py:317`](../../src/bitnet/bitnet_inference.py) — `bitnet_score` — 6-feature hard-reject gate (off by default).
- [`src/core/engine_runner.py:144`](../../src/core/engine_runner.py) — `detect_regime` / `breakout_engine` / `trap_engine` (:159/:183) — 3 features each → regime-adaptive fusion weights.
- [`src/core/fusion_engine.py`](../../src/core/fusion_engine.py) — `FusionEngine` — regime-weighted blend of the 4 engine scores; not feature-driven.

## Ins / Outs

- **Ins:** the 38-dim `CANONICAL_FEATURES` vector ([`src/features/feature_schema.py:46`](../../src/features/feature_schema.py)); raw `Candle` (OHLCV) for CRT; config sections `engine_runner.*` (incl. `zone_registry_path`, `zone_mode`) and `fusion_engine.*`.
- **Outs:** per-engine scores → `FusionEngine` final score → `DecisionEngine` ACCEPT/REJECT/BLOCK.

## Per-model intent (Question A — verified)

| Model | Purpose / phenomenon | Features it OWNS (read explicitly) | Why it ignores the rest |
|---|---|---|---|
| **CRT** | Structural state machine (range→sweep→disp→retest→exec) | body_ratio, disp_strength, retest_depth, atr, candles_since_retest, sweep_detected, double_sweep (+ raw OHLC, internal EMA(2,5), internal ATR(14)) | Self-contained state machine; uses its *own* EMA(2,5)/ATR — canonical momentum/volatility would be redundant/conflicting. **KEEP SPECIALIZED.** |
| **Gaussian** | Directional-momentum Gaussian match | ema_fast, ema_slow, momentum_score | Designed as a narrow momentum vote (independent of CRT structure). **Expansion candidate (B).** |
| **RR** | Candle-polarity (directional commitment) index | close, high, low | Structural-geometry filter, not a predictor; volatility/momentum out of scope by design. **KEEP SPECIALIZED.** |
| **ZoneGate** | Full-vector zone/pattern similarity (weighted-Gaussian) | ALL 38 (per-zone ~25 active, ~13 `zero_indices`) | None excluded by contract; per-zone masking is learned, not designed. |
| **BitNet** | 6-feature hard-reject gate (score<0.55) | body_ratio, retest_depth, disp_strength, atr, candles_since_retest, double_sweep | Deliberately compact gate; off by default. **Expansion candidate (B).** |
| **Regime/Dual** | Regime classify + breakout/trap → fusion weights | ema_spread, momentum_score, volatility_ratio, trend_bias, sweep_detected, disp_strength | 3-feature voters by design; diversity vs the engines. **Expansion candidate (B).** |
| **Fusion** | Regime-weighted blend of 4 scores | (engine scores, not features) | Meta-layer; not feature-driven. |

## Feature × Model Ownership Matrix (Question A done; B/C pending Phase 3–4)

Legend — **REQ·A** required by intent · **SPEC·A** intentionally excluded (keep specialized) ·
**ALL·A** consumed via the full-vector contract · **CAND·B** expansion candidate, value
*evidence-pending* (Phase 3 importance / Phase 4 decision-flip + correlation) · **n/a** meta-layer.
ZoneGate column is **ALL·A** for every feature (38-key contract) and omitted per-row for brevity.

| # | Feature | CRT | Gaussian | RR | BitNet | Regime/Dual |
|---|---|---|---|---|---|---|
| 0 | open | SPEC·A | CAND·B | SPEC·A | CAND·B | CAND·B |
| 1 | high | REQ·A* | CAND·B | REQ·A | CAND·B | CAND·B |
| 2 | low | REQ·A* | CAND·B | REQ·A | CAND·B | CAND·B |
| 3 | close | REQ·A* | CAND·B | REQ·A | CAND·B | CAND·B |
| 4 | volume | SPEC·A | CAND·B | SPEC·A | CAND·B | CAND·B |
| 5 | volume_ratio | SPEC·A | CAND·B | SPEC·A | CAND·B | CAND·B |
| 6 | double_sweep | REQ·A | CAND·B | SPEC·A | REQ·A | CAND·B |
| 7 | ema_fast | (internal 2,5) | REQ·A | SPEC·A | CAND·B | CAND·B |
| 8 | ema_slow | (internal 2,5) | REQ·A | SPEC·A | CAND·B | CAND·B |
| 9 | ema_spread | SPEC·A | CAND·B | SPEC·A | CAND·B | REQ·A |
| 10 | trend_bias | SPEC·A | CAND·B | SPEC·A | CAND·B | REQ·A |
| 11 | trend_strength | SPEC·A | CAND·B | SPEC·A | CAND·B | CAND·B |
| 12 | momentum_score | SPEC·A | REQ·A | SPEC·A | CAND·B | REQ·A |
| 13 | atr | REQ·A | CAND·B | SPEC·A | REQ·A | CAND·B |
| 14 | volatility_ratio | SPEC·A | CAND·B | SPEC·A | CAND·B | REQ·A |
| 15 | rsi_14 | SPEC·A | CAND·B | SPEC·A | CAND·B | CAND·B |
| 16 | macd_line | SPEC·A | CAND·B | SPEC·A | CAND·B | CAND·B |
| 17 | macd_signal | SPEC·A | CAND·B | SPEC·A | CAND·B | CAND·B |
| 18 | macd_hist | SPEC·A | CAND·B | SPEC·A | CAND·B | CAND·B |
| 19 | sweep_detected | REQ·A | CAND·B | SPEC·A | CAND·B | REQ·A |
| 20 | liquidity_sweep | (→double_sweep) | CAND·B | SPEC·A | CAND·B | CAND·B |
| 21 | break_of_structure | SPEC·A | CAND·B | SPEC·A | CAND·B | CAND·B |
| 22 | swing_high | SPEC·A | CAND·B | SPEC·A | CAND·B | CAND·B |
| 23 | swing_low | SPEC·A | CAND·B | SPEC·A | CAND·B | CAND·B |
| 24 | higher_high | SPEC·A | CAND·B | SPEC·A | CAND·B | CAND·B |
| 25 | lower_low | SPEC·A | CAND·B | SPEC·A | CAND·B | CAND·B |
| 26 | body_size | (→body_ratio) | CAND·B | SPEC·A | CAND·B | CAND·B |
| 27 | wick_size | (→body_ratio) | CAND·B | SPEC·A | CAND·B | CAND·B |
| 28 | body_ratio | REQ·A | CAND·B | SPEC·A | REQ·A | CAND·B |
| 29 | volatility_regime | SPEC·A | CAND·B | SPEC·A | CAND·B | CAND·B |
| 30 | session | REQ·A (gating) | CAND·B | SPEC·A | CAND·B | CAND·B |
| 31 | hour_of_day | SPEC·A | CAND·B | SPEC·A | CAND·B | CAND·B |
| 32 | disp_strength | REQ·A | CAND·B | SPEC·A | REQ·A | REQ·A |
| 33 | retest_depth | REQ·A | CAND·B | SPEC·A | REQ·A | CAND·B |
| 34 | candles_since_retest | REQ·A | CAND·B | SPEC·A | REQ·A | CAND·B |
| 35 | liquidity_distance | SPEC·A | CAND·B | SPEC·A | CAND·B | CAND·B |
| 36 | liquidity_pressure_score | SPEC·A | CAND·B | SPEC·A | CAND·B | CAND·B |
| 37 | volume_spike | SPEC·A | CAND·B | SPEC·A | CAND·B | CAND·B |

\* CRT reads raw OHLC from the `Candle` object, not the canonical dict. `(internal 2,5)` = CRT
computes its own EMA(2,5); the canonical ema_fast/slow are EMA(9,21) and feed Gaussian — a
deliberate horizon split, **not** a collision. `(→x)` = consumed only as an intermediate for `x`.

> **No expansion is admitted on this matrix alone.** A `CAND·B` cell becomes REQ/BEN only if it
> clears the Net-Contribution rule (A ∧ B ∧ C ∧ M4 ∧ ΔG001>0; else KEEP SPECIALIZED) — see the plan.

## Feature Lineage Matrix (OHLCV → Formula → State → consumers → fusion weight)

The ownership matrix above answers *designed-to-read*. This one answers the orthogonal, fully
source-verifiable question: **where does each of the 38 features come from (formula over OHLCV), which
CRT state caches it, which engines consume it, and what fusion weight carries its influence** — every
cell file:line-cited. **Branch-scoped to the active config `v2_multi_2026_04`** (§4.0/§6.2 r7).

**Runtime scoping (active config):** live Gaussian = 3-feat heuristic (`gaussian_impl:heuristic`);
`rr_fusion.enabled:false` → RR = base geometric candle-polarity on close/high/low; `use_bitnet:false`
→ the BitNet 6-feat gate never fires; ZoneGate consumes the full 38-vector but is NON_PIVOTAL (F-036)
/ geometric (F-041). **Fusion weights** (config `fusion_engine`): crt **0.4** · gaussian **0.2** · zone
**0.2** · rr **0.2**; blend = weighted-sum / total_w with dead-engine exclusion + optional convergence
penalty ([fusion_engine.py:490](../../src/core/fusion_engine.py)). Regime-adaptive weight profiles exist
in code ([fusion_engine.py:164](../../src/core/fusion_engine.py)) but are **not** config-driven and only
apply when a `regime=` arg is passed. **The 4-engine fusion is OFF in research backtests (F-037,
`BACKTEST_ENGINE_GATE=0`) — these weights are LIVE-path only.**

Legend: **Fusion wt** = weight of the governing (highest-authority) consumer. `Zone✓` = in the 38-key
contract but non-pivotal (nominal 0.2 / effective ΔG001≡0, F-036). Provenance line = `feature_pipeline.py`
unless noted. `ts` = derived from timestamp, not OHLCV.

| # | Feature | OHLCV | Formula | State | CRT | Gau | Zone | RR | Fusion wt |
|---|---|---|---|---|---|---|---|---|---|
| 0 | open | o | RAW | — | ✓ body_size | — | ✓ | — | **CRT 0.4** |
| 1 | high | h | RAW | — | ✓ sweep/wick | — | ✓ | ✓ polarity | **CRT 0.4** |
| 2 | low | l | RAW | — | ✓ sweep/wick | — | ✓ | ✓ polarity | **CRT 0.4** |
| 3 | close | c | RAW | — | ✓ sweep/retest/disp | — | ✓ | ✓ polarity | **CRT 0.4** |
| 4 | volume | v | RAW | — | — | — | ✓ | — | 0.2 Zone (n-p) |
| 5 | volume_ratio | v | vol/vol_ma20 (FX range proxy) `:202` | — | — | — | ✓ | — | 0.2 Zone (n-p) |
| 6 | double_sweep | h,l,c | both ±liquidity_sweep in 5-bar win `:537` | **RETEST** | ✓ soft sweep-bonus | — | ✓ | — | **CRT 0.4** |
| 7 | ema_fast | c | EWM(close, 9) `:486` | — | (CRT uses own EMA 2,5) | ✓ | ✓ | — | **Gau 0.2** |
| 8 | ema_slow | c | EWM(close, 21) `:487` | — | — | ✓ | ✓ | — | **Gau 0.2** |
| 9 | ema_spread | c | (ema_fast−ema_slow)/atr `:491` | — | — | — | ✓ | — | Regime→wts |
| 10 | trend_bias | c | sign(ema_fast−ema_slow) `:506` | — | — | — | ✓ | — | Regime→wts |
| 11 | trend_strength | c | rollmean(slope(ma20),10) `:296` | — | — | — | ✓ | — | 0.2 Zone (n-p) |
| 12 | momentum_score | c | close.diff()/atr `:497` | — | ✓ intent-class | ✓ | ✓ | — | **Gau 0.2** |
| 13 | atr | h,l,c | ATR(14)/close `:462` | **+BitNet** | ✓ disp/retest/SL·TP | — | ✓ | — | **CRT 0.4** |
| 14 | volatility_ratio | h,l,c | (h−l)/(atr·c) `:476` | — | — | — | ✓ | — | Regime→wts |
| 15 | rsi_14 | c | Wilder 100−100/(1+RS) `:251` | — | — | — | ✓ | — | 0.2 Zone (n-p) |
| 16 | macd_line | c | EMA12−EMA26 `:281` | — | — | — | ✓ | — | 0.2 Zone (n-p) |
| 17 | macd_signal | c | EMA9(macd_line) `:282` | — | — | — | ✓ | — | 0.2 Zone (n-p) |
| 18 | macd_hist | c | macd_line−macd_signal `:283` | — | — | — | ✓ | — | 0.2 Zone (n-p) |
| 19 | sweep_detected | h,l,c | 1 if liquidity_sweep≠0 `:515` | — | — | — | ✓ | — | Regime→wts |
| 20 | liquidity_sweep | h,l,c | ±1 close vs ref swing `:409` | — | (→double_sweep) | — | ✓ | — | 0.2 Zone (n-p) |
| 21 | break_of_structure | c | ±1 close vs ref swing `:404` | — | (→liq_distance) | — | ✓ | — | 0.2 Zone (n-p) |
| 22 | swing_high | h | high==rollmax(5,center) `:362` (F-029 benign) | — | — | — | ✓ | — | 0.2 Zone (n-p) |
| 23 | swing_low | l | low==rollmin(5,center) `:364` | — | — | — | ✓ | — | 0.2 Zone (n-p) |
| 24 | higher_high | h | high>last_swing_high.shift(1) `:393` | — | — | — | ✓ | — | 0.2 Zone (n-p) |
| 25 | lower_low | l | low<last_swing_low.shift(1) `:395` | — | — | — | ✓ | — | 0.2 Zone (n-p) |
| 26 | body_size | o,c | abs(close−open) `:443` = `candle_math.body_size` | — | ✓ →body_ratio | — | ✓ | — | **CRT 0.4** |
| 27 | wick_size | h,l | **high−low** `:444` = `candle_math.candle_range` | — | ✓ →body_ratio/disp | — | ✓ | — | **CRT 0.4** |
| 28 | body_ratio | o,h,l,c | body_size/candle_range `:446` = `candle_math.body_ratio` | **RETEST** | ✓ disp gate ≥0.70 | — | ✓ | — | **CRT 0.4** |
| 29 | volatility_regime | h,l,c | ATR-pctile buckets {0,1,2} `:303` | — | — | — | ✓ | — | 0.2 Zone (n-p) |
| 30 | session | ts | hour buckets Asia/Ldn/NY `:341` | **RETEST** | ✓ session filter (lever) | — | ✓ | — | **CRT 0.4** |
| 31 | hour_of_day | ts | timestamp.hour `:338` | — | — | — | ✓ | — | 0.2 Zone (n-p) |
| 32 | disp_strength | h,l,c | body_size/(atr·c) clip[0,3] `:559` | **RETEST** | ✓ disp ceiling | — | ✓ | — | **CRT 0.4** |
| 33 | retest_depth | c | \|close−ema_fast\|/(atr·c) clip[0,1] `:573` | **RETEST** | ✓ retest gate | — | ✓ | — | **CRT 0.4** |
| 34 | candles_since_retest | — | bars since last sweep `:588` | **+BitNet** | (BitNet-only → OFF) | — | ✓ | — | 0 inert (→BitNet if on) |
| 35 | liquidity_distance | h,l,c | min dist→ref/BOS /atr `:599` | — | — | — | ✓ | — | 0.2 Zone (n-p) |
| 36 | liquidity_pressure_score | h,l,c | exp(−0.5·liq_distance) `:648` | — | — | — | ✓ | — | 0.2 Zone (n-p) |
| 37 | volume_spike | v | vol_ratio>rolling-75pctile(50) `:654` | — | — | — | ✓ | — | 0.2 Zone (n-p) |

**Reads:** 12 features route through the only pivotal live weight (**CRT 0.4**) — **11 drive CRT hard
gates (structural)** + `double_sweep` a soft confirmation bonus (advisory) · 3 add **Gaussian 0.2**
(advisory) · 4 route regime weight-selection (advisory) · ~19 reach the decision only via the
non-pivotal ZoneGate contract (effective ≈0, F-036) or are inert (`candles_since_retest`, BitNet off).
This *is* the structural/advisory/unused split: **11 structural · 8 advisory · 19 unused** — the
`role` field in the `feature_lineage` block of [`active_models.yaml`](../../active_models.yaml).

**State caching** ([crt_engine_v2.py:1383](../../src/config_layer/crt_engine_v2.py)): `{retest_depth,
body_ratio, disp_strength, retest_index, session, double_sweep}` cached at RETEST; `atr` +
`candles_since_retest` added at the (off) BitNet layer.

### `wick_size` / `body_ratio` reconciliation (worked proof)

Building this lineage surfaced that `wick_size` had divergent definitions. **Verified resolution
(2026-07-05):** it is **two** definitions, not three — the CRT engine `Candle` property
([crt_engine_v2.py:105](../../src/config_layer/crt_engine_v2.py)) and the batch pipeline
([feature_pipeline.py:444](../../src/features/feature_pipeline.py)) **agree** (`wick_size = high−low`,
`body_ratio = body/range`); the only outlier was the single-row `crt_feature_builder.py` (`body/total_wick`,
unbounded), which has **zero call sites** (dead code). Canonical = **`body/range`** (bounded [0,1] — the
only metric the `0.70` displacement gate is coherent against). Worked example `O100/H110/L95/C108`:

| Path | `wick_size` | `body_ratio` | Status |
|---|---|---|---|
| CRT `Candle` property | 15 (high−low) | 8/15 = **0.533** | canonical |
| batch pipeline | 15 (high−low) | 8/15 = **0.533** | canonical (≡ CRT) |
| single-row builder (was) | 7 (total_wick) | 8/7 = 1.143 | **bug — dead, now corrected** |

All three now route through [`src/features/candle_math.py`](../../src/features/candle_math.py) (immutable
scalar primitives; the batch pipeline is bound by [`tests/test_candle_math.py`](../../tests/test_candle_math.py)),
so divergence is structurally impossible. Zero runtime impact (CRT+pipeline were already canonical; the
outlier was uncalled and the live BitNet path reads the canonical cached `disp.body_ratio`).

### Ontology as the authoritative feature-math source + ownership enforcement (F-047, 2026-07-07)

The WHAT layer now governs **two** layers — geometry primitives **and** deterministic normalized
metrics — with mechanical enforcement, not just declaration. Authority chain (registry is
authoritative, ontology descriptive):
**Ontology** ([`market_ontology.yaml`](../../configs/formulas/market_ontology.yaml): `derived_metrics`
with stable IDs `FM-0NN` / per-feature `version` / `lifecycle` / `depends_on` DAG / `source_of_truth`)
→ **Registry** ([`src/features/registry/`](../../src/features/registry/) package behind the stable
[`formula_registry`](../../src/features/formula_registry.py) facade) → **Implementations**
([`derived_math.py`](../../src/features/derived_math.py) scalars, transcribed verbatim from the pipeline;
never `eval`'d) → **Consumers** (read the registry).

| Metric | ID | lifecycle | canonical formula | `depends_on` |
|---|---|---|---|---|
| disp_strength | FM-020 | parity_verified | `clip(body_size/(atr·close), 0, 3)` | body_size, atr, close |
| retest_depth | FM-021 | parity_verified | `clip(|close−ema_fast|/(atr·close), 0, 1)` | close, ema_fast, atr |
| ema_spread | FM-022 | parity_verified | `(ema_fast−ema_slow)/atr` ⚠ price-scaled | ema_fast, ema_slow, atr |
| momentum_score | FM-023 | parity_verified | `close_delta/atr` ⚠ price-scaled | close_delta, atr |
| volatility_ratio | FM-024 | parity_verified | `(high−low)/(atr·close)` | candle_range, atr, close |
| liquidity_distance | FM-025 | registered | `min|close−level|/(atr·close)` | close, atr, ref_high/low, bos |
| liquidity_pressure_score | FM-026 | registered | `clip(exp(−0.5·dist), 0, 1)` | liquidity_distance |
| displacement_retrace | FM-027 | registered | `clip(\|retest_close−disp_open\|/\|disp_close−disp_open\|, 0, 1)` | retest/disp candles |
| displacement_atr_ratio | FM-028 | registered | `candle_range/atr` | candle_range, atr |
| disp_strength_atr_rescale | FM-029 | registered | `disp_strength/atr` (scoring_engine as-wired input) | disp_strength, atr |
| ema_spread_atr | FM-030 | parity_verified · **`active: false`** | `(ema_fast−ema_slow)/(atr·close)` — scale-invariant correction of FM-022 | ema_fast, ema_slow, atr, close |
| momentum_score_atr | FM-031 | parity_verified · **`active: false`** | `close_delta/(atr·close)` — scale-invariant correction of FM-023 | close_delta, atr, close |

⚠ **FM-022/FM-023 are price-scaled (F-061).** Their numerator is absolute price and `atr` is
close-relative, so `legacy ≡ corrected × close` and the emitted magnitude is the instrument's price
level. On crypto this makes the `engine_runner.dual_engine` thresholds **inert**: `detect_regime`
returns `"trend"` on 98.9% (BNB) / 99.9% (BTC) of bars, `breakout_engine`'s score is pinned at 1.0
on ~100%, `tanh(momentum_score)` saturates (F-060), and `gate_intelligence`'s REVERSAL score
collapses to 0.0. FM-030/031 fix this and are **registered but inactive** — selected by
`feature_pipeline.normalization_basis` (`atr_relative` default = the legacy math, byte-identical;
`atr_absolute` = the corrected pair, reachable only via the non-promoted shadow config). Activation
needs demonstrated ΔG001 **plus** threshold recalibration; registration grants no authority (§6.5).

Three enforcement layers: **parity** ([`tests/test_derived_math.py`](../../tests/test_derived_math.py))
binds the vectorized pipeline columns to the scalar registry; an **ownership-lint**
([`scripts/analysis/feature_math_lint.py`](../../scripts/analysis/feature_math_lint.py) —
semantics-not-syntax: an assignment to a registered name whose RHS is not a registry call is a
violation; dict-reads / clamps / coercions are transport-exempt) fails on any NEW re-derivation; and a
**lineage exhaustiveness** invariant ([`tests/test_feature_lineage.py`](../../tests/test_feature_lineage.py))
proves Feature→registry→impl→parity→vector with an acyclic OHLC-grounded graph.
The census pinned **10 pre-existing divergences** (grandfathered) — load-bearing: `live_engine_hook.py:361`
computes NON-CANONICAL `body_ratio` (body/total_wick, the research-only `wick_based` variant), fix deferred
to Phase B. `crt_engine_v2.py:2539` routed through canonical (parity-neutral). Boundary FROZEN here:
rolling indicators (RSI/MACD/ATR) and stateful detection (sweep/BOS) are algorithms, out of this layer.

## Demonstrated-Edge Matrix (designed vs implemented vs measured alpha)

Question A (above) answers *what each model was designed to own*. This matrix answers the orthogonal
question — *what the evidence says each model actually contributes* — separating **designed alpha**
(target) from **implemented alpha** (runtime) from **measured alpha** (findings). It records
evidence only; per the §6.5 Authority Ladder it **grants no authority** and reverses no finding.

**Edge-state vocabulary** (uncertainty preserved — "no evidence yet" ≠ "evidence of no edge"):
`NONE` (measured, no edge) · `NEGATIVE` (measured, adverse) · `UNMEASURED` (never tested vs G001/M4)
· `UNKNOWN` (semantics/labels not documented) · `POSITIVE` (demonstrated ΔG001>0) · qualifiers
`NON_PIVOTAL` (ΔG001≈0) / `SESSION_FILTER_ONLY` are notes, not verdicts.

| Model | Target (designed) | Training labels | Runtime usage | Findings | Demonstrated edge |
|---|---|---|---|---|---|
| CRT spine | state classification | none (rule-based) | active spine | F-019/F-020/F-021/F-037 | `NONE` (SESSION_FILTER_ONLY) |
| Gaussian (live) | directional_momentum_score | none (heuristic) | active, 3-feat | F-005, F-019… | `NONE` |
| Gaussian `v4_mirrored` | corr(expected_rr, pnl_rr) | historical pnl_rr, 242k | **not wired** | — | `UNMEASURED` — corr 0.2066 is Authority-Level-1 *information*, **not** demonstrated edge |
| ZoneGate | zone quality [0,1] | per-zone win/mean_RR (stored ~98% SL-hit = **F-022 artifact**; honest ≈66%, F-041B) | active hard gate | F-036, F-041 | `NONE` (NON_PIVOTAL, ΔG001≡0; labels contaminated + 0/8 honest-positive) |
| RR (base) | candle-polarity index | none (geometric) | active | F-038 | `NONE` (geometric filter — no edge claimed) |
| BitNet | accept/reject | GGUF-trained — labels not documented (`# UNKNOWN`) | dormant (off by default) | F-004 | `UNKNOWN` |
| Fusion / EngineRunner | blended decision | n/a | active live / OFF backtest | F-037, F-038 | `UNMEASURED` (gate effect modest; entry null unaffected) |
| Strategies S1–S10 | consensus signal | n/a | **orphaned** (dormant `fuse_strategy_results`) | — | `N/A` (not in live spine) |

> **E-001 guards.** (a) `corr 0.2066` is L1 information, never "alpha." (b) Undocumented labels stay
> `# UNKNOWN` — not inferred. (c) No cell downgrades a registered finding; if one would, surface a
> `TruthConflict` (§6.2) instead of editing here. The universal entry-information null
> (F-019…F-035, F-040) is why every measured row is `NONE`/`UNMEASURED`, not `POSITIVE`.

## Entry points & validations

- **Reached via:** the live spine `EngineRunner.run()`; research measurement via
  `src/research/` (`forward_walk` + M4 `QualificationGate`). ZoneGate model path is config-driven
  (`engine_runner.zone_registry_path`).
- **Validated by:** Phase 3 static-weight introspection + `edge_attribution_study.py` (importance),
  Phase 4 decision-flip + ensemble-correlation harness, Phase 5 ZoneGate label verification, Phase 7
  G001/M4. Authority is earned only by demonstrated ΔG001 (`CLAUDE.md §6.5`).

## Tests

- [`tests/test_topic_docs.py`](../../tests/test_topic_docs.py) — mechanical doc contract.
- [`tests/test_current_findings.py`](../../tests/test_current_findings.py) — findings ↔ index sync (F-041).
- Phase-specific tests to be added with the Phase 3–4 harnesses.

## Fits in architecture

Sits at the engine-scoring layer of [`docs/architecture/signal-flow.md`](../architecture/signal-flow.md)
(Steps: engine scores → fusion → decision). Complements [`docs/topics/feature-schema.md`](feature-schema.md)
(the 38-dim schema) — this topic adds *ownership/intent* on top of the schema. Truth precedence per
`CLAUDE.md §4.0`.

## Discussion (filled in-session)

> Standing parallel-discussion surface. Append dated entries; never delete — supersede.

- **Risks:** 2026-06-27 — Forcing all models onto the 38-vector risks correlated errors (Question C); guarded by the Net-Contribution rule.
- **Challenges:** 2026-06-27 — ZoneGate runtime model (`models/zone_registry.json`) carries ~98% SL-hit training labels (6/8 zones negative mean_RR) — observation; label-quality root cause is *verified in Phase 5*, not assumed (F-041).
- **Blockers:** 2026-06-27 — none.
- **Ambiguities:** 2026-06-27 — `zone_gate_registry.json` manifest `active:true` points to a *different* file (hash mismatch) than the config-loaded `models/zone_registry.json`; surfaced as a TruthConflict (F-041), not auto-reconciled.
- **Enhancements:** 2026-06-27 — Phase 3/4 will fill the (B)/(C) cells with measured decision-flip + correlation deltas.
- **Need more info:** 2026-06-27 — which exact label/exit scheme produced the stored zone meta (Phase 5).
- **Enhancements:** 2026-07-02 — reconciled [`active_models.yaml`](../../active_models.yaml) (the session-load registry) to this doc's verified engine truth and restructured it into a 3-truth-layer schema (v2.0: `intent | runtime | evidence | status`). Key corrections propagated: live Gaussian = `HeuristicGaussianEngine` (3 feats) not the 38-dim `v4_mirrored` trained model (now under `trained_registry`, active:false); RR = geometric candle-polarity filter (`learning:false`); ZoneGate = full 38-vector contract (not `[atr,rsi,volume,trend]`); S1–S10 flagged orphaned/sidecar; CRT `states: 10→9`; philosophy preserved with `authority:{validated:false}`. All DOC_DRIFT (code-authority); no finding reversed.
- **Enhancements:** 2026-07-02 (batch A1–A3) — added the **Demonstrated-Edge Matrix** section above (designed vs implemented vs measured alpha, controlled edge-state vocabulary, E-001 guards: `corr 0.2066`=L1 info not alpha, BitNet labels `UNKNOWN`). Formalized the four layers as the **Truth-Layer Standard** in [`docs/reference/conventions.md`](../reference/conventions.md) §9 (scoped to knowledge/registry artifacts) + self-declared `meta.truth_schema` in the registry. Grants no authority; every measured row is `NONE`/`UNMEASURED` per the F-019…F-040 entry-null.
- **Challenges/RESOLVED:** 2026-07-05 (F-041B Phase-5) — the "verified in Phase 5" ZoneGate label question (2026-06-27 Challenges entry) is now **answered**: the stored ~98% SL-hit labels are an **F-022 labeling artifact**. `scripts/research/zone_label_audit.py` re-derived all 139,942 source opportunities through `forward_walk(intrabar_fixed)` over the seeded-KMeans membership (`membership_verification=VERIFIED`; all 8 zones reproduce stored n+mean_rr+sl_hit to 4dp → contamination isolated from re-partition drift). Honest SL≈0.66 (Δ≈−0.33 ∀zone; zones 4/5/6 sign-flip); **0/8 zones clear honest E>0** (bootstrap CI all <0) → label-quality is NOT the rescuable defect, binding constraint stays the entry-info null (extends F-025/F-036; honest win≈0.34 re-confirms F-023). Artifact `docs/analysis/f041b-zone-label-audit-BNBUSDT.json`.
- **Ambiguities/RESOLVED:** 2026-07-05 — the manifest TruthConflict (2026-06-27 Ambiguities entry) is **reconciled** (**F-041A**, B1, user-approved §6.2): registered+promoted `v2_gaussian_runtime_2026_07` so `zone_gate_registry.json.active` `model_file = models/zone_registry.json` (sha `e73e0893` == config-loaded); behavior-/hash-neutral. Permanent invariant `tests/test_zone_manifest_runtime_parity.py` now enforces manifest.active-sha == runtime-sha. Separate measured fact: runtime Gaussian *argmax* assignment agrees with the label partition only **41.4%**. — **2026-07-22 RESOLVED + CORRECTED.** The old gloss ("the live gate partitions differently than the labels describe") asserted something the code does not do. **The runtime SCORES; it never PARTITIONS**: the live decision is `top_scores` -> `compute_weighted_cluster_score` -> `>= zone_cluster_threshold` -> pass/block, and no record is assigned to a zone (`best_zone_id` is telemetry with no consumer). So assignment parity measures a partitioning the runtime does not perform. It is low for a mechanical reason: the 13 dims the runtime zero-weights carry **99.9983%** of the variance driving the KMeans objective (`volume` alone 97.58%), so KMeans partitioned by volume/price level while the runtime scores candle shape. Correct null is the majority-class baseline 0.3264 (not 1/8); kappa 0.238. Probe `scripts/analysis/zone_assignment_parity_probe.py`, artifact `docs/analysis/zone-assignment-parity.LATEST.json` (recorded 0.4140 reproduced exactly). Information only, no authority (§6.5).
- **Enhancements:** 2026-07-03 — [`active_models.yaml`](../../active_models.yaml) file-format **v2.1** (additive; truth-layer schema stays 2.0): each model entry now carries a `reachability` block (config sections, telemetry streams with descriptive `schema`/`purpose`/`llm_questions` semantic contract, tests, topics, framework-registry ids), a **descriptive-only** `optimization` block (`authority: none` — §6.5, promotion stays M4 gate + PromotionManager), and `evidence.conflicts`/`evidence.hypotheses` F-id/H-id reference lists. New sibling registries: `data/hypothesis_registry.jsonl` (H-001…H-016, seed-script pattern, schemas.md §9.6) + generated `data/findings.jsonl` (derived view of current-findings.md, §9.5). Guard: `tests/test_active_models_registry.py` (citation-class). Grants no authority; no finding changed.
- **Enhancements:** 2026-07-22 — [`active_models.yaml`](../../active_models.yaml) file-format **v2.2** (additive): WHO `identity` blocks under `gaussian` / `zone_gate` / `rr_model` / `bitnet` / new thin `tradenet` entry. Each identity **mirrors registry actives** (`authority: mirror_of_registry` — promote stays on registries), documents `spine_binding` (wired vs uses_trained_checkpoint) and `how_path_ref` parity pins against production HOW keys (not loaders), plus `runtime_binding.config_version` == `ACTIVE_VERSION`. No `version_history` (registries remain the ledger). No thresholds/paths as authority. CI: `tests/test_active_models_registry.py` R1–R4. Grants no runtime authority; no EngineRunner/config behavior change.
- **Enhancements:** 2026-07-22 — identity **v2.3 vocabulary** (Exists ≠ Selected ≠ Enabled): `selection` (was `active`), `execution.runtime_enabled` (was `spine_binding.wired`), derived `identity_status` ∈ {absent, selected_not_enabled, selected_and_enabled, enabled_without_checkpoint}. RR/TradeNet stay `selected_not_enabled`; Gaussian `enabled_without_checkpoint` (F-060); ZoneGate `selected_and_enabled`. ModelResolver reads v2.3 with v2.2 fallback. No auto-enable of trained artifacts.
- **Enhancements:** 2026-07-22 (Phase 0) — CODE layout authority [`src/config_layer/model_paths.py`](../../src/config_layer/model_paths.py) + [`src/config_layer/model_resolver.py`](../../src/config_layer/model_resolver.py). `resolve_zone_gate_runtime` fail-closes on registry/identity/HOW path mismatch; `EngineRunner` loads ZoneGate only through the resolver. RR/Gaussian/TradeNet/BitNet resolvable for parity; rr_fusion still loads HOW path when enabled (registry artifact may differ). Guard: `tests/test_model_paths_resolver.py`. No `models/` tree reorg.
- **Enhancements:** 2026-07-22 — **models/ path-literal freeze** (governance, no loader migration): scanner [`scripts/governance/scan_model_paths_literals.py`](../../scripts/governance/scan_model_paths_literals.py) + debt [`docs/governance/model_paths_literal_debt.json`](../governance/model_paths_literal_debt.json) + floor [`tests/test_model_paths_literals.py`](../../tests/test_model_paths_literals.py) (on GREEN_FLOOR). Unauthorized `models/` AST string literals outside `model_paths.py` / `model_resolver.py` / migration tooling / `tests/**` are grandfathered and may only **shrink**. New pairs FAIL CI.
- **Enhancements:** 2026-07-05 — added the **Feature Lineage Matrix** section above (OHLCV → formula → CRT-state → CRT/Gaussian/ZoneGate/RR consumer → fusion weight, every cell file:line-cited, branch-scoped to `v2_multi_2026_04`) + machine-readable `feature_lineage:` block in [`active_models.yaml`](../../active_models.yaml) (`authority: none`, guard extended in `tests/test_active_models_registry.py`). The structural/advisory/unused split falls out of the fusion-weight column (CRT-0.4=structural, Gaussian/regime=advisory, Zone-only/inert=unused).
- **Challenges/RESOLVED:** 2026-07-05 — the `wick_size`/`body_ratio` semantic-divergence risk is **resolved**: **2** definitions not three (CRT `Candle` property ≡ batch pipeline = `body/range`; the single-row `crt_feature_builder` `body/total_wick` outlier is **dead code**), canonical = `body/range` (bounded [0,1]; gate-coherent). Unified all paths through new immutable [`src/features/candle_math.py`](../../src/features/candle_math.py) (parity-tested, byte-identical; 210 golden/determinism tests green). **E-001 correction:** an earlier framing called it "three interpretations, ambiguous" — it is two, CRT matches the pipeline, and the divergence had ZERO runtime impact (the outlier is uncalled; live BitNet reads canonical cached `disp.body_ratio`).
- **Enhancements:** 2026-07-05 — fusion weights confirmed **config-only fail-fast** at runtime (`_cfg_require`, [engine_runner.py:384](../../src/core/engine_runner.py)); the `0.3/0.1` code defaults in `ENGINE_RUNNER_DEFAULTS`/`FusionConfig` are TEST-fixture scaffolding, never a runtime authority. Locked by `tests/test_fusion_weights_config_only.py`.
- **Enhancements:** 2026-07-07 (F-047) — extended the WHAT layer from geometry to **deterministic derived metrics** (new `derived_metrics` section above) and made the ontology/registry the **authoritative, mechanically-enforced** source of feature math. Registry split into a `src/features/registry/` package behind the stable `formula_registry` facade + scalar `derived_math.py` (never `eval`'d); added per-feature stable IDs/version/lifecycle + a `depends_on`↔`used_by` DAG. THREE enforcement layers (parity battery, ownership-lint, lineage exhaustiveness). **E-001 scope caution:** the ownership-lint census surfaced 10 pre-existing divergences (grandfathered/pinned) — the live `body_ratio` (body/total_wick) is a CONFIRMED static-code divergence, but whether it changes a live DECISION is UNVERIFIED (it lands in an `auxiliary` dict; down-consumer impact = the OPEN Phase-B question). Enforcement-only, hash-neutral, byte-identical (crt determinism 3 green, pipeline parity green); grants no authority (§6.5). Phase-B fixes deferred behind their own findings.
- **Enhancements:** 2026-07-11 (`CH-gd004-gd005-disp-strength-closure`) — the last two `disp_strength` grandfather pins CLOSED, identity-only/byte-identical. **GD-005** ([PATCH 7] `wick_size/atr`) adjudicated **exactly FM-028** and routed through `derived_math.displacement_atr_ratio`. **GD-004** (`scoring_engine.compute_scores` local `move/atr`) adjudicated a genuinely **NEW third identity** — the sole caller `crt_engine.py:23` feeds the FM-020 feature as `move`, so the as-wired value is `FM-020/atr_rel` (probe BNBUSDT 29,922 bars: equals FM-028 0.00%, FM-020 2.08% zero-disp only; saturates `s_breakout`'s `min(x/2,1)` on **97.5%** of bars) — registered as **FM-029 `disp_strength_atr_rescale`** + routed. Bare `disp_strength` derivation is now a hard lint failure (no pinned exceptions). **Deferred:** the suspected caller mis-wire (raw move plausibly intended) = `FU-CRT-MOVE-MISWIRE`, a gate-ON behavior change for the post-PIT phase (bounded per F-037/F-048). Geometry census + Gate-2B adjudication resynced (110→117 governed / 0 missing — also absorbed the pre-existing Phase-1 staleness). Evidence: `docs/governance/gd004_gd005_disp_strength_closure-2026-07-11.{md,json}`.
- **Enhancements:** 2026-07-22 — added the narrative companion to this topic: [`docs/architecture/model-design-intent.md`](../architecture/model-design-intent.md) — a design-intent reconstruction of EVERY model (spine engines, execution stack, cognitive sidecar, interpreters, research machinery) in information-contribution language (CTO sentence · trader persona · one question · new information · removal cost · redundancy · category · A–D design grade), plus the cross-model architecture (same-thing groups, merge/never-merge, missing stages: calibration, portfolio, order flow, execution-quality loop, drift actuator) and a target-pipeline diagram. Authority NONE (§6.5); implementation truth stays with this topic + the five lineage audits + `active_models.yaml`. This topic remains the feature-ownership authority; the new doc owns the *why-does-each-model-exist* narrative.
- **Enhancements:** 2026-07-22 — **Envelope layer design freeze** (`ENV_ARCH_V1`): [`docs/architecture/envelope-layer-design.md`](../architecture/envelope-layer-design.md). Last pre-Fusion predictive module after TradeNet; estimates post-entry MFE/MAE/holding/TTL/TP–SL bands (not outcome probabilities). Cross-linked from `model-design-intent.md` §8b + Part VII missing #6 partial close. No production code/wiring/training; Fusion consumption = coherence + risk_mult + planner pass-through (not a 5th EXPECTED_ENGINES vote). Feature ownership: none exclusive at design freeze; planned v1 = full 38-vector + context.
- **Enhancements:** 2026-07-11 (FC1-A `CH-fc1a-swing-causal` + FC1-D `CH-fc1d-volregime-causal`, audited) — **production feature-vector semantics changed for 11 of 38 dims.** The 10-dim structure closure (double_sweep, sweep_detected, liquidity_sweep, break_of_structure, swing_high/low, higher_high, lower_low, liquidity_distance/pressure) now publishes CAUSAL DELAYED (centered pivot shifted k=SWING_WINDOW=2; F-051 blast radius: ~63% of bars differed any-of-10, live path was zero-fed) — batch in `feature_pipeline.compute_structure_liquidity`, live via new `src/features/causal_structure.py` in FeatureStore (parity-tested all 10 columns incl. liquidity dims on the finite domain). `volatility_regime` binds ROLLING_CAUSAL N=200 (FC-0.5 semantic: local ATR-percentile context, NOT Regime Detection; N confirmed structural 2026-07-11 with revision trigger). Centered/global identities remain research-only `*_centered_batch` / `volatility_regime_global_batch` columns. **rr_model + zone_registry are PIT_UNCLEAN** (trained on centered-swings + global-batch-volregime era; `models/*.provenance.json`): no promote/re-enable/economic use without causal re-dataset→retrain→revalidation; no immediate retrain (rr_fusion disabled F-038, marginal value unproven). F-029's gate-OFF ledger claim held under replay (refined, not reversed); gate-ON A/B 11≡11 / 6≡6 is PC-2-bounded (INCONCLUSIVE about structural importance, not "insensitive"). Machine sync: `active_models.yaml` feature_lineage `pit_note` + rows 22/23/29 + zone/rr `pit_provenance`.
- **Enhancements:** 2026-07-22 (F-061, program `FM-030-031-DIMENSIONAL-MIX-MIGRATION`) — the B0/B1 dimensional mix is reclassified from a **representational** defect to a **decision-surface** one, and the correction is made reachable. `legacy ≡ corrected × close` (closed form, verified to 9.9e-08), so the emitted magnitude of FM-022/FM-023 is the instrument's price level: median `|ema_spread|` 320 on BNBUSDT and 38,110 on BTCUSDT versus 0.53 on EURUSD, against `dual_engine` thresholds of 0.15/0.3. Consequence on crypto — `detect_regime` → `"trend"` on **98.86%/99.94%** of bars, `breakout_engine` score pinned at **1.0** on ~100%, `tanh(momentum_score)` saturated on **98.78%/99.94%** (this is F-060's Gaussian mechanism, now shown to be one instance of a four-consumer pattern), and `gate_intelligence`'s REVERSAL score constant **0.0**. Under FM-030/031 all three instruments converge (trend 52.7/52.8/50.1%, pinned 6.8/6.8/7.2%) — the corrected identity discriminates and is instrument-invariant. Three sign-only consumers (`execution_planner._derive_intent`, `crt_engine_v2:2138`, `sl_tp_comparator`) are unaffected. **Remediation is additive and inactive:** FM-030/031 promoted out of the ontology's `migration_candidates:` prose into first-class registered identities (`derived_math.ema_spread_atr` / `momentum_score_atr`, registry-dispatched), selected by a new strict `feature_pipeline.normalization_basis`; the default `atr_relative` arm is the legacy math verbatim and the XAUUSD freeze-pin vector SHA is **unchanged**. Floor: `tests/test_fm030_031_normalization_basis.py` (12 assertions incl. the pinned defect — 100× price must still multiply FM-022/023 by 100 — and fail-closed config discipline). Economic question routed to `scripts/research/dimensional_mix_shadow_diagnostic.py` (gate-ON forced, F-036 method); prior F-019…F-043 predicts null and spine n is below the 30-sample floor. **DESCRIPTIVE only, grants no activation authority (§6.5)**; `ACTIVE_VERSION` unchanged; the four degenerate consumers untouched. Scope: batch-pipeline path only — the live `FeatureStore` ingress is separate M16 consumer-alignment work.
