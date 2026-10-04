# TradeNet GATE-0 Feasibility Report

| Field | Value |
|-------|--------|
| run_id | `20260721T220948Z` |
| created_utc | 2026-07-21T22:09:50.923494+00:00 |
| instrument | BNBUSDT |
| opportunities | `logs/BNBUSDT/bnbusdt_training_20260524/opportunities.jsonl` |
| candles | `data/BNBUSDT_M15.csv` |
| exit_model | `intrabar_fixed` max_forward=40 |
| **verdict** | **FEASIBLE_GO** |
| authority | NONE — GATE-0 / ENV-0 feasibility only; no train/wire/promote |

## Census

```json
{
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
}
```

## G0-Q1 … G0-Q9

### G0-Q1 — trade_decision population keys exist?

- **practical:** `True`
- **evidence:**

```json
{
  "source": "logs/BNBUSDT/bnbusdt_training_20260524/opportunities.jsonl",
  "n_raw_scanned": 24999,
  "unit_keys_present": [
    "timestamp",
    "direction",
    "entry",
    "sl",
    "tp",
    "features",
    "outcome",
    "mfe",
    "mae"
  ],
  "note": "Population is opportunity/detection stream (F-022 class) \u2014 units are entry+geometry rows, not verified trade ledger. Usable as trade_decision candidates for clean re-label."
}
```

### G0-Q2 — entry/SL/TP1 reconstructable?

- **practical:** `True`
- **evidence:**

```json
{
  "n_geometry_ok": 24999,
  "pct_geometry": 100.0,
  "n_with_tp2_field": 0,
  "pct_tp2_field": 0.0,
  "tp2_note": "tp2 field almost/never present \u2192 three-head needs surrogate (MFE>=2R) or two-head protocol freeze at GATE-L",
  "pilot_tp2_field": 0
}
```

### G0-Q3 — OHLCV for forward_walk after entry?

- **practical:** `True`
- **evidence:**

```json
{
  "candle_path": "data/BNBUSDT_M15.csv",
  "n_candles": 70080,
  "n_geometry": 24999,
  "n_timestamp_matched": 24999,
  "pct_ts_match": 100.0,
  "n_future_full_horizon": 24999,
  "pct_future_full": 100.0,
  "max_forward": 40
}
```

### G0-Q4 — 38-dim features@decision attachable?

- **practical:** `True`
- **evidence:**

```json
{
  "n_feature_complete_scan": 24999,
  "pct_feature_complete_scan": 100.0,
  "pilot_feature_complete": 150,
  "pilot_feature_pct": 100.0,
  "pit_note": "Stored opportunity features are pre-computed; F-051 centered-swing era may apply to historical JSONL \u2014 GATE-L must stamp pit_status."
}
```

### G0-Q5 — pilot clean re-derive works end-to-end?

- **practical:** `True`
- **evidence:**

```json
{
  "n_pilot": 150,
  "target_pilot_n": 150,
  "skips": {},
  "exception_count": 0,
  "exception_samples": [],
  "clean_base_rates": {
    "y_tp1": 0.38,
    "y_tp2_surrogate": 0.6466666666666666,
    "y_survives_be": 0.5,
    "timeout_rate": 0.0
  }
}
```

### G0-Q6 — contamination/agreement vs stream (diagnostic)?

- **practical:** `True`
- **evidence:**

```json
{
  "agree_tp1_rate": 0.6466666666666666,
  "agree_survives_be_rate": 0.7466666666666667,
  "n_survives_comparable": 150,
  "mean_abs_stream_mfe_r_minus_path_mfe_r": 0.6433,
  "note": "Low agreement strengthens need for clean y (F-022); does not fail feasibility."
}
```

### G0-Q7 — powered train n plausible after filters?

- **practical:** `True`
- **evidence:**

```json
{
  "est_total_opportunity_lines": 24999,
  "expected_clean_on_scan": 24999,
  "expected_clean_full_file": 24999,
  "gate_l_floor_default": 500,
  "pass_rate_pilot_attempt": 1.0,
  "frac_geometry": 1.0,
  "frac_future_full": 1.0,
  "frac_features": 1.0
}
```

### G0-Q8 — engineering cost of full GATE-L builder?

- **practical:** `True`
- **evidence:**

```json
{
  "reuse": [
    "research.zone_label_audit.honest_outcome",
    "research.measurement.forward_walk",
    "research.measurement.horizon_excursion",
    "features.dataset_builder.extract_feature_vector",
    "scripts/analysis/bnbusdt_trade_anatomy.load_candles"
  ],
  "new_work": [
    "versioned clean JSONL/parquet writer + protocol_hash sidecar",
    "multi-instrument driver",
    "tp2 policy freeze (surrogate vs two-head)",
    "pit_status stamping / optional re-emit"
  ],
  "est_effort": "1\u20133 engineering days for TN GATE-L builder; +0.5\u20131 day for ENV labels sharing same walk",
  "risks": [
    "F-051 PIT on stored features",
    "tp2 geometry absent",
    "F-022 stream must stay diagnostic-only"
  ]
}
```

### G0-Q9 — worth it now?

- **practical:** `True`
- **evidence:**

```json
{
  "rationale": "User explicitly chartered TN GATE-0 + ENV-0 together after accepting ENV_ARCH_V1. F-005 TradeNet unwired + F-045/F-059 label contamination block any KEEP/RETIRE without clean y. Envelope design accepted; without clean MFE/MAE/holding labels ENV cannot leave design freeze. F-001 still binds (governance/throughput > intelligence) but measuring honesty of existing predictive surfaces is high knowledge-ROI and unblocks both ladders without spine wire.",
  "worth_now": true,
  "authority_if_go": "GATE-L / ENV-L research builders only \u2014 no train promote, no neural_fn, no planner attach"
}
```

## Verdict rule application

- Q1–Q5 practical: `True`
- Q7 power plan: `True` (expected_clean_full=24999)
- Q8 cost bounded: `True`
- Q9 worth now: `True`

**GATE-0 verdict: FEASIBLE_GO**

### Effect

- `TRADENET_GATE_0_STATUS = PASS`
- GATE-L engineering **may** start (research builder only)
- Still **forbidden**: train promote, KEEP/RETIRE authority, neural_fn wire, GATE-P

## Dual-track note

Envelope ENV-0 ran on the same pilot (`env_verdict=FEASIBLE_GO`). Shared substrate: `honest_outcome` + `horizon_excursion`. See `docs/governance/envelope_gate0_feasibility.LATEST.md`.
