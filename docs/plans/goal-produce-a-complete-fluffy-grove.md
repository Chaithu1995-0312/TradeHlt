# Plan: Persist the Intelligence-Layer Audit

> Created: 2026-06-02 · Plan-mode deliverable. The audit below is finalized and ready to write
> verbatim to `docs/analysis/intelligence-layer-audit.md` (point-in-time analysis per CLAUDE.md §2).

## Context

A multi-pass, evidence-only audit of the Tradelatest intelligence layer surfaced a chain of findings
that culminate in a concrete production-logic consequence (the zone gate routes ~90–96% of passes
through regions its own metadata records as negative-expectancy, with no stage able to correct it).
These findings are load-bearing and must be persisted as a dated point-in-time doc. Active production
config = `v2_multi_2026_04 - deepdeektry` (per `configs/production/ACTIVE_VERSION`).

## Action on approval

1. Write the document below verbatim to `docs/analysis/intelligence-layer-audit.md`.
2. Append the §6 SESSION LOG block (shown at end) to `assistant_project.md`.
3. No code changes. No architectural proposals. Evidence-only, as produced.

---

# Intelligence-Layer Audit — Tradelatest

> Point-in-time analysis (NOT living). Date: 2026-06-02. Evidence-only; no proposals.
> Active config: `v2_multi_2026_04 - deepdeektry` (`configs/production/ACTIVE_VERSION`).

## 1. The seven systems (A–G)

| System | A. Purpose | B. Inputs | C. Outputs | D. Runtime consumers | E. Training source | F. Status |
|---|---|---|---|---|---|---|
| **Heuristic CRT** | Composite setup score `0.35·sweep+0.25·breakout+0.20·retest+0.20·time` (`scoring_engine.py:42`) | sweep/double_sweep, body_ratio, disp_strength, retest_depth, candles_since_retest (`crt_engine.py:17-27`) | `{score,final,sub-scores}` [0,1] | EngineRunner→Fusion (`engine_runner.py:655`; `score_crt` `fusion_engine.py:371`) | none (rule-based) | **ACTIVE** (`weight_crt 0.4`) |
| **Gaussian** | Probability score; heuristic EMA/momentum PDF (`heuristic_gaussian_engine.py:271-343`) or ML NB sigmoid(expected_rr) (`ml_gaussian_engine.py:167-169`) | 3 feats (heuristic) / 35-dim (ML) | `{score,reason,meta}` | EngineRunner→Fusion (`engine_runner.py:666`) | static mu/sigma or `models/gaussian_*.json` | **ACTIVE** (heuristic); **SHADOW** (ML, `shadow_ml`) |
| **RR Model** | Candle Polarity Index (NOT forward R:R) (`rr_engine.py:4-28,59-73`); optional `RRFusionLayer` nano-model | close/high/low | `{score,candle_polarity,rr_ratio(legacy)}` | EngineRunner→Fusion (`engine_runner.py:684`) | RREngine none; RRFusion `models/rr_model.json` (`rr_dataset_builder.py`) | **ACTIVE** (`weight_rr 0.2`) |
| **TradeNet V2** | 3-head survival net (p_tp1/p_tp2/p_survives_be), composite `0.4/0.4/0.2` (`trade_net_v2.py:15,45`) | 38-dim canonical | `{tradenet_score,p_tp1,p_tp2,p_survives_be}` | only `CognitiveBus` (`cognitive_bus.py:209,232,309`) — off the execution spine | `train_trade_net_v2.py` on `opportunities_*.jsonl` | **DORMANT** (no cognitive section in active config) |
| **ReplayMemory** | Region-conditioned historical win-rate/RR with decay (`replay_memory_engine.py:193-224`) | `opportunities_*.jsonl` + zone centroids | `{historical_winrate,cluster_stability,temporal_confidence,…}` | only `CognitiveBus` (`cognitive_bus.py:219-298`) | none (reads JSONL) | **DORMANT** |
| **ForwardTester** | OOS validators (BitNet zone overfit `bitnet/forward_tester.py:38-187`; LLM 3-mode `llm_research/forward_tester.py:43-245`) | zones / data CSV | per-zone status / `ForwardTestReport` | none (research scripts only) | n/a | **DORMANT** (research-only) |
| **Probability Surface** | none on HEAD; only `inout.probability` config block (model_dir, approach "D") | — | — | none | — | **DEAD** (config ghost; impl only in detached worktrees) |

## 2. Actual runtime dependency graph

```
Features (38-dim CANONICAL_FEATURES — feature_schema.py:46-76)
  ↓
EngineRunner  (engine_runner.py:576) — runs 4 engines sequentially:
   Adapter/trap gate → CRT → Gaussian → ZoneGate → RR (+ optional RRFusionLayer)
   completeness hard-gate: EXPECTED_ENGINES = {crt,gaussian,zone_gate,rr} (:52/:748)
  ↓
FusionEngine.compute (:777; fusion_engine.py:290-547)
   regime-weighted avg (crt .4 / gaussian .2 / zone_gate .2 / rr .2) + conflict + normalize
  ↓
DecisionEngine.evaluate (:961; decision_engine.py:104-158) — dynamic threshold + 4 gates → execute|reject
  ↓
ExecutionPlannerV1_2.plan (execution_planner.py:156-250)
  ↓
UltronRiskGate.evaluate (ultron_risk_gate.py:156-188)

Off-spine, DORMANT: Features → CognitiveBus → {ReplayMemory, TradeNetV2} → TradeNetMeta → logs/cognitive_telemetry.jsonl
```

## 3. Overlap analysis
- **Duplicated:** Gaussian heuristic vs ML (same slot); win-probability produced 3× (Gaussian-ML / TradeNet / ReplayMemory — only Gaussian reaches Decision); two ForwardTesters; "RR" naming collision (CPI vs forward-R:R in Ultron).
- **Abandoned:** Probability Surface (DEAD); cognitive layer (TradeNet+ReplayMemory) de-configured v1→v2; ForwardTesters orphaned.
- **Replacement paths (in code):** Gaussian heuristic→ML (`shadow_ml` harness); RR formula→`RRFusionLayer`; flat risk tiers→TradeNet `capital_quality_score` (gated behind disabled CognitiveBus).

## 4. Probabilistic scorers + density-awareness
- **Comparison:** TradeNet V2 is the only candidate that consumes the full 38-dim vector, emits outcome-grounded multi-head probabilities, and has an honest train/test split (n_test 10k–30k) + AUC promotion guard. Gaussian-ML: corr~0.18–0.21, `n_val=0` (in-sample calibration), 38→35 truncation. Gaussian-heuristic: 3-feature prior, zero-dependency, the live default.
- **Density layer (if TradeNet owns probability):** mathematically correct = **GMM** (multimodal density + per-component Mahalanobis/χ² threshold), which is the generalization of the *existing* diagonal-covariance zone registry. KDE defeated by d=38 + categorical features; Mahalanobis correct only per-mode (it is the GMM exponent); KMeans/novelty/autoencoder are not densities. Note: density (membership) ≠ concept-drift detection (see §6).

## 5. CRT score is informationally redundant
- CRT score = closed-form `f(sweep_detected, double_sweep, body_ratio, disp_strength, retest_depth, candles_since_retest)` — all six already in the 38-vector (`scoring_engine.py:14-51`). No external data.
- TradeNet/Gaussian/zone train on the 38-vector, never on CRT score or sub-scores (`build_input_matrix`→`extract_feature_vector`; grep `crt`/`scoring_engine` = 0).
- Removing CRT score removes **zero** predictive information (reconstructable R²≈1.0; it is an algebraic identity up to config constants). It is an inductive prior, not an information source. Most-predictive features = CRT *geometry* (body_ratio, retest_depth, disp_strength); least = raw OHLCV (zeroed in zone weights; harmful under equal weight).

## 6. The drift gap (core finding): "Known Region ≠ Profitable Region"

A robust system needs three independent answers: **A** what am I looking at (membership), **B** was it historically profitable (baseline expectancy), **C** is it still profitable now (recent expectancy). Status:

- **A — membership: IMPLEMENTED.** Zone gate scores membership against frozen registry, hard pass/block on score ≥ threshold (`zone_gate_engine.py:239-240`).
- **B — baseline expectancy: STORED BUT UNREAD.** Every zone carries `meta.mean_rr / tp_hit_rate / sl_hit_rate / n_samples`. Repo-wide grep shows **no decision-path code reads `mean_rr`** (readers are schema-meta, the separate regime cluster engine, and the dormant replay layer). Dead telemetry w.r.t. the trade decision.
- **C — recent expectancy: NOT IMPLEMENTED in production.** `ReplayMemory.query` *does* compute decay-weighted recent win-rate (`exp(-λ·age_days)`, `replay_memory_engine.py:193-224`) — the correct mechanism — but (a) it is DORMANT, (b) it reports a level not a Δ vs trained edge, (c) its `cluster_stability`/`temporal_confidence` measure dispersion/coverage, not drift, (d) it is fed only by simulated outcomes (see write-back).

### 6.1 Outcome write-back — the live learning loop does not close
- `opportunities.jsonl` (read by ReplayMemory + TradeNet training) is written by the **scanner/backtest** (forward-simulated outcomes), `backtest_v2.on_trade_closed` (`:831-906`).
- `src/inout/` (live package) contains **only** two candle fetchers — no execution, no trade-close, no outcome writer. No writer of `inout_trades.db` exists. No inout code references opportunities/replay.
- **Verdict:** the system re-learns offline by re-simulation over (re-)fetched candles; it **never** ingests its own live outcomes. Slippage, partial fills, real execution quality are structurally invisible.

### 6.2 Zone expectancy — the production registry is 96% losing mass
`models/zone_registry.json` (loaded by active config: `engine_runner.zone_registry_path`, `zone_mode=hard`, `zone_min_samples=50`, `weight_zone_gate=0.2`):

| zone | n_samples | mean_rr | | zone | n_samples | mean_rr |
|---|---:|---:|---|---|---:|---:|
| zone_0 | 20,708 | −0.0292 | | zone_4 | 3,872 | +0.0124 |
| zone_1 | 10,100 | −0.0180 | | zone_5 | 172 | +0.1163 |
| zone_2 | 45,674 | −0.0519 | | zone_6 | 1,162 | +0.0897 |
| zone_3 | 31,540 | −0.0448 | | zone_7 | 26,714 | −0.0500 |

- **5/8 zones negative; negative zones hold 134,736 / 139,942 = 96.3% of occupancy.** The 3 positive zones are the smallest (3.7% mass; the two with real magnitude have 172 & 1,162 samples).
- `min_samples=50` filters by popularity (anti-correlated with edge): all 8 zones load, including all negatives.

### 6.3 Fusion-signing proof — a negative zone *raises* the fused score (architecture, not bug)
- `score = model_fn(vector)` = membership ∈ [0,1]; `passed = score≥threshold` (`zone_gate_engine.py:239-240`). No `mean_rr`.
- `zone_result.score = float(zone_raw["score"])`, `direction = 1 if passed` (`engine_runner.py:649-654`).
- `score_zonegate = _clamp(float(payload["score"]))` ∈ [0,1], always ≥0 (`fusion_engine.py:366,376`).
- `weighted = (… + w_zonegate·score_zonegate + …)/total_w`, `w_zonegate = 0.2 > 0`. ∂(fused)/∂(score_zonegate) = +0.2/total_w.
- **Therefore:** higher membership in any zone (incl. mean_rr<0) → higher fused score → more likely `execute`. `mean_rr` is read by **nothing**, so no term can subtract for a losing zone. It is the *absence* of an edge term (architecture), not a sign error (bug).

### 6.4 Live exposure
- Occupancy-weighted expectancy of the matched zone = **−0.0410 R/candle**.
- If membership passes ∝ occupancy → **~96% of zone-gate passes route through negative zones.** Sensitivity: even at an implausible 10× preferential pass rate for positive zones, negatives still take 72%; realistic skew (sparse positive zones → k≤1) pushes the true figure to the **93–96%** (worse) end.
- Caveats: zone gate is 20% of fusion + hard gate (not sole gate); no downstream engine reads expectancy so none corrects the bias; −0.041R is per-candle raw-scan expectancy, not realized post-pipeline PnL.

## 7. Consolidated status

| Capability | Status |
|---|---|
| Feature extraction (train==live, schema-hash guarded) | SOLVED |
| Zone membership ("known region") | SOLVED |
| Offline re-training loop (scanner→train→registry) | SOLVED (manual) |
| Probability (recency-conditioned) | PARTIAL — ReplayMemory built, DORMANT, sim-fed |
| Live outcome feedback | ABSENT (no live writer) |
| Baseline expectancy at runtime | STORED (`meta.mean_rr`) but UNREAD |
| Concept-drift / region-decay detection | NOT IMPLEMENTED |
| Edge-aware gating (membership × expectancy) | NOT IMPLEMENTED — gate is membership-only; 96% negative-mass exposure |

**Bottom line:** the system reliably recognizes familiar market states but does not verify, at runtime, whether those states still (or ever) had an edge — and by occupancy it routes the large majority of signals through regions its own metadata records as losing. This is more fundamental than any CRT-weight question.

---

## Evidence index (primary citations)
`scoring_engine.py:14-51,42` · `crt_engine.py:17-27` · `heuristic_gaussian_engine.py:271-343` · `ml_gaussian_engine.py:151-169` · `rr_engine.py:4-28,59-82` · `trade_net_v2.py:15,45,165-185` · `train_trade_net_v2.py:141-185` · `replay_memory_engine.py:193-224,294-304` · `cognitive_bus.py:209-309` · `feature_schema.py:46-76,194-273` · `engine_runner.py:52,411-413,576,632-654,655,666,684,748,777,961` · `fusion_engine.py:290-547,366,376` · `decision_engine.py:104-158` · `ultron_risk_gate.py:156-188` · `zone_gate_engine.py:101-102,239-240` · `zone_cosine_searcher.py:117-118,298-344` · `models/zone_registry.json` (8 zones) · `configs/production/ACTIVE_VERSION` · `docs/analysis/feature-region-oos-persistence-2026-06-01.md`

## SESSION LOG block to append (CLAUDE.md §6)
```
---
📝 SESSION LOG ENTRY
Date: 2026-06-02
Topic: Intelligence-layer audit persisted to docs/analysis/intelligence-layer-audit.md
Decision/Output: Full evidence chain — 7-system A–G map, runtime dependency graph, overlap analysis, probabilistic-scorer comparison (TradeNet best, GMM density layer), CRT-score redundancy proof, and the core drift gap: A(membership)=solved, B(baseline meta.mean_rr)=stored-but-unread, C(recent edge)=not implemented; live outcome loop absent (inout = candle fetchers only); production zone_registry is 96.3% negative-expectancy occupancy; fusion-signing proof that mean_rr<0 raises the fused score (architecture, not bug); ~90–96% of zone-gate passes route through negative regions (occupancy-weighted matched-zone expectancy −0.041R).
Open Questions: Per-instrument zone registries not yet cross-checked vs the global one; offline loop automation cadence not traced; OOS-script mechanics (Thread #3) deferred.
Next Step: Optionally cross-check per-instrument registries / OOS script; await user direction on whether any finding becomes a Brick.
---
```

## Verification
- After writing, confirm `docs/analysis/intelligence-layer-audit.md` exists and renders; confirm the SESSION LOG block is appended to `assistant_project.md`.
- Re-confirm two load-bearing facts before publishing: `cat configs/production/ACTIVE_VERSION` = `v2_multi_2026_04 - deepdeektry`; the 8-zone `mean_rr` table reproduces from `models/zone_registry.json`.
