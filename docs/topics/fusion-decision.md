# Topic: Fusion + Decision

> **Topic-visibility unit.** How the four engine scores become one number, and how that number
> becomes an accept/reject. The middle of the candle→order spine.
>
> Created: 2026-06-01 · Updated: 2026-09-03 (Trd-M5) · Status: living

## In plain language
After the four engines (CRT, Gaussian, Zone Gate, RR) each score a candle, **fusion** combines
them into a single `final_score` under regime-aware weights, and the **decision engine** turns
that score (plus probability and RR) into APPROVE or a typed REJECT. Fusion is *aggregation only*
— it does not decide; the decision engine is the gatekeeper, but it scores against a **dynamic
threshold** (the recent score distribution) rather than a fixed cutoff, so "good enough" is
relative to what the market has been offering.

## Code covered
- [`src/core/fusion_engine.py:253`](../../src/core/fusion_engine.py) — `FusionEngine`. `compute()` ([`:290`](../../src/core/fusion_engine.py)) aggregates `engine_results` keyed `crt/gaussian/zone_gate/rr`; **missing any key → `final_score=0.0` + `reason="missing_engine_outputs"`** ([`:307`](../../src/core/fusion_engine.py)) — the completeness guard. Regime weights resolved by priority: explicit `weights=` → `regime=` lookup → scalar config defaults ([`:316`](../../src/core/fusion_engine.py)). Internals: `ScoreNormalizer`, per-engine `EngineHealthTracker` (dead-engine detection).
- **Trd-M5 (2026-06-01):** the LLM tie-breaker (fusion `evaluate()` path only, behind `fusion_use_evaluate`, default off — never on the replay `compute()` path) now (a) **emits an enveloped `LLM_ADVISORY` event** when it fires (from `EngineRunner._evaluate_fusion_path`, keyed on candle ts in the payload, observation-only — never gates a decision); and (b) carries an **execution-authority isolation assertion** after `_decide()` (`fusion_engine.py`) asserting the action stays in the rule-based `{TRADE, REJECT}` contract (LLM only nudges the score). Gated by `GOVERNANCE_MODE` (`core/governance_mode.py`): `strict` raises, `advisory` warns.
- [`src/core/decision_engine.py:85`](../../src/core/decision_engine.py) — `DecisionEngine`. Requires the `decision_engine` config section (raises if `None`, [`:88`](../../src/core/decision_engine.py)). `evaluate()` ([`:104`](../../src/core/decision_engine.py)) uses `fusion["normalized_score"]` against a `DynamicThreshold` computed *before* the decision and updated *after* ([`:119`](../../src/core/decision_engine.py)) to avoid deciding a signal against itself. Reject order: `zone_gate_invalid` (bypassed if engine dead) → `low_score` → `low_probability` → (RR) .
- Orchestrated by [`src/core/engine_runner.py`](../../src/core/engine_runner.py) (`FusionEngine` imported at [`:30`](../../src/core/engine_runner.py)); `EXPECTED_ENGINES` completeness check at [`:718`](../../src/core/engine_runner.py).

- **Spine inventory (2026-09-03 citation pass — path existence on the GCMC spine join; not a behavior claim, not G001, not a file:line citation. Source still wins.:**
- [`src/core/__init__.py`](../../src/core/__init__.py)
- [`src/core/backtest_port.py`](../../src/core/backtest_port.py)
- [`src/core/dynamic_threshold.py`](../../src/core/dynamic_threshold.py)
- [`src/core/governance_mode.py`](../../src/core/governance_mode.py)
- [`src/core/hierarchical_meta_fusion.py`](../../src/core/hierarchical_meta_fusion.py)
- [`src/core/signal_belief_tracker.py`](../../src/core/signal_belief_tracker.py)
- [`src/core/types.py`](../../src/core/types.py)
- [`src/runtime/analyze_fusion_shadow.py`](../../src/runtime/analyze_fusion_shadow.py)

## Ins / Outs
- **Ins:** `engine_results` dict (`crt/gaussian/zone_gate/rr` scores), optional `weights`/`regime`; config sections `fusion_engine` and `decision_engine` (`score_threshold`, `p_win_threshold`, `weak_link_weight`, `weak_component_threshold`). *DecisionEngine reads no RR knob — `rr_threshold` RETIRED, F-048 resolved 2026-07-24; economic reward:risk is owned by `ultron_risk_gate.min_rr_ratio`, not by the decision surface.*
- **Outs:** fusion → `{final_score, scores{}, normalized_score, missing_engines?, reason?}`; decision → `{decision: APPROVE|REJECT, reject_reason?, threshold, ...}`.

## Entry points & validations
- **Reached via:** `EngineRunner.run()` on the `backtest_v2` path and live (`live_engine_hook`). Behind the `fusion_use_evaluate` feature flag in the production config.
- **Validated by:** the four-engine completeness guard (fusion `:307` + runner `:718`); dynamic-threshold update ordering; reject taxonomy is typed (no stringly-typed leaks).

## Tests
- [`tests/test_engine_runner_rr_fusion.py`](../../tests/test_engine_runner_rr_fusion.py) — runner→fusion RR path.
- [`tests/test_fusion_and_validator_regression.py`](../../tests/test_fusion_and_validator_regression.py) — fusion regression + validator.
- [`tests/test_analyze_fusion_shadow.py`](../../tests/test_analyze_fusion_shadow.py) — shadow-fusion analysis.
- [`tests/test_engine_runner_dual_gate.py`](../../tests/test_engine_runner_dual_gate.py) — dual-gate path.

## Fits in architecture
Spine steps between scoring and planning: `EngineRunner → FusionEngine → DecisionEngine → ExecutionPlannerV1_2 → UltronRiskGate` (`CLAUDE.md §10`). See [`crt-spine.md`](crt-spine.md), [`execution-planning.md`](execution-planning.md), [`docs/architecture/signal-flow.md`](../architecture/signal-flow.md).

## Discussion (filled in-session)
- **Risks:** `2026-06-01` `compute()` returns `final_score=0.0` (not an exception) when an engine is missing — a silently-dropped engine degrades to a permanent reject rather than a loud failure. Guarded by `engine_runner.py:718` but worth monitoring.
- **Challenges:** `2026-06-01` two distinct "fusion" notions exist — multi-*engine* fusion (this topic, `core/fusion_engine.py`) vs multi-*strategy* fusion (`FusionEngine.fuse_strategy_results()` in the engines variant). Keep them separate when discussing.
- **Blockers:** `2026-06-01` none.
- **Ambiguities:** `2026-06-01` **module drift** — [`codebase-analysis.md`](../analysis/codebase-analysis.md) documents `src/engines/fusion_engine.py`, but the runtime spine imports `core/fusion_engine.py` ([`engine_runner.py:30`](../../src/core/engine_runner.py); confirmed in `graph.dot`/`code-map`). The `engines/` variant is a dead-code/drift candidate. **Not resolved here** (code change, out of scope) — flagged for the topics-vs-Bricks drift comparison.
- **Enhancements:** `2026-06-01` surface `DynamicThreshold` state in telemetry so the relative-cutoff is auditable per run.
- **Need more info:** `2026-06-01` exact line of `DecisionEngine.evaluate()` RR-branch + the final APPROVE return shape (read on next touch).
- **2026-09-03 — spine citation pass:** named 8 previously unreferenced spine paths under Code covered (path existence on the GCMC spine join; not a behavior claim, not G001, not a file:line citation. Source still wins.).
