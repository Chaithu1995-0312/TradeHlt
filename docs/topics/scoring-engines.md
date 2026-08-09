# Topic: Scoring Engines (Gaussian · Zone-Gate · RR)

> **Topic-visibility unit.** The three non-CRT scoring engines that feed fusion. CRT has its own
> topic ([`crt-spine.md`](crt-spine.md)); fusion of all four is [`fusion-decision.md`](fusion-decision.md).
> Read this for what each scorer contributes and how the runner enforces all four.
>
> Created: 2026-06-05 · Updated: 2026-06-05 · Status: living

## In plain language
Every candle is scored by **four independent engines**, then fused. CRT reads market structure;
the other three are here: **Gaussian** (a probability score — a fast heuristic kernel or a trained
ML model), **Zone-Gate** (a BitNet-backed zone/geometry validator), and **RR** (a candle-polarity /
reward-risk quality score). Each returns a `score ∈ [0,1]` plus a reason. None decides alone — the
runner collects all four and hands them to fusion. The hard rule: **if any of the four is missing,
the runner rejects** rather than fusing a partial set.

## Code covered
- [`src/engines/heuristic_gaussian_engine.py:187`](../../src/engines/heuristic_gaussian_engine.py) — `HeuristicGaussianEngine` — EMA/momentum Gaussian kernel; `compute()` at :271; **fail-fast** on missing canonical features.
- [`src/engines/ml_gaussian_engine.py:24`](../../src/engines/ml_gaussian_engine.py) — `MLGaussianEngine` — trained GaussianNB model path; `compute()` at :113; **fail-open** (returns neutral 0.5 on model/inference error).
- [`src/engines/rr_engine.py:37`](../../src/engines/rr_engine.py) — `RREngine` — Candle Polarity Index; `compute()` at :45 (1.0 = close at extreme, 0.5 = doji, 0.0 = degenerate).
- [`src/engines/zone_gate_engine.py:191`](../../src/engines/zone_gate_engine.py) — `run_zone_gate_engine` — schema-validated BitNet zone gate (hard/soft/force_pass modes); fail-open neutral 0.5 on registry error.
- [`src/core/engine_runner.py:52`](../../src/core/engine_runner.py) — `EXPECTED_ENGINES` — `{"crt","gaussian","zone_gate","rr"}`; the completeness contract.
- [`src/core/engine_runner.py:748`](../../src/core/engine_runner.py) — `missing_engines` — partial-fusion guard: any missing engine → hard reject (`incomplete_engine_execution`).

## Ins / Outs
- **Ins:** a canonical feature dict (see [`feature-schema.md`](feature-schema.md)) + `direction`; Gaussian heuristic needs `ema_fast/ema_slow/momentum_score`, RR needs `close/high/low`, Zone-Gate needs the canonical vector + a `model_fn` + optional zone registry. Config: `get_prod_section("engine_runner")` (impl/mode selectors) and `get_prod_section("fusion_engine")` (per-engine weights).
- **Outs:** per-engine `dict{score, reason, meta…}` collected into `engine_results = {crt, gaussian, zone_gate, rr}`, then fused (`FusionEngine.compute`). Fusion weights (v1 config): crt 0.4 / gaussian 0.2 / zone_gate 0.2 / rr 0.2, with regime-aware overrides.

## Entry points & validations
- **Reached via:** `EngineRunner.run()` on the candle→order spine — invoked by `runtime.backtest_v2` (replay) and `runtime.live_engine_hook` (live). Not called directly.
- **Validated by:** the four-engine completeness guard (`engine_runner.py:822 · missing_engines`); per-engine fail-fast (heuristic Gaussian) / fail-open (ML Gaussian, Zone-Gate) doctrine; signal-audit records every engine score.

## Tests
- [`tests/test_gaussian_impl_switch.py`](../../tests/test_gaussian_impl_switch.py) — heuristic↔ML selector, 38-dim schema contract, direction mirroring for shorts.
- [`tests/test_zone_gate.py`](../../tests/test_zone_gate.py) — zone-gate invocation, canonical-input validation, schema migration.
- [`tests/test_engine_runner_rr_fusion.py`](../../tests/test_engine_runner_rr_fusion.py) — RR engine + optional rr_fusion enhancement layer.
- [`tests/test_fusion_and_validator_regression.py`](../../tests/test_fusion_and_validator_regression.py) — missing-engine detection + regime-weight resolution.

## Fits in architecture
The scoring stage of the spine: `EngineRunner → FusionEngine → DecisionEngine → ExecutionPlannerV1_2 → UltronRiskGate` ([`signal-flow.md`](../architecture/signal-flow.md) Steps 3–4). These three engines + CRT are the inputs to fusion; the runner is the completeness authority.

## Discussion (filled in-session)
- **Ambiguities:** 2026-06-05 — "Gaussian" is two implementations behind one slot (heuristic vs ML), selected by `engine_runner.gaussian_impl`; opposite error doctrines (fail-fast vs fail-open). Keep the distinction explicit when reasoning about robustness.
- **Risks:** 2026-06-05 — Zone-Gate `force_pass` mode logs the real decision but returns `passed=True`; ensure it's never on in production by accident.
- **Need more info:** 2026-06-05 — RR engine returns a `rr_ratio` legacy-compat field but actually scores candle polarity, not forward RR; downstream readers should not treat it as realized RR.
- **Reconciled:** 2026-06-05 — zone **expectancy** (`mean_rr`/`tp_hit_rate` in the registry) is **ORPHANED**: `zone_gate_engine.py` scores geometry only, never expectancy. `strategy_consensus` is fused only when its config weight > 0. See `analysis/intent-vs-code-reconciliation-2026-06-05.md` items 3–4.
