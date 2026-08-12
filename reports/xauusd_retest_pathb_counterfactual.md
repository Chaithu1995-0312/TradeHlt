# XAUUSD RETEST path-B counterfactual (observe-only)

**Generated:** 2026-08-07T22:35:02Z
**ACTIVE_VERSION:** `v2_multi_2026_04`
**Corpus:** `data\XAUUSD_M15_20260807_203705.xlsx`
**HTF:** 4

> Force-session-pass is process-local only (`allowed_sessions` includes `OFF_SESSION`).
> No production config or engine code was modified.

## Path A (force session)

- Forced allow list: `['LONDON', 'NEWYORK', 'OVERLAP', 'ASIA', 'OFF_SESSION']`
- TRADE_OPENED timestamps: `[]`
- Soft-conf outcomes: `{"2026-07-22 19:15:00": {"ts": "2026-07-22 19:15:00", "state_before": "RETEST", "state_after": "EXECUTION", "action": "NONE", "direction": "SHORT", "has_active_trade": false, "soft_conf_candles": 1}, "2026-07-28 05:45:00": {"ts": "2026-07-28 05:45:00", "state_before": "RETEST", "state_after": "EXECUTION", "action": "NONE", "direction": "LONG", "has_active_trade": false, "soft_conf_candles": 1}}`

### build_trade geometry snaps (incl. inverted SL)

```json
[
  {
    "ts": "2026-07-22 19:00:00",
    "dir": "SHORT",
    "entry": 4154.55,
    "sl_would": 4148.662428571429,
    "disp_high": 4146.75,
    "disp_low": 4132.02,
    "disp_open": 4132.02,
    "disp_close": 4142.79,
    "atr": 9.562142857142915,
    "sl_atr_buffer": 0.2,
    "inverted_sl": true,
    "trade_built": false
  },
  {
    "ts": "2026-07-28 05:30:00",
    "dir": "LONG",
    "entry": 4044.31,
    "sl_would": 4045.0657142857144,
    "disp_high": 4059.19,
    "disp_low": 4046.38,
    "disp_open": 4058.08,
    "disp_close": 4047.41,
    "atr": 6.571428571428571,
    "sl_atr_buffer": 0.2,
    "inverted_sl": true,
    "trade_built": false
  }
]
```

## Path B (EngineRunner → Planner → CRT levels → Ultron)

### retest_1_short — soft-conf `2026-07-22 19:15:00`

- **Verdict:** `PATH_B_STOP_ENGINE_RUNNER:zone_gate_invalid|zone_valid_reeval:weak_setup`
- Expected dir: `SHORT`
- Path-A trade present: `False`
- EngineRunner: decision=`reject` reason=`zone_gate_invalid` stage=`decision` score=`0.567`
- Planner: decision=`None`
- Ultron: decision=`None` reason=`None`

### retest_2_long — soft-conf `2026-07-28 05:45:00`

- **Verdict:** `PATH_B_STOP_ENGINE_RUNNER:zone_gate_invalid|zone_valid_reeval:low_score`
- Expected dir: `LONG`
- Path-A trade present: `False`
- EngineRunner: decision=`reject` reason=`zone_gate_invalid` stage=`decision` score=`0.4602`
- Planner: decision=`None`
- Ultron: decision=`None` reason=`None`

## Interpretation

- **Path A force-session:** soft-conf + zone can reach `EXECUTION`; `TRADE_OPENED` still requires `build_trade` non-inverted SL.
- **Path B force-session (production EngineRunner):** first live decision reject reason is authoritative for that call.
- **`zone_valid_reeval` arm:** if `zone_gate_invalid` was only the `passed`-flag wiring (`zone_result.meta.passed` true but top-level `passed` absent), re-evaluate DecisionEngine with `valid=True` to name the *next* semantic reject (`low_score` / `weak_setup` / …).
- `PATH_B_WOULD_OPEN` only if EngineRunner→Planner→levels→Ultron all approve under the empty portfolio fixture.
- Observe-only: **no** session-policy or zone authority granted.
