> Created: 2026-05-19 · Updated: 2026-05-19 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Fix: Post-Training Verification Path Inconsistency

## Context

After `phase5_calibration.py` training completes, it runs a verification step that attempts to reload the saved model. When `--instrument` is supplied, models are saved to a subdirectory (`models/{INSTRUMENT}/{RUN_ID}/model_name.ext`), but the verification functions strip the path down to just the **filename** via `.name` before passing it to the loader. The loaders (`load_gaussian_model`, `load_tradenet_model`) prepend `models/` automatically, so they reconstruct `models/model_name.ext` — a path that does not exist. This causes two `[FAIL !!]` lines every time an instrument-scoped run completes, even though the models themselves are saved correctly and the registry entry is valid.

## Root Cause

| Location | Code | Problem |
|---|---|---|
| `phase5_calibration.py:815` | `load_gaussian_model(model_path.name)` | `.name` strips the subdirectory |
| `phase5_calibration.py:902` | `load_tradenet_model(model_path.name)` | same |

`save_gaussian_model` returns `Path("models/EURUSD/20260519_002117/gaussian_v6_2026_05_eur.json")`. The load functions expect a name **relative to `models/`**, so the correct argument is `str(model_path.relative_to(Path("models")))` = `"EURUSD/20260519_002117/gaussian_v6_2026_05_eur.json"`.

Using `.relative_to(Path("models"))` also handles the no-instrument case cleanly:  
`Path("models/gaussian_v6.json").relative_to(Path("models"))` → `"gaussian_v6.json"` (same as `.name` today, no regression).

## Files to Modify

- `scripts/training/phase5_calibration.py` — lines **815** and **902**

## Exact Changes

### Change 1 — Gaussian verification (line 815)
```python
# BEFORE
loaded_model, loaded_scaler, _ = load_gaussian_model(model_path.name)

# AFTER
loaded_model, loaded_scaler, _ = load_gaussian_model(
    str(model_path.relative_to(Path("models")))
)
```

### Change 2 — TradeNet verification (line 902)
```python
# BEFORE
loaded_model = load_tradenet_model(model_path.name)

# AFTER
loaded_model = load_tradenet_model(
    str(model_path.relative_to(Path("models")))
)
```

`Path` is already imported at the top of the file (used throughout).

## Verification

After the fix, re-run the same command:

```powershell
py -3.12 scripts/training/phase5_calibration.py `
    --opportunities logs/EURUSD/20260519_002117/opportunities.jsonl `
    --version v6_2026_05_eur `
    --instrument EURUSD `
    --base . `
    --train --tradenet
```

Expected outcome:
- `[PASS OK]  Load saved model` (Gaussian)
- `[PASS OK]  Gaussian end-to-end pipeline`
- `[PASS OK]  Load saved TradeNet model`
- `[PASS OK]  TradeNet end-to-end pipeline`

Also verify no regression for the no-instrument path by running without `--instrument` (model saved directly under `models/`).
