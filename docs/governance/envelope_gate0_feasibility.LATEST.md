# EnvelopeNet ENV-0 Feasibility Report

| Field | Value |
|-------|--------|
| run_id | `20260721T220948Z` |
| design | `ENV_ARCH_V1` (accepted) |
| created_utc | 2026-07-21T22:09:50.923494+00:00 |
| instrument | BNBUSDT |
| **verdict** | **FEASIBLE_GO** |
| authority | NONE — GATE-0 / ENV-0 feasibility only; no train/wire/promote |

## Purpose

Is a clean-label path for EnvelopeNet operating-boundary targets **practical** and **worth implementing**?
Labels: MFE/MAE (R), holding bars, time-to-MFE — via `horizon_excursion` + `forward_walk`, never stream MFE alone.

## Pilot quantiles (exit-agnostic envelope)

```json
{
  "n_pilot": 150,
  "quantiles": {
    "mfe_r": {
      "q50": 2.96665,
      "q80": 14.6471,
      "q20": 0.99034
    },
    "mae_r_heat": {
      "q50": 2.96665,
      "q80": 14.6471,
      "q20": 0.99034
    },
    "holding_bars_walk": {
      "q50": 3.0,
      "q80": 12.0
    },
    "time_to_mfe_est": {
      "q50": 2.0,
      "q80": 8.6,
      "n": 148
    }
  },
  "timeout_rate": 0.0,
  "mean_mfe_r_when_survives_be": 8.4269,
  "mean_mfe_r_when_not": 3.5463,
  "label_defs": {
    "y_mfe_r": "horizon_excursion mfe_r (exit-agnostic, primary envelope)",
    "y_mae_r_heat": "abs(horizon_excursion mae_r)",
    "y_holding_bars": "forward_walk duration_candles under intrabar_fixed + unit SL/TP",
    "y_time_to_mfe": "bars until path MFE first attained",
    "y_survives_be_link": "forward_walk.reached_1r (TradeNet head; correlated with envelope mfe)"
  },
  "non_constant": true,
  "feasible_labels": true
}
```

## Shared logistics (with TradeNet GATE-0)

```json
{
  "census": {
    "n_raw_scanned": 24999,
    "n_geometry": 24999,
    "n_feature_complete": 24999,
    "n_stream_outcome": 24999,
    "outcome_top": [
      [
        "SL_HIT",
        24676
      ],
      [
        "TP_HIT",
        315
      ],
      [
        "TIMEOUT",
        8
      ]
    ],
    "n_candles": 70080,
    "n_ts_match": 24999,
    "n_future_full": 24999,
    "est_total_lines": 24999,
    "expected_clean_full": 24999
  },
  "pilot": {
    "n": 150,
    "skips": {},
    "exception_count": 0
  },
  "G0-Q1_geometry": true,
  "G0-Q3_ohlcv": true,
  "G0-Q4_features": true,
  "G0-Q5_walk": true,
  "agreement_stream_vs_clean_tp1": 0.6466666666666666
}
```

**ENV-0 verdict: FEASIBLE_GO**

### Effect

- ENV-L clean-label builder **may** start (research only), preferably **shared** with TN GATE-L walk
- Still **forbidden**: spine attach, planner TTL rewrite, fusion coherence channel, train promote

## Distinction check (non-duplication)

- TradeNet pilot heads: Bernoulli y_tp1 / y_survives_be (and tp2 surrogate)
- Envelope pilot heads: continuous mfe_r / mae_r_heat / holding_bars / time_to_mfe
- Related horizon, different information kind — design non-duplication rule held in pilot schema

TN GATE-0 verdict on same run: **FEASIBLE_GO** (`docs/governance/tradenet_gate0_feasibility.LATEST.md`).
