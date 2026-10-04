# RR Pattern Miner — 39-dim retrain + confidence gate (2026-07-28)

**Authority:** research / architecture · **rr_fusion remains `enabled:false`** · no ΔG001 · no economic promote  
**Active config:** `v2_multi_2026_04`

---

## Deliverables

| Artifact | Path |
|---|---|
| Dataset (39-dim) | `models/XAUUSD/20260728_v39/rr_dataset.json` (n=94,332) |
| Model (39-dim) | `models/XAUUSD/20260728_v39/rr_model_20260728_v39_xau.json` |
| Gate calibration | `results/rr_confidence_probe/rr_v39_xau_gate_calibration.json` |
| Config updates | `configs/production/v2_multi_2026_04.json` → `rr_model` + `engine_runner.rr_fusion` paths/gate |

## Retrain

| Item | Value |
|---|---|
| Source | `logs/XAUUSD/xauusd_phase1_20260723/opportunities.jsonl` |
| Features | **39** = `CANONICAL_FEATURE_DIM` |
| Zeroed indices (price de-anchor) | `[0,1,2,3,4,7,8,16,17,27,28]` (v4: body_size=27, candle_range=28) |
| n_train | 94,332 |
| effective_dof | 28 (39 − 11 zeros) |
| in-sample ridge corr(y_rr) | ~0.098 (descriptive, labels stream-based F-022 risk) |

CLI:

```text
python scripts/data/build_rr_dataset.py --opportunities logs/XAUUSD/.../opportunities.jsonl \
  --output models/XAUUSD/20260728_v39/rr_dataset.json --version 20260728_v39_xau --instrument XAUUSD

python scripts/training/train_rr_model.py --dataset models/XAUUSD/20260728_v39/rr_dataset.json \
  --version 20260728_v39_xau --instrument XAUUSD --zero-price-features \
  --output models/XAUUSD/20260728_v39/rr_model_20260728_v39_xau.json
```

## Gate work (F-044)

| Mode | In-sample bypass (train set) |
|---|---|
| **legacy_scalar** (old default) | **1.0 (100%)** — gate still broken for this dof |
| **percentile** `d_sq_cut=40.4212` | **~0.10 (10%)** target |

Config now:

```json
"confidence_gate": {
  "mode": "percentile",
  "d_sq_cut": 40.4212,
  "target_bypass_fraction": 0.10,
  ...
}
```

Fresh-process verify (5000-row sample): bypass ≈ **8.2%**, success ≈ **91.8%**, `RRFusionLayer.is_loaded=True`, `n_features=39`.

Also set `engine_runner.rr_fusion.full_feature_vector: true` so a future enable feeds the full vector (not the 3-feature stub).

## Explicit non-changes

| Item | Status |
|---|---|
| `engine_runner.rr_fusion.enabled` | **still false** |
| Live fusion RR slot | still **RREngine candle polarity** |
| ΔG001 / promote to decision authority | **none** |
| Overwrite of quarantined `models/rr_model.json` | **not done** (new path only) |

## Code hygiene

- `scripts/training/train_rr_model.py`: price zero indices updated for schema v4 (`candle_range=28`).

## How to smoke offline

```powershell
$env:PYTHONPATH="src"
python scripts/research/run_model_offline.py --model rr_trained `
  --csv data/mt5/XAUUSD_M15.csv --instrument XAUUSD `
  --out-dir results/model_runners --limit 100 `
  --artifact models/XAUUSD/20260728_v39/rr_model_20260728_v39_xau.json
```

Note: offline `rr_trained` adapter bypasses the fusion gate for raw ML views; gate applies on `NanoInferenceEngine.predict` / `RRFusionLayer` when used.

## Re-enable checklist (future, not done)

1. Shadow A/B with `rr_fusion.enabled=true` + this model path  
2. Measure ΔG001 / ledger identity  
3. Only then promote authority
