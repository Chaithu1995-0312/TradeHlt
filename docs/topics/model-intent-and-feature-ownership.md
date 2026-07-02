# Topic: Model Intent & Feature Ownership

> **Topic-visibility unit.** One concept, narrated in human language, kept in sync with the
> code on every working response (`CLAUDE.md §6.1`). Read this to understand *which model owns
> which of the 38 canonical features and why* — **without loading the rest of the codebase**.
> This is the **canonical authority** the feature-expansion program (plan
> `d-tradelatest-reports-ohlcv-lineage…`) defers to. Link, don't inline.
>
> Created: 2026-06-27 · Updated: 2026-07-02 · Status: living

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
| ZoneGate | zone quality [0,1] | per-zone win/mean_RR (~98% SL-hit) | active hard gate | F-036, F-041 | `NONE` (NON_PIVOTAL, ΔG001≡0) |
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
