# Gaussian Lineage Audit

**Program:** Post-CH-002 model/training lineage (subsystem 1 of 5)  
**Date (UTC):** 2026-07-09  
**Active config:** `v2_multi_2026_04`  
**Prerequisite:** `POST_CH002_BASELINE_DIFFERENTIAL = PASS`  
**Authority:** observational — no retrain, no promote, no config change

> **REVISED 2026-07-22 (F-060).** A source-verified re-trace corrected two claims in this document
> and added a lineage it had missed. Corrections are marked `CORRECTED:` inline (§6.2 rule 4 —
> history is preserved, never silently deleted). The dual-track shape is unchanged; what changed is
> (a) the trained artifact is *more* disconnected than "INERT" conveyed, and (b) the audited trainer
> is not the one that produced the artifacts on disk.

---

## Verdict

```text
GAUSSIAN_LINEAGE_VERDICT = DUAL_TRACK
  LIVE_RUNTIME     = ALIGNED (heuristic 3-feature; CH-002 INERT)
  TRAINED_ARTIFACT = INERT on active config (gaussian_impl=heuristic)
  CH002_IMPACT     = INERT for live score path
  REBUILD_REQUIRED = NO
  MARGINAL_OOS     = NO_AUTHORITY (no ΔG001 claim; do not retrain on rename)

  # added 2026-07-22 (F-060)
  LIVE_SCORER_PARAMETERIZED = NO   (mu=0/sigma=1 forced; zero learned params reach the score)
  LABEL_INTEGRITY           = F022_CONTAMINATED_CONFIRMED (was: "possible")
  ARTIFACT_BUILDER          = scripts/training/phase5_calibration.py (NOT train_pipeline.py)
```

---

## Dual-track reality (do not conflate)

| Track | What it is | Active on spine? |
|---|---|---|
| **A — Live fusion Gaussian** | `HeuristicGaussianEngine` — EMA/momentum kernel, 3 features | **YES** (`gaussian_impl: heuristic`) |
| **B — Trained ML Gaussian** | `GaussianNBModel` / `MLGaussianEngine` on full canonical vector | **NO** (requires `gaussian_impl=ml`) |
| **C — ZoneGate “gaussian score”** | Weighted Gaussian distance over zone μ/σ | **Different subsystem** (ZoneGate audit) |

`active_models.yaml` already documents this split (runtime ≠ trained_registry).

---

## Lineage chain (11 slots)

### 1. Training population

| Track | Population |
|---|---|
| **B (ML)** | Paired ENTRY/EXIT fusion JSONL via `validate_logs()` → `feature_vec` + outcome |
| Builder | `src/training/train_pipeline.py:run_gaussian_update` (8-step pipeline) — **unexercised** |
| Source logs | `*_fusion.jsonl` paths passed by caller — **not** CRT `cached_features` |
| Labels origin risk | ~~Outcomes may inherit F-022 contamination if sourced from opportunities~~ |

> **CORRECTED 2026-07-22 (F-060) — the audited builder is not the builder of record.**
> `train_pipeline.py:run_gaussian_update` exists but produced **none** of the artifacts in
> `models/`. Every Gaussian model on disk was written by the second, unaudited orchestrator:
>
> | | Path |
> |---|---|
> | Builder of record | `scripts/training/phase5_calibration.py` — `run_calibration()` `:623` → `train_gaussian` `:642` |
> | Dataset builder | `from_opportunities()` `:382`, feature vector at `:433` |
> | **Labels** | `rec["rr_achieved"]` read **raw** from `opportunities.jsonl` (`:434`) |
> | Nightly wrapper | `scripts/auto_train_from_opportunities.py:96-106` |
>
> `rr_achieved` is the **F-022 stream** (detection stream, 36.8% self-consistent). No
> `forward_walk` re-derivation exists anywhere in the Gaussian training path. The docstrings at
> `phase5_calibration.py:387` ("unbiased ground-truth labels") and `:391` ("CRT is NOT consulted —
> this is the unbiased training path") are contradicted by F-022/F-041B: F-041B is the precedent
> where re-deriving the same class of stored labels through `forward_walk(intrabar_fixed)` flipped
> them materially (sl_hit 0.959–0.989 → honest 0.649–0.663).
>
> `LABEL_INTEGRITY` therefore moves from *possible risk* (gap #4 below) to
> **CONFIRMED on the only lineage that produced artifacts**. This bears on any future ML
> activation; it is inert for the live path, which reads none of these labels.

Heuristic track **A** has no supervised training population — and, per the correction at slot 5,
no registry `mu`/`sigma` either: the defaults 0/1 are what actually run.

### 2. Feature identities

| Track | Features |
|---|---|
| **A live** | `ema_fast`, `ema_slow`, `momentum_score` only (`heuristic_gaussian_engine.py:305-308`) |
| **B train/serve** | Full `CANONICAL_FEATURES` / registry `feature_schema` (35-dim v2 or 38-dim v3) including pipeline names `disp_strength`, `retest_depth` (FM-020/021) |
| CRT FM-027/028 | **Not consumed** by either track |

### 3. Target / label

| Track | Target |
|---|---|
| **A** | None (kernel score ∈[0,1] from EMA ratio + tanh(momentum)) |
| **B** | Continuous `pnl_rr_net`; class via `rr_to_class` (4-bin RR); eval metric `corr(expected_rr, pnl_rr_net)` |

### 4. Dataset builder

| Track | Builder |
|---|---|
| **B** | `run_gaussian_update` steps 1–2: `validate_logs` + direct `feature_vec` extract (`train_pipeline.py:282-302`) |
| Optional | `rr_dataset_builder` path exists historically; current pipeline bypasses OHLCV rebuild when vectors are in logs |

### 5. Artifact

| Artifact | Role | Active on live spine? |
|---|---|---|
| `models/gaussian_registry.json` | Version manifest + per-instrument `__active__` | Read — but supplies **nothing** (see correction) |
| BNBUSDT active | `p5_20260524T120449` → `models/BNBUSDT/bnbusdt_balanced_20260524/gaussian_p5_…json` | Entry resolves; **the `.json` bundle is never opened** |
| ETHUSDT active | `v5_auto_2026_06_eth` | instrument-scoped; irrelevant to BNB spine |
| Many `active:false` entries | Historical 35/38-dim schemas with `disp_strength`/`retest_depth` | Not loaded for fusion score under heuristic |

> **CORRECTED 2026-07-22 (F-060).** ~~"Heuristic loads mu/sigma from active entry."~~ It does not.
> `_normalize_registry_entry` (`heuristic_gaussian_engine.py:42-53`) reads `mu`/`sigma` off the
> registry **entry**, defaulting to `mu=0.0, sigma=1.0` (`:49-50`). **All 11 entries were dumped and
> verified: not one carries a `mu` or `sigma` key** — they carry `version`, `model_file`,
> `feature_schema`, `schema_version`, `metrics`, `trained_at`, `active`. So the defaults fire on a
> *successful* load, and the live score reduces to `exp(-x²/2)` — byte-identical to the
> no-registry-at-all path.
>
> The distinction matters: `TRAINED_ARTIFACT = INERT` reads as "trained weights exist but are
> unused at reduced fidelity." The truth is stronger — **no learned parameter reaches the scoring
> path at any fidelity**. The registry read is a no-op, not a degraded read.
>
> Enforced by `tests/test_gaussian_live_parameterization.py` (fails if a `mu`/`sigma` key is ever
> added — that would be a live-behavior change needing its own governance).

### 6. Loader

| Track | Loader |
|---|---|
| **A** | `GaussianRegistry.load()` inside `HeuristicGaussianEngine._load_registry` — ~~supplies `mu`/`sigma` only~~ **CORRECTED: supplies nothing; defaults 0/1 always win (slot 5)**. Fail-open on load failure (`:236-253`), so a missing registry is indistinguishable at the score. |
| **B** | `MLGaussianEngine._load_model` → `GaussianModelRegistry` + `load_gaussian_model` — full model+scaler |

Separate path: CRT Phase-5 scorer uses `load_active_gaussian_scorer()` → **NoOpScorer** when no active entry for that registry API (`"no active gaussian registered"` in baseline log). That gate is **orthogonal** to fusion Gaussian.

### 7. Inference inputs

| Track | Inputs at compute() |
|---|---|
| **A** | Pipeline dict keys `ema_fast`, `ema_slow`, `momentum_score` (requires full CANONICAL_FEATURES length assert) |
| **B** | `extract_feature_vector(input_data)` → scale → `predict_expected_rr` → sigmoid score |

Neither path reads CRT `displacement_retrace` / `displacement_atr_ratio` (FM-027/028).

### 8. Output semantics

| Track | Output |
|---|---|
| **A** | `{"score": float∈[0,1], "reason": "gaussian_computed", "meta": {mu, sigma, x}}` |
| **B** | `{"score": sigmoid(expected_rr), …}` or fail-open `0.5` / `ml_gaussian_fallback` |

Score is a **directional-momentum / expected-RR proxy**, not a calibrated p(win) and not true RR.

### 9. Active config

```json
"gaussian_impl": "heuristic"   // configs/production/v2_multi_2026_04.json
```

- `engine_runner` selects via `_get_gaussian_engine` (`engine_runner.py:295-321`)
- Fusion weight: `fusion_engine.weight_gaussian` (regime-weighted blend)
- `EXPECTED_ENGINES` includes `"gaussian"`

### 10. Runtime consumption

```text
EngineRunner.run
  → HeuristicGaussianEngine.compute(pipeline features)
  → engine_results["gaussian"]
  → FusionEngine (weight_gaussian)
  → DecisionEngine (fused score threshold)
```

Observed on post-CH-002 baseline log:  
`EngineRunner: using HeuristicGaussianEngine (config: gaussian_impl=heuristic)`  
and later registry load for BNBUSDT version `p5_20260524T120449`.

### 11. Marginal OOS value

| Claim | Status |
|---|---|
| Heuristic adds incremental expectancy beyond CRT alone | **Not measured this audit** |
| Trained 38-dim NB authority on live spine | **None** — unwired |
| F-036 context | Fusion vetoes on gate-ON are zone-independent; CRT+Gaussian dominate scores, but economic authority still bound by entry-info null (F-019 family) |
| Rebuild/retrain justified by CH-002 | **NO** |

**Verdict slot:** `NO_AUTHORITY` for retrain/promote. Ablation for marginal value is a separate research task, not blocked on CH-002.

> **2026-07-22 (F-060):** that ablation now exists —
> `scripts/research/diagnose_gaussian_pivotality.py`, the F-036 method (pin the channel, compare
> trade-ledger sha256). **Result: `GAUSSIAN_INFORMATION_INERT`.** All three cells (live /
> pinned-at-saturation 0.8825 / pinned-0.5) produce byte-identical ledgers on all four majors
> (BNB 11/ETH 4/BTC 5/SOL 6, matching F-037's gate-ON counts), so the channel moves no trade on
> either its information or its level axis. It tests pivotality, not expectancy: gate-ON pooled
> n=26 < `min_samples: 30`, so this is a proof of non-pivotality with **no** economic verdict and
> **no** authority. `MARGINAL_OOS` therefore stays `NO_AUTHORITY` (now with a mechanism: the channel
> is a near-constant, and even removing its level changes nothing — fusion is CRT-dominated, per
> F-036). Recorded in F-060.

---

## CH-002 impact assessment

| Question | Answer |
|---|---|
| Does live heuristic read renamed CRT cache keys? | **No** |
| Does ML path (if enabled) read CRT FM-027/028? | **No** — pipeline FM-020/021 names |
| Did post-CH-002 baseline change Gaussian scores enough to flip trades? | **No** — full economic parity PASS |
| Rebuild required? | **NO** |

Historical ML feature schemas listing `retest_depth`/`disp_strength` refer to **pipeline** identities (unchanged by CH-002), not CRT emission keys.

---

## Known gaps / non-blockers

1. **Docstring drift:** some files still say “32-dim” / “35-dim” while schema is 38 (`ml_gaussian_engine.py` header).
2. **Registry “active” ≠ fusion ML:** ~~BNBUSDT registry active supplies heuristic mu/sigma~~ — **CORRECTED 2026-07-22 (F-060):** it supplies nothing at all; see slot 5. Full NB weights are not used under `gaussian_impl=heuristic`, and neither are kernel parameters.
3. **Phase-5 NoOpScorer** vs fusion heuristic: two different Gaussian surfaces; baseline uses NoOp for Phase-5 p_win gate.
4. **Label integrity** ~~for any future ML retrain~~ — **CORRECTED 2026-07-22 (F-060): CONFIRMED contaminated, not merely a risk.** `phase5_calibration.py:434` trains on raw `rr_achieved` from the F-022 stream; no `forward_walk` re-derivation exists. Re-derive before **any** economic claim about the trained track.
5. **F-038 history:** rr_fusion previously double-weighted Gaussian; already disabled — not Gaussian-lineage defect.

### Residual — found by the F-060 re-trace, deliberately NOT fixed

Recorded so they are not lost; each needs its own scoped change (§6.2 rule 4: surface, don't
silently absorb). None is on the live scoring path.

6. **7 of 11 registry entries are dangling** — `gaussian_v5_tradenet_2026_05_eur`,
   `gaussian_v6_2026_05_btc`, and five `p5_2026051931*` point at `model_file` paths that do not
   exist on disk. All are `active:false`, so nothing resolves through them today.
7. **`v4_mirrored` is a ghost.** It appears in `active_models.yaml:438` (`active:false`,
   experimental) and — as `status: "ACTIVE"` with `corr +0.2066` — in the hardcoded mock data at
   `ui_kits/crt_dashboard/data.js:4,145,324`. There is **no such artifact and no such registry
   entry**. The dashboard displays an active model that does not exist.
8. **The nightly Gaussian trainer cannot train.** `auto_train_from_opportunities.py:98-105` builds
   the phase5 command with `--train` but never `--gaussian`; per `phase5_calibration.py:1380-1381`
   auto-select is skipped when `--train` is explicit, and `:1393-1400` then hard-exits rc=1.
9. **`get_active_gaussian()` is hardcoded to EURUSD** (`model_registry.py:637-640`) while
   `__active__` has no EURUSD key → `load_active_gaussian_scorer` always returns `NoOpScorer`
   (this is *why* gap #3 holds). Latent second defect: `:836-839` resolves `model_file` without
   the `models/`-prefix strip the other two loaders apply.

---

## Rebuild / retrain matrix

| Action | Allowed now? | Condition |
|---|---|---|
| Retrain ML Gaussian because of CH-002 rename | **NO** | Live path unaffected |
| Switch `gaussian_impl` to `ml` | **NO** without ΔG001 | Authority Ladder §6.5 |
| Promote new registry version | **NO** without Phase-5 + PromotionManager | Existing governance |
| Research ablation (heuristic weight / shadow_ml) | YES (measure-only) | Docs/research authority only |

---

## Key file map

| Role | Path |
|---|---|
| Live engine | `src/engines/heuristic_gaussian_engine.py` |
| ML engine | `src/engines/ml_gaussian_engine.py` |
| Selection | `src/core/engine_runner.py:_get_gaussian_engine` |
| Train pipeline (unexercised) | `src/training/train_pipeline.py:run_gaussian_update` |
| **Builder of record** | `scripts/training/phase5_calibration.py:run_calibration` (F-060) |
| Trainer | `src/training/trainer.py:train_gaussian` |
| Parameterization floor | `tests/test_gaussian_live_parameterization.py` |
| Pivotality ablation | `scripts/research/diagnose_gaussian_pivotality.py` |
| Registry | `models/gaussian_registry.json` |
| Config | `configs/production/v2_multi_2026_04.json` → `gaussian_impl` |
| Intent topic | `docs/topics/model-intent-and-feature-ownership.md` |
| active_models | `active_models.yaml` → `gaussian:` |

---

## Next subsystem

**ZoneGate** lineage audit (active hard gate + trained `models/zone_registry.json`).

```text
NEXT = ZoneGate training→artifact→inference→runtime→marginal-value audit
DO_NOT = retrain Gaussian, enable ml path, or reopen CRT
```
