# Three-Track Semantic-Layer Program — Tradelatest

## Context — why this change

The user assessed the 11-phase target architecture and diagnosed the **semantic middle
(Phases 2–5: Feature States → Market Context → Market Shape → Historical Statistics)** as the
"biggest gap," mostly unbuilt, and asked to prioritize building it.

Exploration overturned that premise. Those four layers **already exist** — a coherent,
roadmap-numbered, tested, *shadow-only* pipeline, each module verified against source:

| Phase | Existing module | Self-label |
|---|---|---|
| 2 Feature States | `src/features/feature_states.py` `FeatureStateEncoder` | "Layer 2 … roadmap Phase 2C" |
| 3 Market Context | `src/features/market_context.py` `MarketContextBuilder` | "Layer 4 … roadmap Phase 3" |
| 4 Market Shape | `src/features/market_shape.py` `MarketShapeClassifier` | "Layer 5 … roadmap Phase 5" |
| 5 Historical Stats | `src/research/shape_statistics.py` | "Historical Statistics layer — Layer 6" |

They were deliberately built and **shelved** for two documented reasons: (a) §6.5 authority
discipline — stamped `DESCRIPTIVE_ONLY`, no demonstrated ΔG001 → no authority to wire; and (b) the
edge-seeking version was reported non-economic (F-023/F-041B/IC-003B).

**The user's governing correction:** those legacy nulls sit on contaminated substrate
(F-022 mislabels, F-051 centered-swing PIT leak, F-037 gate-off, F-044 RR mis-spec) and may not be
trustworthy — so **no legacy finding may be cited as a settled premise. Every verdict is
re-derived on a clean substrate.** The user chose to pursue all three directions (1+2+3).

**Intended outcome:** a PIT-honest descriptive semantic surface (A), a *fresh* clean-substrate
verdict on whether shape/context carries edge (B) that confirms-or-overturns F-023 on its own
data, and progress on the repo's own edge-independent value gaps (C) — calibration, portfolio,
live-PnL, drift actuator.

## Guiding principle (applies to all tracks)

Re-derive, never inherit. Clean labels only (`forward_walk(intrabar_fixed)` / `clean_labels` /
episode re-walk — never `opportunities.jsonl`). PIT-clean features. Explicit gate config. XAUUSD
corpus (`data/mt5/XAUUSD_M15.csv`). Additive/surgical only (§3, §6.5 fail-fast, no silent
defaults). Nothing earns production authority without demonstrated ΔG001 through the M4 gate.

## Sequencing (three waves; tracks coupled by substrate, not value)

The one hard dependency: **A2 (band FM-030) must land before B1 freezes its shape projection**,
else B re-tests the contaminated legacy magnitude or drops the trend axis entirely.

```
WAVE 1 (parallel):  A1 bootstrap CIs · C1 allocator shadow-replay · B0 pre-registration doc
WAVE 2 (A2→B1):     A2 FM-030 banding · B1 clean-substrate shape edge re-test · C2 calibration (shadow)
WAVE 3:             A3 unified market-state report · B2 register finding · C3 drift actuator
```

## Track A — Descriptive consolidation (PIT-honest interpretability surface)

- **A1 (first, auto-proceed):** bootstrap CIs in `shape_statistics.py`. New
  `src/research/measurement/bootstrap.py` — deterministic percentile `bootstrap_ci(values, *,
  n_boot, alpha, seed)` seeded like `qualification._seed_for`. Extend `CellStats` with
  `fwd_ret_ci_lo/hi` + `ci_method/n_boot/seed` provenance. Preserve the `DESCRIPTIVE_ONLY` /
  `insufficient` stamps.
- **A2 (user-gated — see gates):** unblock continuous banding by declaring **integer states on
  FM-030** in `configs/formulas/market_ontology.yaml` (registered, `parity_verified`,
  dimensionless, scale-invariant) — **not** the legacy FM-022 magnitude (F-061 defect). Band edges
  are a modeling choice: propose data-driven quantiles of the PIT-clean FM-030 distribution on
  XAUUSD; do not freeze unilaterally.
- **A3 (auto-proceed):** unified read-only report — "current bar: states → context → shape, and how
  that shape resolved historically (with CIs)." No spine wiring, no authority.

## Track B — Clean-substrate edge re-test (the epistemically load-bearing track)

**B1 first milestone:** one registered `Hypothesis` — new
`src/research/hypotheses/market_shape_hypothesis.py` (pattern: `spine_hypothesis.py`), whose
`detect()` classifies `window[-1]` via `MarketShapeClassifier.classify_vector` and emits a `Signal`
iff the shape/family matches a **pre-registered** target, direction from a **pre-declared,
non-fitted** rule. Reuse verbatim: `HypothesisRunner.collect()`, `forward_walk(intrabar_fixed)`,
`EdgeAggregator`, `qualification` (7 gates + BH-FDR), controls `always_long` + `random_baseline`.
Config: `configs/research/research_config_shape_xauusd.json` (XAUUSD, intrabar_fixed, explicit
`q_*` knobs + `round_trip_bps`).

**Anti-contamination design (five guarantees):**
1. **F-022 (labels):** labels only from `forward_walk` on raw CSV bars; `detect()` reads only
   OHLCV-derived features and fail-fasts if fed any `outcome`/`rr_achieved`/`mfe` key.
2. **F-051 (PIT leak):** blocking projection audit — `MarketShapeClassifier.projection` ∩
   centered-swing-contaminated dims **must be ∅** (test `tests/test_shape_hypothesis_pit.py`), or
   drop/re-derive that dim. Plus the kernel's structural no-future-bar guarantee (`.index >
   entry_index`), inherited free by adding no exit logic.
3. **Feature substrate:** shape trend axis bands **FM-030** (A2), not FM-022 — critical on XAUUSD
   (FX-class, where the legacy magnitude binds).
4. **F-037/F-044 (gate config):** pre-registration explicitly records `exit_model=intrabar_fixed`,
   explicit bps + a **0bps sensitivity twin** (XAUUSD M15 cost caveat), that a pure shape hypothesis
   never invokes the fusion spine (so `BACKTEST_ENGINE_GATE` is N/A — stated, not silent), and that
   `rr_fusion` stays `enabled:false`.
5. **Controls + registration:** gate-4 "beats winning control" vs `always_long` +
   `random_baseline` + a pre-registered **unconditional-entry twin** (isolates "shape selects" from
   "geometry pays"). Any multi-family sweep submitted as **one cohort** so BH-FDR (gate 7) corrects
   across it. **B2:** register the verdict as a new `F-0xx` in `docs/current-findings.md`
   (regenerate `data/findings.jsonl` via `scripts/governance/export_findings.py`) with a
   pre-registration doc `docs/research/preregistration-*-shape-edge-xauusd.md` written **before** the
   run. It updates F-023/F-041B as a prior, never cites them as premise. Authority: research-only.

## Track C — Decision/execution value gaps (edge-independent)

- **C1 (first, auto-proceed):** PortfolioAllocator shadow-replay (F-013). New `src/portfolio/
  replay.py` (logic) + `scripts/portfolio/replay_allocator.py` (thin CLI, §3.3). Streams a closed
  trade ledger through `PortfolioAllocator.allocate/open_position/close_position`, emits an
  allocation-decision JSONL; recompute realized-vs-shaped PnL via `metrics_oracle`. Spine-isolated
  (imports nothing from `src/runtime`/`src/inout`).
- **C2 (auto-proceed, shadow):** probability calibration layer — reliability curve / Brier on
  held-out **clean** labels (`forward_walk`, never stream). Shadow-only.
- **C3 (user-gated):** drift **actuator** (F-008: `live_engine_hook.py:676` drift is logged, never
  acted on). Live-spine-adjacent → `BEHAVIOR_CHANGE_AUTHORIZED`; actuation policy is a user decision.

## Critical files

- `src/research/shape_statistics.py`, new `src/research/measurement/bootstrap.py` (A1/A3)
- `configs/formulas/market_ontology.yaml` (A2 — FM-030 state declaration)
- `src/research/runner.py` + `src/research/qualification.py` (B — reuse verbatim)
- `src/features/market_shape.py` (B — classifier wrapped; projection = PIT audit target)
- new `src/research/hypotheses/market_shape_hypothesis.py` + `configs/research/research_config_shape_xauusd.json` (B1)
- `src/portfolio/allocator.py` + `src/analytics/metrics_oracle.py`, new `src/portfolio/replay.py` (C1)

## Verification

- **A:** `tests/test_shape_statistics.py` (seeded-bootstrap determinism, DESCRIPTIVE stamp
  preserved); A2 extends `tests/test_market_shape.py` + must keep `tests/test_fm030_031_
  normalization_basis.py` green; A3 golden-render + no-authority-language grep.
- **B:** two-run byte-identical `edge_report`; blocking `tests/test_shape_hypothesis_pit.py`
  (projection ∩ contaminated-dims == ∅; `detect` raises on stream fields); run the M4 gate, capture
  full 7-gate `reject_reasons`; cross-check n/PF/E against `metrics_oracle`; 0bps cost-sensitivity twin.
- **C:** `tests/portfolio/test_replay_allocator.py` (determinism + spine-isolation +
  metrics_oracle reconciliation); C2 reliability/Brier on clean labels; C3 behavior-preservation
  (inert below threshold) + SESSION LOG + doc-drift decision.
- **Cross-cutting:** each governed change → `📝 SESSION LOG ENTRY` in `assistant_project.md` +
  doc-drift decision (`DOCUMENTATION_DRIFT_PROTOCOL.md`); A2 also runs
  `scripts/governance/construction_protocol.py check`.

## User-decision gates (do not auto-proceed)

1. **A2 FM-030 band cut-points** — feature-layer change under freeze waiver; propose quantiles, user picks edges.
2. **B0/B2 pre-registration + any finding that overturns F-023/F-041B** — governance sign-off before the run and on the final finding.
3. **Sequencing appetite** — run all three waves concurrently vs. gate Wave 2 on Wave 1.
4. **C3 actuation policy** — what the drift actuator does (pause / downsize / alert-only).

**Auto-proceed (additive, shadow-only, no authority):** A1, A3, B1 authoring + M4 run (produces
evidence, earns nothing), C1, C2 — all enforced spine-isolated by tests.
