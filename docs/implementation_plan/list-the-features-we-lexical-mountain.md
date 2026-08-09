# Architectural Roadmap Review — layer inventory, conflicts, and the next safe phase

## Context

The platform is in an architecture consolidation phase: one canonical implementation per
responsibility, no parallel pipelines, no ambiguous ownership. This document reviews the 11-layer
target architecture against what is actually in the repository, and proposes the smallest safe next
phase.

Phase 1 (Feature Mathematics & Canonical Features) completed 2026-07-24: ontology v1.4, canonical
coverage 23/39 → 37/39, feature vector byte-identical.

**Headline finding:** the roadmap's Phase 2 is not a greenfield build. **Five parallel market-state
implementations already exist**, across five different consumption tiers. Building a sixth would
violate the consolidation policy in the same commit that claims to serve it. Phase 2 must be scoped
as a *consolidation*, not a new layer.

---

## 1. Layer inventory

| # | Layer | Status | Authoritative module(s) |
|---|---|---|---|
| 1 | Feature Mathematics | **COMPLETE** | `configs/formulas/market_ontology.yaml` (v1.4) · `features/candle_math.py` · `derived_math.py` · `features/registry/` |
| 2 | Canonical Features | **COMPLETE** | `features/feature_schema.py` (39-dim v4.0) · `features/feature_pipeline.py` |
| 3 | Feature States | **PARTIAL — 5 competing impls** | see §3 |
| 4 | Market Context | **MISSING** | no module aggregates states into one description |
| 5 | Market Shape / Cluster | **PARTIAL, off-spine** | `regime/market_state_cluster_engine.py` (sidecar) · `research/ic003_shapes/` · `research/synthetic/` story ontology |
| 6 | Historical Statistics | **PARTIAL, off-spine** | `replay/replay_memory_engine.py` · `models/zone_registry.json` stats · `research/measurement/` |
| 7 | Model Intent | **COMPLETE (declarative)** | `active_models.yaml` v2.1 — already has `intent`/`runtime`/`evidence`/`status` truth layers |
| 8 | Evidence Fusion | **EXISTS** | `core/fusion_engine.py` (+ `hierarchical_meta_fusion.py`, sidecar) |
| 9 | Trade Score | **EXISTS but STRUCTURALLY DEAD** | `core/decision_engine.py` — see §4 Conflict A |
| 10 | Trade Economics | **PARTIAL** | `config_layer/execution_planner.py` · `core/ultron_risk_gate.py` (spread + slippage tax, sizing) |
| 11 | Portfolio Validation | **EXISTS, off-spine** | `governance/portfolio_validation.py` · `portfolio/allocator.py` (**0 importers**) |
| 12 | Execution | **PARTIAL** | `runtime/live_engine_hook.py` (live) · `execution/alert_manager.py` · `live/mt5_bridge.py` · `execution/loop.py` (**orphaned**) |

Reading: layers 1–2 are consolidated and owned. Layers 3–6 exist as research/sidecar code with no
spine consumption. Layers 8–12 exist on the spine but are gated behind a structural defect.

## 2. What the live spine actually calls

`runtime/live_engine_hook.py` → `core/engine_runner.py` imports exactly: `crt_engine`,
`heuristic_gaussian_engine`, `ml_gaussian_engine`, `zone_gate_engine`, `zone_cluster_score`,
`rr_engine`, `fusion_engine`, `decision_engine`, `regime_governor`, `trap_validator_engine`,
`acceptance_controller`, `convergence_controller`, `collector`.

It imports **none** of: `regime/market_state_cluster_engine`, `replay/replay_memory_engine`,
`cognitive/cognitive_bus`, `msip/`, `research/candle_state/`, `interpreters/regime_observer`,
`portfolio/allocator`. Layers 3–6 are entirely off the decision path (consistent with F-012/F-013).

## 3. Conflict A — five parallel market-state implementations

This is the primary architectural debt the roadmap must resolve, and it is invisible from the layer
diagram because each implementation sits in a different tier:

| Implementation | Tier | Consumed by |
|---|---|---|
| `CRTState` state machine (`config_layer/state_identity.py`, 9 states) | **LIVE — canonical** | `crt_engine_v2`, the whole spine |
| `regime/regime_classifier.py` | **LIVE — second authority** | `runtime/live_engine_hook.py`, `execution/loop.py`, `regime/config_router.py`, `training/stage1_dataset_builder.py` |
| `regime/market_state_cluster_engine.py` (`MarketStateOutput`) | sidecar | `cognitive/cognitive_bus.py` only (F-012) |
| `research/candle_state/encoder.py` (`CandleStateEncoder`) | research | 4 research modules |
| `interpreters/regime_observer.py` (`RegimeLabeler`) | research | 2 research modules |
| `msip/market_state_vector.py` (`MarketStateVector`) | shadow | `msip/` only, hard-wired inert |

Two of these are on the **live** path simultaneously (`CRTState` and `RegimeClassifier`) with no
declared relationship. That is the ambiguous-ownership case the policy targets. The other four are
independent re-derivations of "what state is the market in".

**Migration position, not another abstraction:** `CRTState` owns *sequence* state (where we are in
the sweep→displacement→retest cycle). `RegimeClassifier` owns *conditions* state. These are
genuinely different questions and both should survive — but the ontology must say so, and the other
four must be reduced to consumers of one of them or explicitly retired.

## 4. Conflict B — layers 9–12 are gated behind a dead branch (BLOCKING)

F-048: `DecisionEngine`'s RR gate compares `fusion["rr"]` against `rr_threshold = 1.5`, but the
value wired into that slot at `engine_runner:957` is `RREngine.rr_ratio` — a candle-polarity score
bounded in [0.5, 1]. It can never exceed 1.5, so `low_rr` fires on every candle and `run()` has
returned `execute` **0 times in 70,002 bars**. `ExecutionPlanner:208` hard-gates on
`run() == "execute"`.

Consequence for this roadmap: **Trade Score → Trade Economics → Portfolio Validation → Execution is
structurally unreachable on the live path.** Any roadmap investment in layers 8–12 is unverifiable
until this is resolved — you cannot measure a layer that never receives input.

This is a one-line-class defect with a genuine open question attached (is the live path dormant *by
design*, or mis-wired?). It is not in Phase 2's scope, but it should be decided before any layer
8–12 work is scheduled.

## 5. Missing abstractions

1. **Market Context (layer 4)** — nothing aggregates individual states into one description. This
   is the genuine gap; everything else in 3–6 exists in some form.
2. **A state ENCODER on the spine** — the ontology now *declares* states (v1.4), but no runtime
   component converts a canonical feature vector into a state vector.
3. **Threshold ownership for continuous→state banding** — where does "ema_spread > X ⇒ Strong Bull"
   live? Per §6.5 these are BEHAVIORAL and belong in `configs/production/*.json`, not in code.
4. **Cost model ownership (layer 10)** — `research/costs.py` (12 bps, research) and
   `ultron_risk_gate` spread/slippage (live) are two unrelated cost models. Not yet in conflict
   because they never meet, but they will when layer 10 is built.

---

## 6. Recommended next phase — Phase 2, scoped as CONSOLIDATION

**Why this one:** it is the direct successor to completed Phase 1; **its declarative half already
exists** (ontology v1.4 `states` blocks); layers 3–6 cannot be built without it; and it is the
phase that forces the five-implementation conflict to be resolved rather than deferred. It is also
declarative-first, therefore behavior-preserving and reversible.

**Explicitly NOT in this phase:** no new runtime state engine, no spine wiring, no model changes,
no work on layers 8–12 (blocked by §4).

### Phase 2A — Declarative state definitions (ontology-only, zero code)

The 8 `structural_states` entries (FM-054…061) already carry full `states` blocks. Extend the same
`states` schema to the **continuous** canonical features that have a natural banding, using the
existing `states_shape` contract (`name` / `value` / `condition` / `description`):

| Feature | Proposed bands |
|---|---|
| `ema_spread` (FM-022) | StrongBear · WeakBear · Neutral · WeakBull · StrongBull |
| `volume_ratio` (FM-062) | Low · Normal · High |
| `retest_depth` (FM-021) | None · Healthy · Deep |
| `disp_strength` (FM-020) | NoDisplacement · Moderate · Strong |
| `volatility_ratio` (FM-024) | Compression · Normal · Expansion |
| `rsi_14` (FM-042) | Oversold · Neutral · Overbought |

Band **boundaries** are BEHAVIORAL → declared in `configs/production/*.json` under a new
`feature_states` section and referenced from the ontology via the existing `config_keys` mechanism,
never hardcoded. Reuses: `spec_schema.states_shape`, `_validate_spec_schema`, and the
`test_ontology_config_parity` token rule that already enforces config↔formula agreement.

**Files:** `configs/formulas/market_ontology.yaml`, `configs/production/v2_multi_2026_04.json`
(new hash-neutral section), `src/features/registry/__init__.py` (validation only).

### Phase 2B — Ownership adjudication (documentation, zero code)

Produce one decision record naming, for each of the five implementations in §3: canonical /
consumer / retire. Expected outcome — `CRTState` = canonical sequence state; `RegimeClassifier` =
canonical conditions state; `MarketStateClusterEngine` + `MarketStateVector` = retire or fold;
`CandleStateEncoder` + `RegimeLabeler` = research-only, declared as such.

This is the "document the conflict and propose migration" step the policy requires *before* any
code moves.

### Phase 2C — Runtime encoder (deferred until 2A + 2B are approved)

One `FeatureStateEncoder` consuming the canonical vector + the declared bands, emitting a state
vector. Additive and shadow-only at first: emitted alongside the existing vector, consumed by
nothing, proven inert by the same XAUUSD SHA parity gate used in Phase 1.

### Completion criteria for Phase 2

- Every canonical feature either declares `states` or is explicitly marked continuous-without-bands.
- Band boundaries live in config, strict-read, no silent defaults.
- One decision record with a named owner per state implementation.
- XAUUSD vector SHA `37f43f44…` unchanged; `validate_registry() == []`; no new test failures.

---

## 7. Sequencing recommendation for the remaining roadmap

`Phase 2 (states + ownership)` → `Phase 4 Market Context` (the real gap) → `Phase 5 Shape`
(consolidating onto the Phase-2 canonical encoder) → `Phase 6 Statistics`.

**Layers 8–12 should not be scheduled until the §4 F-048 decision is made.** Fixing that is
cheap and unblocks four layers; building on top of it while it is dead produces unverifiable work.

## Verification (applies to every phase above)

1. `python -c "import sys; sys.path.insert(0,'src'); from features.registry import validate_registry; print(validate_registry())"` → `[]`
2. `python -c "import sys; sys.path.insert(0,'src'); import config_layer.crt_engine_v2"` → clean (the import-time ontology read path)
3. `pytest tests/test_feature_spec_schema.py tests/test_feature_lineage.py tests/test_ontology_config_parity.py -q`
4. XAUUSD vector SHA re-run → `37f43f449af0720ff547dcb9cd0c45243f0e6c421e1f9475e9c9d75517601ef5`
5. `python scripts/analysis/feature_math_lint.py` → `NEW 0`
