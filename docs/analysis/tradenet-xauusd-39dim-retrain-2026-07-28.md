# TradeNet XAUUSD 39-dim Retrain — 2026-07-28

**Authority:** research_only · shadow register only · **not promoted** · no spine wire-up  
**Why:** Live `TradeNetV2` fail-closes when `feature_dim != CANONICAL_FEATURE_DIM` (39). Prior XAU envelope was 38-dim.

## Changes

| Surface | Change |
|---|---|
| `scripts/training/train_trade_net_v2.py` | `INPUT_DIM = CANONICAL_FEATURE_DIM` (39); stop dropping `macd_hist_raw` |
| Labels | Added stream outcome `TP_HIT` to `_TP1_OUTCOMES` (XAU opportunities use this, not `TP1_HIT`) |
| Promotion | `--shadow` only — no active promotion |

## Artifacts

| Version | Path | feature_dim | Notes |
|---|---|---:|---|
| `v2_xauusd_20260728T060451` | `models/XAUUSD/20260728T060451/…json` | 39 | First 39-dim; TP1 labels all-zero (pre TP_HIT fix) |
| **`v2_xauusd_20260728T060800`** | `models/XAUUSD/20260728T060800/tradenet_v2_XAUUSD_20260728T060800.json` | **39** | **Preferred** — TP_HIT mapped |

## Training data

- Source: `logs/XAUUSD/xauusd_phase1_20260723/opportunities.jsonl`
- Usable/closed: 94,332
- Matrix: `(94332, 39)`

## Metrics (v2_xauusd_20260728T060800)

| Head | pos_rate | AUC |
|---|---:|---:|
| p_tp1 | 0.0142 | **0.828** |
| p_tp2 | 0.0 | 0.5 (no TP2 outcomes in stream) |
| p_survives_be | 0.208 | 0.616 |

## Verification

- `TradeNetV2(model_path=…)._mode == "v2"` (dim match live 39)
- Offline runner: `n_ok=50` with `--artifact` pointing at the 39-dim envelope (first artifact)

## Explicit non-claims

- **Not** production-wired (F-005 / TN_QUAL_V1 still gate wire-up)
- **Not** promoted to `__active__` for XAUUSD
- p_tp2 remains uninformative under this opportunity stream
- Opportunity labels remain stream-outcome based (F-022 class risk) — not clean-label forward_walk

## How to score

```powershell
$env:PYTHONPATH = "src"
python scripts/research/run_model_offline.py `
  --model tradenet `
  --csv data/mt5/XAUUSD_M15.csv `
  --instrument XAUUSD `
  --out-dir results/model_runners `
  --limit 200 `
  --artifact models/XAUUSD/20260728T060800/tradenet_v2_XAUUSD_20260728T060800.json
```

## Next (if economic authority is desired)

1. Clean-label rebuild (forward_walk) for y_tp1/y_tp2  
2. TN_QUAL_V1 protocol before any fusion neural_fn wire  
3. Optional promote only after OOS ΔG001
