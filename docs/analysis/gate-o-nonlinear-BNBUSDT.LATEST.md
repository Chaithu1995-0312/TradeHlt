# GATE-O Nonlinear Learnability — TN_ENV_CLEAN_L2

| Field | Value |
|-------|--------|
| created | 2026-07-21T22:33:30.428452+00:00 |
| dataset | `D:\Tradelatest\results\clean_labels\BNBUSDT\20260721T223243Z\clean_labels.jsonl` |
| n_rows_used | 60000 |
| folds | 3 (time-ordered expanding) |
| dataset_sha256 | `0ad3d5502bbe256a…` |
| authority | GATE-O research only — no promote/wire |

## TradeNet binary heads

| Label | base_rate | Lin AUC | NLin AUC | Lift | ECE | Tag |
|-------|-----------|---------|----------|------|-----|-----|
| `y_tp1` | 0.33505 | 0.5015 | 0.5078 | 0.0063 | 0.0062 | **NOISY** |
| `y_tp2` | 0.241817 | 0.5146 | 0.5181 | 0.0035 | 0.017 | **NOISY** |
| `y_survives_be` | 0.5022 | 0.5023 | 0.5006 | -0.0017 | 0.0028 | **NOISY** |

## Envelope regression heads

| Label | y_mean | Lin R² | NLin R² | Spearman IC | Tag |
|-------|--------|--------|---------|-------------|-----|
| `y_mfe_r` | 3.849953 | 0.0161 | -0.0251 | 0.1635 | **CANDIDATE_LEARNABLE** |
| `y_mae_r_heat` | 3.849953 | 0.0161 | -0.0432 | 0.1597 | **CANDIDATE_LEARNABLE** |
| `y_holding_bars` | 6.70155 | 0.0532 | 0.0371 | 0.2682 | **CANDIDATE_LEARNABLE** |
| `y_time_to_mfe` | 4.722749 | 0.033 | 0.0378 | 0.1872 | **CANDIDATE_LEARNABLE** |

## Architectural answers

1. Envelope more learnable than outcomes? **True**
2. Nonlinear changes prior conclusions? **False**
3. Fundamentally noisy: `['y_tp1', 'y_tp2', 'y_survives_be']`
4. Deserve production models: NONE yet — GATE-O is learnability only; production needs GATE-S/P + ΔG001
5. Diagnostic-only candidates: `['y_tp1', 'y_tp2', 'y_survives_be']`
6. Multi-head envelope still justified? **True**

### TradeNet GO/NO-GO: **NO_GO — all outcome heads noisy under nonlinear probe**
### EnvelopeNet GO/NO-GO: **GO_RESEARCH — multi-head EnvelopeNet offline training eligible**

### Regime / side AUC (in-sample descriptive — not CV)

- `y_tp1`: {'low_vol': 0.5731, 'mid_vol': 0.5612, 'high_vol': 0.5448, 'long': 0.5558, 'short': 0.5641}
- `y_tp2`: {'low_vol': 0.6628, 'mid_vol': 0.6404, 'high_vol': 0.6227, 'long': 0.636, 'short': 0.6484}
- `y_survives_be`: {'low_vol': 0.5021, 'mid_vol': 0.5019, 'high_vol': 0.5051, 'long': 0.5231, 'short': 0.4833}

---

GATE-O does **not** authorize training promotion, shadow weight, or spine wire.
