> Created: 2026-05-16 · Updated: 2026-05-16 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# RR Model Training Audit — D:\Tradelatest

**Date:** 2026-05-16  
**Scope:** RR model training existence, dataset generation pipeline, wiring, and promotion.

---

## FINDINGS

### 1. Which file actually trains the RR model?

**PRIMARY:** `scripts/training/train_rr_model.py` (149 lines)  
- CLI entry point. Orchestrates the full RR training sequence.  
- Imports `RRPatternTrainer` from `src/config_layer/rr/rr_pattern_miner.py`.  
- Imports `load_dataset` from `src/config_layer/rr/rr_dataset_builder.py`.  
- Imports `register_rr_model`, `promote_rr`, `get_active_rr_entry` from `src/core/model_registry.py`.  

**TRAINER CLASS:** `src/config_layer/rr/rr_pattern_miner.py` — `RRPatternTrainer.train()` (lines 62–149)  
- Fits `sklearn.linear_model.Ridge` (alpha=10.0, configurable) on (X, y_rr).  
- Fits `sklearn.covariance.LedoitWolf` for Mahalanobis confidence estimation.  
- Trains a Gaussian Naive Bayes (manually implemented) on (X, y_win).  
- Serialises to JSON state dict for `NanoInferenceEngine` (pure-Python inference; no sklearn at predict-time).  
- Requires `numpy` + `scikit-learn` at train-time only.  
- **No xgboost. No lightgbm. No PyTorch.**

---

### 2. Is training integrated into train_pipeline.py?

**NO — RR training is NOT integrated into `src/training/train_pipeline.py`.**

`train_pipeline.py` has two entry points:
- `run_training_pipeline()` — TradeNet / binary-label (PyTorch) path.  
- `run_gaussian_update()` — 8-step Gaussian model update (GaussianNB + StandardScaler via `trainer.py`).

`run_gaussian_update()` calls `validate_dataset_integrity` from `rr_dataset_builder` (step 2) and saves a dataset snapshot, but **does NOT call `RRPatternTrainer`**. It trains the Gaussian model, not the RR model.

The RR training pipeline is a **standalone CLI** (`train_rr_model.py`) with no invocation from `train_pipeline.py`.

---

### 3. Was train_rr_model.py renamed or deleted?

**Neither.** The file **EXISTS** at `scripts/training/train_rr_model.py`. It is 149 lines, functional, and wired to the correct imports. It was **never deleted or renamed**.

---

### 4. Is rr_dataset.json ever consumed?

**Conditionally — and currently BLOCKED by three independent guards:**

| Guard | Location | Effect |
|-------|----------|--------|
| `load_dataset()` shape check | `rr_dataset_builder.py` | `11 != 35 features → ValueError` at row 0 |
| `validate_dataset_integrity()` | `rr_dataset_builder.py` | Raises if all `y_rr == 0.0` (all 430 samples are 0.0) |
| `rr_fusion.enabled = false` | Production config | No live path instantiates `RRFusionLayer` |
| `models/rr_model.json` | Filesystem | **MISSING** — graceful passthrough even if enabled |

**`models/rr_dataset.json` is DEGENERATE:**  
- 430 samples, 11 features (stale schema; canonical is 35).  
- All `y_rr = 0.0`, all `y_win = 0`. Labels were never populated.  
- Caused by old `rr_pattern_miner.py` with phantom `RR_SCHEMA` import — module failed silently, wrote zero-filled targets.  
- Documented in `docs/RR_DATA_INTEGRITY_AUDIT_2026_04_30.md`.  
- **Do NOT train on this file.**

---

## EXECUTION FLOW (end-to-end, current state)

```
STEP 1 — Build dataset (PREREQUISITE — MISSING VALID OUTPUT)
  scripts/data/build_rr_dataset.py
    └─ imports: build_dataset(), save_dataset(), validate_dataset_integrity()
                from src/config_layer/rr/rr_dataset_builder.py
    └─ build_dataset(trades, df)  [line 264 of rr_dataset_builder.py]
         ├─ extract_features()   → 35-dim vector per trade
         ├─ extract_target()     → (y_rr, y_win) from pnl_rr_net / rr_achieved
         └─ validate_dataset_integrity(X, y_rr, y_win)
    └─ save_dataset() → models/rr_dataset_{version}.json

STEP 2 — Train
  scripts/training/train_rr_model.py [--dataset <path>] [--version <ver>] [--promote]
    └─ load_dataset(path)
         └─ rr_dataset_builder.load_dataset()
              └─ validate_dataset_integrity()  ← BLOCKS on degenerate data
    └─ RRPatternTrainer().train(X, y_rr, y_win)
         ├─ Ridge.fit(Xs, y_rr)              ← sklearn
         ├─ LedoitWolf.fit(Xs)               ← sklearn
         └─ GaussianNB (manual)
    └─ trainer.save("models/rr_model_{version}.json")
    └─ register_rr_model(version, path, metrics)
         └─ src/core/model_registry.py → rr_registry.json

STEP 3 — Promote (optional, --promote flag)
  train_rr_model.py --promote
    └─ promote_rr(version)
         └─ model_registry.RRModelRegistry.promote()  [lines 865–877]
              └─ writes active pointer in rr_registry.json
    └─ shutil.copy2(output, "models/rr_model.json")   ← canonical path for engine_runner
```

---

## COMMAND TO RETRAIN FROM SCRATCH

```bash
# Step 1: Build a fresh RR dataset from real trade logs
# (Must have valid fusion JSONL logs with ENTRY/EXIT pairs)
python scripts/data/build_rr_dataset.py \
    --log-dir logs/ \
    --output models/rr_dataset_202505_v1.json

# Step 2: Train the model
cd D:\Tradelatest
python scripts/training/train_rr_model.py \
    --dataset models/rr_dataset_202505_v1.json \
    --version 202505_v1 \
    --promote \
    --zero-price-features
```

**PREREQUISITE CHECK before Step 2:**
```bash
python -c "
from src.config_layer.rr.rr_dataset_builder import load_dataset
X, y_rr, y_win = load_dataset('models/rr_dataset_202505_v1.json')
print(f'n={len(X)}, n_feat={len(X[0])}, y_rr_nonzero={sum(1 for y in y_rr if y != 0.0)}')
"
```
If `y_rr_nonzero == 0` → dataset is degenerate. Do NOT proceed.

---

## DEPENDENCY GRAPH

```
rr_dataset_builder.py
    ├─ extract_features()      ← features/feature_schema.CANONICAL_FEATURE_DIM (35)
    ├─ extract_target()        ← reads pnl_rr_net / rr_achieved / computed from trades
    ├─ build_dataset()         ← called by build_rr_dataset.py, run_gaussian_update()
    ├─ save_dataset()          ← called by build_rr_dataset.py
    ├─ load_dataset()          ← called by train_rr_model.py, model_registry.py
    └─ validate_dataset_integrity() ← called by all of the above

rr_pattern_miner.py
    ├─ RRPatternTrainer.train(X, y_rr, y_win)
    │       ├─ sklearn.linear_model.Ridge
    │       └─ sklearn.covariance.LedoitWolf
    ├─ RRPatternTrainer.save(path)
    ├─ NanoInferenceEngine         ← pure Python, no sklearn at runtime
    └─ train_and_save()            ← convenience wrapper (not called by CLI)

train_rr_model.py  [scripts/training/]
    ├─ rr_dataset_builder.load_dataset()
    ├─ RRPatternTrainer.train()
    ├─ RRPatternTrainer.save()
    ├─ model_registry.register_rr_model()
    └─ model_registry.promote_rr()

model_registry.py  [src/core/]
    └─ RRModelRegistry
            ├─ register_rr_model()    → rr_registry.json
            └─ promote_rr()           → sets active version + writes rr_model.json

rr_engine.py  [src/engines/]
    └─ loads NanoInferenceEngine from models/rr_model.json at runtime

rr_fusion.py  [src/config_layer/rr/]
    └─ RRFusionLayer — wraps NanoInferenceEngine
       CURRENTLY DISABLED: rr_fusion.enabled = false in production config
```

---

## MISSING PIPELINE PIECES

| Gap | Severity | Detail |
|-----|----------|--------|
| `models/rr_dataset.json` is degenerate | CRITICAL | 430 samples, all y_rr=0.0, 11-feature stale schema. Unusable. |
| `models/rr_model.json` is MISSING | HIGH | Engine passthrough; RR scoring contributes nothing to fusion |
| `rr_fusion.enabled = false` | HIGH | Even if model existed, RRFusionLayer is disabled in prod config |
| RR training not in `train_pipeline.py` | MEDIUM | Isolated CLI; no integration gate (Phase-5 calibration) before registration |
| No Phase-5 gate on RR training | MEDIUM | `train_rr_model.py` skips calibration gate that Gaussian path has |
| `build_rr_dataset.py` source unknown | MEDIUM | Script exists but source of trade logs (valid ENTRY/EXIT pairs) is unclear |
| `y_rr` label extraction depends on field presence | LOW | `extract_target()` has 3-level priority; missing `pnl_rr_net` → zeros |

---

## DEAD / UNWIRED SCRIPTS

| Script | Status |
|--------|--------|
| `scripts/data/build_rr_dataset.py` | **Wired** but produces no valid output (degenerate dataset) |
| `scripts/training/train_rr_model.py` | **Wired** but cannot execute (dataset blocks at `load_dataset()`) |
| `models/rr_dataset.json` | **Dead** — degenerate, blocked by 3 guards, must be deleted/quarantined |

---

## IS MODEL PROMOTION FUNCTIONAL?

**Architecturally YES. Practically NO.**

- `model_registry.RRModelRegistry.promote()` (lines 865–877) is implemented.  
- `promote_rr(version)` convenience function exists in `src/core/model_registry.py`.  
- `train_rr_model.py --promote` calls it and copies to canonical `models/rr_model.json`.  
- `control_plane/registry.py` registers `training.train_rr_model` as a control-plane command.  

**Blocker:** Training cannot run because `load_dataset()` raises `ValueError` on the only available dataset (degenerate shape + all-zero targets). No valid `rr_model.json` can be produced until a valid dataset is built.

**Promotion chain is functional end-to-end once a valid dataset exists.**

---

## ML LIBRARIES USED

| Library | Usage | File |
|---------|-------|------|
| `sklearn.linear_model.Ridge` | RR regression | `rr_pattern_miner.py:95–96` |
| `sklearn.covariance.LedoitWolf` | Mahalanobis confidence | `rr_pattern_miner.py:124–125` |
| `sklearn.cluster.KMeans` | Zone registry (unrelated) | `scripts/analysis/zone_registry_builder.py:5` |
| numpy | Matrix ops in trainer | `rr_pattern_miner.py:69` |
| xgboost | **NOT PRESENT** | — |
| lightgbm | **NOT PRESENT** | — |
| PyTorch | TradeNet path only | `src/training/trainer.py` |
