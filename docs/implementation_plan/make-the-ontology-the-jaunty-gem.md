# Plan — Grandfather Divergence Adjudication (read-only) + durable burn-down ledger

> Follows the shipped **F-047** enforcement phase (ontology-authoritative feature math +
> ownership-lint + parity + lineage — DONE; summary at the bottom). This phase does **not** expand the
> feature-math architecture and does **not** remediate any divergence.

## Context

F-047's ownership-lint census grandfathered **10 pre-existing live-surface divergences** into a flat
`key → note` dict — a *baseline ratchet*, not proof of canonicalization. Two flaws: pins are fragile
(keyed by `file::name`; a line move or edited formula wouldn't invalidate them) and unaccountable (no
owner/status/evidence); and reachability was assumed — two traces disagreed on whether the load-bearing
site (live `body_ratio = body/total_wick`) reaches a decision (`engine_runner.py:654` calls
`crt_compute(...)` **with `trade_id="Test:"`** — possibly a harness, not live `run()`). **Unresolved.**

**Goal:** turn the grandfather list into a **measurable, monotonically-shrinking debt-retirement
program** — durable identities, an auditable retirement manifest, source-authoritative reachability with
execution vs decision separated, and evidence kept distinct from inference — **without touching any of
the 10 sites.**

## Hard scope guard (per user answers)

- **ZERO edits to the 10 divergent sites** (`live_engine_hook`, `scoring_engine`, `crt_engine_v2`,
  `crt_sweep_taxonomy`, `rr_engine`). **Defer ALL remediation — even byte-identical — to per-unit
  Phase-B findings.** `git diff` on those files must be empty this phase.
- Code changed this phase = **only adjudication infrastructure** (lint pin *schema* + tests + a
  retirement manifest + a matrix doc; the drift harness is built later — see gates). Not architecture expansion.

---

## Execution order — two gates, two evidence checkpoints

```
GATE 1  (source evidence)
  1. Establish ledger identities (GD-001…GD-010).
  2. Establish durable site fingerprints.
  3. Verify ledger invariants (manifest-based ratchet).
  4. Perform source adjudication and FREEZE Matrix v1.

POST-GATE-1 SYNC
  5. Refine F-047 from frozen Matrix-v1 evidence only.

GATE 2  (source evidence + differential measurement)
  6. Design probes FROM verified consumer paths.
  7. Measure value → score → decision drift.
  8. FREEZE Matrix v2 and rank remediation units.
```
`Matrix v1 = source evidence` · `Matrix v2 = source evidence + differential measurements`. The drift
harness is not written until Matrix v1 is frozen — its architecture is *derived from* verified chains.

---

## GATE 1

### 1. Durable identity ledger — replace flat `_KNOWN_DIVERGENCES` (`scripts/analysis/feature_math_lint.py`)
Assign each grandfather a **stable immutable id `GD-001…GD-010`**. A count cap is not a ratchet
(retire 10→8, add 2, still ≤10). Enforce **set-subset monotonicity** against an append-only manifest
(item 3). Each pin is a structured record: `id (GD-0NN)`, `feature_id (FM-0NN collided)`, `file`,
`enclosing_qualname`, `target_symbol`, `statement_kind`, `rhs_ast_fingerprint`, `durable_key`,
`semantic_class`, `formula_equivalence`, `execution_reachability`, `decision_reachability`,
`observed_value_drift`, `observed_score_drift`, `observed_decision_flips`, `owner`, `evidence`
(two chains — see item 4), `opened`, `review_trigger`.

### 2. Compound durable fingerprint (identifies the SITE, not just the expression)
`file::name` + a bare RHS dump collides across methods. Use:
```
durable_key = SHA256( normalized_file + "\0" + enclosing_qualname + "\0" +
                      target_symbol + "\0" + statement_kind + "\0" + ast.dump(rhs, annotate_fields=False) )
```
- `enclosing_qualname` — module→class→function path via a scope stack during the existing `ast` walk in
  `_scan_module`; `statement_kind` ∈ {Assign, AnnAssign, AugAssign}; `ast.dump(…, annotate_fields=False)`
  is **location-independent, content-sensitive**. Line number stays advisory.
- A pin matches iff its `durable_key` matches. Editing the formula (fingerprint drift) OR moving it to
  another method (qualname drift) makes the pin stale → the site resurfaces as a NEW violation → forced
  re-adjudication.

### 3. Retirement manifest + ratchet tests — `docs/governance/feature-math-grandfather-retirements.json`
`_RETIRED_IDS` as a mutable source set is not truly append-only (a dev can delete an id and restore its
pin, all green). Move retirement into an **explicit, append-only governance manifest** so resurrection is
an *auditable governance violation*, not a one-line edit. Each retirement record:
`{ gd_id, retired_commit, finding_id, resolution_type, evidence_artifact, retired_at }`.
`_ORIGINAL_BASELINE_IDS = frozenset(GD-001 … GD-010)` (immutable in source).

Tests (`tests/test_feature_math_lint.py`):
- `test_grandfather_set_monotonic`: `CURRENT_IDS ∪ RETIRED_IDS == ORIGINAL_BASELINE_IDS`;
  `CURRENT_IDS ∩ RETIRED_IDS == ∅`; no id outside the baseline ever appears.
- `test_retirements_are_evidenced`: every manifest entry has non-empty `finding_id` + `retired_commit`
  + `evidence_artifact`.
- `test_every_pin_well_formed`: all record fields present; `observed_*` default to `not_measured`
  (evidence fields cannot be pre-filled with predictions).
- `test_pin_durable_keys_current`: every current pin's `durable_key` still matches a live site.

### 4. Source adjudication → FREEZE Matrix v1 — `docs/analysis/feature-math-divergence-adjudication.md` (+ `.json`)
Point-in-time forensic (`docs/analysis/`, not living — §6.2 rule 5). **Orthogonal dimensions** — an
inference must never masquerade as measurement:

| Dimension | Values |
|---|---|
| `semantic_class` | same_quantity · name_collision_distinct · transport · unknown |
| `formula_equivalence` | byte_identical · mathematically_equivalent · non_equivalent · unknown |
| `execution_reachability` | reachable · conditional · unreachable · unknown |
| `decision_reachability` | reachable · conditional · unreachable · unknown |
| `observed_value_drift` | measured(stats) · zero · **not_measured** |
| `observed_score_drift` | measured(stats) · zero · **not_measured** |
| `observed_decision_flips` | count/rate · **not_measured** |

**`same_quantity` identity criterion (all must hold, else `name_collision_distinct`/`unknown`):** same
intended market concept · same units/dimensionality · same observation timestamp · same timeframe/context
· same downstream semantic contract. (Name equality alone is insufficient; formula equality is a
separate dimension. Critical for the three `disp_strength` sites — likely distinct quantities.)

**Reachability = two fields, two evidence chains** (source-authoritative, read method boundaries):
- `execution_reachability` — evidence chain `entry point → derivation site` (does the line run at all?).
- `decision_reachability` — evidence chain `derivation site → decision boundary` (does it change
  APPROVE/REJECT, or only enter a diagnostic object?). Each verdict carries a **required call-chain
  citation** + uncertainty note. Resolve the contested cell by reading whether `engine_runner.py:654`
  `crt_compute(trade_id="Test:", …)` is inside live `EngineRunner.run()` or a harness (cite enclosing
  `def` + callers, e.g. `backtest_v2.py:2167`); and what `move` is at `scoring_engine.py:31`. Corroborate
  with `pyan_call_flow.dot` (`gen_pyan.py`) only — document the tooling gap.

Preliminary rows (HYPOTHESES; reachability starts `unknown` where contested):

| GD | Site | semantic | formula_equiv | exec_reach | decision_reach |
|---|---|---|---|---|---|
| 001 | live_engine_hook `body_ratio` (362) | same_quantity? | non_equivalent | unknown | **unknown** (contested) |
| 002 | live_engine_hook `wick_size` (361) | same_quantity? | non_equivalent | unknown | unknown |
| 003 | live_engine_hook `body_size` (360) | same_quantity | byte_identical | unknown | unknown |
| 004 | scoring_engine `disp_strength` (31) | name_collision_distinct? | non_equivalent | unknown | unknown |
| 005 | crt_engine_v2 `disp_strength` (1355) | name_collision_distinct | non_equivalent | reachable | reachable (hard REJECT) |
| 006/007 | crt_engine_v2 upper/lower_wick (1045/46) | name_collision_distinct | non_equivalent | reachable | unreachable (diagnostic) |
| 008/009 | crt_sweep_taxonomy upper/lower_wick (124/25) | name_collision_distinct | non_equivalent | unreachable (dead) | unreachable |
| 010 | rr_engine `candle_range` (59) | same_quantity | byte_identical | conditional (gate) | conditional |

**FREEZE Matrix v1** once every row's semantic/formula_equivalence/both-reachabilities/both-evidence-
chains/uncertainty are set. All `observed_*` remain `not_measured`. Matrix v1 is the Gate-1 deliverable.

## POST-GATE-1 SYNC

### 5. Refine F-047 from frozen evidence only (`docs/current-findings.md` + CLAUDE.md §6.2)
Upgrade the live `body_ratio` reachability from "UNVERIFIED / lands in auxiliary" to the **Matrix-v1
verdict with cited chains** — still NOT claiming production impact (preserve F-010/F-037 scoping). E-001:
sharpening an under-specified claim with new evidence, not a reversal.

## GATE 2 (unlocked only after Matrix v1 freeze)

### 6. Design the differential probe FROM verified chains — `scripts/analysis/feature_math_drift_probe.py` (NEW, READ-ONLY)
Mechanical eligibility: build **only for sites where `formula_equivalence == non_equivalent` AND
`decision_reachability ∈ {reachable, conditional}`**. byte_identical sites need no drift; execution-
reachable-but-decision-unreachable sites (006/007) and dead sites (008/009) are disposition-only. The
probe targets the **actual verified consumer path from Matrix v1**, never a pre-assumed
`s_breakout → CRT → fusion` chain. If 001 proves decision-unreachable, no flip-probe is built for it.

### 7. Measure value → score → decision (preserve denominators + event counts)
On a real M15 corpus (reuse `CandleLoader`): (a) **value-drift** — canonical vs current per bar (% bars
differing, |Δ| distribution, count of [0,1] violations: total_wick < body ⇒ body_ratio > 1);
(b) **score-drift** and (c) **decision-flips** — substitute canonical-vs-current into the *verified* path
under a **gate-ON** backtest, report flip **count/rate with denominator**. Strictly read-only.
**Scope caveat (E-001):** F-037 (research backtests run gate-OFF) + F-010 (live production unverified) —
a gate-ON flip-rate bounds *potential* impact; **production-loss claims prohibited absent production evidence.**

### 8. FREEZE Matrix v2 + rank remediation (defines Phase-B exits; fixes NOTHING)
Populate `observed_*`, freeze Matrix v2, rank by `decision_reachability × measured_decision_flip_rate ×
exposure`. Dispositions (all deferred to their own governed finding; a pin's GD-id is retired — via the
manifest — only in the change that resolves its site):
- non_equivalent + decision-reachable (e.g. 001/002 if confirmed) → behavior-changing finding, gated on
  measured flips + user approval.
- byte_identical (003, 010) → determinism-gated byte-identical finding (deferred).
- name_collision_distinct + decision-reachable (005) → **rename** finding (distinct quantity).
- name_collision + decision-unreachable/dead (006–009) → rename/accept or dead-code disposition.

## Critical files
- `scripts/analysis/feature_math_lint.py` — pin dict → GD-id records + compound `durable_key` (scan/
  classify logic unchanged)
- `docs/governance/feature-math-grandfather-retirements.json` — NEW append-only retirement manifest
- `tests/test_feature_math_lint.py` — set-monotonic + retirements-evidenced + well-formed + durable-key tests
- `docs/analysis/feature-math-divergence-adjudication.md` + `.json` — Matrix v1 (Gate 1) → v2 (Gate 2)
- `scripts/analysis/feature_math_drift_probe.py` — NEW, built in Gate 2 against verified paths
- `docs/current-findings.md`, `CLAUDE.md` §6.2 — F-047 note refinement (post-freeze)
- Reuse: `ast` scan + scope-stack in `feature_math_lint.py`; `CandleLoader` + corpus; `backtest_v2`
  gate-ON path; `gen_pyan.py`/`pyan_call_flow.dot` (reachability corroboration only)

## Verification
1. **Gate 1**: `pytest tests/test_feature_math_lint.py` — set-monotonic + retirements-evidenced +
   durable-key + well-formed green; existing floor green (10 pins match by `durable_key`). Bite tests:
   (a) edit a pinned RHS → pin stale, site resurfaces NEW; (b) move a pinned assignment to another method
   → qualname drift → stale; (c) add an 11th/new-id pin → `test_grandfather_set_monotonic` fails;
   (d) delete a retired id from the manifest → `CURRENT ∪ RETIRED == BASELINE` fails.
2. **Matrix v1**: all 10 rows carry semantic_class + formula_equivalence + BOTH reachability verdicts
   each **with a cited chain** + uncertainty; all `observed_*` = `not_measured`; contested cells resolved.
   Then F-047 note refined.
3. **Gate 2**: `python scripts/analysis/feature_math_drift_probe.py` → value/score/decision-flip report
   (with denominators) **only for non_equivalent + decision-reachable sites**; wrote nothing outside
   `docs/`/`reports/`. `observed_*` populated; Matrix v2 frozen.
4. **Scope guard**: `git diff` on the 10 divergent source files is EMPTY — only lint/tests/docs/harness/manifest changed.

---

## Prior phase — F-047 (COMPLETE, context only)

Shipped: ontology `derived_metrics` (FM-IDs / version / lifecycle / depends_on DAG); registry split
(`src/features/registry/` behind the `formula_registry` facade + scalar `derived_math.py`, never
`eval`'d); three enforcement layers (parity `test_derived_math.py`, ownership-lint
`feature_math_lint.py`, lineage exhaustiveness `test_feature_lineage.py`); parity-neutral
`crt_engine_v2:2539` routed through `candle_math.body_ratio` (determinism-verified). F-047 registered;
hash-neutral; 58 targeted tests green. This adjudication phase is the burn-down of the 10 pins that
phase grandfathered.
