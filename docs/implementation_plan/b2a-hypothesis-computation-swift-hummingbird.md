# Bottom-up Feature-DAG Certification — Milestone 2 (L3 swing-structural family)

## Context

Milestone 1 (L0→L2) is mechanically verified from the maintained artifacts (not the transcript):
the ledger resolver reports **28 PROMOTED · 2 SUPERSEDED · 10 READY · 8 BLOCKED**. The "swings
promoted but L3 deferred" concern is resolved — `swing_high`/`swing_low` are L1 (publication) and
*are* PROMOTED; the L3 structural events that consume them are deferred. Exact frontier:

- **READY (10):** `macd_line` (L1); `break_of_structure`, `displacement_retrace`, `higher_high`,
  `liquidity_sweep`, `lower_low` (L3); `hour_of_day`, `session`, `trend_strength`, `volatility_regime` (L4).
- **BLOCKED (8):** `macd_signal`←macd_line; `macd_hist`←macd_line,signal; `sweep_detected`/
  `double_sweep`/`candles_since_retest`/`retest_depth`←`liquidity_sweep`; `liquidity_distance`←
  `break_of_structure`; `liquidity_pressure_score`←`liquidity_distance`.

This milestone advances by **one strongly-coupled family** and stops: the swing-structural detection
family `higher_high`, `lower_low`, `break_of_structure`, `liquidity_sweep` — all READY, all computed
together in `feature_pipeline.compute_structure_liquidity` from the same causal swing refs. It is
certified **LEDGER-ONLY** (stateful structural detection stays out of the ontology WHAT/math layer,
per the header boundary). Approved execution order:

> **Resolve sweep equality semantics → strengthen dependency-bound PIT evidence → implement atomic
> family certification/promotion → certify the four-member family → mechanically recompute frontier →
> governance close-out → STOP.**

## Pinned semantics (resolved from code — invariant 4)

Authority = `src/features/feature_pipeline.py:457-484`. Refs are CAUSAL FC1-A:
`ref_high = last_swing_high_price.shift(1)`, `ref_low = last_swing_low_price.shift(1)` (publication-
delayed centered pivots, ffill'd). The four int8 outputs, copied EXACTLY (equality boundaries pinned):

- `higher_high = (high > ref_high)` — strict `>`.
- `lower_low = (low < ref_low)` — strict `<`.
- `break_of_structure = +1 if close > ref_high, -1 elif close < ref_low, else 0` — strict `>`/`<`.
- `liquidity_sweep = +1 if (high > ref_high) & (close <= ref_high); -1 elif (low < ref_low) &
  (close >= ref_low); else 0` — **sweep close-return is INCLUSIVE `<=` / `>=`** (`feature_pipeline.py:478-479`).
  The earlier chat summary's strict `<`/`>` was WRONG; the executable authority is inclusive.

## Scope boundary

Reaches **PROMOTED_PRODUCTION (identity)**, not ACTIVATION. No live pipeline math swap, retrain, or
recalibration; 38-dim intact; `PRODUCTION_BEHAVIOR_CHANGED = NO`. Certification is descriptive (§6.5).
After the family is promoted, **STOP** — do NOT certify the newly-unblocked derivatives or L4.

## Change-surface invariant (NOT "additive-only")

```
ALLOWED existing-file MODIFICATIONS:
  scripts/governance/feature_certification_state.py   (intended-quantity map)
  scripts/governance/feature_dag_certify.py           (CERTIFIED intended_quantity stamp + family transaction)
  CLAUDE.md  (F-054 dated L3 note)  ·  assistant_project.md (SESSION LOG)
ALLOWED APPENDS:
  docs/governance/feature_certification_ledger.jsonl  (8 events, in 2 atomic blocks)
ALLOWED NEW FILES:
  scripts/analysis/feature_dag_structural_certification.py
  tests/test_feature_dag_structural_certification.py
  docs/governance/feature_dag_structural_certification-<date>.{json,md} + .LATEST.json
FORBIDDEN (must remain byte-unchanged):
  ontology · registry · feature_pipeline · models · production config · live runtime
```

## Deliverables

### D1 — Establish intended quantity (invariant 4)
Add the four pinned strings above to the curated `_intended_quantities()` map in
`feature_certification_state.py` (currently `UNADJUDICATED` for them). Enhance
`feature_dag_certify.plan_certify` to stamp the current `intended_quantity` (from the witness map)
onto the emitted `CERTIFIED` event (SEEDED `UNADJUDICATED` baseline preserved — append-discipline).

### D2 — Structural certification probe — TWO oracles + equality-boundary probes
New `scripts/analysis/feature_dag_structural_certification.py` (READ-ONLY; M1 probe idiom: synthetic +
majors arms, immutable dated artifact + `.LATEST.json` sha256, exit 0/2). Two independent oracles,
both compared to the real `FeaturePipeline` columns by **exact integer equality** on shared post-warmup rows:

1. **Formula-parity oracle (centered reconstruction).** Centered rolling max/min (`w=2·SWING_WINDOW+1`,
   import `SWING_WINDOW`) → `.shift(SWING_WINDOW)` + ffill → refs → four flags. Proves the FORMULA
   matches. It LEAKS pre-shift, so it is the formula oracle ONLY — never the causality proof.
2. **Causal ONLINE oracle (the causality proof).** A sequential bar-by-bar implementation: at bar `t`
   confirm/publish the pivot for bar `t−k` using only bars `≤ t` (window `[t−2k, t]`), ffill the
   published swing price, derive refs + the four flags. It uses NO future information by construction.
   Its match to the pipeline column proves the pipeline's shifted-centered publication is genuinely
   causal at the structural-flag level (independent re-proof of FC1-A for these four).
3. **Equality-boundary probes.** Explicitly exercise/report rows where `close == ref_high` and
   `close == ref_low` (and `high == ref_high`, `low == ref_low`) to confirm the inclusive `<=`/`>=`
   sweep boundary and the strict `>`/`<` HH/LL/BOS boundaries are reproduced identically.

Verdict per node CERTIFIED/REJECT requires BOTH oracles match + boundary probes pass. Record in the
artifact + each cert event a **dependency-bound PIT evidence** block: `{referenced_artifact:
pit_phaseC_feature_certification.LATEST.json, referenced_floor: tests/test_pit_prefix_invariance.py,
repo_state_hash: <construction_protocol._repo_state_hash()>, causal_online_oracle: matched}` — so the
reference cannot silently go stale against changed pipeline/swing/repo state. Floor
`tests/test_feature_dag_structural_certification.py`: both oracles + boundary probes on synthetic;
overall CERTIFIED; deterministic.

### D3 — ATOMIC family certification/promotion (all-or-none)
Add a **family transaction** to `feature_dag_certify.py` (`certify-family` / `promote-family`
subcommands + pure `plan_certify_family` / `plan_promote_family`):
- **Preflight manifest** for the 4 members: each is READY (deps PROMOTED), the evidence artifact exists
  + its sha256, each member's `formula_hash` + `dependency_contract_hash`, and each member's expected
  prior state. Build ALL four CERTIFIED events in memory; if ANY validation fails, write NOTHING.
- Append the four CERTIFIED events in ONE write; then, only if the whole family re-resolves valid
  (all four CERTIFIED, deps still PROMOTED), build + append the four PROMOTED events in ONE write.
- The family claim is all-or-none — a crash between members cannot expose a partially-promoted family.
No supersession / no `invalidates` (new correct identities; nothing legacy to retire).
**Then recompute the frontier and STOP.**

### D4 — Governance close-out
- Append a dated L3 note to **F-054** (append-discipline — program continuation, not a new finding /
  not a reversal): family PROMOTED atomically, new frontier counts, ledger-only, not activated, both
  oracles + boundary probes green.
- `📝 SESSION LOG ENTRY` (§6) with Belief/ROI/Goal. Authoritative record = the ledger jsonl.

## Reuse map

| Need | Reuse |
|---|---|
| Probe skeleton + arms + immutable artifact/LATEST | `scripts/analysis/feature_dag_rolling_certification.py` |
| Exact pipeline formulas + `SWING_WINDOW` | `src/features/feature_pipeline.py:410-484` |
| Certify/promote + ordering gate + hashes | `scripts/governance/feature_dag_certify.py` |
| repo-state hash for PIT binding | `scripts/governance/construction_protocol.py` `_repo_state_hash()` |
| PIT coverage (dependency-bound reference) | `tests/test_pit_prefix_invariance.py`, `pit_phaseC_feature_certification.LATEST.json` |

## Verification (end-to-end)

1. `python scripts/analysis/feature_dag_structural_certification.py` → overall CERTIFIED; BOTH oracles
   match all four; equality-boundary probes pass; PIT-evidence block carries a fresh `repo_state_hash`.
2. `pytest tests/test_feature_dag_structural_certification.py -q` → green.
3. `feature_dag_certify.py certify-family higher_high lower_low break_of_structure liquidity_sweep
   --evidence <artifact>` then `promote-family …` — atomic; `status` shows the four PROMOTED and
   `sweep_detected/double_sweep/candles_since_retest/retest_depth` + `liquidity_distance` flipped
   BLOCKED→READY (the mechanical unblock proof). Verify the exact new frontier (expected **32 PROMOTED ·
   2 SUPERSEDED · ~11 READY · ~3 BLOCKED**) — read it, don't assert from prose.
4. Full floor regression green: `pytest tests/test_feature_dag_layers.py
   tests/test_feature_certification_ledger.py tests/test_feature_dag_invalidation.py
   tests/test_feature_dag_rolling_certification.py tests/test_feature_dag_structural_certification.py
   tests/test_feature_lineage.py tests/test_feature_math_lint.py tests/test_current_findings.py -q`.
5. `git status` matches the change-surface invariant above — confirm ontology / registry /
   feature_pipeline / models / production config are byte-unchanged; 38-dim intact.

**Deferred (next units, one at a time):** sweep/retest derivatives, then `liquidity_distance`→
`liquidity_pressure_score`, remaining L4, and CRT `displacement_retrace`; L6 activation is the
separate authorized gate.
