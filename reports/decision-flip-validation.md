# 7c Decision-Flip Harness — Validation Report (V1–V10)

_Generated 2026-07-08 (read-only). Verdict: **POSITIVE_CONTROL_NOT_CONSTRUCTIBLE** → the retracted
0-flip result stands retracted; the decision-flip question is **not answerable at the `EngineRunner.run()`
boundary** with a per-candle harness, for a structural reason._

## Bottom line

`EngineRunner.run()` **structurally can never return `execute`**, so body_ratio — which affects only the
fused SCORE — can never flip the run() decision. A legitimate positive control (prove the harness detects
a known body_ratio-only flip through the real machinery) therefore cannot be built without **bypassing the
rr gate**, i.e. replacing production decision logic. Per the V9 escape clause: STOP →
`POSITIVE_CONTROL_NOT_CONSTRUCTIBLE`.

## The structural mechanism (source-confirmed)

1. **DecisionEngine gate order** (`decision_engine.py:129-152`): `zone_gate_invalid` → `low_score`
   (score<threshold) → `low_probability` (p_win<0.4) → **`low_rr` (rr<1.5)** → `weak_setup` → `execute`.
2. **The rr value is a [0,1] polarity, compared to a 1.5 ratio threshold.**
   `engine_runner.py:957-960` sets `fusion_ctx["rr"] = engine_results["rr"]["rr_ratio"]`, and the RR engine
   returns `rr_ratio = round(polarity, 4)` with `polarity = max(upper_body, lower_body) ∈ [0,1]`
   (`rr_engine.py:73-79`). Config `rr_threshold = 1.5` (`v2_multi_2026_04.json:130`). So `rr ≤ 1.0 < 1.5`
   on **every** candle → `low_rr` rejects whenever the score gate is passed. **Empirical: 0 `execute` across
   70,002 candles** (both branches).
3. **In the backtest, `run()` is a VETO, not an approver** (`backtest_v2.py:2182`): a CRT-opened trade is
   vetoed iff `run()` returns REJECT/HOLD **and** the reason is not `zone_gate_invalid` (which is bypassed,
   `:2178-2181`). The trade itself comes from the CRT state machine (`engine.state.active_trade`).
4. **body_ratio's reach:** it enters only `s_breakout` (CRT, fusion weight 0.4) → the fused SCORE. It does
   NOT affect zone membership, p_win (gaussian), rr (polarity), or weak_component. So changing body_ratio
   can only move the reject **reason** between `low_score` and `low_rr` — both are vetoes; neither is
   `zone_gate_invalid`. It can never produce `execute` and never flips the veto outcome.

**Conclusion:** at the `run()` boundary, body_ratio is **decision-inert by construction** — not because its
effect is "small", but because the binding gates (zone validity, rr) are body_ratio-independent and
`execute` is unreachable. This is a *source-structural* result, stronger than (and the correct explanation
for) the retracted counterfactual "0 flips".

## V-item outcomes

| V | Item | Result |
|---|---|---|
| V0 | Step-0 retraction | **DONE** — pins/adjudication/F-047/CLAUDE.md/memory reset to `not_measured`; Matrix v2 un-frozen |
| V1 | State-surface / deepcopy | **PASS (read)** — deepcopy isolates the in-memory decision state (all controllers copied independently; before-decision mutations captured). Non-isolated = post-decision telemetry only (`_GENERATION`, `logs/*.jsonl`). |
| V4 | Corpus parity | **FAIL (moot)** — score probe 19,922 vs decision probe 70,002 candles; would be fixable but the harness is invalid upstream. |
| V5 | Input isolation | **DEFECT confirmed** — prior harness perturbed body_ratio AND wick_size. Correct design = body_ratio-only (no decision-path code reads `input_data["wick_size"]`; grep-confirmed). |
| V6 | Runtime-path parity | **FAIL** — the run() decision path is gated by body_ratio-independent always-reject gates (`zone_gate_invalid` needs `zone_gate['valid']` never set by run(); `low_rr` from a [0,1] polarity vs 1.5). run() never executes; the backtest handles this via veto-bypass, not via the harness path. |
| V7 | Score-propagation | body_ratio → CRT score → final_score DOES propagate (confirmed), but the SCORE is never the binding gate → no `threshold_crossing_opportunity` can ever resolve to `execute` (rr gate dominates). |
| V9 | Positive control | **NOT CONSTRUCTIBLE** — run() cannot execute without bypassing the rr gate (replacing production decision logic). V9 escape clause → STOP. |
| V2,V3,V8,V10 | B-vs-B / trajectory / frozen / tests | **MOOT** — not run; the instrument cannot detect a flip, so downstream controls are irrelevant until a valid instrument exists. |

## Highest-leverage next step (the correct instrument)

The decision-flip question is about the **veto outcome**, so measure it where the trade actually lives:
a **full-backtest ledger differential** — run `backtest_v2` (gate-ON) twice, once with the canonical and
once with the current (live-hook) body_ratio injected into the feature pipeline, and diff the trade
ledgers (which CRT trades survive the run() veto). Structural analysis predicts **0 ledger changes**
(body_ratio affects neither zone membership nor rr, the only body_ratio-independent gates that decide
veto/survival), but that must be *measured*, not asserted. This is a different, valid instrument — NOT the
per-candle run() harness, which is structurally incapable of the measurement.

## Also surfaced (separate findings)
- `low_rr` gate compares a [0,1] polarity score against a 1.5 ratio threshold → the fusion decision gate
  can never `execute`; sibling of the `zone_gate_invalid` always-reject. Governance-relevant (the 4-engine
  fusion decision gate is effectively a veto-only gate). Consistent with F-036/F-037 (fusion gate
  non-decisive; spine is CRT-only).
- Session-encoding mismatch (pipeline `0=london` vs adapter `0=asia`).
- `rotate_session_log.py` overwrites same-date archives (history loss).
