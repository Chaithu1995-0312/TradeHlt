> Created: 2026-05-22 · Updated: 2026-05-22 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# ROI-First Refinement: Phases P6.1 → P6.4 (Gaussian → Regime → TradeNet → Joint, plus ZoneGate / RR / BitNet)

## Context

Current bottleneck on ROI is **calibration + routing quality**, not raw model capacity. Gaussian is the active live RR/expectancy path; downstream engines (TradeNet, BitNet) inherit Gaussian's label noise. So we refine **in dependency order — cleaner labels first, downstream models second** — instead of the previous parallel/independent refinement of Gaussian and TradeNet.

Order: Gaussian (P6.1) → Regime-aware Gaussian (P6.2) → TradeNet 3-head (P6.3) → Joint optimizer (P6.4), with ZoneGate + RR-engine cleanup running alongside P6.1 and BitNet adaptation held until P6.1–P6.3 stabilize.

Targets:
- `corr_mean > 0.35`, `corr_std < 0.05`, `cal_error < 0.08` (Gaussian)
- `auc_tp2 > 0.65`, `survive_be > 0.70` (TradeNet)
- +10–25% expectancy stability (regime split)

---

## Reconnaissance Summary (what already exists — reuse, don't reinvent)

| Layer | Status | Key files |
|-------|--------|-----------|
| **Gaussian scorer** | Live; `phase5_calibration` section exists in prod config (`cv_n_folds=2`, `max_cal_error=0.25`) | [src/config_layer/crt_gaussian_scorer.py](src/config_layer/crt_gaussian_scorer.py), [src/training/evaluator.py](src/training/evaluator.py) |
| **RR class weights** | **Hardcoded** `[0.0,0.5,1.5,2.5]` | [src/training/trainer.py:43](src/training/trainer.py:43) |
| **Feature schema** | 38-dim (v3.0), v2.0=35 sentinel preserved | [src/features/feature_schema.py:44](src/features/feature_schema.py:44) |
| **Regime classifier** | 4 regimes (TRENDING / RANGING / HIGH_VOLATILITY / UNKNOWN); 5-bar cooldown; exposed as feature idx 30 | [src/regime/regime_classifier.py:25](src/regime/regime_classifier.py:25) |
| **Regime-aware fusion** | `FusionConfig.regime_fusion_weights` already wired; `FusionEngine.compute(regime=...)` already routes weights | [src/core/fusion_engine.py:164](src/core/fusion_engine.py:164), [src/core/engine_runner.py:665](src/core/engine_runner.py:665) |
| **TradeNet v2** | **Already 3-head** (`p_tp1`, `p_tp2`, `p_survives_be`); `--shadow` flag exists; weights `(0.4,0.4,0.2)` hardcoded at line 59 | [scripts/training/train_trade_net_v2.py:59](scripts/training/train_trade_net_v2.py:59), [scripts/training/train_trade_net_v2.py:215](scripts/training/train_trade_net_v2.py:215) |
| **ZoneGate** | K-means trained clusters; per-instrument registry; multiple soft-score / cluster constants hardcoded in engine | [src/engines/zone_gate_engine.py:86](src/engines/zone_gate_engine.py:86), [scripts/analysis/zone_registry_builder.py](scripts/analysis/zone_registry_builder.py) |
| **RR engine (live)** | Candle-polarity index (NOT forward RR); 4 hyperparams already externalized | [src/engines/rr_engine.py:37](src/engines/rr_engine.py:37), `rr_model` config section |
| **BitNet** | Fail-closed schema; per-regime thresholds in `bitnet_thresholds.json` | [src/bitnet/bitnet_runner.py:40](src/bitnet/bitnet_runner.py:40) |
| **Promotion gate** | `ConfigValidator.validate()` w/ hard+soft gates; `score_threshold=0.15`, `max_drawdown_pct=0.35` | [src/config_layer/config_validator.py:287](src/config_layer/config_validator.py:287), [src/governance/promotion_manager.py:97](src/governance/promotion_manager.py:97) |
| **Registries** | All support `instrument` + `run_id` fields → no schema change needed for per-(instrument,regime) entries | `models/{gaussian,rr,tradenet,zone_gate}_registry.json` |

---

## Phase P6.1 — Gaussian refinement (PRIMARY, ROI gate)

**Goal:** raise `corr_mean > 0.35`, drop `corr_std < 0.05`, drop `cal_error < 0.08`.

### 1.1 Externalize hardcoded knobs
- [src/training/trainer.py:43](src/training/trainer.py:43) `_RR_WEIGHTS = [0.0, 0.5, 1.5, 2.5]` → read from `phase5_calibration.rr_class_weights`. Accept either:
  - explicit list (e.g., `[0.0, 0.5, 1.5, 2.5]`), or
  - sentinel `"auto"` → compute per-run from observed `pnl_rr_net` quantiles (25/50/75th percentile boundaries; clamp class-0 anchor at 0.0).
- Add `phase5_calibration.train_ratio` (default 0.70) — replaces implicit complement of `val_ratio`. Allowed sweep: 0.60–0.85.
- Add `phase5_calibration.variance_floor` (default 1e-4) — minimum per-class variance to prevent overconfident calibration when a class has <50 samples.
- Add `phase5_calibration.calibration_threshold` (default 0.50, today inside `gaussian_scorer.execute_p`) — promote to optimizer-visible knob so the sweep can co-tune execute_p with class weights.
- Bump `phase5_calibration.cv_n_folds` 2 → 5 (config-only change; no code change needed).
- Flip `phase5_calibration.require_cv_stable` false → true once corr_std target is met.

### 1.2 Feature pruning (38 → ~28)
- Add `phase5_calibration.feature_subset` (default `null` = full 38). When provided, [src/features/dataset_builder.py](src/features/dataset_builder.py) `extract_feature_vector` returns the indexed subset.
- Prune candidates determined post-hoc from a single Gaussian fit's feature-correlation matrix; never edit `CANONICAL_FEATURES` (would invalidate baseline + every registered model).
- Schema-hash impact: subset is captured *per registered model* in registry `feature_schema` field — no global schema-hash invalidation.

### 1.3 Tighten promotion gate
- In `configs/production/v1_multi_2026_03.json` `config_validator` section: drop `max_cal_error` 0.25 → 0.08, add `min_corr_mean` 0.35, `max_corr_std` 0.05.
- Mirror gates in `ConfigValidator._fitness_score()` so promotion *fails* when calibration regresses, not just warns.

### 1.4 Tuner sweep harness
- Extend [src/training/trainer.py](src/training/trainer.py) sweep loop to read `phase5_calibration.sweep` block (already adjacent to existing tuner config). Sweep axes: `train_ratio`, `rr_class_weights` mode (explicit vs auto), `variance_floor`, `calibration_threshold`, `feature_subset`. Grid is bounded — keep under 36 combos per instrument per run.

### 1.5 Files to modify
- [src/training/trainer.py](src/training/trainer.py) — externalize `_RR_WEIGHTS`, add sweep loop entry
- [src/training/evaluator.py](src/training/evaluator.py) — emit `corr_std` alongside `corr_mean`
- [scripts/training/phase5_calibration.py](scripts/training/phase5_calibration.py) — wire `feature_subset` + `variance_floor`
- [src/config_layer/config_validator.py](src/config_layer/config_validator.py) — new hard gates
- [configs/production/v1_multi_2026_03.json](configs/production/v1_multi_2026_03.json) — `phase5_calibration.*` keys
- Re-hash config: `python scripts/maintenance/_compute_hash.py`

---

## Phase P6.2 — Regime-aware Gaussian (per (instrument, regime) entries)

**Goal:** +10–25% expectancy stability by training a Gaussian per regime, dispatched at inference using existing `RegimeClassifier` output.

### 2.1 Registry layout (no schema change)
Reuse existing `instrument` field; add a `regime` field as separate column. Naming convention:

```
gaussian_EURUSD_TRENDING
gaussian_EURUSD_RANGING
gaussian_EURUSD_HIGH_VOLATILITY
gaussian_EURUSD_UNKNOWN   # always falls back to RANGING per RegimeClassifier
```

Each entry is **independently promotable** with its own `ValidationReport`. Rollback is per-(instrument, regime).

### 2.2 Training partition
- Extend [scripts/training/phase5_calibration.py](scripts/training/phase5_calibration.py) to:
  - Group historical opportunities by regime (regime is already in `CANONICAL_FEATURES` idx 30, so it's already in opportunity logs).
  - Skip any regime bucket with fewer samples than `phase5_calibration.min_samples_per_regime` (default 300).
  - Train one Gaussian per (instrument, regime), reusing the P6.1 sweep harness.
- Each model writes its own envelope; `models/gaussian_registry.json` gets one entry per (instrument, regime).

### 2.3 Inference dispatch
- [src/engines/heuristic_gaussian_engine.py](src/engines/heuristic_gaussian_engine.py) `GaussianRegistry`:
  - Currently picks model by `instrument`. Extend to pick by `(instrument, regime)`, falling back to `(instrument, "*")` then global.
- Caller: `EngineRunner` already detects `current_regime` at [src/core/engine_runner.py:665](src/core/engine_runner.py:665) before fusion. Pass it down into the Gaussian engine call (currently passes only feature vector) — a small signature change.

### 2.4 Promotion
- Per-regime promotion runs the same `ConfigValidator` gates, but on the regime-filtered trade subset (not on global metrics).
- Add `governance.regime_promotion_policy`: `"all_or_nothing"` vs `"per_regime"` (default `per_regime` — atomic per regime, mixed live state is OK because regime is mutually exclusive at any given bar).

### 2.5 Files to modify
- [scripts/training/phase5_calibration.py](scripts/training/phase5_calibration.py) — regime partitioning
- [src/engines/heuristic_gaussian_engine.py](src/engines/heuristic_gaussian_engine.py) — regime-aware lookup
- [src/core/engine_runner.py](src/core/engine_runner.py) — pass `regime` into Gaussian engine call
- [src/governance/promotion_manager.py](src/governance/promotion_manager.py) — per-regime promotion path
- `configs/production/v1_multi_2026_03.json` — `phase5_calibration.min_samples_per_regime`, `governance.regime_promotion_policy`

---

## Phase P6.2b — ZoneGate refinement (parallel with P6.1/P6.2)

**Goal:** externalize hardcoded knobs and add per-instrument re-training cadence.

### Hardcoded → config
- [src/engines/zone_gate_engine.py:88-90](src/engines/zone_gate_engine.py:88) soft-score weights `(0.5, 0.3, 0.2)` → `engine_runner.zone_gate.soft_weights`.
- [src/engines/zone_gate_engine.py:135](src/engines/zone_gate_engine.py:135) cluster spread threshold `0.15` → `engine_runner.zone_gate.cluster_spread_max`.
- [src/engines/zone_gate_engine.py:129](src/engines/zone_gate_engine.py:129) min-neighbours `2` → `engine_runner.zone_gate.min_neighbors`.
- [scripts/analysis/zone_registry_builder.py:53](scripts/analysis/zone_registry_builder.py:53) min cluster size `10` and [scripts/analysis/zone_registry_builder.py:63](scripts/analysis/zone_registry_builder.py:63) `min_score=0.5` → `zone_registry_builder.*`.

### Regime split for zones
- Same per-(instrument, regime) registry layout as Gaussian. Zones in TRENDING differ structurally from RANGING zones; existing global zones smear the boundary.
- Reuse [scripts/analysis/zone_registry_builder.py](scripts/analysis/zone_registry_builder.py) — group profitable trades by `volatility_regime` before KMeans clustering.

### Files to modify
- [src/engines/zone_gate_engine.py](src/engines/zone_gate_engine.py) — read soft-weights + spread from config
- [scripts/analysis/zone_registry_builder.py](scripts/analysis/zone_registry_builder.py) — regime partitioning + config knobs
- `configs/production/v1_multi_2026_03.json` — new `zone_gate` + `zone_registry_builder` subsections

---

## Phase P6.2c — RR engine cleanup (parallel)

The semantic mismatch on `rr_engine.py` (candle polarity, not forward RR) is a known footgun. Resolve in this pass:
- Rename `RREngine` → `CandlePolarityEngine` *inside* the file with backward-compat alias `RREngine = CandlePolarityEngine`.
- Add docstring stating it scores commitment, not expected return. Update `EXPECTED_ENGINES` comment only — do **not** change the registry key `"rr"` (that would invalidate every existing fused result).
- Externalize the 4 already-config-driven knobs (`ridge_alpha`, `drift_threshold`, `confidence_bypass_threshold`, `min_samples`) under the same `phase5_calibration.sweep` so RR ridge regularization gets co-tuned with Gaussian.

### Files to modify
- [src/engines/rr_engine.py](src/engines/rr_engine.py) — docstring + alias (no behaviour change)
- [src/training/trainer.py](src/training/trainer.py) — include `rr_model.ridge_alpha` in sweep when present

---

## Phase P6.3 — TradeNet 3-head as profit miner (shadow only)

**Goal:** use [scripts/training/train_trade_net_v2.py](scripts/training/train_trade_net_v2.py) (already 3-head) as a downstream behaviour miner. Externalize the few remaining hardcoded knobs and backfill missing labels.

### 3.1 MFE backfill (prerequisite)
- New script `scripts/maintenance/backfill_mfe.py`: walks each closed opportunity, re-loads the candle window between `opened_at` and `closed_at`, computes `mfe = max((high-entry)/abs(entry-sl))` for longs (mirror for shorts), writes back to opportunity JSONL.
- Idempotent — skips records already containing `mfe`.
- Verify: post-backfill, `<5%` of closed opportunities should still emit `TRADENET_SURVIVES_BE_UNRESOLVED`.

### 3.2 Externalize head weights & training knobs
- [scripts/training/train_trade_net_v2.py:59](scripts/training/train_trade_net_v2.py:59) `COMPOSITE_WEIGHTS = (0.4, 0.4, 0.2)` → read from new config section `tradenet_v2`:
  ```json
  "tradenet_v2": {
    "head_weights": {"tp1": 0.5, "tp2": 0.5, "survives_be": 0.2},
    "hidden_dims": [32, 16],
    "dropout": 0.20,
    "min_samples": 500
  }
  ```
- Sweep ranges per user spec:
  - `hidden_dims`: `[32,16]`, `[64,32]`
  - `dropout`: 0.10–0.35 (step 0.05)
  - `tp1`/`tp2` heads: 0.4–0.6 (step 0.1)
  - `survives_be`: 0.1–0.3 (step 0.1)
  - `min_samples`: sweep 500 → 2000 (step 500) to find diminishing return knee

### 3.3 Shadow-only deployment
- TradeNet stays under `--shadow` until P6.1 + P6.2 metrics confirm clean upstream. Live promotion gated on:
  - `auc_p_tp1 > 0.65` AND `auc_p_tp2 > 0.65` AND `acc_survives_be > 0.70`
  - No regression vs current live model's `auc_p_tp1`
- Existing `--force-promote` flag stays as escape hatch.

### 3.4 Files to modify
- New: `scripts/maintenance/backfill_mfe.py`
- [scripts/training/train_trade_net_v2.py](scripts/training/train_trade_net_v2.py) — read `tradenet_v2.*` from config
- [configs/production/v1_multi_2026_03.json](configs/production/v1_multi_2026_03.json) — new `tradenet_v2` section, extend `config_validator` with TradeNet shadow gates

---

## Phase P6.3b — BitNet adaptation (HELD until P6.1–P6.3 stable)

BitNet's job is to **compress already-clean intelligence**, not absorb upstream noise. So:
- No architecture retraining in this pass.
- Adapt `bitnet_thresholds.json` per-regime thresholds **after** P6.2 lands: re-compute thresholds from the regime-split Gaussian's calibrated distributions instead of from the global mixed distribution.
- Tunable via `engine_runner.bitnet_main_threshold` per regime → new `engine_runner.bitnet_thresholds_per_regime` block.

### Files to modify
- [src/bitnet/bitnet_runner.py](src/bitnet/bitnet_runner.py) — read per-regime threshold (small change)
- `models/bitnet_thresholds.json` — populate regime-keyed thresholds from P6.2 outputs
- `configs/production/v1_multi_2026_03.json` — `engine_runner.bitnet_thresholds_per_regime`

---

## Phase P6.4 — Joint ROI optimizer

**Goal:** one multi-objective fitness function spanning all 4 (instrument, regime) Gaussian models + their downstream consumers.

### 4.1 New fitness formula
Extend [src/config_layer/config_validator.py](src/config_layer/config_validator.py) `_fitness_score()`:

```
ROI_fitness =
   0.35 * expectancy_rr_norm
 + 0.30 * profit_factor_norm
 + 0.20 * trade_count_norm
 - 0.15 * drawdown_norm
```

Weights become config-driven under `config_validator.roi_fitness_weights`. Old `fitness_weights` retained as fallback (`use_roi_fitness: true|false`).

### 4.2 Cross-regime stability term
Add penalty when expectancy variance across the 4 regime models exceeds `max_regime_expectancy_std` (default 0.15). Promotes consistent performance, not just a single hot regime.

### 4.3 Optimizer loop
- [src/training/trainer.py](src/training/trainer.py) gains a top-level `--joint-optimize` flag. When set, the trainer iterates over all (instrument, regime) tuples once per generation, computes the joint fitness above, and only commits the *whole bundle* if it beats current production.
- Reuses existing `ShadowPromotionGate` for the bundle-vs-prod backtest.

### 4.4 Files to modify
- [src/config_layer/config_validator.py](src/config_layer/config_validator.py) — `_fitness_score` ROI mode
- [src/training/trainer.py](src/training/trainer.py) — joint optimizer entry point
- [src/governance/promotion_manager.py](src/governance/promotion_manager.py) — bundled promotion path
- `configs/production/v1_multi_2026_03.json` — `config_validator.roi_fitness_weights`, `config_validator.max_regime_expectancy_std`

---

## Execution sequencing

```
P6.1 Gaussian externalize + sweep        ──┐
P6.2b ZoneGate externalize + regime split ──┼── parallel (independent file sets)
P6.2c RR engine docstring + sweep entry   ──┘
                  │
                  ▼  (gate: corr_mean>0.35, cal_error<0.08)
P6.2 Regime-aware Gaussian per (instrument, regime)
                  │
                  ▼  (gate: per-regime promotion passes)
P6.3 MFE backfill + TradeNet 3-head shadow sweep
                  │
                  ▼  (gate: auc_tp2>0.65, survive_be>0.70 in shadow)
P6.3b BitNet per-regime threshold refresh
                  │
                  ▼
P6.4 Joint ROI optimizer (bundled promotion)
```

**Do not start P6.2** until P6.1 corr_std target is met — regime splits *amplify* whatever noise the global model has.
**Do not promote TradeNet live** until P6.2 lands — TradeNet inherits Gaussian's label noise.
**Do not retrain BitNet** in this cycle.

---

## Verification

### After P6.1
- `python scripts/training/phase5_calibration.py --train --sweep` → produces sweep summary with `corr_mean / corr_std / cal_error` per combo.
- `python src/config_layer/config_validator.py validate-prod --data-dir data/` → must pass new tighter gates.
- `python src/runtime/baseline_capture.py --label phase6_1` → snapshot.

### After P6.2
- Inspect `models/gaussian_registry.json` for 4 entries per instrument (TRENDING/RANGING/HIGH_VOLATILITY/UNKNOWN).
- `python scripts/auto_train_from_opportunities.py --dry-run` → verify regime dispatch picks correct model per bar.
- Compare per-regime expectancy in backtest output (`BacktestMetrics.distribution["per_regime"]` — add if missing).

### After P6.3 (shadow)
- `python scripts/training/train_trade_net_v2.py --shadow --sweep` → sweep summary.
- Grep `logs/agent_audit.jsonl` for `TRADENET_SURVIVES_BE_UNRESOLVED` count before/after MFE backfill — should drop below 5%.

### After P6.4
- `python src/training/trainer.py --joint-optimize --data-dir data/` → bundle proposal.
- `python src/governance/promotion_manager.py promote --checkpoint results/tuner/checkpoint_joint.json --version v3_<label>_<YYYY_MM> --data-dir data/` → atomic bundle promotion.
- Verify `configs/promotion_log.jsonl` contains a single `PROMOTED` line covering all (instrument, regime) entries.

### Regression suite (every phase)
- `python -m pytest tests/` — full suite must remain green at each phase boundary.
- `python scripts/analysis/compress_logs_for_llm.py --logs logs/**/*.jsonl` — for diff-able training/promotion telemetry.

---

## Out of scope (explicit non-goals)

- No change to `CANONICAL_FEATURES` (would invalidate baseline + every registered model).
- No BitNet architecture retraining.
- No new REST/API surface — control plane stays localhost stdlib.
- No replacement of `rr_engine.py` semantics (only docstring + alias).
- No ORM, no DB — registries remain JSON.

---

## Risk register

| Risk | Mitigation |
|------|-----------|
| Sweep grid explodes combinatorially | Cap to ≤36 combos/instrument/run; tuner already uses `phase2_min_iter` floor. |
| Per-regime sample starvation | `min_samples_per_regime=300` floor; fall back to global Gaussian for that regime if unmet. |
| MFE backfill misreads candle history (lookahead) | Restrict candle window strictly to `[opened_at, closed_at]`; cross-check against existing `exit_reason`. |
| Joint optimizer regresses live ROI on bundle promotion | `ShadowPromotionGate` runs bundle vs prod first; rollback = restore archived configs + re-load. |
| Schema-hash invalidation from feature_subset | Subset is per-model registry field, not global schema mutation. Verified safe. |
| Regime classifier instability flapping models at runtime | Existing 5-bar cooldown already mitigates; verify before P6.2 ships. |
