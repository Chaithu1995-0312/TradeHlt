# Feature Layer Mutation Freeze (2026-07-20)

| Field | Value |
|---|---|
| Freeze ID | `FEATURE-LAYER-MUTATION-FREEZE-2026-07-20` |
| Status token | **`FEATURE_LAYER_MUTATION_FREEZE = ACTIVE`** |
| Freeze class | **`GOVERNANCE_FREEZE`** (not scientific closure) |
| Effective | 2026-07-20 · scope revision **2026-07-20b** (XAUUSD-only pin) |
| Mechanical pin | [`feature-layer-freeze-pin-2026-07-20.json`](feature-layer-freeze-pin-2026-07-20.json) |
| Working tracker (closed queue) | [`docs/implementation_plan/feature-layer-tracking-2026-07-19.md`](../implementation_plan/feature-layer-tracking-2026-07-19.md) |
| Engineering focus after freeze | [`docs/implementation_plan/backtest-runtime-roadmap-2026-07-20.md`](../implementation_plan/backtest-runtime-roadmap-2026-07-20.md) |
| Active config | `v2_multi_2026_04` (`configs/production/ACTIVE_VERSION`) |

---

## CORRECTION (2026-07-31, §6.2 rule 4 — historical record preserved below, not edited in place)

Every "dim 38" / "3871×38" figure in this document (lines 58, 117, 118, 129 below) is an
**accurate snapshot of the 2026-07-20 freeze**, not a current claim. The canonical vector was
migrated from schema v3.0 (38-dim) to **schema v4.0 (39-dim)** on 2026-07-22
(SCHEMA-V4-VECTOR-MIGRATION: MACD histogram split into `macd_hist_raw`/`macd_hist_z`,
`wick_size`→`candle_range` rename, `session` domain widened to 5 values — see
`src/features/feature_schema.py:47-68`), i.e. **after** this freeze was declared, under its own
authorized program per the freeze's own §"Accepted future programs" provision. The mechanical
pin `feature-layer-freeze-pin-2026-07-20.json` (schema 1.1.0, scope 2026-07-20b) is therefore
**superseded for its dim/shape fields specifically** — a fresh XAUUSD vector SHA computed today
will not match that pin's recorded hash, and that mismatch is EXPECTED (schema migration, not
regression). The freeze's governance INTENT (routine feature-layer edits require evidence + a
waiver) is unaffected and remains active. Do not re-run the 2026-07-20 pin as a pass/fail gate
without accounting for this migration.

---

## Freeze class (read this first)

This is a **governance freeze**, not a scientific freeze.

| Means | Does **not** mean |
|---|---|
| Routine feature-layer edits are forbidden without evidence + waiver | The feature layer is “perfect” or research-complete |
| Free-form churn has diminishing returns vs runtime/measurement | We never revisit features |
| Accepted future programs remain valid scientific work | L6 activation or economic edge is proven |
| Matching the pin SHA = feature-matrix parity on XAUUSD | Full trading-path behavioral equivalence |

**Psychological guard:** do not let the freeze become “we never touch features again.”
It means **changes require evidence and a waiver.** Named programs (M16, T-11, FM-030/031
migration, T-17/18/19, …) stay legitimate — they are simply not routine engineering.

---

## Why this freeze exists

The 2026-07-18/19 feature-governance session closed the **actionable** feature-layer queue
(config periods, ontology parity, lint coverage, live-ingress fail-closed, wick name collisions,
registration of MACD/session/hour, etc.). Identity certification is exhausted
(`FEATURE_IDENTITY_FRONTIER_EXHAUSTED: YES` per
`feature_completion_alignment_census-2026-07-14.json`). Completion frontier is **not**
exhausted (M16 work units remain), but further free-form feature work has diminishing
governance ROI relative to backtest/runtime correctness.

This freeze is a **mutation freeze**, not L6 activation and not economic closure:

- It does **not** claim `FEATURE_PROGRAM_CLOSED = YES`.
- It does **not** grant activation authority (CLAUDE.md §6.5 Authority Ladder).
- It does **not** reverse M16 `BLOCKS_ACTIVATION: true` debts — it **parks** them under
  explicitly accepted future programs.
- It treats the feature layer as **governance-frozen but scientifically extensible**.

---

## Frozen surfaces (do not edit without a waiver)

Unless covered by an **accepted future program** (pin JSON + § below) or a documented
behavior-change authorization:

1. **Canonical vector identity** — `CANONICAL_FEATURES` / schema hash / dim 38
   (`src/features/feature_schema.py`). [dim SUPERSEDED 2026-07-22 → 39, see CORRECTION above]
2. **Batch emission math** — `src/features/feature_pipeline.py` indicator/structure/temporal
   formulas and emission order.
3. **Scalar geometry / derived registry** — `candle_math.py`, `derived_math.py`,
   `src/features/registry/**`.
4. **Ontology WHAT layer** — `configs/formulas/market_ontology.yaml` (new FM ids, formula
   identity changes).
5. **HOW periods already migrated** — `feature_pipeline` section keys in production configs
   that redefine registered identities (changing them redefines FM lookbacks; requires
   recertification).
6. **Causal structure windows** — `resolve_swing_window` / `resolve_double_sweep_window`
   single-source contract.
7. **Feature-math ownership floor** — do not weaken `feature_math_lint` classifiers or
   re-introduce retired GD pins without a new finding.

---

## Explicitly accepted future programs (exceptions)

These may proceed **only** under their named plan + construction protocol, not as ad-hoc
feature edits. Full list is machine-readable in the freeze pin
`accepted_future_programs`.

| Program | When allowed |
|---|---|
| `M16-WU-SESSION-ENCODING` / `TREND-STRENGTH-COLLISION` / `VOLREGIME-S05` | Future **live_engine_hook / consumer-alignment** phase (user-deferred 2026-07-19) |
| `M16-WU-SUPERSEDED-VECTOR-MIGRATION` | Explicit migration plan + retrain gates; **no silent dim swap** |
| `M16-WU-FM025-PROVENANCE` / `EMPTY-SHA-FAMILY` / `ONTOLOGY-REGISTRATION` | Ledger/ontology hygiene; no formula change unless separately authorized |
| `M16-WU-L6-PREP` | Only after activation-blocking M16 units are addressed or re-scoped |
| `T-5` / `T-6` | Warmup/finalize guards (user-deferred) |
| `T-11-FEEDER-HANDSHAKE` | Coordinated with external EA (`feed_schema_version` + period symmetry) |
| `T-17` / `T-18` / `T-19` | Named semantic revisits (macd_hist z-score; volregime knobs; rename) |
| `STATEFUL-6` | User-excluded until pipeline stable |
| `ZONEGATE-ALIGNMENT-SAFETY-NET` | **Authorized 2026-07-22.** Fail-closed vector alignment for the only live hard gate; prerequisite of the schema-v4 migration. Parity contract: no-op at v3.0 (ledger stays `9bcba138775d4109`) |
| `SCHEMA-V4-VECTOR-MIGRATION` | **Authorized 2026-07-22.** Canonical vector 38→39: `macd_hist`→`macd_hist_raw`+`macd_hist_z`, `wick_size`→`candle_range`, FM-052 session domain {0,1,2}→{0..4}. **`PRODUCTION_BEHAVIOR_CHANGED = YES`** — no parity contract; the binding requirement is full attribution of the ledger delta. Absorbs `M16-WU-SUPERSEDED-VECTOR-MIGRATION`, `M16-WU-SESSION-ENCODING`, `T-17`, `T-19` (retained above, not deleted) |
| `FM-030-031-DIMENSIONAL-MIX-MIGRATION` | **Authorized 2026-07-22.** Config-gated identity only (`feature_pipeline.normalization_basis`, default `atr_relative` == prior literal math) + additive scalars + ontology `active:false` + hash-neutral shadow config. Parity contract: XAUUSD vector SHA **unchanged**. No promotion, no `ACTIVE_VERSION` change, no `dual_engine` threshold recalibration, no retrain, no dim change. Evidence: F-061 |

> **Waiver-log note (2026-07-22).** Three pinned sources (`market_ontology.yaml`, active config,
> `feature_pipeline.py`) were **already drifted** from the 2026-07-20 pin when the FM-030/031
> session opened — before any edit by that change set, and not a line-ending artifact. The
> XAUUSD vector regression *passed* at session open, so the pre-existing drift changed no
> emitted feature value. The SHA refresh in that change set absorbs both the pre-existing drift
> and the program's intended edits; pre-session values are preserved in the pin's `waiver_log`
> (§6.2 rule 4). Provenance of the pre-existing drift is **unidentified** — the working tree has
> been uncommitted since 2026-07-09.

Anything **not** on this list requires a new user-approved future-program entry **before**
mutating frozen surfaces.

---

## Regression benchmark (mechanical) — feature layer only

Pin: [`feature-layer-freeze-pin-2026-07-20.json`](feature-layer-freeze-pin-2026-07-20.json)
(schema **1.1.0**, scope revision **2026-07-20b**).

| Benchmark | Contract | Purpose |
|---|---|---|
| **XAUUSD 2-month** | Full CSV → `FeaturePipeline.run()` → float32 matrix SHA-256 | Primary feature-layer regression oracle (3871×38 at the 2026-07-20 snapshot; SUPERSEDED to 39-dim 2026-07-22, see CORRECTION above) |
| **Schema** | v3.0 / 38 features / schema hash / name list | Detect schema drift [now v4.0/39 — CORRECTION above] |
| **Source SHAs** | Ontology, active config, pipeline, schema, candle/derived/causal math, registry | Detect provenance drift |

**Removed from this pin (2026-07-20b):** BNB head vector hash. BNB remains a good corpus for
**runtime** baselines under roadmap R-1/R-2; it is not part of the frozen *feature* contract.

### Coverage metadata (anti false-green)

The XAUUSD entry carries a `coverage` object. Matching the vector SHA means **only**:

- batch `FeaturePipeline.run()` on that CSV  
- 38-dim float32 emission after warmup drop [SUPERSEDED 2026-07-22 → 39-dim, see CORRECTION above]  

It explicitly marks as **not exercised:** backtest_v2, CRT SM, session filter, zone gate,
fusion, DecisionEngine, planner, Ultron, partial TP, trade ledger.

Runtime/filter/planner coverage is recorded when the **runtime benchmark suite** opens
(roadmap R-1/R-2), not by expanding this pin into a fake full-path oracle.

Enforcement: `tests/test_feature_layer_freeze.py`.

**Pass criterion:** XAUUSD vector SHA + schema + source pins match (or a documented waiver
updates the pin in the **same** change set).

**Not a pass criterion:** trade count, PnL, expectancy, filter admissions — runtime suite.

---

## Forbidden without waiver

- New production feature math or local re-derivation of registered identities.
- Expanding the 38-dim vector or renaming canonical keys.
- “Drive-by” period / threshold changes in `feature_pipeline` that re-cert would require.
- Re-opening B-phase / L6 activation work under a new informal tracker.
- Hand-editing the freeze pin vector hashes without re-running the pipeline contract.

---

## Allowed without unfreezing

- **Backtest / runtime / execution / risk / governance** work that does not mutate frozen
  feature sources (see engineering roadmap).
- Docs, findings, tests that **assert** the freeze (including this file).
- Consumer-alignment under M16 P1–P3 when that phase is opened (consumers, not pipeline math).
- Read-only probes, census regenerate, lint check.
- Bugfixes that restore the pin after accidental drift (must re-green the freeze test).

---

## Waiver procedure

1. Name the accepted future program (or obtain user approval to add one to the pin).
2. Classify via construction protocol / change contracts.
3. Implement with parity or declared behavior change.
4. Update the freeze pin (source SHAs + any affected vector SHAs) in the **same** change set.
5. Re-run `tests/test_feature_layer_freeze.py` + relevant feature floors.
6. SESSION LOG entry citing freeze_id + program id.

---

## Relationship to other closures

| Surface | Relation |
|---|---|
| CANONICAL_FEATURE_CODE_SURFACE **CLOSED** | Still closed; this freeze is an additional **mutation** guard on top of identity closure |
| Feature completion census | Identity exhausted; completion not closed; freeze parks completion work |
| OHLCV corpus freeze | Orthogonal — data substrate, not feature math |
| L6 ACTIVATION | **Not started**; freeze does not authorize it |

---

## Engineering focus after freeze

**Primary:** [`docs/implementation_plan/backtest-runtime-roadmap-2026-07-20.md`](../implementation_plan/backtest-runtime-roadmap-2026-07-20.md)

Feature-layer queue work stops except accepted future programs. New sessions default to
backtest/runtime roadmap items.
