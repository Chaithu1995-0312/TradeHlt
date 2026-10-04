# `resolution_site` — design revision after the first measurement

## Context

The original plan (build stage-aware decision provenance, run it, review EXPANSION) is **executed**.
The recorder, the AST exhaustiveness guard, the harness cross-tab and the four-mode run all shipped
and are green. This revision exists because the measurement changed three things the design assumed.

**What the run produced** (XAUUSD M15, 47,197 aligned bars, corpus sha `4d73f5ce`, 18,155 engine events):

| injection | agreement | mismatches | pre-predicate | predicate-derived |
|---|---:|---:|---:|---:|
| none | **87.7047%** (41,394) | 5,803 | 1,748 | 4,055 |
| reset | 89.1624% | 5,115 | 750 | 4,365 |
| state_to | 98.6715% | 627 | 311 | 316 |
| full | 99.5762% | 200 | 4 | 196 |

**Three findings that force design changes:**

1. **The F-069 pin does not reproduce and the recorder is not why.** 87.7047% vs the recorded
   88.1560%. A control run with *all* instrumentation stripped returned `41394/47197 = 87.7047%`,
   bit-identical — so the recorder is behaviour-neutral. The −213 bars reconcile to per-state recall:
   DISPLACEMENT 97.59%→49.60% (−179), RANGE −21, SWEEP −11. **EXPANSION recall is 10.77%, identical
   to the pin.** Cause, source- and date-verified: `_displacement_entry_allowed` gate 0 is the F-074
   directional contract (authorized **2026-08-13**), which post-dates the F-069 report
   (**2026-08-05**). Corroborated by a pre-existing red (`test_funnel_sweep_to_displacement_bypasses_pipeline_flag`)
   that fails identically with instrumentation stripped. Classified **INDETERMINATE** on the
   object-identity guard, not Case 1.

2. **The two-way pre/post split is misleading, and the concurrent design only half-fixes it.**
   `docs/implementation_plan/resolution-site-classified-occupancy-delta-2026-09.md` correctly bans
   the binary and specifies a six-key `residual_histogram` that stops stuffing stage 3/4 into
   "predicate-derived". That fixes **stage** mixing. It does **not** fix the problem this run
   exposed, which lives *inside* `predicate_derived_funnel` — see the next section.

3. **§6.8 closed: `INTENTIONAL SEMANTIC SEPARATION`** (secondary `DOCUMENTATION GAP`).
   `crt_state_resolver.py:1348-1350` declares it verbatim: *"research EXP entry is inject-owned
   (DISPLACEMENT>EXPANSION / SWEEP>EXPANSION) + SHADOW collapse above."* At `injection=none` the
   resolver's only EXPANSION entry is shadow collapse, which fired **9 times in 47,197 bars** against
   the engine's 4,625. No threshold can enable a path the design routes through injection — which is
   why F-069's exhaustive 33-candidate sweep moved parity only +0.30pp.

## The one design change this run forces

**`predicate_derived_funnel` does not mean "the predicates were tested and failed."** It means the
funnel reached the loop. Derived from source, no new measurement needed:

- `ground_state_fallthrough` fires **only** when `cur ∉ _STICKY_STATES`
  (`= {SWEEP, DISPLACEMENT, EXPANSION, RETEST, EXECUTION}`, `crt_state_resolver.py:1840`).
- Under the default `htf_range`, the loop guard (`:1349-1355`) skips SWEEP / DISPLACEMENT /
  EXPANSION whenever `cur` is not already that state. So on **100%** of `ground_state_fallthrough`
  bars, all three structural states were skipped **before** their `when:` block was evaluated.
- Of the remaining six, `SHADOW_PENDING` / `EXPIRED` / `RESOLUTION` declare `when: {}` with
  `requires_memory`, so the memory-only rule skips them too; `EXECUTION`'s continuous gate is
  unconditionally closed on a real vector (F-069 Category B: `score`/`risk_score`/`crt_score` are not
  in `CANONICAL_FEATURES`).
- **Effective evaluated set = {RETEST, RANGE}: 2 of 9 declared states.**

Restated honestly, of the 4,055 "predicate-derived" residual bars at `injection=none`:

| n | reading |
|---:|---|
| 3,010 | `ground_state_fallthrough` — no state matched; all 3 structural states skipped unevaluated |
| 613 | `sticky_hold_no_match` — no state matched; 2 of 3 skipped unevaluated |
| **3,623 (89.3%)** | **"no state matched", with skips — not "predicates failed"** |
| 432 | `predicate_match` + `sticky_protects_range_match` — a predicate actually fired |

**Change:** sub-split `predicate_derived_funnel` into `predicate_fired` and
`no_match_after_geometry_skip`. This is a **reporting/derivation change, not new instrumentation** —
the discriminator is `cur ∈ _STICKY_STATES`, already implied by the existing `resolution_site` id.
It slots into the concurrent design's **PR2** histogram as a sub-key; it does not compete with it.

Without this split the headline reads "69.9% predicate-derived", which invites exactly the
threshold-tuning conclusion that F-069 already measured to be worth +0.30pp.

## Scope

1. **Report the sub-split** (this turn): the corrected four-way reading above, derived from the run
   already on disk. No code, no re-run.
2. **Fold the sub-key into PR2** (only if the user authorizes that PR sequence): add
   `predicate_fired` / `no_match_after_geometry_skip` under `predicate_derived_funnel` in
   `residual_histogram`, in `scripts/research/crt_state_confusion_matrix.py::build_confusion`.
   Invariant unchanged: bucket keys still sum to `obs.mismatches`.
3. **Resolve the F-069 pin** (governance, needs a decision — see Open questions): either re-pin
   against the current tree, or scope `88.1560%` to its 2026-08-05 epoch in
   `reports/crt_semantic_parity_report.md` + the F-069 row. **Do not** "fix" parity toward the old
   number; the delta is an authorized finding (F-074), not a regression.

## Out of scope (deliberate)

- **No occupancy repair.** The §6.8 verdict is `INTENTIONAL SEMANTIC SEPARATION` — the divergence is
  declared design, not a defect. Any change is a separate `BEHAVIOR_CHANGE_AUTHORIZED` turn, and the
  verdict argues against making one.
- **No parity maximization**, no `market_crt_states.yaml` edit, no config key, no G001.
- **No re-implementation of the recorder** — the concurrent design says so explicitly and it is right.
- Splitting `transition_validity_rewrite` by cause stays deferred (that design defers it too).

## Verification

Already established this turn, nothing further required for scope item 1:

- Recorder behaviour-neutral: instrumented vs stripped both `41394/47197 = 87.7047%`.
- AST guard mutation-tested: deleting one site assignment fails 2 tests; file restored SHA-identical.
- Floors: RC-003 **19/19**, other resolver floors **75/75**.
- Green floor **15 failed / 525 passed** — the *same 15 names* as the pre-change baseline measured
  earlier the same day. Zero new reds.
- Cross-tab backward compatibility verified synthetically (no `resolution_sites` → matrix identical,
  new fields empty).

For scope item 2, if authorized: re-run `injection=none` only and assert
`sum(residual_histogram.values()) == mismatches` and
`predicate_fired + no_match_after_geometry_skip == predicate_derived_funnel`. Pass `enriched=` to
`run_once` this time — the four-mode run recomputed the 47k-bar pipeline once per mode (~30 min
instead of ~8) because I omitted it.

## Open questions (user decisions, not blockers for the report)

1. **Sequencing.** The concurrent design gates work behind "do not implement until user authorizes
   PR1"; this session was told "implement" and did. Substantively compatible — that doc says
   *"recorder already exists in the working tree; do not re-implement"*, and this run produced exactly
   the classification its total function calls for. Surfaced as a §6.2 rule-3 `TruthConflict`, not
   resolved unilaterally.
2. **F-069 pin: re-measure or epoch-scope?**
3. Should the sub-split ship as a PR2 sub-key, or stay a report-only reading?

## Preflight (§1.5)

Concurrent Claude sessions are writing to this repo. `src/features/crt_state_resolver.py`,
`scripts/research/crt_state_confusion_matrix.py` and `assistant_project.md` carry this session's
committed-to-worktree changes; `tests/research/test_rc003_distinct_object.py` is untracked. Nothing
is committed. Never `git add -A`.
