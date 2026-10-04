# Model intent vs trained representation — read-only answer

## Context
User question: for each model, what semantic information does its *intent* require, and what
representation was it *actually* trained to consume? This is an analysis question, not a change.
Sources read: `docs/governance/MODEL_INTENT_AUTHORITY_REGISTER.md` §3 (intent), `active_models.yaml`
(runtime/identity), `docs/governance/model_lineage_rollup.md` §4–5 (training lineage),
`src/features/feature_schema.py:320` (live schema = v6.0, 48 dims, verified by import).

## Answer (the deliverable)

| Model | Intent (MIAR) | Semantic info the intent needs | What it was trained on / consumes | Gap |
|---|---|---|---|---|
| **EMA-momentum kernel** ("Gaussian", live) | How *conformant* is this state to previously observed states? | A learned reference locus (μ, σ) from history; scale-invariant momentum | 3 features (`ema_fast`, `ema_slow`, `momentum_score`); μ=0/σ=1 defaults because 0 registry entries carry them (F-060). Trained NB artifacts (35-dim ETH, 38-dim BNB) exist but are never opened | No reference distribution at all, so "conformity" means distance from *flat*. `momentum_score` is the dimensionally-mixed FM-023, saturated on ~99% of bars (F-061/F-064). Builder `phase5_calibration.py` used F-022 labels |
| **NB outcome classifier** (off-spine) | What outcome do historical labels expect? | Clean outcome labels, direction | 35/38-dim vectors, raw `rr_achieved` from the F-022 detection stream | Labels contaminated (confirmed). Alignment = SEMANTIC_DRIFT |
| **ZoneGate** (feature-cluster similarity) | Is this state in a structurally valid location / neighbourhood? | Feature-space position plus outcome quality per region (structure context, PIT-clean) | KMeans k=8 over the BNB opportunity stream; scores a 38-name subset of the v4 39-dim vector; **hand-set uniform mask, 24 dims active, the 13 price-level dims dropped** (not learned); schema v4, not the live v6/48 | Pre-SMC schema, so it never sees the 9 v5 SMC primitives. PIT_UNCLEAN (centered swings, F-051). Labels F-022-contaminated; honest re-derive gives 0/8 zones E>0 (F-041B). Labels are unread at runtime anyway (purely geometric) |
| **Candle commitment** (fusion slot `rr`) | How strong is the candle's commitment? | Bar geometry only | `close/high/low` → polarity ∈ {0}∪[0.5,1]; no training | Aligned. Only drift is the name: `rr`/`rr_ratio` suggests economic RR (F-048) |
| **RR trained / NanoInference** | What learned reward behaviour goes with this state? | Clean, direction-aware reward labels (`forward_walk`) and an in-distribution confidence measure | Ridge + GNB on 38-dim canonical_38, BNB, 11 zero indices (rank 27); labels = F-022 `outcome`/`rr_achieved` | Confidence gate mis-scaled for 27 dof: 100% bypass even in-sample (F-044). Labels contaminated (F-045). Clean-label retest = KEEP_CANDIDATE, research only (F-059). PIT_UNCLEAN. **Split:** the registry-active version is BNB 38-dim, but config `rr_fusion.model_path` points at `models/XAUUSD/20260728_v39/rr_model_20260728_v39_xau.json` (on disk; I did not check its dim). Moot while `enabled:false` |
| **BitNet** | Should this be rejected because the state is unsafe? | Safety meaning: adverse-outcome risk, for both directions, scale-invariant | Legacy-6 (`body_ratio`, `retest_depth`, `disp_strength`, `atr`, `candles_since_sweep`, `double_sweep`); labels = synthetic **bullish-only** ATR race (+2·ATR before −1·ATR, 40 bars); rows filtered `retest_depth>0.05` | Label is not "unsafe": it is one-sided and not economic. `atr` is raw, so not scale-invariant. Train/serve name skew (F-050, aliased). Dual artifact fork (legacy_6 vs export_35); empty registry. Enabling it harms the book (F-055) |
| **TradeNet v2** | MIAR: expected milestone outcomes (TP1/TP2/BE survival). active_models.yaml: "capital quality of this setup" | Milestone labels from the production trade object (partial TP1 + trail → TP2) | 35-dim (schema v2), ETHUSDT only, F-022 opportunity labels, 3 heads, composite 0.4/0.4/0.2 | Wrong trade object: `forward_walk`-style labels ≠ production's multi-TP trade (F-088). Two schemas behind live (35 vs 48). No BNB/XAU artifact. Unwired (F-005) |
| **EnvelopeNet** (research) | Post-entry price-time bounds | Side (direction), clean excursion labels, quantiles for bands | canonical_38, clean `forward_walk` labels (the only family with them); 4 point heads; **`side` excluded** | 66.9% of MFE/MAE variance can't be learned without side. No quantiles, so the band derivations can't be built. PIT_UNCLEAN_STORED_FEATURES |

### Cross-cutting pattern
1. **Labels:** every trained model except EnvelopeNet learned from the F-022 detection stream (or a
   synthetic proxy, for BitNet), not from the trade object its intent names. So the "semantic
   meaning" the intents require (outcome, reward, safety) never reached training.
2. **Schema:** no trained artifact is on the live v6.0/48 vector. They sit at 6, 35, 38 and 39 dims,
   so all of them are blind to the v5 SMC primitives (F-076).
3. **PIT:** RR, ZoneGate and Envelope were trained in the centered-swing era (F-051, PIT_UNCLEAN).
4. **Only aligned surfaces are untrained geometry:** candle commitment and the CRT FSM.

### Truth conflicts surfaced (§6.2 rule 3, not resolved)
- **TradeNet intent wording:** MIAR §3.6 says "expected milestone outcomes"; `active_models.yaml`
  `tradenet.intent.question` says "capital quality" (that is TradeNetMeta's MIAR §3A.2 meaning).
- **RR intent wording:** `active_models.yaml` `rr_model.intent.question` asks "is the reward-risk
  economically viable?" MIAR splits this into `candle_commitment` and `rr_trained`, and F-048 assigns
  economic RR to UltronRiskGate.
- **DOC_DRIFT:** MIAR §3.2 says schema "v4, dim=39"; the code says v6.0/48. MIAR §3.6 says TradeNet
  input is 39-dim; the registry-active artifact is 35-dim.
- **RR selection vs config HOW path:** BNB 38-dim vs XAU v39 (above).

## Optional follow-ups (not executed; needs user say-so per §1.2)
- Fix the three MIAR/yaml wording drifts (doc-only; §6.2 auto-fix for DOC_DRIFT, but the TradeNet
  and RR intent wording is AMBIGUOUS and needs a user call).
- Check the dim of `rr_model_20260728_v39_xau.json` (read `n_features`) to settle the RR split.

## Verification
Read-only; every row cites a registry line or finding above. Session-log append to
`assistant_project.md` is deferred: plan mode blocks writes.
