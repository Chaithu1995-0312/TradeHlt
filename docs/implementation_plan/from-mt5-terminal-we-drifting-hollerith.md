# EXECUTION ownership claim — verification results + recording plan

## Context
An architecture summary was proposed for the EXECUTION stage (Feature Pipeline → engines → Fusion → Decision → ExecutionPlanner → `compute_crt_levels` → Ultron Risk Gate → MT5). I verified it against source, read-only. **Most of it is correct for the live path**, but it contains three factual errors and omits the single most important fact: **SL/TP has two independent implementations that disagree.** (My verification subagent died on the session limit; everything below I read directly.)

## Verdict

### Correct
- `ExecutionPlannerV1_2` produces **intent + entry + gate**, and explicitly **not** SL/TP — stated verbatim at `src/config_layer/execution_planner.py:8-9`, and its layer diagram (`:11-16`) matches the proposed chain exactly.
- Intent classes (BREAKOUT / PULLBACK / LIQ_SWEEP / REVERSAL) are decided there before geometry (`:6`).
- "Gate Intelligence → SL/TP" is right: `compute_crt_levels` lives at `src/core/gate_intelligence.py:24-84`.
- `Trade` carries entry / sl / tp1 / tp2 / risk_pct / direction (`crt_engine_v2.py:2276-2286`); lifecycle events `TRADE_OPENED` (`:3159`), `TRADE_TP1/TP2/STOPPED` (`:2683`), `TRADE_ABORTED` (`:2655`) all exist.
- TradeNet does not generate Entry/SL/TP.

### Wrong
1. **TradeNet does not participate before Fusion.** `EXPECTED_ENGINES = {"crt", "gaussian", "zone_gate", "rr"}` (`src/core/engine_runner.py:54`) — four engines, no TradeNet. `src/core/fusion_engine.py:8` calls the neural slot *"stubbed; plug TradeNet GGUF here"*. Consistent with **F-005 (Certain): TradeNet is BUILT but unwired.**
2. **`ExecutionPlanner → compute_crt_levels` is not a call edge.** `execution_planner.py` imports only the `GateIntelligence` *class* (`:34`), never the function. The actual caller is **`src/runtime/live_engine_hook.py:911`**.
3. **"Feature Pipeline (39 features) → CRT State Machine" is not the CRT spine.** `process_candle` consumes a `Candle` (OHLCV) — not a feature vector. `state.cached_features` is built *at RETEST* (`:1605-1629`) and holds 3–6 keys, not 39.

### The omission that matters: two SL/TP authorities

|  | Backtest CRT spine | Live path |
| --- | --- | --- |
| Caller | `process_candle:3153` | `live_engine_hook:911` |
| SL/TP producer | `ExecutionEngine.build_trade` (`crt_engine_v2.py:2191-2292`) | `compute_crt_levels` (`gate_intelligence.py:24-84`) |
| **SL anchor** | **displacement candle** `.low`/`.high` (`:2215`, `:2222`) | **current candle** `low`/`high` (`:914-915`) |
| ExecutionPlanner used? | No | Yes |
| `compute_crt_levels` used? | **No** — `crt_engine_v2` never imports `gate_intelligence` | Yes |

The two produce **different stops for the same setup** whenever the entry candle isn't the displacement candle — which is essentially always, since entry is the retest close (`:2202`). `build_trade`'s own comment (`:2204-2208`) states the doctrine the live path does not follow: *"SL anchored to displacement candle extreme… CRT doctrine: SL beyond the displacement candle = trade is structurally invalid."* This is the same duplicate-ownership class as `INV-009`, but semantic rather than structural.

### Documentation drift (2 instances, both in `gate_intelligence.py`)
- `:5-6` and `:37` claim `compute_crt_levels` *"mirrors crt_engine_v2.py lines 1162-1201 exactly."* Lines 1162-1201 are today inside `try_sweep_to_displacement`'s sweep-age and body_ratio guards — not SL/TP code at all. The real SL/TP is at `:2204-2258`. **Stale line citation.**
- `:6` and `execution_planner.py:8-9` both assert *"CRT is sole SL/TP authority."* False — `crt_engine_v2.ExecutionEngine.build_trade` is a second, independent authority. And "mirrors … exactly" is substantively wrong given the different SL anchor.

### Flagged, not re-verified this pass
A memory note (2026-07-29) records `compute_crt_levels` receiving close-relative ATR (FM-041) while treating it as price units → SL buffer ~2,343× too small on XAUUSD. `EngineState.atr_abs`'s own comment (`:244-249`) documents exactly this FM-041-vs-absolute-ATR confusion class. **Not re-confirmed here** — recorded as an open item requiring its own check, not asserted as fresh evidence.

## Recording plan (documentation only)

**Carry-over from the previous approved plan** (plan mode interrupted it — the `.md` invariants landed, the rest did not):
- `reports/crt_semantic_execution_reconstruction.json` — mirror `INV-006`…`INV-011` into `invariants[]` with a `verdict` field.
- Both files — add `FMODE-009 execution_deadend_on_build_trade_none` and `FMODE-010 shadow_memory_partial_teardown`.
- `.md` **Open Questions** — the `EXECUTION→RANGE` and unguarded-shadow-path items.

**New from this pass**, into the same two artifacts:
- `FMODE-011 dual_sl_tp_authority_divergent_anchor` — the two implementations and the displacement-vs-current-candle anchor split, with the table above.
- `DRIFT-004` — `gate_intelligence.py:5-6,37` stale line citation (1162-1201 → 2204-2258).
- `DRIFT-005` — the "sole SL/TP authority" claim contradicted by `build_trade`.
- **Open Questions** — whether the live path's current-candle SL anchor is intentional or drift from the CRT doctrine `build_trade` states; and the FM-041 ATR-basis item above.

No `docs/current-findings.md` entry this pass: these are descriptive architecture observations, and registering the anchor divergence would imply a remediation decision that is the user's (§6.5 — observation grants no authority).

## Verification
- Every line cited was read in source this session; no claim rests on a code comment alone — the two drift items are precisely *comments contradicted by source*.
- After editing: JSON parses, `invariants[]` = 11, `failure_modes[]` = 11, `drift_records[]` = 5, `.md` section count unchanged at 16.
- Strictly descriptive: no `src/`, config, `params`, or `ACTIVE_VERSION` change; no fix to the anchor divergence, the dead-end, or the teardown paths; no promotion.
