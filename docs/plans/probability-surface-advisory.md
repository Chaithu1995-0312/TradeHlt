# Plan: Probability-Surface Advisory (deterministic, weight-0.0, measured-additively)

> Created: 2026-06-02 · Updated: 2026-06-04 · Milestone: Trd-M (Probability-Surface→Fusion advisory)
> Spawned by backlog #6 DECISION = YES (see [`docs/topics/replay-memory.md`](../topics/replay-memory.md) Discussion).
> **Status: KILLED (2026-06-03) — superseded by the Funding Ledger in [`docs/current-findings.md`](../current-findings.md) (Probability Surface V2 = KILLED; evidence F-001, F-012).** This plan is the implementing initiative for Probability-Surface→Fusion; it is retained for replay, **not** active work. Do **not** resume without meeting the ledger's Reopen Conditions (Phase-0 economic-edge gate clears **and** ReplayMemory path-stats show AUC lift beyond static zone features) **and** filing a SESSION LOG entry per `CLAUDE.md §6.2`.
> *(Historical) Status: SCOPED — not yet implemented.*

## Context

The #6 decision granted ReplayMemory **advisory status** (preconditions met: 4-instrument OOS
persistence + schema/weighting repair + 4 per-instrument `zone_v1` registries). The binding
governance constraint (invariant #1, determinism) is that the signal is currently computed in the
**async fire-and-forget `CognitiveBus` worker** — replay-incomparable, so it cannot influence a
decision as-is. This plan re-homes the computation to the **synchronous deterministic path** and
introduces it as a **weight-0.0, measured-additively** advisory (the Phase-6 ROI pattern), never a
gate. Outcome: a reviewed, reversible advisory branch that can earn a non-zero weight only after its
decision-value is measured.

## Constraints (non-negotiable)
- **Determinism (inv #1):** advisory computed inline on the candle→decision path, seeded, no lookahead, candle-time keyed.
- **All-four-engines (inv #2):** advisory is *additional*, never replaces an engine; absence ⇒ neutral, not partial fusion.
- **Authority isolation (inv #5):** advisory adjusts a fusion *score* within bounds; it can never approve/trigger. Weight 0.0 = inert by default.
- **Telemetry additive (inv #5/#5):** new fields only; old telemetry preserved.

## Steps
1. **Synchronous per-instrument lookup.** Add a deterministic `ProbabilitySurface` reader that, given the current bar's features + instrument, loads `models/replay/zone_registry_<INST>.json`, calls `ReplayMemoryEngine._assign_cluster` + cluster stats, and returns a bounded advisory scalar. Reuse the repaired assignment; load synchronously (cache per instrument). Per-instrument selection = option (a) from the topic doc.
2. **Fusion consumption at weight 0.0.** In `core/fusion_engine.py`, add a config-gated advisory term (`probability_surface.weight`, default `0.0`) that nudges the fused score within a clamp. At 0.0 it is a no-op → output identical to today (regression-provable).
3. **Config.** Add a `probability_surface` section (weight 0.0, per-instrument `registry_paths`, enabled flag) to the source-of-truth config; document in `config-reference.md`.
4. **Measure additively.** Emit the would-be advisory delta as telemetry on every decision (additive field) so its decision-value is measurable *before* any non-zero weight — the gate for ever raising the weight.
5. **Tests.** Determinism/replay parity (weight 0.0 ⇒ byte-identical decisions vs baseline); per-instrument registry selection; neutral-on-missing-registry; authority-isolation (advisory cannot flip a REJECT to APPROVE on its own); bounded clamp.

## Verification
- `pytest -q` green; a replay-parity test proves weight-0.0 ⇒ identical decision stream vs current.
- Determinism: same inputs → same advisory value across two runs.
- Invariant re-check: engines still all-or-nothing; LLM/advisory never trigger; telemetry additive.
- Only after measured decision-value justifies it: a separate, validated promotion raises the weight (governance gate).

## Out of scope
- Any non-zero default weight (requires measured-value review first).
- Learned probabilistic path-trees / Monte-Carlo (later milestone).
