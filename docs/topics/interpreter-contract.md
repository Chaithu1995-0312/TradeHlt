# Topic: Interpreter Contract Layer (Level 4)

> **Topic-visibility unit.** One concept, narrated in human language, kept in sync with the
> code on every working response (`CLAUDE.md §6.1`). Read this to understand the topic — what
> code it covers, how it's reached, what tests it, what's still open — **without loading the
> rest of the codebase**. Link, don't inline.
>
> Created: 2026-06-14 · Updated: 2026-06-14 (Plan 4: MA-cross reference + e2e chain proof) · Status: living

## In plain language
The Interpreter Contract is the frozen interface every future market interpreter (P&F, Wyckoff,
Market Profile, Order Flow, …) must satisfy *before* it ships — so a new interpreter becomes an
**experiment measured against G001**, not a belief. An **Interpreter** is an *event/feature
producer*: it observes a window and emits events + confidence/strength that feed **fusion**. It is
a different economic object from a research **Hypothesis** (which emits *trades*). To be measured,
an interpreter is bridged to a `Hypothesis` by an adapter and run through the **existing**
`forward_walk` + `QualificationGate` — there is deliberately **no new oracle** (reuse, not rebuild).

**Frozen hard invariants:** pure · deterministic · no-lookahead · **identity-blind** (fusion never
knows P&F-ness — only events/confidence/strength/unknowns) · `explain()` telemetry-only · `meta`
opaque/forbidden-for-decisions · `schema_version` (contract) ≠ `version()` (implementation).

## Code covered
- [`src/interpreters/contract.py`](../../src/interpreters/contract.py) — `EventKind` enum;
  `InterpreterEvent` (kind/direction(`Optional[Direction]`)/confidence/strength/geometry/opaque
  `meta`); `InterpreterReading` (events/confidence/unknowns/failure_conditions/trace_id/
  observation_time/schema_version); `Interpreter` Protocol (`observe`+`explain`); `BaseInterpreter`
  (core-required + defaulted hooks + strict `_validate`).
- [`src/interpreters/adapter.py`](../../src/interpreters/adapter.py) — `InterpreterHypothesis`: the
  identity-blind bridge that wraps any `Interpreter` as a research `Hypothesis` (`detect()` → Signals
  from directional events only). Mirrors `hypotheses/spine_hypothesis.py`.
- [`src/interpreters/reference.py`](../../src/interpreters/reference.py) — `NullInterpreter` +
  `ConstantDirectionInterpreter` (proof-of-contract stubs) + `MovingAverageCrossInterpreter`
  (Plan 4 — simplest *realistic* reference; reuses `indicators.sma`/`atr`). NONE are real edges.
- [`scripts/research/qualify_interpreter.py`](../../scripts/research/qualify_interpreter.py) —
  thin driver (`--interpreter {ma_cross,pnf}`): register adapted interpreter → `HypothesisRunner` +
  `QualificationGate` on real data → print `EdgeReport` + verdict + Δ-vs-control table (via the
  independent `metrics_oracle`) + first-N provenance lines (chain observability).
- [`src/interpreters/point_and_figure.py`](../../src/interpreters/point_and_figure.py) — **PNF-v1**
  (Plan 5), the FIRST real interpreter: double-top / double-bottom on an ATR-fraction box grid.
  Shadow-measured → **REJECT** (F-028; FROZEN). Extends `EventKind` with `DOUBLE_TOP_BREAKOUT` /
  `DOUBLE_BOTTOM_BREAKDOWN` (the designed extension point).
- [`src/research/contracts.py`](../../src/research/contracts.py) (`Hypothesis`, `Signal`) — the
  adapter target (frozen; never edited). `forward_walk` + `qualification.py` — the reused oracle.

## Ins / Outs
- **Ins:** a `window: Sequence[Candle]` (+ `features`, `ctx{instrument}`); reuses the frozen
  `Direction` enum + `Candle` from `config_layer/crt_engine_v2.py`.
- **Outs:** `InterpreterReading` (the pure `observe()` result); via the adapter, research `Signal`s
  carrying provenance (`trace_id`, confidence, strength) in `Signal.meta` → `forward_walk` →
  `Outcome` → `EdgeReport`.

## Entry points & validations
- **Reached via:** `InterpreterHypothesis(interp)` → `HypothesisRunner` / `forward_walk` (measurement)
  — the same path `SpineHypothesis` uses. (Live fusion integration is a LATER plan.)
- **Validated by:** `BaseInterpreter._validate` (confidence/strength ∈ [0,1], `kind` ∈ EventKind,
  `direction` ∈ {Direction, None}, non-empty trace_id, present observation_time) + the existing
  7-gate `QualificationGate` once measured.

## Tests
- [`tests/interpreters/test_interpreter_contract.py`](../../tests/interpreters/test_interpreter_contract.py)
  — conformance/guards, determinism + observation_time-from-last-bar, `test_fusion_is_identity_blind`,
  and the KEY adapter → `forward_walk` → `EdgeReport` round-trip.
- [`tests/interpreters/test_reference_ma_cross.py`](../../tests/interpreters/test_reference_ma_cross.py)
  — MA-cross unit (cross detection, bounded conf/strength, purity). [Plan 4]
- [`tests/interpreters/test_reference_interpreter_e2e.py`](../../tests/interpreters/test_reference_interpreter_e2e.py)
  — END-TO-END chain proof on real BNBUSDT data (chain runs, verdict ≠ PROMOTE, sha256-deterministic). [Plan 4]
- [`tests/interpreters/test_invariant_guards.py`](../../tests/interpreters/test_invariant_guards.py)
  — `explain()` inert + `meta` opaque (the two strongest contract invariants). [Plan 4]
- [`tests/test_metrics_v2.py`](../../tests/test_metrics_v2.py) — Metrics Oracle V3 (efficiency /
  symbol-attribution / concentration) parity (bundled in Plan 3).

## Fits in architecture
Level 4 (Interpreters) in the owner's hierarchy: Truth → Goal → Metrics → **Oracle → Interpreter
Contract** → Adapter → forward_walk → QualificationGate → EdgeReport → (later) Fusion. Sits beside
the research [Edge Discovery Program](../../src/research/) and reuses its measurement spine.

## Discussion (filled in-session)
> Standing parallel-discussion surface. Append dated entries; never delete — supersede.

- **Risks:** 2026-06-14 — contract creep. Owner froze the surface: no `InterpreterOracle`, no extra
  fields beyond the agreed set; next step is to PROVE with the reference interpreter, not extend.
- **Challenges:** 2026-06-14 — honoring the frozen pure-`detect` invariant while giving the owner's
  observe/events/confidence/unknowns/failure surface → resolved as one pure `observe()→reading`,
  capabilities as reading fields + Base defaults; `trace_id`/`observation_time` derived from the last
  bar (deterministic, replay-safe), never wall-clock.
- **Blockers:** none.
- **Ambiguities:** 2026-06-14 — `Direction.NONE` vs `Optional[Direction]` → reused the frozen
  `Direction` enum + `None` for non-directional (no shared-enum edit).
- **Enhancements:** 2026-06-14 — Plan 4 DONE (MA cross → REJECT, chain proven). **Plan 5 DONE:
  PNF-v1 (P&F double-top/bottom) = first REAL interpreter, shadow-measured on BNBUSDT → n=8554,
  PF 0.528, E −0.4538, verdict REJECT, worse than random (Δexpectancy −0.039). Recorded F-028 +
  FROZEN in the Funding-Ledger falsified-interpreters list — reopen only via a NEW ontology, never a
  box/reversal sweep.** Next: Plan 6 fusion experiments (gated on honest verdicts, not alpha).
- **Need more info:** whether ANY interpreter improves G001 — two falsified so far (MA cross, P&F);
  the chain reliably rejects weak producers, which is the point.
