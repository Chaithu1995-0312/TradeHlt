# CRT Local Math Parity Audit V1 (plan)

```json
{
  "schema_id": "CRT_LOCAL_MATH_PARITY_AUDIT_V1",
  "generated_at_utc": "2026-07-14T10:26:18.740565+00:00",
  "status": "PLAN_FROZEN_NOT_EXECUTED",
  "task_class_when_executed": "OBSERVATION_ONLY",
  "purpose": "Before any deprecation of CRT-local market math or BIND_TO_CANONICAL_FEATURE migration, prove identity/parity of CRT-local quantities vs governed FeaturePipeline / formula_registry.",
  "targets": [
    {
      "quantity": "body_ratio",
      "crt_source": "Candle.body_ratio property",
      "governed_source": "FM-010 / pipeline body_ratio",
      "pass_criterion": "max abs err \u2264 1e-9 on finite bars of frozen XAUUSD Phase-1 corpus sample",
      "blocks_migration": true
    },
    {
      "quantity": "wick_size",
      "crt_source": "Candle.wick_size",
      "governed_source": "FM-002 / pipeline wick_size",
      "pass_criterion": "exact high-low identity",
      "blocks_migration": true
    },
    {
      "quantity": "atr",
      "crt_source": "RangeDetector.compute_atr (absolute? period atr_period)",
      "governed_source": "FM-041 pipeline atr (close-relative documented)",
      "pass_criterion": "document scale relationship; FAIL if assumed equal without transform proof",
      "blocks_migration": true,
      "note": "Likely TRANSFORM not EXACT \u2014 must not bind as identical without transform registry"
    },
    {
      "quantity": "ema_fast / ema_slow",
      "crt_source": "EngineState.update_emas",
      "governed_source": "FM-043 / FM-044 pipeline",
      "pass_criterion": "span/adjust parity proof or registered transform",
      "blocks_migration": true
    }
  ],
  "not_in_audit": [
    "active_range / sweep_event / displacement_candle (private lifecycle)",
    "thresholds (HOW)"
  ],
  "outputs_when_run": [
    "parity report JSON with per-quantity PASS/FAIL/TRANSFORM",
    "no production CRT change"
  ],
  "authorization": "measurement only; does not authorize CRT consumer migration"
}
```
