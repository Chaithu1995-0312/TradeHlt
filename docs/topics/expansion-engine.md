# Topic: Expansion Engine (bounded parameter search)

> **Topic-visibility unit.** The deterministic, guard-railed parameter explorer: an LLM suggests a
> direction once, then a bounded stepwise loop searches for better configs without ever leaving the
> safe envelope. Offline tooling.
>
> Created: 2026-06-05 · Updated: 2026-06-05 · Status: living

## In plain language
To improve a config you want to nudge parameters and see if results get better — but unbounded tuning
overfits and goes off the rails. This engine asks an LLM **once** (offline) for *which* parameters to
move and in which direction, then runs a **deterministic** loop that changes one parameter at a time in
small steps, each clipped to hard `PARAM_BOUNDS` and a max drift, re-backtesting and **rejecting** any
step that drops PnL or blows out drawdown. Output is three ranked config tiers (SAFE/BALANCED/AGGRESSIVE).

## Code covered
- [`src/expansion/expansion_engine.py:24`](../../src/expansion/expansion_engine.py) — `ExpansionEngine` — `run()` at :46 (baseline → per-candidate stepwise mutate → evaluate → rank).
- [`src/expansion/policy_schema.py:56`](../../src/expansion/policy_schema.py) — `PARAM_BOUNDS` — per-parameter hard envelope (+ `MAX_PARAM_CHANGE`, `MAX_STEPS_PER_PARAM`, `MIN_PNL_RATIO`, `MAX_DRAWDOWN_RATIO`).
- [`src/expansion/evaluator.py:6`](../../src/expansion/evaluator.py) — `Evaluator` — score + `passes_guardrails()` + SAFE/BALANCED/AGGRESSIVE tier classification.
- `src/expansion/config_mutator.py` — `ConfigMutator.mutate()` — one-parameter deterministic tweak, clipped to bounds.
- `src/expansion/llm_pattern_extractor.py` — `extract_expansion_plan()` — the one-shot LLM suggestion (with rule-based fallback).

## Ins / Outs
- **Ins:** a base production config + an `ExpansionPlan` (LLM-suggested candidates) + `csv_paths`; bounds from `policy_schema`.
- **Outs:** `ExpansionResult` (baseline + 3 ranked tiers + full step trace); `results/expansion/<config>_<TIER>.json`; audit `logs/expansion_trace.jsonl` (accepted) + `logs/expansion_rejected.jsonl` (rejections with reason).

## Entry points & validations
- **Reached via:** invoked programmatically from `src/governance/expansion_integration.py` (governance automation); no standalone CLI.
- **Validated by:** the bounded-mutation contract — every step clipped to `PARAM_BOUNDS` + `MAX_PARAM_CHANGE`; guardrail rejection on PnL/drawdown regression; deterministic (LLM only suggests, never executes).

## Tests
- [`tests/test_expansion_engine.py`](../../tests/test_expansion_engine.py) — mutate/bounds/max-change, scoring, guardrail rejection, tier classification, full loop with early termination.
- [`tests/test_expansion_governance_bridge.py`](../../tests/test_expansion_governance_bridge.py) — governance integration (viability filter, forward-test).

## Fits in architecture
A research/tuning feeder that produces candidate configs for the governance promotion path
([`promotion-governance.md`](promotion-governance.md), [`config-validation.md`](config-validation.md)).
The "unbounded mutation" anti-pattern is explicitly guarded here (`conventions.md`).

## Discussion (filled in-session)
- **Risks:** 2026-06-05 — search quality depends on the one-shot LLM suggestion; the fallback is conservative, so a bad/absent LLM degrades to small safe steps (acceptable).
- **Enhancements:** 2026-06-05 — no dedicated CLI; reached only via the governance bridge — a thin CLI wrapper would make ad-hoc runs easier.
